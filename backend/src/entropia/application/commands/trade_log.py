"""Trade Log commands (Stage 3d, doc 05 §8, §9, §10; doc 03 Trade Log save path).

A Trade Log is a NATIVE work object (``object_kind=trade_log``): its root/revision
ARE the 3a ``work_object_root`` / ``work_object_revision`` (no mirror revision,
unlike Strategy). These commands therefore REUSE the 3a Mainboard repo + commands
and add only the source-import plane on top.

Command chain (doc 05 §10.3):

    upload_source_asset         -> immutable source_asset (raw bytes + checksum)
    request_trade_log_import    -> durable jobs row (data queue, CR-09); worker
                                   produces a canonical_trade_record_batch
    create_trade_log_and_attach -> validate §10.2 config + require a succeeded,
                                   non-empty record batch -> create native work
                                   object + pin the batch -> (Save & Add) attach onto
                                   the Mainboard (REUSE 3a attach_mainboard_item)
    create_trade_log_revision   -> append an immutable revision N+1; NEVER
                                   auto-repins the Mainboard item (Implementation
                                   Rule 10)

Pin (``Use This Revision``) and soft-delete REUSE 3a's
``patch_mainboard_item(pin_revision)`` / ``soft_delete_work_object`` directly
(doc 05 §8: no duplicate Trade Log endpoints — a Trade Log is a work object, CR-01).

Trade Log is HISTORICAL data (doc 05 §10.4): the work object revision carries
``available_time=None`` — unlike a Trading Signal, there is no per-event
anti-lookahead availability contract; the backtest reads the record timestamps
directly. Every mutation runs in ONE request transaction and NEVER commits.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from entropia.application.commands import mainboard as mb_cmd
from entropia.application.idempotency import run_idempotent
from entropia.application.jobs.data_queue import TRADE_LOG_IMPORT
from entropia.application.queries import mainboard as mb_query
from entropia.domain.identity import Actor
from entropia.domain.identity.policy import ensure_can_edit, require_authenticated
from entropia.domain.importing.column_mapping import (
    BLOCKER_AMBIGUOUS_COLUMN_MAPPING,
    BLOCKER_INVALID_COLUMN_MAPPING,
)
from entropia.domain.lifecycle.enums import DeletionState
from entropia.domain.mainboard.enums import MainboardItemKind
from entropia.domain.trade_log.compiler import (
    CODE_EVENT_MODEL_CONFLICT,
    CODE_PRICE_CONTEXT_CONFLICT,
    compute_config_hash,
    config_to_dict,
    validate_trade_log_config,
)
from entropia.domain.trade_log.config import TradeLogConfig
from entropia.domain.trade_log.enums import RecordBatchStatus
from entropia.domain.trade_log.records import (
    BLOCKER_NO_ACCEPTED_TRADE_RECORDS,
    BLOCKER_REQUIRED_COLUMN_MISSING,
    BLOCKER_TIMEZONE_INVALID,
)
from entropia.infrastructure.postgres.models import (
    CanonicalTradeRecordBatch,
    EntityRegistry,
    WorkObjectRoot,
)
from entropia.infrastructure.postgres.repositories import audit as audit_repo
from entropia.infrastructure.postgres.repositories import mainboard as mb_repo
from entropia.infrastructure.postgres.repositories import source_asset as asset_repo
from entropia.infrastructure.postgres.repositories import trade_log as tl_repo
from entropia.infrastructure.queues import enqueue as job_enqueue
from entropia.infrastructure.s3 import datasets
from entropia.shared.errors import (
    AmbiguousColumnMappingError,
    EventModelPolicyConflictError,
    FileTypeNotAllowedError,
    ImportNotReadyError,
    InvalidColumnMappingError,
    NoAcceptedTradeRecordsError,
    RequiredColumnMissingError,
    SourceAssetNotFoundError,
    SourceFileRequiredError,
    TimezoneRequired,
    TradeLogPriceContextConflictError,
    TradeLogValidationFailedError,
    TradeRecordBatchNotFoundError,
    WorkObjectNotFoundError,
    WorkObjectRevisionConflictError,
)
from entropia.shared.ids import new_id

_DATA_QUEUE = "data"
_WORK_OBJECT_TARGET = "work_object"
_SOURCE_ASSET_TARGET = "source_asset"
_KIND = MainboardItemKind.TRADE_LOG
_ALLOWED_EXTENSIONS = (".txt", ".csv")


# --------------------------------------------------------------------------- #
# 1. Upload immutable source asset                                            #
# --------------------------------------------------------------------------- #


async def upload_source_asset(
    session: AsyncSession,
    actor: Actor,
    *,
    content: bytes,
    content_type: str | None = None,
    original_filename: str | None = None,
    draft_id: str | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Store an immutable raw TXT/CSV source asset (doc 05 §8, §10.3).

    Content-addressed: an identical re-upload by the same owner returns the prior
    asset (idempotent, TL-15) rather than creating a duplicate. The bytes go to
    object storage; the immutable metadata row is the evidence.
    """
    require_authenticated(actor)
    _validate_file_type(original_filename)
    digest = datasets.content_digest(content)

    existing = await asset_repo.find_source_asset_by_hash(
        session, owner_principal_id=actor.principal_id, raw_asset_hash=digest
    )
    if existing is not None:
        return {
            "source_asset_id": existing.source_asset_id,
            "raw_asset_hash": existing.raw_asset_hash,
            "size_bytes": existing.size_bytes,
            "deduplicated": True,
        }

    async def _op() -> dict[str, Any]:
        source_asset_id = new_id("srcasset")
        object_key, stored_digest = datasets.put_source_asset_bytes(
            source_asset_id, content, content_type=content_type
        )
        asset = await asset_repo.create_source_asset(
            session,
            source_asset_id=source_asset_id,
            owner_principal_id=actor.principal_id,
            object_key=object_key,
            raw_asset_hash=stored_digest,
            size_bytes=len(content),
            content_type=content_type,
            original_filename=original_filename,
            draft_id=draft_id,
            uploaded_by_principal_id=actor.principal_id,
        )
        _audit_and_outbox(
            session,
            actor,
            event_kind="trade_log.source_uploaded",
            target_type=_SOURCE_ASSET_TARGET,
            target_entity_id=asset.source_asset_id,
            payload={"raw_asset_hash": stored_digest, "size_bytes": len(content)},
        )
        return {
            "source_asset_id": asset.source_asset_id,
            "raw_asset_hash": stored_digest,
            "size_bytes": len(content),
            "deduplicated": False,
        }

    return await run_idempotent(
        session,
        key=idempotency_key,
        actor_principal_id=actor.principal_id,
        request_payload={"op": "upload_source_asset", "raw_asset_hash": digest},
        operation=_op,
    )


# --------------------------------------------------------------------------- #
# 2. Request a durable import (data queue, CR-09)                             #
# --------------------------------------------------------------------------- #


async def request_trade_log_import(
    session: AsyncSession,
    actor: Actor,
    *,
    source_asset_id: str,
    instrument_id: str,
    source_timezone: str = "UTC",
    import_mapping: dict[str, str] | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Enqueue a durable trade-log import job on the ``data`` queue (doc 05 §8, CR-09).

    The ``jobs`` row is the source of truth and survives browser close (the worker
    parses/normalizes/validates and writes a ``canonical_trade_record_batch``). An
    optional ``import_mapping`` (``{canonical_field: source_header}``, doc 05 §5.2)
    is carried in the durable payload so files whose headers are not the exact
    canonical names still import. Idempotent: the same key returns the same job id
    (TL-14, TL-15).
    """
    require_authenticated(actor)
    asset = await asset_repo.get_source_asset(session, source_asset_id)
    if asset is None:
        raise SourceAssetNotFoundError(f"Source asset '{source_asset_id}' not found.")
    ensure_can_edit(actor, owner_principal_id=asset.owner_principal_id)
    mapping = _clean_mapping(import_mapping)

    async def _op() -> dict[str, Any]:
        job = job_enqueue.enqueue_job(
            session,
            queue=_DATA_QUEUE,
            payload={
                "job_kind": TRADE_LOG_IMPORT,
                "source_asset_id": source_asset_id,
                "instrument_id": instrument_id,
                "source_timezone": source_timezone,
                "import_mapping": mapping,
            },
            actor_principal_id=actor.principal_id,
            idempotency_key=idempotency_key,
            correlation_id=actor.correlation_id,
        )
        _audit_and_outbox(
            session,
            actor,
            event_kind="trade_log.import_requested",
            target_type=_SOURCE_ASSET_TARGET,
            target_entity_id=source_asset_id,
            payload={"job_id": job.job_id, "queue": _DATA_QUEUE},
        )
        return {
            "job_id": job.job_id,
            "source_asset_id": source_asset_id,
            "queue": _DATA_QUEUE,
            "status": str(job.status),
        }

    return await run_idempotent(
        session,
        key=idempotency_key,
        actor_principal_id=actor.principal_id,
        request_payload={"op": "request_import", "source_asset_id": source_asset_id},
        operation=_op,
    )


# --------------------------------------------------------------------------- #
# 3. Save (& Add) — create the native work object + revision 1                #
# --------------------------------------------------------------------------- #


async def create_trade_log_and_attach(
    session: AsyncSession,
    actor: Actor,
    *,
    payload: dict[str, Any],
    workspace_id: str | None = None,
    attach: bool = True,
    position_index: int | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Save a Trade Log revision 1 and (optionally) attach it (doc 05 §8, §9.1).

    Validates the §10.2 config, requires the referenced import to be a succeeded,
    non-empty record batch, then in ONE tx: create the native work object (root +
    immutable revision 1, ``object_kind=trade_log``, ``available_time=None`` —
    historical data) -> pin the record batch to that revision -> if ``attach``
    (Save & Add), attach onto the Mainboard (REUSE 3a ``attach_mainboard_item`` so
    the composition hash + STALE semantics come for free). Save != Ready PASS != Run
    (Implementation Rule 15).
    """
    require_authenticated(actor)
    config = _validate_config(payload)
    canonical = config_to_dict(config)
    config_hash = compute_config_hash(config)
    batch = await _require_ready_import(session, config.import_binding.record_batch_revision_id)
    await _require_source_asset(session, config.import_binding.source_asset_id)

    async def _op() -> dict[str, Any]:
        root, _detail, revision = await mb_repo.create_work_object(
            session,
            owner_principal_id=actor.principal_id,
            created_by_principal_id=actor.principal_id,
            object_kind=_KIND,
            payload=canonical,
            source_provenance=_import_provenance(config, batch, config_hash),
            available_time=None,
        )
        await session.flush()
        tl_repo.link_batch_to_revision(batch, revision.revision_id)
        _audit_and_outbox(
            session,
            actor,
            event_kind="trade_log.revision_created",
            target_type=_WORK_OBJECT_TARGET,
            target_entity_id=root.entity_id,
            target_revision_id=revision.revision_id,
            new_state="active",
            payload={
                "revision_id": revision.revision_id,
                "revision_no": revision.revision_no,
                "config_hash": config_hash,
                "record_batch_revision_id": batch.record_batch_id,
                "accepted_count": batch.accepted_count,
            },
        )

        result: dict[str, Any] = {
            "root_id": root.entity_id,
            "revision_id": revision.revision_id,
            "revision_no": revision.revision_no,
            "object_kind": _KIND.value,
            "config_hash": config_hash,
            "row_version": root.row_version,
            "attached": False,
            "ready_state": "STALE",
        }
        if attach:
            resolved_workspace = await _resolve_attach_workspace(session, actor, workspace_id)
            attach_result = await mb_cmd.attach_mainboard_item(
                session,
                actor,
                workspace_id=resolved_workspace,
                root_id=root.entity_id,
                revision_id=revision.revision_id,
                item_kind=_KIND.value,
                position_index=position_index,
                idempotency_key=None,
            )
            result["attached"] = True
            result["workspace_id"] = resolved_workspace
            result["item_id"] = attach_result["item_id"]
            result["composition_hash"] = attach_result.get("composition_hash")
        return result

    return await run_idempotent(
        session,
        key=idempotency_key,
        actor_principal_id=actor.principal_id,
        request_payload={
            "op": "create_trade_log_and_attach",
            "config_hash": config_hash,
            "attach": attach,
            "workspace_id": workspace_id,
        },
        operation=_op,
    )


# --------------------------------------------------------------------------- #
# 4. Save New Revision — append revision N+1, NO auto-repin                   #
# --------------------------------------------------------------------------- #


async def create_trade_log_revision(
    session: AsyncSession,
    actor: Actor,
    *,
    root_id: str,
    payload: dict[str, Any],
    expected_head_revision_id: str | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Append an immutable Trade Log revision N+1 (doc 05 §8, §9.2, Rule 10, TL-12/TL-13).

    The prior revision is never mutated and the Mainboard item is NEVER auto-repinned
    — the caller must explicitly ``Use This Revision`` (3a pin_revision) to change the
    active composition. Optimistic concurrency via ``expected_head_revision_id``.
    """
    root, detail = await _require_active_trade_log(session, root_id)
    ensure_can_edit(actor, owner_principal_id=root.owner_principal_id)
    config = _validate_config(payload)
    canonical = config_to_dict(config)
    config_hash = compute_config_hash(config)
    batch = await _require_ready_import(session, config.import_binding.record_batch_revision_id)
    await _require_source_asset(session, config.import_binding.source_asset_id)

    async def _op() -> dict[str, Any]:
        await session.refresh(root, with_for_update=True)
        if (
            expected_head_revision_id is not None
            and root.current_revision_id != expected_head_revision_id
        ):
            raise WorkObjectRevisionConflictError()

        revision = await mb_repo.append_work_object_revision(
            session,
            root,
            object_kind=detail.object_kind,
            payload=canonical,
            source_provenance=_import_provenance(config, batch, config_hash),
            available_time=None,
            created_by_principal_id=actor.principal_id,
            change_note=f"trade log revision {config_hash[:12]}",
        )
        tl_repo.link_batch_to_revision(batch, revision.revision_id)
        _audit_and_outbox(
            session,
            actor,
            event_kind="trade_log.revision_created",
            target_type=_WORK_OBJECT_TARGET,
            target_entity_id=root.entity_id,
            target_revision_id=revision.revision_id,
            previous_state=expected_head_revision_id,
            new_state=revision.revision_id,
            payload={
                "revision_id": revision.revision_id,
                "revision_no": revision.revision_no,
                "config_hash": config_hash,
                "auto_repinned": False,
            },
        )
        return {
            "root_id": root.entity_id,
            "revision_id": revision.revision_id,
            "revision_no": revision.revision_no,
            "config_hash": config_hash,
            "row_version": root.row_version,
            "auto_repinned": False,
        }

    return await run_idempotent(
        session,
        key=idempotency_key,
        actor_principal_id=actor.principal_id,
        request_payload={
            "op": "create_trade_log_revision",
            "root_id": root_id,
            "expected_head_revision_id": expected_head_revision_id,
            "config_hash": config_hash,
        },
        operation=_op,
    )


# --------------------------------------------------------------------------- #
# Shared helpers                                                              #
# --------------------------------------------------------------------------- #


def _validate_file_type(original_filename: str | None) -> None:
    name = (original_filename or "").lower()
    if name and not name.endswith(_ALLOWED_EXTENSIONS):
        raise FileTypeNotAllowedError(
            f"File {original_filename!r} is not a TXT/CSV file.",
            details=[{"field": "original_filename", "actual": original_filename}],
        )


def _clean_mapping(import_mapping: dict[str, str] | None) -> dict[str, str] | None:
    """Drop blank entries; an empty mapping degrades to ``None`` (no mapping)."""
    if not import_mapping:
        return None
    cleaned = {
        str(key): str(value).strip()
        for key, value in import_mapping.items()
        if value is not None and str(value).strip()
    }
    return cleaned or None


def _import_provenance(
    config: TradeLogConfig, batch: CanonicalTradeRecordBatch, config_hash: str
) -> dict[str, Any]:
    """Build the revision source-provenance, carrying the mapping evidence id when the
    import used a column mapping (doc 05 §5.2 — ``import_binding.mapping_revision_id``)."""
    provenance: dict[str, Any] = {
        "source_asset_id": config.import_binding.source_asset_id,
        "record_batch_revision_id": batch.record_batch_id,
        "config_hash": config_hash,
    }
    if config.import_binding.mapping_revision_id:
        provenance["mapping_revision_id"] = config.import_binding.mapping_revision_id
    return provenance


def _validate_config(payload: dict[str, Any]) -> TradeLogConfig:
    config, issues = validate_trade_log_config(payload)
    if config is None or issues:
        _raise_for_issues(issues)
    assert config is not None  # narrowed: issues empty and config parsed
    return config


def _raise_for_issues(issues: list[dict[str, Any]]) -> None:
    """Map a validation issue list to the most specific typed 422 error."""
    codes = {issue.get("code") for issue in issues}
    fields = {issue.get("field") for issue in issues}
    if CODE_EVENT_MODEL_CONFLICT in codes:
        raise EventModelPolicyConflictError(details=issues)
    if CODE_PRICE_CONTEXT_CONFLICT in codes:
        raise TradeLogPriceContextConflictError(details=issues)
    if any(field and str(field).startswith("import_binding") for field in fields):
        raise SourceFileRequiredError(details=issues)
    raise TradeLogValidationFailedError(details=issues)


async def _require_ready_import(
    session: AsyncSession, record_batch_revision_id: str
) -> CanonicalTradeRecordBatch:
    """Resolve a succeeded, non-empty canonical trade-record batch.

    A missing batch -> 404; an unfinished/failed import -> the most specific
    blocker (required-column / timezone / no-records / not-ready).
    """
    batch = await tl_repo.get_record_batch(session, record_batch_revision_id)
    if batch is None:
        raise TradeRecordBatchNotFoundError(
            f"Trade-record batch '{record_batch_revision_id}' not found."
        )
    if batch.status != RecordBatchStatus.SUCCEEDED:
        _raise_for_failed_import(batch)
    if batch.accepted_count == 0:
        raise NoAcceptedTradeRecordsError()
    return batch


def _raise_for_failed_import(batch: CanonicalTradeRecordBatch) -> None:
    summary = batch.validation_summary or {}
    blocker = summary.get("blocker_code")
    if blocker == BLOCKER_AMBIGUOUS_COLUMN_MAPPING:
        raise AmbiguousColumnMappingError()
    if blocker == BLOCKER_INVALID_COLUMN_MAPPING:
        raise InvalidColumnMappingError()
    if blocker == BLOCKER_REQUIRED_COLUMN_MISSING:
        raise RequiredColumnMissingError()
    if blocker == BLOCKER_TIMEZONE_INVALID:
        raise TimezoneRequired("Select a valid IANA time zone before importing timestamps.")
    if blocker == BLOCKER_NO_ACCEPTED_TRADE_RECORDS:
        raise NoAcceptedTradeRecordsError()
    if batch.status == RecordBatchStatus.FAILED:
        raise NoAcceptedTradeRecordsError()
    raise ImportNotReadyError("The trade-log import has not finished successfully yet.")


async def _require_source_asset(session: AsyncSession, source_asset_id: str) -> None:
    if await asset_repo.get_source_asset(session, source_asset_id) is None:
        raise SourceAssetNotFoundError(f"Source asset '{source_asset_id}' not found.")


async def _require_active_trade_log(
    session: AsyncSession, root_id: str
) -> tuple[EntityRegistry, WorkObjectRoot]:
    root = await mb_repo.get_work_object_root(session, root_id)
    if root is None or root.deletion_state != DeletionState.ACTIVE:
        raise WorkObjectNotFoundError(f"Trade Log '{root_id}' not found.")
    detail = await mb_repo.get_work_object_detail(session, root_id)
    if detail is None or detail.object_kind != _KIND:
        raise WorkObjectNotFoundError(f"Trade Log '{root_id}' not found.")
    return root, detail


async def _resolve_attach_workspace(
    session: AsyncSession, actor: Actor, workspace_id: str | None
) -> str:
    if workspace_id is not None:
        return workspace_id
    projection = await mb_query.get_default_mainboard(session, actor)
    return str(projection["workspace_id"])


def _audit_and_outbox(
    session: AsyncSession,
    actor: Actor,
    *,
    event_kind: str,
    target_type: str,
    target_entity_id: str,
    target_revision_id: str | None = None,
    previous_state: str | None = None,
    new_state: str | None = None,
    payload: dict[str, Any],
) -> None:
    audit_repo.add_audit_event(
        session,
        event_kind=event_kind,
        actor_principal_id=actor.principal_id,
        actor_kind=actor.actor_kind,
        target_entity_id=target_entity_id,
        target_entity_type=target_type,
        target_revision_id=target_revision_id,
        previous_state=previous_state,
        new_state=new_state,
        correlation_id=actor.correlation_id,
    )
    audit_repo.add_outbox_event(
        session,
        event_type=event_kind,
        resource_type=target_type,
        resource_id=target_entity_id,
        payload=payload,
        correlation_id=actor.correlation_id,
    )


__all__ = [
    "create_trade_log_and_attach",
    "create_trade_log_revision",
    "request_trade_log_import",
    "upload_source_asset",
]
