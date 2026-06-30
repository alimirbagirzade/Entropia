"""Generic approval-decision data access (decision D2)."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from entropia.domain.lifecycle.enums import ApprovalState
from entropia.infrastructure.postgres.models import ApprovalDecision
from entropia.shared.ids import new_id


def add_approval_decision(
    session: AsyncSession,
    *,
    target_entity_id: str,
    target_kind: str,
    decision: ApprovalState,
    target_revision_id: str | None = None,
    approver_principal_id: str | None = None,
    prior_state: str | None = None,
    new_state: str | None = None,
    note: str | None = None,
    policy_context: dict[str, Any] | None = None,
) -> ApprovalDecision:
    row = ApprovalDecision(
        decision_id=new_id("apr"),
        target_entity_id=target_entity_id,
        target_revision_id=target_revision_id,
        target_kind=target_kind,
        decision=decision,
        approver_principal_id=approver_principal_id,
        prior_state=prior_state,
        new_state=new_state,
        note=note,
        policy_context=policy_context,
    )
    session.add(row)
    return row
