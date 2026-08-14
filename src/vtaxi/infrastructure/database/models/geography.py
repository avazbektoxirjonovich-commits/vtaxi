"""Geography domain ORM models: the administrative-area tree and the
whitelist of supported travel directions between areas.

See docs/03-DATABASE-DESIGN.md SS2.2 for the original design; this module
extends it with `postal_code`, `sort_order`/`display_order`, and two more
tree levels (TOWN, STREET), and renames `centroid_latitude`/
`centroid_longitude` to `latitude`/`longitude` per this round's brief.

Placed under `infrastructure/database/models/`, not `domain/geography/`,
for the same Dependency Rule reason as the Identity models.
"""

import uuid
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from vtaxi.infrastructure.database.base import Base
from vtaxi.infrastructure.database.enums import AdministrativeAreaLevel
from vtaxi.infrastructure.database.mixins import TimestampMixin, UUIDMixin
from vtaxi.infrastructure.database.validators import ensure_non_negative, ensure_not_blank


class AdministrativeArea(Base, UUIDMixin, TimestampMixin):
    """Self-referencing hierarchy: COUNTRY -> REGION -> DISTRICT -> CITY ->
    TOWN -> VILLAGE -> MAHALLA -> STREET. Arbitrary depth by construction --
    a new level is a new `AdministrativeAreaLevel` value plus data rows,
    never a schema change. No `SoftDeleteMixin`: like `Direction`, this is
    reference/master data deactivated via `is_active`, not soft-deleted
    (docs/03-DATABASE-DESIGN.md SS0.3).

    `parent`/`children` deliberately do NOT default to `lazy="selectin"`:
    the relationship is self-referential and unbounded in depth, so an
    eager-by-default strategy would cascade into loading the entire
    reachable subtree on every query that touches even one row. Callers
    opt in per query with `.options(selectinload(AdministrativeArea.children))`
    for the one level they actually need.

    The GIN trigram index below (Search Engine autocomplete, docs/01
    SS14.9) requires the `pg_trgm` extension; enabling it is a migration
    concern (`CREATE EXTENSION IF NOT EXISTS pg_trgm`), not something an
    ORM model can do -- left for the first Alembic migration.
    """

    __tablename__ = "administrative_areas"
    __table_args__ = (
        CheckConstraint("id != parent_id", name="no_self_parent"),
        Index("ix_administrative_areas_parent_sort", "parent_id", "sort_order"),
        Index("ix_administrative_areas_parent_name", "parent_id", "name"),
        Index("ix_administrative_areas_level", "level"),
        Index(
            "ix_administrative_areas_name_trgm",
            "name",
            postgresql_using="gin",
            postgresql_ops={"name": "gin_trgm_ops"},
        ),
        # Interim, non-PostGIS support for bounding-box "nearby" queries.
        # True nearest-neighbor search wants a GiST/PostGIS index later --
        # see the module docstring; that upgrade never requires changing
        # these Numeric columns, only adding an index.
        Index("ix_administrative_areas_lat_lng", "latitude", "longitude"),
    )

    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("administrative_areas.id", ondelete="RESTRICT")
    )
    name: Mapped[str] = mapped_column(String(150))
    level: Mapped[AdministrativeAreaLevel]
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    postal_code: Mapped[str | None] = mapped_column(String(20))
    is_active: Mapped[bool] = mapped_column(default=True)
    sort_order: Mapped[int] = mapped_column(default=0)

    parent: Mapped["AdministrativeArea | None"] = relationship(
        "AdministrativeArea",
        remote_side="AdministrativeArea.id",
        foreign_keys="AdministrativeArea.parent_id",
        back_populates="children",
    )
    children: Mapped[list["AdministrativeArea"]] = relationship(
        "AdministrativeArea",
        foreign_keys="AdministrativeArea.parent_id",
        back_populates="parent",
    )

    @validates("name")
    def _validate_name(self, key: str, value: str) -> str:
        return ensure_not_blank(value, field_name=key)

    @validates("sort_order")
    def _validate_sort_order(self, key: str, value: int) -> int:
        return int(ensure_non_negative(value, field_name=key))


class Direction(Base, UUIDMixin, TimestampMixin):
    """A supported, admin-enabled travel corridor between two
    `AdministrativeArea` rows (docs/03-DATABASE-DESIGN.md SS2.2).
    Directional: Namangan->Tashkent and Tashkent->Namangan are two rows,
    not one symmetric row, since demand and matching results differ by
    direction. No `SoftDeleteMixin` -- deactivated via `is_active`.

    Deeper hierarchy validation ("destination must be a real city-level
    area", "origin and destination must not be the same subtree") is not
    expressible in a portable CHECK constraint against a recursive tree
    and belongs in a future application-layer service, not this model;
    only same-row self-reference is guarded here at the database level.
    """

    __tablename__ = "directions"
    __table_args__ = (
        # No explicit `name=`: the naming convention (constants.py) derives
        # `uq_directions_origin_area_id` from column_0 alone -- a known
        # limitation of that convention for multi-column uniqueness, fine
        # while this is the schema's only such constraint.
        UniqueConstraint("origin_area_id", "destination_area_id"),
        CheckConstraint("origin_area_id != destination_area_id", name="no_self_direction"),
    )

    origin_area_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("administrative_areas.id", ondelete="RESTRICT")
    )
    destination_area_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("administrative_areas.id", ondelete="RESTRICT")
    )
    is_active: Mapped[bool] = mapped_column(default=True)
    display_order: Mapped[int] = mapped_column(default=0)

    origin_area: Mapped["AdministrativeArea"] = relationship(
        foreign_keys=[origin_area_id],
        lazy="selectin",
    )
    destination_area: Mapped["AdministrativeArea"] = relationship(
        foreign_keys=[destination_area_id],
        lazy="selectin",
    )

    @validates("display_order")
    def _validate_display_order(self, key: str, value: int) -> int:
        return int(ensure_non_negative(value, field_name=key))


__all__ = ["AdministrativeArea", "Direction"]
