"""Filtered Events as their own result artifact + per-artifact checksums

I-02. Doc 15 §3.2's "Research Data / Agent Data" row lists five actions; "View
Filtered Events" and "View Regime Table" were never wired. §16 requires the
no-entry/filtered decision trace stay readable and not be forced into the shape
of a real fill, and §8.3 says the worker persists the artifacts *with their
checksums*. Before this slice the engine's ``filtered_no_entry`` vetoes were
appended into the SAME ``signal_event`` journal as fills and order events, and
no artifact checksum was stored anywhere.

Two new INSERT-only tables:

* ``filtered_event`` — the filter-veto trace, same shape as ``signal_event`` and
  deliberately a separate table rather than a flag on it, because the two are
  two distinct drill-downs with independent ``seq`` sequences:
  ``filtered_event_id`` VARCHAR(40) PK; ``result_id`` VARCHAR(40) NOT NULL FK ->
  ``backtest_result.result_id`` ON DELETE CASCADE, indexed (L1 parent-before-child
  is enforced by the database, the same pattern the other result children use);
  ``seq`` INTEGER NOT NULL; ``event_time`` VARCHAR(32) NOT NULL; ``event_type``
  VARCHAR(32) NOT NULL; ``direction`` VARCHAR(8) NULL; ``detail`` JSONB NULL;
  ``UNIQUE(result_id, seq)`` so the keyset cursor can never skip or double-count.

* ``result_artifact_checksum`` — one content checksum per (result, artifact
  type), covering EVERY queryable artifact rather than only the new one:
  ``checksum_id`` VARCHAR(40) PK; ``result_id`` FK -> ``backtest_result`` ON
  DELETE CASCADE, indexed; ``artifact_type`` VARCHAR(32); ``row_count`` INTEGER;
  ``checksum`` VARCHAR(64); ``schema_version`` VARCHAR(32);
  ``UNIQUE(result_id, artifact_type)``.

Additive only — no existing table or column is touched. Results materialized
before this migration keep their exact rows; they simply carry no filtered-event
and no checksum rows, and the drill-down reports ``checksum: null`` for them
rather than inventing one. Downgrade drops both tables.

Revision ID: 0041_filtered_event_artifact
Revises: 0040_export_type_agent_pine
Create Date: 2026-07-28
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0041_filtered_event_artifact"
down_revision: str | None = "0040_export_type_agent_pine"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_EVENTS = "filtered_event"
_CHECKSUMS = "result_artifact_checksum"
_RESULT_FK = "backtest_result.result_id"


def upgrade() -> None:
    op.create_table(
        _EVENTS,
        sa.Column("filtered_event_id", sa.String(40), primary_key=True),
        sa.Column(
            "result_id",
            sa.String(40),
            sa.ForeignKey(_RESULT_FK, ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("event_time", sa.String(32), nullable=False),
        sa.Column("event_type", sa.String(32), nullable=False),
        sa.Column("direction", sa.String(8), nullable=True),
        sa.Column("detail", postgresql.JSONB(), nullable=True),
        sa.UniqueConstraint("result_id", "seq", name="uq_filtered_event_seq"),
    )
    op.create_index(f"ix_{_EVENTS}_result_id", _EVENTS, ["result_id"])

    op.create_table(
        _CHECKSUMS,
        sa.Column("checksum_id", sa.String(40), primary_key=True),
        sa.Column(
            "result_id",
            sa.String(40),
            sa.ForeignKey(_RESULT_FK, ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("artifact_type", sa.String(32), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("checksum", sa.String(64), nullable=False),
        sa.Column("schema_version", sa.String(32), nullable=False),
        sa.UniqueConstraint("result_id", "artifact_type", name="uq_result_artifact_checksum"),
    )
    op.create_index(f"ix_{_CHECKSUMS}_result_id", _CHECKSUMS, ["result_id"])


def downgrade() -> None:
    op.drop_index(f"ix_{_CHECKSUMS}_result_id", table_name=_CHECKSUMS)
    op.drop_table(_CHECKSUMS)
    op.drop_index(f"ix_{_EVENTS}_result_id", table_name=_EVENTS)
    op.drop_table(_EVENTS)
