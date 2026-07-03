"""Unit tests for the two-package indicator-vs-indicator condition RHS (Slice C
follow-up): a condition whose right-hand side is a SECOND, separately-pinned indicator
package computed inline (e.g. a fast-MA vs slow-MA cross).

Covers, in isolation from the DB:

* ``ConditionEvaluator`` with a ``reference_key`` — a self-computed reference indicator
  as the RHS: LEVEL (above) and EDGE (crosses_above) comparisons, warm-up fail-closed,
  and precedence over a configured constant ``threshold``;
* ``BlockEvaluator`` in ``condition_only`` mode driving the canonical fast-MA-crosses-
  slow-MA long signal (indicator_output source vs a reference-package slow MA).
"""

from __future__ import annotations

from decimal import Decimal

from entropia.domain.backtest.indicators import (
    BlockEvaluator,
    ConditionEvaluator,
    ConditionSpec,
    IndicatorSpec,
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


# ------------------------------------------------- reference-package RHS (level/edge)


def test_above_compares_source_against_a_reference_indicator_series() -> None:
    # close vs its own SMA(3): only once the SMA is warm AND close exceeds it.
    spec = _cond(canonical_key="cond.above", reference_key="ta.sma", reference_length=3)
    # SMA3: bar2 = 10 (close 10, not >); bar3 window[10,10,20]=13.33 (close 20 > 13.33).
    assert _feed(spec, ["10", "10", "10", "20"]) == [False, False, False, True]


def test_crosses_above_a_reference_indicator_series_fires_on_the_edge() -> None:
    # close crosses above its SMA(2). Warm-up + no-previous-pair fail closed; the fresh
    # upward crossing bar fires exactly once.
    spec = _cond(canonical_key="cond.crosses_above", reference_key="ta.sma", reference_length=2)
    # SMA2: b1=10 (c10, no prev pair), b2=9.5 (c9, 9<9.5), b3=10.5 (c12: prev 9<=9.5, 12>10.5).
    assert _feed(spec, ["10", "10", "9", "12"]) == [False, False, False, True]


def test_reference_indicator_warmup_none_fails_closed() -> None:
    # Before the reference SMA(4) is established its value is None -> RHS None -> closed.
    spec = _cond(canonical_key="cond.above", reference_key="ta.sma", reference_length=4)
    assert _feed(spec, ["10", "20", "30"]) == [False, False, False]


def test_reference_indicator_takes_precedence_over_a_constant_threshold() -> None:
    # An impossible constant threshold is IGNORED when a reference indicator is set; the
    # RHS is the SMA(2), so bar3 (close 20 > SMA 15) fires despite threshold 1000.
    spec = _cond(
        canonical_key="cond.above",
        threshold=Decimal("1000"),
        reference_key="ta.sma",
        reference_length=2,
    )
    assert _feed(spec, ["10", "10", "20"]) == [False, False, True]


def test_reference_rsi_key_builds_an_rsi_series() -> None:
    # A ta.rsi reference is computed as a Wilder RSI (0..100); with a flat-then-up close
    # stream it warms up and the check only evaluates once the RSI is defined.
    spec = _cond(canonical_key="cond.below", reference_key="ta.rsi", reference_length=2)
    # RSI(2) is None until 2 changes seen; all early bars fail closed (RHS None).
    out = _feed(spec, ["10", "11", "12"])
    assert out[0] is False and out[1] is False


# ----------------------------------------- condition_only fast-MA vs slow-MA crossover


def _block_signals(spec: IndicatorSpec, closes: list[str]) -> list[str | None]:
    ev = BlockEvaluator(spec)
    out: list[str | None] = []
    for c in closes:
        ev.update(Decimal(c))
        out.append(ev.current_signal)
    return out


def test_condition_only_fast_ma_crosses_slow_ma_fires_long() -> None:
    # The flagship: a fast SMA(2) block (native trigger IGNORED) driven by a required
    # ``indicator_output crosses_above`` a reference slow SMA(4) — a two-package MA cross.
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
                source="indicator_output",
                threshold=None,
                requirement="required",
                validity="1_candle",
                reference_key="ta.sma",
                reference_length=4,
            ),
        ),
    )
    # fast SMA(2) vs slow SMA(4): the fast average overtakes the slow one on bar4 (index 4).
    signals = _block_signals(block, ["10", "9", "8", "9", "12", "14"])
    assert signals == [None, None, None, None, "long", None]
