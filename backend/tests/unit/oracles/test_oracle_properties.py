"""Oracle — run-level invariants that must hold whatever the fixture (ADIM 12).

Where the other modules pin one number each, these pin RELATIONSHIPS: money is conserved,
the equity curve's derived columns follow from the ledger, the result is a function of
(bars, config) and not of how the bars were batched, a disabled setting costs nothing, and
nothing fills on information the bar had not yet produced.

Canonical anchors: Master Ref §13 §5.2 (``net_profit = final_equity - initial_equity``,
inclusive of every fee/funding/spread), §11.3/§8.2 (no-lookahead), doc 02 §5.8
(restrictions gate ENTRY), doc 13 §8.3 (allocation is an outer cap, not a substitute).
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from entropia.domain.backtest.engine import run_engine
from entropia.domain.backtest.funding import FundingRecord, FundingSchedule
from entropia.domain.backtest.indicators import IndicatorPlan, IndicatorSpec, SignalRule
from tests.unit.oracles.harness import (
    INITIAL_CAPITAL,
    bar,
    batched,
    flat_run,
    oracle_config,
    run_oracle,
)

_UP_CROSS = bar(21, "100", "102", "100", "102")
_WINNER = [*flat_run(), _UP_CROSS, bar(22, "102", "104", "102", "104")]
_LOSER = [*flat_run(), _UP_CROSS, bar(22, "102", "102", "90", "95")]
_PCT_1 = {"percentage_stop": {"enabled": True, "loss_percentage": "1.0"}}


# --------------------------------------------------------------------------- #
# Money conservation                                                           #
# --------------------------------------------------------------------------- #
def test_final_equity_is_the_initial_capital_plus_every_realized_lot() -> None:
    """10000 + 100.00 = 10100.00, and ``net_profit`` is the same difference. A lot that
    reached the trade table but not the book would show up here as a mismatch."""
    out = run_oracle(oracle_config(direction="long", protection={}), _WINNER)

    realized = sum((t.pnl for t in out.trades), Decimal("0"))
    assert realized == Decimal("100.00")
    assert out.summary["final_equity"] == INITIAL_CAPITAL + realized
    assert out.summary["net_profit"] == out.summary["final_equity"] - INITIAL_CAPITAL


def test_funding_is_inside_the_run_total_but_outside_the_trade_lots() -> None:
    """A carry cost is not a trade result: the lot stays at 100.00 while the book absorbs
    the 5100 * 0.001 = 5.10 charge. final = 10000 + 100.00 - 5.10 = 10094.90, so
    ``net_profit`` (94.90) and the sum of lots (100.00) legitimately DIFFER by exactly the
    funding."""
    bars = [
        *flat_run(),
        _UP_CROSS,
        bar(22, "102", "102", "102", "102"),
        bar(23, "102", "104", "102", "104"),
    ]
    schedule = FundingSchedule(
        source_revision_id="rdrev_oracle",
        records=(
            FundingRecord(
                available_at=datetime(2024, 1, 22, tzinfo=UTC),
                event_at=datetime(2024, 1, 22, tzinfo=UTC),
                rate=Decimal("0.001"),
            ),
        ),
        has_instrument_mapping=True,
    )
    out = run_oracle(oracle_config(direction="long", protection={}), bars, funding=schedule)

    lots = sum((t.pnl for t in out.trades), Decimal("0"))
    assert lots == Decimal("100.00")
    assert out.summary["net_profit"] == Decimal("94.90")
    assert lots - out.summary["net_profit"] == Decimal("5.10")


def test_the_equity_curve_columns_follow_from_the_ledger() -> None:
    """The stop-out fixture: equity 10000 -> 9949.00.
    drawdown = peak - equity = 10000.00 - 9949.00 = 51.00
    exposure = closed_notional / equity_before * 100 = (102 * 50) / 10000 * 100 = 51.0000
    The seed point is the untraded opening book: 10000.00 at zero drawdown."""
    out = run_oracle(oracle_config(direction="long", protection=_PCT_1), _LOSER)

    seed, closed = out.equity_points
    assert (seed.equity, seed.drawdown) == (Decimal("10000.00"), Decimal("0.00"))
    assert closed.equity == Decimal("9949.00")
    assert closed.drawdown == Decimal("51.00")
    assert closed.exposure == Decimal("51.0000")


# --------------------------------------------------------------------------- #
# Determinism                                                                  #
# --------------------------------------------------------------------------- #
def test_the_result_is_independent_of_how_the_bars_were_batched() -> None:
    """Reproducibility is a function of (bars, config) — streaming is an implementation
    detail. One bar per batch and fifty bars per batch must agree byte for byte, including
    the decision-trace ordering."""
    config = oracle_config(direction="long", protection=_PCT_1)
    runs = [
        run_engine(
            strategy_config=config,
            bar_batches=batched(_LOSER, size),
            execution_key="oracle_exec_key",
            indicator_plan=_sma_plan(),
        )
        for size in (1, 3, 8, 50)
    ]

    first = runs[0]
    for other in runs[1:]:
        assert other.summary == first.summary
        assert [(t.entry_price, t.exit_price, t.pnl) for t in other.trades] == [
            (t.entry_price, t.exit_price, t.pnl) for t in first.trades
        ]
        assert [(e.seq, e.event_type) for e in other.signal_events] == [
            (e.seq, e.event_type) for e in first.signal_events
        ]


def test_the_same_inputs_replayed_twice_give_the_same_ledger() -> None:
    config = oracle_config(direction="long", protection=_PCT_1)
    first = run_oracle(config, _LOSER)
    second = run_oracle(config, _LOSER)

    assert first.summary == second.summary
    assert [t.pnl for t in first.trades] == [t.pnl for t in second.trades]


def _sma_plan() -> IndicatorPlan:
    spec = IndicatorSpec(
        block_id="blk_1",
        canonical_key="ta.sma",
        length=20,
        direction="long_and_short",
        requirement="required",
        validity="current_candle_only",
    )
    return IndicatorPlan(
        entry_rule=SignalRule(rule="required_indicator_blocks_only"), entry_specs=(spec,)
    )


# --------------------------------------------------------------------------- #
# A disabled setting is free                                                   #
# --------------------------------------------------------------------------- #
def test_disabled_stop_rules_are_inert_not_merely_ignored_at_the_end() -> None:
    """A trailing stop that would sit at 106 * 0.98 and an absolute stop at 101.50 are both
    present but DISABLED. The run must be byte-identical to the percentage-stop-only
    config — the same -51.00 stop-out, not a stop the user switched off."""
    disabled = run_oracle(
        oracle_config(
            direction="long",
            protection={
                **_PCT_1,
                "trailing_stop": {
                    "enabled": False,
                    "trail_percentage": "2.0",
                    "lock_in_percentage": "0.8",
                },
                "absolute_stop": {"enabled": False, "absolute_price": "101.50"},
            },
        ),
        _LOSER,
    )
    only_percentage = run_oracle(oracle_config(direction="long", protection=_PCT_1), _LOSER)

    assert disabled.summary == only_percentage.summary
    assert disabled.trades[0].pnl == Decimal("-51.00")


# --------------------------------------------------------------------------- #
# Restrictions gate ENTRY                                                      #
# --------------------------------------------------------------------------- #
def test_a_date_blackout_covering_the_signal_bar_blocks_the_entry() -> None:
    """The blackout covers 2024-01-21, the cross bar. No trade, book untouched, and the
    veto is journalled in the FILTERED trace rather than dressed up as a fill."""
    restrictions = {
        "rule": "any",
        "filters": [
            {
                "filter_type": "date_blackout_filter",
                "enabled": True,
                "filter_id": "flt_blackout",
                "config": {"date_ranges": [{"start": "2024-01-21", "end": "2024-01-21"}]},
            }
        ],
    }
    out = run_oracle(
        oracle_config(direction="long", protection={}, restrictions=restrictions), _WINNER
    )

    assert out.trades == []
    assert out.summary["final_equity"] == Decimal("10000.00")
    veto = out.filtered_events[0]
    assert (veto.event_type, veto.detail["bar_seq"]) == ("filtered_no_entry", 21)


def test_a_consecutive_loss_filter_blocks_the_entry_after_its_nth_loss() -> None:
    """``max_losses = 1``: the bar-21 long stops out for -51.00, and the fresh cross on bar
    23 is refused. Control (no filter) takes that second trade, so the two runs end apart by
    exactly the trade the filter prevented.

    The SECOND trade is smaller than the first, and that is the point of stating it here
    (GH #550). Every modelled sizing method is a fraction of CAPITAL, so the -51.00 loss
    shrinks the next position: 9 949 * 1% / 2.00 = 49.745 units against the first trade's
    50, and the 1.00 move from 105 to 106 books 49.745 -> 49.74 at the money step. Control
    ends at 9949.00 + 49.74 = 9998.74. Before the fix a base size was a constant unit count
    that ignored the account it was traded in, and this second trade was a flat 50.00."""
    bars = [
        *flat_run(),
        _UP_CROSS,
        bar(22, "102", "102", "99", "99"),
        bar(23, "99", "105", "99", "105"),
        bar(24, "105", "106", "105", "106"),
    ]
    restrictions = {
        "rule": "any",
        "filters": [
            {
                "filter_type": "consecutive_loss_filter",
                "enabled": True,
                "filter_id": "flt_streak",
                "config": {"max_losses": 1},
            }
        ],
    }
    filtered = run_oracle(
        oracle_config(direction="long", protection=_PCT_1, restrictions=restrictions), bars
    )
    control = run_oracle(oracle_config(direction="long", protection=_PCT_1), bars)

    assert [t.pnl for t in filtered.trades] == [Decimal("-51.00")]
    assert [t.pnl for t in control.trades] == [Decimal("-51.00"), Decimal("49.74")]
    assert filtered.summary["final_equity"] == Decimal("9949.00")
    assert control.summary["final_equity"] == Decimal("9998.74")


# --------------------------------------------------------------------------- #
# No-lookahead                                                                 #
# --------------------------------------------------------------------------- #
def test_a_fill_is_never_dated_before_the_signal_that_caused_it() -> None:
    """Structural: every ``entry_fill`` sits at or after its ``entry_signal``'s bar."""
    out = run_oracle(
        oracle_config(direction="long", protection={}, entry_timing="next_candle_open"),
        [
            *flat_run(),
            _UP_CROSS,
            bar(22, "103", "104", "103", "104"),
            bar(23, "104", "106", "104", "106"),
        ],
    )

    signal = next(e for e in out.signal_events if e.event_type == "entry_signal")
    fill = next(e for e in out.signal_events if e.event_type == "entry_fill")
    assert fill.detail["bar_seq"] >= signal.detail["bar_seq"]


def test_a_higher_timeframe_signal_waits_for_its_candle_to_close() -> None:
    """12 hourly bars aggregated into 2h candles (buckets 00-01, 02-03, ... 10-11), so the
    candle closes are the 2nd bar of each bucket: [10, 10, 10, 10, 12, 14].

    An SMA(2) price/MA cross fires on candle 4: its close of 12 crosses the (10 + 12) / 2
    = 11 average. Candle 4 spans the 08:00 and 09:00 bars — it is not COMPLETE until the
    10:00 bar arrives, so that is the first bar the signal may act on.

    The 10:00 bar closes at 14, so the entry pays 14.00. An engine that published the
    candle at 09:00 would have filled at 12.00 and booked 100.00 of profit it could not
    have earned. pnl here = (16 - 14) * 50 = 100.00 from the 11:00 close instead."""
    closes = ["10"] * 8 + ["11", "12", "14", "16"]
    hourly = [
        {
            "timestamp": f"2024-01-01T{hour:02d}:00:00Z",
            "open": close,
            "high": close,
            "low": close,
            "close": close,
            "volume": "10",
        }
        for hour, close in enumerate(closes)
    ]
    htf_spec = IndicatorSpec(
        block_id="blk_htf",
        canonical_key="ta.sma",
        length=2,
        direction="long_and_short",
        requirement="required",
        validity="until_opposite_signal",
        resample_seconds=7200,
    )
    out = run_engine(
        strategy_config=oracle_config(direction="long", protection={}),
        bar_batches=batched(hourly, 4),
        execution_key="oracle_exec_key",
        indicator_plan=IndicatorPlan(
            entry_rule=SignalRule(rule="required_indicator_blocks_only"), entry_specs=(htf_spec,)
        ),
        timeframe="1h",
    )

    trade = out.trades[0]
    assert trade.entry_time == "2024-01-01T10:00:00Z"
    assert trade.entry_price == Decimal("14.00")
    assert trade.pnl == Decimal("100.00")
