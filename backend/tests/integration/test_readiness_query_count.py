"""Finding O-24b — Ready Check reads its pinned revisions in batches, not per leg/item.

Auto-skips without PostgreSQL (see tests/integration/conftest.py). Ready Check's own
per-strategy budget is dominated by two loops that used to issue one round-trip each
time round:

* ``resolve_indicator_plan`` dereferenced the pinned ``package_revision`` for the block,
  then again for every condition, reference package and N-ary chain leg — so the cost
  grew with the strategy's leg count on a page a user waits on;
* ``_resolve_market_data_issues`` / ``_resolve_research_sources`` dereferenced each
  item's pinned dataset revision inside the item loop.

These tests count the actual cursor executions against each revision table and pin BOTH
properties: the count is exactly one, and it does NOT grow with the leg (or item) count.
The identity map is expunged before each measurement — the seeding writes every row
through this session, so a warm session would satisfy the reads from memory and hide the
N+1 entirely.

The fail-closed paths are asserted alongside the counts: a missing revision must still
produce the SAME ``unresolved`` reason string it produced when each id was fetched on its
own (the batch must never turn 'absent row' into 'resolved').
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import pytest
from sqlalchemy import event

from entropia.application.commands.readiness_check import (
    _resolve_market_data_issues,
    _resolve_research_sources,
)
from entropia.application.queries.indicator_plan import resolve_indicator_plan
from entropia.domain.lifecycle.enums import ApprovalState, PackageKind, VisibilityScope
from entropia.domain.mainboard.enums import MainboardItemKind
from entropia.domain.market_data.enums import MarketDataType, ResolutionKind
from entropia.domain.package.enums import PackageValidationState
from entropia.domain.readiness.issues import ReadinessItemInput
from entropia.domain.strategy.config import StrategyConfig
from entropia.infrastructure.postgres.repositories import market_data as md_repo
from entropia.infrastructure.postgres.repositories import packages as pkg_repo
from entropia.infrastructure.postgres.repositories import research_data as research_repo

pytestmark = pytest.mark.integration

LEG_COUNT = 10
MISSING_REVISION_ID = "01JZZZNONEXISTENTREVISIONXX"


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


# --------------------------------------------------------------------------- fixtures


async def _package(session, kind: PackageKind, canonical_key: str) -> str:
    _root, _detail, revision = await pkg_repo.create_package(
        session,
        owner_principal_id=None,
        created_by_principal_id=None,
        package_kind=kind,
        input_contract={"source": "close"},
        output_contract={"kind": "directional_signal"},
        dependency_snapshot={"resolved": [{"canonical_key": canonical_key}]},
        visibility_scope=VisibilityScope.PUBLISHED,
        validation_state=PackageValidationState.PASSED,
        approval_state=ApprovalState.APPROVED,
    )
    await session.flush()
    return revision.revision_id


async def _market_revision(session) -> str:
    _root, revision = await md_repo.create_market_dataset(
        session,
        owner_principal_id=None,
        created_by_principal_id=None,
        market_data_type=MarketDataType.OHLCV,
        payload={"kind": "ohlcv"},
    )
    revision.resolution_kind = ResolutionKind.BAR
    revision.resolution_value = "1h"
    await session.flush()
    return revision.revision_id


async def _research_revision(session) -> str:
    _root, revision = await research_repo.create_research_dataset(
        session,
        owner_principal_id=None,
        created_by_principal_id=None,
        category_key="funding_rate",
        payload={"kind": "funding"},
    )
    await session.flush()
    return revision.revision_id


def _leg(revision_id: str) -> dict[str, Any]:
    return {
        "package_ref": {
            "package_root_id": "pkg_ref_extra",
            "package_revision_id": revision_id,
            "package_content_hash": "extrahash",
        },
        "timeframe": "same_as_base_tf",
    }


def _config(
    *,
    indicator_rev: str,
    condition_rev: str,
    reference_rev: str,
    leg_revs: list[str],
    market_rev: str,
    funding_revision_id: str | None = None,
    scaling_block_rev: str | None = None,
) -> StrategyConfig:
    """One entry block -> one condition -> a primary reference plus ``leg_revs`` legs."""
    funding: dict[str, Any] = {"enabled": False}
    if funding_revision_id is not None:
        funding = {
            "enabled": True,
            "source_root_id": "rd_root_1",
            "source_revision_id": funding_revision_id,
            "source_content_hash": "rdhash_1",
        }
    # S5c Logic-Based Scaling: a FOURTH block group the plan resolver dereferences. Its
    # pins must reach the prefetch set like entry/exit/stop, or every scaling block would
    # read as unresolved.
    scaling: dict[str, Any] = {"enabled": False}
    if scaling_block_rev is not None:
        scaling = {
            "enabled": True,
            "timeframe": "same_as_base_tf",
            "timeframe_mode": "same_strategy",
            "method": "logic_based_scaling",
            "add_size": "percent_of_initial",
            "add_size_value": "50",
            "logic_scaling": {
                "indicator_blocks": [
                    {
                        "block_id": "scale_blk_1",
                        "display_order": 0,
                        "package_ref": {
                            "package_root_id": "pkg_scale",
                            "package_revision_id": scaling_block_rev,
                            "package_content_hash": "scalehash",
                        },
                        "trigger_source": "indicator_native_trigger",
                        "timeframe": "same_as_base_tf",
                        "requirement": "required",
                    }
                ]
            },
        }
    return StrategyConfig.model_validate(
        {
            "strategy_root_id": "strat_root_1",
            "display_name": "O-24b Leg Fixture",
            "rationale_family_id": "rf_1",
            "data": {
                "instrument_id": "BTCUSDT",
                "market_dataset_root_id": "md_root_1",
                "market_dataset_revision_id": market_rev,
                "market_dataset_content_hash": "mdhash_1",
                "backtest_range": {"start": "2024-01-01T00:00:00Z", "end": "2024-12-31T23:59:59Z"},
                "initial_capital": "10000.00",
                "execution": {
                    "entry_timing": "current_candle_close",
                    "exit_timing": "current_candle_close",
                },
                "order_config": {"type": "market_order"},
                "costs": {"slippage_mode": "percentage_slippage", "slippage_value": "0"},
                "intrabar_policy": {"tick_policy": "inherit"},
                "funding": funding,
            },
            "position_entry_logic": {
                "direction_mode": "long_and_short",
                "signal_block": {"rule": "required_indicator_blocks_only"},
                "indicator_blocks": [
                    {
                        "block_id": "blk_1",
                        "display_order": 0,
                        "package_ref": {
                            "package_root_id": "pkg_ind",
                            "package_revision_id": indicator_rev,
                            "package_content_hash": "pkghash_1",
                        },
                        "trigger_source": "indicator_output_plus_condition",
                        "timeframe": "same_as_base_tf",
                        "requirement": "required",
                        "condition_blocks": [
                            {
                                "condition_block_id": "cb_1",
                                "display_order": 0,
                                "package_ref": {
                                    "package_root_id": "pkg_cond",
                                    "package_revision_id": condition_rev,
                                    "package_content_hash": "condhash",
                                },
                                "requirement": "required",
                                "validity": "1_candle",
                                "reference_timeframe": "same_as_base_tf",
                                "parameter_overrides": {"source": "close"},
                                "reference_package_ref": {
                                    "package_root_id": "pkg_ref",
                                    "package_revision_id": reference_rev,
                                    "package_content_hash": "refhash",
                                },
                                "additional_reference_package_refs": [
                                    _leg(rev) for rev in leg_revs
                                ],
                            }
                        ],
                    }
                ],
            },
            "position_exit_logic": {
                "applies_to_direction": "long_and_short",
                "close_percentage": "100",
            },
            "protection_stop_logic": {},
            "scaling_logic": scaling,
            # GH #550: ``size_semantics`` marks this revision as saved AFTER sizing became a
            # percent of resolved capital. Without it Ready Check raises the
            # STRATEGY_SIZING_SEMANTICS_UNCONFIRMED transition blocker and this fixture stops
            # being a fixture for whatever it is about.
            "position_sizing": {
                "method": "base_position_size",
                "base_position_size": "50",
                "size_semantics": "percent_of_capital",
            },
            "restrictions_filters": {"rule": "any", "filters": []},
            "conflict_position_handling": {},
        }
    )


async def _strategy_with_legs(session, *, legs: int, missing_leg: bool = False) -> StrategyConfig:
    indicator = await _package(session, PackageKind.INDICATOR, "ta.sma")
    condition = await _package(session, PackageKind.CONDITION, "cond.crosses_above")
    reference = await _package(session, PackageKind.INDICATOR, "ta.sma")
    leg_revs = [await _package(session, PackageKind.INDICATOR, "ta.ema") for _ in range(legs)]
    if missing_leg:
        leg_revs[-1] = MISSING_REVISION_ID
    market = await _market_revision(session)
    await session.commit()
    return _config(
        indicator_rev=indicator,
        condition_rev=condition,
        reference_rev=reference,
        leg_revs=leg_revs,
        market_rev=market,
    )


# ------------------------------------------------------- indicator plan (the leg axis)


async def test_indicator_plan_reads_every_pinned_package_in_one_query(session) -> None:
    config = await _strategy_with_legs(session, legs=LEG_COUNT)

    with _counting(session, "package_revision") as statements:
        plan = await resolve_indicator_plan(session, config)

    # Every leg is still fully resolved — the batch loses no data.
    assert plan.has_entry is True
    assert plan.unresolved == ()
    assert len(plan.entry_specs[0].conditions[0].extra_references) == LEG_COUNT

    # ...at the cost of exactly ONE package_revision read. Before O-24b this was
    # 3 + LEG_COUNT (block + condition + primary reference + one per leg) = 13.
    assert len(statements) == 1, f"expected 1 package_revision query, got {len(statements)}"
    assert " in (" in statements[0].lower()


async def test_plan_query_count_does_not_grow_with_leg_count(session) -> None:
    """The N+1 proof that survives a changing baseline: one leg and ten legs must cost
    the SAME number of package reads."""
    one = await _strategy_with_legs(session, legs=1)
    with _counting(session, "package_revision") as for_one:
        single = await resolve_indicator_plan(session, one)

    many = await _strategy_with_legs(session, legs=LEG_COUNT)
    with _counting(session, "package_revision") as for_many:
        multi = await resolve_indicator_plan(session, many)

    assert len(single.entry_specs[0].conditions[0].extra_references) == 1
    assert len(multi.entry_specs[0].conditions[0].extra_references) == LEG_COUNT
    assert len(for_many) == len(for_one)


async def test_a_missing_leg_revision_still_fails_closed_without_extra_queries(session) -> None:
    """The batch must never turn an absent row into a resolved leg: the last leg's id has
    no row, so the whole block stays unresolved with its leg-specific reason — and the
    miss costs no additional round-trip."""
    config = await _strategy_with_legs(session, legs=LEG_COUNT, missing_leg=True)

    with _counting(session, "package_revision") as statements:
        plan = await resolve_indicator_plan(session, config)

    assert plan.has_entry is False
    assert plan.unresolved == (
        f"entry:blk_1:condition_additional_reference_unresolved:cb_1:{LEG_COUNT - 1}",
    )
    assert len(statements) == 1


async def test_logic_based_scaling_blocks_are_prefetched_like_every_other_group(
    session,
) -> None:
    """Drift guard: the prefetch set and the dereference set are ONE traversal.

    S5c added Logic-Based Scaling as a fourth block group the resolver dereferences. A
    prefetch set that still knew only entry/exit/stop would leave the scaling pin absent
    from the map, and the resolver would report it as ``scale:...:package_revision_unresolved``
    — a silently un-scaled run that Ready Check would then block. This pins the opposite:
    the scaling block resolves, and it costs no additional query."""
    indicator = await _package(session, PackageKind.INDICATOR, "ta.sma")
    condition = await _package(session, PackageKind.CONDITION, "cond.crosses_above")
    reference = await _package(session, PackageKind.INDICATOR, "ta.sma")
    scale = await _package(session, PackageKind.INDICATOR, "ta.ema")
    market = await _market_revision(session)
    await session.commit()
    config = _config(
        indicator_rev=indicator,
        condition_rev=condition,
        reference_rev=reference,
        leg_revs=[],
        market_rev=market,
        scaling_block_rev=scale,
    )

    with _counting(session, "package_revision") as statements:
        plan = await resolve_indicator_plan(session, config)

    assert plan.unresolved == ()
    assert [spec.block_id for spec in plan.scale_specs] == ["scale_blk_1"]
    assert plan.scale_specs[0].canonical_key == "ta.ema"
    assert len(statements) == 1


# ------------------------------------------------------- readiness resolvers (item axis)


def _item(item_id: str, payload: dict[str, Any]) -> ReadinessItemInput:
    return ReadinessItemInput(
        item_id=item_id,
        kind=MainboardItemKind.STRATEGY,
        root_id=f"root_{item_id}",
        revision_id=f"rev_{item_id}",
        available=True,
        payload=payload,
    )


async def test_market_data_pins_are_resolved_in_one_query(session) -> None:
    """Each item pins its own dataset revision; the check reads them all at once and
    still blocks the ones that are not APPROVED."""
    revisions = [await _market_revision(session) for _ in range(4)]
    await session.commit()
    items = [
        _item(f"item_{index}", {"data": {"market_dataset_revision_id": revision_id}})
        for index, revision_id in enumerate(revisions)
    ]

    with _counting(session, "market_dataset_revision") as statements:
        issues = await _resolve_market_data_issues(session, items)

    # Seeded revisions are DRAFT, not APPROVED -> every item is still blocked.
    assert {issue.scope_id for issue in issues} == {item.item_id for item in items}
    assert len(statements) == 1, f"expected 1 market read, got {len(statements)}"


async def test_research_funding_pins_are_resolved_in_one_query(session) -> None:
    market = await _market_revision(session)
    revisions = [await _research_revision(session) for _ in range(4)]
    await session.commit()
    items = [
        _item(
            f"item_{index}",
            _config(
                indicator_rev="pkg_x",
                condition_rev="pkg_y",
                reference_rev="pkg_z",
                leg_revs=[],
                market_rev=market,
                funding_revision_id=revision_id,
            ).model_dump(mode="json"),
        )
        for index, revision_id in enumerate(revisions)
    ]

    with _counting(session, "research_dataset_revision") as statements:
        sources = await _resolve_research_sources(session, items)

    # Every funding pin still resolves — the batch loses no feed.
    assert len(sources) == len(items)
    assert all(source.found for source in sources)
    assert len(statements) == 1, f"expected 1 research read, got {len(statements)}"
