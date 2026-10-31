"""FastAPI app: thin JSON layer over SessionStore. Game-agnostic via GameAdapter."""

from __future__ import annotations

import os
import random
from typing import Annotated

from fastapi import APIRouter, FastAPI, HTTPException, Query

from server.adapters.kingisdead import KingIsDeadAdapter
from server.schemas import (
    ActionRequest,
    CreateGameRequest,
    ErrorResponse,
    GameExport,
    GameParams,
    GameView,
    RewindRequest,
)
from server.sessions import (
    CannotGoBack,
    IllegalAction,
    Session,
    SessionError,
    SessionStore,
    UnknownSession,
)

GAME_NAME = "king_is_dead"
_ERR = {"model": ErrorResponse}


def _to_adapter_params(p: GameParams) -> dict[str, int]:
    return {} if p.num_players is None else {"players": p.num_players}


def _from_adapter_params(session: Session) -> GameParams:
    return GameParams(num_players=session.game.num_players())


def create_app(dev_mode: bool = False) -> FastAPI:
    store = SessionStore({GAME_NAME: KingIsDeadAdapter()})
    api = APIRouter(prefix="/api")

    def lookup(game_id: str) -> Session:
        try:
            return store.get(game_id)
        except UnknownSession:
            raise HTTPException(404, f"unknown game {game_id!r}") from None

    def render(s: Session, seat: int | None = None) -> GameView:
        if seat is None:
            seat = 0 if s.state.is_terminal() else max(s.state.current_player(), 0)
        if not 0 <= seat < len(s.seats):
            raise HTTPException(422, f"seat {seat} out of range")
        seats: list[str] = list(s.seats)
        return GameView.model_validate(
            {
                "id": s.id,
                "game": GAME_NAME,
                "seats": seats,
                "seat_types": seats,
                "seed": s.seed,
                "seat": seat,
                "history_length": len(s.history),
                "view": s.view(seat),
            }
        )

    def make(game: str, params: GameParams, seats: list[str], seed: int, history: list[int]):
        try:
            return store.create(game, _to_adapter_params(params), seats, seed, history)
        except IllegalAction as e:
            raise HTTPException(400, f"invalid history: {e}") from None
        except (SessionError, ValueError) as e:
            raise HTTPException(400, str(e)) from None

    @api.post("/games", operation_id="create_game", responses={400: _ERR})
    def create_game(req: CreateGameRequest) -> GameView:
        seed = req.seed if req.seed is not None else random.randrange(2**31)
        return render(make(req.game, req.params, list(req.seats), seed, []))

    @api.post("/games/import", operation_id="import_game", responses={400: _ERR})
    def import_game(body: GameExport) -> GameView:
        return render(make(body.game, body.params, list(body.seats), body.seed, body.history))

    @api.get("/games/{game_id}", operation_id="get_game", responses={404: _ERR})
    def get_game(game_id: str, seat: Annotated[int | None, Query()] = None) -> GameView:
        return render(lookup(game_id), seat)

    @api.post(
        "/games/{game_id}/actions",
        operation_id="post_action",
        responses={404: _ERR, 409: _ERR},
    )
    def post_action(game_id: str, req: ActionRequest) -> GameView:
        s = lookup(game_id)
        try:
            s.apply(req.action)
        except IllegalAction as e:
            raise HTTPException(409, str(e)) from None
        return render(s)

    @api.post("/games/{game_id}/back", operation_id="go_back", responses={404: _ERR, 409: _ERR})
    def go_back(game_id: str) -> GameView:
        s = lookup(game_id)
        try:
            s.back()
        except CannotGoBack as e:
            raise HTTPException(409, str(e)) from None
        return render(s)

    @api.post(
        "/games/{game_id}/rewind",
        operation_id="rewind_game",
        responses={400: _ERR, 403: _ERR, 404: _ERR},
    )
    def rewind_game(game_id: str, req: RewindRequest) -> GameView:
        if not dev_mode:
            raise HTTPException(403, "rewind requires dev mode")
        s = lookup(game_id)
        try:
            s.rewind(req.player_actions)
        except SessionError as e:
            raise HTTPException(400, str(e)) from None
        return render(s)

    @api.get("/games/{game_id}/export", operation_id="export_game", responses={404: _ERR})
    def export_game(game_id: str) -> GameExport:
        s = lookup(game_id)
        seats: list[str] = list(s.seats)
        return GameExport.model_validate(
            {
                "game": GAME_NAME,
                "params": _from_adapter_params(s),
                "seats": seats,
                "seed": s.seed,
                "history": list(s.history),
            }
        )

    app = FastAPI(title="King is Dead server")
    app.include_router(api)
    return app


app = create_app(dev_mode=bool(os.environ.get("KID_DEV")))
