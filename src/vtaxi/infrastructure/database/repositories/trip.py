"""Repository for the Trip domain. Bound model is `Trip`.

`TripStatusHistory` still has no dedicated repository (unused so far).
`TripPassenger` -- the canonical Trip/Booking join row (see models/trip.py's
docstring) -- gets its CRUD methods added directly here in Step 8.6, same
reasoning as `VehicleRepository`'s Step 8.3 extension for
`VehicleDocument`/`DriverDocument`/`VehiclePhoto`: this repository is
bound to `Trip`, so its inherited `create()`/`update()` cannot persist a
`TripPassenger`, and `TripService` has no other way to without SQLAlchemy
code of its own. `delete_trip_passenger` is a real hard delete (no
`SoftDeleteMixin` on `TripPassenger`), used only by `remove_passenger()`
while a passenger is still `WAITING` and the trip hasn't started.

`list_by_passenger_profile_id` is this repository's own first cross-model
join (`TripPassenger`, same layer, same reasoning as
`BookingRepository.list_by_driver_profile_id` in Step 8.5): `Trip` has no
passenger column of its own, so finding "every trip this passenger has
ridden" requires joining to `trip_passengers`.
"""

import uuid
from collections.abc import Sequence
from typing import Any

from sqlalchemy import select

from vtaxi.infrastructure.database.enums import TripStatus
from vtaxi.infrastructure.database.models.trip import Trip, TripPassenger
from vtaxi.infrastructure.database.repositories.base import BaseRepository

_ACTIVE_TRIP_STATUSES = (
    TripStatus.SCHEDULED,
    TripStatus.READY,
    TripStatus.STARTED,
    TripStatus.IN_PROGRESS,
)


class TripRepository(BaseRepository[Trip]):
    model = Trip

    async def get_by_advertisement_id(self, advertisement_id: uuid.UUID) -> Trip | None:
        return await self.get_one(Trip.advertisement_id == advertisement_id)

    async def list_by_driver_profile_id(self, driver_profile_id: uuid.UUID) -> Sequence[Trip]:
        return await self.get_many(Trip.driver_profile_id == driver_profile_id)

    async def list_by_passenger_profile_id(self, passenger_profile_id: uuid.UUID) -> Sequence[Trip]:
        stmt = (
            select(Trip)
            .join(TripPassenger, TripPassenger.trip_id == Trip.id)
            .where(TripPassenger.passenger_profile_id == passenger_profile_id)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def list_active(self) -> Sequence[Trip]:
        return await self.get_many(Trip.trip_status.in_(_ACTIVE_TRIP_STATUSES))

    async def list_completed(self) -> Sequence[Trip]:
        return await self.get_many(Trip.trip_status == TripStatus.COMPLETED)

    async def create_trip_passenger(self, **values: Any) -> TripPassenger:
        trip_passenger = TripPassenger(**values)
        self.session.add(trip_passenger)
        await self.session.flush()
        return trip_passenger

    async def find_trip_passenger(
        self, trip_id: uuid.UUID, booking_id: uuid.UUID
    ) -> TripPassenger | None:
        stmt = select(TripPassenger).where(
            TripPassenger.trip_id == trip_id, TripPassenger.booking_id == booking_id
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_trip_passengers(self, trip_id: uuid.UUID) -> Sequence[TripPassenger]:
        stmt = select(TripPassenger).where(TripPassenger.trip_id == trip_id)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def update_trip_passenger(self, instance: TripPassenger, **values: Any) -> TripPassenger:
        for key, value in values.items():
            setattr(instance, key, value)
        await self.session.flush()
        return instance

    async def delete_trip_passenger(self, instance: TripPassenger) -> None:
        await self.session.delete(instance)
        await self.session.flush()


__all__ = ["TripRepository"]
