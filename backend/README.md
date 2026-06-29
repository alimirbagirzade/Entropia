# Entropia V18 — Backend

Modular monolith (one codebase) with separate worker planes, per the canonical
Master Technical Reference §20. Python 3.12 · FastAPI · PostgreSQL 16 ·
Redis 7 + Dramatiq · S3/MinIO · Polars/PyArrow.

## Layout

```
src/entropia/
  config/          env-driven Settings (pydantic-settings)
  shared/          error model, response envelopes, pagination, ids
  infrastructure/  postgres · redis · s3 · queues(dramatiq) · observability
  application/     commands · queries · jobs   (Stage 1+)
  domain/          identity · lifecycle · market_data · ...  (Stage 1+)
  apps/
    api/                 FastAPI app, routes, SSE, error handlers
    worker/              Dramatiq worker plane
    agent_coordinator/   continuous Alpha Agent loop
    scheduler/           maintenance / stale-job recovery
alembic/           async migrations (asyncpg)
tests/             unit · integration · contract · deterministic · acceptance
```

## Local development (without Docker)

```bash
uv sync --all-extras                 # create .venv and install deps
cp ../.env.example ../.env           # or export the variables
uv run alembic upgrade head          # needs a reachable Postgres
uv run uvicorn entropia.apps.api.main:app --reload --port 8000
```

Run a worker plane:

```bash
uv run python -m entropia.apps.worker --queues default,maintenance
uv run python -m entropia.apps.agent_coordinator
uv run python -m entropia.apps.scheduler
```

## Quality gates

```bash
uv run ruff check . && uv run ruff format --check .
uv run mypy src
uv run pytest               # unit + contract (no infra required)
```

> The full stack (Postgres/Redis/MinIO + all worker planes) is easiest via
> `docker compose up -d --build` from the repository root. See the root README.
