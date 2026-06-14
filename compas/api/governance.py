"""/api/governance endpoints — review queues, alerts, knowledge health."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import repository
from ..database import get_session

router = APIRouter(tags=["governance"])


@router.get("/governance")
def governance(session: Session = Depends(get_session)) -> dict:
    return repository.governance_center(session)


@router.get("/governance/alerts")
def alerts(status: str = "OPEN", session: Session = Depends(get_session)) -> dict:
    return {"alerts": repository.list_alerts(session, status=status)}


@router.post("/governance/alerts/{alert_id}/resolve")
def resolve_alert(alert_id: int, session: Session = Depends(get_session)) -> dict:
    if not repository.resolve_alert(session, alert_id):
        raise HTTPException(404, "Alert not found")
    return {"ok": True, "alert_id": alert_id}


@router.get("/governance/health")
def health(session: Session = Depends(get_session)) -> dict:
    return repository.knowledge_health(session)
