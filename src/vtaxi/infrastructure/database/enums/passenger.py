"""See docs/03-DATABASE-DESIGN.md SS2.1, table `passenger_profiles`."""

from enum import StrEnum


class PassengerStatus(StrEnum):
    """Event-derived projection -- see docs/01 SS14.4. Never set directly."""

    ACTIVE = "ACTIVE"
    WAITING = "WAITING"
    BOOKED = "BOOKED"
    ON_TRIP = "ON_TRIP"
    COMPLETED = "COMPLETED"
    BANNED = "BANNED"
