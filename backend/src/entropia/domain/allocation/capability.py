"""Server-owned executability state for SHARED capital allocation (containment).

ONE canonical answer to "does shared capital allocation actually EXECUTE in this
build?", read by every surface that could otherwise disagree:

* :mod:`entropia.domain.allocation.rules` — ``validate_allocation`` raises the
  containment BLOCKER, so the Portfolio page, the plan-revision freeze and Ready
  Check all speak the same finding;
* :mod:`entropia.domain.readiness.validators` — maps it to the typed readiness code
  ``ALLOCATION_SHARED_MODE_NOT_IN_BUILD`` (doc 14 §9.1 code + remediation contract);
* :mod:`entropia.application.commands.backtest_run` — an admission guard reads
  :func:`shared_allocation_requested` straight off the immutable
  ``capital_execution`` snapshot, so a run is refused even if the readiness
  evaluation is bypassed, regressed or replaced;
* the Portfolio page — ``queries.allocation_plan.get_allocation_draft`` publishes
  :func:`shared_allocation_capability_view` so the browser renders the SERVER's
  state instead of a hardcoded client constant.

WHY (empirically grounded, doc 13 §8.3 / §8.4 / §13 / §14 test 11)
-----------------------------------------------------------------
Doc 13 §8.3 is unambiguous: at a given timestamp the engine resolves the mandatory
stop/exit/funding/fee events first and then produces ONE portfolio valuation
snapshot, and every active item forms its entry/scale intent against THAT
snapshot. §8.4 steps 3-4 repeat it, §13 raises it to a normative implementation
rule (the outcome must not depend on DOM row order, browser timing or request
arrival order), and §14 acceptance test 11 pins it.

This build does not do that. ``application.jobs.backtest_engine`` loops over
ITEMS, not over timestamps: each item replays its own bar axis against its own
``_Ledger`` seeded from the full pool P0, and
``domain.backtest.execution.portfolio.combine_item_runs`` then CONCATENATES the
finished runs' realized-PnL progressions in manifest pin order. Two consequences
are financial, not cosmetic:

1. the composite "portfolio equity curve" is not a time series — its points carry
   item-order timestamps, so ``max_drawdown`` (and every metric derived from it,
   ``max_drawdown_pct`` / ``romad``) is measured over a curve that never existed.
   A two-item fixture whose trades interleave in wall-clock time reports a
   sequential max drawdown of 5000.00 where a unified clock over the SAME trades
   reports 3000.00 — a 66% overstatement;
2. ``resolve_allocation_execution`` hands EVERY item the full pool P0 and carries
   no cross-item state at all, so under ``COMPOUND_PORTFOLIO_EQUITY`` an item's
   sleeve compounds off its own equity and can never see a sibling's PnL, fees or
   funding — the shared pool is shared in name only.

Until the co-simulation exists, a shared-mode RUN would publish those numbers as
an immutable, canonical Backtest Result. The disclosure that already ships
(``portfolio_curve_sequential_not_unified_clock`` in the Result diagnostics) makes
the deviation visible but does not stop it being consumed as the answer. This
module fails the mode CLOSED instead: no new shared-capital Result is produced.

INDEPENDENT MODE IS UNAFFECTED
------------------------------
Doc 13 §1.1 states independent capital is a first-class mode, "Not Ready veya
eksik mod değildir". Containment applies ONLY to ``enabled=true`` plans. A
disabled/absent plan resolves to ``None`` capital execution and every existing
independent-mode path replays byte-identically.

WHAT IS *NOT* DONE HERE (honest boundary)
-----------------------------------------
Nothing is downgraded, substituted or silently re-run in independent mode, and no
already-persisted Result is mutated or re-interpreted. Historical shared-pool
Results stay immutable and readable exactly as written; they are labelled as the
legacy sequential approximation they are, from their own pinned diagnostics.

REMOVAL CONDITION
-----------------
:data:`SHARED_ALLOCATION_STATUS` flips back to ``"active_v1"`` ONLY when the
unified-clock multi-item co-simulation lands and is proven — the requester's
roadmap calls that gate "ADIM 20 unified oracle". That label is the requester's;
this repository's own ground truth
(``docs/audit/current_main_ground_truth_2026-08-03.md`` §9 G-05, §18) records the
gap as CONFIRMED and explicitly out of that audit's scope, and defines no
numbered step for it — so the concrete, checkable conditions are stated here
rather than deferred to a name this repo does not yet define:

1. the engine's outer loop is the MERGED timestamp axis of all active items, not
   the item list;
2. ONE shared ledger holds P0, the fixed nominal reserve ``R0 = P0 * r`` and the
   unallocated remainder ``U0``;
3. at each valuation point, mandatory stop/exit/funding/fee events resolve FIRST,
   then exactly ONE portfolio valuation snapshot ``E(t)`` is published and every
   active item sizes ``Ci(t) = max(0, E(t) - R0) * wi / 100`` against THAT
   snapshot (doc 13 §8.3);
4. conflict/exposure arbitration is symmetric with deterministic id-based
   tie-breaking, and a blocked item's share is never transferred (doc 13 §8.4.6,
   §13);
5. doc 13 §14 acceptance test 11 passes, and the composite equity curve is
   time-ordered by construction;
6. ``ENGINE_VERSION`` is bumped — the execution_key namespace MUST shift so no
   sequential-era Result is ever idempotently reused for a unified-clock re-RUN.

Flipping the constant without 1-6 re-opens the exact defect this module contains.
"""

from __future__ import annotations

from typing import Any, Literal

SharedAllocationStatus = Literal["active_v1", "future_dev"]

SHARED_ALLOCATION_CAPABILITY_KEY = "portfolio.shared_capital_allocation"
"""Stable key for the containment, so a log/audit line can name it exactly."""

SHARED_ALLOCATION_STATUS: SharedAllocationStatus = "future_dev"
"""``future_dev`` = shared capital allocation NEVER executes in this build.

Read this through :func:`shared_allocation_is_executable`; never re-derive the
answer at a call site.
"""

SHARED_ALLOCATION_FIELD_PATH = "enabled"
"""The plan-config field the finding points at (the Portfolio toggle)."""

SHARED_ALLOCATION_MESSAGE = (
    "Shared capital allocation is not available in this build. The engine replays "
    "each composition item independently against its own ledger seeded from the "
    "full pool and folds the finished runs in pin order, so there is no single "
    "portfolio valuation snapshot per timestamp and the composite equity curve is "
    "not time-ordered — the portfolio drawdown and every metric derived from it "
    "would be wrong (doc 13 §8.3, §8.4, §13, §14 test 11)."
)

SHARED_ALLOCATION_REMEDIATION = (
    "Turn the Portfolio Allocation toggle off and give each enabled Strategy its "
    "own Initial Capital — independent mode is a complete, supported mode (doc 13 "
    "§1.1), not a degraded one. Shared capital re-opens when the unified-clock "
    "multi-item co-simulation lands."
)

SHARED_ALLOCATION_DEPENDENCY = (
    "Needs a unified-clock multi-item co-simulation: one outer loop over the merged "
    "timestamp axis, one shared ledger holding P0 and the fixed nominal reserve R0, "
    "and exactly one portfolio valuation snapshot E(t) that every active item sizes "
    "its sleeve against (doc 13 §8.3, §8.4 steps 3-7, §13)."
)

LEGACY_SEQUENTIAL_RESULT_NOTE = (
    "Produced by the pre-containment sequential approximation: each item was "
    "replayed independently and the runs were folded in pin order, so this "
    "portfolio equity curve is not a unified-clock valuation. The result is "
    "immutable and is kept exactly as it was written."
)
"""Honest read-time label for an ALREADY-PERSISTED shared-pool Result.

Never written back onto the artifact — a Result is immutable (doc 15 §3.2). It
exists so a reader is told what the stored numbers are, instead of the raw
``portfolio_curve_sequential_not_unified_clock`` token.
"""


def shared_allocation_is_executable() -> bool:
    """``True`` only when this build can honestly run shared capital allocation."""
    return SHARED_ALLOCATION_STATUS == "active_v1"


def shared_allocation_requested(capital_execution: Any) -> bool:
    """Does this immutable ``capital_execution`` snapshot ask for SHARED capital?

    Deliberately defensive and independent of the readiness evaluation: the
    admission guard reads the manifest/snapshot dict straight, so the run refusal
    does not depend on Ready Check having produced (or been given the chance to
    produce) the blocker. Anything that is not an explicitly enabled mapping is
    independent mode — the pre-allocation behaviour — and passes through.

    Mirrors the truthiness ``domain.backtest.engine.resolve_allocation_execution``
    applies to the same key, so the guard and the engine can never disagree about
    which runs are shared.
    """
    return isinstance(capital_execution, dict) and bool(capital_execution.get("enabled"))


def shared_allocation_capability_view() -> dict[str, Any]:
    """The capability block the API publishes so the UI renders SERVER state.

    The browser must not decide availability for itself (a hidden or disabled
    control is presentation, never authorization) — it renders this verbatim while
    the blocker above is what actually refuses the work.
    """
    return {
        "key": SHARED_ALLOCATION_CAPABILITY_KEY,
        "status": SHARED_ALLOCATION_STATUS,
        "available": shared_allocation_is_executable(),
        "message": SHARED_ALLOCATION_MESSAGE,
        "remediation": SHARED_ALLOCATION_REMEDIATION,
        "dependency": SHARED_ALLOCATION_DEPENDENCY,
        "field_path": SHARED_ALLOCATION_FIELD_PATH,
    }


__all__ = [
    "LEGACY_SEQUENTIAL_RESULT_NOTE",
    "SHARED_ALLOCATION_CAPABILITY_KEY",
    "SHARED_ALLOCATION_DEPENDENCY",
    "SHARED_ALLOCATION_FIELD_PATH",
    "SHARED_ALLOCATION_MESSAGE",
    "SHARED_ALLOCATION_REMEDIATION",
    "SHARED_ALLOCATION_STATUS",
    "SharedAllocationStatus",
    "shared_allocation_capability_view",
    "shared_allocation_is_executable",
    "shared_allocation_requested",
]
