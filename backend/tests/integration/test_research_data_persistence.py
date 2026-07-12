"""Stage 2b Research Data acceptance — exercised against a real database.

Auto-skips when no PostgreSQL is reachable (see tests/integration/conftest.py).
Covers: hard market dependency (DEPENDENCY_BLOCKED), create+link, time policy +
approve (verified->approved, +1 audit & +1 outbox, approval_decision recorded),
revoke (approval_revoked + decision recorded), bundle pins exact ids and enforces
usage_scope, optimistic 409, idempotent approve replay returns cached, soft-delete
preserves the revision chain.
"""

from __future__ import annotations

import pytest
from sqlalchemy import func, select

from entropia.application.commands import market_data as md_cmd
from entropia.application.commands import research_data as rd_cmd
from entropia.application.commands.deletion import restore_entity, soft_delete_entity
from entropia.application.jobs import research_data as rd_jobs
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
from entropia.domain.trash.page import TrashEntryStatus
from entropia.infrastructure.postgres.models import (
    ApprovalDecision,
    AuditEvent,
    OutboxEvent,
    Principal,
    ResearchDatasetRevision,
    ResearchMarketLink,
    TrashEntry,
)
from entropia.infrastructure.postgres.repositories import market_data as md_repo
from entropia.infrastructure.postgres.repositories import research_data as rd_repo
from entropia.shared.errors import (
    AccessDeniedError,
    DependencyBlocked,
    StaleRevisionError,
    UsageScopeForbidden,
)

pytestmark = pytest.mark.integration

# Research Data is restricted to Admin/Supervisor/Agent (doc 12 §2): a Supervisor
# is the page-eligible non-Admin owner used throughout these flows.
ADMIN = Actor(principal_id="user_admin", principal_type=PrincipalType.HUMAN, role=Role.ADMIN)
OWNER = Actor(principal_id="user_1", principal_type=PrincipalType.HUMAN, role=Role.SUPERVISOR)
OPEN_INTEREST = CategorySpec(category=ResearchCategory.OPEN_INTEREST)
UTC_TZ = ResearchTimezoneSpec(mode=ResearchTimezoneMode.UTC)
FIXED_DELAY = AvailableTimeSpec(policy=AvailableTimePolicy.FIXED_DELAY, delay_seconds=120)


async def _count(session, model) -> int:
    return int((await session.execute(select(func.count()).select_from(model))).scalar_one())


async def _seed_principals(session) -> None:
    for pid in ("user_admin", "user_1"):
        if await session.get(Principal, pid) is None:
            session.add(Principal(principal_id=pid, principal_type=PrincipalType.HUMAN))
    await session.flush()


async def _approved_market(session) -> str:
    """Create + approve a market dataset; return its entity_id."""
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


async def _verify_head(session, entity_id: str) -> ResearchDatasetRevision:
    root = await rd_repo.get_dataset_root(session, entity_id)
    assert root is not None
    revision = await rd_repo.get_revision(session, root.current_revision_id or "")
    assert revision is not None
    revision.revision_state = ResearchRevisionState.VERIFIED
    revision.event_time_semantics = EventTimeSemantics.PROVIDER_EVENT_TIMESTAMP
    revision.available_time_policy = AvailableTimePolicy.FIXED_DELAY
    revision.available_delay_seconds = 120
    await session.flush()
    return revision


async def test_create_without_approved_market_is_blocked(session) -> None:
    await _seed_principals(session)
    # A market dataset whose head is only DRAFT -> not approved -> blocked.
    root, _ = await md_cmd.create_market_dataset(
        session, ADMIN, market_data_type=MarketDataType.OHLCV, payload={"v": 1}
    )
    await session.commit()
    with pytest.raises(DependencyBlocked):
        await rd_cmd.create_research_dataset(
            session,
            OWNER,
            market_entity_id=root.entity_id,
            payload={"f": 1},
            category=OPEN_INTEREST,
            usage_scope=UsageScope.RESEARCH_BACKTEST,
        )


async def test_create_links_approved_market_with_audit_outbox(session) -> None:
    await _seed_principals(session)
    market_id = await _approved_market(session)
    await session.commit()

    before_audit = await _count(session, AuditEvent)
    before_outbox = await _count(session, OutboxEvent)

    root, revision = await rd_cmd.create_research_dataset(
        session,
        OWNER,
        market_entity_id=market_id,
        payload={"f": 1},
        category=OPEN_INTEREST,
        usage_scope=UsageScope.RESEARCH_BACKTEST,
        display_name="OI",
    )
    await session.commit()

    assert root.row_version == 1
    assert revision.revision_state == ResearchRevisionState.DRAFT
    assert revision.linked_market_dataset_revision_id is not None
    assert await _count(session, ResearchMarketLink) == 1
    assert await _count(session, AuditEvent) == before_audit + 1
    assert await _count(session, OutboxEvent) == before_outbox + 1


async def test_approve_then_revoke_records_decisions(session) -> None:
    await _seed_principals(session)
    market_id = await _approved_market(session)
    await session.commit()
    root, _ = await rd_cmd.create_research_dataset(
        session,
        OWNER,
        market_entity_id=market_id,
        payload={"f": 1},
        category=OPEN_INTEREST,
        usage_scope=UsageScope.RESEARCH_BACKTEST,
    )
    await session.commit()
    revision = await _verify_head(session, root.entity_id)
    await session.commit()

    decisions_before = await _count(session, ApprovalDecision)
    approve = await rd_cmd.approve_research_dataset_revision(
        session, ADMIN, entity_id=root.entity_id, revision_id=revision.revision_id
    )
    await session.commit()
    assert approve["revision_state"] == "approved"
    assert revision.revision_state == ResearchRevisionState.APPROVED

    revoke = await rd_cmd.revoke_research_dataset_approval(
        session, ADMIN, entity_id=root.entity_id, revision_id=revision.revision_id
    )
    await session.commit()
    assert revoke["revision_state"] == "approval_revoked"
    assert revision.revision_state == ResearchRevisionState.APPROVAL_REVOKED
    # Two decisions recorded (approve + revoke).
    assert await _count(session, ApprovalDecision) == decisions_before + 2


async def test_evidence_bundle_pins_exact_ids_and_enforces_scope(session) -> None:
    await _seed_principals(session)
    market_id = await _approved_market(session)
    await session.commit()

    # Approved Research+Backtest revision -> eligible.
    root, _ = await rd_cmd.create_research_dataset(
        session,
        OWNER,
        market_entity_id=market_id,
        payload={"f": 1},
        category=OPEN_INTEREST,
        usage_scope=UsageScope.RESEARCH_BACKTEST,
    )
    await session.commit()
    revision = await _verify_head(session, root.entity_id)
    await session.commit()
    await rd_cmd.approve_research_dataset_revision(
        session, ADMIN, entity_id=root.entity_id, revision_id=revision.revision_id
    )
    await session.commit()

    bundle = await rd_jobs.compile_backtest_evidence_bundle(
        session, ADMIN, research_revision_ids=[revision.revision_id]
    )
    member = bundle["members"][0]
    assert member["research_revision_id"] == revision.revision_id
    assert member["research_content_hash"] == revision.content_hash
    assert member["market_dataset_revision_id"] == revision.linked_market_dataset_revision_id
    assert bundle["bundle_hash"]

    # An Agent-Research-Only revision must be rejected from an evidence bundle.
    aro_root, _ = await rd_cmd.create_research_dataset(
        session,
        OWNER,
        market_entity_id=market_id,
        payload={"f": 2},
        category=OPEN_INTEREST,
        usage_scope=UsageScope.AGENT_RESEARCH_ONLY,
    )
    await session.commit()
    aro_rev = await _verify_head(session, aro_root.entity_id)
    await session.commit()
    await rd_cmd.approve_research_dataset_revision(
        session, ADMIN, entity_id=aro_root.entity_id, revision_id=aro_rev.revision_id
    )
    await session.commit()
    with pytest.raises(UsageScopeForbidden):
        await rd_jobs.compile_backtest_evidence_bundle(
            session, ADMIN, research_revision_ids=[aro_rev.revision_id]
        )


async def test_optimistic_conflict_on_stale_row_version(session) -> None:
    await _seed_principals(session)
    market_id = await _approved_market(session)
    await session.commit()
    root, _ = await rd_cmd.create_research_dataset(
        session,
        OWNER,
        market_entity_id=market_id,
        payload={"f": 1},
        category=OPEN_INTEREST,
        usage_scope=UsageScope.RESEARCH_BACKTEST,
    )
    await session.commit()

    await rd_cmd.create_research_dataset_revision(
        session,
        OWNER,
        entity_id=root.entity_id,
        payload={"f": 2},
        category=OPEN_INTEREST,
        usage_scope=UsageScope.RESEARCH_BACKTEST,
        timezone_spec=UTC_TZ,
        expected_row_version=1,
    )
    await session.commit()

    with pytest.raises(StaleRevisionError):
        await rd_cmd.create_research_dataset_revision(
            session,
            OWNER,
            entity_id=root.entity_id,
            payload={"f": 3},
            category=OPEN_INTEREST,
            usage_scope=UsageScope.RESEARCH_BACKTEST,
            timezone_spec=UTC_TZ,
            expected_row_version=1,  # stale
        )


async def test_idempotent_approve_replay_returns_cached(session) -> None:
    await _seed_principals(session)
    market_id = await _approved_market(session)
    await session.commit()
    root, _ = await rd_cmd.create_research_dataset(
        session,
        OWNER,
        market_entity_id=market_id,
        payload={"f": 1},
        category=OPEN_INTEREST,
        usage_scope=UsageScope.RESEARCH_BACKTEST,
    )
    await session.commit()
    revision = await _verify_head(session, root.entity_id)
    await session.commit()

    first = await rd_cmd.approve_research_dataset_revision(
        session,
        ADMIN,
        entity_id=root.entity_id,
        revision_id=revision.revision_id,
        idempotency_key="approve-k1",
    )
    await session.commit()
    decisions_after_first = await _count(session, ApprovalDecision)
    audit_after_first = await _count(session, AuditEvent)

    second = await rd_cmd.approve_research_dataset_revision(
        session,
        ADMIN,
        entity_id=root.entity_id,
        revision_id=revision.revision_id,
        idempotency_key="approve-k1",
    )
    await session.commit()

    assert second == first
    assert await _count(session, ApprovalDecision) == decisions_after_first
    assert await _count(session, AuditEvent) == audit_after_first


async def test_soft_delete_preserves_revision_chain(session) -> None:
    await _seed_principals(session)
    market_id = await _approved_market(session)
    await session.commit()
    root, revision = await rd_cmd.create_research_dataset(
        session,
        OWNER,
        market_entity_id=market_id,
        payload={"f": 1},
        category=OPEN_INTEREST,
        usage_scope=UsageScope.RESEARCH_BACKTEST,
    )
    await session.commit()
    head = root.current_revision_id

    await soft_delete_entity(session, OWNER, entity_id=root.entity_id, reason="cleanup")
    await session.commit()

    assert root.deletion_state == DeletionState.SOFT_DELETED
    assert await rd_repo.get_revision(session, revision.revision_id) is not None
    assert root.current_revision_id == head


async def _trash_entry(session, entity_id: str) -> TrashEntry | None:
    return (
        await session.execute(select(TrashEntry).where(TrashEntry.entity_id == entity_id))
    ).scalar_one_or_none()


async def _count_kind(session, event_kind: str) -> int:
    return int(
        (
            await session.execute(
                select(func.count())
                .select_from(AuditEvent)
                .where(AuditEvent.event_kind == event_kind)
            )
        ).scalar_one()
    )


async def _create_dataset(session):
    market_id = await _approved_market(session)
    root, _ = await rd_cmd.create_research_dataset(
        session,
        OWNER,
        market_entity_id=market_id,
        payload={"f": 1},
        category=OPEN_INTEREST,
        usage_scope=UsageScope.RESEARCH_BACKTEST,
        display_name="OI",
    )
    await session.commit()
    return root


async def test_domain_soft_delete_writes_named_trash_entry_and_audit(session) -> None:
    await _seed_principals(session)
    root = await _create_dataset(session)

    result = await rd_cmd.soft_delete_research_dataset(
        session, OWNER, entity_id=root.entity_id, reason="cleanup"
    )
    await session.commit()

    assert result["deletion_state"] == str(DeletionState.SOFT_DELETED)
    entry = await _trash_entry(session, root.entity_id)
    assert entry is not None
    assert entry.status == TrashEntryStatus.SOFT_DELETED
    assert entry.entity_type == "research_dataset"
    assert entry.display_name == "OI"  # snapshot from the current revision display_name
    assert await _count_kind(session, "research.dataset.soft_deleted") == 1


async def test_domain_soft_delete_then_admin_restore_round_trip(session) -> None:
    await _seed_principals(session)
    root = await _create_dataset(session)

    await rd_cmd.soft_delete_research_dataset(session, OWNER, entity_id=root.entity_id)
    await session.commit()
    assert root.deletion_state == DeletionState.SOFT_DELETED

    restored = await restore_entity(session, ADMIN, entity_id=root.entity_id)
    await session.commit()

    assert restored.deletion_state == DeletionState.ACTIVE
    assert (await _trash_entry(session, root.entity_id)).status == TrashEntryStatus.RESTORED


async def test_domain_soft_delete_rejects_non_owner(session) -> None:
    await _seed_principals(session)
    root = await _create_dataset(session)
    # A page-eligible but non-owner Supervisor still cannot delete another's root.
    stranger = Actor(
        principal_id="user_2", principal_type=PrincipalType.HUMAN, role=Role.SUPERVISOR
    )

    with pytest.raises(AccessDeniedError):
        await rd_cmd.soft_delete_research_dataset(session, stranger, entity_id=root.entity_id)
    assert await _trash_entry(session, root.entity_id) is None


async def test_domain_soft_delete_stale_row_version_conflicts(session) -> None:
    await _seed_principals(session)
    root = await _create_dataset(session)

    with pytest.raises(StaleRevisionError):
        await rd_cmd.soft_delete_research_dataset(
            session, OWNER, entity_id=root.entity_id, expected_row_version=root.row_version + 99
        )
    assert root.deletion_state == DeletionState.ACTIVE
    assert await _trash_entry(session, root.entity_id) is None
