"""HTTP client for the Navigate REST API.

This is Compas's *only* backend. Every page and partial is rendered from data
fetched here. The client is intentionally thin: one method per Navigate
endpoint, returning the parsed JSON (dicts / envelopes) exactly as Navigate
sends it. Shaping into view-models happens in :mod:`compas.service`.

Tests inject a fake implementing the same surface, so no real server is needed.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

import httpx

from .config import Settings, get_settings

#: Allowlists for the POST action endpoints. The action is interpolated into
#: the request path, so we never let an arbitrary value through — both to keep
#: Compas from hitting an unintended Navigate endpoint and as defence in depth
#: behind the route-level checks.
ARTIFACT_ACTIONS = frozenset({"rescan", "extract", "classify"})
KNOWLEDGE_ACTIONS = frozenset({"approve", "reject", "archive"})
RELATIONSHIP_ACTIONS = frozenset({"approve", "reject"})


def _seg(value: Any) -> str:
    """Percent-encode a single URL path segment.

    Ids come from the browser (URL path / form data) and are interpolated into
    Navigate request paths. Encoding every segment with ``safe=""`` means a
    value containing ``/``, ``?``, ``#`` or ``..`` can't escape its segment and
    redirect the call to a different Navigate endpoint.
    """
    return quote(str(value), safe="")


class NavigateError(RuntimeError):
    """Raised when Navigate returns an error or is unreachable."""

    def __init__(self, message: str, *, status: int | None = None,
                 details: Any = None):
        super().__init__(message)
        self.status = status
        self.details = details


class NavigateClient:
    """Thin wrapper over Navigate's ``/api`` surface."""

    def __init__(self, settings: Settings | None = None,
                 client: httpx.Client | None = None):
        self.settings = settings or get_settings()
        headers = {"Accept": "application/json"}
        if self.settings.navigate_api_key:
            headers["Authorization"] = f"Bearer {self.settings.navigate_api_key}"
        self._client = client or httpx.Client(
            base_url=self.settings.navigate_api_url.rstrip("/"),
            headers=headers,
            timeout=self.settings.navigate_timeout,
        )

    # -- low level -------------------------------------------------------- #
    def _request(self, method: str, path: str, **kwargs) -> Any:
        try:
            resp = self._client.request(method, path, **kwargs)
        except httpx.RequestError as exc:
            raise NavigateError(
                f"Could not reach Navigate API at "
                f"{self.settings.navigate_api_url}: {exc}") from exc
        if resp.status_code >= 400:
            detail: Any = None
            try:
                detail = resp.json()
            except ValueError:
                detail = resp.text
            msg = detail.get("message") if isinstance(detail, dict) else str(detail)
            raise NavigateError(msg or f"HTTP {resp.status_code}",
                                status=resp.status_code, details=detail)
        if resp.status_code == 204 or not resp.content:
            return None
        return resp.json()

    def _get(self, path: str, params: dict | None = None) -> Any:
        return self._request("GET", path, params=_clean(params))

    def _post(self, path: str, json: dict | None = None, **kw) -> Any:
        return self._request("POST", path, json=json, **kw)

    def close(self) -> None:
        self._client.close()

    # -- base ------------------------------------------------------------- #
    def health(self) -> dict:
        return self._get("/health")

    def stats(self) -> dict:
        return self._get("/stats")

    # -- artifacts -------------------------------------------------------- #
    def list_artifacts(self, *, limit: int, offset: int, file_type: str | None = None,
                       scan_status: str | None = None,
                       extraction_status: str | None = None,
                       classification_status: str | None = None,
                       search: str | None = None) -> dict:
        return self._get("/artifacts", {
            "limit": limit, "offset": offset, "file_type": file_type,
            "scan_status": scan_status, "extraction_status": extraction_status,
            "classification_status": classification_status, "search": search})

    def get_artifact(self, artifact_id: str) -> dict:
        return self._get(f"/artifacts/{_seg(artifact_id)}")

    def artifact_links(self, artifact_id: str, *, limit: int = 100,
                       offset: int = 0) -> dict:
        return self._get(f"/artifacts/{_seg(artifact_id)}/links",
                         {"limit": limit, "offset": offset})

    def artifact_evidence(self, artifact_id: str, *, limit: int = 100,
                          offset: int = 0) -> dict:
        return self._get(f"/artifacts/{_seg(artifact_id)}/evidence",
                         {"limit": limit, "offset": offset})

    def artifact_action(self, artifact_id: str, action: str) -> dict:
        if action not in ARTIFACT_ACTIONS:
            raise NavigateError(f"Unsupported artifact action: {action!r}",
                                status=400)
        return self._post(f"/artifacts/{_seg(artifact_id)}/{action}")

    # -- knowledge objects ------------------------------------------------ #
    def list_knowledge(self, *, limit: int, offset: int, object_type: str | None = None,
                       status: str | None = None, review_status: str | None = None,
                       owner: str | None = None, domain: str | None = None,
                       min_confidence: float | None = None,
                       search: str | None = None) -> dict:
        return self._get("/knowledge-objects", {
            "limit": limit, "offset": offset, "object_type": object_type,
            "status": status, "review_status": review_status, "owner": owner,
            "domain": domain, "min_confidence": min_confidence, "search": search})

    def get_knowledge(self, object_id: str) -> dict:
        return self._get(f"/knowledge-objects/{_seg(object_id)}")

    def knowledge_relationships(self, object_id: str, *, limit: int = 200,
                                offset: int = 0) -> dict:
        return self._get(f"/knowledge-objects/{_seg(object_id)}/relationships",
                         {"limit": limit, "offset": offset})

    def knowledge_evidence(self, object_id: str, *, limit: int = 200,
                           offset: int = 0) -> dict:
        return self._get(f"/knowledge-objects/{_seg(object_id)}/evidence",
                         {"limit": limit, "offset": offset})

    def knowledge_mentions(self, object_id: str, *, limit: int = 200,
                           offset: int = 0) -> dict:
        return self._get(f"/knowledge-objects/{_seg(object_id)}/mentions",
                         {"limit": limit, "offset": offset})

    def knowledge_action(self, object_id: str, action: str) -> dict:
        if action not in KNOWLEDGE_ACTIONS:
            raise NavigateError(f"Unsupported knowledge action: {action!r}",
                                status=400)
        return self._post(f"/knowledge-objects/{_seg(object_id)}/{action}")

    # -- relationships ---------------------------------------------------- #
    def list_relationships(self, *, limit: int, offset: int,
                           source_object_id: str | None = None,
                           target_object_id: str | None = None,
                           predicate: str | None = None,
                           review_status: str | None = None,
                           min_confidence: float | None = None) -> dict:
        return self._get("/relationships", {
            "limit": limit, "offset": offset,
            "source_object_id": source_object_id,
            "target_object_id": target_object_id, "predicate": predicate,
            "review_status": review_status, "min_confidence": min_confidence})

    def get_relationship(self, relationship_id: int) -> dict:
        return self._get(f"/relationships/{_seg(relationship_id)}")

    def relationship_action(self, relationship_id: int, action: str) -> dict:
        if action not in RELATIONSHIP_ACTIONS:
            raise NavigateError(f"Unsupported relationship action: {action!r}",
                                status=400)
        return self._post(f"/relationships/{_seg(relationship_id)}/{action}")

    # -- evidence --------------------------------------------------------- #
    def list_evidence(self, *, limit: int, offset: int, artifact_id: str | None = None,
                      knowledge_object_id: str | None = None,
                      relationship_id: int | None = None) -> dict:
        return self._get("/evidence", {
            "limit": limit, "offset": offset, "artifact_id": artifact_id,
            "knowledge_object_id": knowledge_object_id,
            "relationship_id": relationship_id})

    # -- graph ------------------------------------------------------------ #
    def graph_export(self) -> dict:
        return self._get("/graph/export-json")

    def graph_nodes(self, *, limit: int = 500, offset: int = 0) -> dict:
        return self._get("/graph/nodes", {"limit": limit, "offset": offset})

    def graph_neighbors(self, object_id: str) -> dict:
        return self._get(f"/graph/object/{_seg(object_id)}/neighbors")

    def graph_impact(self, object_id: str) -> dict:
        return self._get(f"/graph/object/{_seg(object_id)}/impact")

    def graph_path(self, source: str, target: str,
                   max_depth: int | None = None) -> dict:
        return self._get("/graph/path", {
            "source": source, "target": target, "max_depth": max_depth})

    # -- governance ------------------------------------------------------- #
    def gov_dashboard(self) -> dict:
        return self._get("/governance/dashboard")

    def gov_review_queue(self) -> list:
        return self._get("/governance/review-queue")

    def gov_stale(self) -> list:
        return self._get("/governance/stale")

    def gov_orphaned(self) -> dict:
        return self._get("/governance/orphaned")

    def gov_alerts(self, *, alert_type: str | None = None,
                   severity: str | None = None) -> list:
        return self._get("/governance/alerts",
                         {"alert_type": alert_type, "severity": severity})

    def gov_quality(self, *, ascending: bool = False) -> dict:
        return self._get("/governance/quality", {"ascending": ascending})

    # -- graphrag --------------------------------------------------------- #
    def ask(self, question: str, *, depth: int = 2, show_context: bool = True,
            show_evidence: bool = True) -> dict:
        return self._request(
            "POST", "/ask",
            json={"question": question, "depth": depth,
                  "show_context": show_context, "show_evidence": show_evidence},
            timeout=self.settings.navigate_ask_timeout)

    # -- jobs ------------------------------------------------------------- #
    def list_jobs(self, *, limit: int = 25, offset: int = 0,
                  job_type: str | None = None, status: str | None = None) -> dict:
        return self._get("/jobs", {
            "limit": limit, "offset": offset, "job_type": job_type,
            "status": status})

    def get_job(self, job_id: int) -> dict:
        return self._get(f"/jobs/{_seg(job_id)}")

    # -- links ------------------------------------------------------------ #
    def link_stats(self) -> dict:
        return self._get("/links/stats")

    def top_targets(self, *, limit: int = 20) -> list:
        return self._get("/links/top-targets", {"limit": limit})


def _clean(params: dict | None) -> dict | None:
    """Drop ``None`` and empty-string values from query parameters.

    The filter forms submit every field on each change, so an unselected
    dropdown or an empty search box arrives as ``key=`` (an empty string, not
    ``None``). Forwarding those to Navigate turns them into real ``?status=``
    filters that match nothing and silently break filtering. We drop them here
    while keeping meaningful falsy values such as ``0`` / ``0.0`` (e.g.
    ``min_confidence=0``).
    """
    if not params:
        return None
    return {k: v for k, v in params.items() if v is not None and v != ""}


# --------------------------------------------------------------------------- #
# FastAPI dependency
# --------------------------------------------------------------------------- #
def get_client() -> NavigateClient:
    """Dependency yielding a request-scoped Navigate client.

    Overridden in tests with a fake. A fresh client per request keeps things
    simple and thread-safe; httpx pools connections under the hood.
    """
    client = NavigateClient()
    try:
        yield client
    finally:
        client.close()
