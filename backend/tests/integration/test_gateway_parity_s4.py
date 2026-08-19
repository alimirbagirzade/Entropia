"""Post-V1 S4 — Tool Gateway parity for Allocation + Trade Log (doc 13 §9, doc 05 §11).

Auto-skips without PostgreSQL. Mirrors the Stage 8a parity pattern
(``test_gateway_parity.py``): the Agent's UI-less allocation/trade-log tools
delegate to the SAME application command/query line a human uses, so the server
truth on success and the typed denial code on refusal must be IDENTICAL on both
lines — and an ownership violation is a recorded REJECTED tool call with zero
side effects (doc 13 §14#17, doc 05 TL-22, AL-11).

Covered:
- allocation upsert parity: gateway ``portfolio_allocation.upsert_draft`` yields
  the same draft_fingerprint / enabled / row_version as the direct command for
  identical inputs; validate parity yields the same state / valid / config_hash;
- allocation read parity: gateway get_draft / sync_preview equal the direct query;
- allocation full chain via gateway: upsert -> validate -> create_revision all
  SUCCEEDED, an immutable revision persists with the domain config hash;
- allocation ownership denial: an Agent upsert on a foreign-owner composition is
  REJECTED with the SAME code the human command raises, and writes no plan;
- trade_log create -> revision via gateway: both SUCCEEDED, revision_no increments,
  the Mainboard item is never auto-repinned, config_hash == the domain compute;
- trade_log ownership denial: an Agent revision on a foreign-owner root is REJECTED
  with the SAME code the human command raises, and appends no revision;
- trade_log SUCCESS-path provenance: the durable AgentToolCall row is re-read and carries
  the terminal status, no failure code, and the owner / task / checkpoint it ran under;
- trade_log board isolation: the Agent's attach=True work lands on the Agent's OWN default
  board and leaves a human board's items, composition_hash and row_version untouched.
"""

from __future__ import annotations

import hashlib
from typing import Any

import pytest
from sqlalchemy import func, select

from entropia.application.commands import allocation_plan as alloc_cmd
from entropia.application.commands import mainboard as mb_cmd
from entropia.application.commands import trade_log as tl_cmd
from entropia.application.jobs import agent_tools
from entropia.application.jobs.trade_log import run_import
from entropia.application.queries import allocation_plan as alloc_query
from entropia.application.queries import mainboard as mb_query
from entropia.application.queries import trade_log as tl_query
from entropia.domain.agent_lab.enums import (
    ALPHA_AGENT_ID,
    AgentTaskPriority,
    AgentTaskStatus,
    RuntimeMode,
    RuntimeStatus,
)
from entropia.domain.agent_lab.tool_gateway import PolicyScope, ToolCallStatus, ToolName
from entropia.domain.identity import Actor
from entropia.domain.lifecycle.enums import ActorKind, PrincipalType, Role
from entropia.domain.trade_log.compiler import compute_config_hash, validate_trade_log_config
from entropia.infrastructure.postgres.models import (
    AgentRuntime,
    AgentToolCall,
    PortfolioAllocationPlan,
    PortfolioAllocationPlanRevision,
    Principal,
    WorkObjectRevision,
)
from entropia.infrastructure.postgres.repositories import agent_lab as lab_repo
from entropia.infrastructure.s3 import datasets
from entropia.shared.errors import AccessDeniedError, AllocationHasBlockersError

# ADIM 3: every ENABLED plan leads with the shared-capital containment blocker
# (domain/allocation/capability.py) on BOTH the human and the Agent line.
_CONTAINMENT_CODE = "SHARED_MODE_NOT_IN_BUILD"

pytestmark = pytest.mark.integration

_OWNER_PID = "user_1"
_AGENT_PID = "agent_alpha"
OWNER = Actor(principal_id=_OWNER_PID, principal_type=PrincipalType.HUMAN, role=Role.USER)
AGENT = Actor(
    principal_id=_AGENT_PID,
    principal_type=PrincipalType.AGENT,
    role=None,
    correlation_id="corr_s4_parity",
)

_INITIAL_CAPITAL = {"amount": "10000", "currency": "USDT"}
_COMPOUNDING = "COMPOUND_PORTFOLIO_EQUITY"

_HEADER = "direction,entry_time,entry_price,exit_time,exit_price,symbol"
_GOOD_CSV = "\n".join(
    [
        _HEADER,
        "Long,2024-01-01 10:00,42100,2024-01-01 15:30,42850,BTCUSDT",
        "Short,2024-01-02 09:15,43000,2024-01-02 18:00,41950,BTCUSDT",
    ]
).encode("utf-8")


@pytest.fixture
def fake_object_store(monkeypatch) -> dict[str, bytes]:
    """In-process object storage so upload + worker read run without MinIO."""
    store: dict[str, bytes] = {}

    def _put(source_asset_id: str, data: bytes, *, content_type: str | None = None):
        digest = hashlib.sha256(data).hexdigest()
        key = f"signals/source/{source_asset_id}/{digest}"
        store[key] = data
        return key, digest

    def _get(object_key: str) -> bytes:
        return store[object_key]

    monkeypatch.setattr(datasets, "put_source_asset_bytes", _put)
    monkeypatch.setattr(datasets, "get_raw_bytes", _get)
    return store


async def _seed(session) -> None:
    for pid, ptype in ((_OWNER_PID, PrincipalType.HUMAN), (_AGENT_PID, PrincipalType.AGENT)):
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
    await session.flush()


async def _composition(session, actor: Actor) -> str:
    return str((await mb_query.get_default_mainboard(session, actor))["workspace_id"])


async def _composition_with_items(session, actor: Actor, count: int = 3) -> tuple[str, list[str]]:
    workspace_id = await _composition(session, actor)
    for index in range(count):
        work_object = await mb_cmd.create_work_object(
            session, actor, object_kind="strategy", payload={"note": f"seed-{index}"}
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
    projection = await mb_query.get_default_mainboard(session, actor)
    return workspace_id, [item["item_id"] for item in projection["items"]]


def _entries(*pairs: tuple[str, str]) -> list[dict[str, Any]]:
    return [
        {"composition_item_id": cid, "active": True, "equity_share_percent": share}
        for cid, share in pairs
    ]


async def _count(session, model) -> int:
    return int((await session.execute(select(func.count()).select_from(model))).scalar_one())


def _tl_payload(
    source_asset_id: str, record_batch_revision_id: str, **overrides: Any
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "kind": "trade_log",
        "identity": {"display_name": "Binance BTCUSDT trade history Q1"},
        "source": {"provider_name": "Binance Futures export", "source_kind": "file"},
        "instrument_scope": {"instrument_id": "inst_btcusdt", "display_symbol": "BTCUSDT"},
        "time_model": {
            "resolution_kind": "event_based",
            "base_timeframe": None,
            "source_timezone": "UTC",
            "normalization_timezone": "UTC",
        },
        "classification": {"rationale_family_id": None},
        "data_quality": {"content_profile": "entry_exit_records_only"},
        "price_policy": {
            "source": "trade_log_entry_exit_price",
            "approved_market_data_revision_ref": None,
        },
        "ohlcv_policy": {"use_mode": "use_if_supplied_and_needed"},
        "capital": {"independent_initial_capital": "10000", "currency": "USDT"},
        "import_binding": {
            "source_asset_id": source_asset_id,
            "record_batch_revision_id": record_batch_revision_id,
        },
    }
    payload.update(overrides)
    return payload


async def _imported_batch(session, actor: Actor) -> tuple[str, str]:
    """Upload -> request import -> run worker. Returns (source_asset_id, batch_id)."""
    upload = await tl_cmd.upload_source_asset(
        session, actor, content=_GOOD_CSV, original_filename="trades.csv"
    )
    await session.commit()
    requested = await tl_cmd.request_trade_log_import(
        session, actor, source_asset_id=upload["source_asset_id"], instrument_id="BTCUSDT"
    )
    await session.commit()
    await run_import(session, requested["job_id"])
    await session.commit()
    report = await tl_query.get_import_report(session, actor, job_id=requested["job_id"])
    assert report["status"] == "succeeded"
    return upload["source_asset_id"], report["record_batch_revision_id"]


# --------------------------------------------------------------------------- #
# Allocation upsert + validate parity — same server truth on both lines        #
# --------------------------------------------------------------------------- #


async def test_allocation_upsert_and_validate_parity(session) -> None:
    await _seed(session)
    comp_owner = await _composition(session, OWNER)
    comp_agent = await _composition(session, AGENT)
    inputs = {
        "enabled": True,
        "initial_capital": _INITIAL_CAPITAL,
        "compounding_mode": _COMPOUNDING,
        "reserve_cash_percent": "0",
        "entries": [],
    }

    direct = await alloc_cmd.upsert_allocation_draft(
        session, OWNER, composition_id=comp_owner, expected_row_version=0, **inputs
    )
    await session.commit()

    via_tool = await agent_tools.dispatch_tool_call(
        session,
        AGENT,
        tool_name="portfolio_allocation.upsert_draft",
        policy_scope="proposal",
        request={"composition_id": comp_agent, "expected_row_version": 0, **inputs},
    )
    await session.commit()

    assert via_tool["status"] == "succeeded"
    # The fingerprint is derived from the (composition-independent, entry-free)
    # config, so both lines compute the identical domain truth.
    assert via_tool["draft_fingerprint"] == direct["draft_fingerprint"]
    assert via_tool["enabled"] == direct["enabled"] is True
    assert via_tool["row_version"] == direct["row_version"] == 1

    direct_v = await alloc_cmd.validate_allocation_draft(session, OWNER, composition_id=comp_owner)
    await session.commit()
    via_tool_v = await agent_tools.dispatch_tool_call(
        session,
        AGENT,
        tool_name="portfolio_allocation.validate",
        policy_scope="research",
        request={"composition_id": comp_agent},
    )
    await session.commit()

    assert via_tool_v["status"] == "succeeded"
    assert via_tool_v["state"] == direct_v["state"]
    assert via_tool_v["valid"] == direct_v["valid"]
    assert via_tool_v["config_hash"] == direct_v["config_hash"]


async def test_allocation_read_tools_parity(session) -> None:
    await _seed(session)
    comp = await _composition(session, AGENT)
    await agent_tools.dispatch_tool_call(
        session,
        AGENT,
        tool_name="portfolio_allocation.upsert_draft",
        policy_scope="proposal",
        request={
            "composition_id": comp,
            "expected_row_version": 0,
            "enabled": True,
            "initial_capital": _INITIAL_CAPITAL,
            "compounding_mode": _COMPOUNDING,
            "reserve_cash_percent": "0",
            "entries": [],
        },
    )
    await session.commit()

    direct_draft = await alloc_query.get_allocation_draft(session, AGENT, composition_id=comp)
    via_draft = await agent_tools.dispatch_tool_call(
        session,
        AGENT,
        tool_name="portfolio_allocation.get_draft",
        policy_scope="observation",
        request={"composition_id": comp},
    )
    assert via_draft["status"] == "succeeded"
    assert via_draft["plan_id"] == direct_draft["plan_id"]
    assert via_draft["row_version"] == direct_draft["row_version"]
    assert via_draft["draft"] == direct_draft["draft"]

    direct_sync = await alloc_query.sync_preview(session, AGENT, composition_id=comp)
    via_sync = await agent_tools.dispatch_tool_call(
        session,
        AGENT,
        tool_name="portfolio_allocation.sync_preview",
        policy_scope="observation",
        request={"composition_id": comp},
    )
    assert via_sync["status"] == "succeeded"
    assert via_sync["requires_confirmation"] == direct_sync["requires_confirmation"]
    assert via_sync["retained"] == direct_sync["retained"]


async def test_allocation_full_chain_via_gateway(session) -> None:
    await _seed(session)
    comp, items = await _composition_with_items(session, AGENT, count=3)

    upsert = await agent_tools.dispatch_tool_call(
        session,
        AGENT,
        tool_name="portfolio_allocation.upsert_draft",
        policy_scope="proposal",
        request={
            "composition_id": comp,
            "expected_row_version": 0,
            "enabled": True,
            "initial_capital": _INITIAL_CAPITAL,
            "compounding_mode": _COMPOUNDING,
            "reserve_cash_percent": "10",
            "entries": _entries((items[0], "40"), (items[1], "35"), (items[2], "15")),
        },
    )
    await session.commit()
    assert upsert["status"] == "succeeded"
    assert upsert["row_version"] == 1

    validate = await agent_tools.dispatch_tool_call(
        session,
        AGENT,
        tool_name="portfolio_allocation.validate",
        policy_scope="research",
        request={"composition_id": comp},
    )
    await session.commit()
    assert validate["status"] == "succeeded"
    # ADIM 3 containment: the Agent line sees EXACTLY what the human line sees — an
    # enabled shared plan is not valid, because shared capital does not execute in
    # this build. The gateway is not a second policy surface; it reports the same
    # typed blocker (doc 18 §10: an Agent is never a privileged caller).
    assert validate["valid"] is False
    assert _CONTAINMENT_CODE in {i["code"] for i in validate["issues"]}

    # Human command line: the identical refusal.
    with pytest.raises(AllocationHasBlockersError) as exc_info:
        await alloc_cmd.create_allocation_revision(
            session, AGENT, composition_id=comp, expected_row_version=1
        )
    await session.rollback()
    assert {d["code"] for d in exc_info.value.details} == {_CONTAINMENT_CODE}
    human_line_code = exc_info.value.code

    # Gateway line: the SAME typed error, not a softer gateway-specific outcome.
    # (Only ForbiddenError is translated into a `rejected` envelope; a validation
    # refusal propagates identically on both lines — which is the parity claim.)
    with pytest.raises(AllocationHasBlockersError) as gateway_exc:
        await agent_tools.dispatch_tool_call(
            session,
            AGENT,
            tool_name="portfolio_allocation.create_revision",
            policy_scope="proposal",
            request={"composition_id": comp, "expected_row_version": 1},
        )
    await session.rollback()
    assert gateway_exc.value.code == human_line_code
    assert {d["code"] for d in gateway_exc.value.details} == {_CONTAINMENT_CODE}
    # Neither line left an immutable plan revision behind.
    assert await _count(session, PortfolioAllocationPlanRevision) == 0


async def test_allocation_foreign_owner_upsert_denial_parity(session) -> None:
    await _seed(session)
    comp_owner = await _composition(session, OWNER)  # OWNER-owned composition
    # Commit the seed (principals + runtime + workspace) so the later human-line
    # rollback only undoes the rejected command, not the fixture.
    await session.commit()

    inputs = {
        "composition_id": comp_owner,
        "expected_row_version": 0,
        "enabled": True,
        "initial_capital": _INITIAL_CAPITAL,
        "compounding_mode": _COMPOUNDING,
        "reserve_cash_percent": "0",
        "entries": [],
    }

    # Human command line: the Agent principal calling the command directly gets
    # the typed 403.
    with pytest.raises(AccessDeniedError) as exc_info:
        await alloc_cmd.upsert_allocation_draft(
            session,
            AGENT,
            composition_id=comp_owner,
            expected_row_version=0,
            enabled=True,
            initial_capital=_INITIAL_CAPITAL,
            compounding_mode=_COMPOUNDING,
            reserve_cash_percent="0",
            entries=[],
        )
    await session.rollback()
    human_code = exc_info.value.code

    via_tool = await agent_tools.dispatch_tool_call(
        session,
        AGENT,
        tool_name="portfolio_allocation.upsert_draft",
        policy_scope="proposal",
        request=inputs,
    )
    await session.commit()

    assert via_tool["status"] == "rejected"
    assert via_tool["reason_code"] == human_code
    call = await session.get(AgentToolCall, via_tool["tool_call_id"])
    assert call is not None and call.failure_code == human_code
    assert await _count(session, PortfolioAllocationPlan) == 0  # neither line left a plan


# --------------------------------------------------------------------------- #
# Trade Log create -> revision parity                                          #
# --------------------------------------------------------------------------- #


async def test_trade_log_create_and_revision_via_gateway(session, fake_object_store) -> None:
    await _seed(session)
    source_asset_id, batch_id = await _imported_batch(session, AGENT)

    payload = _tl_payload(source_asset_id, batch_id)
    config, issues = validate_trade_log_config(payload)
    assert config is not None and not issues
    expected_hash = compute_config_hash(config)

    created = await agent_tools.dispatch_tool_call(
        session,
        AGENT,
        tool_name="trade_log.create",
        policy_scope="proposal",
        request={"payload": payload, "attach": True},
    )
    await session.commit()
    assert created["status"] == "succeeded"
    assert created["object_kind"] == "trade_log"
    assert created["revision_no"] == 1
    assert created["config_hash"] == expected_hash
    root_id = created["root_id"]

    revised = await agent_tools.dispatch_tool_call(
        session,
        AGENT,
        tool_name="trade_log.create_revision",
        policy_scope="proposal",
        request={
            "root_id": root_id,
            "payload": _tl_payload(
                source_asset_id, batch_id, identity={"display_name": "Q1 revised"}
            ),
            "expected_head_revision_id": created["revision_id"],
        },
    )
    await session.commit()
    assert revised["status"] == "succeeded"
    assert revised["root_id"] == root_id
    assert revised["revision_no"] == 2
    assert revised["auto_repinned"] is False
    assert await _count(session, WorkObjectRevision) == 2


async def test_trade_log_foreign_owner_revision_denial_parity(session, fake_object_store) -> None:
    await _seed(session)
    source_asset_id, batch_id = await _imported_batch(session, OWNER)
    created = await tl_cmd.create_trade_log_and_attach(
        session, OWNER, payload=_tl_payload(source_asset_id, batch_id)
    )
    await session.commit()
    root_id = created["root_id"]

    revision_payload = _tl_payload(source_asset_id, batch_id, identity={"display_name": "hijack"})

    # Human command line: the Agent calling the command directly gets the typed 403.
    with pytest.raises(AccessDeniedError) as exc_info:
        await tl_cmd.create_trade_log_revision(
            session, AGENT, root_id=root_id, payload=revision_payload
        )
    await session.rollback()
    human_code = exc_info.value.code

    via_tool = await agent_tools.dispatch_tool_call(
        session,
        AGENT,
        tool_name="trade_log.create_revision",
        policy_scope="proposal",
        request={"root_id": root_id, "payload": revision_payload},
    )
    await session.commit()

    assert via_tool["status"] == "rejected"
    assert via_tool["reason_code"] == human_code
    call = await session.get(AgentToolCall, via_tool["tool_call_id"])
    assert call is not None and call.failure_code == human_code
    # The foreign root keeps exactly its single (owner-created) revision.
    assert await _count(session, WorkObjectRevision) == 1


# --------------------------------------------------------------------------- #
# Trade Log import — the durable job actually reaches its actor                 #
# --------------------------------------------------------------------------- #


async def test_trade_log_import_is_handed_off_to_its_data_actor(
    session, fake_object_store, monkeypatch
) -> None:
    """The step the human route performs (``routes/trade_log.py`` ->
    ``send_job(run_trade_log_import, ...)``) and the Gateway plane did not.

    ``enqueue_job`` only INSERTs a QUEUED row; the caller dispatches the actor after
    commit. The ``data`` queue is deliberately excluded from the scheduler's automatic
    redelivery sweep (``ACTOR_BY_QUEUE``) because it is multi-actor, so an
    agent-admitted Trade Log import sat QUEUED until an Admin ran the manual
    redelivery action — a call reporting ``succeeded`` over work that could never
    start. Regression guard for that defect.
    """
    from entropia.application.jobs.data_queue import TRADE_LOG_IMPORT
    from entropia.apps.worker import actors as worker_actors

    await _seed(session)
    upload = await tl_cmd.upload_source_asset(
        session, AGENT, content=_GOOD_CSV, original_filename="trades.csv"
    )
    await session.commit()

    requested = await agent_tools.dispatch_tool_call(
        session,
        AGENT,
        tool_name="trade_log.request_import",
        policy_scope="research",
        request={"source_asset_id": upload["source_asset_id"], "instrument_id": "BTCUSDT"},
    )
    await session.commit()

    assert requested["status"] == "succeeded"  # the CALL was admitted
    assert requested["import_status"] == "queued"  # the WORK has not run
    assert requested["import_job_kind"] == TRADE_LOG_IMPORT
    assert agent_tools.pending_data_job_dispatch(requested) == (
        TRADE_LOG_IMPORT,
        requested["job_id"],
    )

    sent: list[tuple[object, str]] = []
    monkeypatch.setattr(
        "entropia.infrastructure.queues.enqueue.send_job",
        lambda actor, job_id: sent.append((actor, job_id)),
    )
    worker_actors._dispatch_pending_data_job(requested)
    assert sent == [(worker_actors.run_trade_log_import, requested["job_id"])]


async def test_a_replayed_trade_log_import_never_re_dispatches(session, fake_object_store) -> None:
    """A redelivered tool call admitted no new work. ``run_import`` has no
    terminal-state guard, so re-sending a finished job would parse the file twice and
    write a second record batch."""
    await _seed(session)
    upload = await tl_cmd.upload_source_asset(
        session, AGENT, content=_GOOD_CSV, original_filename="trades.csv"
    )
    await session.commit()

    first = await agent_tools.dispatch_tool_call(
        session,
        AGENT,
        tool_name="trade_log.request_import",
        policy_scope="research",
        request={"source_asset_id": upload["source_asset_id"], "instrument_id": "BTCUSDT"},
        idempotency_key="tl-import-1",
    )
    await session.commit()
    replay = await agent_tools.dispatch_tool_call(
        session,
        AGENT,
        tool_name="trade_log.request_import",
        policy_scope="research",
        request={"source_asset_id": upload["source_asset_id"], "instrument_id": "BTCUSDT"},
        idempotency_key="tl-import-1",
    )
    await session.commit()

    assert replay["replayed"] is True
    assert replay["job_id"] == first["job_id"]
    assert agent_tools.pending_data_job_dispatch(replay) is None


# --------------------------------------------------------------------------- #
# TL-22.c3 / c4 — the SUCCESS path's durable provenance, and whose board moves  #
# --------------------------------------------------------------------------- #


async def test_successful_trade_log_tool_call_records_its_own_provenance(
    session, fake_object_store
) -> None:
    """doc 05 §16 TL-22.c3 — "provenance is recorded on a durable AgentToolCall row
    carrying the outcome/failure code".

    Only the DENIAL path re-read the row (``…_denial_parity`` asserts failure_code).
    The success path asserted the returned dict, which the dispatcher builds in
    memory — a handler that never wrote a terminal row, or wrote one under the wrong
    agent/task, would return the same dict. This re-reads the row itself and pins the
    provenance the Agent Lab surfaces are governed by: who ran it, under which task
    and checkpoint, at which scope, and with a terminal SUCCEEDED status carrying no
    failure code.
    """
    await _seed(session)
    source_asset_id, batch_id = await _imported_batch(session, AGENT)
    task = await lab_repo.create_task(
        session,
        agent_id=ALPHA_AGENT_ID,
        task_type="trade_log_ingest",
        title="TL-22 provenance",
        source="directive",
        priority=AgentTaskPriority.NORMAL,
        status=AgentTaskStatus.RUNNING,
    )
    await session.flush()

    created = await agent_tools.dispatch_tool_call(
        session,
        AGENT,
        tool_name="trade_log.create",
        policy_scope="proposal",
        request={"payload": _tl_payload(source_asset_id, batch_id), "attach": True},
        task_id=task.task_id,
        checkpoint_id="agtckpt_tl22",
    )
    await session.commit()
    assert created["status"] == "succeeded"

    call = await session.get(AgentToolCall, created["tool_call_id"])
    assert call is not None
    assert call.status == ToolCallStatus.SUCCEEDED
    # A terminal SUCCESS never carries a failure code — the same column the denial
    # path pins, asserted from the other side so "recorded outcome" means both.
    assert call.failure_code is None
    assert call.failure_message is None
    assert call.tool_name == ToolName.TRADE_LOG_CREATE
    assert call.agent_id == ALPHA_AGENT_ID
    assert call.actor_principal_id == _AGENT_PID
    assert call.actor_kind == ActorKind.AGENT
    assert call.policy_scope == PolicyScope.PROPOSAL
    assert call.task_id == task.task_id
    assert call.checkpoint_id == "agtckpt_tl22"
    assert call.correlation_id == AGENT.correlation_id
    # The row also carries the outcome itself, so the Agent's history resolves the
    # object it created without replaying the tool.
    assert call.response_ref is not None
    assert call.response_ref["root_id"] == created["root_id"]
    assert call.artifact_output_ref == created["revision_id"]


async def test_agent_trade_log_work_leaves_the_human_mainboard_untouched(
    session, fake_object_store
) -> None:
    """doc 05 §16 TL-22.c4 — "the human Mainboard is not auto-mutated by the Agent's
    work".

    ``auto_repinned is False`` is a DIFFERENT guarantee (a pin does not move); it says
    nothing about whose board receives the new item. ``trade_log.create`` defaults to
    ``attach=True`` with no workspace_id, so the attach target is whatever
    ``_resolve_attach_workspace`` resolves — a default board resolved without the
    actor would silently land the Agent's row on a human's composition. This seeds a
    human board first and asserts it is byte-for-byte where it was afterwards.
    """
    await _seed(session)
    human_workspace_id, human_item_ids = await _composition_with_items(session, OWNER, count=2)
    before = await mb_query.get_default_mainboard(session, OWNER)

    source_asset_id, batch_id = await _imported_batch(session, AGENT)
    created = await agent_tools.dispatch_tool_call(
        session,
        AGENT,
        tool_name="trade_log.create",
        policy_scope="proposal",
        request={"payload": _tl_payload(source_asset_id, batch_id), "attach": True},
    )
    await session.commit()

    assert created["status"] == "succeeded"
    assert created["attached"] is True
    # The Agent attached to its OWN board, which must not be the human's.
    assert created["workspace_id"] != human_workspace_id

    after = await mb_query.get_default_mainboard(session, OWNER)
    assert after["workspace_id"] == human_workspace_id
    assert [item["item_id"] for item in after["items"]] == human_item_ids
    # composition_hash and row_version are what a Ready report and an ETag are
    # compared against: an untouched board must move neither.
    assert after["composition_hash"] == before["composition_hash"]
    assert after["row_version"] == before["row_version"]
    # And the Agent's row really exists — on its own board, not nowhere.
    agent_board = await mb_query.get_default_mainboard(session, AGENT)
    assert agent_board["workspace_id"] == created["workspace_id"]
    assert [item["work_object_root_id"] for item in agent_board["items"]] == [created["root_id"]]
