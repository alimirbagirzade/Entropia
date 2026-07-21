"""The runtime auth mode is a published, non-secret /meta contract.

The frontend cannot pick its auth UI or its request credential correctly without
knowing which mechanism the API actually trusts. Inferring it from "a token
exists in localStorage" is what produced the reported failure: under
``AUTH_MODE=dev`` the server ignores Bearer tokens, so a stored token made the
shell hide the dev actor control and claim the user was signed in while every
protected request resolved anonymous (login 200 -> protected 401).

Also pins the leak boundary: /meta names the MECHANISM and nothing else — no
token, no bootstrap email, no service-token state.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from entropia.config import get_settings

pytestmark = pytest.mark.asyncio

_SECRET_FIELDS = (
    "service_token",
    "bootstrap_admin_email",
    "token",
    "secret",
    "password",
)


async def _meta(app) -> dict:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/meta")
    assert resp.status_code == 200
    return resp.json()


@pytest.mark.parametrize("mode", ["dev", "session"])
async def test_meta_publishes_the_configured_auth_mode(
    monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    monkeypatch.setenv("ENTROPIA_ENV", "local")
    monkeypatch.setenv("AUTH_MODE", mode)
    get_settings.cache_clear()
    try:
        from entropia.apps.api.main import create_app

        body = await _meta(create_app())
        assert body["auth_mode"] == mode
    finally:
        get_settings.cache_clear()


async def test_meta_leaks_no_secret_state(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENTROPIA_ENV", "local")
    monkeypatch.setenv("AUTH_MODE", "session")
    monkeypatch.setenv("ENTROPIA_SERVICE_TOKEN", "svc-secret-token")
    monkeypatch.setenv("ENTROPIA_BOOTSTRAP_ADMIN_EMAIL", "root@entropia.test")
    get_settings.cache_clear()
    try:
        from entropia.apps.api.main import create_app

        body = await _meta(create_app())
        assert set(body) == {"name", "version", "environment", "api_base_path", "auth_mode"}
        serialized = str(body)
        assert "svc-secret-token" not in serialized
        assert "root@entropia.test" not in serialized
        for field in _SECRET_FIELDS:
            assert field not in body
    finally:
        get_settings.cache_clear()
