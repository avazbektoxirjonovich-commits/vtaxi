"""Repository for the Rating domain. Bound model is `Rating`.

`list_by_booking_id` added in Step 8.7 for `RatingService.
get_booking_ratings()` -- also reused there (Python-side filtered by
`rater_role`) for the duplicate-rating guard and `can_rate_booking()`,
rather than adding a second, narrower point-lookup method: the real
`UniqueConstraint("booking_id", "rater_role")` already means at most two
rows (one per role) ever come back, so filtering the short list in
Python is not a real cost, and it keeps this repository's surface area
to exactly one new method.
"""

import uuid
from collections.abc import Sequence

from vtaxi.infrastructure.database.models.rating import Rating
from vtaxi.infrastructure.database.repositories.base import BaseRepository


class RatingRepository(BaseRepository[Rating]):
    model = Rating

    async def list_by_driver_profile_id(self, driver_profile_id: uuid.UUID) -> Sequence[Rating]:
        return await self.get_many(Rating.driver_profile_id == driver_profile_id)

    async def list_by_passenger_profile_id(
        self, passenger_profile_id: uuid.UUID
    ) -> Sequence[Rating]:
        return await self.get_many(Rating.passenger_profile_id == passenger_profile_id)

    async def list_by_booking_id(self, booking_id: uuid.UUID) -> Sequence[Rating]:
        return await self.get_many(Rating.booking_id == booking_id)


__all__ = ["RatingRepository"]
