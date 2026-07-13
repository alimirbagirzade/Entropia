"""Stage 2f Package Library catalog — exercised against a real database.

Auto-skips when no PostgreSQL is reachable (see tests/integration/conftest.py).
Covers: Guests are blocked; role-aware SERVER-SIDE visibility (admin sees all; a
user sees own + published, never another user's private draft); facet filters
(type / rationale family / unassigned); the ten-flag permission projection and
N/A performance metrics (L4); the detail projection with 403 on a foreign private
package and 404 on a soft-deleted one; and cursor pagination.
"""

from __future__ import annotations

import pytest

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
from entropia.domain.package.catalog import UNASSIGNED, parse_catalog_filters
from entropia.domain.package.enums import PackageValidationState
from entropia.infrastructure.postgres.models import Principal
from entropia.infrastructure.postgres.repositories import packages as pkg_repo
from entropia.shared.errors import AccessDeniedError, NotFoundError, UnauthenticatedError
from entropia.shared.pagination import PageParams

pytestmark = pytest.mark.integration

ADMIN = Actor(principal_id="user_admin", principal_type=PrincipalType.HUMAN, role=Role.ADMIN)
USER1 = Actor(principal_id="user_1", principal_type=PrincipalType.HUMAN, role=Role.USER)
USER2 = Actor(principal_id="user_2", principal_type=PrincipalType.HUMAN, role=Role.USER)


async def _seed_principals(session) -> None:
    for pid in ("user_admin", "user_1", "user_2"):
        if await session.get(Principal, pid) is None:
            session.add(Principal(principal_id=pid, principal_type=PrincipalType.HUMAN))
    await session.flush()


async def _create_pkg(
    session,
    *,
    owner: str,
    kind: PackageKind = PackageKind.INDICATOR,
    visibility: VisibilityScope = VisibilityScope.PRIVATE,
    validation: PackageValidationState = PackageValidationState.PASSED,
    approval: ApprovalState = ApprovalState.DRAFT,
    name: str = "Pkg",
    family: dict | None = None,
) -> str:
    root, _detail, _revision = await pkg_repo.create_package(
        session,
        owner_principal_id=owner,
        created_by_principal_id=owner,
        package_kind=kind,
        input_contract={"name": name},
        output_contract={"output_kinds": ["signal"]},
        dependency_snapshot={},
        visibility_scope=visibility,
        rationale_family_snapshot=family,
        validation_state=validation,
        approval_state=approval,
    )
    return root.entity_id


async def _list(session, actor, **filter_kwargs):
    return await library_query.list_packages(
        session, actor, PageParams(limit=50), filters=parse_catalog_filters(**filter_kwargs)
    )


async def test_guest_is_blocked_from_catalog(session) -> None:
    await _seed_principals(session)
    await _create_pkg(session, owner="user_1", visibility=VisibilityScope.PUBLISHED)
    await session.commit()
    with pytest.raises(UnauthenticatedError):
        await _list(session, Actor.anonymous())


async def test_visibility_is_enforced_server_side(session) -> None:
    await _seed_principals(session)
    own = await _create_pkg(session, owner="user_1", visibility=VisibilityScope.PRIVATE, name="Own")
    shared = await _create_pkg(
        session, owner="user_2", visibility=VisibilityScope.PUBLISHED, name="Shared"
    )
    system = await _create_pkg(
        session, owner="user_2", visibility=VisibilityScope.SYSTEM, name="System"
    )
    explicit = await _create_pkg(
        session, owner="user_2", visibility=VisibilityScope.EXPLICITLY_SHARED, name="Explicit"
    )
    hidden = await _create_pkg(
        session, owner="user_2", visibility=VisibilityScope.PRIVATE, name="Hidden"
    )
    await session.commit()

    admin_ids = {row["entity_id"] for row in (await _list(session, ADMIN))["data"]}
    assert {own, shared, system, explicit, hidden} <= admin_ids

    user1_ids = {row["entity_id"] for row in (await _list(session, USER1))["data"]}
    assert own in user1_ids  # own private draft
    # published / system are readable to any authenticated actor (mirrors identity
    # policy can_view); pins every entry of _CATALOG_VISIBLE_SCOPES.
    assert shared in user1_ids
    assert system in user1_ids
    # GAP-17: an explicitly_shared package is NO LONGER blanket-visible to every
    # authenticated actor — user_1 holds no share grant for user_2's package, so
    # it is excluded server-side (the over-share hole is closed).
    assert explicit not in user1_ids
    assert hidden not in user1_ids  # another user's private draft is hidden server-side


async def test_type_and_family_filters(session) -> None:
    await _seed_principals(session)
    fam = {"rationale_family_id": "rf_reversal", "display_name": "Reversal"}
    cond = await _create_pkg(
        session,
        owner="user_1",
        kind=PackageKind.CONDITION,
        visibility=VisibilityScope.PUBLISHED,
        name="Cond",
    )
    ind = await _create_pkg(
        session,
        owner="user_1",
        kind=PackageKind.INDICATOR,
        visibility=VisibilityScope.PUBLISHED,
        name="Ind",
        family=fam,
    )
    await session.commit()

    conditions = (await _list(session, USER1, package_type="condition"))["data"]
    assert {r["entity_id"] for r in conditions} == {cond}

    reversal = (await _list(session, USER1, rationale_family_id="rf_reversal"))["data"]
    assert {r["entity_id"] for r in reversal} == {ind}

    unassigned_ids = {
        r["entity_id"]
        for r in (await _list(session, USER1, rationale_family_id=UNASSIGNED))["data"]
    }
    assert cond in unassigned_ids
    assert ind not in unassigned_ids


async def test_status_facet_and_text_filters(session) -> None:
    await _seed_principals(session)
    passed = await _create_pkg(
        session,
        owner="user_1",
        visibility=VisibilityScope.PUBLISHED,
        validation=PackageValidationState.PASSED,
        approval=ApprovalState.APPROVED,
        name="Momentum",
    )
    failed = await _create_pkg(
        session,
        owner="user_1",
        visibility=VisibilityScope.PRIVATE,
        validation=PackageValidationState.FAILED,
        approval=ApprovalState.DRAFT,
        name="Reversal",
    )
    old = await _create_pkg(
        session,
        owner="user_1",
        visibility=VisibilityScope.PUBLISHED,
        validation=PackageValidationState.WARNING,
        approval=ApprovalState.DRAFT,
        name="OldOne",
    )
    old_root = await pkg_repo.get_package_root(session, old)
    assert old_root is not None
    old_root.lifecycle_state = "deprecated"
    await session.commit()

    async def ids(**f) -> set[str]:
        return {r["entity_id"] for r in (await _list(session, USER1, **f))["data"]}

    # validation_state + approval_state read off PackageRevision (not PackageRoot).
    assert await ids(validation_state="passed") == {passed}
    assert await ids(approval_state="approved") == {passed}
    # visibility_scope reads off PackageRoot.
    assert await ids(visibility_scope="private") == {failed}
    # lifecycle_state reads off EntityRegistry; deprecated roots stay discoverable.
    assert await ids(lifecycle_state="deprecated") == {old}
    # free-text query: ILIKE on input_contract->>'name'.
    assert await ids(query="moment") == {passed}


async def test_permission_projection_on_rows(session) -> None:
    await _seed_principals(session)
    pkg = await _create_pkg(session, owner="user_1", visibility=VisibilityScope.PUBLISHED)
    await session.commit()

    owner_row = (await _list(session, USER1))["data"][0]
    assert owner_row["permissions"]["can_create_revision"] is True
    assert owner_row["permissions"]["can_approve_publish"] is False

    other_row = next(r for r in (await _list(session, USER2))["data"] if r["entity_id"] == pkg)
    assert other_row["permissions"]["can_derive"] is True
    assert other_row["permissions"]["can_create_revision"] is False

    admin_row = next(r for r in (await _list(session, ADMIN))["data"] if r["entity_id"] == pkg)
    assert admin_row["permissions"]["can_view"] is True
    # Non-Strategy performance metrics are N/A, never fabricated zeros (L4).
    assert admin_row["performance"]["net_profit"] == "not_applicable"


async def test_detail_projection_and_guards(session) -> None:
    await _seed_principals(session)
    fam = {"rationale_family_id": "rf_reversal", "display_name": "Reversal"}
    pkg = await _create_pkg(
        session, owner="user_1", visibility=VisibilityScope.PRIVATE, name="Detailed", family=fam
    )
    private_other = await _create_pkg(session, owner="user_2", visibility=VisibilityScope.PRIVATE)
    await session.commit()

    detail = await library_query.get_package_detail(session, USER1, entity_id=pkg)
    assert detail["name"] == "Detailed"
    assert detail["rationale_family"]["id"] == "rf_reversal"
    assert "input_contract" in detail
    assert len(detail["revisions"]) == 1

    # A foreign private package is forbidden, not merely empty (doc 08 §9.2).
    with pytest.raises(AccessDeniedError):
        await library_query.get_package_detail(session, USER1, entity_id=private_other)


async def test_soft_deleted_package_is_not_discoverable(session) -> None:
    await _seed_principals(session)
    pkg = await _create_pkg(session, owner="user_1", visibility=VisibilityScope.PUBLISHED)
    await session.commit()

    root = await pkg_repo.get_package_root(session, pkg)
    assert root is not None
    root.deletion_state = DeletionState.SOFT_DELETED
    await session.commit()

    listed = {r["entity_id"] for r in (await _list(session, USER1))["data"]}
    assert pkg not in listed
    with pytest.raises(NotFoundError):
        await library_query.get_package_detail(session, USER1, entity_id=pkg)


async def test_cursor_pagination(session) -> None:
    await _seed_principals(session)
    created = [
        await _create_pkg(
            session, owner="user_1", visibility=VisibilityScope.PUBLISHED, name=f"P{i}"
        )
        for i in range(3)
    ]
    await session.commit()
    newest_first = sorted(created, reverse=True)  # entity_id is time-sortable; list is desc

    first = await library_query.list_packages(
        session, USER1, PageParams(limit=2), filters=parse_catalog_filters()
    )
    page1 = [r["entity_id"] for r in first["data"]]
    assert page1 == newest_first[:2]  # pins newest-first descending order
    assert first["meta"]["has_more"] is True
    assert first["meta"]["cursor"] is not None

    second = await library_query.list_packages(
        session,
        USER1,
        PageParams(cursor=first["meta"]["cursor"], limit=2),
        filters=parse_catalog_filters(),
    )
    page2 = [r["entity_id"] for r in second["data"]]
    assert page2 == newest_first[2:]  # the remaining (lowest) id
    assert second["meta"]["has_more"] is False
    assert set(page1).isdisjoint(page2)
    assert set(page1) | set(page2) == set(created)
