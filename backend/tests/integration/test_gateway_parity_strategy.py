"""Post-V1 S5 — Tool Gateway parity for the Strategy line (doc 02 §12 AT-21).

Auto-skips without PostgreSQL. Mirrors the Stage 8a / S4 parity pattern
(``test_gateway_parity.py``, ``test_gateway_parity_s4.py``): the Agent's UI-less
``strategy.*`` tools delegate to the SAME application command/query line a human
uses, so the server truth on success and the machine code on refusal must be
IDENTICAL on both lines — with no browser, no human session and no Mainboard
side effect.

This file closes the LITERAL clause of AT-21 ("Agent Tool Gateway creates/
validates/saves Strategy revision using same schema, policy, idempotency and
audit as UI; no browser needed"), which `test_acceptance_agent_parity_gaps.py`
could previously only prove on the domain-command axis.

Covered:
- registry/scope contract: the five literals parse, their allowed scopes are
  exactly the declared table, an unknown name is refused, an illegal scope is a
  recorded REJECTED call, and the plan-time exposure offers all five;
- full Gateway chain: create -> get -> patch -> validate -> save, every call
  SUCCEEDED, the immutable revision persisted with pinned references;
- config_hash parity: the Agent's revision hash equals the human's for the same
  payload, while owner/created_by stay the AGENT principal (never the runtime id);
- ownership: get/patch/save against a HUMAN's private draft is a recorded
  REJECTED denial carrying the same code the human command line raises, and
  mutates nothing;
- stale OCC + compiler blockers: a durable FAILED call with the human line's own
  code (STRATEGY_DRAFT_CONFLICT / the compiler's typed 422), never a crash;
- malformed request: missing/blank id, non-integer OCC token, non-object payload
  -> durable FAILED ``AGENT_TOOL_REQUEST_INVALID``, no command executed;
- idempotency: gateway-key replay and domain-key replay both refuse to append a
  second revision; same key + different payload is a recorded conflict;
- Mainboard containment: neither the human's nor the Agent's board gains an item;
- durability: the same envelope through ``enqueue_tool_call`` -> ``run_tool_job``
  writes audit + outbox + agent events, and a redelivery replays it verbatim.
"""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import func, select

from entropia.application.commands import strategy_draft as strat_cmd
from entropia.application.jobs import agent_tools
from entropia.application.queries import agent_tool_gateway as tool_gateway_query
from entropia.application.queries import mainboard as mb_query
from entropia.application.queries import strategy as strat_query
from entropia.domain.agent_lab.enums import (
    ALPHA_AGENT_ID,
    AgentTaskPriority,
    AgentTaskStatus,
    RuntimeMode,
    RuntimeStatus,
)
from entropia.domain.agent_lab.tool_gateway import (
    TOOL_ALLOWED_SCOPES,
    PolicyScope,
    exposed_tool_names,
    parse_tool_name,
    queue_for_tool,
)
from entropia.domain.identity import Actor
from entropia.domain.lifecycle.enums import DeletionState, PrincipalType, Role
from entropia.infrastructure.postgres.models import (
    AgentEvent,
    AgentRuntime,
    AgentToolCall,
    AuditEvent,
    EntityRegistry,
    IdempotencyKey,
    OutboxEvent,
    Principal,
    RationaleFamilyRoot,
    StrategyEditorDraft,
    StrategyRevision,
    StrategyRevisionReference,
)
from entropia.infrastructure.postgres.repositories import agent_lab as al_repo
from entropia.shared.errors import AppError, ToolPolicyScopeError
from tests.integration.test_strategy_integration import _valid_payload

pytestmark = pytest.mark.integration

_HUMAN_PID = "user_1"
_AGENT_PID = "agent_alpha"
_FAMILY_ID = "ratfam_s5_parity"

HUMAN = Actor(principal_id=_HUMAN_PID, principal_type=PrincipalType.HUMAN, role=Role.USER)
ADMIN = Actor(principal_id="admin_1", principal_type=PrincipalType.HUMAN, role=Role.ADMIN)
AGENT = Actor(
    principal_id=_AGENT_PID,
    principal_type=PrincipalType.AGENT,
    role=None,
    correlation_id="corr_s5_parity",
)

_STRATEGY_TOOLS = (
    "strategy.get_draft",
    "strategy.create_draft",
    "strategy.patch_draft",
    "strategy.validate_draft",
    "strategy.save_revision",
)


# --------------------------------------------------------------------------- #
# Fixtures / helpers                                                           #
# --------------------------------------------------------------------------- #


async def _seed(session) -> None:
    for pid, ptype in ((_HUMAN_PID, PrincipalType.HUMAN), (_AGENT_PID, PrincipalType.AGENT)):
        if await session.get(Principal, pid) is None:
            session.add(Principal(principal_id=pid, principal_type=ptype))
    # The durable tool-call row FKs to agent_runtime(agent_id); the default tool
    # agent_id is ALPHA_AGENT_ID, so its runtime must exist.
    if await session.get(AgentRuntime, ALPHA_AGENT_ID) is None:
        session.add(
            AgentRuntime(
                agent_id=ALPHA_AGENT_ID,
                mode=RuntimeMode.CONTINUOUS,
                status=RuntimeStatus.ACTIVE,
                row_version=1,
            )
        )
    if await session.get(RationaleFamilyRoot, _FAMILY_ID) is None:
        session.add(
            EntityRegistry(
                entity_id=_FAMILY_ID,
                entity_type="rationale_family",
                owner_principal_id=_HUMAN_PID,
                created_by_principal_id=_HUMAN_PID,
                deletion_state=DeletionState.ACTIVE,
                row_version=1,
            )
        )
        await session.flush()
        session.add(RationaleFamilyRoot(entity_id=_FAMILY_ID, display_color="#00a9e8"))
    await session.flush()


async def _count(session, model) -> int:
    return int((await session.execute(select(func.count()).select_from(model))).scalar_one())


async def _tool(session, name: str, scope: str, request: dict[str, Any], **kwargs: Any):
    """One gateway call + commit, exactly as the worker scope would."""
    result = await agent_tools.dispatch_tool_call(
        session, AGENT, tool_name=name, policy_scope=scope, request=request, **kwargs
    )
    await session.commit()
    return result


async def _agent_draft(session, *, display_name: str = "Agent parity strategy") -> dict[str, Any]:
    """create_draft via the Gateway (the Agent never touches the command directly)."""
    return await _tool(
        session,
        "strategy.create_draft",
        "proposal",
        {
            "display_name": display_name,
            "rationale_family_id": _FAMILY_ID,
            "initial_payload": _valid_payload(display_name),
        },
    )


async def _human_draft(session, *, display_name: str = "Human strategy") -> dict[str, Any]:
    draft = await strat_cmd.create_strategy_draft(
        session,
        HUMAN,
        display_name=display_name,
        rationale_family_id=_FAMILY_ID,
        initial_payload=_valid_payload(display_name),
    )
    await session.commit()
    return draft


# --------------------------------------------------------------------------- #
# Registry + scope contract (doc 18 §9.2, §10)                                 #
# --------------------------------------------------------------------------- #


def test_strategy_tool_names_parse_and_declare_their_scopes() -> None:
    """The five literals AT-21 needs exist, with exactly the declared scope table."""
    expected = {
        "strategy.get_draft": {PolicyScope.OBSERVATION, PolicyScope.RESEARCH},
        "strategy.create_draft": {PolicyScope.RESEARCH, PolicyScope.PROPOSAL},
        "strategy.patch_draft": {PolicyScope.RESEARCH, PolicyScope.PROPOSAL},
        "strategy.validate_draft": {PolicyScope.RESEARCH, PolicyScope.PROPOSAL},
        "strategy.save_revision": {PolicyScope.PROPOSAL},
    }
    for literal, scopes in expected.items():
        tool = parse_tool_name(literal)
        assert TOOL_ALLOWED_SCOPES[tool] == frozenset(scopes)
        # Hypothesis-shaping work is never EXECUTION, so none of them takes the
        # heavy agent-high plane away from real runs.
        assert PolicyScope.EXECUTION not in TOOL_ALLOWED_SCOPES[tool]
        assert queue_for_tool(tool) == "agent"

    with pytest.raises(ToolPolicyScopeError):
        parse_tool_name("strategy.publish_revision")
    # Doc 18 §10's prose spelling is NOT the registry (see the ToolName docstring).
    with pytest.raises(ToolPolicyScopeError):
        parse_tool_name("strategy.draft.create")


def test_strategy_tools_are_offered_at_plan_time() -> None:
    """CR-08 exposure: ungated tools are offered even with no operational
    capability, so the Coordinator can plan the Strategy line (doc 22 §11)."""
    exposed = exposed_tool_names(frozenset())
    for literal in _STRATEGY_TOOLS:
        assert literal in exposed


async def test_illegal_scope_is_a_recorded_rejection(session) -> None:
    """A save under EXECUTION is a governance denial, durably recorded (AL-11)."""
    await _seed(session)
    result = await _tool(
        session, "strategy.save_revision", "execution", {"draft_id": "does-not-matter"}
    )

    assert result["status"] == "rejected"
    assert result["reason_code"] == "AGENT_TOOL_SCOPE_FORBIDDEN"
    call = await session.get(AgentToolCall, result["tool_call_id"])
    assert call is not None and call.failure_code == "AGENT_TOOL_SCOPE_FORBIDDEN"
    assert await _count(session, StrategyEditorDraft) == 0


# --------------------------------------------------------------------------- #
# The AT-21 chain: create -> get -> patch -> validate -> save                   #
# --------------------------------------------------------------------------- #


async def test_full_strategy_chain_through_the_gateway(session) -> None:
    """AT-21 literal: the Agent drives the whole editor line UI-lessly."""
    await _seed(session)

    created = await _agent_draft(session)
    assert created["status"] == "succeeded"
    draft_id = created["draft_id"]

    fetched = await _tool(session, "strategy.get_draft", "observation", {"draft_id": draft_id})
    assert fetched["status"] == "succeeded"
    assert fetched["row_version"] == created["row_version"]
    assert fetched["payload"]["display_name"] == "Agent parity strategy"
    assert fetched["last_saved_revision_id"] is None  # unsaved draft: no revision yet

    patched = await _tool(
        session,
        "strategy.patch_draft",
        "research",
        {
            "draft_id": draft_id,
            "expected_draft_row_version": fetched["row_version"],
            "patch": {"display_name": "Agent parity strategy v2"},
        },
    )
    assert patched["status"] == "succeeded"
    assert patched["row_version"] == fetched["row_version"] + 1
    assert patched["is_dirty"] is True

    validated = await _tool(session, "strategy.validate_draft", "research", {"draft_id": draft_id})
    assert validated["status"] == "succeeded"
    assert validated["valid"] is True and validated["issues"] == []

    saved = await _tool(
        session,
        "strategy.save_revision",
        "proposal",
        {"draft_id": draft_id, "expected_draft_row_version": patched["row_version"]},
    )
    assert saved["status"] == "succeeded"
    assert saved["revision_number"] == 1
    # Save is never a Ready PASS and never a Run (doc 02 §7.1).
    assert saved["ready_state"] == "STALE"

    revision = await session.get(StrategyRevision, saved["strategy_revision_id"])
    assert revision is not None
    assert revision.config_hash == saved["config_hash"]
    assert await _count(session, StrategyRevisionReference) > 0  # pinned dependencies

    # The envelope's artifact_output_ref points at the immutable revision.
    call = await session.get(AgentToolCall, saved["tool_call_id"])
    assert call is not None
    assert call.artifact_output_ref == saved["strategy_revision_id"]
    assert str(call.status) == "succeeded"


async def test_agent_and_human_lines_produce_the_same_config_hash(session) -> None:
    """Same payload, two callers, one compile line — and provenance still separates
    them: the Agent's root/revision belong to the AGENT PRINCIPAL, never to the
    runtime id (``alpha-agent``), which only labels the tool-call envelope."""
    await _seed(session)

    human_draft = await _human_draft(session, display_name="Shared payload")
    human_saved = await strat_cmd.save_strategy_revision(
        session,
        HUMAN,
        draft_id=human_draft["draft_id"],
        expected_draft_row_version=human_draft["row_version"],
    )
    await session.commit()

    created = await _agent_draft(session, display_name="Shared payload")
    agent_saved = await _tool(
        session,
        "strategy.save_revision",
        "proposal",
        {
            "draft_id": created["draft_id"],
            "expected_draft_row_version": created["row_version"],
        },
    )

    assert agent_saved["config_hash"] == human_saved["config_hash"]
    assert agent_saved["revision_number"] == human_saved["revision_number"] == 1
    assert await _count(session, StrategyRevision) == 2

    revision = await session.get(StrategyRevision, agent_saved["strategy_revision_id"])
    root = await session.get(EntityRegistry, agent_saved["strategy_root_id"])
    assert revision is not None and root is not None
    assert revision.created_by_principal == _AGENT_PID
    assert root.owner_principal_id == root.created_by_principal_id == _AGENT_PID
    assert root.owner_principal_id != ALPHA_AGENT_ID

    call = await session.get(AgentToolCall, agent_saved["tool_call_id"])
    assert call is not None
    assert call.agent_id == ALPHA_AGENT_ID  # runtime identity
    assert call.actor_principal_id == _AGENT_PID  # principal identity — never merged


# --------------------------------------------------------------------------- #
# Ownership — the Agent never reaches a human's private draft                   #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("tool_name", "scope", "extra"),
    [
        ("strategy.get_draft", "observation", {}),
        ("strategy.patch_draft", "research", {"patch": {"display_name": "hijacked"}}),
        ("strategy.save_revision", "proposal", {}),
    ],
)
async def test_human_private_draft_is_a_recorded_denial(
    session, tool_name: str, scope: str, extra: dict[str, Any]
) -> None:
    """Same typed code on both lines, zero side effects on the Agent's line."""
    await _seed(session)
    human_draft = await _human_draft(session)

    # Human command line: the SAME actor calling the command directly is refused.
    with pytest.raises(AppError) as exc_info:
        await strat_cmd.save_strategy_revision(
            session,
            AGENT,
            draft_id=human_draft["draft_id"],
            expected_draft_row_version=human_draft["row_version"],
        )
    await session.rollback()
    human_line_code = exc_info.value.code

    request = {
        "draft_id": human_draft["draft_id"],
        "expected_draft_row_version": human_draft["row_version"],
        **extra,
    }
    via_tool = await _tool(session, tool_name, scope, request)

    assert via_tool["status"] == "rejected"
    assert via_tool["reason_code"] == human_line_code == "ACCESS_DENIED"
    call = await session.get(AgentToolCall, via_tool["tool_call_id"])
    assert call is not None and call.failure_code == human_line_code

    # Nothing moved: no revision, and the human's draft keeps its own version/name.
    assert await _count(session, StrategyRevision) == 0
    draft_row = await session.get(StrategyEditorDraft, human_draft["draft_id"])
    assert draft_row is not None
    assert draft_row.row_version == human_draft["row_version"]
    assert draft_row.payload["display_name"] == "Human strategy"


# --------------------------------------------------------------------------- #
# Stale OCC + compiler blockers -> durable FAILED (never a worker crash)        #
# --------------------------------------------------------------------------- #


async def test_stale_occ_token_is_a_durable_failed_call(session) -> None:
    """A stale ``expected_draft_row_version`` carries the human line's own code and
    leaves durable evidence instead of escaping into a dramatiq retry loop."""
    await _seed(session)
    created = await _agent_draft(session)
    stale_version = created["row_version"] - 1

    with pytest.raises(AppError) as exc_info:
        await strat_cmd.patch_strategy_draft(
            session,
            AGENT,
            draft_id=created["draft_id"],
            expected_draft_row_version=stale_version,
            patch={"display_name": "stale"},
        )
    await session.rollback()
    human_line_code = exc_info.value.code

    via_tool = await _tool(
        session,
        "strategy.patch_draft",
        "research",
        {
            "draft_id": created["draft_id"],
            "expected_draft_row_version": stale_version,
            "patch": {"display_name": "stale"},
        },
    )

    assert via_tool["status"] == "failed"
    assert via_tool["failure_code"] == human_line_code == "STRATEGY_DRAFT_CONFLICT"
    call = await session.get(AgentToolCall, via_tool["tool_call_id"])
    assert call is not None
    assert str(call.status) == "failed" and call.failure_code == human_line_code

    draft_row = await session.get(StrategyEditorDraft, created["draft_id"])
    assert draft_row is not None
    assert draft_row.row_version == created["row_version"]  # never last-write-wins


async def test_compiler_blockers_fail_the_save_on_both_lines(session) -> None:
    """A draft the compiler refuses produces the SAME typed code on both lines and
    appends NO revision — validate_draft reports it first, without mutating."""
    await _seed(session)
    created = await _tool(
        session,
        "strategy.create_draft",
        "research",
        {
            "display_name": "Incomplete strategy",
            "rationale_family_id": _FAMILY_ID,
            "initial_payload": {"display_name": "Incomplete strategy"},
        },
    )

    validated = await _tool(
        session, "strategy.validate_draft", "research", {"draft_id": created["draft_id"]}
    )
    assert validated["status"] == "succeeded"
    assert validated["valid"] is False and validated["issues"]

    with pytest.raises(AppError) as exc_info:
        await strat_cmd.save_strategy_revision(
            session,
            AGENT,
            draft_id=created["draft_id"],
            expected_draft_row_version=created["row_version"],
        )
    await session.rollback()
    human_line_code = exc_info.value.code

    via_tool = await _tool(
        session,
        "strategy.save_revision",
        "proposal",
        {
            "draft_id": created["draft_id"],
            "expected_draft_row_version": created["row_version"],
        },
    )

    assert via_tool["status"] == "failed"
    assert via_tool["failure_code"] == human_line_code
    assert via_tool["details"]  # the compiler issue list rides along for planning
    assert await _count(session, StrategyRevision) == 0


# --------------------------------------------------------------------------- #
# Malformed request -> durable FAILED, no command executed                     #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("tool_name", "scope", "tool_request"),
    [
        ("strategy.get_draft", "observation", {}),
        ("strategy.get_draft", "observation", {"draft_id": "   "}),
        ("strategy.create_draft", "research", {"display_name": 42}),
        (
            "strategy.patch_draft",
            "research",
            {"draft_id": "d1", "expected_draft_row_version": "1"},
        ),
        (
            "strategy.patch_draft",
            "research",
            {"draft_id": "d1", "expected_draft_row_version": True},
        ),
        (
            "strategy.save_revision",
            "proposal",
            {"draft_id": "d1", "expected_draft_row_version": None},
        ),
        (
            "strategy.create_draft",
            "research",
            {"display_name": "x", "initial_payload": "not-an-object"},
        ),
    ],
)
async def test_malformed_request_is_a_durable_failed_call(
    session, tool_name: str, scope: str, tool_request: dict[str, Any]
) -> None:
    """Strict request validation at the tool-call edge: the call is recorded, the
    worker does not crash, and no command ever ran."""
    await _seed(session)
    result = await _tool(session, tool_name, scope, tool_request)

    assert result["status"] == "failed"
    assert result["failure_code"] == "AGENT_TOOL_REQUEST_INVALID"
    call = await session.get(AgentToolCall, result["tool_call_id"])
    assert call is not None and str(call.status) == "failed"
    assert call.response_ref["failure_code"] == "AGENT_TOOL_REQUEST_INVALID"
    assert await _count(session, StrategyEditorDraft) == 0
    assert await _count(session, StrategyRevision) == 0


# --------------------------------------------------------------------------- #
# Idempotency — gateway key AND domain key                                     #
# --------------------------------------------------------------------------- #


async def test_gateway_key_replay_returns_the_recorded_outcome(session) -> None:
    """AL-14: a redelivered gateway key never re-executes the tool."""
    await _seed(session)
    created = await _agent_draft(session)

    first = await _tool(
        session,
        "strategy.save_revision",
        "proposal",
        {
            "draft_id": created["draft_id"],
            "expected_draft_row_version": created["row_version"],
        },
        idempotency_key="s5-save-1",
    )
    replay = await _tool(
        session,
        "strategy.save_revision",
        "proposal",
        {
            "draft_id": created["draft_id"],
            "expected_draft_row_version": created["row_version"],
        },
        idempotency_key="s5-save-1",
    )

    assert replay["replayed"] is True
    assert replay["tool_call_id"] == first["tool_call_id"]
    assert replay["strategy_revision_id"] == first["strategy_revision_id"]
    assert await _count(session, StrategyRevision) == 1
    assert await _count(session, AgentToolCall) == 2  # create_draft + the one save


async def test_domain_key_replay_appends_no_second_revision(session) -> None:
    """The command's own Idempotency-Key contract holds through the Gateway: two
    DIFFERENT tool calls carrying the same domain key yield one revision."""
    await _seed(session)
    created = await _agent_draft(session)
    request = {
        "draft_id": created["draft_id"],
        "expected_draft_row_version": created["row_version"],
        "idempotency_key": "domain-save-1",
    }

    first = await _tool(session, "strategy.save_revision", "proposal", request)
    replay = await _tool(session, "strategy.save_revision", "proposal", dict(request))

    assert first["status"] == replay["status"] == "succeeded"
    assert replay["tool_call_id"] != first["tool_call_id"]  # two distinct tool calls
    assert replay["strategy_revision_id"] == first["strategy_revision_id"]
    assert await _count(session, StrategyRevision) == 1


async def test_same_domain_key_with_a_different_payload_is_a_recorded_conflict(session) -> None:
    """Key reuse under a different request is the human line's 409, recorded."""
    await _seed(session)
    first_draft = await _agent_draft(session, display_name="Key owner")
    await _tool(
        session,
        "strategy.save_revision",
        "proposal",
        {
            "draft_id": first_draft["draft_id"],
            "expected_draft_row_version": first_draft["row_version"],
            "idempotency_key": "reused-key",
        },
    )
    second_draft = await _agent_draft(session, display_name="Key thief")

    via_tool = await _tool(
        session,
        "strategy.save_revision",
        "proposal",
        {
            "draft_id": second_draft["draft_id"],
            "expected_draft_row_version": second_draft["row_version"],
            "idempotency_key": "reused-key",
        },
    )

    assert via_tool["status"] == "failed"
    assert via_tool["failure_code"] == "IDEMPOTENCY_KEY_CONFLICT"
    assert await _count(session, StrategyRevision) == 1  # the second save never ran


# --------------------------------------------------------------------------- #
# Mainboard containment — no auto-attach on either board                        #
# --------------------------------------------------------------------------- #


async def test_agent_strategy_work_never_touches_a_mainboard(session) -> None:
    """The Agent's own output is NOT auto-attached, and a human board is untouched
    (the strategy tools carry no workspace/attach parameter at all)."""
    await _seed(session)
    human_board = await mb_query.get_default_mainboard(session, HUMAN)
    await session.commit()
    assert human_board["items"] == []

    created = await _agent_draft(session)
    await _tool(
        session,
        "strategy.save_revision",
        "proposal",
        {
            "draft_id": created["draft_id"],
            "expected_draft_row_version": created["row_version"],
        },
    )

    human_after = await mb_query.get_default_mainboard(session, HUMAN)
    agent_after = await mb_query.get_default_mainboard(session, AGENT)
    await session.commit()
    assert human_after["items"] == []
    assert human_after["composition_hash"] == human_board["composition_hash"]
    assert agent_after["items"] == []  # the Agent's own board gains nothing either


# --------------------------------------------------------------------------- #
# Durability — enqueue -> run_tool_job -> audit/outbox/events, redelivery-safe  #
# --------------------------------------------------------------------------- #


async def test_durable_job_path_records_audit_outbox_and_replays_on_redelivery(session) -> None:
    """The worker's envelope: the same call through the durable job body writes the
    domain's audit + outbox rows and the gateway's agent events, and a redelivery
    (dramatiq at-least-once) replays the recorded outcome without a second write."""
    await _seed(session)
    created = await _agent_draft(session)

    job = agent_tools.enqueue_tool_call(
        session,
        AGENT,
        tool_name="strategy.save_revision",
        policy_scope="proposal",
        request={
            "draft_id": created["draft_id"],
            "expected_draft_row_version": created["row_version"],
        },
        idempotency_key="durable-save-1",
    )
    await session.commit()
    assert job.queue == "agent"

    result = await agent_tools.run_tool_job(session, job.job_id)
    await session.commit()
    assert result["status"] == "succeeded"
    revision_id = result["strategy_revision_id"]

    audit_count = (
        await session.execute(
            select(func.count())
            .select_from(AuditEvent)
            .where(
                AuditEvent.event_kind == "strategy.revision_created",
                AuditEvent.actor_principal_id == _AGENT_PID,
            )
        )
    ).scalar_one()
    assert audit_count == 1
    outbox_count = (
        await session.execute(
            select(func.count())
            .select_from(OutboxEvent)
            .where(OutboxEvent.event_type == "strategy.revision_created")
        )
    ).scalar_one()
    assert outbox_count == 1
    event_types = set((await session.execute(select(AgentEvent.type))).scalars().all())
    assert {"tool_call_started", "tool_call_succeeded", "strategy_revision_created"} <= event_types

    # Redelivery of the SAME job: the recorded outcome replays, nothing re-runs.
    replay = await agent_tools.run_tool_job(session, job.job_id)
    await session.commit()
    assert replay["replayed"] is True
    assert replay["strategy_revision_id"] == revision_id
    assert await _count(session, StrategyRevision) == 1

    # And the read model agrees with what the Agent was told.
    draft_view = await strat_query.get_strategy_draft(session, AGENT, created["draft_id"])
    assert draft_view["last_saved_revision_id"] == revision_id
    assert draft_view["is_dirty"] is False


# --------------------------------------------------------------------------- #
# Analysis Lab — the new family shows up in the governed call history           #
# --------------------------------------------------------------------------- #


async def test_strategy_calls_reach_the_analysis_lab_history(session) -> None:
    """Doc 18 §7/§9.2: the Lab is the human observation surface over the durable
    record. Both a SUCCEEDED and a FAILED strategy call must be visible there,
    with the literal tool name and the machine code — never a silent gap."""
    await _seed(session)
    task = await al_repo.create_task(
        session,
        agent_id=ALPHA_AGENT_ID,
        task_type="research",
        title="Strategy authoring",
        source="autonomous",
        priority=AgentTaskPriority.AUTONOMOUS,
        status=AgentTaskStatus.RUNNING,
    )
    await session.flush()

    created = await _tool(
        session,
        "strategy.create_draft",
        "proposal",
        {
            "display_name": "Lab-visible strategy",
            "rationale_family_id": _FAMILY_ID,
            "initial_payload": _valid_payload("Lab-visible strategy"),
        },
        task_id=task.task_id,
    )
    failed = await _tool(
        session,
        "strategy.patch_draft",
        "research",
        {
            "draft_id": created["draft_id"],
            "expected_draft_row_version": created["row_version"] - 1,
            "patch": {"display_name": "stale"},
        },
        task_id=task.task_id,
    )

    page = await tool_gateway_query.list_task_tool_calls(session, ADMIN, task_id=task.task_id)
    by_id = {row["tool_call_id"]: row for row in page["tool_calls"]}
    assert by_id[created["tool_call_id"]]["tool_name"] == "strategy.create_draft"
    assert by_id[created["tool_call_id"]]["status"] == "succeeded"
    assert by_id[failed["tool_call_id"]]["tool_name"] == "strategy.patch_draft"
    assert by_id[failed["tool_call_id"]]["status"] == "failed"
    assert by_id[failed["tool_call_id"]]["failure_code"] == "STRATEGY_DRAFT_CONFLICT"

    detail = await tool_gateway_query.get_tool_call(
        session, ADMIN, tool_call_id=failed["tool_call_id"]
    )
    assert detail["policy_scope"] == "research"
    assert detail["request"]["draft_id"] == created["draft_id"]
    assert detail["response_ref"]["failure_code"] == "STRATEGY_DRAFT_CONFLICT"


async def test_a_recorded_failure_rolls_back_everything_the_command_wrote(session) -> None:
    """The durable FAILED row must never ship half-done work.

    A command can flush rows and only then hit a typed failure; on this path there
    is no request scope to roll the transaction back, so the handler runs inside a
    SAVEPOINT. Observable proof: ``run_idempotent`` inserts its key row BEFORE
    calling the operation, so a failed save must leave NO ``idempotency_keys`` row
    — while the tool-call evidence, created outside the savepoint, survives.
    """
    await _seed(session)
    created = await _tool(
        session,
        "strategy.create_draft",
        "research",
        {
            "display_name": "Rollback probe",
            "rationale_family_id": _FAMILY_ID,
            "initial_payload": {"display_name": "Rollback probe"},
        },
    )

    via_tool = await _tool(
        session,
        "strategy.save_revision",
        "proposal",
        {
            "draft_id": created["draft_id"],
            "expected_draft_row_version": created["row_version"],
            "idempotency_key": "rolled-back-save",
        },
    )

    assert via_tool["status"] == "failed"
    keys = (
        await session.execute(
            select(func.count())
            .select_from(IdempotencyKey)
            .where(IdempotencyKey.key == "rolled-back-save")
        )
    ).scalar_one()
    assert keys == 0  # the command's own writes were rolled back to the savepoint
    assert await _count(session, StrategyRevision) == 0

    # ...and the evidence still exists, because the tool-call row predates the savepoint.
    call = await session.get(AgentToolCall, via_tool["tool_call_id"])
    assert call is not None and str(call.status) == "failed"
