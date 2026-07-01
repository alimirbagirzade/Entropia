"""Arrange Metrics command: append a Result View Metric Profile revision (Stage 5c,
doc 17 §7, §8, §9.3, §11, §14).

PRESENTATION-ONLY (CR-07): this NEVER touches a Backtest Result, ``metric_value``,
``result_summary`` or a run manifest — it only advances a display-preference
revision chain. Apply / Lock / Unlock are ALL the same append-only command driven
by ``is_locked`` + the selection. One transaction (supplied by the request
dependency, never committed here); shape mirrors the allocation command:

    require_authenticated + registry validation (OUTSIDE the idempotent body) ->
    run_idempotent op {
        resolve editable target root (first-apply forks a personal root from the
            in-memory System Default; a mis-targeted default when a personal profile
            exists is METRIC_PROFILE_STALE) ->
        session.refresh(with_for_update=True) + expected_profile_revision_id guard
            (409 METRIC_PROFILE_STALE) ->
        lock precondition (a locked profile refuses any change except a PURE unlock,
            409 METRIC_PROFILE_LOCKED) ->
        append immutable revision + advance head + row_version ->
        audit METRIC_PROFILE_UPDATED (+ apply/lock/unlock reason) + outbox
    }

The System Default profile is resolved in-memory from the registry (no DB row in
V1); Admin-writable persisted default is a tracked later refinement.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from entropia.application.idempotency import run_idempotent
from entropia.domain.identity import Actor
from entropia.domain.identity.policy import ensure_can_edit, require_admin, require_authenticated
from entropia.domain.metric_profile.enums import ProfileScope
from entropia.domain.metric_profile.profile import (
    compute_config_hash,
    normalize_selection,
    transition_reason,
)
from entropia.domain.metric_profile.registry import REGISTRY_VERSION
from entropia.infrastructure.postgres.repositories import audit as audit_repo
from entropia.infrastructure.postgres.repositories import metric_profile as mp_repo
from entropia.shared.errors import (
    MetricProfileLockedError,
    MetricProfileNotFoundError,
    MetricProfileStaleError,
)

_PROFILE_TARGET = "result_view_metric_profile"
_ACTIVE = "active"

# Synthetic id the resolved-profile GET returns when the caller has no personal
# profile yet; POSTing a revision to it forks a personal profile (doc 17 §8.1).
SYSTEM_DEFAULT_PROFILE_ID = "system_default"


async def create_metric_profile_revision(
    session: AsyncSession,
    actor: Actor,
    *,
    profile_id: str,
    expected_profile_revision_id: str | None = None,
    selected_metric_codes: list[str],
    is_locked: bool = False,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Apply / Lock / Unlock: append an immutable profile revision (doc 17 §7)."""
    require_authenticated(actor)
    # Registry validation is pure input validation (a read, no mutation) — outside
    # the idempotent body, exactly like the allocation command's config parse.
    snapshot = await mp_repo.load_registry_snapshot(session)
    normalized = normalize_selection(selected_metric_codes, snapshot)
    config_hash = compute_config_hash(
        selected_metric_codes=normalized,
        is_locked=is_locked,
        registry_version=REGISTRY_VERSION,
    )

    async def _op() -> dict[str, Any]:
        if profile_id == SYSTEM_DEFAULT_PROFILE_ID:
            root, current_is_locked, previous_revision_id, is_new = await _resolve_first_apply(
                session, actor
            )
        else:
            root, current_is_locked, previous_revision_id, is_new = await _resolve_existing(
                session, actor, profile_id, expected_profile_revision_id
            )

        previous_selection = await _previous_selection(session, previous_revision_id)
        _enforce_lock_precondition(
            current_is_locked=current_is_locked,
            next_is_locked=is_locked,
            normalized=normalized,
            previous_selection=previous_selection,
        )

        revision_no = await mp_repo.max_revision_no(session, root.profile_id) + 1
        revision = await mp_repo.create_revision(
            session,
            profile_id=root.profile_id,
            revision_no=revision_no,
            selected_metric_codes=normalized,
            display_order=normalized,
            is_locked=is_locked,
            registry_version=REGISTRY_VERSION,
            config_hash=config_hash,
            previous_revision_id=previous_revision_id,
            created_by_principal_id=actor.principal_id,
            audit_correlation_id=actor.correlation_id,
        )
        root.current_revision_id = revision.profile_revision_id
        if not is_new:
            root.row_version += 1

        reason = transition_reason(current_is_locked=current_is_locked, next_is_locked=is_locked)
        _emit_audit(
            session,
            actor,
            root=root,
            revision=revision,
            reason=reason,
            previous_selection=previous_selection,
            selected=normalized,
            previous_revision_id=previous_revision_id,
            is_locked=is_locked,
        )
        return _projection(root, revision, reason=reason)

    return await run_idempotent(
        session,
        key=idempotency_key,
        actor_principal_id=actor.principal_id,
        request_payload={
            "op": "create_metric_profile_revision",
            "profile_id": profile_id,
            "expected_profile_revision_id": expected_profile_revision_id,
            "selected_metric_codes": normalized,
            "is_locked": is_locked,
        },
        operation=_op,
    )


# --------------------------------------------------------------------------- #
# Target resolution                                                           #
# --------------------------------------------------------------------------- #


async def _resolve_first_apply(
    session: AsyncSession, actor: Actor
) -> tuple[Any, bool | None, str | None, bool]:
    """Fork a personal profile from the in-memory System Default (doc 17 §8.1).

    A personal profile already existing means the resolved GET would have returned
    it, so a default-targeted Apply is stale — reload and retry (doc 17 §8.5).
    """
    personal = await mp_repo.get_personal_profile(session, actor.principal_id or "")
    if personal is not None:
        raise MetricProfileStaleError()
    try:
        root = await mp_repo.create_profile_root(
            session, scope=ProfileScope.USER, owner_principal_id=actor.principal_id
        )
    except IntegrityError as exc:
        # A concurrent first-Apply won the UNIQUE(scope, owner_principal_id) race —
        # the personal profile now exists. Surface a clean 409 (reload + reapply,
        # doc 17 §8.5) instead of an unhandled 500; the DB constraint has already
        # guaranteed no duplicate was written.
        raise MetricProfileStaleError() from exc
    return root, None, None, True


async def _resolve_existing(
    session: AsyncSession,
    actor: Actor,
    profile_id: str,
    expected_profile_revision_id: str | None,
) -> tuple[Any, bool | None, str | None, bool]:
    """Resolve + lock an existing profile root under edit policy (doc 17 §2, §8.5)."""
    root = await mp_repo.get_profile(session, profile_id)
    if root is None or root.lifecycle_state != _ACTIVE:
        raise MetricProfileNotFoundError()
    if root.scope is ProfileScope.USER:
        ensure_can_edit(actor, owner_principal_id=root.owner_principal_id)
    else:
        # Persisted workspace/system default editing is Admin-only (doc 17 §2, §9.3);
        # no such row is seeded in V1, so this is a defensive guard.
        require_admin(actor)
    await session.refresh(root, with_for_update=True)
    if expected_profile_revision_id != root.current_revision_id:
        raise MetricProfileStaleError()
    current = (
        await mp_repo.get_revision(session, root.current_revision_id)
        if root.current_revision_id is not None
        else None
    )
    current_is_locked = current.is_locked if current is not None else None
    return root, current_is_locked, root.current_revision_id, False


def _enforce_lock_precondition(
    *,
    current_is_locked: bool | None,
    next_is_locked: bool,
    normalized: list[str],
    previous_selection: list[str] | None,
) -> None:
    """A locked profile refuses everything but a PURE unlock (doc 17 §7, §8.3, §11).

    Pure unlock = ``is_locked`` flips to false with the SAME selection. Re-applying
    while still locked, or changing the selection while locked, is
    METRIC_PROFILE_LOCKED (Unlock first, doc 17 §11).
    """
    if not current_is_locked:
        return
    if next_is_locked:
        raise MetricProfileLockedError()
    if previous_selection is not None and normalized != previous_selection:
        raise MetricProfileLockedError()


async def _previous_selection(
    session: AsyncSession, previous_revision_id: str | None
) -> list[str] | None:
    if previous_revision_id is None:
        return None
    revision = await mp_repo.get_revision(session, previous_revision_id)
    return list(revision.selected_metric_codes) if revision is not None else None


# --------------------------------------------------------------------------- #
# Projection + audit                                                          #
# --------------------------------------------------------------------------- #


def _projection(root: Any, revision: Any, *, reason: str) -> dict[str, Any]:
    return {
        "profile_id": root.profile_id,
        "scope": str(root.scope),
        "is_personal": root.scope is ProfileScope.USER,
        "current_revision_id": root.current_revision_id,
        "profile_revision_id": revision.profile_revision_id,
        "revision_no": revision.revision_no,
        "selected_metric_codes": list(revision.selected_metric_codes),
        "display_order": list(revision.display_order),
        "is_locked": revision.is_locked,
        "registry_version": revision.metric_definition_registry_version,
        "row_version": root.row_version,
        "reason": reason,
        "selected_metric_count": len(revision.selected_metric_codes),
    }


def _emit_audit(
    session: AsyncSession,
    actor: Actor,
    *,
    root: Any,
    revision: Any,
    reason: str,
    previous_selection: list[str] | None,
    selected: list[str],
    previous_revision_id: str | None,
    is_locked: bool,
) -> None:
    metadata = {
        "profile_id": root.profile_id,
        "scope": str(root.scope),
        "old_revision_id": previous_revision_id,
        "new_revision_id": revision.profile_revision_id,
        "old_selected_metric_codes": previous_selection,
        "new_selected_metric_codes": selected,
        "is_locked": is_locked,
        "registry_version": revision.metric_definition_registry_version,
        "reason": reason,
    }
    audit_repo.add_audit_event(
        session,
        event_kind="metric_profile.updated",
        actor_principal_id=actor.principal_id,
        actor_kind=actor.actor_kind,
        target_entity_id=root.profile_id,
        target_entity_type=_PROFILE_TARGET,
        target_revision_id=revision.profile_revision_id,
        new_state=reason,
        correlation_id=actor.correlation_id,
        metadata=metadata,
    )
    audit_repo.add_outbox_event(
        session,
        event_type="metric_profile.updated",
        resource_type=_PROFILE_TARGET,
        resource_id=root.profile_id,
        payload={
            "profile_id": root.profile_id,
            "profile_revision_id": revision.profile_revision_id,
            "reason": reason,
            "is_locked": is_locked,
            "selected_metric_codes": selected,
        },
        correlation_id=actor.correlation_id,
    )


__all__ = ["SYSTEM_DEFAULT_PROFILE_ID", "create_metric_profile_revision"]
