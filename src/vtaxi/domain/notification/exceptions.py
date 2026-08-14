"""Notification domain exceptions."""

from vtaxi.core.domain.error_codes import ErrorCode
from vtaxi.core.domain.exceptions import BaseDomainException, NotFoundError


class NotificationNotFoundError(NotFoundError):
    error_code = ErrorCode.NOTIFICATION_NOT_FOUND
    default_message = "Notification not found."


class NotificationDeliveryFailedError(BaseDomainException):
    error_code = ErrorCode.NOTIFICATION_DELIVERY_FAILED
    default_message = "The notification could not be delivered."


__all__ = ["NotificationDeliveryFailedError", "NotificationNotFoundError"]
