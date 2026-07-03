"""Unit tests for the threshold-condition compute + gating layer (post-V1 (b)).

Covers: the ConditionEvaluator raw checks (above/below), each source (price fields +
indicator_output), the validity window countdown (finite + until_opposite), the
BlockEvaluator native-trigger GATE (a trigger is suppressed when its conditions are
not satisfied), and the condition_block_rule aggregation over required/supporting."""

from __future__ import annotations

from decimal import Decimal

from entropia.domain.backtest.indicators import (
    CONDITION_KEYS,
    CONDITION_SOURCES,
    BlockEvaluator,
    ConditionEvaluator,
    ConditionSpec,
    IndicatorSpec,
    _conditions_satisfied,
)


def _cond(**kw: object) -> ConditionSpec:
    base: dict[str, object] = {
        "condition_block_id": "c1",
        "canonical_key": "cond.above",
        "source": "close",
        "threshold": Decimal("70"),
        "requirement": "required",
        "validity": "current_candle_only",
    }
    base.update(kw)
    return ConditionSpec(**base)  # type: ignore[arg-type]


def _feed_close(spec: ConditionSpec, closes: list[str]) -> list[bool]:
    ce = ConditionEvaluator(spec)
    out: list[bool] = []
    for c in closes:
        close = Decimal(c)
        ce.update(close=close, high=close, low=close, open_price=close, indicator_value=None)
        out.append(ce.satisfied)
    return out


def _block_signals(spec: IndicatorSpec, closes: list[str]) -> list[str | None]:
    ev = BlockEvaluator(spec)
    out: list[str | None] = []
    for c in closes:
        ev.update(Decimal(c))
        out.append(ev.current_signal)
    return out


# --------------------------------------------------------------------- raw checks


def test_cond_above_is_true_only_over_threshold() -> None:
    out = _feed_close(
        _cond(canonical_key="cond.above", threshold=Decimal("70")), ["50", "80", "60"]
    )
    assert out == [False, True, False]


def test_cond_below_is_true_only_under_threshold() -> None:
    out = _feed_close(
        _cond(canonical_key="cond.below", threshold=Decimal("30"), validity="1_candle"),
        ["50", "20", "20"],
    )
    assert out == [False, True, True]


def test_strict_comparators_reject_equality() -> None:
    # 70 is NOT above 70 and NOT below 70 — strict comparison on both sides.
    assert _feed_close(_cond(canonical_key="cond.above", threshold=Decimal("70")), ["70"]) == [
        False
    ]
    assert _feed_close(_cond(canonical_key="cond.below", threshold=Decimal("70")), ["70"]) == [
        False
    ]


# --------------------------------------------------------------------------- sources


def test_source_high_and_low_read_bar_extremes() -> None:
    high_spec = _cond(source="high", canonical_key="cond.above", threshold=Decimal("70"))
    ce = ConditionEvaluator(high_spec)
    ce.update(
        close=Decimal("50"),
        high=Decimal("80"),
        low=Decimal("40"),
        open_price=Decimal("50"),
        indicator_value=None,
    )
    assert ce.satisfied is True  # high 80 > 70 even though close 50 is not

    low_spec = _cond(source="low", canonical_key="cond.below", threshold=Decimal("45"))
    ce = ConditionEvaluator(low_spec)
    ce.update(
        close=Decimal("50"),
        high=Decimal("80"),
        low=Decimal("40"),
        open_price=Decimal("50"),
        indicator_value=None,
    )
    assert ce.satisfied is True  # low 40 < 45


def test_source_indicator_output_reads_parent_value_and_none_is_not_satisfied() -> None:
    spec = _cond(source="indicator_output", canonical_key="cond.above", threshold=Decimal("70"))
    ce = ConditionEvaluator(spec)
    ce.update(
        close=Decimal("0"),
        high=Decimal("0"),
        low=Decimal("0"),
        open_price=Decimal("0"),
        indicator_value=Decimal("72"),
    )
    assert ce.satisfied is True
    ce = ConditionEvaluator(spec)
    ce.update(
        close=Decimal("0"),
        high=Decimal("0"),
        low=Decimal("0"),
        open_price=Decimal("0"),
        indicator_value=None,
    )
    assert ce.satisfied is False  # parent still warming up -> gate fails closed


# ------------------------------------------------------------------- validity window


def test_finite_validity_holds_then_expires() -> None:
    # A satisfied check on bar0 stays active for 3 bars (0,1,2) then clears on bar3.
    spec = _cond(canonical_key="cond.above", threshold=Decimal("70"), validity="3_candles")
    out = _feed_close(spec, ["80", "50", "50", "50"])
    assert out == [True, True, True, False]


def test_until_opposite_clears_the_moment_the_check_fails() -> None:
    spec = _cond(
        canonical_key="cond.above", threshold=Decimal("70"), validity="until_opposite_signal"
    )
    out = _feed_close(spec, ["80", "90", "50", "80"])
    assert out == [True, True, False, True]


# ----------------------------------------------------------------- block-level gate


def _sma_gated(threshold: str) -> IndicatorSpec:
    return IndicatorSpec(
        block_id="b",
        canonical_key="ta.sma",
        length=3,
        direction="long_and_short",
        requirement="required",
        validity="until_opposite_signal",
        conditions=(
            ConditionSpec(
                condition_block_id="c",
                canonical_key="cond.above",
                source="close",
                threshold=Decimal(threshold),
                requirement="required",
                validity="until_opposite_signal",
            ),
        ),
    )


def test_trigger_fires_when_condition_is_satisfied() -> None:
    # SMA(3) long cross on the last bar (close 11); close 11 > threshold 10 -> gate open.
    signals = _block_signals(_sma_gated("10"), ["10", "10", "10", "9", "11"])
    assert signals[4] == "long"


def test_trigger_is_suppressed_when_condition_fails() -> None:
    # Same cross, but close 11 is NOT above threshold 20 -> the trigger is gated away.
    signals = _block_signals(_sma_gated("20"), ["10", "10", "10", "9", "11"])
    assert signals[4] is None


def test_block_without_conditions_is_unchanged() -> None:
    plain = IndicatorSpec(
        block_id="b",
        canonical_key="ta.sma",
        length=3,
        direction="long_and_short",
        requirement="required",
        validity="until_opposite_signal",
    )
    assert _block_signals(plain, ["10", "10", "10", "9", "11"])[4] == "long"


# ------------------------------------------------------------- condition aggregation


def _make_cond(requirement: str, satisfied: bool) -> ConditionEvaluator:
    ce = ConditionEvaluator(
        ConditionSpec(
            condition_block_id="c",
            canonical_key="cond.above",
            source="close",
            threshold=Decimal("50"),
            requirement=requirement,
            validity="until_opposite_signal",
        )
    )
    close = Decimal("60") if satisfied else Decimal("40")
    ce.update(close=close, high=close, low=close, open_price=close, indicator_value=None)
    return ce


def test_required_only_needs_every_required_satisfied() -> None:
    rule = "required_condition_blocks_only"
    assert _conditions_satisfied(rule, [_make_cond("required", True)], None) is True
    assert _conditions_satisfied(rule, [_make_cond("required", False)], None) is False


def test_any_supporting_needs_one_confirmation() -> None:
    rule = "required_plus_any_supporting"
    req = _make_cond("required", True)
    assert _conditions_satisfied(rule, [req, _make_cond("supporting", False)], None) is False
    assert _conditions_satisfied(rule, [req, _make_cond("supporting", True)], None) is True


def test_min_supporting_needs_enough_confirmations() -> None:
    rule = "required_plus_min_supporting"
    req = _make_cond("required", True)
    one = [req, _make_cond("supporting", True), _make_cond("supporting", False)]
    two = [req, _make_cond("supporting", True), _make_cond("supporting", True)]
    assert _conditions_satisfied(rule, one, 2) is False
    assert _conditions_satisfied(rule, two, 2) is True


def test_all_supporting_needs_every_supporting() -> None:
    rule = "required_plus_all_supporting"
    req = _make_cond("required", True)
    assert (
        _conditions_satisfied(
            rule, [req, _make_cond("supporting", True), _make_cond("supporting", False)], None
        )
        is False
    )
    assert (
        _conditions_satisfied(
            rule, [req, _make_cond("supporting", True), _make_cond("supporting", True)], None
        )
        is True
    )


def test_no_required_degenerates_to_all_must_hold() -> None:
    # With no explicitly-required condition, the gate is 'every condition must hold'.
    rule = "required_condition_blocks_only"
    assert (
        _conditions_satisfied(
            rule, [_make_cond("supporting", True), _make_cond("supporting", True)], None
        )
        is True
    )
    assert (
        _conditions_satisfied(
            rule, [_make_cond("supporting", True), _make_cond("supporting", False)], None
        )
        is False
    )


def test_condition_key_and_source_sets_are_coherent() -> None:
    # The level primitives remain; (b2) adds crosses + between (asserted fully in
    # test_backtest_condition_extensions.py), so this checks the invariant subset.
    assert {"cond.above", "cond.below"} <= set(CONDITION_KEYS)
    assert "indicator_output" in CONDITION_SOURCES
    assert {"close", "open", "high", "low"} <= CONDITION_SOURCES
