"""View-model layer.

Turns Navigate API responses (:mod:`compas.navigate_client`) into the shapes
the templates render. No database, no business logic re-implemented — just
fetching, light shaping, and graceful degradation where an older Navigate
doesn't expose a datum (e.g. the domains resource on a pre-upgrade server).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .config import get_settings
from .navigate_client import NavigateClient

PREDICATE_LABELS = {
    "supports": "supports", "depends_on": "depends on",
    "implemented_by": "implemented by", "implements": "implements",
    "owns": "owns", "owned_by": "owned by", "related_to": "related to",
    "affects": "affects", "mentions": "mentions", "references": "references",
}


# --------------------------------------------------------------------------- #
# Pagination
# --------------------------------------------------------------------------- #
@dataclass
class Page:
    items: list[Any]
    total: int
    page: int
    page_size: int

    @property
    def pages(self) -> int:
        return max(1, (self.total + self.page_size - 1) // self.page_size)

    @property
    def has_prev(self) -> bool:
        return self.page > 1

    @property
    def has_next(self) -> bool:
        return self.page < self.pages


def _limits(page: int, page_size: int | None) -> tuple[int, int]:
    s = get_settings()
    size = max(1, min(page_size or s.page_size, s.max_page_size))
    return size, (max(1, page) - 1) * size


def _page(envelope: dict, items: list, page: int, size: int) -> Page:
    return Page(items, envelope.get("total", len(items)), page, size)


def _split_domains(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(v) for v in value]
    return [d.strip() for d in str(value).split(",") if d.strip()]


# --------------------------------------------------------------------------- #
# Dashboard
# --------------------------------------------------------------------------- #
def dashboard(client: NavigateClient) -> dict:
    stats = client.stats()
    total_objs = stats.get("knowledge_object_count", 0)
    try:
        approved = client.list_knowledge(limit=1, offset=0, status="APPROVED")\
            .get("total", 0)
    except Exception:
        approved = 0
    try:
        quality = client.gov_quality().get("average_quality")
    except Exception:
        quality = None
    return {
        "total_artifacts": stats.get("artifact_count", 0),
        "knowledge_objects": total_objs,
        "relationships": stats.get("relationship_count", 0),
        "evidence_count": stats.get("evidence_count", 0),
        "links": stats.get("link_count", 0),
        "approved_objects": approved,
        "pending_reviews": stats.get("pending_review_count", 0),
        "stale_knowledge": stats.get("stale_object_count", 0),
        "quality_score": round(quality, 1) if quality is not None else 0.0,
        "approved_pct": round(100 * approved / total_objs, 1) if total_objs else 0.0,
        "last_scan": stats.get("last_scan"),
    }


def notifications(client: NavigateClient, limit: int = 15) -> list[dict]:
    try:
        alerts = client.gov_alerts() or []
    except Exception:
        return []
    items = [{
        "kind": a.get("alert_type"), "severity": a.get("severity", "INFO"),
        "message": a.get("message"), "object_id": a.get("object_id"),
        "object_name": a.get("object_id"), "created_at": a.get("created_at"),
    } for a in alerts]
    items.sort(key=lambda i: i.get("created_at") or "", reverse=True)
    return items[:limit]


# --------------------------------------------------------------------------- #
# Artifacts
# --------------------------------------------------------------------------- #
def list_artifacts(client: NavigateClient, *, page: int = 1, page_size=None,
                   file_type=None, scan_status=None, classification_status=None,
                   search=None) -> Page:
    size, offset = _limits(page, page_size)
    env = client.list_artifacts(
        limit=size, offset=offset, file_type=file_type, scan_status=scan_status,
        classification_status=classification_status, search=search)
    items = [_artifact_row(a) for a in env.get("items", [])]
    return _page(env, items, page, size)


def _artifact_row(a: dict) -> dict:
    return {
        "id": a.get("id"),
        "title": (a.get("filename") or "").rsplit(".", 1)[0],
        "filename": a.get("filename"),
        "file_type": a.get("file_type"),
        "path": a.get("path"),
        "modified_at": a.get("modified_at"),
        "status": a.get("scan_status"),
        "source_system": a.get("source_system"),
        "size_bytes": a.get("size_bytes"),
        "extraction_status": a.get("extraction_status"),
        "classification_status": a.get("classification_status"),
    }


def get_artifact(client: NavigateClient, artifact_id: str) -> dict | None:
    art = client.get_artifact(artifact_id)
    if not art:
        return None
    links = client.artifact_links(artifact_id).get("items", [])
    evidence = client.artifact_evidence(artifact_id).get("items", [])
    return {
        **_artifact_row(art),
        "created_at": art.get("created_at"),
        "sha256": art.get("sha256"),
        "extraction_status": art.get("extraction_status"),
        "classification_status": art.get("classification_status"),
        "links": [{
            "id": l.get("id"), "url": l.get("normalized_url"),
            "anchor_text": l.get("anchor_text"),
            "target_system": l.get("target_system"),
            "target_type": l.get("target_type"), "link_kind": l.get("link_kind"),
            "status": l.get("status"),
        } for l in links],
        "evidence": [_evidence_row(e) for e in evidence],
    }


def artifact_filter_options(client: NavigateClient) -> dict:
    # Navigate has no filter-options endpoint; offer the documented enums.
    return {
        "file_types": ["docx", "pptx", "xlsx", "pdf", "md", "txt"],
        "statuses": ["RAW", "CHANGED", "UNCHANGED", "DELETED", "DUPLICATE"],
        "classification_statuses": ["CLASSIFIED", "UNCLASSIFIED"],
    }


# --------------------------------------------------------------------------- #
# Knowledge objects
# --------------------------------------------------------------------------- #
def list_knowledge(client: NavigateClient, *, page=1, page_size=None,
                   object_type=None, status=None, review_status=None,
                   owner=None, domain=None, min_confidence=None,
                   search=None) -> Page:
    size, offset = _limits(page, page_size)
    env = client.list_knowledge(
        limit=size, offset=offset, object_type=object_type, status=status,
        review_status=review_status, owner=owner, domain=domain,
        min_confidence=min_confidence, search=search)
    items = [_knowledge_row(o) for o in env.get("items", [])]
    return _page(env, items, page, size)


def _knowledge_row(o: dict) -> dict:
    return {
        "id": o.get("id"), "name": o.get("name"), "type": o.get("object_type"),
        "description": o.get("description"), "confidence": o.get("confidence"),
        "status": o.get("status"), "owner": o.get("owner"),
        "review_status": o.get("review_status"),
        "freshness_state": o.get("freshness_state"),
        "quality_score": o.get("quality_score"),
        # Per-row counts (Navigate now includes these in the list response).
        "relationship_count": o.get("relationship_count"),
        "evidence_count": o.get("evidence_count"),
        "mention_count": o.get("mention_count"),
    }


def get_knowledge(client: NavigateClient, object_id: str) -> dict | None:
    obj = client.get_knowledge(object_id)
    if not obj:
        return None
    evidence = client.knowledge_evidence(object_id).get("items", [])
    mentions = client.knowledge_mentions(object_id).get("items", [])

    # Use the complete relationships endpoint (incoming + outgoing, with
    # confidence + review status) rather than the graph "neighbors" projection,
    # which Navigate filters to a subset of predicates.
    index = _objects_index(client)
    rels_env = _safe(lambda: client.knowledge_relationships(object_id)) or {"items": []}
    relationships: dict[str, list] = {}
    for r in rels_env.get("items", []):
        src, tgt = r.get("source_object"), r.get("target_object")
        outgoing = src == object_id
        other = tgt if outgoing else src
        key = r.get("predicate") if outgoing else f"{r.get('predicate')} (incoming)"
        relationships.setdefault(key, []).append({
            "object_id": other,
            "name": index.get(other, {}).get("name", other),
            "type": index.get(other, {}).get("type"),
            "confidence": r.get("confidence"),
            "review_status": r.get("review_status"),
            "direction": "out" if outgoing else "in",
        })

    doc_ids = {e.get("artifact_id") for e in evidence} | \
        {m.get("artifact_id") for m in mentions}
    return {
        "id": obj.get("id"), "name": obj.get("name"),
        "type": obj.get("object_type"), "description": obj.get("description"),
        "confidence": obj.get("confidence"), "status": obj.get("status"),
        "merge_confidence": obj.get("merge_confidence"),
        "created_at": obj.get("created_at"), "updated_at": obj.get("updated_at"),
        "owner": obj.get("owner"),
        "lifecycle": {
            "review_state": obj.get("review_status"),
            "freshness_state": obj.get("freshness_state"),
        },
        "quality_score": obj.get("quality_score"),
        "evidence": [_evidence_row(e) for e in evidence],
        "evidence_count": len(evidence),
        "relationships": relationships,
        "documents": [{"id": d, "title": d, "file_type": "", "confidence": None}
                      for d in sorted(filter(None, doc_ids))],
        "mentions": len(mentions),
    }


def knowledge_filter_options(client: NavigateClient) -> dict:
    return {
        "types": ["Capability", "Initiative", "Technology", "Platform", "Team",
                  "Product", "Concept", "Decision", "Risk", "Process"],
        "statuses": ["PROPOSED", "REVIEWED", "APPROVED", "REJECTED"],
        "review_states": ["PENDING_REVIEW", "NEEDS_ATTENTION", "APPROVED",
                          "ARCHIVED", "REJECTED"],
    }


def review_object(client: NavigateClient, object_id: str, action: str) -> bool:
    mapping = {"approve": "approve", "reject": "reject", "archive": "archive"}
    act = mapping.get(action.lower())
    if not act:
        return False
    client.knowledge_action(object_id, act)
    return True


# --------------------------------------------------------------------------- #
# Relationships
# --------------------------------------------------------------------------- #
def list_relationships(client: NavigateClient, *, page=1, page_size=None,
                       predicate=None, review_status=None,
                       min_confidence=None, search=None) -> Page:
    size, offset = _limits(page, page_size)
    index = _objects_index(client)

    def _row(r: dict) -> dict:
        src, tgt = r.get("source_object"), r.get("target_object")
        return {
            "id": r.get("id"),
            "source_id": src,
            "source": index.get(src, {}).get("name") or src,
            "source_type": index.get(src, {}).get("type"),
            "predicate": r.get("predicate"),
            "predicate_label": PREDICATE_LABELS.get(r.get("predicate"), r.get("predicate")),
            "target_id": tgt,
            "target": index.get(tgt, {}).get("name") or tgt,
            "target_type": index.get(tgt, {}).get("type"),
            "confidence": r.get("confidence"),
            "evidence": r.get("evidence"),
            "review_status": r.get("review_status"),
        }

    # Navigate's /relationships endpoint filters by predicate/review_status but
    # has no free-text search. When a query is present we fetch the (server-
    # filtered) set and match it against the resolved source/target names
    # client-side, then paginate locally so the search spans every match.
    if search:
        env = client.list_relationships(
            limit=get_settings().max_page_size, offset=0, predicate=predicate,
            review_status=review_status, min_confidence=min_confidence)
        q = search.lower()
        rows = [row for row in (_row(r) for r in env.get("items", []))
                if q in (row["source"] or "").lower()
                or q in (row["target"] or "").lower()]
        return Page(rows[offset:offset + size], len(rows), page, size)

    env = client.list_relationships(
        limit=size, offset=offset, predicate=predicate,
        review_status=review_status, min_confidence=min_confidence)
    items = [_row(r) for r in env.get("items", [])]
    return _page(env, items, page, size)


def relationship_filter_options(client: NavigateClient) -> dict:
    return {
        "predicates": list(PREDICATE_LABELS.keys()),
        "review_statuses": ["PROPOSED", "APPROVED", "REJECTED"],
    }


def review_relationship(client: NavigateClient, rel_id: int, action: str) -> bool:
    act = {"approve": "approve", "reject": "reject",
           "archive": "archive"}.get(action.lower())
    if not act:
        return False
    client.relationship_action(rel_id, act)
    return True


# --------------------------------------------------------------------------- #
# Evidence
# --------------------------------------------------------------------------- #
def _evidence_row(e: dict) -> dict:
    return {
        "id": e.get("id"), "object_id": e.get("knowledge_object_id"),
        "artifact_id": e.get("artifact_id"),
        "artifact_title": e.get("artifact_id"),
        "quote": e.get("quote"), "page_number": e.get("page_number"),
        "slide_number": e.get("slide_number"), "confidence": e.get("confidence"),
    }


def list_evidence(client: NavigateClient, *, page=1, page_size=None,
                  object_id=None, artifact_id=None) -> Page:
    size, offset = _limits(page, page_size)
    env = client.list_evidence(limit=size, offset=offset,
                               knowledge_object_id=object_id,
                               artifact_id=artifact_id)
    items = [_evidence_row(e) for e in env.get("items", [])]
    return _page(env, items, page, size)


# --------------------------------------------------------------------------- #
# Compliance & standards
#
# Navigate's /compliance/* layer ingests standards (Eurocodes, ISO, GDPR…) as
# Standard/Requirement knowledge objects, extracts machine-readable Equations,
# and tracks coverage, gaps and assessment records. Standards, Requirements and
# Equations are knowledge objects, so their approve/reject/archive reuses the
# existing /knowledge-objects action (``review_object``); only Assessments use
# the dedicated /compliance/assessments action.
# --------------------------------------------------------------------------- #
def compliance_home(client: NavigateClient) -> dict:
    coverage = _safe(client.compliance_coverage) or {"overall": None,
                                                     "standards": []}
    gaps = [_gap_row(g) for g in (_safe(client.compliance_gaps) or [])]
    standards = _safe(client.list_compliance_standards) or []
    reqs = _safe(lambda: client.list_compliance_requirements(limit=1, offset=0))\
        or {}
    eqs = _safe(lambda: client.list_compliance_equations(limit=1, offset=0)) or {}
    return {
        "overall": coverage.get("overall"),
        "coverage": [{
            "standard_object_id": s.get("standard_object_id"),
            "standard_name": s.get("standard_name"),
            "total": s.get("total", 0), "satisfied": s.get("satisfied", 0),
            "partial": s.get("partial", 0), "coverage": s.get("coverage"),
        } for s in coverage.get("standards", [])],
        "gaps": gaps,
        "standard_count": len(standards),
        "requirement_count": reqs.get("total", 0),
        "equation_count": eqs.get("total", 0),
    }


def _standard_row(s: dict) -> dict:
    return {
        "id": s.get("object_id"), "name": s.get("name"),
        "authority": s.get("authority"), "version": s.get("version"),
        "jurisdiction": s.get("jurisdiction"), "status": s.get("status"),
    }


def list_standards(client: NavigateClient) -> list[dict]:
    return [_standard_row(s) for s in (client.list_compliance_standards() or [])]


def get_standard(client: NavigateClient, object_id: str) -> dict | None:
    std = client.get_compliance_standard(object_id)
    if not std:
        return None
    reqs = _safe(lambda: client.list_compliance_requirements(
        limit=get_settings().max_page_size, offset=0, standard=object_id)) or {}
    eqs = _safe(lambda: client.list_compliance_equations(
        limit=get_settings().max_page_size, offset=0, standard=object_id)) or {}
    return {
        **_standard_row(std),
        "requirements": [_requirement_row(r) for r in reqs.get("items", [])],
        "equations": [_equation_row(e) for e in eqs.get("items", [])],
    }


def _requirement_row(r: dict) -> dict:
    return {
        "id": r.get("object_id"), "name": r.get("name"),
        "standard_object_id": r.get("standard_object_id"),
        "clause_ref": r.get("clause_ref"), "title": r.get("title"),
        "requirement_text": r.get("requirement_text"),
        "obligation_level": r.get("obligation_level"), "status": r.get("status"),
    }


def list_requirements(client: NavigateClient, *, page=1, page_size=None,
                      standard=None) -> Page:
    size, offset = _limits(page, page_size)
    env = client.list_compliance_requirements(limit=size, offset=offset,
                                              standard=standard)
    items = [_requirement_row(r) for r in env.get("items", [])]
    return _page(env, items, page, size)


def get_requirement(client: NavigateClient, object_id: str) -> dict | None:
    req = client.get_compliance_requirement(object_id)
    if not req:
        return None
    std_id = req.get("standard_object_id")
    # Equations are filtered by standard only; narrow to this requirement.
    eqs_env = _safe(lambda: client.list_compliance_equations(
        limit=get_settings().max_page_size, offset=0, standard=std_id)) or {}
    equations = [_equation_row(e) for e in eqs_env.get("items", [])
                 if e.get("requirement_object_id") == object_id]
    proof = _safe(lambda: client.compliance_prove(object_id)) or {}
    evidence = (_safe(lambda: client.knowledge_evidence(object_id)) or {})\
        .get("items", [])
    return {
        **_requirement_row(req),
        "standard_name": _standard_name(client, std_id),
        "equations": equations,
        "proof": {
            "found": proof.get("found", False),
            "proven": proof.get("proven", False),
            "message": proof.get("message"),
            "assessments": proof.get("assessments", []),
        },
        "evidence": [_evidence_row(e) for e in evidence],
        "evidence_count": len(evidence),
    }


def _equation_row(e: dict) -> dict:
    return {
        "id": e.get("object_id"), "name": e.get("name"),
        "symbol": e.get("symbol"), "title": e.get("title"),
        "standard_object_id": e.get("standard_object_id"),
        "requirement_object_id": e.get("requirement_object_id"),
        "clause_ref": e.get("clause_ref"), "expression": e.get("expression"),
        "valid": e.get("valid"), "status": e.get("status"),
    }


def list_equations(client: NavigateClient, *, page=1, page_size=None,
                   standard=None) -> Page:
    size, offset = _limits(page, page_size)
    env = client.list_compliance_equations(limit=size, offset=offset,
                                           standard=standard)
    items = [_equation_row(e) for e in env.get("items", [])]
    return _page(env, items, page, size)


def get_equation(client: NavigateClient, object_id: str) -> dict | None:
    eq = client.get_compliance_equation(object_id)
    if not eq:
        return None
    std_id = eq.get("standard_object_id")
    req_id = eq.get("requirement_object_id")
    req = _safe(lambda: client.get_compliance_requirement(req_id)) if req_id else None
    evidence = (_safe(lambda: client.knowledge_evidence(object_id)) or {})\
        .get("items", [])
    return {
        **_equation_row(eq),
        "standard_name": _standard_name(client, std_id),
        "requirement_name": (req or {}).get("name") or req_id,
        "python_code": eq.get("python_code"),
        "ast_pretty": _pretty_json(eq.get("ast_json")),
        "latex": eq.get("latex"),
        "validation_note": eq.get("validation_note"),
        "variables": [{
            "symbol": v.get("symbol"), "description": v.get("description"),
            "unit": v.get("unit"),
        } for v in (eq.get("variables") or [])],
        "evidence": [_evidence_row(e) for e in evidence],
        "evidence_count": len(evidence),
    }


def _gap_row(g: dict) -> dict:
    return {
        "id": g.get("object_id"), "requirement_name": g.get("requirement_name"),
        "clause_ref": g.get("clause_ref"), "title": g.get("title"),
        "obligation_level": g.get("obligation_level"),
        "standard_object_id": g.get("standard_object_id"),
        "standard_name": g.get("standard_name"),
    }


def list_gaps(client: NavigateClient) -> list[dict]:
    return [_gap_row(g) for g in (client.compliance_gaps() or [])]


def _assessment_row(a: dict) -> dict:
    return {
        "id": a.get("id"),
        "requirement_object_id": a.get("requirement_object_id"),
        "requirement_name": a.get("requirement_name"),
        "control_object_id": a.get("control_object_id"),
        "control_name": a.get("control_name"), "status": a.get("status"),
        "review_status": a.get("review_status"),
        "assessed_against_version": a.get("assessed_against_version"),
        "rationale": a.get("rationale"),
    }


def list_assessments(client: NavigateClient, *, status=None) -> list[dict]:
    return [_assessment_row(a)
            for a in (client.compliance_assessments(status=status) or [])]


def compliance_filter_options(client: NavigateClient) -> dict:
    return {
        "standards": [{"id": s["id"], "name": s["name"]}
                      for s in (_safe(lambda: list_standards(client)) or [])],
        "obligation_levels": ["MUST", "SHOULD", "MAY"],
        "statuses": ["PROPOSED", "REVIEWED", "APPROVED", "REJECTED"],
        "assessment_statuses": ["SATISFIED", "PARTIAL", "GAP",
                                "NOT_APPLICABLE"],
    }


def review_assessment(client: NavigateClient, assessment_id: int,
                      action: str) -> bool:
    act = {"approve": "approve", "reject": "reject"}.get(action.lower())
    if not act:
        return False
    client.assessment_action(assessment_id, act)
    return True


def run_assessment(client: NavigateClient) -> dict:
    return client.compliance_assess()


def _standard_name(client: NavigateClient, std_id: str | None) -> str | None:
    """Resolve a standard's display name, falling back to its id."""
    if not std_id:
        return None
    std = _safe(lambda: client.get_compliance_standard(std_id))
    return (std or {}).get("name") or std_id


def _pretty_json(value) -> str | None:
    """Pretty-print a JSON string (equation AST) for display, else pass through."""
    if not value:
        return None
    import json
    try:
        return json.dumps(json.loads(value), indent=2)
    except (ValueError, TypeError):
        return str(value)


# --------------------------------------------------------------------------- #
# Domains (Navigate's /governance/domains resource)
# --------------------------------------------------------------------------- #
def _domain_row(d: dict) -> dict:
    return {
        "domain": d.get("domain") or d.get("name"),
        "objects": d.get("object_count", 0),
        "owner": d.get("owner"),
        "review_backlog": d.get("review_backlog", 0),
        "quality": d.get("avg_quality"),
        "freshness": d.get("avg_freshness"),
    }


def domain_overview(client: NavigateClient) -> list[dict]:
    domains = _safe(client.gov_domains)
    if domains is None:
        # Older Navigate without the domains resource: derive from the
        # governance dashboard so the UI degrades gracefully.
        return _domains_from_dashboard(client)
    return [_domain_row(d) for d in domains if isinstance(d, dict)]


def _domains_from_dashboard(client: NavigateClient) -> list[dict]:
    dash = _safe(client.gov_dashboard) or {}
    domains = dash.get("domains") or dash.get("by_domain") or []
    out = []
    for d in domains:
        if isinstance(d, dict):
            out.append({
                "domain": d.get("domain") or d.get("name"),
                "objects": d.get("objects") or d.get("count") or d.get("object_count", 0),
                "owner": d.get("owner"), "review_backlog": d.get("review_backlog", 0),
                "quality": d.get("quality"), "freshness": d.get("freshness"),
            })
        else:
            out.append({"domain": str(d), "objects": 0, "owner": None,
                        "review_backlog": 0, "quality": None, "freshness": None})
    return out


def get_domain(client: NavigateClient, domain: str) -> dict:
    health = _safe(lambda: client.gov_domain(domain)) or {}
    page = list_knowledge(client, domain=domain, page_size=200)
    owners = {i["owner"] for i in page.items if i.get("owner")}
    if health.get("owner"):
        owners.add(health["owner"])
    return {
        "domain": domain,
        "object_count": health.get("object_count", page.total),
        "review_backlog": health.get("review_backlog"),
        "quality": health.get("avg_quality"),
        "freshness": health.get("avg_freshness"),
        "owners": sorted(owners),
        "objects": [{
            "id": o["id"], "name": o["name"], "type": o["type"],
            "status": o["status"], "quality_score": o["quality_score"],
            "review_status": o["review_status"],
        } for o in page.items],
    }


# --------------------------------------------------------------------------- #
# Governance + health
# --------------------------------------------------------------------------- #
def governance_center(client: NavigateClient) -> dict:
    review_queue = [{
        "id": i.get("object_id"), "name": i.get("name"),
        "type": i.get("object_type"), "confidence": i.get("last_confidence"),
        "review_status": i.get("review_state"),
        "freshness_state": i.get("freshness_state"),
    } for i in (_safe(client.gov_review_queue) or [])]

    stale = [{
        "id": i.get("object_id"), "name": i.get("name"),
        "type": i.get("object_type"),
        "review_status": i.get("freshness_state"),
        "freshness_state": i.get("freshness_state"),
        "quality_score": i.get("freshness_score"),
    } for i in (_safe(client.gov_stale) or [])]

    alerts = [{
        "id": a.get("id"), "alert_type": a.get("alert_type"),
        "severity": a.get("severity", "INFO"), "object_id": a.get("object_id"),
        "object_name": a.get("object_id"), "message": a.get("message"),
    } for a in (_safe(client.gov_alerts) or [])]
    by_type: dict[str, list] = {}
    for a in alerts:
        by_type.setdefault(a["alert_type"], []).append(a)

    pending_rels = list_relationships(client, review_status="PROPOSED",
                                      page_size=100).items

    # Drift feed (recent change-log entries) and the owner roster are newer
    # Navigate resources; degrade to empty lists on an older server.
    index = _objects_index(client)
    drift = _change_rows(_safe(lambda: client.gov_drift(limit=20)) or [], index)
    owners = [_owner_row(o, index) for o in (_safe(client.gov_owners) or [])
              if isinstance(o, dict)]
    return {
        "review_queue": review_queue,
        "pending_relationships": pending_rels,
        "alerts": alerts,
        "stale_objects": stale,
        "quality_alerts": by_type.get("QUALITY_DROP", []) + by_type.get("DRIFT", []),
        "drift_alerts": by_type.get("DRIFT", []),
        "orphaned": by_type.get("ORPHANED", []),
        "duplicate_candidates": by_type.get("DUPLICATE_CANDIDATE", []),
        "drift": drift,
        "owners": owners,
    }


def _change_rows(entries: list, index: dict) -> list[dict]:
    """Shape Navigate ChangeLogEntry items, resolving object ids to names."""
    rows = []
    for c in entries:
        oid = c.get("object_id")
        rows.append({
            "id": c.get("id"), "change_type": c.get("change_type"),
            "target_kind": c.get("target_kind"), "object_id": oid,
            "object_name": index.get(oid, {}).get("name") or oid,
            "field": c.get("field"), "old_value": c.get("old_value"),
            "new_value": c.get("new_value"), "detail": c.get("detail"),
            "detected_at": c.get("detected_at"),
        })
    return rows


def _owner_row(o: dict, index: dict) -> dict:
    oid = o.get("object_id")
    return {
        "object_id": oid,
        "object_name": index.get(oid, {}).get("name") or oid,
        "owner_type": o.get("owner_type"), "owner_id": o.get("owner_id"),
        "assigned_at": o.get("assigned_at"), "assigned_by": o.get("assigned_by"),
    }


def object_history(client: NavigateClient, object_id: str) -> dict:
    """Lifecycle / change history for one knowledge object.

    Backed by Navigate's ``/governance/objects/{id}/history``; returns an empty
    history (rather than erroring) when the server predates the resource.
    """
    data = _safe(lambda: client.gov_object_history(object_id))
    if not data:
        return {"object_id": object_id, "changes": [], "owner": None,
                "lifecycle": None}
    index = _objects_index(client)
    owner = data.get("owner")
    return {
        "object_id": object_id,
        "changes": _change_rows(data.get("changes", []), index),
        "owner": _owner_row(owner, index) if owner else None,
        "lifecycle": data.get("lifecycle"),
    }


def assign_owner(client: NavigateClient, object_id: str, *, owner_type: str,
                 owner_id: str) -> dict:
    return client.gov_assign_owner(object_id, owner_type=owner_type,
                                   owner_id=owner_id)


def flag_object(client: NavigateClient, object_id: str) -> dict:
    return client.gov_flag(object_id)


def recent_changes(client: NavigateClient, *, limit: int = 20,
                   index: dict | None = None) -> list[dict]:
    """Recent change-log entries from Navigate's /governance/changes feed.

    ``index`` (id → {name, type}) can be passed in by a caller that already
    built one this request, to avoid a second full knowledge-object fetch.
    """
    env = _safe(lambda: client.gov_changes(limit=limit, offset=0))
    if env is None:
        return []
    if index is None:
        index = _objects_index(client)
    rows = []
    for c in env.get("items", []):
        oid = c.get("object_id")
        rows.append({
            "id": c.get("id"),
            "change_type": c.get("change_type"),
            "target_kind": c.get("target_kind"),
            "object_id": oid,
            "object_name": index.get(oid, {}).get("name") or oid,
            "field": c.get("field"),
            "old_value": c.get("old_value"),
            "new_value": c.get("new_value"),
            "detail": c.get("detail"),
            "detected_at": c.get("detected_at"),
        })
    return rows


def growth_trend(client: NavigateClient, *, interval: str = "month",
                 limit: int = 12) -> dict:
    """Knowledge-base growth over time from /governance/growth."""
    data = _safe(lambda: client.gov_growth(interval=interval, limit=limit))
    if not data:
        return {"interval": interval, "points": []}
    return {"interval": data.get("interval", interval),
            "points": data.get("points", [])}


def bulk_approve_confidence(client: NavigateClient, *, kind: str,
                            min_confidence: float, max_confidence: float = 1.0,
                            include_reviewed: bool = False,
                            note: str | None = None) -> dict | None:
    """Confidence-banded bulk approval of knowledge objects or relationships."""
    if kind == "knowledge":
        return client.knowledge_approve_confidence(
            min_confidence=min_confidence, max_confidence=max_confidence,
            include_reviewed=include_reviewed, note=note)
    if kind == "relationships":
        return client.relationships_approve_confidence(
            min_confidence=min_confidence, max_confidence=max_confidence,
            include_reviewed=include_reviewed, note=note)
    return None


def knowledge_health(client: NavigateClient) -> dict:
    stats = client.stats()
    total = stats.get("knowledge_object_count", 0) or 1
    try:
        quality = client.gov_quality().get("average_quality")
    except Exception:
        quality = None
    try:
        approved = client.list_knowledge(limit=1, offset=0, status="APPROVED")\
            .get("total", 0)
    except Exception:
        approved = 0
    stale = stats.get("stale_object_count", 0)
    return {
        "quality_score": round(quality, 1) if quality is not None else None,
        "freshness": round(100 * (total - stale) / total, 1),
        "review_coverage": round(100 * approved / total, 1),
        # Not exposed by Navigate's API:
        "evidence_coverage": None,
        "relationship_coverage": None,
        "domain_health": domain_overview(client),
    }


# --------------------------------------------------------------------------- #
# Cost / LLM usage  (Navigate's /cost ledger)
# --------------------------------------------------------------------------- #
def cost_overview(client: NavigateClient) -> dict:
    """Token-usage / spend ledger from Navigate's ``/cost`` endpoints.

    Older Navigate servers expose this only via the CLI, so every call is
    guarded: an absent ledger renders an "unavailable" panel rather than
    erroring.
    """
    summary = _safe(client.cost_summary) or {}
    by_operation = _safe(client.cost_by_operation) or []
    by_model = _safe(client.cost_by_model) or []
    per_document = _safe(lambda: client.cost_per_document(top=20)) or []
    vs_quality = _safe(lambda: client.cost_vs_quality(top=20)) or []
    return {
        "available": bool(summary or by_operation or by_model),
        "summary": {
            "calls": summary.get("calls", 0),
            "input_tokens": summary.get("input_tokens", 0),
            "output_tokens": summary.get("output_tokens", 0),
            "total_tokens": summary.get("total_tokens", 0),
            "cache_read_tokens": summary.get("cache_read_tokens", 0),
            "cache_write_tokens": summary.get("cache_write_tokens", 0),
            "cost_usd": summary.get("cost_usd"),
            "unpriced_calls": summary.get("unpriced_calls", 0),
        },
        "by_operation": [{
            "operation": r.get("operation") or "—", "calls": r.get("calls", 0),
            "total_tokens": r.get("total_tokens", 0),
            "cost_usd": r.get("cost_usd"),
        } for r in by_operation if isinstance(r, dict)],
        "by_model": [{
            "model": r.get("model") or "—", "calls": r.get("calls", 0),
            "total_tokens": r.get("total_tokens", 0),
            "cost_usd": r.get("cost_usd"),
            "unpriced_calls": r.get("unpriced_calls", 0),
        } for r in by_model if isinstance(r, dict)],
        "per_document": [{
            "artifact_id": r.get("artifact_id"), "calls": r.get("calls", 0),
            "total_tokens": r.get("total_tokens", 0),
            "cost_usd": r.get("cost_usd"),
        } for r in per_document if isinstance(r, dict)],
        "vs_quality": [{
            "artifact_id": r.get("artifact_id"),
            "document_type": r.get("document_type"),
            "type_confidence": r.get("type_confidence"),
            "calls": r.get("calls", 0), "total_tokens": r.get("total_tokens", 0),
            "cost_usd": r.get("cost_usd"),
        } for r in vs_quality if isinstance(r, dict)],
    }


# --------------------------------------------------------------------------- #
# Graph analytics & RDF projection (folded into Observability)
# --------------------------------------------------------------------------- #
def graph_analytics(client: NavigateClient) -> dict:
    health = _safe(client.graph_health) or {}
    metrics = _safe(lambda: client.graph_metrics(top=10)) or {}
    domains = _safe(client.graph_domains) or []
    return {
        "available": bool(health or metrics or domains),
        "health": health,
        "metrics": metrics,
        "domains": [{
            "domain": d.get("domain"),
            "object_count": d.get("object_count", 0),
            "relationship_count": d.get("relationship_count", 0),
            "most_central": [{
                "id": c.get("id"), "label": c.get("label"),
                "degree": c.get("degree"),
            } for c in (d.get("most_central") or [])],
        } for d in domains if isinstance(d, dict)],
    }


def rdf_overview(client: NavigateClient) -> dict:
    stats = _safe(client.rdf_stats) or {}
    validation = _safe(client.rdf_validate) or {}
    files = validation.get("files") or {}
    return {
        "available": bool(stats),
        "stats": {
            "objects": stats.get("objects", 0),
            "relationships": stats.get("relationships", 0),
            "evidence": stats.get("evidence", 0),
            "knowledge_triples": stats.get("knowledge_triples", 0),
            "relationship_triples": stats.get("relationship_triples", 0),
            "provenance_triples": stats.get("provenance_triples", 0),
        },
        "validation": {
            "files": [{
                "name": name, "ok": f.get("ok"),
                "triples": f.get("triples", 0), "error": f.get("error"),
            } for name, f in files.items()],
            "all_ok": (all(f.get("ok") for f in files.values())
                       if files else None),
        },
    }


# --------------------------------------------------------------------------- #
# Observability
# --------------------------------------------------------------------------- #
def observability(client: NavigateClient) -> dict:
    jobs_env = _safe(lambda: client.list_jobs(limit=25)) or {"items": []}
    jobs = jobs_env.get("items", [])
    health = _safe(client.health) or {"status": "unreachable"}
    link_stats = _safe(client.link_stats) or {}
    return {
        "jobs": [{
            "id": j.get("id"), "job_type": j.get("job_type"),
            "status": j.get("status"), "started_at": j.get("started_at"),
            "completed_at": j.get("completed_at"),
            "error_message": j.get("error_message"),
            "result_summary": j.get("result_summary"),
        } for j in jobs],
        "health": health,
        "link_stats": link_stats,
        "errors": sum(1 for j in jobs if j.get("status") in ("FAILED", "ERROR")),
        "graph_analytics": graph_analytics(client),
        "rdf": rdf_overview(client),
    }


# --------------------------------------------------------------------------- #
# Search (fan-out across resources Navigate can search)
# --------------------------------------------------------------------------- #
def search(client: NavigateClient, query: str, limit: int = 20) -> dict:
    if not query or not query.strip():
        return {"knowledge_objects": [], "artifacts": [], "relationships": [],
                "domains": [], "total": 0}
    q = query.strip()
    ko = _safe(lambda: client.list_knowledge(limit=limit, offset=0, search=q)) or {}
    arts = _safe(lambda: client.list_artifacts(limit=limit, offset=0, search=q)) or {}
    ko_items = [{
        "id": o.get("id"), "name": o.get("name"), "type": o.get("object_type"),
        "status": o.get("status"),
    } for o in ko.get("items", [])]
    art_items = [{
        "id": a.get("id"), "title": (a.get("filename") or "").rsplit(".", 1)[0],
        "file_type": a.get("file_type"), "path": a.get("path"),
    } for a in arts.get("items", [])]
    return {
        "knowledge_objects": ko_items, "artifacts": art_items,
        "relationships": [], "domains": [],
        "total": len(ko_items) + len(art_items),
    }


# --------------------------------------------------------------------------- #
# Graph
# --------------------------------------------------------------------------- #
def graph_payload(client: NavigateClient, *, mode: str = "all", focus=None,
                  depth: int = 1, min_confidence: float = 0.0,
                  limit: int | None = None) -> dict:
    settings = get_settings()
    limit = limit or settings.graph_node_limit
    if focus:
        return _neighbors_payload(client, focus, depth)

    export = client.graph_export()
    nodes = export.get("nodes", [])
    edges = export.get("edges", [])
    type_filter = {
        "capability": {"Capability"}, "technology": {"Technology", "Platform"},
        "decision": {"Decision"}, "team": {"Team"}, "process": {"Process"},
    }.get(mode)

    node_by_id = {n.get("id"): n for n in nodes}
    keep_edges = []
    used_ids: set[str] = set()
    for e in edges:
        if (e.get("confidence") or 0) < min_confidence:
            continue
        s, t = e.get("source"), e.get("target")
        s_node, t_node = node_by_id.get(s), node_by_id.get(t)
        if type_filter and s_node and t_node and (
                s_node.get("type") not in type_filter
                and t_node.get("type") not in type_filter):
            continue
        used_ids.add(s)
        used_ids.add(t)
        keep_edges.append(e)

    if not used_ids:
        used_ids = {n.get("id") for n in nodes[:limit]}
    if len(used_ids) > limit:
        used_ids = set(list(used_ids)[:limit])
        keep_edges = [e for e in keep_edges
                      if e.get("source") in used_ids and e.get("target") in used_ids]

    index = _objects_index(client)
    out_nodes = [{"data": {
        "id": n.get("id"),
        "label": index.get(n.get("id"), {}).get("name") or n.get("label"),
        "type": n.get("type"), "status": n.get("status"),
        "confidence": n.get("confidence"),
        "evidence_count": n.get("mentions") or n.get("documents") or 0,
        "focus": False,
    }} for n in nodes if n.get("id") in used_ids]
    out_edges = [{"data": {
        "id": f"e{e.get('id')}", "source": e.get("source"),
        "target": e.get("target"), "label": e.get("predicate"),
        "confidence": e.get("confidence"), "review_status": e.get("status"),
    }} for e in keep_edges]
    return {"nodes": out_nodes, "edges": out_edges, "mode": mode,
            "node_count": len(out_nodes), "edge_count": len(out_edges),
            "truncated": len(used_ids) >= limit}


def _neighbors_payload(client: NavigateClient, focus: str, depth: int) -> dict:
    """Build a focused payload from /graph/object/{id}/neighbors."""
    seen_nodes: dict[str, dict] = {}
    edges: list[dict] = []
    names = _name_map(client)
    types = _type_map(client)

    def add_node(oid, label=None, ntype=None, focus_flag=False):
        if oid not in seen_nodes:
            seen_nodes[oid] = {"data": {
                "id": oid, "label": label or names.get(oid, oid),
                "type": ntype or types.get(oid), "focus": focus_flag,
                "evidence_count": 0}}

    frontier = {focus}
    visited: set[str] = set()
    add_node(focus, focus_flag=True)
    for _ in range(max(1, depth)):
        nxt: set[str] = set()
        for oid in frontier:
            if oid in visited:
                continue
            visited.add(oid)
            data = _safe(lambda oid=oid: client.graph_neighbors(oid)) or {}
            for predicate, nodes in (data.get("neighbors") or {}).items():
                for n in nodes:
                    nid = n.get("id")
                    add_node(nid, n.get("label"), n.get("type"))
                    direction = n.get("direction", "out")
                    src, tgt = (oid, nid) if direction != "in" else (nid, oid)
                    eid = f"e{src}-{tgt}-{predicate}"
                    if not any(e["data"]["id"] == eid for e in edges):
                        edges.append({"data": {
                            "id": eid, "source": src, "target": tgt,
                            "label": predicate, "confidence": None,
                            "review_status": None}})
                    nxt.add(nid)
        frontier = nxt - visited
    return {"nodes": list(seen_nodes.values()), "edges": edges,
            "mode": "neighbors", "node_count": len(seen_nodes),
            "edge_count": len(edges), "truncated": False}


def shortest_path(client: NavigateClient, source: str, target: str) -> dict:
    settings = get_settings()
    data = client.graph_path(source, target, max_depth=10)
    names = _name_map(client)
    hops = data.get("hops", [])
    steps = [{
        "source": h.get("from"), "source_name": names.get(h.get("from"), h.get("from")),
        "target": h.get("to"), "target_name": names.get(h.get("to"), h.get("to")),
        "predicate": h.get("predicate"), "confidence": None,
    } for h in hops]
    node_ids = [source] + [h.get("to") for h in hops]
    return {
        "found": data.get("found", False), "length": len(hops),
        "nodes": [{"id": nid, "name": names.get(nid, nid), "type": None}
                  for nid in node_ids],
        "steps": steps,
    }


def list_object_names(client: NavigateClient) -> list[dict]:
    return [{"id": oid, "name": v["name"], "type": v["type"]}
            for oid, v in sorted(_objects_index(client).items(),
                                 key=lambda kv: (kv[1]["name"] or "").lower())]


# --------------------------------------------------------------------------- #
# GraphRAG
# --------------------------------------------------------------------------- #
#: GraphRAG reasoning modes Compas offers, with the Navigate call each maps to.
#: ``compare``/``path-reason`` take two terms; the rest reason over one input.
ASK_MODES = ("ask", "explain", "impact", "compare", "path-reason")
ASK_MODE_LABELS = {
    "ask": "Answer", "explain": "Explain", "impact": "Impact",
    "compare": "Compare", "path-reason": "Path reasoning",
}
TWO_TERM_MODES = frozenset({"compare", "path-reason"})


def ask(client: NavigateClient, question: str, *, mode: str = "ask",
        term_b: str | None = None) -> dict:
    settings = get_settings()
    depth = settings.ask_depth
    try:
        if mode == "explain":
            resp = client.ask_explain(question, depth=depth)
        elif mode == "impact":
            resp = client.ask_impact(question, depth=depth)
        elif mode == "compare":
            resp = client.ask_compare(question, term_b or "", depth=depth)
        elif mode == "path-reason":
            resp = client.ask_path_reason(question, term_b or "", depth=depth)
        else:
            resp = client.ask(question, depth=depth)
    except Exception as exc:  # noqa: BLE001
        return {"question": question,
                "answer": f"The Navigate assistant is unavailable: {exc}",
                "confidence": "low", "objects_used": [], "evidence": [],
                "context": None, "focus_id": None, "error": True}
    objects = resp.get("objects_used", [])
    return {
        "question": question,
        "answer": resp.get("answer", ""),
        "confidence": resp.get("confidence", ""),
        "objects_used": [{
            "id": o.get("id"), "name": o.get("label") or o.get("name"),
            "type": o.get("type"),
        } for o in objects],
        "relationships_used": resp.get("relationships_used", []),
        "evidence": [{
            "artifact_id": e.get("document") or e.get("handle"),
            "artifact_title": e.get("document") or e.get("handle"),
            "quote": e.get("quote"), "page_number": e.get("page_number"),
            "confidence": None,
        } for e in resp.get("evidence_used", [])],
        "context": resp.get("context"),
        "focus_id": objects[0].get("id") if objects else None,
    }


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _safe(fn):
    try:
        return fn()
    except Exception:  # noqa: BLE001
        return None


def _objects_index(client: NavigateClient) -> dict[str, dict]:
    """Map object id → {name, type} using the proper-case knowledge list.

    (Navigate lowercases ``label`` in graph payloads, so the knowledge-object
    list is the better source for display names.)
    """
    env = _safe(lambda: client.list_knowledge(
        limit=get_settings().max_page_size, offset=0)) or {"items": []}
    return {o["id"]: {"name": o.get("name"), "type": o.get("object_type")}
            for o in env.get("items", [])}


def _name_map(client: NavigateClient) -> dict[str, str]:
    return {oid: v["name"] for oid, v in _objects_index(client).items()}


def _type_map(client: NavigateClient) -> dict[str, str]:
    return {oid: v["type"] for oid, v in _objects_index(client).items()}
