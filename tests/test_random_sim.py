"""Phase 2 unit 12: OpenSpiel conformance and random-simulation invariants.

The fast tests run ``pyspiel.random_sim_test`` (with serialization) over the registered game.
The slow test plays 10,000 random games (2 and 3 players, fixed seeds), checks the invariant
checker (tests/support/invariants.py) after every move, and asserts every game terminates within
the declared bounds.
"""

import random

import pyspiel
import pytest

from tests.support.invariants import check_invariants

GAME = "python_king_is_dead"


def _load(n: int):
    import kingisdead.game  # noqa: F401  (registers the game)

    return pyspiel.load_game(f"{GAME}(players={n})")


@pytest.mark.parametrize("n", [2, 3])
def test_random_sim_test_with_serialization(n: int) -> None:
    """Unit 12 exit criterion: random_sim_test passes (serialize=True) for 2 and 3 players."""
    pyspiel.random_sim_test(_load(n), num_sims=50, serialize=True, verbose=False)


def _sample_chance(state, rng: random.Random) -> int:
    actions, probs = zip(*state.chance_outcomes(), strict=True)
    return rng.choices(actions, weights=probs)[0]


def _play_random(game, rng: random.Random):
    state = game.new_initial_state()
    check_invariants(state)
    decisions = 0
    max_len = game.max_game_length()
    max_hist = game.max_history_length()
    while not state.is_terminal():
        if state.is_chance_node():
            state.apply_action(_sample_chance(state, rng))
        else:
            legal = state.legal_actions()
            assert legal, "non-terminal decision node with no legal actions"
            state.apply_action(rng.choice(legal))
            decisions += 1
        check_invariants(state)
        assert decisions <= max_len, "exceeded max_game_length (non-terminating?)"
        assert len(state.history()) <= max_hist
    assert state.legal_actions() == []
    return state


@pytest.mark.slow
@pytest.mark.parametrize("n", [2, 3])
def test_10000_random_games_zero_invariant_violations(n: int) -> None:
    """Unit 12 exit: 5,000 games per player count (10,000 total), no invariant violation,
    every game terminates with zero-sum returns."""
    game = _load(n)
    for seed in range(5000):
        rng = random.Random(1000 * n + seed)
        state = _play_random(game, rng)
        returns = state.returns()
        assert abs(sum(returns)) < 1e-9, f"seed {seed}: returns not zero-sum {returns}"
