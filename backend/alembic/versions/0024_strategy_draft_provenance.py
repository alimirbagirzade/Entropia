"""GAP-03 — Strategy Draft source-package provenance (doc 01 §8.2, doc 08 §4.3)

Additive, no backfill: ``strategy_editor_draft`` grows one nullable ``source_provenance``
JSONB column so a draft *derived from a Strategy Package* records where it came from --
``{source_package_root_id, source_package_revision_id, source_content_hash,
inherited_dependencies}`` (doc 01 §8.2: the derived draft's provenance carries the source
package root, the source package revision, and the inherited dependency list). Ordinary
(non-derived) drafts leave it NULL, so behavior is unchanged. The source Strategy Package
stays immutable -- this is a one-way provenance pin, never an FK back-reference (its target
is a heterogeneous package revision id, pinned by content_hash, mirroring the normalized-
reference pattern).

Revision id kept <= 32 chars for ``alembic_version.version_num`` (varchar(32)).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0024_strategy_draft_provenance"
down_revision: str | None = "0023_audit_log_trgm_indexes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "strategy_editor_draft"
_COLUMN = "source_provenance"


def upgrade() -> None:
    op.add_column(_TABLE, sa.Column(_COLUMN, postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column(_TABLE, _COLUMN)
