# Runbook — Redis (broker)

**No alert fires on Redis directly.** There is no Redis metric. You arrive here
from `EntropiaWorkerHeartbeatStale`, `EntropiaQueueNeverDrains`, or a failing
`/health/ready`.

Redis is the Dramatiq broker. When it degrades, the API keeps serving reads and
the UI looks healthy while **every asynchronous job silently stops progressing**.
That asymmetry is why this page exists.

---

## First 60 seconds

```bash
curl -sS http://<host>:8000/api/v1/health/ready | jq '.checks.redis'
docker compose exec redis redis-cli ping
docker compose exec redis redis-cli info memory | grep -E 'used_memory_human|maxmemory'
```

---

## Discriminate

| Symptom | Cause | Action |
|---|---|---|
| `PING` fails | Redis down | Restart; then verify the queue round-trip below |
| `PING` ok, heartbeat stale | Worker not consuming | [worker-down.md](worker-down.md) |
| `evicted_keys` climbing | **Eviction is discarding queued messages** | See below |
| `PING` ok, one queue stuck | Missing consumer for that queue | [stale-jobs.md](stale-jobs.md) |

### Eviction is the dangerous one

```bash
docker compose exec redis redis-cli info stats | grep evicted_keys
docker compose exec redis redis-cli config get maxmemory-policy
```

A broker configured with an `allkeys-*` eviction policy will drop enqueued
messages under memory pressure. Nothing errors — the send succeeded, the message
simply ceases to exist.

Entropia survives this **only** because the durable `jobs` row is the source of
truth and the scheduler re-delivers QUEUED jobs past
`JOB_REDELIVER_GRACE_SECONDS` (default 600s). Two caveats:

* Recovery takes up to a grace window, not instantly.
* The **`data` queue is deliberately excluded** from auto-redelivery
  (`ACTOR_BY_QUEUE`); lost `data` messages are logged as
  `scheduler.redeliver_unroutable` and re-dispatch is an operator action.

---

## Prove the round-trip end to end

The heartbeat exists exactly for this. After restoring Redis:

```bash
docker compose logs --tail=50 --no-color scheduler   # expect `scheduler.maintenance` each tick
docker compose logs --tail=50 --no-color worker-default  # expect `worker.heartbeat`
```

Then confirm the recorded proof, which is what the alert reads:

```sql
SELECT value, updated_at FROM app_metadata
 WHERE key = 'worker.maintenance.last_heartbeat_at';
```

`entropia_worker_heartbeat_age_seconds` should fall back under 60s.

---

## Recovery

`/health/ready` shows `redis: ok`, the heartbeat is fresh, and every queue's
QUEUED depth reaches 0 at least once.

---

## What this cannot tell you

* **Queue depth in Redis.** `entropia_jobs_depth` counts **durable `jobs` rows**,
  not broker messages. A message lost from Redis leaves the row QUEUED — which is
  precisely how `EntropiaQueueNeverDrains` catches it, but the two numbers are
  not the same thing and can legitimately disagree.
* **Whether a message was delivered twice.** At-least-once delivery is the
  contract; idempotency is enforced in the job body, not observed here.
