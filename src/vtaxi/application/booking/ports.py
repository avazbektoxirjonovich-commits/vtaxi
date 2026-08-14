"""Booking-context ports: what `BookingService` needs from a repository/
Unit of Work, expressed as `Protocol`s -- not imports of the concrete
SQLAlchemy classes in `infrastructure/database/repositories/`. Same
reasoning as `application/identity/ports.py`; see that module's docstring
for why this project draws the "framework independent" line where it does.

Same widened-`UnitOfWork` shape as `application/advertisement/ports.py`
(Step 8.4), for the same reason: `validate_passenger()`/
`validate_advertisement()` and the "passenger cannot book own
advertisement" rule read `PassengerProfile`/`Advertisement`/`DriverProfile`
rows that belong to other bounded contexts. `BookingUnitOfWork` exposes
three read-only collaborating repositories alongside its own
`bookings` -- `BookingService` never creates, updates, or deletes a
`PassengerProfile`, `Advertisement`, or `DriverProfile` through this
Unit of Work.

Note what this does *not* cover: `Advertisement`'s seat counters
(`available_seats`/`reserved_seats`). Those are never written through
`uow.advertisements` here -- per this step's own brief
("BookingService MUST communicate with AdvertisementService"),
`BookingService` is constructor-injected with a live `AdvertisementService`
instance (see booking_service.py) and calls its public seat-counter
methods for every seat mutation. `advertisements` on this Protocol is
read-only and exists solely for `BookingService`'s own validation reads
(status, `available_seats`, `driver_profile_id`).
"""

from collections.abc import Sequence
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from vtaxi.infrastructure.database.enums import BookingStatus
from vtaxi.infrastructure.database.models.advertisement import Advertisement
from vtaxi.infrastructure.database.models.booking import Booking
from vtaxi.infrastructure.database.models.identity import DriverProfile, PassengerProfile


class BookingRepositoryProtocol(Protocol):
    async def get_by_id(self, id_: Any) -> Booking | None: ...
    async def create(self, **values: Any) -> Booking: ...
    async def update(self, instance: Booking, **values: Any) -> Booking: ...
    async def list_by_advertisement(
        self, advertisement_id: UUID, *, status: BookingStatus | None = None
    ) -> Sequence[Booking]: ...
    async def list_by_passenger_profile_id(
        self, passenger_profile_id: UUID
    ) -> Sequence[Booking]: ...
    async def list_by_driver_profile_id(self, driver_profile_id: UUID) -> Sequence[Booking]: ...
    async def list_active(self) -> Sequence[Booking]: ...
    async def list_reserved(self) -> Sequence[Booking]: ...
    async def list_expiring(self, *, before: datetime) -> Sequence[Booking]: ...
    async def find_active_by_passenger_and_advertisement(
        self, passenger_profile_id: UUID, advertisement_id: UUID
    ) -> Booking | None: ...


class PassengerReadProtocol(Protocol):
    """Read-only -- `PassengerService` (Step 8.1) owns every write to a
    `PassengerProfile`.
    """

    async def get_by_id(self, id_: Any) -> PassengerProfile | None: ...


class DriverReadProtocol(Protocol):
    """Read-only, same reasoning -- `DriverService` (Step 8.1) owns every
    write to a `DriverProfile`.
    """

    async def get_by_id(self, id_: Any) -> DriverProfile | None: ...


class AdvertisementReadProtocol(Protocol):
    """Read-only -- see module docstring for why every *write* to an
    `Advertisement`'s seat counters goes through the injected
    `AdvertisementService` instead.
    """

    async def get_by_id(self, id_: Any) -> Advertisement | None: ...


class BookingUnitOfWork(Protocol):
    """What `BookingService` needs from a Unit of Work: its own repository
    (read-write) plus three collaborating repositories (read-only), and
    the commit-on-success/rollback-on-exception async context manager
    every service method opens one of via a
    `core.application.UnitOfWorkFactory`.
    """

    bookings: BookingRepositoryProtocol
    passengers: PassengerReadProtocol
    drivers: DriverReadProtocol
    advertisements: AdvertisementReadProtocol

    async def __aenter__(self) -> "BookingUnitOfWork": ...

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None: ...


__all__ = [
    "AdvertisementReadProtocol",
    "BookingRepositoryProtocol",
    "BookingUnitOfWork",
    "DriverReadProtocol",
    "PassengerReadProtocol",
]
