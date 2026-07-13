"""Canonical instrument registry persistence (GAP-16; Master Reference §8.1, §9.1).

``instrument_registry``: the canonical row for a tradable instrument — the
``resolution_key`` (``venue:symbol:contract_type``) is its stable identity, so a
spot instrument and a perpetual can never be equated by free-text symbol match.
The OHLCV canonical schema's ``instrument_id`` (Master §9.1) is a reference to
this table's PK. ``instrument_alias``: display-text -> instrument resolution rows
(e.g. "BTCUSDT Perpetual" -> the canonical id) so the UI's free-text scope maps
to exactly one canonical instrument. Both reference ``principals`` for provenance.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from entropia.domain.instrument.enums import ContractType, InstrumentState
from entropia.infrastructure.postgres.base import Base
from entropia.infrastructure.postgres.mixins import TimestampMixin
from entropia.infrastructure.postgres.types import enum_column

_PRINCIPAL_FK = "principals.principal_id"
_INSTRUMENT_FK = "instrument_registry.instrument_id"


class InstrumentRegistry(TimestampMixin, Base):
    """The canonical row for one tradable instrument (Master §8.1)."""

    __tablename__ = "instrument_registry"
    __table_args__ = (
        UniqueConstraint("resolution_key", name="uq_instrument_registry_resolution_key"),
    )

    instrument_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    resolution_key: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    venue_id: Mapped[str] = mapped_column(String(64), nullable=False)
    symbol: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    contract_type: Mapped[ContractType] = mapped_column(
        enum_column(ContractType, "instrument_contract_type"), nullable=False
    )
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    base_asset: Mapped[str | None] = mapped_column(String(32), nullable=True)
    quote_asset: Mapped[str | None] = mapped_column(String(32), nullable=True)
    settlement_asset: Mapped[str | None] = mapped_column(String(32), nullable=True)
    multiplier: Mapped[Any | None] = mapped_column(Numeric(38, 18), nullable=True)
    market_class: Mapped[str | None] = mapped_column(String(32), nullable=True)
    state: Mapped[InstrumentState] = mapped_column(
        enum_column(InstrumentState, "instrument_state"),
        nullable=False,
        default=InstrumentState.ACTIVE,
        index=True,
    )
    registry_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    deprecation_reason: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_by_principal_id: Mapped[str | None] = mapped_column(
        String(40), ForeignKey(_PRINCIPAL_FK), nullable=True
    )
    updated_by_principal_id: Mapped[str | None] = mapped_column(
        String(40), ForeignKey(_PRINCIPAL_FK), nullable=True
    )


class InstrumentAlias(TimestampMixin, Base):
    """A normalized display alias that resolves to exactly one instrument.

    ``alias_norm`` is UNIQUE across the whole registry: one alias can never point
    at two instruments (that would make free-text scope ambiguous — the exact
    failure Master §8.1 forbids).
    """

    __tablename__ = "instrument_alias"
    __table_args__ = (UniqueConstraint("alias_norm", name="uq_instrument_alias_norm"),)

    alias_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    instrument_id: Mapped[str] = mapped_column(
        String(40), ForeignKey(_INSTRUMENT_FK), nullable=False, index=True
    )
    alias_norm: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    alias_text: Mapped[str] = mapped_column(String(200), nullable=False)
    created_by_principal_id: Mapped[str | None] = mapped_column(
        String(40), ForeignKey(_PRINCIPAL_FK), nullable=True
    )
