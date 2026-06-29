"""stage 1 — common system foundation tables

Identity (principals/human_users/agents), generic root/revision registry,
audit + outbox, trash + tombstones, durable jobs + idempotency keys.

Revision ID: 0002_stage1
Revises: 0001_initial
Create Date: 2026-06-29
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from entropia.domain.lifecycle.enums import (
    ActorKind,
    DeletionState,
    JobStatus,
    PrincipalType,
    Role,
    ValidationStatus,
)
from entropia.infrastructure.postgres.types import enum_column

revision: str = "0002_stage1"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "principals",
        sa.Column("principal_id", sa.String(40), primary_key=True),
        sa.Column("principal_type", enum_column(PrincipalType, "principal_type"), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )

    op.create_table(
        "human_users",
        sa.Column(
            "user_id", sa.String(40), sa.ForeignKey("principals.principal_id"), primary_key=True
        ),
        sa.Column("username", sa.String(128), nullable=False, unique=True),
        sa.Column("email", sa.String(320), nullable=True, unique=True),
        sa.Column("display_name", sa.String(256), nullable=False),
        sa.Column("current_role", enum_column(Role, "role"), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("role_changed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("role_changed_by", sa.String(40), nullable=True),
        sa.Column(
            "deletion_state",
            enum_column(DeletionState, "deletion_state"),
            nullable=False,
            server_default="active",
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", sa.String(40), nullable=True),
        sa.Column("delete_reason", sa.String(512), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )

    op.create_table(
        "agents",
        sa.Column(
            "agent_id", sa.String(40), sa.ForeignKey("principals.principal_id"), primary_key=True
        ),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )

    op.create_table(
        "entity_registry",
        sa.Column("entity_id", sa.String(40), primary_key=True),
        sa.Column("entity_type", sa.String(64), nullable=False),
        sa.Column("owner_principal_id", sa.String(40), nullable=True),
        sa.Column("created_by_principal_id", sa.String(40), nullable=True),
        sa.Column("lifecycle_state", sa.String(48), nullable=True),
        sa.Column(
            "deletion_state",
            enum_column(DeletionState, "deletion_state"),
            nullable=False,
            server_default="active",
        ),
        sa.Column("current_revision_id", sa.String(40), nullable=True),
        sa.Column("row_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", sa.String(40), nullable=True),
        sa.Column("delete_reason", sa.String(512), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_entity_registry_entity_type", "entity_registry", ["entity_type"])
    op.create_index(
        "ix_entity_registry_owner_principal_id", "entity_registry", ["owner_principal_id"]
    )
    op.create_index("ix_entity_registry_deletion_state", "entity_registry", ["deletion_state"])

    op.create_table(
        "entity_revisions",
        sa.Column("revision_id", sa.String(40), primary_key=True),
        sa.Column(
            "entity_id", sa.String(40), sa.ForeignKey("entity_registry.entity_id"), nullable=False
        ),
        sa.Column("revision_no", sa.Integer(), nullable=False),
        sa.Column("parent_revision_id", sa.String(40), nullable=True),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("created_by_principal_id", sa.String(40), nullable=True),
        sa.Column(
            "validation_status", enum_column(ValidationStatus, "validation_status"), nullable=True
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("entity_id", "revision_no", name="uq_entity_revision_no"),
    )
    op.create_index("ix_entity_revisions_entity_id", "entity_revisions", ["entity_id"])

    op.create_table(
        "audit_events",
        sa.Column("event_id", sa.String(40), primary_key=True),
        sa.Column(
            "occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("event_kind", sa.String(96), nullable=False),
        sa.Column("severity", sa.String(16), nullable=False, server_default="info"),
        sa.Column("actor_principal_id", sa.String(40), nullable=True),
        sa.Column("actor_kind", enum_column(ActorKind, "actor_kind"), nullable=False),
        sa.Column("target_entity_id", sa.String(40), nullable=True),
        sa.Column("target_entity_type", sa.String(64), nullable=True),
        sa.Column("target_revision_id", sa.String(40), nullable=True),
        sa.Column("previous_state", sa.String(48), nullable=True),
        sa.Column("new_state", sa.String(48), nullable=True),
        sa.Column("correlation_id", sa.String(40), nullable=True),
        sa.Column("causation_event_id", sa.String(40), nullable=True),
        sa.Column("reason", sa.String(512), nullable=True),
        sa.Column("source_task_id", sa.String(40), nullable=True),
        sa.Column("source_run_id", sa.String(40), nullable=True),
        sa.Column("payload_hash_before", sa.String(64), nullable=True),
        sa.Column("payload_hash_after", sa.String(64), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
    )
    op.create_index("ix_audit_events_log_order", "audit_events", ["occurred_at", "event_id"])
    op.create_index("ix_audit_events_target", "audit_events", ["target_entity_id"])

    op.create_table(
        "outbox_events",
        sa.Column("id", sa.String(40), primary_key=True),
        sa.Column("event_type", sa.String(96), nullable=False),
        sa.Column("resource_type", sa.String(64), nullable=True),
        sa.Column("resource_id", sa.String(40), nullable=True),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("correlation_id", sa.String(40), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_outbox_unpublished", "outbox_events", ["published_at"])

    op.create_table(
        "trash_entries",
        sa.Column("id", sa.String(40), primary_key=True),
        sa.Column("entity_id", sa.String(40), nullable=False),
        sa.Column("entity_type", sa.String(64), nullable=False),
        sa.Column("deleted_by", sa.String(40), nullable=True),
        sa.Column(
            "deleted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("reason", sa.String(512), nullable=True),
        sa.Column("owner_at_deletion", sa.String(40), nullable=True),
        sa.Column("dependency_snapshot", postgresql.JSONB(), nullable=True),
    )
    op.create_index("ix_trash_entries_entity_id", "trash_entries", ["entity_id"])

    op.create_table(
        "tombstones",
        sa.Column("entity_id", sa.String(40), primary_key=True),
        sa.Column("entity_type", sa.String(64), nullable=False),
        sa.Column(
            "purged_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("purged_by", sa.String(40), nullable=True),
    )

    op.create_table(
        "jobs",
        sa.Column("job_id", sa.String(40), primary_key=True),
        sa.Column("queue", sa.String(32), nullable=False),
        sa.Column(
            "status", enum_column(JobStatus, "job_status"), nullable=False, server_default="queued"
        ),
        sa.Column("actor_principal_id", sa.String(40), nullable=True),
        sa.Column("idempotency_key", sa.String(128), nullable=True),
        sa.Column("payload", postgresql.JSONB(), nullable=True),
        sa.Column("result_ref", postgresql.JSONB(), nullable=True),
        sa.Column("correlation_id", sa.String(40), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_jobs_idempotency_key", "jobs", ["idempotency_key"])
    op.create_index("ix_jobs_queue_status", "jobs", ["queue", "status"])
    op.create_index("ix_jobs_stale_running", "jobs", ["status", "claimed_at"])

    op.create_table(
        "idempotency_keys",
        sa.Column("key", sa.String(128), primary_key=True),
        sa.Column("actor_principal_id", sa.String(40), nullable=True),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("response_ref", postgresql.JSONB(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="in_progress"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )


def downgrade() -> None:
    op.drop_table("idempotency_keys")
    op.drop_table("jobs")
    op.drop_table("tombstones")
    op.drop_table("trash_entries")
    op.drop_table("outbox_events")
    op.drop_table("audit_events")
    op.drop_table("entity_revisions")
    op.drop_table("entity_registry")
    op.drop_table("agents")
    op.drop_table("human_users")
    op.drop_table("principals")
