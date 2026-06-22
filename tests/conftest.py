"""Test fixtures.

Compas is a pure client of the Navigate API, so tests inject a
``FakeNavigateClient`` implementing the same surface with deterministic data.
No real Navigate server (and no database) is required.
"""

from __future__ import annotations

import pytest

# --------------------------------------------------------------------------- #
# In-memory Navigate fixture data
# --------------------------------------------------------------------------- #
OBJECTS = [
    {"id": "ko-relgov", "name": "Release Governance", "object_type": "Process",
     "description": "Governance framework controlling releases.",
     "confidence": 0.94, "status": "APPROVED", "merge_confidence": 0.9,
     "review_status": "APPROVED", "freshness_state": "FRESH",
     "quality_score": 90.0, "owner": "Test & Release Team",
     "created_at": "2026-01-01T00:00:00", "updated_at": "2026-05-01T00:00:00"},
    {"id": "ko-launch", "name": "Launchpad Model", "object_type": "Capability",
     "description": "Operating model for launches.", "confidence": 0.88,
     "status": "APPROVED", "review_status": "APPROVED",
     "freshness_state": "FRESH", "quality_score": 82.0, "owner": None},
    {"id": "ko-relmgmt", "name": "Release Management", "object_type": "Capability",
     "description": "End-to-end release capability.", "confidence": 0.91,
     "status": "APPROVED", "review_status": "APPROVED",
     "freshness_state": "AGING", "quality_score": 78.0, "owner": None},
    {"id": "ko-team", "name": "Test & Release Team", "object_type": "Team",
     "description": "Owns the release pipeline.", "confidence": 0.9,
     "status": "APPROVED", "review_status": "APPROVED",
     "freshness_state": "FRESH", "quality_score": 85.0, "owner": None},
    {"id": "ko-sfdc", "name": "Salesforce", "object_type": "Technology",
     "description": "CRM platform.", "confidence": 0.86, "status": "PROPOSED",
     "review_status": "PENDING_REVIEW", "freshness_state": "STALE",
     "quality_score": 55.0, "owner": None},
    {"id": "ko-risk", "name": "Vendor Lock-in", "object_type": "Risk",
     "description": "Risk of vendor dependence.", "confidence": 0.62,
     "status": "PROPOSED", "review_status": "PENDING_REVIEW",
     "freshness_state": "STALE", "quality_score": 40.0, "owner": None},
]

RELATIONSHIPS = [
    {"id": 1, "source_object": "ko-relgov", "predicate": "supports",
     "target_object": "ko-launch", "confidence": 0.9, "review_status": "APPROVED"},
    {"id": 2, "source_object": "ko-relgov", "predicate": "related_to",
     "target_object": "ko-relmgmt", "confidence": 0.88, "review_status": "APPROVED"},
    {"id": 3, "source_object": "ko-relgov", "predicate": "implemented_by",
     "target_object": "ko-team", "confidence": 0.86, "review_status": "APPROVED"},
    {"id": 4, "source_object": "ko-sfdc", "predicate": "affects",
     "target_object": "ko-relmgmt", "confidence": 0.6, "review_status": "PROPOSED"},
]

ARTIFACTS = [
    {"id": f"artifact-{i:03d}", "path": f"/sources/doc_{i}.docx",
     "filename": f"Document {i}.docx", "file_type": "docx",
     "size_bytes": 12345, "created_at": "2026-01-01T00:00:00",
     "modified_at": "2026-05-01T00:00:00", "sha256": "abc" * 10,
     "source_system": "sharepoint", "scan_status": "UNCHANGED",
     "first_seen_at": None, "last_scanned_at": None,
     "extraction_status": "EXTRACTED", "classification_status": "APPROVED"}
    for i in range(12)
]

ALERTS = [
    {"id": 1, "alert_type": "STALE_OBJECT", "severity": "WARNING",
     "object_id": "ko-sfdc", "message": "Salesforce is stale.", "status": "OPEN",
     "created_at": "2026-05-10T00:00:00"},
    {"id": 2, "alert_type": "QUALITY_DROP", "severity": "WARNING",
     "object_id": "ko-risk", "message": "Vendor Lock-in quality dropped.",
     "status": "OPEN", "created_at": "2026-05-09T00:00:00"},
    {"id": 3, "alert_type": "ORPHANED", "severity": "INFO",
     "object_id": "ko-risk", "message": "Vendor Lock-in is orphaned.",
     "status": "OPEN", "created_at": "2026-05-08T00:00:00"},
]

# --- Compliance & standards ------------------------------------------------ #
STANDARDS = [
    {"object_id": "std-ec2", "name": "Eurocode 2", "authority": "CEN",
     "version": "2004", "jurisdiction": "EU", "status": "APPROVED"},
    {"object_id": "std-iso27001", "name": "ISO 27001", "authority": "ISO",
     "version": "2022", "jurisdiction": "Global", "status": "PROPOSED"},
]

REQUIREMENTS = [
    {"object_id": "req-ec2-bend", "name": "Bending resistance",
     "standard_object_id": "std-ec2", "clause_ref": "6.1",
     "title": "Design bending resistance", "requirement_text": "Members shall…",
     "obligation_level": "MUST", "status": "APPROVED"},
    {"object_id": "req-iso-a8", "name": "Access control",
     "standard_object_id": "std-iso27001", "clause_ref": "A.8",
     "title": "Access control policy", "requirement_text": "An access policy…",
     "obligation_level": "SHOULD", "status": "PROPOSED"},
]

EQUATIONS = [
    {"object_id": "eq-mrd", "name": "M_Rd", "standard_object_id": "std-ec2",
     "requirement_object_id": "req-ec2-bend", "clause_ref": "6.1",
     "symbol": "M_Rd", "title": "Design bending moment resistance",
     "expression": "A_s * f_yd * z", "python_code": "def M_Rd(A_s, f_yd, z):\n    return A_s * f_yd * z",
     "ast_json": "{\"type\": \"BinOp\", \"op\": \"Mult\"}",
     "variables": [{"symbol": "A_s", "description": "Area of steel", "unit": "mm^2"},
                   {"symbol": "f_yd", "description": "Design yield strength", "unit": "MPa"},
                   {"symbol": "z", "description": "Lever arm", "unit": "mm"}],
     "latex": "M_{Rd} = A_s f_{yd} z", "valid": True, "validation_note": "",
     "status": "PROPOSED"},
    {"object_id": "eq-bad", "name": "Broken", "standard_object_id": "std-ec2",
     "requirement_object_id": "req-ec2-bend", "clause_ref": "6.2", "symbol": "x",
     "title": "Invalid formula", "expression": "__import__('os')",
     "python_code": "", "ast_json": "", "variables": [], "latex": "",
     "valid": False, "validation_note": "imports are not allowed",
     "status": "PROPOSED"},
]

COVERAGE = {
    "overall": 0.5,
    "standards": [
        {"standard_object_id": "std-ec2", "standard_name": "Eurocode 2",
         "total": 2, "satisfied": 1, "partial": 1, "coverage": 0.75},
        {"standard_object_id": "std-iso27001", "standard_name": "ISO 27001",
         "total": 1, "satisfied": 0, "partial": 0, "coverage": 0.0},
    ],
}

GAPS = [
    {"object_id": "req-iso-a8", "requirement_name": "Access control",
     "clause_ref": "A.8", "title": "Access control policy",
     "obligation_level": "SHOULD", "standard_object_id": "std-iso27001",
     "standard_name": "ISO 27001"},
]

ASSESSMENTS = [
    {"id": 1, "requirement_object_id": "req-ec2-bend",
     "requirement_name": "Bending resistance", "control_object_id": "ko-relgov",
     "control_name": "Release Governance", "status": "SATISFIED",
     "review_status": "PROPOSED", "assessed_against_version": "2004",
     "rationale": "Control covers the clause."},
]


def _evidence_for(oid: str) -> list[dict]:
    n = 17 if oid == "ko-relgov" else 3
    return [{"id": i, "knowledge_object_id": oid, "artifact_id": "artifact-000",
             "quote": f"Evidence {i} for {oid}.", "page_number": i,
             "slide_number": None, "confidence": 0.8,
             "created_at": "2026-05-01T00:00:00"} for i in range(n)]


def _with_counts(o: dict | None) -> dict | None:
    """Annotate an object with the per-row counts Navigate now returns."""
    if o is None:
        return None
    rels = sum(1 for r in RELATIONSHIPS
               if r["source_object"] == o["id"] or r["target_object"] == o["id"])
    return {**o, "relationship_count": rels,
            "evidence_count": len(_evidence_for(o["id"])), "mention_count": 1}


CHANGES = [
    {"id": 3, "change_type": "STATUS_CHANGE", "target_kind": "knowledge_object",
     "object_id": "ko-sfdc", "field": "status", "old_value": "PROPOSED",
     "new_value": "APPROVED", "detail": None, "detected_at": "2026-05-12T00:00:00"},
    {"id": 2, "change_type": "NEW_OBJECT", "target_kind": "knowledge_object",
     "object_id": "ko-risk", "field": None, "old_value": None,
     "new_value": None, "detail": "Vendor Lock-in discovered",
     "detected_at": "2026-05-11T00:00:00"},
    {"id": 1, "change_type": "NEW_RELATIONSHIP", "target_kind": "relationship",
     "object_id": None, "field": None, "old_value": None, "new_value": None,
     "detail": "Salesforce affects Release Management",
     "detected_at": "2026-05-10T00:00:00"},
]

DOMAINS = [
    {"domain": "Test & Release", "owner": "Test & Release Team",
     "object_count": 3, "avg_quality": 84.0, "avg_freshness": 70.0,
     "review_backlog": 1},
    {"domain": "Platform", "owner": None, "object_count": 2,
     "avg_quality": 60.0, "avg_freshness": 40.0, "review_backlog": 2},
]

GROWTH = {"interval": "month", "points": [
    {"period": "2026-03", "artifacts_added": 4, "artifacts_total": 8,
     "objects_added": 2, "objects_total": 4, "relationships_added": 1,
     "relationships_total": 2},
    {"period": "2026-04", "artifacts_added": 4, "artifacts_total": 12,
     "objects_added": 2, "objects_total": 6, "relationships_added": 2,
     "relationships_total": 4},
]}

# --- Governance extras (drift / owners / object history) ------------------- #
DRIFT = [
    {"id": 9, "change_type": "QUALITY_DROP", "target_kind": "knowledge_object",
     "object_id": "ko-sfdc", "field": "quality_score", "old_value": "70",
     "new_value": "55", "detail": None, "detected_at": "2026-05-13T00:00:00"},
]

OWNERS = [
    {"object_id": "ko-relgov", "owner_type": "team",
     "owner_id": "Test & Release Team", "assigned_at": "2026-04-01T00:00:00",
     "assigned_by": "kristoffer"},
]

OBJECT_HISTORY = {
    "object_id": "ko-relgov",
    "changes": [
        {"id": 3, "change_type": "STATUS_CHANGE",
         "target_kind": "knowledge_object", "object_id": "ko-relgov",
         "field": "status", "old_value": "PROPOSED", "new_value": "APPROVED",
         "detail": None, "detected_at": "2026-05-01T00:00:00"},
    ],
    "lifecycle": {"review_state": "APPROVED", "freshness_state": "FRESH"},
    "owner": {"object_id": "ko-relgov", "owner_type": "team",
              "owner_id": "Test & Release Team", "assigned_at": None,
              "assigned_by": "kristoffer"},
}

# --- Cost / LLM usage ------------------------------------------------------ #
COST_SUMMARY = {
    "calls": 120, "input_tokens": 90000, "output_tokens": 30000,
    "total_tokens": 120000, "cache_read_tokens": 5000, "cache_write_tokens": 2000,
    "cost_usd": 1.85, "unpriced_calls": 3,
}
COST_BY_OPERATION = [
    {"operation": "extract", "calls": 60, "total_tokens": 70000, "cost_usd": 1.10},
    {"operation": "classify", "calls": 60, "total_tokens": 50000, "cost_usd": 0.75},
]
COST_BY_MODEL = [
    {"model": "claude-opus-4-8", "calls": 100, "total_tokens": 110000,
     "cost_usd": 1.70, "unpriced_calls": 0},
    {"model": "local/ollama", "calls": 20, "total_tokens": 10000,
     "cost_usd": None, "unpriced_calls": 3},
]
COST_PER_DOCUMENT = [
    {"artifact_id": "artifact-000", "calls": 12, "total_tokens": 24000,
     "cost_usd": 0.42},
]
COST_VS_QUALITY = [
    {"artifact_id": "artifact-000", "document_type": "docx",
     "type_confidence": 0.91, "calls": 12, "total_tokens": 24000,
     "cost_usd": 0.42},
]

# --- Graph analytics ------------------------------------------------------- #
GRAPH_HEALTH = {"islands": 1, "untraceable_claims": 2, "low_confidence": 3,
                "duplicates": 0, "connectivity": 0.87}
GRAPH_METRICS = {"density": 0.21, "components": 1, "clusters": 3,
                 "top_central": [{"id": "ko-relgov", "label": "Release Governance",
                                  "degree": 3}]}
GRAPH_DOMAINS = [
    {"domain": "Process", "object_count": 1, "relationship_count": 3,
     "most_central": [{"id": "ko-relgov", "label": "Release Governance",
                       "degree": 3}]},
]

# --- RDF projection -------------------------------------------------------- #
RDF_STATS = {"objects": 6, "relationships": 4, "evidence": 26,
             "knowledge_triples": 42, "relationship_triples": 12,
             "provenance_triples": 30}
RDF_VALIDATION = {"files": {
    "navigate.ttl": {"ok": True, "triples": 84, "error": None},
}}


def _paginate(items, limit, offset):
    return {"items": items[offset:offset + limit], "limit": limit,
            "offset": offset, "total": len(items)}


class FakeNavigateClient:
    """Implements the NavigateClient surface used by compas.service."""

    def __init__(self, fail: bool = False):
        self.fail = fail
        self.actions: list[tuple] = []

    def _maybe_fail(self):
        if self.fail:
            from compas.navigate_client import NavigateError
            raise NavigateError("Navigate API unreachable (test)")

    def close(self):
        pass

    # base
    def health(self):
        self._maybe_fail()
        return {"status": "ok", "database": {"ok": True}, "version": "1.2.3"}

    def stats(self):
        self._maybe_fail()
        return {"artifact_count": len(ARTIFACTS), "link_count": 5,
                "knowledge_object_count": len(OBJECTS), "relationship_count": len(RELATIONSHIPS),
                "evidence_count": 26, "pending_review_count": 2, "stale_object_count": 2,
                "last_scan": "2026-05-12T00:00:00"}

    # artifacts
    def list_artifacts(self, *, limit, offset, file_type=None, scan_status=None,
                       extraction_status=None, classification_status=None, search=None):
        self._maybe_fail()
        items = ARTIFACTS
        if file_type:
            items = [a for a in items if a["file_type"] == file_type]
        if search:
            items = [a for a in items if search.lower() in a["filename"].lower()]
        return _paginate(items, limit, offset)

    def get_artifact(self, artifact_id):
        self._maybe_fail()
        return next((a for a in ARTIFACTS if a["id"] == artifact_id), None)

    def artifact_links(self, artifact_id, *, limit=100, offset=0):
        return _paginate([{"id": 1, "source_artifact_id": artifact_id,
                           "raw_url": "https://x", "normalized_url": "https://x",
                           "anchor_text": "ref", "target_system": "confluence",
                           "target_type": "wiki_page", "link_kind": "external",
                           "status": "ACTIVE"}], limit, offset)

    def artifact_evidence(self, artifact_id, *, limit=100, offset=0):
        return _paginate(_evidence_for("ko-relgov")[:2], limit, offset)

    def artifact_action(self, artifact_id, action):
        self._maybe_fail()
        self.actions.append((artifact_id, action))
        return {"id": 99, "job_type": action, "status": "queued"}

    # knowledge
    def list_knowledge(self, *, limit, offset, object_type=None, status=None,
                       review_status=None, owner=None, domain=None,
                       min_confidence=None, search=None):
        self._maybe_fail()
        items = OBJECTS
        if object_type:
            items = [o for o in items if o["object_type"] == object_type]
        if status:
            items = [o for o in items if o["status"] == status]
        if review_status:
            items = [o for o in items if o["review_status"] == review_status]
        if search:
            items = [o for o in items if search.lower() in o["name"].lower()]
        return _paginate([_with_counts(o) for o in items], limit, offset)

    def get_knowledge(self, object_id):
        self._maybe_fail()
        return _with_counts(next((o for o in OBJECTS if o["id"] == object_id), None))

    def knowledge_approve_confidence(self, *, min_confidence, max_confidence=1.0,
                                     include_reviewed=False, note=None):
        self._maybe_fail()
        self.actions.append(("knowledge", "approve-confidence"))
        approved = sum(1 for o in OBJECTS
                       if (o.get("confidence") or 0) >= min_confidence)
        return {"min_confidence": min_confidence, "max_confidence": max_confidence,
                "objects_approved": approved, "relationships_approved": 0,
                "message": "ok"}

    def knowledge_evidence(self, object_id, *, limit=200, offset=0):
        return _paginate(_evidence_for(object_id), limit, offset)

    def knowledge_mentions(self, object_id, *, limit=200, offset=0):
        return _paginate([{"id": 1, "knowledge_object_id": object_id,
                           "artifact_id": "artifact-001", "confidence": 0.7,
                           "source_text": "x", "created_at": None}], limit, offset)

    def knowledge_relationships(self, object_id, *, limit=200, offset=0):
        self._maybe_fail()
        items = [r for r in RELATIONSHIPS
                 if r["source_object"] == object_id or r["target_object"] == object_id]
        return _paginate(items, limit, offset)

    def knowledge_action(self, object_id, action):
        self._maybe_fail()
        self.actions.append((object_id, action))
        for o in OBJECTS:
            if o["id"] == object_id:
                o["status"] = {"approve": "APPROVED", "reject": "REJECTED",
                               "archive": "ARCHIVED"}[action]
                o["review_status"] = o["status"]
        return {"id": object_id, "status": "ok", "message": "done"}

    # relationships
    def list_relationships(self, *, limit, offset, source_object_id=None,
                           target_object_id=None, predicate=None,
                           review_status=None, min_confidence=None):
        self._maybe_fail()
        items = RELATIONSHIPS
        if predicate:
            items = [r for r in items if r["predicate"] == predicate]
        if review_status:
            items = [r for r in items if r["review_status"] == review_status]
        return _paginate(items, limit, offset)

    def get_relationship(self, relationship_id):
        return next((r for r in RELATIONSHIPS if r["id"] == relationship_id), None)

    def relationship_action(self, relationship_id, action):
        self._maybe_fail()
        self.actions.append((relationship_id, action))
        return {"id": str(relationship_id), "status": "ok", "message": "done"}

    def relationships_approve_confidence(self, *, min_confidence, max_confidence=1.0,
                                         include_reviewed=False, note=None):
        self._maybe_fail()
        self.actions.append(("relationships", "approve-confidence"))
        approved = sum(1 for r in RELATIONSHIPS
                       if (r.get("confidence") or 0) >= min_confidence)
        return {"min_confidence": min_confidence, "max_confidence": max_confidence,
                "objects_approved": 0, "relationships_approved": approved,
                "message": "ok"}

    # evidence
    def list_evidence(self, *, limit, offset, artifact_id=None,
                      knowledge_object_id=None, relationship_id=None):
        items = _evidence_for(knowledge_object_id or "ko-relgov")
        return _paginate(items, limit, offset)

    # graph
    def graph_export(self):
        self._maybe_fail()
        nodes = [{"id": o["id"], "label": o["name"], "type": o["object_type"],
                  "confidence": o["confidence"], "status": o["status"],
                  "documents": 3, "mentions": 5} for o in OBJECTS]
        edges = [{"id": r["id"], "source": r["source_object"],
                  "target": r["target_object"], "predicate": r["predicate"],
                  "confidence": r["confidence"], "status": r["review_status"]}
                 for r in RELATIONSHIPS]
        return {"nodes": nodes, "edges": edges}

    def graph_nodes(self, *, limit=500, offset=0):
        return _paginate(self.graph_export()["nodes"], limit, offset)

    def graph_neighbors(self, object_id):
        self._maybe_fail()
        neighbors: dict[str, list] = {}
        names = {o["id"]: o for o in OBJECTS}
        for r in RELATIONSHIPS:
            if r["source_object"] == object_id:
                t = names[r["target_object"]]
                neighbors.setdefault(r["predicate"], []).append(
                    {"id": t["id"], "label": t["name"], "type": t["object_type"],
                     "direction": "out"})
            elif r["target_object"] == object_id:
                s = names[r["source_object"]]
                neighbors.setdefault(r["predicate"], []).append(
                    {"id": s["id"], "label": s["name"], "type": s["object_type"],
                     "direction": "in"})
        return {"object_id": object_id, "neighbors": neighbors}

    def graph_impact(self, object_id):
        return {"object_id": object_id, "impacted": []}

    def graph_path(self, source, target, max_depth=None):
        self._maybe_fail()
        # tiny BFS over RELATIONSHIPS (undirected)
        from collections import deque
        adj: dict[str, list[tuple[str, str]]] = {}
        for r in RELATIONSHIPS:
            adj.setdefault(r["source_object"], []).append((r["target_object"], r["predicate"]))
            adj.setdefault(r["target_object"], []).append((r["source_object"], r["predicate"]))
        q = deque([[source]])
        seen = {source}
        while q:
            path = q.popleft()
            if path[-1] == target:
                hops = []
                for a, b in zip(path, path[1:]):
                    pred = next((p for n, p in adj.get(a, []) if n == b), "related_to")
                    hops.append({"from": a, "to": b, "predicate": pred, "forward": True})
                return {"source": source, "target": target, "found": True, "hops": hops}
            for n, _p in adj.get(path[-1], []):
                if n not in seen:
                    seen.add(n)
                    q.append(path + [n])
        return {"source": source, "target": target, "found": False, "hops": []}

    # governance
    def gov_dashboard(self):
        self._maybe_fail()
        return {"domains": [{"domain": "Test & Release", "objects": 3,
                             "documents": 5, "quality": 84.0, "freshness": 70}]}

    def gov_review_queue(self):
        self._maybe_fail()
        return [{"object_id": o["id"], "name": o["name"],
                 "object_type": o["object_type"], "review_state": o["review_status"],
                 "freshness_state": o["freshness_state"],
                 "last_confidence": o["confidence"]}
                for o in OBJECTS if o["review_status"] == "PENDING_REVIEW"]

    def gov_stale(self):
        return [{"object_id": o["id"], "name": o["name"],
                 "object_type": o["object_type"], "freshness_state": "STALE",
                 "freshness_score": 0.2, "last_seen_at": None}
                for o in OBJECTS if o["freshness_state"] == "STALE"]

    def gov_orphaned(self):
        return {"orphaned": ["ko-risk"]}

    def gov_alerts(self, *, alert_type=None, severity=None):
        self._maybe_fail()
        items = ALERTS
        if alert_type:
            items = [a for a in items if a["alert_type"] == alert_type]
        return items

    def gov_quality(self, *, ascending=False):
        self._maybe_fail()
        return {"average_quality": 71.7,
                "items": [{"object_id": o["id"], "canonical_name": o["name"],
                           "object_type": o["object_type"],
                           "quality_score": o["quality_score"],
                           "evidence_count": 3, "document_count": 2}
                          for o in OBJECTS]}

    def gov_domains(self):
        self._maybe_fail()
        return DOMAINS

    def gov_domain(self, name):
        self._maybe_fail()
        return next((d for d in DOMAINS if d["domain"] == name), None)

    def gov_changes(self, *, limit=20, offset=0, object_id=None, change_type=None):
        self._maybe_fail()
        items = CHANGES
        if object_id:
            items = [c for c in items if c["object_id"] == object_id]
        if change_type:
            items = [c for c in items if c["change_type"] == change_type]
        return _paginate(items, limit, offset)

    def gov_growth(self, *, interval="month", limit=12):
        self._maybe_fail()
        return GROWTH

    def gov_drift(self, *, limit=20):
        self._maybe_fail()
        return DRIFT[:limit]

    def gov_owners(self):
        self._maybe_fail()
        return OWNERS

    def gov_object_history(self, object_id):
        self._maybe_fail()
        return {**OBJECT_HISTORY, "object_id": object_id}

    def gov_assign_owner(self, object_id, *, owner_type, owner_id):
        self._maybe_fail()
        self.actions.append((object_id, f"assign-owner:{owner_id}"))
        return {"id": object_id, "status": "ok", "message": "owner set"}

    def gov_flag(self, object_id):
        self._maybe_fail()
        self.actions.append((object_id, "flag"))
        return {"id": object_id, "status": "ok", "message": "flagged"}

    # cost / llm usage
    def cost_summary(self):
        self._maybe_fail()
        return COST_SUMMARY

    def cost_by_operation(self):
        self._maybe_fail()
        return COST_BY_OPERATION

    def cost_by_model(self):
        self._maybe_fail()
        return COST_BY_MODEL

    def cost_per_document(self, *, top=20):
        self._maybe_fail()
        return COST_PER_DOCUMENT[:top]

    def cost_vs_quality(self, *, top=20):
        self._maybe_fail()
        return COST_VS_QUALITY[:top]

    # graph analytics & exports
    def graph_health(self):
        self._maybe_fail()
        return GRAPH_HEALTH

    def graph_metrics(self, *, top=10):
        self._maybe_fail()
        return GRAPH_METRICS

    def graph_domains(self):
        self._maybe_fail()
        return GRAPH_DOMAINS

    def graph_export_gexf(self):
        self._maybe_fail()
        return b"<gexf></gexf>", "application/gexf+xml"

    def graph_export_graphml(self):
        self._maybe_fail()
        return b"<graphml></graphml>", "application/graphml+xml"

    # rdf projection
    def rdf_stats(self):
        self._maybe_fail()
        return RDF_STATS

    def rdf_validate(self):
        self._maybe_fail()
        return RDF_VALIDATION

    def rdf_export(self, *, fmt="turtle"):
        self._maybe_fail()
        return b"@prefix : <#> .", "text/turtle"

    # graphrag
    def ask(self, question, *, depth=2, show_context=True, show_evidence=True):
        self._maybe_fail()
        return {"answer": f"Release Governance supports the Launchpad Model. ({question})",
                "confidence": "high",
                "objects_used": [{"id": "ko-relgov", "label": "Release Governance",
                                  "type": "Process"}],
                "relationships_used": [{"source": "Release Governance",
                                        "predicate": "supports", "target": "Launchpad Model"}],
                "evidence_used": [{"document": "artifact-000", "handle": "h1",
                                   "quote": "Release Governance supports launches."}],
                "context": "graph-first retrieval context"}

    def _ask_reply(self, mode, **terms):
        self._maybe_fail()
        self.actions.append(("ask", mode))
        subject = terms.get("term") or terms.get("term_a") or "?"
        return {"answer": f"[{mode}] {subject}", "confidence": "medium",
                "objects_used": [{"id": "ko-relgov", "label": "Release Governance",
                                  "type": "Process"}],
                "relationships_used": [], "evidence_used": [],
                "context": None}

    def ask_explain(self, term, *, depth=2, show_context=True, show_evidence=True):
        return self._ask_reply("explain", term=term)

    def ask_impact(self, term, *, depth=2, show_context=True, show_evidence=True):
        return self._ask_reply("impact", term=term)

    def ask_compare(self, term_a, term_b, *, depth=2, show_context=True,
                    show_evidence=True):
        return self._ask_reply("compare", term_a=term_a, term_b=term_b)

    def ask_path_reason(self, term_a, term_b, *, depth=2, show_context=True,
                        show_evidence=True):
        return self._ask_reply("path-reason", term_a=term_a, term_b=term_b)

    # jobs / links
    def list_jobs(self, *, limit=25, offset=0, job_type=None, status=None):
        self._maybe_fail()
        return _paginate([{"id": 1, "job_type": "scan", "status": "COMPLETED",
                           "started_at": "2026-05-01T00:00:00",
                           "completed_at": "2026-05-01T00:05:00",
                           "error_message": None,
                           "result_summary": {"files": 12}}], limit, offset)

    def get_job(self, job_id):
        return {"id": job_id, "job_type": "scan", "status": "COMPLETED"}

    def link_stats(self):
        return {"total": 5, "by_target_system": [{"value": "confluence", "count": 3}],
                "by_target_type": [], "by_link_kind": []}

    def top_targets(self, *, limit=20):
        return [{"url": "https://x", "count": 3}]

    # compliance & standards
    def list_compliance_standards(self):
        self._maybe_fail()
        return STANDARDS

    def get_compliance_standard(self, object_id):
        self._maybe_fail()
        return next((s for s in STANDARDS if s["object_id"] == object_id), None)

    def list_compliance_requirements(self, *, limit, offset, standard=None):
        self._maybe_fail()
        items = REQUIREMENTS
        if standard:
            items = [r for r in items if r["standard_object_id"] == standard]
        return _paginate(items, limit, offset)

    def get_compliance_requirement(self, object_id):
        self._maybe_fail()
        return next((r for r in REQUIREMENTS if r["object_id"] == object_id), None)

    def list_compliance_equations(self, *, limit, offset, standard=None):
        self._maybe_fail()
        items = EQUATIONS
        if standard:
            items = [e for e in items if e["standard_object_id"] == standard]
        return _paginate(items, limit, offset)

    def get_compliance_equation(self, object_id):
        self._maybe_fail()
        return next((e for e in EQUATIONS if e["object_id"] == object_id), None)

    def compliance_coverage(self):
        self._maybe_fail()
        return COVERAGE

    def compliance_gaps(self):
        self._maybe_fail()
        return GAPS

    def compliance_assessments(self, *, status=None):
        self._maybe_fail()
        items = ASSESSMENTS
        if status:
            items = [a for a in items if a["status"] == status]
        return items

    def compliance_prove(self, requirement):
        self._maybe_fail()
        rel = [a for a in ASSESSMENTS if a["requirement_object_id"] == requirement]
        return {"found": bool(rel), "proven": any(a["status"] == "SATISFIED" for a in rel),
                "term": requirement, "message": "", "requirement": {},
                "assessments": rel}

    def assessment_action(self, assessment_id, action):
        self._maybe_fail()
        self.actions.append((assessment_id, action))
        return {"id": assessment_id, "status": "ok", "message": "done"}

    def compliance_assess(self):
        self._maybe_fail()
        self.actions.append(("assess", "assess"))
        return {"id": 77, "job_type": "assess", "status": "queued"}


@pytest.fixture()
def fake_client():
    return FakeNavigateClient()


@pytest.fixture()
def client(fake_client):
    """A TestClient whose Navigate dependency is the in-memory fake."""
    from fastapi.testclient import TestClient

    from compas.main import create_app
    from compas.navigate_client import get_client

    app = create_app()
    app.dependency_overrides[get_client] = lambda: fake_client
    with TestClient(app) as c:
        c.fake = fake_client  # type: ignore[attr-defined]
        yield c


@pytest.fixture()
def failing_client():
    """A TestClient whose Navigate dependency always fails (API down)."""
    from fastapi.testclient import TestClient

    from compas.main import create_app
    from compas.navigate_client import get_client

    app = create_app()
    app.dependency_overrides[get_client] = lambda: FakeNavigateClient(fail=True)
    with TestClient(app) as c:
        yield c
