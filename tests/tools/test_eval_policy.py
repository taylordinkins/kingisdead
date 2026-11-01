import json

import pytest

pytest.importorskip("torch")

import torch  # noqa: E402

from kingisdead.rl.checkpoint import save_checkpoint  # noqa: E402
from kingisdead.rl.env import NUM_ACTIONS, SelfPlayEnv  # noqa: E402
from kingisdead.rl.net import NetConfig, PolicyValueNet  # noqa: E402
from tools.eval_policy import evaluate_policy, main  # noqa: E402


@pytest.fixture
def ckpt(tmp_path):
    cfg = NetConfig(
        input_dim=SelfPlayEnv(2).feature_size, num_actions=NUM_ACTIONS, hidden_sizes=(16,)
    )
    torch.manual_seed(0)
    p = tmp_path / "net.pt"
    save_checkpoint(p, PolicyValueNet(cfg), cfg)
    return p


def test_evaluate_policy_random_opponent(ckpt):
    r = evaluate_policy(str(ckpt), "random", games=4, seed=1)
    assert r["games"] == 4
    assert 0.0 <= r["win_rate"] <= 1.0
    assert r["ci95"][0] <= r["win_rate"] <= r["ci95"][1]
    again = evaluate_policy(str(ckpt), "random", games=4, seed=1)
    assert again["wins"] == r["wins"]


def test_cli_games_for_and_json(ckpt, tmp_path):
    out = tmp_path / "o.json"
    rc = main(
        [
            "--checkpoint",
            str(ckpt),
            "--opponents",
            "random",
            "heuristic",
            "--games",
            "2",
            "--games-for",
            "heuristic=3",
            "--seed",
            "5",
            "--json",
            str(out),
        ]
    )
    assert rc == 0
    res = json.loads(out.read_text())["results"]
    assert [(r["opponent"], r["games"]) for r in res] == [("random", 2), ("heuristic", 3)]
