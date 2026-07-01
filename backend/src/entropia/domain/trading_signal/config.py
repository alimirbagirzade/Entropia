"""Typed Trading Signal revision payload (Stage 3c, doc 04 §9.2).

The §9.2 "Revision Payload — Implementation Decision" JSON is modeled here as a
Pydantic ``TradingSignalConfig``. It is the exact shape stored in the native
``work_object_revision.payload`` (a Trading Signal IS a work object,
``object_kind=trading_signal`` — no mirror revision). Field names are the typed
API/OpenAPI contract candidates (doc 04 §16.1 ID-04-06).

Structural (single-field) rules live here; cross-field business rules
(event-model / OHLCV / price policy conflicts) live in ``compiler.py`` so they can
surface as machine-coded issues.
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, field_validator

from entropia.domain.trading_signal.enums import (
    DataQualityMode,
    OhlcvUseMode,
    PriceSourceMode,
    ResolutionKind,
    SourceKind,
)

_NAME_MAX = 160
_PROVIDER_MAX = 200
_SYMBOL_MAX = 64
_NORMALIZATION_TZ = "UTC"


class _Strict(BaseModel):
    """Base: forbid unknown keys so a mixed-kind / legacy payload is rejected."""

    model_config = ConfigDict(extra="forbid")


class SignalIdentity(_Strict):
    display_name: str

    @field_validator("display_name")
    @classmethod
    def _name_trimmed(cls, value: str) -> str:
        trimmed = (value or "").strip()
        if not (1 <= len(trimmed) <= _NAME_MAX):
            raise ValueError(f"display_name must be 1..{_NAME_MAX} characters.")
        return trimmed


class SignalSource(_Strict):
    provider_name: str
    source_kind: SourceKind = SourceKind.FILE

    @field_validator("provider_name")
    @classmethod
    def _provider_trimmed(cls, value: str) -> str:
        trimmed = (value or "").strip()
        if not (1 <= len(trimmed) <= _PROVIDER_MAX):
            raise ValueError(f"provider_name must be 1..{_PROVIDER_MAX} characters.")
        return trimmed


class InstrumentScope(_Strict):
    instrument_id: str
    display_symbol: str

    @field_validator("instrument_id", "display_symbol")
    @classmethod
    def _non_empty(cls, value: str) -> str:
        trimmed = (value or "").strip()
        if not (1 <= len(trimmed) <= _SYMBOL_MAX):
            raise ValueError("instrument scope value must be 1..64 characters.")
        return trimmed


class EventModel(_Strict):
    resolution_kind: ResolutionKind
    base_timeframe: str | None = None


class SignalClassification(_Strict):
    rationale_family_id: str | None = None


class DataQuality(_Strict):
    mode: DataQualityMode


class TimePolicy(_Strict):
    source_timezone: str
    normalization_timezone: str = _NORMALIZATION_TZ
    availability_rule: str = "row_available_time"

    @field_validator("source_timezone")
    @classmethod
    def _tz_present(cls, value: str) -> str:
        trimmed = (value or "").strip()
        if not trimmed:
            raise ValueError("source_timezone is required.")
        return trimmed

    @field_validator("normalization_timezone")
    @classmethod
    def _normalization_utc(cls, value: str) -> str:
        if (value or "").strip().upper() != _NORMALIZATION_TZ:
            raise ValueError("normalization_timezone must be UTC.")
        return _NORMALIZATION_TZ


class PricePolicy(_Strict):
    source: PriceSourceMode
    fallback: str | None = None


class OhlcvPolicy(_Strict):
    use_mode: OhlcvUseMode


class Capital(_Strict):
    independent_initial_capital: Decimal | None = None

    @field_validator("independent_initial_capital")
    @classmethod
    def _positive_finite(cls, value: Decimal | None) -> Decimal | None:
        if value is None:
            return None
        if not value.is_finite() or value <= 0:
            raise ValueError("independent_initial_capital must be a positive finite decimal.")
        return value


class ImportBinding(_Strict):
    source_asset_id: str
    normalized_event_revision_id: str
    mapping_revision_id: str | None = None

    @field_validator("source_asset_id", "normalized_event_revision_id")
    @classmethod
    def _binding_present(cls, value: str) -> str:
        trimmed = (value or "").strip()
        if not trimmed:
            raise ValueError("import binding reference is required.")
        return trimmed


class TradingSignalConfig(_Strict):
    """The full immutable Trading Signal revision payload (doc 04 §9.2)."""

    kind: str = "trading_signal"
    identity: SignalIdentity
    source: SignalSource
    instrument_scope: InstrumentScope
    event_model: EventModel
    classification: SignalClassification = SignalClassification()
    data_quality: DataQuality
    time_policy: TimePolicy
    price_policy: PricePolicy
    ohlcv_policy: OhlcvPolicy
    capital: Capital = Capital()
    import_binding: ImportBinding

    @field_validator("kind")
    @classmethod
    def _kind_is_trading_signal(cls, value: str) -> str:
        if value != "trading_signal":
            raise ValueError("kind must be 'trading_signal'.")
        return value
