<!-- doc-status: historical -->

# RESOLVED-SINCE-BASELINE — the engine-backed `ItemParticipant` (27A)

> **What this is.** The STOP report that precondition 4 of the 27A task requires:
> *"Eğer gerçek production `ItemParticipant` zaten varsa STOP: RESOLVED-SINCE-BASELINE
> raporu üret; ikinci adapter yazma."*
>
> The precondition **fires**. The adapter this task specifies is already shipped, and
> so is the worker wiring the task explicitly forbids. **No production line, no test and
> no golden digest was changed by this report.** Every claim below was re-derived from
> the tree or from an executed command in this session; the branch's own summary,
> `CLAUDE.md` and the PR bodies were treated as hypotheses to falsify.
>
> **This document FREEZES the moment it measured.** Re-derive before trusting it.

## 0. Measured position

| Fact | Value |
|---|---|
| `origin/main` | `46533a76a03a69fcc973fdc8a8ec8ba0ed6c96e6` |
| Branch `claude/engine-backed-item-participant-7qeunk` | **identical to `origin/main`** (`git diff origin/main...HEAD` empty) |
| `ENGINE_VERSION` | `backtest-engine-v18-percent-sizing-per-fill-commission` (unchanged) |
| `SHARED_ALLOCATION_STATUS` | `future_dev` (`domain/allocation/capability.py:105`) |

The startup advisory reported "dal … vs main (79 dosya)". That was measured against a
**stale** `main` ref; after `git fetch origin main` the branch and `origin/main` are the
same commit. Nothing on this branch was pending.

## 1. The adapter exists, and it is production

`backend/src/entropia/domain/backtest/participant.py` — 28 KB, landed in two slices:

| Commit | PR | What it shipped |
|---|---|---|
| `2cda24f` | **#777** (`C3`/E4c) | `_EngineParticipant` + `build_engine_participant` + the two invariants |
| `3994725` | **#799** (`C4`/E5) | the worker's shared-clock branch, its cancel checkpoint, the narrowed tripwire |

It is not a stub and not test-owned:

* `application/jobs/backtest_engine.py:113` imports `build_engine_participant`;
  `:1079` **calls it**, inside the `for pinned in prepared_items:` loop.
* `_ScriptedParticipant` — the test-owned decision source this task forbids promoting —
  has **zero occurrences in `backend/src/`** (three in `tests/`, all oracle-local).
* `participant.py::_protocol_check` is mypy's structural proof that `_EngineParticipant`
  **is** an `ItemParticipant`; `settle` and `finalize` are required Protocol members, never
  `hasattr`-probed.

## 2. Every DESIGN REQUIREMENT, measured against the shipped code

| Requirement (27A) | Shipped | Where |
|---|---|---|
| owns real prepared Strategy state | ✅ | wraps the real `engine._ItemStepper`; `build_engine_participant(..., stepper=…)` |
| deterministic advance to a merged timestamp | ✅ | `_bar_for(view)` over `ItemBarStream`; the axis is the merged clock |
| **P1** carry/funding | ✅ | `carry(view) -> CarryCharges \| None` |
| **P2** pending/open fills | ⚠️ **refused, deliberately** | `_UNSUPPORTED_SHAPES` — a resting order needs `_phase_open_fills`, a phase the shared path never runs |
| **P3** mandatory exits | ✅ | `mandatory_exit(view, *, held)` |
| **P4** intent proposal after shared snapshot | ✅ | `entry(...) -> ItemIntent \| None`, via `form_intent` |
| **P7** admitted intent apply | ✅ | `settle(view, *, admitted)` |
| **P8** same-direction scaling | ⚠️ **refused, deliberately** | `_UNSUPPORTED_SHAPES` — `allow_stacking` / `replace_existing` commit capital inside `_phase_tail` with no snapshot behind them |
| **P9** valuation state export | ✅ *by design inversion* | the `PortfolioLedger` is the **single** authority for `E(t)`; the adapter MEASURES amounts off the item ledger rather than exporting a second book |
| entry evaluation must not book prematurely | ✅ | `C1`'s describe/book split — `entry` runs the pure half only; booking happens in `settle` |
| **P10** end-of-data | ✅ | `finalize(view) -> MandatoryExit \| None` |

**The two ⚠️ rows are not gaps — they are the shipped decision.** P-C2 §C.3.7 (deferred
fills) and §C.3.8 (scaling) each recommend option (a): block the shape. `participant.py`
refuses those shapes **at construction** (`UnsupportedStrategyShapeError`), which makes a
wrong shared run impossible before `C6` exists rather than merely improbable. Writing the
P2/P8 paths the 27A brief asks for would *undo* a signed decision, not complete it.

## 3. HARD INVARIANT — golden digests

**Byte-identical. Verified by execution, not by record.**

```
uv run pytest tests/unit/test_backtest_engine_golden.py -q --no-cov   → EXIT=0, 2 passed
```

`tests/unit/engine_golden_digests.json` carries **50** digest scenarios under
`engine_version = backtest-engine-v18-percent-sizing-per-fill-commission`;
`md5 = 54e57845339fcfc68f6d79049e092bec`, and `git status` on that path is empty after the
run. Independent-mode semantics are untouched.

## 4. TESTS the brief asks for, and where they already live

`tests/unit/oracles/test_oracle_engine_participant.py` — 641 lines, 14 test functions,
**23 cases, all passing** (`EXIT=0`).

| Brief's test | Shipped as |
|---|---|
| real participant against real `_ItemStepper` | `test_the_bars_the_stepper_admits_are_the_clocks_own_objects` |
| warmup / no-lookahead | `test_a_tick_the_item_has_no_bar_at_reaches_no_hook_and_books_nothing` |
| mandatory exit before snapshot | pinned **structurally**: `test_oracle_portfolio_finalize.py:37` asserts `PHASE_ORDER == ("P1","P3","PV","P4","P5","P6b","P7","P9","P10")` — P3 precedes PV |
| shared `E(t)` sizing input | `test_the_sleeve_the_engine_sizes_against_is_the_one_the_pool_published` (parametrized) |
| proposed-but-rejected entry does NOT book | `test_reconciliation_holds_when_arbitration_grants_less_than_the_item_planned`, `test_settle_refuses_a_grant_for_an_entry_the_item_never_described` |
| pending fill | `test_an_execution_shape_the_shared_clock_cannot_drive_is_refused_at_construction` (refusal is the contract) |
| scaling | same refusal case (parametrized over `_UNSUPPORTED_SHAPES`) |
| deterministic repeat | `test_oracle_properties.py::test_the_same_inputs_replayed_twice_give_the_same_ledger`; `test_oracle_portfolio_clock.py::test_a_realistic_composition_stays_conservative_and_deterministic_under_load` |
| existing `run_engine` golden suite unchanged | §3 above |

Whole oracle package re-run this session: `uv run pytest tests/unit/oracles/ -q --no-cov`
→ **EXIT=0, 148 passed**.

## 5. ACCEPTANCE, item by item

| Acceptance clause | Verdict |
|---|---|
| No test-owned decision source in the production participant | ✅ `_ScriptedParticipant` has 0 occurrences in `backend/src/` |
| No duplicate engine | ✅ exactly one `run_engine` (`engine.py:3548`), one phase loop (`portfolio_engine.py::iter_portfolio` / `::run_portfolio`), one adapter |
| No worker wiring yet | ❌ **already wired** — `jobs/backtest_engine.py:1079`, shipped by #799. Beyond baseline, not a defect; this report does not unwire it. |
| No containment lift | ✅ `SHARED_ALLOCATION_STATUS` still `future_dev`; the importer allowlist is still the ONE signed module (`test_oracle_portfolio_containment_gate.py:446`) |

The signed decisions behind the allowlist are in the tree:
`docs/decisions/closure_participant_importer_allowlist_2026-08-18.md` (Option A) and
`docs/decisions/closure_c4_worker_importer_visibility_2026-08-19.md`. The ADR amendment
the brief allows for is already in `docs/adr/0002-unified-clock-portfolio-simulation.md`
(§6 clauses 6–7, §8.2 P10, gate `G9` APPROVED).

## 6. Honest boundary — what is still NOT true

Shipped and wired does **not** mean reachable. `_use_unified_clock` is the one branch
point and it reads:

```python
return shared_allocation_is_executable() and shared_allocation_requested(capital_execution)
```

`shared_allocation_is_executable()` is `SHARED_ALLOCATION_STATUS == "active_v1"`, and the
value is `future_dev`. **The shared path therefore executes in tests only; no production
run reaches `_EngineParticipant` today.** Both conjuncts are load-bearing — either alone
silently re-prices every independent composite Result.

What remains before that flag can move is **not this adapter**, and it is not code:
`G8` (#559) · `G14` (#544) · `G11`+`G12` (→ `C6`, where P2/P8 become user-visible Ready
Check blockers) · `G15` · `G10` never requested. Ordering:
`docs/audit/final_closure_delta_audit_2026-08-25.md` §10.

## 7. What this report did NOT do

* Wrote **no** second adapter (precondition 4).
* Changed **no** production line, **no** test, **no** golden digest, **no** ratchet or
  baseline, **no** `ENGINE_VERSION`, **no** issue state.
* Did **not** re-run the full backend suite or any frontend gate — zero lines changed in
  either tree, so no passed-count and no coverage percentage is claimed here. **CI is the
  authority** for those. What IS claimed above was executed in this session and its exit
  code read separately from its output.
