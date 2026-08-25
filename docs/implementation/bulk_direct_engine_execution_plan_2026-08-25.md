<!-- doc-status: historical -->
> **HISTORICAL RECORD — bu belge GÜNCEL GERÇEK DEĞİLDİR.** Yazıldığı andaki durumu
> kaydeder; SHA'lar, sayılar ve "next" maddeleri bayat olabilir. Güvenmeden önce yeniden ölç.

# Bulk / direct engine execution — measured baseline and plan (2026-08-25)

> **The ask.** Run the engine over many strategies at once — strategies that arrived from
> Create Package, strategies configured by hand, thousands of them concurrently — **without
> going through the HTTP API**. "Connect the motor, say run."
>
> **The short answer: the engine and the queue already do this. What is missing is a
> submission entry point, not an engine capability.** Nothing below proposes a second
> engine, and nothing below proposes bypassing Ready Check.

## 1. What already exists (measured, not assumed)

| Capability | Where | State |
|---|---|---|
| Multi-strategy composition in ONE run | `domain/backtest/engine.py::run_engine` over the item loop | **Shipped.** Independent multi-item runs are first-class (doc 13 §1.1) and are most of what production runs today. |
| Admission callable **without HTTP** | `application/commands/backtest_run.py:121::request_backtest_run(session, actor, *, composition_id, …)` | **Shipped.** A plain async function. The route is one caller, not the only possible one. |
| Durable queue + worker | `apps/worker/actors.py:178::run_backtest_engine` → `jobs/backtest_engine.py::run_backtest` | **Shipped.** Queue `backtest`. |
| Enqueue without HTTP | `infrastructure/queues/enqueue.py::send_job` | **Shipped.** |
| Worker horizontal scale | `apps/worker/__main__.py:27-28` — `--processes` (default 1), `--threads` (`settings.worker_concurrency`) | **Shipped**, deployment-configured. |
| Lost-message redelivery / stale recovery | `apps/scheduler/__main__.py` — `ACTOR_BY_QUEUE["backtest"]`, `recover_stale_jobs`, `redeliverable_queued_jobs` | **Shipped.** |
| Per-composition item cap | none found | No hard limit in code (`METADATA_MAX_ITEMS = 100` is rationale metadata, unrelated). |

**So "connect the motor and say run" is a thin script over `request_backtest_run`, not an
engine change.** That is the whole point of this document: the expensive part is already
built and proven.

## 2. What does NOT exist

1. **No direct entry point.** `pyproject.toml` declares no `console_scripts`; `scripts/`
   contains no backtest runner. Every production run today starts at the HTTP route.
2. **No fan-out submitter.** Nothing takes a list of compositions (or one composition set)
   and admits them as N runs with per-run idempotency keys and a progress view.
3. **No measured scale evidence.** Nobody has run hundreds or thousands of concurrent
   admissions against this stack. Worker `--processes`/`--threads` exist; what they do to
   the Postgres pool, the queue and Result storage at that volume is **unmeasured**. Any
   number in this document about throughput would be invented, so there is none.

## 3. The one thing that must NOT be bypassed

Skipping **HTTP** is fine — the command layer is a supported caller boundary. Skipping
**Ready Check** is not.

`commands/backtest_run.py:523-526` refuses admission when `blocker_count > 0` (422
`READINESS_BLOCKED`, whole transaction rolled back — no run, no manifest, no job). That gate
is what keeps a wrong result from ever being produced: an unresolved indicator becomes
`STRATEGY_INDICATOR_UNRESOLVED` instead of a run that silently computes nothing
(`commands/readiness_check.py:716`).

A bulk runner that calls `request_backtest_run` inherits this for free. A bulk runner that
reaches past it into `run_backtest` or `run_engine` would produce thousands of results
nobody can trust — and would be indistinguishable, in the Result table, from good ones.
**The runner therefore goes through `request_backtest_run`, always.**

## 4. Proposed slices

Ordered so each one is independently useful and independently reversible.

### B1 — a direct runner entry point
One module under `apps/` (mirroring `apps/scheduler`) exposing: admit a run for a named
composition, optionally wait for terminal state, print the Result id. Calls
`request_backtest_run` with a caller-supplied `Idempotency-Key`, then `send_job`.
*Deliverable:* running one composition end to end from a shell, no HTTP.
*Risk:* low — new file, no existing caller changes.

### B2 — fan-out over N compositions
Accept a list, admit each with its own idempotency key, bounded concurrency, and a summary
of admitted / blocked (with each blocker's code) / failed. Readiness rejections are DATA
here, not crashes: a blocked composition must be reported, never skipped silently.
*Risk:* low-medium — the honest failure summary is the hard part, not the loop.

### B3 — measured scale run
Run B2 at increasing N against a real stack and record where it actually breaks: DB pool
exhaustion, queue depth, worker saturation, Result write volume. Publish the numbers.
*This is the slice that turns "thousands" from an aspiration into a fact.*
*Risk:* medium — this is measurement, and its output may be "N is lower than hoped".

### B4 — whatever B3 proves is the bottleneck
Deliberately unspecified. Writing the fix before the measurement would be guessing.

## 5. Explicitly out of scope

**Shared-capital portfolio mode stays off.** `SHARED_ALLOCATION_STATUS` is `future_dev`
(`domain/allocation/capability.py:105`) and the shared branch does not execute. Bulk
execution runs strategies in INDEPENDENT mode — each on its own capital — which is exactly
what most production runs do today. Turning the flag on is a separate, signature-gated
decision (`G8` · `G14` · `G11`+`G12` · `G15`) and would change financial results; it is not
part of making bulk execution work, and must not be smuggled in with it.

## 6. Honest boundary

Everything in §1 was re-derived from the tree in this session. §2 is an absence claim from
targeted greps — absence is weaker evidence than presence, so treat it as "none found",
not "proven none". §3 is measured. **§4 is a proposal: no code from it has been written.**
No throughput, latency or capacity number appears anywhere in this document, because none
has been measured.
