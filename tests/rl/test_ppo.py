import pytest

pytest.importorskip("torch")

import numpy as np  # noqa: E402
import torch  # noqa: E402

from kingisdead.rl.checkpoint import load_checkpoint  # noqa: E402
from kingisdead.rl.env import NUM_ACTIONS, SelfPlayEnv  # noqa: E402
from kingisdead.rl.net import NetConfig, PolicyValueNet  # noqa: E402
from kingisdead.rl.ppo import PPOConfig, _Seat, gae, play_game, train  # noqa: E402


def test_gae_hand_made():
    rewards = np.array([0.0, 0.0, 1.0], dtype=np.float32)
    values = np.array([0.5, 0.25, 0.5], dtype=np.float32)
    adv, ret = gae(rewards, values, gamma=0.5, lam=0.5)
    d2 = 1.0 - 0.5
    d1 = 0.0 + 0.5 * 0.5 - 0.25
    d0 = 0.0 + 0.5 * 0.25 - 0.5
    a2 = d2
    a1 = d1 + 0.25 * a2
    a0 = d0 + 0.25 * a1
    np.testing.assert_allclose(adv, [a0, a1, a2], rtol=1e-6)
    np.testing.assert_allclose(ret, adv + values, rtol=1e-6)


def test_gae_lambda_one_gamma_one_targets_final_return():
    rewards = np.array([0.0, 0.0, -1.0], dtype=np.float32)
    values = np.array([0.1, 0.2, 0.3], dtype=np.float32)
    _, ret = gae(rewards, values, 1.0, 1.0)
    np.testing.assert_allclose(ret, [-1.0, -1.0, -1.0], atol=1e-6)


def test_rollout_never_samples_illegal_actions():
    env = SelfPlayEnv(2)
    cfg = NetConfig(input_dim=env.feature_size, num_actions=NUM_ACTIONS, hidden_sizes=(16,))
    torch.manual_seed(0)
    net = PolicyValueNet(cfg).eval()
    seats = [_Seat(net=net, record=True), _Seat(net=net, record=True)]
    returns = play_game(env, seats, seed=3)  # env.step raises on an illegal action
    assert len(returns) == 2
    steps = [st for s in seats for st in s.steps]
    assert steps
    for _obs, mask, a, logp, _v in steps:
        assert mask[a]
        assert logp <= 0.0


def test_train_smoke_writes_checkpoints_and_resumes(tmp_path):
    cfg = PPOConfig(
        hidden_sizes=(16,),
        workers=1,
        games_per_update=4,
        epochs=1,
        minibatch=64,
        eval_every=1,
        eval_games=2,
        snapshot_every=1,
        seed=1,
    )
    summary = train(cfg, tmp_path, minutes=5, max_updates=2, log=lambda s: None)
    assert summary["updates"] == 2
    _, _, meta = load_checkpoint(tmp_path / "latest.pt")
    assert meta["algorithm"] == "ppo-selfplay"
    assert 0.0 <= meta["eval_stats"]["winrate_vs_heuristic"] <= 1.0
    assert (tmp_path / "best.pt").exists()
    assert len((tmp_path / "curve.csv").read_text().strip().splitlines()) == 3
    s2 = train(cfg, tmp_path, minutes=5, max_updates=3, resume=True, log=lambda s: None)
    assert s2["updates"] == 3
