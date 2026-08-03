"""ESP lifecycle-safe resolution — PC-19 (doc 07) and ESP-17 (doc 09 §15 row 17).

Two clauses of PC-19 are asserted here, and they pull in opposite directions:

  * a HISTORICAL pin stays readable forever (the dependent revision is immutable
    and names an exact ``embedded_revision_id``), and
  * a NEW Pre-Check must NOT resolve a soft-deleted / purge-pending / purged /
    deprecated resolver.

Before this slice only the first held. ``queries/esp.py::resolve_embedded_dependency``
decided on ``entry.trust_state`` alone, and soft delete never touched the registry,
so a soft-deleted ESP kept resolving into NEW work while the function's own
docstring claimed otherwise. ESP-17 (doc 09 §9.5 step 2) is the other half: a
trusted-active resolver root is not deletable at all — Deprecate first.

Auto-skips without PostgreSQL (see tests/integration/conftest.py).
"""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from entropia.application.commands import esp as esp_cmd
from entropia.application.commands import package_lifecycle as pkg_cmd
from entropia.application.commands.deletion import restore_entity, soft_delete_entity
from entropia.application.jobs.create_package import registry_fingerprint
from entropia.application.queries.esp import resolve_embedded_dependency
from entropia.domain.deletion import next_deletion_state
from entropia.domain.esp.enums import ResolverTrustState, RuntimeAdapter
from entropia.domain.identity import Actor
from entropia.domain.lifecycle.enums import (
    ApprovalState,
    DeletionState,
    PackageKind,
    PrincipalType,
    Role,
    VisibilityScope,
)
from entropia.domain.package.enums import PackageValidationState
from entropia.infrastructure.postgres.models import (
    ApprovalDecision,
    AuditEvent,
    OutboxEvent,
    Principal,
    TrashEntry,
)
from entropia.infrastructure.postgres.repositories import esp as esp_repo
from entropia.infrastructure.postgres.repositories import packages as pkg_repo
from entropia.shared.errors import (
    ApprovalRequiresAdmin,
    DeletePolicyBlocked,
    ResolverNotActive,
    ResolverNotResolved,
    ResolverRegistryConflict,
    ResolverSignatureMismatch,
)

pytestmark = pytest.mark.integration

ADMIN = Actor(principal_id="user_admin", principal_type=PrincipalType.HUMAN, role=Role.ADMIN)
OWNER = Actor(principal_id="user_1", principal_type=PrincipalType.HUMAN, role=Role.USER)

_SMA_SIG: dict[str, Any] = {
    "params": [{"name": "source", "type": "series"}, {"name": "length", "type": "int"}],
    "return": "series",
}
# A real ta.sma(3) vector over [1..5] — activation requires a PASSED validation run
# (R8), so every trusted fixture below goes through it rather than faking the state.
_EVIDENCE = {
    "test_vectors": [
        {
            "name": "sma_len3",
            "length": 3,
            "close": [1, 2, 3, 4, 5],
            "expected": [None, None, 2, 3, 4],
        }
    ],
    "review": "passed",
}


async def _count(session, model) -> int:
    return int((await session.execute(select(func.count()).select_from(model))).scalar_one())


async def _seed_principals(session) -> None:
    for pid in ("user_admin", "user_1"):
        if await session.get(Principal, pid) is None:
            session.add(Principal(principal_id=pid, principal_type=PrincipalType.HUMAN))
    await session.flush()


async def _create_esp(session, *, key: str = "ta.sma") -> dict:
    return await esp_cmd.create_esp_package(
        session,
        OWNER,
        canonical_key=key,
        signature=_SMA_SIG,
        runtime_adapter=RuntimeAdapter.PINE_V5,
        input_contract={"resolver_key": key},
        output_contract={"return": "series"},
        evidence=_EVIDENCE,
        visibility_scope=VisibilityScope.SYSTEM,
    )


async def _trusted_esp(session, *, key: str = "ta.sma") -> dict:
    """Create -> validate -> Admin-activate one resolver (the trusted fixture)."""
    created = await _create_esp(session, key=key)
    await esp_cmd.run_resolver_validation(
        session, OWNER, entity_id=created["entity_id"], revision_id=created["revision_id"]
    )
    await esp_cmd.activate_resolver(
        session,
        ADMIN,
        entity_id=created["entity_id"],
        revision_id=created["revision_id"],
        canonical_key=key,
        expected_registry_version=1,
    )
    await session.commit()
    return created


async def _resolve(session, *, key: str = "ta.sma", signature: dict[str, Any] | None = None):
    return await resolve_embedded_dependency(
        session,
        parsed_call={"key": key, "signature": signature if signature is not None else _SMA_SIG},
        target_runtime=RuntimeAdapter.PINE_V5,
    )


async def _force_deletion_state(session, entity_id: str, target: DeletionState) -> None:
    """Walk a root to a terminal deletion state through the domain state machine.

    ``purge_pending`` and ``purged`` are otherwise reachable only through the
    Admin re-auth + durable purge job, which is covered by the Trash suites. What
    is under test HERE is the resolution gate over each state, so the states are
    produced legally (``next_deletion_state`` rejects illegal jumps) without
    re-running the purge workflow.
    """
    root = await pkg_repo.get_package_root(session, entity_id)
    assert root is not None
    for step in (DeletionState.SOFT_DELETED, DeletionState.PURGE_PENDING, DeletionState.PURGED):
        root.deletion_state = next_deletion_state(root.deletion_state, step)
        if step == target:
            break
    await session.commit()


# --------------------------------------------------------------------------- #
# The success case stays green (the gate narrows resolution, it does not break it)
# --------------------------------------------------------------------------- #


async def test_active_trusted_resolver_resolves_to_its_exact_revision(session) -> None:
    await _seed_principals(session)
    esp = await _trusted_esp(session)

    resolved = await _resolve(session)

    assert resolved["resolved"] is True
    assert resolved["revision_id"] == esp["revision_id"]
    assert resolved["entity_id"] == esp["entity_id"]
    # P4/L5: the pin is the exact revision + its content hash, never name-only.
    revision = await pkg_repo.get_revision(session, esp["revision_id"])
    assert revision is not None
    assert resolved["content_hash"] == revision.content_hash


# --------------------------------------------------------------------------- #
# PC-19 clause 2 — a root that has left ACTIVE never resolves for NEW work      #
# --------------------------------------------------------------------------- #


async def test_soft_deleted_root_with_a_live_pointer_does_not_resolve(session) -> None:
    """THE DEFECT THIS SLICE FIXES, in its exact pre-fix database shape.

    The root is soft-deleted while ``embedded_resolver_registry`` still says
    ``trusted_active`` — which is precisely what the old code produced, because
    soft delete never touched the registry. The command layer can no longer CREATE
    this state (deprecate-first blocks it, asserted below), so the fixture writes
    it directly: rows already in a database from before this slice are in exactly
    this shape, and resolution must refuse them rather than trust the pointer.

    Reproduced on ``origin/main`` before the fix: this same sequence returned
    ``resolved=True`` with the pre-delete revision id, so a fresh Pre-Check would
    have pinned a resolver sitting in the Trash.
    """
    await _seed_principals(session)
    esp = await _trusted_esp(session)
    assert (await _resolve(session))["revision_id"] == esp["revision_id"]

    root = await pkg_repo.get_package_root(session, esp["entity_id"])
    assert root is not None
    root.deletion_state = next_deletion_state(root.deletion_state, DeletionState.SOFT_DELETED)
    await session.commit()

    entry = await esp_repo.get_registry_by_key(session, "ta.sma")
    assert entry is not None
    assert entry.trust_state == ResolverTrustState.TRUSTED_ACTIVE  # the stale pointer
    assert entry.trusted_active_revision_id == esp["revision_id"]

    with pytest.raises(ResolverNotActive) as exc_info:
        await _resolve(session)
    assert exc_info.value.code == "RESOLVER_NOT_ACTIVE"
    assert exc_info.value.http_status == 409


async def test_the_ordered_deprecate_then_delete_path_also_closes_resolution(session) -> None:
    """The production route. Deprecation clears the pointer first, so the coarser
    "no trusted revision for this key" gate answers before the root gate ever runs
    — both refusals are correct, and the caller is told to propose/activate rather
    than to wait for something to come back."""
    await _seed_principals(session)
    esp = await _trusted_esp(session)

    await esp_cmd.deprecate_resolver(
        session, ADMIN, canonical_key="ta.sma", reason="retired", expected_registry_version=2
    )
    await soft_delete_entity(session, ADMIN, entity_id=esp["entity_id"], reason="retired")
    await session.commit()

    root = await pkg_repo.get_package_root(session, esp["entity_id"])
    assert root is not None and root.deletion_state == DeletionState.SOFT_DELETED
    with pytest.raises(ResolverNotResolved):
        await _resolve(session)


@pytest.mark.parametrize(
    "target", [DeletionState.PURGE_PENDING, DeletionState.PURGED], ids=["purge_pending", "purged"]
)
async def test_purge_states_do_not_resolve(session, target) -> None:
    """purge_pending is not a grace period and purged is not a fallback: both are
    non-ACTIVE, so both close the resolver for new work."""
    await _seed_principals(session)
    await _trusted_esp(session)
    entry = await esp_repo.get_registry_by_key(session, "ta.sma")
    assert entry is not None
    await _force_deletion_state(session, entry.package_entity_id, target)

    root = await pkg_repo.get_package_root(session, entry.package_entity_id)
    assert root is not None and root.deletion_state == target
    with pytest.raises(ResolverNotActive):
        await _resolve(session)


async def test_lifecycle_deprecated_root_does_not_resolve(session) -> None:
    """The ROOT's own ``lifecycle_state`` (written by ``deprecate_package``) closes
    the resolver even while the registry pointer is untouched — the two facets are
    independent (doc 09 §11.2), so each one is load-bearing on its own."""
    await _seed_principals(session)
    await _trusted_esp(session)
    entry = await esp_repo.get_registry_by_key(session, "ta.sma")
    assert entry is not None
    root = await pkg_repo.get_package_root(session, entry.package_entity_id)
    assert root is not None
    root.lifecycle_state = "deprecated"
    await session.commit()

    # The registry still says trusted_active — only the root moved.
    entry = await esp_repo.get_registry_by_key(session, "ta.sma")
    assert entry is not None and entry.trust_state == ResolverTrustState.TRUSTED_ACTIVE
    with pytest.raises(ResolverNotActive):
        await _resolve(session)


async def test_candidate_resolver_does_not_resolve(session) -> None:
    """Never trusted -> RESOLVER_NOT_RESOLVED (propose), not RESOLVER_NOT_ACTIVE."""
    await _seed_principals(session)
    await _create_esp(session)
    await session.commit()

    with pytest.raises(ResolverNotResolved):
        await _resolve(session)


async def test_deprecated_registry_entry_does_not_resolve(session) -> None:
    await _seed_principals(session)
    await _trusted_esp(session)
    await esp_cmd.deprecate_resolver(
        session, ADMIN, canonical_key="ta.sma", reason="superseded", expected_registry_version=2
    )
    await session.commit()

    with pytest.raises(ResolverNotResolved):
        # Deprecation clears the pointer, so the key no longer has a trusted
        # revision at all — the earlier, coarser gate answers first.
        await _resolve(session)


# --------------------------------------------------------------------------- #
# Structural failures: missing root, wrong kind, contract/adapter mismatch      #
# --------------------------------------------------------------------------- #


async def test_registry_pointing_at_an_entity_with_no_package_detail_does_not_resolve(
    session,
) -> None:
    """A pointer with no package behind it is "no resolver", not "an inactive one".

    A fully dangling ``package_entity_id`` is unreachable — I-08 (PR #517) put a FK
    on that column, and the database rejects the write outright (asserted below).
    What IS reachable is a registry row whose entity exists but carries no
    ``package_root`` detail, so that is the shape exercised here.
    """
    await _seed_principals(session)
    esp = await _trusted_esp(session)
    detail = await pkg_repo.get_package_detail(session, esp["entity_id"])
    assert detail is not None
    await session.delete(detail)
    await session.commit()

    with pytest.raises(ResolverNotResolved):
        await _resolve(session)

    # And the truly-dangling pointer cannot even be written.
    entry = await esp_repo.get_registry_by_key(session, "ta.sma")
    assert entry is not None
    entry.package_entity_id = "pkg_does_not_exist"
    with pytest.raises(IntegrityError):
        await session.flush()
    await session.rollback()


async def test_registry_pointing_at_a_non_embedded_package_does_not_resolve(session) -> None:
    """Registry-root mismatch: the pointer names a real package of the WRONG kind."""
    await _seed_principals(session)
    await _trusted_esp(session)
    other_root, _detail, _revision = await pkg_repo.create_package(
        session,
        owner_principal_id="user_1",
        created_by_principal_id="user_1",
        package_kind=PackageKind.INDICATOR,
        input_contract={"name": "not a resolver"},
        output_contract={"output_kinds": ["signal"]},
        dependency_snapshot={},
        visibility_scope=VisibilityScope.PRIVATE,
        validation_state=PackageValidationState.PASSED,
        approval_state=ApprovalState.APPROVED,
    )
    entry = await esp_repo.get_registry_by_key(session, "ta.sma")
    assert entry is not None
    entry.package_entity_id = other_root.entity_id
    await session.commit()

    with pytest.raises(ResolverNotResolved):
        await _resolve(session)


async def test_signature_mismatch_still_reports_its_own_code(session) -> None:
    """The new root gate must not swallow the pre-existing contract diagnostics."""
    await _seed_principals(session)
    await _trusted_esp(session)
    reversed_call = {
        "params": [{"name": "length", "type": "int"}, {"name": "source", "type": "series"}],
        "return": "series",
    }

    with pytest.raises(ResolverSignatureMismatch):
        await _resolve(session, signature=reversed_call)


async def test_adapter_mismatch_still_reports_its_own_code(session) -> None:
    await _seed_principals(session)
    await _trusted_esp(session)

    from entropia.shared.errors import ResolverAdapterIncompatible

    with pytest.raises(ResolverAdapterIncompatible):
        await resolve_embedded_dependency(
            session,
            parsed_call={"key": "ta.sma", "signature": _SMA_SIG},
            target_runtime=RuntimeAdapter.PYTHON,
        )


# --------------------------------------------------------------------------- #
# ESP-17 — deprecate-first delete policy (doc 09 §9.5 step 2)                   #
# --------------------------------------------------------------------------- #


async def test_trusted_active_resolver_root_cannot_be_deleted(session) -> None:
    await _seed_principals(session)
    esp = await _trusted_esp(session)
    trash_before = await _count(session, TrashEntry)
    audits_before = await _count(session, AuditEvent)

    with pytest.raises(DeletePolicyBlocked) as exc_info:
        await soft_delete_entity(session, ADMIN, entity_id=esp["entity_id"], reason="oops")
    await session.rollback()

    assert exc_info.value.code == "DELETE_POLICY_BLOCKED"
    assert exc_info.value.http_status == 409
    assert exc_info.value.suggested_action == "deprecate_resolver_first"
    assert exc_info.value.scope_id == esp["entity_id"]
    assert exc_info.value.field_path == "ta.sma"

    # The refusal is total: root untouched, and no Trash Entry or audit was written.
    root = await pkg_repo.get_package_root(session, esp["entity_id"])
    assert root is not None and root.deletion_state == DeletionState.ACTIVE
    assert await _count(session, TrashEntry) == trash_before
    assert await _count(session, AuditEvent) == audits_before


async def test_the_production_package_delete_route_is_blocked_too(session) -> None:
    """``pkg_cmd.soft_delete_package`` (doc 08 §7 "Move to Trash", the command behind
    ``DELETE /library/{entity_id}``) is the route a user actually takes, and it runs
    through ``soft_delete_registry_root`` — which executed NO preflight at all before
    this slice. A blocker wired only into ``soft_delete_entity`` would have left this
    path wide open, so it is asserted separately rather than assumed."""
    await _seed_principals(session)
    esp = await _trusted_esp(session)
    trash_before = await _count(session, TrashEntry)

    with pytest.raises(DeletePolicyBlocked) as exc_info:
        await pkg_cmd.soft_delete_package(session, ADMIN, entity_id=esp["entity_id"])
    await session.rollback()

    assert exc_info.value.code == "DELETE_POLICY_BLOCKED"
    root = await pkg_repo.get_package_root(session, esp["entity_id"])
    assert root is not None and root.deletion_state == DeletionState.ACTIVE
    assert await _count(session, TrashEntry) == trash_before


async def test_the_production_route_deletes_once_the_resolver_is_deprecated(session) -> None:
    await _seed_principals(session)
    esp = await _trusted_esp(session)
    await esp_cmd.deprecate_resolver(
        session, ADMIN, canonical_key="ta.sma", reason="retired", expected_registry_version=2
    )
    await session.commit()

    result = await pkg_cmd.soft_delete_package(session, ADMIN, entity_id=esp["entity_id"])
    await session.commit()

    assert result["deletion_state"] == str(DeletionState.SOFT_DELETED)


async def test_a_non_resolver_package_is_still_deletable(session) -> None:
    """The blocker is scoped to live resolvers — an ordinary package still deletes."""
    await _seed_principals(session)
    root, _detail, _revision = await pkg_repo.create_package(
        session,
        owner_principal_id="user_1",
        created_by_principal_id="user_1",
        package_kind=PackageKind.INDICATOR,
        input_contract={"name": "ordinary"},
        output_contract={"output_kinds": ["signal"]},
        dependency_snapshot={},
        visibility_scope=VisibilityScope.PRIVATE,
        validation_state=PackageValidationState.PASSED,
        approval_state=ApprovalState.APPROVED,
    )
    await session.commit()

    deleted = await soft_delete_entity(session, ADMIN, entity_id=root.entity_id, reason="cleanup")
    await session.commit()
    assert deleted.deletion_state == DeletionState.SOFT_DELETED


async def test_deprecate_clears_the_pointer_then_the_delete_succeeds(session) -> None:
    """The ordered path, end to end, with the registry/Trash invariant asserted."""
    await _seed_principals(session)
    esp = await _trusted_esp(session)

    result = await esp_cmd.deprecate_resolver(
        session,
        ADMIN,
        canonical_key="ta.sma",
        reason="superseded by v2",
        expected_registry_version=2,
    )
    await session.commit()

    entry = await esp_repo.get_registry_by_key(session, "ta.sma")
    assert entry is not None
    assert entry.trust_state == ResolverTrustState.DEPRECATED
    assert entry.trusted_active_revision_id is None  # pointer cleared
    assert entry.registry_version == 3  # bumped: 1 create -> 2 activate -> 3 deprecate
    assert result["trust_state"] == str(ResolverTrustState.DEPRECATED)

    deleted = await soft_delete_entity(session, ADMIN, entity_id=esp["entity_id"], reason="retired")
    await session.commit()

    assert deleted.deletion_state == DeletionState.SOFT_DELETED
    # Atomic consistency: a Trashed resolver root is never trusted_active.
    entry = await esp_repo.get_registry_by_key(session, "ta.sma")
    assert entry is not None and entry.trust_state != ResolverTrustState.TRUSTED_ACTIVE
    trash = (
        await session.execute(select(TrashEntry).where(TrashEntry.entity_id == esp["entity_id"]))
    ).scalar_one()
    assert trash.entity_type == "package"


async def test_deprecation_writes_approval_audit_and_outbox_in_one_transaction(session) -> None:
    await _seed_principals(session)
    await _trusted_esp(session)
    approvals_before = await _count(session, ApprovalDecision)
    audits_before = await _count(session, AuditEvent)
    outbox_before = await _count(session, OutboxEvent)

    await esp_cmd.deprecate_resolver(
        session, ADMIN, canonical_key="ta.sma", reason="retired", expected_registry_version=2
    )
    await session.commit()

    assert await _count(session, ApprovalDecision) == approvals_before + 1
    assert await _count(session, AuditEvent) == audits_before + 1
    assert await _count(session, OutboxEvent) == outbox_before + 1
    audit = (
        await session.execute(select(AuditEvent).where(AuditEvent.event_kind == "esp.deprecated"))
    ).scalar_one()
    assert audit.new_state == str(ResolverTrustState.DEPRECATED)


async def test_non_admin_cannot_deprecate(session) -> None:
    await _seed_principals(session)
    await _trusted_esp(session)

    with pytest.raises(ApprovalRequiresAdmin):
        await esp_cmd.deprecate_resolver(
            session, OWNER, canonical_key="ta.sma", reason="not mine to retire"
        )
    await session.rollback()

    entry = await esp_repo.get_registry_by_key(session, "ta.sma")
    assert entry is not None and entry.trust_state == ResolverTrustState.TRUSTED_ACTIVE


async def test_stale_registry_version_loses_to_the_committed_head(session) -> None:
    """Concurrent deprecate: the second caller holds version 2, which the first
    already consumed -> RESOLVER_REGISTRY_CONFLICT, no silent second transition."""
    await _seed_principals(session)
    await _trusted_esp(session)
    await esp_cmd.deprecate_resolver(
        session, ADMIN, canonical_key="ta.sma", reason="first wins", expected_registry_version=2
    )
    await session.commit()

    with pytest.raises(ResolverRegistryConflict):
        await esp_cmd.deprecate_resolver(
            session,
            ADMIN,
            canonical_key="ta.sma",
            reason="second loses",
            expected_registry_version=2,
        )
    await session.rollback()

    entry = await esp_repo.get_registry_by_key(session, "ta.sma")
    assert entry is not None and entry.registry_version == 3


async def test_idempotent_deprecate_replay_returns_the_cached_result(session) -> None:
    await _seed_principals(session)
    await _trusted_esp(session)

    first = await esp_cmd.deprecate_resolver(
        session,
        ADMIN,
        canonical_key="ta.sma",
        reason="retired",
        expected_registry_version=2,
        idempotency_key="dep-k1",
    )
    await session.commit()
    approvals_after_first = await _count(session, ApprovalDecision)

    second = await esp_cmd.deprecate_resolver(
        session,
        ADMIN,
        canonical_key="ta.sma",
        reason="retired",
        expected_registry_version=2,
        idempotency_key="dep-k1",
    )
    await session.commit()

    assert second == first
    assert await _count(session, ApprovalDecision) == approvals_after_first
    entry = await esp_repo.get_registry_by_key(session, "ta.sma")
    assert entry is not None and entry.registry_version == 3  # no second bump


# --------------------------------------------------------------------------- #
# Restore semantics + historical integrity                                      #
# --------------------------------------------------------------------------- #


async def test_restore_reactivates_the_root_but_not_the_trust_pointer(session) -> None:
    """doc 09 §9.5 step 4: restore "does not automatically reinstate a resolver
    trust pointer without policy re-evaluation". The root becomes usable again;
    selecting it for NEW work still requires an explicit Admin activation."""
    await _seed_principals(session)
    esp = await _trusted_esp(session)
    await esp_cmd.deprecate_resolver(
        session, ADMIN, canonical_key="ta.sma", reason="retired", expected_registry_version=2
    )
    await soft_delete_entity(session, ADMIN, entity_id=esp["entity_id"], reason="retired")
    await session.commit()

    restored = await restore_entity(session, ADMIN, entity_id=esp["entity_id"])
    await session.commit()

    assert restored.deletion_state == DeletionState.ACTIVE
    entry = await esp_repo.get_registry_by_key(session, "ta.sma")
    assert entry is not None
    assert entry.trust_state == ResolverTrustState.DEPRECATED  # NOT auto-reactivated
    assert entry.trusted_active_revision_id is None
    # And the resolver is still closed for new work after the restore.
    with pytest.raises(ResolverNotResolved):
        await _resolve(session)


async def test_historical_pin_stays_readable_after_the_resolver_is_closed(session) -> None:
    """PC-19 clause 1, re-asserted against the NEW gate: closing a resolver for new
    work must not touch anything a historical manifest reads. The dependent
    revision keeps its verbatim snapshot and the pinned ESP revision keeps its
    exact content hash — the pair a Run/Result manifest needs to reproduce."""
    await _seed_principals(session)
    esp = await _trusted_esp(session)
    esp_revision = await pkg_repo.get_revision(session, esp["revision_id"])
    assert esp_revision is not None
    pinned_hash = esp_revision.content_hash

    dependency_snapshot = {
        "resolved": [
            {
                "canonical_key": "ta.sma",
                "embedded_entity_id": esp["entity_id"],
                "embedded_revision_id": esp["revision_id"],
            }
        ]
    }
    _dependent_root, _detail, dependent_revision = await pkg_repo.create_package(
        session,
        owner_principal_id="user_1",
        created_by_principal_id="user_1",
        package_kind=PackageKind.INDICATOR,
        input_contract={"name": "Uses ta.sma"},
        output_contract={"output_kinds": ["signal"]},
        dependency_snapshot=dependency_snapshot,
        visibility_scope=VisibilityScope.PRIVATE,
        validation_state=PackageValidationState.PASSED,
        approval_state=ApprovalState.APPROVED,
    )
    await session.commit()

    await esp_cmd.deprecate_resolver(
        session, ADMIN, canonical_key="ta.sma", reason="retired", expected_registry_version=2
    )
    await soft_delete_entity(session, ADMIN, entity_id=esp["entity_id"], reason="retired")
    await session.commit()

    # New work is closed ...
    with pytest.raises(ResolverNotResolved):
        await _resolve(session)
    # ... and the historical pin is untouched.
    historical = await pkg_repo.get_revision(session, dependent_revision.revision_id)
    assert historical is not None
    assert historical.dependency_snapshot == dependency_snapshot
    still_pinned = await pkg_repo.get_revision(session, esp["revision_id"])
    assert still_pinned is not None
    assert still_pinned.content_hash == pinned_hash


# --------------------------------------------------------------------------- #
# Pre-Check staleness is derived server-side from registry AND root lifecycle    #
# --------------------------------------------------------------------------- #


async def test_root_soft_delete_changes_the_registry_fingerprint(session) -> None:
    """doc 07 §8.1: the scan's registry fingerprint is the server's own staleness
    evidence. Before this slice it hashed the registry pointer only, so a resolver
    root could be deleted without the fingerprint moving and an already-PASSED scan
    stayed "fresh". The browser never derives this — it only sees the refusal."""
    await _seed_principals(session)
    esp = await _trusted_esp(session)
    declared = [{"key": "ta.sma", "signature": _SMA_SIG}]

    fresh = await registry_fingerprint(session, declared)

    await esp_cmd.deprecate_resolver(
        session, ADMIN, canonical_key="ta.sma", reason="retired", expected_registry_version=2
    )
    await session.commit()
    after_deprecate = await registry_fingerprint(session, declared)

    await soft_delete_entity(session, ADMIN, entity_id=esp["entity_id"], reason="retired")
    await session.commit()
    after_delete = await registry_fingerprint(session, declared)

    assert fresh != after_deprecate  # registry facet moved
    assert after_deprecate != after_delete  # root lifecycle facet moved — the new half
