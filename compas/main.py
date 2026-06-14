"""Compas application factory and ASGI entrypoint.

Run locally with::

    uvicorn compas.main:app --reload

Compas is local-first: it binds to localhost and makes no outbound network
calls unless Fuseki or a remote GraphRAG endpoint are explicitly enabled.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import __version__
from .api import api_router
from .config import get_settings
from .database import init_engine
from .web import web_router
from .web.templating import templates


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_engine()  # connect to Navigate's catalog (seed demo if missing)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Compas — Navigate Knowledge Observatory",
        version=__version__,
        description="Local-first web dashboard for the Navigate knowledge "
                    "platform (https://github.com/isbak/navigate).",
        lifespan=lifespan,
    )

    app.mount("/static", StaticFiles(directory=str(settings.static_dir)),
              name="static")
    app.include_router(api_router)
    app.include_router(web_router)

    @app.get("/healthz", include_in_schema=False)
    def healthz():
        return {"status": "ok", "version": __version__,
                "app": settings.app_name}

    @app.exception_handler(404)
    async def not_found(request: Request, exc):  # noqa: ANN001
        if request.url.path.startswith("/api"):
            return JSONResponse({"detail": "Not found"}, status_code=404)
        return templates.TemplateResponse(
            request, "pages/not_found.html",
            {"request": request, "settings": settings, "what": "Page",
             "app_name": settings.app_name, "nav": None},
            status_code=404)

    return app


app = create_app()
