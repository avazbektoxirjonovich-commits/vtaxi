"""Advertisement domain exceptions.

The four raised in Step 7.5 (`NotFound`/`Full`/`Expired`/`Closed`) are
kept as-is. Step 8.4 (`AdvertisementService`) adds the rest: one generic
data-validation error, three "not eligible to be advertised" errors for
`validate_vehicle`/`validate_driver`/`validate_direction` (the brief's own
cross-domain checks -- see `application/advertisement/ports.py` for why
`AdvertisementUnitOfWork` reads from `vehicles`/`drivers`/`geography` too),
and the remaining status-machine guards (`CANCELLED`, "already active",
a generic invalid-transition catch-all, and the two seat-counter guards).
"""

from vtaxi.core.domain.error_codes import ErrorCode
from vtaxi.core.domain.exceptions import (
    BaseDomainException,
    InvalidStateError,
    NotFoundError,
)


class AdvertisementNotFoundError(NotFoundError):
    error_code = ErrorCode.ADVERTISEMENT_NOT_FOUND
    default_message = "Advertisement not found."


class AdvertisementFullError(InvalidStateError):
    error_code = ErrorCode.ADVERTISEMENT_FULL
    default_message = "This advertisement has no seats left."


class AdvertisementExpiredError(InvalidStateError):
    error_code = ErrorCode.ADVERTISEMENT_EXPIRED
    default_message = "This advertisement has expired."


class AdvertisementClosedError(InvalidStateError):
    error_code = ErrorCode.ADVERTISEMENT_CLOSED
    default_message = "This advertisement is closed."


class AdvertisementCancelledError(InvalidStateError):
    error_code = ErrorCode.ADVERTISEMENT_CANCELLED
    default_message = "This advertisement has been cancelled."


class AdvertisementAlreadyActiveError(InvalidStateError):
    error_code = ErrorCode.ADVERTISEMENT_ALREADY_ACTIVE
    default_message = "This advertisement is already active."


class AdvertisementInvalidDataError(BaseDomainException):
    """Catch-all for a service-level data check that fails: departure time
    in the past, `expires_at` not after `departure_time`, pickup ==
    destination area, an area id that does not exist, or a `ValueError`
    raised by one of `Advertisement`'s own `@validates` hooks (seat
    counts, price) translated the same way `VehicleInvalidDataError` does.
    """

    error_code = ErrorCode.ADVERTISEMENT_INVALID_DATA
    default_message = "The provided advertisement data is invalid."


class AdvertisementInvalidStatusTransitionError(InvalidStateError):
    """Generic status-machine guard for a transition not covered by one of
    the more specific errors above (e.g. editing a non-DRAFT advertisement,
    reserving seats on a non-ACTIVE one, deactivating a terminal one).
    """

    error_code = ErrorCode.ADVERTISEMENT_INVALID_STATUS_TRANSITION
    default_message = "This advertisement is not in a state that allows this transition."


class AdvertisementInsufficientSeatsError(InvalidStateError):
    error_code = ErrorCode.ADVERTISEMENT_INSUFFICIENT_SEATS
    default_message = "Not enough seats are available for this operation."


class AdvertisementSeatLimitExceededError(InvalidStateError):
    error_code = ErrorCode.ADVERTISEMENT_SEAT_LIMIT_EXCEEDED
    default_message = "This operation would exceed the advertisement's total seat count."


class AdvertisementVehicleNotEligibleError(InvalidStateError):
    error_code = ErrorCode.ADVERTISEMENT_VEHICLE_NOT_ELIGIBLE
    default_message = (
        "This vehicle is not eligible to be advertised "
        "(not found, deleted, not approved, or not owned by this driver)."
    )


class AdvertisementDriverNotEligibleError(InvalidStateError):
    error_code = ErrorCode.ADVERTISEMENT_DRIVER_NOT_ELIGIBLE
    default_message = (
        "This driver is not eligible to publish advertisements "
        "(not found, not approved, or banned)."
    )


class AdvertisementDirectionNotEligibleError(InvalidStateError):
    error_code = ErrorCode.ADVERTISEMENT_DIRECTION_NOT_ELIGIBLE
    default_message = "This direction is not valid (not found or inactive)."


__all__ = [
    "AdvertisementAlreadyActiveError",
    "AdvertisementCancelledError",
    "AdvertisementClosedError",
    "AdvertisementDirectionNotEligibleError",
    "AdvertisementDriverNotEligibleError",
    "AdvertisementExpiredError",
    "AdvertisementFullError",
    "AdvertisementInsufficientSeatsError",
    "AdvertisementInvalidDataError",
    "AdvertisementInvalidStatusTransitionError",
    "AdvertisementNotFoundError",
    "AdvertisementSeatLimitExceededError",
    "AdvertisementVehicleNotEligibleError",
]
