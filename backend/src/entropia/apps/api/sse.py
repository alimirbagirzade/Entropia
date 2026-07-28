"""Central Server-Sent Events endpoint + outbox fan-out (Module 20 §10, Stage 8b).

SSE is a refresh/projection signal, NOT a source of truth (INF-11): the frontend
always refetches authoritative state via query endpoints, so a subscriber that
misses a frame self-heals. A per-process poller tails the transactional outbox by
its lexically-sortable ULID id (starting at the boot-time tail — only NEW events
stream to a fresh subscriber; history is a query concern) and fans each event out
to every connected subscriber as a typed SSE event. Marking events published is
NOT this module's job — that durable checkpoint belongs to the scheduler's relay.

O-21 makes the stream RESUMABLE, so a gap is recovered instead of guessed at:

- every data frame carries ``id:`` — the outbox row id it was projected from —
  which is exactly the token a client (or the browser's own ``EventSource``)
  echoes back as ``Last-Event-ID`` on reconnect;
- a reconnect that presents ``Last-Event-ID`` gets the events it missed REPLAYED
  from the outbox before the live feed resumes;
- a slow subscriber whose buffer overflows, an unreplayably large gap, or a
  failed replay read emits an explicit ``stream.resync`` frame. Loss is still
  tolerated by contract — but it is ANNOUNCED, never silent.

The ``id:`` is the only identifier this envelope carries, and it is a deliberate,
minimal widening of the AUTH-11 minimization: a resumable stream needs a cursor,
and an outbox row id names a log row, not a domain resource — it is not
addressable through any endpoint. ``resource_id`` / ``correlation_id`` /
``event_type`` stay off the wire and the body stays an empty JSON object.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Depends, Request
from sse_starlette.sse import EventSourceResponse

from entropia.application.jobs.outbox_relay import fetch_events_after, latest_event_id
from entropia.apps.api.deps import resolve_request_actor
from entropia.domain.identity import Actor
from entropia.domain.identity.policy import require_authenticated
from entropia.infrastructure.observability import get_logger
from entropia.infrastructure.postgres.engine import get_session_factory
from entropia.shared.ids import looks_like_id

router = APIRouter(tags=["events"])

HEARTBEAT_SECONDS = 15
_SUBSCRIBER_BUFFER = 256

# Control frames. Neither belongs to the Module 20 §10 domain taxonomy: they carry
# no resource meaning, so they are dispatched by name and never mapped to a query
# key. ``stream.resync`` means "you are missing events I cannot hand you — refetch
# everything"; it is the audible replacement for a silent drop.
HEARTBEAT_EVENT = "heartbeat"
RESYNC_EVENT = "stream.resync"

# How far back a reconnect may be replayed. Beyond this the gap is answered with a
# single resync instead of a long catch-up burst: a client that far behind is
# cheaper (and more correct) to refetch wholesale than to walk event by event.
REPLAY_LIMIT = 500

# A ``Last-Event-ID`` is only honoured when it has the exact shape we mint outbox
# ids in. A client-supplied string is otherwise ignored (no cursor -> live-only
# stream); it is never echoed back, so a bogus header cannot become stream content.
_EVENT_ID_PREFIX = "obx"

log = get_logger("api.sse")


def sse_event_name(event_type: str, resource_type: str | None) -> str:
    """Project an outbox event onto the Module 20 §10 SSE taxonomy."""
    kind = resource_type or ""
    if kind.startswith("backtest"):
        return "backtest.run.updated"
    if kind == "job":
        return "job.updated"
    if kind.startswith("agent") or kind == "hypothesis_artifact":
        return "agent.task.updated"
    if event_type.startswith("audit."):
        return "audit.event.created"
    return "resource.changed"


class Subscriber:
    """One connected stream's mailbox plus its OVERFLOW flag.

    The flag is what turns a dropped event into a reportable fact: the hub sets it
    when the mailbox is full (it never blocks the poller), and the stream clears it
    by emitting ``stream.resync`` — so the client learns its view has a hole even
    though the events themselves are gone."""

    __slots__ = ("_overflowed", "queue")

    def __init__(self, *, maxsize: int) -> None:
        self.queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=maxsize)
        self._overflowed = False

    def mark_overflowed(self) -> None:
        self._overflowed = True

    def take_overflow(self) -> bool:
        """Read-and-clear: each overflow burst is announced exactly once."""
        overflowed = self._overflowed
        self._overflowed = False
        return overflowed


class SseHub:
    """In-process broadcast hub. A slow subscriber's full buffer drops events
    (loss-tolerated by contract, INF-11) instead of back-pressuring the poller —
    but the drop is RECORDED on that subscriber so its stream can announce it."""

    def __init__(self) -> None:
        self._subscribers: set[Subscriber] = set()

    def subscribe(self) -> Subscriber:
        subscriber = Subscriber(maxsize=_SUBSCRIBER_BUFFER)
        self._subscribers.add(subscriber)
        return subscriber

    def unsubscribe(self, subscriber: Subscriber) -> None:
        self._subscribers.discard(subscriber)

    def publish(self, event: dict[str, Any]) -> None:
        for subscriber in list(self._subscribers):
            try:
                subscriber.queue.put_nowait(event)
            except asyncio.QueueFull:
                subscriber.mark_overflowed()

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)


hub = SseHub()


async def run_outbox_poller(
    stop: asyncio.Event, *, poll_interval_seconds: float, target: SseHub | None = None
) -> None:
    """Tail the outbox and broadcast new events until ``stop`` is set.

    Each iteration opens its own short session; a failing poll (e.g. database
    briefly unreachable) is logged and retried on the next tick — the poller
    never crashes the API process."""
    sink = target or hub
    cursor: str | None = None
    bootstrapped = False
    while not stop.is_set():
        try:
            factory = get_session_factory()
            async with factory() as session:
                if not bootstrapped:
                    cursor = await latest_event_id(session)
                    bootstrapped = True
                events = await fetch_events_after(session, cursor_id=cursor)
            for event in events:
                cursor = event["id"]
                sink.publish(event)
        except Exception as exc:  # keep polling; SSE loss is tolerated (INF-11)
            log.warning("sse.outbox_poll_failed", error=str(exc))
        try:
            await asyncio.wait_for(stop.wait(), timeout=poll_interval_seconds)
        except TimeoutError:
            continue


def _sse_frame(event: dict[str, Any]) -> dict[str, str]:
    """Project an internal outbox event onto a MINIMAL, non-sensitive invalidation
    frame (AUTH-11). The client invalidates by the taxonomy event NAME alone and
    never reads the body, so the frame carries only that name plus the resumption
    cursor — never the raw outbox dict, whose ``resource_id`` / ``correlation_id``
    / ``event_type`` would leak internal identifiers to every subscriber. The data
    field is an empty JSON object: enough to be a well-formed SSE frame, nothing a
    subscriber can mine. ``id`` is the outbox row id (O-21): it is what the client
    replays from, and it identifies a log row rather than any domain object."""
    frame = {
        "event": sse_event_name(str(event.get("event_type", "")), event.get("resource_type")),
        "data": "{}",
    }
    event_id = event.get("id")
    if event_id:
        frame["id"] = str(event_id)
    return frame


def _control_frame(name: str) -> dict[str, str]:
    """A frame with no ``id``: control frames are not resumption points, so they
    must never move the client's cursor past events it has not actually seen."""
    return {"event": name, "data": "{}"}


def requested_cursor(request: Request) -> str | None:
    """The ``Last-Event-ID`` a reconnecting client presents, or None.

    An absent, malformed or foreign value degrades to None — a live-only stream,
    exactly the pre-O-21 behaviour — rather than being trusted into a query."""
    raw = request.headers.get("last-event-id")
    if raw is None:
        return None
    cursor = raw.strip()
    if not looks_like_id(cursor, prefix=_EVENT_ID_PREFIX):
        return None
    return cursor


async def replay_after(
    cursor: str, *, limit: int = REPLAY_LIMIT
) -> tuple[list[dict[str, Any]], bool]:
    """Read what a disconnected subscriber missed: ``(events, resync_required)``.

    Uses a SHORT session opened and closed here — before the live loop starts — so
    the long-lived stream never pins a database connection. Asking for one row more
    than the limit is how an unreplayably large gap is detected without counting the
    whole tail. A failed read is not silent either: it degrades to a resync, so the
    client refetches instead of believing an empty replay meant 'nothing missed'."""
    try:
        factory = get_session_factory()
        async with factory() as session:
            events = await fetch_events_after(session, cursor_id=cursor, limit=limit + 1)
    except Exception as exc:
        log.warning("sse.replay_failed", error=str(exc))
        return [], True
    if len(events) > limit:
        return [], True
    return events, False


async def _event_source(
    request: Request, *, sink: SseHub | None = None
) -> AsyncIterator[dict[str, str]]:
    target = sink or hub
    subscriber = target.subscribe()
    try:
        # Subscribe BEFORE reading the replay: an event published while the replay
        # query is in flight then lands in the mailbox instead of falling into the
        # seam between the two. The overlap is removed below by id, not by luck.
        replayed_through: str | None = None
        cursor = requested_cursor(request)
        if cursor is not None:
            missed, resync_required = await replay_after(cursor, limit=REPLAY_LIMIT)
            if resync_required:
                yield _control_frame(RESYNC_EVENT)
            for event in missed:
                replayed_through = str(event["id"])
                yield _sse_frame(event)

        while True:
            if await request.is_disconnected():
                break
            try:
                event = await asyncio.wait_for(subscriber.queue.get(), timeout=HEARTBEAT_SECONDS)
            except TimeoutError:
                if subscriber.take_overflow():
                    yield _control_frame(RESYNC_EVENT)
                yield _control_frame(HEARTBEAT_EVENT)
                continue
            if subscriber.take_overflow():
                yield _control_frame(RESYNC_EVENT)
            event_id = str(event.get("id") or "")
            if replayed_through is not None and event_id and event_id <= replayed_through:
                continue  # already handed over by the replay — do not send it twice
            yield _sse_frame(event)
    finally:
        target.unsubscribe(subscriber)


async def _authenticated_subscriber(request: Request) -> Actor:
    """SSE handshake authentication (AUTH-11), in BOTH auth modes.

    Resolve the caller under AUTH_MODE with a SHORT-LIVED session that is opened
    and closed HERE — before the stream starts — so the long-lived event stream
    never pins a database connection for its whole lifetime. An anonymous caller is
    rejected (``UnauthenticatedError`` -> 401); a dead Bearer session surfaces as
    ``SESSION_INVALID`` (raised inside the resolver) so the client can run its
    one-shot invalid-session flow. The stream itself carries only a non-sensitive
    invalidation taxonomy, so any authenticated principal may subscribe — there is
    no per-actor authorization beyond "is authenticated".

    Resolving anonymous never issues a query, so an unauthenticated handshake is
    rejected without touching the database at all.
    """
    factory = get_session_factory()
    async with factory() as session:
        actor = await resolve_request_actor(request, session)
    require_authenticated(actor)
    return actor


@router.get("/events")
async def events(
    request: Request, _subscriber: Actor = Depends(_authenticated_subscriber)
) -> EventSourceResponse:
    return EventSourceResponse(_event_source(request))
