"""Lightweight connectivity probe used by the readiness endpoint."""

from __future__ import annotations

from sqlalchemy import text

from entropia.infrastructure.postgres.engine import get_engine


async def check_postgres() -> bool:
    try:
        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
