"""ADIM 46 (#617, #618) + P-E2 — every batched dereference must fail closed exactly
as the per-item read it replaced.

``test_query_budgets.py`` proves these two surfaces stopped costing a round trip per
item; it cannot prove they still say the same thing. Collapsing a loop is where a
fail-closed check quietly becomes a fail-open one: a row that is absent from an
``IN()`` map looks the same as a row nobody asked about, so a careless batch turns
"cannot confirm" into "fine". This file pins the behavior side.

All four repairs share one shape — an id absent from the prefetched map is the same
``None`` the per-id reader returned — so they are guarded here rather than in files
that would drift apart. P-E2 added the last two Ready Check legs (Trading Signal
OHLCV fallback, Research funding); the budget file records their round-trip cost, and
the sections below record what they still SAY. The Root branches are the ones the
rewrite actually touched, and neither leg's own suite reached them: the signal suite
never manufactures a soft-deleted or foreign-typed Root, and ``root_active=False`` was
only ever fed straight into the pure validator.
"""

from __future__ import annotations

from typing import Any

import pytest

from entropia.application.commands.readiness_check import (
    _resolve_market_data_issues,
    _resolve_research_sources,
    _resolve_signal_market_data_issues,
)
from entropia.application.queries.dependency_pins import (
    PIN_UNREADABLE,
    PINNED_REVISION_MISSING,
    PINNED_REVISION_NOT_APPROVED,
    PINNED_REVISION_NOT_PASSED,
    RESOLVER_KEY_NOT_FOUND,
    RESOLVER_NOT_ACTIVE,
    RESOLVER_NOT_TRUSTED_ACTIVE,
    ensure_pinned_resolvers_active,
)
from entropia.domain.esp.enums import ResolverTrustState, RuntimeAdapter
from entropia.domain.lifecycle.enums import (
    ApprovalState,
    DeletionState,
    PackageKind,
    VisibilityScope,
)
from entropia.domain.mainboard.enums import MainboardItemKind
from entropia.domain.market_data.enums import MarketRevisionState
from entropia.domain.package.enums import PackageValidationState
from entropia.domain.readiness.enums import ReadinessIssueCode
from entropia.domain.readiness.issues import ReadinessItemInput
from entropia.infrastructure.postgres.models import (
    EntityRegistry,
    MarketDatasetRevision,
    ResearchDatasetRevision,
)
from entropia.infrastructure.postgres.repositories import esp as esp_repo
from entropia.infrastructure.postgres.repositories import packages as pkg_repo
from entropia.shared.errors import DependencyUnresolved
from tests.integration.test_readiness_query_count import (
    _config,
    _market_revision,
    _research_revision,
)
from tests.integration.test_readiness_signal_market_data import _signal_payload

pytestmark = pytest.mark.integration


# ----------------------------------------------- #617: Ready Check market-data leg


def _strategy_item(item_id: str, revision_id: str) -> ReadinessItemInput:
    return ReadinessItemInput(
        item_id=item_id,
        kind=MainboardItemKind.STRATEGY,
        root_id=f"root_{item_id}",
        revision_id=f"rev_{item_id}",
        available=True,
        payload={"data": {"market_dataset_revision_id": revision_id}},
    )


async def _approved(session, revision_id: str) -> MarketDatasetRevision:
    """Move a seeded DRAFT revision to the one state that clears the blocker."""
    revision = await session.get(MarketDatasetRevision, revision_id)
    assert revision is not None
    revision.revision_state = MarketRevisionState.APPROVED
    await session.flush()
    return revision


async def test_an_approved_revision_on_an_active_root_clears_the_blocker(session) -> None:
    """The positive path. Without this the batch could return nothing at all and every
    fail-closed assertion below would still pass."""
    revision_id = await _market_revision(session)
    await _approved(session, revision_id)
    await session.commit()

    issues = await _resolve_market_data_issues(session, [_strategy_item("i0", revision_id)])

    assert issues == []


async def test_a_root_that_is_not_a_market_dataset_still_blocks(session) -> None:
    """``get_dataset_root`` returned ``None`` for a foreign entity_type; the batch
    applies that guard in SQL, so such a Root is ABSENT from the map — not approved."""
    revision_id = await _market_revision(session)
    revision = await _approved(session, revision_id)
    root = await session.get(EntityRegistry, revision.entity_id)
    assert root is not None
    root.entity_type = "research_dataset"
    await session.flush()
    await session.commit()

    issues = await _resolve_market_data_issues(session, [_strategy_item("i0", revision_id)])

    assert [issue.code for issue in issues] == [ReadinessIssueCode.MARKET_DATASET_NOT_APPROVED]
    assert issues[0].scope_id == "i0"


async def test_a_soft_deleted_root_still_blocks(session) -> None:
    """The root must still be ACTIVE (doc 14 §9.2/§11) — the batch reads the same column."""
    revision_id = await _market_revision(session)
    revision = await _approved(session, revision_id)
    root = await session.get(EntityRegistry, revision.entity_id)
    assert root is not None
    root.deletion_state = DeletionState.SOFT_DELETED
    await session.flush()
    await session.commit()

    issues = await _resolve_market_data_issues(session, [_strategy_item("i0", revision_id)])

    assert [issue.code for issue in issues] == [ReadinessIssueCode.MARKET_DATASET_NOT_APPROVED]


async def test_an_unpinned_item_still_blocks_and_drags_no_root_into_the_batch(session) -> None:
    """A blank pin matches no revision, so it reaches the root batch as nothing at all."""
    issues = await _resolve_market_data_issues(session, [_strategy_item("i0", "")])

    assert [issue.code for issue in issues] == [ReadinessIssueCode.MARKET_DATASET_NOT_APPROVED]
    assert issues[0].field_path == "data.market_dataset_revision_id"


async def test_only_the_defective_items_block_and_they_keep_item_order(session) -> None:
    """The batch must stay selective: one bad pin among good ones blocks itself only,
    and the issue list still follows the ITEM order, not the map's."""
    good_a = await _market_revision(session)
    bad = await _market_revision(session)  # left DRAFT
    good_b = await _market_revision(session)
    await _approved(session, good_a)
    await _approved(session, good_b)
    await session.commit()

    items = [
        _strategy_item("i0", good_a),
        _strategy_item("i1", bad),
        _strategy_item("i2", good_b),
        _strategy_item("i3", "missing_rev"),
    ]
    issues = await _resolve_market_data_issues(session, items)

    assert [issue.scope_id for issue in issues] == ["i1", "i3"]


async def test_two_items_sharing_one_pin_both_resolve(session) -> None:
    """Duplicate ids collapse in the batch; both items must still see the same answer."""
    revision_id = await _market_revision(session)
    await _approved(session, revision_id)
    await session.commit()

    issues = await _resolve_market_data_issues(
        session, [_strategy_item("i0", revision_id), _strategy_item("i1", revision_id)]
    )

    assert issues == []


# --------------------------------------- #618: Approve-Package pinned-resolver refs


async def _resolver(
    session,
    key: str,
    *,
    trust_state: ResolverTrustState = ResolverTrustState.TRUSTED_ACTIVE,
    validation_state: PackageValidationState = PackageValidationState.PASSED,
    approval_state: ApprovalState = ApprovalState.APPROVED,
) -> str:
    """Register one canonical key backed by a revision in the given evidence state."""
    root, _detail, revision = await pkg_repo.create_package(
        session,
        owner_principal_id=None,
        created_by_principal_id=None,
        package_kind=PackageKind.EMBEDDED_SYSTEM,
        input_contract={"source": "close"},
        output_contract={"kind": "directional_signal"},
        dependency_snapshot={"resolved": []},
        visibility_scope=VisibilityScope.SYSTEM,
        validation_state=validation_state,
        approval_state=approval_state,
    )
    await session.flush()
    esp_repo.upsert_registry_entry(
        session,
        canonical_key=key,
        package_entity_id=root.entity_id,
        runtime_adapter=RuntimeAdapter.PYTHON,
        trust_state=trust_state,
        trusted_active_revision_id=revision.revision_id,
    )
    await session.flush()
    return revision.revision_id


async def _defects(session, refs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The ``details`` the envelope would carry, or ``[]`` when nothing is rejected."""
    try:
        await ensure_pinned_resolvers_active(
            session, dependency_snapshot={"resolved": refs}, scope_id="pkg_under_test"
        )
    except DependencyUnresolved as error:
        return list(error.details or [])
    return []


async def test_a_fully_active_pin_set_is_accepted(session) -> None:
    """The positive path — otherwise every vocabulary assertion below is vacuous."""
    revision_id = await _resolver(session, "ta.ok")
    await session.commit()

    assert (
        await _defects(session, [{"canonical_key": "ta.ok", "embedded_revision_id": revision_id}])
        == []
    )


async def test_every_defect_term_survives_the_batch(session) -> None:
    """Each term in the per-pin vocabulary is still produced for the same input.

    One snapshot carrying all of them at once also pins the second property the issue
    named: ``details`` follows the REF order of the snapshot, not the map's iteration
    order or the order the batch happened to fetch rows in.
    """
    deprecated = await _resolver(session, "ta.dep", trust_state=ResolverTrustState.DEPRECATED)
    unavailable = await _resolver(session, "ta.unavail", trust_state=ResolverTrustState.UNAVAILABLE)
    candidate = await _resolver(session, "ta.cand", trust_state=ResolverTrustState.CANDIDATE)
    not_passed = await _resolver(
        session, "ta.unvalidated", validation_state=PackageValidationState.FAILED
    )
    not_approved = await _resolver(session, "ta.unapproved", approval_state=ApprovalState.DRAFT)
    await _resolver(session, "ta.gone")
    await session.commit()

    refs = [
        {"embedded_revision_id": "rev_x"},  # names no key at all
        {"canonical_key": "ta.absent", "embedded_revision_id": "rev_x"},
        {"canonical_key": "ta.dep", "embedded_revision_id": deprecated},
        {"canonical_key": "ta.unavail", "embedded_revision_id": unavailable},
        {"canonical_key": "ta.cand", "embedded_revision_id": candidate},
        {"canonical_key": "ta.gone", "embedded_revision_id": "rev_never_written"},
        {"canonical_key": "ta.unvalidated", "embedded_revision_id": not_passed},
        {"canonical_key": "ta.unapproved", "embedded_revision_id": not_approved},
    ]

    assert [defect["issue"] for defect in await _defects(session, refs)] == [
        PIN_UNREADABLE,
        RESOLVER_KEY_NOT_FOUND,
        RESOLVER_NOT_ACTIVE,
        RESOLVER_NOT_ACTIVE,
        RESOLVER_NOT_TRUSTED_ACTIVE,
        PINNED_REVISION_MISSING,
        PINNED_REVISION_NOT_PASSED,
        PINNED_REVISION_NOT_APPROVED,
    ]


async def test_a_ref_naming_no_revision_falls_back_to_the_trusted_active_one(session) -> None:
    """The fallback branch is why the revision batch is built AFTER the registry batch:
    this ref's revision id is only knowable from its registry entry."""
    await _resolver(session, "ta.fallback")
    await session.commit()

    assert await _defects(session, [{"canonical_key": "ta.fallback"}]) == []


async def test_the_fallback_still_re_reads_the_evidence_it_lands_on(session) -> None:
    """Falling back must not wave the pin through — the resolved revision is checked."""
    await _resolver(session, "ta.fallback_bad", approval_state=ApprovalState.DRAFT)
    await session.commit()

    defects = await _defects(session, [{"canonical_key": "ta.fallback_bad"}])

    assert [defect["issue"] for defect in defects] == [PINNED_REVISION_NOT_APPROVED]


async def test_the_call_spelling_is_read_like_canonical_key(session) -> None:
    """Pre-Check writes some refs under ``call``; the batch must key on both."""
    revision_id = await _resolver(session, "ta.called")
    await session.commit()

    assert (
        await _defects(session, [{"call": "ta.called", "embedded_revision_id": revision_id}]) == []
    )


async def test_one_bad_pin_among_good_ones_is_reported_alone(session) -> None:
    """The batch stays selective, and the envelope still names the offending key."""
    good = await _resolver(session, "ta.good")
    await session.commit()

    defects = await _defects(
        session,
        [
            {"canonical_key": "ta.good", "embedded_revision_id": good},
            {"canonical_key": "ta.missing", "embedded_revision_id": "rev_x"},
        ],
    )

    assert [(defect["canonical_key"], defect["issue"]) for defect in defects] == [
        ("ta.missing", RESOLVER_KEY_NOT_FOUND)
    ]


async def test_an_empty_snapshot_is_accepted_without_touching_the_database(session) -> None:
    """Both batches short-circuit on empty input — a description-route draft pins none."""
    assert await _defects(session, []) == []


# ------------------------------ P-E2: Ready Check Trading Signal OHLCV-fallback leg


def _signal_item(item_id: str, revision_id: str) -> ReadinessItemInput:
    """One Trading Signal whose price fallback pins ``revision_id`` (doc 04 §5)."""
    return ReadinessItemInput(
        item_id=item_id,
        kind=MainboardItemKind.TRADING_SIGNAL,
        root_id=f"root_{item_id}",
        revision_id=f"rev_{item_id}",
        available=True,
        payload=_signal_payload(
            f"srcast_{item_id}",
            f"nsr_{item_id}",
            {
                "source": "ohlcv_close_if_needed",
                "approved_market_data_revision_ref": revision_id,
            },
        ),
    )


async def test_signal_leg_an_approved_pin_on_an_active_root_clears_the_blocker(session) -> None:
    """The positive path. Without it the batch could return nothing at all and every
    fail-closed assertion below would still pass."""
    revision_id = await _market_revision(session)
    await _approved(session, revision_id)
    await session.commit()

    assert (
        await _resolve_signal_market_data_issues(session, [_signal_item("i0", revision_id)]) == []
    )


async def test_signal_leg_a_root_that_is_not_a_market_dataset_still_blocks(session) -> None:
    """``get_dataset_root`` returned ``None`` for a foreign entity_type; the batch applies
    that guard in SQL, so such a Root is ABSENT from the map — never 'approved'."""
    revision_id = await _market_revision(session)
    revision = await _approved(session, revision_id)
    root = await session.get(EntityRegistry, revision.entity_id)
    assert root is not None
    root.entity_type = "research_dataset"
    await session.flush()
    await session.commit()

    issues = await _resolve_signal_market_data_issues(session, [_signal_item("i0", revision_id)])

    assert [issue.code for issue in issues] == [ReadinessIssueCode.MARKET_DATA_DEPENDENCY_BLOCKED]
    assert issues[0].scope_id == "i0"
    assert issues[0].field_path == "price_policy.approved_market_data_revision_ref"


async def test_signal_leg_a_soft_deleted_root_still_blocks(session) -> None:
    """The Root must still be ACTIVE — the batch reads the same column the per-id read did."""
    revision_id = await _market_revision(session)
    revision = await _approved(session, revision_id)
    root = await session.get(EntityRegistry, revision.entity_id)
    assert root is not None
    root.deletion_state = DeletionState.SOFT_DELETED
    await session.flush()
    await session.commit()

    issues = await _resolve_signal_market_data_issues(session, [_signal_item("i0", revision_id)])

    assert [issue.code for issue in issues] == [ReadinessIssueCode.MARKET_DATA_DEPENDENCY_BLOCKED]


async def test_signal_leg_only_defective_items_block_and_they_keep_item_order(session) -> None:
    """The batch stays selective, and the issue list follows the ITEM order — not the
    map's iteration order, and not the order the batch happened to fetch rows in."""
    good_a = await _market_revision(session)
    bad = await _market_revision(session)  # left DRAFT
    good_b = await _market_revision(session)
    await _approved(session, good_a)
    await _approved(session, good_b)
    await session.commit()

    issues = await _resolve_signal_market_data_issues(
        session,
        [
            _signal_item("i0", good_a),
            _signal_item("i1", bad),
            _signal_item("i2", good_b),
            _signal_item("i3", "missing_rev"),
        ],
    )

    assert [issue.scope_id for issue in issues] == ["i1", "i3"]


async def test_signal_leg_two_items_sharing_one_pin_both_resolve(session) -> None:
    """Duplicate ids collapse twice over (revision batch, then Root batch); both items
    must still see the same answer."""
    revision_id = await _market_revision(session)
    await _approved(session, revision_id)
    await session.commit()

    issues = await _resolve_signal_market_data_issues(
        session, [_signal_item("i0", revision_id), _signal_item("i1", revision_id)]
    )

    assert issues == []


# ------------------------------------- P-E2: Ready Check Research funding leg (O-01)


def _funded_item(item_id: str, revision_id: str) -> ReadinessItemInput:
    """One Strategy whose funding source pins ``revision_id`` (doc 12 §9.2)."""
    return ReadinessItemInput(
        item_id=item_id,
        kind=MainboardItemKind.STRATEGY,
        root_id=f"root_{item_id}",
        revision_id=f"rev_{item_id}",
        available=True,
        payload=_config(
            indicator_rev="pkg_x",
            condition_rev="pkg_y",
            reference_rev="pkg_z",
            leg_revs=[],
            market_rev="md_rev_equiv",
            funding_revision_id=revision_id,
        ).model_dump(mode="json"),
    )


async def test_research_leg_a_resolved_pin_on_an_active_root_reports_it_active(session) -> None:
    """The positive path — otherwise every ``root_active is False`` assertion is vacuous."""
    revision_id = await _research_revision(session)
    await session.commit()

    sources = await _resolve_research_sources(session, [_funded_item("i0", revision_id)])

    assert [(s.found, s.root_active) for s in sources] == [(True, True)]


async def test_research_leg_a_root_that_is_not_a_research_dataset_is_not_active(session) -> None:
    """The research batch applies its OWN ``entity_type`` guard in SQL. A Root retyped to
    a market dataset is ABSENT from the map — exactly the ``None`` the per-id reader
    returned — so the feed is still reported as un-backed rather than silently active."""
    revision_id = await _research_revision(session)
    revision = await session.get(ResearchDatasetRevision, revision_id)
    assert revision is not None
    root = await session.get(EntityRegistry, revision.entity_id)
    assert root is not None
    root.entity_type = "market_dataset"
    await session.flush()
    await session.commit()

    sources = await _resolve_research_sources(session, [_funded_item("i0", revision_id)])

    assert [(s.found, s.root_active) for s in sources] == [(True, False)]


async def test_research_leg_a_soft_deleted_root_is_not_active(session) -> None:
    """``root_active`` reads the same column it always did."""
    revision_id = await _research_revision(session)
    revision = await session.get(ResearchDatasetRevision, revision_id)
    assert revision is not None
    root = await session.get(EntityRegistry, revision.entity_id)
    assert root is not None
    root.deletion_state = DeletionState.SOFT_DELETED
    await session.flush()
    await session.commit()

    sources = await _resolve_research_sources(session, [_funded_item("i0", revision_id)])

    assert [(s.found, s.root_active) for s in sources] == [(True, False)]


async def test_research_leg_an_unresolvable_pin_still_reports_not_found(session) -> None:
    """A pin matching no row never reaches the Root branch at all — it must short-circuit
    to ``found=False`` with its field path intact, not to 'found with an inactive root'."""
    sources = await _resolve_research_sources(session, [_funded_item("i0", "rd_rev_missing")])

    assert [(s.found, s.root_active) for s in sources] == [(False, False)]
    assert sources[0].field_path == "data.funding.source_revision_id"


async def test_research_leg_mixed_items_keep_item_order(session) -> None:
    """One unresolvable feed among good ones resolves itself only, and the states still
    follow the ITEM order."""
    good_a = await _research_revision(session)
    good_b = await _research_revision(session)
    await session.commit()

    sources = await _resolve_research_sources(
        session,
        [
            _funded_item("i0", good_a),
            _funded_item("i1", "rd_rev_missing"),
            _funded_item("i2", good_b),
        ],
    )

    assert [(s.item_id, s.found) for s in sources] == [
        ("i0", True),
        ("i1", False),
        ("i2", True),
    ]


async def test_research_leg_two_items_sharing_one_pin_both_resolve(session) -> None:
    """Duplicate ids collapse in both batches; both items must still see the same Root."""
    revision_id = await _research_revision(session)
    await session.commit()

    sources = await _resolve_research_sources(
        session, [_funded_item("i0", revision_id), _funded_item("i1", revision_id)]
    )

    assert [(s.found, s.root_active) for s in sources] == [(True, True), (True, True)]
