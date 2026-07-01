"""Stage 5b — Results History read model against a real database (doc 16 §16).

Auto-skips without PostgreSQL (tests/integration/conftest.py). A real workspace is
created via the 3a Mainboard query (so ``entity_registry`` carries the owner +
active deletion state the visibility join needs); immutable ``backtest_result`` +
``metric_value`` rows are then seeded directly for precise, deterministic control
over the canonical numeric sort. Covers: default newest-first; canonical numeric
sort (highest return / lowest drawdown / highest ROMAD nulls-last); cursor
pagination (no duplicates, null tail); owner/Admin visibility; soft-deleted results
absent; compare context-diff + exactly-two-distinct guard; null metric surfaced
(never 0, L4).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest

from entropia.application.queries import mainboard as mb_query
from entropia.application.queries import results_history as history_query
from entropia.domain.backtest.enums import MetricAvailability
from entropia.domain.identity import Actor
from entropia.domain.lifecycle.enums import PrincipalType, Role
from entropia.infrastructure.postgres.models import (
    BacktestResult,
    MetricValueRow,
    Principal,
    ResultManifestSnapshot,
)
from entropia.shared.errors import (
    AccessDeniedError,
    CompareRequiresTwoDistinctResultsError,
)

pytestmark = pytest.mark.integration

USER1 = Actor(principal_id="user_1", principal_type=PrincipalType.HUMAN, role=Role.USER)
USER2 = Actor(principal_id="user_2", principal_type=PrincipalType.HUMAN, role=Role.USER)
ADMIN = Actor(principal_id="admin_1", principal_type=PrincipalType.HUMAN, role=Role.ADMIN)

_BASE_TIME = datetime(2026, 1, 1, tzinfo=UTC)


async def _seed_principals(session) -> None:
    for pid in ("user_1", "user_2", "admin_1"):
        if await session.get(Principal, pid) is None:
            session.add(Principal(principal_id=pid, principal_type=PrincipalType.HUMAN))
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
    net_profit: Decimal,
    romad: Decimal | None,
    max_drawdown: Decimal,
    win_rate: Decimal,
    total_trades: Decimal,
    order_index: int,
    engine_version: str = "backtest-engine-v1-stub",
    execution_key: str = "ek-shared",
) -> None:
    """Insert an immutable Result + its 5 key metrics + a manifest snapshot."""
    session.add(
        BacktestResult(
            result_id=result_id,
            run_id=f"run_{result_id}",
            manifest_id=f"man_{result_id}",
            manifest_hash="a" * 64,
            workspace_entity_id=workspace_id,
            composition_fingerprint=f"fp_{result_id}",
            engine_version=engine_version,
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
        "max_drawdown": _metric(max_drawdown),
        "win_rate": _metric(win_rate),
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
    session.add(
        ResultManifestSnapshot(
            snapshot_id=f"snap_{result_id}",
            result_id=result_id,
            manifest_hash="a" * 64,
            execution_key=execution_key,
            engine_version=engine_version,
            manifest={
                "identity": {"engine_version": engine_version, "composition_fingerprint": "fp"},
                "execution_key": execution_key,
                "capital_execution": {"mode": "portfolio"},
            },
        )
    )
    await session.flush()


async def _seed_three(session) -> str:
    """Seed A/B/C owned by user_1 with distinct metric orderings.

    order_index sets created_at: C(newest) > B > A(oldest).
    """
    await _seed_principals(session)
    workspace_id = await _workspace(session, USER1)
    # A: mid return, romad 2, dd 10, wr 60, 10 trades
    await _seed_result(
        session,
        workspace_id=workspace_id,
        result_id="res_a",
        owner="user_1",
        net_profit=Decimal("50.0"),
        romad=Decimal("2.0"),
        max_drawdown=Decimal("10.0"),
        win_rate=Decimal("60.0"),
        total_trades=Decimal("10"),
        order_index=0,
    )
    # B: highest return, NO romad (null), lowest dd, wr 55, most trades
    await _seed_result(
        session,
        workspace_id=workspace_id,
        result_id="res_b",
        owner="user_1",
        net_profit=Decimal("80.0"),
        romad=None,
        max_drawdown=Decimal("5.0"),
        win_rate=Decimal("55.0"),
        total_trades=Decimal("20"),
        order_index=1,
        engine_version="backtest-engine-v2-stub",
    )
    # C: lowest return, highest romad, highest dd, highest wr, fewest trades, newest
    await _seed_result(
        session,
        workspace_id=workspace_id,
        result_id="res_c",
        owner="user_1",
        net_profit=Decimal("30.0"),
        romad=Decimal("3.0"),
        max_drawdown=Decimal("20.0"),
        win_rate=Decimal("70.0"),
        total_trades=Decimal("5"),
        order_index=2,
    )
    await session.commit()
    return workspace_id


def _ids(page: dict[str, Any]) -> list[str]:
    return [item["result_id"] for item in page["items"]]


# --------------------------------------------------------------------------- #
# Listing + canonical numeric sort                                            #
# --------------------------------------------------------------------------- #


async def test_default_sort_is_newest_first(session) -> None:
    await _seed_three(session)
    page = await history_query.list_backtest_results(session, USER1)
    assert _ids(page) == ["res_c", "res_b", "res_a"]  # completed_at DESC
    assert page["sort"] == "newest_current"


async def test_highest_return_sorts_by_net_profit_desc(session) -> None:
    await _seed_three(session)
    page = await history_query.list_backtest_results(session, USER1, sort="highestReturn")
    assert _ids(page) == ["res_b", "res_a", "res_c"]


async def test_lowest_drawdown_sorts_by_absolute_drawdown_asc(session) -> None:
    await _seed_three(session)
    page = await history_query.list_backtest_results(session, USER1, sort="lowestDrawdown")
    assert _ids(page) == ["res_b", "res_a", "res_c"]  # dd 5 < 10 < 20


async def test_highest_romad_places_null_last(session) -> None:
    await _seed_three(session)
    page = await history_query.list_backtest_results(session, USER1, sort="romad_desc")
    assert _ids(page) == ["res_c", "res_a", "res_b"]  # 3.0, 2.0, null last
    # The null-romad result surfaces a non-computed availability, never 0 (L4).
    res_b = next(item for item in page["items"] if item["result_id"] == "res_b")
    assert res_b["key_metrics"]["romad"]["value"] is None
    assert res_b["key_metrics"]["romad"]["availability"] != "computed"


# --------------------------------------------------------------------------- #
# Cursor pagination                                                           #
# --------------------------------------------------------------------------- #


async def test_cursor_pagination_has_no_duplicates(session) -> None:
    await _seed_three(session)
    first = await history_query.list_backtest_results(
        session, USER1, sort="net_profit_percent_desc", limit=2
    )
    assert _ids(first) == ["res_b", "res_a"]
    assert first["next_cursor"] is not None

    second = await history_query.list_backtest_results(
        session, USER1, sort="net_profit_percent_desc", limit=2, cursor=first["next_cursor"]
    )
    assert _ids(second) == ["res_c"]
    assert second["next_cursor"] is None
    assert set(_ids(first)) & set(_ids(second)) == set()  # no duplicate cards (RH-07)


async def test_cursor_pagination_walks_into_null_tail(session) -> None:
    await _seed_three(session)
    first = await history_query.list_backtest_results(session, USER1, sort="romad_desc", limit=2)
    assert _ids(first) == ["res_c", "res_a"]

    second = await history_query.list_backtest_results(
        session, USER1, sort="romad_desc", limit=2, cursor=first["next_cursor"]
    )
    assert _ids(second) == ["res_b"]  # the null-romad row, last


# --------------------------------------------------------------------------- #
# Visibility (owner / Admin) + soft delete                                    #
# --------------------------------------------------------------------------- #


async def test_foreign_user_sees_no_results(session) -> None:
    await _seed_three(session)
    page = await history_query.list_backtest_results(session, USER2)
    assert page["items"] == []


async def test_admin_sees_all_results(session) -> None:
    await _seed_three(session)
    page = await history_query.list_backtest_results(session, ADMIN)
    assert set(_ids(page)) == {"res_a", "res_b", "res_c"}


async def test_soft_deleted_result_absent_from_history(session) -> None:
    await _seed_three(session)
    result = await session.get(BacktestResult, "res_a")
    result.deletion_state = "soft_deleted"
    await session.commit()
    page = await history_query.list_backtest_results(session, USER1)
    assert _ids(page) == ["res_c", "res_b"]  # run manifest/provenance untouched


# --------------------------------------------------------------------------- #
# Compare                                                                     #
# --------------------------------------------------------------------------- #


async def test_compare_flags_context_difference(session) -> None:
    await _seed_three(session)
    # res_a engine v1, res_b engine v2 -> engine_version differs (RH-09).
    compare = await history_query.compare_backtest_results(
        session, USER1, result_ids=["res_a", "res_b"]
    )
    assert compare["context_differs"] is True
    assert compare["context"]["fields"]["engine_version"]["differs"] is True
    # Neither pins a Market Data revision -> honest "Not available", not flagged.
    assert compare["context"]["fields"]["market_data_revision"]["differs"] is False
    assert {r["result_id"] for r in compare["results"]} == {"res_a", "res_b"}


async def test_compare_same_id_is_rejected(session) -> None:
    await _seed_three(session)
    with pytest.raises(CompareRequiresTwoDistinctResultsError):
        await history_query.compare_backtest_results(session, USER1, result_ids=["res_a", "res_a"])


async def test_compare_foreign_result_is_denied(session) -> None:
    await _seed_three(session)
    with pytest.raises(AccessDeniedError):
        await history_query.compare_backtest_results(session, USER2, result_ids=["res_a", "res_b"])


# --------------------------------------------------------------------------- #
# Keyset regressions (adversarial review follow-ups)                          #
# --------------------------------------------------------------------------- #


async def test_equal_metric_values_paginate_without_duplicate_or_skip(session) -> None:
    """Tie-break stability: equal metric values must paginate with a deterministic
    result_id DESC order and no duplicate/skipped rows across pages (keyset needs a
    stable total order, not a chronological id)."""
    await _seed_principals(session)
    workspace_id = await _workspace(session, USER1)
    for idx, rid in enumerate(("res_t1", "res_t2", "res_t3")):
        await _seed_result(
            session,
            workspace_id=workspace_id,
            result_id=rid,
            owner="user_1",
            net_profit=Decimal("42.0"),  # identical -> forces the result_id tie-break
            romad=Decimal("1.0"),
            max_drawdown=Decimal("1.0"),
            win_rate=Decimal("1.0"),
            total_trades=Decimal("1"),
            order_index=idx,
        )
    await session.commit()

    seen: list[str] = []
    cursor: str | None = None
    for _ in range(5):  # bounded walk, one row per page across the tie
        page = await history_query.list_backtest_results(
            session, USER1, sort="net_profit_percent_desc", limit=1, cursor=cursor
        )
        seen.extend(_ids(page))
        cursor = page["next_cursor"]
        if cursor is None:
            break

    assert seen == ["res_t3", "res_t2", "res_t1"]  # deterministic result_id DESC
    assert sorted(seen) == ["res_t1", "res_t2", "res_t3"]  # all present, no dup/skip


async def test_result_missing_sort_metric_row_stays_indexed_in_null_tail(session) -> None:
    """A result with no metric_value row for the sort key must fall into the NULL
    tail via the outer join, never silently vanish from the index (doc 16 §9.2)."""
    await _seed_three(session)
    row = await session.get(MetricValueRow, "mv_res_c_romad")
    await session.delete(row)  # simulate schema drift / repair gap for one result
    await session.commit()

    page = await history_query.list_backtest_results(session, USER1, sort="romad_desc")
    ids = _ids(page)
    assert set(ids) == {"res_a", "res_b", "res_c"}  # none dropped
    assert ids[0] == "res_a"  # the only computed romad (2.0) leads; res_b/res_c null tail
