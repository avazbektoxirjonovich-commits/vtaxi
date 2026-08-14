# VTaxi — Project Structure & Foundation

**Step 2 of the staged build plan. Status: skeleton complete, verified, no business logic.**

This document explains every directory created in this step and why it exists. It assumes [`01-SOFTWARE-ARCHITECTURE.md`](01-SOFTWARE-ARCHITECTURE.md) (layers, the 16 bounded contexts, the Dependency Rule) has been read first — this document is that architecture turned into folders, nothing more.

## What this step deliberately does NOT contain

No entities, no SQLAlchemy models, no repositories, no use cases, no Aiogram handlers. Every context package under `domain/` and `application/` holds a single `__init__.py` with a docstring naming what will live there and which architecture-doc section justifies it — a signpost, not an implementation. Filling them in is Step 6 (Core Domain) onward.

## Full tree

```
VTaxi/
├── configs/                     # static, non-secret runtime config assets
│   ├── logging.yaml
│   └── README.md
├── docs/                        # architecture & process documentation
│   ├── 01-SOFTWARE-ARCHITECTURE.md
│   └── 02-PROJECT-STRUCTURE.md
├── migrations/                  # reserved for Alembic (Step 5)
│   └── README.md
├── scripts/                     # one-off dev scripts, not part of the package
│   └── README.md
├── src/
│   └── vtaxi/                   # the installable package (src-layout)
│       ├── application/         # use cases + ports, one subpackage per bounded context
│       │   ├── advertisement/
│       │   ├── audit_log/
│       │   ├── booking/
│       │   ├── complaint/
│       │   ├── driver_verification/
│       │   ├── geo_engine/
│       │   ├── geography/
│       │   ├── identity/
│       │   ├── matching/
│       │   ├── notification/
│       │   ├── payment/
│       │   ├── queue_engine/
│       │   ├── rating/
│       │   ├── search_engine/
│       │   ├── statistics/
│       │   └── trip/
│       ├── config/               # Settings + logging (real code, see below)
│       │   ├── logging.py
│       │   └── settings.py
│       ├── core/                 # shared kernel base types (empty until Step 6/8)
│       │   ├── application/
│       │   └── domain/
│       ├── di/                   # composition root (empty until Step 8/9)
│       │   └── container.py
│       ├── domain/               # entities, VOs, domain services — mirrors application/
│       │   ├── advertisement/
│       │   ├── audit_log/
│       │   ├── booking/
│       │   ├── complaint/
│       │   ├── driver_verification/
│       │   ├── geo_engine/
│       │   ├── geography/
│       │   ├── identity/
│       │   ├── matching/
│       │   ├── notification/
│       │   ├── payment/
│       │   ├── queue_engine/
│       │   ├── rating/
│       │   ├── search_engine/
│       │   ├── statistics/
│       │   └── trip/
│       ├── infrastructure/       # concrete adapters implementing application/ ports
│       │   ├── cache/
│       │   ├── database/
│       │   ├── notifications/
│       │   ├── payment_providers/
│       │   │   ├── click/
│       │   │   ├── payme/
│       │   │   └── paynet/
│       │   └── telegram_files/
│       ├── presentation/         # delivery mechanisms
│       │   ├── admin_panel/      # future web admin panel
│       │   ├── api/              # future REST API
│       │   └── bot/              # Aiogram 3 (Step 7)
│       │       ├── keyboards/
│       │       ├── middlewares/
│       │       ├── routers/
│       │       └── states/
│       ├── __main__.py           # enables `python -m vtaxi`
│       └── main.py               # entrypoint: configure_logging + settings + boot log
├── tests/
│   ├── e2e/                      # bot scenario tests (Aiogram test utilities)
│   ├── integration/               # repositories/adapters against real Postgres/Redis
│   └── unit/                      # domain + application against fakes, no DB
├── .env.example
├── .gitignore
├── .pre-commit-config.yaml
├── .python-version                # pins 3.13 for uv
├── docker-compose.yml
├── Dockerfile
├── LICENSE
├── Makefile
├── pyproject.toml
├── README.md
└── uv.lock
```

## Why `src/vtaxi/` and not a flat `vtaxi/` at repo root

The `src` layout forces the package to be installed (`uv sync`) rather than importable by accident from the repo root, which is what catches "it works on my machine because I'm in the right directory" bugs before they reach a teammate or CI. Standard for any Python project expected to be packaged, tested, and eventually containerized.

## Why `domain/<context>/` and `application/<context>/` are separate trees, both split the same way

Layer separation is horizontal (domain vs. application vs. infrastructure vs. presentation — the Dependency Rule, docs/01 §2.1); bounded-context separation is vertical (16 contexts, docs/01 §3 and §14.12). Both cuts are needed simultaneously, so every context gets a same-named folder in both `domain/` and `application/`: `domain/booking/` holds the `Booking` entity and its invariants, `application/booking/` holds the use cases that orchestrate it. Nothing under `domain/` ever imports from `application/`, `infrastructure/`, or `presentation/` — only the reverse.

## Why `core/` exists but is still empty

`core/domain/` and `core/application/` will hold the base `Entity`, `ValueObject`, `AggregateRoot`, `DomainEvent`, and `UseCase`/port base types shared by all 16 contexts. They stay empty in this step on purpose: writing them now, before any concrete entity needs them, would mean guessing their shape. Step 6 (Core Domain) writes them against the first real entities.

## Why `config/` (in the package) and `configs/` (at repo root) both exist

`src/vtaxi/config/` is Python code: `settings.py` (Pydantic Settings, reads `.env`) and `logging.py` (applies `logging.config.dictConfig`). `configs/` at the repo root is a data asset directory: today it holds `logging.yaml`, the actual dictConfig definition `logging.py` loads. This keeps configuration *code* and configuration *data* separated — `configs/logging.yaml` can be edited by an ops person without touching Python, and `config/logging.py` has no business logic, only wiring.

## Root-level files

| File | Purpose |
|---|---|
| `pyproject.toml` | Project metadata, dependencies, and **all** tool config (Ruff, Black, MyPy, Pytest) in one place — uv-native, no scattered `setup.cfg`/`.flake8`. |
| `uv.lock` | Exact resolved dependency versions, committed so every environment (dev machine, CI, Docker) installs identical packages. |
| `.python-version` | Pins Python 3.13 for `uv sync`/`uv run` (uv downloaded 3.13.13 automatically — see verification below). |
| `.pre-commit-config.yaml` | Runs Ruff (lint+fix), Black (format), MyPy (types), and basic hygiene hooks before every commit. |
| `.gitignore` | Excludes `.venv/`, `.env`, tool caches, bytecode. |
| `.env.example` | Documents every setting `Settings` reads, with safe non-secret defaults; copy to `.env` and fill in real values. |
| `docker-compose.yml` | Local Postgres 16 + Redis 7 with healthchecks, plus a `bot` service; a commented `worker` service is reserved for Step 5. |
| `Dockerfile` | Multi-layer build (`python:3.13-slim` + `uv`) — dependency layer cached separately from source-code layer. |
| `Makefile` | `make install / run / lint / format / typecheck / test / check / docker-up / docker-down`. |
| `README.md` | Quick start + staged build plan status. |
| `LICENSE` | Proprietary placeholder (see the file itself — replace if the project's licensing intent differs). |

## Verification performed for this step

Every check below was actually run against this skeleton, not assumed:

| Check | Command | Result |
|---|---|---|
| Dependency install | `uv sync` | 59 packages resolved & installed; uv auto-downloaded CPython 3.13.13 |
| Boots | `uv run python -m vtaxi` | `VTaxi initialized successfully (environment=development)` |
| Lint | `uv run ruff check .` | All checks passed |
| Format | `uv run black --check .` | 66 files unchanged |
| Types | `uv run mypy src` | Success: no issues found in 62 source files |
| Tests | `uv run pytest` | 0 collected (expected — no tests exist yet; config itself is valid) |

## Next Step

**Step 3 — Database Design**: analyze entities per bounded context, produce an ER diagram, explain relationships, *then* write SQLAlchemy 2.0 models — in that order, per the approved process.

**Continue to next step?**
