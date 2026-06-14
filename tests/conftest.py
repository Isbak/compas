"""Shared pytest fixtures.

Each test run gets a fresh, demo-seeded catalog in a temporary directory so
tests are isolated from any real Navigate database and from each other.
"""

from __future__ import annotations

import importlib
import os
from pathlib import Path

import pytest


@pytest.fixture()
def app_env(tmp_path: Path, monkeypatch):
    """Configure Compas to use a throwaway demo catalog and reset globals."""
    db_path = tmp_path / "catalog.sqlite"
    monkeypatch.setenv("COMPAS_DATABASE_PATH", str(db_path))
    monkeypatch.setenv("COMPAS_DEMO_MODE", "true")
    monkeypatch.setenv("COMPAS_READ_ONLY", "false")

    from compas import config, database

    config.get_settings.cache_clear()
    # Rebuild the templating module so it picks up the fresh settings/dirs.
    database.reset_engine()
    database.init_engine(force=True)

    yield {"db_path": db_path, "settings": config.get_settings()}

    database.reset_engine()
    config.get_settings.cache_clear()


@pytest.fixture()
def session(app_env):
    from compas.database import get_sessionmaker

    s = get_sessionmaker()()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture()
def client(app_env):
    from fastapi.testclient import TestClient

    from compas.main import create_app

    app = create_app()
    with TestClient(app) as c:
        yield c
