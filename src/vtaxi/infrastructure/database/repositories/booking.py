"""Repository for the Booking domain. Bound model is `Booking`.

`list_by_driver_profile_id`/`list_active`/`list_reserved`/`list_expiring`/
`find_active_by_passenger_and_advertisement` added in Step 8.5 for
`BookingService`'s Queries group and its duplicate-active-booking guard.
`list_by_driver_profile_id` is this project's first repository method to
import another domain's model (`Advertisement`) for a join condition --
still a same-layer (infrastructure) import, not a Dependency Rule
violation: `bookings.advertisement_id` has no `driver_profile_id` column
of its own, so finding "every booking against any of this driver's
advertisements" requires joining to `advertisements`.
"""

import uuid
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import select

from vtaxi.infrastructure.database.enums import BookingStatus
from vtaxi.infrastructure.database.models.advertisement import Advertisement
from vtaxi.infrastructure.database.models.booking import Booking
from vtaxi.infrastructure.database.repositories.base import BaseRepository

_ACTIVE_STATUSES = (BookingStatus.PENDING, BookingStatus.RESERVED, BookingStatus.ACCEPTED)


class BookingRepository(BaseRepository[Booking]):
    model = Booking

    async def list_by_advertisement(
        self, advertisement_id: uuid.UUID, *, status: BookingStatus | None = None
    ) -> Sequence[Booking]:
        where = [Booking.advertisement_id == advertisement_id]
        if status is not None:
            where.append(Booking.booking_status == status)
        return await self.get_many(*where)

    async def list_by_passenger_profile_id(
        self, passenger_profile_id: uuid.UUID
    ) -> Sequence[Booking]:
        return await self.get_many(Booking.passenger_profile_id == passenger_profile_id)

    async def list_by_driver_profile_id(self, driver_profile_id: uuid.UUID) -> Sequence[Booking]:
        stmt = (
            select(Booking)
            .join(Advertisement, Booking.advertisement_id == Advertisement.id)
            .where(Advertisement.driver_profile_id == driver_profile_id)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def list_active(self) -> Sequence[Booking]:
        return await self.get_many(Booking.booking_status.in_(_ACTIVE_STATUSES))

    async def list_reserved(self) -> Sequence[Booking]:
        return await self.get_many(Booking.booking_status == BookingStatus.RESERVED)

    async def list_expiring(self, *, before: datetime) -> Sequence[Booking]:
        """Candidates for the (not-yet-built) reservation-timeout sweep --
        `RESERVED` bookings whose `reserved_until` has already passed, not
        rows already sitting in `EXPIRED` status (same "candidates vs.
        already-terminal" distinction as `AdvertisementRepository.
        list_expiring`).
        """
        return await self.get_many(
            Booking.booking_status == BookingStatus.RESERVED,
            Booking.reserved_until.is_not(None),
            Booking.reserved_until <= before,
            order_by=(Booking.reserved_until,),
        )

    async def find_active_by_passenger_and_advertisement(
        self, passenger_profile_id: uuid.UUID, advertisement_id: uuid.UUID
    ) -> Booking | None:
        """Backs the duplicate-active-booking guard: the real partial
        unique index (`uq_bookings_passenger_advertisement_active`) is
        Postgres-only (see models/booking.py's docstring), so this
        SQLite-portable service-level check is what actually enforces
        "no duplicate active booking" during this project's empirical
        verification.
        """
        return await self.get_one(
            Booking.passenger_profile_id == passenger_profile_id,
            Booking.advertisement_id == advertisement_id,
            Booking.booking_status.in_(_ACTIVE_STATUSES),
        )


__all__ = ["BookingRepository"]
