"""Phase 0 API spike: confirms how OpenSpiel 2.0.2 supports a game written in Python.

Uses the toy game in tests/support/toy_chance_game.py (registered as ``python_kid_toy``), which
is shaped like the future King is Dead game. Findings are written up in
docs/OPENSPIEL_NOTES.md.
"""

from __future__ import annotations

import pickle

import numpy as np
import pyspiel
import pytest
from open_spiel.python.algorithms import generate_playthrough, mcts
from open_spiel.python.observation import make_observation

from tests.support import toy_chance_game as toy

CHANCE = pyspiel.PlayerId.CHANCE
TERMINAL = pyspiel.PlayerId.TERMINAL


def load(players: int | None = None) -> pyspiel.Game:
    name = "python_kid_toy" if players is None else f"python_kid_toy(players={players})"
    return pyspiel.load_game(name)


def play(state: pyspiel.State, actions: list[int]) -> pyspiel.State:
    for action in actions:
        state.apply_action(action)
    return state


def random_playout(
    state: pyspiel.State, rng: np.random.RandomState, bot: mcts.MCTSBot | None = None
) -> pyspiel.State:
    """Plays to the end: chance sampled by probability, players by `bot` or uniformly."""
    while not state.is_terminal():
        if state.is_chance_node():
            actions, probs = zip(*state.chance_outcomes(), strict=True)
            state.apply_action(int(rng.choice(actions, p=probs)))
        elif bot is not None:
            state.apply_action(bot.step(state))
        else:
            state.apply_action(int(rng.choice(state.legal_actions())))
    return state


# -- loading and declared metadata -------------------------------------------------------------


def test_load_by_name_with_params() -> None:
    assert load().num_players() == 2  # default
    assert load(2).num_players() == 2
    assert load(3).num_players() == 3
    assert load(3).get_parameters() == {"players": 3}
    assert str(load(3)) == "python_kid_toy(players=3)"


def test_bad_params_rejected() -> None:
    with pytest.raises(pyspiel.SpielError):
        pyspiel.load_game("python_kid_toy(unknown=1)")
    # load_game does not enforce min/max_num_players for Python games; the game must.
    for bad in (1, 4):
        with pytest.raises(ValueError):
            pyspiel.load_game(f"python_kid_toy(players={bad})")


def test_game_type_fields() -> None:
    t = load().get_type()
    assert t.short_name == "python_kid_toy"
    assert t.dynamics == pyspiel.GameType.Dynamics.SEQUENTIAL
    assert t.chance_mode == pyspiel.GameType.ChanceMode.EXPLICIT_STOCHASTIC
    assert t.information == pyspiel.GameType.Information.PERFECT_INFORMATION
    assert t.utility == pyspiel.GameType.Utility.ZERO_SUM
    assert t.reward_model == pyspiel.GameType.RewardModel.TERMINAL
    assert (t.min_num_players, t.max_num_players) == (2, 3)
    assert t.provides_observation_string and t.provides_observation_tensor
    assert not t.provides_information_state_tensor
    assert t.parameter_specification == {"players": 2}


@pytest.mark.parametrize("n", [2, 3])
def test_game_info_fields(n: int) -> None:
    g = load(n)
    assert g.num_distinct_actions() == 6
    assert g.max_chance_outcomes() == 3
    assert g.num_players() == n
    assert g.min_utility() == pytest.approx(-1.0 / (n - 1))
    assert g.max_utility() == 1.0
    assert g.utility_sum() == 0.0
    assert g.max_game_length() == toy.max_game_length(n) == 4 * n
    assert g.max_chance_nodes_in_history() == 2 * n
    assert g.max_history_length() == 6 * n
    assert g.max_move_number() == 6 * n


# -- the C++ self-test harness -----------------------------------------------------------------


@pytest.mark.parametrize("n", [2, 3])
def test_random_sim_test_with_serialization(n: int) -> None:
    pyspiel.random_sim_test(load(n), num_sims=10, serialize=True, verbose=False)


# -- state behaviour ---------------------------------------------------------------------------


def test_chance_outcomes_are_state_dependent_and_non_uniform() -> None:
    s = load().new_initial_state()
    assert s.is_chance_node() and s.current_player() == CHANCE
    assert s.chance_outcomes() == [(0, 1 / 3), (1, 1 / 3), (2, 1 / 3)]
    s.apply_action(0)
    assert s.chance_outcomes() == [(0, 2 / 8), (1, 3 / 8), (2, 3 / 8)]
    play(s, [0, 0])  # bag is now [0, 3, 3]
    assert s.chance_outcomes() == [(1, 0.5), (2, 0.5)]  # exhausted colour disappears
    assert s.legal_actions(CHANCE) == [1, 2]
    assert s.action_to_string(CHANCE, 1) == "Draw:1"


def test_same_player_decides_twice_in_a_row() -> None:
    s = play(load().new_initial_state(), [0, 1, 0, 1])  # hands: p0 {0,1}, p1 {0,1}
    assert s.current_player() == 0
    assert s.legal_actions() == [0, 1]  # pick a colour held
    s.apply_action(1)
    assert s.current_player() == 0  # same player again
    assert s.legal_actions() == [3, 4, 5]  # pick a target
    s.apply_action(4)
    assert s.current_player() == 1


def test_clone_is_independent() -> None:
    s = play(load(3).new_initial_state(), [0, 1, 2, 0, 1, 2])
    c = s.clone()
    assert str(c) == str(s) and c.history() == s.history()
    play(s, [0, 5])
    assert len(c.history()) == 6 and len(s.history()) == 8
    assert c.current_player() == 0 and c.pending_colour is None
    assert str(c) != str(s)
    play(c, [1, 3])  # advancing the clone does not touch the original either
    assert s.scores == [3, 0, 0] and c.scores == [2, 0, 0]


def test_clone_does_not_share_mutable_lists() -> None:
    s = play(load().new_initial_state(), [0, 1, 0, 1])
    c = s.clone()
    c.apply_action(0)
    c.apply_action(3)
    assert s.hands[0] == [1, 1, 0] and s.scores == [0, 0] and s.pending_colour is None
    assert c.hands[0] == [0, 1, 0] and c.scores == [1, 0]


@pytest.mark.parametrize("n", [2, 3])
def test_serialize_deserialize_round_trip(n: int) -> None:
    g = load(n)
    rng = np.random.RandomState(n)
    s = g.new_initial_state()
    seen_chance = seen_pending = False
    while not s.is_terminal():
        seen_chance |= s.is_chance_node()
        seen_pending |= s.pending_colour is not None
        text = pyspiel.serialize_game_and_state(g, s)
        g2, s2 = pyspiel.deserialize_game_and_state(text)
        assert str(g2) == str(g) and str(s2) == str(s) and s2.history() == s.history()
        assert s2.current_player() == s.current_player()
        assert pickle.loads(pickle.dumps(s)).history() == s.history()
        if s.is_chance_node():
            actions, probs = zip(*s.chance_outcomes(), strict=True)
            a = int(rng.choice(actions, p=probs))
        else:
            a = int(rng.choice(s.legal_actions()))
        s.apply_action(a)
        s2.apply_action(a)  # a deserialized state keeps playing identically
        assert str(s2) == str(s)
    assert seen_chance and seen_pending
    assert s2.returns() == s.returns()
    assert pickle.loads(pickle.dumps(g)).num_players() == n


def test_state_serialize_is_history_plus_pickled_dict() -> None:
    s = play(load().new_initial_state(), [0, 1])
    text = s.serialize()
    assert text.startswith("history=-1:0,-1:1\nmove_number=2\n")
    assert "__dict__=" in text  # Python attributes are pickled, so they must be picklable


# -- observations ------------------------------------------------------------------------------


@pytest.mark.parametrize("n", [2, 3])
def test_observation_tensor_shape_constant(n: int) -> None:
    g = load(n)
    obs = make_observation(g)
    assert obs.tensor is not None
    size = toy.observation_size(n)
    assert g.observation_tensor_size() == size and g.observation_tensor_shape() == [size]
    rng = np.random.RandomState(0)
    s = g.new_initial_state()
    while True:
        for p in range(n):
            obs.set_from(s, p)
            assert obs.tensor.shape == (size,) and obs.tensor.dtype == np.float32
            assert len(s.observation_tensor(p)) == size
            assert isinstance(s.observation_string(p), str)
            assert obs.string_from(s, p) == s.observation_string(p)
        if s.is_terminal():
            break
        random_playout_step(s, rng)


def random_playout_step(s: pyspiel.State, rng: np.random.RandomState) -> None:
    if s.is_chance_node():
        actions, probs = zip(*s.chance_outcomes(), strict=True)
        s.apply_action(int(rng.choice(actions, p=probs)))
    else:
        s.apply_action(int(rng.choice(s.legal_actions())))


def test_observation_content_is_relative_to_observer() -> None:
    g = load(3)
    s = play(g.new_initial_state(), [0, 0, 1, 1, 2, 2, 0])  # p0 picks colour 0
    obs = make_observation(g)
    obs.set_from(s, 0)
    assert obs.dict["hands"].tolist() == [[2, 0, 0], [0, 2, 0], [0, 0, 2]]
    assert obs.dict["to_move"].tolist() == [1, 0, 0]
    assert obs.dict["pending"].tolist() == [1, 0, 0]
    obs.set_from(s, 1)
    assert obs.dict["to_move"].tolist() == [0, 0, 1]  # seat 0 is "previous" from seat 1's view
    assert obs.dict["hands"].tolist() == [[0, 2, 0], [0, 0, 2], [2, 0, 0]]  # own seat first


# -- playthrough generation --------------------------------------------------------------------


@pytest.mark.parametrize("n", [2, 3])
def test_playthrough_generation(n: int) -> None:
    text = generate_playthrough.playthrough(f"python_kid_toy(players={n})", [], seed=7)
    assert text.startswith(f"game: python_kid_toy(players={n})")
    assert "ChanceOutcomes() = " in text
    assert "ObservationTensor(0).hands" in text
    assert "Returns() = " in text
    assert f"MaxGameLength() = {4 * n}" in text
    # deterministic given the same seed
    again = generate_playthrough.playthrough(f"python_kid_toy(players={n})", [], seed=7)
    assert again == text


# -- outcome and returns -----------------------------------------------------------------------


def test_returns_are_zero_before_terminal() -> None:
    s = play(load(3).new_initial_state(), [0, 1, 2])
    assert s.returns() == [0.0, 0.0, 0.0]
    assert s.rewards() == [0.0, 0.0, 0.0]


def test_shared_win_two_players_tie() -> None:
    # p0 and p1 both hold colours {0, 1} and play identically -> both win, k = n = 2.
    s = play(load(2).new_initial_state(), [0, 1, 0, 1])
    play(s, [0, 3, 0, 3, 1, 3, 1, 3])  # (pick, target) pairs: p0, p1, p0, p1
    assert s.is_terminal() and s.current_player() == TERMINAL
    assert s.returns() == [0.0, 0.0]


def test_shared_win_two_of_three() -> None:
    s = play(load(3).new_initial_state(), [0, 1, 0, 1, 0, 1])  # every hand is {0, 1}
    play(s, [0, 4, 0, 4, 0, 3])  # round 1: p0 t1 (2), p1 t1 (2), p2 t0 (1)
    play(s, [1, 4, 1, 4, 1, 3])  # round 2: p0 +4, p1 +4, p2 +2
    assert s.is_terminal() and s.scores == [6, 6, 3]
    assert s.returns() == [0.25, 0.25, -0.5]  # (3-2)/(2*2), -1/2
    assert sum(s.returns()) == 0.0


def test_sole_winner_and_three_way_tie() -> None:
    n = 3
    sole = play(load(n).new_initial_state(), [0, 1, 0, 1, 0, 1])
    play(sole, [0, 5, 0, 4, 0, 3, 1, 5, 1, 4, 1, 3])
    assert sole.returns() == [1.0, -0.5, -0.5]
    assert sole.rewards() == sole.returns()  # default rewards() mirror returns() at terminal
    tie = play(load(n).new_initial_state(), [0, 1, 0, 1, 0, 1])
    play(tie, [0, 3, 0, 3, 0, 3, 1, 3, 1, 3, 1, 3])
    assert tie.returns() == [0.0, 0.0, 0.0]  # k = n -> (n-k)/... = 0


@pytest.mark.parametrize("n", [2, 3])
def test_returns_sum_to_zero_and_game_length_matches(n: int) -> None:
    g = load(n)
    rng = np.random.RandomState(100 + n)
    for _ in range(30):
        s = random_playout(g.new_initial_state(), rng)
        returns = s.returns()
        assert sum(returns) == pytest.approx(0.0)
        assert all(g.min_utility() <= r <= g.max_utility() for r in returns)
        assert len(s.history()) == g.max_history_length()  # exact for this toy game
        assert len(s.history()) - 2 * n == g.max_game_length()  # chance draws not counted


# -- MCTSBot -----------------------------------------------------------------------------------


@pytest.mark.parametrize("n", [2, 3])
def test_mcts_bot_plays_complete_games(n: int) -> None:
    g = load(n)
    rng = np.random.RandomState(n)
    evaluator = mcts.RandomRolloutEvaluator(n_rollouts=1, random_state=rng)
    bot = mcts.MCTSBot(g, uct_c=2.0, max_simulations=15, evaluator=evaluator, random_state=rng)
    for _ in range(2):
        s = g.new_initial_state()
        movers: list[int] = []
        while not s.is_terminal():
            if s.is_chance_node():
                # step() on a chance node is a no-op returning INVALID_ACTION
                assert bot.step(s) == pyspiel.INVALID_ACTION
            else:
                movers.append(s.current_player())
            random_playout_step_with_bot(s, bot, rng)
        assert len(s.history()) == g.max_history_length()
        assert sum(s.returns()) == pytest.approx(0.0)
        # Consecutive same-player decisions (pick, target) were each searched by the bot.
        assert len(movers) == 2 * n * toy.TOKENS_PER_PLAYER
        assert all(movers[i] == movers[i + 1] for i in range(0, len(movers), 2))


def random_playout_step_with_bot(
    s: pyspiel.State, bot: mcts.MCTSBot, rng: np.random.RandomState
) -> None:
    if s.is_chance_node():
        actions, probs = zip(*s.chance_outcomes(), strict=True)
        s.apply_action(int(rng.choice(actions, p=probs)))
    else:
        action = bot.step(s)
        assert action in s.legal_actions()
        s.apply_action(action)


def test_mcts_bot_finds_the_winning_target() -> None:
    """Final decision of the game: only target 2 beats p0; a small search must find it."""
    g = load(2)
    s = play(g.new_initial_state(), [0, 1, 0, 1])
    play(s, [0, 3, 0, 3, 1, 4, 1])  # scores 1, 1, +4 -> 5 vs 1; p1 holds a pending colour-1 pick
    assert s.current_player() == 1 and s.legal_actions() == [3, 4, 5]
    rng = np.random.RandomState(0)
    bot = mcts.MCTSBot(
        g,
        uct_c=2.0,
        max_simulations=30,
        evaluator=mcts.RandomRolloutEvaluator(1, rng),
        random_state=rng,
    )
    assert bot.step(s) == 5  # 1 + 2*3 = 7 > 5; target 1 would tie, target 0 would lose
