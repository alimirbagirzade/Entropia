"""Finding O-24 — listing package shares costs ONE grantee lookup, not N.

Auto-skips without PostgreSQL (see tests/integration/conftest.py). ``list_active_grants``
is unbounded (no per-package share cap exists), so resolving each grantee's account
inside the loop made the round-trip count scale with the share count. These tests
count the actual cursor executions against ``human_users`` and pin BOTH properties:
the count is exactly one, and it does not grow with the number of grantees.

The identity map is expunged before each measurement: the share command loads every
grantee row while validating the recipient, so a warm session would satisfy
``session.get`` from memory and hide the N+1 entirely.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import pytest
from sqlalchemy import event

from entropia.application.commands import sharing as sharing_cmd
from entropia.application.queries import sharing as sharing_query
from entropia.domain.identity import Actor
from entropia.domain.lifecycle.enums import PackageKind, PrincipalType, Role, VisibilityScope
from entropia.infrastructure.postgres.models import HumanUser, Principal
from entropia.infrastructure.postgres.repositories import packages as pkg_repo

pytestmark = pytest.mark.integration

OWNER = Actor(principal_id="user_1", principal_type=PrincipalType.HUMAN, role=Role.USER)
GRANTEE_COUNT = 4


def _grantee_email(index: int) -> str:
    return f"grantee{index}@example.com"


async def _seed(session, *, grantees: int) -> None:
    ids = ["user_1", *(f"user_g{i}" for i in range(grantees))]
    for pid in ids:
        if await session.get(Principal, pid) is None:
            session.add(Principal(principal_id=pid, principal_type=PrincipalType.HUMAN))
    await session.flush()
    for position, pid in enumerate(ids):
        if await session.get(HumanUser, pid) is not None:
            continue
        is_owner = pid == "user_1"
        session.add(
            HumanUser(
                user_id=pid,
                username="owner" if is_owner else f"grantee{position - 1}",
                email=None if is_owner else _grantee_email(position - 1),
                display_name="Owner" if is_owner else f"Grantee {position - 1}",
                current_role=Role.USER,
                status="active",
            )
        )
    await session.flush()


async def _package_shared_with(session, *, grantees: int) -> str:
    await _seed(session, grantees=grantees)
    root, _detail, _revision = await pkg_repo.create_package(
        session,
        owner_principal_id="user_1",
        created_by_principal_id="user_1",
        package_kind=PackageKind.INDICATOR,
        input_contract={"name": "Shared Indicator"},
        output_contract={"output_kinds": ["signal"]},
        dependency_snapshot={},
        visibility_scope=VisibilityScope.PRIVATE,
    )
    for index in range(grantees):
        await sharing_cmd.share_package(
            session, OWNER, entity_id=root.entity_id, grantee_email=_grantee_email(index)
        )
    await session.commit()
    return root.entity_id


@contextmanager
def _counting(session, table: str) -> Iterator[list[str]]:
    """Record every cursor execution touching ``table`` (cold identity map)."""
    session.expunge_all()
    engine = session.get_bind()
    sync_engine = getattr(engine, "sync_engine", engine)
    seen: list[str] = []

    def _record(_conn, _cursor, statement, _params, _context, _many) -> None:
        if table in statement.lower():
            seen.append(statement)

    event.listen(sync_engine, "before_cursor_execute", _record)
    try:
        yield seen
    finally:
        event.remove(sync_engine, "before_cursor_execute", _record)


async def test_grantee_lookup_is_a_single_batched_query(session) -> None:
    entity_id = await _package_shared_with(session, grantees=GRANTEE_COUNT)

    with _counting(session, "human_users") as statements:
        listing = await sharing_query.list_package_shares(session, OWNER, entity_id=entity_id)

    # Every grantee is still fully resolved — the batch loses no data.
    assert len(listing["shares"]) == GRANTEE_COUNT
    assert {s["grantee_email"] for s in listing["shares"]} == {
        _grantee_email(i) for i in range(GRANTEE_COUNT)
    }
    assert all(s["grantee_display_name"] for s in listing["shares"])

    # ...at the cost of exactly ONE human_users read (it was GRANTEE_COUNT before).
    assert len(statements) == 1, f"expected 1 human_users query, got {len(statements)}"
    assert " in (" in statements[0].lower()


async def test_lookup_count_does_not_grow_with_grantee_count(session) -> None:
    """The N+1 proof that survives a changing baseline: one grantee and many
    grantees must cost the SAME number of account reads."""
    one = await _package_shared_with(session, grantees=1)
    with _counting(session, "human_users") as for_one:
        single = await sharing_query.list_package_shares(session, OWNER, entity_id=one)

    many = await _package_shared_with(session, grantees=GRANTEE_COUNT)
    with _counting(session, "human_users") as for_many:
        multi = await sharing_query.list_package_shares(session, OWNER, entity_id=many)

    assert len(single["shares"]) == 1
    assert len(multi["shares"]) == GRANTEE_COUNT
    assert len(for_many) == len(for_one)


async def test_package_with_no_grants_skips_the_lookup_entirely(session) -> None:
    """An empty grant list short-circuits without a round-trip."""
    await _seed(session, grantees=0)
    root, _detail, _revision = await pkg_repo.create_package(
        session,
        owner_principal_id="user_1",
        created_by_principal_id="user_1",
        package_kind=PackageKind.INDICATOR,
        input_contract={"name": "Unshared Indicator"},
        output_contract={"output_kinds": ["signal"]},
        dependency_snapshot={},
        visibility_scope=VisibilityScope.PRIVATE,
    )
    await session.commit()

    with _counting(session, "human_users") as statements:
        listing = await sharing_query.list_package_shares(session, OWNER, entity_id=root.entity_id)

    assert listing["shares"] == []
    assert statements == []
