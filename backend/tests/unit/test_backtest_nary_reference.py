"""Unit tests for the N-ary reference chain (post-V1 Slice C follow-up (ii)): a condition
whose right-hand side is an ORDERED chain of >2 separately-pinned indicator packages
(e.g. a fast-MA vs slow-MA vs slowest-MA fan), extending the two-package (#53) form.

Covers, in isolation from the DB:

* ``ConditionEvaluator`` with ``extra_references`` — LEVEL (above/below) monotonic chains,
  EDGE (crosses_above/below) alignment fires, N-ary being strictly stronger than the single
  reference, and a warming-up leg failing the whole chain closed;
* ``BlockEvaluator`` in ``condition_only`` mode driving a three-MA fan crossover long.
"""

from __future__ import annotations

from decimal import Decimal

from entropia.domain.backtest.indicators import (
    BlockEvaluator,
    ConditionEvaluator,
    ConditionSpec,
    IndicatorSpec,
    ReferenceSeriesSpec,
)


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


def _feed(spec: ConditionSpec, closes: list[str]) -> list[bool]:
    ce = ConditionEvaluator(spec)
    out: list[bool] = []
    for c in closes:
        value = Decimal(c)
        ce.update(close=value, high=value, low=value, open_price=value, indicator_value=value)
        out.append(ce.satisfied)
    return out


# ---------------------------------------------------------------- N-ary LEVEL chains


def test_above_requires_the_full_descending_fan() -> None:
    # close > SMA(2) > SMA(4): the price leads a stacked (fanned) pair of averages.
    spec = _cond(
        canonical_key="cond.above",
        reference_key="ta.sma",
        reference_length=2,
        extra_references=(ReferenceSeriesSpec(key="ta.sma", length=4),),
    )
    # rising 10..50: SMA4 warms at bar3, where 40 > SMA2 35 > SMA4 25.
    assert _feed(spec, ["10", "20", "30", "40", "50"]) == [False, False, False, True, True]


def test_below_requires_the_full_ascending_fan() -> None:
    spec = _cond(
        canonical_key="cond.below",
        reference_key="ta.sma",
        reference_length=2,
        extra_references=(ReferenceSeriesSpec(key="ta.sma", length=4),),
    )
    # falling 50..10: bar3 has 20 < SMA2 25 < SMA4 35.
    assert _feed(spec, ["50", "40", "30", "20", "10"]) == [False, False, False, True, True]


def test_nary_is_stricter_than_the_single_reference_form() -> None:
    # close > SMA(2) holds, but SMA(2) > SMA(3) does NOT (averages not yet fanned): the
    # single-reference (#53) form fires, the N-ary chain stays closed.
    single = _cond(canonical_key="cond.above", reference_key="ta.sma", reference_length=2)
    nary = _cond(
        canonical_key="cond.above",
        reference_key="ta.sma",
        reference_length=2,
        extra_references=(ReferenceSeriesSpec(key="ta.sma", length=3),),
    )
    closes = ["30", "20", "10", "25"]
    assert _feed(single, closes)[-1] is True  # close 25 > SMA2 17.5
    assert _feed(nary, closes)[-1] is False  # ...but SMA2 17.5 < SMA3 18.33 -> broken


# ----------------------------------------------------------------- N-ary EDGE crosses


def test_crosses_above_fires_when_the_fan_aligns_this_bar() -> None:
    spec = _cond(
        canonical_key="cond.crosses_above",
        reference_key="ta.sma",
        reference_length=2,
        extra_references=(ReferenceSeriesSpec(key="ta.sma", length=4),),
    )
    # flat 10s (fan flat, not strict) then a jump to 20 aligns the fan bullishly on bar4.
    assert _feed(spec, ["10", "10", "10", "10", "20"]) == [False, False, False, False, True]


def test_crosses_below_fires_when_the_fan_aligns_bearishly() -> None:
    spec = _cond(
        canonical_key="cond.crosses_below",
        reference_key="ta.sma",
        reference_length=2,
        extra_references=(ReferenceSeriesSpec(key="ta.sma", length=4),),
    )
    assert _feed(spec, ["10", "10", "10", "10", "5"]) == [False, False, False, False, True]


def test_a_warming_up_leg_fails_the_whole_chain_closed() -> None:
    # The slowest leg (SMA 6) never warms over 4 bars -> its None value breaks the chain.
    spec = _cond(
        canonical_key="cond.above",
        reference_key="ta.sma",
        reference_length=2,
        extra_references=(ReferenceSeriesSpec(key="ta.sma", length=6),),
    )
    assert _feed(spec, ["10", "20", "30", "40"]) == [False, False, False, False]


# ------------------------------------------ condition_only three-MA fan crossover long


def _block_signals(spec: IndicatorSpec, closes: list[str]) -> list[str | None]:
    ev = BlockEvaluator(spec)
    out: list[str | None] = []
    for c in closes:
        ev.update(Decimal(c))
        out.append(ev.current_signal)
    return out


def test_condition_only_three_ma_fan_crossover_fires_long() -> None:
    # A condition-only block whose required ``close crosses_above SMA(3) > SMA(4)`` fan
    # aligns on bar4 (the native SMA(2) trigger is ignored) -> one long edge.
    block = IndicatorSpec(
        block_id="b",
        canonical_key="ta.sma",
        length=2,
        direction="long_and_short",
        requirement="required",
        validity="1_candle",
        condition_only=True,
        conditions=(
            ConditionSpec(
                condition_block_id="c",
                canonical_key="cond.crosses_above",
                source="close",
                threshold=None,
                requirement="required",
                validity="1_candle",
                reference_key="ta.sma",
                reference_length=3,
                extra_references=(ReferenceSeriesSpec(key="ta.sma", length=4),),
            ),
        ),
    )
    assert _block_signals(block, ["10", "10", "10", "10", "20"]) == [None, None, None, None, "long"]
