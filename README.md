# Entropia V18

A quantitative trading **strategy & backtest platform**: build strategies and
data packages, pin exact revisions, run deterministic backtests on a worker
plane, and let a continuously-running research Agent propose candidates — all on
an auditable, replayable, revision-controlled core.

This repository is built **stage by stage** from a canonical specification (see
[`docs/spec/`](docs/spec/)). The authoritative tech contract is the
[Master Technical Reference](docs/spec/Entropia_V18_Master_Technical_Reference_v1_0.md).

| Area | Stack |
| --- | --- |
| Backend | Python 3.12 · FastAPI · Pydantic v2 · SQLAlchemy 2 (async) · Alembic |
| Data | PostgreSQL 16 · Redis 7 + Dramatiq · MinIO / S3 · Polars · PyArrow · Parquet |
| Frontend | React 18 · TypeScript · Vite · TanStack Query · React Hook Form |
| Realtime | Server-Sent Events (SSE) |
| Runtime | Docker Compose — modular monolith with separate worker planes |

> **Build status:** **Stage 0 — Project skeleton** is complete (app shell,
> config, DB + migration infra, API + worker/agent/scheduler planes, frontend
> shell with all 22 screens, common error/loading/empty states, tests, CI).
> The staged roadmap lives in [`docs/STAGE_BUILD_PLAN.md`](docs/STAGE_BUILD_PLAN.md).

---

## Quick start — Docker (recommended, identical on macOS / Windows / Linux)

**Prerequisites:** [Docker Desktop](https://www.docker.com/products/docker-desktop/)
(includes Docker Compose v2).

### macOS / Linux

```bash
git clone https://github.com/alimirbagirzade/Entropia.git
cd Entropia
cp .env.example .env
docker compose up -d --build
```

### Windows (PowerShell)

```powershell
git clone https://github.com/alimirbagirzade/Entropia.git
cd Entropia
Copy-Item .env.example .env
docker compose up -d --build
```

Then open:

| URL | What |
| --- | --- |
| http://localhost:8080 | Web app (Mainboard shows live backend status) |
| http://localhost:8000/docs | API — interactive OpenAPI docs |
| http://localhost:8000/api/v1/health/ready | Dependency health (postgres/redis/object storage) |
| http://localhost:9001 | MinIO console (user/pass from `.env`) |

The stack runs migrations automatically (the `migrate` service), creates the
MinIO bucket, and starts the API plus every worker plane
(`worker-default`, `worker-data`, `worker-backtest`, `worker-agent`,
`agent-coordinator`, `scheduler`).

Stop it with `docker compose down` (add `-v` to also delete data volumes).

---

## Local development (without Docker)

You run the app processes natively and point them at infrastructure. The easiest
path is to run **only the infra** in Docker and the app code on your machine.

**Prerequisites**

| Tool | Version | Install |
| --- | --- | --- |
| Python | 3.12 | via [`uv`](https://docs.astral.sh/uv/) (recommended) |
| uv | latest | `curl -LsSf https://astral.sh/uv/install.sh \| sh` (macOS/Linux) · `irm https://astral.sh/uv/install.ps1 \| iex` (Windows) |
| Node.js | 20+ | https://nodejs.org |
| Docker | latest | for Postgres/Redis/MinIO |

### 1. One-time bootstrap

**macOS / Linux**

```bash
make bootstrap          # copies .env, runs `uv sync`, runs `npm install`
```

**Windows (PowerShell)**

```powershell
.\scripts\bootstrap.ps1
```

### 2. Start infrastructure (Postgres + Redis + MinIO)

```bash
docker compose up -d postgres redis minio minio-setup
```

### 3. Run the backend (API) and apply migrations

**macOS / Linux**

```bash
make migrate            # or: cd backend && uv run alembic upgrade head
make backend-dev        # uvicorn with reload on :8000
```

**Windows (PowerShell)**

```powershell
.\scripts\tasks.ps1 migrate
.\scripts\tasks.ps1 backend-dev
```

### 4. Run the frontend

**macOS / Linux**

```bash
make frontend-dev       # Vite dev server on :5173
```

**Windows (PowerShell)**

```powershell
.\scripts\tasks.ps1 frontend-dev
```

The dev frontend talks to `VITE_API_BASE_URL` (default `http://localhost:8000/api/v1`).

### 5. (Optional) Run worker planes natively

```bash
cd backend
uv run python -m entropia.apps.worker --queues default,maintenance
uv run python -m entropia.apps.worker --queues data
uv run python -m entropia.apps.worker --queues backtest
uv run python -m entropia.apps.agent_coordinator
uv run python -m entropia.apps.scheduler
```

---

## Common tasks

macOS/Linux use `make <target>`; Windows use `.\scripts\tasks.ps1 <task>`.

| Task | `make` | `tasks.ps1` |
| --- | --- | --- |
| Full stack up | `make up` | `.\scripts\tasks.ps1 up` |
| Stack down | `make down` | `.\scripts\tasks.ps1 down` |
| Tail logs | `make logs` | `.\scripts\tasks.ps1 logs` |
| DB migrate | `make migrate` | `.\scripts\tasks.ps1 migrate` |
| Backend tests | `make backend-test` | `.\scripts\tasks.ps1 backend-test` |
| Backend lint | `make backend-lint` | `.\scripts\tasks.ps1 backend-lint` |
| Frontend build | `make frontend-build` | `.\scripts\tasks.ps1 frontend-build` |
| Frontend lint | `make frontend-lint` | `.\scripts\tasks.ps1 frontend-lint` |
| Run `make help` for the full list. | | |

---

## Configuration

All configuration is environment-driven. Copy `.env.example` to `.env` and edit.
Secrets are never logged, never written to audit payloads, and never baked into
the frontend build. Each environment (`local`/`staging`/`production`) uses its
own database, bucket, and queue namespace. See
[`.env.example`](.env.example) for every variable and its default.

---

## Repository layout

```
Entropia/
├── backend/              FastAPI app + worker planes (Python, uv)
│   ├── src/entropia/      apps · application · domain · infrastructure · config · shared
│   ├── alembic/           async database migrations
│   └── tests/             unit · integration · contract · deterministic · acceptance
├── frontend/             React + TypeScript + Vite app shell
├── scripts/              cross-platform bootstrap / task runners (sh + ps1)
├── docs/
│   ├── ARCHITECTURE.md        system architecture (synthesized from the spec)
│   ├── DOMAIN_MODEL.md        canonical roots/revisions, roles, invariants
│   ├── STAGE_BUILD_PLAN.md    the Stage 0..8 roadmap
│   └── spec/                  source specification (canonical authority)
├── docker-compose.yml    full local/first-production stack
├── Makefile              macOS/Linux developer tasks
└── .github/workflows/    CI (lint, test, build)
```

---

## Architecture in one paragraph

The backend is a **modular monolith** (one codebase, domain-oriented modules)
with **separate worker processes** for long-running work. The API never runs
heavy work inline — it creates a durable **job** and returns immediately; workers
publish authoritative state in a transaction and emit an **SSE** refresh signal.
**PostgreSQL** is the source of truth for metadata, roots, revisions, audit, and
jobs; large/columnar artifacts live in **object storage** as immutable, content-
addressed Parquet. The **Agent** is a non-login system actor whose research loop
runs continuously in the backend, independent of any browser or UI session. Read
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the full model.

---

## License

Proprietary — see [LICENSE](LICENSE).
