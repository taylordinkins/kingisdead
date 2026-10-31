"""CLI tests for tools/play_text.py and tools/sim_stats.py (Phase 2 unit 12).

Assumed CLI contract:
  play_text.py --players N --seed S [--actions random]
      Plays one game; for each decision prints the legal actions and the chosen action; at the
      end prints the final returns. Exit 0. Same seed gives identical output.
  sim_stats.py --games N --seed S [--players N] [--json]
      Plays N random games (players 2 or 3; default mixes 2 and 3) and prints the end-type mix
      and game length mean/min/max. With --json prints one JSON object on stdout:
        {"games": int,
         "end_types": {"invasion": int, "coronation": int},   # sums to games
         "game_length": {"mean": float, "min": int, "max": int},
         "invariant_violations": 0}
      Exit 0.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
END_TYPES = {"invasion", "coronation"}


def _run(tool: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ROOT / "tools" / tool), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=300,
    )


@pytest.mark.parametrize("players", [2, 3])
def test_play_text_runs_and_prints_returns(players: int) -> None:
    r = _run("play_text.py", "--players", str(players), "--seed", "7", "--actions", "random")
    assert r.returncode == 0, r.stderr
    out = r.stdout.lower()
    assert "legal" in out
    assert "return" in out
    assert len(r.stdout.splitlines()) > 10


def test_play_text_same_seed_same_output() -> None:
    a = _run("play_text.py", "--players", "2", "--seed", "3")
    b = _run("play_text.py", "--players", "2", "--seed", "3")
    assert a.returncode == 0 and b.returncode == 0
    assert a.stdout == b.stdout


def test_play_text_different_seed_differs() -> None:
    a = _run("play_text.py", "--players", "2", "--seed", "3")
    b = _run("play_text.py", "--players", "2", "--seed", "4")
    assert a.returncode == 0 and b.returncode == 0
    assert a.stdout != b.stdout


@pytest.mark.parametrize("players", [None, 2, 3])
def test_sim_stats_json(players: int | None) -> None:
    args = ["--games", "30", "--seed", "1", "--json"]
    if players:
        args += ["--players", str(players)]
    r = _run("sim_stats.py", *args)
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    assert data["games"] == 30
    ends = data["end_types"]
    assert set(ends) <= END_TYPES
    assert sum(ends.values()) == data["games"]
    length = data["game_length"]
    assert length["min"] <= length["mean"] <= length["max"]
    assert length["min"] > 0
    assert data["invariant_violations"] == 0


def test_sim_stats_text_report() -> None:
    r = _run("sim_stats.py", "--games", "10", "--seed", "2")
    assert r.returncode == 0, r.stderr
    out = r.stdout.lower()
    assert "invasion" in out or "coronation" in out
    assert "mean" in out and "min" in out and "max" in out


def test_sim_stats_seeded_is_reproducible() -> None:
    args = ["--games", "15", "--seed", "5", "--json"]
    a, b = _run("sim_stats.py", *args), _run("sim_stats.py", *args)
    assert a.returncode == 0 and a.stdout == b.stdout
