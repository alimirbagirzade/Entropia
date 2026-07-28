"""K-08 — the Trading Signal OHLCV price/context dependency (doc 04 §5, §5.2, §11).

Doc 04 §5 Price Source row: "Fallback options require compatible approved Market Data
at Ready Check." Before K-08 the Ready Check validator applied that rule ONLY to a
Trade Log (the check was guarded by ``is_trade_log``) and the Trading Signal
``PricePolicy`` had no ``approved_market_data_revision_ref`` field at all — so a signal
selecting ``ohlcv_close_if_needed`` / ``ohlcv_intrabar_if_available`` could reach Ready
PASS with nothing behind the fallback.

These tests pin the three facts the fix has to keep true forever:

1. an OHLCV fallback without an approved Market Data pin BLOCKS a Trading Signal
   (``MARKET_DATA_DEPENDENCY_BLOCKED``, the doc 04 §11 Dependency-row code),
2. the same config WITH a pin passes,
3. the Trade Log twin is untouched — it still emits its own doc 05 §5.3 code
   ``OHLCV_FALLBACK_MARKET_DATA_MISSING`` and never the Trading Signal one.
"""

from __future__ import annotations

from typing import Any

from entropia.domain.mainboard.enums import MainboardItemKind
from entropia.domain.market_data.enums import MarketDataType, supports_intrabar_execution
from entropia.domain.readiness.enums import ReadinessIssueCode as Code
from entropia.domain.readiness.enums import ReadinessState
from entropia.domain.readiness.issues import ExternalImportState, ReadinessItemInput
from entropia.domain.readiness.validators import evaluate_readiness
from entropia.domain.trading_signal.config import TradingSignalConfig

_MARKET_REF = "mdrev_synthetic_1"


def _signal_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "kind": "trading_signal",
        "identity": {"display_name": "Copy Trading Signal Source A"},
        "source": {"provider_name": "Provider X", "source_kind": "file"},
        "instrument_scope": {"instrument_id": "BTCUSDT", "display_symbol": "BTCUSDT"},
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


def _item(kind: MainboardItemKind, payload: dict[str, Any]) -> ReadinessItemInput:
    return ReadinessItemInput(
        item_id="item_x1",
        kind=kind,
        root_id="root_x1",
        revision_id="rev_x1",
        available=True,
        payload=payload,
        external=ExternalImportState(
            found=True, succeeded=True, accepted_count=5, instrument_id="BTCUSDT"
        ),
    )


def _signal_codes(**price_policy: Any) -> set[str]:
    payload = _signal_payload(price_policy=price_policy)
    result = evaluate_readiness(
        [_item(MainboardItemKind.TRADING_SIGNAL, payload)],
        allocation_enabled=False,
        allocation_issues=[],
    )
    return {str(i.code) for i in result.issues}


# --------------------------------------------------------------------------- #
# 1. The field itself — the TS schema now MIRRORS the Trade Log one            #
# --------------------------------------------------------------------------- #


def test_ts_price_policy_accepts_approved_market_data_ref() -> None:
    config = TradingSignalConfig(
        **_signal_payload(
            price_policy={
                "source": "ohlcv_close_if_needed",
                "fallback": None,
                "approved_market_data_revision_ref": _MARKET_REF,
            }
        )
    )
    assert config.price_policy.approved_market_data_revision_ref == _MARKET_REF


def test_ts_price_policy_ref_defaults_to_none_for_legacy_payloads() -> None:
    """Every already-persisted revision omits the key; ``extra='forbid'`` must allow it."""
    config = TradingSignalConfig(**_signal_payload())
    assert config.price_policy.approved_market_data_revision_ref is None


# --------------------------------------------------------------------------- #
# 2. The twin blocker — an ohlcv_fallback with no approved Market Data         #
# --------------------------------------------------------------------------- #


def test_ohlcv_fallback_close_without_market_data_blocks_trading_signal() -> None:
    codes = _signal_codes(source="ohlcv_close_if_needed", fallback=None)
    assert Code.MARKET_DATA_DEPENDENCY_BLOCKED.value in codes


def test_ohlcv_fallback_intrabar_without_market_data_blocks_trading_signal() -> None:
    codes = _signal_codes(source="ohlcv_intrabar_if_available", fallback=None)
    assert Code.MARKET_DATA_DEPENDENCY_BLOCKED.value in codes


def test_ts_price_policy_ohlcv_fallback_with_approved_ref_is_ready() -> None:
    payload = _signal_payload(
        price_policy={
            "source": "ohlcv_close_if_needed",
            "fallback": None,
            "approved_market_data_revision_ref": _MARKET_REF,
        }
    )
    result = evaluate_readiness(
        [_item(MainboardItemKind.TRADING_SIGNAL, payload)],
        allocation_enabled=False,
        allocation_issues=[],
    )
    assert Code.MARKET_DATA_DEPENDENCY_BLOCKED.value not in {str(i.code) for i in result.issues}
    assert result.state == ReadinessState.READY


def test_ts_price_policy_suggested_price_needs_no_market_data() -> None:
    """The non-fallback source is unaffected: no pin demanded, no blocker raised."""
    codes = _signal_codes(source="suggested_signal_price", fallback=None)
    assert Code.MARKET_DATA_DEPENDENCY_BLOCKED.value not in codes


# --------------------------------------------------------------------------- #
# 3. OHLCV_CONTEXT_REQUIRED (doc 04 §5.2 "OHLCV Use" row)                      #
# --------------------------------------------------------------------------- #


def test_market_context_mode_requires_a_market_data_pin() -> None:
    """``signal_events_with_market_context`` supplies NO source OHLCV — the context
    the user asked to validate against can only come from an approved pin."""
    payload = _signal_payload(
        data_quality={"mode": "signal_events_with_market_context"},
        ohlcv_policy={"use_mode": "use_for_price_context_and_validation"},
    )
    result = evaluate_readiness(
        [_item(MainboardItemKind.TRADING_SIGNAL, payload)],
        allocation_enabled=False,
        allocation_issues=[],
    )
    assert Code.OHLCV_CONTEXT_REQUIRED.value in {str(i.code) for i in result.issues}


def test_market_context_mode_with_pin_is_satisfied() -> None:
    payload = _signal_payload(
        data_quality={"mode": "signal_events_with_market_context"},
        ohlcv_policy={"use_mode": "use_for_price_context_and_validation"},
        price_policy={
            "source": "suggested_signal_price",
            "fallback": None,
            "approved_market_data_revision_ref": _MARKET_REF,
        },
    )
    result = evaluate_readiness(
        [_item(MainboardItemKind.TRADING_SIGNAL, payload)],
        allocation_enabled=False,
        allocation_issues=[],
    )
    assert Code.OHLCV_CONTEXT_REQUIRED.value not in {str(i.code) for i in result.issues}


def test_source_ohlcv_mode_supplies_its_own_context() -> None:
    """The source file itself carries the OHLCV — no market pin is demanded."""
    payload = _signal_payload(
        data_quality={"mode": "signal_events_with_source_ohlcv"},
        ohlcv_policy={"use_mode": "use_for_price_context_and_validation"},
    )
    result = evaluate_readiness(
        [_item(MainboardItemKind.TRADING_SIGNAL, payload)],
        allocation_enabled=False,
        allocation_issues=[],
    )
    assert Code.OHLCV_CONTEXT_REQUIRED.value not in {str(i.code) for i in result.issues}


# --------------------------------------------------------------------------- #
# 4. Trade Log REGRESSION — the twin keeps its own code and behaviour          #
# --------------------------------------------------------------------------- #


def _trade_log_codes(price_policy: dict[str, Any]) -> set[str]:
    payload = _trade_log_payload(price_policy=price_policy)
    result = evaluate_readiness(
        [_item(MainboardItemKind.TRADE_LOG, payload)],
        allocation_enabled=False,
        allocation_issues=[],
    )
    return {str(i.code) for i in result.issues}


def test_trade_log_ohlcv_fallback_still_uses_its_own_code() -> None:
    codes = _trade_log_codes({"source": "ohlcv_close_if_needed"})
    assert Code.OHLCV_FALLBACK_MARKET_DATA_MISSING.value in codes
    # The doc 04 vocabulary must never leak onto the doc 05 page (K-07 adjudication).
    assert Code.MARKET_DATA_DEPENDENCY_BLOCKED.value not in codes


def test_trade_log_ohlcv_fallback_with_ref_still_passes() -> None:
    codes = _trade_log_codes(
        {
            "source": "ohlcv_close_if_needed",
            "approved_market_data_revision_ref": _MARKET_REF,
        }
    )
    assert Code.OHLCV_FALLBACK_MARKET_DATA_MISSING.value not in codes


def test_trade_log_entry_exit_price_needs_no_market_data() -> None:
    codes = _trade_log_codes({"source": "trade_log_entry_exit_price"})
    assert Code.OHLCV_FALLBACK_MARKET_DATA_MISSING.value not in codes


# --------------------------------------------------------------------------- #
# 5. The intrabar-capability predicate (doc 04 §5.2 intrabar row)              #
# --------------------------------------------------------------------------- #


def test_only_tick_trades_supports_intrabar_execution() -> None:
    assert supports_intrabar_execution(MarketDataType.TICK_TRADES) is True
    assert supports_intrabar_execution(MarketDataType.OHLCV) is False
    assert supports_intrabar_execution(MarketDataType.SPREAD_EXECUTION) is False
    assert supports_intrabar_execution("") is False  # fail closed on an unknown shape
