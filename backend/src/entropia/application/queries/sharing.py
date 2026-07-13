"""Explicit package-sharing read surface (GAP-17; Master Reference §6, §6.4).

``list_package_shares`` returns the ACTIVE grantees of one package — WHO it is
shared with — plus the package ``row_version`` the client carries as the OCC
token for a subsequent revoke. Listing the grantees is itself a management
action: only the owner or an Admin may see it (a grantee never learns who else a
resource is shared with), so a non-owner gets SHARE_MANAGEMENT_FORBIDDEN. A
missing/soft-deleted package is a metadata-free 404.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from entropia.domain.identity import Actor
from entropia.domain.identity import policy as identity_policy
from entropia.domain.lifecycle.enums import DeletionState
from entropia.domain.sharing import ShareResourceType, ensure_can_manage_shares
from entropia.infrastructure.postgres.repositories import identity as identity_repo
from entropia.infrastructure.postgres.repositories import packages as pkg_repo
from entropia.infrastructure.postgres.repositories import resource_share as share_repo
from entropia.shared.errors import NotFoundError

_RESOURCE_TYPE = str(ShareResourceType.PACKAGE)


async def list_package_shares(
    session: AsyncSession, actor: Actor, *, entity_id: str
) -> dict[str, Any]:
    """Return the active share grants of a package (owner/Admin only)."""
    identity_policy.require_authenticated(actor)
    root = await pkg_repo.get_package_root(session, entity_id)
    if root is None or root.deletion_state != DeletionState.ACTIVE:
        raise NotFoundError(f"Package '{entity_id}' not found.")
    detail = await pkg_repo.get_package_detail(session, entity_id)
    if detail is None:
        raise NotFoundError(f"Package '{entity_id}' not found.")
    ensure_can_manage_shares(actor, owner_principal_id=root.owner_principal_id)

    grants = await share_repo.list_active_grants(
        session, resource_type=_RESOURCE_TYPE, resource_id=entity_id
    )
    shares: list[dict[str, Any]] = []
    for grant in grants:
        grantee = await identity_repo.get_human_user(session, grant.grantee_principal_id)
        shares.append(
            {
                "share_id": grant.share_id,
                "grantee_principal_id": grant.grantee_principal_id,
                "grantee_email": grantee.email if grantee is not None else None,
                "grantee_display_name": grantee.display_name if grantee is not None else None,
                "granted_by_principal_id": grant.granted_by_principal_id,
                "created_at": grant.created_at.isoformat() if grant.created_at else None,
            }
        )
    return {
        "entity_id": entity_id,
        "visibility_scope": str(detail.visibility_scope),
        "row_version": root.row_version,
        "shares": shares,
    }


__all__ = ["list_package_shares"]
