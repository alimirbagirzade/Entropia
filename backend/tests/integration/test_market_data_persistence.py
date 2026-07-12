"""Stage 2a Market Data acceptance — exercised against a real database.

Auto-skips when no PostgreSQL is reachable (see tests/integration/conftest.py).
Covers: create dataset + revision, append successor (provenance preserved),
approve (verified->approved, +1 audit & +1 outbox, approval_decision recorded),
optimistic 409 on stale row_version, soft-delete via the Stage-1 deletion command
preserving the revision chain, and resolve-bundle returning only ACTIVE+APPROVED.
"""

from __future__ import annotations

import pytest
from sqlalchemy import func, select

from entropia.application.commands import market_data as md_cmd
from entropia.application.commands.deletion import restore_entity, soft_delete_entity
from entropia.application.queries.market_data import (
    resolve_approved_market_data_bundle,
)
from entropia.domain.identity import Actor
from entropia.domain.lifecycle.enums import (
    DeletionState,
    PrincipalType,
    Role,
)
from entropia.domain.market_data.enums import MarketDataType, MarketRevisionState, TimezoneMode
from entropia.domain.market_data.value_objects import TimezoneSpec
from entropia.domain.trash.page import TrashEntryStatus
from entropia.infrastructure.postgres.models import (
    ApprovalDecision,
    AuditEvent,
    MarketDatasetRevision,
    OutboxEvent,
    Principal,
    TrashEntry,
)
from entropia.infrastructure.postgres.repositories import market_data as md_repo
from entropia.shared.errors import AccessDeniedError, NotFoundError, StaleRevisionError

pytestmark = pytest.mark.integration

ADMIN = Actor(principal_id="user_admin", principal_type=PrincipalType.HUMAN, role=Role.ADMIN)
OWNER = Actor(principal_id="user_1", principal_type=PrincipalType.HUMAN, role=Role.USER)
UTC_TZ = TimezoneSpec(mode=TimezoneMode.UTC)


async def _count(session, model) -> int:
    return int((await session.execute(select(func.count()).select_from(model))).scalar_one())


async def _seed_principals(session) -> None:
    for pid, ptype in (
        ("user_admin", PrincipalType.HUMAN),
        ("user_1", PrincipalType.HUMAN),
    ):
        if await session.get(Principal, pid) is None:
            session.add(Principal(principal_id=pid, principal_type=ptype))
    await session.flush()


async def _verify_head(session, entity_id: str) -> MarketDatasetRevision:
    """Force the head revision into VERIFIED so approval is legal."""
    root = await md_repo.get_dataset_root(session, entity_id)
    assert root is not None
    revision = await md_repo.get_revision(session, root.current_revision_id or "")
    assert revision is not None
    revision.revision_state = MarketRevisionState.VERIFIED
    await session.flush()
    return revision


async def test_create_dataset_inserts_revision_audit_outbox(session) -> None:
    await _seed_principals(session)
    before_audit = await _count(session, AuditEvent)
    before_outbox = await _count(session, OutboxEvent)

    root, revision = await md_cmd.create_market_dataset(
        session,
        OWNER,
        market_data_type=MarketDataType.OHLCV,
        payload={"instrument": "DEMO"},
        title="Demo",
    )
    await session.commit()

    assert root.row_version == 1
    assert root.current_revision_id == revision.revision_id
    assert revision.revision_state == MarketRevisionState.DRAFT
    assert await _count(session, AuditEvent) == before_audit + 1
    assert await _count(session, OutboxEvent) == before_outbox + 1


async def test_successor_preserves_provenance(session) -> None:
    await _seed_principals(session)
    root, first = await md_cmd.create_market_dataset(
        session, OWNER, market_data_type=MarketDataType.OHLCV, payload={"v": 1}
    )
    await session.commit()

    successor = await md_cmd.create_successor_revision(
        session,
        OWNER,
        entity_id=root.entity_id,
        payload={"v": 2},
        market_data_type=MarketDataType.OHLCV,
    )
    await session.commit()

    assert successor.revision_no == 2
    assert successor.supersedes_revision_id == first.revision_id
    assert root.current_revision_id == successor.revision_id
    assert root.row_version == 2
    # The prior revision is immutable and still present (provenance).
    assert await md_repo.get_revision(session, first.revision_id) is not None


async def test_approve_verified_revision_records_decision(session) -> None:
    await _seed_principals(session)
    root, _ = await md_cmd.create_market_dataset(
        session, OWNER, market_data_type=MarketDataType.OHLCV, payload={"v": 1}
    )
    await session.commit()
    revision = await _verify_head(session, root.entity_id)
    await session.commit()

    before_audit = await _count(session, AuditEvent)
    before_outbox = await _count(session, OutboxEvent)
    before_decisions = await _count(session, ApprovalDecision)

    result = await md_cmd.approve_market_dataset_revision(
        session,
        ADMIN,
        entity_id=root.entity_id,
        revision_id=revision.revision_id,
        note="looks good",
    )
    await session.commit()

    assert result["revision_state"] == "approved"
    assert revision.revision_state == MarketRevisionState.APPROVED
    assert await _count(session, AuditEvent) == before_audit + 1
    assert await _count(session, OutboxEvent) == before_outbox + 1
    assert await _count(session, ApprovalDecision) == before_decisions + 1


async def test_optimistic_conflict_on_stale_row_version(session) -> None:
    await _seed_principals(session)
    root, _ = await md_cmd.create_market_dataset(
        session, OWNER, market_data_type=MarketDataType.OHLCV, payload={"v": 1}
    )
    await session.commit()

    # Append once to bump row_version to 2.
    await md_cmd.create_market_dataset_revision(
        session,
        OWNER,
        entity_id=root.entity_id,
        payload={"v": 2},
        market_data_type=MarketDataType.OHLCV,
        timezone_spec=UTC_TZ,
        expected_row_version=1,
    )
    await session.commit()

    with pytest.raises(StaleRevisionError):
        await md_cmd.create_market_dataset_revision(
            session,
            OWNER,
            entity_id=root.entity_id,
            payload={"v": 3},
            market_data_type=MarketDataType.OHLCV,
            timezone_spec=UTC_TZ,
            expected_row_version=1,  # stale
        )


async def test_soft_delete_preserves_revision_chain(session) -> None:
    await _seed_principals(session)
    root, revision = await md_cmd.create_market_dataset(
        session, OWNER, market_data_type=MarketDataType.OHLCV, payload={"v": 1}
    )
    await session.commit()
    head = root.current_revision_id

    await soft_delete_entity(session, OWNER, entity_id=root.entity_id, reason="cleanup")
    await session.commit()

    assert root.deletion_state == DeletionState.SOFT_DELETED
    # Provenance preserved: the revision row still exists and head is unchanged.
    assert await md_repo.get_revision(session, revision.revision_id) is not None
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


async def test_domain_soft_delete_writes_named_trash_entry_and_audit(session) -> None:
    await _seed_principals(session)
    root, _ = await md_cmd.create_market_dataset(
        session, OWNER, market_data_type=MarketDataType.OHLCV, payload={"v": 1}, title="Prices"
    )
    await session.commit()
    before_outbox = await _count(session, OutboxEvent)

    result = await md_cmd.soft_delete_market_dataset(
        session, OWNER, entity_id=root.entity_id, reason="cleanup"
    )
    await session.commit()

    assert result["deletion_state"] == str(DeletionState.SOFT_DELETED)
    assert root.deletion_state == DeletionState.SOFT_DELETED
    entry = await _trash_entry(session, root.entity_id)
    assert entry is not None
    assert entry.status == TrashEntryStatus.SOFT_DELETED
    assert entry.entity_type == "market_dataset"
    assert entry.display_name == "Prices"  # snapshot from the current revision title
    # The delete lands in the market audit family (doc 11 §10), not entity.*.
    assert await _count_kind(session, "market.dataset.soft_deleted") == 1
    assert await _count(session, OutboxEvent) == before_outbox + 1


async def test_domain_soft_delete_then_admin_restore_round_trip(session) -> None:
    await _seed_principals(session)
    root, _ = await md_cmd.create_market_dataset(
        session, OWNER, market_data_type=MarketDataType.OHLCV, payload={"v": 1}, title="RT"
    )
    await session.commit()

    await md_cmd.soft_delete_market_dataset(session, OWNER, entity_id=root.entity_id)
    await session.commit()
    assert root.deletion_state == DeletionState.SOFT_DELETED

    restored = await restore_entity(session, ADMIN, entity_id=root.entity_id)
    await session.commit()

    assert restored.deletion_state == DeletionState.ACTIVE
    assert (await _trash_entry(session, root.entity_id)).status == TrashEntryStatus.RESTORED


async def test_domain_soft_delete_rejects_non_owner(session) -> None:
    await _seed_principals(session)
    root, _ = await md_cmd.create_market_dataset(
        session, OWNER, market_data_type=MarketDataType.OHLCV, payload={"v": 1}
    )
    await session.commit()
    stranger = Actor(principal_id="user_2", principal_type=PrincipalType.HUMAN, role=Role.USER)

    with pytest.raises(AccessDeniedError):
        await md_cmd.soft_delete_market_dataset(session, stranger, entity_id=root.entity_id)
    # No Trash Entry is written for a rejected delete.
    assert await _trash_entry(session, root.entity_id) is None


async def test_domain_soft_delete_repeat_is_idempotent(session) -> None:
    await _seed_principals(session)
    root, _ = await md_cmd.create_market_dataset(
        session, OWNER, market_data_type=MarketDataType.OHLCV, payload={"v": 1}
    )
    await session.commit()

    await md_cmd.soft_delete_market_dataset(session, OWNER, entity_id=root.entity_id)
    await session.commit()
    await md_cmd.soft_delete_market_dataset(session, OWNER, entity_id=root.entity_id)
    await session.commit()

    # One Trash Entry, one audit — the repeat is a no-op (doc 20 §14).
    assert await _count(session, TrashEntry) == 1
    assert await _count_kind(session, "market.dataset.soft_deleted") == 1


async def test_domain_soft_delete_stale_row_version_conflicts(session) -> None:
    await _seed_principals(session)
    root, _ = await md_cmd.create_market_dataset(
        session, OWNER, market_data_type=MarketDataType.OHLCV, payload={"v": 1}
    )
    await session.commit()

    with pytest.raises(StaleRevisionError):
        await md_cmd.soft_delete_market_dataset(
            session, OWNER, entity_id=root.entity_id, expected_row_version=root.row_version + 99
        )
    assert root.deletion_state == DeletionState.ACTIVE
    assert await _trash_entry(session, root.entity_id) is None


async def test_resolve_bundle_only_returns_approved_active(session) -> None:
    await _seed_principals(session)
    root, _ = await md_cmd.create_market_dataset(
        session, OWNER, market_data_type=MarketDataType.OHLCV, payload={"v": 1}
    )
    await session.commit()

    # Draft head -> no bundle.
    with pytest.raises(NotFoundError):
        await resolve_approved_market_data_bundle(session, entity_id=root.entity_id)

    revision = await _verify_head(session, root.entity_id)
    await md_cmd.approve_market_dataset_revision(
        session, ADMIN, entity_id=root.entity_id, revision_id=revision.revision_id
    )
    await session.commit()

    bundle = await resolve_approved_market_data_bundle(session, entity_id=root.entity_id)
    assert bundle["revision_id"] == revision.revision_id
    assert bundle["revision_state"] == "approved"

    # Soft-delete makes it ineligible for consumers again.
    await soft_delete_entity(session, ADMIN, entity_id=root.entity_id)
    await session.commit()
    with pytest.raises(NotFoundError):
        await resolve_approved_market_data_bundle(session, entity_id=root.entity_id)


async def test_idempotent_approve_replay_returns_cached_no_duplicate(session) -> None:
    """Replaying approve with the same Idempotency-Key returns the stored result
    and does NOT re-run the body (no second ApprovalDecision / audit / outbox).

    Regression guard: the concurrency + state-machine checks live inside the
    idempotent body, so a completed-key replay must not re-validate against the
    already-APPROVED state and raise a spurious 409 (D3).
    """
    await _seed_principals(session)
    root, _ = await md_cmd.create_market_dataset(
        session, OWNER, market_data_type=MarketDataType.OHLCV, payload={"v": 1}
    )
    await session.commit()
    revision = await _verify_head(session, root.entity_id)
    await session.commit()

    first = await md_cmd.approve_market_dataset_revision(
        session,
        ADMIN,
        entity_id=root.entity_id,
        revision_id=revision.revision_id,
        idempotency_key="approve-k1",
    )
    await session.commit()
    decisions_after_first = await _count(session, ApprovalDecision)
    audit_after_first = await _count(session, AuditEvent)

    second = await md_cmd.approve_market_dataset_revision(
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


async def test_idempotent_create_revision_replay_skips_stale_check(session) -> None:
    """Replaying create_revision with the same key returns the cached result even
    though row_version advanced — the stale-version check is inside the idempotent
    body and is skipped on a completed-key replay (D3 regression guard)."""
    await _seed_principals(session)
    root, _ = await md_cmd.create_market_dataset(
        session, OWNER, market_data_type=MarketDataType.OHLCV, payload={"v": 1}
    )
    await session.commit()

    first = await md_cmd.create_market_dataset_revision(
        session,
        OWNER,
        entity_id=root.entity_id,
        payload={"v": 2},
        market_data_type=MarketDataType.OHLCV,
        timezone_spec=UTC_TZ,
        expected_row_version=1,
        idempotency_key="rev-k1",
    )
    await session.commit()
    revisions_after_first = await _count(session, MarketDatasetRevision)

    # Same key + same payload; row_version is now 2 so expected_row_version=1
    # would be stale — but the completed key short-circuits before that check.
    second = await md_cmd.create_market_dataset_revision(
        session,
        OWNER,
        entity_id=root.entity_id,
        payload={"v": 2},
        market_data_type=MarketDataType.OHLCV,
        timezone_spec=UTC_TZ,
        expected_row_version=1,
        idempotency_key="rev-k1",
    )
    await session.commit()

    assert second == first
    assert await _count(session, MarketDatasetRevision) == revisions_after_first
