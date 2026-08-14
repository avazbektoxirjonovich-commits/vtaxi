"""Audit domain ORM model: an immutable security/business event log.

References User by string class name / string FK target only -- no import
of identity.py -- so this file cannot create a circular import with it,
and identity.py is not modified to add a back-collection.

Placed under `infrastructure/database/models/`, not `domain/audit_log/`,
for the same Dependency Rule reason as every other domain so far.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import ForeignKey, Index, String, event, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from vtaxi.infrastructure.database.base import Base
from vtaxi.infrastructure.database.enums import AuditAction
from vtaxi.infrastructure.database.mixins import UUIDMixin

if TYPE_CHECKING:
    from vtaxi.infrastructure.database.models.identity import User

# Same cross-dialect JSON/JSONB technique as notification.py.
_JSON_TYPE = JSON().with_variant(JSONB(), "postgresql")


class AuditLog(Base, UUIDMixin):
    """An immutable security/business audit event. See docs/03-DATABASE-
    DESIGN.md SS2.5 for the original `audit_log_entries` design this
    supersedes: that table was admin-actions-only (`admin_id` required,
    FK to `admin_profiles`); this one is broader -- `actor_user_id` is
    nullable (any user, or the system, not just admins) and gains
    `target_user_id`, paired with a generic verb (`AuditAction` -- also
    replaced, see enums/audit.py) plus `entity_type`/`entity_id` on the
    row to say *what* happened, instead of an ever-growing list of
    per-entity action names.

    `entity_type`/`entity_id` are required (not nullable): even a LOGIN/
    LOGOUT event has a natural entity -- the user's own account
    (entity_type="user", entity_id=actor_user_id).

    Python attribute named `event_metadata`, not `metadata`: every
    declarative class already has a `.metadata` attribute (the
    `MetaData` registry via `Base`), so a column literally named
    `metadata` would collide with it. `mapped_column("metadata", ...)`
    keeps the actual database column named `metadata` as asked, while the
    Python-side attribute is named to avoid the clash.

    No `TimestampMixin`: only `created_at` was asked for, and this row
    must never change after insert (see the `before_update` guard below) --
    an `updated_at` would be actively misleading on a row that can't be
    updated.
    """

    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_actor_user_id", "actor_user_id"),
        Index("ix_audit_logs_target_user_id", "target_user_id"),
        Index("ix_audit_logs_entity_type", "entity_type"),
        Index("ix_audit_logs_entity_id", "entity_id"),
        Index("ix_audit_logs_action", "action"),
        Index("ix_audit_logs_created_at", "created_at"),
    )

    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    target_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    entity_type: Mapped[str] = mapped_column(String(50))
    entity_id: Mapped[uuid.UUID]
    action: Mapped[AuditAction]
    ip_address: Mapped[str | None] = mapped_column(String(45))  # IPv6-safe length
    user_agent: Mapped[str | None] = mapped_column(String(300))
    event_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", _JSON_TYPE, default=dict)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    actor: Mapped["User | None"] = relationship(
        "User", foreign_keys=[actor_user_id], lazy="selectin"
    )
    target: Mapped["User | None"] = relationship(
        "User", foreign_keys=[target_user_id], lazy="selectin"
    )


@event.listens_for(AuditLog, "before_update")
def _prevent_audit_log_update(mapper: Any, connection: Any, target: AuditLog) -> None:
    """Enforce immutability at the ORM level: an `AuditLog` row may be
    inserted, never updated. This fires for every ORM-mediated UPDATE
    regardless of which service or repository eventually triggers it.
    """
    raise RuntimeError("AuditLog records are immutable and must never be updated after creation")


__all__ = ["AuditLog"]
