"""Explicit package-sharing commands (GAP-17; Master Reference §6, §6.4).

Each command runs in the request's transaction and NEVER commits (mirrors the
other command modules). The shape per mutation is:

    resolve grantee -> policy check -> OCC check -> shareable-visibility check
    -> repo mutation -> flip root visibility -> bump row_version
    -> add_audit_event ("package.shared" / "package.share_revoked") + outbox

Only the owner or an Admin may manage shares; sharing NEVER changes ownership
(Master §6.4). Optimistic concurrency uses the package root ``row_version`` (the
If-Match / ``expected_row_version`` token): a stale token -> STALE_REVISION (409).
Idempotent commands route through ``run_idempotent`` with the concurrency +
legality checks INSIDE the operation body, and additionally short-circuit on an
already-active grant / already-revoked grant so a differently-keyed retry is a
no-op rather than a spurious duplicate or conflict.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from entropia.application.idempotency import run_idempotent
from entropia.domain.identity import Actor
from entropia.domain.identity import policy as identity_policy
from entropia.domain.lifecycle.enums import DeletionState, VisibilityScope
from entropia.domain.sharing import (
    ShareResourceType,
    ensure_can_manage_shares,
    ensure_distinct_grantee,
    ensure_shareable_visibility,
)
from entropia.infrastructure.postgres.models import EntityRegistry, PackageRoot
from entropia.infrastructure.postgres.repositories import audit as audit_repo
from entropia.infrastructure.postgres.repositories import identity as identity_repo
from entropia.infrastructure.postgres.repositories import packages as pkg_repo
from entropia.infrastructure.postgres.repositories import resource_share as share_repo
from entropia.shared.concurrency import check_row_version
from entropia.shared.errors import (
    NotFoundError,
    ShareGranteeNotFoundError,
    ShareGrantNotFoundError,
)

_RESOURCE_TYPE = str(ShareResourceType.PACKAGE)


def _audit_and_outbox(
    session: AsyncSession,
    actor: Actor,
    *,
    event_kind: str,
    entity_id: str,
    action: str,
    grantee_principal_id: str | None,
    previous_visibility: str | None,
    new_visibility: str | None,
) -> None:
    audit_repo.add_audit_event(
        session,
        event_kind=event_kind,
        actor_principal_id=actor.principal_id,
        actor_kind=actor.actor_kind,
        target_entity_id=entity_id,
        target_entity_type=_RESOURCE_TYPE,
        target_revision_id=None,
        previous_state=previous_visibility,
        new_state=new_visibility,
        correlation_id=actor.correlation_id,
    )
    audit_repo.add_outbox_event(
        session,
        event_type="resource.changed",
        resource_type=_RESOURCE_TYPE,
        resource_id=entity_id,
        payload={"action": action, "grantee_principal_id": grantee_principal_id},
        correlation_id=actor.correlation_id,
    )


async def _require_package(
    session: AsyncSession, entity_id: str
) -> tuple[EntityRegistry, PackageRoot]:
    """Load an active package root + its detail, or raise a metadata-free 404."""
    root = await pkg_repo.get_package_root(session, entity_id)
    if root is None or root.deletion_state != DeletionState.ACTIVE:
        raise NotFoundError(f"Package '{entity_id}' not found.")
    detail = await pkg_repo.get_package_detail(session, entity_id)
    if detail is None:
        raise NotFoundError(f"Package '{entity_id}' not found.")
    return root, detail


async def share_package(
    session: AsyncSession,
    actor: Actor,
    *,
    entity_id: str,
    grantee_email: str,
    expected_row_version: int | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Grant a specific active user explicit view/use access to a private package.

    Resolves the grantee by email (an unknown/inactive recipient ->
    SHARE_GRANTEE_NOT_FOUND, no row created), rejects a self-share, requires the
    caller be the owner or an Admin, and flips a PRIVATE head to EXPLICITLY_SHARED
    on the first grant. Re-sharing with the same grantee is a no-op that returns
    the current state. Emits ``package.shared`` audit + outbox.
    """
    identity_policy.require_authenticated(actor)
    grantee = await identity_repo.get_active_user_by_email(session, grantee_email)
    if grantee is None:
        raise ShareGranteeNotFoundError()
    grantee_principal_id = grantee.user_id
    ensure_distinct_grantee(actor.principal_id, grantee_principal_id)

    async def _op() -> dict[str, Any]:
        root, detail = await _require_package(session, entity_id)
        ensure_can_manage_shares(actor, owner_principal_id=root.owner_principal_id)
        check_row_version(root.row_version, expected_row_version)
        ensure_shareable_visibility(str(detail.visibility_scope))

        existing = await share_repo.get_active_grant(
            session,
            resource_type=_RESOURCE_TYPE,
            resource_id=entity_id,
            grantee_principal_id=grantee_principal_id,
        )
        if existing is not None:
            # Already shared with this grantee — return current state, no mutation
            # (idempotent across a differently-keyed retry).
            count = await share_repo.count_active_grants(
                session, resource_type=_RESOURCE_TYPE, resource_id=entity_id
            )
            return _share_result(entity_id, existing.share_id, grantee, detail, root, count)

        grant = share_repo.create_share(
            session,
            resource_type=_RESOURCE_TYPE,
            resource_id=entity_id,
            grantee_principal_id=grantee_principal_id,
            granted_by_principal_id=actor.principal_id,
        )
        previous_visibility = str(detail.visibility_scope)
        if detail.visibility_scope == VisibilityScope.PRIVATE:
            detail.visibility_scope = VisibilityScope.EXPLICITLY_SHARED
        root.row_version += 1
        await session.flush()
        count = await share_repo.count_active_grants(
            session, resource_type=_RESOURCE_TYPE, resource_id=entity_id
        )
        _audit_and_outbox(
            session,
            actor,
            event_kind="package.shared",
            entity_id=entity_id,
            action="shared",
            grantee_principal_id=grantee_principal_id,
            previous_visibility=previous_visibility,
            new_visibility=str(detail.visibility_scope),
        )
        return _share_result(entity_id, grant.share_id, grantee, detail, root, count)

    return await run_idempotent(
        session,
        key=idempotency_key,
        actor_principal_id=actor.principal_id,
        request_payload={
            "op": "share_package",
            "entity_id": entity_id,
            "grantee_principal_id": grantee_principal_id,
        },
        operation=_op,
    )


async def revoke_package_share(
    session: AsyncSession,
    actor: Actor,
    *,
    entity_id: str,
    share_id: str,
    expected_row_version: int | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Revoke one explicit share grant (owner/Admin only).

    When the last active grant is revoked, an EXPLICITLY_SHARED head returns to
    PRIVATE. A grant id that does not belong to this package -> SHARE_GRANT_NOT_FOUND
    (leaks no cross-resource metadata). An already-revoked grant is a no-op that
    returns the current state. Emits ``package.share_revoked`` audit + outbox.
    """
    identity_policy.require_authenticated(actor)

    async def _op() -> dict[str, Any]:
        root, detail = await _require_package(session, entity_id)
        ensure_can_manage_shares(actor, owner_principal_id=root.owner_principal_id)
        check_row_version(root.row_version, expected_row_version)

        grant = await share_repo.get_share(session, share_id)
        if grant is None or grant.resource_type != _RESOURCE_TYPE or grant.resource_id != entity_id:
            raise ShareGrantNotFoundError()
        if grant.revoked_at is not None:
            count = await share_repo.count_active_grants(
                session, resource_type=_RESOURCE_TYPE, resource_id=entity_id
            )
            return _revoke_result(entity_id, share_id, detail, root, count)

        share_repo.revoke_share(
            grant, revoked_by_principal_id=actor.principal_id, now=datetime.now(UTC)
        )
        await session.flush()
        count = await share_repo.count_active_grants(
            session, resource_type=_RESOURCE_TYPE, resource_id=entity_id
        )
        previous_visibility = str(detail.visibility_scope)
        if count == 0 and detail.visibility_scope == VisibilityScope.EXPLICITLY_SHARED:
            detail.visibility_scope = VisibilityScope.PRIVATE
        root.row_version += 1
        _audit_and_outbox(
            session,
            actor,
            event_kind="package.share_revoked",
            entity_id=entity_id,
            action="share_revoked",
            grantee_principal_id=grant.grantee_principal_id,
            previous_visibility=previous_visibility,
            new_visibility=str(detail.visibility_scope),
        )
        return _revoke_result(entity_id, share_id, detail, root, count)

    return await run_idempotent(
        session,
        key=idempotency_key,
        actor_principal_id=actor.principal_id,
        request_payload={
            "op": "revoke_package_share",
            "entity_id": entity_id,
            "share_id": share_id,
        },
        operation=_op,
    )


def _share_result(
    entity_id: str,
    share_id: str,
    grantee: Any,
    detail: PackageRoot,
    root: EntityRegistry,
    active_share_count: int,
) -> dict[str, Any]:
    return {
        "entity_id": entity_id,
        "share_id": share_id,
        "grantee_principal_id": grantee.user_id,
        "grantee_email": grantee.email,
        "grantee_display_name": grantee.display_name,
        "visibility_scope": str(detail.visibility_scope),
        "active_share_count": active_share_count,
        "row_version": root.row_version,
    }


def _revoke_result(
    entity_id: str,
    share_id: str,
    detail: PackageRoot,
    root: EntityRegistry,
    active_share_count: int,
) -> dict[str, Any]:
    return {
        "entity_id": entity_id,
        "share_id": share_id,
        "revoked": True,
        "visibility_scope": str(detail.visibility_scope),
        "active_share_count": active_share_count,
        "row_version": root.row_version,
    }


__all__ = ["revoke_package_share", "share_package"]
