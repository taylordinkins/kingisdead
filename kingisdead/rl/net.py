# pyright: basic
# torch is an optional dependency (group `train`), so strict checking is relaxed in this file.
"""Masked policy/value network. Torch is imported only here and in checkpoint.py."""

from __future__ import annotations

import random
from dataclasses import asdict, dataclass, field
from typing import Any

import numpy as np
import torch
from torch import nn

NEG_INF = -1e9


@dataclass(frozen=True)
class NetConfig:
    """`value_dim=1`: scalar value from the mover's perspective (2p). For 3p use num_players."""

    input_dim: int
    num_actions: int
    hidden_sizes: tuple[int, ...] = field(default=(256, 256))
    num_players: int = 2
    value_dim: int = 1
    residual: bool = False

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["hidden_sizes"] = list(self.hidden_sizes)
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> NetConfig:
        d = dict(d)
        d["hidden_sizes"] = tuple(d["hidden_sizes"])
        return cls(**d)


class _ResBlock(nn.Module):
    def __init__(self, width: int) -> None:
        super().__init__()
        self.fc1 = nn.Linear(width, width)
        self.fc2 = nn.Linear(width, width)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return x + self.fc2(torch.relu(self.fc1(torch.relu(x))))


class PolicyValueNet(nn.Module):
    def __init__(self, config: NetConfig) -> None:
        super().__init__()
        if not config.hidden_sizes:
            raise ValueError("hidden_sizes must be non-empty")
        self.config = config
        layers: list[nn.Module] = []
        prev = config.input_dim
        for h in config.hidden_sizes:
            layers += [nn.Linear(prev, h), nn.ReLU()]
            if config.residual:
                layers.append(_ResBlock(h))
            prev = h
        self.trunk = nn.Sequential(*layers)
        self.policy_head = nn.Linear(prev, config.num_actions)
        self.value_head = nn.Linear(prev, config.value_dim)

    def forward(self, x: torch.Tensor, mask: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        """Returns (masked logits, value); illegal logits are NEG_INF. Value is tanh-squashed."""
        h = self.trunk(x)
        logits = self.policy_head(h).masked_fill(~mask.bool(), NEG_INF)
        value = torch.tanh(self.value_head(h))
        return logits, value

    @torch.no_grad()
    def act(
        self,
        features: np.ndarray,
        mask: np.ndarray,
        greedy: bool = False,
        rng: random.Random | None = None,
    ) -> int:
        """CPU inference for one state; always returns an action with mask[action] true."""
        legal = np.flatnonzero(mask)
        if legal.size == 0:
            raise ValueError("no legal actions")
        if legal.size == 1:
            return int(legal[0])
        was_training = self.training
        self.eval()
        try:
            x = torch.as_tensor(np.asarray(features, dtype=np.float32)).unsqueeze(0)
            m = torch.as_tensor(np.asarray(mask, dtype=np.bool_)).unsqueeze(0)
            logits, _ = self.forward(x, m)
        finally:
            self.train(was_training)
        if greedy:
            return int(torch.argmax(logits[0]).item())
        probs = torch.softmax(logits[0].double(), dim=0).numpy()
        probs = probs[legal]
        probs = probs / probs.sum()
        r = (rng or random).random()
        idx = int(np.searchsorted(np.cumsum(probs), r, side="right"))
        return int(legal[min(idx, legal.size - 1)])
