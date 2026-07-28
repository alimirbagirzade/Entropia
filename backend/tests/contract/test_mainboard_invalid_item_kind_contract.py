"""AOS-03 over the wire: a legacy item kind returns ``INVALID_ITEM_KIND`` (doc 03).

DI-override style, mirroring ``test_mainboard_contract.py``: the ASGI app is
exercised via httpx with ``request_context`` overridden. Both surfaces asserted
here reject BEFORE touching the session, so no database is required — which is
also the point of AOS-03: "no PackageKind expansion, root, revision or item is
created".

Sibling codes are pinned in the same file so a future edit cannot quietly collapse
them into one: ``strategy`` on the external-only opener and an unknown kind both
stay ``MAINBOARD_ITEM_KIND_MISMATCH`` (CR-01).
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from entropia.apps.api.deps import RequestContext, request_context
from entropia.domain.identity import Actor
from entropia.domain.lifecycle.enums import PrincipalType, Role

_USER = Actor(principal_id="user_1", principal_type=PrincipalType.HUMAN, role=Role.USER)


class _DummySession:
    """Stand-in; the kind guard rejects before any session use."""


def _override(app: Any) -> Iterator[None]:
    app.dependency_overrides[request_context] = lambda: RequestContext(
        session=_DummySession(),  # type: ignore[arg-type]
        actor=_USER,
    )
    try:
        yield
    finally:
        app.dependency_overrides.pop(request_context, None)


async def _client(app: Any) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://t")


@pytest.mark.contract
@pytest.mark.parametrize("legacy", ["signal_package", "trade_log_package"])
async def test_aos_03_legacy_object_kind_post_returns_invalid_item_kind(app, legacy: str) -> None:
    gen = _override(app)
    next(gen)
    try:
        async with await _client(app) as c:
            resp = await c.post(
                "/api/v1/work-objects",
                json={"object_kind": legacy, "payload": {"name": "X"}},
            )
        assert resp.status_code == 422
        error = resp.json()["error"]
        assert error["code"] == "INVALID_ITEM_KIND"
        assert error["category"] == "validation"
        assert error["retryable"] is False
        assert error["field_path"] == "object_kind"
        assert error["details"][0]["actual"] == legacy
    finally:
        next(gen, None)


@pytest.mark.contract
@pytest.mark.parametrize("legacy", ["signal_package", "trade_log_package"])
async def test_aos_03_legacy_draft_kind_is_rejected_by_the_chooser(app, legacy: str) -> None:
    gen = _override(app)
    next(gen)
    try:
        async with await _client(app) as c:
            resp = await c.post(f"/api/v1/external-work-object-drafts/{legacy}")
        assert resp.status_code == 422
        body = resp.json()
        assert body["error"]["code"] == "INVALID_ITEM_KIND"
        # No transient draft identity leaks out of a rejected chooser call.
        assert set(body.keys()) == {"error"}
    finally:
        next(gen, None)


@pytest.mark.contract
async def test_invalid_item_kind_does_not_swallow_the_cr01_mismatch_code(app) -> None:
    gen = _override(app)
    next(gen)
    try:
        async with await _client(app) as c:
            strategy = await c.post("/api/v1/external-work-object-drafts/strategy")
            unknown = await c.post("/api/v1/external-work-object-drafts/not_a_kind")
        assert strategy.status_code == 422
        assert strategy.json()["error"]["code"] == "MAINBOARD_ITEM_KIND_MISMATCH"
        assert unknown.status_code == 422
        assert unknown.json()["error"]["code"] == "MAINBOARD_ITEM_KIND_MISMATCH"
    finally:
        next(gen, None)
