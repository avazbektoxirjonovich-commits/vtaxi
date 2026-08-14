"""Trip domain ORM models: the realized journey, its canonical
passenger-participation records, and its status-transition history.

A Trip is created from an Advertisement once enough bookings are accepted
or the driver manually starts it -- it can exist in SCHEDULED/READY status
before the driver actually departs, which is why `started_at` and the
start/end coordinate columns are all nullable here (unlike docs/03's
original design, where a Trip row only ever existed already-STARTED).

TripPassenger, not a column on Trip, is the canonical link to who is
riding -- passengers are never stored directly on `Trip`. This join row is
what a future multi-stop trip, partial drop-off, or ride-analytics query
actually needs (per-passenger boarding/drop-off timestamps and status),
none of which a bare list of passenger ids could carry. This reverses
docs/03-DATABASE-DESIGN.md SS2.4's original "no trip_passengers table"
call, superseded by this round's explicit instruction; `bookings.trip_id`
was deliberately never added (see booking.py's docstring) precisely so
this table could be the one true link instead of two competing ones.

References Advertisement, DriverProfile, Vehicle, PassengerProfile, User,
and Booking by string class name / string FK target only -- no import of
those modules -- so this file cannot create a circular import with them,
and none of them is modified to add a back-collection (Trip stays
one-directional toward all of them, the same discipline every domain
since Advertisement has used).

Placed under `infrastructure/database/models/`, not `domain/trip/`, for
the same Dependency Rule reason as every other domain so far.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index, Numeric, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from vtaxi.infrastructure.database.base import Base
from vtaxi.infrastructure.database.enums import BoardingStatus, TripStatus
from vtaxi.infrastructure.database.mixins import TimestampMixin, UUIDMixin
from vtaxi.infrastructure.database.validators import ensure_non_negative

if TYPE_CHECKING:
    from vtaxi.infrastructure.database.models.advertisement import Advertisement
    from vtaxi.infrastructure.database.models.booking import Booking
    from vtaxi.infrastructure.database.models.identity import (
        DriverProfile,
        PassengerProfile,
        User,
    )
    from vtaxi.infrastructure.database.models.vehicle import Vehicle


class Trip(Base, UUIDMixin, TimestampMixin):
    """The realized journey created from an `Advertisement`. See
    docs/01-SOFTWARE-ARCHITECTURE.md SS14.1 and docs/03-DATABASE-DESIGN.md
    SS2.4 for the original design; `trip_status` is extended here from
    STARTED/COMPLETED/CANCELLED to SCHEDULED/READY/STARTED/IN_PROGRESS/
    COMPLETED/CANCELLED (see enums/trip.py), since a Trip row can now exist
    before the driver actually departs.

    `vehicle_id` is denormalized from the source Advertisement, same
    reasoning docs/03 gives for `driver_profile_id`: "all trips by vehicle
    X" without a join.

    No `SoftDeleteMixin`: `trip_status` already covers "is this gone"
    (CANCELLED/COMPLETED) -- docs/03 SS0.3.

    Nothing here updates `Booking` or `Advertisement`, computes
    `duration_minutes`/`total_distance_km`, or moves passengers between
    boarding states -- that is entirely the future Service Layer's job.
    """

    __tablename__ = "trips"
    __table_args__ = (
        Index("ix_trips_driver_profile_id", "driver_profile_id"),
        Index("ix_trips_vehicle_id", "vehicle_id"),
        Index("ix_trips_advertisement_id", "advertisement_id"),
        Index("ix_trips_trip_status", "trip_status"),
        Index("ix_trips_started_at", "started_at"),
        Index("ix_trips_ended_at", "ended_at"),
        Index("ix_trips_driver_status", "driver_profile_id", "trip_status"),
        Index("ix_trips_advertisement_status", "advertisement_id", "trip_status"),
        CheckConstraint(
            "ended_at IS NULL OR started_at IS NULL OR ended_at >= started_at",
            name="ended_after_started",
        ),
        CheckConstraint(
            "(start_latitude IS NULL) = (start_longitude IS NULL)",
            name="start_coordinates_paired",
        ),
        CheckConstraint(
            "(end_latitude IS NULL) = (end_longitude IS NULL)",
            name="end_coordinates_paired",
        ),
        CheckConstraint(
            "total_distance_km IS NULL OR total_distance_km >= 0",
            name="total_distance_km_non_negative",
        ),
        CheckConstraint(
            "duration_minutes IS NULL OR duration_minutes >= 0",
            name="duration_minutes_non_negative",
        ),
    )

    # unique=True: one Trip per Advertisement, per docs/01 SS14.1 / docs/03 SS2.4.
    advertisement_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("advertisements.id", ondelete="RESTRICT"), unique=True
    )
    driver_profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("driver_profiles.id", ondelete="RESTRICT")
    )
    vehicle_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("vehicles.id", ondelete="RESTRICT"))
    started_at: Mapped[datetime | None]
    ended_at: Mapped[datetime | None]
    trip_status: Mapped[TripStatus] = mapped_column(default=TripStatus.SCHEDULED)
    start_latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    start_longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    end_latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    end_longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    total_distance_km: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    duration_minutes: Mapped[int | None]
    notes: Mapped[str | None] = mapped_column(Text)

    advertisement: Mapped["Advertisement"] = relationship(
        "Advertisement", foreign_keys=[advertisement_id], lazy="selectin"
    )
    driver_profile: Mapped["DriverProfile"] = relationship(
        "DriverProfile", foreign_keys=[driver_profile_id], lazy="selectin"
    )
    vehicle: Mapped["Vehicle"] = relationship("Vehicle", foreign_keys=[vehicle_id], lazy="selectin")
    passengers: Mapped[list["TripPassenger"]] = relationship(
        back_populates="trip",
        foreign_keys="TripPassenger.trip_id",
        lazy="selectin",
    )
    status_history: Mapped[list["TripStatusHistory"]] = relationship(
        back_populates="trip",
        foreign_keys="TripStatusHistory.trip_id",
        lazy="selectin",
    )

    @validates("total_distance_km")
    def _validate_total_distance_km(self, key: str, value: Decimal | None) -> Decimal | None:
        if value is None:
            return None
        return ensure_non_negative(value, field_name=key)  # type: ignore[return-value]

    @validates("duration_minutes")
    def _validate_duration_minutes(self, key: str, value: int | None) -> int | None:
        if value is None:
            return None
        return int(ensure_non_negative(value, field_name=key))


class TripPassenger(Base, UUIDMixin, TimestampMixin):
    """The canonical association between a `Trip` and a passenger's
    `Booking` (see module docstring) -- never a bare list on `Trip`. Each
    row is one passenger's physical participation in one trip: when they
    boarded, when they were dropped off, and their `boarding_status`,
    independent of the `Booking`'s own reservation status.

    "boarded_at/dropped_off_at >= Trip.started_at" is a cross-table
    invariant and cannot be expressed as a single-table CHECK constraint
    here (Postgres CHECK constraints see only one row of one table); only
    `dropped_off_at >= boarded_at` (same table, same row) is enforced
    below. The cross-table rule belongs to the future Service Layer.
    """

    __tablename__ = "trip_passengers"
    __table_args__ = (
        UniqueConstraint("trip_id", "booking_id"),
        Index("ix_trip_passengers_trip_id", "trip_id"),
        Index("ix_trip_passengers_booking_id", "booking_id"),
        Index("ix_trip_passengers_passenger_profile_id", "passenger_profile_id"),
        Index("ix_trip_passengers_boarding_status", "boarding_status"),
        CheckConstraint(
            "dropped_off_at IS NULL OR boarded_at IS NULL OR dropped_off_at >= boarded_at",
            name="dropped_off_after_boarded",
        ),
    )

    trip_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("trips.id", ondelete="CASCADE"))
    booking_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("bookings.id", ondelete="RESTRICT"))
    passenger_profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("passenger_profiles.id", ondelete="RESTRICT")
    )
    boarded_at: Mapped[datetime | None]
    dropped_off_at: Mapped[datetime | None]
    boarding_status: Mapped[BoardingStatus] = mapped_column(default=BoardingStatus.WAITING)

    trip: Mapped["Trip"] = relationship(
        back_populates="passengers", foreign_keys=[trip_id], lazy="selectin"
    )
    booking: Mapped["Booking"] = relationship("Booking", foreign_keys=[booking_id], lazy="selectin")
    passenger_profile: Mapped["PassengerProfile"] = relationship(
        "PassengerProfile", foreign_keys=[passenger_profile_id], lazy="selectin"
    )


class TripStatusHistory(Base, UUIDMixin):
    """Append-only log of every `Trip.trip_status` transition, regardless
    of actor. Same shape as `AdvertisementStatusHistory`/
    `BookingStatusHistory` -- this is the third instance of that pattern,
    which is exactly what those two models' docstrings said would justify
    extracting a shared mixin. Not done in this step: that would mean
    editing `advertisement.py`/`booking.py`, and this step's instruction is
    "do not modify previous domains unless a critical architecture issue
    is discovered" -- a DRY opportunity is not that bar. Worth raising as
    a deliberate follow-up task, not performed here.

    No `TimestampMixin`: `changed_at` is this row's one meaningful
    timestamp; a log row is never updated after insert.
    """

    __tablename__ = "trip_status_history"
    __table_args__ = (
        Index("ix_trip_status_history_trip_id", "trip_id"),
        Index("ix_trip_status_history_trip_changed", "trip_id", "changed_at"),
    )

    trip_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("trips.id", ondelete="CASCADE"))
    previous_status: Mapped[TripStatus | None]
    new_status: Mapped[TripStatus]
    changed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    reason: Mapped[str | None] = mapped_column(Text)
    changed_at: Mapped[datetime] = mapped_column(server_default=func.now())

    trip: Mapped["Trip"] = relationship(
        back_populates="status_history", foreign_keys=[trip_id], lazy="selectin"
    )
    changed_by: Mapped["User | None"] = relationship(
        "User", foreign_keys=[changed_by_user_id], lazy="selectin"
    )


__all__ = ["Trip", "TripPassenger", "TripStatusHistory"]
