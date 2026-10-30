"""Environment smoke tests: OpenSpiel imports and the package is on the path."""

import pyspiel

import kingisdead


def test_openspiel_runs_a_builtin_game() -> None:
    game = pyspiel.load_game("tic_tac_toe")
    state = game.new_initial_state()
    assert not state.is_terminal()
    assert len(state.legal_actions()) == 9


def test_package_importable() -> None:
    assert kingisdead.__version__
