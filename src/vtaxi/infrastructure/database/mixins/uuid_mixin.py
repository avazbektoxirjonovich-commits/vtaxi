"""Primary-key mixin: UUIDv7, application-generated.

See docs/03-DATABASE-DESIGN.md SS0.1 and SS6 item 1. PostgreSQL 16 (this
project's target -- see docker-compose.yml) has no native `uuidv7()`;
UUIDv7 is generated in Python at flush time via `uuid6.uuid7()` instead.
Time-ordered UUIDs keep the primary-key B-tree index append-mostly under
concurrent writes, avoiding the page-split/fragmentation cost a fully
random UUIDv4 primary key would cause once tables like `bookings` reach
millions of rows -- while still requiring no cross-service coordination,
the property that made UUIDs attractive as a primary key in the first
place.

Generation happens as a plain Python callable (`default=uuid7`), evaluated
by SQLAlchemy at flush time -- an in-memory clock read plus a few random
bytes, not I/O, so this has no bearing on async/event-loop behavior.
"""

import uuid

from sqlalchemy.orm import Mapped, mapped_column
from uuid6 import uuid7


class UUIDMixin:
    """Adds a UUIDv7 primary key column named `id`."""

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid7)
