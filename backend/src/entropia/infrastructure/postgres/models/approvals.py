"""Generic approval-decision record (decision D2).

One table reused by Market Data (2a) and later by Research/ESP/Package stages.
An approval never mutates the target revision payload; it records the Admin
identity, the state transition, an optional note, and the policy context.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from entropia.domain.lifecycle.enums import ApprovalState
from entropia.infrastructure.postgres.base import Base
from entropia.infrastructure.postgres.types import enum_column


class ApprovalDecision(Base):
    """Append-only approval/rejection event for any approvable target."""

    __tablename__ = "approval_decision"

    decision_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    target_entity_id: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    target_revision_id: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    target_kind: Mapped[str] = mapped_column(String(64), nullable=False)
    decision: Mapped[ApprovalState] = mapped_column(
        enum_column(ApprovalState, "approval_decision_state"), nullable=False
    )
    approver_principal_id: Mapped[str | None] = mapped_column(
        String(40), ForeignKey("principals.principal_id"), nullable=True
    )
    prior_state: Mapped[str | None] = mapped_column(String(48), nullable=True)
    new_state: Mapped[str | None] = mapped_column(String(48), nullable=True)
    note: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    policy_context: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
