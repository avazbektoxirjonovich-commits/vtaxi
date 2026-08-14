"""Rating domain exceptions.

The two raised in Step 7.5 (`NotFound`/`AlreadyExists`) are kept as-is --
`RatingAlreadyExistsError` is exactly "duplicate ratings are forbidden" /
"one rating per booking per role," already available, not re-invented
here. Step 8.7 (`RatingService`) adds the rest: a data-validation
catch-all (score out of range, or a `ValueError` from `Rating`'s own
`@validates` hook), a self-rating guard, a trip-eligibility error
("only completed rides may be rated" -- one class, covers both "trip
does not exist" and "trip not yet completed," same pattern established
in Steps 8.4-8.6), and a booking-not-found error (no eligibility nuance
beyond existence, so a plain `NotFoundError`, unlike the trip check).
"""

from vtaxi.core.domain.error_codes import ErrorCode
from vtaxi.core.domain.exceptions import (
    AlreadyExistsError,
    BaseDomainException,
    InvalidStateError,
    NotFoundError,
)


class RatingNotFoundError(NotFoundError):
    error_code = ErrorCode.RATING_NOT_FOUND
    default_message = "Rating not found."


class RatingAlreadyExistsError(AlreadyExistsError):
    error_code = ErrorCode.RATING_ALREADY_EXISTS
    default_message = "This booking has already been rated by this party."


class RatingInvalidDataError(BaseDomainException):
    error_code = ErrorCode.RATING_INVALID_DATA
    default_message = "The provided rating data is invalid."


class RatingSelfRatingError(InvalidStateError):
    error_code = ErrorCode.RATING_SELF_RATING
    default_message = "A user cannot rate themselves."


class RatingTripNotEligibleError(InvalidStateError):
    error_code = ErrorCode.RATING_TRIP_NOT_ELIGIBLE
    default_message = "Only a completed trip may be rated."


class RatingBookingNotFoundError(NotFoundError):
    error_code = ErrorCode.RATING_BOOKING_NOT_FOUND
    default_message = "The given booking does not exist."


__all__ = [
    "RatingAlreadyExistsError",
    "RatingBookingNotFoundError",
    "RatingInvalidDataError",
    "RatingNotFoundError",
    "RatingSelfRatingError",
    "RatingTripNotEligibleError",
]
