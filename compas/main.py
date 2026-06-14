"""Compas application factory and ASGI entrypoint.

Run locally with::

    uvicorn compas.main:app --reload

Compas is a local-first *client* of the Navigate REST API. It binds to
localhost and talks only to the configured Navigate API
(``COMPAS_NAVIGATE_API_URL``); the browser never calls Navigate directly, so
the API key stays server-side.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from . import __version__
from .config import get_settings
from .web import web_router
from .web.templating import templates


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Compas — Navigate Knowledge Observatory",
        version=__version__,
        description="Local-first web dashboard and pure client for the "
                    "Navigate REST API (https://github.com/isbak/navigate).",
        docs_url=None, redoc_url=None, openapi_url=None,  # Compas exposes no API
    )

    app.mount("/static", StaticFiles(directory=str(settings.static_dir)),
              name="static")
    app.include_router(web_router)

    @app.get("/healthz", include_in_schema=False)
    def healthz():
        return {"status": "ok", "version": __version__, "app": settings.app_name}

    @app.exception_handler(404)
    async def not_found(request: Request, exc):  # noqa: ANN001
        return templates.TemplateResponse(
            request, "pages/not_found.html",
            {"request": request, "settings": settings, "what": "Page",
             "app_name": settings.app_name, "nav": None},
            status_code=404)

    return app


app = create_app()
