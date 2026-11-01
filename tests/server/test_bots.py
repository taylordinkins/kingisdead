"""Phase 3 unit 4: bot seats and server-side auto-advance."""

import random
from typing import Any

import pytest
from fastapi.testclient import TestClient

from server.adapters.kingisdead import KingIsDeadAdapter
from server.app import create_app
from server.sessions import SessionError, SessionStore

Json = dict[str, Any]


def _client(dev: bool = False) -> TestClient:
    return TestClient(create_app(dev_mode=dev))


def _create(c: TestClient, seats: list[str], seed: int) -> Json:
    r = c.post(
        "/api/games",
        json={"params": {"num_players": len(seats)}, "seats": seats, "seed": seed},
    )
    assert r.status_code == 200, r.text
    return r.json()


def _play_human(c: TestClient, g: Json, pick: int, steps: int | None = None) -> Json:
    rng = random.Random(pick)
    while not g["view"]["is_terminal"] and steps != 0:
        assert not g["bot_thinking"]
        assert g["seat_types"][g["seat"]] == "human"
        a = rng.choice(g["view"]["legal_actions"])["id"]
        r = c.post(f"/api/games/{g['id']}/actions", json={"action": a})
        assert r.status_code == 200, r.text
        g = r.json()
        steps = None if steps is None else steps - 1
    return g


def _history(c: TestClient, g: Json) -> list[int]:
    return c.get(f"/api/games/{g['id']}/export").json()["history"]


@pytest.mark.parametrize("n", [2, 3])
@pytest.mark.parametrize("seed", [1, 2, 3])
def test_all_random_game_finishes_on_create(n: int, seed: int) -> None:
    g = _create(_client(), ["random"] * n, seed)
    assert g["view"]["is_terminal"]
    assert g["seat_types"] == ["random"] * n
    assert not g["bot_thinking"]


@pytest.mark.parametrize("seats", [["human", "random"], ["random", "human", "random"]])
@pytest.mark.parametrize("seed", [1, 2, 3])
def test_human_vs_random_reaches_terminal(seats: list[str], seed: int) -> None:
    c = _client()
    g = _play_human(c, _create(c, seats, seed), seed)
    assert g["view"]["is_terminal"]
    assert len(g["view"]["returns"]) == len(seats)
    assert g["history_length"] > 0


def test_bot_replies_are_in_history_and_human_to_move() -> None:
    c = _client()
    g = _create(c, ["human", "random"], 4)
    rng = random.Random(0)
    jumps = []
    for _ in range(10):
        n0 = g["history_length"]
        a = rng.choice(g["view"]["legal_actions"])["id"]
        g = c.post(f"/api/games/{g['id']}/actions", json={"action": a}).json()
        jumps.append(g["history_length"] - n0)
        assert g["view"]["is_terminal"] or g["seat_types"][g["seat"]] == "human"
    assert max(jumps) >= 2  # some human action ended the turn and the bot replied


def test_bot_goes_first_is_advanced_on_create() -> None:
    c = _client()
    g = _create(c, ["random", "human"], 5)
    assert g["seat"] == 1 and not g["bot_thinking"]


def test_same_seed_same_choices_identical_history() -> None:
    c = _client()
    seats = ["human", "random", "random"]
    h1 = _history(c, _play_human(c, _create(c, seats, 7), 3))
    h2 = _history(c, _play_human(c, _create(c, seats, 7), 3))
    assert h1 == h2
    assert _history(c, _play_human(c, _create(c, seats, 8), 3)) != h1


def test_export_import_round_trip_with_bots() -> None:
    c = _client()
    g = _play_human(c, _create(c, ["human", "random"], 6), 2, steps=6)
    exp = c.get(f"/api/games/{g['id']}/export").json()
    g2 = c.post("/api/games/import", json=exp).json()
    assert g2["history_length"] == g["history_length"]
    assert g2["view"] == g["view"]
    assert c.get(f"/api/games/{g2['id']}/export").json() == exp


def test_import_all_bot_game_and_tampered_history() -> None:
    c = _client()
    g = _create(c, ["random", "random"], 9)
    exp = c.get(f"/api/games/{g['id']}/export").json()
    assert c.post("/api/games/import", json=exp).json()["view"]["is_terminal"]
    exp["history"][-1] = 10**6
    assert c.post("/api/games/import", json=exp).status_code == 400


def test_back_with_bot_lands_at_human_turn_start() -> None:
    c = _client()
    g = _play_human(c, _create(c, ["human", "random"], 3), 1, steps=4)
    full = _history(c, g)
    r = c.post(f"/api/games/{g['id']}/back")
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["history_length"] < g["history_length"]
    assert b["seat_types"][b["seat"]] == "human" and not b["bot_thinking"]
    h = _history(c, b)
    assert h == full[: len(h)]
    # replaying the same human action reproduces the same continuation (bots deterministic)
    again = c.post(f"/api/games/{b['id']}/actions", json={"action": full[len(h)]}).json()
    h2 = _history(c, again)
    assert h2 == full[: len(h2)]


def test_rewind_with_bot_keeps_human_to_move() -> None:
    c = _client(dev=True)
    g = _play_human(c, _create(c, ["human", "random"], 3), 1, steps=4)
    r = c.post(f"/api/games/{g['id']}/rewind", json={"player_actions": 2})
    assert r.status_code == 200, r.text
    assert not r.json()["bot_thinking"]


def test_unknown_seat_type_rejected() -> None:
    c = _client()
    r = c.post("/api/games", json={"params": {"num_players": 2}, "seats": ["human", "alien"]})
    assert r.status_code == 422


def test_unknown_seat_type_rejected_by_session() -> None:
    a = KingIsDeadAdapter()
    with pytest.raises(SessionError):
        SessionStore({a.name: a}).create(a.name, {"players": 2}, ["human", "alien"], 1)


def test_hotseat_unchanged() -> None:
    c = _client()
    g = _create(c, ["human", "human"], 2)
    assert not g["bot_thinking"]
    before = g["history_length"]
    legal = g["view"]["legal_actions"][0]["id"]
    g = c.post(f"/api/games/{g['id']}/actions", json={"action": legal}).json()
    assert g["history_length"] >= before + 1
    assert g["seat_types"] == ["human", "human"]


# --- Phase 5 unit 2: heuristic / mcts seat types ---


@pytest.mark.parametrize(
    "t",
    ["human", "random", "heuristic", "mcts", "mcts:1", "mcts:50", "mcts:100000"],
)
def test_valid_seat_types(t: str) -> None:
    from server.bots import is_valid_seat_type

    assert is_valid_seat_type(t)


@pytest.mark.parametrize(
    "t",
    [
        "mcts:0",
        "mcts:x",
        "mcts:",
        "mcts:-5",
        "mcts:1.5",
        "mcts:100001",
        "mcts:99999999999",
        "mcts:000000",
        "MCTS",
        "alien",
        "",
        "mcts:5 ",
    ],
)
def test_invalid_seat_types(t: str) -> None:
    from server.bots import is_valid_seat_type

    assert not is_valid_seat_type(t)


def test_get_bot_caches_mcts_per_n() -> None:
    from server.bots import get_bot

    assert get_bot("mcts:7") is get_bot("mcts:7")
    assert get_bot("mcts:7") is not get_bot("mcts:8")
    assert get_bot("mcts") is get_bot("mcts:100")
    with pytest.raises(KeyError):
        get_bot("mcts:0")


def test_api_rejects_bad_mcts_seat_with_422() -> None:
    c = _client()
    for t in ["mcts:0", "mcts:x", "mcts:100001"]:
        r = c.post("/api/games", json={"seats": ["human", t], "seed": 1})
        assert r.status_code == 422, t
    r = c.post("/api/games", json={"seats": ["human", "mcts:5"], "seed": 1})
    assert r.status_code == 200


def test_session_with_heuristic_and_mcts_seats_advances() -> None:
    c = _client()
    g = _create(c, ["human", "heuristic", "mcts:5"], 3)
    assert g["seat_types"] == ["human", "heuristic", "mcts:5"]
    g = _play_human(c, g, pick=1, steps=8)
    assert g["view"]["is_terminal"] or (
        not g["bot_thinking"] and g["seat_types"][g["seat"]] == "human"
    )


def test_heuristic_only_game_finishes_and_replays() -> None:
    c = _client()
    g = _create(c, ["human", "heuristic"], 2)
    g = _play_human(c, g, pick=2)
    assert g["view"]["is_terminal"]
