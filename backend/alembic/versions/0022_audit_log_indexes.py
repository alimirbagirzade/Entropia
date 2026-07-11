"""post-V1 — audit log-projection indexes (doc 19 §5, §6.2)

Index-only migration; no table or column changes. Five indexes on the
insert-hot, append-only ``audit_events`` table, each mirroring an EMPIRICAL
query pattern of the Admin Logs read model (``queries/log_projection.py``):

- ``severity/actor/target_type`` composites carry the newest-first
  ``(occurred_at, event_id)`` keyset behind the filtered column, so a filtered
  page is one ordered index scan. Partial WHERE mirrors the filter semantics
  (NULL never matches) and keeps write amplification low; severity indexes
  only non-info rows (the warning/error triage case — ``severity = 'info'``
  matches the table bulk and stays on ``ix_audit_events_log_order``).
- ``correlation_order`` serves the detail view's correlation chain
  (equality + ASC composite order, doc 19 §5).
- ``correlation_prefix`` is an expression index: the §6.2 filter runs
  ``lower(correlation_id) LIKE 'p%'`` while ids store UPPERCASE Crockford
  base32, so only ``lower(...)`` + ``varchar_pattern_ops`` can serve it.

Honest boundary: ``actor_kind`` (3-value enum) stays unindexed by design, and
the family/query-text substring filters would need pg_trgm (an extension
decision, out of scope) — both keep riding the log-order index.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0022_audit_log_indexes"
down_revision: str | None = "0021_local_auth"
branch_labels: None = None
depends_on: None = None


def upgrade() -> None:
    op.create_index(
        "ix_audit_events_severity_order",
        "audit_events",
        ["severity", "occurred_at", "event_id"],
        postgresql_where=sa.text("severity != 'info'"),
    )
    op.create_index(
        "ix_audit_events_actor_order",
        "audit_events",
        ["actor_principal_id", "occurred_at", "event_id"],
        postgresql_where=sa.text("actor_principal_id IS NOT NULL"),
    )
    op.create_index(
        "ix_audit_events_target_type_order",
        "audit_events",
        ["target_entity_type", "occurred_at", "event_id"],
        postgresql_where=sa.text("target_entity_type IS NOT NULL"),
    )
    op.create_index(
        "ix_audit_events_correlation_order",
        "audit_events",
        ["correlation_id", "occurred_at", "event_id"],
        postgresql_where=sa.text("correlation_id IS NOT NULL"),
    )
    op.create_index(
        "ix_audit_events_correlation_prefix",
        "audit_events",
        [sa.text("lower(correlation_id) varchar_pattern_ops")],
        postgresql_where=sa.text("correlation_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_audit_events_correlation_prefix", table_name="audit_events")
    op.drop_index("ix_audit_events_correlation_order", table_name="audit_events")
    op.drop_index("ix_audit_events_target_type_order", table_name="audit_events")
    op.drop_index("ix_audit_events_actor_order", table_name="audit_events")
    op.drop_index("ix_audit_events_severity_order", table_name="audit_events")
