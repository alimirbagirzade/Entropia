"""O-13: the mutating ops that previously had NO Idempotency-Key.

Fifteen mutating endpoints accepted no idempotency key at all, so a retried submit
(the classic "did my POST land?" after a timeout) wrote a SECOND resource and a
second audit trail. Each now threads `idempotency_key` into its command and runs
the durable body through the existing `run_idempotent` helper — no new mechanism.

The contract these tests pin is the one that matters operationally: replaying the
same key returns the SAME resource and writes nothing extra.
"""

from __future__ import annotations

import pytest
from sqlalchemy import func, select

from entropia.application.commands import auth as auth_cmd
from entropia.application.commands import esp as esp_cmd
from entropia.application.commands import market_data as md_cmd
from entropia.application.commands import package_lifecycle as pkg_cmd
from entropia.application.commands import research_data as rd_cmd
from entropia.application.commands.deletion import soft_delete_entity
from entropia.application.commands.roles import change_user_role
from entropia.domain.identity import Actor
from entropia.domain.lifecycle.enums import PrincipalType, Role
from entropia.domain.market_data.enums import MarketDataType
from entropia.domain.research_data.enums import (
    AvailableTimePolicy,
    EventTimeSemantics,
    ResearchCategory,
    ResearchTimezoneMode,
    UsageScope,
)
from entropia.domain.research_data.value_objects import (
    AvailableTimeSpec,
    CategorySpec,
    FieldDefinition,
    ResearchTimezoneSpec,
)
from entropia.infrastructure.postgres.models import (
    AuditEvent,
    MarketDatasetRevision,
    Principal,
    ResearchFieldDefinition,
)
from entropia.shared.errors import IdempotencyConflictError, StaleRevisionError

pytestmark = pytest.mark.integration

ADMIN = Actor(principal_id="user_admin", principal_type=PrincipalType.HUMAN, role=Role.ADMIN)
OWNER = Actor(principal_id="user_1", principal_type=PrincipalType.HUMAN, role=Role.USER)


async def _count(session, model) -> int:
    return int((await session.execute(select(func.count()).select_from(model))).scalar_one())


async def _seed_principals(session) -> None:
    for pid in ("user_admin", "user_1"):
        if await session.get(Principal, pid) is None:
            session.add(Principal(principal_id=pid, principal_type=PrincipalType.HUMAN))
    await session.flush()


async def _market_dataset(session, key: str | None = None):
    return await md_cmd.create_market_dataset(
        session,
        OWNER,
        market_data_type=MarketDataType.OHLCV,
        payload={"instrument": "DEMO"},
        title="Demo",
        # GH #703 §Karar 1a = `(b2)` (signed 2026-08-31): a market revision naming
        # no instrument can no longer be a research link source.
        instrument_id="DEMO",
        idempotency_key=key,
    )


# --------------------------------------------------------------------------- #
# Creates                                                                      #
# --------------------------------------------------------------------------- #


async def test_create_market_dataset_replay_returns_the_same_dataset(session) -> None:
    await _seed_principals(session)
    before_rev = await _count(session, MarketDatasetRevision)
    before_audit = await _count(session, AuditEvent)

    root_a, rev_a = await _market_dataset(session, "idem-md-1")
    root_b, rev_b = await _market_dataset(session, "idem-md-1")
    await session.commit()

    assert root_a.entity_id == root_b.entity_id
    assert rev_a.revision_id == rev_b.revision_id
    # Exactly ONE dataset and ONE audit event — the replay created nothing.
    assert await _count(session, MarketDatasetRevision) == before_rev + 1
    assert await _count(session, AuditEvent) == before_audit + 1


async def test_create_market_dataset_without_a_key_still_creates_each_time(session) -> None:
    """No key = the caller opted out; behaviour is unchanged (no silent dedupe)."""
    await _seed_principals(session)
    root_a, _ = await _market_dataset(session)
    root_b, _ = await _market_dataset(session)
    await session.commit()
    assert root_a.entity_id != root_b.entity_id


async def test_same_key_different_payload_is_a_conflict(session) -> None:
    await _seed_principals(session)
    await _market_dataset(session, "idem-md-2")
    with pytest.raises(IdempotencyConflictError):
        await md_cmd.create_market_dataset(
            session,
            OWNER,
            market_data_type=MarketDataType.OHLCV,
            payload={"instrument": "OTHER"},
            title="Different title",
            idempotency_key="idem-md-2",
        )


async def test_create_successor_replay_returns_the_same_revision(session) -> None:
    await _seed_principals(session)
    root, _ = await _market_dataset(session)
    before = await _count(session, MarketDatasetRevision)

    a = await md_cmd.create_successor_revision(
        session,
        OWNER,
        entity_id=root.entity_id,
        payload={"v": 2},
        market_data_type=MarketDataType.OHLCV,
        idempotency_key="idem-succ-1",
    )
    b = await md_cmd.create_successor_revision(
        session,
        OWNER,
        entity_id=root.entity_id,
        payload={"v": 2},
        market_data_type=MarketDataType.OHLCV,
        idempotency_key="idem-succ-1",
    )
    await session.commit()

    assert a.revision_id == b.revision_id
    assert await _count(session, MarketDatasetRevision) == before + 1


async def test_confirm_schema_mapping_replay_returns_the_same_mapping(session) -> None:
    await _seed_principals(session)
    root, _ = await _market_dataset(session)
    before_audit = await _count(session, AuditEvent)

    columns = ["timestamp", "open", "high", "low", "close", "volume"]
    a = await md_cmd.confirm_market_schema_mapping(
        session,
        OWNER,
        entity_id=root.entity_id,
        market_data_type=MarketDataType.OHLCV,
        source_columns=columns,
        idempotency_key="idem-map-1",
    )
    b = await md_cmd.confirm_market_schema_mapping(
        session,
        OWNER,
        entity_id=root.entity_id,
        market_data_type=MarketDataType.OHLCV,
        source_columns=columns,
        idempotency_key="idem-map-1",
    )
    await session.commit()

    assert a.mapping_id == b.mapping_id
    # The upsert was already convergent; the audit trail is what the key protects.
    assert await _count(session, AuditEvent) == before_audit + 1


async def test_create_esp_package_replay_returns_the_same_package(session) -> None:
    await _seed_principals(session)
    payload = {
        "canonical_key": "ema.v1",
        "signature": {"params": {"length": "int"}, "return": "series"},
        "runtime_adapter": "python",
        "input_contract": {"series": "close"},
        "output_contract": {"series": "float"},
    }
    a = await esp_cmd.create_esp_package(session, OWNER, idempotency_key="idem-esp-1", **payload)
    b = await esp_cmd.create_esp_package(session, OWNER, idempotency_key="idem-esp-1", **payload)
    await session.commit()

    assert a["entity_id"] == b["entity_id"]
    assert a["revision_id"] == b["revision_id"]


async def test_sign_up_replay_returns_the_same_account(session) -> None:
    """A retried signup must replay the account, not trip USERNAME_TAKEN — which is
    why the uniqueness check lives inside the idempotent body."""
    a = await auth_cmd.sign_up(
        session,
        username="alice",
        password="correct-horse-battery",
        idempotency_key="idem-signup-1",
    )
    b = await auth_cmd.sign_up(
        session,
        username="alice",
        password="correct-horse-battery",
        idempotency_key="idem-signup-1",
    )
    await session.commit()
    assert a["user_id"] == b["user_id"]


# --------------------------------------------------------------------------- #
# autoflush=False — the API's real session semantics                           #
# --------------------------------------------------------------------------- #


async def test_creates_work_with_autoflush_disabled(session) -> None:
    """The idempotent creates re-read their rows through the stored reference; that
    re-read must not depend on autoflush.

    The API session is built with ``autoflush=False`` (``postgres/engine.py``) while
    the test fixture defaults to ``True`` — so a missing explicit ``flush()`` inside
    the idempotent body passes every test here and still 404s in the real app. This
    test pins the app's configuration so that gap cannot reopen.
    """
    await _seed_principals(session)
    session.autoflush = False

    root, revision = await _market_dataset(session, "idem-noflush-1")
    assert root.entity_id and revision.revision_id

    successor = await md_cmd.create_successor_revision(
        session,
        OWNER,
        entity_id=root.entity_id,
        payload={"v": 2},
        market_data_type=MarketDataType.OHLCV,
        idempotency_key="idem-noflush-2",
    )
    assert successor.revision_id != revision.revision_id
    await session.commit()


# --------------------------------------------------------------------------- #
# Research Data definitions                                                    #
# --------------------------------------------------------------------------- #


async def _research_dataset(session):
    market_root, market_rev = await _market_dataset(session)
    market_rev.revision_state = await _approve_market(session, market_root, market_rev)
    return await rd_cmd.create_research_dataset(
        session,
        OWNER,
        market_entity_id=market_root.entity_id,
        payload={"rows": 1},
        category=CategorySpec(category=ResearchCategory.FUNDING_RATE),
        usage_scope=UsageScope.RESEARCH_BACKTEST,
        display_name="RD",
    )


async def _approve_market(session, root, revision):
    from entropia.domain.market_data.enums import MarketRevisionState

    revision.revision_state = MarketRevisionState.VERIFIED
    await session.flush()
    await md_cmd.approve_market_dataset_revision(
        session, ADMIN, entity_id=root.entity_id, revision_id=revision.revision_id
    )
    await session.flush()
    return revision.revision_state


async def test_define_field_replay_returns_the_same_definition(session) -> None:
    await _seed_principals(session)
    root, _ = await _research_dataset(session)
    before = await _count(session, ResearchFieldDefinition)

    field = FieldDefinition(
        field_name="cpi",
        semantic_type="level",
        measurement_method="survey",
        null_semantics="missing",
        event_time_source="release_time",
        availability_rule="as_of",
        allowed_usage="research_only",
    )
    a = await rd_cmd.define_field(
        session, OWNER, entity_id=root.entity_id, field=field, idempotency_key="idem-field-1"
    )
    b = await rd_cmd.define_field(
        session, OWNER, entity_id=root.entity_id, field=field, idempotency_key="idem-field-1"
    )
    await session.commit()

    assert a.field_definition_id == b.field_definition_id
    assert await _count(session, ResearchFieldDefinition) == before + 1


async def test_define_feature_replay_returns_the_same_definition(session) -> None:
    await _seed_principals(session)
    root, _ = await _research_dataset(session)

    a = await rd_cmd.define_feature(
        session,
        OWNER,
        entity_id=root.entity_id,
        feature_name="mom_3m",
        definition={"window": 3},
        idempotency_key="idem-feat-1",
    )
    b = await rd_cmd.define_feature(
        session,
        OWNER,
        entity_id=root.entity_id,
        feature_name="mom_3m",
        definition={"window": 3},
        idempotency_key="idem-feat-1",
    )
    await session.commit()
    assert a.feature_definition_id == b.feature_definition_id


async def test_set_time_policy_replay_returns_the_same_policy(session) -> None:
    await _seed_principals(session)
    root, _ = await _research_dataset(session)

    kwargs = {
        "event_time_semantics": EventTimeSemantics.PROVIDER_EVENT_TIMESTAMP,
        "available_time": AvailableTimeSpec(policy=AvailableTimePolicy.SAME_AS_EVENT_TIME),
        "timezone_spec": ResearchTimezoneSpec(mode=ResearchTimezoneMode.UTC),
    }
    a = await rd_cmd.set_time_policy(
        session, OWNER, entity_id=root.entity_id, idempotency_key="idem-tp-1", **kwargs
    )
    b = await rd_cmd.set_time_policy(
        session, OWNER, entity_id=root.entity_id, idempotency_key="idem-tp-1", **kwargs
    )
    await session.commit()
    assert a.time_policy_id == b.time_policy_id


# --------------------------------------------------------------------------- #
# Lifecycle + O-18 soft delete                                                 #
# --------------------------------------------------------------------------- #


async def test_deprecate_package_replay_writes_one_audit(session) -> None:
    await _seed_principals(session)
    pkg = await esp_cmd.create_esp_package(
        session,
        OWNER,
        canonical_key="rsi.v1",
        signature={"params": {"length": "int"}, "return": "series"},
        runtime_adapter="python",
        input_contract={"s": "close"},
        output_contract={"s": "float"},
    )
    await session.flush()
    before = await _count(session, AuditEvent)

    a = await pkg_cmd.deprecate_package(
        session, OWNER, entity_id=pkg["entity_id"], idempotency_key="idem-dep-1"
    )
    b = await pkg_cmd.deprecate_package(
        session, OWNER, entity_id=pkg["entity_id"], idempotency_key="idem-dep-1"
    )
    await session.commit()

    assert a == b
    # Without the key the second call would raise LIFECYCLE_BLOCKED; with it the
    # stored response replays and exactly one deprecation audit exists.
    assert await _count(session, AuditEvent) == before + 1


async def test_change_user_role_replay_does_not_bump_version_twice(session) -> None:
    await _seed_principals(session)
    created = await auth_cmd.sign_up(session, username="bob", password="correct-horse-battery")
    await session.flush()

    a = await change_user_role(
        session,
        ADMIN,
        target_user_id=created["user_id"],
        new_role=Role.ADMIN,
        idempotency_key="idem-role-1",
    )
    version_after_first = a.version
    b = await change_user_role(
        session,
        ADMIN,
        target_user_id=created["user_id"],
        new_role=Role.ADMIN,
        idempotency_key="idem-role-1",
    )
    await session.commit()

    assert b.version == version_after_first
    assert b.current_role == Role.ADMIN


async def test_soft_delete_entity_replay_writes_one_audit(session) -> None:
    await _seed_principals(session)
    root, _ = await _market_dataset(session)
    await session.flush()
    before = await _count(session, AuditEvent)

    await soft_delete_entity(session, OWNER, entity_id=root.entity_id, idempotency_key="idem-del-1")
    await soft_delete_entity(session, OWNER, entity_id=root.entity_id, idempotency_key="idem-del-1")
    await session.commit()
    assert await _count(session, AuditEvent) == before + 1


async def test_soft_delete_entity_rejects_a_stale_row_version(session) -> None:
    """O-18: the generic soft-delete entry point had no concurrency token at all,
    so a racing edit could be deleted out from under its author."""
    await _seed_principals(session)
    root, _ = await _market_dataset(session)
    await session.flush()

    with pytest.raises(StaleRevisionError):
        await soft_delete_entity(
            session, OWNER, entity_id=root.entity_id, expected_row_version=root.row_version + 5
        )


async def test_soft_delete_entity_accepts_the_current_row_version(session) -> None:
    await _seed_principals(session)
    root, _ = await _market_dataset(session)
    await session.flush()

    deleted = await soft_delete_entity(
        session, OWNER, entity_id=root.entity_id, expected_row_version=root.row_version
    )
    await session.commit()
    assert deleted.entity_id == root.entity_id
