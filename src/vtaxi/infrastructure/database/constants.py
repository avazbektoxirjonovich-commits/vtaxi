"""Schema-wide constants: naming convention and default column sizes.

Business-rule constants (rating bounds, seat limits, ...) intentionally do
NOT live here -- they belong colocated with the model/constraint they
govern, once that model exists. This file is strictly schema
infrastructure, matching this step's scope.
"""

# Applied to Base.metadata (see base.py) so Alembic autogenerate produces
# deterministic constraint names instead of PostgreSQL's anonymous defaults --
# critical for reliable upgrade/downgrade scripts across environments.
NAMING_CONVENTION: dict[str, str] = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

# Fallback VARCHAR length for general-purpose text columns (names, etc.).
DEFAULT_STRING_LENGTH: int = 255

# VARCHAR length for short codes: phone numbers, plate numbers, and similar.
SHORT_STRING_LENGTH: int = 50

# VARCHAR length backing every enum column (see types.py). One uniform,
# generous length instead of docs/03's per-column values (10-30 chars):
# PostgreSQL's VARCHAR(n) has no storage-size difference from the declared
# max length -- it is a constraint, not fixed-width allocation -- so a
# single global rule is simpler than re-specifying a length per column
# everywhere, at no real cost. Widest current enum value is 23 characters
# ("ADVERTISEMENT_CANCELLED"); 50 leaves headroom for future values.
ENUM_BACKING_LENGTH: int = 50
