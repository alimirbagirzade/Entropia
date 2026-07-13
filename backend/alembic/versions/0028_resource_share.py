"""gap-17 — explicit resource share grants (Master Reference §6, §6.4)

Adds ``resource_share``: one row per active/revoked share grant that records
*who* a private resource is explicitly shared with. Before this table the
``explicitly_shared`` visibility state had no writer and no grantee list, so the
policy degenerated to "any authenticated actor may read it" — a latent
over-share. A grant is (resource_type, resource_id) -> grantee principal; a
partial unique index keeps at most one ACTIVE grant per (resource, grantee) so a
repeated share is idempotent. Revocation is a soft close (``revoked_at`` set), so
the grant history is auditable. V1 scope: ``resource_type = 'package'``; the
table is generic so later resources reuse it. Ownership never changes with a
share (Master §6.4).

Revision ID: 0028_resource_share
Revises: 0027_instrument_registry
Create Date: 2026-07-13
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0028_resource_share"
down_revision: str | None = "0027_instrument_registry"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PRINCIPAL_FK = "principals.principal_id"


def upgrade() -> None:
    op.create_table(
        "resource_share",
        sa.Column("share_id", sa.String(40), primary_key=True),
        sa.Column("resource_type", sa.String(32), nullable=False),
        sa.Column("resource_id", sa.String(40), nullable=False),
        sa.Column(
            "grantee_principal_id",
            sa.String(40),
            sa.ForeignKey(_PRINCIPAL_FK),
            nullable=False,
        ),
        sa.Column(
            "granted_by_principal_id",
            sa.String(40),
            sa.ForeignKey(_PRINCIPAL_FK),
            nullable=True,
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "revoked_by_principal_id",
            sa.String(40),
            sa.ForeignKey(_PRINCIPAL_FK),
            nullable=True,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    # At most one ACTIVE grant per (resource, grantee): a repeat share is
    # idempotent, and a revoked row never blocks a fresh re-share.
    op.create_index(
        "uq_resource_share_active_grant",
        "resource_share",
        ["resource_type", "resource_id", "grantee_principal_id"],
        unique=True,
        postgresql_where=sa.text("revoked_at IS NULL"),
    )
    # "shared with me": active grants for one grantee (partial — revoked rows skipped).
    op.create_index(
        "ix_resource_share_grantee_active",
        "resource_share",
        ["grantee_principal_id"],
        postgresql_where=sa.text("revoked_at IS NULL"),
    )
    # "grantees of this resource": active grants for one resource.
    op.create_index(
        "ix_resource_share_resource_active",
        "resource_share",
        ["resource_type", "resource_id"],
        postgresql_where=sa.text("revoked_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_resource_share_resource_active", table_name="resource_share")
    op.drop_index("ix_resource_share_grantee_active", table_name="resource_share")
    op.drop_index("uq_resource_share_active_grant", table_name="resource_share")
    op.drop_table("resource_share")
