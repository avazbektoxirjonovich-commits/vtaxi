"""Booking domain ORM models: a passenger's reservation request against an
Advertisement, and its status-transition history.

A Booking is a *request* -- it does not mean the passenger has joined the
trip. Driver acceptance is required, and this row never touches
`Advertisement`'s own seat columns: no relationship-mutation, no event
listener, no validator here writes to `Advertisement`. That reconciliation
is entirely the future Service Layer's job (see docs/01-SOFTWARE-
ARCHITECTURE.md SS6 for the atomic seat-accounting mechanics this model
deliberately does not implement).

References PassengerProfile, Advertisement, and User by string class name
/ string FK target only -- no import of identity.py or advertisement.py --
so this module cannot create a circular import with them, and neither
file is modified to add a back-collection (Booking stays one-directional
toward both, the same discipline the Advertisement domain used toward
Identity/Vehicle/Geography).

Placed under `infrastructure/database/models/`, not `domain/booking/`, for
the same Dependency Rule reason as every other domain so far.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from vtaxi.infrastructure.database.base import Base
from vtaxi.infrastructure.database.enums import BookingStatus
from vtaxi.infrastructure.database.mixins import TimestampMixin, UUIDMixin
from vtaxi.infrastructure.database.validators import ensure_positive

if TYPE_CHECKING:
    from vtaxi.infrastructure.database.models.advertisement import Advertisement
    from vtaxi.infrastructure.database.models.identity import PassengerProfile, User


class Booking(Base, UUIDMixin, TimestampMixin):
    """A passenger's reservation request against an `Advertisement`. See
    docs/01-SOFTWARE-ARCHITECTURE.md SS6 and docs/03-DATABASE-DESIGN.md
    SS2.4 for the original two-phase seat model this extends: `PENDING`
    does not hold a seat; a seat is only held once the future Service
    Layer moves the booking to `RESERVED`, bounded by `reserved_until`.
    `booking_status` now covers PENDING/RESERVED/ACCEPTED/REJECTED/
    CANCELLED/EXPIRED/COMPLETED -- see enums/booking.py.

    No `trip_id` yet: that FK arrives with the Trip domain (next); adding
    it later is purely additive, no rework needed here.

    No `SoftDeleteMixin`: like `Advertisement`, `booking_status` already
    covers "is this gone" (REJECTED/CANCELLED/EXPIRED) -- docs/03 SS0.3.

    Optimistic locking (future, not implemented here): once the Service
    Layer needs to guard a driver's ACCEPT against a passenger's
    concurrent CANCEL on the same row, add
    `version_id: Mapped[int] = mapped_column(default=0)` plus
    `__mapper_args__ = {"version_id_col": version_id}` to this class --
    SQLAlchemy then rejects a stale UPDATE with `StaleDataError`
    automatically. This comment is the marker for where that goes.
    """

    __tablename__ = "bookings"
    __table_args__ = (
        Index("ix_bookings_passenger_profile_id", "passenger_profile_id"),
        Index("ix_bookings_advertisement_id", "advertisement_id"),
        Index("ix_bookings_booking_status", "booking_status"),
        Index("ix_bookings_reserved_until", "reserved_until"),
        Index("ix_bookings_advertisement_status", "advertisement_id", "booking_status"),
        Index("ix_bookings_passenger_status", "passenger_profile_id", "booking_status"),
        Index("ix_bookings_reserved_until_status", "reserved_until", "booking_status"),
        # Partial unique index (Postgres only -- same pattern as the
        # Geography/Vehicle domains' partial indexes): "only one ACTIVE
        # booking per passenger per advertisement" means active statuses,
        # not all rows -- a passenger may still re-book after a CANCELLED/
        # REJECTED/EXPIRED attempt. On SQLite (this project's test dialect)
        # `postgresql_where` is simply not applied, so this becomes a full
        # unique index there -- fine for compiled-DDL inspection, but not
        # something to exercise a re-booking-after-cancellation test against
        # on SQLite.
        Index(
            "uq_bookings_passenger_advertisement_active",
            "passenger_profile_id",
            "advertisement_id",
            unique=True,
            postgresql_where=text("booking_status IN ('PENDING', 'RESERVED', 'ACCEPTED')"),
        ),
        CheckConstraint("requested_seats > 0", name="requested_seats_positive"),
        CheckConstraint("requested_seats <= 10", name="requested_seats_max"),
        CheckConstraint(
            "accepted_at IS NULL OR accepted_at >= created_at", name="accepted_after_created"
        ),
        CheckConstraint(
            "completed_at IS NULL OR accepted_at IS NULL OR completed_at >= accepted_at",
            name="completed_after_accepted",
        ),
        CheckConstraint(
            "reserved_until IS NULL OR reserved_until >= created_at",
            name="reserved_until_after_created",
        ),
    )

    advertisement_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("advertisements.id", ondelete="RESTRICT")
    )
    passenger_profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("passenger_profiles.id", ondelete="RESTRICT")
    )
    requested_seats: Mapped[int]
    booking_status: Mapped[BookingStatus] = mapped_column(default=BookingStatus.PENDING)
    passenger_comment: Mapped[str | None] = mapped_column(Text)
    driver_comment: Mapped[str | None] = mapped_column(Text)
    reserved_until: Mapped[datetime | None]
    accepted_at: Mapped[datetime | None]
    rejected_at: Mapped[datetime | None]
    cancelled_at: Mapped[datetime | None]
    completed_at: Mapped[datetime | None]

    advertisement: Mapped["Advertisement"] = relationship(
        "Advertisement", foreign_keys=[advertisement_id], lazy="selectin"
    )
    passenger_profile: Mapped["PassengerProfile"] = relationship(
        "PassengerProfile", foreign_keys=[passenger_profile_id], lazy="selectin"
    )
    status_history: Mapped[list["BookingStatusHistory"]] = relationship(
        back_populates="booking",
        foreign_keys="BookingStatusHistory.booking_id",
        lazy="selectin",
    )

    @validates("requested_seats")
    def _validate_requested_seats(self, key: str, value: int) -> int:
        return int(ensure_positive(value, field_name=key))


class BookingStatusHistory(Base, UUIDMixin):
    """Append-only log of every `Booking.booking_status` transition,
    regardless of actor -- including system-triggered ones (e.g. an
    automatic EXPIRED once `reserved_until` passes), which is why
    `changed_by_user_id` is nullable. Same pattern as
    `AdvertisementStatusHistory` (previous step) -- still not extracted
    into a shared mixin; that becomes worthwhile once Trip's status
    history (next) makes it a third real duplicate, not before.

    No `TimestampMixin`: `changed_at` is this row's one meaningful
    timestamp; a log row is never updated after insert.
    """

    __tablename__ = "booking_status_history"
    __table_args__ = (
        Index("ix_booking_status_history_booking_id", "booking_id"),
        Index(
            "ix_booking_status_history_booking_changed",
            "booking_id",
            "changed_at",
        ),
    )

    booking_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("bookings.id", ondelete="CASCADE"))
    previous_status: Mapped[BookingStatus | None]
    new_status: Mapped[BookingStatus]
    changed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    reason: Mapped[str | None] = mapped_column(Text)
    changed_at: Mapped[datetime] = mapped_column(server_default=func.now())

    booking: Mapped["Booking"] = relationship(
        back_populates="status_history",
        foreign_keys=[booking_id],
        lazy="selectin",
    )
    changed_by: Mapped["User | None"] = relationship(
        "User", foreign_keys=[changed_by_user_id], lazy="selectin"
    )


__all__ = ["Booking", "BookingStatusHistory"]
