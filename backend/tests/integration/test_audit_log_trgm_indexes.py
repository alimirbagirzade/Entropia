"""post-V1 — audit log substring (pg_trgm) trigram index shape (doc 19 §6.2).

Auto-skips without PostgreSQL (session fixture). The integration schema is built
from ORM metadata — the ``before_create`` listener in ``models/audit.py``
provisions ``pg_trgm`` first — so these asserts pin the MODEL's trigram index
definitions against ``pg_indexes.indexdef`` (server-truth DDL, not inspector
approximations); the paired migration ``0023_audit_log_trgm_indexes`` is proven
equivalent by the alembic up/down/up + parity ritual.

These three GIN trigram indexes make the Admin Logs SUBSTRING filters
index-served (``queries/log_projection.py`` — the ``family`` token filter and
the ``q`` search): a leading-wildcard ``LIKE '%needle%'`` cannot use a B-tree,
only ``gin_trgm_ops``. The filters lowercase the column, so each index is an
expression index over ``lower(col)``.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# index name -> the column its lower() expression covers
TRGM_INDEXES = {
    "ix_audit_events_event_kind_trgm": "event_kind",
    "ix_audit_events_target_id_trgm": "target_entity_id",
    "ix_audit_events_reason_trgm": "reason",
}


async def _indexdefs(session: AsyncSession) -> dict[str, str]:
    rows = (
        await session.execute(
            text("SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'audit_events'")
        )
    ).all()
    return dict(rows)


async def test_trgm_indexes_exist(session: AsyncSession) -> None:
    defs = await _indexdefs(session)
    assert set(defs) >= set(TRGM_INDEXES), sorted(defs)
    # The extension must be present — the trigram indexes could not exist otherwise.
    ext = (
        await session.execute(text("SELECT 1 FROM pg_extension WHERE extname = 'pg_trgm'"))
    ).scalar()
    assert ext == 1
    # The #139 baseline indexes survive untouched alongside the new trigram ones.
    assert "ix_audit_events_log_order" in defs
    assert "ix_audit_events_correlation_prefix" in defs


async def test_trgm_indexes_are_gin_over_lower_expression(session: AsyncSession) -> None:
    defs = await _indexdefs(session)
    for name, column in TRGM_INDEXES.items():
        ddl = defs[name]
        assert "USING gin" in ddl, ddl
        assert "gin_trgm_ops" in ddl, ddl
        assert "lower(" in ddl, ddl
        assert column in ddl, ddl


async def test_nullable_trgm_indexes_are_partial(session: AsyncSession) -> None:
    defs = await _indexdefs(session)
    for name, column in (
        ("ix_audit_events_target_id_trgm", "target_entity_id"),
        ("ix_audit_events_reason_trgm", "reason"),
    ):
        assert f"{column} IS NOT NULL" in defs[name], defs[name]


async def test_event_kind_trgm_has_no_partial_predicate(session: AsyncSession) -> None:
    # event_kind is NOT NULL — the index covers every row, so no WHERE clause.
    ddl = (await _indexdefs(session))["ix_audit_events_event_kind_trgm"]
    assert "WHERE" not in ddl, ddl
