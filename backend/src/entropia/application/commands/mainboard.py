"""Mainboard composition-plane commands (doc 01 §5, §7, §9; DOMAIN_MODEL §2.2).

Every mutating command runs in ONE transaction supplied by the request dependency
and NEVER commits: it performs the mutation + (where applicable) recomputes and
stores ``workspace.composition_hash`` + writes audit + outbox. The shape per
mutation is: authorization + pure input validation OUTSIDE the idempotent body ->
``run_idempotent`` op { optimistic-concurrency + legality checks INSIDE, BEFORE
any mutation (L2/L7), FOR-UPDATE lock on the root/item via
``session.refresh(..., with_for_update=True)`` } -> repo mutation -> audit +
outbox.

Binding rules (Stage 3 acceptance):

* ``item_kind`` is strictly server-derived from the work object's ``object_kind``;
  a divergent client-supplied kind -> MAINBOARD_ITEM_KIND_MISMATCH (422, CR-01).
* Work objects are pinned by exact ``root_id`` + ``revision_id`` only — never by
  name / "latest" / DOM (L5).
* ``composition_hash`` changes on add / soft-delete / enable-toggle / pin-change
  (prior Ready report STALE); reorder / label-only / expand-collapse do NOT change
  it (doc 01 §5.2, §9.3).
* Trading Signal / Trade Log require a tz-aware UTC ``available_time`` that is not
  in the future (anti-lookahead); Strategy may omit it.
* Revisions are immutable and a revision append NEVER auto-repins any item
  (AT#5) — the only implicit pin is the first one at attach time.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from entropia.application.commands.deletion import soft_delete_entity
from entropia.application.idempotency import run_idempotent
from entropia.domain.identity import Actor
from entropia.domain.identity.policy import (
    ensure_can_edit,
    ensure_can_view,
    require_authenticated,
)
from entropia.domain.lifecycle.enums import DeletionState
from entropia.domain.mainboard.composition import (
    CompositionMember,
    assert_item_kind_matches,
    composition_hash,
)
from entropia.domain.mainboard.enums import MainboardItemKind
from entropia.domain.revision.hashing import content_hash
from entropia.infrastructure.postgres.models import (
    EntityRegistry,
    MainboardWorkingItem,
    MainboardWorkspace,
    WorkObjectRoot,
)
from entropia.infrastructure.postgres.repositories import audit as audit_repo
from entropia.infrastructure.postgres.repositories import mainboard as mb_repo
from entropia.shared.errors import (
    AccessDeniedError,
    MainboardItemKindMismatchError,
    MainboardItemNotFoundError,
    MainboardWorkspaceNotFoundError,
    ObjectNotActiveError,
    RowVersionConflictError,
    ValidationError,
    WorkObjectNotFoundError,
    WorkObjectRevisionConflictError,
)
from entropia.shared.ids import new_id

_EXTERNAL_KINDS = frozenset({MainboardItemKind.TRADING_SIGNAL, MainboardItemKind.TRADE_LOG})

_ITEM_TARGET_TYPE = "mainboard_working_item"
_WORKSPACE_TARGET_TYPE = "mainboard_workspace"
_WORK_OBJECT_TARGET_TYPE = "work_object"

_PIN_REVISION = "pin_revision"
_SET_ENABLED = "set_enabled"
_REORDER = "reorder"
_SET_LABEL = "set_label"
_PATCH_INTENTS = frozenset({_PIN_REVISION, _SET_ENABLED, _REORDER, _SET_LABEL})


# --------------------------------------------------------------------------- #
# Transient draft openers (NO DB) — AT#3: an unsaved draft has no identity.    #
# --------------------------------------------------------------------------- #


def start_strategy_draft(actor: Actor) -> dict[str, Any]:
    """Open a transient Strategy draft. No root/revision/item is created (AT#3)."""
    require_authenticated(actor)
    return {
        "draft_id": new_id("wodraft"),
        "kind": MainboardItemKind.STRATEGY.value,
        "unsaved": True,
    }


def start_external_work_object_draft(actor: Actor, kind: str) -> dict[str, Any]:
    """Open a transient external (Trading Signal / Trade Log) draft (AT#3).

    Only the two external kinds are valid here; a Strategy or unknown kind ->
    MAINBOARD_ITEM_KIND_MISMATCH (422).
    """
    require_authenticated(actor)
    resolved = _coerce_item_kind(kind)
    if resolved not in _EXTERNAL_KINDS:
        raise MainboardItemKindMismatchError(
            f"Kind {resolved.value!r} is not an external work object kind.",
            details=[{"field": "kind", "actual": resolved.value}],
        )
    return {"draft_id": new_id("wodraft"), "kind": resolved.value, "unsaved": True}


# --------------------------------------------------------------------------- #
# Work objects                                                                #
# --------------------------------------------------------------------------- #


async def create_work_object(
    session: AsyncSession,
    actor: Actor,
    *,
    object_kind: str,
    payload: dict[str, Any],
    source_provenance: dict[str, Any] | None = None,
    available_time: datetime | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Create a work object root + immutable revision 1 (doc 01 §7).

    For Trading Signal / Trade Log an ``available_time`` is REQUIRED and must be a
    tz-aware UTC instant that is not in the future (anti-lookahead). Strategy may
    omit it. The FK-safe create + audit/outbox live INSIDE the idempotent body.
    """
    require_authenticated(actor)
    kind = _coerce_item_kind(object_kind)
    _validate_available_time(kind, available_time)

    async def _op() -> dict[str, Any]:
        root, _detail, revision = await mb_repo.create_work_object(
            session,
            owner_principal_id=actor.principal_id,
            created_by_principal_id=actor.principal_id,
            object_kind=kind,
            payload=payload,
            source_provenance=source_provenance,
            available_time=available_time,
        )
        _audit_and_outbox(
            session,
            actor,
            event_kind="mainboard.work_object_created",
            target_type=_WORK_OBJECT_TARGET_TYPE,
            target_entity_id=root.entity_id,
            target_revision_id=revision.revision_id,
            new_state="active",
            payload={"object_kind": kind.value, "revision_id": revision.revision_id},
        )
        return {
            "root_id": root.entity_id,
            "revision_id": revision.revision_id,
            "revision_no": revision.revision_no,
            "object_kind": kind.value,
            "row_version": root.row_version,
        }

    return await run_idempotent(
        session,
        key=idempotency_key,
        actor_principal_id=actor.principal_id,
        request_payload={
            "op": "create_work_object",
            "object_kind": kind.value,
            "content_hash": _payload_hash(kind, payload, available_time),
            "source_provenance": source_provenance,
        },
        operation=_op,
    )


async def create_work_object_revision(
    session: AsyncSession,
    actor: Actor,
    *,
    root_id: str,
    payload: dict[str, Any],
    source_provenance: dict[str, Any] | None = None,
    available_time: datetime | None = None,
    expected_head_revision_id: str | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Append an immutable revision N+1 to a work object (doc 01 §7).

    The root must be an ACTIVE work object the actor may edit. Concurrency (the
    optional ``expected_head_revision_id``) is checked INSIDE the locked body. If
    the new content hash equals the current head's, the append is an idempotent
    no-op (the current head is returned). A revision append NEVER auto-repins any
    Mainboard item (AT#5).
    """
    root, detail = await _require_active_work_object(session, root_id)
    ensure_can_edit(actor, owner_principal_id=root.owner_principal_id)
    kind = detail.object_kind
    _validate_available_time(kind, available_time)

    async def _op() -> dict[str, Any]:
        await session.refresh(root, with_for_update=True)
        if (
            expected_head_revision_id is not None
            and root.current_revision_id != expected_head_revision_id
        ):
            raise WorkObjectRevisionConflictError()

        new_hash = _payload_hash(kind, payload, available_time)
        current = await mb_repo.get_work_object_revision(session, root.current_revision_id or "")
        if current is not None and current.content_hash == new_hash:
            return {
                "root_id": root.entity_id,
                "revision_id": current.revision_id,
                "revision_no": current.revision_no,
                "row_version": root.row_version,
            }

        revision = await mb_repo.append_work_object_revision(
            session,
            root,
            object_kind=kind,
            payload=payload,
            source_provenance=source_provenance,
            available_time=available_time,
            created_by_principal_id=actor.principal_id,
        )
        _audit_and_outbox(
            session,
            actor,
            event_kind="mainboard.work_object_revision_created",
            target_type=_WORK_OBJECT_TARGET_TYPE,
            target_entity_id=root.entity_id,
            target_revision_id=revision.revision_id,
            previous_state=expected_head_revision_id,
            new_state=revision.revision_id,
            payload={"revision_id": revision.revision_id, "revision_no": revision.revision_no},
        )
        return {
            "root_id": root.entity_id,
            "revision_id": revision.revision_id,
            "revision_no": revision.revision_no,
            "row_version": root.row_version,
        }

    return await run_idempotent(
        session,
        key=idempotency_key,
        actor_principal_id=actor.principal_id,
        request_payload={
            "op": "create_work_object_revision",
            "root_id": root_id,
            "expected_head_revision_id": expected_head_revision_id,
            "content_hash": _payload_hash(kind, payload, available_time),
            "source_provenance": source_provenance,
        },
        operation=_op,
    )


# --------------------------------------------------------------------------- #
# Working items                                                               #
# --------------------------------------------------------------------------- #


async def attach_mainboard_item(
    session: AsyncSession,
    actor: Actor,
    *,
    workspace_id: str,
    root_id: str,
    revision_id: str,
    item_kind: str | None = None,
    position_index: int | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Attach a work object onto a workspace as a new working item (doc 01 §5, §7).

    The workspace must be owned by the actor (or Admin). The work object root must
    be ACTIVE and viewable by the actor; the pinned revision must belong to that
    root (no name/latest resolution, L5). The item kind is server-derived from the
    root's ``object_kind`` (CR-01); a divergent client value is rejected. The new
    item is enabled and pins the exact ``root_id`` + ``revision_id``. The
    workspace ``composition_hash`` is recomputed and stored in the same tx.
    """
    workspace = await _require_owned_workspace(session, actor, workspace_id)
    root, detail = await _require_active_work_object(session, root_id)
    # Work objects carry no visibility/share column in Stage 3a, so a foreign work
    # object is private to its owner: only the owner (or Admin) may attach it — a
    # foreign-private root -> AccessDeniedError (403). Never hardcode a permissive
    # share scope. TODO(later): derive published/shared once work-object sharing
    # exists, mirroring queries/market_data.py::_visibility_of.
    ensure_can_view(
        actor,
        owner_principal_id=root.owner_principal_id,
        visibility="private",
    )
    revision = await mb_repo.get_work_object_revision(session, revision_id)
    if revision is None or revision.entity_id != root_id:
        raise ValidationError(
            "The pinned revision does not belong to this work object.",
            details=[{"field": "revision_id", "actual": revision_id}],
        )
    item_kind_value = detail.object_kind
    if item_kind is not None:
        assert_item_kind_matches(_coerce_item_kind(item_kind), item_kind_value)

    async def _op() -> dict[str, Any]:
        position = (
            position_index
            if position_index is not None
            else await mb_repo.next_position_index(session, workspace.entity_id)
        )
        item = await mb_repo.attach_item(
            session,
            workspace_entity_id=workspace.entity_id,
            item_kind=item_kind_value,
            work_object_root_id=root_id,
            pinned_revision_id=revision_id,
            position_index=position,
            created_by_principal_id=actor.principal_id,
        )
        new_hash = await _recompute_composition_hash(session, workspace)
        _audit_and_outbox(
            session,
            actor,
            event_kind="mainboard.item_attached",
            target_type=_ITEM_TARGET_TYPE,
            target_entity_id=item.item_id,
            new_state="enabled",
            payload={
                "workspace_id": workspace.entity_id,
                "work_object_root_id": root_id,
                "pinned_revision_id": revision_id,
                "composition_hash": new_hash,
            },
        )
        _composition_changed(session, actor, workspace.entity_id, new_hash)
        result = _item_projection(item)
        result["composition_hash"] = new_hash
        return result

    return await run_idempotent(
        session,
        key=idempotency_key,
        actor_principal_id=actor.principal_id,
        request_payload={
            "op": "attach_mainboard_item",
            "workspace_id": workspace_id,
            "root_id": root_id,
            "revision_id": revision_id,
        },
        operation=_op,
    )


async def patch_mainboard_item(
    session: AsyncSession,
    actor: Actor,
    *,
    item_id: str,
    intent: str,
    expected_row_version: int,
    revision_id: str | None = None,
    is_enabled: bool | None = None,
    position_index: int | None = None,
    display_label_override: str | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Apply exactly one intent to a working item (doc 01 §5.2, §9.3-9.4).

    Intents: ``pin_revision`` / ``set_enabled`` / ``reorder`` / ``set_label``.
    The item's workspace must be editable by the actor. Inside the locked body the
    item's ``row_version`` is compared to ``expected_row_version`` (stale ->
    ROW_VERSION_CONFLICT). ``pin_revision`` and ``set_enabled`` change the
    composition fingerprint (recompute + store + composition_changed audit);
    ``reorder`` and ``set_label`` do NOT. Every intent bumps ``item.row_version``.
    """
    if intent not in _PATCH_INTENTS:
        raise ValidationError(
            f"Unknown patch intent {intent!r}.", details=[{"field": "intent", "actual": intent}]
        )
    item = await _require_item(session, item_id)
    workspace = await _require_owned_workspace(session, actor, item.workspace_entity_id)

    async def _op() -> dict[str, Any]:
        await session.refresh(item, with_for_update=True)
        if item.row_version != expected_row_version:
            raise RowVersionConflictError()

        hash_changing = await _apply_intent(
            session,
            actor,
            item,
            intent=intent,
            revision_id=revision_id,
            is_enabled=is_enabled,
            position_index=position_index,
            display_label_override=display_label_override,
        )
        item.row_version += 1

        new_hash: str | None = workspace.composition_hash
        if hash_changing:
            new_hash = await _recompute_composition_hash(session, workspace)
            _composition_changed(session, actor, workspace.entity_id, new_hash)
        result = _item_projection(item)
        result["composition_hash"] = new_hash
        return result

    return await run_idempotent(
        session,
        key=idempotency_key,
        actor_principal_id=actor.principal_id,
        request_payload={
            "op": "patch_mainboard_item",
            "item_id": item_id,
            "intent": intent,
            "expected_row_version": expected_row_version,
            "revision_id": revision_id,
            "is_enabled": is_enabled,
            "position_index": position_index,
            "display_label_override": display_label_override,
        },
        operation=_op,
    )


# --------------------------------------------------------------------------- #
# Snapshot                                                                    #
# --------------------------------------------------------------------------- #


async def create_composition_snapshot(
    session: AsyncSession,
    actor: Actor,
    *,
    workspace_id: str,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Freeze the workspace's current ENABLED composition as an immutable snapshot.

    Gathers the current enabled persisted items whose root is ACTIVE (sorted by
    ``position_index``), computes the composition hash, and writes an immutable
    snapshot with ``readiness_state="unevaluated"`` / ``readiness_report_id=null``
    (Stage 4 consumes it; no Ready Check here, doc 01 §9.2).
    """
    workspace = await _require_owned_workspace(session, actor, workspace_id)

    async def _op() -> dict[str, Any]:
        items = await mb_repo.list_active_items(session, workspace.entity_id)
        enabled = [item for item in items if item.is_enabled]
        comp_hash = composition_hash(_members(enabled))
        snapshot_id_holder: dict[str, str] = {}
        manifest = _snapshot_manifest(
            actor,
            workspace_id=workspace.entity_id,
            composition_hash=comp_hash,
            items=enabled,
            snapshot_id_holder=snapshot_id_holder,
        )
        snapshot = await mb_repo.create_snapshot(
            session,
            workspace_entity_id=workspace.entity_id,
            composition_hash=comp_hash,
            item_manifest=manifest,
            created_by_principal_id=actor.principal_id,
        )
        # The manifest references its own snapshot id; backfill it now that the row
        # exists (the JSONB column is set from the same dict object).
        manifest["snapshot_id"] = snapshot.snapshot_id
        _audit_and_outbox(
            session,
            actor,
            event_kind="mainboard.snapshot_created",
            target_type=_WORKSPACE_TARGET_TYPE,
            target_entity_id=workspace.entity_id,
            # new_state holds the snapshot id (<=48); the 64-char composition_hash
            # rides in the outbox payload below (new_state is VARCHAR(48)).
            new_state=snapshot.snapshot_id,
            payload={
                "snapshot_id": snapshot.snapshot_id,
                "composition_hash": comp_hash,
                "item_count": len(enabled),
            },
        )
        return {
            "snapshot_id": snapshot.snapshot_id,
            "composition_hash": comp_hash,
            "item_count": len(enabled),
        }

    return await run_idempotent(
        session,
        key=idempotency_key,
        actor_principal_id=actor.principal_id,
        request_payload={"op": "create_composition_snapshot", "workspace_id": workspace_id},
        operation=_op,
    )


# --------------------------------------------------------------------------- #
# Soft delete                                                                 #
# --------------------------------------------------------------------------- #


async def soft_delete_work_object(
    session: AsyncSession,
    actor: Actor,
    *,
    root_id: str,
    reason: str | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Soft-delete a work object root, then refresh affected workspace fingerprints.

    Authorization (owner/Admin) is enforced before any mutation. A preflight
    extension point (``_assert_not_in_active_run``) is a no-op stub in 3a. The
    generic ``soft_delete_entity`` command is delegated to (root state + trash +
    audit + outbox; an already-deleted root is an idempotent no-op). After
    deletion, every workspace that held an item on this root has its
    ``composition_hash`` recomputed (the items remain but drop out of the active
    projection because the root is now soft-deleted).
    """
    root = await mb_repo.get_work_object_root(session, root_id)
    if root is None:
        raise WorkObjectNotFoundError(f"Work object '{root_id}' not found.")
    ensure_can_edit(actor, owner_principal_id=root.owner_principal_id)

    async def _op() -> dict[str, Any]:
        # Lock the registry root FOR UPDATE so concurrent deletes serialize, then
        # short-circuit an already-deleted root as an idempotent no-op (doc 01
        # §8.5; ENTITY_ALREADY_DELETED semantics) instead of raising a 409.
        await session.refresh(root, with_for_update=True)
        if root.deletion_state != DeletionState.ACTIVE:
            return {"root_id": root_id, "deletion_state": str(root.deletion_state)}
        await _assert_not_in_active_run(session, root_id)
        affected = await mb_repo.list_items_for_root(session, root_id)
        workspace_ids = {item.workspace_entity_id for item in affected}

        await soft_delete_entity(session, actor, entity_id=root_id, reason=reason)
        await session.flush()

        for workspace_id in sorted(workspace_ids):
            workspace = await mb_repo.get_workspace_detail(session, workspace_id)
            if workspace is None:
                continue
            new_hash = await _recompute_composition_hash(session, workspace)
            _composition_changed(session, actor, workspace_id, new_hash)
        return {"root_id": root_id, "deletion_state": str(DeletionState.SOFT_DELETED)}

    return await run_idempotent(
        session,
        key=idempotency_key,
        actor_principal_id=actor.principal_id,
        request_payload={"op": "soft_delete_work_object", "root_id": root_id},
        operation=_op,
    )


async def _assert_not_in_active_run(session: AsyncSession, root_id: str) -> None:
    """Block soft-delete when a QUEUED/PROVISIONING/RUNNING backtest run pins this
    root (Stage 5a wiring of OBJECT_IN_ACTIVE_RUN, doc 15 §12). Immutable historical
    manifests keep their pins unchanged; only ACTIVE runs guard deletion. Imported
    locally to keep the mainboard command free of a backtest import at module load.
    """
    from entropia.infrastructure.postgres.repositories import backtest as bt_repo
    from entropia.shared.errors import ObjectInActiveRunError

    if await bt_repo.has_active_run_for_root(session, root_id):
        raise ObjectInActiveRunError()


# --------------------------------------------------------------------------- #
# Intent application                                                          #
# --------------------------------------------------------------------------- #


async def _apply_intent(
    session: AsyncSession,
    actor: Actor,
    item: MainboardWorkingItem,
    *,
    intent: str,
    revision_id: str | None,
    is_enabled: bool | None,
    position_index: int | None,
    display_label_override: str | None,
) -> bool:
    """Apply one intent to ``item`` in place. Returns True iff the composition
    fingerprint changed (pin / enable), False for presentation-only (reorder /
    label). Audit is written here per-intent."""
    handlers: dict[str, Callable[[], Awaitable[bool]]] = {
        _PIN_REVISION: lambda: _apply_pin(session, actor, item, revision_id),
        _SET_ENABLED: lambda: _apply_enabled(session, actor, item, is_enabled),
        _REORDER: lambda: _apply_reorder(session, actor, item, position_index),
        _SET_LABEL: lambda: _apply_label(session, actor, item, display_label_override),
    }
    return await handlers[intent]()


async def _apply_pin(
    session: AsyncSession,
    actor: Actor,
    item: MainboardWorkingItem,
    revision_id: str | None,
) -> bool:
    if revision_id is None:
        raise ValidationError(
            "pin_revision requires a revision_id.", details=[{"field": "revision_id"}]
        )
    # Lock the work-object root FOR UPDATE before the active check so a concurrent
    # soft_delete_work_object (which locks the same root) cannot commit between the
    # active check and the pin write (L7 TOCTOU close).
    root = await mb_repo.get_work_object_root(session, item.work_object_root_id)
    if root is None:
        raise WorkObjectNotFoundError(f"Work object '{item.work_object_root_id}' not found.")
    await session.refresh(root, with_for_update=True)
    if root.deletion_state != DeletionState.ACTIVE:
        raise ObjectNotActiveError(f"Work object '{item.work_object_root_id}' is not active.")
    revision = await mb_repo.get_work_object_revision(session, revision_id)
    if revision is None or revision.entity_id != item.work_object_root_id:
        raise ValidationError(
            "The pinned revision does not belong to this work object.",
            details=[{"field": "revision_id", "actual": revision_id}],
        )
    previous_revision = item.pinned_revision_id
    item.pinned_revision_id = revision_id
    audit_repo.add_audit_event(
        session,
        event_kind="mainboard.item_revision_pinned",
        actor_principal_id=actor.principal_id,
        actor_kind=actor.actor_kind,
        target_entity_id=item.item_id,
        target_entity_type=_ITEM_TARGET_TYPE,
        target_revision_id=revision_id,
        previous_state=previous_revision,
        new_state=revision_id,
        correlation_id=actor.correlation_id,
    )
    return True


async def _apply_enabled(
    session: AsyncSession,
    actor: Actor,
    item: MainboardWorkingItem,
    is_enabled: bool | None,
) -> bool:
    if is_enabled is None:
        raise ValidationError("set_enabled requires is_enabled.", details=[{"field": "is_enabled"}])
    previous = item.is_enabled
    item.is_enabled = is_enabled
    audit_repo.add_audit_event(
        session,
        event_kind="mainboard.item_enabled_changed",
        actor_principal_id=actor.principal_id,
        actor_kind=actor.actor_kind,
        target_entity_id=item.item_id,
        target_entity_type=_ITEM_TARGET_TYPE,
        previous_state=str(previous),
        new_state=str(is_enabled),
        correlation_id=actor.correlation_id,
    )
    return True


async def _apply_reorder(
    session: AsyncSession,
    actor: Actor,
    item: MainboardWorkingItem,
    position_index: int | None,
) -> bool:
    if position_index is None:
        raise ValidationError(
            "reorder requires a position_index.", details=[{"field": "position_index"}]
        )
    previous = item.position_index
    item.position_index = position_index
    audit_repo.add_audit_event(
        session,
        event_kind="mainboard.item_reordered",
        actor_principal_id=actor.principal_id,
        actor_kind=actor.actor_kind,
        target_entity_id=item.item_id,
        target_entity_type=_ITEM_TARGET_TYPE,
        previous_state=str(previous),
        new_state=str(position_index),
        correlation_id=actor.correlation_id,
    )
    return False


async def _apply_label(
    session: AsyncSession,
    actor: Actor,
    item: MainboardWorkingItem,
    display_label_override: str | None,
) -> bool:
    item.display_label_override = display_label_override
    return False


# --------------------------------------------------------------------------- #
# Shared helpers                                                              #
# --------------------------------------------------------------------------- #


def _coerce_item_kind(value: str) -> MainboardItemKind:
    try:
        return MainboardItemKind(value)
    except ValueError as exc:
        raise MainboardItemKindMismatchError(
            f"Unknown work object kind {value!r}.",
            details=[{"field": "object_kind", "actual": value}],
        ) from exc


def _validate_available_time(kind: MainboardItemKind, available_time: datetime | None) -> None:
    """Anti-lookahead rule for external kinds (doc 01).

    Trading Signal / Trade Log require a tz-aware UTC ``available_time`` that is not
    in the future; Strategy may omit it.
    """
    if kind not in _EXTERNAL_KINDS:
        return
    if available_time is None:
        raise ValidationError(
            f"available_time is required for {kind.value}.",
            details=[{"field": "available_time"}],
        )
    if available_time.tzinfo is None or available_time.utcoffset() is None:
        raise ValidationError(
            "available_time must be a timezone-aware UTC instant.",
            details=[{"field": "available_time"}],
        )
    if available_time.astimezone(UTC) > datetime.now(UTC):
        raise ValidationError(
            "available_time cannot be in the future (anti-lookahead).",
            details=[{"field": "available_time"}],
        )


def _payload_hash(
    kind: MainboardItemKind, payload: dict[str, Any], available_time: datetime | None
) -> str:
    return content_hash(
        {
            "object_kind": kind.value,
            "payload": payload,
            "available_time": available_time.isoformat() if available_time is not None else None,
        }
    )


def _members(items: Sequence[MainboardWorkingItem]) -> list[CompositionMember]:
    return [
        CompositionMember(
            kind=item.item_kind,
            root_id=item.work_object_root_id,
            revision_id=item.pinned_revision_id,
        )
        for item in items
    ]


async def _recompute_composition_hash(session: AsyncSession, workspace: MainboardWorkspace) -> str:
    """Recompute the ENABLED+ACTIVE composition hash and store it on the workspace.

    The workspace row is locked ``FOR UPDATE`` before the read-compute-write so
    concurrent composition mutations on the same workspace serialize (no lost
    update on the cached fingerprint), and ``row_version`` is bumped so the
    ``GET /mainboards/default`` ETag advances on every composition change.
    """
    await session.refresh(workspace, with_for_update=True)
    items = await mb_repo.list_active_items(session, workspace.entity_id)
    enabled = [item for item in items if item.is_enabled]
    new_hash = composition_hash(_members(enabled))
    workspace.composition_hash = new_hash
    workspace.row_version += 1
    return new_hash


def _composition_changed(
    session: AsyncSession, actor: Actor, workspace_id: str, composition_hash_value: str
) -> None:
    audit_repo.add_audit_event(
        session,
        event_kind="mainboard.composition_changed",
        actor_principal_id=actor.principal_id,
        actor_kind=actor.actor_kind,
        target_entity_id=workspace_id,
        target_entity_type=_WORKSPACE_TARGET_TYPE,
        # The 64-char composition_hash exceeds new_state's VARCHAR(48); carry it in
        # the JSONB metadata (and outbox payload below) instead — Postgres enforces
        # the column length even though local SQLite does not.
        metadata={"composition_hash": composition_hash_value},
        correlation_id=actor.correlation_id,
    )
    audit_repo.add_outbox_event(
        session,
        event_type="mainboard.composition_changed",
        resource_type=_WORKSPACE_TARGET_TYPE,
        resource_id=workspace_id,
        payload={"composition_hash": composition_hash_value},
        correlation_id=actor.correlation_id,
    )


def _audit_and_outbox(
    session: AsyncSession,
    actor: Actor,
    *,
    event_kind: str,
    target_type: str,
    target_entity_id: str,
    target_revision_id: str | None = None,
    previous_state: str | None = None,
    new_state: str | None = None,
    payload: dict[str, Any],
) -> None:
    audit_repo.add_audit_event(
        session,
        event_kind=event_kind,
        actor_principal_id=actor.principal_id,
        actor_kind=actor.actor_kind,
        target_entity_id=target_entity_id,
        target_entity_type=target_type,
        target_revision_id=target_revision_id,
        previous_state=previous_state,
        new_state=new_state,
        correlation_id=actor.correlation_id,
    )
    audit_repo.add_outbox_event(
        session,
        event_type=event_kind,
        resource_type=target_type,
        resource_id=target_entity_id,
        payload=payload,
        correlation_id=actor.correlation_id,
    )


def _snapshot_manifest(
    actor: Actor,
    *,
    workspace_id: str,
    composition_hash: str,
    items: Sequence[MainboardWorkingItem],
    snapshot_id_holder: dict[str, str],
) -> dict[str, Any]:
    """Build the snapshot item manifest (doc 01 §9.2 shape).

    ``snapshot_id`` is backfilled by the caller once the row id exists.
    """
    return {
        "snapshot_id": snapshot_id_holder.get("snapshot_id"),
        "workspace_id": workspace_id,
        "composition_hash": composition_hash,
        "items": [
            {
                "item_id": item.item_id,
                "kind": str(item.item_kind),
                "root_id": item.work_object_root_id,
                "revision_id": item.pinned_revision_id,
                "enabled": item.is_enabled,
                "position": item.position_index,
            }
            for item in items
        ],
        "equity_allocation_mode": False,
        "created_by_actor_id": actor.principal_id,
        "created_at": datetime.now(UTC).isoformat(),
    }


def _item_projection(item: MainboardWorkingItem) -> dict[str, Any]:
    return {
        "item_id": item.item_id,
        "item_kind": str(item.item_kind),
        "work_object_root_id": item.work_object_root_id,
        "pinned_revision_id": item.pinned_revision_id,
        "position_index": item.position_index,
        "is_enabled": item.is_enabled,
        "display_label_override": item.display_label_override,
        "row_version": item.row_version,
    }


async def _require_active_work_object(
    session: AsyncSession, root_id: str
) -> tuple[EntityRegistry, WorkObjectRoot]:
    root = await mb_repo.get_work_object_root(session, root_id)
    if root is None:
        raise WorkObjectNotFoundError(f"Work object '{root_id}' not found.")
    if root.deletion_state != DeletionState.ACTIVE:
        raise ObjectNotActiveError(f"Work object '{root_id}' is not active.")
    detail = await mb_repo.get_work_object_detail(session, root_id)
    if detail is None:
        raise WorkObjectNotFoundError(f"Work object '{root_id}' not found.")
    return root, detail


async def _require_owned_workspace(
    session: AsyncSession, actor: Actor, workspace_id: str
) -> MainboardWorkspace:
    require_authenticated(actor)
    root = await mb_repo.get_workspace(session, workspace_id)
    if root is None or root.deletion_state != DeletionState.ACTIVE:
        raise MainboardWorkspaceNotFoundError(f"Mainboard workspace '{workspace_id}' not found.")
    if not (actor.is_admin or root.owner_principal_id == actor.principal_id):
        raise AccessDeniedError("You can only modify your own Mainboard.")
    detail = await mb_repo.get_workspace_detail(session, workspace_id)
    if detail is None:
        raise MainboardWorkspaceNotFoundError(f"Mainboard workspace '{workspace_id}' not found.")
    return detail


async def _require_item(session: AsyncSession, item_id: str) -> MainboardWorkingItem:
    item = await mb_repo.get_item(session, item_id)
    if item is None:
        raise MainboardItemNotFoundError(f"Mainboard item '{item_id}' not found.")
    return item


__all__ = [
    "attach_mainboard_item",
    "create_composition_snapshot",
    "create_work_object",
    "create_work_object_revision",
    "patch_mainboard_item",
    "soft_delete_work_object",
    "start_external_work_object_draft",
    "start_strategy_draft",
]
