"""O-10: Package Library publish rejects a dependency cycle (doc 08 §10, §13, §14).

Exercised against a real database (auto-skips when no PostgreSQL is reachable, see
tests/integration/conftest.py). Closes the gap that ``approve_and_publish_package``
checked head/validation/approval state but never walked the dependency graph, so an
``A -> B -> A`` package pair could reach PUBLISHED. doc 08 §14 "Dependency cycle":

    Publish attempt creates A -> B -> A dependency path.
    -> Server rejects publish; diagnostic identifies cycle path; UI preserves draft
       for repair.

Covered here: the two-package cycle with its cycle-path diagnostic and the untouched
draft; a self-referencing revision; an acyclic dependency that still publishes; and
the no-false-positive proof that an ESP resolver snapshot (doc 09 — a different
registry) is not a package edge. The shared guard is also driven directly, because
the Create-Package publish surface calls the same function.
"""

from __future__ import annotations

import pytest
from sqlalchemy import func, select

from entropia.application.commands import package_lifecycle as pkg_cmd
from entropia.application.queries.package_dependency import (
    collect_root_edges,
    ensure_no_dependency_cycle,
)
from entropia.domain.identity import Actor
from entropia.domain.lifecycle.enums import (
    ApprovalState,
    PackageKind,
    PrincipalType,
    Role,
    VisibilityScope,
)
from entropia.domain.package.enums import PackageValidationState
from entropia.infrastructure.postgres.models import ApprovalDecision, AuditEvent, Principal
from entropia.infrastructure.postgres.repositories import packages as pkg_repo
from entropia.shared.errors import ErrorCategory, PackageDependencyCycle

pytestmark = pytest.mark.integration

OWNER = Actor(principal_id="user_owner", principal_type=PrincipalType.HUMAN, role=Role.USER)
ADMIN = Actor(principal_id="user_admin", principal_type=PrincipalType.HUMAN, role=Role.ADMIN)


async def _seed_principals(session) -> None:
    for principal_id in ("user_owner", "user_admin"):
        if await session.get(Principal, principal_id) is None:
            session.add(Principal(principal_id=principal_id, principal_type=PrincipalType.HUMAN))
    await session.flush()


async def _make_pkg(session, *, name: str, dependency_snapshot: dict | None = None):
    """Create an owned, validation-PASSED root with the given pinned dependencies."""
    root, _detail, revision = await pkg_repo.create_package(
        session,
        owner_principal_id="user_owner",
        created_by_principal_id="user_owner",
        package_kind=PackageKind.INDICATOR,
        input_contract={"name": name},
        output_contract={"output_kinds": ["directional_signal"]},
        dependency_snapshot=dependency_snapshot or {},
        visibility_scope=VisibilityScope.PRIVATE,
        validation_state=PackageValidationState.PASSED,
        approval_state=ApprovalState.DRAFT,
    )
    await session.flush()
    return root, revision


def _pin(root_id: str, revision_id: str) -> dict:
    """The canonical exact-revision package dependency claim (doc 08 §9.1, §13)."""
    return {"packages": [{"package_root_id": root_id, "package_revision_id": revision_id}]}


async def _append_passed_revision(session, root, dependency_snapshot: dict):
    """Append revision N+1 through the real command, then mark it validation-PASSED
    so the publish attempt fails on the DEPENDENCY gate rather than on evidence."""
    appended = await pkg_cmd.create_package_revision(
        session,
        OWNER,
        entity_id=root.entity_id,
        dependency_snapshot=dependency_snapshot,
    )
    await session.flush()
    revision = await pkg_repo.get_revision(session, appended["revision_id"])
    assert revision is not None
    revision.validation_state = PackageValidationState.PASSED
    await session.flush()
    return revision


async def _request_approval(session, root, revision_id: str) -> None:
    await pkg_cmd.request_package_approval(
        session, OWNER, entity_id=root.entity_id, revision_id=revision_id
    )
    await session.flush()


async def _count(session, model, **filters) -> int:
    stmt = select(func.count()).select_from(model)
    for column, value in filters.items():
        stmt = stmt.where(getattr(model, column) == value)
    return int((await session.execute(stmt)).scalar_one())


# --------------------------------------------------------------------------- #
# doc 08 §14 — "Dependency cycle"                                              #
# --------------------------------------------------------------------------- #


async def test_publish_rejects_a_b_a_cycle_and_names_the_cycle_path(session) -> None:
    await _seed_principals(session)
    # A(rev1) has no dependency yet; B pins A(rev1); then A(rev2) pins B -> A -> B -> A.
    root_a, rev_a1 = await _make_pkg(session, name="Alpha")
    root_b, rev_b1 = await _make_pkg(
        session, name="Beta", dependency_snapshot=_pin(root_a.entity_id, rev_a1.revision_id)
    )
    rev_a2 = await _append_passed_revision(
        session, root_a, _pin(root_b.entity_id, rev_b1.revision_id)
    )
    await _request_approval(session, root_a, rev_a2.revision_id)

    with pytest.raises(PackageDependencyCycle) as raised:
        await pkg_cmd.approve_and_publish_package(
            session, ADMIN, entity_id=root_a.entity_id, revision_id=rev_a2.revision_id
        )

    # The diagnostic identifies the cycle PATH, not merely "rejected" (doc 08 §14).
    assert raised.value.code == "PACKAGE_DEPENDENCY_CYCLE"
    assert raised.value.http_status == 409
    assert raised.value.cycle_path == (root_a.entity_id, root_b.entity_id, root_a.entity_id)
    assert raised.value.details[0]["cycle_path"] == [
        root_a.entity_id,
        root_b.entity_id,
        root_a.entity_id,
    ]
    # O-02 recovery envelope: a cycle is a dependency-validation failure that the
    # same request can never retry into success, and the raise site pins the exact
    # revision + field that failed.
    assert raised.value.category == ErrorCategory.DEPENDENCY_VALIDATION
    assert raised.value.retryable is False
    assert raised.value.suggested_action == "repair_dependency_graph"
    assert raised.value.scope_type == "PackageRevision"
    assert raised.value.scope_id == rev_a2.revision_id
    assert raised.value.field_path == "dependency_snapshot"


async def test_rejected_publish_leaves_the_draft_untouched_for_repair(session) -> None:
    await _seed_principals(session)
    root_a, rev_a1 = await _make_pkg(session, name="Alpha")
    root_b, rev_b1 = await _make_pkg(
        session, name="Beta", dependency_snapshot=_pin(root_a.entity_id, rev_a1.revision_id)
    )
    rev_a2 = await _append_passed_revision(
        session, root_a, _pin(root_b.entity_id, rev_b1.revision_id)
    )
    await _request_approval(session, root_a, rev_a2.revision_id)

    with pytest.raises(PackageDependencyCycle):
        await pkg_cmd.approve_and_publish_package(
            session, ADMIN, entity_id=root_a.entity_id, revision_id=rev_a2.revision_id
        )
    await session.flush()

    # The gate runs BEFORE any mutation: the head stays requested + private, and no
    # approval proof or published audit is written (doc 08 §14 "UI preserves draft").
    head = await pkg_repo.get_revision(session, rev_a2.revision_id)
    detail = await pkg_repo.get_package_detail(session, root_a.entity_id)
    assert head is not None and head.approval_state == ApprovalState.APPROVAL_REQUESTED
    assert detail is not None and detail.visibility_scope == VisibilityScope.PRIVATE
    assert await _count(session, ApprovalDecision, target_entity_id=root_a.entity_id) == 0
    assert await _count(session, AuditEvent, event_kind="package.approved_published") == 0


async def test_publish_rejects_a_revision_that_pins_its_own_root(session) -> None:
    await _seed_principals(session)
    root, rev1 = await _make_pkg(session, name="Ouroboros")
    rev2 = await _append_passed_revision(session, root, _pin(root.entity_id, rev1.revision_id))
    await _request_approval(session, root, rev2.revision_id)

    with pytest.raises(PackageDependencyCycle) as raised:
        await pkg_cmd.approve_and_publish_package(
            session, ADMIN, entity_id=root.entity_id, revision_id=rev2.revision_id
        )

    assert raised.value.cycle_path == (root.entity_id, root.entity_id)


async def test_publish_rejects_a_three_package_cycle(session) -> None:
    await _seed_principals(session)
    root_a, rev_a1 = await _make_pkg(session, name="Alpha")
    root_b, rev_b1 = await _make_pkg(
        session, name="Beta", dependency_snapshot=_pin(root_a.entity_id, rev_a1.revision_id)
    )
    root_c, rev_c1 = await _make_pkg(
        session, name="Gamma", dependency_snapshot=_pin(root_b.entity_id, rev_b1.revision_id)
    )
    rev_a2 = await _append_passed_revision(
        session, root_a, _pin(root_c.entity_id, rev_c1.revision_id)
    )
    await _request_approval(session, root_a, rev_a2.revision_id)

    with pytest.raises(PackageDependencyCycle) as raised:
        await pkg_cmd.approve_and_publish_package(
            session, ADMIN, entity_id=root_a.entity_id, revision_id=rev_a2.revision_id
        )

    assert raised.value.cycle_path == (
        root_a.entity_id,
        root_c.entity_id,
        root_b.entity_id,
        root_a.entity_id,
    )


# --------------------------------------------------------------------------- #
# No false positives — the gate must not block legitimate publishes            #
# --------------------------------------------------------------------------- #


async def test_acyclic_dependency_still_publishes(session) -> None:
    await _seed_principals(session)
    _root_leaf, rev_leaf = await _make_pkg(session, name="Leaf")
    root_top, _rev_top = await _make_pkg(
        session, name="Top", dependency_snapshot=_pin(_root_leaf.entity_id, rev_leaf.revision_id)
    )
    head = root_top.current_revision_id or ""
    await _request_approval(session, root_top, head)

    result = await pkg_cmd.approve_and_publish_package(
        session, ADMIN, entity_id=root_top.entity_id, revision_id=head
    )
    await session.flush()

    assert result["approval_state"] == str(ApprovalState.APPROVED)
    assert result["visibility_scope"] == str(VisibilityScope.PUBLISHED)


async def test_embedded_resolver_snapshot_is_not_a_package_cycle(session) -> None:
    """A Create-Package draft pins ESP resolver refs (doc 09), never package roots —
    the gate must let those publish untouched."""
    await _seed_principals(session)
    root, _revision = await _make_pkg(
        session,
        name="Resolver Backed",
        dependency_snapshot={
            "resolved": [
                {
                    "call": "ta.rsi",
                    "canonical_key": "ta.rsi",
                    "embedded_entity_id": "esp_rsi",
                    "embedded_revision_id": "esprev_rsi_1",
                }
            ],
            "scan_id": "scan_1",
        },
    )
    head = root.current_revision_id or ""
    await _request_approval(session, root, head)

    result = await pkg_cmd.approve_and_publish_package(
        session, ADMIN, entity_id=root.entity_id, revision_id=head
    )
    await session.flush()

    assert result["approval_state"] == str(ApprovalState.APPROVED)


# --------------------------------------------------------------------------- #
# The shared guard both publish surfaces call                                  #
# --------------------------------------------------------------------------- #


async def test_shared_guard_resolves_root_edges_from_pinned_revisions(session) -> None:
    await _seed_principals(session)
    root_a, rev_a1 = await _make_pkg(session, name="Alpha")
    root_b, rev_b1 = await _make_pkg(
        session, name="Beta", dependency_snapshot=_pin(root_a.entity_id, rev_a1.revision_id)
    )
    rev_a2 = await _append_passed_revision(
        session, root_a, _pin(root_b.entity_id, rev_b1.revision_id)
    )

    edges = await collect_root_edges(session, revision_id=rev_a2.revision_id)

    # Both legs of the loop are materialized from the exact pinned revisions.
    assert edges == {
        root_a.entity_id: (root_b.entity_id,),
        root_b.entity_id: (root_a.entity_id,),
    }
    with pytest.raises(PackageDependencyCycle):
        await ensure_no_dependency_cycle(
            session, root_id=root_a.entity_id, revision_id=rev_a2.revision_id
        )


async def test_shared_guard_follows_a_root_only_claim_to_the_current_head(session) -> None:
    """A claim that names only a root resolves to that root's CURRENT head — the edge
    a name-only reference would take (doc 08 §13 forbids resolving to "latest" for the
    PIN, but the cycle walk must still see where such a claim points)."""
    await _seed_principals(session)
    root_a, _rev_a1 = await _make_pkg(session, name="Alpha")
    root_b, _rev_b1 = await _make_pkg(
        session,
        name="Beta",
        dependency_snapshot={"packages": [{"package_root_id": root_a.entity_id}]},
    )
    rev_a2 = await _append_passed_revision(
        session, root_a, {"packages": [{"package_root_id": root_b.entity_id}]}
    )

    with pytest.raises(PackageDependencyCycle) as raised:
        await ensure_no_dependency_cycle(
            session, root_id=root_a.entity_id, revision_id=rev_a2.revision_id
        )

    assert raised.value.cycle_path == (root_a.entity_id, root_b.entity_id, root_a.entity_id)


async def test_shared_guard_passes_when_a_pinned_target_is_missing(session) -> None:
    """An unloadable pinned revision ends that leg — an unresolved dependency is the
    separate PACKAGE_DEPENDENCY_UNRESOLVED gate, not a fabricated cycle."""
    await _seed_principals(session)
    root, revision = await _make_pkg(
        session, name="Dangling", dependency_snapshot=_pin("pkg_missing", "pkgrev_missing")
    )

    await ensure_no_dependency_cycle(
        session, root_id=root.entity_id, revision_id=revision.revision_id
    )
