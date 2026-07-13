"""r8 — ESP resolver validation-run evidence plane

Adds the INSERT-only immutable ``embedded_resolver_validation_run`` table. Each run
records the terminal ``status`` (a ``package_validation_state`` value) its stored
test-vectors certified, the ``validator_version`` namespace, the number of vectors run
and the per-check breakdown. No behaviour lives here; the ``run_resolver_validation``
command drives these rows + copies ``status`` onto ``revision.validation_state``, and the
activation gate then requires ``passed`` (post-V1 R8, doc 09 §11.1). Mirrors the market/
research ``*_validation_run`` and the ``package_validation_run`` (0025) immutable-evidence
shape.

Revision ID: 0029_esp_validation_run
Revises: 0028_resource_share
Create Date: 2026-07-13
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from entropia.domain.package.enums import PackageValidationState
from entropia.infrastructure.postgres.types import enum_column

revision: str = "0029_esp_validation_run"
down_revision: str | None = "0028_resource_share"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ENTITY_FK = "entity_registry.entity_id"
_PRINCIPAL_FK = "principals.principal_id"


def upgrade() -> None:
    op.create_table(
        "embedded_resolver_validation_run",
        sa.Column("run_id", sa.String(40), primary_key=True),
        sa.Column("entity_id", sa.String(40), sa.ForeignKey(_ENTITY_FK), nullable=False),
        sa.Column("revision_id", sa.String(40), nullable=False),
        sa.Column("canonical_key", sa.String(128), nullable=False),
        sa.Column(
            "status",
            enum_column(PackageValidationState, "package_validation_state"),
            nullable=False,
        ),
        sa.Column("validator_version", sa.String(64), nullable=False),
        sa.Column("vectors_run", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("checks", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_by_principal_id", sa.String(40), sa.ForeignKey(_PRINCIPAL_FK), nullable=True
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index(
        "ix_embedded_resolver_validation_run_entity_id",
        "embedded_resolver_validation_run",
        ["entity_id"],
    )
    op.create_index(
        "ix_embedded_resolver_validation_run_revision_id",
        "embedded_resolver_validation_run",
        ["revision_id"],
    )
    op.create_index(
        "ix_embedded_resolver_validation_run_canonical_key",
        "embedded_resolver_validation_run",
        ["canonical_key"],
    )


def downgrade() -> None:
    op.drop_table("embedded_resolver_validation_run")
