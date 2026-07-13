"""GAP-06 (epic slice 1) package Library lifecycle: Deprecate + Move to Trash.

Exercised against a real database (auto-skips when no PostgreSQL is reachable, see
tests/integration/conftest.py). Covers the two root-lifecycle mutations the catalog
already advertised via ``PackagePermissions`` but never dispatched (doc 08 §7, §8.4):

* Deprecate flips an ``active`` root -> ``deprecated`` (owner or Admin), keeps the
  head/history, and drops the row out of the "offered for new work" set while it
  stays listed; a non-active / soft-deleted root -> 409 LIFECYCLE_BLOCKED; a foreign
  package -> 403; a missing root -> 404.
* Move to Trash soft-deletes the root through the shared Trash-core: a Trash entry is
  written (object type ``package`` -> "Package Library"), the row leaves the catalog,
  the ``package.soft_deleted`` audit + outbox land; a stale ``row_version`` -> 409
  STALE_REVISION; a repeat delete is an idempotent no-op; a foreign delete -> 403.
* Restore is the existing Admin Trash surface: a deprecated-then-deleted package
  restores back to ``deprecated`` (lifecycle preserved, not silently reactivated).
"""

from __future__ import annotations

import pytest
from sqlalchemy import func, select

from entropia.application.commands import deletion as del_cmd
from entropia.application.commands import package_lifecycle as pkg_cmd
from entropia.application.queries import library as library_query
from entropia.domain.identity import Actor
from entropia.domain.lifecycle.enums import (
    ApprovalState,
    DeletionState,
    PackageKind,
    PrincipalType,
    Role,
    VisibilityScope,
)
from entropia.domain.package.catalog import parse_catalog_filters
from entropia.domain.package.enums import PackageValidationState
from entropia.infrastructure.postgres.models import (
    AuditEvent,
    EntityRegistry,
    OutboxEvent,
    Principal,
    TrashEntry,
)
from entropia.infrastructure.postgres.repositories import packages as pkg_repo
from entropia.infrastructure.postgres.repositories import trash as trash_repo
from entropia.shared.errors import (
    AccessDeniedError,
    LifecycleBlocked,
    PackageNotFound,
    StaleRevisionError,
)
from entropia.shared.pagination import PageParams

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
    lifecycle_state: str = "active",
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
        visibility_scope=VisibilityScope.PUBLISHED,
        validation_state=PackageValidationState.PASSED,
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


async def _catalog_ids(session, actor: Actor) -> set[str]:
    page = await library_query.list_packages(
        session, actor, PageParams(cursor=None, limit=100), filters=parse_catalog_filters()
    )
    return {row["entity_id"] for row in page["data"]}


# --------------------------------------------------------------------------- #
# Deprecate                                                                    #
# --------------------------------------------------------------------------- #


async def test_deprecate_active_package_flips_lifecycle_and_audits(session) -> None:
    await _seed_principals(session)
    root = await _make_pkg(session)

    result = await pkg_cmd.deprecate_package(session, OWNER, entity_id=root.entity_id, note="stale")
    await session.flush()

    assert result["lifecycle_state"] == "deprecated"
    refreshed = await pkg_repo.get_package_root(session, root.entity_id)
    assert refreshed is not None and refreshed.lifecycle_state == "deprecated"
    assert refreshed.deletion_state == DeletionState.ACTIVE  # still listed, not deleted
    assert await _count(session, AuditEvent, event_kind="package.deprecated") == 1
    assert await _count(session, OutboxEvent, resource_id=root.entity_id) == 1
    # A deprecated package is still discoverable in the catalog (doc 08 §4.4).
    assert root.entity_id in await _catalog_ids(session, OWNER)


async def test_deprecate_already_deprecated_is_lifecycle_blocked(session) -> None:
    await _seed_principals(session)
    root = await _make_pkg(session, lifecycle_state="deprecated")

    with pytest.raises(LifecycleBlocked):
        await pkg_cmd.deprecate_package(session, OWNER, entity_id=root.entity_id)


async def test_admin_can_deprecate_foreign_package(session) -> None:
    await _seed_principals(session)
    root = await _make_pkg(session, owner="user_owner")

    result = await pkg_cmd.deprecate_package(session, ADMIN, entity_id=root.entity_id)
    assert result["lifecycle_state"] == "deprecated"


async def test_deprecate_foreign_package_is_forbidden(session) -> None:
    await _seed_principals(session)
    root = await _make_pkg(session, owner="user_owner")

    with pytest.raises(AccessDeniedError):
        await pkg_cmd.deprecate_package(session, OTHER, entity_id=root.entity_id)


async def test_deprecate_missing_root_is_not_found(session) -> None:
    await _seed_principals(session)
    with pytest.raises(PackageNotFound):
        await pkg_cmd.deprecate_package(session, OWNER, entity_id="pkg_missing")


# --------------------------------------------------------------------------- #
# Move to Trash (soft delete)                                                  #
# --------------------------------------------------------------------------- #


async def test_soft_delete_creates_trash_entry_and_hides_from_catalog(session) -> None:
    await _seed_principals(session)
    root = await _make_pkg(session, name="Deletable Indicator")

    result = await pkg_cmd.soft_delete_package(session, OWNER, entity_id=root.entity_id)
    await session.flush()

    assert result["deletion_state"] == str(DeletionState.SOFT_DELETED)
    assert result["display_name"] == "Deletable Indicator"
    refreshed = await pkg_repo.get_package_root(session, root.entity_id)
    assert refreshed is not None and refreshed.deletion_state == DeletionState.SOFT_DELETED

    entry = await trash_repo.get_recoverable_entry_for_entity(session, root.entity_id)
    assert entry is not None
    assert entry.entity_type == "package"
    assert entry.original_location == "Package Library"
    assert entry.display_name == "Deletable Indicator"
    assert await _count(session, AuditEvent, event_kind="package.soft_deleted") == 1
    # The soft-deleted root drops out of the catalog projection (doc 08 §8.4).
    assert root.entity_id not in await _catalog_ids(session, OWNER)


async def test_soft_delete_stale_row_version_conflicts(session) -> None:
    await _seed_principals(session)
    root = await _make_pkg(session)

    with pytest.raises(StaleRevisionError):
        await pkg_cmd.soft_delete_package(
            session, OWNER, entity_id=root.entity_id, expected_row_version=999
        )
    refreshed = await pkg_repo.get_package_root(session, root.entity_id)
    assert refreshed is not None and refreshed.deletion_state == DeletionState.ACTIVE


async def test_soft_delete_repeat_is_idempotent_noop(session) -> None:
    await _seed_principals(session)
    root = await _make_pkg(session)

    await pkg_cmd.soft_delete_package(session, OWNER, entity_id=root.entity_id)
    await session.flush()
    await pkg_cmd.soft_delete_package(session, OWNER, entity_id=root.entity_id)
    await session.flush()

    # One entry, one audit — the second call short-circuits (doc 20 §14).
    assert await _count(session, TrashEntry, entity_id=root.entity_id) == 1
    assert await _count(session, AuditEvent, event_kind="package.soft_deleted") == 1


async def test_soft_delete_foreign_is_forbidden(session) -> None:
    await _seed_principals(session)
    root = await _make_pkg(session, owner="user_owner")

    with pytest.raises(AccessDeniedError):
        await pkg_cmd.soft_delete_package(session, OTHER, entity_id=root.entity_id)


async def test_deprecated_then_deleted_package_restores_to_deprecated(session) -> None:
    await _seed_principals(session)
    root = await _make_pkg(session)

    await pkg_cmd.deprecate_package(session, OWNER, entity_id=root.entity_id)
    await pkg_cmd.soft_delete_package(session, OWNER, entity_id=root.entity_id)
    await session.flush()

    restored = await del_cmd.restore_entity(session, ADMIN, entity_id=root.entity_id)
    assert restored.deletion_state == DeletionState.ACTIVE
    # Lifecycle is preserved across the round-trip — restore is not a silent reactivate.
    assert restored.lifecycle_state == "deprecated"
    assert root.entity_id in await _catalog_ids(session, OWNER)
