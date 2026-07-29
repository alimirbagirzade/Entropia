"""Result export command (Stage 5c, doc-15 deferred; doc 15 §7, §8.5, §9.1, §14).

``RequestResultExport`` materializes a schema-versioned DERIVATIVE of one immutable
Result. V1 is SYNCHRONOUS (the engine is a stub, artifacts are small): one tx builds
the export metadata row — object-storage key + content ``checksum`` + ``schema_version``
+ ``row_count`` — with PROVENANCE = the source Result's ``manifest_hash`` (doc 15
§9.1, §14). The bytes are derived from the persisted immutable artifact, never from
rendered UI rows (doc 15 §8.5), so the checksum is reproducible. An async ExportJob
for large outputs is a tracked later refinement (doc 15 §7). Runs under
``run_idempotent`` so a retried request returns the same export (doc 15 §11).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from entropia.application.idempotency import run_idempotent
from entropia.application.queries import result_access
from entropia.domain.backtest.export import (
    EXPORT_SCHEMA_VERSION,
    ExportType,
    build_object_key,
    compute_export_checksum,
    normalize_export_format,
    normalize_export_type,
)
from entropia.domain.identity import Actor
from entropia.domain.identity.policy import require_authenticated
from entropia.infrastructure.postgres.repositories import audit as audit_repo
from entropia.infrastructure.postgres.repositories import backtest as bt_repo
from entropia.infrastructure.postgres.repositories import export as export_repo
from entropia.shared.errors import AgentDatasetSourceNotApprovedError, BacktestResultNotFoundError
from entropia.shared.ids import new_id

_EXPORT_TARGET = "export_artifact"
_ACTIVE = "active"


async def request_result_export(
    session: AsyncSession,
    actor: Actor,
    *,
    result_id: str,
    export_type: str,
    export_format: str,
    filter_spec: dict[str, Any] | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Materialize a schema-versioned export from an immutable Result (doc 15 §7)."""
    require_authenticated(actor)
    result = await bt_repo.get_result(session, result_id)
    if result is None or result.deletion_state != _ACTIVE:
        raise BacktestResultNotFoundError()
    # Doc 15 §2 keeps "Result view / export" on ONE row: whoever may read an
    # accessible Result may export it when policy permits. So this gate is the SAME
    # composition-view rule the history list/detail/compare use (O-14) — otherwise a
    # grantee sees a card advertising ``allowed_actions.export=True`` and is then
    # denied. Starting a RUN stays owner-only; exporting an existing Result is a read.
    await result_access.ensure_can_view_composition(session, actor, result.workspace_entity_id)
    # Validate the export contract before any mutation (422 on bad type/format).
    canonical_type = normalize_export_type(export_type)
    canonical_format = normalize_export_format(export_format)
    # Doc 15 §3.2 puts ONE extra condition on the agent dataset that the other six
    # types do not carry: it may be composed only from approved / scope-authorized
    # artifacts. The scope half is the composition-view gate just above (shared by
    # every export); the approved half is checked here, before any write.
    if canonical_type is ExportType.AGENT_DATASET:
        await _assert_agent_dataset_sources_approved(session, result_id=result_id, result=result)

    async def _op() -> dict[str, Any]:
        snapshot = await bt_repo.get_manifest_snapshot(session, result_id)
        source_manifest_hash = (
            snapshot.manifest_hash if snapshot is not None else result.manifest_hash
        )
        rows = await export_repo.load_source_rows(
            session, result_id=result_id, export_type=canonical_type
        )
        export_id = new_id("btexp")
        object_key = build_object_key(
            result_id=result_id,
            export_type=canonical_type,
            export_id=export_id,
            fmt=canonical_format,
        )
        checksum = compute_export_checksum(
            export_type=canonical_type,
            fmt=canonical_format,
            schema_version=EXPORT_SCHEMA_VERSION,
            source_manifest_hash=source_manifest_hash,
            rows=rows,
        )
        export = await export_repo.create_export(
            session,
            export_id=export_id,
            result_id=result_id,
            export_type=canonical_type,
            export_format=canonical_format,
            source_manifest_hash=source_manifest_hash,
            object_key=object_key,
            checksum=checksum,
            schema_version=EXPORT_SCHEMA_VERSION,
            row_count=len(rows),
            filter_spec=filter_spec,
            created_by_principal_id=actor.principal_id,
        )
        _emit_export_audit(session, actor, export=export)
        return _projection(export)

    return await run_idempotent(
        session,
        key=idempotency_key,
        actor_principal_id=actor.principal_id,
        request_payload={
            "op": "request_result_export",
            "result_id": result_id,
            "export_type": str(canonical_type),
            "export_format": str(canonical_format),
            "filter_spec": filter_spec,
        },
        operation=_op,
    )


# --------------------------------------------------------------------------- #
# Helpers                                                                     #
# --------------------------------------------------------------------------- #


_APPROVED = "approved"


async def _assert_agent_dataset_sources_approved(
    session: AsyncSession, *, result_id: str, result: Any
) -> None:
    """Doc 15 §3.2: an agent dataset only from APPROVED source artifacts.

    The evidence is the Result's own manifest snapshot, not a re-read of the current
    Package Library: the snapshot records the ``approval_state`` each pinned package
    revision had when the run was admitted, which is what the Result actually
    replayed. Re-reading the library would let a package approved (or un-approved)
    afterwards change the verdict on an immutable Result.

    A Result with no manifest snapshot and no pinned package context passes — there is
    no unapproved source to object to, and refusing would block the export on absence
    of evidence rather than on evidence of a problem.
    """
    snapshot = await bt_repo.get_manifest_snapshot(session, result_id)
    manifest = snapshot.manifest if snapshot is not None else None
    if not isinstance(manifest, dict):
        return
    context = manifest.get("strategy_package_context") or []
    unapproved: list[dict[str, Any]] = []
    for item in context:
        for pinned in (item or {}).get("package_revisions") or []:
            revision = (pinned or {}).get("revision")
            if not isinstance(revision, dict):
                # The pin exists but its revision could not be dereferenced at
                # admission. That is a manifest-resolution concern the worker already
                # owns; it is not evidence of an unapproved package, so it is not
                # reported here.
                continue
            if str(revision.get("approval_state")) != _APPROVED:
                unapproved.append(
                    {
                        "package_revision_id": pinned.get("package_revision_id"),
                        "role": pinned.get("role"),
                        "approval_state": revision.get("approval_state"),
                    }
                )
    if unapproved:
        raise AgentDatasetSourceNotApprovedError(
            details=unapproved,
            scope_type="backtest_result",
            scope_id=result.result_id,
        )


def _projection(export: Any) -> dict[str, Any]:
    return {
        "export_id": export.export_id,
        "result_id": export.result_id,
        "export_type": str(export.export_type),
        "export_format": str(export.export_format),
        "source_manifest_hash": export.source_manifest_hash,
        "object_key": export.object_key,
        "checksum": export.checksum,
        "schema_version": export.schema_version,
        "row_count": export.row_count,
        "status": export.status,
    }


def _emit_export_audit(session: AsyncSession, actor: Actor, *, export: Any) -> None:
    metadata = {
        "export_id": export.export_id,
        "result_id": export.result_id,
        "export_type": str(export.export_type),
        "export_format": str(export.export_format),
        "source_manifest_hash": export.source_manifest_hash,
        "checksum": export.checksum,
        "schema_version": export.schema_version,
        "row_count": export.row_count,
    }
    for event_kind in ("backtest.export_requested", "backtest.export_completed"):
        audit_repo.add_audit_event(
            session,
            event_kind=event_kind,
            actor_principal_id=actor.principal_id,
            actor_kind=actor.actor_kind,
            target_entity_id=export.export_id,
            target_entity_type=_EXPORT_TARGET,
            new_state=export.status,
            correlation_id=actor.correlation_id,
            metadata=metadata,
        )
    audit_repo.add_outbox_event(
        session,
        event_type="backtest.export_completed",
        resource_type=_EXPORT_TARGET,
        resource_id=export.export_id,
        payload={
            "export_id": export.export_id,
            "result_id": export.result_id,
            "export_type": str(export.export_type),
            "object_key": export.object_key,
            "checksum": export.checksum,
            "row_count": export.row_count,
        },
        correlation_id=actor.correlation_id,
    )


__all__ = ["request_result_export"]
