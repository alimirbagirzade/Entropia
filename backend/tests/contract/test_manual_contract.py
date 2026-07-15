"""User Manual auth-gating contract tests (doc 21 §2, UM-07/UM-16) — no DB.

The admin-only manual write routes must reject non-admin humans, the Agent and
anonymous callers at the ROUTE (before any DB access); menu visibility is never
authorization. Upload type / title validation also rejects before touching the
database, so those run here too.
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


ADMIN = Actor(principal_id="user_admin", principal_type=PrincipalType.HUMAN, role=Role.ADMIN)
USER = Actor(principal_id="user_1", principal_type=PrincipalType.HUMAN, role=Role.USER)
SUPERVISOR = Actor(
    principal_id="user_sup", principal_type=PrincipalType.HUMAN, role=Role.SUPERVISOR
)
AGENT = Actor(principal_id="agent_alpha", principal_type=PrincipalType.AGENT, role=None)


def _override(app, actor: Actor) -> Iterator[None]:
    app.dependency_overrides[request_context] = lambda: RequestContext(
        session=_DummySession(),
        actor=actor,  # type: ignore[arg-type]
    )
    try:
        yield
    finally:
        app.dependency_overrides.pop(request_context, None)


def _client(app) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://t")


_MD_BYTES = b"# Heading\n\nBody.\n"

# The upload route is multipart (F-03) and is gated by its own dedicated test
# below; the JSON write routes stay here.
_WRITE_CALLS = [
    ("post", "/api/v1/admin/manual/documents", {"title": "T", "content": "body"}),
    ("post", "/api/v1/admin/manual/documents/mdoc_x/revisions", {"content": "body"}),
    ("delete", "/api/v1/admin/manual/documents/mdoc_x", None),
]


@pytest.mark.contract
@pytest.mark.parametrize("actor", [USER, SUPERVISOR, AGENT], ids=["user", "supervisor", "agent"])
@pytest.mark.parametrize("method,path,body", _WRITE_CALLS, ids=["create", "revise", "delete"])
async def test_manual_write_routes_are_admin_only(app, actor, method, path, body) -> None:
    gen = _override(app, actor)
    next(gen)
    try:
        async with _client(app) as c:
            resp = await c.request(method.upper(), path, json=body)
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "ADMIN_MANUAL_WRITE_REQUIRED"
    finally:
        next(gen, None)


@pytest.mark.contract
@pytest.mark.parametrize("actor", [USER, SUPERVISOR, AGENT], ids=["user", "supervisor", "agent"])
async def test_manual_upload_is_admin_only(app, actor) -> None:
    # F-03: a valid multipart document passes FastAPI validation, so the 403 is
    # the handler's require_manual_admin (menu visibility is never authorization).
    gen = _override(app, actor)
    next(gen)
    try:
        async with _client(app) as c:
            resp = await c.post(
                "/api/v1/admin/manual/documents:upload",
                files={"file": ("guide.md", _MD_BYTES, "text/markdown")},
            )
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "ADMIN_MANUAL_WRITE_REQUIRED"
    finally:
        next(gen, None)


@pytest.mark.contract
@pytest.mark.parametrize("actor", [USER, SUPERVISOR, AGENT], ids=["user", "supervisor", "agent"])
async def test_manual_restore_is_trash_admin_only(app, actor) -> None:
    gen = _override(app, actor)
    next(gen)
    try:
        async with _client(app) as c:
            resp = await c.post("/api/v1/admin/manual/documents/mdoc_x:restore")
        assert resp.status_code == 403
        assert resp.json()["error"]["code"] == "TRASH_ACCESS_FORBIDDEN"
    finally:
        next(gen, None)


@pytest.mark.contract
async def test_manual_stream_requires_authentication(app) -> None:
    gen = _override(app, Actor.anonymous())
    next(gen)
    try:
        async with _client(app) as c:
            resp = await c.get("/api/v1/manual/stream")
        assert resp.status_code == 401
    finally:
        next(gen, None)


@pytest.mark.contract
async def test_upload_rejects_unsupported_file_type_before_db(app) -> None:
    gen = _override(app, ADMIN)
    next(gen)
    try:
        async with _client(app) as c:
            resp = await c.post(
                "/api/v1/admin/manual/documents:upload",
                files={"file": ("guide.pdf", b"not really a pdf", "application/pdf")},
            )
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "MANUAL_FILE_TYPE_UNSUPPORTED"
    finally:
        next(gen, None)


@pytest.mark.contract
async def test_upload_rejects_non_utf8_document_before_db(app) -> None:
    # F-03 encoding gate: a non-UTF-8 document is rejected at the route before the
    # command touches the manual stream.
    gen = _override(app, ADMIN)
    next(gen)
    try:
        async with _client(app) as c:
            resp = await c.post(
                "/api/v1/admin/manual/documents:upload",
                files={"file": ("guide.md", b"\xff\xfe\x00bad", "text/markdown")},
            )
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "UPLOAD_ENCODING_INVALID"
    finally:
        next(gen, None)


@pytest.mark.contract
async def test_create_rejects_blank_title_before_db(app) -> None:
    gen = _override(app, ADMIN)
    next(gen)
    try:
        async with _client(app) as c:
            resp = await c.post(
                "/api/v1/admin/manual/documents", json={"title": "   ", "content": "body"}
            )
        assert resp.status_code == 422
        assert resp.json()["error"]["code"] == "MANUAL_TITLE_REQUIRED"
    finally:
        next(gen, None)
