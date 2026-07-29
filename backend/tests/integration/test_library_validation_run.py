"""S-L3 — POST /library/{id}/validation-runs (doc 08 §7 "Request validation").

The Library plane advertised the action in doc 08 §4.2 (`can_request_validation`) but
had no command behind it, and the projection deliberately hid the flag rather than
advertise something un-performable. This slice adds the command as a WRAPPER around
the CreatePackage-plane run — the seven checks, the immutable evidence row, the
durable job and the state machine are unchanged, so a package cannot end up with two
ways to be certified.

Auto-skips without PostgreSQL (see tests/integration/conftest.py).
"""

from __future__ import annotations

import pytest
from sqlalchemy import func, select

from entropia.application.commands import package_lifecycle as pkg_cmd
from entropia.application.jobs import create_package as cp_jobs
from entropia.application.queries import library as library_query
from entropia.domain.create_package.enums import CreatePackageState, ValidationRunStatus
from entropia.domain.package.catalog import parse_catalog_filters
from entropia.infrastructure.postgres.models import EntityRegistry, PackageValidationRun
from entropia.infrastructure.postgres.repositories import create_package as cp_repo
from entropia.shared.errors import (
    PackageRevisionConflict,
    ValidationAlreadyRunning,
    ValidationPipelineUnavailable,
)
from entropia.shared.pagination import PageParams
from tests.integration.test_validation_evidence import (
    ADMIN,
    OWNER,
    _drive_to_draft,
    _seed_family,
    _seed_principals,
    _seed_python_resolver,
)

pytestmark = pytest.mark.integration


async def _count(session, model) -> int:
    return int((await session.execute(select(func.count()).select_from(model))).scalar_one())


async def _library_head(session) -> tuple[str, str]:
    """Drive a request to draft and return its (package_root_id, head_revision_id)."""
    await _seed_principals(session)
    await _seed_python_resolver(session)
    family_id = await _seed_family(session)
    request_id = await _drive_to_draft(session, family_id=family_id)
    await session.commit()

    detail = await cp_repo.get_request_detail(session, request_id)
    assert detail is not None and detail.package_root_id is not None
    root = await session.get(EntityRegistry, detail.package_root_id)
    assert root is not None and root.current_revision_id is not None
    return detail.package_root_id, root.current_revision_id


async def test_library_request_validation_drives_the_same_cp_run(session) -> None:
    """One pipeline, addressed from the Library plane — no second certification path."""
    entity_id, revision_id = await _library_head(session)
    runs_before = await _count(session, PackageValidationRun)

    out = await pkg_cmd.request_package_validation(
        session,
        OWNER,
        entity_id=entity_id,
        revision_id=revision_id,
        expected_head_revision_id=revision_id,
    )
    await session.commit()

    # Answered in package terms, with the CP identifiers carried through so both
    # planes stay traceable to ONE run.
    assert out["entity_id"] == entity_id
    assert out["revision_id"] == revision_id
    assert out["status"] == str(ValidationRunStatus.QUEUED)
    assert out["state"] == str(CreatePackageState.VALIDATION_RUNNING)
    assert out["job_id"]

    # Exactly one new immutable evidence row — the CP plane's, not a Library copy.
    assert await _count(session, PackageValidationRun) == runs_before + 1
    run = await session.get(PackageValidationRun, out["validation_run_id"])
    assert run is not None
    assert run.package_root_id == entity_id
    assert run.request_entity_id == out["request_id"]

    # The durable worker completes it exactly as the CP-plane path does.
    finished = await cp_jobs.run_create_package_job(session, out["job_id"])
    await session.commit()
    assert finished["status"] == str(ValidationRunStatus.PASSED)


async def test_a_run_already_in_flight_is_a_conflict_not_a_duplicate(session) -> None:
    entity_id, revision_id = await _library_head(session)
    first = await pkg_cmd.request_package_validation(
        session, OWNER, entity_id=entity_id, revision_id=revision_id
    )
    await session.commit()
    runs_after_first = await _count(session, PackageValidationRun)

    with pytest.raises(ValidationAlreadyRunning) as excinfo:
        await pkg_cmd.request_package_validation(
            session, OWNER, entity_id=entity_id, revision_id=revision_id
        )
    await session.rollback()

    assert excinfo.value.code == "VALIDATION_ALREADY_RUNNING"
    assert excinfo.value.details[0]["validation_run_id"] == first["validation_run_id"]
    # No duplicate evidence row was created.
    assert await _count(session, PackageValidationRun) == runs_after_first


async def test_a_stale_expected_head_is_refused(session) -> None:
    entity_id, revision_id = await _library_head(session)
    with pytest.raises(PackageRevisionConflict):
        await pkg_cmd.request_package_validation(
            session,
            OWNER,
            entity_id=entity_id,
            revision_id=revision_id,
            expected_head_revision_id="pkgrev_stale",
        )
    await session.rollback()


async def test_a_package_with_no_originating_request_is_refused_explicitly(session) -> None:
    """A Derived / seeded package has no draft to certify.

    Refusing loudly is the point: a silent no-op is the same "advertises an
    un-performable action" defect this slice removes on the projection side.
    """
    entity_id, revision_id = await _library_head(session)
    detail = await cp_repo.get_request_for_package_root(session, entity_id)
    assert detail is not None
    # Sever the link the way a Derived package is born: no originating request.
    detail.package_root_id = None
    await session.flush()

    with pytest.raises(ValidationPipelineUnavailable) as excinfo:
        await pkg_cmd.request_package_validation(
            session, OWNER, entity_id=entity_id, revision_id=revision_id
        )
    await session.rollback()
    assert excinfo.value.code == "VALIDATION_PIPELINE_UNAVAILABLE"


async def test_catalog_projects_can_request_validation_for_the_backed_root(session) -> None:
    """The orphan flag is consumed: doc 08 §4.2's capability is now advertised."""
    entity_id, _revision_id = await _library_head(session)

    detail = await library_query.get_package_detail(session, ADMIN, entity_id=entity_id)
    assert detail["permissions"]["can_request_validation"] is True

    page = await library_query.list_packages(
        session, ADMIN, _params(), filters=parse_catalog_filters()
    )
    row = next(r for r in page["data"] if r["entity_id"] == entity_id)
    assert row["permissions"]["can_request_validation"] is True


def _params() -> PageParams:
    return PageParams(cursor=None, limit=20)
