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
from sse_starlette.sse import ServerSentEvent
from starlette.requests import Request

from entropia.apps.api.main import create_app
from entropia.apps.api.sse import _sse_frame, requested_cursor
from entropia.config import get_settings

EVENTS_PATH = "/api/v1/events"


def _request(headers: dict[str, str]) -> Request:
    """A bare request carrying only headers — enough for the cursor read, and it
    exercises the real (case-insensitive) Starlette header lookup."""
    scope = {
        "type": "http",
        "method": "GET",
        "path": EVENTS_PATH,
        "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
    }
    return Request(scope)


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


def test_sse_frame_carries_only_the_event_name_and_the_resumption_cursor() -> None:
    """O-21 widened the AUTH-11 envelope by exactly ONE field: the outbox row id,
    which is what a reconnect replays from. Everything else stays out — the id
    names a log row, never an addressable domain object."""
    raw = {
        "id": "obx_00000000000000000000000001",
        "event_type": "backtest_requested",
        "resource_type": "backtest_run",
        "resource_id": "btrun_private_id",
        "correlation_id": "corr_private_id",
    }

    frame = _sse_frame(raw)

    assert frame["event"] == "backtest.run.updated"  # taxonomy name still projected
    assert frame["data"] == "{}"  # minimal, non-sensitive body
    assert frame["id"] == "obx_00000000000000000000000001"  # resumption cursor (O-21)
    assert set(frame) == {"event", "data", "id"}, "the envelope grew a field it must not carry"
    emitted = "".join(frame.values())
    for leaked in ("btrun_private_id", "corr_private_id", "backtest_requested"):
        assert leaked not in emitted, f"raw outbox field leaked into the SSE frame: {leaked}"


def test_sse_frame_without_an_outbox_id_omits_the_cursor() -> None:
    """A frame that cannot be resumed from must not claim it can: an id-less event
    yields no ``id:`` line, so the client's cursor never advances past nothing."""
    frame = _sse_frame({"event_type": "job.updated", "resource_type": "job"})

    assert frame["event"] == "job.updated"
    assert "id" not in frame


@pytest.mark.parametrize(
    "header",
    ["obx_00000000000000000000000001", "  obx_00000000000000000000000001  "],
)
def test_a_well_formed_last_event_id_is_honoured(header: str) -> None:
    """The cursor is what makes a reconnect lossless, so a real one (even with the
    whitespace a proxy may add) must survive intact."""
    assert requested_cursor(_request({"Last-Event-ID": header})) == (
        "obx_00000000000000000000000001"
    )


def test_last_event_id_lookup_is_case_insensitive() -> None:
    """The browser sends ``Last-Event-ID``; HTTP header names are case-insensitive
    and the cursor must not hinge on which casing a client or proxy picked."""
    assert requested_cursor(_request({"last-event-id": "obx_00000000000000000000000009"})) == (
        "obx_00000000000000000000000009"
    )


@pytest.mark.parametrize(
    ("label", "header"),
    [
        ("a foreign id namespace", "corr_00000000000000000000000001"),
        ("an empty value", "   "),
        ("an unbounded string", "obx_" + "x" * 200),
        ("a SQL-ish payload", "obx_1' OR '1'='1"),
    ],
)
def test_an_unusable_last_event_id_is_ignored(label: str, header: str) -> None:
    """A client-supplied header is never trusted into a query: anything that is not
    one of our outbox ids degrades to 'no cursor' (a live-only stream), which is
    exactly the pre-O-21 behaviour — never a partial or attacker-shaped replay."""
    assert requested_cursor(_request({"Last-Event-ID": header})) is None, label


def test_no_last_event_id_means_no_replay() -> None:
    assert requested_cursor(_request({})) is None


def test_the_frame_encodes_to_a_wire_id_line() -> None:
    """The dict is only half the contract — ``EventSourceResponse`` has to put the
    cursor on the WIRE as an ``id:`` line, because that is what a client (and a
    native ``EventSource``) reads to know where to resume from."""
    wire = ServerSentEvent(
        **_sse_frame({"id": "obx_00000000000000000000000001", "resource_type": "agent_task"})
    ).encode()

    assert b"id: obx_00000000000000000000000001" in wire
    assert b"event: agent.task.updated" in wire
