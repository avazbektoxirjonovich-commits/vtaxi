"""Authentication domain exceptions -- verifying *who* is making a
request. See domain/permission/exceptions.py for *what* they're allowed
to do once identified.
"""

from vtaxi.core.domain.error_codes import ErrorCode
from vtaxi.core.domain.exceptions import BaseDomainException, InvalidStateError


class AuthenticationFailedError(BaseDomainException):
    error_code = ErrorCode.AUTHENTICATION_FAILED
    default_message = "Authentication failed."


class InvalidCredentialsError(BaseDomainException):
    error_code = ErrorCode.INVALID_CREDENTIALS
    default_message = "The provided credentials are invalid."


class SessionExpiredError(InvalidStateError):
    error_code = ErrorCode.SESSION_EXPIRED
    default_message = "The session has expired; please authenticate again."


__all__ = ["AuthenticationFailedError", "InvalidCredentialsError", "SessionExpiredError"]
