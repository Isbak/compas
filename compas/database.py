"""Database engine and session management for the Navigate catalog.

Compas connects to Navigate's SQLite catalog. The catalog is the system of
record, so Compas opens it read-only by default and only escalates to
read-write when ``COMPAS_READ_ONLY=false`` so governance actions can be
persisted. A FastAPI dependency yields short-lived sessions.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from .config import Settings, get_settings
from .models import Base

_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def _build_url(path: Path, read_only: bool) -> str:
    # Use SQLite URI mode so we can request immutable / read-only access and
    # avoid creating the file when it should not exist.
    path = Path(path)
    if read_only:
        return f"sqlite:///file:{path}?mode=ro&uri=true"
    return f"sqlite:///{path}"


def init_engine(settings: Settings | None = None, *, force: bool = False) -> Engine:
    """Create (once) and return the global SQLAlchemy engine.

    When the catalog file is missing and ``demo_mode`` is on, a synthetic demo
    catalog is seeded so the dashboard is immediately usable.
    """
    global _engine, _SessionLocal
    if _engine is not None and not force:
        return _engine

    settings = settings or get_settings()
    db_path = Path(settings.database_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    needs_seed = not db_path.exists()
    if needs_seed and settings.demo_mode:
        # Create an empty file first; seed after engine/tables are ready.
        db_path.touch()

    read_only = settings.read_only and db_path.exists() and not needs_seed
    _engine = create_engine(
        _build_url(db_path, read_only),
        connect_args={"check_same_thread": False},
        future=True,
    )

    @event.listens_for(_engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, _record):  # pragma: no cover - trivial
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.execute("PRAGMA journal_mode=WAL")
        cur.close()

    # Ensure the full schema exists (no-op against a real Navigate catalog).
    if not read_only:
        Base.metadata.create_all(_engine)

    _SessionLocal = sessionmaker(
        bind=_engine, autoflush=False, expire_on_commit=False, class_=Session
    )

    if needs_seed and settings.demo_mode:
        from .sample_data import seed_demo_catalog

        with _SessionLocal() as session:
            seed_demo_catalog(session)

    return _engine


def get_sessionmaker() -> sessionmaker[Session]:
    if _SessionLocal is None:
        init_engine()
    assert _SessionLocal is not None
    return _SessionLocal


def get_session() -> Iterator[Session]:
    """FastAPI dependency yielding a database session."""
    factory = get_sessionmaker()
    session = factory()
    try:
        yield session
    finally:
        session.close()


def reset_engine() -> None:
    """Dispose of the engine (used by tests)."""
    global _engine, _SessionLocal
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionLocal = None
