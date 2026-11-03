# Phase 6: Trained policies

Branch `phase-6/trained-policies`. No rule behaviour changed and the rules spec is untouched, so `rules-auditor` was not run.

## Exit criteria
| Criterion | Evidence |
|---|---|
| Beats heuristic >= 60% (Wilson lower bound > 0.5) over 300+ 2-player games | `tools.eval_policy --mode mcts --sims 50`, seed 500: 270/300 = 0.90, CI [0.861, 0.929] (`phase-6-az-full.md`). Tournament cross-check, 200 games: 0.87 [0.816, 0.910] |
| Approaches `mcts:100` | 87/100 = 0.87 [0.790, 0.922] (eval_policy); tournament 0.79 [0.700, 0.858] (`phase-6-trained-strength.md`). Above parity in both |
| Playable from the lobby | Preset "Trained (AlphaZero)" = `trained:az-2p-v1`; `web/e2e/bots.spec.ts` plays human vs trained |

## Evidence of a green tree
- `ruff check`, `ruff format --check`, `pyright`: clean (pyright also 0 errors in a torch-free `uv sync --locked` env, as CI runs).
- `pytest -q`: 934 passed, 1 skipped, 2 xfailed. `pytest -q -m slow`: 192 passed (348 s).
- Web: `tsc` clean, `npm test` 126/126, `npm run e2e` 10/10.
- No `pending` markers claimed by this phase.

## What shipped
Optional `train` dependency group and RL env; masked policy/value net and checkpoints; PPO spike and AlphaZero-style trainer (D33 picked AlphaZero: net + MCTS); full 3 h run (474 iterations, 22,752 games, RTX 3080); `models/az-2p-v1.pt`; `trained:<name>` seat type; strength report; Playwright test.

## Reviews
- `code-reviewer` (Opus) on `git diff master...HEAD`: CHANGES NEEDED, then APPROVE after one fix round (`cf67e4d`).
  - Fixed: CI pyright failed without torch (9 errors); shared `TrainedBot`/`NetMCTS` state raced across session threads; lazy-load race; weak 2-player 422 test (new `tests/bots/test_trained_threads.py`).
  - Checked sound: model-name validation (no path traversal), `torch.load(weights_only=True)`, 422 paths, action legality, player perspective, AZ resume.
- `rules-auditor`: not run (no rule IDs touched).

## Deferred (PLAN.md section 9 Backlog)
Non-atomic trainer writes and unpersisted replay buffer on resume; process-wide `torch.set_num_threads(1)`; model load before the forced-move shortcut; trained preset offered in 3-player lobby; vs `mcts:100` is about 0.8 and could improve with a longer run.

## Decisions
D34 (trained seat serving), plus D33 from the checkpoint.
