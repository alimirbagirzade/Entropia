"""Package Library catalog API contract tests (doc 08 §2, §5, §9.2).

DI-override style (mirrors test_esp_contract.py). The catalog is Guest-blocked and
filter validation happens before any DB access, so a dummy session is enough: the
guest paths assert 401 from the query's ``require_authenticated`` and the
bad-filter paths assert the typed 422 from ``parse_catalog_filters``.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from entropia.apps.api.deps import RequestContext, request_context
from entropia.domain.identity import Actor
from entropia.domain.lifecycle.enums import PrincipalType, Role
from entropia.shared.concurrency import etag_for_row_version


class _DummySession:
    """Stand-in; guest + bad-filter paths never touch it."""


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
async def test_guest_cannot_list_catalog(app) -> None:
    gen = _override(app, Actor.anonymous())
    next(gen)
    try:
        async with await _client(app) as c:
            resp = await c.get("/api/v1/library")
        assert resp.status_code == 401
        assert resp.json()["error"]["code"] == "UNAUTHENTICATED"
    finally:
        next(gen, None)


@pytest.mark.contract
async def test_guest_cannot_open_detail(app) -> None:
    gen = _override(app, Actor.anonymous())
    next(gen)
    try:
        async with await _client(app) as c:
            resp = await c.get("/api/v1/library/pkg_x")
        assert resp.status_code == 401
        assert resp.json()["error"]["code"] == "UNAUTHENTICATED"
    finally:
        next(gen, None)


@pytest.mark.contract
async def test_legacy_type_filter_rejected(app) -> None:
    # CR-01: trading_signal / trade_log are external objects, not packages.
    gen = _override(app, _actor(Role.USER, PrincipalType.HUMAN, "user_1"))
    next(gen)
    try:
        async with await _client(app) as c:
            resp = await c.get("/api/v1/library", params={"type": "trading_signal"})
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "CLIENT_LEGACY_TYPE_REJECTED"
    finally:
        next(gen, None)


@pytest.mark.contract
async def test_invalid_facet_filter_rejected(app) -> None:
    gen = _override(app, _actor(Role.USER, PrincipalType.HUMAN, "user_1"))
    next(gen)
    try:
        async with await _client(app) as c:
            resp = await c.get("/api/v1/library", params={"validation_state": "bogus"})
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "CATALOG_FILTER_INVALID"
    finally:
        next(gen, None)


@pytest.mark.contract
async def test_list_success_returns_envelope_and_passes_aliases(app, monkeypatch) -> None:
    import entropia.apps.api.routes.library as route

    captured: dict[str, Any] = {}

    async def _fake_list(session: Any, actor: Any, params: Any, *, filters: Any) -> dict[str, Any]:
        captured["filters"] = filters
        captured["limit"] = params.limit
        return {"data": [{"entity_id": "pkg_1"}], "meta": {"cursor": None, "has_more": False}}

    monkeypatch.setattr(route.library_query, "list_packages", _fake_list)
    gen = _override(app, _actor(Role.USER, PrincipalType.HUMAN, "user_1"))
    next(gen)
    try:
        async with await _client(app) as c:
            resp = await c.get(
                "/api/v1/library", params={"q": "moment", "type": "indicator", "limit": 5}
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"][0]["entity_id"] == "pkg_1"
        assert "meta" in body
        # ?q= -> query, ?type= -> package_type, limit forwarded to the query layer.
        assert captured["filters"].query == "moment"
        assert str(captured["filters"].package_kind) == "indicator"
        assert captured["limit"] == 5
    finally:
        next(gen, None)


@pytest.mark.contract
async def test_limit_out_of_bounds_is_422(app) -> None:
    gen = _override(app, _actor(Role.USER, PrincipalType.HUMAN, "user_1"))
    next(gen)
    try:
        async with await _client(app) as c:
            too_big = await c.get("/api/v1/library", params={"limit": 101})
            too_small = await c.get("/api/v1/library", params={"limit": 0})
        assert too_big.status_code == 422
        assert too_small.status_code == 422
    finally:
        next(gen, None)


@pytest.mark.contract
async def test_detail_emits_etag_header(app, monkeypatch) -> None:
    import entropia.apps.api.routes.library as route

    async def _fake_detail(session: Any, actor: Any, *, entity_id: str) -> dict[str, Any]:
        return {"entity_id": entity_id, "row_version": 3, "name": "X"}

    monkeypatch.setattr(route.library_query, "get_package_detail", _fake_detail)
    gen = _override(app, _actor(Role.USER, PrincipalType.HUMAN, "user_1"))
    next(gen)
    try:
        async with await _client(app) as c:
            resp = await c.get("/api/v1/library/pkg_1")
        assert resp.status_code == 200
        assert resp.headers["ETag"] == etag_for_row_version(3)
    finally:
        next(gen, None)


@pytest.mark.contract
async def test_market_and_timeframe_aliases_pass_through(app, monkeypatch) -> None:
    # P-06: the market / timeframe query params reach the filter layer as scopes.
    import entropia.apps.api.routes.library as route

    captured: dict[str, Any] = {}

    async def _fake_list(session: Any, actor: Any, params: Any, *, filters: Any) -> dict[str, Any]:
        captured["filters"] = filters
        return {"data": [], "meta": {"cursor": None, "has_more": False}}

    monkeypatch.setattr(route.library_query, "list_packages", _fake_list)
    gen = _override(app, _actor(Role.USER, PrincipalType.HUMAN, "user_1"))
    next(gen)
    try:
        async with await _client(app) as c:
            resp = await c.get(
                "/api/v1/library", params={"market": "BTCUSDT", "timeframe": "multi"}
            )
        assert resp.status_code == 200
        # Market is normalized (open scope); timeframe is a validated capability token.
        assert captured["filters"].market_scope == "btcusdt"
        assert captured["filters"].timeframe_scope == "multi"
    finally:
        next(gen, None)


@pytest.mark.contract
async def test_invalid_timeframe_filter_rejected(app) -> None:
    # A timeframe outside the capability vocabulary is a typed 422 before any DB access.
    gen = _override(app, _actor(Role.USER, PrincipalType.HUMAN, "user_1"))
    next(gen)
    try:
        async with await _client(app) as c:
            resp = await c.get("/api/v1/library", params={"timeframe": "15m"})
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "CATALOG_FILTER_INVALID"
    finally:
        next(gen, None)
