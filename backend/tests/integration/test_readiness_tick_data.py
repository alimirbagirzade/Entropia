"""F-07i sub-slice A — Ready Check tick-data requirement against a real database.

'Use Tick Data = Yes' (``intrabar_policy.tick_policy == 'require'``) makes an approved
tick/trade revision for the strategy's instrument mandatory (Master Ref §6.4). Ready
Check must evaluate dataset-resolution sufficiency and BLOCK RUN when it is unmet
(Master Ref §11.2 / line ~3558) rather than silently resolving the intrabar-sensitive
execution over OHLCV. This mirrors ``test_unapproved_market_dataset_blocks_then_approved
_passes``: a require-tick strategy with no approved tick dataset -> TICK_DATA_UNAVAILABLE
blocker; seed an approved tick revision for the instrument -> the blocker clears.

The engine itself STILL fails closed on the tick-DEPENDENT execution SETTINGS (the real
intrabar-path replay is sub-slice B); this slice only wires the Ready Check requirement.

Auto-skips when no PostgreSQL is reachable (see tests/integration/conftest.py).
"""

from __future__ import annotations

import copy
from typing import Any

import pytest

from entropia.application.commands import mainboard as mb_cmd
from entropia.application.commands import readiness_check as readiness_cmd
from entropia.domain.lifecycle.enums import (
    ApprovalState,
    PackageKind,
    VisibilityScope,
)
from entropia.domain.market_data.enums import MarketDataType, MarketRevisionState
from entropia.domain.package.enums import PackageValidationState
from entropia.infrastructure.postgres.models import EntityRegistry, MarketDatasetRevision
from entropia.infrastructure.postgres.repositories import packages as pkg_repo

# Reuse the seeding helpers from the sibling readiness persistence suite.
from tests.integration.test_readiness_persistence import (
    USER1,
    _empty_composition,
    _seed_market_revision,
    _seed_principals,
    _strategy_payload,
)

pytestmark = pytest.mark.integration


async def _seed_tick_revision(
    session, *, instrument_id: str = "BTCUSDT", state: MarketRevisionState
) -> None:
    """Seed one tick/trade dataset revision for ``instrument_id`` in ``state``.

    Lives under its own ACTIVE market_dataset root (distinct from the OHLCV md_root_1).
    ``deletion_state`` defaults to ACTIVE on the registry row.
    """
    root = await session.get(EntityRegistry, "tick_root_1")
    if root is None:
        root = EntityRegistry(
            entity_id="tick_root_1",
            entity_type="market_dataset",
            owner_principal_id="user_1",
            created_by_principal_id="user_1",
            lifecycle_state="active",
            current_revision_id=None,
        )
        session.add(root)
        await session.flush()
        session.add(
            MarketDatasetRevision(
                revision_id="tick_rev_1",
                entity_id=root.entity_id,
                revision_no=1,
                market_data_type=MarketDataType.TICK_TRADES,
                revision_state=state,
                instrument_id=instrument_id,
                payload={},
                content_hash="c" * 64,
                created_by_principal_id="user_1",
            )
        )
        root.current_revision_id = "tick_rev_1"
    else:
        revision = await session.get(MarketDatasetRevision, "tick_rev_1")
        assert revision is not None
        revision.revision_state = state
    await session.flush()


async def _composition_requiring_tick(session, actor) -> str:
    """A composition whose one strategy sets 'Use Tick Data = Yes' (tick_policy=require).

    Mirrors ``_composition_with_strategy`` but flips the intrabar policy to ``require``.
    """
    await _seed_market_revision(session, MarketRevisionState.APPROVED)
    workspace_id = await _empty_composition(session, actor)
    _reg, _pkg_root, pkg_rev = await pkg_repo.create_package(
        session,
        owner_principal_id=None,
        created_by_principal_id=None,
        package_kind=PackageKind.INDICATOR,
        input_contract={"source": "close"},
        output_contract={"kind": "directional_signal"},
        dependency_snapshot={"resolved": [{"call": "ta.sma", "canonical_key": "ta.sma"}]},
        visibility_scope=VisibilityScope.PUBLISHED,
        validation_state=PackageValidationState.PASSED,
        approval_state=ApprovalState.APPROVED,
    )
    await session.flush()
    payload: dict[str, Any] = copy.deepcopy(
        _strategy_payload(indicator_revision_id=pkg_rev.revision_id)
    )
    payload["data"]["intrabar_policy"]["tick_policy"] = "require"
    work_object = await mb_cmd.create_work_object(
        session, actor, object_kind="strategy", payload=payload
    )
    await mb_cmd.attach_mainboard_item(
        session,
        actor,
        workspace_id=workspace_id,
        root_id=work_object["root_id"],
        revision_id=work_object["revision_id"],
        item_kind="strategy",
    )
    await session.commit()
    return workspace_id


async def test_require_tick_without_approved_tick_data_blocks_then_passes(session) -> None:
    await _seed_principals(session)
    composition_id = await _composition_requiring_tick(session, USER1)

    # No approved tick dataset for BTCUSDT yet -> the require-tick strategy blocks RUN.
    blocked = await readiness_cmd.run_readiness_check(session, USER1, composition_id=composition_id)
    assert blocked["state"] == "not_ready"
    assert any(i["code"] == "TICK_DATA_UNAVAILABLE" for i in blocked["issues"])

    # A tick revision that is not yet APPROVED does not satisfy the requirement.
    await _seed_tick_revision(session, state=MarketRevisionState.NEEDS_REVIEW)
    still_blocked = await readiness_cmd.run_readiness_check(
        session, USER1, composition_id=composition_id
    )
    assert still_blocked["state"] == "not_ready"
    assert any(i["code"] == "TICK_DATA_UNAVAILABLE" for i in still_blocked["issues"])

    # Approving a matching-instrument tick revision clears the tick blocker.
    await _seed_tick_revision(session, state=MarketRevisionState.APPROVED)
    approved = await readiness_cmd.run_readiness_check(
        session, USER1, composition_id=composition_id
    )
    assert approved["state"] == "ready"
    assert not any(i["code"] == "TICK_DATA_UNAVAILABLE" for i in approved["issues"])


async def test_require_tick_with_wrong_instrument_tick_data_stays_blocked(session) -> None:
    await _seed_principals(session)
    composition_id = await _composition_requiring_tick(session, USER1)

    # An APPROVED tick revision for a DIFFERENT instrument does not satisfy BTCUSDT.
    await _seed_tick_revision(session, instrument_id="ETHUSDT", state=MarketRevisionState.APPROVED)
    result = await readiness_cmd.run_readiness_check(session, USER1, composition_id=composition_id)
    assert result["state"] == "not_ready"
    assert any(i["code"] == "TICK_DATA_UNAVAILABLE" for i in result["issues"])
