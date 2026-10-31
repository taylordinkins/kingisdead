# Phase 3 report: Server + web shell

Closed 2026-10-31 on branch `phase-3/server-web-shell`. Units 1–10 of the task list are ticked in PLAN.md. This is a ✋ phase: the exit criterion is your playtest (below).

## Exit criteria and evidence

| Criterion | Evidence |
|---|---|
| FastAPI + adapter | `server/` (adapter, sessions, endpoints, bots, reports); `uv run pytest -q -rxX`: 793 passed, 2 xfailed (the marker self-tests), 0 failed |
| React shell: legal-action list, text board, human and random seats | `web/src/shell/`, `web/src/games/king-is-dead/`; `npm test`: 29 passed |
| Report and replay export/import | `POST /api/games/{id}/report` writes `playtest/reports/<id>.json`; export/import in the shell; covered by server tests and Vitest |
| Playwright smoke test finishes a game vs the random bot | `npm run e2e`: 2 passed (full game, seed 1, about 2 s; Report dialog) |
| Engine untouched | `git diff master...HEAD` has no changes under `kingisdead/`, `docs/`, `tests/rules`, `tests/scenarios`, `tests/playthroughs` |
| Slow suite | `uv run pytest -q -m slow -rxX`: 188 passed (234 s), run before the lock fix; the fix touches only `server/` |
| Lint, format, types, schema | `ruff check`, `ruff format --check`, `pyright`, `tools.export_openapi --check`, `tsc --noEmit`, `vite build`: all clean |
| No stale pending markers | `grep -rn "pending(" tests/`: only docstring mentions |

**Still open (yours): playtest #1.** Play at least one hotseat game and one game against random, and file reports.

## Review verdicts

- **Rules audit** (`rules-auditor`): PASS. No blockers or must-fix. Scoring breakdown checked against an independent R-403 ranking over 800 random games (0 mismatches) plus hand-built R-404/R-405 edge cases; Back/Rewind rebuild state by replay, so the undo block (R-216/R-217) is respected.
- **Code review** (`code-reviewer`, `git diff master...HEAD`): CHANGES NEEDED, 0 blockers, 1 must-fix, 4 should-fix, 6 minor. The must-fix is fixed; the re-check says APPROVE (the new test fails 3/3 on the unfixed code and passes 3/3 with the lock; no deadlock risk found).

## Findings fixed

- Must-fix: sessions were mutated from several threadpool threads with no lock (a poll could race an action and 500, and two writes could both pass the legality check). Each session now has an `RLock` held from lookup through response; `tests/server/test_concurrency.py` fails without the lock and passes with it (3 extra runs, no flakiness).
- Follow-ups approved during the phase: typed top-level `GameView` fields, labelled `history` and `dev_mode` (D26); faction and card names sent from the server, regions-resolved line and the `recent_win` legend from R-303/R-403 (D27).

## Findings deferred (PLAN.md §9 Backlog)

Should-fix, none block the merge: stale poll responses, polling stopping after repeated identical errors, CI not checking `schema.d.ts`, unbounded sessions and report notes, human empty-hand PASS not auto-submitted (R-106), weak scoring-breakdown test, and the 8 s concurrency test sitting in the fast suite (trim or mark slow, keep a short smoke version). Plus minor items (input bounds, `KID_DEV=0`, hash decoding, import input reset, board wording for undefined ranks).

## Decisions

- D26: `GameView` has typed top-level fields; the game-specific `view` stays opaque.
- D27: faction and card names come from the server.
- D28: handlers stay sync with a per-session lock; Phase 5 slow bots must not run inside it.
- D29: web work needs Node 20; Vite 5/Vitest 2 and `rollup@4.67.2` pins stay until cleaned up; Playwright pinned to 1.64.1.

## What to playtest

1. Start the API: `uv run uvicorn server.app:app` (add `KID_DEV=1` to see Rewind), and the UI: `cd web && npm run dev` (Node 20), then open http://localhost:5173.
2. One hotseat game (both seats human) and one game against the random bot, to the end.
3. Use Back, the action log, and Export/Import once. File a Report for anything odd; reports land in `playtest/reports/`.
4. Check the text board for anything missing or confusing, especially the scoring breakdown at game end.
