from __future__ import annotations

import os
from collections.abc import Callable, Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.importer.load import import_courses, import_package
from app.importer.package import load_courses, load_package
from app.main import create_app
from app.models import Base
from app.services import auth
from app.settings import Settings
from tests.conftest import COURSES_FILE, PACKAGES, TODAY

ADMIN_TOKEN = "test-admin-token-that-is-long-enough-123"
STUDENT_EMAIL = "student@auib.edu.iq"
# CI sets ADVISOR_TEST_DATABASE_URL to run these tests against PostgreSQL too.
DATABASE_URL = os.environ.get("ADVISOR_TEST_DATABASE_URL", "sqlite+pysqlite:///:memory:")


def build_app(**overrides: object) -> FastAPI:
    values: dict[str, object] = {
        "environment": "test",
        "database_url": DATABASE_URL,
        "admin_token": ADMIN_TOKEN,
        "rate_limit_per_minute": 1000,
        **overrides,
    }
    settings = Settings(**values)  # type: ignore[arg-type]
    app = create_app(settings)
    # On PostgreSQL every app shares one database: start each from empty, including the table the
    # migration check in CI leaves behind.
    Base.metadata.drop_all(app.state.engine)
    with app.state.engine.begin() as connection:
        connection.execute(text("DROP TABLE IF EXISTS alembic_version"))
    Base.metadata.create_all(app.state.engine)
    with app.state.session_factory() as session:
        import_courses(session, load_courses(COURSES_FILE), actor="test")
        for package in PACKAGES:
            import_package(session, load_package(package), actor="test", accept_warnings=True)
        # Course and program data need a signed-in AUIB student (F9.1); most tests use this session.
        app.state.student_token = auth.start_session(session, settings, STUDENT_EMAIL, auth.utcnow()).token
        session.commit()
    app.state.today = lambda: TODAY
    return app


@pytest.fixture
def make_client() -> Iterator[Callable[..., TestClient]]:
    clients: list[TestClient] = []

    def make(signed_in: bool = True, **overrides: object) -> TestClient:
        app = build_app(**overrides)
        client = TestClient(app)
        if signed_in:
            client.cookies.set("advisor_session", app.state.student_token)
        client.__enter__()
        clients.append(client)
        return client

    yield make
    for client in clients:
        client.__exit__(None, None, None)


@pytest.fixture
def client(make_client: Callable[..., TestClient]) -> TestClient:
    """A signed-in AUIB student."""
    return make_client()


@pytest.fixture
def anonymous_client(client: TestClient) -> TestClient:
    """Nobody signed in: another browser on the same server as ``client`` (a second app would empty the
    shared PostgreSQL database, signing ``client`` out)."""
    return TestClient(client.app)


@pytest.fixture
def admin_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {ADMIN_TOKEN}"}
