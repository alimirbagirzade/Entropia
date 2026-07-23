"""V18 R3 P-14 — Panel / Logs primary "All User Backtest Logs" projection (doc 19).

Auto-skips without PostgreSQL (tests/integration/conftest.py). Each user's workspace
is created via the 3a Mainboard query (so ``entity_registry`` carries the owner +
active deletion state the projection joins on); immutable ``backtest_result`` +
``metric_value`` rows are then seeded directly for deterministic control. Covers:
Admin-only guard; cross-user visibility (every user's results); human User label with
an honest raw-principal-id fallback; metrics sourced from server-truth (null surfaced,
never 0); newest-first cursor pagination with no dup/skip; soft-deleted result absent.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest

from entropia.application.queries import mainboard as mb_query
from entropia.application.queries import panel_backtest_log as log_query
from entropia.domain.backtest.enums import MetricAvailability
from entropia.domain.identity import Actor
from entropia.domain.lifecycle.enums import PrincipalType, Role
from entropia.infrastructure.postgres.models import (
    BacktestResult,
    HumanUser,
    MetricValueRow,
    Principal,
)
from entropia.shared.errors import AdminPanelAccessRequiredError, CursorInvalidError

pytestmark = pytest.mark.integration

USER1 = Actor(principal_id="user_1", principal_type=PrincipalType.HUMAN, role=Role.USER)
USER2 = Actor(principal_id="user_2", principal_type=PrincipalType.HUMAN, role=Role.USER)
ADMIN = Actor(principal_id="admin_1", principal_type=PrincipalType.HUMAN, role=Role.ADMIN)

_BASE_TIME = datetime(2026, 3, 1, tzinfo=UTC)


async def _seed_principals(session) -> None:
    for pid in ("user_1", "user_2", "admin_1"):
        if await session.get(Principal, pid) is None:
            session.add(Principal(principal_id=pid, principal_type=PrincipalType.HUMAN))
    await session.flush()


async def _seed_human(session, uid: str, username: str) -> None:
    session.add(
        HumanUser(
            user_id=uid,
            username=username,
            display_name=username.title(),
            current_role=Role.USER,
            status="active",
            version=1,
        )
    )
    await session.flush()


async def _workspace(session, actor: Actor) -> str:
    mb = await mb_query.get_default_mainboard(session, actor)
    await session.commit()
    return mb["workspace_id"]


def _metric(value: Decimal | None) -> tuple[Decimal | None, MetricAvailability]:
    if value is None:
        return (None, MetricAvailability.NOT_AVAILABLE)
    return (value, MetricAvailability.COMPUTED)


async def _seed_result(
    session,
    *,
    workspace_id: str,
    result_id: str,
    owner: str,
    net_profit: Decimal | None,
    romad: Decimal | None,
    total_trades: Decimal,
    order_index: int,
) -> None:
    """An immutable Result + its three log key metrics (net_profit/romad/total_trades)."""
    session.add(
        BacktestResult(
            result_id=result_id,
            run_id=f"run_{result_id}",
            manifest_id=f"man_{result_id}",
            manifest_hash="a" * 64,
            workspace_entity_id=workspace_id,
            composition_fingerprint=f"fp_{result_id}",
            engine_version="backtest-engine-v1-stub",
            deletion_state="active",
            row_version=1,
            created_by_principal_id=owner,
            created_at=_BASE_TIME + timedelta(hours=order_index),
        )
    )
    await session.flush()
    metrics: dict[str, tuple[Decimal | None, MetricAvailability]] = {
        "net_profit": _metric(net_profit),
        "romad": _metric(romad),
        "total_trades": _metric(total_trades),
    }
    for pos, (key, (value, availability)) in enumerate(metrics.items()):
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
    await session.flush()


async def _seed_two_users(session) -> None:
    """res_a/b/c owned by user_1; res_d (newest) owned by user_2. order_index drives
    created_at so newest-first is d > c > b > a."""
    await _seed_principals(session)
    ws1 = await _workspace(session, USER1)
    ws2 = await _workspace(session, USER2)
    await _seed_result(
        session,
        workspace_id=ws1,
        result_id="res_a",
        owner="user_1",
        net_profit=Decimal("10.0"),
        romad=Decimal("1.0"),
        total_trades=Decimal("5"),
        order_index=0,
    )
    await _seed_result(
        session,
        workspace_id=ws1,
        result_id="res_b",
        owner="user_1",
        net_profit=Decimal("20.0"),
        romad=Decimal("2.0"),
        total_trades=Decimal("8"),
        order_index=1,
    )
    await _seed_result(
        session,
        workspace_id=ws1,
        result_id="res_c",
        owner="user_1",
        net_profit=Decimal("30.0"),
        romad=Decimal("3.0"),
        total_trades=Decimal("11"),
        order_index=2,
    )
    await _seed_result(
        session,
        workspace_id=ws2,
        result_id="res_d",
        owner="user_2",
        net_profit=Decimal("40.0"),
        romad=Decimal("4.0"),
        total_trades=Decimal("14"),
        order_index=3,
    )
    await session.commit()


def _ids(page: dict[str, Any]) -> list[str]:
    return [row["result_id"] for row in page["data"]]


def _by_id(page: dict[str, Any], result_id: str) -> dict[str, Any]:
    return next(row for row in page["data"] if row["result_id"] == result_id)


# --------------------------------------------------------------------------- #
# Admin guard + cross-user visibility                                         #
# --------------------------------------------------------------------------- #


async def test_non_admin_is_denied(session) -> None:
    await _seed_two_users(session)
    with pytest.raises(AdminPanelAccessRequiredError):
        await log_query.list_admin_backtest_log(session, USER1)


async def test_admin_sees_every_users_backtests_newest_first(session) -> None:
    await _seed_two_users(session)
    page = await log_query.list_admin_backtest_log(session, ADMIN)
    # res_d (user_2) is newest, then user_1's c > b > a — all users, one table.
    assert _ids(page) == ["res_d", "res_c", "res_b", "res_a"]
    assert page["meta"]["has_more"] is False


# --------------------------------------------------------------------------- #
# User label — human name with honest raw-id fallback (W3a)                    #
# --------------------------------------------------------------------------- #


async def test_user_label_resolves_human_name_and_falls_back_to_raw_id(session) -> None:
    await _seed_principals(session)
    await _seed_human(session, "user_1", "alice")  # user_2 has NO human_users row
    ws1 = await _workspace(session, USER1)
    ws2 = await _workspace(session, USER2)
    await _seed_result(
        session,
        workspace_id=ws1,
        result_id="res_named",
        owner="user_1",
        net_profit=Decimal("10.0"),
        romad=Decimal("1.0"),
        total_trades=Decimal("5"),
        order_index=0,
    )
    await _seed_result(
        session,
        workspace_id=ws2,
        result_id="res_raw",
        owner="user_2",
        net_profit=Decimal("20.0"),
        romad=Decimal("2.0"),
        total_trades=Decimal("8"),
        order_index=1,
    )
    await session.commit()

    page = await log_query.list_admin_backtest_log(session, ADMIN)
    named = _by_id(page, "res_named")["user"]
    assert named["username"] == "alice"
    assert named["display_name"] == "Alice"
    assert named["principal_id"] == "user_1"

    raw = _by_id(page, "res_raw")["user"]
    assert raw["username"] is None  # never fabricated
    assert raw["display_name"] is None
    assert raw["principal_id"] == "user_2"  # honest raw-id fallback


# --------------------------------------------------------------------------- #
# Metrics come from server-truth (null surfaced, never 0 — L4)                 #
# --------------------------------------------------------------------------- #


async def test_metrics_are_server_truth_with_null_surfaced(session) -> None:
    await _seed_principals(session)
    ws1 = await _workspace(session, USER1)
    await _seed_result(
        session,
        workspace_id=ws1,
        result_id="res_m",
        owner="user_1",
        net_profit=Decimal("42.0"),
        romad=None,
        total_trades=Decimal("9"),
        order_index=0,
    )
    await session.commit()

    row = _by_id(await log_query.list_admin_backtest_log(session, ADMIN), "res_m")
    # Canonical numeric server value (the _MONEY column scale is preserved as a string;
    # the browser formats it via value_format — it is never re-computed there).
    assert Decimal(row["net_profit"]["value"]) == Decimal("42.0")
    assert row["net_profit"]["value_format"] == "decimal2"
    assert row["net_profit"]["availability"] == "computed"
    assert Decimal(row["total_trades"]["value"]) == Decimal("9")
    # A non-computed ROMAD surfaces its availability, never a silent 0 (L4).
    assert row["romad"]["value"] is None
    assert row["romad"]["availability"] != "computed"


async def test_result_without_metric_rows_shows_none_cells(session) -> None:
    await _seed_principals(session)
    ws1 = await _workspace(session, USER1)
    session.add(
        BacktestResult(
            result_id="res_bare",
            run_id="run_bare",
            manifest_id="man_bare",
            manifest_hash="a" * 64,
            workspace_entity_id=ws1,
            composition_fingerprint="fp_bare",
            engine_version="backtest-engine-v1-stub",
            deletion_state="active",
            row_version=1,
            created_by_principal_id="user_1",
            created_at=_BASE_TIME,
        )
    )
    await session.commit()

    row = _by_id(await log_query.list_admin_backtest_log(session, ADMIN), "res_bare")
    assert row["net_profit"] is None
    assert row["romad"] is None
    assert row["total_trades"] is None


# --------------------------------------------------------------------------- #
# Cursor pagination — newest-first, no dup/skip                                #
# --------------------------------------------------------------------------- #


async def test_cursor_pagination_has_no_duplicate_or_skip(session) -> None:
    await _seed_two_users(session)
    first = await log_query.list_admin_backtest_log(session, ADMIN, limit=2)
    assert _ids(first) == ["res_d", "res_c"]
    assert first["meta"]["cursor"] is not None

    second = await log_query.list_admin_backtest_log(
        session, ADMIN, limit=2, cursor=first["meta"]["cursor"]
    )
    assert _ids(second) == ["res_b", "res_a"]
    assert second["meta"]["cursor"] is None
    assert set(_ids(first)) & set(_ids(second)) == set()


async def test_equal_created_at_paginates_on_result_id_tiebreak(session) -> None:
    """Ties on created_at must page on the result_id DESC tie-break with no dup/skip."""
    await _seed_principals(session)
    ws1 = await _workspace(session, USER1)
    for rid in ("res_t1", "res_t2", "res_t3"):
        await _seed_result(
            session,
            workspace_id=ws1,
            result_id=rid,
            owner="user_1",
            net_profit=Decimal("1.0"),
            romad=Decimal("1.0"),
            total_trades=Decimal("1"),
            order_index=0,  # identical created_at -> forces the result_id tie-break
        )
    await session.commit()

    seen: list[str] = []
    cursor: str | None = None
    for _ in range(5):  # bounded walk, one row per page across the tie
        page = await log_query.list_admin_backtest_log(session, ADMIN, limit=1, cursor=cursor)
        seen.extend(_ids(page))
        cursor = page["meta"]["cursor"]
        if cursor is None:
            break
    assert seen == ["res_t3", "res_t2", "res_t1"]  # deterministic result_id DESC
    assert sorted(seen) == ["res_t1", "res_t2", "res_t3"]  # all present, no dup/skip


async def test_malformed_cursor_is_rejected(session) -> None:
    await _seed_two_users(session)
    with pytest.raises(CursorInvalidError):
        await log_query.list_admin_backtest_log(session, ADMIN, cursor="not-a-real-cursor")


# --------------------------------------------------------------------------- #
# Soft-deleted result absent                                                   #
# --------------------------------------------------------------------------- #


async def test_soft_deleted_result_absent_from_log(session) -> None:
    await _seed_two_users(session)
    result = await session.get(BacktestResult, "res_c")
    result.deletion_state = "soft_deleted"
    await session.commit()

    page = await log_query.list_admin_backtest_log(session, ADMIN)
    assert _ids(page) == ["res_d", "res_b", "res_a"]  # res_c gone, others intact
