"""K-09 (c) — the sizing ladder, tested as its own unit.

Position sizing used to be reachable only through a bar replay. Extracted into
``execution.sizing`` it is a pure function of ``(config, entry_price, equity)``, so
the ladder — raw method -> leverage -> signal strength -> configured min/max caps,
then the sleeve capacity cap — can be exercised directly.

The rules under test are the fail-closed ones, because they are what keeps a
misconfigured strategy financially inert instead of fabricating a notional:
an unparseable/non-finite formula param, a bust account, a non-positive entry price,
an unmodelled leverage mode and an unallocated sleeve must each resolve to 0.
"""

from __future__ import annotations

from decimal import Decimal

from entropia.domain.backtest.execution.sizing import (
    _cap_to_sleeve,
    _clamp_to_limits,
    _decimal_param,
    _kelly_capital_fraction,
    _leverage_multiplier,
    _position_size,
    _raw_position_size,
    leverage_is_modelled,
    sizing_is_modelled,
)
from entropia.domain.strategy.config import PositionSizeLimits
from tests.unit.test_backtest_engine import _config
from tests.unit.test_backtest_leverage_trailing import _config as _lev_config

_PRICE = Decimal("100")
_EQUITY = Decimal("10000")


# --------------------------------------------------------------------------- #
# _decimal_param — the unvalidated formula_params boundary                     #
# --------------------------------------------------------------------------- #
def test_decimal_param_reads_a_numeric_value() -> None:
    assert _decimal_param({"kelly_fraction": "0.5"}, "kelly_fraction") == Decimal("0.5")


def test_decimal_param_returns_none_for_an_absent_key() -> None:
    assert _decimal_param({}, "kelly_fraction") is None


def test_decimal_param_fails_closed_on_a_non_numeric_value() -> None:
    assert _decimal_param({"payoff_ratio": "abc"}, "payoff_ratio") is None
    assert _decimal_param({"payoff_ratio": None}, "payoff_ratio") is None


def test_decimal_param_rejects_non_finite_values() -> None:
    """``Decimal("nan")`` constructs without error but RAISES on the ordered
    comparisons downstream, and an ``Infinity`` payoff would read as a real edge.
    Both must fail closed here."""
    assert _decimal_param({"payoff_ratio": "nan"}, "payoff_ratio") is None
    assert _decimal_param({"payoff_ratio": "Infinity"}, "payoff_ratio") is None
    assert _decimal_param({"payoff_ratio": "-Infinity"}, "payoff_ratio") is None


# --------------------------------------------------------------------------- #
# _kelly_capital_fraction                                                      #
# --------------------------------------------------------------------------- #
def _kelly_sizing(**kw: str):
    return _config(
        method="formula_based_sizing", formula_type="kelly_criterion", **kw
    ).position_sizing


def test_kelly_fraction_applies_the_edge_formula() -> None:
    # W=0.6, R=2 -> edge = 0.6 - 0.4/2 = 0.4; absent kelly_fraction -> full Kelly
    assert _kelly_capital_fraction(_kelly_sizing(win_prob="0.6", payoff="2")) == Decimal("0.4")


def test_kelly_fraction_scales_by_the_fractional_multiplier() -> None:
    sizing = _kelly_sizing(win_prob="0.6", payoff="2", kelly_fraction="0.5")
    assert _kelly_capital_fraction(sizing) == Decimal("0.2")


def test_kelly_fraction_clamps_a_non_positive_edge_to_zero() -> None:
    """A losing edge sizes NOTHING — it never goes negative (a negative size would
    invert the PnL sign of every later trade)."""
    assert _kelly_capital_fraction(_kelly_sizing(win_prob="0.3", payoff="1")) == Decimal("0")


def test_kelly_fraction_is_none_for_out_of_range_probability() -> None:
    assert _kelly_capital_fraction(_kelly_sizing(win_prob="1.5", payoff="2")) is None
    assert _kelly_capital_fraction(_kelly_sizing(win_prob="0", payoff="2")) is None


def test_kelly_fraction_is_none_when_params_are_missing() -> None:
    assert _kelly_capital_fraction(_kelly_sizing()) is None


def test_a_garbage_kelly_fraction_is_not_upgraded_to_full_kelly() -> None:
    """An unreadable multiplier must not silently become 1.0 (full Kelly) — that
    would size LARGER than the user asked for."""
    assert (
        _kelly_capital_fraction(_kelly_sizing(win_prob="0.6", payoff="2", kelly_fraction="abc"))
        is None
    )


# --------------------------------------------------------------------------- #
# sizing_is_modelled — the shared Ready Check / engine predicate               #
# --------------------------------------------------------------------------- #
def test_sizing_is_modelled_for_the_three_honored_methods() -> None:
    assert sizing_is_modelled(_config(method="base_position_size"))
    assert sizing_is_modelled(_config(method="risk_based_sizing", risk_pct="2", stop_point="5"))
    assert sizing_is_modelled(
        _config(
            method="formula_based_sizing",
            formula_type="kelly_criterion",
            win_prob="0.6",
            payoff="2",
        )
    )


def test_sizing_is_not_modelled_for_a_custom_formula() -> None:
    assert not sizing_is_modelled(
        _config(method="formula_based_sizing", formula_type="custom_formula")
    )


def test_sizing_is_not_modelled_when_the_sub_config_is_missing() -> None:
    assert not sizing_is_modelled(_config(method="risk_based_sizing"))


# --------------------------------------------------------------------------- #
# Leverage (§10.2)                                                             #
# --------------------------------------------------------------------------- #
def test_no_leverage_normalizes_to_one_regardless_of_the_saved_multiplier() -> None:
    cfg = _lev_config(leverage_mode="no_leverage", leverage="5")
    assert leverage_is_modelled(cfg)
    assert _leverage_multiplier(cfg) == Decimal("1")


def test_isolated_leverage_applies_the_saved_multiplier() -> None:
    cfg = _lev_config(leverage_mode="isolated", leverage="3")
    assert leverage_is_modelled(cfg)
    assert _leverage_multiplier(cfg) == Decimal("3")


def test_cross_margin_is_never_modelled() -> None:
    """Cross-margin needs a portfolio risk model the engine does not implement; it
    fails closed rather than silently degrading to isolated semantics."""
    assert not leverage_is_modelled(_lev_config(leverage_mode="cross", leverage="3"))


# --------------------------------------------------------------------------- #
# _clamp_to_limits                                                             #
# --------------------------------------------------------------------------- #
# GH #550: the bounds are PERCENTAGES of resolved capital, so the clamp needs the equity
# and the entry price to evaluate them. Every case below is about the fail-closed
# behaviour and NOT about the conversion, so it is run at the calibration where a percent
# converts one-for-one into a unit (10 000 of equity at a price of 100), which keeps each
# expected number the pre-#550 number. The conversion is pinned in
# ``test_backtest_engine.py::test_clamp_to_limits_reads_its_bounds_as_percentages_of_capital``.
def _clamp(size: str, limits: PositionSizeLimits | None) -> Decimal:
    return _clamp_to_limits(
        Decimal(size), limits, equity=Decimal("10000"), entry_price=Decimal("100")
    )


def test_clamp_does_not_resurrect_a_zero_size_via_the_min_cap() -> None:
    """0 is the fail-closed "do not open" sentinel — a min cap must not lift it
    into a live position."""
    limits = _config(min_size="10").position_sizing.position_size_limits
    assert _clamp("0", limits) == Decimal("0")


def test_clamp_fails_closed_when_the_window_is_impossible() -> None:
    limits = _config(min_size="50", max_size="10").position_sizing.position_size_limits
    assert _clamp("30", limits) == Decimal("0")


def test_clamp_is_a_noop_without_limits() -> None:
    assert _clamp("33", None) == Decimal("33")


# --------------------------------------------------------------------------- #
# The full ladder                                                              #
# --------------------------------------------------------------------------- #
def test_limits_remain_the_final_word_after_a_leverage_boost() -> None:
    """A leveraged size is still capped — leverage must not be able to breach the
    configured maximum."""
    cfg = _lev_config(leverage_mode="isolated", leverage="5")
    raw = _raw_position_size(cfg, _PRICE, _EQUITY)
    assert raw == Decimal("10")
    assert _position_size(cfg, _PRICE, _EQUITY) == Decimal("50")  # 10 * 5x, no caps set


def test_risk_based_sizing_is_independent_of_the_entry_price() -> None:
    cfg = _config(method="risk_based_sizing", risk_pct="2", stop_point="5")
    assert _raw_position_size(cfg, Decimal("100"), _EQUITY) == _raw_position_size(
        cfg, Decimal("7"), _EQUITY
    )


def test_kelly_sizing_is_entry_price_dependent() -> None:
    """Kelly sizes a fraction of CAPITAL; converting that to units divides by price."""
    cfg = _config(
        method="formula_based_sizing", formula_type="kelly_criterion", win_prob="0.6", payoff="2"
    )
    assert _raw_position_size(cfg, Decimal("100"), _EQUITY) != _raw_position_size(
        cfg, Decimal("50"), _EQUITY
    )


def test_a_bust_account_sizes_nothing_rather_than_going_negative() -> None:
    cfg = _config(method="risk_based_sizing", risk_pct="2", stop_point="5")
    assert _raw_position_size(cfg, _PRICE, Decimal("-500")) == Decimal("0")


def test_an_unmodelled_method_sizes_nothing_rather_than_all_in() -> None:
    cfg = _config(method="formula_based_sizing", formula_type="custom_formula")
    assert _raw_position_size(cfg, _PRICE, _EQUITY) == Decimal("0")


# --------------------------------------------------------------------------- #
# _cap_to_sleeve — the allocation capacity bound                               #
# --------------------------------------------------------------------------- #
def test_cap_to_sleeve_caps_the_desired_size_to_the_sleeve_capacity() -> None:
    # sleeve 1000 at price 100 -> 10 units of capacity
    assert _cap_to_sleeve(Decimal("25"), Decimal("1000"), _PRICE) == Decimal("10")


def test_cap_to_sleeve_passes_a_size_that_already_fits() -> None:
    assert _cap_to_sleeve(Decimal("4"), Decimal("1000"), _PRICE) == Decimal("4")


def test_cap_to_sleeve_yields_nothing_for_an_unallocated_item() -> None:
    """A 0-capital sleeve fills NOTHING — it never falls back to the strategy's own
    capital."""
    assert _cap_to_sleeve(Decimal("25"), Decimal("0"), _PRICE) == Decimal("0")
    assert _cap_to_sleeve(Decimal("25"), Decimal("-1"), _PRICE) == Decimal("0")


def test_cap_to_sleeve_yields_nothing_for_a_non_positive_price() -> None:
    assert _cap_to_sleeve(Decimal("25"), Decimal("1000"), Decimal("0")) == Decimal("0")
