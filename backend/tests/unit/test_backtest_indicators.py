"""Unit tests for the built-in TA compute + native-trigger layer (post-V1 Slice C).

Covers: MA/RSI value correctness (hand-verified references + monotonic invariants),
native-trigger cross detection (MA price-cross, RSI band-cross), the validity window
countdown, the block direction filter, and signal-block aggregation rules."""

from __future__ import annotations

from decimal import Decimal

import pytest

from entropia.domain.backtest.indicators import (
    BUILTIN_ENTRY_MODEL,
    DIRECTIONAL_KEYS,
    RECOGNIZED_KEYS,
    BlockEvaluator,
    IndicatorPlan,
    IndicatorSpec,
    SignalRule,
    _MovingAverage,
    _Rsi,
    aggregate,
    build_evaluators,
    default_length,
)


def _feed_ma(key: str, length: int, closes: list[str]) -> list[Decimal | None]:
    ma = _MovingAverage(key, length)
    return [ma.update(Decimal(c)) for c in closes]


def _feed_rsi(length: int, closes: list[str]) -> list[Decimal | None]:
    rsi = _Rsi(length)
    return [rsi.update(Decimal(c)) for c in closes]


def _signals(spec: IndicatorSpec, closes: list[str]) -> list[str | None]:
    ev = BlockEvaluator(spec)
    out: list[str | None] = []
    for c in closes:
        ev.update(Decimal(c))
        out.append(ev.current_signal)
    return out


def _spec(**kw: object) -> IndicatorSpec:
    base: dict[str, object] = {
        "block_id": "b1",
        "canonical_key": "ta.sma",
        "length": 3,
        "direction": "long_and_short",
        "requirement": "required",
        "validity": "1_candle",
    }
    base.update(kw)
    return IndicatorSpec(**base)  # type: ignore[arg-type]


# --------------------------------------------------------------------------- MA value


def test_sma_warms_up_then_averages_window() -> None:
    values = _feed_ma("ta.sma", 3, ["1", "2", "3", "4"])
    assert values[0] is None and values[1] is None
    assert values[2] == Decimal("2")  # mean(1,2,3)
    assert values[3] == Decimal("3")  # mean(2,3,4)


def test_wma_weights_recent_close_highest() -> None:
    values = _feed_ma("ta.wma", 3, ["1", "2", "3"])
    assert values[2] == Decimal(14) / Decimal(6)  # (1*1 + 2*2 + 3*3) / (1+2+3)


def test_ema_seeds_from_sma_then_smooths() -> None:
    values = _feed_ma("ta.ema", 3, ["1", "2", "3", "4"])
    assert values[2] == Decimal("2")  # seed = SMA(1,2,3)
    assert values[3] == Decimal("3")  # 2 + (2/4)*(4-2)


def test_rma_seeds_from_sma_then_wilder_smooths() -> None:
    values = _feed_ma("ta.rma", 3, ["1", "2", "3", "4"])
    assert values[2] == Decimal("2")  # seed = SMA(1,2,3)
    assert values[3] == (Decimal("2") * Decimal(2) + Decimal("4")) / Decimal(3)  # 8/3


# --------------------------------------------------------------------------- RSI value


def test_rsi_all_up_series_is_100() -> None:
    values = _feed_rsi(3, ["1", "2", "3", "4", "5", "6"])
    assert values[-1] == Decimal("100")  # avg_loss == 0


def test_rsi_all_down_series_is_0() -> None:
    values = _feed_rsi(3, ["6", "5", "4", "3", "2", "1"])
    assert values[-1] == Decimal("0")  # avg_gain == 0


def test_rsi_none_until_length_changes_seen() -> None:
    values = _feed_rsi(3, ["10", "11", "12"])  # only 2 changes < length 3
    assert values == [None, None, None]


# --------------------------------------------------------------------- native triggers


def test_ma_cross_up_fires_long_and_cross_down_fires_short() -> None:
    # SMA len 3 over [10,10,10,9,11]: bar4 crosses below -> short, bar5 above -> long.
    signals = _signals(_spec(canonical_key="ta.sma", length=3), ["10", "10", "10", "9", "11"])
    assert signals[3] == "short"
    assert signals[4] == "long"


def test_rsi_band_cross_up_fires_long() -> None:
    # len 2: drop to RSI 0 (oversold), then recover crossing back above 30 -> long.
    signals = _signals(_spec(canonical_key="ta.rsi", length=2), ["100", "90", "80", "100"])
    assert signals[-1] == "long"


def test_direction_filter_suppresses_disallowed_side() -> None:
    # A long-only block never emits the short that the raw cross would produce.
    signals = _signals(
        _spec(canonical_key="ta.sma", length=3, direction="long"),
        ["10", "10", "10", "9", "11"],
    )
    assert signals[3] is None  # short cross suppressed
    assert signals[4] == "long"


# --------------------------------------------------------------------- validity window


def test_validity_three_candles_stays_active_for_three_bars() -> None:
    # A long fires on bar5; with 3_candles it stays active bars 5,6,7 then clears.
    closes = ["10", "10", "10", "9", "11", "11", "11", "11"]
    signals = _signals(_spec(canonical_key="ta.sma", length=3, validity="3_candles"), closes)
    assert signals[4] == "long"  # fire
    assert signals[5] == "long"
    assert signals[6] == "long"
    assert signals[7] is None  # expired after 3 bars


def test_validity_current_candle_only_active_one_bar() -> None:
    closes = ["10", "10", "10", "9", "11", "11"]
    signals = _signals(
        _spec(canonical_key="ta.sma", length=3, validity="current_candle_only"), closes
    )
    assert signals[4] == "long"
    assert signals[5] is None


# ------------------------------------------------------------------------- aggregation


def test_required_only_fires_when_all_required_agree() -> None:
    rule = SignalRule(rule="required_indicator_blocks_only")
    evs = build_evaluators(
        (_spec(block_id="a", canonical_key="ta.sma", length=3, validity="until_opposite_signal"),)
    )
    for c in ["10", "10", "10", "9", "11"]:
        for ev in evs:
            ev.update(Decimal(c))
    assert aggregate(rule, evs) == "long"


def test_min_supporting_requires_enough_confirmations() -> None:
    rule = SignalRule(rule="required_plus_min_supporting", min_supporting_count=1)
    required = _spec(block_id="r", requirement="required", validity="until_opposite_signal")
    supporting = _spec(block_id="s", requirement="supporting", validity="until_opposite_signal")
    evs = build_evaluators((required, supporting))
    # Feed only the required a cross; supporting stays flat -> not enough support.
    for ev, series in zip(
        evs, [["10", "10", "10", "9", "11"], ["5", "5", "5", "5", "5"]], strict=True
    ):
        for c in series:
            ev.update(Decimal(c))
    assert aggregate(rule, evs) is None  # required fired but no supporting confirmation


def test_all_confirmations_requires_every_supporting() -> None:
    rule = SignalRule(rule="required_plus_all_confirmations")
    a = _spec(block_id="a", requirement="required", validity="until_opposite_signal")
    b = _spec(block_id="b", requirement="supporting", validity="until_opposite_signal")
    evs = build_evaluators((a, b))
    for ev in evs:
        for c in ["10", "10", "10", "9", "11"]:
            ev.update(Decimal(c))
    assert aggregate(rule, evs) == "long"  # both crossed identically -> confirmed


def test_empty_evaluators_never_signal() -> None:
    assert aggregate(SignalRule(rule="required_indicator_blocks_only"), []) is None


# ------------------------------------------------------------------------------- misc


def test_plan_has_entry_reflects_specs() -> None:
    empty = IndicatorPlan(
        entry_rule=SignalRule(rule="required_indicator_blocks_only"), entry_specs=()
    )
    assert empty.has_entry is False
    filled = IndicatorPlan(
        entry_rule=SignalRule(rule="required_indicator_blocks_only"),
        entry_specs=(_spec(),),
    )
    assert filled.has_entry is True


def test_default_length_matches_key() -> None:
    assert default_length("ta.rsi") == 14
    assert default_length("ta.sma") == 20


def test_recognized_key_sets_are_coherent() -> None:
    assert "ta.rsi" in DIRECTIONAL_KEYS
    assert DIRECTIONAL_KEYS <= RECOGNIZED_KEYS
    assert BUILTIN_ENTRY_MODEL.startswith("builtin_indicator")


@pytest.mark.parametrize("key", sorted(DIRECTIONAL_KEYS))
def test_every_directional_key_computes_without_error(key: str) -> None:
    signals = _signals(_spec(canonical_key=key, length=3), ["10", "11", "12", "10", "13", "9"])
    assert all(s in (None, "long", "short") for s in signals)
