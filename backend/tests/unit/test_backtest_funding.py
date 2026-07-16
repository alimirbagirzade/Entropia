"""F-11 — funding cost + available-time (anti-lookahead) application in the pure engine.

DB-free. Proves the acceptance criteria on the pure engine surface:
  * funding-enabled vs funding-disabled produce a verifiably DIFFERENT result;
  * a funding value dated after the last replayed bar can never affect the run
    (future-leak protection, F-24);
  * a fixed-delay available-time offset shifts WHEN a rate becomes effective;
  * funding is charged only while a position is held (perp convention);
  * a long pays a positive rate, a short receives it;
  * the result is byte-identical across batch sizes (reproducibility);
  * an empty schedule is byte-identical to funding-off.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from entropia.domain.backtest.engine import run_engine
from entropia.domain.backtest.funding import FundingRecord, FundingSchedule
from tests.unit.test_backtest_engine import _bar, _batched, _config, _flat


def _long_held(hold: int = 4) -> list[dict[str, Any]]:
    """20 flat bars → an upside breakout (long @102) → ``hold`` flat bars (no stop)."""
    bars = _flat(20)
    bars.append(_bar("2024-01-21T00:00:00Z", "100", "102", "100", "102"))
    for i in range(hold):
        day = 22 + i
        bars.append(_bar(f"2024-01-{day:02d}T00:00:00Z", "102", "102", "101", "102"))
    return bars


def _short_held(hold: int = 4) -> list[dict[str, Any]]:
    """20 flat bars → a downside breakout (short @98) → ``hold`` flat bars (no stop)."""
    bars = _flat(20)
    bars.append(_bar("2024-01-21T00:00:00Z", "100", "100", "98", "98"))
    for i in range(hold):
        day = 22 + i
        bars.append(_bar(f"2024-01-{day:02d}T00:00:00Z", "98", "98", "98", "98"))
    return bars


def _ts(day: int) -> datetime:
    return datetime(2024, 1, day, tzinfo=UTC)


def _schedule(*records: tuple[int, str]) -> FundingSchedule:
    """Build a schedule from ``(day, rate)`` pairs; available_at == event_at (already safe)."""
    return FundingSchedule(
        source_revision_id="rdrev_funding_1",
        records=tuple(
            FundingRecord(available_at=_ts(day), event_at=_ts(day), rate=Decimal(rate))
            for day, rate in records
        ),
    )


def _run(cfg: Any, bars: list[dict[str, Any]], funding: Any, *, batch: int = 8) -> Any:
    return run_engine(
        strategy_config=cfg,
        bar_batches=_batched(bars, batch),
        execution_key="exec_key_funding",
        funding=funding,
    )


def test_funding_enabled_and_disabled_produce_different_results() -> None:
    cfg = _config()
    bars = _long_held()
    # The long opens at 102 close (base size 50 → notional 5100). A 0.001 rate firing while
    # held costs 5100 * 0.001 = 5.10 — a long PAYS a positive rate.
    off = _run(cfg, bars, None)
    on = _run(cfg, bars, _schedule((23, "0.001")))
    assert off.summary["funding_paid"] == Decimal("0.00")
    assert on.summary["funding_paid"] == Decimal("5.10")
    assert on.diagnostics["funding_charges"] == 1
    assert on.diagnostics["funding_enabled"] is True
    assert on.diagnostics["funding_source_revision_id"] == "rdrev_funding_1"
    # The cost is a real, verifiable divergence in the final equity / net profit.
    assert off.summary["final_equity"] - on.summary["final_equity"] == Decimal("5.10")
    assert on.summary["net_profit"] == off.summary["net_profit"] - Decimal("5.10")


def test_funding_value_after_last_bar_never_leaks_into_the_run() -> None:
    # F-24: a funding record only AVAILABLE after the last replayed bar (2024-06-01, well
    # past the 2024-01-25 tail) must NEVER fire — a future value cannot improve/worsen the
    # backtest. The run is byte-identical to funding-off.
    cfg = _config()
    bars = _long_held()
    off = _run(cfg, bars, None)
    leaked = FundingSchedule(
        source_revision_id="rdrev_funding_1",
        records=(
            FundingRecord(
                available_at=datetime(2024, 6, 1, tzinfo=UTC),
                event_at=datetime(2024, 6, 1, tzinfo=UTC),
                rate=Decimal("0.5"),
            ),
        ),
    )
    out = _run(cfg, bars, leaked)
    assert out.diagnostics["funding_charges"] == 0
    assert out.summary["funding_paid"] == Decimal("0.00")
    assert out.summary == off.summary
    assert [t.pnl for t in out.trades] == [t.pnl for t in off.trades]


def test_fixed_delay_available_time_offset_defers_when_a_rate_fires() -> None:
    # The SAME funding event (event_at 2024-01-23) fires at a different bar depending on its
    # available_at. When the available-time offset pushes it past the last bar, it never
    # fires — proving the anti-lookahead offset actually gates consumption.
    cfg = _config()
    bars = _long_held()  # last bar 2024-01-25
    within = FundingSchedule(
        source_revision_id="rd_1",
        records=(FundingRecord(available_at=_ts(24), event_at=_ts(23), rate=Decimal("0.001")),),
    )
    beyond = FundingSchedule(
        source_revision_id="rd_1",
        records=(FundingRecord(available_at=_ts(28), event_at=_ts(23), rate=Decimal("0.001")),),
    )
    assert _run(cfg, bars, within).diagnostics["funding_charges"] == 1
    assert _run(cfg, bars, beyond).diagnostics["funding_charges"] == 0


def test_funding_is_charged_only_while_a_position_is_held() -> None:
    # A record available during the flat window (2024-01-10, before the entry at 2024-01-21)
    # is consumed WITHOUT a charge — funding is paid only for the interval actually held.
    cfg = _config()
    bars = _long_held()
    out = _run(cfg, bars, _schedule((10, "0.001"), (23, "0.001")))
    # Only the in-position record (day 23) is charged; the flat-window one (day 10) is not.
    assert out.diagnostics["funding_charges"] == 1
    assert out.summary["funding_paid"] == Decimal("5.10")


def test_long_pays_and_short_receives_a_positive_rate() -> None:
    cfg = _config()
    long_out = _run(cfg, _long_held(), _schedule((23, "0.001")))
    short_out = _run(cfg, _short_held(), _schedule((23, "0.001")))
    # Long pays (positive funding_paid); short receives (negative funding_paid).
    assert long_out.summary["funding_paid"] > Decimal("0")
    assert short_out.summary["funding_paid"] < Decimal("0")
    # Short notional 98 * 50 = 4900 → receives 4.90.
    assert short_out.summary["funding_paid"] == Decimal("-4.90")


def test_funding_result_is_deterministic_across_batch_sizes() -> None:
    cfg = _config()
    bars = _long_held()
    sched = _schedule((22, "0.0003"), (23, "0.0007"), (24, "0.0005"))
    a = _run(cfg, bars, sched, batch=8)
    b = _run(cfg, bars, sched, batch=3)
    assert a.summary == b.summary
    assert a.diagnostics["funding_charges"] == b.diagnostics["funding_charges"] == 3


def test_empty_schedule_is_byte_identical_to_funding_off() -> None:
    cfg = _config()
    bars = _long_held()
    empty = FundingSchedule(source_revision_id="rd_1", records=())
    off = _run(cfg, bars, None)
    on = _run(cfg, bars, empty)
    assert on.summary["funding_paid"] == Decimal("0.00")
    assert on.summary == off.summary
    assert on.diagnostics["funding_charges"] == 0
    # funding_charge never appears in the trace when nothing fires.
    assert not any(e.event_type == "funding_charge" for e in on.signal_events)


def test_funding_charge_events_are_emitted_for_the_decision_trace() -> None:
    cfg = _config()
    out = _run(cfg, _long_held(), _schedule((23, "0.001")))
    charges = [e for e in out.signal_events if e.event_type == "funding_charge"]
    assert len(charges) == 1
    detail = charges[0].detail
    assert detail["rate"] == "0.001"
    assert detail["charge"] == "5.10"
    assert detail["source_revision_id"] == "rdrev_funding_1"
    assert detail["available_at"].startswith("2024-01-23")
    assert "bar_seq" in detail  # every event binds to its bar (F-10)
