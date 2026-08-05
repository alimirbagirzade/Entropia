# Install / upgrade / restore acceptance (ADIM 22)

This is the acceptance chain for the **installation**, not for the code and not
for the browser. It answers one question: *if an operator installs Entropia on
an empty machine, upgrades an older database, or has to restore from a backup —
does that actually work, and does CI notice when it stops working?*

Before this slice, the answer to the last clause was **no**. The harnesses
existed (`scripts/e2e-acceptance.sh`, `scripts/backup.sh`, `scripts/restore.sh`,
`scripts/backup-verify.sh`) but **no CI job ever ran any of them**, and three
mandated properties had no automated proof anywhere:

The **✔** rows were executed locally against a real PostgreSQL/MinIO while this
slice was written. The **▶** rows are gated by Compose jobs that could not run
locally — a parallel worktree session held ports 5432/8000/8080/9000 throughout —
so they get their first real execution in CI on this PR. That distinction is
part of the record, not a footnote.

| Property | Before | Now |
| --- | --- | --- |
| A **legacy** database upgrades to head with its rows intact | manual only | ✔ `migration-acceptance.sh` [5] · every PR |
| The head revision **down/up** round-trips | prose ritual in `CONTRIBUTING.md` | ✔ `migration-acceptance.sh` [6] · every PR |
| The revision graph has **one head** | manual `alembic heads` | ✔ `migration-acceptance.sh` [1] · every PR |
| Migration ↔ **model column parity** | docstring claims | ✔ `migration-acceptance.sh` [3] · every PR |
| Provisioning is **concurrent**-idempotent | not tested — **and it was broken** | ✔ `migration-acceptance.sh` [8] + `test_provision_concurrency.py` |
| A backup **preserves rows and hashes** | only "does the dump load?" | ✔ `dr-acceptance.sh` [5]–[8] · nightly |
| The acceptance gate **fails** when a plane dies | never observed failing | ▶ `install-acceptance.yml` negative step |
| Empty volumes → first Admin, and **only** the first | never asserted end to end | ▶ `install-acceptance.yml` **fresh-install** |

---

## The chain, and where each link is proven

| # | Link | Proven by | Cadence |
| --- | --- | --- | --- |
| 1 | Empty volumes → `migrate` → `provision` → bucket → first Admin → every plane healthy | `install-acceptance.yml` job **fresh-install** | every PR |
| 2 | Fresh **dev-auth** is local-only; production is fail-safe | `scripts/e2e-acceptance.sh dev-auth`; `tests/unit/test_settings.py` + `tests/integration/test_auth.py` (F-22) | manual / every PR |
| 3 | Representative **legacy revisions → head**, data preserved, single head | `scripts/migration-acceptance.sh` [1][5] | every PR |
| 4 | `agent_alpha` **principal** ≠ `alpha-agent` **runtime**; no duplicate provisioning | `migration-acceptance.sh` [4] + `tests/integration/test_provision_concurrency.py` | every PR |
| 5 | Provisioning **repeat + concurrent** idempotency; existing state never reset | `migration-acceptance.sh` [7][8] + `test_provision_concurrency.py` | every PR |
| 6 | Backup a seeded stack → **scratch restore** → head, tables, counts, revision/manifest/result hashes, object checksums, checkpoints, audit/outbox | `scripts/dr-acceptance.sh` | nightly + manual |
| 7 | Latest migration **up/down/up**, data-preserving | `migration-acceptance.sh` [6] | every PR |
| 8 | An unhealthy / stopped / restarted service makes `make accept` **fail** | `install-acceptance.yml` negative step | every PR |
| 9 | Fast fresh smoke on PRs; heavy legacy + restore nightly/manual | `install-acceptance.yml` job split | — |

---

## Running it locally

```bash
make migration-accept   # ~30s, needs only a reachable PostgreSQL — no Docker
make dr-accept          # back up the live DB, restore to scratch, verify deeply
make e2e-legacy         # the heavy Docker legacy-upgrade flow (isolated project)
make accept             # the state gate against a stack you already brought up
```

Both work inside **scratch** targets, each guarded by name against the live one
and torn down on exit (`KEEP_SCRATCH=1` / `DR_KEEP_SCRATCH=1` to keep them for
inspection). The complete write set is:

| Command | Writes | Reads only |
| --- | --- | --- |
| `make migration-accept` | scratch DB (`entropia_migration_acceptance`) + a `…_model` parity DB | — |
| `make dr-accept` | scratch DB, scratch **bucket** (`entropia-dr-acceptance`), and `./backups/dr-acceptance/` | the live database **and** the live bucket |

The scratch bucket is not decoration. `scripts/restore.sh`'s `RESTORE_DB` scopes
only its Postgres half; its object half resolves the bucket from the environment
and mirrors into it, so restoring with the live bucket in scope would silently
revert every artifact key written since the backup. `dr-accept` therefore
overrides `OBJECT_STORAGE_BUCKET` as well — and that is also what makes the
object comparison meaningful rather than circular: it checks the backup against
what the **restore** wrote, not against the bucket the backup was read from.
`./backups/dr-acceptance/` is likewise separate because `backup.sh` prunes to
`BACKUP_RETENTION` inside whatever directory it is given.

```bash
MIGRATION_ACCEPTANCE_DB=my_scratch make migration-accept
MIGRATION_ACCEPTANCE_LEGACY_REV=0020_future_dev make migration-accept
DR_SCRATCH_DB=my_dr_scratch DR_SCRATCH_BUCKET=my-dr-bucket ./scripts/dr-acceptance.sh ./backups/<stamp>
DR_REQUIRE_OBJECTS=1 make dr-accept    # turn "no objects captured" from WARN into FAIL
```

---

## What `migration-acceptance.sh` asserts

Against a real PostgreSQL, through the **real install path** (`alembic upgrade`)
— never `metadata.create_all`, which is a *test* convenience and skips every row
a migration inserts:

1. **one head** — a branched graph makes `upgrade head` ambiguous;
2. **empty → head** — the fresh install itself, stamped at the expected revision;
3. **column parity** — the migrated schema and `Base.metadata` agree on every
   column name, type, nullability and length; the script prints the count it
   compared rather than asserting a frozen number, so adding a column is not a
   documentation change;
4. **migration-provisioned rows** — exactly one `agent_runtime` row, `alpha-agent`,
   from `0016_analysis_lab`;
5. **legacy → head** — `0001_initial` (the full 42-step climb) and
   `0030_precheck_source_warnings` (identity + domain + audit rows), each with a
   value fingerprint that must survive the upgrade unchanged;
6. **head down/up/up** — measured against those same real rows, not an empty schema;
7. **repeat idempotency** — two provisioning runs, identical state;
8. **concurrent idempotency** — three parallel provisioning runs, all exit 0, and
   the result equals the sequential one.

## What `dr-acceptance.sh` adds over `backup-verify.sh`

`backup-verify.sh` asks *"does the dump load?"* — `alembic_version` present and
the table count matching the manifest. A dump that lost every row, every
immutable hash and every audit event still passes it. `dr-acceptance.sh` restores
into a scratch database and then compares source vs restored on:

- the Alembic head and the full public **table set**;
- **every table's row count** — all tables, not a sample;
- **immutable evidence**, byte for byte: `entity_revisions.content_hash`,
  `backtest_run_manifest` / `backtest_result` manifest hashes + composition
  fingerprints, market/research/package/rationale/strategy revision hashes,
  `export_artifact.checksum`, `manual_document_revisions.content_checksum`;
- the **append-only planes**: `audit_events`, `outbox_events`, `agent_checkpoint`;
- **object storage**, per object: path, size and md5 between the backup mirror
  and the live bucket.

---

## The defect this slice found and fixed

Provisioning was **not** concurrent-safe. Every guard in `apps/seed.py` is
SELECT-then-INSERT and the seed commits once at the end, so under READ COMMITTED
a second run cannot see the first one's uncommitted rows: both pass their "does
it already exist?" check, and the loser dies on `principals_pkey`, rolling back
its whole transaction. Reproduced on a fresh, migrated database — 2 of 3 parallel
runs exited 1.

That is not cosmetic. The compose `provision` one-shot is a
`service_completed_successfully` gate for **every** plane
(`docker-compose.yml` `x-needs-provision`), so a single racing exit-1 stops the
API, all worker planes, the coordinator and the scheduler from starting.

The loud crash is only the visible half. The guards with **no unique constraint**
behind them commit silent duplicates instead of failing —
`rationale_family_revision.normalized_name` is `index=True` only, so two runs can
both pass "does this family exist?" and both COMMIT. Measured, not assumed: with
the lock removed, three concurrent runs produce **18** rationale families where
six are canonical, and nothing anywhere reports an error.
`test_concurrency_does_not_duplicate_an_unguarded_seed_block` pins that number.

The fix is `seed.lock_provisioning` — a transaction-scoped
`pg_advisory_xact_lock`, the idiom already used by
`repositories/identity.py::lock_admin_count` and
`repositories/manual.py::lock_stream`. It is taken before the first guard reads
anything and released by PostgreSQL on commit **or** rollback, so a crashed run
cannot leave the next one blocked.

The wait is **bounded** (`PROVISION_LOCK_TIMEOUT_MS`, default 120s, enforced with
`SET LOCAL lock_timeout` — verified to apply to `pg_advisory_xact_lock` on
PostgreSQL 16). An unbounded wait would have been a worse bug than the one it
replaced: a run blocked behind a stale idle-in-transaction backend would hang the
whole stack with no error at all, which is harder to diagnose than an exit code.

---

## Honest boundaries

- **Index names are not gated.** `alembic check` reports differences between the
  migrations and `Base.metadata` — all of them index-*name* divergences (a
  migration-named `ix_result_manifest_snapshot_hash` vs the model's
  autogenerated `ix_result_manifest_snapshot_manifest_hash`) plus one server
  default. Column parity — the axis `CONTRIBUTING.md` actually names — is clean
  and **is** gated. Turning `alembic check` into a gate is a separate, larger
  cleanup; it is not silently ignored here, it is deliberately out of scope.
- **The integration suite still builds its schema with `metadata.create_all`**
  (`tests/integration/conftest.py`). That is a test-speed decision, not the
  install path, and it means migration-inserted rows (the `alpha-agent`
  `agent_runtime` singleton, `0019`/`0020` fixtures) do **not** exist in pytest.
  Anything that depends on them must be asserted against a migrated database —
  which is what `migration-acceptance.sh` is for.
- **`dr-acceptance.sh` warns when it proved little, and CI gates on how much it
  proved.** An `EMPTY == EMPTY` comparison is a true statement about nothing, so
  step [6] warns when fewer than two evidence tables carried rows and step [7]
  warns when all three append-only planes were empty. But a warning nobody can
  configure into a failure fires forever and gets read as normal, so the nightly
  job also sets coverage **floors** — `DR_MIN_EVIDENCE_TABLES`,
  `DR_REQUIRE_APPEND_ONLY`, `DR_MIN_OBJECTS` — at what its fixture and workload
  actually produce. They are off by default: a developer verifying one backup by
  hand should not have to satisfy CI's fixture coverage.
- **The seed alone cannot cover the append-only planes.** `apps/seed.py` writes
  through the repositories, so it never reaches `_audit_and_outbox`: it produces
  zero `audit_events` and zero `outbox_events`, and it calls exactly one of the
  four object writers. Measured, not assumed — Actions run 31038908690 printed
  "[7] all three append-only planes were EMPTY" and "[8] 1 objects". The nightly
  job therefore drives `scripts/dr-workload.sh` (one authenticated
  `POST /trade-logs/source-assets`) between seeding and backing up. Still
  uncovered on purpose: `agent_checkpoint`, and the `market/raw` and
  `create-package/baseline` key prefixes — step [8] names the prefixes it did
  cover on every run, so that gap stays in the transcript instead of being
  inferred from a PASS line.
- **Object *bytes* are only covered when MinIO is reachable.** With no object
  store, `backup.sh` WARN-skips the mirror and step [8] warns rather than
  passes. `DR_REQUIRE_OBJECTS=1` (which CI sets) turns that warning into a
  failure, so object-storage backup cannot silently stop working under a job
  that stays green.
- **PITR, off-site replication and scheduled backups remain out of V1 scope**
  (`docs/BACKUP_DR.md` "Scope"). This slice proves the operator-initiated chain
  that V1 actually ships; it does not invent the deferred infra module.
- **The Docker jobs in `install-acceptance.yml` were not run locally.** A
  parallel worktree session held the default ports during this slice, so bringing
  up a second stack would have collided with it. The shell harnesses
  (`migration-acceptance.sh`, `dr-acceptance.sh`) were run locally and are green;
  the compose jobs get their first real execution in CI on this PR.
