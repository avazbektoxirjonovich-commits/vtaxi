"""Vehicle domain exceptions -- also covers `VehicleDocument`,
`DriverDocument`, and `VehiclePhoto` (all four models live in
`infrastructure/database/models/vehicle.py`; `DriverDocument` in
particular is grouped with Vehicle, not Identity, at the ORM layer, and
Step 8.2's brief assigns "Driver Documents" to `VehicleService`).
"""

from vtaxi.core.domain.error_codes import ErrorCode
from vtaxi.core.domain.exceptions import (
    AlreadyExistsError,
    BaseDomainException,
    InvalidStateError,
    NotFoundError,
)


class VehicleNotFoundError(NotFoundError):
    error_code = ErrorCode.VEHICLE_NOT_FOUND
    default_message = "Vehicle not found."


class VehicleAlreadyExistsError(AlreadyExistsError):
    error_code = ErrorCode.VEHICLE_ALREADY_EXISTS
    default_message = "A vehicle with this plate number is already registered."


class VehicleNotApprovedError(InvalidStateError):
    error_code = ErrorCode.VEHICLE_NOT_APPROVED
    default_message = "This vehicle has not been approved by an admin yet."


class VehicleAlreadyVerifiedError(InvalidStateError):
    """Added in Step 8.3 for `VehicleService.approve_vehicle()` -- guards
    against approving a vehicle a second time. Named "verified", matching
    this round's own vocabulary, even though the guard is on
    `verification_status == APPROVED` (see geography_service.py's
    `verify` vs `approve` split, same pattern used here: `verify_vehicle()`
    checks document completeness without mutating state, `approve_vehicle()`
    is the actual, one-time state transition).
    """

    error_code = ErrorCode.VEHICLE_ALREADY_VERIFIED
    default_message = "This vehicle has already been verified."


class VehicleDocumentsIncompleteError(InvalidStateError):
    """`verify_vehicle()`'s guard: not every required `VehicleDocument`
    (REGISTRATION, INSURANCE, TECHNICAL_INSPECTION) is present and
    individually approved yet -- "verification must happen before
    approval," and this is what verification actually checks.
    """

    error_code = ErrorCode.VEHICLE_DOCUMENTS_INCOMPLETE
    default_message = "Not all required vehicle documents have been verified yet."


class VehicleInvalidDataError(BaseDomainException):
    """Catch-all translation for the `ValueError`s the ORM's own
    `@validates` hooks raise (manufacture year in the future, non-positive
    seat count, blank brand/model/color/plate number, ...) -- so a
    `Result.fail(...)` is what a caller sees, not a raw `ValueError`
    leaking out of the service.
    """

    error_code = ErrorCode.VEHICLE_INVALID_DATA
    default_message = "The provided vehicle data is invalid."


class VehicleDocumentNotFoundError(NotFoundError):
    error_code = ErrorCode.VEHICLE_DOCUMENT_NOT_FOUND
    default_message = "Vehicle document not found."


class DriverDocumentNotFoundError(NotFoundError):
    error_code = ErrorCode.DRIVER_DOCUMENT_NOT_FOUND
    default_message = "Driver document not found."


class InvalidDocumentStatusTransitionError(InvalidStateError):
    """Shared by vehicle- and driver-document verify/reject guards --
    "already verified" or "already rejected," the same underlying
    concept regardless of which of the two document tables it's on.
    """

    error_code = ErrorCode.INVALID_DOCUMENT_STATUS_TRANSITION
    default_message = "This document is not in a state that allows this transition."


__all__ = [
    "DriverDocumentNotFoundError",
    "InvalidDocumentStatusTransitionError",
    "VehicleAlreadyExistsError",
    "VehicleAlreadyVerifiedError",
    "VehicleDocumentNotFoundError",
    "VehicleDocumentsIncompleteError",
    "VehicleInvalidDataError",
    "VehicleNotApprovedError",
    "VehicleNotFoundError",
]
