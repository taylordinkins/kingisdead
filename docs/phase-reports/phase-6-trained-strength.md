# Phase 6 trained-policy strength (trained:az-2p-v1)

2-player games, seat rotation on, ties shared (see `tools/tournament.py`). Win rate is for
`trained:az-2p-v1` (AlphaZero net + MCTS, 50 sims, greedy; see `kingisdead/bots/trained.py`); 95%
Wilson CI. Raw JSON (with git commit) in `docs/phase-reports/data/trained_*.json`.
Command: `uv run python -m tools.tournament --seats trained:az-2p-v1 B --games N --seed S --workers 6 --json ...`
`tools/tournament.py` needed no change: `get_bot` builds the `TrainedBot` lazily in each worker
process (the cache is empty at fork), so each worker loads the model itself and no torch object is pickled.

| Opponent | Games | Seed | Win rate | 95% CI | Wall time | Mean s/move (trained) |
|---|---|---|---|---|---|---|
| random | 100 | 200 | 0.900 | [0.826, 0.945] | 24 s | 0.029 |
| heuristic | 200 | 201 | 0.870 | [0.816, 0.910] | 57 s | 0.032 |
| mcts:100 | 100 | 202 | 0.790 | [0.700, 0.858] | 397 s | 0.029 |

No draws; mean game length about 89 plies. Opponent cost per move: mcts:100 0.45 s, heuristic 1.3 ms.

Consistency with unit 6 (`phase-6-az-full.md`, eval_policy: 0.90 vs heuristic n=300, 0.87 vs
mcts:100 n=100): the heuristic result (0.87, n=200) is within noise of 0.90 and the intervals
overlap. vs mcts:100 the tournament gives 0.79 against 0.87; the intervals overlap heavily (different
seeds and game sets, n=100 each), so this is consistent but suggests the true rate is nearer 0.8.

Caveats: the win rate vs random (0.90) is not higher than vs heuristic, so the net is
not a strict improvement over simple play in every position; at n=100 CIs are about +-0.08; only
the 2-player model exists (no 3-player trained policy); results hold for 50 sims at play time.

Slow test: `tests/bots/test_strength_slow.py::test_trained_beats_heuristic` (20 games, seed 21,
needs torch and `models/az-2p-v1.pt`, else skipped) asserts at least 14 wins.
