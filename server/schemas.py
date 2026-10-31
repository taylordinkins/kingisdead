"""Request/response envelopes for the HTTP API (OpenAPI source for generated web types)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

SeatType = Literal["human", "random"]


class GameParams(BaseModel):
    """Creation parameters for a game."""

    num_players: int | None = Field(default=None, description="Number of players (2 or 3).")


class CreateGameRequest(BaseModel):
    game: str = "king_is_dead"
    params: GameParams = Field(default_factory=GameParams)
    seats: list[SeatType]
    seed: int | None = None


class GameView(BaseModel):
    """A game as seen by one seat."""

    id: str
    game: str
    seats: list[SeatType]
    seat_types: list[SeatType]
    seed: int
    bot_thinking: bool = Field(description="A bot seat is to move (not yet played).")
    seat: int
    history_length: int
    view: dict[str, Any] = Field(description="Adapter-defined view payload.")


class ActionRequest(BaseModel):
    action: int


class RewindRequest(BaseModel):
    player_actions: int


class GameExport(BaseModel):
    """Replay file: everything needed to rebuild a game by replaying `history`."""

    game: str
    params: GameParams
    seats: list[SeatType]
    seed: int
    history: list[int]


class ReportRequest(BaseModel):
    note: str = Field(min_length=1, description="What went wrong (required).")
    category: str | None = Field(default=None, description='e.g. "engine", "ui", "other".')

    @field_validator("note")
    @classmethod
    def _note_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("note must not be blank")
        return v


class ReportResponse(BaseModel):
    report_id: str
    path: str


class ErrorResponse(BaseModel):
    detail: str
