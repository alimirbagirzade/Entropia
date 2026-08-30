"""GH #703's SECOND door, measured on the READY CHECK plane (backlog R1).

Auto-skips without PostgreSQL (see tests/integration/conftest.py).

ADIM 138 closed the native-asset half of GH #703 and pinned the surviving half --
``instrument_mapping_ref`` is never written by production -- on the WORKER plane
(``queries/funding.py`` -> ``build_funding_schedule`` fails closed). The same predicate,
``time_policy.instrument_mapping_is_valid``, is also read by ``domain/readiness/
validators.py`` as a **BLOCKER** (``INSTRUMENT_MAPPING_INVALID``), and that plane was
never exercised against a revision production can actually create.

Why it stayed invisible is the mirror image of ADIM 138's lesson, in a stronger disguise.
There the fakes did something extra (they set the pointer). Here the seeding helper does
something LESS: ``test_readiness_research_data.py::_seed_research_revision`` inserts the
revision by hand and never sets ``linked_market_dataset_revision_id``, so the pair reads
``has_link == has_ref == False`` -- which the predicate calls COHERENT. Production cannot
produce that shape: ``CreateDatasetRequest.market_entity_id`` is required and
``create_research_dataset`` always writes the link, so every application-created revision
lands on ``True == False`` and is BLOCKED.

These cases assert the DIVERGENCE, not merely the refusal: one drives the real
create -> time-policy -> analysis -> approve pipeline and shows Ready Check reports
NOT_READY; one shows admission is refused and leaves nothing behind; one shows the
hand-seeded shape stays silent on the very same composition, which is what made the gap
survivable. Nothing here fixes the gap -- the writer for ``instrument_mapping_ref`` is a
product decision (backlog R1), left unsigned in
``docs/decisions/closure_i703_instrument_mapping_writer_2026-08-30.md``. That document also
records what a negative control measured here: giving the seeding helper a market link
turns TWO of the sibling suite's cases red, so moving the harness toward the production
shape is itself a decision, not a cleanup.
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
from entropia.infrastructure.postgres.models import BacktestRun, BacktestRunManifest, Job
from entropia.infrastructure.postgres.models.research_data import ResearchDatasetRevision
from entropia.infrastructure.postgres.repositories import packages as pkg_repo
from entropia.shared.errors import ReadinessBlockedError
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
    -- that both halves are what production leaves behind is the claim under test.
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
async def test_an_application_created_research_revision_is_blocked_by_ready_check(
    session,
) -> None:
    revision = await _production_funding_revision(session)

    # Vacuity guard: the two halves the predicate reads are exactly what production left,
    # so "blocked" is a statement about the production shape and not about a hand-set field.
    assert revision.linked_market_dataset_revision_id is not None, (
        "a market link is required at create; without it this case proves nothing"
    )
    assert revision.instrument_mapping_ref is None

    composition_id = await _composition_pinning(
        session,
        USER1,
        source_root_id=revision.entity_id,
        source_revision_id=revision.revision_id,
        source_content_hash=revision.content_hash,
        market_revision_id=revision.linked_market_dataset_revision_id,
    )

    result = await readiness_cmd.run_readiness_check(session, USER1, composition_id=composition_id)
    assert result["state"] == "not_ready"
    assert "INSTRUMENT_MAPPING_INVALID" in _codes(result)


@pytest.mark.asyncio
async def test_the_blocked_revision_is_refused_admission_and_leaves_nothing_behind(
    session,
) -> None:
    """Doc 14 Flow B: a BLOCKER refuses the run and writes no run / manifest / job row.

    Counting rows (not just asserting the raise) is the discriminating half: a guard
    placed AFTER the insert would raise identically while leaving a row behind.

    ``Job`` is measured as a DELTA, not as an absolute zero: the production pipeline that
    builds the revision enqueues its own analysis job, so ``count == 0`` would be false for
    a reason that has nothing to do with admission. The sibling suite could assert zero
    only because it hand-seeds the revision and never runs that pipeline.
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

    jobs_before = await _count(session, Job)
    assert jobs_before > 0, (
        "vacuity guard: the pipeline's own analysis job must exist, else the delta below "
        "would be trivially zero"
    )

    with pytest.raises(ReadinessBlockedError):
        await backtest_cmd.request_backtest_run(session, USER1, composition_id=composition_id)

    assert await _count(session, BacktestRun) == 0
    assert await _count(session, BacktestRunManifest) == 0
    assert await _count(session, Job) == jobs_before


@pytest.mark.asyncio
async def test_the_hand_seeded_revision_shape_never_reaches_the_mapping_gate(
    session,
) -> None:
    """The measurement of the gap: the seeding helper's shape is silent HERE.

    ``_seed_research_revision`` never writes ``linked_market_dataset_revision_id``, so the
    pair is ``False == False`` -- coherent -- and the BLOCKER the production shape earns is
    never raised. Same composition wiring, same predicate, opposite verdict: that is why
    six green Ready Check research cases were consistent with the defect.
    """
    await _seed_readiness_principals(session)
    await _seed_market_revision(session, MarketRevisionState.APPROVED)
    await _seed_research_revision(session)

    seeded = await session.get(ResearchDatasetRevision, "rdrev_ready_1")
    assert seeded is not None
    # The shape production cannot make: no link at all.
    assert seeded.linked_market_dataset_revision_id is None
    assert seeded.instrument_mapping_ref is None

    composition_id = await _composition_pinning(
        session,
        USER1,
        source_root_id="rdent_ready_1",
        source_revision_id="rdrev_ready_1",
        source_content_hash=seeded.content_hash,
        market_revision_id="md_rev_1",
    )

    result = await readiness_cmd.run_readiness_check(session, USER1, composition_id=composition_id)
    assert "INSTRUMENT_MAPPING_INVALID" not in _codes(result), (
        "the seeded shape must stay silent -- that silence is what this case measures"
    )
    assert result["state"] != "not_ready"
