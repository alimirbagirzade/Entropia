"""Portfolio-level rules: composition-wide Max Total Exposure + cross-item conflict policy

Two additive nullable columns on ``portfolio_allocation_plan`` (doc 13 §8.4 —
the portfolio plane is where cross-item rules live, mirroring the existing
plan-level draft fields 0012 created):

* ``max_total_exposure_percent`` NUMERIC(9,6) NULL — a composition-wide ceiling
  on total concurrent notional as a percent of the shared pool P0 (NULL = no
  cap; may exceed 100 for leveraged exposure, bounded at 999.999999 by the
  type). Today's caps are per-strategy only (doc 02 sizing) — this is the
  portfolio total.
* ``conflict_policy`` VARCHAR + CHECK (non-native ``enum_column``, identical to
  0012's compounding-mode pattern) NULL — the opposing same-instrument signal
  policy across items: NET | BLOCK_OPPOSITE | KEEP_SEPARATE (NULL =
  KEEP_SEPARATE, the pre-rules behaviour).

Both columns are nullable with no backfill, so existing plans keep their exact
behaviour (no cap, keep-separate). Downgrade drops the columns.

Revision ID: 0035_portfolio_rules
Revises: 0034_package_implementation
Create Date: 2026-07-19
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from entropia.domain.allocation.enums import CrossItemConflictPolicy
from entropia.infrastructure.postgres.types import enum_column

revision: str = "0035_portfolio_rules"
down_revision: str | None = "0034_package_implementation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "portfolio_allocation_plan"
_PERCENT = sa.Numeric(9, 6)


def upgrade() -> None:
    op.add_column(
        _TABLE,
        sa.Column("max_total_exposure_percent", _PERCENT, nullable=True),
    )
    op.add_column(
        _TABLE,
        sa.Column(
            "conflict_policy",
            enum_column(CrossItemConflictPolicy, "allocation_conflict_policy"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column(_TABLE, "conflict_policy")
    op.drop_column(_TABLE, "max_total_exposure_percent")
