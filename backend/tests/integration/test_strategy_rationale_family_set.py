"""R2-07 gap closure — one-time rationale-family set on a strategy root.

A Mainboard-inline "+ Add Strategy" creates the root with rationale_family_id
NULL while StrategyConfig requires it; ``set_strategy_rationale_family`` is the
additive owner-gated NULL→set transition. Covered here against a real database:
set persists + writes audit/outbox in the same tx; an already-set root answers
STRATEGY_RATIONALE_FAMILY_ALREADY_SET (never overwritten in place); a missing/
soft-deleted family answers RATIONALE_FAMILY_NOT_ACTIVE; a foreign owner is
rejected; a repeated Idempotency-Key replays the cached result.
"""

from __future__ import annotations

import pytest
from sqlalchemy import func, select

from entropia.application.commands import rationale as rationale_cmd
from entropia.application.commands import strategy_draft as strat_cmd
from entropia.domain.identity import Actor
from entropia.domain.lifecycle.enums import PrincipalType, Role
from entropia.infrastructure.postgres.models import AuditEvent, OutboxEvent, Principal, StrategyRoot
from entropia.shared.errors import (
    AccessDeniedError,
    RationaleFamilyNotActive,
    StrategyRationaleFamilyAlreadySetError,
    ValidationError,
)

pytestmark = pytest.mark.integration

USER1 = Actor(principal_id="user_1", principal_type=PrincipalType.HUMAN, role=Role.USER)
USER2 = Actor(principal_id="user_2", principal_type=PrincipalType.HUMAN, role=Role.USER)


async def _seed_principals(session) -> None:
    for pid in ("user_1", "user_2"):
        if await session.get(Principal, pid) is None:
            session.add(Principal(principal_id=pid, principal_type=PrincipalType.HUMAN))
    await session.flush()


async def _root_without_family(session, actor: Actor = USER1) -> str:
    """The Mainboard-inline shape: create_strategy_draft with NO family."""
    result = await strat_cmd.create_strategy_draft(
        session, actor, display_name="STRATEGY 1", rationale_family_id=None
    )
    await session.flush()
    return result["strategy_root_id"]


async def _active_family(session) -> str:
    created = await rationale_cmd.create_family(
        session, USER1, display_name="Momentum Continuation"
    )
    await session.flush()
    return created["entity_id"]


async def _count(session, model, **filters) -> int:
    stmt = select(func.count()).select_from(model)
    for key, value in filters.items():
        stmt = stmt.where(getattr(model, key) == value)
    return (await session.execute(stmt)).scalar_one()


async def test_set_family_persists_and_audits(session) -> None:
    await _seed_principals(session)
    root_id = await _root_without_family(session)
    family_id = await _active_family(session)

    result = await strat_cmd.set_strategy_rationale_family(
        session, USER1, strategy_root_id=root_id, rationale_family_id=family_id
    )
    await session.flush()

    assert result == {"strategy_root_id": root_id, "rationale_family_id": family_id}
    detail = await session.get(StrategyRoot, root_id)
    assert detail is not None and detail.rationale_family_id == family_id
    assert (await _count(session, AuditEvent, event_kind="strategy.rationale_family_set")) == 1
    assert (await _count(session, OutboxEvent, event_type="strategy.rationale_family_set")) == 1


async def test_already_set_family_is_never_overwritten(session) -> None:
    await _seed_principals(session)
    root_id = await _root_without_family(session)
    family_id = await _active_family(session)
    await strat_cmd.set_strategy_rationale_family(
        session, USER1, strategy_root_id=root_id, rationale_family_id=family_id
    )
    await session.flush()

    with pytest.raises(StrategyRationaleFamilyAlreadySetError):
        await strat_cmd.set_strategy_rationale_family(
            session, USER1, strategy_root_id=root_id, rationale_family_id=family_id
        )
    detail = await session.get(StrategyRoot, root_id)
    assert detail is not None and detail.rationale_family_id == family_id


async def test_missing_family_rejected(session) -> None:
    await _seed_principals(session)
    root_id = await _root_without_family(session)

    with pytest.raises(RationaleFamilyNotActive):
        await strat_cmd.set_strategy_rationale_family(
            session, USER1, strategy_root_id=root_id, rationale_family_id="ratfam_missing"
        )
    detail = await session.get(StrategyRoot, root_id)
    assert detail is not None and detail.rationale_family_id is None


async def test_blank_family_id_rejected(session) -> None:
    await _seed_principals(session)
    root_id = await _root_without_family(session)

    with pytest.raises(ValidationError):
        await strat_cmd.set_strategy_rationale_family(
            session, USER1, strategy_root_id=root_id, rationale_family_id="   "
        )


async def test_foreign_owner_rejected(session) -> None:
    await _seed_principals(session)
    root_id = await _root_without_family(session, USER1)
    family_id = await _active_family(session)

    with pytest.raises(AccessDeniedError):
        await strat_cmd.set_strategy_rationale_family(
            session, USER2, strategy_root_id=root_id, rationale_family_id=family_id
        )
    detail = await session.get(StrategyRoot, root_id)
    assert detail is not None and detail.rationale_family_id is None


async def test_repeated_idempotency_key_replays_cached_result(session) -> None:
    await _seed_principals(session)
    root_id = await _root_without_family(session)
    family_id = await _active_family(session)

    first = await strat_cmd.set_strategy_rationale_family(
        session,
        USER1,
        strategy_root_id=root_id,
        rationale_family_id=family_id,
        idempotency_key="idem-ratfam-1",
    )
    await session.flush()
    replay = await strat_cmd.set_strategy_rationale_family(
        session,
        USER1,
        strategy_root_id=root_id,
        rationale_family_id=family_id,
        idempotency_key="idem-ratfam-1",
    )

    assert replay == first
    assert (await _count(session, AuditEvent, event_kind="strategy.rationale_family_set")) == 1
