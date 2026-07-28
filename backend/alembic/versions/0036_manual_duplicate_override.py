"""Manual duplicate-content override provenance on the publication event trail

Doc 21 §10 (``MANUAL_DUPLICATE_CONTENT``) makes an explicit duplicate override
a separately recorded Admin decision. Until now
the ``allow_duplicate`` flag never left the request: the published section was
indistinguishable from one that never hit a duplicate at all.

Two additive nullable columns on ``manual_publication_events`` (the immutable
manual trail of doc 21 §9/§11):

* ``duplicate_override`` BOOLEAN NULL — TRUE only when an active duplicate
  actually existed AND the Admin published over it; FALSE for an ordinary
  publish; NULL for rows written before this migration and for non-publish
  events (revise/soft delete/purge), where the notion does not apply.
* ``duplicate_of_document_id`` VARCHAR(40) NULL — the active section whose
  normalized checksum was duplicated, so the recorded decision names its
  counterpart without a second lookup. Deliberately NOT an FK: the duplicated
  section may itself be soft-deleted or purged later, and this column is
  historical evidence, not a live reference.

Both nullable with no backfill — existing rows keep their exact meaning.
Downgrade drops the columns.

Revision ID: 0036_manual_duplicate_override
Revises: 0035_portfolio_rules
Create Date: 2026-07-28
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0036_manual_duplicate_override"
down_revision: str | None = "0035_portfolio_rules"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "manual_publication_events"


def upgrade() -> None:
    op.add_column(_TABLE, sa.Column("duplicate_override", sa.Boolean(), nullable=True))
    op.add_column(
        _TABLE, sa.Column("duplicate_of_document_id", sa.String(length=40), nullable=True)
    )


def downgrade() -> None:
    op.drop_column(_TABLE, "duplicate_of_document_id")
    op.drop_column(_TABLE, "duplicate_override")
