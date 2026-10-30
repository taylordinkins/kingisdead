---
name: audit-patterns
description: Recurring defects found when auditing docs/RULES_SPEC.md, ACTIONS.md and SCENARIOS.md against the TKID rulebook (examples, undo block, terminology, validators, companion-doc drift)
metadata:
  type: project
---

Recurring patterns seen in spec audits (first seen 2026-10-30, Phase 1 units 2-5 and full audit):

- **Examples with local premises but global conclusions.** E.g. R-210 "Strathclyde borders no
  Scottish-controlled region → nothing eligible" ignores Scottish control elsewhere. Check every
  "nothing/only X is legal" example against the whole board, not just the named regions.
- **Examples that silently assume board state** (no board given; summon or a struggle between plays
  could remove the followers the example relies on). Ask for explicit fragments.
- **Undo block is board-based since D21 (user-confirmed 2026-10-30)**: the earlier pick-based gap
  (1-for-2 restoring B* via different picks) is resolved by D21. D20 (no-op Manoeuvre blocked,
  1-for-1 Outmanoeuvre reverse blocked) is user-confirmed: do not relitigate either.
- **"Played" vs "had an effect" conflation.** The rulebook calls a same-faction swap "no effect",
  yet D20 needs B* retained after it; R-216 conditioned B* on L "had an effect". Scenario validator
  V6 tied "disc spent" to "Negotiate not in hand", but a no-effect Negotiate leaves the disc unused.
  Whenever a rule or validator keys on a card having been played, check the no-effect case.
- **Legality must be judged on complete swaps.** Mandatory-form rules (R-202/R-215) select the form
  from *legal* (unblocked) swaps; check masks never offer a first pick whose only completions are
  blocked, and that mode is computed after block filtering.
- **Companion docs drop spec qualifiers.** ACTIONS.md's undo-block section said every "not blocked"
  mask compares with B*, omitting R-216's "same card type as L" (would make a Manoeuvre's B* block
  an Outmanoeuvre). Diff each companion-doc paraphrase against the rule it cites, qualifier by qualifier.
- **Stored fields that are derivable get under-constrained validation.** recent_win is derivable
  from slots + region_state (struggle k is always at slot k since Negotiate only swaps face-up
  cards), but V5 only checked "slot s is f's", not "latest". Prefer derived; else validate equality.
- **Rulebook terminology trap:** p6 defines "controlled regions" as having a control OR instability
  disc; card text "region controlled by the Scots" means a faction disc only. Spec uses "closed".
- **Cross-refs that exist but point at the wrong rule.** Read each ref for meaning, not just
  existence (an ID grep found no dangling refs in the full audit, as in unit 3).
- **"Immediately"/"the moment" wording vs. step ordering.** Game-end phrasing can contradict the
  sequenced resolution (R-304) and "every state" invariants (R-015 also breaks mid-setup while the
  bag holds followers). Check timing/universality words against the ordered steps and chance nodes.
- **Tiebreak arguments: right conclusion, wrong justification.** Verify the reasoning, not just the
  claim. (Coronation/invasion tiebreak chains were otherwise sound.)

**Why:** these recur because spec authors reason from the card text locally and companion docs
paraphrase the spec.
**How to apply:** on every audit of examples, masks, validators or action legality, run these first.
