"""Vehicle-context ports: what `VehicleService` needs from a repository/
Unit of Work, expressed as `Protocol`s -- not imports of the concrete
SQLAlchemy classes in `infrastructure/database/repositories/`. Same
reasoning as `application/identity/ports.py`/`application/geography/
ports.py`; see the former's docstring for why referencing ORM classes for
typing is not a "framework independent" violation in this project.

`VehicleRepositoryProtocol` includes the `VehicleDocument`/
`DriverDocument`/`VehiclePhoto` methods added to the concrete
`VehicleRepository` in Step 8.3 (see that file's docstring) -- the
repository is bound to `Vehicle`, so its inherited `create()` cannot
persist any of those three, and this service has no other way to create
one without SQLAlchemy code of its own.
"""

from collections.abc import Sequence
from typing import Any, Protocol
from uuid import UUID

from vtaxi.infrastructure.database.models.vehicle import (
    DriverDocument,
    Vehicle,
    VehicleDocument,
    VehiclePhoto,
)


class VehicleRepositoryProtocol(Protocol):
    async def get_by_id(self, id_: Any) -> Vehicle | None: ...
    async def get_by_plate_number(self, plate_number: str) -> Vehicle | None: ...
    async def list_by_driver_profile_id(self, driver_profile_id: UUID) -> Sequence[Vehicle]: ...
    async def create(self, **values: Any) -> Vehicle: ...
    async def update(self, instance: Vehicle, **values: Any) -> Vehicle: ...
    async def delete(self, instance: Vehicle) -> None: ...
    async def restore(self, instance: Vehicle) -> Vehicle: ...

    async def create_vehicle_document(self, **values: Any) -> VehicleDocument: ...
    async def get_vehicle_document(self, document_id: UUID) -> VehicleDocument | None: ...
    async def list_vehicle_documents(self, vehicle_id: UUID) -> Sequence[VehicleDocument]: ...
    async def update_vehicle_document(
        self, instance: VehicleDocument, **values: Any
    ) -> VehicleDocument: ...

    async def create_driver_document(self, **values: Any) -> DriverDocument: ...
    async def get_driver_document(self, document_id: UUID) -> DriverDocument | None: ...
    async def list_driver_documents(self, driver_profile_id: UUID) -> Sequence[DriverDocument]: ...
    async def update_driver_document(
        self, instance: DriverDocument, **values: Any
    ) -> DriverDocument: ...

    async def create_vehicle_photo(self, **values: Any) -> VehiclePhoto: ...
    async def list_vehicle_photos(self, vehicle_id: UUID) -> Sequence[VehiclePhoto]: ...


class VehicleUnitOfWork(Protocol):
    """What `VehicleService` needs from a Unit of Work: the one repository
    above, plus the commit-on-success/rollback-on-exception async context
    manager every service method opens one of via a
    `core.application.UnitOfWorkFactory`.
    """

    vehicles: VehicleRepositoryProtocol

    async def __aenter__(self) -> "VehicleUnitOfWork": ...

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None: ...


__all__ = ["VehicleRepositoryProtocol", "VehicleUnitOfWork"]
