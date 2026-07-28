"""Lock the audit-log read model — the compliance read path (M3 §8).

Auto-skips when no PostgreSQL is reachable (see tests/integration/conftest.py).

``queries/audit_log.py::list_audit_events`` is what an auditor actually sees: it
is the only projection of the immutable ``audit_events`` table, and until now no
test executed it — only the route's 403 denial was covered
(``tests/contract/test_identity_and_gating.py``), which returns BEFORE the query
runs. A dropped field or an off-by-one cursor would have shipped silently.

Covers: newest-first ordering and page cap; ``next_cursor`` presence/absence and
its exclusive semantics; a full cursor walk visiting every event exactly once;
the exact projected field set (including nullable columns projected as ``null``,
never omitted); an event whose subject no longer exists staying listed (audit is
standalone and survives delete/purge); and the route's Admin gate in both
directions. Behaviour is unchanged — this only pins it.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient

from entropia.application.queries.audit_log import list_audit_events
from entropia.apps.api.deps import RequestContext, request_context
from entropia.domain.identity import Actor
from entropia.domain.lifecycle.enums import ActorKind, PrincipalType, Role
from entropia.infrastructure.postgres.models import AuditEvent
from entropia.shared.pagination import PageParams

pytestmark = pytest.mark.integration

ADMIN = Actor(principal_id="user_admin", principal_type=PrincipalType.HUMAN, role=Role.ADMIN)
USER = Actor(principal_id="user_1", principal_type=PrincipalType.HUMAN, role=Role.USER)

_BASE_TIME = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)


def _event_id(index: int) -> str:
    # Ids are ULID-like and lexicographically time-sortable (shared/ids.py), so a
    # zero-padded sequence reproduces the real id/time co-ordering the keyset
    # cursor (``event_id <`` under an ``occurred_at, event_id`` order) relies on.
    return f"evt_{index:04d}"


async def _seed_events(session, count: int) -> list[str]:
    """Insert ``count`` events, oldest first; return their ids in insertion order."""
    ids = []
    for index in range(1, count + 1):
        event_id = _event_id(index)
        session.add(
            AuditEvent(
                event_id=event_id,
                occurred_at=_BASE_TIME.replace(minute=index),
                event_kind="mainboard.work_object_created",
                severity="info",
                actor_principal_id="user_1",
                actor_kind=ActorKind.HUMAN,
            )
        )
        ids.append(event_id)
    await session.flush()
    return ids


def _override(app, actor: Actor, session) -> Iterator[None]:
    app.dependency_overrides[request_context] = lambda: RequestContext(session=session, actor=actor)
    try:
        yield
    finally:
        app.dependency_overrides.pop(request_context, None)


# --------------------------------------------------------------------------- #
# Ordering + paging                                                            #
# --------------------------------------------------------------------------- #


async def test_returns_newest_first_capped_at_the_page_limit(session) -> None:
    await _seed_events(session, 5)

    data, _ = await list_audit_events(session, PageParams(limit=3))

    assert [row["event_id"] for row in data] == [_event_id(5), _event_id(4), _event_id(3)]


async def test_returns_the_last_event_on_the_page_as_cursor_when_more_remain(session) -> None:
    await _seed_events(session, 5)

    data, next_cursor = await list_audit_events(session, PageParams(limit=3))

    assert next_cursor == data[-1]["event_id"] == _event_id(3)


async def test_returns_no_cursor_when_the_page_exhausts_the_log(session) -> None:
    await _seed_events(session, 3)

    data, next_cursor = await list_audit_events(session, PageParams(limit=3))

    assert len(data) == 3
    assert next_cursor is None


async def test_returns_empty_page_and_no_cursor_when_the_log_is_empty(session) -> None:
    data, next_cursor = await list_audit_events(session, PageParams(limit=20))

    assert data == []
    assert next_cursor is None


async def test_cursor_page_excludes_the_cursor_event_itself(session) -> None:
    await _seed_events(session, 5)

    _, next_cursor = await list_audit_events(session, PageParams(limit=3))
    data, _ = await list_audit_events(session, PageParams(cursor=next_cursor, limit=3))

    assert next_cursor not in [row["event_id"] for row in data]
    assert [row["event_id"] for row in data] == [_event_id(2), _event_id(1)]


async def test_cursor_walk_visits_every_event_exactly_once_newest_first(session) -> None:
    seeded = await _seed_events(session, 7)

    seen: list[str] = []
    cursor: str | None = None
    for _ in range(10):  # bounded: a non-advancing cursor must fail, not spin
        page, cursor = await list_audit_events(session, PageParams(cursor=cursor, limit=2))
        seen.extend(row["event_id"] for row in page)
        if cursor is None:
            break

    assert cursor is None
    assert seen == list(reversed(seeded))


# --------------------------------------------------------------------------- #
# Projection shape                                                             #
# --------------------------------------------------------------------------- #


async def test_projects_exactly_the_advertised_fields_from_the_row(session) -> None:
    occurred_at = _BASE_TIME
    session.add(
        AuditEvent(
            event_id=_event_id(1),
            occurred_at=occurred_at,
            event_kind="strategy.revision_created",
            severity="warning",
            actor_principal_id="user_1",
            actor_kind=ActorKind.HUMAN,
            target_entity_id="strat_1",
            target_entity_type="strategy",
            previous_state="draft",
            new_state="validated",
            correlation_id="corr_1",
            reason="not projected",
        )
    )
    await session.flush()

    data, _ = await list_audit_events(session, PageParams(limit=1))

    assert data == [
        {
            "event_id": _event_id(1),
            "occurred_at": occurred_at.isoformat(),
            "event_kind": "strategy.revision_created",
            "severity": "warning",
            "actor_principal_id": "user_1",
            "actor_kind": "human",
            "target_entity_id": "strat_1",
            "target_entity_type": "strategy",
            "previous_state": "draft",
            "new_state": "validated",
            "correlation_id": "corr_1",
        }
    ]


async def test_projects_absent_columns_as_null_rather_than_omitting_the_keys(session) -> None:
    session.add(
        AuditEvent(
            event_id=_event_id(1),
            occurred_at=_BASE_TIME,
            event_kind="system.started",
            severity="info",
            actor_principal_id=None,
            actor_kind=ActorKind.SYSTEM_SERVICE,
        )
    )
    await session.flush()

    data, _ = await list_audit_events(session, PageParams(limit=1))

    row = data[0]
    assert row["actor_kind"] == "system_service"
    for key in (
        "actor_principal_id",
        "target_entity_id",
        "target_entity_type",
        "previous_state",
        "new_state",
        "correlation_id",
    ):
        assert key in row
        assert row[key] is None


async def test_lists_an_event_whose_subject_no_longer_exists(session) -> None:
    # Audit rows are standalone and immutable: they survive the soft delete AND the
    # purge of their subject (models/audit.py). The projection must therefore still
    # return an event whose ``target_entity_id`` resolves to nothing.
    session.add(
        AuditEvent(
            event_id=_event_id(1),
            occurred_at=_BASE_TIME,
            event_kind="trash.entry_purged",
            severity="warning",
            actor_principal_id="user_admin",
            actor_kind=ActorKind.HUMAN,
            target_entity_id="strat_purged",
            target_entity_type="strategy",
            previous_state="soft_deleted",
            new_state="purged",
        )
    )
    await session.flush()

    data, _ = await list_audit_events(session, PageParams(limit=20))

    assert [row["target_entity_id"] for row in data] == ["strat_purged"]
    assert data[0]["new_state"] == "purged"


# --------------------------------------------------------------------------- #
# Route gate                                                                   #
# --------------------------------------------------------------------------- #


async def test_route_returns_the_paged_envelope_for_an_admin(app, session) -> None:
    await _seed_events(session, 3)
    gen = _override(app, ADMIN, session)
    next(gen)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
            resp = await client.get("/api/v1/audit-events", params={"limit": 2})
    finally:
        next(gen, None)

    assert resp.status_code == 200
    body = resp.json()
    assert [row["event_id"] for row in body["data"]] == [_event_id(3), _event_id(2)]
    assert body["meta"] == {"cursor": _event_id(2), "has_more": True}


async def test_route_rejects_a_non_admin_before_reading_any_event(app, session) -> None:
    await _seed_events(session, 3)
    gen = _override(app, USER, session)
    next(gen)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as client:
            resp = await client.get("/api/v1/audit-events")
    finally:
        next(gen, None)

    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "ACCESS_DENIED"
