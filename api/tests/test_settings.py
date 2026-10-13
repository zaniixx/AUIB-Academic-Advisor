"""Settings from the environment, including the database address Heroku Postgres provides."""

import pytest

from app.settings import Settings, sqlalchemy_url


@pytest.fixture(autouse=True)
def _clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("ADVISOR_DATABASE_URL", "DATABASE_URL", "ADVISOR_ENVIRONMENT", "ADVISOR_ADMIN_TOKEN"):
        monkeypatch.delenv(name, raising=False)


def test_heroku_addresses_name_the_driver_and_require_tls() -> None:
    assert (
        sqlalchemy_url("postgres://u:secret@db.example.com:5432/d1")
        == "postgresql+psycopg://u:secret@db.example.com:5432/d1?sslmode=require"
    )
    assert (
        sqlalchemy_url("postgres://u:p@h/d?sslmode=verify-full")
        == "postgresql+psycopg://u:p@h/d?sslmode=verify-full"
    )
    assert sqlalchemy_url("postgres://u:p@h/d?application_name=x") == (
        "postgresql+psycopg://u:p@h/d?application_name=x&sslmode=require"
    )
    assert sqlalchemy_url("postgresql://u:p@h/d") == "postgresql+psycopg://u:p@h/d"
    # Addresses that already name a driver, and SQLite, are left alone.
    assert sqlalchemy_url("postgresql+psycopg://u:p@db:5432/d") == "postgresql+psycopg://u:p@db:5432/d"
    assert sqlalchemy_url("sqlite+pysqlite:///:memory:") == "sqlite+pysqlite:///:memory:"


def test_database_url_from_heroku_postgres(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgres://u:p@h:5432/d")
    monkeypatch.setenv("ADVISOR_ENVIRONMENT", "production")
    assert Settings().database_url == "postgresql+psycopg://u:p@h:5432/d?sslmode=require"


def test_the_advisor_setting_wins_over_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgres://u:p@h:5432/d")
    monkeypatch.setenv("ADVISOR_DATABASE_URL", "postgresql+psycopg://other:p@db:5432/advisor")
    assert Settings().database_url == "postgresql+psycopg://other:p@db:5432/advisor"


def test_pool_size_is_configurable(monkeypatch: pytest.MonkeyPatch) -> None:
    assert (Settings().db_pool_size, Settings().db_max_overflow) == (5, 10)
    monkeypatch.setenv("ADVISOR_DB_POOL_SIZE", "3")
    monkeypatch.setenv("ADVISOR_DB_MAX_OVERFLOW", "2")
    assert (Settings().db_pool_size, Settings().db_max_overflow) == (3, 2)
