"""Geography domain exceptions (`AdministrativeArea`/`Direction`)."""

from vtaxi.core.domain.error_codes import ErrorCode
from vtaxi.core.domain.exceptions import AlreadyExistsError, InvalidStateError, NotFoundError


class GeographyNotFoundError(NotFoundError):
    error_code = ErrorCode.GEOGRAPHY_NOT_FOUND
    default_message = "Administrative area not found."


class InvalidHierarchyError(InvalidStateError):
    """Added in Step 8.2 for `GeographyService.validate_hierarchy()` --
    covers "Country cannot have a parent," "a child area's level must sit
    below its parent's in the COUNTRY..STREET ordering," and "every
    non-COUNTRY area must have a parent." No prior code covered any of
    these.
    """

    error_code = ErrorCode.INVALID_HIERARCHY_LEVEL
    default_message = "This parent/level combination is not a valid administrative hierarchy."


class DirectionNotFoundError(NotFoundError):
    error_code = ErrorCode.DIRECTION_NOT_FOUND
    default_message = "Direction not found."


class DirectionAlreadyExistsError(AlreadyExistsError):
    """Added in Step 8.2 for `GeographyService.create_direction()` --
    analogous to `UserAlreadyExistsError`/`DriverAlreadyExistsError`, no
    prior code covered a duplicate (origin, destination) pair.
    """

    error_code = ErrorCode.DIRECTION_ALREADY_EXISTS
    default_message = "A direction between these two areas already exists."


class DirectionNotSupportedError(InvalidStateError):
    error_code = ErrorCode.DIRECTION_NOT_SUPPORTED
    default_message = "This direction is not currently supported."


__all__ = [
    "DirectionAlreadyExistsError",
    "DirectionNotFoundError",
    "DirectionNotSupportedError",
    "GeographyNotFoundError",
    "InvalidHierarchyError",
]
