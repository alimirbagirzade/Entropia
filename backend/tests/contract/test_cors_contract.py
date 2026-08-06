"""I-14 — CORS contract: the browser policy is a closed allowlist, not ``"*"``.

Two halves, both infra-free:

- REQUEST side (httpx ASGI preflight): with ``allow_credentials=True`` the
  middleware must approve exactly the headers the backend reads — the OCC
  tokens, ``Idempotency-Key``, auth/context/SSE headers — and reject anything
  else with Starlette's 400 "Disallowed CORS ..." preflight failure.
- STARTUP side (``Settings``): production refuses to boot with an empty or
  wildcard ``API_CORS_ORIGINS``, because Starlette turns ``*`` + credentials
  into "reflect the caller's Origin" rather than a literal ``*``.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

from entropia.apps.api.main import CORS_ALLOWED_HEADERS, CORS_ALLOWED_METHODS
from entropia.config import Settings
from tests.production_profile import PRODUCTION_CREDENTIALS

_ALLOWED_ORIGIN = "http://localhost:5173"  # settings.py default origin list


async def _preflight(app, *, method: str, request_headers: str, origin: str = _ALLOWED_ORIGIN):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        return await client.options(
            "/api/v1/meta",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": method,
                "Access-Control-Request-Headers": request_headers,
            },
        )


# ---- Request side: preflight allowlist ----


@pytest.mark.contract
async def test_cors_preflight_allows_every_header_the_backend_reads(app) -> None:
    """The full set the frontend and API clients actually send — OCC dual-token
    (``If-Match`` + the ``X-*-Version`` variants), ``Idempotency-Key``, auth,
    request-context and the SSE reconnect cursor — clears preflight in one go."""
    resp = await _preflight(
        app,
        method="PATCH",
        request_headers=", ".join(CORS_ALLOWED_HEADERS),
    )
    assert resp.status_code == 200, resp.text
    # Credentialed CORS never answers with a literal "*": the origin is echoed.
    assert resp.headers["Access-Control-Allow-Origin"] == _ALLOWED_ORIGIN
    assert resp.headers["Access-Control-Allow-Credentials"] == "true"

    allowed = {h.strip().lower() for h in resp.headers["Access-Control-Allow-Headers"].split(",")}
    for header in CORS_ALLOWED_HEADERS:
        assert header.lower() in allowed


@pytest.mark.contract
@pytest.mark.parametrize(
    "occ_header",
    ["If-Match", "X-Request-Version", "X-Registry-Version", "Idempotency-Key"],
)
async def test_cors_preflight_allows_each_occ_token_header(app, occ_header: str) -> None:
    """Each concurrency/idempotency header clears preflight on its own, so a
    single mutating call is never blocked by the tightened allowlist."""
    resp = await _preflight(app, method="POST", request_headers=f"content-type, {occ_header}")
    assert resp.status_code == 200, resp.text


@pytest.mark.contract
async def test_cors_preflight_rejects_an_unlisted_header(app) -> None:
    """The point of dropping ``allow_headers=["*"]``: an arbitrary header name
    is no longer mirrored back as approved."""
    resp = await _preflight(app, method="POST", request_headers="content-type, x-not-a-real-header")
    assert resp.status_code == 400
    assert "Disallowed CORS" in resp.text
    assert "headers" in resp.text
    mirrored = resp.headers.get("Access-Control-Allow-Headers", "")
    assert "x-not-a-real-header" not in mirrored.lower()


@pytest.mark.contract
async def test_cors_preflight_rejects_an_unlisted_origin(app) -> None:
    """The origin list stays the primary gate — an unknown site fails even when
    it asks only for allowlisted headers."""
    resp = await _preflight(
        app,
        method="POST",
        request_headers="content-type",
        origin="https://evil.example",
    )
    assert resp.status_code == 400
    assert "origin" in resp.text


@pytest.mark.contract
async def test_cors_allow_methods_is_a_closed_enumeration(app) -> None:
    """``allow_methods`` is pinned, so the advertised verb set is ours rather
    than whatever ``starlette.ALL_METHODS`` happens to hold after an upgrade."""
    resp = await _preflight(app, method="GET", request_headers="content-type")
    assert resp.status_code == 200
    advertised = {
        m.strip().upper() for m in resp.headers["Access-Control-Allow-Methods"].split(",")
    }
    assert advertised == set(CORS_ALLOWED_METHODS)
    # Nothing the routers never declare leaks into the advertised set.
    assert not advertised & {"TRACE", "CONNECT"}


# ---- Startup side: production fail-fast on unpinned origins ----


def test_cors_production_rejects_wildcard_origin() -> None:
    """``*`` + ``allow_credentials=True`` means Starlette reflects ANY caller's
    Origin. Production refuses to construct its settings at all."""
    with pytest.raises(ValidationError, match="API_CORS_ORIGINS must not contain"):
        Settings(ENTROPIA_ENV="production", AUTH_MODE="session", API_CORS_ORIGINS="*")


def test_cors_production_rejects_wildcard_mixed_into_a_real_list() -> None:
    with pytest.raises(ValidationError, match="API_CORS_ORIGINS must not contain"):
        Settings(
            ENTROPIA_ENV="production",
            AUTH_MODE="session",
            API_CORS_ORIGINS="https://app.example.test,*",
        )


@pytest.mark.parametrize("blank", ["", "   ", ",", " , "])
def test_cors_production_rejects_empty_origin_list(blank: str) -> None:
    """Blank/whitespace/comma-only all parse to zero origins — the deployment
    believes it pinned its origins and pinned nothing."""
    with pytest.raises(ValidationError, match="API_CORS_ORIGINS must list at least one"):
        Settings(ENTROPIA_ENV="production", AUTH_MODE="session", API_CORS_ORIGINS=blank)


def test_cors_production_accepts_explicit_origins() -> None:
    # A production Settings expected to SUCCEED must also carry rotated
    # credentials (ADIM 23). The three rejection cases above need no such thing:
    # the CORS validator runs before the credential one, so they still fail on —
    # and still `match=` — the message they are actually about.
    s = Settings(
        ENTROPIA_ENV="production",
        AUTH_MODE="session",
        API_CORS_ORIGINS="https://app.example.test, https://admin.example.test",
        **PRODUCTION_CREDENTIALS,
    )
    assert s.cors_origin_list == ["https://app.example.test", "https://admin.example.test"]


@pytest.mark.parametrize("env", ["local", "staging"])
def test_cors_wildcard_still_allowed_outside_production(env: str) -> None:
    """The gate is deliberately production-scoped: a local dev profile and a
    staging sandbox may still run a permissive origin list without the app
    refusing to boot."""
    s = Settings(ENTROPIA_ENV=env, AUTH_MODE="session", API_CORS_ORIGINS="*")
    assert s.cors_origin_list == ["*"]
