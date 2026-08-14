"""Complaint-context ports: what `ComplaintService` needs from a
repository/Unit of Work, expressed as `Protocol`s.

Same departure from precedent as `application/rating/ports.py` -- see
that module's docstring for the full reasoning (Step 8.7's brief
explicitly forbids importing SQLAlchemy ORM models anywhere in the
Application Layer, stricter than every prior step). `ComplaintRecord`/
`TripRecord`/`BookingRecord`/`UserRecord` are plain structural `Protocol`s;
the real `Complaint`/`Trip`/`Booking`/`User` ORM classes satisfy them
automatically (PEP 544) without being imported here.
"""

import uuid
from collections.abc import Sequence
from datetime import datetime
from typing import Any, Protocol

from vtaxi.infrastructure.database.enums import (
    ComplaintReason,
    ComplaintResolutionAction,
    ComplaintStatus,
)


class ComplaintRecord(Protocol):
    id: uuid.UUID
    reporter_user_id: uuid.UUID
    target_user_id: uuid.UUID
    trip_id: uuid.UUID | None
    booking_id: uuid.UUID | None
    complaint_type: ComplaintReason
    title: str
    description: str
    evidence_url: str | None
    complaint_status: ComplaintStatus
    resolution_action: ComplaintResolutionAction
    resolved_by_admin_id: uuid.UUID | None
    resolved_at: datetime | None
    resolution_note: str | None
    created_at: datetime
    updated_at: datetime


class TripRecord(Protocol):
    """Only existence is ever checked -- no other attribute of a `Trip` is
    read by `ComplaintService`.
    """

    id: uuid.UUID


class BookingRecord(Protocol):
    """Only existence is ever checked -- no other attribute of a `Booking`
    is read by `ComplaintService`.
    """

    id: uuid.UUID


class UserRecord(Protocol):
    """Only existence is ever checked, for `reporter_user_id`/
    `target_user_id`.
    """

    id: uuid.UUID


class ComplaintRepositoryProtocol(Protocol):
    async def get_by_id(self, id_: Any) -> ComplaintRecord | None: ...
    async def create(self, **values: Any) -> ComplaintRecord: ...
    async def update(self, instance: Any, **values: Any) -> ComplaintRecord: ...
    async def list_by_status(self, status: ComplaintStatus) -> Sequence[ComplaintRecord]: ...
    async def list_by_target_user_id(
        self, target_user_id: uuid.UUID
    ) -> Sequence[ComplaintRecord]: ...
    async def list_by_reporter_user_id(
        self, reporter_user_id: uuid.UUID
    ) -> Sequence[ComplaintRecord]: ...
    async def list_by_trip_id(self, trip_id: uuid.UUID) -> Sequence[ComplaintRecord]: ...
    async def list_by_booking_id(self, booking_id: uuid.UUID) -> Sequence[ComplaintRecord]: ...


class TripReadProtocol(Protocol):
    """Read-only -- `TripService` (Step 8.6) owns every write to a `Trip`."""

    async def get_by_id(self, id_: Any) -> TripRecord | None: ...


class BookingReadProtocol(Protocol):
    """Read-only -- `BookingService` (Step 8.5) owns every write to a
    `Booking`.
    """

    async def get_by_id(self, id_: Any) -> BookingRecord | None: ...


class UserReadProtocol(Protocol):
    """Read-only -- `UserService` (Step 8.1) owns every write to a `User`."""

    async def get_by_id(self, id_: Any) -> UserRecord | None: ...


class ComplaintUnitOfWork(Protocol):
    """What `ComplaintService` needs from a Unit of Work: its own
    repository (read-write) plus three collaborating repositories
    (read-only), and the commit-on-success/rollback-on-exception async
    context manager every service method opens one of via a
    `core.application.UnitOfWorkFactory`.
    """

    complaints: ComplaintRepositoryProtocol
    trips: TripReadProtocol
    bookings: BookingReadProtocol
    users: UserReadProtocol

    async def __aenter__(self) -> "ComplaintUnitOfWork": ...

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None: ...


__all__ = [
    "BookingReadProtocol",
    "BookingRecord",
    "ComplaintRecord",
    "ComplaintRepositoryProtocol",
    "ComplaintUnitOfWork",
    "TripReadProtocol",
    "TripRecord",
    "UserReadProtocol",
    "UserRecord",
]
