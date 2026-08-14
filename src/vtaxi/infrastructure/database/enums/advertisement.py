"""See docs/03-DATABASE-DESIGN.md SS2.4, table `advertisements`."""

from enum import StrEnum


class AdvertisementStatus(StrEnum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    FULL = "FULL"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"
