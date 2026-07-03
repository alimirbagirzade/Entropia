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

- **Landed:** **V1 ROADMAP COMPLETE — Stages 0-8** (docs 01-22 + e2e integration +
  hardening) **+ post-V1 Auth/IdP (PR #38) + Parquet batch data-access (INF-12
  Slice A, PR #41) + real bar-replay backtest engine (INF-12 Slice B, PR #43)**;
  `main` after PR #43 = **`fc746f8`**;
  alembic head = **`0021_local_auth`** (`human_credentials` + `auth_sessions`;
  Slices A/B need no migration). **822 tests green** (818 + 4 engine).
  Engine slice: `domain/backtest/engine.py::run_engine` — pure single-pass
  bar-replay over `iter_bar_batches` (breakout entry PROXY labelled
  `entry_model=deterministic_bar_breakout_proxy_v1` + REAL protection stops
  percentage/trailing/absolute intrabar + costs + notional sizing clamped to
  `max(equity,0)`); `application/jobs/backtest_engine.py::run_backtest`
  (injectable `stream_bars`, ASSET_UNAVAILABLE/ENGINE_ERROR fail paths);
  manifest `ENGINE_VERSION=backtest-engine-v1-bar-replay`; run/manifest/result
  contracts unchanged. Review: 1 CRITICAL (negative all-in size inverts PnL) —
  empirically CONFIRMED, fixed via `max(equity,0)` clamp + bust-safety test.
  Parquet slice: `infrastructure/s3/parquet_stream.py`
  (`stream_processed_batches` — S3 → `SpooledTemporaryFile` 32MB spill cap →
  pyarrow `iter_batches`; `iter_parquet_batches` pure local I/O; worker plane
  only) + `application/queries/market_bars.py` (`resolve_bar_source` →
  `BarSourceRef`, `iter_bar_batches` — Slice B builds on this) +
  `repositories/market_data.py::get_processed_asset_for_revision` (ordering
  contract: separate-tx re-processing, same-ms ULID tiebreak documented limit);
  review 1 finding (ULID tiebreak) — empirically CONFIRMED, pinned by a
  deterministic test. Auth slice: local auth per M1 §4 —
  argon2id credentials, opaque Bearer sessions (SHA-256 digest only, fresh role
  per request), `AUTH_MODE=dev|session` (dev default keeps `X-Actor-Id` for
  tests), non-human-only service line `ENTROPIA_SERVICE_TOKEN`, rate-limit key
  from Authorization digest; review 0 CRITICAL/HIGH. V1 recap:
  8a: Coordinator plan step consumes CR-08 exposure (`run_coordinator_cycle` →
  `exposed_tools` in summary + `agent_task_created` payload); cross-stage FIX —
  `readiness_check._resolve_strategy_payload` dereferences the Strategy-editor
  mirror revision so the editor path (draft→save→attach→Ready Check→RUN) works;
  e2e flow (a) full real-id pipeline (ingest→…→RUN→Result→History→Metrics→Trash→
  restore; INF-04 idempotent reuse, INF-05 no-latest-leak via shared
  `execution_key` + identical metrics, CR-03, monotonic audit+outbox), flow (b)
  UI-less Agent loop (directive→bundle→backtest→result→hypothesis + ownership
  boundary REJECTED), gateway parity suite (same report/denial code/capability
  gate on both lines). 8b: outbox→SSE fan-out all domains
  (`application/jobs/outbox_relay.py` scheduler checkpoint + `apps/api/sse.py`
  SseHub/poller/taxonomy, loss-tolerant INF-11); real scheduler
  (`application/jobs/maintenance.py`: INF-09 stale recovery audited,
  INF-03 QUEUED redelivery via `ACTOR_BY_QUEUE`, data queue operator-only);
  security headers + opt-in rate limiting (`RATE_LIMIT_ENABLED`, bounded memory)
  + `/v1/metrics` (golden signals + jobs depth + outbox lag + lease age;
  `unmatched` 404 sentinel). Reviews: 8a 0 findings; 8b 2 HIGH both real, fixed
  in-commit. **Test-infra:** integration tests rebuild the schema per test —
  parallel sessions MUST use an isolated DB (`TEST_DATABASE_URL=...entropia_auth`).
- **Next:** **post-V1 (continued)** — natural next in the backtest track: **Slice C —
  real indicator compute** (replace the engine's entry/exit PROXY with real
  indicator signals via Create-Package candidate generation; **only** `engine.py`'s
  entry/exit evaluation changes — run/manifest/result contracts stay fixed).
  Small follow-up: `risk_based`/`formula_based` sizing (now notional + warning).
  Other candidates (order in `docs/POST_V1_KICKOFF.md`): frontend SSE/metrics/login
  integration, CP real candidate generation, capability activations, deferred list
  (`summary["timeframe"]` resolution, tool-call status shadowing, retention
  auto-purge, data-queue redelivery, SSE streaming e2e, first-Admin provisioning).
  Ask the user which slice to start; full handoff: `docs/POST_V1_KICKOFF.md`.
