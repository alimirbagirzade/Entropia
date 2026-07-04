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
  Slice A, PR #41) + real bar-replay backtest engine (INF-12 Slice B, PR #43) +
  real built-in indicator compute (INF-12 Slice C, PR #45) + `risk_based`
  position sizing (INF-12 Slice C follow-up a, PR #47) + threshold condition
  blocks (INF-12 Slice C follow-up b, PR #49) + condition extensions
  (INF-12 Slice C follow-up b2, PR #51) + two-package indicator-vs-indicator
  (INF-12 Slice C follow-up, PR #53) + higher-timeframe bar resampling
  (INF-12 Slice C follow-up c, PR #55) + per-condition multi-timeframe reference
  (INF-12 Slice C follow-up i, PR #56)**. **Overall: ~77% complete** (V1=100%, post-V1 core=74%, frontend=15%).
  `main` after PR #56 (per-condition code `1c5cca0`; multi-timeframe code `def6c28`; indicator-vs-indicator code `9087c2b`; condition-extensions code `361df4c`; condition-blocks code `8766fae`; risk_based code `43cee29`; Slice C code `671d227`);
  alembic head = **`0021_local_auth`** (`human_credentials` + `auth_sessions`;
  Slices A/B/C + follow-ups (a)/(b)/(b2)/(#53)/(c)/(i) need no migration). **953 tests green** (939 + 14 per-condition multi-TF reference).
  Follow-up (c) — higher-timeframe bar resampling (PR #55): an indicator block may
  compute on a timeframe COARSER than the base bars (`timeframe` override was
  `timeframe_override_deferred`; now resamples). `domain/backtest/indicators.py`
  `timeframe_seconds()` + `_epoch_seconds`/`_htf_bucket` (ISO/`Z`/epoch → `floor(epoch/span)`
  timestamp bucketing, clock-free); `IndicatorSpec` +`resample_seconds: int|None`;
  `BlockEvaluator.update` splits into a base/HTF dispatcher + `_advance` (base-TF path
  BYTE-IDENTICAL to Slice C). HTF path aggregates base bars into the block's coarser
  candle (open=first, high=max, low=min, close=last) and calls `_advance` ONLY on candle
  CLOSE = first bar of the NEXT bucket → no look-ahead / no repaint; trailing partial
  candle never finalizes; validity/conditions tick in HTF candles. `indicator_plan.py`
  `_resolve_base_seconds` (reads pinned revision base TF) + `_resolve_timeframe`: coarser→
  `resample_seconds`, finer→`timeframe_finer_than_base`, equal→base compute, base-unknown→
  still resamples (degrades to base bars, deterministic). `market_data` repo read-only
  `get_base_timeframe_for_revision` (`ResolutionKind.BAR` `resolution_value`). `engine.py`
  passes `bar.timestamp` to evaluators + `multi_timeframe_blocks` diagnostic; `ENGINE_VERSION`
  → `backtest-engine-v2-multi-timeframe` (execution_key ns shift). +11 tests (unit +6 /
  integration +5). No migration.
  Follow-up (i) — per-condition multi-timeframe reference (PR #56): a nested condition's
  RHS reference indicator (`reference_package_ref`, the #53 two-package form) may compute on
  a timeframe COARSER than its parent block (fast `source` vs a slower reference that only
  advances on a completed reference candle → no look-ahead, symmetric with (c)).
  `domain/strategy/config.py` `ConditionBlock` +`reference_timeframe` (optional Literal,
  default `same_as_base_tf`; JSONB, no migration). `indicators.py` `ConditionSpec`
  +`reference_resample_seconds:int|None`; `ConditionEvaluator._advance_reference` buckets the
  RHS closes and advances it ONLY on a completed reference candle (`reference_resample_seconds
  is None` → advance-every-bar, BYTE-IDENTICAL to #53); `ConditionEvaluator.update` +`timestamp`
  kwarg; `BlockEvaluator._advance` threads `timestamp` to conditions + tracks `_form_ts` (forming
  HTF candle close time → a nested reference buckets against the parent candle, not raw base
  bars). Honest dar boundary: only the reference PACKAGE is resampled (bounded `reference`/
  constant `threshold` RHS stays on the block TF). `indicator_plan.py` `_resolve_reference_timeframe`
  resolves against `block_effective_seconds` (block resample span else base bars): coarser→
  `reference_resample_seconds`, equal→block compute, finer→`condition_reference_timeframe_finer_than_block`,
  base/block-unknown→still resamples; `_resolve_reference_package` now returns a 4-tuple; a
  reference-TF override with no reference package → `condition_reference_timeframe_without_package`.
  `engine.py` +`per_condition_timeframe_conditions` diagnostic; `ENGINE_VERSION` →
  `backtest-engine-v2-per-condition-timeframe` (execution_key ns shift). Review APPROVE 0
  CRITICAL/HIGH. +14 tests (unit +6 / integration +8). No migration. Honest boundary: >2-package
  (N-ary, ii) and non-MA/RSI reference keys (d) still deferred.
  Follow-up — two-package indicator-vs-indicator (PR #53): a nested `ConditionBlock`
  can pin a SECOND indicator package whose computed output series is the condition RHS
  (the canonical fast-MA vs slow-MA crossover; opens the (b2) honest boundary). Previously
  the RHS was only a constant `threshold` or a bounded single-package `reference` series.
  `domain/strategy/config.py` `ConditionBlock` +`reference_package_ref: PackageReference | None`
  (optional Pydantic/JSONB, no migration; precedence over threshold/bounded reference).
  `domain/backtest/indicators.py` `ConditionSpec` +`reference_key`/`reference_length`; new
  `_build_reference_indicator` factory (reuses `_MovingAverage`/`_Rsi`; RSI for `ta.rsi`,
  else MA); `ConditionEvaluator._ref_indicator` advanced inline from `close` each bar,
  `_rhs_value` precedence reference-indicator > bounded `reference` > constant `threshold`
  (warm-up `None` fails closed, LEVEL and CROSS). `indicator_plan.py::_resolve_reference_package`
  dereferences the 2nd pinned package to a `DIRECTIONAL_KEYS` key + look-back
  (`_REFERENCE_LENGTH_KEYS` else `default_length`; body NOT executed); fail-closed reasons
  `condition_reference_package_unresolved`/`_no_series`/`_package_on_range` (reference pkg on a
  `cond.between` RANGE = misconfig). `ENGINE_VERSION` → `backtest-engine-v2-indicator-vs-indicator`
  (execution_key ns shift); ENGINE + `apps/seed.py` unchanged (RHS self-computed in the evaluator).
  +12 tests (`test_backtest_indicator_vs_indicator.py` +6 incl. flagship condition-only fast/slow
  MA-cross → long; `test_condition_plan_resolution.py` +6); review APPROVE 0 CRITICAL/HIGH; no migration.
  Follow-up (b) — condition blocks (PR #49): THRESHOLD-ONLY nested condition GATE for
  the bar-replay engine. `domain/backtest/indicators.py` gains `ConditionSpec` +
  `ConditionEvaluator` (per-bar threshold check on a bar price field OR the parent
  block's `indicator_output` value vs a strategy constant; validity window mirrors the
  trigger's `_VALIDITY_BARS`; strict `>`/`<`; `until_opposite` clears on false; `None`
  source during warm-up fails closed), `CONDITION_KEYS={cond.above,cond.below}`,
  `_conditions_satisfied` (condition_block_rule aggregation); `BlockEvaluator.current_signal`
  gates the trigger; `IndicatorSpec` +`conditions`/`condition_rule`/`min_condition_support`
  (defaulted). `indicator_plan.py::_resolve_block` accepts
  `indicator_native_trigger_plus_condition` and dereferences the pinned condition
  package's `cond.*` dep into `ConditionSpec` (fail-closed: any unresolvable condition →
  whole block `unresolved`; threshold REQUIRED, source default `close`).
  `indicator_output_plus_condition` deferred in (b), now RESOLVED in (b2, below). `engine.py` feeds
  full OHLC to evaluators + `condition_blocks` diagnostics count; (b) `ENGINE_VERSION` →
  `backtest-engine-v2-condition-blocks`. `apps/seed.py` seeds `cond.above`/`cond.below`
  ESP resolvers. +28 tests; review APPROVE 0 CRITICAL/HIGH; no migration.
  Follow-up (b2) — condition extensions (PR #51): extends the (b) gate with crosses/between/
  series-vs-series RHS + condition-only directional signals — the honest boundary of single-package
  condition compute. `CONDITION_KEYS` → 5 (`cond.above/below` LEVEL, `cond.crosses_above/below`
  EDGE via `_prev_source`/`_prev_rhs`, warm-up `None` fail-closed; `cond.between` RANGE strict
  `lower<source<upper`), `CROSS_CONDITION_KEYS`/`RANGE_CONDITION_KEYS`, `condition_direction()`
  (crosses_above→long, crosses_below→short). `ConditionSpec` +`lower`/`upper`/`reference`
  (threshold Optional; `ConditionEvaluator._rhs_value` = reference series OR constant →
  series-vs-series). `IndicatorSpec` +`condition_only`: `BlockEvaluator` skips native `_detect`,
  fires on the RISING EDGE of the `_conditions_satisfied` gate (`_prev_gate`), directs via
  `_condition_only_direction` (shared polarity of required crosses), held for block validity,
  filtered by `block.direction`; `current_signal` returns `_active_dir` in condition_only.
  `indicator_plan.py` `_ACCEPTED_TRIGGERS` += `indicator_output_plus_condition`;
  `_resolve_condition` handles `between` (bounds REQUIRED + `lower<upper` → `condition_bounds_missing`/
  `_invalid`) + `reference` (`_reference_override` → threshold Optional); condition_only fail-closed
  reasons (`condition_only_no_directional_edge`/`_conflicting_direction`). Honest boundary
  (docstring): two SEPARATE packages need a 2nd `package_ref` (out of scope). `ENGINE_VERSION` →
  `backtest-engine-v2-condition-extensions`; `apps/seed.py` +`cond.crosses_above/below`+`cond.between`
  resolvers. +24 tests; review APPROVE 0 CRITICAL/HIGH; no migration.
  Slice C: `domain/backtest/indicators.py` — pure incremental (bounded-memory)
  Decimal TA compute (`ta.sma/ema/rma/wma` MA-cross + `ta.rsi` band cross;
  `ta.atr/vwap` recognized-but-non-directional), types `IndicatorSpec/SignalRule/
  IndicatorPlan` + `BlockEvaluator`, `BUILTIN_ENTRY_MODEL=builtin_indicator_native_trigger_v1`;
  `application/queries/indicator_plan.py::resolve_indicator_plan` dereferences the
  pinned `PackageRevision.dependency_snapshot` canonical keys (bodies NOT executed;
  native-trigger-only → `*_plus_condition`/timeframe/non-directional = `unresolved`
  warning, L4); `engine.py::run_engine(..., indicator_plan=None)` dual-mode (plan →
  real signals, else labelled breakout PROXY fallback); run/manifest/result
  contracts unchanged; no blocking review finding.
  Follow-up (a) — `risk_based` sizing (PR #47): `domain/backtest/engine.py::_position_size`
  gains a `risk_based` branch (`size=max(equity,0)*risk%/100/stop_loss_point` —
  deterministic, entry-price-independent, non-negative clamp) + helper
  `_sizing_is_honored` (explicit `base_position_size` + `risk_based_sizing` with a
  sub-config are honored; `formula_based` and a sub-config-less `risk_based` →
  notional fallback + L4 `position_sizing_method_unsupported`); manifest
  `ENGINE_VERSION=backtest-engine-v2-risk-based-sizing` (bumped from
  `-indicator-compute`; shifts the `execution_key` namespace so a stale notional
  result is not reused — INF-04/INF-05); +5 tests; review APPROVE 0 CRITICAL/HIGH;
  `formula_based`/Kelly still honest `unresolved`. Engine (Slice B):
  `domain/backtest/engine.py::run_engine` — pure single-pass
  bar-replay over `iter_bar_batches` (breakout entry PROXY labelled
  `entry_model=deterministic_bar_breakout_proxy_v1` + REAL protection stops
  percentage/trailing/absolute intrabar + costs + notional sizing clamped to
  `max(equity,0)`); `application/jobs/backtest_engine.py::run_backtest`
  (injectable `stream_bars`, ASSET_UNAVAILABLE/ENGINE_ERROR fail paths);
  manifest `ENGINE_VERSION` bumped v1→v2 by Slice C; run/manifest/result
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
- **Next:** **post-V1 (continued)** — **3 priority tiers:**
  
  **TIER 1 — Slice C remaining (backend, high-impact):**
  - **(ii) >2-package condition comparison** (N-ary reference schema, not just `reference_package_ref`; fast-MA vs slow-MA vs volume MA — extends the (i)/#56 `reference_package_ref`+`reference_timeframe` fields to N-ary)
  - **(d) Non-MA/RSI directional keys** (`ta.atr`/`ta.vwap` recognized-but-non-directional today; must become `DIRECTIONAL_KEYS` or stay `unresolved`; also blocks them as reference-package RHS)
  - **formula_based / Kelly sizing** (still notional fallback + `position_sizing_method_unsupported`; path-dependent, ungrounded in the foundation)
  
  **TIER 2 — Frontend + infra (user-facing, 0% today):**
  - Frontend SSE/metrics/login integration (WebSocket subscription, real-time backtest progress, user session)
  - Capability activations (gate new features per user role)
  - Admin provisioning dashboard (first-Admin onboarding)
  
  **TIER 3 — Data/ops (deferred, optional for MVP):**
  - Retention auto-purge (strategy/backtest history cleanup)
  - Data-queue redelivery (operator recovery tool)
  - SSE streaming e2e (handle connection drops gracefully)
  - Tool-call status shadowing (CR-08 follow-up)
  
  **Landed follow-ups (✅):**
  - (a) `risk_based` sizing **PR #47** — `formula_based`/Kelly still `unresolved`
  - (b) condition blocks **PR #49** — threshold gates
  - (b2) condition extensions **PR #51** — crosses/between/series-vs-series
  - indicator-vs-indicator **PR #53** — two-package reference
  - (c) higher-timeframe bar resampling **PR #55** — indicator block on a coarser TF (no look-ahead)
  - (i) per-condition multi-TF reference **PR #56** — a condition's RHS reference package on a coarser TF (no look-ahead); `ConditionBlock.reference_timeframe`
  
  Full roadmap: `docs/POST_V1_KICKOFF.md`.
