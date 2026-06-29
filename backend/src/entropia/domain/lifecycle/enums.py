"""Central Lifecycle Enum Registry (CR-04).

All lifecycle/state values are **lowercase snake_case** and are returned over
REST/SSE verbatim. The domain `lifecycle_state`, `validation_status`, and
`deletion_state` are three SEPARATE concerns that never collapse into one
column. Per-entity lifecycle enums (strategy, package, dataset, run, ...) are
added by their owning stage; Stage 1 defines the cross-cutting ones every entity
and worker share.
"""

from __future__ import annotations

from enum import StrEnum


class PrincipalType(StrEnum):
    ANONYMOUS = "anonymous"
    HUMAN = "human"
    AGENT = "agent"
    SYSTEM = "system"


class Role(StrEnum):
    """Fixed, title-based human roles. No per-action grants."""

    ADMIN = "admin"
    SUPERVISOR = "supervisor"
    USER = "user"


class ActorKind(StrEnum):
    """Who performed an audited action."""

    HUMAN = "human"
    AGENT = "agent"
    SYSTEM_SERVICE = "system_service"


class DeletionState(StrEnum):
    """Deletion overlay — orthogonal to every entity's domain lifecycle.

    Forbidden jumps: active -> purged, purge_pending -> active (restore),
    purged -> active. Enforced by the deletion state machine.
    """

    ACTIVE = "active"
    SOFT_DELETED = "soft_deleted"
    PURGE_PENDING = "purge_pending"
    PURGED = "purged"


class JobStatus(StrEnum):
    """Durable generic job lifecycle (Module 20 §6). Distinct from BacktestRun
    and AgentTask enums — never aliased (CR-04)."""

    QUEUED = "queued"
    CLAIMED = "claimed"
    RUNNING = "running"
    CANCELLATION_REQUESTED = "cancellation_requested"
    CANCELLED = "cancelled"
    FAILED_RETRYABLE = "failed_retryable"
    FAILED_FINAL = "failed_final"
    SUCCEEDED = "succeeded"
    SUPERSEDED = "superseded"


class ValidationStatus(StrEnum):
    PASS = "pass"
    WARNING = "warning"
    BLOCKING_FAIL = "blocking_fail"


# Job states from which a worker may still transition (not terminal).
JOB_TERMINAL_STATES: frozenset[JobStatus] = frozenset(
    {JobStatus.SUCCEEDED, JobStatus.CANCELLED, JobStatus.FAILED_FINAL, JobStatus.SUPERSEDED}
)
