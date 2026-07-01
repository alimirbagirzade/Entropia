"""Trade Log config validation + hashing (Stage 3d, doc 05 §5.2, §10.2, §12).

``validate_trade_log_config`` parses the §10.2 payload and applies the cross-field
policy rules a single-field type check cannot express (event-model / OHLCV /
price-source conflicts). A non-empty issue list means the payload must NOT be
persisted as an immutable Trade Log revision.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from pydantic import ValidationError as PydanticValidationError

from entropia.domain.trade_log.config import TradeLogConfig
from entropia.domain.trade_log.enums import (
    ContentProfile,
    OhlcvUseMode,
    PriceSourceMode,
    ResolutionKind,
)

# Machine-coded issue codes (mapped to typed API errors in the command layer).
CODE_STRUCTURAL = "TRADE_LOG_VALIDATION_ERROR"
CODE_EVENT_MODEL_CONFLICT = "EVENT_MODEL_POLICY_CONFLICT"
CODE_PRICE_CONTEXT_CONFLICT = "PRICE_CONTEXT_CONFLICT"

_OHLCV_FALLBACK_SOURCES = (
    PriceSourceMode.OHLCV_CLOSE_IF_NEEDED,
    PriceSourceMode.OHLCV_INTRABAR_IF_AVAILABLE,
)


def validate_trade_log_config(
    payload: dict[str, Any],
) -> tuple[TradeLogConfig | None, list[dict[str, Any]]]:
    """Parse + structurally + cross-field validate a §10.2 payload.

    Returns ``(config, issues)``. ``config`` is ``None`` when structural (Pydantic)
    validation fails, and ``issues`` then carries the structural errors. Otherwise
    ``issues`` holds the cross-field blockers found on the structurally-valid config
    (empty list => safe to persist).
    """
    try:
        config = TradeLogConfig(**payload)
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


def validate_semantics(config: TradeLogConfig) -> list[dict[str, Any]]:
    """Cross-field policy validation over a structurally-valid config (doc 05 §5.2)."""
    issues: list[dict[str, Any]] = []
    issues.extend(_event_model_issues(config))
    issues.extend(_price_context_issues(config))
    return issues


def _event_model_issues(config: TradeLogConfig) -> list[dict[str, Any]]:
    model = config.time_model
    if model.resolution_kind == ResolutionKind.EVENT_BASED and model.base_timeframe:
        return [
            {
                "field": "time_model.base_timeframe",
                "code": CODE_EVENT_MODEL_CONFLICT,
                "message": "Event-based trade records carry no base timeframe.",
            }
        ]
    if model.resolution_kind == ResolutionKind.BAR_TIMEFRAME and not model.base_timeframe:
        return [
            {
                "field": "time_model.base_timeframe",
                "code": CODE_EVENT_MODEL_CONFLICT,
                "message": "A bar-aligned trade log requires a base timeframe.",
            }
        ]
    return []


def _price_context_issues(config: TradeLogConfig) -> list[dict[str, Any]]:
    price = config.price_policy.source
    use_mode = config.ohlcv_policy.use_mode
    profile = config.data_quality.content_profile
    issues: list[dict[str, Any]] = []
    # TL-10: an OHLCV price fallback cannot be combined with "Ignore OHLCV context".
    if price in _OHLCV_FALLBACK_SOURCES and use_mode == OhlcvUseMode.IGNORE:
        issues.append(
            {
                "field": "ohlcv_policy.use_mode",
                "code": CODE_PRICE_CONTEXT_CONFLICT,
                "message": "OHLCV fallback cannot be used while OHLCV Use is set to Ignore.",
            }
        )
    # Entry/Exit-only ledger supplies no OHLCV to use for price context/validation.
    if (
        profile == ContentProfile.ENTRY_EXIT_RECORDS_ONLY
        and use_mode == OhlcvUseMode.USE_FOR_PRICE_CONTEXT_AND_VALIDATION
    ):
        issues.append(
            {
                "field": "ohlcv_policy.use_mode",
                "code": CODE_PRICE_CONTEXT_CONFLICT,
                "message": "Entry/exit-only data quality supplies no source OHLCV to use.",
            }
        )
    return issues


def config_to_dict(config: TradeLogConfig) -> dict[str, Any]:
    """Serialize the config to a JSON-safe dict (Decimals -> strings)."""
    return config.model_dump(mode="json")


def compute_config_hash(config: TradeLogConfig) -> str:
    """Deterministic SHA-256 over the canonical config serialization."""
    canonical = json.dumps(config.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
