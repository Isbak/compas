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
from fastapi.responses import HTMLResponse, JSONResponse, Response
from markupsafe import escape

from .. import service
from ..config import get_settings
from ..navigate_client import (
    ARTIFACT_ACTIONS,
    ASSESSMENT_ACTIONS,
    KNOWLEDGE_ACTIONS,
    RELATIONSHIP_ACTIONS,
    NavigateClient,
    NavigateError,
    get_client,
)
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
    if action not in ARTIFACT_ACTIONS:
        return HTMLResponse("Unknown action", status_code=400)
    try:
        job = client.artifact_action(artifact_id, action)
    except NavigateError as exc:
        return HTMLResponse(
            f'<span class="badge badge-rejected">{escape(str(exc))}</span>',
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
    if action.lower() not in KNOWLEDGE_ACTIONS:
        return HTMLResponse("Unknown action", status_code=400)
    try:
        service.review_object(client, object_id, action)
        obj = service.get_knowledge(client, object_id)
    except NavigateError as exc:
        return HTMLResponse(
            f'<span class="badge badge-rejected">{escape(str(exc))}</span>',
            status_code=502)
    return render("partials/object_status.html", _ctx(request, obj=obj))


@router.get("/knowledge/{object_id}/history", response_class=HTMLResponse)
def knowledge_history(
    request: Request, object_id: str, client: NavigateClient = Depends(get_client)
):
    """Lazy-loaded lifecycle / change history (HTMX fragment)."""
    try:
        history = service.object_history(client, object_id)
    except NavigateError as exc:
        return _error_page(request, exc)
    return render("partials/object_history.html",
                  _ctx(request, history=history))


@router.post("/knowledge/{object_id}/assign-owner", response_class=HTMLResponse)
def knowledge_assign_owner(
    request: Request, object_id: str, owner_id: str = Form(...),
    owner_type: str = Form("team"), client: NavigateClient = Depends(get_client),
):
    owner_id = owner_id.strip()
    if not owner_id:
        return HTMLResponse(
            '<span class="badge badge-rejected">Owner is required</span>',
            status_code=400)
    try:
        service.assign_owner(client, object_id, owner_type=owner_type,
                             owner_id=owner_id)
    except NavigateError as exc:
        return HTMLResponse(
            f'<span class="badge badge-rejected">{escape(str(exc))}</span>',
            status_code=502)
    return HTMLResponse(
        f'<span class="badge badge-active">Owner set · '
        f'{escape(owner_id)}</span>')


@router.post("/knowledge/{object_id}/flag", response_class=HTMLResponse)
def knowledge_flag(
    request: Request, object_id: str, client: NavigateClient = Depends(get_client)
):
    try:
        service.flag_object(client, object_id)
    except NavigateError as exc:
        return HTMLResponse(
            f'<span class="badge badge-rejected">{escape(str(exc))}</span>',
            status_code=502)
    return HTMLResponse(
        '<span class="badge badge-warning">Flagged for review</span>')


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
            client, page=page, predicate=predicate, review_status=review_status,
            search=q)
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
    action = action.lower()
    if action not in RELATIONSHIP_ACTIONS:
        return HTMLResponse("Unknown action", status_code=400)
    try:
        service.review_relationship(client, rel_id, action)
    except NavigateError as exc:
        return HTMLResponse(
            f'<span class="badge badge-rejected">{escape(str(exc))}</span>',
            status_code=502)
    status = {"approve": "APPROVED", "reject": "REJECTED",
              "archive": "ARCHIVED"}[action]
    return HTMLResponse(
        f'<span class="badge badge-{status.lower()}">{status.title()}</span>')


# --------------------------------------------------------------------------- #
# Compliance & standards
# --------------------------------------------------------------------------- #
def _status_badge(status: str) -> HTMLResponse:
    return HTMLResponse(
        f'<span class="badge badge-{status.lower()}">{status.title()}</span>')


#: Action → resulting knowledge-object status, for the optimistic badge swap.
_REVIEW_STATUS = {"approve": "APPROVED", "reject": "REJECTED",
                  "archive": "ARCHIVED"}


@router.get("/compliance", response_class=HTMLResponse)
def compliance(request: Request, client: NavigateClient = Depends(get_client)):
    try:
        data = service.compliance_home(client)
    except NavigateError as exc:
        return _error_page(request, exc)
    return render("pages/compliance.html",
                  _ctx(request, nav="compliance", data=data))


@router.get("/compliance/standards", response_class=HTMLResponse)
def standards(request: Request, client: NavigateClient = Depends(get_client)):
    try:
        items = service.list_standards(client)
    except NavigateError as exc:
        return _error_page(request, exc)
    ctx = _ctx(request, nav="standards", standards=items)
    if request.headers.get("HX-Request"):
        return render("partials/standards_table.html", ctx)
    return render("pages/standards.html", ctx)


@router.get("/compliance/standards/{object_id}", response_class=HTMLResponse)
def standard_detail(
    request: Request, object_id: str, client: NavigateClient = Depends(get_client)
):
    try:
        std = service.get_standard(client, object_id)
    except NavigateError as exc:
        return _error_page(request, exc)
    if std is None:
        return render("pages/not_found.html", _ctx(request, what="Standard"),
                      status_code=404)
    return render("pages/standard_detail.html",
                  _ctx(request, nav="standards", std=std))


@router.get("/compliance/requirements", response_class=HTMLResponse)
def requirements(
    request: Request, page: int = 1, standard: str | None = None,
    client: NavigateClient = Depends(get_client),
):
    try:
        page_obj = service.list_requirements(client, page=page, standard=standard)
    except NavigateError as exc:
        return _error_page(request, exc)
    ctx = _ctx(request, nav="requirements", page_obj=page_obj,
               filters=service.compliance_filter_options(client),
               active={"standard": standard})
    if request.headers.get("HX-Request"):
        return render("partials/requirements_table.html", ctx)
    return render("pages/requirements.html", ctx)


@router.get("/compliance/requirements/{object_id}", response_class=HTMLResponse)
def requirement_detail(
    request: Request, object_id: str, client: NavigateClient = Depends(get_client)
):
    try:
        req = service.get_requirement(client, object_id)
    except NavigateError as exc:
        return _error_page(request, exc)
    if req is None:
        return render("pages/not_found.html", _ctx(request, what="Requirement"),
                      status_code=404)
    return render("pages/requirement_detail.html",
                  _ctx(request, nav="requirements", req=req))


@router.get("/compliance/equations", response_class=HTMLResponse)
def equations(
    request: Request, page: int = 1, standard: str | None = None,
    client: NavigateClient = Depends(get_client),
):
    try:
        page_obj = service.list_equations(client, page=page, standard=standard)
    except NavigateError as exc:
        return _error_page(request, exc)
    ctx = _ctx(request, nav="equations", page_obj=page_obj,
               filters=service.compliance_filter_options(client),
               active={"standard": standard})
    if request.headers.get("HX-Request"):
        return render("partials/equations_table.html", ctx)
    return render("pages/equations.html", ctx)


@router.get("/compliance/equations/{object_id}", response_class=HTMLResponse)
def equation_detail(
    request: Request, object_id: str, client: NavigateClient = Depends(get_client)
):
    try:
        eq = service.get_equation(client, object_id)
    except NavigateError as exc:
        return _error_page(request, exc)
    if eq is None:
        return render("pages/not_found.html", _ctx(request, what="Equation"),
                      status_code=404)
    return render("pages/equation_detail.html",
                  _ctx(request, nav="equations", eq=eq))


@router.get("/compliance/gaps", response_class=HTMLResponse)
def gaps(request: Request, client: NavigateClient = Depends(get_client)):
    try:
        items = service.list_gaps(client)
    except NavigateError as exc:
        return _error_page(request, exc)
    return render("pages/gaps.html", _ctx(request, nav="gaps", gaps=items))


@router.get("/compliance/assessments", response_class=HTMLResponse)
def assessments(
    request: Request, status: str | None = None,
    client: NavigateClient = Depends(get_client),
):
    try:
        items = service.list_assessments(client, status=status)
    except NavigateError as exc:
        return _error_page(request, exc)
    ctx = _ctx(request, nav="assessments", assessments=items,
               filters=service.compliance_filter_options(client),
               active={"status": status})
    if request.headers.get("HX-Request"):
        return render("partials/assessments_table.html", ctx)
    return render("pages/assessments.html", ctx)


# Declared before the generic ``/compliance/{kind}/.../review`` so the
# assessment route (which uses Navigate's dedicated endpoint) wins the match.
@router.post("/compliance/assessments/{assessment_id}/review",
             response_class=HTMLResponse)
def assessment_review(
    request: Request, assessment_id: int, action: str = Form(...),
    client: NavigateClient = Depends(get_client),
):
    action = action.lower()
    if action not in ASSESSMENT_ACTIONS:
        return HTMLResponse("Unknown action", status_code=400)
    try:
        service.review_assessment(client, assessment_id, action)
    except NavigateError as exc:
        return HTMLResponse(
            f'<span class="badge badge-rejected">{escape(str(exc))}</span>',
            status_code=502)
    return _status_badge({"approve": "APPROVED", "reject": "REJECTED"}[action])


@router.post("/compliance/{kind}/{object_id}/review", response_class=HTMLResponse)
def compliance_review(
    request: Request, kind: str, object_id: str, action: str = Form(...),
    client: NavigateClient = Depends(get_client),
):
    action = action.lower()
    if kind not in ("standards", "requirements", "equations"):
        return HTMLResponse("Unknown resource", status_code=400)
    if action not in KNOWLEDGE_ACTIONS:
        return HTMLResponse("Unknown action", status_code=400)
    try:
        service.review_object(client, object_id, action)
    except NavigateError as exc:
        return HTMLResponse(
            f'<span class="badge badge-rejected">{escape(str(exc))}</span>',
            status_code=502)
    return _status_badge(_REVIEW_STATUS[action])


@router.post("/compliance/assess", response_class=HTMLResponse)
def compliance_assess(
    request: Request, client: NavigateClient = Depends(get_client)
):
    try:
        job = client.compliance_assess()
    except NavigateError as exc:
        return HTMLResponse(
            f'<span class="badge badge-rejected">{escape(str(exc))}</span>',
            status_code=502)
    return HTMLResponse(
        f'<span class="badge badge-info">Job #{job.get("id")} '
        f'{job.get("status", "queued")}</span>')


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


#: Resources that support Navigate's confidence-banded bulk approval.
BULK_APPROVE_KINDS = frozenset({"knowledge", "relationships"})


@router.get("/governance/changes", response_class=HTMLResponse)
def governance_changes(
    request: Request, client: NavigateClient = Depends(get_client)
):
    """Lazy-loaded recent change-log panel (HTMX fragment)."""
    try:
        changes = service.recent_changes(client)
    except NavigateError as exc:
        return _error_page(request, exc)
    return render("partials/changes_table.html",
                  _ctx(request, changes=changes))


@router.get("/governance/growth", response_class=HTMLResponse)
def governance_growth(
    request: Request, client: NavigateClient = Depends(get_client)
):
    """Lazy-loaded growth-trend panel (HTMX fragment)."""
    try:
        growth = service.growth_trend(client)
    except NavigateError as exc:
        return _error_page(request, exc)
    return render("partials/growth.html", _ctx(request, growth=growth))


@router.post("/governance/approve-confidence/{kind}",
             response_class=HTMLResponse)
def governance_bulk_approve(
    request: Request, kind: str, min_confidence: float = Form(...),
    max_confidence: float = Form(1.0), include_reviewed: bool = Form(False),
    client: NavigateClient = Depends(get_client),
):
    if kind not in BULK_APPROVE_KINDS:
        return HTMLResponse("Unknown resource", status_code=400)
    lo = _clamp_confidence(min_confidence)
    hi = _clamp_confidence(max_confidence)
    try:
        result = service.bulk_approve_confidence(
            client, kind=kind, min_confidence=lo, max_confidence=hi,
            include_reviewed=include_reviewed)
    except NavigateError as exc:
        return HTMLResponse(
            f'<span class="badge badge-rejected">{escape(str(exc))}</span>',
            status_code=502)
    count = (result or {}).get(
        "objects_approved" if kind == "knowledge" else "relationships_approved", 0)
    return HTMLResponse(
        f'<span class="badge badge-approved">Approved {count} '
        f'{"objects" if kind == "knowledge" else "relationships"}</span>')


# --------------------------------------------------------------------------- #
# Cost / LLM usage
# --------------------------------------------------------------------------- #
@router.get("/costs", response_class=HTMLResponse)
def costs(request: Request, client: NavigateClient = Depends(get_client)):
    try:
        data = service.cost_overview(client)
    except NavigateError as exc:
        return _error_page(request, exc)
    return render("pages/cost.html", _ctx(request, nav="costs", data=data))


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


#: Hard cap on graph traversal depth requested from the browser, to bound how
#: far an expansion can fan out across Navigate's /graph endpoints.
MAX_GRAPH_DEPTH = 5


def _clamp_depth(depth: int) -> int:
    return max(1, min(depth, MAX_GRAPH_DEPTH))


def _clamp_confidence(value: float) -> float:
    return max(0.0, min(value, 1.0))


@router.get("/graph/data")
def graph_data(
    mode: str = "all", focus: str | None = None, depth: int = 1,
    min_confidence: float = 0.0, client: NavigateClient = Depends(get_client),
):
    try:
        return JSONResponse(service.graph_payload(
            client, mode=mode, focus=focus, depth=_clamp_depth(depth),
            min_confidence=_clamp_confidence(min_confidence)))
    except NavigateError as exc:
        return JSONResponse({"error": str(exc)}, status_code=502)


@router.get("/graph/neighbors/{object_id}")
def graph_neighbors(
    object_id: str, depth: int = 1, client: NavigateClient = Depends(get_client)
):
    try:
        return JSONResponse(service.graph_payload(
            client, focus=object_id, depth=_clamp_depth(depth)))
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


#: Graph export formats Compas proxies → (client method, download filename).
_GRAPH_EXPORTS = {
    "gexf": ("graph_export_gexf", "navigate-graph.gexf"),
    "graphml": ("graph_export_graphml", "navigate-graph.graphml"),
}


@router.get("/graph/export/{fmt}")
def graph_export(
    fmt: str, client: NavigateClient = Depends(get_client)
):
    """Proxy Navigate's GEXF/GraphML export, server-side, as a download.

    Proxying (rather than linking the browser straight at Navigate) keeps the
    API key server-side, in line with Compas's local-first model.
    """
    spec = _GRAPH_EXPORTS.get(fmt)
    if spec is None:
        return JSONResponse({"error": "Unknown format"}, status_code=400)
    method, filename = spec
    try:
        content, content_type = getattr(client, method)()
    except NavigateError as exc:
        return JSONResponse({"error": str(exc)}, status_code=502)
    return Response(content, media_type=content_type, headers={
        "Content-Disposition": f'attachment; filename="{filename}"'})


#: RDF serialisations Navigate offers → download extension.
_RDF_FORMATS = {"turtle": "ttl", "json-ld": "jsonld", "nt": "nt"}


@router.get("/rdf/export")
def rdf_export(
    fmt: str = "turtle", client: NavigateClient = Depends(get_client)
):
    """Proxy Navigate's RDF export (Turtle / JSON-LD / N-Triples) as a download."""
    if fmt not in _RDF_FORMATS:
        return JSONResponse({"error": "Unknown format"}, status_code=400)
    try:
        content, content_type = client.rdf_export(fmt=fmt)
    except NavigateError as exc:
        return JSONResponse({"error": str(exc)}, status_code=502)
    filename = f"navigate.{_RDF_FORMATS[fmt]}"
    return Response(content, media_type=content_type, headers={
        "Content-Disposition": f'attachment; filename="{filename}"'})


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
    modes = [{"value": m, "label": service.ASK_MODE_LABELS[m],
              "two_term": m in service.TWO_TERM_MODES}
             for m in service.ASK_MODES]
    return render("pages/graphrag.html",
                  _ctx(request, nav="graphrag", suggestions=suggestions,
                       modes=modes))


@router.post("/graphrag/ask", response_class=HTMLResponse)
def graphrag_ask(
    request: Request, question: str = Form(...), mode: str = Form("ask"),
    term_b: str | None = Form(None),
    client: NavigateClient = Depends(get_client),
):
    if mode not in service.ASK_MODES:
        mode = "ask"
    answer = service.ask(client, question, mode=mode, term_b=term_b)
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
