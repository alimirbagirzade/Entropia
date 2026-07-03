"""Unit tests for the (b2) condition extensions: cross edges, range, series-vs-series
reference RHS, and the condition-only directional signal.

Covers, in isolation from the DB:

* ``ConditionEvaluator`` — crosses_above/crosses_below EDGE detection (vs a constant
  threshold and vs a ``reference`` series), the ``cond.between`` RANGE, series-vs-series
  level comparisons, and the cross + ``until_opposite_signal`` degeneration;
* ``condition_direction`` polarity mapping;
* ``BlockEvaluator`` in ``condition_only`` mode — a required cross drives the signal,
  the block ``direction`` filter applies, and a supporting gate can veto the fire.
"""

from __future__ import annotations

from decimal import Decimal

from entropia.domain.backtest.indicators import (
    CONDITION_KEYS,
    CROSS_CONDITION_KEYS,
    RANGE_CONDITION_KEYS,
    BlockEvaluator,
    ConditionEvaluator,
    ConditionSpec,
    IndicatorSpec,
    condition_direction,
)


def _cond(**kw: object) -> ConditionSpec:
    base: dict[str, object] = {
        "condition_block_id": "c1",
        "canonical_key": "cond.crosses_above",
        "source": "close",
        "threshold": Decimal("70"),
        "requirement": "required",
        "validity": "current_candle_only",
    }
    base.update(kw)
    return ConditionSpec(**base)  # type: ignore[arg-type]


def _feed(spec: ConditionSpec, bars: list[dict[str, str]]) -> list[bool]:
    """Feed OHLC(+indicator) bars into one condition; return per-bar ``satisfied``."""
    ce = ConditionEvaluator(spec)
    out: list[bool] = []
    for b in bars:
        ind = b.get("indicator")
        ce.update(
            close=Decimal(b["close"]),
            high=Decimal(b.get("high", b["close"])),
            low=Decimal(b.get("low", b["close"])),
            open_price=Decimal(b.get("open", b["close"])),
            indicator_value=None if ind is None else Decimal(ind),
        )
        out.append(ce.satisfied)
    return out


def _closes(values: list[str]) -> list[dict[str, str]]:
    return [{"close": v} for v in values]


# ------------------------------------------------------------------- cross edges


def test_crosses_above_fires_only_on_the_upward_crossing_bar() -> None:
    # prev <= 70 AND now > 70: only bar2 (65 -> 80) is a fresh upward cross.
    out = _feed(_cond(canonical_key="cond.crosses_above"), _closes(["60", "65", "80", "85", "60"]))
    assert out == [False, False, True, False, False]


def test_crosses_below_fires_only_on_the_downward_crossing_bar() -> None:
    out = _feed(
        _cond(canonical_key="cond.crosses_below", threshold=Decimal("30")),
        _closes(["40", "35", "20", "15", "40"]),
    )
    assert out == [False, False, True, False, False]


def test_cross_is_an_edge_not_a_level_unlike_above() -> None:
    # A LEVEL (above) stays true while over the line; a CROSS fires once, then clears.
    closes = _closes(["80", "85", "90"])
    assert _feed(_cond(canonical_key="cond.above"), closes) == [True, True, True]
    assert _feed(_cond(canonical_key="cond.crosses_above"), closes) == [False, False, False]


def test_first_bar_cross_fails_closed_no_previous_pair() -> None:
    # No previous bar => no cross can be asserted (fail-closed), even if already over.
    assert _feed(_cond(canonical_key="cond.crosses_above"), _closes(["80"])) == [False]


def test_cross_with_until_opposite_stays_active_only_for_its_firing_bar() -> None:
    # A momentary cross under an open-ended window clears the very next bar.
    out = _feed(
        _cond(canonical_key="cond.crosses_above", validity="until_opposite_signal"),
        _closes(["60", "80", "85", "60"]),
    )
    assert out == [False, True, False, False]


# ---------------------------------------------------------------- reference series


def test_above_compares_source_against_a_reference_series() -> None:
    # close vs the parent indicator_output (series-vs-series LEVEL), no constant.
    spec = _cond(canonical_key="cond.above", threshold=None, reference="indicator_output")
    bars = [
        {"close": "13", "indicator": "12"},  # 13 > 12 -> True
        {"close": "11", "indicator": "12"},  # 11 > 12 -> False
    ]
    assert _feed(spec, bars) == [True, False]


def test_crosses_above_against_a_reference_series() -> None:
    # close crosses above indicator_output between bar1 and bar2.
    spec = _cond(canonical_key="cond.crosses_above", threshold=None, reference="indicator_output")
    bars = [
        {"close": "10", "indicator": "12"},  # prev None -> False
        {"close": "11", "indicator": "12"},  # 11 <= 12 -> no cross
        {"close": "13", "indicator": "12"},  # prev 11<=12, now 13>12 -> cross
        {"close": "14", "indicator": "12"},  # prev 13>12 -> no fresh cross
    ]
    assert _feed(spec, bars) == [False, False, True, False]


def test_reference_warmup_none_fails_closed() -> None:
    spec = _cond(canonical_key="cond.above", threshold=None, reference="indicator_output")
    bars = [{"close": "13", "indicator": None}]  # parent still warming up
    assert _feed(spec, bars) == [False]


# ------------------------------------------------------------------------- range


def test_between_is_true_only_strictly_inside_the_bounds() -> None:
    spec = _cond(
        canonical_key="cond.between", threshold=None, lower=Decimal("30"), upper=Decimal("70")
    )
    out = _feed(spec, _closes(["20", "50", "80", "70", "30"]))
    # 20 out; 50 in; 80 out; 70 and 30 on the (exclusive) bound -> out.
    assert out == [False, True, False, False, False]


# ------------------------------------------------------------ direction polarity


def test_condition_direction_maps_only_crosses() -> None:
    assert condition_direction("cond.crosses_above") == "long"
    assert condition_direction("cond.crosses_below") == "short"
    assert condition_direction("cond.above") is None
    assert condition_direction("cond.below") is None
    assert condition_direction("cond.between") is None


# ----------------------------------------------------- condition-only signal


def _condition_only_block(**kw: object) -> IndicatorSpec:
    """An SMA block whose native trigger is IGNORED; a required cross drives it."""
    conds = kw.pop("conditions", None)
    base: dict[str, object] = {
        "block_id": "b",
        "canonical_key": "ta.sma",
        "length": 3,
        "direction": "long_and_short",
        "requirement": "required",
        "validity": "1_candle",
        "condition_only": True,
        "conditions": conds
        or (
            ConditionSpec(
                condition_block_id="c",
                canonical_key="cond.crosses_above",
                source="close",
                threshold=Decimal("70"),
                requirement="required",
                validity="1_candle",
            ),
        ),
    }
    base.update(kw)
    return IndicatorSpec(**base)  # type: ignore[arg-type]


def _block_signals(spec: IndicatorSpec, closes: list[str]) -> list[str | None]:
    ev = BlockEvaluator(spec)
    out: list[str | None] = []
    for c in closes:
        ev.update(Decimal(c))
        out.append(ev.current_signal)
    return out


def test_condition_only_fires_long_on_the_required_cross() -> None:
    # No native SMA trigger is used; the crosses_above 70 edge (bar2) fires long.
    signals = _block_signals(_condition_only_block(), ["60", "65", "80", "85", "60"])
    assert signals == [None, None, "long", None, None]


def test_condition_only_respects_the_block_direction_filter() -> None:
    # crosses_above is a LONG edge; a short-only block suppresses it entirely.
    signals = _block_signals(_condition_only_block(direction="short"), ["60", "65", "80", "85"])
    assert signals == [None, None, None, None]


def test_condition_only_short_edge_fires_short() -> None:
    block = _condition_only_block(
        conditions=(
            ConditionSpec(
                condition_block_id="c",
                canonical_key="cond.crosses_below",
                source="close",
                threshold=Decimal("30"),
                requirement="required",
                validity="1_candle",
            ),
        ),
    )
    signals = _block_signals(block, ["40", "35", "20", "15"])
    assert signals == [None, None, "short", None]


def test_condition_only_supporting_gate_can_veto_the_fire() -> None:
    # required crosses_above 70 (long edge) + supporting above 100; rule needs the
    # supporting confirmation. The cross bar's close 80 is NOT above 100 -> no fire.
    block = _condition_only_block(
        condition_rule="required_plus_any_supporting",
        conditions=(
            ConditionSpec(
                condition_block_id="cr",
                canonical_key="cond.crosses_above",
                source="close",
                threshold=Decimal("70"),
                requirement="required",
                validity="1_candle",
            ),
            ConditionSpec(
                condition_block_id="cs",
                canonical_key="cond.above",
                source="close",
                threshold=Decimal("100"),
                requirement="supporting",
                validity="1_candle",
            ),
        ),
    )
    assert _block_signals(block, ["60", "65", "80", "85"]) == [None, None, None, None]


# --------------------------------------------------------------- set coherence


def test_condition_key_sets_are_coherent() -> None:
    assert (
        frozenset(
            {"cond.above", "cond.below", "cond.crosses_above", "cond.crosses_below", "cond.between"}
        )
        == CONDITION_KEYS
    )
    assert frozenset({"cond.crosses_above", "cond.crosses_below"}) == CROSS_CONDITION_KEYS
    assert frozenset({"cond.between"}) == RANGE_CONDITION_KEYS
    assert CROSS_CONDITION_KEYS <= CONDITION_KEYS
    assert RANGE_CONDITION_KEYS <= CONDITION_KEYS
