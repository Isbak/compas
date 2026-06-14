"""View-model layer.

Turns Navigate API responses (:mod:`compas.navigate_client`) into the shapes
the templates render. No database, no business logic re-implemented — just
fetching, light shaping, and graceful degradation where Navigate's API doesn't
expose a datum (domains list, growth trend, change log, per-row counts).
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
                       min_confidence=None) -> Page:
    size, offset = _limits(page, page_size)
    env = client.list_relationships(
        limit=size, offset=offset, predicate=predicate,
        review_status=review_status, min_confidence=min_confidence)
    names = _name_map(client)
    types = _type_map(client)
    items = [{
        "id": r.get("id"),
        "source_id": r.get("source_object"),
        "source": names.get(r.get("source_object"), r.get("source_object")),
        "source_type": types.get(r.get("source_object")),
        "predicate": r.get("predicate"),
        "predicate_label": PREDICATE_LABELS.get(r.get("predicate"), r.get("predicate")),
        "target_id": r.get("target_object"),
        "target": names.get(r.get("target_object"), r.get("target_object")),
        "target_type": types.get(r.get("target_object")),
        "confidence": r.get("confidence"),
        "evidence": r.get("evidence"),
        "review_status": r.get("review_status"),
    } for r in env.get("items", [])]
    return _page(env, items, page, size)


def relationship_filter_options(client: NavigateClient) -> dict:
    return {
        "predicates": list(PREDICATE_LABELS.keys()),
        "review_statuses": ["PROPOSED", "APPROVED", "REJECTED"],
    }


def review_relationship(client: NavigateClient, rel_id: int, action: str) -> bool:
    act = {"approve": "approve", "reject": "reject"}.get(action.lower())
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
# Domains (derived; Navigate has no domains resource)
# --------------------------------------------------------------------------- #
def domain_overview(client: NavigateClient) -> list[dict]:
    try:
        dash = client.gov_dashboard() or {}
    except Exception:
        dash = {}
    domains = dash.get("domains") or dash.get("by_domain") or []
    out = []
    for d in domains:
        if isinstance(d, dict):
            out.append({
                "domain": d.get("domain") or d.get("name"),
                "objects": d.get("objects") or d.get("count") or d.get("object_count", 0),
                "documents": d.get("documents", 0),
                "quality": d.get("quality"), "freshness": d.get("freshness"),
            })
        else:
            out.append({"domain": str(d), "objects": 0, "documents": 0,
                        "quality": None, "freshness": None})
    return out


def get_domain(client: NavigateClient, domain: str) -> dict:
    page = list_knowledge(client, domain=domain, page_size=200)
    return {
        "domain": domain, "object_count": page.total,
        "relationship_count": None, "quality": None, "freshness": None,
        "owners": sorted({i["owner"] for i in page.items if i.get("owner")}),
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
    return {
        "review_queue": review_queue,
        "pending_relationships": pending_rels,
        "alerts": alerts,
        "stale_objects": stale,
        "quality_alerts": by_type.get("QUALITY_DROP", []) + by_type.get("DRIFT", []),
        "drift_alerts": by_type.get("DRIFT", []),
        "orphaned": by_type.get("ORPHANED", []),
        "duplicate_candidates": by_type.get("DUPLICATE_CANDIDATE", []),
    }


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
def ask(client: NavigateClient, question: str) -> dict:
    settings = get_settings()
    try:
        resp = client.ask(question, depth=settings.ask_depth)
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
