# Runbook — Schema migrations

**No alert fires on migrations.** A failed migration surfaces as the API failing
to start (`EntropiaApiDown`) or as 5xx from routes touching the changed tables.

Current head: **`0043_i08_registry_strategy_fks`** (43 revisions in
`backend/alembic/versions/`). Verify rather than trusting this line — it ages:

```bash
cd backend && uv run alembic heads
```

**Exactly one head must be reported.** Two heads is a merge accident and must be
resolved before deploying.

---

## Applying

```bash
make migrate          # inside the running stack
```

The compose stack has a dedicated `migrate` service that runs before `api` and
the workers (`depends_on`), so a normal `make up` applies migrations in the right
order without manual steps.

---

## Before merging a migration

The acceptance gate covers single-head, empty->head, LEGACY->head, down/up and
provisioning idempotency against a scratch database, with no Docker:

```bash
make migration-accept
```

Locally, the project's own standard for a new revision `<n>` is an
**up / down / up** proof against a clean schema:

```bash
LC_ALL=en_US.UTF-8 psql "$DATABASE_URL" -c 'DROP SCHEMA public CASCADE; CREATE SCHEMA public;'
cd backend
uv run alembic upgrade head
uv run alembic downgrade -1
uv run alembic upgrade head
```

Then confirm **migration <-> model column parity** — a migration that adds a
column the model does not declare (or vice versa) passes Alembic and fails at
runtime.

---

## When a migration fails mid-flight

1. **Do not retry blindly.** Establish where it stopped:

   ```bash
   cd backend && uv run alembic current
   ```

2. Compare against `heads`. If `current` is behind, the transaction rolled back
   and the database is at the previous revision — safe to fix forward.
3. If the migration was **not** fully transactional (index creation, data
   backfill), the database may be in an intermediate state. Restore from backup
   rather than hand-patching: [backup-restore.md](backup-restore.md).
4. Keep the writers stopped until `current` matches `heads`. An API serving
   requests against a half-migrated schema produces 5xx that look like an
   application bug.

---

## Rolling back

```bash
cd backend && uv run alembic downgrade -1
```

**A downgrade is only safe if it is data-preserving.** A revision that dropped a
column cannot restore its contents. If the forward migration was destructive,
roll back by **restoring the backup**, not by downgrading.

---

## After any migration

```bash
make smoke
curl -sS http://<host>:8000/api/v1/health/ready | jq
```

Then confirm the async plane came back: `entropia_worker_heartbeat_age_seconds`
fresh, and every queue draining ([worker-down.md](worker-down.md)).

If the migration changed a public API surface, the OpenAPI snapshot must match:

```bash
make openapi-check
```

---

## What this cannot tell you

* **Migration duration.** Not measured. A long-running migration is
  indistinguishable from a hung one except by watching `pg_stat_activity`.
* **Lock waits.** A migration blocked behind a lock reports nothing:

  ```sql
  SELECT pid, wait_event_type, wait_event, left(query, 100)
    FROM pg_stat_activity WHERE wait_event_type = 'Lock';
  ```

* **Whether the schema matches the models.** Only the parity check above answers
  that, and it is a pre-merge step, not a runtime signal.
