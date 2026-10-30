---
name: audit-patterns
description: Recurring defects found when auditing docs/RULES_SPEC.md against the TKID rulebook (examples, undo block, terminology)
metadata:
  type: project
---

Recurring patterns seen in spec audits (first seen 2026-10-30, Phase 1 unit 2, R-200..R-217):

- **Examples with local premises but global conclusions.** E.g. R-210 "Strathclyde borders no
  Scottish-controlled region → nothing eligible" ignores Scottish control elsewhere. Check every
  "nothing/only X is legal" example against the whole board, not just the named regions.
- **Examples that silently assume board state** (no board given; summon or a struggle between plays
  could remove the followers the example relies on). Ask for explicit fragments.
- **Undo block is pick-based (C2/R-216), not board-effect-based.** For a 1-for-2 Outmanoeuvre whose
  single faction also appears in its pair, a different-pick play can restore the exact prior board
  and is NOT blocked. Raised as an open question 2026-10-30; check whether the user has ruled on it
  before raising again. D20 (no-op Manoeuvre, 1-for-1 Outmanoeuvre reverse) is user-confirmed: do
  not relitigate.
- **Legality must be judged on complete swaps.** Mandatory-form rules (R-202/R-215) select the form
  from *legal* (unblocked) swaps; worth checking tests/code compute form after block filtering and
  that sub-decision masks never offer a first pick whose only completions are blocked.
- **Rulebook terminology trap:** p6 defines "controlled regions" as having a control OR instability
  disc; card text "region controlled by the Scots" means a faction disc only. Spec uses "closed".

- **Cross-refs that exist but point at the wrong rule.** An ID-existence grep finds no dangling
  refs, yet e.g. R-400 said outcome is "computed by R-401 or R-403" (R-401 is the records rule;
  should be R-402/R-404/R-405). Read each ref for meaning, not just existence (seen unit 3).
- **"Immediately"/"the moment" wording vs. step ordering.** Game-end phrasing can contradict the
  sequenced resolution (R-304 ends after followers return + flip) and an "every state" invariant
  (R-015). Check terminal-state timing words against the ordered steps.
- **Tiebreak arguments: right conclusion, wrong justification.** R-403's "≤2 tie, only at 0"
  follows from struggle numbers being distinct per winner, not from "≥6 controlled". Verify the
  reasoning, not just the claim. (Coronation/invasion tiebreak chains were otherwise sound.)

**Why:** these recur because spec authors reason from the card text locally.
**How to apply:** on every audit of examples or action legality, run these checks first.
