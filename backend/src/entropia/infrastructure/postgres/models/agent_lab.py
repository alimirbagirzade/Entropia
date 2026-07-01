"""Analysis Lab persistence (Stage 6a, doc 18 §9, §9.1).

Agent Workspace observation/control plane. The runtime's operational pointers
(status, active_task_id, last_checkpoint_id, pending_control) are mutable and
owned only by the Coordinator/control services; directives, checkpoints,
messages and events are append-only. Circular/cross-domain references
(active_task_id, context_manifest_id, parent_task_id, checkpoint_id) are plain
String columns (no FK), mirroring the entity_registry head-pointer pattern.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Identity,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from entropia.domain.agent_lab.enums import (
    AgentTaskPriority,
    AgentTaskStatus,
    DirectiveStatus,
    HypothesisStatus,
    LabMessageType,
    RuntimeControl,
    RuntimeMode,
    RuntimeStatus,
)
from entropia.domain.lifecycle.enums import ActorKind, DeletionState
from entropia.infrastructure.postgres.base import Base
from entropia.infrastructure.postgres.mixins import TimestampMixin
from entropia.infrastructure.postgres.types import enum_column

_PRINCIPAL_FK = "principals.principal_id"
_RUNTIME_FK = "agent_runtime.agent_id"
_TASK_FK = "agent_task.task_id"
_ARTIFACT_FK = "hypothesis_artifact.artifact_id"


class AgentRuntime(TimestampMixin, Base):
    """Alpha Agent instance + mutable lifecycle pointers (doc 18 §9). Singleton
    per agent_id; not a human account."""

    __tablename__ = "agent_runtime"

    agent_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    mode: Mapped[RuntimeMode] = mapped_column(
        enum_column(RuntimeMode, "agent_runtime_mode"), nullable=False
    )
    status: Mapped[RuntimeStatus] = mapped_column(
        enum_column(RuntimeStatus, "agent_runtime_status"), nullable=False, index=True
    )
    # Plain columns (no FK): circular with agent_task / agent_checkpoint.
    active_task_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    last_checkpoint_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    pending_control: Mapped[RuntimeControl | None] = mapped_column(
        enum_column(RuntimeControl, "agent_runtime_control"), nullable=True
    )
    control_correlation_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    policy_revision: Mapped[str | None] = mapped_column(String(64), nullable=True)
    row_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")


class AgentTask(TimestampMixin, Base):
    """Persistent research/work object (doc 18 §9). Task status is a SEPARATE
    registry from BacktestRun / generic Job enums (CR-04)."""

    __tablename__ = "agent_task"

    task_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    agent_id: Mapped[str] = mapped_column(
        String(64), ForeignKey(_RUNTIME_FK), nullable=False, index=True
    )
    task_type: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    priority: Mapped[AgentTaskPriority] = mapped_column(
        enum_column(AgentTaskPriority, "agent_task_priority"), nullable=False
    )
    status: Mapped[AgentTaskStatus] = mapped_column(
        enum_column(AgentTaskStatus, "agent_task_status"), nullable=False, index=True
    )
    stage: Mapped[str | None] = mapped_column(String(64), nullable=True)
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    context_manifest_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    parent_task_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    waiting_reason: Mapped[str | None] = mapped_column(String(256), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(String(256), nullable=True)


class TaskDirective(Base):
    """Human research direction (doc 18 §9). Row content (text/priority/author)
    is immutable; status is an operational pointer with an append-only event
    trail."""

    __tablename__ = "task_directive"

    directive_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    author_principal_id: Mapped[str] = mapped_column(
        String(40), ForeignKey(_PRINCIPAL_FK), nullable=False, index=True
    )
    target_agent_id: Mapped[str] = mapped_column(
        String(64), ForeignKey(_RUNTIME_FK), nullable=False, index=True
    )
    related_task_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[AgentTaskPriority] = mapped_column(
        enum_column(AgentTaskPriority, "task_directive_priority"), nullable=False
    )
    status: Mapped[DirectiveStatus] = mapped_column(
        enum_column(DirectiveStatus, "task_directive_status"), nullable=False, index=True
    )
    consumed_checkpoint_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    delivery_policy: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="next_safe_checkpoint",
        server_default="next_safe_checkpoint",
    )
    correlation_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class AgentCheckpoint(Base):
    """Resumable, immutable work record (doc 18 §9, §9.1). Never UPDATEd."""

    __tablename__ = "agent_checkpoint"
    __table_args__ = (UniqueConstraint("task_id", "checkpoint_no", name="uq_agent_checkpoint_no"),)

    checkpoint_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    task_id: Mapped[str] = mapped_column(
        String(40), ForeignKey(_TASK_FK, ondelete="CASCADE"), nullable=False, index=True
    )
    checkpoint_no: Mapped[int] = mapped_column(Integer, nullable=False)
    stage: Mapped[str] = mapped_column(String(64), nullable=False)
    state_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)
    context_manifest_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    plan_revision: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    directive_cursor: Mapped[str | None] = mapped_column(String(40), nullable=True)
    artifact_ids: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, default=list, server_default="[]"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class LabMessage(Base):
    """Conversation/event record (doc 18 §9). Append-only; corrections add a new
    clarification message, the original is never deleted."""

    __tablename__ = "lab_message"

    message_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    type: Mapped[LabMessageType] = mapped_column(
        enum_column(LabMessageType, "lab_message_type"), nullable=False, index=True
    )
    author_principal_id: Mapped[str | None] = mapped_column(
        String(40), ForeignKey(_PRINCIPAL_FK), nullable=True
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    task_id: Mapped[str | None] = mapped_column(
        String(40), ForeignKey(_TASK_FK, ondelete="SET NULL"), nullable=True
    )
    correlation_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )


class HypothesisArtifact(TimestampMixin, Base):
    """Persistent hypothesis/output (doc 18 §9, §12). Not derived from chat.
    Agent-owned; soft delete keeps provenance/audit (AL-16)."""

    __tablename__ = "hypothesis_artifact"

    artifact_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    status: Mapped[HypothesisStatus] = mapped_column(
        enum_column(HypothesisStatus, "hypothesis_status"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    mechanism: Mapped[str] = mapped_column(Text, nullable=False)
    data_context: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_refs: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, default=list, server_default="[]"
    )
    next_action: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_task_id: Mapped[str | None] = mapped_column(
        String(40), ForeignKey(_TASK_FK, ondelete="SET NULL"), nullable=True, index=True
    )
    checkpoint_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    deletion_state: Mapped[DeletionState] = mapped_column(
        enum_column(DeletionState, "hypothesis_deletion_state"),
        nullable=False,
        default=DeletionState.ACTIVE,
        server_default=DeletionState.ACTIVE.value,
        index=True,
    )
    created_by_principal_id: Mapped[str | None] = mapped_column(
        String(40), ForeignKey(_PRINCIPAL_FK), nullable=True
    )
    correlation_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    row_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")


class ArtifactLink(Base):
    """Provenance edge from a hypothesis to a package/run/result/data resource
    (doc 18 §9). Append-only."""

    __tablename__ = "artifact_link"

    link_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    source_artifact_id: Mapped[str] = mapped_column(
        String(40), ForeignKey(_ARTIFACT_FK, ondelete="CASCADE"), nullable=False, index=True
    )
    target_type: Mapped[str] = mapped_column(String(64), nullable=False)
    target_id: Mapped[str] = mapped_column(String(64), nullable=False)
    relation_type: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class AgentEvent(Base):
    """Durable observability + projection-refresh trigger (doc 18 §9, §9.2).
    Append-only; ``seq`` gives a stable SSE ordering / Last-Event-ID."""

    __tablename__ = "agent_event"

    event_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    seq: Mapped[int] = mapped_column(
        BigInteger, Identity(), nullable=False, unique=True, index=True
    )
    type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    actor_principal_id: Mapped[str | None] = mapped_column(
        String(40), ForeignKey(_PRINCIPAL_FK), nullable=True
    )
    actor_kind: Mapped[ActorKind] = mapped_column(
        enum_column(ActorKind, "agent_event_actor_kind"), nullable=False
    )
    task_id: Mapped[str | None] = mapped_column(
        String(40), ForeignKey(_TASK_FK, ondelete="SET NULL"), nullable=True, index=True
    )
    directive_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )
    correlation_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )


__all__ = [
    "AgentCheckpoint",
    "AgentEvent",
    "AgentRuntime",
    "AgentTask",
    "ArtifactLink",
    "HypothesisArtifact",
    "LabMessage",
    "TaskDirective",
]
