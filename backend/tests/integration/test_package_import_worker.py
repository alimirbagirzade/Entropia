"""S3 slice (b/c) — package import command + worker end-to-end.

Drives submit_package_import (the 202 command) then runs the worker body in-session
(no broker needed) and asserts the reverse-of-Export outcomes: a clean manifest -> a
DRAFT root with origin provenance; an unresolved dependency -> a BLOCKED, never-
executable FAILED-validation root + diagnostics; a malformed manifest -> failed with no
package; idempotent replay -> the same job. Auto-skips without PostgreSQL.
"""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from entropia.application.commands import package_import as import_cmd
from entropia.application.jobs.package_import import run_import
from entropia.application.queries import package_import as import_query
from entropia.domain.create_package.enums import PackageImportStatus
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
    PackageImportJob,
    PackageRevision,
    PackageRoot,
    Principal,
)
from entropia.infrastructure.postgres.repositories import esp as esp_repo
from entropia.infrastructure.postgres.repositories import package_import as import_repo
from entropia.infrastructure.postgres.repositories import packages as pkg_repo
from entropia.shared.errors import PackageImportJobNotFound, PackageImportManifestInvalid

pytestmark = pytest.mark.asyncio

OWNER = Actor(principal_id="user_1", principal_type=PrincipalType.HUMAN, role=Role.USER)
OTHER = Actor(principal_id="user_2", principal_type=PrincipalType.HUMAN, role=Role.USER)

_RSI_SIG = {
    "params": [{"name": "source", "type": "series"}, {"name": "length", "type": "int"}],
    "return": "series",
}


async def _seed_principals(session: AsyncSession) -> None:
    for pid in ("user_admin", "user_1", "user_2"):
        if await session.get(Principal, pid) is None:
            session.add(Principal(principal_id=pid, principal_type=PrincipalType.HUMAN))
    await session.flush()


async def _seed_rsi_resolver(session: AsyncSession) -> str:
    root, _detail, revision = await pkg_repo.create_package(
        session,
        owner_principal_id="user_admin",
        created_by_principal_id="user_admin",
        package_kind=PackageKind.EMBEDDED_SYSTEM,
        input_contract={"resolver_key": "ta.rsi"},
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
        canonical_key="ta.rsi",
        signature=_RSI_SIG,
        runtime_adapter=RuntimeAdapter.PYTHON,
    )
    esp_repo.upsert_registry_entry(
        session,
        canonical_key="ta.rsi",
        package_entity_id=root.entity_id,
        runtime_adapter=RuntimeAdapter.PYTHON,
        trust_state=ResolverTrustState.TRUSTED_ACTIVE,
        trusted_active_revision_id=revision.revision_id,
        updated_by_principal_id="user_admin",
    )
    await session.flush()
    return revision.revision_id


def _manifest(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "package_root_id": "pkg_origin",
        "revision_id": "pkgrev_origin",
        "revision_no": 1,
        "package_kind": "indicator",
        "name": "Imported RSI",
        "input_contract": {"name": "Imported RSI"},
        "output_contract": {"kind": "directional_signal"},
        "dependency_snapshot": {"resolved": []},
        "rationale_family_snapshot": None,
        "validation_state": "passed",
        "approval_state": "approved",
        "content_hash": "c" * 64,
        "derived_from_revision_id": None,
    }
    base.update(overrides)
    return base


async def _count_roots(session: AsyncSession) -> int:
    return int((await session.execute(select(func.count()).select_from(PackageRoot))).scalar_one())


async def _run(session: AsyncSession, manifest: dict[str, Any], *, actor: Actor = OWNER) -> str:
    submitted = await import_cmd.submit_package_import(session, actor, manifest=manifest)
    assert submitted["status"] == "queued"
    await run_import(session, submitted["job_id"])
    return submitted["import_job_id"]


async def test_clean_manifest_creates_draft_root_with_provenance(session: AsyncSession) -> None:
    await _seed_principals(session)
    before = await _count_roots(session)
    import_job_id = await _run(session, _manifest())

    row = await import_repo.get_import_job(session, import_job_id)
    assert row is not None
    assert row.status is PackageImportStatus.SUCCEEDED
    assert row.result_package_root_id is not None
    assert await _count_roots(session) == before + 1

    root = await session.get(PackageRoot, row.result_package_root_id)
    assert root is not None
    assert root.origin_package_id == "pkg_origin"
    revision = (
        await session.execute(
            select(PackageRevision).where(PackageRevision.entity_id == root.entity_id)
        )
    ).scalar_one()
    # A clean import is a DRAFT PENDING package — never auto-approved / auto-validated.
    assert revision.validation_state is PackageValidationState.PENDING
    assert revision.approval_state is ApprovalState.DRAFT


async def test_resolvable_dependency_repins_to_local_registry(session: AsyncSession) -> None:
    await _seed_principals(session)
    local_rev = await _seed_rsi_resolver(session)
    manifest = _manifest(
        dependency_snapshot={"resolved": [{"canonical_key": "ta.rsi", "call": "ta.rsi"}]}
    )
    import_job_id = await _run(session, manifest)

    row = await import_repo.get_import_job(session, import_job_id)
    assert row is not None
    assert row.status is PackageImportStatus.SUCCEEDED
    root = await session.get(PackageRoot, row.result_package_root_id)
    assert root is not None
    revision = (
        await session.execute(
            select(PackageRevision).where(PackageRevision.entity_id == root.entity_id)
        )
    ).scalar_one()
    resolved = revision.dependency_snapshot["resolved"]
    assert len(resolved) == 1
    # re-pinned to the LOCAL revision (P4/L5), not the foreign one.
    assert resolved[0]["embedded_revision_id"] == local_rev
    assert revision.validation_state is PackageValidationState.PENDING


async def test_unresolved_dependency_blocks_and_is_never_executable(
    session: AsyncSession,
) -> None:
    await _seed_principals(session)
    manifest = _manifest(
        dependency_snapshot={"resolved": [{"canonical_key": "ta.unknown", "call": "ta.unknown"}]}
    )
    import_job_id = await _run(session, manifest)

    row = await import_repo.get_import_job(session, import_job_id)
    assert row is not None
    assert row.status is PackageImportStatus.BLOCKED
    assert row.diagnostics is not None
    missing = row.diagnostics["missing_dependencies"]
    assert missing and missing[0]["call"] == "ta.unknown"

    # The blocked package IS created (auditable) but is FAILED-validation -> not executable.
    root = await session.get(PackageRoot, row.result_package_root_id)
    assert root is not None
    revision = (
        await session.execute(
            select(PackageRevision).where(PackageRevision.entity_id == root.entity_id)
        )
    ).scalar_one()
    assert revision.validation_state is PackageValidationState.FAILED
    assert revision.approval_state is ApprovalState.DRAFT
    assert revision.validation_summary["import_status"] == "blocked"


async def test_malformed_manifest_fails_with_no_package(session: AsyncSession) -> None:
    await _seed_principals(session)
    before = await _count_roots(session)
    # missing input_contract -> a structural defect the worker records as failed.
    manifest = _manifest()
    del manifest["input_contract"]
    import_job_id = await _run(session, manifest)

    row = await import_repo.get_import_job(session, import_job_id)
    assert row is not None
    assert row.status is PackageImportStatus.FAILED
    assert row.result_package_root_id is None
    assert row.diagnostics is not None
    assert await _count_roots(session) == before  # no package created


async def test_invalid_package_kind_rejected_synchronously(session: AsyncSession) -> None:
    await _seed_principals(session)
    with pytest.raises(PackageImportManifestInvalid):
        await import_cmd.submit_package_import(
            session, OWNER, manifest=_manifest(package_kind="not_a_kind")
        )
    with pytest.raises(PackageImportManifestInvalid):
        await import_cmd.submit_package_import(session, OWNER, manifest={})


async def test_idempotent_replay_returns_same_job(session: AsyncSession) -> None:
    await _seed_principals(session)
    manifest = _manifest()
    first = await import_cmd.submit_package_import(
        session, OWNER, manifest=manifest, idempotency_key="key-1"
    )
    second = await import_cmd.submit_package_import(
        session, OWNER, manifest=manifest, idempotency_key="key-1"
    )
    assert first["job_id"] == second["job_id"]
    assert first["import_job_id"] == second["import_job_id"]
    count = int(
        (await session.execute(select(func.count()).select_from(PackageImportJob))).scalar_one()
    )
    assert count == 1


async def test_report_is_owner_scoped(session: AsyncSession) -> None:
    await _seed_principals(session)
    import_job_id = await _run(session, _manifest())
    await session.flush()

    report = await import_query.get_import_report(session, OWNER, import_job_id=import_job_id)
    assert report["import_job_id"] == import_job_id
    assert report["status"] == "succeeded"

    listed = await import_query.list_import_reports(session, OWNER)
    assert any(item["import_job_id"] == import_job_id for item in listed["items"])

    # cross-owner read -> 404, no existence leak.
    with pytest.raises(PackageImportJobNotFound):
        await import_query.get_import_report(session, OTHER, import_job_id=import_job_id)
