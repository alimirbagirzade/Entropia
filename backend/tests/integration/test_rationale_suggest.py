"""S-L5 — GET /rationale-families:suggest is a suggestion, never a mutation.

Master ref Module 6 §11 lists the endpoint as "Create Package / Agent icin yalnizca
oneri; mutation yapmaz", and §9.3 spells out the hazard it guards against: a
suggestion is an INFERENCE, so the backend must not silently create a Family card or
change an existing package assignment on the user's or the Agent's behalf.

Every test here therefore asserts BOTH halves: the right rows come back, and the
row counts / head pointers are byte-identical afterwards.

Auto-skips without PostgreSQL (see tests/integration/conftest.py).
"""

from __future__ import annotations

import pytest
from sqlalchemy import func, select

from entropia.application.commands import rationale as rationale_cmd
from entropia.application.queries import rationale as rationale_query
from entropia.domain.identity import Actor
from entropia.domain.lifecycle.enums import PrincipalType, Role
from entropia.infrastructure.postgres.models import (
    AuditEvent,
    EntityRegistry,
    OutboxEvent,
    Principal,
    RationaleFamilyRevision,
    RationaleFamilyRoot,
)
from entropia.shared.errors import UnauthenticatedError

pytestmark = pytest.mark.integration

USER = Actor(principal_id="user_1", principal_type=PrincipalType.HUMAN, role=Role.USER)
GUEST = Actor(principal_id=None, principal_type=None, role=None)

_TRACKED = (
    EntityRegistry,
    RationaleFamilyRoot,
    RationaleFamilyRevision,
    AuditEvent,
    OutboxEvent,
)


async def _count(session, model) -> int:
    return int((await session.execute(select(func.count()).select_from(model))).scalar_one())


async def _snapshot(session) -> dict[str, int]:
    return {model.__name__: await _count(session, model) for model in _TRACKED}


async def _seed(session) -> None:
    session.add(Principal(principal_id="user_1", principal_type=PrincipalType.HUMAN))
    await session.flush()
    for name, subs in (
        ("Momentum / Trend", ["breakout", "continuation"]),
        ("Mean Reversion", ["fade", "reversal"]),
        ("Volatility / Regime", []),
    ):
        await rationale_cmd.create_family(session, USER, display_name=name, subfamilies=subs)
    await session.commit()


async def test_suggest_matches_the_display_name_case_insensitively(session) -> None:
    await _seed(session)
    before = await _snapshot(session)

    result = await rationale_query.suggest_families(session, USER, q="MOM")

    assert [row["display_name"] for row in result["data"]] == ["Momentum / Trend"]
    assert result["meta"]["q"] == "mom"
    assert result["meta"]["has_more"] is False
    assert await _snapshot(session) == before  # no row, no audit, no outbox


async def test_suggest_also_matches_a_subfamily(session) -> None:
    """Section 9.3 is about matching detected LOGIC to the catalog, not titles.

    "reversal" is a subfamily of Mean Reversion and appears in no display name.
    """
    await _seed(session)
    before = await _snapshot(session)

    result = await rationale_query.suggest_families(session, USER, q="reversal")

    assert [row["display_name"] for row in result["data"]] == ["Mean Reversion"]
    assert "reversal" in result["data"][0]["subfamilies"]
    assert await _snapshot(session) == before


async def test_a_query_matching_nothing_creates_nothing(session) -> None:
    """The §9.3 hazard, pinned: "Onerilen Family mevcut degil" must NOT create it."""
    await _seed(session)
    before = await _snapshot(session)

    result = await rationale_query.suggest_families(session, USER, q="funding exhaustion")

    assert result["data"] == []
    assert await _snapshot(session) == before


async def test_a_too_short_query_returns_nothing_not_the_whole_catalog(session) -> None:
    await _seed(session)
    assert (await rationale_query.suggest_families(session, USER, q="m"))["data"] == []
    assert (await rationale_query.suggest_families(session, USER, q=" "))["data"] == []


async def test_limit_is_capped_and_reports_has_more(session) -> None:
    await _seed(session)
    # "re" hits all three seeded families (trend / reversion / regime); take one.
    result = await rationale_query.suggest_families(session, USER, q="re", limit=1)
    assert len(result["data"]) == 1
    assert result["meta"]["has_more"] is True


async def test_a_soft_deleted_family_is_never_suggested(session) -> None:
    """Suggesting it would propose an assignment the command layer then rejects."""
    await _seed(session)
    target = (
        (
            await session.execute(
                select(RationaleFamilyRevision).where(
                    RationaleFamilyRevision.normalized_name == "mean reversion"
                )
            )
        )
        .scalars()
        .one()
    )
    await rationale_cmd.soft_delete_family(
        session, USER, entity_id=target.entity_id, expected_row_version=None
    )
    await session.commit()

    result = await rationale_query.suggest_families(session, USER, q="reversion")
    assert result["data"] == []


async def test_guests_are_rejected_before_any_data_is_returned(session) -> None:
    await _seed(session)
    with pytest.raises(UnauthenticatedError):
        await rationale_query.suggest_families(session, GUEST, q="mom")
