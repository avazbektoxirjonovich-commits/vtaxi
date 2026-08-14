"""See docs/03-DATABASE-DESIGN.md SS2.3: `vehicles`, `vehicle_documents`, `driver_documents`."""

from enum import StrEnum


class VehicleClass(StrEnum):
    ECONOMY = "ECONOMY"
    COMFORT = "COMFORT"
    BUSINESS = "BUSINESS"
    MINIVAN = "MINIVAN"


class VerificationStatus(StrEnum):
    """Shared by `vehicles`, `vehicle_documents`, and `driver_documents`."""

    PENDING_REVIEW = "PENDING_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class VehicleDocumentType(StrEnum):
    """No PHOTO value: superseded by the dedicated `VehiclePhoto` model and
    `VehiclePhotoType` -- keeping both would be two conflicting ways to
    represent "a photo of the vehicle".
    """

    REGISTRATION = "REGISTRATION"
    INSURANCE = "INSURANCE"
    TECHNICAL_INSPECTION = "TECHNICAL_INSPECTION"


class DriverDocumentType(StrEnum):
    LICENSE = "LICENSE"
    PROFILE_PHOTO = "PROFILE_PHOTO"
    PASSPORT = "PASSPORT"
    ID_CARD = "ID_CARD"


class VehiclePhotoType(StrEnum):
    FRONT = "FRONT"
    BACK = "BACK"
    LEFT = "LEFT"
    RIGHT = "RIGHT"
    INTERIOR = "INTERIOR"
