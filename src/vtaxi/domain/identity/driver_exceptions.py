"""Driver-specific domain exceptions (the `DriverProfile` extension, not
`User` itself -- see user_exceptions.py for that).
"""

from vtaxi.core.domain.error_codes import ErrorCode
from vtaxi.core.domain.exceptions import AlreadyExistsError, InvalidStateError, NotFoundError


class DriverNotFoundError(NotFoundError):
    error_code = ErrorCode.DRIVER_NOT_FOUND
    default_message = "Driver profile not found."


class DriverAlreadyExistsError(AlreadyExistsError):
    error_code = ErrorCode.DRIVER_ALREADY_EXISTS
    default_message = "This user already has a driver profile."


class DriverNotVerifiedError(InvalidStateError):
    error_code = ErrorCode.DRIVER_NOT_VERIFIED
    default_message = "This driver has not been verified by an admin yet."


class DriverAlreadyVerifiedError(InvalidStateError):
    """Added in Step 8.1: `DriverService.verify_driver()` needs this guard,
    and no existing code covered "already verified" (the opposite of
    `DriverNotVerifiedError`).
    """

    error_code = ErrorCode.DRIVER_ALREADY_VERIFIED
    default_message = "This driver has already been verified."


class DriverBannedError(InvalidStateError):
    error_code = ErrorCode.DRIVER_BANNED
    default_message = "This driver has been banned."


__all__ = [
    "DriverAlreadyExistsError",
    "DriverAlreadyVerifiedError",
    "DriverBannedError",
    "DriverNotFoundError",
    "DriverNotVerifiedError",
]
