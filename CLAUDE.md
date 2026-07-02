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

- **Landed:** **Stages 0-7 COMPLETE** — last slice **Stage 7b — Future Dev (doc 22,
  PR #32)**. `main` after PR #32 = `ef3e1c1`; alembic head = **`0020_future_dev`**
  (6 tables: `future_capability` registry root with UNIQUE `capability_key` +
  per-row monotonic `registry_version` OCC + `dependency_snapshot` JSONB gates;
  immutable `capability_activation_event` with UNIQUE
  `(capability_id, resulting_registry_version)`; output roots `analysis_artifact` +
  `view_dataset` (deletion_state overlay); future-only `experiment_proposal` +
  `execution_plan` — NO V1 command writes them; 7 baseline slots seeded
  Placeholder with ids `fcap_<key>`). `domain/capability`: 7-state graph
  (`placeholder→designed→internal→shadow→limited→active`, rollback
  `active→limited`/`limited→shadow`, `limited|active→retired` terminal) + 7 gates
  (Designed/Internal/Shadow = keys present; Limited = 6 complete sans `ui`;
  Active = 7/7 → else 422 CAPABILITY_DEPENDENCY_MISSING per-gate list).
  `transition_capability`: Admin route+service (`require_capability_admin`),
  non-empty reason, REQUIRED idempotency key + `expected_registry_version` OCC
  (`with_for_update`, stale → 409 CAPABILITY_STATE_STALE), one-tx event+audit+
  outbox. Operational cmds gate FIRST: inactive → CAPABILITY_NOT_ACTIVE, zero
  side effects (CR-09); `POST /v1/view-datasets/query` + `/v1/analysis-artifacts`
  (type→capability map `ANALYSIS_ARTIFACT_CAPABILITY`) only Limited/Active.
  CR-08: `view_dataset.query`/`analysis_artifact.create` in
  `CAPABILITY_GATED_TOOLS`; `exposed_tool_names(operational_keys)` +
  `capability_repo.operational_capability_keys`; Placeholder call → REJECTED
  record. No live-trade/order route (FD-12). Review: 0 findings. **781 tests
  pass.**
- **Next:** **Stage 8 — End-to-End Integration & Hardening**: outbox→SSE fan-out
  all domains; Tool Gateway parity tests vs human commands (+ wire
  `exposed_tool_names` into Coordinator planning — 7b deferred); cross-stage
  manifest reproducibility; retention/purge scheduler; rate limiting;
  CORS/security headers; metrics (golden signals + queue depth + outbox lag +
  lease age). Flows: (a) full pipeline ingest→…→RUN→Result→Trash→restore,
  (b) UI-independent Agent loop. Acceptance: pinned-manifest reproducibility,
  CR-03, INF-01..INF-10, deployment topology boots + health/ready. Branch
  `feat/stage-8-integration`. Full handoff: `docs/STAGE8_KICKOFF.md`.
