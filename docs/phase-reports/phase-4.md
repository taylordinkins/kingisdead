# Phase 4 report: Board UI + setup editor

Closed 2026-10-31 on branch `phase-4/board-ui-setup-editor`. Units 1–9 of the task list are ticked in PLAN.md. This is a ✋ phase: the exit criterion is your playtest #2 (below).

## Exit criteria and evidence

| Criterion | Evidence |
|---|---|
| SVG board with click-to-act, region-card track, courts, hands, supply, discs | `web/src/games/king-is-dead/` (`board/MapBoard.tsx`, `board/Players.tsx`, `Board.tsx`); clicks on regions, track cards and hand cards submit actions, a faction chooser handles multi-faction regions, the action list stays as fallback |
| History, Back/Rewind, scoring breakdown | `ActionLog.tsx` (collapsed setup draws, seat badges), `ScoringPanel.tsx` (each R-402/R-404 step); `rules-auditor` unit 6 spot-audit PASS, 800 random games: last step equals winners |
| Scenario-backed sessions | create/import/export/report carry the scenario; Back/Rewind replay over its start state (unit 1) |
| Setup editor (`setup` and `state` kinds, live V1–V11, import/export, start playing) | `web/src/editor/`; the TS validator agrees with `kingisdead/scenario.py` on 1500 generated scenarios (same accept/reject and V-code) |
| Forced PASS auto-plays (R-106), stale-poll fix | `useGame.ts`; only a lone `pass` auto-plays |
| Playwright: full click-through game vs random bot and an editor-built setup | `npm run e2e`: 5 passed (re-run after the fix round) |
| Fast and slow suites, lint, types, schema | after the fix round: `pytest -q` 827 passed, 2 xfailed; `pytest -m slow` 188 passed (268 s); ruff, format, pyright, `export_openapi --check`, `tsc`, `npm run build` clean; `npm test` 106 passed |
| Engine untouched | no rule behaviour changed; the only `kingisdead/` change is type guards in `scenario.py` (below) |

**Still open (yours): playtest #2.** Mirror at least one physical-table setup in the editor (`#/editor`) and play it through; file reports with the in-app Report dialog.

## Review verdicts

- **Rules audit** (`rules-auditor`): FAIL on one must-fix, now fixed (the Turn panel showed a stale "Negotiation first region" during Manoeuvre/Outmanoeuvre because `neg_first` was sent in the swap phase). Everything else should-fix or minor. Verified: the TS V1–V11 port matches the Python loader on 1500 cases, setup scenarios loaded directly equal the SCENARIOS §2 chance sequence (40 random setups plus `setup_basic`), R-106 auto-advance is equivalent to an empty hand.
- **Code review** (`code-reviewer`, `git diff master...HEAD`): CHANGES NEEDED, 1 blocker, 1 must-fix, 5 should-fix, 4 minor.

## Findings fixed (one round)

- Blocker: the `#/editor` hash listener only ran once, so Lobby to editor and back did not navigate (`App.tsx`). Fixed, with an App test for the round trip.
- Must-fix: malformed scenario JSON (wrong types in `region_state`, hands, `reference_board`, `last_play`, `last_card.type`) gave HTTP 500; `scenario.py` now rejects with `ValueError` and `make()` returns 422 for `/games` and `/games/import`; tests cover each payload.
- Must-fix (audit): `neg_first` is only sent while PHASE_NEG_SECOND ≤ phase ≤ PHASE_NEG_DISC; adapter test added.
- Earlier in the phase: the audit findings of unit 6 (rank-2 test strength, "share the win" only on the last applied step, legal fixtures), and playtest #1 reports 20261031T232540 (follower type in Assemble) and 20261031T232657 (card positions).

## Findings deferred (PLAN.md §9 Backlog)

Should-fix and minor items from both reviewers, notably: editor numbers players from 1 while the board uses 0 (worth fixing before you mirror a table), the region chooser can reappear unasked, "Check with server" leaves a throwaway session per click, and the early-invasion map still shows a NEXT badge.

## Decisions

- D30: sessions carry the scenario JSON and replay over its start state; only a forced PASS auto-plays. Amending D12 and SCENARIOS §2 (setups load directly, not via chance sequence) needs your sign-off; the results were verified identical.
