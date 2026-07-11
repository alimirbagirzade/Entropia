"""Stage 7b follow-up — Future Dev operational output HISTORY read surface
(doc 22 §7, §13). Auto-skips without PostgreSQL.

Covers the owner-scoped, ACTIVE-only, newest-first keyset projections that make
the outputs the operational POSTs create readable: View Dataset + Analysis
Artifact list/detail, cross-owner isolation (existence never leaks, not-found),
soft-delete exclusion, keyset paging, artifact-type narrowing, and the
futureDevNoHistory.empty empty page. Ordering is asserted against the id-DESC
contract itself (``sorted(ids, reverse=True)``) so it never depends on two
same-millisecond ids resolving in creation order.
"""

from __future__ import annotations

import pytest

from entropia.application.commands.capability import (
    create_analysis_artifact,
    query_view_dataset,
    transition_capability,
)
from entropia.application.queries.capability import (
    get_analysis_artifact,
    get_view_dataset,
    list_analysis_artifacts,
    list_view_datasets,
)
from entropia.domain.capability.baseline import initial_dependency_snapshot
from entropia.domain.capability.enums import BACKTEST_REVIEW, GRAPHIC_VIEW, ActivationGate
from entropia.domain.identity import Actor
from entropia.domain.lifecycle.enums import DeletionState, PrincipalType, Role
from entropia.infrastructure.postgres.models import Principal, ViewDataset
from entropia.infrastructure.postgres.repositories import capability as capability_repo
from entropia.shared.errors import (
    AnalysisArtifactNotFoundError,
    ViewDatasetNotFoundError,
)

pytestmark = pytest.mark.integration

ADMIN = Actor(
    principal_id="user_admin",
    principal_type=PrincipalType.HUMAN,
    role=Role.ADMIN,
    correlation_id="corr_adm",
)
USER = Actor(principal_id="user_1", principal_type=PrincipalType.HUMAN, role=Role.USER)
OTHER = Actor(principal_id="user_2", principal_type=PrincipalType.HUMAN, role=Role.USER)

GATES_WITHOUT_UI = {"gates": {gate.value: gate is not ActivationGate.UI for gate in ActivationGate}}


async def _seed(session) -> None:
    for actor in (ADMIN, USER, OTHER):
        session.add(Principal(principal_id=actor.principal_id, principal_type=actor.principal_type))
    await capability_repo.seed_baseline_capabilities(session)
    await session.commit()


async def _walk_to_limited(session, key: str) -> None:
    """placeholder -> designed -> internal -> shadow -> limited (legal chain)."""
    steps = (
        ("designed", 1, initial_dependency_snapshot()),
        ("internal", 2, None),
        ("shadow", 3, None),
        ("limited", 4, GATES_WITHOUT_UI),
    )
    for to_state, expected, snapshot in steps:
        await transition_capability(
            session,
            ADMIN,
            capability_key=key,
            to_state=to_state,
            reason=f"activate {key} to {to_state}",
            expected_registry_version=expected,
            dependency_snapshot=snapshot,
            idempotency_key=f"{key}-{to_state}",
        )
    await session.commit()


async def _prepare_view_dataset(session, actor: Actor, ref: str, *, idem: str) -> str:
    result = await query_view_dataset(
        session,
        actor,
        source_manifest_refs=[ref],
        schema_version="v1",
        idempotency_key=idem,
    )
    return result["view_dataset_id"]


async def _create_artifact(
    session, actor: Actor, artifact_type: str, ref: str, *, idem: str
) -> str:
    result = await create_analysis_artifact(
        session,
        actor,
        artifact_type=artifact_type,
        input_manifest_refs=[ref],
        method_version=f"{artifact_type}-v1",
        idempotency_key=idem,
    )
    return result["artifact_id"]


# --------------------------------------------------------------------------- #
# View Dataset output history                                                  #
# --------------------------------------------------------------------------- #


async def test_view_dataset_history_owner_scoped_newest_first(session) -> None:
    await _seed(session)
    await _walk_to_limited(session, GRAPHIC_VIEW)
    first = await _prepare_view_dataset(session, USER, "r1", idem="u-vds-1")
    second = await _prepare_view_dataset(session, USER, "r2", idem="u-vds-2")
    # OTHER prepares one too — it must never leak into USER's history.
    await _prepare_view_dataset(session, OTHER, "r3", idem="o-vds-1")
    await session.commit()

    page = await list_view_datasets(session, USER)
    ids = [row["view_dataset_id"] for row in page["data"]]
    assert ids == sorted([first, second], reverse=True)  # id-DESC contract
    assert page["meta"]["has_more"] is False
    assert page["meta"]["cursor"] is None
    assert all(row["capability_key"] == GRAPHIC_VIEW for row in page["data"])
    assert all(row["deletion_state"] == "active" for row in page["data"])


async def test_view_dataset_history_keyset_pages(session) -> None:
    await _seed(session)
    await _walk_to_limited(session, GRAPHIC_VIEW)
    ids = [await _prepare_view_dataset(session, USER, f"r{i}", idem=f"u-vds-{i}") for i in range(3)]
    await session.commit()
    expected = sorted(ids, reverse=True)

    page1 = await list_view_datasets(session, USER, limit=2)
    assert [row["view_dataset_id"] for row in page1["data"]] == expected[:2]
    assert page1["meta"]["has_more"] is True
    cursor = page1["meta"]["cursor"]
    assert cursor is not None

    page2 = await list_view_datasets(session, USER, cursor=cursor, limit=2)
    assert [row["view_dataset_id"] for row in page2["data"]] == expected[2:]
    assert page2["meta"]["has_more"] is False
    assert page2["meta"]["cursor"] is None


async def test_view_dataset_detail_owner_scoped_never_leaks(session) -> None:
    await _seed(session)
    await _walk_to_limited(session, GRAPHIC_VIEW)
    dataset_id = await _prepare_view_dataset(session, USER, "r1", idem="u-vds")
    await session.commit()

    detail = await get_view_dataset(session, USER, view_dataset_id=dataset_id)
    assert detail["view_dataset_id"] == dataset_id
    assert detail["owner_principal_id"] == USER.principal_id
    assert detail["source_manifest_refs"] == ["r1"]

    # Cross-owner and unknown ids are BOTH reported as not-found (no leak).
    with pytest.raises(ViewDatasetNotFoundError):
        await get_view_dataset(session, OTHER, view_dataset_id=dataset_id)
    with pytest.raises(ViewDatasetNotFoundError):
        await get_view_dataset(session, USER, view_dataset_id="vds_does_not_exist")


async def test_view_dataset_history_excludes_soft_deleted(session) -> None:
    await _seed(session)
    await _walk_to_limited(session, GRAPHIC_VIEW)
    dataset_id = await _prepare_view_dataset(session, USER, "r1", idem="u-vds")
    await session.commit()

    row = await session.get(ViewDataset, dataset_id)
    row.deletion_state = DeletionState.SOFT_DELETED
    await session.commit()

    page = await list_view_datasets(session, USER)
    assert page["data"] == []
    assert page["meta"]["has_more"] is False
    with pytest.raises(ViewDatasetNotFoundError):
        await get_view_dataset(session, USER, view_dataset_id=dataset_id)


# --------------------------------------------------------------------------- #
# Analysis Artifact output history                                             #
# --------------------------------------------------------------------------- #


async def test_analysis_artifact_history_owner_scoped_and_type_filter(session) -> None:
    await _seed(session)
    await _walk_to_limited(session, BACKTEST_REVIEW)  # gates review/MC/WFA
    review = await _create_artifact(session, USER, "backtest_review", "r1", idem="u-art-1")
    mc = await _create_artifact(session, USER, "monte_carlo", "r2", idem="u-art-2")
    # OTHER's artifact must not leak into USER's history.
    await _create_artifact(session, OTHER, "walk_forward", "r3", idem="o-art-1")
    await session.commit()

    page = await list_analysis_artifacts(session, USER)
    assert {row["artifact_id"] for row in page["data"]} == {review, mc}
    assert page["meta"]["artifact_type"] is None
    assert all(row["capability_key"] == BACKTEST_REVIEW for row in page["data"])

    filtered = await list_analysis_artifacts(session, USER, artifact_type="monte_carlo")
    assert [row["artifact_id"] for row in filtered["data"]] == [mc]
    assert filtered["meta"]["artifact_type"] == "monte_carlo"


async def test_analysis_artifact_detail_owner_scoped_never_leaks(session) -> None:
    await _seed(session)
    await _walk_to_limited(session, BACKTEST_REVIEW)
    artifact_id = await _create_artifact(session, USER, "backtest_review", "r1", idem="u-art")
    await session.commit()

    detail = await get_analysis_artifact(session, USER, artifact_id=artifact_id)
    assert detail["artifact_id"] == artifact_id
    assert detail["capability_key"] == BACKTEST_REVIEW
    assert detail["owner_principal_id"] == USER.principal_id
    assert detail["method_version"] == "backtest_review-v1"

    with pytest.raises(AnalysisArtifactNotFoundError):
        await get_analysis_artifact(session, OTHER, artifact_id=artifact_id)
    with pytest.raises(AnalysisArtifactNotFoundError):
        await get_analysis_artifact(session, USER, artifact_id="aart_does_not_exist")


# --------------------------------------------------------------------------- #
# futureDevNoHistory.empty (doc 22 §7)                                          #
# --------------------------------------------------------------------------- #


async def test_output_history_is_empty_when_no_outputs(session) -> None:
    """An operational capability that has produced nothing yet returns a real
    empty page — the futureDevNoHistory.empty state, never a fabricated row."""
    await _seed(session)
    await _walk_to_limited(session, GRAPHIC_VIEW)

    datasets = await list_view_datasets(session, USER)
    assert datasets["data"] == []
    assert datasets["meta"]["has_more"] is False
    assert datasets["meta"]["cursor"] is None

    artifacts = await list_analysis_artifacts(session, USER)
    assert artifacts["data"] == []
    assert artifacts["meta"]["has_more"] is False
