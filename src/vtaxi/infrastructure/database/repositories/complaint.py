"""Repository for the Complaint domain. Bound model is `Complaint`.

`list_by_reporter_user_id`/`list_by_trip_id`/`list_by_booking_id` added
in Step 8.7 for `ComplaintService.list_user_complaints()`/
`list_trip_complaints()`/`list_booking_complaints()`. `list_user_complaints()`
is deliberately reporter-scoped ("complaints this user filed"), not
target-scoped -- the pre-existing `list_by_target_user_id` (complaints
*about* a user, an admin/moderation view) is left as-is and simply not
called by this round's service, matching "do not modify unrelated
repositories."
"""

import uuid
from collections.abc import Sequence

from vtaxi.infrastructure.database.enums import ComplaintStatus
from vtaxi.infrastructure.database.models.complaint import Complaint
from vtaxi.infrastructure.database.repositories.base import BaseRepository


class ComplaintRepository(BaseRepository[Complaint]):
    model = Complaint

    async def list_by_status(self, status: ComplaintStatus) -> Sequence[Complaint]:
        return await self.get_many(Complaint.complaint_status == status)

    async def list_by_target_user_id(self, target_user_id: uuid.UUID) -> Sequence[Complaint]:
        return await self.get_many(Complaint.target_user_id == target_user_id)

    async def list_by_reporter_user_id(self, reporter_user_id: uuid.UUID) -> Sequence[Complaint]:
        return await self.get_many(Complaint.reporter_user_id == reporter_user_id)

    async def list_by_trip_id(self, trip_id: uuid.UUID) -> Sequence[Complaint]:
        return await self.get_many(Complaint.trip_id == trip_id)

    async def list_by_booking_id(self, booking_id: uuid.UUID) -> Sequence[Complaint]:
        return await self.get_many(Complaint.booking_id == booking_id)


__all__ = ["ComplaintRepository"]
