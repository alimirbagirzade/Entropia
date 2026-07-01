"""stage 6c — Trash page contract columns on trash_entries (doc 20 §4, §5, §9.1)

No new table: the Stage-1 ``trash_entries`` record grows the Admin page-contract
fields — immutable deletion snapshot (display name, original location, redacted
snapshot JSONB), the entry ``status`` overlay (soft_deleted / restored /
purge_pending / purge_failed / purged), the Trash OCC token ``row_version``
(``expected_head_revision_id``), purge-job linkage and restore evidence. Enum is
VARCHAR (enum_column, no CREATE TYPE), mirroring 0016/0017. Keyset index
``(deleted_at, id)`` backs the stable ``deleted_at DESC, id DESC`` cursor sort
(doc 20 §13 gap resolution).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from entropia.domain.trash.page import TrashEntryStatus
from entropia.infrastructure.postgres.types import enum_column

revision: str = "0018_trash_page"
down_revision: str | None = "0017_agent_tool_gateway"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "trash_entries"


def upgrade() -> None:
    op.add_column(_TABLE, sa.Column("display_name", sa.String(200), nullable=True))
    op.add_column(_TABLE, sa.Column("original_location", sa.String(120), nullable=True))
    op.add_column(_TABLE, sa.Column("deletion_snapshot", postgresql.JSONB(), nullable=True))
    op.add_column(
        _TABLE,
        sa.Column(
            "status",
            enum_column(TrashEntryStatus, "trash_entry_status"),
            nullable=False,
            server_default=TrashEntryStatus.SOFT_DELETED.value,
        ),
    )
    op.add_column(
        _TABLE,
        sa.Column("row_version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(_TABLE, sa.Column("purge_job_id", sa.String(40), nullable=True))
    op.add_column(_TABLE, sa.Column("purge_error", sa.String(200), nullable=True))
    op.add_column(_TABLE, sa.Column("purge_requested_by", sa.String(40), nullable=True))
    op.add_column(_TABLE, sa.Column("correlation_id", sa.String(64), nullable=True))
    op.add_column(_TABLE, sa.Column("restored_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(_TABLE, sa.Column("restored_by", sa.String(40), nullable=True))
    op.create_index(
        "ix_trash_entries_deleted_at_id",
        _TABLE,
        [sa.text("deleted_at DESC"), sa.text("id DESC")],
    )
    op.create_index("ix_trash_entries_status", _TABLE, ["status"])
    op.create_index("ix_trash_entries_entity_type", _TABLE, ["entity_type"])


def downgrade() -> None:
    op.drop_index("ix_trash_entries_entity_type", table_name=_TABLE)
    op.drop_index("ix_trash_entries_status", table_name=_TABLE)
    op.drop_index("ix_trash_entries_deleted_at_id", table_name=_TABLE)
    op.drop_column(_TABLE, "restored_by")
    op.drop_column(_TABLE, "restored_at")
    op.drop_column(_TABLE, "correlation_id")
    op.drop_column(_TABLE, "purge_requested_by")
    op.drop_column(_TABLE, "purge_error")
    op.drop_column(_TABLE, "purge_job_id")
    op.drop_column(_TABLE, "row_version")
    op.drop_column(_TABLE, "status")
    op.drop_column(_TABLE, "deletion_snapshot")
    op.drop_column(_TABLE, "original_location")
    op.drop_column(_TABLE, "display_name")
