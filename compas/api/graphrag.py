"""/api/graphrag endpoint — the knowledge assistant."""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends
from sqlalchemy.orm import Session

from .. import graphrag as graphrag_service
from ..database import get_session

router = APIRouter(tags=["graphrag"])

SUGGESTED_QUESTIONS = [
    "What supports Release Governance?",
    "What capabilities depend on Salesforce?",
    "What risks affect Release Management?",
    "Who owns Release Management?",
    "What is related to Cloud Migration?",
]


@router.post("/graphrag")
def ask(
    question: str = Body(..., embed=True),
    session: Session = Depends(get_session),
) -> dict:
    return graphrag_service.ask(session, question)


@router.get("/graphrag/suggestions")
def suggestions() -> dict:
    return {"questions": SUGGESTED_QUESTIONS}
