"""Rating-context ports: what `RatingService` needs from a repository/Unit
of Work, expressed as `Protocol`s.

**Deliberate departure from every prior context's ports.py** (Identity/
Geography/Vehicle/Advertisement/Booking/Trip): those all imported the
concrete SQLAlchemy declarative model (`Vehicle`, `Advertisement`, ...)
purely for type hints, on the reasoning that "referencing an ORM class
for typing is not a framework dependency." Step 8.7's own brief is
explicit and repeated: "Services MUST NOT import SQLAlchemy ORM models
directly" / "Never import ORM models in the Application Layer" -- a
stricter line than the one every previous step drew. This module honors
that literally rather than reconciling it away.

The mechanism: `RatingRecord`/`TripRecord`/`BookingRecord`/
`DriverProfileRecord`/`PassengerProfileRecord` below are plain, structural
`Protocol`s describing only the attributes this service actually reads --
zero import of `vtaxi.infrastructure.database.models.*`. `Protocol`
compatibility in Python (PEP 544) is structural, not nominal: the real
`Rating`/`Trip`/`Booking`/`DriverProfile`/`PassengerProfile` ORM classes
satisfy these shapes automatically (they have every attribute named
below, with compatible types) without inheriting from them or being
imported here. The concrete `infrastructure/database/repositories/
unit_of_work.UnitOfWork` therefore still structurally satisfies
`RatingUnitOfWork` with zero infrastructure change.

Repository-Protocol methods that take the entity as a *parameter*
(`update`/`delete`) are typed `instance: Any`, not `instance: RatingRecord`:
a parameter position is contravariant, and `BaseRepository[Rating].update`
declares `instance: Rating` -- `Rating` is not a valid substitute for an
arbitrary `RatingRecord`-shaped parameter (only the reverse holds), so
typing it as `RatingRecord` would make the concrete repository fail this
Protocol. `Any` is honest here: the service only ever forwards an object
it just received from `get_by_id()`/`create()`, never constructs one
itself.
"""

import uuid
from collections.abc import Sequence
from datetime import datetime
from typing import Any, Protocol

from vtaxi.infrastructure.database.enums import PartyRole, TripStatus


class RatingRecord(Protocol):
    id: uuid.UUID
    trip_id: uuid.UUID
    booking_id: uuid.UUID
    driver_profile_id: uuid.UUID
    passenger_profile_id: uuid.UUID
    rater_user_id: uuid.UUID
    target_user_id: uuid.UUID
    rater_role: PartyRole
    score: int
    comment: str | None
    created_at: datetime


class TripRecord(Protocol):
    """Only the two attributes `RatingService` actually reads: whether the
    trip exists at all, who its driver was, and whether it has finished.
    """

    id: uuid.UUID
    driver_profile_id: uuid.UUID
    trip_status: TripStatus


class BookingRecord(Protocol):
    id: uuid.UUID
    passenger_profile_id: uuid.UUID


class DriverProfileRecord(Protocol):
    id: uuid.UUID
    user_id: uuid.UUID


class PassengerProfileRecord(Protocol):
    id: uuid.UUID
    user_id: uuid.UUID


class RatingRepositoryProtocol(Protocol):
    async def get_by_id(self, id_: Any) -> RatingRecord | None: ...
    async def create(self, **values: Any) -> RatingRecord: ...
    async def update(self, instance: Any, **values: Any) -> RatingRecord: ...
    async def delete(self, instance: Any) -> None: ...
    async def list_by_driver_profile_id(
        self, driver_profile_id: uuid.UUID
    ) -> Sequence[RatingRecord]: ...
    async def list_by_passenger_profile_id(
        self, passenger_profile_id: uuid.UUID
    ) -> Sequence[RatingRecord]: ...
    async def list_by_booking_id(self, booking_id: uuid.UUID) -> Sequence[RatingRecord]: ...


class TripReadProtocol(Protocol):
    """Read-only -- `TripService` (Step 8.6) owns every write to a `Trip`."""

    async def get_by_id(self, id_: Any) -> TripRecord | None: ...


class BookingReadProtocol(Protocol):
    """Read-only -- `BookingService` (Step 8.5) owns every write to a
    `Booking`.
    """

    async def get_by_id(self, id_: Any) -> BookingRecord | None: ...


class DriverReadProtocol(Protocol):
    """Read-only -- `DriverService` (Step 8.1) owns every write to a
    `DriverProfile`.
    """

    async def get_by_id(self, id_: Any) -> DriverProfileRecord | None: ...


class PassengerReadProtocol(Protocol):
    """Read-only -- `PassengerService` (Step 8.1) owns every write to a
    `PassengerProfile`.
    """

    async def get_by_id(self, id_: Any) -> PassengerProfileRecord | None: ...


class RatingUnitOfWork(Protocol):
    """What `RatingService` needs from a Unit of Work: its own repository
    (read-write) plus four collaborating repositories (read-only), and
    the commit-on-success/rollback-on-exception async context manager
    every service method opens one of via a
    `core.application.UnitOfWorkFactory`.
    """

    ratings: RatingRepositoryProtocol
    trips: TripReadProtocol
    bookings: BookingReadProtocol
    drivers: DriverReadProtocol
    passengers: PassengerReadProtocol

    async def __aenter__(self) -> "RatingUnitOfWork": ...

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None: ...


__all__ = [
    "BookingReadProtocol",
    "BookingRecord",
    "DriverProfileRecord",
    "DriverReadProtocol",
    "PassengerProfileRecord",
    "PassengerReadProtocol",
    "RatingRecord",
    "RatingRepositoryProtocol",
    "RatingUnitOfWork",
    "TripReadProtocol",
    "TripRecord",
]
