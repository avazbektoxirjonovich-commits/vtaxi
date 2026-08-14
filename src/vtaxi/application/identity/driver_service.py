"""`DriverService` -- Identity use cases for the `DriverProfile` extension.

`approval_status` (the one-time verification gate) and `availability_status`
(operational visibility) are independent axes -- see docs/01-SOFTWARE-
ARCHITECTURE.md SS14.3 and models/identity.py. `verify_driver`/
`reject_driver` only ever touch the former; `ban_driver`/`activate_driver`/
`deactivate_driver` only ever touch the latter, except `activate_driver`
also *reads* `approval_status` (a driver can't go online unverified).
"""

import uuid
from typing import Any

from vtaxi.core.application import UnitOfWorkFactory, fail
from vtaxi.core.domain import Result
from vtaxi.domain.identity.driver_exceptions import (
    DriverAlreadyExistsError,
    DriverAlreadyVerifiedError,
    DriverBannedError,
    DriverNotFoundError,
    DriverNotVerifiedError,
)
from vtaxi.domain.identity.user_exceptions import UserNotFoundError
from vtaxi.infrastructure.database.enums import DriverApprovalStatus, DriverAvailabilityStatus
from vtaxi.infrastructure.database.models.identity import DriverProfile

from .ports import IdentityUnitOfWork


class DriverService:
    def __init__(self, uow_factory: UnitOfWorkFactory[IdentityUnitOfWork]) -> None:
        self._uow_factory = uow_factory

    async def create_driver_profile(
        self, user_id: uuid.UUID, **fields: Any
    ) -> Result[DriverProfile]:
        async with self._uow_factory() as uow:
            if await uow.users.get_by_id(user_id) is None:
                return fail(UserNotFoundError)
            if await uow.drivers.get_by_user_id(user_id) is not None:
                return fail(DriverAlreadyExistsError)
            profile = await uow.drivers.create(user_id=user_id, **fields)
            return Result.ok(profile)

    async def verify_driver(self, driver_profile_id: uuid.UUID) -> Result[DriverProfile]:
        async with self._uow_factory() as uow:
            profile = await uow.drivers.get_by_id(driver_profile_id)
            if profile is None:
                return fail(DriverNotFoundError)
            if profile.approval_status == DriverApprovalStatus.APPROVED:
                return fail(DriverAlreadyVerifiedError)
            updated = await uow.drivers.update(
                profile, approval_status=DriverApprovalStatus.APPROVED
            )
            return Result.ok(updated)

    async def reject_driver(self, driver_profile_id: uuid.UUID) -> Result[DriverProfile]:
        """No rejection-reason parameter: `DriverProfile` has no column for
        one (unlike `VehicleDocument`/`DriverDocument`, which do) -- adding
        one would mean editing an ORM model, out of scope for this step.
        """
        async with self._uow_factory() as uow:
            profile = await uow.drivers.get_by_id(driver_profile_id)
            if profile is None:
                return fail(DriverNotFoundError)
            updated = await uow.drivers.update(
                profile, approval_status=DriverApprovalStatus.REJECTED
            )
            return Result.ok(updated)

    async def ban_driver(self, driver_profile_id: uuid.UUID) -> Result[DriverProfile]:
        async with self._uow_factory() as uow:
            profile = await uow.drivers.get_by_id(driver_profile_id)
            if profile is None:
                return fail(DriverNotFoundError)
            if profile.availability_status == DriverAvailabilityStatus.BANNED:
                return fail(DriverBannedError)
            updated = await uow.drivers.update(
                profile, availability_status=DriverAvailabilityStatus.BANNED
            )
            return Result.ok(updated)

    async def activate_driver(self, driver_profile_id: uuid.UUID) -> Result[DriverProfile]:
        """ "Activate" = go ONLINE. Requires prior verification and refuses
        for a banned driver -- an unverified or banned driver cannot make
        themselves visible to Matching by calling this.
        """
        async with self._uow_factory() as uow:
            profile = await uow.drivers.get_by_id(driver_profile_id)
            if profile is None:
                return fail(DriverNotFoundError)
            if profile.availability_status == DriverAvailabilityStatus.BANNED:
                return fail(DriverBannedError)
            if profile.approval_status != DriverApprovalStatus.APPROVED:
                return fail(DriverNotVerifiedError)
            updated = await uow.drivers.update(
                profile, availability_status=DriverAvailabilityStatus.ONLINE
            )
            return Result.ok(updated)

    async def deactivate_driver(self, driver_profile_id: uuid.UUID) -> Result[DriverProfile]:
        """ "Deactivate" = go OFFLINE. Always allowed, including for a
        banned driver -- going offline is never an invalid transition.
        """
        async with self._uow_factory() as uow:
            profile = await uow.drivers.get_by_id(driver_profile_id)
            if profile is None:
                return fail(DriverNotFoundError)
            updated = await uow.drivers.update(
                profile, availability_status=DriverAvailabilityStatus.OFFLINE
            )
            return Result.ok(updated)

    async def get_driver_profile(self, driver_profile_id: uuid.UUID) -> Result[DriverProfile]:
        async with self._uow_factory() as uow:
            profile = await uow.drivers.get_by_id(driver_profile_id)
            if profile is None:
                return fail(DriverNotFoundError)
            return Result.ok(profile)

    async def driver_exists(self, user_id: uuid.UUID) -> Result[bool]:
        async with self._uow_factory() as uow:
            return Result.ok(await uow.drivers.get_by_user_id(user_id) is not None)


__all__ = ["DriverService"]
