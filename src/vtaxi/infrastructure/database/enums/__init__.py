"""Shared enum vocabulary, one module per bounded context.

Pure Python enums only -- no tables, no models. Values match the approved
column specs in docs/03-DATABASE-DESIGN.md exactly; nothing here should
need to change when a future model attaches one to a real column via
Base.type_annotation_map's Enum wildcard entry (see database/types.py).
"""

from vtaxi.infrastructure.database.enums.admin import AdminRole
from vtaxi.infrastructure.database.enums.advertisement import AdvertisementStatus
from vtaxi.infrastructure.database.enums.audit import AuditAction
from vtaxi.infrastructure.database.enums.booking import BookingStatus
from vtaxi.infrastructure.database.enums.complaint import (
    ComplaintReason,
    ComplaintResolutionAction,
    ComplaintStatus,
    EvidenceFileType,
)
from vtaxi.infrastructure.database.enums.driver import (
    DriverApprovalStatus,
    DriverAvailabilityStatus,
)
from vtaxi.infrastructure.database.enums.geography import AdministrativeAreaLevel
from vtaxi.infrastructure.database.enums.identity import UserRole
from vtaxi.infrastructure.database.enums.notification import (
    NotificationChannel,
    NotificationStatus,
    NotificationType,
)
from vtaxi.infrastructure.database.enums.passenger import PassengerStatus
from vtaxi.infrastructure.database.enums.roles import PartyRole
from vtaxi.infrastructure.database.enums.trip import BoardingStatus, TripStatus
from vtaxi.infrastructure.database.enums.vehicle import (
    DriverDocumentType,
    VehicleClass,
    VehicleDocumentType,
    VehiclePhotoType,
    VerificationStatus,
)

__all__ = [
    "AdminRole",
    "AdministrativeAreaLevel",
    "AdvertisementStatus",
    "AuditAction",
    "BoardingStatus",
    "BookingStatus",
    "ComplaintReason",
    "ComplaintResolutionAction",
    "ComplaintStatus",
    "DriverApprovalStatus",
    "DriverAvailabilityStatus",
    "DriverDocumentType",
    "EvidenceFileType",
    "NotificationChannel",
    "NotificationStatus",
    "NotificationType",
    "PartyRole",
    "PassengerStatus",
    "TripStatus",
    "UserRole",
    "VehicleClass",
    "VehicleDocumentType",
    "VehiclePhotoType",
    "VerificationStatus",
]
