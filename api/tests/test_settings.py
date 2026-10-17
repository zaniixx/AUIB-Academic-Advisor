"""Settings from the environment, including the database address Heroku Postgres provides."""

import pytest

from app.settings import Settings, sqlalchemy_url


@pytest.fixture(autouse=True)
def _clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "ADVISOR_DATABASE_URL",
        "DATABASE_URL",
        "ADVISOR_ENVIRONMENT",
        "ADVISOR_ADMIN_TOKEN",
        "ADVISOR_SECRET_KEY",
        "ADVISOR_MAIL_MODE",
        "ADVISOR_SMTP_HOST",
        "ADVISOR_SMTP_FROM",
        "ADVISOR_ALLOWED_EMAIL_DOMAINS",
    ):
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
    monkeypatch.setenv("ADVISOR_SECRET_KEY", "s" * 40)
    monkeypatch.setenv("ADVISOR_MAIL_MODE", "smtp")
    monkeypatch.setenv("ADVISOR_SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("ADVISOR_SMTP_FROM", "advisor@auib.edu.iq")
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


def test_production_needs_a_secret_key_and_a_mail_server(monkeypatch: pytest.MonkeyPatch) -> None:
    from pydantic import ValidationError

    production = {"environment": "production", "database_url": "postgresql+psycopg://u:p@h/d"}
    # Every problem is listed at once, so they can all be fixed in one go.
    with pytest.raises(ValidationError, match=r"(?s)ADVISOR_SECRET_KEY.*emailed in production.*SMTP_HOST"):
        Settings(**production)  # type: ignore[arg-type]
    secret = "s" * 40
    with pytest.raises(ValidationError, match="emailed in production"):
        Settings(**production, secret_key=secret)  # type: ignore[arg-type]
    with pytest.raises(ValidationError, match="ADVISOR_SMTP_HOST"):
        Settings(**production, secret_key=secret, mail_mode="smtp")  # type: ignore[arg-type]
    ready = Settings(  # type: ignore[arg-type]
        **production,
        secret_key=secret,
        mail_mode="smtp",
        smtp_host="smtp.example.com",
        smtp_from="a@auib.edu.iq",
    )
    assert ready.secure_cookies and ready.allowed_email_domains == ["auib.edu.iq"]
    monkeypatch.setenv("ADVISOR_ALLOWED_EMAIL_DOMAINS", '["AUIB.edu.iq", "@staff.auib.edu.iq"]')
    assert Settings().allowed_email_domains == ["auib.edu.iq", "staff.auib.edu.iq"]
