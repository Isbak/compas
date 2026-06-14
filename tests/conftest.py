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


def _evidence_for(oid: str) -> list[dict]:
    n = 17 if oid == "ko-relgov" else 3
    return [{"id": i, "knowledge_object_id": oid, "artifact_id": "artifact-000",
             "quote": f"Evidence {i} for {oid}.", "page_number": i,
             "slide_number": None, "confidence": 0.8,
             "created_at": "2026-05-01T00:00:00"} for i in range(n)]


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
                "evidence_count": 26, "pending_review_count": 2, "stale_object_count": 2}

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
        return _paginate(items, limit, offset)

    def get_knowledge(self, object_id):
        self._maybe_fail()
        return next((o for o in OBJECTS if o["id"] == object_id), None)

    def knowledge_evidence(self, object_id, *, limit=200, offset=0):
        return _paginate(_evidence_for(object_id), limit, offset)

    def knowledge_mentions(self, object_id, *, limit=200, offset=0):
        return _paginate([{"id": 1, "knowledge_object_id": object_id,
                           "artifact_id": "artifact-001", "confidence": 0.7,
                           "source_text": "x", "created_at": None}], limit, offset)

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
