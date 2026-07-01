"""Canonical MetricDefinition registry seed (Stage 5c, doc 17 §3.1, §3.2, §6, §9.2).

The single authority for the ``metric_definition`` table: migration 0015 seeds the
DB from ``METRIC_REGISTRY``; the Arrange Metrics query/command layer then reads the
DB (never this module at request time) so the registry is a real, versioned table
(doc 17 §13). The nine ``SELECTABLE`` codes mirror the Stage 5a
``domain/backtest/metrics.DEFAULT_METRICS`` (same code/label/unit/format) so the
Arrange Metrics view stays consistent with the immutable ``metric_value`` the
engine already wrote — Arrange Metrics NEVER recomputes or mutates those (CR-07).
The eighteen ``FUTURE`` codes are reference-only (doc 17 §3.2): not selectable, no
fake value, no backfilled MetricValue.
"""

from __future__ import annotations

from dataclasses import dataclass

from entropia.domain.metric_profile.enums import MetricAvailabilityStatus

# Registry version stamped onto every profile revision (doc 17 §5.1
# metric_definition_registry_version, §9.3 registry drift). Bump when the offered
# metric set or a formula contract changes so historical revisions stay traceable.
REGISTRY_VERSION = "v1"
FORMULA_VERSION = "v1"


@dataclass(frozen=True, slots=True)
class MetricDefinitionSeed:
    """One canonical registry row (doc 17 §9.2 metric contract)."""

    metric_code: str
    label: str
    unit: str
    value_format: str
    availability_status: MetricAvailabilityStatus
    display_order: int
    formula_version: str | None
    description: str


# The nine V18 SELECTABLE metrics in canonical display order (doc 17 §3.1, §6);
# codes/labels/units mirror Stage 5a DEFAULT_METRICS exactly.
_SELECTABLE: tuple[tuple[str, str, str, str, str], ...] = (
    (
        "net_profit",
        "Net Profit",
        "percent",
        "signed_percent",
        "Final equity minus initial equity after realized PnL, fees, commissions, "
        "funding, spread and slippage included by the run manifest.",
    ),
    (
        "max_drawdown",
        "Max Drawdown",
        "percent",
        "signed_percent",
        "Largest peak-to-trough decline on the equity curve; stored as an absolute "
        "decimal (the UI may show a minus sign).",
    ),
    (
        "romad",
        "ROMAD",
        "ratio",
        "decimal2",
        "Return over maximum drawdown. When max drawdown is zero it is reported as "
        "Not available with a no_drawdown status, never infinity.",
    ),
    (
        "win_rate",
        "Win Rate",
        "percent",
        "percent",
        "Winning closed trade roots divided by winning plus losing closed trade "
        "roots. Breakeven trades are excluded from the default denominator.",
    ),
    (
        "profit_factor",
        "Profit Factor",
        "ratio",
        "decimal2",
        "Gross profit divided by absolute gross loss. With no losing trades it is "
        "reported as Not available with a no_losing_trade status, never infinity.",
    ),
    (
        "total_trades",
        "Total Trades",
        "count",
        "integer",
        "Fully closed trade roots. Scaling legs, partial exits and multiple fills do "
        "not create extra trade roots.",
    ),
    (
        "total_stops",
        "Total Stops",
        "count",
        "integer",
        "Completed trade roots whose terminal close reason category is STOP_LOSS. A "
        "partial stop leg alone does not increase this root-level metric.",
    ),
    (
        "max_stop_streak",
        "Max Stop Streak",
        "count",
        "integer",
        "Longest consecutive sequence of fully closed trade roots whose terminal "
        "close reason category is STOP_LOSS; a normal-exit loss ends the streak.",
    ),
    (
        "total_winning_trades",
        "Total Winning Trades",
        "count",
        "integer",
        "Fully closed trade roots with net PnL greater than zero after fees, funding "
        "and all run-manifest costs.",
    ),
)

# The eighteen Future Version Metrics (doc 17 §3.2) — reference-only, not selectable.
_FUTURE: tuple[tuple[str, str], ...] = (
    ("sharpe_ratio", "Sharpe Ratio"),
    ("sortino_ratio", "Sortino Ratio"),
    ("recovery_factor", "Recovery Factor"),
    ("robustness_test", "Robustness Test"),
    ("monte_carlo_result", "Monte Carlo Result"),
    ("walk_forward_result", "Walk-Forward Result"),
    ("out_of_sample_result", "Out of Sample Result"),
    ("average_trade", "Average Trade"),
    ("average_holding_time", "Average Holding Time"),
    ("consecutive_losses", "Consecutive Losses"),
    ("exposure", "Exposure"),
    ("long_short_distribution", "Long / Short Distribution"),
    ("monthly_return", "Monthly Return"),
    ("timeframe_sensitivity", "Timeframe Sensitivity"),
    ("regime_sensitivity", "Regime Sensitivity"),
    ("parameter_stability", "Parameter Stability"),
    ("slippage_sensitivity", "Slippage Sensitivity"),
    ("commission_sensitivity", "Commission Sensitivity"),
)


def _build_registry() -> tuple[MetricDefinitionSeed, ...]:
    rows: list[MetricDefinitionSeed] = []
    for order, (code, label, unit, value_format, description) in enumerate(_SELECTABLE):
        rows.append(
            MetricDefinitionSeed(
                metric_code=code,
                label=label,
                unit=unit,
                value_format=value_format,
                availability_status=MetricAvailabilityStatus.SELECTABLE,
                display_order=order,
                formula_version=FORMULA_VERSION,
                description=description,
            )
        )
    base = len(_SELECTABLE)
    for offset, (code, label) in enumerate(_FUTURE):
        rows.append(
            MetricDefinitionSeed(
                metric_code=code,
                label=label,
                unit="reference",
                value_format="reference",
                availability_status=MetricAvailabilityStatus.FUTURE,
                display_order=base + offset,
                formula_version=None,
                description=(
                    f"{label} is a future reference metric. It is not selectable and "
                    "produces no value until its capability and calculation contract "
                    "are activated."
                ),
            )
        )
    return tuple(rows)


METRIC_REGISTRY: tuple[MetricDefinitionSeed, ...] = _build_registry()

# The nine SELECTABLE codes in display order — the System Default profile selection
# when a caller has no personal profile yet (doc 17 §4 "First open / profile absent").
DEFAULT_SELECTED_METRIC_CODES: tuple[str, ...] = tuple(
    row.metric_code
    for row in METRIC_REGISTRY
    if row.availability_status is MetricAvailabilityStatus.SELECTABLE
)


__all__ = [
    "DEFAULT_SELECTED_METRIC_CODES",
    "FORMULA_VERSION",
    "METRIC_REGISTRY",
    "REGISTRY_VERSION",
    "MetricDefinitionSeed",
]
