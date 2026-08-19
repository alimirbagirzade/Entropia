"""Stage 5c — Arrange Metrics + export/artifact against a real database (doc 17; doc-15).

Auto-skips without PostgreSQL. The integration conftest builds the schema with
``create_all`` (not the migration), so the ``metric_definition`` registry is seeded
here from ``METRIC_REGISTRY`` (the same authority the migration uses). A real
workspace is created via the 3a Mainboard query (so ``entity_registry`` carries the
owner + active state the visibility guard needs); an immutable Result + metrics +
artifacts are seeded directly for deterministic control.

Covers: System Default resolution; registry availability filter; first-Apply forks
a personal profile (L1 FK: root before revision); minimum-one-selectable; future
metric block; Lock → change-blocked → Unlock; stale expected-revision; idempotent
Apply; foreign-profile role guard; presentation-only result metrics (null never 0,
dropped metric keeps its MetricValue row); export provenance + idempotency + invalid
type; artifact cursor pagination (no duplicates, wrong-type cursor rejected); a
soft-deleted result hides its artifacts.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy import select

from entropia.application.commands import metric_profile as mp_cmd
from entropia.application.commands import result_export as export_cmd
from entropia.application.queries import mainboard as mb_query
from entropia.application.queries import metric_profile as mp_query
from entropia.application.queries import result_artifacts as artifact_query
from entropia.domain.backtest.enums import BacktestRunState, MetricAvailability
from entropia.domain.identity import Actor
from entropia.domain.lifecycle.enums import JobStatus, PrincipalType, Role
from entropia.domain.metric_profile.registry import METRIC_REGISTRY
from entropia.infrastructure.postgres.models import (
    BacktestResult,
    BacktestRun,
    DiagnosticArtifact,
    Job,
    MetricDefinition,
    MetricValueRow,
    Principal,
    ResultManifestSnapshot,
    SignalEventRow,
    TradeLedgerRow,
)
from entropia.infrastructure.postgres.repositories import backtest as bt_repo
from entropia.infrastructure.postgres.repositories import export as export_repo
from entropia.infrastructure.postgres.repositories import metric_profile as mp_repo
from entropia.shared.errors import (
    AccessDeniedError,
    BacktestResultNotFoundError,
    CursorInvalidError,
    ExportTypeInvalidError,
    MetricNotSelectableError,
    MetricProfileLockedError,
    MetricProfileStaleError,
    MetricSelectionEmptyError,
)

pytestmark = pytest.mark.integration

USER1 = Actor(principal_id="user_1", principal_type=PrincipalType.HUMAN, role=Role.USER)
USER2 = Actor(principal_id="user_2", principal_type=PrincipalType.HUMAN, role=Role.USER)
ADMIN = Actor(principal_id="admin_1", principal_type=PrincipalType.HUMAN, role=Role.ADMIN)

_MANIFEST_HASH = "b" * 64


async def _seed_registry(session) -> None:
    for row in METRIC_REGISTRY:
        session.add(
            MetricDefinition(
                metric_code=row.metric_code,
                label=row.label,
                unit=row.unit,
                value_format=row.value_format,
                availability_status=row.availability_status,
                display_order=row.display_order,
                formula_version=row.formula_version,
                description=row.description,
                registry_version="v1",
            )
        )
    await session.flush()


async def _seed_principals(session) -> None:
    for pid in ("user_1", "user_2", "admin_1"):
        if await session.get(Principal, pid) is None:
            session.add(Principal(principal_id=pid, principal_type=PrincipalType.HUMAN))
    await session.flush()


async def _workspace(session, actor: Actor) -> str:
    mb = await mb_query.get_default_mainboard(session, actor)
    await session.commit()
    return mb["workspace_id"]


async def _seed_result(
    session, *, workspace_id: str, result_id: str, owner: str, ledger_rows: int = 0
) -> None:
    session.add(
        BacktestResult(
            result_id=result_id,
            run_id=f"run_{result_id}",
            manifest_id=f"man_{result_id}",
            manifest_hash=_MANIFEST_HASH,
            workspace_entity_id=workspace_id,
            composition_fingerprint=f"fp_{result_id}",
            engine_version="backtest-engine-v1-stub",
            deletion_state="active",
            row_version=1,
            created_by_principal_id=owner,
        )
    )
    await session.flush()
    # 9 canonical metrics; romad is NULL (not_available) to prove null-never-0.
    values: dict[str, tuple[Decimal | None, MetricAvailability]] = {
        "net_profit": (Decimal("12.5"), MetricAvailability.COMPUTED),
        "max_drawdown": (Decimal("8.1"), MetricAvailability.COMPUTED),
        "romad": (None, MetricAvailability.NOT_AVAILABLE),
        "win_rate": (Decimal("55.0"), MetricAvailability.COMPUTED),
        "profit_factor": (Decimal("1.8"), MetricAvailability.COMPUTED),
        "total_trades": (Decimal("20"), MetricAvailability.COMPUTED),
        "total_stops": (Decimal("3"), MetricAvailability.COMPUTED),
        "max_stop_streak": (Decimal("2"), MetricAvailability.COMPUTED),
        "total_winning_trades": (Decimal("11"), MetricAvailability.COMPUTED),
    }
    for pos, (key, (value, availability)) in enumerate(values.items()):
        session.add(
            MetricValueRow(
                metric_value_id=f"mv_{result_id}_{key}",
                result_id=result_id,
                metric_key=key,
                label=key.replace("_", " ").title(),
                unit="ratio",
                value_format="decimal2",
                value=value,
                availability=availability,
                formula_version="v1",
                position_index=pos,
            )
        )
    session.add(
        ResultManifestSnapshot(
            snapshot_id=f"snap_{result_id}",
            result_id=result_id,
            manifest_hash=_MANIFEST_HASH,
            execution_key="ek-1",
            engine_version="backtest-engine-v1-stub",
            manifest={"identity": {"engine_version": "backtest-engine-v1-stub"}},
        )
    )
    for seq in range(1, ledger_rows + 1):
        session.add(
            TradeLedgerRow(
                trade_row_id=f"tr_{result_id}_{seq}",
                result_id=result_id,
                seq=seq,
                entry_time=f"2026-01-0{seq}T00:00:00Z",
                exit_time=f"2026-01-0{seq}T01:00:00Z",
                direction="long",
                entry_price=Decimal("100"),
                exit_price=Decimal("101"),
                pnl=Decimal("1"),
                exit_reason="take_profit",
            )
        )
    session.add(
        DiagnosticArtifact(
            diagnostic_id=f"diag_{result_id}",
            result_id=result_id,
            kind="run_diagnostics",
            content={"note": "stub"},
        )
    )
    session.add(
        SignalEventRow(
            signal_event_id=f"se_{result_id}",
            result_id=result_id,
            seq=1,
            event_time="2026-01-01T00:00:00Z",
            event_type="entry_signal",
            direction="long",
            detail={"k": "v"},
        )
    )
    await session.flush()


# --------------------------------------------------------------------------- #
# Registry + resolution                                                        #
# --------------------------------------------------------------------------- #


async def test_system_default_resolution(session):
    await _seed_registry(session)
    await _seed_principals(session)
    resolved = await mp_query.get_resolved_metric_profile(session, USER1)
    assert resolved["is_personal"] is False
    assert resolved["scope"] == "system_default"
    assert resolved["current_revision_id"] is None
    assert resolved["selected_metric_codes"][0] == "net_profit"
    assert len(resolved["selected_metric_codes"]) == 9


async def test_list_definitions_availability_filter(session):
    await _seed_registry(session)
    await _seed_principals(session)
    all_defs = await mp_query.list_metric_definitions(session, USER1)
    selectable = await mp_query.list_metric_definitions(session, USER1, availability="selectable")
    future = await mp_query.list_metric_definitions(session, USER1, availability="future")
    assert len(all_defs["metric_definitions"]) == 27
    assert len(selectable["metric_definitions"]) == 9
    assert len(future["metric_definitions"]) == 18
    assert all(d["selectable"] for d in selectable["metric_definitions"])


# --------------------------------------------------------------------------- #
# Apply / Lock / Unlock                                                        #
# --------------------------------------------------------------------------- #


async def test_first_apply_forks_personal_profile(session):
    await _seed_registry(session)
    await _seed_principals(session)
    out = await mp_cmd.create_metric_profile_revision(
        session,
        USER1,
        profile_id=mp_cmd.SYSTEM_DEFAULT_PROFILE_ID,
        selected_metric_codes=["net_profit", "win_rate"],
        is_locked=False,
    )
    assert out["is_personal"] is True
    assert out["selected_metric_codes"] == ["net_profit", "win_rate"]
    assert out["revision_no"] == 1
    resolved = await mp_query.get_resolved_metric_profile(session, USER1)
    assert resolved["is_personal"] is True
    assert resolved["profile_id"] == out["profile_id"]
    assert resolved["selected_metric_codes"] == ["net_profit", "win_rate"]


async def test_min_selection_blocked(session):
    await _seed_registry(session)
    await _seed_principals(session)
    with pytest.raises(MetricSelectionEmptyError):
        await mp_cmd.create_metric_profile_revision(
            session,
            USER1,
            profile_id=mp_cmd.SYSTEM_DEFAULT_PROFILE_ID,
            selected_metric_codes=[],
        )


async def test_future_metric_blocked(session):
    await _seed_registry(session)
    await _seed_principals(session)
    with pytest.raises(MetricNotSelectableError):
        await mp_cmd.create_metric_profile_revision(
            session,
            USER1,
            profile_id=mp_cmd.SYSTEM_DEFAULT_PROFILE_ID,
            selected_metric_codes=["net_profit", "sharpe_ratio"],
        )


async def test_lock_blocks_change_then_unlock(session):
    await _seed_registry(session)
    await _seed_principals(session)
    first = await mp_cmd.create_metric_profile_revision(
        session,
        USER1,
        profile_id=mp_cmd.SYSTEM_DEFAULT_PROFILE_ID,
        selected_metric_codes=["net_profit", "win_rate"],
    )
    pid = first["profile_id"]
    locked = await mp_cmd.create_metric_profile_revision(
        session,
        USER1,
        profile_id=pid,
        expected_profile_revision_id=first["current_revision_id"],
        selected_metric_codes=["net_profit", "win_rate"],
        is_locked=True,
    )
    assert locked["is_locked"] is True
    assert locked["reason"] == "lock"
    # A selection change while locked is rejected.
    with pytest.raises(MetricProfileLockedError):
        await mp_cmd.create_metric_profile_revision(
            session,
            USER1,
            profile_id=pid,
            expected_profile_revision_id=locked["current_revision_id"],
            selected_metric_codes=["net_profit"],
            is_locked=True,
        )
    # A pure unlock (same selection) is allowed.
    unlocked = await mp_cmd.create_metric_profile_revision(
        session,
        USER1,
        profile_id=pid,
        expected_profile_revision_id=locked["current_revision_id"],
        selected_metric_codes=["net_profit", "win_rate"],
        is_locked=False,
    )
    assert unlocked["is_locked"] is False
    assert unlocked["reason"] == "unlock"


async def test_stale_expected_revision_rejected(session):
    await _seed_registry(session)
    await _seed_principals(session)
    first = await mp_cmd.create_metric_profile_revision(
        session,
        USER1,
        profile_id=mp_cmd.SYSTEM_DEFAULT_PROFILE_ID,
        selected_metric_codes=["net_profit", "win_rate"],
    )
    pid = first["profile_id"]
    stale_expected = first["current_revision_id"]
    await mp_cmd.create_metric_profile_revision(
        session,
        USER1,
        profile_id=pid,
        expected_profile_revision_id=stale_expected,
        selected_metric_codes=["net_profit"],
    )
    with pytest.raises(MetricProfileStaleError):
        await mp_cmd.create_metric_profile_revision(
            session,
            USER1,
            profile_id=pid,
            expected_profile_revision_id=stale_expected,
            selected_metric_codes=["romad"],
        )


async def test_idempotent_apply(session):
    await _seed_registry(session)
    await _seed_principals(session)
    a = await mp_cmd.create_metric_profile_revision(
        session,
        USER1,
        profile_id=mp_cmd.SYSTEM_DEFAULT_PROFILE_ID,
        selected_metric_codes=["net_profit", "win_rate"],
        idempotency_key="k1",
    )
    b = await mp_cmd.create_metric_profile_revision(
        session,
        USER1,
        profile_id=mp_cmd.SYSTEM_DEFAULT_PROFILE_ID,
        selected_metric_codes=["net_profit", "win_rate"],
        idempotency_key="k1",
    )
    assert a["profile_revision_id"] == b["profile_revision_id"]
    assert a["revision_no"] == b["revision_no"] == 1


async def test_foreign_profile_role_guard(session):
    await _seed_registry(session)
    await _seed_principals(session)
    owned = await mp_cmd.create_metric_profile_revision(
        session,
        USER1,
        profile_id=mp_cmd.SYSTEM_DEFAULT_PROFILE_ID,
        selected_metric_codes=["net_profit"],
    )
    with pytest.raises(AccessDeniedError):
        await mp_cmd.create_metric_profile_revision(
            session,
            USER2,
            profile_id=owned["profile_id"],
            expected_profile_revision_id=owned["current_revision_id"],
            selected_metric_codes=["romad"],
        )


async def test_second_default_apply_when_personal_exists_is_stale(session):
    # F1 pre-check branch: once a personal profile exists, a fresh POST to the
    # System Default sentinel is stale — the client must target the personal
    # profile (doc 17 §8.5). The UNIQUE(scope, owner) constraint backs this under
    # a true concurrent race (IntegrityError -> MetricProfileStaleError).
    await _seed_registry(session)
    await _seed_principals(session)
    await mp_cmd.create_metric_profile_revision(
        session,
        USER1,
        profile_id=mp_cmd.SYSTEM_DEFAULT_PROFILE_ID,
        selected_metric_codes=["net_profit"],
    )
    with pytest.raises(MetricProfileStaleError):
        await mp_cmd.create_metric_profile_revision(
            session,
            USER1,
            profile_id=mp_cmd.SYSTEM_DEFAULT_PROFILE_ID,
            selected_metric_codes=["win_rate"],
        )


async def test_existing_profile_rejects_none_expected_when_head_set(session):
    # A committed root ALWAYS carries a head revision, so an omitted
    # expected_profile_revision_id (None) on an existing profile is rejected as
    # stale — the OCC guard is not bypassable once a revision exists.
    await _seed_registry(session)
    await _seed_principals(session)
    first = await mp_cmd.create_metric_profile_revision(
        session,
        USER1,
        profile_id=mp_cmd.SYSTEM_DEFAULT_PROFILE_ID,
        selected_metric_codes=["net_profit", "win_rate"],
    )
    with pytest.raises(MetricProfileStaleError):
        await mp_cmd.create_metric_profile_revision(
            session,
            USER1,
            profile_id=first["profile_id"],
            expected_profile_revision_id=None,
            selected_metric_codes=["romad"],
        )


# --------------------------------------------------------------------------- #
# Result metrics (presentation-only)                                           #
# --------------------------------------------------------------------------- #


async def test_result_metrics_presentation_and_null(session):
    await _seed_registry(session)
    await _seed_principals(session)
    ws = await _workspace(session, USER1)
    await _seed_result(session, workspace_id=ws, result_id="btres_m", owner="user_1")
    # Default profile: all 9 cards, romad surfaced as not_available (never 0).
    default_view = await mp_query.get_result_metrics(session, USER1, result_id="btres_m")
    assert [c["key"] for c in default_view["metrics"]][:3] == [
        "net_profit",
        "max_drawdown",
        "romad",
    ]
    romad = next(c for c in default_view["metrics"] if c["key"] == "romad")
    assert romad["value"] is None
    assert romad["availability"] == str(MetricAvailability.NOT_AVAILABLE)
    # Apply a subset that drops max_stop_streak.
    await mp_cmd.create_metric_profile_revision(
        session,
        USER1,
        profile_id=mp_cmd.SYSTEM_DEFAULT_PROFILE_ID,
        selected_metric_codes=["net_profit", "win_rate"],
    )
    subset_view = await mp_query.get_result_metrics(session, USER1, result_id="btres_m")
    assert [c["key"] for c in subset_view["metrics"]] == ["net_profit", "win_rate"]
    # Presentation separation: the dropped metric's immutable MetricValue row survives.
    still_there = await session.get(MetricValueRow, "mv_btres_m_max_stop_streak")
    assert still_there is not None


# --------------------------------------------------------------------------- #
# Export                                                                        #
# --------------------------------------------------------------------------- #


async def test_export_provenance_and_idempotent(session):
    await _seed_registry(session)
    await _seed_principals(session)
    ws = await _workspace(session, USER1)
    await _seed_result(session, workspace_id=ws, result_id="btres_x", owner="user_1", ledger_rows=4)
    out = await export_cmd.request_result_export(
        session,
        USER1,
        result_id="btres_x",
        export_type="trade_ledger",
        export_format="csv",
        idempotency_key="e1",
    )
    assert out["row_count"] == 4
    assert out["source_manifest_hash"] == _MANIFEST_HASH
    assert out["schema_version"] == "v1"
    assert out["object_key"].endswith(".csv")
    assert len(out["checksum"]) == 64
    # Idempotent retry returns the same export.
    again = await export_cmd.request_result_export(
        session,
        USER1,
        result_id="btres_x",
        export_type="trade_ledger",
        export_format="csv",
        idempotency_key="e1",
    )
    assert again["export_id"] == out["export_id"]
    exports = await export_repo.list_exports(session, "btres_x")
    assert len(exports) == 1


async def test_export_invalid_type_rejected(session):
    await _seed_registry(session)
    await _seed_principals(session)
    ws = await _workspace(session, USER1)
    await _seed_result(session, workspace_id=ws, result_id="btres_e", owner="user_1")
    with pytest.raises(ExportTypeInvalidError):
        await export_cmd.request_result_export(
            session,
            USER1,
            result_id="btres_e",
            export_type="bogus",
            export_format="csv",
        )


# --------------------------------------------------------------------------- #
# Artifact cursor-query                                                         #
# --------------------------------------------------------------------------- #


async def test_artifact_cursor_pagination_no_duplicates(session):
    await _seed_registry(session)
    await _seed_principals(session)
    ws = await _workspace(session, USER1)
    await _seed_result(session, workspace_id=ws, result_id="btres_a", owner="user_1", ledger_rows=5)

    seen: list[Any] = []
    page = await artifact_query.query_result_artifact(
        session, USER1, result_id="btres_a", artifact_type="trade_ledger", limit=2
    )
    assert len(page["items"]) == 2
    assert page["next_cursor"] is not None
    seen.extend(r["seq"] for r in page["items"])

    page2 = await artifact_query.query_result_artifact(
        session,
        USER1,
        result_id="btres_a",
        artifact_type="trade_ledger",
        cursor=page["next_cursor"],
        limit=2,
    )
    assert len(page2["items"]) == 2
    seen.extend(r["seq"] for r in page2["items"])

    page3 = await artifact_query.query_result_artifact(
        session,
        USER1,
        result_id="btres_a",
        artifact_type="trade_ledger",
        cursor=page2["next_cursor"],
        limit=2,
    )
    assert len(page3["items"]) == 1
    assert page3["next_cursor"] is None
    seen.extend(r["seq"] for r in page3["items"])

    assert seen == [1, 2, 3, 4, 5]  # server-side order, no duplicates/gaps


async def test_artifact_wrong_type_cursor_rejected(session):
    await _seed_registry(session)
    await _seed_principals(session)
    ws = await _workspace(session, USER1)
    await _seed_result(session, workspace_id=ws, result_id="btres_c", owner="user_1", ledger_rows=3)
    page = await artifact_query.query_result_artifact(
        session, USER1, result_id="btres_c", artifact_type="trade_ledger", limit=2
    )
    with pytest.raises(CursorInvalidError):
        await artifact_query.query_result_artifact(
            session,
            USER1,
            result_id="btres_c",
            artifact_type="equity_curve",
            cursor=page["next_cursor"],
            limit=2,
        )


async def test_soft_deleted_result_hides_artifacts(session):
    await _seed_registry(session)
    await _seed_principals(session)
    ws = await _workspace(session, USER1)
    await _seed_result(session, workspace_id=ws, result_id="btres_d", owner="user_1", ledger_rows=2)
    result = await session.get(BacktestResult, "btres_d")
    result.deletion_state = "soft_deleted"
    await session.flush()
    with pytest.raises(BacktestResultNotFoundError):
        await artifact_query.query_result_artifact(
            session, USER1, result_id="btres_d", artifact_type="trade_ledger"
        )
    with pytest.raises(BacktestResultNotFoundError):
        await mp_query.get_result_metrics(session, USER1, result_id="btres_d")


# --------------------------------------------------------------------------- #
# Doc 17 §15 acceptance debt — AM-03 / AM-05 / AM-06 / AM-07                    #
# --------------------------------------------------------------------------- #


async def _seed_run_and_job(session, *, workspace_id: str, result_id: str) -> None:
    """A queued BacktestRun + its Job row, so "no run is created" is measured in a
    world where those tables are NOT empty (an empty-table count proves less)."""
    session.add(
        Job(
            job_id=f"job_{result_id}",
            queue="backtest",
            status=JobStatus.QUEUED,
            actor_principal_id="user_1",
            payload={"run_id": f"run_{result_id}"},
        )
    )
    session.add(
        BacktestRun(
            run_id=f"run_{result_id}",
            workspace_entity_id=workspace_id,
            composition_snapshot_id=f"snap_comp_{result_id}",
            composition_fingerprint=f"fp_{result_id}",
            manifest_id=f"man_{result_id}",
            manifest_hash=_MANIFEST_HASH,
            state=BacktestRunState.SUCCEEDED,
            requested_by_principal_id="user_1",
            job_id=f"job_{result_id}",
            result_id=result_id,
            row_version=1,
        )
    )
    await session.flush()


async def _run_and_job_ids(session) -> tuple[list[str], list[str]]:
    run_rows = await session.execute(select(BacktestRun.run_id).order_by(BacktestRun.run_id))
    job_rows = await session.execute(select(Job.job_id).order_by(Job.job_id))
    return list(run_rows.scalars()), list(job_rows.scalars())


async def test_profile_apply_creates_no_run_and_leaves_manifest_untouched(session):
    # AM-03.c2 + AM-03.c3 (doc 17 §15): an Arrange Metrics Apply is presentation-only.
    # The e2e pipeline asserts manifest-hash stability across a whole span that also
    # contains a Trash delete + restore, so the claim was never scoped to the Apply
    # itself; and nothing anywhere counted run/job rows around one.
    await _seed_registry(session)
    await _seed_principals(session)
    ws = await _workspace(session, USER1)
    await _seed_result(session, workspace_id=ws, result_id="btres_am3", owner="user_1")
    await _seed_run_and_job(session, workspace_id=ws, result_id="btres_am3")

    runs_before, jobs_before = await _run_and_job_ids(session)
    assert runs_before == ["run_btres_am3"] and jobs_before == ["job_btres_am3"]
    run_before = await session.get(BacktestRun, "run_btres_am3")
    before = (
        run_before.manifest_hash,
        run_before.manifest_id,
        str(run_before.state),
        run_before.row_version,
    )
    result_before = await session.get(BacktestResult, "btres_am3")
    result_manifest_before = (result_before.manifest_hash, result_before.row_version)
    snapshot_before = await session.get(ResultManifestSnapshot, "snap_btres_am3")
    snapshot_manifest_before = (snapshot_before.manifest_hash, dict(snapshot_before.manifest))

    applied = await mp_cmd.create_metric_profile_revision(
        session,
        USER1,
        profile_id=mp_cmd.SYSTEM_DEFAULT_PROFILE_ID,
        selected_metric_codes=["net_profit", "win_rate"],
    )
    # The Apply really landed — without this the "nothing moved" assertions below
    # would also hold for a call that did nothing at all.
    assert applied["revision_no"] == 1
    assert applied["selected_metric_codes"] == ["net_profit", "win_rate"]

    # Read the rows back from the database rather than from the identity map.
    await session.flush()
    session.expire_all()

    runs_after, jobs_after = await _run_and_job_ids(session)
    assert runs_after == runs_before, "an Arrange Metrics Apply appended a BacktestRun"
    assert jobs_after == jobs_before, "an Arrange Metrics Apply enqueued a job"
    run_after = await session.get(BacktestRun, "run_btres_am3")
    assert (
        run_after.manifest_hash,
        run_after.manifest_id,
        str(run_after.state),
        run_after.row_version,
    ) == before
    result_after = await session.get(BacktestResult, "btres_am3")
    assert (result_after.manifest_hash, result_after.row_version) == result_manifest_before
    snapshot_after = await session.get(ResultManifestSnapshot, "snap_btres_am3")
    assert (
        snapshot_after.manifest_hash,
        dict(snapshot_after.manifest),
    ) == snapshot_manifest_before


async def test_empty_selection_refusal_leaves_canonical_revision_in_place(session):
    # AM-05.c2 (doc 17 §15): the existing `test_min_selection_blocked` empties the
    # selection against the SYSTEM DEFAULT sentinel — a profile with no revision at
    # all — so "the previous canonical revision survives" is structurally out of its
    # scope. Drive the refusal against a profile that HAS a head, then re-read it.
    await _seed_registry(session)
    await _seed_principals(session)
    first = await mp_cmd.create_metric_profile_revision(
        session,
        USER1,
        profile_id=mp_cmd.SYSTEM_DEFAULT_PROFILE_ID,
        selected_metric_codes=["net_profit", "win_rate"],
    )
    pid = first["profile_id"]
    second = await mp_cmd.create_metric_profile_revision(
        session,
        USER1,
        profile_id=pid,
        expected_profile_revision_id=first["current_revision_id"],
        selected_metric_codes=["romad"],
    )
    assert second["revision_no"] == 2
    head_before = second["current_revision_id"]
    root_before = await mp_repo.get_profile(session, pid)
    row_version_before = root_before.row_version

    with pytest.raises(MetricSelectionEmptyError):
        await mp_cmd.create_metric_profile_revision(
            session,
            USER1,
            profile_id=pid,
            expected_profile_revision_id=head_before,
            selected_metric_codes=[],
        )

    await session.flush()
    session.expire_all()
    root_after = await mp_repo.get_profile(session, pid)
    assert root_after.current_revision_id == head_before
    assert root_after.row_version == row_version_before
    assert await mp_repo.max_revision_no(session, pid) == 2
    resolved = await mp_query.get_resolved_metric_profile(session, USER1)
    assert resolved["current_revision_id"] == head_before
    assert resolved["selected_metric_codes"] == ["romad"]


async def test_lock_unlock_cycle_leaves_result_values_unchanged(session):
    # AM-06.c3 (doc 17 §15): lock/unlock mechanics and the disabled UI are proven,
    # but no test reads the Result metric projection across the cycle. Select ALL
    # nine selectable codes so the projection cannot narrow and every card is
    # comparable at each step.
    await _seed_registry(session)
    await _seed_principals(session)
    ws = await _workspace(session, USER1)
    await _seed_result(session, workspace_id=ws, result_id="btres_am6", owner="user_1")
    all_nine = (await mp_query.get_resolved_metric_profile(session, USER1))["selected_metric_codes"]
    assert len(all_nine) == 9

    applied = await mp_cmd.create_metric_profile_revision(
        session,
        USER1,
        profile_id=mp_cmd.SYSTEM_DEFAULT_PROFILE_ID,
        selected_metric_codes=all_nine,
    )
    pid = applied["profile_id"]
    before = await mp_query.get_result_metrics(session, USER1, result_id="btres_am6")
    assert before["profile"]["is_locked"] is False
    # A NULL metric is in the set, so "unchanged" is not just a story about numbers.
    assert any(card["value"] is None for card in before["metrics"])

    locked = await mp_cmd.create_metric_profile_revision(
        session,
        USER1,
        profile_id=pid,
        expected_profile_revision_id=applied["current_revision_id"],
        selected_metric_codes=all_nine,
        is_locked=True,
    )
    assert locked["reason"] == "lock" and locked["is_locked"] is True
    during = await mp_query.get_result_metrics(session, USER1, result_id="btres_am6")
    assert during["profile"]["is_locked"] is True
    assert during["metrics"] == before["metrics"]

    unlocked = await mp_cmd.create_metric_profile_revision(
        session,
        USER1,
        profile_id=pid,
        expected_profile_revision_id=locked["current_revision_id"],
        selected_metric_codes=all_nine,
        is_locked=False,
    )
    assert unlocked["reason"] == "unlock" and unlocked["is_locked"] is False
    after = await mp_query.get_result_metrics(session, USER1, result_id="btres_am6")
    assert after["profile"]["is_locked"] is False
    assert after["metrics"] == before["metrics"]

    # The stored rows behind the projection are untouched too (read back from the
    # database, not from the identity map).
    await session.flush()
    session.expire_all()
    stored = {
        row.metric_key: (row.value, str(row.availability))
        for row in await bt_repo.list_metric_values(session, "btres_am6")
    }
    assert stored["net_profit"] == (Decimal("12.5"), str(MetricAvailability.COMPUTED))
    assert stored["romad"] == (None, str(MetricAvailability.NOT_AVAILABLE))
    assert len(stored) == 9


async def test_foreign_unlock_denied_and_the_lock_preference_grants_nothing(session):
    # AM-07.c2 (doc 17 §15): the one ownership guard the suite drives is an UNLOCKED
    # profile with a CHANGED selection (that is AM-14's scenario). The criterion's own
    # scenario — a LOCKED profile, a pure unlock, a foreign caller — is never driven,
    # so "lock is a preference, not a grant" was inferred from shared code.
    await _seed_registry(session)
    await _seed_principals(session)
    first = await mp_cmd.create_metric_profile_revision(
        session,
        USER1,
        profile_id=mp_cmd.SYSTEM_DEFAULT_PROFILE_ID,
        selected_metric_codes=["net_profit", "win_rate"],
    )
    pid = first["profile_id"]
    locked = await mp_cmd.create_metric_profile_revision(
        session,
        USER1,
        profile_id=pid,
        expected_profile_revision_id=first["current_revision_id"],
        selected_metric_codes=["net_profit", "win_rate"],
        is_locked=True,
    )
    assert locked["is_locked"] is True
    root_before = await mp_repo.get_profile(session, pid)
    row_version_before = root_before.row_version

    with pytest.raises(AccessDeniedError):
        await mp_cmd.create_metric_profile_revision(
            session,
            USER2,
            profile_id=pid,
            expected_profile_revision_id=locked["current_revision_id"],
            selected_metric_codes=["net_profit", "win_rate"],
            is_locked=False,
        )

    await session.flush()
    session.expire_all()
    still = await mp_repo.get_profile(session, pid)
    assert still.current_revision_id == locked["current_revision_id"]
    assert still.row_version == row_version_before
    head = await mp_repo.get_revision(session, still.current_revision_id)
    assert head.is_locked is True

    # The refusal was about WHO called, not about the unlock being malformed: the
    # byte-identical call from the owner succeeds. Without this the AccessDeniedError
    # above could be attributed to the request rather than to the actor.
    owner_unlock = await mp_cmd.create_metric_profile_revision(
        session,
        USER1,
        profile_id=pid,
        expected_profile_revision_id=locked["current_revision_id"],
        selected_metric_codes=["net_profit", "win_rate"],
        is_locked=False,
    )
    assert owner_unlock["reason"] == "unlock" and owner_unlock["is_locked"] is False
