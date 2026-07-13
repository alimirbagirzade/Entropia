"""Stage 2c ESP acceptance — exercised against a real database.

Auto-skips when no PostgreSQL is reachable (see tests/integration/conftest.py).
Covers: create ESP package (+1 audit & +1 outbox, CANDIDATE registry row),
activate (CANDIDATE -> TRUSTED_ACTIVE, approval_decision recorded, revision
APPROVED — validation stays ``pending`` because activation does not fabricate a
validation pass, GAP-07c/doc 09 §7), the evidence precondition (activating a
resolver with no/empty test-vector evidence -> RESOLVER_EVIDENCE_REQUIRED),
deprecate, resolve returns the exact revision only once trusted_active + a
validation run marked it passed + approved, optimistic/stale registry version ->
409, idempotent activate replay returns the cached result, soft-delete preserves
the revision chain, and seed-style TA resolvers are resolvable.
"""

from __future__ import annotations

import pytest
from sqlalchemy import func, select

from entropia.application.commands import esp as esp_cmd
from entropia.application.commands.deletion import soft_delete_entity
from entropia.application.queries.esp import resolve_embedded_dependency
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
    EmbeddedResolverRegistry,
    OutboxEvent,
    Principal,
)
from entropia.infrastructure.postgres.repositories import esp as esp_repo
from entropia.infrastructure.postgres.repositories import packages as pkg_repo
from entropia.shared.errors import (
    ResolverAdapterIncompatible,
    ResolverEvidenceRequired,
    ResolverNotResolved,
    ResolverRegistryConflict,
    ResolverSignatureMismatch,
)

pytestmark = pytest.mark.integration

ADMIN = Actor(principal_id="user_admin", principal_type=PrincipalType.HUMAN, role=Role.ADMIN)
OWNER = Actor(principal_id="user_1", principal_type=PrincipalType.HUMAN, role=Role.USER)

_SMA_SIG = {
    "params": [{"name": "source", "type": "series"}, {"name": "length", "type": "int"}],
    "return": "series",
}

# Passing test-vector evidence is a precondition for trusted activation (doc 09
# §4.2/§7). A proposal carries it so an Admin can activate; the rejection tests
# override it with None/{} to prove the gate.
_EVIDENCE = {"test_vectors": ["warmup", "boundary", "normal"], "review": "passed"}


async def _count(session, model) -> int:
    return int((await session.execute(select(func.count()).select_from(model))).scalar_one())


async def _seed_principals(session) -> None:
    for pid in ("user_admin", "user_1"):
        if await session.get(Principal, pid) is None:
            session.add(Principal(principal_id=pid, principal_type=PrincipalType.HUMAN))
    await session.flush()


async def _create_esp(session, *, key: str = "ta.sma", evidence: dict | None = _EVIDENCE) -> dict:
    return await esp_cmd.create_esp_package(
        session,
        OWNER,
        canonical_key=key,
        signature=_SMA_SIG,
        runtime_adapter=RuntimeAdapter.PINE_V5,
        input_contract={"resolver_key": key},
        output_contract={"return": "series"},
        evidence=evidence,
    )


async def test_create_esp_inserts_audit_outbox_and_candidate(session) -> None:
    await _seed_principals(session)
    before_audit = await _count(session, AuditEvent)
    before_outbox = await _count(session, OutboxEvent)

    created = await _create_esp(session)
    await session.commit()

    assert created["trust_state"] == str(ResolverTrustState.CANDIDATE)
    assert await _count(session, AuditEvent) == before_audit + 1
    assert await _count(session, OutboxEvent) == before_outbox + 1

    entry = await esp_repo.get_registry_by_key(session, "ta.sma")
    assert entry is not None
    assert entry.trust_state == ResolverTrustState.CANDIDATE
    assert entry.registry_version == 1


async def test_activate_promotes_and_records_decision(session) -> None:
    await _seed_principals(session)
    created = await _create_esp(session)
    await session.commit()

    before_decisions = await _count(session, ApprovalDecision)
    before_audit = await _count(session, AuditEvent)

    result = await esp_cmd.activate_resolver(
        session,
        ADMIN,
        entity_id=created["entity_id"],
        revision_id=created["revision_id"],
        canonical_key="ta.sma",
        expected_registry_version=1,
        note="evidence passed",
    )
    await session.commit()

    assert result["trust_state"] == str(ResolverTrustState.TRUSTED_ACTIVE)
    assert result["registry_version"] == 2
    assert await _count(session, ApprovalDecision) == before_decisions + 1
    assert await _count(session, AuditEvent) == before_audit + 1

    entry = await esp_repo.get_registry_by_key(session, "ta.sma")
    assert entry is not None
    assert entry.trusted_active_revision_id == created["revision_id"]
    revision = await pkg_repo.get_revision(session, created["revision_id"])
    assert revision is not None
    # Activation records the Admin's APPROVAL but does NOT fabricate a validation
    # pass: with only a presence gate (GAP-07c), validation stays PENDING until a
    # real validation run (separate scope) marks the evidence passed (doc 09 §7).
    assert revision.validation_state == PackageValidationState.PENDING
    assert revision.approval_state == ApprovalState.APPROVED


async def test_activate_without_evidence_rejected(session) -> None:
    """Doc 09 §4.2/§7: passing test-vector evidence is a precondition for trusted
    activation. A proposal carrying no evidence cannot be activated."""
    await _seed_principals(session)
    created = await _create_esp(session, evidence=None)
    await session.commit()

    with pytest.raises(ResolverEvidenceRequired):
        await esp_cmd.activate_resolver(
            session,
            ADMIN,
            entity_id=created["entity_id"],
            revision_id=created["revision_id"],
            canonical_key="ta.sma",
            expected_registry_version=1,
        )

    # The registry pointer is untouched — no partial activation.
    entry = await esp_repo.get_registry_by_key(session, "ta.sma")
    assert entry is not None
    assert entry.trust_state == ResolverTrustState.CANDIDATE
    assert entry.registry_version == 1


async def test_activate_with_empty_evidence_rejected(session) -> None:
    """An empty ``evidence`` payload ({}) counts as no evidence (presence gate)."""
    await _seed_principals(session)
    created = await _create_esp(session, evidence={})
    await session.commit()

    with pytest.raises(ResolverEvidenceRequired):
        await esp_cmd.activate_resolver(
            session,
            ADMIN,
            entity_id=created["entity_id"],
            revision_id=created["revision_id"],
            canonical_key="ta.sma",
            expected_registry_version=1,
        )


async def test_resolve_returns_exact_revision_only_when_trusted(session) -> None:
    await _seed_principals(session)
    created = await _create_esp(session)
    await session.commit()

    # Candidate -> not resolvable yet.
    with pytest.raises(ResolverNotResolved):
        await resolve_embedded_dependency(
            session,
            parsed_call={"key": "ta.sma", "signature": _SMA_SIG},
            target_runtime=RuntimeAdapter.PINE_V5,
        )

    await esp_cmd.activate_resolver(
        session,
        ADMIN,
        entity_id=created["entity_id"],
        revision_id=created["revision_id"],
        canonical_key="ta.sma",
        expected_registry_version=1,
    )
    await session.commit()

    # Trusted-active + approved but validation still PENDING -> not yet resolvable
    # (doc 09 §4.3 step 5). Activation is an approval, not a validation pass.
    with pytest.raises(ResolverNotResolved):
        await resolve_embedded_dependency(
            session,
            parsed_call={"key": "ta.sma", "signature": _SMA_SIG},
            target_runtime=RuntimeAdapter.PINE_V5,
        )

    # Simulate the out-of-scope validation run marking the evidence as passed.
    revision = await pkg_repo.get_revision(session, created["revision_id"])
    assert revision is not None
    revision.validation_state = PackageValidationState.PASSED
    await session.commit()

    resolved = await resolve_embedded_dependency(
        session,
        parsed_call={"key": "ta.sma", "signature": _SMA_SIG},
        target_runtime=RuntimeAdapter.PINE_V5,
    )
    assert resolved["resolved"] is True
    assert resolved["revision_id"] == created["revision_id"]
    assert resolved["content_hash"]


async def test_resolve_signature_mismatch_and_adapter(session) -> None:
    await _seed_principals(session)
    created = await _create_esp(session)
    await esp_cmd.activate_resolver(
        session,
        ADMIN,
        entity_id=created["entity_id"],
        revision_id=created["revision_id"],
        canonical_key="ta.sma",
        expected_registry_version=1,
    )
    await session.commit()

    reversed_call = {
        "params": [{"name": "length", "type": "int"}, {"name": "source", "type": "series"}],
        "return": "series",
    }
    with pytest.raises(ResolverSignatureMismatch):
        await resolve_embedded_dependency(
            session,
            parsed_call={"key": "ta.sma", "signature": reversed_call},
            target_runtime=RuntimeAdapter.PINE_V5,
        )
    with pytest.raises(ResolverAdapterIncompatible):
        await resolve_embedded_dependency(
            session,
            parsed_call={"key": "ta.sma", "signature": _SMA_SIG},
            target_runtime=RuntimeAdapter.PYTHON,
        )


async def test_deprecate_closes_new_selection(session) -> None:
    await _seed_principals(session)
    created = await _create_esp(session)
    await esp_cmd.activate_resolver(
        session,
        ADMIN,
        entity_id=created["entity_id"],
        revision_id=created["revision_id"],
        canonical_key="ta.sma",
        expected_registry_version=1,
    )
    await session.commit()

    result = await esp_cmd.deprecate_resolver(
        session,
        ADMIN,
        canonical_key="ta.sma",
        reason="superseded by v2",
        expected_registry_version=2,
    )
    await session.commit()

    assert result["trust_state"] == str(ResolverTrustState.DEPRECATED)
    with pytest.raises(ResolverNotResolved):
        await resolve_embedded_dependency(
            session,
            parsed_call={"key": "ta.sma", "signature": _SMA_SIG},
            target_runtime=RuntimeAdapter.PINE_V5,
        )


async def test_stale_registry_version_conflicts(session) -> None:
    await _seed_principals(session)
    created = await _create_esp(session)
    await session.commit()

    with pytest.raises(ResolverRegistryConflict):
        await esp_cmd.activate_resolver(
            session,
            ADMIN,
            entity_id=created["entity_id"],
            revision_id=created["revision_id"],
            canonical_key="ta.sma",
            expected_registry_version=99,  # stale
        )


async def test_idempotent_activate_replay_returns_cached(session) -> None:
    await _seed_principals(session)
    created = await _create_esp(session)
    await session.commit()

    first = await esp_cmd.activate_resolver(
        session,
        ADMIN,
        entity_id=created["entity_id"],
        revision_id=created["revision_id"],
        canonical_key="ta.sma",
        expected_registry_version=1,
        idempotency_key="act-k1",
    )
    await session.commit()
    decisions_after_first = await _count(session, ApprovalDecision)

    # Replay with the same key; registry version advanced to 2 so the inside-body
    # check would otherwise conflict — the completed key short-circuits (L2/D3).
    second = await esp_cmd.activate_resolver(
        session,
        ADMIN,
        entity_id=created["entity_id"],
        revision_id=created["revision_id"],
        canonical_key="ta.sma",
        expected_registry_version=1,
        idempotency_key="act-k1",
    )
    await session.commit()

    assert second == first
    assert await _count(session, ApprovalDecision) == decisions_after_first


async def test_soft_delete_preserves_revision_chain(session) -> None:
    await _seed_principals(session)
    created = await _create_esp(session)
    await session.commit()

    root = await pkg_repo.get_package_root(session, created["entity_id"])
    assert root is not None
    head = root.current_revision_id

    await soft_delete_entity(session, ADMIN, entity_id=created["entity_id"], reason="cleanup")
    await session.commit()

    assert root.deletion_state == DeletionState.SOFT_DELETED
    assert await pkg_repo.get_revision(session, created["revision_id"]) is not None
    assert root.current_revision_id == head


async def test_seed_style_ta_resolvers_resolve(session) -> None:
    """A trusted-active TA resolver seeded directly (seed-style) is resolvable."""
    await _seed_principals(session)
    signature = {"params": [{"name": "source", "type": "series"}], "return": "series"}
    _root, _detail, revision = await pkg_repo.create_package(
        session,
        owner_principal_id="user_admin",
        created_by_principal_id="user_admin",
        package_kind=PackageKind.EMBEDDED_SYSTEM,
        input_contract={"resolver_key": "ta.vwap"},
        output_contract={"return": "series"},
        dependency_snapshot={},
        visibility_scope=VisibilityScope.SYSTEM,
        validation_state=PackageValidationState.PASSED,
        approval_state=ApprovalState.APPROVED,
    )
    esp_repo.add_resolver_contract(
        session,
        entity_id=_root.entity_id,
        revision_id=revision.revision_id,
        canonical_key="ta.vwap",
        signature=signature,
        runtime_adapter=RuntimeAdapter.PINE_V5,
    )
    esp_repo.upsert_registry_entry(
        session,
        canonical_key="ta.vwap",
        package_entity_id=_root.entity_id,
        runtime_adapter=RuntimeAdapter.PINE_V5,
        trust_state=ResolverTrustState.TRUSTED_ACTIVE,
        trusted_active_revision_id=revision.revision_id,
        updated_by_principal_id="user_admin",
    )
    await session.commit()

    resolved = await resolve_embedded_dependency(
        session,
        parsed_call={"key": "ta.vwap", "signature": signature},
        target_runtime=RuntimeAdapter.PINE_V5,
    )
    assert resolved["revision_id"] == revision.revision_id

    # Sanity: there is exactly one registry row for the key.
    rows = (
        (
            await session.execute(
                select(EmbeddedResolverRegistry).where(
                    EmbeddedResolverRegistry.canonical_key == "ta.vwap"
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1
