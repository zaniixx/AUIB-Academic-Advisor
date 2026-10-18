"""Configuration from environment variables (prefix ``ADVISOR_``); see .env.example."""

from __future__ import annotations

import hashlib
import hmac
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]  # the repository, or the image's data root
DEFAULT_DATA_DIR = REPO_ROOT / "data" / "programs"
DEFAULT_COURSES_FILE = REPO_ROOT / "data" / "catalog" / "courses.json"
DEFAULT_SEALED_DATA = REPO_ROOT / "data" / "sealed" / "curriculum.sealed"
# Public on purpose, for development and tests; production refuses to start with it.
DEVELOPMENT_SECRET = "development-only-secret-do-not-use-in-production"  # noqa: S105


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ADVISOR_", extra="ignore")

    environment: Literal["development", "test", "production"] = "development"
    # ADVISOR_DATABASE_URL, or DATABASE_URL as Heroku Postgres sets it (see sqlalchemy_url).
    database_url: str = Field(
        default="sqlite+pysqlite:///./advisor-dev.sqlite3",
        validation_alias=AliasChoices("ADVISOR_DATABASE_URL", "DATABASE_URL", "database_url"),
    )
    # Connections each API worker keeps open, and how many more it may open at busy moments.
    # Heroku's smallest Postgres plans allow 20 connections in all.
    db_pool_size: int = Field(default=5, ge=1, le=50)
    db_max_overflow: int = Field(default=10, ge=0, le=50)
    # The master token (ADR 0009): adds and removes admins, and opens the admin page in an emergency.
    # Admins otherwise sign in with their AUIB email. It also keys the sign-in codes (see code_key).
    admin_token: SecretStr | None = None
    cors_origins: list[str] = Field(default_factory=list)
    # Requests per minute per client address for the planning endpoints.
    rate_limit_per_minute: int = Field(default=60, ge=1)
    max_request_bytes: int = Field(default=512_000, ge=10_000)
    # Admin uploads (a whole course list or term schedule) may be larger.
    max_admin_request_bytes: int = Field(default=8_000_000, ge=10_000)
    # Program packages (one folder each) and the course catalog they all share.
    data_dir: Path = DEFAULT_DATA_DIR
    courses_file: Path = DEFAULT_COURSES_FILE
    # The repository holds them sealed (ADR 0008); this key opens the sealed copy when the plain files
    # are not on disk. Kept by the maintainers, Heroku's config vars and GitHub's Actions secrets.
    sealed_data: Path = DEFAULT_SEALED_DATA
    data_key: SecretStr | None = None
    api_docs: bool = True
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    # Sign-in (F9.1): only addresses at these domains get a code, and only signed-in students reach
    # the course and program data.
    allowed_email_domains: list[str] = Field(default_factory=lambda: ["auib.edu.iq"])
    # Keys the hashes of sign-in codes, so a copy of the database alone cannot be used to guess them.
    # Optional: by default the key is derived from the master token (code_key). The development value
    # is public and only for development and tests.
    secret_key: SecretStr = SecretStr(DEVELOPMENT_SECRET)
    login_code_minutes: int = Field(default=10, ge=1, le=60)
    session_days: int = Field(default=30, ge=1, le=180)
    # How sign-in codes are delivered: "smtp" sends email; "log" writes the code to the API log,
    # for development and tests only.
    mail_mode: Literal["smtp", "log"] = "log"
    smtp_host: str = ""
    smtp_port: int = Field(default=587, ge=1, le=65535)
    # "starttls" (port 587), "ssl" (port 465) or "none" (a trusted relay on the same network).
    smtp_security: Literal["starttls", "ssl", "none"] = "starttls"
    smtp_username: str = ""
    smtp_password: SecretStr = SecretStr("")
    # The sender, such as "AUIB Academic Advisor <advisor@auib.edu.iq>".
    smtp_from: str = ""

    @field_validator("database_url")
    @classmethod
    def _driver(cls, value: str) -> str:
        return sqlalchemy_url(value)

    @field_validator("allowed_email_domains")
    @classmethod
    def _domains(cls, values: list[str]) -> list[str]:
        domains = [value.strip().lower().lstrip("@") for value in values if value.strip()]
        if not domains:
            raise ValueError("Name at least one email domain students sign in with")
        return domains

    @model_validator(mode="after")
    def _check_production(self) -> Settings:
        problems = self._production_problems()
        if problems:
            # One line per problem, so they can all be fixed at once (python -m app.cli check-settings).
            raise ValueError("\n".join(problems))
        return self

    def _production_problems(self) -> list[str]:
        if self.environment != "production":
            return []
        problems = []
        if self.database_url.startswith("sqlite"):
            problems.append("Use PostgreSQL in production (set ADVISOR_DATABASE_URL)")
        token = self.admin_token.get_secret_value() if self.admin_token else ""
        secret = self.secret_key.get_secret_value()
        if token and len(token) < 32:
            problems.append(
                "ADVISOR_ADMIN_TOKEN (the master token) must be at least 32 characters in production"
            )
        elif not token and secret == DEVELOPMENT_SECRET:
            problems.append(
                "Set ADVISOR_ADMIN_TOKEN, the master token: a random value of at least 32 characters"
            )
        if secret != DEVELOPMENT_SECRET and len(secret) < 32:
            problems.append(
                "ADVISOR_SECRET_KEY must be at least 32 characters, or unset to use the master token"
            )
        if self.mail_mode != "smtp":
            problems.append("Sign-in codes must be emailed in production (ADVISOR_MAIL_MODE=smtp)")
        if not self.smtp_host or not self.smtp_from:
            problems.append("Set ADVISOR_SMTP_HOST and ADVISOR_SMTP_FROM so sign-in codes can be emailed")
        return problems

    @property
    def code_key(self) -> bytes:
        """The key for hashing sign-in codes: ADVISOR_SECRET_KEY when it is set, else derived from the
        master token, so a server needs one secret fewer. Changing it only stops codes already sent."""
        secret = self.secret_key.get_secret_value()
        token = self.admin_token.get_secret_value() if self.admin_token else ""
        if secret == DEVELOPMENT_SECRET and token:
            return hmac.new(token.encode(), b"auib-advisor sign-in codes", hashlib.sha256).digest()
        return secret.encode()

    @property
    def secure_cookies(self) -> bool:
        """Session cookies are sent over HTTPS only (browsers treat localhost as HTTPS); tests use HTTP."""
        return self.environment != "test"


def sqlalchemy_url(url: str) -> str:
    """The database address in SQLAlchemy's form.

    Heroku Postgres gives ``postgres://user:password@host:5432/name``; SQLAlchemy needs the driver
    named (``postgresql+psycopg://``), and Heroku accepts only encrypted connections, so such an
    address also gets ``sslmode=require`` unless it names a mode already.
    """
    if url.startswith("postgres://"):
        url = "postgresql+psycopg://" + url.removeprefix("postgres://")
        if "sslmode=" not in url:
            url += ("&" if "?" in url else "?") + "sslmode=require"
    elif url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url.removeprefix("postgresql://")
    return url


@lru_cache
def get_settings() -> Settings:
    return Settings()
