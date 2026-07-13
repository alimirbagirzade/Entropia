"""Stage 2c ESP acceptance (+ post-V1 R8 validation-run) — exercised against a real DB.

Auto-skips when no PostgreSQL is reachable (see tests/integration/conftest.py).
Covers: create ESP package (+1 audit & +1 outbox, CANDIDATE registry row); the R8
validation-run (``run_resolver_validation`` executes the stored test-vectors ->
``validation_state=passed`` + an immutable run row + ``esp.validation.completed``
audit); the activation gate now requires a PASSED run (activating a revision that has
evidence but has not passed -> RESOLVER_VALIDATION_REQUIRED; no/empty evidence ->
RESOLVER_EVIDENCE_REQUIRED); activate (CANDIDATE -> TRUSTED_ACTIVE, approval_decision
recorded, revision APPROVED) only after a passed run; deprecate; resolve returns the
exact revision only once trusted_active + validation passed + approved; optimistic/stale
registry version -> 409; idempotent activate/validate replay returns the cached result;
non-owner validation is denied; soft-delete preserves the revision chain; and seed-style
TA resolvers are resolvable.
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
    EmbeddedResolverValidationRun,
    OutboxEvent,
    Principal,
)
from entropia.infrastructure.postgres.repositories import esp as esp_repo
from entropia.infrastructure.postgres.repositories import packages as pkg_repo
from entropia.shared.errors import (
    AccessDeniedError,
    ResolverAdapterIncompatible,
    ResolverEvidenceRequired,
    ResolverNotResolved,
    ResolverRegistryConflict,
    ResolverSignatureMismatch,
    ResolverValidationRequired,
)

pytestmark = pytest.mark.integration

ADMIN = Actor(principal_id="user_admin", principal_type=PrincipalType.HUMAN, role=Role.ADMIN)
OWNER = Actor(principal_id="user_1", principal_type=PrincipalType.HUMAN, role=Role.USER)

_SMA_SIG = {
    "params": [{"name": "source", "type": "series"}, {"name": "length", "type": "int"}],
    "return": "series",
}

# Executable test-vector evidence (R8): a real ``ta.sma`` len-3 vector whose expected
# column matches the engine compute, so ``run_resolver_validation`` sets
# ``validation_state=passed`` and an Admin may then activate. SMA(3) over [1,2,3,4,5] is
# [None, None, 2, 3, 4].
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

# Evidence whose vector does NOT match the compute -> the validation-run FAILS, so
# activation is blocked with RESOLVER_VALIDATION_REQUIRED (R8).
_FAILING_EVIDENCE = {
    "test_vectors": [{"length": 3, "close": [1, 2, 3, 4, 5], "expected": [None, None, 2, 3, 99]}]
}


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


async def _validate(session, created: dict, *, actor: Actor = OWNER, **kw) -> dict:
    """Run the R8 validation-run for a created resolver (owner-or-Admin)."""
    return await esp_cmd.run_resolver_validation(
        session,
        actor,
        entity_id=created["entity_id"],
        revision_id=created["revision_id"],
        **kw,
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
    await _validate(session, created)  # R8: the test-vectors must pass before activation
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
    # The validation-run stamped PASSED (R8); activation then records the Admin's APPROVAL
    # on top of it (it never fabricates the pass).
    assert revision.validation_state == PackageValidationState.PASSED
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


async def test_validation_run_persists_row_and_passes(session) -> None:
    """R8: run_resolver_validation executes the vectors -> passed + an immutable run row
    + an esp.validation.completed audit."""
    await _seed_principals(session)
    created = await _create_esp(session)
    await session.commit()

    before_runs = await _count(session, EmbeddedResolverValidationRun)
    before_audit = await _count(session, AuditEvent)

    result = await _validate(session, created)
    await session.commit()

    assert result["validation_state"] == str(PackageValidationState.PASSED)
    assert result["vectors_run"] == 1
    assert await _count(session, EmbeddedResolverValidationRun) == before_runs + 1
    assert await _count(session, AuditEvent) == before_audit + 1

    revision = await pkg_repo.get_revision(session, created["revision_id"])
    assert revision is not None
    assert revision.validation_state == PackageValidationState.PASSED
    run = await esp_repo.get_latest_validation_run(session, created["revision_id"])
    assert run is not None
    assert run.status == PackageValidationState.PASSED
    assert run.validator_version


async def test_activation_requires_passed_validation_even_with_evidence(session) -> None:
    """The core R8 fix: evidence PRESENCE is no longer enough — a resolver that has never
    passed a validation-run cannot be activated (doc 09 §4.3 step 5)."""
    await _seed_principals(session)
    created = await _create_esp(session)  # carries real evidence but is NOT validated
    await session.commit()

    with pytest.raises(ResolverValidationRequired):
        await esp_cmd.activate_resolver(
            session,
            ADMIN,
            entity_id=created["entity_id"],
            revision_id=created["revision_id"],
            canonical_key="ta.sma",
            expected_registry_version=1,
        )

    entry = await esp_repo.get_registry_by_key(session, "ta.sma")
    assert entry is not None
    assert entry.trust_state == ResolverTrustState.CANDIDATE  # untouched


async def test_activation_blocked_when_validation_failed(session) -> None:
    """A validation-run over mismatched vectors -> failed; activation stays blocked."""
    await _seed_principals(session)
    created = await _create_esp(session, evidence=_FAILING_EVIDENCE)
    result = await _validate(session, created)
    await session.commit()

    assert result["validation_state"] == str(PackageValidationState.FAILED)
    with pytest.raises(ResolverValidationRequired):
        await esp_cmd.activate_resolver(
            session,
            ADMIN,
            entity_id=created["entity_id"],
            revision_id=created["revision_id"],
            canonical_key="ta.sma",
            expected_registry_version=1,
        )


async def test_validation_by_non_owner_denied(session) -> None:
    """Validation writes evidence + moves validation_state -> a non-owner, non-Admin actor
    is denied (doc 09 §5 owner/Admin evidence collection)."""
    await _seed_principals(session)
    created = await _create_esp(session)
    await session.commit()

    other = Actor(principal_id="user_2", principal_type=PrincipalType.HUMAN, role=Role.USER)
    with pytest.raises(AccessDeniedError):
        await _validate(session, created, actor=other)


async def test_idempotent_validation_replay_returns_cached(session) -> None:
    await _seed_principals(session)
    created = await _create_esp(session)
    await session.commit()

    first = await _validate(session, created, idempotency_key="val-k1")
    await session.commit()
    runs_after_first = await _count(session, EmbeddedResolverValidationRun)

    second = await _validate(session, created, idempotency_key="val-k1")
    await session.commit()

    assert second == first
    assert await _count(session, EmbeddedResolverValidationRun) == runs_after_first


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

    # A passed validation-run alone does NOT make it resolvable — it is still only a
    # CANDIDATE (validation and registry trust are separate facets, doc 09 §11.2).
    validated = await _validate(session, created)
    await session.commit()
    assert validated["validation_state"] == str(PackageValidationState.PASSED)
    with pytest.raises(ResolverNotResolved):
        await resolve_embedded_dependency(
            session,
            parsed_call={"key": "ta.sma", "signature": _SMA_SIG},
            target_runtime=RuntimeAdapter.PINE_V5,
        )

    # Admin activation (now permitted because validation passed) trusts the revision.
    await esp_cmd.activate_resolver(
        session,
        ADMIN,
        entity_id=created["entity_id"],
        revision_id=created["revision_id"],
        canonical_key="ta.sma",
        expected_registry_version=1,
    )
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
    await _validate(session, created)
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
    await _validate(session, created)
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
    await _validate(session, created)
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
