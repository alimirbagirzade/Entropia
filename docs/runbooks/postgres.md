# Runbook — PostgreSQL

**Alert:** `EntropiaMetricsDatabaseProbeFailing` (page) —
`up{job="entropia-api"} == 1 and absent(entropia_outbox_lag_seconds)` for 5m.

That expression is structural, not tuned. `apps/api/routes/metrics.py` degrades
the DB-backed gauge block to a comment line when it cannot open a session, so all
four gauges vanish together while the process counters keep flowing. **"API up,
gauges absent" means exactly one thing: the API cannot reach PostgreSQL.**

Treat it as a live incident even though `/metrics` still returns 200: with
Postgres unreachable, every durable write is failing.

---

## First 60 seconds

```bash
curl -sS http://<host>:8000/api/v1/health/ready | jq
docker compose ps postgres
docker compose logs --tail=200 --no-color postgres
```

In the API log, look for `metrics.operational_gauges_probe_failed`. It carries
`error_type` **only, by design** — driver errors echo the DSN and that body is
served to a scraper. To see more, reproduce the connection yourself rather than
asking the log to leak it.

---

## Discriminate

| Symptom | Cause | Action |
|---|---|---|
| Container exited | Crash or OOM | Check `docker compose logs postgres` for the signal, restart |
| `FATAL: sorry, too many clients already` | Connection exhaustion | See below |
| `could not extend file` / `No space left` | Disk full | Free space **before** restarting; a full-disk restart can worsen it |
| Container up, API cannot connect | Network/credentials | Verify `DATABASE_URL` resolves from inside the API container |

```bash
docker compose exec api python -c "import os;print(os.environ['DATABASE_URL'].split('@')[-1])"
```

That prints host/db only — never echo the full DSN into a shared channel.

---

## Connection exhaustion

This is the failure the deployment is least protected against, so check it early.

`infrastructure/postgres/engine.py` creates the engine with `pool_pre_ping=True`
and **no explicit `pool_size`, `max_overflow` or `pool_timeout`**. SQLAlchemy's
defaults (5 + 10 overflow) therefore apply **per process**, and the stack runs
one API plus seven worker/scheduler/coordinator planes.

```sql
SELECT count(*), state FROM pg_stat_activity
 WHERE datname = current_database() GROUP BY state;
SHOW max_connections;
```

If `count(*)` is at or near `max_connections`:

1. Identify the hoarder — `SELECT application_name, count(*) FROM pg_stat_activity GROUP BY 1 ORDER BY 2 DESC;`
2. Restart that plane rather than raising `max_connections` blindly.
3. Long-term, this is a **known gap** (matrix §4): pool utilisation is not
   exposed as a metric, so exhaustion presents first as latency
   (`EntropiaApiRequestsExceedLargestBucket`), then as 5xx.

---

## Slow queries

```sql
SELECT pid, now() - query_start AS age, state, left(query, 120)
  FROM pg_stat_activity
 WHERE state <> 'idle' AND now() - query_start > interval '30 seconds'
 ORDER BY age DESC;
```

Before cancelling anything, check whether the query belongs to a running
backtest — see [backtest.md](backtest.md). A long backtest read is progress, not
a fault.

The expected round-trip counts per operation are recorded in
`docs/performance/query_budgets.json`; a query that is *new* rather than slow is
a regression against that budget.

---

## Recovery

* `entropia_outbox_lag_seconds` is present in the scrape again, **and**
* `/health/ready` returns 200 with `postgres: ok`.

Then check the knock-on effects — a Postgres outage stops the scheduler sweep, so
expect [outbox-lag.md](outbox-lag.md) and [stale-jobs.md](stale-jobs.md) to
follow, and confirm they clear on their own before standing down.

---

## Known false positives

* The very first scrape after an API restart can race pool warm-up. `for: 5m`
  covers it.
* A scrape refused by the auth gate returns 401/403 and never reaches this rule —
  a credential problem presents as `EntropiaApiDown`, not as this alert.

---

## What this cannot tell you

* **Replication lag, WAL growth, autovacuum health, bloat, index health.** None
  are observed. There is no metric and no probe.
* **Pool utilisation.** See above — invisible by construction.
* **Whether data is correct.** This alert is about reachability only.
