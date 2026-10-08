"""Configuration from environment variables (prefix ``ADVISOR_``); see .env.example."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "programs"
DEFAULT_COURSES_FILE = Path(__file__).resolve().parents[2] / "data" / "catalog" / "courses.json"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ADVISOR_", extra="ignore")

    environment: Literal["development", "test", "production"] = "development"
    database_url: str = "sqlite+pysqlite:///./advisor-dev.sqlite3"
    # Bearer token for the admin API. Unset means the admin API is switched off.
    admin_token: SecretStr | None = None
    cors_origins: list[str] = Field(default_factory=list)
    # Requests per minute per client address for the planning endpoints.
    rate_limit_per_minute: int = Field(default=60, ge=1)
    max_request_bytes: int = Field(default=512_000, ge=10_000)
    # Program packages (one folder each) and the course catalog they all share.
    data_dir: Path = DEFAULT_DATA_DIR
    courses_file: Path = DEFAULT_COURSES_FILE
    api_docs: bool = True
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    @model_validator(mode="after")
    def _check_production(self) -> Settings:
        if self.environment == "production":
            if self.database_url.startswith("sqlite"):
                raise ValueError("Use PostgreSQL in production (set ADVISOR_DATABASE_URL)")
            token = self.admin_token.get_secret_value() if self.admin_token else ""
            if token and len(token) < 32:
                raise ValueError("ADVISOR_ADMIN_TOKEN must be at least 32 characters in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
