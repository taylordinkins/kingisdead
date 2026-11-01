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


def _terminal_state(n: int, seed: int) -> pyspiel.State:
    rng = random.Random(seed)
    state = _game(n).new_initial_state()
    while not state.is_terminal():
        _step(state, rng)
    return state


@pytest.mark.parametrize("n", [2, 3])
@pytest.mark.parametrize("seed", range(12))
def test_last_scoring_step_matches_winners(n: int, seed: int) -> None:
    state = _terminal_state(n, seed)
    scoring = ADAPTER.view(state, 0)["scoring"]
    last = [s for s in scoring["steps"] if not s.get("skipped")][-1]
    assert last["remaining"] == scoring["winners"] == state.winners()


def _coronation_state(n: int) -> pyspiel.State:
    for seed in range(200):
        state = _terminal_state(n, seed)
        if ADAPTER.view(state, 0)["scoring"]["mode"] == "coronation":
            return state
    pytest.skip("no coronation playout found")


def test_scoring_rank2_undefined_is_skipped() -> None:
    state = _coronation_state(2)
    # Built position: faction 0 controls every region, so ranks 2 and 3 are undefined (R-403).
    state.region_states = [1] * 8
    state.region_control = [0] * 8
    state.recent_win = [8, -1, -1]
    # Players tie on faction-0 followers; rank-2 counts (faction 1) would favour player 0 if used.
    state.courts = [[2, 5, 3], [2, 1, 0]]
    state.hand_empty = [9, 4]
    scoring = ADAPTER.view(state, 0)["scoring"]
    assert scoring["faction_ranking"] == [0, None, None]
    steps = {s["name"]: s for s in scoring["steps"]}
    assert len(steps["rank_1_followers"]["tied_before"]) == 2
    assert steps["rank_1_followers"]["remaining"] == [0, 1]
    assert steps["rank_2_followers"] == {
        "name": "rank_2_followers",
        "faction": None,
        "skipped": True,
    }
    assert steps["hand_emptied"]["remaining"] == [1]
    assert scoring["winners"] == state.winners() == [1]


def test_scoring_nobody_emptied_hand_shares_win() -> None:
    state = _coronation_state(2)
    state.region_states = [1] * 8
    state.region_control = [0, 0, 0, 0, 1, 1, 1, 1]
    state.recent_win = [7, 8, -1]
    state.courts = [[2, 1, 0], [2, 1, 0]]  # tie on rank 1 and rank 2 followers
    state.hand_empty = [None, None]
    scoring = ADAPTER.view(state, 0)["scoring"]
    last = scoring["steps"][-1]
    assert last["name"] == "hand_emptied"
    assert last["remaining"] == scoring["winners"] == [0, 1]
    assert state.winners() == [0, 1]


def test_chance_labels_are_meaningful() -> None:
    state = _game(2).new_initial_state()
    rng = random.Random(1)
    labels = []
    while state.is_chance_node():
        a = state.chance_outcomes()[0][0]
        labels.append(ADAPTER.chance_label(state, a))
        state.apply_action(a)
        rng.random()
    assert labels[0].startswith("Setup: region card ")
    assert any("court draws" in lb for lb in labels)
    assert any("follower placed in" in lb for lb in labels)
    assert not any(lb.startswith("Chance outcome") for lb in labels)


def test_neg_first_absent_during_swap_phase() -> None:
    from kingisdead import constants as C
    from kingisdead.scenario import load_scenario

    state = load_scenario("tests/scenarios/undo_block_outmanoeuvre.json")
    state.apply_action(7)
    assert state.phase == C.PHASE_SWAP
    state.neg_first = 3  # stale value left over from an earlier Negotiate
    assert ADAPTER.view(state, 0)["pending"]["neg_first"] is None
