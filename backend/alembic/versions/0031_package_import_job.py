"""S3 — package import job durable projection + import provenance

The reverse of package Export (doc 08 §9.1/§10/§14, master ref Modül 7 §12). Adds:

* ``package_root.origin_package_id`` — import provenance: the foreign export
  manifest's ``package_root_id`` this local DRAFT root was created from (NULL for
  natively-authored roots).
* ``package_import_job`` — the durable append-then-terminal import-job projection
  the Library Import report reads. A worker parses a submitted manifest, re-resolves
  its dependencies and either creates a clean DRAFT root (``succeeded``) or a
  FAILED-validation DRAFT root with the missing calls in ``diagnostics`` (``blocked``
  — never silently executable); a structurally-unparseable manifest is ``failed``.

No behaviour lives here; the SubmitPackageImport command + the worker drive these.
Mirrors the ``package_validation_run`` immutable-evidence shape (0025).

Revision ID: 0031_package_import_job
Revises: 0030_precheck_source_warnings
Create Date: 2026-07-14
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from entropia.domain.create_package.enums import PackageImportStatus
from entropia.domain.lifecycle.enums import PackageKind
from entropia.infrastructure.postgres.types import enum_column

revision: str = "0031_package_import_job"
down_revision: str | None = "0030_precheck_source_warnings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PRINCIPAL_FK = "principals.principal_id"


def upgrade() -> None:
    op.add_column(
        "package_root",
        sa.Column("origin_package_id", sa.String(40), nullable=True),
    )
    op.create_table(
        "package_import_job",
        sa.Column("import_job_id", sa.String(40), primary_key=True),
        sa.Column("manifest_hash", sa.String(64), nullable=False),
        sa.Column("origin_package_id", sa.String(40), nullable=True),
        sa.Column("origin_revision_id", sa.String(40), nullable=True),
        sa.Column("package_kind", enum_column(PackageKind, "package_kind"), nullable=False),
        sa.Column("result_package_root_id", sa.String(40), nullable=True),
        sa.Column(
            "status",
            enum_column(PackageImportStatus, "package_import_status"),
            nullable=False,
            server_default="queued",
        ),
        sa.Column("diagnostics", postgresql.JSONB(), nullable=True),
        sa.Column("job_id", sa.String(40), nullable=True),
        sa.Column("correlation_id", sa.String(64), nullable=True),
        sa.Column(
            "created_by_principal_id", sa.String(40), sa.ForeignKey(_PRINCIPAL_FK), nullable=True
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index(
        "ix_package_import_job_created_by",
        "package_import_job",
        ["created_by_principal_id"],
    )
    op.create_index("ix_package_import_job_status", "package_import_job", ["status"])


def downgrade() -> None:
    op.drop_index("ix_package_import_job_status", table_name="package_import_job")
    op.drop_index("ix_package_import_job_created_by", table_name="package_import_job")
    op.drop_table("package_import_job")
    op.drop_column("package_root", "origin_package_id")
