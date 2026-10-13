"""Configuration from environment variables (prefix ``ADVISOR_``); see .env.example."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "programs"
DEFAULT_COURSES_FILE = Path(__file__).resolve().parents[2] / "data" / "catalog" / "courses.json"


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
    # Bearer token for the admin API. Unset means the admin API is switched off.
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
    api_docs: bool = True
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    @field_validator("database_url")
    @classmethod
    def _driver(cls, value: str) -> str:
        return sqlalchemy_url(value)

    @model_validator(mode="after")
    def _check_production(self) -> Settings:
        if self.environment == "production":
            if self.database_url.startswith("sqlite"):
                raise ValueError("Use PostgreSQL in production (set ADVISOR_DATABASE_URL)")
            token = self.admin_token.get_secret_value() if self.admin_token else ""
            if token and len(token) < 32:
                raise ValueError("ADVISOR_ADMIN_TOKEN must be at least 32 characters in production")
        return self


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
