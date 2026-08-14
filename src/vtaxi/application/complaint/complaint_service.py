"""`ComplaintService` -- passenger/driver moderation intake, and the
OPEN/UNDER_REVIEW/RESOLVED/DISMISSED status machine.

Every method opens its own Unit of Work via the injected factory and is
therefore independently atomic, same discipline as every service so far.
**Zero SQLAlchemy or ORM model import, including for typing** -- see
`ports.py`'s docstring (and `application/rating/ports.py`'s, which
explains the reasoning in full) for why this step draws a stricter line
than every prior one.

Status machine, as implemented here:

    OPEN --close_complaint()--> UNDER_REVIEW
      |                              |
      +---------resolve_complaint()--+------> RESOLVED (terminal)
      |                              |
      +---------reject_complaint()---+------> DISMISSED (terminal)

`ComplaintStatus` has exactly three non-initial values (`UNDER_REVIEW`/
`RESOLVED`/`DISMISSED`) and this step's brief names exactly three
transition methods (`close_complaint`/`resolve_complaint`/
`reject_complaint`) beyond `create_complaint()` -- a clean 1:1 mapping.
`close_complaint()` maps onto `UNDER_REVIEW` specifically: the brief's
"close" vocabulary describes closing out the open intake queue and
moving the complaint into active admin handling, not a fourth terminal
status the schema does not have. `resolve_complaint()`/
`reject_complaint()` are each allowed from *either* `OPEN` or
`UNDER_REVIEW` (both count as "unresolved," the brief's own wording for
resolve's precondition), not gated behind having gone through
`close_complaint()` first.

Not implemented, deliberately: flipping `DriverProfile.availability_status`/
`PassengerProfile.passenger_status` to `BANNED` when `resolve_complaint()`
is called with `resolution_action=BAN`. `models/complaint.py`'s own
docstring calls `resolution_action` "the only path that flips
availability_status/passenger_status to BANNED" as a *future* concern;
doing it here would mean injecting `DriverService`/`PassengerService`
(mirroring `BookingService`'s dependency on `AdvertisementService`), and
this step's brief names no such responsibility -- flagged, not built,
same discipline `TripService` applied to the Advertisement/Booking
write-backs it also left out.
"""

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

from vtaxi.core.application import UnitOfWorkFactory, fail
from vtaxi.core.domain import Result
from vtaxi.core.domain.result import Failure
from vtaxi.domain.complaint.exceptions import (
    ComplaintAlreadyResolvedError,
    ComplaintDismissedError,
    ComplaintInvalidDataError,
    ComplaintNotFoundError,
    ComplaintReferenceNotFoundError,
)
from vtaxi.infrastructure.database.enums import (
    ComplaintReason,
    ComplaintResolutionAction,
    ComplaintStatus,
)

from .ports import ComplaintRecord, ComplaintUnitOfWork


class ComplaintService:
    def __init__(self, uow_factory: UnitOfWorkFactory[ComplaintUnitOfWork]) -> None:
        self._uow_factory = uow_factory

    # --- Validation (private helpers) -------------------------------------

    async def _fetch_complaint(
        self, complaint_id: uuid.UUID, uow: ComplaintUnitOfWork
    ) -> ComplaintRecord | Failure:
        complaint = await uow.complaints.get_by_id(complaint_id)
        if complaint is None:
            return fail(ComplaintNotFoundError)
        return complaint

    async def _reference_violation(
        self,
        trip_id: uuid.UUID | None,
        booking_id: uuid.UUID | None,
        uow: ComplaintUnitOfWork,
    ) -> Failure | None:
        if trip_id is None and booking_id is None:
            return fail(
                ComplaintInvalidDataError, "A complaint must reference a valid Booking or Trip."
            )
        if trip_id is not None and await uow.trips.get_by_id(trip_id) is None:
            return fail(ComplaintReferenceNotFoundError, "The given trip does not exist.")
        if booking_id is not None and await uow.bookings.get_by_id(booking_id) is None:
            return fail(ComplaintReferenceNotFoundError, "The given booking does not exist.")
        return None

    async def _user_violation(
        self, user_id: uuid.UUID, uow: ComplaintUnitOfWork, *, role: str
    ) -> Failure | None:
        if await uow.users.get_by_id(user_id) is None:
            return fail(ComplaintInvalidDataError, f"The given {role} user does not exist.")
        return None

    # --- Validation (public) ---------------------------------------------

    async def validate_complaint(
        self,
        *,
        reporter_user_id: uuid.UUID,
        target_user_id: uuid.UUID,
        trip_id: uuid.UUID | None = None,
        booking_id: uuid.UUID | None = None,
    ) -> Result[None]:
        async with self._uow_factory() as uow:
            violation = await self._reference_violation(trip_id, booking_id, uow)
            if violation is not None:
                return violation
            violation = await self._user_violation(reporter_user_id, uow, role="reporter")
            if violation is not None:
                return violation
            violation = await self._user_violation(target_user_id, uow, role="target")
            if violation is not None:
                return violation
            return Result.ok(None)

    async def can_submit_complaint(
        self, *, trip_id: uuid.UUID | None = None, booking_id: uuid.UUID | None = None
    ) -> Result[bool]:
        if trip_id is None and booking_id is None:
            raise ValueError("can_submit_complaint() requires trip_id or booking_id")
        async with self._uow_factory() as uow:
            if trip_id is not None and await uow.trips.get_by_id(trip_id) is None:
                return Result.ok(False)
            if booking_id is not None and await uow.bookings.get_by_id(booking_id) is None:
                return Result.ok(False)
            return Result.ok(True)

    # --- Complaint Management ------------------------------------------

    async def create_complaint(
        self,
        *,
        reporter_user_id: uuid.UUID,
        target_user_id: uuid.UUID,
        complaint_type: ComplaintReason,
        title: str,
        description: str,
        trip_id: uuid.UUID | None = None,
        booking_id: uuid.UUID | None = None,
        evidence_url: str | None = None,
    ) -> Result[ComplaintRecord]:
        async with self._uow_factory() as uow:
            violation = await self._reference_violation(trip_id, booking_id, uow)
            if violation is not None:
                return violation
            violation = await self._user_violation(reporter_user_id, uow, role="reporter")
            if violation is not None:
                return violation
            violation = await self._user_violation(target_user_id, uow, role="target")
            if violation is not None:
                return violation

            try:
                complaint = await uow.complaints.create(
                    reporter_user_id=reporter_user_id,
                    target_user_id=target_user_id,
                    trip_id=trip_id,
                    booking_id=booking_id,
                    complaint_type=complaint_type,
                    title=title,
                    description=description,
                    evidence_url=evidence_url,
                )
            except ValueError as exc:
                return fail(ComplaintInvalidDataError, str(exc))
            return Result.ok(complaint)

    async def resolve_complaint(
        self,
        complaint_id: uuid.UUID,
        *,
        resolution_action: ComplaintResolutionAction = ComplaintResolutionAction.NONE,
        resolution_note: str | None = None,
        resolved_by_admin_id: uuid.UUID | None = None,
    ) -> Result[ComplaintRecord]:
        """`OPEN`/`UNDER_REVIEW` -> `RESOLVED`. Idempotent if already
        `RESOLVED`; refused if already `DISMISSED` ("only unresolved
        complaints may be resolved").
        """
        async with self._uow_factory() as uow:
            result = await self._fetch_complaint(complaint_id, uow)
            if isinstance(result, Failure):
                return result
            complaint = result

            if complaint.complaint_status == ComplaintStatus.RESOLVED:
                return Result.ok(complaint)
            if complaint.complaint_status == ComplaintStatus.DISMISSED:
                return fail(ComplaintDismissedError)

            updated = await uow.complaints.update(
                complaint,
                complaint_status=ComplaintStatus.RESOLVED,
                resolution_action=resolution_action,
                resolution_note=resolution_note,
                resolved_by_admin_id=resolved_by_admin_id,
                resolved_at=datetime.now(UTC),
            )
            return Result.ok(updated)

    async def reject_complaint(
        self,
        complaint_id: uuid.UUID,
        *,
        resolution_note: str | None = None,
        resolved_by_admin_id: uuid.UUID | None = None,
    ) -> Result[ComplaintRecord]:
        """`OPEN`/`UNDER_REVIEW` -> `DISMISSED` (found not to warrant
        action; `resolution_action` is always `NONE`). Idempotent if
        already `DISMISSED`; refused if already `RESOLVED` ("only
        unresolved complaints may be resolved" applies symmetrically to
        rejection).
        """
        async with self._uow_factory() as uow:
            result = await self._fetch_complaint(complaint_id, uow)
            if isinstance(result, Failure):
                return result
            complaint = result

            if complaint.complaint_status == ComplaintStatus.DISMISSED:
                return Result.ok(complaint)
            if complaint.complaint_status == ComplaintStatus.RESOLVED:
                return fail(ComplaintAlreadyResolvedError)

            updated = await uow.complaints.update(
                complaint,
                complaint_status=ComplaintStatus.DISMISSED,
                resolution_action=ComplaintResolutionAction.NONE,
                resolution_note=resolution_note,
                resolved_by_admin_id=resolved_by_admin_id,
                resolved_at=datetime.now(UTC),
            )
            return Result.ok(updated)

    async def close_complaint(self, complaint_id: uuid.UUID) -> Result[ComplaintRecord]:
        """`OPEN` -> `UNDER_REVIEW` (see module docstring). Idempotent if
        already `UNDER_REVIEW`; refused if already finalized
        (`RESOLVED`/`DISMISSED` -- "complaint status transitions must be
        validated").
        """
        async with self._uow_factory() as uow:
            result = await self._fetch_complaint(complaint_id, uow)
            if isinstance(result, Failure):
                return result
            complaint = result

            if complaint.complaint_status == ComplaintStatus.UNDER_REVIEW:
                return Result.ok(complaint)
            if complaint.complaint_status == ComplaintStatus.RESOLVED:
                return fail(ComplaintAlreadyResolvedError)
            if complaint.complaint_status == ComplaintStatus.DISMISSED:
                return fail(ComplaintDismissedError)

            updated = await uow.complaints.update(
                complaint, complaint_status=ComplaintStatus.UNDER_REVIEW
            )
            return Result.ok(updated)

    async def get_complaint(self, complaint_id: uuid.UUID) -> Result[ComplaintRecord]:
        async with self._uow_factory() as uow:
            result = await self._fetch_complaint(complaint_id, uow)
            return result if isinstance(result, Failure) else Result.ok(result)

    # --- Queries -----------------------------------------------------------

    async def list_user_complaints(
        self, reporter_user_id: uuid.UUID
    ) -> Result[Sequence[ComplaintRecord]]:
        """Complaints this user *filed* -- not complaints made *against*
        them (see `infrastructure/database/repositories/complaint.py`'s
        docstring for the pre-existing, still-available
        `list_by_target_user_id` this deliberately does not call).
        """
        async with self._uow_factory() as uow:
            complaints = await uow.complaints.list_by_reporter_user_id(reporter_user_id)
            return Result.ok(complaints)

    async def list_trip_complaints(self, trip_id: uuid.UUID) -> Result[Sequence[ComplaintRecord]]:
        async with self._uow_factory() as uow:
            complaints = await uow.complaints.list_by_trip_id(trip_id)
            return Result.ok(complaints)

    async def list_booking_complaints(
        self, booking_id: uuid.UUID
    ) -> Result[Sequence[ComplaintRecord]]:
        async with self._uow_factory() as uow:
            complaints = await uow.complaints.list_by_booking_id(booking_id)
            return Result.ok(complaints)


__all__ = ["ComplaintService"]
