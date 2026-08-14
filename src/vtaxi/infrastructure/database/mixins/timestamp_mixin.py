"""created_at / updated_at mixin.

See docs/03-DATABASE-DESIGN.md SS0.2. Both columns are DB-generated
(`server_default=func.now()`) rather than Python-side defaults, so they
are correct even for a row inserted by a raw SQL script or a future
non-Python service -- the database, not the application process, is the
single source of truth for "when did this row change."

`onupdate=func.now()` covers every UPDATE that goes through SQLAlchemy.
A trigger-based defense-in-depth for writes issued completely outside the
ORM is a one-time DDL addition that belongs in Step 6's first Alembic
migration, not in this Python model layer.
"""

from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import Mapped, mapped_column


class TimestampMixin:
    """Adds `created_at` and `updated_at`, both UTC (see Base.type_annotation_map)."""

    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
