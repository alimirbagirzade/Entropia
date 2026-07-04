"""Per-condition multi-timeframe reference unit tests (post-V1 Slice C follow-up (i)) — DB-free.

A nested condition's RHS reference indicator (``reference_key`` — the two-package
indicator-vs-indicator form) may compute on a timeframe COARSER than its parent block:
the fast ``source`` is compared against a slower reference series that only advances when
a reference candle CLOSES (no look-ahead / no repaint). These tests pin: the RHS held
constant within a forming reference candle, byte-identical behaviour when the reference
timeframe equals the block (``None`` span), fail-closed when timestamps are absent, the
causal timing of a multi-timeframe cross, and the full BlockEvaluator -> ConditionEvaluator
timestamp plumbing for a condition-only signal.
"""

from __future__ import annotations

from decimal import Decimal

from entropia.domain.backtest.indicators import (
    BlockEvaluator,
    ConditionEvaluator,
    ConditionSpec,
    IndicatorSpec,
)

_2H = 7200  # two 1-hour base bars per reference candle at wall-clock 2h boundaries


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


def _hourly(closes: list[str]) -> list[tuple[str, Decimal]]:
    """(ISO hourly timestamp, close) pairs, one per hour from 2024-01-01T00:00Z."""
    return [(f"2024-01-01T{h:02d}:00:00Z", Decimal(c)) for h, c in enumerate(closes)]


def _feed_ts(spec: ConditionSpec, bars: list[tuple[str, Decimal]]) -> list[bool]:
    ce = ConditionEvaluator(spec)
    out: list[bool] = []
    for ts, close in bars:
        ce.update(
            close=close,
            high=close,
            low=close,
            open_price=close,
            indicator_value=close,
            timestamp=ts,
        )
        out.append(ce.satisfied)
    return out


# --------------------------------------------------- RHS held within a reference candle


def test_reference_resample_holds_rhs_within_a_forming_candle() -> None:
    # cond.above close vs a 2h SMA(1) reference (SMA(1) == the reference candle's close).
    # The RHS only advances when a 2h candle CLOSES (first bar of the next bucket), so it
    # is HELD constant across the two hourly bars of a forming candle — no repaint.
    spec = _cond(
        canonical_key="cond.above",
        reference_key="ta.sma",
        reference_length=1,
        reference_resample_seconds=_2H,
    )
    # bars 0-1: RHS not yet closed -> None -> closed. bar2 closes candle0 (RHS=10), close 20>10.
    # bar3 (forming candle1): RHS STILL 10 -> 20>10 True. bar4 closes candle1 (RHS=20): 20>20 False.
    assert _feed_ts(spec, _hourly(["10", "10", "20", "20", "20", "20"])) == [
        False,
        False,
        True,
        True,
        False,
        False,
    ]


def test_base_tf_reference_would_never_be_above_its_own_sma1() -> None:
    # Sanity contrast: with the RHS on the block timeframe (no resample), SMA(1) == close ==
    # source every bar, so close is never strictly ABOVE it. The resample above is what
    # makes the comparison meaningful (a slower, held reference).
    spec = _cond(
        canonical_key="cond.above",
        reference_key="ta.sma",
        reference_length=1,
        reference_resample_seconds=None,
    )
    assert _feed_ts(spec, _hourly(["10", "10", "20", "20", "20", "20"])) == [False] * 6


# ------------------------------------------------- byte-identical when span is None


def test_reference_resample_none_ignores_timestamp() -> None:
    # reference_resample_seconds=None is the (#53) two-package behaviour: the RHS ticks with
    # the block, so feeding timestamps changes NOTHING versus feeding none.
    spec = _cond(canonical_key="cond.above", reference_key="ta.sma", reference_length=2)
    closes = ["10", "10", "20", "30", "5"]
    with_ts = _feed_ts(spec, _hourly(closes))
    ce = ConditionEvaluator(spec)
    without_ts: list[bool] = []
    for c in closes:
        v = Decimal(c)
        ce.update(close=v, high=v, low=v, open_price=v, indicator_value=v)
        without_ts.append(ce.satisfied)
    assert with_ts == without_ts


# ------------------------------------------------------------- fail-closed without ts


def test_reference_resample_without_timestamp_fails_closed() -> None:
    # A coarser reference timeframe needs timestamps to bucket; without them the reference
    # candle never closes, the RHS never warms up, and every check fails closed.
    spec = _cond(
        canonical_key="cond.above",
        reference_key="ta.sma",
        reference_length=1,
        reference_resample_seconds=_2H,
    )
    ce = ConditionEvaluator(spec)
    out: list[bool] = []
    for c in ["10", "20", "30", "40"]:
        v = Decimal(c)
        ce.update(close=v, high=v, low=v, open_price=v, indicator_value=v, timestamp=None)
        out.append(ce.satisfied)
    assert out == [False, False, False, False]


# --------------------------------------------------- multi-timeframe cross timing


def test_coarser_reference_cross_fires_when_the_reference_candle_closes() -> None:
    # close crosses_above a 2h SMA(2) reference. The reference only advances on a completed
    # 2h candle, so the fast source cannot cross a still-forming (stale) reference.
    spec = _cond(
        canonical_key="cond.crosses_above",
        reference_key="ta.sma",
        reference_length=2,
        reference_resample_seconds=_2H,
    )
    # candle closes fed to SMA(2): bar1=10, bar3=10 (RHS 10 @ bar4), bar5=5 (RHS 7.5 @ bar6).
    # The source jumps to 30 at bar6 (bucket3 open) -> crosses above the fresh RHS 7.5.
    out = _feed_ts(spec, _hourly(["10", "10", "10", "10", "5", "5", "30", "30"]))
    assert out == [False, False, False, False, False, False, True, False]


# ----------------------------------- full BlockEvaluator -> ConditionEvaluator plumbing


def test_block_condition_only_signal_uses_coarser_reference_timeframe() -> None:
    # A base-TF condition_only block whose REQUIRED cross drives the direction: close
    # crosses_above a 2h SMA(2) reference. Proves the block passes each base bar's timestamp
    # down to the nested condition so the coarser reference buckets correctly.
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
                reference_length=2,
                reference_resample_seconds=_2H,
            ),
        ),
    )
    ev = BlockEvaluator(block)
    signals: list[str | None] = []
    for ts, close in _hourly(["10", "10", "10", "10", "5", "5", "30", "30"]):
        ev.update(close, timestamp=ts)
        signals.append(ev.current_signal)
    # The cross lands at bar6 (reference candle2 closes); the condition-only signal fires
    # long on that rising edge and is held for its 1-candle validity.
    assert signals[6] == "long"
    assert signals[7] is None
