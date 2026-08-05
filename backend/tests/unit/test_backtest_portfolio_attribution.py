"""ADIM 19 — per-item attribution and contribution over one shared ledger (contained).

The load-bearing property is RECONCILIATION: the per-item rows a Result publishes must sum
to the portfolio total exactly, with no residual and no tolerance. Everything else here
exists to keep that property honest when a mark is missing.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from entropia.domain.backtest.execution.attribution import (
    ATTRIBUTION_POLICY_VERSION,
    CONTRIBUTION_METHOD,
    COUNTERFACTUAL_MARGINAL_STATUS,
    NO_OPEN_POSITION,
    UNMARKED_POSITION,
    AttributionError,
    UnknownAttributionItemError,
    attribute,
    build_contribution_report,
    contribution_correlation,
    contribution_series,
    pearson,
)
from entropia.domain.backtest.execution.portfolio import _pearson as shipped_pearson
from entropia.domain.backtest.execution.portfolio_ledger import (
    MarkPrice,
    PortfolioLedger,
    ledger_for_items,
)

_ORDINALS = {"ci_a": 0, "ci_b": 1}


def _ledger() -> PortfolioLedger:
    return ledger_for_items(
        pool_initial=Decimal("10000.00"),
        reserve_percent=Decimal("10.00"),
        shares={"ci_a": Decimal("40.00"), "ci_b": Decimal("35.00")},
        compound=True,
    )


def _fresh(price: str) -> MarkPrice:
    return MarkPrice(Decimal(price), "fresh_bar_close")


# --------------------------------------------------------------------------- #
# 1. reconciliation — the whole point
# --------------------------------------------------------------------------- #
def test_realised_rows_sum_to_the_portfolio_with_zero_residual() -> None:
    ledger = _ledger()
    ledger.book_trade("ci_a", gross_pnl=Decimal("500.00"), commission=Decimal("10.00"))
    ledger.book_trade("ci_b", gross_pnl=Decimal("-120.00"), commission=Decimal("4.00"))
    ledger.book_funding("ci_b", amount=Decimal("7.50"))
    ledger.book_other_cost("ci_a", amount=Decimal("2.25"))

    report = attribute(ledger=ledger, t_ms=1_000, pin_ordinals=_ORDINALS)

    assert report.realized_residual == Decimal("0")
    assert report.realized_reconciled is True
    assert report.realized_total == ledger.equity - ledger.plan.pool_initial
    assert sum(row.net_realized for row in report.rows) == report.realized_total


def test_marked_rows_sum_to_the_marked_portfolio_with_zero_residual() -> None:
    ledger = _ledger()
    ledger.book_trade("ci_a", gross_pnl=Decimal("500.00"), commission=Decimal("10.00"))
    ledger.set_position("ci_a", direction="long", size=Decimal("2"), entry_price=Decimal("100.00"))
    ledger.set_position("ci_b", direction="short", size=Decimal("3"), entry_price=Decimal("50.00"))

    marks = {"ci_a": _fresh("110.00"), "ci_b": _fresh("45.00")}
    report = attribute(ledger=ledger, t_ms=1_000, marks=marks, pin_ordinals=_ORDINALS)

    assert report.unmarked_items == ()
    assert report.marked_residual == Decimal("0")
    assert report.marked_reconciled is True
    assert report.marked_equity == ledger.equity + report.unrealized_total
    assert sum(row.total_contribution for row in report.rows) == (
        report.marked_equity - report.pool_initial
    )
    # long +10 * 2 = +20 ; short (50-45) * 3 = +15
    assert report.by_item("ci_a").unrealized == Decimal("20.00")
    assert report.by_item("ci_b").unrealized == Decimal("15.00")
    assert report.unrealized_total == Decimal("35.00")


def test_per_item_costs_are_broken_out_and_sum_to_the_ledger_totals() -> None:
    ledger = _ledger()
    ledger.book_trade("ci_a", gross_pnl=Decimal("300.00"), commission=Decimal("11.00"))
    ledger.book_fee("ci_b", amount=Decimal("3.00"))
    ledger.book_funding("ci_a", amount=Decimal("1.25"))
    ledger.book_other_cost("ci_b", amount=Decimal("0.75"))

    report = attribute(ledger=ledger, t_ms=1_000, pin_ordinals=_ORDINALS)

    assert sum(row.fees for row in report.rows) == ledger.fees
    assert sum(row.funding for row in report.rows) == ledger.funding
    assert sum(row.other_costs for row in report.rows) == ledger.other_costs
    assert sum(row.realized_pnl for row in report.rows) == ledger.realized_pnl
    a = report.by_item("ci_a")
    assert a.total_costs == a.fees + a.funding + a.other_costs
    assert a.net_realized == a.realized_pnl - a.total_costs


def test_an_item_that_never_traded_still_gets_a_zero_row() -> None:
    """A share-holding item that did nothing must appear with zeros, not be missing —
    an absent row reads as "not in the portfolio", which is a different claim."""
    ledger = _ledger()
    ledger.book_trade("ci_a", gross_pnl=Decimal("100.00"))
    report = attribute(ledger=ledger, t_ms=1_000, pin_ordinals=_ORDINALS)
    idle = report.by_item("ci_b")
    assert idle.net_realized == Decimal("0")
    assert idle.unrealized == Decimal("0")
    assert idle.total_contribution == Decimal("0")
    assert idle.reason == NO_OPEN_POSITION


# --------------------------------------------------------------------------- #
# 2. a missing mark is disclosed, never imputed
# --------------------------------------------------------------------------- #
def test_an_unmarked_position_leaves_unrealised_unknown_rather_than_zero() -> None:
    """Modül 12 §9 forbids fallback. An unusable mark must not silently become 0."""
    ledger = _ledger()
    ledger.set_position("ci_a", direction="long", size=Decimal("2"), entry_price=Decimal("100.00"))
    ledger.set_position("ci_b", direction="long", size=Decimal("1"), entry_price=Decimal("80.00"))

    report = attribute(
        ledger=ledger, t_ms=1_000, marks={"ci_a": _fresh("110.00")}, pin_ordinals=_ORDINALS
    )

    assert report.unmarked_items == ("ci_b",)
    assert report.by_item("ci_b").unrealized is None
    assert report.by_item("ci_b").total_contribution is None
    assert report.by_item("ci_b").reason == UNMARKED_POSITION
    assert report.unrealized_total is None
    assert report.marked_equity is None
    assert report.marked_residual is None
    assert report.marked_reconciled is None
    # the REALISED identity still holds and is still reported
    assert report.realized_reconciled is True


def test_an_unusable_mark_authority_counts_as_unmarked() -> None:
    ledger = _ledger()
    ledger.set_position("ci_a", direction="long", size=Decimal("2"), entry_price=Decimal("100.00"))
    report = attribute(
        ledger=ledger,
        t_ms=1_000,
        marks={"ci_a": MarkPrice(Decimal("110.00"), "unavailable")},
        pin_ordinals=_ORDINALS,
    )
    assert report.unmarked_items == ("ci_a",)
    assert report.by_item("ci_a").unrealized is None


def test_a_stale_mark_is_usable_and_its_staleness_is_not_thresholded_here() -> None:
    """OD-2 is open: this module does not invent a staleness cutoff. A stale-but-usable
    mark values the position; the POLICY question is disclosed in the manifest."""
    ledger = _ledger()
    ledger.set_position("ci_a", direction="long", size=Decimal("2"), entry_price=Decimal("100.00"))
    report = attribute(
        ledger=ledger,
        t_ms=1_000,
        marks={"ci_a": MarkPrice(Decimal("110.00"), "stale_last_close", staleness_ms=86_400_000)},
        pin_ordinals=_ORDINALS,
    )
    assert report.unmarked_items == ()
    assert report.by_item("ci_a").unrealized == Decimal("20.00")


# --------------------------------------------------------------------------- #
# 3. determinism and refusals
# --------------------------------------------------------------------------- #
def test_rows_are_ordered_by_pin_ordinal_then_item_id() -> None:
    ledger = _ledger()
    report = attribute(ledger=ledger, t_ms=1_000, pin_ordinals={"ci_a": 5, "ci_b": 1})
    assert [row.item_id for row in report.rows] == ["ci_b", "ci_a"]
    assert [row.pin_ordinal for row in report.rows] == [1, 5]


def test_attribution_is_read_only_and_repeatable() -> None:
    ledger = _ledger()
    ledger.book_trade("ci_a", gross_pnl=Decimal("100.00"))
    first = attribute(ledger=ledger, t_ms=1_000, pin_ordinals=_ORDINALS)
    equity_after = ledger.equity
    second = attribute(ledger=ledger, t_ms=1_000, pin_ordinals=_ORDINALS)
    assert ledger.equity == equity_after
    assert first.as_dict() == second.as_dict()


def test_a_pin_ordinal_for_an_unknown_item_is_refused() -> None:
    with pytest.raises(UnknownAttributionItemError):
        attribute(ledger=_ledger(), t_ms=1_000, pin_ordinals={"ci_ghost": 0})


def test_by_item_refuses_an_unknown_item() -> None:
    report = attribute(ledger=_ledger(), t_ms=1_000, pin_ordinals=_ORDINALS)
    with pytest.raises(UnknownAttributionItemError):
        report.by_item("ci_ghost")


# --------------------------------------------------------------------------- #
# 4. the method is versioned and its omission disclosed
# --------------------------------------------------------------------------- #
def test_the_contribution_method_is_versioned_and_the_counterfactual_gap_is_disclosed() -> None:
    payload = attribute(ledger=_ledger(), t_ms=1_000, pin_ordinals=_ORDINALS).as_dict()
    assert payload["policy_version"] == ATTRIBUTION_POLICY_VERSION == "portfolio-attribution-v1"
    assert payload["method"] == CONTRIBUTION_METHOD == "additive_pnl_decomposition"
    assert payload["counterfactual_status"] == COUNTERFACTUAL_MARGINAL_STATUS
    assert "must not be read as one" in payload["counterfactual_note"]


def test_the_serialised_reconciliation_block_carries_the_proof() -> None:
    ledger = _ledger()
    ledger.book_trade("ci_a", gross_pnl=Decimal("100.00"), commission=Decimal("1.00"))
    block = attribute(ledger=ledger, t_ms=1_000, pin_ordinals=_ORDINALS).as_dict()["reconciliation"]
    # the string keeps the ledger's exponent ("0.00"); the VALUE is what must be zero
    assert Decimal(block["realized_residual"]) == 0
    assert block["realized_reconciled"] is True


# --------------------------------------------------------------------------- #
# 5. correlation — parity with the shipped sequential implementation
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    ("xs", "ys"),
    [
        ([1.0, 2.0, 3.0], [2.0, 4.0, 6.0]),
        ([1.0, 2.0, 3.0], [6.0, 4.0, 2.0]),
        ([1.0, 2.0, 3.0, 4.0], [1.0, 3.0, 2.0, 5.0]),
        ([1.0], [2.0]),
        ([1.0, 1.0, 1.0], [1.0, 2.0, 3.0]),
    ],
)
def test_pearson_is_numerically_identical_to_the_shipped_implementation(
    xs: list[float], ys: list[float]
) -> None:
    """Parity is PROVEN by calling the shipped ``portfolio._pearson``, not asserted in
    prose — the two eras must read alike."""
    assert pearson(xs, ys) == shipped_pearson(xs, ys)


def _snapshots() -> list:
    ledger = _ledger()
    snaps = []
    moves = [
        (Decimal("100"), Decimal("-50")),
        (Decimal("200"), Decimal("-100")),
        (Decimal("50"), Decimal("-25")),
    ]
    for step, (a, b) in enumerate(moves, start=1):
        ledger.book_trade("ci_a", gross_pnl=a)
        ledger.book_trade("ci_b", gross_pnl=b)
        snaps.append(attribute(ledger=ledger, t_ms=step * 1_000, pin_ordinals=_ORDINALS))
    return snaps


def test_the_contribution_series_is_per_tick_deltas_not_levels() -> None:
    series = contribution_series(_snapshots())
    assert series.item_ids == ("ci_a", "ci_b")
    assert series.instants == (1_000, 2_000, 3_000)
    assert series.values["ci_a"] == (Decimal("100"), Decimal("200"), Decimal("50"))
    assert series.values["ci_b"] == (Decimal("-50"), Decimal("-100"), Decimal("-25"))


def test_perfectly_anticorrelated_items_report_minus_one() -> None:
    block = contribution_correlation(contribution_series(_snapshots()))
    assert block["item_ids"] == ["ci_a", "ci_b"]
    assert block["aligned_point_count"] == 3
    assert block["matrix"][0][0] == "1.0000"
    assert block["matrix"][0][1] == "-1.0000"
    assert block["average_pairwise"] == "-1.0000"


def test_a_zero_variance_series_yields_null_not_a_fabricated_number() -> None:
    ledger = _ledger()
    snaps = [attribute(ledger=ledger, t_ms=t, pin_ordinals=_ORDINALS) for t in (1_000, 2_000)]
    block = contribution_correlation(contribution_series(snaps))
    assert block["matrix"][0][1] is None
    assert block["average_pairwise"] is None


def test_the_correlation_block_uses_the_shipped_key_names() -> None:
    block = contribution_correlation(contribution_series(_snapshots()))
    assert set(block) == {"item_ids", "aligned_point_count", "matrix", "average_pairwise"}


def test_a_contribution_report_carries_the_final_rows_and_the_correlation() -> None:
    snaps = _snapshots()
    payload = build_contribution_report(snaps).as_dict()
    assert payload["items"][0]["item_id"] == "ci_a"
    assert payload["correlation"]["average_pairwise"] == "-1.0000"
    assert payload["reconciliation"]["realized_reconciled"] is True
    assert payload["t_ms"] == 3_000


def test_an_empty_snapshot_sequence_is_refused() -> None:
    """An empty report would read as "no contribution" rather than "no ticks"."""
    with pytest.raises(AttributionError):
        build_contribution_report([])


# --------------------------------------------------------------------------- #
# 6. containment
# --------------------------------------------------------------------------- #
def _imports_attribution(source: str) -> bool:
    return (
        "execution.attribution" in source
        or "execution import attribution" in source
        or "from . import attribution" in source
    )


def test_nothing_in_production_imports_the_attribution_layer_yet() -> None:
    """Only the sibling provenance module (also contained) may import it."""
    src = Path(__file__).resolve().parents[2] / "src" / "entropia"
    importers = [
        path.relative_to(src).as_posix()
        for path in src.rglob("*.py")
        if path.name != "attribution.py" and _imports_attribution(path.read_text(encoding="utf-8"))
    ]
    assert importers == ["domain/backtest/execution/provenance.py"]
