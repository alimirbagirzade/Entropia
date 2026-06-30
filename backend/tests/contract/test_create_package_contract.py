"""Create Package + Pre-Check API contract tests (docs 06 §2, §4; CR-02).

DI-override style (mirrors test_esp_contract.py). Every asserted path fails on
authorization or PURE validation BEFORE any DB access, so a dummy session is
enough: Guest create -> 401; legacy/strategy type, empty source, bad runtime and
incompatible output contract -> 422 with their typed codes; non-Admin / Agent
approve -> 403 APPROVAL_REQUIRES_ADMIN (the Admin gate runs before the request is
loaded).
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from entropia.apps.api.deps import RequestContext, request_context
from entropia.domain.identity import Actor
from entropia.domain.lifecycle.enums import PrincipalType, Role

_VALID_BODY = {
    "package_type": "indicator",
    "creation_mode": "translate_existing_code",
    "source_language": "pinescript",
    "target_runtime": "python",
    "request_body": "//@version=5\nindicator('x')",
    "output_contract": {"kind": "directional_signal"},
}

_REQUESTS = "/api/v1/create-package/requests"


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


async def _post(app: Any, actor: Actor, path: str, body: dict[str, Any]) -> tuple[int, str]:
    gen = _override(app, actor)
    next(gen)
    try:
        async with await _client(app) as c:
            resp = await c.post(path, json=body)
        return resp.status_code, resp.json()["error"]["code"]
    finally:
        next(gen, None)


@pytest.mark.contract
async def test_guest_create_rejected(app) -> None:
    status, code = await _post(app, Actor.anonymous(), _REQUESTS, _VALID_BODY)
    assert status == 401
    assert code == "UNAUTHENTICATED"


@pytest.mark.contract
async def test_legacy_type_rejected(app) -> None:
    body = {**_VALID_BODY, "package_type": "trading_signal"}
    status, code = await _post(
        app, _actor(Role.USER, PrincipalType.HUMAN, "user_1"), _REQUESTS, body
    )
    assert status == 422
    assert code == "CLIENT_LEGACY_TYPE_REJECTED"


@pytest.mark.contract
async def test_strategy_type_rejected(app) -> None:
    body = {**_VALID_BODY, "package_type": "strategy"}
    status, code = await _post(
        app, _actor(Role.USER, PrincipalType.HUMAN, "user_1"), _REQUESTS, body
    )
    assert status == 422
    assert code == "CLIENT_LEGACY_TYPE_REJECTED"


@pytest.mark.contract
async def test_empty_source_rejected(app) -> None:
    body = {**_VALID_BODY, "request_body": "   "}
    status, code = await _post(
        app, _actor(Role.USER, PrincipalType.HUMAN, "user_1"), _REQUESTS, body
    )
    assert status == 422
    assert code == "EMPTY_SOURCE"


@pytest.mark.contract
async def test_unsupported_runtime_rejected(app) -> None:
    body = {**_VALID_BODY, "target_runtime": "pine_v5"}
    status, code = await _post(
        app, _actor(Role.USER, PrincipalType.HUMAN, "user_1"), _REQUESTS, body
    )
    assert status == 422
    assert code == "RUNTIME_UNAVAILABLE"


@pytest.mark.contract
async def test_output_contract_invalid_for_type(app) -> None:
    body = {
        "package_type": "condition",
        "creation_mode": "generate_from_description",
        "target_runtime": "python",
        "request_body": "boolean cross condition",
        "output_contract": {"kind": "directional_signal"},  # not valid for condition
    }
    status, code = await _post(
        app, _actor(Role.USER, PrincipalType.HUMAN, "user_1"), _REQUESTS, body
    )
    assert status == 422
    assert code == "OUTPUT_CONTRACT_INVALID"


@pytest.mark.contract
async def test_non_admin_approve_rejected(app) -> None:
    status, code = await _post(
        app,
        _actor(Role.SUPERVISOR, PrincipalType.HUMAN, "sup_1"),
        f"{_REQUESTS}/pkgreq_x/approve",
        {},
    )
    assert status == 403
    assert code == "APPROVAL_REQUIRES_ADMIN"


@pytest.mark.contract
async def test_agent_approve_rejected(app) -> None:
    status, code = await _post(
        app,
        _actor(None, PrincipalType.AGENT, "agent_1"),
        f"{_REQUESTS}/pkgreq_x/approve",
        {},
    )
    assert status == 403
    assert code == "APPROVAL_REQUIRES_ADMIN"


@pytest.mark.contract
async def test_guest_list_rejected(app) -> None:
    gen = _override(app, Actor.anonymous())
    next(gen)
    try:
        async with await _client(app) as c:
            resp = await c.get(_REQUESTS)
        assert resp.status_code == 401
        assert resp.json()["error"]["code"] == "UNAUTHENTICATED"
    finally:
        next(gen, None)
