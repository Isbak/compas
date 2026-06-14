"""NavigateClient tests using an httpx MockTransport (no real server)."""

from __future__ import annotations

import httpx
import pytest

from compas.config import Settings
from compas.navigate_client import NavigateClient, NavigateError


def _make_client(handler, *, api_key=""):
    settings = Settings(navigate_api_url="http://nav.test/api",
                        navigate_api_key=api_key)
    transport = httpx.MockTransport(handler)
    http = httpx.Client(base_url=settings.navigate_api_url, transport=transport,
                        headers={"Authorization": f"Bearer {api_key}"} if api_key else {})
    return NavigateClient(settings=settings, client=http)


def test_builds_paginated_url():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, json={"items": [], "limit": 50, "offset": 0,
                                         "total": 0})

    client = _make_client(handler)
    client.list_artifacts(limit=50, offset=100, file_type="docx")
    assert "/api/artifacts" in seen["url"]
    assert "limit=50" in seen["url"]
    assert "offset=100" in seen["url"]
    assert "file_type=docx" in seen["url"]
    # None filters must be dropped, not sent as empty.
    assert "scan_status" not in seen["url"]


def test_knowledge_objects_path_and_actions():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["method"] = request.method
        return httpx.Response(200, json={"id": "x", "status": "ok", "message": "y"})

    client = _make_client(handler)
    client.knowledge_action("ko-1", "approve")
    assert seen["path"] == "/api/knowledge-objects/ko-1/approve"
    assert seen["method"] == "POST"


def test_bearer_auth_header():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers.get("Authorization")
        return httpx.Response(200, json={"status": "ok"})

    client = _make_client(handler, api_key="secret-key")
    client.health()
    assert seen["auth"] == "Bearer secret-key"


def test_error_envelope_raises_navigate_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"error": "not_found",
                                         "message": "No such object",
                                         "details": {}})

    client = _make_client(handler)
    with pytest.raises(NavigateError) as exc:
        client.get_knowledge("missing")
    assert exc.value.status == 404
    assert "No such object" in str(exc.value)


def test_connection_error_raises_navigate_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    client = _make_client(handler)
    with pytest.raises(NavigateError):
        client.stats()


def test_ask_posts_body():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"answer": "ok", "confidence": "high",
                                         "objects_used": [], "relationships_used": [],
                                         "evidence_used": [], "context": None})

    client = _make_client(handler)
    client.ask("Why?", depth=3)
    assert seen["body"]["question"] == "Why?"
    assert seen["body"]["depth"] == 3
