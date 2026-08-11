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
| `make backup-verify` | `scripts/backup-verify.sh` | Quick gate: prove the latest backup **loads** into a throwaway scratch DB. |
| `make dr-accept` | `scripts/dr-acceptance.sh` | Full gate: back up, restore into a scratch DB, and prove the **content** survived. |
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
make backup-verify   # quick: does the dump LOAD?
make dr-accept       # full: did the CONTENT survive?
```

`backup-verify` restores `postgres.dump` into a throwaway database
(`entropia_restore_check`), asserts `alembic_version` is present and the table
count matches the manifest, then drops the scratch DB. **An untested backup is
not a backup** — run it after every backup.

**Read its exit code, not just its colour.** Since ADIM 36 it reports three
distinct states. The third exists because the script used to blame the backup
for its own plumbing failing: a `dropdb` that failed was swallowed, the leftover
database made `createdb` fail, and a perfectly sound backup came back as `1`.

| Code | Means | A verdict about |
|---|---|---|
| `0` | the dump restores into a coherent database | the BACKUP |
| `1` | the dump does **not** restore | the BACKUP |
| `3` | it could **not be verified** — a postgres client tool is missing, or one of them did not answer inside its timeout | the ENVIRONMENT |

`3` is non-zero, so CI/cron still goes red: uncertainty fails. What it no longer
does is claim a sound backup is broken. The bounds are
`BACKUP_VERIFY_PG_TIMEOUT_SECONDS` (default 60 — `dropdb`/`createdb`/`psql`, all
sub-5s on a healthy host) and `BACKUP_VERIFY_RESTORE_TIMEOUT_SECONDS` (default
1800 — `pg_restore`, whose honest duration scales with the dump).

It is deliberately shallow, though: a dump that lost every row, every immutable
hash and every audit event still passes it. `make dr-accept`
(`scripts/dr-acceptance.sh`) closes that gap. It backs up, restores into its own
scratch database, and compares source vs restored on the Alembic head, the full
public table set, **every table's row count**, the immutable evidence columns
(revision content hashes, run/result manifest hashes and composition
fingerprints, export checksums, manual-revision checksums), the append-only
planes (`audit_events`, `outbox_events`, `agent_checkpoint`), and — when the
backup captured object storage — the path, size and **md5 of every object the
backup mirrored**. The source database is only ever read.

Both run in CI: `.github/workflows/install-acceptance.yml` job
**disaster-recovery**, nightly (03:17 UTC) and on manual dispatch, against a
stack seeded with the golden fixture so the hash comparisons have real content
to compare. It uploads the run transcripts and every `MANIFEST.json` as the
`dr-evidence` artifact — never the dump or the mirrored objects, which are data.
This closes audit finding **H-07** ("backup/restore is not verified in CI").

### How much a given run actually covers

"Every object the backup mirrored" is a claim about the **run**, not about the
product: steps [6]–[8] compare source to restored and cannot make the source
hold anything. A run against an empty stack compares `EMPTY` to `EMPTY` and
passes while proving nothing, so read the transcript, not just the exit code:

- step **[6]** prints each evidence table's fingerprint and warns when fewer
  than two carried rows;
- step **[7]** names, by table, the append-only planes that were empty on both
  sides;
- step **[8]** prints the object count **and the key prefixes** it covered.
  `infrastructure/s3/datasets.py` has four writers — `market/raw`,
  `market/processed`, `signals/source`, `create-package/baseline` — and a run
  that exercised only one of them says so.

The CI job sets `DR_MIN_EVIDENCE_TABLES`, `DR_REQUIRE_APPEND_ONLY`,
`DR_REQUIRE_OBJECTS` and `DR_MIN_OBJECTS` to what its fixture and workload
actually produce, so coverage that quietly shrinks fails the build instead of
printing a smaller number under a PASS line. `apps/seed.py` cannot satisfy the
append-only floor by itself — it writes through the repositories and so never
reaches `_audit_and_outbox` — which is why the job drives
`scripts/dr-workload.sh` (one authenticated `POST /trade-logs/source-assets`,
producing a `signals/source` object plus a real audit and outbox row) between
seeding and backing up.

**Still uncovered, deliberately:** `agent_checkpoint` (it needs an Agent tool
call) and the `market/raw` + `create-package/baseline` key prefixes. The
transcript names them on every run rather than leaving them to be inferred from
a PASS line.

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
