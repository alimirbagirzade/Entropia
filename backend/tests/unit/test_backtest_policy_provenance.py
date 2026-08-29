"""GH #534 — every conflict / order / sizing / scaling / cost policy the engine resolved
is readable back off a Result's diagnostics provenance block.

The block already published most policy tokens, but eight fields were missing (issue #534's
table plus the six the ADIM 11 capability-matrix adjudication found). Each omission has the
same consequence: a Result cannot be read back to the option that governed it without
re-deriving the strategy revision, and for two of them the value was not recoverable from a
Result *at all*.

Two of these fields need more than "publish the saved value":

* ``same_candle_entry_exit`` was visible only inside an ``entry_exit_collision`` event's
  ``detail["policy"]`` — so a run in which no collision happened recorded nothing, even
  though the policy still governed. Its one aggregate signal, ``suppressed_entries``, is
  shared with two unrelated suppression paths and so attributes to nothing.
* ``stop_priority_order`` is nullable, and ``null`` is the common case. Publishing only the
  saved value would say nothing about what governed; publishing only the resolved order
  would report a canonical order the operator never chose as though they had. Both are
  published, the way this block already separates a saved policy from its executed form.

Every assertion here drives a NON-DEFAULT value. A fixture whose fields are all ``None``
would pass against a block that published a hardcoded ``None`` for each key.
"""

from __future__ import annotations

from typing import Any

import tests.unit.test_backtest_engine as base
from entropia.domain.backtest.execution.fills import (
    _stop_priority_index,
    stop_priority_sequence,
)
from entropia.domain.strategy.config import StrategyConfig

# The eight fields #534 names, as the keys this block publishes them under. ``stop_priority_order``
# contributes two keys because the saved input and the resolved order are two different facts.
_PUBLISHED_KEYS = (
    "same_candle_entry_exit",
    "stop_priority_order",
    "stop_priority_order_resolved",
    "slippage_mode",
    "limit_price_rule",
    "limit_partial_fill_policy",
    "sizing_formula_type",
    "scaling_timeframe",
    "scaling_timeframe_mode",
)


def _patched(config: StrategyConfig, patch: dict[str, Any]) -> StrategyConfig:
    """Re-validate ``config`` with ``patch`` deep-merged in.

    The base fixture does not expose every sub-config as a keyword, and widening its
    signature for provenance-only fields would change a fixture eight other modules share.
    """
    payload = config.model_dump(mode="json")

    def merge(dst: dict[str, Any], src: dict[str, Any]) -> None:
        for key, value in src.items():
            if isinstance(value, dict) and isinstance(dst.get(key), dict):
                merge(dst[key], value)
            else:
                dst[key] = value

    merge(payload, patch)
    return StrategyConfig.model_validate(payload)


def _diagnostics(config: StrategyConfig) -> dict[str, Any]:
    return base._run(config, base._long_breakout_then_stop()).diagnostics


def test_every_named_policy_field_is_published_with_its_configured_value() -> None:
    """All eight #534 fields carry the SAVED value, driven away from every default.

    One run configures all of them at once: they are independent keys on one dict, and a
    per-field run would not detect a key that reads the wrong sub-config (the defect this
    test's own first draft had, publishing ``stop_priority_order`` off ``conflict_cfg``).

    ``formula_based_sizing`` is not modelled in this build, so this run is financially
    inert — which is exactly a case where provenance has to survive: an inert Result must
    still say which options it was asked to run.
    """
    config = _patched(
        base._config(
            same_candle_entry_exit="exit_first",
            method="formula_based_sizing",
            formula_type="kelly_criterion",
        ),
        {
            "data": {
                "costs": {"slippage_mode": "historical_slippage_if_available"},
                "order_config": {
                    "type": "limit_order",
                    "limit": {
                        "price_rule": "signal_price_minus_offset",
                        "offset_value": "1.0",
                        "unfilled_policy": "cancel_order",
                        "partial_fill_policy": "minimum_50_percent",
                    },
                },
            },
            "protection_stop_logic": {"stop_priority_order": ["absolute", "percentage"]},
            "scaling_logic": {
                "enabled": True,
                "method": "price_distance_scaling",
                "trigger_distance": "2.00",
                "max_layers": 3,
                "layer_sizing": {"mode": "percentage_of_initial", "percentage": "50"},
                "timeframe": "1h",
                "timeframe_mode": "increasing_by_layer",
            },
        },
    )
    diagnostics = _diagnostics(config)

    missing = [key for key in _PUBLISHED_KEYS if key not in diagnostics]
    assert not missing, f"provenance block omits {missing}"

    assert diagnostics["same_candle_entry_exit"] == "exit_first"
    assert diagnostics["slippage_mode"] == "historical_slippage_if_available"
    assert diagnostics["limit_price_rule"] == "signal_price_minus_offset"
    assert diagnostics["limit_partial_fill_policy"] == "minimum_50_percent"
    assert diagnostics["sizing_formula_type"] == "kelly_criterion"
    assert diagnostics["scaling_timeframe"] == "1h"
    assert diagnostics["scaling_timeframe_mode"] == "increasing_by_layer"
    assert diagnostics["stop_priority_order"] == ["absolute", "percentage"]

    # Vacuity guard: none of the values above may be the field's own default, or this test
    # would pass against a block that published the default for every key.
    default = _diagnostics(base._config())
    shared = [key for key in _PUBLISHED_KEYS if default.get(key) == diagnostics[key]]
    assert not shared, f"these keys were not driven off their default value: {shared}"


def test_the_same_candle_policy_is_published_when_no_collision_occurred() -> None:
    """#534's core complaint: the policy was recorded only by a collision EVENT.

    These bars produce no ``entry_exit_collision``, so before this change the run carried no
    record of the policy at all — the field is what makes it readable."""
    config = base._config(same_candle_entry_exit="exit_first")
    output = base._run(config, base._long_breakout_then_stop())

    collisions = [e for e in output.signal_events if e.event_type == "entry_exit_collision"]
    assert collisions == [], "fixture must NOT collide, or the event would carry the policy"
    assert output.diagnostics["same_candle_entry_exit"] == "exit_first"


def test_a_saved_null_stop_priority_order_still_publishes_the_order_that_governed() -> None:
    """The nullable case, which is the common one: ``null`` in, canonical §9.2 order out.

    The saved value stays ``None`` — a reader must still be able to tell that the operator
    chose nothing, which a resolved-only field would hide."""
    diagnostics = _diagnostics(base._config())

    assert diagnostics["stop_priority_order"] is None
    assert diagnostics["stop_priority_order_resolved"] == ["percentage", "trailing", "absolute"]


def test_the_saved_and_resolved_stop_priority_orders_are_two_different_facts() -> None:
    """A partial saved order resolves to a TOTAL one; publishing either alone loses a fact."""
    config = _patched(
        base._config(), {"protection_stop_logic": {"stop_priority_order": ["absolute"]}}
    )
    diagnostics = _diagnostics(config)

    assert diagnostics["stop_priority_order"] == ["absolute"]
    # "absolute" leads; the keys it omits are appended in canonical order, so the result is
    # total and deterministic — and demonstrably not a copy of the saved input.
    assert diagnostics["stop_priority_order_resolved"] == ["absolute", "percentage", "trailing"]
    assert diagnostics["stop_priority_order_resolved"] != diagnostics["stop_priority_order"]


def test_the_published_order_is_the_one_the_combination_engine_ranks_by() -> None:
    """Single-derivation guard.

    The published sequence is only trustworthy while it IS the ranking the fills resolve
    against. A second implementation on the reporting side would be free to drift, and no
    behavioural test would catch it: the golden scenarios would keep passing with a wrong
    order published beside correct trades.
    """
    for custom, logic in (
        (None, []),
        (None, ["logic:b1"]),
        (["absolute"], []),
        (["trailing", "logic:b2"], ["logic:b1", "logic:b2"]),
    ):
        sequence = stop_priority_sequence(custom, logic)
        index = _stop_priority_index(custom, logic)
        assert index == {key: i for i, key in enumerate(sequence)}, (custom, logic)
        # The resolution must stay TOTAL: every enabled key ranks, and no key ranks twice.
        assert set(sequence) >= set(logic) | {"percentage", "trailing", "absolute"}
        assert len(set(sequence)) == len(sequence)
