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


class RunEventType(StrEnum):
    """Durable run stage-event kinds (doc 15 §12 "Worker state change").

    These are the SPEC tokens verbatim (``RUN_STARTED``, ``RUN_STAGE_CHANGED``,
    ``RUN_SUCCEEDED``/``RUN_FAILED``/``RUN_CANCELLED``) and name the rows of the
    durable ``backtest_run_event`` stream a reconnecting client replays. The
    paired ``audit_events`` rows keep the shipped dotted ``backtest.*``
    ``event_kind`` convention (``backtest.run_succeeded`` already ships) — the
    two naming schemes are deliberate, not drift: one is the spec's event token,
    the other the audit plane's kind.
    """

    RUN_STARTED = "RUN_STARTED"
    RUN_STAGE_CHANGED = "RUN_STAGE_CHANGED"
    RUN_SUCCEEDED = "RUN_SUCCEEDED"
    RUN_FAILED = "RUN_FAILED"
    RUN_CANCELLED = "RUN_CANCELLED"


class MetricAvailability(StrEnum):
    """Why a canonical metric does — or does not — carry a value (doc 15 §5, §6).

    A missing metric is NEVER 0 — it is one of the non-computed states (L4). The
    null states are deliberately GRANULAR (I-01): ``NOT_AVAILABLE`` is the generic
    "no value was produced", while ``NO_DRAWDOWN`` / ``NO_LOSING_TRADE`` name the
    two divide-by-zero cases the spec forbids rendering as infinity — doc 17 §9.2
    ("Max drawdown=0 ise null + `no_drawdown`; infinity yasak" / "Gross loss=0 ise
    null + `no_losing_trade`") and doc 16 §9.3 (such a ROMAD sorts null-last, never
    a fake large value). Collapsing them back into ``NOT_AVAILABLE`` loses the very
    reason the value is absent, which is the whole point of the status.

    ``NOT_COMPUTED`` is NOT dead and means something else entirely: it is emitted by
    the Arrange Metrics result view (``queries/metric_profile.py::
    _metric_card_not_computed``) for a metric the caller's profile SELECTS but this
    immutable Result was never calculated with (doc 17 §6.1 "Not computed for this
    result"). ``derive_metric_values`` never emits it, because an engine summary has
    by construction run every canonical metric — the two producers are disjoint.
    """

    COMPUTED = "computed"
    NOT_COMPUTED = "not_computed"
    NOT_AVAILABLE = "not_available"
    NO_QUALIFYING_TRADES = "no_qualifying_trades"
    NO_DRAWDOWN = "no_drawdown"
    NO_LOSING_TRADE = "no_losing_trade"


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
    # F-11: a funding-enabled strategy's pinned Research revision could not be resolved
    # into a usable funding source (not Approved / wrong scope-category / hash mismatch /
    # unreadable native schema). Fail-closed — never a silent zero-cost run.
    FUNDING_SOURCE_INVALID = "RUN_FAILED_FUNDING_SOURCE_INVALID"


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
    "RunEventType",
    "RunFailureCode",
]
