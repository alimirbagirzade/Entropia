"""OD-2(a)'s mark path, bound to the production loop — the diagnostics half (ADIM 134).

ADIM 132 shipped the policy (``MarkPrice.is_usable`` / ``.is_stale_refused``, the
``MARK_STALE_AFTER_MS`` bound, ``PortfolioValuation.stale_refused_items``) and recorded it
in the manifest as ``carry_forward_bounded_v1``. It did NOT bind it: ``attribute()`` had
zero callers, ``MarkPrice`` was constructed only in tests, and so the counter ADR §13.1
OD-2(a) asks for — *"a diagnostic counter"* — could not be produced by any run. The manifest
nevertheless declared ``mark_staleness_status: "built"`` on every run.

Product owner decision (2026-08-28, ``closure_od2_mark_production_binding_2026-08-28.md``):
Karar 1 = **(b) diagnostics only**, Karar 2 = **A** (the 900 s bound is untouched),
Karar 3 = **A** (no ``ENGINE_VERSION`` bump — reproduction identity does not move).

Every fixture here runs the SHIPPED loop through ``oracles.portfolio_harness``. Nothing is
hand-built and no expected figure is recomputed by this module.

The staleness fixture needs no contrivance: the harness replays HOURLY bars and the bound is
900 s, so an item that holds a position through a tick at which it has no fresh bar is
already past it. That is Ölçüm 6 of the decision document observed from the other side — at
30m and coarser the bound carries zero bars — and it is why the counter is reachable at all.
"""

from __future__ import annotations

from entropia.domain.backtest.execution.portfolio_ledger import MARK_STALE_AFTER_MS
from entropia.domain.backtest.portfolio_engine import PortfolioRun

from .oracles.portfolio_harness import ScriptedItem, simulate
from .oracles.test_oracle_portfolio_clock import _HOURS
from .test_backtest_portfolio_projection import _pinned, _project

_ONE_HOUR_MS = 3_600_000


def _holder_and_ticker() -> list[ScriptedItem]:
    """``b`` opens at hour 0 and then goes quiet while ``a`` keeps the axis moving.

    ``b`` holds an open position for the rest of the run with no fresh bar, so from hour 1
    onward its only offerable price is a ``stale_last_close`` whose age is a full hour —
    four times ``MARK_STALE_AFTER_MS``. That is the exact state OD-2(a) exists to name."""
    return [
        ScriptedItem(item_id="a", share="50", bars=[(hour, "100") for hour in _HOURS[:4]]),
        ScriptedItem(
            item_id="b",
            share="50",
            bars=[(_HOURS[0], "100")],
            entries={_HOURS[0]: ("long", "10")},
        ),
    ]


def _marked_holder() -> list[ScriptedItem]:
    """``a`` holds a long through a RISING market with a fresh bar at every tick.

    Deliberately the opposite of ``_holder_and_ticker``: here the position is markable at
    every tick, so ``unrealized_pnl`` is non-zero and an ``E(t)`` that folded a mark in
    would visibly diverge. Without a moving price this fixture would report ``0`` and the
    assertion it carries would be vacuous — which is exactly what a negative control caught
    on the first writing of this module."""
    return [
        ScriptedItem(
            item_id="a",
            share="50",
            bars=[
                (_HOURS[0], "100"),
                (_HOURS[1], "110"),
                (_HOURS[2], "120"),
                (_HOURS[3], "130"),
            ],
            entries={_HOURS[0]: ("long", "10")},
        ),
        ScriptedItem(item_id="b", share="50", bars=[(hour, "100") for hour in _HOURS[:4]]),
    ]


def _diagnostic(run: PortfolioRun) -> dict[str, object]:
    return dict(_project(run, _pinned("a", "b")).diagnostics["mark_staleness"])


# ------------------------------------------------------- the counter OD-2(a) asked for


def test_a_position_held_past_the_bound_is_named_in_the_stale_refused_counter() -> None:
    """The gap ADIM 132 left open, closed: a real run now PRODUCES the counter.

    Before the binding this assertion could not be written at all — not because the policy
    was wrong but because nothing reachable called it. ``stale_refused_items`` is asserted
    by NAME rather than by count: OD-2(a) wants to know WHICH position aged out."""
    diagnostic = _diagnostic(simulate(_holder_and_ticker()))

    assert diagnostic["stale_refused_items"] == ["b"]
    assert "b" in diagnostic["unmarked_items"]
    # The hour the harness replays is four times the bound — the refusal is not marginal.
    assert _ONE_HOUR_MS > MARK_STALE_AFTER_MS


def test_the_stale_counter_is_a_subset_of_unmarked_not_a_copy_of_it() -> None:
    """``portfolio_ledger``'s own invariant, now observable end to end.

    Every stale-refused item is unmarked, but not every unmarked item is stale. Reading
    staleness off the wider list would over-report it, which is the specific defect the
    two separate lists exist to prevent."""
    diagnostic = _diagnostic(simulate(_holder_and_ticker()))

    assert set(diagnostic["stale_refused_items"]) <= set(diagnostic["unmarked_items"])


def test_an_item_that_never_goes_quiet_is_never_reported_stale() -> None:
    """The positive control: a fresh bar at every tick refuses nothing.

    Without this, the fixture above would prove only that SOMETHING lands in the counter,
    not that the bound is what put it there."""
    both_fresh = [
        ScriptedItem(
            item_id="a",
            share="50",
            bars=[(hour, "100") for hour in _HOURS[:4]],
            entries={_HOURS[0]: ("long", "10")},
        ),
        ScriptedItem(item_id="b", share="50", bars=[(hour, "100") for hour in _HOURS[:4]]),
    ]
    diagnostic = _diagnostic(simulate(both_fresh))

    assert diagnostic["stale_refused_items"] == []
    assert diagnostic["unmarked_items"] == []


# ------------------------------------------------------------- reported, never folded in


def test_the_mark_never_moves_e_of_t() -> None:
    """ADR §5 and the ledger module docstring: ``E(t)`` is realized-only.

    Asserted at the seam itself rather than on a downstream total: the valuation is taken
    inside the frozen window beside the snapshot, and it reports the SAME equity that
    snapshot froze. If a mark were ever folded in, these two would diverge at the first
    tick carrying a non-zero unrealized figure.

    The vacuity guard is load-bearing, not decoration: an earlier version of this test ran
    on a fixture whose every position was UNMARKABLE, so ``unrealized_pnl`` was ``0`` or
    ``None`` at every tick and folding it into equity changed nothing. The negative control
    stayed green and the test proved nothing. Assert the fixture is live, then assert the
    invariant."""
    run = simulate(_marked_holder())

    assert run.ticks, "fixture must walk at least one tick"
    unrealized = [tick.valuation.unrealized_pnl for tick in run.ticks]
    assert any(figure is not None and figure != 0 for figure in unrealized), (
        f"vacuous fixture: nothing is held at a moved price ({unrealized})"
    )

    for tick in run.ticks:
        assert tick.valuation.equity == tick.snapshot.equity
        assert tick.valuation.t_ms == tick.t_ms


def test_an_unmarkable_position_is_reported_not_valued_at_zero() -> None:
    """The refusal is fail-closed: no partial marked exposure is published.

    A marked figure computed over only the markable half would read as a smaller portfolio
    than the one actually held, so the ledger nulls all three rather than shrinking them."""
    run = simulate(_holder_and_ticker())

    stale_ticks = [tick for tick in run.ticks if tick.valuation.unmarked_items]
    assert stale_ticks, "fixture must produce at least one unmarkable tick"
    for tick in stale_ticks:
        assert tick.valuation.unrealized_pnl is None
        assert tick.valuation.marked_gross_exposure is None
        assert tick.valuation.marked_net_exposure is None


# ------------------------------------------------------------------ the per-run fold


def test_the_two_tick_counts_partition_every_tick_walked() -> None:
    """A tick is either fully marked or it is not; nothing is counted twice or dropped."""
    run = simulate(_holder_and_ticker())
    output = _project(run, _pinned("a", "b"))
    diagnostic = output.diagnostics["mark_staleness"]

    assert (
        diagnostic["ticks_fully_marked"] + diagnostic["ticks_with_unmarked_positions"]
        == output.diagnostics["tick_count"]
        == len(run.ticks)
    )
    assert diagnostic["ticks_with_unmarked_positions"] >= 1


def test_the_binding_reports_and_does_not_enter_the_execution_identity() -> None:
    """Karar 3 = A, pinned: the diagnostic is a report, not part of reproduction identity.

    ``execution_key`` is passed IN by the caller and derives from the manifest, never from
    ``EngineOutput``. This asserts the projection does not smuggle the mark figures into
    it — which is what would have forced the ``ENGINE_VERSION`` bump option (c2) carries."""
    output = _project(simulate(_holder_and_ticker()), _pinned("a", "b"))

    assert output.diagnostics["execution_key"] == "exec-key"
    assert "mark_staleness" not in output.summary
    assert all(
        isinstance(value, (int, list)) for value in output.diagnostics["mark_staleness"].values()
    )


def test_a_run_holding_nothing_reports_an_empty_counter_not_a_missing_one() -> None:
    """Absence must be an empty list, not a missing key.

    A missing key would make a caller unable to distinguish 'nothing aged out' from 'this
    build does not measure staleness' — the same declaration-vs-fact asymmetry this slice
    exists to remove."""
    flat = [
        ScriptedItem(item_id="a", share="50", bars=[(hour, "100") for hour in _HOURS[:3]]),
        ScriptedItem(item_id="b", share="50", bars=[(hour, "100") for hour in _HOURS[:3]]),
    ]
    diagnostic = _diagnostic(simulate(flat))

    assert diagnostic["stale_refused_items"] == []
    assert diagnostic["unmarked_items"] == []
    assert diagnostic["ticks_with_unmarked_positions"] == 0
    assert diagnostic["ticks_fully_marked"] == 3
