"""Advertisement-context ports: what `AdvertisementService` needs from a
repository/Unit of Work, expressed as `Protocol`s -- not imports of the
concrete SQLAlchemy classes in `infrastructure/database/repositories/`.
Same reasoning as `application/identity/ports.py`; see that module's
docstring for why this project draws the "framework independent" line
where it does (referencing ORM classes for typing is fine, calling
SQLAlchemy APIs is not).

Deliberate departure from every prior context's Unit-of-Work Protocol
(`IdentityUnitOfWork`/`GeographyUnitOfWork`/`VehicleUnitOfWork` each expose
exactly one repository): this step's own brief asks for
`validate_vehicle()`/`validate_driver()`/`validate_direction()` as
`AdvertisementService` responsibilities, and "an approved vehicle, an
active driver, a valid direction" as a precondition for
`activate_advertisement()`. Those checks read `Vehicle`/`DriverProfile`/
`Direction` rows that belong to other bounded contexts -- unlike
`VehicleService` (Step 8.3), which deliberately declined to validate
`driver_profile_id` because nothing in its own brief asked for it.
`AdvertisementUnitOfWork` therefore exposes three additional attributes,
each typed to a narrow, READ-ONLY protocol (`get_by_id` and, for
`geography`, `get_direction`) -- `AdvertisementService` never creates,
updates, or deletes a `Vehicle`, `DriverProfile`, or `Direction`; only
`uow.advertisements` is ever written to. The concrete
`infrastructure/database/repositories/unit_of_work.UnitOfWork` already
has `.vehicles`/`.drivers`/`.geography` attributes (Steps 7/8.2/8.3), so
no infrastructure change is needed to satisfy this wider Protocol.
"""

from collections.abc import Sequence
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from vtaxi.infrastructure.database.models.advertisement import Advertisement
from vtaxi.infrastructure.database.models.geography import AdministrativeArea, Direction
from vtaxi.infrastructure.database.models.identity import DriverProfile
from vtaxi.infrastructure.database.models.vehicle import Vehicle


class AdvertisementRepositoryProtocol(Protocol):
    async def get_by_id(self, id_: Any) -> Advertisement | None: ...
    async def create(self, **values: Any) -> Advertisement: ...
    async def update(self, instance: Advertisement, **values: Any) -> Advertisement: ...
    async def list_active_by_direction(
        self, direction_id: UUID, *, before: datetime | None = None
    ) -> Sequence[Advertisement]: ...
    async def list_by_driver_profile_id(
        self, driver_profile_id: UUID
    ) -> Sequence[Advertisement]: ...
    async def list_all_active(self) -> Sequence[Advertisement]: ...
    async def list_by_direction(self, direction_id: UUID) -> Sequence[Advertisement]: ...
    async def list_expiring(self, *, before: datetime) -> Sequence[Advertisement]: ...


class VehicleReadProtocol(Protocol):
    """Read-only: validating a vehicle for an advertisement never creates,
    updates, or deletes one -- that stays `VehicleService`'s job (Step 8.3).
    """

    async def get_by_id(self, id_: Any) -> Vehicle | None: ...


class DriverReadProtocol(Protocol):
    """Read-only, same reasoning as `VehicleReadProtocol` --
    `DriverService` (Step 8.1) owns every write to a `DriverProfile`.
    """

    async def get_by_id(self, id_: Any) -> DriverProfile | None: ...


class GeographyReadProtocol(Protocol):
    """Read-only, same reasoning again -- `GeographyService` (Step 8.2)
    owns every write to an `AdministrativeArea`/`Direction`.
    """

    async def get_by_id(self, id_: Any) -> AdministrativeArea | None: ...
    async def get_direction(self, direction_id: UUID) -> Direction | None: ...


class AdvertisementUnitOfWork(Protocol):
    """What `AdvertisementService` needs from a Unit of Work: its own
    repository (read-write) plus three collaborating repositories
    (read-only), and the commit-on-success/rollback-on-exception async
    context manager every service method opens one of via a
    `core.application.UnitOfWorkFactory`.
    """

    advertisements: AdvertisementRepositoryProtocol
    vehicles: VehicleReadProtocol
    drivers: DriverReadProtocol
    geography: GeographyReadProtocol

    async def __aenter__(self) -> "AdvertisementUnitOfWork": ...

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None: ...


__all__ = [
    "AdvertisementRepositoryProtocol",
    "AdvertisementUnitOfWork",
    "DriverReadProtocol",
    "GeographyReadProtocol",
    "VehicleReadProtocol",
]
