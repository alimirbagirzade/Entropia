"""Agent bundle vs Backtest bundle — point-in-time parity (doc 12 §9.1, §9.2, §9.3, §11).

ADIM 13. The charter question: does a Research Data revision carry the SAME canonical
point-in-time truth into an Agent research bundle as it does into a Backtest execution
bundle? These tests answer it against a real database, on the four surfaces that can
pin a research revision:

    A1  ``jobs/agent_tools._handle_data_bundle_resolve``  (the UI-less Agent tool)
    A2  ``jobs/research_data.compile_agent_data_bundle``  (POST /bundles/agent)
    B1  ``jobs/research_data.compile_backtest_evidence_bundle`` (POST /bundles/backtest-evidence)
    B2  ``commands/backtest_run_context._research_entries``     (the Run manifest)

Where the four agree, a passing test locks the agreement. Where they DISAGREE, the
test states the CANONICAL expectation and is marked ``xfail(strict=True)`` with the
issue that owns the decision — never softened into an assertion of the defect, and
never "fixed" here: the ADIM 13 charter permits a narrow fix only in the shared
time-policy layer (which is where ``ensure_time_policy_mutable`` landed).

Companion pure-layer proofs: ``tests/unit/test_research_point_in_time.py``.
Evidence matrix: ``docs/audit/research_point_in_time_matrix.md``.
"""

from __future__ import annotations

import pytest

from entropia.application.commands import backtest_run_context as run_ctx
from entropia.application.commands import market_data as md_cmd
from entropia.application.commands import research_data as rd_cmd
from entropia.application.jobs import agent_tools
from entropia.application.jobs import research_data as rd_jobs
from entropia.domain.agent_lab.enums import ALPHA_AGENT_ID, RuntimeMode, RuntimeStatus
from entropia.domain.identity import Actor
from entropia.domain.lifecycle.enums import DeletionState, PrincipalType, Role
from entropia.domain.market_data.enums import MarketDataType, MarketRevisionState
from entropia.domain.research_data.enums import (
    AvailableTimePolicy,
    EventTimeSemantics,
    ResearchCategory,
    ResearchRevisionState,
    ResearchTimezoneMode,
    UsageScope,
)
from entropia.domain.research_data.value_objects import (
    AvailableTimeSpec,
    CategorySpec,
    ResearchTimezoneSpec,
)
from entropia.domain.strategy.config import FundingPolicy
from entropia.infrastructure.postgres.models import (
    AgentRuntime,
    Principal,
    ResearchDatasetRevision,
)
from entropia.infrastructure.postgres.repositories import market_data as md_repo
from entropia.infrastructure.postgres.repositories import research_data as rd_repo
from entropia.shared.errors import (
    FieldMeaningInsufficient,
    LifecycleBlocked,
    NotFoundError,
    TimePolicyInvalid,
    UsageScopeForbidden,
)

pytestmark = pytest.mark.integration

ADMIN = Actor(principal_id="user_admin", principal_type=PrincipalType.HUMAN, role=Role.ADMIN)
OWNER = Actor(principal_id="user_1", principal_type=PrincipalType.HUMAN, role=Role.SUPERVISOR)
AGENT = Actor(
    principal_id="agent_alpha",
    principal_type=PrincipalType.AGENT,
    role=None,
    correlation_id="corr_adim13",
)

OPEN_INTEREST = CategorySpec(category=ResearchCategory.OPEN_INTEREST)
UTC_TZ = ResearchTimezoneSpec(mode=ResearchTimezoneMode.UTC)
FIXED_DELAY_2M = AvailableTimeSpec(policy=AvailableTimePolicy.FIXED_DELAY, delay_seconds=120)
FIXED_DELAY_2H = AvailableTimeSpec(policy=AvailableTimePolicy.FIXED_DELAY, delay_seconds=7200)


# --------------------------------------------------------------------------- #
# Fixtures                                                                      #
# --------------------------------------------------------------------------- #


async def _seed(session) -> None:
    for pid, kind in (
        ("user_admin", PrincipalType.HUMAN),
        ("user_1", PrincipalType.HUMAN),
        ("agent_alpha", PrincipalType.AGENT),
    ):
        if await session.get(Principal, pid) is None:
            session.add(Principal(principal_id=pid, principal_type=kind))
    session.add(
        AgentRuntime(
            agent_id=ALPHA_AGENT_ID,
            mode=RuntimeMode.CONTINUOUS,
            status=RuntimeStatus.ACTIVE,
            row_version=1,
        )
    )
    await session.flush()


async def _approved_market(session) -> str:
    root, _ = await md_cmd.create_market_dataset(
        session, ADMIN, market_data_type=MarketDataType.OHLCV, payload={"v": 1}
    )
    await session.flush()
    revision = await md_repo.get_revision(session, root.current_revision_id or "")
    assert revision is not None
    revision.revision_state = MarketRevisionState.VERIFIED
    await session.flush()
    await md_cmd.approve_market_dataset_revision(
        session, ADMIN, entity_id=root.entity_id, revision_id=revision.revision_id
    )
    await session.flush()
    return root.entity_id


async def _head(session, entity_id: str) -> ResearchDatasetRevision:
    root = await rd_repo.get_dataset_root(session, entity_id)
    assert root is not None
    revision = await rd_repo.get_revision(session, root.current_revision_id or "")
    assert revision is not None
    return revision


async def _research(
    session,
    market_id: str,
    scope: UsageScope,
    *,
    payload: dict | None = None,
    approve: bool = True,
    delay_seconds: int = 120,
) -> tuple[str, ResearchDatasetRevision]:
    """A research dataset whose head revision carries a valid fixed-delay policy."""
    root, _ = await rd_cmd.create_research_dataset(
        session,
        OWNER,
        market_entity_id=market_id,
        payload=payload or {"f": 1},
        category=OPEN_INTEREST,
        usage_scope=scope,
    )
    await session.flush()
    revision = await _head(session, root.entity_id)
    revision.event_time_semantics = EventTimeSemantics.PROVIDER_EVENT_TIMESTAMP
    revision.available_time_policy = AvailableTimePolicy.FIXED_DELAY
    revision.available_delay_seconds = delay_seconds
    revision.revision_state = ResearchRevisionState.VERIFIED
    await session.flush()
    if approve:
        await rd_cmd.approve_research_dataset_revision(
            session, ADMIN, entity_id=root.entity_id, revision_id=revision.revision_id
        )
        await session.flush()
    return root.entity_id, revision


async def _gateway_bundle(session, revision_id: str, *, scope: str, **spec) -> dict:
    return await agent_tools.dispatch_tool_call(
        session,
        AGENT,
        tool_name="data_bundle.resolve",
        policy_scope=scope,
        request={"research_revisions": [{"revision_id": revision_id, **spec}]},
    )


# --------------------------------------------------------------------------- #
# P — the four surfaces pin the SAME revision identity                          #
# --------------------------------------------------------------------------- #


async def test_every_bundle_surface_pins_the_same_exact_revision_identity(session) -> None:
    # doc 12 §9.1: "Agent Data Bundle exact revision IDs ... pins. 'Latest approved'
    # dynamic resolution forbidden." §9.2 says the same for the evidence bundle.
    # A later approved revision under the SAME root must move none of them.
    await _seed(session)
    market_id = await _approved_market(session)
    entity_id, v1 = await _research(session, market_id, UsageScope.RESEARCH_BACKTEST)
    await session.commit()

    agent_bundle = await rd_jobs.compile_agent_data_bundle(
        session, ADMIN, research_revision_ids=[v1.revision_id]
    )
    evidence = await rd_jobs.compile_backtest_evidence_bundle(
        session, ADMIN, research_revision_ids=[v1.revision_id]
    )
    gateway = await _gateway_bundle(session, v1.revision_id, scope="research")

    assert agent_bundle["members"][0]["research_revision_id"] == v1.revision_id
    assert evidence["members"][0]["research_revision_id"] == v1.revision_id
    assert gateway["research_revision_ids"] == [v1.revision_id]
    # Identity is the revision id AND its content hash — the two halves of the pin.
    assert (
        agent_bundle["members"][0]["research_content_hash"]
        == evidence["members"][0]["research_content_hash"]
        == v1.content_hash
    )
    # The head advances; the compiled bundles do not follow it.
    await rd_cmd.create_research_dataset_revision(
        session,
        OWNER,
        entity_id=entity_id,
        payload={"f": 2},
        category=OPEN_INTEREST,
        usage_scope=UsageScope.RESEARCH_BACKTEST,
        timezone_spec=UTC_TZ,
    )
    await session.commit()
    v2 = await _head(session, entity_id)
    assert v2.revision_id != v1.revision_id
    recompiled = await rd_jobs.compile_agent_data_bundle(
        session, ADMIN, research_revision_ids=[v1.revision_id]
    )
    assert recompiled["members"][0]["research_revision_id"] == v1.revision_id
    assert recompiled["bundle_hash"] == agent_bundle["bundle_hash"]


async def test_the_run_manifest_pins_the_same_revision_identity_as_the_evidence_bundle(
    session,
) -> None:
    # B1 vs B2: the evidence bundle and the Run manifest are compiled by different
    # code, so they must be shown to agree on WHICH revision and WHICH bytes.
    await _seed(session)
    market_id = await _approved_market(session)
    entity_id, revision = await _research(session, market_id, UsageScope.RESEARCH_BACKTEST)
    await session.commit()

    evidence = await rd_jobs.compile_backtest_evidence_bundle(
        session, ADMIN, research_revision_ids=[revision.revision_id]
    )
    entries = await run_ctx._research_entries(
        session,
        FundingPolicy(
            enabled=True,
            source_root_id=entity_id,
            source_revision_id=revision.revision_id,
            source_content_hash=revision.content_hash,
        ),
    )

    member = evidence["members"][0]
    pinned = entries[0]
    assert pinned["revision_id"] == member["research_revision_id"] == revision.revision_id
    assert pinned["pinned_content_hash"] == member["research_content_hash"]
    assert pinned["revision"]["content_hash"] == member["research_content_hash"]
    assert pinned["revision"]["usage_scope"] == member["usage_scope"]


async def test_funding_disabled_pins_no_research_feed_at_all(session) -> None:
    # The V1 engine consumes exactly one research feed; with funding off there is
    # nothing to pin, and an empty list is not the same as an unresolved pin.
    await _seed(session)
    assert await run_ctx._research_entries(session, FundingPolicy(enabled=False)) == []


# --------------------------------------------------------------------------- #
# S — usage scope decides consumption, identically on both sides                #
# --------------------------------------------------------------------------- #


async def test_agent_research_only_is_allowed_for_research_and_forbidden_for_execution(
    session,
) -> None:
    # doc 12 §9.3 row 2 — the defining asymmetry between the two bundles.
    await _seed(session)
    market_id = await _approved_market(session)
    _, revision = await _research(session, market_id, UsageScope.AGENT_RESEARCH_ONLY)
    await session.commit()

    agent_bundle = await rd_jobs.compile_agent_data_bundle(
        session, ADMIN, research_revision_ids=[revision.revision_id]
    )
    assert agent_bundle["members"][0]["usage_scope"] == UsageScope.AGENT_RESEARCH_ONLY.value

    with pytest.raises(UsageScopeForbidden):
        await rd_jobs.compile_backtest_evidence_bundle(
            session, ADMIN, research_revision_ids=[revision.revision_id]
        )

    research_call = await _gateway_bundle(session, revision.revision_id, scope="research")
    assert research_call["status"] == "succeeded"
    execution_call = await _gateway_bundle(session, revision.revision_id, scope="execution")
    assert execution_call["status"] == "rejected"
    assert execution_call["reason_code"] == "RESEARCH_INPUT_BLOCKED"


async def test_feature_input_only_without_an_approved_definition_is_blocked(session) -> None:
    # doc 12 §9.3 row 3: "Only via approved feature definition and eligible revision."
    await _seed(session)
    market_id = await _approved_market(session)
    _, revision = await _research(session, market_id, UsageScope.FEATURE_INPUT_ONLY)
    await session.commit()

    with pytest.raises(FieldMeaningInsufficient):
        await rd_jobs.compile_backtest_evidence_bundle(
            session, ADMIN, research_revision_ids=[revision.revision_id]
        )
    # Agent research is still allowed for the same revision (§9.3 row 3, column 1).
    agent_bundle = await rd_jobs.compile_agent_data_bundle(
        session, ADMIN, research_revision_ids=[revision.revision_id]
    )
    assert agent_bundle["members"][0]["research_revision_id"] == revision.revision_id


async def test_feature_input_only_with_an_approved_definition_enters_the_evidence_bundle(
    session,
) -> None:
    # The POSITIVE half of §9.3 row 3 — the required path actually opens the gate,
    # so the rule is a routing requirement rather than a permanent prohibition.
    await _seed(session)
    market_id = await _approved_market(session)
    entity_id, revision = await _research(session, market_id, UsageScope.FEATURE_INPUT_ONLY)
    await session.commit()
    await rd_cmd.define_feature(
        session,
        OWNER,
        entity_id=entity_id,
        feature_name="oi_zscore",
        definition={"window": 30},
        feature_version=1,
        approval_state="approved",
    )
    await session.commit()

    evidence = await rd_jobs.compile_backtest_evidence_bundle(
        session, ADMIN, research_revision_ids=[revision.revision_id]
    )
    assert evidence["members"][0]["research_revision_id"] == revision.revision_id
    assert evidence["members"][0]["usage_scope"] == UsageScope.FEATURE_INPUT_ONLY.value


# --------------------------------------------------------------------------- #
# L — lifecycle: a revision that may no longer be selected                       #
# --------------------------------------------------------------------------- #


async def test_a_soft_deleted_root_is_blocked_from_both_bundle_compilers(session) -> None:
    # doc 12 §11 + §14: a soft-deleted root leaves the active registry and new
    # selection/bundle use is blocked; historical manifests stay readable.
    await _seed(session)
    market_id = await _approved_market(session)
    entity_id, revision = await _research(session, market_id, UsageScope.RESEARCH_BACKTEST)
    await session.commit()
    root = await rd_repo.get_dataset_root(session, entity_id)
    assert root is not None
    root.deletion_state = DeletionState.SOFT_DELETED
    await session.commit()

    with pytest.raises(NotFoundError):
        await rd_jobs.compile_agent_data_bundle(
            session, ADMIN, research_revision_ids=[revision.revision_id]
        )
    with pytest.raises(NotFoundError):
        await rd_jobs.compile_backtest_evidence_bundle(
            session, ADMIN, research_revision_ids=[revision.revision_id]
        )


@pytest.mark.parametrize(
    "state",
    [ResearchRevisionState.DEPRECATED, ResearchRevisionState.APPROVAL_REVOKED],
)
async def test_a_non_consumable_revision_is_blocked_from_both_bundle_compilers(
    session, state: ResearchRevisionState
) -> None:
    await _seed(session)
    market_id = await _approved_market(session)
    _, revision = await _research(session, market_id, UsageScope.RESEARCH_BACKTEST)
    revision.revision_state = state
    await session.commit()

    with pytest.raises(NotFoundError):
        await rd_jobs.compile_agent_data_bundle(
            session, ADMIN, research_revision_ids=[revision.revision_id]
        )
    with pytest.raises(NotFoundError):
        await rd_jobs.compile_backtest_evidence_bundle(
            session, ADMIN, research_revision_ids=[revision.revision_id]
        )


# --------------------------------------------------------------------------- #
# T — the time policy a bundle was compiled under cannot be rewritten           #
# --------------------------------------------------------------------------- #


async def test_an_approved_revision_cannot_be_retimed_in_place(session) -> None:
    # ADIM 13 fix. Before it, ``set_time_policy`` rewrote an APPROVED revision's
    # available-time rule while its ``content_hash`` (payload bytes only) stayed
    # identical — and ``queries/funding.py`` re-reads these fields LIVE at run time,
    # so an already-finished Run would replay under a rule it never used.
    await _seed(session)
    market_id = await _approved_market(session)
    entity_id, revision = await _research(session, market_id, UsageScope.RESEARCH_BACKTEST)
    await session.commit()
    assert revision.revision_state is ResearchRevisionState.APPROVED

    with pytest.raises(LifecycleBlocked) as excinfo:
        await rd_cmd.set_time_policy(
            session,
            ADMIN,
            entity_id=entity_id,
            event_time_semantics=EventTimeSemantics.PROVIDER_EVENT_TIMESTAMP,
            available_time=FIXED_DELAY_2H,
            timezone_spec=UTC_TZ,
        )
    assert excinfo.value.code == "LIFECYCLE_BLOCKED"
    assert excinfo.value.field_path == "available_time_policy"
    assert excinfo.value.scope_id == revision.revision_id
    # The gate fires BEFORE any write, so the revision the runs pinned is untouched
    # (the command never reached ``rd_repo.set_time_policy``).
    assert revision.available_delay_seconds == 120
    assert revision.available_time_policy is AvailableTimePolicy.FIXED_DELAY


async def test_the_canonical_recovery_is_a_new_revision_that_leaves_v1_intact(
    session,
) -> None:
    # doc 12 §14 "Revision immutability": v1.0 is not mutated; a v1.1 draft carries
    # the new rule, and anything already pinned to v1.0 keeps v1.0's rule.
    await _seed(session)
    market_id = await _approved_market(session)
    entity_id, v1 = await _research(session, market_id, UsageScope.RESEARCH_BACKTEST)
    await session.commit()
    evidence_v1 = await rd_jobs.compile_backtest_evidence_bundle(
        session, ADMIN, research_revision_ids=[v1.revision_id]
    )

    await rd_cmd.create_research_dataset_revision(
        session,
        OWNER,
        entity_id=entity_id,
        payload={"f": 2},
        category=OPEN_INTEREST,
        usage_scope=UsageScope.RESEARCH_BACKTEST,
        timezone_spec=UTC_TZ,
    )
    await session.commit()
    await rd_cmd.set_time_policy(
        session,
        ADMIN,
        entity_id=entity_id,
        event_time_semantics=EventTimeSemantics.PROVIDER_EVENT_TIMESTAMP,
        available_time=FIXED_DELAY_2H,
        timezone_spec=UTC_TZ,
    )
    await session.commit()

    v2 = await _head(session, entity_id)
    assert v2.available_delay_seconds == 7200
    v1_reloaded = await rd_repo.get_revision(session, v1.revision_id)
    assert v1_reloaded is not None
    assert v1_reloaded.available_delay_seconds == 120
    assert v1_reloaded.available_time_policy is AvailableTimePolicy.FIXED_DELAY

    # The historical bundle recompiles byte-identically: a correction downstream of
    # it changed nothing it had pinned.
    recompiled = await rd_jobs.compile_backtest_evidence_bundle(
        session, ADMIN, research_revision_ids=[v1.revision_id]
    )
    assert recompiled["bundle_hash"] == evidence_v1["bundle_hash"]
    assert recompiled["members"] == evidence_v1["members"]


async def test_a_pre_approval_revision_may_still_be_retimed_through_the_command(
    session,
) -> None:
    # The freeze must not break the ordinary creation flow: a draft is still editable.
    await _seed(session)
    market_id = await _approved_market(session)
    entity_id, revision = await _research(
        session, market_id, UsageScope.RESEARCH_BACKTEST, approve=False
    )
    revision.revision_state = ResearchRevisionState.DRAFT
    await session.commit()

    policy = await rd_cmd.set_time_policy(
        session,
        ADMIN,
        entity_id=entity_id,
        event_time_semantics=EventTimeSemantics.PROVIDER_EVENT_TIMESTAMP,
        available_time=FIXED_DELAY_2M,
        timezone_spec=UTC_TZ,
    )
    await session.commit()
    assert policy.available_time_policy is AvailableTimePolicy.FIXED_DELAY
    assert (await _head(session, entity_id)).available_delay_seconds == 120


async def test_the_agent_bundle_does_not_validate_the_time_policy_by_design(session) -> None:
    # NOT a defect: doc 12 §9.3 row-by-row allows EVERY scope into Agent research,
    # and an Agent research bundle performs no as-of resolution, so an incomplete
    # time policy does not make it unusable. Only the EVIDENCE bundle, whose members
    # are replayed against decision times, requires a resolvable rule (§9.2).
    await _seed(session)
    market_id = await _approved_market(session)
    _, revision = await _research(session, market_id, UsageScope.RESEARCH_BACKTEST)
    revision.available_time_policy = None
    revision.available_delay_seconds = None
    await session.commit()

    agent_bundle = await rd_jobs.compile_agent_data_bundle(
        session, ADMIN, research_revision_ids=[revision.revision_id]
    )
    assert agent_bundle["members"][0]["research_revision_id"] == revision.revision_id

    with pytest.raises(TimePolicyInvalid):
        await rd_jobs.compile_backtest_evidence_bundle(
            session, ADMIN, research_revision_ids=[revision.revision_id]
        )


# --------------------------------------------------------------------------- #
# CONFIRMED DISCREPANCIES — canonical expectation, expected to fail today       #
# --------------------------------------------------------------------------- #
# Each of these reproduces a defect that ADIM 13 confirmed empirically but did NOT
# fix: the charter allows a narrow fix only in the shared time-policy layer, and
# these live in the Agent tool gateway / the bundle member shape. They are
# ``strict`` so the day the defect is fixed the xfail itself fails and the marker
# must be removed — a silent "it started passing" is not possible.


@pytest.mark.xfail(
    strict=True,
    reason="GH #556 — data_bundle.resolve reads no lifecycle state: a soft-deleted "
    "root and a deprecated/revoked revision both pin successfully, while the twin "
    "compile_agent_data_bundle blocks both (doc 12 §11, §14).",
)
async def test_the_agent_tool_gateway_blocks_a_soft_deleted_root(session) -> None:
    await _seed(session)
    market_id = await _approved_market(session)
    entity_id, revision = await _research(session, market_id, UsageScope.RESEARCH_BACKTEST)
    root = await rd_repo.get_dataset_root(session, entity_id)
    assert root is not None
    root.deletion_state = DeletionState.SOFT_DELETED
    await session.commit()

    result = await _gateway_bundle(session, revision.revision_id, scope="research")
    assert result["status"] == "rejected"


@pytest.mark.xfail(
    strict=True,
    reason="GH #556 — data_bundle.resolve reads no revision_state: a DEPRECATED "
    "revision pins successfully (doc 12 §11).",
)
async def test_the_agent_tool_gateway_blocks_a_deprecated_revision(session) -> None:
    await _seed(session)
    market_id = await _approved_market(session)
    _, revision = await _research(session, market_id, UsageScope.RESEARCH_BACKTEST)
    revision.revision_state = ResearchRevisionState.DEPRECATED
    await session.commit()

    result = await _gateway_bundle(session, revision.revision_id, scope="research")
    assert result["status"] == "rejected"


@pytest.mark.xfail(
    strict=True,
    reason="GH #557 — data_bundle.resolve trusts the CALLER's claimed "
    "has_approved_feature_definition instead of resolving it server-side the way "
    "compile_backtest_evidence_bundle does (doc 12 §9.3, §2 server-side policy).",
)
async def test_the_agent_tool_gateway_resolves_the_feature_definition_server_side(
    session,
) -> None:
    await _seed(session)
    market_id = await _approved_market(session)
    _, revision = await _research(session, market_id, UsageScope.FEATURE_INPUT_ONLY)
    await session.commit()

    # No ResearchFeatureDefinition row exists; the caller claims one does.
    result = await _gateway_bundle(
        session,
        revision.revision_id,
        scope="execution",
        has_approved_feature_definition=True,
    )
    assert result["status"] == "rejected"


@pytest.mark.xfail(
    strict=True,
    reason="GH #558 — neither bundle member carries the available-time policy, "
    "though doc 12 §9.1 requires the Agent Data Bundle to pin 'exact revision IDs, "
    "usage scope and time policy' and §9.2 lists available_time_policies[] as a "
    "BacktestEvidenceBundle field. The Run manifest DOES pin it, so the two "
    "execution-evidence surfaces disagree.",
)
async def test_both_bundles_pin_the_available_time_policy(session) -> None:
    await _seed(session)
    market_id = await _approved_market(session)
    entity_id, revision = await _research(session, market_id, UsageScope.RESEARCH_BACKTEST)
    await session.commit()

    agent_bundle = await rd_jobs.compile_agent_data_bundle(
        session, ADMIN, research_revision_ids=[revision.revision_id]
    )
    evidence = await rd_jobs.compile_backtest_evidence_bundle(
        session, ADMIN, research_revision_ids=[revision.revision_id]
    )
    manifest_entry = (
        await run_ctx._research_entries(
            session,
            FundingPolicy(
                enabled=True,
                source_root_id=entity_id,
                source_revision_id=revision.revision_id,
                source_content_hash=revision.content_hash,
            ),
        )
    )[0]

    # The Run manifest already pins it; the two bundles must not be poorer.
    assert manifest_entry["revision"]["available_time_policy"] == "fixed_delay"
    assert agent_bundle["members"][0]["available_time_policy"] == "fixed_delay"
    assert evidence["members"][0]["available_time_policy"] == "fixed_delay"
