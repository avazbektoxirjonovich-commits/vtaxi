"""Repository for the Vehicle domain. Bound model is `Vehicle` itself.

`DriverDocument`/`VehicleDocument`/`VehiclePhoto` are queried and persisted
directly via `self.session` rather than through their own bound
repositories -- same reasoning as `GeographyRepository` and `Direction`:
only one `VehicleRepository` was asked for (Step 7), and this step
(8.3, `VehicleService`) explicitly assigns Vehicle Documents, Driver
Documents, and Vehicle Photos to it. `create_vehicle_document`/
`create_driver_document`/`create_vehicle_photo` exist because this
repository's inherited `create()` always builds a `Vehicle` (the model
it's bound to); `update_vehicle_document`/`update_driver_document` exist
purely for a correctly-typed return value -- the inherited generic
`update()` would work identically (it never touches `self.model`), but
returns `Vehicle` per its own type hint.
"""

import uuid
from collections.abc import Sequence
from typing import Any

from sqlalchemy import select

from vtaxi.infrastructure.database.models.vehicle import (
    DriverDocument,
    Vehicle,
    VehicleDocument,
    VehiclePhoto,
)
from vtaxi.infrastructure.database.repositories.base import BaseRepository


class VehicleRepository(BaseRepository[Vehicle]):
    model = Vehicle

    async def get_by_plate_number(self, plate_number: str) -> Vehicle | None:
        return await self.get_one(Vehicle.plate_number == plate_number)

    async def list_by_driver_profile_id(self, driver_profile_id: uuid.UUID) -> Sequence[Vehicle]:
        return await self.get_many(Vehicle.driver_profile_id == driver_profile_id)

    # --- Vehicle Documents -----------------------------------------------

    async def create_vehicle_document(self, **values: Any) -> VehicleDocument:
        document = VehicleDocument(**values)
        self.session.add(document)
        await self.session.flush()
        return document

    async def get_vehicle_document(self, document_id: uuid.UUID) -> VehicleDocument | None:
        stmt = select(VehicleDocument).where(VehicleDocument.id == document_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_vehicle_documents(self, vehicle_id: uuid.UUID) -> Sequence[VehicleDocument]:
        stmt = select(VehicleDocument).where(VehicleDocument.vehicle_id == vehicle_id)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def update_vehicle_document(
        self, instance: VehicleDocument, **values: Any
    ) -> VehicleDocument:
        for key, value in values.items():
            setattr(instance, key, value)
        await self.session.flush()
        return instance

    # --- Driver Documents ------------------------------------------------

    async def create_driver_document(self, **values: Any) -> DriverDocument:
        document = DriverDocument(**values)
        self.session.add(document)
        await self.session.flush()
        return document

    async def get_driver_document(self, document_id: uuid.UUID) -> DriverDocument | None:
        stmt = select(DriverDocument).where(DriverDocument.id == document_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_driver_documents(self, driver_profile_id: uuid.UUID) -> Sequence[DriverDocument]:
        stmt = select(DriverDocument).where(DriverDocument.driver_profile_id == driver_profile_id)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def update_driver_document(
        self, instance: DriverDocument, **values: Any
    ) -> DriverDocument:
        for key, value in values.items():
            setattr(instance, key, value)
        await self.session.flush()
        return instance

    # --- Vehicle Photos --------------------------------------------------

    async def create_vehicle_photo(self, **values: Any) -> VehiclePhoto:
        photo = VehiclePhoto(**values)
        self.session.add(photo)
        await self.session.flush()
        return photo

    async def list_vehicle_photos(self, vehicle_id: uuid.UUID) -> Sequence[VehiclePhoto]:
        stmt = select(VehiclePhoto).where(VehiclePhoto.vehicle_id == vehicle_id)
        result = await self.session.execute(stmt)
        return result.scalars().all()


__all__ = ["VehicleRepository"]
