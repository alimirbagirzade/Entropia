"""K-01 backward-compat audit CLI — prints the at-risk revision report (READ-ONLY).

Thin wrapper over ``entropia.application.queries.timezone_audit``; the queries live in
the package so they are covered by the integration suite rather than only by this
script. Writes nothing and migrates nothing — see the module docstring there for why a
migration cannot be done honestly.

Usage:
    uv run python scripts/audit_timezone_normalization.py

Honors ``DATABASE_URL`` (same default as the app). Always exits 0: an at-risk finding
is information for a human, not a build failure.
"""

from __future__ import annotations

import asyncio
import os

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from entropia.application.queries.timezone_audit import (
    AtRiskRevision,
    market_revisions_at_risk,
    research_revisions_at_risk,
)

DEFAULT_URL = "postgresql+asyncpg://entropia:entropia@localhost:5432/entropia"


async def _report() -> None:
    url = os.getenv("DATABASE_URL", DEFAULT_URL)
    engine = create_async_engine(url, poolclass=NullPool)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            market = await market_revisions_at_risk(session)
            research = await research_revisions_at_risk(session)
    finally:
        await engine.dispose()

    print("K-01 timezone-normalization audit (READ-ONLY)")
    print(f"database: {url.rsplit('@', 1)[-1]}")
    print()
    _print_section("Market Data revisions at risk", market)
    print()
    _print_section("Research Data revisions at risk", research)
    print()

    total = len(market) + len(research)
    if total == 0:
        print("No at-risk revisions: every consumable revision declares UTC.")
        print("Nothing to re-analyze.")
        return
    print(f"{total} revision(s) at risk.")
    print(
        "Each was ingested before the declared timezone was applied. Re-run Analyze on the "
        "revision to re-parse its raw asset under K-01: a source whose cells already carried "
        "a UTC offset re-verifies unchanged; a naive source either lands the corrected instant "
        "(custom IANA) or blocks with MARKET_DATA_TIMEZONE_UNRESOLVED / "
        "RESEARCH_DATA_TIMEZONE_UNRESOLVED (exchange mode, no identifier to resolve)."
    )


def _print_section(title: str, rows: list[AtRiskRevision]) -> None:
    print(f"## {title}: {len(rows)}")
    for row in rows:
        declared = row.timezone_iana or "(no IANA identifier)"
        print(
            f"  - {row.revision_id}  state={row.revision_state:<16} "
            f"mode={row.timezone_mode:<9} iana={declared}  created={row.created_at}"
        )


if __name__ == "__main__":
    asyncio.run(_report())
