"""Rating domain ORM model: mutual post-trip feedback between a driver and
a passenger.

References Trip, Booking, DriverProfile, PassengerProfile, and User by
string class name / string FK target only -- no import of those modules --
so this file cannot create a circular import with them, and none of them
is modified to add a back-collection (Rating stays one-directional toward
all of them, the same discipline every domain since Advertisement has
used).

Placed under `infrastructure/database/models/`, not `domain/rating/`, for
the same Dependency Rule reason as every other domain so far.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from vtaxi.infrastructure.database.base import Base
from vtaxi.infrastructure.database.enums import PartyRole
from vtaxi.infrastructure.database.mixins import UUIDMixin
from vtaxi.infrastructure.database.validators import ensure_within_range

if TYPE_CHECKING:
    from vtaxi.infrastructure.database.models.booking import Booking
    from vtaxi.infrastructure.database.models.identity import (
        DriverProfile,
        PassengerProfile,
        User,
    )
    from vtaxi.infrastructure.database.models.trip import Trip


class Rating(Base, UUIDMixin):
    """Mutual post-trip feedback -- see docs/03-DATABASE-DESIGN.md SS2.5.
    `driver_profile_id`/`passenger_profile_id` denormalize the fixed pair
    this rating is about; `rater_user_id`/`target_user_id`/`rater_role`
    say which direction this particular row is (docs/03's original
    `rater_id`/`ratee_id`, renamed here). `trip_id` is new alongside
    docs/03's `booking_id`-only design -- both are kept, since a rating is
    naturally scoped to the realized journey as well as the specific
    reservation.

    No `TimestampMixin`: only `created_at` was asked for, and a rating
    isn't expected to be edited after submission -- same reasoning as the
    `*_status_history` tables' `changed_at`-only shape.

    Nothing here writes to `DriverProfile.average_rating` or
    `PassengerProfile.average_rating` -- recomputing those cached
    aggregates (docs/03 SS4) is the future Service Layer's job, not
    something a model does on insert.
    """

    __tablename__ = "ratings"
    __table_args__ = (
        # One rating per direction per booking -- a passenger rates a
        # driver at most once, and vice versa, for a given booking.
        UniqueConstraint("booking_id", "rater_role"),
        Index("ix_ratings_score", "score"),
        Index("ix_ratings_driver_profile_id", "driver_profile_id"),
        Index("ix_ratings_passenger_profile_id", "passenger_profile_id"),
        Index("ix_ratings_trip_id", "trip_id"),
        Index("ix_ratings_booking_id", "booking_id"),
        Index("ix_ratings_rater_user_id", "rater_user_id"),
        Index("ix_ratings_target_user_id", "target_user_id"),
        Index("ix_ratings_created_at", "created_at"),
        CheckConstraint("score >= 1 AND score <= 5", name="score_within_range"),
    )

    trip_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("trips.id", ondelete="RESTRICT"))
    booking_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("bookings.id", ondelete="RESTRICT"))
    driver_profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("driver_profiles.id", ondelete="RESTRICT")
    )
    passenger_profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("passenger_profiles.id", ondelete="RESTRICT")
    )
    rater_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    target_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    rater_role: Mapped[PartyRole]
    score: Mapped[int]
    comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    trip: Mapped["Trip"] = relationship("Trip", foreign_keys=[trip_id], lazy="selectin")
    booking: Mapped["Booking"] = relationship("Booking", foreign_keys=[booking_id], lazy="selectin")
    driver_profile: Mapped["DriverProfile"] = relationship(
        "DriverProfile", foreign_keys=[driver_profile_id], lazy="selectin"
    )
    passenger_profile: Mapped["PassengerProfile"] = relationship(
        "PassengerProfile", foreign_keys=[passenger_profile_id], lazy="selectin"
    )
    rater: Mapped["User"] = relationship("User", foreign_keys=[rater_user_id], lazy="selectin")
    target: Mapped["User"] = relationship("User", foreign_keys=[target_user_id], lazy="selectin")

    @validates("score")
    def _validate_score(self, key: str, value: int) -> int:
        return int(ensure_within_range(value, minimum=1, maximum=5, field_name=key))


__all__ = ["Rating"]
