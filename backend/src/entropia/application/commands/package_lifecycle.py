"""Package Library lifecycle commands (doc 08 §7, §11 — GAP-06 epic, slice 1).

The first slice of the GAP-06 "library actions" epic wires the two lowest-risk
root-lifecycle mutations the catalog already advertises via ``PackagePermissions``
but never dispatched (doc 08 §4.3 "absent actions are explained by permission /
lifecycle, not merely hidden"):

* **Deprecate** — an owner/Admin flips an ``active`` package root to ``deprecated``
  (doc 08 §7 "Deprecate"): history is kept, pinned references keep resolving, only
  NEW use is disabled (``can_use`` already gates on an active head). No new revision.
* **Move to Trash** — an owner/Admin soft-deletes the root through the shared
  Trash-core path (doc 08 §7 "Move to Trash", §8.4). Restore stays the Admin-only
  Trash surface (already landed); ``package`` is already a registered Trash object
  type, so the existing generic registry restore reactivates it with no change here.

Both reuse the established registry patterns — owner-or-Admin ``ensure_can_edit``,
optional ``row_version`` OCC, the ``package.*`` audit family + a ``resource.changed``
outbox — mirroring ``commands/market_data.py``. The server RE-VALIDATES every guard;
the permission projection is only a UX hint (doc 08 §2). Later epic slices add
Create Revision / Derive / Request Validation / Request Approval / Approve & Publish
/ Export onto this module.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from entropia.application.commands.deletion import soft_delete_registry_root
from entropia.domain.identity import Actor
from entropia.domain.identity.policy import ensure_can_edit
from entropia.domain.lifecycle.enums import DeletionState
from entropia.infrastructure.postgres.models import EntityRegistry
from entropia.infrastructure.postgres.repositories import audit as audit_repo
from entropia.infrastructure.postgres.repositories import packages as pkg_repo
from entropia.shared.errors import LifecycleBlocked, PackageNotFound

_TARGET_KIND = pkg_repo.ENTITY_TYPE
_ACTIVE = "active"
_DEPRECATED = "deprecated"


def _audit_and_outbox(
    session: AsyncSession,
    actor: Actor,
    *,
    event_kind: str,
    entity_id: str,
    revision_id: str | None,
    previous_state: str | None,
    new_state: str | None,
    action: str,
    reason: str | None = None,
) -> None:
    """One domain audit row + a ``resource.changed`` outbox fan-out (SSE sweeps the
    ``["library"]`` cache) — the ``package.*`` family so the delete/deprecate lands
    in the Logs family filter beside the package's other events (doc 08 §11.2)."""
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
        reason=reason,
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


async def _require_package_root(session: AsyncSession, entity_id: str) -> EntityRegistry:
    """Load the package root by id (any deletion state — a repeat soft delete stays
    an idempotent no-op via the Trash core); a missing / non-package id -> 404 that
    leaks no metadata (doc 08 §9.2)."""
    root = await pkg_repo.get_package_root(session, entity_id)
    if root is None:
        raise PackageNotFound()
    return root


async def _package_display_name(session: AsyncSession, root: EntityRegistry) -> str | None:
    """The package name from the head revision's input contract (doc 08 §4.2) — the
    Trash-entry display identity, exactly the field the catalog row surfaces."""
    if not root.current_revision_id:
        return None
    revision = await pkg_repo.get_revision(session, root.current_revision_id)
    if revision is None:
        return None
    contract = revision.input_contract if isinstance(revision.input_contract, dict) else {}
    name = contract.get("name")
    return name if isinstance(name, str) else None


async def deprecate_package(
    session: AsyncSession,
    actor: Actor,
    *,
    entity_id: str,
    note: str | None = None,
) -> dict[str, Any]:
    """Owner-or-Admin: flip an ACTIVE package root ``active -> deprecated`` (doc 08
    §7 "Deprecate").

    Row-locks the root, then rejects a non-active or already soft-deleted package
    with ``LIFECYCLE_BLOCKED`` (409) rather than silently no-opping — the catalog
    disables the button once ``can_deprecate`` turns false. History and pinned
    references are untouched (no revision mutation); only new ``Use`` is blocked
    because ``can_use`` requires an active head. Audit ``package.deprecated``.
    """
    root = await _require_package_root(session, entity_id)
    ensure_can_edit(actor, owner_principal_id=root.owner_principal_id)
    await session.refresh(root, with_for_update=True)

    if root.deletion_state != DeletionState.ACTIVE or root.lifecycle_state != _ACTIVE:
        raise LifecycleBlocked()

    previous = root.lifecycle_state
    root.lifecycle_state = _DEPRECATED
    _audit_and_outbox(
        session,
        actor,
        event_kind="package.deprecated",
        entity_id=entity_id,
        revision_id=root.current_revision_id,
        previous_state=previous,
        new_state=_DEPRECATED,
        action="deprecated",
        reason=note,
    )
    return {"entity_id": entity_id, "lifecycle_state": root.lifecycle_state}


async def soft_delete_package(
    session: AsyncSession,
    actor: Actor,
    *,
    entity_id: str,
    reason: str | None = None,
    expected_row_version: int | None = None,
) -> dict[str, Any]:
    """Owner-or-Admin soft delete of a package root (doc 08 §7 "Move to Trash", §8.4).

    Reuses the shared Trash-core (``soft_delete_registry_root``): row-lock + optional
    ``row_version`` OCC (a stale head -> 409) + Trash entry write; on a real
    ``active -> soft_deleted`` transition this emits the ``package.soft_deleted``
    audit (the core stays audit-silent so each domain keeps its own event family).
    Historical revision/manifest provenance and any run-pinned references survive;
    a repeat delete is an idempotent no-op. Restore is the Admin-only Trash surface
    (``package`` is already a registered Trash object type — no change needed here).
    """
    root = await _require_package_root(session, entity_id)
    ensure_can_edit(actor, owner_principal_id=root.owner_principal_id)
    display_name = await _package_display_name(session, root)

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
            event_kind="package.soft_deleted",
            entity_id=entity_id,
            revision_id=root.current_revision_id,
            previous_state=previous,
            new_state=new_state,
            action="soft_deleted",
            reason=reason,
        )
    return {
        "entity_id": entity_id,
        "deletion_state": str(root.deletion_state),
        "display_name": display_name,
    }


__all__ = [
    "deprecate_package",
    "soft_delete_package",
]
