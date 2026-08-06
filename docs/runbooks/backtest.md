# Runbook — Backtest run stuck, slow, or produced no Result

**No alert fires on the backtest engine.** This is the single largest
observability gap in the system and you should know its exact shape before an
incident, not during one.

`application/jobs/backtest_engine.py` and `application/commands/backtest_run.py`
contain **no logger at all** — not "logs only", *no* operational logs. There is
no timing, no bars-processed counter, no artifact-error counter. The only
alerting signal a stuck run produces is its `backtest`-queue **job** aging, via
`EntropiaJobLeaseStuck` and `EntropiaQueueNeverDrains`.

What you have instead is **durable domain evidence**, which is richer than a
metric but must be queried deliberately.

---

## Vocabulary that matters here

* A **Backtest Run** and a **Backtest Result** are different entities. A Run is
  an execution; a Result is an immutable artifact.
* **Only a `succeeded` Run materialises a Result.** `failed` and `cancelled` keep
  diagnostics and produce no Result and no history row. This is not a policy you
  may relax to clear an alert.
* `BacktestRunState`: `queued`, `provisioning`, `running`, `succeeded`, `failed`,
  `cancelled`.

---

## Where a run actually is

```sql
SELECT run_id, state, created_at, started_at, finished_at
  FROM backtest_run WHERE run_id = '<run-id>';

SELECT sequence_no, event_type, previous_state, state, occurred_at, detail
  FROM backtest_run_event
 WHERE run_id = '<run-id>'
 ORDER BY sequence_no;
```

`backtest_run_event` is the stage stream: `RUN_STARTED`, `RUN_STAGE_CHANGED`,
then one terminal `RUN_SUCCEEDED` / `RUN_FAILED` / `RUN_CANCELLED`. The `detail`
payloads carry counts such as `prepared_item_count`, `strategy_item_count`,
`item_count`, `replayed_item_count`.

**This is how you tell "progressing" from "stuck":** re-run the query a few
minutes apart. New `RUN_STAGE_CHANGED` rows, or a rising item count, mean the
engine is working — a long run is not a stuck run. No new rows across several
minutes means it is wedged.

Bars processed is **not** emitted anywhere. Stage events are the finest
granularity available.

---

## Discriminate

| Observation | Cause | Action |
|---|---|---|
| No `jobs` row for the run | Enqueue failed | Check the API log at submit time |
| Job `queued`, never `running` | `worker-backtest` not consuming | [worker-down.md](worker-down.md) |
| Job `running`, stage events advancing | Legitimately long | **Wait.** Do not kill it |
| Job `running`, no stage event for minutes | Wedged | See below |
| `RUN_FAILED` present | Real failure | Read `detail`; the run correctly produced no Result |
| Run `succeeded`, no Result visible | Artifact write or projection | [object-storage.md](object-storage.md) |

### A wedged run

```sql
SELECT job_id, queue, status, attempts, max_attempts, claimed_at, started_at
  FROM jobs WHERE queue = 'backtest' AND status = 'running';
```

Then check whether it is blocked in the database rather than computing:

```sql
SELECT pid, now() - query_start AS age, left(query, 120)
  FROM pg_stat_activity WHERE state <> 'idle' ORDER BY age DESC LIMIT 5;
```

Let the scheduler's reclaim sweep handle it (RUNNING past
`JOB_STALE_AFTER_SECONDS` = 600s). If the sweep is not running, that is the real
incident — [worker-down.md](worker-down.md).

---

## The rule that overrides operator convenience

**Never advance a run's state by hand.** Forcing a `backtest_run` row to
`succeeded` would let an immutable Result and its manifest be built on an
execution that never completed — and a pinned manifest is never re-derived from
live state afterwards, so the fabrication becomes permanent and unnoticeable.

Re-run instead. A re-run is cheap; a corrupted Result is not.

---

## Recovery

The run reaches a terminal state on its own, and `EntropiaJobLeaseStuck` clears.
A `failed` run that failed for a real reason is a **correct** outcome, not an
unresolved alert.

---

## What this cannot tell you

Everything below is invisible and no alert will ever fire for it:

* Admission and readiness-check latency.
* Run duration, per-stage duration, bars processed.
* Result-write latency and artifact write errors.
* Engine-level errors that were caught and turned into a `RUN_FAILED` detail —
  the detail is durable, but nothing aggregates or alerts on it.

Adding any of these means emitting a metric first; the alert-rules contract test
will reject a rule over a metric that does not exist.
