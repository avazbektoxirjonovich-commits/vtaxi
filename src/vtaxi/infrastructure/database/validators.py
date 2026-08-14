"""Generic, business-agnostic validation guards.

Not wired to any model -- there are none yet, per this step's scope. Meant
to be called from a future concrete model's `@validates(...)` method, e.g.:

    @validates("full_name")
    def _validate_full_name(self, key: str, value: str) -> str:
        return ensure_not_blank(value, field_name=key)

Not one of the file paths named in the Step 5 brief (`base.py`, `mixins/`,
`enums/`, `constants.py`, `types.py`); added because "common validators"
(item 8) needs a home and none of those five is the right fit for it.
"""

from datetime import UTC, datetime
from decimal import Decimal

Number = int | float | Decimal


def ensure_not_blank(value: str, *, field_name: str) -> str:
    """Reject an empty or whitespace-only string; return it stripped."""
    stripped = value.strip()
    if not stripped:
        raise ValueError(f"{field_name} must not be blank")
    return stripped


def ensure_positive(value: Number, *, field_name: str) -> Number:
    """Reject a value that is not strictly greater than zero."""
    if value <= 0:
        raise ValueError(f"{field_name} must be greater than zero")
    return value


def ensure_non_negative(value: Number, *, field_name: str) -> Number:
    """Reject a negative value (zero is allowed)."""
    if value < 0:
        raise ValueError(f"{field_name} must not be negative")
    return value


def ensure_not_in_future_year(value: int, *, field_name: str) -> int:
    """Reject a year later than the current UTC year."""
    current_year = datetime.now(UTC).year
    if value > current_year:
        raise ValueError(f"{field_name} must not be in the future")
    return value


def ensure_within_range(
    value: Number, *, minimum: Number, maximum: Number, field_name: str
) -> Number:
    """Reject a value outside the inclusive [minimum, maximum] range."""
    if not minimum <= value <= maximum:
        raise ValueError(f"{field_name} must be between {minimum} and {maximum}")
    return value
