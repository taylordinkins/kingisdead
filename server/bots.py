"""Bot seats: a registry of seat type -> Bot. Phase 5 registers MCTS/heuristic here."""

from __future__ import annotations

import random
import re
from typing import Protocol

import pyspiel

from kingisdead.bots.heuristic import HeuristicBot
from kingisdead.bots.mcts import MCTSSeatBot
from kingisdead.bots.trained import NAME_RE, TrainedBot, TrainedUnavailable, check_available


class Bot(Protocol):
    def choose(self, state: pyspiel.State, rng: random.Random) -> int:
        """Return a legal action id for the current player of `state`."""
        ...


class RandomBot:
    def choose(self, state: pyspiel.State, rng: random.Random) -> int:
        return rng.choice(state.legal_actions())


BOTS: dict[str, Bot] = {"random": RandomBot(), "heuristic": HeuristicBot()}

HUMAN = "human"
MCTS_DEFAULT_SIMS = 100
MCTS_MAX_SIMS = 100_000
SEAT_TYPE_PATTERN = (
    r"^(human|random|heuristic|mcts(:([1-9][0-9]{0,4}|100000))?|trained:[a-z0-9_-]+)$"
)
_MCTS_RE = re.compile(r"^mcts(?::([1-9][0-9]{0,4}|100000))?$")
_mcts_cache: dict[int, Bot] = {}
_trained_cache: dict[str, Bot] = {}
TRAINED_PREFIX = "trained:"


def _trained_name(seat_type: str) -> str | None:
    if not seat_type.startswith(TRAINED_PREFIX):
        return None
    name = seat_type[len(TRAINED_PREFIX) :]
    return name if NAME_RE.fullmatch(name) else None


def check_seat_available(seat_type: str, num_players: int) -> None:
    """Raise TrainedUnavailable if a `trained:<name>` seat cannot be played (no-op otherwise)."""
    name = _trained_name(seat_type)
    if name is None:
        return
    if num_players != 2:
        raise TrainedUnavailable(f"seat type {seat_type!r} supports 2-player games only")
    check_available(name)


def _mcts_sims(seat_type: str) -> int | None:
    m = _MCTS_RE.match(seat_type)
    if m is None:
        return None
    n = int(m.group(1)) if m.group(1) is not None else MCTS_DEFAULT_SIMS
    return n if 1 <= n <= MCTS_MAX_SIMS else None


def is_valid_seat_type(seat_type: str) -> bool:
    return (
        seat_type == HUMAN
        or seat_type in BOTS
        or _mcts_sims(seat_type) is not None
        or _trained_name(seat_type) is not None
    )


def get_bot(seat_type: str) -> Bot:
    """Resolve a bot seat type (random, heuristic, mcts[:N], trained:<name>) to a Bot."""
    if seat_type in BOTS:
        return BOTS[seat_type]
    tname = _trained_name(seat_type)
    if tname is not None:
        if tname not in _trained_cache:
            _trained_cache[tname] = TrainedBot(tname)
        return _trained_cache[tname]
    n = _mcts_sims(seat_type)
    if n is None:
        raise KeyError(seat_type)
    if n not in _mcts_cache:
        _mcts_cache[n] = MCTSSeatBot(n)
    return _mcts_cache[n]


def bot_rng(seed: int, history_length: int) -> random.Random:
    """Reproducible from (session seed, position in history); distinct from the chance RNG."""
    return random.Random(f"{seed}:bot:{history_length}")
