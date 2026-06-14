"""Apache Jena Fuseki (SPARQL) client.

Optional and disabled by default — Compas is local-first. When a Fuseki
endpoint is configured and enabled, raw SPARQL can be executed against
Navigate's RDF projection. The status helper reports reachability without
throwing so the Settings/Observability pages can render gracefully offline.
"""

from __future__ import annotations

from typing import Any

import httpx

from .config import get_settings


def status() -> dict[str, Any]:
    settings = get_settings()
    if not settings.fuseki_enabled:
        return {"enabled": False, "reachable": False,
                "endpoint": settings.fuseki_endpoint,
                "message": "Fuseki integration is disabled (local-first)."}
    try:
        resp = httpx.get(settings.fuseki_endpoint.rstrip("/") + "/$/ping",
                         timeout=settings.fuseki_timeout)
        reachable = resp.status_code < 500
    except Exception as exc:  # noqa: BLE001
        return {"enabled": True, "reachable": False,
                "endpoint": settings.fuseki_endpoint, "message": str(exc)}
    return {"enabled": True, "reachable": reachable,
            "endpoint": settings.fuseki_endpoint,
            "message": "Connected" if reachable else "Unreachable"}


def query(sparql: str) -> dict[str, Any]:
    """Execute a SPARQL SELECT and return the JSON results bindings."""
    settings = get_settings()
    if not settings.fuseki_enabled:
        return {"enabled": False, "results": [],
                "message": "Fuseki is disabled; enable COMPAS_FUSEKI_ENABLED."}
    resp = httpx.post(
        settings.fuseki_endpoint.rstrip("/") + "/sparql",
        data={"query": sparql},
        headers={"Accept": "application/sparql-results+json"},
        timeout=settings.fuseki_timeout,
    )
    resp.raise_for_status()
    payload = resp.json()
    bindings = payload.get("results", {}).get("bindings", [])
    rows = [{k: v.get("value") for k, v in row.items()} for row in bindings]
    return {"enabled": True, "results": rows,
            "vars": payload.get("head", {}).get("vars", [])}
