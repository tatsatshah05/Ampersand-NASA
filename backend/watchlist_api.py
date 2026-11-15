"""The watchlist's web routes (see backend/watchlist.py). Included by backend/app.py."""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel, Field

from . import watchlist, watchlist_pictures

log = logging.getLogger("backend.watchlist_api")
router = APIRouter(prefix="/api/watchlist")


class VoteBody(BaseModel):
    answer: str = Field(..., max_length=20)
    note: str | None = Field(None, max_length=2000)   # the exact limit (280) is checked, with a plain message
    voter: str = Field(..., max_length=64)


def _refuse(e: watchlist.WatchlistError) -> HTTPException:
    return HTTPException(e.status, e.message)


def _base(request: Request) -> str:
    return str(request.base_url).rstrip("/")


@router.get("")
def list_watchlist(group: str | None = Query(None, description="eyes, known or artefact"),
                   kind: str | None = Query(None, description="mover or changer"),
                   limit: int = Query(20, ge=1, le=200), offset: int = Query(0, ge=0),
                   x_voter: str | None = Header(None)) -> dict[str, Any]:
    """The candidates, in the machine's order, each with vote tallies and (for brightness changes) NEOWISE's reading."""
    try:
        return watchlist.list_rows(group, kind, limit, offset, x_voter)
    except watchlist.WatchlistError as e:
        raise _refuse(e) from e


# The export routes come before /{candidate_id}, which would otherwise take "export.csv" as an id.
@router.get("/export.csv")
def export_csv(request: Request) -> Response:
    text = watchlist.export_csv(_base(request))
    return Response(text, media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="spherex-watchlist.csv"'})


@router.get("/export.json")
def export_json(request: Request) -> JSONResponse:
    return JSONResponse(watchlist.export_json(_base(request)),
                        headers={"Content-Disposition": 'attachment; filename="spherex-watchlist.json"'})


@router.get("/{candidate_id}")
def one_candidate(candidate_id: str, x_voter: str | None = Header(None)) -> dict[str, Any]:
    try:
        return watchlist.get_row(candidate_id, x_voter)
    except watchlist.WatchlistError as e:
        raise _refuse(e) from e


@router.post("/{candidate_id}/vote")
def cast_vote(candidate_id: str, body: VoteBody) -> dict[str, Any]:
    """An opinion, not a confirmation: real, artefact or unsure, with an optional note. Voting again replaces it."""
    try:
        return watchlist.vote(candidate_id, body.answer, body.note, body.voter)
    except watchlist.WatchlistError as e:
        raise _refuse(e) from e


@router.get("/{candidate_id}/picture.png")
def picture(candidate_id: str) -> FileResponse:
    """The candidate's picture strip, made from images already on this server; 404 if they are not here."""
    try:
        row = watchlist.get_row(candidate_id)
    except watchlist.WatchlistError as e:
        raise _refuse(e) from e
    patch = row.get("patch")
    detector = row.get("best_detector")
    if not patch or not detector:
        raise HTTPException(404, "No picture: this candidate does not say which patch and detector it came from.")
    try:
        path = watchlist_pictures.build(candidate_id, row["ra"], row["dec"], patch, int(detector))
    except Exception as e:  # noqa: BLE001 - a picture that cannot be made is "no picture", logged in full
        log.exception("picture for %s failed", candidate_id)
        raise HTTPException(404, "No picture: it could not be made from the images on this server.") from e
    if path is None:
        raise HTTPException(404, "No picture: the SPHEREx images of this patch are not stored on this server.")
    return FileResponse(path, media_type="image/png", headers={"Cache-Control": "public, max-age=3600"})
