"""Remaining REST endpoints: evidence, domains, search, notifications,
observability, health, fuseki and dashboard stats."""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Query
from sqlalchemy.orm import Session

from .. import fuseki, repository
from ..database import get_session

router = APIRouter(tags=["misc"])


# --- Dashboard ----------------------------------------------------------- #
@router.get("/stats")
def stats(session: Session = Depends(get_session)) -> dict:
    return {
        "stats": repository.dashboard_stats(session),
        "domains": repository.domain_overview(session),
        "growth": repository.knowledge_growth_trend(session),
        "recent_changes": repository.recent_changes(session),
    }


# --- Evidence ------------------------------------------------------------ #
@router.get("/evidence")
def evidence(
    page: int = Query(1, ge=1),
    object_id: str | None = None,
    artifact_id: str | None = None,
    session: Session = Depends(get_session),
) -> dict:
    return repository.list_evidence(
        session, page=page, object_id=object_id, artifact_id=artifact_id).to_dict()


# --- Domains ------------------------------------------------------------- #
@router.get("/domains")
def domains(session: Session = Depends(get_session)) -> dict:
    return {"domains": repository.domain_overview(session)}


@router.get("/domains/{domain}")
def domain_detail(domain: str, session: Session = Depends(get_session)) -> dict:
    return repository.get_domain(session, domain)


# --- Search -------------------------------------------------------------- #
@router.get("/search")
def search(
    q: str = Query(..., min_length=1),
    limit: int = Query(30, ge=1, le=100),
    session: Session = Depends(get_session),
) -> dict:
    return repository.search(session, q, limit=limit)


# --- Notifications ------------------------------------------------------- #
@router.get("/notifications")
def notifications(session: Session = Depends(get_session)) -> dict:
    items = repository.notifications(session)
    return {"notifications": items, "count": len(items)}


# --- Observability ------------------------------------------------------- #
@router.get("/observability")
def observability(session: Session = Depends(get_session)) -> dict:
    data = repository.observability(session)
    data["fuseki"] = fuseki.status()
    return data


# --- Fuseki / SPARQL ----------------------------------------------------- #
@router.get("/fuseki/status")
def fuseki_status() -> dict:
    return fuseki.status()


@router.post("/fuseki/query")
def fuseki_query(sparql: str = Body(..., embed=True)) -> dict:
    return fuseki.query(sparql)
