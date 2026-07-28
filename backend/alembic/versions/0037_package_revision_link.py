"""O-08 — Request Revision parent link: revision chain head pins + append-only ledger

Request Revision (doc 06 §7 "Creates immutable next attempt linked to parent revision
and prior validation summary"; §15 acceptance "Revision immutability") cleared the
request's draft head pointers and kept NO reference to the attempt it descended from,
so the chain broke at the first revision. This migration adds the storage the link
needs:

* ``package_request.revision_attempt_no`` INTEGER NOT NULL DEFAULT 1 — the attempt the
  request is ON (1 = the original attempt, so existing rows are correct with no
  backfill), ``parent_revision_ref`` / ``prior_validation_run_ref`` VARCHAR(40) NULL —
  the prior attempt's draft revision + validation run, pinned before the head clears.
* ``package_revision_link`` — the append-only chain ledger (one row per Request
  Revision). The head pins alone would collapse to one level on a second revision;
  these rows keep every attempt's own parent, and are never UPDATEd.

No behaviour lives here; ``commands.create_package.request_package_revision`` writes
these and ``queries.create_package.get_package_request`` projects them. Mirrors the
``package_validation_run`` immutable-evidence shape (0025 / 0031). Downgrade drops the
table and the three columns.

Revision ID: 0037_package_revision_link
Revises: 0036_manual_duplicate_override
Create Date: 2026-07-27
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from entropia.domain.create_package.enums import CreatePackageState
from entropia.infrastructure.postgres.types import enum_column

revision: str = "0037_package_revision_link"
down_revision: str | None = "0036_manual_duplicate_override"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_REQUEST_TABLE = "package_request"
_LINK_TABLE = "package_revision_link"
_ENTITY_FK = "entity_registry.entity_id"
_PRINCIPAL_FK = "principals.principal_id"


def upgrade() -> None:
    op.add_column(
        _REQUEST_TABLE,
        sa.Column("revision_attempt_no", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        _REQUEST_TABLE,
        sa.Column("parent_revision_ref", sa.String(40), nullable=True),
    )
    op.add_column(
        _REQUEST_TABLE,
        sa.Column("prior_validation_run_ref", sa.String(40), nullable=True),
    )
    op.create_table(
        _LINK_TABLE,
        sa.Column("revision_link_id", sa.String(40), primary_key=True),
        sa.Column("request_entity_id", sa.String(40), sa.ForeignKey(_ENTITY_FK), nullable=False),
        sa.Column("attempt_no", sa.Integer(), nullable=False),
        sa.Column("parent_package_root_id", sa.String(40), nullable=True),
        sa.Column("parent_revision_ref", sa.String(40), nullable=True),
        sa.Column("prior_validation_run_ref", sa.String(40), nullable=True),
        sa.Column("prior_candidate_hash", sa.String(80), nullable=True),
        sa.Column(
            "prior_state",
            enum_column(CreatePackageState, "create_package_state"),
            nullable=False,
        ),
        sa.Column("correlation_id", sa.String(64), nullable=True),
        sa.Column(
            "created_by_principal_id", sa.String(40), sa.ForeignKey(_PRINCIPAL_FK), nullable=True
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint(
            "request_entity_id", "attempt_no", name="uq_package_revision_link_attempt"
        ),
    )
    op.create_index(
        "ix_package_revision_link_request_entity_id",
        _LINK_TABLE,
        ["request_entity_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_package_revision_link_request_entity_id", table_name=_LINK_TABLE)
    op.drop_table(_LINK_TABLE)
    op.drop_column(_REQUEST_TABLE, "prior_validation_run_ref")
    op.drop_column(_REQUEST_TABLE, "parent_revision_ref")
    op.drop_column(_REQUEST_TABLE, "revision_attempt_no")
