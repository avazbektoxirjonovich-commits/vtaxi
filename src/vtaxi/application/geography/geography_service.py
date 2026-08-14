"""`GeographyService` -- Administrative Area and Direction use cases.

Every method opens its own Unit of Work via the injected factory and is
therefore independently atomic, same discipline as `application/identity/`'s
services. Nothing here imports SQLAlchemy, Aiogram, or FastAPI -- only
`ports.py` (structural Protocols) and the ORM classes themselves for
typing (see ports.py's docstring for why that's not a "framework
independent" violation in this project).

No GPS/distance calculation, nearby search, or real-time location here --
that is the Geo Engine's job (docs/01-SOFTWARE-ARCHITECTURE.md SS14.8),
a distinct, not-yet-built service. This module only manages the
administrative-area tree and the Direction whitelist as data.
"""

import uuid
from collections.abc import Sequence
from decimal import Decimal
from typing import Any

from vtaxi.core.application import UnitOfWorkFactory, fail
from vtaxi.core.domain import Result
from vtaxi.core.domain.result import Failure
from vtaxi.domain.geography.exceptions import (
    DirectionAlreadyExistsError,
    DirectionNotFoundError,
    DirectionNotSupportedError,
    GeographyNotFoundError,
    InvalidHierarchyError,
)
from vtaxi.infrastructure.database.enums import AdministrativeAreaLevel
from vtaxi.infrastructure.database.models.geography import AdministrativeArea, Direction

from .ports import GeographyUnitOfWork

# COUNTRY -> STREET, shallow to deep. A child's level must sit strictly
# below (a higher index than) its parent's in this ordering -- see
# `_hierarchy_violation`. TOWN is retained from the already-approved
# enum (Step 5.2) even though this round's brief's hierarchy diagram
# omits it; dropping it would mean editing an ORM model, out of scope.
_LEVEL_ORDER: tuple[AdministrativeAreaLevel, ...] = (
    AdministrativeAreaLevel.COUNTRY,
    AdministrativeAreaLevel.REGION,
    AdministrativeAreaLevel.DISTRICT,
    AdministrativeAreaLevel.CITY,
    AdministrativeAreaLevel.TOWN,
    AdministrativeAreaLevel.VILLAGE,
    AdministrativeAreaLevel.MAHALLA,
    AdministrativeAreaLevel.STREET,
)


class GeographyService:
    def __init__(self, uow_factory: UnitOfWorkFactory[GeographyUnitOfWork]) -> None:
        self._uow_factory = uow_factory

    # --- Administrative Areas --------------------------------------------

    async def _hierarchy_violation(
        self,
        level: AdministrativeAreaLevel,
        parent_id: uuid.UUID | None,
        uow: GeographyUnitOfWork,
    ) -> Failure | None:
        """`None` if the (level, parent) combination is valid, a `Failure`
        otherwise -- shared by the public `validate_hierarchy()` and
        `create_administrative_area()`'s internal check, so the two can
        never silently disagree about what counts as valid.
        """
        if level == AdministrativeAreaLevel.COUNTRY:
            if parent_id is not None:
                return fail(InvalidHierarchyError, "A COUNTRY-level area cannot have a parent.")
            return None

        if parent_id is None:
            return fail(InvalidHierarchyError, f"A {level.value}-level area must have a parent.")

        parent = await uow.geography.get_by_id(parent_id)
        if parent is None:
            return fail(GeographyNotFoundError, "The given parent area does not exist.")
        if _LEVEL_ORDER.index(level) <= _LEVEL_ORDER.index(parent.level):
            return fail(
                InvalidHierarchyError,
                f"A {level.value}-level area cannot be a child of a "
                f"{parent.level.value}-level area.",
            )
        return None

    async def validate_hierarchy(
        self, level: AdministrativeAreaLevel, parent_id: uuid.UUID | None
    ) -> Result[None]:
        async with self._uow_factory() as uow:
            violation = await self._hierarchy_violation(level, parent_id, uow)
            return violation if violation is not None else Result.ok(None)

    async def create_administrative_area(
        self,
        *,
        name: str,
        level: AdministrativeAreaLevel,
        parent_id: uuid.UUID | None = None,
        latitude: Decimal | None = None,
        longitude: Decimal | None = None,
        postal_code: str | None = None,
        sort_order: int = 0,
    ) -> Result[AdministrativeArea]:
        async with self._uow_factory() as uow:
            violation = await self._hierarchy_violation(level, parent_id, uow)
            if violation is not None:
                return violation
            area = await uow.geography.create(
                name=name,
                level=level,
                parent_id=parent_id,
                latitude=latitude,
                longitude=longitude,
                postal_code=postal_code,
                sort_order=sort_order,
            )
            return Result.ok(area)

    async def get_administrative_area(self, area_id: uuid.UUID) -> Result[AdministrativeArea]:
        async with self._uow_factory() as uow:
            area = await uow.geography.get_by_id(area_id)
            if area is None:
                return fail(GeographyNotFoundError)
            return Result.ok(area)

    async def get_children(self, parent_id: uuid.UUID) -> Result[Sequence[AdministrativeArea]]:
        async with self._uow_factory() as uow:
            if await uow.geography.get_by_id(parent_id) is None:
                return fail(GeographyNotFoundError)
            children = await uow.geography.list_children(parent_id)
            return Result.ok(children)

    async def get_parent(self, area_id: uuid.UUID) -> Result[AdministrativeArea | None]:
        """`Result.ok(None)` -- not a failure -- when `area_id` is
        COUNTRY-level and genuinely has no parent; that is the expected,
        correct answer, not an error condition.
        """
        async with self._uow_factory() as uow:
            area = await uow.geography.get_by_id(area_id)
            if area is None:
                return fail(GeographyNotFoundError)
            if area.parent_id is None:
                return Result.ok(None)
            parent = await uow.geography.get_by_id(area.parent_id)
            return Result.ok(parent)

    async def get_full_path(self, area_id: uuid.UUID) -> Result[Sequence[AdministrativeArea]]:
        """Root-to-leaf order, e.g. `[Uzbekistan, Namangan region, ...,
        area_id's own row]`. `parent`/`children` were deliberately not
        made eager-loading relationships (Step 5.2 -- unbounded self-
        referential recursion risk), so this walks `parent_id` one
        `get_by_id` at a time instead of traversing an in-memory object
        graph.
        """
        async with self._uow_factory() as uow:
            area = await uow.geography.get_by_id(area_id)
            if area is None:
                return fail(GeographyNotFoundError)

            path: list[AdministrativeArea] = [area]
            current = area
            while current.parent_id is not None:
                parent = await uow.geography.get_by_id(current.parent_id)
                if parent is None:
                    break  # orphaned reference; stop rather than loop forever
                path.append(parent)
                current = parent

            path.reverse()
            return Result.ok(path)

    async def area_exists(self, area_id: uuid.UUID) -> Result[bool]:
        async with self._uow_factory() as uow:
            return Result.ok(await uow.geography.get_by_id(area_id) is not None)

    async def search_area_by_name(
        self, query: str, *, limit: int = 20
    ) -> Result[Sequence[AdministrativeArea]]:
        async with self._uow_factory() as uow:
            results = await uow.geography.search_by_name(query, limit=limit)
            return Result.ok(results)

    # --- Directions --------------------------------------------------------

    async def create_direction(
        self,
        *,
        origin_area_id: uuid.UUID,
        destination_area_id: uuid.UUID,
        is_active: bool = True,
        display_order: int = 0,
        **fields: Any,
    ) -> Result[Direction]:
        if origin_area_id == destination_area_id:
            return fail(
                DirectionNotSupportedError, "Origin and destination cannot be the same area."
            )
        async with self._uow_factory() as uow:
            if await uow.geography.get_by_id(origin_area_id) is None:
                return fail(GeographyNotFoundError, "The origin area does not exist.")
            if await uow.geography.get_by_id(destination_area_id) is None:
                return fail(GeographyNotFoundError, "The destination area does not exist.")
            if await uow.geography.find_direction(origin_area_id, destination_area_id) is not None:
                return fail(DirectionAlreadyExistsError)

            direction = await uow.geography.create_direction(
                origin_area_id=origin_area_id,
                destination_area_id=destination_area_id,
                is_active=is_active,
                display_order=display_order,
                **fields,
            )
            return Result.ok(direction)

    async def get_direction(self, direction_id: uuid.UUID) -> Result[Direction]:
        async with self._uow_factory() as uow:
            direction = await uow.geography.get_direction(direction_id)
            if direction is None:
                return fail(DirectionNotFoundError)
            return Result.ok(direction)

    async def get_all_directions(self) -> Result[Sequence[Direction]]:
        """Active directions only: `GeographyRepository` (Step 7) exposes
        `list_active_directions()`, not an unfiltered query -- adding one
        would mean a second Repository Layer change beyond this step's one
        necessary addition (`create_direction`; see ports.py/geography.py).
        """
        async with self._uow_factory() as uow:
            directions = await uow.geography.list_active_directions()
            return Result.ok(directions)

    async def direction_exists(
        self, origin_area_id: uuid.UUID, destination_area_id: uuid.UUID
    ) -> Result[bool]:
        async with self._uow_factory() as uow:
            direction = await uow.geography.find_direction(origin_area_id, destination_area_id)
            return Result.ok(direction is not None)

    async def is_valid_direction(self, direction_id: uuid.UUID) -> Result[bool]:
        """A direction can exist but be deactivated -- "valid" means both
        found and currently active, distinct from `get_direction()`
        (found, regardless of status) and `direction_exists()` (found by
        area pair, regardless of status).
        """
        async with self._uow_factory() as uow:
            direction = await uow.geography.get_direction(direction_id)
            return Result.ok(direction is not None and direction.is_active)


__all__ = ["GeographyService"]
