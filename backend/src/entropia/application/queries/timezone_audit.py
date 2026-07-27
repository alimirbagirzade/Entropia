"""K-01 backward-compat audit — revisions ingested under the silent-UTC assumption.

READ-ONLY. Before K-01 the ingest parse path ignored the declared timezone and read
every NAIVE source timestamp as UTC, so a revision declaring ``custom`` with a non-UTC
IANA identifier — or ``exchange``, which carries no identifier at all — was stored at
the wrong instant while still auto-verifying.

Why this is an audit and not a migration
----------------------------------------
Whether a given revision is actually wrong depends on the RAW bytes, not the database:
a source whose cells already carried a UTC offset parsed correctly even under the old
code; only a naive-cell source was shifted. That fact lives in object storage, so these
queries report revisions that are AT RISK and must be re-analyzed to be trusted. They
deliberately do not guess, and they mutate nothing.

``scripts/audit_timezone_normalization.py`` is the CLI wrapper that prints the report.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# States whose data is trusted downstream: VERIFIED can be approved, APPROVED feeds
# research/backtests, and a DEPRECATED / APPROVAL_REVOKED revision may still be pinned
# by a completed run's manifest. DRAFT / ANALYZING / NEEDS_REVIEW / REJECTED are not at
# risk because nothing consumes them.
CONSUMABLE_MARKET_STATES = ("verified", "approved", "deprecated")
CONSUMABLE_RESEARCH_STATES = ("verified", "approved", "approval_revoked")

# Identifiers that resolve to UTC: those revisions were read as UTC and were therefore
# correct by accident, so they need no re-analysis.
_UTC_EQUIVALENT_IANA = ("UTC", "Etc/UTC", "Etc/GMT", "Etc/Zulu", "Universal", "Zulu")

MARKET_AT_RISK_SQL = """
SELECT r.revision_id      AS revision_id,
       r.entity_id        AS entity_id,
       r.revision_state   AS revision_state,
       r.timezone_mode    AS timezone_mode,
       r.timezone_iana    AS timezone_iana,
       r.created_at       AS created_at
  FROM market_dataset_revision r
 WHERE r.revision_state = ANY(:states)
   AND (
         r.timezone_mode = 'exchange'
      OR (r.timezone_mode = 'custom'
          AND COALESCE(r.timezone_iana, '') <> ALL(:utc_equivalents))
       )
 ORDER BY r.created_at DESC
"""

RESEARCH_AT_RISK_SQL = """
SELECT r.revision_id             AS revision_id,
       r.entity_id               AS entity_id,
       r.revision_state          AS revision_state,
       r.source_timezone_mode    AS timezone_mode,
       r.source_timezone_iana    AS timezone_iana,
       r.created_at              AS created_at
  FROM research_dataset_revision r
 WHERE r.revision_state = ANY(:states)
   AND (
         r.source_timezone_mode = 'exchange'
      OR (r.source_timezone_mode = 'custom'
          AND COALESCE(r.source_timezone_iana, '') <> ALL(:utc_equivalents))
       )
 ORDER BY r.created_at DESC
"""


@dataclass(frozen=True, slots=True)
class AtRiskRevision:
    """One revision whose stored instants may be shifted by its declared offset."""

    revision_id: str
    entity_id: str
    revision_state: str
    timezone_mode: str
    timezone_iana: str | None
    created_at: datetime


async def market_revisions_at_risk(session: AsyncSession) -> list[AtRiskRevision]:
    """Consumable market revisions whose declared timezone was never applied."""
    return await _run(session, MARKET_AT_RISK_SQL, CONSUMABLE_MARKET_STATES)


async def research_revisions_at_risk(session: AsyncSession) -> list[AtRiskRevision]:
    """Consumable research revisions whose declared source timezone was never applied."""
    return await _run(session, RESEARCH_AT_RISK_SQL, CONSUMABLE_RESEARCH_STATES)


async def _run(session: AsyncSession, sql: str, states: tuple[str, ...]) -> list[AtRiskRevision]:
    result = await session.execute(
        text(sql),
        {"states": list(states), "utc_equivalents": list(_UTC_EQUIVALENT_IANA)},
    )
    return [_row(row) for row in result.mappings().all()]


def _row(row: Any) -> AtRiskRevision:
    return AtRiskRevision(
        revision_id=row["revision_id"],
        entity_id=row["entity_id"],
        revision_state=str(row["revision_state"]),
        timezone_mode=str(row["timezone_mode"]),
        timezone_iana=row["timezone_iana"],
        created_at=row["created_at"],
    )


__all__ = [
    "MARKET_AT_RISK_SQL",
    "RESEARCH_AT_RISK_SQL",
    "AtRiskRevision",
    "market_revisions_at_risk",
    "research_revisions_at_risk",
]
