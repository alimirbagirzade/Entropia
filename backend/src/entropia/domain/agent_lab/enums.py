"""Analysis Lab domain enums (Stage 6a, doc 18 §5, §9, §9.1).

Agent Workspace observation/control plane. All values are lowercase snake_case
``StrEnum`` stored via ``enum_column`` (VARCHAR + CHECK, CR-04). Task/run/job
enums are three SEPARATE registries and are never aliased into one another.
"""

from __future__ import annotations

from enum import StrEnum


class RuntimeStatus(StrEnum):
    """Alpha Agent runtime operational status (doc 18 §5, §9)."""

    ACTIVE = "active"
    PAUSED = "paused"
    STOPPING = "stopping"
    RECOVERING = "recovering"


class RuntimeMode(StrEnum):
    """Runtime mode — read-only policy state, never a user dropdown (doc 18 §3.1)."""

    CONTINUOUS = "continuous"


class RuntimeControl(StrEnum):
    """A pending, safe-checkpoint-deferred lifecycle control request (doc 18 §8.4)."""

    PAUSE = "pause"
    STOP = "stop"


class AgentTaskStatus(StrEnum):
    """Canonical AgentTask lifecycle (doc 18 §9.1). Distinct from BacktestRun /
    generic Job enums (CR-04)."""

    QUEUED = "queued"
    RUNNING = "running"
    WAITING = "waiting"
    CHECKPOINTING = "checkpointing"
    PAUSED = "paused"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentTaskPriority(StrEnum):
    """Task priority. ``autonomous`` is Coordinator-generated only and is NEVER
    human-selectable (doc 18 §9.1, §11)."""

    NORMAL = "normal"
    HIGH = "high"
    AUTONOMOUS = "autonomous"


class DirectiveStatus(StrEnum):
    """Human directive lifecycle. Created immutable; transitions are append-only
    events (doc 18 §9, §12)."""

    QUEUED = "queued"
    CONSUMED = "consumed"
    DEFERRED = "deferred"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class LabMessageType(StrEnum):
    """Conversation/event record type (doc 18 §3.2, §9)."""

    ASSISTANT = "assistant"
    MESSAGE = "message"
    DIRECTIVE = "directive"
    SYSTEM = "system"


class HypothesisStatus(StrEnum):
    """Persistent research artifact status (doc 18 §5, §9)."""

    EXPLORING = "exploring"
    TESTING = "testing"
    CANDIDATE = "candidate"
    REJECTED = "rejected"
    ARCHIVED = "archived"


# --- State-membership sets (coordinator + control guards) -------------------

TASK_ACTIVE_STATES: frozenset[AgentTaskStatus] = frozenset(
    {
        AgentTaskStatus.QUEUED,
        AgentTaskStatus.RUNNING,
        AgentTaskStatus.WAITING,
        AgentTaskStatus.CHECKPOINTING,
    }
)
TASK_TERMINAL_STATES: frozenset[AgentTaskStatus] = frozenset(
    {AgentTaskStatus.SUCCEEDED, AgentTaskStatus.FAILED, AgentTaskStatus.CANCELLED}
)
# A run is controllably stoppable only while it is doing live work.
TASK_STOPPABLE_STATES: frozenset[AgentTaskStatus] = frozenset(
    {AgentTaskStatus.RUNNING, AgentTaskStatus.WAITING, AgentTaskStatus.CHECKPOINTING}
)

# Human-selectable directive priorities (doc 18 §5, §11: autonomous rejected).
HUMAN_DIRECTIVE_PRIORITIES: frozenset[AgentTaskPriority] = frozenset(
    {AgentTaskPriority.NORMAL, AgentTaskPriority.HIGH}
)

# The canonical singleton Alpha Agent runtime id (doc 18 §5, §9).
ALPHA_AGENT_ID = "alpha-agent"


__all__ = [
    "ALPHA_AGENT_ID",
    "HUMAN_DIRECTIVE_PRIORITIES",
    "TASK_ACTIVE_STATES",
    "TASK_STOPPABLE_STATES",
    "TASK_TERMINAL_STATES",
    "AgentTaskPriority",
    "AgentTaskStatus",
    "DirectiveStatus",
    "HypothesisStatus",
    "LabMessageType",
    "RuntimeControl",
    "RuntimeMode",
    "RuntimeStatus",
]
