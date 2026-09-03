.PHONY: api mobile test lint verify web up down seed

up:
	docker compose up --build

down:
	docker compose down

api:
	cd backend && uv run uvicorn app.main:app --reload

mobile:
	cd mobile && npm run start

test:
	cd backend && uv run pytest

lint:
	cd backend && uv run ruff check app tests migrations
	cd backend && uv run ruff format --check app tests migrations
	cd mobile && npm run typecheck

verify: lint
	cd backend && uv run alembic upgrade head
	cd backend && uv run alembic check
	cd backend && uv run pytest --cov=app
	cd mobile && npm run doctor
	cd mobile && npx expo export --platform web

web:
	cd mobile && npx expo export --platform web

seed:
	cd backend && uv run python -m app.seed
