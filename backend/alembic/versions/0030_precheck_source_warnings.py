"""S2 — Pre-Check source-scan warnings (doc 07 §6.2, PC-05/PC-06)

Additive, no backfill: the immutable ``dependency_scan`` evidence grows one
``source_warnings`` JSONB column so a scan self-carries the reconcile warnings
between the source-detected call set and the declared dependency list --
declared-but-not-found-in-source entries (over-declaration). Undeclared source
calls remain a Blocker and ride the existing ``missing_calls`` field; warnings
are non-fatal (the scan can still be PASSED) and must be pinned on the immutable
record rather than re-derived from the mutable request. Existing rows default to
``'[]'`` so history is unchanged.

Revision id kept <= 32 chars for ``alembic_version.version_num`` (varchar(32)).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0030_precheck_source_warnings"
down_revision: str | None = "0029_esp_validation_run"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "dependency_scan"
_COLUMN = "source_warnings"


def upgrade() -> None:
    op.add_column(
        _TABLE,
        sa.Column(
            _COLUMN,
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_column(_TABLE, _COLUMN)
