"""K-09 (b) — the partial-close ratchet and the scaling ladder's cap precedence.

``resolve_scale_rejection`` is the reason this slice is worth having on its own. Its
cap ORDER is behaviour, not an implementation detail: the losing cap's name is written
into the rejected layer's ledger entry, so which cap "wins" when several bind at once
is observable to a reviewer reconstructing why a layer did not fill. Before the
extraction that order could only be exercised by constructing a bar replay that made
several caps bind simultaneously; now it is pinned directly.

``apply_partial_aftermath`` carries the one-time-ratchet invariant: a later partial
close may only TIGHTEN the locked stop, never loosen it.
"""

from __future__ import annotations

from decimal import Decimal

from entropia.domain.backtest.execution.scaling import (
    apply_partial_aftermath,
    resolve_scale_layer_size,
    resolve_scale_rejection,
    scale_threshold_crossed,
)
from entropia.domain.backtest.execution.state import _Position

_ZERO = Decimal("0")


def _pos(
    *,
    direction: str = "long",
    entry: str = "100",
    stop: str | None = None,
    anchor: str = "100",
    trail: str | None = None,
    lock: str | None = None,
) -> _Position:
    return _Position(
        direction=direction,
        entry_time="2024-01-21T00:00:00Z",
        entry_price=Decimal(entry),
        size=Decimal("10"),
        initial_size=Decimal("10"),
        entry_notional=Decimal(entry) * 10,
        peak_notional=Decimal(entry) * 10,
        entry_bar_seq=1,
        position_seq=1,
        pct_stop=Decimal(stop) if stop is not None else None,
        abs_stop=None,
        trail_anchor=Decimal(anchor),
        trail_pct=Decimal(trail) if trail is not None else None,
        trail_lock_in_pct=Decimal(lock) if lock is not None else None,
        scale_reference=Decimal(entry),
    )


def _aftermath(pos: _Position, price: str, mode: str) -> bool:
    return apply_partial_aftermath(
        pos, Decimal(price), aftermath=mode, half_spread=_ZERO, slippage=_ZERO
    )


# --------------------------------------------------------------------------- #
# apply_partial_aftermath                                                      #
# --------------------------------------------------------------------------- #
def test_move_stop_to_entry_breakevens_the_remainder() -> None:
    pos = _pos(stop="95")
    assert _aftermath(pos, "110", "move_stop_to_entry") is False  # not a profit lock
    assert pos.pct_stop == Decimal("100")


def test_lock_in_profit_sets_the_stop_to_the_achieved_price() -> None:
    pos = _pos(stop="95")
    assert _aftermath(pos, "110", "lock_in_profit") is True
    assert pos.pct_stop == Decimal("110.00")


def test_lock_in_profit_is_a_one_time_ratchet_for_a_long() -> None:
    """A LATER partial close may only tighten the lock, never loosen it."""
    pos = _pos(stop="95")
    _aftermath(pos, "110", "lock_in_profit")
    _aftermath(pos, "104", "lock_in_profit")  # worse price — must not move the stop down
    assert pos.pct_stop == Decimal("110.00")


def test_lock_in_profit_ratchets_downward_for_a_short() -> None:
    pos = _pos(direction="short", stop="105")
    _aftermath(pos, "90", "lock_in_profit")
    _aftermath(pos, "96", "lock_in_profit")
    assert pos.pct_stop == Decimal("90.00")


def test_trailing_stop_aftermath_force_activates_the_trail() -> None:
    """The partial exit itself is the activation event, even below the configured
    profit-lock threshold."""
    pos = _pos(anchor="100", trail="0.02", lock="0.05")
    assert _aftermath(pos, "110", "trailing_stop") is True
    assert pos.trail_anchor == Decimal("105.00")  # entry * (1 + 0.05)


def test_trailing_aftermath_never_moves_the_anchor_backward() -> None:
    pos = _pos(anchor="120", trail="0.02", lock="0.05")
    _aftermath(pos, "110", "trailing_stop")
    assert pos.trail_anchor == Decimal("120")


def test_an_unconfigured_trailing_aftermath_locks_nothing() -> None:
    pos = _pos(anchor="100")  # no trail_pct / trail_lock_in_pct
    assert _aftermath(pos, "110", "trailing_stop") is False
    assert pos.trail_anchor == Decimal("100")


# --------------------------------------------------------------------------- #
# scale_threshold_crossed / resolve_scale_layer_size                           #
# --------------------------------------------------------------------------- #
def test_a_long_ladder_steps_on_an_adverse_move_down() -> None:
    kw = {"reference": Decimal("100"), "distance_pct": Decimal("1"), "is_long": True}
    assert scale_threshold_crossed(close=Decimal("99"), **kw)
    assert not scale_threshold_crossed(close=Decimal("99.5"), **kw)


def test_a_short_ladder_steps_on_an_adverse_move_up() -> None:
    kw = {"reference": Decimal("100"), "distance_pct": Decimal("1"), "is_long": False}
    assert scale_threshold_crossed(close=Decimal("101"), **kw)
    assert not scale_threshold_crossed(close=Decimal("100.5"), **kw)


def test_layer_size_from_a_fixed_amount() -> None:
    assert resolve_scale_layer_size(
        basis="fixed_amount",
        value=Decimal("3"),
        initial_size=Decimal("10"),
        current_size=Decimal("25"),
    ) == Decimal("3")


def test_layer_size_percent_of_initial_ignores_the_grown_position() -> None:
    assert resolve_scale_layer_size(
        basis="percent_of_initial",
        value=Decimal("50"),
        initial_size=Decimal("10"),
        current_size=Decimal("25"),
    ) == Decimal("5")


def test_layer_size_percent_of_current_compounds_with_the_position() -> None:
    assert resolve_scale_layer_size(
        basis="percent_of_current",
        value=Decimal("50"),
        initial_size=Decimal("10"),
        current_size=Decimal("25"),
    ) == Decimal("12.5")


# --------------------------------------------------------------------------- #
# resolve_scale_rejection — the OBSERVABLE cap precedence                      #
# --------------------------------------------------------------------------- #
def _reject(**kw):
    base = {
        "layer_size": Decimal("5"),
        "layer_notional": Decimal("500"),
        "scaled_size": Decimal("15"),
        "max_total_size": None,
        "max_position_size": None,
        "sleeve_remaining": None,
        "portfolio_headroom": None,
    }
    return resolve_scale_rejection(**{**base, **kw})


def test_an_uncapped_candidate_is_accepted() -> None:
    assert _reject() == (None, None)


def test_a_degenerate_layer_is_rejected_before_any_cap() -> None:
    """A percent basis can quantize to 0; that must never become a phantom 0-size
    layer, and it is caught before any cap can claim the rejection."""
    reason, cap = _reject(layer_size=_ZERO, max_total_size=Decimal("1"))
    assert reason == "layer_size_not_positive"
    assert cap is None


def test_the_per_strategy_total_outranks_the_position_size_limit() -> None:
    reason, cap = _reject(max_total_size=Decimal("12"), max_position_size=Decimal("11"))
    assert reason == "max_total_exposure"
    assert cap == "12"


def test_the_position_size_limit_outranks_the_sleeve() -> None:
    reason, cap = _reject(max_position_size=Decimal("11"), sleeve_remaining=Decimal("100"))
    assert reason == "position_size_limit"
    assert cap == "11"


def test_the_sleeve_outranks_the_composition_wide_cap() -> None:
    reason, cap = _reject(sleeve_remaining=Decimal("100"), portfolio_headroom=Decimal("50"))
    assert reason == "sleeve_capacity"
    assert cap == "100.00"


def test_the_composition_wide_cap_is_the_last_word() -> None:
    reason, cap = _reject(portfolio_headroom=Decimal("50"))
    assert reason == "portfolio_max_total_exposure"
    assert cap == "50.00"


def test_a_negative_headroom_is_reported_as_zero_not_negative() -> None:
    _, cap = _reject(portfolio_headroom=Decimal("-30"))
    assert cap == "0.00"


def test_an_unset_bound_does_not_reject() -> None:
    """``None`` means the bound is not configured for this run — never a default cap."""
    assert _reject(max_total_size=None, sleeve_remaining=None) == (None, None)


def test_a_layer_that_exactly_fits_the_sleeve_is_accepted() -> None:
    """The cap binds on EXCESS only — an exact fit is not an over-cap layer."""
    assert _reject(layer_notional=Decimal("500"), sleeve_remaining=Decimal("500")) == (None, None)
