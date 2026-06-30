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

from entropia.application.idempotency import run_idempotent
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
    MarketRawAsset,
    MarketSchemaMapping,
)
from entropia.infrastructure.postgres.repositories import approvals as approval_repo
from entropia.infrastructure.postgres.repositories import audit as audit_repo
from entropia.infrastructure.postgres.repositories import market_data as md_repo
from entropia.infrastructure.queues import enqueue as job_enqueue
from entropia.shared.concurrency import check_head_revision, check_row_version
from entropia.shared.errors import (
    MappingReviewRequired,
    NotFoundError,
    TimezoneRequired,
)
from entropia.shared.manifest import manifest_hash

_DATA_QUEUE = "data"
_TARGET_KIND = md_repo.ENTITY_TYPE


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
) -> tuple[Any, MarketDatasetRevision]:
    """Create the dataset Root + first DRAFT revision (owner = actor)."""
    require_authenticated(actor)
    root, revision = md_repo.create_market_dataset(
        session,
        owner_principal_id=actor.principal_id,
        created_by_principal_id=actor.principal_id,
        market_data_type=market_data_type,
        payload=payload,
        title=title,
        instrument_id=instrument_id,
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
    object_key: str,
    content_digest: str,
    size_bytes: int,
    content_type: str | None = None,
    original_filename: str | None = None,
) -> MarketRawAsset:
    """Record the raw-upload metadata row pointing at an object-storage key.

    The bytes are written to object storage by the route/infra; here we persist
    the immutable evidence row (D5/D6) and audit it.
    """
    root = await _require_root(session, entity_id)
    md_policy.ensure_can_edit_draft(actor, owner_principal_id=root.owner_principal_id)
    asset = md_repo.add_raw_asset(
        session,
        entity_id=entity_id,
        revision_id=root.current_revision_id,
        object_key=object_key,
        content_digest=content_digest,
        size_bytes=size_bytes,
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
    return asset


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
            payload={"entity_id": entity_id, "revision_id": revision.revision_id},
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


def now_utc() -> datetime:
    """Deterministic UTC clock seam (kept here so tests can patch one place)."""
    return datetime.now(UTC)
