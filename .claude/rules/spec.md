---
paths:
  - "docs/RULES_SPEC.md"
  - "docs/ACTIONS.md"
---

# Rules spec conventions

- One rule per heading: `### R-012 — <short title>`. IDs are permanent; retire a rule rather than
  renumber it.
- Each rule states its source: a rulebook page/section, or a PLAN.md §4 clarification (C1–C10) or
  decision (D-number). Paraphrase the rulebook; don't paste it.
- Write rules as testable statements with at least one concrete example (board fragment → result).
- Anything the rulebook doesn't settle goes to PLAN.md §9 as a question for the user, not into the
  spec as a guess.
- The Status line at the top is DRAFT, APPROVED or AMENDING. Only the user changes it. While it is
  APPROVED, a hook blocks edits to this file.
