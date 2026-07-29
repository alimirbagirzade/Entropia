"""Widen export_artifact.export_type for the two doc 15 §3.2 types

S-L2. ``ExportType`` gains ``pinescript_signal_marker`` and ``agent_dataset``
(doc 15 §3.2 Data Export + Research Data / Agent Data rows).

``export_artifact.export_type`` is a NON-native SQLAlchemy enum
(``types.enum_column`` -> ``SAEnum(native_enum=False)``), so on Postgres it is a
plain ``VARCHAR(n)`` where ``n`` is the longest member's length — not a PG ENUM
type and, since SQLAlchemy 2.0 defaults ``create_constraint=False``, with no CHECK
constraint either. Membership is enforced in Python (``validate_strings=True``).

That makes the length the ONLY schema fact tied to the enum: the column was sized
for ``signal_events`` (13). ``pinescript_signal_marker`` is 24 characters and would
be truncated/rejected by the existing column, so it is widened to 24. ``agent_dataset``
(13) fits either way.

No data changes: widening a VARCHAR is an in-place catalog update in Postgres, every
existing value stays valid, and no row is rewritten. Downgrade narrows back to 13 —
safe because it can only run on a database that never stored a longer value (a
``pinescript_signal_marker`` row would make the narrowing fail loudly rather than
silently truncate, which is the correct outcome).

Revision ID: 0040_export_type_agent_pine
Revises: 0039_backtest_run_cancellation
Create Date: 2026-07-29
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0040_export_type_agent_pine"
down_revision: str | None = "0039_backtest_run_cancellation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "export_artifact"
_COLUMN = "export_type"
# len("pinescript_signal_marker") == 24; len("signal_events") == 13.
_NEW_LENGTH = 24
_OLD_LENGTH = 13


def upgrade() -> None:
    op.alter_column(
        _TABLE,
        _COLUMN,
        existing_type=sa.String(length=_OLD_LENGTH),
        type_=sa.String(length=_NEW_LENGTH),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        _TABLE,
        _COLUMN,
        existing_type=sa.String(length=_NEW_LENGTH),
        type_=sa.String(length=_OLD_LENGTH),
        existing_nullable=False,
    )
