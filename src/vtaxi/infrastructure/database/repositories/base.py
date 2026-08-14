"""`BaseRepository[ModelT]` -- what every concrete repository in this
project actually extends.

Adds exactly one thing on top of `GenericRepository`: the model class is
bound once, at the class level, so a concrete repository is just

    class UserRepository(BaseRepository[User]):
        model = User

instead of every repository re-implementing `__init__` to forward
`(session, User)` to the generic engine.

Not `ClassVar`: `GenericRepository.__init__` also assigns `self.model`
(an ordinary instance attribute), and mypy rejects a subclass turning an
inherited instance attribute into a `ClassVar` -- a plain annotation here
is compatible with both "provide a class-level default" (what every
concrete repository below does) and "read/write via `self`" (what the
base class's `__init__` does).
"""

from sqlalchemy.ext.asyncio import AsyncSession

from vtaxi.infrastructure.database.repositories.generic import GenericRepository, ModelT


class BaseRepository(GenericRepository[ModelT]):
    """Concrete subclasses must set the `model` class attribute."""

    model: type[ModelT]

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, self.model)
