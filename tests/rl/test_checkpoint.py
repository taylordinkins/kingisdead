import pytest

pytest.importorskip("torch")

import torch  # noqa: E402

from kingisdead.rl.checkpoint import CHECKPOINT_VERSION, load_checkpoint, save_checkpoint  # noqa: E402
from kingisdead.rl.env import NUM_ACTIONS, SelfPlayEnv  # noqa: E402
from kingisdead.rl.net import NetConfig, PolicyValueNet  # noqa: E402


def make(env):
    cfg = NetConfig(input_dim=env.feature_size, num_actions=NUM_ACTIONS, hidden_sizes=(16, 16))
    torch.manual_seed(1)
    return PolicyValueNet(cfg), cfg


def test_round_trip_identical_outputs_and_meta(tmp_path):
    env = SelfPlayEnv(2)
    env.reset(4)
    net, cfg = make(env)
    meta = {"algorithm": "ppo", "seed": 7, "train_config": {"lr": 0.1}, "eval_stats": {"wr": 0.6}}
    path = tmp_path / "sub" / "m.pt"
    save_checkpoint(path, net, cfg, meta)
    net2, cfg2, meta2 = load_checkpoint(path)
    assert cfg2 == cfg
    for k in meta:
        assert meta2[k] == meta[k]
    assert "git_commit" in meta2 and "created" in meta2
    x = torch.as_tensor(env.features()).unsqueeze(0)
    m = torch.as_tensor(env.mask()).unsqueeze(0)
    net.eval()
    with torch.no_grad():
        l1, v1 = net(x, m)
        l2, v2 = net2(x, m)
    assert torch.equal(l1, l2) and torch.equal(v1, v2)


def test_bad_version_rejected(tmp_path):
    env = SelfPlayEnv(2)
    net, cfg = make(env)
    path = tmp_path / "m.pt"
    save_checkpoint(path, net, cfg, {})
    payload = torch.load(path, weights_only=True)
    payload["version"] = CHECKPOINT_VERSION + 1
    torch.save(payload, path)
    with pytest.raises(ValueError, match="version"):
        load_checkpoint(path)
