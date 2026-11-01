# Phase 5 bot strength validation

2-player games, seat rotation on, ties shared (see `tools/tournament.py`). Win rate is for the
first-listed bot; 95% Wilson CI. Raw JSON (with git commit) in `docs/phase-reports/data/`.
Command: `uv run python -m tools.tournament --seats A B --games N --seed S --workers 6 --json ...`

| Matchup | Games | Seed | Win rate (first) | 95% CI | Mean s/move (first) |
|---|---|---|---|---|---|
| heuristic vs random | 1000 | 100 | 0.758 | [0.730, 0.784] | 0.0021 |
| mcts:100 vs random | 300 | 101 | 0.970 | [0.944, 0.984] | 0.449 |
| mcts:100 vs heuristic | 100 | 102 | 0.790 | [0.700, 0.858] | 0.407 |

No draws in any run; mean game length about 77 plies. Mean game wall time: 17.4 s (mcts vs random),
16.0 s (mcts vs heuristic); random and heuristic moves cost about 0.1 ms and 1.5-2 ms.

Exit criterion "MCTS clearly beats random over a few hundred 2-player games": met (0.97, lower
bound 0.944). MCTS also clearly beats the heuristic. No evaluator change was needed.

Slow test (`tests/bots/test_strength_slow.py`, `pytest -m slow`, about 2.5 min with 4 workers):
heuristic vs random 400 games (seed 11), mcts:50 vs random 30 games (seed 12), and mcts:50 vs
heuristic 20 games (seed 13); asserts Wilson lower bound > 0.5 for the first two and a sanity
bound for the third.
