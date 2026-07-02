"""Baseline capability registry seed + placeholder copy (doc 22 §4, §4.1, §7).

The seven V18 navigation slots are seeded as PLACEHOLDER registry rows with
fixed ids (``fcap_<key>``) so every environment addresses the same records —
mirroring the 7a baseline-guide seed. The static Graphic View card copy and the
per-state status messages are the doc-22 §4.1/§7 verbatim texts; a placeholder
never turns them into a fake operation result (CR-09).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from entropia.domain.capability.enums import (
    BACKTEST_REVIEW,
    GRAPHIC_VIEW,
    HYPOTHESIS_LAB,
    LIVE_TRADE,
    PARAMETER_FIELDS,
    REGIME_RESEARCH,
    SIGNAL_INTELLIGENCE,
    ActivationGate,
    CapabilityState,
)

UI_SURFACE_VERSION_V18 = "v18-placeholder"


def initial_dependency_snapshot() -> dict[str, Any]:
    """Placeholder minimum metadata (doc 22 §6.1): every gate key present,
    none complete."""
    return {"gates": {gate.value: False for gate in ActivationGate}}


@dataclass(frozen=True)
class CapabilitySeed:
    capability_key: str
    title: str
    menu_path: str
    summary: str
    dependency_snapshot: dict[str, Any] = field(default_factory=initial_dependency_snapshot)

    @property
    def capability_id(self) -> str:
        return f"fcap_{self.capability_key}"


BASELINE_CAPABILITIES: tuple[CapabilitySeed, ...] = (
    CapabilitySeed(
        capability_key=LIVE_TRADE,
        title="Live Trade",
        menu_path="Future Dev > Live Trade",
        summary=(
            "Future execution orchestration slot. Requires a separate execution "
            "plan, execution session, broker/venue adapter, order ledger and "
            "risk/freshness gate domain — never a live-money variant of the "
            "Backtest RUN button."
        ),
    ),
    CapabilitySeed(
        capability_key=GRAPHIC_VIEW,
        title="Graphic View",
        menu_path="Future Dev > Graphic View",
        summary=(
            "Central future surface for visual review. The active renderer only "
            "consumes the View Dataset contract built from pinned immutable "
            "Backtest Result / Market Data references."
        ),
    ),
    CapabilitySeed(
        capability_key=BACKTEST_REVIEW,
        title="Backtest Review",
        menu_path="Future Dev > AI Operations > Backtest Review",
        summary=(
            "Turns immutable Backtest Result diagnostics into evidence-linked "
            "review artifacts. Never recomputes or overwrites canonical metrics."
        ),
    ),
    CapabilitySeed(
        capability_key=SIGNAL_INTELLIGENCE,
        title="Signal Intelligence",
        menu_path="Future Dev > AI Operations > Signal Intelligence",
        summary=(
            "Classifies signal events at scale into versioned intelligence "
            "artifacts. Makes no entry/exit decision and never rewrites Strategy "
            "Details condition blocks."
        ),
    ),
    CapabilitySeed(
        capability_key=REGIME_RESEARCH,
        title="Regime Research",
        menu_path="Future Dev > Research > Regime Research",
        summary=(
            "Studies market context (trend/range, volatility, liquidity) into "
            "regime artifacts or versioned feature definitions. Strategy use only "
            "through published feature definitions with as-of policy."
        ),
    ),
    CapabilitySeed(
        capability_key=HYPOTHESIS_LAB,
        title="Hypothesis Lab",
        menu_path="Future Dev > Research > Hypothesis Lab",
        summary=(
            "Turns a human/Agent research idea into a repeatable "
            "hypothesis-to-experiment lifecycle with acceptance criteria."
        ),
    ),
    CapabilitySeed(
        capability_key=PARAMETER_FIELDS,
        title="Parameter Fields",
        menu_path="Future Dev > Research > Parameter Fields",
        summary=(
            "Defines controlled parameter search-spaces and sensitivity "
            "experiment plans. Outputs candidate configurations or experiment "
            "requests — never silently overwrites active Strategy parameters."
        ),
    ),
)

# Per-state status/recovery copy (doc 22 §5, §7 information catalog).
STATE_MESSAGES: dict[CapabilityState, str] = {
    CapabilityState.PLACEHOLDER: (
        "This capability is currently a controlled Future Dev placeholder. It does "
        "not generate operational data, background jobs, execution actions, or "
        "persistent production output. Activation requires a completed domain "
        "contract, data lineage, policy, API/worker, audit, rollback, and "
        "acceptance-test gate."
    ),
    CapabilityState.DESIGNED: (
        "The capability contract and dependencies are being defined. No operational "
        "command is available in this environment."
    ),
    CapabilityState.INTERNAL: "Internal validation only. Output is not authoritative.",
    CapabilityState.SHADOW: "Shadow output does not affect production decisions.",
    CapabilityState.LIMITED: (
        "This capability is active only for its approved limited scope. Eligibility, "
        "policy, history, and rollback information are shown before an operation "
        "can start."
    ),
    CapabilityState.ACTIVE: "This capability is active.",
    CapabilityState.RETIRED: ("This capability is retired. Historical records remain read-only."),
}

# Graphic View placeholder page copy (doc 22 §4.1 verbatim).
GRAPHIC_VIEW_INTRO = (
    "Graphic View is reserved for future chart and visual-review development. "
    "The page is intentionally a placeholder until the chart engine, event "
    "markers and structured visual datasets are implemented."
)

GRAPHIC_VIEW_CARDS: tuple[dict[str, str], ...] = (
    {
        "title": "Price Chart",
        "text": "Future: entry, exit, stop and scaling markers with S1 / S2 / S3 labels.",
    },
    {
        "title": "Equity Curve",
        "text": "Future: total portfolio and strategy-level equity curves.",
    },
    {
        "title": "Drawdown Chart",
        "text": "Future: time-based drawdown from equity peaks.",
    },
    {
        "title": "Exposure / Position Size",
        "text": "Future: open position size, layer count and leverage impact.",
    },
    {
        "title": "Trade Distribution",
        "text": (
            "Future: profit/loss distribution, average win, average loss and outlier behavior."
        ),
    },
    {
        "title": "Regime Overlay",
        "text": "Future: trend, range, high-volatility and low-volatility context labels.",
    },
)

__all__ = [
    "BASELINE_CAPABILITIES",
    "GRAPHIC_VIEW_CARDS",
    "GRAPHIC_VIEW_INTRO",
    "STATE_MESSAGES",
    "UI_SURFACE_VERSION_V18",
    "CapabilitySeed",
    "initial_dependency_snapshot",
]
