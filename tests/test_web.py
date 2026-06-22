"""UI / HTMX route tests against a fake Navigate client."""

from __future__ import annotations

import pytest

PAGES = ["/", "/artifacts", "/knowledge", "/relationships", "/domains",
         "/governance", "/costs", "/graph", "/graphrag", "/observability",
         "/settings", "/compliance", "/compliance/standards",
         "/compliance/requirements", "/compliance/equations",
         "/compliance/gaps", "/compliance/assessments"]


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


def test_relationships_filter_by_predicate(client):
    # Server-side predicate filter narrows the table to matching triples.
    r = client.get("/relationships?predicate=affects", headers={"HX-Request": "true"})
    assert r.status_code == 200
    assert "affects" in r.text and "supports" not in r.text


def test_relationships_search_matches_source_or_target(client):
    # Navigate's /relationships has no free-text search, so Compas resolves
    # object names and filters by source/target client-side. Searching for the
    # target "Salesforce" must keep its "affects" triple and drop unrelated ones.
    r = client.get("/relationships?q=Salesforce", headers={"HX-Request": "true"})
    assert r.status_code == 200
    assert "affects" in r.text
    assert "supports" not in r.text and "implemented by" not in r.text

    # Searching by source name returns that object's outgoing triples.
    r = client.get("/relationships?q=Release Governance",
                   headers={"HX-Request": "true"})
    assert "supports" in r.text
    assert "affects" not in r.text


def test_relationships_search_combines_with_predicate(client):
    r = client.get("/relationships?q=Release&predicate=supports",
                   headers={"HX-Request": "true"})
    assert r.status_code == 200
    assert "supports" in r.text and "affects" not in r.text


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


def test_relationship_archive(client):
    r = client.post("/relationships/4/review", data={"action": "archive"})
    assert r.status_code == 200
    assert 'class="badge badge-archived"' in r.text
    assert "Archived" in r.text
    assert (4, "archive") in client.fake.actions


def test_governance_changes_fragment(client):
    r = client.get("/governance/changes", headers={"HX-Request": "true"})
    assert r.status_code == 200
    assert "<!DOCTYPE html>" not in r.text
    # Object ids are resolved to display names from the knowledge list.
    assert "Salesforce" in r.text


def test_governance_growth_fragment(client):
    r = client.get("/governance/growth", headers={"HX-Request": "true"})
    assert r.status_code == 200
    assert "2026-04" in r.text


def test_governance_bulk_approve_knowledge(client):
    r = client.post("/governance/approve-confidence/knowledge",
                    data={"min_confidence": "0.9"})
    assert r.status_code == 200
    assert "Approved" in r.text and "objects" in r.text
    assert ("knowledge", "approve-confidence") in client.fake.actions


def test_governance_bulk_approve_relationships(client):
    r = client.post("/governance/approve-confidence/relationships",
                    data={"min_confidence": "0.8"})
    assert r.status_code == 200
    assert "Approved" in r.text and "relationships" in r.text
    assert ("relationships", "approve-confidence") in client.fake.actions


def test_governance_bulk_approve_rejects_unknown_kind(client):
    r = client.post("/governance/approve-confidence/bogus",
                    data={"min_confidence": "0.9"})
    assert r.status_code == 400
    assert client.fake.actions == []


def test_dashboard_shows_last_scan(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "Last scan" in r.text


def test_knowledge_table_shows_counts(client):
    r = client.get("/knowledge", headers={"HX-Request": "true"})
    assert r.status_code == 200
    assert "Links" in r.text


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


def test_graphrag_ask_explain_mode(client):
    r = client.post("/graphrag/ask",
                    data={"question": "Release Governance", "mode": "explain"})
    assert r.status_code == 200
    assert ("ask", "explain") in client.fake.actions


def test_graphrag_ask_compare_uses_two_terms(client):
    r = client.post("/graphrag/ask", data={
        "question": "Release Governance", "mode": "compare",
        "term_b": "Launchpad Model"})
    assert r.status_code == 200
    assert ("ask", "compare") in client.fake.actions


def test_graphrag_ask_unknown_mode_falls_back(client):
    # An unknown mode must not reach a bogus Navigate path; it degrades to /ask.
    r = client.post("/graphrag/ask",
                    data={"question": "x", "mode": "../etc"})
    assert r.status_code == 200
    assert not any(a == ("ask", "../etc") for a in client.fake.actions)


# --- Cost / LLM usage ------------------------------------------------------ #
def test_cost_page_shows_summary(client):
    r = client.get("/costs")
    assert r.status_code == 200
    assert "Cost" in r.text
    assert "claude-opus-4-8" in r.text          # by-model breakdown rendered
    assert "$1.85" in r.text                     # total spend formatted


def test_cost_page_unavailable_degrades(failing_client):
    # No cost ledger → an explanatory panel, not a 502.
    r = failing_client.get("/costs")
    assert r.status_code == 200
    assert "isn't available" in r.text


# --- Graph / RDF exports --------------------------------------------------- #
def test_graph_export_gexf(client):
    r = client.get("/graph/export/gexf")
    assert r.status_code == 200
    assert "attachment" in r.headers["content-disposition"]
    assert "gexf" in r.text


def test_graph_export_unknown_format(client):
    assert client.get("/graph/export/bogus").status_code == 400


def test_rdf_export_turtle(client):
    r = client.get("/rdf/export?fmt=turtle")
    assert r.status_code == 200
    assert "navigate.ttl" in r.headers["content-disposition"]


def test_rdf_export_unknown_format(client):
    assert client.get("/rdf/export?fmt=bogus").status_code == 400


def test_observability_shows_graph_analytics_and_rdf(client):
    r = client.get("/observability")
    assert r.status_code == 200
    assert "Graph analytics" in r.text
    assert "RDF projection" in r.text
    assert "GEXF" in r.text and "Turtle" in r.text


# --- Knowledge ownership / flag / history ---------------------------------- #
def test_knowledge_history_fragment(client):
    r = client.get("/knowledge/ko-relgov/history", headers={"HX-Request": "true"})
    assert r.status_code == 200
    assert "<!DOCTYPE html>" not in r.text
    assert "Status Change" in r.text


def test_knowledge_assign_owner(client):
    r = client.post("/knowledge/ko-relgov/assign-owner",
                    data={"owner_id": "Platform Team", "owner_type": "team"})
    assert r.status_code == 200
    assert "Owner set" in r.text
    assert ("ko-relgov", "assign-owner:Platform Team") in client.fake.actions


def test_knowledge_assign_owner_requires_value(client):
    r = client.post("/knowledge/ko-relgov/assign-owner",
                    data={"owner_id": "  "})
    assert r.status_code == 400
    assert client.fake.actions == []


def test_knowledge_flag(client):
    r = client.post("/knowledge/ko-relgov/flag")
    assert r.status_code == 200
    assert "Flagged" in r.text
    assert ("ko-relgov", "flag") in client.fake.actions


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


# --- Compliance & standards ------------------------------------------------ #
def test_equation_detail_page(client):
    r = client.get("/compliance/equations/eq-mrd")
    assert r.status_code == 200
    assert "M_Rd" in r.text
    assert "Variables" in r.text and "A_s" in r.text
    # Machine-readable surfaces are rendered.
    assert "Python" in r.text and "syntax tree" in r.text


def test_requirement_detail_page(client):
    r = client.get("/compliance/requirements/req-ec2-bend")
    assert r.status_code == 200
    assert "Design bending resistance" in r.text
    assert "Eurocode 2" in r.text


def test_standard_detail_page(client):
    r = client.get("/compliance/standards/std-ec2")
    assert r.status_code == 200
    assert "Eurocode 2" in r.text and "M_Rd" in r.text


def test_equations_filter_by_standard(client):
    r = client.get("/compliance/equations?standard=std-ec2",
                   headers={"HX-Request": "true"})
    assert r.status_code == 200
    assert "<!DOCTYPE html>" not in r.text
    assert "M_Rd" in r.text


def test_equation_review_uses_knowledge_action(client):
    # Equations are knowledge objects: approval reuses the KO action endpoint.
    r = client.post("/compliance/equations/eq-mrd/review",
                    data={"action": "approve"})
    assert r.status_code == 200
    assert 'class="badge badge-approved"' in r.text
    assert ("eq-mrd", "approve") in client.fake.actions


def test_assessment_review_uses_assessment_action(client):
    r = client.post("/compliance/assessments/1/review", data={"action": "approve"})
    assert r.status_code == 200
    assert 'class="badge badge-approved"' in r.text
    assert (1, "approve") in client.fake.actions


def test_compliance_review_rejects_unknown_resource(client):
    r = client.post("/compliance/bogus/x/review", data={"action": "approve"})
    assert r.status_code == 400
    assert client.fake.actions == []


def test_run_assessment_enqueues_job(client):
    r = client.post("/compliance/assess")
    assert r.status_code == 200
    assert "Job #77" in r.text
    assert ("assess", "assess") in client.fake.actions
