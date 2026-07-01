"""Unit tests for the Trading Signal §9.2 config + compiler (doc 04 §5, §5.2, §9.2)."""

from __future__ import annotations

from typing import Any

from entropia.domain.trading_signal.compiler import (
    CODE_EVENT_MODEL_CONFLICT,
    CODE_OHLCV_POLICY_CONFLICT,
    compute_config_hash,
    validate_trading_signal_config,
)


def _valid_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "kind": "trading_signal",
        "identity": {"display_name": "Copy Trading Signal Source A"},
        "source": {"provider_name": "Provider X", "source_kind": "file"},
        "instrument_scope": {"instrument_id": "inst_btcusdt", "display_symbol": "BTCUSDT"},
        "event_model": {"resolution_kind": "event_based", "base_timeframe": None},
        "classification": {"rationale_family_id": None},
        "data_quality": {"mode": "signal_events_only"},
        "time_policy": {
            "source_timezone": "UTC",
            "normalization_timezone": "UTC",
            "availability_rule": "row_available_time",
        },
        "price_policy": {"source": "suggested_signal_price", "fallback": None},
        "ohlcv_policy": {"use_mode": "use_if_supplied_and_needed"},
        "capital": {"independent_initial_capital": "10000"},
        "import_binding": {
            "source_asset_id": "srcasset_x",
            "normalized_event_revision_id": "normsig_x",
            "mapping_revision_id": None,
        },
    }
    payload.update(overrides)
    return payload


def test_valid_config_parses_with_no_issues() -> None:
    config, issues = validate_trading_signal_config(_valid_payload())
    assert config is not None
    assert issues == []


def test_blank_provider_is_a_structural_error() -> None:
    payload = _valid_payload(source={"provider_name": "   ", "source_kind": "file"})
    config, issues = validate_trading_signal_config(payload)
    assert config is None
    assert any(str(i["field"]).startswith("source.provider_name") for i in issues)


def test_event_based_with_base_timeframe_conflicts() -> None:
    payload = _valid_payload(
        event_model={"resolution_kind": "event_based", "base_timeframe": "15m"}
    )
    config, issues = validate_trading_signal_config(payload)
    assert config is not None
    assert CODE_EVENT_MODEL_CONFLICT in {i["code"] for i in issues}


def test_bar_timeframe_without_base_timeframe_conflicts() -> None:
    payload = _valid_payload(
        event_model={"resolution_kind": "bar_timeframe", "base_timeframe": None}
    )
    config, issues = validate_trading_signal_config(payload)
    assert config is not None
    assert CODE_EVENT_MODEL_CONFLICT in {i["code"] for i in issues}


def test_ignore_ohlcv_with_intrabar_price_conflicts() -> None:
    payload = _valid_payload(
        price_policy={"source": "ohlcv_intrabar_if_available", "fallback": None},
        ohlcv_policy={"use_mode": "ignore"},
    )
    config, issues = validate_trading_signal_config(payload)
    assert config is not None
    assert CODE_OHLCV_POLICY_CONFLICT in {i["code"] for i in issues}


def test_signal_events_only_cannot_use_source_ohlcv_context() -> None:
    payload = _valid_payload(
        data_quality={"mode": "signal_events_only"},
        ohlcv_policy={"use_mode": "use_for_price_context_and_validation"},
    )
    config, issues = validate_trading_signal_config(payload)
    assert config is not None
    assert CODE_OHLCV_POLICY_CONFLICT in {i["code"] for i in issues}


def test_config_hash_is_deterministic_and_content_sensitive() -> None:
    config_a, _ = validate_trading_signal_config(_valid_payload())
    config_b, _ = validate_trading_signal_config(_valid_payload())
    assert config_a is not None and config_b is not None
    h1 = compute_config_hash(config_a)
    assert h1 == compute_config_hash(config_b)
    assert len(h1) == 64

    changed = _valid_payload(identity={"display_name": "Another Name"})
    config_c, _ = validate_trading_signal_config(changed)
    assert config_c is not None
    assert compute_config_hash(config_c) != h1


def test_unknown_key_is_rejected() -> None:
    payload = _valid_payload()
    payload["totally_unexpected"] = True
    config, issues = validate_trading_signal_config(payload)
    assert config is None
    assert issues
