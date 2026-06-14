"""Graph endpoints: payloads, neighbourhoods and shortest paths."""

from __future__ import annotations

from compas import repository


def _id(session, name):
    page = repository.list_knowledge_objects(session, q=name, page_size=500)
    return next(i["id"] for i in page.items if i["name"] == name)


def test_graph_payload_shape(client):
    r = client.get("/api/graph")
    assert r.status_code == 200
    body = r.json()
    assert body["nodes"]
    assert body["edges"]
    node = body["nodes"][0]["data"]
    assert {"id", "label", "type"} <= set(node)


def test_graph_mode_filter(client):
    body = client.get("/api/graph?mode=team").json()
    types = {n["data"]["type"] for n in body["nodes"]}
    # A team-centred view must include at least one Team node.
    assert "Team" in types


def test_graph_neighbours(client, session):
    oid = _id(session, "Release Governance")
    body = client.get(f"/api/graph/neighbors/{oid}?depth=1").json()
    ids = {n["data"]["id"] for n in body["nodes"]}
    assert oid in ids
    assert len(ids) > 1


def test_shortest_path(client, session):
    src = _id(session, "Release Governance")
    dst = _id(session, "Test & Release Team")
    r = client.get(f"/api/graph/path?source={src}&target={dst}")
    body = r.json()
    assert body["found"] is True
    assert body["length"] >= 1
    assert body["nodes"][0]["id"] == src
    assert body["nodes"][-1]["id"] == dst


def test_graph_node_limit(client, session):
    # Limit is honoured so large graphs load incrementally.
    body = client.get("/api/graph?limit=5").json()
    assert len(body["nodes"]) <= 5


def test_graph_min_confidence(client):
    high = client.get("/api/graph?min_confidence=0.85").json()
    low = client.get("/api/graph?min_confidence=0.0").json()
    assert len(high["edges"]) <= len(low["edges"])
