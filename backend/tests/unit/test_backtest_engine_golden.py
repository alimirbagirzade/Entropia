"""Golden-output guard for the deterministic bar-replay engine.

The engine's reproducibility contract says a pinned strategy revision replayed over a
pinned market revision yields BYTE-IDENTICAL output (doc 15 §17). Every other engine
test asserts a specific behaviour; this one asserts that NOTHING changed at all.

It replays a scenario matrix built from the shipped engine test modules' own config and
bar builders — so it tracks real behaviour rather than a parallel fixture set — and
digests each run's FULL ``EngineOutput``: summary, trades, equity points, decision
events, diagnostics and position intervals. The digests live in
``engine_golden_digests.json`` next to this file.

Why the full output and not just the summary metrics: a refactor can leave every
headline metric intact while shifting a decision event's ordering, a diagnostic
counter or an exit reason — all of which are persisted into the immutable Result
artifact and read by users.

WHEN THIS TEST FAILS, it is doing its job. Two cases:

* You did NOT mean to change engine output. The diff names the scenarios that moved —
  that is a regression; fix the code, do not touch the JSON.
* You DID mean to change engine output (a real modelling fix or a new capability).
  Then the change shifts the reproducibility namespace: bump ``ENGINE_VERSION`` in
  ``domain/backtest/manifest.py`` in the SAME change, then regenerate the baseline with

      uv run --extra dev python -m tests.unit.test_backtest_engine_golden

  and commit the regenerated JSON alongside the code and the version bump. Regenerating
  without a version bump silently reuses an old ``execution_key`` namespace for output
  that no longer matches it, which is exactly what the contract forbids.

Introduced by K-09, the engine god-module split, where it proved five successive
refactors byte-identical — and caught one that was not (a dropped scaling-reference
capture that no behavioural test noticed).
"""

from __future__ import annotations

import hashlib
import json
import pathlib
from decimal import Decimal
from typing import Any

import tests.unit.test_backtest_engine as base
import tests.unit.test_backtest_engine_allocation as alloc
import tests.unit.test_backtest_funding as fund
import tests.unit.test_backtest_leverage_trailing as lev
import tests.unit.test_backtest_limit_orders as lim
import tests.unit.test_backtest_partial_close as part
import tests.unit.test_backtest_portfolio_rules as prules
import tests.unit.test_backtest_scaling as scal
import tests.unit.test_backtest_stop_orders as stops
from entropia.domain.backtest.engine import ItemRun
from entropia.domain.backtest.execution.portfolio import combine_item_runs
from entropia.domain.backtest.manifest import ENGINE_VERSION

GOLDEN_PATH = pathlib.Path(__file__).with_name("engine_golden_digests.json")


def _canon(value: Any) -> Any:
    """A stable, type-tagged projection: ``Decimal`` never collapses into a float, and
    dict ordering never leaks into the digest."""
    if isinstance(value, Decimal):
        return f"D:{value}"
    if isinstance(value, dict):
        return {str(k): _canon(v) for k, v in sorted(value.items(), key=lambda kv: str(kv[0]))}
    if isinstance(value, (list, tuple)):
        return [_canon(v) for v in value]
    if hasattr(value, "__dataclass_fields__"):
        return {n: _canon(getattr(value, n)) for n in sorted(value.__dataclass_fields__)}
    return value


def _digest(payload: Any) -> str:
    blob = json.dumps(_canon(payload), sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(blob.encode()).hexdigest()


def _scenarios() -> list[tuple[str, Any]]:
    """One entry per engine sub-system. Add to this list when a new one lands; never
    remove an entry to make a failure go away."""
    c: list[tuple[str, Any]] = []
    add = c.append

    # -- fills / order matching -----------------------------------------
    add(
        (
            "fills.baseline_stop_out",
            lambda: base._run(base._config(), base._long_breakout_then_stop()),
        )
    )
    add(
        (
            "fills.short",
            lambda: base._run(base._config(direction="short"), base._long_breakout_then_stop()),
        )
    )
    add(
        (
            "fills.no_stop",
            lambda: base._run(base._config(with_stop=False), base._long_breakout_then_stop()),
        )
    )
    add(
        (
            "fills.next_candle_open",
            lambda: base._run(
                base._config(entry_timing="next_candle_open", exit_timing="next_candle_open"),
                base._long_breakout_then_stop(),
            ),
        )
    )
    add(
        (
            "fills.next_candle_close",
            lambda: base._run(
                base._config(entry_timing="next_candle_close", exit_timing="next_candle_close"),
                base._long_breakout_then_stop(),
            ),
        )
    )
    add(
        (
            "fills.stop_exit_collision",
            lambda: base._run(
                base._config(stop_exit_conflict="exit_has_priority"),
                base._long_breakout_then_stop(),
            ),
        )
    )
    add(
        (
            "fills.limit_touch",
            lambda: lim._run(
                lim._config(order_config=lim._limit_order()),
                lim._long_breakout_then(
                    [
                        lim._fu(22, "102", "102", "98", "101"),
                        lim._fu(23, "101", "103", "100", "102"),
                    ]
                ),
            ),
        )
    )
    add(
        (
            "fills.limit_no_touch",
            lambda: lim._run(
                lim._config(order_config=lim._limit_order()),
                lim._long_breakout_then([lim._no_touch(22), lim._no_touch(23), lim._no_touch(24)]),
            ),
        )
    )
    add(
        (
            "fills.limit_offset_market_on_unfilled",
            lambda: lim._run(
                lim._config(
                    order_config=lim._limit_order(
                        offset="1", unfilled_policy="convert_to_market_order"
                    )
                ),
                lim._long_breakout_then([lim._no_touch(22), lim._no_touch(23), lim._no_touch(24)]),
            ),
        )
    )
    add(
        (
            "fills.limit_short",
            lambda: lim._run(
                lim._config(order_config=lim._limit_order()),
                lim._short_breakout_then([lim._fu(22, "98", "102", "98", "101")]),
            ),
        )
    )
    add(
        (
            "fills.stop_order",
            lambda: stops._run(
                stops._config(order_config=stops._stop_order()),
                stops._long_breakout_then(
                    [
                        stops._fu(22, "102", "106", "101", "105"),
                        stops._fu(23, "105", "105", "99", "100"),
                    ]
                ),
            ),
        )
    )
    add(
        (
            "fills.stop_order_never_triggers",
            lambda: stops._run(
                stops._config(order_config=stops._stop_order()),
                stops._long_breakout_then(
                    [stops._no_touch(22), stops._no_touch(23), stops._no_touch(24)]
                ),
            ),
        )
    )
    add(
        (
            "fills.stop_limit_order",
            lambda: stops._run(
                stops._config(order_config=stops._stop_limit_order()),
                stops._long_breakout_then(
                    [
                        stops._fu(22, "102", "106", "101", "105"),
                        stops._fu(23, "105", "105", "99", "100"),
                    ]
                ),
            ),
        )
    )

    # -- partial close / scaling ----------------------------------------
    for am in ("move_stop_to_entry", "lock_in_profit", "trailing_stop", "close_all"):
        add(
            (
                f"scaling.partial_{am}",
                (
                    lambda a=am: part._run(
                        part._config(close_percentage="50", partial_aftermath=a, with_stop=True),
                        part._long_then(
                            [
                                part._fu(22, "102", "112", "102", "111"),
                                part._fu(23, "111", "111", "95", "96"),
                            ]
                        ),
                    )
                ),
            )
        )
    add(
        (
            "scaling.price_ladder",
            lambda: scal._run(
                scal._config(scaling=scal._price_scaling()),
                scal._long_then(
                    [
                        scal._fu(22, "102", "108", "102", "107"),
                        scal._fu(23, "107", "115", "106", "114"),
                    ]
                ),
            ),
        )
    )
    add(
        (
            "scaling.price_ladder_capped",
            lambda: scal._run(
                scal._config(
                    scaling=scal._price_scaling(layers=1),
                    position_size_limits={"max_position_size": "60"},
                ),
                scal._long_then(
                    [
                        scal._fu(22, "102", "108", "102", "107"),
                        scal._fu(23, "107", "115", "106", "114"),
                    ]
                ),
            ),
        )
    )
    add(
        (
            "scaling.logic_unsupported",
            lambda: scal._run(
                scal._config(scaling=scal._logic_scaling()),
                scal._long_then([scal._fu(22, "102", "108", "102", "107")]),
            ),
        )
    )
    add(
        (
            "scaling.short_ladder",
            lambda: scal._run(
                scal._config(scaling=scal._price_scaling()),
                scal._short_then(
                    [scal._fu(22, "98", "98", "92", "93"), scal._fu(23, "93", "93", "85", "86")]
                ),
            ),
        )
    )

    # -- costs ----------------------------------------------------------
    # Added at #552. Until then the matrix configured NO commission anywhere — 46 scenarios
    # and not one of them priced a fee — so the per-FILL fix moved 0 of 46 digests and this
    # guard was structurally blind to the axis. A ratchet that cannot see a change cannot
    # ratchet it. Two scenarios, because the defect was not in the fee itself but in what it
    # scaled with: a two-fill round trip, and a ladder whose fills outnumber its closes.
    add(
        (
            "costs.commission_round_trip",
            lambda: scal._run(
                scal._config(commission="7"),
                scal._long_then(
                    [
                        scal._fu(22, "102", "108", "102", "107"),
                        scal._fu(23, "107", "115", "106", "114"),
                    ]
                ),
            ),
        )
    )
    add(
        (
            "costs.commission_scale_ladder",
            lambda: scal._run(
                scal._config(scaling=scal._price_scaling(), commission="7"),
                scal._long_then(
                    [
                        scal._fu(22, "102", "108", "102", "107"),
                        scal._fu(23, "107", "115", "106", "114"),
                    ]
                ),
            ),
        )
    )

    # -- sizing / leverage / allocation ---------------------------------
    # Added at #550/#551: the base (percent-of-capital) sizing path and the fail-closed
    # zero-size path. The matrix reached neither — its builders' DEFAULT sizing is
    # risk-based, so nothing here exercised the field #550 re-read, and no scenario asked
    # for a size that resolves to nothing.
    add(
        (
            "sizing.base_percent_of_capital",
            lambda: base._run(base._config(base_size="10"), base._long_breakout_then_stop()),
        )
    )
    add(
        (
            "sizing.impossible_window_opens_nothing",
            lambda: base._run(
                base._config(base_size="50", min_size="80", max_size="20"),
                base._long_breakout_then_stop(),
            ),
        )
    )
    add(
        (
            "sizing.risk_based",
            lambda: base._run(
                base._config(method="risk_based_sizing", risk_pct="2", stop_point="5"),
                base._long_breakout_then_stop(),
            ),
        )
    )
    add(
        (
            "sizing.kelly",
            lambda: base._run(
                base._config(
                    method="formula_based_sizing",
                    formula_type="kelly_criterion",
                    win_prob="0.6",
                    payoff="2",
                ),
                base._long_breakout_then_stop(),
            ),
        )
    )
    add(
        (
            "sizing.kelly_fractional",
            lambda: base._run(
                base._config(
                    method="formula_based_sizing",
                    formula_type="kelly_criterion",
                    win_prob="0.6",
                    payoff="2",
                    kelly_fraction="0.5",
                ),
                base._long_breakout_then_stop(),
            ),
        )
    )
    add(
        (
            "sizing.unsupported_method",
            lambda: base._run(
                base._config(method="formula_based_sizing", formula_type="custom_formula"),
                base._long_breakout_then_stop(),
            ),
        )
    )
    add(
        (
            "sizing.limits_clamped",
            lambda: base._run(
                base._config(min_size="10", max_size="20"), base._long_breakout_then_stop()
            ),
        )
    )
    add(
        (
            "sizing.allocation_sleeve_compound",
            lambda: alloc._run(alloc._config(), alloc._two_trade_bars(), allocation=alloc._alloc()),
        )
    )
    add(
        (
            "sizing.allocation_sleeve_fixed",
            lambda: alloc._run(
                alloc._config(),
                alloc._two_trade_bars(),
                allocation=alloc._alloc(mode="FIXED_INITIAL_PORTFOLIO_CAPITAL"),
            ),
        )
    )
    add(
        (
            "sizing.allocation_absent",
            lambda: alloc._run(alloc._config(), alloc._two_trade_bars(), allocation=None),
        )
    )
    add(
        (
            "sizing.leverage_trailing",
            lambda: lev._run(
                lev._config(leverage="3", trail_percentage="2", lock_in_percentage="1"),
                lev._long_then(
                    [
                        lev._fu(22, "102", "112", "102", "111"),
                        lev._fu(23, "111", "111", "100", "101"),
                    ]
                ),
            ),
        )
    )
    add(
        (
            "sizing.leverage_cross_unsupported",
            lambda: lev._run(
                lev._config(leverage_mode="cross", leverage="3"),
                lev._long_then([lev._fu(22, "102", "112", "102", "111")]),
            ),
        )
    )

    # -- funding / carry -------------------------------------------------
    add(
        (
            "costs.funding_long",
            lambda: fund._run(
                base._config(), fund._long_held(), fund._schedule((22, "0.001"), (23, "0.002"))
            ),
        )
    )
    add(
        (
            "costs.funding_short",
            lambda: fund._run(
                base._config(direction="short"),
                fund._short_held(),
                fund._schedule((22, "0.001"), (23, "0.002")),
            ),
        )
    )
    add(("costs.funding_off", lambda: fund._run(base._config(), fund._long_held(), None)))
    add(
        (
            "costs.funding_future_leak",
            lambda: fund._run(base._config(), fund._long_held(), fund._schedule((28, "0.5"))),
        )
    )
    add(
        (
            "costs.funding_batch_2",
            lambda: fund._run(
                base._config(), fund._long_held(), fund._schedule((22, "0.001")), batch=2
            ),
        )
    )

    # -- portfolio rules / compose ---------------------------------------
    add(
        (
            "portfolio.rules_block_opposite",
            lambda: prules._run(
                prules._config(),
                rules=prules._rules(policy="BLOCK_OPPOSITE", priors=(prules._iv(),)),
            ),
        )
    )
    add(
        (
            "portfolio.rules_net_downgrade",
            lambda: prules._run(
                prules._config(), rules=prules._rules(policy="NET", priors=(prules._iv(),))
            ),
        )
    )
    add(
        (
            "portfolio.rules_exposure_cap",
            lambda: prules._run(prules._config(), rules=prules._rules(pct="10")),
        )
    )
    add(
        (
            "portfolio.rules_exposure_invalid",
            lambda: prules._run(prules._config(), rules=prules._rules(invalid=True)),
        )
    )
    add(("portfolio.rules_none", lambda: prules._run(prules._config(), rules=None)))

    def _runs() -> list[ItemRun]:
        a = base._run(base._config(), base._long_breakout_then_stop())
        b = base._run(base._config(direction="short"), base._long_breakout_then_stop())
        return [
            ItemRun(
                item_id="mbi_1", item_kind="strategy", root_id="wo_a", revision_id="rev_a", output=a
            ),
            ItemRun(
                item_id="mbi_2", item_kind="strategy", root_id="wo_b", revision_id="rev_b", output=b
            ),
            ItemRun(
                item_id="mbi_3",
                item_kind="trading_signal",
                root_id="wo_c",
                revision_id="rev_c",
                output=None,
            ),
        ]

    add(
        (
            "portfolio.combine",
            lambda: combine_item_runs(
                _runs(),
                portfolio_initial_capital=Decimal("20000.00"),
                execution_key="exec_key_test",
                item_count=3,
            ),
        )
    )
    add(
        (
            "portfolio.combine_shared_pool",
            lambda: combine_item_runs(
                _runs(),
                portfolio_initial_capital=Decimal("20000.00"),
                execution_key="exec_key_test",
                item_count=3,
                shared_pool=True,
            ),
        )
    )
    add(
        (
            "portfolio.combine_reversed",
            lambda: combine_item_runs(
                list(reversed(_runs())),
                portfolio_initial_capital=Decimal("20000.00"),
                execution_key="exec_key_test",
                item_count=3,
            ),
        )
    )
    add(
        (
            "portfolio.combine_non_executing_only",
            lambda: combine_item_runs(
                [
                    ItemRun(
                        item_id="mbi_9",
                        item_kind="trade_log",
                        root_id="wo_z",
                        revision_id="rev_z",
                        output=None,
                    )
                ],
                portfolio_initial_capital=Decimal("10000.00"),
                execution_key="exec_key_test",
                item_count=1,
            ),
        )
    )

    # -- the reproducibility contract itself ------------------------------
    add(
        (
            "contract.execution_key",
            lambda: {
                "execution_key": base._manifest(
                    "run_1", "snap_1", "2024-01-01T00:00:00Z"
                ).execution_key,
                "engine_version": ENGINE_VERSION,
            },
        )
    )
    return c


def _current() -> dict[str, str]:
    return {name: _digest(fn()) for name, fn in _scenarios()}


def test_engine_output_matches_the_recorded_golden_digests() -> None:
    """Every scenario's FULL output digest must equal the recorded baseline.

    See the module docstring before changing the JSON: an intentional output change
    requires an ENGINE_VERSION bump in the same commit."""
    recorded: dict[str, str] = json.loads(GOLDEN_PATH.read_text())["digests"]
    current = _current()

    missing = sorted(set(recorded) - set(current))
    assert not missing, (
        f"scenarios disappeared from the matrix: {missing}. A scenario is never removed "
        "to silence a failure — restore it or justify the removal explicitly."
    )
    added = sorted(set(current) - set(recorded))
    assert not added, (
        f"new scenarios are not in the baseline yet: {added}. Regenerate the JSON "
        "(see the module docstring) in the same commit that adds them."
    )
    moved = sorted(k for k in recorded if recorded[k] != current[k])
    assert not moved, (
        f"engine output changed for {len(moved)} scenario(s): {moved}. If this was NOT "
        "intended it is a regression — fix the code, not the JSON. If it WAS intended, "
        "bump ENGINE_VERSION in domain/backtest/manifest.py and regenerate the baseline "
        "in the same change."
    )


def test_the_golden_baseline_records_the_engine_version_it_was_taken_at() -> None:
    """A baseline is only meaningful next to the engine version that produced it: if the
    digests still match but the recorded version has drifted, someone bumped the version
    without any output change (a namespace shift with nothing behind it) or regenerated
    the file without recording it."""
    recorded = json.loads(GOLDEN_PATH.read_text())
    assert recorded["engine_version"] == ENGINE_VERSION, (
        f"baseline was taken at engine_version={recorded['engine_version']!r} but the "
        f"engine now reports {ENGINE_VERSION!r}; regenerate the baseline in the same "
        "change that bumped the version."
    )


def _regenerate() -> None:
    GOLDEN_PATH.write_text(
        json.dumps(
            {"engine_version": ENGINE_VERSION, "digests": _current()},
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
    print(f"wrote {GOLDEN_PATH} at engine_version={ENGINE_VERSION}")


if __name__ == "__main__":
    _regenerate()
