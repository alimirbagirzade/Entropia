"""O-08 — Request Revision produces a PARENT-LINKED next attempt (doc 06 §7, §15).

Auto-skips when no PostgreSQL is reachable (tests/integration/conftest.py). Covers the
doc 06 §15 acceptance row "Revision immutability": a validation-failed draft's Request
Revision produces a new candidate attempt WITH a parent_revision_ref, and the old
draft / code / reports stay unchanged.

* the reopened attempt PINS the prior attempt (parent revision + root, prior validation
  run, prior candidate hash) instead of dropping the head pointers into NULL;
* a second revision keeps the FULL chain — the first link is not rewritten;
* the prior draft revision and its validation report are byte-for-byte unchanged;
* the next draft carries the parent on the package plane too
  (``PackageRevision.parent_revision_id`` / ``PackageRoot.derived_from_revision_id``);
* the projection renders the chain (``revision_chain`` / ``revision_attempt_no``);
* L1 FK insert-order: a link row cannot exist without its request Root;
* the declared OCC token is enforced (doc 06 §7 STALE_REVISION).
"""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from entropia.application.commands import create_package as cp_cmd
from entropia.application.jobs import create_package as cp_jobs
from entropia.application.queries import create_package as cp_query
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
from entropia.infrastructure.postgres.models import (
    PackageRevision,
    PackageRevisionLink,
    PackageRoot,
    PackageValidationRun,
    Principal,
)
from entropia.infrastructure.postgres.repositories import create_package as cp_repo
from entropia.infrastructure.postgres.repositories import esp as esp_repo
from entropia.infrastructure.postgres.repositories import packages as pkg_repo
from entropia.infrastructure.postgres.repositories import rationale as rationale_repo
from entropia.shared.errors import RequestVersionConflict

pytestmark = pytest.mark.integration

ADMIN = Actor(principal_id="user_admin", principal_type=PrincipalType.HUMAN, role=Role.ADMIN)
OWNER = Actor(principal_id="user_1", principal_type=PrincipalType.HUMAN, role=Role.USER)

_RSI_SIG = {
    "params": [{"name": "source", "type": "series"}, {"name": "length", "type": "int"}],
    "return": "series",
}
_RSI_DEP = {"key": "ta.rsi", "signature": _RSI_SIG}
_INDICATOR_OUTPUT = {"kind": "directional_signal"}


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
        equivalence_claim=False,
    )
    request_id = created["request_id"]
    queued_pre = await cp_cmd.run_precheck(session, OWNER, request_id=request_id)
    await cp_jobs.run_create_package_job(session, queued_pre["job_id"])
    admitted = await cp_cmd.submit_candidate_generation(session, OWNER, request_id=request_id)
    sent = await cp_jobs.run_create_package_job(session, admitted["job_id"])
    await cp_cmd.create_draft_from_candidate(
        session, OWNER, request_id=request_id, expected_candidate_hash=sent["candidate_hash"]
    )
    await session.flush()
    return request_id


async def _validate(session, request_id: str) -> dict:
    admitted = await cp_cmd.start_package_validation_run(session, OWNER, request_id=request_id)
    return await cp_jobs.run_create_package_job(session, admitted["job_id"])


async def _deprecate_resolver(session) -> None:
    """Make re-resolution drift so the next validation run FAILS (dependency_health)."""
    entry = await esp_repo.get_registry_by_key(session, "ta.rsi")
    assert entry is not None
    esp_repo.set_trust_state(
        entry, trust_state=ResolverTrustState.DEPRECATED, updated_by_principal_id="user_admin"
    )
    await session.commit()


def _row_snapshot(row, model) -> dict:
    return {column.name: getattr(row, column.name) for column in model.__table__.columns}


async def _reload_snapshot(session, model, pk_column, pk_value) -> dict:
    session.expire_all()
    row = (await session.execute(select(model).where(pk_column == pk_value))).scalar_one()
    return _row_snapshot(row, model)


async def _failed_first_attempt(session) -> tuple[str, dict]:
    """Drive a request to a FAILED validation run sitting in revision_required."""
    await _seed_principals(session)
    await _seed_python_resolver(session)
    family_id = await _seed_family(session)
    request_id = await _drive_to_draft(session, family_id=family_id)
    await session.commit()
    await _deprecate_resolver(session)
    failed = await _validate(session, request_id)
    await session.commit()
    assert failed["status"] == str(ValidationRunStatus.FAILED)
    assert failed["state"] == str(CreatePackageState.REVISION_REQUIRED)
    return request_id, failed


async def test_request_revision_pins_parent_revision_and_prior_validation(session) -> None:
    request_id, failed = await _failed_first_attempt(session)
    detail = await cp_repo.get_request_detail(session, request_id)
    assert detail is not None
    first_revision_id = detail.draft_revision_id
    first_root_id = detail.package_root_id
    first_candidate_hash = detail.candidate_hash
    first_run_id = failed["validation_run_id"]
    assert first_revision_id is not None
    # Baseline of the artefacts the revision must NOT touch.
    revision_before = await _reload_snapshot(
        session, PackageRevision, PackageRevision.revision_id, first_revision_id
    )
    run_before = await _reload_snapshot(
        session, PackageValidationRun, PackageValidationRun.validation_run_id, first_run_id
    )

    revised = await cp_cmd.request_package_revision(session, OWNER, request_id=request_id)
    await session.commit()

    # The command answers with the link it just made — the old response could only say
    # "candidate_ready" and the caller had no way to reach the attempt it came from.
    assert revised["state"] == str(CreatePackageState.CANDIDATE_READY)
    assert revised["revision_attempt_no"] == 2
    assert revised["parent_revision_ref"] == first_revision_id
    assert revised["prior_validation_run_ref"] == first_run_id

    # The head pointers are still cleared (the next C.D.P must build a FRESH draft),
    # but the attempt they pointed at is now pinned instead of lost.
    detail = await cp_repo.get_request_detail(session, request_id)
    assert detail is not None
    assert detail.draft_revision_id is None
    assert detail.package_root_id is None
    assert detail.current_validation_run_id is None
    assert detail.parent_revision_ref == first_revision_id
    assert detail.prior_validation_run_ref == first_run_id
    assert detail.revision_attempt_no == 2

    # The immutable ledger row carries the full parent context.
    links = await cp_repo.list_revision_links(session, request_id)
    assert [link.attempt_no for link in links] == [2]
    link = links[0]
    assert link.parent_revision_ref == first_revision_id
    assert link.parent_package_root_id == first_root_id
    assert link.prior_validation_run_ref == first_run_id
    assert link.prior_candidate_hash == first_candidate_hash
    assert link.prior_state == CreatePackageState.REVISION_REQUIRED

    # Revision immutability (doc 06 §15): the old draft revision and the old validation
    # report are untouched — not re-pointed, not re-stated, not re-hashed.
    assert (
        await _reload_snapshot(
            session, PackageRevision, PackageRevision.revision_id, first_revision_id
        )
        == revision_before
    )
    assert (
        await _reload_snapshot(
            session, PackageValidationRun, PackageValidationRun.validation_run_id, first_run_id
        )
        == run_before
    )


async def test_next_draft_carries_the_parent_on_the_package_plane(session) -> None:
    request_id, failed = await _failed_first_attempt(session)
    detail = await cp_repo.get_request_detail(session, request_id)
    assert detail is not None
    first_revision_id = detail.draft_revision_id

    await cp_cmd.request_package_revision(session, OWNER, request_id=request_id)
    await session.commit()
    drafted = await cp_cmd.create_draft_from_candidate(session, OWNER, request_id=request_id)
    await session.commit()

    assert drafted["draft_revision_id"] != first_revision_id
    assert drafted["revision_attempt_no"] == 2
    assert drafted["parent_revision_ref"] == first_revision_id
    second_revision = await pkg_repo.get_revision(session, drafted["draft_revision_id"])
    assert second_revision is not None
    # The chain is readable from the package plane as well: attempt 2's revision names
    # attempt 1's revision, and its root records where it was derived from.
    assert second_revision.parent_revision_id == first_revision_id
    assert first_revision_id in str(second_revision.change_note)
    second_root = await session.get(PackageRoot, drafted["package_root_id"])
    assert second_root is not None
    assert second_root.derived_from_revision_id == first_revision_id
    # The first attempt keeps its own (empty) parentage — it was not back-filled.
    first_revision = await pkg_repo.get_revision(session, first_revision_id)
    assert first_revision is not None
    assert first_revision.parent_revision_id is None
    assert failed["validation_run_id"] is not None


async def test_second_revision_keeps_the_whole_chain(session) -> None:
    request_id, failed = await _failed_first_attempt(session)
    detail = await cp_repo.get_request_detail(session, request_id)
    assert detail is not None
    first_revision_id = detail.draft_revision_id
    first_run_id = failed["validation_run_id"]

    await cp_cmd.request_package_revision(session, OWNER, request_id=request_id)
    await session.commit()
    second = await cp_cmd.create_draft_from_candidate(session, OWNER, request_id=request_id)
    await session.commit()
    second_failed = await _validate(session, request_id)
    await session.commit()
    assert second_failed["state"] == str(CreatePackageState.REVISION_REQUIRED)

    await cp_cmd.request_package_revision(session, OWNER, request_id=request_id)
    await session.commit()

    links = await cp_repo.list_revision_links(session, request_id)
    assert [link.attempt_no for link in links] == [2, 3]
    # A head-pointer-only fix would have collapsed the chain to its newest link; the
    # append-only ledger keeps attempt 2 pointing at the ORIGINAL draft.
    assert links[0].parent_revision_ref == first_revision_id
    assert links[0].prior_validation_run_ref == first_run_id
    assert links[1].parent_revision_ref == second["draft_revision_id"]
    assert links[1].prior_validation_run_ref == second_failed["validation_run_id"]

    projection = await cp_query.get_package_request(session, OWNER, request_id=request_id)
    assert projection["revision_attempt_no"] == 3
    assert projection["revision_total_attempts"] == 3
    assert projection["parent_revision_ref"] == second["draft_revision_id"]
    assert projection["prior_validation_run_ref"] == second_failed["validation_run_id"]
    assert [entry["attempt_no"] for entry in projection["revision_chain"]] == [2, 3]
    assert projection["revision_chain"][0]["parent_revision_ref"] == first_revision_id
    assert projection["revision_chain"][0]["prior_state"] == str(
        CreatePackageState.REVISION_REQUIRED
    )


async def test_fresh_request_projects_an_empty_chain(session) -> None:
    await _seed_principals(session)
    await _seed_python_resolver(session)
    family_id = await _seed_family(session)
    request_id = await _drive_to_draft(session, family_id=family_id)
    await session.commit()

    projection = await cp_query.get_package_request(session, OWNER, request_id=request_id)
    assert projection["revision_attempt_no"] == 1
    assert projection["revision_total_attempts"] == 1
    assert projection["parent_revision_ref"] is None
    assert projection["prior_validation_run_ref"] is None
    assert projection["revision_chain"] == []


async def test_request_revision_rejects_a_stale_request_version(session) -> None:
    request_id, _failed = await _failed_first_attempt(session)
    root = await cp_repo.get_request_root(session, request_id)
    assert root is not None

    with pytest.raises(RequestVersionConflict):
        await cp_cmd.request_package_revision(
            session,
            OWNER,
            request_id=request_id,
            expected_request_version=root.row_version - 1,
        )
    await session.rollback()

    # Nothing was pinned by the refused call.
    assert await cp_repo.list_revision_links(session, request_id) == []


async def test_revision_link_requires_its_request_root(session) -> None:
    """L1 FK insert-order proof: the link is a child of the request Root.

    A link inserted for an id with no ``entity_registry`` row must be refused by the FK
    (never a silently orphaned chain entry); the same insert flushes cleanly once the
    Root exists.
    """
    await _seed_principals(session)
    session.add(
        PackageRevisionLink(
            revision_link_id="revlink_orphan",
            request_entity_id="pkgreq_does_not_exist",
            attempt_no=2,
            parent_package_root_id=None,
            parent_revision_ref=None,
            prior_validation_run_ref=None,
            prior_candidate_hash=None,
            prior_state=CreatePackageState.REVISION_REQUIRED,
            correlation_id=None,
            created_by_principal_id=None,
        )
    )
    with pytest.raises(IntegrityError):
        await session.flush()
    await session.rollback()

    await _seed_principals(session)
    await _seed_python_resolver(session)
    family_id = await _seed_family(session)
    request_id = await _drive_to_draft(session, family_id=family_id)
    link = await cp_repo.append_revision_link(
        session,
        request_entity_id=request_id,
        parent_package_root_id=None,
        parent_revision_ref=None,
        prior_validation_run_ref=None,
        prior_candidate_hash=None,
        prior_state=CreatePackageState.REVISION_REQUIRED,
        correlation_id=None,
        created_by_principal_id="user_1",
    )
    await session.flush()
    assert link.attempt_no == 2
    assert link.request_entity_id == request_id
