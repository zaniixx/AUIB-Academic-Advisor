"""Shared request dependencies."""

from __future__ import annotations

import hmac
from collections.abc import Iterator
from datetime import date
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.db import session_scope
from app.domain.catalog import Catalog, Program
from app.settings import Settings

_bearer = HTTPBearer(auto_error=False, description="Admin token (ADVISOR_ADMIN_TOKEN)")


def get_settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def get_session(request: Request) -> Iterator[Session]:
    yield from session_scope(request.app.state.session_factory)


def get_catalog(request: Request, session: Annotated[Session, Depends(get_session)]) -> Catalog:
    catalog: Catalog = request.app.state.catalog_cache.get(session)
    return catalog


def get_today(request: Request) -> date:
    """Today's date; tests replace it so plans are reproducible."""
    override = getattr(request.app.state, "today", None)
    return override() if callable(override) else date.today()


def published_program(catalog: Catalog, program_id: str) -> Program:
    program = catalog.programs.get(program_id)
    if program is None or not program.available:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Program {program_id!r} is not available")
    return program


def require_admin(
    settings: Annotated[Settings, Depends(get_settings)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> str:
    """Admin endpoints need ``Authorization: Bearer <ADVISOR_ADMIN_TOKEN>``; returns the actor name."""
    expected = settings.admin_token.get_secret_value() if settings.admin_token else ""
    if not expected:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "The admin API is not enabled on this server"
        )
    supplied = credentials.credentials if credentials else ""
    if not hmac.compare_digest(supplied.encode(), expected.encode()):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "A valid admin token is required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return "admin"


SessionDep = Annotated[Session, Depends(get_session)]
CatalogDep = Annotated[Catalog, Depends(get_catalog)]
TodayDep = Annotated[date, Depends(get_today)]
AdminDep = Annotated[str, Depends(require_admin)]
