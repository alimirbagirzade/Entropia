"""R2 (GAP-06 epic slice R2a) Package Library revision-plane actions: Derive +
Create Revision.

Exercised against a real database (auto-skips when no PostgreSQL is reachable, see
tests/integration/conftest.py). Covers the two revision-plane mutations the catalog
advertised via ``PackagePermissions`` (``can_derive`` / ``can_create_revision``) but
never dispatched (doc 08 §7, §8.2, §8.5, §11.1):

* Derive copies an immutable source revision into a NEW root owned by the caller,
  PRIVATE + PENDING + DRAFT, recording ``derived_from_revision_id``; any viewer may
  derive (a non-owner Derives rather than edits); a foreign PRIVATE source -> 403; a
  blank name -> 422 PACKAGE_DERIVE_INVALID; a source not on the root -> 404; a repeat
  under one Idempotency-Key creates exactly one root; the source is never mutated.
* Create Revision appends an immutable revision N+1 to an owned active root, advances
  the head + row_version, keeps the base immutable, and starts PENDING/DRAFT; a stale
  ``expected_head_revision_id`` -> 409 PACKAGE_REVISION_CONFLICT; a foreign root -> 403;
  a deprecated/soft-deleted root -> 409 LIFECYCLE_BLOCKED; a repeat under one
  Idempotency-Key appends exactly one revision.
"""

from __future__ import annotations

import pytest
from sqlalchemy import func, select

from entropia.application.commands import package_lifecycle as pkg_cmd
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
    AuditEvent,
    EntityRegistry,
    OutboxEvent,
    PackageRevision,
    Principal,
)
from entropia.infrastructure.postgres.repositories import packages as pkg_repo
from entropia.shared.errors import (
    AccessDeniedError,
    LifecycleBlocked,
    PackageDeriveInvalid,
    PackageNotFound,
    PackageRevisionConflict,
)

pytestmark = pytest.mark.integration

OWNER = Actor(principal_id="user_owner", principal_type=PrincipalType.HUMAN, role=Role.USER)
OTHER = Actor(principal_id="user_other", principal_type=PrincipalType.HUMAN, role=Role.USER)
ADMIN = Actor(principal_id="user_admin", principal_type=PrincipalType.HUMAN, role=Role.ADMIN)


async def _seed_principals(session) -> None:
    for pid in ("user_owner", "user_other", "user_admin"):
        if await session.get(Principal, pid) is None:
            session.add(Principal(principal_id=pid, principal_type=PrincipalType.HUMAN))
    await session.flush()


async def _make_pkg(
    session,
    *,
    owner: str = "user_owner",
    visibility: VisibilityScope = VisibilityScope.PUBLISHED,
    lifecycle_state: str = "active",
    validation: PackageValidationState = PackageValidationState.PASSED,
    name: str = "Reversal RSI Indicator",
) -> EntityRegistry:
    root, _detail, _revision = await pkg_repo.create_package(
        session,
        owner_principal_id=owner,
        created_by_principal_id=owner,
        package_kind=PackageKind.INDICATOR,
        input_contract={"name": name},
        output_contract={"output_kinds": ["directional_signal"]},
        dependency_snapshot={"resolved": [{"canonical_key": "ta.rsi"}]},
        visibility_scope=visibility,
        rationale_family_snapshot={"rationale_family_id": "rf_1", "display_name": "Reversal"},
        validation_state=validation,
        approval_state=ApprovalState.DRAFT,
        lifecycle_state=lifecycle_state,
    )
    await session.flush()
    return root


async def _count(session, model, **filters) -> int:
    stmt = select(func.count()).select_from(model)
    for column, value in filters.items():
        stmt = stmt.where(getattr(model, column) == value)
    return int((await session.execute(stmt)).scalar_one())


# --------------------------------------------------------------------------- #
# Derive                                                                       #
# --------------------------------------------------------------------------- #


async def test_derive_creates_new_root_owned_by_caller_with_provenance(session) -> None:
    await _seed_principals(session)
    root = await _make_pkg(session, owner="user_owner", name="Source RSI")
    source_rev = root.current_revision_id

    result = await pkg_cmd.derive_package(
        session,
        OTHER,
        entity_id=root.entity_id,
        source_revision_id=source_rev,
        name="My Derived RSI",
        change_note="tuned",
    )
    await session.flush()

    new_id = result["entity_id"]
    assert new_id != root.entity_id
    assert result["derived_from_revision_id"] == source_rev
    assert result["source_entity_id"] == root.entity_id
    assert result["name"] == "My Derived RSI"

    new_root = await pkg_repo.get_package_root(session, new_id)
    new_detail = await pkg_repo.get_package_detail(session, new_id)
    new_rev = await pkg_repo.get_revision(session, result["current_revision_id"])
    assert new_root is not None and new_root.owner_principal_id == "user_other"
    assert new_detail is not None
    assert new_detail.visibility_scope == VisibilityScope.PRIVATE  # a fresh private root
    assert new_detail.derived_from_revision_id == source_rev
    assert new_rev is not None
    assert new_rev.validation_state == PackageValidationState.PENDING  # must be re-validated
    assert new_rev.approval_state == ApprovalState.DRAFT
    assert new_rev.input_contract["name"] == "My Derived RSI"  # name overridden
    assert new_rev.output_contract == {"output_kinds": ["directional_signal"]}  # copied
    assert new_rev.package_kind == PackageKind.INDICATOR

    # The source root is never mutated (doc 08 §11.1 "original root never mutated").
    src_root = await pkg_repo.get_package_root(session, root.entity_id)
    assert src_root is not None and src_root.current_revision_id == source_rev
    assert await _count(session, AuditEvent, event_kind="package.derived") == 1
    assert await _count(session, OutboxEvent, resource_id=new_id) == 1


async def test_derive_requires_view_permission_on_source(session) -> None:
    await _seed_principals(session)
    root = await _make_pkg(session, owner="user_owner", visibility=VisibilityScope.PRIVATE)

    with pytest.raises(AccessDeniedError):
        await pkg_cmd.derive_package(
            session,
            OTHER,
            entity_id=root.entity_id,
            source_revision_id=root.current_revision_id or "",
            name="Sneaky",
        )
    # Nothing was created for the denied caller.
    assert await _count(session, EntityRegistry, owner_principal_id="user_other") == 0


async def test_derive_blank_name_is_rejected(session) -> None:
    await _seed_principals(session)
    root = await _make_pkg(session)

    with pytest.raises(PackageDeriveInvalid):
        await pkg_cmd.derive_package(
            session,
            OTHER,
            entity_id=root.entity_id,
            source_revision_id=root.current_revision_id or "",
            name="   ",
        )


async def test_derive_source_not_on_root_is_not_found(session) -> None:
    await _seed_principals(session)
    root = await _make_pkg(session)

    with pytest.raises(PackageNotFound):
        await pkg_cmd.derive_package(
            session,
            OTHER,
            entity_id=root.entity_id,
            source_revision_id="pkgrev_not_here",
            name="Derived",
        )


async def test_derive_is_idempotent_under_one_key(session) -> None:
    await _seed_principals(session)
    root = await _make_pkg(session, owner="user_owner")

    first = await pkg_cmd.derive_package(
        session,
        OTHER,
        entity_id=root.entity_id,
        source_revision_id=root.current_revision_id or "",
        name="Derived Once",
        idempotency_key="idem-derive-1",
    )
    await session.flush()
    second = await pkg_cmd.derive_package(
        session,
        OTHER,
        entity_id=root.entity_id,
        source_revision_id=root.current_revision_id or "",
        name="Derived Once",
        idempotency_key="idem-derive-1",
    )
    await session.flush()

    assert first["entity_id"] == second["entity_id"]  # replay returns the same root
    assert await _count(session, EntityRegistry, owner_principal_id="user_other") == 1
    assert await _count(session, AuditEvent, event_kind="package.derived") == 1


# --------------------------------------------------------------------------- #
# Create Revision                                                              #
# --------------------------------------------------------------------------- #


async def test_create_revision_appends_and_advances_head(session) -> None:
    await _seed_principals(session)
    root = await _make_pkg(session, owner="user_owner")
    base_rev = root.current_revision_id

    result = await pkg_cmd.create_package_revision(
        session,
        OWNER,
        entity_id=root.entity_id,
        expected_head_revision_id=base_rev,
        change_note="v2 tweak",
    )
    await session.flush()

    assert result["revision_no"] == 2
    assert result["base_revision_id"] == base_rev
    refreshed = await pkg_repo.get_package_root(session, root.entity_id)
    assert refreshed is not None
    assert refreshed.current_revision_id == result["revision_id"]  # head advanced
    assert refreshed.row_version == 2  # create_package starts at 1, append bumps it

    new_rev = await pkg_repo.get_revision(session, result["revision_id"])
    assert new_rev is not None
    assert new_rev.validation_state == PackageValidationState.PENDING  # must re-validate
    assert new_rev.approval_state == ApprovalState.DRAFT
    assert new_rev.supersedes_revision_id == base_rev
    # The base revision stays immutable and still exists as revision_no 1.
    base = await pkg_repo.get_revision(session, base_rev or "")
    assert base is not None and base.revision_no == 1
    assert await _count(session, PackageRevision, entity_id=root.entity_id) == 2
    assert await _count(session, AuditEvent, event_kind="package.revision_drafted") == 1


async def test_create_revision_applies_contract_override(session) -> None:
    await _seed_principals(session)
    root = await _make_pkg(session, owner="user_owner")

    result = await pkg_cmd.create_package_revision(
        session,
        OWNER,
        entity_id=root.entity_id,
        input_contract={"name": "Edited Head"},
    )
    await session.flush()
    new_rev = await pkg_repo.get_revision(session, result["revision_id"])
    assert new_rev is not None and new_rev.input_contract == {"name": "Edited Head"}
    # Unspecified contracts copy the base (doc 08 §7 "based on exact base revision").
    assert new_rev.output_contract == {"output_kinds": ["directional_signal"]}


async def test_create_revision_stale_head_conflicts(session) -> None:
    await _seed_principals(session)
    root = await _make_pkg(session, owner="user_owner")

    with pytest.raises(PackageRevisionConflict):
        await pkg_cmd.create_package_revision(
            session,
            OWNER,
            entity_id=root.entity_id,
            expected_head_revision_id="pkgrev_stale",
        )
    # No revision appended — the head is unchanged.
    assert await _count(session, PackageRevision, entity_id=root.entity_id) == 1


async def test_create_revision_foreign_root_is_forbidden(session) -> None:
    await _seed_principals(session)
    root = await _make_pkg(session, owner="user_owner")

    with pytest.raises(AccessDeniedError):
        await pkg_cmd.create_package_revision(session, OTHER, entity_id=root.entity_id)


async def test_admin_can_create_revision_on_foreign_root(session) -> None:
    await _seed_principals(session)
    root = await _make_pkg(session, owner="user_owner")

    result = await pkg_cmd.create_package_revision(session, ADMIN, entity_id=root.entity_id)
    assert result["revision_no"] == 2


async def test_create_revision_on_deprecated_root_is_blocked(session) -> None:
    await _seed_principals(session)
    root = await _make_pkg(session, owner="user_owner", lifecycle_state="deprecated")

    with pytest.raises(LifecycleBlocked):
        await pkg_cmd.create_package_revision(session, OWNER, entity_id=root.entity_id)


async def test_create_revision_is_idempotent_under_one_key(session) -> None:
    await _seed_principals(session)
    root = await _make_pkg(session, owner="user_owner")

    first = await pkg_cmd.create_package_revision(
        session, OWNER, entity_id=root.entity_id, idempotency_key="idem-rev-1"
    )
    await session.flush()
    second = await pkg_cmd.create_package_revision(
        session, OWNER, entity_id=root.entity_id, idempotency_key="idem-rev-1"
    )
    await session.flush()

    assert first["revision_id"] == second["revision_id"]  # replay returns the same rev
    assert (
        await _count(session, PackageRevision, entity_id=root.entity_id) == 2
    )  # 1 base + 1 append
    assert await _count(session, AuditEvent, event_kind="package.revision_drafted") == 1
