"""Async SQLAlchemy engine factory.

A pure factory, not a module-level singleton: callers (currently just
`database.py`, later the DI container) decide the engine's lifetime
explicitly instead of relying on import-time global state.
"""

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from vtaxi.config.settings import Settings, get_settings
from vtaxi.infrastructure.database.config import get_engine_kwargs


def create_engine(settings: Settings | None = None) -> AsyncEngine:
    """Build the async engine for `settings.database_url` (asyncpg driver
    in every real environment; see `.env.example`).
    """
    settings = settings or get_settings()
    return create_async_engine(settings.database_url, **get_engine_kwargs(settings))
