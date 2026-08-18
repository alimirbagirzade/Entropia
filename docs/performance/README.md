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
| **Latency ratio** | `performance.yml` -> `load-full`, `--compare docs/performance/baseline_ci.json --max-ratio 2.5` | no (nightly) | each scenario's p95 in units of the within-run control, against the frozen baseline. **Armed 2026-08-12** — see §6 |
| Browser rendering | `e2e.yml` -> `lighthouse` | **yes** | Lighthouse category scores per route, ratcheted. Not this directory's subject — see §8 |

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
| Interactive read p95, `github-ubuntu-latest` | **still unset — a product decision, not this directory's** | six nightlies now exist and the observed range is recorded below, but an *observation* is not a *target*. `backend/tests/contract/test_alert_rules_contract.py` holds the alerting side to the same line: no rule may invent an absolute latency bound |
| Queue depth after a read-only run | 0 | read scenarios enqueue nothing; anything else means a leak |

The p95 row is **still empty on purpose**, and the reason has changed — so it is restated
rather than left to read as the old one. It was blank because nothing had been measured;
that is no longer true. On the frozen baseline (`baseline_ci.json`, 2026-08-11, warm
phase, 16 comparable read scenarios) the observed p95 runs **307.5 ms to 477.9 ms, median
404.7 ms**, against a control of 193.5 ms. Those are **observations**, recorded here so a
future SLO discussion starts from numbers. Promoting one of them to a target is a product
decision nobody has taken, and taking it inside a CI slice would be inventing canon —
`docs/spec/01..22` still set no latency target at all.

What *is* now enforced from these runs is the **ratio** gate in §6, which needs no
absolute target: it asks whether the application's own cost moved, not whether it is fast.

---

## 6. The ratio gate — ACTIVATED 2026-08-12 (RC §6.7 / P10-7)

`scripts/loadgen.py --compare <baseline.json> --max-ratio <r>` is implemented and unit
tested (`backend/tests/unit/test_loadgen.py`). It compares each scenario's p95 **in units
of the within-run control** (`meta`: unauthenticated, no DB read), so a machine that got
uniformly slower passes and application work that grew against a steady control fails.

It shipped **unwired**, and that was a measurement decision, not an oversight: two
back-to-back full runs against an unchanged stack on the development laptop moved the
control by 4.4x and several scenarios by 3-5x even after normalization. A band chosen
from that would have been a number out of the air. The five-step procedure below was
written to replace the guess with data. All five steps have now been executed.

### What the procedure asked for, and what it produced

| Step | Asked for | Result |
|---|---|---|
| 1 | at least five `loadgen-baseline` artifacts from one runner class | **six**, 2026-08-07..08-12, all `github-ubuntu-latest`, all 16/40, all zero errors |
| 2 | control-normalized p95 spread across those runs | worst max/min spread **1.92x** (`hypotheses`); worst ratio against the frozen baseline **1.62x** (`admin_logs`) |
| 3 | commit the median run, set `--max-ratio` to ~1.5x the spread | `baseline_ci.json` = run 31461912952 (2026-08-11, `4e9512d2`); `1.5 x 1.62 = 2.43` -> **`--max-ratio 2.5`** |
| 4 | add `--compare` to `load-full`, nightly only | done — `performance.yml`, `load-full` -> "Full load run". `load-smoke` deliberately untouched |
| 5 | if no useful band exists, say so and leave it off | **not taken.** The band clears every observed night with 1.54x headroom and still fails a 3.0x regression |

Raw measurements and the full replay:
`docs/releases/evidence/2026-08-12/p10_7_nightly_baselines.md`,
`p10_7_control_normalised_spread.txt`, `p10_7_ratio_gate_replay.txt`.

### Where the baseline lives (and why the clock cannot reset)

Two lifetimes, and only one of them needs to be long:

* the nightly **artifact** (`loadgen-baseline`, 30-day retention) is the *input* — it
  only has to survive long enough to be read once;
* the gate's **baseline is a tracked file** in this directory. Once committed, the gate
  no longer depends on artifact retention at all.

A nightly that produces no artifact is announced by `performance.yml`'s
`nightly-failure-notice` rather than quietly not counting. And a scheduled run cannot be
cancelled by the next one: `cancel-in-progress` is
`${{ github.ref != 'refs/heads/main' }}`, and on a `schedule` event `github.ref` **is**
`refs/heads/main`. That was checked against six consecutive run logs, not assumed.

### What this gate does NOT catch (stated, not hidden)

* **Anything under 2.5x.** A regression between the observed 1.62x weather and the 2.5x
  band merges and stays. The band is wide because six samples cannot bound a tail;
  narrowing it is a later decision with more nights behind it, made here with the new
  numbers — never an edit made to silence a red nightly.
* **Anything on a PR.** The gate is nightly. A latency regression merges green and is
  caught the next morning. That is §1's trade, made deliberately.
* **Any other runner class.** §2 already forbids the comparison.

The band is pinned in three places that must agree — `performance.yml`'s `--max-ratio`,
`_OBSERVED_WORST_RATIO`/`_BAND` in `backend/tests/unit/test_loadgen.py`, and this section.
`test_the_nightly_actually_passes_the_band_this_file_pins` fails if they drift apart, so
widening the band in the workflow alone is not possible.

---

## 7. Open findings this measurement produced

| # | Surface | Cost | Status |
|---|---|---|---|
| [#617](https://github.com/alimirbagirzade/Entropia/issues/617) | Ready Check market-data leg | 1 extra round trip per Strategy item | open — batch `get_dataset_root` |
| [#618](https://github.com/alimirbagirzade/Entropia/issues/618) | Approve Package pinned-resolver re-validation | 2 round trips per pin | open — batch both reads |

Both were found by the budget gate on the run that introduced it, and both are recorded
in `query_budgets.json` rather than repaired: **the slice that introduces the gate**
should not also be the slice that changes a fail-closed admission path. Each issue names
the acceptance — tighten the budget row to `per_item: 0` — so the fix and its proof
arrive together.

### That rule is about the *measuring* slice, not a ban on ever repairing admission

Stated because P4 has now done both halves in one slice and the sentence above, read
alone, would forbid it. The rule's subject was always the slice that **shipped the
counter**: it had every surface's first number in hand at once, and repairing a
fail-closed path in the same change would have left no independent measurement of the
before-state to check the repair against. A *later*, single-surface slice is the opposite
situation, and the acceptance those issues name — tighten the row to `per_item: 0` — only
has meaning if some slice eventually does both.

What a slice touching admission owes instead is the evidence the measuring slice would
have lacked, and P4 (`backtest_run.admission_tick_pins`) is the worked example:

* the row lands at its **measured pre-repair slope first** (3 → 23, `per_item: 2`), so
  the before-state is recorded as a fact rather than reconstructed from a diff;
* the fixture is shown to actually **execute** the leg before any number is believed —
  this leg is fail-closed and skips every strategy that does not demand tick data, so a
  green `0` is equally consistent with "batched" and "never ran";
* behaviour parity is proved separately from cost (`test_backtest_tick_pin_batch.py`):
  the 422 keeps its code and both promoted envelope fields and still names the first
  failing item in **manifest order**, and — because the pinned revision id enters the
  immutable manifest — the batch is shown to pick the same row as the per-item reader
  against a deliberate equal-`created_at` tie;
* the negative control runs against a **pristine** file, and runs once per batched read
  rather than once for the pair, so neither can be decoration.

Leg 3 of Ready Check (`_resolve_external`) is still not repairable on these terms and is
still unscheduled: there the per-item winner is undefined, so no fixture can pin "the
same row" and the change is a product decision (gate G15), not a performance one.

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
* **Frontend rendering — still not measured HERE, but no longer unmeasured anywhere.**
  Since RC §6.7 / P11-8 there is a Lighthouse ratchet (`e2e.yml` -> `lighthouse`,
  `frontend/e2e/lighthouse-baseline.json`) scoring every audited route in a real
  browser. **The two are not rivals and must never be cited for each other:** this
  directory answers *"did the server's own work get more expensive?"* — per-endpoint HTTP
  p95, control-normalised, nightly. Lighthouse answers *"did the page get slower to
  paint and become interactive?"* — FCP/LCP/TBT/CLS rolled into a category score, per
  route, per PR. A green nightly says nothing about a bundle regression, and a green
  Lighthouse score says nothing about a query that doubled. The sentence below is the
  original boundary and still holds for what this driver measures.
  this directory is the server's.

---

## 9. Files

| File | What it is |
|---|---|
| `query_budgets.json` | the ratchet the PR gate reads |
| `baseline_local_2026-08-06.json` | a `full` run on the development laptop, base `02608a3`. Reference for shape, **not** a CI baseline |
| `baseline_ci.json` | **the armed ratio gate's frozen baseline.** The median of six nightlies, run 31461912952 / 2026-08-11 / `4e9512d2`, `github-ubuntu-latest`, 16 in flight x 40 passes, zero errors. Replacing it re-bases every future comparison, so it is changed only with a new §6 measurement behind it |
