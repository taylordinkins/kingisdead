"""RL env (Phase 6 unit 1). Must not import torch."""

from __future__ import annotations

import random
import sys

import numpy as np
import pytest

from kingisdead.rl.env import NUM_ACTIONS, SelfPlayEnv


def _playout(n: int, seed: int, policy_seed: int = 0, check: bool = True):
    env = SelfPlayEnv(n)
    env.reset(seed)
    rng = random.Random(policy_seed)
    trace: list[tuple[int, int]] = []
    shapes: set[tuple[tuple[int, ...], str]] = set()
    while not env.done:
        assert env.current_player in range(n)  # never a chance node
        assert not env.state.is_chance_node()
        f, m = env.features(), env.mask()
        shapes.add((f.shape, str(f.dtype)))
        if check:
            assert m.shape == (NUM_ACTIONS,) and m.dtype == np.bool_
            assert set(np.flatnonzero(m).tolist()) == set(env.state.legal_actions())
        a = rng.choice(np.flatnonzero(m).tolist())
        trace.append((env.current_player, a))
        env.step(a)
    return env, trace, shapes


def test_no_torch_imported():
    assert "torch" not in sys.modules


@pytest.mark.parametrize("n", [2, 3])
@pytest.mark.parametrize("seed", [0, 1, 2, 3])
def test_playout_terminal_with_returns(n: int, seed: int):
    env, trace, shapes = _playout(n, seed)
    assert env.done and env.current_player == -1 and trace
    assert len(env.returns()) == n
    assert len(shapes) == 1
    ((shape, dtype),) = shapes
    assert shape == (env.feature_size,) and dtype == "float32"
    assert not env.mask().any()


def test_returns_before_terminal_raises():
    env = SelfPlayEnv(2)
    env.reset(0)
    with pytest.raises(RuntimeError):
        env.returns()


def test_illegal_action_rejected():
    env = SelfPlayEnv(2)
    env.reset(0)
    bad = int(np.flatnonzero(~env.mask())[0])
    with pytest.raises(ValueError):
        env.step(bad)


@pytest.mark.parametrize("n", [2, 3])
def test_seeded_determinism(n: int):
    e1, t1, _ = _playout(n, 5, check=False)
    e2, t2, _ = _playout(n, 5, check=False)
    assert t1 == t2 and e1.returns() == e2.returns()
    _, t3, _ = _playout(n, 6, check=False)
    assert t3 != t1


def test_bad_player_count():
    with pytest.raises(ValueError):
        SelfPlayEnv(4)
