"""Unit tests for the VWAP directional key (post-V1 Slice C follow-up (d)).

``ta.vwap`` becomes a ``DIRECTIONAL_KEYS`` member: a rolling, volume-weighted price line
whose price/VWAP cross is a native directional trigger (same shape as an MA cross), and
which is usable as a condition's reference-package RHS and as an N-ary reference chain leg.

Covers, in isolation from the DB:

* the incremental ``_Vwap`` compute — volume weighting (vs an equal-weight SMA), typical
  price ``(H+L+C)/3``, warm-up, and the zero-volume fail-closed guard;
* a ``BlockEvaluator`` VWAP block firing long/short on a price/VWAP cross, the direction
  filter, and the honest no-signal when volume is absent;
* VWAP as a condition reference leg (two-package) and as an N-ary chain leg;
* a resampled VWAP reference leg summing volume across its coarser reference candle.
"""

from __future__ import annotations

from decimal import Decimal

from entropia.domain.backtest.indicators import (
    DIRECTIONAL_KEYS,
    NON_DIRECTIONAL_KEYS,
    VOLUME_WEIGHTED_KEYS,
    BlockEvaluator,
    ConditionEvaluator,
    ConditionSpec,
    IndicatorSpec,
    ReferenceSeriesSpec,
    _ReferenceSeries,
    _Vwap,
)

_D = Decimal


# --------------------------------------------------------------- key-set membership


def test_vwap_is_directional_and_atr_stays_non_directional() -> None:
    # (d): vwap moves into the directional family; atr remains recognized-but-non-directional.
    assert "ta.vwap" in DIRECTIONAL_KEYS
    assert "ta.vwap" in VOLUME_WEIGHTED_KEYS
    assert "ta.atr" in NON_DIRECTIONAL_KEYS
    assert "ta.atr" not in DIRECTIONAL_KEYS
    assert "ta.vwap" not in NON_DIRECTIONAL_KEYS


# --------------------------------------------------------------- _Vwap compute


def _feed_vwap(vwap: _Vwap, candles: list[tuple[str, str, str, str]]) -> list[Decimal | None]:
    # candles: (close, high, low, volume)
    return [vwap.update(_D(c), _D(h), _D(low), _D(v)) for c, h, low, v in candles]


def test_vwap_value_is_volume_weighted_not_a_plain_mean() -> None:
    # length-2 window, typical = close (H=L=C). Equal weight would give SMA 15; the
    # 3x-volume bar at 20 pulls the VWAP to (10*1 + 20*3)/(1+3) = 17.5.
    out = _feed_vwap(_Vwap(2), [("10", "10", "10", "1"), ("20", "20", "20", "3")])
    assert out == [None, _D("17.5")]


def test_vwap_typical_price_uses_hlc3_not_close() -> None:
    # Both closes are 10, but bar B has a high of 16 -> typical (16+10+10)/3 = 12; with
    # equal volume VWAP(2) = (10 + 12)/2 = 11. Close-only would give 10, so this proves HLC/3.
    out = _feed_vwap(_Vwap(2), [("10", "10", "10", "1"), ("10", "16", "10", "1")])
    assert out == [None, _D("11")]


def test_vwap_warms_up_over_length_candles() -> None:
    vwap = _Vwap(3)
    out = _feed_vwap(
        vwap, [("10", "10", "10", "1"), ("11", "11", "11", "1"), ("12", "12", "12", "1")]
    )
    assert out[0] is None and out[1] is None
    assert out[2] == _D("11")  # (10+11+12)/3 with equal volume


def test_vwap_zero_volume_window_fails_closed() -> None:
    # No volume in the window -> the volume-weighted mean is undefined -> value None
    # (never a divide-by-zero, never a phantom line).
    out = _feed_vwap(_Vwap(2), [("10", "10", "10", "0"), ("20", "20", "20", "0")])
    assert out == [None, None]


# --------------------------------------------------------------- VWAP native trigger


def _vwap_block_signals(
    spec: IndicatorSpec, bars: list[tuple[str, str, str, str]]
) -> list[str | None]:
    # bars: (close, high, low, volume); open defaults to close
    ev = BlockEvaluator(spec)
    out: list[str | None] = []
    for c, h, low, v in bars:
        ev.update(_D(c), _D(h), _D(low), _D(c), volume=_D(v))
        out.append(ev.current_signal)
    return out


def _vwap_block(direction: str = "long_and_short") -> IndicatorSpec:
    return IndicatorSpec(
        block_id="b",
        canonical_key="ta.vwap",
        length=2,
        direction=direction,
        requirement="required",
        validity="1_candle",
    )


def test_vwap_block_fires_long_when_price_crosses_up_through_the_line() -> None:
    # Flat 10s (VWAP 10), then a jump to 20 on bar 3: close 20 > VWAP 15 while the prior
    # close sat on the line -> an upward price/VWAP cross -> long.
    bars = [("10", "10", "10", "1")] * 3 + [("20", "20", "20", "1")]
    assert _vwap_block_signals(_vwap_block(), bars) == [None, None, None, "long"]


def test_vwap_block_fires_short_when_price_crosses_down_through_the_line() -> None:
    bars = [("20", "20", "20", "1")] * 3 + [("10", "10", "10", "1")]
    assert _vwap_block_signals(_vwap_block(), bars) == [None, None, None, "short"]


def test_vwap_block_direction_filter_suppresses_the_disallowed_side() -> None:
    # A long-only block ignores the downward (short) cross.
    bars = [("20", "20", "20", "1")] * 3 + [("10", "10", "10", "1")]
    assert _vwap_block_signals(_vwap_block("long"), bars) == [None, None, None, None]


def test_vwap_block_with_zero_volume_yields_no_signal() -> None:
    # Volume-less bars leave the VWAP line undefined, so no cross is ever detected — the
    # block resolves but honestly produces no phantom entries.
    bars = [("10", "10", "10", "0")] * 3 + [("20", "20", "20", "0")]
    assert _vwap_block_signals(_vwap_block(), bars) == [None, None, None, None]


# --------------------------------------------------------------- VWAP as a reference RHS


def _cond(**kw: object) -> ConditionSpec:
    base: dict[str, object] = {
        "condition_block_id": "c1",
        "canonical_key": "cond.above",
        "source": "close",
        "threshold": None,
        "requirement": "required",
        "validity": "current_candle_only",
    }
    base.update(kw)
    return ConditionSpec(**base)  # type: ignore[arg-type]


def _feed_cond(spec: ConditionSpec, bars: list[tuple[str, str]]) -> list[bool]:
    # bars: (close, volume); high=low=close
    ce = ConditionEvaluator(spec)
    out: list[bool] = []
    for c, v in bars:
        val = _D(c)
        ce.update(close=val, high=val, low=val, open_price=val, indicator_value=val, volume=_D(v))
        out.append(ce.satisfied)
    return out


def test_condition_reference_leg_can_be_a_vwap_series() -> None:
    # cond.above with a VWAP(2) reference RHS: close vs the volume-weighted line. Once warm,
    # close 20 exceeds VWAP (10*1 + 20*3)/4 = 17.5 -> satisfied.
    spec = _cond(canonical_key="cond.above", reference_key="ta.vwap", reference_length=2)
    assert _feed_cond(spec, [("10", "1"), ("10", "1"), ("20", "3")]) == [False, False, True]


def test_nary_chain_leg_can_be_a_vwap_series() -> None:
    # source > primary SMA(2) > extra VWAP(2) — a descending fan mixing an MA and a VWAP
    # leg. With the lower price carrying the heavier volume, VWAP(2) 12.5 sits under SMA(2)
    # 15, so on bar 2 (close 20) the strict chain 20 > 15 > 12.5 holds.
    spec = _cond(
        canonical_key="cond.above",
        reference_key="ta.sma",
        reference_length=2,
        extra_references=(ReferenceSeriesSpec(key="ta.vwap", length=2),),
    )
    assert _feed_cond(spec, [("10", "3"), ("20", "1")]) == [False, True]


def test_resampled_vwap_reference_leg_sums_volume_across_the_candle() -> None:
    # A VWAP(1) reference leg on a 1-minute reference candle. Two base bars aggregate into
    # one candle (high=13, low=10, close=13, volume=2+2=4 -> typical (13+10+13)/3 = 12); the
    # leg advances only when the candle CLOSES (the first bar of the next minute), so it is
    # None until then (no look-ahead) and equals the volume-weighted candle price after.
    leg = _ReferenceSeries(_Vwap(1), resample_seconds=60)
    leg.advance(_D("10"), _D("10"), _D("10"), _D("2"), "2026-01-01T00:00:00Z")
    leg.advance(_D("13"), _D("13"), _D("13"), _D("2"), "2026-01-01T00:00:30Z")
    assert leg.value is None  # candle still forming -> no repaint
    leg.advance(_D("100"), _D("100"), _D("100"), _D("1"), "2026-01-01T00:01:00Z")
    assert leg.value == _D("12")
