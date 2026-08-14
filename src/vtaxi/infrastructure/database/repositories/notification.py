"""Repository for the Notification domain. Bound model is `Notification`.

`mark_as_read` only sets `read_at`/`delivery_status` on a row already
given to it -- it doesn't decide when a message was read or send
anything; that's the future Service Layer's job (docs/01-SOFTWARE-
ARCHITECTURE.md SS7.5, `AbstractNotifier`).
"""

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

from vtaxi.infrastructure.database.enums import NotificationStatus
from vtaxi.infrastructure.database.models.notification import Notification
from vtaxi.infrastructure.database.repositories.base import BaseRepository


class NotificationRepository(BaseRepository[Notification]):
    model = Notification

    async def list_unread_by_user(self, user_id: uuid.UUID) -> Sequence[Notification]:
        return await self.get_many(
            Notification.user_id == user_id,
            Notification.read_at.is_(None),
            order_by=(Notification.created_at.desc(),),
        )

    async def mark_as_read(self, instance: Notification) -> Notification:
        return await self.update(
            instance,
            read_at=datetime.now(UTC),
            delivery_status=NotificationStatus.READ,
        )


__all__ = ["NotificationRepository"]
