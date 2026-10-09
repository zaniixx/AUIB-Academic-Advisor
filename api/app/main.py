"""FastAPI application factory."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import __version__
from app.api.routes import admin, admin_catalog, catalog, health, planner
from app.db import make_engine, make_session_factory
from app.security import (
    ADMIN_PREFIX,
    BodySizeLimitMiddleware,
    RateLimitMiddleware,
    RequestLogMiddleware,
    SecurityHeadersMiddleware,
    configure_logging,
)
from app.services.catalog_cache import CatalogCache
from app.settings import Settings, get_settings

log = logging.getLogger("app")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)
    engine = make_engine(settings.database_url)
    session_factory = make_session_factory(engine)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        yield
        engine.dispose()

    app = FastAPI(
        title="AUIB Academic Advisor API",
        version=__version__,
        description="Degree planning for AUIB students. Planning endpoints are stateless and store nothing.",
        docs_url="/api/docs" if settings.api_docs else None,
        redoc_url=None,
        openapi_url="/api/openapi.json" if settings.api_docs else None,
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = session_factory
    app.state.catalog_cache = CatalogCache()

    for router in (health.router, catalog.router, planner.router, admin.router, admin_catalog.router):
        app.include_router(router)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_request: Request, error: RequestValidationError) -> JSONResponse:
        # Echo where the input was wrong, never the submitted values themselves.
        details = [{"loc": e["loc"], "msg": e["msg"], "type": e["type"]} for e in error.errors()]
        return JSONResponse({"detail": details}, status_code=422)

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, error: Exception) -> JSONResponse:
        request_id = request.scope.get("state", {}).get("request_id", "")
        log.error(
            "unhandled error", exc_info=error, extra={"request_id": request_id, "path": request.url.path}
        )
        return JSONResponse(
            {"detail": f"Something went wrong on our side. Reference: {request_id}"}, status_code=500
        )

    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_methods=["GET", "POST", "PUT", "DELETE"],
            allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
        )
    app.add_middleware(RateLimitMiddleware, per_minute=settings.rate_limit_per_minute)
    app.add_middleware(
        BodySizeLimitMiddleware,
        max_bytes=settings.max_request_bytes,
        larger={ADMIN_PREFIX: settings.max_admin_request_bytes},
    )
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestLogMiddleware)
    return app
