"""Research Data API contract tests (doc 12, AT role-policy/prerequisite/time/async).

DI-override style (mirrors test_market_data_contract.py). Research Data is an
Agent-Workspace page restricted to Admin/Supervisor/Agent (doc 12 §2/§4): Users
and Guests are blocked by the router-level page gate before any handler runs, so
the validation/prerequisite paths below use a Supervisor (page-eligible, non-Admin)
or Admin actor. Auth-gated and boundary-validation paths fail BEFORE DB access, so
a dummy session suffices; the DEPENDENCY_BLOCKED and idempotent-analyze paths use
small fakes.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from entropia.apps.api.deps import RequestContext, request_context
from entropia.domain.identity import Actor
from entropia.domain.lifecycle.enums import DeletionState, PrincipalType, Role


class _DummySession:
    """Stand-in; gated/boundary paths never touch it."""


def _actor(role: Role | None, ptype: PrincipalType, pid: str | None) -> Actor:
    return Actor(principal_id=pid, principal_type=ptype, role=role)


def _supervisor() -> Actor:
    return _actor(Role.SUPERVISOR, PrincipalType.HUMAN, "sup_1")


def _admin() -> Actor:
    return _actor(Role.ADMIN, PrincipalType.HUMAN, "user_admin")


def _override(app: Any, actor: Actor, session: Any | None = None) -> Iterator[None]:
    app.dependency_overrides[request_context] = lambda: RequestContext(
        session=session or _DummySession(),  # type: ignore[arg-type]
        actor=actor,
    )
    try:
        yield
    finally:
        app.dependency_overrides.pop(request_context, None)


async def _client(app: Any) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://t")


# ---- Page access gate (doc 12 §2/§4: Admin/Supervisor/Agent only) -------------


@pytest.mark.contract
async def test_regular_user_blocked_from_page_403(app) -> None:
    """A regular User is blocked from every Research Data endpoint (ACCESS_DENIED)."""
    gen = _override(app, _actor(Role.USER, PrincipalType.HUMAN, "user_1"))
    next(gen)
    try:
        async with await _client(app) as c:
            resp = await c.get("/api/v1/research-datasets")
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "ACCESS_DENIED"
    finally:
        next(gen, None)


@pytest.mark.contract
async def test_guest_blocked_unauthenticated(app) -> None:
    """A Guest (unauthenticated) is blocked by the page gate with 401."""
    gen = _override(app, Actor.anonymous())
    next(gen)
    try:
        async with await _client(app) as c:
            resp = await c.get("/api/v1/research-datasets")
        assert resp.status_code == 401
        assert resp.json()["error"]["code"] == "UNAUTHENTICATED"
    finally:
        next(gen, None)


# ---- Approval / revocation are Admin-only (page-eligible Supervisor -> 403) ----


@pytest.mark.contract
async def test_non_admin_approve_rejected_403(app) -> None:
    gen = _override(app, _supervisor())
    next(gen)
    try:
        async with await _client(app) as c:
            resp = await c.post(
                "/api/v1/research-datasets/rds_x/approve",
                json={"revision_id": "rrev_x"},
            )
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "APPROVAL_REQUIRES_ADMIN"
    finally:
        next(gen, None)


@pytest.mark.contract
async def test_non_admin_revoke_rejected_403(app) -> None:
    gen = _override(app, _supervisor())
    next(gen)
    try:
        async with await _client(app) as c:
            resp = await c.post(
                "/api/v1/research-datasets/rds_x/revoke",
                json={"revision_id": "rrev_x"},
            )
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "APPROVAL_REQUIRES_ADMIN"
    finally:
        next(gen, None)


# ---- Boundary validation (page-eligible Supervisor) --------------------------


@pytest.mark.contract
async def test_create_custom_category_blank_returns_422(app) -> None:
    """Other/Custom with no custom value -> CUSTOM_CATEGORY_REQUIRED (no fallback)."""
    gen = _override(app, _supervisor())
    next(gen)
    try:
        async with await _client(app) as c:
            resp = await c.post(
                "/api/v1/research-datasets",
                json={
                    "market_entity_id": "mds_x",
                    "payload": {},
                    "category": "other_custom",
                    "usage_scope": "research_backtest",
                },
            )
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "CUSTOM_CATEGORY_REQUIRED"
    finally:
        next(gen, None)


@pytest.mark.contract
async def test_create_revision_custom_timezone_missing_iana_422(app) -> None:
    gen = _override(app, _supervisor())
    next(gen)
    try:
        async with await _client(app) as c:
            resp = await c.post(
                "/api/v1/research-datasets/rds_x/revisions",
                json={
                    "payload": {},
                    "category": "open_interest",
                    "usage_scope": "research_backtest",
                    "timezone_mode": "custom",  # custom without IANA -> TIME_POLICY_INVALID
                },
            )
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "TIME_POLICY_INVALID"
    finally:
        next(gen, None)


@pytest.mark.contract
async def test_set_time_policy_fixed_delay_without_delay_422(app) -> None:
    gen = _override(app, _supervisor())
    next(gen)
    try:
        async with await _client(app) as c:
            resp = await c.post(
                "/api/v1/research-datasets/rds_x/time-policy",
                json={
                    "event_time_semantics": "provider_event_timestamp",
                    "available_time_policy": "fixed_delay",  # no delay_seconds -> invalid
                    "timezone_mode": "utc",
                },
            )
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "TIME_POLICY_INVALID"
    finally:
        next(gen, None)


# ---- DEPENDENCY_BLOCKED on create without an approved market (fake session) ----


class _FakeResult:
    def __init__(self, value: Any) -> None:
        self._value = value

    def scalar_one_or_none(self) -> Any:
        return self._value

    def scalars(self) -> _FakeResult:
        return self

    def first(self) -> Any:
        return self._value

    def all(self) -> list[Any]:
        return []


class _NoMarketSession:
    """Session double where the linked market dataset does not resolve -> 409."""

    def __init__(self) -> None:
        self.added: list[Any] = []

    async def get(self, model: Any, ident: Any) -> Any:
        # No EntityRegistry root for the market entity -> resolve raises NotFound.
        return None

    def add(self, row: Any) -> None:
        self.added.append(row)

    async def execute(self, *_a: Any, **_k: Any) -> _FakeResult:
        return _FakeResult(None)


@pytest.mark.contract
async def test_create_without_approved_market_returns_dependency_blocked(app) -> None:
    fake = _NoMarketSession()
    gen = _override(app, _supervisor(), session=fake)
    next(gen)
    try:
        async with await _client(app) as c:
            resp = await c.post(
                "/api/v1/research-datasets",
                json={
                    "market_entity_id": "mds_missing",
                    "payload": {},
                    "category": "open_interest",
                    "usage_scope": "research_backtest",
                },
            )
        assert resp.status_code == 409
        assert resp.json()["error"]["code"] == "DEPENDENCY_BLOCKED"
    finally:
        next(gen, None)


# ---- Idempotent analyze handshake (fake session, no real DB) -----------------


class _FakeRevision:
    def __init__(self) -> None:
        from entropia.domain.research_data.enums import ResearchRevisionState

        self.revision_id = "rrev_1"
        self.revision_no = 1
        self.revision_state = ResearchRevisionState.DRAFT
        self.manifest_hash = None
        self.raw_asset_id = None


class _FakeRoot:
    def __init__(self) -> None:
        self.entity_id = "rds_1"
        self.entity_type = "research_dataset"
        self.owner_principal_id = "user_admin"
        self.current_revision_id = "rrev_1"
        self.row_version = 1
        self.deletion_state = DeletionState.ACTIVE
        self.lifecycle_state = "active"


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
        if name == "ResearchDatasetRevision":
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
    fake = _FakeSession(_FakeRoot(), _FakeRevision())

    import entropia.infrastructure.queues.enqueue as enqueue_mod

    monkeypatch.setattr(enqueue_mod, "new_id", lambda _p: "job_fixed")
    monkeypatch.setattr(enqueue_mod, "send_job", lambda *_a, **_k: None)
    import entropia.apps.api.routes.research_data as route_mod

    monkeypatch.setattr(route_mod.job_enqueue, "send_job", lambda *_a, **_k: None)

    # Admin is page-eligible and may edit any owner's draft -> reaches the
    # idempotent analyze body on the fake root.
    app.dependency_overrides[request_context] = lambda: RequestContext(
        session=fake,  # type: ignore[arg-type]
        actor=_admin(),
    )
    try:
        async with await _client(app) as c:
            r1 = await c.post(
                "/api/v1/research-datasets/rds_1/analysis",
                headers={"Idempotency-Key": "k-123"},
            )
            r2 = await c.post(
                "/api/v1/research-datasets/rds_1/analysis",
                headers={"Idempotency-Key": "k-123"},
            )
        assert r1.status_code == 202
        assert r2.status_code == 202
        assert r1.json()["job_id"] == r2.json()["job_id"] == "job_fixed"
    finally:
        app.dependency_overrides.pop(request_context, None)


# ---- F-02 real multipart upload — pure validation before any DB touch -------


@pytest.mark.contract
async def test_upload_rejects_unsupported_file_type_before_db(app) -> None:
    """The extension gate runs before ``_require_root`` — a Supervisor is
    page-eligible (Users/Guests are blocked at the router gate) and a dummy
    session that never answers a query is enough."""
    gen = _override(app, _supervisor())
    next(gen)
    try:
        async with await _client(app) as c:
            resp = await c.post(
                "/api/v1/research-datasets/rds_x/upload-session",
                files={"file": ("dataset.xlsx", b"not-a-csv", "application/octet-stream")},
            )
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "RESEARCH_DATA_FILE_TYPE_NOT_ALLOWED"
    finally:
        next(gen, None)


@pytest.mark.contract
async def test_upload_rejects_empty_file_before_db(app) -> None:
    gen = _override(app, _supervisor())
    next(gen)
    try:
        async with await _client(app) as c:
            resp = await c.post(
                "/api/v1/research-datasets/rds_x/upload-session",
                files={"file": ("dataset.csv", b"", "text/csv")},
            )
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "VALIDATION_ERROR"
    finally:
        next(gen, None)
