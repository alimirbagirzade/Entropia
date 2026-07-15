"""Backtest execution-plane enums (Stage 5a, doc 15 §9.1, §9.3).

Lowercase snake_case ``StrEnum`` values stored as canonical strings. The
``BacktestRunState`` is deliberately distinct from the generic ``JobStatus`` and
from ``ReadinessState`` — never aliased (CR-04, doc 15 §17).
"""

from __future__ import annotations

from enum import StrEnum


class BacktestRunState(StrEnum):
    """Canonical BacktestRun lifecycle (doc 15 §9.3).

    Only a ``succeeded`` run materializes an immutable Backtest Result; ``failed``
    / ``cancelled`` keep diagnostics only and produce no Result or history row
    (doc 15 §1, §8.4, CR-03).
    """

    QUEUED = "queued"
    PROVISIONING = "provisioning"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class MetricAvailability(StrEnum):
    """Whether a canonical metric was computed for a result (doc 15 §5, §6).

    A missing metric is NEVER 0 — it is one of the non-computed states (L4).
    """

    COMPUTED = "computed"
    NOT_COMPUTED = "not_computed"
    NOT_AVAILABLE = "not_available"
    NO_QUALIFYING_TRADES = "no_qualifying_trades"


class RunFailureCode(StrEnum):
    """Structured terminal failure causes (doc 15 §11).

    No 'latest' fallback is ever attempted — an unresolved pinned dependency is a
    hard terminal failure, never silently substituted (doc 15 §15).
    """

    MANIFEST_RESOLUTION = "RUN_FAILED_MANIFEST_RESOLUTION"
    ASSET_UNAVAILABLE = "RUN_FAILED_ASSET_UNAVAILABLE"
    UNRESOLVED_DEPENDENCY = "RUN_FAILED_UNRESOLVED_DEPENDENCY"
    ENGINE_ERROR = "RUN_FAILED_ENGINE_ERROR"
    INVALID_BACKTEST_RANGE = "RUN_FAILED_INVALID_BACKTEST_RANGE"
    INSTRUMENT_MISMATCH = "RUN_FAILED_INSTRUMENT_MISMATCH"
    EMPTY_FILTERED_RANGE = "RUN_FAILED_EMPTY_FILTERED_RANGE"


RUN_ACTIVE_STATES: frozenset[BacktestRunState] = frozenset(
    {BacktestRunState.QUEUED, BacktestRunState.PROVISIONING, BacktestRunState.RUNNING}
)
RUN_TERMINAL_STATES: frozenset[BacktestRunState] = frozenset(
    {BacktestRunState.SUCCEEDED, BacktestRunState.FAILED, BacktestRunState.CANCELLED}
)
RUN_RETRYABLE_STATES: frozenset[BacktestRunState] = frozenset(
    {BacktestRunState.FAILED, BacktestRunState.CANCELLED}
)


__all__ = [
    "RUN_ACTIVE_STATES",
    "RUN_RETRYABLE_STATES",
    "RUN_TERMINAL_STATES",
    "BacktestRunState",
    "MetricAvailability",
    "RunFailureCode",
]
