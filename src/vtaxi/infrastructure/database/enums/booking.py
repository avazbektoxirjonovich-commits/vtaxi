"""See docs/03-DATABASE-DESIGN.md SS2.4, table `bookings`.

Extended from the original 5 values to 7: `RESERVED` and `EXPIRED` are new,
splitting "request submitted" (PENDING, no seat held) from "seat held"
(RESERVED, bounded by `reserved_until`) per the Booking domain's
reservation model.
"""

from enum import StrEnum


class BookingStatus(StrEnum):
    PENDING = "PENDING"
    RESERVED = "RESERVED"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"
    COMPLETED = "COMPLETED"
