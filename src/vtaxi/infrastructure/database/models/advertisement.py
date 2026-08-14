"""Advertisement domain ORM models: a driver's published offer, and its
status-transition history.

Advertisement is NOT a Trip: it is the listing a driver publishes; a Trip
(a later domain) is the realized journey created once accepted bookings
depart. See docs/01-SOFTWARE-ARCHITECTURE.md SS14.1.

References DriverProfile, Vehicle, Direction, AdministrativeArea, and User
by string class name / string FK target only -- no import of identity.py,
vehicle.py, or geography.py -- so this module cannot create a circular
import with them, and none of those files is modified to add this
domain's models (relationships from this side are one-directional; no
back-populated collections were added to those other domains).

Placed under `infrastructure/database/models/`, not `domain/advertisement/`,
for the same Dependency Rule reason as every other domain so far.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from vtaxi.infrastructure.database.base import Base
from vtaxi.infrastructure.database.enums import AdvertisementStatus
from vtaxi.infrastructure.database.mixins import TimestampMixin, UUIDMixin
from vtaxi.infrastructure.database.validators import ensure_non_negative, ensure_positive

if TYPE_CHECKING:
    from vtaxi.infrastructure.database.models.geography import AdministrativeArea, Direction
    from vtaxi.infrastructure.database.models.identity import DriverProfile, User
    from vtaxi.infrastructure.database.models.vehicle import Vehicle


class Advertisement(Base, UUIDMixin, TimestampMixin):
    """A driver's published offer on a supported Direction. See
    docs/01-SOFTWARE-ARCHITECTURE.md SS14.1 and docs/03-DATABASE-DESIGN.md
    SS2.4 -- `advertisement_status` stays DRAFT/ACTIVE/FULL/CLOSED/
    CANCELLED/EXPIRED; this model does not gain STARTED/COMPLETED values.

    `started_at`/`completed_at` are denormalized mirrors of the (future)
    Trip's own lifecycle timestamps, kept here purely so a list view of
    advertisements doesn't need to join to a not-yet-built `trips` table --
    not a new state machine, and nothing in this model sets them; that's
    the future Service Layer's job (see "no business logic" note below).

    No `SoftDeleteMixin`: like `bookings`/`trips`, this table's own status
    enum already covers "is this gone" (CANCELLED/EXPIRED/CLOSED) -- see
    docs/03-DATABASE-DESIGN.md SS0.3.

    Seat accounting (`total_seats`/`available_seats`/`reserved_seats`) is
    the two-phase reservation from docs/03-DATABASE-DESIGN.md SS2.4: the
    columns and their CHECK-constraint invariants live here; the atomic
    conditional UPDATE that actually moves seats between buckets is a
    future Service Layer / repository concern -- nothing here computes or
    defaults seat counts automatically.
    """

    __tablename__ = "advertisements"
    __table_args__ = (
        Index("ix_advertisements_driver_profile_id", "driver_profile_id"),
        Index("ix_advertisements_direction_id", "direction_id"),
        Index("ix_advertisements_advertisement_status", "advertisement_status"),
        Index("ix_advertisements_departure_time", "departure_time"),
        Index("ix_advertisements_expires_at", "expires_at"),
        Index("ix_advertisements_direction_status", "direction_id", "advertisement_status"),
        Index("ix_advertisements_direction_departure", "direction_id", "departure_time"),
        Index("ix_advertisements_driver_status", "driver_profile_id", "advertisement_status"),
        Index("ix_advertisements_priority_status", "is_priority", "advertisement_status"),
        CheckConstraint("total_seats > 0", name="total_seats_positive"),
        CheckConstraint("available_seats >= 0", name="available_seats_non_negative"),
        CheckConstraint("reserved_seats >= 0", name="reserved_seats_non_negative"),
        CheckConstraint("available_seats <= total_seats", name="available_seats_within_total"),
        CheckConstraint("reserved_seats <= total_seats", name="reserved_seats_within_total"),
        CheckConstraint(
            "available_seats + reserved_seats <= total_seats", name="seats_within_total"
        ),
        CheckConstraint(
            "pickup_area_id != destination_area_id", name="pickup_destination_distinct"
        ),
        CheckConstraint("departure_time < expires_at", name="departure_before_expiry"),
        CheckConstraint("price >= 0", name="price_non_negative"),
    )

    driver_profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("driver_profiles.id", ondelete="RESTRICT")
    )
    vehicle_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("vehicles.id", ondelete="RESTRICT"))
    direction_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("directions.id", ondelete="RESTRICT")
    )
    pickup_area_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("administrative_areas.id", ondelete="RESTRICT")
    )
    destination_area_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("administrative_areas.id", ondelete="RESTRICT")
    )
    # Numeric, not float, matching the Geography domain's precedent -- keeps
    # the door open for a future PostGIS migration without a type change.
    current_latitude: Mapped[Decimal] = mapped_column(Numeric(9, 6))
    current_longitude: Mapped[Decimal] = mapped_column(Numeric(9, 6))
    departure_time: Mapped[datetime]
    estimated_arrival_time: Mapped[datetime | None]
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    currency_code: Mapped[str] = mapped_column(String(3), default="UZS")
    total_seats: Mapped[int]
    reserved_seats: Mapped[int] = mapped_column(default=0)
    available_seats: Mapped[int]
    advertisement_status: Mapped[AdvertisementStatus] = mapped_column(
        default=AdvertisementStatus.DRAFT
    )
    # Required (not nullable), unlike docs/03's original design: the
    # `departure_time < expires_at` CHECK constraint below is only a real
    # invariant if this column can't be NULL (SQL CHECK treats a NULL
    # comparison as passing, not failing).
    expires_at: Mapped[datetime]
    notes: Mapped[str | None] = mapped_column(Text)
    is_priority: Mapped[bool] = mapped_column(default=False)
    published_at: Mapped[datetime | None]
    started_at: Mapped[datetime | None]
    completed_at: Mapped[datetime | None]

    driver_profile: Mapped["DriverProfile"] = relationship(
        "DriverProfile", foreign_keys=[driver_profile_id], lazy="selectin"
    )
    vehicle: Mapped["Vehicle"] = relationship("Vehicle", foreign_keys=[vehicle_id], lazy="selectin")
    direction: Mapped["Direction"] = relationship(
        "Direction", foreign_keys=[direction_id], lazy="selectin"
    )
    pickup_area: Mapped["AdministrativeArea"] = relationship(
        "AdministrativeArea", foreign_keys=[pickup_area_id], lazy="selectin"
    )
    destination_area: Mapped["AdministrativeArea"] = relationship(
        "AdministrativeArea", foreign_keys=[destination_area_id], lazy="selectin"
    )
    status_history: Mapped[list["AdvertisementStatusHistory"]] = relationship(
        back_populates="advertisement",
        foreign_keys="AdvertisementStatusHistory.advertisement_id",
        lazy="selectin",
    )

    @validates("total_seats")
    def _validate_total_seats(self, key: str, value: int) -> int:
        return int(ensure_positive(value, field_name=key))

    @validates("available_seats", "reserved_seats")
    def _validate_seat_counts(self, key: str, value: int) -> int:
        return int(ensure_non_negative(value, field_name=key))

    @validates("price")
    def _validate_price(self, key: str, value: Decimal) -> Decimal:
        return ensure_non_negative(value, field_name=key)  # type: ignore[return-value]


class AdvertisementStatusHistory(Base, UUIDMixin):
    """Append-only log of every `Advertisement.advertisement_status`
    transition, regardless of actor -- including system-triggered ones
    (auto-FULL, auto-expiry), which is why `changed_by_user_id` is
    nullable. Same shape as the five status-history tables planned in
    docs/03-DATABASE-DESIGN.md SS2.6, with this round's field names
    (`previous_status`/`new_status`/`changed_at` vs. that document's
    `from_status`/`to_status`/`occurred_at`).

    Not extracted into a shared mixin yet: this is the first of five
    planned status-history tables to actually be built. A mixin now would
    be designing against a plan, not real duplication -- worth doing once
    a second one (Booking's, next) exists.

    No `TimestampMixin`: `changed_at` already is this row's one meaningful
    timestamp; a log row is never updated after insert, so a generic
    `updated_at` would be dead weight.
    """

    __tablename__ = "advertisement_status_history"
    __table_args__ = (
        Index("ix_advertisement_status_history_advertisement_id", "advertisement_id"),
        Index(
            "ix_advertisement_status_history_advertisement_changed",
            "advertisement_id",
            "changed_at",
        ),
    )

    advertisement_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("advertisements.id", ondelete="CASCADE")
    )
    previous_status: Mapped[AdvertisementStatus | None]
    new_status: Mapped[AdvertisementStatus]
    changed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    reason: Mapped[str | None] = mapped_column(Text)
    changed_at: Mapped[datetime] = mapped_column(server_default=func.now())

    advertisement: Mapped["Advertisement"] = relationship(
        back_populates="status_history",
        foreign_keys=[advertisement_id],
        lazy="selectin",
    )
    changed_by: Mapped["User | None"] = relationship(
        "User", foreign_keys=[changed_by_user_id], lazy="selectin"
    )


__all__ = ["Advertisement", "AdvertisementStatusHistory"]
