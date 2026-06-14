"""Backend / data-access tests against the demo catalog."""

from __future__ import annotations

from compas import repository


def test_demo_catalog_seeded(session):
    stats = repository.dashboard_stats(session)
    assert stats["total_artifacts"] >= 40
    assert stats["knowledge_objects"] >= 15
    assert stats["relationships"] >= 15
    assert stats["evidence_count"] > 0
    assert 0 <= stats["quality_score"] <= 100


def test_every_object_has_evidence(session):
    """Navigate invariant: every knowledge object carries evidence."""
    page = repository.list_knowledge_objects(session, page_size=500)
    assert page.total >= 15
    for item in page.items:
        assert item["evidence_count"] > 0, item["name"]


def test_artifact_pagination(session):
    p1 = repository.list_artifacts(session, page=1, page_size=10)
    p2 = repository.list_artifacts(session, page=2, page_size=10)
    assert len(p1.items) == 10
    assert p1.total == p2.total
    ids1 = {i["id"] for i in p1.items}
    ids2 = {i["id"] for i in p2.items}
    assert ids1.isdisjoint(ids2)


def test_artifact_filters(session):
    opts = repository.artifact_filter_options(session)
    assert opts["file_types"]
    ft = opts["file_types"][0]
    page = repository.list_artifacts(session, file_type=ft, page_size=500)
    assert all(i["file_type"] == ft for i in page.items)


def test_knowledge_detail_release_governance(session):
    """The worked example from the spec must be fully wired up."""
    page = repository.list_knowledge_objects(session, q="Release Governance")
    match = next(i for i in page.items if i["name"] == "Release Governance")
    detail = repository.get_knowledge_object(session, match["id"])
    assert detail is not None
    assert detail["evidence_count"] == 17
    targets = {r["name"] for items in detail["relationships"].values() for r in items}
    assert "Launchpad Model" in targets
    assert "Release Management" in targets
    assert "Test & Release Team" in targets


def test_review_object_persists(session):
    page = repository.list_knowledge_objects(session, status="PROPOSED", page_size=5)
    assert page.items
    oid = page.items[0]["id"]
    assert repository.review_object(session, oid, "approve")
    detail = repository.get_knowledge_object(session, oid)
    assert detail["status"] == "APPROVED"
    assert any(h["change_type"] == "APPROVE" for h in detail["history"])


def test_review_relationship_persists(session):
    page = repository.list_relationships(session, review_status="PROPOSED", page_size=5)
    assert page.items
    rid = page.items[0]["id"]
    assert repository.review_relationship(session, rid, "approve")
    again = repository.list_relationships(session, page_size=500)
    found = next(r for r in again.items if r["id"] == rid)
    assert found["review_status"] == "APPROVED"


def test_domain_overview_and_detail(session):
    overview = repository.domain_overview(session)
    assert overview
    domain = overview[0]["domain"]
    detail = repository.get_domain(session, domain)
    assert detail["object_count"] >= 0
    assert "objects" in detail


def test_governance_center(session):
    gov = repository.governance_center(session)
    assert "review_queue" in gov
    assert "alerts" in gov
    assert gov["alerts"]


def test_knowledge_health_metrics(session):
    h = repository.knowledge_health(session)
    for key in ("quality_score", "freshness", "review_coverage",
                "evidence_coverage", "relationship_coverage"):
        assert 0 <= h[key] <= 100


def test_search_fuzzy(session):
    res = repository.search(session, "Releas")  # misspelt / partial
    names = {o["name"] for o in res["knowledge_objects"]}
    assert any("Release" in n for n in names)


def test_observability(session):
    obs = repository.observability(session)
    assert obs["scan_jobs"]
    assert obs["classification_jobs"]
