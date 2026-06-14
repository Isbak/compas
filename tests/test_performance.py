"""Performance / scale tests.

Seeds a large synthetic graph (1000 objects, ~3000 relationships) and asserts
that paginated and graph queries stay fast and bounded — the dashboard must
support 10k+ artifacts and 100k+ relationships via pagination + lazy loading.
"""

from __future__ import annotations

import time
from datetime import datetime

import pytest

from compas import models, repository


@pytest.fixture()
def large_catalog(session):
    now = datetime(2026, 1, 1).isoformat()
    objects = []
    for i in range(1000):
        oid = f"big-{i:04d}"
        objects.append(models.KnowledgeObject(
            id=oid, name=f"Object {i}", object_type="Capability",
            description="bulk", confidence=0.8, status="APPROVED",
            created_at=now, updated_at=now))
    session.add_all(objects)
    session.add_all([
        models.KnowledgeEvidence(knowledge_object_id=f"big-{i:04d}",
                                 artifact_id="artifact-000", quote="q",
                                 confidence=0.7, created_at=now)
        for i in range(1000)])
    session.add_all([
        models.KnowledgeRelationship(
            source_object=f"big-{i % 1000:04d}", predicate="related_to",
            target_object=f"big-{(i + 1) % 1000:04d}", confidence=0.7,
            review_status="APPROVED", created_at=now)
        for i in range(3000)])
    session.commit()
    return session


def test_pagination_is_bounded_and_fast(large_catalog):
    start = time.perf_counter()
    page = repository.list_knowledge_objects(large_catalog, page=2, page_size=50)
    elapsed = time.perf_counter() - start
    assert page.total >= 1000
    assert len(page.items) == 50  # never returns the whole table
    assert elapsed < 2.0


def test_graph_payload_respects_limit(large_catalog):
    start = time.perf_counter()
    payload = repository.graph_payload(large_catalog, limit=100)
    elapsed = time.perf_counter() - start
    assert payload["node_count"] <= 100
    assert elapsed < 3.0


def test_neighbourhood_is_local(large_catalog):
    payload = repository.graph_payload(large_catalog, focus="big-0500", depth=1)
    ids = {n["data"]["id"] for n in payload["nodes"]}
    # Depth-1 neighbourhood on a ring graph stays tiny regardless of scale.
    assert "big-0500" in ids
    assert len(ids) < 20


def test_search_scales(large_catalog):
    start = time.perf_counter()
    res = repository.search(large_catalog, "Object 42", limit=20)
    assert time.perf_counter() - start < 3.0
    assert len(res["knowledge_objects"]) <= 20
