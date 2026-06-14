"""HTMX page + partial routes.

Full-page requests render ``base.html`` with the page content. HTMX requests
(``HX-Request`` header) that target a table/region return just the relevant
partial, keeping payloads small and interactions snappy.

All data comes from Navigate's REST API via :mod:`compas.service`. Compas
builds no API of its own; the browser only ever talks to Compas, which proxies
to Navigate server-side (so the API key never reaches the browser). The handful
of JSON view-helpers below (graph data / path / objects) exist solely to feed
Compas's own graph-explorer widget — they are not a public REST surface.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse

from .. import service
from ..config import get_settings
from ..navigate_client import NavigateClient, NavigateError, get_client
from .templating import render

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


def _error_page(request: Request, exc: NavigateError):
    return render("pages/error.html", _ctx(
        request, nav=None, error=str(exc),
        endpoint=get_settings().navigate_api_url), status_code=502)


# --------------------------------------------------------------------------- #
# Dashboard
# --------------------------------------------------------------------------- #
@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request, client: NavigateClient = Depends(get_client)):
    try:
        ctx = _ctx(
            request, nav="dashboard",
            stats=service.dashboard(client),
            domains=service.domain_overview(client),
            notifications=service.notifications(client, limit=6),
            review_queue=service.governance_center(client)["review_queue"][:6],
        )
    except NavigateError as exc:
        return _error_page(request, exc)
    return render("pages/dashboard.html", ctx)


# --------------------------------------------------------------------------- #
# Artifacts
# --------------------------------------------------------------------------- #
@router.get("/artifacts", response_class=HTMLResponse)
def artifacts(
    request: Request, page: int = 1, file_type: str | None = None,
    status: str | None = None, classification_status: str | None = None,
    q: str | None = None, client: NavigateClient = Depends(get_client),
):
    try:
        page_obj = service.list_artifacts(
            client, page=page, file_type=file_type, scan_status=status,
            classification_status=classification_status, search=q)
    except NavigateError as exc:
        return _error_page(request, exc)
    ctx = _ctx(request, nav="artifacts", page_obj=page_obj,
               filters=service.artifact_filter_options(client),
               active={"file_type": file_type, "status": status,
                       "classification_status": classification_status, "q": q})
    if request.headers.get("HX-Request"):
        return render("partials/artifacts_table.html", ctx)
    return render("pages/artifacts.html", ctx)


@router.get("/artifacts/{artifact_id}", response_class=HTMLResponse)
def artifact_detail(
    request: Request, artifact_id: str, client: NavigateClient = Depends(get_client)
):
    try:
        art = service.get_artifact(client, artifact_id)
    except NavigateError as exc:
        return _error_page(request, exc)
    if art is None:
        return render("pages/not_found.html", _ctx(request, what="Artifact"),
                      status_code=404)
    return render("pages/artifact_detail.html",
                  _ctx(request, nav="artifacts", artifact=art))


@router.post("/artifacts/{artifact_id}/{action}", response_class=HTMLResponse)
def artifact_action(
    request: Request, artifact_id: str, action: str,
    client: NavigateClient = Depends(get_client),
):
    if action not in {"rescan", "extract", "classify"}:
        return HTMLResponse("Unknown action", status_code=400)
    try:
        job = client.artifact_action(artifact_id, action)
    except NavigateError as exc:
        return HTMLResponse(f'<span class="badge badge-rejected">{exc}</span>',
                            status_code=502)
    return HTMLResponse(
        f'<span class="badge badge-info">Job #{job.get("id")} '
        f'{job.get("status", "queued")}</span>')


# --------------------------------------------------------------------------- #
# Knowledge objects
# --------------------------------------------------------------------------- #
@router.get("/knowledge", response_class=HTMLResponse)
def knowledge(
    request: Request, page: int = 1, object_type: str | None = None,
    status: str | None = None, review_state: str | None = None,
    domain: str | None = None, q: str | None = None,
    client: NavigateClient = Depends(get_client),
):
    try:
        page_obj = service.list_knowledge(
            client, page=page, object_type=object_type, status=status,
            review_status=review_state, domain=domain, search=q)
    except NavigateError as exc:
        return _error_page(request, exc)
    ctx = _ctx(request, nav="knowledge", page_obj=page_obj,
               filters=service.knowledge_filter_options(client),
               active={"object_type": object_type, "status": status,
                       "review_state": review_state, "domain": domain, "q": q})
    if request.headers.get("HX-Request"):
        return render("partials/knowledge_table.html", ctx)
    return render("pages/knowledge.html", ctx)


@router.get("/knowledge/{object_id}", response_class=HTMLResponse)
def knowledge_detail(
    request: Request, object_id: str, client: NavigateClient = Depends(get_client)
):
    try:
        obj = service.get_knowledge(client, object_id)
    except NavigateError as exc:
        return _error_page(request, exc)
    if obj is None:
        return render("pages/not_found.html",
                      _ctx(request, what="Knowledge object"), status_code=404)
    return render("pages/knowledge_detail.html",
                  _ctx(request, nav="knowledge", obj=obj))


@router.post("/knowledge/{object_id}/review", response_class=HTMLResponse)
def knowledge_review(
    request: Request, object_id: str, action: str = Form(...),
    client: NavigateClient = Depends(get_client),
):
    try:
        service.review_object(client, object_id, action)
        obj = service.get_knowledge(client, object_id)
    except NavigateError as exc:
        return HTMLResponse(f'<span class="badge badge-rejected">{exc}</span>',
                            status_code=502)
    return render("partials/object_status.html", _ctx(request, obj=obj))


# --------------------------------------------------------------------------- #
# Relationships
# --------------------------------------------------------------------------- #
@router.get("/relationships", response_class=HTMLResponse)
def relationships(
    request: Request, page: int = 1, predicate: str | None = None,
    review_status: str | None = None, q: str | None = None,
    client: NavigateClient = Depends(get_client),
):
    try:
        page_obj = service.list_relationships(
            client, page=page, predicate=predicate, review_status=review_status)
    except NavigateError as exc:
        return _error_page(request, exc)
    ctx = _ctx(request, nav="relationships", page_obj=page_obj,
               filters=service.relationship_filter_options(client),
               active={"predicate": predicate, "review_status": review_status,
                       "q": q})
    if request.headers.get("HX-Request"):
        return render("partials/relationships_table.html", ctx)
    return render("pages/relationships.html", ctx)


@router.post("/relationships/{rel_id}/review", response_class=HTMLResponse)
def relationship_review(
    request: Request, rel_id: int, action: str = Form(...),
    client: NavigateClient = Depends(get_client),
):
    try:
        service.review_relationship(client, rel_id, action)
    except NavigateError as exc:
        return HTMLResponse(f'<span class="badge badge-rejected">{exc}</span>',
                            status_code=502)
    return HTMLResponse(
        f'<span class="badge badge-{action.lower()}">{action.upper()}D</span>')


# --------------------------------------------------------------------------- #
# Domains
# --------------------------------------------------------------------------- #
@router.get("/domains", response_class=HTMLResponse)
def domains(request: Request, client: NavigateClient = Depends(get_client)):
    try:
        data = service.domain_overview(client)
    except NavigateError as exc:
        return _error_page(request, exc)
    return render("pages/domains.html",
                  _ctx(request, nav="domains", domains=data))


@router.get("/domains/{domain}", response_class=HTMLResponse)
def domain_detail(
    request: Request, domain: str, client: NavigateClient = Depends(get_client)
):
    try:
        data = service.get_domain(client, domain)
    except NavigateError as exc:
        return _error_page(request, exc)
    return render("pages/domain_detail.html",
                  _ctx(request, nav="domains", domain=data))


# --------------------------------------------------------------------------- #
# Governance
# --------------------------------------------------------------------------- #
@router.get("/governance", response_class=HTMLResponse)
def governance(request: Request, client: NavigateClient = Depends(get_client)):
    try:
        ctx = _ctx(request, nav="governance",
                   data=service.governance_center(client),
                   health=service.knowledge_health(client))
    except NavigateError as exc:
        return _error_page(request, exc)
    return render("pages/governance.html", ctx)


# --------------------------------------------------------------------------- #
# Graph explorer (page + JSON view-helpers for the explorer widget)
# --------------------------------------------------------------------------- #
@router.get("/graph", response_class=HTMLResponse)
def graph(request: Request, client: NavigateClient = Depends(get_client)):
    try:
        objects = service.list_object_names(client)
    except NavigateError as exc:
        return _error_page(request, exc)
    return render("pages/graph.html", _ctx(
        request, nav="graph", objects=objects,
        modes=["all", "capability", "technology", "decision", "team", "process"]))


@router.get("/graph/data")
def graph_data(
    mode: str = "all", focus: str | None = None, depth: int = 1,
    min_confidence: float = 0.0, client: NavigateClient = Depends(get_client),
):
    try:
        return JSONResponse(service.graph_payload(
            client, mode=mode, focus=focus, depth=depth,
            min_confidence=min_confidence))
    except NavigateError as exc:
        return JSONResponse({"error": str(exc)}, status_code=502)


@router.get("/graph/neighbors/{object_id}")
def graph_neighbors(
    object_id: str, depth: int = 1, client: NavigateClient = Depends(get_client)
):
    try:
        return JSONResponse(service.graph_payload(client, focus=object_id, depth=depth))
    except NavigateError as exc:
        return JSONResponse({"error": str(exc)}, status_code=502)


@router.get("/graph/path")
def graph_path(
    source: str, target: str, client: NavigateClient = Depends(get_client)
):
    try:
        return JSONResponse(service.shortest_path(client, source, target))
    except NavigateError as exc:
        return JSONResponse({"error": str(exc)}, status_code=502)


@router.get("/graph/object/{object_id}")
def graph_object(object_id: str, client: NavigateClient = Depends(get_client)):
    try:
        obj = service.get_knowledge(client, object_id)
    except NavigateError as exc:
        return JSONResponse({"error": str(exc)}, status_code=502)
    if obj is None:
        return JSONResponse({"error": "not found"}, status_code=404)
    return JSONResponse(obj)


# --------------------------------------------------------------------------- #
# GraphRAG
# --------------------------------------------------------------------------- #
@router.get("/graphrag", response_class=HTMLResponse)
def graphrag_page(request: Request):
    suggestions = [
        "What supports Release Governance?",
        "What capabilities depend on Salesforce?",
        "What risks affect Release Management?",
        "Who owns Release Management?",
        "What is related to Cloud Migration?",
    ]
    return render("pages/graphrag.html",
                  _ctx(request, nav="graphrag", suggestions=suggestions))


@router.post("/graphrag/ask", response_class=HTMLResponse)
def graphrag_ask(
    request: Request, question: str = Form(...),
    client: NavigateClient = Depends(get_client),
):
    answer = service.ask(client, question)
    return render("partials/graphrag_answer.html",
                  _ctx(request, answer=answer, question=question))


# --------------------------------------------------------------------------- #
# Observability
# --------------------------------------------------------------------------- #
@router.get("/observability", response_class=HTMLResponse)
def observability(request: Request, client: NavigateClient = Depends(get_client)):
    try:
        data = service.observability(client)
    except NavigateError as exc:
        return _error_page(request, exc)
    return render("pages/observability.html",
                  _ctx(request, nav="observability", data=data))


# --------------------------------------------------------------------------- #
# Settings
# --------------------------------------------------------------------------- #
@router.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request, client: NavigateClient = Depends(get_client)):
    health = None
    try:
        health = client.health()
    except NavigateError as exc:
        health = {"status": "unreachable", "message": str(exc)}
    return render("pages/settings.html",
                  _ctx(request, nav="settings", health=health))


# --------------------------------------------------------------------------- #
# Global search + notifications (HTMX partials)
# --------------------------------------------------------------------------- #
@router.get("/search", response_class=HTMLResponse)
def search(request: Request, q: str = "", client: NavigateClient = Depends(get_client)):
    results = None
    if q:
        try:
            results = service.search(client, q)
        except NavigateError:
            results = None
    ctx = _ctx(request, nav="search", q=q, results=results)
    if request.headers.get("HX-Request"):
        return render("partials/search_results.html", ctx)
    return render("pages/search.html", ctx)


@router.get("/notifications", response_class=HTMLResponse)
def notifications(request: Request, client: NavigateClient = Depends(get_client)):
    try:
        items = service.notifications(client)
    except NavigateError:
        items = []
    return render("partials/notifications.html",
                  _ctx(request, notifications=items))
