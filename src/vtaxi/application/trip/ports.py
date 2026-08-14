"""Trip-context ports: what `TripService` needs from a repository/Unit of
Work, expressed as `Protocol`s -- not imports of the concrete SQLAlchemy
classes in `infrastructure/database/repositories/`. Same reasoning as
`application/identity/ports.py`; see that module's docstring for why this
project draws the "framework independent" line where it does.

Same widened-`UnitOfWork` shape as `application/advertisement/ports.py`
(Step 8.4) and `application/booking/ports.py` (Step 8.5), for the same
reason, taken further: this step's own Validation section names
`validate_driver()`, `validate_vehicle()`, `validate_booking()`, and
`validate_passenger()` as `TripService` responsibilities, and "driver must
own advertisement" reads `Advertisement` directly too. `TripUnitOfWork`
therefore exposes its own `trips` (read-write) alongside FOUR read-only
collaborating repositories -- `TripService` never creates, updates, or
deletes an `Advertisement`, `Vehicle`, `DriverProfile`, `PassengerProfile`,
or `Booking` through this Unit of Work.

Unlike `BookingService` (Step 8.5), `TripService` does *not* depend on any
sibling service instance (no `AdvertisementService`/`BookingService`
injected): this step's brief has no "TripService MUST communicate with
X" instruction the way Booking's did for seat counters, so there is
nothing here for `TripService` to write back through another service's
API -- see trip_service.py's module docstring for the two write-backs
(`Advertisement.started_at`/`completed_at`, `Booking.booking_status`
-> `COMPLETED`) deliberately left out of this step's scope instead.
"""

from collections.abc import Sequence
from typing import Any, Protocol
from uuid import UUID

from vtaxi.infrastructure.database.models.advertisement import Advertisement
from vtaxi.infrastructure.database.models.booking import Booking
from vtaxi.infrastructure.database.models.identity import DriverProfile, PassengerProfile
from vtaxi.infrastructure.database.models.trip import Trip, TripPassenger
from vtaxi.infrastructure.database.models.vehicle import Vehicle


class TripRepositoryProtocol(Protocol):
    async def get_by_id(self, id_: Any) -> Trip | None: ...
    async def create(self, **values: Any) -> Trip: ...
    async def update(self, instance: Trip, **values: Any) -> Trip: ...
    async def get_by_advertisement_id(self, advertisement_id: UUID) -> Trip | None: ...
    async def list_by_driver_profile_id(self, driver_profile_id: UUID) -> Sequence[Trip]: ...
    async def list_by_passenger_profile_id(self, passenger_profile_id: UUID) -> Sequence[Trip]: ...
    async def list_active(self) -> Sequence[Trip]: ...
    async def list_completed(self) -> Sequence[Trip]: ...

    async def create_trip_passenger(self, **values: Any) -> TripPassenger: ...
    async def find_trip_passenger(
        self, trip_id: UUID, booking_id: UUID
    ) -> TripPassenger | None: ...
    async def list_trip_passengers(self, trip_id: UUID) -> Sequence[TripPassenger]: ...
    async def update_trip_passenger(
        self, instance: TripPassenger, **values: Any
    ) -> TripPassenger: ...
    async def delete_trip_passenger(self, instance: TripPassenger) -> None: ...


class AdvertisementReadProtocol(Protocol):
    """Read-only -- `AdvertisementService` (Step 8.4) owns every write to
    an `Advertisement`.
    """

    async def get_by_id(self, id_: Any) -> Advertisement | None: ...


class VehicleReadProtocol(Protocol):
    """Read-only -- `VehicleService` (Step 8.3) owns every write to a
    `Vehicle`.
    """

    async def get_by_id(self, id_: Any) -> Vehicle | None: ...


class DriverReadProtocol(Protocol):
    """Read-only -- `DriverService` (Step 8.1) owns every write to a
    `DriverProfile`.
    """

    async def get_by_id(self, id_: Any) -> DriverProfile | None: ...


class PassengerReadProtocol(Protocol):
    """Read-only -- `PassengerService` (Step 8.1) owns every write to a
    `PassengerProfile`.
    """

    async def get_by_id(self, id_: Any) -> PassengerProfile | None: ...


class BookingReadProtocol(Protocol):
    """Read-only -- `BookingService` (Step 8.5) owns every write to a
    `Booking`.
    """

    async def get_by_id(self, id_: Any) -> Booking | None: ...


class TripUnitOfWork(Protocol):
    """What `TripService` needs from a Unit of Work: its own repository
    (read-write) plus four collaborating repositories (read-only), and
    the commit-on-success/rollback-on-exception async context manager
    every service method opens one of via a
    `core.application.UnitOfWorkFactory`.
    """

    trips: TripRepositoryProtocol
    advertisements: AdvertisementReadProtocol
    vehicles: VehicleReadProtocol
    drivers: DriverReadProtocol
    passengers: PassengerReadProtocol
    bookings: BookingReadProtocol

    async def __aenter__(self) -> "TripUnitOfWork": ...

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None: ...


__all__ = [
    "AdvertisementReadProtocol",
    "BookingReadProtocol",
    "DriverReadProtocol",
    "PassengerReadProtocol",
    "TripRepositoryProtocol",
    "TripUnitOfWork",
    "VehicleReadProtocol",
]
