"""I-17-COV — Agent-parity + soft-delete acceptance IDs (docs 02, 03, 04).

Auto-skips without PostgreSQL (see tests/integration/conftest.py). Closes three
rows ``docs/audit/acceptance_id_map.md`` §E listed as GENUINE coverage gaps:

- AT-21 (doc 02 §12 "Agent parity"): the Agent creates + saves a Strategy revision
  through the SAME application command line a human uses — same schema, same
  ownership policy, same Idempotency-Key contract, same audit — with no browser.
- AT-24 (doc 02 §12 "Soft delete integrity"): delete soft-deletes the Root only
  AFTER the active-run guard; the historical Run Manifest / Result keeps resolving
  its immutable provenance; Trash restore is Admin-only.
- TS-20 (doc 04 §15) / AOS-20 (doc 03 §NN) "Agent parity": the Agent
  imports/saves/attaches an external work object UI-lessly, its output is owned and
  provenance-recorded, and it is NOT auto-attached to a human board.

HONEST BOUNDARY for AT-21 / TS-20 (verified 2026-07-29): neither page's line has a
Tool Gateway tool. ``domain/agent_lab/tool_gateway.py::ToolName`` ships allocation
and trade_log tools (post-V1 S4) but NO ``strategy.*`` and no ``trading_signal.*``
member, so the literal "via Tool Gateway" clause of AT-21/TS-20 cannot be tested —
there is nothing to call. What IS proven here is the substance both rows are about
and what AOS-20 states outright ("Tool Gateway/domain commands"): the Agent reaches
the same server truth on the same command line, under the same policy, with no UI.
The missing tools are an implementation gap, tracked in §E.2 of the map.
"""

from __future__ import annotations

import hashlib
from typing import Any

import pytest
from sqlalchemy import func, select

from entropia.application.commands import backtest_run as backtest_cmd
from entropia.application.commands import strategy_draft as strat_cmd
from entropia.application.commands import trading_signal as ts_cmd
from entropia.application.commands.deletion import restore_entity, soft_delete_entity
from entropia.application.jobs.backtest_engine import run_backtest
from entropia.application.jobs.trading_signal import run_import
from entropia.application.queries import backtest_run as backtest_query
from entropia.application.queries import mainboard as mb_query
from entropia.application.queries import trading_signal as ts_query
from entropia.domain.identity import Actor
from entropia.domain.lifecycle.enums import DeletionState, PrincipalType, Role
from entropia.infrastructure.postgres.models import (
    AuditEvent,
    Principal,
    StrategyRevision,
    WorkObjectRevision,
)
from entropia.infrastructure.postgres.repositories import backtest as bt_repo
from entropia.infrastructure.s3 import datasets
from entropia.shared.errors import (
    AccessDeniedError,
    ObjectInActiveRunError,
    TrashAccessForbiddenError,
)
from tests.integration.test_backtest_persistence import _e2e_bars, _ready_composition
from tests.integration.test_strategy_integration import _valid_payload

pytestmark = pytest.mark.integration

_HUMAN_PID = "user_1"
_AGENT_PID = "agent_alpha"
_ADMIN_PID = "user_admin"

HUMAN = Actor(principal_id=_HUMAN_PID, principal_type=PrincipalType.HUMAN, role=Role.USER)
ADMIN = Actor(principal_id=_ADMIN_PID, principal_type=PrincipalType.HUMAN, role=Role.ADMIN)
AGENT = Actor(
    principal_id=_AGENT_PID,
    principal_type=PrincipalType.AGENT,
    role=None,
    correlation_id="corr_i17cov_parity",
)

_HEADER = "source_record_id,event_time,available_time,direction,signal_type"
_GOOD_CSV = "\n".join(
    [
        _HEADER,
        "r1,2024-05-01T10:00:00Z,2024-05-01T10:03:00Z,long,entry",
        "r2,2024-05-02T10:00:00Z,2024-05-02T10:01:00Z,sell,exit",
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


async def _seed_principals(session) -> None:
    for pid, ptype in (
        (_HUMAN_PID, PrincipalType.HUMAN),
        (_ADMIN_PID, PrincipalType.HUMAN),
        (_AGENT_PID, PrincipalType.AGENT),
    ):
        if await session.get(Principal, pid) is None:
            session.add(Principal(principal_id=pid, principal_type=ptype))
    await session.flush()


async def _count(session, model) -> int:
    return int((await session.execute(select(func.count()).select_from(model))).scalar_one())


async def _draft_and_save(
    session, actor: Actor, *, idempotency_key: str | None = None
) -> dict[str, Any]:
    draft = await strat_cmd.create_strategy_draft(
        session,
        actor,
        display_name="Parity Strategy",
        rationale_family_id="ratfam_int",
        initial_payload=_valid_payload("Parity Strategy"),
    )
    await session.commit()
    saved = await strat_cmd.save_strategy_revision(
        session,
        actor,
        draft_id=draft["draft_id"],
        expected_draft_row_version=draft["row_version"],
        idempotency_key=idempotency_key,
    )
    await session.commit()
    return {"draft": draft, "saved": saved}


def _signal_payload(source_asset_id: str, normalized_revision_id: str) -> dict[str, Any]:
    return {
        "kind": "trading_signal",
        "identity": {"display_name": "Agent-imported signal source"},
        "source": {"provider_name": "Provider X", "source_kind": "file"},
        "instrument_scope": {"instrument_id": "inst_btcusdt", "display_symbol": "BTCUSDT"},
        "event_model": {"resolution_kind": "event_based", "base_timeframe": None},
        "classification": {"rationale_family_id": None},
        "data_quality": {"mode": "signal_events_only"},
        "time_policy": {"source_timezone": "UTC", "normalization_timezone": "UTC"},
        "price_policy": {"source": "suggested_signal_price", "fallback": None},
        "ohlcv_policy": {"use_mode": "use_if_supplied_and_needed"},
        "capital": {"independent_initial_capital": "10000"},
        "import_binding": {
            "source_asset_id": source_asset_id,
            "normalized_event_revision_id": normalized_revision_id,
        },
    }


async def _import_signal(session, actor: Actor) -> dict[str, Any]:
    """Upload -> request import -> run worker, entirely on the command line."""
    upload = await ts_cmd.upload_source_asset(
        session, actor, content=_GOOD_CSV, original_filename="signals.csv"
    )
    await session.commit()
    requested = await ts_cmd.request_trading_signal_import(
        session, actor, source_asset_id=upload["source_asset_id"], instrument_id="BTCUSDT"
    )
    await session.commit()
    await run_import(session, requested["job_id"])
    await session.commit()
    report = await ts_query.get_import_report(session, actor, job_id=requested["job_id"])
    assert report["status"] == "succeeded"
    return {
        "source_asset_id": upload["source_asset_id"],
        "normalized_revision_id": report["normalized_event_revision_id"],
    }


# --------------------------------------------------------------------------- #
# AT-21 — Agent parity on the Strategy save line                                #
# --------------------------------------------------------------------------- #


async def test_agent_saves_a_strategy_revision_with_human_parity(session) -> None:
    """AT-21: same schema, same server truth, no browser.

    The Agent principal drives create-draft -> save through the identical command
    functions the UI calls, and the immutable revision it produces carries the SAME
    ``config_hash`` a human produces from the same payload — the strongest available
    statement that one validation/compile line serves both callers.
    """
    await _seed_principals(session)

    human = await _draft_and_save(session, HUMAN)
    agent = await _draft_and_save(session, AGENT)

    assert agent["saved"]["config_hash"] == human["saved"]["config_hash"]
    assert agent["saved"]["revision_number"] == human["saved"]["revision_number"] == 1
    assert await _count(session, StrategyRevision) == 2

    # Provenance: the Agent's revision is owned/created by the AGENT principal, so a
    # reader can tell the two lines apart even though the truth is identical.
    revision = await session.get(StrategyRevision, agent["saved"]["strategy_revision_id"])
    assert revision is not None
    assert revision.created_by_principal == _AGENT_PID

    agent_audit = (
        await session.execute(
            select(func.count())
            .select_from(AuditEvent)
            .where(
                AuditEvent.event_kind == "strategy.revision_created",
                AuditEvent.actor_principal_id == _AGENT_PID,
            )
        )
    ).scalar_one()
    assert agent_audit == 1


async def test_agent_strategy_save_honours_idempotency_and_ownership(session) -> None:
    """AT-21's other two clauses: the SAME Idempotency-Key contract, and the SAME
    ownership policy — an Agent may not save into a human's draft."""
    await _seed_principals(session)

    first = await _draft_and_save(session, AGENT, idempotency_key="agent-save-1")
    replay = await strat_cmd.save_strategy_revision(
        session,
        AGENT,
        draft_id=first["draft"]["draft_id"],
        expected_draft_row_version=first["draft"]["row_version"],
        idempotency_key="agent-save-1",
    )
    await session.commit()
    assert replay["strategy_revision_id"] == first["saved"]["strategy_revision_id"]
    assert await _count(session, StrategyRevision) == 1  # the replay appended nothing

    human_draft = await strat_cmd.create_strategy_draft(
        session,
        HUMAN,
        display_name="Human only",
        rationale_family_id="ratfam_int",
        initial_payload=_valid_payload("Human only"),
    )
    await session.commit()
    with pytest.raises(AccessDeniedError):
        await strat_cmd.save_strategy_revision(
            session,
            AGENT,
            draft_id=human_draft["draft_id"],
            expected_draft_row_version=human_draft["row_version"],
        )
    await session.rollback()
    assert await _count(session, StrategyRevision) == 1  # still only the Agent's own


# --------------------------------------------------------------------------- #
# AT-24 — soft-delete integrity around a historical run                         #
# --------------------------------------------------------------------------- #


async def test_strategy_delete_waits_for_the_run_guard_and_keeps_run_provenance(session) -> None:
    """AT-24: "Delete Strategy soft deletes Root/row after active-run guard;
    historical Run Manifest/Result continues to resolve immutable provenance; Trash
    restore Admin-only." All three clauses, in that order."""
    await _seed_principals(session)
    composition_id, strategy_root_id, strategy_revision_id = await _ready_composition(
        session, HUMAN
    )

    admitted = await backtest_cmd.request_backtest_run(
        session, HUMAN, composition_id=composition_id
    )
    await session.commit()
    manifest_hash = admitted["manifest_hash"]

    # 1. The active-run guard vetoes the delete BEFORE any Trash entry exists.
    with pytest.raises(ObjectInActiveRunError):
        await soft_delete_entity(session, HUMAN, entity_id=strategy_root_id, reason="cleanup")
    await session.rollback()

    finished = await run_backtest(session, admitted["job_id"], stream_bars=_e2e_bars)
    await session.commit()
    assert finished["state"] == "succeeded"

    # 2. With no active run the same delete now succeeds.
    root = await soft_delete_entity(session, HUMAN, entity_id=strategy_root_id, reason="cleanup")
    await session.commit()
    assert root.deletion_state == DeletionState.SOFT_DELETED

    # 3. The historical manifest/result still resolves the SAME pinned provenance.
    manifest = await bt_repo.get_manifest_by_run(session, admitted["run_id"])
    assert manifest is not None and manifest.manifest_hash == manifest_hash
    result_view = await backtest_query.get_backtest_result(
        session, HUMAN, result_id=finished["result_id"]
    )
    assert result_view["manifest"]["manifest_hash"] == manifest_hash
    pinned = await session.get(WorkObjectRevision, strategy_revision_id)
    assert pinned is not None  # the immutable revision the manifest names still reads

    # 4. Restore is Admin-only; the owner who deleted it cannot undo it themselves.
    with pytest.raises(TrashAccessForbiddenError):
        await restore_entity(session, HUMAN, entity_id=strategy_root_id)
    await session.rollback()
    restored = await restore_entity(session, ADMIN, entity_id=strategy_root_id)
    await session.commit()
    assert restored.deletion_state == DeletionState.ACTIVE


# --------------------------------------------------------------------------- #
# TS-20 / AOS-20 — UI-less external work object, owned and not auto-attached    #
# --------------------------------------------------------------------------- #


async def test_agent_imports_and_saves_a_trading_signal_without_a_ui(
    session, fake_object_store
) -> None:
    """TS-20 / AOS-20: the Agent runs upload -> import -> save & attach on the same
    command line as the page, and reaches the same server truth as a human doing the
    identical import."""
    await _seed_principals(session)

    agent_import = await _import_signal(session, AGENT)
    agent_saved = await ts_cmd.create_trading_signal_and_attach(
        session,
        AGENT,
        payload=_signal_payload(
            agent_import["source_asset_id"], agent_import["normalized_revision_id"]
        ),
    )
    await session.commit()

    human_import = await _import_signal(session, HUMAN)
    human_saved = await ts_cmd.create_trading_signal_and_attach(
        session,
        HUMAN,
        payload=_signal_payload(
            human_import["source_asset_id"], human_import["normalized_revision_id"]
        ),
    )
    await session.commit()

    assert agent_saved["object_kind"] == human_saved["object_kind"] == "trading_signal"
    assert agent_saved["attached"] is True
    agent_revision = await session.get(WorkObjectRevision, agent_saved["revision_id"])
    human_revision = await session.get(WorkObjectRevision, human_saved["revision_id"])
    assert agent_revision is not None and human_revision is not None
    # Same normalization -> same available_time truth; the payload differs only in the
    # ids of each caller's own import binding.
    assert agent_revision.available_time == human_revision.available_time
    assert agent_revision.payload["kind"] == "trading_signal"

    # Provenance: the Agent's output is attributed to the AGENT principal.
    assert agent_revision.created_by_principal_id == _AGENT_PID
    agent_audit = (
        await session.execute(
            select(func.count())
            .select_from(AuditEvent)
            .where(
                AuditEvent.event_kind == "trading_signal.revision_created",
                AuditEvent.actor_principal_id == _AGENT_PID,
            )
        )
    ).scalar_one()
    assert agent_audit == 1


async def test_agent_signal_is_not_auto_attached_to_a_human_board(
    session, fake_object_store
) -> None:
    """TS-20 / AOS-20 last clause: "human board is not auto-mutated". The Agent's
    save attaches to the AGENT's own default composition; the human's board is
    exactly as empty as before."""
    await _seed_principals(session)
    human_board_before = await mb_query.get_default_mainboard(session, HUMAN)
    await session.commit()

    imported = await _import_signal(session, AGENT)
    await ts_cmd.create_trading_signal_and_attach(
        session,
        AGENT,
        payload=_signal_payload(imported["source_asset_id"], imported["normalized_revision_id"]),
    )
    await session.commit()

    human_board_after = await mb_query.get_default_mainboard(session, HUMAN)
    assert human_board_after["items"] == []
    assert human_board_after["composition_hash"] == human_board_before["composition_hash"]

    agent_board = await mb_query.get_default_mainboard(session, AGENT)
    assert [item["item_kind"] for item in agent_board["items"]] == ["trading_signal"]
    assert agent_board["workspace_id"] != human_board_after["workspace_id"]
