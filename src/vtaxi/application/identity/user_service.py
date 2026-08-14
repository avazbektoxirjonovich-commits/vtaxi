"""`UserService` -- Identity use cases for the `User` entity itself (see
`driver_service.py`/`passenger_service.py` for the role-specific
extensions).

Every method opens its own Unit of Work via the injected factory and is
therefore independently atomic; no method assumes a caller-managed
transaction spanning multiple calls. Nothing here imports SQLAlchemy,
Aiogram, or FastAPI -- only `ports.py` (structural Protocols) and the
`User` ORM class itself (a type reference, not a behavioral dependency;
see ports.py's docstring for why that's the line this project draws).
"""

import uuid
from typing import Any

from vtaxi.core.application import UnitOfWorkFactory, fail
from vtaxi.core.domain import Result
from vtaxi.domain.identity.user_exceptions import UserAlreadyExistsError, UserNotFoundError
from vtaxi.infrastructure.database.enums import UserRole
from vtaxi.infrastructure.database.models.identity import User

from .ports import IdentityUnitOfWork


class UserService:
    def __init__(self, uow_factory: UnitOfWorkFactory[IdentityUnitOfWork]) -> None:
        self._uow_factory = uow_factory

    async def create_user(
        self,
        *,
        telegram_id: int,
        phone_number: str,
        first_name: str,
        role: UserRole,
        last_name: str | None = None,
        language_code: str = "uz",
    ) -> Result[User]:
        async with self._uow_factory() as uow:
            if await uow.users.get_by_telegram_id(telegram_id) is not None:
                return fail(
                    UserAlreadyExistsError, "A user with this Telegram account already exists."
                )
            if await uow.users.get_by_phone_number(phone_number) is not None:
                return fail(UserAlreadyExistsError, "A user with this phone number already exists.")

            user = await uow.users.create(
                telegram_id=telegram_id,
                phone_number=phone_number,
                first_name=first_name,
                last_name=last_name,
                language_code=language_code,
                role=role,
            )
            return Result.ok(user)

    async def get_user(self, user_id: uuid.UUID) -> Result[User]:
        async with self._uow_factory() as uow:
            user = await uow.users.get_by_id(user_id)
            if user is None:
                return fail(UserNotFoundError)
            return Result.ok(user)

    async def get_user_by_phone(self, phone_number: str) -> Result[User]:
        async with self._uow_factory() as uow:
            user = await uow.users.get_by_phone_number(phone_number)
            if user is None:
                return fail(UserNotFoundError)
            return Result.ok(user)

    async def get_user_by_telegram_id(self, telegram_id: int) -> Result[User]:
        async with self._uow_factory() as uow:
            user = await uow.users.get_by_telegram_id(telegram_id)
            if user is None:
                return fail(UserNotFoundError)
            return Result.ok(user)

    async def update_user(self, user_id: uuid.UUID, **fields: Any) -> Result[User]:
        async with self._uow_factory() as uow:
            user = await uow.users.get_by_id(user_id)
            if user is None:
                return fail(UserNotFoundError)
            updated = await uow.users.update(user, **fields)
            return Result.ok(updated)

    async def soft_delete_user(self, user_id: uuid.UUID) -> Result[None]:
        """Idempotent: soft-deleting an already-deleted user is a no-op
        success, not an error -- matching REST DELETE semantics rather
        than treating "already gone" as a failure.
        """
        async with self._uow_factory() as uow:
            user = await uow.users.get_by_id(user_id)
            if user is None:
                return fail(UserNotFoundError)
            if user.deleted_at is None:
                await uow.users.delete(user)
            return Result.ok(None)

    async def restore_user(self, user_id: uuid.UUID) -> Result[User]:
        """Idempotent, same reasoning as `soft_delete_user`.

        Note for whoever wires Step 9's composition root: if
        `register_soft_delete_filter()` (infrastructure/database/mixins/
        soft_delete_mixin.py) is ever registered, `get_by_id` here would
        stop finding an already-soft-deleted user (the global filter
        excludes them), and this method would need `get_by_id` to accept
        an `include_deleted` bypass that `GenericRepository` doesn't
        currently expose. Not fixed here: doing so means editing the
        Repository Layer, out of scope for this step.
        """
        async with self._uow_factory() as uow:
            user = await uow.users.get_by_id(user_id)
            if user is None:
                return fail(UserNotFoundError)
            if user.deleted_at is not None:
                await uow.users.restore(user)
            return Result.ok(user)

    async def user_exists(
        self,
        *,
        user_id: uuid.UUID | None = None,
        telegram_id: int | None = None,
        phone_number: str | None = None,
    ) -> Result[bool]:
        """Checks whichever identifier is given -- `create_user` doesn't
        call this (it needs both users, if any, for the "which already
        exists" message), but any future caller only holding one
        identifier can.
        """
        if user_id is None and telegram_id is None and phone_number is None:
            raise ValueError(
                "user_exists() requires at least one of user_id/telegram_id/phone_number"
            )
        async with self._uow_factory() as uow:
            if user_id is not None:
                return Result.ok(await uow.users.get_by_id(user_id) is not None)
            if telegram_id is not None:
                return Result.ok(await uow.users.get_by_telegram_id(telegram_id) is not None)
            assert phone_number is not None
            return Result.ok(await uow.users.get_by_phone_number(phone_number) is not None)


__all__ = ["UserService"]
