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
the permission projection is only a UX hint (doc 08 §2).

R2a adds the two revision-plane mutations the catalog advertised but never dispatched
(``can_derive`` / ``can_create_revision``):

* **Derive** — any viewer copies an immutable source revision into a NEW root owned by
  the caller (doc 08 §7 "Derive", §8.2). ``ensure_can_view`` gates it (a non-owner must
  Derive rather than edit); the new root is PRIVATE + PENDING validation + DRAFT approval
  and records ``derived_from_revision_id``. The original root is never mutated. Audit
  ``package.derived``; a fresh ``Idempotency-Key`` guards double-creation.
* **Create Revision** — an owner/Admin appends an immutable revision N+1 to their own
  active root (doc 08 §7 "Create Revision", §11.1). The ``expected_head_revision_id`` OCC
  guards a concurrent head move -> 409 ``PACKAGE_REVISION_CONFLICT`` (doc 08 §8.5); no old
  revision is mutated. Audit ``package.revision_drafted``.

Later epic slices add Request Approval / Approve & Publish / Export onto this module.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from entropia.application.commands.deletion import soft_delete_registry_root
from entropia.application.idempotency import run_idempotent
from entropia.domain.identity import Actor
from entropia.domain.identity.policy import (
    ensure_can_edit,
    ensure_can_view,
    require_authenticated,
)
from entropia.domain.lifecycle.enums import ApprovalState, DeletionState, VisibilityScope
from entropia.domain.package.enums import PackageValidationState
from entropia.infrastructure.postgres.models import EntityRegistry
from entropia.infrastructure.postgres.repositories import audit as audit_repo
from entropia.infrastructure.postgres.repositories import packages as pkg_repo
from entropia.infrastructure.postgres.repositories import resource_share as share_repo
from entropia.shared.errors import (
    LifecycleBlocked,
    PackageDeriveInvalid,
    PackageNotFound,
    PackageRevisionConflict,
)

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


async def derive_package(
    session: AsyncSession,
    actor: Actor,
    *,
    entity_id: str,
    source_revision_id: str,
    name: str,
    change_note: str | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Any viewer: copy an immutable source revision into a NEW root owned by the
    caller (doc 08 §7 "Derive", §8.2, §11.1 "Derive").

    ``ensure_can_view`` (owner / public / resolved share) gates the source — a
    non-owner Derives rather than edits (doc 08 §8.2). The new root starts PRIVATE,
    PENDING validation and DRAFT approval, owned by the caller, and records the exact
    ``derived_from_revision_id`` for provenance; the original root and every strategy
    that already pins it are untouched. A fresh ``Idempotency-Key`` guards
    double-creation — a completed-key replay returns the same new root id. A blank
    name -> 422 ``PACKAGE_DERIVE_INVALID``; a source revision that is not a revision
    of this root -> 404.
    """
    require_authenticated(actor)
    new_name = (name or "").strip()
    if not new_name:
        raise PackageDeriveInvalid()

    root = await _require_package_root(session, entity_id)
    detail = await pkg_repo.get_package_detail(session, entity_id)
    if detail is None or root.deletion_state != DeletionState.ACTIVE:
        raise PackageNotFound()

    grantee_ids = await share_repo.active_grantee_ids(
        session, resource_type=_TARGET_KIND, resource_id=entity_id
    )
    ensure_can_view(
        actor,
        owner_principal_id=root.owner_principal_id,
        visibility=str(detail.visibility_scope),
        shared_principal_ids=grantee_ids,
    )

    source = await pkg_repo.get_revision(session, source_revision_id)
    if source is None or source.entity_id != entity_id:
        raise PackageNotFound()

    async def _op() -> dict[str, Any]:
        input_contract = dict(source.input_contract or {})
        input_contract["name"] = new_name
        family = (
            dict(source.rationale_family_snapshot) if source.rationale_family_snapshot else None
        )
        new_root, _new_detail, revision = await pkg_repo.create_package(
            session,
            owner_principal_id=actor.principal_id,
            created_by_principal_id=actor.principal_id,
            package_kind=source.package_kind,
            input_contract=input_contract,
            output_contract=dict(source.output_contract or {}),
            dependency_snapshot=dict(source.dependency_snapshot or {}),
            visibility_scope=VisibilityScope.PRIVATE,
            rationale_family_snapshot=family,
            validation_state=PackageValidationState.PENDING,
            approval_state=ApprovalState.DRAFT,
            change_note=change_note,
            derived_from_revision_id=source_revision_id,
        )
        _audit_and_outbox(
            session,
            actor,
            event_kind="package.derived",
            entity_id=new_root.entity_id,
            revision_id=revision.revision_id,
            previous_state=source_revision_id,
            new_state=revision.revision_id,
            action="derived",
            reason=change_note,
        )
        return {
            "entity_id": new_root.entity_id,
            "current_revision_id": revision.revision_id,
            "package_kind": str(source.package_kind),
            "name": new_name,
            "derived_from_revision_id": source_revision_id,
            "source_entity_id": entity_id,
        }

    return await run_idempotent(
        session,
        key=idempotency_key,
        actor_principal_id=actor.principal_id,
        request_payload={
            "op": "derive",
            "source_revision_id": source_revision_id,
            "name": new_name,
        },
        operation=_op,
    )


async def create_package_revision(
    session: AsyncSession,
    actor: Actor,
    *,
    entity_id: str,
    expected_head_revision_id: str | None = None,
    change_note: str | None = None,
    input_contract: dict[str, Any] | None = None,
    output_contract: dict[str, Any] | None = None,
    dependency_snapshot: dict[str, Any] | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Owner-or-Admin: append an immutable revision N+1 to an active owned root
    (doc 08 §7 "Create Revision", §11.1 "New revision publish").

    Row-locks the root, then rejects a non-active / soft-deleted package with
    ``LIFECYCLE_BLOCKED``. The ``expected_head_revision_id`` OCC guards a concurrent
    head move -> 409 ``PACKAGE_REVISION_CONFLICT`` (doc 08 §8.5) — never a silent
    overwrite. The new revision copies the exact base revision's contracts (an
    optional ``input``/``output``/``dependency`` override applies a real edit) and
    starts PENDING validation + DRAFT approval, so it must be re-validated before
    approval; the base revision stays immutable. The OCC + append live inside the
    idempotent body so a completed-key replay short-circuits (D3). Audit
    ``package.revision_drafted``.
    """
    root = await _require_package_root(session, entity_id)
    ensure_can_edit(actor, owner_principal_id=root.owner_principal_id)
    await session.refresh(root, with_for_update=True)

    if root.deletion_state != DeletionState.ACTIVE or root.lifecycle_state != _ACTIVE:
        raise LifecycleBlocked()

    async def _op() -> dict[str, Any]:
        if (
            expected_head_revision_id is not None
            and root.current_revision_id != expected_head_revision_id
        ):
            raise PackageRevisionConflict()
        base = await pkg_repo.get_revision(session, root.current_revision_id or "")
        if base is None:
            raise PackageNotFound()

        revision = await pkg_repo.append_package_revision(
            session,
            root,
            package_kind=base.package_kind,
            input_contract=(
                input_contract if input_contract is not None else dict(base.input_contract or {})
            ),
            output_contract=(
                output_contract if output_contract is not None else dict(base.output_contract or {})
            ),
            dependency_snapshot=(
                dependency_snapshot
                if dependency_snapshot is not None
                else dict(base.dependency_snapshot or {})
            ),
            created_by_principal_id=actor.principal_id,
            rationale_family_snapshot=(
                dict(base.rationale_family_snapshot) if base.rationale_family_snapshot else None
            ),
            validation_state=PackageValidationState.PENDING,
            approval_state=ApprovalState.DRAFT,
            change_note=change_note,
            supersedes_revision_id=base.revision_id,
        )
        _audit_and_outbox(
            session,
            actor,
            event_kind="package.revision_drafted",
            entity_id=entity_id,
            revision_id=revision.revision_id,
            previous_state=base.revision_id,
            new_state=revision.revision_id,
            action="revision_drafted",
            reason=change_note,
        )
        return {
            "entity_id": entity_id,
            "revision_id": revision.revision_id,
            "revision_no": revision.revision_no,
            "current_revision_id": root.current_revision_id,
            "base_revision_id": base.revision_id,
        }

    return await run_idempotent(
        session,
        key=idempotency_key,
        actor_principal_id=actor.principal_id,
        request_payload={
            "op": "create_revision",
            "entity_id": entity_id,
            "expected_head_revision_id": expected_head_revision_id,
        },
        operation=_op,
    )


__all__ = [
    "create_package_revision",
    "deprecate_package",
    "derive_package",
    "soft_delete_package",
]
