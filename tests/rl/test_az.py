import pytest

pytest.importorskip("torch")

import random  # noqa: E402

import numpy as np  # noqa: E402
import torch  # noqa: E402

from kingisdead.rl.az import (  # noqa: E402
    AZConfig,
    NetEvaluator,
    NetMCTS,
    ReplayBuffer,
    az_loss,
    self_play_game,
    train,
)
from kingisdead.rl.checkpoint import load_checkpoint  # noqa: E402
from kingisdead.rl.env import NUM_ACTIONS, SelfPlayEnv  # noqa: E402
from kingisdead.rl.net import NetConfig, PolicyValueNet  # noqa: E402


def _net(env: SelfPlayEnv) -> PolicyValueNet:
    torch.manual_seed(0)
    cfg = NetConfig(input_dim=env.feature_size, num_actions=NUM_ACTIONS, hidden_sizes=(16,))
    return PolicyValueNet(cfg).eval()


def test_evaluator_priors_legal_and_values_zero_sum():
    env = SelfPlayEnv(2)
    env.reset(1)
    ev = NetEvaluator(_net(env))
    prior = ev.prior(env.state)
    assert sorted(a for a, _ in prior) == sorted(env.state.legal_actions())
    assert sum(p for _, p in prior) == pytest.approx(1.0)
    vals = ev.evaluate(env.state)
    assert vals[0] == pytest.approx(-vals[1])
    assert -1.0 <= vals[env.current_player] <= 1.0


def test_visit_targets_normalised_and_legal():
    env = SelfPlayEnv(2)
    env.reset(2)
    agent = NetMCTS(_net(env), sims=12, dirichlet=(0.25, 0.3))
    pi = agent.search(env.state)
    assert pi.sum() == pytest.approx(1.0, abs=1e-5)
    assert np.all(pi[~env.mask()] == 0.0)
    assert agent.choose(env.state, random.Random(0)) in env.state.legal_actions()


def test_self_play_game_records_valid_samples():
    env = SelfPlayEnv(2)
    agent = NetMCTS(_net(env), sims=6, dirichlet=(0.25, 0.3))
    recs, plies = self_play_game(env, agent, AZConfig(temp_moves=3), seed=5)
    assert plies > 0 and recs
    for _f, m, pi, v in recs:
        assert pi.sum() == pytest.approx(1.0, abs=1e-5)
        assert np.all(pi[~m] == 0.0)
        assert -1.0 <= v <= 1.0


def test_loss_and_buffer():
    env = SelfPlayEnv(2)
    net = _net(env)
    buf = ReplayBuffer(4, env.feature_size)
    n = 6  # wraps around
    obs = np.random.rand(n, env.feature_size).astype(np.float32)
    mask = np.zeros((n, NUM_ACTIONS), np.bool_)
    mask[:, :3] = True
    pi = np.zeros((n, NUM_ACTIONS), np.float32)
    pi[:, 0] = 1.0
    buf.add(obs, mask, pi, np.ones(n, np.float32))
    assert buf.size == 4
    o, m, p, v = (torch.as_tensor(a) for a in buf.sample(4, np.random.default_rng(0)))
    pl, vl = az_loss(net, o, m, p, v)
    assert torch.isfinite(pl) and torch.isfinite(vl)


def test_train_smoke_writes_checkpoints(tmp_path):
    cfg = AZConfig(
        hidden_sizes=(16,),
        workers=1,
        sims=4,
        eval_sims=4,
        games_per_iter=2,
        task_games=1,
        batch_size=16,
        min_buffer=1,
        eval_every=1,
        eval_raw_games=2,
        eval_mcts_games=2,
        eval_best_games=2,
        seed=1,
    )
    summary = train(cfg, tmp_path, minutes=5, max_iters=1, log=lambda _s: None)
    assert summary["iters"] == 1
    for f in ("latest.pt", "best.pt", "curve.csv", "state.json"):
        assert (tmp_path / f).exists()
    _, _, meta = load_checkpoint(tmp_path / "latest.pt")
    assert meta["algorithm"] == "alphazero"
    assert "git_commit" in meta
    assert meta["run_config"]["max_iters"] == 1
    assert meta["train_config"]["eval_best_games"] == 2
    _, _, bmeta = load_checkpoint(tmp_path / "best.pt")
    assert "mcts_vs_heuristic" in bmeta["eval_stats"]

    s2 = train(cfg, tmp_path, minutes=5, max_iters=2, resume=True, log=lambda _s: None)
    assert s2["iters"] == 2
    assert s2["best"] >= summary["best"]
