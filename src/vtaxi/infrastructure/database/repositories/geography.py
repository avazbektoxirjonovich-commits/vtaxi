"""Repository for the Geography domain. Bound model is `AdministrativeArea`;
`Direction` (the same bounded context, docs/01-SOFTWARE-ARCHITECTURE.md
SS10) is queried directly via `self.session` rather than through a second
bound repository, since only one `GeographyRepository` was asked for.

`search_by_name` is a plain `ILIKE` -- a reasonable, portable persistence-
layer baseline. The trigram-ranked autocomplete algorithm itself (docs/01
SS14.9, Search Engine) is a Service Layer concern, not something this
repository decides.

`create_direction` added in Step 8.2: `GeographyRepository.create()`
(inherited from `BaseRepository`) always constructs an `AdministrativeArea`
-- the model this repository is bound to -- so it cannot be used to
persist a `Direction`. Step 8.2's `GeographyService.create_direction()`
needs a way to do that without touching SQLAlchemy directly (services
must stay framework-independent), so this one small, additive method
fills that gap. Nothing else here changed.
"""

import uuid
from collections.abc import Sequence
from typing import Any

from sqlalchemy import select

from vtaxi.infrastructure.database.enums import AdministrativeAreaLevel
from vtaxi.infrastructure.database.models.geography import AdministrativeArea, Direction
from vtaxi.infrastructure.database.repositories.base import BaseRepository


class GeographyRepository(BaseRepository[AdministrativeArea]):
    model = AdministrativeArea

    async def list_children(self, parent_id: uuid.UUID) -> Sequence[AdministrativeArea]:
        return await self.get_many(
            AdministrativeArea.parent_id == parent_id,
            order_by=(AdministrativeArea.sort_order,),
        )

    async def list_by_level(self, level: AdministrativeAreaLevel) -> Sequence[AdministrativeArea]:
        return await self.get_many(AdministrativeArea.level == level)

    async def search_by_name(self, query: str, *, limit: int = 20) -> Sequence[AdministrativeArea]:
        stmt = (
            select(AdministrativeArea)
            .where(AdministrativeArea.name.ilike(f"%{query}%"))
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_direction(self, direction_id: uuid.UUID) -> Direction | None:
        stmt = select(Direction).where(Direction.id == direction_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def find_direction(
        self, origin_area_id: uuid.UUID, destination_area_id: uuid.UUID
    ) -> Direction | None:
        stmt = select(Direction).where(
            Direction.origin_area_id == origin_area_id,
            Direction.destination_area_id == destination_area_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_active_directions(self) -> Sequence[Direction]:
        stmt = (
            select(Direction).where(Direction.is_active.is_(True)).order_by(Direction.display_order)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def create_direction(self, **values: Any) -> Direction:
        direction = Direction(**values)
        self.session.add(direction)
        await self.session.flush()
        return direction


__all__ = ["GeographyRepository"]
