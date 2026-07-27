"""K-03 — funding/fee/carry runs at doc 15 §9.3 STEP 2, at the top of the bar.

The engine used to apply funding at the END of the bar loop, after this bar's fills,
stops, exposure checks, entry and scaling had already run. ``equity`` is what sizes an
entry (``_position_size``) and what bounds the allocation sleeve / exposure caps
(``_sleeve_capital``), so the old placement sized every position off equity that had not
yet paid its carry — under perp funding a one-directional CUMULATIVE bias toward larger
positions, with ``max_total_exposure`` binding a bar late. It also silently DROPPED any
charge whose record became available on the bar that closed the position.

These tests pin the corrected order. Each one fails under the old end-of-bar placement:

  * a record available on the EXIT bar is charged (it was dropped before);
  * ``funding_charge`` precedes every other event on its bar (it came last before);
  * that charge propagates into the equity sizing the NEXT entry (before/after assert);
  * a same-bar charge binds the exposure cap of that same bar's scaling ladder, flipping
    an accepted layer to a ``sleeve_capacity`` rejection (the late-binding exposure cap);
  * a position OPENED on a bar does not pay that bar's record — the perp convention
    (funding is paid only for the interval actually held) now cuts both ways.

Note on "same bar funding + entry": a charge requires a HELD position and a fresh entry
requires a FLAT book, so a charge and a first entry can never fall on one bar. The two
genuine same-bar interactions are the scaling ladder (covered here) and the exit bar; the
entry-sizing effect is therefore asserted on the next entry after a charged bar.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from entropia.domain.backtest.engine import (
    EngineOutput,
    resolve_allocation_execution,
    run_engine,
)
from entropia.domain.backtest.funding import FundingRecord, FundingSchedule
from entropia.domain.strategy.config import StrategyConfig
from tests.unit.engine_signal_plan import sma_entry_plan
from tests.unit.test_backtest_engine import _bar, _batched, _config, _flat
from tests.unit.test_backtest_engine_allocation import _capexec
from tests.unit.test_backtest_scaling import _config as _scale_config
from tests.unit.test_backtest_scaling import _fu, _long_then, _price_scaling

_SOURCE = "rdrev_k03_funding"


def _schedule(*records: tuple[int, str]) -> FundingSchedule:
    """A schedule from ``(january_day, rate)`` pairs; available_at == event_at."""
    return FundingSchedule(
        source_revision_id=_SOURCE,
        records=tuple(
            FundingRecord(
                available_at=datetime(2024, 1, day, tzinfo=UTC),
                event_at=datetime(2024, 1, day, tzinfo=UTC),
                rate=Decimal(rate),
            )
            for day, rate in records
        ),
        has_instrument_mapping=True,
    )


def _run(
    cfg: StrategyConfig,
    bars: list[dict[str, Any]],
    funding: FundingSchedule | None,
    **kw: Any,
) -> EngineOutput:
    return run_engine(
        strategy_config=cfg,
        bar_batches=_batched(bars, 8),
        execution_key="exec_key_k03",
        funding=funding,
        indicator_plan=sma_entry_plan(),
        **kw,
    )


def _entry_fills(out: EngineOutput) -> list[dict[str, Any]]:
    return [e.detail for e in out.signal_events if e.event_type == "entry_fill"]


def _bar_events(out: EngineOutput, bar_seq: int) -> list[str]:
    return [e.event_type for e in out.signal_events if e.detail.get("bar_seq") == bar_seq]


def _entry_then_stop() -> list[dict[str, Any]]:
    """20 look-back bars -> an upside breakout (long @102 on bar 21) -> a stop-out on 22."""
    bars = _flat(20)
    bars.append(_bar("2024-01-21T00:00:00Z", "100", "102", "100", "102"))
    bars.append(_bar("2024-01-22T00:00:00Z", "102", "102", "90", "95"))
    return bars


def _entry_stop_then_reentry() -> list[dict[str, Any]]:
    """``_entry_then_stop`` + a flat stretch + a SECOND breakout (long @120 on bar 29)."""
    bars = _entry_then_stop()
    bars.extend(_bar(f"2024-01-{23 + i:02d}T00:00:00Z", "95", "95", "95", "95") for i in range(6))
    bars.append(_bar("2024-01-29T00:00:00Z", "95", "120", "95", "120"))
    bars.append(_bar("2024-01-30T00:00:00Z", "120", "121", "119", "120"))
    return bars


def _scale_batches(bars: list[dict[str, Any]]) -> Iterator[list[dict[str, Any]]]:
    for start in range(0, len(bars), 8):
        yield bars[start : start + 8]


# --------------------------------------------------------------------------- #
# The exit bar: a charge the old end-of-bar order silently dropped             #
# --------------------------------------------------------------------------- #


def test_funding_available_on_the_exit_bar_is_charged() -> None:
    # The position is held at the START of bar 22 and stopped out later in that same bar.
    # Under the old END-of-bar placement the funding block ran after the close, saw a flat
    # book and consumed the record WITHOUT charging — a free bar of carry on every exit.
    bars = _entry_then_stop()
    off = _run(_config(), bars, None)
    on = _run(_config(), bars, _schedule((22, "0.001")))
    assert off.diagnostics["funding_charges"] == 0
    # Entry notional 50 * 102 = 5100; a long PAYS a positive rate: 5100 * 0.001 = 5.10.
    assert on.diagnostics["funding_charges"] == 1
    assert on.summary["funding_paid"] == Decimal("5.10")
    assert off.summary["final_equity"] - on.summary["final_equity"] == Decimal("5.10")


def test_funding_charge_precedes_every_other_event_on_its_bar() -> None:
    # Step 2 runs before steps 3-8, so on any bar the charge is the FIRST event emitted.
    # The old order emitted it last (when it was emitted at all).
    on = _run(_config(), _entry_then_stop(), _schedule((22, "0.001")))
    events = _bar_events(on, 22)
    assert events[0] == "funding_charge"
    assert "position_close" in events
    assert events.index("funding_charge") < events.index("position_close")


# --------------------------------------------------------------------------- #
# Position sizing: the before/after the charge actually moves                  #
# --------------------------------------------------------------------------- #


def test_exit_bar_funding_shrinks_the_equity_that_sizes_the_next_entry() -> None:
    # risk_based_sizing makes the entry size a pure function of equity
    # (size = equity * risk% / 100 / stop_loss_point), so the funding charge is visible
    # directly in the position the engine opens.
    cfg = _config(method="risk_based_sizing", risk_pct="2.0", stop_point="1.0")
    bars = _entry_stop_then_reentry()
    off = _run(cfg, bars, None)
    on = _run(cfg, bars, _schedule((22, "0.001")))

    off_fills, on_fills = _entry_fills(off), _entry_fills(on)
    assert len(off_fills) == len(on_fills) == 2
    # BEFORE the charge both runs are identical: 10000 * 2% / 1 = 200 units @102.
    assert off_fills[0]["size"] == on_fills[0]["size"] == "200.00000000"
    assert off_fills[0]["entry_notional"] == on_fills[0]["entry_notional"] == "20400.00"

    # The bar-22 charge is 20400 * 0.001 = 20.40, booked BEFORE the stop-out closes the
    # position, so it lands in the equity that sizes the SECOND entry on bar 29:
    #   funding off: (10000 - 204.00) * 2% = 195.92000000
    #   funding on : (10000 - 204.00 - 20.40) * 2% = 195.51200000
    assert on.summary["funding_paid"] == Decimal("20.40")
    assert off_fills[1]["size"] == "195.92000000"
    assert on_fills[1]["size"] == "195.51200000"
    assert Decimal(on_fills[1]["size"]) < Decimal(off_fills[1]["size"])
    # The whole bias in one line: the un-funded run opens the LARGER position.
    assert Decimal(off_fills[1]["entry_notional"]) - Decimal(on_fills[1]["entry_notional"]) == (
        Decimal("48.96")
    )


def test_same_bar_funding_binds_the_exposure_cap_of_the_scaling_ladder() -> None:
    # The clearest "same bar" case: a charge and a scaling candidate on ONE bar. The ladder's
    # sleeve headroom is ``_sleeve_capital(equity) - entry_notional``, so charging first is
    # what makes ``max_total_exposure`` bind on time. Funding off, the layer is ACCEPTED;
    # funding on, the SAME layer is REJECTED for sleeve capacity — under the old order the
    # charge landed after the ladder and the layer was accepted either way.
    bars = _long_then(
        [_fu(22, "102", "102", "100", "100.5"), _fu(23, "100.5", "101", "100", "100.5")]
    )
    cfg = _scale_config(scaling=_price_scaling(retracement="1.0", layers=3, add_size_value="50"))
    allocation = resolve_allocation_execution(
        _capexec(item_id="mbi_1", amount="10000.00", mode="COMPOUND_PORTFOLIO_EQUITY", share="77"),
        item_id="mbi_1",
    )

    def _scale_run(funding: FundingSchedule | None) -> EngineOutput:
        return run_engine(
            strategy_config=cfg,
            bar_batches=_scale_batches(bars),
            execution_key="exec_key_k03_scale",
            allocation=allocation,
            funding=funding,
            indicator_plan=sma_entry_plan(),
        )

    off = _scale_run(None)
    on = _scale_run(_schedule((22, "0.03")))

    # Sleeve = 77% of equity. Off: 7700 - 5100 = 2600 >= the 25 * 100.50 = 2512.50 candidate.
    assert _bar_events(off, 22) == ["scale_layer_added"]
    added = next(e.detail for e in off.signal_events if e.event_type == "scale_layer_added")
    assert added["new_size"] == "75.00000000"

    # On: the bar-22 charge is 5100 * 0.03 = 153.00, so the sleeve is
    # 77% * (10000 - 153) - 5100 = 2482.19 < 2512.50 -> the layer is refused, not trimmed.
    assert on.summary["funding_paid"] == Decimal("153.00")
    assert _bar_events(on, 22) == ["funding_charge", "scale_layer_rejected"]
    rejected = next(e.detail for e in on.signal_events if e.event_type == "scale_layer_rejected")
    assert rejected["reason"] == "sleeve_capacity"
    assert rejected["cap"] == "2482.19"


# --------------------------------------------------------------------------- #
# The other side of the perp convention                                        #
# --------------------------------------------------------------------------- #


def test_a_position_opened_on_a_bar_does_not_pay_that_bar_s_funding() -> None:
    # Step 2 runs while the book is still flat on the entry bar, so the record is consumed
    # WITHOUT a charge: funding is paid only for the interval the position is actually held.
    # The old end-of-bar order charged it — the position had opened by then. This is the
    # symmetric half of the exit-bar fix, and it is why a charge and a first entry can never
    # share a bar.
    bars = _entry_stop_then_reentry()
    cfg = _config()
    on = _run(cfg, bars, _schedule((21, "0.001")))  # available on the ENTRY bar
    assert on.diagnostics["funding_charges"] == 0
    assert on.summary["funding_paid"] == Decimal("0.00")
    assert on.summary == _run(cfg, bars, None).summary
    assert not any(e.event_type == "funding_charge" for e in on.signal_events)


def test_the_corrected_order_stays_deterministic_across_batch_sizes() -> None:
    # Reproducibility is unaffected by the move (doc 15 §17): the charge is applied at the
    # same bar regardless of how the OHLCV stream is batched.
    cfg = _config(method="risk_based_sizing", risk_pct="2.0", stop_point="1.0")
    bars = _entry_stop_then_reentry()
    sched = _schedule((22, "0.001"), (24, "0.0005"), (29, "0.0002"))
    a = run_engine(
        strategy_config=cfg,
        bar_batches=_batched(bars, 8),
        execution_key="exec_key_k03",
        funding=sched,
        indicator_plan=sma_entry_plan(),
    )
    b = run_engine(
        strategy_config=cfg,
        bar_batches=_batched(bars, 3),
        execution_key="exec_key_k03",
        funding=sched,
        indicator_plan=sma_entry_plan(),
    )
    assert a.summary == b.summary
    assert _entry_fills(a) == _entry_fills(b)
