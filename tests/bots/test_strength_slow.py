"""Bot strength validation (Phase 5 unit 6). Slow: run with `pytest -m slow`.

Seeded, seat-rotated 2-player tournaments via tools.tournament. Recorded larger runs live in
docs/phase-reports/phase-5-bot-strength.md.
"""

from __future__ import annotations

import pytest

from kingisdead.bots.trained import MODELS_DIR
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


def test_trained_beats_heuristic():
    pytest.importorskip("torch")
    if not (MODELS_DIR / "az-2p-v1.pt").is_file():
        pytest.skip("models/az-2p-v1.pt not present")
    # True win rate is about 0.9 (docs/phase-reports/phase-6-trained-strength.md). Requiring >= 14
    # of 20 games (seeded, so deterministic given the model): if the true rate were 0.85 the chance
    # of falling below is about 2%, at 0.9 about 0.2%. Chance level (0.5) passes with only 5.8%.
    res = run_tournament(["trained:az-2p-v1", "heuristic"], games=20, seed=21, workers=WORKERS)
    assert res["games"] == 20
    assert _rate(res, 0)["wins"] >= 14
