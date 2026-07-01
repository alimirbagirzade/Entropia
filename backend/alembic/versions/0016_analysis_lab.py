"""stage 6a — Analysis Lab observation/control plane (doc 18 §9)

Eight Agent Workspace tables. The runtime's operational pointers are mutable;
directives, checkpoints, messages, artifact links and events are append-only.
Enum columns are VARCHAR + CHECK (enum_column, no CREATE TYPE). A singleton
``alpha-agent`` runtime row is seeded so the overview projection renders.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from entropia.domain.agent_lab.enums import (
    ALPHA_AGENT_ID,
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
from entropia.infrastructure.postgres.types import enum_column

revision: str = "0016_analysis_lab"
down_revision: str | None = "0015_arrange_metrics_export"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PRINCIPAL_FK = "principals.principal_id"
_RUNTIME_FK = "agent_runtime.agent_id"
_TASK_FK = "agent_task.task_id"
_ARTIFACT_FK = "hypothesis_artifact.artifact_id"


def upgrade() -> None:
    # === agent_runtime (root singleton, no FK) ===
    op.create_table(
        "agent_runtime",
        sa.Column("agent_id", sa.String(64), primary_key=True),
        sa.Column("mode", enum_column(RuntimeMode, "agent_runtime_mode"), nullable=False),
        sa.Column("status", enum_column(RuntimeStatus, "agent_runtime_status"), nullable=False),
        sa.Column("active_task_id", sa.String(40), nullable=True),
        sa.Column("last_checkpoint_id", sa.String(40), nullable=True),
        sa.Column(
            "pending_control", enum_column(RuntimeControl, "agent_runtime_control"), nullable=True
        ),
        sa.Column("control_correlation_id", sa.String(40), nullable=True),
        sa.Column("policy_revision", sa.String(64), nullable=True),
        sa.Column("row_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_agent_runtime_status", "agent_runtime", ["status"])

    # === agent_task (FK -> agent_runtime) ===
    op.create_table(
        "agent_task",
        sa.Column("task_id", sa.String(40), primary_key=True),
        sa.Column("agent_id", sa.String(64), sa.ForeignKey(_RUNTIME_FK), nullable=False),
        sa.Column("task_type", sa.String(64), nullable=False),
        sa.Column("title", sa.String(256), nullable=False),
        sa.Column("source", sa.String(64), nullable=False),
        sa.Column(
            "priority", enum_column(AgentTaskPriority, "agent_task_priority"), nullable=False
        ),
        sa.Column("status", enum_column(AgentTaskStatus, "agent_task_status"), nullable=False),
        sa.Column("stage", sa.String(64), nullable=True),
        sa.Column("progress", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("context_manifest_id", sa.String(40), nullable=True),
        sa.Column("parent_task_id", sa.String(40), nullable=True),
        sa.Column("waiting_reason", sa.String(256), nullable=True),
        sa.Column("failure_reason", sa.String(256), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_agent_task_agent", "agent_task", ["agent_id"])
    op.create_index("ix_agent_task_status", "agent_task", ["status"])

    # === task_directive (FK -> principals, agent_runtime) ===
    op.create_table(
        "task_directive",
        sa.Column("directive_id", sa.String(40), primary_key=True),
        sa.Column(
            "author_principal_id", sa.String(40), sa.ForeignKey(_PRINCIPAL_FK), nullable=False
        ),
        sa.Column("target_agent_id", sa.String(64), sa.ForeignKey(_RUNTIME_FK), nullable=False),
        sa.Column("related_task_id", sa.String(40), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column(
            "priority", enum_column(AgentTaskPriority, "task_directive_priority"), nullable=False
        ),
        sa.Column("status", enum_column(DirectiveStatus, "task_directive_status"), nullable=False),
        sa.Column("consumed_checkpoint_id", sa.String(40), nullable=True),
        sa.Column(
            "delivery_policy", sa.String(32), nullable=False, server_default="next_safe_checkpoint"
        ),
        sa.Column("correlation_id", sa.String(40), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_task_directive_author", "task_directive", ["author_principal_id"])
    op.create_index("ix_task_directive_target", "task_directive", ["target_agent_id"])
    op.create_index("ix_task_directive_status", "task_directive", ["status"])

    # === agent_checkpoint (FK -> agent_task) ===
    op.create_table(
        "agent_checkpoint",
        sa.Column("checkpoint_id", sa.String(40), primary_key=True),
        sa.Column(
            "task_id", sa.String(40), sa.ForeignKey(_TASK_FK, ondelete="CASCADE"), nullable=False
        ),
        sa.Column("checkpoint_no", sa.Integer(), nullable=False),
        sa.Column("stage", sa.String(64), nullable=False),
        sa.Column("state_ref", sa.String(128), nullable=True),
        sa.Column("context_manifest_id", sa.String(40), nullable=True),
        sa.Column("plan_revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("directive_cursor", sa.String(40), nullable=True),
        sa.Column("artifact_ids", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("task_id", "checkpoint_no", name="uq_agent_checkpoint_no"),
    )
    op.create_index("ix_agent_checkpoint_task", "agent_checkpoint", ["task_id"])

    # === lab_message (FK -> principals, agent_task) ===
    op.create_table(
        "lab_message",
        sa.Column("message_id", sa.String(40), primary_key=True),
        sa.Column("type", enum_column(LabMessageType, "lab_message_type"), nullable=False),
        sa.Column(
            "author_principal_id", sa.String(40), sa.ForeignKey(_PRINCIPAL_FK), nullable=True
        ),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column(
            "task_id", sa.String(40), sa.ForeignKey(_TASK_FK, ondelete="SET NULL"), nullable=True
        ),
        sa.Column("correlation_id", sa.String(40), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_lab_message_type", "lab_message", ["type"])
    op.create_index("ix_lab_message_created", "lab_message", ["created_at"])

    # === hypothesis_artifact (FK -> agent_task, principals) ===
    op.create_table(
        "hypothesis_artifact",
        sa.Column("artifact_id", sa.String(40), primary_key=True),
        sa.Column("status", enum_column(HypothesisStatus, "hypothesis_status"), nullable=False),
        sa.Column("title", sa.String(256), nullable=False),
        sa.Column("mechanism", sa.Text(), nullable=False),
        sa.Column("data_context", sa.Text(), nullable=True),
        sa.Column("evidence_refs", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("next_action", sa.Text(), nullable=True),
        sa.Column(
            "source_task_id",
            sa.String(40),
            sa.ForeignKey(_TASK_FK, ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("checkpoint_id", sa.String(40), nullable=True),
        sa.Column(
            "deletion_state",
            enum_column(DeletionState, "hypothesis_deletion_state"),
            nullable=False,
            server_default=DeletionState.ACTIVE.value,
        ),
        sa.Column(
            "created_by_principal_id", sa.String(40), sa.ForeignKey(_PRINCIPAL_FK), nullable=True
        ),
        sa.Column("correlation_id", sa.String(40), nullable=True),
        sa.Column("row_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_hypothesis_artifact_status", "hypothesis_artifact", ["status"])
    op.create_index("ix_hypothesis_artifact_source_task", "hypothesis_artifact", ["source_task_id"])
    op.create_index("ix_hypothesis_artifact_deletion", "hypothesis_artifact", ["deletion_state"])

    # === artifact_link (FK -> hypothesis_artifact) ===
    op.create_table(
        "artifact_link",
        sa.Column("link_id", sa.String(40), primary_key=True),
        sa.Column(
            "source_artifact_id",
            sa.String(40),
            sa.ForeignKey(_ARTIFACT_FK, ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("target_type", sa.String(64), nullable=False),
        sa.Column("target_id", sa.String(64), nullable=False),
        sa.Column("relation_type", sa.String(64), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_artifact_link_source", "artifact_link", ["source_artifact_id"])

    # === agent_event (FK -> principals, agent_task; seq Identity for SSE ordering) ===
    op.create_table(
        "agent_event",
        sa.Column("event_id", sa.String(40), primary_key=True),
        sa.Column("seq", sa.BigInteger(), sa.Identity(), nullable=False, unique=True),
        sa.Column("type", sa.String(64), nullable=False),
        sa.Column("actor_principal_id", sa.String(40), sa.ForeignKey(_PRINCIPAL_FK), nullable=True),
        sa.Column("actor_kind", enum_column(ActorKind, "agent_event_actor_kind"), nullable=False),
        sa.Column(
            "task_id", sa.String(40), sa.ForeignKey(_TASK_FK, ondelete="SET NULL"), nullable=True
        ),
        sa.Column("directive_id", sa.String(40), nullable=True),
        sa.Column("payload", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("correlation_id", sa.String(40), nullable=True),
        sa.Column(
            "occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_agent_event_seq", "agent_event", ["seq"])
    op.create_index("ix_agent_event_type", "agent_event", ["type"])
    op.create_index("ix_agent_event_task", "agent_event", ["task_id"])
    op.create_index("ix_agent_event_occurred", "agent_event", ["occurred_at"])

    # === Seed the singleton Alpha Agent runtime (doc 18 §5, §9) ===
    runtime = sa.table(
        "agent_runtime",
        sa.column("agent_id", sa.String),
        sa.column("mode", sa.String),
        sa.column("status", sa.String),
        sa.column("row_version", sa.Integer),
    )
    op.bulk_insert(
        runtime,
        [
            {
                "agent_id": ALPHA_AGENT_ID,
                "mode": RuntimeMode.CONTINUOUS.value,
                "status": RuntimeStatus.ACTIVE.value,
                "row_version": 1,
            }
        ],
    )


def downgrade() -> None:
    op.drop_table("agent_event")
    op.drop_table("artifact_link")
    op.drop_table("hypothesis_artifact")
    op.drop_table("lab_message")
    op.drop_table("agent_checkpoint")
    op.drop_table("task_directive")
    op.drop_table("agent_task")
    op.drop_table("agent_runtime")
