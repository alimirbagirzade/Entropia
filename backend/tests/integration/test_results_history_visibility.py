"""Results History visibility against a real database (doc 16 §2; finding O-14).

Before O-14 the history index answered ``owner OR Admin`` only: the generic
``resource_share`` table (already carrying Package grants, GAP-17) was never
joined, so doc 16 §2's "own + explicitly shared + published" collapsed to "own",
and Supervisor was indistinguishable from User at the query level. These tests
pin the corrected contract end to end — list, detail and compare — plus the
fail-closed edges (revoked grant, wrong resource_type, stranger).

Auto-skips without PostgreSQL (tests/integration/conftest.py).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest

from entropia.application.queries import results_history as history_query
from entropia.application.queries.backtest_run import get_backtest_result
from entropia.domain.backtest.enums import MetricAvailability
from entropia.domain.identity import Actor
from entropia.domain.lifecycle.enums import PrincipalType, Role
from entropia.domain.mainboard.enums import WorkspaceKind
from entropia.domain.sharing import ShareResourceType
from entropia.infrastructure.postgres.models import (
    BacktestResult,
    MetricValueRow,
    Principal,
    ResultManifestSnapshot,
)
from entropia.infrastructure.postgres.repositories import mainboard as mb_repo
from entropia.infrastructure.postgres.repositories import resource_share as share_repo
from entropia.shared.errors import AccessDeniedError

pytestmark = pytest.mark.integration

OWNER = Actor(principal_id="user_owner", principal_type=PrincipalType.HUMAN, role=Role.USER)
GRANTEE = Actor(principal_id="user_grantee", principal_type=PrincipalType.HUMAN, role=Role.USER)
STRANGER = Actor(principal_id="user_stranger", principal_type=PrincipalType.HUMAN, role=Role.USER)
SUPERVISOR = Actor(
    principal_id="user_supervisor", principal_type=PrincipalType.HUMAN, role=Role.SUPERVISOR
)
ADMIN = Actor(principal_id="admin_1", principal_type=PrincipalType.HUMAN, role=Role.ADMIN)
AGENT = Actor(principal_id="agent_1", principal_type=PrincipalType.AGENT, role=None)

_COMPOSITION = str(ShareResourceType.COMPOSITION)
_BASE_TIME = datetime(2026, 3, 1, tzinfo=UTC)
_HUMANS = ("user_owner", "user_grantee", "user_stranger", "user_supervisor", "admin_1")


async def _seed_principals(session) -> None:
    for pid in _HUMANS:
        if await session.get(Principal, pid) is None:
            session.add(Principal(principal_id=pid, principal_type=PrincipalType.HUMAN))
    if await session.get(Principal, "agent_1") is None:
        session.add(Principal(principal_id="agent_1", principal_type=PrincipalType.AGENT))
    await session.flush()


async def _workspace(session, *, owner: str, kind: WorkspaceKind) -> str:
    _root, detail = await mb_repo.create_workspace(
        session,
        owner_principal_id=owner,
        created_by_principal_id=owner,
        workspace_kind=kind,
        title=None,
        is_default=True,
    )
    await session.flush()
    return detail.entity_id


async def _seed_result(
    session,
    *,
    workspace_id: str,
    result_id: str,
    owner: str,
    order_index: int,
    engine_version: str = "backtest-engine-vis-stub",
) -> None:
    """One immutable Result + a single computed metric + its manifest snapshot."""
    session.add(
        BacktestResult(
            result_id=result_id,
            run_id=f"run_{result_id}",
            manifest_id=f"man_{result_id}",
            manifest_hash="c" * 64,
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
    session.add(
        MetricValueRow(
            metric_value_id=f"mv_{result_id}_net_profit",
            result_id=result_id,
            metric_key="net_profit",
            label="Net Profit",
            unit="ratio",
            value_format="decimal2",
            value=Decimal("10.0") + order_index,
            availability=MetricAvailability.COMPUTED,
            formula_version="v1",
            position_index=0,
        )
    )
    session.add(
        ResultManifestSnapshot(
            snapshot_id=f"snap_{result_id}",
            result_id=result_id,
            manifest_hash="c" * 64,
            execution_key=f"ek_{result_id}",
            engine_version=engine_version,
            manifest={
                "identity": {"engine_version": engine_version, "composition_fingerprint": "fp"},
                "execution_key": f"ek_{result_id}",
                "capital_execution": {"mode": "portfolio"},
            },
        )
    )
    await session.flush()


def _grant(session, *, workspace_id: str, grantee: str, resource_type: str = _COMPOSITION) -> Any:
    """An ACTIVE grant written through the SAME repo Package sharing uses."""
    return share_repo.create_share(
        session,
        resource_type=resource_type,
        resource_id=workspace_id,
        grantee_principal_id=grantee,
        granted_by_principal_id="user_owner",
    )


def _ids(page: dict[str, Any]) -> list[str]:
    return [item["result_id"] for item in page["items"]]


async def _seed_owner_workspace(session) -> str:
    """Two Results owned by ``user_owner`` in one human composition."""
    await _seed_principals(session)
    workspace_id = await _workspace(session, owner="user_owner", kind=WorkspaceKind.HUMAN_DEFAULT)
    await _seed_result(
        session, workspace_id=workspace_id, result_id="res_o1", owner="user_owner", order_index=0
    )
    await _seed_result(
        session, workspace_id=workspace_id, result_id="res_o2", owner="user_owner", order_index=1
    )
    await session.commit()
    return workspace_id


# --------------------------------------------------------------------------- #
# Explicit share — the doc 16 §2 "explicitly shared" column                    #
# --------------------------------------------------------------------------- #


async def test_owner_still_sees_own_results(session) -> None:
    await _seed_owner_workspace(session)
    page = await history_query.list_backtest_results(session, OWNER)
    assert _ids(page) == ["res_o2", "res_o1"]
    assert all(item["allowed_actions"]["soft_delete"] is True for item in page["items"])


async def test_grantee_of_a_shared_composition_sees_its_results(session) -> None:
    workspace_id = await _seed_owner_workspace(session)
    assert _ids(await history_query.list_backtest_results(session, GRANTEE)) == []

    _grant(session, workspace_id=workspace_id, grantee="user_grantee")
    await session.commit()

    page = await history_query.list_backtest_results(session, GRANTEE)
    assert _ids(page) == ["res_o2", "res_o1"]
    # doc 16 §2 "someone else's result is read-only": a grantee reads, never deletes.
    assert all(item["allowed_actions"]["soft_delete"] is False for item in page["items"])


async def test_grantee_can_read_detail_and_compare(session) -> None:
    workspace_id = await _seed_owner_workspace(session)
    _grant(session, workspace_id=workspace_id, grantee="user_grantee")
    await session.commit()

    detail = await get_backtest_result(session, GRANTEE, result_id="res_o1")
    assert detail["result_id"] == "res_o1"

    compare = await history_query.compare_backtest_results(
        session, GRANTEE, result_ids=["res_o1", "res_o2"]
    )
    assert {row["result_id"] for row in compare["results"]} == {"res_o1", "res_o2"}


async def test_revoked_share_drops_the_results_again(session) -> None:
    workspace_id = await _seed_owner_workspace(session)
    grant = _grant(session, workspace_id=workspace_id, grantee="user_grantee")
    await session.commit()
    assert _ids(await history_query.list_backtest_results(session, GRANTEE)) != []

    share_repo.revoke_share(grant, revoked_by_principal_id="user_owner", now=datetime.now(UTC))
    await session.commit()

    assert _ids(await history_query.list_backtest_results(session, GRANTEE)) == []
    with pytest.raises(AccessDeniedError):
        await get_backtest_result(session, GRANTEE, result_id="res_o1")


async def test_a_package_grant_never_opens_a_composition(session) -> None:
    """Fail-closed across resource types: the grant is keyed by BOTH columns, so a
    ``package`` grant that happens to carry the composition id grants nothing."""
    workspace_id = await _seed_owner_workspace(session)
    _grant(
        session,
        workspace_id=workspace_id,
        grantee="user_grantee",
        resource_type=str(ShareResourceType.PACKAGE),
    )
    await session.commit()

    assert _ids(await history_query.list_backtest_results(session, GRANTEE)) == []
    with pytest.raises(AccessDeniedError):
        await get_backtest_result(session, GRANTEE, result_id="res_o1")


async def test_stranger_sees_nothing_and_is_denied_on_detail_and_compare(session) -> None:
    workspace_id = await _seed_owner_workspace(session)
    _grant(session, workspace_id=workspace_id, grantee="user_grantee")
    await session.commit()

    assert _ids(await history_query.list_backtest_results(session, STRANGER)) == []
    with pytest.raises(AccessDeniedError):
        await get_backtest_result(session, STRANGER, result_id="res_o1")
    with pytest.raises(AccessDeniedError):
        await history_query.compare_backtest_results(
            session, STRANGER, result_ids=["res_o1", "res_o2"]
        )


async def test_admin_sees_every_result(session) -> None:
    await _seed_owner_workspace(session)
    page = await history_query.list_backtest_results(session, ADMIN)
    assert set(_ids(page)) == {"res_o1", "res_o2"}
    assert all(item["allowed_actions"]["soft_delete"] is True for item in page["items"])


# --------------------------------------------------------------------------- #
# Supervisor — the doc 16 §2 "accessible/shared work scope" column             #
# --------------------------------------------------------------------------- #


async def _seed_agent_workspace(session) -> str:
    workspace_id = await _workspace(session, owner="agent_1", kind=WorkspaceKind.AGENT_RESEARCH)
    await _seed_result(
        session, workspace_id=workspace_id, result_id="res_lab", owner="agent_1", order_index=5
    )
    await session.commit()
    return workspace_id


async def test_supervisor_sees_agent_research_results_read_only(session) -> None:
    """The Analysis Lab already opens the Agent research scope to (Admin, Supervisor);
    a Result produced there is inside that same accessible work scope — read-only."""
    await _seed_owner_workspace(session)
    await _seed_agent_workspace(session)

    page = await history_query.list_backtest_results(session, SUPERVISOR)
    assert _ids(page) == ["res_lab"]
    assert page["items"][0]["allowed_actions"]["soft_delete"] is False

    detail = await get_backtest_result(session, SUPERVISOR, result_id="res_lab")
    assert detail["result_id"] == "res_lab"


async def test_supervisor_does_not_see_another_humans_private_results(session) -> None:
    """The lab scope is not a master key: a private human composition stays closed."""
    await _seed_owner_workspace(session)

    assert _ids(await history_query.list_backtest_results(session, SUPERVISOR)) == []
    with pytest.raises(AccessDeniedError):
        await get_backtest_result(session, SUPERVISOR, result_id="res_o1")


async def test_plain_user_never_sees_agent_research_results(session) -> None:
    await _seed_principals(session)
    await _seed_agent_workspace(session)
    assert _ids(await history_query.list_backtest_results(session, STRANGER)) == []


async def test_supervisor_still_sees_own_and_shared_results(session) -> None:
    """The lab scope is ADDITIVE: own + explicitly shared keep working for a
    Supervisor exactly as they do for a User."""
    workspace_id = await _seed_owner_workspace(session)
    await _seed_agent_workspace(session)
    _grant(session, workspace_id=workspace_id, grantee="user_supervisor")
    await session.commit()

    page = await history_query.list_backtest_results(session, SUPERVISOR)
    assert set(_ids(page)) == {"res_o1", "res_o2", "res_lab"}


async def test_shared_and_lab_rows_page_through_one_authorized_set(session) -> None:
    """``has_more``/cursor must count the AUTHORIZED set: paginating the mixed
    own/shared/lab scope yields every row once, with no post-filtered gap."""
    workspace_id = await _seed_owner_workspace(session)
    await _seed_agent_workspace(session)
    _grant(session, workspace_id=workspace_id, grantee="user_supervisor")
    await session.commit()

    seen: list[str] = []
    cursor: str | None = None
    for _ in range(5):
        page = await history_query.list_backtest_results(
            session, SUPERVISOR, limit=2, cursor=cursor
        )
        seen.extend(_ids(page))
        cursor = page["next_cursor"]
        if cursor is None:
            break

    assert sorted(seen) == ["res_lab", "res_o1", "res_o2"]
