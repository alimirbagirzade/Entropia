"""AUTH-11: GET /events authenticates the handshake and minimizes the payload.

The audited hole had two halves, both pinned here without a database:

- ``/events`` had NO actor dependency, so any anonymous client could subscribe.
  Anonymous resolution issues no query, so a rejected handshake needs no DB — we
  assert 401 in BOTH auth modes.
- the stream broadcast the RAW outbox dict (``resource_id``, ``correlation_id``,
  ``event_type`` …) to every subscriber. ``_sse_frame`` must now emit only the
  taxonomy event name, never those internal identifiers.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from entropia.apps.api.main import create_app
from entropia.apps.api.sse import _sse_frame
from entropia.config import get_settings

EVENTS_PATH = "/api/v1/events"


async def _get_events(
    monkeypatch: pytest.MonkeyPatch, mode: str, headers: dict[str, str] | None = None
) -> tuple[int, dict]:
    monkeypatch.setenv("AUTH_MODE", mode)
    monkeypatch.setenv("ENTROPIA_ENV", "local")
    get_settings.cache_clear()
    try:
        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(EVENTS_PATH, headers=headers or {})
        return response.status_code, response.json()
    finally:
        get_settings.cache_clear()


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["dev", "session"])
async def test_anonymous_handshake_is_rejected(monkeypatch: pytest.MonkeyPatch, mode: str) -> None:
    status, body = await _get_events(monkeypatch, mode)
    assert status == 401, "an unauthenticated SSE handshake must be rejected in every mode"
    assert body["error"]["code"] == "UNAUTHENTICATED"


@pytest.mark.asyncio
async def test_session_mode_ignores_a_bare_actor_header(monkeypatch: pytest.MonkeyPatch) -> None:
    """A bare ``X-Actor-Id`` is not a session-mode credential — the deps.py trust
    model ignores it, so the SSE handshake stays anonymous and is rejected."""
    status, body = await _get_events(monkeypatch, "session", {"X-Actor-Id": "user_1"})
    assert status == 401
    assert body["error"]["code"] == "UNAUTHENTICATED"


def test_sse_frame_carries_only_the_event_name_never_the_raw_payload() -> None:
    raw = {
        "id": "obx_0000000000000000000000001",
        "event_type": "backtest_requested",
        "resource_type": "backtest_run",
        "resource_id": "btrun_private_id",
        "correlation_id": "corr_private_id",
    }

    frame = _sse_frame(raw)

    assert frame["event"] == "backtest.run.updated"  # taxonomy name still projected
    assert frame["data"] == "{}"  # minimal, non-sensitive body
    emitted = frame["event"] + frame["data"]
    for leaked in ("obx_0000000000000000000000001", "btrun_private_id", "corr_private_id"):
        assert leaked not in emitted, f"raw outbox field leaked into the SSE frame: {leaked}"
