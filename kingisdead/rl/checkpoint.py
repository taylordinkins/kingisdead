# pyright: basic
# torch is an optional dependency (group `train`), so strict checking is relaxed in this file.
"""Save/load trained networks as plain-dict torch files (loaded with weights_only=True)."""

from __future__ import annotations

import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import torch

from kingisdead.rl.net import NetConfig, PolicyValueNet

CHECKPOINT_VERSION = 1


def git_commit() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True, timeout=5
        )
        return out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def save_checkpoint(
    path: str | Path, net: PolicyValueNet, config: NetConfig, meta: dict[str, Any] | None = None
) -> None:
    """meta keys (all optional): algorithm, git_commit, seed, train_config, created, eval_stats.
    Missing git_commit/created are filled in. Values must be plain types (dict/list/str/num)."""
    m: dict[str, Any] = {
        "algorithm": None,
        "git_commit": git_commit(),
        "seed": None,
        "train_config": None,
        "created": datetime.now(UTC).isoformat(),
        "eval_stats": None,
    }
    m.update(meta or {})
    payload = {
        "version": CHECKPOINT_VERSION,
        "config": config.to_dict(),
        "state_dict": {k: v.detach().cpu() for k, v in net.state_dict().items()},
        "meta": m,
    }
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    torch.save(payload, p)


def load_checkpoint(
    path: str | Path, map_location: str = "cpu"
) -> tuple[PolicyValueNet, NetConfig, dict[str, Any]]:
    payload = torch.load(Path(path), map_location=map_location, weights_only=True)
    version = payload.get("version") if isinstance(payload, dict) else None
    if version != CHECKPOINT_VERSION:
        raise ValueError(
            f"unsupported checkpoint version {version!r}; expected {CHECKPOINT_VERSION}"
        )
    config = NetConfig.from_dict(payload["config"])
    net = PolicyValueNet(config)
    net.load_state_dict(payload["state_dict"])
    net.to(map_location)
    net.eval()
    return net, config, dict(payload["meta"])
