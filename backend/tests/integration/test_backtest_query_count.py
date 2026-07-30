"""Finding O-24b — RUN admission and the worker resolve their pins in batches.

Auto-skips without PostgreSQL (see tests/integration/conftest.py). Two loops on the
backtest hot path used to cost one round-trip per element:

* ``backtest_run_context.resolve_run_manifest_context`` dereferenced each enabled item's
  pinned work-object revision inside the item loop, and then — per Strategy — each
  pinned package revision inside the block/condition/reference/leg loop, so admission
  latency grew with BOTH the composition's item count and each strategy's leg count;
* the worker's ``_unresolved_pins`` gate re-walked the same manifest one id at a time.

These tests count the actual cursor executions against each revision table and pin BOTH
properties: the count is exactly one, and it does NOT grow with the leg or item count.
The identity map is expunged before each measurement — the seeding writes every row
through this session, so a warm session would satisfy the reads from memory and hide the
N+1 entirely.

The manifest CONTENT is asserted alongside the counts: it feeds ``execution_key``
reproducibility, so the batch must record exactly the same pins, in the same order, with
the same null details for anything that no longer resolves.
"""

from __future__ import annotations

from typing import Any

import pytest

from entropia.application.commands.backtest_run_context import resolve_run_manifest_context
from entropia.application.jobs.backtest_engine import _unresolved_pins
from entropia.domain.lifecycle.enums import PackageKind
from entropia.domain.mainboard.enums import MainboardItemKind
from entropia.infrastructure.postgres.repositories import mainboard as mb_repo
from tests.integration.test_readiness_query_count import (
    LEG_COUNT,
    MISSING_REVISION_ID,
    _counting,
    _market_revision,
    _package,
    _strategy_with_legs,
)

pytestmark = pytest.mark.integration

ITEM_COUNT = 4


async def _work_object(session, payload: dict[str, Any]) -> str:
    _root, _detail, revision = await mb_repo.create_work_object(
        session,
        owner_principal_id=None,
        created_by_principal_id=None,
        object_kind=MainboardItemKind.STRATEGY,
        payload=payload,
    )
    await session.flush()
    return revision.revision_id


async def _item_manifest(session, *, items: int, legs: int) -> dict[str, Any]:
    """A composition snapshot of ``items`` Strategy items, each with ``legs`` chain legs."""
    entries: list[dict[str, Any]] = []
    for index in range(items):
        config = await _strategy_with_legs(session, legs=legs)
        revision_id = await _work_object(session, config.model_dump(mode="json"))
        entries.append(
            {
                "item_id": f"item_{index}",
                "kind": MainboardItemKind.STRATEGY,
                "revision_id": revision_id,
                "enabled": True,
            }
        )
    await session.commit()
    return {"items": entries}


# ------------------------------------------------------------------ admission: packages


async def test_manifest_records_every_pinned_package_in_one_query(session) -> None:
    manifest = await _item_manifest(session, items=1, legs=LEG_COUNT)

    with _counting(session, "package_revision") as statements:
        context = await resolve_run_manifest_context(session, manifest)

    # Every pin is still recorded, with its resolved detail — the batch loses nothing.
    packages = context.strategy_package[0]["package_revisions"]
    assert len(packages) == LEG_COUNT + 3  # block + condition + primary reference + legs
    assert all(pkg["revision"] is not None for pkg in packages)
    assert [pkg["role"] for pkg in packages[:3]] == [
        "entry",
        "entry_condition",
        "entry_condition_reference",
    ]

    # ...at the cost of exactly ONE package_revision read (it was LEG_COUNT + 3 before).
    assert len(statements) == 1, f"expected 1 package_revision query, got {len(statements)}"
    assert " in (" in statements[0].lower()


async def test_manifest_package_query_count_does_not_grow_with_leg_count(session) -> None:
    one = await _item_manifest(session, items=1, legs=1)
    with _counting(session, "package_revision") as for_one:
        single = await resolve_run_manifest_context(session, one)

    many = await _item_manifest(session, items=1, legs=LEG_COUNT)
    with _counting(session, "package_revision") as for_many:
        multi = await resolve_run_manifest_context(session, many)

    assert len(single.strategy_package[0]["package_revisions"]) == 4
    assert len(multi.strategy_package[0]["package_revisions"]) == LEG_COUNT + 3
    assert len(for_many) == len(for_one)


async def test_an_unresolvable_pin_is_still_recorded_with_a_null_detail(session) -> None:
    """A pin that no longer resolves must stay in the manifest with ``revision: null`` so
    the worker fails the run closed — the batch must never drop or fabricate it."""
    config = await _strategy_with_legs(session, legs=LEG_COUNT, missing_leg=True)
    revision_id = await _work_object(session, config.model_dump(mode="json"))
    await session.commit()
    manifest = {
        "items": [
            {
                "item_id": "item_0",
                "kind": MainboardItemKind.STRATEGY,
                "revision_id": revision_id,
                "enabled": True,
            }
        ]
    }

    with _counting(session, "package_revision") as statements:
        context = await resolve_run_manifest_context(session, manifest)

    packages = context.strategy_package[0]["package_revisions"]
    unresolved = [pkg for pkg in packages if pkg["revision"] is None]
    assert [pkg["package_revision_id"] for pkg in unresolved] == [MISSING_REVISION_ID]
    assert len(statements) == 1


# --------------------------------------------------------------------- admission: items


async def test_item_revisions_are_resolved_in_one_query(session) -> None:
    manifest = await _item_manifest(session, items=ITEM_COUNT, legs=1)

    with _counting(session, "work_object_revision") as statements:
        context = await resolve_run_manifest_context(session, manifest)

    assert len(context.strategy_package) == ITEM_COUNT
    assert len(context.data_time) == ITEM_COUNT
    assert len(statements) == 1, f"expected 1 work_object_revision query, got {len(statements)}"


# ------------------------------------------------------------------------ worker gate


async def test_worker_pin_gate_reads_each_table_once(session) -> None:
    """``_unresolved_pins`` walks the manifest the admission stage wrote; a manifest whose
    pins all resolve must report nothing missing, and must not pay per pin to say so."""
    strategy = await _strategy_with_legs(session, legs=LEG_COUNT)
    strategy_revision_id = await _work_object(session, strategy.model_dump(mode="json"))
    pinned = await _package(session, PackageKind.INDICATOR, "ta.sma")
    market = await _market_revision(session)
    await session.commit()
    manifest = {
        "mainboard_items": [
            {
                "item_id": "item_0",
                "item_kind": MainboardItemKind.STRATEGY,
                "root_id": "root_0",
                "selected_revision_id": strategy_revision_id,
                "enabled": True,
            }
        ],
        "strategy_package_context": [
            {"package_revisions": [{"package_revision_id": pinned}], "resolver_revisions": []}
        ],
        "data_time_context": [{"market_dataset_revision_id": market}],
    }

    with (
        _counting(session, "work_object_revision") as work_object_reads,
        _counting(session, "package_revision") as package_reads,
    ):
        missing = await _unresolved_pins(session, manifest)

    assert missing == []
    assert len(work_object_reads) == 1
    assert len(package_reads) == 1
