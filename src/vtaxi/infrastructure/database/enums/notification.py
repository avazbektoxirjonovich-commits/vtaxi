"""See docs/03-DATABASE-DESIGN.md SS2.5, table `notifications`."""

from enum import StrEnum


class NotificationChannel(StrEnum):
    """Only TELEGRAM has a live sender today; the rest are reserved values."""

    TELEGRAM = "TELEGRAM"
    PUSH = "PUSH"
    SMS = "SMS"
    EMAIL = "EMAIL"


class NotificationStatus(StrEnum):
    """`delivery_status` column values. DELIVERED is new -- distinct from
    SENT (left this system) and READ (the user opened it).
    """

    PENDING = "PENDING"
    SENT = "SENT"
    DELIVERED = "DELIVERED"
    READ = "READ"
    FAILED = "FAILED"


class NotificationType(StrEnum):
    """What kind of event this is, independent of `NotificationChannel`
    (how it's delivered).
    """

    SYSTEM = "SYSTEM"
    BOOKING = "BOOKING"
    ADVERTISEMENT = "ADVERTISEMENT"
    TRIP = "TRIP"
    PAYMENT = "PAYMENT"
    SECURITY = "SECURITY"
    WARNING = "WARNING"
    PROMOTION = "PROMOTION"
