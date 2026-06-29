"""Central Server-Sent Events endpoint (Module 20 §10).

SSE is a refresh/projection signal, NOT a source of truth. On reconnect the
frontend refetches authoritative state via query endpoints. Stage 0 ships a
heartbeat stream; domain event fan-out (backtest.run.updated, job.updated,
agent.task.updated, resource.changed, audit.event.created) lands in Stage 1+.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse

router = APIRouter(tags=["events"])

HEARTBEAT_SECONDS = 15


async def _event_source(request: Request) -> AsyncIterator[dict[str, str]]:
    while True:
        if await request.is_disconnected():
            break
        yield {"event": "heartbeat", "data": "{}"}
        await asyncio.sleep(HEARTBEAT_SECONDS)


@router.get("/events")
async def events(request: Request) -> EventSourceResponse:
    return EventSourceResponse(_event_source(request))
