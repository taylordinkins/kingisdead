"""Phase 4 unit 1: scenario-backed sessions."""

import json
import random
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from server.app import create_app

Json = dict[str, Any]
SCEN = Path(__file__).parent.parent / "scenarios"


def _scenario(name: str) -> Json:
    return json.loads((SCEN / name).read_text())


def _client() -> TestClient:
    return TestClient(create_app(dev_mode=True))


def _create(c: TestClient, scenario: Json, **extra: Any) -> Json:
    n = scenario["players"]
    r = c.post(
        "/api/games", json={"seats": ["human"] * n, "seed": 4, "scenario": scenario, **extra}
    )
    assert r.status_code == 200, r.text
    return r.json()


def _step(c: TestClient, g: Json, rng: random.Random, n: int) -> Json:
    for _ in range(n):
        if g["is_terminal"]:
            break
        a = rng.choice(g["legal_actions"])["id"]
        r = c.post(f"/api/games/{g['id']}/actions", json={"action": a})
        assert r.status_code == 200, r.text
        g = r.json()
    return g


def _no_id(g: Json) -> Json:
    return {k: v for k, v in g.items() if k != "id"}


def test_setup_scenario_back_rewind() -> None:
    c = _client()
    g0 = _create(c, _scenario("setup_basic.json"))
    g = _step(c, g0, random.Random(1), 5)
    assert g["history_length"] > g0["history_length"]
    gid = g["id"]
    b = c.post(f"/api/games/{gid}/back")
    assert b.status_code == 200, b.text
    assert b.json()["history_length"] < g["history_length"]
    assert g["history_length"] >= 5
    rw = c.post(f"/api/games/{gid}/rewind", json={"player_actions": 0})
    assert rw.status_code == 200, rw.text
    assert rw.json()["view"] == g0["view"]


def test_state_scenario_play_and_roundtrip() -> None:
    c = _client()
    sc = _scenario("undo_block_outmanoeuvre.json")
    g = _create(c, sc)
    g = _step(c, g, random.Random(2), 6)
    exp = c.get(f"/api/games/{g['id']}/export").json()
    assert exp["scenario"] == sc
    r = c.post("/api/games/import", json=exp)
    assert r.status_code == 200, r.text
    assert _no_id(r.json()) == _no_id(c.get(f"/api/games/{g['id']}").json())
    rw = c.post(f"/api/games/{r.json()['id']}/rewind", json={"player_actions": 0})
    assert rw.status_code == 200, rw.text
    assert rw.json()["history_length"] == _create(c, sc)["history_length"]


def test_report_carries_scenario(tmp_path: Path) -> None:
    c = TestClient(create_app(reports_dir=tmp_path))
    sc = _scenario("undo_block_outmanoeuvre.json")
    g = _create(c, sc)
    out = c.post(f"/api/games/{g['id']}/report", json={"note": "x"}).json()
    assert json.loads(Path(out["path"]).read_text())["export"]["scenario"] == sc


def test_invalid_scenario_422() -> None:
    c = _client()
    sc = _scenario("setup_basic.json")
    sc["format"] = 2
    r = c.post("/api/games", json={"seats": ["human"] * 2, "scenario": sc})
    assert r.status_code == 422
    assert "format" in r.json()["detail"]


def test_num_players_mismatch_422() -> None:
    c = _client()
    sc = _scenario("setup_basic.json")
    r = c.post(
        "/api/games",
        json={"seats": ["human"] * 3, "params": {"num_players": 3 - 1 if sc["players"] == 3 else 3},
              "scenario": sc},
    )  # fmt: skip
    assert r.status_code == 422
