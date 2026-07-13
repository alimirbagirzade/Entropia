# Backup & Disaster Recovery (V1)

Entropia's V1 backup story is **operator-initiated and local**, covering the two
stores that hold authoritative state. It is delivered as three runnable scripts
plus this runbook — the same shape as the `make smoke` health check, not a new
subsystem. Production-grade DR is deferred to the technical-infra module (spec
Master Technical Reference, Module 20: "Log retention, cold storage … will be
finalised under the technical infrastructure module").

---

## Scope — what V1 backs up (and what it defers)

| Store | Volume / bucket | Backed up? | Why |
| --- | --- | --- | --- |
| **PostgreSQL 16** | `pgdata` | **Yes — required** | Authoritative metadata: every domain object, immutable revision, audit event, and outbox row. |
| **MinIO / S3** | `miniodata` · bucket `entropia-artifacts` | **Yes — optional** | Immutable artifacts: uploaded source assets, processed parquet, backtest/result artifacts. The DB stores each URI + checksum; the **bytes** live here. |
| **Redis 7** | `redisdata` | **No — by design** | Derivable queue + cache. In-flight work recovers from the durable Postgres **outbox** + INF-03 redelivery; the cache repopulates on demand. |

**Deferred to the infra module (out of scope for V1):** scheduled/cron backups,
off-site & cross-region replication, WAL archiving / point-in-time recovery
(PITR), encryption-at-rest of backup artifacts, and log cold-storage. V1 has no
fixed production deployment target, so these depend on decisions that module
makes.

---

## Objectives (local / first-production stack)

- **RPO** (max data loss): the time since the last `make backup`. Backups are
  operator-initiated — pick a cadence that matches your risk tolerance. There is
  no continuous WAL streaming in V1.
- **RTO** (time to recover): one `make restore` run — seconds to a few minutes
  for the metadata database at V1 data volumes, plus artifact mirror time.

---

## Toolchain

| Command | Script | What it does |
| --- | --- | --- |
| `make backup` | `scripts/backup.sh` | Snapshot Postgres (+ MinIO if reachable) into `./backups/<UTC-stamp>/`. |
| `make backup-verify` | `scripts/backup-verify.sh` | Prove the latest backup restores into a throwaway scratch DB. |
| `make restore` | `scripts/restore.sh` | Recover Postgres (+ MinIO) from a backup dir. **Destructive**, guarded. |

Windows users run the scripts under Git Bash / WSL (see [Windows](#windows)).

---

## What a backup contains

```
backups/<UTC-stamp>/           e.g. 20260713T133531Z/
  postgres.dump                pg_dump custom format (-Fc); selective pg_restore
  minio/                       mirror of the artifact bucket (only if MinIO was reachable)
  MANIFEST.json                provenance for verification
```

`MANIFEST.json` fields: `created_at_utc`, `git_commit`, `database`,
`alembic_head`, `public_table_count`, `postgres_dump_bytes`,
`object_storage_included`, `object_bucket`.

---

## Running a backup

```bash
make backup
# or, custom destination + retention:
BACKUP_DIR=/mnt/ext BACKUP_RETENTION=14 ./scripts/backup.sh
```

- Connection settings are read from `.env` (`POSTGRES_*` / `OBJECT_STORAGE_*`),
  accessed host-facing via `localhost` and the published ports. Override with
  `BACKUP_PGHOST` / `BACKUP_PGPORT` / `BACKUP_OBJECT_ENDPOINT`.
- **Postgres is required** — a failed dump aborts with exit 1 and removes the
  partial directory.
- **Object storage is optional** — mirrored when MinIO is reachable and `mc` or
  `docker` is available; otherwise WARN-skipped (the Postgres dump is still
  captured). This mirrors how `make smoke` treats object storage in the minimal
  Docker-free setup.
- **Retention**: the newest `BACKUP_RETENTION` timestamped directories are kept
  (default `7`); older ones are pruned automatically.

---

## Verifying a backup (do this routinely)

```bash
make backup-verify
```

Restores `postgres.dump` into a throwaway database (`entropia_restore_check`),
asserts `alembic_version` is present and the table count matches the manifest,
then drops the scratch DB. **An untested backup is not a backup** — run this
after every backup, and wire it into CI/cron to catch silent corruption early.

---

## Restoring

> **Destructive.** The Postgres restore DROPs and recreates every object in the
> target database. The command is guarded — pass `--yes` or type the
> confirmation phrase.

```bash
make restore                                    # latest backup -> live DB (prompts)
./scripts/restore.sh ./backups/<stamp> --yes    # a specific backup, no prompt
RESTORE_DB=entropia_scratch ./scripts/restore.sh <dir> --yes   # rehearse into a scratch DB
```

The object-storage restore is **additive**: it overwrites keys present in the
backup but never deletes keys created after the backup was taken.

---

## Disaster scenarios

| Scenario | Recovery |
| --- | --- |
| `pgdata` volume lost or corrupted | `make restore` from the latest **verified** backup. Data loss = time since that backup (RPO). |
| Object store lost, database intact | Restore from a backup whose `minio/` is present; the DB's URIs + checksums already point at the recovered keys. |
| Whole host lost | Provision a fresh stack (`make up` → `make migrate`), then `make restore`. |
| Bad migration / late-detected corruption | Restore into a scratch DB (`RESTORE_DB=…`), inspect, then cut over. |
| Redis lost | Nothing to restore — restart the workers; the outbox relay + INF-03 redelivery re-drive pending work. |

---

## Windows

The `make` targets are macOS/Linux. On Windows, run the scripts under Git Bash
or WSL, or issue the raw client commands:

```bash
pg_dump  -h localhost -U entropia -Fc -f postgres.dump entropia
pg_restore -h localhost -U entropia -d entropia --clean --if-exists postgres.dump
```

---

## Security

Backup artifacts contain real data and **must be treated as sensitive**.
`./backups/` is git-ignored — never commit a dump. Store off-box copies on
encrypted media; backup encryption-at-rest and off-site rotation are infra-module
concerns (see Scope above).
