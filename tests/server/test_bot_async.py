"""Phase 5 unit 3: bot thinking runs off the session lock (D28)."""

import random
import threading
import time
from typing import Any

import pytest
from fastapi.testclient import TestClient

import server.bots as bots_mod
from server.app import create_app

Json = dict[str, Any]


class SlowBot:
    def __init__(self, delay: float) -> None:
        self.delay = delay
        self.calls = 0

    def choose(self, state, rng):
        self.calls += 1
        if self.calls == 1:  # only the first move is slow, keeps the suite fast
            time.sleep(self.delay)
        return rng.choice(state.legal_actions())


class BoomBot:
    def choose(self, state, rng):
        raise RuntimeError("boom")


def _client(inline: bool = False) -> TestClient:
    return TestClient(create_app(inline_bots=inline))


def _create(c: TestClient, seats: list[str], seed: int = 3) -> Json:
    r = c.post(
        "/api/games",
        json={"params": {"num_players": len(seats)}, "seats": seats, "seed": seed},
    )
    assert r.status_code == 200, r.text
    return r.json()


def _get(c: TestClient, gid: str) -> Json:
    return c.get(f"/api/games/{gid}").json()


def _wait(c: TestClient, gid: str, pred, timeout: float = 20.0) -> Json:
    deadline = time.monotonic() + timeout
    while True:
        g = _get(c, gid)
        if pred(g):
            return g
        assert time.monotonic() < deadline, "timed out"
        time.sleep(0.01)


def _human_acts(c: TestClient, g: Json) -> Json:
    r = c.post(f"/api/games/{g['id']}/actions", json={"action": g["legal_actions"][0]["id"]})
    assert r.status_code == 200, r.text
    return r.json()


def test_slow_bot_does_not_block(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(bots_mod.BOTS, "random", SlowBot(1.0))
    c = _client()
    g = _create(c, ["human", "random"])
    assert not g["bot_thinking"]
    t = time.monotonic()
    g = _human_acts(c, g)
    while g["current_player"] == 0 and not g["bot_thinking"]:
        g = _human_acts(c, g)
    assert time.monotonic() - t < 0.5
    assert g["bot_thinking"]
    n = g["history_length"]
    t = time.monotonic()
    g2 = _get(c, g["id"])
    assert time.monotonic() - t < 0.3
    assert g2["bot_thinking"] and g2["history_length"] == n
    g3 = _wait(c, g["id"], lambda x: not x["bot_thinking"])
    assert g3["history_length"] > n


def test_back_discards_stale_move(monkeypatch: pytest.MonkeyPatch) -> None:
    bot = SlowBot(0.6)
    monkeypatch.setitem(bots_mod.BOTS, "random", bot)
    c = _client()
    g = _create(c, ["human", "random"])
    gid = g["id"]
    g = _human_acts(c, g)
    while not g["bot_thinking"]:
        g = _human_acts(c, g)
    time.sleep(0.1)  # the worker is inside choose()
    r = c.post(f"/api/games/{gid}/back")
    assert r.status_code == 200
    back = r.json()
    assert back["history_length"] < g["history_length"]
    assert not back["bot_thinking"]
    time.sleep(1.0)  # let the stale computation finish
    now = _get(c, gid)
    assert now["history"] == back["history"]
    assert now["current_player"] == 0


def _full_game(c: TestClient, seats: list[str], seed: int) -> list[int]:
    g = _create(c, seats, seed)
    rng = random.Random(1)
    gid = g["id"]
    deadline = time.monotonic() + 30
    while not g["is_terminal"]:
        assert time.monotonic() < deadline
        if g["bot_thinking"]:
            time.sleep(0.005)
            g = _get(c, gid)
            continue
        a = rng.choice(g["legal_actions"])["id"]
        r = c.post(f"/api/games/{gid}/actions", json={"action": a})
        assert r.status_code == 200, r.text
        g = r.json()
    return [e["id"] for e in g["history"]]


def test_async_matches_inline_history() -> None:
    seats = ["human", "random", "heuristic"]
    assert _full_game(_client(False), seats, 11) == _full_game(_client(True), seats, 11)


def test_bots_only_game_terminal_and_deterministic() -> None:
    seats = ["random", "random"]
    c = _client()
    g = _create(c, seats, 4)
    g = _wait(c, g["id"], lambda x: x["is_terminal"])
    inline = _client(True)
    h = _create(inline, seats, 4)
    assert h["is_terminal"]
    assert [e["id"] for e in g["history"]] == [e["id"] for e in h["history"]]


def test_no_second_worker(monkeypatch: pytest.MonkeyPatch) -> None:
    bot = SlowBot(0.3)
    monkeypatch.setitem(bots_mod.BOTS, "random", bot)
    c = _client()
    g = _create(c, ["human", "random"])
    g = _human_acts(c, g)
    while not g["bot_thinking"]:
        g = _human_acts(c, g)
    name = f"bots-{g['id'][:8]}"
    assert len([t for t in threading.enumerate() if t.name == name]) == 1
    for _ in range(5):
        _get(c, g["id"])
    assert len([t for t in threading.enumerate() if t.name == name]) == 1
    _wait(c, g["id"], lambda x: not x["bot_thinking"])


def test_schedule_is_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    from server.adapters.kingisdead import KingIsDeadAdapter
    from server.sessions import SessionStore

    monkeypatch.setitem(bots_mod.BOTS, "random", SlowBot(0.3))
    store = SessionStore({"king_is_dead": KingIsDeadAdapter()}, inline_bots=False)
    s = store.create("king_is_dead", {"players": 2}, ["random", "human"], 1)
    for _ in range(10):
        s.schedule_bots()
    workers = [t for t in threading.enumerate() if t.name == f"bots-{s.id[:8]}"]
    assert len(workers) <= 1
    deadline = time.monotonic() + 10
    while s.bot_thinking:
        assert time.monotonic() < deadline
        time.sleep(0.01)


def test_raising_bot_stops_worker(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(bots_mod.BOTS, "random", BoomBot())
    c = _client()
    g = _create(c, ["human", "random"])
    g = _human_acts(c, g)
    while g["current_player"] == 0:
        g = _human_acts(c, g)
    g = _wait(c, g["id"], lambda x: not x["bot_thinking"], timeout=5)
    assert g["current_player"] == 1 and not g["is_terminal"]
    name = f"bots-{g['id'][:8]}"
    for t in [t for t in threading.enumerate() if t.name == name]:
        t.join(5)
    assert not [t for t in threading.enumerate() if t.name == name]


class FlakyBot:
    """Sleeps then raises on its first call; afterwards behaves like the random bot."""

    def __init__(self, fail_first: bool = True, delay: float = 0.0) -> None:
        self.fail = fail_first
        self.delay = delay
        self.calls = 0

    def choose(self, state, rng):
        self.calls += 1
        time.sleep(self.delay)
        if self.fail:
            self.fail = False
            raise RuntimeError("flaky")
        return rng.choice(state.legal_actions())


def test_stale_bot_exception_is_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    from server.adapters.kingisdead import KingIsDeadAdapter
    from server.sessions import SessionStore

    monkeypatch.setitem(bots_mod.BOTS, "random", FlakyBot(delay=0.4))
    store = SessionStore({"king_is_dead": KingIsDeadAdapter()}, inline_bots=False)
    s = store.create("king_is_dead", {"players": 2}, ["human", "random"], 2)
    with s.lock:
        while not s.pending_bot:
            s.apply(s.state.legal_actions()[0])
    time.sleep(0.1)  # worker is inside the failing choose()
    with s.lock:
        s._load(list(s.history))  # any mutation invalidates the snapshot
        s._resolve_chance()
        s.schedule_bots()
    deadline = time.monotonic() + 10
    while s.bot_thinking:
        assert time.monotonic() < deadline
        time.sleep(0.01)
    assert s.bot_error is None
    assert 1 in s.actors  # the bot did move


def test_bot_error_exposed_and_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    flaky = FlakyBot()
    monkeypatch.setitem(bots_mod.BOTS, "random", flaky)
    c = _client()
    g = _create(c, ["random", "random"], 6)
    g = _wait(c, g["id"], lambda x: x["bot_error"] is not None, timeout=5)
    assert not g["bot_thinking"] and "flaky" in g["bot_error"]
    r = c.post(f"/api/games/{g['id']}/bots/retry")
    assert r.status_code == 200 and r.json()["bot_error"] is None
    g = _wait(c, g["id"], lambda x: x["is_terminal"])
    assert g["bot_error"] is None
    assert c.post(f"/api/games/{g['id']}/bots/retry").status_code == 409
    assert c.post("/api/games/nope/bots/retry").status_code == 404


def test_thread_start_failure_does_not_stick(monkeypatch: pytest.MonkeyPatch) -> None:
    from server.adapters.kingisdead import KingIsDeadAdapter
    from server.sessions import SessionStore

    def boom(self):
        raise RuntimeError("no threads")

    store = SessionStore({"king_is_dead": KingIsDeadAdapter()}, inline_bots=False)
    s = store.create("king_is_dead", {"players": 2}, ["human", "random"], 1)
    monkeypatch.setattr(threading.Thread, "start", boom)
    with pytest.raises(RuntimeError), s.lock:
        while True:
            s.apply(s.state.legal_actions()[0])
    assert s.bot_error is not None and not s._worker_running
    assert not s.bot_thinking
