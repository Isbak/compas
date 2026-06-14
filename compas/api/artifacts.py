"""/api/artifacts endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from .. import repository
from ..database import get_session

router = APIRouter(tags=["artifacts"])


@router.get("/artifacts")
def list_artifacts(
    page: int = Query(1, ge=1),
    page_size: int | None = Query(None, ge=1),
    file_type: str | None = None,
    status: str | None = None,
    domain: str | None = None,
    q: str | None = None,
    session: Session = Depends(get_session),
) -> dict:
    return repository.list_artifacts(
        session, page=page, page_size=page_size, file_type=file_type,
        status=status, domain=domain, q=q).to_dict()


@router.get("/artifacts/filters")
def artifact_filters(session: Session = Depends(get_session)) -> dict:
    return repository.artifact_filter_options(session)


@router.get("/artifacts/{artifact_id}")
def get_artifact(artifact_id: str, session: Session = Depends(get_session)) -> dict:
    art = repository.get_artifact(session, artifact_id)
    if art is None:
        raise HTTPException(404, "Artifact not found")
    return art


@router.get("/artifacts/{artifact_id}/evidence")
def artifact_evidence(
    artifact_id: str, page: int = Query(1, ge=1),
    session: Session = Depends(get_session),
) -> dict:
    return repository.list_evidence(
        session, artifact_id=artifact_id, page=page).to_dict()
