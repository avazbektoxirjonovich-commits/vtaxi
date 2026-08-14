"""`RepositoryFactory` -- the seam between Step 6's session factory and
Step 7's repositories/Unit of Work. Whatever wires the future DI
container (Step 8/9) constructs one of these from a `Database`'s
`session_factory` and hands it to whatever needs repositories.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from vtaxi.infrastructure.database.repositories.unit_of_work import UnitOfWork


class RepositoryFactory:
    """Builds a fresh, session-bound `UnitOfWork` per call -- never a
    shared/reused session across calls, so concurrent callers never
    accidentally share one unit of work.
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    def create_unit_of_work(self) -> UnitOfWork:
        """Caller owns the session's lifecycle (including closing it)."""
        return UnitOfWork(self._session_factory())

    @asynccontextmanager
    async def unit_of_work(self) -> AsyncIterator[UnitOfWork]:
        """`async with factory.unit_of_work() as uow: ...` -- commits on
        clean exit, rolls back on exception, always closes (see
        `UnitOfWork.__aexit__`).
        """
        async with UnitOfWork(self._session_factory()) as uow:
            yield uow


__all__ = ["RepositoryFactory"]
