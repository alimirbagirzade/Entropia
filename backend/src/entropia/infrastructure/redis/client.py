"""Async Redis client (queue signalling + lightweight cache, never truth)."""

from __future__ import annotations

from functools import lru_cache

import redis.asyncio as redis

from entropia.config import get_settings
from entropia.infrastructure.observability import get_logger

log = get_logger("redis")


@lru_cache(maxsize=1)
def get_redis() -> redis.Redis:
    settings = get_settings()
    client: redis.Redis = redis.from_url(settings.redis_url, decode_responses=True)
    return client


async def check_redis() -> bool:
    try:
        client = get_redis()
        return bool(await client.ping())
    except Exception as exc:
        # The probe still reports "down" — only the silence changes. Log the
        # exception CLASS, never str(exc): redis errors quote the connection
        # URL, which carries the password.
        log.warning("redis.probe_failed", error_type=type(exc).__name__)
        return False
