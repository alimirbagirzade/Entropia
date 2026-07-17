"""F-07e — Restrictions/Filters + conflict/position handling engine tests (Master Ref §12/§13).

The bar-replay engine never evaluated ``restrictions_filters`` and only executed
``exit_on_opposite_signal`` + ``stop_exit_conflict`` out of ``conflict_position_handling`` —
a saved filter set / stacking / hedge policy was silently ignored. These tests pin the new
behaviour. Restrictions: the modelled filters (date-blackout windows, max daily loss,
consecutive losses — block-entries action) veto a wanted entry at DECISION time with a
``filtered_no_entry`` trace event (``reason="restriction_blocked"``), combined by the §12.1
rule (any = OR, all = AND); volatility/spread/volume/correlation filters, another action and
a malformed config FAIL CLOSED (Ready Check blocker + an inert engine run). Conflicts: a NEW
aggregated signal EDGE while a position is open resolves per policy — same direction stacks
(fold-in add) / replaces / delegates to scaling / is ignored; an opposite signal with
exit-on-opposite OFF closes (``close_existing``) or is ignored; a true hedge (``allow_hedge``
with exit-on-opposite off) FAILS CLOSED. Each filter/policy has a positive (allowed/passes)
and a negative (blocked) case (spec F-07 acceptance).
"""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from typing import Any

from entropia.domain.backtest.engine import (
    EngineOutput,
    conflict_handling_is_modelled,
    restrictions_are_modelled,
    run_engine,
)
from entropia.domain.backtest.indicators import IndicatorPlan, IndicatorSpec, SignalRule
from entropia.domain.strategy.config import StrategyConfig
from tests.unit.engine_signal_plan import sma_entry_plan

_ZERO_COST = {"slippage_mode": "percentage_slippage", "slippage_value": "0"}


def _filter(
    filter_type: str,
    config: dict[str, Any] | None = None,
    *,
    enabled: bool = True,
    filter_id: str = "flt_1",
) -> dict[str, Any]:
    return {
        "filter_type": filter_type,
        "enabled": enabled,
        "filter_id": filter_id,
        "config": config or {},
    }


def _blackout(*ranges: tuple[str, str], filter_id: str = "flt_black") -> dict[str, Any]:
    return _filter(
        "date_blackout_filter",
        {"date_ranges": [{"start": s, "end": e} for s, e in ranges]},
        filter_id=filter_id,
    )


def _config(
    *,
    restrictions: dict[str, Any] | None = None,
    conflict: dict[str, Any] | None = None,
    position_size_limits: dict[str, Any] | None = None,
) -> StrategyConfig:
    """A minimal VALID StrategyConfig; only the fields the engine reads matter.

    Zero costs so fills land exactly on the resolved price; no protection stop so the
    conflict/exit paths (not a stop) govern the position's life."""
    sizing: dict[str, Any] = {"method": "base_position_size", "base_position_size": "50"}
    if position_size_limits is not None:
        sizing["position_size_limits"] = position_size_limits
    return StrategyConfig.model_validate(
        {
            "strategy_root_id": "strat_root_1",
            "display_name": "Restrictions Fixture",
            "rationale_family_id": "rf_1",
            "data": {
                "instrument_id": "BTCUSDT",
                "market_dataset_root_id": "md_root_1",
                "market_dataset_revision_id": "md_rev_1",
                "market_dataset_content_hash": "mdhash_1",
                "backtest_range": {
                    "start": "2024-01-01T00:00:00Z",
                    "end": "2024-12-31T23:59:59Z",
                },
                "initial_capital": "10000.00",
                "execution": {
                    "entry_timing": "current_candle_close",
                    "exit_timing": "current_candle_close",
                },
                "order_config": {"type": "market_order"},
                "costs": dict(_ZERO_COST),
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
            "position_exit_logic": {},
            "protection_stop_logic": {},
            "position_sizing": sizing,
            "restrictions_filters": restrictions or {"rule": "any", "filters": []},
            "conflict_position_handling": conflict or {},
        }
    )


def _bar(ts: str, o: str, h: str, low: str, c: str) -> dict[str, Any]:
    return {"timestamp": ts, "open": o, "high": h, "low": low, "close": c, "volume": "10"}


def _flat(n: int) -> list[dict[str, Any]]:
    return [_bar(f"2024-01-{i + 1:02d}T00:00:00Z", "100", "100", "100", "100") for i in range(n)]


def _day_closes(closes: list[str]) -> list[dict[str, Any]]:
    """One flat bar per DAY (o=h=l=c) — the plan-mode scripts; no intrabar surprises."""
    return [_bar(f"2024-01-{i + 1:02d}T00:00:00Z", c, c, c, c) for i, c in enumerate(closes)]


def _hour_closes(closes: list[str], *, day: int = 1) -> list[dict[str, Any]]:
    """One flat bar per HOUR of 2024-01-<day> — same-UTC-day restriction scripts."""
    return [_bar(f"2024-01-{day:02d}T{i:02d}:00:00Z", c, c, c, c) for i, c in enumerate(closes)]


def _sma_plan(*, exit_on_opposite: bool = True) -> IndicatorPlan:
    """SMA(3) price-cross entry plan: cross up -> long, cross down -> short (held until
    the opposite cross), mirroring how the production query resolves a pinned MA block."""
    spec = IndicatorSpec(
        block_id="blk_1",
        canonical_key="ta.sma",
        length=3,
        direction="long_and_short",
        requirement="required",
        validity="until_opposite_signal",
    )
    return IndicatorPlan(
        entry_rule=SignalRule(rule="required_indicator_blocks_only"),
        entry_specs=(spec,),
        exit_on_opposite=exit_on_opposite,
    )


def _run(
    config: StrategyConfig,
    bars: list[dict[str, Any]],
    *,
    batch: int = 8,
    plan: IndicatorPlan | None = None,
) -> EngineOutput:
    """Replay ``bars`` under ``config``; ``plan`` defaults to the shared ``ta.sma`` cross plan.

    F-24: the engine's breakout proxy is unreachable in a real RUN (F-06 makes an unresolved
    plan a Ready Check blocker), so no fixture may depend on it — entries here come from a
    real MA cross. A test needing a specific plan passes its own.

    This module HOLDS the signal (``until_opposite_signal``) rather than treating it as a
    one-bar edge, because that is what the rule under test needs: a restriction VETOES an
    otherwise-valid signal, and once the restriction lifts the still-valid signal must be able
    to enter. Under a one-bar edge the signal would expire together with the veto, making
    "blocked inside the window, allowed after" untestable — the ban and the signal's own
    expiry would be indistinguishable."""

    def batched() -> Iterator[list[dict[str, Any]]]:
        for start in range(0, len(bars), batch):
            yield bars[start : start + batch]

    return run_engine(
        strategy_config=config,
        bar_batches=batched(),
        execution_key="exec_key_restrictions",
        indicator_plan=plan or sma_entry_plan(validity="until_opposite_signal"),
    )


def _events(out: EngineOutput, kind: str) -> list[dict[str, Any]]:
    return [e.detail for e in out.signal_events if e.event_type == kind]


def _filtered(out: EngineOutput, reason: str) -> list[dict[str, Any]]:
    return [d for d in _events(out, "filtered_no_entry") if d["reason"] == reason]


# Breakout-proxy shapes (restriction tests need no plan): 20 look-back bars @100, an
# upside breakout on day 21 (long @102); day 22 re-breaks the grown window (close 104).
_BREAKOUT = _bar("2024-01-21T00:00:00Z", "100", "103", "100", "102")
_REBREAK = _bar("2024-01-22T00:00:00Z", "103", "105", "103", "104")

# SMA(3) plan scripts: 3 warm-up closes @10, a step to 12 crosses UP (long), a drop to 8
# crosses DOWN (short signal), a step back to 12 crosses UP again (a NEW long edge).
_WARMUP = ["10", "10", "10"]


# --------------------------------------------------------------------------- #
# Predicates — shared source of truth (readiness + engine)                    #
# --------------------------------------------------------------------------- #


def test_restrictions_predicate_trivial_and_disabled_filters_are_modelled() -> None:
    # No filters / a disabled unsupported filter is not an active engine rule.
    assert restrictions_are_modelled(_config())
    assert restrictions_are_modelled(
        _config(
            restrictions={
                "rule": "any",
                "filters": [_filter("volatility_filter", enabled=False)],
            }
        )
    )


def test_restrictions_predicate_modelled_filters_with_canonical_config() -> None:
    assert restrictions_are_modelled(
        _config(
            restrictions={
                "rule": "all",
                "filters": [
                    _blackout(("2024-03-01", "2024-03-05")),
                    _filter("max_daily_loss_filter", {"limit_percent": "2"}, filter_id="flt_dl"),
                    _filter(
                        "consecutive_loss_filter",
                        {"max_losses": 3, "action": "block_entries"},
                        filter_id="flt_cl",
                    ),
                ],
            }
        )
    )


def test_restrictions_predicate_fails_closed_on_unmodelled_filter_types() -> None:
    for kind in ("volatility_filter", "spread_filter", "volume_filter", "correlation_filter"):
        cfg = _config(restrictions={"rule": "any", "filters": [_filter(kind)]})
        assert not restrictions_are_modelled(cfg), kind


def test_restrictions_predicate_fails_closed_on_malformed_config() -> None:
    # A blackout needs at least one valid start<=end date window; a loss limit must be a
    # finite positive percent; a streak limit must be an int >= 1; a non-block action
    # (reduce/close/disable/warn) is a different behaviour the engine cannot execute.
    assert not restrictions_are_modelled(
        _config(restrictions={"rule": "any", "filters": [_filter("date_blackout_filter")]})
    )
    assert not restrictions_are_modelled(
        _config(restrictions={"rule": "any", "filters": [_blackout(("2024-03-05", "2024-03-01"))]})
    )
    assert not restrictions_are_modelled(
        _config(
            restrictions={
                "rule": "any",
                "filters": [_filter("max_daily_loss_filter", {"limit_percent": "0"})],
            }
        )
    )
    assert not restrictions_are_modelled(
        _config(
            restrictions={
                "rule": "any",
                "filters": [_filter("consecutive_loss_filter", {"max_losses": 0})],
            }
        )
    )
    assert not restrictions_are_modelled(
        _config(
            restrictions={
                "rule": "any",
                "filters": [
                    _filter("max_daily_loss_filter", {"limit_percent": "2", "action": "warn"})
                ],
            }
        )
    )


def test_conflict_predicate_defaults_modelled_hedge_without_exit_not() -> None:
    # Defaults (exit_on_opposite=True) are modelled for EVERY hedge value — the opposite
    # signal closes the position before a hedge could arise. A true hedge (allow_hedge
    # with exit-on-opposite OFF) needs two concurrent opposite positions -> fail closed.
    assert conflict_handling_is_modelled(_config())
    assert conflict_handling_is_modelled(
        _config(
            conflict={
                "exit_on_opposite_signal": False,
                "opposite_direction_hedge": "close_existing",
            }
        )
    )
    assert conflict_handling_is_modelled(
        _config(conflict={"exit_on_opposite_signal": False, "opposite_direction_hedge": "ignore"})
    )
    assert not conflict_handling_is_modelled(
        _config(
            conflict={"exit_on_opposite_signal": False, "opposite_direction_hedge": "allow_hedge"}
        )
    )


# --------------------------------------------------------------------------- #
# Restrictions — date blackout windows (§12.3)                                #
# --------------------------------------------------------------------------- #


def test_date_blackout_blocks_entry_inside_window_and_allows_after() -> None:
    cfg = _config(
        restrictions={"rule": "any", "filters": [_blackout(("2024-01-21", "2024-01-21"))]}
    )
    out = _run(cfg, [*_flat(20), _BREAKOUT, _REBREAK])
    # Day 21's breakout is vetoed (traced, never silent); day 22 re-breaks and enters.
    blocked = _filtered(out, "restriction_blocked")
    assert len(blocked) == 1
    assert blocked[0]["active_filters"] == [
        {"filter_id": "flt_black", "filter_type": "date_blackout_filter"}
    ]
    assert blocked[0]["context"] == "flat_entry"
    assert len(out.trades) == 1
    assert out.trades[0].entry_time == "2024-01-22T00:00:00Z"
    assert out.diagnostics["entries_blocked_by_restriction"] == 1
    assert out.diagnostics["restrictions_modelled"] is True
    assert out.diagnostics["active_filter_types"] == ["date_blackout_filter"]


def test_date_blackout_outside_window_entry_proceeds() -> None:
    cfg = _config(
        restrictions={"rule": "any", "filters": [_blackout(("2024-06-01", "2024-06-30"))]}
    )
    out = _run(cfg, [*_flat(20), _BREAKOUT])
    assert len(out.trades) == 1
    assert out.trades[0].entry_time == "2024-01-21T00:00:00Z"
    assert not _filtered(out, "restriction_blocked")


def test_restriction_rule_any_blocks_rule_all_requires_every_filter() -> None:
    # Blackout active on the breakout day + a never-active streak filter: "any" (OR)
    # blocks; "all" (AND) needs BOTH active so the entry proceeds.
    filters = [
        _blackout(("2024-01-01", "2024-12-31")),
        _filter("consecutive_loss_filter", {"max_losses": 5}, filter_id="flt_cl"),
    ]
    blocked_out = _run(
        _config(restrictions={"rule": "any", "filters": filters}), [*_flat(20), _BREAKOUT]
    )
    assert not blocked_out.trades
    assert _filtered(blocked_out, "restriction_blocked")
    allowed_out = _run(
        _config(restrictions={"rule": "all", "filters": filters}), [*_flat(20), _BREAKOUT]
    )
    assert len(allowed_out.trades) == 1
    assert not _filtered(allowed_out, "restriction_blocked")


# --------------------------------------------------------------------------- #
# Restrictions — max daily loss / consecutive losses (§12.4)                  #
# --------------------------------------------------------------------------- #


def test_max_daily_loss_blocks_reentry_same_day_allows_next_day() -> None:
    # Hourly bars: a long @12 closed @8 on the opposite cross realizes -200 (2% of the
    # 10000 capital) -> the 1% daily-loss filter is active for the REST of that UTC day
    # (both the held-short attempt @8 and the re-cross long @12 are vetoed); the next
    # day's accumulator starts fresh and the still-held long signal enters.
    cfg = _config(
        restrictions={
            "rule": "any",
            "filters": [
                _filter("max_daily_loss_filter", {"limit_percent": "1"}, filter_id="flt_dl")
            ],
        }
    )
    bars = [
        *_hour_closes([*_WARMUP, "12", "8", "8", "12"]),
        _bar("2024-01-02T00:00:00Z", "12", "12", "12", "12"),
    ]
    out = _run(cfg, bars, plan=_sma_plan())
    blocked = _filtered(out, "restriction_blocked")
    assert blocked, "the same-day re-entry must be vetoed"
    assert all(
        b["active_filters"] == [{"filter_id": "flt_dl", "filter_type": "max_daily_loss_filter"}]
        for b in blocked
    )
    assert len(out.trades) == 2
    assert out.trades[0].pnl == Decimal("-200.00")
    assert out.trades[1].entry_time == "2024-01-02T00:00:00Z"  # fresh day -> allowed
    assert out.trades[1].exit_reason == "end_of_data"


def test_max_daily_loss_under_limit_never_blocks() -> None:
    # The same -200 loss with a 5% (=500) limit stays under the threshold: the re-cross
    # long @12 re-enters the SAME day (hour 5) and nothing is vetoed.
    cfg = _config(
        restrictions={
            "rule": "any",
            "filters": [_filter("max_daily_loss_filter", {"limit_percent": "5"})],
        }
    )
    out = _run(cfg, _hour_closes([*_WARMUP, "12", "8", "12"]), plan=_sma_plan())
    assert not _filtered(out, "restriction_blocked")
    assert len(out.trades) == 2
    assert out.trades[1].direction == "long"
    assert out.trades[1].entry_time == "2024-01-01T05:00:00Z"


def test_consecutive_losses_block_next_entry_at_streak() -> None:
    # Two losing long trades (12->8 twice) reach the max_losses=2 streak -> the third
    # long cross is vetoed; the run ends flat with exactly the two realized losses.
    cfg = _config(
        restrictions={
            "rule": "any",
            "filters": [_filter("consecutive_loss_filter", {"max_losses": 2}, filter_id="flt_cl")],
        }
    )
    out = _run(cfg, _day_closes([*_WARMUP, "12", "8", "12", "8", "12"]), plan=_sma_plan())
    blocked = _filtered(out, "restriction_blocked")
    assert len(blocked) == 1
    assert blocked[0]["active_filters"] == [
        {"filter_id": "flt_cl", "filter_type": "consecutive_loss_filter"}
    ]
    assert len(out.trades) == 2
    assert all(t.pnl < 0 for t in out.trades)


def test_consecutive_losses_under_streak_allows_entry() -> None:
    # The same two losses with max_losses=3 stay under the streak: the third long cross
    # enters and rides to end-of-data.
    cfg = _config(
        restrictions={
            "rule": "any",
            "filters": [_filter("consecutive_loss_filter", {"max_losses": 3})],
        }
    )
    out = _run(cfg, _day_closes([*_WARMUP, "12", "8", "12", "8", "12"]), plan=_sma_plan())
    assert not _filtered(out, "restriction_blocked")
    assert len(out.trades) == 3
    assert out.trades[2].exit_reason == "end_of_data"


def test_unmodelled_filter_fails_closed_in_engine() -> None:
    # A stale readiness state reaching the worker with a volatility filter opens NOTHING
    # (never a silently unfiltered run) and surfaces the divergence (L4).
    cfg = _config(restrictions={"rule": "any", "filters": [_filter("volatility_filter")]})
    out = _run(cfg, [*_flat(20), _BREAKOUT])
    assert not out.trades
    assert out.diagnostics["restrictions_modelled"] is False
    assert "restrictions_unsupported:volatility_filter" in out.diagnostics["warnings"]


# --------------------------------------------------------------------------- #
# Conflict — same-direction stacking (§13)                                    #
# --------------------------------------------------------------------------- #

# Opposite-signal survival (exit_on_opposite OFF) needs a modelled hedge policy; "ignore"
# keeps the position open so the NEXT long cross is a genuine same-direction EDGE.
_STACK_CONFLICT = {"exit_on_opposite_signal": False, "opposite_direction_hedge": "ignore"}
# long @12 (cross up), short signal @8 (ignored), NEW long edge @12 (stacks), close @13.
_STACK_CLOSES = [*_WARMUP, "12", "8", "12", "13"]


def test_allow_stacking_folds_second_signal_into_position() -> None:
    cfg = _config(conflict={**_STACK_CONFLICT, "same_direction_stacking": "allow_stacking"})
    out = _run(cfg, _day_closes(_STACK_CLOSES), plan=_sma_plan(exit_on_opposite=False))
    added = _events(out, "stack_entry_added")
    assert len(added) == 1
    assert Decimal(added[0]["stack_size"]) == 50
    assert Decimal(added[0]["new_size"]) == 100
    assert Decimal(added[0]["entry_basis"]) == 12
    # The doubled position rides 12 -> 13: +100 (a single 50-size ride would book +50).
    assert len(out.trades) == 1
    assert out.trades[0].pnl == Decimal("100.00")
    assert out.diagnostics["stack_entries_added"] == 1
    assert out.diagnostics["same_direction_stacking"] == "allow_stacking"


def test_stacking_ignore_suppresses_second_signal_with_trace() -> None:
    cfg = _config(conflict={**_STACK_CONFLICT, "same_direction_stacking": "ignore"})
    out = _run(cfg, _day_closes(_STACK_CLOSES), plan=_sma_plan(exit_on_opposite=False))
    assert len(_filtered(out, "stacking_ignored")) == 1
    assert not _events(out, "stack_entry_added")
    assert len(out.trades) == 1
    assert out.trades[0].pnl == Decimal("50.00")  # the position never grew


def test_stacking_scale_existing_delegates_to_the_ladder() -> None:
    # No scaling subtree is enabled -> the repeated signal is a traced no-op (§13
    # "only if scaling allows"); position growth stays the ladder's job.
    cfg = _config(conflict={**_STACK_CONFLICT, "same_direction_stacking": "scale_existing"})
    out = _run(cfg, _day_closes(_STACK_CLOSES), plan=_sma_plan(exit_on_opposite=False))
    scale_only = _filtered(out, "stacking_scale_only")
    assert len(scale_only) == 1
    assert scale_only[0]["scaling_enabled"] is False
    assert len(out.trades) == 1
    assert out.trades[0].pnl == Decimal("50.00")


def test_replace_existing_closes_and_reopens_on_second_signal() -> None:
    cfg = _config(conflict={**_STACK_CONFLICT, "same_direction_stacking": "replace_existing"})
    out = _run(cfg, _day_closes(_STACK_CLOSES), plan=_sma_plan(exit_on_opposite=False))
    assert len(out.trades) == 2
    assert out.trades[0].exit_reason == "replaced_by_signal"
    assert out.trades[0].pnl == Decimal("0.00")  # entered @12, replaced @12
    assert out.trades[1].exit_reason == "end_of_data"
    assert out.trades[1].pnl == Decimal("50.00")  # the fresh 50-size rides 12 -> 13
    assert out.diagnostics["positions_replaced"] == 1
    assert len(_events(out, "entry_fill")) == 2


def test_stack_rejected_by_position_size_limit_never_trimmed() -> None:
    # 50 + 50 breaches the 60 cap -> the stack candidate is REJECTED with a ledger
    # reason (never auto-trimmed); the position rides at its original size.
    cfg = _config(
        conflict={**_STACK_CONFLICT, "same_direction_stacking": "allow_stacking"},
        position_size_limits={"max_position_size": "60"},
    )
    out = _run(cfg, _day_closes(_STACK_CLOSES), plan=_sma_plan(exit_on_opposite=False))
    rejected = _events(out, "stack_entry_rejected")
    assert len(rejected) == 1
    assert rejected[0]["reason"] == "position_size_limit"
    assert rejected[0]["cap"] == "60"
    assert not _events(out, "stack_entry_added")
    assert out.trades[0].pnl == Decimal("50.00")
    assert out.diagnostics["stack_entries_rejected"] == 1


def test_restriction_gate_also_vets_a_stack_entry() -> None:
    # §12.1 "block entry" is entry-scoped: the stack day (2024-01-06) sits in a blackout
    # window -> the same-direction edge is vetoed with the conflict_entry context.
    cfg = _config(
        restrictions={"rule": "any", "filters": [_blackout(("2024-01-06", "2024-01-06"))]},
        conflict={**_STACK_CONFLICT, "same_direction_stacking": "allow_stacking"},
    )
    out = _run(cfg, _day_closes(_STACK_CLOSES), plan=_sma_plan(exit_on_opposite=False))
    blocked = _filtered(out, "restriction_blocked")
    assert len(blocked) == 1
    assert blocked[0]["context"] == "conflict_entry"
    assert not _events(out, "stack_entry_added")
    assert len(out.trades) == 1
    assert out.trades[0].pnl == Decimal("50.00")


# --------------------------------------------------------------------------- #
# Conflict — opposite direction (§13)                                         #
# --------------------------------------------------------------------------- #


def test_exit_on_opposite_default_closes_position_before_any_hedge_question() -> None:
    # The V18 default path is untouched: the opposite cross closes as an exit signal;
    # no conflict-policy event fires.
    out = _run(_config(), _day_closes([*_WARMUP, "12", "8"]), plan=_sma_plan())
    assert len(out.trades) == 1
    assert out.trades[0].exit_reason == "exit_signal"
    assert out.diagnostics["opposite_signal_closes"] == 0
    assert out.diagnostics["conflict_signals_ignored"] == 0


def test_close_existing_closes_on_opposite_signal_when_exit_on_opposite_off() -> None:
    cfg = _config(
        conflict={"exit_on_opposite_signal": False, "opposite_direction_hedge": "close_existing"}
    )
    out = _run(
        cfg, _day_closes([*_WARMUP, "12", "8", "12", "13"]), plan=_sma_plan(exit_on_opposite=False)
    )
    # The opposite cross closes @8 with its OWN reason; the next long cross re-enters
    # flat and rides to end-of-data.
    assert len(out.trades) == 2
    assert out.trades[0].exit_reason == "opposite_signal"
    assert out.trades[0].pnl == Decimal("-200.00")
    assert out.trades[1].exit_reason == "end_of_data"
    assert out.diagnostics["opposite_signal_closes"] == 1


def test_hedge_ignore_keeps_position_open_with_trace() -> None:
    cfg = _config(conflict={"exit_on_opposite_signal": False, "opposite_direction_hedge": "ignore"})
    out = _run(cfg, _day_closes([*_WARMUP, "12", "8", "8"]), plan=_sma_plan(exit_on_opposite=False))
    ignored = _filtered(out, "hedge_ignored")
    assert len(ignored) == 1  # the EDGE traces once; the held short never re-fires
    assert len(out.trades) == 1
    assert out.trades[0].exit_reason == "end_of_data"  # the long survived the short signal
    assert out.diagnostics["conflict_signals_ignored"] == 1


def test_allow_hedge_without_exit_on_opposite_fails_closed_in_engine() -> None:
    cfg = _config(
        conflict={"exit_on_opposite_signal": False, "opposite_direction_hedge": "allow_hedge"}
    )
    out = _run(
        cfg, _day_closes([*_WARMUP, "12", "8", "12"]), plan=_sma_plan(exit_on_opposite=False)
    )
    assert not out.trades
    assert out.diagnostics["conflict_handling_modelled"] is False
    assert (
        "conflict_handling_unsupported:allow_hedge_without_exit_on_opposite"
        in out.diagnostics["warnings"]
    )


def test_conflict_paths_stay_inert_in_proxy_mode() -> None:
    # The breakout proxy computes no signals while a position is held -> no conflict
    # event can fire and the baseline stays byte-identical (documented boundary).
    cfg = _config(conflict={**_STACK_CONFLICT, "same_direction_stacking": "allow_stacking"})
    out = _run(cfg, [*_flat(20), _BREAKOUT, _REBREAK])
    assert not _events(out, "stack_entry_added")
    assert not _filtered(out, "hedge_ignored")
    assert out.diagnostics["stack_entries_added"] == 0
    assert len(out.trades) == 1
