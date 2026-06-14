"""/api/graph endpoints — incremental graph payloads and path finding."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from .. import repository
from ..database import get_session

router = APIRouter(tags=["graph"])


@router.get("/graph")
def graph(
    mode: str = Query("all"),
    focus: str | None = None,
    depth: int = Query(1, ge=0, le=4),
    min_confidence: float = Query(0.0, ge=0.0, le=1.0),
    limit: int | None = Query(None, ge=1),
    session: Session = Depends(get_session),
) -> dict:
    return repository.graph_payload(
        session, mode=mode, focus=focus, depth=depth,
        min_confidence=min_confidence, limit=limit)


@router.get("/graph/neighbors/{object_id}")
def neighbors(
    object_id: str, depth: int = Query(1, ge=1, le=3),
    session: Session = Depends(get_session),
) -> dict:
    return repository.graph_payload(session, focus=object_id, depth=depth)


@router.get("/graph/path")
def path(
    source: str, target: str, session: Session = Depends(get_session),
) -> dict:
    return repository.shortest_path(session, source, target)


@router.get("/graph/objects")
def objects(session: Session = Depends(get_session)) -> list[dict]:
    return repository.list_object_names(session)
