# Metric and alert matrix (ADIM 25)

The complete, verified inventory of what Entropia can observe today — and, just
as importantly, what it **cannot**. Every row was checked against the code at
`e5c650a`; nothing here is aspirational.

Two rules govern this document:

1. **No metric appears here that the code does not emit.** A matrix that lists
   intentions reads as coverage and produces none.
2. **Section 4 is not a backlog, it is a warning.** Anything listed there is
   invisible to alerting right now. Do not write a rule over it, and do not
   assume an operator will be paged when it breaks.

---

## 1. Exposition surface

| Fact | Value |
|---|---|
| Endpoint | `GET {API_BASE_PATH}/metrics` — `apps/api/routes/metrics.py` |
| Format | Prometheus text exposition `0.0.4` |
| Auth | Bearer `ENTROPIA_METRICS_TOKEN`. Missing credential -> 401, wrong -> 403. Token unset: open in local/dev, **403 fail-closed in production** |
| Rate limiting | Exempt (`hardening._EXEMPT_SUFFIXES`) — shedding a scrape blinds the operator exactly when load is highest |
| Processes exposing it | **API only.** Worker, scheduler and agent-coordinator have no HTTP surface |
| Degradation | If PostgreSQL is unreachable at scrape time the four DB-backed gauges are replaced by a comment line. The scrape still returns 200 |

**Scrape assumption baked into the rules:** job name `entropia-api`. Change it in
`prometheus.yml` and `EntropiaApiDown` / `EntropiaMetricsDatabaseProbeFailing`
silently stop matching.

---

## 2. Metrics that exist

Producer notation: `P` = in-process registry (`infrastructure/observability/metrics.py`),
`Q` = computed at scrape time from PostgreSQL (`application/queries/job_gauges.py`).

| Metric | Type | Labels | Prod. | Cardinality bound | Alert | Runbook |
|---|---|---|---|---|---|---|
| `entropia_http_requests_total` | counter | `method`, `path`, `status` | P | `method` <= **8** (the 7 in `hardening._KNOWN_METHODS` + `other`), `path` <= **178** (177 route templates + the literal `unmatched`), `status` <= observed codes. **Both** label axes are clamped: `path` to the resolved route template, `method` to the known set — `request.method` is an arbitrary wire token and used to pass through verbatim | `EntropiaApiServerErrors` | [api.md](api.md) |
| `entropia_http_request_duration_seconds` | histogram | `method`, `path` | P | 9 buckets + `+Inf` + `_sum` + `_count` per `(method, path)`; same clamps as above | `EntropiaApiRequestsExceedLargestBucket` | [api.md](api.md) |
| `entropia_http_requests_in_flight` | gauge | — | P | 1 | none — see §3 | [api.md](api.md) |
| `entropia_jobs_depth` | gauge | `queue`, `status` | Q | 7 queues x 9 `JobStatus` values = **63** | `EntropiaQueueNeverDrains`, `EntropiaJobsFailingTerminally` | [stale-jobs.md](stale-jobs.md) |
| `entropia_outbox_lag_seconds` | gauge | — | Q | 1 | `EntropiaOutboxLagGrowing`, `EntropiaOutboxLagSevere`, and `absent()` in `EntropiaMetricsDatabaseProbeFailing` | [outbox-lag.md](outbox-lag.md) |
| `entropia_job_lease_age_seconds` | gauge | — | Q | 1 | `EntropiaJobLeaseStuck` | [stale-jobs.md](stale-jobs.md) |
| `entropia_worker_heartbeat_age_seconds` | gauge | — | Q | 1 | `EntropiaWorkerHeartbeatStale`, `EntropiaWorkerHeartbeatNeverRecorded` | [worker-down.md](worker-down.md) |

Label values worth pinning in your head, because getting them wrong produces a
rule that matches nothing and never fires:

* `queue` ∈ `default`, `maintenance`, `data`, `backtest`, `agent`, `agent-high`, `agent-executor`
* `status` on `entropia_jobs_depth` is `str(JobStatus)`, i.e. **lowercase**:
  `queued`, `claimed`, `running`, `cancellation_requested`, `cancelled`,
  `failed_retryable`, `failed_final`, `succeeded`, `superseded`.
  There is **no `failed`** — the terminal value is `failed_final`.
  (`test_alert_rules_contract.py` enforces this against the enum.)

### Health probes (not metrics)

| Probe | Checks | Consumer |
|---|---|---|
| `GET /health/live` | process only | compose/orchestrator healthcheck for `api` |
| `GET /health/ready` | postgres, redis, object_storage; 503 when any is down | operator + orchestrator |

Worker, scheduler and coordinator containers are health-checked with a **Redis
PING**, not an HTTP probe — they serve no HTTP.

---

## 3. Why there is no latency or saturation SLO alert

`docs/performance/README.md` records a deliberate decision: the interactive-read
p95 row is **"to be filled from the first nightly artifacts — deliberately blank
rather than guessed"**, and the reference state carries no latency, throughput or
resource target at all.

So no rule here invents one.

* **Latency** is alerted only via `EntropiaApiRequestsExceedLargestBucket`, which
  compares against `le="5.0"` — the largest bucket already shipped in
  `metrics.py:15`. "Slower than the exposition can measure" is a structural fact
  about the histogram, not a new product target.
* **Saturation** (`entropia_http_requests_in_flight`) has **no alert**. A
  threshold needs an adjudicated concurrency target, and none exists. The gauge
  is published for dashboards and for correlation during an incident.

`test_alert_rules_contract.py::test_no_rule_invents_an_absolute_latency_target`
enforces this: any `le=` other than the shipped largest bucket or `+Inf` fails.

---

## 4. NOT OBSERVABLE TODAY

**Read this section as an alerting blind-spot map.** Each row is a failure mode
that no metric will catch. Diagnosis is possible — via logs or SQL — but only
*after* a human already suspects a problem.

| Area | What is missing | What exists instead | Consequence |
|---|---|---|---|
| **Backtest** | admission, readiness, run duration, result-write latency, bars processed, artifact write errors | `backtest_engine.py` and `commands/backtest_run.py` contain **no logger at all**. Evidence is domain-level: `backtest_run_event` rows (`RUN_STARTED`, `RUN_STAGE_CHANGED`, `RUN_SUCCEEDED`) + audit + outbox twins | A slow or failing engine is visible only as a `backtest`-queue job aging. See [backtest.md](backtest.md) |
| **Agent coordinator** | tick count, cycle duration, state transitions, task/checkpoint counts, ToolCall error rate | logs only: `agent_coordinator.cycle` (fields `runtime_status`, `consumed_directive`, `followup_task_id`, `executor_job_id`), `.dispatch_failed`, `.cycle_failed` | A coordinator looping without progress looks identical to an idle one. See [agent-coordinator.md](agent-coordinator.md) |
| **SSE** | connection count, dropped-event count, replay lag | `SseHub.subscriber_count` exists but is read **only by tests**. Overflow is a boolean flag (`_overflowed`), so the number of dropped events is never recorded — each burst yields one `stream.resync` frame | Cannot distinguish "quiet system" from "fan-out broken". Nearest proxy: `entropia_outbox_lag_seconds` |
| **Object storage** | availability, read/write success rate, checksum failures | `/health/ready` boolean only; `object_storage.probe_failed` log carries `error_type` | Storage degradation surfaces as 5xx on artifact routes, not as a storage signal. See [object-storage.md](object-storage.md) |
| **Backup** | backup age, verify pass/fail | `MANIFEST.json` per backup dir (`created_at_utc`, `git_commit`, `alembic_head`, `public_table_count`, `postgres_dump_bytes`, `object_storage_included`). `backup-verify.sh` prints a human line and exits 0/1 — **no status file**. No cron/systemd unit invokes `backup.sh` | **Backups are operator-initiated. A missed backup raises nothing.** See [backup-restore.md](backup-restore.md) |
| **DB pool** | pool size/overflow/checkout utilisation | `create_async_engine` sets only `pool_pre_ping=True`; no `pool_size`, `max_overflow`, `pool_timeout`. SQLAlchemy defaults (5 + 10 overflow) apply **per process** | Pool exhaustion presents as latency, then 5xx, with no direct signal. See [postgres.md](postgres.md) |
| **Worker (per queue)** | liveness of `data`, `backtest`, `agent`, `agent-high`, `agent-executor` workers | `entropia_worker_heartbeat_age_seconds` covers the **`maintenance` queue only** (`worker-default`) | A dead `worker-backtest` leaves the heartbeat fresh. Caught indirectly by `EntropiaQueueNeverDrains`, and only once work is pending |
| **Correlation into workers** | `correlation_id` in worker logs | bound by the API middleware only (`apps/api/context.py`). `Job.correlation_id` exists as a **column** but no actor binds it to the log context | An API request cannot be traced into the worker log line that executed its job |
| **Alert NOTIFICATION** — *(was "the alert rules themselves"; the PromQL-validation half was closed in ADIM 26)* | an Alertmanager. No receiver, no routing, no silences, no on-call integration; `severity: page` vs `ticket` is a label nothing reads | the rules are now **evaluated**, not just tokenized: `scripts/alert-rules-gate.sh` runs `promtool check config` + `check rules` + `test rules` against a digest-pinned Prometheus as its own blocking CI job, and `ops/alerts/entropia.rules.test.yml` proves each of the 11 alerts actually reaches `alertstate="firing"` on synthetic series. `ops/prometheus/prometheus.yml` makes `job="entropia-api"` a real scrape job, and the contract test fails on any rule naming a job it does not declare | **Rules that fire correctly still notify nobody.** The evaluation blind spot is closed — the ADIM 25 `and absent(...)` defect now fails the gate (proven by deleting `on()`: `check rules` stays green, `test rules` reports `got: nil`). The DELIVERY blind spot is not: standing up Alertmanager was deliberately out of ADIM 26's scope, which is a validation gate, not a monitoring stack. Two things also remain unvalidated: the rules are never evaluated against **real production series** (a metric that exists but is never populated looks healthy here), and no gate proves the deployed Prometheus is actually configured from this file |
| **Log redaction** | a structlog scrubbing processor | enforced **by hand, per call site** — probes log `type(exc).__name__` instead of `str(exc)` because driver errors echo the DSN. `errors.py:203` still logs `str(exc)` | A new call site can leak a secret without any gate objecting. `test_probe_failure_logging.py` covers the probes only |

---

## 5. Maintenance

* Alert rules: `ops/alerts/entropia.rules.yml`
* Scrape config: `ops/prometheus/prometheus.yml` — the file that makes
  `job="entropia-api"` a checked fact rather than a comment. No Prometheus
  service is shipped; mount `ops/` into one you run yourself.
* Enforcement runs at **two levels**, and both are blocking:
  * *Text* — `backend/tests/contract/test_alert_rules_contract.py`: metric names
    are derived from the exposition code, thresholds are checked against the
    configuration defaults they claim to be multiples of, every `runbook`
    annotation must resolve to a real file, and every `job=` matcher must name a
    job the scrape config declares.
  * *Evaluation* — `scripts/alert-rules-gate.sh` (CI job **Alert rules —
    promtool**): `check config`, `check rules`, then `test rules` over
    `ops/alerts/entropia.rules.test.yml`. Run it locally before pushing; it needs
    docker and nothing else.
* Adding a metric: emit it, then add the row here, then (only then) write a rule.
  The contract test will reject a rule over a metric that does not exist.
* Adding a rule: it is not done until `entropia.rules.test.yml` contains a case
  in which it reaches `alertstate="firing"`.
  `test_every_alert_has_an_evaluated_firing_case` refuses a rule nobody has run.
