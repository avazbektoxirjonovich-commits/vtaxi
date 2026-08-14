"""Ties `core.domain.exceptions` and `core.domain.result` together for
every future service: an expected business-rule violation (already
exists, not found, wrong state, ...) is reported as a `Failure`, using the
matching `BaseDomainException` subclass purely as a source of its
`error_code`/`default_message` -- never actually raised. Raising stays
reserved for genuinely exceptional situations a service doesn't expect to
handle itself (see each service module for whether it does).
"""

from vtaxi.core.domain.exceptions import BaseDomainException
from vtaxi.core.domain.result import Failure, Result


def fail(exc_cls: type[BaseDomainException], message: str | None = None) -> Failure:
    """`return fail(UserAlreadyExistsError)` instead of
    `return Result.fail(ErrorCode.USER_ALREADY_EXISTS, "...")` -- one
    source of truth (the exception class) for both the code and the
    default wording, so they can never silently drift apart.
    """
    return Result.fail(exc_cls.error_code, message or exc_cls.default_message)


__all__ = ["fail"]
