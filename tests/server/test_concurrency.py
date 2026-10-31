"""Sessions are shared across FastAPI's threadpool; handlers must serialise per session."""

import random
import sys
import threading

import pytest
from fastapi.testclient import TestClient

from server.app import create_app


@pytest.fixture
def fast_switching():
    old = sys.getswitchinterval()
    sys.setswitchinterval(1e-6)  # make thread interleaving (the race) likely
    yield
    sys.setswitchinterval(old)


def test_poll_while_playing_never_errors(fast_switching) -> None:
    c = TestClient(create_app())
    r = c.post(
        "/api/games",
        json={"game": "king_is_dead", "params": {"num_players": 2},
              "seats": ["human", "random"], "seed": 5},
    )  # fmt: skip
    assert r.status_code == 200, r.text
    gid = r.json()["id"]
    done = threading.Event()
    bad: list[str] = []

    def poll() -> None:
        while not done.is_set():
            try:
                resp = c.get(f"/api/games/{gid}")
                if resp.status_code != 200:
                    bad.append(f"{resp.status_code} {resp.text[:100]}")
            except Exception as e:  # noqa: BLE001
                bad.append(repr(e))

    def play() -> None:
        rng = random.Random(1)
        try:
            for _ in range(4):
                g = c.get(f"/api/games/{gid}").json()
                while not g["is_terminal"]:
                    a = rng.choice(g["legal_actions"])["id"]
                    resp = c.post(f"/api/games/{gid}/actions", json={"action": a})
                    if resp.status_code != 200:
                        bad.append(f"play {resp.status_code} {resp.text[:100]}")
                        return
                    g = resp.json()
                # Undo back to the first human turn so the same session can be replayed.
                while c.post(f"/api/games/{gid}/back").status_code == 200:
                    pass
        finally:
            done.set()

    pollers = [threading.Thread(target=poll) for _ in range(2)]
    for t in pollers:
        t.start()
    play()
    for t in pollers:
        t.join()
    assert not bad, bad[:3]
