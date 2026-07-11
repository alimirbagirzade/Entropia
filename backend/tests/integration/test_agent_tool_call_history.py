"""Agent Tool Gateway call-history read surface (doc 18 §7, §9.2, §14).

Wires the previously-orphan ``agent_tool_gateway`` repo reads
(``list_tool_calls`` / ``get_tool_call``) into role-gated query projections. The
WRITE path (``dispatch_tool_call``) stays fully gated; these tests exercise the
new READ side: Admin/Supervisor may observe, a baseline User is denied, and a
missing task / tool-call id is reported as not-found (never a silent empty page).

Auto-skips without PostgreSQL (the integration conftest builds the schema).
"""

from __future__ import annotations

import pytest

from entropia.application.jobs import agent_tools
from entropia.application.queries import agent_tool_gateway as tool_gateway_query
from entropia.domain.agent_lab.enums import (
    ALPHA_AGENT_ID,
    AgentTaskPriority,
    AgentTaskStatus,
    RuntimeMode,
    RuntimeStatus,
)
from entropia.domain.identity import Actor
from entropia.domain.lifecycle.enums import PrincipalType, Role
from entropia.infrastructure.postgres.models import AgentRuntime, Principal
from entropia.infrastructure.postgres.repositories import agent_lab as al_repo
from entropia.shared.errors import (
    AccessDeniedError,
    AgentTaskNotFoundError,
    AgentToolCallNotFoundError,
)

pytestmark = pytest.mark.integration

_AGENT_PID = "agent_alpha"
AGENT = Actor(
    principal_id=_AGENT_PID,
    principal_type=PrincipalType.AGENT,
    role=None,
    correlation_id="corr_ag",
)
ADMIN = Actor(
    principal_id="admin_1",
    principal_type=PrincipalType.HUMAN,
    role=Role.ADMIN,
    correlation_id="corr_admin",
)
SUPERVISOR = Actor(
    principal_id="sup_1",
    principal_type=PrincipalType.HUMAN,
    role=Role.SUPERVISOR,
    correlation_id="corr_sup",
)
USER = Actor(
    principal_id="user_1",
    principal_type=PrincipalType.HUMAN,
    role=Role.USER,
    correlation_id="corr_user",
)


async def _seed(session) -> None:
    session.add(Principal(principal_id=_AGENT_PID, principal_type=PrincipalType.AGENT))
    session.add(
        AgentRuntime(
            agent_id=ALPHA_AGENT_ID,
            mode=RuntimeMode.CONTINUOUS,
            status=RuntimeStatus.ACTIVE,
            row_version=1,
        )
    )
    await session.flush()


async def _seed_task(session):
    return await al_repo.create_task(
        session,
        agent_id=ALPHA_AGENT_ID,
        task_type="research",
        title="Active research",
        source="autonomous",
        priority=AgentTaskPriority.AUTONOMOUS,
        status=AgentTaskStatus.RUNNING,
    )


async def _dispatch(session, task_id: str, key: str) -> str:
    result = await agent_tools.dispatch_tool_call(
        session,
        AGENT,
        tool_name="artifact.create",
        policy_scope="research",
        task_id=task_id,
        checkpoint_id="ckpt_x",
        input_manifest_id="man_x",
        idempotency_key=key,
        request={"title": f"Edge {key}", "mechanism": "carry"},
    )
    return result["tool_call_id"]


# --------------------------------------------------------------------------- #
# List — task-scoped observability
# --------------------------------------------------------------------------- #


async def test_list_task_tool_calls_returns_task_calls(session) -> None:
    await _seed(session)
    task = await _seed_task(session)
    id_a = await _dispatch(session, task.task_id, "key_a")
    id_b = await _dispatch(session, task.task_id, "key_b")

    page = await tool_gateway_query.list_task_tool_calls(session, ADMIN, task_id=task.task_id)

    rows = page["tool_calls"]
    assert {r["tool_call_id"] for r in rows} == {id_a, id_b}
    sample = rows[0]
    assert sample["tool_name"] == "artifact.create"
    assert sample["task_id"] == task.task_id
    assert sample["status"] == "succeeded"
    # Summary rows never carry the payload bodies — those live on the detail read.
    assert "request" not in sample
    assert "response_ref" not in sample


async def test_list_task_tool_calls_honours_limit(session) -> None:
    await _seed(session)
    task = await _seed_task(session)
    for i in range(3):
        await _dispatch(session, task.task_id, f"key_{i}")

    page = await tool_gateway_query.list_task_tool_calls(
        session, SUPERVISOR, task_id=task.task_id, limit=2
    )

    assert len(page["tool_calls"]) == 2


async def test_list_task_tool_calls_unknown_task_is_not_found(session) -> None:
    await _seed(session)
    with pytest.raises(AgentTaskNotFoundError):
        await tool_gateway_query.list_task_tool_calls(session, ADMIN, task_id="task_missing")


async def test_list_task_tool_calls_denies_baseline_user(session) -> None:
    await _seed(session)
    task = await _seed_task(session)
    await _dispatch(session, task.task_id, "key_a")
    with pytest.raises(AccessDeniedError):
        await tool_gateway_query.list_task_tool_calls(session, USER, task_id=task.task_id)


# --------------------------------------------------------------------------- #
# Detail — full record
# --------------------------------------------------------------------------- #


async def test_get_tool_call_detail_carries_payload(session) -> None:
    await _seed(session)
    task = await _seed_task(session)
    call_id = await _dispatch(session, task.task_id, "key_a")

    detail = await tool_gateway_query.get_tool_call(session, ADMIN, tool_call_id=call_id)

    assert detail["tool_call_id"] == call_id
    assert detail["agent_id"] == ALPHA_AGENT_ID
    assert detail["actor_principal_id"] == _AGENT_PID
    assert detail["input_manifest_id"] == "man_x"
    assert detail["request"] == {"title": "Edge key_a", "mechanism": "carry"}
    # A succeeded call records its terminal outcome verbatim.
    assert detail["response_ref"] is not None


async def test_get_tool_call_unknown_is_not_found(session) -> None:
    await _seed(session)
    with pytest.raises(AgentToolCallNotFoundError):
        await tool_gateway_query.get_tool_call(session, ADMIN, tool_call_id="tc_missing")


async def test_get_tool_call_denies_baseline_user(session) -> None:
    await _seed(session)
    task = await _seed_task(session)
    call_id = await _dispatch(session, task.task_id, "key_a")
    with pytest.raises(AccessDeniedError):
        await tool_gateway_query.get_tool_call(session, USER, tool_call_id=call_id)
