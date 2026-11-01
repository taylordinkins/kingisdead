# The King is Dead — OpenSpiel

Python OpenSpiel game (`kingisdead/`), later a FastAPI server (`server/`) and React/TS web UI (`web/`).
Plan and phases: `PLAN.md` (read only the current phase). Rules contract: `docs/RULES_SPEC.md`.
Default branch is `master`; work happens on `phase-N/<slug>` branches merged by PR.

## Commands
- Install: `uv sync`
- Fast tests: `uv run pytest -q` · one rule: `uv run pytest -q -k R012` · slow sims: `uv run pytest -q -m slow`
- Lint/format/types: `uv run ruff check .` · `uv run ruff format .` · `uv run pyright`
- Web (Node 20 required; run from `web/`; the Windows npm on the WSL PATH breaks things, use `source ~/.nvm/nvm.sh && nvm use 20`): install `npm ci` · typecheck `npx tsc --noEmit` · unit `npm test` · build `npm run build` · smoke `npm run e2e` (Playwright; starts the API and Vite itself; first time `npx playwright install --with-deps chromium`)
- API schema: after changing server models run `uv run python -m tools.export_openapi` then `npm run gen:api` (in `web/`); `--check` verifies it is current

## Model and agent policy
The main session orchestrates; it delegates rather than writing large changes itself.
- Workhorse (Sonnet): `implementer` writes code, `spec-test-writer` writes tests from the spec.
- Cheap (Haiku): `Explore` for searching, `sim-runner` for long test/sim runs and their output.
- QA (Opus): `rules-auditor` checks spec conformance, `code-reviewer` checks for bugs. Use them at
  task or phase close, not for routine work.
- Workflow skills: `/start-phase N`, `/next-task`, `/close-phase`, `/triage-report <file>`.

## Rules
- IMPORTANT: no rule behaviour without a `docs/RULES_SPEC.md` entry. Ambiguity → stop, add it to
  PLAN.md §9, ask the user. Never resolve a rules question by guessing.
- Once the spec's Status is APPROVED it is locked (a hook enforces this). Propose amendments to the user.
- Tests written ahead of code carry `@pytest.mark.pending("R-012")` (rules) or `@pytest.mark.regression("<report id>")` (playtest bugs, strict xfail); remove the marker when the rule or fix lands.
- Never edit a test to make it pass, and never regenerate `tests/playthroughs/` golden files without
  saying why in the commit message.
- Action IDs are frozen once Phase 2 closes: replays and playtest reports depend on them.
- A Stop hook runs lint + fast tests when Python files changed; don't end a turn red.
- The rulebook PDF lives in `docs/rules/` and is git-ignored. Never commit it or copy board art.
- Commit at each green step with a message that names the rule IDs or task it covers.

## Web notes
- Layout: board in `web/src/games/king-is-dead/` (`Board.tsx` chooser popover, `board/MapBoard.tsx` SVG map, `board/Players.tsx` hand cards, `ScoringPanel.tsx`); setup editor in `web/src/editor/` (route `#/editor`); shell/hooks in `web/src/shell/` (`useGame.ts`, `GameScreen.tsx`, `Lobby.tsx`); plugin in `plugin.ts`, registered via `web/src/games/registry`.
- Click-to-act: `GameScreen` passes `{canAct, onAct, hoverAction}` to `plugin.renderBoard`; the board maps clicks on regions/hand cards to legal action ids (several actions in one region open the chooser popover). The action list always remains as a fallback.
- `plugin.autoAdvance(action, legal)` decides which single legal actions are auto-played; King is Dead only auto-plays the forced PASS (R-106).
- Editor examples: drop a scenario JSON in `web/src/editor/examples/` and add it to `EXAMPLES` in `examples.ts` (copied from `tests/scenarios`).
- Gotcha: `editor/serverValidate.ts` ("Check with server") creates a throwaway game session on the API; do not call it per keystroke. Live V1-V11 validation is client-side (`validate.ts`).
- E2E (`web/e2e/`): `smoke.spec.ts` plays via the action list; `board.spec.ts` clicks the board (`.kid-region[role=button]`, hand chips, `region-chooser`) with a seed, checks Back, and plays to the scoring panel; it also covers editor example/import and Start playing.

## Bot notes
- Seat types: `human`, `random`, `heuristic`, `mcts:N`. Validated by pattern in `server/bots.py`; implementations/registry in `kingisdead/bots/`. Lobby presets: `web/src/shell/seatTypes.ts`.
- Bot moves are computed in a background worker off the session lock (`server/sessions.py`); a result is discarded if the session version changed (stale-move discard).
- Failures set `bot_error` on the game; the UI shows a Retry button that calls `POST /bots/retry`.
- Tournament: `uv run python -m tools.tournament --seats heuristic random --games 100 --seed 0 [--workers N --json out.json]`. Strength report: `docs/phase-reports/phase-5-bot-strength.md`.
- Gotcha: MCTS moves take about 0.4 s at N=100 (more at 400), so the UI shows "<Name> (P#) is thinking…"; heuristic is near-instant. E2E: `web/e2e/bots.spec.ts` (heuristic, `mcts:20`).
