"""Notification domain ORM model: every message the system generates for
a user, across every channel.

References User by string class name / string FK target only -- no import
of identity.py -- so this file cannot create a circular import with it,
and identity.py is not modified to add a back-collection.

Placed under `infrastructure/database/models/`, not `domain/notification/`,
for the same Dependency Rule reason as every other domain so far.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates
from sqlalchemy.types import JSON

from vtaxi.infrastructure.database.base import Base
from vtaxi.infrastructure.database.enums import (
    NotificationChannel,
    NotificationStatus,
    NotificationType,
)
from vtaxi.infrastructure.database.mixins import TimestampMixin, UUIDMixin
from vtaxi.infrastructure.database.validators import ensure_not_blank

if TYPE_CHECKING:
    from vtaxi.infrastructure.database.models.identity import User

# JSON on every dialect, upgraded to native JSONB on Postgres -- verified to
# compile and create correctly against both SQLite (this project's test
# dialect) and Postgres (this project's production dialect).
_JSON_TYPE = JSON().with_variant(JSONB(), "postgresql")


class Notification(Base, UUIDMixin, TimestampMixin):
    """A message the system generated for a user -- see docs/03-DATABASE-
    DESIGN.md SS2.5 for the original, simpler design this replaces:
    `payload` (JSONB) supersedes `related_entity_type`/`related_entity_id`
    as the "what is this about" reference -- still not a real FK (a
    notification can be about any entity, and Postgres has no polymorphic
    FK, exactly docs/03's original reasoning), just carried as structured
    data instead of a loose (type, id) pair. `notification_type` is new:
    what *kind* of event this is (BOOKING, TRIP, ...), independent of
    `channel` (how it's delivered).

    Nothing here sends anything: `sent_at`/`delivered_at`/`read_at`/
    `failed_at`/`error_message` are just columns for the future Service
    Layer to populate as delivery actually happens.
    """

    __tablename__ = "notifications"
    __table_args__ = (
        Index("ix_notifications_user_id", "user_id"),
        Index("ix_notifications_delivery_status", "delivery_status"),
        Index("ix_notifications_channel", "channel"),
        Index("ix_notifications_created_at", "created_at"),
        CheckConstraint("sent_at IS NULL OR sent_at >= created_at", name="sent_after_created"),
        CheckConstraint(
            "delivered_at IS NULL OR sent_at IS NULL OR delivered_at >= sent_at",
            name="delivered_after_sent",
        ),
        CheckConstraint(
            "read_at IS NULL OR delivered_at IS NULL OR read_at >= delivered_at",
            name="read_after_delivered",
        ),
        CheckConstraint(
            "failed_at IS NULL OR failed_at >= created_at", name="failed_after_created"
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    notification_type: Mapped[NotificationType]
    channel: Mapped[NotificationChannel] = mapped_column(default=NotificationChannel.TELEGRAM)
    title: Mapped[str] = mapped_column(String(150))
    message: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict[str, Any]] = mapped_column(_JSON_TYPE, default=dict)
    delivery_status: Mapped[NotificationStatus] = mapped_column(default=NotificationStatus.PENDING)
    sent_at: Mapped[datetime | None]
    delivered_at: Mapped[datetime | None]
    read_at: Mapped[datetime | None]
    failed_at: Mapped[datetime | None]
    error_message: Mapped[str | None] = mapped_column(Text)

    user: Mapped["User"] = relationship("User", foreign_keys=[user_id], lazy="selectin")

    @validates("title")
    def _validate_title(self, key: str, value: str) -> str:
        return ensure_not_blank(value, field_name=key)


__all__ = ["Notification"]
