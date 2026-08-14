"""See docs/03-DATABASE-DESIGN.md SS2.4, table `trips`.

`TripStatus` extended from 3 values to 6: a Trip row can now exist before
the driver actually departs (SCHEDULED once enough bookings are accepted,
READY once the driver is positioned to start), so STARTED is no longer
the initial state. `BoardingStatus` is new, for `trip_passengers`.
"""

from enum import StrEnum


class TripStatus(StrEnum):
    SCHEDULED = "SCHEDULED"
    READY = "READY"
    STARTED = "STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class BoardingStatus(StrEnum):
    WAITING = "WAITING"
    BOARDED = "BOARDED"
    DROPPED_OFF = "DROPPED_OFF"
    NO_SHOW = "NO_SHOW"
