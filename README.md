# VTaxi

**A Clean Architecture / DDD ride-booking backend for intercity taxi service — published as an architecture showcase, not a finished product.**

![Python](https://img.shields.io/badge/Python-3.13-3776AB?logo=python&logoColor=white)
![Aiogram](https://img.shields.io/badge/Aiogram-3-2CA5E0)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0%20async-D71F00)
![Tests](https://img.shields.io/badge/tests-6%20passing-brightgreen)
![License](https://img.shields.io/badge/license-proprietary-lightgrey)

[English](README.md) | [O'zbek](README.uz.md)

> **Honest status:** the domain and application layers are substantially implemented for several bounded contexts — booking has a complete state machine, identity/trip/vehicle have real services — but the Telegram bot, API, and admin panel presentation layers are not wired up yet (routers/keyboards/middlewares/states exist only as empty packages). This repository demonstrates architecture and domain-modeling work, not a working bot.

## Description

VTaxi is a Telegram-based intercity taxi booking backend (starting with Namangan ⇄ Tashkent), architected with Clean Architecture and Domain-Driven Design so new city pairs are a data change, not a rewrite. The most mature part of the codebase is the domain and application layer, not the bot itself.

## What's actually implemented vs. not

| Layer | Status |
|---|---|
| `domain/booking`, `application/booking` (booking_service.py, 620 lines) | **Implemented** — full booking state machine (PENDING → RESERVED → ACCEPTED → COMPLETED / REJECTED / CANCELLED / EXPIRED), cross-service seat synchronization |
| `domain/identity`, `application/identity` | **Implemented** — driver/passenger/user services |
| `domain/trip`, `application/trip` | **Implemented** |
| `domain/vehicle`, `application/vehicle` | **Implemented** |
| `application/payment`, `application/matching`, and others | **Scaffolded only** — package exists, no logic yet |
| `presentation/bot` (routers, keyboards, middlewares, states) | **Not implemented** — empty packages |
| `presentation/api`, `presentation/admin_panel` | **Not implemented** — empty packages |
| Database foundation | **Implemented and tested** — SQLAlchemy 2.0 async, Alembic (1 migration) |

## Demo

There is no working UI to screenshot — the presentation layer isn't wired up (see the table above). Rather than fabricate one, here are the four diagrams that document what's actually there, each derived directly from the real code and the real initial migration schema (not a generic template):

| | |
|---|---|
| [Clean Architecture layers](docs/architecture/clean-architecture.svg) | [Bounded contexts](docs/architecture/bounded-contexts.svg) |
| [Booking state machine](docs/architecture/booking-state-machine.svg) | [Database ER diagram](docs/architecture/database-er.svg) |

## Architecture

See [docs/architecture/clean-architecture.svg](docs/architecture/clean-architecture.svg), [docs/architecture/bounded-contexts.svg](docs/architecture/bounded-contexts.svg), [docs/architecture/booking-state-machine.svg](docs/architecture/booking-state-machine.svg), and [docs/architecture/database-er.svg](docs/architecture/database-er.svg).

```
presentation/  (bot, API, admin — not yet wired)
      ↓
application/   (services, Protocol-based ports) — booking, identity, trip, vehicle implemented
      ↓
domain/        (entities, exceptions, per bounded context)
      ↓
infrastructure/ (SQLAlchemy models, repositories, Unit-of-Work)
      ↓
PostgreSQL (async, via asyncpg)
```

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.13, async throughout |
| Bot framework (unwired) | Aiogram 3 |
| Database | PostgreSQL, SQLAlchemy 2.0 async, Alembic |
| DI | Dishka |
| Config | Pydantic Settings |
| Dependency management | uv |
| Task queue | arq |

## Database

PostgreSQL via async SQLAlchemy 2.0. Repository pattern with mixins for UUID primary keys, timestamps, audit fields, and soft deletes; a Unit-of-Work pattern coordinates transactions across repositories. One Alembic migration currently exists (`456c700ca981_initial_schema.py`).

## Testing

6 tests currently pass (`tests/unit/infrastructure/test_database_foundation.py`), covering the database foundation layer. `tests/{unit,integration,e2e}` are otherwise scaffolded but empty — this is the clearest gap before the project could be called production-ready.

```bash
uv run pytest tests/ -q
```

## Deployment

Dockerfile present; `docker compose up -d postgres redis` brings up local infrastructure. No deployed environment currently exists.

## Installation

```powershell
uv sync
Copy-Item .env.example .env
uv run python -m vtaxi
```

You should see `VTaxi initialized successfully` — the skeleton boots, but no bot, API, or handler logic is wired up yet.

## Environment Variables

See [`.env.example`](.env.example) for the full list.

## Project Structure

```
VTaxi/
├── src/vtaxi/
│   ├── domain/          # entities + exceptions per bounded context
│   ├── application/      # services + Protocol-based ports
│   ├── infrastructure/    # SQLAlchemy models, repositories, Unit-of-Work
│   └── presentation/       # bot/ api/ admin_panel/ — not yet implemented
├── migrations/             # Alembic
├── docs/                    # 01-SOFTWARE-ARCHITECTURE.md, 02-PROJECT-STRUCTURE.md,
│                             # 03-DATABASE-DESIGN.md, 04-SQLALCHEMY-FOUNDATION.md
├── tests/
└── pyproject.toml
```

## Roadmap

- [ ] Wire up the Telegram bot presentation layer against the existing application services
- [ ] Implement `payment` and `matching` application logic
- [ ] Expand test coverage beyond the database foundation layer

## License

Proprietary — see [LICENSE](LICENSE). This repository is published as a portfolio/architecture showcase; the license terms reflect the project's original commercial intent and were not changed for this publication.
