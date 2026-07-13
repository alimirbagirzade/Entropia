"""GAP-07 Package validation-evidence plane + evidence-gated approval.

Auto-skips when no PostgreSQL is reachable (tests/integration/conftest.py). Covers:
a draft cannot be published without a passing validation run (VALIDATION_REQUIRED);
a passed run reaches eligible_for_approval and unlocks approval; a drifted dependency
fails validation -> revision_required -> Request Revision reopens the loop; validation
evidence is immutable (per-attempt) and goes stale when the candidate changes.
"""

from __future__ import annotations

import pytest
from sqlalchemy import func, select

from entropia.application.commands import create_package as cp_cmd
from entropia.domain.create_package.enums import (
    CreatePackageState,
    CreationMode,
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
from entropia.infrastructure.postgres.models import PackageValidationRun, Principal
from entropia.infrastructure.postgres.repositories import create_package as cp_repo
from entropia.infrastructure.postgres.repositories import esp as esp_repo
from entropia.infrastructure.postgres.repositories import packages as pkg_repo
from entropia.infrastructure.postgres.repositories import rationale as rationale_repo
from entropia.shared.errors import ValidationRequired, ValidationStale

pytestmark = pytest.mark.integration

ADMIN = Actor(principal_id="user_admin", principal_type=PrincipalType.HUMAN, role=Role.ADMIN)
OWNER = Actor(principal_id="user_1", principal_type=PrincipalType.HUMAN, role=Role.USER)

_RSI_SIG = {
    "params": [{"name": "source", "type": "series"}, {"name": "length", "type": "int"}],
    "return": "series",
}
_RSI_DEP = {"key": "ta.rsi", "signature": _RSI_SIG}
_INDICATOR_OUTPUT = {"kind": "directional_signal"}


async def _count(session, model) -> int:
    return int((await session.execute(select(func.count()).select_from(model))).scalar_one())


async def _seed_principals(session) -> None:
    for pid in ("user_admin", "user_1"):
        if await session.get(Principal, pid) is None:
            session.add(Principal(principal_id=pid, principal_type=PrincipalType.HUMAN))
    await session.flush()


async def _seed_python_resolver(session, *, key: str = "ta.rsi") -> str:
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


async def _drive_to_draft(session, *, family_id: str) -> str:
    created = await cp_cmd.create_package_request(
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
        declared_dependencies=[_RSI_DEP],
    )
    request_id = created["request_id"]
    await cp_cmd.run_precheck(session, OWNER, request_id=request_id)
    sent = await cp_cmd.submit_candidate_generation(session, OWNER, request_id=request_id)
    await cp_cmd.create_draft_from_candidate(
        session, OWNER, request_id=request_id, expected_candidate_hash=sent["candidate_hash"]
    )
    await session.flush()
    return request_id


async def test_approve_without_validation_is_rejected(session) -> None:
    await _seed_principals(session)
    await _seed_python_resolver(session)
    family_id = await _seed_family(session)
    request_id = await _drive_to_draft(session, family_id=family_id)
    await session.commit()

    # A fresh draft has no validation evidence -> approval is refused (GAP-07).
    with pytest.raises(ValidationRequired):
        await cp_cmd.approve_and_publish(session, ADMIN, request_id=request_id)


async def test_validation_pass_enables_approval(session) -> None:
    await _seed_principals(session)
    await _seed_python_resolver(session)
    family_id = await _seed_family(session)
    request_id = await _drive_to_draft(session, family_id=family_id)
    await session.commit()

    validated = await cp_cmd.start_package_validation_run(session, OWNER, request_id=request_id)
    await session.commit()
    assert validated["status"] == str(ValidationRunStatus.PASSED)
    assert validated["state"] == str(CreatePackageState.ELIGIBLE_FOR_APPROVAL)
    # Evidence enumerates the executed checks (never a cosmetic label).
    statuses = {c["check"]: c["status"] for c in validated["checks"]}
    assert statuses["output_structure"] == "passed"
    assert statuses["dependency_health"] == "passed"
    assert statuses["syntax"] == "not_executed"

    published = await cp_cmd.approve_and_publish(session, ADMIN, request_id=request_id)
    await session.commit()
    assert published["approval_state"] == str(ApprovalState.APPROVED)
    assert published["visibility_scope"] == str(VisibilityScope.PUBLISHED)


async def test_validation_failure_routes_to_revision_and_reopens(session) -> None:
    await _seed_principals(session)
    await _seed_python_resolver(session)
    family_id = await _seed_family(session)
    request_id = await _drive_to_draft(session, family_id=family_id)
    await session.commit()

    # Deprecate the pinned resolver so re-resolution drifts -> dependency_health fails.
    entry = await esp_repo.get_registry_by_key(session, "ta.rsi")
    assert entry is not None
    esp_repo.set_trust_state(
        entry, trust_state=ResolverTrustState.DEPRECATED, updated_by_principal_id="user_admin"
    )
    await session.commit()

    failed = await cp_cmd.start_package_validation_run(session, OWNER, request_id=request_id)
    await session.commit()
    assert failed["status"] == str(ValidationRunStatus.FAILED)
    assert failed["state"] == str(CreatePackageState.REVISION_REQUIRED)

    # A failed draft cannot be approved.
    with pytest.raises(ValidationRequired):
        await cp_cmd.approve_and_publish(session, ADMIN, request_id=request_id)

    # Request Revision reopens the loop with a fresh candidate.
    revised = await cp_cmd.request_package_revision(session, OWNER, request_id=request_id)
    await session.commit()
    assert revised["state"] == str(CreatePackageState.CANDIDATE_READY)

    # A second draft + validation run appends immutable evidence (attempt_no 2).
    await cp_cmd.create_draft_from_candidate(session, OWNER, request_id=request_id)
    await session.commit()
    await cp_cmd.start_package_validation_run(session, OWNER, request_id=request_id)
    await session.commit()
    runs = (
        (
            await session.execute(
                select(PackageValidationRun).where(
                    PackageValidationRun.request_entity_id == request_id
                )
            )
        )
        .scalars()
        .all()
    )
    assert {r.attempt_no for r in runs} == {1, 2}


async def test_stale_evidence_blocks_approve(session) -> None:
    await _seed_principals(session)
    await _seed_python_resolver(session)
    family_id = await _seed_family(session)
    request_id = await _drive_to_draft(session, family_id=family_id)
    await session.commit()

    await cp_cmd.start_package_validation_run(session, OWNER, request_id=request_id)
    await session.commit()

    # Simulate the candidate moving on after the run certified the prior hash: the
    # evidence no longer matches the draft's candidate and approval must refuse it.
    detail = await cp_repo.get_request_detail(session, request_id)
    assert detail is not None
    detail.candidate_hash = "sha256:regenerated-after-validation"
    await session.commit()

    with pytest.raises(ValidationStale):
        await cp_cmd.approve_and_publish(session, ADMIN, request_id=request_id)


async def test_validation_writes_audit_event(session) -> None:
    from entropia.infrastructure.postgres.models import AuditEvent

    await _seed_principals(session)
    await _seed_python_resolver(session)
    family_id = await _seed_family(session)
    request_id = await _drive_to_draft(session, family_id=family_id)
    await session.commit()

    before = await _count(session, AuditEvent)
    await cp_cmd.start_package_validation_run(session, OWNER, request_id=request_id)
    await session.commit()
    assert await _count(session, AuditEvent) == before + 1
