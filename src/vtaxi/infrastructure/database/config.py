"""Environment-aware assembly of async engine keyword arguments.

`Settings` (src/vtaxi/config/settings.py) owns the raw, environment-
overridable pool knobs; this module decides how to turn them into actual
`create_async_engine(...)` kwargs per environment -- kept separate so
"what can be tuned" (Settings) and "what the default tuning is per
environment" (here) don't live in the same class.
"""

from typing import Any

from sqlalchemy.pool import NullPool

from vtaxi.config.settings import Settings


def get_engine_kwargs(settings: Settings) -> dict[str, Any]:
    """Build the kwargs `create_async_engine` needs for the given environment.

    `testing` uses `NullPool`: a fresh connection per checkout, no pooling
    at all -- avoids a pooled connection being reused across event loops
    or test functions, which is where async pool + pytest cross-test
    connection reuse bugs usually come from. `pool_size`/`max_overflow`
    are meaningless with `NullPool` and are omitted, not just set to zero.
    """
    if settings.environment == "testing":
        return {"poolclass": NullPool, "pool_pre_ping": settings.db_pool_pre_ping}

    return {
        "pool_size": settings.db_pool_size,
        "max_overflow": settings.db_max_overflow,
        "pool_timeout": settings.db_pool_timeout,
        "pool_recycle": settings.db_pool_recycle,
        "pool_pre_ping": settings.db_pool_pre_ping,
    }
