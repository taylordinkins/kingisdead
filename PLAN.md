# The King is Dead — OpenSpiel Implementation Plan

**Status:** Draft v2 · 2026-10-30
**Repository:** `taylordinkins/kingisdead` (default branch `master`)
**Rules source:** *The King is Dead*, Second Edition rulebook (Peer Sylvester, Osprey Games 2020)
**Target framework:** OpenSpiel `open-spiel==2.0.2` (Python ≥ 3.11; wheels for macOS arm64, Linux, Windows)

### Progress
- [x] Phase 0 — Scaffold & OpenSpiel API spike (closed 2026-10-30, see docs/phase-reports/phase-0.md)
- [x] Phase 1 — Rules spec ✋ *you review* (closed 2026-10-30, see docs/phase-reports/phase-1.md)
- [x] Phase 2 — Engine (2–3 players, base game) (closed 2026-10-30, see docs/phase-reports/phase-2.md)
- [x] Phase 3 — Server + web shell ✋ *playtest #1* (closed 2026-10-31, see docs/phase-reports/phase-3.md; playtest pending)
- [x] Phase 4 — Board UI + setup editor ✋ *playtest #2* (closed 2026-10-31, see docs/phase-reports/phase-4.md; playtest pending)
- [ ] Phase 5 — Bots (MCTS, heuristic) ✋ *playtest #3*
- [ ] Phase 6 — 4-player teams
- [ ] Phase 7 — Advanced game (cunning actions)
- [ ] Phase 8 — Trained policies

---

## 1. Goal

A faithful, well-tested implementation of *The King is Dead* as a **Python OpenSpiel game**, playable by humans in a **browser** against other humans and bots, and usable unchanged by OpenSpiel algorithms for later RL work.

**Done for v1 means:**
1. `pyspiel.load_game("python_king_is_dead", {"players": 2})` (and `3`) works and passes OpenSpiel's random-simulation tests.
2. Every rule in `docs/RULES_SPEC.md` has at least one test that cites its rule ID.
3. You can play a full 2- or 3-player game in the browser against any mix of humans, random, MCTS and heuristic bots, and report a problem with one click.

## 2. Scope

| In v1 | Later phases | Out of scope |
|---|---|---|
| Base game, 2 and 3 players | 4-player teams (Phase 6) | C++ port (revisit only if training speed demands it) |
| Random setup + manual setup editor | Advanced game / cunning actions (Phase 7) | Online multiplayer across machines, accounts |
| Web UI: hotseat, random, MCTS, heuristic seats | Trained-policy opponents (Phase 8) | Mobile-optimised UI |
| Playtest report button + replay export | | Reproducing the published board art |

## 3. Decisions log

| # | Topic | Decision | Notes |
|---|---|---|---|
| D1 | Language | Python game registered via `pyspiel.register_game` | No C++ build; fastest iteration |
| D2 | Framework version | Pin `open-spiel==2.0.2`, Python 3.12 | 2.0 is a new major; Phase 0 verifies the Python game API before we build on it |
| D3 | Player counts | 2 and 3 first; 4 (teams) in Phase 6 | 2-player removes 2 followers per faction (48 total) |
| D4 | Advanced game | Phase 7, registered as a **separate game** `python_king_is_dead_advanced` | It's imperfect information (hidden hands); `GameType.information` is per registered game |
| D5 | Web stack | FastAPI backend + React/TypeScript (Vite) frontend, **game-agnostic shell** + per-game board plugin | OpenSpiel has no browser UI of its own (only the terminal `mcts.py` example); the shell is reusable for future games |
| D6 | Opponents | Hotseat humans, random, MCTS, heuristic; trained policies later | Any seat can be any type |
| D7 | Action encoding | Sequential sub-decisions (card → targets → summon), same player keeps acting until the turn ends | Small, fixed action space (40 IDs) |
| D8 | Returns | Zero-sum: sole winner +1, others −1/(n−1) | Shared wins: see D9 |
| D9 | Unresolvable ties | Shared win (draw) among still-tied players | Winners each get (n−k)/(k·(n−1)), losers −1/(n−1); still sums to 0. Chosen over a seat-order house rule to avoid seat bias in RL |
| D10 | Discard visibility | UI shows every player's full play history | Base game is perfect information anyway |
| D11 | Bug reports | In-game **Report** button → `playtest/reports/*.json` | Each fixed report becomes a regression test |
| D12 | Setup | Random setup via chance nodes **plus** a manual setup editor | Amended 2026-11-01 (D30): sessions load a `setup` scenario directly via `load_scenario`; the position equals the chance-outcome sequence (verified on `setup_basic` and 40 random setups), but the editor does not emit one |
| D13 | Adjacency | Table in §4 C1, confirmed against the physical board | |
| D14 | Model use (2026-10-30) | Sonnet does routine implementation and test writing; Haiku does search and long test/sim runs; Opus is reserved for rules audits and code review | Main session defaults to Sonnet (`.claude/settings.json`) and orchestrates rather than writing large changes. See §8 |
| D15 | Spec lock (2026-10-30) | `docs/RULES_SPEC.md` Status line DRAFT → APPROVED → AMENDING; a hook blocks edits while APPROVED | Only the user changes the Status line |
| D16 | Tests ahead of code (2026-10-30) | Spec tests carry `@pytest.mark.pending("R-0xx")` and run as non-strict xfail until the implementer removes the marker | Keeps the suite green so the stop gate can be strict |
| D17 | Test independence (2026-10-30) | `spec-test-writer` can't read `kingisdead/` source (hook-enforced); it writes against the spec and `tests/harness.py` | Disagreements between tests and code surface bugs or spec ambiguities |
| D18 | Persistence (2026-10-30) | Persist action histories, never `serialize()` strings; never deserialize client input | Deserialization unpickles `__dict__` without replaying history (docs/OPENSPIEL_NOTES.md) |
| D19 | Type stub (2026-10-30) | pyspiel type stub in `typings/` keeps pyright strict on engine code | Only signatures confirmed against the installed 2.0.2; extend as needed |
| D20 | Undo block edge cases (2026-10-30) | A no-op same-faction Manoeuvre swap is blocked like any exact reverse; an exact 1-for-1 Outmanoeuvre reverse is blocked | User-confirmed; R-216 |
| D21 | Undo block is board-based (2026-10-30) | A same-type play is blocked if its result equals the board before the previous Manoeuvre/Outmanoeuvre with that play's summoned follower removed; lifted by the next card played. Supersedes D20's pick-based wording; D20's no-op case still holds | User-confirmed; R-216, R-217. Needs a reference board in state/observation |
| D22 | B* void case (2026-10-30) | If L's summoned follower's region held none of that faction before L's effect, B* is void and nothing is blocked | User-confirmed in close-phase; amends R-216 (needs spec unlock), ACTIONS §5, SCENARIOS |
| D23 | Serialization of scenario states (2026-10-30) | Phase 2 closed with scenario-loaded states not serializable (empty history); persistence stays history-based (D18) | See Backlog; code-reviewer finding 4 |
| D24 | End-type labels (2026-10-30) | `sim_stats` reports "invasion" (3 unstable regions) and "coronation" | User-approved at unit 12 |
| D25 | Spec amendment (2026-10-30) | R-216 Example 4 now cites `undo_block_void.json` as an Outmanoeuvre exercise of the same void rule, not as the Manoeuvre example itself | User-approved pointer fix; no behaviour change |
| D26 | Typed GameView (2026-10-31) | `GameView` carries typed top-level `legal_actions`, `current_player`, `is_terminal`, `returns`, `winners`, labelled `history` and `dev_mode`; the game-specific `view` stays opaque for the board plugin, so the shell is game-agnostic | User-approved after unit 7 |
| D27 | Names from the server (2026-10-31) | The KID view sends `faction_names` and `card_names` from `constants.py`; the web has no copy | User-approved after unit 9 |
| D28 | Per-session locking (2026-10-31) | Handlers stay sync and hold a per-session `RLock`; Phase 5 slow bots must not run inside it | code-reviewer must-fix |
| D29 | Web toolchain (2026-10-31) | Node 20 (nvm) for web work; Vite 5 / Vitest 2 and `rollup@4.67.2` pins stay until cleaned up; Playwright pinned to 1.64.1 | See Backlog |
| D30 | Scenario sessions and click UI (2026-10-31) | Sessions carry the scenario JSON and replay history over its start state (setups load directly, not as a chance sequence; results checked identical); only a forced PASS auto-plays (R-106), every other single action waits for a click | User-approved; D12 and SCENARIOS §2 amended 2026-11-01 |

## 4. Rules clarifications

The rulebook is silent or ambiguous on these. They become numbered entries in `docs/RULES_SPEC.md`. Items marked ⚑ are defaults I chose that weren't explicitly discussed — **veto any of them during Phase 1 review.**

**C1 — Region adjacency** (France is not a region; it only holds instability discs)

| Region | Borders |
|---|---|
| Moray | Strathclyde |
| Strathclyde | Moray, Lancaster, Northumbria |
| Lancaster | Strathclyde, Northumbria, Gwynedd, Warwick |
| Northumbria | Strathclyde, Lancaster, Warwick, Essex |
| Gwynedd | Lancaster, Warwick, Devon |
| Warwick | Lancaster, Northumbria, Gwynedd, Essex, Devon |
| Essex | Northumbria, Warwick, Devon |
| Devon | Gwynedd, Warwick, Essex |

Home regions: Scots → Moray, Welsh → Gwynedd, English → Essex.

**C2 — Manoeuvre / Outmanoeuvre "undo" block.** An undo is the exact reverse swap of the most recent action, when that action was another player's Manoeuvre (or Outmanoeuvre):
- Manoeuvre undo: swapping the same two regions so the same two factions move back.
- Outmanoeuvre undo: the original moved faction *x* from R1→R2 and factions {*y*,*z*} from R2→R1; the undo is taking *x* from R2 and {*y*,*z*} from R1.
- **Superseded by D21 (2026-10-30):** the block is board-based, defined in R-216 (reference board = pre-L board minus L's summoned follower); the pick-based description above is the intuition only.
- The block lasts until any player plays a card. Passes don't lift it; the original player's summon doesn't lift it. ⚑ Power struggles also don't lift it (literal reading: only *actions* count).

**C3 — Winner determination and fallbacks**
- *Coronation ranking:* sort factions by (regions controlled ↓, index of most recent power struggle won ↓). A faction that never won has index −1. Two factions can only tie here if both have 0 regions; that rank is then **undefined**.
- *Coronation winner:* (1) most followers of rank-1 faction; (2) among tied, most of rank-2 faction — **skipped if rank 2 is undefined**; (3) among still tied, the earliest player to have emptied their hand wins (any player who emptied beats any who didn't); (4) if none of the still-tied players emptied their hand → shared win (D9).
- *Invasion winner:* most complete sets (min of a player's three faction counts); among tied, the player who most recently played an action card; if none of the tied players ever played one → shared win.

**C4 — Turns and passing**
- Turn order is increasing player index (= clockwise). ⚑ Player 0 starts; the UI lets you choose who sits in seat 0 ("most recently visited a castle").
- A power struggle triggers when the consecutive-pass count reaches the number of players. It resolves automatically (no decision), the count resets, and play continues with the next player in rotation.
- ⚑ A player with no cards left has exactly one legal action, PASS. The UI and bots auto-submit it.
- The game ends when the struggle that places the third instability disc has finished (invasion, R-304), otherwise after the 8th power struggle (coronation).

**C5 — Power struggle.** The faction with strictly the most followers takes control. A tie for most, or an empty region, makes the region unstable. All followers in the region return to the supply. The region card is flipped face down; the order of resolved struggles is recorded for C3.

**C6 — Summon.** Mandatory after every action if any follower is on the board: choose one (region, faction) follower and move it to your court. If the board is empty, skip. Never from the supply.

**C7 — Support cards.** Eligible target regions are uncontrolled regions that either border a region with that faction's control disc, or — if the faction's home region has no control/instability disc — border the home region. The home region itself is eligible only via the first clause. Fewer than 2 in supply → place as many as possible. No eligible region → no effect (card is still played and summon still happens).

**C8 — Partial actions.** Every card in hand is always playable. "Full effect if any instance exists anywhere" is enforced through legal-action masks (e.g. Outmanoeuvre must be 1-for-2 if any bordering pair allows it, else 1-for-1, else no effect).

**C9 — Negotiate.** Pick two distinct face-up region cards without a negotiation disc, swap their slots, then place your disc on one of them (your choice). Fewer than two eligible → no effect.

**C10 — Assemble.** Place one Scottish, then one Welsh, then one English follower, each into any uncontrolled region; skip a faction whose supply is empty.

## 5. Architecture

### 5.1 Repository layout

```
kingisdead/                   # repository root
├─ PLAN.md
├─ CLAUDE.md                  # commands, conventions, guardrails for agent sessions
├─ .claude/
│  ├─ settings.json           # default model, permission allowlist, hooks
│  ├─ agents/                 # implementer, spec-test-writer, Explore, sim-runner, rules-auditor, code-reviewer
│  ├─ skills/                 # start-phase, next-task, close-phase, triage-report
│  ├─ hooks/                  # check.py (stop gate), protect_spec.py, format_py.py, block_engine_reads.py
│  └─ rules/                  # path-scoped conventions: engine.md, web.md, spec.md
├─ .github/workflows/ci.yml   # ruff, pyright, fast + slow tests on every push and PR
├─ docs/
│  ├─ RULES_SPEC.md           # numbered rules (R-001…), the contract tests cite
│  ├─ ACTIONS.md              # action-ID table + turn phase machine
│  ├─ phase-reports/          # evidence report written by /close-phase for each phase
│  └─ rules/                  # rulebook PDF (local only, git-ignored)
├─ kingisdead/
│  ├─ constants.py            # regions, adjacency, factions, cards, counts
│  ├─ rules.py                # pure functions: eligibility, struggle, scoring
│  ├─ actions.py              # encode/decode, human-readable labels
│  ├─ game.py                 # pyspiel Game/State + registration
│  ├─ observer.py             # observation tensor/string
│  ├─ scenario.py             # build states from scenario JSON / setup editor
│  └─ bots/heuristic.py
├─ server/                    # FastAPI app: generic game sessions + kingisdead adapter
├─ web/                       # React + TS (Vite): shell/ + games/king-is-dead/
├─ tests/
│  ├─ rules/                  # test_R###_*.py, one file per rule group
│  ├─ scenarios/*.json
│  ├─ regressions/            # one test per fixed playtest report
│  └─ playthroughs/           # golden playthrough files
├─ tools/                     # play_text.py, replay.py, sim_stats.py (dev only)
└─ playtest/reports/
```

Tooling: `uv`, `pytest` + `hypothesis`, `ruff`; `npm` + Vite + Vitest; one Playwright smoke test.

### 5.2 OpenSpiel game definition (confirmed against 2.0.2, see docs/OPENSPIEL_NOTES.md)

- `short_name="python_king_is_dead"`, `dynamics=SEQUENTIAL`, `chance_mode=EXPLICIT_STOCHASTIC`, `information=PERFECT_INFORMATION`, `utility=ZERO_SUM`, `reward_model=TERMINAL`, `min_num_players=2`, `max_num_players=3` (→ 4 in Phase 6).
- Parameters: `players` (int, default 2), declared via `parameter_specification={"players": 2}`. `load_game` does not enforce the player-count range for Python games, so `Game.__init__` validates it and builds `GameInfo(num_players=…)` from the parameter.
- `num_distinct_actions=40`, `max_chance_outcomes=8`, `max_game_length` computed from bounds and counting **player decisions only** (≤8 cards × sub-steps per player + bounded passes). Chance nodes are not counted in 2.0.2 (`random_sim_test` enforces this); bound them separately by overriding `Game.max_chance_nodes_in_history()` (setup draws).
- Observation via `Game.make_py_observer` (flat float32 `tensor` + named `dict` views + `set_from`/`string_from`); state serialization is the default (history + pickled `__dict__`), so all state attributes must be picklable.

### 5.3 Turn phase machine

```
SETUP (chance) ──► TURN_START ──PASS──► (n consecutive passes → resolve struggle) ──► TURN_START / TERMINAL
                        │
                        └─PLAY_CARD──► card sub-steps (0–3 decisions) ──► SUMMON (0–1) ──► TURN_START  (struggles, and so TERMINAL, follow only a PASS; see docs/ACTIONS.md §4)
```

Card sub-steps:

| Card | Sub-decisions |
|---|---|
| Scottish / Welsh / English Support | target region |
| Assemble | region for Scot, region for Welsh, region for English (skipping empty supply) |
| Negotiate | first region card, second region card, which one gets the disc |
| Manoeuvre | follower A (region, faction), follower B in a different region |
| Outmanoeuvre | single follower in R1, first follower in bordering R2, second follower in R2 |

To keep the game tree small, duplicate orderings are canonicalised (Manoeuvre: B's region index > A's; Outmanoeuvre pair: second faction index ≥ first). The UI sorts the user's clicks into canonical order.

### 5.4 Action IDs

| IDs | Meaning | Used by |
|---|---|---|
| 0 | PASS | turn start |
| 1–7 | PLAY card: Scot Support, Welsh Support, English Support, Assemble, Negotiate, Manoeuvre, Outmanoeuvre | turn start |
| 8–15 | REGION *r* | support target, assemble placement, negotiate card picks, disc placement |
| 16–39 | FOLLOWER (*r*, *f*) = 16 + 3·*r* + *f* | manoeuvre/outmanoeuvre picks, summon |

Chance outcomes: region-card shuffle (8 sequential picks, uniform over remaining regions), then court draws (2 per player, in seat order), then region fills (fixed region order). Each bag draw's outcome is a faction (0–2), weighted by remaining bag counts.

### 5.5 Observation

Perfect information, so information state = observation. Tensor, from the observing player's perspective (own seat first): followers per region per faction; control state per region (none/S/W/E/unstable); region-card slot order, face-down flags, negotiation discs; supply counts; each player's court counts and remaining cards; negotiation disc availability; current phase and pending sub-decision context; consecutive-pass count; undo-block record; hand-emptied order; last-card-played order. The string form doubles as the debug view.

### 5.6 Server

- FastAPI; **the action history is the single source of truth** — state is rebuilt by replaying it. This makes undo, rewind, replay and reports trivial and exact.
- Game-agnostic `GameAdapter` interface: `load(params)`, `view(state, seat)` → JSON, `action_meta(state, id)` → `{label, kind, region?, faction?, card?}`. `view` takes a seat now so hidden hands in Phase 7 need no redesign.
- Endpoints: create game (params, seats, setup mode), get view, post action, back (to start of current human turn), rewind (dev mode), report, export/import replay.
- Bots run server-side; frontend polls (WebSocket only if polling proves sluggish).

### 5.7 Web

- **Shell (reusable):** lobby (game, seats, setup), action log, *legal-action list fallback* (any game is playable before its board exists), bot-thinking indicator, Back, Rewind, Report, replay export/import.
- **King is Dead plugin:** our own schematic SVG map (not the published art), clickable regions and cubes, region-card track with slot numbers and discs, courts, supply, France, end-of-game scoring breakdown that shows each ranking and tiebreak step.
- **Setup editor:** set court contents, region contents and region-card order; validated against bag counts; sessions load the result directly (D30), equivalent to the chance sequence.

### 5.8 Bots

- **Random:** uniform over legal actions.
- **MCTS:** OpenSpiel's `MCTSBot` with random-rollout evaluator; simulations configurable per seat.
- **Heuristic:** greedy one-turn lookahead scoring court strength against projected region control.
- **Trained (Phase 8):** loaded as a seat type through the same bot interface.

## 6. Verification strategy

Layered, cheapest first:

1. **Rule unit tests** — named `test_R###_…`, written from the spec *before* the code, using small scenario JSON fixtures.
2. **Invariants after every action** in random simulations: cube conservation (supply + board + courts = 48 or 54); controlled/unstable regions hold no followers; face-down region cards = resolved struggles; ≤ 3 instability discs; hand sizes consistent; non-terminal states have ≥ 1 legal action; returns sum to 0.
3. **OpenSpiel conformance** — `pyspiel.random_sim_test` (with serialization) over thousands of games.
4. **Golden playthroughs** — fixed-seed playthrough files; any diff must be explained in the PR.
5. **Independent rules audit** — a fresh-context agent compares each card's implementation against the rulebook text and the spec, without seeing the implementer's reasoning.
6. **Human playtests** — you at each ✋ checkpoint, reporting with the Report button.

Layers 1–3 are enforced mechanically as work happens: a Stop/SubagentStop hook runs lint and the fast suite whenever Python files changed and won't let a session or implementer finish red, and CI runs everything, including the slow simulations, on every push.

**Report → fix loop:** reproduce from the report's replay → add a failing regression test → fix → green → mark the report resolved.

## 7. Phases

Each phase starts with a short plan and task list and ends with its exit criteria demonstrated. ✋ = stop for your review before moving on.

**Phase 0 — Scaffold & API spike**
- ✅ `uv` project, pinned `open-spiel==2.0.2`, ruff, pytest, pyright, CI, `CLAUDE.md`, agents, skills, hooks (2026-10-30; OpenSpiel 2.0.2 installs and runs on Python 3.12).
- ✅ Register a toy Python game with chance nodes and confirm, on 2.0.2: `register_game`/`GameType` fields, observer API, `random_sim_test`, playthrough generation, `MCTSBot` on a Python game. Record findings in §5.2.
- *Exit:* `uv run pytest` green; spike notes committed.

**Phase 1 — Rules spec ✋**
- `docs/RULES_SPEC.md` (numbered rules from the rulebook + §4 clarifications), `docs/ACTIONS.md`, scenario JSON format.
- Independent audit of the spec against the rulebook.
- *Exit:* you approve the spec. After approval, behaviour changes require a spec change you sign off.

Task list (approved 2026-10-30, branch `phase-1/rules-spec`):
- [x] 1. Components, setup and turn flow (regions, C1, factions, counts, setup, turn order, PASS, C4) → `docs/RULES_SPEC.md`
- [x] 2. Six action cards plus summon (C7, C10, C9, C2, C8, C6) → `docs/RULES_SPEC.md`
- [x] 3. Power struggle, end of game, scoring (C5, C3, D8, D9) → `docs/RULES_SPEC.md`
- [x] 4. Action catalogue: IDs, phase machine, canonical ordering, masks → `docs/ACTIONS.md`
- [x] 5. Scenario JSON format plus 2–3 examples → `docs/ACTIONS.md` or `docs/SCENARIOS.md`, `tests/scenarios/*.json`
- [x] 6. Independent audit vs rulebook (`rules-auditor`)
- [x] 7. Fix round, Phase 1 report, ✋ user review and approval

**Phase 2 — Engine (2–3 players, base game)**
- `constants`, `rules`, `actions`, `game`, `observer`; tests first per rule ID; invariant checker; `tools/play_text.py` for agent self-play debugging; golden playthroughs for 3 seeds; card-by-card independent review.
- *Exit:* all rule tests green; `random_sim_test` passes; 10,000 random games with zero invariant violations; `sim_stats` report (end-type mix, game length) recorded.

Task list (approved 2026-10-30, branch `phase-2/engine`; each unit: `spec-test-writer` first, then `implementer`):
- [x] 1. Constants and board (R-001–R-006, R-008) → `kingisdead/constants.py`
- [x] 2. Actions and chance encoding (ACTIONS §1–3, R-007) → `kingisdead/actions.py`
- [x] 3. Setup and game skeleton (R-007, R-010–R-015, R-100) → `game.py`, `scenario.py`
- [x] 4. Turn start, pass and phase machine (R-101–R-106) → `game.py`, `rules.py`
- [x] 5. Support cards, summon and placement (R-200–R-202, R-210, R-211)
- [x] 6. Assemble and Negotiate (R-212, R-213)
- [x] 7. Manoeuvre, Outmanoeuvre and undo block (R-214–R-217); `rules-auditor` spot check
- [x] 8. Power struggle (R-300–R-304); `rules-auditor` spot check
- [x] 9. End of game and scoring (R-400–R-405); `rules-auditor` spot check
- [x] 10. Observer (§5.5) → `observer.py`
- [x] 11. Scenario loader and invariant checker → `scenario.py`, `tests/support/invariants.py`
- [x] 12. Tools, sims, golden playthroughs (`play_text.py`, `sim_stats.py`, 10,000-game slow test, 3 seeds)
- [x] 13. Card-by-card independent review (`rules-auditor`) and fix round

**Phase 3 — Server + web shell ✋ playtest #1**
- FastAPI + adapter; React shell with legal-action list and a text board; human and random seats; Report and replay export; Playwright smoke test that finishes a game against the random bot.
- *Exit:* you play at least one hotseat game and one game against random, and file reports.

Task list (approved 2026-10-30, branch `phase-3/server-web-shell`; server/web units have no rule IDs, so `implementer` writes their tests). Defaults: frontend polls; sessions in memory plus JSON export; Rewind only with a server dev flag; code-reviewer and rules-auditor run at `/close-phase`. Phase 3 board is text only; graphics are always our own schematic art, never the published art.
- [x] 1. Adapter interface and KID adapter (`GameAdapter`: `load`, `view`, `action_meta`; scoring breakdown) → `server/adapters/`, `tests/server/test_adapter.py`
- [x] 2. Session store with history replay (apply, back, rewind; no deserialization, D18) → `server/sessions.py`
- [x] 3. FastAPI endpoints (create, view, action, back, rewind, export/import; seeded chance auto-resolve) → `server/app.py`, `server/schemas.py`
- [x] 4. Bot seats (`human`, `random`; server-side auto-advance; bot-thinking flag) → `server/bots.py`
- [x] 5. Report endpoint (D11) → `server/reports.py`, `playtest/reports/`
- [x] 6. OpenAPI type generation and `web/` scaffold (Vite, React, strict TS, Vitest; confirm Node first) → `tools/export_openapi.py`, `web/`
- [x] 7. Shell: lobby, game screen, legal-action list, bot-thinking indicator, polling → `web/src/shell/`
- [x] 8. Shell: action log, Back, Rewind, Report dialog, replay export/import → `web/src/shell/`
- [x] 9. King is Dead text-board plugin and plugin registry → `web/src/games/king-is-dead/`
- [x] 10. Playwright smoke test (full game vs random bot), CI and `CLAUDE.md` commands → `web/e2e/`, `.github/workflows/ci.yml`

**Phase 4 — Board UI + setup editor ✋ playtest #2**
- SVG board with click-to-act, region-card track, courts, history, Back/Rewind, scoring breakdown, setup editor.
- *Exit:* you mirror at least one physical-table setup in the editor and play it through.

Task list (approved 2026-10-31, branch `phase-4/board-ui-setup-editor`). Decision: scenario games (option A) keep the scenario JSON in the session and replay history over its start state; export carries the scenario (closes the Phase 2 scenario-serialize backlog item). The map follows the rulebook's region layout and R-002 adjacency but is our own original, good-looking schematic art (no published art copied); it should look appealing from the first version. No new rule behaviour, so `implementer` writes the tests.
- [x] 1. Scenario-backed sessions: `scenario` on create, replay over start state, export/import carries it, 422 on invalid → `server/`, `kingisdead/scenario.py`, tests, `schema.d.ts`
- [x] 2. Board geometry and static SVG: attractive original map, region states, region-card track and discs; follower type shown in Assemble (report 20261031T232540) → `web/src/games/king-is-dead/board/`
- [x] 3. Courts, hands, supply, negotiation discs; card positions clear (report 20261031T232657) → `web/src/games/king-is-dead/`
- [x] 4. Click-to-act on the board, action list as fallback → `web/src/games/king-is-dead/`, shell hooks
- [x] 5. Forced-single-action auto-advance (R-106 empty-hand PASS), stale-poll fix, R-403 rank wording → `web/src/shell/useGame.ts`, board
- [x] 6. Scoring breakdown panel, chance labels in the log (adapter hook), history panel polish → `server/adapters/kingisdead.py`, `web/`
- [x] 7. Setup editor model and live V1–V11 validation → `web/src/editor/`
- [x] 8. Setup editor UI (mirror a physical table, `setup` and `state` kinds, import/export, start playing) → `web/src/editor/`, `Lobby.tsx`
- [x] 9. Playwright: click-through game vs random bot and an editor-built setup; `CLAUDE.md` web notes → `web/e2e/`, `CLAUDE.md`

**Phase 5 — Bots ✋ playtest #3**
- MCTS and heuristic seats; `tools/tournament.py` for bot-vs-bot win rates.
- *Exit:* MCTS clearly beats random over a few hundred 2-player games; you play against MCTS and heuristic.

Tasks (approved 2026-10-31; branch `phase-5/bots`):
- [x] 1. Heuristic bot: greedy one-turn lookahead, court strength vs projected region control → `kingisdead/bots/heuristic.py`, `tests/bots/`
- [x] 2. MCTS bot (OpenSpiel `MCTSBot`, thin wrapper) + parameterised seat types `mcts:N`, `heuristic`; schema validation → `kingisdead/bots/mcts.py`, `server/bots.py`, `server/schemas.py`
- [ ] 3. Bot moves off the session lock (D28): background task, stale-move invalidation on Back/Rewind/human action → `server/sessions.py`, `server/app.py`
- [ ] 4. `tools/tournament.py` (seat rotation, win rate with Wilson CI, JSON output, seeded) → `tools/`
- [ ] 5. Lobby/UI: heuristic and MCTS strength presets, named thinking indicator, regenerate API schema → `web/src/shell/`
- [ ] 6. Strength validation (slow test + recorded tournament, MCTS vs random and vs heuristic) → `tests/bots/test_strength_slow.py`, `docs/phase-reports/`
- [ ] 7. Playwright vs heuristic and `mcts:20`; `CLAUDE.md` bot notes; tick §5.8 → `web/e2e/`, `CLAUDE.md`
- Note: if MCTS is too slow or weak, swap the rollout evaluator (e.g. heuristic rollouts) rather than rewriting the search.

**Phase 6 — 4-player teams** *(starts with a mini-interview: team returns, partner display)*
**Phase 7 — Advanced game** *(mini-interview: Spy copying Negotiate/Manoeuvre, Plot reveal UX, hidden-hand hotseat handoff)*
**Phase 8 — Trained policies** *(mini-interview: algorithm choice, compute budget, evaluation)*

## 8. Working agreement for agent sessions

### Who does what (D14)

| Role | Agent | Model | Used for |
|---|---|---|---|
| Orchestrator | main session | Sonnet (project default) | Runs the skills, delegates, talks to you. Doesn't write large changes itself |
| Workhorse | `implementer` | Sonnet | One task-list unit: engine, server, web, tools, review fixes |
| Workhorse | `spec-test-writer` | Sonnet | Tests from the spec before code; regression tests for playtest reports |
| Cheap | `Explore` (overrides the built-in) | Haiku | Codebase search without filling the main context |
| Cheap | `sim-runner` | Haiku | Full suite, slow sims, tool scripts; returns a short summary |
| QA | `rules-auditor` | Opus, high effort, project memory | Spec vs rulebook (Phase 1); code and tests vs spec (spot checks, phase close) |
| QA | `code-reviewer` | Opus, high effort | Correctness review of the phase diff before it merges |

Opus runs at phase close and as spot audits only on units touching scoring, power struggles or the undo block, never on routine units. For a high-stakes planning conversation, such as drafting the spec, you can switch the main session with `/model opus`.

### The loop

1. **`/start-phase N`** — branch `phase-N/<slug>`, break the phase into agent-sized units (one rule group or component, ≲300 changed lines), you approve the list.
2. **`/next-task`** per unit — `spec-test-writer` writes pending tests from the spec → `implementer` makes them pass → `sim-runner` runs the suite → `rules-auditor` spot check (scoring, struggles, undo block only) → commit, tick the box.
3. **`/close-phase`** — full run including slow sims, `rules-auditor` + `code-reviewer` in parallel, one fix round (only blocker or must-fix findings block the merge; the rest go to the §9 Backlog), `docs/phase-reports/phase-N.md`, PR to `master`. ✋ phases stop for you; you merge.
4. **`/triage-report <file>`** — for each playtest report: reproduce, classify (engine bug / spec gap / UI bug / not a bug), regression test, fix or ask you.

### Rules for every session

- No rule behaviour without a spec entry. If an ambiguity turns up, stop, add it to §9, and ask — don't guess.
- Tests cite rule IDs; the spec, tests and code must agree before a phase closes. Nobody edits a test to make it pass.
- Commit at each green step on the phase branch; `master` only changes by PR. Direct and force pushes to `master` are denied in settings.
- Keep this file current: tick the progress list and task boxes, append decisions to §3 with a date.
- `CLAUDE.md` holds the exact commands so any session can start cold; keep it short (path-specific detail goes in `.claude/rules/`).

### What's enforced mechanically

| Guard | Mechanism |
|---|---|
| Don't finish with failing lint/tests | `check.py` on Stop (main session) and SubagentStop (`implementer`, `spec-test-writer`) |
| Don't change an approved spec | `protect_spec.py` on PreToolUse (Edit/Write/Bash) |
| Tests stay independent of the code | `block_engine_reads.py` in `spec-test-writer`'s frontmatter |
| Consistent formatting | `format_py.py` runs `ruff format` after each Python edit |
| No force pushes or direct pushes to `master` | `permissions.deny` in `.claude/settings.json` |

## 9. Open questions (deferred)

- Phase 6: team returns and tiebreak presentation for partners.
- Phase 7: Spy copying Negotiate when your disc is already used; Spy and the undo block; Plot interaction with draws (D9).
- Phase 8: algorithm (AlphaZero vs PPO-style), training budget, whether a C++ port is needed for speed.

### Backlog
Should-fix and minor findings, tagged with the phase that found them. `/close-phase` appends here.

- Phase 0: `spec-test-writer` can still see engine source via `git diff`, `git log -p`, `git show <rev>`, `king*` globs and `inspect.getsource` (low risk with a cooperative agent).
- Phase 0: `git merge/pull/rebase` aren't in the spec-revert list (the Stop-time backstop catches the result).
- Phase 0: Bash blocks standalone `kingisdead` tokens such as `-k kingisdead` (false positive).
- Phase 0: the spec backstop trips if the user sets APPROVED while spec edits are still uncommitted; commit spec edits before approving.
- Phase 0: GitHub branch protection on `master` needs GitHub Pro on a private repo (user's call).
- Phase 1: the `protect_spec.py` hook also fires on Bash commands that only mention the spec's filename (false positive; use Edit/Write for other files).
- Phase 2 (code-reviewer): `State.__str__` (`game.py:463-468`) omits hands, phase, pending card, sub-state, `reference_board`, `recent_win` etc., so distinct states print alike (PLAY(Manoeuvre) vs PHASE_SWAP). Fix by delegating to the observer's `string_from`; regenerates the goldens, so say why in the commit message.
- Phase 2 (code-reviewer): scenario-loaded states have empty history, so `serialize()`/`deserialize_state()` returns the initial node (`scenario.py:156-169`). Refuse to serialize or carry the scenario JSON.
- Phase 2 (code-reviewer, optional): legal actions recomputed 2-3 times per action (`game.py:243,253,264`); `swap_mode` (`rules.py:158-165`) builds the full candidate list to test emptiness; `tests/rules/test_observer.py:309-310` turns a rejected scenario into `pytest.skip` (make it a failure).
- Phase 2 (rules-auditor, unit 13): the unit 7/8/9 audit items are closed (fixed in c1f2055, or equivalent mutants); no new rule gaps. Mutants `no_void` and `persist_noswap` are equivalent.
- Phase 3 (unit 9): the KID view exposes every player's hand and the text board shows them all. Fine for hotseat; for networked play or Phase 7 hidden hands, filter the view per seat server-side (user: leave visible for now).
- Phase 3 (unit 8): chance outcomes in the action log are labelled "Chance outcome N" because the adapter has no chance labels; add an adapter hook if the log needs better wording.
- Phase 3 (unit 6): `web/package.json` pins `rollup@4.67.2` (the 4.67.3 tarball 404'd) and Vite 5/Vitest 2 for Node 18; drop the pins after moving to Node 20.
- Phase 3 (code-reviewer, should-fix): stale poll response can overwrite newer state (`useGame.ts:46-62`; use a mutation counter); polling stops after two identical errors (`useGame.ts:130-133`; re-arm on a poll tick); CI doesn't check `schema.d.ts` is current (add `npm run gen:api && git diff --exit-code src/api/schema.d.ts` to the web job); sessions and report notes are unbounded in memory and on disk (add `max_length`, cap or expire sessions) before the server is reachable from other machines.
- Phase 3 (code-reviewer, minor): `num_players` needs `Field(ge=2, le=3)` (huge values give a 500); seeds need `ge=0, lt=2**53` (browser precision); a bot failure after the human action is reported as a 409 illegal move; `KID_DEV=0` still enables dev mode; malformed `%` in the URL hash throws in `App.tsx:8`; the import file input is never cleared after a failed import.
- Phase 3 (rules-auditor, should-fix): R-106, a human with an empty hand must click PASS (the spec says UI and bots submit it automatically); fold into Phase 4's forced-single-action auto-advance. The scoring-breakdown test only compares `winners` with itself (`tests/server/test_adapter.py:72-81`): add last-step-equals-winners over seeded games plus built terminal states for rank-2-undefined and nobody-emptied-hand.
- Phase 3 (rules-auditor, minor): `_narrow` in the adapter copies private `rules._best_record` (can drift); the board prints "Scots > none > none" when ranks 2-3 are undefined (R-403), better wording needed.
- Phase 3 (code-reviewer, should-fix): `tests/server/test_concurrency.py` takes about 8 s in the fast suite; trim the replay loop or mark it slow and keep a short smoke version. Phase 5: a slow bot runs inside the session lock and stalls polling; if `advance_bots` moves to a background task it must take `s.lock`.
- Phase 4 (code-reviewer, should-fix): the region chooser in `Board.tsx` stays open across turns and can reappear unasked (reset `choosing` when history length or legal actions change); "Check with server" leaves a throwaway session each click and `serverValidate.ts:20-28` reads `game_id` instead of `id` (add a validate-only endpoint); the "Auto-played" note never clears (`useGame.ts:173`); `hoverAction` can stick after a click (reset on history change in `GameScreen.tsx`); editor stepper `aria-label` hides the number (`Editor.tsx:66`).
- Phase 4 (code-reviewer, minor): auto-advance "already tried" key skips a forced PASS reached again at the same history length after Back; editor file input not reset after import; `1e400` in a number field becomes `Infinity`/`null`; `download()` anchor not attached to the DOM.
- Phase 4 (rules-auditor, should-fix): the editor numbers players from 1 but the board, log and spec number from 0 (use one numbering before playtest #2); editor "Last play" and "Hand empty" tooltips should say card-play number per R-401 (not history index); map still shows "Struggle k+1 of 8" and NEXT badge after an early invasion end (gate on `is_terminal`, R-400); `useGame.test.tsx` uses its own predicate, not the shipped `kingIsDeadPlugin.autoAdvance`; D12 and SCENARIOS §2 still describe the chance-sequence conversion (needs user sign-off to amend).
- Phase 4 (rules-auditor, minor): Assemble banner says "followers" plural (should be "follower", R-212); Courts hint in the editor cites V11 for `state` scenarios; reference board (B*) of the last card is toggle-only in the editor; track cards move by buttons, not drag; Phase 3 backlog items fixed in Phase 4 (chance labels, stale poll and re-arm, R-106 PASS, scoring-breakdown tests, R-403 wording) can be struck; `state.serialize()` of scenario-loaded states still returns the initial state (sessions carry the scenario instead); history log can't group by phase (entries carry no phase).

## 10. Risks

| Risk | Mitigation |
|---|---|
| OpenSpiel 2.0 Python game API differs from 1.x examples online | Phase 0 spike before any engine code |
| Rule misreads | Spec review ✋, rule-ID tests, independent audit, playtests |
| Python too slow for heavy MCTS/RL | Fine for interactive play; revisit a C++ port in Phase 8 only if needed |
| Sub-decision encoding bloats search trees | Canonical orderings (§5.3); forced single-action nodes auto-advance in UI |
| Copyright of rulebook and board art | Rulebook kept local and git-ignored; UI uses an original schematic map |
