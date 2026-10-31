"""Phase 3 unit 5: report endpoint."""

import json
from pathlib import Path

from fastapi.testclient import TestClient

from server.app import create_app


def _setup(tmp_path: Path) -> tuple[TestClient, dict]:
    c = TestClient(create_app(reports_dir=tmp_path / "reports"))
    g = c.post(
        "/api/games",
        json={"params": {"num_players": 2}, "seats": ["human", "human"], "seed": 5},
    ).json()
    a = g["view"]["legal_actions"][0]["id"]
    g = c.post(f"/api/games/{g['id']}/actions", json={"action": a}).json()
    return c, g


def test_report_written(tmp_path: Path) -> None:
    c, g = _setup(tmp_path)
    r = c.post(f"/api/games/{g['id']}/report", json={"note": "bad move", "category": "engine"})
    assert r.status_code == 200, r.text
    out = r.json()
    path = Path(out["path"])
    assert path == tmp_path / "reports" / f"{out['report_id']}.json"
    data = json.loads(path.read_text())
    assert data["report_id"] == out["report_id"]
    assert data["note"] == "bad move"
    assert data["category"] == "engine"
    assert data["session_id"] == g["id"]
    assert data["seed"] == 5
    assert data["export"] == c.get(f"/api/games/{g['id']}/export").json()
    assert data["history"] == data["export"]["history"]
    assert data["view"]["view"] == g["view"]
    assert "created_at" in data
    # the embedded export replays
    assert c.post("/api/games/import", json=data["export"]).status_code == 200


def test_report_ids_unique_and_sortable(tmp_path: Path) -> None:
    c, g = _setup(tmp_path)
    ids = [
        c.post(f"/api/games/{g['id']}/report", json={"note": "x"}).json()["report_id"]
        for _ in range(3)
    ]
    assert len(set(ids)) == 3
    assert all("/" not in i and ".." not in i for i in ids)
    assert len(list((tmp_path / "reports").glob("*.json"))) == 3


def test_report_errors(tmp_path: Path) -> None:
    c, g = _setup(tmp_path)
    assert c.post("/api/games/nope/report", json={"note": "x"}).status_code == 404
    assert c.post(f"/api/games/{g['id']}/report", json={"note": ""}).status_code == 422
    assert c.post(f"/api/games/{g['id']}/report", json={"note": "  "}).status_code == 422
    assert c.post(f"/api/games/{g['id']}/report", json={}).status_code == 422
    assert not (tmp_path / "reports").exists()
