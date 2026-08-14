"""`UnitOfWork` -- one transactional unit of work: owns a session, exposes
every repository bound to that same session, and the explicit
begin/commit/rollback/flush/refresh/close lifecycle.

This sits on top of, not instead of, the `session_scope()`/
`transaction_scope()` context managers from Step 6 (infrastructure/
database/session.py) -- those remain the simpler choice for a single-
repository operation; `UnitOfWork` is for a use case that touches several
repositories and needs them to share one atomic transaction.
"""

from types import TracebackType

from sqlalchemy.ext.asyncio import AsyncSession, AsyncSessionTransaction

from vtaxi.infrastructure.database.repositories.advertisement import AdvertisementRepository
from vtaxi.infrastructure.database.repositories.audit import AuditRepository
from vtaxi.infrastructure.database.repositories.booking import BookingRepository
from vtaxi.infrastructure.database.repositories.complaint import ComplaintRepository
from vtaxi.infrastructure.database.repositories.geography import GeographyRepository
from vtaxi.infrastructure.database.repositories.identity import (
    DriverRepository,
    PassengerRepository,
    UserRepository,
)
from vtaxi.infrastructure.database.repositories.notification import NotificationRepository
from vtaxi.infrastructure.database.repositories.rating import RatingRepository
from vtaxi.infrastructure.database.repositories.trip import TripRepository
from vtaxi.infrastructure.database.repositories.vehicle import VehicleRepository


class UnitOfWork:
    """`async with unit_of_work:` commits on clean exit, rolls back on any
    raised exception -- see `__aexit__`. Manual `begin()`/`commit()`/
    `rollback()`/`flush()`/`refresh()`/`close()` are also exposed directly
    for callers that want to manage the boundary themselves instead.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

        self.users = UserRepository(session)
        self.drivers = DriverRepository(session)
        self.passengers = PassengerRepository(session)
        self.geography = GeographyRepository(session)
        self.vehicles = VehicleRepository(session)
        self.advertisements = AdvertisementRepository(session)
        self.bookings = BookingRepository(session)
        self.trips = TripRepository(session)
        self.ratings = RatingRepository(session)
        self.complaints = ComplaintRepository(session)
        self.notifications = NotificationRepository(session)
        self.audit_logs = AuditRepository(session)

    def begin(self) -> AsyncSessionTransaction:
        """Returns the session's async-context-manager transaction, e.g.
        `async with uow.begin(): ...` -- mirrors `AsyncSession.begin()`
        directly rather than wrapping it, since it is already exactly the
        right shape.
        """
        return self.session.begin()

    async def commit(self) -> None:
        await self.session.commit()

    async def rollback(self) -> None:
        await self.session.rollback()

    async def flush(self) -> None:
        await self.session.flush()

    async def refresh(self, instance: object) -> None:
        await self.session.refresh(instance)

    async def close(self) -> None:
        await self.session.close()

    async def __aenter__(self) -> "UnitOfWork":
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        try:
            if exc_type is None:
                await self.commit()
            else:
                await self.rollback()
        finally:
            await self.close()


__all__ = ["UnitOfWork"]
