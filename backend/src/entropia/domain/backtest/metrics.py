"""Canonical result metric registry + MetricValue derivation (Stage 5a, doc 15 §5,§6).

Presentation labels + units + null behaviour live in this server-side read model,
NOT in the frontend (doc 15 §15 "no frontend formula"). A metric absent from the
engine output is surfaced with the status that NAMES WHY it is absent — never 0
(L4, doc 15 §5): ``NO_DRAWDOWN`` / ``NO_LOSING_TRADE`` for the two forbidden
divide-by-zero cases (doc 17 §9.2), ``NO_QUALIFYING_TRADES`` only for metrics whose
denominator actually needs trade roots, ``NOT_AVAILABLE`` otherwise. This is
distinct from the user Result View Metric Profile (Arrange Metrics, doc 17), which
is a later slice and only a display preference.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from entropia.domain.backtest.enums import MetricAvailability

FORMULA_VERSION = "v1"


@dataclass(frozen=True, slots=True)
class MetricDefinition:
    """One canonical, selectable metric definition (doc 15 §5 field contract).

    ``trade_dependent`` records whether the metric's denominator actually needs
    closed trade roots (doc 17 §9.2). Only such a metric may be labelled
    ``NO_QUALIFYING_TRADES`` when a run closed no trades — an equity-curve metric
    (Net Profit / Max Drawdown / ROMAD) is computed from the curve regardless of
    trade count, so blaming its absence on "no qualifying trades" would be a false
    reason (I-01).
    """

    key: str
    label: str
    unit: str
    value_format: str
    summary_key: str
    trade_dependent: bool = False


# The nine V18 default Summary Metrics, in their canonical display order (doc 15 §3.2).
DEFAULT_METRICS: tuple[MetricDefinition, ...] = (
    MetricDefinition("net_profit", "Net Profit", "percent", "signed_percent", "net_profit_pct"),
    MetricDefinition(
        "max_drawdown", "Max Drawdown", "percent", "signed_percent", "max_drawdown_pct"
    ),
    MetricDefinition("romad", "ROMAD", "ratio", "decimal2", "romad"),
    MetricDefinition(
        "win_rate", "Win Rate", "percent", "percent", "win_rate", trade_dependent=True
    ),
    MetricDefinition(
        "profit_factor", "Profit Factor", "ratio", "decimal2", "profit_factor", trade_dependent=True
    ),
    MetricDefinition(
        "total_trades", "Total Trades", "count", "integer", "total_trades", trade_dependent=True
    ),
    MetricDefinition(
        "total_stops", "Total Stops", "count", "integer", "total_stops", trade_dependent=True
    ),
    MetricDefinition(
        "max_stop_streak",
        "Max Stop Streak",
        "count",
        "integer",
        "max_stop_streak",
        trade_dependent=True,
    ),
    MetricDefinition(
        "total_winning_trades",
        "Total Winning Trades",
        "count",
        "integer",
        "total_winning_trades",
        trade_dependent=True,
    ),
)


@dataclass(frozen=True, slots=True)
class MetricValue:
    """A materialized metric reading for a result (doc 15 §9.1 ResultSummary/MetricValue)."""

    key: str
    label: str
    unit: str
    value_format: str
    value: Decimal | None
    availability: MetricAvailability
    formula_version: str
    position_index: int


_ZERO = Decimal("0")


def _is_zero(raw: Any) -> bool:
    """True only for a PRESENT, numerically zero summary value (``None`` is not 0)."""
    if raw is None:
        return False
    value = raw if isinstance(raw, Decimal) else Decimal(str(raw))
    return value == _ZERO


def _null_availability(
    definition: MetricDefinition, summary: dict[str, Any], total_trades: int
) -> MetricAvailability:
    """Name WHY a canonical metric carries no value (doc 15 §5, doc 17 §9.2).

    Order matters. A key the engine never emitted at all carries no reason beyond
    "absent", so it stays ``NOT_AVAILABLE`` — only a key that IS present with a null
    value was deliberately nulled by a fold, and only then can the cause be named.
    """
    if definition.summary_key not in summary:
        return MetricAvailability.NOT_AVAILABLE
    if definition.key == "romad" and _is_zero(summary.get("max_drawdown_pct")):
        # doc 17 §9.2: "Max drawdown=0 ise null + no_drawdown; infinity yasak."
        return MetricAvailability.NO_DRAWDOWN
    if definition.key == "profit_factor" and total_trades > 0:
        # Both folds (``engine.py`` and ``execution/portfolio.py::_fold_composite_metrics``)
        # null profit_factor on exactly ONE condition — ``gross_loss == 0`` — so with
        # trade roots present the cause is "no losing trade", never a missing
        # computation (doc 17 §9.2: "Gross loss=0 ise null + no_losing_trade").
        return MetricAvailability.NO_LOSING_TRADE
    if definition.trade_dependent and total_trades == 0:
        return MetricAvailability.NO_QUALIFYING_TRADES
    return MetricAvailability.NOT_AVAILABLE


def derive_metric_values(summary: dict[str, Any]) -> list[MetricValue]:
    """Map an engine summary to canonical MetricValue rows (missing => not 0, L4)."""
    total_trades = int(summary.get("total_trades") or 0)
    out: list[MetricValue] = []
    for position, definition in enumerate(DEFAULT_METRICS):
        raw = summary.get(definition.summary_key)
        if raw is None:
            availability = _null_availability(definition, summary, total_trades)
            out.append(
                MetricValue(
                    key=definition.key,
                    label=definition.label,
                    unit=definition.unit,
                    value_format=definition.value_format,
                    value=None,
                    availability=availability,
                    formula_version=FORMULA_VERSION,
                    position_index=position,
                )
            )
            continue
        value = raw if isinstance(raw, Decimal) else Decimal(str(raw))
        out.append(
            MetricValue(
                key=definition.key,
                label=definition.label,
                unit=definition.unit,
                value_format=definition.value_format,
                value=value,
                availability=MetricAvailability.COMPUTED,
                formula_version=FORMULA_VERSION,
                position_index=position,
            )
        )
    return out


__all__ = [
    "DEFAULT_METRICS",
    "FORMULA_VERSION",
    "MetricDefinition",
    "MetricValue",
    "derive_metric_values",
]
