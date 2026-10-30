---
paths:
  - "kingisdead/**/*.py"
  - "tests/**/*.py"
  - "tools/**/*.py"
---

# Engine conventions

- `kingisdead/rules.py` is pure: no pyspiel import, no I/O, no randomness. `game.py` only adapts it
  to the pyspiel `Game`/`State` API. Randomness exists only as explicit chance nodes.
- Keep state small and cheap to copy (tuples, small ints, frozen dataclasses). MCTS clones states
  constantly; avoid per-state dicts of lists and deep object graphs.
- Use the named constants in `kingisdead/actions.py` for action IDs; never write numeric literals.
- Every function that implements a rule names its rule ID in the docstring (e.g. "Implements R-021").
- Rule tests target the public harness (`tests/harness.py`) and scenario JSON in `tests/scenarios/`,
  not engine internals, so they survive refactors. Name them `test_R###_<behaviour>`.
- Invariants (cube conservation, empty controlled regions, etc. — PLAN.md §6) are checked in the
  random-simulation tests; add a new invariant whenever a bug slips past the existing ones.
- Fixing a bug from a playtest report: first add a failing test in `tests/regressions/`, then fix.
