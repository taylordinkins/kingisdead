---
name: next-task
description: Run the next unchecked unit of the current phase through the delegation loop - tests from the spec, implementation, checks, commit. Use to work through an approved phase task list.
argument-hint: "[optional unit number]"
---

Run the next unit of the current phase (or unit $ARGUMENTS if given). You orchestrate; the agents
write the code. Keep your own context small: delegate reading and long commands.

1. Find the unit: the first unchecked box under the current phase in PLAN.md (or the one named).
2. **Tests first (engine units):** delegate to `spec-test-writer` with the rule IDs, the scenario
   files to reuse, and the done-condition. If it reports spec ambiguities, stop and bring them to
   the user with AskUserQuestion before any code is written.
3. **Implement:** delegate to `implementer` with the unit, its rule IDs, files in scope, and the
   tests just written. Give it everything it needs in the message; it starts with no context.
4. **Check:** delegate the full fast suite to `sim-runner` (`uv run pytest -q -rxX`, plus
   `uv run pyright`). If anything fails, send the failure summary back to `implementer` (resume it
   with SendMessage if it is still available). Two failed rounds → stop and report to the user.
5. **Spot-audit (only units that touch scoring, power struggles or the undo block):** delegate to `rules-auditor` scoped to that unit's rule IDs. Blockers go back
   to `implementer`; disagreements about what a rule means go to the user.
6. **Commit** on the phase branch: `<unit summary> (R-0xx, R-0yy)`. Tick the box in PLAN.md.
7. Report in three lines or fewer: what landed, test totals, anything the user needs to decide.

Don't run Opus reviewers on every unit; the full review happens in `/close-phase`.
