"""Tool Gateway persistence (Stage 6a-2, doc 18 §9.2, §10, §14).

One durable ``agent_tool_call`` row per UI-less agent tool invocation, carrying
the fixed context envelope the spec mandates (actor_context, task_id,
checkpoint_id, input_manifest_id, idempotency_key, policy_scope,
artifact_output_ref; doc 18 §9.2). The row is the at-least-once redelivery guard:
a redelivered call with the same ``idempotency_key`` replays the recorded outcome
instead of re-executing (doc 18 §8.5, AL-14). Cross-domain references
(checkpoint_id, input_manifest_id, artifact_output_ref) are plain String columns
mirroring the agent_lab head-pointer pattern; ``task_id`` keeps an FK with
``ON DELETE SET NULL`` for provenance.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from entropia.domain.agent_lab.tool_gateway import PolicyScope, ToolCallStatus
from entropia.domain.lifecycle.enums import ActorKind
from entropia.infrastructure.postgres.base import Base
from entropia.infrastructure.postgres.mixins import TimestampMixin
from entropia.infrastructure.postgres.types import enum_column

_PRINCIPAL_FK = "principals.principal_id"
_RUNTIME_FK = "agent_runtime.agent_id"
_TASK_FK = "agent_task.task_id"


class AgentToolCall(TimestampMixin, Base):
    """A durable, governed record of one agent Tool Gateway call (doc 18 §9.2).

    ``status`` is the operational pointer (queued -> running -> succeeded/failed/
    rejected); ``response_ref`` stores the terminal outcome verbatim so a
    redelivered call replays instead of re-executing (AL-14)."""

    __tablename__ = "agent_tool_call"
    __table_args__ = (UniqueConstraint("idempotency_key", name="uq_agent_tool_call_idem"),)

    tool_call_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    tool_name: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    agent_id: Mapped[str] = mapped_column(
        String(64), ForeignKey(_RUNTIME_FK), nullable=False, index=True
    )
    actor_principal_id: Mapped[str | None] = mapped_column(
        String(40), ForeignKey(_PRINCIPAL_FK), nullable=True
    )
    actor_kind: Mapped[ActorKind] = mapped_column(
        enum_column(ActorKind, "agent_tool_call_actor_kind"), nullable=False
    )
    task_id: Mapped[str | None] = mapped_column(
        String(40), ForeignKey(_TASK_FK, ondelete="SET NULL"), nullable=True, index=True
    )
    checkpoint_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    input_manifest_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(80), nullable=True)
    policy_scope: Mapped[PolicyScope] = mapped_column(
        enum_column(PolicyScope, "agent_tool_call_policy_scope"), nullable=False
    )
    status: Mapped[ToolCallStatus] = mapped_column(
        enum_column(ToolCallStatus, "agent_tool_call_status"), nullable=False, index=True
    )
    artifact_output_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)
    request: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )
    response_ref: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    failure_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    failure_message: Mapped[str | None] = mapped_column(String(256), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(40), nullable=True)


__all__ = ["AgentToolCall"]
