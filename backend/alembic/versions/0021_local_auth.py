"""post-V1 — local auth (M1 §4 / Master §20)

Two tables: human_credentials (one argon2id hash per human user; secrets live
apart from the user root) and auth_sessions (server-side revocable sessions;
only a SHA-256 digest of the opaque Bearer token is stored — never the token).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0021_local_auth"
down_revision: str | None = "0020_future_dev"
branch_labels: None = None
depends_on: None = None


def upgrade() -> None:
    op.create_table(
        "human_credentials",
        sa.Column(
            "user_id",
            sa.String(40),
            sa.ForeignKey("human_users.user_id"),
            primary_key=True,
        ),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("algorithm", sa.String(32), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )

    op.create_table(
        "auth_sessions",
        sa.Column("session_id", sa.String(40), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(40),
            sa.ForeignKey("human_users.user_id"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("idx_auth_sessions_user_id", "auth_sessions", ["user_id"])


def downgrade() -> None:
    op.drop_index("idx_auth_sessions_user_id", table_name="auth_sessions")
    op.drop_table("auth_sessions")
    op.drop_table("human_credentials")
