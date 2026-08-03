"""G-02 — package import across export schema versions (doc 08 §10, §14).

Auto-skips without PostgreSQL. Companion to ``test_esp_export_contract_v2.py``: that file
pins what the exporter WRITES, this one pins what the importer will READ.

The compatibility rule under test:

* **v1** — the artifact predates ``export_schema_version`` entirely. It must keep importing
  unchanged; a version gate that orphaned every artifact already in the wild would be a
  regression dressed as a contract.
* **v2** — parses, and its ESP contract facts reach the import report — but as an ECHO
  stamped ``trusted: false``. The package is still built purely from LOCAL re-resolution.
* **anything else** — fail-closed at the API boundary (422) AND, defence in depth, as a
  terminal ``failed`` in the worker. Guessing at a version this build has never seen is how
  an unreadable artifact becomes a silently executable package.

The sharpest assertion here is the negative one: importing a v2 manifest that names a
foreign ``runtime_adapter`` writes NO ``embedded_resolver_contract`` and NO
``embedded_resolver_registry`` row. A foreign adapter earns no local trust by being named
in a file.
"""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from entropia.application.commands import package_import as import_cmd
from entropia.application.jobs.package_import import run_import
from entropia.domain.create_package.enums import PackageImportStatus
from entropia.domain.package.export_contract import (
    EVIDENCE_RECORDED,
    EXPORT_SCHEMA_VERSION,
    EXPORTER_VERSION,
)
from entropia.infrastructure.postgres.models import (
    EmbeddedResolverContract,
    EmbeddedResolverRegistry,
    Job,
    PackageImportJob,
    PackageRevision,
    PackageRoot,
)
from entropia.infrastructure.postgres.repositories import package_import as import_repo
from entropia.shared.errors import PackageImportManifestInvalid

from .test_package_import_worker import (
    OWNER,
    _manifest,
    _run,
    _seed_principals,
    _seed_rsi_resolver,
)

pytestmark = pytest.mark.asyncio

_FOREIGN_CONTRACT: dict[str, Any] = {
    "contract_id": "espc_foreign",
    "package_root_id": "pkg_origin",
    "revision_id": "pkgrev_origin",
    "canonical_key": "ta.rsi",
    "signature": {"params": [{"name": "length", "type": "int"}], "return": "series"},
    # Deliberately NOT the adapter the local registry trusts for ta.rsi (python).
    "runtime_adapter": "pine_v5",
    "warm_up_period": 14,
    "timing_semantics": "close_of_bar",
    "repaint": False,
    "evidence": {"test_vectors": [{"length": 14, "close": [1, 2], "expected": [None, None]}]},
}

_FOREIGN_EVIDENCE: dict[str, Any] = {
    "evidence_state": EVIDENCE_RECORDED,
    "validation_run_id": "espv_foreign",
    "validator_version": "esp-validation-v1",
    "status": "passed",
    "vectors_run": 1,
    "checks": {"checks": []},
    "completed_at": "2026-01-01T00:00:00+00:00",
    "revision_validation_state": "passed",
    "revision_approval_state": "approved",
}


def _v2_manifest(**overrides: Any) -> dict[str, Any]:
    return _manifest(
        export_schema_version=EXPORT_SCHEMA_VERSION,
        exporter_version=EXPORTER_VERSION,
        package_kind="embedded_system",
        dependency_snapshot={"resolved": [{"canonical_key": "ta.rsi"}]},
        resolver_contract_snapshot=_FOREIGN_CONTRACT,
        validation_evidence_snapshot=_FOREIGN_EVIDENCE,
        **overrides,
    )


async def _count(session: AsyncSession, model: Any) -> int:
    return int((await session.execute(select(func.count()).select_from(model))).scalar_one())


# --------------------------------------------------------------------------- #
# v1 compatibility                                                              #
# --------------------------------------------------------------------------- #


async def test_v1_manifest_without_a_version_field_still_imports(session: AsyncSession) -> None:
    """An artifact exported before G-02 carries no version and must import unchanged."""
    await _seed_principals(session)
    legacy = _manifest()
    assert "export_schema_version" not in legacy

    import_job_id = await _run(session, legacy)

    row = await import_repo.get_import_job(session, import_job_id)
    assert row is not None
    assert row.status is PackageImportStatus.SUCCEEDED
    # The report records which reading was applied, so a v1 import is never mistaken for a
    # v2 one that happened to omit its ESP facts.
    assert row.diagnostics["export_schema_version"] == 1
    assert "origin_resolver_contract" not in row.diagnostics


async def test_explicit_v1_version_is_accepted(session: AsyncSession) -> None:
    await _seed_principals(session)
    import_job_id = await _run(session, _manifest(export_schema_version=1))

    row = await import_repo.get_import_job(session, import_job_id)
    assert row is not None
    assert row.status is PackageImportStatus.SUCCEEDED
    assert row.diagnostics["export_schema_version"] == 1


# --------------------------------------------------------------------------- #
# v2 success — parsed, echoed, never trusted                                    #
# --------------------------------------------------------------------------- #


async def test_v2_manifest_imports_and_repins_to_the_local_resolver(session: AsyncSession) -> None:
    """A v2 ESP manifest resolves against the LOCAL registry, not its own claim.

    The manifest names ``pine_v5``; the local trusted resolver for ``ta.rsi`` is ``python``.
    The re-pinned dependency must carry the LOCAL revision and the LOCAL adapter — the
    origin's adapter survives only inside the untrusted echo."""
    await _seed_principals(session)
    local_revision_id = await _seed_rsi_resolver(session)

    import_job_id = await _run(session, _v2_manifest())

    row = await import_repo.get_import_job(session, import_job_id)
    assert row is not None
    assert row.status is PackageImportStatus.SUCCEEDED
    assert row.diagnostics["export_schema_version"] == EXPORT_SCHEMA_VERSION

    revision = (
        await session.execute(
            select(PackageRevision).where(PackageRevision.entity_id == row.result_package_root_id)
        )
    ).scalar_one()
    pinned = revision.dependency_snapshot["resolved"][0]
    assert pinned["embedded_revision_id"] == local_revision_id
    assert pinned["runtime_adapter"] == "python"  # LOCAL, not the manifest's pine_v5


async def test_v2_origin_contract_is_echoed_as_untrusted_and_grants_no_local_trust(
    session: AsyncSession,
) -> None:
    """The import report SHOWS the origin claim and refuses it in the same breath.

    Row-count assertions are the point: a v2 import must not manufacture an
    ``embedded_resolver_contract`` or an ``embedded_resolver_registry`` pointer out of a
    foreign manifest, or importing a file would be a way to mint trusted resolvers."""
    await _seed_principals(session)
    await _seed_rsi_resolver(session)
    contracts_before = await _count(session, EmbeddedResolverContract)
    registry_before = await _count(session, EmbeddedResolverRegistry)

    import_job_id = await _run(session, _v2_manifest())

    row = await import_repo.get_import_job(session, import_job_id)
    assert row is not None
    echo = row.diagnostics["origin_resolver_contract"]
    assert echo["canonical_key"] == "ta.rsi"
    assert echo["runtime_adapter"] == "pine_v5"
    assert echo["warm_up_period"] == 14
    assert echo["timing_semantics"] == "close_of_bar"
    assert echo["origin_validation_status"] == "passed"
    # The two refusals, carried on the record itself.
    assert echo["trusted"] is False
    assert echo["local_revalidation_required"] is True

    assert await _count(session, EmbeddedResolverContract) == contracts_before
    assert await _count(session, EmbeddedResolverRegistry) == registry_before


async def test_v2_manifest_with_an_unresolvable_adapter_key_is_blocked(
    session: AsyncSession,
) -> None:
    """No local resolver for the declared key -> BLOCKED, FAILED validation, never runnable.

    The origin's "passed" evidence is present in the manifest and changes nothing: local
    resolvability is the only thing that decides."""
    await _seed_principals(session)  # NOTE: no local ta.rsi resolver seeded

    import_job_id = await _run(session, _v2_manifest())

    row = await import_repo.get_import_job(session, import_job_id)
    assert row is not None
    assert row.status is PackageImportStatus.BLOCKED
    assert row.diagnostics["missing_dependencies"][0]["call"] == "ta.rsi"
    assert row.diagnostics["missing_dependencies"][0]["code"] == "RESOLVER_NOT_RESOLVED"
    # The origin claim is still reported — and still untrusted.
    assert row.diagnostics["origin_resolver_contract"]["trusted"] is False

    revision = (
        await session.execute(
            select(PackageRevision).where(PackageRevision.entity_id == row.result_package_root_id)
        )
    ).scalar_one()
    assert revision.validation_state.value == "failed"


# --------------------------------------------------------------------------- #
# Unknown future versions fail closed                                           #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("version", [3, 99, "next", "2.0", "", True, 0, -1, [2], {"v": 2}])
async def test_unknown_schema_version_is_rejected_at_the_api_boundary(
    session: AsyncSession, version: Any
) -> None:
    """422 before any durable job opens — including the bool trap (``True == 1``).

    ``True`` is listed on purpose: a naive ``raw in {1, 2}`` accepts it, and a manifest
    whose version reads ``true`` is not a v1 artifact.

    The counts are on ``PackageImportJob`` and ``Job`` deliberately: ``submit_package_import``
    never creates a ``PackageRoot`` under ANY input, so asserting on roots here would be
    vacuous — it would pass even if the gate were deleted and a durable job opened."""
    await _seed_principals(session)
    import_jobs_before = await _count(session, PackageImportJob)
    jobs_before = await _count(session, Job)

    with pytest.raises(PackageImportManifestInvalid):
        await import_cmd.submit_package_import(
            session, OWNER, manifest=_manifest(export_schema_version=version)
        )

    assert await _count(session, PackageImportJob) == import_jobs_before
    assert await _count(session, Job) == jobs_before


async def test_an_explicit_null_version_is_read_as_v1(session: AsyncSession) -> None:
    """``{"export_schema_version": null}`` states no version, exactly as an absent key does.

    Called out because it is the one input where "fail closed" and "read it" could both be
    argued. JSON ``null`` is the absence of a value, not an unknown future version, so it
    takes the v1 reading — and local re-resolution still governs everything that follows."""
    await _seed_principals(session)
    import_job_id = await _run(session, _manifest(export_schema_version=None))

    row = await import_repo.get_import_job(session, import_job_id)
    assert row is not None
    assert row.status is PackageImportStatus.SUCCEEDED
    assert row.diagnostics["export_schema_version"] == 1


async def test_worker_fails_closed_on_an_unknown_version_that_reached_the_queue(
    session: AsyncSession,
) -> None:
    """Defence in depth: a job row carrying an unreadable version produces no package.

    The boundary is bypassed here on purpose — a job could reach the queue from an older
    build, a replayed payload or a direct enqueue, and the worker must not be the layer that
    trusts its input."""
    await _seed_principals(session)
    submitted = await import_cmd.submit_package_import(session, OWNER, manifest=_manifest())
    job = await session.get(Job, submitted["job_id"])
    assert job is not None
    job.payload = {
        **job.payload,
        "manifest": {**job.payload["manifest"], "export_schema_version": 7},
    }
    await session.flush()
    roots_before = await _count(session, PackageRoot)

    await run_import(session, submitted["job_id"])

    row = await import_repo.get_import_job(session, submitted["import_job_id"])
    assert row is not None
    assert row.status is PackageImportStatus.FAILED
    assert row.diagnostics["reason"] == "unsupported_export_schema_version"
    assert row.result_package_root_id is None
    assert await _count(session, PackageRoot) == roots_before


# --------------------------------------------------------------------------- #
# End-to-end round trip — a real exported artifact, fed straight back in        #
# --------------------------------------------------------------------------- #


async def test_real_exported_esp_artifact_round_trips_without_minting_trust(
    session: AsyncSession,
) -> None:
    """Export a genuinely trusted ESP, then import that exact artifact back.

    Every earlier import test uses a hand-built manifest; this one closes the loop with the
    bytes the exporter actually produces, so exporter and importer cannot drift apart
    unnoticed. The assertions that matter are the refusals: the round trip creates a DRAFT
    PENDING package (never executable without its own Pre-Check) and mints NO resolver
    contract and NO registry pointer — even though the artifact it just consumed contains a
    complete, validator-certified ``passed`` contract. Trust is local, and importing a file
    is not a way to acquire it.
    """
    from entropia.application.commands import package_lifecycle as pkg_cmd

    from .test_acceptance_esp_package_gaps import ADMIN, _trusted_esp

    await _seed_principals(session)
    esp = await _trusted_esp(session)
    contracts_before = await _count(session, EmbeddedResolverContract)
    registry_before = await _count(session, EmbeddedResolverRegistry)

    exported = await pkg_cmd.export_package(
        session, ADMIN, entity_id=esp["entity_id"], revision_id=esp["revision_id"]
    )
    await session.commit()
    artifact = exported["manifest"]
    assert artifact["export_schema_version"] == EXPORT_SCHEMA_VERSION
    assert artifact["validation_evidence_snapshot"]["status"] == "passed"

    import_job_id = await _run(session, artifact)

    row = await import_repo.get_import_job(session, import_job_id)
    assert row is not None
    assert row.status is PackageImportStatus.SUCCEEDED
    assert row.diagnostics["export_schema_version"] == EXPORT_SCHEMA_VERSION
    echo = row.diagnostics["origin_resolver_contract"]
    assert echo["canonical_key"] == "ta.sma"
    assert echo["origin_validation_status"] == "passed"
    assert echo["trusted"] is False

    revision = (
        await session.execute(
            select(PackageRevision).where(PackageRevision.entity_id == row.result_package_root_id)
        )
    ).scalar_one()
    assert revision.validation_state.value == "pending"
    assert revision.approval_state.value == "draft"

    assert await _count(session, EmbeddedResolverContract) == contracts_before
    assert await _count(session, EmbeddedResolverRegistry) == registry_before
