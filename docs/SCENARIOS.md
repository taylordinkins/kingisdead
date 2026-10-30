# The King is Dead — Scenario Format

**Status:** DRAFT. Companion to `docs/RULES_SPEC.md` and `docs/ACTIONS.md`. Scenarios are JSON files
(`tests/scenarios/*.json`) that describe a position. Two users share one format:

- **Rule tests** load a scenario as a start state (`kingisdead/scenario.py`, Phase 2) and check legal
  actions and outcomes against R-IDs.
- **The setup editor** (Phase 4) produces and consumes `"kind": "setup"` scenarios and turns them into the
  chance-outcome sequence of `docs/ACTIONS.md` §3, so there is one code path.

A scenario is **a position, not a history**: it need not be reachable by legal play (the validator only
checks the constraints in §3), which keeps rule fixtures small.

## 1. Fields

Names: regions use the R-001 names (`"Moray"`, `"Strathclyde"`, `"Lancaster"`, `"Northumbria"`,
`"Gwynedd"`, `"Warwick"`, `"Essex"`, `"Devon"`); factions use `"S"`, `"W"`, `"E"` (R-003); cards use
`"scottish_support"`, `"welsh_support"`, `"english_support"`, `"assemble"`, `"negotiate"`,
`"manoeuvre"`, `"outmanoeuvre"`. A *count map* is `{"S": n, "W": n, "E": n}` where an absent key means 0.
Unknown keys are an error.

| Field | Kind | Type | Meaning | Default |
|---|---|---|---|---|
| `format` | both | `1` | format version | required |
| `kind` | both | `"setup"` \| `"state"` | `setup`: a fresh position (R-014); `state`: any position | required |
| `description` | both | string | free text for humans | `""` |
| `players` | both | 2 or 3 | R-007 | required |
| `slots` | both | 8 region names | the region shown on the card in slot 1, 2, …, 8 (R-010); a permutation of the 8 regions | required |
| `regions` | both | map region → count map | followers on each region | empty region |
| `courts` | both | list of `players` count maps | each player's court | required |
| `to_play` | state | int | player to act (at TURN_START) | 0 |
| `struggles` | state | int 0..8 | struggles resolved so far (R-303) | 0 |
| `region_state` | state | map region → `"S"` \| `"W"` \| `"E"` \| `"unstable"` | closed regions and how they closed (R-004) | open |
| `recent_win` | state | map faction → int | struggle number of each faction's latest win, −1 if none (R-303) | −1 each |
| `negotiation` | state | list of `players` entries, each a region name or `null` | the region whose card carries that player's spent disc, or `null` if unspent (R-006) | all `null` |
| `hands` | state | list of `players` lists of card names (repeats allowed for `assemble`) | cards still in hand (R-008) | the full starting hand |
| `pass_count` | state | int 0..players−1 | consecutive passes (R-103) | 0 |
| `last_play` | state | list of `players` entries, int or `null` | each player's most recent card-play number (R-401) | `null` each |
| `hand_empty` | state | list of `players` entries, int or `null` | the card-play number at which each player's hand emptied (R-401) | `null` each |
| `last_card` | state | `null` or `{"type": <card>, "reference_board"?: {...}}` | the most recent card played (R-102); `reference_board` is B* (R-216) | `null` |
| `example` | both | object | optional worked example: see §4 | none |

Derived, never written: `supply` (each faction's pool, R-005, minus regions minus courts); which slots are
face down (exactly slots 1..`struggles`, see V4); the instability discs on the board (the number of
`"unstable"` entries); the card-play total (V7).

`reference_board` has the shape `{"regions": {...count maps...}, "region_state": {...}}` and is only
allowed when `last_card.type` is `manoeuvre` or `outmanoeuvre` (R-216).

A `setup` scenario may use only `format`, `kind`, `description`, `players`, `slots`, `regions`, `courts`,
`example`; everything else takes its R-014 value.

## 2. Setup scenarios → chance sequence

The editor converts a valid `setup` scenario to the outcome sequence of `docs/ACTIONS.md` §3:

1. 8 region picks: the region IDs of `slots`, slot 1 first.
2. Court draws: for each player in seat order, that player's court as a faction list in ascending
   faction order (S, W, E), 2 draws.
3. Region fill: for regions 0..7, the region's followers minus the home followers (R-011), as a faction
   list in ascending faction order.

Applying this sequence to a fresh game yields exactly the scenario's position. (The sequence is one of
several that give the same position; draws of one faction are exchangeable, R-005.)

## 3. Validation

A scenario is rejected, with the failing rule, unless all of these hold.

- **V1** (R-005) For each faction, followers in `regions` + `courts` is at most the pool (18, or 16 with 2
  players); the supply is the difference.
- **V2** (R-004, R-302) Every region in `region_state` holds 0 followers.
- **V3** (R-304) Fewer than 3 regions are `"unstable"` unless the scenario is terminal (`struggles` may
  then be below 8; use `example.expect.terminal` to document it).
- **V4** (R-300, R-303) `struggles` equals the number of closed regions, and the closed regions are exactly
  the regions in slots 1..`struggles`.
- **V5** (R-303) Each `recent_win` value is −1 or a struggle number 1..`struggles`; non-negative values
  are distinct; a faction has −1 exactly when it controls no region; if a faction's value is *s*, the
  region in slot *s* is controlled by that faction.
- **V6** (R-006, R-213) A player's `negotiation` entry is non-null exactly when `negotiate` is not in
  their hand, and names a region; no two players name the same region. A card carrying a disc may be
  face up or face down.
- **V7** (R-102, R-401) Card-play total = Σ over players of (8 − hand size). `last_play` values are
  distinct integers in 1..total, `null` exactly for a player who has played nothing; the largest one
  belongs to the player who played the most recent card. `hand_empty` is non-null exactly for a player
  with an empty hand, and equals that player's `last_play`.
- **V8** (R-008) Each hand is a sub-multiset of the starting hand.
- **V9** (R-103) `pass_count` < `players`.
- **V10** (R-102, R-216) `last_card` is `null` iff the V7 total is 0; otherwise its `type` is a card
  the player who played the most recent card (V7) no longer holds (for `assemble`, at most one copy
  left in hand). `reference_board`, if present, obeys V1 and V2 on its own, and `last_card.type` is
  then `manoeuvre` or `outmanoeuvre`.
- **V11** (`setup` only, R-011..R-014) Every region holds exactly 4 followers; Moray has ≥2 Scottish,
  Gwynedd ≥2 Welsh, Essex ≥2 English; each court has exactly 2 followers; all V1 constraints hold.

## 4. The `example` block

Optional. It documents one move so a test can check the scenario against the spec:

```json
"example": {
  "actions": [1, 9],
  "expect": {
    "legal_after": {"1": [9]},
    "regions": {"Strathclyde": {"S": 3, "W": 2, "E": 1}},
    "supply": {"S": 3}
  }
}
```

`actions` are decision action IDs (`docs/ACTIONS.md` §2) applied in order from the scenario. `expect`
(all keys optional): `legal_after` maps a prefix length (as a string) to the exact sorted legal-action
list after that many actions; `regions` and `supply` list expected values after all the actions;
`terminal`, `winners` and `returns` describe an ended game; `phase` names the phase (ACTIONS.md §4).
Only listed keys are checked.

## 5. Shipped examples (`tests/scenarios/`)

| File | Rules exercised |
|---|---|
| `setup_basic.json` | R-010..R-014 (setup constraints), R-210/R-211 (Scottish Support) |
| `undo_block_outmanoeuvre.json` | R-215, R-216, R-217, R-102 (a blocked 1-for-2 forces 1-for-1) |
| `coronation_tiebreak.json` | R-403, R-404, R-405 (rank by recent win, rank-2 tiebreak) |
