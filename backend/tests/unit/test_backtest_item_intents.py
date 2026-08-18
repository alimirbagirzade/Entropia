"""Shared-snapshot item intents — pure unit tests (ADR 0002 §6/§7, doc 13 §8.4 step 4).

Proves the one sentence this slice implements: every active Mainboard item at a valuation
point forms its intent against the SAME immutable portfolio snapshot, side-effect-free,
naming the exact pinned revision it speaks for; that a suppressed intent is emitted and
traced rather than dropped; that mandatory stops/exits are formed BEFORE the snapshot
exists so the canonical order cannot invert; that the sizes come from the shipped sizing
chain (checked against a real ``run_engine`` fill) with the sleeve cap deliberately left
to a later phase; and that item order is the pinned axis, never the order a caller's
mapping happened to be built in.

Containment is part of the contract: nothing in production imports this layer yet, so the
rollback stays "delete the module" and no shipped digest can move because it exists."""

from __future__ import annotations

import inspect
import re
import time
from collections.abc import Iterator
from dataclasses import astuple
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from entropia.domain.backtest.engine import EngineOutput, run_engine
from entropia.domain.backtest.execution.clock import ItemBarStream, ItemTickView, iter_ticks
from entropia.domain.backtest.execution.costs import FillCosts, _cost_params
from entropia.domain.backtest.execution.intents import (
    ACTIONABLE_KINDS,
    INTENT_CONTRACT_VERSION,
    INTENT_LAYER_REASONS,
    ITEM_KIND_DOES_NOT_EXECUTE,
    MANDATORY_KINDS,
    NO_BAR_AT_TICK,
    NO_SIGNAL_AT_TICK,
    ClosingSize,
    EntrySizing,
    ItemDecision,
    ItemIdentity,
    MandatoryEventNotAnIntentError,
    MismatchedItemViewError,
    MissingSizingInputsError,
    NoDecisionAtTickError,
    PortfolioSnapshot,
    ScaleSizing,
    SnapshotMismatchError,
    UndirectedIntentError,
    UnknownItemError,
    build_snapshot,
    form_intent,
    form_intents,
    form_mandatory_intent,
    idle_decision,
    snapshot_identities,
)
from entropia.domain.backtest.execution.scaling import resolve_scale_rejection
from entropia.domain.backtest.execution.sizing import _position_size, blocked_reason
from entropia.domain.backtest.execution.state import _Bar, _normalize
from entropia.domain.backtest.manifest import ENGINE_VERSION
from entropia.domain.strategy.config import StrategyConfig
from tests.unit.engine_signal_plan import sma_entry_plan

_ZERO = Decimal("0")
_COSTS = FillCosts(half_spread=Decimal("0"), slippage=Decimal("0"), commission=Decimal("0"))


# ---------------------------------------------------------------------------- fixtures


def _bar(ts: str, close: str = "100") -> _Bar:
    return _Bar(
        timestamp=ts,
        open=Decimal(close),
        high=Decimal(close),
        low=Decimal(close),
        close=Decimal(close),
        volume=Decimal("1"),
    )


def _view(
    item_id: str = "item_a",
    *,
    t_ms: int = 1_700_000_000_000,
    pin_ordinal: int = 0,
    bars: tuple[_Bar, ...] = (),
    last_closed: _Bar | None = None,
    last_closed_t_ms: int | None = None,
) -> ItemTickView:
    resolved_last = last_closed if last_closed is not None else (bars[-1] if bars else None)
    resolved_t = last_closed_t_ms if last_closed_t_ms is not None else (t_ms if bars else None)
    return ItemTickView(
        item_id=item_id,
        pin_ordinal=pin_ordinal,
        t_ms=t_ms,
        bars=bars,
        last_closed=resolved_last,
        last_closed_t_ms=resolved_t,
    )


def _identity(
    item_id: str = "item_a", *, kind: str = "strategy", pin_ordinal: int = 0
) -> ItemIdentity:
    return ItemIdentity(
        item_id=item_id,
        item_kind=kind,
        pin_ordinal=pin_ordinal,
        root_id=f"root_{item_id}",
        selected_revision_id=f"rev_{item_id}",
        item_label=f"Label {item_id}",
    )


def _snapshot(
    *,
    t_ms: int = 1_700_000_000_000,
    equity: str = "10000",
    reserve: str = "1000",
    sleeves: dict[str, str] | None = None,
    deployed: dict[str, str] | None = None,
) -> Any:
    sleeve_map = {k: Decimal(v) for k, v in (sleeves or {"item_a": "3600"}).items()}
    deployed_map = {k: Decimal((deployed or {}).get(k, "0")) for k in sleeve_map}
    return build_snapshot(
        t_ms=t_ms,
        equity=Decimal(equity),
        reserve_nominal=Decimal(reserve),
        sleeve_capacity=sleeve_map,
        deployed_notional=deployed_map,
    )


def _entry_sizing(config: StrategyConfig, base: str = "10000") -> EntrySizing:
    return EntrySizing(
        config=config,
        fill_costs=_COSTS,
        base=Decimal(base),
        base_source="portfolio_equity",
    )


def _config(
    *,
    method: str = "base_position_size",
    slippage: str = "0",
) -> StrategyConfig:
    sizing: dict[str, Any] = {"method": method}
    if method == "base_position_size":
        sizing["base_position_size"] = "50"
    if method == "risk_based_sizing":
        sizing["risk_based"] = {"risk_percentage_per_trade": "2", "stop_loss_point": "4"}
    return StrategyConfig.model_validate(
        {
            "strategy_root_id": "strat_root_1",
            "display_name": "Intent Fixture",
            "rationale_family_id": "rf_1",
            "data": {
                "instrument_id": "BTCUSDT",
                "market_dataset_root_id": "md_root_1",
                "market_dataset_revision_id": "md_rev_1",
                "market_dataset_content_hash": "mdhash_1",
                "backtest_range": {"start": "2024-01-01T00:00:00Z", "end": "2024-12-31T23:59:59Z"},
                "initial_capital": "10000.00",
                "execution": {
                    "entry_timing": "current_candle_close",
                    "exit_timing": "current_candle_close",
                },
                "order_config": {"type": "market_order"},
                "costs": {"slippage_mode": "percentage_slippage", "slippage_value": slippage},
                "intrabar_policy": {"tick_policy": "inherit"},
                "funding": {"enabled": False},
            },
            "position_entry_logic": {
                "direction_mode": "long_and_short",
                "signal_block": {"rule": "required_indicator_blocks_only"},
                "indicator_blocks": [
                    {
                        "block_id": "blk_1",
                        "display_order": 0,
                        "package_ref": {
                            "package_root_id": "pkg_1",
                            "package_revision_id": "pkgrev_1",
                            "package_content_hash": "pkghash_1",
                        },
                        "trigger_source": "indicator_native_trigger",
                        "requirement": "required",
                    }
                ],
            },
            "position_exit_logic": {
                "applies_to_direction": "long_and_short",
                "close_percentage": "100",
            },
            "protection_stop_logic": {
                "percentage_stop": {"enabled": True, "loss_percentage": "1.0"}
            },
            "position_sizing": sizing,
            "restrictions_filters": {"rule": "any", "filters": []},
            "conflict_position_handling": {},
        }
    )


def _raw(ts: str, o: str, h: str, low: str, c: str) -> dict[str, Any]:
    return {"timestamp": ts, "open": o, "high": h, "low": low, "close": c}


def _breakout_bars() -> list[dict[str, Any]]:
    bars = [_raw(f"2024-01-{i + 1:02d}T00:00:00Z", "100", "100", "100", "100") for i in range(20)]
    bars.append(_raw("2024-01-21T00:00:00Z", "100", "102", "100", "102"))
    return bars


def _batched(rows: list[dict[str, Any]], size: int = 8) -> Iterator[list[dict[str, Any]]]:
    for start in range(0, len(rows), size):
        yield rows[start : start + size]


def _run(config: StrategyConfig, rows: list[dict[str, Any]]) -> EngineOutput:
    return run_engine(
        strategy_config=config,
        bar_batches=_batched(rows),
        execution_key="exec_key_intents",
        indicator_plan=sma_entry_plan(),
    )


# ------------------------------------------------------------------------ the snapshot


def test_a_snapshot_derives_allocatable_and_unallocated_from_one_equity() -> None:
    # doc 13 §14 test 10's arithmetic: P0=10000, R0=1000 -> A0=9000; 40/35/15 shares
    # yield 3600/3150/1350 with U0=900. Deriving A(t) and U(t) inside build_snapshot is
    # what stops the three figures from ever being published inconsistently.
    snap = _snapshot(
        equity="10000",
        reserve="1000",
        sleeves={"a": "3600", "b": "3150", "c": "1350"},
    )
    assert snap.allocatable == Decimal("9000")
    assert snap.unallocated == Decimal("900")
    assert snap.item_ids == ("a", "b", "c")


def test_reserve_nominal_is_fixed_and_never_re_derived_from_equity() -> None:
    """R0 is fixed nominal (doc 13 §0.2, §6.1; Modül 11 §1.2.6). Below R0 the allocatable
    pool floors at zero — it never goes negative and R0 never shrinks to fit."""
    snap = _snapshot(equity="400", reserve="1000", sleeves={"a": "0"})
    assert snap.reserve_nominal == Decimal("1000")
    assert snap.allocatable == _ZERO


def test_a_snapshot_refuses_an_item_it_only_half_values() -> None:
    with pytest.raises(UnknownItemError):
        build_snapshot(
            t_ms=1,
            equity=Decimal("10"),
            reserve_nominal=_ZERO,
            sleeve_capacity={"a": Decimal("1"), "b": Decimal("1")},
            deployed_notional={"a": _ZERO},
        )


def test_a_published_snapshots_maps_cannot_be_edited_afterwards() -> None:
    # "Every item sees the same snapshot" has to be structural: an item that could edit
    # sleeve_capacity would silently change what its siblings size against.
    snap = _snapshot(sleeves={"item_a": "3600", "item_b": "1000"})
    with pytest.raises(TypeError):
        snap.sleeve_capacity["item_a"] = Decimal("999999")
    with pytest.raises(TypeError):
        snap.deployed_notional["item_b"] = Decimal("1")


def test_snapshot_identity_ignores_the_order_the_maps_were_built_in() -> None:
    """A snapshot assembled from a mapping the DB happened to iterate differently is the
    same valuation, so its identity must not move (ADR §11 determinism)."""
    forward = build_snapshot(
        t_ms=7,
        equity=Decimal("100"),
        reserve_nominal=Decimal("10"),
        sleeve_capacity={"a": Decimal("1"), "b": Decimal("2")},
        deployed_notional={"a": _ZERO, "b": _ZERO},
    )
    reversed_ = build_snapshot(
        t_ms=7,
        equity=Decimal("100"),
        reserve_nominal=Decimal("10"),
        sleeve_capacity={"b": Decimal("2"), "a": Decimal("1")},
        deployed_notional={"b": _ZERO, "a": _ZERO},
    )
    assert forward.identity == reversed_.identity


def test_snapshot_identity_discriminates_a_moved_valuation() -> None:
    assert _snapshot(equity="10000").identity != _snapshot(equity="10001").identity
    assert _snapshot(t_ms=1).identity != _snapshot(t_ms=2).identity
    assert (
        _snapshot(deployed={"item_a": "10"}).identity
        != _snapshot(deployed={"item_a": "20"}).identity
    )


def test_remaining_sleeve_capacity_is_a_cap_not_a_wallet() -> None:
    """ADR §7: ``remaining = max(0, Ci(t) - deployed_i)``, and an over-deployed item
    reports zero headroom rather than a negative wallet balance."""
    snap = _snapshot(sleeves={"item_a": "3600"}, deployed={"item_a": "1000"})
    assert snap.remaining_sleeve_capacity("item_a") == Decimal("2600")
    over = _snapshot(sleeves={"item_a": "100"}, deployed={"item_a": "500"})
    assert over.remaining_sleeve_capacity("item_a") == _ZERO
    with pytest.raises(UnknownItemError):
        snap.remaining_sleeve_capacity("item_zzz")


# --------------------------------------------------------------- one shared snapshot


def test_every_item_at_a_tick_forms_its_intent_against_one_snapshot_identity() -> None:
    """doc 13 §8.4 step 4 / §14 test 11: all items see the SAME valuation. Checked over
    the intents alone, so it survives a serialization boundary that loses object ids."""
    snap = _snapshot(sleeves={"item_a": "3600", "item_b": "3150", "item_c": "1350"})
    intents = [
        form_intent(
            identity=_identity(item, pin_ordinal=ordinal),
            view=_view(item, pin_ordinal=ordinal, bars=(_bar("2024-01-01T00:00:00Z"),)),
            snapshot=snap,
            decision=ItemDecision(kind="no_op", reason=NO_SIGNAL_AT_TICK),
        )
        for ordinal, item in enumerate(("item_a", "item_b", "item_c"))
    ]
    assert snapshot_identities(intents) == {snap.identity}
    assert {i.dependencies["portfolio_equity"] for i in intents} == {snap.equity}


def test_a_snapshot_from_another_tick_is_refused() -> None:
    with pytest.raises(SnapshotMismatchError):
        form_intent(
            identity=_identity(),
            view=_view(t_ms=1_700_000_060_000, bars=(_bar("2024-01-01T00:01:00Z"),)),
            snapshot=_snapshot(t_ms=1_700_000_000_000),
            decision=ItemDecision(kind="no_op", reason=NO_SIGNAL_AT_TICK),
        )


def test_an_item_the_snapshot_does_not_value_cannot_form_an_intent() -> None:
    # A snapshot that omits a participating item is not a portfolio-wide valuation.
    with pytest.raises(UnknownItemError):
        form_intent(
            identity=_identity("item_missing"),
            view=_view("item_missing", bars=(_bar("2024-01-01T00:00:00Z"),)),
            snapshot=_snapshot(sleeves={"item_a": "3600"}),
            decision=ItemDecision(kind="no_op", reason=NO_SIGNAL_AT_TICK),
        )


# ------------------------------------------------------------------------- the kinds


def test_an_entry_intent_carries_a_pre_cap_size_from_the_shipped_sizing_chain() -> None:
    config = _config(method="risk_based_sizing")
    intent = form_intent(
        identity=_identity(),
        view=_view(bars=(_bar("2024-01-01T00:00:00Z", "200"),)),
        snapshot=_snapshot(),
        decision=ItemDecision(kind="entry", direction="long", reason="entry_signal"),
        sizing=_entry_sizing(config, base="10000"),
    )
    expected = _position_size(config, Decimal("200"), Decimal("10000"), Decimal("1"))
    assert intent.kind == "entry"
    assert intent.desired_size == expected == Decimal("50")
    assert intent.reference_price == Decimal("200")
    assert intent.effective_price == Decimal("200")
    assert intent.is_actionable


def test_a_scale_in_intent_sizes_through_the_ladder_not_the_entry_chain() -> None:
    """The ladder is deliberately independent of ``_position_size`` — no leverage, no
    signal-strength multiplier (§11.3). Routing it through the entry chain would move
    shipped scale sizes."""
    intent = form_intent(
        identity=_identity(),
        view=_view(bars=(_bar("2024-01-01T00:00:00Z", "150"),)),
        snapshot=_snapshot(),
        decision=ItemDecision(kind="scale_in", direction="long", reason="scale_layer_added"),
        sizing=ScaleSizing(
            basis="percent_of_initial",
            value=Decimal("50"),
            initial_size=Decimal("8"),
            current_size=Decimal("8"),
        ),
    )
    assert intent.desired_size == Decimal("4")
    # Priceless by design: the ladder never re-prices, so the reference price passes
    # through unadjusted rather than being run through the fill-cost model.
    assert intent.effective_price == intent.reference_price == Decimal("150")


def test_a_mandatory_exit_is_formed_before_any_snapshot_exists() -> None:
    """ADR §6 rule 4 / Modül 11 §5.2. The P3 former takes no snapshot ARGUMENT, so the
    ordering guarantee is structural: it cannot size against an E(t) that does not exist
    yet, whatever a caller intends."""
    for kind, reason, units in (
        ("exit", "stop_loss", "50"),
        ("partial_exit", "exit_signal", "25"),
    ):
        intent = form_mandatory_intent(
            identity=_identity(),
            view=_view(bars=(_bar("2024-01-01T00:00:00Z", "95"),)),
            decision=ItemDecision(kind=kind, direction="long", reason=reason),  # type: ignore[arg-type]
            sizing=ClosingSize(units=Decimal(units)),
        )
        assert intent.phase == "P3"
        assert intent.snapshot_identity is None
        assert intent.reason == reason
        # The close size is the one the P3 resolver already determined, recorded verbatim
        # rather than re-derived from close_percentage a second time.
        assert intent.desired_size == Decimal(units)
        assert kind in MANDATORY_KINDS


def test_a_mandatory_exit_without_its_close_size_fails_closed() -> None:
    """A mandatory exit recorded as size 0 would read as "closed nothing" — a different,
    and false, statement from "the close size was not supplied"."""
    with pytest.raises(MissingSizingInputsError):
        form_mandatory_intent(
            identity=_identity(),
            view=_view(bars=(_bar("2024-01-01T00:00:00Z", "95"),)),
            decision=ItemDecision(kind="exit", direction="long", reason="stop_loss"),
        )


def test_a_mandatory_event_offered_to_the_post_snapshot_former_is_refused() -> None:
    with pytest.raises(MandatoryEventNotAnIntentError):
        form_intent(
            identity=_identity(),
            view=_view(bars=(_bar("2024-01-01T00:00:00Z"),)),
            snapshot=_snapshot(),
            decision=ItemDecision(kind="exit", direction="long", reason="stop_loss"),
        )


def test_a_discretionary_entry_offered_to_the_pre_snapshot_former_is_refused() -> None:
    # The refusal is symmetric: an entry has no meaning before E(t) is published either.
    with pytest.raises(MandatoryEventNotAnIntentError):
        form_mandatory_intent(
            identity=_identity(),
            view=_view(bars=(_bar("2024-01-01T00:00:00Z"),)),
            decision=ItemDecision(kind="entry", direction="long", reason="entry_signal"),
        )


def test_a_no_op_is_emitted_and_traced_rather_than_dropped() -> None:
    view = _view(bars=(_bar("2024-01-01T00:00:00Z"),))
    intent = form_intent(
        identity=_identity(),
        view=view,
        snapshot=_snapshot(),
        decision=idle_decision(_identity(), view),
    )
    assert intent.kind == "no_op"
    assert intent.reason == NO_SIGNAL_AT_TICK
    assert intent.desired_size == _ZERO
    assert not intent.is_actionable
    # A non-actionable intent claims no price authority for a size it did not compute.
    assert intent.effective_price is None


def test_an_item_with_no_bar_at_this_tick_still_appears_with_its_own_reason() -> None:
    """ADR §5: the tick is not a decision for this item, but its open position is still
    part of E(t) — a missing view would hide that. The two silences get two tokens."""
    view = _view(bars=(), last_closed=_bar("2024-01-01T00:00:00Z", "99"), last_closed_t_ms=1)
    intent = form_intent(
        identity=_identity(),
        view=view,
        snapshot=_snapshot(),
        decision=idle_decision(_identity(), view),
    )
    assert (intent.kind, intent.reason) == ("no_op", NO_BAR_AT_TICK)
    assert intent.price_authority == "stale_last_close"
    assert intent.reference_price == Decimal("99")


def test_a_non_executing_kind_is_blocked_with_the_honest_v1_reason() -> None:
    """Trading Signal / Trade Log are pinned and participate, but the V1 bar-replay engine
    runs no standalone simulation for them (``ItemRun.output is None``). They must never
    receive a fabricated entry — a phantom contribution is exactly what Future Dev
    capability may not produce. Whether they may hold a sleeve at all is OD-6, open."""
    for kind in ("trading_signal", "trade_log"):
        identity = _identity("item_a", kind=kind)
        view = _view(bars=(_bar("2024-01-01T00:00:00Z"),))
        intent = form_intent(
            identity=identity,
            view=view,
            snapshot=_snapshot(),
            decision=idle_decision(identity, view),
        )
        assert not identity.executes
        assert (intent.kind, intent.reason) == ("blocked", ITEM_KIND_DOES_NOT_EXECUTE)
        assert intent.desired_size == _ZERO


def test_an_actionable_intent_at_a_barless_tick_fails_closed() -> None:
    with pytest.raises(NoDecisionAtTickError):
        form_intent(
            identity=_identity(),
            view=_view(bars=()),
            snapshot=_snapshot(),
            decision=ItemDecision(kind="entry", direction="long", reason="entry_signal"),
            sizing=_entry_sizing(_config()),
        )


def test_an_entry_without_sizing_inputs_fails_closed_instead_of_sizing_zero() -> None:
    """A fabricated 0 would read as "the strategy wanted nothing" — a different, and
    false, statement from "the size could not be computed"."""
    with pytest.raises(MissingSizingInputsError):
        form_intent(
            identity=_identity(),
            view=_view(bars=(_bar("2024-01-01T00:00:00Z"),)),
            snapshot=_snapshot(),
            decision=ItemDecision(kind="entry", direction="long", reason="entry_signal"),
        )
    with pytest.raises(MissingSizingInputsError):
        form_intent(
            identity=_identity(),
            view=_view(bars=(_bar("2024-01-01T00:00:00Z"),)),
            snapshot=_snapshot(),
            decision=ItemDecision(kind="scale_in", direction="long", reason="scale_layer_added"),
            sizing=_entry_sizing(_config()),
        )


# --------------------------------------------------------------------- provenance


def test_an_intent_names_the_exact_pinned_revision_it_speaks_for() -> None:
    """Historical traceability (doc 13 §11.1): the revision comes from the pinned identity
    and is echoed into the dependencies, so a stored intent is readable without joining
    today's live registry."""
    identity = _identity("item_b", pin_ordinal=2)
    intent = form_intent(
        identity=identity,
        view=_view("item_b", pin_ordinal=2, bars=(_bar("2024-01-01T00:00:00Z"),)),
        snapshot=_snapshot(sleeves={"item_b": "1000"}),
        decision=ItemDecision(kind="no_op", reason=NO_SIGNAL_AT_TICK),
    )
    assert intent.identity is identity
    assert intent.item_id == "item_b"
    assert intent.dependencies["root_id"] == "root_item_b"
    assert intent.dependencies["selected_revision_id"] == "rev_item_b"
    assert intent.dependencies["item_kind"] == "strategy"
    assert intent.contract_version == INTENT_CONTRACT_VERSION


def test_an_intents_dependencies_pin_the_valuation_it_rests_on() -> None:
    snap = _snapshot(sleeves={"item_a": "3600"}, deployed={"item_a": "600"})
    intent = form_intent(
        identity=_identity(),
        view=_view(bars=(_bar("2024-01-01T00:00:00Z"),)),
        snapshot=snap,
        decision=ItemDecision(kind="entry", direction="long", reason="entry_signal"),
        sizing=_entry_sizing(_config()),
    )
    assert intent.dependencies["snapshot_identity"] == snap.identity
    assert intent.dependencies["snapshot_t_ms"] == snap.t_ms
    assert intent.dependencies["reserve_nominal"] == snap.reserve_nominal
    assert intent.dependencies["sleeve_capacity"] == Decimal("3600")
    assert intent.dependencies["remaining_sleeve_capacity"] == Decimal("3000")
    # The base the pre-cap chain ran against is recorded, never assumed (SIZING_BASE_DIVERGENCE).
    assert intent.dependencies["sizing_base_source"] == "portfolio_equity"
    assert intent.dependencies["sizing_base"] == Decimal("10000")


def test_diagnostics_measure_staleness_without_applying_a_threshold() -> None:
    """OD-2 is open: the layer reports the facts a mark policy would need and bounds
    nothing. A duplicate instant inside one item is surfaced, not collapsed."""
    t = 1_700_000_000_000
    fresh = _view(bars=(_bar("2024-01-01T00:00:00Z"), _bar("2024-01-01T00:00:00Z", "101")))
    stale = _view(
        bars=(), last_closed=_bar("2023-12-31T00:00:00Z"), last_closed_t_ms=t - 86_400_000
    )
    snap = _snapshot()
    fresh_intent = form_intent(
        identity=_identity(),
        view=fresh,
        snapshot=snap,
        decision=ItemDecision(kind="no_op", reason=NO_SIGNAL_AT_TICK),
    )
    stale_intent = form_intent(
        identity=_identity(),
        view=stale,
        snapshot=snap,
        decision=ItemDecision(kind="no_op", reason=NO_BAR_AT_TICK),
    )
    assert fresh_intent.diagnostics["staleness_ms"] == 0
    assert fresh_intent.diagnostics["duplicate_instant"] is True
    assert fresh_intent.diagnostics["bars_at_tick"] == 2
    assert stale_intent.diagnostics["staleness_ms"] == 86_400_000
    assert stale_intent.diagnostics["is_decision"] is False
    # The last of two bars at one instant wins, matching the engine's forward replay.
    assert fresh_intent.reference_price == Decimal("101")


def test_price_authority_distinguishes_a_fresh_close_from_a_carried_one() -> None:
    snap = _snapshot()
    fresh = form_intent(
        identity=_identity(),
        view=_view(bars=(_bar("2024-01-01T00:00:00Z"),)),
        snapshot=snap,
        decision=ItemDecision(kind="no_op", reason=NO_SIGNAL_AT_TICK),
    )
    carried = form_intent(
        identity=_identity(),
        view=_view(bars=(), last_closed=_bar("2023-12-31T00:00:00Z"), last_closed_t_ms=1),
        snapshot=snap,
        decision=ItemDecision(kind="no_op", reason=NO_BAR_AT_TICK),
    )
    unseen = form_intent(
        identity=_identity(),
        view=_view(bars=()),
        snapshot=snap,
        decision=ItemDecision(kind="no_op", reason=NO_BAR_AT_TICK),
    )
    assert fresh.price_authority == "fresh_bar_close"
    assert carried.price_authority == "stale_last_close"
    assert unseen.price_authority == "unavailable"
    assert unseen.reference_price is None


# ------------------------------------------------------------- purity & determinism


def test_forming_an_intent_twice_yields_an_equal_value() -> None:
    """ADR §6 rule 3, idempotence."""
    args = {
        "identity": _identity(),
        "view": _view(bars=(_bar("2024-01-01T00:00:00Z"),)),
        "snapshot": _snapshot(),
        "decision": ItemDecision(kind="entry", direction="long", reason="entry_signal"),
        "sizing": _entry_sizing(_config()),
    }
    assert form_intent(**args) == form_intent(**args)


def test_forming_an_intent_mutates_neither_the_view_nor_the_snapshot() -> None:
    """ADR §6 rule 1: pure — no ledger write, no I/O, no mutation of item state. There is
    no fill and no ledger in this layer to move, and the two inputs come back untouched."""
    view = _view(bars=(_bar("2024-01-01T00:00:00Z"),))
    snap = _snapshot(sleeves={"item_a": "3600"}, deployed={"item_a": "600"})
    # Captured by VALUE, not by reference: holding the objects themselves would compare
    # each to itself afterwards and pass whatever form_intent had done to them.
    before = (
        astuple(view),
        snap.equity,
        snap.allocatable,
        snap.unallocated,
        dict(snap.sleeve_capacity),
        dict(snap.deployed_notional),
        snap.identity,
    )
    form_intent(
        identity=_identity(),
        view=view,
        snapshot=snap,
        decision=ItemDecision(kind="entry", direction="long", reason="entry_signal"),
        sizing=_entry_sizing(_config()),
    )
    assert (
        astuple(view),
        snap.equity,
        snap.allocatable,
        snap.unallocated,
        dict(snap.sleeve_capacity),
        dict(snap.deployed_notional),
        snap.identity,
    ) == before


def test_evidence_handed_in_cannot_be_edited_through_the_intent() -> None:
    evidence = {"rule": "required_indicator_blocks_only", "blocks": ["blk_1"]}
    intent = form_intent(
        identity=_identity(),
        view=_view(bars=(_bar("2024-01-01T00:00:00Z"),)),
        snapshot=_snapshot(),
        decision=ItemDecision(kind="no_op", reason=NO_SIGNAL_AT_TICK, evidence=evidence),
    )
    evidence["rule"] = "tampered"
    assert intent.evidence["rule"] == "required_indicator_blocks_only"
    with pytest.raises(TypeError):
        intent.evidence["rule"] = "tampered"  # type: ignore[index]


def test_item_order_follows_the_pinned_axis_not_the_decision_mapping_order() -> None:
    """ADR §4.4 / doc 13 §13: the outcome must not depend on DOM row order, browser timing
    or request arrival order — and equally not on the order a DB query returned the work
    in. The order is a property of the pinned manifest, read off the clock's own views."""
    ids = ("item_a", "item_b", "item_c")
    streams = [
        ItemBarStream(item_id=item, pin_ordinal=ordinal, batches=iter([[_raw_row(item)]]))
        for ordinal, item in enumerate(ids)
    ]
    tick = next(iter_ticks(streams))
    snap = _snapshot(t_ms=tick.t_ms, sleeves={"item_a": "1", "item_b": "2", "item_c": "3"})
    identities = {item: _identity(item, pin_ordinal=ordinal) for ordinal, item in enumerate(ids)}
    forward = form_intents(tick, snap, identities, {})
    shuffled = form_intents(
        tick,
        snap,
        {k: identities[k] for k in reversed(ids)},
        {
            item: (ItemDecision(kind="no_op", reason=NO_SIGNAL_AT_TICK), None)
            for item in reversed(ids)
        },
    )
    assert tuple(i.item_id for i in forward) == ids
    assert tuple(i.item_id for i in shuffled) == ids
    assert snapshot_identities(forward) == snapshot_identities(shuffled) == {snap.identity}


def _raw_row(item: str) -> dict[str, Any]:
    return {"timestamp": "2024-01-01T00:00:00Z", "open": "1", "high": "1", "low": "1", "close": "1"}


def test_an_item_with_no_supplied_decision_is_traced_not_skipped() -> None:
    """ "The caller forgot this item" and "this item chose nothing" are both visible, and
    neither collapses into a missing row (ADR §6 rule 5)."""
    streams = [
        ItemBarStream(item_id="item_a", pin_ordinal=0, batches=iter([[_raw_row("item_a")]])),
        ItemBarStream(item_id="item_b", pin_ordinal=1, batches=iter([[_raw_row("item_b")]])),
    ]
    tick = next(iter_ticks(streams))
    snap = _snapshot(t_ms=tick.t_ms, sleeves={"item_a": "1", "item_b": "1"})
    intents = form_intents(
        tick,
        snap,
        {
            "item_a": _identity("item_a", pin_ordinal=0),
            "item_b": _identity("item_b", pin_ordinal=1),
        },
        {},
    )
    assert len(intents) == len(tick.views) == 2
    assert {i.reason for i in intents} == {NO_SIGNAL_AT_TICK}


def test_an_unidentified_item_on_the_axis_fails_closed() -> None:
    streams = [ItemBarStream(item_id="item_a", pin_ordinal=0, batches=iter([[_raw_row("item_a")]]))]
    tick = next(iter_ticks(streams))
    with pytest.raises(UnknownItemError):
        form_intents(tick, _snapshot(t_ms=tick.t_ms), {}, {})


def test_many_items_form_exactly_one_intent_each_at_every_tick() -> None:
    """Performance sanity, not a benchmark: the per-tick cost stays linear in item count
    and the one-intent-per-view invariant holds at scale. The wall-clock bound is a smoke
    guard against an accidental quadratic, deliberately generous for a shared CI box."""
    item_count, tick_count = 120, 25
    rows = [
        {
            "timestamp": f"2024-01-01T00:{minute:02d}:00Z",
            "open": "1",
            "high": "1",
            "low": "1",
            "close": "1",
        }
        for minute in range(tick_count)
    ]
    ids = tuple(f"item_{n:03d}" for n in range(item_count))
    streams = [
        ItemBarStream(item_id=item, pin_ordinal=ordinal, batches=iter([list(rows)]))
        for ordinal, item in enumerate(ids)
    ]
    identities = {item: _identity(item, pin_ordinal=ordinal) for ordinal, item in enumerate(ids)}
    sleeves = dict.fromkeys(ids, "10")
    started = time.monotonic()
    total = 0
    for tick in iter_ticks(streams):
        snap = _snapshot(t_ms=tick.t_ms, sleeves=sleeves)
        intents = form_intents(tick, snap, identities, {})
        assert len(intents) == item_count
        assert snapshot_identities(intents) == {snap.identity}
        total += len(intents)
    assert total == item_count * tick_count
    assert time.monotonic() - started < 20.0


# --------------------------------------------------------------- single-item oracle


def test_an_entry_intents_size_and_price_match_the_engines_own_fill() -> None:
    """The parity that matters: for the entry ``run_engine`` actually took on a real
    replay, the intent layer reproduces the engine's own filled size and fill price.

    It holds because the layer calls the SAME shipped functions the entry path calls
    (``costs._effective_fill`` then ``sizing._position_size``) rather than re-deriving
    them — so this asserts the wiring, and would fail the moment the layer grew arithmetic
    of its own. Run with allocation off and no partial fill, where the engine's
    ``planned_size`` reduces to the pre-cap chain this layer stops at."""
    for method in ("base_position_size", "risk_based_sizing"):
        config = _config(method=method, slippage="0.001")
        out = _run(config, _breakout_bars())
        fills = [e for e in out.signal_events if e.event_type == "entry_fill"]
        assert len(fills) == 1, method
        fill = fills[0]
        signal_bar = _normalize(_breakout_bars()[fill.detail["bar_seq"] - 1])
        assert signal_bar is not None

        intent = form_intent(
            identity=_identity(),
            view=_view(bars=(signal_bar,)),
            snapshot=_snapshot(),
            decision=ItemDecision(kind="entry", direction="long", reason="entry_signal"),
            sizing=EntrySizing(
                # Built through the engine's OWN cost resolver, so the fixture cannot
                # quietly disagree with it about what "0.001 percentage slippage" means.
                config=config,
                fill_costs=FillCosts(*_cost_params(config)),
                base=Decimal("10000.00"),
                base_source="portfolio_equity",
            ),
        )
        assert str(intent.effective_price) == fill.detail["fill_price"], method
        assert str(intent.desired_size) == fill.detail["size"], method


def test_the_intent_layer_leaves_the_sleeve_cap_to_a_later_phase() -> None:
    """``sizing.planned_size`` folds ``_cap_to_sleeve`` in; ADR §8.2 splits that into P6a
    (sizing, here) and P6b (sleeve cap, ADIM 19). A binding sleeve must therefore NOT
    shrink ``desired_size`` — it is published as a dependency for the cap layer instead."""
    config = _config()
    snap = _snapshot(sleeves={"item_a": "100"})  # 100 / 100 = 1 unit of headroom
    intent = form_intent(
        identity=_identity(),
        view=_view(bars=(_bar("2024-01-01T00:00:00Z", "100"),)),
        snapshot=snap,
        decision=ItemDecision(kind="entry", direction="long", reason="entry_signal"),
        sizing=_entry_sizing(config),
    )
    capped_units = snap.remaining_sleeve_capacity("item_a") / intent.reference_price
    assert intent.desired_size == Decimal("50")
    assert intent.desired_size > capped_units
    assert intent.dependencies["remaining_sleeve_capacity"] == Decimal("100")


def test_the_intent_layer_invents_no_reason_vocabulary() -> None:
    """Every ``blocked`` reason an intent can carry is a token ``run_engine`` already
    writes into its decision trace. The layer adds exactly three tokens — the states that
    only exist once there IS a shared axis — and they are disjoint from the engine's."""
    # Read out of LIVE source rather than copied here, so this set cannot rot silently
    # into a stale claim about a vocabulary that has since moved.
    engine_tokens: set[str] = set()
    for func in (blocked_reason, resolve_scale_rejection):
        engine_tokens |= set(re.findall(r'return "([a-z_]+)"', inspect.getsource(func)))
    assert len(engine_tokens) >= 8, sorted(engine_tokens)
    assert {"sleeve_zero_capacity", "layer_size_not_positive"} <= engine_tokens

    assert {NO_BAR_AT_TICK, NO_SIGNAL_AT_TICK, ITEM_KIND_DOES_NOT_EXECUTE} == INTENT_LAYER_REASONS
    assert INTENT_LAYER_REASONS.isdisjoint(engine_tokens)


def test_every_engine_entry_decision_projects_to_exactly_one_intent() -> None:
    """No silent drop, measured against a real replay: every entry-class decision the
    engine traced (fired, filtered or blocked) becomes exactly one typed intent carrying
    the engine's own reason token."""
    out = _run(_config(), _breakout_bars())
    traced = [e for e in out.signal_events if e.event_type in {"entry_signal", "entry_blocked"}]
    traced += [e for e in out.filtered_events if e.event_type == "filtered_no_entry"]
    assert traced, "the fixture must produce at least one entry-class decision"

    snap = _snapshot()
    intents = []
    for event in traced:
        blocked = event.event_type != "entry_signal"
        intents.append(
            form_intent(
                identity=_identity(),
                view=_view(bars=(_bar("2024-01-01T00:00:00Z"),)),
                snapshot=snap,
                decision=ItemDecision(
                    kind="blocked" if blocked else "entry",
                    direction=event.direction,
                    reason=str(event.detail.get("reason", event.event_type)),
                    evidence=dict(event.detail),
                ),
                sizing=None if blocked else _entry_sizing(_config()),
            )
        )
    # The counts match trivially (one append per event); what the MODULE has to deliver is
    # that it accepts every one of them — no event rejected, silently rewritten, or
    # stripped of the engine's own reason and evidence on the way through.
    assert len(intents) == len(traced)
    assert [i.reason for i in intents] == [
        str(e.detail.get("reason", e.event_type)) for e in traced
    ]
    assert all(i.reason not in INTENT_LAYER_REASONS for i in intents)
    assert all(
        i.evidence["bar_seq"] == e.detail["bar_seq"] for i, e in zip(intents, traced, strict=True)
    )
    assert {i.kind for i in intents} <= ACTIONABLE_KINDS | {"blocked"}
    # An accepted entry is genuinely sized; a blocked one genuinely is not.
    for intent in intents:
        assert (intent.desired_size > _ZERO) is (intent.kind == "entry")


# ------------------------------------------------------------------------ containment


def test_the_intent_layer_is_reachable_only_through_the_phase_loop() -> None:
    """The rollback for this slice is "delete the module", exactly as for the ADIM 15
    clock — which is what keeps every shipped digest still. When the phase loop wires
    ``run_portfolio`` in, this test is the one that must be updated deliberately; it
    should never fail by accident.

    **Widened deliberately at `C3` (E4c), by ONE NAMED module.** ``domain/backtest/participant.py``
    is the engine-backed ``ItemParticipant`` adapter; it names the phase loop's own types in
    its signatures, so it cannot exist without appearing here. It sits OUTSIDE ``execution/``
    on purpose — inside, the containment gate's importer scan would have exempted it and the
    guard would have gone blind rather than satisfied. The widening is a named entry, never a
    wildcard, so a THIRD importer is still a red build. Signed 2026-08-18, Option A:
    ``docs/decisions/closure_participant_importer_allowlist_2026-08-18.md``.

    It has been updated deliberately twice, in the same shape the clock's own containment
    test was, and each entry is NAMED rather than the assertion being loosened to "some
    importers are fine": the ADIM 17 shared ledger (``execution/portfolio_ledger.py``)
    publishes a ``PortfolioSnapshot``, and the cross-item arbitration layer
    (``execution/arbitration.py``) reads the ``ItemIntent`` values it arbitrates. Both are
    themselves contained — their own test files assert nothing imports THEM — so the property
    this test defends is unchanged: no production path reaches the intent layer, and the
    rollback is still "delete the modules".

    Third deliberate update (ADIM 19): ``execution/provenance.py`` projects ``ItemIdentity``
    into the manifest's pinned item rows. Contained as well.

    **Fourth, and the one this test was written for: ADIM 18's ``portfolio_engine.py``.** It is
    a production entry point, not a contained sibling, so "nothing in production imports the
    intent layer" is retired here on purpose. What replaces it is the property that matters
    from here on — the intent layer is reached through the P3/P4 phases of ``run_portfolio``
    and nowhere else. The loop takes a P4 intent already FORMED by the item (an entry's size
    needs the item's own ``StrategyConfig``) and validates it; it imports this module for
    ``form_mandatory_intent`` and for the types it checks against.

    **Fifth deliberate update: ``execution/portfolio_projection.py``.** The Result projection
    READS a finished run's intents — they are its decision trace — so it needs the
    ``ItemIntent`` type and nothing else from here: it forms no intent, validates none, and
    never reaches the layer during a run. It is itself contained
    (``test_oracle_portfolio_containment_gate.py`` asserts nothing calls it), and it is the
    ONLY unified-clock module it imports at all: the three policy-version constants it might
    have published were dropped rather than widen three more of these lists for a field no
    consumer reads. So the property this test defends is unchanged."""
    src = Path(__file__).resolve().parents[2] / "src" / "entropia"
    importers = sorted(
        path.relative_to(src).as_posix()
        for path in src.rglob("*.py")
        if path.name != "intents.py" and _imports_intents(path.read_text(encoding="utf-8"))
    )
    assert importers == [
        "domain/backtest/execution/arbitration.py",
        "domain/backtest/execution/portfolio_ledger.py",
        "domain/backtest/execution/portfolio_projection.py",
        "domain/backtest/execution/provenance.py",
        "domain/backtest/participant.py",
        "domain/backtest/portfolio_engine.py",
    ]


def test_no_intent_field_ships_in_the_manifest_yet_and_the_engine_version_stands() -> None:
    """This slice changes no replay, so no ``execution_key`` namespace may shift. The
    manifest fields land with the ``ENGINE_VERSION`` bump, not before."""
    manifest_src = (
        Path(__file__).resolve().parents[2] / "src/entropia/domain/backtest/manifest.py"
    ).read_text(encoding="utf-8")
    # The literal moves only when something OUTSIDE the contained work bumps the version;
    # #550/#551/#552 (percent sizing, the zero-size guard, per-fill commission) did, and
    # the tripwire is unchanged by that: lifting containment still cannot happen without
    # editing this line.
    assert ENGINE_VERSION == "backtest-engine-v18-percent-sizing-per-fill-commission"
    for field_name in ("intent_contract_version", "arbitration_policy_version", "item-intent-v1"):
        assert field_name not in manifest_src


def _imports_intents(source: str) -> bool:
    """Every spelling that would actually import the module.

    Matching only the dotted path would miss ``from ... execution import intents`` and a
    relative ``from . import intents``, so the rollback guarantee would be pinned for one
    import style and quietly unpinned for two."""
    return (
        "execution.intents" in source
        or "execution import intents" in source
        or "from . import intents" in source
    )


def test_an_identity_paired_with_another_items_view_is_refused() -> None:
    """The intent is built half from the identity (provenance, snapshot lookup) and half
    from the view (price, instant, staleness). Letting the two disagree would attribute an
    intent to one item while sizing it off another's bar — cross-item contamination in
    exactly the place ADR §6 rule 2 forbids it, arriving through the front door."""
    snap = _snapshot(sleeves={"item_a": "3600", "item_b": "3600"})
    with pytest.raises(MismatchedItemViewError):
        form_intent(
            identity=_identity("item_a", pin_ordinal=0),
            view=_view("item_b", pin_ordinal=1, bars=(_bar("2024-01-01T00:00:00Z", "999"),)),
            snapshot=snap,
            decision=ItemDecision(kind="entry", direction="long", reason="entry_signal"),
            sizing=_entry_sizing(_config()),
        )
    with pytest.raises(MismatchedItemViewError):
        form_mandatory_intent(
            identity=_identity("item_a"),
            view=_view("item_b", bars=(_bar("2024-01-01T00:00:00Z"),)),
            decision=ItemDecision(kind="exit", direction="long", reason="stop_loss"),
            sizing=ClosingSize(units=Decimal("1")),
        )


def test_an_actionable_intent_without_a_usable_direction_is_refused() -> None:
    """``_effective_fill`` takes a boolean side, so an absent direction would be priced as
    a SELL: the adverse adjustment flips sign, the fill reads better than it is and the
    size computed from it comes out larger. That must not be silent."""
    for direction in (None, "flat", "LONG"):
        with pytest.raises(UndirectedIntentError):
            form_intent(
                identity=_identity(),
                view=_view(bars=(_bar("2024-01-01T00:00:00Z"),)),
                snapshot=_snapshot(),
                decision=ItemDecision(kind="entry", direction=direction, reason="entry_signal"),
                sizing=_entry_sizing(_config()),
            )
    # A short is a first-class direction, priced on the adverse side of its own trade.
    short = form_intent(
        identity=_identity(),
        view=_view(bars=(_bar("2024-01-01T00:00:00Z", "100"),)),
        snapshot=_snapshot(),
        decision=ItemDecision(kind="entry", direction="short", reason="entry_signal"),
        sizing=EntrySizing(
            config=_config(),
            fill_costs=FillCosts(
                half_spread=Decimal("1"), slippage=Decimal("0"), commission=Decimal("0")
            ),
            base=Decimal("10000"),
            base_source="portfolio_equity",
        ),
    )
    assert short.effective_price == Decimal("99.00")


def test_one_valuation_has_one_identity_whatever_the_decimal_spelling() -> None:
    """``Decimal("3600") == Decimal("3600.00")`` and the two arise from the same
    arithmetic (a quantized ledger read vs an unquantized share computation). A digest
    over their ``str`` forms would identify the FORMATTING, so the same valuation would
    fail its own "all items saw one snapshot" check across a serialization boundary."""
    plain = build_snapshot(
        t_ms=5,
        equity=Decimal("10000"),
        reserve_nominal=Decimal("1000"),
        sleeve_capacity={"a": Decimal("3600")},
        deployed_notional={"a": Decimal("0")},
    )
    quantized = build_snapshot(
        t_ms=5,
        equity=Decimal("10000.00"),
        reserve_nominal=Decimal("1000.000"),
        sleeve_capacity={"a": Decimal("3600.00")},
        deployed_notional={"a": Decimal("0.00")},
    )
    assert plain == quantized
    assert plain.identity == quantized.identity
    # Still discriminating: a genuinely different number is a different valuation.
    assert plain.identity != _snapshot(t_ms=5, equity="10000.01").identity


def test_a_snapshots_identity_is_computed_once_not_per_reader() -> None:
    """As a recomputing property this made a tick of n items cost n full re-hashes of all
    n items — quadratic in the item count, in the one loop this programme exists to make
    linear. It is a stored field now, so every reader gets the same object."""
    snap = _snapshot(sleeves={f"item_{n}": "10" for n in range(50)})
    assert snap.identity is snap.identity


def test_a_directly_constructed_snapshot_carries_the_same_guarantees() -> None:
    """The freezing, the derived ``item_ids`` and the identity live in ``__post_init__``,
    not in the factory, so a snapshot built by a future caller that bypasses
    ``build_snapshot`` cannot hand out mutable maps or an item set that disagrees with
    them."""
    direct = PortfolioSnapshot(
        t_ms=5,
        equity=Decimal("100"),
        reserve_nominal=Decimal("10"),
        allocatable=Decimal("90"),
        sleeve_capacity={"b": Decimal("1"), "a": Decimal("2")},
        deployed_notional={"b": _ZERO, "a": _ZERO},
        unallocated=Decimal("87"),
    )
    assert direct.item_ids == ("a", "b")
    assert direct.identity != ""
    with pytest.raises(TypeError):
        direct.sleeve_capacity["a"] = Decimal("9")  # type: ignore[index]
    with pytest.raises(UnknownItemError):
        PortfolioSnapshot(
            t_ms=5,
            equity=Decimal("100"),
            reserve_nominal=_ZERO,
            allocatable=Decimal("100"),
            sleeve_capacity={"a": Decimal("1")},
            deployed_notional={},
            unallocated=Decimal("99"),
        )


def test_a_decision_for_an_item_off_the_axis_is_refused_not_discarded() -> None:
    """The symmetric half of "nothing is silently dropped": a view with no identity already
    raised, but a decision with no view used to vanish — a real decision, discarded."""
    streams = [ItemBarStream(item_id="item_a", pin_ordinal=0, batches=iter([[_raw_row("item_a")]]))]
    tick = next(iter_ticks(streams))
    with pytest.raises(UnknownItemError):
        form_intents(
            tick,
            _snapshot(t_ms=tick.t_ms),
            {"item_a": _identity("item_a")},
            {"item_ghost": (ItemDecision(kind="no_op", reason=NO_SIGNAL_AT_TICK), None)},
        )


def test_an_over_allocated_snapshot_reports_a_negative_unallocated_pool() -> None:
    """``A(t)`` is floored at zero per ADR §7; ``U(t)`` is not. Sleeves summing past
    ``A(t)`` means the plan over-allocated — a state ``validate_allocation`` refuses
    upstream — and reporting it negative is the point: clamping would hide the violation
    behind a healthy-looking zero."""
    snap = _snapshot(equity="2000", reserve="1000", sleeves={"a": "900", "b": "900"})
    assert snap.allocatable == Decimal("1000")
    assert snap.unallocated == Decimal("-800")
