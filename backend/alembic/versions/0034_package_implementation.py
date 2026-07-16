"""F-14 — real candidate/package generation: store the loadable implementation

Adds two additive nullable JSONB columns so a generated candidate carries a real,
loadable implementation (not just a hash):

* ``package_request.candidate_implementation`` — the generated implementation set at
  candidate-generation time (source, entry symbol, plan, executable flag, provenance).
* ``package_revision.implementation`` — the immutable copy pinned onto the draft
  revision at C.D.P, so the resolver/validation sandbox loads a real artifact and a
  hash-without-implementation can never reach approval.

Both are nullable (pre-F-14 rows carry ``NULL``); no backfill.

Revision ID: 0034_package_implementation
Revises: 0033_stop_dependency_role
Create Date: 2026-07-16
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0034_package_implementation"
down_revision: str | None = "0033_stop_dependency_role"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "package_request",
        sa.Column("candidate_implementation", postgresql.JSONB(), nullable=True),
    )
    op.add_column(
        "package_revision",
        sa.Column("implementation", postgresql.JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("package_revision", "implementation")
    op.drop_column("package_request", "candidate_implementation")
