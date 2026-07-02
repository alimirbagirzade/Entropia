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

- **Landed:** Stages 0-4b + 5a/5b-1/5c (docs 15/16/17) + **Stage 6 COMPLETE** — 6a
  (doc 18) + 6a-2 (Coordinator + Tool Gateway) + 6b (Panel/Management/Logs, doc 19)
  + **6c — Trash (doc 20, PR #28)**. `main` after PR #28 = `b437254`; alembic head =
  **`0018_trash_page`** (no new table — `trash_entries` page-contract columns:
  `status` overlay, `row_version` OCC, snapshots, purge-job linkage + explicit
  `(deleted_at DESC, id DESC)` keyset index). 6c: state machine gained
  `PURGE_PENDING → SOFT_DELETED` (worker failure); `soft_delete_entity` = row-lock +
  idempotent repeat + type preflight (`OBJECT_IN_ACTIVE_RUN`,
  `RATIONALE_FAMILY_IN_USE` — no entry for a blocked delete);
  `restore_trash_entry` (Admin, OCC `expected_head_revision_id` vs entry
  `row_version`, head-pointer integrity → `RESTORE_CONFLICT`, same
  entity_id/current_revision_id, `trash.restored` audit + `entity.restored` outbox);
  `request_purge` (confirmation_phrase = display identity, non-empty `reauth_proof`,
  OCC+idempotency → `purge_pending` + durable `maintenance` job, 202) +
  `application/jobs/purge.run_purge` worker (re-preflight; success = root PURGED
  row-retained + tombstone; failure = back to soft_deleted + entry `purge_failed`);
  `require_trash_admin` → 403 `TRASH_ACCESS_FORBIDDEN` at route AND service (Agent
  denied; own-artifact soft-delete AL-16 only); `GET /v1/trash-entries[/{id}]`
  Admin-only projection (q/object_type SQL push-down, opaque cursor,
  `restore_eligible`); Backtest Result delete now writes a Trash entry
  (Result-local deletion flag dispatch). Review: 2 HIGH verified real, fixed
  (`soft_delete_family` row lock; DESC index DDL). **719 tests pass.**
- **Next:** **Stage 7a — User Manual (doc 21)**: `domain/manual` (atomic
  `stream_position`, canonical blocks — no raw HTML/MD), all-role
  `GET /v1/manual/stream` + `/search` (Postgres FTS, cursor), Admin-only write
  (`POST /v1/admin/manual/documents`, `:upload`, revisions; delete/restore via the
  landed Trash core), `BASELINE_MANUAL_IMMUTABLE`, Agent `documentation.search/
  get_section` + `artifact.attach_citation` via Tool Gateway. Then **7b — Future Dev
  (doc 22)** (capability registry, 7 activation gates, `CAPABILITY_NOT_ACTIVE`).
  Branch `feat/stage-7a-user-manual`; migration `0019_*` (→0018). Full handoff:
  `docs/STAGE7_KICKOFF.md`.
