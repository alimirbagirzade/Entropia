# Runbook — Backup, verify, restore

**No alert fires on backups. Read that sentence twice.**

Backups are **operator-initiated**. No cron job, no systemd unit and no compose
service invokes `scripts/backup.sh` — only `make backup` and the CI
install-acceptance workflow. Backup age and verify status are not recorded in any
machine-readable place, so **a backup that silently stops being taken raises
nothing, forever.**

Until that changes (see "Closing the gap" below), backup freshness is a **human
calendar item**, not a monitored property.

---

## Taking a backup

```bash
make backup
```

Writes `./backups/<UTC-timestamp>/` containing the Postgres dump, optionally the
object-storage contents, and a `MANIFEST.json`:

| Field | Use during recovery |
|---|---|
| `created_at_utc` | The only record of backup age — the directory name |
| `git_commit` | Which code the schema belongs to |
| `alembic_head` | **Must match the target's head, or restore first and migrate after** |
| `database` | Source database name |
| `public_table_count` | Verified on restore |
| `postgres_dump_bytes` | Truncation check |
| `object_storage_included` / `object_bucket` | Whether artifacts are in this backup at all |

Check age by hand:

```bash
ls -1 backups/ | sort | tail -3
```

---

## Verifying a backup

```bash
make backup-verify
```

Restores the latest backup into a scratch database and checks `alembic_head` and
`public_table_count` back out of the manifest.

**The result is human-readable only:** it prints `VERIFY OK — …` and exits 0, or
prints an error and exits 1. It writes **no status file** — its only artifact,
`.verify.err`, is deleted on success. If you want a record that verification
happened, capture it yourself:

```bash
make backup-verify 2>&1 | tee "backups/$(ls -1 backups/ | sort | tail -1)/verify.log"; echo "exit=$?"
```

For the deeper check — restore into a scratch DB, then compare row counts,
immutable hashes and object checksums:

```bash
make dr-accept
```

This is the only place object checksums are ever verified. Nothing verifies them
continuously.

---

## Restoring

**`make restore` is destructive.** It replaces the target database.

```bash
make restore dir=./backups/<timestamp>
```

Order of operations:

1. **Stop the writers first** — `api`, every `worker-*`, `scheduler`,
   `agent-coordinator`. Restoring under live writes produces a database that
   matches neither the backup nor the prior state.
2. Restore.
3. Compare the manifest's `alembic_head` with the code you are about to run. If
   the code is newer, `make migrate` **after** the restore, never before.
4. Start `api` last, after the workers, so no request is served by a stack whose
   async plane has not proven itself.
5. Verify: `make smoke`, then confirm
   `entropia_worker_heartbeat_age_seconds` appears and is fresh
   ([worker-down.md](worker-down.md)).

### Artifacts

If `object_storage_included` is `false`, the restored database references objects
that the restore did **not** bring back. Results will resolve rows and fail on
artifact read. Confirm before declaring recovery complete —
[object-storage.md](object-storage.md).

---

## What must never be done

* **Do not repair a restored row to make a Result appear.** A Result exists only
  because a Run `succeeded`; manifests pin exact revisions and are never
  re-derived from live state. A hand-made Result is permanent fiction.
* **Do not restore over a running stack** to "save time".

---

## Closing the gap

Making backup age alertable needs, in order: a machine-readable status written by
`backup-verify.sh`, a scrape path for it, then a rule. Until all three exist,
**do not add an alert** — the contract test rejects rules over metrics that are
not emitted, and that rejection is the point.

---

## What this cannot tell you

* Whether a backup was taken at all today.
* Whether the last verification passed.
* Whether stored objects still match the rows that reference them, outside a
  `make dr-accept` run.
