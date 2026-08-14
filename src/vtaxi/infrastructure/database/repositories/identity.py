"""Repositories for the Identity domain (`User`, `DriverProfile`,
`PassengerProfile`). Persistence-only: no phone-number normalization, no
approval workflow, no role checks -- see the Base/Generic repository
docstrings for why.
"""

import uuid
from collections.abc import Sequence

from vtaxi.infrastructure.database.enums import DriverAvailabilityStatus
from vtaxi.infrastructure.database.models.identity import DriverProfile, PassengerProfile, User
from vtaxi.infrastructure.database.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    model = User

    async def get_by_telegram_id(self, telegram_id: int) -> User | None:
        return await self.get_one(User.telegram_id == telegram_id)

    async def get_by_phone_number(self, phone_number: str) -> User | None:
        return await self.get_one(User.phone_number == phone_number)


class DriverRepository(BaseRepository[DriverProfile]):
    model = DriverProfile

    async def get_by_user_id(self, user_id: uuid.UUID) -> DriverProfile | None:
        return await self.get_one(DriverProfile.user_id == user_id)

    async def list_by_availability_status(
        self, status: DriverAvailabilityStatus
    ) -> Sequence[DriverProfile]:
        return await self.get_many(DriverProfile.availability_status == status)


class PassengerRepository(BaseRepository[PassengerProfile]):
    model = PassengerProfile

    async def get_by_user_id(self, user_id: uuid.UUID) -> PassengerProfile | None:
        return await self.get_one(PassengerProfile.user_id == user_id)


__all__ = ["DriverRepository", "PassengerRepository", "UserRepository"]
