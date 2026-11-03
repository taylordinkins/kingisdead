"""Phase 6 unit 7: `trained:<name>` seat type."""

import random
import re

import pyspiel
import pytest
from fastapi.testclient import TestClient

import kingisdead.bots.trained as trained
from server.app import create_app
from server.bots import SEAT_TYPE_PATTERN, get_bot, is_valid_seat_type


@pytest.mark.parametrize(
    "t", ["trained:az-2p-v1", "trained:a_b-9", "human", "random", "heuristic", "mcts", "mcts:20"]
)
def test_seat_accepted(t: str) -> None:
    assert is_valid_seat_type(t)
    assert re.fullmatch(SEAT_TYPE_PATTERN, t)


@pytest.mark.parametrize(
    "t", ["trained:", "trained", "trained:../x", "trained:a/b", "trained:A", "trained:a.pt"]
)
def test_seat_rejected(t: str) -> None:
    assert not is_valid_seat_type(t)
    assert not re.fullmatch(SEAT_TYPE_PATTERN, t)


def _create(seats: list[str]):
    c = TestClient(create_app())
    return c.post("/api/games", json={"params": {"num_players": 2}, "seats": seats, "seed": 1})


def test_missing_model_422() -> None:
    pytest.importorskip("torch")
    r = _create(["human", "trained:no-such-model"])
    assert r.status_code == 422
    assert "no-such-model" in r.text


def test_missing_torch_422(monkeypatch: pytest.MonkeyPatch) -> None:
    import builtins

    real = builtins.__import__

    def fake(name, *a, **k):
        if name == "torch":
            raise ImportError("no torch")
        return real(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", fake)
    r = _create(["human", "trained:az-2p-v1"])
    assert r.status_code == 422
    assert "PyTorch" in r.text


def test_three_players_422() -> None:
    c = TestClient(create_app())
    r = c.post(
        "/api/games",
        json={"params": {"num_players": 3}, "seats": ["human", "human", "trained:az-2p-v1"]},
    )
    assert r.status_code == 422
    assert "2-player" in r.text


def test_bot_returns_legal_action() -> None:
    pytest.importorskip("torch")
    if not trained.model_path("az-2p-v1").is_file():
        pytest.skip("model not present")
    state = pyspiel.load_game("python_king_is_dead(players=2)").new_initial_state()
    rng = random.Random(0)
    bot = get_bot("trained:az-2p-v1")
    for i in range(6):
        if state.is_chance_node():
            acts, probs = zip(*state.chance_outcomes(), strict=True)
            state.apply_action(rng.choices(acts, weights=probs)[0])
            continue
        a = bot.choose(state, random.Random(i))
        assert a in state.legal_actions()
        state.apply_action(a)
