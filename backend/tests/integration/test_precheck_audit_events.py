"""O-04 — the doc 07 §13.2 Pre-Check audit events, against a real database.

§13.2 mandates four events the code never wrote:

* ``precheck_started``    — the admission-side operational trace (attempt, hashes,
                            scanner version, job ref) that tells duplicates,
                            retries and jobs apart.
* ``dependency_resolved`` — per-call provenance: WHICH resolver revision + content
                            hash + registry version the scan actually pinned.
* ``dependency_missing``  — the failing call and its typed resolver code.
* ``precheck_stale``      — the refusal to reuse an old Passed scan.

``precheck_stale`` is the durability case (O-04): it is only ever reached by
RAISING ``PrecheckStale`` (409), and the request transaction is rolled back on that
status, so an in-transaction row could never survive. The test rolls the request
session back exactly as the middleware would and reads the row through a SEPARATE
committed session.

Auto-skips when no PostgreSQL is reachable (see tests/integration/conftest.py).

Acceptance (doc 07 §16): PC-08/PC-09 (a Passed scan is refused for reuse once the
source text or the resolver registry moved — ``precheck_stale`` is the durable
evidence of that refusal, and the old scan survives as historical evidence) and
PC-04 (``dependency_resolved`` records WHICH resolver revision the scan pinned).
"""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from entropia.application.commands import create_package as cp_cmd
from entropia.application.jobs import create_package as cp_jobs
from entropia.domain.create_package.enums import CreationMode, PrecheckScanStatus, SourceLanguage
from entropia.domain.create_package.source_scan import SOURCE_SCANNER_VERSION
from entropia.domain.esp.enums import ResolverTrustState, RuntimeAdapter
from entropia.domain.identity import Actor
from entropia.domain.lifecycle.enums import (
    ActorKind,
    ApprovalState,
    PackageKind,
    PrincipalType,
    Role,
    VisibilityScope,
)
from entropia.domain.package.enums import PackageValidationState
from entropia.infrastructure.postgres.models import DependencyScan, PackageRequest, Principal
from entropia.infrastructure.postgres.models.audit import AuditEvent
from entropia.infrastructure.postgres.repositories import esp as esp_repo
from entropia.infrastructure.postgres.repositories import packages as pkg_repo
from entropia.infrastructure.postgres.repositories import rationale as rationale_repo
from entropia.shared.errors import PrecheckStale

pytestmark = pytest.mark.integration

OWNER = Actor(
    principal_id="user_1",
    principal_type=PrincipalType.HUMAN,
    role=Role.USER,
    correlation_id="corr_pc",
)

_RSI_SIG = {
    "params": [{"name": "source", "type": "series"}, {"name": "length", "type": "int"}],
    "return": "series",
}
_RSI_DEP = {"key": "ta.rsi", "signature": _RSI_SIG}
_INDICATOR_OUTPUT = {"kind": "directional_signal"}


def _audit_factory(session: AsyncSession) -> async_sessionmaker[AsyncSession]:
    bind = session.bind
    assert isinstance(bind, AsyncEngine)
    return async_sessionmaker(bind=bind, expire_on_commit=False)


async def _events(session: AsyncSession, event_kind: str) -> list[AuditEvent]:
    async with _audit_factory(session)() as read:
        result = await read.execute(
            select(AuditEvent)
            .where(AuditEvent.event_kind == event_kind)
            .order_by(AuditEvent.event_id)
        )
        return list(result.scalars().all())


async def _seed_principals(session: AsyncSession) -> None:
    for pid in ("user_admin", "user_1"):
        if await session.get(Principal, pid) is None:
            session.add(Principal(principal_id=pid, principal_type=PrincipalType.HUMAN))
    await session.flush()


async def _seed_python_resolver(session: AsyncSession, *, key: str = "ta.rsi") -> str:
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
    return str(revision.revision_id)


async def _seed_family(session: AsyncSession) -> str:
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
    return str(root.entity_id)


async def _create_request(session: AsyncSession, *, family_id: str, deps: list[dict]) -> dict:
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
        equivalence_claim=False,
    )


# --------------------------------------------------------------------------- #
# precheck_started                                                            #
# --------------------------------------------------------------------------- #


async def test_admission_writes_precheck_started_with_the_next_attempt(
    session: AsyncSession,
) -> None:
    await _seed_principals(session)
    await _seed_python_resolver(session)
    family_id = await _seed_family(session)
    await session.commit()
    created = await _create_request(session, family_id=family_id, deps=[_RSI_DEP])
    await session.commit()

    queued = await cp_cmd.run_precheck(session, OWNER, request_id=created["request_id"])
    await session.commit()

    events = await _events(session, "precheck_started")
    assert len(events) == 1
    event = events[0]
    assert event.actor_principal_id == "user_1"
    assert event.target_entity_id == created["request_id"]
    assert event.target_entity_type == "package_request"
    assert event.new_state == str(PrecheckScanStatus.CHECKING)
    assert event.correlation_id == "corr_pc"
    metadata = event.event_metadata or {}
    # The attempt is announced BEFORE the worker writes anything, and must match the
    # attempt the scan is eventually given.
    assert metadata["scan_attempt"] == 1
    assert metadata["job_id"] == queued["job_id"]
    assert metadata["scanner_version"] == SOURCE_SCANNER_VERSION
    detail = await session.get(PackageRequest, created["request_id"])
    assert detail is not None
    assert metadata["source_hash"] == detail.source_hash
    assert metadata["context_hash"] == detail.context_hash

    result = await cp_jobs.run_create_package_job(session, queued["job_id"])
    await session.commit()
    assert result["attempt_no"] == metadata["scan_attempt"]


async def test_second_admission_announces_attempt_two(session: AsyncSession) -> None:
    await _seed_principals(session)
    await _seed_python_resolver(session)
    family_id = await _seed_family(session)
    await session.commit()
    created = await _create_request(session, family_id=family_id, deps=[_RSI_DEP])
    await session.commit()

    first = await cp_cmd.run_precheck(session, OWNER, request_id=created["request_id"])
    await session.commit()
    await cp_jobs.run_create_package_job(session, first["job_id"])
    await session.commit()

    await cp_cmd.run_precheck(session, OWNER, request_id=created["request_id"])
    await session.commit()

    attempts = [
        (e.event_metadata or {})["scan_attempt"] for e in await _events(session, "precheck_started")
    ]
    assert attempts == [1, 2]


# --------------------------------------------------------------------------- #
# dependency_resolved / dependency_missing                                    #
# --------------------------------------------------------------------------- #


async def test_worker_writes_per_dependency_provenance(session: AsyncSession) -> None:
    await _seed_principals(session)
    resolver_rev = await _seed_python_resolver(session)
    family_id = await _seed_family(session)
    await session.commit()
    created = await _create_request(
        session,
        family_id=family_id,
        deps=[_RSI_DEP, {"key": "ta.unknown", "signature": _RSI_SIG}],
    )
    await session.commit()

    queued = await cp_cmd.run_precheck(session, OWNER, request_id=created["request_id"])
    await session.commit()
    result = await cp_jobs.run_create_package_job(session, queued["job_id"])
    await session.commit()

    resolved = await _events(session, "dependency_resolved")
    assert len(resolved) == 1
    event = resolved[0]
    assert event.actor_kind == ActorKind.SYSTEM_SERVICE
    assert event.target_entity_id == created["request_id"]
    # The pin is the exact revision — never a name-only / "latest" reference.
    assert event.target_revision_id == resolver_rev
    metadata = event.event_metadata or {}
    assert metadata["canonical_key"] == "ta.rsi"
    assert metadata["embedded_revision_id"] == resolver_rev
    assert metadata["scan_id"] == result["scan_id"]
    assert metadata["request_id"] == created["request_id"]
    assert metadata["content_hash"]

    missing = await _events(session, "dependency_missing")
    assert len(missing) == 1
    assert missing[0].severity == "warning"
    missing_metadata = missing[0].event_metadata or {}
    assert missing_metadata["call"] == "ta.unknown"
    assert missing_metadata["code"]
    assert missing_metadata["scan_id"] == result["scan_id"]


# --------------------------------------------------------------------------- #
# precheck_stale — survives the 409 rollback                                  #
# --------------------------------------------------------------------------- #


async def test_stale_scan_refusal_leaves_a_durable_precheck_stale_audit(
    session: AsyncSession,
) -> None:
    await _seed_principals(session)
    await _seed_python_resolver(session)
    family_id = await _seed_family(session)
    await session.commit()
    created = await _create_request(session, family_id=family_id, deps=[_RSI_DEP])
    await session.commit()

    queued = await cp_cmd.run_precheck(session, OWNER, request_id=created["request_id"])
    await session.commit()
    scan = await cp_jobs.run_create_package_job(session, queued["job_id"])
    await session.commit()
    assert scan["status"] == str(PrecheckScanStatus.PASSED)

    # The request's context moved on after the Passed scan: the old scan may no
    # longer authorize the Send gate (PC-13).
    detail = await session.get(PackageRequest, created["request_id"])
    assert detail is not None
    old_context_hash = detail.context_hash
    detail.context_hash = "sha256:" + "c" * 64
    await session.commit()

    with pytest.raises(PrecheckStale):
        await cp_cmd.submit_candidate_generation(
            session,
            OWNER,
            request_id=created["request_id"],
            audit_session_factory=_audit_factory(session),
        )
    await session.rollback()  # exactly what TransactionBoundaryMiddleware does on 4xx

    events = await _events(session, "precheck_stale")
    assert len(events) == 1
    event = events[0]
    assert event.severity == "warning"
    assert event.actor_principal_id == "user_1"
    assert event.target_entity_id == created["request_id"]
    assert event.new_state == str(PrecheckScanStatus.STALE)
    metadata = event.event_metadata or {}
    assert metadata["old_scan_id"] == scan["scan_id"]
    assert metadata["old_context_hash"] == old_context_hash
    assert metadata["new_context_hash"] == "sha256:" + "c" * 64
    assert metadata["trigger"] == "candidate_generation_gate"


async def test_registry_move_under_a_passed_scan_is_stale_on_the_registry_arm(
    session: AsyncSession,
) -> None:
    """PC-09.c2: the Send gate's REGISTRY arm, which the sibling test never reaches.

    The test above moves ``context_hash`` — the request's own text changed under it.
    Here the request is untouched and an Admin DEPRECATES the resolver the passed
    scan pinned, so only ``registry_fingerprint`` moves. That is a genuinely
    different failure mode: an ESP the user never edited changing underneath a
    request that is still byte-identical to the one that scanned green.

    Both arms raise the same ``PrecheckStale``, so the exception alone cannot tell
    them apart. The discriminator is the audit: the context arm records
    ``new_registry_fingerprint`` as None, this arm names the recomputed fingerprint.
    """
    await _seed_principals(session)
    await _seed_python_resolver(session)
    family_id = await _seed_family(session)
    await session.commit()
    created = await _create_request(session, family_id=family_id, deps=[_RSI_DEP])
    await session.commit()

    queued = await cp_cmd.run_precheck(session, OWNER, request_id=created["request_id"])
    await session.commit()
    scan = await cp_jobs.run_create_package_job(session, queued["job_id"])
    await session.commit()
    assert scan["status"] == str(PrecheckScanStatus.PASSED)

    detail = await session.get(PackageRequest, created["request_id"])
    assert detail is not None
    unchanged_context_hash = detail.context_hash
    scan_row = await session.get(DependencyScan, scan["scan_id"])
    assert scan_row is not None
    pinned_fingerprint = scan_row.registry_fingerprint

    # The registry moves under the passed scan. The request itself is NOT touched.
    entry = await esp_repo.get_registry_by_key(session, "ta.rsi")
    assert entry is not None
    esp_repo.set_trust_state(
        entry,
        trust_state=ResolverTrustState.DEPRECATED,
        updated_by_principal_id="user_admin",
    )
    await session.commit()

    with pytest.raises(PrecheckStale):
        await cp_cmd.submit_candidate_generation(
            session,
            OWNER,
            request_id=created["request_id"],
            audit_session_factory=_audit_factory(session),
        )
    await session.rollback()  # exactly what TransactionBoundaryMiddleware does on 4xx

    events = await _events(session, "precheck_stale")
    assert len(events) == 1
    metadata = events[0].event_metadata or {}
    assert metadata["old_scan_id"] == scan["scan_id"]
    # The context arm cannot have fired: the request's hash is still the scan's.
    assert metadata["old_context_hash"] == unchanged_context_hash
    assert metadata["new_context_hash"] == unchanged_context_hash
    # So the refusal came from the registry arm, and it names the fingerprint the
    # gate recomputed against the one the scan pinned (the context arm writes None).
    assert metadata["old_registry_fingerprint"] == pinned_fingerprint
    assert metadata["new_registry_fingerprint"] is not None
    assert metadata["new_registry_fingerprint"] != pinned_fingerprint
    assert metadata["trigger"] == "candidate_generation_gate"
