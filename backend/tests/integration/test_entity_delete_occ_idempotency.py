"""O-18 at the HTTP edge: OCC + Idempotency-Key on the generic soft-delete route.

``DELETE /api/v1/entities/{entity_id}`` is the one delete surface that used to
carry NO concurrency token, so a racing edit could be deleted out from under its
author, and a retried submit could write a second audit trail. The fix (landed
with the O-12/O-13/O-18 wave) threads ``expected_row_version`` / ``If-Match``
through ``reconcile_occ_tokens`` and wraps the command body in ``run_idempotent``.

``tests/integration/test_idempotency_new_ops.py`` pins that at the COMMAND level
and ``tests/contract/test_occ_dual_token_contract.py`` pins the disagreement rule
against a dummy session. Neither proves the route actually forwards the header to
the command against a real database — a dropped ``Header(...)`` parameter would
pass both. These tests close that gap end to end:

* a stale ``If-Match`` -> 409 ``STALE_REVISION`` and the root stays ACTIVE;
* the current ``If-Match`` -> 204;
* NO token -> still 204. The precondition is deliberately OPTIONAL (it is not a
  428/422 gate): every one of the 16 dual-token ops in this repo treats the
  concurrency token as opt-in, and the generic delete is reachable by callers
  that predate O-18. Pinned here so the choice is explicit, not accidental;
* the same ``Idempotency-Key`` twice -> exactly ONE ``trash_entries`` row and ONE
  ``entity.soft_deleted`` audit event, with the key durably recorded.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from entropia.application.commands.entities import create_entity
from entropia.apps.api.deps import RequestContext, request_context
from entropia.domain.identity import Actor
from entropia.domain.lifecycle.enums import DeletionState, PrincipalType, Role
from entropia.infrastructure.postgres.models import (
    AuditEvent,
    EntityRegistry,
    IdempotencyKey,
    TrashEntry,
)

pytestmark = pytest.mark.integration

USER = Actor(principal_id="user_1", principal_type=PrincipalType.HUMAN, role=Role.USER)

_DELETE_PATH = "/api/v1/entities/{entity_id}"


def _override(app, session) -> Iterator[None]:
    """Bind the route to THIS test's session (the real DB), as the audit-log
    read-model test does. ``request.state.db_session`` stays unset, so the
    transaction boundary middleware neither commits nor rolls it back — the test
    owns the commits, one per simulated request."""
    app.dependency_overrides[request_context] = lambda: RequestContext(session=session, actor=USER)
    try:
        yield
    finally:
        app.dependency_overrides.pop(request_context, None)


def _client(app) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://t")


async def _count(session, model) -> int:
    return int((await session.execute(select(func.count()).select_from(model))).scalar_one())


async def _soft_delete_audits(session) -> int:
    return int(
        (
            await session.execute(
                select(func.count())
                .select_from(AuditEvent)
                .where(AuditEvent.event_kind == "entity.soft_deleted")
            )
        ).scalar_one()
    )


async def _seed_root(session) -> EntityRegistry:
    root = await create_entity(session, USER, entity_type="demo_entity", payload={"v": 1})
    await session.commit()
    return root


# --------------------------------------------------------------------------- #
# OCC                                                                          #
# --------------------------------------------------------------------------- #


async def test_entity_delete_occ_rejects_a_stale_if_match(app, session) -> None:
    root = await _seed_root(session)
    # Read the identity BEFORE the rollback below expires the instance.
    entity_id = root.entity_id
    stale = f'"rv-{root.row_version + 5}"'

    gen = _override(app, session)
    next(gen)
    try:
        async with _client(app) as c:
            resp = await c.delete(
                _DELETE_PATH.format(entity_id=entity_id), headers={"If-Match": stale}
            )
    finally:
        next(gen, None)

    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "STALE_REVISION"
    # The losing request must not have deleted anything.
    await session.rollback()
    survivor = await session.get(EntityRegistry, entity_id)
    assert survivor is not None
    assert survivor.deletion_state == DeletionState.ACTIVE
    assert await _count(session, TrashEntry) == 0


async def test_entity_delete_occ_accepts_the_current_if_match(app, session) -> None:
    root = await _seed_root(session)
    current = f'"rv-{root.row_version}"'

    gen = _override(app, session)
    next(gen)
    try:
        async with _client(app) as c:
            resp = await c.delete(
                _DELETE_PATH.format(entity_id=root.entity_id), headers={"If-Match": current}
            )
    finally:
        next(gen, None)
    await session.commit()

    assert resp.status_code == 204
    assert await _count(session, TrashEntry) == 1


async def test_entity_delete_occ_rejects_contradicting_tokens(app, session) -> None:
    """O-12 over a REAL session: body and header are two spellings of one value."""
    root = await _seed_root(session)

    gen = _override(app, session)
    next(gen)
    try:
        async with _client(app) as c:
            resp = await c.request(
                "DELETE",
                _DELETE_PATH.format(entity_id=root.entity_id),
                json={"expected_row_version": root.row_version},
                headers={"If-Match": f'"rv-{root.row_version + 1}"'},
            )
    finally:
        next(gen, None)

    assert resp.status_code == 409
    error = resp.json()["error"]
    assert error["code"] == "OCC_TOKEN_CONFLICT"
    assert error["retryable"] is False
    await session.rollback()
    assert await _count(session, TrashEntry) == 0


async def test_entity_delete_occ_token_is_optional_not_a_precondition_gate(app, session) -> None:
    """A tokenless delete is still accepted (204), NOT rejected with 428/422.

    Every dual-token op in this repo treats the concurrency token as opt-in
    (``shared/concurrency.py::check_row_version`` — ``None`` means "no
    precondition"), and doc 20 §14 asks for the token to BE the concurrency
    mechanism, not for it to be mandatory. Pinned so a future change to make it
    required is a deliberate, breaking decision rather than a silent one.
    """
    root = await _seed_root(session)

    gen = _override(app, session)
    next(gen)
    try:
        async with _client(app) as c:
            resp = await c.delete(_DELETE_PATH.format(entity_id=root.entity_id))
    finally:
        next(gen, None)
    await session.commit()

    assert resp.status_code == 204
    assert await _count(session, TrashEntry) == 1


# --------------------------------------------------------------------------- #
# Idempotency                                                                  #
# --------------------------------------------------------------------------- #


async def test_entity_delete_idempotent_replay_writes_one_trash_entry(app, session) -> None:
    root = await _seed_root(session)
    headers = {"Idempotency-Key": "idem-entity-delete-1"}

    gen = _override(app, session)
    next(gen)
    try:
        async with _client(app) as c:
            first = await c.delete(_DELETE_PATH.format(entity_id=root.entity_id), headers=headers)
            await session.commit()  # the real request boundary commits per request
            second = await c.delete(_DELETE_PATH.format(entity_id=root.entity_id), headers=headers)
            await session.commit()
    finally:
        next(gen, None)

    assert (first.status_code, second.status_code) == (204, 204)
    assert await _count(session, TrashEntry) == 1
    assert await _soft_delete_audits(session) == 1


async def test_entity_delete_idempotent_key_is_recorded_by_the_route(app, session) -> None:
    """The header must reach ``run_idempotent`` — a dropped ``Header(...)``
    parameter would leave the route silently non-idempotent while every
    command-level test still passed."""
    root = await _seed_root(session)

    gen = _override(app, session)
    next(gen)
    try:
        async with _client(app) as c:
            resp = await c.delete(
                _DELETE_PATH.format(entity_id=root.entity_id),
                headers={"Idempotency-Key": "idem-entity-delete-2"},
            )
    finally:
        next(gen, None)
    await session.commit()

    assert resp.status_code == 204
    stored = await session.get(IdempotencyKey, "idem-entity-delete-2")
    assert stored is not None
    assert stored.status == "completed"
    assert stored.actor_principal_id == USER.principal_id
