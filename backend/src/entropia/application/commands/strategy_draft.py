"""Strategy Details commands (doc 02 §7, §8, §9; DOMAIN_MODEL §2.3).

Every mutating command runs in ONE transaction supplied by the request dependency
and NEVER commits. The shape mirrors the Mainboard commands: authorization + pure
input validation OUTSIDE the idempotent body -> ``run_idempotent`` op {
optimistic-concurrency + legality checks INSIDE, BEFORE any mutation (L2/L7),
FOR-UPDATE lock on the root/draft via ``session.refresh(..., with_for_update=True)``
} -> repo mutation -> audit + outbox.

Binding rules (Stage 3b acceptance):

* A Strategy is a work object (shared registry Root, ``object_kind=strategy``); the
  typed StrategyConfig lives in ``strategy_root`` / ``strategy_revision``.
* **Save != Ready PASS != Run.** A successful Save creates the immutable
  ``strategy_revision`` (typed, ``config_hash``), appends a mirror
  ``work_object_revision``, and re-pins every attached Mainboard item to it via
  3a's ``patch_mainboard_item(pin_revision)`` — so the workspace
  ``composition_hash`` changes and the prior Ready report becomes STALE. Save NEVER
  produces a Ready PASS or a Run.
* Sizing exclusivity + trigger-source-conditional are enforced by the compiler
  (doc 02 §3, §6) and surface as typed 422s.
* ``expected_draft_row_version`` is a live optimistic-concurrency token; a stale
  Save/patch -> STRATEGY_DRAFT_CONFLICT (never last-write-wins).
* References are pinned by exact ``root_id`` + ``revision_id`` + ``content_hash``
  (no "latest", L5).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from entropia.application.commands import mainboard as mb_cmd
from entropia.application.idempotency import run_idempotent
from entropia.application.queries import instrument as instrument_query
from entropia.domain.identity import Actor
from entropia.domain.identity.policy import ensure_can_edit, ensure_can_view, require_authenticated
from entropia.domain.lifecycle.enums import DeletionState, PackageKind
from entropia.domain.mainboard.enums import MainboardItemKind
from entropia.domain.package.permissions import package_permissions
from entropia.domain.strategy.compiler import (
    CODE_ENTRY_DIRECTION_INCOHERENT,
    CODE_ENTRY_REQUIRED_BLOCK_MISSING,
    CODE_SIGNAL_SUPPORTING_REQUIREMENT_UNMET,
    CODE_SIZING_NOT_EXCLUSIVE,
    CODE_TRIGGER_CONDITION_REQUIRED,
    compute_config_hash,
    config_to_dict,
    validate_strategy_config,
)
from entropia.domain.strategy.config import StrategyConfig
from entropia.domain.strategy.enums import (
    DependencyRoleEnum,
    ReferencedEntityTypeEnum,
    StrategyLifecycleStateEnum,
    ValidationStatusEnum,
)
from entropia.infrastructure.postgres.models import EntityRegistry, StrategyRoot
from entropia.infrastructure.postgres.repositories import audit as audit_repo
from entropia.infrastructure.postgres.repositories import mainboard as mb_repo
from entropia.infrastructure.postgres.repositories import packages as pkg_repo
from entropia.infrastructure.postgres.repositories import strategy as strat_repo
from entropia.shared.errors import (
    EntryDirectionIncoherentError,
    EntryRequiredBlockMissingError,
    PackageNotDerivableError,
    PackageNotFound,
    SignalSupportingRequirementUnmetError,
    SizingMethodNotExclusiveError,
    StrategyDraftConflictError,
    StrategyDraftNotAttachedError,
    StrategyDraftNotFoundError,
    StrategyLockedForTestError,
    StrategyReferenceNotActiveError,
    StrategyValidationFailedError,
    TriggerSourceConditionRequiredError,
    ValidationError,
)

_DRAFT_TARGET_TYPE = "strategy_editor_draft"
_STRATEGY_TARGET_TYPE = "strategy"
_MIRROR_KIND = MainboardItemKind.STRATEGY


# --------------------------------------------------------------------------- #
# Create draft                                                                #
# --------------------------------------------------------------------------- #


async def create_strategy_draft(
    session: AsyncSession,
    actor: Actor,
    *,
    display_name: str,
    rationale_family_id: str | None = None,
    initial_payload: dict[str, Any] | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Create a persisted Strategy draft + root (doc 02 §7; AT-01).

    The registry Root is created as a work object (so it can later be attached to a
    Mainboard) with ``object_kind=strategy``; a ``strategy_root`` head pointer and a
    mutable ``strategy_editor_draft`` are created alongside it. No revision exists
    yet — an unsaved draft cannot enter Ready Check / RUN (AT-01).
    """
    require_authenticated(actor)
    name = (display_name or "").strip()
    if not name:
        raise ValidationError(
            "A strategy display name is required.", details=[{"field": "display_name"}]
        )
    payload = initial_payload if initial_payload is not None else {}

    async def _op() -> dict[str, Any]:
        _root, strategy_root, _work_object, draft = await strat_repo.create_strategy(
            session,
            owner_principal_id=actor.principal_id or "",
            created_by_principal_id=actor.principal_id or "",
            display_name=name,
            rationale_family_id=rationale_family_id,
            initial_payload=payload,
        )
        _audit_and_outbox(
            session,
            actor,
            event_kind="strategy.draft_created",
            target_type=_STRATEGY_TARGET_TYPE,
            target_entity_id=strategy_root.entity_id,
            new_state=StrategyLifecycleStateEnum.DRAFT.value,
            payload={"draft_id": draft.draft_id, "display_name": name},
        )
        return {
            "draft_id": draft.draft_id,
            "strategy_root_id": strategy_root.entity_id,
            "display_name": name,
            "row_version": draft.row_version,
        }

    return await run_idempotent(
        session,
        key=idempotency_key,
        actor_principal_id=actor.principal_id,
        request_payload={
            "op": "create_strategy_draft",
            "display_name": name,
            "rationale_family_id": rationale_family_id,
        },
        operation=_op,
    )


# --------------------------------------------------------------------------- #
# Derive draft from a Strategy Package (GAP-03; doc 01 §8.2, doc 08 §4.3)      #
# --------------------------------------------------------------------------- #


async def derive_strategy_draft_from_package(
    session: AsyncSession,
    actor: Actor,
    *,
    source_package_root_id: str,
    source_package_revision_id: str | None = None,
    display_name: str | None = None,
    rationale_family_id: str | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Create a new Strategy draft seeded from a usable Strategy Package (doc 01 §8.2).

    This is the canonical cross-owner reuse path: rather than attaching a foreign
    work object, a viewer *derives* their OWN strategy root+draft from a Strategy
    Package they may use. The source package stays immutable; the new draft records
    the pinned source ``(root, revision, content_hash)`` and the inherited dependency
    list as ``source_provenance``. The editable config starts EMPTY — a
    ``kind=strategy`` package carries contracts + a dependency snapshot, not a full
    StrategyConfig, so it seeds provenance and the caller completes the config (doc
    08 §4.3 "create or seed a Strategy Draft").

    Guards (server re-validated, never client-authoritative): view permission
    (foreign private -> 403), Strategy-kind only, and the EXACT pinned revision must
    be usable (active + validation-passed, ``package_permissions.can_use``) -> else a
    typed 422 ``PACKAGE_NOT_DERIVABLE`` that names why (doc 08 §4.4). The revision is
    pinned exactly (explicit id or the current head — no "latest" leak, L5).
    """
    require_authenticated(actor)
    root_id = (source_package_root_id or "").strip()
    if not root_id:
        raise ValidationError(
            "A source_package_root_id is required.",
            details=[{"field": "source_package_root_id"}],
        )

    root = await pkg_repo.get_package_root(session, root_id)
    detail = await pkg_repo.get_package_detail(session, root_id)
    if root is None or detail is None or root.deletion_state != DeletionState.ACTIVE:
        raise PackageNotFound(f"Package '{root_id}' not found.")
    # View gate first — a foreign private package is a 403, not a silent no-op.
    ensure_can_view(
        actor,
        owner_principal_id=root.owner_principal_id,
        visibility=str(detail.visibility_scope),
    )
    if detail.package_kind != PackageKind.STRATEGY:
        raise PackageNotDerivableError(
            "Only Strategy packages can seed a Strategy Draft.",
            details=[{"field": "source_package_root_id", "actual": str(detail.package_kind)}],
        )

    revision = await _resolve_source_revision(session, root, source_package_revision_id)
    permissions = package_permissions(
        actor,
        owner_principal_id=root.owner_principal_id,
        visibility_scope=str(detail.visibility_scope),
        lifecycle_state=root.lifecycle_state,
        validation_state=revision.validation_state,
        approval_state=revision.approval_state,
    )
    if not permissions.can_use:
        raise PackageNotDerivableError(
            "This package revision is not usable (it must be active and validation-passed).",
            details=[
                {"field": "source_package_revision_id", "actual": revision.revision_id},
                {"field": "validation_state", "actual": str(revision.validation_state)},
            ],
        )

    source_name = _source_package_display_name(revision)
    name = (display_name or source_name).strip() or source_name
    family_id = rationale_family_id or _pinned_family_id(revision)
    provenance: dict[str, Any] = {
        "source_package_root_id": root.entity_id,
        "source_package_revision_id": revision.revision_id,
        "source_content_hash": revision.content_hash,
        "source_package_kind": str(detail.package_kind),
        "source_display_name": source_name,
        # The inherited dependency set (doc 01 §8.2) — the package revision's
        # resolved dependency snapshot, copied verbatim as origin metadata.
        "inherited_dependencies": revision.dependency_snapshot or {},
    }

    async def _op() -> dict[str, Any]:
        _root, strategy_root, _work_object, draft = await strat_repo.create_strategy(
            session,
            owner_principal_id=actor.principal_id or "",
            created_by_principal_id=actor.principal_id or "",
            display_name=name,
            rationale_family_id=family_id,
            initial_payload={},
            source_provenance=provenance,
        )
        _audit_and_outbox(
            session,
            actor,
            event_kind="strategy.derived_from_package",
            target_type=_STRATEGY_TARGET_TYPE,
            target_entity_id=strategy_root.entity_id,
            new_state=StrategyLifecycleStateEnum.DRAFT.value,
            payload={
                "draft_id": draft.draft_id,
                "display_name": name,
                "source_package_root_id": root.entity_id,
                "source_package_revision_id": revision.revision_id,
            },
        )
        return {
            "draft_id": draft.draft_id,
            "strategy_root_id": strategy_root.entity_id,
            "display_name": name,
            "row_version": draft.row_version,
            "source_provenance": provenance,
        }

    return await run_idempotent(
        session,
        key=idempotency_key,
        actor_principal_id=actor.principal_id,
        request_payload={
            "op": "derive_strategy_draft_from_package",
            "source_package_root_id": root.entity_id,
            "source_package_revision_id": revision.revision_id,
            "display_name": name,
        },
        operation=_op,
    )


async def _resolve_source_revision(
    session: AsyncSession, root: EntityRegistry, explicit_revision_id: str | None
) -> Any:
    """Pin the exact source package revision (explicit id or head; no "latest", L5)."""
    if explicit_revision_id:
        revision = await pkg_repo.get_revision(session, explicit_revision_id)
        if revision is None or revision.entity_id != root.entity_id:
            raise PackageNotFound(f"Package revision '{explicit_revision_id}' not found.")
        return revision
    revision = await pkg_repo.get_revision(session, root.current_revision_id or "")
    if revision is None:
        raise PackageNotDerivableError(
            "This package has no current revision to derive from.",
            details=[{"field": "source_package_root_id", "actual": root.entity_id}],
        )
    return revision


def _source_package_display_name(revision: Any) -> str:
    """Best-effort display name from the package revision's input contract."""
    contract = revision.input_contract if isinstance(revision.input_contract, dict) else {}
    name = contract.get("name")
    return name.strip() if isinstance(name, str) and name.strip() else "Derived Strategy"


def _pinned_family_id(revision: Any) -> str | None:
    """The package revision's pinned rationale family id (inherited if not overridden)."""
    snapshot = revision.rationale_family_snapshot or {}
    family_id = snapshot.get("rationale_family_id") if isinstance(snapshot, dict) else None
    return family_id if isinstance(family_id, str) and family_id else None


# --------------------------------------------------------------------------- #
# Patch draft                                                                 #
# --------------------------------------------------------------------------- #


async def patch_strategy_draft(
    session: AsyncSession,
    actor: Actor,
    *,
    draft_id: str,
    expected_draft_row_version: int,
    payload: dict[str, Any] | None = None,
    patch: dict[str, Any] | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Apply an edit to a draft (doc 02 §7; AT-19).

    Accepts either a full ``payload`` replacement or a shallow ``patch`` dict merged
    into the current payload. Optimistic concurrency: a stale
    ``expected_draft_row_version`` -> STRATEGY_DRAFT_CONFLICT (never last-write-wins).
    No revalidation here — the UI/agent validates on Save.
    """
    draft, strategy_root, _registry_root = await _load_editable_draft(session, actor, draft_id)

    async def _op() -> dict[str, Any]:
        await session.refresh(draft, with_for_update=True)
        if draft.row_version != expected_draft_row_version:
            raise StrategyDraftConflictError()

        if payload is not None:
            new_payload = dict(payload)
        elif patch is not None:
            new_payload = {**draft.payload, **patch}
        else:
            raise ValidationError("A payload or patch is required.", details=[{"field": "payload"}])

        draft.payload = new_payload
        draft.is_dirty = True
        draft.row_version += 1
        draft.updated_by_principal = actor.principal_id or draft.updated_by_principal
        draft.updated_at = datetime.now(UTC)
        _audit_only(
            session,
            actor,
            event_kind="strategy.draft_patched",
            target_type=_DRAFT_TARGET_TYPE,
            target_entity_id=draft.draft_id,
            previous_state=str(expected_draft_row_version),
            new_state=str(draft.row_version),
        )
        return {
            "draft_id": draft.draft_id,
            "strategy_root_id": strategy_root.entity_id if strategy_root else None,
            "row_version": draft.row_version,
            "is_dirty": draft.is_dirty,
        }

    return await run_idempotent(
        session,
        key=idempotency_key,
        actor_principal_id=actor.principal_id,
        request_payload={
            "op": "patch_strategy_draft",
            "draft_id": draft_id,
            "expected_draft_row_version": expected_draft_row_version,
            "payload": payload,
            "patch": patch,
        },
        operation=_op,
    )


# --------------------------------------------------------------------------- #
# Validate draft (no mutation, no revision)                                   #
# --------------------------------------------------------------------------- #


async def validate_strategy_draft(
    session: AsyncSession,
    actor: Actor,
    *,
    draft_id: str,
) -> dict[str, Any]:
    """Validate the draft's config WITHOUT creating a revision (doc 02 §8.4).

    Returns a structured issue envelope (machine codes + paths) so the UI/agent can
    surface blockers before Save. No immutable revision is produced.
    """
    draft = await strat_repo.get_strategy_draft(session, draft_id)
    if draft is None:
        raise StrategyDraftNotFoundError(f"Strategy draft '{draft_id}' not found.")
    owner = await _draft_owner(session, draft.strategy_root_id)
    ensure_can_view(actor, owner_principal_id=owner, visibility="private")

    _config, issues = validate_strategy_config(draft.payload)
    return {"draft_id": draft_id, "valid": not issues, "issues": issues, "warnings": []}


# --------------------------------------------------------------------------- #
# Save revision                                                               #
# --------------------------------------------------------------------------- #


async def save_strategy_revision(
    session: AsyncSession,
    actor: Actor,
    *,
    draft_id: str,
    expected_draft_row_version: int,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Save a draft as an immutable Strategy revision (doc 02 §7.1; AT-02, AT-20).

    Atomic: validate -> append immutable ``strategy_revision`` (typed +
    ``config_hash``) + pinned references -> append mirror ``work_object_revision``
    -> re-pin every attached Mainboard item to it (composition_hash changes ->
    prior Ready report STALE) -> mark the draft saved -> audit + outbox. Save is
    never a Ready PASS or a Run.
    """
    draft = await strat_repo.get_strategy_draft(session, draft_id)
    if draft is None:
        raise StrategyDraftNotFoundError(f"Strategy draft '{draft_id}' not found.")
    if draft.strategy_root_id is None:
        raise StrategyDraftNotAttachedError()
    strategy_root = await strat_repo.get_strategy_root(session, draft.strategy_root_id)
    registry_root = await strat_repo.get_strategy_registry_root(session, draft.strategy_root_id)
    if strategy_root is None or registry_root is None:
        raise StrategyDraftNotFoundError(f"Strategy '{draft.strategy_root_id}' not found.")
    ensure_can_edit(actor, owner_principal_id=registry_root.owner_principal_id)
    if strategy_root.lifecycle_state == StrategyLifecycleStateEnum.LOCKED_FOR_TEST:
        raise StrategyLockedForTestError()

    async def _op() -> dict[str, Any]:
        await session.refresh(registry_root, with_for_update=True)
        await session.refresh(draft, with_for_update=True)
        if draft.row_version != expected_draft_row_version:
            raise StrategyDraftConflictError()
        if registry_root.deletion_state != DeletionState.ACTIVE:
            raise StrategyDraftNotFoundError(f"Strategy '{registry_root.entity_id}' not found.")

        config, issues = validate_strategy_config(draft.payload)
        if config is None or issues:
            _raise_for_issues(issues)
        assert config is not None  # narrowed: issues empty and config parsed

        # GAP-16 (Master §8.1): resolve the free-text instrument scope to a canonical
        # instrument BEFORE hashing/persisting the immutable revision — unresolvable
        # -> 422 (never a silent free-text instrument in a saved strategy).
        config = await _resolve_instrument_scope(session, config)

        canonical = config_to_dict(config)
        config_hash = compute_config_hash(config)
        references = _extract_references(config)
        await _assert_references_active(session, references)

        revision = await strat_repo.append_strategy_revision(
            session,
            strategy_root,
            payload=canonical,
            config_hash=config_hash,
            validation_status=ValidationStatusEnum.VALID,
            created_by_principal_id=actor.principal_id or "",
            lifecycle_snapshot=StrategyLifecycleStateEnum.VALIDATED.value,
            family_snapshot=strategy_root.rationale_family_id,
        )
        await session.flush()

        for position, ref in enumerate(references):
            await strat_repo.add_strategy_reference(
                session,
                strategy_revision_id=revision.revision_id,
                referenced_entity_type=ref["entity_type"],
                referenced_root_id=ref["root_id"],
                referenced_revision_id=ref["revision_id"],
                referenced_content_hash=ref["content_hash"],
                dependency_role=ref["role"],
                position_in_graph=position,
            )
        await session.flush()

        # Mirror work-object revision so 3a's pin mechanics bind the typed revision.
        mirror = await mb_repo.append_work_object_revision(
            session,
            registry_root,
            object_kind=_MIRROR_KIND,
            payload={
                "strategy_revision_id": revision.revision_id,
                "config_hash": config_hash,
                "display_name": strategy_root.display_name,
            },
            source_provenance={"strategy_revision_id": revision.revision_id},
            created_by_principal_id=actor.principal_id or "",
            change_note=f"strategy revision {revision.revision_number}",
        )
        await session.flush()

        # Auto-repin every attached Mainboard item to the new mirror revision (doc
        # 02 §7.1 step 7) — REUSE 3a's pin_revision (composition_hash changes ->
        # prior Ready report STALE). First save has no items yet (no-op).
        pinned = await _repin_attached_items(
            session, actor, registry_root.entity_id, mirror.revision_id
        )

        # Lifecycle advances draft -> validated on first successful save.
        strategy_root.lifecycle_state = StrategyLifecycleStateEnum.VALIDATED
        strategy_root.updated_by_principal = (
            actor.principal_id or strategy_root.updated_by_principal
        )
        strategy_root.updated_at = datetime.now(UTC)
        registry_root.lifecycle_state = StrategyLifecycleStateEnum.VALIDATED.value

        draft.is_dirty = False
        draft.last_saved_revision_id = revision.revision_id
        draft.row_version += 1
        draft.updated_by_principal = actor.principal_id or draft.updated_by_principal
        draft.updated_at = datetime.now(UTC)

        _audit_and_outbox(
            session,
            actor,
            event_kind="strategy.revision_created",
            target_type=_STRATEGY_TARGET_TYPE,
            target_entity_id=strategy_root.entity_id,
            target_revision_id=revision.revision_id,
            new_state=StrategyLifecycleStateEnum.VALIDATED.value,
            payload={
                "strategy_revision_id": revision.revision_id,
                "revision_number": revision.revision_number,
                "config_hash": config_hash,
                "reference_count": len(references),
                "pinned_item_ids": [item["item_id"] for item in pinned],
            },
        )
        return {
            "strategy_root_id": strategy_root.entity_id,
            "strategy_revision_id": revision.revision_id,
            "revision_number": revision.revision_number,
            "config_hash": config_hash,
            "mirror_revision_id": mirror.revision_id,
            "pinned_items": pinned,
            "ready_state": "STALE",
            "warnings": [],
            "correlation_id": actor.correlation_id,
        }

    return await run_idempotent(
        session,
        key=idempotency_key,
        actor_principal_id=actor.principal_id,
        request_payload={
            "op": "save_strategy_revision",
            "draft_id": draft_id,
            "expected_draft_row_version": expected_draft_row_version,
        },
        operation=_op,
    )


# --------------------------------------------------------------------------- #
# Clear draft                                                                 #
# --------------------------------------------------------------------------- #


async def clear_strategy_draft(
    session: AsyncSession,
    actor: Actor,
    *,
    draft_id: str,
    expected_draft_row_version: int,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Reset a draft's editor state to blank (doc 02 §7; AT-23).

    Clears unsaved config only — never deletes the root or a saved revision, and
    never creates a Trash entry.
    """
    draft, _strategy_root, _registry_root = await _load_editable_draft(session, actor, draft_id)

    async def _op() -> dict[str, Any]:
        await session.refresh(draft, with_for_update=True)
        if draft.row_version != expected_draft_row_version:
            raise StrategyDraftConflictError()
        draft.payload = {}
        draft.is_dirty = False
        draft.row_version += 1
        draft.updated_by_principal = actor.principal_id or draft.updated_by_principal
        draft.updated_at = datetime.now(UTC)
        _audit_only(
            session,
            actor,
            event_kind="strategy.draft_cleared",
            target_type=_DRAFT_TARGET_TYPE,
            target_entity_id=draft.draft_id,
            new_state=str(draft.row_version),
        )
        return {"draft_id": draft.draft_id, "row_version": draft.row_version, "cleared": True}

    return await run_idempotent(
        session,
        key=idempotency_key,
        actor_principal_id=actor.principal_id,
        request_payload={
            "op": "clear_strategy_draft",
            "draft_id": draft_id,
            "expected_draft_row_version": expected_draft_row_version,
        },
        operation=_op,
    )


# --------------------------------------------------------------------------- #
# Shared helpers                                                              #
# --------------------------------------------------------------------------- #


async def _load_editable_draft(
    session: AsyncSession, actor: Actor, draft_id: str
) -> tuple[Any, StrategyRoot | None, EntityRegistry | None]:
    draft = await strat_repo.get_strategy_draft(session, draft_id)
    if draft is None:
        raise StrategyDraftNotFoundError(f"Strategy draft '{draft_id}' not found.")
    strategy_root: StrategyRoot | None = None
    registry_root: EntityRegistry | None = None
    if draft.strategy_root_id is not None:
        strategy_root = await strat_repo.get_strategy_root(session, draft.strategy_root_id)
        registry_root = await strat_repo.get_strategy_registry_root(session, draft.strategy_root_id)
    owner = registry_root.owner_principal_id if registry_root is not None else actor.principal_id
    ensure_can_edit(actor, owner_principal_id=owner)
    return draft, strategy_root, registry_root


async def _draft_owner(session: AsyncSession, strategy_root_id: str | None) -> str | None:
    if strategy_root_id is None:
        return None
    registry_root = await strat_repo.get_strategy_registry_root(session, strategy_root_id)
    return registry_root.owner_principal_id if registry_root is not None else None


async def _resolve_instrument_scope(
    session: AsyncSession, config: StrategyConfig
) -> StrategyConfig:
    """Resolve ``DataContext.instrument_scope`` to a canonical instrument (GAP-16).

    No scope declared -> the config is returned unchanged (the free-text
    ``instrument_id`` is kept, backward compatible). A populated scope resolves
    through the registry and rewrites ``data.instrument_id`` to the canonical id;
    an unresolvable/invalid scope fails closed (INSTRUMENT_SCOPE_UNRESOLVABLE /
    _INVALID -> 422) so a saved strategy can never conflate spot with perpetual.
    """
    scope = config.data.instrument_scope
    resolved_id = await instrument_query.resolve_scope_id(
        session, scope.model_dump() if scope is not None else None
    )
    if resolved_id is None:
        return config
    new_data = config.data.model_copy(update={"instrument_id": resolved_id})
    return config.model_copy(update={"data": new_data})


def _raise_for_issues(issues: list[dict[str, Any]]) -> None:
    """Map a compiler issue list to the most specific typed 422 error."""
    codes = {issue.get("code") for issue in issues}
    if CODE_SIZING_NOT_EXCLUSIVE in codes:
        raise SizingMethodNotExclusiveError(details=issues)
    if CODE_TRIGGER_CONDITION_REQUIRED in codes:
        raise TriggerSourceConditionRequiredError(details=issues)
    if CODE_ENTRY_REQUIRED_BLOCK_MISSING in codes:
        raise EntryRequiredBlockMissingError(details=issues)
    if CODE_SIGNAL_SUPPORTING_REQUIREMENT_UNMET in codes:
        raise SignalSupportingRequirementUnmetError(details=issues)
    if CODE_ENTRY_DIRECTION_INCOHERENT in codes:
        raise EntryDirectionIncoherentError(details=issues)
    raise StrategyValidationFailedError(details=issues)


def _extract_references(config: StrategyConfig) -> list[dict[str, Any]]:
    """Collect the pinned dependency edges implied by an enabled config.

    Every reference carries the exact ``(root_id, revision_id, content_hash)`` tuple
    (L5). Only enabled blocks survive ``filter_disabled_sections``, so nothing
    disabled is pinned.
    """
    refs: list[dict[str, Any]] = []

    data = config.data
    refs.append(
        {
            "entity_type": ReferencedEntityTypeEnum.MARKET_DATASET,
            "role": DependencyRoleEnum.DATA_SOURCE,
            "root_id": data.market_dataset_root_id,
            "revision_id": data.market_dataset_revision_id,
            "content_hash": data.market_dataset_content_hash,
        }
    )
    funding = data.funding
    if (
        funding.enabled
        and funding.source_root_id
        and funding.source_revision_id
        and funding.source_content_hash
    ):
        refs.append(
            {
                "entity_type": ReferencedEntityTypeEnum.RESEARCH_DATASET,
                "role": DependencyRoleEnum.FUNDING_SOURCE,
                "root_id": funding.source_root_id,
                "revision_id": funding.source_revision_id,
                "content_hash": funding.source_content_hash,
            }
        )

    _collect_block_refs(
        config.position_entry_logic.indicator_blocks,
        indicator_role=DependencyRoleEnum.ENTRY_INDICATOR,
        condition_role=DependencyRoleEnum.ENTRY_CONDITION,
        out=refs,
    )
    if config.position_exit_logic.indicator_blocks:
        _collect_block_refs(
            config.position_exit_logic.indicator_blocks,
            indicator_role=DependencyRoleEnum.EXIT_INDICATOR,
            condition_role=DependencyRoleEnum.EXIT_CONDITION,
            out=refs,
        )
    if config.scaling_logic is not None and config.scaling_logic.logic_scaling is not None:
        _collect_block_refs(
            config.scaling_logic.logic_scaling.indicator_blocks,
            indicator_role=DependencyRoleEnum.SCALING_LOGIC,
            condition_role=DependencyRoleEnum.SCALING_LOGIC,
            out=refs,
        )
    # F-08: Logic-Based Stop Blocks pin indicator + condition packages exactly like
    # entry/exit blocks, so they are validated active at save and recorded as edges.
    if config.protection_stop_logic is not None and config.protection_stop_logic.logic_blocks:
        _collect_block_refs(
            config.protection_stop_logic.logic_blocks,
            indicator_role=DependencyRoleEnum.PROTECTION_STOP_INDICATOR,
            condition_role=DependencyRoleEnum.PROTECTION_STOP_CONDITION,
            out=refs,
        )
    return refs


def _collect_block_refs(
    blocks: list[Any],
    *,
    indicator_role: DependencyRoleEnum,
    condition_role: DependencyRoleEnum,
    out: list[dict[str, Any]],
) -> None:
    for block in blocks:
        pkg = block.package_ref
        out.append(
            {
                "entity_type": ReferencedEntityTypeEnum.INDICATOR_PACKAGE,
                "role": indicator_role,
                "root_id": pkg.package_root_id,
                "revision_id": pkg.package_revision_id,
                "content_hash": pkg.package_content_hash,
            }
        )
        for condition in getattr(block, "condition_blocks", None) or []:
            cpkg = condition.package_ref
            out.append(
                {
                    "entity_type": ReferencedEntityTypeEnum.CONDITION_PACKAGE,
                    "role": condition_role,
                    "root_id": cpkg.package_root_id,
                    "revision_id": cpkg.package_revision_id,
                    "content_hash": cpkg.package_content_hash,
                }
            )


async def _assert_references_active(
    session: AsyncSession, references: list[dict[str, Any]]
) -> None:
    """Reject a Save whose pinned dependency root is soft-deleted (doc 02 §8.2).

    V1 leniency: a root that does not resolve in ``entity_registry`` is allowed
    (pinned by content_hash; integrity re-verified at manifest time, Stage 5). A
    resolved-but-not-ACTIVE root -> REFERENCE_NOT_ACTIVE.
    """
    seen: set[str] = set()
    for ref in references:
        root_id = ref["root_id"]
        if root_id in seen:
            continue
        seen.add(root_id)
        root = await session.get(EntityRegistry, root_id)
        if root is not None and root.deletion_state != DeletionState.ACTIVE:
            raise StrategyReferenceNotActiveError(
                f"Referenced dependency '{root_id}' is no longer active.",
                details=[{"field": "reference", "actual": root_id}],
            )


async def _repin_attached_items(
    session: AsyncSession, actor: Actor, work_object_root_id: str, mirror_revision_id: str
) -> list[dict[str, Any]]:
    """Re-pin every Mainboard item on this strategy to the new mirror revision.

    REUSE of 3a ``patch_mainboard_item(pin_revision)`` — each pin recomputes the
    workspace ``composition_hash`` (prior Ready report STALE) inside this same tx.
    """
    items = await mb_repo.list_items_for_root(session, work_object_root_id)
    pinned: list[dict[str, Any]] = []
    for item in items:
        result = await mb_cmd.patch_mainboard_item(
            session,
            actor,
            item_id=item.item_id,
            intent="pin_revision",
            expected_row_version=item.row_version,
            revision_id=mirror_revision_id,
            idempotency_key=None,
        )
        pinned.append(
            {
                "item_id": item.item_id,
                "pinned_revision_id": mirror_revision_id,
                "composition_hash": result.get("composition_hash"),
            }
        )
    return pinned


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


def _audit_only(
    session: AsyncSession,
    actor: Actor,
    *,
    event_kind: str,
    target_type: str,
    target_entity_id: str,
    previous_state: str | None = None,
    new_state: str | None = None,
) -> None:
    audit_repo.add_audit_event(
        session,
        event_kind=event_kind,
        actor_principal_id=actor.principal_id,
        actor_kind=actor.actor_kind,
        target_entity_id=target_entity_id,
        target_entity_type=target_type,
        previous_state=previous_state,
        new_state=new_state,
        correlation_id=actor.correlation_id,
    )


__all__ = [
    "clear_strategy_draft",
    "create_strategy_draft",
    "derive_strategy_draft_from_package",
    "patch_strategy_draft",
    "save_strategy_revision",
    "validate_strategy_draft",
]
