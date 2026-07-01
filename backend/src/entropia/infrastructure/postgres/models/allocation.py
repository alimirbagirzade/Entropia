"""Portfolio / Equity Allocation persistence (Stage 4a, doc 13 §8.1).

Three tables on the allocation plane, all hung off a Mainboard composition
(``mainboard_workspace`` IS the composition draft, doc 13 §8.1 — no new
``composition_draft`` table is introduced). One plan per composition (1:1,
enforced by a UNIQUE on ``workspace_entity_id``):

* ``portfolio_allocation_plan`` — the plan ROOT carrying the MUTABLE draft state
  (enabled, initial capital/currency, compounding, reserve) + ``row_version``
  (the optimistic-concurrency token) + a plain ``current_revision_id`` head
  pointer (no FK — mirrors ``entity_registry``, avoids a circular constraint).
* ``portfolio_allocation_entry`` — a plain child row bound to a composition item
  by ``composition_item_id`` (= ``mainboard_working_item.item_id``), NEVER by
  display name / DOM / Type text (doc 13 §13). ``composition_item_id`` carries NO
  ForeignKey: an entry may legitimately outlive its item's soft-delete and be
  flagged ITEM_UNAVAILABLE at validation time (§4.1) rather than blocking the
  insert — the same normalized-reference pattern used for strategy references.
* ``portfolio_allocation_plan_revision`` — INSERT-only immutable validated config
  + ``config_hash`` (doc 13 §8.1). Never UPDATEd; rerun = new revision.

Money and percent use ``Numeric`` (never float, doc 13 §13). Enums use
``enum_column`` (VARCHAR + CHECK, ``native_enum=False``) so no PostgreSQL
``CREATE TYPE`` is emitted (identical to 0005-0011).
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from entropia.domain.allocation.enums import AllocationCurrency, CompoundingMode
from entropia.domain.mainboard.enums import MainboardItemKind
from entropia.infrastructure.postgres.base import Base
from entropia.infrastructure.postgres.mixins import TimestampMixin
from entropia.infrastructure.postgres.types import enum_column

_ENTITY_FK = "entity_registry.entity_id"
_PRINCIPAL_FK = "principals.principal_id"
_PLAN_FK = "portfolio_allocation_plan.plan_id"

# Money at 38/18 (D6-style high precision); percent at 9/6 (0..100.000000).
_AMOUNT = Numeric(38, 18)
_PERCENT = Numeric(9, 6)


class PortfolioAllocationPlan(TimestampMixin, Base):
    """Composition-bound plan root + current mutable draft state (doc 13 §8.1)."""

    __tablename__ = "portfolio_allocation_plan"
    __table_args__ = (
        UniqueConstraint("workspace_entity_id", name="uq_portfolio_allocation_plan_workspace"),
    )

    plan_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    workspace_entity_id: Mapped[str] = mapped_column(
        String(40), ForeignKey(_ENTITY_FK), nullable=False, index=True
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    initial_capital_amount: Mapped[Decimal | None] = mapped_column(_AMOUNT, nullable=True)
    initial_capital_currency: Mapped[AllocationCurrency | None] = mapped_column(
        enum_column(AllocationCurrency, "allocation_currency"), nullable=True
    )
    compounding_mode: Mapped[CompoundingMode | None] = mapped_column(
        enum_column(CompoundingMode, "allocation_compounding_mode"), nullable=True
    )
    reserve_cash_percent: Mapped[Decimal | None] = mapped_column(_PERCENT, nullable=True)
    draft_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Plain column (no FK): set once a revision exists (mirrors entity_registry).
    current_revision_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    row_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    created_by_principal_id: Mapped[str | None] = mapped_column(
        String(40), ForeignKey(_PRINCIPAL_FK), nullable=True
    )


class PortfolioAllocationEntry(TimestampMixin, Base):
    """A draft allocation row bound to a composition item (doc 13 §5.2, §13).

    No ``unique(plan_id, composition_item_id)``: a duplicate ACTIVE item is a
    validation blocker (§14#6), not a DB constraint — mirroring the Mainboard
    "no unique(workspace, root)" attach rule.
    """

    __tablename__ = "portfolio_allocation_entry"

    entry_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    plan_id: Mapped[str] = mapped_column(
        String(40), ForeignKey(_PLAN_FK, ondelete="CASCADE"), nullable=False, index=True
    )
    # No FK (normalized reference): survives a composition item's soft-delete and
    # is flagged ITEM_UNAVAILABLE at validation, not blocked at insert (doc 13 §4.1).
    composition_item_id: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    item_type: Mapped[MainboardItemKind] = mapped_column(
        enum_column(MainboardItemKind, "mainboard_item_kind"), nullable=False
    )
    active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    equity_share_percent: Mapped[Decimal | None] = mapped_column(_PERCENT, nullable=True)
    position_index: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    row_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")


class PortfolioAllocationPlanRevision(Base):
    """Immutable validated allocation config + config hash (doc 13 §8.1). Never UPDATEd."""

    __tablename__ = "portfolio_allocation_plan_revision"
    __table_args__ = (
        UniqueConstraint("plan_id", "revision_no", name="uq_portfolio_allocation_plan_revision_no"),
    )

    plan_revision_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    plan_id: Mapped[str] = mapped_column(
        String(40), ForeignKey(_PLAN_FK, ondelete="CASCADE"), nullable=False, index=True
    )
    revision_no: Mapped[int] = mapped_column(Integer, nullable=False)
    config: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    config_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    derived_amounts: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    source_draft_row_version: Mapped[int] = mapped_column(Integer, nullable=False)
    created_by_principal_id: Mapped[str | None] = mapped_column(
        String(40), ForeignKey(_PRINCIPAL_FK), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
