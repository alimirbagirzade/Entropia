"""Embedded System Packages API contract tests (doc 09 §8, §9.3, §9.4, §15).

DI-override style (mirrors test_market_data_contract.py). Admin-gated paths
(activate/deprecate) fail BEFORE any DB access, so a dummy session is enough; the
contract uses a Supervisor (page-eligible per doc 09 §2 but non-Admin) so the
asserted code is the intended ApprovalRequiresAdmin, not a generic page denial.
The resolve path is exercised with a tiny fake session so signature-mismatch /
not-resolved / adapter-incompatible map to their typed error codes.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from entropia.apps.api.deps import RequestContext, request_context
from entropia.domain.esp.enums import ResolverTrustState, RuntimeAdapter
from entropia.domain.identity import Actor
from entropia.domain.lifecycle.enums import ApprovalState, PrincipalType, Role
from entropia.domain.package.enums import PackageValidationState

_SMA_SIG = {
    "params": [{"name": "source", "type": "series"}, {"name": "length", "type": "int"}],
    "return": "series",
}


class _DummySession:
    """Stand-in; gated/boundary paths never touch it."""


def _actor(role: Role | None, ptype: PrincipalType, pid: str | None) -> Actor:
    return Actor(principal_id=pid, principal_type=ptype, role=role)


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


# ---- Activate / deprecate are Admin-only (Supervisor -> 403) ------------------


@pytest.mark.contract
async def test_non_admin_activate_rejected_403(app) -> None:
    gen = _override(app, _actor(Role.SUPERVISOR, PrincipalType.HUMAN, "sup_1"))
    next(gen)
    try:
        async with await _client(app) as c:
            resp = await c.post(
                "/api/v1/embedded-system-packages/pkg_x/activate",
                json={"revision_id": "pkgrev_x", "canonical_key": "ta.sma"},
            )
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "APPROVAL_REQUIRES_ADMIN"
    finally:
        next(gen, None)


@pytest.mark.contract
async def test_agent_activate_rejected_403(app) -> None:
    gen = _override(app, _actor(None, PrincipalType.AGENT, "agent_1"))
    next(gen)
    try:
        async with await _client(app) as c:
            resp = await c.post(
                "/api/v1/embedded-system-packages/pkg_x/activate",
                json={"revision_id": "pkgrev_x", "canonical_key": "ta.sma"},
            )
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "APPROVAL_REQUIRES_ADMIN"
    finally:
        next(gen, None)


@pytest.mark.contract
async def test_non_admin_deprecate_rejected_403(app) -> None:
    gen = _override(app, _actor(Role.USER, PrincipalType.HUMAN, "user_1"))
    next(gen)
    try:
        async with await _client(app) as c:
            resp = await c.post(
                "/api/v1/embedded-system-packages/pkg_x/deprecate",
                json={"canonical_key": "ta.sma", "reason": "superseded"},
            )
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "APPROVAL_REQUIRES_ADMIN"
    finally:
        next(gen, None)


# ---- create rejects legacy package types (CR-01) -----------------------------
# The package kind is fixed to embedded_system server-side; a legacy type can only
# arrive via the generic package path, so this guards the resolve/role surface
# instead. Here we assert an unauthenticated create is rejected before any work.


@pytest.mark.contract
async def test_guest_create_rejected(app) -> None:
    gen = _override(app, Actor.anonymous())
    next(gen)
    try:
        async with await _client(app) as c:
            resp = await c.post(
                "/api/v1/embedded-system-packages",
                json={
                    "canonical_key": "ta.sma",
                    "signature": _SMA_SIG,
                    "runtime_adapter": "pine_v5",
                },
            )
        assert resp.status_code == 401
        assert resp.json()["error"]["code"] == "UNAUTHENTICATED"
    finally:
        next(gen, None)


# ---- resolve path: typed diagnostics (fake session) --------------------------


class _FakeContract:
    def __init__(self) -> None:
        self.contract_id = "espc_1"
        self.canonical_key = "ta.sma"
        self.signature = _SMA_SIG
        self.runtime_adapter = RuntimeAdapter.PINE_V5
        self.warm_up_period = None
        self.timing_semantics = "closed_bar_only"
        self.repaint = False
        self.evidence = {"test_vectors": "seed"}


class _FakeRevision:
    def __init__(self) -> None:
        self.revision_id = "pkgrev_1"
        self.entity_id = "pkg_1"
        self.revision_no = 1
        self.content_hash = "deadbeef"
        self.validation_state = PackageValidationState.PASSED
        self.approval_state = ApprovalState.APPROVED


class _FakeRegistry:
    def __init__(self) -> None:
        self.registry_id = "espr_1"
        self.canonical_key = "ta.sma"
        self.package_entity_id = "pkg_1"
        self.trusted_active_revision_id = "pkgrev_1"
        self.trust_state = ResolverTrustState.TRUSTED_ACTIVE
        self.runtime_adapter = RuntimeAdapter.PINE_V5
        self.registry_version = 2
        self.replacement_revision_id = None


class _FakeSession:
    """Minimal async-session double for the resolve query path."""

    def __init__(self) -> None:
        self._registry = _FakeRegistry()
        self._contract = _FakeContract()
        self._revision = _FakeRevision()

    async def get(self, model: Any, ident: Any) -> Any:
        if model.__name__ == "PackageRevision":
            return self._revision if ident == self._revision.revision_id else None
        return None

    async def execute(self, *_a: Any, **_k: Any) -> Any:
        raise AssertionError("resolve query should use repo helpers, not raw execute here")


def _patch_repo(monkeypatch, *, registry, contract, revision) -> None:
    import entropia.application.queries.esp as q

    async def _get_registry(_session, key):
        return registry if (registry and key == registry.canonical_key) else None

    async def _get_contract(_session, rev_id):
        return contract if (contract and rev_id == "pkgrev_1") else None

    async def _get_revision(_session, rev_id):
        return revision if (revision and rev_id == "pkgrev_1") else None

    monkeypatch.setattr(q.esp_repo, "get_registry_by_key", _get_registry)
    monkeypatch.setattr(q.esp_repo, "get_contract_by_revision", _get_contract)
    monkeypatch.setattr(q.pkg_repo, "get_revision", _get_revision)


@pytest.mark.contract
async def test_resolve_exact_match_returns_pinned_revision(app, monkeypatch) -> None:
    _patch_repo(
        monkeypatch, registry=_FakeRegistry(), contract=_FakeContract(), revision=_FakeRevision()
    )
    app.dependency_overrides[request_context] = lambda: RequestContext(
        session=_FakeSession(),  # type: ignore[arg-type]
        actor=_actor(Role.USER, PrincipalType.HUMAN, "user_1"),
    )
    try:
        async with await _client(app) as c:
            resp = await c.post(
                "/api/v1/embedded-system-packages/resolve",
                json={
                    "parsed_call": {"key": "ta.sma", "signature": _SMA_SIG},
                    "target_runtime": "pine_v5",
                },
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["resolved"] is True
        assert body["revision_id"] == "pkgrev_1"
        assert body["content_hash"] == "deadbeef"
    finally:
        app.dependency_overrides.pop(request_context, None)


@pytest.mark.contract
async def test_resolve_signature_mismatch_returns_typed_code(app, monkeypatch) -> None:
    _patch_repo(
        monkeypatch, registry=_FakeRegistry(), contract=_FakeContract(), revision=_FakeRevision()
    )
    reversed_call = {
        "params": [{"name": "length", "type": "int"}, {"name": "source", "type": "series"}],
        "return": "series",
    }
    app.dependency_overrides[request_context] = lambda: RequestContext(
        session=_FakeSession(),  # type: ignore[arg-type]
        actor=_actor(Role.USER, PrincipalType.HUMAN, "user_1"),
    )
    try:
        async with await _client(app) as c:
            resp = await c.post(
                "/api/v1/embedded-system-packages/resolve",
                json={
                    "parsed_call": {"key": "ta.sma", "signature": reversed_call},
                    "target_runtime": "pine_v5",
                },
            )
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "RESOLVER_SIGNATURE_MISMATCH"
    finally:
        app.dependency_overrides.pop(request_context, None)


@pytest.mark.contract
async def test_resolve_adapter_incompatible_returns_typed_code(app, monkeypatch) -> None:
    _patch_repo(
        monkeypatch, registry=_FakeRegistry(), contract=_FakeContract(), revision=_FakeRevision()
    )
    app.dependency_overrides[request_context] = lambda: RequestContext(
        session=_FakeSession(),  # type: ignore[arg-type]
        actor=_actor(Role.USER, PrincipalType.HUMAN, "user_1"),
    )
    try:
        async with await _client(app) as c:
            resp = await c.post(
                "/api/v1/embedded-system-packages/resolve",
                json={
                    "parsed_call": {"key": "ta.sma", "signature": _SMA_SIG},
                    "target_runtime": "python",
                },
            )
        assert resp.status_code == 409
        assert resp.json()["error"]["code"] == "RESOLVER_ADAPTER_INCOMPATIBLE"
    finally:
        app.dependency_overrides.pop(request_context, None)


@pytest.mark.contract
async def test_resolve_unknown_key_returns_not_resolved(app, monkeypatch) -> None:
    _patch_repo(monkeypatch, registry=None, contract=None, revision=None)
    app.dependency_overrides[request_context] = lambda: RequestContext(
        session=_FakeSession(),  # type: ignore[arg-type]
        actor=_actor(Role.USER, PrincipalType.HUMAN, "user_1"),
    )
    try:
        async with await _client(app) as c:
            resp = await c.post(
                "/api/v1/embedded-system-packages/resolve",
                json={
                    "parsed_call": {"key": "ta.unknown", "signature": _SMA_SIG},
                    "target_runtime": "pine_v5",
                },
            )
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "RESOLVER_NOT_RESOLVED"
    finally:
        app.dependency_overrides.pop(request_context, None)


@pytest.mark.contract
async def test_guest_cannot_resolve(app) -> None:
    """Guests are blocked from the resolver endpoint; only authenticated actors
    (User/Supervisor/Agent) may use trusted system resolvers (doc 09 §2)."""
    gen = _override(app, Actor.anonymous())
    next(gen)
    try:
        async with await _client(app) as c:
            resp = await c.post(
                "/api/v1/embedded-system-packages/resolve",
                json={
                    "parsed_call": {"key": "ta.sma", "signature": _SMA_SIG},
                    "target_runtime": "pine_v5",
                },
            )
        assert resp.status_code == 401
        assert resp.json()["error"]["code"] == "UNAUTHENTICATED"
    finally:
        next(gen, None)
