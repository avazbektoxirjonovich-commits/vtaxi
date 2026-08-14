.PHONY: install run lint format typecheck test check precommit-install docker-up docker-down docker-logs migrate migration

install:
	uv sync

run:
	uv run python -m vtaxi

lint:
	uv run ruff check .

format:
	uv run black .
	uv run ruff check . --fix

typecheck:
	uv run mypy src

test:
	uv run pytest

check: lint typecheck test

precommit-install:
	uv run pre-commit install

docker-up:
	docker compose up -d

docker-down:
	docker compose down

docker-logs:
	docker compose logs -f

migrate:
	uv run alembic upgrade head

migration:
	uv run alembic revision --autogenerate -m "$(m)"
