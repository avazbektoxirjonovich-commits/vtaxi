"""Identity domain ORM models: `User` and its three role-specific extensions.

Class-table-inheritance pattern (docs/03-DATABASE-DESIGN.md SS2.1): `User`
holds identity common to every role; `DriverProfile` / `PassengerProfile` /
`AdminProfile` each hold exactly the columns specific to that role, in a
1:1 relationship with `User`. `User.role` says which extension applies.

All four models live in this one module rather than one file per class --
the four-way web of relationships (User <-> each profile) never needs a
cross-module import this way, avoiding circular imports by construction
instead of by discipline.

Placed under `infrastructure/database/models/`, not `domain/identity/`:
these are SQLAlchemy declarative classes (they inherit `Base`, use
`mapped_column`/`relationship`), which makes them infrastructure by the
Dependency Rule in docs/01-SOFTWARE-ARCHITECTURE.md SS2.1 -- domain code
must carry zero framework imports. `domain/identity/` stays reserved for
framework-free entities if a later step introduces them.

Deferred, not dropped, from docs/03's original `driver_profiles` design:
`current_latitude`/`current_longitude`/`current_area_id` need
`administrative_areas`, which is explicitly next (Geography), not this
step. `approved_at`/`approved_by_admin_id` are left for that same reason
-- they're additive later, so nothing here has to change shape to add
them.
"""

import uuid
from decimal import Decimal

from sqlalchemy import BigInteger, ForeignKey, Index, Numeric, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from vtaxi.infrastructure.database.base import Base
from vtaxi.infrastructure.database.enums import (
    AdminRole,
    DriverApprovalStatus,
    DriverAvailabilityStatus,
    PassengerStatus,
    UserRole,
)
from vtaxi.infrastructure.database.mixins import (
    AuditMixin,
    SoftDeleteMixin,
    TimestampMixin,
    UUIDMixin,
)
from vtaxi.infrastructure.database.validators import ensure_non_negative, ensure_not_blank


class User(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    """The single identity record for every platform participant, regardless
    of role. See docs/03-DATABASE-DESIGN.md SS2.1.

    No `AuditMixin`: a user is (today) always self-registered via Telegram,
    so "who created/updated this row" has no actor other than the row's own
    subject -- unlike the three profile tables below, which admins do act
    on. `role` is kept even though this round's brief didn't restate it:
    dropping it would break the whole class-table-inheritance design, since
    it's the only way to know which of the three profile tables applies.
    "User Status" from the brief maps to `is_active` (docs/03's column of
    that purpose); there is no separate status enum for `users` itself in
    the approved design.
    """

    __tablename__ = "users"
    __table_args__ = (
        # Partial unique index, not a plain unique column: docs/03 SS0.3/SS2.1
        # -- a phone number becomes reusable once its old account is
        # soft-deleted, so uniqueness only holds among *active* rows.
        Index(
            "uq_users_phone_number_active",
            "phone_number",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    phone_number: Mapped[str] = mapped_column(String(20))
    username: Mapped[str | None] = mapped_column(String(32), unique=True)
    first_name: Mapped[str] = mapped_column(String(150))
    last_name: Mapped[str | None] = mapped_column(String(150))
    language_code: Mapped[str] = mapped_column(String(10), default="uz")
    role: Mapped[UserRole]
    is_active: Mapped[bool] = mapped_column(default=True)

    driver_profile: Mapped["DriverProfile | None"] = relationship(
        back_populates="user",
        foreign_keys="DriverProfile.user_id",
        uselist=False,
        lazy="selectin",
    )
    passenger_profile: Mapped["PassengerProfile | None"] = relationship(
        back_populates="user",
        foreign_keys="PassengerProfile.user_id",
        uselist=False,
        lazy="selectin",
    )
    admin_profile: Mapped["AdminProfile | None"] = relationship(
        back_populates="user",
        foreign_keys="AdminProfile.user_id",
        uselist=False,
        lazy="selectin",
    )

    @validates("phone_number")
    def _validate_phone_number(self, key: str, value: str) -> str:
        return ensure_not_blank(value, field_name=key)

    @validates("first_name")
    def _validate_first_name(self, key: str, value: str) -> str:
        return ensure_not_blank(value, field_name=key)


class DriverProfile(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin, AuditMixin):
    """Driver-specific extension of `User`. See docs/03-DATABASE-DESIGN.md SS2.1
    and docs/01-SOFTWARE-ARCHITECTURE.md SS14.3 for why `approval_status`
    (verification gate) and `availability_status` (operational visibility)
    are two independent columns, not one.
    """

    __tablename__ = "driver_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True
    )
    approval_status: Mapped[DriverApprovalStatus] = mapped_column(
        default=DriverApprovalStatus.PENDING_REVIEW
    )
    availability_status: Mapped[DriverAvailabilityStatus] = mapped_column(
        default=DriverAvailabilityStatus.OFFLINE
    )
    average_rating: Mapped[Decimal | None] = mapped_column(Numeric(3, 2))
    ratings_count: Mapped[int] = mapped_column(default=0)
    completed_trips_count: Mapped[int] = mapped_column(default=0)
    cancelled_trips_count: Mapped[int] = mapped_column(default=0)

    user: Mapped["User"] = relationship(
        back_populates="driver_profile",
        foreign_keys=[user_id],
        lazy="selectin",
    )

    @validates("ratings_count", "completed_trips_count", "cancelled_trips_count")
    def _validate_non_negative_count(self, key: str, value: int) -> int:
        return int(ensure_non_negative(value, field_name=key))

    @validates("average_rating")
    def _validate_average_rating(self, key: str, value: Decimal | None) -> Decimal | None:
        if value is None:
            return None
        return ensure_non_negative(value, field_name=key)  # type: ignore[return-value]


class PassengerProfile(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin, AuditMixin):
    """Passenger-specific extension of `User`. `passenger_status` is an
    event-derived projection (docs/01-SOFTWARE-ARCHITECTURE.md SS14.4) --
    kept even though this round's brief only asked for the four counters,
    since dropping it would silently regress that already-approved design.
    """

    __tablename__ = "passenger_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True
    )
    passenger_status: Mapped[PassengerStatus] = mapped_column(default=PassengerStatus.ACTIVE)
    average_rating: Mapped[Decimal | None] = mapped_column(Numeric(3, 2))
    ratings_count: Mapped[int] = mapped_column(default=0)
    completed_trips_count: Mapped[int] = mapped_column(default=0)
    cancelled_bookings_count: Mapped[int] = mapped_column(default=0)

    user: Mapped["User"] = relationship(
        back_populates="passenger_profile",
        foreign_keys=[user_id],
        lazy="selectin",
    )

    @validates("ratings_count", "completed_trips_count", "cancelled_bookings_count")
    def _validate_non_negative_count(self, key: str, value: int) -> int:
        return int(ensure_non_negative(value, field_name=key))

    @validates("average_rating")
    def _validate_average_rating(self, key: str, value: Decimal | None) -> Decimal | None:
        if value is None:
            return None
        return ensure_non_negative(value, field_name=key)  # type: ignore[return-value]


class AdminProfile(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin, AuditMixin):
    """Admin-specific extension of `User`. `admin_role` resolves
    docs/03-DATABASE-DESIGN.md SS6 item 2, previously left flat/undecided --
    this round's brief explicitly asked for a role, so it's added now.
    """

    __tablename__ = "admin_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True
    )
    admin_role: Mapped[AdminRole] = mapped_column(default=AdminRole.SUPPORT)
    is_active: Mapped[bool] = mapped_column(default=True)

    user: Mapped["User"] = relationship(
        back_populates="admin_profile",
        foreign_keys=[user_id],
        lazy="selectin",
    )


__all__ = ["AdminProfile", "DriverProfile", "PassengerProfile", "User"]
