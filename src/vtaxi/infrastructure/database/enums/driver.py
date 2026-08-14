"""See docs/03-DATABASE-DESIGN.md SS2.1, table `driver_profiles`."""

from enum import StrEnum


class DriverApprovalStatus(StrEnum):
    """The one-time verification gate -- can this driver publish at all."""

    PENDING_REVIEW = "PENDING_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class DriverAvailabilityStatus(StrEnum):
    """Operational visibility for Matching -- orthogonal to approval_status."""

    ONLINE = "ONLINE"
    OFFLINE = "OFFLINE"
    BUSY = "BUSY"
    ON_TRIP = "ON_TRIP"
    BANNED = "BANNED"
