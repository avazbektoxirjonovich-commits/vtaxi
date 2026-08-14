"""The shared shape of "a factory that hands out a Unit of Work" -- generic
over whichever Unit-of-Work Protocol a given bounded context actually
needs, so this one alias is reusable by every future `application/<context>/`
service module without depending on any of them.

Each context (e.g. `application/identity/ports.py`) defines its own
narrow Unit-of-Work Protocol, scoped to exactly the repositories that
context's services use -- not one bloated Protocol here listing every
repository across the whole system. The concrete
`infrastructure/database/repositories/unit_of_work.UnitOfWork` (Step 7)
structurally satisfies all of them simultaneously, since it already has
every attribute any of them could ask for; nothing here imports it.
"""

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from typing import TypeVar

UowT = TypeVar("UowT")

# A zero-argument callable returning an async context manager that yields a
# `UowT` (some context-specific Unit-of-Work Protocol) -- e.g.
# `RepositoryFactory.unit_of_work` (Step 7) satisfies this shape for
# `UowT = IdentityUnitOfWork` without either module importing the other.
UnitOfWorkFactory = Callable[[], AbstractAsyncContextManager[UowT]]

__all__ = ["UnitOfWorkFactory", "UowT"]
