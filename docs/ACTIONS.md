# The King is Dead — Action Catalogue

**Status:** APPROVED with the spec (2026-10-30). Companion to `docs/RULES_SPEC.md` (R-IDs below refer to it). Written in Phase 1
(PLAN.md §5.3, §5.4); **action IDs freeze when Phase 2 closes** (replays and playtest reports depend
on them). If this file and the spec disagree, the spec wins and this file is fixed.

## 1. Index conventions

| Index | Meaning | Source |
|---|---|---|
| region *r* ∈ 0..7 | 0 Moray, 1 Strathclyde, 2 Lancaster, 3 Northumbria, 4 Gwynedd, 5 Warwick, 6 Essex, 7 Devon | R-001 |
| faction *f* ∈ 0..2 | 0 Scottish, 1 Welsh, 2 English | R-003 |
| card *c* ∈ 1..7 | 1 Scottish Support, 2 Welsh Support, 3 English Support, 4 Assemble, 5 Negotiate, 6 Manoeuvre, 7 Outmanoeuvre | R-008 |

## 2. Decision action IDs (`num_distinct_actions` = 40)

| IDs | Name | Used in phase |
|---|---|---|
| 0 | `PASS` | TURN_START |
| 1–7 | `PLAY(c)` = *c* | TURN_START |
| 8–15 | `REGION(r)` = 8 + *r* | SUPPORT_TARGET, ASSEMBLE_S/W/E, NEG_FIRST, NEG_SECOND, NEG_DISC |
| 16–39 | `FOLLOWER(r, f)` = 16 + 3·*r* + *f* | MAN_FIRST, MAN_SECOND, OUT_SINGLE, OUT_FIRST, OUT_SECOND, SUMMON |

A `REGION(r)` identifies a region card by the region it shows (each region appears on exactly one
card). A `FOLLOWER(r, f)` identifies "a follower of faction *f* in region *r*" (followers of one
faction are interchangeable, R-005).

## 3. Chance outcomes (`max_chance_outcomes` = 8)

Setup (R-010..R-013) is a fixed-order run of chance nodes. Outcome IDs are independent of the
decision IDs above.

| Order | Count | Outcome | Distribution |
|---|---|---|---|
| 1. Region cards | 8 | region index *r*, assigned to slot 1, 2, …, 8 in turn | uniform over regions not yet placed (R-010) |
| 2. Court draws | 2 × *n* (seat order, 2 draws per player) | faction *f* | proportional to the bag's remaining count of each faction (R-012) |
| 3. Region fill | 26 (the 32 board followers minus the 6 home followers), regions 0..7 in order, each topped up to 4 | faction *f* | same bag distribution (R-013) |

Total chance nodes: 38 (2 players), 40 (3 players). Home followers (R-011) are placed with no chance
node. The manual setup editor (Phase 4/5, `docs/SCENARIOS.md`) emits the equivalent outcome sequence,
so there is one code path.

## 4. Phase machine

```
SETUP (chance) ─► TURN_START ─ PASS ─► [pass count = n? → struggle (R-300..R-304, automatic)] ─► TURN_START | TERMINAL
                      │
                      └ PLAY(c) ─► card sub-steps (0–3 decisions) ─► SUMMON (0–1) ─► TURN_START | (never terminal: struggles only follow a pass)
```

The power struggle is not a node: it runs inside the transition of the `PASS` that makes the pass
count reach *n* (R-105), and may end the game (R-304). The player to move is the acting player at all
decision nodes; chance nodes use the chance player.

| Phase | Entered after | Legal actions (mask) |
|---|---|---|
| TURN_START | setup; a summon; a card play or its last sub-step when the summon is skipped; a pass (no struggle); a struggle | `PASS` always (R-101, R-103); `PLAY(c)` for each card still in hand (R-101). With an empty hand only `PASS`. |
| SUPPORT_TARGET | `PLAY(1..3)` when ≥1 eligible region and supply of that faction ≥1 (R-210, R-211) | `REGION(r)` for each eligible region *r* (R-210) |
| ASSEMBLE_S, ASSEMBLE_W, ASSEMBLE_E | `PLAY(4)`; then each next phase in S → W → E order, skipping a faction with empty supply (R-212) | `REGION(r)` for every open region *r* |
| NEG_FIRST | `PLAY(5)` when ≥2 eligible cards (R-213) | `REGION(r)` for each eligible card that has an eligible partner with a higher region index |
| NEG_SECOND | NEG_FIRST | `REGION(r')` for eligible cards with *r'* > first |
| NEG_DISC | NEG_SECOND | the two chosen regions: `REGION(first)`, `REGION(second)` |
| MAN_FIRST | `PLAY(6)` when a legal swap exists (R-214, R-216) | `FOLLOWER(r1, f1)` with a legal canonical completion |
| MAN_SECOND | MAN_FIRST | `FOLLOWER(r2, f2)` with *r2* > *r1*, followers present, and the swap not blocked by R-216 |
| OUT_SINGLE | `PLAY(7)` when a legal swap exists (R-215); in 1-for-1 mode this first pick is not a "single" but keeps the name | `FOLLOWER(r1, f)` that has a legal completion in the mode below (in 1-for-1 mode a completion with *r2* > *r1*) |
| OUT_FIRST | OUT_SINGLE | `FOLLOWER(r2, f)`, a follower present, with *r2* bordering *r1* (R-002); 1-for-1 mode uses OUT_SINGLE → OUT_FIRST only; in 1-for-1 mode also *r2* > *r1* and the swap not blocked by R-216 |
| OUT_SECOND | OUT_FIRST, 1-for-2 mode only | `FOLLOWER(r2, f')` with the same *r2*, *f'* ≥ *f* of the first pair pick, a follower available (two if *f'* = *f*), swap not blocked (R-216) |
| SUMMON | after every card's effect, if any follower is on a region (R-201) | `FOLLOWER(r, f)` for each (region, faction) present on the board |
| TERMINAL | R-304 | none; returns by R-405 |

Phases whose preconditions fail are skipped: the card then has no effect (R-202) and play moves
straight to SUMMON, which is itself skipped if no follower is on any region.

## 5. Sub-step rules

### Support (R-210, R-211)
`PLAY(c)` → `REGION(r)` for one eligible region → place min(2, supply). No sub-steps if there is no
eligible region or the supply is 0.

### Assemble (R-212)
`PLAY(4)` → `REGION` for the Scottish follower → `REGION` for the Welsh → `REGION` for the English.
A faction with an empty supply gets no sub-step. At least one open region always exists when a card is
playable, so Assemble always has a target; if every faction's supply is empty it has no sub-steps.

### Negotiate (R-213)
`PLAY(5)` → `REGION(r1)` → `REGION(r2)` with *r2* > *r1*, both eligible (face up, no disc) → `REGION`
choosing which of the two cards gets the player's disc. The unordered pair {r1, r2} is chosen in
canonical order, so each swap has exactly one action sequence; the disc choice is a separate
decision. Fewer than two eligible cards → no sub-steps.

### Manoeuvre (R-214, R-216)
`PLAY(6)` → `FOLLOWER(r1, f1)` → `FOLLOWER(r2, f2)` with *r2* > *r1*. Every swap {(r1, f1), (r2, f2)} has
exactly one sequence (the lower region first). A first pick is legal only if some second pick
completes a swap whose result is not the reference board B* (R-216); if no swap is legal anywhere,
there are no sub-steps. Same-faction swaps are legal (a no-op, unless blocked by R-216).

### Outmanoeuvre (R-215, R-216)
When the card is played the **mode** is fixed from the position at that moment:
1-for-2 if any legal 1-for-2 swap exists, else 1-for-1 if any legal 1-for-1 swap exists, else none
(no sub-steps). A swap is legal if its result is not B* (R-216).
- **1-for-2:** `PLAY(7)` → `FOLLOWER(r1, fx)` (the single) → `FOLLOWER(r2, fy)` with *r2* bordering *r1*
  → `FOLLOWER(r2, fz)` with *fz* ≥ *fy* (the pair, in canonical faction order). The single's region and
  the pair's region are distinguishable, so no further canonicalisation is needed.
- **1-for-1:** `PLAY(7)` → `FOLLOWER(r1, f1)` → `FOLLOWER(r2, f2)` with *r2* bordering *r1* and *r2* > *r1*
  (a 1-for-1 swap is symmetric; the lower region goes first). No third pick.

Earlier picks are legal only if they have a legal completion in the current mode.

### Undo block (R-216, R-217)
The state stores the reference board B* (region contents and states, R-004) as defined in R-216 (D22: if the summoned follower's region held none of that faction before L's effect, B* is void and nothing is blocked):
the position before L's effect with L's summoned follower removed. It is captured when L's effect starts,
completed when L's summon is made, and cleared by any other card play (R-217). Every mask above that says "not blocked" applies only when the card being resolved is the same type as L (Manoeuvre vs Manoeuvre, Outmanoeuvre vs Outmanoeuvre; otherwise nothing is blocked, R-216) and compares the candidate swap's resulting board
(before its own summon) with B*. The observation must expose enough of B* for this to be reproduced.

### Summon (R-201)
`FOLLOWER(r, f)` for any (region, faction) with at least one follower on the board. Skipped when none.

## 6. Mask ↔ rule coverage

| Rule | Where it surfaces |
|---|---|
| R-007 | game construction (player count validated) |
| R-100, R-106 | `current_player` after every transition (including after a struggle); an empty hand has only `PASS` at TURN_START |
| R-015 | invariant checker, run after every action and chance node |
| R-101, R-103 | TURN_START mask |
| R-102, R-401 | transition on `PLAY`: hand update, play counter, hand-empty time |
| R-104, R-105 | transition on `PASS` / `PLAY`: pass count; struggle trigger |
| R-200 | every mask that places or moves followers lists open regions only |
| R-201 | SUMMON mask |
| R-202 | skipped phases fall through to SUMMON |
| R-210, R-211 | SUPPORT_TARGET mask |
| R-212 | ASSEMBLE_S/W/E masks |
| R-213 | NEG_* masks |
| R-214 | MAN_* masks |
| R-215 | OUT_* masks and the mode |
| R-216, R-217 | "not blocked" conditions; B* maintenance |
| R-300..R-304 | automatic, inside the `PASS` transition |
| R-400, R-402..R-405 | TERMINAL: `returns()` |
| R-010..R-014 | chance nodes of §3 |

## 7. Game-length bound

Decisions per card play ≤ 5 (the play, up to 3 sub-steps, the summon). A player plays at most 8 cards
(R-102), so card-play decisions ≤ 5 · 8 · *n*. Passes: each pass-run is ended by a struggle (≤ 8 runs of
*n* passes) or by a card play (≤ 8*n* runs of ≤ *n* − 1 passes), so passes ≤ 8*n* + 8*n*(*n* − 1) = 8*n*².
`max_game_length` = 40*n* + 8*n*² (2 players: 112; 3 players: 192), counting player decisions only
(chance nodes are bounded separately by `max_chance_nodes_in_history`: 38 and 40).
