"""Trip domain exceptions.

The four raised in Step 7.5 (`NotFound`/`AlreadyStarted`/`Completed`/
`Cancelled`) are kept as-is. Step 8.6 (`TripService`) adds the rest:
`AlreadyExists` (one Trip per Advertisement), five cross-domain
eligibility errors (advertisement/driver/vehicle/booking/passenger)
mirroring the pattern established in Steps 8.4/8.5 -- one class covers
both "the referenced row does not exist" and "it exists but fails the
eligibility check" -- plus a generic invalid-transition catch-all, a
not-found for the `TripPassenger` join row specifically (distinct from
`TripBookingNotEligibleError`, which is about the `Booking` itself), and
a boarding-specific invalid-transition error for `board_passenger`/
`drop_off_passenger`/`mark_no_show`'s shared state-machine guards.
"""

from vtaxi.core.domain.error_codes import ErrorCode
from vtaxi.core.domain.exceptions import AlreadyExistsError, InvalidStateError, NotFoundError


class TripNotFoundError(NotFoundError):
    error_code = ErrorCode.TRIP_NOT_FOUND
    default_message = "Trip not found."


class TripAlreadyStartedError(InvalidStateError):
    error_code = ErrorCode.TRIP_ALREADY_STARTED
    default_message = "This trip has already started."


class TripCompletedError(InvalidStateError):
    error_code = ErrorCode.TRIP_COMPLETED
    default_message = "This trip has already been completed."


class TripCancelledError(InvalidStateError):
    error_code = ErrorCode.TRIP_CANCELLED
    default_message = "This trip has been cancelled."


class TripAlreadyExistsError(AlreadyExistsError):
    error_code = ErrorCode.TRIP_ALREADY_EXISTS
    default_message = "A trip already exists for this advertisement."


class TripAdvertisementNotEligibleError(InvalidStateError):
    error_code = ErrorCode.TRIP_ADVERTISEMENT_NOT_ELIGIBLE
    default_message = "The given advertisement does not exist."


class TripDriverNotEligibleError(InvalidStateError):
    error_code = ErrorCode.TRIP_DRIVER_NOT_ELIGIBLE
    default_message = (
        "This driver is not eligible for this trip "
        "(not found, not approved, banned, or does not own the advertisement)."
    )


class TripVehicleNotEligibleError(InvalidStateError):
    error_code = ErrorCode.TRIP_VEHICLE_NOT_ELIGIBLE
    default_message = (
        "This vehicle is not eligible for this trip (not found, deleted, or not approved)."
    )


class TripBookingNotEligibleError(InvalidStateError):
    error_code = ErrorCode.TRIP_BOOKING_NOT_ELIGIBLE
    default_message = (
        "This booking is not eligible to join the trip "
        "(not found, not ACCEPTED, wrong advertisement, or already added)."
    )


class TripPassengerNotEligibleError(InvalidStateError):
    error_code = ErrorCode.TRIP_PASSENGER_NOT_ELIGIBLE
    default_message = (
        "This passenger is not eligible for this trip (not found, deleted, or banned)."
    )


class TripNoPassengersError(InvalidStateError):
    error_code = ErrorCode.TRIP_NO_PASSENGERS
    default_message = "A trip cannot start without at least one passenger."


class TripInvalidStatusTransitionError(InvalidStateError):
    """Generic status-machine guard for a transition not covered by one of
    the more specific errors above (e.g. finishing a trip that hasn't
    started, adding/removing a passenger after departure).
    """

    error_code = ErrorCode.TRIP_INVALID_STATUS_TRANSITION
    default_message = "This trip is not in a state that allows this transition."


class TripPassengerNotFoundError(NotFoundError):
    """The `TripPassenger` join row for a given (trip, booking) pair does
    not exist -- distinct from `TripBookingNotEligibleError`, which is
    about the underlying `Booking` never having been eligible to join in
    the first place.
    """

    error_code = ErrorCode.TRIP_PASSENGER_NOT_FOUND
    default_message = "This passenger has not been added to this trip."


class TripBoardingInvalidTransitionError(InvalidStateError):
    """Shared by `board_passenger`/`drop_off_passenger`/`mark_no_show`'s
    guards -- "cannot board twice," "cannot drop off before boarding,"
    "a no-show cannot board" -- one class, message varies (same pattern as
    Vehicle's `InvalidDocumentStatusTransitionError`).
    """

    error_code = ErrorCode.TRIP_BOARDING_INVALID_TRANSITION
    default_message = "This passenger is not in a boarding state that allows this transition."


__all__ = [
    "TripAdvertisementNotEligibleError",
    "TripAlreadyExistsError",
    "TripAlreadyStartedError",
    "TripBoardingInvalidTransitionError",
    "TripBookingNotEligibleError",
    "TripCancelledError",
    "TripCompletedError",
    "TripDriverNotEligibleError",
    "TripInvalidStatusTransitionError",
    "TripNoPassengersError",
    "TripNotFoundError",
    "TripPassengerNotEligibleError",
    "TripPassengerNotFoundError",
    "TripVehicleNotEligibleError",
]
