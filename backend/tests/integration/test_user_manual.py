"""Stage 7a — User Manual against a real database (doc 21 §7-§12, UM-01..UM-18).

Auto-skips without PostgreSQL. Covers: baseline-first single-snapshot stream
ordered by unique stream_position (UM-01); Admin-only write at the service
(UM-07/16); Add/Paste + Markdown upload canonical blocks (UM-04/05); upload
type + parse rejections with no phantom section (UM-06/17); duplicate-content
block + explicit override; server-side FTS over title/heading/content with
anchors (UM-02); soft delete -> Trash page-contract entry (UM-08); baseline
immutability (UM-10); deterministic same-position restore through the landed
Trash core (UM-09); revision replace keeps position, supersedes v1 (UM-11);
stale stream/revision OCC (UM-15); two-phase purge with search-projection
redaction; Agent tool parity — documentation.search/get_section +
artifact.attach_citation, ownership guard (UM-03/12); an L1 FK insert-order
proof for the new create_* helpers.
"""

from __future__ import annotations

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from entropia.application.commands.deletion import request_purge
from entropia.application.commands.manual import (
    create_manual_document,
    replace_manual_revision,
    restore_manual_document,
    soft_delete_manual_document,
    upload_manual_document,
)
from entropia.application.jobs import agent_tools
from entropia.application.jobs import purge as purge_job
from entropia.application.queries.manual import (
    get_manual_section,
    get_manual_stream,
    search_manual,
)
from entropia.domain.agent_lab.enums import (
    ALPHA_AGENT_ID,
    HypothesisStatus,
    RuntimeMode,
    RuntimeStatus,
)
from entropia.domain.identity import Actor
from entropia.domain.lifecycle.enums import DeletionState, PrincipalType, Role
from entropia.domain.manual.blocks import ContentBlock
from entropia.domain.manual.enums import (
    BASELINE_DOCUMENT_ID,
    MANUAL_ENTITY_TYPE,
    BlockType,
    ManualSourceType,
)
from entropia.infrastructure.postgres.models import (
    AgentRuntime,
    ArtifactLink,
    AuditEvent,
    ManualDocument,
    ManualDocumentRevision,
    ManualSearchChunk,
    ManualStreamEntry,
    Principal,
    Tombstone,
    TrashEntry,
)
from entropia.infrastructure.postgres.repositories import agent_lab as al_repo
from entropia.infrastructure.postgres.repositories import manual as manual_repo
from entropia.infrastructure.postgres.repositories import trash as trash_repo
from entropia.shared.errors import (
    AdminManualWriteRequiredError,
    BaselineManualImmutableError,
    ManualContentRequiredError,
    ManualDuplicateContentError,
    ManualFileTypeUnsupportedError,
    ManualParseFailedError,
    ManualRevisionConflictError,
    ManualSectionNotFoundError,
    ManualStreamConflictError,
    ManualTitleRequiredError,
)

pytestmark = pytest.mark.integration

ADMIN = Actor(
    principal_id="user_admin",
    principal_type=PrincipalType.HUMAN,
    role=Role.ADMIN,
    correlation_id="corr_adm",
)
USER = Actor(principal_id="user_1", principal_type=PrincipalType.HUMAN, role=Role.USER)
SUPERVISOR = Actor(
    principal_id="user_sup", principal_type=PrincipalType.HUMAN, role=Role.SUPERVISOR
)
AGENT = Actor(
    principal_id="agent_alpha",
    principal_type=PrincipalType.AGENT,
    role=None,
    correlation_id="corr_ag",
)


async def _seed(session) -> None:
    for actor in (ADMIN, USER, SUPERVISOR, AGENT):
        session.add(Principal(principal_id=actor.principal_id, principal_type=actor.principal_type))
    session.add(
        AgentRuntime(
            agent_id=ALPHA_AGENT_ID,
            mode=RuntimeMode.CONTINUOUS,
            status=RuntimeStatus.ACTIVE,
            row_version=1,
        )
    )
    await manual_repo.seed_baseline(session)
    await session.commit()


async def _count(session, model) -> int:
    return int((await session.execute(select(func.count()).select_from(model))).scalar_one())


async def _add_doc(session, title: str, content: str) -> dict:
    result = await create_manual_document(session, ADMIN, title=title, content=content)
    await session.commit()
    return result


# --------------------------------------------------------------------------- #
# Stream + publish                                                             #
# --------------------------------------------------------------------------- #


async def test_stream_baseline_first_then_unique_positions(session) -> None:
    await _seed(session)
    a = await _add_doc(session, "Alpha Guide", "First body about entries.")
    b = await _add_doc(session, "Beta Guide", "Second body about exits.")

    page = await get_manual_stream(session, USER)
    sections = page["data"]
    assert [s["document_id"] for s in sections][:1] == [BASELINE_DOCUMENT_ID]
    assert sections[0]["is_baseline"] is True
    expected = [1, a["stream_position"], b["stream_position"]]
    assert [s["stream_position"] for s in sections] == expected
    assert a["stream_position"] == 2 and b["stream_position"] == 3
    assert page["meta"]["stream_version"] == 3
    assert sections[1]["anchor"] == f"manual-section-{a['document_id']}"
    assert sections[1]["blocks"][0]["block_type"] == "paragraph"


async def test_stream_pagination_keyset(session) -> None:
    await _seed(session)
    await _add_doc(session, "Alpha Guide", "First body.")
    first = await get_manual_stream(session, USER, limit=1)
    assert len(first["data"]) == 1 and first["meta"]["has_more"] is True
    second = await get_manual_stream(session, USER, cursor=first["meta"]["cursor"], limit=1)
    assert second["data"][0]["stream_position"] == 2


async def test_publish_is_atomic_and_audited(session) -> None:
    await _seed(session)
    audits_before = await _count(session, AuditEvent)
    result = await _add_doc(session, "Atomic Guide", "Body text.")
    assert result["revision_no"] == 1
    assert result["stream_version"] == 2
    assert await _count(session, AuditEvent) == audits_before + 1
    revision = await manual_repo.get_revision(session, result["revision_id"])
    assert revision is not None and revision.source_type == ManualSourceType.ADDED_TEXT


async def test_create_idempotency_replay_no_duplicate(session) -> None:
    await _seed(session)
    first = await create_manual_document(
        session, ADMIN, title="Idem Guide", content="Same body.", idempotency_key="mkey-1"
    )
    await session.commit()
    replay = await create_manual_document(
        session, ADMIN, title="Idem Guide", content="Same body.", idempotency_key="mkey-1"
    )
    await session.commit()
    assert replay["document_id"] == first["document_id"]
    assert await _count(session, ManualDocument) == 2  # baseline + one


# --------------------------------------------------------------------------- #
# Write policy + validation (UM-06/07/16/17)                                   #
# --------------------------------------------------------------------------- #


async def test_service_rejects_non_admin_writers(session) -> None:
    await _seed(session)
    revisions_before = await _count(session, ManualDocumentRevision)
    for actor in (USER, SUPERVISOR, AGENT):
        with pytest.raises(AdminManualWriteRequiredError):
            await create_manual_document(session, actor, title="X", content="y")
    assert await _count(session, ManualDocumentRevision) == revisions_before


async def test_title_and_content_required(session) -> None:
    await _seed(session)
    with pytest.raises(ManualTitleRequiredError):
        await create_manual_document(session, ADMIN, title="  ", content="body")
    with pytest.raises(ManualContentRequiredError):
        await create_manual_document(session, ADMIN, title="T", content="   \n  ")


async def test_upload_markdown_becomes_canonical_blocks(session) -> None:
    await _seed(session)
    content = "# Setup\nIntro line.\n\n- one\n- two\n\n```python\nprint(1)\n```\n"
    result = await upload_manual_document(
        session, ADMIN, source_filename="setup-notes.md", content=content
    )
    await session.commit()
    assert result["title"] == "setup-notes"
    blocks = (await manual_repo.load_blocks(session, [result["revision_id"]]))[
        result["revision_id"]
    ]
    kinds = [b.block_type for b in blocks]
    assert kinds == [BlockType.HEADING, BlockType.PARAGRAPH, BlockType.BULLET_LIST, BlockType.CODE]
    assert blocks[0].anchor == "setup"
    assert blocks[3].payload["code_text"] == "print(1)"


async def test_upload_rejects_unsupported_and_parse_failures(session) -> None:
    await _seed(session)
    docs_before = await _count(session, ManualDocument)
    with pytest.raises(ManualFileTypeUnsupportedError):
        await upload_manual_document(session, ADMIN, source_filename="a.pdf", content="x")
    with pytest.raises(ManualParseFailedError):
        await upload_manual_document(
            session,
            ADMIN,
            source_filename="evil.html",
            content="<p>ok</p><script>alert(1)</script>",
        )
    await session.rollback()
    assert await _count(session, ManualDocument) == docs_before  # no phantom section


async def test_duplicate_content_blocked_unless_overridden(session) -> None:
    await _seed(session)
    await _add_doc(session, "Original", "Unique duplicate-check body.")
    with pytest.raises(ManualDuplicateContentError):
        await create_manual_document(
            session, ADMIN, title="Copy", content="Unique duplicate-check body."
        )
    await session.rollback()
    result = await create_manual_document(
        session, ADMIN, title="Copy", content="Unique duplicate-check body.", allow_duplicate=True
    )
    await session.commit()
    assert result["stream_position"] == 3


# --------------------------------------------------------------------------- #
# Search (UM-02/14)                                                            #
# --------------------------------------------------------------------------- #


async def test_search_covers_title_heading_and_content(session) -> None:
    await _seed(session)
    content = "# Position Entry\nThe zebra threshold controls entries.\n"
    doc = await upload_manual_document(
        session, ADMIN, source_filename="entries.md", content=content, title="Entry Rules"
    )
    await session.commit()

    by_content = await search_manual(session, SUPERVISOR, q="zebra")
    assert [r["document_id"] for r in by_content["data"]] == [doc["document_id"]]
    hit = by_content["data"][0]
    assert hit["revision_no"] == 1
    assert hit["heading_path"].startswith("Entry Rules")
    assert hit["anchor"] == "position-entry"
    assert "[zebra]" in hit["excerpt"]
    assert hit["block_ids"]

    by_title = await search_manual(session, USER, q="Entry Rules")
    assert any(r["document_id"] == doc["document_id"] for r in by_title["data"])

    blank = await search_manual(session, USER, q="   ")
    assert blank["data"] == [] and blank["meta"]["query"] == ""


async def test_search_excludes_soft_deleted_documents(session) -> None:
    await _seed(session)
    doc = await _add_doc(session, "Vanishing", "A quokka fact inside.")
    assert (await search_manual(session, USER, q="quokka"))["data"]
    await soft_delete_manual_document(session, ADMIN, document_id=doc["document_id"])
    await session.commit()
    assert (await search_manual(session, USER, q="quokka"))["data"] == []


# --------------------------------------------------------------------------- #
# Soft delete / baseline / restore (UM-08/09/10/15)                            #
# --------------------------------------------------------------------------- #


async def test_soft_delete_writes_manual_trash_entry(session) -> None:
    await _seed(session)
    doc = await _add_doc(session, "Deletable", "Body.")
    result = await soft_delete_manual_document(
        session, ADMIN, document_id=doc["document_id"], reason="cleanup"
    )
    await session.commit()

    entry = await trash_repo.get_recoverable_entry_for_entity(session, doc["document_id"])
    assert entry is not None
    assert entry.entity_type == MANUAL_ENTITY_TYPE
    assert entry.display_name == "Deletable"
    assert entry.original_location == "Help / User Manual"
    assert (entry.deletion_snapshot or {}).get("stream_position") == doc["stream_position"]
    assert result["stream_version"] == 3

    stream = await get_manual_stream(session, USER)
    assert all(s["document_id"] != doc["document_id"] for s in stream["data"])

    repeat = await soft_delete_manual_document(session, ADMIN, document_id=doc["document_id"])
    assert repeat.get("idempotent_repeat") is True
    assert await _count(session, TrashEntry) == 1


async def test_baseline_is_immutable_via_page_flow(session) -> None:
    await _seed(session)
    with pytest.raises(BaselineManualImmutableError):
        await soft_delete_manual_document(session, ADMIN, document_id=BASELINE_DOCUMENT_ID)
    with pytest.raises(BaselineManualImmutableError):
        await replace_manual_revision(
            session, ADMIN, document_id=BASELINE_DOCUMENT_ID, content="new"
        )
    await session.rollback()
    stream = await get_manual_stream(session, USER)
    assert stream["data"][0]["document_id"] == BASELINE_DOCUMENT_ID


async def test_stale_stream_version_blocks_delete(session) -> None:
    await _seed(session)
    doc = await _add_doc(session, "Guarded", "Body.")
    with pytest.raises(ManualStreamConflictError):
        await soft_delete_manual_document(
            session, ADMIN, document_id=doc["document_id"], expected_stream_version=1
        )
    await session.rollback()
    assert (await manual_repo.get_document(session, doc["document_id"])).deletion_state == (
        DeletionState.ACTIVE
    )


async def test_restore_returns_same_position_and_revision_chain(session) -> None:
    await _seed(session)
    a = await _add_doc(session, "A-doc", "Alpha body.")  # position 2
    await _add_doc(session, "B-doc", "Beta body.")  # position 3
    await soft_delete_manual_document(session, ADMIN, document_id=a["document_id"])
    await session.commit()
    await _add_doc(session, "C-doc", "Gamma body.")  # position 4 (2 never reused)

    restored = await restore_manual_document(session, ADMIN, document_id=a["document_id"])
    await session.commit()
    assert restored["entity_id"] == a["document_id"]
    assert restored["current_revision_id"] == a["revision_id"]  # same chain, no new revision

    stream = await get_manual_stream(session, USER)
    positions = [(s["document_id"], s["stream_position"]) for s in stream["data"]]
    assert positions == [
        (BASELINE_DOCUMENT_ID, 1),
        (a["document_id"], 2),
        (positions[2][0], 3),
        (positions[3][0], 4),
    ]
    assert (await search_manual(session, USER, q="Alpha"))["data"]


# --------------------------------------------------------------------------- #
# Revision replace (UM-11)                                                     #
# --------------------------------------------------------------------------- #


async def test_replace_revision_keeps_position_and_supersedes(session) -> None:
    await _seed(session)
    doc = await _add_doc(session, "Versioned", "Version one narwhal.")
    result = await replace_manual_revision(
        session,
        ADMIN,
        document_id=doc["document_id"],
        content="Version two walrus.",
        expected_head_revision_id=doc["revision_id"],
    )
    await session.commit()

    assert result["revision_no"] == 2
    assert result["stream_position"] == doc["stream_position"]  # position never moves
    old = await manual_repo.get_revision(session, doc["revision_id"])
    assert old is not None and old.publication_state.value == "superseded"

    stream = await get_manual_stream(session, USER)
    section = next(s for s in stream["data"] if s["document_id"] == doc["document_id"])
    assert section["revision_no"] == 2
    assert (await search_manual(session, USER, q="walrus"))["data"]
    assert (await search_manual(session, USER, q="narwhal"))["data"] == []

    with pytest.raises(ManualRevisionConflictError):
        await replace_manual_revision(
            session,
            ADMIN,
            document_id=doc["document_id"],
            content="v3",
            expected_head_revision_id=doc["revision_id"],  # stale head
        )
    await session.rollback()


# --------------------------------------------------------------------------- #
# Two-phase purge (doc 20 §8.3 + doc 21 §11)                                   #
# --------------------------------------------------------------------------- #


async def test_manual_purge_redacts_search_keeps_revisions(session) -> None:
    await _seed(session)
    doc = await _add_doc(session, "Purgeable", "Purge body.")
    await soft_delete_manual_document(session, ADMIN, document_id=doc["document_id"])
    await session.commit()
    entry = await trash_repo.get_recoverable_entry_for_entity(session, doc["document_id"])
    accepted = await request_purge(
        session,
        ADMIN,
        trash_entry_id=entry.id,
        confirmation_phrase="Purgeable",
        reauth_proof="proof-token",
    )
    await session.commit()

    outcome = await purge_job.run_purge(session, accepted["purge_job_id"])
    await session.commit()
    assert outcome["purge_status"] == "completed"

    document = await manual_repo.get_document(session, doc["document_id"])
    assert document is not None and document.deletion_state == DeletionState.PURGED
    chunk_count = (
        await session.execute(
            select(func.count())
            .select_from(ManualSearchChunk)
            .where(ManualSearchChunk.document_id == doc["document_id"])
        )
    ).scalar_one()
    assert chunk_count == 0  # search projection redacted
    assert await manual_repo.get_revision(session, doc["revision_id"]) is not None  # retained
    assert (await session.get(Tombstone, doc["document_id"])) is not None


# --------------------------------------------------------------------------- #
# Agent tool parity (UM-03/12)                                                 #
# --------------------------------------------------------------------------- #


async def test_agent_documentation_search_and_get_section(session) -> None:
    await _seed(session)
    await upload_manual_document(
        session,
        ADMIN,
        source_filename="time.md",
        content="# Available Time\nAvailability is never inferred from render time.\n",
        title="Time Rules",
    )
    await session.commit()

    search = await agent_tools.dispatch_tool_call(
        session,
        AGENT,
        tool_name="documentation.search",
        policy_scope="research",
        request={"query": "available time"},
    )
    await session.commit()
    assert search["status"] == "succeeded"
    assert search["results"], "agent search must reach the published corpus"
    hit = search["results"][0]

    section = await agent_tools.dispatch_tool_call(
        session,
        AGENT,
        tool_name="documentation.get_section",
        policy_scope="observation",
        request={
            "document_id": hit["document_id"],
            "anchor": hit["anchor"],
            "revision_no": hit["revision_no"],
        },
    )
    await session.commit()
    assert section["status"] == "succeeded"
    assert section["citation"]["revision_no"] == hit["revision_no"]
    assert section["blocks"][0]["block_type"] == "heading"


async def test_agent_attach_citation_owns_artifact_only(session) -> None:
    await _seed(session)
    doc = await _add_doc(session, "Cited", "Citable body.")
    own = await al_repo.create_hypothesis(
        session,
        status=HypothesisStatus.EXPLORING,
        title="own",
        mechanism="m",
        data_context=None,
        evidence_refs=[],
        next_action=None,
        source_task_id=None,
        checkpoint_id=None,
        created_by_principal_id=AGENT.principal_id,
        correlation_id=None,
    )
    foreign = await al_repo.create_hypothesis(
        session,
        status=HypothesisStatus.EXPLORING,
        title="foreign",
        mechanism="m",
        data_context=None,
        evidence_refs=[],
        next_action=None,
        source_task_id=None,
        checkpoint_id=None,
        created_by_principal_id=ADMIN.principal_id,
        correlation_id=None,
    )
    await session.commit()

    ok = await agent_tools.dispatch_tool_call(
        session,
        AGENT,
        tool_name="artifact.attach_citation",
        policy_scope="research",
        request={
            "artifact_id": own.artifact_id,
            "document_id": doc["document_id"],
            "revision_no": 1,
            "anchor": doc["anchor"],
            "block_ids": [f"{doc['revision_id']}-b0000"],
        },
    )
    await session.commit()
    assert ok["status"] == "succeeded"
    links = (
        (
            await session.execute(
                select(ArtifactLink).where(ArtifactLink.source_artifact_id == own.artifact_id)
            )
        )
        .scalars()
        .all()
    )
    assert [link.relation_type for link in links] == ["cites_manual"]

    denied = await agent_tools.dispatch_tool_call(
        session,
        AGENT,
        tool_name="artifact.attach_citation",
        policy_scope="research",
        request={
            "artifact_id": foreign.artifact_id,
            "document_id": doc["document_id"],
            "revision_no": 1,
            "anchor": doc["anchor"],
        },
    )
    await session.commit()
    assert denied["status"] == "rejected"
    assert denied["reason_code"] == "ARTIFACT_NOT_OWNED"


# --------------------------------------------------------------------------- #
# Section resolution + FK insert-order proof                                   #
# --------------------------------------------------------------------------- #


async def test_get_section_slices_by_anchor_and_flags_stale(session) -> None:
    await _seed(session)
    content = "# One\nfirst part.\n\n# Two\nsecond part.\n"
    doc = await upload_manual_document(
        session, ADMIN, source_filename="s.md", content=content, title="Sliced"
    )
    await session.commit()

    section = await get_manual_section(session, USER, document_id=doc["document_id"], anchor="two")
    texts = [b["payload"].get("text", "") for b in section["blocks"]]
    assert texts == ["Two", "second part."]
    with pytest.raises(ManualSectionNotFoundError):
        await get_manual_section(session, USER, document_id=doc["document_id"], anchor="gone")
    with pytest.raises(ManualSectionNotFoundError):
        await get_manual_section(session, USER, document_id=doc["document_id"], revision_no=99)


async def test_l1_fk_insert_order_proof_for_manual_creates(session) -> None:
    await _seed(session)
    with pytest.raises(IntegrityError):
        await manual_repo.create_revision(
            session,
            document_id="mdoc_missing_root",
            revision_no=1,
            title="orphan",
            source_type=ManualSourceType.ADDED_TEXT,
            source_filename=None,
            content_checksum="0" * 64,
            created_by_principal_id=None,
            blocks=[ContentBlock(BlockType.PARAGRAPH, {"text": "x"})],
        )
    await session.rollback()

    entries = (await session.execute(select(ManualStreamEntry))).scalars().all()
    assert {entry.stream_position for entry in entries} == {1}  # baseline only, nothing leaked
