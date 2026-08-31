"""O-01 — the Research Data validator layer against a real database (doc 14 §9.2).

Doc 12 §9.2: "Ready Check and Backtest worker must validate the bundle again
server-side." Before this slice the Research layer existed ONLY in the worker
(``queries/funding.py`` -> ``FundingSourceInvalid``), so a composition pinning an
``agent_research_only`` revision reported READY, was ADMITTED, and then died inside
the worker. These cases prove the upfront gate: Ready Check reports NOT_READY with
``USAGE_SCOPE_FORBIDDEN``, RUN raises 422 ``READINESS_BLOCKED``, and no run, manifest
or job row is left behind. The worker gate stays in place (F-11 suite) — doc 12 §9.2
wants BOTH layers, because eligibility can change between admission and execution.

Auto-skips when no PostgreSQL is reachable (see tests/integration/conftest.py).
"""

from __future__ import annotations

import copy
from typing import Any

import pytest
from sqlalchemy import func, select

from entropia.application.commands import backtest_run as backtest_cmd
from entropia.application.commands import mainboard as mb_cmd
from entropia.application.commands import readiness_check as readiness_cmd
from entropia.domain.lifecycle.enums import (
    ApprovalState,
    PackageKind,
    ValidationStatus,
    VisibilityScope,
)
from entropia.domain.market_data.enums import MarketRevisionState
from entropia.domain.package.enums import PackageValidationState
from entropia.domain.research_data.enums import (
    AvailableTimePolicy,
    ResearchCategory,
    ResearchRevisionState,
    UsageScope,
)
from entropia.infrastructure.postgres.models import BacktestRun, BacktestRunManifest, Job
from entropia.infrastructure.postgres.models.registry import EntityRegistry
from entropia.infrastructure.postgres.models.research_data import ResearchDatasetRevision
from entropia.infrastructure.postgres.repositories import packages as pkg_repo
from entropia.shared.errors import ReadinessBlockedError

# Reuse the seeding helpers from the sibling readiness persistence suite.
from tests.integration.test_readiness_persistence import (
    USER1,
    _empty_composition,
    _seed_market_revision,
    _seed_principals,
    _strategy_payload,
)

pytestmark = pytest.mark.integration

_RESEARCH_ROOT = "rdent_ready_1"
_RESEARCH_REVISION = "rdrev_ready_1"
_RESEARCH_HASH = "f" * 64


async def _seed_research_revision(
    session,
    *,
    scope: UsageScope = UsageScope.RESEARCH_BACKTEST,
    state: ResearchRevisionState = ResearchRevisionState.APPROVED,
    available_time_policy: AvailableTimePolicy | None = AvailableTimePolicy.SAME_AS_EVENT_TIME,
    validation_status: ValidationStatus = ValidationStatus.PASS,
) -> None:
    """Insert (or re-shape) the one funding research revision the strategy pins."""
    revision = await session.get(ResearchDatasetRevision, _RESEARCH_REVISION)
    if revision is None:
        session.add(
            EntityRegistry(
                entity_id=_RESEARCH_ROOT,
                entity_type="research_dataset",
                owner_principal_id="user_1",
                created_by_principal_id="user_1",
                lifecycle_state="active",
            )
        )
        await session.flush()
        revision = ResearchDatasetRevision(
            revision_id=_RESEARCH_REVISION,
            entity_id=_RESEARCH_ROOT,
            revision_no=1,
            category_key=ResearchCategory.FUNDING_RATE.value,
            payload={},
            content_hash=_RESEARCH_HASH,
            created_by_principal_id="user_1",
        )
        session.add(revision)
    revision.revision_state = state
    revision.usage_scope = scope
    revision.available_time_policy = available_time_policy
    revision.available_delay_seconds = None
    revision.validation_status = validation_status
    # GH #703 §Karar 2 = `A` (signed 2026-08-31): pull the seed to the production shape.
    # Before the writer landed, this helper set NEITHER half, and the coherence rule
    # calls "neither" coherent -- so six green cases here were consistent with the very
    # defect ADIM 140 measured. Both halves are now what ``create_research_dataset``
    # leaves behind: the link points at the market revision ``_strategy_payload`` pins
    # (equal, so the sibling DEPENDENCY_BLOCKED cannot fire) and the mapping ref is that
    # revision's own ``instrument_id``, copied.
    revision.linked_market_dataset_revision_id = "md_rev_1"
    revision.instrument_mapping_ref = "BTCUSDT"
    await session.flush()


async def _composition_with_funding_strategy(session, actor) -> str:
    """A composition whose one strategy enables funding against the seeded revision."""
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
    payload["data"]["funding"] = {
        "enabled": True,
        "source_root_id": _RESEARCH_ROOT,
        "source_revision_id": _RESEARCH_REVISION,
        "source_content_hash": _RESEARCH_HASH,
    }
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


async def _count(session, model) -> int:
    return int((await session.execute(select(func.count()).select_from(model))).scalar_one())


async def test_agent_research_only_pin_blocks_ready_check_then_clears_on_scope_fix(
    session,
) -> None:
    await _seed_principals(session)
    await _seed_research_revision(session, scope=UsageScope.AGENT_RESEARCH_ONLY)
    composition_id = await _composition_with_funding_strategy(session, USER1)

    blocked = await readiness_cmd.run_readiness_check(session, USER1, composition_id=composition_id)
    assert blocked["state"] == "not_ready"
    forbidden = [i for i in blocked["issues"] if i["code"] == "USAGE_SCOPE_FORBIDDEN"]
    assert len(forbidden) == 1
    assert forbidden[0]["scope"] == "research_data"
    assert forbidden[0]["severity"] == "blocker"
    assert forbidden[0]["field_path"] == "data.funding.source_revision_id"

    # The same pin under a Research + Backtest scope is eligible -> the blocker clears.
    await _seed_research_revision(session, scope=UsageScope.RESEARCH_BACKTEST)
    cleared = await readiness_cmd.run_readiness_check(session, USER1, composition_id=composition_id)
    assert cleared["state"] == "ready"
    assert not any(i["scope"] == "research_data" for i in cleared["issues"])


async def test_agent_research_only_pin_blocks_run_and_leaves_no_manifest_or_job(session) -> None:
    await _seed_principals(session)
    await _seed_research_revision(session, scope=UsageScope.AGENT_RESEARCH_ONLY)
    composition_id = await _composition_with_funding_strategy(session, USER1)

    with pytest.raises(ReadinessBlockedError) as excinfo:
        await backtest_cmd.request_backtest_run(session, USER1, composition_id=composition_id)
    assert "USAGE_SCOPE_FORBIDDEN" in {detail["code"] for detail in excinfo.value.details}

    # The whole admission transaction rolled back: no run, no manifest, no job.
    await session.rollback()
    assert await _count(session, BacktestRun) == 0
    assert await _count(session, BacktestRunManifest) == 0
    assert await _count(session, Job) == 0


async def test_unapproved_research_pin_blocks_ready_check(session) -> None:
    await _seed_principals(session)
    await _seed_research_revision(session, state=ResearchRevisionState.VERIFIED)
    composition_id = await _composition_with_funding_strategy(session, USER1)

    result = await readiness_cmd.run_readiness_check(session, USER1, composition_id=composition_id)
    assert result["state"] == "not_ready"
    assert any(i["code"] == "LIFECYCLE_BLOCKED" for i in result["issues"])


async def test_missing_available_time_policy_blocks_ready_check(session) -> None:
    await _seed_principals(session)
    await _seed_research_revision(session, available_time_policy=None)
    composition_id = await _composition_with_funding_strategy(session, USER1)

    result = await readiness_cmd.run_readiness_check(session, USER1, composition_id=composition_id)
    assert result["state"] == "not_ready"
    assert any(i["code"] == "TIME_POLICY_INVALID" for i in result["issues"])


async def test_warned_research_revision_is_ready_with_warnings_not_blocked(session) -> None:
    await _seed_principals(session)
    await _seed_research_revision(session, validation_status=ValidationStatus.WARNING)
    composition_id = await _composition_with_funding_strategy(session, USER1)

    result = await readiness_cmd.run_readiness_check(session, USER1, composition_id=composition_id)
    assert result["state"] == "ready_with_warnings"
    assert any(i["code"] == "RESEARCH_COVERAGE_LIMITED" for i in result["issues"])
    # A warning never blocks admission (doc 14 §8.2 Flow B).
    admitted = await backtest_cmd.request_backtest_run(
        session, USER1, composition_id=composition_id
    )
    assert admitted["run_id"]


async def test_funding_disabled_strategy_resolves_no_research_source(session) -> None:
    """The V1 engine consumes exactly one research feed; funding OFF pins none, so the
    Research layer must stay silent rather than inventing a dependency."""
    await _seed_principals(session)
    await _seed_market_revision(session, MarketRevisionState.APPROVED)
    workspace_id = await _empty_composition(session, USER1)
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
    work_object = await mb_cmd.create_work_object(
        session,
        USER1,
        object_kind="strategy",
        payload=_strategy_payload(indicator_revision_id=pkg_rev.revision_id),
    )
    await mb_cmd.attach_mainboard_item(
        session,
        USER1,
        workspace_id=workspace_id,
        root_id=work_object["root_id"],
        revision_id=work_object["revision_id"],
        item_kind="strategy",
    )
    await session.commit()

    result = await readiness_cmd.run_readiness_check(session, USER1, composition_id=workspace_id)
    assert result["state"] == "ready"
    assert not any(i["scope"] == "research_data" for i in result["issues"])
