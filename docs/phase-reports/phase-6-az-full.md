# Phase 6 unit 6: full AlphaZero training run (D33)

Model: `models/az-2p-v1.pt` (copy of `runs/az-full/best.pt`, ~0.9 MB). Used with net+MCTS, not the raw policy head.

## Run
- Command: `uv run python -m tools.train_az --out runs/az-full --minutes 180 --workers 6 --sims 50 --eval-sims 50 --eval-every 5 --eval-best-games 100` (device: cuda), trainer commit `f5d6690`.
- 474 iterations, 22,752 self-play games, 1.31M samples, 10,809 s.
- In-run curve (net+MCTS 50 sims vs heuristic, 100 games, every 5 iterations): 0.79 at iter 5, 0.8-0.84 around iters 100-200, 0.84-0.97 after iter 250. `best.pt` was picked as the maximum of these evals (0.97 at iter ~405). That maximum is selection-biased, so the independent eval below is the number to trust.

## Final eval (independent seed 500, greedy, net+MCTS 50 sims, `tools.eval_policy --mode mcts`)
| Opponent | Games | Wins | Win rate | Wilson 95% CI |
|---|---|---|---|---|
| heuristic | 300 | 270 | 0.900 | [0.861, 0.929] |
| mcts:100 | 100 | 87 | 0.870 | [0.790, 0.922] |

No draws. Ties shared as in `tools/tournament.py`. Policy ~0.027 s/move vs ~0.45 s/move for `mcts:100`. Raw JSON: `runs/az-full/final_eval.json` (not committed).

## Done condition
Net+MCTS beats heuristic >= 60% with Wilson lower bound > 0.5 (0.90, lower 0.861), and it beats `mcts:100` rather than just approaching it (0.87, lower 0.79). Compared with the 90-minute spike (0.80-0.85 vs heuristic, 0.66-0.70 vs `mcts:100`) this is a clear gain.

## Caveats
- Two-player games only; evaluated against built-in bots, not humans.
- Seats rotate by game index; one seed per opponent.
- Raw policy head (no search) was not re-evaluated here; the PPO and spike reports show it is weak.
