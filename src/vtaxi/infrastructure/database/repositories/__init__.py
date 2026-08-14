"""Repository layer: persistence-only data access, one repository per
bounded context's primary aggregate, plus the Generic/Base engine,
Unit of Work, and factory that tie them together.
"""

from vtaxi.infrastructure.database.repositories.advertisement import AdvertisementRepository
from vtaxi.infrastructure.database.repositories.audit import AuditRepository
from vtaxi.infrastructure.database.repositories.base import BaseRepository
from vtaxi.infrastructure.database.repositories.booking import BookingRepository
from vtaxi.infrastructure.database.repositories.complaint import ComplaintRepository
from vtaxi.infrastructure.database.repositories.factory import RepositoryFactory
from vtaxi.infrastructure.database.repositories.generic import GenericRepository, Page
from vtaxi.infrastructure.database.repositories.geography import GeographyRepository
from vtaxi.infrastructure.database.repositories.identity import (
    DriverRepository,
    PassengerRepository,
    UserRepository,
)
from vtaxi.infrastructure.database.repositories.notification import NotificationRepository
from vtaxi.infrastructure.database.repositories.protocols import RepositoryProtocol
from vtaxi.infrastructure.database.repositories.rating import RatingRepository
from vtaxi.infrastructure.database.repositories.trip import TripRepository
from vtaxi.infrastructure.database.repositories.unit_of_work import UnitOfWork
from vtaxi.infrastructure.database.repositories.vehicle import VehicleRepository

__all__ = [
    "AdvertisementRepository",
    "AuditRepository",
    "BaseRepository",
    "BookingRepository",
    "ComplaintRepository",
    "DriverRepository",
    "GenericRepository",
    "GeographyRepository",
    "NotificationRepository",
    "Page",
    "PassengerRepository",
    "RatingRepository",
    "RepositoryFactory",
    "RepositoryProtocol",
    "TripRepository",
    "UnitOfWork",
    "UserRepository",
    "VehicleRepository",
]
