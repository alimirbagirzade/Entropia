# Worker delivery & recovery matrix — ADIM 21

**Base:** `origin/main` @ `d7fe432` · **Date:** 2026-08-05 · **Branch:** `test/worker-recovery-chaos`

Goal: not exactly-once transport (Redis + dramatiq cannot give it) but **effectively-once
domain effects**. Whatever the broker or the scheduler does, the durable world must end up
with exactly one immutable revision / validation run / imported package / Result / purge
outcome, one audit trail and one outbox fan-out.

Everything below was reproduced against a real PostgreSQL. Where a row says a guard exists,
a test in this repo executes the double delivery and counts the rows; where a row says a
guard was missing, the reproduction is recorded with the failing assertion.

---

## 1. Job-type matrix

`claim` = how a delivery takes ownership. `RUNNING visible?` = whether the durable row shows
RUNNING to another reader mid-flight (it does not unless the body commits before finishing —
this is what decides whether the scheduler's QUEUED sweep can hand a *live* job to a second
worker). `Guard` = the at-least-once terminal check.

| Queue | Actor | Source row | Claim | RUNNING visible? | Lease | Retry | Terminal | Idempotency | Object writes | Commit | Ack |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `data` | `run_market_data_analysis` | `jobs` + `market_dataset_revision` | `claim_job_for_delivery` (job row `FOR UPDATE`) | ❌ no mid-body commit | stale sweep only | dramatiq ×3 | `succeeded` / raise | **job-row terminal replay** (ADIM 21) | processed Parquet, content-addressed | actor wrapper, one tx | after commit |
| `data` | `run_research_data_analysis` | `jobs` + `research_dataset_revision` | same | ❌ | stale sweep only | dramatiq ×3 | `succeeded` / raise | **job-row terminal replay** (ADIM 21) | native Parquet, content-addressed | actor wrapper, one tx | after commit |
| `data` | `run_trading_signal_import` | `jobs` + `source_asset` | same | ❌ | stale sweep only | dramatiq ×3 | `succeeded` / raise | **job-row terminal replay** (ADIM 21) | reads raw bytes only | actor wrapper, one tx | after commit |
| `data` | `run_trade_log_import` | `jobs` + `source_asset` | same | ❌ | stale sweep only | dramatiq ×3 | `succeeded` / raise | **job-row terminal replay** (ADIM 21) | reads raw bytes only | actor wrapper, one tx | after commit |
| `data` | `run_package_import` | `jobs` + `package_import_job` | same | ❌ | stale sweep only | dramatiq ×3 | `succeeded` (incl. recorded `failed` import) | **job-row terminal replay** (ADIM 21) | none | actor wrapper, one tx | after commit |
| `backtest` | `run_backtest_engine` | `jobs` + `backtest_run` + manifest | `bt_repo.get_run(for_update=True)` | ✅ commits at each stage (O-05) | stale sweep + stage commits | dramatiq ×3 | `succeeded`/`failed`/`cancelled` run states | `run.state in RUN_TERMINAL_STATES` | Result artifacts | staged commits + final | after commit |
| `agent` / `agent-high` | `run_agent_tool` / `_high` | `jobs` + `agent_tool_call` | job read (no lock) | ❌ | stale sweep only | dramatiq ×3 | tool-call terminal states | AL-14 `idempotency_key` lookup | evidence refs | actor wrapper, one tx | after commit |
| `agent-executor` | `run_agent_executor` | `jobs` + `agent_task` + `agent_runtime` | `refresh(runtime/task, with_for_update=True)` | ❌ | stale sweep only | dramatiq ×3 | `TASK_TERMINAL_STATES` | task terminal + not-QUEUED guard | checkpoints, artifacts | actor wrapper, one tx | after commit |
| `default` | `run_create_package_job` (4 kinds) | `jobs` + `package_request` | `refresh(root, with_for_update=True)` | ❌ | stale sweep only | dramatiq ×3 | `succeeded`/`failed_final`/`superseded` | `job.status in _JOB_TERMINAL` + superseded guard | baseline CSV read | actor wrapper, one tx | after commit |
| `maintenance` | `run_trash_purge` | `jobs` + `trash_entries` | entry read (no lock) | ❌ | stale sweep only | dramatiq ×3 | `purged` / `purge_failed` | `entry.status != PURGE_PENDING` | object deletes | actor wrapper, one tx | after commit |
| `maintenance` | `system_heartbeat` | — (no durable row) | — | — | — | ×3 | — | not applicable (no effect) | none | none | — |

**Cancellation** is a single plane's concern: only `backtest` implements it
(`cancel_requested_at` intent + four safe checkpoints, O-06). No other plane advertises
cancellation, so none is claimed here.

---

## 2. Failure-seam results

Seams are the injectable kwargs the bodies already expose (`load_and_parse`,
`write_processed`, `write_native`, `stream_bars`) plus the object-store monkeypatch the
ingest suites already use. **There is no sleep in any test in this slice**; the concurrency
case synchronises on a Postgres row lock (`FOR UPDATE NOWAIT`), not on a clock.

| # | Seam | Expected | Result |
|---|---|---|---|
| 1 | Crash **before** the DB commit | whole tx rolls back, row stays QUEUED, retry runs the body for real, exactly one artifact | ✅ `test_a_crash_before_commit_leaves_nothing_and_the_retry_writes_once` |
| 2 | Crash **after** the DB commit, **before** the ack (broker redelivers) | second delivery replays the recorded outcome, writes nothing | ✅ 5 data-plane tests + purge — **was ❌ before this slice, see §4** |
| 3 | Crash **after** the object write, before the commit | object exists with no row; the retry re-addresses the SAME key | ✅ `test_object_writes_are_content_addressed_so_a_retry_orphans_nothing` |
| 4 | Duplicate delivery of a **terminal** job | replay, byte-identical result reference | ✅ all six `..._redelivered_after_commit_...` tests assert `replay == first` |
| 5 | **Lease-expired old worker still alive** (two workers, one live job) | the second serializes behind the first's row lock | ✅ `test_a_live_delivery_locks_the_job_row_against_a_second_worker` (a `FOR UPDATE NOWAIT` probe from a second connection fails while worker A holds the claim) |
| 6 | Second worker after the first commits | replay, no second artifact | ✅ `test_a_second_worker_replays_once_the_first_delivery_commits` |
| 7 | **Stale scheduler** sweep re-dispatch | RUNNING past threshold → attempts+1 → QUEUED, or FAILED_FINAL with typed `STALE_JOB_RECOVERED` once exhausted; every recovery audited | ✅ already pinned by `test_hardening.py` (INF-09/INF-03) — **not duplicated here** |
| 8 | Broker `send` rejects during the sweep | logged, loop continues, count excludes it, row stays QUEUED | ✅ already pinned by `tests/unit/test_scheduler_redelivery.py` (O-23) |
| 9 | **Expected business failure** (malformed import manifest) | recorded terminal outcome, job SUCCEEDED, redelivery replays it — never retried | ✅ `test_an_expected_business_failure_is_recorded_and_never_retried` |
| 10 | Infra failure (unreadable asset, object-store error) | raises → rollback → dramatiq retry → exhaustion → stale sweep writes typed `FAILED_FINAL` | ✅ seam 1 + `test_hardening.py` exhaustion path |
| 11 | Purge redelivery | recorded skip, one tombstone, one `trash.purge_completed` audit | ✅ `test_purge_redelivery_never_purges_twice` |
| 12 | **Queue with no consumer** | every durable queue must be consumed by a worker service | ❌→✅ `test_every_durable_queue_has_a_worker_service` — **see §5** |
| 13 | Cancellation race (QUEUED vs worker claim) | both sides take the run row lock; late cancel is honestly not applied | ✅ already pinned by `test_backtest_run_cancellation.py` (O-06) — **not duplicated here** |

---

## 3. What each plane's guard actually is (cross-reference)

| Plane | Redelivery idempotence pinned by |
|---|---|
| `backtest` | `test_backtest_persistence.py::test_worker_is_redelivery_idempotent`, `test_backtest_run_events.py::test_terminal_redelivery_writes_no_further_events` |
| `agent-executor` | `test_agent_executor.py` (replay + pending-pause deferral) |
| `agent` / `agent-high` | `test_gateway_parity_*.py` (AL-14 tool-call idempotency) |
| `default` (Create-Package ×4) | `test_create_package_{precheck,baseline,candidate_validation}_worker.py` |
| `data` ×5 | **`test_worker_delivery_recovery.py` — new in this slice** |
| `maintenance` (purge) | **`test_worker_delivery_recovery.py` — new in this slice** |

### 3.1 Which of the new tests actually hold the line

Every new test was re-run with the five body fixes reverted (the guard module left in
place but unwired). **7 of the 11 integration tests fail without the fix** — those are the
regression barrier. The other **4 pass either way**; they are characterization tests that
pin behaviour which already existed, and they are recorded as such rather than counted as
protection:

| Fails without the fix (regression barrier) | Passes either way (characterization) |
|---|---|
| the five `..._redelivered_after_commit_...` data-plane tests | `test_purge_redelivery_never_purges_twice` — the maintenance plane's own guard predates this slice |
| `test_a_second_worker_replays_once_the_first_delivery_commits` | `test_a_live_delivery_locks_the_job_row_against_a_second_worker` — calls the helper directly, so it pins `claim_job_for_delivery` itself, not the five call sites |
| `test_an_expected_business_failure_is_recorded_and_never_retried` | `test_a_crash_before_commit_leaves_nothing_and_the_retry_writes_once` and `test_object_writes_are_content_addressed_so_a_retry_orphans_nothing` — both pin rollback / content-addressing semantics that the fix did not change |

The compose defect (§5) has its own reproduction: `test_every_durable_queue_has_a_worker_service`
fails against the pre-fix `docker-compose.yml` with
`durable queues with NO consumer: ['agent-executor']`.

---

## 4. Confirmed defect #1 — the `data` queue had no at-least-once guard

**Reproduced before any code was written.** Running `trading_signal.run_import` twice on the
same `job_id` (the commit-succeeded/ack-lost case) produced:

```
PROBE revisions=2 audits=2 outbox=2      # expected 1 1 1
```

All five `data`-plane bodies were structurally identical: read the job, set RUNNING, compute,
INSERT an append-only artifact with a freshly generated id, write audit + outbox, mark the job
SUCCEEDED. No terminal check and no row lock. Nothing rejects the duplicate — every artifact
carries a new primary key, so no unique constraint fires.

Worst case of the five is `package_import`: a second delivery mints a **second DRAFT package
root**, so the same imported package exists twice in the registry with no way to tell which
one anything pinned.

Three separate docstrings asserted the opposite, and none was true:

* `apps/scheduler/__main__.py` — *"workers on every plane are redelivery-idempotent, so an occasional double send is safe"*
* `application/jobs/maintenance.py` — *"Workers are redelivery-idempotent (proven per plane)"*
* `application/commands/data_queue.py` — *"every data-plane worker is redelivery-idempotent, so a double send is a no-op"*

The gap was in fact already **known and written down** — `tests/integration/test_gateway_parity_s4.py:561`
says verbatim: *"`run_import` has no terminal-state guard, so re-sending a finished job would
parse the file twice and write a second record batch."* That test worked around the gap
rather than closing it.

**Reachability.** Two independent paths, neither hypothetical:

1. the broker's own commit/ack window;
2. `maintenance.redeliverable_queued_jobs` — it re-dispatches every row still QUEUED past
   `JOB_REDELIVER_GRACE_SECONDS` (default **600s**). A `data` body runs in ONE transaction,
   so its RUNNING transition is invisible until it commits: an import that takes longer than
   the grace window is still QUEUED while it runs, and the Admin redelivery action
   (`POST /admin/data-queue/redeliver`) lists and routes it to a second worker.

**Fix — narrow, in shared worker infrastructure.** One new module,
`application/jobs/delivery.py::claim_job_for_delivery`, does a single locked read of the
durable row and answers both questions at once:

* *already terminal?* → return `job.result_ref` verbatim, write nothing;
* *another delivery live?* → the `FOR UPDATE` blocks until it commits, then answers the above.

The five bodies each lost three lines and gained three. Nothing else changed: a body that
raises still rolls back and still retries, because the guard keys on the **durable status**,
not on "have I seen this message".

Bodies that already hold a domain-row lock and guard on a domain terminal state — `backtest`
(run row), `agent_executor` (runtime + task), `create_package` (request root + `job.status`) —
answer both questions through that lock and were **left untouched**.

`run_idempotent` was evaluated for reuse and rejected: it de-duplicates an HTTP request by the
caller's `Idempotency-Key` inside the *admission* transaction, and by worker time that key is
already completed with the `202 queued` envelope. Replaying it would hand back the acceptance
body, never the worker's outcome. The two compose — the key stops a second job being created,
the claim stops one job running twice.

---

## 5. Confirmed defect #2 — `agent-executor` had no consumer in the shipped stack

`docker-compose.yml` declared four worker services covering `default,maintenance`, `data`,
`backtest`, and `agent,agent-high`. The **`agent-executor` queue was consumed by nothing** —
while `apps/agent_coordinator` actively dispatches to it (`send_job(run_agent_executor, ...)`)
and `ACTOR_BY_QUEUE` lists it as safely auto-redeliverable.

The two combine into a silent infinite loop: the Coordinator enqueues an Agent task, the
scheduler re-sends it to the empty queue every grace window, the send SUCCEEDS every time, and
the task never runs. Nothing reports a fault at any layer. `docs/ARCHITECTURE.md` §"planes"
enumerated the same four services, so the docs matched the (broken) deployment rather than the
code.

Reproduced deterministically by a config-contract test that reads the deployment, not a doc:

```
AssertionError: durable queues with NO consumer in docker-compose.yml: ['agent-executor'] —
jobs on these are enqueued, redelivered by the scheduler forever, and never run
```

**Fix.** A dedicated `worker-agent-executor` service. Its own service rather than a queue
appended to `worker-agent` because `run_agent_task` runs the full backtest engine inside its
body (its `stream_bars` default is the same S3-backed streamer `worker-backtest` uses) — it
carries the backtest plane's runtime profile, not the tool gateway's latency-sensitive one.

---

## 6. Residual orphan policy (object store)

Every data-plane object write is **content-addressed**: `<prefix>/<entity_id>/<sha256-of-bytes>`
(`infrastructure/s3/datasets.py`). The write happens before the DB commit, so a crash between
them leaves an object with no row.

There is **no reconciliation sweep, and this slice does not add one.** For a deterministic
retry none is needed: re-parsing the same source produces the same bytes, hence the same key,
so the retry *overwrites* the orphan rather than accumulating a second one. This is pinned by
`test_object_writes_are_content_addressed_so_a_retry_orphans_nothing`.

**The honest residual:** an orphan survives only when a retry produces *different* bytes for
the same logical artifact — a non-deterministic parse, or a source asset mutated between
attempts. Neither is reachable today (source assets are immutable and content-deduplicated on
upload, and the parsers are pure), so the residual is a bounded, unswept remainder rather than
a leak with a known rate. A sweep would need a reachability scan over the bucket against
`market_processed_asset` / research native assets; that is a separate slice and is **not**
claimed as done.

---

## 7. Honest boundaries of this slice

* ~~**`make accept` was NOT run, and the Docker process-restart smoke was NOT executed.**~~
  **CLOSED 2026-08-05 (post-merge) — see §7.1.** Docker was unavailable while this slice was
  authored (`docker info` failed, `docker compose` was not installed), so both gates shipped
  unexecuted and `scripts/worker-restart-smoke.sh` had only been syntax-checked (`bash -n`).
  Both have since been run against a live stack, including the mid-flight kill the script's
  own header calls the interesting case. Two pre-existing defects surfaced doing so.
* The `agent` / `agent-high` guard is `if idempotency_key is not None`. Every durable tool job
  observed in-tree carries one, but a caller that enqueues with `idempotency_key=None` would
  get an **unguarded** tool call. Not exercised here — recorded as an open question, not a
  claim in either direction.
* `purge` and `agent`/`agent-high` guard on domain state **without a row lock**, so their
  concurrent-delivery window (seam 5) is closed only by the fact that `maintenance` and
  `agent` bodies are short. Sequential redelivery is proven for both; simultaneous delivery is
  **not** proven for either.
* `claim_job_for_delivery` holds the job row lock for the caller's whole transaction. A second
  delivery therefore **waits** for a long import instead of returning immediately. That is the
  intended trade — returning early cannot distinguish "already done" from "in flight" — but it
  does mean a blocked worker thread for the duration.
* Frontend is untouched by this slice; no OpenAPI, migration or engine-semantics change.
* **Verification actually run:** full backend suite `3669 passed, 4 xfailed`, exit code 0,
  coverage 93.26% (gate >=90); `ruff check` / `ruff format --check` / `mypy src` clean;
  `openapi_export --check` reports no drift. The four pre-existing strict xfails are
  unchanged. No migration in this slice (single alembic head untouched).

---

### 7.1 Docker validation — run 2026-08-05, after the slice merged (PR #587 -> `f81ee82`)

Run against the PR head `cd02450` (identical tree to the merge commit for every file involved).
Engine: **OrbStack 2.2.2**, `docker` 29.4.0, Compose **v5.1.2**. Host ports 5432/6379/9000/9001
belong to native postgres/redis/minio on that machine, so the stack ran on the compose-
parameterized host ports (`PG_HOST_PORT=55432`, `REDIS_HOST_PORT=56379`, `MINIO_HOST_PORT=59000`,
`MINIO_CONSOLE_HOST_PORT=59001`, `API_HOST_PORT=58000`, `WEB_HOST_PORT=58080`) supplied through
the git-ignored `.env`. They must live in `.env` rather than the command line: `acceptance.sh`
and `worker-restart-smoke.sh` shell out to `docker compose` themselves, and with the variables
unset those calls re-render the infra services at their defaults and try to rebind the busy
native ports. Container-internal URLs (`postgres:5432` etc.) are unaffected.

**`make accept` -> exit 0.** 15/15 services PASS, every `RestartCount = 0`, the three one-shots
(`minio-setup`, `migrate`, `provision`) exited 0. Re-run after the SIGKILL smoke: still exit 0.

**`worker-agent-executor` boots and genuinely consumes its queue.** `{"queues":
"agent-executor", "event": "worker.boot"}` proves only that the flag parsed, so consumption was
confirmed at the broker: a 3 s `redis-cli MONITOR` sample shows the dramatiq consumer polling
`agent-executor` and its `.DQ` delay queue. §5's defect is closed in the shipped stack, not just
in the compose file.

**`make worker-restart-smoke` -> exit 0, but on an idle stack the result is vacuous.** Every
before/after count was `0` and `jobs` was empty, so no message was redelivered and
`claim_job_for_delivery` was never entered. What that run does establish: the seven planes
survive SIGKILL, return healthy with `RestartCount = 0`, and the sweeps invent nothing against an
empty durable store.

**Mid-flight kill (the strong form) — run under `dev-auth`, and the guard holds.** Staged 8
Market Data datasets (`create` -> `raw-uploads` with an 8.6 MB / ~150 000-row OHLCV CSV ->
`finalize`), fired all 8 `POST /market-datasets/{id}/analysis` concurrently, SIGKILLed
`worker-data` 6 s in while the bodies were parsing, restarted it, and waited for every job to go
terminal. Because `data` is deliberately excluded from scheduler re-dispatch (`ACTOR_BY_QUEUE`
has no `data` key), the only automatic redelivery here is dramatiq requeuing the killed
consumer's unacked messages — exactly the commit/ack seam §4's guard exists for. The plane
logged **11 `worker.market_analysis.start` events for 8 distinct jobs**, so at least three
redeliveries re-entered the body. Final state:

```
data jobs enqueued          9   (8 mid-flight + 1 earlier single-job probe)
market.analysis.requested   9
market.analysis.completed   8
market_validation_run       8   -- exactly one per succeeded job
audit_events               44
outbox_events              44   -- paired, no orphan

SELECT job_id, count(*) FROM market_validation_run GROUP BY job_id;
-- every row count = 1;  job_ids with count > 1: 0
```

Before this slice each of those redeliveries would have written a second `market_validation_run`
plus a second audit and outbox row. None did.

#### Defect #3 (pre-existing, NOT introduced here) — the same event-loop bug lives in the worker actors and **strands** durable jobs

`apps/worker/actors.py` calls `asyncio.run(...)` per message while
`infrastructure/postgres/engine.py::get_engine` is `@lru_cache(maxsize=1)`. Each dramatiq worker
thread therefore builds and closes its own loop over a process-wide asyncpg pool, so a connection
created under one loop is checked out under another:

```
RuntimeError: Task <Task ... _run_market_data_analysis() at apps/worker/actors.py:53>
  got Future <Future pending> attached to a different loop
Retries exceeded for message '26c0e9c2-b4e6-499f-8056-3161a1a458a3'.
```

Observed: **4 loop crashes across 11 deliveries** (11 `start` vs 7 `done`), and **one message
exhausted `max_retries=3` and was discarded**. Its durable row is stranded permanently —
`job_01KZ9717XQ5V0PKJ1PGKMB7P7B`, `status=queued`, `attempts=0` (the body crashed before
committing its RUNNING transition). Nothing recovers it: the broker message is gone and `data` is
by design not auto-redelivered, so re-dispatch is an operator action nobody is prompted to take.
A crash is **not** required to trigger this — any two `data` jobs running in parallel can hit it.

This does not contradict §4: the guard did its job and wrote no duplicate. It is the mirror
failure — an effect that never happens at all — on the same plane this slice hardened. The
identical anti-pattern is in `apps/scheduler/__main__.py::run()`, where it makes **exactly every
other** maintenance pass abort (observed 6 OK / 6 `scheduler.maintenance_failed` over 12
consecutive 30 s ticks, strict alternation), halving the effective rate of the outbox relay and
the INF-03/INF-09 sweeps. Both are tracked outside this slice.

> **The scheduler half is FIXED — PR #593 (`20a32ab`), merged 2026-08-05.** It holds one event
> loop for the process lifetime, so the alternation is gone. The measurement above is kept as the
> record of that run, not as current state. **The `apps/worker/actors.py` half stands exactly as
> measured** — #593 touched only the scheduler twin.

Related: `worker-restart-smoke.sh` step 5 greps for the substring `scheduler.maintenance`, which
also matches `scheduler.maintenance_failed`. In this run the `OK scheduler swept` line was
satisfied by a genuine successful pass, but the check would report the same on a stack where
every sweep fails.

> **Fixed in the same PR #593 (`20a32ab`)** — step 5 now greps `scheduler\.maintenance([^_]|$)`,
> so a stack whose every sweep aborts no longer reports `OK scheduler swept`.

#### Defect #4 (minor) — `worker-agent-executor` is missing from the dev-auth override

The service was added to `docker-compose.yml` (§5) but not to `docker-compose.dev-auth.yml`.
Verified on the running dev-auth stack:

```
api / worker-data / worker-agent / scheduler / agent-coordinator   AUTH_MODE=dev
worker-agent-executor                                              AUTH_MODE=session
```

`tests/unit/test_worker_plane_deployment.py` cannot catch it — it pins
`_COMPOSE = .../docker-compose.yml` and never reads the override. This is the same shape as the
defect §5 fixed (a plane declared in one place and forgotten in another), so extending that test
to the override file belongs with it.

> **FIXED — see §7.2.** The service was added to `docker-compose.dev-auth.yml` and the test now
> reads both files.

#### Transient observation

While the 8 analyses ran, `worker-data` saturated CPU (~130%) and its healthcheck —
`redis.ping()` in a fresh Python process, `timeout: 5s` — repeatedly exceeded the timeout, so the
container reported `unhealthy` and `make accept` would have failed at that moment. It returned to
`healthy` unaided once the load drained. Not a defect, but the 5 s margin is thin for a plane
doing CPU-bound parsing.

#### Still NOT proven by this run

The mid-flight evidence covers the **`data`** plane only, and within it the market-data actor.
The Trading Signal / Trade Log / Research Data / Package Import bodies share
`claim_job_for_delivery` and are covered by `test_worker_delivery_recovery.py`, but were not
crash-tested live. Seam 5 (two *simultaneous* deliveries of the same job) is still not exercised
against a live stack for any plane, and the `agent`/`agent-high` `idempotency_key=None` question
above remains open.

### 7.2 Defect #4 closed — the dev-auth override, and the test that now reads it

`docker-compose.dev-auth.yml` gained the missing `worker-agent-executor` entry, so all **10**
backend planes carry `AUTH_MODE: dev` under the override. Verified against the real merged
config rather than the source file — `docker compose -f docker-compose.yml -f
docker-compose.dev-auth.yml config` (exit 0), then the resolved `AUTH_MODE` read back per service
that runs `image: entropia-backend:local`:

```
agent-coordinator  api  migrate  provision  scheduler
worker-agent  worker-agent-executor  worker-backtest  worker-data  worker-default
-- all 10: AUTH_MODE=dev   (before: worker-agent-executor = session)
```

`tests/unit/test_worker_plane_deployment.py` now reads **both** compose files and pins the
invariant so the pairing cannot drift again:

- `test_dev_auth_override_forces_dev_mode_on_every_backend_plane` — the plane set is derived from
  the resolved `image: entropia-backend:local`, **not** a hand-kept name list, so a plane added
  through the `*backend-build` anchor is covered the moment it is written. Also asserts every
  override entry actually pins `AUTH_MODE: dev`, not merely that the key exists.
- `test_dev_auth_override_declares_no_service_the_base_stack_lacks` — the mirror defect. Compose
  merges by name, so a misspelt `worker-agent-exectuor:` raises nothing: it defines a new
  imageless service **and** leaves the real plane on session mode.

Reproduced red before the fix (`AssertionError: backend planes absent from
docker-compose.dev-auth.yml: ['worker-agent-executor']`), green after — 4 passed.

**Not covered by this:** `dev-auth` is currently the only override file, and the test names it
explicitly — a second override added later gets no coverage until someone extends the test. No
assertion is made about the base stack's own `AUTH_MODE` either; what is pinned is override-vs-base
coverage, not the value any given stack ends up running.
