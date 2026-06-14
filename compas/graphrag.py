"""GraphRAG assistant.

Local-first: by default Compas answers questions deterministically from the
local knowledge graph (no network calls), returning the answer alongside the
evidence, confidence, knowledge objects used and the SPARQL queries that would
retrieve the same facts. When ``COMPAS_GRAPHRAG_ENABLED`` is set and an
endpoint is configured, the question is delegated to Navigate's GraphRAG
assistant over HTTP instead.
"""

from __future__ import annotations

import re
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models, repository
from .config import get_settings


def ask(session: Session, question: str) -> dict[str, Any]:
    settings = get_settings()
    if settings.graphrag_enabled and settings.graphrag_endpoint:
        try:
            return _ask_remote(settings.graphrag_endpoint, question,
                               settings.graphrag_timeout)
        except Exception as exc:  # noqa: BLE001 - fall back to local
            local = _ask_local(session, question)
            local["note"] = f"Remote GraphRAG unavailable ({exc}); answered locally."
            return local
    return _ask_local(session, question)


def _ask_remote(endpoint: str, question: str, timeout: float) -> dict[str, Any]:
    resp = httpx.post(endpoint.rstrip("/") + "/ask",
                      json={"question": question}, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()
    data.setdefault("source", "navigate-graphrag")
    return data


def _ask_local(session: Session, question: str) -> dict[str, Any]:
    """Graph-first retrieval with strict grounding (no hallucination).

    The retriever finds the knowledge objects named in the question, then
    walks their relationships to assemble a grounded answer. If nothing is
    found it says so rather than inventing facts.
    """
    q = (question or "").strip()
    if not q:
        return _empty("Please ask a question about the knowledge graph.")

    names = repository.list_object_names(session)
    matched = _match_objects(q, names)
    intent = _detect_intent(q)

    if not matched:
        return _empty(
            "I couldn't find a knowledge object matching that question. Try "
            "naming a capability, team, technology, decision or risk that "
            "exists in the catalog.")

    focus = matched[0]
    detail = repository.get_knowledge_object(session, focus["id"])
    if detail is None:
        return _empty("That object is no longer present in the catalog.")

    # Filter relationships by intent (supports / depends / affects / etc.)
    relations = _collect_relations(detail, intent)
    used_ids = [focus["id"]] + [r["object_id"] for r in relations]
    used = _objects_summary(session, used_ids)

    evidence = detail["evidence"][:5]
    confidence = _aggregate_confidence(detail, relations)
    answer = _compose_answer(detail, relations, intent)
    sparql = _sparql_for(focus["name"], intent)

    return {
        "question": q,
        "answer": answer,
        "confidence": round(confidence, 2),
        "evidence": [{
            "object": detail["name"], "artifact_id": e["artifact_id"],
            "artifact_title": e["artifact_title"], "quote": e["quote"],
            "page_number": e["page_number"], "confidence": e["confidence"],
        } for e in evidence],
        "knowledge_objects_used": used,
        "sparql_queries": sparql,
        "focus_id": focus["id"],
        "source": "compas-local",
    }


# --------------------------------------------------------------------------- #
# Intent + matching
# --------------------------------------------------------------------------- #
_INTENT_PREDICATES = {
    "supports": ["supports"],
    "depends": ["depends_on"],
    "affects": ["affects"],
    "risk": ["affects"],
    "owns": ["owns", "owned_by", "implemented_by"],
    "implements": ["implements", "implemented_by"],
    "related": ["related_to"],
}


def _detect_intent(q: str) -> str | None:
    ql = q.lower()
    if "support" in ql:
        return "supports"
    if "depend" in ql or "rely" in ql:
        return "depends"
    if "risk" in ql or "affect" in ql or "threat" in ql:
        return "affects"
    if "own" in ql or "responsible" in ql or "team" in ql:
        return "owns"
    if "implement" in ql:
        return "implements"
    if "relate" in ql or "connect" in ql:
        return "related"
    return None


def _match_objects(q: str, names: list[dict[str, str]]) -> list[dict[str, str]]:
    ql = q.lower()
    scored = []
    for n in names:
        name = n["name"].lower()
        if name in ql:
            scored.append((len(name), n))
        else:
            score = repository._fuzzy(name, ql)
            if score >= 0.6:
                scored.append((score, n))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [n for _, n in scored]


def _collect_relations(detail: dict, intent: str | None) -> list[dict]:
    preds = _INTENT_PREDICATES.get(intent) if intent else None
    out = []
    for predicate, items in detail["relationships"].items():
        base = predicate.replace(" (incoming)", "")
        if preds and base not in preds:
            continue
        for item in items:
            out.append({**item, "predicate": base})
    out.sort(key=lambda r: r.get("confidence") or 0, reverse=True)
    return out


def _compose_answer(detail: dict, relations: list[dict], intent: str | None) -> str:
    name = detail["name"]
    if not relations:
        return (f"**{name}** ({detail['type']}) is in the catalog with "
                f"{detail['evidence_count']} pieces of evidence, but I found no "
                "relationships matching your question.")
    verb = {
        "supports": "is supported by / supports", "depends": "depends on",
        "affects": "is affected by / affects", "owns": "is owned / implemented by",
        "implements": "implements", "related": "is related to",
    }.get(intent, "is connected to")
    parts = [f"**{name}** {verb}:"]
    for r in relations[:8]:
        conf = f" ({int((r['confidence'] or 0) * 100)}%)" if r.get("confidence") else ""
        parts.append(f"- {r['predicate'].replace('_', ' ')} → **{r['name']}** "
                     f"({r['type']}){conf}")
    parts.append(f"\nGrounded in {detail['evidence_count']} evidence quotes "
                 f"across {len(detail['documents'])} documents.")
    return "\n".join(parts)


def _aggregate_confidence(detail: dict, relations: list[dict]) -> float:
    vals = [detail.get("confidence") or 0]
    vals += [r.get("confidence") or 0 for r in relations[:5]]
    vals = [v for v in vals if v]
    return sum(vals) / len(vals) if vals else 0.0


def _objects_summary(session: Session, ids: list[str]) -> list[dict]:
    seen, out = set(), []
    objs = {o.id: o for o in session.execute(
        select(models.KnowledgeObject).where(
            models.KnowledgeObject.id.in_(ids))).scalars()}
    for oid in ids:
        if oid in seen or oid not in objs:
            continue
        seen.add(oid)
        o = objs[oid]
        out.append({"id": o.id, "name": o.name, "type": o.object_type,
                    "confidence": o.confidence})
    return out


def _sparql_for(name: str, intent: str | None) -> list[dict[str, str]]:
    safe = re.sub(r'["\\]', "", name)
    preds = _INTENT_PREDICATES.get(intent, ["?p"]) if intent else ["?p"]
    pred = preds[0] if preds and preds[0] != "?p" else "?p"
    pred_term = f"nav:{pred}" if pred != "?p" else "?p"
    query = (
        "PREFIX nav: <https://navigate.isbak.dev/ontology#>\n"
        "SELECT ?target ?targetName ?confidence WHERE {\n"
        f'  ?s nav:name "{safe}" .\n'
        f"  ?s {pred_term} ?target .\n"
        "  ?target nav:name ?targetName .\n"
        "  OPTIONAL {{ ?s nav:confidence ?confidence }}\n"
        "}\nORDER BY DESC(?confidence)"
    )
    return [{"label": f"Neighbours of {name}", "query": query}]


def _empty(message: str) -> dict[str, Any]:
    return {
        "answer": message, "confidence": 0.0, "evidence": [],
        "knowledge_objects_used": [], "sparql_queries": [],
        "source": "compas-local",
    }
