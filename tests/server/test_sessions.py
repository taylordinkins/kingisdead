"""Phase 3 unit 2: session store with history replay."""

import random

import pytest

from server.adapters.kingisdead import KingIsDeadAdapter
from server.sessions import (
    CHANCE,
    CannotGoBack,
    IllegalAction,
    Session,
    SessionError,
    SessionStore,
    UnknownSession,
)

ADAPTER = KingIsDeadAdapter()
STORE = SessionStore({ADAPTER.name: ADAPTER})


def _new(n: int = 2, seed: int = 1, seats: list[str] | None = None) -> Session:
    return STORE.create(ADAPTER.name, {"players": n}, seats or ["human"] * n, seed)


def _play(s: Session, pick_seed: int, steps: int | None = None) -> None:
    rng = random.Random(pick_seed)
    while not s.state.is_terminal() and (steps is None or steps > 0):
        s.apply(rng.choice(s.state.legal_actions()))
        if steps is not None:
            steps -= 1


def _snapshot(s: Session) -> tuple[str, list[int]]:
    return str(s.state), list(s.history)


@pytest.mark.parametrize("n", [2, 3])
@pytest.mark.parametrize("seed", [0, 5])
def test_replay_reproduces_live_state(n: int, seed: int) -> None:
    s = _new(n, seed)
    _play(s, seed + 100)
    assert s.state.is_terminal()
    again = STORE.create(ADAPTER.name, {"players": n}, ["human"] * n, seed, s.history)
    assert again.history == s.history
    assert str(again.state) == str(s.state)
    for seat in range(n):
        assert again.view(seat) == s.view(seat)


@pytest.mark.parametrize("n", [2, 3])
def test_same_seed_same_actions_same_history(n: int) -> None:
    a, b = _new(n, 7), _new(n, 7)
    _play(a, 3, 60)
    _play(b, 3, 60)
    assert a.history == b.history and len(a.history) > 60


def test_different_seed_changes_chance() -> None:
    assert _new(2, 1).history != _new(2, 2).history


def test_creation_resolves_chance_and_unknowns() -> None:
    s = _new()
    assert not s.state.is_chance_node()
    assert s.actors and all(a == CHANCE for a in s.actors)
    with pytest.raises(UnknownSession):
        STORE.get("nope")
    assert STORE.get(s.id) is s
    with pytest.raises(SessionError):
        STORE.create(ADAPTER.name, {"players": 2}, ["human"], 1)
    with pytest.raises(SessionError):
        STORE.create("chess", {}, ["human"], 1)


def test_illegal_action_does_not_mutate() -> None:
    s = _new()
    before = _snapshot(s)
    with pytest.raises(IllegalAction):
        s.apply(10**6)
    assert _snapshot(s) == before


def test_apply_on_terminal_rejected() -> None:
    s = _new()
    _play(s, 1)
    before = _snapshot(s)
    with pytest.raises(IllegalAction):
        s.apply(0)
    assert _snapshot(s) == before


def test_import_rejects_corrupted_history() -> None:
    s = _new()
    _play(s, 2, 10)
    bad = list(s.history)
    bad[len(bad) - 1] = 10**6
    with pytest.raises(IllegalAction):
        STORE.create(ADAPTER.name, {"players": 2}, ["human"] * 2, 1, bad)
    # chance outcome in a player slot / player action in a chance slot
    with pytest.raises(IllegalAction):
        STORE.create(ADAPTER.name, {"players": 2}, ["human"] * 2, 1, [10**6])
    # trailing actions past the end of the game
    _play(s, 2)
    with pytest.raises(IllegalAction):
        STORE.create(ADAPTER.name, {"players": 2}, ["human"] * 2, 1, [*s.history, 0])


def _runs(s: Session) -> list[tuple[int, int]]:
    """(start index, seat) of each maximal run of same-seat player actions."""
    out: list[tuple[int, int]] = []
    for i, who in enumerate(s.actors):
        if who != CHANCE and (i == 0 or s.actors[i - 1] != who):
            out.append((i, who))
    return out


def _advance_until_multi_action_turn(s: Session) -> None:
    rng = random.Random(4)
    while not s.state.is_terminal():
        s.apply(rng.choice(s.state.legal_actions()))
        runs = _runs(s)
        k = len(s.history)
        if len(runs) >= 3 and s.actors[k - 1] == s.actors[k - 2] != CHANCE:
            return
    pytest.fail("no multi-action turn found")


def test_back_to_start_of_current_turn_hotseat() -> None:
    s = _new(2, 3)
    _advance_until_multi_action_turn(s)
    start = _runs(s)[-1][0]
    s.back()
    assert len(s.history) == start
    # replaying the truncated history reproduces the same state
    again = STORE.create(ADAPTER.name, {"players": 2}, ["human"] * 2, 3, s.history)
    assert str(again.state) == str(s.state)


def test_back_with_nothing_done_undoes_previous_turn() -> None:
    s = _new(2, 3)
    _play(s, 9, 40)
    # step back to the very start of the current turn, then once more for the previous turn
    s.back()
    here = len(s.history)
    if here == 0:
        pytest.skip("at start")
    prev_start = None
    k = here
    while k > 0 and s.actors[k - 1] == CHANCE:
        k -= 1
    if k > 0:
        who = s.actors[k - 1]
        while k > 0 and s.actors[k - 1] == who:
            k -= 1
        prev_start = k
    if prev_start is None:
        return
    s.back()
    assert len(s.history) == prev_start


def test_back_at_start_errors() -> None:
    s = _new()
    before = _snapshot(s)
    with pytest.raises(CannotGoBack):
        s.back()
    assert _snapshot(s) == before


def test_back_skips_bot_turns() -> None:
    s = _new(2, 3, ["human", "random"])
    rng = random.Random(8)
    for _ in range(8):
        if s.state.is_terminal():
            break
        assert not s.pending_bot  # bots are always advanced inline
        s.apply(rng.choice(s.state.legal_actions()))
    assert 1 in s.actors, "bot should have played"
    for _ in range(50):
        before = len(s.history)
        try:
            s.back()
        except CannotGoBack:
            break
        assert len(s.history) < before
        # landed at the start of a human turn: human to move, last real actor not that human
        assert not s.state.is_terminal() and s.is_human(s.state.current_player())
        real = [w for w in s.actors if w != CHANCE]
        assert not real or real[-1] == 1  # only the bot acted between the human's turns
    assert 0 not in s.actors


def test_rewind_truncates_player_actions_and_reresolves_chance() -> None:
    s = _new(2, 6)
    _play(s, 11, 30)
    full = list(s.history)
    for n in (17, 5, 0):
        s.rewind(n)
        assert sum(1 for w in s.actors if w != CHANCE) == n
        assert not s.state.is_chance_node()
        assert s.history == full[: len(s.history)]
    with pytest.raises(SessionError):
        s.rewind(999)
    # redoing the same actions reproduces the same history
    s = STORE.create(ADAPTER.name, {"players": 2}, ["human"] * 2, 6, full[:0])
    for a in [x for x, w in zip(full, _actors_of(full), strict=True) if w][:30]:
        s.apply(a)
    assert s.history == full


def _actors_of(history: list[int]) -> list[bool]:
    """True where the history entry is a player action."""
    s = Session("x", ADAPTER, {"players": 2}, ["human"] * 2, 6, history)
    return [w != CHANCE for w in s.actors]
