"""F-07g — signal-strength adjustment engine tests (Master Ref §10.3, doc 02 §6).

The saved ``position_sizing.signal_strength_adjustment`` mode now EXECUTES:

* ``no_adjustment`` — inert (a 1x multiplier); byte-identical baseline.
* ``volatility_adjusted`` — a deterministic, config-free inverse-volatility multiplier
  computed at the SIGNAL bar from the bars already replayed (doc 02 §6's canonical
  example: "düşük volatilitede daha büyük, yüksek volatilitede daha küçük pozisyon").
  A calm recent tape relative to the look-back baseline reads as a STRONGER signal
  context (larger size, clamped at 2x); a turbulent one as WEAKER (smaller, clamped at
  0.5x). Look-back only — a deferred/limit fill inherits its signal bar's multiplier.
* ``trend_adjusted`` / ``divergence_adjusted`` — NOT modelled (the saved schema carries
  no condition refs / multiplier / band config to execute them) and FAIL CLOSED: a
  Ready Check blocker + an engine that opens no position.
"""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from typing import Any

from entropia.domain.backtest.engine import (
    EngineOutput,
    _Bar,
    _position_size,
    _volatility_strength,
    run_engine,
    signal_strength_is_modelled,
)
from entropia.domain.strategy.config import StrategyConfig
from tests.unit.engine_signal_plan import sma_entry_plan

_ZERO_COST = {"slippage_mode": "percentage_slippage", "slippage_value": "0"}


def _config(
    *,
    base_position_size: str = "10",
    signal_strength_adjustment: str = "no_adjustment",
    entry_timing: str = "current_candle_close",
    position_size_limits: dict[str, Any] | None = None,
) -> StrategyConfig:
    """A minimal VALID StrategyConfig; only the fields the engine reads matter.

    Zero costs so a fill lands exactly on the resolved price; no protection stops so a
    follow-up bar never closes the position before the assertions read it."""
    sizing: dict[str, Any] = {
        "method": "base_position_size",
        "base_position_size": base_position_size,
        "signal_strength_adjustment": signal_strength_adjustment,
    }
    if position_size_limits is not None:
        sizing["position_size_limits"] = position_size_limits
    return StrategyConfig.model_validate(
        {
            "strategy_root_id": "strat_root_1",
            "display_name": "Signal Strength Fixture",
            "rationale_family_id": "rf_1",
            "data": {
                "instrument_id": "BTCUSDT",
                "market_dataset_root_id": "md_root_1",
                "market_dataset_revision_id": "md_rev_1",
                "market_dataset_content_hash": "mdhash_1",
                "backtest_range": {
                    "start": "2024-01-01T00:00:00Z",
                    "end": "2024-12-31T23:59:59Z",
                },
                "initial_capital": "10000.00",
                "execution": {
                    "entry_timing": entry_timing,
                    "exit_timing": "current_candle_close",
                },
                "order_config": {"type": "market_order"},
                "costs": _ZERO_COST,
                "intrabar_policy": {"tick_policy": "inherit"},
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
                "partial_aftermath": "move_stop_to_entry",
            },
            "protection_stop_logic": {},
            "position_sizing": sizing,
            "restrictions_filters": {"rule": "any", "filters": []},
            "conflict_position_handling": {},
        }
    )


def _bar_dict(ts: str, o: str, h: str, low: str, c: str) -> dict[str, Any]:
    return {"timestamp": ts, "open": o, "high": h, "low": low, "close": c, "volume": "10"}


def _day(day: int, o: str, h: str, low: str, c: str) -> dict[str, Any]:
    return _bar_dict(f"2024-01-{day:02d}T00:00:00Z", o, h, low, c)


def _bars(*specs: tuple[str, str, str, str]) -> list[dict[str, Any]]:
    return [_day(i + 1, *spec) for i, spec in enumerate(specs)]


_WIDE = ("100", "104", "96", "100")  # relative range 8/100 = 0.08
_FLAT = ("100", "100", "100", "100")  # relative range 0
# Upside breakout above the fixtures' 104 window high (long signal @105), range 6/105.
_BREAKOUT = ("100", "106", "100", "105")


def _calm_recent() -> list[dict[str, Any]]:
    """Wide look-back baseline, calm recent tape -> strength clamps to the 2x max."""
    return _bars(*([_WIDE] * 15), *([_FLAT] * 5), _BREAKOUT)


def _turbulent_recent() -> list[dict[str, Any]]:
    """Calm look-back baseline, turbulent recent tape -> strength clamps to the 0.5x min."""
    return _bars(*([_FLAT] * 15), *([_WIDE] * 5), _BREAKOUT)


def _run(config: StrategyConfig, bars: list[dict[str, Any]], *, batch: int = 8) -> EngineOutput:
    def batched() -> Iterator[list[dict[str, Any]]]:
        for start in range(0, len(bars), batch):
            yield bars[start : start + batch]

    return run_engine(
        strategy_config=config,
        bar_batches=batched(),
        execution_key="exec_key_test",
        indicator_plan=sma_entry_plan(),
    )


def _event(out: EngineOutput, event_type: str) -> Any:
    return next(e for e in out.signal_events if e.event_type == event_type)


def _mk_bar(o: str, h: str, low: str, c: str) -> _Bar:
    return _Bar(
        timestamp="2024-01-01T00:00:00Z",
        open=Decimal(o),
        high=Decimal(h),
        low=Decimal(low),
        close=Decimal(c),
        volume=Decimal("10"),
    )


# --------------------------------------------------------------------------- #
# Predicate                                                                   #
# --------------------------------------------------------------------------- #


def test_strength_predicate_no_adjustment_and_volatility_are_modelled() -> None:
    assert signal_strength_is_modelled(_config(signal_strength_adjustment="no_adjustment"))
    assert signal_strength_is_modelled(_config(signal_strength_adjustment="volatility_adjusted"))


def test_strength_predicate_trend_and_divergence_are_not_modelled() -> None:
    assert not signal_strength_is_modelled(_config(signal_strength_adjustment="trend_adjusted"))
    assert not signal_strength_is_modelled(
        _config(signal_strength_adjustment="divergence_adjusted")
    )


# --------------------------------------------------------------------------- #
# Volatility multiplier — pure metric                                         #
# --------------------------------------------------------------------------- #


def test_volatility_strength_exact_mid_range_ratio() -> None:
    # Baseline mean range 0.07 over 20 bars, recent 5-bar mean 0.04 -> 1.75 exactly.
    history = tuple(
        [_mk_bar("100", "104", "96", "100")] * 15 + [_mk_bar("100", "102", "98", "100")] * 5
    )
    assert _volatility_strength(history) == Decimal("1.7500")


def test_volatility_strength_clamps_to_max_and_min() -> None:
    calm_recent = tuple(
        [_mk_bar("100", "104", "96", "100")] * 15 + [_mk_bar("100", "100.5", "99.5", "100")] * 5
    )
    assert _volatility_strength(calm_recent) == Decimal("2.0")
    turbulent_recent = tuple(
        [_mk_bar("100", "100.5", "99.5", "100")] * 15 + [_mk_bar("100", "110", "90", "100")] * 5
    )
    assert _volatility_strength(turbulent_recent) == Decimal("0.5")


def test_volatility_strength_warm_up_and_degenerate_tapes_are_neutral() -> None:
    wide = _mk_bar("100", "104", "96", "100")
    assert _volatility_strength(tuple([wide] * 19)) == Decimal("1")  # warm-up
    flat = _mk_bar("100", "100", "100", "100")
    assert _volatility_strength(tuple([flat] * 20)) == Decimal("1")  # zero volatility
    broken = _mk_bar("100", "104", "96", "0")
    assert _volatility_strength(tuple([wide] * 19 + [broken])) == Decimal("1")  # bad close


# --------------------------------------------------------------------------- #
# Sizing composition — strength scales, limits stay the final word            #
# --------------------------------------------------------------------------- #


def test_position_size_scales_by_strength_multiplier() -> None:
    config = _config(base_position_size="10")
    price, equity = Decimal("100"), Decimal("10000")
    assert _position_size(config, price, equity, Decimal("2.0")) == Decimal("20")
    assert _position_size(config, price, equity, Decimal("0.5")) == Decimal("5")


def test_position_size_limits_cap_a_strength_boosted_size() -> None:
    config = _config(base_position_size="10", position_size_limits={"max_position_size": "15"})
    assert _position_size(config, Decimal("100"), Decimal("10000"), Decimal("2.0")) == Decimal("15")


# --------------------------------------------------------------------------- #
# Engine — positive: strong context sizes up, weak context sizes down         #
# --------------------------------------------------------------------------- #


def test_strong_signal_calm_recent_tape_doubles_position_size() -> None:
    out = _run(_config(signal_strength_adjustment="volatility_adjusted"), _calm_recent())
    signal = _event(out, "entry_signal")
    assert signal.detail["signal_strength"] == {
        "mode": "volatility_adjusted",
        "multiplier": "2.0",
    }
    fill = _event(out, "entry_fill")
    assert Decimal(fill.detail["size"]) == Decimal("20")
    assert out.diagnostics["signal_strength_mode"] == "volatility_adjusted"
    assert out.diagnostics["signal_strength_modelled"] is True
    assert out.diagnostics["strength_adjustments"] == 1


def test_weak_signal_turbulent_recent_tape_halves_position_size() -> None:
    out = _run(_config(signal_strength_adjustment="volatility_adjusted"), _turbulent_recent())
    signal = _event(out, "entry_signal")
    assert signal.detail["signal_strength"]["multiplier"] == "0.5"
    fill = _event(out, "entry_fill")
    assert Decimal(fill.detail["size"]) == Decimal("5")
    assert out.diagnostics["strength_adjustments"] == 1


def test_no_adjustment_stays_byte_identical_baseline() -> None:
    out = _run(_config(signal_strength_adjustment="no_adjustment"), _turbulent_recent())
    signal = _event(out, "entry_signal")
    assert "signal_strength" not in signal.detail
    fill = _event(out, "entry_fill")
    assert Decimal(fill.detail["size"]) == Decimal("10")
    assert out.diagnostics["signal_strength_mode"] == "no_adjustment"
    assert out.diagnostics["signal_strength_modelled"] is True
    assert out.diagnostics["strength_adjustments"] == 0


def test_uniform_tape_resolves_neutral_and_is_not_counted() -> None:
    # 20 identical-range bars + a breakout bar with the SAME relative range (8.4/105 =
    # 0.08) -> short and long windows agree -> exactly 1x, traced but never counted.
    bars = _bars(*([_WIDE] * 20), ("100", "108.4", "100", "105"))
    out = _run(_config(signal_strength_adjustment="volatility_adjusted"), bars)
    signal = _event(out, "entry_signal")
    assert signal.detail["signal_strength"]["multiplier"] == "1.0000"
    fill = _event(out, "entry_fill")
    assert Decimal(fill.detail["size"]) == Decimal("10")
    assert out.diagnostics["strength_adjustments"] == 0


def test_deferred_fill_inherits_the_signal_bars_strength() -> None:
    # next_candle_open: the fill lands on bar 22 (a violent bar); the size still uses the
    # SIGNAL bar's 2x multiplier — recomputing at the fill bar would NOT clamp to 2x.
    bars = [*_calm_recent(), _day(22, "105", "120", "100", "105")]
    out = _run(
        _config(
            signal_strength_adjustment="volatility_adjusted",
            entry_timing="next_candle_open",
        ),
        bars,
    )
    fill = _event(out, "entry_fill")
    assert fill.detail["deferred"] is True
    assert Decimal(fill.detail["size"]) == Decimal("20")
    assert out.diagnostics["deferred_entry_fills"] == 1


# --------------------------------------------------------------------------- #
# Engine — negative: unsupported modes fail closed                            #
# --------------------------------------------------------------------------- #


def test_trend_adjusted_mode_opens_no_position() -> None:
    out = _run(_config(signal_strength_adjustment="trend_adjusted"), _calm_recent())
    assert out.diagnostics["signal_strength_modelled"] is False
    assert out.summary["total_trades"] == 0
    assert "signal_strength_unsupported:trend_adjusted" in out.diagnostics["warnings"]
    blocked = _event(out, "entry_blocked")
    assert blocked.detail["reason"] == "signal_strength_unsupported"


def test_divergence_adjusted_mode_opens_no_position() -> None:
    out = _run(_config(signal_strength_adjustment="divergence_adjusted"), _calm_recent())
    assert out.summary["total_trades"] == 0
    assert "signal_strength_unsupported:divergence_adjusted" in out.diagnostics["warnings"]
