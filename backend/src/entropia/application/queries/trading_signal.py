"""Trading Signal read-side queries (Stage 3c, doc 04 §7, §9).

Two read surfaces:

* ``get_import_report`` — the durable import status + accepted/skipped counts +
  skipped-row evidence for a job (doc 04 ``GetImportReport``).
* ``get_trading_signal`` — the native work object header + current §9.2 revision
  payload + normalized-event summary.

Both are authentication-gated and re-authorize ownership server-side; the report is
scoped to the source asset's owner, the detail to the work object's owner.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from entropia.domain.identity import Actor
from entropia.domain.identity.policy import ensure_can_view, require_authenticated
from entropia.infrastructure.postgres.models import Job
from entropia.infrastructure.postgres.repositories import mainboard as mb_repo
from entropia.infrastructure.postgres.repositories import trading_signal as ts_repo
from entropia.shared.errors import (
    ImportJobNotFoundError,
    WorkObjectNotFoundError,
)

_MAX_SKIPPED_ROWS = 200


async def get_import_report(session: AsyncSession, actor: Actor, *, job_id: str) -> dict[str, Any]:
    """Return the durable import status + evidence for a job (doc 04 §7).

    While the worker is still running there is no normalized revision yet — the job
    status is returned. Once complete, the normalized revision's counts + skipped-row
    report + validation summary are surfaced (skipped rows are capped so a huge file
    cannot blow up the response).
    """
    require_authenticated(actor)
    job = await session.get(Job, job_id)
    if job is None:
        raise ImportJobNotFoundError(f"Import job '{job_id}' not found.")
    ensure_can_view(actor, owner_principal_id=job.actor_principal_id, visibility="private")

    normalized = await ts_repo.get_normalized_revision_for_job(session, job_id)
    if normalized is None:
        return {
            "job_id": job_id,
            "status": str(job.status),
            "normalized_event_revision_id": None,
            "accepted_count": 0,
            "skipped_count": 0,
            "skipped_rows": [],
            "validation_summary": None,
        }
    return {
        "job_id": job_id,
        "status": str(normalized.status),
        "normalized_event_revision_id": normalized.normalized_revision_id,
        "source_asset_id": normalized.source_asset_id,
        "instrument_id": normalized.instrument_id,
        "accepted_count": normalized.accepted_count,
        "skipped_count": normalized.skipped_count,
        "skipped_rows": (normalized.skipped_rows or [])[:_MAX_SKIPPED_ROWS],
        "validation_summary": normalized.validation_summary,
        "content_hash": normalized.content_hash,
    }


async def get_trading_signal(
    session: AsyncSession, actor: Actor, *, root_id: str
) -> dict[str, Any]:
    """Return the Trading Signal work object header + current revision (doc 04 §9.1)."""
    require_authenticated(actor)
    root = await mb_repo.get_work_object_root(session, root_id)
    detail = await mb_repo.get_work_object_detail(session, root_id)
    if root is None or detail is None or str(detail.object_kind) != "trading_signal":
        raise WorkObjectNotFoundError(f"Trading Signal '{root_id}' not found.")
    ensure_can_view(actor, owner_principal_id=root.owner_principal_id, visibility="private")

    revision = None
    if root.current_revision_id is not None:
        revision = await mb_repo.get_work_object_revision(session, root.current_revision_id)

    return {
        "root_id": root.entity_id,
        "object_kind": str(detail.object_kind),
        "owner_principal_id": root.owner_principal_id,
        "lifecycle_state": root.lifecycle_state,
        "deletion_state": str(root.deletion_state),
        "current_revision_id": root.current_revision_id,
        "row_version": root.row_version,
        "current_revision": _revision_projection(revision) if revision is not None else None,
    }


def _revision_projection(revision: Any) -> dict[str, Any]:
    return {
        "revision_id": revision.revision_id,
        "revision_no": revision.revision_no,
        "payload": revision.payload,
        "source_provenance": revision.source_provenance,
        "available_time": (
            revision.available_time.isoformat() if revision.available_time is not None else None
        ),
        "content_hash": revision.content_hash,
    }


__all__ = ["get_import_report", "get_trading_signal"]
