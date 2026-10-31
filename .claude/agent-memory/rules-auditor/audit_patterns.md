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


Code/test audit patterns (first seen 2026-10-30, Phase 2 unit 7 spot audit):

- **pyspiel Python apply_action does not check legality.** Probe illegal actions per sub-step
  phase with a quick script (e.g. PASS mid-swap was accepted in unit 7 because game.py handles
  PASS before dispatching on phase). Masks being right is not enough.
- **Follower-total argument for undo-block tests.** Swaps preserve totals and each summon removes 1,
  so an old B* is unreachable after any later play except Assemble/Support with a 1-follower supply
  (net 0). Tests of "B* replaced by no-swap M/O" or "D22 void vs naive negative count" are
  inherently non-discriminating via masks; only a physical-origin B* alternative (undo_block_void)
  or a net-0 Assemble discriminates. Don't flag the engine for these; note the test as weak at most.
  Unit 8 (struggle) escalated it: a mid-card PASS can trigger a struggle mid-Assemble, and PASS
  after terminal runs extra struggles (4th instability disc; IndexError after the 8th). Also probe
  apply_action on a terminal state every unit. Tracked in PLAN.md §9 ("Fix before Phase 3").
- **Tests that silently rely on the lenient apply_action.** Loops like `while not terminal: PASS;
  PASS` apply a PASS to a terminal state; they'll break when legality is enforced. Check that
  multi-action loop bodies re-test is_terminal between actions.
- Run spec examples end to end (pre-L board → L → summon → next play) in a scratch script; tests
  often inject B* via scenario and skip the capture path.

**Why:** these recur because spec authors reason from the card text locally and companion docs
paraphrase the spec.
**How to apply:** on every audit of examples, masks, validators or action legality, run these first.
