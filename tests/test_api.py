"""REST API tests covering every documented endpoint family."""

from __future__ import annotations

import pytest


def test_healthz(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_stats_endpoint(client):
    r = client.get("/api/stats")
    assert r.status_code == 200
    body = r.json()
    assert body["stats"]["knowledge_objects"] > 0
    assert "domains" in body and "growth" in body


def test_artifacts_endpoint(client):
    r = client.get("/api/artifacts?page=1&page_size=5")
    assert r.status_code == 200
    body = r.json()
    assert len(body["items"]) == 5
    assert body["total"] >= 40
    assert body["has_next"] is True


def test_artifact_detail_and_404(client):
    listing = client.get("/api/artifacts").json()
    aid = listing["items"][0]["id"]
    assert client.get(f"/api/artifacts/{aid}").status_code == 200
    assert client.get("/api/artifacts/nope").status_code == 404


def test_knowledge_endpoints(client):
    listing = client.get("/api/knowledge?sort=quality").json()
    assert listing["items"]
    oid = listing["items"][0]["id"]
    detail = client.get(f"/api/knowledge/{oid}").json()
    assert detail["id"] == oid
    assert "relationships" in detail


def test_knowledge_review_via_api(client):
    listing = client.get("/api/knowledge?status=PROPOSED").json()
    oid = listing["items"][0]["id"]
    r = client.post(f"/api/knowledge/{oid}/review", json={"action": "approve"})
    assert r.status_code == 200
    assert r.json()["action"] == "APPROVE"
    assert client.get(f"/api/knowledge/{oid}").json()["status"] == "APPROVED"


def test_relationships_endpoints(client):
    r = client.get("/api/relationships")
    assert r.status_code == 200
    rid = r.json()["items"][0]["id"]
    rev = client.post(f"/api/relationships/{rid}/review", json={"action": "reject"})
    assert rev.status_code == 200


def test_evidence_endpoint(client):
    r = client.get("/api/evidence?page=1")
    assert r.status_code == 200
    assert r.json()["total"] > 0


def test_domains_endpoints(client):
    domains = client.get("/api/domains").json()["domains"]
    assert domains
    d = domains[0]["domain"]
    assert client.get(f"/api/domains/{d}").status_code == 200


def test_governance_endpoints(client):
    assert client.get("/api/governance").status_code == 200
    assert client.get("/api/governance/health").status_code == 200
    alerts = client.get("/api/governance/alerts").json()["alerts"]
    assert alerts
    aid = alerts[0]["id"]
    assert client.post(f"/api/governance/alerts/{aid}/resolve").status_code == 200


def test_search_endpoint(client):
    r = client.get("/api/search?q=Salesforce")
    assert r.status_code == 200
    assert r.json()["total"] >= 1


def test_graphrag_endpoint(client):
    r = client.post("/api/graphrag", json={"question": "What supports Release Governance?"})
    assert r.status_code == 200
    body = r.json()
    assert body["answer"]
    assert body["sparql_queries"]
    assert body["knowledge_objects_used"]


def test_graphrag_suggestions(client):
    r = client.get("/api/graphrag/suggestions")
    assert r.status_code == 200
    assert r.json()["questions"]


def test_notifications_and_observability(client):
    assert client.get("/api/notifications").status_code == 200
    assert client.get("/api/observability").status_code == 200


def test_fuseki_status_disabled(client):
    r = client.get("/api/fuseki/status")
    assert r.status_code == 200
    assert r.json()["enabled"] is False  # local-first default
