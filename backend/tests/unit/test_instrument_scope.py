"""Unit tests for the canonical instrument scope normalization + state machine
(GAP-16; Master Reference §8.1). Pure functions — no database."""

from __future__ import annotations

import pytest

from entropia.domain.instrument.enums import ContractType, InstrumentState
from entropia.domain.instrument.scope import (
    InstrumentScope,
    coerce_contract_type,
    normalize_alias,
    normalize_token,
    require_registerable,
    resolution_key,
)
from entropia.domain.instrument.state_machine import (
    IllegalInstrumentTransition,
    can_deprecate,
    next_instrument_state,
)
from entropia.shared.errors import InstrumentScopeInvalidError


def test_resolution_key_is_normalized_lowercase() -> None:
    assert (
        resolution_key("  Binance ", " BTCUSDT ", ContractType.PERPETUAL)
        == "binance:btcusdt:perpetual"
    )


def test_spot_and_perpetual_are_distinct_identities() -> None:
    """Master §8.1: "BTCUSD" (spot) and "BTCUSDT Perpetual" cannot be equated."""
    spot = resolution_key("coinbase", "BTC-USD", ContractType.SPOT)
    perp = resolution_key("binance", "BTCUSDT", ContractType.PERPETUAL)
    assert spot != perp
    # Even the same venue+symbol with a different contract type is a distinct row.
    assert resolution_key("binance", "BTCUSDT", ContractType.SPOT) != resolution_key(
        "binance", "BTCUSDT", ContractType.PERPETUAL
    )


def test_coerce_contract_type_accepts_known_and_rejects_unknown() -> None:
    assert coerce_contract_type("perpetual") == ContractType.PERPETUAL
    assert coerce_contract_type(ContractType.SPOT) == ContractType.SPOT
    with pytest.raises(InstrumentScopeInvalidError):
        coerce_contract_type("swaption")
    with pytest.raises(InstrumentScopeInvalidError):
        coerce_contract_type("")


def test_normalize_token_and_alias_collapse_whitespace() -> None:
    assert normalize_token("  BTCUSDT   Perpetual ") == "btcusdt perpetual"
    assert normalize_alias("BTCUSDT   Perpetual") == "btcusdt perpetual"
    assert normalize_token(None) == ""


def _scope(**overrides: object) -> InstrumentScope:
    base = {
        "venue_id": "binance",
        "symbol": "BTCUSDT",
        "contract_type": ContractType.PERPETUAL,
        "display_name": "BTCUSDT Perpetual",
    }
    base.update(overrides)
    return InstrumentScope(**base)  # type: ignore[arg-type]


def test_require_registerable_rejects_blank_identity() -> None:
    with pytest.raises(InstrumentScopeInvalidError):
        require_registerable(_scope(venue_id="  "))
    with pytest.raises(InstrumentScopeInvalidError):
        require_registerable(_scope(symbol=""))
    with pytest.raises(InstrumentScopeInvalidError):
        require_registerable(_scope(display_name="   "))
    # A complete scope is accepted.
    require_registerable(_scope())


def test_scope_resolution_key_property() -> None:
    assert _scope().resolution_key == "binance:btcusdt:perpetual"


def test_state_machine_only_allows_active_to_deprecated() -> None:
    assert can_deprecate(InstrumentState.ACTIVE) is True
    assert can_deprecate(InstrumentState.DEPRECATED) is False
    assert (
        next_instrument_state(InstrumentState.ACTIVE, InstrumentState.DEPRECATED)
        == InstrumentState.DEPRECATED
    )
    with pytest.raises(IllegalInstrumentTransition):
        next_instrument_state(InstrumentState.DEPRECATED, InstrumentState.ACTIVE)
    with pytest.raises(IllegalInstrumentTransition):
        next_instrument_state(InstrumentState.ACTIVE, InstrumentState.ACTIVE)
