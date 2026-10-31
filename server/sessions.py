"""In-memory sessions. The action history is the single source of truth (D18).

State is always rebuilt by replaying `history` from `game.new_initial_state()`; nothing is
serialised or deserialised through OpenSpiel.
"""

from __future__ import annotations

import random
import uuid
from collections.abc import Mapping, Sequence
from typing import Any

import pyspiel

from server.adapters.base import JSON, GameAdapter

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
    ) -> None:
        self.id = session_id
        self.adapter = adapter
        self.params = params
        self.seats = list(seats)
        self.seed = seed
        self.game = adapter.load(params)
        if len(self.seats) != self.game.num_players():
            raise SessionError(
                f"{len(self.seats)} seats given, game has {self.game.num_players()} players"
            )
        self.history: list[int] = []
        self.actors: list[int] = []  # parallel to history: seat that acted, or CHANCE
        self.state: pyspiel.State = self.game.new_initial_state()
        self._load(history)
        self._resolve_chance()

    @property
    def game_name(self) -> str:
        return self.adapter.name

    def is_human(self, seat: int) -> bool:
        return self.seats[seat] == "human"

    def _load(self, history: Sequence[int]) -> None:
        """Replace state/history by replaying `history` from scratch, validating every step."""
        state = self.game.new_initial_state()
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

    def apply(self, action_id: int) -> None:
        """Apply a player action, then auto-resolve following chance nodes."""
        if self.state.is_terminal():
            raise IllegalAction("game is over")
        if action_id not in self.state.legal_actions():
            raise IllegalAction(f"action {action_id} is not legal for the current player")
        self.actors.append(self.state.current_player())
        self.state.apply_action(action_id)
        self.history.append(action_id)
        self._resolve_chance()

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


class SessionStore:
    def __init__(self, adapters: Mapping[str, GameAdapter]) -> None:
        self.adapters = dict(adapters)
        self.sessions: dict[str, Session] = {}

    def create(
        self,
        game: str,
        params: dict[str, Any],
        seats: Sequence[str],
        seed: int,
        history: Sequence[int] = (),
    ) -> Session:
        """New session; a non-empty `history` (import) is validated by replay."""
        if game not in self.adapters:
            raise SessionError(f"unknown game {game!r}")
        session = Session(uuid.uuid4().hex, self.adapters[game], params, seats, seed, history)
        self.sessions[session.id] = session
        return session

    def get(self, session_id: str) -> Session:
        try:
            return self.sessions[session_id]
        except KeyError:
            raise UnknownSession(session_id) from None
