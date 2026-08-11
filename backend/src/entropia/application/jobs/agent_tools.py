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

from entropia.application.commands import agent_artifact as artifact_cmd
from entropia.application.commands import backtest_run as backtest_cmd
from entropia.application.commands import readiness_check as readiness_cmd
from entropia.application.jobs import research_data as rd_jobs
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
from entropia.infrastructure.postgres.repositories import backtest as bt_repo
from entropia.infrastructure.postgres.repositories import market_data as market_repo
from entropia.infrastructure.queues.enqueue import enqueue_job
from entropia.shared.errors import (
    AgentToolCallForbiddenError,
    AgentToolRequestInvalidError,
    AppError,
    ArtifactOwnershipError,
    ForbiddenError,
    ResearchInputBlockedError,
)
from entropia.shared.ids import new_id

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
        # The handler still receives ``payload`` with its bytes intact; only what is
        # PERSISTED is de-referenced, and it happens here — before the INSERT — so an
        # oversized file is never written to the row it is about to be rejected for.
        request=_persistable_request(tool, payload),
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
        if tool in _DURABLE_FAILURE_TOOLS:
            # A recorded FAILED outcome must never carry HALF-DONE work into the
            # commit. A command can flush rows (an immutable revision, its mirror)
            # and only then hit a typed failure downstream (a Mainboard re-pin OCC
            # clash, say); the human line is saved by the request scope's rollback,
            # which this durable path does not get. The SAVEPOINT rolls the handler
            # back to exactly the state before it ran — the tool-call row itself was
            # created BEFORE the savepoint, so the evidence survives the rollback.
            async with session.begin_nested():
                outcome = await _HANDLERS[tool](ctx)
        else:
            outcome = await _HANDLERS[tool](ctx)
    except ForbiddenError as denial:
        return await _record_rejection(ctx, denial)
    except AppError as failure:
        # A typed NON-governance failure — malformed request, stale OCC token,
        # compiler blockers. For the families in ``_DURABLE_FAILURE_TOOLS`` this is
        # recorded as a terminal FAILED call (the Agent gets evidence and a code
        # identical to the human line's) instead of escaping into the worker's
        # rollback + dramatiq retry loop, where a deterministic denial would be
        # retried three times and leave NO tool-call row at all. Other families
        # keep their landed propagate-to-caller contract (see the frozenset).
        if tool not in _DURABLE_FAILURE_TOOLS:
            raise
        return await _record_failure(ctx, failure)

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


# Tools whose request carries raw file bytes that must NOT be copied into the
# durable tool-call envelope. The tool-call row is the long-lived agent history
# surface, so inlining a multi-megabyte ledger there would duplicate the asset into
# evidence storage forever — and would do it even for a file that is about to be
# REJECTED for being too large, which is the one case where writing it is most
# obviously wrong. The bytes belong in object storage, content-addressed; the row
# keeps the address. Scoped to the signal family on purpose: the landed trade_log
# tools have their own recorded envelope shape and this slice does not restate it.
_SOURCE_CONTENT_TOOLS: frozenset[ToolName] = frozenset({ToolName.TRADING_SIGNAL_UPLOAD_SOURCE})


def _persistable_request(tool: ToolName, payload: dict[str, Any]) -> dict[str, Any]:
    """The request as it should be STORED — raw source bytes replaced by a reference.

    The in-memory ``payload`` the handler runs on is untouched; only the durable copy
    is de-referenced, and the digest is the SAME sha256 the upload command
    content-addresses the asset by, so the row still names the exact object.
    """
    if tool not in _SOURCE_CONTENT_TOOLS or "content" not in payload:
        return payload
    from entropia.infrastructure.s3 import datasets

    raw = payload["content"]
    content = raw.encode("utf-8") if isinstance(raw, str) else raw
    stored = {key: value for key, value in payload.items() if key != "content"}
    if not isinstance(content, bytes | bytearray):
        # A malformed ``content`` is about to fail closed in the handler; record the
        # shape that was sent rather than pretending an asset reference exists.
        stored["content_ref"] = {"invalid_type": type(raw).__name__}
        return stored
    stored["content_ref"] = {
        "sha256": datasets.content_digest(bytes(content)),
        "size_bytes": len(content),
    }
    return stored


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


async def _record_failure(ctx: _Ctx, failure: AppError) -> dict[str, Any]:
    """A typed non-governance failure is a durable FAILED outcome (doc 18 §11).

    REJECTED stays reserved for a governance denial (AL-11); a stale OCC token or a
    malformed request is a *failure*, so it is recorded with the SAME machine code
    the human line raises. ``details`` rides along so the Agent can plan a fix
    (which draft version to reload, which compiler blocker to resolve)."""
    response: dict[str, Any] = {
        "status": "failed",
        "failure_code": failure.code,
        "failure_reason": failure.message,
        "details": list(failure.details or []),
    }
    ctx.call.status = ToolCallStatus.FAILED
    ctx.call.failure_code = failure.code
    ctx.call.failure_message = failure.message
    ctx.call.response_ref = response
    await _emit_event(
        ctx.session,
        ctx.actor,
        "tool_call_failed",
        task_id=ctx.task_id,
        payload={"tool": ctx.tool.value, "failure_code": failure.code},
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
    """`data_bundle.resolve` — pin Market + usage-scoped Research revisions into a
    context bundle. EXECUTION scope enforces the evidence-bundle gate:
    ``agent_research_only`` is blocked and never enters the manifest (AL-11).

    The research half passes through ``rd_jobs.admit_bundle_member`` — the SAME
    admission gate the human compilers use — so a soft-deleted root and a
    deprecated/revoked revision are refused a NEW bundle here exactly as they are
    there (GH #556; doc 12 §11, §14). The §9.3 usage-scope gate then runs with the
    Feature-Input-Only precondition RESOLVED FROM THE DATABASE; the caller's
    ``has_approved_feature_definition`` claim is not read (GH #557; doc 12 §2,
    §9.2 "must not rely on a dropdown selection or a browser-held record").

    Honest boundary: the market half still checks existence only. This docstring
    used to claim "approved Market" — it does not enforce that, and the ACTIVE-root
    + APPROVED-revision gate for a pinned market revision stays tracked on #556.
    """
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
        # ``for_execution=False`` on both scopes: this tool pins a CONTEXT manifest,
        # not a BacktestEvidenceBundle, so it takes the lifecycle admission every
        # surface owes and applies the §9.3 scope gate itself below (see the gate's
        # docstring). Refusals are translated into the one rejection taxonomy this
        # surface has always used, because a typed non-``ForbiddenError`` (the
        # NotFoundError for a soft-deleted root, the FieldMeaningInsufficient for a
        # missing feature definition) would otherwise escape the gateway —
        # ``data_bundle.resolve`` is not a durable-FAILED family, so nothing would
        # be recorded and the Agent would get a crash instead of a blocker to read
        # (doc 18 §9.2 "on governance denial: REJECTED, never a crash").
        try:
            research_rev = await rd_jobs.admit_bundle_member(
                ctx.session, ctx.actor, revision_id, for_execution=False
            )
            scope = research_rev.usage_scope
            if scope is None:
                raise ResearchInputBlockedError(
                    f"Research revision '{revision_id}' is not resolvable for a data bundle."
                )
            if execution:
                # Real evidence-bundle gate: agent_research_only -> UsageScopeForbidden;
                # feature_input_only requires an approved feature definition, and
                # whether one exists is a SERVER fact (doc 12 §9.3, GH #557).
                ensure_allows_evidence_bundle(
                    scope,
                    has_approved_feature_definition=(
                        await rd_jobs.has_approved_feature_definition(
                            ctx.session, research_rev.entity_id
                        )
                    ),
                )
            elif not allows_agent_research(scope):
                raise ResearchInputBlockedError(
                    f"Research revision '{revision_id}' scope forbids Agent research use."
                )
        except ResearchInputBlockedError:
            raise
        except AppError as denial:
            raise ResearchInputBlockedError(denial.message) from denial
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
    board; provenance/audit are retained; restore/purge are Admin-only (AL-16).

    K-06: delegated to the shared ``commands/agent_artifact`` command so the SAME
    transaction also writes the canonical Trash Entry (doc 20 §10, §11) — without
    it the artifact left the board but never reached the Admin Trash surface."""
    artifact_id = str(ctx.request.get("artifact_id", ""))
    outcome = await artifact_cmd.soft_delete_hypothesis_artifact(
        ctx.session, ctx.actor, artifact_id=artifact_id
    )
    if outcome["deletion_state"] != DeletionState.SOFT_DELETED.value:
        # Already soft-deleted / purge-pending / purged: idempotent no-op, and the
        # existing Trash Entry (never a duplicate) stands (doc 20 §14).
        return _ToolOutcome(response=outcome)
    return _ToolOutcome(response=outcome, artifact_output_ref=artifact_id)


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
        # doc 14 §12.2 requires the parent Agent task id on the check/admission
        # audit; this is the only surface that knows it.
        parent_agent_task_id=ctx.task_id,
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
        parent_agent_task_id=ctx.task_id,
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


# --------------------------------------------------------------------------- #
# S4 — Portfolio / Equity Allocation parity (doc 13 §9)                        #
#                                                                             #
# Each handler forwards to the SAME application command/query a human calls;   #
# ownership (``ensure_can_edit``/``ensure_can_view``), optimistic concurrency  #
# (``expected_row_version``), idempotency and audit all live INSIDE those      #
# functions — no gateway-side business logic is added. An ownership violation  #
# raises ``AccessDeniedError`` (a ``ForbiddenError``) and lands as a recorded  #
# REJECTED denial, identical to the human 403 (AL-11, doc 13 §14#17).          #
# --------------------------------------------------------------------------- #


async def _handle_allocation_get_draft(ctx: _Ctx) -> _ToolOutcome:
    """`portfolio_allocation.get_draft` — read the composition's draft projection,
    row_version and candidate items through the same read model (doc 13 §9)."""
    from entropia.application.queries.allocation_plan import get_allocation_draft

    result = await get_allocation_draft(
        ctx.session, ctx.actor, composition_id=str(ctx.request.get("composition_id", ""))
    )
    return _ToolOutcome(response=result)


async def _handle_allocation_sync_preview(ctx: _Ctx) -> _ToolOutcome:
    """`portfolio_allocation.sync_preview` — non-destructive Sync-From-Mainboard
    merge preview (doc 13 §9, §10.2 Flow D). A preview never mutates."""
    from entropia.application.queries.allocation_plan import sync_preview

    result = await sync_preview(
        ctx.session, ctx.actor, composition_id=str(ctx.request.get("composition_id", ""))
    )
    return _ToolOutcome(response=result)


async def _handle_allocation_upsert_draft(ctx: _Ctx) -> _ToolOutcome:
    """`portfolio_allocation.upsert_draft` — autosave the draft config on the
    Agent's OWN composition (doc 13 §9). ``expected_row_version`` is the live OCC
    token; a stale value is ALLOCATION_DRAFT_CONFLICT, never last-write-wins."""
    from entropia.application.commands.allocation_plan import upsert_allocation_draft

    request = ctx.request
    result = await upsert_allocation_draft(
        ctx.session,
        ctx.actor,
        composition_id=str(request.get("composition_id", "")),
        expected_row_version=request.get("expected_row_version"),
        enabled=bool(request.get("enabled", False)),
        initial_capital=request.get("initial_capital"),
        compounding_mode=request.get("compounding_mode"),
        reserve_cash_percent=request.get("reserve_cash_percent"),
        entries=request.get("entries"),
        idempotency_key=request.get("idempotency_key"),
    )
    return _ToolOutcome(
        response=result,
        artifact_output_ref=result.get("plan_id"),
        domain_events=[("allocation_draft_changed", {"plan_id": result.get("plan_id")})],
    )


async def _handle_allocation_validate(ctx: _Ctx) -> _ToolOutcome:
    """`portfolio_allocation.validate` — resolve blocker/warning/derived caps into
    an immutable validation report (doc 13 §9, §11.2). No revision or run."""
    from entropia.application.commands.allocation_plan import validate_allocation_draft

    result = await validate_allocation_draft(
        ctx.session, ctx.actor, composition_id=str(ctx.request.get("composition_id", ""))
    )
    return _ToolOutcome(response=result, artifact_output_ref=result.get("validation_report_id"))


async def _handle_allocation_create_revision(ctx: _Ctx) -> _ToolOutcome:
    """`portfolio_allocation.create_revision` — turn a validated, blocker-free
    enabled draft into an immutable plan revision (doc 13 §9, §8.5). Never mutates
    an active/completed run manifest — a new revision is a future snapshot only."""
    from entropia.application.commands.allocation_plan import create_allocation_revision

    request = ctx.request
    result = await create_allocation_revision(
        ctx.session,
        ctx.actor,
        composition_id=str(request.get("composition_id", "")),
        expected_row_version=request.get("expected_row_version"),
        idempotency_key=request.get("idempotency_key"),
    )
    return _ToolOutcome(
        response=result,
        artifact_output_ref=result.get("plan_revision_id"),
        domain_events=[
            ("allocation_revision_created", {"plan_revision_id": result.get("plan_revision_id")})
        ],
    )


# --------------------------------------------------------------------------- #
# S4 — Trade Log parity (doc 05 §11, TL-22)                                    #
# --------------------------------------------------------------------------- #


async def _handle_trade_log_upload_source(ctx: _Ctx) -> _ToolOutcome:
    """`trade_log.upload_source_asset` — store an immutable TXT/CSV source asset
    (doc 05 §11). Content-addressed dedup lives in the command. The bytes ride in
    ``content`` (bytes, or a UTF-8 string coerced here for a JSON-safe envelope).

    The F-03 byte gate runs HERE for the same reason its Trading Signal twin does:
    on the human plane it lives at the multipart route
    (``routes/trade_log.py`` -> ``validate_multipart_upload(file, require_csv_schema=True)``),
    and the Agent has no browser to go through. Without it this plane enforced only
    the command's extension+sniff gate — no size ceiling, no whole-document UTF-8
    check, no CSV header check — so the Agent could upload a file the page refuses.
    The sibling handler's docstring already stated the rule ("the Agent can never
    upload what a human cannot"); this handler was the one place it was not true.
    """
    from entropia.application.commands.trade_log import upload_source_asset
    from entropia.domain.importing.source_file import assert_source_bytes_admissible

    content = _require_source_content(ctx)
    # ``require_csv_schema=True`` mirrors routes/trade_log.py exactly.
    assert_source_bytes_admissible(content, require_csv_schema=True)
    result = await upload_source_asset(
        ctx.session,
        ctx.actor,
        content=content,
        content_type=_optional_text(ctx, "content_type"),
        original_filename=_optional_text(ctx, "original_filename"),
        draft_id=_optional_text(ctx, "draft_id"),
        idempotency_key=_optional_text(ctx, "idempotency_key"),
    )
    return _ToolOutcome(response=result, artifact_output_ref=result.get("source_asset_id"))


async def _handle_trade_log_request_import(ctx: _Ctx) -> _ToolOutcome:
    """`trade_log.request_import` — enqueue a durable import job on the data queue
    (doc 05 §11, CR-09). The Agent receives the structured job handle and may plan
    a remediation task; the worker parses/normalizes/validates."""
    from entropia.application.commands.trade_log import request_trade_log_import
    from entropia.application.jobs.data_queue import TRADE_LOG_IMPORT

    request = ctx.request
    result = await request_trade_log_import(
        ctx.session,
        ctx.actor,
        source_asset_id=str(request.get("source_asset_id", "")),
        instrument_id=str(request.get("instrument_id", "")),
        instrument_scope=request.get("instrument_scope"),
        source_timezone=str(request.get("source_timezone", "UTC")),
        import_mapping=request.get("import_mapping"),
        idempotency_key=request.get("idempotency_key"),
    )
    # The job's own ``status`` is namespaced so it never shadows the envelope's
    # terminal call ``status`` (doc 18 §9.2 envelope-wins rule).
    response = {**result, "import_status": result.get("status")}
    response.pop("status", None)
    # The job kind the post-commit broker hand-off routes on. Without it
    # ``pending_data_job_dispatch`` returns None and the admitted import sits QUEUED
    # forever: ``data`` is excluded from the scheduler's automatic redelivery sweep
    # because it is multi-actor, so ONLY an explicit Admin redelivery would have moved
    # it. The trading_signal family shipped this with its tools; trade_log predates
    # the hand-off and was left admitting work that could never start.
    response["import_job_kind"] = TRADE_LOG_IMPORT
    return _ToolOutcome(
        response=response,
        artifact_output_ref=result.get("job_id"),
        domain_events=[("trade_log_import_requested", {"job_id": result.get("job_id")})],
    )


async def _handle_trade_log_create(ctx: _Ctx) -> _ToolOutcome:
    """`trade_log.create` — Save (& Add): create the native Trade Log work object +
    immutable revision 1 and optionally attach it onto the Mainboard (doc 05 §11).
    Save != Ready PASS != Run."""
    from entropia.application.commands.trade_log import create_trade_log_and_attach

    request = ctx.request
    result = await create_trade_log_and_attach(
        ctx.session,
        ctx.actor,
        payload=dict(request.get("payload") or {}),
        workspace_id=request.get("workspace_id"),
        attach=bool(request.get("attach", True)),
        position_index=request.get("position_index"),
        idempotency_key=request.get("idempotency_key"),
    )
    return _ToolOutcome(
        response=result,
        artifact_output_ref=result.get("revision_id"),
        domain_events=[("trade_log_created", {"root_id": result.get("root_id")})],
    )


async def _handle_trade_log_create_revision(ctx: _Ctx) -> _ToolOutcome:
    """`trade_log.create_revision` — append an immutable Trade Log revision N+1 on
    the Agent's OWN root (doc 05 §11, Rule 10). ``expected_head_revision_id`` is the
    OCC token; the Mainboard item is NEVER auto-repinned."""
    from entropia.application.commands.trade_log import create_trade_log_revision

    request = ctx.request
    result = await create_trade_log_revision(
        ctx.session,
        ctx.actor,
        root_id=str(request.get("root_id", "")),
        payload=dict(request.get("payload") or {}),
        expected_head_revision_id=request.get("expected_head_revision_id"),
        idempotency_key=request.get("idempotency_key"),
    )
    return _ToolOutcome(
        response=result,
        artifact_output_ref=result.get("revision_id"),
        domain_events=[("trade_log_revision_created", {"root_id": result.get("root_id")})],
    )


# --------------------------------------------------------------------------- #
# S5 — Strategy draft/save parity (doc 02 §12 AT-21, §11 rule 20)              #
#                                                                             #
# Each handler forwards to the SAME application command/query a human calls.   #
# Ownership (``ensure_can_edit``/``ensure_can_view``), the ``expected_draft_    #
# row_version`` OCC token, ``Idempotency-Key`` (``run_idempotent``), the        #
# compiler verdict, audit + outbox and the Mainboard re-pin all live INSIDE     #
# those functions — the gateway adds NO business logic, only request-shape      #
# checking and the durable envelope. An ownership violation raises              #
# ``AccessDeniedError`` (a ``ForbiddenError``) -> recorded REJECTED, identical  #
# to the human 403; a stale OCC / compiler blocker -> recorded FAILED carrying  #
# the human line's own code.                                                   #
# --------------------------------------------------------------------------- #


def _require_text(ctx: _Ctx, field: str) -> str:
    """A required non-empty string id. Blank/absent/non-string fails CLOSED — the
    command line must never be called with a coerced ``"None"`` id."""
    value = ctx.request.get(field)
    if not isinstance(value, str) or not value.strip():
        raise AgentToolRequestInvalidError(
            f"'{field}' must be a non-empty string.",
            details=[{"field": field, "actual": type(value).__name__}],
            field_path=field,
        )
    return value.strip()


def _optional_text(ctx: _Ctx, field: str) -> str | None:
    value = ctx.request.get(field)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise AgentToolRequestInvalidError(
            f"'{field}' must be a non-empty string when supplied.",
            details=[{"field": field, "actual": type(value).__name__}],
            field_path=field,
        )
    return value.strip()


def _require_int(ctx: _Ctx, field: str) -> int:
    """A required integer OCC token. ``bool`` is rejected explicitly (it is an
    ``int`` subclass in Python, and ``True`` must never read as row_version 1)."""
    value = ctx.request.get(field)
    if isinstance(value, bool) or not isinstance(value, int):
        raise AgentToolRequestInvalidError(
            f"'{field}' must be an integer version token.",
            details=[{"field": field, "actual": type(value).__name__}],
            field_path=field,
        )
    return value


def _optional_mapping(ctx: _Ctx, field: str) -> dict[str, Any] | None:
    value = ctx.request.get(field)
    if value is None:
        return None
    if not isinstance(value, dict):
        raise AgentToolRequestInvalidError(
            f"'{field}' must be an object when supplied.",
            details=[{"field": field, "actual": type(value).__name__}],
            field_path=field,
        )
    return dict(value)


def _require_mapping(ctx: _Ctx, field: str) -> dict[str, Any]:
    """A required object. Absent fails as loudly as malformed — a config payload
    defaulted to ``{}`` would reach the compiler as "every field missing" and report
    a validation storm instead of the one real defect (the field was never sent)."""
    value = ctx.request.get(field)
    if not isinstance(value, dict):
        raise AgentToolRequestInvalidError(
            f"'{field}' must be an object.",
            details=[{"field": field, "actual": type(value).__name__}],
            field_path=field,
        )
    return dict(value)


def _optional_int(ctx: _Ctx, field: str) -> int | None:
    """An optional integer. ``bool`` is rejected explicitly (it is an ``int``
    subclass, and ``True`` must never read as position 1)."""
    value = ctx.request.get(field)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise AgentToolRequestInvalidError(
            f"'{field}' must be an integer when supplied.",
            details=[{"field": field, "actual": type(value).__name__}],
            field_path=field,
        )
    return value


def _optional_string_mapping(ctx: _Ctx, field: str) -> dict[str, str] | None:
    """An optional ``{str: str}`` map (the import column mapping, doc 04 §5.1).

    Values are checked, not coerced: ``str(None)`` would hand the parser a column
    literally named ``"None"`` and the file would fail far away from the real cause.
    """
    value = _optional_mapping(ctx, field)
    if value is None:
        return None
    bad = sorted(key for key, item in value.items() if not isinstance(item, str))
    if bad:
        raise AgentToolRequestInvalidError(
            f"'{field}' must map every key to a string column name.",
            details=[{"field": field, "actual": bad}],
            field_path=field,
        )
    return {str(key): item for key, item in value.items()}


async def _handle_strategy_get_draft(ctx: _Ctx) -> _ToolOutcome:
    """`strategy.get_draft` — read the Agent's OWN draft (payload, ``row_version``
    OCC token, provenance) through the same read model a human's editor uses
    (doc 02 §7). A foreign private draft is a recorded REJECTED denial."""
    from entropia.application.queries.strategy import get_strategy_draft

    result = await get_strategy_draft(ctx.session, ctx.actor, _require_text(ctx, "draft_id"))
    return _ToolOutcome(response=result)


async def _handle_strategy_create_draft(ctx: _Ctx) -> _ToolOutcome:
    """`strategy.create_draft` — create an Agent-OWNED strategy root + draft (doc 02
    §7, AT-01). No revision exists yet, so the draft can never enter Ready Check or
    a Run; nothing is attached to any Mainboard (the tool has no workspace input)."""
    from entropia.application.commands.strategy_draft import create_strategy_draft

    result = await create_strategy_draft(
        ctx.session,
        ctx.actor,
        display_name=_require_text(ctx, "display_name"),
        rationale_family_id=_optional_text(ctx, "rationale_family_id"),
        initial_payload=_optional_mapping(ctx, "initial_payload"),
        idempotency_key=_optional_text(ctx, "idempotency_key"),
    )
    return _ToolOutcome(
        response=result,
        artifact_output_ref=result.get("strategy_root_id"),
        domain_events=[
            (
                "strategy_draft_created",
                {
                    "strategy_root_id": result.get("strategy_root_id"),
                    "draft_id": result.get("draft_id"),
                },
            )
        ],
    )


async def _handle_strategy_patch_draft(ctx: _Ctx) -> _ToolOutcome:
    """`strategy.patch_draft` — apply a full ``payload`` replacement or a shallow
    ``patch`` merge on the Agent's OWN draft (doc 02 §7, AT-19).
    ``expected_draft_row_version`` is MANDATORY: a stale token is
    STRATEGY_DRAFT_CONFLICT, recorded, never last-write-wins."""
    from entropia.application.commands.strategy_draft import patch_strategy_draft

    result = await patch_strategy_draft(
        ctx.session,
        ctx.actor,
        draft_id=_require_text(ctx, "draft_id"),
        expected_draft_row_version=_require_int(ctx, "expected_draft_row_version"),
        payload=_optional_mapping(ctx, "payload"),
        patch=_optional_mapping(ctx, "patch"),
        idempotency_key=_optional_text(ctx, "idempotency_key"),
    )
    return _ToolOutcome(
        response=result,
        artifact_output_ref=result.get("draft_id"),
        domain_events=[("strategy_draft_patched", {"draft_id": result.get("draft_id")})],
    )


async def _handle_strategy_validate_draft(ctx: _Ctx) -> _ToolOutcome:
    """`strategy.validate_draft` — the compiler's verdict on the draft WITHOUT a
    revision (doc 02 §8.4). The truth comes from ``validate_strategy_config``, the
    same function the human Save path runs; the gateway never re-implements it."""
    from entropia.application.commands.strategy_draft import validate_strategy_draft

    result = await validate_strategy_draft(
        ctx.session, ctx.actor, draft_id=_require_text(ctx, "draft_id")
    )
    return _ToolOutcome(response=result)


async def _handle_strategy_save_revision(ctx: _Ctx) -> _ToolOutcome:
    """`strategy.save_revision` — Save: the immutable ``strategy_revision`` with its
    ``config_hash`` + pinned references, the mirror work-object revision, the
    Mainboard re-pin of items already on this root, audit + outbox (doc 02 §7.1,
    AT-02, AT-20). Save is never a Ready PASS and never a Run — the response
    reports ``ready_state="STALE"`` exactly as the human line does."""
    from entropia.application.commands.strategy_draft import save_strategy_revision

    result = await save_strategy_revision(
        ctx.session,
        ctx.actor,
        draft_id=_require_text(ctx, "draft_id"),
        expected_draft_row_version=_require_int(ctx, "expected_draft_row_version"),
        idempotency_key=_optional_text(ctx, "idempotency_key"),
    )
    return _ToolOutcome(
        response=result,
        artifact_output_ref=result.get("strategy_revision_id"),
        domain_events=[
            (
                "strategy_revision_created",
                {
                    "strategy_root_id": result.get("strategy_root_id"),
                    "strategy_revision_id": result.get("strategy_revision_id"),
                    "config_hash": result.get("config_hash"),
                },
            )
        ],
    )


# --------------------------------------------------------------------------- #
# S6 — Trading Signal parity (doc 04 §10, §15 TS-20; doc 03 §14 AOS-20)        #
#                                                                             #
# Each handler forwards to the SAME command/query the page calls, so the file  #
# type gate, content-addressed dedup, timezone/instrument resolution, the      #
# §9.2 config compiler, the ``expected_head_revision_id`` OCC token,           #
# Idempotency-Key (``run_idempotent``), the available_time pin, audit +        #
# outbox and the Mainboard attach all live INSIDE those functions. The gateway #
# adds NO business logic — only request-shape checking, the F-03 byte gate the #
# browser plane runs at its route, and the durable envelope.                   #
#                                                                             #
# A Trading Signal is a native external WORK OBJECT and is NEVER a Package     #
# (CR-01): no handler here names ``PackageKind``, and the Mainboard            #
# ``item_kind`` is derived server-side from the root inside                    #
# ``attach_mainboard_item``.                                                   #
# --------------------------------------------------------------------------- #


def _require_source_content(ctx: _Ctx) -> bytes:
    """The raw source bytes an upload tool carried.

    Accepts ``bytes`` or a UTF-8 ``str`` (a JSON envelope cannot hold bytes).
    Anything else fails CLOSED — notably ``bytes(5)`` would silently produce five NUL
    bytes and hand the command a file the caller never meant to store.
    """
    raw = ctx.request.get("content")
    if isinstance(raw, str):
        return raw.encode("utf-8")
    if isinstance(raw, bytes | bytearray):
        return bytes(raw)
    raise AgentToolRequestInvalidError(
        "'content' must be raw bytes or a UTF-8 string.",
        details=[{"field": "content", "actual": type(raw).__name__}],
        field_path="content",
    )


async def _handle_trading_signal_upload_source(ctx: _Ctx) -> _ToolOutcome:
    """`trading_signal.upload_source_asset` — store an immutable TXT/CSV signal-event
    source asset (doc 04 §7, §10 ``UploadSourceAsset``).

    The command supplies the fail-closed extension/type gate, the sha256 content
    address and the per-owner dedup. What it does NOT supply is the F-03 byte gate
    (size / whole-document UTF-8 / CSV header): on the human plane that runs at the
    multipart route, which this caller has no browser to go through. Running it here
    is what makes "the same rules" true instead of aspirational — an oversized or
    headerless file is refused with the SAME machine code the page returns
    (``UPLOAD_TOO_LARGE`` / ``UPLOAD_SCHEMA_INVALID``), off ONE shared ceiling, so the
    Agent can never upload what a human cannot.
    """
    from entropia.application.commands.trading_signal import upload_source_asset
    from entropia.domain.importing.source_file import assert_source_bytes_admissible

    content = _require_source_content(ctx)
    # ``require_csv_schema=True`` mirrors the Trading Signal route exactly.
    assert_source_bytes_admissible(content, require_csv_schema=True)
    result = await upload_source_asset(
        ctx.session,
        ctx.actor,
        content=content,
        content_type=_optional_text(ctx, "content_type"),
        original_filename=_optional_text(ctx, "original_filename"),
        draft_id=_optional_text(ctx, "draft_id"),
        idempotency_key=_optional_text(ctx, "idempotency_key"),
    )
    return _ToolOutcome(response=result, artifact_output_ref=result.get("source_asset_id"))


async def _handle_trading_signal_request_import(ctx: _Ctx) -> _ToolOutcome:
    """`trading_signal.request_import` — admit a durable import onto the ``data``
    queue (doc 04 §7; §9 makes the import job independent of browser lifetime; §10
    backs this row with ``RequestTradingSignalImport``).

    A SUCCEEDED tool call here means the work was ADMITTED, not that it finished: the
    worker still has to parse/map/validate and write the normalized revision. The
    job's own lifecycle is therefore reported as ``import_status``, so it can never
    shadow the envelope's terminal call ``status`` (doc 18 §9.2 envelope-wins rule)
    and can never be misread as "the import succeeded". Completion is observed only
    through ``trading_signal.get_import_report``.
    """
    from entropia.application.commands.trading_signal import request_trading_signal_import
    from entropia.application.jobs.data_queue import TRADING_SIGNAL_IMPORT

    result = await request_trading_signal_import(
        ctx.session,
        ctx.actor,
        source_asset_id=_require_text(ctx, "source_asset_id"),
        instrument_id=_require_text(ctx, "instrument_id"),
        instrument_scope=_optional_mapping(ctx, "instrument_scope"),
        source_timezone=_optional_text(ctx, "source_timezone") or "UTC",
        import_mapping=_optional_string_mapping(ctx, "import_mapping"),
        idempotency_key=_optional_text(ctx, "idempotency_key"),
    )
    response = {**result, "import_status": result.get("status")}
    response.pop("status", None)
    # The job kind the post-commit broker hand-off routes on (see
    # ``pending_data_job_dispatch``): ``data`` is multi-actor, so the dispatcher
    # cannot pick the actor from the queue name alone.
    response["import_job_kind"] = TRADING_SIGNAL_IMPORT
    return _ToolOutcome(
        response=response,
        artifact_output_ref=result.get("job_id"),
        domain_events=[("trading_signal_import_requested", {"job_id": result.get("job_id")})],
    )


async def _handle_trading_signal_get_import_report(ctx: _Ctx) -> _ToolOutcome:
    """`trading_signal.get_import_report` — the durable import status + accepted/
    skipped counts + skipped-row evidence (doc 04 §10 ``GetImportReport``).

    This is the Agent's validation surface: it receives the structured blockers the
    page shows and does not bypass availability/data policy (doc 04 §10). The report's
    own lifecycle is namespaced to ``import_status`` for the same envelope-wins reason
    as the admission — and note it legitimately changes vocabulary mid-flight (the
    ``jobs`` status while the worker runs, the normalized revision's status once it
    lands), which is precisely why it must not be read as the call's status.
    """
    from entropia.application.queries.trading_signal import get_import_report

    result = await get_import_report(ctx.session, ctx.actor, job_id=_require_text(ctx, "job_id"))
    response = {**result, "import_status": result.get("status")}
    response.pop("status", None)
    return _ToolOutcome(response=response)


async def _handle_trading_signal_create(ctx: _Ctx) -> _ToolOutcome:
    """`trading_signal.create` — Save (& Add): the native Trading Signal work object +
    immutable revision 1, optionally attached (doc 04 §8.1, §10).

    ``available_time`` is pinned from the normalized import's earliest accepted event
    INSIDE the command — the gateway never computes or supplies it, so the lookahead
    guard doc 04 §5 makes mandatory cannot be weakened from this plane. Save is never
    a Ready PASS and never a Run: the response reports ``ready_state="STALE"`` exactly
    as the human line does (doc 04 §15 TS-21).

    Attach containment (doc 04 §10: "Agent attaches to its own agent research
    workspace, not automatically to a human Default Mainboard"): with no
    ``workspace_id`` the command resolves the CALLER's own default workspace, which
    for an Agent principal is its ``agent_research`` board — a human's board is never
    reachable by omission. An explicitly named foreign workspace is refused by
    ``attach_mainboard_item``'s owner check and a foreign private root by its
    ``ensure_can_view``; both surface here as a recorded REJECTED denial.
    """
    from entropia.application.commands.trading_signal import create_trading_signal_and_attach

    attach = ctx.request.get("attach", True)
    if not isinstance(attach, bool):
        raise AgentToolRequestInvalidError(
            "'attach' must be a boolean.",
            details=[{"field": "attach", "actual": type(attach).__name__}],
            field_path="attach",
        )
    result = await create_trading_signal_and_attach(
        ctx.session,
        ctx.actor,
        payload=_require_mapping(ctx, "payload"),
        workspace_id=_optional_text(ctx, "workspace_id"),
        attach=attach,
        position_index=_optional_int(ctx, "position_index"),
        idempotency_key=_optional_text(ctx, "idempotency_key"),
    )
    return _ToolOutcome(
        response=result,
        artifact_output_ref=result.get("revision_id"),
        domain_events=[("trading_signal_created", {"root_id": result.get("root_id")})],
    )


async def _handle_trading_signal_create_revision(ctx: _Ctx) -> _ToolOutcome:
    """`trading_signal.create_revision` — append an immutable revision N+1 on the
    Agent's OWN root (doc 04 §8.2 rule 9, §10 ``CreateTradingSignalRevision``).

    ``expected_head_revision_id`` is the OCC token — a revision id, not a row_version;
    this surface is deliberately NOT a dual-token op, so nothing is reconciled here. A
    stale token is ``WORK_OBJECT_REVISION_CONFLICT``, recorded, never last-write-wins.
    The prior revision is never mutated and the Mainboard item is NEVER auto-repinned:
    ``auto_repinned: False`` rides in the response and moving the pin stays the
    explicit "Use This Revision" action.
    """
    from entropia.application.commands.trading_signal import create_trading_signal_revision

    result = await create_trading_signal_revision(
        ctx.session,
        ctx.actor,
        root_id=_require_text(ctx, "root_id"),
        payload=_require_mapping(ctx, "payload"),
        expected_head_revision_id=_optional_text(ctx, "expected_head_revision_id"),
        idempotency_key=_optional_text(ctx, "idempotency_key"),
    )
    return _ToolOutcome(
        response=result,
        artifact_output_ref=result.get("revision_id"),
        domain_events=[("trading_signal_revision_created", {"root_id": result.get("root_id")})],
    )


def pending_data_job_dispatch(response: dict[str, Any]) -> tuple[str, str] | None:
    """The ``(job_kind, job_id)`` a tool response ADMITTED onto the ``data`` queue.

    The worker calls this AFTER its commit and hands the pair to the matching actor —
    the step the human page performs in its own route (``routes/trading_signal.py``
    -> ``send_job(run_trading_signal_import, ...)``). Without it an agent-admitted
    import would sit QUEUED indefinitely: the ``data`` queue is deliberately excluded
    from the scheduler's automatic redelivery sweep (``ACTOR_BY_QUEUE``) because the
    queue is multi-actor, so ONLY an explicit Admin redelivery would ever have moved
    it. A tool call reporting ``succeeded`` while its durable work could never start
    is exactly the silent-fallback shape this system forbids.

    Returns ``None`` for a REPLAY, and the reason is admission, not protection: a
    redelivered tool call admitted no new work, so there is no newly-queued job for
    this step to hand over. The envelope being replayed describes a job the original
    delivery already dispatched.

    This docstring used to justify the same ``None`` by asserting that the import
    bodies had no terminal-state guard. That premise expired when the shared guard
    landed — the agent-admitted import bodies now open with
    ``jobs/delivery.py::claim_job_for_delivery``, like every other durable body that
    does not hold a domain-row lock of its own. Do not restate that module's
    coverage here; its own docstring is the authority for which bodies claim.
    """
    if response.get("replayed"):
        return None
    if response.get("status") != str(ToolCallStatus.SUCCEEDED):
        return None
    job_kind = response.get("import_job_kind")
    job_id = response.get("job_id")
    if not isinstance(job_kind, str) or not isinstance(job_id, str):
        return None
    return job_kind, job_id


# Tools whose typed non-governance failures are recorded as a durable FAILED call
# instead of propagating (see ``dispatch_tool_call``). The S4 families keep their
# landed propagate-to-caller contract, which their acceptance tests pin.
_DURABLE_FAILURE_TOOLS: frozenset[ToolName] = frozenset(
    {
        ToolName.STRATEGY_GET_DRAFT,
        ToolName.STRATEGY_CREATE_DRAFT,
        ToolName.STRATEGY_PATCH_DRAFT,
        ToolName.STRATEGY_VALIDATE_DRAFT,
        ToolName.STRATEGY_SAVE_REVISION,
        # The signal family joins the durable-FAILED contract rather than the S4
        # propagate one: every one of its refusals (oversize file, unmapped events,
        # import not ready, stale OCC) is DETERMINISTIC, so letting one escape into
        # the worker's rollback would burn three dramatiq retries and leave the Agent
        # no tool-call row to read the blocker from. Recording it is what makes doc 04
        # §10's "Agent receives structured blockers/warnings" true.
        ToolName.TRADING_SIGNAL_UPLOAD_SOURCE,
        ToolName.TRADING_SIGNAL_REQUEST_IMPORT,
        ToolName.TRADING_SIGNAL_GET_IMPORT_REPORT,
        ToolName.TRADING_SIGNAL_CREATE,
        ToolName.TRADING_SIGNAL_CREATE_REVISION,
    }
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
    ToolName.ALLOCATION_GET_DRAFT: _handle_allocation_get_draft,
    ToolName.ALLOCATION_SYNC_PREVIEW: _handle_allocation_sync_preview,
    ToolName.ALLOCATION_UPSERT_DRAFT: _handle_allocation_upsert_draft,
    ToolName.ALLOCATION_VALIDATE: _handle_allocation_validate,
    ToolName.ALLOCATION_CREATE_REVISION: _handle_allocation_create_revision,
    ToolName.TRADE_LOG_UPLOAD_SOURCE: _handle_trade_log_upload_source,
    ToolName.TRADE_LOG_REQUEST_IMPORT: _handle_trade_log_request_import,
    ToolName.TRADE_LOG_CREATE: _handle_trade_log_create,
    ToolName.TRADE_LOG_CREATE_REVISION: _handle_trade_log_create_revision,
    ToolName.STRATEGY_GET_DRAFT: _handle_strategy_get_draft,
    ToolName.STRATEGY_CREATE_DRAFT: _handle_strategy_create_draft,
    ToolName.STRATEGY_PATCH_DRAFT: _handle_strategy_patch_draft,
    ToolName.STRATEGY_VALIDATE_DRAFT: _handle_strategy_validate_draft,
    ToolName.STRATEGY_SAVE_REVISION: _handle_strategy_save_revision,
    ToolName.TRADING_SIGNAL_UPLOAD_SOURCE: _handle_trading_signal_upload_source,
    ToolName.TRADING_SIGNAL_REQUEST_IMPORT: _handle_trading_signal_request_import,
    ToolName.TRADING_SIGNAL_GET_IMPORT_REPORT: _handle_trading_signal_get_import_report,
    ToolName.TRADING_SIGNAL_CREATE: _handle_trading_signal_create,
    ToolName.TRADING_SIGNAL_CREATE_REVISION: _handle_trading_signal_create_revision,
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


__all__ = [
    "dispatch_tool_call",
    "enqueue_tool_call",
    "pending_data_job_dispatch",
    "run_tool_job",
]
