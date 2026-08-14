"""Async session factory and three ways to obtain a session, each for a
different caller:

* `get_session` -- an async-generator dependency (the shape a future DI
  framework / Aiogram middleware expects via `Depends`-style wiring). No
  automatic commit: the use case that receives the session decides when
  to commit.
* `session_scope` -- the same "just give me a session" behavior as a
  plain `async with` context manager, for ad-hoc scripts that aren't
  going through a DI framework.
* `transaction_scope` -- like `session_scope`, but wraps `session.begin()`
  so the block commits automatically on success and rolls back on any
  exception -- the common "one unit of work" case.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """`expire_on_commit=False`: attributes stay readable after commit
    without a fresh SELECT, matching the pattern used throughout this
    project's own verification scripts and tests.
    """
    return async_sessionmaker(engine, expire_on_commit=False)


async def get_session(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    async with session_factory() as session:
        yield session


@asynccontextmanager
async def session_scope(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    async with session_factory() as session:
        yield session


@asynccontextmanager
async def transaction_scope(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    async with session_factory() as session, session.begin():
        yield session
