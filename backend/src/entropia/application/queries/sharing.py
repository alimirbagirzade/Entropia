"""Explicit package-sharing read surface (GAP-17; Master Reference §6, §6.4).

``list_package_shares`` returns the ACTIVE grantees of one package — WHO it is
shared with — plus the package ``row_version`` the client carries as the OCC
token for a subsequent revoke. Listing the grantees is itself a management
action: only the owner or an Admin may see it (a grantee never learns who else a
resource is shared with), so a non-owner gets SHARE_MANAGEMENT_FORBIDDEN. A
missing/soft-deleted package is a metadata-free 404.

The listing is cursor-paginated over ``share_id`` (finding O-24). The grant list
has no per-package cap, so an unpaged read let one package decide how much work
the endpoint did; ``meta.has_more`` keeps a truncated page honest instead of
silently dropping the tail.
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
from entropia.shared.pagination import MAX_LIMIT, PageParams

_RESOURCE_TYPE = str(ShareResourceType.PACKAGE)

# This surface's page size when the caller names none. Deliberately MAX_LIMIT and
# not ``pagination.DEFAULT_LIMIT`` (20), the way ``rationale``/``result_artifacts``
# also pick a per-surface default: the share panel renders one flat list with no
# "next page" control, so a default of 20 would hide grantees 21..100 from a UI
# that cannot ask for them. 100 still kills the unbounded scan, and anything past
# it is reported through ``meta.has_more`` rather than silently dropped.
DEFAULT_SHARE_PAGE_LIMIT = MAX_LIMIT


async def list_package_shares(
    session: AsyncSession, actor: Actor, *, entity_id: str, params: PageParams | None = None
) -> dict[str, Any]:
    """Return one page of a package's active share grants (owner/Admin only)."""
    identity_policy.require_authenticated(actor)
    root = await pkg_repo.get_package_root(session, entity_id)
    if root is None or root.deletion_state != DeletionState.ACTIVE:
        raise NotFoundError(f"Package '{entity_id}' not found.")
    detail = await pkg_repo.get_package_detail(session, entity_id)
    if detail is None:
        raise NotFoundError(f"Package '{entity_id}' not found.")
    ensure_can_manage_shares(actor, owner_principal_id=root.owner_principal_id)

    page = params if params is not None else PageParams(limit=DEFAULT_SHARE_PAGE_LIMIT)
    # +1 row is the has_more probe, exactly as ``esp.list_embedded_system_packages``
    # does it; the probe row is dropped before it reaches the projection.
    window = await share_repo.list_active_grants(
        session,
        resource_type=_RESOURCE_TYPE,
        resource_id=entity_id,
        after_share_id=page.cursor,
        limit=page.limit + 1,
    )
    has_more = len(window) > page.limit
    grants = list(window[: page.limit])
    # ONE batched lookup for every grantee (finding O-24) — a per-grant account
    # read made the round-trip count scale with the share count, and the page bound
    # alone would only have capped that at ``limit`` reads instead of removing it.
    # Same pattern as ``market_data.summarize_coverage_for_revisions``; a grantee
    # whose account row is missing is simply absent from the map and still renders
    # ``None``.
    grantees = await identity_repo.get_human_users(
        session, [grant.grantee_principal_id for grant in grants]
    )
    shares: list[dict[str, Any]] = []
    for grant in grants:
        grantee = grantees.get(grant.grantee_principal_id)
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
        # ``cursor`` is the last returned share_id, so the next page resumes AFTER
        # it; None when this page is the tail (never a cursor that returns nothing).
        "meta": {
            "cursor": grants[-1].share_id if has_more and grants else None,
            "has_more": has_more,
        },
    }


__all__ = ["DEFAULT_SHARE_PAGE_LIMIT", "list_package_shares"]
