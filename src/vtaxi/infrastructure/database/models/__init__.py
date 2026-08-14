"""ORM models (SQLAlchemy 2.0 declarative), one module per bounded context.

Every model is imported here so `Base.metadata` is fully populated before
anything inspects it -- Alembic's `env.py` in particular (see
`migrations/env.py`), which otherwise would only see whichever model
modules happened to already be imported elsewhere.
"""

from vtaxi.infrastructure.database.models.advertisement import (
    Advertisement,
    AdvertisementStatusHistory,
)
from vtaxi.infrastructure.database.models.audit import AuditLog
from vtaxi.infrastructure.database.models.booking import Booking, BookingStatusHistory
from vtaxi.infrastructure.database.models.complaint import Complaint
from vtaxi.infrastructure.database.models.geography import AdministrativeArea, Direction
from vtaxi.infrastructure.database.models.identity import (
    AdminProfile,
    DriverProfile,
    PassengerProfile,
    User,
)
from vtaxi.infrastructure.database.models.notification import Notification
from vtaxi.infrastructure.database.models.rating import Rating
from vtaxi.infrastructure.database.models.trip import Trip, TripPassenger, TripStatusHistory
from vtaxi.infrastructure.database.models.vehicle import (
    DriverDocument,
    Vehicle,
    VehicleDocument,
    VehiclePhoto,
)

__all__ = [
    "AdministrativeArea",
    "AdminProfile",
    "Advertisement",
    "AdvertisementStatusHistory",
    "AuditLog",
    "Booking",
    "BookingStatusHistory",
    "Complaint",
    "Direction",
    "DriverDocument",
    "DriverProfile",
    "Notification",
    "PassengerProfile",
    "Rating",
    "Trip",
    "TripPassenger",
    "TripStatusHistory",
    "User",
    "Vehicle",
    "VehicleDocument",
    "VehiclePhoto",
]
