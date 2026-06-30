"""stage 2c — ESP shared package model + resolver registry

Shared package tables (``package_root`` detail + INSERT-only ``package_revision``)
hung off entity_registry, plus the ESP resolver registry: per-revision
``embedded_resolver_contract`` and the canonical_key -> trusted pointer
``embedded_resolver_registry``.

Revision ID: 0005_esp_packages
Revises: 0004_research_data
Create Date: 2026-06-30
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from entropia.domain.esp.enums import ResolverTrustState, RuntimeAdapter
from entropia.domain.lifecycle.enums import ApprovalState, PackageKind, VisibilityScope
from entropia.domain.package.enums import PackageValidationState
from entropia.infrastructure.postgres.types import enum_column

revision: str = "0005_esp_packages"
down_revision: str | None = "0004_research_data"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ENTITY_FK = "entity_registry.entity_id"
_PRINCIPAL_FK = "principals.principal_id"


def upgrade() -> None:
    op.create_table(
        "package_root",
        sa.Column("entity_id", sa.String(40), sa.ForeignKey(_ENTITY_FK), primary_key=True),
        sa.Column("package_kind", enum_column(PackageKind, "package_kind"), nullable=False),
        sa.Column(
            "visibility_scope",
            enum_column(VisibilityScope, "visibility_scope"),
            nullable=False,
            server_default="private",
        ),
        sa.Column("derived_from_revision_id", sa.String(40), nullable=True),
    )
    op.create_index("ix_package_root_package_kind", "package_root", ["package_kind"])
    op.create_index("ix_package_root_visibility_scope", "package_root", ["visibility_scope"])

    op.create_table(
        "package_revision",
        sa.Column("revision_id", sa.String(40), primary_key=True),
        sa.Column("entity_id", sa.String(40), sa.ForeignKey(_ENTITY_FK), nullable=False),
        sa.Column("revision_no", sa.Integer(), nullable=False),
        sa.Column("parent_revision_id", sa.String(40), nullable=True),
        sa.Column("supersedes_revision_id", sa.String(40), nullable=True),
        sa.Column("package_kind", enum_column(PackageKind, "package_kind"), nullable=False),
        sa.Column("input_contract", postgresql.JSONB(), nullable=False),
        sa.Column("output_contract", postgresql.JSONB(), nullable=False),
        sa.Column("dependency_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("rationale_family_snapshot", postgresql.JSONB(), nullable=True),
        sa.Column(
            "validation_state",
            enum_column(PackageValidationState, "package_validation_state"),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "approval_state",
            enum_column(ApprovalState, "package_approval_state"),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("validation_summary", postgresql.JSONB(), nullable=True),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("change_note", sa.String(1024), nullable=True),
        sa.Column(
            "created_by_principal_id", sa.String(40), sa.ForeignKey(_PRINCIPAL_FK), nullable=True
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("entity_id", "revision_no", name="uq_package_revision_no"),
    )
    op.create_index("ix_package_revision_entity_id", "package_revision", ["entity_id"])
    op.create_index("ix_package_revision_package_kind", "package_revision", ["package_kind"])
    op.create_index(
        "ix_package_revision_validation_state", "package_revision", ["validation_state"]
    )
    op.create_index("ix_package_revision_approval_state", "package_revision", ["approval_state"])

    op.create_table(
        "embedded_resolver_contract",
        sa.Column("contract_id", sa.String(40), primary_key=True),
        sa.Column("entity_id", sa.String(40), sa.ForeignKey(_ENTITY_FK), nullable=False),
        sa.Column("revision_id", sa.String(40), nullable=False),
        sa.Column("canonical_key", sa.String(128), nullable=False),
        sa.Column("signature", postgresql.JSONB(), nullable=False),
        sa.Column(
            "runtime_adapter", enum_column(RuntimeAdapter, "runtime_adapter"), nullable=False
        ),
        sa.Column("warm_up_period", sa.Integer(), nullable=True),
        sa.Column("timing_semantics", sa.String(256), nullable=True),
        sa.Column("repaint", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("evidence", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("revision_id", name="uq_embedded_resolver_contract_revision"),
    )
    op.create_index(
        "ix_embedded_resolver_contract_entity_id", "embedded_resolver_contract", ["entity_id"]
    )
    op.create_index(
        "ix_embedded_resolver_contract_revision_id", "embedded_resolver_contract", ["revision_id"]
    )
    op.create_index(
        "ix_embedded_resolver_contract_canonical_key",
        "embedded_resolver_contract",
        ["canonical_key"],
    )

    op.create_table(
        "embedded_resolver_registry",
        sa.Column("registry_id", sa.String(40), primary_key=True),
        sa.Column("canonical_key", sa.String(128), nullable=False),
        sa.Column("package_entity_id", sa.String(40), sa.ForeignKey(_ENTITY_FK), nullable=False),
        sa.Column("trusted_active_revision_id", sa.String(40), nullable=True),
        sa.Column(
            "trust_state",
            enum_column(ResolverTrustState, "resolver_trust_state"),
            nullable=False,
            server_default="candidate",
        ),
        sa.Column(
            "runtime_adapter", enum_column(RuntimeAdapter, "runtime_adapter"), nullable=False
        ),
        sa.Column("registry_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("replacement_revision_id", sa.String(40), nullable=True),
        sa.Column(
            "updated_by_principal_id", sa.String(40), sa.ForeignKey(_PRINCIPAL_FK), nullable=True
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("canonical_key", name="uq_embedded_resolver_registry_key"),
    )
    op.create_index(
        "ix_embedded_resolver_registry_canonical_key",
        "embedded_resolver_registry",
        ["canonical_key"],
    )
    op.create_index(
        "ix_embedded_resolver_registry_package_entity_id",
        "embedded_resolver_registry",
        ["package_entity_id"],
    )
    op.create_index(
        "ix_embedded_resolver_registry_trust_state",
        "embedded_resolver_registry",
        ["trust_state"],
    )


def downgrade() -> None:
    op.drop_table("embedded_resolver_registry")
    op.drop_table("embedded_resolver_contract")
    op.drop_table("package_revision")
    op.drop_table("package_root")
