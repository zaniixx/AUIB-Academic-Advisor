"""Liveness and readiness checks for Docker and load balancers."""

from fastapi import APIRouter
from sqlalchemy import text

from app.api.deps import CatalogDep, SessionDep, TodayDep
from app.api.schemas import HealthOut, ReadyOut

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health", summary="The process is up")
def health() -> HealthOut:
    return HealthOut(status="ok")


@router.get("/ready", summary="The database answers and the catalog is loaded")
def ready(session: SessionDep, catalog: CatalogDep, today: TodayDep) -> ReadyOut:
    session.execute(text("SELECT 1"))
    return ReadyOut(
        status="ready",
        database="ok",
        catalog_revision=catalog.revision,
        programs=len(catalog.published_programs()),
        today=today,
    )
