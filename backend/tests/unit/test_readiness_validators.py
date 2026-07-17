"""Stage 4b — pure Backtest Ready Check validator unit tests (doc 14 §9.2, §15).

No DB. Each test constructs resolved ``ReadinessItemInput`` value objects (the same
shape the command passes) and asserts the aggregate ``evaluate_readiness`` output.
Maps to acceptance IDs RC-01..RC-06, RC-08, RC-16 + the 3d follow-ups (TL-09,
TL-11, OHLCV-fallback) and allocation RC-03/RC-04.
"""

from __future__ import annotations

from typing import Any

from entropia.domain.allocation.enums import AllocationIssueCode, AllocationIssueSeverity
from entropia.domain.allocation.rules import AllocationIssue
from entropia.domain.mainboard.enums import MainboardItemKind
from entropia.domain.readiness.enums import ReadinessIssueCode as Code
from entropia.domain.readiness.enums import ReadinessScope, ReadinessSeverity, ReadinessState
from entropia.domain.readiness.issues import (
    ExternalImportState,
    ReadinessIssue,
    ReadinessItemInput,
)
from entropia.domain.readiness.validators import evaluate_readiness, is_stale

# --------------------------------------------------------------------------- #
# Payload builders (minimal VALID domain configs; override per test)          #
# --------------------------------------------------------------------------- #


def _strategy_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "strategy_root_id": "strat_root_1",
        "display_name": "MA cross",
        "rationale_family_id": "rf_1",
        "data": {
            "instrument_id": "BTCUSDT",
            "market_dataset_root_id": "md_root_1",
            "market_dataset_revision_id": "md_rev_1",
            "market_dataset_content_hash": "a" * 64,
            "backtest_range": {"start": "2024-01-01T00:00:00Z", "end": "2024-06-01T00:00:00Z"},
            "initial_capital": "10000.00",
            "execution": {
                "entry_timing": "next_candle_open",
                "exit_timing": "next_candle_open",
            },
            "order_config": {"type": "market_order"},
            "costs": {"commission": "0.04", "spread": "0.01", "slippage_value": "0.1"},
            "intrabar_policy": {"tick_policy": "inherit"},
            "funding": {"enabled": False},
        },
        "position_entry_logic": {
            "signal_block": {"rule": "required_indicator_blocks_only"},
            "indicator_blocks": [
                {
                    "block_id": "ib_1",
                    "display_order": 0,
                    "package_ref": {
                        "package_root_id": "pkg_root_1",
                        "package_revision_id": "pkg_rev_1",
                        "package_content_hash": "b" * 64,
                    },
                    "trigger_source": "indicator_native_trigger",
                    "requirement": "required",
                }
            ],
        },
        "position_exit_logic": {},
        "protection_stop_logic": {"percentage_stop": {"enabled": True, "loss_percentage": "1.0"}},
        "position_sizing": {"method": "base_position_size", "base_position_size": "1.0"},
        "restrictions_filters": {},
        "conflict_position_handling": {},
    }
    payload.update(overrides)
    return payload


def _trade_log_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "kind": "trade_log",
        "identity": {"display_name": "MT5 export"},
        "source": {"provider_name": "MetaTrader", "source_kind": "file"},
        "instrument_scope": {"instrument_id": "BTCUSDT", "display_symbol": "BTCUSDT"},
        "time_model": {"resolution_kind": "event_based", "source_timezone": "UTC"},
        "data_quality": {"content_profile": "trade_log_with_ohlcv"},
        "price_policy": {"source": "trade_log_entry_exit_price"},
        "ohlcv_policy": {"use_mode": "use_if_supplied_and_needed"},
        "capital": {"independent_initial_capital": "1000", "currency": "USDT"},
        "import_binding": {"source_asset_id": "sa_1", "record_batch_revision_id": "batch_1"},
    }
    payload.update(overrides)
    return payload


def _strategy_item(item_id: str = "item_s1", **overrides: Any) -> ReadinessItemInput:
    return ReadinessItemInput(
        item_id=item_id,
        kind=MainboardItemKind.STRATEGY,
        root_id=overrides.pop("root_id", f"root_{item_id}"),
        revision_id=f"rev_{item_id}",
        available=overrides.pop("available", True),
        payload=overrides.pop("payload", _strategy_payload()),
    )


def _trade_log_item(item_id: str = "item_t1", **overrides: Any) -> ReadinessItemInput:
    external = overrides.pop(
        "external",
        ExternalImportState(found=True, succeeded=True, accepted_count=5, instrument_id="BTCUSDT"),
    )
    return ReadinessItemInput(
        item_id=item_id,
        kind=MainboardItemKind.TRADE_LOG,
        root_id=overrides.pop("root_id", f"root_{item_id}"),
        revision_id=f"rev_{item_id}",
        available=overrides.pop("available", True),
        payload=overrides.pop("payload", _trade_log_payload()),
        external=external,
    )


def _codes(evaluation: Any) -> set[str]:
    return {str(i.code) for i in evaluation.issues}


# --------------------------------------------------------------------------- #
# Composition / lifecycle                                                     #
# --------------------------------------------------------------------------- #


def test_rc01_empty_composition_is_not_ready() -> None:
    result = evaluate_readiness([], allocation_enabled=False, allocation_issues=[])
    assert result.state == ReadinessState.NOT_READY
    assert Code.COMPOSITION_EMPTY.value in _codes(result)


def test_rc02_single_valid_strategy_is_ready() -> None:
    result = evaluate_readiness([_strategy_item()], allocation_enabled=False, allocation_issues=[])
    assert result.state == ReadinessState.READY
    assert result.issues == ()


def test_duplicate_enabled_root_blocks() -> None:
    a = _strategy_item("item_a", root_id="shared_root")
    b = _strategy_item("item_b", root_id="shared_root")
    result = evaluate_readiness([a, b], allocation_enabled=False, allocation_issues=[])
    assert Code.DUPLICATE_ENABLED_ITEM.value in _codes(result)
    assert result.state == ReadinessState.NOT_READY


def test_rc16_soft_deleted_dependency_is_unavailable() -> None:
    item = _strategy_item(available=False)
    result = evaluate_readiness([item], allocation_enabled=False, allocation_issues=[])
    # Unavailable item -> ITEM_UNAVAILABLE and, as it is the only member, also EMPTY.
    assert Code.ITEM_UNAVAILABLE.value in _codes(result)
    assert result.state == ReadinessState.NOT_READY


# --------------------------------------------------------------------------- #
# Strategy configuration (RC-05 / RC-06)                                       #
# --------------------------------------------------------------------------- #


def test_rc05_native_trigger_needs_no_condition_package() -> None:
    result = evaluate_readiness([_strategy_item()], allocation_enabled=False, allocation_issues=[])
    assert Code.CONDITION_PACKAGE_REQUIRED.value not in _codes(result)
    assert result.state == ReadinessState.READY


def test_rc06_output_plus_condition_requires_condition_package() -> None:
    payload = _strategy_payload()
    payload["position_entry_logic"]["indicator_blocks"][0]["trigger_source"] = (
        "indicator_output_plus_condition"
    )
    result = evaluate_readiness(
        [_strategy_item(payload=payload)], allocation_enabled=False, allocation_issues=[]
    )
    assert Code.CONDITION_PACKAGE_REQUIRED.value in _codes(result)
    assert result.state == ReadinessState.NOT_READY


def test_strategy_without_exit_or_stop_blocks() -> None:
    payload = _strategy_payload(protection_stop_logic=None)
    result = evaluate_readiness(
        [_strategy_item(payload=payload)], allocation_enabled=False, allocation_issues=[]
    )
    assert Code.STRATEGY_NO_EXIT_OR_STOP.value in _codes(result)


def test_strategy_unsupported_sizing_blocks() -> None:
    # F-09: an unmodelled position-sizing method (custom_formula) must BLOCK RUN — the
    # engine fails closed and would open no position, so Ready Check surfaces it.
    payload = _strategy_payload(
        position_sizing={
            "method": "formula_based_sizing",
            "formula_based": {"formula_type": "custom_formula", "formula_params": {}},
        }
    )
    result = evaluate_readiness(
        [_strategy_item(payload=payload)], allocation_enabled=False, allocation_issues=[]
    )
    assert Code.STRATEGY_SIZING_UNSUPPORTED.value in _codes(result)
    assert result.state == ReadinessState.NOT_READY


def test_strategy_supported_sizing_does_not_block() -> None:
    # A valid base_position_size strategy raises no sizing blocker (the default payload).
    result = evaluate_readiness([_strategy_item()], allocation_enabled=False, allocation_issues=[])
    assert Code.STRATEGY_SIZING_UNSUPPORTED.value not in _codes(result)


def test_strategy_unsupported_execution_timing_blocks() -> None:
    # F-07a: an unsupported entry execution timing (intrabar_touch, not modelled over
    # OHLCV) must BLOCK RUN — the engine fails closed and would open no position.
    payload = _strategy_payload()
    payload["data"]["execution"]["entry_timing"] = "intrabar_touch"
    result = evaluate_readiness(
        [_strategy_item(payload=payload)], allocation_enabled=False, allocation_issues=[]
    )
    assert Code.STRATEGY_EXECUTION_TIMING_UNSUPPORTED.value in _codes(result)
    assert result.state == ReadinessState.NOT_READY


def test_strategy_supported_execution_timing_does_not_block() -> None:
    # Both timings modelled (next_candle_open, the default payload) → no timing blocker.
    result = evaluate_readiness([_strategy_item()], allocation_enabled=False, allocation_issues=[])
    assert Code.STRATEGY_EXECUTION_TIMING_UNSUPPORTED.value not in _codes(result)


def test_strategy_unsupported_order_type_blocks() -> None:
    # F-07b: a Stop order carries no trigger price in the schema → the engine fails closed
    # (opens no position) → Ready Check surfaces STRATEGY_ORDER_TYPE_UNSUPPORTED.
    payload = _strategy_payload()
    payload["data"]["order_config"] = {"type": "stop_order"}
    result = evaluate_readiness(
        [_strategy_item(payload=payload)], allocation_enabled=False, allocation_issues=[]
    )
    assert Code.STRATEGY_ORDER_TYPE_UNSUPPORTED.value in _codes(result)
    assert result.state == ReadinessState.NOT_READY


def test_strategy_supported_order_type_does_not_block() -> None:
    # A modelled Limit order (signal price rule, not-allowed partial fill) raises no order
    # blocker; the default market_order payload likewise does not.
    payload = _strategy_payload()
    payload["data"]["order_config"] = {
        "type": "limit_order",
        "limit": {
            "price_rule": "entry_signal_price",
            "validity": "3_candles",
            "unfilled_policy": "cancel_order",
            "partial_fill_policy": "not_allowed",
        },
    }
    limit_result = evaluate_readiness(
        [_strategy_item(payload=payload)], allocation_enabled=False, allocation_issues=[]
    )
    assert Code.STRATEGY_ORDER_TYPE_UNSUPPORTED.value not in _codes(limit_result)
    market_result = evaluate_readiness(
        [_strategy_item()], allocation_enabled=False, allocation_issues=[]
    )
    assert Code.STRATEGY_ORDER_TYPE_UNSUPPORTED.value not in _codes(market_result)


def test_strategy_unsupported_partial_close_aftermath_blocks() -> None:
    # F-07c: a partial close (close_percentage 50) with a trailing aftermath is not modelled
    # (deferred to slice f) → the engine fails closed → Ready Check surfaces it.
    payload = _strategy_payload()
    payload["position_exit_logic"] = {
        "close_percentage": "50",
        "partial_aftermath": "trailing_stop",
    }
    result = evaluate_readiness(
        [_strategy_item(payload=payload)], allocation_enabled=False, allocation_issues=[]
    )
    assert Code.STRATEGY_PARTIAL_CLOSE_UNSUPPORTED.value in _codes(result)
    assert result.state == ReadinessState.NOT_READY


def test_strategy_supported_partial_close_does_not_block() -> None:
    # A 50% partial with a move-stop-to-entry aftermath is modelled; a full close (default
    # payload, close_percentage 100) likewise raises no partial-close blocker.
    payload = _strategy_payload()
    payload["position_exit_logic"] = {
        "close_percentage": "50",
        "partial_aftermath": "move_stop_to_entry",
    }
    partial = evaluate_readiness(
        [_strategy_item(payload=payload)], allocation_enabled=False, allocation_issues=[]
    )
    assert Code.STRATEGY_PARTIAL_CLOSE_UNSUPPORTED.value not in _codes(partial)
    full = evaluate_readiness([_strategy_item()], allocation_enabled=False, allocation_issues=[])
    assert Code.STRATEGY_PARTIAL_CLOSE_UNSUPPORTED.value not in _codes(full)


def test_strategy_unsupported_scaling_blocks() -> None:
    # F-07d: Logic-Based scaling needs separate scale-rule evaluators (a later slice) → the
    # engine fails closed (opens no position) → Ready Check surfaces it as a BLOCKER.
    payload = _strategy_payload()
    payload["scaling_logic"] = {
        "enabled": True,
        "method": "logic_based_scaling",
        "logic_scaling": {
            "indicator_blocks": [
                {
                    "block_id": "sc_1",
                    "display_order": 0,
                    "package_ref": {
                        "package_root_id": "pkg_root_1",
                        "package_revision_id": "pkg_rev_1",
                        "package_content_hash": "b" * 64,
                    },
                    "trigger_source": "indicator_native_trigger",
                    "requirement": "required",
                }
            ]
        },
        "add_size_value": "50",
    }
    result = evaluate_readiness(
        [_strategy_item(payload=payload)], allocation_enabled=False, allocation_issues=[]
    )
    assert Code.STRATEGY_SCALING_UNSUPPORTED.value in _codes(result)
    assert result.state == ReadinessState.NOT_READY


def test_strategy_supported_scaling_does_not_block() -> None:
    # A Price-Distance ladder on the strategy timeframe with a positive add size is modelled;
    # disabled/absent scaling (the default payload) likewise raises no scaling blocker.
    payload = _strategy_payload()
    payload["scaling_logic"] = {
        "enabled": True,
        "method": "price_distance_scaling",
        "price_scaling": {"retracement_distance": "1.0", "layers": 2},
        "add_size": "percent_of_initial",
        "add_size_value": "50",
        "scaling_limits": {"max_scaling_layers": 2, "max_total_position_size": "100"},
    }
    scaled = evaluate_readiness(
        [_strategy_item(payload=payload)], allocation_enabled=False, allocation_issues=[]
    )
    assert Code.STRATEGY_SCALING_UNSUPPORTED.value not in _codes(scaled)
    absent = evaluate_readiness([_strategy_item()], allocation_enabled=False, allocation_issues=[])
    assert Code.STRATEGY_SCALING_UNSUPPORTED.value not in _codes(absent)


def test_strategy_unsupported_leverage_blocks() -> None:
    # F-07f: 'Cross' margin mode needs a portfolio-level risk model the single-position
    # bar-replay engine does not implement → fails closed (opens no position) → BLOCKER.
    payload = _strategy_payload()
    payload["position_sizing"] = {
        "method": "base_position_size",
        "base_position_size": "1.0",
        "leverage_mode": "cross",
        "leverage": "2",
    }
    result = evaluate_readiness(
        [_strategy_item(payload=payload)], allocation_enabled=False, allocation_issues=[]
    )
    assert Code.STRATEGY_LEVERAGE_UNSUPPORTED.value in _codes(result)
    assert result.state == ReadinessState.NOT_READY


def test_strategy_supported_leverage_does_not_block() -> None:
    # 'No Leverage' and 'Isolated' with a positive multiplier are modelled; the default
    # payload (isolated, leverage 1x) likewise raises no leverage blocker.
    payload = _strategy_payload()
    payload["position_sizing"] = {
        "method": "base_position_size",
        "base_position_size": "1.0",
        "leverage_mode": "no_leverage",
        "leverage": "5",
    }
    no_leverage = evaluate_readiness(
        [_strategy_item(payload=payload)], allocation_enabled=False, allocation_issues=[]
    )
    assert Code.STRATEGY_LEVERAGE_UNSUPPORTED.value not in _codes(no_leverage)
    isolated_payload = _strategy_payload()
    isolated_payload["position_sizing"] = {
        "method": "base_position_size",
        "base_position_size": "1.0",
        "leverage_mode": "isolated",
        "leverage": "2",
    }
    isolated = evaluate_readiness(
        [_strategy_item(payload=isolated_payload)], allocation_enabled=False, allocation_issues=[]
    )
    assert Code.STRATEGY_LEVERAGE_UNSUPPORTED.value not in _codes(isolated)
    default = evaluate_readiness([_strategy_item()], allocation_enabled=False, allocation_issues=[])
    assert Code.STRATEGY_LEVERAGE_UNSUPPORTED.value not in _codes(default)


def test_strategy_unsupported_restriction_filter_blocks() -> None:
    # F-07e: a volatility filter needs an ATR/indicator data series OHLCV alone cannot
    # supply → the engine fails closed (opens no position) → Ready Check BLOCKER.
    payload = _strategy_payload()
    payload["restrictions_filters"] = {
        "rule": "any",
        "filters": [{"filter_type": "volatility_filter", "enabled": True, "filter_id": "flt_1"}],
    }
    result = evaluate_readiness(
        [_strategy_item(payload=payload)], allocation_enabled=False, allocation_issues=[]
    )
    assert Code.STRATEGY_RESTRICTIONS_UNSUPPORTED.value in _codes(result)
    assert result.state == ReadinessState.NOT_READY


def test_strategy_supported_restriction_filters_do_not_block() -> None:
    # F-07e: the modelled filters (date-blackout / max-daily-loss / consecutive-loss with
    # canonical configs) raise nothing; a DISABLED unsupported filter is not an active rule.
    payload = _strategy_payload()
    payload["restrictions_filters"] = {
        "rule": "all",
        "filters": [
            {
                "filter_type": "date_blackout_filter",
                "enabled": True,
                "filter_id": "flt_1",
                "config": {"date_ranges": [{"start": "2024-03-01", "end": "2024-03-05"}]},
            },
            {
                "filter_type": "max_daily_loss_filter",
                "enabled": True,
                "filter_id": "flt_2",
                "config": {"limit_percent": "2"},
            },
            {
                "filter_type": "consecutive_loss_filter",
                "enabled": True,
                "filter_id": "flt_3",
                "config": {"max_losses": 3},
            },
            {"filter_type": "spread_filter", "enabled": False, "filter_id": "flt_4"},
        ],
    }
    result = evaluate_readiness(
        [_strategy_item(payload=payload)], allocation_enabled=False, allocation_issues=[]
    )
    assert Code.STRATEGY_RESTRICTIONS_UNSUPPORTED.value not in _codes(result)


def test_strategy_hedge_without_exit_on_opposite_blocks() -> None:
    # F-07e: a true hedge (allow_hedge with exit-on-opposite OFF) needs two concurrent
    # opposite positions the single-position replay cannot simulate → BLOCKER.
    payload = _strategy_payload()
    payload["conflict_position_handling"] = {
        "exit_on_opposite_signal": False,
        "opposite_direction_hedge": "allow_hedge",
    }
    result = evaluate_readiness(
        [_strategy_item(payload=payload)], allocation_enabled=False, allocation_issues=[]
    )
    assert Code.STRATEGY_CONFLICT_HANDLING_UNSUPPORTED.value in _codes(result)
    assert result.state == ReadinessState.NOT_READY


def test_strategy_modelled_conflict_handling_does_not_block() -> None:
    # F-07e: the defaults (exit-on-opposite ON) and every close/ignore combination are
    # modelled; only the hedge-without-exit combination blocks.
    default = evaluate_readiness([_strategy_item()], allocation_enabled=False, allocation_issues=[])
    assert Code.STRATEGY_CONFLICT_HANDLING_UNSUPPORTED.value not in _codes(default)
    payload = _strategy_payload()
    payload["conflict_position_handling"] = {
        "exit_on_opposite_signal": False,
        "opposite_direction_hedge": "close_existing",
        "same_direction_stacking": "replace_existing",
    }
    closing = evaluate_readiness(
        [_strategy_item(payload=payload)], allocation_enabled=False, allocation_issues=[]
    )
    assert Code.STRATEGY_CONFLICT_HANDLING_UNSUPPORTED.value not in _codes(closing)


def test_strategy_default_costs_warns_not_blocks() -> None:
    payload = _strategy_payload()
    payload["data"]["costs"] = {"slippage_value": "0.1"}  # commission + spread unset
    result = evaluate_readiness(
        [_strategy_item(payload=payload)], allocation_enabled=False, allocation_issues=[]
    )
    assert Code.EXECUTION_ASSUMPTIONS_DEFAULT.value in _codes(result)
    assert result.state == ReadinessState.READY_WITH_WARNINGS


def test_invalid_strategy_payload_blocks() -> None:
    result = evaluate_readiness(
        [_strategy_item(payload={"display_name": "broken"})],
        allocation_enabled=False,
        allocation_issues=[],
    )
    assert Code.STRATEGY_CONFIG_INVALID.value in _codes(result)


# --------------------------------------------------------------------------- #
# External working objects (RC-07 / RC-08 / TL-09 / TL-11 / OHLCV)             #
# --------------------------------------------------------------------------- #


def test_rc07_external_without_import_revision_blocks() -> None:
    item = _trade_log_item(
        external=ExternalImportState(found=False, succeeded=False, accepted_count=0)
    )
    result = evaluate_readiness([item], allocation_enabled=False, allocation_issues=[])
    assert Code.EXTERNAL_IMPORT_UNRESOLVED.value in _codes(result)
    assert result.state == ReadinessState.NOT_READY


def test_valid_trade_log_is_ready() -> None:
    result = evaluate_readiness([_trade_log_item()], allocation_enabled=False, allocation_issues=[])
    assert result.state == ReadinessState.READY


def test_tl09_mixed_symbol_scope_blocks() -> None:
    item = _trade_log_item(
        external=ExternalImportState(
            found=True,
            succeeded=True,
            accepted_count=3,
            instrument_id="BTCUSDT",
            skipped_reason_codes=frozenset({"INSTRUMENT_MISMATCH"}),
        )
    )
    result = evaluate_readiness([item], allocation_enabled=False, allocation_issues=[])
    assert Code.MIXED_SYMBOL_SCOPE.value in _codes(result)
    assert result.state == ReadinessState.NOT_READY


def test_rc08_chronology_skips_warn() -> None:
    item = _trade_log_item(
        external=ExternalImportState(
            found=True,
            succeeded=True,
            accepted_count=3,
            instrument_id="BTCUSDT",
            skipped_reason_codes=frozenset({"EXIT_BEFORE_ENTRY"}),
        )
    )
    result = evaluate_readiness([item], allocation_enabled=False, allocation_issues=[])
    assert Code.TRADE_LOG_CHRONOLOGY_INVALID.value in _codes(result)
    assert result.state == ReadinessState.READY_WITH_WARNINGS


def test_ohlcv_fallback_without_market_data_ref_blocks() -> None:
    payload = _trade_log_payload()
    payload["price_policy"] = {"source": "ohlcv_close_if_needed"}
    result = evaluate_readiness(
        [_trade_log_item(payload=payload)], allocation_enabled=False, allocation_issues=[]
    )
    assert Code.OHLCV_FALLBACK_MARKET_DATA_MISSING.value in _codes(result)


def test_ohlcv_fallback_with_market_data_ref_ok() -> None:
    payload = _trade_log_payload()
    payload["price_policy"] = {
        "source": "ohlcv_close_if_needed",
        "approved_market_data_revision_ref": "md_rev_9",
    }
    result = evaluate_readiness(
        [_trade_log_item(payload=payload)], allocation_enabled=False, allocation_issues=[]
    )
    assert Code.OHLCV_FALLBACK_MARKET_DATA_MISSING.value not in _codes(result)


def test_tl11_independent_capital_required_when_allocation_off() -> None:
    payload = _trade_log_payload()
    payload["capital"] = {}  # no independent_initial_capital
    result = evaluate_readiness(
        [_trade_log_item(payload=payload)], allocation_enabled=False, allocation_issues=[]
    )
    assert Code.INDEPENDENT_CAPITAL_REQUIRED.value in _codes(result)


def test_tl11_independent_capital_not_required_when_allocation_on() -> None:
    payload = _trade_log_payload()
    payload["capital"] = {}
    result = evaluate_readiness(
        [_trade_log_item(payload=payload)], allocation_enabled=True, allocation_issues=[]
    )
    assert Code.INDEPENDENT_CAPITAL_REQUIRED.value not in _codes(result)


# --------------------------------------------------------------------------- #
# Allocation mapping (RC-03 / RC-04)                                           #
# --------------------------------------------------------------------------- #


def test_rc04_allocation_blocker_maps_and_not_ready() -> None:
    alloc = [
        AllocationIssue(
            AllocationIssueCode.TOTAL_ALLOCATION_EXCEEDS_100,
            AllocationIssueSeverity.BLOCKER,
            "Total allocation is 102%; it cannot exceed 100%.",
            field="entries",
        )
    ]
    result = evaluate_readiness(
        [_strategy_item()], allocation_enabled=True, allocation_issues=alloc
    )
    assert Code.ALLOCATION_TOTAL_EXCEEDS_100.value in _codes(result)
    assert result.state == ReadinessState.NOT_READY


def test_rc03_allocation_unallocated_cash_warns() -> None:
    alloc = [
        AllocationIssue(
            AllocationIssueCode.TOTAL_ALLOCATION_UNDER_100,
            AllocationIssueSeverity.WARNING,
            "80% active share defined; the remaining 20% stays unallocated.",
            field="entries",
        )
    ]
    result = evaluate_readiness(
        [_strategy_item()], allocation_enabled=True, allocation_issues=alloc
    )
    assert Code.ALLOCATION_UNALLOCATED_CASH.value in _codes(result)
    assert result.state == ReadinessState.READY_WITH_WARNINGS


# --------------------------------------------------------------------------- #
# Stale compare (RC-09 / RC-10)                                                #
# --------------------------------------------------------------------------- #


def test_is_stale_detects_fingerprint_change() -> None:
    assert is_stale("hash_a", "hash_b") is True
    assert is_stale("hash_a", "hash_a") is False


# --------------------------------------------------------------------------- #
# Regression (review Finding 1): exit logic via indicator blocks, no stop      #
# --------------------------------------------------------------------------- #


def _exit_indicator_block(enabled: bool = True) -> dict[str, Any]:
    return {
        "block_id": "xb_1",
        "display_order": 0,
        "enabled": enabled,
        "package_ref": {
            "package_root_id": "pkg_root_x",
            "package_revision_id": "pkg_rev_x",
            "package_content_hash": "c" * 64,
        },
        "trigger_source": "indicator_native_trigger",
        "requirement": "required",
    }


def test_exit_via_enabled_indicator_block_is_ready_without_stop() -> None:
    # A valid exit expressed as an enabled exit indicator block (no signal_block,
    # no protection stop) must NOT be flagged STRATEGY_NO_EXIT_OR_STOP.
    payload = _strategy_payload(
        position_exit_logic={"indicator_blocks": [_exit_indicator_block(enabled=True)]},
        protection_stop_logic=None,
    )
    result = evaluate_readiness(
        [_strategy_item(payload=payload)], allocation_enabled=False, allocation_issues=[]
    )
    assert Code.STRATEGY_NO_EXIT_OR_STOP.value not in _codes(result)
    assert result.state == ReadinessState.READY


def test_disabled_exit_block_without_stop_still_blocks() -> None:
    # A DISABLED exit indicator block is not an active engine rule (doc 14 §5.1);
    # with no active stop it must still block.
    payload = _strategy_payload(
        position_exit_logic={"indicator_blocks": [_exit_indicator_block(enabled=False)]},
        protection_stop_logic=None,
    )
    result = evaluate_readiness(
        [_strategy_item(payload=payload)], allocation_enabled=False, allocation_issues=[]
    )
    assert Code.STRATEGY_NO_EXIT_OR_STOP.value in _codes(result)


# --------------------------------------------------------------------------- #
# GAP-16: cross-item instrument consistency (Master §8.1)                      #
# --------------------------------------------------------------------------- #


def test_external_import_instrument_mismatch_blocks() -> None:
    # An external import resolved to a DIFFERENT canonical instrument than the
    # strategy (spot import under a perpetual strategy) is a Ready blocker.
    mismatched = ExternalImportState(
        found=True,
        succeeded=True,
        accepted_count=5,
        instrument_id="binance:btcusdt:perpetual",
    )
    result = evaluate_readiness(
        [_strategy_item(), _trade_log_item(external=mismatched)],
        allocation_enabled=False,
        allocation_issues=[],
    )
    assert Code.INSTRUMENT_SCOPE_MISMATCH.value in _codes(result)
    assert result.state == ReadinessState.NOT_READY


def test_external_import_matching_instrument_has_no_mismatch() -> None:
    # The strategy and the import share the same canonical instrument -> no mismatch.
    result = evaluate_readiness(
        [_strategy_item(), _trade_log_item()],
        allocation_enabled=False,
        allocation_issues=[],
    )
    assert Code.INSTRUMENT_SCOPE_MISMATCH.value not in _codes(result)


def test_f06_injected_strategy_indicator_issue_blocks() -> None:
    # F-06: the command resolves the pinned indicator plan (a DB read) and injects a
    # blocker for an unresolved required dependency; the validator aggregates it 1:1.
    unresolved = ReadinessIssue(
        code=Code.STRATEGY_INDICATOR_UNRESOLVED,
        severity=ReadinessSeverity.BLOCKER,
        scope=ReadinessScope.STRATEGY,
        message="A pinned indicator package does not resolve to a computable signal.",
        scope_id="item_s1",
    )
    result = evaluate_readiness(
        [_strategy_item()],
        allocation_enabled=False,
        allocation_issues=[],
        strategy_indicator_issues=[unresolved],
    )
    assert Code.STRATEGY_INDICATOR_UNRESOLVED.value in _codes(result)
    assert result.state == ReadinessState.NOT_READY
