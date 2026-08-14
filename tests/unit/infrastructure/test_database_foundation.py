"""Verifies the Step 5 SQLAlchemy foundation: Base/metadata configuration,
the four mixins, and the enum wildcard -- with no business entities
involved, only test-scoped throwaway models (table names prefixed `_test_`
so they can never collide with a real table added in a later step).

Uses an in-memory SQLite engine for speed (docs/01 SS7.7: unit tests don't
need a real database). Two properties -- timezone-aware storage and the
enum CHECK constraint -- are instead verified by compiling DDL against the
PostgreSQL dialect, because SQLite has no real tz-aware datetime type and
would silently strip tzinfo on round-trip, which is a SQLite limitation,
not a property of this code (docker-compose.yml pins Postgres 16 for every
real environment).
"""

import enum
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import cast

import pytest
import pytest_asyncio
from sqlalchemy import CheckConstraint, Enum, Table, select
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.schema import CreateTable

from vtaxi.infrastructure.database.base import Base
from vtaxi.infrastructure.database.mixins import (
    AuditMixin,
    SoftDeleteMixin,
    TimestampMixin,
    UUIDMixin,
    register_soft_delete_filter,
)


class _TestColor(enum.StrEnum):
    RED = "RED"
    BLUE = "BLUE"


class _TestWidget(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "_test_foundation_widget"

    name: Mapped[str] = mapped_column()
    color: Mapped[_TestColor] = mapped_column()


class _TestAuditedThing(Base, UUIDMixin, TimestampMixin, AuditMixin):
    __tablename__ = "_test_foundation_audited_thing"

    label: Mapped[str] = mapped_column()


# `DeclarativeBase.__table__` is typed generically as `FromClause` in
# SQLAlchemy's stubs; these mapped classes are always backed by a real
# `Table`, so a single explicit cast here lets everything below be properly
# typed instead of repeating `cast(Table, ...)` at every call site.
_WIDGET_TABLE = cast(Table, _TestWidget.__table__)
_AUDITED_TABLE = cast(Table, _TestAuditedThing.__table__)

# `_TestAuditedThing` is deliberately excluded here: its FK targets a `users`
# table that does not exist yet (see audit_mixin.py), and `create_all()` must
# resolve every FK for whatever tables it's given. That table is only ever
# used for static metadata introspection below, never for DDL emission.
_TEST_TABLES: list[Table] = [_WIDGET_TABLE]


@pytest_asyncio.fixture
async def engine() -> AsyncIterator[AsyncEngine]:
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, tables=_TEST_TABLES)
    try:
        yield eng
    finally:
        await eng.dispose()


def test_naming_convention_applied_to_primary_key_constraint() -> None:
    assert _WIDGET_TABLE.primary_key.name == "pk__test_foundation_widget"


@pytest.mark.asyncio
async def test_uuid_mixin_generates_time_ordered_v7_ids(engine: AsyncEngine) -> None:
    # `default=uuid7` is evaluated at flush time, not at object construction --
    # these need to actually go through a session for `.id` to be populated.
    a, b = _TestWidget(name="a", color=_TestColor.RED), _TestWidget(name="b", color=_TestColor.BLUE)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        session.add_all([a, b])
        await session.commit()

    assert isinstance(a.id, uuid.UUID)
    assert a.id.version == 7
    assert a.id < b.id, "sequentially generated UUIDv7s must be time-ordered"


def test_timestamp_columns_compile_as_timezone_aware_on_postgres() -> None:
    # postgresql.dialect()'s stub return type isn't fully typed -- narrow,
    # justified suppression rather than loosening strict mypy project-wide.
    ddl = str(CreateTable(_WIDGET_TABLE).compile(dialect=postgresql.dialect()))  # type: ignore[no-untyped-call]
    assert "created_at TIMESTAMP WITH TIME ZONE" in ddl
    assert "updated_at TIMESTAMP WITH TIME ZONE" in ddl


def test_enum_column_compiles_as_varchar_with_check_not_native_enum() -> None:
    column_type = cast(Enum, _WIDGET_TABLE.c.color.type)
    assert column_type.native_enum is False
    assert isinstance(column_type.length, int) and column_type.length > 0

    checks = [c for c in _WIDGET_TABLE.constraints if isinstance(c, CheckConstraint)]
    assert any("color" in str(c.sqltext) for c in checks), "expected a CHECK constraint on `color`"

    # postgresql.dialect()'s stub return type isn't fully typed -- narrow,
    # justified suppression rather than loosening strict mypy project-wide.
    ddl = str(CreateTable(_WIDGET_TABLE).compile(dialect=postgresql.dialect()))  # type: ignore[no-untyped-call]
    assert "color VARCHAR" in ddl
    assert "CREATE TYPE" not in ddl.upper(), "must not emit a native PostgreSQL ENUM type"


def test_audit_mixin_fk_targets_users_with_set_null() -> None:
    """No `users` table needs to exist for this: ForeignKey.target_fullname
    and .ondelete are read directly off the (string-based) FK definition,
    resolved lazily only if/when the target is actually needed for a join
    or DDL emission -- see audit_mixin.py's docstring.
    """
    column = _AUDITED_TABLE.c.created_by_user_id
    fk = next(iter(column.foreign_keys))
    assert fk.target_fullname == "users.id"
    assert fk.ondelete == "SET NULL"
    assert column.nullable is True


@pytest.mark.asyncio
async def test_soft_delete_filter_excludes_by_default_and_can_opt_out(
    engine: AsyncEngine,
) -> None:
    register_soft_delete_filter()
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        alive = _TestWidget(name="alive", color=_TestColor.RED)
        deleted = _TestWidget(name="deleted", color=_TestColor.BLUE, deleted_at=datetime.now(UTC))
        session.add_all([alive, deleted])
        await session.commit()

        default_names = {w.name for w in (await session.execute(select(_TestWidget))).scalars()}
        assert default_names == {"alive"}

        all_names = {
            w.name
            for w in (
                await session.execute(
                    select(_TestWidget), execution_options={"include_deleted": True}
                )
            ).scalars()
        }
        assert all_names == {"alive", "deleted"}
