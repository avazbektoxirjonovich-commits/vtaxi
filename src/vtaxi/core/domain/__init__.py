"""Base Entity, ValueObject, and AggregateRoot types shared by all bounded
contexts are still pending (Step 6). `ErrorCode`, `BaseDomainException`
(+ `NotFoundError`/`AlreadyExistsError`/`InvalidStateError`), and the
`Result`/`Success`/`Failure` pattern are implemented now -- see
error_codes.py/exceptions.py/result.py -- re-exported here for convenience.
"""

from vtaxi.core.domain.error_codes import ErrorCode
from vtaxi.core.domain.exceptions import (
    AlreadyExistsError,
    BaseDomainException,
    InvalidStateError,
    NotFoundError,
)
from vtaxi.core.domain.result import Failure, Result, Success

__all__ = [
    "AlreadyExistsError",
    "BaseDomainException",
    "ErrorCode",
    "Failure",
    "InvalidStateError",
    "NotFoundError",
    "Result",
    "Success",
]
