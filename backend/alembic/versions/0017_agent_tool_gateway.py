"""stage 6a-2 — Tool Gateway durable tool-call record (doc 18 §9.2)

One ``agent_tool_call`` table: the durable envelope for every UI-less agent tool
invocation (actor_context, task_id, checkpoint_id, input_manifest_id,
idempotency_key, policy_scope, artifact_output_ref). ``idempotency_key`` is UNIQUE
so a redelivered call replays its recorded outcome (AL-14). Enum columns are
VARCHAR + CHECK (enum_column, no CREATE TYPE), mirroring 0016.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from entropia.domain.agent_lab.tool_gateway import PolicyScope, ToolCallStatus
from entropia.domain.lifecycle.enums import ActorKind
from entropia.infrastructure.postgres.types import enum_column

revision: str = "0017_agent_tool_gateway"
down_revision: str | None = "0016_analysis_lab"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PRINCIPAL_FK = "principals.principal_id"
_RUNTIME_FK = "agent_runtime.agent_id"
_TASK_FK = "agent_task.task_id"


def upgrade() -> None:
    op.create_table(
        "agent_tool_call",
        sa.Column("tool_call_id", sa.String(40), primary_key=True),
        sa.Column("tool_name", sa.String(64), nullable=False),
        sa.Column("agent_id", sa.String(64), sa.ForeignKey(_RUNTIME_FK), nullable=False),
        sa.Column("actor_principal_id", sa.String(40), sa.ForeignKey(_PRINCIPAL_FK), nullable=True),
        sa.Column(
            "actor_kind",
            enum_column(ActorKind, "agent_tool_call_actor_kind"),
            nullable=False,
        ),
        sa.Column(
            "task_id", sa.String(40), sa.ForeignKey(_TASK_FK, ondelete="SET NULL"), nullable=True
        ),
        sa.Column("checkpoint_id", sa.String(40), nullable=True),
        sa.Column("input_manifest_id", sa.String(40), nullable=True),
        sa.Column("idempotency_key", sa.String(80), nullable=True),
        sa.Column(
            "policy_scope",
            enum_column(PolicyScope, "agent_tool_call_policy_scope"),
            nullable=False,
        ),
        sa.Column("status", enum_column(ToolCallStatus, "agent_tool_call_status"), nullable=False),
        sa.Column("artifact_output_ref", sa.String(64), nullable=True),
        sa.Column("request", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("response_ref", postgresql.JSONB(), nullable=True),
        sa.Column("failure_code", sa.String(64), nullable=True),
        sa.Column("failure_message", sa.String(256), nullable=True),
        sa.Column("correlation_id", sa.String(40), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("idempotency_key", name="uq_agent_tool_call_idem"),
    )
    op.create_index("ix_agent_tool_call_tool_name", "agent_tool_call", ["tool_name"])
    op.create_index("ix_agent_tool_call_agent", "agent_tool_call", ["agent_id"])
    op.create_index("ix_agent_tool_call_task", "agent_tool_call", ["task_id"])
    op.create_index("ix_agent_tool_call_status", "agent_tool_call", ["status"])


def downgrade() -> None:
    op.drop_table("agent_tool_call")
