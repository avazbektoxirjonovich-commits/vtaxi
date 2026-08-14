"""User-specific domain exceptions. See core/domain/exceptions.py for the
shared `NotFoundError`/`AlreadyExistsError`/`InvalidStateError` bases.
"""

from vtaxi.core.domain.error_codes import ErrorCode
from vtaxi.core.domain.exceptions import AlreadyExistsError, InvalidStateError, NotFoundError


class UserNotFoundError(NotFoundError):
    error_code = ErrorCode.USER_NOT_FOUND
    default_message = "User not found."


class UserAlreadyExistsError(AlreadyExistsError):
    error_code = ErrorCode.USER_ALREADY_EXISTS
    default_message = "A user with these identifying details already exists."


class UserBannedError(InvalidStateError):
    error_code = ErrorCode.USER_BANNED
    default_message = "This user account has been banned."


class UserInactiveError(InvalidStateError):
    error_code = ErrorCode.USER_INACTIVE
    default_message = "This user account is inactive."


__all__ = [
    "UserAlreadyExistsError",
    "UserBannedError",
    "UserInactiveError",
    "UserNotFoundError",
]
