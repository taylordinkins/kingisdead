# pyright: basic
# pyright: reportMissingImports=false
# torch is an optional dependency (group `train`), imported lazily; strict checking is relaxed here.
"""Trained-network seat bot (`trained:<name>`, model file `models/<name>.pt`). No rule behaviour.

AlphaZero checkpoints play net+MCTS (greedy, no Dirichlet, 50 sims) via `kingisdead.rl.az.NetMCTS`;
any other checkpoint (e.g. PPO) plays its raw greedy policy head.
"""

from __future__ import annotations

import random
import re
import threading
from pathlib import Path
from typing import Any

import pyspiel

MODELS_DIR = Path(__file__).resolve().parent.parent.parent / "models"
NAME_RE = re.compile(r"^[a-z0-9_-]+$")
TRAINED_SIMS = 50


class TrainedUnavailable(Exception):
    """torch is not installed, or the model file is missing/invalid."""


def model_path(name: str) -> Path:
    if not NAME_RE.fullmatch(name):
        raise TrainedUnavailable(f"invalid model name {name!r}")
    return MODELS_DIR / f"{name}.pt"


def check_available(name: str) -> None:
    """Raise TrainedUnavailable with a clear message if the seat cannot be played."""
    path = model_path(name)
    try:
        import torch  # noqa: F401
    except ImportError:
        raise TrainedUnavailable(
            f"seat type 'trained:{name}' needs PyTorch (install the 'train' dependency group)"
        ) from None
    if not path.is_file():
        raise TrainedUnavailable(f"model file models/{name}.pt not found")


_LOAD_LOCK = threading.Lock()
_LOADED: dict[str, tuple[Any, str | None]] = {}


def _load_net(name: str) -> tuple[Any, str | None]:
    """Load (net, algorithm) once per model name, published fully built under a lock."""
    with _LOAD_LOCK:
        hit = _LOADED.get(name)
        if hit is not None:
            return hit
        check_available(name)
        import torch

        from kingisdead.rl.checkpoint import load_checkpoint

        torch.set_num_threads(1)
        try:
            net, _config, meta = load_checkpoint(model_path(name))
        except Exception as e:
            raise TrainedUnavailable(f"cannot load models/{name}.pt: {e}") from None
        net.eval()
        res = (net, meta.get("algorithm"))
        _LOADED[name] = res
        return res


class TrainedBot:
    """Thread-safe: only the loaded net is shared; every `choose` builds its own search objects."""

    def __init__(self, name: str, sims: int = TRAINED_SIMS) -> None:
        self.name = name
        self.sims = sims

    def choose(self, state: pyspiel.State, rng: random.Random) -> int:
        net, algorithm = _load_net(self.name)
        legal = state.legal_actions()
        if len(legal) == 1:
            return int(legal[0])
        if algorithm == "alphazero":
            from kingisdead.rl.az import NetMCTS

            return int(NetMCTS(net, self.sims).choose(state, rng))
        from kingisdead.rl.env import features, legal_mask

        p = state.current_player()
        return int(net.act(features(state, p), legal_mask(state), greedy=True))
