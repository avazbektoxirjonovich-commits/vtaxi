"""The `Database` lifecycle object: owns one engine + session factory for
the process's lifetime, and the startup/shutdown/health-check operations
around them.

Not wired into `main.py` yet: doing so would make `python -m vtaxi`
require a live Postgres connection just to boot, which would break the
Step 2 guarantee that this project runs immediately after `uv sync` with
no infrastructure running. That wiring belongs with the Bot step (Step 7),
which is the first thing that actually needs a live database connection
to do anything.
"""

import logging
from collections.abc import AsyncIterator
from contextlib import AbstractAsyncContextManager, asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from vtaxi.config.settings import Settings, get_settings
from vtaxi.infrastructure.database.engine import create_engine
from vtaxi.infrastructure.database.session import create_session_factory
from vtaxi.infrastructure.database.session import session_scope as _session_scope
from vtaxi.infrastructure.database.session import transaction_scope as _transaction_scope

logger = logging.getLogger("vtaxi")


class Database:
    """Constructed once per process. The engine itself is lazy (no socket
    is opened until first use) -- `startup()` is what turns "the engine
    object exists" into "we've confirmed Postgres is actually reachable."
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings: Settings = settings or get_settings()
        self.engine: AsyncEngine = create_engine(self.settings)
        self.session_factory: async_sessionmaker[AsyncSession] = create_session_factory(self.engine)

    async def startup(self) -> None:
        """Fail fast: verify the database is reachable before the rest of
        the app starts serving traffic, instead of discovering a bad
        connection string on the first real query a user triggers.
        """
        await self.health_check(raise_on_failure=True)
        logger.info("database connection established (environment=%s)", self.settings.environment)

    async def shutdown(self) -> None:
        await self.engine.dispose()
        logger.info("database connection pool disposed")

    async def health_check(self, *, raise_on_failure: bool = False) -> bool:
        """A lightweight ping -- `SELECT 1` on its own connection, not
        borrowed from application code's session usage.
        """
        try:
            async with self.engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
            return True
        except Exception:
            logger.exception("database health check failed")
            if raise_on_failure:
                raise
            return False

    def session_scope(self) -> AbstractAsyncContextManager[AsyncSession]:
        return _session_scope(self.session_factory)

    def transaction_scope(self) -> AbstractAsyncContextManager[AsyncSession]:
        return _transaction_scope(self.session_factory)


@asynccontextmanager
async def database_lifespan(settings: Settings | None = None) -> AsyncIterator[Database]:
    """Convenience context manager pairing `startup()`/`shutdown()` --
    `async with database_lifespan() as db: ...` -- for whichever future
    entrypoint (bot, worker, script) first needs the database running.
    """
    db = Database(settings)
    await db.startup()
    try:
        yield db
    finally:
        await db.shutdown()
