"""GAP-03 Add Package -> derive Strategy Draft from Package (doc 01 §8.2, doc 08 §4.3).

Exercised against a real database (auto-skips when no PostgreSQL is reachable, see
tests/integration/conftest.py). Covers the canonical cross-owner reuse path:

* A viewer derives their OWN strategy root+draft from a usable *foreign* published
  Strategy Package; the new draft records ``source_provenance`` (pinned source
  root+revision+content_hash + the inherited dependency list) and the source package
  is untouched (no new package revision).
* The exact revision is pinned (explicit id or head; no "latest" leak).
* Guards: a non-usable revision (validation not passed / deprecated) -> 422
  PACKAGE_NOT_DERIVABLE; a non-Strategy kind -> 422; a foreign PRIVATE package -> 403;
  a revision id that belongs to another root -> 404; a missing root -> 404.
* Idempotency: a repeated key returns the same draft (one root, one draft).
* FK insert order (L1): draft + strategy_root + work_object + registry all persist.
"""

from __future__ import annotations

import pytest
from sqlalchemy import func, select

from entropia.application.commands import strategy_draft as strat_cmd
from entropia.application.queries import strategy as strat_query
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
    Principal,
    StrategyEditorDraft,
    StrategyRoot,
    WorkObjectRoot,
)
from entropia.infrastructure.postgres.repositories import packages as pkg_repo
from entropia.shared.errors import (
    AccessDeniedError,
    PackageNotDerivableError,
    PackageNotFound,
)

pytestmark = pytest.mark.integration

OWNER = Actor(principal_id="user_owner", principal_type=PrincipalType.HUMAN, role=Role.USER)
DERIVER = Actor(principal_id="user_deriver", principal_type=PrincipalType.HUMAN, role=Role.USER)

_DEPS = {"resolved": [{"canonical_key": "ta.sma"}, {"canonical_key": "ta.rsi"}]}


async def _seed_principals(session) -> None:
    for pid in ("user_owner", "user_deriver"):
        if await session.get(Principal, pid) is None:
            session.add(Principal(principal_id=pid, principal_type=PrincipalType.HUMAN))
    await session.flush()


async def _make_pkg(
    session,
    *,
    owner: str = "user_owner",
    kind: PackageKind = PackageKind.STRATEGY,
    visibility: VisibilityScope = VisibilityScope.PUBLISHED,
    validation: PackageValidationState = PackageValidationState.PASSED,
    lifecycle_state: str | None = "active",
    name: str = "Reusable Trend Strategy",
    deps: dict | None = None,
):
    root, detail, revision = await pkg_repo.create_package(
        session,
        owner_principal_id=owner,
        created_by_principal_id=owner,
        package_kind=kind,
        input_contract={"name": name},
        output_contract={"output_kinds": ["strategy"]},
        dependency_snapshot=_DEPS if deps is None else deps,
        visibility_scope=visibility,
        validation_state=validation,
        approval_state=ApprovalState.DRAFT,
        lifecycle_state=lifecycle_state,
    )
    await session.flush()
    return root, detail, revision


async def test_derive_from_foreign_published_package_carries_provenance(session) -> None:
    await _seed_principals(session)
    root, _detail, revision = await _make_pkg(session)
    await session.commit()

    result = await strat_cmd.derive_strategy_draft_from_package(
        session, DERIVER, source_package_root_id=root.entity_id, idempotency_key="k1"
    )
    await session.commit()

    # Return payload carries provenance with the exact pinned source.
    prov = result["source_provenance"]
    assert prov["source_package_root_id"] == root.entity_id
    assert prov["source_package_revision_id"] == revision.revision_id
    assert prov["source_content_hash"] == revision.content_hash
    assert prov["source_package_kind"] == "strategy"
    assert prov["inherited_dependencies"] == _DEPS
    assert result["display_name"] == "Reusable Trend Strategy"
    assert result["row_version"] == 0  # fresh draft

    # The new strategy root is owned by the DERIVER, not the package owner.
    new_root = await session.get(EntityRegistry, result["strategy_root_id"])
    assert new_root is not None
    assert new_root.owner_principal_id == "user_deriver"

    # Persisted draft carries the same provenance (survives the tx) — surfaced by the query.
    draft = await session.get(StrategyEditorDraft, result["draft_id"])
    assert draft is not None
    assert draft.source_provenance == prov
    assert draft.payload == {}  # empty editable config (honest boundary)
    view = await strat_query.get_strategy_draft(session, DERIVER, result["draft_id"])
    assert view["source_provenance"] == prov

    # FK insert order (L1): the shared root + both details + draft all persist.
    assert await session.get(StrategyRoot, result["strategy_root_id"]) is not None
    assert await session.get(WorkObjectRoot, result["strategy_root_id"]) is not None

    # The source package is untouched — still exactly one revision, same head.
    pkg_rev_count = await session.scalar(
        select(func.count())
        .select_from(EntityRegistry)
        .where(EntityRegistry.entity_id == root.entity_id)
    )
    assert pkg_rev_count == 1
    src_root = await session.get(EntityRegistry, root.entity_id)
    assert src_root is not None and src_root.current_revision_id == revision.revision_id

    # Audit + outbox written in the same tx.
    audit = await session.scalar(
        select(AuditEvent).where(AuditEvent.event_kind == "strategy.derived_from_package")
    )
    assert audit is not None
    outbox = await session.scalar(
        select(OutboxEvent).where(OutboxEvent.event_type == "strategy.derived_from_package")
    )
    assert outbox is not None


async def test_explicit_revision_pin_and_wrong_root_rejected(session) -> None:
    await _seed_principals(session)
    root_a, _da, rev_a = await _make_pkg(session, name="A")
    _root_b, _db, rev_b = await _make_pkg(session, name="B")
    await session.commit()

    # Explicit revision of the SAME root is pinned exactly.
    result = await strat_cmd.derive_strategy_draft_from_package(
        session,
        DERIVER,
        source_package_root_id=root_a.entity_id,
        source_package_revision_id=rev_a.revision_id,
        idempotency_key="k-explicit",
    )
    await session.commit()
    assert result["source_provenance"]["source_package_revision_id"] == rev_a.revision_id

    # A revision id belonging to ANOTHER root is a 404 (no cross-root pinning).
    with pytest.raises(PackageNotFound):
        await strat_cmd.derive_strategy_draft_from_package(
            session,
            DERIVER,
            source_package_root_id=root_a.entity_id,
            source_package_revision_id=rev_b.revision_id,
            idempotency_key="k-wrong",
        )


async def test_non_usable_revision_is_rejected(session) -> None:
    await _seed_principals(session)
    failed, _d, _r = await _make_pkg(session, validation=PackageValidationState.FAILED)
    deprecated, _d2, _r2 = await _make_pkg(session, lifecycle_state="deprecated")
    await session.commit()

    with pytest.raises(PackageNotDerivableError):
        await strat_cmd.derive_strategy_draft_from_package(
            session, DERIVER, source_package_root_id=failed.entity_id
        )
    with pytest.raises(PackageNotDerivableError):
        await strat_cmd.derive_strategy_draft_from_package(
            session, DERIVER, source_package_root_id=deprecated.entity_id
        )


async def test_non_strategy_kind_is_rejected(session) -> None:
    await _seed_principals(session)
    indicator, _d, _r = await _make_pkg(session, kind=PackageKind.INDICATOR)
    await session.commit()
    with pytest.raises(PackageNotDerivableError):
        await strat_cmd.derive_strategy_draft_from_package(
            session, DERIVER, source_package_root_id=indicator.entity_id
        )


async def test_foreign_private_package_is_forbidden(session) -> None:
    await _seed_principals(session)
    private, _d, _r = await _make_pkg(session, visibility=VisibilityScope.PRIVATE)
    await session.commit()
    with pytest.raises(AccessDeniedError):
        await strat_cmd.derive_strategy_draft_from_package(
            session, DERIVER, source_package_root_id=private.entity_id
        )


async def test_missing_root_is_not_found(session) -> None:
    await _seed_principals(session)
    await session.commit()
    with pytest.raises(PackageNotFound):
        await strat_cmd.derive_strategy_draft_from_package(
            session, DERIVER, source_package_root_id="pkg_does_not_exist"
        )


async def test_idempotent_repeat_returns_same_draft(session) -> None:
    await _seed_principals(session)
    root, _d, _r = await _make_pkg(session)
    await session.commit()

    first = await strat_cmd.derive_strategy_draft_from_package(
        session, DERIVER, source_package_root_id=root.entity_id, idempotency_key="dup"
    )
    await session.commit()
    second = await strat_cmd.derive_strategy_draft_from_package(
        session, DERIVER, source_package_root_id=root.entity_id, idempotency_key="dup"
    )
    await session.commit()

    assert first["draft_id"] == second["draft_id"]
    draft_count = await session.scalar(select(func.count()).select_from(StrategyEditorDraft))
    assert draft_count == 1
