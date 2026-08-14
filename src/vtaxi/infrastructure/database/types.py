"""Shared, reusable SQLAlchemy 2.0 type configuration.

See docs/03-DATABASE-DESIGN.md SS0.5: every enumerated column is stored as
VARCHAR + CHECK, never a native PostgreSQL ENUM type, because native enums
are cheap to add a value to but expensive to rename or remove -- and this
project's business vocabularies (complaint reasons, audit actions, ...)
are exactly the kind of thing that gains values over time.
"""

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Enum, Uuid
from sqlalchemy.types import TypeEngine

from vtaxi.infrastructure.database.constants import ENUM_BACKING_LENGTH

# Registered on Base.type_annotation_map (see base.py). The `enum.Enum` entry
# is a wildcard: for any `Mapped[SomeConcreteEnum]` annotation, SQLAlchemy
# reuses this configuration (native_enum=False, validate_strings=True, one
# uniform length) but substitutes in the concrete enum class actually used --
# so every future enum column gets the SS0.5 policy automatically, with zero
# per-column boilerplate.
#
# `datetime` always maps to a timezone-aware column: every timestamp in this
# system is UTC, no exceptions, so there is no case where the naive variant
# is the right default.
#
# `uuid.UUID` always maps to the dialect-native UUID type (`as_uuid=True`
# returns real `uuid.UUID` Python objects, not strings).
TYPE_ANNOTATION_MAP: dict[type, TypeEngine[Any]] = {
    datetime: DateTime(timezone=True),
    uuid.UUID: Uuid(as_uuid=True),
    enum.Enum: Enum(
        enum.Enum,
        native_enum=False,
        create_constraint=True,
        validate_strings=True,
        length=ENUM_BACKING_LENGTH,
    ),
}


def pg_enum(enum_cls: type[enum.Enum], *, length: int = ENUM_BACKING_LENGTH) -> Enum:
    """Explicit override for a column that needs different `Enum` config than
    the global default above (a longer `length`, for instance). Most columns
    should just declare `Mapped[SomeEnum]` and rely on `TYPE_ANNOTATION_MAP`
    instead of calling this directly.
    """
    return Enum(
        enum_cls,
        native_enum=False,
        create_constraint=True,
        validate_strings=True,
        length=length,
    )
