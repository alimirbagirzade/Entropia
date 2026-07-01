"""stage 4a — Portfolio / Equity Allocation plane (doc 13 §8.1)

Three new tables on the allocation plane, all hung off a Mainboard composition
(the existing ``mainboard_workspace`` IS the composition draft — no new
``composition_draft`` table):

* ``portfolio_allocation_plan`` — 1:1 with a composition (UNIQUE workspace),
  carrying the mutable draft state + ``row_version`` + a plain ``current_revision_id``.
* ``portfolio_allocation_entry`` — plain child bound by ``composition_item_id``
  (no FK: an entry may outlive its item's soft-delete and be flagged at validation).
* ``portfolio_allocation_plan_revision`` — INSERT-only immutable validated config.

ENUM REUSE — currency / compounding / item_kind columns are built via
``enum_column`` (VARCHAR, ``native_enum=False``) so NO PostgreSQL ``CREATE TYPE``
is emitted (identical to 0005-0011). Money/percent are ``Numeric`` (never float).
``current_revision_id`` carries NO ForeignKey (mirrors ``entity_registry``,
avoids a circular root<->revision constraint).

Revision ID: 0012_portfolio_allocation
Revises: 0011_trade_log
Create Date: 2026-07-01
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from entropia.domain.allocation.enums import AllocationCurrency, CompoundingMode
from entropia.domain.mainboard.enums import MainboardItemKind
from entropia.infrastructure.postgres.types import enum_column

revision: str = "0012_portfolio_allocation"
down_revision: str | None = "0011_trade_log"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ENTITY_FK = "entity_registry.entity_id"
_PRINCIPAL_FK = "principals.principal_id"
_PLAN_FK = "portfolio_allocation_plan.plan_id"

_AMOUNT = sa.Numeric(38, 18)
_PERCENT = sa.Numeric(9, 6)


def upgrade() -> None:
    op.create_table(
        "portfolio_allocation_plan",
        sa.Column("plan_id", sa.String(40), primary_key=True),
        sa.Column(
            "workspace_entity_id",
            sa.String(40),
            sa.ForeignKey(_ENTITY_FK),
            nullable=False,
        ),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("initial_capital_amount", _AMOUNT, nullable=True),
        sa.Column(
            "initial_capital_currency",
            enum_column(AllocationCurrency, "allocation_currency"),
            nullable=True,
        ),
        sa.Column(
            "compounding_mode",
            enum_column(CompoundingMode, "allocation_compounding_mode"),
            nullable=True,
        ),
        sa.Column("reserve_cash_percent", _PERCENT, nullable=True),
        sa.Column("draft_fingerprint", sa.String(64), nullable=True),
        sa.Column("current_revision_id", sa.String(40), nullable=True),
        sa.Column("row_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_by_principal_id", sa.String(40), sa.ForeignKey(_PRINCIPAL_FK), nullable=True
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("workspace_entity_id", name="uq_portfolio_allocation_plan_workspace"),
    )
    op.create_index(
        "ix_portfolio_allocation_plan_workspace_entity_id",
        "portfolio_allocation_plan",
        ["workspace_entity_id"],
    )

    op.create_table(
        "portfolio_allocation_entry",
        sa.Column("entry_id", sa.String(40), primary_key=True),
        sa.Column(
            "plan_id",
            sa.String(40),
            sa.ForeignKey(_PLAN_FK, ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("composition_item_id", sa.String(40), nullable=False),
        sa.Column(
            "item_type",
            enum_column(MainboardItemKind, "mainboard_item_kind"),
            nullable=False,
        ),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("equity_share_percent", _PERCENT, nullable=True),
        sa.Column("position_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("row_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index(
        "ix_portfolio_allocation_entry_plan_id",
        "portfolio_allocation_entry",
        ["plan_id"],
    )
    op.create_index(
        "ix_portfolio_allocation_entry_composition_item_id",
        "portfolio_allocation_entry",
        ["composition_item_id"],
    )

    op.create_table(
        "portfolio_allocation_plan_revision",
        sa.Column("plan_revision_id", sa.String(40), primary_key=True),
        sa.Column(
            "plan_id",
            sa.String(40),
            sa.ForeignKey(_PLAN_FK, ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("revision_no", sa.Integer(), nullable=False),
        sa.Column("config", postgresql.JSONB(), nullable=False),
        sa.Column("config_hash", sa.String(64), nullable=False),
        sa.Column("derived_amounts", postgresql.JSONB(), nullable=True),
        sa.Column("source_draft_row_version", sa.Integer(), nullable=False),
        sa.Column(
            "created_by_principal_id", sa.String(40), sa.ForeignKey(_PRINCIPAL_FK), nullable=True
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint(
            "plan_id", "revision_no", name="uq_portfolio_allocation_plan_revision_no"
        ),
    )
    op.create_index(
        "ix_portfolio_allocation_plan_revision_plan_id",
        "portfolio_allocation_plan_revision",
        ["plan_id"],
    )
    op.create_index(
        "ix_portfolio_allocation_plan_revision_config_hash",
        "portfolio_allocation_plan_revision",
        ["config_hash"],
    )


def downgrade() -> None:
    op.drop_table("portfolio_allocation_plan_revision")
    op.drop_table("portfolio_allocation_entry")
    op.drop_table("portfolio_allocation_plan")
