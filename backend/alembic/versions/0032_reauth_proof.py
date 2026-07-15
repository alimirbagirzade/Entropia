"""F-21 — real Trash re-authentication: short-lived, single-use proof tokens

Adds ``reauth_proofs`` (mirrors ``auth_sessions``): a human re-enters their
password via ``POST /auth/reauth`` and receives an opaque, purpose-scoped,
short-lived proof token. Only its SHA-256 digest is persisted. Permanent
Delete (``request_purge``) now verifies a real proof here instead of
accepting any non-empty string.

Revision ID: 0032_reauth_proof
Revises: 0031_package_import_job
Create Date: 2026-07-15
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0032_reauth_proof"
down_revision: str | None = "0031_package_import_job"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "reauth_proofs",
        sa.Column("proof_id", sa.String(40), primary_key=True),
        sa.Column("user_id", sa.String(40), sa.ForeignKey("human_users.user_id"), nullable=False),
        sa.Column("purpose", sa.String(64), nullable=False),
        sa.Column("proof_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("idx_reauth_proofs_user_id", "reauth_proofs", ["user_id"])


def downgrade() -> None:
    op.drop_index("idx_reauth_proofs_user_id", table_name="reauth_proofs")
    op.drop_table("reauth_proofs")
