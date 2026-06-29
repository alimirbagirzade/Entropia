"""Liveness and readiness probes (Module 20 §11).

- /health/live  : process is up (no dependency checks).
- /health/ready : dependencies reachable (postgres, redis, object storage).
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Response
from pydantic import BaseModel

from entropia.infrastructure.postgres.health import check_postgres
from entropia.infrastructure.redis.client import check_redis
from entropia.infrastructure.s3.client import check_object_storage

router = APIRouter(prefix="/health", tags=["health"])


class LiveResponse(BaseModel):
    status: str = "ok"


class ReadyResponse(BaseModel):
    status: str
    checks: dict[str, str]


@router.get("/live", response_model=LiveResponse)
async def live() -> LiveResponse:
    return LiveResponse(status="ok")


@router.get("/ready", response_model=ReadyResponse)
async def ready(response: Response) -> ReadyResponse:
    pg, rd, obj = await asyncio.gather(
        check_postgres(),
        check_redis(),
        asyncio.to_thread(check_object_storage),
    )
    checks = {
        "postgres": "ok" if pg else "down",
        "redis": "ok" if rd else "down",
        "object_storage": "ok" if obj else "down",
    }
    healthy = all(v == "ok" for v in checks.values())
    if not healthy:
        response.status_code = 503
    return ReadyResponse(status="ok" if healthy else "degraded", checks=checks)
