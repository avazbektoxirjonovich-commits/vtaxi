"""Matching domain exceptions."""

from vtaxi.core.domain.error_codes import ErrorCode
from vtaxi.core.domain.exceptions import BaseDomainException, NotFoundError


class MatchingNotFoundError(NotFoundError):
    error_code = ErrorCode.MATCHING_NOT_FOUND
    default_message = "No matching advertisement was found."


class NoAvailableDriversError(BaseDomainException):
    error_code = ErrorCode.NO_AVAILABLE_DRIVERS
    default_message = "No drivers are currently available for this request."


__all__ = ["MatchingNotFoundError", "NoAvailableDriversError"]
