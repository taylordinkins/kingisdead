# Phase 6 spike A: PPO self-play

No rule behaviour changed. Code: `kingisdead/rl/`, `tools/train_ppo.py`, `tools/eval_policy.py`.

## Setup

- Algorithm: PPO self-play (GAE, gamma 1.0, lambda 0.95, clip 0.2, 4 epochs, minibatch 1024, lr 3e-4,
  vf_coef 0.5, ent_coef 0.01, grad clip 0.5), masked policy/value MLP 256x256 (no residual), 2 players.
- Opponent mix: 80% pure self-play, 20% of games vs snapshots (every 10 updates, max 8) / heuristic / random.
- 192 games per update, 6 workers, 90 min wall clock (3224 updates, 619,008 games, about 114 games/s).
- In-run eval every 20 updates: 200 greedy games vs random and vs heuristic (SE about 0.03). `best.pt` is the
  checkpoint with the best in-run heuristic win rate (0.745 at update 2960); `latest.pt` is the final update.
- Git commit recorded in the checkpoints: 12a1692 (trainer code). Seed 0.
- Raw data: `data/ppo_main_curve.csv` (per-update losses/entropy, eval columns every 20 updates).

## Learning curve (greedy, 200 games per point, evenly spaced eval points)

| update | games | minutes | vs random | vs heuristic | entropy |
|---|---|---|---|---|---|
| 20 | 3.8k | 1 | 0.695 | 0.605 | 1.51 |
| 460 | 88k | 13 | 0.815 | 0.405 | 1.02 |
| 920 | 177k | 27 | 0.790 | 0.420 | 1.10 |
| 1380 | 265k | 41 | 0.785 | 0.595 | 0.92 |
| 1840 | 353k | 54 | 0.780 | 0.545 | 0.80 |
| 2300 | 442k | 66 | 0.840 | 0.590 | 0.72 |
| 2760 | 530k | 78 | 0.860 | 0.595 | 0.72 |
| 3220 | 618k | 90 | 0.835 | 0.680 | 0.65 |

Mean heuristic win rate over blocks of 30 evals (600 updates): 0.44, 0.46, 0.55, 0.56, 0.66, 0.65. Mean
policy entropy per 400 updates fell steadily: 1.25, 1.01, 1.03, 0.91, 0.81, 0.76, 0.75, 0.70, 0.63.
Value loss is flat at about 0.28-0.30; mean game length stays about 58-64 plies.

## Large-sample results (greedy, seat rotation, shared ties, 95% Wilson CI)

Games vs random/heuristic: 400 (seed 200). Games vs mcts:100: 100 (seed 201). No draws occurred.

| checkpoint | vs random | vs heuristic | vs mcts:100 |
|---|---|---|---|
| best.pt | 0.807 [0.766, 0.843] | 0.675 [0.628, 0.719] | 0.400 [0.309, 0.498] |
| latest.pt | 0.818 [0.777, 0.852] | 0.672 [0.625, 0.717] | 0.420 [0.328, 0.518] |

Data: `data/ppo_main_{best,latest}_vs_random_heuristic.json`, `data/ppo_main_{best,latest}_vs_mcts100.json`.
Games in the 400-game runs average about 82 plies (these counts include forced moves, unlike the training
curve's mean_plies column, so they are not directly comparable).

## Per-move latency

Policy: about 0.0003 s/move (single-thread CPU, 256x256 MLP, including feature extraction). Opponents in
the same games: random 0.00005 s, heuristic 0.0013 s, mcts:100 0.43 s. The policy is about 1400x faster
than mcts:100 per move.

## Observations

- The policy beats random about 4 games in 5 and heuristic about 2 in 3, but loses to mcts:100 (0.40-0.42,
  CI upper bounds just under 0.52, so parity with mcts:100 is not excluded). Seat/first-player effects are
  averaged out by rotation.
- The in-run best-vs-heuristic number (0.745) was inflated by selection on a noisy 200-game eval (best of
  161 evals); the 400-game re-evaluation gives 0.675. In-run "best" is therefore not meaningfully better
  than latest: best vs latest differ by less than 0.015 everywhere, well inside the noise. Treat latest as
  the default and best as a nominal alias.
- Early instability: win rate vs heuristic fell from 0.6 (update 20) to about 0.4 by update 460-920, while
  vs random stayed near 0.8. The net first learned to beat random, then lost ground against the
  heuristic's structured play, recovering after about 1300 updates. This looks like self-play drift
  (entropy collapsing from 1.5 to 1.0 in the first 460 updates).
- Not a plateau: heuristic win rate was still rising over the last 1200 updates (block means 0.55, 0.56,
  0.66, 0.65 vs earlier 0.44-0.46), and entropy was still decreasing. Vs-random improved only slowly
  (0.78 to 0.84), suggesting remaining errors are against weak but unusual play.
- Value loss did not decrease (about 0.28), so the critic has barely improved; with gamma 1 and win/loss
  returns the value signal is hard to learn from few features. This may cap policy quality.
- Caveat: only one seed and one hyperparameter set; no ablation of opponent mix or entropy coefficient.

## What a longer run might gain

Trends were still positive at 90 min, so a 3-4x longer run (about 2M games) plausibly lifts heuristic win
rate into the 0.75-0.8 range and gets near or above parity with mcts:100, but with diminishing returns
(heuristic gain from 460k to 620k games was only about +0.05-0.09 per 200k games). Cheaper levers to try
first: a larger share of heuristic/snapshot opponents (the 20% mix is small), lr decay, entropy schedule,
residual net, and a better value target. Use at least 400 games for any checkpoint comparison; 200-game
in-run evals cannot resolve differences below about 0.07.
