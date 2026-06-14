"""/api/knowledge endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from .. import repository
from ..database import get_session

router = APIRouter(tags=["knowledge"])


@router.get("/knowledge")
def list_knowledge(
    page: int = Query(1, ge=1),
    page_size: int | None = Query(None, ge=1),
    object_type: str | None = None,
    status: str | None = None,
    review_state: str | None = None,
    domain: str | None = None,
    q: str | None = None,
    sort: str = "quality",
    session: Session = Depends(get_session),
) -> dict:
    return repository.list_knowledge_objects(
        session, page=page, page_size=page_size, object_type=object_type,
        status=status, review_state=review_state, domain=domain, q=q,
        sort=sort).to_dict()


@router.get("/knowledge/filters")
def knowledge_filters(session: Session = Depends(get_session)) -> dict:
    return repository.knowledge_filter_options(session)


@router.get("/knowledge/{object_id}")
def get_knowledge(object_id: str, session: Session = Depends(get_session)) -> dict:
    obj = repository.get_knowledge_object(session, object_id)
    if obj is None:
        raise HTTPException(404, "Knowledge object not found")
    return obj


@router.post("/knowledge/{object_id}/review")
def review_knowledge(
    object_id: str,
    action: str = Body(..., embed=True),
    note: str | None = Body(None, embed=True),
    session: Session = Depends(get_session),
) -> dict:
    ok = repository.review_object(session, object_id, action, note=note)
    if not ok:
        raise HTTPException(400, "Invalid object or action")
    return {"ok": True, "object_id": object_id, "action": action.upper()}
