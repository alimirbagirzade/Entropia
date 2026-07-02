# Entropia — Claude Operating Guide

Backend-first, **spec-driven, staged** build (FastAPI + Postgres + Alembic + dramatiq).
Specs live in `docs/spec/NN_*`; the stage roadmap is `docs/STAGE_BUILD_PLAN.md`; the
running handoff is `docs/STAGE2_HANDOFF.md`; each slice has a `docs/STAGE<x>_KICKOFF.md`
with a **paste-ready resume prompt** at the bottom.

> Conversation language: **Turkish**. Technical identifiers stay in English.

---

## Session START protocol (do this FIRST, every session)

1. **Verify — the handoff/summary is STALE-BY-DEFAULT.** Never trust a prior-session
   summary or local branch. Run `git fetch`, `git log --oneline origin/main -6`,
   `gh pr list --state all`. Confirm what actually **landed/merged** before acting.
2. **Read in authority order:** (1) latest `docs/STAGE<next>_KICKOFF.md` (this slice's
   full handoff), (2) `docs/STAGE2_HANDOFF.md` ("... landed" + "Next"), (3)
   `docs/STAGE_BUILD_PLAN.md` (stage table + acceptance), (4) `docs/spec/NN_*` (extract
   the spec FULLY), (5) memory checkpoints for the prior stage (ecc graph + claude-mem).
3. The **paste-ready resume prompt** at the bottom of the kickoff doc is your
   continuation seed — that is what gets pasted into a fresh session.

---

## Session CLOSING ritual (do this at EVERY close — MANDATORY)

Before stopping a working session, produce **ALL** of the following:

1. **Handoff** — update `docs/STAGE2_HANDOFF.md`: add a `## Stage <x> — <title> landed (PR #n)`
   entry (migration, new tables, test counts, review outcome, deferred items) and set
   `## Next: Stage <y> — <title>`.
2. **Kickoff + resume prompt** — create/refresh `docs/STAGE<next>_KICKOFF.md`: where we
   are, what the last slice **left behind (reuse anchors with exact symbol names)**, next
   design pointers, REUSE list, working-loop method, and a **paste-ready resume prompt
   block** (the exact text to paste into a clean session to continue).
3. **Memory checkpoint — write BOTH systems:**
   - **ecc knowledge graph** — an entity `Entropia Stage <x> — <title>` with rich factual
     observations + a relation to the next stage (`unblocks`).
   - **claude-mem** — a checkpoint observation for the slice (searchable via `mem-search`).
4. **Commit -> PR -> await merge** — commit on branch `docs/stage-<x>-landed` (conventional
   message, **NO AI attribution**), push, open a PR to `main`, `gh pr checks <n> --watch`;
   **self-merge is blocked -> ask the user to merge** once green.

---

## Conventions

- **Cost-conscious.** No unnecessary parallel agents or full-file reads. **Empirically
  verify** every code-review CRITICAL/HIGH finding before fixing (they are often wrong).
- **Direct-author (no Workflow)** for backend slices; mirror the previous slice's pattern
  (module-level async commands, one-tx no-commit, `run_idempotent`,
  `session.refresh(with_for_update=True)`, `_audit_and_outbox`).
- **GateGuard:** write NEW files via Bash heredoc (`cat > f << 'PYEOF'`) -> gate-free; an
  EDIT/WRITE to an existing file triggers fact-force (present 4 facts: importers / affected
  public API / data schema / user request verbatim -> retry). First Bash of a session
  triggers a one-time fact gate.
- **Local verify (backend):** `cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest --no-cov -q`
  + an **L1 FK insert-order proof for every new `create_*`** + **alembic `<n>` up/down/up**
  (`LC_ALL=en_US.UTF-8`, `DROP SCHEMA public CASCADE; CREATE SCHEMA public;` before the proof)
  + migration<->model column parity. Local Postgres on **:5432** (`entropia`/`entropia`).
- **Git:** `feat/stage-<x>-<slug>` for features, `docs/stage-<x>-landed` for closing docs.
  Commit `<type>(stage-<x>): <subject>`. **No AI attribution** (disabled globally).
- **Stage order is authoritative** (`STAGE_BUILD_PLAN.md`) — never skip sub-stages.
  Stage 5 = docs 15/16/17; Stage 6 = docs 18/19/20; Stage 7 = docs 21/22.

---

## Current position (keep in sync at each closing)

- **Landed:** Stages 0-6 COMPLETE + **Stage 7a — User Manual (doc 21, PR #30)**. `main`
  after PR #30 = `be65d4e`; alembic head = **`0019_user_manual`** (6 tables:
  `manual_documents` page-local root + `is_baseline`/`deletion_state` overlay,
  immutable `manual_document_revisions`, `manual_stream_entries` with unique
  never-reassigned `stream_position`, canonical `manual_content_blocks`,
  `manual_search_chunks` + GIN `'simple'` FTS, append-only `manual_publication_events`
  whose UNIQUE monotonic `resulting_stream_version` is the reader stream_version;
  baseline guide seeded from `build_baseline_seed()`). Commands: one-tx publish
  (create/upload share `_publish_new_document`), revision replace (same position,
  v1→Superseded, OCC `expected_head_revision_id`), soft delete → Trash entry
  (`MANUAL_ENTITY_TYPE` dispatch in deletion.py/purge.py; restore = same position +
  same revision chain; purge redacts search chunks, retains revisions; baseline never
  delete/purge-eligible). Advisory stream lock (`lock_stream`, key 210721) serializes
  stream mutations; `expected_stream_version` → MANUAL_STREAM_CONFLICT. Routes:
  `GET /v1/manual/stream|/search` (all-role) + Admin write (`require_manual_admin`
  route AND service). Tool Gateway += `documentation.search/get_section` +
  `artifact.attach_citation` (read/citation only). **L1 lesson:** without
  `relationship()` SQLAlchemy does NOT FK-order cross-table inserts — repo `create_*`
  must flush parent-before-child (manual repo precedent). Review: 0 CRITICAL/HIGH.
  **758 tests pass.**
- **Next:** **Stage 7b — Future Dev (doc 22)**: `domain/capability` (7 activation
  gates + state graph), Admin `capability_transition` (legal edge + non-empty reason +
  `expected_registry_version` OCC + idempotency_key), inactive op →
  `CAPABILITY_NOT_ACTIVE` (already in `shared/errors`), tables `future_capability`/
  `capability_activation_event`/`analysis_artifact`/`view_dataset`/
  `experiment_proposal`/`execution_plan` → migration `0020_*` (→0019), endpoints
  `GET /api/v1/capabilities`, `/capabilities/{key}`, `POST .../lifecycle-transitions`
  (Admin), `GET /future-dev/graphic_view/overview`, `POST /view-datasets/query`
  (Limited/Active only), `POST /analysis-artifacts`. Agent tool contracts ONLY for
  Active/Limited (CR-08); NO fake endpoints/jobs/progress/chart (CR-09); Live Trade =
  separate execution plane. Branch `feat/stage-7b-future-dev`. Full handoff:
  `docs/STAGE7B_KICKOFF.md`.
