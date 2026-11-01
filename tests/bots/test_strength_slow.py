"""Bot strength validation (Phase 5 unit 6). Slow: run with `pytest -m slow`.

Seeded, seat-rotated 2-player tournaments via tools.tournament. Recorded larger runs live in
docs/phase-reports/phase-5-bot-strength.md.
"""

from __future__ import annotations

import pytest

from tools.tournament import run_tournament

pytestmark = pytest.mark.slow

WORKERS = 4


def _rate(res: dict, slot: int) -> dict:
    return res["bots"][slot]


def test_heuristic_beats_random():
    res = run_tournament(["heuristic", "random"], games=400, seed=11, workers=WORKERS)
    assert _rate(res, 0)["ci95"][0] > 0.5


def test_mcts_beats_random():
    res = run_tournament(["mcts:50", "random"], games=30, seed=12, workers=WORKERS)
    assert _rate(res, 0)["ci95"][0] > 0.5


def test_mcts_vs_heuristic_runs_and_is_not_clearly_worse():
    res = run_tournament(["mcts:50", "heuristic"], games=20, seed=13, workers=WORKERS)
    assert res["games"] == 20
    # Recorded only; assert MCTS is not clearly worse (upper CI bound above 0.25).
    assert _rate(res, 0)["ci95"][1] > 0.25
