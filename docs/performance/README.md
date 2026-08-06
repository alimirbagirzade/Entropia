# Performance, load and query budgets (ADIM 24)

This directory is the whole performance story: what is measured, on what machine, what
blocks a merge, and — as loudly — what is **not** measured.

> **There is no canonical SLO.** `docs/spec/01..22` and the V18 Master Technical
> Reference state no latency, throughput or resource target: `grep -rniE '\bSLO\b|p95|p99'
> docs/spec/` returns nothing. Every number in this directory that looks like a target is
> therefore labelled **operational target** — an engineering choice recorded here, never a
> product requirement, and never something to cite back as canon.

---

## 1. What gates what

| Gate | Where it runs | Blocks a PR | What it measures |
|---|---|---|---|
| **Query budgets** | `backend/tests/integration/test_query_budgets.py`, inside `ci.yml`'s pytest step | **yes** | DB round trips per operation, and the per-item slope |
| **Load-driver logic** | `backend/tests/unit/test_loadgen.py`, inside `ci.yml`'s pytest step | **yes** | the driver's own pass/fail decisions, plus that every scenario still exists in `docs/openapi.json` |
| **Load smoke** | `performance.yml` -> `load-smoke` | **yes** | every scenario answers 2xx against a real API process under light concurrency |
| **Load full** | `performance.yml` -> `load-full` (nightly 04:23 UTC + manual) | no (nightly) | latency percentiles, throughput, SSE, server gauges; writes the baseline artifact |
| Latency ratio | `scripts/loadgen.py --compare` | **not wired yet** | see §6 |

The division is deliberate. **Round-trip counts are deterministic** — identical on a
laptop and on a shared runner — so they can block a merge. **Milliseconds are not.** A
latency gate on a GitHub runner fails on weather, gets marked flaky, and is switched off
within a month; a gate that can never fail is worse than no gate at all (the same
reasoning `ci.yml` records for `npm audit --continue-on-error`).

---

## 2. The fixed environment

A baseline is only comparable inside its own **runner class**, recorded in every report
as `environment.runner_class`.

| Class | Definition |
|---|---|
| `github-ubuntu-latest` | GitHub-hosted `ubuntu-latest`, 2 vCPU / 7 GB. The only class CI produces. |
| `local-<os>-<arch>-dev-laptop` | A developer machine. Useful for before/after inside one sitting; **never** comparable to a CI baseline or to another laptop. |

Fixed across every run in a class:

* **Stack** — nightly: the full `docker compose` stack (API, workers, Postgres 16, Redis,
  MinIO) built from the repository. Smoke: the API process plus the `postgres:16-alpine`
  service, no workers and no object store, because the smoke only asks "does it answer".
* **Seed** — nightly seeds the E2E golden fixture (`SEED_E2E_GOLDEN=1 SEED_ESP_TA=1
  SEED_RATIONALE=1`), the same dataset the browser journeys run against, so Library,
  Results and Market Data are measured with rows on them instead of empty.
* **Auth** — the real session profile (argon2id credentials, opaque Bearer tokens), not
  dev impersonation. Per-request session verification is application work; excluding it
  would understate every authenticated scenario.
* **Cache state** — each run reports two phases. `cold` is one sequential lap with
  nothing warmed; `warm` is the concurrent matrix. They are reported apart because a
  first-touch page is a different measurement, not an outlier to be averaged away.
* **Concurrency / repeats** — smoke: 4 in flight, 5 passes. Nightly: 16 in flight, 40
  passes (both overridable on a manual dispatch).

---

## 3. Query budgets — `query_budgets.json`

Each surface records the **total** statements it issues at `n_small` and `n_large` rows
on its axis, from a cold identity map, plus the `per_item` slope between them. The slope
is the N+1 gate: a surface recorded at `0` that starts reading per row fails even when
its small-`n` total is unchanged.

This is a **ratchet**. Under budget prints a tighten-me line (`pytest -s`); over budget
fails. Raising a number is a deliberate edit with a written reason in `note`, exactly like
`frontend/e2e/a11y-baseline.json`.

Measured on `02608a3`:

| Surface | n=1 | n=11 | per item |
|---|---|---|---|
| `library.list_packages` | 3 | 3 | 0 |
| `results_history.list_backtest_results` | 6 | 6 | 0 |
| `readiness_check.market_data_leg` | 2 | 12 | **1** |
| `dependency_pins.ensure_pinned_resolvers_active` | 2 | 22 | **2** |
| `agent_workspace.list_tasks` | 1 | 1 | 0 |
| `audit_log.list_audit_events` | 1 | 1 | 0 |

The two non-zero slopes are **open defects, recorded not blessed** — see §7.

### Why counting one table was not enough

`tests/integration/test_readiness_query_count.py` pins Ready Check's
`market_dataset_revision` read at exactly one and asserts it does not grow. That is true,
and it is also how the residual N+1 survived: the test filters statements to that one
table, so the `get_dataset_root` call in the same item loop was never counted. The budget
gate filters nothing.

### Adding a surface

Add the seed/run pair to `test_query_budgets.py`, add its name to
`test_every_registered_surface_has_a_budget`, run once with a deliberately loose budget,
and copy the printed numbers in. Budgets are **measured**, never estimated.

---

## 4. The load driver — `scripts/loadgen.py`

One framework, no new dependency: `asyncio` + `httpx`, already in
`backend/pyproject.toml`. Modes:

```bash
# Offline — every scenario still exists in the published schema.
uv run python ../scripts/loadgen.py --check-catalogue

# Against a running stack (session auth).
uv run python ../scripts/loadgen.py \
  --base-url http://localhost:8000 \
  --login-username perf_admin --login-password "$PASSWORD" \
  --profile full --concurrency 16 --repeats 40 --out baseline.json
```

`--actor <id>` runs against a dev-auth stack instead. There is no anonymous mode on
purpose: a run that authenticated as nobody would publish the 401 path's latency as the
page's latency.

**Collected per scenario:** request count, status histogram, transport errors, throughput,
bytes received, and p50/p95/p99/max/mean latency. Percentiles are **nearest-rank** — every
printed number is a request that really happened.

**Collected once per run:** a before/after diff of the application's own credentialed
`/metrics` exposition (request counters, the duration histogram, in-flight gauge, queue
depth per queue/status, outbox lag, oldest lease age), and an SSE probe over
`/api/v1/events` reporting connects, reconnects, transport disconnects and time to first
line. A reconnect is a real signal: the whole event taxonomy rides one long-lived stream,
so a stream that drops under load is user-visible even when every polled endpoint is 200.

---

## 5. Operational targets

**Not canon.** Nothing in `docs/spec` sets these; they are recorded so an operator has
something to compare a nightly artifact against, and so a future SLO discussion starts
from measurements rather than from nothing.

| Signal | Operational target | Basis |
|---|---|---|
| Errors in a load run | **0** | the only hard, non-noisy latency-adjacent gate; already enforced |
| SSE reconnects in a 15 s window | 0 | a healthy stream survives its own window |
| Interactive read p95, `github-ubuntu-latest` | to be filled from the first nightly artifacts | deliberately blank rather than guessed |
| Queue depth after a read-only run | 0 | read scenarios enqueue nothing; anything else means a leak |

The p95 row is **empty on purpose**. Writing a number before the nightly job has ever run
would be exactly the arbitrary target this slice was told not to invent.

---

## 6. Activating the ratio gate

`scripts/loadgen.py --compare <baseline.json> --max-ratio <r>` is implemented and unit
tested (`backend/tests/unit/test_loadgen.py`). It compares each scenario's p95 **in units
of the within-run control** (`meta`: unauthenticated, no DB read), so a machine that got
uniformly slower passes and application work that grew against a steady control fails.

It is **not wired into CI yet**, and that is a measurement decision, not an oversight.
Two back-to-back full runs against an unchanged stack on the development laptop moved the
control by 4.4x and several scenarios by 3-5x even after normalization. Choosing a band
from that would be picking a number out of the air.

Procedure to turn it on:

1. Let `load-full` run nightly and collect **at least five** `loadgen-baseline` artifacts
   from the same runner class.
2. For each scenario compute the control-normalized p95 across those runs and take the
   observed max/min spread.
3. Commit the median run as `docs/performance/baseline_ci.json` and set `--max-ratio` to
   roughly **1.5x the observed spread** — derived from data, recorded here with the data.
4. Add `--compare docs/performance/baseline_ci.json --max-ratio <r>` to the `load-full`
   step. Keep it on the nightly job, not on PRs.
5. If step 2 shows the spread is wide enough that no useful band exists, say so here and
   leave the gate off. An honest "we cannot gate this on shared runners" is a result.

---

## 7. Open findings this measurement produced

| # | Surface | Cost | Status |
|---|---|---|---|
| [#617](https://github.com/alimirbagirzade/Entropia/issues/617) | Ready Check market-data leg | 1 extra round trip per Strategy item | open — batch `get_dataset_root` |
| [#618](https://github.com/alimirbagirzade/Entropia/issues/618) | Approve Package pinned-resolver re-validation | 2 round trips per pin | open — batch both reads |

Both were found by the budget gate on the run that introduced it, and both are recorded
in `query_budgets.json` rather than repaired: the slice that measures should not also be
the slice that changes a fail-closed admission path. Each issue names the acceptance —
tighten the budget row to `per_item: 0` — so the fix and its proof arrive together.

---

## 8. What is NOT measured (honest boundary)

Repeated in every report's `not_measured` block so no artifact can read as fuller
coverage than the run had.

* **Ready Check and Run admission latency.** Both mutate; driving them per repeat would
  measure the seeding. Their DB cost is gated deterministically instead
  (`query_budgets.json`, `tests/integration/test_backtest_query_count.py`).
* **Worker time.** Ingest, import, validation, backtest, export and Agent worker
  durations are not observable from an HTTP client. The run reports the queue-depth and
  oldest-lease-age gauges the API exposes; per-actor timing needs worker-side
  instrumentation that does not exist yet.
* **API memory and CPU.** Not exposed by the application. The nightly job captures
  `docker stats` before and after and uploads it beside the JSON rather than having the
  driver guess.
* **Object storage I/O and artifact sizes.** No read scenario fetches an artifact, so the
  run says nothing about them.
* **Unified portfolio performance.** `SHARED_ALLOCATION_STATUS` is `future_dev` and
  containment is closed, so there is no production entry point to drive (GitHub #582).
* **Frontend rendering.** Bundle size and interaction latency are the browser's story;
  this directory is the server's.

---

## 9. Files

| File | What it is |
|---|---|
| `query_budgets.json` | the ratchet the PR gate reads |
| `baseline_local_2026-08-06.json` | a `full` run on the development laptop, base `02608a3`. Reference for shape, **not** a CI baseline |
| `baseline_ci.json` | not present yet — produced per §6 |
