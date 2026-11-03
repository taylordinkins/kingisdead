import random

import pytest

pytest.importorskip("torch")

import numpy as np  # noqa: E402
import torch  # noqa: E402

from kingisdead.rl.env import NUM_ACTIONS, SelfPlayEnv  # noqa: E402
from kingisdead.rl.net import NEG_INF, NetConfig, PolicyValueNet  # noqa: E402


def make_net(env: SelfPlayEnv, **kw) -> PolicyValueNet:
    cfg = NetConfig(
        input_dim=env.feature_size, num_actions=NUM_ACTIONS, hidden_sizes=(32, 32), **kw
    )
    torch.manual_seed(0)
    return PolicyValueNet(cfg)


def test_masked_forward_no_illegal_mass():
    env = SelfPlayEnv(2)
    env.reset(1)
    net = make_net(env)
    x = torch.as_tensor(env.features()).unsqueeze(0)
    m = torch.as_tensor(env.mask()).unsqueeze(0)
    logits, value = net(x, m)
    assert logits.shape == (1, NUM_ACTIONS)
    assert value.shape == (1, 1)
    probs = torch.softmax(logits, dim=-1)[0]
    assert probs[~m[0]].sum().item() == 0.0
    assert probs[m[0]].sum().item() == pytest.approx(1.0)
    assert logits[0][~m[0]].max().item() == NEG_INF


@pytest.mark.parametrize("residual", [False, True])
def test_value_dim_configurable(residual):
    env = SelfPlayEnv(3)
    env.reset(2)
    net = make_net(env, num_players=3, value_dim=3, residual=residual)
    x = torch.as_tensor(env.features()).unsqueeze(0)
    m = torch.as_tensor(env.mask()).unsqueeze(0)
    _, value = net(x, m)
    assert value.shape == (1, 3)


@pytest.mark.parametrize("greedy", [False, True])
def test_act_always_legal_over_random_games(greedy):
    env = SelfPlayEnv(2)
    rng = random.Random(5)
    net = make_net(env)
    steps = 0
    for seed in range(3):
        env.reset(seed)
        while not env.done:
            mask = env.mask()
            a = net.act(env.features(), mask, greedy=greedy, rng=rng)
            assert mask[a]
            env.step(a if rng.random() < 0.5 else rng.choice(np.flatnonzero(mask).tolist()))
            steps += 1
    assert steps > 0


def test_act_greedy_deterministic_and_seeded_sampling():
    env = SelfPlayEnv(2)
    env.reset(3)
    net = make_net(env)
    f, m = env.features(), env.mask()
    assert net.act(f, m, greedy=True) == net.act(f, m, greedy=True)
    a = [net.act(f, m, rng=random.Random(9)) for _ in range(3)]
    assert len(set(a)) == 1


def test_act_no_legal_raises():
    env = SelfPlayEnv(2)
    env.reset(0)
    net = make_net(env)
    with pytest.raises(ValueError):
        net.act(env.features(), np.zeros(NUM_ACTIONS, dtype=np.bool_))
