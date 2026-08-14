"""The single SQLAlchemy declarative base for the entire application.

Every ORM model, in every bounded context (`domain/<context>/`), inherits
from this one `Base` -- never a per-context declarative base. Alembic
(Step 6) points its `target_metadata` at `Base.metadata`; if two contexts
defined separate declarative bases, autogenerate would only ever see one
of them and silently miss the other's tables.
"""

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

from vtaxi.infrastructure.database.constants import NAMING_CONVENTION
from vtaxi.infrastructure.database.types import TYPE_ANNOTATION_MAP


class Base(DeclarativeBase):
    """Declarative base shared by every mapped class. See module docstring."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)
    type_annotation_map = TYPE_ANNOTATION_MAP
