"""Bot seats: a registry of seat type -> Bot. Phase 5 registers MCTS/heuristic here."""

from __future__ import annotations

import random
from typing import Protocol

import pyspiel


class Bot(Protocol):
    def choose(self, state: pyspiel.State, rng: random.Random) -> int:
        """Return a legal action id for the current player of `state`."""
        ...


class RandomBot:
    def choose(self, state: pyspiel.State, rng: random.Random) -> int:
        return rng.choice(state.legal_actions())


BOTS: dict[str, Bot] = {"random": RandomBot()}

HUMAN = "human"


def is_valid_seat_type(seat_type: str) -> bool:
    return seat_type == HUMAN or seat_type in BOTS


def bot_rng(seed: int, history_length: int) -> random.Random:
    """Reproducible from (session seed, position in history); distinct from the chance RNG."""
    return random.Random(f"{seed}:bot:{history_length}")
