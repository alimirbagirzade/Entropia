"""Stage 7b — Future Dev against a real database (doc 22 §8-§12, FD-01..FD-15).

Auto-skips without PostgreSQL. Covers: seven baseline PLACEHOLDER registry
slots with deterministic ids (idempotent seed); registry list/detail + Graphic
View placeholder overview with the six static cards and NO dataset/job
(FD-01/03); Admin-only lifecycle transitions at the service (FD-13); non-empty
reason + required idempotency key + legal edge enforcement (FD-14); the
expected_registry_version OCC (CAPABILITY_STATE_STALE); the seven activation
gates — presence for Designed, completeness for Limited (6) / Active (7) with a
per-gate issue list; immutable activation events + audit/outbox in one tx;
idempotent transition replay; Retired terminality (FD-11); inactive operation
-> CAPABILITY_NOT_ACTIVE with zero rows/jobs/events (FD-02, CR-09); Limited
view-dataset preparation from pinned refs (FD-04) and immutable analysis
artifacts requiring method_version (FD-05/09); CR-08 Agent tool exposure +
recorded REJECTED denial while Placeholder (FD-10); no Live Trade order route
(FD-12); an L1 FK insert-order proof for the new create_* helpers; and — against
a REAL seeded Backtest Result rather than a literal ref — that neither operation
writes anything back onto it (FD-04.c4 / FD-05.c4).
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import func, select

from entropia.application.commands.capability import (
    create_analysis_artifact,
    query_view_dataset,
    transition_capability,
)
from entropia.application.jobs import agent_tools
from entropia.application.queries.capability import (
    get_capability,
    get_graphic_view_overview,
    list_capabilities,
)
from entropia.domain.agent_lab.enums import ALPHA_AGENT_ID, RuntimeMode, RuntimeStatus
from entropia.domain.agent_lab.tool_gateway import (
    CAPABILITY_GATED_TOOLS,
    ToolName,
    exposed_tool_names,
)
from entropia.domain.backtest.enums import MetricAvailability
from entropia.domain.capability.baseline import (
    BASELINE_CAPABILITIES,
    GRAPHIC_VIEW_INTRO,
    initial_dependency_snapshot,
)
from entropia.domain.capability.enums import (
    BACKTEST_REVIEW,
    BASELINE_CAPABILITY_KEYS,
    GRAPHIC_VIEW,
    LIVE_TRADE,
    ActivationGate,
    CapabilityState,
)
from entropia.domain.identity import Actor
from entropia.domain.lifecycle.enums import PrincipalType, Role
from entropia.infrastructure.postgres.models import (
    AgentRuntime,
    AnalysisArtifact,
    AuditEvent,
    BacktestResult,
    CapabilityActivationEvent,
    FutureCapability,
    Job,
    MetricValueRow,
    OutboxEvent,
    Principal,
    ResultManifestSnapshot,
    TradeLedgerRow,
    ViewDataset,
)
from entropia.infrastructure.postgres.repositories import capability as capability_repo
from entropia.shared.errors import (
    CapabilityAccessDeniedError,
    CapabilityDependencyMissingError,
    CapabilityNotActiveError,
    CapabilityNotFoundError,
    CapabilityStateStaleError,
    CapabilityTransitionRejectedError,
    ValidationError,
)

pytestmark = pytest.mark.integration

ADMIN = Actor(
    principal_id="user_admin",
    principal_type=PrincipalType.HUMAN,
    role=Role.ADMIN,
    correlation_id="corr_adm",
)
USER = Actor(principal_id="user_1", principal_type=PrincipalType.HUMAN, role=Role.USER)
SUPERVISOR = Actor(
    principal_id="user_sup", principal_type=PrincipalType.HUMAN, role=Role.SUPERVISOR
)
AGENT = Actor(
    principal_id="agent_alpha",
    principal_type=PrincipalType.AGENT,
    role=None,
    correlation_id="corr_ag",
)

ALL_GATES_COMPLETE = {"gates": {gate.value: True for gate in ActivationGate}}
GATES_WITHOUT_UI = {"gates": {gate.value: gate is not ActivationGate.UI for gate in ActivationGate}}


async def _seed(session) -> None:
    for actor in (ADMIN, USER, SUPERVISOR, AGENT):
        session.add(Principal(principal_id=actor.principal_id, principal_type=actor.principal_type))
    session.add(
        AgentRuntime(
            agent_id=ALPHA_AGENT_ID,
            mode=RuntimeMode.CONTINUOUS,
            status=RuntimeStatus.ACTIVE,
            row_version=1,
        )
    )
    await capability_repo.seed_baseline_capabilities(session)
    await session.commit()


async def _count(session, model) -> int:
    return int((await session.execute(select(func.count()).select_from(model))).scalar_one())


async def _transition(
    session, key: str, to_state: str, *, expected: int, snapshot=None, idem: str
) -> dict:
    return await transition_capability(
        session,
        ADMIN,
        capability_key=key,
        to_state=to_state,
        reason=f"stage 7b test transition to {to_state}",
        expected_registry_version=expected,
        dependency_snapshot=snapshot,
        idempotency_key=idem,
    )


async def _walk_to_limited(session, key: str) -> dict:
    """placeholder -> designed -> internal -> shadow -> limited (legal chain)."""
    snapshot = initial_dependency_snapshot()
    result = await _transition(
        session, key, "designed", expected=1, snapshot=snapshot, idem=f"{key}-designed"
    )
    result = await _transition(session, key, "internal", expected=2, idem=f"{key}-internal")
    result = await _transition(session, key, "shadow", expected=3, idem=f"{key}-shadow")
    result = await _transition(
        session, key, "limited", expected=4, snapshot=GATES_WITHOUT_UI, idem=f"{key}-limited"
    )
    await session.commit()
    return result


# --------------------------------------------------------------------------- #
# Registry seed + read models (FD-01/03)                                       #
# --------------------------------------------------------------------------- #


async def test_baseline_seed_seven_placeholder_capabilities(session) -> None:
    await _seed(session)
    rows = (await session.execute(select(FutureCapability))).scalars().all()
    assert sorted(row.capability_key for row in rows) == sorted(BASELINE_CAPABILITY_KEYS)
    for row in rows:
        assert row.lifecycle_state is CapabilityState.PLACEHOLDER
        assert row.registry_version == 1
        assert row.capability_id == f"fcap_{row.capability_key}"
        assert set(row.dependency_snapshot["gates"]) == {g.value for g in ActivationGate}
    # Idempotent re-seed: no duplicates.
    await capability_repo.seed_baseline_capabilities(session)
    await session.commit()
    assert await _count(session, FutureCapability) == len(BASELINE_CAPABILITY_KEYS)


async def test_list_and_get_capability_read_models(session) -> None:
    await _seed(session)
    listing = await list_capabilities(session, USER)
    assert listing["count"] == 7
    assert [c["capability_key"] for c in listing["capabilities"]] == sorted(
        BASELINE_CAPABILITY_KEYS
    )
    assert all(not c["is_operational"] for c in listing["capabilities"])

    detail = await get_capability(session, USER, capability_key=GRAPHIC_VIEW)
    assert detail["menu_path"] == "Future Dev > Graphic View"
    assert detail["lifecycle_state"] == "placeholder"
    assert "controlled Future Dev placeholder" in detail["status_message"]
    assert set(detail["dependency_snapshot"]["gates"]) == {g.value for g in ActivationGate}

    with pytest.raises(CapabilityNotFoundError):
        await get_capability(session, USER, capability_key="not_a_capability")


async def test_graphic_view_overview_is_static_and_side_effect_free(session) -> None:
    """FD-01/03: the placeholder overview renders intro + six cards and starts
    nothing — no dataset, no job, no publication of any kind (CR-09)."""
    await _seed(session)
    overview = await get_graphic_view_overview(session, USER)
    assert overview["lifecycle_state"] == "placeholder"
    assert overview["is_operational"] is False
    assert overview["intro"] == GRAPHIC_VIEW_INTRO
    assert [card["title"] for card in overview["cards"]] == [
        "Price Chart",
        "Equity Curve",
        "Drawdown Chart",
        "Exposure / Position Size",
        "Trade Distribution",
        "Regime Overlay",
    ]
    assert await _count(session, ViewDataset) == 0
    assert await _count(session, Job) == 0


async def test_no_live_trade_order_route_exists(session) -> None:
    """FD-12/CR-09: Live Trade stays a separate NOT-implemented execution plane
    — no order/broker/execution-session route is registered anywhere."""
    from entropia.apps.api.main import create_app

    paths = [getattr(route, "path", "") for route in create_app().routes]
    assert not any("live-trade" in p or "live_trade" in p or "order" in p for p in paths)
    assert not any("execution-plan" in p or "execution_plan" in p for p in paths)


# --------------------------------------------------------------------------- #
# Lifecycle transition contract (FD-13/14, OCC, gates, audit)                  #
# --------------------------------------------------------------------------- #


async def test_transition_is_admin_only_at_service(session) -> None:
    await _seed(session)
    for actor in (USER, SUPERVISOR, AGENT):
        with pytest.raises(CapabilityAccessDeniedError):
            await transition_capability(
                session,
                actor,
                capability_key=GRAPHIC_VIEW,
                to_state="designed",
                reason="not allowed",
                expected_registry_version=1,
                idempotency_key=f"idem-{actor.principal_id}",
            )
    capability = await capability_repo.get_capability_by_key(session, GRAPHIC_VIEW)
    assert capability.lifecycle_state is CapabilityState.PLACEHOLDER
    assert await _count(session, CapabilityActivationEvent) == 0


async def test_transition_requires_nonempty_reason_and_idempotency_key(session) -> None:
    await _seed(session)
    for bad_reason in ("", "   "):
        with pytest.raises(CapabilityTransitionRejectedError):
            await transition_capability(
                session,
                ADMIN,
                capability_key=GRAPHIC_VIEW,
                to_state="designed",
                reason=bad_reason,
                expected_registry_version=1,
                idempotency_key="idem-reason",
            )
    with pytest.raises(ValidationError):
        await transition_capability(
            session,
            ADMIN,
            capability_key=GRAPHIC_VIEW,
            to_state="designed",
            reason="valid reason",
            expected_registry_version=1,
            idempotency_key=None,
        )
    assert await _count(session, CapabilityActivationEvent) == 0


async def test_transition_rejects_illegal_edge_and_unknown_state(session) -> None:
    await _seed(session)
    with pytest.raises(CapabilityTransitionRejectedError) as exc:
        await _transition(session, GRAPHIC_VIEW, "active", expected=1, idem="illegal-edge")
    issue = exc.value.details[0]
    assert issue["issue"] == "illegal_transition"
    assert issue["current_state"] == "placeholder"
    assert issue["allowed_targets"] == ["designed"]

    with pytest.raises(CapabilityTransitionRejectedError):
        await _transition(session, GRAPHIC_VIEW, "not_a_state", expected=1, idem="unknown-state")
    capability = await capability_repo.get_capability_by_key(session, GRAPHIC_VIEW)
    assert capability.lifecycle_state is CapabilityState.PLACEHOLDER


async def test_transition_stale_registry_version_conflict(session) -> None:
    await _seed(session)
    with pytest.raises(CapabilityStateStaleError):
        await _transition(session, GRAPHIC_VIEW, "designed", expected=99, idem="stale-occ")
    capability = await capability_repo.get_capability_by_key(session, GRAPHIC_VIEW)
    assert capability.registry_version == 1


async def test_transition_missing_gate_keys_blocked_with_issue_list(session) -> None:
    """FD-14: Designed needs every gate KEY recorded in the snapshot; the
    rejection carries the per-gate issue list and the state does not change."""
    await _seed(session)
    with pytest.raises(CapabilityDependencyMissingError) as exc:
        await _transition(
            session,
            GRAPHIC_VIEW,
            "designed",
            expected=1,
            snapshot={"gates": {"domain": True}},
            idem="missing-gates",
        )
    missing = {issue["gate"] for issue in exc.value.details}
    assert missing == {g.value for g in ActivationGate} - {"domain"}
    capability = await capability_repo.get_capability_by_key(session, GRAPHIC_VIEW)
    assert capability.lifecycle_state is CapabilityState.PLACEHOLDER


async def test_transition_writes_event_audit_outbox_and_bumps_version(session) -> None:
    await _seed(session)
    result = await _transition(
        session,
        GRAPHIC_VIEW,
        "designed",
        expected=1,
        snapshot=initial_dependency_snapshot(),
        idem="designed-ok",
    )
    await session.commit()
    assert result["lifecycle_state"] == "designed"
    assert result["registry_version"] == 2

    events = await capability_repo.list_activation_events(session, "fcap_graphic_view")
    assert len(events) == 1
    event = events[0]
    assert (event.from_state, event.to_state) == (
        CapabilityState.PLACEHOLDER,
        CapabilityState.DESIGNED,
    )
    assert event.prior_registry_version == 1
    assert event.resulting_registry_version == 2
    assert event.reason == "stage 7b test transition to designed"
    assert len(event.snapshot_checksum) == 64

    audit = (
        (
            await session.execute(
                select(AuditEvent).where(AuditEvent.event_kind == "capability_state_changed")
            )
        )
        .scalars()
        .all()
    )
    assert len(audit) == 1
    assert audit[0].target_entity_id == "fcap_graphic_view"
    outbox = (
        (
            await session.execute(
                select(OutboxEvent).where(OutboxEvent.event_type == "capability_state_changed")
            )
        )
        .scalars()
        .all()
    )
    assert len(outbox) == 1
    assert outbox[0].payload["to_state"] == "designed"


async def test_transition_idempotent_replay_returns_same_result(session) -> None:
    await _seed(session)
    first = await _transition(
        session,
        GRAPHIC_VIEW,
        "designed",
        expected=1,
        snapshot=initial_dependency_snapshot(),
        idem="replay-key",
    )
    await session.commit()
    replay = await _transition(
        session,
        GRAPHIC_VIEW,
        "designed",
        expected=1,
        snapshot=initial_dependency_snapshot(),
        idem="replay-key",
    )
    assert replay["registry_version"] == first["registry_version"] == 2
    assert await _count(session, CapabilityActivationEvent) == 1


async def test_active_requires_all_seven_gates_then_retires_terminally(session) -> None:
    """Limited passes with 6 complete gates (UI outstanding); Active demands
    the seventh; Retired accepts no further transition (FD-11)."""
    await _seed(session)
    await _walk_to_limited(session, GRAPHIC_VIEW)
    capability = await capability_repo.get_capability_by_key(session, GRAPHIC_VIEW)
    assert capability.lifecycle_state is CapabilityState.LIMITED
    assert capability.enabled_at is not None

    with pytest.raises(CapabilityDependencyMissingError) as exc:
        await _transition(session, GRAPHIC_VIEW, "active", expected=5, idem="active-no-ui")
    assert exc.value.details == [{"gate": "ui", "issue": "gate_incomplete"}]

    await _transition(
        session,
        GRAPHIC_VIEW,
        "active",
        expected=5,
        snapshot=ALL_GATES_COMPLETE,
        idem="active-ok",
    )
    await session.commit()
    result = await _transition(session, GRAPHIC_VIEW, "retired", expected=6, idem="retire-ok")
    await session.commit()
    assert result["lifecycle_state"] == "retired"
    assert result["retirement_at"] is not None

    with pytest.raises(CapabilityTransitionRejectedError):
        await _transition(session, GRAPHIC_VIEW, "designed", expected=7, idem="after-retire")


# --------------------------------------------------------------------------- #
# Inactive operations (FD-02, CR-09)                                           #
# --------------------------------------------------------------------------- #


async def test_view_dataset_query_inactive_creates_nothing(session) -> None:
    await _seed(session)
    with pytest.raises(CapabilityNotActiveError) as exc:
        await query_view_dataset(
            session,
            USER,
            source_manifest_refs=["result_abc123"],
            schema_version="v1",
        )
    assert exc.value.details == [{"capability_key": GRAPHIC_VIEW, "lifecycle_state": "placeholder"}]
    await session.rollback()
    assert await _count(session, ViewDataset) == 0
    assert await _count(session, Job) == 0
    assert await _count(session, OutboxEvent) == 0


async def test_analysis_artifact_inactive_creates_nothing(session) -> None:
    await _seed(session)
    with pytest.raises(CapabilityNotActiveError):
        await create_analysis_artifact(
            session,
            USER,
            artifact_type="backtest_review",
            input_manifest_refs=["result_abc123"],
            method_version="review-v1",
        )
    await session.rollback()
    assert await _count(session, AnalysisArtifact) == 0
    assert await _count(session, Job) == 0


async def test_analysis_artifact_unknown_type_rejected(session) -> None:
    await _seed(session)
    with pytest.raises(ValidationError):
        await create_analysis_artifact(
            session,
            USER,
            artifact_type="totally_new_analysis",
            input_manifest_refs=["result_abc123"],
            method_version="v1",
        )
    assert await _count(session, AnalysisArtifact) == 0


async def test_retired_capability_rejects_operations(session) -> None:
    """FD-11: Retired accepts no new command; history stays readable."""
    await _seed(session)
    await _walk_to_limited(session, GRAPHIC_VIEW)
    await _transition(session, GRAPHIC_VIEW, "retired", expected=5, idem="retire-limited")
    await session.commit()
    with pytest.raises(CapabilityNotActiveError):
        await query_view_dataset(
            session, USER, source_manifest_refs=["result_abc123"], schema_version="v1"
        )
    await session.rollback()
    events = await capability_repo.list_activation_events(session, "fcap_graphic_view")
    assert len(events) == 5  # full history preserved read-only


# --------------------------------------------------------------------------- #
# Operational commands while Limited (FD-04/05/09)                             #
# --------------------------------------------------------------------------- #


async def test_view_dataset_limited_pins_sources_and_validates(session) -> None:
    await _seed(session)
    await _walk_to_limited(session, GRAPHIC_VIEW)

    with pytest.raises(ValidationError):
        await query_view_dataset(session, USER, source_manifest_refs=[], schema_version="v1")
    with pytest.raises(ValidationError):
        await query_view_dataset(
            session, USER, source_manifest_refs=["result_abc123"], schema_version="  "
        )
    assert await _count(session, ViewDataset) == 0

    result = await query_view_dataset(
        session,
        USER,
        source_manifest_refs=["result_abc123", "mkt_rev_9"],
        schema_version="v1",
        range_spec={"start": "2026-01-01T00:00:00Z", "end": "2026-06-30T00:00:00Z"},
        idempotency_key="vds-1",
    )
    await session.commit()
    row = await session.get(ViewDataset, result["view_dataset_id"])
    assert row.source_manifest_refs == ["result_abc123", "mkt_rev_9"]
    assert row.capability_key == GRAPHIC_VIEW
    assert row.owner_principal_id == USER.principal_id
    outbox = (
        (
            await session.execute(
                select(OutboxEvent).where(OutboxEvent.event_type == "view_dataset_prepared")
            )
        )
        .scalars()
        .all()
    )
    assert len(outbox) == 1


async def test_analysis_artifact_limited_requires_method_and_is_immutable_root(session) -> None:
    await _seed(session)
    await _walk_to_limited(session, BACKTEST_REVIEW)

    with pytest.raises(ValidationError):
        await create_analysis_artifact(
            session,
            AGENT,
            artifact_type="backtest_review",
            input_manifest_refs=["result_abc123"],
            method_version="",
        )
    result = await create_analysis_artifact(
        session,
        AGENT,
        artifact_type="monte_carlo",
        input_manifest_refs=["result_abc123"],
        method_version="mc-v1",
        idempotency_key="aart-1",
    )
    await session.commit()
    row = await session.get(AnalysisArtifact, result["artifact_id"])
    assert row.artifact_type == "monte_carlo"
    assert row.capability_key == BACKTEST_REVIEW  # MC/WFA gate on Backtest Review
    assert row.input_manifest_refs == ["result_abc123"]
    assert row.method_version == "mc-v1"
    assert row.owner_principal_id == AGENT.principal_id


# --------------------------------------------------------------------------- #
# CR-08 — Agent tool exposure + gateway denial (FD-10)                          #
# --------------------------------------------------------------------------- #


async def test_agent_tool_exposure_follows_capability_state(session) -> None:
    exposed_placeholder = exposed_tool_names(frozenset())
    assert "view_dataset.query" not in exposed_placeholder
    assert "analysis_artifact.create" not in exposed_placeholder
    assert "documentation.search" in exposed_placeholder

    exposed_gv = exposed_tool_names(frozenset({GRAPHIC_VIEW}))
    assert "view_dataset.query" in exposed_gv
    assert "analysis_artifact.create" not in exposed_gv

    exposed_review = exposed_tool_names(frozenset({BACKTEST_REVIEW}))
    assert "analysis_artifact.create" in exposed_review
    assert LIVE_TRADE not in {
        key for keys in CAPABILITY_GATED_TOOLS.values() for key in keys
    }  # Live Trade offers NO agent tool at all (doc 22 §11)

    await _seed(session)
    assert await capability_repo.operational_capability_keys(session) == frozenset()
    await _walk_to_limited(session, GRAPHIC_VIEW)
    assert await capability_repo.operational_capability_keys(session) == frozenset({GRAPHIC_VIEW})


async def test_agent_gateway_records_rejected_denial_while_placeholder(session) -> None:
    """FD-02/10: an Agent call against a Placeholder capability is a durable
    REJECTED governance record (CAPABILITY_NOT_ACTIVE) — never a job/output."""
    await _seed(session)
    result = await agent_tools.dispatch_tool_call(
        session,
        AGENT,
        tool_name="view_dataset.query",
        policy_scope="research",
        request={"source_manifest_refs": ["result_abc123"], "schema_version": "v1"},
        idempotency_key="agent-vds-placeholder",
    )
    await session.commit()
    assert result["status"] == "rejected"
    assert result["reason_code"] == "CAPABILITY_NOT_ACTIVE"
    assert await _count(session, ViewDataset) == 0
    assert await _count(session, Job) == 0


async def test_agent_gateway_dispatches_while_limited(session) -> None:
    await _seed(session)
    await _walk_to_limited(session, GRAPHIC_VIEW)
    result = await agent_tools.dispatch_tool_call(
        session,
        AGENT,
        tool_name="view_dataset.query",
        policy_scope="research",
        request={"source_manifest_refs": ["result_abc123"], "schema_version": "v1"},
        idempotency_key="agent-vds-limited",
    )
    await session.commit()
    assert result["status"] == "succeeded"
    row = await session.get(ViewDataset, result["view_dataset_id"])
    assert row is not None
    assert row.owner_principal_id == AGENT.principal_id


# --------------------------------------------------------------------------- #
# L1 FK insert-order proof (7a lesson — parent flushed before child)            #
# --------------------------------------------------------------------------- #


async def test_l1_fk_insert_order_proof_for_new_create_helpers(session) -> None:
    """Without relationship() SQLAlchemy does NOT FK-order cross-table inserts:
    create_capability flushes the registry row BEFORE add_activation_event
    references it, in ONE uncommitted transaction."""
    session.add(Principal(principal_id=ADMIN.principal_id, principal_type=PrincipalType.HUMAN))
    await session.flush()
    capability = await capability_repo.create_capability(
        session,
        capability_key="l1_proof",
        title="L1 Proof",
        menu_path="Future Dev > L1 Proof",
        dependency_snapshot=initial_dependency_snapshot(),
    )
    await capability_repo.add_activation_event(
        session,
        capability_id=capability.capability_id,
        capability_key="l1_proof",
        from_state=CapabilityState.PLACEHOLDER,
        to_state=CapabilityState.DESIGNED,
        actor_principal_id=ADMIN.principal_id,
        reason="l1 fk proof",
        dependency_snapshot={},
        snapshot_checksum="0" * 64,
        prior_registry_version=1,
        resulting_registry_version=2,
    )
    dataset = await capability_repo.create_view_dataset(
        session,
        capability_key=GRAPHIC_VIEW,
        source_manifest_refs=["result_l1"],
        series_refs=[],
        marker_refs=[],
        range_spec=None,
        schema_version="v1",
        owner_principal_id=ADMIN.principal_id,
        created_by_principal_id=ADMIN.principal_id,
    )
    artifact = await capability_repo.create_analysis_artifact(
        session,
        artifact_type="backtest_review",
        capability_key=BACKTEST_REVIEW,
        input_manifest_refs=["result_l1"],
        method_version="v1",
        output_ref=None,
        owner_principal_id=ADMIN.principal_id,
        created_by_principal_id=ADMIN.principal_id,
    )
    await session.commit()
    assert await _count(session, CapabilityActivationEvent) == 1
    assert (await session.get(ViewDataset, dataset.view_dataset_id)) is not None
    assert (await session.get(AnalysisArtifact, artifact.artifact_id)) is not None


async def test_seeded_capability_keys_match_tool_gate_keys() -> None:
    """Every CR-08 gating key must be a real registry key — a typo here would
    silently make a tool un-exposable forever."""
    seed_keys = {seed.capability_key for seed in BASELINE_CAPABILITIES}
    gated_keys = {key for keys in CAPABILITY_GATED_TOOLS.values() for key in keys}
    assert gated_keys <= seed_keys
    assert ToolName.VIEW_DATASET_QUERY in CAPABILITY_GATED_TOOLS
    assert ToolName.ANALYSIS_ARTIFACT_CREATE in CAPABILITY_GATED_TOOLS


# --------------------------------------------------------------------------- #
# Acceptance batch 21 — the referenced Backtest Result is READ, never WRITTEN   #
# (FD-04.c4 / FD-05.c4, doc 22 §16)                                             #
# --------------------------------------------------------------------------- #
#
# Every FD-04/FD-05 test above hands the commands a LITERAL ref ("result_abc123")
# that names no row at all, so "the referenced Backtest Result is untouched" was
# true only because there was nothing to touch. These two cases seed a REAL,
# DENSE result — canonical metrics, a trade ledger and the pinned run-manifest
# snapshot — pass ITS id as the ref, and read the whole thing back out of
# Postgres afterwards. Without the density guard the claim would be vacuous on
# an empty result; without re-reading from the database it would be an assertion
# about the identity map (the fixture runs with expire_on_commit=False).

_RESULT_ID = "res_fd_immutable"
_RUN_ID = "run_fd_immutable"
_MANIFEST_BODY = {
    "manifest_version": "v1",
    "composition_snapshot_id": "snap_fd_1",
    "instruments": ["BTCUSDT"],
    "market_data_revision_refs": ["mkt_rev_9"],
}


async def _seed_backtest_result(session) -> None:
    """One dense, immutable Backtest Result: 3 canonical metrics, 2 trade ledger
    rows and the manifest snapshot pinned to the result (doc 15 §9.1, §12)."""
    session.add(
        BacktestResult(
            result_id=_RESULT_ID,
            run_id=_RUN_ID,
            manifest_id="man_fd_1",
            manifest_hash="a" * 64,
            workspace_entity_id="ws_fd_1",
            composition_fingerprint="f" * 64,
            engine_version="backtest-engine-fd-test",
            deletion_state="active",
            row_version=1,
            created_by_principal_id=USER.principal_id,
        )
    )
    await session.flush()
    for index, (key, label, value, availability) in enumerate(
        (
            ("net_profit", "Net Profit", Decimal("1250.75"), MetricAvailability.COMPUTED),
            ("max_drawdown", "Max Drawdown", Decimal("310.50"), MetricAvailability.COMPUTED),
            ("romad", "RoMaD", None, MetricAvailability.NO_DRAWDOWN),
        )
    ):
        session.add(
            MetricValueRow(
                metric_value_id=f"mv_fd_{index}",
                result_id=_RESULT_ID,
                metric_key=key,
                label=label,
                unit="usd",
                value_format="decimal_2",
                value=value,
                availability=availability,
                formula_version="metric-v1",
                position_index=index,
            )
        )
    for seq, (direction, entry, exit_price, pnl) in enumerate(
        (
            ("long", Decimal("100.00"), Decimal("110.00"), Decimal("10.00")),
            ("short", Decimal("120.00"), Decimal("115.00"), Decimal("5.00")),
        ),
        start=1,
    ):
        session.add(
            TradeLedgerRow(
                trade_row_id=f"tr_fd_{seq}",
                result_id=_RESULT_ID,
                seq=seq,
                entry_time=f"2026-01-0{seq}T00:00:00Z",
                exit_time=f"2026-01-0{seq}T06:00:00Z",
                direction=direction,
                entry_price=entry,
                exit_price=exit_price,
                pnl=pnl,
                exit_reason="target",
            )
        )
    session.add(
        ResultManifestSnapshot(
            snapshot_id="rms_fd_1",
            result_id=_RESULT_ID,
            manifest_hash="a" * 64,
            execution_key="exec_fd_1",
            engine_version="backtest-engine-fd-test",
            manifest=dict(_MANIFEST_BODY),
        )
    )
    await session.commit()


async def _result_snapshot(session) -> dict[str, object]:
    """Read the whole result back OUT OF POSTGRES, not out of the identity map.

    ``expire_all`` is load-bearing: the integration session is built with
    ``expire_on_commit=False``, so without it every field below would be served
    from the objects this process already holds and a mutation that reached the
    database on another statement could still compare equal.
    """
    session.expire_all()
    row = await session.get(BacktestResult, _RESULT_ID)
    assert row is not None
    metrics = (
        (
            await session.execute(
                select(MetricValueRow)
                .where(MetricValueRow.result_id == _RESULT_ID)
                .order_by(MetricValueRow.position_index)
            )
        )
        .scalars()
        .all()
    )
    ledger = (
        (
            await session.execute(
                select(TradeLedgerRow)
                .where(TradeLedgerRow.result_id == _RESULT_ID)
                .order_by(TradeLedgerRow.seq)
            )
        )
        .scalars()
        .all()
    )
    manifest = (
        (
            await session.execute(
                select(ResultManifestSnapshot).where(ResultManifestSnapshot.result_id == _RESULT_ID)
            )
        )
        .scalars()
        .all()
    )
    return {
        "result_row": (
            row.result_id,
            row.run_id,
            row.manifest_id,
            row.manifest_hash,
            row.workspace_entity_id,
            row.composition_fingerprint,
            row.engine_version,
            row.deletion_state,
            row.row_version,
        ),
        "metrics": [
            (
                m.metric_value_id,
                m.metric_key,
                m.label,
                m.unit,
                m.value_format,
                None if m.value is None else str(m.value),
                str(m.availability),
                m.formula_version,
                m.position_index,
            )
            for m in metrics
        ],
        "ledger": [
            (
                t.trade_row_id,
                t.seq,
                t.entry_time,
                t.exit_time,
                t.direction,
                str(t.entry_price),
                None if t.exit_price is None else str(t.exit_price),
                None if t.pnl is None else str(t.pnl),
                t.exit_reason,
            )
            for t in ledger
        ],
        "manifest_snapshot": [
            (s.snapshot_id, s.manifest_hash, s.execution_key, s.engine_version, s.manifest)
            for s in manifest
        ],
    }


def _assert_dense(before: dict[str, object]) -> None:
    """Vacuity guard: "nothing changed" is free on an empty result."""
    assert len(before["metrics"]) == 3
    assert len(before["ledger"]) == 2
    assert before["manifest_snapshot"] and before["manifest_snapshot"][0][4] == _MANIFEST_BODY


async def test_view_dataset_never_writes_the_referenced_result(session) -> None:
    """FD-04.c4 — preparing a View Dataset from a REAL result ref leaves that
    result's manifest and result state exactly as they were."""
    await _seed(session)
    await _walk_to_limited(session, GRAPHIC_VIEW)
    await _seed_backtest_result(session)
    before = await _result_snapshot(session)
    _assert_dense(before)

    result = await query_view_dataset(
        session,
        USER,
        source_manifest_refs=[_RESULT_ID, "mkt_rev_9"],
        schema_version="v1",
        idempotency_key="vds-immutable",
    )
    await session.commit()

    # The command really landed — otherwise "nothing moved" also holds for a
    # call that did nothing at all.
    dataset = await session.get(ViewDataset, result["view_dataset_id"])
    assert dataset is not None
    assert dataset.source_manifest_refs == [_RESULT_ID, "mkt_rev_9"]

    after = await _result_snapshot(session)
    # Two independent axes of the same clause: a defect can move the result's
    # own state without touching the pinned manifest copy, and vice versa.
    assert after["result_row"] == before["result_row"]
    assert after["manifest_snapshot"] == before["manifest_snapshot"]


async def test_analysis_artifact_never_writes_the_referenced_result(session) -> None:
    """FD-05.c4 — creating the review artifact leaves the canonical metrics, the
    trade ledger and the original run manifest byte-identical."""
    await _seed(session)
    await _walk_to_limited(session, BACKTEST_REVIEW)
    await _seed_backtest_result(session)
    before = await _result_snapshot(session)
    _assert_dense(before)

    result = await create_analysis_artifact(
        session,
        AGENT,
        artifact_type="backtest_review",
        input_manifest_refs=[_RESULT_ID],
        method_version="review-v1",
        idempotency_key="aart-immutable",
    )
    await session.commit()

    artifact = await session.get(AnalysisArtifact, result["artifact_id"])
    assert artifact is not None
    assert artifact.input_manifest_refs == [_RESULT_ID]

    after = await _result_snapshot(session)
    # Three separately breakable axes. Comparing the full row tuples (not counts)
    # catches an overwrite; comparing the lists (not just their heads) catches an
    # appended metric or trade row, which an overwrite check would miss.
    assert after["metrics"] == before["metrics"]
    assert after["ledger"] == before["ledger"]
    assert after["manifest_snapshot"] == before["manifest_snapshot"]
    assert after["result_row"] == before["result_row"]
