"""Auth-gating contract tests — no database needed.

We override the request_context dependency to inject a chosen Actor and a dummy
session. The admin-only routes reject non-admins (403) BEFORE any DB access, so
these run without infrastructure.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from httpx import ASGITransport, AsyncClient

from entropia.apps.api.deps import RequestContext, request_context
from entropia.domain.identity import Actor
from entropia.domain.lifecycle.enums import PrincipalType, Role


class _DummySession:
    """Stand-in; the gated paths never touch it."""


def _actor(role: Role | None, principal_type: PrincipalType, pid: str | None) -> Actor:
    return Actor(principal_id=pid, principal_type=principal_type, role=role)


def _override(app, actor: Actor) -> Iterator[None]:
    app.dependency_overrides[request_context] = lambda: RequestContext(
        session=_DummySession(),
        actor=actor,  # type: ignore[arg-type]
    )
    try:
        yield
    finally:
        app.dependency_overrides.pop(request_context, None)


async def _client(app) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://t")


@pytest.mark.contract
async def test_me_anonymous(app) -> None:
    gen = _override(app, Actor.anonymous())
    next(gen)
    try:
        async with await _client(app) as c:
            resp = await c.get("/api/v1/me")
        assert resp.status_code == 200
        body = resp.json()
        assert body["is_authenticated"] is False
        assert body["principal_type"] == "anonymous"
    finally:
        next(gen, None)


@pytest.mark.contract
async def test_me_admin(app) -> None:
    admin = _actor(Role.ADMIN, PrincipalType.HUMAN, "user_admin")
    gen = _override(app, admin)
    next(gen)
    try:
        async with await _client(app) as c:
            resp = await c.get("/api/v1/me")
        assert resp.status_code == 200
        assert resp.json()["is_admin"] is True
    finally:
        next(gen, None)


@pytest.mark.contract
@pytest.mark.parametrize(
    "method,path,expected_code",
    [
        ("GET", "/api/v1/trash-entries", "TRASH_ACCESS_FORBIDDEN"),
        ("GET", "/api/v1/trash-entries/trash_x", "TRASH_ACCESS_FORBIDDEN"),
        ("POST", "/api/v1/trash-entries/trash_x/restore", "TRASH_ACCESS_FORBIDDEN"),
        ("POST", "/api/v1/trash-entries/trash_x/purge", "TRASH_ACCESS_FORBIDDEN"),
        ("GET", "/api/v1/audit-events", "ACCESS_DENIED"),
        ("POST", "/api/v1/users/user_2/role", "ACCESS_DENIED"),
    ],
)
async def test_admin_routes_reject_normal_user(
    app, method: str, path: str, expected_code: str
) -> None:
    user = _actor(Role.USER, PrincipalType.HUMAN, "user_1")
    gen = _override(app, user)
    next(gen)
    body: dict[str, str] | None = None
    if path.endswith("role"):
        body = {"role": "admin"}
    elif path.endswith("purge"):
        # A schema-valid body so the 403 guard (not 422 validation) is exercised.
        body = {"confirmation_phrase": "x", "reauth_proof": "y"}
    try:
        async with await _client(app) as c:
            resp = await c.request(method, path, json=body)
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == expected_code
        # No object names, counts or snapshots leak to a denied caller (doc 20 §15).
        assert "data" not in resp.json()
    finally:
        next(gen, None)


@pytest.mark.contract
async def test_role_endpoint_rejects_invalid_role_value(app) -> None:
    admin = _actor(Role.ADMIN, PrincipalType.HUMAN, "user_admin")
    gen = _override(app, admin)
    next(gen)
    try:
        async with await _client(app) as c:
            # 'agent' is not an assignable role -> schema rejects it (422).
            resp = await c.post("/api/v1/users/user_2/role", json={"role": "agent"})
        assert resp.status_code == 422
    finally:
        next(gen, None)
