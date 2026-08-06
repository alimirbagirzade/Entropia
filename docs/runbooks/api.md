# Runbook — API

**Alerts:** `EntropiaApiDown` (page), `EntropiaApiServerErrors` (page),
`EntropiaApiRequestsExceedLargestBucket` (ticket).

---

## EntropiaApiDown — `up{job="entropia-api"} == 0` for 2m

### First 60 seconds

```bash
make ps
```

Then, from a client network — this is the question that decides whether users are
affected:

```bash
curl -sS -o /dev/null -w '%{http_code}\n' http://<host>:8000/api/v1/health/live
```

### Discriminate

| Observation | Cause | Go to |
|---|---|---|
| `health/live` returns 200 | The **scrape** is broken, not the API | "Scrape-only failures" below |
| Container absent or exited | Process died | Restart, then read the logs you captured |
| Container up, port refused | Bind/network/proxy | Check `API_HOST_PORT` and the reverse proxy |
| Container restarting in a loop | Crash on boot | Capture logs **before** the next restart |

```bash
docker compose logs --tail=200 --no-color api
```

### Scrape-only failures

The API is fine and only monitoring is blind. Two causes dominate:

* **Credential.** `/metrics` is gated by `ENTROPIA_METRICS_TOKEN`. A missing
  Bearer is 401, a wrong one is 403 — and in **production a token that was never
  configured is 403 by design**, so a fresh deployment that forgot the variable
  looks exactly like an outage. Verify:

  ```bash
  curl -sS -o /dev/null -w '%{http_code}\n' \
    -H "Authorization: Bearer $ENTROPIA_METRICS_TOKEN" \
    http://<host>:8000/api/v1/metrics
  ```

* **Job name.** The rules match `job="entropia-api"`. Rename the scrape job and
  the alerts stop matching without any error anywhere.

### Recovery

`up == 1` sustained 5m **and** `/health/ready` returns 200 with all three checks
`ok`.

### Escalation

Page immediately — this alert means the product is unavailable. If the container
crash-loops on boot, treat as a release incident and roll back rather than
restarting repeatedly; each restart discards the frame that explains it.

---

## EntropiaApiServerErrors — 5xx that will not stop

Fires when at least one 5xx lands in every sliding 5-minute window for 10
minutes. That is **not** the same as "continuous": roughly three errors spaced
under 5 minutes apart are enough, and this is a paging alert. A single 500 is
not — `rate()` decays out of the window well before `for: 10m` elapses.

The threshold is **zero**, not a percentage: `docs/performance/README.md` pins
"errors in a load run = 0" as the one hard gate, and this alert inherits it
rather than inventing an SLO the project deliberately left unset. `for: 10m` is
what keeps a single 500 from paging.

### Localise

```promql
sum by (path, status) (rate(entropia_http_requests_total{status=~"5.."}[5m]))
```

| Shape | Meaning | Next |
|---|---|---|
| One `path` | That handler, usually a recent change | Roll back the release |
| Every `path` | A shared dependency | `/health/ready`, then [postgres.md](postgres.md) / [redis.md](redis.md) / [object-storage.md](object-storage.md) |
| Only artifact/export paths | Object storage | [object-storage.md](object-storage.md) |

```bash
curl -sS http://<host>:8000/api/v1/health/ready | jq
```

### Correlate a specific failure

Every response carries `X-Request-Id` and `X-Correlation-Id`, and both are
mirrored into the error envelope (`code`, `message`, `details`, `request_id`,
`correlation_id`). Take the id from the user's report and grep the API log for
it — that is the intended path from a complaint to a log line.

```bash
docker compose logs --no-color api | grep '<request-id>'
```

**Boundary:** the correlation id is bound by the API middleware only. It does
**not** reach worker logs, so the trail ends where the job is enqueued.

### Recovery

The 5m 5xx rate returns to 0 and holds for 15m.

---

## EntropiaApiRequestsExceedLargestBucket — requests slower than 5s

5.0s is not a new target — it is the largest bucket already shipped in
`infrastructure/observability/metrics.py`. Overflowing it means "slower than this
exposition can even measure".

### Localise

```promql
  sum by (path) (rate(entropia_http_request_duration_seconds_bucket{le="+Inf"}[10m]))
- sum by (path) (rate(entropia_http_request_duration_seconds_bucket{le="5.0"}[10m]))
```

### Likely causes, in order

1. **Query-count regression.** `docs/performance/query_budgets.json` records the
   expected DB round trips per operation and their per-item slope. A regression
   there surfaces here first. Run the budget gate:
   `cd backend && uv run pytest tests/integration/test_query_budgets.py`.
2. **Pool contention.** The engine sets no explicit `pool_size`, so SQLAlchemy's
   default 5 + 10 overflow applies per process. Under concurrency, requests queue
   for a connection and the wait lands in this histogram.
3. **Legitimate long operations.** Uploads and exports genuinely exceed 5s and
   are counted here. Confirm the `path` is an interactive read before calling it
   a regression.

### Recovery

The over-5s rate returns to 0 for 30m.

### Escalation

Ticket. Escalate to page only alongside `EntropiaApiServerErrors` or a rising
`entropia_http_requests_in_flight`.

---

## What this cannot tell you

* **Per-endpoint saturation.** `entropia_http_requests_in_flight` is a single
  process-wide gauge with no alert — no adjudicated concurrency target exists.
* **Which user or tenant is affected.** Ids are deliberately kept out of metric
  labels; use the structured logs and the request id.
* **Whether the async plane is healthy.** A perfectly green API says nothing
  about workers. See [worker-down.md](worker-down.md).
