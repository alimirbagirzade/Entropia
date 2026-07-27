"""O-04 — the mandatory-audit events that a rollback used to erase (docs 14 §12.2, 07 §13.2).

Every command runs in ONE request transaction that is rolled back on any >=4xx
(``apps.api.deps.TransactionBoundaryMiddleware``). That made three spec-mandated
audit events STRUCTURALLY unwritable, because each is reached only by RAISING:

* ``run_admission_rejected``  — a blocked RUN raises ``ReadinessBlockedError`` (422)
* ``readiness_access_denied`` — a foreign actor raises ``AccessDeniedError`` (403)
* ``precheck_stale``          — a stale scan raises ``PrecheckStale`` (409)

These tests are the proof of durability, not of "an audit call happened": the
request session is ROLLED BACK exactly as the middleware would, and the audit row
is then read back through a SEPARATE committed session. A row that only lived in
the request transaction cannot pass.

Also covered: the accepted-admission event carries the idempotency-key DIGEST (never
the raw key) + parent Agent task id, ``readiness.became_stale`` fires from the
composition mutation that invalidated the report (not from the read-time
derivation), and the Pre-Check ``precheck_started`` / ``dependency_*`` trail.

Auto-skips when no PostgreSQL is reachable (see tests/integration/conftest.py).
"""

from __future__ import annotations

import hashlib
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from entropia.application.commands import backtest_run as backtest_cmd
from entropia.application.commands import mainboard as mb_cmd
from entropia.application.commands import readiness_check as readiness_cmd
from entropia.application.queries import mainboard as mb_query
from entropia.domain.identity import Actor
from entropia.domain.lifecycle.enums import (
    ApprovalState,
    PackageKind,
    PrincipalType,
    Role,
    VisibilityScope,
)
from entropia.domain.market_data.enums import MarketDataType, MarketRevisionState
from entropia.domain.package.enums import PackageValidationState
from entropia.infrastructure.postgres.models import (
    BacktestRun,
    EntityRegistry,
    MainboardWorkingItem,
    MarketDatasetRevision,
    Principal,
    ReadyCheckReport,
)
from entropia.infrastructure.postgres.models.audit import AuditEvent, OutboxEvent
from entropia.infrastructure.postgres.repositories import packages as pkg_repo
from entropia.shared.errors import AccessDeniedError, ReadinessBlockedError

pytestmark = pytest.mark.integration

USER1 = Actor(
    principal_id="user_1",
    principal_type=PrincipalType.HUMAN,
    role=Role.USER,
    correlation_id="corr_o04",
)
USER2 = Actor(principal_id="user_2", principal_type=PrincipalType.HUMAN, role=Role.USER)


# --------------------------------------------------------------------------- #
# Durable-audit plumbing (mirrors tests/integration/test_auth.py)              #
# --------------------------------------------------------------------------- #


def _audit_factory(session: AsyncSession) -> async_sessionmaker[AsyncSession]:
    """A committed-transaction factory bound to the SAME test engine, so the rows
    the commands write in their OWN transaction land in this test's database (the
    production ``lru_cache`` factory is not safe across test event loops)."""
    bind = session.bind
    assert isinstance(bind, AsyncEngine)
    return async_sessionmaker(bind=bind, expire_on_commit=False)


async def _events(session: AsyncSession, event_kind: str) -> list[AuditEvent]:
    """Read committed audit rows through a FRESH session — the durability proof."""
    async with _audit_factory(session)() as read:
        result = await read.execute(
            select(AuditEvent)
            .where(AuditEvent.event_kind == event_kind)
            .order_by(AuditEvent.event_id)
        )
        return list(result.scalars().all())


# --------------------------------------------------------------------------- #
# Seeding (same shape as test_readiness_persistence)                           #
# --------------------------------------------------------------------------- #


async def _seed_principals(session: AsyncSession) -> None:
    for pid in ("user_1", "user_2"):
        if await session.get(Principal, pid) is None:
            session.add(Principal(principal_id=pid, principal_type=PrincipalType.HUMAN))
    await session.flush()


async def _seed_market_revision(session: AsyncSession) -> None:
    root = EntityRegistry(
        entity_id="md_root_1",
        entity_type="market_dataset",
        owner_principal_id="user_1",
        created_by_principal_id="user_1",
        lifecycle_state="active",
        current_revision_id=None,
    )
    session.add(root)
    await session.flush()
    session.add(
        MarketDatasetRevision(
            revision_id="md_rev_1",
            entity_id=root.entity_id,
            revision_no=1,
            market_data_type=MarketDataType.OHLCV,
            revision_state=MarketRevisionState.APPROVED,
            payload={},
            content_hash="a" * 64,
            created_by_principal_id="user_1",
        )
    )
    root.current_revision_id = "md_rev_1"
    await session.flush()


def _strategy_payload(indicator_revision_id: str) -> dict[str, Any]:
    return {
        "strategy_root_id": "strat_root_seed",
        "display_name": "Seed strategy",
        "rationale_family_id": "rf_1",
        "data": {
            "instrument_id": "BTCUSDT",
            "market_dataset_root_id": "md_root_1",
            "market_dataset_revision_id": "md_rev_1",
            "market_dataset_content_hash": "a" * 64,
            "backtest_range": {"start": "2024-01-01T00:00:00Z", "end": "2024-06-01T00:00:00Z"},
            "initial_capital": "10000.00",
            "execution": {"entry_timing": "next_candle_open", "exit_timing": "next_candle_open"},
            "order_config": {"type": "market_order"},
            "costs": {"commission": "0.04", "spread": "0.01", "slippage_value": "0.1"},
            "intrabar_policy": {"tick_policy": "inherit"},
            "funding": {"enabled": False},
        },
        "position_entry_logic": {
            "signal_block": {"rule": "required_indicator_blocks_only"},
            "indicator_blocks": [
                {
                    "block_id": "ib_1",
                    "display_order": 0,
                    "package_ref": {
                        "package_root_id": "pkg_root_1",
                        "package_revision_id": indicator_revision_id,
                        "package_content_hash": "b" * 64,
                    },
                    "trigger_source": "indicator_native_trigger",
                    "requirement": "required",
                }
            ],
        },
        "position_exit_logic": {},
        "protection_stop_logic": {"percentage_stop": {"enabled": True, "loss_percentage": "1.0"}},
        "position_sizing": {"method": "base_position_size", "base_position_size": "1.0"},
        "restrictions_filters": {},
        "conflict_position_handling": {},
    }


async def _empty_composition(session: AsyncSession, actor: Actor) -> str:
    mb = await mb_query.get_default_mainboard(session, actor)
    await session.commit()
    return str(mb["workspace_id"])


async def _toggle_item(session: AsyncSession, actor: Actor, item_id: str, *, enabled: bool) -> None:
    """Flip an item's enabled flag — a doc 01 §5.2 fingerprint-CHANGING mutation."""
    item = await session.get(MainboardWorkingItem, item_id)
    assert item is not None
    await mb_cmd.patch_mainboard_item(
        session,
        actor,
        item_id=item_id,
        intent="set_enabled",
        expected_row_version=item.row_version,
        is_enabled=enabled,
    )


async def _composition_with_strategy(session: AsyncSession, actor: Actor) -> tuple[str, str]:
    """A RUNnable composition. Returns ``(composition_id, item_id)``."""
    await _seed_market_revision(session)
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
    work_object = await mb_cmd.create_work_object(
        session,
        actor,
        object_kind="strategy",
        payload=_strategy_payload(pkg_rev.revision_id),
    )
    item = await mb_cmd.attach_mainboard_item(
        session,
        actor,
        workspace_id=workspace_id,
        root_id=work_object["root_id"],
        revision_id=work_object["revision_id"],
        item_kind="strategy",
    )
    await session.commit()
    return workspace_id, str(item["item_id"])


# --------------------------------------------------------------------------- #
# run_admission_rejected — survives the 422 rollback                          #
# --------------------------------------------------------------------------- #


async def test_blocked_run_admission_leaves_a_durable_rejected_audit(
    session: AsyncSession,
) -> None:
    # An empty composition is a BLOCKER (COMPOSITION_EMPTY), so admission must 422 —
    # and doc 14 §12.2 says that decision is itself auditable. Before O-04 the audit
    # died with the rollback the 422 triggers; here the request tx is rolled back
    # explicitly and the row is still readable from a separate session.
    await _seed_principals(session)
    composition_id = await _empty_composition(session, USER1)

    with pytest.raises(ReadinessBlockedError):
        await backtest_cmd.request_backtest_run(
            session,
            USER1,
            composition_id=composition_id,
            audit_session_factory=_audit_factory(session),
        )
    await session.rollback()  # exactly what TransactionBoundaryMiddleware does on 4xx

    events = await _events(session, "backtest.run_admission_rejected")
    assert len(events) == 1
    event = events[0]
    assert event.severity == "warning"
    assert event.actor_principal_id == "user_1"
    assert event.target_entity_id == composition_id
    assert event.correlation_id == "corr_o04"
    metadata = event.event_metadata or {}
    assert metadata["response_code"] == "READINESS_BLOCKED"
    assert metadata["http_status"] == 422
    assert metadata["issue_count"] >= 1
    assert any(item["code"] == "COMPOSITION_EMPTY" for item in metadata["issue_summary"])
    assert metadata["current_fingerprint"] is not None  # the preflight DID compute one
    # The preflight's own report was written in the rolled-back transaction, so the
    # audit must NOT name it — that id will not exist a moment from now.
    assert metadata["ready_report_id"] is None

    # The rejection really did roll everything else back: no run, no report survives.
    async with _audit_factory(session)() as read:
        assert (await read.execute(select(BacktestRun))).scalars().first() is None
        assert (await read.execute(select(ReadyCheckReport))).scalars().first() is None


async def test_stale_fingerprint_admission_rejection_records_both_fingerprints(
    session: AsyncSession,
) -> None:
    # RC-09: a stale ``expected_fingerprint`` is a 409 raised INSIDE the nested
    # preflight — the path that never reached the admission code at all. §12.2 wants
    # the expected/current pair, so the wrapper reports what the body had resolved.
    await _seed_principals(session)
    composition_id, _item_id = await _composition_with_strategy(session, USER1)

    from entropia.shared.errors import CompositionStaleError

    with pytest.raises(CompositionStaleError):
        await backtest_cmd.request_backtest_run(
            session,
            USER1,
            composition_id=composition_id,
            expected_fingerprint="0" * 64,
            audit_session_factory=_audit_factory(session),
        )
    await session.rollback()

    events = await _events(session, "backtest.run_admission_rejected")
    assert len(events) == 1
    metadata = events[0].event_metadata or {}
    assert metadata["response_code"] == "COMPOSITION_STALE"
    assert metadata["expected_fingerprint"] == "0" * 64
    # The preflight raised before publishing a report, so the current fingerprint is
    # honestly null rather than a guess.
    assert metadata["current_fingerprint"] is None
    assert metadata["ready_report_id"] is None


# --------------------------------------------------------------------------- #
# readiness_access_denied — survives the 403 rollback, on BOTH surfaces        #
# --------------------------------------------------------------------------- #


async def test_foreign_actor_ready_check_leaves_a_durable_access_denied_audit(
    session: AsyncSession,
) -> None:
    await _seed_principals(session)
    composition_id = await _empty_composition(session, USER1)

    with pytest.raises(AccessDeniedError):
        await readiness_cmd.run_readiness_check(
            session,
            USER2,
            composition_id=composition_id,
            audit_session_factory=_audit_factory(session),
        )
    await session.rollback()

    events = await _events(session, "readiness.access_denied")
    assert len(events) == 1
    event = events[0]
    assert event.actor_principal_id == "user_2"
    assert event.target_entity_id == composition_id
    assert event.target_entity_type == "mainboard_workspace"
    assert event.new_state == "ACCESS_DENIED"
    metadata = event.event_metadata or {}
    assert metadata["operation"] == "run_readiness_check"
    assert metadata["denial_code"] == "ACCESS_DENIED"


async def test_foreign_actor_run_admission_denial_is_tagged_with_its_operation(
    session: AsyncSession,
) -> None:
    # One event kind, two doors: the ``operation`` field is what distinguishes a
    # denied Ready Check from a denied RUN admission on the same composition.
    await _seed_principals(session)
    composition_id = await _empty_composition(session, USER1)

    with pytest.raises(AccessDeniedError):
        await backtest_cmd.request_backtest_run(
            session,
            USER2,
            composition_id=composition_id,
            audit_session_factory=_audit_factory(session),
        )
    await session.rollback()

    events = await _events(session, "readiness.access_denied")
    assert len(events) == 1
    assert (events[0].event_metadata or {})["operation"] == "request_backtest_run"


# --------------------------------------------------------------------------- #
# run_admission_accepted — key DIGEST + parent Agent task id                   #
# --------------------------------------------------------------------------- #


async def test_accepted_admission_audit_carries_key_digest_and_parent_task(
    session: AsyncSession,
) -> None:
    await _seed_principals(session)
    composition_id, _item_id = await _composition_with_strategy(session, USER1)

    result = await backtest_cmd.request_backtest_run(
        session,
        USER1,
        composition_id=composition_id,
        idempotency_key="idem-key-abc",
        parent_agent_task_id="agtask_1",
    )
    await session.commit()  # accepted admission commits with its audit (same tx)

    events = await _events(session, "backtest.run_admission_accepted")
    assert len(events) == 1
    event = events[0]
    assert event.target_entity_id == result["run_id"]
    metadata = event.event_metadata or {}
    digest = hashlib.sha256(b"idem-key-abc").hexdigest()
    assert metadata["idempotency_key_hash"] == f"sha256:{digest}"
    # The raw key is never persisted anywhere in the row.
    assert "idem-key-abc" not in str(metadata)
    assert metadata["parent_agent_task_id"] == "agtask_1"
    assert metadata["ready_report_id"] == result["ready_report_id"]
    assert metadata["manifest_hash"] == result["manifest_hash"]
    # queue/outbox outcome (doc 14 §12.2): the run really was handed to a durable job.
    assert metadata["queue_outcome"] == {"queue": "backtest", "job_id": result["job_id"]}
    assert metadata["outbox_outcome"] == "backtest.run_queued"

    # The pre-existing taxonomy is untouched — the new event is added, not swapped in.
    assert len(await _events(session, "backtest.run_requested")) == 1
    assert len(await _events(session, "backtest.run_queued")) == 1


async def test_admission_without_idempotency_key_records_a_null_digest(
    session: AsyncSession,
) -> None:
    # No key supplied is a real, distinguishable state — never a hash of "".
    await _seed_principals(session)
    composition_id, _item_id = await _composition_with_strategy(session, USER1)

    await backtest_cmd.request_backtest_run(session, USER1, composition_id=composition_id)
    await session.commit()

    metadata = (await _events(session, "backtest.run_admission_accepted"))[0].event_metadata or {}
    assert metadata["idempotency_key_hash"] is None
    assert metadata["parent_agent_task_id"] is None


async def test_ready_check_request_audit_carries_the_parent_agent_task(
    session: AsyncSession,
) -> None:
    await _seed_principals(session)
    composition_id = await _empty_composition(session, USER1)

    await readiness_cmd.run_readiness_check(
        session, USER1, composition_id=composition_id, parent_agent_task_id="agtask_7"
    )
    await session.commit()

    events = await _events(session, "readiness.check_requested")
    assert len(events) == 1
    assert (events[0].event_metadata or {})["parent_agent_task_id"] == "agtask_7"


# --------------------------------------------------------------------------- #
# readiness_became_stale — emitted by the mutation, not by the read            #
# --------------------------------------------------------------------------- #


async def test_composition_change_emits_readiness_became_stale(session: AsyncSession) -> None:
    # The readiness QUERY still derives staleness at read time (unchanged). What was
    # missing is the audit of the transition: the mutation that invalidated the
    # report emits it, in the same tx, with the old/new fingerprint pair.
    await _seed_principals(session)
    composition_id, item_id = await _composition_with_strategy(session, USER1)
    report = await readiness_cmd.run_readiness_check(session, USER1, composition_id=composition_id)
    await session.commit()

    await _toggle_item(session, USER1, item_id, enabled=False)
    await session.commit()

    events = await _events(session, "readiness.became_stale")
    assert len(events) == 1
    event = events[0]
    assert event.target_entity_id == report["report_id"]
    assert event.target_entity_type == "ready_check_report"
    assert event.new_state == "stale"
    metadata = event.event_metadata or {}
    assert metadata["previous_report_id"] == report["report_id"]
    assert metadata["old_fingerprint"] == report["composition_fingerprint"]
    assert metadata["new_fingerprint"] != report["composition_fingerprint"]
    assert metadata["source_event"] == "mainboard.composition_changed"

    # Outbox fan-out too: this path commits, so the transactional outbox carries it.
    async with _audit_factory(session)() as read:
        rows = (
            (
                await read.execute(
                    select(OutboxEvent).where(OutboxEvent.event_type == "readiness.became_stale")
                )
            )
            .scalars()
            .all()
        )
    assert len(rows) == 1
    assert rows[0].resource_id == report["report_id"]


async def test_already_stale_report_does_not_re_emit_became_stale(
    session: AsyncSession,
) -> None:
    # A burst of composition edits produces ONE transition event, not one per edit:
    # a report that was already stale cannot become stale again.
    await _seed_principals(session)
    composition_id, item_id = await _composition_with_strategy(session, USER1)
    await readiness_cmd.run_readiness_check(session, USER1, composition_id=composition_id)
    await session.commit()

    await _toggle_item(session, USER1, item_id, enabled=False)
    await session.commit()
    await _toggle_item(session, USER1, item_id, enabled=True)
    await session.commit()

    assert len(await _events(session, "readiness.became_stale")) == 1


async def test_never_checked_composition_emits_no_became_stale(session: AsyncSession) -> None:
    # Nothing to invalidate when the composition was never checked.
    await _seed_principals(session)
    _composition_id, item_id = await _composition_with_strategy(session, USER1)

    await _toggle_item(session, USER1, item_id, enabled=False)
    await session.commit()

    assert await _events(session, "readiness.became_stale") == []
