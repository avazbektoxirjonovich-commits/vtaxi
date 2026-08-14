"""See docs/03-DATABASE-DESIGN.md SS2.5, tables `complaints`, `complaint_evidence`."""

from enum import StrEnum


class ComplaintReason(StrEnum):
    DRIVER_MISCONDUCT = "DRIVER_MISCONDUCT"
    PASSENGER_MISCONDUCT = "PASSENGER_MISCONDUCT"
    VEHICLE_CONDITION = "VEHICLE_CONDITION"
    SAFETY_CONCERN = "SAFETY_CONCERN"
    PAYMENT_DISPUTE = "PAYMENT_DISPUTE"
    NO_SHOW = "NO_SHOW"
    OTHER = "OTHER"


class ComplaintStatus(StrEnum):
    OPEN = "OPEN"
    UNDER_REVIEW = "UNDER_REVIEW"
    RESOLVED = "RESOLVED"
    DISMISSED = "DISMISSED"


class ComplaintResolutionAction(StrEnum):
    """NONE/WARNING leave availability_status/passenger_status untouched;
    only BAN flips it -- see docs/03-DATABASE-DESIGN.md SS2.5 and SS6 item 4.
    """

    NONE = "NONE"
    WARNING = "WARNING"
    BAN = "BAN"


class EvidenceFileType(StrEnum):
    PHOTO = "PHOTO"
    VIDEO = "VIDEO"
    DOCUMENT = "DOCUMENT"
