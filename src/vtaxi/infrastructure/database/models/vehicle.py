"""Vehicle domain ORM models: `Vehicle` and its documents/photos, plus the
driver's own identity documents.

References `driver_profiles`/`admin_profiles` (Identity) by string class
name / string FK target only -- no import of `identity.py` -- so this
module never creates a circular import with it, and Identity is never
modified to add this domain's models.

Placed under `infrastructure/database/models/`, not `domain/vehicle/`, for
the same Dependency Rule reason as the Identity and Geography models.
"""

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    String,
    func,
    text,
)
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship, validates

from vtaxi.infrastructure.database.base import Base
from vtaxi.infrastructure.database.enums import (
    DriverDocumentType,
    VehicleClass,
    VehicleDocumentType,
    VehiclePhotoType,
    VerificationStatus,
)
from vtaxi.infrastructure.database.mixins import SoftDeleteMixin, TimestampMixin, UUIDMixin
from vtaxi.infrastructure.database.validators import (
    ensure_non_negative,
    ensure_not_blank,
    ensure_not_in_future_year,
    ensure_positive,
)

if TYPE_CHECKING:
    # Type-checking only -- never imported at runtime, so this can't create
    # a circular import with identity.py (which does not import this module).
    from vtaxi.infrastructure.database.models.identity import AdminProfile, DriverProfile


class VerifiableDocumentMixin:
    """Shared shape for a document that goes through admin verification --
    used by `DriverDocument` and `VehicleDocument`. Not promoted to
    `infrastructure/database/mixins/` since it is Vehicle-domain-specific
    today, not a cross-context concern like the four generic mixins there.

    `verified_by_admin_id`/`verified_by` use `declared_attr` for the same
    reason `AuditMixin` does (see mixins/audit_mixin.py): a string FK
    target ("admin_profiles.id") resolves at mapper-configuration time, so
    this mixin never needs to import the `AdminProfile` class.
    """

    document_number: Mapped[str | None] = mapped_column(String(100))
    issue_date: Mapped[date | None]
    expiry_date: Mapped[date | None]
    verification_status: Mapped[VerificationStatus] = mapped_column(
        default=VerificationStatus.PENDING_REVIEW
    )
    verified_at: Mapped[datetime | None]
    rejection_reason: Mapped[str | None] = mapped_column(String(500))

    @declared_attr
    def verified_by_admin_id(cls) -> Mapped[uuid.UUID | None]:
        return mapped_column(ForeignKey("admin_profiles.id", ondelete="SET NULL"))

    @declared_attr
    def verified_by(cls) -> Mapped["AdminProfile | None"]:
        # `foreign_keys` as a lambda, not a direct list: defers attribute
        # access until mapper-configuration time, safe regardless of the
        # two declared_attrs' evaluation order on the concrete subclass.
        return relationship(
            "AdminProfile",
            # mypy resolves `cls.verified_by_admin_id` to its value type
            # (UUID | None) here, not the InstrumentedAttribute SQLAlchemy
            # actually passes at runtime -- a stub precision gap, not a bug.
            foreign_keys=lambda: [cls.verified_by_admin_id],  # type: ignore[arg-type]
            lazy="selectin",
        )


class Vehicle(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    """A driver's registered vehicle. A driver may own more than one over
    time (Future Compatibility: "multiple vehicles per driver" needs no
    special column -- `driver_profile_id` is a plain, unconstrained-by-
    uniqueness FK already). "Vehicle replacement" and "temporary inactive
    vehicles" likewise need no schema change now: swapping which vehicle an
    Advertisement points at is that model's concern (not built yet), and a
    future `is_active` toggle would be a purely additive column.

    `verified` (bool) and `verification_status` (enum) are intentionally
    both present, even though `verified` is essentially
    `verification_status == APPROVED` -- kept as two columns because the
    brief asked for both explicitly; reconciling them is a future
    service-layer concern, not something to invent here.
    """

    __tablename__ = "vehicles"
    __table_args__ = (
        Index("ix_vehicles_driver_profile_id", "driver_profile_id"),
        Index("ix_vehicles_verification_status", "verification_status"),
        Index("ix_vehicles_verified", "verified"),
        # Partial unique index, not a plain unique column: same reasoning as
        # `users.phone_number` (docs/03 SS0.3) -- a plate number becomes
        # reusable once its old vehicle record is soft-deleted.
        Index(
            "uq_vehicles_plate_number_active",
            "plate_number",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        CheckConstraint("seat_count > 0", name="seat_count_positive"),
    )

    driver_profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("driver_profiles.id", ondelete="RESTRICT")
    )
    brand: Mapped[str] = mapped_column(String(50))
    model: Mapped[str] = mapped_column(String(50))
    manufacture_year: Mapped[int]
    color: Mapped[str] = mapped_column(String(30))
    plate_number: Mapped[str] = mapped_column(String(20))
    vehicle_class: Mapped[VehicleClass]
    seat_count: Mapped[int]
    luggage_capacity: Mapped[int | None]
    air_conditioning: Mapped[bool] = mapped_column(default=False)
    verified: Mapped[bool] = mapped_column(default=False)
    verification_status: Mapped[VerificationStatus] = mapped_column(
        default=VerificationStatus.PENDING_REVIEW
    )
    verified_at: Mapped[datetime | None]

    driver_profile: Mapped["DriverProfile"] = relationship(
        "DriverProfile", foreign_keys=[driver_profile_id], lazy="selectin"
    )
    documents: Mapped[list["VehicleDocument"]] = relationship(
        back_populates="vehicle",
        foreign_keys="VehicleDocument.vehicle_id",
        lazy="selectin",
    )
    photos: Mapped[list["VehiclePhoto"]] = relationship(
        back_populates="vehicle",
        foreign_keys="VehiclePhoto.vehicle_id",
        lazy="selectin",
    )

    @validates("brand", "model", "color", "plate_number")
    def _validate_not_blank(self, key: str, value: str) -> str:
        return ensure_not_blank(value, field_name=key)

    @validates("seat_count")
    def _validate_seat_count(self, key: str, value: int) -> int:
        return int(ensure_positive(value, field_name=key))

    @validates("manufacture_year")
    def _validate_manufacture_year(self, key: str, value: int) -> int:
        return ensure_not_in_future_year(value, field_name=key)

    @validates("luggage_capacity")
    def _validate_luggage_capacity(self, key: str, value: int | None) -> int | None:
        if value is None:
            return None
        return int(ensure_non_negative(value, field_name=key))


class DriverDocument(Base, UUIDMixin, TimestampMixin, VerifiableDocumentMixin):
    """A driver's own identity document (license, passport, ID card) -- as
    distinct from `Vehicle`'s registration/insurance paperwork. No
    `SoftDeleteMixin`: like the rest of this project's document tables, a
    superseding upload is a new row, not an edit -- see docs/03-DATABASE-
    DESIGN.md SS2.3 for the same reasoning applied to `driver_documents`.
    """

    __tablename__ = "driver_documents"
    __table_args__ = (
        Index("ix_driver_documents_driver_profile_id", "driver_profile_id"),
        Index("ix_driver_documents_verification_status", "verification_status"),
        Index("ix_driver_documents_expiry_date", "expiry_date"),
        CheckConstraint(
            "expiry_date IS NULL OR issue_date IS NULL OR expiry_date > issue_date",
            name="expiry_after_issue",
        ),
    )

    driver_profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("driver_profiles.id", ondelete="CASCADE")
    )
    document_type: Mapped[DriverDocumentType]

    # One-directional only: a `DriverProfile.driver_documents` back-collection
    # would require editing identity.py, out of scope this step.
    driver_profile: Mapped["DriverProfile"] = relationship(
        "DriverProfile", foreign_keys=[driver_profile_id], lazy="selectin"
    )

    @validates("document_number")
    def _validate_document_number(self, key: str, value: str | None) -> str | None:
        if value is None:
            return None
        return ensure_not_blank(value, field_name=key)


class VehicleDocument(Base, UUIDMixin, TimestampMixin, VerifiableDocumentMixin):
    """A vehicle's paperwork: registration, insurance, technical inspection.
    No `SoftDeleteMixin`, same reasoning as `DriverDocument`.
    """

    __tablename__ = "vehicle_documents"
    __table_args__ = (
        Index("ix_vehicle_documents_vehicle_id", "vehicle_id"),
        Index("ix_vehicle_documents_verification_status", "verification_status"),
        Index("ix_vehicle_documents_expiry_date", "expiry_date"),
        CheckConstraint(
            "expiry_date IS NULL OR issue_date IS NULL OR expiry_date > issue_date",
            name="expiry_after_issue",
        ),
    )

    vehicle_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("vehicles.id", ondelete="CASCADE"))
    document_type: Mapped[VehicleDocumentType]

    vehicle: Mapped["Vehicle"] = relationship(
        back_populates="documents", foreign_keys=[vehicle_id], lazy="selectin"
    )

    @validates("document_number")
    def _validate_document_number(self, key: str, value: str | None) -> str | None:
        if value is None:
            return None
        return ensure_not_blank(value, field_name=key)


class VehiclePhoto(Base, UUIDMixin, TimestampMixin):
    """One of a vehicle's angle photos (front/back/left/right/interior).

    Simpler than `VehicleDocument` on purpose -- just a `verified` flag, no
    full verification workflow (no admin/rejection-reason columns) -- the
    brief's field list for this model is deliberately smaller than the
    document models', and this mirrors that.

    `image_url` (not `file_reference`): kept as a plain string so it can
    hold today's Telegram `file_id` and tomorrow's real object-storage URL
    without a schema change -- exactly the "future image storage
    migration" compatibility the brief asks for.
    """

    __tablename__ = "vehicle_photos"
    __table_args__ = (
        Index("ix_vehicle_photos_vehicle_id", "vehicle_id"),
        Index("ix_vehicle_photos_verified", "verified"),
    )

    vehicle_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("vehicles.id", ondelete="CASCADE"))
    image_url: Mapped[str] = mapped_column(String(500))
    image_type: Mapped[VehiclePhotoType]
    uploaded_at: Mapped[datetime] = mapped_column(server_default=func.now())
    verified: Mapped[bool] = mapped_column(default=False)

    vehicle: Mapped["Vehicle"] = relationship(
        back_populates="photos", foreign_keys=[vehicle_id], lazy="selectin"
    )

    @validates("image_url")
    def _validate_image_url(self, key: str, value: str) -> str:
        return ensure_not_blank(value, field_name=key)


__all__ = ["DriverDocument", "Vehicle", "VehicleDocument", "VehiclePhoto"]
