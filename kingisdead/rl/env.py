"""Self-play RL environment over the OpenSpiel game. No rule behaviour lives here."""

from __future__ import annotations

import random
from typing import Any

import numpy as np
import numpy.typing as npt
import pyspiel

import kingisdead.game as _game  # registers the game
from kingisdead import actions as act

_ = _game
NUM_ACTIONS: int = act.NUM_DISTINCT_ACTIONS


def load_game(num_players: int) -> Any:
    return pyspiel.load_game(f"python_king_is_dead(players={num_players})")


def features(state: Any, player: int) -> npt.NDArray[np.float32]:
    """Observation tensor from `player`'s perspective (kingisdead/observer.py), as a copy."""
    return np.asarray(state.observation_tensor(player), dtype=np.float32).copy()


def legal_mask(state: Any) -> npt.NDArray[np.bool_]:
    """Boolean mask over the frozen action ids; true exactly for state.legal_actions()."""
    mask = np.zeros(NUM_ACTIONS, dtype=np.bool_)
    if not state.is_terminal() and not state.is_chance_node():
        mask[state.legal_actions()] = True
    return mask


class SelfPlayEnv:
    """All seats are driven by the caller; chance nodes are resolved internally.

    After `reset`/`step`, the env is either at a decision node (`current_player >= 0`) or
    terminal (`done`, `returns` available). Chance outcomes use the env's own seeded RNG.
    """

    def __init__(self, num_players: int = 2) -> None:
        if num_players not in (2, 3):
            raise ValueError(f"num_players must be 2 or 3, got {num_players}")
        self.num_players = num_players
        self.game = load_game(num_players)
        self.num_actions = NUM_ACTIONS
        self.feature_size: int = int(self.game.observation_tensor_size())
        self._rng = random.Random(0)
        self.state: Any = self.game.new_initial_state()

    def reset(self, seed: int) -> None:
        self._rng = random.Random(seed)
        self.state = self.game.new_initial_state()
        self._advance_chance()

    def _advance_chance(self) -> None:
        while self.state.is_chance_node():
            actions, probs = zip(*self.state.chance_outcomes(), strict=True)
            self.state.apply_action(self._rng.choices(actions, weights=probs)[0])

    @property
    def done(self) -> bool:
        return bool(self.state.is_terminal())

    @property
    def current_player(self) -> int:
        return -1 if self.done else int(self.state.current_player())

    def features(self, player: int | None = None) -> npt.NDArray[np.float32]:
        return features(self.state, self.current_player if player is None else player)

    def mask(self) -> npt.NDArray[np.bool_]:
        return legal_mask(self.state)

    def step(self, action: int) -> None:
        if self.done:
            raise RuntimeError("game is over; call reset")
        if not self.mask()[action]:
            raise ValueError(f"illegal action {action}")
        self.state.apply_action(action)
        self._advance_chance()

    def returns(self) -> list[float]:
        if not self.done:
            raise RuntimeError("returns are only available at a terminal state")
        return [float(r) for r in self.state.returns()]
