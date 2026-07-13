"""Embedded System Package (ESP) read-side queries (doc 09 §4, §10).

Role-aware: soft-deleted and unauthorized resolvers are excluded server-side, not
by the client (doc 09 §2, §15 "Role-aware list"). Cursor pagination uses the
"fetch limit+1" pattern. ``resolve_embedded_dependency`` implements the DC3 /
doc 09 §4.3 algorithm: a resolver is resolved only on exact key + signature +
adapter + trusted_active + validation passed + approval approved; each failing
precondition maps to the exact typed error so Pre-Check can branch precisely.

All return values are JSON-safe dicts (``str(enum)``, ``.isoformat()``). ESP
performance fields are N/A, never fabricated zeroes (L4 / doc 09 §14).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from entropia.domain.esp import policy as esp_policy
from entropia.domain.esp.enums import ResolverTrustState, RuntimeAdapter
from entropia.domain.esp.resolver import ResolutionReason, evaluate_resolution
from entropia.domain.identity import Actor
from entropia.domain.lifecycle.enums import DeletionState, PackageKind
from entropia.infrastructure.postgres.models import (
    EmbeddedResolverContract,
    EmbeddedResolverRegistry,
    EmbeddedResolverValidationRun,
    EntityRegistry,
    PackageRoot,
)
from entropia.infrastructure.postgres.repositories import esp as esp_repo
from entropia.infrastructure.postgres.repositories import packages as pkg_repo
from entropia.shared.errors import (
    NotFoundError,
    ResolverAdapterIncompatible,
    ResolverNotResolved,
    ResolverSignatureMismatch,
)
from entropia.shared.pagination import PageParams

# ESP performance metrics are not applicable (doc 09 §14, §3.3, L4).
_NOT_APPLICABLE = "not_applicable"


def _visibility_of(detail: PackageRoot, root: EntityRegistry) -> str:
    """Trusted/system ESPs are visible to all; otherwise use the stored scope."""
    return str(detail.visibility_scope)


def _registry_dict(entry: EmbeddedResolverRegistry) -> dict[str, Any]:
    return {
        "registry_id": entry.registry_id,
        "canonical_key": entry.canonical_key,
        "package_entity_id": entry.package_entity_id,
        "trusted_active_revision_id": entry.trusted_active_revision_id,
        "trust_state": str(entry.trust_state),
        "runtime_adapter": str(entry.runtime_adapter),
        "registry_version": entry.registry_version,
        "replacement_revision_id": entry.replacement_revision_id,
        # Performance metrics are N/A for resolvers (never fabricated, L4).
        "net_profit": _NOT_APPLICABLE,
        "backtest_ready": _NOT_APPLICABLE,
        "oos_passed": _NOT_APPLICABLE,
    }


async def list_embedded_system_packages(
    session: AsyncSession,
    actor: Actor,
    params: PageParams,
    *,
    trust_state: ResolverTrustState | None = None,
) -> dict[str, Any]:
    """List resolver registry entries visible to the actor, cursor-paginated.

    Role-aware (doc 09 §2): a registry entry is visible when the actor can view its
    backing package root. Soft-deleted package roots are excluded server-side.
    """
    stmt = (
        select(EmbeddedResolverRegistry, PackageRoot, EntityRegistry)
        .join(PackageRoot, PackageRoot.entity_id == EmbeddedResolverRegistry.package_entity_id)
        .join(
            EntityRegistry, EntityRegistry.entity_id == EmbeddedResolverRegistry.package_entity_id
        )
        .where(
            EntityRegistry.entity_type == pkg_repo.ENTITY_TYPE,
            EntityRegistry.deletion_state == DeletionState.ACTIVE,
            PackageRoot.package_kind == PackageKind.EMBEDDED_SYSTEM,
        )
        .order_by(EmbeddedResolverRegistry.canonical_key.asc())
    )
    if trust_state is not None:
        stmt = stmt.where(EmbeddedResolverRegistry.trust_state == trust_state)
    if params.cursor is not None:
        stmt = stmt.where(EmbeddedResolverRegistry.canonical_key > params.cursor)
    stmt = stmt.limit(params.limit + 1)

    rows = list((await session.execute(stmt)).all())
    visible = [
        (entry, detail, root) for entry, detail, root in rows if _can_view(actor, detail, root)
    ]
    has_more = len(visible) > params.limit
    page = visible[: params.limit]
    next_cursor = page[-1][0].canonical_key if has_more and page else None
    return {
        "data": [_registry_dict(entry) for entry, _detail, _root in page],
        "meta": {"cursor": next_cursor, "has_more": has_more},
    }


def _can_view(actor: Actor, detail: PackageRoot, root: EntityRegistry) -> bool:
    from entropia.domain.identity import policy as identity_policy

    return identity_policy.can_view(
        actor,
        owner_principal_id=root.owner_principal_id,
        visibility=_visibility_of(detail, root),
    )


async def get_esp_detail(session: AsyncSession, actor: Actor, *, entity_id: str) -> dict[str, Any]:
    """Return the resolver detail, re-checking view permission server-side."""
    root = await pkg_repo.get_package_root(session, entity_id)
    if root is None or root.deletion_state != DeletionState.ACTIVE:
        raise NotFoundError(f"Embedded System Package '{entity_id}' not found.")
    detail = await pkg_repo.get_package_detail(session, entity_id)
    if detail is None or detail.package_kind != PackageKind.EMBEDDED_SYSTEM:
        raise NotFoundError(f"Embedded System Package '{entity_id}' not found.")
    esp_policy.ensure_can_view(
        actor,
        owner_principal_id=root.owner_principal_id,
        visibility=_visibility_of(detail, root),
    )
    revision = await pkg_repo.get_revision(session, root.current_revision_id or "")
    if revision is None:
        raise NotFoundError("Resolver has no current revision.")
    contract = await esp_repo.get_contract_by_revision(session, revision.revision_id)
    entry = (
        await esp_repo.get_registry_by_key(session, contract.canonical_key)
        if contract is not None
        else None
    )
    latest_run = await esp_repo.get_latest_validation_run(session, revision.revision_id)
    return {
        "entity_id": entity_id,
        "revision_id": revision.revision_id,
        "revision_no": revision.revision_no,
        "package_kind": str(detail.package_kind),
        "visibility_scope": str(detail.visibility_scope),
        "validation_state": str(revision.validation_state),
        "approval_state": str(revision.approval_state),
        "content_hash": revision.content_hash,
        "row_version": root.row_version,
        "lifecycle_state": root.lifecycle_state,
        "owner_principal_id": root.owner_principal_id,
        "contract": _contract_dict(contract) if contract is not None else None,
        "registry": _registry_dict(entry) if entry is not None else None,
        "latest_validation_run": _validation_run_dict(latest_run),
        "created_at": revision.created_at.isoformat() if revision.created_at else None,
        # Resolver perf fields are N/A (never fabricated, L4 / doc 09 §14).
        "net_profit": _NOT_APPLICABLE,
        "backtest_ready": _NOT_APPLICABLE,
        "oos_passed": _NOT_APPLICABLE,
    }


def _validation_run_dict(run: EmbeddedResolverValidationRun | None) -> dict[str, Any] | None:
    """Surface the latest validation-run (status + checks) for the detail projection (R8)."""
    if run is None:
        return None
    return {
        "run_id": run.run_id,
        "status": str(run.status),
        "validator_version": run.validator_version,
        "vectors_run": run.vectors_run,
        "checks": run.checks,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
    }


def _contract_dict(contract: EmbeddedResolverContract) -> dict[str, Any]:
    return {
        "contract_id": contract.contract_id,
        "canonical_key": contract.canonical_key,
        "signature": contract.signature,
        "runtime_adapter": str(contract.runtime_adapter),
        "warm_up_period": contract.warm_up_period,
        "timing_semantics": contract.timing_semantics,
        "repaint": contract.repaint,
        "evidence": contract.evidence,
    }


_REASON_ERRORS = {
    ResolutionReason.SIGNATURE_MISMATCH: ResolverSignatureMismatch,
    ResolutionReason.ADAPTER_INCOMPATIBLE: ResolverAdapterIncompatible,
}


async def resolve_embedded_dependency(
    session: AsyncSession,
    *,
    parsed_call: dict[str, Any],
    target_runtime: RuntimeAdapter | str,
) -> dict[str, Any]:
    """Resolve a parsed source call to an exact trusted ESP revision (doc 09 §4.3).

    ``parsed_call`` is ``{"key": <canonical_key>, "signature": {"params": [...],
    "return": ...}}``. On success returns the EXACT pinned revision id + content
    hash + contract snapshot (P4/L5 — never name-only/latest). On failure raises
    the precise typed error so Pre-Check branches correctly:
      * signature mismatch -> RESOLVER_SIGNATURE_MISMATCH (422),
      * adapter incompatible -> RESOLVER_ADAPTER_INCOMPATIBLE (409),
      * key not found / not trusted / not passed / not approved -> RESOLVER_NOT_RESOLVED (404).
    """
    canonical_key = str(parsed_call.get("key", "")).strip()
    parsed_signature = parsed_call.get("signature") or {}

    entry = await esp_repo.get_registry_by_key(session, canonical_key) if canonical_key else None
    if entry is None or entry.trusted_active_revision_id is None:
        raise ResolverNotResolved("No trusted Embedded System Package matched this dependency.")
    contract = await esp_repo.get_contract_by_revision(session, entry.trusted_active_revision_id)
    if contract is None:
        raise ResolverNotResolved("The trusted resolver revision has no contract.")
    revision = await pkg_repo.get_revision(session, entry.trusted_active_revision_id)
    if revision is None:
        raise ResolverNotResolved("The trusted resolver revision is missing.")

    outcome = evaluate_resolution(
        key_matches=contract.canonical_key == canonical_key,
        parsed_call_signature=parsed_signature,
        contract_signature=contract.signature,
        contract_adapter=contract.runtime_adapter,
        target_runtime=target_runtime,
        trust_state=entry.trust_state,
        validation_state=revision.validation_state,
        approval_state=revision.approval_state,
    )
    if not outcome.is_resolved:
        error_cls = _REASON_ERRORS.get(outcome.reason, ResolverNotResolved)
        raise error_cls()

    return {
        "resolved": True,
        "canonical_key": canonical_key,
        "entity_id": entry.package_entity_id,
        "revision_id": revision.revision_id,
        "content_hash": revision.content_hash,
        "runtime_adapter": str(contract.runtime_adapter),
        "registry_version": entry.registry_version,
        "signature": contract.signature,
        "evidence": contract.evidence,
    }


__all__ = [
    "get_esp_detail",
    "list_embedded_system_packages",
    "resolve_embedded_dependency",
]
