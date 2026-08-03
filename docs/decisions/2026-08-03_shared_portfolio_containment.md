# Containment decision record — shared capital allocation (ADIM 3)

- **Date:** 2026-08-03
- **Base:** `origin/main` @ `948b6fb`
- **Branch:** `fix/portfolio-shared-mode-containment`
- **Status:** ACTIVE — temporary, removal conditions in §6
- **Canonical gap it contains:** `docs/audit/current_main_ground_truth_2026-08-03.md` §9 **G-05**
  ("Shared Equity Allocation = sequential approximation, unified clock YOK")

---

## 1. Decision

While the engine has no unified-clock multi-item co-simulation, an **enabled shared
capital allocation plan is fail-closed**: it raises a typed blocker, cannot be frozen
into a plan revision, and can never be admitted for a Backtest Run. **Independent
capital mode is untouched and remains fully supported.**

No already-persisted Result is modified, deleted or re-interpreted.

## 2. What is the canonical requirement (spec), and what actually ships

**Canonical — doc 13 §8.3 (formulas + the load-bearing sentence), §8.4 steps 3-7, §13
(normative implementation rule), §14 acceptance test 11:** at a given timestamp the
engine resolves mandatory stop/exit/funding/fee events first and then produces
**ONE portfolio valuation snapshot**; every active item forms its entry/scale intent
against that same snapshot. `E(t) = P0 + realized_pnl(t) − fees(t) − funding(t) −
realized_costs(t)`, `A(t) = max(0, E(t) − R0)`, `Ci(t) = A(t)·wi/100`. The result must
not depend on DOM row order, browser timing or request arrival order. Nothing in
doc 13 authorises an approximation.

**Shipped:** `application/jobs/backtest_engine.py` loops over **items, not
timestamps**. Each item replays its own bar axis against its own `_Ledger` seeded from
the full pool P0, and `domain/backtest/execution/portfolio.py::combine_item_runs`
concatenates the finished runs' realized-PnL progressions in manifest pin order.

## 3. Empirical reproduction (this is why, not an opinion)

Pinned as executable tests in `backend/tests/unit/test_shared_allocation_containment.py`.

**(a) The composite "portfolio equity curve" is not a time series.** Two items whose
trades interleave in wall-clock time (A at 01:00 / 04:00, B at 02:00 / 03:00) produce a
curve whose points come out in ITEM order: `01:00, 04:00, 02:00, 03:00`.

**(b) The financial consequence is a wrong number, not a cosmetic one.** Folding A
whole and then B walks `10000 → 13000 → 11000 → 8000 → 11000` and reports
`max_drawdown = 5000.00`. Replaying the SAME four closes on one clock walks
`10000 → 13000 → 10000 → 13000 → 11000` and reports `3000.00`. The shipped path
**overstates the portfolio drawdown by 66%**, and `max_drawdown_pct` / `romad` are
derived from it.

**(c) There is no cross-item state at all.** `resolve_allocation_execution` hands
EVERY item the full pool P0; `AllocationExecution` carries capital, reserve,
compounding and the item's own share and nothing about any sibling. Under
`COMPOUND_PORTFOLIO_EQUITY` an item's sleeve therefore compounds off its own equity
and can never see another item's PnL, fees or funding — the pool is shared in name only.

**A real unified clock does NOT already exist**, so §2 of the mandate ("if it exists,
prove it and stop") does not apply.

## 4. Canonical gap vs. temporary behaviour — the separation

| | Canonical gap (permanent until the engine lands) | Temporary containment (this PR) |
|---|---|---|
| What | No unified-clock multi-item co-simulation (G-05) | Shared mode is refused before it can produce a Result |
| Where | `jobs/backtest_engine.py` outer loop; `execution/portfolio.py` fold | `domain/allocation/capability.py` + one blocker + one admission guard |
| Owner | Engine work, a product decision, out of this slice | Release closure |
| Removal | Requires the engine (see §6) | Flip `SHARED_ALLOCATION_STATUS` — **only** after §6 |

The containment **does not** attempt, approximate, downgrade or substitute the missing
simulation. It refuses.

**What changed relative to `main`'s previous position.** Before this PR the deviation
was *disclosed* (`portfolio_curve_sequential_not_unified_clock` in the immutable Result
diagnostics) but still shipped as the canonical shared-capital answer — the audit's own
words: "Sapma bildirilmiş olduğu için sessiz değil; yine de canonical sonuç gibi
sunuluyor." This PR converts disclosure into refusal. That is a product-position
change, made on explicit instruction from the release owner.

## 5. Mechanism (no new schema, no migration)

Single source of truth: **`backend/src/entropia/domain/allocation/capability.py`**
(`SHARED_ALLOCATION_STATUS = "future_dev"`). Four surfaces read it, none restates it:

1. **Validation** — `domain/allocation/rules.py::validate_allocation` leads an enabled
   plan with `SHARED_MODE_NOT_IN_BUILD` (BLOCKER, `field="enabled"`). Consequences: the
   Portfolio page shows it inline, and `create_allocation_revision` refuses the freeze.
   The draft still **saves** — authoring is preserved, execution is not.
2. **Ready Check** — `domain/readiness/validators.py` maps it to the typed
   `ALLOCATION_SHARED_MODE_NOT_IN_BUILD` under scope `portfolio_allocation`, carrying
   `remediation` + `field_path` (doc 14 §9.1). State → `not_ready`.
3. **Run admission** — `application/commands/backtest_run.py::_admit_run_body` carries
   an **independent** guard that reads `snapshot.capital_mode_snapshot` directly, so a
   run is refused even if the readiness evaluation is bypassed, regressed or replaced.
   It runs before `build_run_manifest`, so no run / manifest / job is created
   (doc 15 §9.3). Every path funnels through it: request + retry, human + Agent.
4. **UI** — `queries/allocation_plan.py::get_allocation_draft` publishes
   `shared_mode_capability`; `pages/Portfolio.tsx` renders it verbatim. The toggle and
   every field stay interactive: a disabled control is presentation, never
   authorization — the refusal is server-side.

**No migration — verified, not assumed.** `readiness_issue.code` is `String(64)` with
no CHECK constraint (`infrastructure/postgres/models/readiness.py:88`) and the new
value is 35 characters. `readiness_issue.scope` IS an enum column, but the containment
reuses the existing `portfolio_allocation` member rather than adding one.
`AllocationIssue.code` is an in-memory value object that reaches the client as JSON,
never a column. The API field is additive on an already-untyped `dict[str, Any]`
response, so `docs/openapi.json` is unchanged — regenerated and diffed: no drift,
196 operations.
`ENGINE_VERSION` is deliberately **not** bumped — no executed behaviour changed; the
containment only prevents execution.

## 6. Removal conditions

`SHARED_ALLOCATION_STATUS` flips back to `active_v1` **only** when all six hold:

1. the engine's outer loop is the MERGED timestamp axis of all active items, not the item list;
2. ONE shared ledger holds `P0`, the fixed nominal reserve `R0 = P0·r` and the unallocated `U0`;
3. at each valuation point mandatory stop/exit/funding/fee resolve FIRST, then exactly
   ONE `E(t)` is published and every active item sizes `Ci(t) = max(0, E(t) − R0)·wi/100`
   against THAT snapshot (doc 13 §8.3);
4. conflict/exposure arbitration is symmetric with deterministic id-based tie-breaking,
   and a blocked item's share is never transferred (doc 13 §8.4.6, §13);
5. doc 13 §14 acceptance test 11 passes and the composite equity curve is time-ordered
   by construction — i.e. `test_composite_portfolio_curve_is_not_time_ordered` must be
   rewritten as its positive counterpart, not deleted;
6. `ENGINE_VERSION` is bumped so no sequential-era Result is ever idempotently reused
   for a unified-clock re-RUN (INF-04/INF-05).

**On the "ADIM 20 unified oracle gate".** The mandate asks the removal condition to be
tied to that gate. That label is the requester's roadmap name and **this repository does
not define it**: `docs/audit/current_main_ground_truth_2026-08-03.md` §18 lists slices
1-8 with no ADIM 14-20, and records unified-clock co-simulation as a confirmed gap
"requiring a product decision, outside this audit's scope". The six conditions above are
therefore stated concretely here rather than deferred to a name the repo cannot check.
When the ADIM 20 gate is defined in-repo, it should reference this section, not replace it.

## 7. Historical results

Immutable and untouched. A pre-containment shared-pool Result keeps its stored
`diagnostics.composition.capital_allocation = "shared_pool"` and its
`portfolio_curve_sequential_not_unified_clock` warning byte-for-byte; nothing is
rewritten, re-derived or suppressed (pinned by
`test_a_legacy_shared_pool_result_stays_readable_and_unmodified`). At READ time the
raw tokens are now given honest labels naming them as the legacy sequential
approximation (`frontend/src/lib/backtest.ts::diagnosticWarningLabel`), instead of
reaching the user as bare machine strings (audit G-07).

## 8. Known coverage reduction (honest boundary)

Three behaviours can no longer be exercised through an admitted run, because no
admitted shared run exists any more:

- the worker capitalising a run from the pinned pool `P0` — the sizing arithmetic
  itself stays covered by `tests/unit/test_backtest_engine_allocation.py`;
- the portfolio rules (`max_total_exposure_percent`, `conflict_policy`) surviving into
  a **frozen** plan revision — the draft round-trip is still asserted, and the freeze
  refusal is now asserted instead;
- RC-03's original fixture (unallocated-cash warning on a shared plan) — RC-03 now
  rides on the strategy-scoped `EXECUTION_ASSUMPTIONS_DEFAULT` warning, and the
  now-unreachable allocation-warning path is pinned by
  `test_shared_allocation_warning_path_is_now_fail_closed`.

Removing the containment must restore these, not silently leave them behind.
