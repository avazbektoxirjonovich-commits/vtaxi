"""Soft-delete mixin plus a global query filter that enforces it.

See docs/03-DATABASE-DESIGN.md SS0.3 for which tables use this (accounts,
profiles, and assets with a deactivate concept) and which deliberately
don't (tables with their own terminal status, and append-only logs).
"""

from datetime import datetime

from sqlalchemy import event
from sqlalchemy.orm import Mapped, ORMExecuteState, Session, mapped_column, with_loader_criteria


class SoftDeleteMixin:
    """Adds `deleted_at`; NULL means the row is active."""

    deleted_at: Mapped[datetime | None] = mapped_column(default=None)

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None


def register_soft_delete_filter() -> None:
    """Exclude soft-deleted rows from every ORM SELECT by default.

    Call once at application startup (Step 8's composition root) -- not
    triggered automatically on import, so importing this module never has a
    surprising global side effect.

    Works transparently with `AsyncSession`: it delegates statement
    execution to a sync `Session` internally, and `do_orm_execute` fires at
    statement-compilation time, before any I/O -- nothing here blocks the
    event loop.

    A caller that genuinely needs deleted rows opts out explicitly:

        await session.execute(stmt, execution_options={"include_deleted": True})
    """

    @event.listens_for(Session, "do_orm_execute")
    def _exclude_soft_deleted(execute_state: ORMExecuteState) -> None:
        if not execute_state.is_select:
            return
        if execute_state.execution_options.get("include_deleted", False):
            return
        execute_state.statement = execute_state.statement.options(
            with_loader_criteria(
                SoftDeleteMixin,
                lambda cls: cls.deleted_at.is_(None),
                include_aliases=True,
            )
        )
