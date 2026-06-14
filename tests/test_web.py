"""UI / HTMX route tests — every page renders and partials return fragments."""

from __future__ import annotations

import pytest

PAGES = ["/", "/artifacts", "/knowledge", "/relationships", "/domains",
         "/governance", "/graph", "/graphrag", "/observability", "/settings"]


@pytest.mark.parametrize("path", PAGES)
def test_pages_render(client, path):
    r = client.get(path)
    assert r.status_code == 200
    assert "<!DOCTYPE html>" in r.text
    assert "Compas" in r.text


def test_htmx_partial_is_fragment(client):
    """An HX-Request returns just the table, not the whole page."""
    full = client.get("/artifacts")
    partial = client.get("/artifacts", headers={"HX-Request": "true"})
    assert "<!DOCTYPE html>" in full.text
    assert "<!DOCTYPE html>" not in partial.text
    assert "table-wrap" in partial.text


def test_artifact_detail_page(client):
    aid = client.get("/api/artifacts").json()["items"][0]["id"]
    r = client.get(f"/artifacts/{aid}")
    assert r.status_code == 200
    assert "Classification" in r.text or "Details" in r.text


def test_knowledge_detail_page(client):
    oid = client.get("/api/knowledge").json()["items"][0]["id"]
    r = client.get(f"/knowledge/{oid}")
    assert r.status_code == 200
    assert "Evidence" in r.text
    assert "Relationships" in r.text


def test_knowledge_review_partial(client):
    listing = client.get("/api/knowledge?status=PROPOSED").json()
    oid = listing["items"][0]["id"]
    r = client.post(f"/knowledge/{oid}/review", data={"action": "approve"})
    assert r.status_code == 200
    assert "badge" in r.text


def test_global_search_partial(client):
    r = client.get("/search?q=Release", headers={"HX-Request": "true"})
    assert r.status_code == 200
    assert "Release" in r.text


def test_graphrag_ask_partial(client):
    r = client.post("/graphrag/ask", data={"question": "What supports Release Governance?"})
    assert r.status_code == 200
    assert "Knowledge Objects Used" in r.text or "answer-card" in r.text


def test_notifications_partial(client):
    r = client.get("/notifications")
    assert r.status_code == 200


def test_404_page(client):
    r = client.get("/knowledge/does-not-exist")
    assert r.status_code == 404
    assert "404" in r.text


def test_static_assets_served(client):
    assert client.get("/static/js/compas.js").status_code == 200
    assert client.get("/static/js/graph.js").status_code == 200
    assert client.get("/static/css/styles.css").status_code == 200
