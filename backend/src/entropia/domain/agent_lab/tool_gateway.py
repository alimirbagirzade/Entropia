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
    # Post-V1 S4 — Portfolio / Equity Allocation parity (doc 13 §9): the SAME
    # draft/validate/revision command line a human uses. The Agent mutates only
    # its OWN composition's plan (ownership enforced INSIDE each command); a
    # foreign-owner plan is a recorded REJECTED denial, never last-write-wins.
    ALLOCATION_GET_DRAFT = "portfolio_allocation.get_draft"
    ALLOCATION_UPSERT_DRAFT = "portfolio_allocation.upsert_draft"
    ALLOCATION_SYNC_PREVIEW = "portfolio_allocation.sync_preview"
    ALLOCATION_VALIDATE = "portfolio_allocation.validate"
    ALLOCATION_CREATE_REVISION = "portfolio_allocation.create_revision"
    # Post-V1 S4 — Trade Log parity (doc 05 §11, TL-22): the SAME upload/import/
    # save/revision command line a human uses (a Trade Log is a native work object,
    # CR-01). Pin (``Use This Revision``) + soft-delete stay the shared 3a Mainboard
    # tools; export (doc 05 §11 request_trade_log_export) is a separate slice.
    TRADE_LOG_UPLOAD_SOURCE = "trade_log.upload_source_asset"
    TRADE_LOG_REQUEST_IMPORT = "trade_log.request_import"
    TRADE_LOG_CREATE = "trade_log.create"
    TRADE_LOG_CREATE_REVISION = "trade_log.create_revision"
    # Post-V1 S5 — Strategy draft/save parity (doc 02 §12 AT-21, §11 rule 20): the
    # SAME create/patch/validate/save command line a human uses, with no browser
    # and no human session. The Agent mutates only its OWN draft/root (ownership
    # enforced INSIDE each command); a human's private draft is a recorded denial,
    # never last-write-wins. Save appends an immutable revision — it is never a
    # Ready PASS and never a Run (doc 02 §7.1), and it never attaches anything to
    # a human Mainboard (these tools carry no workspace/attach parameter at all).
    #
    # NAMING (adjudicated). Doc 18 §10's parity table writes ``strategy.draft.create``
    # in prose; the same table also names ``artifact.query``, ``context_manifest.read``,
    # ``market_data.query`` and ``research_data.query``, none of which are ToolName
    # members either — that table illustrates intent, it is not the registry. The
    # shipped registry convention is ``<family>.<verb_object>``
    # (``trade_log.create_revision``, ``portfolio_allocation.upsert_draft``), so the
    # strategy family follows it. These five literals are also the ones the
    # ground-truth audit (G-03) pinned as ABSENT.
    STRATEGY_GET_DRAFT = "strategy.get_draft"
    STRATEGY_CREATE_DRAFT = "strategy.create_draft"
    STRATEGY_PATCH_DRAFT = "strategy.patch_draft"
    STRATEGY_VALIDATE_DRAFT = "strategy.validate_draft"
    STRATEGY_SAVE_REVISION = "strategy.save_revision"
    # Post-V1 S6 — Trading Signal parity (doc 04 §10 + §15 TS-20, doc 03 §14 AOS-20):
    # "Agent creates/imports/validates/saves/attaches a Signal via Tool Gateway
    # without opening browser ... human board is not auto-mutated." These call the
    # SAME upload/import/report/save/revision commands the page calls. A Trading
    # Signal is a native external WORK OBJECT, never a Package (CR-01) — nothing here
    # touches ``PackageKind`` and the Mainboard ``item_kind`` stays server-derived.
    #
    # NAMING (adjudicated, by the rule the strategy family established). Doc 04 §10's
    # parity table is written in AGENT-INTENT terms and names the real backing command
    # in its own "Tool / domain capability" column; the registry follows the COMMAND,
    # because the command is what parity is actually about:
    #   * ``trading_signal.create``        -> shipped verbatim (the table's own name).
    #   * ``trading_signal.import_events`` -> the table backs it with TWO commands,
    #     "UploadSourceAsset + RequestTradingSignalImport". They are genuinely two
    #     steps with two different durability stories (an immutable content-addressed
    #     asset vs. a durable data-queue job), so they ship as two tools; fusing them
    #     would have hidden the admission/completion boundary the import depends on.
    #   * ``trading_signal.validate``      -> backed by "GetImportReport". The report
    #     IS the validation surface here (the §9.2 config compiler runs INSIDE
    #     create/create_revision, it is not a separate command), so the read ships
    #     under its command name rather than inventing a validate-only entry point.
    #   * ``trading_signal.save_revision`` -> backed by ``CreateTradingSignalRevision``;
    #     ships as ``create_revision`` so the sibling external work object
    #     (``trade_log.create_revision``) and this one read identically.
    # ``trading_signal.attach`` is covered by ``create`` (its ``attach`` flag runs the
    # shared 3a ``attach_mainboard_item``). The standalone "Use This Revision" re-pin
    # and ``trading_signal.delete`` stay OUT of this slice, on exactly the boundary the
    # trade_log family took: they are shared Mainboard/lifecycle surfaces, not
    # signal-specific ones, and no tool exists for them on either family yet.
    TRADING_SIGNAL_UPLOAD_SOURCE = "trading_signal.upload_source_asset"
    TRADING_SIGNAL_REQUEST_IMPORT = "trading_signal.request_import"
    TRADING_SIGNAL_GET_IMPORT_REPORT = "trading_signal.get_import_report"
    TRADING_SIGNAL_CREATE = "trading_signal.create"
    TRADING_SIGNAL_CREATE_REVISION = "trading_signal.create_revision"


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
    # S4 allocation (doc 13 §9): reads are OBSERVATION/RESEARCH; the draft/validate/
    # revision mutations are hypothesis-shaping work, never a backtest EXECUTION
    # (a run is a separate ``backtest.request`` tool, doc 13 §9 last row).
    ToolName.ALLOCATION_GET_DRAFT: frozenset({PolicyScope.OBSERVATION, PolicyScope.RESEARCH}),
    ToolName.ALLOCATION_SYNC_PREVIEW: frozenset({PolicyScope.OBSERVATION, PolicyScope.RESEARCH}),
    ToolName.ALLOCATION_UPSERT_DRAFT: frozenset({PolicyScope.RESEARCH, PolicyScope.PROPOSAL}),
    ToolName.ALLOCATION_VALIDATE: frozenset({PolicyScope.RESEARCH, PolicyScope.PROPOSAL}),
    ToolName.ALLOCATION_CREATE_REVISION: frozenset({PolicyScope.PROPOSAL}),
    # S4 trade_log (doc 05 §11): upload/import prepare research inputs; save/revision
    # produce a native work object (a proposal-shaped output), never a run.
    ToolName.TRADE_LOG_UPLOAD_SOURCE: frozenset({PolicyScope.RESEARCH}),
    ToolName.TRADE_LOG_REQUEST_IMPORT: frozenset({PolicyScope.RESEARCH}),
    ToolName.TRADE_LOG_CREATE: frozenset({PolicyScope.RESEARCH, PolicyScope.PROPOSAL}),
    ToolName.TRADE_LOG_CREATE_REVISION: frozenset({PolicyScope.RESEARCH, PolicyScope.PROPOSAL}),
    # S5 strategy (doc 02 §12 AT-21): reading a draft is OBSERVATION/RESEARCH;
    # shaping one (create/patch/validate) is RESEARCH/PROPOSAL hypothesis work;
    # Save publishes the immutable revision the Agent proposes, so it is
    # PROPOSAL-only — never EXECUTION (a run is the separate ``backtest.request``
    # tool, and Save is never a Ready PASS, doc 02 §7.1).
    ToolName.STRATEGY_GET_DRAFT: frozenset({PolicyScope.OBSERVATION, PolicyScope.RESEARCH}),
    ToolName.STRATEGY_CREATE_DRAFT: frozenset({PolicyScope.RESEARCH, PolicyScope.PROPOSAL}),
    ToolName.STRATEGY_PATCH_DRAFT: frozenset({PolicyScope.RESEARCH, PolicyScope.PROPOSAL}),
    ToolName.STRATEGY_VALIDATE_DRAFT: frozenset({PolicyScope.RESEARCH, PolicyScope.PROPOSAL}),
    ToolName.STRATEGY_SAVE_REVISION: frozenset({PolicyScope.PROPOSAL}),
    # S6 trading_signal (doc 04 §10): the import half prepares research inputs; the
    # save half produces a native external work object (a proposal-shaped output).
    # Reading the import report is an OBSERVATION/RESEARCH read. NONE of them is
    # EXECUTION — doc 04 §15 TS-21 is explicit that "Add Outsource Signal selection
    # or save never creates Backtest Result", so all five route to the ``agent``
    # queue and a run stays the separate ``backtest.request`` tool.
    ToolName.TRADING_SIGNAL_UPLOAD_SOURCE: frozenset({PolicyScope.RESEARCH}),
    ToolName.TRADING_SIGNAL_REQUEST_IMPORT: frozenset({PolicyScope.RESEARCH}),
    ToolName.TRADING_SIGNAL_GET_IMPORT_REPORT: frozenset(
        {PolicyScope.OBSERVATION, PolicyScope.RESEARCH}
    ),
    ToolName.TRADING_SIGNAL_CREATE: frozenset({PolicyScope.RESEARCH, PolicyScope.PROPOSAL}),
    ToolName.TRADING_SIGNAL_CREATE_REVISION: frozenset(
        {PolicyScope.RESEARCH, PolicyScope.PROPOSAL}
    ),
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
