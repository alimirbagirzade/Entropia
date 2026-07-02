"""Future Dev capability commands (Stage 7b, doc 22 §8, §9, §12).

Each command is ONE transaction (no commit here). ``transition_capability``
mirrors the 7a manual pattern: Admin guard at route AND service, legal state
edge, non-empty reason, ``expected_registry_version`` OCC against the row
locked with ``with_for_update``, activation gates, then registry mutation +
immutable activation event + audit + outbox together (doc 22 §8).

The operational commands (``query_view_dataset``, ``create_analysis_artifact``)
re-check the server-side capability state FIRST: below Limited/Active they
raise CAPABILITY_NOT_ACTIVE and create no job, no row, no output (CR-09,
FD-02) — the client's cached state is never trusted.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from entropia.application.idempotency import run_idempotent
from entropia.domain.capability.enums import (
    BACKTEST_REVIEW,
    CAPABILITY_ENTITY_TYPE,
    GRAPHIC_VIEW,
    PARAMETER_FIELDS,
    REGIME_RESEARCH,
    SIGNAL_INTELLIGENCE,
    CapabilityState,
)
from entropia.domain.capability.lifecycle import (
    ensure_gates_pass,
    ensure_operational,
    ensure_transition_legal,
    parse_capability_state,
    snapshot_checksum,
)
from entropia.domain.identity import Actor
from entropia.domain.identity.policy import require_authenticated, require_capability_admin
from entropia.infrastructure.postgres.models import FutureCapability
from entropia.infrastructure.postgres.repositories import audit as audit_repo
from entropia.infrastructure.postgres.repositories import capability as capability_repo
from entropia.shared.errors import (
    CapabilityNotFoundError,
    CapabilityStateStaleError,
    CapabilityTransitionRejectedError,
    ValidationError,
)

MAX_REASON_LENGTH = 512

# Which capability gates each analysis artifact type (doc 22 §10.3-§10.6):
# review/MC/WFA validate results (Backtest Review); sensitivity plans belong to
# Parameter Fields; label/regime outputs to their research capabilities.
ANALYSIS_ARTIFACT_CAPABILITY: dict[str, str] = {
    "backtest_review": BACKTEST_REVIEW,
    "monte_carlo": BACKTEST_REVIEW,
    "walk_forward": BACKTEST_REVIEW,
    "signal_intelligence": SIGNAL_INTELLIGENCE,
    "regime_research": REGIME_RESEARCH,
    "parameter_fields": PARAMETER_FIELDS,
    "sensitivity": PARAMETER_FIELDS,
}


# --------------------------------------------------------------------------- #
# Shared helpers                                                               #
# --------------------------------------------------------------------------- #


async def _require_capability(session: AsyncSession, capability_key: str) -> FutureCapability:
    capability = await capability_repo.get_capability_by_key(session, capability_key)
    if capability is None:
        raise CapabilityNotFoundError()
    return capability


async def require_operational_capability(
    session: AsyncSession, capability_key: str
) -> FutureCapability:
    """Server-side inactive-operation guard (doc 22 §12, FD-02): a missing or
    below-Limited/Active capability yields CAPABILITY_NOT_ACTIVE before any
    validation, job or persistence happens."""
    capability = await _require_capability(session, capability_key)
    ensure_operational(capability.lifecycle_state, capability_key)
    return capability


def _normalize_refs(raw: Any, *, field: str) -> list[str]:
    """Pinned immutable references: a non-empty list of non-blank strings
    (doc 22 §6.1 source-manifest-refs rule)."""
    if not isinstance(raw, list):
        raise ValidationError(
            f"{field} must be a list of immutable reference ids.",
            details=[{"field": field, "issue": "not_a_list"}],
        )
    refs = [str(item).strip() for item in raw if str(item).strip()]
    if len(refs) != len(raw) or not refs:
        raise ValidationError(
            f"{field} must pin at least one non-empty immutable reference.",
            details=[{"field": field, "issue": "empty_or_blank_ref"}],
        )
    return refs


def _required_text(raw: str | None, *, field: str, max_length: int) -> str:
    value = " ".join((raw or "").split())
    if not value:
        raise ValidationError(
            f"{field} is required.", details=[{"field": field, "issue": "required"}]
        )
    if len(value) > max_length:
        raise ValidationError(
            f"{field} exceeds {max_length} characters.",
            details=[{"field": field, "issue": "too_long"}],
        )
    return value


def _audit_and_outbox(
    session: AsyncSession,
    actor: Actor,
    *,
    event_kind: str,
    entity_type: str,
    entity_id: str,
    previous_state: str | None,
    new_state: str | None,
    payload: dict[str, Any],
    reason: str | None = None,
) -> None:
    audit_repo.add_audit_event(
        session,
        event_kind=event_kind,
        actor_principal_id=actor.principal_id,
        actor_kind=actor.actor_kind,
        target_entity_id=entity_id,
        target_entity_type=entity_type,
        target_revision_id=None,
        previous_state=previous_state,
        new_state=new_state,
        reason=reason,
        correlation_id=actor.correlation_id,
    )
    audit_repo.add_outbox_event(
        session,
        event_type=event_kind,
        resource_type=entity_type,
        resource_id=entity_id,
        payload=payload,
        correlation_id=actor.correlation_id,
    )


def _capability_envelope(capability: FutureCapability) -> dict[str, Any]:
    return {
        "capability_id": capability.capability_id,
        "capability_key": capability.capability_key,
        "title": capability.title,
        "menu_path": capability.menu_path,
        "lifecycle_state": capability.lifecycle_state.value,
        "ui_surface_version": capability.ui_surface_version,
        "domain_contract_version": capability.domain_contract_version,
        "registry_version": capability.registry_version,
        "enabled_at": capability.enabled_at.isoformat() if capability.enabled_at else None,
        "retirement_at": (
            capability.retirement_at.isoformat() if capability.retirement_at else None
        ),
    }


# --------------------------------------------------------------------------- #
# Admin lifecycle transition (doc 22 §8, §9.1, §9.2, §12)                       #
# --------------------------------------------------------------------------- #


async def transition_capability(
    session: AsyncSession,
    actor: Actor,
    *,
    capability_key: str,
    to_state: str,
    reason: str,
    expected_registry_version: int,
    dependency_snapshot: dict[str, Any] | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Admin-only lifecycle transition: legal edge + non-empty reason +
    ``expected_registry_version`` OCC + activation gates; the registry mutation,
    the immutable activation event and audit/outbox commit together (doc 22 §8).
    Both the idempotency key and the expected registry version are REQUIRED."""
    require_capability_admin(actor)
    target = parse_capability_state(to_state)
    final_reason = " ".join((reason or "").split())
    if not final_reason:
        raise CapabilityTransitionRejectedError(
            "A non-empty transition reason is required.",
            details=[{"field": "reason", "issue": "required"}],
        )
    if len(final_reason) > MAX_REASON_LENGTH:
        raise ValidationError(
            f"The transition reason exceeds {MAX_REASON_LENGTH} characters.",
            details=[{"field": "reason", "issue": "too_long"}],
        )
    if not (idempotency_key or "").strip():
        raise ValidationError(
            "An Idempotency-Key is required for capability lifecycle transitions.",
            details=[{"field": "idempotency_key", "issue": "required"}],
        )

    async def _op() -> dict[str, Any]:
        capability = await _require_capability(session, capability_key)
        await session.refresh(capability, with_for_update=True)
        if expected_registry_version != capability.registry_version:
            raise CapabilityStateStaleError()
        from_state = capability.lifecycle_state
        ensure_transition_legal(from_state, target)
        snapshot = (
            dependency_snapshot
            if dependency_snapshot is not None
            else (capability.dependency_snapshot or {})
        )
        ensure_gates_pass(snapshot, target)

        now = datetime.now(UTC)
        capability.lifecycle_state = target
        capability.dependency_snapshot = snapshot
        capability.registry_version += 1
        capability.changed_by_actor_id = actor.principal_id
        capability.change_reason = final_reason
        if target in (CapabilityState.LIMITED, CapabilityState.ACTIVE):
            capability.enabled_at = capability.enabled_at or now
        if target is CapabilityState.RETIRED:
            capability.retirement_at = now
        event = await capability_repo.add_activation_event(
            session,
            capability_id=capability.capability_id,
            capability_key=capability.capability_key,
            from_state=from_state,
            to_state=target,
            actor_principal_id=actor.principal_id,
            reason=final_reason,
            dependency_snapshot=snapshot,
            snapshot_checksum=snapshot_checksum(snapshot),
            prior_registry_version=expected_registry_version,
            resulting_registry_version=capability.registry_version,
            correlation_id=actor.correlation_id,
        )
        _audit_and_outbox(
            session,
            actor,
            event_kind="capability_state_changed",
            entity_type=CAPABILITY_ENTITY_TYPE,
            entity_id=capability.capability_id,
            previous_state=from_state.value,
            new_state=target.value,
            payload={
                "capability_key": capability.capability_key,
                "from_state": from_state.value,
                "to_state": target.value,
                "registry_version": capability.registry_version,
                "activation_event_id": event.event_id,
                "snapshot_checksum": event.snapshot_checksum,
            },
            reason=final_reason,
        )
        return {
            **_capability_envelope(capability),
            "activation_event_id": event.event_id,
            "correlation_id": actor.correlation_id,
        }

    return await run_idempotent(
        session,
        key=idempotency_key,
        actor_principal_id=actor.principal_id,
        request_payload={
            "op": "capability.lifecycle_transition",
            "capability_key": capability_key,
            "to_state": to_state,
            "reason": final_reason,
            "expected_registry_version": expected_registry_version,
            "dependency_snapshot": dependency_snapshot,
        },
        operation=_op,
    )


# --------------------------------------------------------------------------- #
# Operational commands — Limited/Active only (doc 22 §8, FD-02/04/05)           #
# --------------------------------------------------------------------------- #


async def query_view_dataset(
    session: AsyncSession,
    actor: Actor,
    *,
    source_manifest_refs: list[str],
    schema_version: str,
    series_refs: list[str] | None = None,
    marker_refs: list[str] | None = None,
    range_spec: dict[str, Any] | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Prepare a renderer-independent View Dataset from PINNED immutable source
    refs (doc 22 §8, §10.2, FD-04). Requires graphic_view Limited/Active — a
    placeholder cannot start it and no fake dataset/job is created (CR-09)."""
    require_authenticated(actor)

    async def _op() -> dict[str, Any]:
        # State gate FIRST: an inactive capability rejects before validation.
        await require_operational_capability(session, GRAPHIC_VIEW)
        refs = _normalize_refs(source_manifest_refs, field="source_manifest_refs")
        version = _required_text(schema_version, field="schema_version", max_length=32)
        series = _normalize_refs(series_refs, field="series_refs") if series_refs else []
        markers = _normalize_refs(marker_refs, field="marker_refs") if marker_refs else []

        dataset = await capability_repo.create_view_dataset(
            session,
            capability_key=GRAPHIC_VIEW,
            source_manifest_refs=refs,
            series_refs=series,
            marker_refs=markers,
            range_spec=range_spec,
            schema_version=version,
            owner_principal_id=actor.principal_id,
            created_by_principal_id=actor.principal_id,
        )
        _audit_and_outbox(
            session,
            actor,
            event_kind="view_dataset_prepared",
            entity_type="view_dataset",
            entity_id=dataset.view_dataset_id,
            previous_state=None,
            new_state="prepared",
            payload={
                "view_dataset_id": dataset.view_dataset_id,
                "capability_key": GRAPHIC_VIEW,
                "source_manifest_refs": refs,
                "schema_version": version,
            },
        )
        return {
            "view_dataset_id": dataset.view_dataset_id,
            "capability_key": GRAPHIC_VIEW,
            "source_manifest_refs": refs,
            "series_refs": series,
            "marker_refs": markers,
            "range_spec": range_spec,
            "schema_version": version,
            "correlation_id": actor.correlation_id,
        }

    return await run_idempotent(
        session,
        key=idempotency_key,
        actor_principal_id=actor.principal_id,
        request_payload={
            "op": "view_dataset.query",
            "source_manifest_refs": source_manifest_refs,
            "schema_version": schema_version,
            "series_refs": series_refs,
            "marker_refs": marker_refs,
            "range_spec": range_spec,
        },
        operation=_op,
    )


async def create_analysis_artifact(
    session: AsyncSession,
    actor: Actor,
    *,
    artifact_type: str,
    input_manifest_refs: list[str],
    method_version: str,
    output_ref: str | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Create one immutable Analysis Artifact (doc 22 §8, FD-05/09): pinned
    input manifest refs + method version are mandatory; the gating capability
    (per artifact type) must be Limited/Active; canonical Backtest Result
    fields are never touched."""
    require_authenticated(actor)
    normalized_type = (artifact_type or "").strip().lower()
    gating_capability = ANALYSIS_ARTIFACT_CAPABILITY.get(normalized_type)
    if gating_capability is None:
        raise ValidationError(
            f"Unknown analysis artifact type '{artifact_type}'.",
            details=[
                {
                    "field": "artifact_type",
                    "issue": "unknown_type",
                    "allowed": sorted(ANALYSIS_ARTIFACT_CAPABILITY),
                }
            ],
        )

    async def _op() -> dict[str, Any]:
        await require_operational_capability(session, gating_capability)
        refs = _normalize_refs(input_manifest_refs, field="input_manifest_refs")
        method = _required_text(method_version, field="method_version", max_length=64)

        artifact = await capability_repo.create_analysis_artifact(
            session,
            artifact_type=normalized_type,
            capability_key=gating_capability,
            input_manifest_refs=refs,
            method_version=method,
            output_ref=output_ref,
            owner_principal_id=actor.principal_id,
            created_by_principal_id=actor.principal_id,
        )
        _audit_and_outbox(
            session,
            actor,
            event_kind="analysis_artifact_created",
            entity_type="analysis_artifact",
            entity_id=artifact.artifact_id,
            previous_state=None,
            new_state="created",
            payload={
                "artifact_id": artifact.artifact_id,
                "artifact_type": normalized_type,
                "capability_key": gating_capability,
                "input_manifest_refs": refs,
                "method_version": method,
            },
        )
        return {
            "artifact_id": artifact.artifact_id,
            "artifact_type": normalized_type,
            "capability_key": gating_capability,
            "input_manifest_refs": refs,
            "method_version": method,
            "output_ref": output_ref,
            "correlation_id": actor.correlation_id,
        }

    return await run_idempotent(
        session,
        key=idempotency_key,
        actor_principal_id=actor.principal_id,
        request_payload={
            "op": "analysis_artifact.create",
            "artifact_type": normalized_type,
            "input_manifest_refs": input_manifest_refs,
            "method_version": method_version,
            "output_ref": output_ref,
        },
        operation=_op,
    )


__all__ = [
    "ANALYSIS_ARTIFACT_CAPABILITY",
    "create_analysis_artifact",
    "query_view_dataset",
    "require_operational_capability",
    "transition_capability",
]
