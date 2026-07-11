# Entropia V18 — System Architecture

> **Status:** Canonical engineering reference for Production V1.
> **Authority:** This document is subordinate to `docs/spec/Entropia_V18_Master_Technical_Reference_v1_0.md` (Modules M0–M19) and the canonical integration decisions **CR-01..CR-09**. Where a page doc and the Master Reference disagree, the Master Reference wins. V18 prototype (HTML/client demo) is **never** authoritative for persistence, authorization, lifecycle, or API behavior.
> **Scope:** Process topology, code layering, data layer split, queue/job/worker model, backtest & agent planes, SSE/event model, API contract conventions, observability/audit, deployment.

---

## 1. Architectural Principles (non-negotiable)

| # | Principle | Consequence |
|---|-----------|-------------|
| P1 | **Server is the only source of truth.** | Client-sent `role`/`owner`/`isAdmin`/`ready`/`backtestReady`/DOM/localStorage are never authoritative. Every command re-derives principal, re-evaluates policy, re-validates state. |
| P2 | **Command/Query separation at the app boundary.** | UI button → API command → application service → domain → (Postgres tx + outbox + optional job). Agent tool → the *same* application command (capability parity, no browser emulation). |
| P3 | **Roots are immutable-by-revision.** | Every meaningful change `INSERT`s a new revision (never `UPDATE` payload), bumps `revision_no`, moves `current_revision_id`, writes audit. No `PATCH /entities/{id}` generic endpoint. |
| P4 | **Pin exact revisions, never "latest".** | Manifests/snapshots/bundles pin `root_id + revision_id + content_hash`. New revisions never auto-repin or mutate prior work. |
| P5 | **Long work is a durable job, never inline HTTP.** | Parse/analyze/validate/backtest/export/agent loops run on Dramatiq workers; command returns `202 + job/run id`; status via polling + SSE refresh signal. Browser close/logout never cancels a worker. |
| P6 | **Metadata in Postgres, bulk artifacts in object storage.** | Filterable/joinable fields are relational columns; raw files and Parquet processed assets live in MinIO/S3, referenced by `asset_id + digest`. Object path is not identity. |
| P7 | **Soft delete only; Trash & purge are Admin-only.** | Normal delete = soft delete (atomic: root state + trash entry + dependency snapshot + audit + outbox). Hard purge is a separate Admin async job with retention/dependency preflight. |
| P8 | **One transaction per mutation; outbox for fan-out.** | The domain mutation, fingerprint recompute, audit event, and outbox enqueue commit together or roll back together. Consumer (search index, projection, agent tool registry) failure never rolls back the root. |

---

## 2. Process Topology

Docker Compose **modular monolith**: one Python package (`entropia`), multiple process roles bound to the same domain/application code, separated by queue subscription and resource profile.

```
                         ┌──────────────────────────────────────────────┐
   React + Vite SPA ───▶ │  api  (FastAPI / uvicorn)                     │
   (TanStack Query,      │  - parse request, resolve ActorContext        │
    RHF, SSE client)     │  - call application command/query             │
                         │  - 1 tx: domain + audit + outbox              │
                         │  - enqueue job, return 202 + id               │
                         │  - SSE /events refresh signal                 │
                         └───────┬───────────────┬──────────────┬────────┘
                                 │ Postgres       │ Redis (queues)│ MinIO/S3
                                 ▼                ▼               ▼
   ┌───────────────────────────────────────────────────────────────────┐
   │ WORKER PLANES (Dramatiq, shared codebase, distinct queue + profile)│
   ├───────────────────────────────────────────────────────────────────┤
   │ worker-default   queue=default        generic domain jobs          │
   │ worker-data      queue=data           ingest/parse/validate parquet│
   │ worker-backtest  queue=backtest       manifest → engine → result   │
   │ worker-agent     queue=agent,agent-high  Alpha Agent tool execution│
   │ agent-coordinator (long-lived loop)   agent runtime / checkpoints  │
   │ scheduler        (cron / periodiq)    retention, outbox relay, GC   │
   └───────────────────────────────────────────────────────────────────┘
                                 ▲
                         outbox relay (scheduler) → SSE fan-out, search index,
                         projection rebuild, agent tool registry refresh
```

### 2.1 Process roles

| Process | Module entrypoint | Consumes | Responsibility |
|---------|-------------------|----------|----------------|
| **api** | `entropia.apps.api.main:create_app` (uvicorn) | — | HTTP/SSE surface. No SQL business logic, no path building, no inline long work. |
| **worker-default** | `python -m entropia.apps.worker --queues default` | `default` | Generic domain jobs (revision materialization side-effects, exports). |
| **worker-data** | `python -m entropia.apps.worker --queues data` | `data` | Market/Research ingestion: raw upload finalize, parse, schema-map, validate, Parquet write. Polars/PyArrow. |
| **worker-backtest** | `python -m entropia.apps.worker --queues backtest` | `backtest` | Backtest execution plane: read manifest → run engine → materialize immutable result + artifacts. Lower concurrency, higher memory. |
| **worker-agent** | `python -m entropia.apps.worker --queues agent,agent-high` | `agent`, `agent-high` | Executes Agent tool calls dispatched by the coordinator. `agent-high` carries High-priority directives but **never preempts** a running task. |
| **agent-coordinator** | `entropia.apps.agent_coordinator` | (long-lived) | Owns the always-on `agent_runtime` loop, task scheduling, checkpoint cadence, directive consumption at safe checkpoints. |
| **scheduler** | `entropia.apps.scheduler` | cron | Outbox relay, retention sweeps, purge-job eligibility, projection refresh, stale-lease reclamation. |

> The canonical Dramatiq queue set is fixed in `infrastructure/queues/broker.py`: **`default, data, backtest, agent, agent-high, maintenance`**. `maintenance` carries health/heartbeat and operational jobs.

### 2.2 Shared infrastructure services

| Service | Role | Notes |
|---------|------|-------|
| **PostgreSQL 16** | System of record: identity, roots, revisions, manifests, projections, audit, outbox, trash, tombstones. | SQLAlchemy 2.x async (`asyncpg`) for app; `psycopg2` sync URL derived for Alembic (`Settings.sync_database_url`). |
| **Redis 7** | Dramatiq transport + ephemeral cache + idempotency-key short-TTL guard. | Redis message is *only* transport; durable job truth lives in the Postgres job table. |
| **MinIO/S3** | Immutable raw assets + partitioned Parquet processed assets + result artifacts + exports. | Content-addressed; deleted only at purge after retention/pinning check. |

---

## 3. Code Layering (`backend/src/entropia/`)

Strict dependency direction: **apps → application → domain ← infrastructure**. Domain depends on nothing; infrastructure implements domain ports; application orchestrates; apps adapt transport.

```
entropia/
├── apps/                      # transport adapters (no business logic)
│   ├── api/                   # FastAPI: main, context, deps, errors, sse, routes/
│   ├── worker/                # Dramatiq worker entrypoint + actors
│   ├── agent_coordinator/     # always-on agent runtime loop
│   └── scheduler/             # cron: outbox relay, retention, purge eligibility
├── application/               # use-case orchestration
│   ├── commands/              # write use-cases (1 tx: domain + audit + outbox + enqueue)
│   ├── queries/               # read use-cases (role-aware projections)
│   └── jobs/                  # durable job bodies invoked by worker actors
├── domain/                    # pure model: entities, value objects, lifecycle enums,
│                              # invariants, policy rules, ports (no I/O imports)
├── infrastructure/            # adapters implementing domain ports
│   ├── postgres/              # engine, Base, repositories, health
│   ├── queues/                # Dramatiq broker wiring
│   ├── redis/                 # client + idempotency cache
│   ├── s3/                    # object-storage client (MinIO/S3)
│   └── observability/         # structlog configuration, logger factory
├── config/                    # Settings (pydantic-settings, env-driven)
└── shared/                    # cross-cutting primitives: ids, errors, responses, pagination
```

### 3.1 Layer contracts

| Layer | May import | Must not |
|-------|-----------|----------|
| **apps** | application, shared | domain internals directly for business decisions; infrastructure adapters except via DI in `deps.py` |
| **application** | domain, ports (infrastructure interfaces), shared | FastAPI, SQLAlchemy session details (only via repository ports), HTTP concepts |
| **domain** | shared (ids, errors, enums) | FastAPI, SQLAlchemy, Dramatiq, boto3 — **zero I/O** |
| **infrastructure** | domain ports, shared, config | application, apps |
| **shared** | stdlib, pydantic | any other internal layer |

### 3.2 Route handler contract (`apps/api/routes/*`)

A handler does exactly four things (already established in Stage 0 scaffolding):
1. Parse/validate the request body (Pydantic v2 model).
2. Resolve `ActorContext` via `deps.actor_context` — real identity + role per `AUTH_MODE` (`dev`: `X-Actor-Id` header; `session`: opaque Bearer session / service token), role always re-read from the database.
3. Invoke one application command or query.
4. Serialize the result into the canonical envelope; set `ETag` on single resources; return `202 + id` for jobs.

No SQL, no queue enqueue, no object-storage path building, no policy logic in the route.

---

## 4. Data Layer Split (Postgres metadata vs Object-Storage Parquet)

### 4.1 Hybrid persistence model (M2)

- **`entity_registry`** (shared identity table): `entity_id` (ULID-like prefixed id, never reused even post-purge), `entity_type`, `owner_principal_id`, `created_by_principal_id`, `visibility`, `lifecycle_state`, `deletion_state`, `current_revision_id`, `row_version`, timestamps.
- **Per-domain root + `*_revisions` tables** joined to the registry by FK. Revision: `revision_id`, `entity_id`, `revision_no`, `parent_revision_id`, `payload` (JSONB), `content_hash` (SHA-256 of canonicalized payload), `created_by_principal_id`, `created_at`, `validation_status`, `lifecycle_snapshot`.
- **Normalized reference rows** (dependency edges) even when payload is JSONB — required for dependency graph, usage queries, restore, reproducibility, cycle detection. **No EAV / generic JSON** for core domain.

> Human-readable refs (`STR-`, `PKG-`, `MKT-`, `RUN-`) are display-only; the API addresses everything by opaque `entity_id`.

### 4.2 What lives where

| Postgres (filterable / joinable / authoritative metadata) | Object storage (immutable bulk bytes) |
|---|---|
| principals, human_users, agents | raw uploaded source assets (`raw/.../`) |
| entity_registry, `*_revisions`, reference/relation tables | processed Parquet (partitioned, `processed/.../`) |
| run_manifests, result_manifest_snapshots, composition_snapshots | validation reports (`reports/.../`) |
| validation runs/issues, approval decisions, dataset coverage | run manifests pinned copy (`manifests/.../`) |
| backtest_runs, backtest_results, metric values, result summary | trade ledger / equity curve / signal events Parquet (`backtests/{run_id}/artifacts/...`) |
| agent_runtime, agent_task, task_directive, agent_checkpoint, hypothesis | generated `runtime.py`, candidate artifacts, exports |
| audit_events, trash_entries, outbox_events, tombstones | (purge-time deletion only) |

### 4.3 Object-storage path convention

```
s3://entropia/<class>/<domain>/{root_id}/r{revision_no}/<artifact>.<ext>
  class ∈ raw | processed | reports | manifests
  e.g. processed/market/{root}/r3/ohlcv.parquet
       backtests/{run_id}/artifacts/trade_ledger/{sha256}.parquet
```

- Object path is **not identity**: `asset_id + digest + manifest` is. `raw_file_hash` is tracked separately from `content_hash`.
- Workers read via **Polars + PyArrow**. TimescaleDB (if introduced) is a cache only — never replaces the revision manifest.
- Formats: Parquet/CSV/JSON-NDJSON (+GZIP/ZIP). XLSX not a base contract; formulas/macros never executed.
- Raw bytes are never overwritten; a new mapping/semantic produces a new revision, not a mutation.

### 4.4 Decimal & time discipline

- Money/percent stored as Postgres **NUMERIC / fixed-point**, transported as canonical dot-decimal strings. **No binary float** for financial values.
- Time fields kept separate and explicit: `event_time`, `published_at`, `available_at`, `decision_time`, `execution_time`. As-of/backward join requires `available_at <= decision_time AND event_at <= available_at`. Forbidden: nearest-future-row, event-time-only join, client-clock join, forward-fill unless a field definition allows it. Normalize to UTC, retain original timezone (IANA).

---

## 5. Queue / Job / Worker Model & Job State Machine

### 5.1 Command → Job handshake

1. API command authorizes, asserts idempotency key, opens one Postgres tx.
2. Tx writes the durable **job row** (`status=queued`, idempotency_key, correlation_id, input refs) + audit + **outbox enqueue**.
3. Tx commits. Outbox relay (or in-handler enqueue after commit) publishes the Dramatiq message to the canonical queue.
4. Worker actor claims the job (lease), transitions `running`, executes, writes terminal state + artifacts, emits domain/outbox events.
5. SSE relays the state change as a **refresh signal**; client refetches authoritative state.

> The Redis message is transport only. Retry policy, idempotency, correlation, and final state live in the Postgres job table (`infrastructure/queues/broker.py` docstring).

### 5.2 Canonical Generic Job State (CR-04, lowercase snake_case)

```
queued → claimed → running → ┬→ succeeded
                              ├→ failed_retryable → (re-queue) → claimed
                              ├→ failed_final
                              └→ cancellation_requested → cancelled
                  (also) → superseded  (a newer attempt obsoletes this one)
```

- States are domain values returned verbatim in payload/SSE. UI must not invent local aliases.
- Idempotency: same `actor + route + key + payload` returns the original job/result, no second effect; conflicting payload under the same key → `409 *_IDEMPOTENCY_CONFLICT`.
- Stale-lease reclamation: scheduler re-queues `claimed/running` jobs whose worker lease expired.

### 5.3 Distinct enums (never aliased)

`GenericJobState`, `BacktestRunState`, and `AgentTaskState` are **separate registries**. They are never collapsed into one column or aliased in the UI.

---

## 6. Backtest Execution Plane

### 6.1 Pipeline (M11–M13, CR-03/04/05/06/07)

```
Mainboard Composition Draft (mutable, row_version, current_fingerprint)
      │  Backtest Ready Check (server preflight)
      ▼
Composition Snapshot (immutable)  +  Readiness Report (immutable: state, fingerprints, policy_version)
      │  RUN admission (re-runs full preflight; expected_fingerprint must match)
      ▼
Backtest Run Manifest (immutable, manifest_hash = SHA-256(canonical_json(...)))
      │  enqueue queue=backtest (1 tx: snapshot + manifest + run + outbox)
      ▼
worker-backtest reads ONLY the manifest (never current board / latest package)
      │
      ▼
BacktestRun lifecycle  →  succeeded ⇒ materialize immutable BacktestResult + artifacts
                          failed/cancelled ⇒ diagnostics only, NO Result, NO history row
```

### 6.2 BacktestRun state machine (CR-04)

```
requested → preflight_running → {rejected | queued}
queued → provisioning → running → [cancellation_requested] → finalizing
finalizing → {succeeded | failed | cancelled}
```

- Terminal: `rejected | succeeded | failed | cancelled`.
- **Retry** = NEW `run_id` + new `manifest_hash` + `retry_of_run_id` link; the original is never mutated.
- **Result** (CR-03): `materializing → complete | integrity_failed`. There is **no** failed/cancelled Result state. `run_id` is UNIQUE on Result (one primary result per succeeded run, never overwritten).

### 6.3 Engine contract & reproducibility

- Worker reads only the manifest. Missing pinned asset ⇒ run **FAILED**, never a fallback to "latest"/current.
- Engine evaluation order is fixed by a **versioned Engine Contract** (CR-05): available-time context → fee/funding/carry → planned fills → stop/exit → conflict/exposure/allocation/risk → new entry → same-direction scaling → snapshot/diagnostics.
- Manifest persists (M0 §7.2): `run_id`, `strategy_version_id`, `package_version_ids[]`, `market_dataset_version_id`, `research_dataset_version_ids[]`, `research_available_time_policies[]`, `backtest_range`, `execution_model`, commission/spread/slippage config, `equity_allocation_mode` + `portfolio_allocation_plan_revision_id` (CR-06; **no** `allocation_profile*`), `run_profile_id`, `output_artifact_profile_id`, `metric_definition_set_version`, `result_view_metric_profile_id` (CR-07; presentation-only), `engine_contract_version`, timestamps, status.
- **RUN never triggers live trade or broker side effects.**

### 6.4 Result artifacts & presentation

- Artifacts (trade ledger, equity/drawdown curve, signal events, diagnostics) are immutable, checksummed Parquet in object storage; DB holds URI + checksum + schema_version + row_count.
- Results History and Arrange Metrics are **read/projection layers**: sort/filter on canonical numeric MetricDefinition values (never rounded card strings); nulls sort last (never coerced to 0). `Result View Metric Profile` selects a display subset — it never reduces the engine metric set or mutates stored values.

---

## 7. Agent Coordinator Plane (M14)

### 7.1 Always-on runtime (CR-09 boundary)

- The Alpha Agent runs **continuously backend-side**, independent of any UI. Browser close/logout never stops the loop.
- `agent-coordinator` owns `agent_runtime` (mutable pointers: status, active_task_id, last_checkpoint_id, policy_revision). `agent_task` is mutable only on status/stage/progress/lease/checkpoint-pointer.
- Checkpoints, manifests, evidence, directives are **immutable** after creation.

### 7.2 Directive & control model

| Action | Roles | Behavior |
|--------|-------|----------|
| Send Message / Send Directive (Normal\|High) | Supervisor, Admin | Directive is **queued**, consumed only at a safe checkpoint. High **never preempts** a running task. `autonomous` priority rejected for humans (`422 INVALID_DIRECTIVE_PRIORITY`). |
| Pause / Resume / Stop | Admin only | Checkpoint/cancellation-safe; never kills a worker mid-flight. |
| Agent tool calls | Agent (system actor) | Through the **Tool Gateway**: `data_bundle.resolve`, `package.proposal.create`, `backtest.request`, `artifact.create`, `documentation.search`, etc. Each call carries `task_id, checkpoint_id, input_manifest_id, actor, idempotency_key, policy_scope`. |

### 7.3 Agent capability parity & limits

- Agent uses the **same application commands/validators** as humans — no looser path, no UI automation, no browser dependency.
- Agent owns only its own outputs (`owner_principal=Agent`; the directive issuer is `initiated_by` provenance only).
- Agent can **never**: approve datasets, publish/approve packages, mutate the canonical ESP registry, access Trash, assign roles, or execute live trades. It may only create proposals/approval requests.
- Data bundles pin exact approved revisions for the task duration (no "latest" mid-run).

---

## 8. SSE / Event Model

### 8.1 Transactional Outbox is the spine

- Domain mutations write an `outbox_events` row in the same commit. The scheduler relay publishes to: SSE fan-out, search index, selector/cache projections, agent tool registry.
- Consumer failure retries independently and **never rolls back** the root state.
- Events are delivered at-least-once; clients de-dupe by `sequence_no` / `event_id`.

### 8.2 SSE semantics (refresh signal, not source of truth)

- Single endpoint `GET {base}/events` — heartbeat + live domain fan-out (the outbox relay publishes every domain family through `apps/api/sse.py`; loss-tolerant, INF-11).
- On reconnect, the client refetches authoritative state via query endpoints (`Last-Event-ID` + resource refresh). SSE payloads are **never** trusted as state.
- Event envelope: `event_id, event_type, resource{type,id,version}, correlation_id, occurred_at`.
- Canonical event families: `backtest_run.state_changed`, `backtest_result.created` (**no** `backtest_result.failed`), `job.updated`, `agent.task.*` (task_created/started/waiting, checkpoint_saved, directive_queued/consumed/deferred, tool_call_*, backtest_requested, result_linked, hypothesis_*), `resource.changed`, `audit.event.created`, `mainboard.composition_changed`, `ready_report.staled`.

---

## 9. API Contract Conventions

### 9.1 Surface & envelope

- Base path **`/api/v1`** (URL path versioning; `Settings.api_base_path`). JSON, ISO-8601 UTC, opaque ULID/UUID ids (never name-based addressing).
- Success collection: `{ "data": [...], "meta": { cursor, has_more, total } }` (`shared/responses.Page`).
- Success single: the resource object directly, with an `ETag` header.
- Long jobs: `202 Accepted` + `{ run_id|job_id, state, manifest_ref?, event_stream_ref? }`.

### 9.2 Error envelope (canonical)

```json
{ "error": { "code", "message", "details": [{ "field", "issue" }],
             "request_id", "correlation_id" } }
```

- Implemented in `apps/api/errors.py` + `shared/errors.AppError`. Stack traces / internal paths / secrets are never exposed; unexpected exceptions become a generic `500 INTERNAL_ERROR`.
- Status mapping: 400 (malformed) · 401 `UNAUTHENTICATED` · 403 `FORBIDDEN`/`ACCESS_DENIED`/`*_ADMIN_REQUIRED` · 404 `NOT_FOUND` (soft-deleted GET → 404) · 409 `CONFLICT`/`*_REVISION_CONFLICT`/`COMPOSITION_STALE`/`READY_REPORT_STALE` · 412 (If-Match precondition) · 422 `VALIDATION_ERROR`/`READINESS_BLOCKED` · 429 (rate limit) · 500/503.
- Richer per-issue form (M19): `issues[{severity, code, path, related_resource}], retryable`.

### 9.3 Concurrency — no last-write-wins

- Optimistic concurrency on every mutation:
  - Revision creates carry `expected_head_revision_id` (or `expected_revision_no`) → mismatch `409 HEAD_REVISION_CONFLICT` / domain-specific (`ROW_VERSION_CONFLICT`, `RATIONALE_FAMILY_CONFLICT`, `PACKAGE_REVISION_CONFLICT`, `USER_ROLE_VERSION_CONFLICT`).
  - Mutable drafts carry `expected_row_version`.
  - RUN carries `expected_fingerprint` → `409 COMPOSITION_STALE`.
- Transport: HTTP `If-Match` / `ETag` mirrors the domain token; ETag is transport, **not** domain identity.
- Identical-payload re-save (content_hash match) = idempotent no-op.

### 9.4 Idempotency

- All mutating commands (create/save/attach/run/import/delete/restore/purge) require an `Idempotency-Key`. Replay returns the canonical result; conflicting payload under the same key → `409 *_IDEMPOTENCY_CONFLICT`. Delete/restore/purge additionally lock the row `FOR UPDATE`; duplicate delete → `ENTITY_ALREADY_DELETED` no-op (no duplicate Trash entry/job).

### 9.5 Pagination

- Cursor-based (opaque forward cursor) for large/real-time datasets: `?cursor=&limit=` (`shared/pagination.PageParams`, default 20, max 100). Unbounded list responses are forbidden. List endpoints exclude unauthorized rows server-side (no client-side hiding). Log/history projections cursor on `(occurred_at DESC, event_id DESC)`.

### 9.6 Command-only mutation

- No generic `PATCH /entities/{id}`. Lifecycle transitions are typed commands (`submit_for_validation`, `approve`, `deprecate`, `soft_delete`, `restore`, `purge`), each running permission + domain validation + audit emission.

---

## 10. Authorization Model (server-side, every request)

Evaluation order (re-run on every command/query/tool call):

```
resolve principal (session/runtime; ignore client body role/owner/isAdmin)
  → classify operation (list|view|use|create|edit|soft_delete|restore|permanent_delete|assign_role|system_config|directive)
  → load target context (owner, visibility, lifecycle_state, deletion_state, pin/job state)
  → apply role + resource policy (incl. approval=Admin-only, publish=Admin-only,
                                  Trash=Admin-only, last-admin protection)
  → deny pre-mutation with structured error, else execute in one tx
```

- Principals: `anonymous`, `human`, `agent`, `system` (separate; Agent is a non-login, non-assignable system actor).
- Operations are distinct policy ops: **view ≠ use ≠ edit ≠ delete**. `use` grants reference rights only; the new output's owner is the caller.
- Global shared-edit exception: **Rationale Families + Package Rationale Assignment** (`can_manage_rationale_families` / `can_edit_rationale_assignments`) — resource-type scoped, does **not** widen any other edit right and does **not** extend to Trash restore/purge.
- Menu hide/disable is UX only, never authorization.

---

## 11. Observability & Audit

### 11.1 Logging

- Structured JSON via **structlog** (`infrastructure/observability`). `request_id` + `correlation_id` bound into contextvars by `RequestContextMiddleware`, echoed on every response header and error envelope, and propagated API → queue → worker → artifact (`causation_event_id` chains).
- No secrets/credentials/PII in logs.

### 11.2 Audit (append-only, survives delete & purge)

- Stored in `audit_events`: `event_id, occurred_at, command_name, actor_principal_id, actor_kind(human|agent|system_service), target_entity_id/type/revision, previous_state/new_state, correlation_id, causation_event_id, reason, source_task/run_id, payload_hash_before/after`. Never stores secrets/PII/large payloads (hashes + summaries only).
- Mandatory events include: `ROLE_CHANGED`, `RESOURCE_SOFT_DELETED/RESTORED/PERMANENTLY_DELETED`, `AGENT_DIRECTIVE_QUEUED`, `AGENT_RUN_CONTROL_REQUESTED`, `entity.delete.requested/completed/denied/blocked`, `trash.restore.*`, `trash.purge.*`, `backtest_run.*`, `backtest_result.created`, package/dataset/rationale domain events.
- Logs page (M19) is an append-only **projection** over audit/outbox; corrections add a new event via `causation_event_id` (never edit/delete).

### 11.3 Health & metrics

- `/health/live` (process up) and `/health/ready` (Postgres + Redis + object storage reachable; `503` if degraded) — already implemented.
- `GET {base}/metrics` — Prometheus text exposition: golden signals (latency histogram, traffic, errors, in-flight), jobs depth per queue, outbox lag, worker lease age. Rendered in-app on the Admin **System Metrics** screen; `scripts/smoke.sh` asserts the exposition outside-in.

---

## 12. Deployment & Environments

### 12.1 Compose topology

One image, role per service: `api`, `worker-default`, `worker-data`, `worker-backtest`, `worker-agent`, `agent-coordinator`, `scheduler`, plus `postgres:16`, `redis:7`, `minio`. Frontend (`web`) built with Vite, served statically / behind the API gateway.

### 12.2 Configuration (`config/settings.py`, env-driven)

- `ENTROPIA_ENV ∈ {local, staging, production}`; `DATABASE_URL` (async) with derived `sync_database_url` for Alembic; `REDIS_URL` + `QUEUE_NAMESPACE`; `OBJECT_STORAGE_*`; `WORKER_CONCURRENCY`, `BACKTEST_WORKER_CONCURRENCY`; `API_BASE_PATH`, `API_CORS_ORIGINS`; `AUTH_MODE ∈ {dev, session}` + `AUTH_SESSION_TTL_MINUTES` + `ENTROPIA_SERVICE_TOKEN` (non-human service line) + `ENTROPIA_BOOTSTRAP_ADMIN_EMAIL` (first-Admin bootstrap, empty = disabled); `RATE_LIMIT_*` (opt-in). Secrets from environment only — never logged, never in audit payloads, never in the frontend build.

### 12.3 Migrations

- **Alembic** forward-only in production; each migration reversible in lower envs; non-locking strategies for large tables (add column → backfill → constraint). One `DeclarativeBase` metadata (`infrastructure/postgres/base.Base`).

### 12.4 Canonical INF acceptance tests (Stage gate)

The infrastructure baseline is validated by the **INF acceptance suite** — these must pass before any product domain is built and remain green every stage:

| ID | Acceptance assertion |
|----|----------------------|
| **INF-01** | `create_app()` boots; `/api/v1/meta` returns name/version/environment; OpenAPI served at `/openapi.json`. |
| **INF-02** | `/api/v1/health/live` → 200; `/api/v1/health/ready` returns per-dependency checks and `503` when any of Postgres/Redis/object-storage is down. |
| **INF-03** | Every response carries `X-Request-Id` + `X-Correlation-Id`; an inbound id is honored, otherwise generated. |
| **INF-04** | Any raised `AppError` produces the canonical error envelope with `code/message/details/request_id/correlation_id`; an unexpected exception yields generic `500 INTERNAL_ERROR` with no stack trace. |
| **INF-05** | `RequestValidationError` → `422 VALIDATION_ERROR` with `details[].field/issue`. |
| **INF-06** | Queue round-trip: enqueuing `system_heartbeat` on `maintenance` is claimed and logged by a worker. |
| **INF-07** | Object-storage client connects to MinIO; `check_object_storage` reflects bucket reachability in `/health/ready`. |
| **INF-08** | SSE `GET /api/v1/events` opens, emits heartbeat, and terminates cleanly on client disconnect. |
| **INF-09** | Cursor pagination params clamp to `limit ≤ 100`; `Page` envelope shape is stable. |
| **INF-10** | Settings load from env; secrets never appear in logs; `sync_database_url` derives correctly for Alembic. |

> These tests are the canonical contract referenced by every later stage's "depends on the INF baseline" clause in `STAGE_BUILD_PLAN.md`.
