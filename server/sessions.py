"""In-memory sessions. The action history is the single source of truth (D18).

State is always rebuilt by replaying `history` from `game.new_initial_state()`; nothing is
serialised or deserialised through OpenSpiel.
"""

from __future__ import annotations

import logging
import random
import threading
import uuid
from collections.abc import Mapping, Sequence
from typing import Any

import pyspiel

from kingisdead.scenario import load_scenario
from server.adapters.base import JSON, GameAdapter
from server.bots import bot_rng, get_bot, is_valid_seat_type

log = logging.getLogger(__name__)

CHANCE = -1  # actor marker for chance outcomes in `Session.actors`


class SessionError(Exception):
    """Base class for session failures."""


class IllegalAction(SessionError):
    """The action (or chance outcome) is not allowed at this point of the history."""


class UnknownSession(SessionError):
    """No session with that id."""


class CannotGoBack(SessionError):
    """back() found no earlier human turn to return to."""


class Session:
    """One game in progress.

    Chance: after each player action (and at creation) chance nodes are resolved automatically.
    Each pick uses `random.Random(f"{seed}:{len(history)}")`, i.e. the RNG is re-seeded from
    (seed, position in history). It is stateless, so replaying, truncating (back/rewind) and
    re-resolving always reproduces the same outcomes: same seed + same player actions gives an
    identical history.
    """

    def __init__(
        self,
        session_id: str,
        adapter: GameAdapter,
        params: dict[str, Any],
        seats: Sequence[str],
        seed: int,
        history: Sequence[int] = (),
        scenario: dict[str, Any] | None = None,
        inline_bots: bool = True,
    ) -> None:
        self.id = session_id
        # inline_bots: mutations play bot turns synchronously (tests/tools). Otherwise a
        # background worker does it off the lock (D28).
        self.inline_bots = inline_bots
        # Bumped on every mutation of history; lets the worker discard stale results.
        self.version = 0
        self.bot_error: str | None = None
        self._worker_running = False
        # Held by callers (server handlers) around every read/write of this session.
        self.lock = threading.RLock()
        self.adapter = adapter
        self.params = params
        self.seats = list(seats)
        self.seed = seed
        # Scenario games start from load_scenario(scenario) and replay history on top (D18
        # cannot serialise such states, so the scenario JSON is the session's start point).
        self.scenario = scenario
        self.game = adapter.load(params)
        if len(self.seats) != self.game.num_players():
            raise SessionError(
                f"{len(self.seats)} seats given, game has {self.game.num_players()} players"
            )
        for t in self.seats:
            if not is_valid_seat_type(t):
                raise SessionError(f"unknown seat type {t!r}")
        self.history: list[int] = []
        self.actors: list[int] = []  # parallel to history: seat that acted, or CHANCE
        self.state: pyspiel.State = self._initial()
        self._load(history)
        self._resolve_chance()
        self._after_mutation()

    def _initial(self) -> pyspiel.State:
        if self.scenario is not None:
            return load_scenario(self.scenario)
        return self.game.new_initial_state()

    @property
    def game_name(self) -> str:
        return self.adapter.name

    def is_human(self, seat: int) -> bool:
        return self.seats[seat] == "human"

    @property
    def pending_bot(self) -> bool:
        """True iff the seat to move is a bot and the game is not over."""
        if self.state.is_terminal() or self.state.is_chance_node():
            return False
        return not self.is_human(self.state.current_player())

    @property
    def bot_thinking(self) -> bool:
        """A bot is to move and has not failed (the worker is computing or about to)."""
        return self.pending_bot and self.bot_error is None

    def _after_mutation(self) -> None:
        if self.inline_bots:
            self.advance_bots()
        else:
            self.schedule_bots()

    def schedule_bots(self) -> None:
        """Ensure a background worker is playing pending bot turns (at most one per session)."""
        with self.lock:
            if self._worker_running or not self.bot_thinking:
                return
            self._worker_running = True
        try:
            threading.Thread(
                target=self._bot_worker, name=f"bots-{self.id[:8]}", daemon=True
            ).start()
        except BaseException as e:
            log.exception("could not start bot worker for session %s", self.id)
            with self.lock:
                self.bot_error = f"could not start bot worker: {e}"
                self._worker_running = False
            raise

    def _bot_worker(self) -> None:
        # The flag is cleared only under the lock together with the "nothing pending" check, and
        # mutators call schedule_bots() under the lock, so a mutation either is seen by the next
        # loop iteration or sees the flag cleared and spawns a fresh worker (no lost wake-up).
        try:
            while True:
                with self.lock:
                    if not self.bot_thinking:
                        self._worker_running = False
                        return
                    version = self.version
                    seat = self.state.current_player()
                    seat_type = self.seats[seat]
                    clone = self.state.clone()
                    rng = bot_rng(self.seed, len(self.history))
                try:
                    a = get_bot(seat_type).choose(clone, rng)  # slow part, outside the lock
                except Exception:
                    with self.lock:
                        if self.version != version:
                            continue  # failure belongs to a stale snapshot; ignore it
                    raise
                with self.lock:
                    if self.version != version:
                        continue  # stale (back/rewind/etc. happened); re-snapshot
                    if a not in self.state.legal_actions():
                        raise IllegalAction(f"bot {seat_type!r} chose illegal action {a}")
                    self.actors.append(seat)
                    self.state.apply_action(a)
                    self.history.append(a)
                    self.version += 1
                    self._resolve_chance()
        except BaseException as e:  # noqa: BLE001
            log.exception("bot worker for session %s failed", self.id)
            with self.lock:
                self.bot_error = f"{type(e).__name__}: {e}"
                self._worker_running = False

    def retry_bots(self) -> None:
        """Clear a recorded bot error and restart the worker (caller holds the lock)."""
        if not self.pending_bot:
            raise IllegalAction("no bot is to move")
        self._touch()
        self._after_mutation()

    def _touch(self) -> None:
        self.version += 1
        self.bot_error = None

    def advance_bots(self, max_steps: int | None = None) -> int:
        """Play consecutive bot turns (at most `max_steps`); returns the number played.

        Each choice is seeded from (seed, len(history)), so replays are reproducible. Callers
        currently run this inline; slow bots can later call it from a background task.
        """
        steps = 0
        while self.pending_bot and (max_steps is None or steps < max_steps):
            seat = self.state.current_player()
            a = get_bot(self.seats[seat]).choose(self.state, bot_rng(self.seed, len(self.history)))
            if a not in self.state.legal_actions():
                raise IllegalAction(f"bot {self.seats[seat]!r} chose illegal action {a}")
            self.actors.append(seat)
            self.state.apply_action(a)
            self.history.append(a)
            self.version += 1
            self._resolve_chance()
            steps += 1
        return steps

    def _load(self, history: Sequence[int]) -> None:
        """Replace state/history by replaying `history` from scratch, validating every step."""
        self._touch()
        state = self._initial()
        actors: list[int] = []
        for i, a in enumerate(history):
            if state.is_terminal():
                raise IllegalAction(f"history[{i}]={a}: game already over")
            if state.is_chance_node():
                if a not in {o for o, p in state.chance_outcomes() if p > 0}:
                    raise IllegalAction(f"history[{i}]={a}: not a possible chance outcome")
                actors.append(CHANCE)
            else:
                if a not in state.legal_actions():
                    raise IllegalAction(f"history[{i}]={a}: illegal for player")
                actors.append(state.current_player())
            state.apply_action(a)
        self.state, self.history, self.actors = state, list(history), actors

    def _resolve_chance(self) -> None:
        while not self.state.is_terminal() and self.state.is_chance_node():
            rng = random.Random(f"{self.seed}:{len(self.history)}")
            actions, probs = zip(*self.state.chance_outcomes(), strict=True)
            a = rng.choices(actions, weights=probs)[0]
            self.state.apply_action(a)
            self.history.append(a)
            self.actors.append(CHANCE)

    def _truncate(self, length: int) -> None:
        self._load(self.history[:length])
        self._resolve_chance()
        self._after_mutation()

    def apply(self, action_id: int) -> None:
        """Apply a player action, then auto-resolve following chance nodes."""
        if self.state.is_terminal():
            raise IllegalAction("game is over")
        if self.pending_bot:
            raise IllegalAction("a bot is to move")
        if action_id not in self.state.legal_actions():
            raise IllegalAction(f"action {action_id} is not legal for the current player")
        self.actors.append(self.state.current_player())
        self.state.apply_action(action_id)
        self.history.append(action_id)
        self._touch()
        self._resolve_chance()
        self._after_mutation()

    def _human_turn_start(self) -> int:
        """History index where the current (or else the previous) human turn began.

        A human turn is the maximal run of consecutive actions by one human seat with no chance
        outcome or other seat in between. If the seat to move is human and has acted this turn,
        that run is the target; otherwise we skip back over chance/bot/non-run entries to the
        last human action and take its whole run.
        """
        k = len(self.history)
        cur = CHANCE if self.state.is_terminal() else self.state.current_player()
        if not (cur >= 0 and self.is_human(cur) and k > 0 and self.actors[k - 1] == cur):
            while k > 0 and not (self.actors[k - 1] >= 0 and self.is_human(self.actors[k - 1])):
                k -= 1
            if k == 0:
                raise CannotGoBack("no earlier human turn")
        seat = self.actors[k - 1]
        while k > 0 and self.actors[k - 1] == seat:
            k -= 1
        return k

    def back(self) -> None:
        """Rewind to the start of the current human turn (or the previous one if none begun)."""
        self._truncate(self._human_turn_start())

    def rewind(self, n_player_actions: int) -> None:
        """Dev mode: keep only the first `n_player_actions` player actions (plus chance)."""
        if n_player_actions < 0:
            raise SessionError("n_player_actions must be >= 0")
        seen = 0
        for i, who in enumerate(self.actors):
            if who != CHANCE:
                if seen == n_player_actions:
                    self._truncate(i)
                    return
                seen += 1
        if seen != n_player_actions:
            raise SessionError(f"only {seen} player actions have been taken")

    def view(self, seat: int) -> JSON:
        return self.adapter.view(self.state, seat)

    def history_entries(self) -> list[JSON]:
        """Labelled history: replay, labelling each action as it was when it was legal."""
        state = self._initial()
        out: list[JSON] = []
        for i, (a, who) in enumerate(zip(self.history, self.actors, strict=True)):
            if who == CHANCE:
                label = self.adapter.chance_label(state, a)
                actor = None
            else:
                label = str(self.adapter.action_meta(state, a)["label"])
                actor = who
            out.append({"index": i, "actor": actor, "id": a, "label": label})
            state.apply_action(a)
        return out


class SessionStore:
    def __init__(self, adapters: Mapping[str, GameAdapter], inline_bots: bool = True) -> None:
        self.inline_bots = inline_bots
        self.adapters = dict(adapters)
        self.sessions: dict[str, Session] = {}
        self._lock = threading.Lock()

    def create(
        self,
        game: str,
        params: dict[str, Any],
        seats: Sequence[str],
        seed: int,
        history: Sequence[int] = (),
        scenario: dict[str, Any] | None = None,
    ) -> Session:
        """New session; a non-empty `history` (import) is validated by replay."""
        if game not in self.adapters:
            raise SessionError(f"unknown game {game!r}")
        session = Session(
            uuid.uuid4().hex,
            self.adapters[game],
            params,
            seats,
            seed,
            history,
            scenario,
            self.inline_bots,
        )
        with self._lock:
            self.sessions[session.id] = session
        return session

    def get(self, session_id: str) -> Session:
        try:
            with self._lock:
                return self.sessions[session_id]
        except KeyError:
            raise UnknownSession(session_id) from None
