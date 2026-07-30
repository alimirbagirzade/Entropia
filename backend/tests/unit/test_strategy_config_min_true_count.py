"""I-15a (a) — Restrictions/Filters "Minimum N of M" combination (doc 02 §5.8).

Before this slice ``RestrictionsFilters.rule`` was ``Literal["any", "all"]`` and
``min_true_count`` did not exist anywhere in the repo, so the spec's third combination
was unrepresentable: a user who wanted "block only when at least 2 of my 3 filters fire"
could express neither the OR (too eager) nor the AND (too lax) alternative honestly.

These tests pin the full path end to end:

* **model** — N is required for ``min_n_of_m`` and DROPPED for any/all, so switching the
  rule back never leaves a stale count in the saved revision;
* **compiler** — N above the ENABLED filter count is dead config
  (``RESTRICTION_MIN_COUNT_UNSATISFIABLE``), the restriction-side twin of the entry
  supporting-count rule;
* **engine** — the gate genuinely blocks at N active filters, with N=1 reproducing
  ``any`` and N=len reproducing ``all`` BYTE-FOR-BYTE (the two shipped rules are
  untouched), plus the strictly-between case neither old rule could express;
* **manifest** — the ENGINE_VERSION bump shifts the ``execution_key`` namespace, so a
  result produced by an engine that could not evaluate Minimum-N is never idempotently
  reused for a re-RUN (INF-04/INF-05).
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from pydantic import ValidationError as PydanticValidationError

from entropia.domain.backtest.engine import EngineOutput, restrictions_are_modelled, run_engine
from entropia.domain.backtest.manifest import ENGINE_VERSION, build_run_manifest
from entropia.domain.strategy.compiler import (
    CODE_RESTRICTION_MIN_COUNT_UNSATISFIABLE,
    validate_strategy_config,
)
from entropia.domain.strategy.config import RestrictionsFilters, StrategyConfig
from tests.unit.engine_signal_plan import sma_entry_plan

# The ENGINE_VERSION this slice replaced — the namespace the execution_key must leave.
_PRIOR_ENGINE_VERSION = "backtest-engine-v18-funding-step-order"


# --------------------------------------------------------------------------- #
# Fixtures                                                                     #
# --------------------------------------------------------------------------- #


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


def _blackout(start: str, end: str, *, filter_id: str) -> dict[str, Any]:
    """A date-blackout filter — ACTIVE for every bar inside [start, end]."""
    return _filter(
        "date_blackout_filter",
        {"date_ranges": [{"start": start, "end": end}]},
        filter_id=filter_id,
    )


def _never_active_streak(filter_id: str = "flt_cl") -> dict[str, Any]:
    """A consecutive-loss filter with a streak cap no fixture run ever reaches."""
    return _filter("consecutive_loss_filter", {"max_losses": 5}, filter_id=filter_id)


def _payload(restrictions: dict[str, Any]) -> dict[str, Any]:
    """A minimal structurally + semantically VALID StrategyConfig payload.

    Only ``restrictions_filters`` varies across these tests; every other section is the
    smallest shape that passes the compiler so an issue list is never polluted by an
    unrelated rule.
    """
    return {
        "strategy_root_id": "strat_root_1",
        "display_name": "Minimum-N Fixture",
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
            "costs": {"slippage_mode": "percentage_slippage", "slippage_value": "0"},
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
        "position_sizing": {"method": "base_position_size", "base_position_size": "50"},
        "restrictions_filters": restrictions,
        "conflict_position_handling": {},
    }


def _config(restrictions: dict[str, Any]) -> StrategyConfig:
    return StrategyConfig.model_validate(_payload(restrictions))


def _bar(ts: str, close: str) -> dict[str, Any]:
    """A flat bar (o=h=l=c) — no intrabar surprises."""
    return {
        "timestamp": ts,
        "open": close,
        "high": close,
        "low": close,
        "close": close,
        "volume": "10",
    }


def _breakout_script() -> list[dict[str, Any]]:
    """20 flat warm-up bars @100 then an up-close @102 — an SMA(3) cross UP = one long."""
    bars = [_bar(f"2024-01-{i + 1:02d}T00:00:00Z", "100") for i in range(20)]
    bars.append(_bar("2024-01-21T00:00:00Z", "102"))
    return bars


def _run(config: StrategyConfig) -> EngineOutput:
    bars = _breakout_script()

    def batched() -> Iterator[list[dict[str, Any]]]:
        for start in range(0, len(bars), 8):
            yield bars[start : start + 8]

    return run_engine(
        strategy_config=config,
        bar_batches=batched(),
        execution_key="exec_key_min_true_count",
        indicator_plan=sma_entry_plan(validity="until_opposite_signal"),
    )


def _was_blocked(out: EngineOutput) -> bool:
    """Read the veto from the FILTERED journal (I-02).

    ``filtered_no_entry`` left ``signal_events`` when Filtered Events became its own
    artifact (doc 15 §3.2 "View Filtered Events", §16). The Minimum-N assertions below
    are unchanged — only the journal this helper reads is."""
    return any(
        e.detail["reason"] == "restriction_blocked"
        for e in out.filtered_events
        if e.event_type == "filtered_no_entry"
    )


# --------------------------------------------------------------------------- #
# Model — presence + drop-on-switch (mirrors SignalBlock.min_supporting_count) #
# --------------------------------------------------------------------------- #


def test_strategy_config_min_true_count_is_required_for_the_min_n_of_m_rule() -> None:
    with pytest.raises(PydanticValidationError, match="Minimum restriction count required"):
        RestrictionsFilters.model_validate({"rule": "min_n_of_m", "filters": []})


def test_strategy_config_min_true_count_is_dropped_under_the_any_and_all_rules() -> None:
    # A stale count sent under any/all is silently DROPPED, not rejected — switching the
    # rule back can never leave an N behind in the saved revision.
    for rule in ("any", "all"):
        model = RestrictionsFilters.model_validate(
            {"rule": rule, "min_true_count": 3, "filters": []}
        )
        assert model.min_true_count is None, rule


def test_strategy_config_min_true_count_rejects_zero_and_negative_counts() -> None:
    for bad in (0, -1):
        with pytest.raises(PydanticValidationError):
            RestrictionsFilters.model_validate({"rule": "min_n_of_m", "min_true_count": bad})


def test_strategy_config_min_true_count_defaults_stay_backward_compatible() -> None:
    # An untouched pre-I-15a payload parses exactly as before: rule="any", no count.
    model = RestrictionsFilters.model_validate({"filters": []})
    assert model.rule == "any"
    assert model.min_true_count is None


# --------------------------------------------------------------------------- #
# Compiler — N above the ENABLED filter count is dead config                   #
# --------------------------------------------------------------------------- #


def _issue_codes(restrictions: dict[str, Any]) -> set[str]:
    config, issues = validate_strategy_config(_payload(restrictions))
    assert config is not None, issues
    return {issue["code"] for issue in issues}


def test_strategy_config_min_true_count_above_enabled_filters_is_rejected() -> None:
    codes = _issue_codes(
        {
            "rule": "min_n_of_m",
            "min_true_count": 3,
            "filters": [_blackout("2024-01-01", "2024-12-31", filter_id="flt_a")],
        }
    )
    assert CODE_RESTRICTION_MIN_COUNT_UNSATISFIABLE in codes


def test_strategy_config_min_true_count_counts_only_enabled_filters() -> None:
    # M is the ENABLED subset (the disabled-child convention), so an N that fits the
    # TOTAL but not the enabled subset is still unsatisfiable.
    filters = [
        _blackout("2024-01-01", "2024-12-31", filter_id="flt_a"),
        _filter("consecutive_loss_filter", {"max_losses": 5}, enabled=False, filter_id="flt_b"),
    ]
    codes = _issue_codes({"rule": "min_n_of_m", "min_true_count": 2, "filters": filters})
    assert CODE_RESTRICTION_MIN_COUNT_UNSATISFIABLE in codes


def test_strategy_config_min_true_count_equal_to_enabled_filters_is_accepted() -> None:
    filters = [
        _blackout("2024-01-01", "2024-12-31", filter_id="flt_a"),
        _never_active_streak("flt_b"),
    ]
    codes = _issue_codes({"rule": "min_n_of_m", "min_true_count": 2, "filters": filters})
    assert CODE_RESTRICTION_MIN_COUNT_UNSATISFIABLE not in codes


def test_strategy_config_min_true_count_is_not_checked_under_any_or_all() -> None:
    # The rule was never min_n_of_m, so the (dropped) count cannot make it unsatisfiable.
    for rule in ("any", "all"):
        codes = _issue_codes({"rule": rule, "min_true_count": 9, "filters": []})
        assert CODE_RESTRICTION_MIN_COUNT_UNSATISFIABLE not in codes, rule


# --------------------------------------------------------------------------- #
# Engine — the config -> behaviour proof                                       #
# --------------------------------------------------------------------------- #

# One filter ACTIVE on the breakout day + one that never fires.
_ONE_ACTIVE = [
    _blackout("2024-01-01", "2024-12-31", filter_id="flt_a"),
    _never_active_streak("flt_b"),
]
# Two ACTIVE + one that never fires — the strictly-between case.
_TWO_ACTIVE = [
    _blackout("2024-01-01", "2024-12-31", filter_id="flt_a"),
    _blackout("2024-01-15", "2024-02-15", filter_id="flt_b"),
    _never_active_streak("flt_c"),
]


def test_strategy_config_min_true_count_gate_blocks_at_n_and_allows_below_it() -> None:
    blocked = _run(_config({"rule": "min_n_of_m", "min_true_count": 1, "filters": _ONE_ACTIVE}))
    assert not blocked.trades
    assert _was_blocked(blocked)

    allowed = _run(_config({"rule": "min_n_of_m", "min_true_count": 2, "filters": _ONE_ACTIVE}))
    assert len(allowed.trades) == 1
    assert not _was_blocked(allowed)


def test_strategy_config_min_true_count_expresses_what_any_and_all_cannot() -> None:
    # Two of three filters active. "any" would block (too eager), "all" would allow
    # (too lax); Minimum 2 of 3 blocks and Minimum 3 of 3 allows — the gate genuinely
    # sits between the two shipped rules rather than aliasing one of them.
    assert _was_blocked(_run(_config({"rule": "any", "filters": _TWO_ACTIVE})))
    assert not _was_blocked(_run(_config({"rule": "all", "filters": _TWO_ACTIVE})))

    at_two = _run(_config({"rule": "min_n_of_m", "min_true_count": 2, "filters": _TWO_ACTIVE}))
    assert not at_two.trades
    assert _was_blocked(at_two)

    at_three = _run(_config({"rule": "min_n_of_m", "min_true_count": 3, "filters": _TWO_ACTIVE}))
    assert len(at_three.trades) == 1
    assert not _was_blocked(at_three)


def test_strategy_config_min_true_count_boundaries_reproduce_any_and_all_exactly() -> None:
    # N=1 IS "any" and N=len IS "all" — the two shipped rules keep their pre-I-15a
    # behaviour byte-for-byte, which is why the bump is a namespace shift and not a
    # numeric restatement of every existing result.
    for filters in (_ONE_ACTIVE, _TWO_ACTIVE):
        any_out = _run(_config({"rule": "any", "filters": filters}))
        min_one = _run(_config({"rule": "min_n_of_m", "min_true_count": 1, "filters": filters}))
        assert [t.pnl for t in min_one.trades] == [t.pnl for t in any_out.trades]
        assert _was_blocked(min_one) == _was_blocked(any_out)

        all_out = _run(_config({"rule": "all", "filters": filters}))
        min_all = _run(
            _config({"rule": "min_n_of_m", "min_true_count": len(filters), "filters": filters})
        )
        assert [t.pnl for t in min_all.trades] == [t.pnl for t in all_out.trades]
        assert _was_blocked(min_all) == _was_blocked(all_out)


def test_strategy_config_min_true_count_keeps_the_fail_closed_modelling_predicate() -> None:
    # Minimum-N is a COMBINATION, not a filter type: an unmodelled filter still fails
    # closed exactly as under any/all (never a silently unfiltered run).
    cfg = _config(
        {
            "rule": "min_n_of_m",
            "min_true_count": 1,
            "filters": [_filter("volatility_filter", filter_id="flt_v")],
        }
    )
    assert not restrictions_are_modelled(cfg)
    assert not _run(cfg).trades


# --------------------------------------------------------------------------- #
# Manifest — the execution_key namespace shift (INF-04/INF-05)                 #
# --------------------------------------------------------------------------- #


def _manifest(engine_version: str):
    return build_run_manifest(
        run_id="btrun_min_n",
        composition_id="mbws_1",
        composition_snapshot_id="snap_A",
        composition_fingerprint="fp_1",
        item_manifest={
            "items": [
                {
                    "item_id": "mbi_1",
                    "kind": "strategy",
                    "root_id": "wo_a",
                    "revision_id": "rev_a",
                    "position": 10,
                    "enabled": True,
                }
            ]
        },
        capital_mode={"enabled": False},
        requested_by_principal_id="user_1",
        preflight={"ready_report_id": "rcrpt_1", "state": "ready", "warning_count": 0},
        correlation_id="corr_1",
        created_at_iso="2024-01-01T00:00:00Z",
        engine_version=engine_version,
    )


def test_strategy_config_min_true_count_bumps_engine_version_and_shifts_execution_key() -> None:
    current = _manifest(ENGINE_VERSION)
    prior = _manifest(_PRIOR_ENGINE_VERSION)
    assert current.manifest["identity"]["engine_version"] == ENGINE_VERSION
    # An engine that could not evaluate Minimum-N must never share this namespace...
    assert current.execution_key != prior.execution_key
    # ...while the same pin reproduces the same key.
    assert current.execution_key == _manifest(ENGINE_VERSION).execution_key
