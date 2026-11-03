"""FastAPI app: thin JSON layer over SessionStore. Game-agnostic via GameAdapter."""

from __future__ import annotations

import os
import random
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, FastAPI, HTTPException, Query

from kingisdead.bots.trained import TrainedUnavailable
from kingisdead.scenario import load_scenario
from server.adapters.kingisdead import KingIsDeadAdapter
from server.bots import check_seat_available
from server.reports import DEFAULT_REPORTS_DIR, write_report
from server.schemas import (
    ActionRequest,
    CreateGameRequest,
    ErrorResponse,
    GameExport,
    GameParams,
    GameView,
    ReportRequest,
    ReportResponse,
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


def create_app(
    dev_mode: bool = False,
    reports_dir: Path | str | None = None,
    inline_bots: bool | None = None,
) -> FastAPI:
    # Production default: bots think on a background thread (D28). KID_BOTS_INLINE=1 (or
    # inline_bots=True) plays them synchronously inside the request, for tests and tools.
    if inline_bots is None:
        inline_bots = os.environ.get("KID_BOTS_INLINE", "") not in ("", "0")
    reports_path = Path(reports_dir or os.environ.get("KID_REPORTS_DIR") or DEFAULT_REPORTS_DIR)
    store = SessionStore({GAME_NAME: KingIsDeadAdapter()}, inline_bots=inline_bots)
    api = APIRouter(prefix="/api")

    def lookup(game_id: str) -> Session:
        try:
            return store.get(game_id)
        except UnknownSession:
            raise HTTPException(404, f"unknown game {game_id!r}") from None

    def render(s: Session, seat: int | None = None) -> GameView:
        with s.lock:
            if seat is None:
                seat = 0 if s.state.is_terminal() else max(s.state.current_player(), 0)
            if not 0 <= seat < len(s.seats):
                raise HTTPException(422, f"seat {seat} out of range")
            seats: list[str] = list(s.seats)
            v = s.view(seat)
            return GameView.model_validate(
                {
                    "id": s.id,
                    "game": GAME_NAME,
                    "seats": seats,
                    "seat_types": seats,
                    "seed": s.seed,
                    "bot_thinking": s.bot_thinking,
                    "bot_error": s.bot_error,
                    "seat": seat,
                    "history_length": len(s.history),
                    "history": s.history_entries(),
                    "dev_mode": dev_mode,
                    "current_player": v["current_player"],
                    "is_terminal": v["is_terminal"],
                    "legal_actions": v["legal_actions"],
                    "returns": v.get("returns"),
                    "winners": v.get("winners"),
                    "view": v,
                }
            )

    def make(
        game: str,
        params: GameParams,
        seats: list[str],
        seed: int,
        history: list[int],
        scenario: dict[str, Any] | None = None,
    ):
        adapter_params: dict[str, int] = _to_adapter_params(params)
        if scenario is not None:
            try:
                n: int = load_scenario(scenario).n
            except (ValueError, TypeError, AttributeError, KeyError) as e:
                raise HTTPException(422, f"invalid scenario: {e}") from None
            if params.num_players is not None and params.num_players != n:
                raise HTTPException(
                    422, f"num_players {params.num_players} does not match scenario ({n})"
                )
            adapter_params = {"players": n}
        n_players = adapter_params.get("players", 2)
        for t in seats:
            try:
                check_seat_available(t, n_players)
            except TrainedUnavailable as e:
                raise HTTPException(422, str(e)) from None
        try:
            return store.create(game, adapter_params, seats, seed, history, scenario)
        except IllegalAction as e:
            raise HTTPException(400, f"invalid history: {e}") from None
        except (SessionError, ValueError) as e:
            raise HTTPException(400, str(e)) from None

    @api.post("/games", operation_id="create_game", responses={400: _ERR, 422: _ERR})
    def create_game(req: CreateGameRequest) -> GameView:
        seed = req.seed if req.seed is not None else random.randrange(2**31)
        return render(make(req.game, req.params, list(req.seats), seed, [], req.scenario))

    @api.post("/games/import", operation_id="import_game", responses={400: _ERR, 422: _ERR})
    def import_game(body: GameExport) -> GameView:
        return render(
            make(body.game, body.params, list(body.seats), body.seed, body.history, body.scenario)
        )

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
        with s.lock:
            try:
                s.apply(req.action)
            except IllegalAction as e:
                raise HTTPException(409, str(e)) from None
            return render(s)

    @api.post("/games/{game_id}/back", operation_id="go_back", responses={404: _ERR, 409: _ERR})
    def go_back(game_id: str) -> GameView:
        s = lookup(game_id)
        with s.lock:
            try:
                s.back()
            except CannotGoBack as e:
                raise HTTPException(409, str(e)) from None
            return render(s)

    @api.post(
        "/games/{game_id}/bots/retry",
        operation_id="retry_bots",
        responses={404: _ERR, 409: _ERR},
    )
    def retry_bots(game_id: str) -> GameView:
        s = lookup(game_id)
        with s.lock:
            try:
                s.retry_bots()
            except IllegalAction as e:
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
        with s.lock:
            try:
                s.rewind(req.player_actions)
            except SessionError as e:
                raise HTTPException(400, str(e)) from None
            return render(s)

    @api.get(
        "/games/{game_id}/export",
        operation_id="export_game",
        responses={404: _ERR},
        response_model_exclude_unset=True,
    )
    def export_game(game_id: str) -> GameExport:
        s = lookup(game_id)
        with s.lock:
            seats: list[str] = list(s.seats)
            data: dict[str, Any] = {
                "game": GAME_NAME,
                "params": _from_adapter_params(s),
                "seats": seats,
                "seed": s.seed,
                "history": list(s.history),
            }
            if s.scenario is not None:  # omitted for plain games (keeps old exports unchanged)
                data["scenario"] = s.scenario
            return GameExport.model_validate(data)

    @api.post("/games/{game_id}/report", operation_id="report_game", responses={404: _ERR})
    def report_game(game_id: str, req: ReportRequest) -> ReportResponse:
        s = lookup(game_id)
        with s.lock:
            export = export_game(game_id)
            report_id, path = write_report(
                reports_path,
                {
                    "note": req.note,
                    "category": req.category,
                    "session_id": s.id,
                    "game": export.game,
                    "params": export.params.model_dump(),
                    "seats": list(export.seats),
                    "seed": export.seed,
                    "export": export.model_dump(exclude_unset=True),
                    "view": render(s).model_dump(),
                    "history": list(s.history),
                },
            )
            return ReportResponse(report_id=report_id, path=str(path))

    app = FastAPI(title="King is Dead server")
    app.include_router(api)
    return app


app = create_app(dev_mode=bool(os.environ.get("KID_DEV")))
