"""Shared application-layer kernel. A generic `UnitOfWorkFactory` alias and
the `fail()` helper (Result <-> Domain Exceptions) are implemented now
(Step 8.1); a common "Base UseCase" abstraction is not -- this project's
services are multi-method classes (`UserService.create_user()`,
`.get_user()`, ...), not single-method command objects, so there is no
one-method-shaped interface for a base UseCase class to usefully capture.
"""

from vtaxi.core.application.errors import fail
from vtaxi.core.application.unit_of_work import UnitOfWorkFactory, UowT

__all__ = ["UnitOfWorkFactory", "UowT", "fail"]
