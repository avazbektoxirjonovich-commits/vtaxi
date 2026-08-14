"""Application-wide settings, loaded from environment variables and `.env`.

Every field has a safe development default so the application boots without
a `.env` file present. Real deployments override these via the environment
(see `.env.example`). Validation is fail-fast: an invalid value raises at
process startup, never on first use deep inside a handler.
"""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Root configuration object. Construct via `get_settings()`, not directly."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: Literal["development", "testing", "staging", "production"] = "development"
    log_level: str = "INFO"

    bot_token: str = "changeme"
    webhook_url: str | None = None

    database_url: str = "postgresql+asyncpg://vtaxi:vtaxi@localhost:5432/vtaxi"
    redis_url: str = "redis://localhost:6379/0"

    # Raw connection-pool knobs -- environment-appropriate defaults are
    # assembled from these by infrastructure/database/config.py, not here;
    # this class only owns "what can be overridden from the environment."
    db_pool_size: int = 5
    db_max_overflow: int = 10
    db_pool_timeout: int = 30
    db_pool_recycle: int = 1800
    db_pool_pre_ping: bool = True

    # Reserved for a future payments step (see docs/01 SS14.11). Unused today.
    click_merchant_id: str | None = None
    payme_merchant_id: str | None = None
    paynet_merchant_id: str | None = None


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide `Settings` singleton, built once and cached."""
    return Settings()
