"""Arrange Metrics persistence (Stage 5c, doc 17 §5.1, §9.3).

No commits — the command layer owns the transaction. L1 (parent-before-child):
``create_profile_root`` flushes the root before a revision references it, and
``create_revision`` flushes after adding the child so its id is available in the
same transaction. Registry reads are pure lookups over the seeded
``metric_definition`` table (never the frontend, never a hard-coded list — doc 17
§13).
"""

from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from entropia.domain.metric_profile.enums import MetricAvailabilityStatus, ProfileScope
from entropia.domain.metric_profile.profile import RegistrySnapshot
from entropia.infrastructure.postgres.models.metric_profile import (
    MetricDefinition,
    ResultViewMetricProfileRevision,
    ResultViewMetricProfileRoot,
)
from entropia.shared.ids import new_id

# --------------------------------------------------------------------------- #
# Metric definition registry                                                  #
# --------------------------------------------------------------------------- #


async def list_definitions(
    session: AsyncSession, *, availability: Iterable[str] | None = None
) -> list[MetricDefinition]:
    """Registry rows ordered by ``display_order`` (doc 17 §3, §7). ``availability``
    filters to the given status set; ``None`` returns the whole registry."""
    stmt = select(MetricDefinition).order_by(MetricDefinition.display_order)
    if availability is not None:
        wanted = list(availability)
        stmt = stmt.where(MetricDefinition.availability_status.in_(wanted))
    return list((await session.execute(stmt)).scalars().all())


async def load_registry_snapshot(session: AsyncSession) -> RegistrySnapshot:
    """The selectable order map + full known-code set for Apply validation (doc 17 §11)."""
    rows = list((await session.execute(select(MetricDefinition))).scalars().all())
    selectable_order = {
        row.metric_code: row.display_order
        for row in rows
        if row.availability_status is MetricAvailabilityStatus.SELECTABLE
    }
    known = frozenset(row.metric_code for row in rows)
    return RegistrySnapshot(selectable_order=selectable_order, known=known)


# --------------------------------------------------------------------------- #
# Profile root / revision                                                     #
# --------------------------------------------------------------------------- #


async def get_profile(session: AsyncSession, profile_id: str) -> ResultViewMetricProfileRoot | None:
    return await session.get(ResultViewMetricProfileRoot, profile_id)


async def get_personal_profile(
    session: AsyncSession, owner_principal_id: str
) -> ResultViewMetricProfileRoot | None:
    """The caller's own (scope=user) profile root, if one exists (doc 17 §2, §8.1)."""
    stmt = select(ResultViewMetricProfileRoot).where(
        ResultViewMetricProfileRoot.scope == ProfileScope.USER,
        ResultViewMetricProfileRoot.owner_principal_id == owner_principal_id,
    )
    return (await session.execute(stmt)).scalars().first()


async def create_profile_root(
    session: AsyncSession,
    *,
    scope: ProfileScope,
    owner_principal_id: str | None,
) -> ResultViewMetricProfileRoot:
    """Insert a profile root (row_version=1, no head yet). Flushes before children."""
    root = ResultViewMetricProfileRoot(
        profile_id=new_id("rvmpr"),
        scope=scope,
        owner_principal_id=owner_principal_id,
        lifecycle_state="active",
        current_revision_id=None,
        row_version=1,
    )
    session.add(root)
    await session.flush()
    return root


async def get_revision(
    session: AsyncSession, profile_revision_id: str
) -> ResultViewMetricProfileRevision | None:
    return await session.get(ResultViewMetricProfileRevision, profile_revision_id)


async def create_revision(
    session: AsyncSession,
    *,
    profile_id: str,
    revision_no: int,
    selected_metric_codes: list[str],
    display_order: list[str],
    is_locked: bool,
    registry_version: str,
    config_hash: str,
    previous_revision_id: str | None,
    created_by_principal_id: str | None,
    audit_correlation_id: str | None,
) -> ResultViewMetricProfileRevision:
    """Append an immutable profile revision. Flushes so the id is available."""
    revision = ResultViewMetricProfileRevision(
        profile_revision_id=new_id("rvmprev"),
        profile_id=profile_id,
        revision_no=revision_no,
        selected_metric_codes=selected_metric_codes,
        display_order=display_order,
        is_locked=is_locked,
        metric_definition_registry_version=registry_version,
        config_hash=config_hash,
        previous_revision_id=previous_revision_id,
        created_by_principal_id=created_by_principal_id,
        audit_correlation_id=audit_correlation_id,
    )
    session.add(revision)
    await session.flush()
    return revision


async def max_revision_no(session: AsyncSession, profile_id: str) -> int:
    stmt = select(func.max(ResultViewMetricProfileRevision.revision_no)).where(
        ResultViewMetricProfileRevision.profile_id == profile_id
    )
    current = (await session.execute(stmt)).scalar_one_or_none()
    return int(current) if current is not None else 0


__all__ = [
    "create_profile_root",
    "create_revision",
    "get_personal_profile",
    "get_profile",
    "get_revision",
    "list_definitions",
    "load_registry_snapshot",
    "max_revision_no",
]
