"""Phase 3 unit 3: HTTP API."""

import random
from typing import Any

import pytest
from fastapi.testclient import TestClient

from server.app import create_app

Json = dict[str, Any]


def _client(dev: bool = False) -> TestClient:
    return TestClient(create_app(dev_mode=dev))


def _new(c: TestClient, n: int = 2, seed: int = 3) -> Json:
    r = c.post(
        "/api/games",
        json={"game": "king_is_dead", "params": {"num_players": n},
              "seats": ["human"] * n, "seed": seed},
    )  # fmt: skip
    assert r.status_code == 200, r.text
    return r.json()


def _play(c: TestClient, g: Json, rng: random.Random, steps: int | None = None) -> Json:
    while not g["view"]["is_terminal"] and steps != 0:
        legal = g["view"]["legal_actions"]
        r = c.post(f"/api/games/{g['id']}/actions", json={"action": rng.choice(legal)["id"]})
        assert r.status_code == 200, r.text
        g = r.json()
        steps = None if steps is None else steps - 1
    return g


@pytest.mark.parametrize("n", [2, 3])
def test_full_game_through_api(n: int) -> None:
    c = _client()
    g = _play(c, _new(c, n), random.Random(n))
    assert g["view"]["is_terminal"]
    assert g["history_length"] > 0
    assert g["seat_types"] == ["human"] * n
    assert len(g["view"]["returns"]) == n


def test_export_import_round_trip() -> None:
    c = _client()
    g = _play(c, _new(c, 3, seed=9), random.Random(1), steps=40)
    exp = c.get(f"/api/games/{g['id']}/export").json()
    assert set(exp) == {"game", "params", "seats", "seed", "history"}
    r = c.post("/api/games/import", json=exp)
    assert r.status_code == 200, r.text
    g2 = r.json()
    assert g2["id"] != g["id"]
    assert g2["view"] == g["view"]
    assert g2["history_length"] == g["history_length"]


def test_import_invalid_history_rejected() -> None:
    c = _client()
    exp = c.get(f"/api/games/{_new(c)['id']}/export").json()
    exp["history"] = [*exp["history"], 10**6]
    r = c.post("/api/games/import", json=exp)
    assert r.status_code == 400
    assert "invalid history" in r.json()["detail"]


def test_illegal_action_409_and_unchanged() -> None:
    c = _client()
    g = _new(c)
    r = c.post(f"/api/games/{g['id']}/actions", json={"action": 10**6})
    assert r.status_code == 409
    after = c.get(f"/api/games/{g['id']}").json()
    assert after["history_length"] == g["history_length"]
    assert after["view"] == g["view"]


def test_unknown_id_404() -> None:
    c = _client()
    assert c.get("/api/games/nope").status_code == 404
    assert c.post("/api/games/nope/actions", json={"action": 0}).status_code == 404
    assert c.get("/api/games/nope/export").status_code == 404


@pytest.mark.parametrize(
    "body",
    [
        {"seats": ["human"], "params": {"num_players": 2}},
        {"seats": ["human", "human"], "params": {"num_players": 3}},
        {"seats": ["human", "alien"]},
        {"game": "chess", "seats": ["human", "human"]},
        {"seats": ["human", "human"], "params": {"num_players": 9}},
    ],
)
def test_bad_create_4xx(body: Json) -> None:
    r = _client().post("/api/games", json=body)
    assert 400 <= r.status_code < 500


def test_random_seats_accepted_and_seat_view() -> None:
    c = _client()
    r = c.post("/api/games", json={"seats": ["human", "random"], "seed": 1})
    assert r.status_code == 200
    g = r.json()
    assert g["seat_types"] == ["human", "random"]
    assert c.get(f"/api/games/{g['id']}?seat=1").json()["seat"] == 1
    assert c.get(f"/api/games/{g['id']}?seat=5").status_code == 422


def test_back() -> None:
    c = _client()
    g = _new(c)
    assert c.post(f"/api/games/{g['id']}/back").status_code == 409
    g = _play(c, g, random.Random(2), steps=3)
    r = c.post(f"/api/games/{g['id']}/back")
    assert r.status_code == 200
    assert r.json()["history_length"] < g["history_length"]


def test_rewind_requires_dev_mode() -> None:
    c = _client()
    g = _play(c, _new(c), random.Random(2), steps=3)
    assert c.post(f"/api/games/{g['id']}/rewind", json={"player_actions": 0}).status_code == 403

    d = _client(dev=True)
    g = _play(d, _new(d), random.Random(2), steps=5)
    r = d.post(f"/api/games/{g['id']}/rewind", json={"player_actions": 1})
    assert r.status_code == 200
    assert r.json()["history_length"] < g["history_length"]
    assert d.post(f"/api/games/{g['id']}/rewind", json={"player_actions": 999}).status_code == 400


def test_openapi_operation_ids() -> None:
    schema = _client().app.openapi()  # pyright: ignore[reportUnknownMemberType,reportAttributeAccessIssue]
    ids = {op["operationId"] for p in schema["paths"].values() for op in p.values()}
    assert ids >= {
        "create_game", "import_game", "get_game", "post_action", "go_back",
        "rewind_game", "export_game",
    }  # fmt: skip
