"""Geo Engine domain exceptions -- distance calculation, location
normalization ("Location" in this step's brief).
"""

from vtaxi.core.domain.error_codes import ErrorCode
from vtaxi.core.domain.exceptions import BaseDomainException, InvalidStateError


class LocationNotSupportedError(InvalidStateError):
    error_code = ErrorCode.LOCATION_NOT_SUPPORTED
    default_message = "This location is not currently supported."


class InvalidCoordinatesError(BaseDomainException):
    error_code = ErrorCode.INVALID_COORDINATES
    default_message = "The provided coordinates are invalid."


__all__ = ["InvalidCoordinatesError", "LocationNotSupportedError"]
