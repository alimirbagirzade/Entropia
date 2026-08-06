<!-- doc-status: historical -->
> **HISTORICAL RECORD — bu belge GÜNCEL GERÇEK DEĞİLDİR.** Yazıldığı andaki durumu
> kaydeder; SHA'lar, sayılar, alembic head'i ve "next" maddeleri bayat olabilir.
> Güncel otorite: `CLAUDE.md` §Current position + `docs/generated/repository_facts.md`
> (üretilmiş, CI'da `--check` ile kapılı).

# Unified portfolio oracle acceptance — ADIM 20 gate report

> ## ADDENDUM — ADIM 18, 2026-08-05 (`feat/stage-18-run-portfolio`)
>
> **This report was written on `b0bb4a0`, before `run_portfolio` existed. Three of its rows are
> now out of date and are corrected below; everything else still holds.** The body is left
> intact rather than rewritten, because §1's reproduction is the evidence that the gap was real
> when it was measured.
>
> **What changed:** the phase loop shipped as `domain/backtest/portfolio_engine.py::run_portfolio`
> and the 25 oracles were re-pointed at it **unchanged** — the exact substitution §2's honest
> boundary named as the acceptance evidence ADR §14 asks for. **A1, A3 and A5 move from
> PRIMITIVE/BLOCKED to MET** (see the corrected rows in §3). A2, A6–A12 and A18 remain
> PRIMITIVE for one reason only: they are now proven *in the shipped loop*, but the shipped loop
> has **no production caller**.
>
> **What did NOT change:** `SHARED_ALLOCATION_STATUS` is still `future_dev`;
> `ENGINE_VERSION` is unchanged; no migration, no OpenAPI, no manifest field; the worker still
> loops over items (`jobs/backtest_engine.py:298`) and folds with `combine_item_runs` (`:363`).
> Wiring it needs an `ItemParticipant` backed by the real engine — ADR §12's skipped ADIM 16
> stepper. §1's probe row for that stepper is **still accurate**.
>
> **§6's human gates are discharged:** ADR 0002 is **`Accepted`** (2026-08-05); OD-1…OD-7 are
> resolved to their recommendations in the new ADR **§13.1** amendment table; §12's numbering is
> corrected and ADIM 16 formally SKIPPED. Two policy *labels* in code still read `pending`
> (`MARK_STALENESS_POLICY`, `CONTENTION_SELECTION_STATUS`) — deliberately, per §13.1: they are
> published only through `build_portfolio_manifest`, which ADIM 20 owns.
>
> The gate test named in §1 was **rewritten, not deleted**:
> `test_no_unified_clock_driver_exists_in_production_on_this_commit` →
> `test_the_phase_loop_exists_but_no_production_path_reaches_it`.


**Base:** `origin/main` @ `b0bb4a0` (PR #581, ADIM 19 provenance) · **Branch:**
`test/portfolio-unified-oracles` · **Date:** 2026-08-05 · **Alembic head:**
`0043_i08_registry_strategy_fks` (single head, unchanged) · **Migration:** none ·
**OpenAPI:** unchanged · **`ENGINE_VERSION`:** unchanged
(`backtest-engine-v18-gap-adjusted-stop-fill`).

> **Outcome: the containment is NOT lifted.** `SHARED_ALLOCATION_STATUS` stays `future_dev`.
> The stopping condition in the ADIM 20 brief is met — see §1. This PR adds the acceptance
> suite the lift will need and records, empirically, what is still missing.

---

## 1. Why the lift cannot proceed — the reproduction, before any code was written

The brief requires reproducing current behaviour before writing anything. The reproduction is
not "an oracle failed": it is that **the system the oracles are supposed to accept does not
exist on this commit.**

| Probe | Result |
|---|---|
| `grep -rn "def run_portfolio" backend/src` | no match — ADR §12 ADIM 18's entry point was never written |
| importers of `execution.{clock,intents,portfolio_ledger,arbitration,attribution,provenance}` outside `execution/` | none |
| `application/jobs/backtest_engine.py:298` | `for prepared in prepared_items:` — the outer loop is still the ITEM list |
| `application/jobs/backtest_engine.py:363` | `combine_item_runs(...)` — finished runs are still folded in pin order |
| resumable per-item stepper (ADR §12 **ADIM 16**, a pure refactor) | **never written** — no stepper in `engine.py` or `execution/state.py` |
| `ENGINE_VERSION` | unchanged; `execution_key` namespace has not shifted |
| `manifest.py` policy fields (`clock_policy_version`, `arbitration_policy_version`, `engine_allocation_policy_version`, `mark_staleness_policy`) | absent |
| ADR 0002 status | **`Proposed`** — §16 makes approval a precondition for *any* implementation slice |

The six unified-clock modules that landed as ADIM 15–19 are a **detached island**: complete,
heavily unit-tested primitives (216 tests) that nothing calls. Every removal condition in
`domain/allocation/capability.py` §REMOVAL that speaks about *the engine* (#1 outer loop, #3
one `E(t)` reaching sizing, #5 doc 13 §14 test 11 in the shipped path, #6 `ENGINE_VERSION`) is
therefore unsatisfied **by construction**, not by a failing assertion.

Pinned as executable evidence in
`backend/tests/unit/oracles/test_oracle_portfolio_containment_gate.py`.

## 2. What this PR adds

A **multi-tick, multi-item** oracle suite. The 216 existing tests over the six modules are all
single-tick or single-module; nothing ran clock → intents → ledger → arbitration together over
a portfolio's lifetime, which is exactly where the contained defect lives.

| File | Tests | Covers |
|---|---|---|
| `tests/unit/oracles/portfolio_harness.py` | — | the ADR §8.2 phase loop (P1 → P3 → PV → P4 → P5/P6b → P7 → P9) over the shipped primitives; inputs and sequencing only |
| `tests/unit/oracles/test_oracle_portfolio_clock.py` | 10 | one valuation per tick, mandatory-before-PV, time-ordered curve, no-lookahead across a run, heterogeneous timeframes contending for one pool, caller-order invariance, batch invariance, load sanity (12 items × 72 ticks) |
| `tests/unit/oracles/test_oracle_portfolio_capital.py` | 11 | doc 13 §14 test 10 split, fixed `R0` across a drawdown, compound vs fixed on one fixture, joint insolvency, no share transfer, exposure cap, opposite-direction conflict, NET fail-closed, accounting identity per tick, per-item reconciliation |
| `tests/unit/oracles/test_oracle_portfolio_containment_gate.py` | 4 | 5000 (sequential) vs 3000 (unified) on one trade set; the four gate facts of §1 |

Every expected figure is a hand-derived literal from doc 13 / Modül 11 / ADR 0002. No engine
arithmetic helper builds an expectation.

**Non-vacuity was verified**, not assumed: perturbing four load-bearing literals
(`3000.00` → `5000.00`, sleeve `3500.00` → `4500.00`, compound `2500.00` → `4500.00`,
rejected `0` units → `5`) failed exactly those four tests and no others.

### Honest boundary — read before trusting a green run

The phase loop these oracles drive is **test-owned**, because `run_portfolio` does not exist.
A green run is evidence about the **primitives**, not about the shipped engine, which never
calls them. When ADIM 18 lands, `portfolio_harness.simulate` must be replaced by
`run_portfolio` and these oracles re-run unchanged — **that substitution is the acceptance
evidence ADR §14 asks for, and nothing here substitutes for it.**

## 3. ADR §14 acceptance matrix — status on this commit

Legend: **MET** · **PRIMITIVE** (proven for the modules; unreachable in production) ·
**BLOCKED** · **N/A-YET** (trivially true only because nothing is wired).

| # | Criterion | Status | Evidence |
|---|---|---|---|
| A1 | Outer loop is the merged timestamp axis | **MET in the loop / no caller** *(ADIM 18)* | `portfolio_engine.py::run_portfolio` iterates `iter_ticks(...)`, never the item list; the 25 oracles run on it. The worker does not call it — `test_the_phase_loop_exists_but_no_production_path_reaches_it` |
| A2 | Exactly one ledger holds `P0`/`R0`/`U0` | **PRIMITIVE** | `ledger_for_items` drives all items in the oracle suite; production shared path still seeds a per-item `_Ledger` from the full pool |
| A3 | Mandatory events first, then exactly one `E(t)` every item sizes against | **MET in the loop** *(ADIM 18)* — the order is now structural: `publish_snapshot` freezes the ledger and `arbitrate` refuses an unfrozen one | `test_a_stop_that_fires_at_a_tick_shrinks_its_siblings_sleeve_at_that_same_tick`, `test_every_item_at_a_tick_sizes_against_exactly_one_published_valuation` |
| A4 | Item order does not change the result | **PRIMITIVE** | `test_the_order_the_caller_visits_items_in_cannot_move_a_number`. ADR requires an identical **`EngineOutput` digest** under permuted `mainboard_items` — needs the real engine |
| A5 | Composite curve time-ordered by construction; the 5000 fixture reports 3000 | **MET in the loop** *(ADIM 18)* | `test_the_unified_clock_reports_the_drawdown_the_sequential_fold_overstated`, `test_the_same_trades_read_5000_sequentially_and_3000_on_one_clock` |
| A6 | Compound sleeves recompute from `E(t)` including siblings' PnL/fees/funding | **PRIMITIVE** | `test_a_siblings_loss_shrinks_the_survivors_sleeve_only_under_compounding` (2500.00 vs 4500.00) |
| A7 | Fixed mode keeps `Ci_fixed`; no auto-compounding; no silent borrow | **PRIMITIVE** | same test + `test_jointly_insolvent_entries_reject_the_later_pin_whole_and_never_trim_it` |
| A8 | Over-sleeve desire ⇒ deterministic cap/reject; item risk limits never bypassed | **PRIMITIVE** | `test_the_composition_wide_exposure_cap_clamps_the_later_pin_at_the_same_tick` |
| A9 | A blocked item's share is never transferred | **PRIMITIVE** | `test_a_rejected_items_sleeve_is_never_handed_to_the_admitted_sibling` |
| A10 | Solvency shortfall ⇒ reject whole, never partial, never borrow | **PRIMITIVE** | `test_jointly_insolvent_entries_reject_the_later_pin_whole_and_never_trim_it` (5 units available, 0 granted) |
| A11 | `R0` fixed nominal; `U0` never borrowed | **PRIMITIVE** | `test_the_reserve_stays_a_fixed_nominal_amount_across_a_multi_tick_drawdown` |
| A12 | Sleeve arithmetic exact (`3600/3150/1350`, `U0=900`) | **PRIMITIVE** | `test_the_first_valuation_publishes_doc13_acceptance_test_10` |
| A13 | 37 non-portfolio golden digests unchanged; only 9 `portfolio.*` move | **N/A-YET** | no digest moved because no engine behaviour changed; must be re-evaluated at the real ADIM 20 |
| A14 | Single-Strategy composition byte-identical | **N/A-YET** | as A13 |
| A15 | `ENGINE_VERSION` bumped; `execution_key` namespace shifted | **BLOCKED** | deliberately not bumped by this PR |
| A16 | Manifest carries sleeve amounts, FX refs and every policy version | **BLOCKED** | `test_the_manifest_carries_none_of_the_policy_fields_the_lift_requires` |
| A17 | Point-in-time integrity preserved, tests green **unweakened** | **BLOCKED** (narrowed) | `tests/integration/test_research_point_in_time_parity.py` now carries **1 `xfail(strict=True)`** — GH **#558** only, a product decision (no bundle pins the available-time policy). The three Agent-tool-gateway xfails (**#556** ×2, **#557**) were FIXED and their markers removed: `data_bundle.resolve` routes every research member through `jobs/research_data.py::admit_bundle_member` and resolves the Feature-Input-Only precondition server-side. Measured 2026-08-06: **16 passed + 1 xfail**. Still BLOCKED — "green **unweakened**" is not reached while a strict xfail stands, and the **market half of #556** (existence-only check on a pinned market revision) is still open |
| A18 | Cross-item batch invariance | **PRIMITIVE** | `test_chunking_each_items_bars_differently_cannot_move_a_number`; ADR requires an identical digest |
| A19 | Historical Results unchanged and correctly labelled | **MET** | `test_the_same_trades_read_5000_sequentially_and_3000_on_one_clock` (legacy fold and its disclosure untouched) + the existing `test_a_legacy_shared_pool_result_stays_readable_and_unmodified` |
| A20 | Rollback proven | **MET (one direction)** | containment refuses shared runs and its 9+7 tests stay green; the post-lift flip-back cannot be tested until a lift exists |
| A21 | Cancel/pause lands on a safe checkpoint | **BLOCKED** | checkpoints are still **per item** (`jobs/backtest_engine.py` O-06 checkpoint #3, "between two items' bar-replays"); no tick-based checkpoint exists |
| A22 | Full backend suite green at `--cov-fail-under=90` | see §6 | single invocation, exit code read separately |

## 4. Decision-record §6 removal conditions

| # | Condition | Status |
|---|---|---|
| 1 | Outer loop is the merged timestamp axis | **half met (ADIM 18)** — the merged-axis loop `run_portfolio` exists and is exercised; the worker still loops over items, so no *run* uses it |
| 2 | One shared ledger holds `P0`, `R0`, `U0` | **primitive only** — `PortfolioLedger` exists, nothing calls it |
| 3 | Mandatory events first, one `E(t)`, `Ci(t) = max(0, E(t) − R0)·wi/100` | **proven in the shipped loop (ADIM 18)**; still unreachable from a run |
| 4 | Symmetric conflict arbitration, id tie-break, share never transferred | **primitive proven** (A9, A10, opposite-direction conflict) |
| 5 | doc 13 §14 test 11 passes; curve time-ordered by construction | **primitive proven**; the shipped path still reports `5000.00` and `test_composite_portfolio_curve_is_not_time_ordered` still holds |
| 6 | `ENGINE_VERSION` bumped | **NOT MET** |

Decision-record **§8's three deliberate scope losses** (pinned-pool capitalisation end to end,
frozen portfolio rules on an admitted run, RC-03's original fixture) remain unrestorable while
no shared run can be admitted.

## 5. Remaining unsupported policies (must not be read as shipped after any lift)

| Policy | Status | Tracking |
|---|---|---|
| `CrossItemConflictPolicy.NET` | **fail-closed** in the unified path (`UnsupportedConflictPolicyError`); the shipped sequential engine still downgrades it to `BLOCK_OPPOSITE` and discloses `CONFLICT_POLICY_NET_V1`. Canon defines no netting price, custody, fee or PnL attribution. | GH **#544** (`blocks-adim-19`) |
| DST fold / gap on a merged mixed-zone axis | undefined; both resolve silently today | GH **#559** |
| `leverage_mode = cross` / cross-margin / portfolio liquidation | out of scope, stays `canonical_gap` after any lift | ADR §9.5 |
| FX conversion for a multi-currency shared plan | out of scope; mismatch stays a blocker | ADR OD-5 |
| Trading Signal / Trade Log execution while holding a sleeve | out of scope; ADR recommends blocking such plans | ADR OD-6 |
| `record_time_basis` honoured by the engine | field pinned, never read | ADR OD-1 |
| Mark policy for an item with no fresh bar | `MARK_STALENESS_POLICY = "undefined_pending_od2"` | ADR OD-2 |
| Which of several jointly-insolvent intents is rejected | `CONTENTION_SELECTION_STATUS = "recommended_pending_approval"` | ADR OD-3 |
| `Ci(t)` continuous cap vs entry-only; `METRIC_SET_VERSION` bump | unresolved | ADR OD-4, OD-7 |

**R-1 (§10.2 revision pinning drift) is CLOSED** — `a33d3e4 fix(readiness): pin the allocation
revision the snapshot names`; `readiness_check.py::_pinned_revision` now reads the named
revision's config.

## 6. Human gates that outrank the technical matrix — DISCHARGED at ADIM 18

All three were resolved by the PO/maintainer on 2026-08-05, before any ADIM 18 code was written.
The original text is kept below each item so the gate is readable as it was posed.

1. ~~**ADR 0002 is `Proposed`.**~~ → **`Accepted`.** §16 is rewritten as *discharged* and records
   that approval arrived **after** ADIM 15–19 had landed, rather than smoothing that over. The
   gate is not a formality and must hold for ADIM 20, the first slice to change a shipped number.
2. ~~**ADR §12's numbering does not match what shipped.**~~ → §12 is **corrected**: ADIM 16 is
   formally SKIPPED, with a shipped-vs-ADR numbering map. **The substantive loss is recorded,
   not argued away:** ADIM 16's proof obligation (46 digests unchanged) was discharged by ADIM 18
   for free, because `run_portfolio` never touches `run_engine`'s body — but when the engine-backed
   participant is written, restructure and re-price will land together and a moved digest will be
   harder to attribute than ADR §15 R-4 intended. **The follow-up must split those into two PRs.**
3. ~~**Seven open decisions (OD-1…OD-7) are unresolved.**~~ → resolved in ADR **§13.1**, each to
   its own recommendation. R-5 still binds ADIM 20: the resolutions must be recorded in the
   manifest as versioned policies before the lift, and the two `pending` code labels flipped.

## 7. Verification

Commands and results are recorded in the PR body. Targeted: `tests/unit/oracles/` (111
passed). Repo-wide: `ruff check .`, `ruff format --check .`, `mypy src`, and the full backend
suite in a single invocation with the exit code read separately.
