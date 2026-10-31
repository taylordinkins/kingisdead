"""Game-agnostic adapter interface (PLAN.md 5.6). The server shell only talks to this."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import pyspiel

JSON = dict[str, Any]


class GameAdapter(ABC):
    """Maps one OpenSpiel game to JSON for clients."""

    name: str

    @abstractmethod
    def load(self, params: dict[str, Any]) -> pyspiel.Game:
        """Build the pyspiel game from creation params (e.g. {"players": 3})."""

    @abstractmethod
    def view(self, state: pyspiel.State, seat: int) -> JSON:
        """JSON-serialisable view of `state` for `seat` (hidden info is filtered per seat)."""

    @abstractmethod
    def action_meta(self, state: pyspiel.State, action_id: int) -> JSON:
        """Metadata for an action: label, kind, and optional region/faction/card."""
