"""G11 (P2) / G12 (P8) — the resolved-Strategy shapes a shared clock cannot drive.

``domain/backtest/execution/shared_shapes.py`` is read by three surfaces: the engine's
construction-time refusal, Ready Check, and the run-admission guard. This file pins the
PREDICATE. The engine-side parity (that the loop really consumes this table rather than
carrying a second copy) and the deliberately WITHHELD rows are measured where a real
``_RunConfig`` exists — ``tests/unit/oracles/test_oracle_engine_participant.py``. The
user-facing issue shape is ``tests/unit/test_shared_mode_admission.py``; the wiring proof
is ``tests/integration/test_shared_mode_admission.py``.

Every refusal below is paired with a negative control that differs only in the offending
field: a predicate that returned everything would otherwise pass the refusal half.
"""

from __future__ import annotations

from typing import Any, get_args

import pytest

from entropia.domain.backtest.execution.fills import _fill_schedule
from entropia.domain.backtest.execution.shared_shapes import (
    IMMEDIATE_ORDER_TYPES,
    SharedShapeKind,
    unsupported_shared_shapes,
)
from entropia.domain.strategy.config import ExecutionModel, StrategyConfig
from entropia.domain.strategy.enums import OrderTypeEnum

from .oracles.harness import oracle_config

_SCALING_ON: dict[str, Any] = {
    "enabled": True,
    "method": "price_distance_scaling",
    "price_scaling": {"retracement_distance": "1", "layers": 2},
    "add_size": "percent_of_initial",
    "add_size_value": "50",
}


def _limit_order(order_type: str) -> dict[str, Any]:
    return {
        "type": order_type,
        "limit": {
            "price_rule": "entry_signal_price",
            "validity": "3_candles",
            "unfilled_policy": "cancel_order",
            "partial_fill_policy": "not_allowed",
        },
    }


def _config(**kwargs: Any) -> StrategyConfig:
    """A config that clears BOTH gates unless a kwarg breaks exactly one."""
    return oracle_config(direction="long", conflict={"same_direction_stacking": "ignore"}, **kwargs)


def _kinds(config: StrategyConfig) -> list[SharedShapeKind]:
    return [violation.kind for violation in unsupported_shared_shapes(config)]


def _paths(config: StrategyConfig) -> list[str]:
    return [violation.field_path for violation in unsupported_shared_shapes(config)]


# --------------------------------------------------------------------------- #
# Baseline                                                                     #
# --------------------------------------------------------------------------- #


def test_a_config_that_clears_both_gates_reports_nothing() -> None:
    """The negative control every other case in this file is measured against."""
    assert unsupported_shared_shapes(_config()) == ()


# --------------------------------------------------------------------------- #
# G11 / P2 — deferring timings and resting order types                         #
# --------------------------------------------------------------------------- #


def _accepted(field: str) -> tuple[str, ...]:
    """The literals THIS field accepts.

    Derived per field, not from ``ExecutionTimingEnum``: the two fields take different
    subsets of it (``limit_fill_simulation`` is entry-only, ``stop_limit_priority_simulation``
    exit-only), so one shared list would either skip a real value or feed each field a
    literal it rejects — measured, after the first version of this file did the latter.
    """
    return get_args(ExecutionModel.model_fields[field].annotation)


def _deferring(field: str) -> list[str]:
    """Every accepted literal the shipped ``_fill_schedule`` does NOT fill on the
    deciding bar. Derived rather than typed out: a new deferring timing joins by itself,
    where a list of three literals would keep passing while a fourth slipped through."""
    return sorted(t for t in _accepted(field) if _fill_schedule(t) != "immediate")


def _immediate(field: str) -> list[str]:
    return sorted(t for t in _accepted(field) if _fill_schedule(t) == "immediate")


def test_the_deferring_timing_set_is_the_one_g11_measured() -> None:
    """G11 §Ölçüm 3 named exactly three, and the same three on both sides. If a fourth
    ever appears the gate still covers it (the set is derived), but the decision was
    signed against these three — so a change here is a fact a reader of that signature
    needs to see."""
    expected = ["intrabar_touch", "next_candle_close", "next_candle_open"]
    assert _deferring("entry_timing") == expected
    assert _deferring("exit_timing") == expected


@pytest.mark.parametrize("timing", _deferring("entry_timing"))
def test_a_deferring_entry_timing_is_a_deferred_fill_violation(timing: str) -> None:
    violations = unsupported_shared_shapes(_config(entry_timing=timing))
    assert [v.kind for v in violations] == [SharedShapeKind.DEFERRED_FILL]
    assert violations[0].field_path == "data.execution.entry_timing"
    # The engine's own sentence must NAME the offending value, or a reader of the
    # UnsupportedStrategyShapeError cannot tell which of the two timings was at fault.
    assert timing in violations[0].detail


@pytest.mark.parametrize("timing", _deferring("exit_timing"))
def test_a_deferring_exit_timing_is_a_deferred_fill_violation(timing: str) -> None:
    violations = unsupported_shared_shapes(_config(exit_timing=timing))
    assert [v.kind for v in violations] == [SharedShapeKind.DEFERRED_FILL]
    assert violations[0].field_path == "data.execution.exit_timing"
    assert timing in violations[0].detail


@pytest.mark.parametrize("timing", _immediate("entry_timing"))
def test_an_entry_timing_that_fills_on_the_deciding_bar_is_clean(timing: str) -> None:
    """NEGATIVE CONTROL for the entry case above: the other half of the accepted set.

    ``limit_fill_simulation`` is here on purpose — its SCHEDULE is immediate (the limit
    machinery governs the fill, not the schedule), so the timing axis passes and it is
    the ORDER TYPE axis below that refuses a limit-backed configuration."""
    assert unsupported_shared_shapes(_config(entry_timing=timing)) == ()


@pytest.mark.parametrize("timing", _immediate("exit_timing"))
def test_an_exit_timing_that_fills_on_the_deciding_bar_is_clean(timing: str) -> None:
    """NEGATIVE CONTROL for the exit case; ``stop_limit_priority_simulation`` is the
    exit-side counterpart of the note above."""
    assert unsupported_shared_shapes(_config(exit_timing=timing)) == ()


@pytest.mark.parametrize(
    "order_type", sorted(str(t) for t in OrderTypeEnum if str(t) not in IMMEDIATE_ORDER_TYPES)
)
def test_a_resting_order_type_is_a_deferred_fill_violation(order_type: str) -> None:
    violations = unsupported_shared_shapes(_config(order_config=_limit_order(order_type)))
    assert [v.kind for v in violations] == [SharedShapeKind.DEFERRED_FILL]
    assert violations[0].field_path == "data.order_config.type"
    assert order_type in violations[0].detail


@pytest.mark.parametrize("order_type", sorted(IMMEDIATE_ORDER_TYPES))
def test_an_immediate_order_type_is_clean(order_type: str) -> None:
    assert unsupported_shared_shapes(_config(order_config={"type": order_type})) == ()


def test_an_unknown_order_type_fails_closed() -> None:
    """The set is stated POSITIVELY, so a type this build has never heard of RESTS.

    Constructed by mutating the parsed config rather than by validating an invalid
    payload: the point is what the predicate does with a value, not what pydantic does
    with one, and a widened ``OrderTypeEnum`` would reach the predicate exactly so."""
    config = _config()
    object.__setattr__(config.data.order_config, "type", "some_future_order_type")
    assert _kinds(config) == [SharedShapeKind.DEFERRED_FILL]


# --------------------------------------------------------------------------- #
# G12 / P8 — same-direction scaling                                            #
# --------------------------------------------------------------------------- #


def test_enabled_scaling_is_a_scaling_violation() -> None:
    violations = unsupported_shared_shapes(_config(scaling=_SCALING_ON))
    assert [v.kind for v in violations] == [SharedShapeKind.SCALING]
    assert violations[0].field_path == "scaling_logic.enabled"


def test_scaling_present_but_disabled_is_clean() -> None:
    """NEGATIVE CONTROL: the subtree exists, the ladder does not run.

    A predicate keyed on ``scaling_logic is not None`` would refuse this — and would
    refuse every Strategy that ever opened the scaling panel and turned it back off."""
    assert unsupported_shared_shapes(_config(scaling={**_SCALING_ON, "enabled": False})) == ()


def test_no_scaling_subtree_is_clean() -> None:
    assert _config().scaling_logic is None
    assert unsupported_shared_shapes(_config()) == ()


# --------------------------------------------------------------------------- #
# Several at once                                                              #
# --------------------------------------------------------------------------- #


def test_every_violation_is_reported_in_field_order() -> None:
    """All four rows at once. Reporting only the first would let a user fix one setting,
    re-run, and meet the next refusal — the O-02 envelope promotes a leader precisely
    because ``details`` is expected to carry the whole list."""
    config = _config(
        entry_timing="next_candle_open",
        exit_timing="intrabar_touch",
        order_config=_limit_order("limit_order"),
        scaling=_SCALING_ON,
    )
    assert _paths(config) == [
        "data.execution.entry_timing",
        "data.execution.exit_timing",
        "data.order_config.type",
        "scaling_logic.enabled",
    ]
    assert _kinds(config) == [
        SharedShapeKind.DEFERRED_FILL,
        SharedShapeKind.DEFERRED_FILL,
        SharedShapeKind.DEFERRED_FILL,
        SharedShapeKind.SCALING,
    ]


def test_the_two_gates_are_independent() -> None:
    """Scaling alone must not drag in a fill finding, or vice versa — they are two
    signatures and either can be revisited without the other."""
    assert _kinds(_config(scaling=_SCALING_ON)) == [SharedShapeKind.SCALING]
    assert _kinds(_config(entry_timing="next_candle_open")) == [SharedShapeKind.DEFERRED_FILL]


def test_only_the_two_signed_gates_exist() -> None:
    """The admission surface emits blockers for these kinds and nothing else.

    A third member added without a signature would silently become a user-visible
    blocker the moment someone mapped it, so the set is pinned here rather than left to
    the mapping table's key coverage."""
    assert sorted(str(kind) for kind in SharedShapeKind) == ["deferred_fill", "scaling"]
