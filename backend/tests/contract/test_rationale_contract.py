"""Rationale Families API contract tests (doc 10 §2, §7, §10).

DI-override style (mirrors test_esp_contract.py). Guest-gated and pure-validation
paths fail BEFORE any DB access, so a dummy session is enough. A User (page-eligible
under the shared exception) is used so an asserted validation code is the intended
one, not a page-access denial.
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
    """Stand-in; gated/validation paths never touch it."""


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


# ---- Guest is rejected before any registry/assignment data (doc 10 §2, RF-14) ----


@pytest.mark.contract
async def test_guest_cannot_list_families(app) -> None:
    gen = _override(app, Actor.anonymous())
    next(gen)
    try:
        async with await _client(app) as c:
            resp = await c.get("/api/v1/rationale-families")
        assert resp.status_code == 401
        assert resp.json()["error"]["code"] == "UNAUTHENTICATED"
    finally:
        next(gen, None)


@pytest.mark.contract
async def test_guest_cannot_list_assignments(app) -> None:
    gen = _override(app, Actor.anonymous())
    next(gen)
    try:
        async with await _client(app) as c:
            resp = await c.get("/api/v1/package-rationale-assignments")
        assert resp.status_code == 401
        assert resp.json()["error"]["code"] == "UNAUTHENTICATED"
    finally:
        next(gen, None)


@pytest.mark.contract
async def test_guest_cannot_create_family(app) -> None:
    gen = _override(app, Actor.anonymous())
    next(gen)
    try:
        async with await _client(app) as c:
            resp = await c.post("/api/v1/rationale-families", json={"display_name": "Reversal"})
        assert resp.status_code == 401
        assert resp.json()["error"]["code"] == "UNAUTHENTICATED"
    finally:
        next(gen, None)


@pytest.mark.contract
async def test_guest_cannot_batch_assign(app) -> None:
    """Also proves the ':batch' route literal matches in Starlette."""
    gen = _override(app, Actor.anonymous())
    next(gen)
    try:
        async with await _client(app) as c:
            resp = await c.post(
                "/api/v1/package-rationale-assignments:batch",
                json={"changes": [{"package_root_id": "pkg_x"}]},
            )
        assert resp.status_code == 401
        assert resp.json()["error"]["code"] == "UNAUTHENTICATED"
    finally:
        next(gen, None)


# ---- Pure validation runs before any DB access (doc 10 §10.1) -----------------


@pytest.mark.contract
async def test_blank_family_name_rejected(app) -> None:
    gen = _override(app, _actor(Role.USER, PrincipalType.HUMAN, "user_1"))
    next(gen)
    try:
        async with await _client(app) as c:
            resp = await c.post("/api/v1/rationale-families", json={"display_name": "   "})
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "RATIONALE_FAMILY_NAME_REQUIRED"
    finally:
        next(gen, None)


@pytest.mark.contract
async def test_too_long_family_name_rejected(app) -> None:
    gen = _override(app, _actor(Role.USER, PrincipalType.HUMAN, "user_1"))
    next(gen)
    try:
        async with await _client(app) as c:
            resp = await c.post("/api/v1/rationale-families", json={"display_name": "x" * 121})
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "RATIONALE_FAMILY_NAME_TOO_LONG"
    finally:
        next(gen, None)


@pytest.mark.contract
async def test_empty_batch_rejected(app) -> None:
    gen = _override(app, _actor(Role.USER, PrincipalType.HUMAN, "user_1"))
    next(gen)
    try:
        async with await _client(app) as c:
            resp = await c.post("/api/v1/package-rationale-assignments:batch", json={"changes": []})
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "VALIDATION_ERROR"
    finally:
        next(gen, None)
