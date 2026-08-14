"""The framework-level CRUD engine every repository is built on.

Nothing here knows about Users, Bookings, or any other VTaxi concept --
`GenericRepository[ModelT]` works against any SQLAlchemy 2.0 declarative
model, reusable outside this project unchanged. Project-specific
conventions (soft-delete-aware delete/restore bound at the class level to
one model) live in `base.py`, one layer up.

Persistence-only, deliberately: no business rules, no validation beyond
"is this a valid page number," no state-machine transitions, nothing that
decides *when* to call these methods -- that is the future Service
Layer's job (Step 8).

Update() goes through plain ORM attribute-setting + `flush()`, not a Core
`update()` statement -- this is what lets a model add
`__mapper_args__ = {"version_id_col": ...}` later (optimistic locking,
already marked as a future addition on `Booking`, see models/booking.py)
and have it enforced automatically on flush, with zero repository changes.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Generic, Protocol, TypeVar

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.interfaces import ORMOption


class _HasId(Protocol):
    id: Any


ModelT = TypeVar("ModelT", bound=_HasId)


@dataclass(frozen=True, slots=True)
class Page(Generic[ModelT]):
    """One page of a `list_paginated()` result."""

    items: Sequence[ModelT]
    total: int
    page: int
    page_size: int

    @property
    def total_pages(self) -> int:
        if self.page_size <= 0:
            return 0
        return -(-self.total // self.page_size)

    @property
    def has_next(self) -> bool:
        return self.page * self.page_size < self.total

    @property
    def has_previous(self) -> bool:
        return self.page > 1


class GenericRepository(Generic[ModelT]):
    """CRUD + query mechanics bound to one `AsyncSession` and one model
    class, both supplied by the caller (compare `BaseRepository`, which
    binds the model at the class level for concrete repositories).
    """

    def __init__(self, session: AsyncSession, model: type[ModelT]) -> None:
        self.session = session
        self.model = model

    async def get_by_id(self, id_: Any, *, options: Sequence[ORMOption] = ()) -> ModelT | None:
        stmt = select(self.model).where(self.model.id == id_)
        for option in options:
            stmt = stmt.options(option)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_one(
        self, *where: ColumnElement[bool], options: Sequence[ORMOption] = ()
    ) -> ModelT | None:
        stmt = select(self.model).where(*where)
        for option in options:
            stmt = stmt.options(option)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_many(
        self,
        *where: ColumnElement[bool],
        # `Sequence[Any]`, not `Sequence[ColumnElement[Any]]`: a sort key is
        # commonly `Model.column` (an `InstrumentedAttribute`) or
        # `Model.column.desc()` (a `UnaryExpression`) -- neither is typed as
        # a plain `ColumnElement` in a way mypy accepts through a `Sequence`
        # parameter, so this is typed for what callers actually pass.
        order_by: Sequence[Any] = (),
        options: Sequence[ORMOption] = (),
        limit: int | None = None,
        offset: int | None = None,
    ) -> Sequence[ModelT]:
        stmt = select(self.model).where(*where)
        if order_by:
            stmt = stmt.order_by(*order_by)
        if limit is not None:
            stmt = stmt.limit(limit)
        if offset is not None:
            stmt = stmt.offset(offset)
        for option in options:
            stmt = stmt.options(option)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def exists(self, *where: ColumnElement[bool]) -> bool:
        stmt = select(self.model.id).where(*where).limit(1)
        result = await self.session.execute(stmt)
        return result.first() is not None

    async def count(self, *where: ColumnElement[bool]) -> int:
        stmt = select(func.count()).select_from(self.model).where(*where)
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def create(self, **values: Any) -> ModelT:
        instance = self.model(**values)
        self.session.add(instance)
        await self.session.flush()
        return instance

    async def update(self, instance: ModelT, **values: Any) -> ModelT:
        for key, value in values.items():
            setattr(instance, key, value)
        await self.session.flush()
        return instance

    async def delete(self, instance: ModelT) -> None:
        """Soft-delete (sets `deleted_at`) when the model has that column
        (`SoftDeleteMixin` -- see docs/03-DATABASE-DESIGN.md SS0.3 for
        which models do), otherwise a real hard delete. The check is a
        generic `hasattr`, not a per-model branch: this class still knows
        nothing about any specific VTaxi model.
        """
        if hasattr(instance, "deleted_at"):
            instance.deleted_at = datetime.now(UTC)
            await self.session.flush()
            return
        await self.session.delete(instance)
        await self.session.flush()

    async def restore(self, instance: ModelT) -> ModelT:
        """The inverse of a soft `delete()`. Raises for a model with no
        `deleted_at` column -- there is nothing to restore from a hard
        delete, which by definition already removed the row.
        """
        if not hasattr(instance, "deleted_at"):
            raise NotImplementedError(f"{type(instance).__name__} does not support soft delete")
        instance.deleted_at = None
        await self.session.flush()
        return instance

    async def list_paginated(
        self,
        *where: ColumnElement[bool],
        page: int = 1,
        page_size: int = 20,
        order_by: Sequence[Any] = (),
        options: Sequence[ORMOption] = (),
    ) -> Page[ModelT]:
        if page < 1:
            raise ValueError("page must be >= 1")
        if page_size < 1:
            raise ValueError("page_size must be >= 1")

        total = await self.count(*where)
        items = await self.get_many(
            *where,
            order_by=order_by,
            options=options,
            limit=page_size,
            offset=(page - 1) * page_size,
        )
        return Page(items=items, total=total, page=page, page_size=page_size)
