"""Analysis Lab state machines (Stage 6a, doc 18 §8, §9.1, §11).

Pure transition guards over the runtime / task / directive enums. The Coordinator
scaffold and the Admin lifecycle commands consult these; they never mutate a
worker process directly (doc 18 §14).
"""

from __future__ import annotations

from entropia.domain.agent_lab.enums import (
    HUMAN_DIRECTIVE_PRIORITIES,
    AgentTaskPriority,
    AgentTaskStatus,
    DirectiveStatus,
    RuntimeControl,
    RuntimeStatus,
)
from entropia.shared.errors import InvalidDirectivePriorityError

# --- Runtime lifecycle -------------------------------------------------------

# Pause/Stop are requested only from a live runtime; Resume only from paused.
_RUNTIME_PAUSE_ELIGIBLE: frozenset[RuntimeStatus] = frozenset({RuntimeStatus.ACTIVE})
_RUNTIME_RESUME_ELIGIBLE: frozenset[RuntimeStatus] = frozenset({RuntimeStatus.PAUSED})


def runtime_can_pause(status: RuntimeStatus, pending_control: RuntimeControl | None) -> bool:
    """A pause request is eligible only from ACTIVE with no control already pending."""
    return status in _RUNTIME_PAUSE_ELIGIBLE and pending_control is None


def runtime_can_resume(status: RuntimeStatus) -> bool:
    return status in _RUNTIME_RESUME_ELIGIBLE


def runtime_can_request_stop(status: RuntimeStatus, pending_control: RuntimeControl | None) -> bool:
    """Stop is a controlled cancellation of the current sub-run; not while a
    control is already pending, and not from a terminal/paused runtime with no run."""
    return status in {RuntimeStatus.ACTIVE, RuntimeStatus.RECOVERING} and pending_control is None


# --- Task lifecycle ----------------------------------------------------------

_TASK_TRANSITIONS: dict[AgentTaskStatus, frozenset[AgentTaskStatus]] = {
    AgentTaskStatus.QUEUED: frozenset(
        {AgentTaskStatus.RUNNING, AgentTaskStatus.WAITING, AgentTaskStatus.CANCELLED}
    ),
    AgentTaskStatus.RUNNING: frozenset(
        {
            AgentTaskStatus.WAITING,
            AgentTaskStatus.CHECKPOINTING,
            AgentTaskStatus.PAUSED,
            AgentTaskStatus.SUCCEEDED,
            AgentTaskStatus.FAILED,
            AgentTaskStatus.CANCELLED,
        }
    ),
    AgentTaskStatus.WAITING: frozenset(
        {
            AgentTaskStatus.RUNNING,
            AgentTaskStatus.CHECKPOINTING,
            AgentTaskStatus.CANCELLED,
            AgentTaskStatus.FAILED,
        }
    ),
    AgentTaskStatus.CHECKPOINTING: frozenset(
        {
            AgentTaskStatus.RUNNING,
            AgentTaskStatus.PAUSED,
            AgentTaskStatus.SUCCEEDED,
            AgentTaskStatus.FAILED,
            AgentTaskStatus.CANCELLED,
        }
    ),
    AgentTaskStatus.PAUSED: frozenset({AgentTaskStatus.RUNNING, AgentTaskStatus.CANCELLED}),
    AgentTaskStatus.SUCCEEDED: frozenset(),
    AgentTaskStatus.FAILED: frozenset(),
    AgentTaskStatus.CANCELLED: frozenset(),
}


def task_transition_allowed(frm: AgentTaskStatus, to: AgentTaskStatus) -> bool:
    return to in _TASK_TRANSITIONS.get(frm, frozenset())


# --- Directive lifecycle -----------------------------------------------------

_DIRECTIVE_TRANSITIONS: dict[DirectiveStatus, frozenset[DirectiveStatus]] = {
    DirectiveStatus.QUEUED: frozenset(
        {DirectiveStatus.CONSUMED, DirectiveStatus.DEFERRED, DirectiveStatus.CANCELLED}
    ),
    DirectiveStatus.DEFERRED: frozenset(
        {DirectiveStatus.QUEUED, DirectiveStatus.CONSUMED, DirectiveStatus.CANCELLED}
    ),
    DirectiveStatus.CONSUMED: frozenset({DirectiveStatus.COMPLETED}),
    DirectiveStatus.COMPLETED: frozenset(),
    DirectiveStatus.CANCELLED: frozenset(),
}


def directive_transition_allowed(frm: DirectiveStatus, to: DirectiveStatus) -> bool:
    return to in _DIRECTIVE_TRANSITIONS.get(frm, frozenset())


def parse_human_directive_priority(raw: str) -> AgentTaskPriority:
    """Map a client priority string to a human-selectable priority.

    ``autonomous`` (Coordinator-only) or any unknown value raises
    ``InvalidDirectivePriorityError`` (422, doc 18 §11 AL-07).
    """
    try:
        candidate = AgentTaskPriority(raw)
    except ValueError as exc:
        raise InvalidDirectivePriorityError() from exc
    if candidate not in HUMAN_DIRECTIVE_PRIORITIES:
        raise InvalidDirectivePriorityError()
    return candidate


__all__ = [
    "directive_transition_allowed",
    "parse_human_directive_priority",
    "runtime_can_pause",
    "runtime_can_request_stop",
    "runtime_can_resume",
    "task_transition_allowed",
]
