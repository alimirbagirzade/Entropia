"""Research Data commands (doc 12, decisions DR1-DR8).

Each command runs in one transaction supplied by the request dependency and
NEVER commits (mirrors Stage 1 / Stage 2a market_data). The shape per mutation:

    policy check -> domain state-machine / pure validation -> repo mutation
    -> add_audit_event ("research.*") + add_outbox_event

Hard dependency (DR3): a research dataset revision can only be created/approved
when an ACTIVE+APPROVED ``market_dataset_revision`` is linked; otherwise the
command raises ``DependencyBlocked`` (409).

Idempotent commands go through ``application.idempotency.run_idempotent`` (DR8).
CRITICAL (the 2a lesson): optimistic-concurrency and state-machine legality
checks live INSIDE the ``operation()`` body so a completed-key replay returns the
cached result instead of raising a spurious 409. Authorization (policy) and pure
input validation stay OUTSIDE.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from entropia.application.commands.deletion import soft_delete_registry_root
from entropia.application.idempotency import run_idempotent
from entropia.application.jobs.data_queue import RESEARCH_DATA_ANALYSIS
from entropia.application.queries.market_data import resolve_approved_market_data_bundle
from entropia.domain.identity import Actor
from entropia.domain.identity.policy import require_authenticated
from entropia.domain.lifecycle.enums import ApprovalState, DeletionState
from entropia.domain.market_data.enums import MarketRevisionState
from entropia.domain.research_data import policy as rd_policy
from entropia.domain.research_data.enums import (
    EventTimeSemantics,
    ResearchRevisionState,
    ResearchTimezoneMode,
    UsageScope,
)
from entropia.domain.research_data.state_machine import next_research_revision_state
from entropia.domain.research_data.time_policy import time_policy_is_valid
from entropia.domain.research_data.value_objects import (
    AvailableTimeSpec,
    CategorySpec,
    FieldDefinition,
    ResearchTimezoneSpec,
)
from entropia.infrastructure.postgres.models import (
    ResearchDatasetRevision,
    ResearchFeatureDefinition,
    ResearchFieldDefinition,
    ResearchTimePolicy,
)
from entropia.infrastructure.postgres.repositories import approvals as approval_repo
from entropia.infrastructure.postgres.repositories import audit as audit_repo
from entropia.infrastructure.postgres.repositories import market_data as md_repo
from entropia.infrastructure.postgres.repositories import research_data as rd_repo
from entropia.infrastructure.queues import enqueue as job_enqueue
from entropia.infrastructure.s3 import datasets
from entropia.shared.concurrency import check_head_revision, check_row_version
from entropia.shared.errors import (
    DependencyBlocked,
    NotFoundError,
    ResearchDataFileTooLargeError,
    ResearchDataFileTypeNotAllowedError,
    ResearchDataUploadIntegrityError,
    ResearchDataUploadStorageFailedError,
    TimePolicyInvalid,
    ValidationError,
)
from entropia.shared.manifest import manifest_hash

_DATA_QUEUE = "data"
_TARGET_KIND = rd_repo.ENTITY_TYPE

# F-02: accepted raw-asset file types and the server-enforced upload ceiling
# (mirrors F-01 market_data). MAX_UPLOAD_BYTES is public because the API route
# bounds its read of the multipart body by this same constant — one source of
# truth for the limit (doc 12 §7 "validate content/size server-side").
_ALLOWED_UPLOAD_EXTENSIONS = (".csv", ".txt")
MAX_UPLOAD_BYTES = 200 * 1024 * 1024  # 200 MB


async def _require_root(session: AsyncSession, entity_id: str) -> Any:
    root = await rd_repo.get_dataset_root(session, entity_id)
    if root is None:
        raise NotFoundError(f"Research dataset '{entity_id}' not found.")
    return root


async def _require_current_revision(session: AsyncSession, root: Any) -> ResearchDatasetRevision:
    revision = await rd_repo.get_revision(session, root.current_revision_id or "")
    if revision is None:
        raise NotFoundError("Research dataset has no current revision.")
    return revision


async def _resolve_market_link(session: AsyncSession, market_entity_id: str) -> dict[str, Any]:
    """Resolve the exact ACTIVE+APPROVED market bundle or raise DEPENDENCY_BLOCKED.

    The market query raises ``NotFound`` when there is no eligible revision; we
    translate that into ``DependencyBlocked`` (409) so the research layer surfaces
    the canonical anti-orphan error (DR3, doc 12 §10).
    """
    try:
        return await resolve_approved_market_data_bundle(session, entity_id=market_entity_id)
    except NotFoundError as exc:
        raise DependencyBlocked(
            "Link this Research Data version to an Approved Market Data dataset first."
        ) from exc


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


async def create_research_dataset(
    session: AsyncSession,
    actor: Actor,
    *,
    market_entity_id: str,
    payload: dict[str, Any],
    category: CategorySpec,
    usage_scope: UsageScope,
    display_name: str | None = None,
    provider_name: str | None = None,
) -> tuple[Any, ResearchDatasetRevision]:
    """Create the dataset Root + first DRAFT revision pinned to an Approved market.

    DR3: the linked market dataset must have an ACTIVE+APPROVED revision; the exact
    revision id + content hash are pinned both on the revision and in an immutable
    ``research_market_link`` row.
    """
    require_authenticated(actor)
    bundle = await _resolve_market_link(session, market_entity_id)

    root, revision = await rd_repo.create_research_dataset(
        session,
        owner_principal_id=actor.principal_id,
        created_by_principal_id=actor.principal_id,
        payload=payload,
        display_name=display_name,
        category_key=category.category_key,
        custom_category=category.custom_category,
        provider_name=provider_name,
        usage_scope=usage_scope,
        linked_market_dataset_revision_id=bundle["revision_id"],
    )
    rd_repo.add_market_link(
        session,
        entity_id=root.entity_id,
        market_dataset_revision_id=bundle["revision_id"],
        revision_id=revision.revision_id,
        market_content_hash=bundle.get("content_hash"),
    )
    _audit_and_outbox(
        session,
        actor,
        event_kind="research.dataset.created",
        entity_id=root.entity_id,
        revision_id=revision.revision_id,
        new_state=str(revision.revision_state),
        action="created",
    )
    return root, revision


async def create_upload_session(
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
    raw-asset evidence row (doc 12 §7 Browse File).

    The object key, SHA-256 digest, byte size, and content type are all derived
    from the transferred bytes here — the caller never supplies storage
    metadata (F-02). Content-addressed: an identical re-upload for the same
    dataset returns the prior asset (idempotent regardless of retry) rather
    than writing a duplicate object.
    """
    _validate_upload_file_type(original_filename)
    _validate_upload_file_size(len(content))

    root = await _require_root(session, entity_id)
    rd_policy.ensure_can_edit_draft(actor, owner_principal_id=root.owner_principal_id)

    digest = datasets.content_digest(content)
    existing = await rd_repo.find_raw_asset_by_hash(
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
        asset = rd_repo.add_raw_asset(
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
            event_kind="research.raw_upload.started",
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
            "op": "create_upload_session",
            "entity_id": entity_id,
            "raw_asset_hash": digest,
        },
        operation=_op,
    )


async def finalize_upload(
    session: AsyncSession,
    actor: Actor,
    *,
    entity_id: str,
    asset_id: str,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Mark a raw upload complete. Idempotent: same key + payload returns prior."""
    root = await _require_root(session, entity_id)
    rd_policy.ensure_can_edit_draft(actor, owner_principal_id=root.owner_principal_id)

    async def _op() -> dict[str, Any]:
        revision = await _require_current_revision(session, root)
        revision.raw_asset_id = asset_id
        _audit_and_outbox(
            session,
            actor,
            event_kind="research.raw_upload.finalized",
            entity_id=entity_id,
            revision_id=revision.revision_id,
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


async def request_research_dataset_analysis(
    session: AsyncSession,
    actor: Actor,
    *,
    entity_id: str,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Enqueue a durable analysis job on the ``data`` queue (DR8) and move the
    revision DRAFT -> ANALYZING. Idempotent: same key returns the same job id."""
    root = await _require_root(session, entity_id)
    rd_policy.ensure_can_edit_draft(actor, owner_principal_id=root.owner_principal_id)

    async def _op() -> dict[str, Any]:
        revision = await _require_current_revision(session, root)
        previous = revision.revision_state
        if previous == ResearchRevisionState.DRAFT:
            revision.revision_state = next_research_revision_state(
                previous, ResearchRevisionState.ANALYZING
            )
        job = job_enqueue.enqueue_job(
            session,
            queue=_DATA_QUEUE,
            payload={
                "job_kind": RESEARCH_DATA_ANALYSIS,
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
            event_kind="research.analysis.requested",
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


async def create_research_dataset_revision(
    session: AsyncSession,
    actor: Actor,
    *,
    entity_id: str,
    payload: dict[str, Any],
    category: CategorySpec,
    usage_scope: UsageScope,
    timezone_spec: ResearchTimezoneSpec,
    market_entity_id: str | None = None,
    display_name: str | None = None,
    provider_name: str | None = None,
    base_revision_id: str | None = None,
    expected_row_version: int | None = None,
    expected_head_revision_id: str | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Append a new DRAFT revision under optimistic concurrency control (DR8).

    Constructing the value objects already validated category requiredness and the
    IANA timezone. A stale ``expected_row_version``/``expected_head`` -> 409.
    """
    root = await _require_root(session, entity_id)
    rd_policy.ensure_can_edit_draft(actor, owner_principal_id=root.owner_principal_id)
    # Re-resolve defensively; construction already validated the spec.
    _ = timezone_spec.zone if timezone_spec.mode != ResearchTimezoneMode.EXCHANGE else None

    market_id = market_entity_id
    bundle: dict[str, Any] | None = None
    if market_id is not None:
        bundle = await _resolve_market_link(session, market_id)

    async def _op() -> dict[str, Any]:
        # Concurrency checks INSIDE the body so a completed-key replay returns the
        # cached result without re-validating the advanced head (the 2a lesson).
        check_row_version(root.row_version, expected_row_version)
        check_head_revision(root.current_revision_id, expected_head_revision_id)
        linked_id = bundle["revision_id"] if bundle is not None else None
        revision = await rd_repo.append_research_dataset_revision(
            session,
            root,
            payload=payload,
            created_by_principal_id=actor.principal_id,
            base_revision_id=base_revision_id,
            display_name=display_name,
            category_key=category.category_key,
            custom_category=category.custom_category,
            provider_name=provider_name,
            usage_scope=usage_scope,
            linked_market_dataset_revision_id=linked_id,
        )
        revision.source_timezone_mode = timezone_spec.mode
        revision.source_timezone_iana = timezone_spec.iana
        revision.manifest_hash = manifest_hash(
            {"entity_id": entity_id, "revision_no": revision.revision_no, "payload": payload}
        )
        if bundle is not None:
            rd_repo.add_market_link(
                session,
                entity_id=entity_id,
                market_dataset_revision_id=bundle["revision_id"],
                revision_id=revision.revision_id,
                market_content_hash=bundle.get("content_hash"),
            )
        _audit_and_outbox(
            session,
            actor,
            event_kind="research.dataset.revised",
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


async def set_time_policy(
    session: AsyncSession,
    actor: Actor,
    *,
    entity_id: str,
    event_time_semantics: EventTimeSemantics,
    available_time: AvailableTimeSpec,
    timezone_spec: ResearchTimezoneSpec,
    time_policy_version: int = 1,
) -> ResearchTimePolicy:
    """Set the event/available time policy (doc 12 §5.2, §8.4).

    Constructing ``AvailableTimeSpec``/``ResearchTimezoneSpec`` already enforces
    fixed-delay positivity and IANA validity. We additionally assert the structural
    rule that only the fixed-delay policy may carry a delay (TIME_POLICY_INVALID).
    """
    root = await _require_root(session, entity_id)
    rd_policy.ensure_can_edit_draft(actor, owner_principal_id=root.owner_principal_id)

    delay = (
        None
        if available_time.delay_seconds is None
        else timedelta(seconds=available_time.delay_seconds)
    )
    if not time_policy_is_valid(policy=available_time.policy, delay=delay):
        raise TimePolicyInvalid("The available-time rule and delay are inconsistent.")

    policy = rd_repo.set_time_policy(
        session,
        entity_id=entity_id,
        event_time_semantics=event_time_semantics,
        available_time_policy=available_time.policy,
        source_timezone_mode=timezone_spec.mode,
        revision_id=root.current_revision_id,
        time_policy_version=time_policy_version,
        delay_seconds=available_time.delay_seconds,
        source_timezone_iana=timezone_spec.iana,
    )
    revision = await _require_current_revision(session, root)
    revision.event_time_semantics = event_time_semantics
    revision.available_time_policy = available_time.policy
    revision.available_delay_seconds = available_time.delay_seconds
    revision.source_timezone_mode = timezone_spec.mode
    revision.source_timezone_iana = timezone_spec.iana
    _audit_and_outbox(
        session,
        actor,
        event_kind="research.time_policy.set",
        entity_id=entity_id,
        revision_id=root.current_revision_id,
        action="time_policy_set",
    )
    return policy


async def define_field(
    session: AsyncSession,
    actor: Actor,
    *,
    entity_id: str,
    field: FieldDefinition,
    definition_version: int = 1,
) -> ResearchFieldDefinition:
    """Persist one field-level semantic definition (doc 12 §8.3).

    ``FieldDefinition`` construction already rejects insufficient meaning
    (FIELD_MEANING_INSUFFICIENT)."""
    root = await _require_root(session, entity_id)
    rd_policy.ensure_can_edit_draft(actor, owner_principal_id=root.owner_principal_id)
    row = rd_repo.add_field_definition(
        session,
        entity_id=entity_id,
        field_name=field.field_name,
        semantic_type=field.semantic_type,
        revision_id=root.current_revision_id,
        definition_version=definition_version,
        unit_or_scale=field.unit_or_scale,
        measurement_method=field.measurement_method,
        null_semantics=field.null_semantics,
        event_time_source=field.event_time_source,
        availability_rule=field.availability_rule,
        allowed_usage=field.allowed_usage,
    )
    _audit_and_outbox(
        session,
        actor,
        event_kind="research.field_definition.defined",
        entity_id=entity_id,
        revision_id=root.current_revision_id,
        action="field_defined",
    )
    return row


async def define_feature(
    session: AsyncSession,
    actor: Actor,
    *,
    entity_id: str,
    feature_name: str,
    definition: dict[str, Any],
    feature_version: int = 1,
    approval_state: str | None = None,
) -> ResearchFeatureDefinition:
    """Persist a versioned feature definition (doc 12 §9.3). Required path before a
    Feature-Input-Only revision can feed Strategy logic."""
    root = await _require_root(session, entity_id)
    rd_policy.ensure_can_edit_draft(actor, owner_principal_id=root.owner_principal_id)
    row = rd_repo.add_feature_definition(
        session,
        entity_id=entity_id,
        feature_name=feature_name,
        definition=definition,
        revision_id=root.current_revision_id,
        feature_version=feature_version,
        approval_state=approval_state,
    )
    _audit_and_outbox(
        session,
        actor,
        event_kind="research.feature_definition.defined",
        entity_id=entity_id,
        revision_id=root.current_revision_id,
        action="feature_defined",
    )
    return row


async def approve_research_dataset_revision(
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

    ``verified`` != ``approved`` (DR2). Re-validates the hard market dependency
    (DR3) and the time policy (DR4) before approval. Non-Admin -> 403.
    """
    rd_policy.ensure_can_approve(actor)
    root = await _require_root(session, entity_id)
    revision = await rd_repo.get_revision(session, revision_id)
    if revision is None or revision.entity_id != entity_id:
        raise NotFoundError(f"Revision '{revision_id}' not found for this dataset.")

    async def _op() -> dict[str, Any]:
        # Concurrency + legality + dependency checks INSIDE the body so a
        # completed-key replay returns the stored result (the 2a lesson).
        check_row_version(root.row_version, expected_row_version)
        _ensure_time_policy_approvable(revision)
        await _ensure_market_link_active(session, revision)
        previous = revision.revision_state
        revision.revision_state = next_research_revision_state(
            previous, ResearchRevisionState.APPROVED
        )
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
            event_kind="research.dataset.approved",
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


async def revoke_research_dataset_approval(
    session: AsyncSession,
    actor: Actor,
    *,
    entity_id: str,
    revision_id: str,
    note: str | None = None,
    expected_row_version: int | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Admin-only: move an APPROVED revision -> APPROVAL_REVOKED (doc 12 §7).

    Stops new use; pinned historical manifests remain immutable. Records an
    approval_decision (REJECTED) + audit + outbox in one tx.
    """
    rd_policy.ensure_can_revoke(actor)
    root = await _require_root(session, entity_id)
    revision = await rd_repo.get_revision(session, revision_id)
    if revision is None or revision.entity_id != entity_id:
        raise NotFoundError(f"Revision '{revision_id}' not found for this dataset.")

    async def _op() -> dict[str, Any]:
        check_row_version(root.row_version, expected_row_version)
        previous = revision.revision_state
        revision.revision_state = next_research_revision_state(
            previous, ResearchRevisionState.APPROVAL_REVOKED
        )
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
            policy_context={"action": "revoke"},
        )
        _audit_and_outbox(
            session,
            actor,
            event_kind="research.dataset.approval_revoked",
            entity_id=entity_id,
            revision_id=revision_id,
            previous_state=str(previous),
            new_state=str(revision.revision_state),
            action="approval_revoked",
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
        request_payload={"op": "revoke", "entity_id": entity_id, "revision_id": revision_id},
        operation=_op,
    )


async def soft_delete_research_dataset(
    session: AsyncSession,
    actor: Actor,
    *,
    entity_id: str,
    reason: str | None = None,
    expected_row_version: int | None = None,
) -> dict[str, Any]:
    """Owner-or-Admin soft delete of a Research Dataset root (doc 12 §7/§11,
    ``SoftDeleteResearchDatasetRoot``; RESEARCH_DATASET_SOFT_DELETED).

    Removes the root from the active list and writes a Trash Entry; historical
    Agent/Backtest manifests and any linked-market provenance stay intact (no
    cascade, doc 12 §11). Like its market sibling there is NO running-job blocker:
    references are pinned in the Run manifest, so soft delete only affects NEW
    selection. Restore / permanent delete stay Admin-only via the Trash surface;
    a repeat delete is an idempotent no-op. ``expected_row_version`` enforces the
    doc 12 "expected root version current" precondition when supplied.
    """
    root = await _require_root(session, entity_id)
    rd_policy.ensure_can_edit_draft(actor, owner_principal_id=root.owner_principal_id)

    display_name: str | None = None
    if root.current_revision_id:
        revision = await rd_repo.get_revision(session, root.current_revision_id)
        if revision is not None:
            display_name = revision.display_name

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
            event_kind="research.dataset.soft_deleted",
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


def _ensure_time_policy_approvable(revision: ResearchDatasetRevision) -> None:
    """A revision with missing/invalid time rules cannot be approved (DR4)."""
    if revision.available_time_policy is None or revision.event_time_semantics is None:
        raise TimePolicyInvalid("Event and available time policy must be set before approval.")
    delay = (
        None
        if revision.available_delay_seconds is None
        else timedelta(seconds=revision.available_delay_seconds)
    )
    if not time_policy_is_valid(policy=revision.available_time_policy, delay=delay):
        raise TimePolicyInvalid("The available-time rule is invalid; cannot approve.")


async def _ensure_market_link_active(
    session: AsyncSession, revision: ResearchDatasetRevision
) -> None:
    """The linked market revision must still be ACTIVE+APPROVED at approval (DR3)."""
    linked = revision.linked_market_dataset_revision_id
    if linked is None:
        raise DependencyBlocked("This revision has no linked Approved Market Data revision.")
    market_rev = await md_repo.get_revision(session, linked)
    if market_rev is None:
        raise DependencyBlocked("The linked Market Data revision no longer exists.")
    market_root = await md_repo.get_dataset_root(session, market_rev.entity_id)
    if (
        market_root is None
        or market_root.deletion_state != DeletionState.ACTIVE
        or market_rev.revision_state != MarketRevisionState.APPROVED
    ):
        raise DependencyBlocked("The linked Market Data revision is not active and approved.")


# --------------------------------------------------------------------------- #
# F-02 upload helpers                                                         #
# --------------------------------------------------------------------------- #


def _validate_upload_file_type(original_filename: str | None) -> None:
    name = (original_filename or "").lower()
    if name and not name.endswith(_ALLOWED_UPLOAD_EXTENSIONS):
        raise ResearchDataFileTypeNotAllowedError(
            f"File {original_filename!r} is not a CSV/TXT file.",
            details=[{"field": "original_filename", "actual": original_filename}],
        )


def _validate_upload_file_size(size_bytes: int) -> None:
    if size_bytes <= 0:
        raise ValidationError("The uploaded file is empty.")
    if size_bytes > MAX_UPLOAD_BYTES:
        raise ResearchDataFileTooLargeError(
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
    verification, F-02) before any evidence row is persisted."""
    try:
        object_key, stored_digest = datasets.put_raw_bytes(
            entity_id, content, content_type=content_type
        )
    except Exception as exc:
        raise ResearchDataUploadStorageFailedError() from exc

    try:
        roundtrip = datasets.get_raw_bytes(object_key)
    except Exception as exc:
        raise ResearchDataUploadStorageFailedError() from exc

    if len(roundtrip) != len(content) or datasets.content_digest(roundtrip) != stored_digest:
        raise ResearchDataUploadIntegrityError()

    return object_key, stored_digest
