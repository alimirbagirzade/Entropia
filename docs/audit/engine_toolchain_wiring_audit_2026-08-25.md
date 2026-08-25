<!-- doc-status: historical -->

# Engine ↔ toolchain wiring audit (2026-08-25)

> **What this is.** A READ-ONLY trace of whether the backtest engine is actually connected
> to the rest of the product — Create Package, the ESP resolver registry, Strategy pinning,
> Ready Check and the durable run path — and of what a user-created indicator can and
> cannot make it do. Asked as: *"does it work, and will it work correctly?"*
>
> Every claim was re-derived from the tree or from a command executed in this session.
> `CLAUDE.md`, prior audits and PR bodies were treated as **hypotheses to falsify**.
>
> **This document FREEZES the moment it measured.** Re-derive before trusting it.

## 1. Verdict

**The engine is fully wired and does execute user-created indicators — in INDEPENDENT
mode.** There is no broken link in that chain. The shared-capital portfolio mode is
wired but does not execute, deliberately.

One genuine defect was found, and it is **not** a mis-computation: it is a
**boundary that is enforced late** (§4).

## 2. The chain, end to end

| Step | Symbol / location |
|---|---|
| HTTP admission | `apps/api/routes/backtest.py:199-203` → `job_enqueue.send_job(run_backtest_engine, job_id)` |
| dramatiq actor | `apps/worker/actors.py:178` → `:198` → `run_backtest(session, job_id)` |
| pin resolution | `jobs/backtest_engine.py:875` → `resolve_indicator_plan(session, config)` |
| ← source of truth | reads `PackageRevision.dependency_snapshot` from Postgres (`queries/indicator_plan.py`) |
| engine entry | `jobs/backtest_engine.py:960` → `run_engine(...)` |
| evaluator build | `engine.py:1194, 1197, 1204, 1213` → `build_evaluators(entry/exit/stop/scale specs)` |
| **per-bar advance** | `engine.py:2015-2022` → `ev.update(close, high, low, open, volume=…, timestamp=…)` |
| **per-bar signal** | `engine.py:2023-2025` → `aggregate(rule, evals)` |

No link is missing. A pinned indicator package **is** read from the database, expanded into
an `IndicatorPlan`, and stepped on **every bar**.

## 3. What the engine can actually compute

Measured by importing the module, not by reading prose:

| Set | Keys |
|---|---|
| Directional (computes **and** yields a signal) | `ta.ema` `ta.rma` `ta.rsi` `ta.sma` `ta.vwap` `ta.wma` |
| Recognized, **non-directional** (no signal, by design) | `ta.atr` |
| Condition primitives | `cond.above` `cond.below` `cond.between` `cond.crosses_above` `cond.crosses_below` |

The ESP registry seed (`apps/seed.py::_ESP_TA_RESOLVERS`, `::_ESP_COND_RESOLVERS`) contains
**7 TA + 5 condition** entries. Cross-checking the two sets: the only registry entry with no
directional compute is **`ta.atr`**, and that is intentional — it is a volatility band width,
not a directional line (`indicators.py:63-66`).

**Fail-closed is real.** An unresolvable block does not run with an empty signal: it becomes
`STRATEGY_INDICATOR_UNRESOLVED` at **BLOCKER** severity (`commands/readiness_check.py:716-737`),
and `commands/backtest_run.py:523-526` turns any blocker into `422 READINESS_BLOCKED` with the
whole transaction rolled back — no run, no manifest, no job. The system refuses to compute
rather than compute wrongly.

## 4. FINDING — the computability boundary is enforced only at the LAST step

**Shape.** Three surfaces decide what an indicator may be, and they do not agree on the
question they ask:

| Surface | What it checks | Location |
|---|---|---|
| ESP resolver registration | `canonical_key` is **non-empty**. Nothing else. | `commands/esp.py:127` |
| Create Package candidate | the key **prefix** is `ta.` / `cond.` | `domain/create_package/candidate.py:117-128` |
| Create Package validation | the key resolves **against the live ESP registry** | `domain/create_package/validation.py:117` |
| **Engine / Ready Check** | the key is in the engine's computable set | `queries/indicator_plan.py`, `readiness_check.py:716` |

Measured: `grep` for `RECOGNIZED_KEYS` / `DIRECTIONAL_KEYS` / `CONDITION_KEYS` under
`domain/create_package/` and `commands/esp.py` returns **nothing**. Neither surface consults
the engine's capability.

**Consequence.** An Admin registers a resolver `ta.macd` → registration succeeds → a package
built on it passes Create Package validation (the key now resolves against the registry) →
a Strategy pins it → **Ready Check blocks it**. The user's first signal that the key is not
executable arrives at the very last gate, after the package has been created, validated and
pinned.

**Why the obvious fix is wrong.** Rejecting non-computable keys at registration would break
**`ta.atr`**, which is registered on purpose and deliberately yields no directional signal.
A registry entry that the engine cannot turn into a signal is a **legitimate state**, not an
error. So the correct remedy is a *diagnostic*, not a gate.

**Disposition.** Recorded here. Product decision taken 2026-08-25: surface it as a **warning
plus early diagnosis**, never as a blocker. Implementation ships separately from this audit.

## 5. Second observation — `SEED_ESP_TA` defaults to OFF

`apps/seed.py:58` — `SEED_ESP_TA = os.getenv("SEED_ESP_TA", "0") == "1"`. In a default
deployment the ESP registry therefore carries **no** TA resolvers, and Create Package
validation (§4, row 3) resolves nothing.

This is **not** an engine defect: the engine reads `dependency_snapshot.canonical_key`
directly and never consults `EmbeddedResolverRegistry` (measured — the registry's only
readers are `commands/esp.py`, `queries/esp.py` and `jobs/package_import.py`). It is a
deployment-configuration fact, recorded so an operator provisioning a fresh environment
knows the flag exists. **Not reclassified and not changed.**

## 6. Shared-capital portfolio mode — wired, not executing

`_use_unified_clock` (`jobs/backtest_engine.py`) is the single branch point:

```python
return shared_allocation_is_executable() and shared_allocation_requested(capital_execution)
```

`shared_allocation_is_executable()` is `SHARED_ALLOCATION_STATUS == "active_v1"`
(`domain/allocation/capability.py:154`) and the value is `future_dev` (`:105`). **No
production run reaches `_EngineParticipant` today.** Multi-item runs do work — in
*independent* mode, each item on its own capital.

What stands between here and that flag moving is **not code**: `G8` (#559) · `G14` (#544) ·
`G11`+`G12` (→ `C6`) · `G15`; `G10` was never requested. This audit did not touch the flag,
the containment gate, or any signature block.

## 7. Evidence executed in this session

| Command | Result |
|---|---|
| `pytest tests/unit/ -k "engine or indicator or strategy" -q --no-cov` | **EXIT=0**, 352 passed |
| `pytest tests/unit/test_backtest_indicators.py …vwap…indicator_vs_indicator…condition_extensions -q --no-cov` | **EXIT=0**, 58 passed |
| `pytest tests/unit/test_backtest_engine_golden.py -q --no-cov` | **EXIT=0**, 50 digest scenarios, file byte-identical |
| `pytest tests/integration/test_backtest_persistence.py -q --no-cov` | **EXIT=0**, 26 passed, **0 skipped** (live Postgres 16) |

Postgres 16 was provisioned in this container (`pg_ctlcluster 16 main start`, role/db
`entropia`), so the integration result above is a real run against a real database, not a
skip. The **full** integration package was started but had not finished when this document
was written — no total is claimed for it. **CI is the authority** for full-suite passes and
coverage.

## 8. What this audit did NOT do

Changed no production line, no test, no golden digest, no ratchet, no baseline, no feature
flag, no issue state. Did not run the frontend gates. Did not reclassify any acceptance-debt
row. The §4 finding is recorded, not silenced — and not fixed in this document.
