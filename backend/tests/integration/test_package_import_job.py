"""S3 slice (a) — package_import_job persistence + import provenance shape.

Verifies the durable import-job projection table and the ``package_root``
provenance column via the repository. Auto-skips without PostgreSQL (session
fixture rebuilds the schema from the models per test).
"""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from entropia.domain.create_package.enums import PackageImportStatus
from entropia.domain.lifecycle.enums import PackageKind, PrincipalType
from entropia.infrastructure.postgres.models import Principal
from entropia.infrastructure.postgres.repositories import package_import as import_repo
from entropia.shared.ids import new_id

pytestmark = pytest.mark.asyncio


async def _principal(session: AsyncSession) -> str:
    pid = new_id("prin")
    session.add(Principal(principal_id=pid, principal_type=PrincipalType.HUMAN))
    await session.flush()
    return pid


async def test_create_import_job_defaults_to_queued(session: AsyncSession) -> None:
    pid = await _principal(session)
    row = await import_repo.create_import_job(
        session,
        manifest_hash="a" * 64,
        package_kind=PackageKind.INDICATOR,
        origin_package_id="pkg_origin",
        origin_revision_id="pkgrev_origin",
        job_id="job_1",
        correlation_id="corr_1",
        created_by_principal_id=pid,
    )
    await session.flush()

    fetched = await import_repo.get_import_job(session, row.import_job_id)
    assert fetched is not None
    assert fetched.status is PackageImportStatus.QUEUED
    assert fetched.manifest_hash == "a" * 64
    assert fetched.origin_package_id == "pkg_origin"
    assert fetched.origin_revision_id == "pkgrev_origin"
    assert fetched.result_package_root_id is None
    assert fetched.diagnostics is None
    assert fetched.completed_at is None
    assert fetched.import_job_id.startswith("pkgimp_")


async def test_mark_terminal_blocked_records_diagnostics(session: AsyncSession) -> None:
    pid = await _principal(session)
    row = await import_repo.create_import_job(
        session,
        manifest_hash="b" * 64,
        package_kind=PackageKind.INDICATOR,
        origin_package_id=None,
        origin_revision_id=None,
        job_id="job_2",
        correlation_id=None,
        created_by_principal_id=pid,
    )
    await session.flush()

    diagnostics = {"missing_dependencies": [{"call": "ta.foo", "code": "RESOLVER_NOT_RESOLVED"}]}
    await import_repo.mark_terminal(
        session,
        row,
        status=PackageImportStatus.BLOCKED,
        result_package_root_id="pkg_local",
        diagnostics=diagnostics,
    )
    await session.flush()

    fetched = await import_repo.get_import_job(session, row.import_job_id)
    assert fetched is not None
    assert fetched.status is PackageImportStatus.BLOCKED
    assert fetched.result_package_root_id == "pkg_local"
    assert fetched.diagnostics == diagnostics
    assert fetched.completed_at is not None


async def test_get_import_job_by_job_id(session: AsyncSession) -> None:
    pid = await _principal(session)
    row = await import_repo.create_import_job(
        session,
        manifest_hash="c" * 64,
        package_kind=PackageKind.CONDITION,
        origin_package_id=None,
        origin_revision_id=None,
        job_id="job_3",
        correlation_id=None,
        created_by_principal_id=pid,
    )
    await session.flush()

    by_job = await import_repo.get_import_job_by_job_id(session, "job_3")
    assert by_job is not None
    assert by_job.import_job_id == row.import_job_id
    assert await import_repo.get_import_job_by_job_id(session, "job_missing") is None


async def test_list_import_jobs_owner_scoped_newest_first(session: AsyncSession) -> None:
    owner = await _principal(session)
    other = await _principal(session)
    for i in range(3):
        await import_repo.create_import_job(
            session,
            manifest_hash=f"{i}" * 64,
            package_kind=PackageKind.INDICATOR,
            origin_package_id=None,
            origin_revision_id=None,
            job_id=f"job_owner_{i}",
            correlation_id=None,
            created_by_principal_id=owner,
        )
    await import_repo.create_import_job(
        session,
        manifest_hash="d" * 64,
        package_kind=PackageKind.INDICATOR,
        origin_package_id=None,
        origin_revision_id=None,
        job_id="job_other",
        correlation_id=None,
        created_by_principal_id=other,
    )
    await session.flush()

    rows = await import_repo.list_import_jobs_for_owner(session, owner_principal_id=owner)
    assert len(rows) == 3
    assert all(r.created_by_principal_id == owner for r in rows)
    # newest-first: created_at desc, import_job_id desc tiebreak
    ids = [r.import_job_id for r in rows]
    assert ids == sorted(ids, reverse=True)


async def test_package_root_carries_origin_provenance_column(session: AsyncSession) -> None:
    cols = (
        (
            await session.execute(
                text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name = 'package_root'"
                )
            )
        )
        .scalars()
        .all()
    )
    assert "origin_package_id" in set(cols)


async def test_import_job_table_columns(session: AsyncSession) -> None:
    cols = set(
        (
            await session.execute(
                text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name = 'package_import_job'"
                )
            )
        )
        .scalars()
        .all()
    )
    expected = {
        "import_job_id",
        "manifest_hash",
        "origin_package_id",
        "origin_revision_id",
        "package_kind",
        "result_package_root_id",
        "status",
        "diagnostics",
        "job_id",
        "correlation_id",
        "created_by_principal_id",
        "completed_at",
        "created_at",
    }
    assert expected <= cols


async def test_status_stored_verbatim_and_length_bounded(session: AsyncSession) -> None:
    # native_enum=False stores the StrEnum value VERBATIM (CR-04) in a VARCHAR sized to
    # the longest domain value ("succeeded" = 9); an over-length value is truncated-out.
    pid = await _principal(session)
    row = await import_repo.create_import_job(
        session,
        manifest_hash="f" * 64,
        package_kind=PackageKind.INDICATOR,
        origin_package_id=None,
        origin_revision_id=None,
        job_id="job_verbatim",
        correlation_id=None,
        created_by_principal_id=pid,
    )
    await import_repo.mark_terminal(
        session,
        row,
        status=PackageImportStatus.SUCCEEDED,
        result_package_root_id="pkg_local",
        diagnostics=None,
    )
    await session.flush()

    stored = (
        await session.execute(
            text("SELECT status FROM package_import_job WHERE import_job_id = :i"),
            {"i": row.import_job_id},
        )
    ).scalar_one()
    assert stored == "succeeded"

    with pytest.raises(DBAPIError):
        await session.execute(
            text(
                "INSERT INTO package_import_job "
                "(import_job_id, manifest_hash, package_kind, status, created_by_principal_id) "
                "VALUES (:i, :h, 'indicator', 'way_too_long_status', :p)"
            ),
            {"i": new_id("pkgimp"), "h": "e" * 64, "p": pid},
        )
