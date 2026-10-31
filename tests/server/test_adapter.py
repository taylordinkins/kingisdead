"""Phase 3 unit 1: King is Dead GameAdapter (PLAN.md 5.6)."""

import json
import random

import pyspiel
import pytest

from server.adapters.base import GameAdapter
from server.adapters.kingisdead import KingIsDeadAdapter

KINDS = {"pass", "play", "region", "follower"}
ADAPTER = KingIsDeadAdapter()


def _step(state: pyspiel.State, rng: random.Random) -> None:
    if state.is_chance_node():
        actions, probs = zip(*state.chance_outcomes(), strict=True)
        state.apply_action(rng.choices(actions, weights=probs)[0])
    else:
        state.apply_action(rng.choice(state.legal_actions()))


def _game(n: int) -> pyspiel.Game:
    return ADAPTER.load({"players": n})


def _views_along_game(n: int, seed: int) -> list[tuple[pyspiel.State, dict]]:
    rng = random.Random(seed)
    state = _game(n).new_initial_state()
    out = []
    while not state.is_terminal():
        out.append((state.clone(), ADAPTER.view(state, 0)))
        _step(state, rng)
    out.append((state.clone(), ADAPTER.view(state, 0)))
    return out


def test_is_adapter() -> None:
    assert isinstance(ADAPTER, GameAdapter)


@pytest.mark.parametrize("n", [2, 3])
def test_load_player_count(n: int) -> None:
    assert _game(n).num_players() == n
    assert ADAPTER.view(_game(n).new_initial_state(), 0)["num_players"] == n


@pytest.mark.parametrize("n", [2, 3])
@pytest.mark.parametrize("seed", range(4))
def test_legal_actions_have_metadata_and_view_is_json(n: int, seed: int) -> None:
    for state, view in _views_along_game(n, seed):
        text = json.dumps(view)
        assert json.loads(text) == view
        assert json.dumps(ADAPTER.view(state, 0)) == text  # deterministic
        assert view["is_chance"] == state.is_chance_node()
        assert view["is_terminal"] == state.is_terminal()
        if state.is_chance_node() or state.is_terminal():
            assert view["legal_actions"] == []
            continue
        assert view["current_player"] == state.current_player()
        assert [a["id"] for a in view["legal_actions"]] == state.legal_actions()
        for entry in view["legal_actions"]:
            assert entry["label"]
            assert entry["kind"] in KINDS
            meta = ADAPTER.action_meta(state, entry["id"])
            assert {k: v for k, v in entry.items() if k != "id"} == meta


@pytest.mark.parametrize("n", [2, 3])
@pytest.mark.parametrize("seed", range(4))
def test_terminal_view_has_scoring_and_winners(n: int, seed: int) -> None:
    state, view = _views_along_game(n, seed)[-1]
    assert view["is_terminal"]
    assert view["winners"] == [p for p in range(n) if state.returns()[p] == max(state.returns())]
    assert view["returns"] == state.returns()
    scoring = view["scoring"]
    assert scoring["mode"] in ("invasion", "coronation")
    assert scoring["winners"] == view["winners"]
    assert scoring["steps"]
    assert all("name" in s for s in scoring["steps"])


@pytest.mark.parametrize("n", [2, 3])
@pytest.mark.parametrize("seed", range(3))
def test_replayed_history_gives_identical_view(n: int, seed: int) -> None:
    rng = random.Random(seed)
    state = _game(n).new_initial_state()
    while not state.is_terminal() and len(state.history()) < 80:
        _step(state, rng)
    replay = _game(n).new_initial_state()
    for a in state.history():
        replay.apply_action(a)
    assert json.dumps(ADAPTER.view(replay, 1)) == json.dumps(ADAPTER.view(state, 1))


def test_view_names_match_constants() -> None:
    from kingisdead import constants as C

    view = ADAPTER.view(_game(2).new_initial_state(), 0)
    assert view["faction_names"] == list(C.FACTION_NAMES)
    assert view["card_names"] == {str(c): n for c, n in C.CARD_NAMES.items()}
