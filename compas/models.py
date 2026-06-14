"""SQLAlchemy ORM models mirroring Navigate's SQLite catalog schema.

These map 1:1 onto the tables created by ``navigate``'s ``src/catalog/db.py``
so Compas can read (and, for governance, lightly write to) the same catalog
that Navigate maintains. Column names and types intentionally match Navigate;
timestamps are stored as ISO-8601 TEXT, exactly as Navigate writes them.

See https://github.com/isbak/navigate for the source schema.
"""

from __future__ import annotations

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


# --------------------------------------------------------------------------- #
# Core: artifacts, links, scan runs
# --------------------------------------------------------------------------- #
class Artifact(Base):
    __tablename__ = "artifacts"

    path: Mapped[str] = mapped_column(Text, primary_key=True)
    id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    filename: Mapped[str] = mapped_column(Text, nullable=False)
    file_type: Mapped[str] = mapped_column(Text, nullable=False)
    size_bytes: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[str | None] = mapped_column(Text)
    modified_at: Mapped[str | None] = mapped_column(Text)
    sha256: Mapped[str | None] = mapped_column(Text)
    source_system: Mapped[str | None] = mapped_column(Text, default="local_laptop")
    scan_status: Mapped[str | None] = mapped_column(Text, default="RAW")
    first_seen_at: Mapped[str | None] = mapped_column(Text)
    last_scanned_at: Mapped[str | None] = mapped_column(Text)


class Link(Base):
    __tablename__ = "links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_artifact_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    raw_url: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_url: Mapped[str] = mapped_column(Text, nullable=False)
    anchor_text: Mapped[str | None] = mapped_column(Text)
    target_system: Mapped[str | None] = mapped_column(Text)
    target_type: Mapped[str | None] = mapped_column(Text)
    link_kind: Mapped[str | None] = mapped_column(Text)
    discovered_at: Mapped[str | None] = mapped_column(Text)
    last_seen_at: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str | None] = mapped_column(Text, default="ACTIVE")


class ScanRun(Base):
    __tablename__ = "scan_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    started_at: Mapped[str | None] = mapped_column(Text)
    finished_at: Mapped[str | None] = mapped_column(Text)
    files_scanned: Mapped[int] = mapped_column(Integer, default=0)
    new_files: Mapped[int] = mapped_column(Integer, default=0)
    changed_files: Mapped[int] = mapped_column(Integer, default=0)
    unchanged_files: Mapped[int] = mapped_column(Integer, default=0)
    duplicate_files: Mapped[int] = mapped_column(Integer, default=0)
    deleted_files: Mapped[int] = mapped_column(Integer, default=0)


class LinkScanRun(Base):
    __tablename__ = "link_scan_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    started_at: Mapped[str | None] = mapped_column(Text)
    completed_at: Mapped[str | None] = mapped_column(Text)
    artifacts_processed: Mapped[int | None] = mapped_column(Integer)
    links_found: Mapped[int | None] = mapped_column(Integer)
    links_new: Mapped[int | None] = mapped_column(Integer)
    links_updated: Mapped[int | None] = mapped_column(Integer)
    links_removed: Mapped[int | None] = mapped_column(Integer)
    errors: Mapped[int | None] = mapped_column(Integer)


# --------------------------------------------------------------------------- #
# Semantic classification
# --------------------------------------------------------------------------- #
class DocumentClassification(Base):
    __tablename__ = "document_classifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    artifact_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    document_type: Mapped[str | None] = mapped_column(Text)
    type_confidence: Mapped[float | None] = mapped_column(Float)
    domains: Mapped[str | None] = mapped_column(Text)  # JSON / comma list
    short_summary: Mapped[str | None] = mapped_column(Text)
    long_summary: Mapped[str | None] = mapped_column(Text)
    knowledge_type: Mapped[str | None] = mapped_column(Text, default="OBSERVATION")
    review_status: Mapped[str | None] = mapped_column(Text, default="NEW")
    model: Mapped[str | None] = mapped_column(Text)
    source_hash: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str | None] = mapped_column(Text)


class ClassificationRun(Base):
    __tablename__ = "classification_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    started_at: Mapped[str | None] = mapped_column(Text)
    completed_at: Mapped[str | None] = mapped_column(Text)
    model: Mapped[str | None] = mapped_column(Text)
    documents_processed: Mapped[int | None] = mapped_column(Integer)
    documents_skipped: Mapped[int | None] = mapped_column(Integer)
    errors: Mapped[int | None] = mapped_column(Integer)


# --------------------------------------------------------------------------- #
# Knowledge consolidation
# --------------------------------------------------------------------------- #
class KnowledgeObject(Base):
    __tablename__ = "knowledge_objects"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    object_type: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    canonical_name: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str | None] = mapped_column(Text, default="PROPOSED")
    merge_confidence: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[str | None] = mapped_column(Text)

    evidence: Mapped[list["KnowledgeEvidence"]] = relationship(
        back_populates="object", cascade="all, delete-orphan"
    )
    mentions: Mapped[list["KnowledgeMention"]] = relationship(
        back_populates="object", cascade="all, delete-orphan"
    )
    lifecycle: Mapped["KnowledgeLifecycle | None"] = relationship(
        back_populates="object", uselist=False
    )
    quality: Mapped["KnowledgeQuality | None"] = relationship(
        back_populates="object", uselist=False
    )


class KnowledgeMention(Base):
    __tablename__ = "knowledge_mentions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    knowledge_object_id: Mapped[str] = mapped_column(
        ForeignKey("knowledge_objects.id", ondelete="CASCADE"), index=True
    )
    artifact_id: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float)
    source_text: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str | None] = mapped_column(Text)

    object: Mapped[KnowledgeObject] = relationship(back_populates="mentions")


class KnowledgeEvidence(Base):
    __tablename__ = "knowledge_evidence"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    knowledge_object_id: Mapped[str] = mapped_column(
        ForeignKey("knowledge_objects.id", ondelete="CASCADE"), index=True
    )
    artifact_id: Mapped[str] = mapped_column(Text, nullable=False)
    quote: Mapped[str | None] = mapped_column(Text)
    page_number: Mapped[int | None] = mapped_column(Integer)
    slide_number: Mapped[int | None] = mapped_column(Integer)
    confidence: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[str | None] = mapped_column(Text)

    object: Mapped[KnowledgeObject] = relationship(back_populates="evidence")


class KnowledgeRelationship(Base):
    __tablename__ = "knowledge_relationships"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_object: Mapped[str] = mapped_column(
        ForeignKey("knowledge_objects.id", ondelete="CASCADE"), index=True
    )
    predicate: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    target_object: Mapped[str] = mapped_column(
        ForeignKey("knowledge_objects.id", ondelete="CASCADE"), index=True
    )
    confidence: Mapped[float | None] = mapped_column(Float)
    evidence: Mapped[str | None] = mapped_column(Text)
    review_status: Mapped[str | None] = mapped_column(Text, default="PROPOSED")
    created_at: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[str | None] = mapped_column(Text)


class KnowledgeReview(Base):
    __tablename__ = "knowledge_reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    target_kind: Mapped[str] = mapped_column(Text, nullable=False)  # object|relationship
    target_id: Mapped[str] = mapped_column(Text, nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False)  # APPROVE|REJECT|ARCHIVE
    confidence: Mapped[float | None] = mapped_column(Float)
    note: Mapped[str | None] = mapped_column(Text)
    reviewer: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str | None] = mapped_column(Text)


# --------------------------------------------------------------------------- #
# Governance
# --------------------------------------------------------------------------- #
class KnowledgeOwner(Base):
    __tablename__ = "knowledge_owners"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    object_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    owner_type: Mapped[str] = mapped_column(Text, nullable=False)
    owner_id: Mapped[str] = mapped_column(Text, nullable=False)
    assigned_at: Mapped[str | None] = mapped_column(Text)
    assigned_by: Mapped[str | None] = mapped_column(Text)


class KnowledgeLifecycle(Base):
    __tablename__ = "knowledge_lifecycle"

    object_id: Mapped[str] = mapped_column(
        ForeignKey("knowledge_objects.id", ondelete="CASCADE"), primary_key=True
    )
    name: Mapped[str | None] = mapped_column(Text)
    object_type: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str | None] = mapped_column(Text)
    last_seen_at: Mapped[str | None] = mapped_column(Text)
    last_reviewed_at: Mapped[str | None] = mapped_column(Text)
    last_confirmed_at: Mapped[str | None] = mapped_column(Text)
    last_confidence: Mapped[float | None] = mapped_column(Float)
    freshness_score: Mapped[float | None] = mapped_column(Float)
    freshness_state: Mapped[str | None] = mapped_column(Text, default="FRESH")
    review_state: Mapped[str | None] = mapped_column(Text, default="PENDING_REVIEW")
    present: Mapped[int | None] = mapped_column(Integer, default=1)
    updated_at: Mapped[str | None] = mapped_column(Text)

    object: Mapped[KnowledgeObject] = relationship(back_populates="lifecycle")


class KnowledgeQuality(Base):
    __tablename__ = "knowledge_quality"

    object_id: Mapped[str] = mapped_column(
        ForeignKey("knowledge_objects.id", ondelete="CASCADE"), primary_key=True
    )
    quality_score: Mapped[float | None] = mapped_column(Float)
    evidence_score: Mapped[float | None] = mapped_column(Float)
    review_score: Mapped[float | None] = mapped_column(Float)
    freshness_score: Mapped[float | None] = mapped_column(Float)
    consistency_score: Mapped[float | None] = mapped_column(Float)
    owner_score: Mapped[float | None] = mapped_column(Float)
    confidence_score: Mapped[float | None] = mapped_column(Float)
    evidence_count: Mapped[int | None] = mapped_column(Integer)
    document_count: Mapped[int | None] = mapped_column(Integer)
    computed_at: Mapped[str | None] = mapped_column(Text)

    object: Mapped[KnowledgeObject] = relationship(back_populates="quality")


class KnowledgeAlert(Base):
    __tablename__ = "knowledge_alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    alert_type: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    severity: Mapped[str | None] = mapped_column(Text, default="INFO")
    object_id: Mapped[str | None] = mapped_column(Text)
    message: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str | None] = mapped_column(Text, default="OPEN")
    created_at: Mapped[str | None] = mapped_column(Text)
    resolved_at: Mapped[str | None] = mapped_column(Text)


class KnowledgeChangeLog(Base):
    __tablename__ = "knowledge_change_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    change_type: Mapped[str] = mapped_column(Text, nullable=False)
    target_kind: Mapped[str | None] = mapped_column(Text)
    object_id: Mapped[str | None] = mapped_column(Text)
    field: Mapped[str | None] = mapped_column(Text)
    old_value: Mapped[str | None] = mapped_column(Text)
    new_value: Mapped[str | None] = mapped_column(Text)
    detail: Mapped[str | None] = mapped_column(Text)
    detected_at: Mapped[str | None] = mapped_column(Text)
