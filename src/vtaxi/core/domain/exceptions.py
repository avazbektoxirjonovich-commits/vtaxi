"""`BaseDomainException` -- the root of every domain exception in this
system -- plus three shared intermediate categories (`NotFoundError`,
`AlreadyExistsError`, `InvalidStateError`) that recur across nearly every
bounded context.

Framework-independent by construction: this module imports nothing but
the standard library and `error_codes.py`. A Telegram handler, a future
FastAPI route, or a mobile app's API layer can all catch `NotFoundError`
generically (map it to "not found" in whatever form that surface uses)
without knowing about `UserNotFoundError` vs `BookingNotFoundError`
specifically -- while still being able to catch the specific one when it
matters.
"""

from typing import Any, ClassVar

from vtaxi.core.domain.error_codes import ErrorCode


class BaseDomainException(Exception):  # noqa: N818 -- name required by this step's brief
    """Never raised directly -- every concrete exception (in this module
    or a `domain/<context>/exceptions.py`) sets `error_code` and
    `default_message` as class attributes and is raised as itself, e.g.
    `raise UserNotFoundError(user_id=some_id)`.

    `details` carries arbitrary structured context (the id that wasn't
    found, the state that blocked the operation, ...) for whatever logs
    or serializes this exception later -- never used to change control
    flow within this class itself.
    """

    error_code: ClassVar[ErrorCode]
    default_message: ClassVar[str] = "A domain error occurred."

    def __init__(self, message: str | None = None, **details: Any) -> None:
        if type(self) is BaseDomainException:
            raise TypeError("BaseDomainException must not be raised directly")
        resolved_message = message or self.default_message
        super().__init__(resolved_message)
        self.message = resolved_message
        self.details = details


class NotFoundError(BaseDomainException):
    """Shared base for every "<X> not found" exception."""

    default_message = "The requested resource was not found."


class AlreadyExistsError(BaseDomainException):
    """Shared base for every "<X> already exists" exception."""

    default_message = "The resource already exists."


class InvalidStateError(BaseDomainException):
    """Shared base for "<X> cannot do this in its current state" errors --
    expired, cancelled, completed, already started, banned, blocked, not
    verified, not approved, and similar.
    """

    default_message = "The resource is not in a valid state for this operation."


__all__ = [
    "AlreadyExistsError",
    "BaseDomainException",
    "InvalidStateError",
    "NotFoundError",
]
