"""Service-layer tests: Navigate API responses → view-models."""

from __future__ import annotations

from compas import service


def test_dashboard_maps_stats(fake_client):
    d = service.dashboard(fake_client)
    assert d["total_artifacts"] == 12
    assert d["knowledge_objects"] == 6
    assert d["relationships"] == 4
    assert d["approved_objects"] == 4          # status=APPROVED count
    assert d["quality_score"] == 71.7
    assert d["approved_pct"] > 0


def test_list_artifacts_pagination(fake_client):
    page = service.list_artifacts(fake_client, page=1, page_size=5)
    assert len(page.items) == 5
    assert page.total == 12
    assert page.pages == 3
    assert page.has_next and not page.has_prev


def test_list_knowledge_filter(fake_client):
    page = service.list_knowledge(fake_client, object_type="Team")
    assert page.items
    assert all(i["type"] == "Team" for i in page.items)


def test_knowledge_detail_uses_neighbors_and_evidence(fake_client):
    detail = service.get_knowledge(fake_client, "ko-relgov")
    assert detail["name"] == "Release Governance"
    assert detail["evidence_count"] == 17           # invariant honoured
    targets = {r["name"] for items in detail["relationships"].values() for r in items}
    assert {"Launchpad Model", "Release Management", "Test & Release Team"} <= targets


def test_relationship_names_resolved(fake_client):
    page = service.list_relationships(fake_client)
    rel = next(r for r in page.items if r["id"] == 1)
    assert rel["source"] == "Release Governance"
    assert rel["target"] == "Launchpad Model"
    assert rel["predicate_label"] == "supports"


def test_review_object_calls_api(fake_client):
    assert service.review_object(fake_client, "ko-sfdc", "approve")
    assert ("ko-sfdc", "approve") in fake_client.actions


def test_graph_payload_shape(fake_client):
    payload = service.graph_payload(fake_client)
    assert payload["nodes"] and payload["edges"]
    node = payload["nodes"][0]["data"]
    assert {"id", "label", "type"} <= set(node)


def test_graph_neighbors_focus(fake_client):
    payload = service.graph_payload(fake_client, focus="ko-relgov", depth=1)
    ids = {n["data"]["id"] for n in payload["nodes"]}
    assert "ko-relgov" in ids and "ko-launch" in ids


def test_shortest_path(fake_client):
    path = service.shortest_path(fake_client, "ko-relgov", "ko-team")
    assert path["found"] is True
    assert path["nodes"][0]["name"] == "Release Governance"
    assert path["nodes"][-1]["name"] == "Test & Release Team"


def test_governance_center(fake_client):
    gov = service.governance_center(fake_client)
    assert gov["review_queue"]
    assert gov["alerts"]
    assert gov["stale_objects"]


def test_knowledge_health(fake_client):
    h = service.knowledge_health(fake_client)
    assert h["quality_score"] == 71.7
    assert 0 <= h["review_coverage"] <= 100
    # Not exposed by Navigate → None, not invented.
    assert h["evidence_coverage"] is None


def test_search(fake_client):
    res = service.search(fake_client, "Release")
    names = {o["name"] for o in res["knowledge_objects"]}
    assert any("Release" in n for n in names)


def test_ask_maps_navigate_response(fake_client):
    ans = service.ask(fake_client, "What supports Release Governance?")
    assert ans["confidence"] == "high"
    assert ans["objects_used"][0]["name"] == "Release Governance"
    assert ans["evidence"]
    assert ans["focus_id"] == "ko-relgov"


# --- Compliance & standards ------------------------------------------------ #
def test_compliance_home_maps_coverage(fake_client):
    home = service.compliance_home(fake_client)
    assert home["overall"] == 0.5
    assert home["standard_count"] == 2
    assert home["equation_count"] == 2
    assert {s["standard_name"] for s in home["coverage"]} == {"Eurocode 2", "ISO 27001"}
    assert home["gaps"] and home["gaps"][0]["standard_name"] == "ISO 27001"


def test_standard_detail_includes_requirements_and_equations(fake_client):
    std = service.get_standard(fake_client, "std-ec2")
    assert std["name"] == "Eurocode 2"
    assert any(r["id"] == "req-ec2-bend" for r in std["requirements"])
    assert any(e["id"] == "eq-mrd" for e in std["equations"])


def test_equation_detail_pretty_prints_ast_and_resolves_names(fake_client):
    eq = service.get_equation(fake_client, "eq-mrd")
    assert eq["symbol"] == "M_Rd"
    assert eq["standard_name"] == "Eurocode 2"
    # AST string is reformatted with indentation for display.
    assert "\n" in eq["ast_pretty"]
    assert [v["symbol"] for v in eq["variables"]] == ["A_s", "f_yd", "z"]


def test_invalid_equation_keeps_validation_note(fake_client):
    eq = service.get_equation(fake_client, "eq-bad")
    assert eq["valid"] is False
    assert "imports" in eq["validation_note"]


def test_requirement_detail_narrows_equations(fake_client):
    req = service.get_requirement(fake_client, "req-ec2-bend")
    assert req["standard_name"] == "Eurocode 2"
    assert all(e["requirement_object_id"] == "req-ec2-bend" for e in req["equations"])
    assert req["proof"]["proven"] is True


def test_review_assessment_calls_dedicated_endpoint(fake_client):
    assert service.review_assessment(fake_client, 1, "approve")
    assert (1, "approve") in fake_client.actions
