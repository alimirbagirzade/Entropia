"""Mainboard composition-plane API contract tests (doc 01 §4, §5, §7).

DI-override style (mirrors test_library_contract.py): the ASGI app is exercised via
httpx with ``request_context`` overridden to inject a chosen actor and a dummy
session. Only DB-free paths are asserted here — the Guest 401 (page is
authentication-gated, AT#1 no leak), the CR-01 external-kind validation, and the
two transient draft openers (AT#3, no root/revision/item identity). DB-touching
flows are covered by tests/integration/test_mainboard_persistence.py.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from entropia.apps.api.deps import RequestContext, request_context
from entropia.domain.identity import Actor
from entropia.domain.lifecycle.enums import PrincipalType, Role


class _DummySession:
    """Stand-in; guest + transient + pure-validation paths never touch it."""


def _actor(role: Role | None, ptype: PrincipalType, pid: str | None) -> Actor:
    return Actor(principal_id=pid, principal_type=ptype, role=role)


def _override(app: Any, actor: Actor) -> Iterator[None]:
    app.dependency_overrides[request_context] = lambda: RequestContext(
        session=_DummySession(),  # type: ignore[arg-type]
        actor=actor,
    )
    try:
        yield
    finally:
        app.dependency_overrides.pop(request_context, None)


async def _client(app: Any) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://t")


@pytest.mark.contract
async def test_guest_cannot_open_default_mainboard(app) -> None:
    gen = _override(app, Actor.anonymous())
    next(gen)
    try:
        async with await _client(app) as c:
            resp = await c.get("/api/v1/mainboards/default")
        assert resp.status_code == 401
        assert resp.json()["error"]["code"] == "UNAUTHENTICATED"
    finally:
        next(gen, None)


@pytest.mark.contract
async def test_strategy_is_not_a_valid_external_draft_kind(app) -> None:
    # CR-01: a Strategy is not an external work object kind for this endpoint.
    gen = _override(app, _actor(Role.USER, PrincipalType.HUMAN, "user_1"))
    next(gen)
    try:
        async with await _client(app) as c:
            resp = await c.post("/api/v1/external-work-object-drafts/strategy")
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "MAINBOARD_ITEM_KIND_MISMATCH"
    finally:
        next(gen, None)


@pytest.mark.contract
async def test_unknown_external_draft_kind_is_rejected(app) -> None:
    gen = _override(app, _actor(Role.USER, PrincipalType.HUMAN, "user_1"))
    next(gen)
    try:
        async with await _client(app) as c:
            resp = await c.post("/api/v1/external-work-object-drafts/not_a_kind")
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "MAINBOARD_ITEM_KIND_MISMATCH"
    finally:
        next(gen, None)


@pytest.mark.contract
async def test_external_trading_signal_draft_is_transient(app) -> None:
    gen = _override(app, _actor(Role.USER, PrincipalType.HUMAN, "user_1"))
    next(gen)
    try:
        async with await _client(app) as c:
            resp = await c.post("/api/v1/external-work-object-drafts/trading_signal")
        assert resp.status_code == 200
        body = resp.json()
        assert body["kind"] == "trading_signal"
        assert body["unsaved"] is True
        # AT#3: an unsaved draft has no root/revision/item identity.
        assert "root_id" not in body
        assert "revision_id" not in body
        assert "item_id" not in body
        assert body["draft_id"].startswith("wodraft_")
    finally:
        next(gen, None)


@pytest.mark.contract
async def test_strategy_draft_is_transient(app) -> None:
    gen = _override(app, _actor(Role.USER, PrincipalType.HUMAN, "user_1"))
    next(gen)
    try:
        async with await _client(app) as c:
            resp = await c.post("/api/v1/strategy-drafts")
        assert resp.status_code == 200
        body = resp.json()
        assert body["kind"] == "strategy"
        assert body["unsaved"] is True
        assert "root_id" not in body
        assert body["draft_id"].startswith("wodraft_")
    finally:
        next(gen, None)


@pytest.mark.contract
async def test_guest_cannot_open_strategy_draft(app) -> None:
    gen = _override(app, Actor.anonymous())
    next(gen)
    try:
        async with await _client(app) as c:
            resp = await c.post("/api/v1/strategy-drafts")
        assert resp.status_code == 401
        assert resp.json()["error"]["code"] == "UNAUTHENTICATED"
    finally:
        next(gen, None)
