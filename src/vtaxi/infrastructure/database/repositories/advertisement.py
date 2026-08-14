"""Repository for the Advertisement domain. Bound model is `Advertisement`.

`*_status_history` tables have no dedicated repository in this round --
only the 12 named repositories were asked for; a future step can add one
per status-history table the same way, once a service actually needs to
write to it.

`list_all_active`/`list_by_direction`/`list_expiring` added in Step 8.4 for
`AdvertisementService`'s Queries group (`get_active_advertisements()`,
`get_direction_advertisements()`, `get_expired_advertisements()`):
`list_active_by_direction` (this file, pre-existing) always filters by a
specific `direction_id`, so it cannot serve an unfiltered "every active
advertisement" or "every advertisement on this direction regardless of
status" query; `list_expiring` is the not-yet-built expiry sweep's own
candidate query (docs/03-DATABASE-DESIGN.md SS2.4 ADR-009), distinct from
"already-EXPIRED" rows a plain status filter would return.
"""

import uuid
from collections.abc import Sequence
from datetime import datetime

from vtaxi.infrastructure.database.enums import AdvertisementStatus
from vtaxi.infrastructure.database.models.advertisement import Advertisement
from vtaxi.infrastructure.database.repositories.base import BaseRepository


class AdvertisementRepository(BaseRepository[Advertisement]):
    model = Advertisement

    async def list_active_by_direction(
        self, direction_id: uuid.UUID, *, before: datetime | None = None
    ) -> Sequence[Advertisement]:
        """The matching hot path: same shape as the
        `(direction_id, advertisement_status, departure_time)` composite
        index docs/03-DATABASE-DESIGN.md SS2.4 calls "the single most
        important index in the schema." Ranking/filtering beyond this
        (distance, rating, Queue Engine fairness) is the Matching Engine's
        job, not this repository's.
        """
        where = [
            Advertisement.direction_id == direction_id,
            Advertisement.advertisement_status == AdvertisementStatus.ACTIVE,
        ]
        if before is not None:
            where.append(Advertisement.departure_time <= before)
        return await self.get_many(*where, order_by=(Advertisement.departure_time,))

    async def list_by_driver_profile_id(
        self, driver_profile_id: uuid.UUID
    ) -> Sequence[Advertisement]:
        return await self.get_many(Advertisement.driver_profile_id == driver_profile_id)

    async def list_all_active(self) -> Sequence[Advertisement]:
        return await self.get_many(
            Advertisement.advertisement_status == AdvertisementStatus.ACTIVE,
            order_by=(Advertisement.departure_time,),
        )

    async def list_by_direction(self, direction_id: uuid.UUID) -> Sequence[Advertisement]:
        return await self.get_many(
            Advertisement.direction_id == direction_id,
            order_by=(Advertisement.departure_time,),
        )

    async def list_expiring(self, *, before: datetime) -> Sequence[Advertisement]:
        """Candidates for the (not-yet-built) expiry sweep worker: not yet
        terminal -- `ACTIVE`/`FULL` only, matching the partial index
        docs/03-DATABASE-DESIGN.md SS2.4/SS9 describes for this exact
        query -- and past `expires_at`.
        """
        return await self.get_many(
            Advertisement.advertisement_status.in_(
                (AdvertisementStatus.ACTIVE, AdvertisementStatus.FULL)
            ),
            Advertisement.expires_at <= before,
            order_by=(Advertisement.expires_at,),
        )


__all__ = ["AdvertisementRepository"]
