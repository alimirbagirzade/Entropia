"""R2 (GAP-06 epic slice R2c) Package Library Export: package-revision manifest.

Exercised against a real database (auto-skips when no PostgreSQL is reachable, see
tests/integration/conftest.py). Covers the ``can_export`` action the catalog
advertised but never dispatched (doc 08 §7 "Export", §9.1 ``package_export``). This is
the immutable package-revision MANIFEST — NOT a backtest result_export:

* Any viewer (owner / published / shared) exports a selected revision and gets the
  content-addressed manifest + manifest_hash; a ``package.exported`` audit records the
  hash as durable provenance; the source revision/root is never mutated.
* A foreign PRIVATE source -> 403; a revision not on the root -> 404.
* A repeat under one Idempotency-Key returns the same manifest_hash (no duplicate
  audit); a non-head (older) revision is exportable.
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
from entropia.infrastructure.postgres.models import AuditEvent, Principal
from entropia.infrastructure.postgres.repositories import packages as pkg_repo
from entropia.shared.errors import AccessDeniedError, PackageNotFound

pytestmark = pytest.mark.integration

OWNER = Actor(principal_id="user_owner", principal_type=PrincipalType.HUMAN, role=Role.USER)
OTHER = Actor(principal_id="user_other", principal_type=PrincipalType.HUMAN, role=Role.USER)


async def _seed_principals(session) -> None:
    for pid in ("user_owner", "user_other"):
        if await session.get(Principal, pid) is None:
            session.add(Principal(principal_id=pid, principal_type=PrincipalType.HUMAN))
    await session.flush()


async def _make_pkg(
    session,
    *,
    owner: str = "user_owner",
    visibility: VisibilityScope = VisibilityScope.PUBLISHED,
    name: str = "Exportable RSI",
):
    root, _detail, _revision = await pkg_repo.create_package(
        session,
        owner_principal_id=owner,
        created_by_principal_id=owner,
        package_kind=PackageKind.INDICATOR,
        input_contract={"name": name},
        output_contract={"output_kinds": ["directional_signal"]},
        dependency_snapshot={"resolved": [{"canonical_key": "ta.rsi"}]},
        visibility_scope=visibility,
        validation_state=PackageValidationState.PASSED,
        approval_state=ApprovalState.DRAFT,
    )
    await session.flush()
    return root


async def _count(session, model, **filters) -> int:
    stmt = select(func.count()).select_from(model)
    for column, value in filters.items():
        stmt = stmt.where(getattr(model, column) == value)
    return int((await session.execute(stmt)).scalar_one())


async def test_export_returns_manifest_hash_and_audits_without_mutating_source(session) -> None:
    await _seed_principals(session)
    root = await _make_pkg(session, owner="user_owner")
    head = root.current_revision_id or ""

    result = await pkg_cmd.export_package(
        session, OWNER, entity_id=root.entity_id, revision_id=head
    )
    await session.flush()

    assert result["manifest_hash"].startswith("sha256:") or len(result["manifest_hash"]) == 64
    assert result["manifest"]["revision_id"] == head
    assert result["manifest"]["package_kind"] == str(PackageKind.INDICATOR)
    assert result["manifest"]["name"] == "Exportable RSI"
    assert result["manifest"]["content_hash"]  # the immutable revision digest is carried
    # An export writes an audit provenance row and mutates nothing on the source.
    assert await _count(session, AuditEvent, event_kind="package.exported") == 1
    src = await pkg_repo.get_package_root(session, root.entity_id)
    assert src is not None and src.current_revision_id == head and src.row_version == 1


async def test_viewer_of_published_package_can_export(session) -> None:
    await _seed_principals(session)
    root = await _make_pkg(session, owner="user_owner", visibility=VisibilityScope.PUBLISHED)

    # A non-owner viewer may export a published package (can_export follows can_view).
    result = await pkg_cmd.export_package(
        session, OTHER, entity_id=root.entity_id, revision_id=root.current_revision_id or ""
    )
    assert result["manifest_hash"]


async def test_export_requires_view_permission(session) -> None:
    await _seed_principals(session)
    root = await _make_pkg(session, owner="user_owner", visibility=VisibilityScope.PRIVATE)

    with pytest.raises(AccessDeniedError):
        await pkg_cmd.export_package(
            session, OTHER, entity_id=root.entity_id, revision_id=root.current_revision_id or ""
        )


async def test_export_revision_not_on_root_is_not_found(session) -> None:
    await _seed_principals(session)
    root = await _make_pkg(session, owner="user_owner")

    with pytest.raises(PackageNotFound):
        await pkg_cmd.export_package(
            session, OWNER, entity_id=root.entity_id, revision_id="pkgrev_not_here"
        )


async def test_export_is_idempotent_and_deterministic(session) -> None:
    await _seed_principals(session)
    root = await _make_pkg(session, owner="user_owner")
    head = root.current_revision_id or ""

    first = await pkg_cmd.export_package(
        session, OWNER, entity_id=root.entity_id, revision_id=head, idempotency_key="idem-export-1"
    )
    await session.flush()
    second = await pkg_cmd.export_package(
        session, OWNER, entity_id=root.entity_id, revision_id=head, idempotency_key="idem-export-1"
    )
    await session.flush()

    # The manifest hash is content-addressed and the replay returns the SAME hash with
    # no duplicate audit.
    assert first["manifest_hash"] == second["manifest_hash"]
    assert await _count(session, AuditEvent, event_kind="package.exported") == 1


async def test_older_non_head_revision_is_exportable(session) -> None:
    await _seed_principals(session)
    root = await _make_pkg(session, owner="user_owner")
    base = root.current_revision_id or ""
    # Advance the head so `base` is no longer current, then export the OLD revision.
    await pkg_cmd.create_package_revision(session, OWNER, entity_id=root.entity_id)
    await session.flush()
    refreshed = await pkg_repo.get_package_root(session, root.entity_id)
    assert refreshed is not None and refreshed.current_revision_id != base

    result = await pkg_cmd.export_package(
        session, OWNER, entity_id=root.entity_id, revision_id=base
    )
    assert result["manifest"]["revision_id"] == base  # a pinned historical export
