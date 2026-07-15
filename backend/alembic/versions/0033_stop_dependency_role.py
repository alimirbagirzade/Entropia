"""F-08 — Logic-Based Stop: widen strategy_dependency_role for stop pins

The ``dependency_role`` column of ``strategy_revision_references`` is a portable
VARCHAR sized (by ``enum_column``) to the longest ``DependencyRoleEnum`` value.
F-08 adds ``protection_stop_indicator`` / ``protection_stop_condition`` (25 chars)
so a Logic-Based Stop Block's pinned indicator/condition packages are recorded as
first-class dependency edges (validated active at save time, indexed, exported)
exactly like entry / exit / scaling blocks. The prior width (18 = len
``restriction_filter``) cannot hold the new values, so this widens the column to
VARCHAR(25). There is no CHECK constraint on the column (enum_column is
non-native and does not emit one here), so only the type width changes.

Revision ID: 0033_stop_dependency_role
Revises: 0032_reauth_proof
Create Date: 2026-07-15
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0033_stop_dependency_role"
down_revision: str | None = "0032_reauth_proof"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "strategy_revision_references"
_COLUMN = "dependency_role"


def upgrade() -> None:
    op.alter_column(
        _TABLE,
        _COLUMN,
        existing_type=sa.String(18),
        type_=sa.String(25),
        existing_nullable=False,
    )


def downgrade() -> None:
    # Reversible width restore. Forward-only in production once stop-role rows
    # exist (a longer value would not fit varchar(18)); the routine down is safe
    # on a schema with no protection-stop dependency rows yet.
    op.alter_column(
        _TABLE,
        _COLUMN,
        existing_type=sa.String(25),
        type_=sa.String(18),
        existing_nullable=False,
    )
