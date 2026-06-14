"""REST API for Compas.

Exposes the endpoints listed in the specification under ``/api``:
artifacts, knowledge, relationships, evidence, domains, governance,
graphrag, search, graph — plus health, notifications and observability.
"""

from fastapi import APIRouter

from . import governance, graph, graphrag, knowledge, misc, relationships
from .artifacts import router as artifacts_router

api_router = APIRouter(prefix="/api")
api_router.include_router(artifacts_router)
api_router.include_router(knowledge.router)
api_router.include_router(relationships.router)
api_router.include_router(graph.router)
api_router.include_router(governance.router)
api_router.include_router(graphrag.router)
api_router.include_router(misc.router)

__all__ = ["api_router"]
