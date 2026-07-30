"""Finding O-24 — listing package shares costs a FIXED number of reads, not N.

Auto-skips without PostgreSQL (see tests/integration/conftest.py). Two defects sat
behind this endpoint: the grantee account was resolved inside the loop (one read per
grant), and ``list_active_grants`` was unbounded (no per-package share cap exists),
so a single package's grant count decided how much work the request did. These tests
count actual cursor executions and pin both halves: the ``human_users`` read is
exactly one, and the TOTAL read count does not move between one grantee and fifty.

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
from entropia.shared.pagination import PageParams

pytestmark = pytest.mark.integration

OWNER = Actor(principal_id="user_1", principal_type=PrincipalType.HUMAN, role=Role.USER)
GRANTEE_COUNT = 4
# The O-24 check step's fixture size. Kept off the cheap N+1 tests above so the
# suite pays for fifty share commands only where fifty is the point.
LARGE_GRANTEE_COUNT = 50

# What one page of this endpoint costs, whatever the grant count: the package root,
# the package detail, the bounded grant page, and the ONE batched grantee lookup.
#
# The finding's target was "<= 3", written before the reads were actually counted:
# root and detail are two separate pre-existing reads that have nothing to do with
# the N+1 and could only be removed by joining two repository functions that other
# queries also call. Four is the honest floor, and the property that matters is the
# one asserted below — the count is CONSTANT. Before the fix fifty grants cost 53.
EXPECTED_TOTAL_QUERIES = 4


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
def _counting(session, table: str | None = None) -> Iterator[list[str]]:
    """Record cursor executions — all of them, or only those naming ``table``.

    The identity map is dropped first so every read is a real round-trip.
    """
    session.expunge_all()
    engine = session.get_bind()
    sync_engine = getattr(engine, "sync_engine", engine)
    seen: list[str] = []

    def _record(_conn, _cursor, statement, _params, _context, _many) -> None:
        if table is None or table in statement.lower():
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


async def test_fifty_grantees_cost_the_same_total_reads_as_one(session) -> None:
    """The O-24 check step: TOTAL statements, not just the grantee lookup.

    Counting every statement is what makes this a regression test rather than a
    spot check — reintroducing a per-grant read anywhere in the projection (an
    audit lookup, a permission re-check) fails here even if ``human_users`` stays
    batched.
    """
    one = await _package_shared_with(session, grantees=1)
    with _counting(session) as for_one:
        single = await sharing_query.list_package_shares(session, OWNER, entity_id=one)

    many = await _package_shared_with(session, grantees=LARGE_GRANTEE_COUNT)
    with _counting(session) as for_fifty:
        multi = await sharing_query.list_package_shares(session, OWNER, entity_id=many)

    # All fifty are returned — the default page (100) is above the fixture size, so
    # a constant read count here is batching, not truncation.
    assert len(single["shares"]) == 1
    assert len(multi["shares"]) == LARGE_GRANTEE_COUNT
    assert multi["meta"] == {"cursor": None, "has_more": False}

    assert len(for_fifty) == EXPECTED_TOTAL_QUERIES, (
        f"expected {EXPECTED_TOTAL_QUERIES} statements for "
        f"{LARGE_GRANTEE_COUNT} grantees, got {len(for_fifty)}:\n" + "\n".join(for_fifty)
    )
    assert len(for_fifty) == len(for_one), "the read count moved with the grant count"


async def test_page_limit_bounds_the_grant_scan(session) -> None:
    """An explicit limit truncates the page AND says so — never silently."""
    entity_id = await _package_shared_with(session, grantees=LARGE_GRANTEE_COUNT)

    with _counting(session) as statements:
        page = await sharing_query.list_package_shares(
            session, OWNER, entity_id=entity_id, params=PageParams(limit=10)
        )

    assert len(page["shares"]) == 10
    assert page["meta"]["has_more"] is True
    # The cursor is the LAST returned grant, so the next page resumes after it.
    assert page["meta"]["cursor"] == page["shares"][-1]["share_id"]
    # A smaller page is not a cheaper page in round-trips — it is the same four.
    assert len(statements) == EXPECTED_TOTAL_QUERIES


async def test_cursor_walks_every_grant_exactly_once(session) -> None:
    """Paging to the end returns all fifty grants, no gaps and no repeats."""
    entity_id = await _package_shared_with(session, grantees=LARGE_GRANTEE_COUNT)

    seen: list[str] = []
    cursor: str | None = None
    for _page in range(10):  # bounded so a broken cursor fails instead of hanging
        result = await sharing_query.list_package_shares(
            session, OWNER, entity_id=entity_id, params=PageParams(cursor=cursor, limit=20)
        )
        seen.extend(share["share_id"] for share in result["shares"])
        cursor = result["meta"]["cursor"]
        if not result["meta"]["has_more"]:
            break

    assert len(seen) == LARGE_GRANTEE_COUNT
    assert len(set(seen)) == LARGE_GRANTEE_COUNT, "a grant was returned on two pages"
    assert seen == sorted(seen), "paging broke the stable oldest-first order"
    # The tail page advertises no cursor — a client never asks for an empty page.
    assert cursor is None


async def test_default_page_is_the_surface_cap_not_the_generic_default(session) -> None:
    """Omitting params must not fall back to PageParams' generic limit of 20.

    The share panel renders one flat list with no "next page" control, so a 20-row
    default would hide grantees 21..100 from a UI that cannot ask for them.
    """
    assert sharing_query.DEFAULT_SHARE_PAGE_LIMIT == 100

    entity_id = await _package_shared_with(session, grantees=LARGE_GRANTEE_COUNT)
    listing = await sharing_query.list_package_shares(session, OWNER, entity_id=entity_id)

    assert len(listing["shares"]) == LARGE_GRANTEE_COUNT
    assert listing["meta"]["has_more"] is False
