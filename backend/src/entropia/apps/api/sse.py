"""Central Server-Sent Events endpoint + outbox fan-out (Module 20 §10, Stage 8b).

SSE is a refresh/projection signal, NOT a source of truth (INF-11): on reconnect
the frontend refetches authoritative state via query endpoints, so delivery here
is deliberately loss-tolerant. A per-process poller tails the transactional
outbox by its lexically-sortable ULID id (starting at the boot-time tail — only
NEW events stream; history is a query concern) and fans each event out to every
connected subscriber as a typed SSE event. Marking events published is NOT this
module's job — that durable checkpoint belongs to the scheduler's relay.
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

router = APIRouter(tags=["events"])

HEARTBEAT_SECONDS = 15
_SUBSCRIBER_BUFFER = 256

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


class SseHub:
    """In-process broadcast hub. A slow subscriber's full buffer DROPS events
    (loss-tolerated by contract, INF-11) instead of back-pressuring the poller."""

    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue[dict[str, Any]]] = set()

    def subscribe(self) -> asyncio.Queue[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=_SUBSCRIBER_BUFFER)
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[dict[str, Any]]) -> None:
        self._subscribers.discard(queue)

    def publish(self, event: dict[str, Any]) -> None:
        for queue in list(self._subscribers):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                continue

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
    never reads the body, so the frame carries ONLY that name — never the raw
    outbox dict, whose ``resource_id`` / ``correlation_id`` / ``event_type`` would
    leak internal identifiers to every subscriber. The data field is an empty JSON
    object: enough to be a well-formed SSE frame, nothing a subscriber can mine."""
    return {
        "event": sse_event_name(str(event.get("event_type", "")), event.get("resource_type")),
        "data": "{}",
    }


async def _event_source(request: Request) -> AsyncIterator[dict[str, str]]:
    queue = hub.subscribe()
    try:
        while True:
            if await request.is_disconnected():
                break
            try:
                event = await asyncio.wait_for(queue.get(), timeout=HEARTBEAT_SECONDS)
            except TimeoutError:
                yield {"event": "heartbeat", "data": "{}"}
                continue
            yield _sse_frame(event)
    finally:
        hub.unsubscribe(queue)


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
