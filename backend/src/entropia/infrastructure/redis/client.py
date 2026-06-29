"""Async Redis client (queue signalling + lightweight cache, never truth)."""

from __future__ import annotations

from functools import lru_cache

import redis.asyncio as redis

from entropia.config import get_settings


@lru_cache(maxsize=1)
def get_redis() -> redis.Redis:
    settings = get_settings()
    client: redis.Redis = redis.from_url(  # type: ignore[no-untyped-call]
        settings.redis_url, decode_responses=True
    )
    return client


async def check_redis() -> bool:
    try:
        client = get_redis()
        return bool(await client.ping())
    except Exception:
        return False
