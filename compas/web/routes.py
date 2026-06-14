"""HTMX page + partial routes.

Full-page requests render ``base.html`` with the page content. HTMX requests
(``HX-Request`` header) that target a table/region return just the relevant
partial, keeping payloads small and interactions snappy.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from .. import fuseki, graphrag as graphrag_service, repository
from ..config import get_settings
from ..database import get_session
from .templating import render, templates

router = APIRouter(include_in_schema=False)


def _ctx(request: Request, **kwargs) -> dict:
    settings = get_settings()
    base = {
        "request": request,
        "settings": settings,
        "app_name": settings.app_name,
        "nav": kwargs.pop("nav", None),
    }
    base.update(kwargs)
    return base


# --------------------------------------------------------------------------- #
# Dashboard
# --------------------------------------------------------------------------- #
@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request, session: Session = Depends(get_session)):
    return render("pages/dashboard.html", _ctx(
        request, nav="dashboard",
        stats=repository.dashboard_stats(session),
        domains=repository.domain_overview(session),
        growth=repository.knowledge_growth_trend(session),
        recent_changes=repository.recent_changes(session),
        notifications=repository.notifications(session, limit=6),
    ))


# --------------------------------------------------------------------------- #
# Artifacts
# --------------------------------------------------------------------------- #
@router.get("/artifacts", response_class=HTMLResponse)
def artifacts(
    request: Request, page: int = 1, file_type: str | None = None,
    status: str | None = None, domain: str | None = None, q: str | None = None,
    session: Session = Depends(get_session),
):
    page_obj = repository.list_artifacts(
        session, page=page, file_type=file_type, status=status,
        domain=domain, q=q)
    ctx = _ctx(request, nav="artifacts", page_obj=page_obj,
               filters=repository.artifact_filter_options(session),
               active={"file_type": file_type, "status": status,
                       "domain": domain, "q": q})
    if request.headers.get("HX-Request"):
        return render("partials/artifacts_table.html", ctx)
    return render("pages/artifacts.html", ctx)


@router.get("/artifacts/{artifact_id}", response_class=HTMLResponse)
def artifact_detail(
    request: Request, artifact_id: str, session: Session = Depends(get_session)
):
    art = repository.get_artifact(session, artifact_id)
    if art is None:
        return render(
            "pages/not_found.html", _ctx(request, what="Artifact"), status_code=404)
    return render("pages/artifact_detail.html", _ctx(
        request, nav="artifacts", artifact=art))


# --------------------------------------------------------------------------- #
# Knowledge objects
# --------------------------------------------------------------------------- #
@router.get("/knowledge", response_class=HTMLResponse)
def knowledge(
    request: Request, page: int = 1, object_type: str | None = None,
    status: str | None = None, review_state: str | None = None,
    domain: str | None = None, q: str | None = None, sort: str = "quality",
    session: Session = Depends(get_session),
):
    page_obj = repository.list_knowledge_objects(
        session, page=page, object_type=object_type, status=status,
        review_state=review_state, domain=domain, q=q, sort=sort)
    ctx = _ctx(request, nav="knowledge", page_obj=page_obj,
               filters=repository.knowledge_filter_options(session),
               active={"object_type": object_type, "status": status,
                       "review_state": review_state, "domain": domain,
                       "q": q, "sort": sort})
    if request.headers.get("HX-Request"):
        return render("partials/knowledge_table.html", ctx)
    return render("pages/knowledge.html", ctx)


@router.get("/knowledge/{object_id}", response_class=HTMLResponse)
def knowledge_detail(
    request: Request, object_id: str, session: Session = Depends(get_session)
):
    obj = repository.get_knowledge_object(session, object_id)
    if obj is None:
        return render(
            "pages/not_found.html", _ctx(request, what="Knowledge object"),
            status_code=404)
    return render("pages/knowledge_detail.html", _ctx(
        request, nav="knowledge", obj=obj))


@router.post("/knowledge/{object_id}/review", response_class=HTMLResponse)
def knowledge_review(
    request: Request, object_id: str, action: str = Form(...),
    session: Session = Depends(get_session),
):
    repository.review_object(session, object_id, action)
    obj = repository.get_knowledge_object(session, object_id)
    return render("partials/object_status.html", _ctx(
        request, obj=obj))


# --------------------------------------------------------------------------- #
# Relationships
# --------------------------------------------------------------------------- #
@router.get("/relationships", response_class=HTMLResponse)
def relationships(
    request: Request, page: int = 1, predicate: str | None = None,
    review_status: str | None = None, q: str | None = None,
    session: Session = Depends(get_session),
):
    page_obj = repository.list_relationships(
        session, page=page, predicate=predicate, review_status=review_status, q=q)
    ctx = _ctx(request, nav="relationships", page_obj=page_obj,
               filters=repository.relationship_filter_options(session),
               active={"predicate": predicate, "review_status": review_status,
                       "q": q})
    if request.headers.get("HX-Request"):
        return render("partials/relationships_table.html", ctx)
    return render("pages/relationships.html", ctx)


@router.post("/relationships/{rel_id}/review", response_class=HTMLResponse)
def relationship_review(
    request: Request, rel_id: int, action: str = Form(...),
    session: Session = Depends(get_session),
):
    repository.review_relationship(session, rel_id, action)
    return HTMLResponse(
        f'<span class="badge badge-{action.lower()}">{action.upper()}D</span>')


# --------------------------------------------------------------------------- #
# Domains
# --------------------------------------------------------------------------- #
@router.get("/domains", response_class=HTMLResponse)
def domains(request: Request, session: Session = Depends(get_session)):
    return render("pages/domains.html", _ctx(
        request, nav="domains", domains=repository.domain_overview(session)))


@router.get("/domains/{domain}", response_class=HTMLResponse)
def domain_detail(request: Request, domain: str, session: Session = Depends(get_session)):
    return render("pages/domain_detail.html", _ctx(
        request, nav="domains", domain=repository.get_domain(session, domain)))


# --------------------------------------------------------------------------- #
# Governance + health
# --------------------------------------------------------------------------- #
@router.get("/governance", response_class=HTMLResponse)
def governance(request: Request, session: Session = Depends(get_session)):
    return render("pages/governance.html", _ctx(
        request, nav="governance",
        data=repository.governance_center(session),
        health=repository.knowledge_health(session)))


# --------------------------------------------------------------------------- #
# Graph explorer
# --------------------------------------------------------------------------- #
@router.get("/graph", response_class=HTMLResponse)
def graph(request: Request, session: Session = Depends(get_session)):
    return render("pages/graph.html", _ctx(
        request, nav="graph",
        objects=repository.list_object_names(session),
        modes=["all", "capability", "technology", "decision", "team",
               "process"]))


# --------------------------------------------------------------------------- #
# GraphRAG
# --------------------------------------------------------------------------- #
@router.get("/graphrag", response_class=HTMLResponse)
def graphrag_page(request: Request, session: Session = Depends(get_session)):
    from ..api.graphrag import SUGGESTED_QUESTIONS
    return render("pages/graphrag.html", _ctx(
        request, nav="graphrag", suggestions=SUGGESTED_QUESTIONS))


@router.post("/graphrag/ask", response_class=HTMLResponse)
def graphrag_ask(
    request: Request, question: str = Form(...),
    session: Session = Depends(get_session),
):
    answer = graphrag_service.ask(session, question)
    return render("partials/graphrag_answer.html", _ctx(
        request, answer=answer, question=question))


# --------------------------------------------------------------------------- #
# Observability
# --------------------------------------------------------------------------- #
@router.get("/observability", response_class=HTMLResponse)
def observability(request: Request, session: Session = Depends(get_session)):
    data = repository.observability(session)
    data["fuseki"] = fuseki.status()
    return render("pages/observability.html", _ctx(
        request, nav="observability", data=data))


# --------------------------------------------------------------------------- #
# Settings
# --------------------------------------------------------------------------- #
@router.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request):
    return render("pages/settings.html", _ctx(
        request, nav="settings", fuseki=fuseki.status()))


# --------------------------------------------------------------------------- #
# Global search + notifications (HTMX partials)
# --------------------------------------------------------------------------- #
@router.get("/search", response_class=HTMLResponse)
def search(request: Request, q: str = "", session: Session = Depends(get_session)):
    results = repository.search(session, q) if q else None
    ctx = _ctx(request, nav="search", q=q, results=results)
    if request.headers.get("HX-Request"):
        return render("partials/search_results.html", ctx)
    return render("pages/search.html", ctx)


@router.get("/notifications", response_class=HTMLResponse)
def notifications(request: Request, session: Session = Depends(get_session)):
    return render("partials/notifications.html", _ctx(
        request, notifications=repository.notifications(session)))
