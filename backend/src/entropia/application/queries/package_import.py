"""Package import report read model (S3, doc 08 §9.1/§10/§14).

Owner-scoped reads over the ``package_import_job`` projection for the Library Import
report. A cross-owner or missing job is a 404 (no existence leak).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from entropia.domain.identity import Actor
from entropia.domain.identity.policy import require_authenticated
from entropia.infrastructure.postgres.models import PackageImportJob
from entropia.infrastructure.postgres.repositories import package_import as import_repo
from entropia.shared.errors import PackageImportJobNotFound


def _to_report(row: PackageImportJob) -> dict[str, Any]:
    return {
        "import_job_id": row.import_job_id,
        "status": str(row.status),
        "package_kind": str(row.package_kind),
        "manifest_hash": row.manifest_hash,
        "origin_package_id": row.origin_package_id,
        "origin_revision_id": row.origin_revision_id,
        "result_package_root_id": row.result_package_root_id,
        "diagnostics": row.diagnostics,
        "job_id": row.job_id,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "completed_at": row.completed_at.isoformat() if row.completed_at else None,
    }


async def get_import_report(
    session: AsyncSession, actor: Actor, *, import_job_id: str
) -> dict[str, Any]:
    """One import-job report, owner-scoped. Missing/cross-owner -> 404 (no leak)."""
    require_authenticated(actor)
    row = await import_repo.get_import_job(session, import_job_id)
    if row is None or row.created_by_principal_id != actor.principal_id:
        raise PackageImportJobNotFound()
    return _to_report(row)


async def list_import_reports(
    session: AsyncSession, actor: Actor, *, limit: int = 50
) -> dict[str, Any]:
    """Owner-scoped newest-first import jobs for the Library Import report list."""
    require_authenticated(actor)
    rows = await import_repo.list_import_jobs_for_owner(
        session, owner_principal_id=actor.principal_id or "", limit=limit
    )
    return {"items": [_to_report(r) for r in rows]}
