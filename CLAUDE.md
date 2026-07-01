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
  Stage 5 = docs 15/16/17; Stage 6 = docs 18/19/20.

---

## Current position (keep in sync at each closing)

- **Landed:** Stages 0-4b + 5a (doc 15) + 5b-1 (doc 16) + 5c (doc 17 + doc-15 deferred)
  + 6a (doc 18 surface + persistence) + **6a-2 — Analysis Lab Coordinator runtime
  loop + Tool Gateway (doc 18 §9.2/§10)**. `main` after PR #24 = `23e13a5`; alembic
  head = `0017_agent_tool_gateway` (adds `agent_tool_call` — the durable tool-call
  envelope; `idempotency_key` UNIQUE). Coordinator loop = `apps/agent_coordinator` +
  `application/commands/agent_loop.run_coordinator_cycle`; Tool Gateway =
  `application/jobs/agent_tools` (`dispatch_tool_call`/`run_tool_job`/`enqueue_tool_call`)
  on `agent`/`agent-high` queue; parity tools + governance in
  `domain/agent_lab/tool_gateway`. AL-01/AL-11/AL-12/AL-14/AL-16 covered.
- **Next:** **Stage 6b — Panel / Management / Logs (doc 19)**: `application/commands/
  role_assignment` (atomic role change + last-admin protection) + `application/queries/
  log_projection` (Admin-only read model over `audit_events`, filters + opaque cursor);
  `require_admin` at endpoint **and** service; append-only events. Branch
  `feat/stage-6b-panel-logs`; migration `0018_*` if new tables. Then 6c = Trash
  (doc 20). Full handoff: `docs/STAGE6B_KICKOFF.md`.
