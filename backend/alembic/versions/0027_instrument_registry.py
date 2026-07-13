"""gap-16 — canonical instrument registry (Master Reference §8.1, §9.1)

Adds ``instrument_registry`` (the canonical row for one tradable instrument; its
``resolution_key`` = normalized ``venue:symbol:contract_type`` is the stable
identity that keeps spot vs perpetual distinct — a free-text symbol match can
never equate "BTCUSD" with "BTCUSDT Perpetual") and ``instrument_alias`` (a
display-text -> instrument resolution row; ``alias_norm`` is UNIQUE across the
whole registry so an alias can never be ambiguous). The OHLCV canonical schema's
``instrument_id`` (Master §9.1) references ``instrument_registry.instrument_id``.
No behaviour lives here; the register/alias/deprecate commands drive the rows.

Revision ID: 0027_instrument_registry
Revises: 0026_package_baseline_asset
Create Date: 2026-07-13
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from entropia.domain.instrument.enums import ContractType, InstrumentState
from entropia.infrastructure.postgres.types import enum_column

revision: str = "0027_instrument_registry"
down_revision: str | None = "0026_package_baseline_asset"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PRINCIPAL_FK = "principals.principal_id"
_INSTRUMENT_FK = "instrument_registry.instrument_id"


def upgrade() -> None:
    op.create_table(
        "instrument_registry",
        sa.Column("instrument_id", sa.String(40), primary_key=True),
        sa.Column("resolution_key", sa.String(200), nullable=False),
        sa.Column("venue_id", sa.String(64), nullable=False),
        sa.Column("symbol", sa.String(64), nullable=False),
        sa.Column(
            "contract_type",
            enum_column(ContractType, "instrument_contract_type"),
            nullable=False,
        ),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("base_asset", sa.String(32), nullable=True),
        sa.Column("quote_asset", sa.String(32), nullable=True),
        sa.Column("settlement_asset", sa.String(32), nullable=True),
        sa.Column("multiplier", sa.Numeric(38, 18), nullable=True),
        sa.Column("market_class", sa.String(32), nullable=True),
        sa.Column(
            "state",
            enum_column(InstrumentState, "instrument_state"),
            nullable=False,
            server_default="active",
        ),
        sa.Column("registry_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("deprecation_reason", sa.String(512), nullable=True),
        sa.Column(
            "created_by_principal_id", sa.String(40), sa.ForeignKey(_PRINCIPAL_FK), nullable=True
        ),
        sa.Column(
            "updated_by_principal_id", sa.String(40), sa.ForeignKey(_PRINCIPAL_FK), nullable=True
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("resolution_key", name="uq_instrument_registry_resolution_key"),
    )
    op.create_index(
        "ix_instrument_registry_resolution_key", "instrument_registry", ["resolution_key"]
    )
    op.create_index("ix_instrument_registry_symbol", "instrument_registry", ["symbol"])
    op.create_index("ix_instrument_registry_state", "instrument_registry", ["state"])

    op.create_table(
        "instrument_alias",
        sa.Column("alias_id", sa.String(40), primary_key=True),
        sa.Column("instrument_id", sa.String(40), sa.ForeignKey(_INSTRUMENT_FK), nullable=False),
        sa.Column("alias_norm", sa.String(200), nullable=False),
        sa.Column("alias_text", sa.String(200), nullable=False),
        sa.Column(
            "created_by_principal_id", sa.String(40), sa.ForeignKey(_PRINCIPAL_FK), nullable=True
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("alias_norm", name="uq_instrument_alias_norm"),
    )
    op.create_index("ix_instrument_alias_instrument_id", "instrument_alias", ["instrument_id"])
    op.create_index("ix_instrument_alias_norm", "instrument_alias", ["alias_norm"])


def downgrade() -> None:
    op.drop_table("instrument_alias")
    op.drop_table("instrument_registry")
