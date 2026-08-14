"""created_by / updated_by actor-tracking mixin.

See docs/03-DATABASE-DESIGN.md SS0.4 for the FK deletion policy this
follows (`SET NULL` -- losing the "who did this" pointer loses a
convenience, not a fact).

Uses `declared_attr` with a *string* FK target (`"users.id"`) rather than
a direct class reference, because SQLAlchemy resolves string-based
`ForeignKey` targets at mapper-configuration time, not at class-body
execution time. That means this mixin can be written now, before `users`
exists as a Python model (explicitly out of scope for this step), and it
will resolve correctly the moment a table literally named `users` is
registered on this same `Base.metadata` -- no rework needed when that
model is added next.

Opt-in, not universal: only mix this into entities actually created or
modified by an identifiable actor. The `*_status_history` tables already
carry their own `changed_by_user_id` for the same purpose and have no
need for this mixin.
"""

import uuid

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, declared_attr, mapped_column


class AuditMixin:
    """Adds `created_by_user_id` and `updated_by_user_id`, both nullable."""

    @declared_attr
    def created_by_user_id(cls) -> Mapped[uuid.UUID | None]:
        return mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    @declared_attr
    def updated_by_user_id(cls) -> Mapped[uuid.UUID | None]:
        return mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
