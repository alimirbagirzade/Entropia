"""post-V1 — audit log-projection index shape (doc 19 §5, §6.2).

Auto-skips without PostgreSQL (session fixture). The integration schema is
built from ORM metadata, so these asserts pin the MODEL's index definitions;
the paired migration ``0022_audit_log_indexes`` is proven equivalent by the
alembic up/down/up + migration<->model parity ritual. Asserts run against
``pg_indexes.indexdef`` (server-truth DDL, not inspector approximations):

- the five projection indexes exist on ``audit_events``;
- each filter composite carries the newest-first ``(occurred_at, event_id)``
  keyset BEHIND its filter column (column order is the contract);
- partial predicates match the filter semantics (NULL never matches;
  severity indexes only non-info triage rows);
- the correlation prefix index is an expression index over
  ``lower(correlation_id)`` with pattern ops (ids store UPPERCASE Crockford
  base32 — a plain column index cannot serve the §6.2 LIKE-prefix filter).
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

EXPECTED_INDEXES = {
    "ix_audit_events_severity_order",
    "ix_audit_events_actor_order",
    "ix_audit_events_target_type_order",
    "ix_audit_events_correlation_order",
    "ix_audit_events_correlation_prefix",
}


async def _indexdefs(session: AsyncSession) -> dict[str, str]:
    rows = (
        await session.execute(
            text("SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'audit_events'")
        )
    ).all()
    return dict(rows)


async def test_projection_indexes_exist(session: AsyncSession) -> None:
    defs = await _indexdefs(session)
    assert set(defs) >= EXPECTED_INDEXES, sorted(defs)
    # The pre-existing baseline indexes survive untouched.
    assert "ix_audit_events_log_order" in defs
    assert "ix_audit_events_target" in defs


async def test_filter_composites_carry_keyset_order(session: AsyncSession) -> None:
    defs = await _indexdefs(session)
    assert "(severity, occurred_at, event_id)" in defs["ix_audit_events_severity_order"]
    assert "(actor_principal_id, occurred_at, event_id)" in defs["ix_audit_events_actor_order"]
    assert (
        "(target_entity_type, occurred_at, event_id)" in defs["ix_audit_events_target_type_order"]
    )
    assert "(correlation_id, occurred_at, event_id)" in defs["ix_audit_events_correlation_order"]


async def test_partial_predicates_mirror_filter_semantics(session: AsyncSession) -> None:
    defs = await _indexdefs(session)
    assert "WHERE" in defs["ix_audit_events_severity_order"]
    assert "info" in defs["ix_audit_events_severity_order"]
    for name, column in (
        ("ix_audit_events_actor_order", "actor_principal_id"),
        ("ix_audit_events_target_type_order", "target_entity_type"),
        ("ix_audit_events_correlation_order", "correlation_id"),
        ("ix_audit_events_correlation_prefix", "correlation_id"),
    ):
        assert f"{column} IS NOT NULL" in defs[name], defs[name]


async def test_correlation_prefix_is_expression_index(session: AsyncSession) -> None:
    ddl = (await _indexdefs(session))["ix_audit_events_correlation_prefix"]
    assert "lower(" in ddl
    assert "varchar_pattern_ops" in ddl
