---
name: close-phase
description: Close the current phase - full test and simulation run, Opus rules audit and code review, fix loop, PLAN.md update, evidence report and pull request. Run when every unit of the phase is done.
disable-model-invocation: true
---

Close the current phase. The goal is evidence the user can check in a few minutes.

1. **Completeness:** every unit in the phase's PLAN.md task list is ticked, and no
   `pytest.mark.pending` marker remains for a rule ID this phase claims (`grep -rn "pending(" tests/`).
2. **Full run** via `sim-runner`: `uv run ruff check .`, `uv run ruff format --check .`,
   `uv run pyright`, `uv run pytest -q -rxX`, `uv run pytest -q -m slow -rxX`, plus any phase-specific
   exit-criteria commands from PLAN.md §7 (e.g. 10,000-game invariant sims, `tools/sim_stats.py`).
3. **Reviews, in parallel:** `rules-auditor` (scope: every rule ID touched this phase; for Phase 1,
   the whole spec against the rulebook) and `code-reviewer` (scope: `git diff master...HEAD`).
4. **Fix loop:** one round only. Send blocker and must-fix findings to `implementer`, then re-run
   step 2 and re-check only the affected findings with the same reviewer. Only blocker or must-fix
   findings block the merge; anything still open of that severity goes to the user. Should-fix and
   minor findings are appended to the "Backlog" list in PLAN.md §9 with the phase number, not fixed
   now. Any finding that is really a question about what a rule means still goes to the user.
5. **Record:** write `docs/phase-reports/phase-N.md` with the exit criteria and the evidence for each
   (commands run and their headline numbers), review verdicts, findings fixed, findings deferred,
   and new decisions. Tick the phase in PLAN.md's progress list and append decisions to §3 with
   today's date.
6. **Ship:** commit, push the branch, open a PR to `master` whose description links the phase report.
7. If the phase has a ✋ checkpoint, stop here and tell the user exactly what to review or playtest.
   Don't merge; the user merges.
