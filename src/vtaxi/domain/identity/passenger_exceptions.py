"""Passenger-specific domain exceptions (the `PassengerProfile` extension,
not `User` itself -- see user_exceptions.py for that).
"""

from vtaxi.core.domain.error_codes import ErrorCode
from vtaxi.core.domain.exceptions import AlreadyExistsError, InvalidStateError, NotFoundError


class PassengerNotFoundError(NotFoundError):
    error_code = ErrorCode.PASSENGER_NOT_FOUND
    default_message = "Passenger profile not found."


class PassengerAlreadyExistsError(AlreadyExistsError):
    """Added in Step 8.1 for `PassengerService.create_passenger_profile()` --
    analogous to `UserAlreadyExistsError`/`DriverAlreadyExistsError`, missed
    when this module was first written.
    """

    error_code = ErrorCode.PASSENGER_ALREADY_EXISTS
    default_message = "This user already has a passenger profile."


class PassengerBlockedError(InvalidStateError):
    error_code = ErrorCode.PASSENGER_BLOCKED
    default_message = "This passenger has been blocked."


__all__ = ["PassengerAlreadyExistsError", "PassengerBlockedError", "PassengerNotFoundError"]
