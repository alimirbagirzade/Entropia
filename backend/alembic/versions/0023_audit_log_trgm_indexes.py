"""post-V1 — audit log substring (pg_trgm) indexes (doc 19 §6.2)

Index-only migration; no table or column changes. Enables the ``pg_trgm``
extension and adds three GIN trigram indexes on ``audit_events`` so the Admin
Logs read model's SUBSTRING filters (``queries/log_projection.py``) become
index-served instead of sequential scans — the honest boundary that #139
(``0022_audit_log_indexes``) explicitly left open:

- the ``family`` filter (``_family_predicate``) runs
  ``lower(event_kind) LIKE '%token%'``;
- the ``q`` search runs the same ``LIKE '%needle%'`` over ``event_kind``,
  ``target_entity_id`` and ``reason`` (doc 19 §6.2 — "text search over safe
  INDEXED fields").

A leading-wildcard ``LIKE`` cannot use a B-tree (not even
``varchar_pattern_ops``, which serves only anchored prefixes); only a
``gin_trgm_ops`` trigram index serves it. The filters lowercase the column, so
each index is an expression index over ``lower(col)`` to match the predicate.
Nullable columns carry a partial ``IS NOT NULL`` predicate (a NULL row never
matches a ``contains`` filter) to keep the insert-hot append path cheap;
``event_kind`` is NOT NULL so it needs no predicate.

Honest boundary: the ``system_other`` family and the earlier-family exclusions
are PURELY negative (``NOT LIKE '%token%'``) — no trigram index can serve a
negated substring, so those keep riding a scan filter behind the positive
predicate. ``pg_trgm`` requires ``CREATE EXTENSION`` privilege at deploy time
(a trusted extension on PG13+, installable by the database owner).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0023_audit_log_trgm_indexes"
down_revision: str | None = "0022_audit_log_indexes"
branch_labels: None = None
depends_on: None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.create_index(
        "ix_audit_events_event_kind_trgm",
        "audit_events",
        [sa.text("lower(event_kind) gin_trgm_ops")],
        postgresql_using="gin",
    )
    op.create_index(
        "ix_audit_events_target_id_trgm",
        "audit_events",
        [sa.text("lower(target_entity_id) gin_trgm_ops")],
        postgresql_using="gin",
        postgresql_where=sa.text("target_entity_id IS NOT NULL"),
    )
    op.create_index(
        "ix_audit_events_reason_trgm",
        "audit_events",
        [sa.text("lower(reason) gin_trgm_ops")],
        postgresql_using="gin",
        postgresql_where=sa.text("reason IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_audit_events_reason_trgm", table_name="audit_events")
    op.drop_index("ix_audit_events_target_id_trgm", table_name="audit_events")
    op.drop_index("ix_audit_events_event_kind_trgm", table_name="audit_events")
    # pg_trgm is deliberately NOT dropped: an extension can back objects beyond
    # this table, and DROP EXTENSION is destructive/irreversible in a routine
    # down-migration.
