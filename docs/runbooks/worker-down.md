# Runbook — Worker plane stopped

**Alerts:** `EntropiaWorkerHeartbeatStale` (page),
`EntropiaWorkerHeartbeatNeverRecorded` (page).

---

## Read this first — what the heartbeat actually proves

The scheduler enqueues `system_heartbeat` on the **`maintenance`** queue every
`SCHEDULER_TICK_SECONDS` (default 30s). The worker consuming it records the
completion into `app_metadata`, and `entropia_worker_heartbeat_age_seconds`
publishes the age.

So a fresh heartbeat proves exactly one thing: **`worker-default` (queues
`default,maintenance`) is alive and consuming.**

It says **nothing** about `worker-data`, `worker-backtest`, `worker-agent` or
`worker-agent-executor`. A dead `worker-backtest` leaves this gauge perfectly
fresh. Those planes are caught only by `EntropiaQueueNeverDrains`, and only once
work is actually pending — see [stale-jobs.md](stale-jobs.md).

---

## EntropiaWorkerHeartbeatStale — age > 180s for 5m

180s is six consecutive missed ticks at the 30s default.

The round-trip has three links. Find the broken one, in this order:

```bash
# 1. Scheduler alive and sweeping? Expect `scheduler.maintenance` every tick.
docker compose logs --tail=100 --no-color scheduler

# 2. Broker reachable?
docker compose exec redis redis-cli ping

# 3. Worker consuming? Expect `worker.heartbeat`.
docker compose logs --tail=100 --no-color worker-default
```

| Result | Cause | Action |
|---|---|---|
| No `scheduler.maintenance` | Scheduler stopped | Restart `scheduler` |
| `scheduler.maintenance_failed` present | Sweep failing — the line carries `error` | Usually Postgres: [postgres.md](postgres.md) |
| Scheduler fine, `PING` fails | Broker down | [redis.md](redis.md) |
| Both fine, no `worker.heartbeat` | Worker stopped or wedged | Restart `worker-default` |

### Why this is a page, not a ticket

The `maintenance` queue also carries the **outbox relay** and the **stale-job
reclaim**. When it stops, three things stop together: worker liveness, SSE event
delivery, and job recovery. Expect `EntropiaOutboxLagGrowing` to follow within
minutes; if it does, the scheduler is the common cause, not the worker.

---

## EntropiaWorkerHeartbeatNeverRecorded — series absent for 15m

The exposition prints the `# TYPE` line with **no sample** when no heartbeat has
ever been written, precisely so this is detectable instead of rendering a
healthy-looking `0.0`. This is a **provisioning** failure, not a runtime one.

```bash
docker compose ps scheduler worker-default
```

```sql
SELECT * FROM app_metadata WHERE key = 'worker.maintenance.last_heartbeat_at';
```

Zero rows and 15 minutes of uptime means the async plane was never wired up. Do
not accept user traffic on that deployment: every durable job is at risk, not
just maintenance.

Fix: start `scheduler` and a worker consuming `maintenance` (`worker-default` in
the shipped compose), then confirm the row appears.

---

## Checking a plane the heartbeat does not cover

```sql
SELECT queue, status, count(*) FROM jobs GROUP BY queue, status ORDER BY queue;
```

Queue-to-service map:

| Queue | Service |
|---|---|
| `default`, `maintenance` | `worker-default` |
| `data` | `worker-data` |
| `backtest` | `worker-backtest` |
| `agent`, `agent-high` | `worker-agent` |
| `agent-executor` | `worker-agent-executor` |

A queue with rising `queued` and no `running` means its consumer is gone.

---

## Verify a restart did not duplicate work

Delivery is at-least-once. After restarting any worker plane:

```bash
make worker-restart-smoke
```

This SIGKILLs every worker plane on a running stack and proves the restart
duplicates nothing.

---

## Recovery

`entropia_worker_heartbeat_age_seconds` back under 60s and holding, every queue
draining, and `EntropiaOutboxLagGrowing` clear.

---

## Known false positives

* A planned scheduler stop (debugging, maintenance window) reproduces both alerts
  exactly. **Silence before doing it.**
* `EntropiaWorkerHeartbeatNeverRecorded` is expected in the first minutes of a
  brand-new stack. `for: 15m` is the allowance; firing after that means the
  install is genuinely incomplete.

---

## What this cannot tell you

* **Per-queue liveness** — see the boundary at the top of this page.
* **Whether a worker is making progress.** A worker looping on one poisoned job
  still heartbeats. Look at `jobs.attempts` and [stale-jobs.md](stale-jobs.md).
* **Restart count.** Not recorded anywhere. `docker compose ps` shows the current
  state, not the history.
