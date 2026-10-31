"""Chance outcome range validation and chance action labels."""

import pyspiel
import pytest

import kingisdead.game  # noqa: F401  (registers the game)


def _new():
    return pyspiel.load_game("python_king_is_dead(players=2)").new_initial_state()


def _to_draws():
    s = _new()
    while s.is_chance_node() and len(s.history()) < 8:
        s.apply_action(s.chance_outcomes()[0][0])
    return s


@pytest.mark.parametrize("bad", [8, 9, 100])
def test_region_pick_out_of_range_raises(bad):
    s = _new()
    with pytest.raises(ValueError):
        s.apply_action(bad)


@pytest.mark.parametrize("bad", [3, 5, 7, 100])
def test_draw_out_of_range_raises(bad):
    s = _to_draws()
    assert s.is_chance_node()
    with pytest.raises(ValueError):
        s.apply_action(bad)


def test_action_to_string_never_indexes_out_of_range():
    s = _new()
    with pytest.raises(ValueError):
        s.action_to_string(pyspiel.PlayerId.CHANCE, 99)
    while s.is_chance_node():
        s.apply_action(s.chance_outcomes()[0][0])
    with pytest.raises(ValueError):
        s.action_to_string(pyspiel.PlayerId.CHANCE, 99)
    assert isinstance(s.action_to_string(pyspiel.PlayerId.CHANCE, 2), str)
