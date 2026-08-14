# migrations/

Alembic migration environment (async template). `env.py` builds its engine
via `vtaxi.infrastructure.database.engine.create_engine()` -- the same
factory the application uses -- reading the connection string from
`Settings` (`.env`), not from `alembic.ini`. `target_metadata` is
`Base.metadata`, populated by importing
`vtaxi.infrastructure.database.models` (every model, one place).

Common commands (see the Makefile):

```
uv run alembic revision --autogenerate -m "message"
uv run alembic upgrade head
uv run alembic downgrade -1
```
