import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncEngine

# Populates Base.metadata as a side effect of import -- every model must be
# importable from this one package (see models/__init__.py) or autogenerate
# silently won't see its table.
import vtaxi.infrastructure.database.models  # noqa: F401
from vtaxi.config.settings import get_settings
from vtaxi.infrastructure.database.base import Base
from vtaxi.infrastructure.database.engine import create_engine

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# The single source of truth for *what tables exist* -- see docs/04-
# SQLALCHEMY-FOUNDATION.md: there is exactly one Base/MetaData in this
# system, every model inherits from it, and this is where Alembic is
# pointed at it.
target_metadata = Base.metadata

# The single source of truth for *the connection string* is `Settings`
# (src/vtaxi/config/settings.py), which reads `.env` -- not a hardcoded
# `sqlalchemy.url` in alembic.ini, which would need to be kept in sync by
# hand and inevitably drift. `create_engine()` (the same factory the app
# itself uses) builds the engine from `Settings`, so migrations always run
# against whatever `.env`/environment variables the app itself would use.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = get_settings().database_url
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Create an engine via the app's own factory (see module docstring)
    and associate a connection with the migration context.
    """

    connectable: AsyncEngine = create_engine()

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""

    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
