"""O-09 — the Approve Package "dependencies active" precondition (doc 06 §7).

Auto-skips when no PostgreSQL is reachable (see tests/integration/conftest.py).

Doc 06 §7 requires an approval to hold *"current validation eligible; mode-aware
baseline gate satisfied; dependencies active"*, and lists DEPENDENCY_UNRESOLVED
among its errors. Pre-Check pins the resolver refs, but Pre-Check and Approve are
separate human steps: these tests drive a request all the way to
``eligible_for_approval`` and then move the registry underneath it, so the window
between the two steps is exercised for real rather than asserted about.

Covered: a resolver deprecated after Pre-Check blocks the approval and leaves the
draft intact; a pinned ESP revision that loses its approval blocks it too; an
untouched trusted-active resolver still publishes.
"""

from __future__ import annotations

import pytest
from sqlalchemy import func, select

from entropia.application.commands import create_package as cp_cmd
from entropia.application.commands import esp as esp_cmd
from entropia.application.jobs import create_package as cp_jobs
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
from entropia.infrastructure.postgres.models import ApprovalDecision, Principal
from entropia.infrastructure.postgres.repositories import esp as esp_repo
from entropia.infrastructure.postgres.repositories import packages as pkg_repo
from entropia.infrastructure.postgres.repositories import rationale as rationale_repo
from entropia.shared.errors import DependencyUnresolved

pytestmark = pytest.mark.integration

ADMIN = Actor(principal_id="user_admin", principal_type=PrincipalType.HUMAN, role=Role.ADMIN)
OWNER = Actor(principal_id="user_1", principal_type=PrincipalType.HUMAN, role=Role.USER)

_RSI_KEY = "ta.rsi"
_RSI_SIG = {
    "params": [{"name": "source", "type": "series"}, {"name": "length", "type": "int"}],
    "return": "series",
}
_RSI_DEP = {"key": _RSI_KEY, "signature": _RSI_SIG}
_INDICATOR_OUTPUT = {"kind": "directional_signal"}


async def _count(session, model) -> int:
    return int((await session.execute(select(func.count()).select_from(model))).scalar_one())


async def _seed_principals(session) -> None:
    for pid in ("user_admin", "user_1"):
        if await session.get(Principal, pid) is None:
            session.add(Principal(principal_id=pid, principal_type=PrincipalType.HUMAN))
    await session.flush()


async def _seed_python_resolver(session) -> str:
    """Seed a trusted-active ESP resolver on the Python adapter; return its revision id."""
    root, _detail, revision = await pkg_repo.create_package(
        session,
        owner_principal_id="user_admin",
        created_by_principal_id="user_admin",
        package_kind=PackageKind.EMBEDDED_SYSTEM,
        input_contract={"resolver_key": _RSI_KEY},
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
        canonical_key=_RSI_KEY,
        signature=_RSI_SIG,
        runtime_adapter=RuntimeAdapter.PYTHON,
    )
    esp_repo.upsert_registry_entry(
        session,
        canonical_key=_RSI_KEY,
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


async def _drive_to_eligible(session) -> tuple[str, str, str]:
    """Create -> Pre-Check -> Send -> Draft -> Validation PASSED.

    Returns ``(request_id, draft_revision_id, resolver_revision_id)`` with the request
    sitting in ``eligible_for_approval`` — the exact state Approve Package acts on.
    """
    await _seed_principals(session)
    resolver_revision_id = await _seed_python_resolver(session)
    family_id = await _seed_family(session)
    await session.commit()

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
        # The mode-aware baseline gate is a different precondition; opt out so the
        # approval turns on the dependency gate alone.
        equivalence_claim=False,
    )
    await session.commit()
    request_id = created["request_id"]

    queued = await cp_cmd.run_precheck(session, OWNER, request_id=request_id)
    await cp_jobs.run_create_package_job(session, queued["job_id"])
    await session.commit()

    admitted = await cp_cmd.submit_candidate_generation(session, OWNER, request_id=request_id)
    sent = await cp_jobs.run_create_package_job(session, admitted["job_id"])
    await session.commit()

    draft = await cp_cmd.create_draft_from_candidate(
        session, OWNER, request_id=request_id, expected_candidate_hash=sent["candidate_hash"]
    )
    await session.commit()

    admitted = await cp_cmd.start_package_validation_run(session, OWNER, request_id=request_id)
    validated = await cp_jobs.run_create_package_job(session, admitted["job_id"])
    await session.commit()
    assert validated["status"] == str(ValidationRunStatus.PASSED)
    assert validated["state"] == str(CreatePackageState.ELIGIBLE_FOR_APPROVAL)

    # The draft pinned the exact resolver revision Pre-Check resolved.
    revision = await pkg_repo.get_revision(session, draft["draft_revision_id"])
    assert revision is not None
    pinned = revision.dependency_snapshot["resolved"][0]
    assert pinned["embedded_revision_id"] == resolver_revision_id

    return request_id, draft["draft_revision_id"], resolver_revision_id


async def test_resolver_deprecated_after_precheck_blocks_approval(session) -> None:
    """The Pre-Check -> Approve window: a deprecated resolver fails the approval closed."""
    request_id, draft_revision_id, _resolver_revision_id = await _drive_to_eligible(session)
    before_decisions = await _count(session, ApprovalDecision)

    await esp_cmd.deprecate_resolver(
        session,
        ADMIN,
        canonical_key=_RSI_KEY,
        reason="Superseded by a corrected implementation.",
    )
    await session.commit()

    with pytest.raises(DependencyUnresolved) as excinfo:
        await cp_cmd.approve_and_publish(
            session, ADMIN, request_id=request_id, expected_head_revision_id=draft_revision_id
        )
    await session.rollback()

    error = excinfo.value
    assert error.code == "DEPENDENCY_UNRESOLVED"
    assert error.details == [
        {
            "canonical_key": _RSI_KEY,
            "embedded_revision_id": error.details[0]["embedded_revision_id"],
            "issue": "resolver_not_active",
        }
    ]
    assert error.scope_id == draft_revision_id
    assert error.field_path == "dependency_snapshot.resolved"

    # Nothing was published and the draft survives for repair (doc 06 §7).
    revision = await pkg_repo.get_revision(session, draft_revision_id)
    assert revision is not None and revision.approval_state == ApprovalState.DRAFT
    detail = await pkg_repo.get_package_detail(session, revision.entity_id)
    assert detail is not None and detail.visibility_scope == VisibilityScope.PRIVATE
    # The deprecation itself records a decision; the approval must not add one.
    assert await _count(session, ApprovalDecision) == before_decisions + 1


async def test_unapproved_pinned_esp_revision_blocks_approval(session) -> None:
    """The key stays trusted, but the pinned revision lost its approval evidence."""
    request_id, draft_revision_id, resolver_revision_id = await _drive_to_eligible(session)

    resolver_revision = await pkg_repo.get_revision(session, resolver_revision_id)
    assert resolver_revision is not None
    resolver_revision.approval_state = ApprovalState.REJECTED
    await session.commit()

    with pytest.raises(DependencyUnresolved) as excinfo:
        await cp_cmd.approve_and_publish(
            session, ADMIN, request_id=request_id, expected_head_revision_id=draft_revision_id
        )
    await session.rollback()

    assert excinfo.value.details[0]["issue"] == "not_approved"
    revision = await pkg_repo.get_revision(session, draft_revision_id)
    assert revision is not None and revision.approval_state == ApprovalState.DRAFT


async def test_still_trusted_resolver_publishes(session) -> None:
    """The control case: an untouched trusted-active pin approves and publishes."""
    request_id, draft_revision_id, _resolver_revision_id = await _drive_to_eligible(session)

    published = await cp_cmd.approve_and_publish(
        session, ADMIN, request_id=request_id, expected_head_revision_id=draft_revision_id
    )
    await session.commit()

    assert published["approval_state"] == str(ApprovalState.APPROVED)
    assert published["visibility_scope"] == str(VisibilityScope.PUBLISHED)
    revision = await pkg_repo.get_revision(session, draft_revision_id)
    assert revision is not None and revision.approval_state == ApprovalState.APPROVED
