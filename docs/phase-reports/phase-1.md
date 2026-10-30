# Phase 1 report: rules spec

Branch `phase-1/rules-spec`. Status: **spec APPROVED by the user on 2026-10-30** (the user authorised
the Status change; the spec, ACTIONS.md and SCENARIOS.md are locked, amendments go through the user).

## Deliverables

| File | Content |
|---|---|
| `docs/RULES_SPEC.md` | R-001..R-015 components and setup, R-100..R-106 turn flow, R-200..R-217 actions, summon and undo block, R-300..R-304 power struggle, R-400..R-405 game end, scoring and returns |
| `docs/ACTIONS.md` | 40 action IDs, chance sequence (38/40 nodes), phase machine and masks, canonical ordering, rule-to-mask coverage, `max_game_length` = 40n + 8n² |
| `docs/SCENARIOS.md` | scenario JSON format (`setup` and `state` kinds), validation V1..V11, setup-to-chance conversion |
| `tests/scenarios/` | `setup_basic`, `undo_block_outmanoeuvre`, `coronation_tiebreak` |

## Audits

- Unit 2 spot audit (R-200..R-217): no blockers; 1 must-fix and 7 minor fixed.
- Unit 3 spot audit (R-300..R-405): no blockers; 1 must-fix and 2 minor fixed.
- Unit 6 full audit (everything, against the rulebook pages and PLAN §4): 4 must-fix and 8 minor, all
  fixed in the fix round: "made a swap" wording for the undo block (same-faction swaps count), the
  same-type condition in ACTIONS.md, SCENARIOS V6 (a no-op Negotiate leaves the disc unused),
  `recent_win` now derived from `slots` + `region_state`, plus V3/V7 tightening, setup-time bag wording,
  R-008 discard-privacy note, R-106 wording, ACTIONS §6 coverage rows, PLAN §5.3/C4 wording.
- The audits needed no new rules ruling beyond the user-confirmed D20 and D21.

## Decisions made this phase

D20 (no-op swap and 1-for-1 Outmanoeuvre blocked) and D21 (board-based undo block: reference board =
pre-L board minus L's summoned follower), both user-confirmed.

## Reviewed and approved

The user reviewed the spec and approved everything below: the ⚑ defaults, the region index order and
the pass-count reset.

## Defaults reviewed

Defaults the rulebook does not state, marked ⚑ in the spec: player 0 starts (R-014), a player with no
cards has only PASS (R-101), a power struggle does not lift the undo block (R-217), Support with an empty
supply asks for no region (R-211), and D20's no-op case (R-216). Also the region index order (R-001)
and the pass-count reset rule (R-104), which are my choices.

Before you set APPROVED, check the spec edits are committed (they are, as of this report).
