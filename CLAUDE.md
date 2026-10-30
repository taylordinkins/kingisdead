# The King is Dead — OpenSpiel

Python OpenSpiel game (`kingisdead/`), later a FastAPI server (`server/`) and React/TS web UI (`web/`).
Plan and phases: `PLAN.md` (read only the current phase). Rules contract: `docs/RULES_SPEC.md`.
Default branch is `master`; work happens on `phase-N/<slug>` branches merged by PR.

## Commands
- Install: `uv sync`
- Fast tests: `uv run pytest -q` · one rule: `uv run pytest -q -k R012` · slow sims: `uv run pytest -q -m slow`
- Lint/format/types: `uv run ruff check .` · `uv run ruff format .` · `uv run pyright`

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
- Tests written ahead of code carry `@pytest.mark.pending("R-012")`; remove the marker when the rule lands.
- Never edit a test to make it pass, and never regenerate `tests/playthroughs/` golden files without
  saying why in the commit message.
- Action IDs are frozen once Phase 2 closes: replays and playtest reports depend on them.
- A Stop hook runs lint + fast tests when Python files changed; don't end a turn red.
- The rulebook PDF lives in `docs/rules/` and is git-ignored. Never commit it or copy board art.
- Commit at each green step with a message that names the rule IDs or task it covers.
