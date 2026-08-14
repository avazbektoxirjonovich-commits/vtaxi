"""Complaint domain ORM model: passenger/driver moderation intake.

References User, AdminProfile, Trip, and Booking by string class name /
string FK target only -- no import of those modules -- so this file
cannot create a circular import with them, and none of them is modified
to add a back-collection.

Placed under `infrastructure/database/models/`, not `domain/complaint/`,
for the same Dependency Rule reason as every other domain so far.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from vtaxi.infrastructure.database.base import Base
from vtaxi.infrastructure.database.enums import (
    ComplaintReason,
    ComplaintResolutionAction,
    ComplaintStatus,
)
from vtaxi.infrastructure.database.mixins import TimestampMixin, UUIDMixin
from vtaxi.infrastructure.database.validators import ensure_not_blank

if TYPE_CHECKING:
    from vtaxi.infrastructure.database.models.booking import Booking
    from vtaxi.infrastructure.database.models.identity import AdminProfile, User
    from vtaxi.infrastructure.database.models.trip import Trip


class Complaint(Base, UUIDMixin, TimestampMixin):
    """Moderation intake -- see docs/01-SOFTWARE-ARCHITECTURE.md SS14.6 and
    docs/03-DATABASE-DESIGN.md SS2.5. `complaint_type` is this round's name
    for docs/03's `reason` column (same `ComplaintReason` enum);
    `evidence_url` replaces docs/03's separate `complaint_evidence` table
    with a single nullable string, matching this round's explicit field
    list -- multiple attachments, if ever needed, would be an additive
    table later, not built now.

    `resolution_action` is kept from docs/03 though not restated in this
    round's field list: it's load-bearing (the only path that flips
    `availability_status`/`passenger_status` to BANNED, per docs/01
    SS14.6). `reporter_role` (docs/03) is dropped -- derivable via a join
    to `users.role` when actually needed, not worth a column this round
    didn't ask for.

    "Complaint cannot reference unrelated trip and booking": verifying a
    given `booking_id` actually belongs to the given `trip_id` requires
    checking `TripPassenger`, a different table entirely -- a cross-table
    invariant no single-table CHECK constraint can express here (same
    limitation noted on the Trip domain's models) -- left for the future
    Service Layer. Only "at least one of trip/booking is set" is enforced
    below, since that's a same-row check.
    """

    __tablename__ = "complaints"
    __table_args__ = (
        Index("ix_complaints_target_user_id", "target_user_id"),
        Index("ix_complaints_reporter_user_id", "reporter_user_id"),
        Index("ix_complaints_complaint_status", "complaint_status"),
        Index("ix_complaints_resolved_by_admin_id", "resolved_by_admin_id"),
        Index("ix_complaints_created_at", "created_at"),
        Index("ix_complaints_trip_id", "trip_id"),
        Index("ix_complaints_booking_id", "booking_id"),
        CheckConstraint(
            "trip_id IS NOT NULL OR booking_id IS NOT NULL",
            name="has_trip_or_booking",
        ),
    )

    reporter_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    target_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    trip_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("trips.id", ondelete="SET NULL"))
    booking_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("bookings.id", ondelete="SET NULL")
    )
    complaint_type: Mapped[ComplaintReason]
    title: Mapped[str] = mapped_column(String(150))
    description: Mapped[str] = mapped_column(Text)
    evidence_url: Mapped[str | None] = mapped_column(String(500))
    complaint_status: Mapped[ComplaintStatus] = mapped_column(default=ComplaintStatus.OPEN)
    resolution_action: Mapped[ComplaintResolutionAction] = mapped_column(
        default=ComplaintResolutionAction.NONE
    )
    resolved_by_admin_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("admin_profiles.id", ondelete="SET NULL")
    )
    resolved_at: Mapped[datetime | None]
    resolution_note: Mapped[str | None] = mapped_column(Text)

    reporter: Mapped["User"] = relationship(
        "User", foreign_keys=[reporter_user_id], lazy="selectin"
    )
    target: Mapped["User"] = relationship("User", foreign_keys=[target_user_id], lazy="selectin")
    trip: Mapped["Trip | None"] = relationship("Trip", foreign_keys=[trip_id], lazy="selectin")
    booking: Mapped["Booking | None"] = relationship(
        "Booking", foreign_keys=[booking_id], lazy="selectin"
    )
    resolved_by: Mapped["AdminProfile | None"] = relationship(
        "AdminProfile", foreign_keys=[resolved_by_admin_id], lazy="selectin"
    )

    @validates("title", "description")
    def _validate_not_blank(self, key: str, value: str) -> str:
        return ensure_not_blank(value, field_name=key)


__all__ = ["Complaint"]
