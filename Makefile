# Entropia V18 — developer convenience targets (macOS / Linux).
# Windows users: use the mirror scripts in scripts/*.ps1 (see README).
.DEFAULT_GOAL := help
SHELL := /bin/bash

COMPOSE := docker compose

.PHONY: help bootstrap update up down restart logs ps migrate revision \
        backend-install backend-dev backend-test backend-lint backend-format \
        frontend-install frontend-dev frontend-build frontend-lint test clean nuke

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

bootstrap: ## One-time local setup (env file, backend venv, frontend deps)
	@bash scripts/bootstrap.sh

update: ## Pull latest + update deps + migrate DB (Docker-free)
	@bash scripts/update.sh

up: ## Start the full Docker stack (build if needed)
	$(COMPOSE) up -d --build

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

frontend-install: ## Install frontend deps
	cd frontend && npm install

frontend-dev: ## Run the Vite dev server
	cd frontend && npm run dev

frontend-build: ## Production build of the frontend
	cd frontend && npm run build

frontend-lint: ## Lint + typecheck the frontend
	cd frontend && npm run lint && npm run typecheck

test: backend-test ## Alias: run all tests
	cd frontend && npm test --silent || true

clean: ## Remove build artifacts and caches
	rm -rf backend/.pytest_cache backend/.ruff_cache backend/.mypy_cache frontend/dist frontend/.vite

nuke: ## Stop stack and DELETE all volumes (DESTRUCTIVE)
	$(COMPOSE) down -v
