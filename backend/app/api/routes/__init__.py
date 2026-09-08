"""Route aggregation.

A tuple rather than a pre-composed router, so ``create_app`` decides how each
router is mounted and a reviewer can see the full list in one place. Note that
this FastAPI version resolves ``include_router`` lazily: ``app.routes`` holds
internal placeholder objects until the schema is built, so inspect
``app.openapi()["paths"]`` rather than ``app.routes`` when checking what is
mounted.
"""

from fastapi import APIRouter

from app.api.routes import (
    actions,
    auth,
    grow,
    keep,
    meta,
    opportunities,
    personal,
    profile,
)

ROUTERS: tuple[APIRouter, ...] = (
    meta.router,
    auth.router,
    profile.router,
    opportunities.router,
    actions.router,
    keep.router,
    grow.router,
    personal.router,
)

__all__ = ["ROUTERS"]
