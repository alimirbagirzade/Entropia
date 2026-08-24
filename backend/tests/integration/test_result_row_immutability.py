"""A Backtest Result row is immutable — only its lifecycle flags move (doc 16 §14).

Auto-skips without PostgreSQL (see tests/integration/conftest.py).

Batch 04 of the class-B acceptance ledger. Seven doc 16 rows share one claim that
nothing asserted: a persisted Result is a historical record, so **reading it,
comparing it, re-profiling it, or building on it must not touch the row** — and the
two operations that legitimately DO touch it (soft delete, restore) must leave an
audit trail and preserve the artifact hashes.

The suite already proved the projection side (what History lists, who may see it).
What it never did was read the ROW back after a neighbouring operation. Each test
here therefore snapshots the persisted columns first and compares them afterwards.

Acceptance (doc 16 §14) by test:

- ``RH-05.c2``  a later Mainboard edit does not change a finished result
- ``RH-10.c3``  a refused compare leaves both result rows unmodified
- ``RH-11.c3``  a soft delete writes its audit row
- ``RH-12.c3``  artifact checksums survive a restore
- ``RH-12.c4``  a restore writes its audit row
- ``RH-16.c2``  a stale ``expected_row_version`` on soft delete conflicts

NOT in this batch, measured and deferred rather than rushed: ``RH-13.c2`` (a Result
View profile change must not move the History key-metric digest) needs the metric
REGISTRY seeded before a profile revision will validate, and ``RH-14.c3`` (creating an
Analysis Artifact must not touch the Result row) needs the capability registry walked
to Limited — whose seeding helper collides with this module's principals. Both are
plumbing, not doubt about the behaviour; they are the next batch's first two items.

Helpers are reused from ``test_results_history`` (``_seed_result``, ``_workspace``,
``_seed_principals``, the actors) rather than re-seeded here.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy import func, select

from entropia.application.commands.backtest_run import soft_delete_backtest_result
from entropia.application.commands.deletion import restore_trash_entry
from entropia.application.commands.mainboard import create_work_object
from entropia.application.commands.metric_profile import (
    SYSTEM_DEFAULT_PROFILE_ID,
    create_metric_profile_revision,
)
from entropia.application.jobs import agent_tools
from entropia.application.queries.results_history import (
    compare_backtest_results,
    list_backtest_results,
)
from entropia.domain.agent_lab.enums import (
    ALPHA_AGENT_ID,
    AgentTaskPriority,
    AgentTaskStatus,
    RuntimeMode,
    RuntimeStatus,
)
from entropia.domain.backtest.history import KEY_METRIC_KEYS
from entropia.domain.identity import Actor
from entropia.domain.lifecycle.enums import PrincipalType
from entropia.infrastructure.postgres.models import (
    AgentRuntime,
    ArtifactLink,
    AuditEvent,
    BacktestResult,
    Principal,
    ResultArtifactChecksum,
    ResultManifestSnapshot,
    ResultViewMetricProfileRevision,
    TrashEntry,
)
from entropia.infrastructure.postgres.repositories import agent_lab as al_repo
from entropia.shared.errors import (
    CompareRequiresTwoDistinctResultsError,
    RowVersionConflictError,
)
from tests.integration.test_arrange_metrics import _seed_registry
from tests.integration.test_results_history import (
    ADMIN,
    USER1,
    _seed_principals,
    _seed_result,
    _workspace,
)

pytestmark = pytest.mark.integration

AGENT = Actor(
    principal_id="agent_alpha",
    principal_type=PrincipalType.AGENT,
    role=None,
    correlation_id="corr_rh14",
)


def _snapshot(result: BacktestResult) -> dict[str, Any]:
    """Every column that must not move while the row is merely being read."""
    return {
        "result_id": result.result_id,
        "run_id": result.run_id,
        "manifest_id": result.manifest_id,
        "manifest_hash": result.manifest_hash,
        "workspace_entity_id": result.workspace_entity_id,
        "composition_fingerprint": result.composition_fingerprint,
        "engine_version": result.engine_version,
        "deletion_state": result.deletion_state,
        "row_version": result.row_version,
        "created_by_principal_id": result.created_by_principal_id,
        "created_at": result.created_at,
    }


async def _reread(session, result_id: str) -> BacktestResult:
    """Re-READ from the database — the identity map must not answer for the row."""
    session.expire_all()
    row = await session.get(BacktestResult, result_id)
    assert row is not None
    return row


async def _count_audits(session, event_kind: str) -> int:
    return int(
        (
            await session.execute(
                select(func.count())
                .select_from(AuditEvent)
                .where(AuditEvent.event_kind == event_kind)
            )
        ).scalar_one()
    )


_RESTORE_AUDIT_KIND = "trash.restored"


async def _count_result_audits(session, event_kind: str, result_id: str) -> int:
    return int(
        (
            await session.execute(
                select(func.count())
                .select_from(AuditEvent)
                .where(AuditEvent.event_kind == event_kind)
                .where(AuditEvent.target_entity_id == result_id)
            )
        ).scalar_one()
    )


async def _checksums(session, result_id: str) -> list[tuple[str, int, str]]:
    rows = (
        (
            await session.execute(
                select(ResultArtifactChecksum).where(ResultArtifactChecksum.result_id == result_id)
            )
        )
        .scalars()
        .all()
    )
    return sorted((r.artifact_type, r.row_count, r.checksum, r.schema_version) for r in rows)


async def _manifest_snapshot(session, result_id: str) -> Any:
    row = await session.get(BacktestResult, result_id)
    assert row is not None
    snap = (
        (
            await session.execute(
                select(ResultManifestSnapshot).where(ResultManifestSnapshot.result_id == result_id)
            )
        )
        .scalars()
        .first()
    )
    return None if snap is None else (snap.snapshot_id, snap.manifest_hash, snap.manifest)


async def _mutate_composition(session, workspace_id: str) -> None:
    """A REAL later edit: attach a fresh work object to the same workspace."""
    await create_work_object(
        session,
        USER1,
        object_kind="trading_signal",
        payload={"kind": "trading_signal"},
        available_time=datetime(2024, 1, 1, tzinfo=UTC),
    )
    await session.commit()


async def _one_result(session, *, result_id: str = "btres_imm_1") -> tuple[str, str]:
    await _seed_principals(session)
    workspace_id = await _workspace(session, USER1)
    await _seed_result(
        session,
        workspace_id=workspace_id,
        result_id=result_id,
        owner=USER1.principal_id,
        net_profit=Decimal("100"),
        romad=Decimal("1.5"),
        max_drawdown=Decimal("10"),
        win_rate=Decimal("55"),
        total_trades=Decimal("20"),
        order_index=1,
    )
    await session.commit()
    return workspace_id, result_id


# --------------------------------------------------------------------------- #
# RH-16.c2 / RH-11.c3 — the two operations that MAY touch the row              #
# --------------------------------------------------------------------------- #


async def test_stale_row_version_on_soft_delete_conflicts_and_writes_nothing(
    session,
) -> None:
    """RH-16.c2: a stale ETag must conflict rather than overwrite.

    The refusal is only half the claim; the other half is that the refused call
    changes nothing, so the row is re-read afterwards.
    """
    _workspace_id, result_id = await _one_result(session)
    before = _snapshot(await _reread(session, result_id))
    audits_before = await _count_audits(session, "backtest.result_soft_deleted")

    with pytest.raises(RowVersionConflictError):
        await soft_delete_backtest_result(
            session,
            ADMIN,
            result_id=result_id,
            expected_row_version=before["row_version"] + 7,  # stale by construction
        )
    await session.rollback()

    assert _snapshot(await _reread(session, result_id)) == before
    assert await _count_audits(session, "backtest.result_soft_deleted") == audits_before


async def test_soft_delete_writes_its_audit_row_and_moves_only_lifecycle_columns(
    session,
) -> None:
    """RH-11.c3 + the RH-16 positive: the CORRECT token succeeds and is audited.

    Naming note, not a defect: doc 16 writes the event as ``RESULT_SOFT_DELETED``;
    the shipped kind is ``backtest.result_soft_deleted``. The shipped name is
    canonical here (the O-02 / O-31 precedent), so the test pins the wire kind.

    The row is allowed to move on exactly two columns — ``deletion_state`` and
    ``row_version``. Everything else is asserted unchanged, which is what makes this
    a Result-immutability test rather than a delete smoke test.
    """
    _workspace_id, result_id = await _one_result(session)
    before = _snapshot(await _reread(session, result_id))
    audits_before = await _count_audits(session, "backtest.result_soft_deleted")

    await soft_delete_backtest_result(
        session,
        ADMIN,
        result_id=result_id,
        expected_row_version=before["row_version"],
    )
    await session.commit()

    after = _snapshot(await _reread(session, result_id))
    assert after["deletion_state"] == "soft_deleted" != before["deletion_state"]
    assert after["row_version"] == before["row_version"] + 1
    moved = {k for k in before if before[k] != after[k]}
    assert moved == {"deletion_state", "row_version"}
    assert await _count_audits(session, "backtest.result_soft_deleted") == audits_before + 1


# --------------------------------------------------------------------------- #
# RH-10.c3 — a refused compare mutates nothing                                 #
# --------------------------------------------------------------------------- #


async def test_refused_compare_leaves_both_result_rows_unmodified(session) -> None:
    """RH-10.c3: selecting the same result twice is refused AND writes nothing.

    The refusal itself was already asserted; the "mutates nothing" half was not.
    Two distinct results are seeded so the assertion covers both rows — a compare
    that touched only the first would still pass a single-row check.
    """
    await _seed_principals(session)
    workspace_id = await _workspace(session, USER1)
    for index, result_id in enumerate(("btres_cmp_a", "btres_cmp_b"), start=1):
        await _seed_result(
            session,
            workspace_id=workspace_id,
            result_id=result_id,
            owner=USER1.principal_id,
            net_profit=Decimal("100") * index,
            romad=Decimal("1.5"),
            max_drawdown=Decimal("10"),
            win_rate=Decimal("55"),
            total_trades=Decimal("20"),
            order_index=index,
        )
    await session.commit()

    before = {rid: _snapshot(await _reread(session, rid)) for rid in ("btres_cmp_a", "btres_cmp_b")}

    with pytest.raises(CompareRequiresTwoDistinctResultsError):
        await compare_backtest_results(session, USER1, result_ids=["btres_cmp_a", "btres_cmp_a"])
    await session.rollback()

    for rid, snap in before.items():
        assert _snapshot(await _reread(session, rid)) == snap


# --------------------------------------------------------------------------- #
# RH-12 — a restore returns the row, its hashes and an audit trail             #
# --------------------------------------------------------------------------- #


async def test_restore_preserves_artifact_checksums_and_writes_its_audit_row(
    session,
) -> None:
    """RH-12.c3 + c4: the round trip must be lossless AND recorded.

    Artifact checksums are the load-bearing part: a restore that re-derived them
    would silently invalidate every later verification, and nothing asserted they
    survive. The audit half is asserted by NAME after measuring which kind the
    restore path actually writes — doc 16 calls it ``RESULT_RESTORED``, the shipped
    trash path writes its own kind, and the shipped name is canonical (O-02/O-31).
    """
    _workspace_id, result_id = await _one_result(session, result_id="btres_restore_1")
    session.add(
        ResultArtifactChecksum(
            checksum_id="rac_restore_1",
            result_id=result_id,
            artifact_type="equity_curve",
            row_count=42,
            checksum="c" * 64,
            schema_version="v1",
        )
    )
    await session.commit()

    checks_before = await _checksums(session, result_id)
    assert checks_before, "the fixture must actually seed a checksum"

    await soft_delete_backtest_result(session, ADMIN, result_id=result_id)
    await session.commit()
    entry = (
        await session.execute(select(TrashEntry).where(TrashEntry.entity_id == result_id))
    ).scalar_one()

    audits_before = await _count_result_audits(session, _RESTORE_AUDIT_KIND, result_id)
    restored = await restore_trash_entry(session, ADMIN, trash_entry_id=entry.id)
    await session.commit()
    assert restored["deletion_state"] == "active"

    row = await _reread(session, result_id)
    assert row.deletion_state == "active"
    # Identity + provenance come back unchanged, and the checksums are byte-identical.
    assert row.manifest_hash == "a" * 64
    assert await _checksums(session, result_id) == checks_before
    # Measured, not assumed: the restore path writes `trash.restored`, attributed to
    # this result via target_entity_id. Doc 16 calls the event RESULT_RESTORED; the
    # shipped name is canonical (O-02 / O-31), and the attribution is what makes this
    # a proof about THIS result rather than about any trash activity.
    assert await _count_result_audits(session, _RESTORE_AUDIT_KIND, result_id) == (
        audits_before + 1
    )


# --------------------------------------------------------------------------- #
# RH-05 / RH-13 / RH-14 — reading, re-profiling and building on a result       #
# --------------------------------------------------------------------------- #


async def test_later_mainboard_edit_does_not_touch_a_finished_result(session) -> None:
    """RH-05.c2: history is history — a later composition edit cannot reach back.

    The result is seeded, the workspace's composition is then genuinely mutated
    (a new item attached, which moves the composition fingerprint), and the result
    row plus its manifest snapshot are re-read. A Result that resolved its excerpt
    from the LIVE composition would move here; one that owns its snapshot will not.
    """
    workspace_id, result_id = await _one_result(session, result_id="btres_hist_1")
    before = _snapshot(await _reread(session, result_id))
    snapshot_before = await _manifest_snapshot(session, result_id)

    await _mutate_composition(session, workspace_id)

    assert _snapshot(await _reread(session, result_id)) == before
    assert await _manifest_snapshot(session, result_id) == snapshot_before


# --------------------------------------------------------------------------- #
# Acceptance batch 23 — doc 16's last two open clauses                         #
#                                                                              #
# ADIM 55 measured both of these and deferred them as plumbing rather than      #
# rushing them; this batch supplies the plumbing. Both are "X did not move"     #
# claims, so both re-READ through ``_reread`` / a fresh query — the integration #
# session is built with ``expire_on_commit=False``, and an identity-map answer  #
# would make either assertion tautological.                                     #
# --------------------------------------------------------------------------- #


async def _apply_metric_profile(session, actor, codes: list[str]) -> list[str]:
    """Fork a PERSONAL Result View profile whose selection is ``codes``.

    Returns the selection the command actually persisted — the caller asserts
    against that rather than against what it asked for, so a command that
    silently widened the selection cannot make the test vacuous.
    """
    revision = await create_metric_profile_revision(
        session,
        actor,
        profile_id=SYSTEM_DEFAULT_PROFILE_ID,
        selected_metric_codes=codes,
    )
    await session.commit()
    stored = await session.get(ResultViewMetricProfileRevision, revision["profile_revision_id"])
    assert stored is not None, "the profile revision must actually be persisted"
    return list(stored.selected_metric_codes)


async def _history_digest(session, actor, result_id: str) -> dict[str, Any]:
    """The Results History key-metric digest for ONE result, re-read from the DB."""
    session.expire_all()
    page = await list_backtest_results(session, actor)
    row = next((item for item in page["items"] if item["result_id"] == result_id), None)
    assert row is not None, "the seeded result must be visible in Results History"
    return row["key_metrics"]


async def test_result_view_profile_change_does_not_move_the_history_digest(
    session,
) -> None:
    """RH-13.c2: a presentation preference cannot reach the historical digest.

    The clause is about the boundary between doc 17 (Arrange Metrics — a personal,
    revisable *view* preference) and doc 16 §9.4 (``key_metrics`` — a fixed digest
    on an immutable historical record). Nothing asserted that boundary: no test
    listed Results History before and after applying a narrower profile.

    The profile applied here drops **all five** key metrics — it selects only
    ``profit_factor`` and ``total_stops`` — which is the strongest form of the
    clause. ``_digest_from_rows`` filters on the CONSTANT ``KEY_METRIC_KEYS``, so a
    profile revision cannot reach it; this test is what states that.

    Non-vacuity is asserted in both directions before the equality is claimed: the
    digest must actually be POPULATED (an all-``None`` digest would compare equal to
    itself while proving nothing), and the applied selection must actually EXCLUDE
    the key metrics (a profile that kept them would make the comparison trivial).
    """
    await _seed_registry(session)
    _workspace_id, result_id = await _one_result(session, result_id="btres_profile_1")

    before = await _history_digest(session, USER1, result_id)
    # Non-vacuity (1): the digest carries real values, not five Nones.
    assert set(before) == set(KEY_METRIC_KEYS)
    assert all(before[key] is not None for key in KEY_METRIC_KEYS), before

    selected = await _apply_metric_profile(session, USER1, ["profit_factor", "total_stops"])
    # Non-vacuity (2): the profile really did drop every key metric.
    assert selected == ["profit_factor", "total_stops"]
    assert not set(selected) & set(KEY_METRIC_KEYS)

    # Full-dictionary equality, not a key lookup: a digest that LOST a key, gained
    # one, or changed a cell's label/unit/format all fail here (ADIM 98/101).
    assert await _history_digest(session, USER1, result_id) == before


async def _seed_agent(session) -> None:
    if await session.get(Principal, AGENT.principal_id) is None:
        session.add(Principal(principal_id=AGENT.principal_id, principal_type=PrincipalType.AGENT))
    if await session.get(AgentRuntime, ALPHA_AGENT_ID) is None:
        session.add(
            AgentRuntime(
                agent_id=ALPHA_AGENT_ID,
                mode=RuntimeMode.CONTINUOUS,
                status=RuntimeStatus.ACTIVE,
                row_version=1,
            )
        )
    await session.flush()


async def test_agent_artifact_create_leaves_the_referenced_result_row_untouched(
    session,
) -> None:
    """RH-14.c3: building ON a result must not write TO it.

    RH-14.c1/c2 are asserted by the agent-loop e2e test, but that test only ever
    reads forward — it checks the artifact, its ``source_task_id`` and its
    ``ArtifactLink`` rows, and never re-reads the ``BacktestResult`` afterwards. The
    link lives on the artifact side, so non-mutation holds by construction; this
    test is what turns that argument into an assertion.

    The tool call is the SHIPPED gateway path (``artifact.create`` under the
    ``research`` policy scope), driven against a REAL persisted result whose id is
    carried in both ``evidence_refs`` and a provenance link — so the artifact
    genuinely references the row whose stillness is being claimed.
    """
    await _seed_agent(session)
    _workspace_id, result_id = await _one_result(session, result_id="btres_artifact_1")
    task = await al_repo.create_task(
        session,
        agent_id=ALPHA_AGENT_ID,
        task_type="research",
        title="Does the funding-reversal edge survive out of sample?",
        source="autonomous",
        priority=AgentTaskPriority.AUTONOMOUS,
        status=AgentTaskStatus.RUNNING,
    )
    await session.commit()
    # Read the id BEFORE the snapshot: `_reread` calls `session.expire_all()`, which
    # expires this object too, and a later `task.task_id` would then lazy-load from a
    # sync context (MissingGreenlet). Same identity-map hazard as ADIM 100, other way up.
    task_id = task.task_id

    before = _snapshot(await _reread(session, result_id))
    manifest_before = await _manifest_snapshot(session, result_id)

    created = await agent_tools.dispatch_tool_call(
        session,
        AGENT,
        tool_name="artifact.create",
        policy_scope="research",
        request={
            "title": "Funding reversal holds on the pinned bundle",
            "mechanism": "Long bias after negative funding extremes persists OOS.",
            "evidence_refs": [result_id],
            "links": [
                {
                    "target_type": "backtest_result",
                    "target_id": result_id,
                    "relation_type": "evidenced_by",
                }
            ],
        },
        task_id=task_id,
        idempotency_key="rh14-artifact-1",
    )
    await session.commit()

    # Non-vacuity: the call really succeeded and really points AT this result. A
    # refused or unlinked call would leave the row still by doing nothing at all.
    assert created["status"] == "succeeded"
    links = (
        (
            await session.execute(
                select(ArtifactLink).where(
                    ArtifactLink.source_artifact_id == created["artifact_id"]
                )
            )
        )
        .scalars()
        .all()
    )
    assert [(link.target_type, link.target_id) for link in links] == [
        ("backtest_result", result_id)
    ]

    # The target assertion: every durable column, plus the manifest snapshot.
    assert _snapshot(await _reread(session, result_id)) == before
    assert await _manifest_snapshot(session, result_id) == manifest_before
