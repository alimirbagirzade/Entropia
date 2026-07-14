"""Durable package-import job repository (doc 08 §9.1/§10/§14, master ref Modül 7 §12).

The ``package_import_job`` row is the reverse-of-Export read model. The submit
command inserts it ``queued``; the worker updates it exactly once to a terminal
status (``succeeded``/``blocked``/``failed``) with the resulting root and diagnostics.
Reads are owner-scoped newest-first for the Library Import report.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from entropia.domain.create_package.enums import PackageImportStatus
from entropia.domain.lifecycle.enums import PackageKind
from entropia.infrastructure.postgres.models import PackageImportJob
from entropia.shared.ids import new_id


async def create_import_job(
    session: AsyncSession,
    *,
    manifest_hash: str,
    package_kind: PackageKind,
    origin_package_id: str | None,
    origin_revision_id: str | None,
    job_id: str | None,
    correlation_id: str | None,
    created_by_principal_id: str | None,
) -> PackageImportJob:
    """Insert a fresh ``queued`` import-job row and return it (no commit)."""
    row = PackageImportJob(
        import_job_id=new_id("pkgimp"),
        manifest_hash=manifest_hash,
        origin_package_id=origin_package_id,
        origin_revision_id=origin_revision_id,
        package_kind=package_kind,
        result_package_root_id=None,
        status=PackageImportStatus.QUEUED,
        diagnostics=None,
        job_id=job_id,
        correlation_id=correlation_id,
        created_by_principal_id=created_by_principal_id,
    )
    session.add(row)
    return row


async def get_import_job(session: AsyncSession, import_job_id: str) -> PackageImportJob | None:
    """Fetch one import-job row by id (None if it does not exist)."""
    return await session.get(PackageImportJob, import_job_id)


async def get_import_job_by_job_id(session: AsyncSession, job_id: str) -> PackageImportJob | None:
    """Fetch the import-job row that a durable ``jobs`` row dispatches (worker path)."""
    stmt = select(PackageImportJob).where(PackageImportJob.job_id == job_id)
    return (await session.execute(stmt)).scalars().first()


async def mark_terminal(
    session: AsyncSession,
    row: PackageImportJob,
    *,
    status: PackageImportStatus,
    result_package_root_id: str | None,
    diagnostics: dict[str, object] | None,
) -> PackageImportJob:
    """Transition a ``queued``/``running`` row to a terminal outcome (worker only)."""
    row.status = status
    row.result_package_root_id = result_package_root_id
    row.diagnostics = diagnostics
    row.completed_at = datetime.now(UTC)
    return row


async def list_import_jobs_for_owner(
    session: AsyncSession,
    *,
    owner_principal_id: str,
    limit: int = 50,
) -> list[PackageImportJob]:
    """Owner-scoped newest-first import jobs for the Library Import report."""
    stmt = (
        select(PackageImportJob)
        .where(PackageImportJob.created_by_principal_id == owner_principal_id)
        .order_by(PackageImportJob.created_at.desc(), PackageImportJob.import_job_id.desc())
        .limit(limit)
    )
    return list((await session.execute(stmt)).scalars().all())
