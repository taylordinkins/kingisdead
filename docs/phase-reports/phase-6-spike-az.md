# Phase 6 spike B: AlphaZero-style self-play

No rule behaviour changed. Code: `kingisdead/rl/az.py`, `tools/train_az.py`, `tools/eval_policy.py` (now with `--mode raw|mcts`).

## Setup

- Own PUCT loop built on OpenSpiel's Python `mcts` (`MCTSBot` with `puct_value`, a net evaluator giving priors and value,
  Dirichlet noise at the root in self-play). OpenSpiel's bundled `alpha_zero` is unusable here: it depends on JAX/TF
  model code that is not in our torch-only `train` group and does not handle our masked frozen action space.
- Net: masked policy/value MLP 256x256 (no residual), 2 players. c_puct 1.5, Dirichlet alpha 0.3 / eps 0.25, first 12
  own decisions sampled from visits then greedy, 50 sims per move in self-play.
- Learner: replay buffer 200k, batch 512, lr 1e-3, weight decay 1e-4, 4 train steps-worth of reuse per new sample,
  48 games per iteration, 6 workers, 90 min wall clock (215 iterations, 10,320 games, 667,950 samples).
- Throughput: about 2.4 self-play games/s while self-playing (4279 s of the 5413 s run); training took only 226 s;
  the rest was evals and sync. About 1.9 games/s overall.
- In-run eval every 5 iterations: 100 raw games and only 24 mcts games per opponent (very noisy). `best.pt` is the best
  in-run mcts-vs-heuristic (0.925 on 40 games), which is selection on noise; treat it as a nominal alias for a
  late checkpoint. `latest.pt` is the final iteration. Seed 0. Trainer commit a8680eb.
- Raw data: `data/az_main_curve.csv`.

## Learning curve (8 of 43 eval points; raw = greedy policy head, mcts = 50-sim net search)

| iter | games | minutes | policy loss | value loss | raw vs random | raw vs heur | mcts vs random | mcts vs heur |
|---|---|---|---|---|---|---|---|---|
| 5 | 240 | 2 | 1.477 | 0.109 | 0.27 | 0.21 | 0.825 | 0.75 |
| 35 | 1.7k | 13 | 1.354 | 0.101 | 0.47 | 0.45 | 0.875 | 0.80 |
| 65 | 3.1k | 25 | 1.384 | 0.123 | 0.50 | 0.42 | 0.875 | 0.80 |
| 95 | 4.6k | 37 | 1.403 | 0.131 | 0.57 | 0.41 | 0.875 | 0.90 |
| 125 | 6.0k | 48 | 1.419 | 0.117 | 0.60 | 0.41 | 0.925 | 0.85 |
| 155 | 7.4k | 61 | 1.434 | 0.107 | 0.62 | 0.47 | 0.975 | 0.70 |
| 185 | 8.9k | 75 | 1.438 | 0.103 | 0.63 | 0.44 | 0.90 | 0.925 |
| 215 | 10.3k | 90 | 1.439 | 0.101 | 0.72 | 0.50 | 0.90 | 0.675 |

Raw evals have 100 games (SE about 0.05); mcts evals only 24 games (SE about 0.1), so the mcts columns cannot show
a trend. Policy loss is cross-entropy to the search visit distribution; it rises slightly because search targets get
sharper as the net improves, so it is not a progress signal. Raw strength climbs steadily (vs random 0.27 to 0.72).

## Large-sample results (seat rotation, shared ties, 95% Wilson CI, no draws)

Raw mode, 400 games, seed 300:

| checkpoint | vs random | vs heuristic |
|---|---|---|
| latest.pt | 0.588 [0.539, 0.635] | 0.440 [0.392, 0.489] |
| best.pt | 0.598 [0.549, 0.644] | 0.482 [0.434, 0.531] |

Mcts mode (net-guided search, no noise, most-visited action). 200 games vs heuristic, 100 vs mcts:100:

| checkpoint | sims | seed | vs heuristic | vs mcts:100 |
|---|---|---|---|---|
| latest.pt | 50 | 300 | 0.800 [0.739, 0.850] | 0.700 [0.604, 0.781] |
| best.pt | 50 | 300 | 0.845 [0.788, 0.889] | 0.660 [0.563, 0.745] |
| latest.pt | 100 | 301 | 0.860 [0.805, 0.901] | 0.690 [0.594, 0.772] |

Data: `data/az_main_{latest,best}_raw.json`, `data/az_main_{latest,best}_mcts50.json`, `data/az_main_latest_mcts100.json`.
Game counts were not reduced.

## Per-move latency (single process, CPU)

| mode | s/move |
|---|---|
| raw policy | 0.0003-0.0004 |
| mcts, 50 sims | 0.033-0.040 |
| mcts, 100 sims | 0.079-0.081 |
| reference: heuristic | about 0.001 |
| reference: mcts:100 (random rollouts) | about 0.4 |

Latencies were measured while 6 workers ran in parallel, so they are slightly pessimistic.

## Comparison with the PPO spike (equal 90 min wall clock, same machine, same net size)

| | PPO (spike A) | AZ (spike B) |
|---|---|---|
| raw vs random | 0.82 | 0.59 |
| raw vs heuristic | 0.67 | 0.44-0.48 |
| raw vs mcts:100 | 0.42 | not measured |
| search vs heuristic | n/a | 0.80 (50 sims), 0.86 (100 sims) |
| search vs mcts:100 | n/a | 0.70 (50 sims), 0.69 (100 sims) |
| s/move | 0.0003 | 0.0004 raw; 0.035 at 50 sims; 0.08 at 100 sims |
| games trained on | 619k | 10.3k |

- Strength: with search, AZ clearly beats both heuristic and mcts:100 (CI lower bound on mcts:100 about 0.6), which PPO
  could not (0.42). Without search, PPO's policy is much stronger than AZ's raw head. The 100-sim run is not significantly
  better than the 50-sim run vs mcts:100 (0.69 vs 0.70), so the extra search cost bought nothing there; vs heuristic
  the gain (0.80 to 0.86) is within noise as well (different seeds).
- Latency and serving: PPO is 100x+ cheaper per move and needs no search code, so it is the better fit for many
  concurrent sessions or a cheap default bot. AZ at 50 sims costs about 0.035 s/move, which is still about 10x faster
  than mcts:100 while being stronger, and is fine for the web UI (one thinking bot per game), but it needs a torch
  inference per simulation in the server process. Both need torch at serve time; the AZ agent also needs the
  OpenSpiel mcts code path, which already ships.
- Training complexity: PPO is simpler (one loop, no search in the actors). AZ needs a search-in-the-loop actor,
  replay buffer, and care with evaluators/noise/temperature; self-play is about 20x slower per game, but each game
  yields much better targets.
- Sample efficiency: AZ reached mcts:100-beating play from 10k games versus PPO's 619k games without matching it,
  so about 60x more sample efficient in games, though not in compute; at equal wall-clock AZ is the stronger
  searcher and PPO the stronger raw policy.
- Caveats: one seed each, no ablations; in-run evals too small to select checkpoints (best.pt vs latest.pt differ
  within noise everywhere: raw heuristic 0.482 vs 0.440 has overlapping CIs). Latency was measured under 6-way
  parallel load. The 100-sim cell shares no seed with the 50-sim cells.

## What a longer run might gain

The raw head was still improving linearly at 90 min (vs random 0.27 to 0.72, heuristic 0.21 to 0.50), so a 3-4x run
likely brings raw play toward PPO's level, and search strength would rise further, though mcts-vs-opponent evals are
too noisy to confirm that now. Cheap levers: larger eval (200+ games) for checkpoint selection, a residual or wider
net, lr decay, more sims in self-play (cost is linear), and distilling the search into the raw head so the cheap
policy approaches the search policy. A hybrid is also plausible: warm-start AZ from the PPO net.
