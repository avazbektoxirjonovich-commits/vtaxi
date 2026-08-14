"""Booking domain exceptions.

The four raised in Step 7.5 (`NotFound`/`AlreadyExists`/`Expired`/
`Cancelled`) are kept as-is. Step 8.5 (`BookingService`) adds the rest:
`Rejected` (a terminal state this service actively produces, same
reasoning as its three Step-7.5 siblings), a generic invalid-transition
catch-all, a data-validation catch-all, an insufficient-seats guard, and
three cross-domain eligibility errors (self-booking, advertisement not
bookable, passenger not eligible) mirroring the pattern
`AdvertisementVehicleNotEligibleError`/`AdvertisementDriverNotEligibleError`/
`AdvertisementDirectionNotEligibleError` established in Step 8.4 -- one
class covers both "the referenced row does not exist" and "it exists but
fails the eligibility check," since both are equally "not usable for this
booking" from a caller's point of view.
"""

from vtaxi.core.domain.error_codes import ErrorCode
from vtaxi.core.domain.exceptions import (
    AlreadyExistsError,
    BaseDomainException,
    InvalidStateError,
    NotFoundError,
)


class BookingNotFoundError(NotFoundError):
    error_code = ErrorCode.BOOKING_NOT_FOUND
    default_message = "Booking not found."


class BookingAlreadyExistsError(AlreadyExistsError):
    error_code = ErrorCode.BOOKING_ALREADY_EXISTS
    default_message = "An active booking already exists for this passenger and advertisement."


class BookingExpiredError(InvalidStateError):
    error_code = ErrorCode.BOOKING_EXPIRED
    default_message = "This booking's reservation window has expired."


class BookingCancelledError(InvalidStateError):
    error_code = ErrorCode.BOOKING_CANCELLED
    default_message = "This booking has been cancelled."


class BookingRejectedError(InvalidStateError):
    error_code = ErrorCode.BOOKING_REJECTED
    default_message = "This booking has been rejected."


class BookingInvalidStatusTransitionError(InvalidStateError):
    """Generic status-machine guard for a transition not covered by one of
    the more specific errors above (e.g. reserving a seat on a non-PENDING
    booking, accepting a booking that isn't RESERVED, cancelling an
    already-ACCEPTED one).
    """

    error_code = ErrorCode.BOOKING_INVALID_STATUS_TRANSITION
    default_message = "This booking is not in a state that allows this transition."


class BookingInvalidDataError(BaseDomainException):
    """Catch-all for a service-level data check that fails: `requested_seats`
    out of range, a `reserved_until` that has not passed yet, or a
    `ValueError` raised by `Booking`'s own `@validates` hook, translated
    the same way `VehicleInvalidDataError`/`AdvertisementInvalidDataError` do.
    """

    error_code = ErrorCode.BOOKING_INVALID_DATA
    default_message = "The provided booking data is invalid."


class BookingInsufficientSeatsError(InvalidStateError):
    error_code = ErrorCode.BOOKING_INSUFFICIENT_SEATS
    default_message = "Not enough seats are available on this advertisement."


class BookingSelfBookingError(InvalidStateError):
    error_code = ErrorCode.BOOKING_SELF_BOOKING
    default_message = "A driver cannot book their own advertisement."


class BookingAdvertisementNotBookableError(InvalidStateError):
    error_code = ErrorCode.BOOKING_ADVERTISEMENT_NOT_BOOKABLE
    default_message = "This advertisement is not currently accepting bookings."


class BookingPassengerNotEligibleError(InvalidStateError):
    error_code = ErrorCode.BOOKING_PASSENGER_NOT_ELIGIBLE
    default_message = "This passenger is not eligible to book (not found, deleted, or banned)."


__all__ = [
    "BookingAdvertisementNotBookableError",
    "BookingAlreadyExistsError",
    "BookingCancelledError",
    "BookingExpiredError",
    "BookingInsufficientSeatsError",
    "BookingInvalidDataError",
    "BookingInvalidStatusTransitionError",
    "BookingNotFoundError",
    "BookingPassengerNotEligibleError",
    "BookingRejectedError",
    "BookingSelfBookingError",
]
