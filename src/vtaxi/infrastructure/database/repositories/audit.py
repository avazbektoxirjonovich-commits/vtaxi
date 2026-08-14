"""Repository for the Audit domain. Bound model is `AuditLog`.

`update()`/`delete()` are overridden to refuse immediately rather than
inherit the generic engine's behavior: `AuditLog` is immutable by design
(see models/audit.py's `before_update` guard) -- failing at the
repository call site, before a flush is even attempted, is a clearer
error than waiting for the ORM event to reject it.
"""

import uuid
from collections.abc import Sequence
from typing import Any

from vtaxi.infrastructure.database.models.audit import AuditLog
from vtaxi.infrastructure.database.repositories.base import BaseRepository


class AuditRepository(BaseRepository[AuditLog]):
    model = AuditLog

    async def list_by_entity(self, entity_type: str, entity_id: uuid.UUID) -> Sequence[AuditLog]:
        return await self.get_many(
            AuditLog.entity_type == entity_type,
            AuditLog.entity_id == entity_id,
            order_by=(AuditLog.created_at.desc(),),
        )

    async def list_by_actor(self, actor_user_id: uuid.UUID) -> Sequence[AuditLog]:
        return await self.get_many(
            AuditLog.actor_user_id == actor_user_id,
            order_by=(AuditLog.created_at.desc(),),
        )

    async def update(self, instance: AuditLog, **values: Any) -> AuditLog:
        raise NotImplementedError("AuditLog records are immutable and must never be updated")

    async def delete(self, instance: AuditLog) -> None:
        raise NotImplementedError("AuditLog records are immutable and must never be deleted")


__all__ = ["AuditRepository"]
