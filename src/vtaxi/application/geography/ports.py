"""Geography-context ports: what `GeographyService` needs from a
repository/Unit of Work, expressed as `Protocol`s -- not imports of the
concrete SQLAlchemy classes in `infrastructure/database/repositories/`.
Same reasoning as `application/identity/ports.py`; see that module's
docstring for why this project draws the "framework independent" line
where it does (referencing ORM classes for typing is fine, calling
SQLAlchemy APIs is not).

`GeographyRepositoryProtocol` includes `create_direction` (added to the
concrete `GeographyRepository` in Step 8.2 -- see that file's docstring):
the repository is bound to `AdministrativeArea`, so its inherited
`create()` cannot persist a `Direction`, and this service has no other
way to create one without SQLAlchemy code of its own.
"""

from collections.abc import Sequence
from typing import Any, Protocol
from uuid import UUID

from vtaxi.infrastructure.database.models.geography import AdministrativeArea, Direction


class GeographyRepositoryProtocol(Protocol):
    async def get_by_id(self, id_: Any) -> AdministrativeArea | None: ...
    async def create(self, **values: Any) -> AdministrativeArea: ...
    async def list_children(self, parent_id: UUID) -> Sequence[AdministrativeArea]: ...
    async def search_by_name(
        self, query: str, *, limit: int = 20
    ) -> Sequence[AdministrativeArea]: ...
    async def get_direction(self, direction_id: UUID) -> Direction | None: ...
    async def find_direction(
        self, origin_area_id: UUID, destination_area_id: UUID
    ) -> Direction | None: ...
    async def list_active_directions(self) -> Sequence[Direction]: ...
    async def create_direction(self, **values: Any) -> Direction: ...


class GeographyUnitOfWork(Protocol):
    """What `GeographyService` needs from a Unit of Work: the one
    repository above, plus the commit-on-success/rollback-on-exception
    async context manager every service method opens one of via a
    `core.application.UnitOfWorkFactory`.
    """

    geography: GeographyRepositoryProtocol

    async def __aenter__(self) -> "GeographyUnitOfWork": ...

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None: ...


__all__ = ["GeographyRepositoryProtocol", "GeographyUnitOfWork"]
