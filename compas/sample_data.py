"""Seed a synthetic Navigate catalog for demos, tests and first-run usage.

The data deliberately mirrors the worked example in the Compas specification
(Release Governance → Launchpad Model → Test & Release Team) and exercises
every object type, governance state and alert kind so the dashboard has
something meaningful to display before a real Navigate scan has run.
"""

from __future__ import annotations

import hashlib
import random
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from . import models

_NOW = datetime(2026, 6, 1, 12, 0, 0)


def _iso(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


def _oid(name: str) -> str:
    return "ko-" + hashlib.sha1(name.encode()).hexdigest()[:12]


# (name, type, description, confidence, status, domains)
_OBJECTS: list[tuple[str, str, str, float, str, list[str]]] = [
    ("Release Governance", "Process",
     "The governance framework controlling how releases are approved, "
     "scheduled and audited across the platform.", 0.94, "APPROVED",
     ["Test & Release", "Digital Transformation"]),
    ("Launchpad Model", "Capability",
     "Operating model that standardises product launches across teams.",
     0.88, "APPROVED", ["Digital Transformation", "Leadership"]),
    ("Release Management", "Capability",
     "End-to-end capability for planning, coordinating and delivering "
     "software releases.", 0.91, "APPROVED", ["Test & Release"]),
    ("Test & Release Team", "Team",
     "Cross-functional team owning test automation and the release pipeline.",
     0.9, "APPROVED", ["Test & Release"]),
    ("Salesforce", "Technology",
     "CRM platform underpinning customer-facing capabilities.", 0.86,
     "APPROVED", ["Architecture", "Digital Transformation"]),
    ("Customer 360", "Capability",
     "Unified customer view aggregating data across systems.", 0.79,
     "REVIEWED", ["Digital Transformation"]),
    ("Data Platform", "Platform",
     "Central platform for ingestion, storage and analytics.", 0.83,
     "APPROVED", ["Architecture"]),
    ("Cloud Migration", "Initiative",
     "Programme migrating on-prem workloads to the cloud.", 0.81,
     "REVIEWED", ["Architecture", "Leadership"]),
    ("Vendor Lock-in", "Risk",
     "Strategic risk of excessive dependence on a single vendor.", 0.62,
     "PROPOSED", ["Leadership", "Architecture"]),
    ("Adopt CI/CD pipeline", "Decision",
     "Decision to standardise on a shared CI/CD pipeline for all teams.",
     0.77, "REVIEWED", ["Test & Release"]),
    ("Identity Platform", "Platform",
     "Centralised authentication and authorisation services.", 0.7,
     "PROPOSED", ["Architecture"]),
    ("Knowledge Catalog", "Concept",
     "The organisation's structured, indexed memory of artifacts and "
     "relationships.", 0.88, "APPROVED", ["Digital Transformation"]),
    ("Architecture Board", "Team",
     "Governance body reviewing significant architectural decisions.", 0.84,
     "APPROVED", ["Architecture", "Leadership"]),
    ("Legacy CRM", "Technology",
     "Deprecated CRM scheduled for decommissioning.", 0.55, "PROPOSED",
     ["Architecture"]),
    ("Data Privacy Compliance", "Process",
     "Process ensuring handling of personal data meets regulation.", 0.8,
     "REVIEWED", ["Leadership"]),
]

# (source, predicate, target, confidence, review_status)
_RELATIONSHIPS: list[tuple[str, str, str, float, str]] = [
    ("Release Governance", "supports", "Launchpad Model", 0.9, "APPROVED"),
    ("Release Governance", "related_to", "Release Management", 0.88, "APPROVED"),
    ("Release Governance", "implemented_by", "Test & Release Team", 0.86, "APPROVED"),
    ("Release Management", "depends_on", "Adopt CI/CD pipeline", 0.78, "APPROVED"),
    ("Test & Release Team", "owns", "Release Management", 0.82, "APPROVED"),
    ("Launchpad Model", "supports", "Customer 360", 0.7, "PROPOSED"),
    ("Customer 360", "depends_on", "Salesforce", 0.81, "APPROVED"),
    ("Customer 360", "depends_on", "Data Platform", 0.76, "PROPOSED"),
    ("Cloud Migration", "affects", "Data Platform", 0.74, "PROPOSED"),
    ("Cloud Migration", "affects", "Salesforce", 0.68, "PROPOSED"),
    ("Vendor Lock-in", "affects", "Salesforce", 0.6, "PROPOSED"),
    ("Salesforce", "related_to", "Identity Platform", 0.64, "PROPOSED"),
    ("Architecture Board", "owns", "Cloud Migration", 0.79, "APPROVED"),
    ("Data Platform", "depends_on", "Identity Platform", 0.66, "PROPOSED"),
    ("Knowledge Catalog", "supports", "Release Governance", 0.72, "REVIEWED"),
    ("Legacy CRM", "related_to", "Salesforce", 0.5, "PROPOSED"),
    ("Data Privacy Compliance", "affects", "Customer 360", 0.71, "REVIEWED"),
    ("Architecture Board", "supports", "Data Privacy Compliance", 0.69, "PROPOSED"),
]

_DOC_TYPES = ["Governance", "Strategy", "Architecture", "Roadmap", "Project",
              "Meeting Notes", "Presentation", "Report", "Technical Design"]
_FILE_TYPES = ["docx", "pptx", "xlsx", "pdf", "md"]
_DOMAINS_POOL = ["Digital Transformation", "Leadership", "Test & Release",
                 "Architecture"]


def seed_demo_catalog(session: Session, *, seed: int = 7) -> None:
    """Populate ``session`` with a coherent synthetic catalog."""
    rng = random.Random(seed)

    # --- Scan runs ------------------------------------------------------
    for i in range(5):
        start = _NOW - timedelta(days=20 - i * 4, hours=2)
        session.add(models.ScanRun(
            started_at=_iso(start), finished_at=_iso(start + timedelta(minutes=8)),
            files_scanned=120 + i * 6, new_files=rng.randint(2, 12),
            changed_files=rng.randint(1, 8), unchanged_files=100 + i,
            duplicate_files=rng.randint(0, 3), deleted_files=rng.randint(0, 2)))
    for i in range(3):
        start = _NOW - timedelta(days=12 - i * 4)
        session.add(models.LinkScanRun(
            started_at=_iso(start), completed_at=_iso(start + timedelta(minutes=3)),
            artifacts_processed=80 + i * 5, links_found=rng.randint(40, 90),
            links_new=rng.randint(3, 15), links_updated=rng.randint(1, 9),
            links_removed=rng.randint(0, 4), errors=rng.randint(0, 1)))
    for i in range(3):
        start = _NOW - timedelta(days=10 - i * 3)
        session.add(models.ClassificationRun(
            started_at=_iso(start), completed_at=_iso(start + timedelta(minutes=15)),
            model="llama3.1", documents_processed=rng.randint(20, 60),
            documents_skipped=rng.randint(0, 8), errors=rng.randint(0, 2)))

    # --- Artifacts + classifications + links ----------------------------
    artifacts: list[models.Artifact] = []
    for i in range(40):
        ftype = rng.choice(_FILE_TYPES)
        modified = _NOW - timedelta(days=rng.randint(0, 240), hours=rng.randint(0, 23))
        created = modified - timedelta(days=rng.randint(0, 120))
        aid = f"artifact-{i:03d}"
        title = _ARTIFACT_TITLES[i % len(_ARTIFACT_TITLES)] + (f" v{i//len(_ARTIFACT_TITLES)+1}" if i >= len(_ARTIFACT_TITLES) else "")
        path = f"/sources/{rng.choice(_DOMAINS_POOL).replace(' & ', '_').replace(' ', '_').lower()}/{title.replace(' ', '_')}.{ftype}"
        status = rng.choices(["RAW", "UNCHANGED", "CHANGED", "DUPLICATE"],
                             weights=[1, 6, 2, 1])[0]
        art = models.Artifact(
            path=path, id=aid, filename=f"{title}.{ftype}", file_type=ftype,
            size_bytes=rng.randint(20_000, 8_000_000),
            created_at=_iso(created), modified_at=_iso(modified),
            sha256=hashlib.sha256(path.encode()).hexdigest(),
            source_system=rng.choice(["local_laptop", "sharepoint", "onedrive"]),
            scan_status=status, first_seen_at=_iso(created),
            last_scanned_at=_iso(_NOW - timedelta(days=rng.randint(0, 5))))
        artifacts.append(art)
        session.add(art)

        domains = rng.sample(_DOMAINS_POOL, k=rng.randint(1, 2))
        session.add(models.DocumentClassification(
            artifact_id=aid, document_type=rng.choice(_DOC_TYPES),
            type_confidence=round(rng.uniform(0.55, 0.98), 2),
            domains=",".join(domains),
            short_summary=f"{title}: summary of key points.",
            long_summary=f"{title} discusses governance, capabilities and "
                         "delivery considerations across the organisation.",
            knowledge_type=rng.choice(["OBSERVATION", "HYPOTHESIS"]),
            review_status=rng.choice(["NEW", "REVIEWED", "APPROVED"]),
            model="llama3.1", source_hash=art.sha256[:16],
            created_at=_iso(modified)))

        for _ in range(rng.randint(0, 4)):
            tsys = rng.choice(["sharepoint", "confluence", "jira", "github",
                               "external_web", "teams"])
            session.add(models.Link(
                source_artifact_id=aid,
                raw_url=f"https://{tsys}.example.com/{rng.randint(1000,9999)}",
                normalized_url=f"https://{tsys}.example.com/{rng.randint(1000,9999)}",
                anchor_text=rng.choice(["see also", "reference", "details", None]),
                target_system=tsys, target_type=rng.choice(
                    ["document", "wiki_page", "work_item", "repository"]),
                link_kind=rng.choice(["internal", "external"]),
                discovered_at=_iso(modified), last_seen_at=_iso(_NOW),
                status="ACTIVE"))

    artifact_ids = [a.id for a in artifacts]

    # --- Knowledge objects ----------------------------------------------
    name_to_id: dict[str, str] = {}
    for idx, (name, otype, desc, conf, status, domains) in enumerate(_OBJECTS):
        oid = _oid(name)
        name_to_id[name] = oid
        created = _NOW - timedelta(days=rng.randint(30, 200))
        updated = _NOW - timedelta(days=rng.randint(0, 60))
        session.add(models.KnowledgeObject(
            id=oid, name=name, object_type=otype, description=desc,
            canonical_name=name.lower(), confidence=conf, status=status,
            merge_confidence=round(rng.uniform(0.6, 0.95), 2),
            created_at=_iso(created), updated_at=_iso(updated)))

        # Evidence (every object has at least one — Navigate's invariant)
        n_ev = {"Release Governance": 17}.get(name, rng.randint(2, 9))
        for e in range(n_ev):
            aid = rng.choice(artifact_ids)
            session.add(models.KnowledgeEvidence(
                knowledge_object_id=oid, artifact_id=aid,
                quote=f"…{name} is a key element of how the organisation "
                      "operates and delivers value…",
                page_number=rng.randint(1, 30) if rng.random() > 0.5 else None,
                slide_number=rng.randint(1, 20) if rng.random() > 0.7 else None,
                confidence=round(rng.uniform(0.6, 0.97), 2),
                created_at=_iso(updated)))
        # Mentions
        for aid in rng.sample(artifact_ids, k=min(len(artifact_ids), rng.randint(2, 6))):
            session.add(models.KnowledgeMention(
                knowledge_object_id=oid, artifact_id=aid,
                confidence=round(rng.uniform(0.5, 0.95), 2),
                source_text=f"Reference to {name}.",
                created_at=_iso(updated)))

        # Owner
        if rng.random() > 0.3:
            session.add(models.KnowledgeOwner(
                object_id=oid, owner_type="team",
                owner_id=rng.choice(["Test & Release Team", "Architecture Board",
                                     "Leadership", "Platform Team"]),
                assigned_at=_iso(created), assigned_by="kristoffer"))

        # Lifecycle
        days_since_review = rng.randint(0, 260)
        last_reviewed = _NOW - timedelta(days=days_since_review)
        if days_since_review > 180:
            fresh_state, fresh_score = "STALE", round(rng.uniform(0.1, 0.4), 2)
        elif days_since_review > 90:
            fresh_state, fresh_score = "AGING", round(rng.uniform(0.4, 0.7), 2)
        else:
            fresh_state, fresh_score = "FRESH", round(rng.uniform(0.7, 1.0), 2)
        review_state = {"APPROVED": "APPROVED", "REVIEWED": "APPROVED",
                        "PROPOSED": "PENDING_REVIEW"}[status]
        if fresh_state == "STALE" and review_state == "APPROVED":
            review_state = "NEEDS_ATTENTION"
        session.add(models.KnowledgeLifecycle(
            object_id=oid, name=name, object_type=otype,
            created_at=_iso(created), last_seen_at=_iso(_NOW),
            last_reviewed_at=_iso(last_reviewed),
            last_confirmed_at=_iso(last_reviewed), last_confidence=conf,
            freshness_score=fresh_score, freshness_state=fresh_state,
            review_state=review_state, present=1, updated_at=_iso(updated)))

        # Quality
        ev_score = min(1.0, n_ev / 12)
        qscore = round(100 * (0.3 * ev_score + 0.2 * conf + 0.2 * fresh_score
                              + 0.3 * (1 if status == "APPROVED" else 0.5)), 1)
        session.add(models.KnowledgeQuality(
            object_id=oid, quality_score=qscore,
            evidence_score=round(ev_score, 2),
            review_score=1.0 if status == "APPROVED" else 0.5,
            freshness_score=fresh_score,
            consistency_score=round(rng.uniform(0.6, 1.0), 2),
            owner_score=round(rng.uniform(0.5, 1.0), 2),
            confidence_score=conf, evidence_count=n_ev,
            document_count=rng.randint(2, 12), computed_at=_iso(_NOW)))

    # --- Relationships --------------------------------------------------
    for src, pred, tgt, conf, rstatus in _RELATIONSHIPS:
        if src not in name_to_id or tgt not in name_to_id:
            continue
        created = _NOW - timedelta(days=rng.randint(5, 120))
        session.add(models.KnowledgeRelationship(
            source_object=name_to_id[src], predicate=pred,
            target_object=name_to_id[tgt], confidence=conf,
            evidence=f"Both {src} and {tgt} appear together across "
                     f"{rng.randint(2, 9)} documents.",
            review_status=rstatus, created_at=_iso(created),
            updated_at=_iso(created)))

    # --- Alerts ---------------------------------------------------------
    alerts = [
        ("STALE_OBJECT", "WARNING", "Legacy CRM",
         "Knowledge object 'Legacy CRM' has not been reviewed in over 180 days."),
        ("QUALITY_DROP", "WARNING", "Vendor Lock-in",
         "Quality score for 'Vendor Lock-in' decreased below threshold."),
        ("ORPHANED", "INFO", "Identity Platform",
         "'Identity Platform' has no approved relationships."),
        ("DUPLICATE_CANDIDATE", "INFO", "Legacy CRM",
         "'Legacy CRM' may be a duplicate of 'Salesforce'."),
        ("NEW_CAPABILITY", "INFO", "Customer 360",
         "New capability 'Customer 360' discovered and awaiting review."),
        ("DRIFT", "CRITICAL", "Cloud Migration",
         "Evidence for 'Cloud Migration' diverges from approved description."),
        ("NEW_EVIDENCE", "INFO", "Release Governance",
         "3 new evidence quotes found for 'Release Governance'."),
    ]
    for i, (atype, sev, oname, msg) in enumerate(alerts):
        session.add(models.KnowledgeAlert(
            alert_type=atype, severity=sev,
            object_id=name_to_id.get(oname), message=msg, status="OPEN",
            created_at=_iso(_NOW - timedelta(days=i, hours=i * 2))))

    # --- Change log -----------------------------------------------------
    changes = [
        ("CREATED", "object", "Customer 360", None, None, "Object created"),
        ("CONFIDENCE_CHANGED", "object", "Vendor Lock-in", "confidence",
         "0.71", "0.62"),
        ("RELATIONSHIP_ADDED", "relationship", "Release Governance", None,
         None, "supports → Launchpad Model"),
        ("APPROVED", "object", "Release Governance", "status", "REVIEWED",
         "APPROVED"),
        ("EVIDENCE_ADDED", "object", "Release Governance", "evidence_count",
         "14", "17"),
        ("STATUS_CHANGED", "object", "Cloud Migration", "status", "PROPOSED",
         "REVIEWED"),
    ]
    for i, (ctype, tkind, oname, field, old, new) in enumerate(changes):
        session.add(models.KnowledgeChangeLog(
            change_type=ctype, target_kind=tkind,
            object_id=name_to_id.get(oname), field=field, old_value=old,
            new_value=new, detail=new if field is None else None,
            detected_at=_iso(_NOW - timedelta(days=i, hours=i))))

    session.commit()


_ARTIFACT_TITLES = [
    "Release Governance Framework", "Launchpad Operating Model",
    "Q3 Release Plan", "Architecture Decision Record - CI/CD",
    "Cloud Migration Strategy", "Customer 360 Vision",
    "Data Platform Design", "Salesforce Integration Guide",
    "Test Automation Roadmap", "Leadership Offsite Notes",
    "Vendor Risk Assessment", "Identity Platform Proposal",
    "Knowledge Catalog Overview", "Architecture Board Charter",
    "Data Privacy Policy", "Release Retrospective",
    "Platform Capabilities Map", "Digital Transformation Strategy",
    "Quarterly Business Review", "Incident Postmortem",
]
