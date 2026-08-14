"""Identity-context ports: what `UserService`/`DriverService`/
`PassengerService` need from a repository/Unit of Work, expressed as
`Protocol`s -- not imports of the concrete SQLAlchemy classes in
`infrastructure/database/repositories/`.

Each Protocol below declares only the methods its matching service
actually calls (Interface Segregation, not the full ten-method generic
repository shape) -- `UserRepositoryProtocol` skips `get_one`/`get_many`/
`count`/`list_paginated`, for instance, since nothing in this context uses
them yet. The concrete `infrastructure/database/repositories/identity.py`
classes (Step 7) already satisfy every Protocol here structurally, with no
import in either direction and no change needed to them.

`IdentityUnitOfWork` is this context's own narrow Unit-of-Work shape
(`users`/`drivers`/`passengers` + the async context-manager protocol) --
not a single shared "UnitOfWorkProtocol" covering all twelve
repositories, which would force this module to import every other
context's ports just to describe three attributes. The concrete
`infrastructure/database/repositories/unit_of_work.UnitOfWork` (Step 7)
satisfies this and every other context's narrower protocol at once, since
it already has every attribute any of them ask for.

References `User`/`DriverProfile`/`PassengerProfile` for typing only --
consistent with this project's choice (since Step 5.1) to let the
SQLAlchemy model *be* the domain model rather than maintain a parallel
DTO layer. "Framework independent" here means no SQLAlchemy *behavior*
(no `select()`, no `Session`, no query construction) -- referencing the
data types themselves is not that.
"""

from typing import Any, Protocol
from uuid import UUID

from vtaxi.infrastructure.database.enums import DriverAvailabilityStatus
from vtaxi.infrastructure.database.models.identity import DriverProfile, PassengerProfile, User


class UserRepositoryProtocol(Protocol):
    async def get_by_id(self, id_: Any) -> User | None: ...
    async def get_by_telegram_id(self, telegram_id: int) -> User | None: ...
    async def get_by_phone_number(self, phone_number: str) -> User | None: ...
    async def create(self, **values: Any) -> User: ...
    async def update(self, instance: User, **values: Any) -> User: ...
    async def delete(self, instance: User) -> None: ...
    async def restore(self, instance: User) -> User: ...


class DriverRepositoryProtocol(Protocol):
    async def get_by_id(self, id_: Any) -> DriverProfile | None: ...
    async def get_by_user_id(self, user_id: UUID) -> DriverProfile | None: ...
    async def list_by_availability_status(self, status: DriverAvailabilityStatus) -> Any: ...
    async def create(self, **values: Any) -> DriverProfile: ...
    async def update(self, instance: DriverProfile, **values: Any) -> DriverProfile: ...


class PassengerRepositoryProtocol(Protocol):
    async def get_by_id(self, id_: Any) -> PassengerProfile | None: ...
    async def get_by_user_id(self, user_id: UUID) -> PassengerProfile | None: ...
    async def create(self, **values: Any) -> PassengerProfile: ...
    async def update(self, instance: PassengerProfile, **values: Any) -> PassengerProfile: ...


class IdentityUnitOfWork(Protocol):
    """What Identity services need from a Unit of Work: the three
    repositories above, plus the commit-on-success/rollback-on-exception
    async context manager every service method opens one of via a
    `core.application.UnitOfWorkFactory`.
    """

    users: UserRepositoryProtocol
    drivers: DriverRepositoryProtocol
    passengers: PassengerRepositoryProtocol

    async def __aenter__(self) -> "IdentityUnitOfWork": ...

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None: ...


__all__ = [
    "DriverRepositoryProtocol",
    "IdentityUnitOfWork",
    "PassengerRepositoryProtocol",
    "UserRepositoryProtocol",
]
