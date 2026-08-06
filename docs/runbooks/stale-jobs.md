# Runbook — Stuck leases, undrained queues, terminal failures

**Alerts:** `EntropiaJobLeaseStuck` (page), `EntropiaQueueNeverDrains` (ticket),
`EntropiaJobsFailingTerminally` (ticket).

Background: the scheduler's maintenance pass runs every
`SCHEDULER_TICK_SECONDS` (30s) and does four things in one transaction — relay
the outbox, reclaim RUNNING jobs older than `JOB_STALE_AFTER_SECONDS` (600s),
find QUEUED jobs past `JOB_REDELIVER_GRACE_SECONDS` (600s), and re-dispatch them.
The `scheduler.maintenance` log line reports `relayed`, `requeued`,
`failed_terminal`, `redelivered`.

---

## EntropiaJobLeaseStuck — lease age > 1200s for 10m

1200s is **2x** the reclaim bound. By then a healthy sweep has had ~20 chances to
act, so the age itself proves the reclaim path is not running or is failing.

### Identify

```sql
SELECT job_id, queue, status, attempts, max_attempts, claimed_at, started_at
  FROM jobs WHERE status = 'running'
 ORDER BY coalesce(started_at, claimed_at) LIMIT 5;
```

### Discriminate

| Observation | Cause | Action |
|---|---|---|
| No `scheduler.maintenance` in the log | Sweep not running | [worker-down.md](worker-down.md) |
| `scheduler.maintenance_failed` present (carries `error`) | Sweep failing | Usually Postgres: [postgres.md](postgres.md) |
| Sweep running, `attempts` climbing | The job is being reclaimed in a loop | It is poisoned — see below |
| Sweep running, `attempts` static, queue `backtest` | Possibly a legitimately long run | [backtest.md](backtest.md) **before** intervening |

### A poisoned job

`attempts` approaching `max_attempts` with no progress means the job fails the
same way each time. Read the worker log for that plane around the `claimed_at`
timestamps. Let it reach `failed_final` — that is the retry machinery working.
Do **not** reset `attempts` to buy more retries without fixing the cause.

### The rule that overrides convenience

**Never hand-edit a `jobs` row to `succeeded`.** That fabricates an outcome no
execution produced, and for a backtest it would let an immutable Result be built
on a run that never completed. Only a `SUCCEEDED` run may yield a Result.

### Recovery

`entropia_job_lease_age_seconds` below 600s.

---

## EntropiaQueueNeverDrains — QUEUED depth never reached 0 in 20m

20m is 2x the redelivery grace.

**Read the alert literally.** `entropia_jobs_depth` comes from a `GROUP BY`, so a
queue with zero QUEUED rows emits *no series* rather than a `0`, and
`min_over_time` skips gaps. What fires is "every sample this queue reported in
20 minutes was above zero" — **not** "the queue never emptied". A queue that
drained briefly and refilled still trips it. Confirm against the table below
before concluding anything is wedged.

### Read the `queue` label first

**`data` is the expected offender and is usually not a bug.** The `data` queue is
deliberately absent from the scheduler's `ACTOR_BY_QUEUE`: lost `data` messages
are logged as `scheduler.redeliver_unroutable` (with `queue`, `count`, and up to
20 `job_ids`) and re-dispatch is an **operator action** by design.

```bash
docker compose logs --no-color scheduler | grep redeliver_unroutable | tail -5
```

Any **other** queue means its consumer is gone — go to
[worker-down.md](worker-down.md) and use the queue-to-service map.

### Is it stuck or just busy?

```sql
SELECT queue, status, count(*) FROM jobs GROUP BY queue, status ORDER BY queue;
```

Rising `succeeded` alongside a non-zero `queued` is throughput, not breakage. Flat
`succeeded` with growing `queued` is a stopped consumer.

### Recovery

The queue reaches depth 0 at least once in a 20m window.

### Escalation

Escalate to page if the queue is `backtest` — users are waiting on run results
with no terminal state shown.

---

## EntropiaJobsFailingTerminally — new `failed_final` rows in the last hour

`delta` (not `increase`) because `entropia_jobs_depth` is a **gauge** of rows per
status. `failed_final` and not `failed_retryable`: the retryable state is the
retry machinery working as designed.

```sql
SELECT queue, count(*) FROM jobs
 WHERE status = 'failed_final' AND finished_at > now() - interval '1 hour'
 GROUP BY queue;
```

Then read the worker log for that queue around those timestamps.

| Shape | Meaning |
|---|---|
| Clustered on one queue | Systemic defect — escalate |
| Scattered across users | Often bad input failing validation as intended |

Terminal failures are user-visible: the originating page shows a failed job and
no result. Fix the cause and let the user re-submit.

### Recovery

No new `failed_final` transitions for 2h.

---

## What this cannot tell you

* **Job duration.** Not measured. There is no per-job timing metric — only the
  aggregate oldest-lease age.
* **Retry rate.** `attempts` lives on the row; no metric aggregates it.
* **Which job the lease-age gauge refers to.** It is a single aggregate; the SQL
  above is the only way to name the job.
* **Why a job failed.** The worker log is the only source; `.done` lines carry
  `job_id` and nothing else.
