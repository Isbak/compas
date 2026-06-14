"""Data-access layer: all catalog queries used by the API and web routes.

Functions here translate Navigate's catalog into the view-models the dashboard
needs. Everything is paginated and parameterised so the dashboard scales to
large catalogs (10k+ artifacts, 100k+ relationships).
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from . import models
from .config import get_settings

# Predicates rendered with friendlier phrasing in the UI.
PREDICATE_LABELS = {
    "supports": "supports",
    "depends_on": "depends on",
    "implemented_by": "implemented by",
    "implements": "implements",
    "owns": "owns",
    "owned_by": "owned by",
    "related_to": "related to",
    "affects": "affects",
    "mentions": "mentions",
    "references": "references",
}


# --------------------------------------------------------------------------- #
# Pagination helpers
# --------------------------------------------------------------------------- #
@dataclass
class Page:
    items: list[Any]
    total: int
    page: int
    page_size: int

    @property
    def pages(self) -> int:
        return max(1, (self.total + self.page_size - 1) // self.page_size)

    @property
    def has_prev(self) -> bool:
        return self.page > 1

    @property
    def has_next(self) -> bool:
        return self.page < self.pages

    def to_dict(self) -> dict[str, Any]:
        return {
            "items": self.items,
            "total": self.total,
            "page": self.page,
            "page_size": self.page_size,
            "pages": self.pages,
            "has_prev": self.has_prev,
            "has_next": self.has_next,
        }


def _clamp_page_size(page_size: int | None) -> int:
    s = get_settings()
    if not page_size:
        return s.page_size
    return max(1, min(page_size, s.max_page_size))


def _days_ago(iso: str | None) -> int | None:
    if not iso:
        return None
    try:
        dt = datetime.fromisoformat(iso)
    except ValueError:
        return None
    return (datetime.now() - dt).days


# --------------------------------------------------------------------------- #
# Dashboard metrics
# --------------------------------------------------------------------------- #
def dashboard_stats(session: Session) -> dict[str, Any]:
    total_artifacts = session.scalar(select(func.count()).select_from(models.Artifact)) or 0
    total_objects = session.scalar(select(func.count()).select_from(models.KnowledgeObject)) or 0
    total_rels = session.scalar(select(func.count()).select_from(models.KnowledgeRelationship)) or 0
    evidence_count = session.scalar(select(func.count()).select_from(models.KnowledgeEvidence)) or 0
    approved = session.scalar(
        select(func.count()).select_from(models.KnowledgeObject)
        .where(models.KnowledgeObject.status == "APPROVED")
    ) or 0
    pending = session.scalar(
        select(func.count()).select_from(models.KnowledgeLifecycle)
        .where(models.KnowledgeLifecycle.review_state.in_(
            ["PENDING_REVIEW", "NEEDS_ATTENTION"]))
    ) or 0
    stale = session.scalar(
        select(func.count()).select_from(models.KnowledgeLifecycle)
        .where(models.KnowledgeLifecycle.freshness_state == "STALE")
    ) or 0
    quality = session.scalar(select(func.avg(models.KnowledgeQuality.quality_score)))
    open_alerts = session.scalar(
        select(func.count()).select_from(models.KnowledgeAlert)
        .where(models.KnowledgeAlert.status == "OPEN")
    ) or 0

    return {
        "total_artifacts": total_artifacts,
        "knowledge_objects": total_objects,
        "relationships": total_rels,
        "evidence_count": evidence_count,
        "approved_objects": approved,
        "pending_reviews": pending,
        "stale_knowledge": stale,
        "quality_score": round(quality, 1) if quality is not None else 0.0,
        "open_alerts": open_alerts,
        "approved_pct": round(100 * approved / total_objects, 1) if total_objects else 0.0,
    }


def domain_overview(session: Session) -> list[dict[str, Any]]:
    """Aggregate domains from document classifications + object freshness."""
    rows = session.execute(
        select(models.DocumentClassification.domains)
    ).scalars().all()
    counter: Counter[str] = Counter()
    for raw in rows:
        for d in _split_domains(raw):
            counter[d] += 1

    # Map objects to domains via their mentions' artifacts' classifications.
    obj_domains = _object_domain_map(session)
    domain_quality: dict[str, list[float]] = defaultdict(list)
    domain_fresh: dict[str, list[float]] = defaultdict(list)
    q_by_obj = {
        q.object_id: q.quality_score
        for q in session.execute(select(models.KnowledgeQuality)).scalars()
    }
    f_by_obj = {
        lc.object_id: lc.freshness_score
        for lc in session.execute(select(models.KnowledgeLifecycle)).scalars()
    }
    obj_count: Counter[str] = Counter()
    for oid, domains in obj_domains.items():
        for d in domains:
            obj_count[d] += 1
            if q_by_obj.get(oid) is not None:
                domain_quality[d].append(q_by_obj[oid])
            if f_by_obj.get(oid) is not None:
                domain_fresh[d].append(f_by_obj[oid])

    result = []
    for domain in sorted(set(counter) | set(obj_count)):
        q = domain_quality.get(domain)
        f = domain_fresh.get(domain)
        result.append({
            "domain": domain,
            "documents": counter.get(domain, 0),
            "objects": obj_count.get(domain, 0),
            "quality": round(sum(q) / len(q), 1) if q else None,
            "freshness": round(100 * sum(f) / len(f), 0) if f else None,
        })
    result.sort(key=lambda r: r["objects"], reverse=True)
    return result


def knowledge_growth_trend(session: Session) -> list[dict[str, Any]]:
    """Cumulative knowledge-object count grouped by creation month."""
    rows = session.execute(
        select(models.KnowledgeObject.created_at)
    ).scalars().all()
    months: Counter[str] = Counter()
    for iso in rows:
        if not iso:
            continue
        try:
            dt = datetime.fromisoformat(iso)
        except ValueError:
            continue
        months[f"{dt.year}-{dt.month:02d}"] += 1
    trend, cumulative = [], 0
    for month in sorted(months):
        cumulative += months[month]
        trend.append({"period": month, "added": months[month], "total": cumulative})
    return trend


def recent_changes(session: Session, limit: int = 12) -> list[dict[str, Any]]:
    rows = session.execute(
        select(models.KnowledgeChangeLog)
        .order_by(models.KnowledgeChangeLog.detected_at.desc())
        .limit(limit)
    ).scalars().all()
    names = _object_name_map(session)
    return [{
        "id": c.id,
        "change_type": c.change_type,
        "target_kind": c.target_kind,
        "object_id": c.object_id,
        "object_name": names.get(c.object_id, c.object_id),
        "field": c.field,
        "old_value": c.old_value,
        "new_value": c.new_value,
        "detail": c.detail,
        "detected_at": c.detected_at,
    } for c in rows]


# --------------------------------------------------------------------------- #
# Artifacts
# --------------------------------------------------------------------------- #
def list_artifacts(
    session: Session, *, page: int = 1, page_size: int | None = None,
    file_type: str | None = None, status: str | None = None,
    domain: str | None = None, q: str | None = None,
) -> Page:
    page_size = _clamp_page_size(page_size)
    stmt = select(models.Artifact)
    if file_type:
        stmt = stmt.where(models.Artifact.file_type == file_type)
    if status:
        stmt = stmt.where(models.Artifact.scan_status == status)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(models.Artifact.filename.ilike(like),
                             models.Artifact.path.ilike(like)))
    if domain:
        sub = select(models.DocumentClassification.artifact_id).where(
            models.DocumentClassification.domains.ilike(f"%{domain}%"))
        stmt = stmt.where(models.Artifact.id.in_(sub))

    total = session.scalar(
        select(func.count()).select_from(stmt.subquery())) or 0
    rows = session.execute(
        stmt.order_by(models.Artifact.modified_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    ).scalars().all()

    # Counts of links + knowledge objects per artifact (batch).
    art_ids = [a.id for a in rows]
    link_counts = _counts(session, models.Link.source_artifact_id,
                          models.Link.source_artifact_id.in_(art_ids))
    ko_counts = _counts(session, models.KnowledgeMention.artifact_id,
                        models.KnowledgeMention.artifact_id.in_(art_ids))
    cls = {
        c.artifact_id: c for c in session.execute(
            select(models.DocumentClassification).where(
                models.DocumentClassification.artifact_id.in_(art_ids))
        ).scalars()
    }
    items = [{
        "id": a.id,
        "title": a.filename.rsplit(".", 1)[0],
        "filename": a.filename,
        "file_type": a.file_type,
        "path": a.path,
        "modified_at": a.modified_at,
        "status": a.scan_status,
        "source_system": a.source_system,
        "size_bytes": a.size_bytes,
        "document_type": cls[a.id].document_type if a.id in cls else None,
        "domains": _split_domains(cls[a.id].domains) if a.id in cls else [],
        "links": link_counts.get(a.id, 0),
        "knowledge_objects": ko_counts.get(a.id, 0),
    } for a in rows]
    return Page(items, total, page, page_size)


def get_artifact(session: Session, artifact_id: str) -> dict[str, Any] | None:
    art = session.execute(
        select(models.Artifact).where(models.Artifact.id == artifact_id)
    ).scalar_one_or_none()
    if art is None:
        return None
    cls = session.execute(
        select(models.DocumentClassification).where(
            models.DocumentClassification.artifact_id == artifact_id)
    ).scalar_one_or_none()
    links = session.execute(
        select(models.Link).where(models.Link.source_artifact_id == artifact_id)
    ).scalars().all()
    mentions = session.execute(
        select(models.KnowledgeMention, models.KnowledgeObject)
        .join(models.KnowledgeObject,
              models.KnowledgeObject.id == models.KnowledgeMention.knowledge_object_id)
        .where(models.KnowledgeMention.artifact_id == artifact_id)
    ).all()
    return {
        "id": art.id,
        "title": art.filename.rsplit(".", 1)[0],
        "filename": art.filename,
        "path": art.path,
        "file_type": art.file_type,
        "size_bytes": art.size_bytes,
        "created_at": art.created_at,
        "modified_at": art.modified_at,
        "status": art.scan_status,
        "source_system": art.source_system,
        "sha256": art.sha256,
        "classification": {
            "document_type": cls.document_type if cls else None,
            "type_confidence": cls.type_confidence if cls else None,
            "domains": _split_domains(cls.domains) if cls else [],
            "short_summary": cls.short_summary if cls else None,
            "long_summary": cls.long_summary if cls else None,
            "review_status": cls.review_status if cls else None,
        } if cls else None,
        "links": [{
            "id": l.id, "url": l.normalized_url, "anchor_text": l.anchor_text,
            "target_system": l.target_system, "target_type": l.target_type,
            "link_kind": l.link_kind, "status": l.status,
        } for l in links],
        "knowledge_objects": [{
            "id": ko.id, "name": ko.name, "type": ko.object_type,
            "confidence": m.confidence,
        } for m, ko in mentions],
    }


def artifact_filter_options(session: Session) -> dict[str, list[str]]:
    file_types = session.execute(
        select(models.Artifact.file_type).distinct()).scalars().all()
    statuses = session.execute(
        select(models.Artifact.scan_status).distinct()).scalars().all()
    domains = sorted({
        d for raw in session.execute(
            select(models.DocumentClassification.domains)).scalars()
        for d in _split_domains(raw)
    })
    return {
        "file_types": sorted(f for f in file_types if f),
        "statuses": sorted(s for s in statuses if s),
        "domains": domains,
    }


# --------------------------------------------------------------------------- #
# Knowledge objects
# --------------------------------------------------------------------------- #
def list_knowledge_objects(
    session: Session, *, page: int = 1, page_size: int | None = None,
    object_type: str | None = None, status: str | None = None,
    review_state: str | None = None, domain: str | None = None,
    q: str | None = None, sort: str = "quality",
) -> Page:
    page_size = _clamp_page_size(page_size)
    stmt = select(models.KnowledgeObject)
    if object_type:
        stmt = stmt.where(models.KnowledgeObject.object_type == object_type)
    if status:
        stmt = stmt.where(models.KnowledgeObject.status == status)
    if q:
        stmt = stmt.where(models.KnowledgeObject.name.ilike(f"%{q}%"))
    if review_state:
        sub = select(models.KnowledgeLifecycle.object_id).where(
            models.KnowledgeLifecycle.review_state == review_state)
        stmt = stmt.where(models.KnowledgeObject.id.in_(sub))

    obj_domains = _object_domain_map(session) if domain else {}
    if domain:
        ids = [oid for oid, ds in obj_domains.items() if domain in ds]
        stmt = stmt.where(models.KnowledgeObject.id.in_(ids or ["__none__"]))

    total = session.scalar(
        select(func.count()).select_from(stmt.subquery())) or 0
    rows = session.execute(stmt).scalars().all()

    ids = [o.id for o in rows]
    quality = {
        q.object_id: q for q in session.execute(
            select(models.KnowledgeQuality).where(
                models.KnowledgeQuality.object_id.in_(ids))).scalars()
    }
    lifecycle = {
        lc.object_id: lc for lc in session.execute(
            select(models.KnowledgeLifecycle).where(
                models.KnowledgeLifecycle.object_id.in_(ids))).scalars()
    }
    ev_counts = _counts(session, models.KnowledgeEvidence.knowledge_object_id,
                        models.KnowledgeEvidence.knowledge_object_id.in_(ids))
    rel_counts = _relationship_counts(session, ids)
    owners = _owner_map(session, ids)

    items = [{
        "id": o.id,
        "name": o.name,
        "type": o.object_type,
        "description": o.description,
        "confidence": o.confidence,
        "status": o.status,
        "evidence_count": ev_counts.get(o.id, 0),
        "relationship_count": rel_counts.get(o.id, 0),
        "owner": owners.get(o.id),
        "review_status": lifecycle[o.id].review_state if o.id in lifecycle else None,
        "freshness_state": lifecycle[o.id].freshness_state if o.id in lifecycle else None,
        "quality_score": quality[o.id].quality_score if o.id in quality else None,
    } for o in rows]

    sort_keys = {
        "quality": lambda i: (i["quality_score"] or 0),
        "evidence": lambda i: i["evidence_count"],
        "relationships": lambda i: i["relationship_count"],
        "confidence": lambda i: (i["confidence"] or 0),
        "name": lambda i: i["name"].lower(),
    }
    reverse = sort != "name"
    items.sort(key=sort_keys.get(sort, sort_keys["quality"]), reverse=reverse)

    start = (page - 1) * page_size
    return Page(items[start:start + page_size], total, page, page_size)


def get_knowledge_object(session: Session, object_id: str) -> dict[str, Any] | None:
    obj = session.get(models.KnowledgeObject, object_id)
    if obj is None:
        return None
    quality = session.get(models.KnowledgeQuality, object_id)
    lifecycle = session.get(models.KnowledgeLifecycle, object_id)
    owners = session.execute(
        select(models.KnowledgeOwner).where(
            models.KnowledgeOwner.object_id == object_id)).scalars().all()

    evidence = session.execute(
        select(models.KnowledgeEvidence, models.Artifact)
        .join(models.Artifact,
              models.Artifact.id == models.KnowledgeEvidence.artifact_id, isouter=True)
        .where(models.KnowledgeEvidence.knowledge_object_id == object_id)
        .order_by(models.KnowledgeEvidence.confidence.desc())
    ).all()

    rels = relationships_for_object(session, object_id)
    docs = session.execute(
        select(models.Artifact, models.KnowledgeMention.confidence)
        .join(models.KnowledgeMention,
              models.KnowledgeMention.artifact_id == models.Artifact.id)
        .where(models.KnowledgeMention.knowledge_object_id == object_id)
    ).all()
    history = session.execute(
        select(models.KnowledgeChangeLog)
        .where(models.KnowledgeChangeLog.object_id == object_id)
        .order_by(models.KnowledgeChangeLog.detected_at.desc())
    ).scalars().all()

    return {
        "id": obj.id,
        "name": obj.name,
        "type": obj.object_type,
        "description": obj.description,
        "confidence": obj.confidence,
        "status": obj.status,
        "merge_confidence": obj.merge_confidence,
        "created_at": obj.created_at,
        "updated_at": obj.updated_at,
        "domains": sorted(_object_domain_map(session).get(object_id, set())),
        "owners": [{"type": o.owner_type, "id": o.owner_id} for o in owners],
        "quality": _quality_dict(quality),
        "lifecycle": _lifecycle_dict(lifecycle),
        "evidence": [{
            "id": e.id, "artifact_id": e.artifact_id,
            "artifact_title": a.filename.rsplit(".", 1)[0] if a else e.artifact_id,
            "quote": e.quote, "page_number": e.page_number,
            "slide_number": e.slide_number, "confidence": e.confidence,
        } for e, a in evidence],
        "evidence_count": len(evidence),
        "relationships": rels,
        "documents": [{
            "id": a.id, "title": a.filename.rsplit(".", 1)[0],
            "file_type": a.file_type, "confidence": conf,
        } for a, conf in docs],
        "history": [{
            "change_type": h.change_type, "field": h.field,
            "old_value": h.old_value, "new_value": h.new_value,
            "detail": h.detail, "detected_at": h.detected_at,
        } for h in history],
    }


def knowledge_filter_options(session: Session) -> dict[str, list[str]]:
    types = session.execute(
        select(models.KnowledgeObject.object_type).distinct()).scalars().all()
    statuses = session.execute(
        select(models.KnowledgeObject.status).distinct()).scalars().all()
    reviews = session.execute(
        select(models.KnowledgeLifecycle.review_state).distinct()).scalars().all()
    return {
        "types": sorted(t for t in types if t),
        "statuses": sorted(s for s in statuses if s),
        "review_states": sorted(r for r in reviews if r),
        "domains": sorted({d for ds in _object_domain_map(session).values() for d in ds}),
    }


# --------------------------------------------------------------------------- #
# Relationships
# --------------------------------------------------------------------------- #
def list_relationships(
    session: Session, *, page: int = 1, page_size: int | None = None,
    predicate: str | None = None, review_status: str | None = None,
    q: str | None = None,
) -> Page:
    page_size = _clamp_page_size(page_size)
    stmt = select(models.KnowledgeRelationship)
    if predicate:
        stmt = stmt.where(models.KnowledgeRelationship.predicate == predicate)
    if review_status:
        stmt = stmt.where(models.KnowledgeRelationship.review_status == review_status)

    total = session.scalar(
        select(func.count()).select_from(stmt.subquery())) or 0
    rows = session.execute(
        stmt.order_by(models.KnowledgeRelationship.confidence.desc())
        .offset((page - 1) * page_size).limit(page_size)
    ).scalars().all()
    names = _object_name_map(session)
    types = _object_type_map(session)
    items = []
    for r in rows:
        src = names.get(r.source_object, r.source_object)
        tgt = names.get(r.target_object, r.target_object)
        if q and q.lower() not in f"{src} {r.predicate} {tgt}".lower():
            continue
        items.append({
            "id": r.id,
            "source_id": r.source_object, "source": src,
            "source_type": types.get(r.source_object),
            "predicate": r.predicate,
            "predicate_label": PREDICATE_LABELS.get(r.predicate, r.predicate),
            "target_id": r.target_object, "target": tgt,
            "target_type": types.get(r.target_object),
            "confidence": r.confidence, "evidence": r.evidence,
            "review_status": r.review_status,
        })
    return Page(items, total, page, page_size)


def relationships_for_object(session: Session, object_id: str) -> dict[str, list]:
    names = _object_name_map(session)
    types = _object_type_map(session)
    out: list = session.execute(
        select(models.KnowledgeRelationship).where(
            models.KnowledgeRelationship.source_object == object_id)).scalars().all()
    inc: list = session.execute(
        select(models.KnowledgeRelationship).where(
            models.KnowledgeRelationship.target_object == object_id)).scalars().all()
    grouped: dict[str, list] = defaultdict(list)
    for r in out:
        grouped[r.predicate].append({
            "id": r.id, "object_id": r.target_object,
            "name": names.get(r.target_object, r.target_object),
            "type": types.get(r.target_object),
            "confidence": r.confidence, "review_status": r.review_status,
            "direction": "out",
        })
    for r in inc:
        grouped[f"{r.predicate} (incoming)"].append({
            "id": r.id, "object_id": r.source_object,
            "name": names.get(r.source_object, r.source_object),
            "type": types.get(r.source_object),
            "confidence": r.confidence, "review_status": r.review_status,
            "direction": "in",
        })
    return dict(grouped)


def relationship_filter_options(session: Session) -> dict[str, list[str]]:
    preds = session.execute(
        select(models.KnowledgeRelationship.predicate).distinct()).scalars().all()
    statuses = session.execute(
        select(models.KnowledgeRelationship.review_status).distinct()).scalars().all()
    return {
        "predicates": sorted(p for p in preds if p),
        "review_statuses": sorted(s for s in statuses if s),
    }


# --------------------------------------------------------------------------- #
# Evidence
# --------------------------------------------------------------------------- #
def list_evidence(
    session: Session, *, page: int = 1, page_size: int | None = None,
    object_id: str | None = None, artifact_id: str | None = None,
) -> Page:
    page_size = _clamp_page_size(page_size)
    stmt = select(models.KnowledgeEvidence)
    if object_id:
        stmt = stmt.where(models.KnowledgeEvidence.knowledge_object_id == object_id)
    if artifact_id:
        stmt = stmt.where(models.KnowledgeEvidence.artifact_id == artifact_id)
    total = session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = session.execute(
        stmt.order_by(models.KnowledgeEvidence.confidence.desc())
        .offset((page - 1) * page_size).limit(page_size)).scalars().all()
    names = _object_name_map(session)
    items = [{
        "id": e.id, "object_id": e.knowledge_object_id,
        "object_name": names.get(e.knowledge_object_id),
        "artifact_id": e.artifact_id, "quote": e.quote,
        "page_number": e.page_number, "slide_number": e.slide_number,
        "confidence": e.confidence,
    } for e in rows]
    return Page(items, total, page, page_size)


# --------------------------------------------------------------------------- #
# Domains
# --------------------------------------------------------------------------- #
def get_domain(session: Session, domain: str) -> dict[str, Any]:
    obj_domains = _object_domain_map(session)
    object_ids = [oid for oid, ds in obj_domains.items() if domain in ds]
    objects = session.execute(
        select(models.KnowledgeObject).where(
            models.KnowledgeObject.id.in_(object_ids or ["__none__"]))
    ).scalars().all()
    quality = {
        q.object_id: q.quality_score for q in session.execute(
            select(models.KnowledgeQuality).where(
                models.KnowledgeQuality.object_id.in_(object_ids))).scalars()
    }
    lifecycle = {
        lc.object_id: lc for lc in session.execute(
            select(models.KnowledgeLifecycle).where(
                models.KnowledgeLifecycle.object_id.in_(object_ids))).scalars()
    }
    owners = _owner_map(session, object_ids)
    rel_count = session.scalar(
        select(func.count()).select_from(models.KnowledgeRelationship).where(
            or_(models.KnowledgeRelationship.source_object.in_(object_ids),
                models.KnowledgeRelationship.target_object.in_(object_ids)))) or 0
    q_vals = [quality[o.id] for o in objects if o.id in quality]
    f_vals = [lifecycle[o.id].freshness_score for o in objects
              if o.id in lifecycle and lifecycle[o.id].freshness_score is not None]
    return {
        "domain": domain,
        "object_count": len(objects),
        "relationship_count": rel_count,
        "quality": round(sum(q_vals) / len(q_vals), 1) if q_vals else None,
        "freshness": round(100 * sum(f_vals) / len(f_vals)) if f_vals else None,
        "owners": sorted({o for oid in object_ids for o in
                          ([owners[oid]] if owners.get(oid) else [])}),
        "objects": [{
            "id": o.id, "name": o.name, "type": o.object_type,
            "status": o.status,
            "quality_score": quality.get(o.id),
            "review_status": lifecycle[o.id].review_state if o.id in lifecycle else None,
        } for o in objects],
    }


# --------------------------------------------------------------------------- #
# Governance
# --------------------------------------------------------------------------- #
def governance_center(session: Session) -> dict[str, Any]:
    review_queue = list_knowledge_objects(
        session, review_state="PENDING_REVIEW", page_size=100).items
    needs_attention = list_knowledge_objects(
        session, review_state="NEEDS_ATTENTION", page_size=100).items
    pending_rels = list_relationships(
        session, review_status="PROPOSED", page_size=100).items
    alerts = list_alerts(session)
    by_type: dict[str, list] = defaultdict(list)
    for a in alerts:
        by_type[a["alert_type"]].append(a)

    stale = list_knowledge_objects(session, page_size=500)
    stale_objs = [i for i in stale.items if i["freshness_state"] == "STALE"]
    return {
        "review_queue": review_queue,
        "approval_queue": needs_attention,
        "pending_relationships": pending_rels,
        "alerts": alerts,
        "alerts_by_type": dict(by_type),
        "stale_objects": stale_objs,
        "quality_alerts": by_type.get("QUALITY_DROP", []) + by_type.get("DRIFT", []),
        "drift_alerts": by_type.get("DRIFT", []),
        "orphaned": by_type.get("ORPHANED", []),
        "duplicate_candidates": by_type.get("DUPLICATE_CANDIDATE", []),
    }


def list_alerts(session: Session, status: str = "OPEN") -> list[dict[str, Any]]:
    stmt = select(models.KnowledgeAlert)
    if status:
        stmt = stmt.where(models.KnowledgeAlert.status == status)
    rows = session.execute(
        stmt.order_by(models.KnowledgeAlert.created_at.desc())).scalars().all()
    names = _object_name_map(session)
    return [{
        "id": a.id, "alert_type": a.alert_type, "severity": a.severity,
        "object_id": a.object_id, "object_name": names.get(a.object_id),
        "message": a.message, "status": a.status, "created_at": a.created_at,
    } for a in rows]


def knowledge_health(session: Session) -> dict[str, Any]:
    objects = session.execute(select(models.KnowledgeObject)).scalars().all()
    total = len(objects) or 1
    quality = session.execute(select(models.KnowledgeQuality)).scalars().all()
    lifecycle = {lc.object_id: lc for lc in
                 session.execute(select(models.KnowledgeLifecycle)).scalars()}

    avg_quality = (sum(q.quality_score or 0 for q in quality) / len(quality)
                   if quality else 0)
    fresh = sum(1 for lc in lifecycle.values() if lc.freshness_state == "FRESH")
    reviewed = sum(1 for o in objects if o.status in ("APPROVED", "REVIEWED"))
    with_evidence = sum(1 for q in quality if (q.evidence_count or 0) > 0)
    rel_obj_ids = set(session.execute(
        select(models.KnowledgeRelationship.source_object)).scalars()) | set(
        session.execute(
            select(models.KnowledgeRelationship.target_object)).scalars())
    with_rels = sum(1 for o in objects if o.id in rel_obj_ids)

    return {
        "quality_score": round(avg_quality, 1),
        "freshness": round(100 * fresh / total, 1),
        "review_coverage": round(100 * reviewed / total, 1),
        "evidence_coverage": round(100 * with_evidence / total, 1),
        "relationship_coverage": round(100 * with_rels / total, 1),
        "domain_health": domain_overview(session),
    }


# --------------------------------------------------------------------------- #
# Governance write actions
# --------------------------------------------------------------------------- #
def review_object(session: Session, object_id: str, action: str,
                  reviewer: str = "compas", note: str | None = None) -> bool:
    obj = session.get(models.KnowledgeObject, object_id)
    if obj is None:
        return False
    status_map = {"APPROVE": "APPROVED", "REJECT": "REJECTED",
                  "ARCHIVE": "ARCHIVED"}
    new_status = status_map.get(action.upper())
    if not new_status:
        return False
    old_status = obj.status
    obj.status = new_status
    obj.updated_at = datetime.now().isoformat(timespec="seconds")
    lc = session.get(models.KnowledgeLifecycle, object_id)
    if lc:
        lc.review_state = {"APPROVED": "APPROVED", "REJECTED": "REJECTED",
                           "ARCHIVED": "ARCHIVED"}[new_status]
        lc.last_reviewed_at = obj.updated_at
    session.add(models.KnowledgeReview(
        target_kind="object", target_id=object_id, action=action.upper(),
        confidence=obj.confidence, note=note, reviewer=reviewer,
        created_at=obj.updated_at))
    session.add(models.KnowledgeChangeLog(
        change_type=action.upper(), target_kind="object", object_id=object_id,
        field="status", old_value=old_status, new_value=new_status,
        detected_at=obj.updated_at))
    session.commit()
    return True


def review_relationship(session: Session, rel_id: int, action: str,
                        reviewer: str = "compas", note: str | None = None) -> bool:
    rel = session.get(models.KnowledgeRelationship, rel_id)
    if rel is None:
        return False
    status_map = {"APPROVE": "APPROVED", "REJECT": "REJECTED"}
    new_status = status_map.get(action.upper())
    if not new_status:
        return False
    old = rel.review_status
    rel.review_status = new_status
    rel.updated_at = datetime.now().isoformat(timespec="seconds")
    session.add(models.KnowledgeReview(
        target_kind="relationship", target_id=str(rel_id),
        action=action.upper(), confidence=rel.confidence, note=note,
        reviewer=reviewer, created_at=rel.updated_at))
    session.add(models.KnowledgeChangeLog(
        change_type=action.upper(), target_kind="relationship",
        object_id=rel.source_object, field="review_status", old_value=old,
        new_value=new_status, detected_at=rel.updated_at))
    session.commit()
    return True


def resolve_alert(session: Session, alert_id: int) -> bool:
    alert = session.get(models.KnowledgeAlert, alert_id)
    if alert is None:
        return False
    alert.status = "RESOLVED"
    alert.resolved_at = datetime.now().isoformat(timespec="seconds")
    session.commit()
    return True


# --------------------------------------------------------------------------- #
# Notifications (derived from alerts + change log)
# --------------------------------------------------------------------------- #
def notifications(session: Session, limit: int = 15) -> list[dict[str, Any]]:
    alerts = list_alerts(session)[:limit]
    items = [{
        "kind": a["alert_type"], "severity": a["severity"],
        "message": a["message"], "object_id": a["object_id"],
        "object_name": a["object_name"], "created_at": a["created_at"],
    } for a in alerts]
    items.sort(key=lambda i: i["created_at"] or "", reverse=True)
    return items[:limit]


# --------------------------------------------------------------------------- #
# Observability
# --------------------------------------------------------------------------- #
def observability(session: Session) -> dict[str, Any]:
    def _rows(model, order_col):
        return session.execute(
            select(model).order_by(order_col.desc()).limit(10)).scalars().all()

    scans = _rows(models.ScanRun, models.ScanRun.started_at)
    link_scans = _rows(models.LinkScanRun, models.LinkScanRun.started_at)
    cls_runs = _rows(models.ClassificationRun, models.ClassificationRun.started_at)
    return {
        "scan_jobs": [{
            "id": s.id, "started_at": s.started_at, "finished_at": s.finished_at,
            "files_scanned": s.files_scanned, "new": s.new_files,
            "changed": s.changed_files, "deleted": s.deleted_files,
            "duplicate": s.duplicate_files,
        } for s in scans],
        "link_jobs": [{
            "id": s.id, "started_at": s.started_at, "completed_at": s.completed_at,
            "links_found": s.links_found, "new": s.links_new,
            "updated": s.links_updated, "removed": s.links_removed,
            "errors": s.errors,
        } for s in link_scans],
        "classification_jobs": [{
            "id": s.id, "started_at": s.started_at, "completed_at": s.completed_at,
            "model": s.model, "processed": s.documents_processed,
            "skipped": s.documents_skipped, "errors": s.errors,
        } for s in cls_runs],
        "totals": {
            "scan_errors": 0,
            "link_errors": sum(s.errors or 0 for s in link_scans),
            "classification_errors": sum(s.errors or 0 for s in cls_runs),
        },
    }


# --------------------------------------------------------------------------- #
# Search (fuzzy)
# --------------------------------------------------------------------------- #
def search(session: Session, query: str, limit: int = 30) -> dict[str, list]:
    if not query or not query.strip():
        return {"knowledge_objects": [], "artifacts": [], "relationships": [],
                "domains": [], "total": 0}
    q = query.strip().lower()

    objects = session.execute(select(models.KnowledgeObject)).scalars().all()
    ko_hits = []
    for o in objects:
        score = _fuzzy(q, o.name.lower())
        if o.description and q in o.description.lower():
            score = max(score, 0.6)
        if score >= 0.45:
            ko_hits.append((score, {
                "id": o.id, "name": o.name, "type": o.object_type,
                "status": o.status, "score": round(score, 2)}))
    ko_hits.sort(key=lambda x: x[0], reverse=True)

    arts = session.execute(
        select(models.Artifact).where(
            models.Artifact.filename.ilike(f"%{query}%")).limit(limit)).scalars().all()
    art_hits = [{
        "id": a.id, "title": a.filename.rsplit(".", 1)[0],
        "file_type": a.file_type, "path": a.path} for a in arts]

    names = _object_name_map(session)
    rels = session.execute(select(models.KnowledgeRelationship)).scalars().all()
    rel_hits = []
    for r in rels:
        text = f"{names.get(r.source_object,'')} {r.predicate} {names.get(r.target_object,'')}".lower()
        if q in text:
            rel_hits.append({
                "id": r.id, "source": names.get(r.source_object),
                "predicate": r.predicate, "target": names.get(r.target_object),
                "review_status": r.review_status})

    domains = [d for d in {d for ds in _object_domain_map(session).values()
                           for d in ds} if q in d.lower()]

    return {
        "knowledge_objects": [h for _, h in ko_hits[:limit]],
        "artifacts": art_hits[:limit],
        "relationships": rel_hits[:limit],
        "domains": [{"domain": d} for d in domains],
        "total": len(ko_hits) + len(art_hits) + len(rel_hits) + len(domains),
    }


# --------------------------------------------------------------------------- #
# Graph
# --------------------------------------------------------------------------- #
def graph_payload(
    session: Session, *, mode: str = "all", focus: str | None = None,
    depth: int = 1, min_confidence: float = 0.0, limit: int | None = None,
) -> dict[str, Any]:
    """Build a Cytoscape-style node/edge payload.

    ``mode`` selects a view (capability, technology, decision, team, domain,
    all). ``focus`` + ``depth`` restrict to a neighbourhood for incremental
    loading.
    """
    settings = get_settings()
    limit = limit or settings.graph_node_limit

    type_filter = {
        "capability": {"Capability"},
        "technology": {"Technology", "Platform"},
        "decision": {"Decision"},
        "team": {"Team"},
        "process": {"Process"},
    }.get(mode)

    all_rels = session.execute(
        select(models.KnowledgeRelationship).where(
            models.KnowledgeRelationship.confidence >= min_confidence)).scalars().all()
    objects = {o.id: o for o in
               session.execute(select(models.KnowledgeObject)).scalars()}

    if focus:
        keep = _neighbourhood(focus, all_rels, depth)
    else:
        keep = set(objects)

    node_ids: set[str] = set()
    edges = []
    for r in all_rels:
        if r.source_object not in keep or r.target_object not in keep:
            continue
        s_obj, t_obj = objects.get(r.source_object), objects.get(r.target_object)
        if not s_obj or not t_obj:
            continue
        if type_filter and (s_obj.object_type not in type_filter
                            and t_obj.object_type not in type_filter):
            continue
        node_ids.add(r.source_object)
        node_ids.add(r.target_object)
        edges.append({
            "data": {
                "id": f"e{r.id}", "source": r.source_object,
                "target": r.target_object, "label": r.predicate,
                "confidence": r.confidence, "review_status": r.review_status,
            }
        })

    if not focus and not edges:  # isolated nodes for empty graph
        node_ids = set(list(objects)[:limit])

    if len(node_ids) > limit:
        node_ids = set(list(node_ids)[:limit])
        edges = [e for e in edges if e["data"]["source"] in node_ids
                 and e["data"]["target"] in node_ids]

    ev_counts = _counts(session, models.KnowledgeEvidence.knowledge_object_id,
                        models.KnowledgeEvidence.knowledge_object_id.in_(list(node_ids)))
    nodes = []
    for oid in node_ids:
        o = objects[oid]
        nodes.append({"data": {
            "id": o.id, "label": o.name, "type": o.object_type,
            "status": o.status, "confidence": o.confidence,
            "evidence_count": ev_counts.get(o.id, 0),
            "focus": oid == focus,
        }})
    return {"nodes": nodes, "edges": edges, "mode": mode,
            "node_count": len(nodes), "edge_count": len(edges),
            "truncated": len(node_ids) >= limit}


def shortest_path(session: Session, source_id: str, target_id: str) -> dict[str, Any]:
    """BFS shortest path between two knowledge objects (undirected)."""
    rels = session.execute(select(models.KnowledgeRelationship)).scalars().all()
    adj: dict[str, list[tuple[str, models.KnowledgeRelationship]]] = defaultdict(list)
    for r in rels:
        adj[r.source_object].append((r.target_object, r))
        adj[r.target_object].append((r.source_object, r))

    from collections import deque
    queue = deque([[source_id]])
    seen = {source_id}
    names = _object_name_map(session)
    types = _object_type_map(session)
    while queue:
        path = queue.popleft()
        node = path[-1]
        if node == target_id:
            steps = []
            for a, b in zip(path, path[1:]):
                rel = next((r for n, r in adj[a] if n == b), None)
                steps.append({
                    "source": a, "source_name": names.get(a, a),
                    "target": b, "target_name": names.get(b, b),
                    "predicate": rel.predicate if rel else "related_to",
                    "confidence": rel.confidence if rel else None,
                })
            return {
                "found": True, "length": len(path) - 1,
                "nodes": [{"id": n, "name": names.get(n, n),
                           "type": types.get(n)} for n in path],
                "steps": steps,
            }
        for nxt, _ in adj[node]:
            if nxt not in seen:
                seen.add(nxt)
                queue.append(path + [nxt])
    return {"found": False, "length": None, "nodes": [], "steps": []}


def list_object_names(session: Session) -> list[dict[str, str]]:
    rows = session.execute(
        select(models.KnowledgeObject.id, models.KnowledgeObject.name,
               models.KnowledgeObject.object_type)
        .order_by(models.KnowledgeObject.name)).all()
    return [{"id": i, "name": n, "type": t} for i, n, t in rows]


# --------------------------------------------------------------------------- #
# Internal helpers
# --------------------------------------------------------------------------- #
def _split_domains(raw: str | None) -> list[str]:
    if not raw:
        return []
    raw = raw.strip()
    if raw.startswith("["):
        import json
        try:
            return [str(x) for x in json.loads(raw)]
        except (ValueError, TypeError):
            pass
    return [d.strip() for d in raw.split(",") if d.strip()]


def _counts(session: Session, column, where_clause) -> dict[str, int]:
    rows = session.execute(
        select(column, func.count()).where(where_clause).group_by(column)).all()
    return {k: v for k, v in rows}


def _relationship_counts(session: Session, ids: list[str]) -> dict[str, int]:
    out = _counts(session, models.KnowledgeRelationship.source_object,
                  models.KnowledgeRelationship.source_object.in_(ids))
    inc = _counts(session, models.KnowledgeRelationship.target_object,
                  models.KnowledgeRelationship.target_object.in_(ids))
    result: Counter[str] = Counter()
    result.update(out)
    result.update(inc)
    return dict(result)


def _owner_map(session: Session, ids: list[str]) -> dict[str, str]:
    rows = session.execute(
        select(models.KnowledgeOwner.object_id, models.KnowledgeOwner.owner_id)
        .where(models.KnowledgeOwner.object_id.in_(ids))).all()
    return {oid: owner for oid, owner in rows}


def _object_name_map(session: Session) -> dict[str, str]:
    return dict(session.execute(
        select(models.KnowledgeObject.id, models.KnowledgeObject.name)).all())


def _object_type_map(session: Session) -> dict[str, str]:
    return dict(session.execute(
        select(models.KnowledgeObject.id, models.KnowledgeObject.object_type)).all())


def _object_domain_map(session: Session) -> dict[str, set[str]]:
    """Map each knowledge object to the domains of documents that mention it."""
    cls_domains = dict(session.execute(
        select(models.DocumentClassification.artifact_id,
               models.DocumentClassification.domains)).all())
    mentions = session.execute(
        select(models.KnowledgeMention.knowledge_object_id,
               models.KnowledgeMention.artifact_id)).all()
    out: dict[str, set[str]] = defaultdict(set)
    for oid, aid in mentions:
        for d in _split_domains(cls_domains.get(aid)):
            out[oid].add(d)
    return out


def _neighbourhood(focus: str, rels: list, depth: int) -> set[str]:
    adj: dict[str, set[str]] = defaultdict(set)
    for r in rels:
        adj[r.source_object].add(r.target_object)
        adj[r.target_object].add(r.source_object)
    frontier = {focus}
    seen = {focus}
    for _ in range(max(0, depth)):
        nxt: set[str] = set()
        for n in frontier:
            nxt |= adj[n] - seen
        seen |= nxt
        frontier = nxt
    return seen


def _quality_dict(q: models.KnowledgeQuality | None) -> dict[str, Any] | None:
    if q is None:
        return None
    return {
        "quality_score": q.quality_score, "evidence_score": q.evidence_score,
        "review_score": q.review_score, "freshness_score": q.freshness_score,
        "consistency_score": q.consistency_score, "owner_score": q.owner_score,
        "confidence_score": q.confidence_score, "evidence_count": q.evidence_count,
        "document_count": q.document_count,
    }


def _lifecycle_dict(lc: models.KnowledgeLifecycle | None) -> dict[str, Any] | None:
    if lc is None:
        return None
    return {
        "freshness_state": lc.freshness_state, "freshness_score": lc.freshness_score,
        "review_state": lc.review_state, "last_reviewed_at": lc.last_reviewed_at,
        "last_seen_at": lc.last_seen_at,
        "days_since_review": _days_ago(lc.last_reviewed_at),
    }


def _fuzzy(needle: str, haystack: str) -> float:
    """Cheap fuzzy score combining substring + trigram Dice coefficient."""
    if not needle or not haystack:
        return 0.0
    if needle in haystack:
        return 0.9 if haystack.startswith(needle) else 0.75

    def trigrams(s: str) -> set[str]:
        s = f"  {s} "
        return {s[i:i + 3] for i in range(len(s) - 2)}

    a, b = trigrams(needle), trigrams(haystack)
    if not a or not b:
        return 0.0
    return 2 * len(a & b) / (len(a) + len(b))
