"""O-21: the SSE stream is resumable and never loses events in silence.

Before this slice ``GET /events`` emitted no ``id:``, ignored ``Last-Event-ID``,
and a slow subscriber's full 256-slot buffer dropped events with nothing on the
wire to say so — the client's only compensation was a blind full refresh.

Pinned here against a real database, through the real generator:

- a reconnect that presents ``Last-Event-ID`` is handed the events it missed,
  in order, each carrying the cursor to resume from next time;
- the live feed does not re-deliver what the replay already handed over;
- a buffer overflow, an unreplayably large gap, and a failed replay read each
  emit ``stream.resync`` — loss stays tolerated (INF-11) but becomes ANNOUNCED.

The stream is driven directly rather than over HTTP: ``_event_source`` is the
whole contract, and a stub request lets the test end the stream deterministically
instead of racing a real socket. Header lookup stays production-faithful (real
Starlette ``Headers``, so case-insensitivity is exercised, not assumed).
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.datastructures import Headers

from entropia.apps.api import sse
from entropia.apps.api.sse import RESYNC_EVENT, SseHub, _event_source
from entropia.infrastructure.postgres.models.audit import OutboxEvent

pytestmark = pytest.mark.integration


def _event_id(n: int) -> str:
    """A deterministic, lexically ordered outbox id. ``new_id`` mixes a millisecond
    stamp with randomness, so two events minted in the same millisecond have no
    guaranteed order — a replay test must not depend on that coin flip."""
    return f"obx_{n:026d}"


def _seed(session: AsyncSession, n: int) -> str:
    event_id = _event_id(n)
    session.add(
        OutboxEvent(
            id=event_id,
            event_type="agent_task_updated",
            resource_type="agent_task",
            resource_id=f"agtask_{n}",
            payload={},
            correlation_id=f"corr_{n}",
        )
    )
    return event_id


def _live(n: int) -> dict[str, Any]:
    """An event as the outbox poller broadcasts it (a projection dict, not a row)."""
    return {
        "id": _event_id(n),
        "event_type": "agent_task_updated",
        "resource_type": "agent_task",
        "resource_id": f"agtask_{n}",
    }


class _StubRequest:
    """Only what ``_event_source`` touches: real Starlette headers (so the
    ``Last-Event-ID`` lookup is the production, case-insensitive one) plus a
    disconnect switch the test flips to end the stream on demand."""

    def __init__(self, headers: dict[str, str] | None = None) -> None:
        self.headers = Headers(headers or {})
        self.disconnected = False

    async def is_disconnected(self) -> bool:
        return self.disconnected


class _SessionFactory:
    """Hand the replay the test's OWN session, so seeded rows are visible without
    committing — while still exercising the real ``fetch_events_after`` SQL rather
    than a stubbed-out result."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def __call__(self) -> _SessionFactory:
        return self

    async def __aenter__(self) -> AsyncSession:
        return self._session

    async def __aexit__(self, *_exc: object) -> bool:
        return False


@pytest.fixture
def replay_session(monkeypatch: pytest.MonkeyPatch, session: AsyncSession) -> AsyncSession:
    monkeypatch.setattr(sse, "get_session_factory", lambda: _SessionFactory(session))
    return session


async def _take(stream: AsyncIterator[dict[str, str]], count: int) -> list[dict[str, str]]:
    """Pull exactly ``count`` frames, failing fast instead of hanging the suite."""
    frames: list[dict[str, str]] = []
    for _ in range(count):
        frames.append(await asyncio.wait_for(anext(stream), timeout=5))
    return frames


async def _wait_subscribed(hub: SseHub) -> None:
    """Publishing before the generator has subscribed would drop the event on the
    floor and prove nothing, so yield to the loop until the mailbox exists."""
    for _ in range(100):
        if hub.subscriber_count == 1:
            return
        await asyncio.sleep(0)
    raise AssertionError("the stream never subscribed to the hub")


@pytest.mark.asyncio
async def test_reconnect_with_last_event_id_replays_the_gap(replay_session: AsyncSession) -> None:
    for n in (1, 2, 3, 4):
        _seed(replay_session, n)
    await replay_session.flush()

    request = _StubRequest({"Last-Event-ID": _event_id(2)})
    stream = _event_source(request, sink=SseHub())  # type: ignore[arg-type]

    frames = await _take(stream, 2)

    # Exactly the two events emitted while the client was away — no loss, and
    # nothing it had already seen before the drop.
    assert [f["id"] for f in frames] == [_event_id(3), _event_id(4)]
    assert {f["event"] for f in frames} == {"agent.task.updated"}

    request.disconnected = True
    with pytest.raises(StopAsyncIteration):
        await asyncio.wait_for(anext(stream), timeout=5)


@pytest.mark.asyncio
async def test_a_fresh_connection_replays_nothing(replay_session: AsyncSession) -> None:
    """No cursor means no history: a first-time subscriber still gets only NEW
    events (history is a query concern), so the replay must not backfill it."""
    _seed(replay_session, 1)
    await replay_session.flush()

    hub = SseHub()
    stream = _event_source(_StubRequest(), sink=hub)  # type: ignore[arg-type]

    frames_task = asyncio.create_task(_take(stream, 1))
    await _wait_subscribed(hub)
    hub.publish(_live(9))

    frames = await asyncio.wait_for(frames_task, timeout=5)
    assert [f["id"] for f in frames] == [_event_id(9)], "a stale row was replayed to a new client"


@pytest.mark.asyncio
async def test_live_feed_does_not_redeliver_what_the_replay_handed_over(
    replay_session: AsyncSession,
) -> None:
    """The generator subscribes BEFORE it reads the replay, so an event published
    during the query lands in both paths. It must reach the client exactly once."""
    for n in (1, 2, 3):
        _seed(replay_session, n)
    await replay_session.flush()

    hub = SseHub()
    stream = _event_source(_StubRequest({"last-event-id": _event_id(1)}), sink=hub)  # type: ignore[arg-type]

    replayed = await _take(stream, 2)
    assert [f["id"] for f in replayed] == [_event_id(2), _event_id(3)]

    hub.publish(_live(3))  # the overlap: already replayed
    hub.publish(_live(4))  # genuinely new

    frames = await _take(stream, 1)
    assert [f["id"] for f in frames] == [_event_id(4)], "a replayed event was sent twice"


@pytest.mark.asyncio
async def test_buffer_overflow_announces_a_resync_instead_of_dropping_silently(
    replay_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sse, "_SUBSCRIBER_BUFFER", 2)
    hub = SseHub()
    stream = _event_source(_StubRequest(), sink=hub)  # type: ignore[arg-type]

    frames_task = asyncio.create_task(_take(stream, 3))
    await _wait_subscribed(hub)
    for n in (1, 2, 3):
        hub.publish(_live(n))  # the third overruns the 2-slot mailbox

    frames = await asyncio.wait_for(frames_task, timeout=5)

    # The third event is gone — that is the contract — but the client is TOLD, so
    # it can refetch instead of rendering a silently stale view.
    assert frames[0]["event"] == RESYNC_EVENT
    assert "id" not in frames[0], "a resync must not advance the client's cursor"
    assert [f["id"] for f in frames[1:]] == [_event_id(1), _event_id(2)]


@pytest.mark.asyncio
async def test_gap_larger_than_the_replay_window_asks_for_a_resync(
    replay_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sse, "REPLAY_LIMIT", 2)
    for n in (1, 2, 3, 4):
        _seed(replay_session, n)
    await replay_session.flush()

    hub = SseHub()
    stream = _event_source(_StubRequest({"Last-Event-ID": _event_id(1)}), sink=hub)  # type: ignore[arg-type]

    frames_task = asyncio.create_task(_take(stream, 2))
    await _wait_subscribed(hub)
    hub.publish(_live(5))
    frames = await asyncio.wait_for(frames_task, timeout=5)

    # Three events missed with a window of two: a partial replay would look
    # complete and hide the hole, so the whole gap is answered with one resync.
    assert frames[0]["event"] == RESYNC_EVENT
    assert [f["id"] for f in frames[1:]] == [_event_id(5)], "the live feed must still resume"


@pytest.mark.asyncio
async def test_a_failed_replay_read_asks_for_a_resync(
    replay_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An empty replay and a broken replay are indistinguishable to the client, so
    the failure must not degrade into 'nothing was missed'."""

    async def _boom(*_args: object, **_kwargs: object) -> list[dict[str, Any]]:
        raise RuntimeError("database unreachable")

    monkeypatch.setattr(sse, "fetch_events_after", _boom)

    stream = _event_source(_StubRequest({"Last-Event-ID": _event_id(1)}), sink=SseHub())  # type: ignore[arg-type]

    frames = await _take(stream, 1)
    assert frames[0]["event"] == RESYNC_EVENT


@pytest.mark.asyncio
async def test_an_unusable_last_event_id_falls_back_to_a_live_only_stream(
    replay_session: AsyncSession,
) -> None:
    """A client-supplied header is never trusted into a query: a foreign or
    oversized value degrades to the pre-O-21 behaviour (live events only)."""
    for n in (1, 2, 3):
        _seed(replay_session, n)
    await replay_session.flush()

    hub = SseHub()
    stream = _event_source(_StubRequest({"Last-Event-ID": "corr_not_an_outbox_cursor"}), sink=hub)  # type: ignore[arg-type]

    frames_task = asyncio.create_task(_take(stream, 1))
    await _wait_subscribed(hub)
    hub.publish(_live(7))
    frames = await asyncio.wait_for(frames_task, timeout=5)

    assert [f["id"] for f in frames] == [_event_id(7)], "a bogus cursor triggered a replay"
