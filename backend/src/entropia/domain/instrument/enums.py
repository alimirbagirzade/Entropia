"""Instrument registry per-domain enums (GAP-16; Master Reference §8.1, §9.1).

All values are lowercase snake_case and are returned over REST verbatim. The
``contract_type`` is the discriminator that keeps a spot instrument distinct from
a perpetual/future one — "BTCUSD" (spot) and "BTCUSDT Perpetual" can never be
equated by free-text symbol match (Master Reference §8.1).
"""

from __future__ import annotations

from enum import StrEnum


class ContractType(StrEnum):
    """The settlement/contract shape of a tradable instrument (Master §8.1)."""

    SPOT = "spot"
    PERPETUAL = "perpetual"
    FUTURE = "future"
    OPTION = "option"
    INDEX = "index"
    OTHER = "other"


class InstrumentState(StrEnum):
    """Registry lifecycle projection of a canonical instrument.

    ``active``: selectable for new work and resolvable for ingest.
    ``deprecated``: removed from default new selection; historical pins that
    already reference the ``instrument_id`` keep reading it (Master §8.1).
    """

    ACTIVE = "active"
    DEPRECATED = "deprecated"
