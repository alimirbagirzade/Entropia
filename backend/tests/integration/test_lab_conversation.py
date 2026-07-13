"""Lab Conversation read surface (doc 18 §3.2, §9).

Wires the previously-orphan ``lab_message`` write path (``record_discussion_message``
only WROTE the append-only conversation log; nothing read it back) into a
role-gated, keyset read projection — the PR #144/#146 orphan-close pattern
(projection + gated GET, write path unchanged).

Admin/Supervisor may observe; a baseline User is denied; a missing ``task`` id is
reported as not-found (never a silent empty page); the page is task-scopable and
keyset-paged newest-first.

Auto-skips without PostgreSQL (the integration conftest builds the schema).
"""

from __future__ import annotations

import pytest

from entropia.application.commands import lab_message as msg
from entropia.application.queries import agent_workspace as ws
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
from entropia.shared.errors import AccessDeniedError, AgentTaskNotFoundError

pytestmark = pytest.mark.integration

ADMIN = Actor(principal_id="admin_1", principal_type=PrincipalType.HUMAN, role=Role.ADMIN)
SUPERVISOR = Actor(principal_id="sup_1", principal_type=PrincipalType.HUMAN, role=Role.SUPERVISOR)
USER = Actor(principal_id="user_1", principal_type=PrincipalType.HUMAN, role=Role.USER)


async def _seed(session) -> None:
    for pid in ("admin_1", "sup_1", "user_1"):
        session.add(Principal(principal_id=pid, principal_type=PrincipalType.HUMAN))
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
        title="Momentum research",
        source="human_directive",
        priority=AgentTaskPriority.NORMAL,
        status=AgentTaskStatus.RUNNING,
    )


# --------------------------------------------------------------------------- #
# List — the conversation the write path persisted
# --------------------------------------------------------------------------- #


async def test_list_lab_messages_surfaces_persisted_conversation(session) -> None:
    await _seed(session)
    await msg.record_discussion_message(session, ADMIN, text="Which revisions are pinned?")

    page = await ws.list_lab_messages(session, ADMIN)

    rows = page["messages"]
    # Each discussion records the human MESSAGE + the assistant ASSISTANT reply.
    assert [r["type"] for r in rows] == ["assistant", "message"]  # newest-first
    assert rows[1]["text"] == "Which revisions are pinned?"
    assert rows[1]["author_principal_id"] == "admin_1"
    assert rows[0]["author_principal_id"] is None  # the assistant is system-authored
    assert rows[0]["created_at"] is not None
    assert page["next_cursor"] is None


async def test_list_lab_messages_is_newest_first(session) -> None:
    await _seed(session)
    await msg.record_discussion_message(session, ADMIN, text="first")
    await msg.record_discussion_message(session, ADMIN, text="second")

    rows = (await ws.list_lab_messages(session, ADMIN))["messages"]

    ids = [r["message_id"] for r in rows]
    assert ids == sorted(ids, reverse=True)  # sortable id => newest-first
    human = [r["text"] for r in rows if r["type"] == "message"]
    assert human == ["second", "first"]  # latest human message leads


async def test_list_lab_messages_task_scoped(session) -> None:
    await _seed(session)
    task = await _seed_task(session)
    await msg.record_discussion_message(session, ADMIN, text="global note")
    await msg.record_discussion_message(
        session, ADMIN, text="task note", related_task_id=task.task_id
    )

    scoped = await ws.list_lab_messages(session, ADMIN, task_id=task.task_id)

    rows = scoped["messages"]
    assert {r["task_id"] for r in rows} == {task.task_id}
    assert {r["text"] for r in rows} == {"task note", _assistant_text(rows)}
    # The global thread is not leaked into the task-scoped page.
    assert all(r["text"] != "global note" for r in rows)


def _assistant_text(rows) -> str:
    return next(r["text"] for r in rows if r["type"] == "assistant")


async def test_list_lab_messages_unknown_task_is_not_found(session) -> None:
    await _seed(session)
    with pytest.raises(AgentTaskNotFoundError):
        await ws.list_lab_messages(session, ADMIN, task_id="agttask_missing")


async def test_list_lab_messages_denies_baseline_user(session) -> None:
    await _seed(session)
    await msg.record_discussion_message(session, ADMIN, text="secret research")
    with pytest.raises(AccessDeniedError):
        await ws.list_lab_messages(session, USER)


async def test_list_lab_messages_keyset_pages_without_overlap(session) -> None:
    await _seed(session)
    # 3 discussions => 6 append-only rows (message + assistant each).
    for i in range(3):
        await msg.record_discussion_message(session, SUPERVISOR, text=f"msg-{i}")

    first = await ws.list_lab_messages(session, SUPERVISOR, limit=2)
    assert len(first["messages"]) == 2
    assert first["next_cursor"] is not None

    second = await ws.list_lab_messages(session, SUPERVISOR, limit=2, cursor=first["next_cursor"])
    assert len(second["messages"]) == 2

    first_ids = {r["message_id"] for r in first["messages"]}
    second_ids = {r["message_id"] for r in second["messages"]}
    assert first_ids.isdisjoint(second_ids)
    # Keyset strictly descends across the page boundary.
    assert min(first_ids) > max(second_ids)
