"""/api/relationships endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from .. import repository
from ..database import get_session

router = APIRouter(tags=["relationships"])


@router.get("/relationships")
def list_relationships(
    page: int = Query(1, ge=1),
    page_size: int | None = Query(None, ge=1),
    predicate: str | None = None,
    review_status: str | None = None,
    q: str | None = None,
    session: Session = Depends(get_session),
) -> dict:
    return repository.list_relationships(
        session, page=page, page_size=page_size, predicate=predicate,
        review_status=review_status, q=q).to_dict()


@router.get("/relationships/filters")
def relationship_filters(session: Session = Depends(get_session)) -> dict:
    return repository.relationship_filter_options(session)


@router.post("/relationships/{rel_id}/review")
def review_relationship(
    rel_id: int,
    action: str = Body(..., embed=True),
    note: str | None = Body(None, embed=True),
    session: Session = Depends(get_session),
) -> dict:
    ok = repository.review_relationship(session, rel_id, action, note=note)
    if not ok:
        raise HTTPException(400, "Invalid relationship or action")
    return {"ok": True, "relationship_id": rel_id, "action": action.upper()}
