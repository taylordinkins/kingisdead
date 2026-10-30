# The King is Dead — OpenSpiel Implementation Plan

**Status:** Draft v2 · 2026-10-30
**Repository:** `taylordinkins/kingisdead` (default branch `master`)
**Rules source:** *The King is Dead*, Second Edition rulebook (Peer Sylvester, Osprey Games 2020)
**Target framework:** OpenSpiel `open-spiel==2.0.2` (Python ≥ 3.11; wheels for macOS arm64, Linux, Windows)

### Progress
- [x] Phase 0 — Scaffold & OpenSpiel API spike (closed 2026-10-30, see docs/phase-reports/phase-0.md)
- [ ] Phase 1 — Rules spec ✋ *you review*
- [ ] Phase 2 — Engine (2–3 players, base game)
- [ ] Phase 3 — Server + web shell ✋ *playtest #1*
- [ ] Phase 4 — Board UI + setup editor ✋ *playtest #2*
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
| D12 | Setup | Random setup via chance nodes **plus** a manual setup editor | Editor emits the equivalent chance-outcome sequence, so there's one code path |
| D13 | Adjacency | Table in §4 C1, confirmed against the physical board | |
| D14 | Model use (2026-10-30) | Sonnet does routine implementation and test writing; Haiku does search and long test/sim runs; Opus is reserved for rules audits and code review | Main session defaults to Sonnet (`.claude/settings.json`) and orchestrates rather than writing large changes. See §8 |
| D15 | Spec lock (2026-10-30) | `docs/RULES_SPEC.md` Status line DRAFT → APPROVED → AMENDING; a hook blocks edits while APPROVED | Only the user changes the Status line |
| D16 | Tests ahead of code (2026-10-30) | Spec tests carry `@pytest.mark.pending("R-0xx")` and run as non-strict xfail until the implementer removes the marker | Keeps the suite green so the stop gate can be strict |
| D17 | Test independence (2026-10-30) | `spec-test-writer` can't read `kingisdead/` source (hook-enforced); it writes against the spec and `tests/harness.py` | Disagreements between tests and code surface bugs or spec ambiguities |
| D18 | Persistence (2026-10-30) | Persist action histories, never `serialize()` strings; never deserialize client input | Deserialization unpickles `__dict__` without replaying history (docs/OPENSPIEL_NOTES.md) |
| D19 | Type stub (2026-10-30) | pyspiel type stub in `typings/` keeps pyright strict on engine code | Only signatures confirmed against the installed 2.0.2; extend as needed |

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
- The block lasts until any player plays a card. Passes don't lift it; the original player's summon doesn't lift it. ⚑ Power struggles also don't lift it (literal reading: only *actions* count).

**C3 — Winner determination and fallbacks**
- *Coronation ranking:* sort factions by (regions controlled ↓, index of most recent power struggle won ↓). A faction that never won has index −1. Two factions can only tie here if both have 0 regions; that rank is then **undefined**.
- *Coronation winner:* (1) most followers of rank-1 faction; (2) among tied, most of rank-2 faction — **skipped if rank 2 is undefined**; (3) among still tied, the earliest player to have emptied their hand wins (any player who emptied beats any who didn't); (4) if none of the still-tied players emptied their hand → shared win (D9).
- *Invasion winner:* most complete sets (min of a player's three faction counts); among tied, the player who most recently played an action card; if none of the tied players ever played one → shared win.

**C4 — Turns and passing**
- Turn order is increasing player index (= clockwise). ⚑ Player 0 starts; the UI lets you choose who sits in seat 0 ("most recently visited a castle").
- A power struggle triggers when the consecutive-pass count reaches the number of players. It resolves automatically (no decision), the count resets, and play continues with the next player in rotation.
- ⚑ A player with no cards left has exactly one legal action, PASS. The UI and bots auto-submit it.
- The game ends **immediately** when the third instability disc is placed (invasion), otherwise after the 8th power struggle (coronation).

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
                        └─PLAY_CARD──► card sub-steps (0–4 decisions) ──► SUMMON (0–1) ──► TURN_START / TERMINAL
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
- **Setup editor:** set court contents, region contents and region-card order; validated against bag counts; emits the equivalent chance sequence.

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
- [ ] 1. Components, setup and turn flow (regions, C1, factions, counts, setup, turn order, PASS, C4) → `docs/RULES_SPEC.md`
- [ ] 2. Six action cards plus summon (C7, C10, C9, C2, C8, C6) → `docs/RULES_SPEC.md`
- [ ] 3. Power struggle, end of game, scoring (C5, C3, D8, D9) → `docs/RULES_SPEC.md`
- [ ] 4. Action catalogue: IDs, phase machine, canonical ordering, masks → `docs/ACTIONS.md`
- [ ] 5. Scenario JSON format plus 2–3 examples → `docs/ACTIONS.md` or `docs/SCENARIOS.md`, `tests/scenarios/*.json`
- [ ] 6. Independent audit vs rulebook (`rules-auditor`)
- [ ] 7. Fix round, Phase 1 report, ✋ user review and approval

**Phase 2 — Engine (2–3 players, base game)**
- `constants`, `rules`, `actions`, `game`, `observer`; tests first per rule ID; invariant checker; `tools/play_text.py` for agent self-play debugging; golden playthroughs for 3 seeds; card-by-card independent review.
- *Exit:* all rule tests green; `random_sim_test` passes; 10,000 random games with zero invariant violations; `sim_stats` report (end-type mix, game length) recorded.

**Phase 3 — Server + web shell ✋ playtest #1**
- FastAPI + adapter; React shell with legal-action list and a text board; human and random seats; Report and replay export; Playwright smoke test that finishes a game against the random bot.
- *Exit:* you play at least one hotseat game and one game against random, and file reports.

**Phase 4 — Board UI + setup editor ✋ playtest #2**
- SVG board with click-to-act, region-card track, courts, history, Back/Rewind, scoring breakdown, setup editor.
- *Exit:* you mirror at least one physical-table setup in the editor and play it through.

**Phase 5 — Bots ✋ playtest #3**
- MCTS and heuristic seats; `tools/tournament.py` for bot-vs-bot win rates.
- *Exit:* MCTS clearly beats random over a few hundred 2-player games; you play against MCTS and heuristic.

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

## 10. Risks

| Risk | Mitigation |
|---|---|
| OpenSpiel 2.0 Python game API differs from 1.x examples online | Phase 0 spike before any engine code |
| Rule misreads | Spec review ✋, rule-ID tests, independent audit, playtests |
| Python too slow for heavy MCTS/RL | Fine for interactive play; revisit a C++ port in Phase 8 only if needed |
| Sub-decision encoding bloats search trees | Canonical orderings (§5.3); forced single-action nodes auto-advance in UI |
| Copyright of rulebook and board art | Rulebook kept local and git-ignored; UI uses an original schematic map |
