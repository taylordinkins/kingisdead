---
name: start-phase
description: Start a phase from PLAN.md - create its branch and a task list of agent-sized units for the user to approve. Run at the beginning of every phase.
disable-model-invocation: true
argument-hint: "[phase-number]"
---

Start Phase $ARGUMENTS of PLAN.md.

1. Read PLAN.md §7 for Phase $ARGUMENTS (deliverables, exit criteria, ✋ checkpoint) and §8. Read
   only what the phase needs; use the `Explore` agent for any codebase questions.
2. Check prerequisites: earlier phases ticked in PLAN.md's progress list, working tree clean, on
   `master` and up to date (`git fetch origin master`). If the phase is 6, 7 or 8, PLAN.md says it
   starts with a mini-interview: run that interview with AskUserQuestion before planning.
3. Create the branch `phase-$ARGUMENTS/<short-slug>`.
4. Break the phase into units that one `implementer` run can finish: one rule group or one
   component, roughly 300 changed lines or less, each with a clear done-condition. For engine work,
   pair every unit with its rule IDs; the `spec-test-writer` runs before the `implementer`.
5. Present the units as a numbered task list (also create them with TaskCreate) with, for each:
   rule IDs or component, files in scope, done-condition, and which agent runs it.
6. Stop and wait for the user to approve or edit the list. Don't start the first unit until they do.

Once approved, record the list under the phase in PLAN.md as checkboxes, commit, and tell the user to
run `/next-task` (or ask you to continue) to work through it.
