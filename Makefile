# Entropia V18 — developer convenience targets (macOS / Linux).
# Windows users: use the mirror scripts in scripts/*.ps1 (see README).
.DEFAULT_GOAL := help
SHELL := /bin/bash

COMPOSE := docker compose
# dev-auth (X-Actor-Id impersonation) layers the override ON TOP of the base
# session stack — same project + volumes, only AUTH_MODE flips. See DEP-04.
COMPOSE_DEV_AUTH := docker compose -f docker-compose.yml -f docker-compose.dev-auth.yml

.PHONY: help bootstrap update up up-dev-auth down restart logs ps migrate revision \
        accept accept-dev-auth \
        backend-install backend-dev backend-test backend-lint backend-format \
        openapi openapi-check \
        frontend-install frontend-dev frontend-build frontend-lint test smoke clean nuke

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

bootstrap: ## One-time local setup (env file, backend venv, frontend deps)
	@bash scripts/bootstrap.sh

update: ## Pull latest + update deps + migrate DB (Docker-free)
	@bash scripts/update.sh

up: ## Start the full stack — NORMAL session auth (real login). Build if needed.
	$(COMPOSE) up -d --build

up-dev-auth: ## Start the stack in dev-auth impersonation (X-Actor-Id, no login; local-only)
	$(COMPOSE_DEV_AUTH) up -d --build

down: ## Stop the stack (keep volumes)
	$(COMPOSE) down

restart: ## Restart the stack
	$(COMPOSE) down && $(COMPOSE) up -d --build

logs: ## Tail all service logs
	$(COMPOSE) logs -f --tail=100

ps: ## Show stack status
	$(COMPOSE) ps

migrate: ## Apply DB migrations to head (inside the stack)
	$(COMPOSE) run --rm migrate

revision: ## Create a new autogenerate migration: make revision m="message"
	cd backend && uv run alembic revision --autogenerate -m "$(m)"

backend-install: ## Install backend deps via uv
	cd backend && uv sync --all-extras

backend-dev: ## Run API locally with reload (needs infra: make up first)
	cd backend && uv run uvicorn entropia.apps.api.main:app --reload --port 8000

backend-test: ## Run backend test suite
	cd backend && uv run pytest

backend-lint: ## Ruff + mypy
	cd backend && uv run ruff check . && uv run mypy src

backend-format: ## Auto-format backend (ruff format)
	cd backend && uv run ruff format . && uv run ruff check --fix .

openapi: ## Regenerate the committed OpenAPI snapshot (docs/openapi.json)
	cd backend && uv run python -m entropia.apps.api.openapi_export

openapi-check: ## Fail if docs/openapi.json drifted from the app's schema
	cd backend && uv run python -m entropia.apps.api.openapi_export --check

frontend-install: ## Install frontend deps
	cd frontend && npm install

frontend-dev: ## Run the Vite dev server
	cd frontend && npm run dev

frontend-build: ## Production build of the frontend
	cd frontend && npm run build

frontend-lint: ## Lint + typecheck the frontend
	cd frontend && npm run lint && npm run typecheck

test: backend-test ## Run all tests — fails if EITHER backend or frontend suite fails (TEST-11)
	cd frontend && npm test --silent

smoke: ## Smoke-test a RUNNING stack (health, deps, metrics, identity, frontend)
	@bash scripts/smoke.sh

accept: ## Acceptance gate for a RUNNING stack: fail if any service exited/restarted/unhealthy (DEP-05)
	@bash scripts/acceptance.sh

accept-dev-auth: ## Acceptance gate against the dev-auth stack (DEP-05)
	@COMPOSE_DEV_AUTH=1 bash scripts/acceptance.sh

clean: ## Remove build artifacts and caches
	rm -rf backend/.pytest_cache backend/.ruff_cache backend/.mypy_cache frontend/dist frontend/.vite

nuke: ## Stop stack and DELETE all volumes (DESTRUCTIVE)
	$(COMPOSE) down -v

.PHONY: backup restore backup-verify

backup: ## Back up Postgres + object storage to ./backups/<timestamp>
	@bash scripts/backup.sh

restore: ## Restore Postgres + object storage from a backup dir (DESTRUCTIVE; make restore dir=./backups/<ts>)
	@bash scripts/restore.sh $(dir)

backup-verify: ## Verify the latest backup restores cleanly into a scratch DB
	@bash scripts/backup-verify.sh
