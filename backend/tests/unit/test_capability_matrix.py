"""F-05 / M-05 — machine-readable capability matrix parity (UI ↔ Ready Check ↔ engine).

The acceptance criterion for this slice is a NEGATIVE one: there must be no ENABLED
option that a user can select and save and that then fails — or worse, silently
mismodels — at execution time. These tests enforce it from three directions:

1. **Exhaustiveness** (:func:`test_matrix_enumerates_every_schema_literal`) — for every
   field the matrix enumerates, its rows cover EXACTLY the saved schema's ``Literal``
   values. This is the anti-drift guard that matters most: a new option added to
   ``config.py`` cannot reach the UI without being classified ``active_v1`` or
   ``future_dev`` first, because this test fails the moment the sets diverge.
2. **Fail-closed parity** (:func:`test_every_future_dev_option_blocks_and_opens_nothing`)
   — every ``future_dev`` row, driven through a real config, both blocks Ready Check with
   ``STRATEGY_CAPABILITY_NOT_IN_BUILD`` and opens NO position in the engine.
3. **Executability** (:func:`test_active_v1_baseline_runs`,
   :func:`test_dependency_free_active_v1_options_stay_modelled`) — ``active_v1`` options
   really do run rather than being classified optimistically.

Plus :func:`test_generated_typescript_mirror_is_up_to_date`, which pins the UI's copy of
the matrix to the Python canon so the editor can never offer an option the engine refuses.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any, Literal, get_args, get_origin

import pytest

from entropia.domain.backtest.capabilities import (
    CAPABILITY_MATRIX,
    FUTURE_DEV_OPTIONS,
    CapabilityOption,
    capabilities_are_modelled,
    future_dev_selections,
    option_status,
)
from entropia.domain.backtest.engine import EngineOutput, run_engine
from entropia.domain.mainboard.enums import MainboardItemKind
from entropia.domain.readiness.enums import ReadinessIssueCode as Code
from entropia.domain.readiness.issues import ReadinessItemInput
from entropia.domain.readiness.validators import evaluate_readiness
from entropia.domain.strategy import config as config_module
from entropia.domain.strategy.config import StrategyConfig
from tests.unit.engine_signal_plan import sma_entry_plan

# ---------------------------------------------------------------------------
# Fixtures — a minimal VALID config that selects ONLY active_v1 options, plus the
# smallest bar series that produces a real breakout entry.
# ---------------------------------------------------------------------------

_BASE_PAYLOAD: dict[str, Any] = {
    "strategy_root_id": "strat_root_1",
    "display_name": "Capability Matrix Fixture",
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
    "position_sizing": {"method": "base_position_size", "base_position_size": "10"},
    "restrictions_filters": {"rule": "any", "filters": []},
    "conflict_position_handling": {},
}


def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    merged = {k: (dict(v) if isinstance(v, dict) else v) for k, v in base.items()}
    for key, value in overlay.items():
        current = merged.get(key)
        if isinstance(current, dict) and isinstance(value, dict):
            merged[key] = _deep_merge(current, value)
        else:
            merged[key] = value
    return merged


def _payload(**overlay: Any) -> dict[str, Any]:
    """The raw pinned revision payload — exactly what Ready Check receives."""
    return _deep_merge(_BASE_PAYLOAD, overlay)


def _config(**overlay: Any) -> StrategyConfig:
    return StrategyConfig.model_validate(_payload(**overlay))


def _bars() -> list[dict[str, Any]]:
    """Twenty flat bars then an upside breakout — a guaranteed long entry.

    Twenty matches ``engine._BREAKOUT_WINDOW`` / ``sma_entry_plan``'s ``length=20``: the MA
    rests exactly at the flat price, so the breakout bar crosses it on that same bar."""
    flat = [
        {
            "timestamp": f"2024-01-{day:02d}T00:00:00Z",
            "open": "100",
            "high": "100",
            "low": "100",
            "close": "100",
            "volume": "10",
        }
        for day in range(1, 21)
    ]
    breakout = {
        "timestamp": "2024-01-21T00:00:00Z",
        "open": "100",
        "high": "106",
        "low": "100",
        "close": "105",
        "volume": "10",
    }
    return [*flat, breakout]


def _run(config: StrategyConfig) -> EngineOutput:
    bars = _bars()

    def batched() -> Iterator[list[dict[str, Any]]]:
        for start in range(0, len(bars), 8):
            yield bars[start : start + 8]

    return run_engine(
        strategy_config=config,
        bar_batches=batched(),
        execution_key="exec_key_capability",
        indicator_plan=sma_entry_plan(),
    )


def _readiness_codes(payload: dict[str, Any]) -> set[str]:
    """Every issue code Ready Check raises for a single-strategy composition.

    Goes through the REAL ``evaluate_readiness`` entry point with a raw pinned payload
    (not a pre-parsed config) so the blocker is proven on the same path production uses."""
    item = ReadinessItemInput(
        item_id="item_s1",
        kind=MainboardItemKind.STRATEGY,
        root_id="root_s1",
        revision_id="rev_s1",
        available=True,
        payload=payload,
    )
    evaluation = evaluate_readiness([item], allocation_enabled=False, allocation_issues=[])
    return {issue.code.value for issue in evaluation.issues}


# ---------------------------------------------------------------------------
# 1. Exhaustiveness — the matrix classifies every literal the schema accepts.
# ---------------------------------------------------------------------------

# field_path -> (pydantic model, field name). The matrix's own field paths are the keys, so
# a new enumerated field must be registered here too (and this test then proves it complete).
_SCHEMA_FIELDS: dict[str, tuple[type, str]] = {
    "data.costs.slippage_mode": (config_module.CostsModel, "slippage_mode"),
    "data.execution.entry_timing": (config_module.ExecutionModel, "entry_timing"),
    "data.execution.exit_timing": (config_module.ExecutionModel, "exit_timing"),
    "data.order_config.limit.price_rule": (
        config_module.LimitOrderDetails,
        "price_rule",
    ),
    "data.order_config.limit.partial_fill_policy": (
        config_module.LimitOrderDetails,
        "partial_fill_policy",
    ),
    "position_sizing.leverage_mode": (config_module.PositionSizing, "leverage_mode"),
    "position_sizing.signal_strength_adjustment": (
        config_module.PositionSizing,
        "signal_strength_adjustment",
    ),
    "position_sizing.formula_based.formula_type": (
        config_module.FormulaBasedSizing,
        "formula_type",
    ),
    "position_exit_logic.partial_aftermath": (
        config_module.PositionExitLogic,
        "partial_aftermath",
    ),
    "scaling_logic.timeframe": (config_module.ScalingLogic, "timeframe"),
    "scaling_logic.timeframe_mode": (config_module.ScalingLogic, "timeframe_mode"),
    "scaling_logic.method": (config_module.ScalingLogic, "method"),
    "restrictions_filters.filters.filter_type": (
        config_module.RestrictionFilter,
        "filter_type",
    ),
    "conflict_position_handling.opposite_direction_hedge": (
        config_module.ConflictPositionHandling,
        "opposite_direction_hedge",
    ),
}


def _literal_values(model: type, field_name: str) -> set[str]:
    """The ``Literal`` members a pydantic field accepts (unwrapping ``| None``)."""
    annotation = model.model_fields[field_name].annotation
    if get_origin(annotation) is Literal:
        return {str(v) for v in get_args(annotation)}
    # Optional[Literal[...]] — find the Literal arm.
    for arm in get_args(annotation):
        if get_origin(arm) is Literal:
            return {str(v) for v in get_args(arm)}
    raise AssertionError(f"{model.__name__}.{field_name} is not a Literal field")


# Matrix fields whose values live in a FREE-FORM config dict rather than a pydantic
# ``Literal`` — no schema enumeration exists, so axis 1 cannot run over them. Each one
# must instead carry its own vocabulary pin (for the action field:
# :func:`test_action_vocabulary_matches_the_engine`, which compares the matrix rows
# against the engine's ``_MODELLED_FILTER_ACTIONS`` in both directions).
_FREE_FORM_FIELDS: frozenset[str] = frozenset({"restrictions_filters.filters.action"})


def test_the_registry_covers_every_matrix_field_path() -> None:
    """The exhaustiveness guard is only as wide as ``_SCHEMA_FIELDS`` — so pin the width.

    ``test_matrix_enumerates_every_schema_literal`` is parametrized over the registry, not
    over the matrix. A matrix field path that nobody registers is therefore never asserted
    about, and CI stays green while a new literal reaches the editor unclassified — the
    exact failure the matrix was built to close. That is not hypothetical: the registry sat
    at 9 of 14 paths (GH #540), and no test could notice.

    This is the second axis. Axis 1 (above) asks "are this field's literals classified?";
    this one asks "is every gated field being asked at all?" — a drifting registry fails
    here even when every registered field still agrees. A free-form field (no schema
    ``Literal`` to enumerate) is registered in ``_FREE_FORM_FIELDS`` instead, and must
    carry a dedicated vocabulary pin.
    """
    assert set(_SCHEMA_FIELDS) | _FREE_FORM_FIELDS == {o.field_path for o in CAPABILITY_MATRIX}, (
        "the exhaustiveness registries and the capability matrix disagree. Every matrix "
        "field_path must be registered in _SCHEMA_FIELDS (so its literals are checked) or, "
        "when its values live in a free-form config dict, in _FREE_FORM_FIELDS (with its "
        "own vocabulary pin); neither registry may name a path the matrix does not classify."
    )
    assert not (set(_SCHEMA_FIELDS) & _FREE_FORM_FIELDS), (
        "a field cannot be both schema-enumerated and free-form"
    )


def test_action_vocabulary_matches_the_engine() -> None:
    """The action field's vocabulary pin — the free-form analogue of axis 1 (GH #546).

    ``RestrictionFilter.config`` is a free-form JSONB dict, so no pydantic ``Literal``
    exists for ``action`` and the schema-diff guard cannot see it. The drift risk lives in
    the ENGINE instead: ``_MODELLED_FILTER_ACTIONS`` growing or shrinking without the
    matrix following. Both directions are pinned — an engine literal the matrix does not
    mark ``active_v1`` fails here, and so does a matrix ``active_v1`` action the engine
    does not execute. The refused half is pinned to the engine docstring's own canon
    shorthand "(reduce / close / disable / warn)" (doc 02 §5.8, Master Ref §12.4)."""
    from entropia.domain.backtest.engine import _MODELLED_FILTER_ACTIONS

    action_rows = {
        o.value: o.status
        for o in CAPABILITY_MATRIX
        if o.field_path == "restrictions_filters.filters.action"
    }
    assert set(action_rows) == {"block", "block_entries", "reduce", "close", "disable", "warn"}
    active = {value for value, status in action_rows.items() if status == "active_v1"}
    assert active == set(_MODELLED_FILTER_ACTIONS), (
        "the matrix's active_v1 action rows and the engine's _MODELLED_FILTER_ACTIONS "
        "diverged — classify the change on both surfaces together."
    )


@pytest.mark.parametrize("field_path", sorted(_SCHEMA_FIELDS))
def test_matrix_enumerates_every_schema_literal(field_path: str) -> None:
    """Every saved literal is classified — no option can reach the UI unclassified.

    This is the acceptance guard for "no enabled option that fails later": if someone adds
    a new value to a ``Literal`` in ``config.py`` and does not classify it here, the sets
    diverge and CI fails BEFORE the option can be offered in the editor."""
    model, field_name = _SCHEMA_FIELDS[field_path]
    matrix_values = {o.value for o in CAPABILITY_MATRIX if o.field_path == field_path}
    assert matrix_values == _literal_values(model, field_name), (
        f"{field_path}: the capability matrix and the saved schema disagree. Classify new "
        f"options in domain/backtest/capabilities.py as active_v1 or future_dev."
    )


# ---------------------------------------------------------------------------
# 1b. Conflict-field literal guard (GH #536 Gap C, signed 2026-09-01 `A-Z`).
#
# Six conflict/protection fields deliberately do NOT join ``_SCHEMA_FIELDS``: every
# value they accept executes (ADIM 141-144 pinned the behaviours one by one), so
# forcing matrix rows for each literal would invent a classification per value
# without adding a decision any surface can act on. But that left the silent hole
# #536 names: a literal ADDED to one of these fields reached the UI with no
# classification and no guard failure — measured on the untouched tree, injecting a
# fake ``same_candle_entry_exit`` literal left this whole file green. The signed
# alternative (the issue's own item 4): a new literal on a conflict field must be
# either matrix-enumerated or EXPLICITLY allow-listed here. Exact equality cuts both
# ways — a removed literal must leave the list, and a literal that later gains a
# matrix row must leave it too (the disjointness half).
# ---------------------------------------------------------------------------

_UNGATED_CONFLICT_LITERALS: dict[str, tuple[tuple[type, str], frozenset[str]]] = {
    "conflict_position_handling.same_direction_stacking": (
        (config_module.ConflictPositionHandling, "same_direction_stacking"),
        frozenset({"allow_stacking", "replace_existing", "scale_existing", "ignore"}),
    ),
    "conflict_position_handling.overlapping_signal_policy": (
        (config_module.ConflictPositionHandling, "overlapping_signal_policy"),
        frozenset({"queue_sequential", "cancel_pending", "merge_signals", "ignore_if_active"}),
    ),
    "conflict_position_handling.stop_exit_conflict": (
        (config_module.ConflictPositionHandling, "stop_exit_conflict"),
        frozenset(
            {"stop_has_priority", "exit_has_priority", "record_both_reasons", "first_trigger_wins"}
        ),
    ),
    "conflict_position_handling.same_candle_entry_exit": (
        (config_module.ConflictPositionHandling, "same_candle_entry_exit"),
        frozenset(
            {
                "use_intrabar_data_if_available",
                "exit_first",
                "stop_first",
                "ignore_trade",
                "conservative_rule",
            }
        ),
    ),
    "protection_stop_logic.stop_trigger_requirement": (
        (config_module.ProtectionStopLogic, "stop_trigger_requirement"),
        frozenset({"any_active", "all_active"}),
    ),
    "protection_stop_logic.stop_conflict_resolution": (
        (config_module.ProtectionStopLogic, "stop_conflict_resolution"),
        frozenset(
            {
                "first_trigger_wins",
                "most_conservative",
                "priority_order",
                "record_all_execute_highest",
            }
        ),
    ),
}


@pytest.mark.parametrize("field_path", sorted(_UNGATED_CONFLICT_LITERALS))
def test_new_conflict_literals_must_be_classified_or_allowlisted(field_path: str) -> None:
    """A new conflict-field literal cannot ship silently unclassified (GH #536 Gap C).

    Every literal a conflict field accepts must be either a capability-matrix row or an
    entry in ``_UNGATED_CONFLICT_LITERALS`` above. Adding a literal to ``config.py``
    without touching either surface turns this red — the reviewer then decides whether
    the new value is a capability decision (matrix row) or another uniformly-executing
    value (allow-list entry with the ADIM 141-144 class of behavioural pin)."""
    (model, field_name), allowlisted = _UNGATED_CONFLICT_LITERALS[field_path]
    matrix_values = {o.value for o in CAPABILITY_MATRIX if o.field_path == field_path}
    schema_values = _literal_values(model, field_name)
    assert schema_values - matrix_values == allowlisted, (
        f"{field_path}: schema literals outside the matrix and the explicit allow-list "
        f"disagree. New literal? Classify it (matrix row in capabilities.py) or "
        f"allow-list it here with a behavioural pin. Removed literal? Drop it from the "
        f"allow-list."
    )
    assert not (allowlisted & matrix_values), (
        f"{field_path}: a literal is both matrix-enumerated and allow-listed — the "
        f"allow-list entry is stale, remove it."
    )


def test_every_matrix_row_has_a_reason_when_gated() -> None:
    """A ``future_dev`` row must say WHY — an unexplained refusal is not an honest boundary."""
    for option in FUTURE_DEV_OPTIONS:
        assert option.dependency.strip(), f"{option.field_path}={option.value} has no reason"


def test_option_status_is_none_for_unenumerated_fields() -> None:
    """Unenumerated fields/values read as ``None`` — never as a refusal."""
    assert option_status("data.costs.slippage_mode", "percentage_slippage") == "active_v1"
    assert option_status("data.costs.nonexistent_field", "whatever") is None
    assert option_status("data.costs.slippage_mode", "not_a_real_value") is None


# ---------------------------------------------------------------------------
# 2. Fail-closed parity — every future_dev option blocks AND opens nothing.
# ---------------------------------------------------------------------------

# One config overlay per future_dev option that actually SELECTS it. Sharing one table
# between the Ready Check and engine assertions is deliberate: both surfaces are proven
# against the identical config, which is what "parity" means here.
_FUTURE_DEV_OVERLAYS: dict[tuple[str, str], dict[str, Any]] = {
    ("data.costs.slippage_mode", "historical_slippage_if_available"): {
        "data": {"costs": {"slippage_mode": "historical_slippage_if_available"}}
    },
    ("data.order_config.limit.price_rule", "best_bid_ask"): {
        "data": {
            "order_config": {
                "type": "limit_order",
                "limit": {
                    "price_rule": "best_bid_ask",
                    "validity": "1_candle",
                    "unfilled_policy": "cancel_order",
                },
            }
        }
    },
    ("position_sizing.formula_based.formula_type", "custom_formula"): {
        "position_sizing": {
            "method": "formula_based_sizing",
            "base_position_size": None,
            "formula_based": {"formula_type": "custom_formula", "formula_params": {}},
        }
    },
    ("position_sizing.leverage_mode", "cross"): {
        "position_sizing": {"leverage_mode": "cross", "leverage": "2"}
    },
    ("position_sizing.signal_strength_adjustment", "trend_adjusted"): {
        "position_sizing": {"signal_strength_adjustment": "trend_adjusted"}
    },
    ("position_sizing.signal_strength_adjustment", "divergence_adjusted"): {
        "position_sizing": {"signal_strength_adjustment": "divergence_adjusted"}
    },
    ("scaling_logic.method", "logic_based_scaling"): {
        "scaling_logic": {
            "enabled": True,
            "timeframe": "same_as_base_tf",
            "method": "logic_based_scaling",
            "add_size_value": "1",
        }
    },
    ("conflict_position_handling.opposite_direction_hedge", "allow_hedge"): {
        "conflict_position_handling": {
            "opposite_direction_hedge": "allow_hedge",
            "exit_on_opposite_signal": False,
        }
    },
}

# The remaining future_dev rows are the enumerated scaling timeframes and restriction
# filter types — generated rather than hand-listed so adding one to the matrix
# automatically extends the proof instead of silently escaping it.
_FUTURE_DEV_OVERLAYS.update(
    {
        ("scaling_logic.timeframe", option.value): {
            "scaling_logic": {
                "enabled": True,
                "timeframe": option.value,
                "method": "price_distance_scaling",
                "price_scaling": {"retracement_distance": "1", "layers": 1},
                "add_size_value": "1",
            }
        }
        for option in FUTURE_DEV_OPTIONS
        if option.field_path == "scaling_logic.timeframe"
    }
)
# S5c introduced the per-layer timeframe STRUCTURE with ``increasing_by_layer`` as its
# one future_dev value; GH #547 lifted it (rung fixed by doc 02 §6.1, exhaustion signed
# to the custom_sequence precedent), so all three ``timeframe_mode`` values are active_v1
# and the field carries NO overlay here — an overlay for an active_v1 value would be a
# fail-closed proof for a mode that must trade. Its behavioural coverage lives in
# ``test_backtest_scaling_timeframe_mode.py``.
_FUTURE_DEV_OVERLAYS.update(
    {
        ("restrictions_filters.filters.filter_type", option.value): {
            "restrictions_filters": {
                "rule": "any",
                "filters": [{"filter_type": option.value, "enabled": True, "filter_id": "flt_1"}],
            }
        }
        for option in FUTURE_DEV_OPTIONS
        if option.field_path == "restrictions_filters.filters.filter_type"
    }
)
# GH #546 / D-4: each unmodelled ACTION rides an otherwise fully-modelled loss filter
# (modelled type, valid limit) so the action itself is the only unexecutable part of
# the selection — the free-form config key is what the row must detect.
_FUTURE_DEV_OVERLAYS.update(
    {
        ("restrictions_filters.filters.action", option.value): {
            "restrictions_filters": {
                "rule": "any",
                "filters": [
                    {
                        "filter_type": "max_daily_loss_filter",
                        "enabled": True,
                        "filter_id": "flt_act_1",
                        "config": {"limit_percent": "2", "action": option.value},
                    }
                ],
            }
        }
        for option in FUTURE_DEV_OPTIONS
        if option.field_path == "restrictions_filters.filters.action"
    }
)


def test_every_future_dev_option_has_a_proof_overlay() -> None:
    """No ``future_dev`` row may escape the parity proof below."""
    missing = [
        (o.field_path, o.value)
        for o in FUTURE_DEV_OPTIONS
        if (o.field_path, o.value) not in _FUTURE_DEV_OVERLAYS
    ]
    assert not missing, f"future_dev options with no proof config: {missing}"


@pytest.mark.parametrize(
    "option",
    FUTURE_DEV_OPTIONS,
    ids=[f"{o.field_path}={o.value}" for o in FUTURE_DEV_OPTIONS],
)
def test_every_future_dev_option_blocks_and_opens_nothing(option: CapabilityOption) -> None:
    """A future_dev selection is refused by Ready Check AND inert in the engine.

    Both halves matter: the blocker is what a user sees, and the engine gate is what
    protects a run admitted under a stale readiness state."""
    overlay = _FUTURE_DEV_OVERLAYS[(option.field_path, option.value)]
    config = _config(**overlay)

    # The matrix sees the selection...
    selected = future_dev_selections(config)
    assert option in selected, f"{option.value} not detected as selected"
    assert not capabilities_are_modelled(config)

    # ...Ready Check turns it into a "Not available in this build" BLOCKER...
    assert Code.STRATEGY_CAPABILITY_NOT_IN_BUILD.value in _readiness_codes(_payload(**overlay))

    # ...and the engine opens NO position (fail closed, never a silent mismodel).
    out = _run(config)
    assert out.diagnostics["capabilities_modelled"] is False
    assert f"{option.field_path}={option.value}" in out.diagnostics["capability_not_in_build"]
    assert (
        f"capability_not_in_build:{option.field_path}={option.value}" in out.diagnostics["warnings"]
    )
    assert out.trades == [], "a future_dev option must open no position"


def test_historical_slippage_was_the_silent_hole() -> None:
    """Regression pin for the F-05 finding.

    Before this slice ``slippage_mode='historical_slippage_if_available'`` passed all nine
    per-domain predicates, so Ready Check admitted the run and ``_cost_params`` — which
    never branched on the MODE — resolved slippage to ZERO (the schema makes
    ``slippage_value`` optional under that mode). The user got a silently over-optimistic
    fill model. It must now be refused, not merely warned about."""
    overlay = {
        "data": {
            "costs": {
                "slippage_mode": "historical_slippage_if_available",
                "slippage_value": None,
            }
        }
    }
    config = _config(**overlay)
    assert config.data.costs.slippage_value is None  # the schema really does allow this

    codes = _readiness_codes(_payload(**overlay))
    assert Code.STRATEGY_CAPABILITY_NOT_IN_BUILD.value in codes
    # None of the nine per-domain predicates ever covered this option — the matrix is what
    # closed it, so this assertion documents WHY the matrix has to exist.
    assert Code.STRATEGY_SIZING_UNSUPPORTED.value not in codes
    assert Code.STRATEGY_ORDER_TYPE_UNSUPPORTED.value not in codes
    assert _run(config).trades == []


def test_unmodelled_action_was_the_invisible_refusal() -> None:
    """Regression pin for the D-4 finding (GH #546).

    Before this slice a saved ``action: "reduce"`` failed closed CORRECTLY —
    ``restrictions_are_modelled`` returned False, Ready Check blocked, the engine opened
    nothing — but the refusal was invisible in structured provenance: measured on the
    untouched tree, ``capabilities_are_modelled`` stayed True and
    ``future_dev_selections`` stayed empty, so ``capability_not_in_build`` was an empty
    list on an inert run and the reason survived only in a free-text warning. Both
    surfaces must now name the action; the per-domain blocker stays — the GATE outcome
    was already correct and must not move."""
    overlay = {
        "restrictions_filters": {
            "rule": "any",
            "filters": [
                {
                    "filter_type": "max_daily_loss_filter",
                    "enabled": True,
                    "filter_id": "flt_d4",
                    "config": {"limit_percent": "2", "action": "reduce"},
                }
            ],
        }
    }
    config = _config(**overlay)
    assert [(o.field_path, o.value) for o in future_dev_selections(config)] == [
        ("restrictions_filters.filters.action", "reduce")
    ]
    assert not capabilities_are_modelled(config)

    codes = _readiness_codes(_payload(**overlay))
    # The structured disclosure is NEW; the per-domain fail-closed blocker is UNCHANGED.
    assert Code.STRATEGY_CAPABILITY_NOT_IN_BUILD.value in codes
    assert Code.STRATEGY_RESTRICTIONS_UNSUPPORTED.value in codes

    out = _run(config)
    assert out.diagnostics["capabilities_modelled"] is False
    assert (
        "restrictions_filters.filters.action=reduce" in out.diagnostics["capability_not_in_build"]
    )
    assert out.trades == []


# ---------------------------------------------------------------------------
# 3. Executability — active_v1 really executes.
# ---------------------------------------------------------------------------


def test_active_v1_baseline_runs() -> None:
    """The all-active_v1 baseline is admitted and DOES trade.

    Guards the inverse failure mode: a matrix that blocks everything would satisfy the
    fail-closed tests above while making the product useless."""
    config = _config()
    assert future_dev_selections(config) == ()
    assert capabilities_are_modelled(config)
    assert Code.STRATEGY_CAPABILITY_NOT_IN_BUILD.value not in _readiness_codes(_payload())

    out = _run(config)
    assert out.diagnostics["capabilities_modelled"] is True
    assert out.diagnostics["capability_not_in_build"] == []
    assert out.trades, "the active_v1 baseline must actually open a position"


def test_inert_allow_hedge_stays_runnable() -> None:
    """``allow_hedge`` WITH exit-on-opposite ON is inert, not a hedge — so it still runs.

    The engine closes the position on an opposite signal before the hedge branch is
    reachable, so the saved value executes no hedging and must not be reported as a
    selection. This keeps an already-saved strategy working instead of breaking it on a
    value that never had any effect."""
    overlay = {
        "conflict_position_handling": {
            "opposite_direction_hedge": "allow_hedge",
            "exit_on_opposite_signal": True,
        }
    }
    config = _config(**overlay)
    assert future_dev_selections(config) == ()
    assert Code.STRATEGY_CAPABILITY_NOT_IN_BUILD.value not in _readiness_codes(_payload(**overlay))
    assert _run(config).trades


def test_full_close_ignores_partial_aftermath() -> None:
    """A 100% close leaves no remainder, so its aftermath is unreachable and never gates.

    Mirrors ``partial_close_is_modelled``'s own short circuit — the reader must agree with
    the predicate or the two surfaces would disagree about an inert field."""
    config = _config(
        position_exit_logic={"close_percentage": "100", "partial_aftermath": "trailing_stop"}
    )
    assert future_dev_selections(config) == ()


def test_action_reader_mirrors_the_engine_parse_order() -> None:
    """The three skip arms of ``_read_filter_actions`` agree with ``_parse_restriction``.

    (1) An ABSENT action is the modelled block default — the engine's ``action is None``
    arm — so it is not a saved selection and must never gate. (2) A DISABLED filter is
    inert (the ``_read_filter_types`` rule). (3) A filter whose TYPE is unmodelled bails
    in the engine before the action is ever read, so only the filter_type row reports —
    reporting the unreachable action too would be the #533 class of false claim."""
    absent = {
        "restrictions_filters": {
            "rule": "any",
            "filters": [
                {
                    "filter_type": "max_daily_loss_filter",
                    "enabled": True,
                    "filter_id": "flt_r1",
                    "config": {"limit_percent": "2"},
                }
            ],
        }
    }
    assert future_dev_selections(_config(**absent)) == ()
    assert Code.STRATEGY_CAPABILITY_NOT_IN_BUILD.value not in _readiness_codes(_payload(**absent))

    disabled = {
        "restrictions_filters": {
            "rule": "any",
            "filters": [
                {
                    "filter_type": "max_daily_loss_filter",
                    "enabled": False,
                    "filter_id": "flt_r2",
                    "config": {"limit_percent": "2", "action": "warn"},
                }
            ],
        }
    }
    assert future_dev_selections(_config(**disabled)) == ()

    unmodelled_type = {
        "restrictions_filters": {
            "rule": "any",
            "filters": [
                {
                    "filter_type": "volatility_filter",
                    "enabled": True,
                    "filter_id": "flt_r3",
                    "config": {"action": "warn"},
                }
            ],
        }
    }
    selected = [(o.field_path, o.value) for o in future_dev_selections(_config(**unmodelled_type))]
    assert selected == [("restrictions_filters.filters.filter_type", "volatility_filter")]


@pytest.mark.parametrize(
    "option",
    [o for o in CAPABILITY_MATRIX if o.status == "active_v1"],
    ids=[f"{o.field_path}={o.value}" for o in CAPABILITY_MATRIX if o.status == "active_v1"],
)
def test_active_v1_options_are_never_reported_as_future_dev(option: CapabilityOption) -> None:
    """An ``active_v1`` value is never a refusal, whatever else the config holds."""
    assert option_status(option.field_path, option.value) == "active_v1"
    assert option not in FUTURE_DEV_OPTIONS


# ---------------------------------------------------------------------------
# 4. UI mirror parity — the editor's table equals the Python canon.
# ---------------------------------------------------------------------------


def test_generated_typescript_mirror_is_up_to_date() -> None:
    """``frontend/src/lib/engineCapabilityMatrix.generated.ts`` matches the matrix.

    The single-source-of-truth guarantee for the UI half of F-05: the Strategy editor
    disables options from this generated file, so if it drifts from the Python matrix the
    editor could offer an option the engine refuses. Regenerate with::

        cd backend && uv run python tools/export_capability_matrix.py
    """
    import tools.export_capability_matrix as exporter

    target = exporter._TARGET
    assert target.exists(), f"missing generated mirror: {target}"
    assert target.read_text(encoding="utf-8") == exporter.render(), (
        "the generated TS capability mirror is stale — run "
        "`cd backend && uv run python tools/export_capability_matrix.py`"
    )
