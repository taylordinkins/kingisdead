"""MCTS seat bot (Phase 5 unit 2): legality, determinism, no state mutation."""

from __future__ import annotations

import random

import pyspiel
import pytest

import kingisdead.game  # noqa: F401  (registers the game)
from kingisdead.bots.mcts import MCTSSeatBot
from server.bots import RandomBot


def _midgame(n: int, seed: int, plies: int):
    state = pyspiel.load_game(f"python_king_is_dead(players={n})").new_initial_state()
    rng = random.Random(seed)
    rb = RandomBot()
    for _ in range(plies):
        if state.is_terminal():
            break
        if state.is_chance_node():
            outcomes, probs = zip(*state.chance_outcomes(), strict=True)
            state.apply_action(rng.choices(outcomes, probs)[0])
        else:
            state.apply_action(rb.choose(state, rng))
    while state.is_chance_node():
        state.apply_action(state.chance_outcomes()[0][0])
    return state


@pytest.mark.parametrize("n", [2, 3])
@pytest.mark.parametrize("seed", [1, 2, 3])
def test_mcts_returns_legal_actions(n: int, seed: int) -> None:
    bot = MCTSSeatBot(10)
    rng = random.Random(seed)
    state = _midgame(n, seed, 40)
    for _ in range(6):
        if state.is_terminal():
            break
        if state.is_chance_node():
            state.apply_action(state.chance_outcomes()[0][0])
            continue
        a = bot.choose(state, rng)
        assert a in state.legal_actions()
        state.apply_action(a)


def test_mcts_deterministic_and_does_not_mutate() -> None:
    state = _midgame(2, 5, 50)
    before = (str(state), state.history(), state.legal_actions())
    bot = MCTSSeatBot(20)
    a1 = bot.choose(state, random.Random(7))
    a2 = MCTSSeatBot(20).choose(state, random.Random(7))
    assert a1 == a2
    assert (str(state), state.history(), state.legal_actions()) == before


def test_single_legal_action_skips_search() -> None:
    state = _midgame(2, 1, 0)
    while not state.is_terminal() and len(state.legal_actions()) != 1:
        if state.is_chance_node():
            state.apply_action(state.chance_outcomes()[0][0])
        else:
            state.apply_action(state.legal_actions()[0])
    if state.is_terminal():
        pytest.skip("no single-action state reached")
    assert MCTSSeatBot(1).choose(state, random.Random(0)) == state.legal_actions()[0]
