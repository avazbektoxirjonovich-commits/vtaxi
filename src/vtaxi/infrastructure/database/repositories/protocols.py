"""`RepositoryProtocol[ModelT]` -- the structural interface every concrete
repository satisfies, for the future Service Layer (Step 8) to depend on
instead of a concrete SQLAlchemy class.

One generic protocol, not twelve per-repository ones: every concrete
repository's *extra* domain-specific methods (`get_by_telegram_id`, and
so on) aren't separately protocol'd here -- that would be twelve near-
duplicate interfaces for methods that, today, have exactly one
implementation and no mock/fake standing in for them yet. Add a narrower
protocol for a specific repository if/when a second implementation
(a test fake, most likely) actually needs one -- not preemptively.

Physically placed alongside the repositories that implement it
(`infrastructure/database/repositories/`), not under `application/<context>/`
as strict Clean Architecture would eventually want (docs/01-SOFTWARE-
ARCHITECTURE.md SS2.1): the application layer's port interfaces don't
exist yet (Step 8 is explicitly out of scope this round), and this
protocol has no SQLAlchemy import of its own -- it can be moved verbatim
once something in `application/` is ready to import it.
"""

from collections.abc import Sequence
from typing import Any, Protocol

from sqlalchemy import ColumnElement
from sqlalchemy.orm.interfaces import ORMOption

from vtaxi.infrastructure.database.repositories.generic import ModelT, Page

# Reuses generic.py's `ModelT` (bound to `_HasId`, invariant) rather than a
# separate covariant TypeVar: `update`/`delete`/`restore` below take
# `ModelT` as a *parameter*, which only an invariant TypeVar allows in a
# Protocol -- a covariant one is restricted to return-type ("output")
# positions and mypy rejects it here.


class RepositoryProtocol(Protocol[ModelT]):
    """The structural shape of `GenericRepository`/`BaseRepository`."""

    async def get_by_id(self, id_: Any, *, options: Sequence[ORMOption] = ()) -> ModelT | None: ...

    async def get_one(
        self, *where: ColumnElement[bool], options: Sequence[ORMOption] = ()
    ) -> ModelT | None: ...

    async def get_many(
        self,
        *where: ColumnElement[bool],
        order_by: Sequence[Any] = (),
        options: Sequence[ORMOption] = (),
        limit: int | None = None,
        offset: int | None = None,
    ) -> Sequence[ModelT]: ...

    async def exists(self, *where: ColumnElement[bool]) -> bool: ...

    async def count(self, *where: ColumnElement[bool]) -> int: ...

    async def create(self, **values: Any) -> ModelT: ...

    async def update(self, instance: ModelT, **values: Any) -> ModelT: ...

    async def delete(self, instance: ModelT) -> None: ...

    async def restore(self, instance: ModelT) -> ModelT: ...

    async def list_paginated(
        self,
        *where: ColumnElement[bool],
        page: int = 1,
        page_size: int = 20,
        order_by: Sequence[Any] = (),
        options: Sequence[ORMOption] = (),
    ) -> Page[ModelT]: ...
