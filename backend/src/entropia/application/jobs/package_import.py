"""Package import job body (S3, doc 08 §9.1/§10/§14, master ref Modül 7 §12).

Runs on the ``data`` queue. The reverse of package Export:

    load job + manifest -> validate structure -> re-resolve every declared dependency
    against the LOCAL ESP registry -> create a NEW local DRAFT package root with
    ``origin_package_id`` provenance -> advance the durable job + the import projection.

Outcome mapping (never an exception for a *ran-but-unusable* import — that is a terminal
result row, doc 08 §10):

* ``succeeded`` — every dependency resolved -> a clean DRAFT root (validation PENDING),
  its dependency snapshot re-pinned to the LOCAL revisions (P4/L5).
* ``blocked``   — at least one unresolved dependency -> a DRAFT root created FAILED-
  validation (never executable) with the missing calls in ``diagnostics``.
* ``failed``    — the manifest is structurally unparseable -> no package is created.

A hard infra read error (missing job row) is raised so Dramatiq retries; a bad manifest
is a durable ``failed`` result, not a retry. The worker session scope commits.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from entropia.domain.create_package.enums import PackageImportStatus
from entropia.domain.esp.enums import ResolverTrustState
from entropia.domain.lifecycle.enums import (
    ActorKind,
    ApprovalState,
    JobStatus,
    PackageKind,
)
from entropia.domain.package.enums import PackageValidationState
from entropia.infrastructure.postgres.models import Job
from entropia.infrastructure.postgres.repositories import audit as audit_repo
from entropia.infrastructure.postgres.repositories import esp as esp_repo
from entropia.infrastructure.postgres.repositories import package_import as import_repo
from entropia.infrastructure.postgres.repositories import packages as pkg_repo

_TARGET_TYPE = "package_import_job"
# Honest import-resolution boundary (doc 08 §10): an export dependency snapshot pins
# revisions, NOT per-call signatures, so import cannot re-run the full signature/adapter
# match. It resolves by TRUSTED-KEY AVAILABILITY — a canonical key must map to a locally
# trusted-active resolver whose revision is PASSED + APPROVED — and re-pins to that local
# revision (P4/L5). A key absent / not trusted locally blocks. The imported package is
# created PENDING and must still pass its OWN Pre-Check before it can ever execute, so the
# deferred signature check is never a silent-execution risk.
_NOT_RESOLVED = "RESOLVER_NOT_RESOLVED"


def _declared_calls(dependency_snapshot: Any) -> list[str]:
    """The canonical keys the manifest's dependency snapshot pins (order-preserving)."""
    if not isinstance(dependency_snapshot, dict):
        return []
    resolved = dependency_snapshot.get("resolved")
    if not isinstance(resolved, list):
        return []
    keys: list[str] = []
    for ref in resolved:
        if not isinstance(ref, dict):
            continue
        key = ref.get("canonical_key") or ref.get("call")
        if isinstance(key, str) and key:
            keys.append(key)
    return keys


async def _reresolve(
    session: AsyncSession, keys: list[str]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Re-resolve each declared key by trusted-key availability in the LOCAL registry.

    Returns ``(resolved_refs, missing_calls)``. A key resolves iff it maps to a locally
    TRUSTED_ACTIVE resolver whose pinned revision is PASSED + APPROVED; the ref then pins
    that LOCAL revision (never name-only, P4/L5). Anything else is a missing call with a
    RESOLVER_NOT_RESOLVED code — the signature/adapter match is deferred to the imported
    package's own Pre-Check (see the module boundary note)."""
    resolved_refs: list[dict[str, Any]] = []
    missing_calls: list[dict[str, Any]] = []
    for key in keys:
        entry = await esp_repo.get_registry_by_key(session, key)
        revision = (
            await pkg_repo.get_revision(session, entry.trusted_active_revision_id)
            if entry is not None and entry.trusted_active_revision_id is not None
            else None
        )
        resolvable = (
            entry is not None
            and entry.trust_state == ResolverTrustState.TRUSTED_ACTIVE
            and revision is not None
            and revision.validation_state == PackageValidationState.PASSED
            and revision.approval_state == ApprovalState.APPROVED
        )
        if not resolvable or revision is None or entry is None:
            missing_calls.append(
                {
                    "call": key,
                    "code": _NOT_RESOLVED,
                    "message": f"No trusted local resolver for '{key}'.",
                }
            )
            continue
        contract = await esp_repo.get_contract_by_revision(session, revision.revision_id)
        resolved_refs.append(
            {
                "call": key,
                "canonical_key": key,
                "embedded_entity_id": entry.package_entity_id,
                "embedded_revision_id": revision.revision_id,
                "content_hash": revision.content_hash,
                "runtime_adapter": str(contract.runtime_adapter) if contract else None,
                "registry_version": entry.registry_version,
            }
        )
    return resolved_refs, missing_calls


def _manifest_defect(manifest: dict[str, Any]) -> str | None:
    """A structural reason the manifest cannot become a package, or None if usable."""
    for field in ("input_contract", "output_contract", "dependency_snapshot"):
        if not isinstance(manifest.get(field), dict):
            return f"missing_or_invalid_{field}"
    return None


async def run_import(session: AsyncSession, job_id: str) -> dict[str, Any]:
    """Execute the durable package-import job. The ``jobs`` row is the source of truth.

    Returns a JSON-safe result reference; does not commit (the worker scope commits).
    """
    job = await session.get(Job, job_id)
    if job is None:
        raise ValueError(f"Job '{job_id}' not found.")
    import_row = await import_repo.get_import_job_by_job_id(session, job_id)
    if import_row is None:
        raise ValueError(f"Import job for '{job_id}' not found.")

    job.status = JobStatus.RUNNING
    job.started_at = datetime.now(UTC)
    import_row.status = PackageImportStatus.RUNNING

    payload = job.payload or {}
    manifest = payload.get("manifest")
    manifest = manifest if isinstance(manifest, dict) else {}

    defect = _manifest_defect(manifest)
    if defect is not None:
        return await _finish(
            session,
            job,
            import_row,
            status=PackageImportStatus.FAILED,
            result_root_id=None,
            diagnostics={"reason": defect},
        )

    keys = _declared_calls(manifest["dependency_snapshot"])
    resolved_refs, missing_calls = await _reresolve(session, keys)
    blocked = bool(missing_calls)

    input_contract = dict(manifest["input_contract"])
    output_contract = dict(manifest["output_contract"])
    origin_package_id = (
        manifest.get("package_root_id")
        if isinstance(manifest.get("package_root_id"), str)
        else None
    )
    rationale = manifest.get("rationale_family_snapshot")
    dependency_snapshot: dict[str, Any] = {
        "resolved": resolved_refs,
        "source": "import",
        "origin_package_id": origin_package_id,
    }
    if blocked:
        dependency_snapshot["missing"] = missing_calls
    validation_summary = (
        {"import_status": "blocked", "missing_dependencies": missing_calls} if blocked else None
    )

    root, detail, _revision = await pkg_repo.create_package(
        session,
        owner_principal_id=job.actor_principal_id,
        created_by_principal_id=job.actor_principal_id,
        package_kind=PackageKind(str(import_row.package_kind)),
        input_contract=input_contract,
        output_contract=output_contract,
        dependency_snapshot=dependency_snapshot,
        rationale_family_snapshot=rationale if isinstance(rationale, dict) else None,
        validation_state=(
            PackageValidationState.FAILED if blocked else PackageValidationState.PENDING
        ),
        approval_state=ApprovalState.DRAFT,
        change_note="Imported from export manifest.",
    )
    detail.origin_package_id = origin_package_id
    if validation_summary is not None:
        _revision.validation_summary = validation_summary
    await session.flush()

    status = PackageImportStatus.BLOCKED if blocked else PackageImportStatus.SUCCEEDED
    diagnostics: dict[str, Any] = {"resolved_count": len(resolved_refs)}
    if blocked:
        diagnostics["missing_dependencies"] = missing_calls
    return await _finish(
        session,
        job,
        import_row,
        status=status,
        result_root_id=root.entity_id,
        diagnostics=diagnostics,
    )


async def _finish(
    session: AsyncSession,
    job: Job,
    import_row: Any,
    *,
    status: PackageImportStatus,
    result_root_id: str | None,
    diagnostics: dict[str, Any] | None,
) -> dict[str, Any]:
    """Mark the import projection + durable job terminal and emit audit + outbox."""
    await import_repo.mark_terminal(
        session,
        import_row,
        status=status,
        result_package_root_id=result_root_id,
        diagnostics=diagnostics,
    )
    audit_repo.add_audit_event(
        session,
        event_kind="package.imported",
        actor_principal_id=job.actor_principal_id,
        actor_kind=ActorKind.SYSTEM_SERVICE,
        target_entity_id=import_row.import_job_id,
        target_entity_type=_TARGET_TYPE,
        new_state=str(status),
        correlation_id=job.correlation_id,
        metadata={"result_package_root_id": result_root_id},
    )
    audit_repo.add_outbox_event(
        session,
        event_type="resource.changed",
        resource_type=_TARGET_TYPE,
        resource_id=import_row.import_job_id,
        payload={
            "action": "import_completed",
            "status": str(status),
            "result_package_root_id": result_root_id,
        },
        correlation_id=job.correlation_id,
    )
    job.status = JobStatus.SUCCEEDED
    job.finished_at = datetime.now(UTC)
    result = {
        "import_job_id": import_row.import_job_id,
        "status": str(status),
        "result_package_root_id": result_root_id,
    }
    job.result_ref = result
    return result
