"""Tool Gateway policy surface (Stage 6a-2, doc 18 §9.2, §10, §14).

The Alpha Agent does its real domain work UI-lessly through the Tool Gateway —
the same policy-checked application-service line a human uses (doc 18 §10). Every
tool call is durably recorded with a fixed context envelope (actor_context,
task_id, checkpoint_id, input_manifest_id, idempotency_key, policy_scope,
artifact_output_ref; doc 18 §9.2). These are the pure enums + scope guards; the
durable record + dispatch live in ``application/jobs/agent_tools``.
"""

from __future__ import annotations

from enum import StrEnum

from entropia.shared.errors import ToolPolicyScopeError


class ToolName(StrEnum):
    """The UI-less agent tool set with human parity (doc 18 §10). Approve /
    publish / dataset-approval / Trash / role tools are deliberately absent — the
    Agent never gains those privileges (doc 18 §14, AL-12, AL-16)."""

    TASK_QUERY = "agent.task.query"
    DATA_BUNDLE_RESOLVE = "data_bundle.resolve"
    PACKAGE_PROPOSAL_CREATE = "package.proposal.create"
    BACKTEST_READY_CHECK = "backtest.ready_check"
    BACKTEST_REQUEST = "backtest.request"
    RESULT_QUERY = "result.query"
    ARTIFACT_CREATE = "artifact.create"
    ARTIFACT_SOFT_DELETE = "artifact.soft_delete"
    FOLLOWUP_TASK_ENQUEUE = "followup_task.enqueue"
    # Stage 7a — User Manual retrieval parity (doc 21 §12): Published-corpus
    # read/search + citation provenance only; manual MUTATION tools do not exist.
    DOCUMENTATION_SEARCH = "documentation.search"
    DOCUMENTATION_GET_SECTION = "documentation.get_section"
    ARTIFACT_ATTACH_CITATION = "artifact.attach_citation"
    # Stage 7b — Future Dev capability tools (doc 22 §11, CR-08): these exist in
    # the enum but are OFFERED to the Agent only while their gating capability is
    # Limited/Active (``exposed_tool_names``); a call while inactive is a recorded
    # REJECTED denial (CAPABILITY_NOT_ACTIVE), never a job or output.
    VIEW_DATASET_QUERY = "view_dataset.query"
    ANALYSIS_ARTIFACT_CREATE = "analysis_artifact.create"


class ToolCallStatus(StrEnum):
    """Durable tool-call lifecycle. REJECTED is a *recorded governance denial*
    (doc 18 §11 AL-11) — never an unrecorded crash."""

    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    REJECTED = "rejected"


class PolicyScope(StrEnum):
    """The intent scope a tool call runs under. EXECUTION is the strict gate:
    ``agent_research_only`` data may never enter it (doc 18 §9.1, §14, AL-11)."""

    OBSERVATION = "observation"
    RESEARCH = "research"
    PROPOSAL = "proposal"
    EXECUTION = "execution"


# Which policy scopes each tool may legally run under (doc 18 §9.2, §10).
TOOL_ALLOWED_SCOPES: dict[ToolName, frozenset[PolicyScope]] = {
    ToolName.TASK_QUERY: frozenset({PolicyScope.OBSERVATION}),
    ToolName.RESULT_QUERY: frozenset({PolicyScope.OBSERVATION}),
    ToolName.DATA_BUNDLE_RESOLVE: frozenset({PolicyScope.RESEARCH, PolicyScope.EXECUTION}),
    ToolName.PACKAGE_PROPOSAL_CREATE: frozenset({PolicyScope.PROPOSAL}),
    ToolName.BACKTEST_READY_CHECK: frozenset({PolicyScope.EXECUTION}),
    ToolName.BACKTEST_REQUEST: frozenset({PolicyScope.EXECUTION}),
    ToolName.ARTIFACT_CREATE: frozenset({PolicyScope.RESEARCH, PolicyScope.PROPOSAL}),
    ToolName.ARTIFACT_SOFT_DELETE: frozenset({PolicyScope.RESEARCH}),
    ToolName.FOLLOWUP_TASK_ENQUEUE: frozenset({PolicyScope.RESEARCH}),
    ToolName.DOCUMENTATION_SEARCH: frozenset({PolicyScope.OBSERVATION, PolicyScope.RESEARCH}),
    ToolName.DOCUMENTATION_GET_SECTION: frozenset({PolicyScope.OBSERVATION, PolicyScope.RESEARCH}),
    ToolName.ARTIFACT_ATTACH_CITATION: frozenset({PolicyScope.RESEARCH, PolicyScope.PROPOSAL}),
    ToolName.VIEW_DATASET_QUERY: frozenset({PolicyScope.RESEARCH}),
    ToolName.ANALYSIS_ARTIFACT_CREATE: frozenset({PolicyScope.RESEARCH, PolicyScope.PROPOSAL}),
}

# CR-08 (doc 22 §11): which capability keys gate a tool's contract. A gated
# tool enters the Agent tool registry ONLY while at least one of its gating
# capabilities is Limited/Active; Placeholder/Designed capabilities are never
# offered, so the Agent never plans around them (FD-10). The per-request
# capability re-check happens again inside the application command.
CAPABILITY_GATED_TOOLS: dict[ToolName, frozenset[str]] = {
    ToolName.VIEW_DATASET_QUERY: frozenset({"graphic_view"}),
    ToolName.ANALYSIS_ARTIFACT_CREATE: frozenset(
        {"backtest_review", "signal_intelligence", "regime_research", "parameter_fields"}
    ),
}


def exposed_tool_names(operational_capability_keys: frozenset[str] | set[str]) -> tuple[str, ...]:
    """The Agent-visible tool registry (doc 22 §11, CR-08): every ungated tool
    plus the capability tools whose gating capability is currently operational."""
    return tuple(
        tool.value
        for tool in ToolName
        if tool not in CAPABILITY_GATED_TOOLS
        or CAPABILITY_GATED_TOOLS[tool] & frozenset(operational_capability_keys)
    )


TERMINAL_TOOL_CALL_STATES: frozenset[ToolCallStatus] = frozenset(
    {ToolCallStatus.SUCCEEDED, ToolCallStatus.FAILED, ToolCallStatus.REJECTED}
)

# Queue routing: EXECUTION-scoped tools (backtest run/ready-check) carry the
# heaviest downstream work → the dedicated ``agent-high`` plane; everything else
# runs on the ``agent`` plane (doc 18 §9.2).
AGENT_QUEUE = "agent"
AGENT_HIGH_QUEUE = "agent-high"


def parse_tool_name(raw: str) -> ToolName:
    try:
        return ToolName(raw)
    except ValueError as exc:
        raise ToolPolicyScopeError(f"Unknown agent tool '{raw}'.") from exc


def parse_policy_scope(raw: str) -> PolicyScope:
    try:
        return PolicyScope(raw)
    except ValueError as exc:
        raise ToolPolicyScopeError(f"Unknown policy scope '{raw}'.") from exc


def ensure_scope_allowed(tool: ToolName, scope: PolicyScope) -> None:
    """A tool may run only under a scope it declares (doc 18 §9.2, §10)."""
    if scope not in TOOL_ALLOWED_SCOPES[tool]:
        raise ToolPolicyScopeError(
            f"Tool '{tool.value}' cannot run under policy scope '{scope.value}'."
        )


def queue_for_tool(tool: ToolName, scope: PolicyScope | None = None) -> str:
    """Route the heavy execution work to the high plane (doc 18 §9.2): an
    EXECUTION-scoped call (incl. an EXECUTION data-bundle resolve that gates a run)
    or a tool that is execution-only goes to ``agent-high``."""
    if scope is PolicyScope.EXECUTION:
        return AGENT_HIGH_QUEUE
    if TOOL_ALLOWED_SCOPES[tool] == frozenset({PolicyScope.EXECUTION}):
        return AGENT_HIGH_QUEUE
    return AGENT_QUEUE


def is_terminal_tool_call(status: ToolCallStatus) -> bool:
    return status in TERMINAL_TOOL_CALL_STATES


__all__ = [
    "AGENT_HIGH_QUEUE",
    "AGENT_QUEUE",
    "CAPABILITY_GATED_TOOLS",
    "TERMINAL_TOOL_CALL_STATES",
    "TOOL_ALLOWED_SCOPES",
    "PolicyScope",
    "ToolCallStatus",
    "ToolName",
    "ensure_scope_allowed",
    "exposed_tool_names",
    "is_terminal_tool_call",
    "parse_policy_scope",
    "parse_tool_name",
    "queue_for_tool",
]
