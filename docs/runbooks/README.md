# Operator runbooks (ADIM 25)

One page per failure mode, reachable from the alert that fires. Each is written
for the operator who was asleep ninety seconds ago: symptom first, then the
smallest command that discriminates between causes, then the fix.

## Index

| Runbook | Covers | Alerts that land here |
|---|---|---|
| [api.md](api.md) | API down, 5xx, requests past the largest histogram bucket | `EntropiaApiDown`, `EntropiaApiServerErrors`, `EntropiaApiRequestsExceedLargestBucket` |
| [postgres.md](postgres.md) | PostgreSQL unreachable, connection exhaustion, slow queries | `EntropiaMetricsDatabaseProbeFailing` |
| [redis.md](redis.md) | Broker down, lost messages, eviction | — (no metric; see the matrix §4) |
| [object-storage.md](object-storage.md) | MinIO/S3 unavailable, artifact read/write failures | — (no metric; see the matrix §4) |
| [worker-down.md](worker-down.md) | A worker plane has stopped consuming | `EntropiaWorkerHeartbeatStale`, `EntropiaWorkerHeartbeatNeverRecorded` |
| [stale-jobs.md](stale-jobs.md) | Stuck leases, queues that never drain, terminal failures | `EntropiaJobLeaseStuck`, `EntropiaQueueNeverDrains`, `EntropiaJobsFailingTerminally` |
| [outbox-lag.md](outbox-lag.md) | Event relay behind; SSE stale | `EntropiaOutboxLagGrowing`, `EntropiaOutboxLagSevere` |
| [alert-notification.md](alert-notification.md) | How any of the above reaches a human — routing, fail-closed startup, silencing, and what delivery still does not prove | *(all 11 — this is the path, not a rule)* |
| [backtest.md](backtest.md) | A run is stuck, slow, or produced no Result | — (no metric; diagnosis is via `backtest_run_event`) |
| [agent-coordinator.md](agent-coordinator.md) | Coordinator looping without progress, executor starved | — (no metric; logs only) |
| [backup-restore.md](backup-restore.md) | Taking, verifying and restoring a backup | — (**backups are operator-initiated; nothing alerts on a missed one**) |
| [migration.md](migration.md) | Applying, verifying and rolling back a schema migration | — |

## Before you use any of these

**Know what is NOT watched.** Read
[METRIC_ALERT_MATRIX.md §4](METRIC_ALERT_MATRIX.md#4-not-observable-today)
once, in advance. Backtest internals, Agent coordinator progress, SSE fan-out,
object-storage health, backup age and DB pool utilisation have **no metric**. No
alert will wake you for any of them.

## Conventions

* Commands assume the Docker stack (`docker-compose.yml`) and are run from the
  repository root. Services: `api`, `worker-default`, `worker-data`,
  `worker-backtest`, `worker-agent`, `worker-agent-executor`,
  `agent-coordinator`, `scheduler`, `postgres`, `redis`, `minio`, `web`.
* `make` targets are the supported entry points — `make ps`, `make logs`,
  `make smoke`, `make accept`, `make backup`, `make restore`, `make migrate`.
* **Severity `page`** = product is unavailable or silently losing work; wake
  someone. **Severity `ticket`** = degraded but serving; handle in hours.
* Every runbook ends with a *"What this cannot tell you"* section. Read it before
  concluding that a clean check means a healthy system.

## Rule that overrides operator convenience

Never hand-edit a durable row to make an alert stop. A `jobs` row forced to
`succeeded`, or a `backtest_run` forced past a failure, **fabricates an outcome
no execution produced** — and downstream, an immutable Result and its manifest
will be built on it. Only a `SUCCEEDED` run may yield a Result. Fix the cause,
or leave the failure visible.
