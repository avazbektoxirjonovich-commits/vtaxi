"""Composable model mixins.

Compose only what a concrete model needs -- these are building blocks, not
a mandatory bundle. See docs/03-DATABASE-DESIGN.md SS0 for which tables
need which mixin, and the individual mixin modules for why each exists.
"""

from vtaxi.infrastructure.database.mixins.audit_mixin import AuditMixin
from vtaxi.infrastructure.database.mixins.soft_delete_mixin import (
    SoftDeleteMixin,
    register_soft_delete_filter,
)
from vtaxi.infrastructure.database.mixins.timestamp_mixin import TimestampMixin
from vtaxi.infrastructure.database.mixins.uuid_mixin import UUIDMixin

__all__ = [
    "AuditMixin",
    "SoftDeleteMixin",
    "TimestampMixin",
    "UUIDMixin",
    "register_soft_delete_filter",
]
