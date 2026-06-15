"""UI / HTMX route tests against a fake Navigate client."""

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


def test_compas_exposes_no_api(client):
    # Pure client: no public REST surface, no docs.
    assert client.get("/openapi.json").status_code == 404
    assert client.get("/api/artifacts").status_code == 404


def test_htmx_partial_is_fragment(client):
    full = client.get("/artifacts")
    partial = client.get("/artifacts", headers={"HX-Request": "true"})
    assert "<!DOCTYPE html>" in full.text
    assert "<!DOCTYPE html>" not in partial.text
    assert "table-wrap" in partial.text


def test_timeago_handles_timezone_aware_datetimes(client):
    from tests.conftest import ARTIFACTS

    original = ARTIFACTS[0]["modified_at"]
    ARTIFACTS[0]["modified_at"] = "2026-05-01T00:00:00+00:00"
    try:
        r = client.get("/artifacts")
    finally:
        ARTIFACTS[0]["modified_at"] = original
    assert r.status_code == 200
    assert "artifact-000" in r.text


def test_artifact_detail_page(client):
    r = client.get("/artifacts/artifact-000")
    assert r.status_code == 200
    assert "Details" in r.text


def test_knowledge_detail_page(client):
    r = client.get("/knowledge/ko-relgov")
    assert r.status_code == 200
    assert "Evidence" in r.text and "Relationships" in r.text
    assert "Launchpad Model" in r.text


def test_knowledge_review_partial(client):
    r = client.post("/knowledge/ko-sfdc/review", data={"action": "approve"})
    assert r.status_code == 200
    assert "badge" in r.text
    assert ("ko-sfdc", "approve") in client.fake.actions


def test_relationship_review(client):
    r = client.post("/relationships/4/review", data={"action": "approve"})
    assert r.status_code == 200
    # Badge class must match the styled CSS classes (past tense) and read
    # correctly — not the old unstyled "badge-approve"/"REJECTD".
    assert 'class="badge badge-approved"' in r.text
    assert "Approved" in r.text
    assert ("approve" in t for t in [a[1] for a in client.fake.actions])

    r = client.post("/relationships/4/review", data={"action": "reject"})
    assert 'class="badge badge-rejected"' in r.text
    assert "Rejected" in r.text and "REJECTD" not in r.text


def test_relationship_review_rejects_unknown_action(client):
    # A bogus action must not reach Navigate, must not be reflected into the
    # response (XSS), and must not return a fake "success" badge.
    payload = '"><script>alert(1)</script>'
    r = client.post("/relationships/4/review", data={"action": payload})
    assert r.status_code == 400
    assert "<script>" not in r.text
    assert client.fake.actions == []


def test_knowledge_review_rejects_unknown_action(client):
    r = client.post("/knowledge/ko-sfdc/review", data={"action": "<b>nope</b>"})
    assert r.status_code == 400
    assert "<b>nope" not in r.text
    assert client.fake.actions == []


def test_artifact_action_error_is_escaped(failing_client):
    # When Navigate errors, the message is HTML-escaped (no raw markup leaks
    # into the badge fragment).
    r = failing_client.post("/artifacts/artifact-000/extract")
    assert r.status_code == 502
    assert "<script" not in r.text


def test_artifact_action(client):
    r = client.post("/artifacts/artifact-000/extract")
    assert r.status_code == 200
    assert ("artifact-000", "extract") in client.fake.actions


def test_graph_data_endpoint(client):
    body = client.get("/graph/data").json()
    assert body["nodes"] and body["edges"]


def test_graph_path_endpoint(client):
    body = client.get("/graph/path?source=ko-relgov&target=ko-team").json()
    assert body["found"] is True


def test_graph_neighbors_endpoint(client):
    body = client.get("/graph/neighbors/ko-relgov?depth=1").json()
    ids = {n["data"]["id"] for n in body["nodes"]}
    assert "ko-relgov" in ids


def test_global_search_partial(client):
    r = client.get("/search?q=Release", headers={"HX-Request": "true"})
    assert r.status_code == 200
    assert "Release" in r.text


def test_graphrag_ask_partial(client):
    r = client.post("/graphrag/ask", data={"question": "What supports Release Governance?"})
    assert r.status_code == 200
    assert "answer-card" in r.text
    assert "Release Governance" in r.text


def test_notifications_partial(client):
    assert client.get("/notifications").status_code == 200


def test_404_page(client):
    r = client.get("/knowledge/does-not-exist")
    assert r.status_code == 404
    assert "404" in r.text


def test_static_assets_served(client):
    assert client.get("/static/js/compas.js").status_code == 200
    assert client.get("/static/js/graph.js").status_code == 200
    assert client.get("/static/css/styles.css").status_code == 200


def test_error_page_when_navigate_down(failing_client):
    r = failing_client.get("/")
    assert r.status_code == 502
    assert "Navigate API unavailable" in r.text
