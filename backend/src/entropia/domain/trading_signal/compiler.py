"""Trading Signal config validation + hashing (Stage 3c, doc 04 §5.2, §9.2, §11).

``validate_trading_signal_config`` parses the §9.2 payload and applies the
cross-field policy rules a single-field type check cannot express (event-model /
OHLCV / price-source conflicts). A non-empty issue list means the payload must NOT
be persisted as an immutable Trading Signal revision.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from pydantic import ValidationError as PydanticValidationError

from entropia.domain.trading_signal.config import TradingSignalConfig
from entropia.domain.trading_signal.enums import (
    DataQualityMode,
    OhlcvUseMode,
    PriceSourceMode,
    ResolutionKind,
)

# Machine-coded issue codes (mapped to typed API errors in the command layer).
CODE_STRUCTURAL = "TRADING_SIGNAL_VALIDATION_ERROR"
CODE_EVENT_MODEL_CONFLICT = "EVENT_MODEL_POLICY_CONFLICT"
CODE_OHLCV_POLICY_CONFLICT = "OHLCV_POLICY_CONFLICT"


def validate_trading_signal_config(
    payload: dict[str, Any],
) -> tuple[TradingSignalConfig | None, list[dict[str, Any]]]:
    """Parse + structurally + cross-field validate a §9.2 payload.

    Returns ``(config, issues)``. ``config`` is ``None`` when structural (Pydantic)
    validation fails, and ``issues`` then carries the structural errors. Otherwise
    ``issues`` holds the cross-field blockers found on the structurally-valid config
    (empty list => safe to persist).
    """
    try:
        config = TradingSignalConfig(**payload)
    except PydanticValidationError as exc:
        errors: list[dict[str, Any]] = []
        for error in exc.errors():
            loc = error.get("loc", ("unknown",))
            errors.append(
                {
                    "field": ".".join(str(x) for x in loc),
                    "code": CODE_STRUCTURAL,
                    "message": error.get("msg", "Invalid value"),
                }
            )
        return None, errors

    return config, validate_semantics(config)


def validate_semantics(config: TradingSignalConfig) -> list[dict[str, Any]]:
    """Cross-field policy validation over a structurally-valid config (doc 04 §5.2)."""
    issues: list[dict[str, Any]] = []
    issues.extend(_event_model_issues(config))
    issues.extend(_ohlcv_policy_issues(config))
    return issues


def _event_model_issues(config: TradingSignalConfig) -> list[dict[str, Any]]:
    model = config.event_model
    if model.resolution_kind == ResolutionKind.EVENT_BASED and model.base_timeframe:
        return [
            {
                "field": "event_model.base_timeframe",
                "code": CODE_EVENT_MODEL_CONFLICT,
                "message": "Event-based signals carry no base timeframe.",
            }
        ]
    if model.resolution_kind == ResolutionKind.BAR_TIMEFRAME and not model.base_timeframe:
        return [
            {
                "field": "event_model.base_timeframe",
                "code": CODE_EVENT_MODEL_CONFLICT,
                "message": "A bar-aligned signal requires a base timeframe.",
            }
        ]
    return []


def _ohlcv_policy_issues(config: TradingSignalConfig) -> list[dict[str, Any]]:
    price = config.price_policy.source
    use_mode = config.ohlcv_policy.use_mode
    mode = config.data_quality.mode
    issues: list[dict[str, Any]] = []
    if price == PriceSourceMode.OHLCV_INTRABAR_IF_AVAILABLE and use_mode == OhlcvUseMode.IGNORE:
        issues.append(
            {
                "field": "ohlcv_policy.use_mode",
                "code": CODE_OHLCV_POLICY_CONFLICT,
                "message": "Intrabar price policy cannot ignore OHLCV context.",
            }
        )
    if (
        mode == DataQualityMode.SIGNAL_EVENTS_ONLY
        and use_mode == OhlcvUseMode.USE_FOR_PRICE_CONTEXT_AND_VALIDATION
    ):
        issues.append(
            {
                "field": "ohlcv_policy.use_mode",
                "code": CODE_OHLCV_POLICY_CONFLICT,
                "message": "Signal-events-only data quality supplies no source OHLCV to use.",
            }
        )
    return issues


def config_to_dict(config: TradingSignalConfig) -> dict[str, Any]:
    """Serialize the config to a JSON-safe dict (Decimals -> strings)."""
    return config.model_dump(mode="json")


def compute_config_hash(config: TradingSignalConfig) -> str:
    """Deterministic SHA-256 over the canonical config serialization."""
    canonical = json.dumps(config.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
