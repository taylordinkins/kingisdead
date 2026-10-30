# Phase 0 report: scaffold and OpenSpiel API spike

Closed 2026-10-30 on branch `phase-0/scaffold`. OpenSpiel 2.0.2, Python 3.12.

## Exit criteria (PLAN.md §7, Phase 0)

| Criterion | Evidence |
|---|---|
| `uv` project, pinned `open-spiel==2.0.2`, ruff, pytest, pyright, CI, `CLAUDE.md`, agents, skills, hooks | `uv sync` installs and runs; `.github/workflows/ci.yml`, `.claude/` committed; `tests/test_hooks.py` covers the hooks |
| Lint clean | `uv run ruff check .`: All checks passed; `uv run ruff format --check .`: 33 files already formatted |
| Types clean | `uv run pyright`: 0 errors, 0 warnings (strict, over `kingisdead` and `tests/support`, using `typings/pyspiel.pyi`) |
| `uv run pytest` green | `uv run pytest -q`: 31 passed, 182 deselected, 2 xfailed (the xfails are the pending/regression marker self-tests) |
| Slow suite green | `uv run pytest -q -m slow`: 182 passed (includes `tests/test_hooks.py`, now marked slow) |
| Toy chance game registered; `register_game`/`GameType`, observer API, `random_sim_test` with serialization, playthrough generation and `MCTSBot` confirmed on 2.0.2 | `tests/test_openspiel_api.py` (2- and 3-player runs of each); `tests/support/toy_chance_game.py` |
| Spike notes committed | `docs/OPENSPIEL_NOTES.md`. Claims with no test are labelled "checked in source (file:line)" |

## Review

Opus code review verdict: CHANGES NEEDED, 8 findings. Findings 1-6 were fixed in commit 57f770a
(workflow hooks and settings). Findings 7-8 are fixed in this commit: the OpenSpiel notes
corrections (default `rewards()` equals `returns()` at terminal; `max_chance_nodes_in_history`
unenforced; deserialization does not replay history; clone deep-copies `__dict__`; untested claims
relabelled) and the `typings/pyspiel.pyi` stub with strict pyright over `tests/support`.

Process trims applied (user-approved, for rapid development): `tests/test_hooks.py` is slow-marked
to speed the stop gate; the spot-audit runs only on units touching scoring, power struggles or the
undo block; `/close-phase` does one fix round and only blocker or must-fix findings block the
merge, the rest going to the PLAN §9 Backlog. PLAN §8 matches.

## Deferred

PLAN.md §9 "Backlog" (five Phase 0 items: spec-test-writer source visibility, git merge/pull/rebase
spec-revert gap, `kingisdead` token false positive, spec backstop with uncommitted edits, branch
protection needing GitHub Pro).

## Decisions

D14 model use, D15 spec lock, D16 tests ahead of code, D17 test independence, D18 persist action
histories and never deserialize client input, D19 pyspiel type stub in `typings/`.
