"""Tool Gateway — UI-less agent tool dispatch (Stage 6a-2, doc 18 §9.2, §10, §14).

The Alpha Agent does real domain work through the SAME policy-checked application
service line a human uses (doc 18 §10). ``dispatch_tool_call`` is the gateway:

    at-least-once replay guard (idempotency_key, AL-14) ->
    scope-legality guard (doc 18 §9.2) ->
    record the durable envelope (actor_context, task_id, checkpoint_id,
        input_manifest_id, idempotency_key, policy_scope, artifact_output_ref) ->
    tool_call_started event -> route to handler ->
    on governance denial: REJECTED + rejection event (AL-11), never a crash ->
    on success: SUCCEEDED + tool_call_succeeded event + artifact_output_ref.

Governance boundaries (doc 18 §14): ``agent_research_only`` data may never enter
an execution/backtest context (AL-11); a package proposal is candidate/draft only,
never approve/publish (AL-12); the Agent may soft-delete only its own artifact,
restore/purge stay Admin-only (AL-16). It never gains dataset approval, Trash,
role management or publish rights.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from entropia.application.commands import backtest_run as backtest_cmd
from entropia.application.commands import readiness_check as readiness_cmd
from entropia.domain.agent_lab.enums import (
    ALPHA_AGENT_ID,
    AgentTaskPriority,
    AgentTaskStatus,
    HypothesisStatus,
)
from entropia.domain.agent_lab.tool_gateway import (
    PolicyScope,
    ToolCallStatus,
    ToolName,
    ensure_scope_allowed,
    parse_policy_scope,
    parse_tool_name,
    queue_for_tool,
)
from entropia.domain.identity import Actor
from entropia.domain.lifecycle.enums import DeletionState, PrincipalType
from entropia.domain.research_data.usage_scope import (
    allows_agent_research,
    ensure_allows_evidence_bundle,
)
from entropia.infrastructure.postgres.models import Job
from entropia.infrastructure.postgres.repositories import agent_lab as al_repo
from entropia.infrastructure.postgres.repositories import agent_tool_gateway as tg_repo
from entropia.infrastructure.postgres.repositories import audit as audit_repo
from entropia.infrastructure.postgres.repositories import backtest as bt_repo
from entropia.infrastructure.postgres.repositories import market_data as market_repo
from entropia.infrastructure.postgres.repositories import research_data as research_repo
from entropia.infrastructure.queues.enqueue import enqueue_job
from entropia.shared.errors import (
    AgentToolCallForbiddenError,
    ArtifactOwnershipError,
    ForbiddenError,
    ResearchInputBlockedError,
)
from entropia.shared.ids import new_id

_ARTIFACT_TARGET = "hypothesis_artifact"
_TOOL_CALL_TARGET = "agent_tool_call"


@dataclass(frozen=True)
class _ToolOutcome:
    """A successful handler result written back onto the tool-call row. Every
    successful call also emits a generic ``tool_call_succeeded`` event; the
    tool-specific ``domain_events`` (data_bundle_pinned, artifact_created,
    package_proposal_created, ...) are emitted in addition (doc 18 §9.2)."""

    response: dict[str, Any]
    artifact_output_ref: str | None = None
    input_manifest_id: str | None = None
    domain_events: list[tuple[str, dict[str, Any]]] = field(default_factory=list)


@dataclass(frozen=True)
class _Ctx:
    session: AsyncSession
    actor: Actor
    agent_id: str
    tool: ToolName
    scope: PolicyScope
    task_id: str | None
    checkpoint_id: str | None
    request: dict[str, Any]
    call: Any  # AgentToolCall


# --------------------------------------------------------------------------- #
# Gateway
# --------------------------------------------------------------------------- #


async def dispatch_tool_call(
    session: AsyncSession,
    actor: Actor,
    *,
    tool_name: str,
    policy_scope: str,
    request: dict[str, Any] | None = None,
    task_id: str | None = None,
    checkpoint_id: str | None = None,
    input_manifest_id: str | None = None,
    idempotency_key: str | None = None,
    agent_id: str = ALPHA_AGENT_ID,
) -> dict[str, Any]:
    """Record + dispatch one UI-less agent tool call (doc 18 §9.2). No commit."""
    tool = parse_tool_name(tool_name)
    scope = parse_policy_scope(policy_scope)
    payload = dict(request or {})

    # At-least-once redelivery guard (AL-14): a prior call with this key never
    # re-executes; a terminal one replays its recorded outcome verbatim.
    if idempotency_key is not None:
        prior = await tg_repo.get_by_idempotency_key(session, idempotency_key)
        if prior is not None:
            return _replayed(prior)

    call = await tg_repo.create_tool_call(
        session,
        tool_name=tool,
        agent_id=agent_id,
        actor_principal_id=actor.principal_id,
        actor_kind=actor.actor_kind,
        policy_scope=scope,
        task_id=task_id,
        checkpoint_id=checkpoint_id,
        input_manifest_id=input_manifest_id,
        idempotency_key=idempotency_key,
        request=payload,
        correlation_id=actor.correlation_id,
    )
    await _emit_event(
        session, actor, "tool_call_started", task_id=task_id, payload={"tool": tool.value}
    )

    ctx = _Ctx(
        session=session,
        actor=actor,
        agent_id=agent_id,
        tool=tool,
        scope=scope,
        task_id=task_id,
        checkpoint_id=checkpoint_id,
        request=payload,
        call=call,
    )
    try:
        ensure_scope_allowed(tool, scope)
        outcome = await _HANDLERS[tool](ctx)
    except ForbiddenError as denial:
        return await _record_rejection(ctx, denial)

    call.status = ToolCallStatus.SUCCEEDED
    call.response_ref = outcome.response
    call.artifact_output_ref = outcome.artifact_output_ref
    if outcome.input_manifest_id is not None:
        call.input_manifest_id = outcome.input_manifest_id
    for event_type, event_payload in outcome.domain_events:
        await _emit_event(session, actor, event_type, task_id=task_id, payload=event_payload)
    await _emit_event(
        session,
        actor,
        "tool_call_succeeded",
        task_id=task_id,
        payload={"tool": tool.value, "tool_call_id": call.tool_call_id},
    )
    # The envelope's lifecycle status + id WIN over any handler payload key: a
    # handler's own ``status`` (e.g. hypothesis ``exploring``) must never shadow
    # the call's terminal ``succeeded`` — the durable row is authoritative.
    return {**outcome.response, "tool_call_id": call.tool_call_id, "status": "succeeded"}


def _replayed(prior: Any) -> dict[str, Any]:
    # Same envelope-wins rule as the success path: the durable row's terminal
    # status + id are authoritative, never shadowed by the stored handler payload.
    return {
        **(prior.response_ref or {}),
        "tool_call_id": prior.tool_call_id,
        "status": str(prior.status),
        "replayed": True,
    }


async def _record_rejection(ctx: _Ctx, denial: ForbiddenError) -> dict[str, Any]:
    """A governance denial is a durable REJECTED outcome, not a crash (AL-11)."""
    reason_code = getattr(denial, "code", "FORBIDDEN")
    response = {"status": "rejected", "reason_code": reason_code, "reason": denial.message}
    ctx.call.status = ToolCallStatus.REJECTED
    ctx.call.failure_code = reason_code
    ctx.call.failure_message = denial.message
    ctx.call.response_ref = response
    event_type = (
        "research_input_blocked"
        if isinstance(denial, ResearchInputBlockedError)
        else "tool_call_failed"
    )
    await _emit_event(
        ctx.session,
        ctx.actor,
        event_type,
        task_id=ctx.task_id,
        payload={"tool": ctx.tool.value, "reason_code": reason_code},
    )
    return {"tool_call_id": ctx.call.tool_call_id, **response}


async def _emit_event(
    session: AsyncSession,
    actor: Actor,
    event_type: str,
    *,
    task_id: str | None,
    payload: dict[str, Any],
) -> None:
    await al_repo.append_event(
        session,
        event_type=event_type,
        actor_principal_id=actor.principal_id,
        actor_kind=actor.actor_kind,
        task_id=task_id,
        payload=payload,
        correlation_id=actor.correlation_id,
    )


# --------------------------------------------------------------------------- #
# Handlers (doc 18 §10 parity table)
# --------------------------------------------------------------------------- #


async def _handle_task_query(ctx: _Ctx) -> _ToolOutcome:
    """`agent.task.query` — read the Agent's OWN task (doc 18 §10)."""
    target_task_id = str(ctx.request.get("target_task_id") or ctx.task_id or "")
    task = await al_repo.get_task(ctx.session, target_task_id) if target_task_id else None
    if task is None:
        return _ToolOutcome(response={"found": False})
    if task.agent_id != ctx.agent_id:
        # Never reach another principal's private object outside policy (doc 18 §10).
        raise AgentToolCallForbiddenError("The Agent may only query its own tasks.")
    return _ToolOutcome(
        response={
            "found": True,
            "task_id": task.task_id,
            # Namespaced so it never shadows the envelope's call ``status``.
            "task_status": str(task.status),
            "stage": task.stage,
            "progress": task.progress,
            "context_manifest_id": task.context_manifest_id,
        }
    )


async def _handle_result_query(ctx: _Ctx) -> _ToolOutcome:
    """`result.query` — read an immutable Backtest Result / run (doc 18 §10)."""
    run_id = ctx.request.get("run_id")
    if run_id is not None:
        run = await bt_repo.get_run(ctx.session, str(run_id))
        if run is None:
            return _ToolOutcome(response={"found": False})
        return _ToolOutcome(
            response={
                "found": True,
                "run_id": run.run_id,
                "state": str(run.state),
                "result_id": run.result_id,
            }
        )
    result_id = ctx.request.get("result_id")
    result = await bt_repo.get_result(ctx.session, str(result_id)) if result_id else None
    if result is None:
        return _ToolOutcome(response={"found": False})
    return _ToolOutcome(
        response={"found": True, "result_id": result.result_id, "run_id": result.run_id}
    )


async def _handle_data_bundle_resolve(ctx: _Ctx) -> _ToolOutcome:
    """`data_bundle.resolve` — pin approved Market + usage-scoped Research revisions
    into a context bundle. EXECUTION scope enforces the evidence-bundle gate:
    ``agent_research_only`` is blocked and never enters the manifest (AL-11)."""
    market_ids = [str(x) for x in ctx.request.get("market_revision_ids", [])]
    research_specs = ctx.request.get("research_revisions", [])
    execution = ctx.scope is PolicyScope.EXECUTION

    pinned_market: list[str] = []
    for revision_id in market_ids:
        revision = await market_repo.get_revision(ctx.session, revision_id)
        if revision is None:
            raise ResearchInputBlockedError(
                f"Market revision '{revision_id}' is not resolvable for a data bundle."
            )
        pinned_market.append(revision_id)

    pinned_research: list[str] = []
    for spec in research_specs:
        revision_id = str(spec.get("revision_id"))
        has_feature_def = bool(spec.get("has_approved_feature_definition", False))
        research_rev = await research_repo.get_revision(ctx.session, revision_id)
        if research_rev is None or research_rev.usage_scope is None:
            raise ResearchInputBlockedError(
                f"Research revision '{revision_id}' is not resolvable for a data bundle."
            )
        scope = research_rev.usage_scope
        if execution:
            # Real evidence-bundle gate: agent_research_only -> UsageScopeForbidden;
            # feature_input_only requires an approved feature definition (doc 12 §9.3).
            try:
                ensure_allows_evidence_bundle(
                    scope, has_approved_feature_definition=has_feature_def
                )
            except ForbiddenError as exc:
                raise ResearchInputBlockedError(str(exc)) from exc
        elif not allows_agent_research(scope):
            raise ResearchInputBlockedError(
                f"Research revision '{revision_id}' scope forbids Agent research use."
            )
        pinned_research.append(revision_id)

    manifest_id = new_id("agtbundle")
    return _ToolOutcome(
        response={
            "context_manifest_id": manifest_id,
            "scope": ctx.scope.value,
            "market_revision_ids": pinned_market,
            "research_revision_ids": pinned_research,
        },
        artifact_output_ref=manifest_id,
        input_manifest_id=manifest_id,
        domain_events=[("data_bundle_pinned", {"manifest_id": manifest_id})],
    )


async def _create_agent_artifact(
    ctx: _Ctx, *, default_status: HypothesisStatus, allow_status_override: bool = True
) -> Any:
    """Shared: create an Agent-owned hypothesis artifact + optional provenance links.

    ``allow_status_override=False`` pins the status (used by package proposals, which
    are always CANDIDATE — the Agent can never self-escalate maturity, AL-12)."""
    request = ctx.request
    status_raw = request.get("status") if allow_status_override else None
    status = HypothesisStatus(status_raw) if status_raw else default_status
    artifact = await al_repo.create_hypothesis(
        ctx.session,
        status=status,
        title=str(request.get("title", "Untitled hypothesis")),
        mechanism=str(request.get("mechanism", "")),
        data_context=request.get("data_context"),
        evidence_refs=request.get("evidence_refs") or [],
        next_action=request.get("next_action"),
        source_task_id=ctx.task_id,
        checkpoint_id=ctx.checkpoint_id,
        created_by_principal_id=ctx.actor.principal_id,
        correlation_id=ctx.actor.correlation_id,
    )
    for link in request.get("links", []):
        await al_repo.create_artifact_link(
            ctx.session,
            source_artifact_id=artifact.artifact_id,
            target_type=str(link.get("target_type", "unknown")),
            target_id=str(link.get("target_id", "")),
            relation_type=str(link.get("relation_type", "relates_to")),
        )
    return artifact


async def _handle_artifact_create(ctx: _Ctx) -> _ToolOutcome:
    """`artifact.create` — persist an Agent-owned hypothesis/output (doc 18 §10)."""
    artifact = await _create_agent_artifact(ctx, default_status=HypothesisStatus.EXPLORING)
    return _ToolOutcome(
        # ``artifact_status`` is namespaced so the artifact's maturity never
        # shadows the envelope's call ``status`` (doc 18 §9.2).
        response={"artifact_id": artifact.artifact_id, "artifact_status": str(artifact.status)},
        artifact_output_ref=artifact.artifact_id,
        domain_events=[
            ("artifact_created", {"artifact_id": artifact.artifact_id}),
            ("hypothesis_created", {"artifact_id": artifact.artifact_id}),
        ],
    )


async def _handle_package_proposal_create(ctx: _Ctx) -> _ToolOutcome:
    """`package.proposal.create` — a CANDIDATE/draft proposal only; the Agent can
    never approve or publish (doc 18 §10, §14, AL-12). Recorded as a candidate
    hypothesis artifact with package provenance; entry to the Create Package
    approval pipeline stays human/Admin-gated."""
    artifact = await _create_agent_artifact(ctx, default_status=HypothesisStatus.CANDIDATE)
    await al_repo.create_artifact_link(
        ctx.session,
        source_artifact_id=artifact.artifact_id,
        target_type="package_proposal",
        target_id=str(ctx.request.get("package_ref", artifact.artifact_id)),
        relation_type="proposes_candidate",
    )
    return _ToolOutcome(
        response={
            "artifact_id": artifact.artifact_id,
            "proposal_status": "candidate",
            "can_approve": False,
            "can_publish": False,
        },
        artifact_output_ref=artifact.artifact_id,
        domain_events=[("package_proposal_created", {"artifact_id": artifact.artifact_id})],
    )


async def _handle_artifact_soft_delete(ctx: _Ctx) -> _ToolOutcome:
    """`artifact.soft_delete` — the Agent removes its OWN artifact from the active
    board; provenance/audit are retained; restore/purge are Admin-only (AL-16)."""
    artifact_id = str(ctx.request.get("artifact_id", ""))
    artifact = await al_repo.get_hypothesis(ctx.session, artifact_id)
    if artifact is None:
        raise ArtifactOwnershipError("The artifact to soft-delete was not found.")
    if artifact.created_by_principal_id != ctx.actor.principal_id:
        raise ArtifactOwnershipError()
    if artifact.deletion_state is not DeletionState.ACTIVE:
        return _ToolOutcome(
            response={"artifact_id": artifact_id, "deletion_state": str(artifact.deletion_state)}
        )
    artifact.deletion_state = DeletionState.SOFT_DELETED
    artifact.row_version += 1
    audit_repo.add_audit_event(
        ctx.session,
        event_kind="agent.artifact.soft_deleted",
        actor_principal_id=ctx.actor.principal_id,
        actor_kind=ctx.actor.actor_kind,
        target_entity_id=artifact_id,
        target_entity_type=_ARTIFACT_TARGET,
        new_state=DeletionState.SOFT_DELETED.value,
        correlation_id=ctx.actor.correlation_id,
    )
    audit_repo.add_outbox_event(
        ctx.session,
        event_type="agent.artifact.soft_deleted",
        resource_type=_ARTIFACT_TARGET,
        resource_id=artifact_id,
        payload={"artifact_id": artifact_id, "deletion_state": DeletionState.SOFT_DELETED.value},
        correlation_id=ctx.actor.correlation_id,
    )
    return _ToolOutcome(
        response={"artifact_id": artifact_id, "deletion_state": DeletionState.SOFT_DELETED.value},
        artifact_output_ref=artifact_id,
    )


async def _handle_followup_task_enqueue(ctx: _Ctx) -> _ToolOutcome:
    """`followup_task.enqueue` — the Agent plans an AUTONOMOUS follow-up task within
    its own policy/budget (doc 18 §9.1, §10). Never human-selectable priority."""
    task = await al_repo.create_task(
        ctx.session,
        agent_id=ctx.agent_id,
        task_type=str(ctx.request.get("task_type", "research")),
        title=str(ctx.request.get("title", "Autonomous follow-up")),
        source=str(ctx.request.get("source", "autonomous")),
        priority=AgentTaskPriority.AUTONOMOUS,
        status=AgentTaskStatus.QUEUED,
        stage=ctx.request.get("stage"),
        context_manifest_id=ctx.request.get("context_manifest_id"),
        parent_task_id=ctx.request.get("parent_task_id") or ctx.task_id,
    )
    return _ToolOutcome(
        response={"task_id": task.task_id, "priority": str(task.priority)},
        artifact_output_ref=task.task_id,
        domain_events=[("agent_task_created", {"task_id": task.task_id})],
    )


async def _handle_backtest_ready_check(ctx: _Ctx) -> _ToolOutcome:
    """`backtest.ready_check` — the same Ready Check command a human runs (doc 18
    §10). Ready Check is never bypassable; the report is the gate for a run."""
    composition_id = str(ctx.request.get("composition_id", ""))
    report = await readiness_cmd.run_readiness_check(
        ctx.session,
        ctx.actor,
        composition_id=composition_id,
        expected_fingerprint=ctx.request.get("expected_fingerprint"),
        idempotency_key=ctx.request.get("idempotency_key"),
    )
    return _ToolOutcome(response=report, artifact_output_ref=report.get("report_id"))


async def _handle_backtest_request(ctx: _Ctx) -> _ToolOutcome:
    """`backtest.request` — the same admission command a human uses; Ready Check is
    enforced INSIDE the command (never bypassed) and the run manifest is pinned
    (doc 18 §10, §9.1). A cancelled/failed run never yields a normal Result."""
    composition_id = str(ctx.request.get("composition_id", ""))
    run = await backtest_cmd.request_backtest_run(
        ctx.session,
        ctx.actor,
        composition_id=composition_id,
        expected_fingerprint=ctx.request.get("expected_fingerprint"),
        ready_report_id=ctx.request.get("ready_report_id"),
        idempotency_key=ctx.request.get("idempotency_key"),
    )
    return _ToolOutcome(
        response=run,
        artifact_output_ref=run.get("run_id"),
        domain_events=[("backtest_requested", {"run_id": run.get("run_id")})],
    )


async def _handle_documentation_search(ctx: _Ctx) -> _ToolOutcome:
    """`documentation.search` — Published-corpus search through the SAME read
    model a human uses (doc 21 §12, UM-03). Draft/soft-deleted content never
    enters the result; the Agent needs no browser session."""
    from entropia.application.queries.manual import search_manual

    page = await search_manual(
        ctx.session,
        ctx.actor,
        q=str(ctx.request.get("query", "")),
        cursor=ctx.request.get("cursor"),
        limit=ctx.request.get("limit"),
    )
    return _ToolOutcome(response={"results": page["data"], "meta": page["meta"]})


async def _handle_documentation_get_section(ctx: _Ctx) -> _ToolOutcome:
    """`documentation.get_section` — canonical blocks + source label +
    stream_version + citation metadata for one published section (doc 21 §12)."""
    from entropia.application.queries.manual import get_manual_section

    revision_no_raw = ctx.request.get("revision_no")
    section = await get_manual_section(
        ctx.session,
        ctx.actor,
        document_id=str(ctx.request.get("document_id", "")),
        anchor=ctx.request.get("anchor"),
        revision_no=int(revision_no_raw) if revision_no_raw is not None else None,
    )
    return _ToolOutcome(response=section)


async def _handle_artifact_attach_citation(ctx: _Ctx) -> _ToolOutcome:
    """`artifact.attach_citation` — provenance evidence on the Agent's OWN
    artifact (doc 21 §12): document_id + revision_no + anchor + block_ids. The
    cited revision must exist; the manual itself is never mutated."""
    from entropia.infrastructure.postgres.repositories import manual as manual_repo

    artifact_id = str(ctx.request.get("artifact_id", ""))
    artifact = await al_repo.get_hypothesis(ctx.session, artifact_id)
    if artifact is None:
        raise ArtifactOwnershipError("The artifact to cite from was not found.")
    if artifact.created_by_principal_id != ctx.actor.principal_id:
        raise ArtifactOwnershipError("The Agent may only attach citations to its own artifacts.")

    document_id = str(ctx.request.get("document_id", ""))
    revision_no = int(ctx.request.get("revision_no", 0))
    anchor = str(ctx.request.get("anchor", ""))
    revision = await manual_repo.get_revision_by_no(ctx.session, document_id, revision_no)
    if revision is None:
        raise AgentToolCallForbiddenError(
            "The cited manual revision does not exist; a citation must resolve."
        )
    citation = {
        "document_id": document_id,
        "revision_no": revision_no,
        "revision_id": revision.revision_id,
        "anchor": anchor,
        "block_ids": [str(b) for b in ctx.request.get("block_ids", [])],
    }
    link = await al_repo.create_artifact_link(
        ctx.session,
        source_artifact_id=artifact_id,
        target_type="manual_citation",
        # target_id is String(64); the anchor rides in the citation payload.
        target_id=f"{document_id}@{revision_no}",
        relation_type="cites_manual",
    )
    return _ToolOutcome(
        response={"artifact_id": artifact_id, "link_id": link.link_id, "citation": citation},
        artifact_output_ref=artifact_id,
        domain_events=[("citation_attached", {"artifact_id": artifact_id, "citation": citation})],
    )


async def _handle_view_dataset_query(ctx: _Ctx) -> _ToolOutcome:
    """`view_dataset.query` — Graphic View input preparation (doc 22 §11, CR-08).
    The command re-checks the server-side registry state: below Limited/Active
    it raises CAPABILITY_NOT_ACTIVE, which lands here as a recorded REJECTED
    denial — no dataset row, no job, no fake output (CR-09, FD-02/10)."""
    from entropia.application.commands.capability import query_view_dataset

    result = await query_view_dataset(
        ctx.session,
        ctx.actor,
        source_manifest_refs=list(ctx.request.get("source_manifest_refs") or []),
        schema_version=str(ctx.request.get("schema_version", "")),
        series_refs=ctx.request.get("series_refs"),
        marker_refs=ctx.request.get("marker_refs"),
        range_spec=ctx.request.get("range_spec"),
    )
    return _ToolOutcome(
        response=result,
        artifact_output_ref=result["view_dataset_id"],
        domain_events=[("view_dataset_prepared", {"view_dataset_id": result["view_dataset_id"]})],
    )


async def _handle_analysis_artifact_create(ctx: _Ctx) -> _ToolOutcome:
    """`analysis_artifact.create` — immutable evidence-linked analysis output
    (doc 22 §10.3-§10.6, §11). Same capability re-check as the HTTP route; a
    Placeholder capability yields a recorded CAPABILITY_NOT_ACTIVE rejection."""
    from entropia.application.commands.capability import create_analysis_artifact

    result = await create_analysis_artifact(
        ctx.session,
        ctx.actor,
        artifact_type=str(ctx.request.get("artifact_type", "")),
        input_manifest_refs=list(ctx.request.get("input_manifest_refs") or []),
        method_version=str(ctx.request.get("method_version", "")),
        output_ref=ctx.request.get("output_ref"),
    )
    return _ToolOutcome(
        response=result,
        artifact_output_ref=result["artifact_id"],
        domain_events=[
            (
                "analysis_artifact_created",
                {"artifact_id": result["artifact_id"], "artifact_type": result["artifact_type"]},
            )
        ],
    )


_HANDLERS = {
    ToolName.TASK_QUERY: _handle_task_query,
    ToolName.RESULT_QUERY: _handle_result_query,
    ToolName.DATA_BUNDLE_RESOLVE: _handle_data_bundle_resolve,
    ToolName.PACKAGE_PROPOSAL_CREATE: _handle_package_proposal_create,
    ToolName.ARTIFACT_CREATE: _handle_artifact_create,
    ToolName.ARTIFACT_SOFT_DELETE: _handle_artifact_soft_delete,
    ToolName.FOLLOWUP_TASK_ENQUEUE: _handle_followup_task_enqueue,
    ToolName.BACKTEST_READY_CHECK: _handle_backtest_ready_check,
    ToolName.BACKTEST_REQUEST: _handle_backtest_request,
    ToolName.DOCUMENTATION_SEARCH: _handle_documentation_search,
    ToolName.DOCUMENTATION_GET_SECTION: _handle_documentation_get_section,
    ToolName.ARTIFACT_ATTACH_CITATION: _handle_artifact_attach_citation,
    ToolName.VIEW_DATASET_QUERY: _handle_view_dataset_query,
    ToolName.ANALYSIS_ARTIFACT_CREATE: _handle_analysis_artifact_create,
}


# --------------------------------------------------------------------------- #
# Durable job body (agent / agent-high queue)
# --------------------------------------------------------------------------- #


def enqueue_tool_call(
    session: AsyncSession,
    actor: Actor,
    *,
    tool_name: str,
    policy_scope: str,
    request: dict[str, Any] | None = None,
    task_id: str | None = None,
    checkpoint_id: str | None = None,
    input_manifest_id: str | None = None,
    idempotency_key: str | None = None,
    agent_id: str = ALPHA_AGENT_ID,
) -> Job:
    """Enqueue a durable Tool Gateway job, routed by scope to ``agent`` /
    ``agent-high`` (doc 18 §9.2). Does not commit; after the transaction commits
    the caller dispatches the matching actor via ``send_job``. The job payload is
    the tool-call envelope the worker replays into ``dispatch_tool_call``."""
    tool = parse_tool_name(tool_name)
    scope = parse_policy_scope(policy_scope)
    return enqueue_job(
        session,
        queue=queue_for_tool(tool, scope),
        payload={
            "tool_name": tool.value,
            "policy_scope": scope.value,
            "request": dict(request or {}),
            "task_id": task_id,
            "checkpoint_id": checkpoint_id,
            "input_manifest_id": input_manifest_id,
            "agent_id": agent_id,
            "actor_principal_id": actor.principal_id,
        },
        actor_principal_id=actor.principal_id,
        idempotency_key=idempotency_key,
        correlation_id=actor.correlation_id,
    )


async def run_tool_job(session: AsyncSession, job_id: str) -> dict[str, Any]:
    """Execute a durable Tool Gateway job (doc 18 §9.2). Does not commit (the
    worker scope commits). Redelivery-safe via the tool_call idempotency guard."""
    job = await session.get(Job, job_id)
    if job is None:
        raise ValueError(f"Job '{job_id}' not found.")
    payload = job.payload or {}
    actor = Actor(
        principal_id=payload.get("actor_principal_id"),
        principal_type=PrincipalType.AGENT,
        role=None,
        correlation_id=job.correlation_id or "",
    )
    return await dispatch_tool_call(
        session,
        actor,
        tool_name=str(payload.get("tool_name", "")),
        policy_scope=str(payload.get("policy_scope", "")),
        request=payload.get("request") or {},
        task_id=payload.get("task_id"),
        checkpoint_id=payload.get("checkpoint_id"),
        input_manifest_id=payload.get("input_manifest_id"),
        idempotency_key=job.idempotency_key,
        agent_id=str(payload.get("agent_id", ALPHA_AGENT_ID)),
    )


__all__ = ["dispatch_tool_call", "enqueue_tool_call", "run_tool_job"]
