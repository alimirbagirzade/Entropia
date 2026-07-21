"""BACK-01 / AUTH-04: login issuance is mode-consistent with login acceptance.

The audited failure is "login 200 -> protected 401": dev mode's request pipeline
resolves only ``X-Actor-Id`` (deps.py) and ignores Bearer sessions, yet
``POST /auth/login`` used to mint one anyway. UI gating cannot close that hole —
a direct API call reproduces it — so the rejection is pinned at the API boundary.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from entropia.apps.api.main import create_app
from entropia.config import get_settings

pytestmark = pytest.mark.asyncio

LOGIN_PATH = "/api/v1/auth/login"


async def _post_login(monkeypatch: pytest.MonkeyPatch, mode: str) -> tuple[int, dict]:
    monkeypatch.setenv("AUTH_MODE", mode)
    monkeypatch.setenv("ENTROPIA_ENV", "local")
    get_settings.cache_clear()
    try:
        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                LOGIN_PATH, json={"username": "admin", "password": "irrelevant"}
            )
        return response.status_code, response.json()
    finally:
        get_settings.cache_clear()


async def test_dev_mode_login_is_a_typed_mismatch_not_200(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    status, body = await _post_login(monkeypatch, "dev")

    assert status != 200, "dev mode must never mint a session the pipeline ignores"
    assert status == 409
    assert body["error"]["code"] == "AUTH_MODE_MISMATCH"


async def test_dev_mode_login_never_returns_a_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The whole point: no usable-looking Bearer session may escape in dev mode."""
    _, body = await _post_login(monkeypatch, "dev")

    assert "token" not in body
    assert "session_id" not in body
    # And the rejection itself must not leak credentials or the bootstrap email.
    assert "irrelevant" not in str(body)


async def test_session_mode_login_reaches_the_credential_check(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Session mode is untouched: it proceeds past the gate to real verification.

    The DB is not seeded here, so the correct outcome is the generic
    INVALID_CREDENTIALS — proving the request got past the mode gate rather than
    being short-circuited by it.
    """
    status, body = await _post_login(monkeypatch, "session")

    assert body["error"]["code"] != "AUTH_MODE_MISMATCH"
    assert status == 401
    assert body["error"]["code"] == "INVALID_CREDENTIALS"
