"""Per-item attribution and contribution over ONE shared ledger (ADIM 19).

CONTAINED — nothing in production imports this module.

``PortfolioLedger`` already books the REALISED half per item: every ``book_*`` call writes
the delta it actually applied into ``ItemAttribution``, so
``sum(net_contribution) == equity - pool_initial`` holds by construction
(``portfolio_ledger.py:541-608``). What is missing, and what this module adds, is the
UNREALISED half: ``PortfolioValuation`` reports one portfolio-level ``unrealized_pnl`` with
no per-item split, so a per-item breakdown cannot be reconciled against a marked total.

**The contribution method, and why it is this one.** With a shared clock and a shared
ledger, an item's counterfactual — "what would the portfolio have done without it" — is not
derivable from a single replay: removing an item changes every sibling's sleeve capacity,
solvency headroom and arbitration outcome from that tick onward. The sequential path can
fold a leave-one-out because its items never interacted (``portfolio._contribution_block``);
a unified run cannot. Canon defines no marginal formula for the shared clock, so none is
invented. The method here is the **additive P&L decomposition**: each item's contribution is
its own realised PnL net of its own costs plus its own unrealised mark-to-market. It is
exact (the parts sum to the whole with zero residual), order-free, and needs no
counterfactual. ``COUNTERFACTUAL_MARGINAL_STATUS`` records the omission out loud so nobody
reads the absence as an oversight.

**Marks are never imputed.** An open position with no usable mark makes that item's
``unrealized`` ``None`` and lands the item in ``unmarked_items``; ``marked_reconciled``
becomes ``False``. The realised identity still holds and is reported separately. Modül 12 §9
forbids fallback, so a missing mark is disclosed, not filled in.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from math import sqrt
from types import MappingProxyType
from typing import Any

from entropia.domain.backtest.execution.constants import _ZERO
from entropia.domain.backtest.execution.portfolio_ledger import (
    MarkPrice,
    PortfolioLedger,
    PortfolioValuation,
)

#: Bump when the emitted decomposition changes meaning.
ATTRIBUTION_POLICY_VERSION = "portfolio-attribution-v1"

#: The only decomposition derivable from one shared-clock replay. See the module docstring.
CONTRIBUTION_METHOD = "additive_pnl_decomposition"

#: ADR 0002 §9 — a leave-one-out over a shared ledger would require re-simulating the
#: portfolio without the item. Recorded, not silently omitted.
COUNTERFACTUAL_MARGINAL_STATUS = "not_derivable_without_re_simulation"
COUNTERFACTUAL_MARGINAL_NOTE = (
    "A leave-one-out marginal requires re-simulating the portfolio without the item: on a "
    "shared clock the removal changes every sibling's sleeve capacity, solvency headroom "
    "and arbitration outcome. This artifact reports the exact additive decomposition "
    "instead; it is not a counterfactual and must not be read as one."
)

#: Per-item reason tokens.
UNMARKED_POSITION = "unmarked_position_no_unrealized"
NO_OPEN_POSITION = "no_open_position"


class AttributionError(ValueError):
    """Base for every refusal in this module."""


class UnknownAttributionItemError(AttributionError):
    """An item was addressed that the ledger's plan does not carry."""


class AttributionResidualError(AttributionError):
    """The parts did not sum to the whole — a bug, never a rounding tolerance."""


@dataclass(frozen=True, slots=True)
class ItemContribution:
    """One item's row. ``unrealized`` is ``None`` exactly when the mark is unusable."""

    item_id: str
    pin_ordinal: int
    realized_pnl: Decimal
    fees: Decimal
    funding: Decimal
    other_costs: Decimal
    net_realized: Decimal
    unrealized: Decimal | None
    total_contribution: Decimal | None
    open_notional: Decimal
    reason: str | None = None

    @property
    def total_costs(self) -> Decimal:
        return self.fees + self.funding + self.other_costs

    def as_dict(self) -> dict[str, Any]:
        return {
            "item_id": self.item_id,
            "pin_ordinal": self.pin_ordinal,
            "realized_pnl": str(self.realized_pnl),
            "fees": str(self.fees),
            "funding": str(self.funding),
            "other_costs": str(self.other_costs),
            "total_costs": str(self.total_costs),
            "net_realized": str(self.net_realized),
            "unrealized": None if self.unrealized is None else str(self.unrealized),
            "total_contribution": (
                None if self.total_contribution is None else str(self.total_contribution)
            ),
            "open_notional": str(self.open_notional),
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class PortfolioAttribution:
    """The per-item breakdown plus the reconciliation proof against the portfolio total."""

    t_ms: int
    pool_initial: Decimal
    equity: Decimal
    realized_total: Decimal
    unrealized_total: Decimal | None
    marked_equity: Decimal | None
    rows: tuple[ItemContribution, ...]
    unmarked_items: tuple[str, ...]
    realized_residual: Decimal
    marked_residual: Decimal | None
    policy_version: str = ATTRIBUTION_POLICY_VERSION
    method: str = CONTRIBUTION_METHOD
    counterfactual_status: str = COUNTERFACTUAL_MARGINAL_STATUS

    @property
    def realized_reconciled(self) -> bool:
        """``sum(net_realized) == equity - pool_initial``, exactly."""
        return self.realized_residual == _ZERO

    @property
    def marked_reconciled(self) -> bool | None:
        """``sum(total_contribution) == marked_equity - pool_initial``, exactly.

        ``None`` when any open position is unmarked — an unknown, not a failure."""
        return None if self.marked_residual is None else self.marked_residual == _ZERO

    def by_item(self, item_id: str) -> ItemContribution:
        for row in self.rows:
            if row.item_id == item_id:
                return row
        raise UnknownAttributionItemError(f"No attribution row for item {item_id!r}.")

    def as_dict(self) -> dict[str, Any]:
        return {
            "t_ms": self.t_ms,
            "policy_version": self.policy_version,
            "method": self.method,
            "counterfactual_status": self.counterfactual_status,
            "counterfactual_note": COUNTERFACTUAL_MARGINAL_NOTE,
            "pool_initial": str(self.pool_initial),
            "equity": str(self.equity),
            "realized_total": str(self.realized_total),
            "unrealized_total": (
                None if self.unrealized_total is None else str(self.unrealized_total)
            ),
            "marked_equity": None if self.marked_equity is None else str(self.marked_equity),
            "items": [row.as_dict() for row in self.rows],
            "unmarked_items": list(self.unmarked_items),
            "reconciliation": {
                "realized_residual": str(self.realized_residual),
                "realized_reconciled": self.realized_reconciled,
                "marked_residual": (
                    None if self.marked_residual is None else str(self.marked_residual)
                ),
                "marked_reconciled": self.marked_reconciled,
            },
        }


def attribute(
    *,
    ledger: PortfolioLedger,
    t_ms: int,
    marks: Mapping[str, MarkPrice] | None = None,
    pin_ordinals: Mapping[str, int] | None = None,
) -> PortfolioAttribution:
    """Decompose the ledger into per-item rows and prove they sum to the portfolio.

    Pure and read-only: it calls ``ledger.valuation`` (which writes nothing) and reads
    ``ledger.attribution`` / ``ledger.positions``. Rows are ordered by
    ``(pin_ordinal, item_id)`` so the output does not depend on dict iteration order.

    :raises AttributionResidualError: if the realised parts do not sum to the realised
        whole. That identity is guaranteed by ``PortfolioLedger``'s booking, so a mismatch
        is a defect and is raised rather than reported as a tolerance.
    """
    offered = marks or {}
    ordinals = pin_ordinals or {}
    unknown = sorted(set(ordinals) - set(ledger.attribution))
    if unknown:
        raise UnknownAttributionItemError(f"Pin ordinals given for unknown items {unknown}.")
    valuation: PortfolioValuation = ledger.valuation(t_ms, marks=offered)

    rows: list[ItemContribution] = []
    unmarked: list[str] = []
    for item_id in sorted(ledger.attribution, key=lambda i: (ordinals.get(i, 0), i)):
        booked = ledger.attribution[item_id]
        position = ledger.positions.get(item_id)
        net_realized = booked.net_contribution
        if position is None:
            unrealized: Decimal | None = _ZERO
            reason: str | None = NO_OPEN_POSITION
            open_notional = _ZERO
        else:
            open_notional = position.notional
            mark = offered.get(item_id)
            if mark is None or not mark.is_usable:
                unrealized = None
                reason = UNMARKED_POSITION
                unmarked.append(item_id)
            else:
                unrealized = position.unrealized(mark.price)
                reason = None
        rows.append(
            ItemContribution(
                item_id=item_id,
                pin_ordinal=ordinals.get(item_id, 0),
                realized_pnl=booked.realized_pnl,
                fees=booked.fees,
                funding=booked.funding,
                other_costs=booked.other_costs,
                net_realized=net_realized,
                unrealized=unrealized,
                total_contribution=None if unrealized is None else net_realized + unrealized,
                open_notional=open_notional,
                reason=reason,
            )
        )

    realized_total = sum((row.net_realized for row in rows), _ZERO)
    realized_residual = realized_total - (ledger.equity - ledger.plan.pool_initial)
    if realized_residual != _ZERO:
        raise AttributionResidualError(
            f"Realised attribution does not sum to the ledger: residual {realized_residual}."
        )

    complete = not unmarked
    unrealized_total = valuation.unrealized_pnl if complete else None
    marked_equity = None if unrealized_total is None else ledger.equity + unrealized_total
    if marked_equity is None:
        marked_residual: Decimal | None = None
    else:
        total = sum(
            (row.total_contribution for row in rows if row.total_contribution is not None),
            _ZERO,
        )
        marked_residual = total - (marked_equity - ledger.plan.pool_initial)

    return PortfolioAttribution(
        t_ms=t_ms,
        pool_initial=ledger.plan.pool_initial,
        equity=ledger.equity,
        realized_total=realized_total,
        unrealized_total=unrealized_total,
        marked_equity=marked_equity,
        rows=tuple(rows),
        unmarked_items=tuple(unmarked),
        realized_residual=realized_residual,
        marked_residual=marked_residual,
    )


def pearson(xs: Sequence[float], ys: Sequence[float]) -> float | None:
    """Pearson r; ``None`` (never fabricated) below 2 points or on zero variance.

    Numerically identical to the shipped sequential ``portfolio._pearson``; a parity test
    calls that function directly rather than asserting the equivalence in prose."""
    n = len(xs)
    if n < 2:
        return None
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys, strict=True))
    var_x = sum((x - mean_x) ** 2 for x in xs)
    var_y = sum((y - mean_y) ** 2 for y in ys)
    if var_x <= 0.0 or var_y <= 0.0:
        return None
    return cov / sqrt(var_x * var_y)


@dataclass(frozen=True, slots=True)
class ContributionSeries:
    """Per-item contribution deltas keyed by tick, built from consecutive snapshots."""

    item_ids: tuple[str, ...]
    instants: tuple[int, ...]
    values: Mapping[str, tuple[Decimal, ...]]

    def __post_init__(self) -> None:
        object.__setattr__(self, "values", MappingProxyType(dict(self.values)))


def contribution_series(
    snapshots: Sequence[PortfolioAttribution],
) -> ContributionSeries:
    """Per-tick CHANGE in each item's net realised contribution.

    Deltas, not levels: a cumulative series is monotone-ish and its correlation would
    mostly measure a shared trend rather than co-movement. Realised (not marked) is used so
    a tick where an item has no usable mark still contributes a defined 0 rather than a
    hole. Snapshots must be in tick order; the first one seeds the baseline."""
    if not snapshots:
        return ContributionSeries(item_ids=(), instants=(), values={})
    item_ids = tuple(sorted({row.item_id for snap in snapshots for row in snap.rows}))
    previous: dict[str, Decimal] = dict.fromkeys(item_ids, _ZERO)
    columns: dict[str, list[Decimal]] = {item: [] for item in item_ids}
    instants: list[int] = []
    for snap in snapshots:
        instants.append(snap.t_ms)
        current = {row.item_id: row.net_realized for row in snap.rows}
        for item in item_ids:
            now = current.get(item, previous[item])
            columns[item].append(now - previous[item])
            previous[item] = now
    return ContributionSeries(
        item_ids=item_ids,
        instants=tuple(instants),
        values={item: tuple(values) for item, values in columns.items()},
    )


def contribution_correlation(series: ContributionSeries) -> dict[str, Any]:
    """Pairwise Pearson over the contribution deltas.

    Same key names, same 4-dp cell formatting and the same strict-upper-triangle average as
    the shipped sequential ``portfolio._correlation_block``, so the two eras read alike."""
    vectors = [[float(v) for v in series.values[item]] for item in series.item_ids]
    matrix: list[list[str | None]] = []
    pair_total = 0.0
    pair_count = 0
    for i, vi in enumerate(vectors):
        row: list[str | None] = []
        for j, vj in enumerate(vectors):
            r = pearson(vi, vj)
            row.append(None if r is None else f"{r:.4f}")
            if r is not None and i < j:
                pair_total += r
                pair_count += 1
        matrix.append(row)
    return {
        "item_ids": list(series.item_ids),
        "aligned_point_count": len(series.instants),
        "matrix": matrix,
        "average_pairwise": f"{pair_total / pair_count:.4f}" if pair_count else None,
    }


@dataclass(frozen=True, slots=True)
class ContributionReport:
    """The artifact a unified Result publishes: final rows + the correlation block."""

    attribution: PortfolioAttribution
    correlation: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        payload = self.attribution.as_dict()
        payload["correlation"] = dict(self.correlation)
        return payload


def build_contribution_report(
    snapshots: Sequence[PortfolioAttribution],
) -> ContributionReport:
    """Final attribution + correlation over the whole run.

    :raises AttributionError: on an empty snapshot sequence — an empty report would read as
        "no contribution", which is a different claim from "the run produced no ticks"."""
    if not snapshots:
        raise AttributionError("A contribution report needs at least one attribution snapshot.")
    return ContributionReport(
        attribution=snapshots[-1],
        correlation=contribution_correlation(contribution_series(snapshots)),
    )


__all__ = [
    "ATTRIBUTION_POLICY_VERSION",
    "CONTRIBUTION_METHOD",
    "COUNTERFACTUAL_MARGINAL_NOTE",
    "COUNTERFACTUAL_MARGINAL_STATUS",
    "NO_OPEN_POSITION",
    "UNMARKED_POSITION",
    "AttributionError",
    "AttributionResidualError",
    "ContributionReport",
    "ContributionSeries",
    "ItemContribution",
    "PortfolioAttribution",
    "UnknownAttributionItemError",
    "attribute",
    "build_contribution_report",
    "contribution_correlation",
    "contribution_series",
    "pearson",
]
