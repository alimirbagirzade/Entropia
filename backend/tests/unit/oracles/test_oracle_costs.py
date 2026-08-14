"""Oracle — trading costs and funding/carry (ADIM 12).

Canonical rules under test (doc 02 §2 Costs; doc 12 §8.4 funding; Master Ref §6.3):

* the SPREAD is paid half per side, adversely — a buy lifts the offer, a sell hits the bid;
* percentage SLIPPAGE scales the (already spread-adjusted) price adversely;
* COMMISSION is a per-fill fee, charged twice for a round trip;
* FUNDING is charged on the position's notional while it is HELD: a long pays a positive
  rate, a short receives it, and a record only fires once it is AVAILABLE (its available
  time, never its event time).

Every fixture is the zero-cost baseline with exactly ONE cost switched on, so the delta is
attributable. Baseline for reference: long in at 102, out at 104, 50 units, pnl 100.00.

Hand arithmetic (long, entry 102 / exit 104, size 50)::

    effective buy  = (raw + spread/2) * (1 + slippage)
    effective sell = (raw - spread/2) * (1 - slippage)
    pnl            = (exit_eff - entry_eff) * size - commission * 2
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from entropia.domain.backtest.engine import EngineOutput
from entropia.domain.backtest.funding import FundingRecord, FundingSchedule
from tests.unit.oracles.harness import bar, flat_run, oracle_config, run_oracle

SIZE = Decimal("50")
_UP_CROSS = bar(21, "100", "102", "100", "102")
_DOWN_CROSS = bar(21, "100", "100", "98", "98")
_LONG_BARS = [*flat_run(), _UP_CROSS, bar(22, "102", "104", "102", "104")]
_SHORT_BARS = [*flat_run(), _DOWN_CROSS, bar(22, "98", "98", "96", "96")]


def _costs(**overrides: str) -> dict[str, str]:
    return {"slippage_mode": "percentage_slippage", "slippage_value": "0", **overrides}


def _long(costs: dict[str, str]) -> EngineOutput:
    return run_oracle(oracle_config(direction="long", protection={}, costs=costs), _LONG_BARS)


def _short(costs: dict[str, str]) -> EngineOutput:
    return run_oracle(oracle_config(direction="short", protection={}, costs=costs), _SHORT_BARS)


# --------------------------------------------------------------------------- #
# Spread / slippage / commission                                               #
# --------------------------------------------------------------------------- #
def test_zero_costs_are_an_identity_on_the_raw_bar_prices() -> None:
    """The control every other case is measured against: fills ARE the bar prices."""
    trade = _long(_costs()).trades[0]
    assert (trade.entry_price, trade.exit_price, trade.pnl) == (
        Decimal("102.00"),
        Decimal("104.00"),
        Decimal("100.00"),
    )


def test_a_spread_costs_half_of_it_on_each_side_of_a_long() -> None:
    """spread 0.40 -> half = 0.20. Buy 102 + 0.20 = 102.20; sell 104 - 0.20 = 103.80.
    pnl = (103.80 - 102.20) * 50 = 80.00 — exactly one full spread * 50 units below the
    zero-cost 100.00."""
    trade = _long(_costs(spread="0.40")).trades[0]
    assert (trade.entry_price, trade.exit_price) == (Decimal("102.20"), Decimal("103.80"))
    assert trade.pnl == Decimal("80.00")


def test_a_spread_costs_half_of_it_on_each_side_of_a_short_too() -> None:
    """The mirror: a short SELLS to open (98 - 0.20 = 97.80) and BUYS to close
    (96 + 0.20 = 96.20). pnl = (96.20 - 97.80) * 50 * (-1) = 80.00 — the same 20.00
    penalty the long paid, never a windfall."""
    trade = _short(_costs(spread="0.40")).trades[0]
    assert (trade.entry_price, trade.exit_price) == (Decimal("97.80"), Decimal("96.20"))
    assert trade.pnl == Decimal("80.00")


def test_percentage_slippage_moves_both_fills_against_the_run() -> None:
    """0.5% -> buy 102 * 1.005 = 102.51; sell 104 * 0.995 = 103.48.
    pnl = (103.48 - 102.51) * 50 = 48.50."""
    trade = _long(_costs(slippage_value="0.5")).trades[0]
    assert (trade.entry_price, trade.exit_price) == (Decimal("102.51"), Decimal("103.48"))
    assert trade.pnl == Decimal("48.50")


def test_percentage_slippage_moves_a_short_the_other_way() -> None:
    """0.5% -> sell 98 * 0.995 = 97.51; buy 96 * 1.005 = 96.48.
    pnl = (96.48 - 97.51) * 50 * (-1) = 51.50."""
    trade = _short(_costs(slippage_value="0.5")).trades[0]
    assert (trade.entry_price, trade.exit_price) == (Decimal("97.51"), Decimal("96.48"))
    assert trade.pnl == Decimal("51.50")


def test_spread_is_applied_before_slippage_scales_the_price() -> None:
    """The ORDER of the two is observable. Spread first, then the percentage:
    buy  = (102 + 0.20) * 1.005 = 102.711 -> 102.71
    sell = (104 - 0.20) * 0.995 = 103.281 -> 103.28
    pnl  = (103.28 - 102.71) * 50 = 28.50.
    Slippage-first would give (102 * 1.005) + 0.20 = 102.71 as well on this side but
    103.28 vs 103.28 — the pair is pinned so a reordering that shifts either fill by a
    cent is caught."""
    trade = _long(_costs(spread="0.40", slippage_value="0.5")).trades[0]
    assert (trade.entry_price, trade.exit_price) == (Decimal("102.71"), Decimal("103.28"))
    assert trade.pnl == Decimal("28.50")


def test_commission_is_charged_once_per_fill_and_the_entry_pays_at_entry() -> None:
    """Fills are untouched (102 / 104). Commission 7 is PER-FILL (GH #552, PD-2), and this
    round trip is two fills, so the account pays 14 in total — but not in one place.

    The trade row carries only its own EXIT fill: 100.00 - 7 = 93.00. The entry fill's 7
    was charged to equity when it filled, which is the same seam the scale ladder and
    ``absorb_remainder`` already use, and is why ``final_equity`` (below) is 10086 while
    this row reads 93.

    Renamed from ``..._charged_twice_for_a_round_trip``, which asserted 86.00 = 100 - 7*2:
    the whole round trip billed at the exit. That model made cost scale with the number of
    partial CLOSES rather than fills — see the partial-close oracle in
    ``test_oracle_position_lifecycle.py``."""
    trade = _long(_costs(commission="7")).trades[0]
    assert (trade.entry_price, trade.exit_price) == (Decimal("102.00"), Decimal("104.00"))
    assert trade.pnl == Decimal("93.00")


def test_costs_reach_the_run_total_and_not_only_the_trade_row() -> None:
    """A cost that shows on the trade but not in equity would flatter the summary.

    This is the assertion that keeps the per-FILL split honest: the trade row reads 93.00
    (its exit fill only) but the account is down the ENTRY fill's 7 as well, so the run
    total is 100.00 - 14 = 86.00 and equity lands at 10086.00 — the same total the
    round-trip model produced, reached by charging each fill once.

    ``net_profit`` is derived from equity, not summed from the trade rows; if it were
    summed, this split would silently overstate the run by the entry commission."""
    out = _long(_costs(commission="7"))
    assert out.trades[0].pnl == Decimal("93.00")
    assert out.summary["net_profit"] == Decimal("86.00")
    assert out.summary["final_equity"] == Decimal("10086.00")


# --------------------------------------------------------------------------- #
# Funding / carry                                                              #
# --------------------------------------------------------------------------- #
def _day(day: int) -> datetime:
    return datetime(2024, 1, day, tzinfo=UTC)


def _schedule(*records: tuple[int, int, str]) -> FundingSchedule:
    """``(event_day, available_day, rate)`` triples — the two times kept SEPARATE."""
    return FundingSchedule(
        source_revision_id="rdrev_oracle",
        records=tuple(
            FundingRecord(available_at=_day(av), event_at=_day(ev), rate=Decimal(rate))
            for ev, av, rate in records
        ),
        has_instrument_mapping=True,
    )


_HELD_LONG = [
    *flat_run(),
    _UP_CROSS,
    bar(22, "102", "102", "102", "102"),
    bar(23, "102", "104", "102", "104"),
]
_HELD_SHORT = [
    *flat_run(),
    _DOWN_CROSS,
    bar(22, "98", "98", "98", "98"),
    bar(23, "98", "98", "96", "96"),
]


def test_a_long_pays_a_positive_funding_rate_on_its_notional() -> None:
    """Notional = entry 102 * 50 = 5100. Charge = 5100 * 0.001 = 5.10, PAID.
    Trade pnl is untouched at (104 - 102) * 50 = 100.00; equity carries the cost:
    10000 + 100.00 - 5.10 = 10094.90."""
    out = run_oracle(
        oracle_config(direction="long", protection={}),
        _HELD_LONG,
        funding=_schedule((22, 22, "0.001")),
    )
    assert out.trades[0].pnl == Decimal("100.00")
    assert out.summary["final_equity"] == Decimal("10094.90")


def test_a_short_receives_the_same_positive_rate() -> None:
    """Notional = entry 98 * 50 = 4900. The short RECEIVES 4900 * 0.001 = 4.90.
    pnl = (96 - 98) * 50 * (-1) = 100.00; equity = 10000 + 100.00 + 4.90 = 10104.90."""
    out = run_oracle(
        oracle_config(direction="short", protection={}),
        _HELD_SHORT,
        funding=_schedule((22, 22, "0.001")),
    )
    assert out.trades[0].pnl == Decimal("100.00")
    assert out.summary["final_equity"] == Decimal("10104.90")


def test_funding_dated_after_the_last_replayed_bar_can_never_be_charged() -> None:
    """A 50% rate on day 28 against a run that ends on day 23: the cursor never reaches it,
    so equity is the funding-free 10100.00. Future leakage is impossible by construction,
    not by a comparison someone has to remember to write."""
    out = run_oracle(
        oracle_config(direction="long", protection={}),
        _HELD_LONG,
        funding=_schedule((28, 28, "0.5")),
    )
    assert out.summary["final_equity"] == Decimal("10100.00")


def test_a_rate_available_while_flat_is_consumed_without_being_charged() -> None:
    """Day 5 is inside the flat look-back — no position is held, so the perp convention
    bills nothing and equity stays at the funding-free 10100.00."""
    out = run_oracle(
        oracle_config(direction="long", protection={}),
        _HELD_LONG,
        funding=_schedule((5, 5, "0.001")),
    )
    assert out.summary["final_equity"] == Decimal("10100.00")


def test_availability_not_the_event_time_decides_which_bar_is_billed() -> None:
    """The SAME event (day 22, rate 0.001) charged the SAME 5.10 lands on a different bar
    depending on when it became usable: available day 22 -> bar 22; available day 23 ->
    bar 23. A run that reads event time would bill both on bar 22 — a look-ahead."""
    early = run_oracle(
        oracle_config(direction="long", protection={}),
        _HELD_LONG,
        funding=_schedule((22, 22, "0.001")),
    )
    late = run_oracle(
        oracle_config(direction="long", protection={}),
        _HELD_LONG,
        funding=_schedule((22, 23, "0.001")),
    )

    def charge_bar(out: EngineOutput) -> int:
        event = next(e for e in out.signal_events if e.event_type == "funding_charge")
        return int(event.detail["bar_seq"])

    assert charge_bar(early) == 22
    assert charge_bar(late) == 23
    assert early.summary["final_equity"] == late.summary["final_equity"] == Decimal("10094.90")


def test_an_empty_schedule_is_the_funding_free_run() -> None:
    out = run_oracle(
        oracle_config(direction="long", protection={}), _HELD_LONG, funding=_schedule()
    )
    assert out.summary["final_equity"] == Decimal("10100.00")
