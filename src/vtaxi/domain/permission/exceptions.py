"""Permission domain exceptions -- verifying *what* an already-identified
actor is allowed to do. See domain/authentication/exceptions.py for *who*
they are.
"""

from vtaxi.core.domain.error_codes import ErrorCode
from vtaxi.core.domain.exceptions import BaseDomainException


class PermissionDeniedError(BaseDomainException):
    error_code = ErrorCode.PERMISSION_DENIED
    default_message = "You do not have permission to perform this action."


class InsufficientRoleError(BaseDomainException):
    error_code = ErrorCode.INSUFFICIENT_ROLE
    default_message = "Your role does not permit this action."


__all__ = ["InsufficientRoleError", "PermissionDeniedError"]
