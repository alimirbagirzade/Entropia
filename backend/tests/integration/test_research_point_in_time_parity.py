"""Agent bundle vs Backtest bundle — point-in-time parity (doc 12 §9.1, §9.2, §9.3, §11).

ADIM 13. The charter question: does a Research Data revision carry the SAME canonical
point-in-time truth into an Agent research bundle as it does into a Backtest execution
bundle? These tests answer it against a real database, on the four surfaces that can
pin a research revision:

    A1  ``jobs/agent_tools._handle_data_bundle_resolve``  (the UI-less Agent tool)
    A2  ``jobs/research_data.compile_agent_data_bundle``  (POST /bundles/agent)
    B1  ``jobs/research_data.compile_backtest_evidence_bundle`` (POST /bundles/backtest-evidence)
    B2  ``commands/backtest_run_context._research_entries``     (the Run manifest)

Where the four agree, a passing test locks the agreement. Where they DISAGREED, the
test stated the CANONICAL expectation and carried ``xfail(strict=True)`` naming the
issue that owned the decision — never softened into an assertion of the defect.

All of those are now closed and assert normally. The last one, GH #558 (neither
bundle pinned the available-time policy), was a PRODUCT decision: Karar 2 was signed
A1+A2 on 2026-08-14 and ``jobs/research_data._pin_member`` shipped the pin, so the
marker was REMOVED rather than relaxed. This file therefore holds no strict xfail —
section T below is the replacement, and it fails if the pin ever regresses.

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
from entropia.shared.manifest import manifest_hash

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
# CONFIRMED DISCREPANCIES — canonical expectation                               #
# --------------------------------------------------------------------------- #
# Each of these reproduced a defect that ADIM 13 confirmed empirically but did NOT
# fix. They were ``xfail(strict)`` so the day the defect was fixed the xfail itself
# would fail and the marker HAD to be removed — a silent "it started passing" was
# never possible.
#
# The three Agent-tool-gateway rows (#556 twice, #557) are now FIXED and assert
# normally: ``jobs/agent_tools._handle_data_bundle_resolve`` passes every research
# member through ``rd_jobs.admit_bundle_member``, the same admission gate the human
# compilers use. The last one (#558, the missing available-time-policy pin) is a
# PRODUCT decision, not a bug fix, and keeps its marker.


async def test_the_agent_tool_gateway_blocks_a_soft_deleted_root(session) -> None:
    # GH #556, FIXED: the gateway routes through the SAME
    # ``rd_jobs.admit_bundle_member`` gate the twin compiler uses (doc 12 §11, §14).
    await _seed(session)
    market_id = await _approved_market(session)
    entity_id, revision = await _research(session, market_id, UsageScope.RESEARCH_BACKTEST)
    root = await rd_repo.get_dataset_root(session, entity_id)
    assert root is not None
    root.deletion_state = DeletionState.SOFT_DELETED
    await session.commit()

    result = await _gateway_bundle(session, revision.revision_id, scope="research")
    assert result["status"] == "rejected"


async def test_the_agent_tool_gateway_blocks_a_deprecated_revision(session) -> None:
    # GH #556, FIXED: a non-consumable revision is refused a NEW bundle on every
    # surface, the gateway included (doc 12 §11).
    await _seed(session)
    market_id = await _approved_market(session)
    _, revision = await _research(session, market_id, UsageScope.RESEARCH_BACKTEST)
    revision.revision_state = ResearchRevisionState.DEPRECATED
    await session.commit()

    result = await _gateway_bundle(session, revision.revision_id, scope="research")
    assert result["status"] == "rejected"


async def test_the_agent_tool_gateway_resolves_the_feature_definition_server_side(
    session,
) -> None:
    # GH #557, FIXED: the Feature-Input-Only precondition is resolved from the
    # database by the shared gate; the caller's claim is not read at all
    # (doc 12 §9.3, §2 server-side policy).
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


# GH #558 — FIXED (Karar 2 = A1+A2, signed 2026-08-14). This was the repository's
# ONLY ``xfail(strict=True)``; the marker is gone, not softened, because the product
# changed: ``jobs/research_data._pin_member`` now carries the timing block on every
# member of both bundles. Strict xfail count 1 -> 0.
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


# --------------------------------------------------------------------------- #
# T — timing provenance is pinned INTO the bundle identity (GH #558, Karar 2)    #
# --------------------------------------------------------------------------- #
# Karar 2 (``docs/decisions/closure_product_decisions_2026-08-13.md`` §Karar 2,
# signed 2026-08-14) chose A1+A2: the full timing field set on every member
# (authoritative) plus doc 12 §9.2's top-level derived arrays. These tests hold
# the three execution-evidence surfaces to ONE answer and prove the hash moved.

# The six keys the Run manifest pins per research feed
# (``commands/backtest_run_context.py::_research_entries``). A1 mirrors them
# field for field, so this tuple is the parity contract itself: adding a seventh
# to the manifest without adding it to the members re-opens #558.
# The two keys ``_seal_bundle`` adds AFTER computing the hash. They cannot be inside
# it: ``resolved_at`` is wall-clock (it would make an identical bundle hash differently
# every compile) and ``bundle_hash`` cannot contain itself.
_UNHASHED = frozenset({"resolved_at", "bundle_hash"})

TIMING_KEYS = (
    "available_time_policy",
    "available_delay_seconds",
    "event_time_semantics",
    "frequency_policy",
    "source_timezone_mode",
    "source_timezone_iana",
)


async def _three_artifacts(session, entity_id: str, revision) -> tuple[dict, dict, dict]:
    """Agent bundle member, evidence bundle member, Run manifest revision — same run."""
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
    return agent_bundle, evidence, manifest_entry


async def test_all_three_artifacts_carry_the_same_timing_dict(session) -> None:
    # The charter question of this slice: for ONE run, do the Agent Data Bundle,
    # the Backtest Evidence Bundle and the Run Context Manifest agree on the whole
    # timing dictionary — not merely on the policy token? Asserting only the token
    # is what Karar 2 Seçenek C would have bought: green gate, open gap.
    await _seed(session)
    market_id = await _approved_market(session)
    entity_id, revision = await _research(
        session, market_id, UsageScope.RESEARCH_BACKTEST, delay_seconds=7200
    )
    # A NON-default zone on both halves. The harness leaves the zone unset, and an
    # unset zone makes the three artifacts agree on ``None`` — equality that would
    # hold just as well if no surface carried the field at all.
    revision.source_timezone_mode = ResearchTimezoneMode.CUSTOM
    revision.source_timezone_iana = "Europe/Istanbul"
    await session.commit()

    agent_bundle, evidence, manifest_entry = await _three_artifacts(session, entity_id, revision)

    manifest_timing = {k: manifest_entry["revision"][k] for k in TIMING_KEYS}
    agent_timing = {k: agent_bundle["members"][0][k] for k in TIMING_KEYS}
    evidence_timing = {k: evidence["members"][0][k] for k in TIMING_KEYS}

    assert agent_timing == manifest_timing
    assert evidence_timing == manifest_timing
    # Pin the VALUES too: an all-None dict would satisfy equality three ways and
    # prove nothing. 7200s is the harness's non-default delay, so a member that
    # silently dropped the delay and kept the token cannot pass.
    assert manifest_timing["available_time_policy"] == "fixed_delay"
    assert manifest_timing["available_delay_seconds"] == 7200
    assert manifest_timing["event_time_semantics"] == "provider_event_timestamp"
    assert manifest_timing["source_timezone_mode"] == "custom"
    assert manifest_timing["source_timezone_iana"] == "Europe/Istanbul"


async def test_the_bundle_hash_moves_when_the_available_delay_moves(session) -> None:
    # The POINT of A1: ``bundle_hash`` used to be invariant under a time-policy
    # change (GH #558), so a bundle could not attest, from its own contents, which
    # availability rule compiled it. One variable moves here — the delay — and the
    # revision id and content_hash (which hashes the PAYLOAD, not the timing
    # metadata) both stay put, so a moved hash can only come from the new pin.
    await _seed(session)
    market_id = await _approved_market(session)
    _, revision = await _research(
        session, market_id, UsageScope.RESEARCH_BACKTEST, delay_seconds=120
    )
    await session.commit()

    first = await rd_jobs.compile_backtest_evidence_bundle(
        session, ADMIN, research_revision_ids=[revision.revision_id]
    )
    # Negative control: recompiling an UNCHANGED revision must reproduce the hash
    # byte for byte. Without this, the assertion below would also pass if the hash
    # were simply nondeterministic (``resolved_at`` is added AFTER hashing — this
    # is what proves that still holds).
    again = await rd_jobs.compile_backtest_evidence_bundle(
        session, ADMIN, research_revision_ids=[revision.revision_id]
    )
    assert again["bundle_hash"] == first["bundle_hash"]
    # ...and the reason it reproduces is that the two volatile keys sit OUTSIDE the
    # hashed body. Recomputing over the body minus those two keys must return the
    # published hash — which also pins that nothing else was excluded.
    assert (
        manifest_hash({k: v for k, v in first.items() if k not in _UNHASHED})
        == (first["bundle_hash"])
    )

    # Production CANNOT reach this mutation — ADIM 13 froze an approved revision's
    # policy (``time_policy.py::ensure_time_policy_mutable``) and ADIM 54 pinned
    # that with an acceptance test. The ORM write here is deliberate: it isolates
    # the hash's SENSITIVITY, which is a property of the bundle itself and must not
    # depend on two distant neighbouring rules staying strict (Karar 2 §Seçenek B).
    revision.available_delay_seconds = 7200
    await session.flush()

    moved = await rd_jobs.compile_backtest_evidence_bundle(
        session, ADMIN, research_revision_ids=[revision.revision_id]
    )
    assert (
        moved["members"][0]["research_revision_id"] == first["members"][0]["research_revision_id"]
    )
    assert (
        moved["members"][0]["research_content_hash"] == first["members"][0]["research_content_hash"]
    )
    assert moved["bundle_hash"] != first["bundle_hash"]


async def test_the_sealed_bundle_publishes_doc_12_92_arrays(session) -> None:
    # Karar 2 = A2: §9.2's own field names, values DERIVED from the members. The
    # arrays are sorted and de-duplicated because canonical JSON sorts object keys
    # but not array elements — an unsorted projection would make ``bundle_hash``
    # depend on the caller's argument order.
    await _seed(session)
    market_id = await _approved_market(session)
    _, first = await _research(session, market_id, UsageScope.RESEARCH_BACKTEST, delay_seconds=120)
    _, second = await _research(
        session, market_id, UsageScope.RESEARCH_BACKTEST, delay_seconds=7200
    )
    _, third = await _research(session, market_id, UsageScope.RESEARCH_BACKTEST)
    # DISTINCT policies, so the derived array holds two elements and the sort is
    # actually exercised. With one shared token a single-element set sorts the same
    # either way and an unsorted projection would pass this test unnoticed.
    # ``same_as_event_time`` must send a null delay (doc 12 §5.2).
    third.available_time_policy = AvailableTimePolicy.SAME_AS_EVENT_TIME
    third.available_delay_seconds = None
    await session.commit()

    ids = [first.revision_id, second.revision_id, third.revision_id]
    forward = await rd_jobs.compile_agent_data_bundle(session, ADMIN, research_revision_ids=ids)
    reverse = await rd_jobs.compile_agent_data_bundle(
        session, ADMIN, research_revision_ids=list(reversed(ids))
    )

    assert forward["compiler_version"] == "research-bundle-v2"
    # Three members, two distinct tokens -> de-duplicated AND sorted.
    assert forward["available_time_policies"] == ["fixed_delay", "same_as_event_time"]
    assert forward["available_time_policies"] == reverse["available_time_policies"]
    assert "instrument_mapping_revision_ids" in forward
    assert "feature_definition_revision_ids" in forward

    # The DERIVED arrays are order-independent; the member list is not, and must
    # not be — it is the authoritative half and follows the caller's pinned order.
    assert [m["research_revision_id"] for m in forward["members"]] == ids
    assert [m["research_revision_id"] for m in reverse["members"]] == list(reversed(ids))

    # Class D, recorded not hidden: doc 12 §9.2 also names these two, and NOTHING in
    # backend/src produces them (measured 2026-08-14). Emitting them as empty arrays
    # would assert "there are none" — a provenance lie rather than a provenance gap.
    # This assertion is the tripwire: whoever ships the backing field must decide
    # here, deliberately, rather than discover the omission in an audit.
    assert "alignment_policy_versions" not in forward
    assert "missing_and_stale_policies" not in forward


async def test_the_two_backed_92_arrays_carry_real_values(session) -> None:
    # Karar 2's sub-decision: of §9.2's four remaining names, the two with a shipped
    # source go IN. Presence alone is not the claim — these must carry the revision's
    # actual instrument mapping and its actual feature definitions, so this test
    # gives both a non-empty, non-default value.
    await _seed(session)
    market_id = await _approved_market(session)
    entity_id, revision = await _research(
        session, market_id, UsageScope.RESEARCH_BACKTEST, approve=False
    )
    beta = await rd_cmd.define_feature(
        session, OWNER, entity_id=entity_id, feature_name="beta", definition={"expr": "b"}
    )
    alpha = await rd_cmd.define_feature(
        session, OWNER, entity_id=entity_id, feature_name="alpha", definition={"expr": "a"}
    )
    revision.instrument_mapping_ref = "map_v3"
    await session.commit()

    bundle = await rd_jobs.compile_agent_data_bundle(
        session, ADMIN, research_revision_ids=[revision.revision_id]
    )

    assert bundle["members"][0]["instrument_mapping_ref"] == "map_v3"
    assert bundle["instrument_mapping_revision_ids"] == ["map_v3"]
    assert bundle["feature_definition_revision_ids"] == sorted(
        [alpha.feature_definition_id, beta.feature_definition_id]
    )
    # Defined beta-then-alpha; the derived array is sorted by id, not by creation
    # order, so the bundle body hashes identically however the rows were written.
    assert bundle["members"][0]["feature_definition_ids"] == sorted(
        [alpha.feature_definition_id, beta.feature_definition_id]
    )


async def test_the_sealed_body_matches_the_published_openapi_schema(session) -> None:
    # Both bundle handlers return a bare ``dict``, so ``docs/openapi.json`` used to
    # publish a free-form object: the timing pin could have changed shape with a
    # ZERO-line schema diff and the drift guard would have stayed green (the O-30
    # trap). ``SealedBundleResponse`` closes that — but a declared schema nothing
    # checks is just a better-looking lie, so this compares the schema against a
    # body compiled from a real database, key for key, in both directions.
    from entropia.apps.api.openapi_export import generate_schema

    components = generate_schema()["components"]["schemas"]
    published_bundle = set(components["SealedBundleResponse"]["properties"])
    published_member = set(components["BundleMemberModel"]["properties"])

    await _seed(session)
    market_id = await _approved_market(session)
    _, revision = await _research(session, market_id, UsageScope.RESEARCH_BACKTEST)
    await session.commit()

    agent_bundle = await rd_jobs.compile_agent_data_bundle(
        session, ADMIN, research_revision_ids=[revision.revision_id], task_id="task_7"
    )
    evidence = await rd_jobs.compile_backtest_evidence_bundle(
        session, ADMIN, research_revision_ids=[revision.revision_id], run_request_id="run_3"
    )

    # Neither body alone covers the schema: ``_seal_bundle`` DROPS a None extra, so
    # ``task_id`` rides only on the Agent bundle and ``run_request_id`` only on the
    # evidence bundle. Together they must account for every published key, and
    # neither may carry a key the schema does not publish.
    assert set(agent_bundle) | set(evidence) == published_bundle
    assert set(agent_bundle) <= published_bundle
    assert set(evidence) <= published_bundle
    assert set(agent_bundle["members"][0]) == published_member
    assert set(evidence["members"][0]) == published_member
