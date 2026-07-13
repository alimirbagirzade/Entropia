"""Canonical instrument registry domain (GAP-16; Master Reference §8.1, §9.1)."""

from __future__ import annotations

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
    can_deprecate,
    next_instrument_state,
)

__all__ = [
    "ContractType",
    "InstrumentScope",
    "InstrumentState",
    "can_deprecate",
    "coerce_contract_type",
    "next_instrument_state",
    "normalize_alias",
    "normalize_token",
    "require_registerable",
    "resolution_key",
]
