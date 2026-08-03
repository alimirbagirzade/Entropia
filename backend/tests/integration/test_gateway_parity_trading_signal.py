"""Post-V1 S6 — Tool Gateway parity for the Trading Signal line (doc 04 §10, §15).

Auto-skips without PostgreSQL. Mirrors the S4/S5 parity pattern
(``test_gateway_parity_s4.py``, ``test_gateway_parity_strategy.py``): the Agent's
UI-less ``trading_signal.*`` tools delegate to the SAME application command/query
line a human uses, so the server truth on success and the machine code on refusal
must be IDENTICAL on both planes — with no browser, no human session, and no
human-board side effect.

This file closes the LITERAL clause of two acceptance rows that
``test_acceptance_agent_parity_gaps.py`` could previously only prove on the
domain-command axis, because no ``trading_signal.*`` ToolName member existed:

* doc 04 §15 **TS-20** — "Agent creates/imports/validates/saves/attaches a Signal
  via Tool Gateway without opening browser. Agent output ownership and
  task/checkpoint provenance are recorded; human board is not auto-mutated."
* doc 03 §14 **AOS-20** — "Agent creates/imports/attaches an external work object
  using Tool Gateway/domain commands without opening UI. Agent-created output
  owner/provenance is recorded; it is not auto-attached to a human board."

Covered:
- registry/scope contract: the five literals parse with exactly the declared scope
  table, none of them is EXECUTION, the doc-04 §10 INTENT spellings are refused,
  and all five are offered with no capability required;
- upload: valid/dedup parity with the human command, and the F-03 byte gate the
  browser plane runs at its route — oversize / non-UTF-8 / headerless / empty —
  refused here with the page's own code, plus malformed request shapes;
- payload containment: the durable tool-call envelope stores a content REFERENCE,
  never the raw bytes, including for the oversize call that is rejected;
- import: admission is not completion (``import_status`` namespaced), the admitted
  job is handed to its data actor, running/succeeded/failed reports, and a
  redelivery that replays without re-dispatching;
- create: a native work object and NOT a Package (CR-01), the exact normalized
  revision pinned, ``available_time`` taken from the import and distinct from
  ``event_time``, ``ready_state="STALE"``;
- containment: Agent output is owned by the Agent and lands on the Agent's own
  ``agent_research`` board; the human board is untouched; a foreign workspace and a
  foreign private root are recorded REJECTED denials;
- revision: ``expected_head_revision_id`` OCC, immutable N+1, and NO auto-repin;
- idempotency: gateway-key replay and domain-key replay, plus same-key/different-
  payload conflict;
- durability + history: enqueue -> run_tool_job writes audit + outbox + agent
  events and the calls appear in the Analysis Lab call history with provenance.
"""

from __future__ import annotations

import hashlib
from typing import Any

import pytest
from sqlalchemy import func, select

from entropia.application.commands import trading_signal as ts_cmd
from entropia.application.jobs import agent_tools
from entropia.application.jobs.data_queue import TRADING_SIGNAL_IMPORT
from entropia.application.jobs.trading_signal import run_import
from entropia.application.queries import agent_tool_gateway as tool_gateway_query
from entropia.application.queries import mainboard as mb_query
from entropia.domain.agent_lab.enums import (
    ALPHA_AGENT_ID,
    AgentTaskPriority,
    AgentTaskStatus,
    RuntimeMode,
    RuntimeStatus,
)
from entropia.domain.agent_lab.tool_gateway import (
    TOOL_ALLOWED_SCOPES,
    PolicyScope,
    ToolName,
    exposed_tool_names,
    parse_tool_name,
    queue_for_tool,
)
from entropia.domain.identity import Actor
from entropia.domain.importing.source_file import MAX_SOURCE_UPLOAD_BYTES
from entropia.domain.lifecycle.enums import JobStatus, PrincipalType, Role
from entropia.infrastructure.postgres.models import (
    AgentEvent,
    AgentRuntime,
    AgentToolCall,
    AuditEvent,
    Job,
    MainboardWorkingItem,
    NormalizedSignalEventRevision,
    OutboxEvent,
    PackageRoot,
    Principal,
    SourceAsset,
    WorkObjectRevision,
)
from entropia.infrastructure.postgres.repositories import agent_lab as al_repo
from entropia.infrastructure.s3 import datasets
from entropia.shared.errors import ToolPolicyScopeError

pytestmark = pytest.mark.integration

_HUMAN_PID = "user_1"
_AGENT_PID = "agent_alpha"

HUMAN = Actor(principal_id=_HUMAN_PID, principal_type=PrincipalType.HUMAN, role=Role.USER)
ADMIN = Actor(principal_id="admin_1", principal_type=PrincipalType.HUMAN, role=Role.ADMIN)
AGENT = Actor(
    principal_id=_AGENT_PID,
    principal_type=PrincipalType.AGENT,
    role=None,
    correlation_id="corr_s6_signal_parity",
)

_SIGNAL_TOOLS = (
    "trading_signal.upload_source_asset",
    "trading_signal.request_import",
    "trading_signal.get_import_report",
    "trading_signal.create",
    "trading_signal.create_revision",
)

_HEADER = "source_record_id,event_time,available_time,direction,signal_type"
# r1's availability lags its event by three minutes, so a revision that pinned
# ``event_time`` instead of ``available_time`` would be visibly wrong (10:00 vs 10:03).
_GOOD_CSV = "\n".join(
    [
        _HEADER,
        "r1,2024-05-01T10:00:00Z,2024-05-01T10:03:00Z,long,entry",
        "r2,2024-05-02T10:00:00Z,2024-05-02T10:01:00Z,sell,exit",
    ]
).encode("utf-8")
_EARLIEST_AVAILABLE = "2024-05-01T10:03:00"
_EARLIEST_EVENT = "2024-05-01T10:00:00"

# No ``available_time`` column at all -> the importer must refuse to invent one.
_NO_AVAILABILITY_CSV = "\n".join(
    [
        "source_record_id,event_time,direction,signal_type",
        "r1,2024-05-01T10:00:00Z,long,entry",
    ]
).encode("utf-8")


@pytest.fixture
def fake_object_store(monkeypatch) -> dict[str, bytes]:
    """In-process object storage so upload + worker read run without MinIO."""
    store: dict[str, bytes] = {}

    def _put(source_asset_id: str, data: bytes, *, content_type: str | None = None):
        digest = hashlib.sha256(data).hexdigest()
        key = f"signals/source/{source_asset_id}/{digest}"
        store[key] = data
        return key, digest

    def _get(object_key: str) -> bytes:
        return store[object_key]

    monkeypatch.setattr(datasets, "put_source_asset_bytes", _put)
    monkeypatch.setattr(datasets, "get_raw_bytes", _get)
    return store


async def _seed(session) -> None:
    for pid, ptype in ((_HUMAN_PID, PrincipalType.HUMAN), (_AGENT_PID, PrincipalType.AGENT)):
        if await session.get(Principal, pid) is None:
            session.add(Principal(principal_id=pid, principal_type=ptype))
    # The durable tool-call row FKs to agent_runtime(agent_id).
    if await session.get(AgentRuntime, ALPHA_AGENT_ID) is None:
        session.add(
            AgentRuntime(
                agent_id=ALPHA_AGENT_ID,
                mode=RuntimeMode.CONTINUOUS,
                status=RuntimeStatus.ACTIVE,
                row_version=1,
            )
        )
    await session.flush()


async def _count(session, model) -> int:
    return int((await session.execute(select(func.count()).select_from(model))).scalar_one())


async def _tool(session, name: str, scope: str, request: dict[str, Any], **kwargs: Any):
    """One gateway call + commit, exactly as the worker scope would."""
    result = await agent_tools.dispatch_tool_call(
        session, AGENT, tool_name=name, policy_scope=scope, request=request, **kwargs
    )
    await session.commit()
    return result


def _signal_payload(source_asset_id: str, normalized_revision_id: str) -> dict[str, Any]:
    return {
        "kind": "trading_signal",
        "identity": {"display_name": "Agent-imported signal source"},
        "source": {"provider_name": "Provider X", "source_kind": "file"},
        "instrument_scope": {"instrument_id": "inst_btcusdt", "display_symbol": "BTCUSDT"},
        "event_model": {"resolution_kind": "event_based", "base_timeframe": None},
        "classification": {"rationale_family_id": None},
        "data_quality": {"mode": "signal_events_only"},
        "time_policy": {"source_timezone": "UTC", "normalization_timezone": "UTC"},
        "price_policy": {"source": "suggested_signal_price", "fallback": None},
        "ohlcv_policy": {"use_mode": "use_if_supplied_and_needed"},
        "capital": {"independent_initial_capital": "10000"},
        "import_binding": {
            "source_asset_id": source_asset_id,
            "normalized_event_revision_id": normalized_revision_id,
        },
    }


async def _agent_import(session, *, content: bytes = _GOOD_CSV) -> dict[str, Any]:
    """upload -> request_import -> run worker -> report, ALL through the Gateway."""
    upload = await _tool(
        session,
        "trading_signal.upload_source_asset",
        "research",
        {"content": content.decode("utf-8"), "original_filename": "signals.csv"},
    )
    requested = await _tool(
        session,
        "trading_signal.request_import",
        "research",
        {"source_asset_id": upload["source_asset_id"], "instrument_id": "BTCUSDT"},
    )
    await run_import(session, requested["job_id"])
    await session.commit()
    report = await _tool(
        session,
        "trading_signal.get_import_report",
        "observation",
        {"job_id": requested["job_id"]},
    )
    return {"upload": upload, "requested": requested, "report": report}


async def _agent_signal(session) -> dict[str, Any]:
    """A saved + attached Agent-owned Trading Signal, entirely UI-lessly."""
    imported = await _agent_import(session)
    created = await _tool(
        session,
        "trading_signal.create",
        "proposal",
        {
            "payload": _signal_payload(
                imported["upload"]["source_asset_id"],
                imported["report"]["normalized_event_revision_id"],
            )
        },
    )
    return {**imported, "created": created}


# --------------------------------------------------------------------------- #
# Registry + scope contract (doc 18 §9.2, §10)                                 #
# --------------------------------------------------------------------------- #


def test_trading_signal_tool_names_parse_and_declare_their_scopes() -> None:
    """The five literals TS-20 needs exist, with exactly the declared scope table."""
    expected = {
        "trading_signal.upload_source_asset": {PolicyScope.RESEARCH},
        "trading_signal.request_import": {PolicyScope.RESEARCH},
        "trading_signal.get_import_report": {PolicyScope.OBSERVATION, PolicyScope.RESEARCH},
        "trading_signal.create": {PolicyScope.RESEARCH, PolicyScope.PROPOSAL},
        "trading_signal.create_revision": {PolicyScope.RESEARCH, PolicyScope.PROPOSAL},
    }
    for literal, scopes in expected.items():
        tool = parse_tool_name(literal)
        assert TOOL_ALLOWED_SCOPES[tool] == frozenset(scopes)
        # doc 04 §15 TS-21: selecting or saving a Signal never creates a Result, so
        # none of these may take the heavy execution plane away from real runs.
        assert PolicyScope.EXECUTION not in TOOL_ALLOWED_SCOPES[tool]
        assert queue_for_tool(tool) == "agent"


def test_the_doc04_intent_spellings_are_not_the_registry() -> None:
    """Doc 04 §10's parity table is written in agent-INTENT terms and names the real
    backing command in its own column; the registry follows the command (see the
    ToolName docstring). The rejected spellings are pinned so the adjudication is
    visible rather than remembered."""
    for rejected in (
        "trading_signal.import_events",
        "trading_signal.validate",
        "trading_signal.save_revision",
        "trading_signal.attach",
        "trading_signal.delete",
    ):
        with pytest.raises(ToolPolicyScopeError):
            parse_tool_name(rejected)


def test_the_new_literals_fit_the_persisted_column_so_no_migration_is_needed() -> None:
    """``agent_tool_call.tool_name`` is a plain ``String(64)``, not a DB enum, which is
    why this slice ships no migration. That is a claim about a column, so it is
    asserted rather than asserted-in-prose: the longest new literal
    (``trading_signal.upload_source_asset``) is 34 chars, comfortably inside 64."""
    for tool in ToolName:
        assert len(tool.value) <= 64, tool.value
    assert max(len(name) for name in _SIGNAL_TOOLS) == 34


def test_all_five_tools_are_offered_without_any_capability() -> None:
    """They are ungated (not CR-08 Future-Dev tools), so an Agent planning with no
    operational capability still sees the whole signal line."""
    offered = exposed_tool_names(frozenset())
    assert set(_SIGNAL_TOOLS) <= set(offered)


async def test_an_illegal_scope_is_a_recorded_denial(session) -> None:
    """A scope the tool does not declare never reaches the command line; it is a
    durable record, not a crash (doc 18 §11 AL-11)."""
    await _seed(session)
    result = await _tool(
        session,
        "trading_signal.create",
        "execution",
        {"payload": {}},
    )
    assert result["status"] == "rejected"
    assert await _count(session, WorkObjectRevision) == 0


# --------------------------------------------------------------------------- #
# Upload — same rules as the page, on a plane with no page                      #
# --------------------------------------------------------------------------- #


async def test_agent_upload_reaches_the_same_asset_as_the_human_line(
    session, fake_object_store
) -> None:
    """Same bytes -> same content address. The second upload of identical bytes by
    the same owner is the command's own dedup, not a duplicate asset."""
    await _seed(session)
    first = await _tool(
        session,
        "trading_signal.upload_source_asset",
        "research",
        {"content": _GOOD_CSV.decode("utf-8"), "original_filename": "signals.csv"},
    )
    assert first["status"] == "succeeded"
    assert first["deduplicated"] is False
    assert first["raw_asset_hash"] == hashlib.sha256(_GOOD_CSV).hexdigest()
    assert first["size_bytes"] == len(_GOOD_CSV)

    again = await _tool(
        session,
        "trading_signal.upload_source_asset",
        "research",
        {"content": _GOOD_CSV.decode("utf-8"), "original_filename": "signals.csv"},
    )
    assert again["deduplicated"] is True
    assert again["source_asset_id"] == first["source_asset_id"]
    assert await _count(session, SourceAsset) == 1

    # The human command line on the same bytes lands on its OWN asset (dedup is
    # per-owner) but at the identical content address — one storage rule, two callers.
    human = await ts_cmd.upload_source_asset(
        session, HUMAN, content=_GOOD_CSV, original_filename="signals.csv"
    )
    await session.commit()
    assert human["raw_asset_hash"] == first["raw_asset_hash"]


async def test_the_durable_envelope_stores_a_reference_not_the_raw_bytes(
    session, fake_object_store
) -> None:
    """Payload containment: the tool-call row is long-lived agent history, so it
    keeps the sha256 + size that NAME the asset, never a second copy of it."""
    await _seed(session)
    result = await _tool(
        session,
        "trading_signal.upload_source_asset",
        "research",
        {"content": _GOOD_CSV.decode("utf-8"), "original_filename": "signals.csv"},
    )
    call = await session.get(AgentToolCall, result["tool_call_id"])
    assert call is not None
    assert "content" not in call.request
    assert call.request["content_ref"] == {
        "sha256": hashlib.sha256(_GOOD_CSV).hexdigest(),
        "size_bytes": len(_GOOD_CSV),
    }
    # The reference is not a lossy substitute: it is the SAME address the asset is
    # stored under, so the evidence still resolves the exact bytes.
    assert call.request["content_ref"]["sha256"] == result["raw_asset_hash"]
    assert call.artifact_output_ref == result["source_asset_id"]


async def test_an_oversize_upload_is_refused_with_the_pages_own_code(
    session, fake_object_store
) -> None:
    """F-03 size gate. On the human plane this runs at the multipart route, which
    this caller never goes through — so an unbounded agent upload was the real
    exposure. One shared ceiling means the Agent cannot upload what a human cannot,
    and the rejected payload is NOT copied into the evidence row either."""
    await _seed(session)
    oversize = _HEADER.encode("utf-8") + b"\n" + b"x" * MAX_SOURCE_UPLOAD_BYTES
    result = await _tool(
        session,
        "trading_signal.upload_source_asset",
        "research",
        {"content": oversize.decode("utf-8"), "original_filename": "signals.csv"},
    )
    assert result["status"] == "failed"
    assert result["failure_code"] == "UPLOAD_TOO_LARGE"
    assert await _count(session, SourceAsset) == 0

    call = await session.get(AgentToolCall, result["tool_call_id"])
    assert call is not None
    assert "content" not in call.request
    assert call.request["content_ref"]["size_bytes"] == len(oversize)


@pytest.mark.parametrize(
    ("content", "filename", "code"),
    [
        # No header row at all -> the F-03 schema gate (route-only until now).
        (b"\n\n", "signals.csv", "UPLOAD_SCHEMA_INVALID"),
        # Not decodable as UTF-8 -> the F-03 ENCODING gate, which runs before the
        # command's type gate here exactly as it does on the route (the route calls
        # validate_multipart_upload first, then the command). Same order, same code.
        (b"source_record_id\n\xff\xfe\x00bad", "signals.csv", "UPLOAD_ENCODING_INVALID"),
        # Empty file -> the base ValidationError the route raises for the same input.
        (b"", "signals.csv", "VALIDATION_ERROR"),
        # The command's own fail-closed type gate still runs on this plane.
        (_GOOD_CSV, "signals.xlsx", "FILE_TYPE_NOT_ALLOWED"),
        (_GOOD_CSV, None, "FILE_TYPE_NOT_ALLOWED"),
    ],
)
async def test_invalid_uploads_fail_closed_with_a_recorded_code(
    session, fake_object_store, content: bytes, filename: str | None, code: str
) -> None:
    """Every refusal is a durable FAILED call carrying a machine code, never a crash
    and never a stored asset."""
    await _seed(session)
    request: dict[str, Any] = {"content": content}
    if filename is not None:
        request["original_filename"] = filename
    result = await _tool(session, "trading_signal.upload_source_asset", "research", request)
    assert result["status"] == "failed"
    assert result["failure_code"] == code
    assert await _count(session, SourceAsset) == 0


@pytest.mark.parametrize("bad_content", [None, 5, {"a": 1}, ["x"]])
async def test_malformed_content_shapes_fail_closed(
    session, fake_object_store, bad_content: Any
) -> None:
    """``bytes(5)`` would silently manufacture five NUL bytes, so a non-bytes,
    non-string ``content`` must be refused before the command sees it."""
    await _seed(session)
    result = await _tool(
        session,
        "trading_signal.upload_source_asset",
        "research",
        {"content": bad_content, "original_filename": "signals.csv"},
    )
    assert result["status"] == "failed"
    assert result["failure_code"] == "AGENT_TOOL_REQUEST_INVALID"
    assert await _count(session, SourceAsset) == 0


# --------------------------------------------------------------------------- #
# Import — admission is not completion (doc 04 §7, §9, CR-09)                   #
# --------------------------------------------------------------------------- #


async def test_import_admission_is_not_completion(session, fake_object_store) -> None:
    """A SUCCEEDED tool call means the durable job was ADMITTED. The job's own
    lifecycle is namespaced to ``import_status`` so it can never shadow — or be
    mistaken for — the envelope's terminal call status."""
    await _seed(session)
    upload = await _tool(
        session,
        "trading_signal.upload_source_asset",
        "research",
        {"content": _GOOD_CSV.decode("utf-8"), "original_filename": "signals.csv"},
    )
    requested = await _tool(
        session,
        "trading_signal.request_import",
        "research",
        {"source_asset_id": upload["source_asset_id"], "instrument_id": "BTCUSDT"},
    )
    assert requested["status"] == "succeeded"  # the CALL
    assert requested["import_status"] == "queued"  # the WORK
    assert requested["queue"] == "data"
    assert requested["import_job_kind"] == TRADING_SIGNAL_IMPORT

    job = await session.get(Job, requested["job_id"])
    assert job is not None and job.status == JobStatus.QUEUED
    # Nothing has been parsed yet — admission produced no normalized truth.
    assert await _count(session, NormalizedSignalEventRevision) == 0


async def test_the_gateway_hands_the_admitted_import_to_its_data_actor(
    session, fake_object_store, monkeypatch
) -> None:
    """The step the human page performs in its route. Without it the job would sit
    QUEUED forever: ``data`` is excluded from the scheduler's automatic redelivery
    sweep, so only an explicit Admin redelivery would ever have moved it."""
    from entropia.apps.worker import actors as worker_actors

    await _seed(session)
    upload = await _tool(
        session,
        "trading_signal.upload_source_asset",
        "research",
        {"content": _GOOD_CSV.decode("utf-8"), "original_filename": "signals.csv"},
    )
    requested = await _tool(
        session,
        "trading_signal.request_import",
        "research",
        {"source_asset_id": upload["source_asset_id"], "instrument_id": "BTCUSDT"},
    )

    assert agent_tools.pending_data_job_dispatch(requested) == (
        TRADING_SIGNAL_IMPORT,
        requested["job_id"],
    )

    sent: list[tuple[Any, str]] = []
    monkeypatch.setattr(
        "entropia.infrastructure.queues.enqueue.send_job",
        lambda actor, job_id: sent.append((actor, job_id)),
    )
    worker_actors._dispatch_pending_data_job(requested)
    assert sent == [(worker_actors.run_trading_signal_import, requested["job_id"])]

    # An upload response admitted no data job, so it dispatches nothing.
    assert agent_tools.pending_data_job_dispatch(upload) is None


async def test_the_worker_actually_performs_the_hand_off_after_it_commits(monkeypatch) -> None:
    """The wiring, not just the helper. The test above proves
    ``_dispatch_pending_data_job`` resolves the right actor; this proves
    ``_run_agent_tool`` CALLS it — and calls it only after the commit, which is the
    part that would silently rot if the line were dropped. A send that happened
    before the commit would hand the actor a job row it cannot yet read.
    """
    from entropia.application.jobs import agent_tools as tools_module
    from entropia.apps.worker import actors as worker_actors
    from entropia.infrastructure.postgres import engine as engine_module

    events: list[str] = []

    class _StubSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def commit(self):
            events.append("commit")

        async def rollback(self):  # pragma: no cover - not reached on the happy path
            events.append("rollback")

    async def _fake_run_tool_job(_session, _job_id):
        events.append("run")
        return {
            "status": "succeeded",
            "job_id": "job_admitted_1",
            "import_job_kind": TRADING_SIGNAL_IMPORT,
        }

    monkeypatch.setattr(engine_module, "get_session_factory", lambda: _StubSession)
    monkeypatch.setattr(tools_module, "run_tool_job", _fake_run_tool_job)
    monkeypatch.setattr(
        "entropia.infrastructure.queues.enqueue.send_job",
        lambda actor, job_id: events.append(f"send:{job_id}"),
    )

    await worker_actors._run_agent_tool("job_tool_1")

    assert events == ["run", "commit", "send:job_admitted_1"]


async def test_a_running_import_reports_running_and_no_normalized_truth_yet(
    session, fake_object_store
) -> None:
    """Mid-flight state. While the worker holds the job the report must say so and
    must NOT present a normalized revision — the Agent has to be able to tell "still
    working" apart from "finished", which is the whole reason the field is namespaced."""
    await _seed(session)
    upload = await _tool(
        session,
        "trading_signal.upload_source_asset",
        "research",
        {"content": _GOOD_CSV.decode("utf-8"), "original_filename": "signals.csv"},
    )
    requested = await _tool(
        session,
        "trading_signal.request_import",
        "research",
        {"source_asset_id": upload["source_asset_id"], "instrument_id": "BTCUSDT"},
    )
    job = await session.get(Job, requested["job_id"])
    assert job is not None
    job.status = JobStatus.RUNNING
    await session.commit()

    report = await _tool(
        session,
        "trading_signal.get_import_report",
        "observation",
        {"job_id": requested["job_id"]},
    )
    assert report["status"] == "succeeded"  # reading it worked
    assert report["import_status"] == "running"  # the work has not
    assert report["normalized_event_revision_id"] is None
    assert report["accepted_count"] == 0


async def test_import_success_is_observed_through_the_report_tool(
    session, fake_object_store
) -> None:
    """doc 04 §10 ``GetImportReport``: the Agent reads the same structured report the
    page shows, with the same counts and the same normalized revision id."""
    await _seed(session)
    imported = await _agent_import(session)
    report = imported["report"]
    assert report["status"] == "succeeded"  # the CALL
    assert report["import_status"] == "succeeded"  # the IMPORT
    assert report["accepted_count"] == 2
    assert report["skipped_count"] == 0
    assert report["normalized_event_revision_id"] is not None
    assert await _count(session, NormalizedSignalEventRevision) == 1


async def test_a_failed_import_reports_blockers_instead_of_inventing_availability(
    session, fake_object_store
) -> None:
    """doc 04 §5 makes ``available_time`` mandatory and doc 04 §15 TS-05 forbids
    inferring it. A file without the column must fail the import and must not become
    a saveable Signal — the Agent gets the structured blocker, not a silent default."""
    await _seed(session)
    imported = await _agent_import(session, content=_NO_AVAILABILITY_CSV)
    report = imported["report"]
    assert report["status"] == "succeeded"  # reading the report succeeded
    assert report["import_status"] == "failed"  # the import did not
    assert report["accepted_count"] == 0

    created = await _tool(
        session,
        "trading_signal.create",
        "proposal",
        {
            "payload": _signal_payload(
                imported["upload"]["source_asset_id"],
                report["normalized_event_revision_id"],
            )
        },
    )
    assert created["status"] == "failed"
    assert created["failure_code"] is not None
    assert await _count(session, WorkObjectRevision) == 0


async def test_redelivery_replays_and_never_re_dispatches_the_import(
    session, fake_object_store
) -> None:
    """At-least-once redelivery (AL-14). The replay returns the recorded outcome and
    admits nothing new — and because the import job body has NO terminal-state guard,
    re-sending it would parse the file twice and write a second normalized revision,
    so the replay must dispatch nothing."""
    await _seed(session)
    upload = await _tool(
        session,
        "trading_signal.upload_source_asset",
        "research",
        {"content": _GOOD_CSV.decode("utf-8"), "original_filename": "signals.csv"},
    )
    first = await _tool(
        session,
        "trading_signal.request_import",
        "research",
        {"source_asset_id": upload["source_asset_id"], "instrument_id": "BTCUSDT"},
        idempotency_key="ts-import-1",
    )
    replay = await _tool(
        session,
        "trading_signal.request_import",
        "research",
        {"source_asset_id": upload["source_asset_id"], "instrument_id": "BTCUSDT"},
        idempotency_key="ts-import-1",
    )
    assert replay["replayed"] is True
    assert replay["job_id"] == first["job_id"]
    assert replay["tool_call_id"] == first["tool_call_id"]
    assert agent_tools.pending_data_job_dispatch(replay) is None

    data_jobs = (
        await session.execute(select(func.count()).select_from(Job).where(Job.queue == "data"))
    ).scalar_one()
    assert data_jobs == 1


# --------------------------------------------------------------------------- #
# TS-20 / AOS-20 — the whole journey, on the Gateway, with no browser           #
# --------------------------------------------------------------------------- #


async def test_the_full_signal_journey_runs_end_to_end_through_the_gateway(
    session, fake_object_store
) -> None:
    """TS-20's literal sentence, walked in order and asserted at every step:
    "Agent creates/imports/validates/saves/attaches a Signal via Tool Gateway
    without opening browser."

    Five tool calls, no HTTP request, no human session, no browser — and each one is
    a durable SUCCEEDED row, so the journey is auditable rather than merely possible.
    """
    await _seed(session)

    # 1. imports — the immutable source asset.
    upload = await _tool(
        session,
        "trading_signal.upload_source_asset",
        "research",
        {"content": _GOOD_CSV.decode("utf-8"), "original_filename": "signals.csv"},
    )
    assert upload["status"] == "succeeded"

    # 2. imports — the durable job, admitted onto the data queue.
    requested = await _tool(
        session,
        "trading_signal.request_import",
        "research",
        {"source_asset_id": upload["source_asset_id"], "instrument_id": "BTCUSDT"},
    )
    assert requested["import_status"] == "queued"
    await run_import(session, requested["job_id"])
    await session.commit()

    # 3. validates — the structured import report is the Agent's blocker surface.
    report = await _tool(
        session,
        "trading_signal.get_import_report",
        "observation",
        {"job_id": requested["job_id"]},
    )
    assert report["import_status"] == "succeeded"
    assert report["accepted_count"] == 2

    # 4. creates + attaches — the native work object, revision 1, on the Agent's board.
    created = await _tool(
        session,
        "trading_signal.create",
        "proposal",
        {
            "payload": _signal_payload(
                upload["source_asset_id"], report["normalized_event_revision_id"]
            )
        },
    )
    assert created["object_kind"] == "trading_signal"
    assert created["revision_no"] == 1
    assert created["attached"] is True

    # 5. saves — an immutable revision 2 under OCC, with no auto-repin.
    revised = await _tool(
        session,
        "trading_signal.create_revision",
        "proposal",
        {
            "root_id": created["root_id"],
            "payload": _signal_payload(
                upload["source_asset_id"], report["normalized_event_revision_id"]
            ),
            "expected_head_revision_id": created["revision_id"],
        },
    )
    assert revised["revision_no"] == 2
    assert revised["auto_repinned"] is False

    # Every step is durable evidence: five SUCCEEDED tool calls, one per literal.
    calls = (
        (
            await session.execute(
                select(AgentToolCall.tool_name, AgentToolCall.status).order_by(
                    AgentToolCall.created_at
                )
            )
        )
        .tuples()
        .all()
    )
    assert [name for name, _ in calls] == list(_SIGNAL_TOOLS)
    assert {str(status) for _, status in calls} == {"succeeded"}


# --------------------------------------------------------------------------- #
# Create — a native work object, never a Package (CR-01)                        #
# --------------------------------------------------------------------------- #


async def test_create_produces_a_work_object_and_never_a_package(
    session, fake_object_store
) -> None:
    """CR-01: "Trading Signal ve Trade Log package değildir." The Gateway path must
    not be the one that quietly reclassifies it. Save is also never a Ready PASS
    (doc 04 §15 TS-21)."""
    await _seed(session)
    saved = (await _agent_signal(session))["created"]

    assert saved["status"] == "succeeded"
    assert saved["object_kind"] == "trading_signal"
    assert saved["revision_no"] == 1
    assert saved["ready_state"] == "STALE"
    assert saved["attached"] is True
    # No Package row exists anywhere, and the Mainboard item carries the work-object
    # kind the server derived from the root — not a package kind.
    assert await _count(session, PackageRoot) == 0
    item = (
        await session.execute(
            select(MainboardWorkingItem).where(
                MainboardWorkingItem.work_object_root_id == saved["root_id"]
            )
        )
    ).scalar_one()
    assert str(item.item_kind) == "trading_signal"


async def test_create_pins_the_exact_normalized_revision_and_its_available_time(
    session, fake_object_store
) -> None:
    """The revision pins the EXACT normalized import, and ``available_time`` comes
    from that import's earliest accepted event — never from ``event_time`` and never
    from wall-clock. r1 is available three minutes after it occurred, so the two
    timestamps are distinguishable and the lookahead guard is observable."""
    await _seed(session)
    bundle = await _agent_signal(session)
    saved = bundle["created"]
    normalized_id = bundle["report"]["normalized_event_revision_id"]

    revision = await session.get(WorkObjectRevision, saved["revision_id"])
    assert revision is not None
    assert revision.available_time is not None
    assert revision.available_time.isoformat().startswith(_EARLIEST_AVAILABLE)
    assert not revision.available_time.isoformat().startswith(_EARLIEST_EVENT)
    assert revision.payload["import_binding"]["normalized_event_revision_id"] == normalized_id

    # The normalized revision is linked back to exactly this work-object revision.
    normalized = await session.get(NormalizedSignalEventRevision, normalized_id)
    assert normalized is not None
    assert normalized.work_object_revision_id == saved["revision_id"]


async def test_agent_output_is_owned_by_the_agent_and_never_touches_a_human_board(
    session, fake_object_store
) -> None:
    """TS-20 / AOS-20, the whole sentence: ownership + provenance are recorded, and
    the human board is not auto-mutated. With no ``workspace_id`` the attach resolves
    the CALLER's own default board, which for an Agent is its ``agent_research``
    composition — a human board is unreachable by omission."""
    await _seed(session)
    human_before = await mb_query.get_default_mainboard(session, HUMAN)
    await session.commit()

    saved = (await _agent_signal(session))["created"]

    revision = await session.get(WorkObjectRevision, saved["revision_id"])
    assert revision is not None
    assert revision.created_by_principal_id == _AGENT_PID

    human_after = await mb_query.get_default_mainboard(session, HUMAN)
    assert human_after["items"] == []
    assert human_after["composition_hash"] == human_before["composition_hash"]

    agent_board = await mb_query.get_default_mainboard(session, AGENT)
    assert [item["item_kind"] for item in agent_board["items"]] == ["trading_signal"]
    assert agent_board["workspace_id"] != human_after["workspace_id"]
    assert agent_board["workspace_kind"] == "agent_research"
    assert saved["workspace_id"] == agent_board["workspace_id"]

    audit = (
        await session.execute(
            select(func.count())
            .select_from(AuditEvent)
            .where(
                AuditEvent.event_kind == "trading_signal.revision_created",
                AuditEvent.actor_principal_id == _AGENT_PID,
            )
        )
    ).scalar_one()
    assert audit == 1


async def test_an_explicitly_named_human_workspace_is_refused(session, fake_object_store) -> None:
    """Containment is not merely a default. Naming the human's board outright is a
    recorded governance denial, and nothing is attached to it."""
    await _seed(session)
    human_board = await mb_query.get_default_mainboard(session, HUMAN)
    await session.commit()

    imported = await _agent_import(session)
    result = await _tool(
        session,
        "trading_signal.create",
        "proposal",
        {
            "payload": _signal_payload(
                imported["upload"]["source_asset_id"],
                imported["report"]["normalized_event_revision_id"],
            ),
            "workspace_id": human_board["workspace_id"],
        },
    )
    assert result["status"] == "rejected"

    after = await mb_query.get_default_mainboard(session, HUMAN)
    assert after["items"] == []
    assert after["composition_hash"] == human_board["composition_hash"]


async def test_a_foreign_private_root_cannot_be_revised(session, fake_object_store) -> None:
    """The Agent may update only its OWN output (doc 04 §10). A human's root is a
    recorded denial, never last-write-wins."""
    await _seed(session)
    human_upload = await ts_cmd.upload_source_asset(
        session, HUMAN, content=_GOOD_CSV, original_filename="signals.csv"
    )
    await session.commit()
    human_import = await ts_cmd.request_trading_signal_import(
        session, HUMAN, source_asset_id=human_upload["source_asset_id"], instrument_id="BTCUSDT"
    )
    await session.commit()
    await run_import(session, human_import["job_id"])
    await session.commit()
    from entropia.application.queries.trading_signal import get_import_report

    report = await get_import_report(session, HUMAN, job_id=human_import["job_id"])
    human_payload = _signal_payload(
        human_upload["source_asset_id"], report["normalized_event_revision_id"]
    )
    human_saved = await ts_cmd.create_trading_signal_and_attach(
        session, HUMAN, payload=human_payload
    )
    await session.commit()

    result = await _tool(
        session,
        "trading_signal.create_revision",
        "proposal",
        {
            "root_id": human_saved["root_id"],
            "payload": human_payload,
            "expected_head_revision_id": human_saved["revision_id"],
        },
    )
    assert result["status"] == "rejected"
    # Still exactly the human's single revision.
    revisions = (
        await session.execute(
            select(func.count())
            .select_from(WorkObjectRevision)
            .where(WorkObjectRevision.entity_id == human_saved["root_id"])
        )
    ).scalar_one()
    assert revisions == 1


# --------------------------------------------------------------------------- #
# Revision — OCC + no auto-repin (doc 04 §8.2 rule 9)                           #
# --------------------------------------------------------------------------- #


async def test_revision_occ_conflict_is_recorded_and_never_last_write_wins(
    session, fake_object_store
) -> None:
    """A stale ``expected_head_revision_id`` is the human line's own conflict code,
    recorded as a durable FAILED call — no second revision is appended."""
    await _seed(session)
    bundle = await _agent_signal(session)
    saved = bundle["created"]
    payload = _signal_payload(
        bundle["upload"]["source_asset_id"], bundle["report"]["normalized_event_revision_id"]
    )

    stale = await _tool(
        session,
        "trading_signal.create_revision",
        "proposal",
        {
            "root_id": saved["root_id"],
            "payload": payload,
            "expected_head_revision_id": "wovrev_not_the_head",
        },
    )
    assert stale["status"] == "failed"
    assert stale["failure_code"] == "WORK_OBJECT_REVISION_CONFLICT"
    assert await _count(session, WorkObjectRevision) == 1


async def test_a_new_revision_is_immutable_and_never_auto_repins_the_item(
    session, fake_object_store
) -> None:
    """Rule 9: the prior revision is untouched and the Mainboard item keeps pointing
    at the revision it was pinned to. Moving the pin stays the explicit
    "Use This Revision" action, which this slice deliberately does not automate."""
    await _seed(session)
    bundle = await _agent_signal(session)
    saved = bundle["created"]
    payload = _signal_payload(
        bundle["upload"]["source_asset_id"], bundle["report"]["normalized_event_revision_id"]
    )

    item_before = (
        await session.execute(
            select(MainboardWorkingItem).where(
                MainboardWorkingItem.work_object_root_id == saved["root_id"]
            )
        )
    ).scalar_one()
    assert item_before.pinned_revision_id == saved["revision_id"]

    payload["identity"]["display_name"] = "Agent-imported signal source v2"
    revised = await _tool(
        session,
        "trading_signal.create_revision",
        "proposal",
        {
            "root_id": saved["root_id"],
            "payload": payload,
            "expected_head_revision_id": saved["revision_id"],
        },
    )
    assert revised["status"] == "succeeded"
    assert revised["revision_no"] == 2
    assert revised["auto_repinned"] is False
    assert revised["revision_id"] != saved["revision_id"]

    original = await session.get(WorkObjectRevision, saved["revision_id"])
    assert original is not None
    assert original.payload["identity"]["display_name"] == "Agent-imported signal source"

    await session.refresh(item_before)
    assert item_before.pinned_revision_id == saved["revision_id"]


# --------------------------------------------------------------------------- #
# Idempotency (AL-14 + the domain Idempotency-Key contract)                     #
# --------------------------------------------------------------------------- #


async def test_domain_idempotency_key_replay_appends_no_second_revision(
    session, fake_object_store
) -> None:
    """The command's OWN Idempotency-Key contract, reached through the Gateway: the
    same key returns the same revision instead of appending another."""
    await _seed(session)
    bundle = await _agent_signal(session)
    saved = bundle["created"]
    payload = _signal_payload(
        bundle["upload"]["source_asset_id"], bundle["report"]["normalized_event_revision_id"]
    )

    first = await _tool(
        session,
        "trading_signal.create_revision",
        "proposal",
        {
            "root_id": saved["root_id"],
            "payload": payload,
            "expected_head_revision_id": saved["revision_id"],
            "idempotency_key": "ts-rev-1",
        },
    )
    replay = await _tool(
        session,
        "trading_signal.create_revision",
        "proposal",
        {
            "root_id": saved["root_id"],
            "payload": payload,
            "expected_head_revision_id": saved["revision_id"],
            "idempotency_key": "ts-rev-1",
        },
    )
    assert replay["revision_id"] == first["revision_id"]
    assert await _count(session, WorkObjectRevision) == 2  # revision 1 + the one append


async def test_same_domain_key_with_a_different_payload_is_a_recorded_conflict(
    session, fake_object_store
) -> None:
    """Reusing a key for different inputs is a conflict, not a silent overwrite."""
    await _seed(session)
    bundle = await _agent_signal(session)
    saved = bundle["created"]
    payload = _signal_payload(
        bundle["upload"]["source_asset_id"], bundle["report"]["normalized_event_revision_id"]
    )
    await _tool(
        session,
        "trading_signal.create_revision",
        "proposal",
        {
            "root_id": saved["root_id"],
            "payload": payload,
            "expected_head_revision_id": saved["revision_id"],
            "idempotency_key": "ts-rev-clash",
        },
    )
    diverged = {**payload, "identity": {"display_name": "different input"}}
    clash = await _tool(
        session,
        "trading_signal.create_revision",
        "proposal",
        {
            "root_id": saved["root_id"],
            "payload": diverged,
            "expected_head_revision_id": saved["revision_id"],
            "idempotency_key": "ts-rev-clash",
        },
    )
    assert clash["status"] == "failed"
    assert await _count(session, WorkObjectRevision) == 2


# --------------------------------------------------------------------------- #
# Durability + the governed call history (doc 18 §9.2)                          #
# --------------------------------------------------------------------------- #


async def test_durable_job_path_records_audit_outbox_and_events(session, fake_object_store) -> None:
    """The worker's envelope: the same call through ``enqueue_tool_call`` ->
    ``run_tool_job`` writes the domain's audit + outbox rows and the gateway's agent
    events, and a redelivery replays the recorded outcome without a second write."""
    await _seed(session)
    imported = await _agent_import(session)

    job = agent_tools.enqueue_tool_call(
        session,
        AGENT,
        tool_name="trading_signal.create",
        policy_scope="proposal",
        request={
            "payload": _signal_payload(
                imported["upload"]["source_asset_id"],
                imported["report"]["normalized_event_revision_id"],
            )
        },
        idempotency_key="durable-ts-create-1",
    )
    await session.commit()
    assert job.queue == "agent"

    result = await agent_tools.run_tool_job(session, job.job_id)
    await session.commit()
    assert result["status"] == "succeeded"
    revision_id = result["revision_id"]

    outbox = (
        await session.execute(
            select(func.count())
            .select_from(OutboxEvent)
            .where(OutboxEvent.event_type == "trading_signal.revision_created")
        )
    ).scalar_one()
    assert outbox == 1
    event_types = set((await session.execute(select(AgentEvent.type))).scalars().all())
    assert {"tool_call_started", "tool_call_succeeded", "trading_signal_created"} <= event_types

    replay = await agent_tools.run_tool_job(session, job.job_id)
    await session.commit()
    assert replay["replayed"] is True
    assert replay["revision_id"] == revision_id
    assert await _count(session, WorkObjectRevision) == 1


async def test_signal_calls_reach_the_analysis_lab_history_with_provenance(
    session, fake_object_store
) -> None:
    """TS-20's provenance clause: "task/checkpoint provenance are recorded". Both a
    SUCCEEDED and a FAILED signal call must be visible in the governed history with
    the literal tool name, the machine code, and the task/checkpoint they belong to."""
    await _seed(session)
    task = await al_repo.create_task(
        session,
        agent_id=ALPHA_AGENT_ID,
        task_type="research",
        title="Signal ingestion",
        source="autonomous",
        priority=AgentTaskPriority.AUTONOMOUS,
        status=AgentTaskStatus.RUNNING,
    )
    await session.flush()

    upload = await _tool(
        session,
        "trading_signal.upload_source_asset",
        "research",
        {"content": _GOOD_CSV.decode("utf-8"), "original_filename": "signals.csv"},
        task_id=task.task_id,
        checkpoint_id="ckpt_signal_1",
    )
    failed = await _tool(
        session,
        "trading_signal.request_import",
        "research",
        {"source_asset_id": "srcasset_missing", "instrument_id": "BTCUSDT"},
        task_id=task.task_id,
        checkpoint_id="ckpt_signal_1",
    )

    page = await tool_gateway_query.list_task_tool_calls(session, ADMIN, task_id=task.task_id)
    by_id = {row["tool_call_id"]: row for row in page["tool_calls"]}
    assert by_id[upload["tool_call_id"]]["tool_name"] == "trading_signal.upload_source_asset"
    assert by_id[upload["tool_call_id"]]["status"] == "succeeded"
    assert by_id[upload["tool_call_id"]]["checkpoint_id"] == "ckpt_signal_1"
    assert by_id[upload["tool_call_id"]]["correlation_id"] == AGENT.correlation_id
    assert by_id[failed["tool_call_id"]]["status"] == "failed"
    assert by_id[failed["tool_call_id"]]["failure_code"] == "SOURCE_ASSET_NOT_FOUND"

    detail = await tool_gateway_query.get_tool_call(
        session, ADMIN, tool_call_id=upload["tool_call_id"]
    )
    assert detail["policy_scope"] == "research"
    assert detail["task_id"] == task.task_id
    # Provenance without the payload: the history shows the reference, not the bytes.
    assert "content" not in detail["request"]
    assert detail["request"]["content_ref"]["size_bytes"] == len(_GOOD_CSV)
