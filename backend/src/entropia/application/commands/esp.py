"""Embedded System Package (ESP) commands (doc 09 §8, §10, §11, DC1/DC4/DC6).

Each command runs in one transaction supplied by the request dependency and
NEVER commits (mirrors Stage 1/2a/2b). The shape per mutation is always:

    policy check -> domain state-machine check -> repo mutation
    -> add_audit_event ("esp.*") + add_outbox_event

Registry activation/deprecation are Admin-only (CR-02, doc 09 §2/§8/§10.3) and
record a generic ``approval_decision`` (target_kind="embedded_system_package").
Optimistic concurrency uses the registry version token: a stale
``expected_registry_version`` -> RESOLVER_REGISTRY_CONFLICT (409, doc 09 §9.4).
Idempotent commands route through ``application.idempotency.run_idempotent`` with
the concurrency + legality checks INSIDE the operation body (L2/D3), so a
completed-key replay returns the cached result instead of a spurious conflict.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from entropia.application.idempotency import run_idempotent
from entropia.domain.esp import policy as esp_policy
from entropia.domain.esp import validation as esp_validation
from entropia.domain.esp.enums import ResolverTrustState, RuntimeAdapter
from entropia.domain.esp.state_machine import next_resolver_trust_state
from entropia.domain.identity import Actor
from entropia.domain.identity.policy import require_authenticated
from entropia.domain.lifecycle.enums import ApprovalState, PackageKind, VisibilityScope
from entropia.domain.package.enums import PackageValidationState
from entropia.domain.package.kind import ensure_package_kind
from entropia.infrastructure.postgres.models import (
    EmbeddedResolverContract,
    EmbeddedResolverRegistry,
    PackageRevision,
    PackageRoot,
)
from entropia.infrastructure.postgres.repositories import approvals as approval_repo
from entropia.infrastructure.postgres.repositories import audit as audit_repo
from entropia.infrastructure.postgres.repositories import esp as esp_repo
from entropia.infrastructure.postgres.repositories import packages as pkg_repo
from entropia.shared.errors import (
    NotFoundError,
    ResolverContractInvalid,
    ResolverEvidenceRequired,
    ResolverRegistryConflict,
    ResolverValidationRequired,
)

# Audit target / approval target kind for ESP registry decisions (doc 09 §11.3).
_TARGET_KIND = "embedded_system_package"


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


async def _require_registry(session: AsyncSession, canonical_key: str) -> EmbeddedResolverRegistry:
    entry = await esp_repo.get_registry_by_key(session, canonical_key)
    if entry is None:
        raise NotFoundError(f"No resolver registry entry for key '{canonical_key}'.")
    return entry


async def create_esp_package(
    session: AsyncSession,
    actor: Actor,
    *,
    canonical_key: str,
    signature: dict[str, Any],
    runtime_adapter: RuntimeAdapter,
    input_contract: dict[str, Any],
    output_contract: dict[str, Any],
    dependency_snapshot: dict[str, Any] | None = None,
    warm_up_period: int | None = None,
    timing_semantics: str | None = None,
    repaint: bool = False,
    evidence: dict[str, Any] | None = None,
    package_kind: str | PackageKind = PackageKind.EMBEDDED_SYSTEM,
    visibility_scope: VisibilityScope = VisibilityScope.PRIVATE,
    change_note: str | None = None,
) -> dict[str, Any]:
    """Create an embedded_system PackageRoot + first revision + resolver contract.

    The proposal starts as a CANDIDATE registry entry (not trusted): Pre-Check
    cannot select it until an Admin activates it (doc 09 §5 "Draft / candidate").
    The package kind is guarded (CR-01): only ``embedded_system`` is accepted here;
    legacy ``trading_signal``/``trade_log`` are rejected with
    CLIENT_LEGACY_TYPE_REJECTED.
    """
    require_authenticated(actor)
    kind = ensure_package_kind(package_kind)
    if kind != PackageKind.EMBEDDED_SYSTEM:
        raise ResolverContractInvalid("An ESP package must have package_kind 'embedded_system'.")
    if not canonical_key.strip():
        raise ResolverContractInvalid("A resolver canonical key is required.")
    if not signature.get("params") and "return" not in signature:
        raise ResolverContractInvalid("A resolver signature must define params and a return shape.")

    deps = dependency_snapshot if dependency_snapshot is not None else {}
    root, _detail, revision = await pkg_repo.create_package(
        session,
        owner_principal_id=actor.principal_id,
        created_by_principal_id=actor.principal_id,
        package_kind=kind,
        input_contract=input_contract,
        output_contract=output_contract,
        dependency_snapshot=deps,
        visibility_scope=visibility_scope,
        validation_state=PackageValidationState.PENDING,
        approval_state=ApprovalState.DRAFT,
        change_note=change_note,
    )
    esp_repo.add_resolver_contract(
        session,
        entity_id=root.entity_id,
        revision_id=revision.revision_id,
        canonical_key=canonical_key,
        signature=signature,
        runtime_adapter=runtime_adapter,
        warm_up_period=warm_up_period,
        timing_semantics=timing_semantics,
        repaint=repaint,
        evidence=evidence,
    )
    # Register a CANDIDATE pointer for the key if none exists yet. An existing key
    # keeps its registry row (activation later repoints it via set_trust_state).
    existing = await esp_repo.get_registry_by_key(session, canonical_key)
    if existing is None:
        esp_repo.upsert_registry_entry(
            session,
            canonical_key=canonical_key,
            package_entity_id=root.entity_id,
            runtime_adapter=runtime_adapter,
            trust_state=ResolverTrustState.CANDIDATE,
            updated_by_principal_id=actor.principal_id,
        )
    _audit_and_outbox(
        session,
        actor,
        event_kind="esp.proposal.created",
        entity_id=root.entity_id,
        revision_id=revision.revision_id,
        new_state=str(ResolverTrustState.CANDIDATE),
        action="proposal_created",
    )
    return {
        "entity_id": root.entity_id,
        "revision_id": revision.revision_id,
        "canonical_key": canonical_key,
        "trust_state": str(ResolverTrustState.CANDIDATE),
        "runtime_adapter": str(runtime_adapter),
    }


async def activate_resolver(
    session: AsyncSession,
    actor: Actor,
    *,
    entity_id: str,
    revision_id: str,
    canonical_key: str,
    expected_registry_version: int | None = None,
    note: str | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Admin-only: activate a CANDIDATE resolver -> TRUSTED_ACTIVE (doc 09 §8/§10.2).

    A PASSED validation-run is a precondition for trusted activation (doc 09 §4.3
    step 5, §5, §7; post-V1 R8): the revision must have its stored test-vectors
    executed to ``validation_state=passed`` via ``run_resolver_validation`` first —
    a resolver with no/empty evidence is rejected ResolverEvidenceRequired (409),
    and a revision that has NOT reached ``passed`` (still ``pending``/``warning``/
    ``failed``) is rejected ResolverValidationRequired (409). This keeps registry
    trust and Pre-Check resolvability (which already requires ``validation_state ==
    passed``) in agreement — no longer a presence-only gate. Activation itself is
    still an APPROVAL: it records an approval_decision + audit("esp.registry.
    activated") + outbox in one transaction and stamps ``approval_state=approved``
    (the validation pass was stamped by the earlier run, not fabricated here). A
    stale ``expected_registry_version`` -> RESOLVER_REGISTRY_CONFLICT (409). The
    revision must belong to the resolver's package root; non-Admins are rejected
    with ApprovalRequiresAdmin (403) before the body runs.
    """
    esp_policy.ensure_can_activate(actor)
    entry = await _require_registry(session, canonical_key)
    revision = await _require_revision(session, entity_id, revision_id)
    contract = await esp_repo.get_contract_by_revision(session, revision_id)

    async def _op() -> dict[str, Any]:
        # Concurrency + legality checks live INSIDE the idempotent body (L2/D3):
        # a completed-key replay returns the stored result before reaching here.
        _check_registry_version(entry, expected_registry_version)
        _ensure_validation_passed(revision, contract)
        previous = entry.trust_state
        next_resolver_trust_state(previous, ResolverTrustState.TRUSTED_ACTIVE)
        # Activation is an APPROVAL decision layered on top of a PASSED validation
        # run (checked just above, R8): the earlier run set ``validation_state=
        # passed`` on the strength of the executed test-vectors; here we record the
        # Admin's approval and repoint the registry. We never fabricate the pass.
        revision.approval_state = ApprovalState.APPROVED
        esp_repo.set_trust_state(
            entry,
            trust_state=ResolverTrustState.TRUSTED_ACTIVE,
            trusted_active_revision_id=revision_id,
            updated_by_principal_id=actor.principal_id,
        )
        approval_repo.add_approval_decision(
            session,
            target_entity_id=entity_id,
            target_kind=_TARGET_KIND,
            decision=ApprovalState.APPROVED,
            target_revision_id=revision_id,
            approver_principal_id=actor.principal_id,
            prior_state=str(previous),
            new_state=str(entry.trust_state),
            note=note,
            policy_context={"action": "activate", "canonical_key": canonical_key},
        )
        _audit_and_outbox(
            session,
            actor,
            event_kind="esp.registry.activated",
            entity_id=entity_id,
            revision_id=revision_id,
            previous_state=str(previous),
            new_state=str(entry.trust_state),
            action="activated",
        )
        return {
            "entity_id": entity_id,
            "revision_id": revision_id,
            "canonical_key": canonical_key,
            "trust_state": str(entry.trust_state),
            "registry_version": entry.registry_version,
        }

    return await run_idempotent(
        session,
        key=idempotency_key,
        actor_principal_id=actor.principal_id,
        request_payload={
            "op": "activate_resolver",
            "entity_id": entity_id,
            "revision_id": revision_id,
        },
        operation=_op,
    )


async def run_resolver_validation(
    session: AsyncSession,
    actor: Actor,
    *,
    entity_id: str,
    revision_id: str,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Execute a resolver revision's stored test-vectors -> set ``validation_state`` (R8).

    The resolver's owner or an Admin may run validation (doc 09 §5 candidate evidence
    collection). Runs the deterministic ``esp_validation.run_resolver_validation`` suite over
    the contract's evidence + signature, copies the terminal status onto
    ``revision.validation_state``, writes an immutable ``embedded_resolver_validation_run``
    row and emits ``esp.validation.completed`` audit + outbox in one transaction. Idempotent
    on ``idempotency_key`` (a completed-key replay returns the cached report). Only after a
    ``passed`` run can an Admin ``activate_resolver`` the revision (doc 09 §4.3 step 5)."""
    revision = await _require_revision(session, entity_id, revision_id)
    root = await pkg_repo.get_package_root(session, entity_id)
    owner_principal_id = root.owner_principal_id if root is not None else None
    esp_policy.ensure_can_run_validation(actor, owner_principal_id=owner_principal_id)
    contract = await esp_repo.get_contract_by_revision(session, revision_id)
    if contract is None:
        raise ResolverContractInvalid("This resolver revision has no contract to validate.")
    canonical_key = contract.canonical_key
    signature = contract.signature
    evidence = contract.evidence
    repaint = contract.repaint

    async def _op() -> dict[str, Any]:
        report = esp_validation.run_resolver_validation(
            canonical_key=canonical_key,
            signature=signature,
            evidence=evidence,
            repaint=repaint,
        )
        revision.validation_state = report.status
        esp_repo.add_validation_run(
            session,
            entity_id=entity_id,
            revision_id=revision_id,
            canonical_key=canonical_key,
            status=report.status,
            validator_version=esp_validation.VALIDATOR_VERSION,
            vectors_run=report.vectors_run,
            checks=report.as_dict(),
            created_by_principal_id=actor.principal_id,
        )
        _audit_and_outbox(
            session,
            actor,
            event_kind="esp.validation.completed",
            entity_id=entity_id,
            revision_id=revision_id,
            new_state=str(report.status),
            action="validation_completed",
        )
        return {
            "entity_id": entity_id,
            "revision_id": revision_id,
            "canonical_key": canonical_key,
            "validation_state": str(report.status),
            "vectors_run": report.vectors_run,
            "checks": [c.as_dict() for c in report.checks],
        }

    return await run_idempotent(
        session,
        key=idempotency_key,
        actor_principal_id=actor.principal_id,
        request_payload={"op": "run_resolver_validation", "revision_id": revision_id},
        operation=_op,
    )


async def deprecate_resolver(
    session: AsyncSession,
    actor: Actor,
    *,
    canonical_key: str,
    reason: str,
    replacement_revision_id: str | None = None,
    expected_registry_version: int | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Admin-only: deprecate a TRUSTED_ACTIVE resolver -> DEPRECATED (doc 09 §8).

    A reason is required (doc 09 §6 "Deprecation Reason *"). Historical pins keep
    reading their exact revision; only new-work selection is closed. A stale
    ``expected_registry_version`` -> RESOLVER_REGISTRY_CONFLICT (409).
    """
    esp_policy.ensure_can_deprecate(actor)
    if not reason.strip():
        raise ResolverContractInvalid("A deprecation reason is required.")
    entry = await _require_registry(session, canonical_key)
    prior_revision_id = entry.trusted_active_revision_id

    async def _op() -> dict[str, Any]:
        _check_registry_version(entry, expected_registry_version)
        previous = entry.trust_state
        next_resolver_trust_state(previous, ResolverTrustState.DEPRECATED)
        esp_repo.set_trust_state(
            entry,
            trust_state=ResolverTrustState.DEPRECATED,
            replacement_revision_id=replacement_revision_id,
            updated_by_principal_id=actor.principal_id,
        )
        approval_repo.add_approval_decision(
            session,
            target_entity_id=entry.package_entity_id,
            target_kind=_TARGET_KIND,
            decision=ApprovalState.REJECTED,
            target_revision_id=prior_revision_id,
            approver_principal_id=actor.principal_id,
            prior_state=str(previous),
            new_state=str(entry.trust_state),
            note=reason,
            policy_context={
                "action": "deprecate",
                "canonical_key": canonical_key,
                "replacement_revision_id": replacement_revision_id,
            },
        )
        _audit_and_outbox(
            session,
            actor,
            event_kind="esp.deprecated",
            entity_id=entry.package_entity_id,
            revision_id=prior_revision_id,
            previous_state=str(previous),
            new_state=str(entry.trust_state),
            action="deprecated",
        )
        return {
            "canonical_key": canonical_key,
            "entity_id": entry.package_entity_id,
            "trust_state": str(entry.trust_state),
            "replacement_revision_id": replacement_revision_id,
            "registry_version": entry.registry_version,
        }

    return await run_idempotent(
        session,
        key=idempotency_key,
        actor_principal_id=actor.principal_id,
        request_payload={"op": "deprecate_resolver", "canonical_key": canonical_key},
        operation=_op,
    )


def _check_registry_version(
    entry: EmbeddedResolverRegistry, expected_registry_version: int | None
) -> None:
    """Optimistic-concurrency guard on the registry pointer (doc 09 §9.4)."""
    if (
        expected_registry_version is not None
        and entry.registry_version != expected_registry_version
    ):
        raise ResolverRegistryConflict(
            f"Expected registry version {expected_registry_version} "
            f"but current is {entry.registry_version}."
        )


def _ensure_activation_evidence(contract: EmbeddedResolverContract | None) -> None:
    """Precondition gate: a resolver may only be trusted-activated when its
    contract carries test-vector evidence (doc 09 §4.1/§4.2/§7 "Passing evidence
    is a precondition for registry activation. LLM output or package name is not
    evidence."). This checks PRESENCE only — a missing/empty ``evidence`` payload
    is rejected; whether those vectors actually pass is the separate validation-run
    plane (GAP-07 core), deliberately NOT wired here.
    """
    if contract is None or not contract.evidence:
        raise ResolverEvidenceRequired(
            "This resolver revision has no test-vector evidence; attach passing "
            "evidence before activation."
        )


def _ensure_validation_passed(
    revision: PackageRevision, contract: EmbeddedResolverContract | None
) -> None:
    """Activation gate (R8): the resolver must carry evidence AND have reached
    ``validation_state=passed`` via a validation-run (doc 09 §4.3 step 5, §5, §7).

    The evidence-presence check runs FIRST so a bare proposal returns the more specific
    RESOLVER_EVIDENCE_REQUIRED; a resolver that has evidence but has not passed its run
    (still ``pending``/``warning``/``failed``) returns RESOLVER_VALIDATION_REQUIRED. This
    replaces the presence-only gate so registry trust and Pre-Check resolvability (which
    already requires ``validation_state == passed``) finally agree."""
    _ensure_activation_evidence(contract)
    if revision.validation_state != PackageValidationState.PASSED:
        raise ResolverValidationRequired(
            "This resolver has not passed validation; run its test vectors before activation."
        )


async def _require_revision(
    session: AsyncSession, entity_id: str, revision_id: str
) -> PackageRevision:
    """Resolve the ESP revision, verifying it belongs to an embedded_system root."""
    root = await pkg_repo.get_package_root(session, entity_id)
    if root is None:
        raise NotFoundError(f"Embedded System Package '{entity_id}' not found.")
    detail: PackageRoot | None = await pkg_repo.get_package_detail(session, entity_id)
    if detail is None or detail.package_kind != PackageKind.EMBEDDED_SYSTEM:
        raise NotFoundError(f"Embedded System Package '{entity_id}' not found.")
    revision = await pkg_repo.get_revision(session, revision_id)
    if revision is None or revision.entity_id != entity_id:
        raise NotFoundError(f"Revision '{revision_id}' not found for this resolver.")
    return revision


__all__ = [
    "activate_resolver",
    "create_esp_package",
    "deprecate_resolver",
    "run_resolver_validation",
]
