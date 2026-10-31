# Phase 2 report: Engine (2–3 players, base game)

Closed 2026-10-30 on branch `phase-2/engine`. Units 1–13 of the task list are ticked in PLAN.md.

## Exit criteria and evidence

| Criterion | Evidence |
|---|---|
| All rule tests green | `uv run pytest -q -rxX`: 699 passed, 2 xfailed (the two marker self-tests), 0 failed |
| Slow suite | `uv run pytest -q -m slow -rxX`: 188 passed, 0 failed (254 s) |
| `random_sim_test` passes | `tests/test_random_sim.py`: 50 serialized sims each for 2 and 3 players |
| 10,000 random games, zero invariant violations | `tests/test_random_sim.py` slow test (5,000 games per player count) and `tools/sim_stats.py --games 10000 --seed 1`: 0 violations |
| `sim_stats` recorded | `docs/phase-reports/sim_stats.md`: invasion 2382 (23.8%), coronation 7618 (76.2%); game length mean 96.91, min 37, max 136 decisions |
| Golden playthroughs for 3 seeds | `tests/playthroughs/king_is_dead_{2p_seed1,3p_seed2,2p_seed3}.txt` |
| Lint, format, types | `ruff check`, `ruff format --check`, `pyright`: all clean |
| No stale pending markers | `grep -rn "pending(" tests/`: only docstring mentions |

## Review verdicts

- **Unit 13 audit** (`rules-auditor`, `docs/phase-reports/unit-13-audit.md`): engine conforms to the spec, no blockers. 66 mutants, 63 killed, 2 equivalent, 1 real gap (rank-3 tie-break). Independent flow, struggle, scoring and card oracles matched over three goldens, 1,500 random games and 6,580 card plays.
- **Phase close audit** (`rules-auditor`): PASS. No blockers or must-fix. All 42 spec rule IDs are cited by tests.
- **Code review** (`code-reviewer`, `git diff master...HEAD`): APPROVE. No blockers or must-fix.

## Findings fixed

Unit 13 fix round (c1f2055): R-404 rank-3 non-tie-break test; R-216 examples 2 and 3 played through real play; literal R-405 `returns()` assertions; strict `_rec`; vacuous assertion removed; `sim_stats` now fails if the invariant checker is missing.

## Post-review fixes (user-approved)

- Region-pick chance outcomes are range-checked; out-of-range `action_to_string` chance ids raise `ValueError` (`tests/test_chance_validation.py`). Goldens unchanged. Fast suite: 707 passed.
- Stale docstrings in `game.py` and `tests/rules/test_observer.py` corrected.
- Spec amendment: R-216 Example 4 now cites `undo_block_void.json` as an Outmanoeuvre exercise of the same void rule (D25).

## Findings deferred (PLAN.md §9 Backlog)

Should-fix severity, none block the merge: `__str__` omits most of the state (fixing it regenerates the goldens); scenario-loaded states do not serialize; minor performance and test-skip items.

## Decisions

- D23: scenario-loaded states are not serializable; persistence stays history-based (D18).
- D24: end-type labels "invasion" and "coronation" in `sim_stats` (user-approved).
- D25: R-216 Example 4 pointer amended (user-approved).
- No rules ambiguities arose in this phase.
