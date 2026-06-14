"""Application configuration.

Compas is a *pure client* of the Navigate REST API — it builds no API or
database of its own. It talks only to a running Navigate API
(`catalog api`). Settings come from environment variables (prefixed
``COMPAS_``) and an optional ``.env`` file.

Compas remains local-first: the API key (if any) stays server-side, and the
browser only ever talks to Compas, which proxies to Navigate.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

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

    # --- Navigate API (the only backend) -----------------------------------
    #: Base URL of Navigate's REST API, including the ``/api`` prefix.
    navigate_api_url: str = "http://127.0.0.1:8000/api"
    #: Optional bearer token; sent as ``Authorization: Bearer <key>``.
    navigate_api_key: str = ""
    #: Request timeout (seconds) for calls to Navigate.
    navigate_timeout: float = 30.0
    #: Longer timeout for the GraphRAG ``/ask`` endpoint.
    navigate_ask_timeout: float = 120.0

    # --- Pagination / performance ------------------------------------------
    page_size: int = 50          # maps to Navigate's ``limit``
    max_page_size: int = 500     # Navigate's hard cap
    graph_node_limit: int = 250

    # --- GraphRAG defaults --------------------------------------------------
    ask_depth: int = 2

    @property
    def static_dir(self) -> Path:
        return PACKAGE_DIR / "static"

    @property
    def templates_dir(self) -> Path:
        return PACKAGE_DIR / "templates"


@lru_cache
def get_settings() -> Settings:
    return Settings()
