---
name: triage-report
description: Triage a playtest report from playtest/reports/ - reproduce it, classify it, and drive the fix with a regression test. Use when the user files or mentions a playtest report.
disable-model-invocation: true
argument-hint: "[report file]"
---

Triage the playtest report `$ARGUMENTS` (a JSON file in `playtest/reports/`: engine version, game
params, seats, full action history, the user's note, and the state at report time).

1. Read the user's note and the final state. Rebuild the game from the action history with
   `uv run python tools/replay.py $ARGUMENTS` (via `sim-runner` if the output is long).
2. Classify, citing rule IDs:
   - **Engine bug:** the engine did something the spec forbids, or forbade something it allows.
   - **Spec gap:** the spec doesn't settle the situation, or the user's table reading differs from it.
   - **UI bug:** engine state is right but the UI showed or offered the wrong thing.
   - **Not a bug:** the rules work as the spec says; explain which rule and why.
3. Act on the class:
   - Engine bug: `spec-test-writer` adds a failing regression test in
     `tests/regressions/test_report_<id>.py` built from the report's history and marked
     `@pytest.mark.regression("<id>")` (strict xfail, so the gate stays green while it fails); then
     `implementer` fixes it and removes the marker once the test passes; then `sim-runner` runs the full suite.
   - Spec gap: stop. Present the situation and the candidate readings with AskUserQuestion. After
     the user decides, record it in PLAN.md (§3 or §4) and, if the spec is APPROVED, ask them to set
     it to AMENDING so the rule can be added.
   - UI bug: `implementer` fixes it with a test at the server or web layer.
4. Add a `"resolution"` field to the report (class, rule IDs, commit or decision) and tell the user
   the outcome in two or three lines.
