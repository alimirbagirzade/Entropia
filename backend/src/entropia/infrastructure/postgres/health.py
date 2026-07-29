"""Lightweight connectivity probe used by the readiness endpoint."""

from __future__ import annotations

from sqlalchemy import text

from entropia.infrastructure.observability import get_logger
from entropia.infrastructure.postgres.engine import get_engine

log = get_logger("postgres")


async def check_postgres() -> bool:
    try:
        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception as exc:
        # The probe still reports "down" — only the silence changes. Log the
        # exception CLASS, never str(exc): driver errors echo the DSN, which
        # carries the password.
        log.warning("postgres.probe_failed", error_type=type(exc).__name__)
        return False
