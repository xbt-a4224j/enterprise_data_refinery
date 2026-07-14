.PHONY: dev test lint up down fmt migrate
dev:
	uv sync
test:
	uv run pytest
lint:
	uv run ruff check .
fmt:
	uv run ruff format .
up:
	docker compose up --build
down:
	docker compose down -v
migrate:
	uv run alembic upgrade head
