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

from entropia.application.commands import metric_profile as mp_cmd
from entropia.application.commands import result_export as export_cmd
from entropia.application.queries import mainboard as mb_query
from entropia.application.queries import metric_profile as mp_query
from entropia.application.queries import result_artifacts as artifact_query
from entropia.domain.backtest.enums import MetricAvailability
from entropia.domain.identity import Actor
from entropia.domain.lifecycle.enums import PrincipalType, Role
from entropia.domain.metric_profile.registry import METRIC_REGISTRY
from entropia.infrastructure.postgres.models import (
    BacktestResult,
    DiagnosticArtifact,
    MetricDefinition,
    MetricValueRow,
    Principal,
    ResultManifestSnapshot,
    SignalEventRow,
    TradeLedgerRow,
)
from entropia.infrastructure.postgres.repositories import export as export_repo
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
