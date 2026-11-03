"""TrainedBot is shared across session threads: searches must not share caches or RNGs."""

import pytest

pytest.importorskip("torch")

import random  # noqa: E402
import threading  # noqa: E402
from pathlib import Path  # noqa: E402

import torch  # noqa: E402

import kingisdead.bots.trained as trained  # noqa: E402
import kingisdead.game  # noqa: E402, F401  (registers the game)
from kingisdead.rl.env import NUM_ACTIONS, SelfPlayEnv  # noqa: E402
from kingisdead.rl.net import NetConfig, PolicyValueNet  # noqa: E402
from kingisdead.scenario import load_scenario  # noqa: E402

SCEN = Path(__file__).resolve().parent.parent / "scenarios"


@pytest.fixture
def bot(monkeypatch: pytest.MonkeyPatch) -> trained.TrainedBot:
    torch.manual_seed(0)
    cfg = NetConfig(
        input_dim=SelfPlayEnv(2).feature_size, num_actions=NUM_ACTIONS, hidden_sizes=(16,)
    )
    monkeypatch.setitem(trained._LOADED, "thr", (PolicyValueNet(cfg).eval(), "alphazero"))
    return trained.TrainedBot("thr", sims=20)


def test_concurrent_choose_on_identical_looking_histories(bot: trained.TrainedBot) -> None:
    s1 = load_scenario(SCEN / "undo_block_void.json")
    s2 = load_scenario(SCEN / "undo_block_outmanoeuvre.json")
    assert list(s1.history()) == list(s2.history()) == []
    alone = bot.choose(s1.clone(), random.Random("x"))

    out: dict[str, int] = {}

    def run(key: str, st) -> None:
        out[key] = bot.choose(st.clone(), random.Random("x"))

    threads = [
        threading.Thread(target=run, args=("a", s1)),
        threading.Thread(target=run, args=("b", s2)),
        threading.Thread(target=run, args=("c", s1)),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert out["a"] in s1.legal_actions()
    assert out["c"] in s1.legal_actions()
    assert out["b"] in s2.legal_actions()
    assert out["a"] == out["c"] == alone
