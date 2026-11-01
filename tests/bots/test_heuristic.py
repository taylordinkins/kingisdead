"""Heuristic bot (Phase 5 unit 1): legality, determinism, strength against RandomBot."""

from __future__ import annotations

import random

import pyspiel
import pytest

import kingisdead.game  # noqa: F401  (registers the game)
from kingisdead.bots.heuristic import HeuristicBot
from server.bots import Bot, RandomBot


def _new(n: int):
    return pyspiel.load_game(f"python_king_is_dead(players={n})").new_initial_state()


def _play(n: int, bots: list[Bot], seed: int, check_legal: bool = False):
    rng = random.Random(seed)
    state = _new(n)
    while not state.is_terminal():
        if state.is_chance_node():
            actions, probs = zip(*state.chance_outcomes(), strict=True)
            state.apply_action(rng.choices(actions, weights=probs)[0])
            continue
        a = bots[state.current_player()].choose(state, rng)
        if check_legal:
            assert a in state.legal_actions()
        state.apply_action(a)
    return state


@pytest.mark.parametrize("n", [2, 3])
def test_always_legal_and_games_complete(n: int) -> None:
    for seed in range(4):
        state = _play(n, [HeuristicBot()] * n, seed, check_legal=True)
        assert state.is_terminal()


def test_deterministic_for_same_state_and_rng() -> None:
    rng = random.Random(5)
    state = _new(2)
    bot = HeuristicBot()
    checked = 0
    while not state.is_terminal():
        if state.is_chance_node():
            actions, probs = zip(*state.chance_outcomes(), strict=True)
            state.apply_action(rng.choices(actions, weights=probs)[0])
            continue
        a1 = bot.choose(state, random.Random(11))
        a2 = bot.choose(state.clone(), random.Random(11))
        assert a1 == a2
        checked += 1
        state.apply_action(a1)
    assert checked > 0


def test_beats_random_bot() -> None:
    games = 50
    score = 0.0
    for g in range(games):
        seat = g % 2
        bots: list[Bot] = [RandomBot(), RandomBot()]
        bots[seat] = HeuristicBot()
        state = _play(2, bots, 100 + g)
        if state.returns()[seat] > 0:
            score += 1
        elif state.returns()[seat] == 0:
            score += 0.5
    assert score / games >= 0.6, score / games
