"""The Result pattern: how a future use case reports success or failure
to its caller without raising across a layer boundary -- an alternative
to letting a `BaseDomainException` propagate, for callers (a Telegram
handler, a future REST endpoint) that want to branch on outcome rather
than catch exceptions.

Pure data, no I/O, no framework import -- "async-friendly" here just
means nothing in this module does anything that could need to be
awaited; a `Result[T]` is exactly as usable from inside a coroutine as
outside one.

`Result` itself is never instantiated -- it exists for its two static
factories (`Result.ok()` / `Result.fail()`) and as the type-annotation
spelling `Result[T]` for "either a `Success[T]` or a `Failure`". Concrete
instances are always actually a `Success[T]` or a `Failure`.
"""

from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

from vtaxi.core.domain.error_codes import ErrorCode

T = TypeVar("T")
T_co = TypeVar("T_co", covariant=True)


class Result(ABC, Generic[T_co]):
    """Shared property contract for `Success[T]`/`Failure`. See module
    docstring for why this class is never instantiated directly.
    """

    @property
    @abstractmethod
    def is_success(self) -> bool: ...

    @property
    def is_failure(self) -> bool:
        return not self.is_success

    @property
    @abstractmethod
    def data(self) -> T_co | None: ...

    @property
    @abstractmethod
    def error_code(self) -> ErrorCode | None: ...

    @property
    @abstractmethod
    def message(self) -> str | None: ...

    @staticmethod
    def ok(data: T) -> "Success[T]":
        return Success(data)

    @staticmethod
    def fail(error_code: ErrorCode, message: str = "") -> "Failure":
        return Failure(error_code, message)


class Success(Result[T_co]):
    """A successful outcome carrying `data`. `error_code`/`message` are
    always `None` -- there is nothing to report.
    """

    __slots__ = ("_value",)

    def __init__(self, value: T_co) -> None:
        self._value = value

    def __repr__(self) -> str:
        return f"Success({self._value!r})"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Success) and self._value == other._value

    @property
    def is_success(self) -> bool:
        return True

    @property
    def data(self) -> T_co:
        return self._value

    @property
    def error_code(self) -> None:
        return None

    @property
    def message(self) -> None:
        return None


class Failure(Result[Any]):
    """A failed outcome: no `data` (always `None`), an `ErrorCode`, and a
    human-readable `message`. Not generic over `T` -- a failure never
    carries a success value to be generic *about*; it is still assignable
    wherever a `Result[T]` (for any `T`) is expected, since `Result`'s
    type parameter is covariant and this extends `Result[Any]`.
    """

    __slots__ = ("_error_code", "_message")

    def __init__(self, error_code: ErrorCode, message: str = "") -> None:
        self._error_code = error_code
        self._message = message or error_code.value

    def __repr__(self) -> str:
        return f"Failure({self._error_code!r}, {self._message!r})"

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, Failure)
            and self._error_code == other._error_code
            and self._message == other._message
        )

    @property
    def is_success(self) -> bool:
        return False

    @property
    def data(self) -> None:
        return None

    @property
    def error_code(self) -> ErrorCode:
        return self._error_code

    @property
    def message(self) -> str:
        return self._message


__all__ = ["Failure", "Result", "Success"]
