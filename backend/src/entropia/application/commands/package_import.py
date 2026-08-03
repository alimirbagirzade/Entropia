"""Package import command (S3, doc 08 §9.1/§10/§14, master ref Modül 7 §12).

The reverse of R2c package Export. A caller submits a foreign export manifest; this
command validates it at the boundary, opens a durable ``package_import_job`` row + a
``data``-queue ``jobs`` row (INF-03 ``job_kind`` discriminator) and returns 202. The
worker (``application/jobs/package_import.py``) parses the manifest, re-resolves its
dependencies against the LOCAL ESP registry and creates the DRAFT root — nothing
executable is produced here (CR-09). Idempotent: the same key returns the same job.

G-02 adds the export-schema gate. Import reads v1 (the field is absent — those artifacts
predate it) and v2; a manifest declaring any OTHER version is rejected here, synchronously,
before a durable job opens. Parsing a version this build has never seen would mean guessing
at its fields, and doc 08 §10 is explicit that an import which cannot be understood must
never become a silently executable package.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from entropia.application.idempotency import run_idempotent
from entropia.application.jobs.data_queue import DATA_QUEUE, PACKAGE_IMPORT
from entropia.domain.identity import Actor
from entropia.domain.identity.policy import require_authenticated
from entropia.domain.lifecycle.enums import ActorKind, PackageKind
from entropia.domain.package.export_contract import (
    SUPPORTED_IMPORT_SCHEMA_VERSIONS,
    resolve_import_schema_version,
)
from entropia.infrastructure.postgres.repositories import audit as audit_repo
from entropia.infrastructure.postgres.repositories import package_import as import_repo
from entropia.infrastructure.queues import enqueue as job_enqueue
from entropia.shared.errors import PackageImportManifestInvalid
from entropia.shared.manifest import manifest_hash

_TARGET_TYPE = "package_import_job"


def _coerce_kind(manifest: dict[str, Any]) -> PackageKind:
    """Extract the manifest ``package_kind`` as a domain enum, or 422.

    The durable job row's ``package_kind`` is NOT NULL, so a body that cannot even
    name a valid package kind is rejected synchronously (the worker never opens).
    Deeper structural defects (missing contracts, malformed deps) stay a worker
    ``failed`` outcome — this only guards the row's NOT NULL identity."""
    raw = manifest.get("package_kind")
    if not isinstance(raw, str):
        raise PackageImportManifestInvalid("The manifest is missing a package_kind.")
    try:
        return PackageKind(raw)
    except ValueError as exc:
        raise PackageImportManifestInvalid(
            f"Unknown package_kind '{raw}' in the import manifest."
        ) from exc


def _coerce_schema_version(manifest: dict[str, Any]) -> int:
    """Return the schema version this build may parse the manifest as, or 422.

    Fail-closed on anything outside :data:`SUPPORTED_IMPORT_SCHEMA_VERSIONS`. Doc 08 names
    no error code for an unreadable schema version, so no new taxonomy entry is invented
    here: the shipped ``PACKAGE_IMPORT_MANIFEST_INVALID`` already means "structurally
    unusable at the API boundary", which is exactly what an uninterpretable version is."""
    version = resolve_import_schema_version(manifest)
    if version is None:
        supported = ", ".join(str(v) for v in sorted(SUPPORTED_IMPORT_SCHEMA_VERSIONS))
        raise PackageImportManifestInvalid(
            f"Unsupported export_schema_version "
            f"{manifest.get('export_schema_version')!r}; this build reads {supported}."
        )
    return version


async def submit_package_import(
    session: AsyncSession,
    actor: Actor,
    *,
    manifest: dict[str, Any],
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Open a durable package-import job for a submitted export manifest (202).

    Auth + the light boundary validation run OUTSIDE the idempotent body; only the
    durable writes (the import-job row, the durable ``jobs`` row, audit + outbox) are
    inside ``_op`` so an idempotent replay never re-runs the side effects. Returns the
    import-job id + the durable job id + the queued status.
    """
    require_authenticated(actor)
    if not isinstance(manifest, dict) or not manifest:
        raise PackageImportManifestInvalid("The import manifest must be a non-empty object.")
    # Version FIRST: a manifest this build cannot interpret is refused on those grounds,
    # not on whatever its (possibly re-shaped) package_kind field happens to look like.
    schema_version = _coerce_schema_version(manifest)
    package_kind = _coerce_kind(manifest)
    origin_package_id = manifest.get("package_root_id")
    origin_revision_id = manifest.get("revision_id")
    # F-07 §4.4: the imported package's own name, as the submitted manifest declares it
    # (``commands.package_lifecycle.export_package`` writes "name"). Captured HERE, with
    # the manifest_hash, so the Library Import report can name the job even when it later
    # ends blocked/failed and no local package exists to join against.
    source_name = manifest.get("name")
    digest = manifest_hash(manifest)

    async def _op() -> dict[str, Any]:
        job = job_enqueue.enqueue_job(
            session,
            queue=DATA_QUEUE,
            payload={
                "job_kind": PACKAGE_IMPORT,
                "manifest": manifest,
                "manifest_hash": digest,
                # Provenance, exactly like ``manifest_hash`` beside it: a record of what the
                # BOUNDARY accepted, so a durable job row can be read back later without
                # re-deriving it. The worker deliberately does NOT consume this — it
                # re-derives the version from the manifest itself, so a payload that reached
                # the queue by some other path is still checked (defence in depth).
                "export_schema_version": schema_version,
            },
            actor_principal_id=actor.principal_id,
            idempotency_key=idempotency_key,
            correlation_id=actor.correlation_id,
        )
        import_job = await import_repo.create_import_job(
            session,
            manifest_hash=digest,
            package_kind=package_kind,
            origin_package_id=origin_package_id if isinstance(origin_package_id, str) else None,
            origin_revision_id=origin_revision_id if isinstance(origin_revision_id, str) else None,
            job_id=job.job_id,
            correlation_id=actor.correlation_id,
            created_by_principal_id=actor.principal_id,
            source_package_name=source_name if isinstance(source_name, str) else None,
        )
        await session.flush()
        audit_repo.add_audit_event(
            session,
            event_kind="package.import_requested",
            actor_principal_id=actor.principal_id,
            actor_kind=actor.actor_kind or ActorKind.HUMAN,
            target_entity_id=import_job.import_job_id,
            target_entity_type=_TARGET_TYPE,
            new_state="queued",
            metadata={
                "manifest_hash": digest,
                "origin_package_id": origin_package_id,
                "export_schema_version": schema_version,
            },
            correlation_id=actor.correlation_id,
        )
        audit_repo.add_outbox_event(
            session,
            event_type="resource.changed",
            resource_type=_TARGET_TYPE,
            resource_id=import_job.import_job_id,
            payload={"action": "import_requested", "job_id": job.job_id},
            correlation_id=actor.correlation_id,
        )
        return {
            "import_job_id": import_job.import_job_id,
            "job_id": job.job_id,
            "queue": DATA_QUEUE,
            "status": str(import_job.status),
        }

    return await run_idempotent(
        session,
        key=idempotency_key,
        actor_principal_id=actor.principal_id,
        request_payload={"op": "submit_package_import", "manifest_hash": digest},
        operation=_op,
    )
