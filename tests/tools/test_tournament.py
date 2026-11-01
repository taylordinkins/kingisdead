import json

import pytest

from tools.tournament import main, run_tournament, wilson


def wins(res):
    return [b["wins"] for b in res["bots"]]


def test_smoke_two_player():
    res = run_tournament(["random", "heuristic"], 10, 0)
    assert res["games"] == 10
    assert sum(wins(res)) == pytest.approx(10)
    assert res["mean_plies"] > 0


def test_deterministic_and_workers_equal():
    a = run_tournament(["random", "heuristic"], 6, 3)
    b = run_tournament(["random", "heuristic"], 6, 3)
    c = run_tournament(["random", "heuristic"], 6, 3, workers=2)
    assert wins(a) == wins(b) == wins(c)
    assert a["draws"] == c["draws"] and a["mean_plies"] == c["mean_plies"]


def test_rotation_balances_seats():
    res = run_tournament(["random", "random"], 6, 0)
    assert [b["seat_counts"] for b in res["bots"]] == [[3, 3], [3, 3]]
    res = run_tournament(["random", "random"], 4, 0, rotate=False)
    assert res["bots"][0]["seat_counts"] == [4, 0]


def test_wilson_known_values():
    lo, hi = wilson(0, 10)
    assert lo == 0.0 and hi == pytest.approx(0.2775, abs=1e-3)
    lo, hi = wilson(10, 10)
    assert hi == 1.0 and lo == pytest.approx(0.7225, abs=1e-3)
    lo, hi = wilson(5, 10)
    assert lo == pytest.approx(0.2366, abs=1e-3)
    assert hi == pytest.approx(0.7634, abs=1e-3)


def test_json_output(tmp_path):
    p = tmp_path / "out.json"
    assert main(["--seats", "random", "random", "--games", "2", "--json", str(p), "--quiet"]) == 0
    data = json.loads(p.read_text())
    assert data["games"] == 2 and "args" in data and len(data["bots"]) == 2


def test_three_player():
    res = run_tournament(["random", "heuristic", "random"], 3, 1)
    assert sum(wins(res)) == pytest.approx(3)
