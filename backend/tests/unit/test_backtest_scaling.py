"""F-07d — same-direction scaling (price-distance ladder) engine tests (Master Ref §11).

The bar-replay engine held one fixed-size position per lifecycle and silently ignored a
saved ``scaling_logic``. These tests pin the new behaviour: each ``retracement_distance``%
ADVERSE close from the reference (initial entry fill, then each trigger close) creates ONE
layer candidate; layer-count caps gate candidate CREATION (an exhausted ladder generates
nothing), exposure/size caps gate ACCEPTANCE (an over-cap layer is REJECTED with a ledger
reason, NEVER auto-trimmed — §11.4 exposure binding). An accepted layer fills at the trigger
bar's close and folds into the single position as a size-weighted average basis. Logic-based
scaling, a per-layer timeframe override and a missing add size FAIL CLOSED (Ready Check
blocker + an inert engine run). Each setting has a positive and a negative case (spec F-07
acceptance).

Entries come from a real, production-reachable ``ta.sma`` cross plan (see
tests/unit/engine_signal_plan.py — F-24: the engine's breakout proxy is unreachable in a real
RUN, so no fixture is allowed to depend on it): 20 look-back bars establish the MA, then an
upside breakout (long @102) or downside breakdown (short @98) crosses it; end-of-data closes
the position.
"""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from typing import Any

from entropia.domain.backtest.engine import (
    EngineOutput,
    run_engine,
    scaling_is_modelled,
)
from entropia.domain.strategy.config import StrategyConfig
from tests.unit.engine_signal_plan import sma_entry_plan

_ZERO_COST = {"slippage_mode": "percentage_slippage", "slippage_value": "0"}

_LOGIC_BLOCK = {
    "block_id": "sc_1",
    "display_order": 0,
    "package_ref": {
        "package_root_id": "pkg_1",
        "package_revision_id": "pkgrev_1",
        "package_content_hash": "pkghash_1",
    },
    "trigger_source": "indicator_native_trigger",
    "requirement": "required",
}


def _price_scaling(
    *,
    retracement: str = "1.0",
    layers: int = 3,
    add_size: str = "percent_of_initial",
    add_size_value: str | None = "50",
    limits: dict[str, Any] | None = None,
    timeframe: str = "same_as_base_tf",
) -> dict[str, Any]:
    """An enabled Price-Distance scaling subtree (the modelled method)."""
    scaling: dict[str, Any] = {
        "enabled": True,
        "timeframe": timeframe,
        "method": "price_distance_scaling",
        "price_scaling": {"retracement_distance": retracement, "layers": layers},
        "add_size": add_size,
    }
    if add_size_value is not None:
        scaling["add_size_value"] = add_size_value
    if limits is not None:
        scaling["scaling_limits"] = limits
    return scaling


def _logic_scaling() -> dict[str, Any]:
    """An enabled Logic-Based scaling subtree (deferred -> fail closed)."""
    return {
        "enabled": True,
        "method": "logic_based_scaling",
        "logic_scaling": {"indicator_blocks": [_LOGIC_BLOCK]},
        "add_size_value": "50",
    }


def _config(
    *,
    scaling: dict[str, Any] | None = None,
    position_size_limits: dict[str, Any] | None = None,
    commission: str | None = None,
) -> StrategyConfig:
    """A minimal VALID StrategyConfig; only the fields the engine reads matter.

    Zero costs by default so a fill lands exactly on the resolved price; no protection
    stop so the ladder (not a stop) governs the position's life.

    ``opposite_direction_hedge="ignore"`` isolates the rule under test. A ladder scales INTO
    an adverse move, and under a real MA cross (F-24) an adverse retracement below the MA is
    itself an opposite signal — which under the default hedge policy would close the position
    before the ladder's later layers can trigger. Closing on an opposite signal is the
    documented hedge/reverse rule (§9), not the scaling rule; pinning it here keeps the ladder
    the only thing governing the position's life, exactly as this fixture's bars intend. The
    retired breakout proxy produced no opposite signal over these retracement bars, so this
    fixture never had to say which rule it meant."""
    sizing: dict[str, Any] = {"method": "base_position_size", "base_position_size": "50"}
    if position_size_limits is not None:
        sizing["position_size_limits"] = position_size_limits
    costs: dict[str, Any] = dict(_ZERO_COST)
    if commission is not None:
        costs["commission"] = commission
    return StrategyConfig.model_validate(
        {
            "strategy_root_id": "strat_root_1",
            "display_name": "Scaling Fixture",
            "rationale_family_id": "rf_1",
            "data": {
                "instrument_id": "BTCUSDT",
                "market_dataset_root_id": "md_root_1",
                "market_dataset_revision_id": "md_rev_1",
                "market_dataset_content_hash": "mdhash_1",
                "backtest_range": {
                    "start": "2024-01-01T00:00:00Z",
                    "end": "2024-12-31T23:59:59Z",
                },
                "initial_capital": "10000.00",
                "execution": {
                    "entry_timing": "current_candle_close",
                    "exit_timing": "current_candle_close",
                },
                "order_config": {"type": "market_order"},
                "costs": costs,
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
            "position_exit_logic": {},
            "protection_stop_logic": {},
            "position_sizing": sizing,
            "scaling_logic": scaling,
            "restrictions_filters": {"rule": "any", "filters": []},
            "conflict_position_handling": {"opposite_direction_hedge": "ignore"},
        }
    )


def _bar(ts: str, o: str, h: str, low: str, c: str) -> dict[str, Any]:
    return {"timestamp": ts, "open": o, "high": h, "low": low, "close": c, "volume": "10"}


def _fu(day: int, o: str, h: str, low: str, c: str) -> dict[str, Any]:
    return _bar(f"2024-01-{day:02d}T00:00:00Z", o, h, low, c)


def _flat(n: int, *, base: str = "100") -> list[dict[str, Any]]:
    """n flat look-back bars at ``base``, which is also where the entry MA settles."""
    return [_bar(f"2024-01-{i + 1:02d}T00:00:00Z", base, base, base, base) for i in range(n)]


def _long_then(followups: list[dict[str, Any]], *, base: str = "100") -> list[dict[str, Any]]:
    """20 look-back bars at ``base``, an upside breakout (long @102), then the follow-ups.

    ``base`` sets where the entry MA settles, and therefore how far a retracement can run
    before it crosses back under the MA and becomes an EXIT signal. A ladder whose later
    rungs sit below 100 needs a lower ``base`` so the whole ladder is a retracement WITHIN
    the trend (the case scaling exists for) rather than a trend break. Under the retired
    breakout proxy this knob was a window ``floor`` — the proxy exited on a new window low,
    which a real MA-cross strategy does not do."""
    bars = _flat(20, base=base)
    bars.append(_bar("2024-01-21T00:00:00Z", "100", "103", "100", "102"))  # breakout -> long
    return bars + followups


def _short_then(followups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """20 look-back bars, a downside breakdown (short @98), then the follow-up bars."""
    bars = _flat(20)
    bars.append(_bar("2024-01-21T00:00:00Z", "100", "100", "97", "98"))  # breakdown -> short
    return bars + followups


# Retracement bars for a long @102 (ref 102): day22 crosses the 1% threshold (100.98) while
# staying above the 100 window floor; day23 closes the run at 103 (no further cross).
_RETRACE = _fu(22, "101", "101", "100.4", "100.5")
_CLOSE_UP = _fu(23, "103", "104", "103", "103")


def _run(config: StrategyConfig, bars: list[dict[str, Any]], *, batch: int = 8) -> EngineOutput:
    def batched() -> Iterator[list[dict[str, Any]]]:
        for start in range(0, len(bars), batch):
            yield bars[start : start + batch]

    return run_engine(
        strategy_config=config,
        bar_batches=batched(),
        execution_key="exec_key_test",
        indicator_plan=sma_entry_plan(),
    )


def _events(out: EngineOutput, kind: str) -> list[dict[str, Any]]:
    return [e.detail for e in out.signal_events if e.event_type == kind]


# --------------------------------------------------------------------------- #
# Predicate — shared source of truth (readiness + engine)                     #
# --------------------------------------------------------------------------- #


def test_predicate_disabled_or_absent_scaling_is_modelled() -> None:
    # No subtree / enabled=false -> nothing to scale -> trivially modelled.
    assert scaling_is_modelled(_config())
    assert scaling_is_modelled(_config(scaling={"enabled": False}))


def test_predicate_price_distance_modelled_logic_based_not() -> None:
    assert scaling_is_modelled(_config(scaling=_price_scaling()))
    assert scaling_is_modelled(_config(scaling=_price_scaling(limits={"max_scaling_layers": 2})))
    assert not scaling_is_modelled(_config(scaling=_logic_scaling()))


def test_predicate_fails_closed_on_timeframe_override_and_missing_config() -> None:
    # A per-layer timeframe override (custom TF sequence family) is deferred; an enabled
    # subtree with no method / no derivable add size cannot produce a layer.
    assert not scaling_is_modelled(_config(scaling=_price_scaling(timeframe="15m")))
    assert not scaling_is_modelled(_config(scaling={"enabled": True}))
    assert not scaling_is_modelled(_config(scaling=_price_scaling(add_size_value=None)))


def test_predicate_fails_closed_on_misconfigured_caps() -> None:
    # Spec §11.4: Max Additional Layers is an int >= 0; a non-positive total-exposure cap
    # could never hold any position — both are misconfigurations, never silently ignored.
    assert not scaling_is_modelled(
        _config(scaling=_price_scaling(limits={"max_scaling_layers": -1}))
    )
    assert not scaling_is_modelled(
        _config(scaling=_price_scaling(limits={"max_total_position_size": "0"}))
    )


# --------------------------------------------------------------------------- #
# Baseline — disabled scaling is byte-identical                               #
# --------------------------------------------------------------------------- #


def test_scaling_absent_or_disabled_is_byte_identical_baseline() -> None:
    absent = _run(_config(), _long_then([_RETRACE, _CLOSE_UP]))
    disabled = _run(_config(scaling={"enabled": False}), _long_then([_RETRACE, _CLOSE_UP]))
    for out in (absent, disabled):
        assert out.diagnostics["scaling_enabled"] is False
        assert out.diagnostics["scaling_modelled"] is True
        assert out.diagnostics["scaling_method"] is None
        assert out.diagnostics["scale_layers_added"] == 0
        assert not _events(out, "scale_layer_added")
        assert out.summary["total_trades"] == 1
        assert out.trades[0].pnl == Decimal("50.00")  # (103-102)*50, un-scaled


# --------------------------------------------------------------------------- #
# Price-distance ladder — positive                                            #
# --------------------------------------------------------------------------- #


def test_price_distance_layer_added_on_retracement() -> None:
    # Long @102 (ref 102); day22 closes 100.5 <= 100.98 (1% adverse) -> one 25-unit layer
    # (50% of the initial 50) @100.5 -> basis (102*50 + 100.5*25)/75 = 101.50, size 75.
    out = _run(_config(scaling=_price_scaling()), _long_then([_RETRACE, _CLOSE_UP]))
    assert out.diagnostics["scale_layers_added"] == 1
    assert out.diagnostics["scale_layers_rejected"] == 0
    assert out.diagnostics["scaling_enabled"] is True
    assert out.diagnostics["scaling_method"] == "price_distance_scaling"
    assert out.diagnostics["max_total_exposure_active"] is False
    added = _events(out, "scale_layer_added")
    assert len(added) == 1
    evt = added[0]
    assert evt["layer_seq"] == 1
    assert Decimal(evt["reference"]) == Decimal("102")
    assert Decimal(evt["fill_price"]) == Decimal("100.50")
    assert Decimal(evt["layer_size"]) == Decimal("25")
    assert Decimal(evt["new_size"]) == Decimal("75")
    assert Decimal(evt["entry_basis"]) == Decimal("101.50")
    assert Decimal(evt["exposure"]) == Decimal("7612.50")
    assert evt["method"] == "price_distance_scaling"
    # One lifecycle, one trade: the scaled position closes at end-of-data (103).
    assert out.summary["total_trades"] == 1
    assert out.trades[0].pnl == Decimal("112.50")  # (103 - 101.50) * 75


def test_ladder_advances_reference_and_adds_layers() -> None:
    # 0.75% ladder over a deep-floor window (the retracement bars must not trip the breakout
    # exit): thresholds 101.235 (ref 102) then 99.74625 (ref 100.5) -> two 25-unit layers ->
    # basis (5100 + 2512.50 + 2492.50)/100 = 101.05, size 100.
    followups = [
        _RETRACE,
        _fu(23, "100", "100", "99.5", "99.7"),
        _fu(24, "101", "101", "100.5", "101"),
    ]
    out = _run(
        _config(scaling=_price_scaling(retracement="0.75")),
        _long_then(followups, base="90"),
    )
    assert out.diagnostics["scale_layers_added"] == 2
    added = _events(out, "scale_layer_added")
    assert [e["layer_seq"] for e in added] == [1, 2]
    # The reference advances to each trigger close (initial entry -> previous filled layer).
    assert Decimal(added[0]["reference"]) == Decimal("102")
    assert Decimal(added[1]["reference"]) == Decimal("100.5")
    assert Decimal(added[1]["entry_basis"]) == Decimal("101.05")
    assert out.summary["total_trades"] == 1
    assert out.trades[0].pnl == Decimal("-5.00")  # (101 - 101.05) * 100


def test_percent_of_current_compounds_layer_size() -> None:
    # percent_of_current: layer1 = 50% of 50 = 25 (size 75), layer2 = 50% of 75 = 37.5
    # (size 112.5) — distinguishes the basis from percent_of_initial (25 + 25).
    followups = [
        _RETRACE,
        _fu(23, "100", "100", "99.5", "99.7"),
        _fu(24, "101", "101", "100.5", "101"),
    ]
    out = _run(
        _config(scaling=_price_scaling(retracement="0.75", add_size="percent_of_current")),
        _long_then(followups, base="90"),
    )
    added = _events(out, "scale_layer_added")
    assert len(added) == 2
    assert Decimal(added[1]["layer_size"]) == Decimal("37.5")
    assert Decimal(added[1]["new_size"]) == Decimal("112.5")
    assert Decimal(added[1]["entry_basis"]) == Decimal("100.90")
    assert out.trades[0].pnl == Decimal("11.25")  # (101 - 100.90) * 112.5


def test_fixed_amount_layer_size() -> None:
    # fixed_amount: the layer is add_size_value in SIZE UNITS (10) regardless of the
    # position's size -> basis (5100 + 1005)/60 = 101.75, size 60.
    out = _run(
        _config(scaling=_price_scaling(add_size="fixed_amount", add_size_value="10")),
        _long_then([_RETRACE, _CLOSE_UP]),
    )
    added = _events(out, "scale_layer_added")
    assert len(added) == 1
    assert Decimal(added[0]["layer_size"]) == Decimal("10")
    assert Decimal(added[0]["entry_basis"]) == Decimal("101.75")
    assert out.trades[0].pnl == Decimal("75.00")  # (103 - 101.75) * 60


def test_short_position_scales_on_adverse_rise() -> None:
    # Short @98 (ref 98); day22 closes 99 >= 98.98 (1% adverse RISE) -> a 25-unit layer @99
    # -> basis (98*50 + 99*25)/75 = 98.33 (quantized), size 75; closes at 98.5 end-of-data.
    followups = [_fu(22, "99", "99.5", "98.5", "99"), _fu(23, "98.5", "98.8", "98.2", "98.5")]
    out = _run(_config(scaling=_price_scaling()), _short_then(followups))
    added = _events(out, "scale_layer_added")
    assert len(added) == 1
    assert Decimal(added[0]["reference"]) == Decimal("98")
    assert Decimal(added[0]["entry_basis"]) == Decimal("98.33")
    assert out.summary["total_trades"] == 1
    assert out.trades[0].direction == "short"
    assert out.trades[0].pnl == Decimal("-12.75")  # (98.33 - 98.5) * 75


def test_layer_commission_charged_at_fill() -> None:
    # The layer's own entry fill pays one commission AT FILL; the close still books the
    # initial round trip -> trade pnl = (103-101.5)*75 - 2 = 110.50, equity additionally
    # carries the mid-run 1.00 layer fill -> net 109.50.
    out = _run(
        _config(scaling=_price_scaling(), commission="1.0"),
        _long_then([_RETRACE, _CLOSE_UP]),
    )
    assert out.diagnostics["scale_layers_added"] == 1
    assert out.trades[0].pnl == Decimal("110.50")
    assert out.summary["net_profit"] == Decimal("109.50")
    assert out.summary["final_equity"] == Decimal("10109.50")


# --------------------------------------------------------------------------- #
# Layer-count caps — gate candidate CREATION (no candidate, no event)         #
# --------------------------------------------------------------------------- #


def test_method_layer_count_caps_candidate_creation() -> None:
    # layers=1: the second threshold cross generates NO candidate at all (an exhausted
    # ladder creates nothing, §11.4) — no rejection event, no reference churn.
    followups = [
        _RETRACE,
        _fu(23, "100", "100", "99.5", "99.7"),
        _fu(24, "101", "101", "100.5", "101"),
    ]
    out = _run(
        _config(scaling=_price_scaling(retracement="0.75", layers=1)),
        _long_then(followups, base="90"),
    )
    assert out.diagnostics["scale_layers_added"] == 1
    assert out.diagnostics["scale_layers_rejected"] == 0
    assert not _events(out, "scale_layer_rejected")


def test_max_scaling_layers_zero_disables_ladder() -> None:
    # An explicit global cap of 0 additional layers is a LEGAL config (int >= 0): the run
    # trades normally, the ladder simply never fires.
    out = _run(
        _config(scaling=_price_scaling(limits={"max_scaling_layers": 0})),
        _long_then([_RETRACE, _CLOSE_UP]),
    )
    assert out.diagnostics["scaling_modelled"] is True
    assert out.diagnostics["scale_layers_added"] == 0
    assert not _events(out, "scale_layer_added")
    assert out.summary["total_trades"] == 1
    assert out.trades[0].pnl == Decimal("50.00")  # un-scaled (103-102)*50


# --------------------------------------------------------------------------- #
# Exposure / size caps — gate ACCEPTANCE (reject + ledger reason, no trim)    #
# --------------------------------------------------------------------------- #


def test_max_total_exposure_rejects_layer_never_trims() -> None:
    # Max Total Exposure 60 < 50+25: the candidate is REJECTED whole (never trimmed to a
    # 10-unit sliver) with the reason in the ledger; the position stays 50 units.
    out = _run(
        _config(scaling=_price_scaling(limits={"max_total_position_size": "60"})),
        _long_then([_RETRACE, _CLOSE_UP]),
    )
    assert out.diagnostics["max_total_exposure_active"] is True
    assert out.diagnostics["scale_layers_added"] == 0
    assert out.diagnostics["scale_layers_rejected"] == 1
    assert not _events(out, "scale_layer_added")
    rejected = _events(out, "scale_layer_rejected")
    assert len(rejected) == 1
    assert rejected[0]["reason"] == "max_total_exposure"
    assert Decimal(rejected[0]["cap"]) == Decimal("60")
    assert Decimal(rejected[0]["candidate_size"]) == Decimal("25")
    # The un-scaled 50-unit position closes at 103: pnl proves no partial layer opened.
    assert out.summary["total_trades"] == 1
    assert out.trades[0].pnl == Decimal("50.00")


def test_position_size_limit_rejects_layer() -> None:
    # The §6 global max_position_size cap binds the scaled TOTAL too: 50+25 > 60 -> the
    # candidate is rejected (uniform no-trim rule), reason position_size_limit.
    out = _run(
        _config(
            scaling=_price_scaling(),
            position_size_limits={"max_position_size": "60"},
        ),
        _long_then([_RETRACE, _CLOSE_UP]),
    )
    assert out.diagnostics["scale_layers_added"] == 0
    rejected = _events(out, "scale_layer_rejected")
    assert len(rejected) == 1
    assert rejected[0]["reason"] == "position_size_limit"
    assert out.trades[0].pnl == Decimal("50.00")


# --------------------------------------------------------------------------- #
# Fail-closed configs — Ready Check blocker + inert engine backstop           #
# --------------------------------------------------------------------------- #


def test_logic_based_scaling_fails_closed() -> None:
    out = _run(_config(scaling=_logic_scaling()), _long_then([_RETRACE, _CLOSE_UP]))
    assert out.diagnostics["scaling_modelled"] is False
    assert out.summary["total_trades"] == 0
    assert "scaling_unsupported:logic_based_scaling" in out.diagnostics["warnings"]


def test_timeframe_override_fails_closed() -> None:
    out = _run(_config(scaling=_price_scaling(timeframe="15m")), _long_then([_RETRACE, _CLOSE_UP]))
    assert out.diagnostics["scaling_modelled"] is False
    assert out.summary["total_trades"] == 0
    assert "scaling_unsupported:price_distance_scaling" in out.diagnostics["warnings"]


def test_missing_add_size_value_fails_closed() -> None:
    out = _run(
        _config(scaling=_price_scaling(add_size_value=None)),
        _long_then([_RETRACE, _CLOSE_UP]),
    )
    assert out.diagnostics["scaling_modelled"] is False
    assert out.summary["total_trades"] == 0
    assert "scaling_unsupported:price_distance_scaling" in out.diagnostics["warnings"]
