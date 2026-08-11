"""``PortfolioRun`` -> ONE composite ``EngineOutput`` — the ADR 0002 Result projection.

Every fixture here is driven through the SHIPPED phase loop (``oracles.portfolio_harness``),
so what is under test is the projection alone: no second engine, no re-derived amount, no
expected value this module computed for itself. The two error fixtures do not hand-build a
run either — they take a real one and ``dataclasses.replace`` exactly one field, so the
refusal is provoked by a specific corruption rather than by a synthetic object that was
never a run in the first place.

The flagship case is deliberately the containment fixture's own trade set: the same four
closes ``test_oracle_portfolio_containment_gate`` folds sequentially into ``5000.00``. What
that gate could only show as a ``PortfolioRun`` property, this module shows in the artifact
the Result actually reads.
"""

from __future__ import annotations

import json
from dataclasses import asdict, replace
from decimal import Decimal
from hashlib import sha256
from typing import Any

import pytest

from entropia.domain.backtest.engine import EngineOutput
from entropia.domain.backtest.execution.portfolio import _DIAG_SUM_KEYS
from entropia.domain.backtest.execution.portfolio_projection import (
    ABSENT_BY_CONSTRUCTION,
    ENGINE_KIND,
    NON_EXECUTING_NOTE,
    PORTFOLIO_PROJECTION_VERSION,
    PinnedItem,
    UnpairedCloseError,
    UnpinnedItemError,
    UnpricedIntentError,
    project_portfolio_run,
)
from entropia.domain.backtest.portfolio_engine import PortfolioRun

from .oracles.portfolio_harness import ScriptedItem, simulate
from .oracles.test_oracle_portfolio_clock import _HOURS, _interleaved_pair


def _pinned(
    *item_ids: str,
    symbol: str | None = "BTCUSDT",
    timeframe: str | None = "1h",
) -> list[PinnedItem]:
    """Manifest-pinned metadata for each item, in pin order unless a test permutes it."""
    return [
        PinnedItem(
            item_id=item_id,
            item_kind="strategy",
            root_id=f"root_{item_id}",
            revision_id=f"rev_{item_id}",
            item_label=f"Item {item_id.upper()}",
            symbol=symbol,
            timeframe=timeframe,
        )
        for item_id in item_ids
    ]


def _project(
    run: PortfolioRun,
    items: list[PinnedItem] | None = None,
    *,
    item_count: int = 2,
) -> EngineOutput:
    return project_portfolio_run(
        run,
        items=_pinned("a", "b") if items is None else items,
        execution_key="exec-key",
        item_count=item_count,
    )


def _digest(output: EngineOutput) -> str:
    """A canonical digest of the WHOLE output, order included.

    Order is inside the digest on purpose: A4 and A18 are about a permuted or re-chunked
    input producing an identical artifact, and an order-insensitive comparison would pass
    over exactly the regression those criteria exist to catch."""
    payload: dict[str, Any] = {
        "summary": output.summary,
        "trades": [asdict(row) for row in output.trades],
        "equity_points": [asdict(point) for point in output.equity_points],
        "signal_events": [asdict(event) for event in output.signal_events],
        "diagnostics": output.diagnostics,
        "position_intervals": output.position_intervals,
        "filtered_events": [asdict(event) for event in output.filtered_events],
    }
    return sha256(json.dumps(payload, default=str).encode("utf-8")).hexdigest()


def _flat_pair() -> list[ScriptedItem]:
    """Two items that decide nothing: bars, no entries, no exits, no charges."""
    bars = [(hour, "100") for hour in _HOURS[:3]]
    return [
        ScriptedItem(item_id="a", share="50", bars=bars),
        ScriptedItem(item_id="b", share="50", bars=bars),
    ]


# --------------------------------------------------------------- the number A5 asks for


def test_it_publishes_the_unified_3000_in_the_artifact_the_result_reads() -> None:
    """ADR §14 A5, one step further than the containment gate could take it.

    The gate shows ``5000.00`` sequentially and ``3000.00`` on the merged axis, but the
    second number lives on a ``PortfolioRun`` that no Result can be built from. Here it is
    in ``EngineOutput.summary`` — the exact dict ``create_result`` writes into
    ``ResultSummary.headline`` and ``derive_metric_values`` reads."""
    output = _project(simulate(_interleaved_pair(), pool="10000"))

    assert output.summary["max_drawdown"] == Decimal("3000.00")
    assert output.summary["final_equity"] == Decimal("11000.00")
    assert output.summary["net_profit"] == Decimal("1000.00")
    assert output.diagnostics["engine_kind"] == ENGINE_KIND

    stamps = [point.timestamp for point in output.equity_points if point.timestamp]
    assert stamps == sorted(stamps)


def test_the_curve_is_the_ledgers_own_points_not_a_refold_of_them() -> None:
    """The projection copies the series; it does not rebuild one from trades.

    A fold that re-derived the curve from the trade list would silently drop every
    funding-only movement of ``E(t)`` — which is precisely the completeness ADR §7's
    equity-series rule exists to add."""
    run = simulate(_interleaved_pair(), pool="10000")
    output = _project(run)

    assert len(output.equity_points) == len(run.ledger.equity_points)
    assert [point.equity for point in output.equity_points] == [
        point.equity for point in run.ledger.equity_points
    ]
    # The ``t_ms=None`` seed keeps the empty stamp the sequential fold also seeds with.
    assert output.equity_points[0].timestamp == ""
    assert output.equity_points[0].equity == Decimal("10000")
    assert all(point.timestamp for point in output.equity_points[1:])


def test_a_funding_only_tick_reaches_the_curve_with_no_trade_behind_it() -> None:
    """The completeness claim above, exercised rather than asserted about.

    A charge with no close moves ``E(t)``, so it MUST produce an equity point that no trade
    row corresponds to. Under the sequential fold this movement is invisible."""
    bars = [(hour, "100") for hour in _HOURS[:3]]
    run = simulate(
        [ScriptedItem(item_id="a", share="100", bars=bars, funding={_HOURS[1]: "25.00"})],
        pool="10000",
    )
    output = _project(run, _pinned("a"), item_count=1)

    assert output.trades == []
    assert [point.equity for point in output.equity_points] == [
        Decimal("10000"),
        Decimal("9975.00"),
    ]
    assert output.summary["net_profit"] == Decimal("-25.00")


# ------------------------------------------------------------------------- trade rows


def test_every_trade_row_carries_the_amount_the_ledger_actually_applied() -> None:
    """``pnl`` is ``book_trade``'s return value, never ``gross - commission`` recomputed.

    The check that makes it meaningful is the identity: the rows must sum to the ledger's
    own ``net_profit``. A re-derived figure could satisfy each row and still drift on the
    sum by a cent per lot."""
    run = simulate(_interleaved_pair(), pool="10000")
    output = _project(run)

    assert [row.pnl for row in output.trades] == [
        Decimal("3000.00"),
        Decimal("-3000.00"),
        Decimal("3000.00"),
        Decimal("-2000.00"),
    ]
    assert sum(row.pnl for row in output.trades) == output.summary["net_profit"]


def test_trades_are_sequenced_by_the_merged_axis_not_grouped_by_item() -> None:
    """The sequential fold emits every trade of item A, then every trade of item B. On one
    clock the two interleave, and the seq order has to follow the wall clock — otherwise a
    Trade Ledger page would read as a story that never happened in that order."""
    output = _project(simulate(_interleaved_pair(), pool="10000"))

    assert [row.seq for row in output.trades] == [1, 2, 3, 4]
    assert [row.exit_time for row in output.trades] == [
        _HOURS[1],
        _HOURS[2],
        _HOURS[3],
        _HOURS[4],
    ]
    # a closes, then b twice, then a again — grouped-by-item would be a,a,b,b.
    assert [row.entry_time for row in output.trades] == [
        _HOURS[0],
        _HOURS[0],
        _HOURS[2],
        _HOURS[2],
    ]


def test_the_summary_metrics_are_the_shipped_folds_own_counting_rule() -> None:
    """Hand-derived from the fixture: 4 lots, 2 winners, every exit a stop, gross profit
    6000 against gross loss 5000 on a 10000 pool whose peak reached 13000."""
    output = _project(simulate(_interleaved_pair(), pool="10000"))

    assert output.summary["total_trades"] == 4
    assert output.summary["total_winning_trades"] == 2
    assert output.summary["total_stops"] == 4
    assert output.summary["max_stop_streak"] == 4
    assert output.summary["win_rate"] == Decimal("50.0000")
    assert output.summary["profit_factor"] == Decimal("1.20")
    assert output.summary["net_profit_pct"] == Decimal("10.0000")
    assert output.summary["max_drawdown_pct"] == Decimal("23.0769")
    assert output.summary["romad"] == Decimal("0.43")
    # F-05: the range actually walked, which the sequential fold never states at all.
    assert output.summary["period_start"] == _HOURS[0]
    assert output.summary["period_end"] == _HOURS[4]


def test_a_non_stop_exit_resets_the_stop_streak() -> None:
    """The streak rule is the shipped one: only ``stop_loss`` extends it, anything else
    resets. Provoked by re-labelling ONE real exit, so the run behind it is unchanged."""
    run = simulate(_interleaved_pair(), pool="10000")
    second = run.ticks[2]
    relabelled = replace(second, mandatory=(replace(second.mandatory[0], reason="take_profit"),))
    ticks = (*run.ticks[:2], relabelled, *run.ticks[3:])
    output = _project(PortfolioRun(ledger=run.ledger, ticks=ticks))

    assert [row.exit_reason for row in output.trades] == [
        "stop_loss",
        "take_profit",
        "stop_loss",
        "stop_loss",
    ]
    assert output.summary["total_stops"] == 3
    assert output.summary["max_stop_streak"] == 2


def test_a_run_that_closed_nothing_nulls_the_trade_dependent_metrics() -> None:
    """Null, never zero (L4): no trade is not a 0% win rate, and no drawdown is not a
    romad of 0. ``derive_metric_values`` reads exactly these nulls to name WHY."""
    output = _project(simulate(_flat_pair(), pool="10000"))

    assert output.trades == []
    assert output.summary["total_trades"] == 0
    assert output.summary["win_rate"] is None
    assert output.summary["profit_factor"] is None
    assert output.summary["romad"] is None
    assert output.summary["max_drawdown"] == Decimal("0.00")


def test_an_item_the_exposure_cap_refused_contributes_no_trade_row() -> None:
    """A refused admission opens nothing, so it owns no lot — but it is still in the
    decision trace, which is what makes the suppression auditable rather than invisible."""
    run = simulate(_interleaved_pair(), pool="10000", max_total_exposure_notional="3000")
    output = _project(run)

    refused = [
        event
        for event in output.signal_events
        if event.detail.get("arbitration", {}).get("outcome") in ("blocked", "rejected")
    ]
    assert refused, "the cap refused nobody; the fixture no longer exercises the branch"
    assert all(row.pnl != Decimal("0") for row in output.trades)


# ------------------------------------------------------------------- decision trace


def test_every_traced_event_binds_to_the_pinned_object_revision() -> None:
    """F-10 — a reviewer must resolve a rule id back to the immutable revision the run
    replayed, never to whatever the live composition says today."""
    output = _project(simulate(_interleaved_pair(), pool="10000"))

    assert output.signal_events
    assert [event.seq for event in output.signal_events] == list(range(len(output.signal_events)))
    for event in output.signal_events:
        item_id = event.detail["item_id"]
        assert event.detail["root_id"] == f"root_{item_id}"
        assert event.detail["revision_id"] == f"rev_{item_id}"
    assert output.diagnostics["decision_trace_count"] == len(output.signal_events)


def test_only_the_discretionary_half_of_a_tick_carries_an_arbitration_outcome() -> None:
    """P3 is resolved BEFORE ``E(t)`` exists and is never arbitrated (a mandatory intent is
    not arbitrable at all); P4 always is, actionable or not. Attaching the tick's P4 answer
    to its P3 event would read as though a forced exit had been permitted by the pool."""
    output = _project(simulate(_interleaved_pair(), pool="10000"))

    phases = {event.detail["phase"] for event in output.signal_events}
    assert phases == {"P3", "P4"}
    for event in output.signal_events:
        assert ("arbitration" in event.detail) is (event.detail["phase"] == "P4")


# ------------------------------------------------------- order and chunking invariance


def test_permuting_the_caller_and_the_pinned_list_moves_nothing() -> None:
    """ADR §14 **A4**, evaluable for the first time: the criterion is worded over an
    ``EngineOutput`` digest, and until this projection existed there was none to take."""
    baseline = _digest(_project(simulate(_interleaved_pair(), pool="10000")))
    permuted = _digest(
        _project(
            simulate(_interleaved_pair(), pool="10000", caller_order=[1, 0]),
            list(reversed(_pinned("a", "b"))),
        )
    )

    assert permuted == baseline


@pytest.mark.parametrize("batch", [1, 2, 3])
def test_chunking_each_items_bars_differently_moves_nothing(batch: int) -> None:
    """ADR §14 **A18**, likewise: the loop's batch invariance was already proven, but the
    ARTIFACT's was not, and a projection that read a batch boundary would break it."""
    baseline = _digest(_project(simulate(_interleaved_pair(), pool="10000")))

    assert _digest(_project(simulate(_interleaved_pair(), pool="10000", batch=batch))) == baseline


# --------------------------------------------------------------- declared boundaries


def test_it_names_every_number_it_does_not_measure() -> None:
    """Fail-closed, never zero-filled. A ``0`` in ``bars_processed`` would read as *"the
    engine processed no bars"*; the truth is that this loop never counts bars at all."""
    output = _project(simulate(_interleaved_pair(), pool="10000"))

    assert output.diagnostics["warnings"] == list(ABSENT_BY_CONSTRUCTION)
    for key in _DIAG_SUM_KEYS:
        assert key not in output.diagnostics, f"{key} claims a measurement the loop never took"
    assert "entry_model" not in output.diagnostics
    assert "contribution" not in output.diagnostics["composition"]
    assert output.filtered_events == []
    assert output.position_intervals == []
    assert output.diagnostics["filtered_event_count"] == 0


def test_the_projections_provenance_is_its_own_and_not_the_adim_20_manifest() -> None:
    """Two versions, both of which decide this output's SHAPE — and nothing else.

    ADR §10.3 puts ``clock_policy_version`` and its neighbours in the ADIM 20 MANIFEST, built
    by ``execution.provenance``; publishing them here would advertise a decision no artifact
    records, and would make this module an importer of three separately contained modules to
    do it. Pinned as an exact key set so that widening cannot happen by habit."""
    output = _project(simulate(_interleaved_pair(), pool="10000"))
    versions = output.diagnostics["policy_versions"]

    assert set(versions) == {"portfolio_projection_version", "portfolio_loop_version"}
    assert versions["portfolio_projection_version"] == PORTFOLIO_PROJECTION_VERSION
    assert versions["portfolio_loop_version"] == "portfolio-phase-loop-v1"
    assert output.diagnostics["execution_key"] == "exec-key"


def test_the_composition_reports_shared_pool_attribution_not_a_per_item_curve() -> None:
    """ADR §7 — the pool is not partitioned, so an item has no capital of its own. What it
    HAS is the tagged contribution the ledger recorded as each booking happened."""
    output = _project(simulate(_interleaved_pair(), pool="10000"))
    composition = output.diagnostics["composition"]
    first = composition["items"][0]

    assert composition["capital_allocation"] == "shared_pool"
    assert composition["clock"] == "unified_merged_axis"
    assert composition["compounding_mode"] == "COMPOUND_PORTFOLIO_EQUITY"
    assert [item["item_id"] for item in composition["items"]] == ["a", "b"]
    assert first["item_label"] == "Item A"
    assert first["equity_share_percent"] == Decimal("50")
    assert first["net_contribution"] == Decimal("1000.00")
    assert (first["total_trades"], first["winning_trades"]) == (2, 1)
    # The refusals: no per-item capital, no per-item curve, no contiguous seq range.
    for absent in ("initial_capital", "final_equity", "equity_curve", "trade_seq_range"):
        assert absent not in first


def test_a_pinned_but_non_executing_object_is_recorded_never_faked() -> None:
    """A Trading Signal / Trade Log takes part without simulating. It is listed for
    traceability with the token the sequential fold already uses, and every figure it does
    not have is ``None`` rather than a plausible zero."""
    signal = PinnedItem(item_id="s1", item_kind="trading_signal", item_label="Signal One")
    output = _project(
        simulate(_interleaved_pair(), pool="10000"),
        [*_pinned("a", "b"), signal],
        item_count=3,
    )
    composition = output.diagnostics["composition"]
    row = composition["items"][-1]

    assert composition["strategy_count"] == 2
    assert composition["participating_item_count"] == 3
    assert row["item_id"] == "s1"
    assert row["executed"] is False
    assert row["note"] == NON_EXECUTING_NOTE
    assert row["net_contribution"] is None
    assert row["total_trades"] == 0


def test_symbol_and_timeframe_collapse_only_when_the_items_agree() -> None:
    """The sequential fold's own rule: one shared value, or ``None``. A two-symbol
    portfolio has no single symbol, and naming one of them would be a guess."""
    run = simulate(_interleaved_pair(), pool="10000")

    assert _project(run).summary["symbol"] == "BTCUSDT"

    mixed = _pinned("a", "b")
    mixed[1] = replace(mixed[1], symbol="ETHUSDT", timeframe="4h")
    assert _project(run, mixed).summary["symbol"] is None
    assert _project(run, mixed).summary["timeframe"] is None


# ------------------------------------------------------------------ fail-closed refusals


def test_it_refuses_an_item_that_traded_without_a_pinned_record() -> None:
    """F-07 §4.4 — an unnamed row in an immutable Result cannot be attributed later, and a
    Result is not re-labelled from the live composition. So it is refused at build time."""
    run = simulate(_interleaved_pair(), pool="10000")

    with pytest.raises(UnpinnedItemError, match="'b'"):
        _project(run, _pinned("a"))


def test_it_refuses_a_booked_close_with_no_open_before_it() -> None:
    """Dropping the tick that opened the position leaves its close unpaired. A trade row
    built across that gap would state an entry time and price nobody recorded."""
    run = simulate(_interleaved_pair(), pool="10000")

    with pytest.raises(UnpairedCloseError, match="no open position recorded"):
        _project(PortfolioRun(ledger=run.ledger, ticks=run.ticks[1:]))


def test_it_refuses_a_position_closed_at_no_price() -> None:
    """An intent with neither an effective nor a reference price never names a fill. The
    row would need one, so the projection stops instead of inventing it."""
    run = simulate(_interleaved_pair(), pool="10000")
    closing = run.ticks[1]
    unpriced = replace(
        closing,
        mandatory=(replace(closing.mandatory[0], effective_price=None, reference_price=None),),
    )

    with pytest.raises(UnpricedIntentError, match="carries no price"):
        _project(PortfolioRun(ledger=run.ledger, ticks=(run.ticks[0], unpriced, *run.ticks[2:])))
