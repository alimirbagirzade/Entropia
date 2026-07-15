"""Market Data commands (doc 11, decisions D1-D8).

Each command runs in one transaction supplied by the request dependency and
NEVER commits (mirrors Stage 1). The shape per mutation is always:

    policy check -> domain state-machine check -> repo mutation
    -> add_audit_event ("market.*") + add_outbox_event

Long-running analysis is enqueued as a durable ``jobs`` row (D4); the row is the
source of truth and survives browser close / logout (CR-09). Idempotent commands
go through ``application.idempotency.run_idempotent`` (D3).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from entropia.application.commands.deletion import soft_delete_registry_root
from entropia.application.idempotency import run_idempotent
from entropia.application.jobs.data_queue import MARKET_DATA_ANALYSIS
from entropia.application.queries import instrument as instrument_query
from entropia.domain.identity import Actor
from entropia.domain.identity.policy import require_authenticated
from entropia.domain.lifecycle.enums import ApprovalState
from entropia.domain.market_data import policy as md_policy
from entropia.domain.market_data.enums import MarketDataType, MarketRevisionState
from entropia.domain.market_data.schema_mapping import (
    confirmed_mapping_is_complete,
    propose_schema_mapping,
)
from entropia.domain.market_data.state_machine import (
    can_deprecate,
    next_market_revision_state,
)
from entropia.domain.market_data.value_objects import TimezoneSpec
from entropia.infrastructure.postgres.models import (
    MarketDatasetRevision,
    MarketSchemaMapping,
)
from entropia.infrastructure.postgres.repositories import approvals as approval_repo
from entropia.infrastructure.postgres.repositories import audit as audit_repo
from entropia.infrastructure.postgres.repositories import market_data as md_repo
from entropia.infrastructure.queues import enqueue as job_enqueue
from entropia.infrastructure.s3 import datasets
from entropia.shared.concurrency import check_head_revision, check_row_version
from entropia.shared.errors import (
    MappingReviewRequired,
    MarketDataFileTooLargeError,
    MarketDataFileTypeNotAllowedError,
    MarketDataUploadIntegrityError,
    MarketDataUploadStorageFailedError,
    NotFoundError,
    TimezoneRequired,
    ValidationError,
)
from entropia.shared.manifest import manifest_hash

_DATA_QUEUE = "data"
_TARGET_KIND = md_repo.ENTITY_TYPE

# F-01: accepted raw-asset file types and the server-enforced upload ceiling.
# MAX_UPLOAD_BYTES is public (not "_"-prefixed) because the API route bounds its
# read of the multipart body by this same constant (doc 11 "Validate content/
# size server-side" — one source of truth for the limit).
_ALLOWED_UPLOAD_EXTENSIONS = (".csv", ".txt")
MAX_UPLOAD_BYTES = 200 * 1024 * 1024  # 200 MB


async def _require_root(session: AsyncSession, entity_id: str) -> Any:
    root = await md_repo.get_dataset_root(session, entity_id)
    if root is None:
        raise NotFoundError(f"Market dataset '{entity_id}' not found.")
    return root


async def _require_current_revision(session: AsyncSession, root: Any) -> MarketDatasetRevision:
    revision = await md_repo.get_revision(session, root.current_revision_id or "")
    if revision is None:
        raise NotFoundError("Market dataset has no current revision.")
    return revision


def _audit_and_outbox(
    session: AsyncSession,
    actor: Actor,
    *,
    event_kind: str,
    entity_id: str,
    revision_id: str | None,
    previous_state: str | None = None,
    new_state: str | None = None,
    action: str,
) -> None:
    audit_repo.add_audit_event(
        session,
        event_kind=event_kind,
        actor_principal_id=actor.principal_id,
        actor_kind=actor.actor_kind,
        target_entity_id=entity_id,
        target_entity_type=_TARGET_KIND,
        target_revision_id=revision_id,
        previous_state=previous_state,
        new_state=new_state,
        correlation_id=actor.correlation_id,
    )
    audit_repo.add_outbox_event(
        session,
        event_type="resource.changed",
        resource_type=_TARGET_KIND,
        resource_id=entity_id,
        payload={"action": action, "revision_id": revision_id},
        correlation_id=actor.correlation_id,
    )


async def create_market_dataset(
    session: AsyncSession,
    actor: Actor,
    *,
    market_data_type: MarketDataType,
    payload: dict[str, Any],
    title: str | None = None,
    instrument_id: str | None = None,
    instrument_scope: dict[str, Any] | None = None,
) -> tuple[Any, MarketDatasetRevision]:
    """Create the dataset Root + first DRAFT revision (owner = actor).

    When ``instrument_scope`` is supplied (GAP-16; Master §8.1), the free-text
    scope is resolved to a canonical ``instrument_id`` through the registry — an
    unresolvable scope fails closed (INSTRUMENT_SCOPE_UNRESOLVABLE) rather than
    persisting a silent free-text assumption. Without a scope the legacy
    ``instrument_id`` is stored verbatim (backward compatible).
    """
    require_authenticated(actor)
    resolved_instrument_id = instrument_id
    if instrument_scope:
        resolved = await instrument_query.resolve_scope(
            session,
            venue_id=instrument_scope.get("venue_id"),
            symbol=instrument_scope.get("symbol"),
            contract_type=instrument_scope.get("contract_type"),
            alias=instrument_scope.get("alias"),
        )
        resolved_instrument_id = resolved["instrument_id"]
    root, revision = await md_repo.create_market_dataset(
        session,
        owner_principal_id=actor.principal_id,
        created_by_principal_id=actor.principal_id,
        market_data_type=market_data_type,
        payload=payload,
        title=title,
        instrument_id=resolved_instrument_id,
    )
    _audit_and_outbox(
        session,
        actor,
        event_kind="market.dataset.created",
        entity_id=root.entity_id,
        revision_id=revision.revision_id,
        new_state=str(revision.revision_state),
        action="created",
    )
    return root, revision


async def start_market_raw_upload(
    session: AsyncSession,
    actor: Actor,
    *,
    entity_id: str,
    content: bytes,
    content_type: str | None = None,
    original_filename: str | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Store the raw upload bytes in object storage and record the immutable
    evidence row (D5/D6).

    The object key, SHA-256 digest, byte size, and content type are all derived
    from the transferred bytes here — the caller never supplies storage
    metadata (F-01). Content-addressed: an identical re-upload for the same
    dataset returns the prior asset (idempotent regardless of retry) rather
    than writing a duplicate object.
    """
    _validate_upload_file_type(original_filename)
    _validate_upload_file_size(len(content))

    root = await _require_root(session, entity_id)
    md_policy.ensure_can_edit_draft(actor, owner_principal_id=root.owner_principal_id)

    digest = datasets.content_digest(content)
    existing = await md_repo.find_raw_asset_by_hash(
        session, entity_id=entity_id, content_digest=digest
    )
    if existing is not None:
        return {
            "asset_id": existing.asset_id,
            "entity_id": entity_id,
            "content_digest": existing.content_digest,
            "size_bytes": existing.size_bytes,
            "content_type": existing.content_type,
            "original_filename": existing.original_filename,
            "deduplicated": True,
        }

    async def _op() -> dict[str, Any]:
        object_key, stored_digest = _write_and_verify_raw_bytes(entity_id, content, content_type)
        asset = md_repo.add_raw_asset(
            session,
            entity_id=entity_id,
            revision_id=root.current_revision_id,
            object_key=object_key,
            content_digest=stored_digest,
            size_bytes=len(content),
            content_type=content_type,
            original_filename=original_filename,
            uploaded_by_principal_id=actor.principal_id,
        )
        _audit_and_outbox(
            session,
            actor,
            event_kind="market.raw_upload.started",
            entity_id=entity_id,
            revision_id=root.current_revision_id,
            action="raw_upload_started",
        )
        return {
            "asset_id": asset.asset_id,
            "entity_id": entity_id,
            "content_digest": stored_digest,
            "size_bytes": len(content),
            "content_type": content_type,
            "original_filename": original_filename,
            "deduplicated": False,
        }

    return await run_idempotent(
        session,
        key=idempotency_key,
        actor_principal_id=actor.principal_id,
        request_payload={
            "op": "start_raw_upload",
            "entity_id": entity_id,
            "raw_asset_hash": digest,
        },
        operation=_op,
    )


async def finalize_market_raw_upload(
    session: AsyncSession,
    actor: Actor,
    *,
    entity_id: str,
    asset_id: str,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Mark a raw upload complete and move the revision DRAFT -> UPLOADING.

    Idempotent: the same key + payload returns the prior result.
    """
    root = await _require_root(session, entity_id)
    md_policy.ensure_can_edit_draft(actor, owner_principal_id=root.owner_principal_id)

    async def _op() -> dict[str, Any]:
        revision = await _require_current_revision(session, root)
        previous = revision.revision_state
        if previous == MarketRevisionState.DRAFT:
            revision.revision_state = next_market_revision_state(
                previous, MarketRevisionState.UPLOADING
            )
        _audit_and_outbox(
            session,
            actor,
            event_kind="market.raw_upload.finalized",
            entity_id=entity_id,
            revision_id=revision.revision_id,
            previous_state=str(previous),
            new_state=str(revision.revision_state),
            action="raw_upload_finalized",
        )
        return {
            "entity_id": entity_id,
            "asset_id": asset_id,
            "revision_id": revision.revision_id,
            "revision_state": str(revision.revision_state),
        }

    return await run_idempotent(
        session,
        key=idempotency_key,
        actor_principal_id=actor.principal_id,
        request_payload={"op": "finalize_upload", "entity_id": entity_id, "asset_id": asset_id},
        operation=_op,
    )


async def request_market_dataset_analysis(
    session: AsyncSession,
    actor: Actor,
    *,
    entity_id: str,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Enqueue a durable analysis job on the ``data`` queue (D4) and move the
    revision -> ANALYZING. Idempotent: the same key returns the same job id."""
    root = await _require_root(session, entity_id)
    md_policy.ensure_can_edit_draft(actor, owner_principal_id=root.owner_principal_id)

    async def _op() -> dict[str, Any]:
        revision = await _require_current_revision(session, root)
        previous = revision.revision_state
        if previous != MarketRevisionState.ANALYZING:
            revision.revision_state = next_market_revision_state(
                previous, MarketRevisionState.ANALYZING
            )
        job = job_enqueue.enqueue_job(
            session,
            queue=_DATA_QUEUE,
            payload={
                "job_kind": MARKET_DATA_ANALYSIS,
                "entity_id": entity_id,
                "revision_id": revision.revision_id,
            },
            actor_principal_id=actor.principal_id,
            idempotency_key=idempotency_key,
            correlation_id=actor.correlation_id,
        )
        _audit_and_outbox(
            session,
            actor,
            event_kind="market.analysis.requested",
            entity_id=entity_id,
            revision_id=revision.revision_id,
            previous_state=str(previous),
            new_state=str(revision.revision_state),
            action="analysis_requested",
        )
        return {
            "job_id": job.job_id,
            "entity_id": entity_id,
            "revision_id": revision.revision_id,
            "queue": _DATA_QUEUE,
            "status": str(job.status),
        }

    return await run_idempotent(
        session,
        key=idempotency_key,
        actor_principal_id=actor.principal_id,
        request_payload={"op": "request_analysis", "entity_id": entity_id},
        operation=_op,
    )


async def confirm_market_schema_mapping(
    session: AsyncSession,
    actor: Actor,
    *,
    entity_id: str,
    market_data_type: MarketDataType,
    source_columns: list[str],
    confirmed_mapping: dict[str, str | None] | None = None,
) -> MarketSchemaMapping:
    """Propose (and optionally confirm) the canonical schema mapping (D7).

    Auto-confirms when the proposal is unambiguous. If essential fields are
    ambiguous/unmapped and the caller supplied no complete confirmation, raises
    ``MAPPING_REVIEW_REQUIRED``.
    """
    root = await _require_root(session, entity_id)
    md_policy.ensure_can_edit_draft(actor, owner_principal_id=root.owner_principal_id)

    proposal = propose_schema_mapping(market_data_type, source_columns)

    if confirmed_mapping is not None:
        if not confirmed_mapping_is_complete(market_data_type, confirmed_mapping):
            raise MappingReviewRequired("The confirmed mapping leaves an essential field unmapped.")
        final_confirmed: dict[str, str | None] | None = confirmed_mapping
        review_required = False
    elif proposal.review_required:
        raise MappingReviewRequired(
            "Essential fields are ambiguous or unmapped: "
            f"{', '.join(proposal.ambiguous_fields + proposal.unmapped_fields)}."
        )
    else:
        final_confirmed = dict(proposal.proposed)
        review_required = False

    mapping = md_repo.upsert_schema_mapping(
        session,
        entity_id=entity_id,
        market_data_type=market_data_type,
        proposed_mapping=dict(proposal.proposed),
        revision_id=root.current_revision_id,
        confirmed_mapping=final_confirmed,
        review_required=review_required,
        confirmed_by_principal_id=actor.principal_id,
    )
    _audit_and_outbox(
        session,
        actor,
        event_kind="market.schema_mapping.confirmed",
        entity_id=entity_id,
        revision_id=root.current_revision_id,
        action="schema_mapping_confirmed",
    )
    return mapping


async def create_market_dataset_revision(
    session: AsyncSession,
    actor: Actor,
    *,
    entity_id: str,
    payload: dict[str, Any],
    market_data_type: MarketDataType,
    title: str | None = None,
    instrument_id: str | None = None,
    timezone_spec: TimezoneSpec | None = None,
    expected_row_version: int | None = None,
    expected_head_revision_id: str | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Append a new DRAFT revision under optimistic concurrency control.

    Requires a valid timezone spec (CR / AT #5 — IANA required for custom mode).
    A stale ``expected_row_version``/``expected_head`` -> 409 STALE_REVISION.
    """
    root = await _require_root(session, entity_id)
    md_policy.ensure_can_edit_draft(actor, owner_principal_id=root.owner_principal_id)

    if timezone_spec is None:
        raise TimezoneRequired("A timezone specification is required to create a revision.")
    # Constructing the TimezoneSpec already validated IANA; re-resolve defensively.
    _ = timezone_spec.zone if timezone_spec.mode.value != "exchange" else None

    async def _op() -> dict[str, Any]:
        # Optimistic-concurrency checks live INSIDE the idempotent body so a
        # completed-key replay returns the stored result instead of failing the
        # stale-version check against the already-advanced head (D3).
        check_row_version(root.row_version, expected_row_version)
        check_head_revision(root.current_revision_id, expected_head_revision_id)
        revision = await md_repo.append_market_dataset_revision(
            session,
            root,
            market_data_type=market_data_type,
            payload=payload,
            created_by_principal_id=actor.principal_id,
            title=title,
            instrument_id=instrument_id,
        )
        revision.timezone_mode = timezone_spec.mode
        revision.timezone_iana = timezone_spec.iana
        revision.manifest_hash = manifest_hash(
            {"entity_id": entity_id, "revision_no": revision.revision_no, "payload": payload}
        )
        _audit_and_outbox(
            session,
            actor,
            event_kind="market.dataset.revised",
            entity_id=entity_id,
            revision_id=revision.revision_id,
            new_state=str(revision.revision_state),
            action="revised",
        )
        return {
            "entity_id": entity_id,
            "revision_id": revision.revision_id,
            "revision_no": revision.revision_no,
            "row_version": root.row_version,
        }

    return await run_idempotent(
        session,
        key=idempotency_key,
        actor_principal_id=actor.principal_id,
        request_payload={"op": "create_revision", "entity_id": entity_id, "payload": payload},
        operation=_op,
    )


async def approve_market_dataset_revision(
    session: AsyncSession,
    actor: Actor,
    *,
    entity_id: str,
    revision_id: str,
    note: str | None = None,
    expected_row_version: int | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Admin-only: move a VERIFIED revision -> APPROVED and record the decision.

    ``verified`` != ``approved``: approval is only legal from VERIFIED, and only
    an Admin may perform it (CR-02 -> ApprovalRequiresAdmin / 403).
    """
    md_policy.ensure_can_approve(actor)
    root = await _require_root(session, entity_id)

    revision = await md_repo.get_revision(session, revision_id)
    if revision is None or revision.entity_id != entity_id:
        raise NotFoundError(f"Revision '{revision_id}' not found for this dataset.")

    async def _op() -> dict[str, Any]:
        # Concurrency + legality checks live INSIDE the idempotent body: a
        # completed-key replay short-circuits before this and returns the stored
        # result, so it must not re-validate against the now-APPROVED state (D3).
        # next_market_revision_state raises IllegalMarketRevisionTransition (409)
        # on a first, genuinely-illegal call (e.g. approving a non-verified rev).
        check_row_version(root.row_version, expected_row_version)
        previous = revision.revision_state
        revision.revision_state = next_market_revision_state(previous, MarketRevisionState.APPROVED)
        root.lifecycle_state = "active"
        approval_repo.add_approval_decision(
            session,
            target_entity_id=entity_id,
            target_kind=_TARGET_KIND,
            decision=ApprovalState.APPROVED,
            target_revision_id=revision_id,
            approver_principal_id=actor.principal_id,
            prior_state=str(previous),
            new_state=str(revision.revision_state),
            note=note,
            policy_context={"role": "admin"},
        )
        _audit_and_outbox(
            session,
            actor,
            event_kind="market.dataset.approved",
            entity_id=entity_id,
            revision_id=revision_id,
            previous_state=str(previous),
            new_state=str(revision.revision_state),
            action="approved",
        )
        return {
            "entity_id": entity_id,
            "revision_id": revision_id,
            "revision_state": str(revision.revision_state),
        }

    return await run_idempotent(
        session,
        key=idempotency_key,
        actor_principal_id=actor.principal_id,
        request_payload={"op": "approve", "entity_id": entity_id, "revision_id": revision_id},
        operation=_op,
    )


async def create_successor_revision(
    session: AsyncSession,
    actor: Actor,
    *,
    entity_id: str,
    payload: dict[str, Any],
    market_data_type: MarketDataType,
    title: str | None = None,
    instrument_id: str | None = None,
) -> MarketDatasetRevision:
    """Append a successor DRAFT revision that supersedes the current head.

    Provenance is preserved: the prior revision remains immutable and is recorded
    as ``supersedes_revision_id``.
    """
    root = await _require_root(session, entity_id)
    md_policy.ensure_can_edit_draft(actor, owner_principal_id=root.owner_principal_id)

    revision = await md_repo.append_market_dataset_revision(
        session,
        root,
        market_data_type=market_data_type,
        payload=payload,
        created_by_principal_id=actor.principal_id,
        supersedes_revision_id=root.current_revision_id,
        title=title,
        instrument_id=instrument_id,
    )
    _audit_and_outbox(
        session,
        actor,
        event_kind="market.dataset.successor_created",
        entity_id=entity_id,
        revision_id=revision.revision_id,
        new_state=str(revision.revision_state),
        action="successor_created",
    )
    return revision


async def deprecate_market_dataset_revision(
    session: AsyncSession,
    actor: Actor,
    *,
    entity_id: str,
    revision_id: str,
    note: str | None = None,
) -> dict[str, Any]:
    """Admin-only: move an APPROVED revision -> DEPRECATED."""
    md_policy.ensure_can_approve(actor)
    root = await _require_root(session, entity_id)
    revision = await md_repo.get_revision(session, revision_id)
    if revision is None or revision.entity_id != entity_id:
        raise NotFoundError(f"Revision '{revision_id}' not found for this dataset.")

    if not can_deprecate(revision.revision_state):
        next_market_revision_state(revision.revision_state, MarketRevisionState.DEPRECATED)

    previous = revision.revision_state
    revision.revision_state = next_market_revision_state(previous, MarketRevisionState.DEPRECATED)
    root.lifecycle_state = "deprecated"
    approval_repo.add_approval_decision(
        session,
        target_entity_id=entity_id,
        target_kind=_TARGET_KIND,
        decision=ApprovalState.REJECTED,
        target_revision_id=revision_id,
        approver_principal_id=actor.principal_id,
        prior_state=str(previous),
        new_state=str(revision.revision_state),
        note=note,
        policy_context={"action": "deprecate"},
    )
    _audit_and_outbox(
        session,
        actor,
        event_kind="market.dataset.deprecated",
        entity_id=entity_id,
        revision_id=revision_id,
        previous_state=str(previous),
        new_state=str(revision.revision_state),
        action="deprecated",
    )
    return {
        "entity_id": entity_id,
        "revision_id": revision_id,
        "revision_state": str(revision.revision_state),
    }


async def soft_delete_market_dataset(
    session: AsyncSession,
    actor: Actor,
    *,
    entity_id: str,
    reason: str | None = None,
    expected_row_version: int | None = None,
) -> dict[str, Any]:
    """Owner-or-Admin soft delete of a Market Dataset root (doc 11 §10.1, Flow F,
    rule 13; MARKET_DATASET_SOFT_DELETED).

    Removes the root from the active catalog + new-selector projections and writes
    a Trash Entry; historical revision/manifest provenance and any run-pinned
    references are preserved (no cascade). There is deliberately NO running-job
    blocker: a completed or in-flight Run keeps its own pinned manifest (exact
    revision id + digests), so soft delete only affects NEW selection (doc 11
    §10.1, sibling of ``deprecate``). Restore / permanent delete stay Admin-only
    via the Trash surface; a repeat delete is an idempotent no-op.
    """
    root = await _require_root(session, entity_id)
    md_policy.ensure_can_edit_draft(actor, owner_principal_id=root.owner_principal_id)

    display_name: str | None = None
    if root.current_revision_id:
        revision = await md_repo.get_revision(session, root.current_revision_id)
        if revision is not None:
            display_name = revision.title

    transition = await soft_delete_registry_root(
        session,
        actor,
        root,
        reason=reason,
        display_name=display_name,
        expected_row_version=expected_row_version,
    )
    if transition is not None:
        previous, new_state = transition
        _audit_and_outbox(
            session,
            actor,
            event_kind="market.dataset.soft_deleted",
            entity_id=entity_id,
            revision_id=root.current_revision_id,
            previous_state=previous,
            new_state=new_state,
            action="soft_deleted",
        )
    return {
        "entity_id": entity_id,
        "deletion_state": str(root.deletion_state),
        "display_name": display_name,
    }


def now_utc() -> datetime:
    """Deterministic UTC clock seam (kept here so tests can patch one place)."""
    return datetime.now(UTC)


# --------------------------------------------------------------------------- #
# F-01 upload helpers                                                         #
# --------------------------------------------------------------------------- #


def _validate_upload_file_type(original_filename: str | None) -> None:
    name = (original_filename or "").lower()
    if name and not name.endswith(_ALLOWED_UPLOAD_EXTENSIONS):
        raise MarketDataFileTypeNotAllowedError(
            f"File {original_filename!r} is not a CSV/TXT file.",
            details=[{"field": "original_filename", "actual": original_filename}],
        )


def _validate_upload_file_size(size_bytes: int) -> None:
    if size_bytes <= 0:
        raise ValidationError("The uploaded file is empty.")
    if size_bytes > MAX_UPLOAD_BYTES:
        raise MarketDataFileTooLargeError(
            f"The file exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB upload limit.",
            details=[
                {"field": "size_bytes", "actual": size_bytes, "limit": MAX_UPLOAD_BYTES},
            ],
        )


def _write_and_verify_raw_bytes(
    entity_id: str, content: bytes, content_type: str | None
) -> tuple[str, str]:
    """Write bytes to object storage, then read them back and re-hash to
    confirm the stored object matches what was uploaded (integrity
    verification, F-01) before any evidence row is persisted."""
    try:
        object_key, stored_digest = datasets.put_raw_bytes(
            entity_id, content, content_type=content_type
        )
    except Exception as exc:
        raise MarketDataUploadStorageFailedError() from exc

    try:
        roundtrip = datasets.get_raw_bytes(object_key)
    except Exception as exc:
        raise MarketDataUploadStorageFailedError() from exc

    if len(roundtrip) != len(content) or datasets.content_digest(roundtrip) != stored_digest:
        raise MarketDataUploadIntegrityError()

    return object_key, stored_digest
