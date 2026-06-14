"""Application configuration.

Settings are loaded from environment variables (prefixed ``COMPAS_``) and an
optional ``.env`` file. Compas is *local-first*: by default it never reaches
out to the network. The Fuseki and GraphRAG integrations are only contacted
when their endpoints are explicitly configured and enabled.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Repository root (…/compas)
ROOT_DIR = Path(__file__).resolve().parent.parent
PACKAGE_DIR = Path(__file__).resolve().parent


class Settings(BaseSettings):
    """Runtime configuration for the Compas dashboard."""

    model_config = SettingsConfigDict(
        env_prefix="COMPAS_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Core ---------------------------------------------------------------
    app_name: str = "Compas"
    debug: bool = False

    #: Path to Navigate's SQLite catalog (the system of record). When this file
    #: does not exist and ``demo_mode`` is enabled, Compas will create a small
    #: synthetic catalog so the dashboard is usable out of the box.
    database_path: Path = Field(default=ROOT_DIR / "data" / "catalog.sqlite")

    #: Open the Navigate catalog read-write so governance actions (approve /
    #: reject / archive) can be persisted. Navigate remains the system of
    #: record; Compas only writes review + lifecycle rows.
    read_only: bool = False

    #: When the catalog is missing, seed a demo catalog instead of failing.
    demo_mode: bool = True

    # --- Pagination / performance ------------------------------------------
    page_size: int = 50
    max_page_size: int = 500
    #: Maximum number of nodes returned in a single graph payload.
    graph_node_limit: int = 250

    # --- Fuseki (SPARQL) ----------------------------------------------------
    fuseki_enabled: bool = False
    fuseki_endpoint: str = "http://localhost:3030/navigate"
    fuseki_timeout: float = 15.0

    # --- GraphRAG assistant -------------------------------------------------
    #: When disabled, the GraphRAG panel answers from the local graph using a
    #: deterministic, fully local retriever (no external calls).
    graphrag_enabled: bool = False
    #: Optional HTTP endpoint exposing Navigate's GraphRAG assistant.
    graphrag_endpoint: str = ""
    graphrag_timeout: float = 60.0

    # --- LLM provider settings (surfaced in Settings page) ------------------
    llm_provider: str = "ollama"  # ollama | openai | claude
    ollama_endpoint: str = "http://localhost:11434"
    ollama_model: str = "llama3.1"
    openai_model: str = "gpt-4o-mini"

    # --- Governance ---------------------------------------------------------
    review_interval_days: int = 90
    stale_after_days: int = 180

    @property
    def static_dir(self) -> Path:
        return PACKAGE_DIR / "static"

    @property
    def templates_dir(self) -> Path:
        return PACKAGE_DIR / "templates"


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
