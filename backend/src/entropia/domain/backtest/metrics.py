"""Canonical result metric registry + MetricValue derivation (Stage 5a, doc 15 §5,§6).

Presentation labels + units + null behaviour live in this server-side read model,
NOT in the frontend (doc 15 §15 "no frontend formula"). A metric absent from the
engine output is surfaced as NOT_AVAILABLE / NO_QUALIFYING_TRADES — never 0 (L4,
doc 15 §5). This is distinct from the user Result View Metric Profile (Arrange
Metrics, doc 17), which is a later slice and only a display preference.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from entropia.domain.backtest.enums import MetricAvailability

FORMULA_VERSION = "v1"


@dataclass(frozen=True, slots=True)
class MetricDefinition:
    """One canonical, selectable metric definition (doc 15 §5 field contract)."""

    key: str
    label: str
    unit: str
    value_format: str
    summary_key: str


# The nine V18 default Summary Metrics, in their canonical display order (doc 15 §3.2).
DEFAULT_METRICS: tuple[MetricDefinition, ...] = (
    MetricDefinition("net_profit", "Net Profit", "percent", "signed_percent", "net_profit_pct"),
    MetricDefinition(
        "max_drawdown", "Max Drawdown", "percent", "signed_percent", "max_drawdown_pct"
    ),
    MetricDefinition("romad", "ROMAD", "ratio", "decimal2", "romad"),
    MetricDefinition("win_rate", "Win Rate", "percent", "percent", "win_rate"),
    MetricDefinition("profit_factor", "Profit Factor", "ratio", "decimal2", "profit_factor"),
    MetricDefinition("total_trades", "Total Trades", "count", "integer", "total_trades"),
    MetricDefinition("total_stops", "Total Stops", "count", "integer", "total_stops"),
    MetricDefinition("max_stop_streak", "Max Stop Streak", "count", "integer", "max_stop_streak"),
    MetricDefinition(
        "total_winning_trades", "Total Winning Trades", "count", "integer", "total_winning_trades"
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


def derive_metric_values(summary: dict[str, Any]) -> list[MetricValue]:
    """Map an engine summary to canonical MetricValue rows (missing => not 0, L4)."""
    total_trades = summary.get("total_trades") or 0
    out: list[MetricValue] = []
    for position, definition in enumerate(DEFAULT_METRICS):
        raw = summary.get(definition.summary_key)
        if raw is None:
            availability = (
                MetricAvailability.NO_QUALIFYING_TRADES
                if total_trades == 0
                else MetricAvailability.NOT_AVAILABLE
            )
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
