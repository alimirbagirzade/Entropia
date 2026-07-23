"""Stage 2e Create Package + Pre-Check — exercised against a real database.

Auto-skips when no PostgreSQL is reachable (see tests/integration/conftest.py).
Covers the full vertical: create request -> Pre-Check resolves a declared TA call
against a trusted Python ESP resolver (PASSED, pinned revision) -> send (candidate
ready) -> Create Draft Package (root + immutable draft revision) -> Admin approve &
publish (revision approved, package published, approval_decision recorded). Also:
a missing resolver -> BLOCKED scan + Send rejected; description route skips the
dependency gate; C.D.P is idempotent; a non-owner is rejected.
"""

from __future__ import annotations

import pytest
from sqlalchemy import func, select

from entropia.application.commands import create_package as cp_cmd
from entropia.application.queries import create_package as cp_query
from entropia.domain.create_package.enums import (
    CreatePackageState,
    CreationMode,
    PrecheckScanStatus,
    SourceLanguage,
    ValidationRunStatus,
)
from entropia.domain.esp.enums import ResolverTrustState, RuntimeAdapter
from entropia.domain.identity import Actor
from entropia.domain.lifecycle.enums import (
    ApprovalState,
    PackageKind,
    PrincipalType,
    Role,
    VisibilityScope,
)
from entropia.domain.package.enums import PackageValidationState
from entropia.infrastructure.postgres.models import (
    ApprovalDecision,
    AuditEvent,
    DependencyScan,
    PackageRoot,
    Principal,
)
from entropia.infrastructure.postgres.repositories import create_package as cp_repo
from entropia.infrastructure.postgres.repositories import esp as esp_repo
from entropia.infrastructure.postgres.repositories import packages as pkg_repo
from entropia.infrastructure.postgres.repositories import rationale as rationale_repo
from entropia.shared.errors import (
    AccessDeniedError,
    PrecheckBlocked,
    RationaleFamilyNotActive,
    ValidationError,
)

pytestmark = pytest.mark.integration

ADMIN = Actor(principal_id="user_admin", principal_type=PrincipalType.HUMAN, role=Role.ADMIN)
OWNER = Actor(principal_id="user_1", principal_type=PrincipalType.HUMAN, role=Role.USER)
OTHER = Actor(principal_id="user_2", principal_type=PrincipalType.HUMAN, role=Role.USER)

_RSI_SIG = {
    "params": [{"name": "source", "type": "series"}, {"name": "length", "type": "int"}],
    "return": "series",
}
_RSI_DEP = {"key": "ta.rsi", "signature": _RSI_SIG}
_INDICATOR_OUTPUT = {"kind": "directional_signal"}


async def _count(session, model) -> int:
    return int((await session.execute(select(func.count()).select_from(model))).scalar_one())


async def _seed_principals(session) -> None:
    for pid in ("user_admin", "user_1", "user_2"):
        if await session.get(Principal, pid) is None:
            session.add(Principal(principal_id=pid, principal_type=PrincipalType.HUMAN))
    await session.flush()


async def _seed_python_resolver(session, *, key: str = "ta.rsi") -> str:
    """Seed a trusted-active ESP resolver running on the Python adapter."""
    root, _detail, revision = await pkg_repo.create_package(
        session,
        owner_principal_id="user_admin",
        created_by_principal_id="user_admin",
        package_kind=PackageKind.EMBEDDED_SYSTEM,
        input_contract={"resolver_key": key},
        output_contract={"return": "series"},
        dependency_snapshot={},
        visibility_scope=VisibilityScope.SYSTEM,
        validation_state=PackageValidationState.PASSED,
        approval_state=ApprovalState.APPROVED,
    )
    esp_repo.add_resolver_contract(
        session,
        entity_id=root.entity_id,
        revision_id=revision.revision_id,
        canonical_key=key,
        signature=_RSI_SIG,
        runtime_adapter=RuntimeAdapter.PYTHON,
    )
    esp_repo.upsert_registry_entry(
        session,
        canonical_key=key,
        package_entity_id=root.entity_id,
        runtime_adapter=RuntimeAdapter.PYTHON,
        trust_state=ResolverTrustState.TRUSTED_ACTIVE,
        trusted_active_revision_id=revision.revision_id,
        updated_by_principal_id="user_admin",
    )
    return revision.revision_id


async def _seed_family(session) -> str:
    root, _detail, _revision = await rationale_repo.create_family(
        session,
        owner_principal_id="user_admin",
        created_by_principal_id="user_admin",
        display_name="Reversal / Mean Reversion",
        normalized_name="reversal / mean reversion",
        subfamilies=[],
        compatible_output_types=["directional_signal"],
        display_color="#FFD1DC",
        change_note=None,
    )
    return root.entity_id


async def _create_indicator_request(session, *, family_id: str, deps: list[dict]) -> dict:
    return await cp_cmd.create_package_request(
        session,
        OWNER,
        package_type="indicator",
        creation_mode=CreationMode.TRANSLATE_EXISTING_CODE,
        source_language=SourceLanguage.PINESCRIPT,
        other_language_label=None,
        target_runtime=RuntimeAdapter.PYTHON,
        request_body="//@version=5\nindicator('rsi')\nta.rsi(close, 14)",
        output_contract=_INDICATOR_OUTPUT,
        rationale_family_id=family_id,
        declared_dependencies=deps,
        # These plumbing tests do not exercise the mode-aware baseline gate; opt out
        # of the equivalence claim so publish needs no baseline (GAP-07b).
        equivalence_claim=False,
    )


async def test_full_flow_create_precheck_draft_publish(session) -> None:
    await _seed_principals(session)
    resolver_rev = await _seed_python_resolver(session)
    family_id = await _seed_family(session)
    await session.commit()

    created = await _create_indicator_request(session, family_id=family_id, deps=[_RSI_DEP])
    await session.commit()
    request_id = created["request_id"]
    assert created["state"] == str(CreatePackageState.REQUESTED)

    pre = await cp_cmd.run_precheck(session, OWNER, request_id=request_id)
    await session.commit()
    assert pre["status"] == str(PrecheckScanStatus.PASSED)
    assert pre["state"] == str(CreatePackageState.PRECHECK_PASSED)
    # The resolved ref pins the exact ESP revision (never name-only/latest).
    scan = await cp_repo.get_scan(session, pre["scan_id"])
    assert scan is not None
    assert scan.resolved_refs[0]["embedded_revision_id"] == resolver_rev

    sent = await cp_cmd.submit_candidate_generation(session, OWNER, request_id=request_id)
    await session.commit()
    assert sent["state"] == str(CreatePackageState.CANDIDATE_READY)

    draft = await cp_cmd.create_draft_from_candidate(
        session, OWNER, request_id=request_id, expected_candidate_hash=sent["candidate_hash"]
    )
    await session.commit()
    assert draft["package_root_id"] is not None
    assert draft["state"] == str(CreatePackageState.DRAFT_CREATED)

    # F-14: the draft revision carries a real, loadable, executable implementation —
    # a hash without an implementation could never survive validation.
    draft_revision = await pkg_repo.get_revision(session, draft["draft_revision_id"])
    assert draft_revision is not None and draft_revision.implementation is not None
    impl = draft_revision.implementation
    assert impl["executable"] is True and impl["entry_symbol"] == "build_signal_plan"
    loaded: dict = {"__builtins__": {}}
    exec(compile(impl["source"], "<rev>", "exec"), loaded)
    plan = loaded["build_signal_plan"]()
    assert plan["output_kind"] == "directional_signal" and plan["primitives"] == ["ta.rsi"]

    # GAP-07: a draft cannot be approved without a passing validation run.
    validated = await cp_cmd.start_package_validation_run(session, OWNER, request_id=request_id)
    await session.commit()
    assert validated["status"] == str(ValidationRunStatus.PASSED)
    assert validated["state"] == str(CreatePackageState.ELIGIBLE_FOR_APPROVAL)
    # F-14: validation PASSED only because the sandbox loaded + executed this implementation.
    runtime_check = next(c for c in validated["checks"] if c["check"] == "runtime")
    assert runtime_check["status"] == "passed"
    assert runtime_check["artifacts"]["execution_status"] == "executed"

    before_decisions = await _count(session, ApprovalDecision)
    published = await cp_cmd.approve_and_publish(
        session,
        ADMIN,
        request_id=request_id,
        expected_head_revision_id=draft["draft_revision_id"],
    )
    await session.commit()
    assert published["approval_state"] == str(ApprovalState.APPROVED)
    assert published["visibility_scope"] == str(VisibilityScope.PUBLISHED)
    assert await _count(session, ApprovalDecision) == before_decisions + 1

    detail = await pkg_repo.get_package_detail(session, draft["package_root_id"])
    revision = await pkg_repo.get_revision(session, draft["draft_revision_id"])
    assert detail is not None and detail.visibility_scope == VisibilityScope.PUBLISHED
    assert revision is not None and revision.approval_state == ApprovalState.APPROVED
    # The draft pinned the resolved dependency snapshot from the scan.
    assert revision.dependency_snapshot["resolved"][0]["embedded_revision_id"] == resolver_rev


async def test_missing_resolver_blocks_precheck_and_send(session) -> None:
    await _seed_principals(session)
    family_id = await _seed_family(session)
    await session.commit()

    created = await _create_indicator_request(
        session, family_id=family_id, deps=[{"key": "ta.unknown", "signature": _RSI_SIG}]
    )
    await session.commit()
    request_id = created["request_id"]

    pre = await cp_cmd.run_precheck(session, OWNER, request_id=request_id)
    await session.commit()
    assert pre["status"] == str(PrecheckScanStatus.BLOCKED)
    assert pre["state"] == str(CreatePackageState.PRECHECK_BLOCKED)
    assert pre["missing"][0]["call"] == "ta.unknown"

    with pytest.raises(PrecheckBlocked):
        await cp_cmd.submit_candidate_generation(session, OWNER, request_id=request_id)


async def test_description_route_skips_dependency_gate(session) -> None:
    await _seed_principals(session)
    family_id = await _seed_family(session)
    await session.commit()

    created = await cp_cmd.create_package_request(
        session,
        OWNER,
        package_type="condition",
        creation_mode=CreationMode.GENERATE_FROM_DESCRIPTION,
        source_language=None,
        other_language_label=None,
        target_runtime=RuntimeAdapter.PYTHON,
        request_body="True when fast EMA crosses above slow EMA on a closed bar.",
        output_contract={"kind": "boolean_condition"},
        rationale_family_id=family_id,
        declared_dependencies=[],
    )
    await session.commit()
    assert created["state"] == str(CreatePackageState.PRECHECK_NOT_APPLICABLE)

    sent = await cp_cmd.submit_candidate_generation(
        session, OWNER, request_id=created["request_id"]
    )
    await session.commit()
    assert sent["state"] == str(CreatePackageState.CANDIDATE_READY)

    draft = await cp_cmd.create_draft_from_candidate(
        session, OWNER, request_id=created["request_id"]
    )
    await session.commit()
    assert draft["package_root_id"] is not None


async def test_create_draft_is_idempotent(session) -> None:
    await _seed_principals(session)
    await _seed_python_resolver(session)
    family_id = await _seed_family(session)
    await session.commit()

    created = await _create_indicator_request(session, family_id=family_id, deps=[_RSI_DEP])
    await cp_cmd.run_precheck(session, OWNER, request_id=created["request_id"])
    sent = await cp_cmd.submit_candidate_generation(
        session, OWNER, request_id=created["request_id"]
    )
    await session.commit()

    before_packages = await _count(session, PackageRoot)
    first = await cp_cmd.create_draft_from_candidate(
        session, OWNER, request_id=created["request_id"], idempotency_key="cdp-1"
    )
    await session.commit()
    second = await cp_cmd.create_draft_from_candidate(
        session, OWNER, request_id=created["request_id"], idempotency_key="cdp-1"
    )
    await session.commit()

    assert first["package_root_id"] == second["package_root_id"]
    assert first["draft_revision_id"] == second["draft_revision_id"]
    # Exactly one new package root was created across both calls.
    assert await _count(session, PackageRoot) == before_packages + 1
    _ = sent


async def test_non_owner_cannot_run_precheck(session) -> None:
    await _seed_principals(session)
    family_id = await _seed_family(session)
    await session.commit()

    created = await _create_indicator_request(session, family_id=family_id, deps=[])
    await session.commit()

    with pytest.raises(AccessDeniedError):
        await cp_cmd.run_precheck(session, OTHER, request_id=created["request_id"])


async def test_scan_is_immutable_evidence(session) -> None:
    """Re-running Pre-Check appends a new attempt; the old scan is retained."""
    await _seed_principals(session)
    await _seed_python_resolver(session)
    family_id = await _seed_family(session)
    await session.commit()

    created = await _create_indicator_request(session, family_id=family_id, deps=[_RSI_DEP])
    await cp_cmd.run_precheck(session, OWNER, request_id=created["request_id"])
    await cp_cmd.run_precheck(session, OWNER, request_id=created["request_id"])
    await session.commit()

    scans = (
        (
            await session.execute(
                select(DependencyScan).where(
                    DependencyScan.request_entity_id == created["request_id"]
                )
            )
        )
        .scalars()
        .all()
    )
    assert {s.attempt_no for s in scans} == {1, 2}


async def test_request_creation_writes_audit(session) -> None:
    await _seed_principals(session)
    family_id = await _seed_family(session)
    await session.commit()

    before = await _count(session, AuditEvent)
    await _create_indicator_request(session, family_id=family_id, deps=[])
    await session.commit()
    assert await _count(session, AuditEvent) == before + 1


_EMA_DEP = {"key": "ta.ema", "signature": _RSI_SIG}


async def _create_request_with_body(
    session, *, family_id: str, body: str, deps: list[dict]
) -> dict:
    """A code request with a caller-supplied source body (for the source lexer)."""
    return await cp_cmd.create_package_request(
        session,
        OWNER,
        package_type="indicator",
        creation_mode=CreationMode.TRANSLATE_EXISTING_CODE,
        source_language=SourceLanguage.PINESCRIPT,
        other_language_label=None,
        target_runtime=RuntimeAdapter.PYTHON,
        request_body=body,
        output_contract=_INDICATOR_OUTPUT,
        rationale_family_id=family_id,
        declared_dependencies=deps,
        equivalence_claim=False,
    )


async def test_precheck_blocks_undeclared_source_call(session) -> None:
    """PC-06: a real ``ta.rsi`` call the request never declared must Block."""
    await _seed_principals(session)
    await _seed_python_resolver(session, key="ta.rsi")
    family_id = await _seed_family(session)
    await session.commit()

    created = await _create_request_with_body(
        session,
        family_id=family_id,
        body="//@version=5\nx = ta.rsi(close, 14)",
        deps=[],
    )
    await session.commit()

    pre = await cp_cmd.run_precheck(session, OWNER, request_id=created["request_id"])
    await session.commit()
    assert pre["status"] == str(PrecheckScanStatus.BLOCKED)
    assert pre["state"] == str(CreatePackageState.PRECHECK_BLOCKED)
    codes = {m["code"] for m in pre["missing"]}
    assert "UNDECLARED_SOURCE_DEPENDENCY" in codes
    assert any(m["call"] == "ta.rsi" for m in pre["missing"])
    scan = await cp_repo.get_scan(session, pre["scan_id"])
    assert scan is not None
    assert scan.detected_calls == ["ta.rsi"]

    with pytest.raises(PrecheckBlocked):
        await cp_cmd.submit_candidate_generation(session, OWNER, request_id=created["request_id"])


async def test_precheck_comment_only_call_is_not_a_dependency(session) -> None:
    """PC-06: ``ta.rsi`` only inside a comment creates no dependency -> PASSED."""
    await _seed_principals(session)
    family_id = await _seed_family(session)
    await session.commit()

    created = await _create_request_with_body(
        session,
        family_id=family_id,
        body="//@version=5\n// legacy note: ta.rsi(close, 14)\nplot(close)",
        deps=[],
    )
    await session.commit()

    pre = await cp_cmd.run_precheck(session, OWNER, request_id=created["request_id"])
    await session.commit()
    assert pre["status"] == str(PrecheckScanStatus.PASSED)
    assert pre["missing"] == []
    assert pre["warnings"] == []
    scan = await cp_repo.get_scan(session, pre["scan_id"])
    assert scan is not None
    assert scan.detected_calls == []


async def test_precheck_over_declared_dependency_is_a_warning(session) -> None:
    """A declared call the source never invokes is a non-fatal Warning (PASSED)."""
    await _seed_principals(session)
    await _seed_python_resolver(session, key="ta.rsi")
    await _seed_python_resolver(session, key="ta.ema")
    family_id = await _seed_family(session)
    await session.commit()

    created = await _create_request_with_body(
        session,
        family_id=family_id,
        body="//@version=5\nx = ta.rsi(close, 14)",
        deps=[_RSI_DEP, _EMA_DEP],
    )
    await session.commit()

    pre = await cp_cmd.run_precheck(session, OWNER, request_id=created["request_id"])
    await session.commit()
    assert pre["status"] == str(PrecheckScanStatus.PASSED)
    assert pre["missing"] == []
    assert [w["call"] for w in pre["warnings"]] == ["ta.ema"]
    assert pre["warnings"][0]["code"] == "DECLARED_NOT_IN_SOURCE"
    scan = await cp_repo.get_scan(session, pre["scan_id"])
    assert scan is not None
    assert scan.source_warnings[0]["call"] == "ta.ema"
    # A warning does not block Send.
    sent = await cp_cmd.submit_candidate_generation(
        session, OWNER, request_id=created["request_id"]
    )
    assert sent["state"] == str(CreatePackageState.CANDIDATE_READY)


async def _seed_family_named(session, *, display_name: str, normalized_name: str) -> str:
    root, _detail, _revision = await rationale_repo.create_family(
        session,
        owner_principal_id="user_admin",
        created_by_principal_id="user_admin",
        display_name=display_name,
        normalized_name=normalized_name,
        subfamilies=[],
        compatible_output_types=["directional_signal"],
        display_color="#CDE7FF",
        change_note=None,
    )
    return root.entity_id


async def _seed_indicator_package(session) -> tuple[str, str]:
    """Seed a published Indicator package (root + head revision) to link against."""
    root, _detail, revision = await pkg_repo.create_package(
        session,
        owner_principal_id="user_admin",
        created_by_principal_id="user_admin",
        package_kind=PackageKind.INDICATOR,
        input_contract={"source_kind": "code"},
        output_contract={"kind": "directional_signal"},
        dependency_snapshot={},
        visibility_scope=VisibilityScope.PUBLISHED,
        validation_state=PackageValidationState.PASSED,
        approval_state=ApprovalState.APPROVED,
    )
    return root.entity_id, revision.revision_id


async def _create_condition_request(session, *, family_id, compatible=None, linked=None) -> dict:
    return await cp_cmd.create_package_request(
        session,
        OWNER,
        package_type="condition",
        creation_mode=CreationMode.GENERATE_FROM_DESCRIPTION,
        source_language=None,
        other_language_label=None,
        target_runtime=RuntimeAdapter.PYTHON,
        request_body="A reversal condition on the linked indicator.",
        output_contract={"kind": "boolean_condition"},
        rationale_family_id=family_id,
        compatible_rationale_family_ids=compatible,
        linked_indicator=linked,
        equivalence_claim=False,
    )


async def test_compatible_family_and_linked_indicator_round_trip(session) -> None:
    """P-05: both compatibility declarations persist and survive save→reload.

    The Compatible Family list is deduped and the assigned ("Same") family dropped;
    the Explicit Indicator Link is pinned to the indicator root+revision. The GET
    projection returns exactly what was saved (audit acceptance).
    """
    await _seed_principals(session)
    family_id = await _seed_family(session)
    compat_id = await _seed_family_named(
        session, display_name="Trend / Momentum", normalized_name="trend / momentum"
    )
    indicator_root, indicator_rev = await _seed_indicator_package(session)
    await session.commit()

    created = await _create_condition_request(
        session,
        family_id=family_id,
        # The assigned family + a duplicate are dropped; only the distinct OTHER family stays.
        compatible=[compat_id, family_id, compat_id],
        linked={
            "linked_indicator_package_root_id": indicator_root,
            "linked_indicator_package_revision_id": indicator_rev,
        },
    )
    await session.commit()
    assert created["compatible_rationale_family_ids"] == [compat_id]
    assert created["linked_indicator"] == {
        "linked_indicator_package_root_id": indicator_root,
        "linked_indicator_package_revision_id": indicator_rev,
    }

    # Save→reload: the immutable request projection returns the same pins.
    projection = await cp_query.get_package_request(
        session, OWNER, request_id=created["request_id"]
    )
    assert projection["compatible_rationale_family_ids"] == [compat_id]
    assert projection["linked_indicator"] == {
        "linked_indicator_package_root_id": indicator_root,
        "linked_indicator_package_revision_id": indicator_rev,
    }


async def test_compatible_family_must_be_active(session) -> None:
    """A Compatible Family that is not an ACTIVE family is rejected (no auto-create)."""
    await _seed_principals(session)
    family_id = await _seed_family(session)
    await session.commit()

    with pytest.raises(RationaleFamilyNotActive):
        await _create_condition_request(
            session, family_id=family_id, compatible=["fam_does_not_exist"]
        )


async def test_linked_indicator_rejected_for_non_condition(session) -> None:
    """The Explicit Indicator Link is Condition-only (doc 06 §4)."""
    await _seed_principals(session)
    family_id = await _seed_family(session)
    indicator_root, indicator_rev = await _seed_indicator_package(session)
    await session.commit()

    with pytest.raises(ValidationError):
        await _create_indicator_request_with_link(
            session,
            family_id=family_id,
            linked={
                "linked_indicator_package_root_id": indicator_root,
                "linked_indicator_package_revision_id": indicator_rev,
            },
        )


async def test_linked_indicator_unknown_revision_rejected(session) -> None:
    """Name-only / dangling links are rejected — the revision must belong to the root."""
    await _seed_principals(session)
    family_id = await _seed_family(session)
    indicator_root, _rev = await _seed_indicator_package(session)
    await session.commit()

    with pytest.raises(ValidationError):
        await _create_condition_request(
            session,
            family_id=family_id,
            linked={
                "linked_indicator_package_root_id": indicator_root,
                "linked_indicator_package_revision_id": "rev_not_real",
            },
        )


async def _create_indicator_request_with_link(session, *, family_id, linked) -> dict:
    return await cp_cmd.create_package_request(
        session,
        OWNER,
        package_type="indicator",
        creation_mode=CreationMode.GENERATE_FROM_DESCRIPTION,
        source_language=None,
        other_language_label=None,
        target_runtime=RuntimeAdapter.PYTHON,
        request_body="An indicator that should not carry an indicator link.",
        output_contract=_INDICATOR_OUTPUT,
        rationale_family_id=family_id,
        linked_indicator=linked,
        equivalence_claim=False,
    )
