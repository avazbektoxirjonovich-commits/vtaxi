"""`VehicleService` -- Vehicle management, verification, and the vehicle/
driver documents + vehicle photos that verification depends on.

Every method opens its own Unit of Work via the injected factory and is
therefore independently atomic, same discipline as every service so far.
Nothing here imports SQLAlchemy, Aiogram, or FastAPI -- only `ports.py`
(structural Protocols) and the ORM classes themselves for typing (see
`application/identity/ports.py`'s docstring for why that's not a
"framework independent" violation in this project).

Cross-domain boundary, deliberate: `driver_profile_id` (on `create_vehicle`,
`upload_driver_document`, `get_driver_documents`) is never checked for
existence here -- doing so would need the Identity domain's
`DriverRepository`, which `VehicleUnitOfWork` does not expose (only
`vehicles`). An invalid `driver_profile_id` still can't reach the
database: the FK constraint on `vehicles.driver_profile_id`/
`driver_documents.driver_profile_id` rejects it at flush time. Wiring an
actual cross-domain check belongs to a future orchestration layer (see
"Driver onboarding workflow" in this step's Future Compatibility list),
not this service.

"Banned" (from "Vehicle cannot be activated if banned/rejected"): there is
no ban/availability concept on `Vehicle` itself (that axis exists on
`DriverProfile`, Identity's domain -- see the paragraph above for why this
service doesn't reach into it). `activate_vehicle()` enforces the part
that *is* within Vehicle's own data: `verification_status == REJECTED`
(and `PENDING_REVIEW`) both block activation via `VehicleNotApprovedError`.
"""

import datetime as dt
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from vtaxi.core.application import UnitOfWorkFactory, fail
from vtaxi.core.domain import Result
from vtaxi.core.domain.result import Failure
from vtaxi.domain.vehicle.exceptions import (
    DriverDocumentNotFoundError,
    InvalidDocumentStatusTransitionError,
    VehicleAlreadyExistsError,
    VehicleAlreadyVerifiedError,
    VehicleDocumentNotFoundError,
    VehicleDocumentsIncompleteError,
    VehicleInvalidDataError,
    VehicleNotApprovedError,
    VehicleNotFoundError,
)
from vtaxi.infrastructure.database.enums import (
    DriverDocumentType,
    VehicleClass,
    VehicleDocumentType,
    VehiclePhotoType,
    VerificationStatus,
)
from vtaxi.infrastructure.database.models.vehicle import (
    DriverDocument,
    Vehicle,
    VehicleDocument,
    VehiclePhoto,
)

from .ports import VehicleUnitOfWork

# The three document types `verify_vehicle()` requires to each be
# individually APPROVED before `approve_vehicle()` may proceed --
# "verification must happen before approval."
_REQUIRED_VEHICLE_DOCUMENT_TYPES = (
    VehicleDocumentType.REGISTRATION,
    VehicleDocumentType.INSURANCE,
    VehicleDocumentType.TECHNICAL_INSPECTION,
)


class VehicleService:
    def __init__(self, uow_factory: UnitOfWorkFactory[VehicleUnitOfWork]) -> None:
        self._uow_factory = uow_factory

    # --- Vehicle Management ------------------------------------------------

    async def create_vehicle(
        self,
        *,
        driver_profile_id: uuid.UUID,
        brand: str,
        model: str,
        manufacture_year: int,
        color: str,
        plate_number: str,
        vehicle_class: VehicleClass,
        seat_count: int,
        luggage_capacity: int | None = None,
        air_conditioning: bool = False,
    ) -> Result[Vehicle]:
        async with self._uow_factory() as uow:
            existing = await uow.vehicles.get_by_plate_number(plate_number)
            if existing is not None and existing.deleted_at is None:
                return fail(VehicleAlreadyExistsError)

            try:
                vehicle = await uow.vehicles.create(
                    driver_profile_id=driver_profile_id,
                    brand=brand,
                    model=model,
                    manufacture_year=manufacture_year,
                    color=color,
                    plate_number=plate_number,
                    vehicle_class=vehicle_class,
                    seat_count=seat_count,
                    luggage_capacity=luggage_capacity,
                    air_conditioning=air_conditioning,
                )
            except ValueError as exc:
                return fail(VehicleInvalidDataError, str(exc))
            return Result.ok(vehicle)

    async def get_vehicle(self, vehicle_id: uuid.UUID) -> Result[Vehicle]:
        async with self._uow_factory() as uow:
            vehicle = await uow.vehicles.get_by_id(vehicle_id)
            if vehicle is None:
                return fail(VehicleNotFoundError)
            return Result.ok(vehicle)

    async def vehicle_exists(
        self,
        *,
        vehicle_id: uuid.UUID | None = None,
        plate_number: str | None = None,
    ) -> Result[bool]:
        if vehicle_id is None and plate_number is None:
            raise ValueError("vehicle_exists() requires vehicle_id or plate_number")
        async with self._uow_factory() as uow:
            if vehicle_id is not None:
                return Result.ok(await uow.vehicles.get_by_id(vehicle_id) is not None)
            assert plate_number is not None
            existing = await uow.vehicles.get_by_plate_number(plate_number)
            return Result.ok(existing is not None and existing.deleted_at is None)

    async def update_vehicle(self, vehicle_id: uuid.UUID, **fields: Any) -> Result[Vehicle]:
        async with self._uow_factory() as uow:
            vehicle = await uow.vehicles.get_by_id(vehicle_id)
            if vehicle is None:
                return fail(VehicleNotFoundError)

            new_plate = fields.get("plate_number")
            if new_plate is not None and new_plate != vehicle.plate_number:
                existing = await uow.vehicles.get_by_plate_number(new_plate)
                if existing is not None and existing.deleted_at is None:
                    return fail(VehicleAlreadyExistsError)

            try:
                updated = await uow.vehicles.update(vehicle, **fields)
            except ValueError as exc:
                return fail(VehicleInvalidDataError, str(exc))
            return Result.ok(updated)

    async def soft_delete_vehicle(self, vehicle_id: uuid.UUID) -> Result[None]:
        """Idempotent: soft-deleting an already-deleted vehicle is a no-op
        success, matching `UserService.soft_delete_user`'s convention.
        """
        async with self._uow_factory() as uow:
            vehicle = await uow.vehicles.get_by_id(vehicle_id)
            if vehicle is None:
                return fail(VehicleNotFoundError)
            if vehicle.deleted_at is None:
                await uow.vehicles.delete(vehicle)
            return Result.ok(None)

    async def restore_vehicle(self, vehicle_id: uuid.UUID) -> Result[Vehicle]:
        """Idempotent, same reasoning as `soft_delete_vehicle`.

        Same caveat as `UserService.restore_user`: if
        `register_soft_delete_filter()` is ever registered at a future
        composition root, `get_by_id` would stop finding an already-
        soft-deleted vehicle, and this method would need a repository-
        level `include_deleted` bypass that does not currently exist --
        not fixed here, out of scope for a service-layer step.
        """
        async with self._uow_factory() as uow:
            vehicle = await uow.vehicles.get_by_id(vehicle_id)
            if vehicle is None:
                return fail(VehicleNotFoundError)
            if vehicle.deleted_at is not None:
                await uow.vehicles.restore(vehicle)
            return Result.ok(vehicle)

    # --- Verification --------------------------------------------------

    async def _document_completeness_violation(
        self, vehicle_id: uuid.UUID, uow: VehicleUnitOfWork
    ) -> Failure | None:
        """`None` if every required `VehicleDocument` type is present and
        individually APPROVED, a `Failure` otherwise -- shared by the
        public `verify_vehicle()` and `approve_vehicle()`'s internal
        check, so the two can never silently disagree (same pattern as
        `GeographyService._hierarchy_violation`).
        """
        documents = await uow.vehicles.list_vehicle_documents(vehicle_id)
        approved_types = {
            doc.document_type
            for doc in documents
            if doc.verification_status == VerificationStatus.APPROVED
        }
        missing = [t.value for t in _REQUIRED_VEHICLE_DOCUMENT_TYPES if t not in approved_types]
        if missing:
            return fail(
                VehicleDocumentsIncompleteError,
                f"Missing or unverified documents: {', '.join(missing)}.",
            )
        return None

    async def verify_vehicle(self, vehicle_id: uuid.UUID) -> Result[None]:
        """Checks document completeness -- does not mutate `Vehicle` itself.
        "Verification must happen before approval": `approve_vehicle()`
        runs the same check first and only proceeds if it succeeds.
        """
        async with self._uow_factory() as uow:
            if await uow.vehicles.get_by_id(vehicle_id) is None:
                return fail(VehicleNotFoundError)
            violation = await self._document_completeness_violation(vehicle_id, uow)
            return violation if violation is not None else Result.ok(None)

    async def approve_vehicle(self, vehicle_id: uuid.UUID) -> Result[Vehicle]:
        async with self._uow_factory() as uow:
            vehicle = await uow.vehicles.get_by_id(vehicle_id)
            if vehicle is None:
                return fail(VehicleNotFoundError)
            if vehicle.verification_status == VerificationStatus.APPROVED:
                return fail(VehicleAlreadyVerifiedError)

            violation = await self._document_completeness_violation(vehicle_id, uow)
            if violation is not None:
                return violation

            updated = await uow.vehicles.update(
                vehicle,
                verification_status=VerificationStatus.APPROVED,
                verified_at=datetime.now(UTC),
            )
            return Result.ok(updated)

    async def reject_vehicle(self, vehicle_id: uuid.UUID) -> Result[Vehicle]:
        """No rejection-reason parameter: `Vehicle` has no column for one
        (unlike `VehicleDocument`/`DriverDocument`, which do via
        `VerifiableDocumentMixin`) -- adding one would mean editing an ORM
        model, out of scope for this step.
        """
        async with self._uow_factory() as uow:
            vehicle = await uow.vehicles.get_by_id(vehicle_id)
            if vehicle is None:
                return fail(VehicleNotFoundError)
            updated = await uow.vehicles.update(
                vehicle, verification_status=VerificationStatus.REJECTED, verified=False
            )
            return Result.ok(updated)

    async def activate_vehicle(self, vehicle_id: uuid.UUID) -> Result[Vehicle]:
        """`verified` (bool) is this project's operational "currently
        active/usable" flag, distinct from `verification_status` (the
        admin's one-time review outcome) -- see module docstring.
        Requires prior approval; refuses a soft-deleted or not-yet-/no-
        longer-approved vehicle.
        """
        async with self._uow_factory() as uow:
            vehicle = await uow.vehicles.get_by_id(vehicle_id)
            if vehicle is None:
                return fail(VehicleNotFoundError)
            if vehicle.deleted_at is not None:
                return fail(VehicleNotFoundError, "This vehicle has been deleted.")
            if vehicle.verification_status != VerificationStatus.APPROVED:
                return fail(VehicleNotApprovedError)
            updated = await uow.vehicles.update(vehicle, verified=True)
            return Result.ok(updated)

    async def deactivate_vehicle(self, vehicle_id: uuid.UUID) -> Result[Vehicle]:
        """Always allowed -- deactivating is never an invalid transition."""
        async with self._uow_factory() as uow:
            vehicle = await uow.vehicles.get_by_id(vehicle_id)
            if vehicle is None:
                return fail(VehicleNotFoundError)
            updated = await uow.vehicles.update(vehicle, verified=False)
            return Result.ok(updated)

    # --- Vehicle Documents -----------------------------------------------

    async def upload_vehicle_document(
        self,
        *,
        vehicle_id: uuid.UUID,
        document_type: VehicleDocumentType,
        document_number: str | None = None,
        issue_date: dt.date | None = None,
        expiry_date: dt.date | None = None,
    ) -> Result[VehicleDocument]:
        async with self._uow_factory() as uow:
            if await uow.vehicles.get_by_id(vehicle_id) is None:
                return fail(VehicleNotFoundError)
            try:
                document = await uow.vehicles.create_vehicle_document(
                    vehicle_id=vehicle_id,
                    document_type=document_type,
                    document_number=document_number,
                    issue_date=issue_date,
                    expiry_date=expiry_date,
                )
            except ValueError as exc:
                return fail(VehicleInvalidDataError, str(exc))
            return Result.ok(document)

    async def get_vehicle_documents(
        self, vehicle_id: uuid.UUID
    ) -> Result[Sequence[VehicleDocument]]:
        async with self._uow_factory() as uow:
            if await uow.vehicles.get_by_id(vehicle_id) is None:
                return fail(VehicleNotFoundError)
            documents = await uow.vehicles.list_vehicle_documents(vehicle_id)
            return Result.ok(documents)

    async def verify_vehicle_document(
        self, document_id: uuid.UUID, *, verified_by_admin_id: uuid.UUID | None = None
    ) -> Result[VehicleDocument]:
        async with self._uow_factory() as uow:
            document = await uow.vehicles.get_vehicle_document(document_id)
            if document is None:
                return fail(VehicleDocumentNotFoundError)
            if document.verification_status == VerificationStatus.APPROVED:
                return fail(
                    InvalidDocumentStatusTransitionError, "This document is already verified."
                )
            updated = await uow.vehicles.update_vehicle_document(
                document,
                verification_status=VerificationStatus.APPROVED,
                verified_at=datetime.now(UTC),
                verified_by_admin_id=verified_by_admin_id,
            )
            return Result.ok(updated)

    async def reject_vehicle_document(
        self, document_id: uuid.UUID, *, rejection_reason: str | None = None
    ) -> Result[VehicleDocument]:
        async with self._uow_factory() as uow:
            document = await uow.vehicles.get_vehicle_document(document_id)
            if document is None:
                return fail(VehicleDocumentNotFoundError)
            if document.verification_status == VerificationStatus.REJECTED:
                return fail(
                    InvalidDocumentStatusTransitionError, "This document is already rejected."
                )
            updated = await uow.vehicles.update_vehicle_document(
                document,
                verification_status=VerificationStatus.REJECTED,
                rejection_reason=rejection_reason,
            )
            return Result.ok(updated)

    # --- Driver Documents ------------------------------------------------

    async def upload_driver_document(
        self,
        *,
        driver_profile_id: uuid.UUID,
        document_type: DriverDocumentType,
        document_number: str | None = None,
        issue_date: dt.date | None = None,
        expiry_date: dt.date | None = None,
    ) -> Result[DriverDocument]:
        async with self._uow_factory() as uow:
            try:
                document = await uow.vehicles.create_driver_document(
                    driver_profile_id=driver_profile_id,
                    document_type=document_type,
                    document_number=document_number,
                    issue_date=issue_date,
                    expiry_date=expiry_date,
                )
            except ValueError as exc:
                return fail(VehicleInvalidDataError, str(exc))
            return Result.ok(document)

    async def get_driver_documents(
        self, driver_profile_id: uuid.UUID
    ) -> Result[Sequence[DriverDocument]]:
        async with self._uow_factory() as uow:
            documents = await uow.vehicles.list_driver_documents(driver_profile_id)
            return Result.ok(documents)

    async def verify_driver_document(
        self, document_id: uuid.UUID, *, verified_by_admin_id: uuid.UUID | None = None
    ) -> Result[DriverDocument]:
        async with self._uow_factory() as uow:
            document = await uow.vehicles.get_driver_document(document_id)
            if document is None:
                return fail(DriverDocumentNotFoundError)
            if document.verification_status == VerificationStatus.APPROVED:
                return fail(
                    InvalidDocumentStatusTransitionError, "This document is already verified."
                )
            updated = await uow.vehicles.update_driver_document(
                document,
                verification_status=VerificationStatus.APPROVED,
                verified_at=datetime.now(UTC),
                verified_by_admin_id=verified_by_admin_id,
            )
            return Result.ok(updated)

    async def reject_driver_document(
        self, document_id: uuid.UUID, *, rejection_reason: str | None = None
    ) -> Result[DriverDocument]:
        async with self._uow_factory() as uow:
            document = await uow.vehicles.get_driver_document(document_id)
            if document is None:
                return fail(DriverDocumentNotFoundError)
            if document.verification_status == VerificationStatus.REJECTED:
                return fail(
                    InvalidDocumentStatusTransitionError, "This document is already rejected."
                )
            updated = await uow.vehicles.update_driver_document(
                document,
                verification_status=VerificationStatus.REJECTED,
                rejection_reason=rejection_reason,
            )
            return Result.ok(updated)

    # --- Vehicle Photos --------------------------------------------------

    async def upload_vehicle_photo(
        self, *, vehicle_id: uuid.UUID, image_url: str, image_type: VehiclePhotoType
    ) -> Result[VehiclePhoto]:
        async with self._uow_factory() as uow:
            if await uow.vehicles.get_by_id(vehicle_id) is None:
                return fail(VehicleNotFoundError)
            try:
                photo = await uow.vehicles.create_vehicle_photo(
                    vehicle_id=vehicle_id, image_url=image_url, image_type=image_type
                )
            except ValueError as exc:
                return fail(VehicleInvalidDataError, str(exc))
            return Result.ok(photo)

    async def get_vehicle_photos(self, vehicle_id: uuid.UUID) -> Result[Sequence[VehiclePhoto]]:
        async with self._uow_factory() as uow:
            if await uow.vehicles.get_by_id(vehicle_id) is None:
                return fail(VehicleNotFoundError)
            photos = await uow.vehicles.list_vehicle_photos(vehicle_id)
            return Result.ok(photos)


__all__ = ["VehicleService"]
