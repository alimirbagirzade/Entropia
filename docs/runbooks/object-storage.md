# Runbook — Object storage (MinIO / S3)

**No alert fires on object storage.** There is no availability, read/write or
checksum metric (matrix §4). You arrive here from `EntropiaApiServerErrors`
concentrated on artifact or export routes, or from a failing `/health/ready`.

Artifacts — backtest outputs, uploads, exports — live here. When it degrades the
rest of the product keeps working, so the symptom is narrow 5xx rather than an
outage.

---

## First 60 seconds

```bash
curl -sS http://<host>:8000/api/v1/health/ready | jq '.checks.object_storage'
docker compose ps minio
docker compose logs --tail=200 --no-color minio
```

In the API log look for `object_storage.probe_failed`. Like the other probes it
carries `error_type` only — deliberately, so credentials in a driver message
never reach the log.

---

## Discriminate

| Symptom | Cause | Action |
|---|---|---|
| Container exited | Service down | Restart, then re-run `make smoke` |
| Up, probe fails | Credentials or bucket missing | Check `OBJECT_STORAGE_*`; the bucket is created by the `minio-setup` service |
| Reads ok, writes fail | Disk full or quota | Free space on the `miniodata` volume |
| Intermittent 5xx on artifact routes | Endpoint/SSL mismatch | Verify `OBJECT_STORAGE_ENDPOINT` and `OBJECT_STORAGE_USE_SSL` |

---

## Confirm read/write yourself

The probe is a boolean; it does not prove a write succeeds. Test the actual path:

```bash
docker compose exec minio mc alias set local \
  http://localhost:9000 "$OBJECT_STORAGE_ACCESS_KEY" "$OBJECT_STORAGE_SECRET_KEY"
docker compose exec minio mc ls local/"$OBJECT_STORAGE_BUCKET"
```

---

## Consequences while it is down

* **New backtest runs fail at artifact write.** The run does not become a Result —
  which is correct: only a `SUCCEEDED` run yields an immutable Result. Do not
  attempt to publish a Result for a run whose artifacts never landed.
* **Existing Results stay readable** only if their artifacts are already stored;
  pinned manifests reference exact objects and are never re-derived from live
  state.
* **Uploads fail** at the source-file gate or immediately after.

---

## Recovery

`/health/ready` shows `object_storage: ok`, and an artifact read on an existing
Result returns 200. Re-run any failed runs from the UI — do **not** hand-repair
their rows.

---

## What this cannot tell you

* **Checksum integrity.** Verified only during
  `make dr-accept` / `scripts/backup-verify.sh`, never continuously.
* **Per-object failures.** No metric distinguishes a single bad object from a
  service outage.
* **Silent data loss.** Nothing continuously reconciles stored objects against
  the rows that reference them.
