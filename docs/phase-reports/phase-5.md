# Phase 5 report: Bots (MCTS, heuristic)

Closed 2026-11-01 on branch `phase-5/bots`. Units 1-7 of the task list are ticked in PLAN.md. This is a ✋ phase: the exit criterion is your playtest #3 (below). Bot strength numbers are in `phase-5-bot-strength.md`.

## Exit criteria and evidence

| Criterion | Evidence |
|---|---|
| Heuristic and MCTS seats (`heuristic`, `mcts:N`), validated seat types | `kingisdead/bots/`, `server/bots.py`; lobby presets in `web/src/shell/seatTypes.ts` |
| Bot moves off the session lock (D28), stale-move discard, `bot_error` + Retry | `server/sessions.py` background worker, `POST /bots/retry`; code-reviewer verified every history mutation bumps `version` and that Back/Rewind during a search are discarded |
| `tools/tournament.py` (seeded, seat rotation, Wilson CI, JSON) | `uv run python -m tools.tournament ...`; results in `docs/phase-reports/data/` |
| MCTS clearly beats random over a few hundred 2-player games | mcts:100 vs random 0.970 over 300 games, 95% CI [0.944, 0.984]; mcts:100 vs heuristic 0.790 over 100 games, CI [0.700, 0.858]; heuristic vs random 0.758 over 1000 games |
| Fast and slow suites, lint, types | `pytest -q` 881 passed, 2 xfailed (the marker self-tests), 0 xpassed; `pytest -m slow` 191 passed (328 s); ruff, ruff format, pyright clean. After the fix round: `pytest -q` 881 passed, `npm test` 125 passed (16 files), `tsc --noEmit` and `npm run build` clean |
| Playwright vs heuristic and `mcts:20` | `web/e2e/bots.spec.ts` added in unit 7. `npm run e2e`: 9 passed (run by you after the swap and tooltip fixes; not re-run by me after the final held-pick fix) |
| Engine untouched | `git diff master...HEAD -- kingisdead/ docs/RULES_SPEC.md` shows only the new `kingisdead/bots/` files; `actions.py`, `rules.py`, `game.py` and the spec are unchanged, so action IDs are still frozen |

**Still open (yours): playtest #3.** Play against `heuristic` and `mcts:100` (and optionally `mcts:400`); file reports with the in-app Report dialog.

## Playtest #3 reports so far (all triaged)

- `20261101T180522-891ed6` (R-214): UI bug. Manoeuvre's second pick only offered higher-numbered regions because the UI did not sort clicks into the engine's canonical order, as `docs/ACTIONS.md` requires. Fixed (commit 680602f).
- `20261101T181007-48abf3` (R-213): same cause for Negotiate. Fixed (d9678c6).
- Found while triaging: Outmanoeuvre 1-for-2 had the same problem on the pair's faction order. Fixed (7fe0689).
- `20261101T174750-ff097f`: enhancement request, card effect tooltips plus a touch-friendly card guide (b8e5d5b). Texts reviewed against R-201 and R-210..R-215 by the rules-auditor.

## Review verdicts

- **Rules audit** (`rules-auditor`): PASS. No rule behaviour or action ID changed; bots pick only legal actions, never mutate engine state and use no hidden information (probe over 458 decisions: no state change, all moves legal). An independent oracle written from the spec checked every `swap_pairs` first pick and pair in either click order over about 6,000 decisions (including R-216 blocks, 46 cases forcing 1-for-1): 0 mismatches. One should-fix (the held-pick bug below), minor wording gaps in the tooltips, doc drift and weak coverage of missing pairs in tests.
- **Code review** (`code-reviewer`, `git diff master...HEAD`): CHANGES NEEDED, 1 must-fix, 2 should-fix, 4 minor. The stale-move discard, bot RNG determinism, frozen action IDs and `swap_pairs` server logic were found sound.

## Findings fixed (one round)

- Must-fix: the client-side held first pick of a swap survived position changes (Back, finishing via the action list, hot-seat hand-over), so a later click could submit a stale pair. The held pick is now derived from a position key (history length, player, phase, pick count) and cannot be stale in any render; regression tests added (8f71bcc).
- The `swap_pairs` doc comments were corrected (8f71bcc).

Re-check by the same reviewer (CHANGES NEEDED, one should-fix): the must-fix is resolved for position changes that produce a new key, and the two-action submit flows are unaffected. One residual: a stale pick is hidden but not deleted, so it returns if the identical position key recurs (for example hold a pick, press Back, replay the same card). Fixed afterwards: the stale pick is now dropped the first time a render sees a different key, with a regression test that fails without the fix (web tests 126 passed).

## Findings deferred (PLAN.md §9 Backlog)

- Should-fix: a bot exception racing Back/Rewind/retry can leave a stale `bot_error` and no worker; `mcts:N` has no upper bound and a stale search cannot be cancelled.
- Minor: seat regex accepts a trailing newline in Python; `actors` and `history` can desync if the engine raises; Retry bypasses `useGame.run` and restarts a healthy worker; inline-mode 500; tooltip wording gaps; weak missing-pair coverage in `test_swap_pairs.py`; `tools/replay.py` referenced by the triage skill does not exist; no Playwright test for higher-first swap clicks.

## Decisions

- D31: the engine keeps one canonical action sequence per swap; the server exposes `swap_pairs` and the UI accepts the two clicks in either order. Card tooltips paraphrase the spec. No rule behaviour changed.
