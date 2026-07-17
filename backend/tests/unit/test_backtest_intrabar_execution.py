"""F-07i (B) — real intrabar tick-path execution (unit, pure, no DB).

Covers the tick primitives (``_tick_epoch_ms`` / ``_normalize_tick`` /
``_TickCursor`` window alignment / ``_first_tick_touch``), the ``_resolve_stop``
``first_trigger_wins`` resolution by TRUE print order (vs the flagged conservative
OHLCV approximation), the engine-level flagship where the real first touch picks a
DIFFERENT stop than the conservative model (trailing lock above entry beats the
entry-tighter percentage stop), the tick-less byte-identical guarantee, and the
manifest ``tick_data`` reproducibility pin (execution_key namespace, INF-04/05).
"""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from typing import Any

from entropia.domain.backtest.engine import (
    EngineOutput,
    _Bar,
    _first_tick_touch,
    _normalize_tick,
    _Position,
    _resolve_stop,
    _Tick,
    _tick_epoch_ms,
    _TickCursor,
    run_engine,
)
from entropia.domain.backtest.manifest import build_run_manifest
from entropia.domain.strategy.config import StrategyConfig
from tests.unit.engine_signal_plan import sma_entry_plan

_ENTRY = Decimal("100")


# --------------------------------------------------------------------------- #
# Fixtures                                                                     #
# --------------------------------------------------------------------------- #


def _cfg(protection: dict[str, Any]) -> StrategyConfig:
    """A minimal VALID StrategyConfig; ``_resolve_stop`` only reads protection_stop_logic."""
    return StrategyConfig.model_validate(
        {
            "strategy_root_id": "strat_root_1",
            "display_name": "Intrabar Fixture",
            "rationale_family_id": "rf_1",
            "data": {
                "instrument_id": "BTCUSDT",
                "market_dataset_root_id": "md_root_1",
                "market_dataset_revision_id": "md_rev_1",
                "market_dataset_content_hash": "mdhash_1",
                "backtest_range": {"start": "2024-01-01T00:00:00Z", "end": "2024-12-31T23:59:59Z"},
                "initial_capital": "10000.00",
                "execution": {
                    "entry_timing": "current_candle_close",
                    "exit_timing": "current_candle_close",
                },
                "order_config": {"type": "market_order"},
                "costs": {"slippage_mode": "percentage_slippage", "slippage_value": "0"},
                "intrabar_policy": {"tick_policy": "require"},
                "funding": {"enabled": False},
            },
            "position_entry_logic": {
                "direction_mode": "long_and_short",
                "signal_block": {"rule": "required_indicator_blocks_only"},
                "indicator_blocks": [
                    {
                        "block_id": "blk_1",
                        "display_order": 0,
                        "package_ref": {
                            "package_root_id": "pkg_1",
                            "package_revision_id": "pkgrev_1",
                            "package_content_hash": "pkghash_1",
                        },
                        "trigger_source": "indicator_native_trigger",
                        "requirement": "required",
                    }
                ],
            },
            "position_exit_logic": {
                "applies_to_direction": "long_and_short",
                "close_percentage": "100",
            },
            "protection_stop_logic": protection,
            "position_sizing": {"method": "base_position_size", "base_position_size": "50"},
            "restrictions_filters": {"rule": "any", "filters": []},
            "conflict_position_handling": {},
        }
    )


_FIRST_TRIGGER = {
    "percentage_stop": {"enabled": True, "loss_percentage": "5.0"},
    "trailing_stop": {"enabled": True, "trail_percentage": "5.0", "lock_in_percentage": "2.0"},
    "stop_conflict_resolution": "first_trigger_wins",
}


def _pos_long_trailing() -> _Position:
    """Long from 100, trailing locked from a 115 anchor (level 108.25), pct stop at 95.

    Conservative (distance to ENTRY) picks percentage (|100-95|=5 < |100-108.25|=8.25);
    a falling continuous path touches trailing FIRST — the case the two models disagree."""
    return _Position(
        position_seq=1,
        entry_bar_seq=1,
        direction="long",
        entry_time="2024-01-01T00:00:00Z",
        entry_price=_ENTRY,
        size=Decimal("1"),
        pct_stop=Decimal("95"),
        abs_stop=None,
        trail_pct=Decimal("0.05"),
        trail_anchor=Decimal("115"),
        entry_notional=_ENTRY,
        trail_lock_in_pct=Decimal("0.02"),
    )


def _pos_short_trailing() -> _Position:
    """Short from 100, trailing locked from a 90 anchor (level 94.5), pct stop at 103."""
    return _Position(
        position_seq=1,
        entry_bar_seq=1,
        direction="short",
        entry_time="2024-01-01T00:00:00Z",
        entry_price=_ENTRY,
        size=Decimal("1"),
        pct_stop=Decimal("103"),
        abs_stop=None,
        trail_pct=Decimal("0.05"),
        trail_anchor=Decimal("90"),
        entry_notional=_ENTRY,
        trail_lock_in_pct=Decimal("0.02"),
    )


def _bar(low: str, high: str = "100", close: str = "98") -> _Bar:
    return _Bar(
        timestamp="2024-01-22T00:00:00Z",
        open=Decimal("100"),
        high=Decimal(high),
        low=Decimal(low),
        close=Decimal(close),
        volume=Decimal("10"),
    )


def _ticks(*prices: str) -> tuple[_Tick, ...]:
    return tuple(_Tick(epoch_ms=1000 * i, price=Decimal(p)) for i, p in enumerate(prices))


def _resolve(pos: _Position, bar: _Bar, ticks: tuple[_Tick, ...] = ()):
    return _resolve_stop(
        _cfg(_FIRST_TRIGGER), pos, bar, logic_enabled=[], logic_triggered=[], ticks=ticks
    )


# --------------------------------------------------------------------------- #
# Tick primitives                                                              #
# --------------------------------------------------------------------------- #


def test_tick_epoch_ms_parses_iso_epoch_seconds_and_millis() -> None:
    assert _tick_epoch_ms("2024-01-01T00:00:00Z") == 1704067200000
    assert _tick_epoch_ms("2024-01-01T00:00:00.250+00:00") == 1704067200250
    assert _tick_epoch_ms("1704067200") == 1704067200000  # bare epoch seconds
    assert _tick_epoch_ms("1704067200250") == 1704067200250  # bare epoch millis
    assert _tick_epoch_ms("not-a-time") is None
    assert _tick_epoch_ms("") is None


def test_normalize_tick_drops_unprovable_rows_fail_closed() -> None:
    assert _normalize_tick({"timestamp": "2024-01-01T00:00:00Z", "price": "101.5"}) == _Tick(
        epoch_ms=1704067200000, price=Decimal("101.5")
    )
    assert _normalize_tick({"price": "101.5"}) is None  # no timestamp
    assert _normalize_tick({"timestamp": "2024-01-01T00:00:00Z"}) is None  # no price
    assert _normalize_tick({"timestamp": "junk", "price": "101.5"}) is None
    assert _normalize_tick({"timestamp": "2024-01-01T00:00:00Z", "price": "0"}) is None
    assert _normalize_tick({"timestamp": "2024-01-01T00:00:00Z", "price": "abc"}) is None


def _row(ts: str, price: str) -> dict[str, Any]:
    return {"timestamp": ts, "price": price}


def _cursor(rows: list[dict[str, Any]], span: int = 60) -> _TickCursor:
    return _TickCursor(iter([rows]), span)


def test_cursor_assigns_prints_to_their_bar_windows() -> None:
    cursor = _cursor(
        [
            _row("2024-01-01T00:00:01Z", "101"),
            _row("2024-01-01T00:00:59Z", "102"),
            _row("2024-01-01T00:01:05Z", "103"),  # belongs to the NEXT 1m bar
        ]
    )
    first = cursor.for_bar("2024-01-01T00:00:00Z")
    assert [str(t.price) for t in first] == ["101", "102"]
    second = cursor.for_bar("2024-01-01T00:01:00Z")
    assert [str(t.price) for t in second] == ["103"]


def test_cursor_sorts_prints_within_one_window_stably() -> None:
    cursor = _cursor(
        [
            _row("2024-01-01T00:00:30Z", "105"),
            _row("2024-01-01T00:00:10Z", "104"),
            _row("2024-01-01T00:00:10Z", "104.5"),  # equal-ms keeps source order
        ]
    )
    prints = cursor.for_bar("2024-01-01T00:00:00Z")
    assert [str(t.price) for t in prints] == ["104", "104.5", "105"]


def test_cursor_drops_prints_behind_the_consumed_window_fail_closed() -> None:
    cursor = _cursor(
        [
            _row("2024-01-01T00:01:05Z", "103"),  # ahead: buffered for bar 2
            _row("2024-01-01T00:00:02Z", "101"),  # behind once bar 1 passed: dropped
        ]
    )
    assert cursor.for_bar("2024-01-01T00:00:00Z") == ()
    second = cursor.for_bar("2024-01-01T00:01:00Z")
    assert [str(t.price) for t in second] == ["103"]  # the stale 101 never resurfaces


def test_cursor_skips_unparseable_rows_and_unalignable_bars() -> None:
    cursor = _cursor([_row("junk", "101"), _row("2024-01-01T00:00:05Z", "102")])
    assert [str(t.price) for t in cursor.for_bar("2024-01-01T00:00:00Z")] == ["102"]
    assert _cursor([_row("2024-01-01T00:00:05Z", "102")]).for_bar("not-a-time") == ()


def test_first_tick_touch_gap_print_resolves_to_the_continuous_path_order() -> None:
    # One gap print through BOTH long stop levels resolves to the level a continuous
    # falling path would have touched first — the HIGHEST (trailing 108.25, not 95).
    levels = {"percentage": Decimal("95"), "trailing": Decimal("108.25")}
    winner = _first_tick_touch(
        levels, _ticks("94"), is_long=True, priority={"percentage": 0, "trailing": 1}
    )
    assert winner == "trailing"


# --------------------------------------------------------------------------- #
# _resolve_stop: first_trigger_wins by TRUE print order                        #
# --------------------------------------------------------------------------- #


def test_first_trigger_with_ticks_resolves_the_real_first_touch_long() -> None:
    # Falling path 111 -> 107 -> 94: 107 touches trailing (108.25) FIRST. The
    # conservative model would have picked the entry-tighter percentage (95).
    out = _resolve(_pos_long_trailing(), _bar(low="94"), _ticks("111", "107", "94"))
    assert out is not None
    assert out.tick_resolved is True
    assert out.approximated_first is False
    assert out.executed_key == "trailing"
    assert out.price == Decimal("115") * Decimal("0.95")


def test_first_trigger_with_ticks_resolves_the_real_first_touch_short() -> None:
    # Rising path 92 -> 95 -> 104: 95 touches the short trailing lock (94.5) FIRST;
    # conservative would have picked the entry-tighter percentage (103).
    out = _resolve(_pos_short_trailing(), _bar(low="92", high="104"), _ticks("92", "95", "104"))
    assert out is not None
    assert out.tick_resolved is True
    assert out.executed_key == "trailing"
    assert out.price == Decimal("90") * Decimal("1.05")


def test_first_trigger_without_ticks_stays_conservative_and_flagged() -> None:
    out = _resolve(_pos_long_trailing(), _bar(low="94"))
    assert out is not None
    assert out.approximated_first is True
    assert out.tick_resolved is False
    assert out.executed_key == "percentage"  # tightest to ENTRY — the OHLCV model
    assert out.price == Decimal("95")


def test_first_trigger_with_contradictory_ticks_falls_back_conservative() -> None:
    # The bar's low (94) triggered both stops but no print ever reaches a level —
    # the tick path contradicts the OHLC extremes, so the order stays unknowable.
    out = _resolve(_pos_long_trailing(), _bar(low="94"), _ticks("111", "110"))
    assert out is not None
    assert out.approximated_first is True
    assert out.tick_resolved is False
    assert out.executed_key == "percentage"


# --------------------------------------------------------------------------- #
# Engine-level flagship: the tick path changes the executed stop               #
# --------------------------------------------------------------------------- #


def _bars_trailing_vs_percentage() -> list[dict[str, Any]]:
    """20 flat bars -> breakout long at 102 -> rally arms the trailing lock -> stop bar.

    Stop bar levels: trailing = 115 * 0.95 = 109.25 (ABOVE entry — locked profit),
    percentage = 102 * 0.95 = 96.90 (tighter to entry). The bar's low (94) touches
    both. The entry is a real ta.sma(20) cross (see engine_signal_plan.py — F-24): the
    MA rests at the flat 100 baseline and the breakout bar crosses it; the follow-up
    closes stay above the MA, so nothing re-crosses it after the stop-out."""
    day = "2024-01-{0:02d}T00:00:00Z"
    bars = [
        {
            "timestamp": day.format(i + 1),
            "open": "100",
            "high": "100",
            "low": "100",
            "close": "100",
            "volume": "10",
        }
        for i in range(20)
    ]
    bars.append(
        {
            "timestamp": day.format(21),
            "open": "100",
            "high": "102",
            "low": "100",
            "close": "102",
            "volume": "10",
        }
    )  # breakout -> long at close 102
    bars.append(
        {
            "timestamp": day.format(22),
            "open": "110",
            "high": "115",
            "low": "110",
            "close": "112",
            "volume": "10",
        }
    )  # anchor 115; trailing arms at 109.25
    bars.append(
        {
            "timestamp": day.format(23),
            "open": "112",
            "high": "112",
            "low": "94",
            "close": "101",
            "volume": "10",
        }
    )  # touches trailing AND percentage
    return bars


def _stop_day_ticks() -> Iterator[list[dict[str, Any]]]:
    yield [
        _row("2024-01-23T00:30:00Z", "111"),  # no level touched yet
        _row("2024-01-23T01:00:00Z", "108"),  # first touch: trailing (108 <= 109.25)
        _row("2024-01-23T02:00:00Z", "94"),
    ]


def _run_flagship(*, ticks: bool, timeframe: str | None = "1D") -> EngineOutput:
    return run_engine(
        strategy_config=_cfg(_FIRST_TRIGGER),
        bar_batches=iter([_bars_trailing_vs_percentage()]),
        execution_key="exec_key_test",
        timeframe=timeframe,
        tick_batches=_stop_day_ticks() if ticks else None,
        indicator_plan=sma_entry_plan(),
    )


def test_engine_tick_path_executes_the_true_first_touch_stop() -> None:
    out = _run_flagship(ticks=True)
    assert out.summary["total_trades"] == 1
    trade = out.trades[0]
    assert trade.exit_reason == "stop_loss"
    assert trade.exit_price == Decimal("109.25")  # trailing — a LOCKED PROFIT exit
    assert trade.pnl > Decimal("0")
    assert out.diagnostics["tick_path_enabled"] is True
    assert out.diagnostics["tick_bars"] == 1
    assert out.diagnostics["tick_first_trigger_resolutions"] == 1
    resolution = [e for e in out.signal_events if e.event_type == "stop_resolution"]
    assert resolution and resolution[-1].detail["first_trigger_tick_resolved"] is True
    assert resolution[-1].detail["first_trigger_approximated"] is False
    assert resolution[-1].detail["executed"] == "trailing"


def test_engine_tickless_path_stays_byte_identical_conservative() -> None:
    out = _run_flagship(ticks=False)
    trade = out.trades[0]
    assert trade.exit_price == Decimal("102") * Decimal("0.95")  # percentage 96.90
    assert trade.pnl < Decimal("0")
    assert out.diagnostics["tick_path_enabled"] is False
    assert out.diagnostics["tick_bars"] == 0
    assert out.diagnostics["tick_first_trigger_resolutions"] == 0
    assert "tick_alignment_unavailable" not in out.diagnostics["warnings"]
    resolution = [e for e in out.signal_events if e.event_type == "stop_resolution"]
    assert resolution and resolution[-1].detail["first_trigger_approximated"] is True
    assert "first_trigger_tick_resolved" not in resolution[-1].detail


def test_engine_unalignable_timeframe_warns_and_stays_conservative() -> None:
    # Ticks injected but the revision has no supported bar timeframe: prints cannot
    # be attributed to bar windows -> conservative model + an honest L4 warning.
    out = _run_flagship(ticks=True, timeframe=None)
    trade = out.trades[0]
    assert trade.exit_price == Decimal("102") * Decimal("0.95")
    assert "tick_alignment_unavailable" in out.diagnostics["warnings"]
    assert out.diagnostics["tick_path_enabled"] is True
    assert out.diagnostics["tick_bars"] == 0
    assert out.diagnostics["tick_first_trigger_resolutions"] == 0


def test_engine_tick_run_is_deterministic() -> None:
    first = _run_flagship(ticks=True)
    second = _run_flagship(ticks=True)
    assert first.summary == second.summary
    assert [t.pnl for t in first.trades] == [t.pnl for t in second.trades]


# --------------------------------------------------------------------------- #
# Manifest: tick_data is REPRODUCIBILITY content (INF-04/05)                   #
# --------------------------------------------------------------------------- #


def _tick_manifest(tick_data: dict[str, Any] | None):
    return build_run_manifest(
        run_id="btrun_A",
        composition_id="mbws_1",
        composition_snapshot_id="snap_A",
        composition_fingerprint="fp_1",
        item_manifest={
            "items": [
                {
                    "item_id": "mbi_1",
                    "kind": "strategy",
                    "root_id": "wo_a",
                    "revision_id": "rev_a",
                    "position": 10,
                    "enabled": True,
                }
            ]
        },
        capital_mode={"enabled": False},
        requested_by_principal_id="user_1",
        preflight={"ready_report_id": "rcrpt_1", "state": "ready", "warning_count": 0},
        correlation_id="corr_1",
        created_at_iso="2024-01-01T00:00:00Z",
        tick_data=tick_data,
    )


def test_manifest_carries_the_tick_pin_and_shifts_the_execution_key() -> None:
    pin = {"mbi_1": {"tick_revision_id": "tick_rev_1", "instrument_id": "BTCUSDT"}}
    other = {"mbi_1": {"tick_revision_id": "tick_rev_2", "instrument_id": "BTCUSDT"}}
    with_pin = _tick_manifest(pin)
    assert with_pin.manifest["tick_data"] == pin
    assert _tick_manifest(None).manifest["tick_data"] is None
    # A different tick path must never share an execution_key (INF-04/05)...
    assert with_pin.execution_key != _tick_manifest(None).execution_key
    assert with_pin.execution_key != _tick_manifest(other).execution_key
    # ...while the same pin reproduces the same key.
    assert with_pin.execution_key == _tick_manifest(pin).execution_key
