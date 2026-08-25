"""Stage 2a Market Data acceptance — exercised against a real database.

Auto-skips when no PostgreSQL is reachable (see tests/integration/conftest.py).
Covers: create dataset + revision, append successor (provenance preserved),
approve (verified->approved, +1 audit & +1 outbox, approval_decision recorded),
optimistic 409 on stale row_version, soft-delete via the Stage-1 deletion command
preserving the revision chain, and resolve-bundle returning only ACTIVE+APPROVED.
"""

from __future__ import annotations

import hashlib

import pytest
from sqlalchemy import func, select

from entropia.application.commands import market_data as md_cmd
from entropia.application.commands.deletion import restore_entity, soft_delete_entity
from entropia.application.queries.market_data import (
    get_market_dataset_detail,
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
    MarketRawAsset,
    OutboxEvent,
    Principal,
    TrashEntry,
)
from entropia.infrastructure.postgres.repositories import market_data as md_repo
from entropia.shared.errors import (
    AccessDeniedError,
    MarketDataFileTypeNotAllowedError,
    MarketDataUploadIntegrityError,
    MarketDataUploadStorageFailedError,
    NotFoundError,
    StaleRevisionError,
)

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
        await resolve_approved_market_data_bundle(session, ADMIN, entity_id=root.entity_id)

    revision = await _verify_head(session, root.entity_id)
    await md_cmd.approve_market_dataset_revision(
        session, ADMIN, entity_id=root.entity_id, revision_id=revision.revision_id
    )
    await session.commit()

    bundle = await resolve_approved_market_data_bundle(session, ADMIN, entity_id=root.entity_id)
    assert bundle["revision_id"] == revision.revision_id
    assert bundle["revision_state"] == "approved"

    # Soft-delete makes it ineligible for consumers again.
    await soft_delete_entity(session, ADMIN, entity_id=root.entity_id)
    await session.commit()
    with pytest.raises(NotFoundError):
        await resolve_approved_market_data_bundle(session, ADMIN, entity_id=root.entity_id)


async def test_approved_bundle_agrees_with_detail_on_who_may_read(session) -> None:
    """The bundle surface must never answer a reader that its guarded sibling refuses.

    ``resolve_approved_market_data_bundle`` was, before this test, the only
    id-addressed surface in the backend that never received the actor. It looked
    harmless because for every root it can return, ``get_market_dataset_detail``
    would also grant access: approval sets ``lifecycle_state = "active"``,
    ``_visibility_of`` maps that to ``published``, and ``can_view`` grants
    ``published`` to everyone before it ever asks whether the caller is
    authenticated.

    That is a coincidence of two conditions lining up, not an invariant — so
    asserting it is worthless. This test asserts the DIVERGENCE instead: it
    constructs the one state where the two conditions come apart (the root's
    ``lifecycle_state`` no longer ``active`` while its current revision is still
    APPROVED and the row still ACTIVE) and requires both surfaces to refuse the
    same stranger. The state is built directly rather than through a command
    precisely because no command produces it today; a future one might, and this
    test is what would notice.
    """
    await _seed_principals(session)
    session.add(Principal(principal_id="user_2", principal_type=PrincipalType.HUMAN))
    stranger = Actor(principal_id="user_2", principal_type=PrincipalType.HUMAN, role=Role.USER)

    root, _ = await md_cmd.create_market_dataset(
        session, OWNER, market_data_type=MarketDataType.OHLCV, payload={"v": 1}
    )
    await session.commit()
    revision = await _verify_head(session, root.entity_id)
    await md_cmd.approve_market_dataset_revision(
        session, ADMIN, entity_id=root.entity_id, revision_id=revision.revision_id
    )
    await session.commit()

    # Positive control: the fixture really is cross-owner, and while the root is
    # published BOTH surfaces answer the stranger. If this half ever fails the
    # test below proves nothing.
    assert root.owner_principal_id != stranger.principal_id
    detail = await get_market_dataset_detail(session, stranger, entity_id=root.entity_id)
    bundle = await resolve_approved_market_data_bundle(session, stranger, entity_id=root.entity_id)
    assert detail["entity_id"] == root.entity_id
    assert bundle["revision_id"] == revision.revision_id

    # The divergence state: still ACTIVE, still APPROVED, no longer published.
    root.lifecycle_state = "deprecated"
    await session.flush()
    assert root.deletion_state == DeletionState.ACTIVE
    assert revision.revision_state == MarketRevisionState.APPROVED

    with pytest.raises(AccessDeniedError):
        await get_market_dataset_detail(session, stranger, entity_id=root.entity_id)
    with pytest.raises(AccessDeniedError):
        await resolve_approved_market_data_bundle(session, stranger, entity_id=root.entity_id)

    # ...and the owner and an Admin still read it through BOTH surfaces, so the
    # gate narrowed access by ownership rather than switching the endpoint off.
    for reader in (OWNER, ADMIN):
        assert (
            await resolve_approved_market_data_bundle(session, reader, entity_id=root.entity_id)
        )["revision_id"] == revision.revision_id
        assert (await get_market_dataset_detail(session, reader, entity_id=root.entity_id))[
            "entity_id"
        ] == root.entity_id


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


# ---- F-01 real raw-asset upload (doc 11 §3.1, §7) ---------------------------


@pytest.fixture
def fake_object_store(monkeypatch) -> dict[str, bytes]:
    """In-process object storage so upload/verify run without MinIO (mirrors
    test_trading_signal_persistence.py's fake_object_store)."""
    from entropia.infrastructure.s3 import datasets

    store: dict[str, bytes] = {}

    def _put(entity_id: str, data: bytes, *, content_type: str | None = None):
        digest = hashlib.sha256(data).hexdigest()
        key = f"market/raw/{entity_id}/{digest}"
        store[key] = data
        return key, digest

    def _get(object_key: str) -> bytes:
        return store[object_key]

    monkeypatch.setattr(datasets, "put_raw_bytes", _put)
    monkeypatch.setattr(datasets, "get_raw_bytes", _get)
    return store


async def test_upload_writes_object_storage_and_evidence_row(session, fake_object_store) -> None:
    """The client supplies only bytes + filename; object key, digest, size, and
    content type are all derived server-side (F-01 acceptance)."""
    await _seed_principals(session)
    root, _ = await md_cmd.create_market_dataset(
        session, OWNER, market_data_type=MarketDataType.OHLCV, payload={"v": 1}
    )
    await session.commit()

    content = b"timestamp,open,high,low,close,volume\n2024-01-01T00:00:00Z,1,2,0.5,1.5,100\n"
    result = await md_cmd.start_market_raw_upload(
        session,
        OWNER,
        entity_id=root.entity_id,
        content=content,
        content_type="text/csv",
        original_filename="btcusdt-1m.csv",
    )
    await session.commit()

    assert result["deduplicated"] is False
    assert result["size_bytes"] == len(content)
    expected_digest = hashlib.sha256(content).hexdigest()
    assert result["content_digest"] == expected_digest
    assert fake_object_store[f"market/raw/{root.entity_id}/{expected_digest}"] == content

    asset = await session.get(MarketRawAsset, result["asset_id"])
    assert asset is not None
    assert asset.content_digest == expected_digest
    assert asset.size_bytes == len(content)
    assert asset.original_filename == "btcusdt-1m.csv"


async def test_upload_is_content_deduplicated(session, fake_object_store) -> None:
    """Re-uploading identical bytes for the same dataset is idempotent: it
    returns the prior asset instead of writing a duplicate object/row."""
    await _seed_principals(session)
    root, _ = await md_cmd.create_market_dataset(
        session, OWNER, market_data_type=MarketDataType.OHLCV, payload={"v": 1}
    )
    await session.commit()

    content = b"timestamp,open,high,low,close,volume\n2024-01-01T00:00:00Z,1,2,0.5,1.5,100\n"
    first = await md_cmd.start_market_raw_upload(
        session, OWNER, entity_id=root.entity_id, content=content, original_filename="a.csv"
    )
    await session.commit()
    before = await _count(session, MarketRawAsset)

    second = await md_cmd.start_market_raw_upload(
        session, OWNER, entity_id=root.entity_id, content=content, original_filename="a.csv"
    )
    await session.commit()

    assert second["deduplicated"] is True
    assert second["asset_id"] == first["asset_id"]
    assert await _count(session, MarketRawAsset) == before


async def test_upload_file_type_gate_is_fail_closed(session, fake_object_store) -> None:
    """The CSV/TXT gate no longer SKIPS when the filename is absent.

    Before this fix ``if name and not name.endswith(...)`` accepted ANY payload
    as long as ``original_filename`` was ``None``/blank, so the doc 11 §3.1/§7
    server-side type control could be dropped entirely by a direct command
    caller. Every axis now fails closed with the surface's own documented code,
    and only a real .csv/.txt carrying text content is stored."""
    await _seed_principals(session)
    root, _ = await md_cmd.create_market_dataset(
        session, OWNER, market_data_type=MarketDataType.OHLCV, payload={"v": 1}
    )
    await session.commit()

    good_csv = b"timestamp,open,high,low,close,volume\n2024-01-01T00:00:00Z,1,2,0.5,1.5,100\n"
    rejected: list[tuple[str | None, bytes]] = [
        (None, good_csv),  # no filename at all (direct command caller)
        ("", good_csv),  # raw multipart part carrying filename=""
        ("   ", good_csv),  # blank-only filename
        ("dataset.xlsx", b"binary-ish"),  # unsupported extension
        ("dataset.csv", b"PK\x03\x04\x14\x00binary"),  # binary blob renamed .csv
    ]
    for filename, content in rejected:
        with pytest.raises(MarketDataFileTypeNotAllowedError) as excinfo:
            await md_cmd.start_market_raw_upload(
                session,
                OWNER,
                entity_id=root.entity_id,
                content=content,
                original_filename=filename,
            )
        assert excinfo.value.code == "MARKET_DATA_FILE_TYPE_NOT_ALLOWED"
        assert excinfo.value.details[0]["field"] == "original_filename"

    # Nothing above reached storage or the evidence table...
    assert await _count(session, MarketRawAsset) == 0
    assert fake_object_store == {}

    # ...and the supported extension with text content still uploads.
    accepted = await md_cmd.start_market_raw_upload(
        session,
        OWNER,
        entity_id=root.entity_id,
        content=good_csv,
        original_filename="dataset.csv",
    )
    await session.commit()
    assert accepted["deduplicated"] is False
    assert await _count(session, MarketRawAsset) == 1
    assert len(fake_object_store) == 1


async def test_upload_rejects_non_owner(session, fake_object_store) -> None:
    await _seed_principals(session)
    if await session.get(Principal, "user_2") is None:
        session.add(Principal(principal_id="user_2", principal_type=PrincipalType.HUMAN))
        await session.flush()
    root, _ = await md_cmd.create_market_dataset(
        session, OWNER, market_data_type=MarketDataType.OHLCV, payload={"v": 1}
    )
    await session.commit()

    other = Actor(principal_id="user_2", principal_type=PrincipalType.HUMAN, role=Role.USER)
    with pytest.raises(AccessDeniedError):
        await md_cmd.start_market_raw_upload(
            session,
            other,
            entity_id=root.entity_id,
            content=b"a,b\n1,2\n",
            original_filename="a.csv",
        )


async def test_upload_surfaces_storage_failure(session, fake_object_store, monkeypatch) -> None:
    from entropia.infrastructure.s3 import datasets

    def _boom(*_a, **_k):
        raise RuntimeError("simulated object-storage outage")

    monkeypatch.setattr(datasets, "put_raw_bytes", _boom)

    await _seed_principals(session)
    root, _ = await md_cmd.create_market_dataset(
        session, OWNER, market_data_type=MarketDataType.OHLCV, payload={"v": 1}
    )
    await session.commit()

    with pytest.raises(MarketDataUploadStorageFailedError):
        await md_cmd.start_market_raw_upload(
            session,
            OWNER,
            entity_id=root.entity_id,
            content=b"a,b\n1,2\n",
            original_filename="a.csv",
        )
    assert await _count(session, MarketRawAsset) == 0


async def test_upload_surfaces_digest_mismatch(session, fake_object_store, monkeypatch) -> None:
    """A read-back that no longer matches the uploaded bytes (storage
    corruption) fails closed instead of persisting an untrustworthy asset."""
    from entropia.infrastructure.s3 import datasets

    monkeypatch.setattr(datasets, "get_raw_bytes", lambda _key: b"corrupted-bytes")

    await _seed_principals(session)
    root, _ = await md_cmd.create_market_dataset(
        session, OWNER, market_data_type=MarketDataType.OHLCV, payload={"v": 1}
    )
    await session.commit()

    with pytest.raises(MarketDataUploadIntegrityError):
        await md_cmd.start_market_raw_upload(
            session,
            OWNER,
            entity_id=root.entity_id,
            content=b"a,b\n1,2\n",
            original_filename="a.csv",
        )
    assert await _count(session, MarketRawAsset) == 0
