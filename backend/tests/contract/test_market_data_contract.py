"""Market Data API contract tests (doc 11, AT #5/#6/#10).

DI-override style (mirrors test_identity_and_gating.py). Auth-gated and
boundary-validation paths fail BEFORE any DB access, so a dummy session is
enough. The happy-path idempotency handshake is covered with a tiny fake session
that records added rows and can fetch an idempotency key.
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
    """Stand-in; gated/boundary paths never touch it."""


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
async def test_non_admin_approve_rejected_403(app) -> None:
    user = _actor(Role.USER, PrincipalType.HUMAN, "user_1")
    gen = _override(app, user)
    next(gen)
    try:
        async with await _client(app) as c:
            resp = await c.post(
                "/api/v1/market-datasets/mds_x/approve",
                json={"revision_id": "mrev_x"},
            )
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "APPROVAL_REQUIRES_ADMIN"
    finally:
        next(gen, None)


@pytest.mark.contract
async def test_guest_approve_rejected_403(app) -> None:
    gen = _override(app, Actor.anonymous())
    next(gen)
    try:
        async with await _client(app) as c:
            resp = await c.post(
                "/api/v1/market-datasets/mds_x/approve",
                json={"revision_id": "mrev_x"},
            )
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "APPROVAL_REQUIRES_ADMIN"
    finally:
        next(gen, None)


@pytest.mark.contract
async def test_create_revision_missing_iana_returns_422(app) -> None:
    user = _actor(Role.USER, PrincipalType.HUMAN, "user_1")
    gen = _override(app, user)
    next(gen)
    try:
        async with await _client(app) as c:
            resp = await c.post(
                "/api/v1/market-datasets/mds_x/revisions",
                json={
                    "market_data_type": "ohlcv",
                    "payload": {},
                    "timezone_mode": "custom",  # custom without IANA -> TimezoneRequired
                },
            )
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "TIMEZONE_REQUIRED"
    finally:
        next(gen, None)


@pytest.mark.contract
async def test_deprecate_requires_admin(app) -> None:
    user = _actor(Role.USER, PrincipalType.HUMAN, "user_1")
    gen = _override(app, user)
    next(gen)
    try:
        async with await _client(app) as c:
            resp = await c.post(
                "/api/v1/market-datasets/mds_x/deprecate",
                json={"revision_id": "mrev_x"},
            )
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "APPROVAL_REQUIRES_ADMIN"
    finally:
        next(gen, None)


# ---- Idempotent analyze handshake (fake session, no real DB) -----------------


class _FakeResult:
    def __init__(self, value: Any) -> None:
        self._value = value

    def scalar_one_or_none(self) -> Any:
        return self._value

    def scalars(self) -> _FakeResult:
        return self

    def first(self) -> Any:
        return self._value


class _FakeRevision:
    def __init__(self) -> None:
        from entropia.domain.market_data.enums import MarketDataType, MarketRevisionState

        self.revision_id = "mrev_1"
        self.revision_no = 1
        self.revision_state = MarketRevisionState.UPLOADING
        self.market_data_type = MarketDataType.OHLCV
        self.manifest_hash = None


class _FakeRoot:
    def __init__(self) -> None:
        from entropia.domain.lifecycle.enums import DeletionState

        self.entity_id = "mds_1"
        self.entity_type = "market_dataset"
        self.owner_principal_id = "user_1"
        self.current_revision_id = "mrev_1"
        self.row_version = 1
        self.deletion_state = DeletionState.ACTIVE
        self.lifecycle_state = "draft"


class _FakeSession:
    """Minimal async-session double for the analyze idempotency path."""

    def __init__(self, root: _FakeRoot, revision: _FakeRevision) -> None:
        self._root = root
        self._revision = revision
        self.added: list[Any] = []
        self.keys: dict[str, Any] = {}

    async def get(self, model: Any, ident: Any) -> Any:
        name = model.__name__
        if name == "EntityRegistry":
            return self._root if ident == self._root.entity_id else None
        if name == "MarketDatasetRevision":
            return self._revision if ident == self._revision.revision_id else None
        if name == "IdempotencyKey":
            return self.keys.get(ident)
        return None

    def add(self, row: Any) -> None:
        self.added.append(row)
        if type(row).__name__ == "IdempotencyKey":
            self.keys[row.key] = row

    async def execute(self, *_a: Any, **_k: Any) -> _FakeResult:
        return _FakeResult(None)


@pytest.mark.contract
async def test_idempotent_analyze_returns_same_job(app, monkeypatch) -> None:
    root = _FakeRoot()
    revision = _FakeRevision()
    fake = _FakeSession(root, revision)

    # Deterministic job id so both calls return the same value.
    import entropia.infrastructure.queues.enqueue as enqueue_mod

    monkeypatch.setattr(enqueue_mod, "new_id", lambda _p: "job_fixed")
    # Don't actually dispatch to a broker.
    monkeypatch.setattr(enqueue_mod, "send_job", lambda *_a, **_k: None)
    import entropia.apps.api.routes.market_data as route_mod

    monkeypatch.setattr(route_mod.job_enqueue, "send_job", lambda *_a, **_k: None)

    user = _actor(Role.USER, PrincipalType.HUMAN, "user_1")
    app.dependency_overrides[request_context] = lambda: RequestContext(
        session=fake,  # type: ignore[arg-type]
        actor=user,
    )
    try:
        async with await _client(app) as c:
            r1 = await c.post(
                "/api/v1/market-datasets/mds_1/analysis",
                headers={"Idempotency-Key": "k-123"},
            )
            r2 = await c.post(
                "/api/v1/market-datasets/mds_1/analysis",
                headers={"Idempotency-Key": "k-123"},
            )
        assert r1.status_code == 202
        assert r2.status_code == 202
        assert r1.json()["job_id"] == r2.json()["job_id"] == "job_fixed"
    finally:
        app.dependency_overrides.pop(request_context, None)


# ---- F-01 real multipart upload — pure validation before any DB touch -------


@pytest.mark.contract
async def test_upload_rejects_unsupported_file_type_before_db(app) -> None:
    """The extension gate runs before ``_require_root`` — a dummy session that
    never answers a query is enough (mirrors trading-signal contract tests)."""
    user = _actor(Role.USER, PrincipalType.HUMAN, "user_1")
    gen = _override(app, user)
    next(gen)
    try:
        async with await _client(app) as c:
            resp = await c.post(
                "/api/v1/market-datasets/mds_x/raw-uploads",
                files={"file": ("dataset.xlsx", b"not-a-csv", "application/octet-stream")},
            )
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "MARKET_DATA_FILE_TYPE_NOT_ALLOWED"
    finally:
        next(gen, None)


@pytest.mark.contract
async def test_upload_rejects_empty_file_before_db(app) -> None:
    user = _actor(Role.USER, PrincipalType.HUMAN, "user_1")
    gen = _override(app, user)
    next(gen)
    try:
        async with await _client(app) as c:
            resp = await c.post(
                "/api/v1/market-datasets/mds_x/raw-uploads",
                files={"file": ("dataset.csv", b"", "text/csv")},
            )
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "VALIDATION_ERROR"
    finally:
        next(gen, None)
