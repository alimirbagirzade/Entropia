"""Unit tests for the Trade Log §10.2 config + compiler (doc 05 §5, §5.2, §10.2)."""

from __future__ import annotations

from typing import Any

from entropia.domain.trade_log.compiler import (
    CODE_EVENT_MODEL_CONFLICT,
    CODE_PRICE_CONTEXT_CONFLICT,
    compute_config_hash,
    validate_trade_log_config,
)


def _valid_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "kind": "trade_log",
        "identity": {"display_name": "Binance BTCUSDT trade history Q1"},
        "source": {"provider_name": "Binance Futures export", "source_kind": "file"},
        "instrument_scope": {"instrument_id": "inst_btcusdt", "display_symbol": "BTCUSDT"},
        "time_model": {
            "resolution_kind": "event_based",
            "base_timeframe": None,
            "source_timezone": "UTC",
            "normalization_timezone": "UTC",
        },
        "classification": {"rationale_family_id": None},
        "data_quality": {"content_profile": "entry_exit_records_only"},
        "price_policy": {
            "source": "trade_log_entry_exit_price",
            "approved_market_data_revision_ref": None,
        },
        "ohlcv_policy": {"use_mode": "use_if_supplied_and_needed"},
        "capital": {"independent_initial_capital": "10000", "currency": "USDT"},
        "import_binding": {
            "source_asset_id": "srcasset_x",
            "record_batch_revision_id": "tlbatch_x",
            "mapping_revision_id": None,
        },
    }
    payload.update(overrides)
    return payload


def test_valid_config_parses_with_no_issues() -> None:
    config, issues = validate_trade_log_config(_valid_payload())
    assert config is not None
    assert issues == []


def test_blank_provider_is_a_structural_error() -> None:
    payload = _valid_payload(source={"provider_name": "   ", "source_kind": "file"})
    config, issues = validate_trade_log_config(payload)
    assert config is None
    assert any(str(i["field"]).startswith("source.provider_name") for i in issues)


def test_event_based_with_base_timeframe_conflicts() -> None:
    payload = _valid_payload(
        time_model={
            "resolution_kind": "event_based",
            "base_timeframe": "15m",
            "source_timezone": "UTC",
        }
    )
    config, issues = validate_trade_log_config(payload)
    assert config is not None
    assert CODE_EVENT_MODEL_CONFLICT in {i["code"] for i in issues}


def test_bar_timeframe_without_base_timeframe_conflicts() -> None:
    payload = _valid_payload(
        time_model={
            "resolution_kind": "bar_timeframe",
            "base_timeframe": None,
            "source_timezone": "UTC",
        }
    )
    config, issues = validate_trade_log_config(payload)
    assert config is not None
    assert CODE_EVENT_MODEL_CONFLICT in {i["code"] for i in issues}


def test_ohlcv_fallback_with_ignore_conflicts() -> None:
    payload = _valid_payload(
        price_policy={
            "source": "ohlcv_intrabar_if_available",
            "approved_market_data_revision_ref": None,
        },
        ohlcv_policy={"use_mode": "ignore"},
    )
    config, issues = validate_trade_log_config(payload)
    assert config is not None
    assert CODE_PRICE_CONTEXT_CONFLICT in {i["code"] for i in issues}


def test_entry_exit_only_cannot_use_source_ohlcv_context() -> None:
    payload = _valid_payload(
        data_quality={"content_profile": "entry_exit_records_only"},
        ohlcv_policy={"use_mode": "use_for_price_context_and_validation"},
    )
    config, issues = validate_trade_log_config(payload)
    assert config is not None
    assert CODE_PRICE_CONTEXT_CONFLICT in {i["code"] for i in issues}


def test_negative_capital_is_rejected() -> None:
    payload = _valid_payload(capital={"independent_initial_capital": "-5", "currency": "USDT"})
    config, issues = validate_trade_log_config(payload)
    assert config is None
    assert issues


def test_config_hash_is_deterministic_and_content_sensitive() -> None:
    config_a, _ = validate_trade_log_config(_valid_payload())
    config_b, _ = validate_trade_log_config(_valid_payload())
    assert config_a is not None and config_b is not None
    h1 = compute_config_hash(config_a)
    assert h1 == compute_config_hash(config_b)
    assert len(h1) == 64

    changed = _valid_payload(identity={"display_name": "Another Name"})
    config_c, _ = validate_trade_log_config(changed)
    assert config_c is not None
    assert compute_config_hash(config_c) != h1


def test_unknown_key_is_rejected() -> None:
    payload = _valid_payload()
    payload["totally_unexpected"] = True
    config, issues = validate_trade_log_config(payload)
    assert config is None
    assert issues


def test_kind_must_be_trade_log() -> None:
    payload = _valid_payload(kind="trading_signal")
    config, issues = validate_trade_log_config(payload)
    assert config is None
    assert issues
