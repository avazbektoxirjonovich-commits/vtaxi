"""Complaint domain exceptions.

The two raised in Step 7.5 (`NotFound`/`AlreadyResolved`) are kept as-is.
Step 8.7 (`ComplaintService`) adds the rest: a data-validation catch-all
(empty title/description, or "must reference a valid Booking or Trip"),
a reference-not-found error (the given `trip_id`/`booking_id` does not
actually exist -- distinct from the "neither was given at all" case,
which is a data problem, not a reference problem), and a `DISMISSED`
terminal-state guard symmetric with the existing `ComplaintAlreadyResolvedError`
(`RESOLVED`'s own guard) -- `ComplaintStatus` has two terminal values,
so it gets two matching exceptions, same as Advertisement/Booking/Trip's
one-class-per-reachable-terminal-state pattern.
"""

from vtaxi.core.domain.error_codes import ErrorCode
from vtaxi.core.domain.exceptions import BaseDomainException, InvalidStateError, NotFoundError


class ComplaintNotFoundError(NotFoundError):
    error_code = ErrorCode.COMPLAINT_NOT_FOUND
    default_message = "Complaint not found."


class ComplaintAlreadyResolvedError(InvalidStateError):
    error_code = ErrorCode.COMPLAINT_ALREADY_RESOLVED
    default_message = "This complaint has already been resolved."


class ComplaintInvalidDataError(BaseDomainException):
    error_code = ErrorCode.COMPLAINT_INVALID_DATA
    default_message = "The provided complaint data is invalid."


class ComplaintReferenceNotFoundError(NotFoundError):
    error_code = ErrorCode.COMPLAINT_REFERENCE_NOT_FOUND
    default_message = "The referenced trip or booking does not exist."


class ComplaintDismissedError(InvalidStateError):
    error_code = ErrorCode.COMPLAINT_DISMISSED
    default_message = "This complaint has already been dismissed."


__all__ = [
    "ComplaintAlreadyResolvedError",
    "ComplaintDismissedError",
    "ComplaintInvalidDataError",
    "ComplaintNotFoundError",
    "ComplaintReferenceNotFoundError",
]
