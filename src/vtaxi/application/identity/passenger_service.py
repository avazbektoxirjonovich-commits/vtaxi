"""`PassengerService` -- Identity use cases for the `PassengerProfile`
extension.

`block_passenger()`/`activate_passenger()` map to `passenger_status`
BANNED/ACTIVE (docs/01-SOFTWARE-ARCHITECTURE.md SS14.4) -- "blocked" is
this step's naming (matching `PassengerBlockedError`, Step 7.5), the
column value itself is `BANNED`, same real-world concept.
"""

import uuid
from typing import Any

from vtaxi.core.application import UnitOfWorkFactory, fail
from vtaxi.core.domain import Result
from vtaxi.domain.identity.passenger_exceptions import (
    PassengerAlreadyExistsError,
    PassengerBlockedError,
    PassengerNotFoundError,
)
from vtaxi.domain.identity.user_exceptions import UserNotFoundError
from vtaxi.infrastructure.database.enums import PassengerStatus
from vtaxi.infrastructure.database.models.identity import PassengerProfile

from .ports import IdentityUnitOfWork


class PassengerService:
    def __init__(self, uow_factory: UnitOfWorkFactory[IdentityUnitOfWork]) -> None:
        self._uow_factory = uow_factory

    async def create_passenger_profile(
        self, user_id: uuid.UUID, **fields: Any
    ) -> Result[PassengerProfile]:
        async with self._uow_factory() as uow:
            if await uow.users.get_by_id(user_id) is None:
                return fail(UserNotFoundError)
            if await uow.passengers.get_by_user_id(user_id) is not None:
                return fail(PassengerAlreadyExistsError)
            profile = await uow.passengers.create(user_id=user_id, **fields)
            return Result.ok(profile)

    async def block_passenger(self, passenger_profile_id: uuid.UUID) -> Result[PassengerProfile]:
        async with self._uow_factory() as uow:
            profile = await uow.passengers.get_by_id(passenger_profile_id)
            if profile is None:
                return fail(PassengerNotFoundError)
            if profile.passenger_status == PassengerStatus.BANNED:
                return fail(PassengerBlockedError)
            updated = await uow.passengers.update(profile, passenger_status=PassengerStatus.BANNED)
            return Result.ok(updated)

    async def activate_passenger(self, passenger_profile_id: uuid.UUID) -> Result[PassengerProfile]:
        """Unconditional reset to ACTIVE -- idempotent whether or not the
        passenger was actually blocked, same reasoning as
        `UserService.soft_delete_user`'s idempotency.
        """
        async with self._uow_factory() as uow:
            profile = await uow.passengers.get_by_id(passenger_profile_id)
            if profile is None:
                return fail(PassengerNotFoundError)
            updated = await uow.passengers.update(profile, passenger_status=PassengerStatus.ACTIVE)
            return Result.ok(updated)

    async def get_passenger_profile(
        self, passenger_profile_id: uuid.UUID
    ) -> Result[PassengerProfile]:
        async with self._uow_factory() as uow:
            profile = await uow.passengers.get_by_id(passenger_profile_id)
            if profile is None:
                return fail(PassengerNotFoundError)
            return Result.ok(profile)

    async def passenger_exists(self, user_id: uuid.UUID) -> Result[bool]:
        async with self._uow_factory() as uow:
            return Result.ok(await uow.passengers.get_by_user_id(user_id) is not None)


__all__ = ["PassengerService"]
