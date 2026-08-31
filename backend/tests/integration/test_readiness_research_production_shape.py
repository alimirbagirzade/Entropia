"""GH #703's SECOND door on the READY CHECK plane -- now the guard for its fix.

Auto-skips without PostgreSQL (see tests/integration/conftest.py).

ADIM 138 closed the native-asset half of GH #703. ADIM 140 measured the surviving
half here: ``instrument_mapping_ref`` had a declaration, two readers and ZERO writers,
so every revision the application created landed on ``has_link=True, has_ref=False`` --
which ``time_policy.instrument_mapping_is_valid`` calls INCOHERENT -- and Ready Check
refused it with ``INSTRUMENT_MAPPING_INVALID`` (``Sev.BLOCKER``). Funding-enabled runs
were therefore unusable with any app-created research revision.

ADIM 149 shipped the writer (``closure_i703_instrument_mapping_writer_2026-08-30.md``,
signed 2026-08-31): §Karar 1 = `(b)` DERIVE FROM THE LINK, §Karar 1a = `(b2)` FAIL
CLOSED FLAT, §Karar 2 = `A` PULL THE HARNESS TO THE PRODUCTION SHAPE.

This file used to assert the DIVERGENCE (production blocked, hand-seeded silent). All
three of those premises are now dead, and they were rewritten deliberately rather than
deleted: the axes they measured are kept and inverted. What was "production is refused"
is now "production is admitted and writes the run" -- the strongest available statement
that the defect blocked usable work and no longer does. What was "the hand-seeded shape
never reaches the gate" is now "the hand-seeded shape no longer diverges from it", which
is the §Karar 2 = `A` cost, made falsifiable instead of merely paid.

The mapping half is asserted against the linked market revision's OWN ``instrument_id``,
read back from the row -- never against a literal. A writer that pinned any constant
would satisfy a literal and fail this.
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
    VisibilityScope,
)
from entropia.domain.market_data.enums import MarketRevisionState
from entropia.domain.package.enums import PackageValidationState
from entropia.domain.research_data.enums import ResearchRevisionState
from entropia.infrastructure.postgres.models import BacktestRun, BacktestRunManifest
from entropia.infrastructure.postgres.models.research_data import ResearchDatasetRevision
from entropia.infrastructure.postgres.repositories import market_data as md_repo
from entropia.infrastructure.postgres.repositories import packages as pkg_repo
from tests.integration.test_readiness_persistence import (
    USER1,
    _empty_composition,
    _seed_market_revision,
    _strategy_payload,
)
from tests.integration.test_readiness_persistence import (
    _seed_principals as _seed_readiness_principals,
)
from tests.integration.test_readiness_research_data import _seed_research_revision
from tests.integration.test_research_native_asset_pointer import (
    _analysed_funding_revision,
    _approve,
)

pytestmark = pytest.mark.integration


async def _production_funding_revision(session) -> Any:
    """A funding research revision built by the REAL commands, then approved.

    Nothing here assigns ``instrument_mapping_ref`` or ``linked_market_dataset_revision_id``
    -- what production leaves behind on both halves is the claim under test.
    """
    entity_id, revision = await _analysed_funding_revision(session)
    approved = await _approve(session, entity_id, revision)
    assert approved.revision_state == ResearchRevisionState.APPROVED
    return approved


async def _composition_pinning(
    session,
    actor,
    *,
    source_root_id: str,
    source_revision_id: str,
    source_content_hash: str,
    market_revision_id: str,
) -> str:
    """A composition whose one strategy enables funding against the named revision.

    The strategy's market pin is set to the SAME market revision the research revision
    links to, so ``DEPENDENCY_BLOCKED`` (the sibling market-compatibility issue) cannot
    fire and the mapping conjunct is the only thing under test.
    """
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
    payload["data"]["market_dataset_revision_id"] = market_revision_id
    payload["data"]["funding"] = {
        "enabled": True,
        "source_root_id": source_root_id,
        "source_revision_id": source_revision_id,
        "source_content_hash": source_content_hash,
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


def _codes(result) -> list[str]:
    return [i["code"] for i in result["issues"]]


@pytest.mark.asyncio
async def test_the_production_shape_carries_a_mapping_copied_from_its_linked_market(
    session,
) -> None:
    """`(b)`: the ref is the linked market revision's own ``instrument_id``, copied.

    Compared against the market row rather than a literal on purpose -- a writer that
    pinned any constant, or resolved some other instrument, passes a literal and fails
    this. The link half is asserted too: a ref without a link is the mirror incoherence.
    """
    revision = await _production_funding_revision(session)

    linked_id = revision.linked_market_dataset_revision_id
    assert linked_id is not None, "a market link is required at create"

    linked_market = await md_repo.get_revision(session, linked_id)
    assert linked_market is not None
    assert linked_market.instrument_id, (
        "vacuity guard: the source instrument must be non-empty, else the equality "
        "below would hold for a writer that copies nothing"
    )
    assert revision.instrument_mapping_ref == linked_market.instrument_id


@pytest.mark.asyncio
async def test_the_production_shape_passes_the_ready_check_mapping_gate(
    session,
) -> None:
    """The inversion of ADIM 140's first case: the BLOCKER no longer fires.

    Narrowed to the mapping code on purpose. Asserting ``state == "ready"`` would make
    this case answer for every other validator too, and a future unrelated blocker would
    then turn it red for a reason that has nothing to do with #703.
    """
    revision = await _production_funding_revision(session)
    composition_id = await _composition_pinning(
        session,
        USER1,
        source_root_id=revision.entity_id,
        source_revision_id=revision.revision_id,
        source_content_hash=revision.content_hash,
        market_revision_id=revision.linked_market_dataset_revision_id,
    )

    result = await readiness_cmd.run_readiness_check(session, USER1, composition_id=composition_id)
    assert "INSTRUMENT_MAPPING_INVALID" not in _codes(result)


@pytest.mark.asyncio
async def test_admission_accepts_the_production_shape_and_writes_the_run(
    session,
) -> None:
    """The strongest statement available: the shape that was refused now does work.

    ADIM 140's sibling counted rows to show a BLOCKER left nothing behind. The same
    counters are the measure of the fix, read the other way: a run row and its manifest
    now exist. Row counts, not the absence of a raise -- an admission that raised after
    inserting would look identical from the outside.
    """
    revision = await _production_funding_revision(session)
    composition_id = await _composition_pinning(
        session,
        USER1,
        source_root_id=revision.entity_id,
        source_revision_id=revision.revision_id,
        source_content_hash=revision.content_hash,
        market_revision_id=revision.linked_market_dataset_revision_id,
    )

    assert await _count(session, BacktestRun) == 0, "vacuity guard: nothing admitted yet"

    await backtest_cmd.request_backtest_run(session, USER1, composition_id=composition_id)

    assert await _count(session, BacktestRun) == 1
    assert await _count(session, BacktestRunManifest) == 1


@pytest.mark.asyncio
async def test_the_hand_seeded_shape_no_longer_diverges_from_production(
    session,
) -> None:
    """§Karar 2 = `A`, made falsifiable.

    ADIM 140 measured the gap here: the seeding helper wrote NEITHER half, the coherence
    rule calls "neither" coherent, and so six green Ready Check research cases were
    consistent with a defect that refused every production revision. The helper now
    writes both halves. This case pins that it does -- if it drifts back to the silent
    shape, the sibling suite would go green again for the wrong reason and only this
    would notice.
    """
    await _seed_readiness_principals(session)
    await _seed_market_revision(session, MarketRevisionState.APPROVED)
    await _seed_research_revision(session)

    seeded = await session.get(ResearchDatasetRevision, "rdrev_ready_1")
    assert seeded is not None
    assert seeded.linked_market_dataset_revision_id == "md_rev_1"

    linked_market = await md_repo.get_revision(session, "md_rev_1")
    assert linked_market is not None
    assert seeded.instrument_mapping_ref == linked_market.instrument_id, (
        "the seed must carry the production shape: ref copied from the linked market row"
    )

    composition_id = await _composition_pinning(
        session,
        USER1,
        source_root_id="rdent_ready_1",
        source_revision_id="rdrev_ready_1",
        source_content_hash=seeded.content_hash,
        market_revision_id="md_rev_1",
    )

    result = await readiness_cmd.run_readiness_check(session, USER1, composition_id=composition_id)
    assert "INSTRUMENT_MAPPING_INVALID" not in _codes(result)
