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

- **Mutation probes beat reading for test strength** (unit 9, 2026-10-30): a pytest plugin in the
  scratchpad that monkeypatches `rules.*` / `KingIsDeadState.*` per `MUT` env var, run with
  `PYTHONPATH=<scratch> uv run pytest -p mutplug <file>`. game.py calls `rules.x` by attribute, so
  patches take. Tie-break chains are typically under-tested at the step *after* the last spec step
  (e.g. using rank-3 followers before hand-empty survived: tied courts never differ on rank 3).
- **Unit 13 full review (2026-10-30):** legality is now enforced in `_apply_action` (illegal and
  post-terminal actions raise; probe found none accepted), so the unit 7/8 lenient-apply items are
  closed. Equivalent mutants by the follower-total argument: "keep full pre-L board as B*" (D22
  ignored) and "no-swap M/O keeps the old B*" survive every test and cannot be distinguished; don't
  report them as gaps. A mutant killed ONLY by golden playthroughs (they embed the observer tensor,
  which exposes internal fields) is still a rule-test gap: goldens get regenerated, not debugged.
  Backlog test-gap items tend to survive unfixed into later units; recheck each line.
- **Phase-close bookkeeping drift** (Phase 2 close, 2026-10-30): when fixes land, the PLAN.md §9
  backlog lines that requested them are left listed as open, and module/test docstrings still
  claim `pending` markers or NotImplementedError after the code lands. At close, check each backlog
  line against the code and grep docstrings for "pending"/"NotImplemented"/"later unit".
- **Differential oracle recipe:** scratch script with an independent tracker (passes, plays,
  hand-empty, recent-win, B*) replaying random games and asserting each struggle/score/flow step,
  plus full sub-tree exploration (clone + legal_actions) per card at each turn start compared with
  an oracle built from the spec. ~7 s/game for the card oracle; 40 games is enough for masks.
- **Tooling quirk:** the protect_spec PreToolUse hook rejected a Bash heredoc that wrote a scratch
  script (no spec path in it). Write scratch scripts with the Write tool; run them with
  `PYTHONPATH=/home/xdink/code/kingisdead uv run python <script>`.

Server/UI audit patterns (first seen Phase 3 close, 2026-10-31):

- **"No rule IDs" phases still owe spec statements about the UI.** R-106/C4 say "the UI and bots
  auto-submit PASS" for an empty hand; Phase 3 built the UI but not the auto-submit, because its
  task list said server/web units carry no rule IDs. At UI/server phase close, grep the spec and
  PLAN.md §4 for "UI", "automatic", "auto-" and check each one.
- **Adapter re-derivations of engine results are tested only for shape.** The scoring breakdown
  re-runs the tie-break chain with its own copy of `_best_record`, but its "winners" field comes from
  `state.winners()`, so the tests compared winners with winners and never checked the step chain.
  Recipe: random games (800 in ~1 min) asserting last step "remaining" == winners, plus hand-made
  terminal states (mutate fields on a cloned terminal state) for rank-2 undefined and the
  all-None hand-empty share. Random games never reach rank-2 undefined, so construct it.
- **Built terminal states that never reach the step they name** (Phase 4 unit 6, 2026-10-31): the
  "rank-2 undefined" test mutated regions on a random terminal state but kept its courts, so rank 1
  decided outright and the skip was shape-only. For each built state, print the step chain and
  check the target step has tied_before > 1. Also check built recent-win against R-303: if all 8
  regions are controlled, some faction's recent-win must be 8 (fixtures used 7 / 5).
- **Per-step UI wording that states the final result early**: "share the win" was printed on every
  step whose remaining set equals the final winners, not only the deciding step (R-404 shares only
  after step 3). Check outcome text is step-local.
- **Back/rewind built by truncating and replaying with full legality checks cannot bypass the
  undo block** (B* is rebuilt by replay); confirm `_load` validates every action, then stop there.

Board/editor audit patterns (first seen Phase 4 close, 2026-10-31):

- **Phase-gated view fields leak stale values.** The adapter exposed `pending.neg_first` with
  `phase >= PHASE_NEG_SECOND`, so PHASE_SWAP (7) showed "Negotiation first region: Moray" on every
  Manoeuvre/Outmanoeuvre. Probe: random games, at each phase assert every pending field is null
  outside the phases that own it. Check `>=`/`<` gating against the phase enum order.
- **Terminal-state displays keep "next" cues.** "Struggle k+1 of 8" and a NEXT badge stayed on an
  invasion-ended board (R-400). Check every progress indicator against is_terminal.
- **Seat numbering drift.** Editor said "Player 1/Seat 1" (1-based) while board, log and spec use
  P0 (R-014). Check numbering consistency wherever the user mirrors a physical table.
- **Hook tests that pass their own predicate.** useGame tests supplied an AUTO predicate instead of
  the plugin's `autoAdvance`, so the real R-106 predicate was untested. Check the shipped function is
  what the test exercises.
- **TS-port differential recipe (worked, 0/1500 mismatches):** Python generator in the scratchpad
  (random TURN_START snapshots -> state JSON + 1-2 random field mutations, verdict from
  `load_scenario`), then a temporary `web/src/editor/__auditdiff.test.ts` (vitest only collects
  under src) that reads the scratch JSON, compares accept/reject and V-code, and is deleted after.
  Option-A setup loading (load_scenario) was also checked equal to the SCENARIOS §2 chance sequence
  (vars(), observation, legal actions) on setup_basic + 40 random setups.

**Why:** these recur because spec authors reason from the card text locally and companion docs
paraphrase the spec.
**How to apply:** on every audit of examples, masks, validators or action legality, run these first.
