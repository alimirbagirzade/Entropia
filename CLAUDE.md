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
  (INF-12 Slice C follow-up i, PR #56) + N-ary reference chain
  (INF-12 Slice C follow-up ii, PR #57) + VWAP directional key
  (INF-12 Slice C follow-up d, PR #58) + formula_based Kelly criterion sizing
  (INF-12 Slice C follow-up, PR #60 + non-finite fail-closed fix PR #61) + position_size_limits
  min/max cap wiring (INF-12 Slice C follow-up, PR #63) + TIER 2 frontend real-auth
  login/signup/logout (PR #65, MERGED) + TIER 2 frontend SSE live-invalidation
  (PR #67, MERGED) + TIER 2 frontend /v1/metrics ops dashboard (PR #69, MERGED) + TIER 2
  frontend live-data backtest pages RUN & Results History (PR #72, MERGED) + TIER 2
  frontend Arrange Metrics & Analysis Lab live pages (PR #74, MERGED) + first-Admin
  bootstrap provisioning (post-V1 TIER 2 backend, PR #76, MERGED) + TIER 2 frontend
  live-data Panel / Management / Logs page (PR #78, MERGED) + TIER 2 frontend history
  compare/soft-delete & profile-hydrated Result metrics rebind (PR #80, MERGED) + TIER 2
  frontend Future Dev capability registry page (PR #82, MERGED) + first-Admin provisioning
  dashboard + bootstrap-status endpoint (post-V1 TIER 2, PR #84, MERGED) + TIER 2 frontend
  live-data Admin Trash restore page (PR #86, MERGED) + frontend auth invalidation on
  signup/login (PR #88, MERGED) + deterministic Create Package candidate generation
  (INF-12, PR #89, MERGED) + TIER 2 frontend live-data Create Package request page
  (PR #91, MERGED) + CP request lifecycle actions + Pre-Check page (PR #93, MERGED) + gated
  capability operational POSTs into Future Dev (PR #95, MERGED) + TIER 2 frontend live-data
  Package Library catalog page (PR #97, MERGED)**.
  **Overall: ~94% complete** (V1=100%, post-V1 core=88%, frontend=88%).
  `main` after PR #97 (`af7c66b`; Package Library feat `53394fe` MERGED; capability-POSTs feat `652dfde` MERGED; CP-actions/Pre-Check feat `e8f8982` MERGED; CP-create-page feat `79fbd24` MERGED; CP-Gen candidate-generation feat `5cc62cc` MERGED; auth-invalidation feat MERGED (PR #88); trash-page feat `3ccb50d` MERGED; provisioning-dashboard feat `b56f621` MERGED; capability-page feat `3d7977e` MERGED; history-compare feat `491ac03` MERGED; panel-page feat `726ffcc` MERGED; first-Admin bootstrap feat `a53cf34` MERGED; live-pages feat `499bd8b` MERGED; backtest-pages feat `10a0007` MERGED; metrics feat `d3039e7` MERGED; login feat `58781e4` MERGED; SSE feat `5ddb14f` MERGED; position_size_limits feat `5ef5525`; Kelly feat `3f254bc` / non-finite fail-closed fix `3a92e7d`; VWAP code `d27b2bb`; N-ary code `44099a7`; per-condition code `1c5cca0`; multi-timeframe code `def6c28`; indicator-vs-indicator code `9087c2b`; condition-extensions code `361df4c`; condition-blocks code `8766fae`; risk_based code `43cee29`; Slice C code `671d227`);
  alembic head = **`0021_local_auth`** (`human_credentials` + `auth_sessions`;
  Slices A/B/C + follow-ups (a)/(b)/(b2)/(#53)/(c)/(i)/(ii)/(d) + Kelly sizing + position_size_limits + first-Admin bootstrap + bootstrap-status read endpoint + CP-Gen deterministic candidate generation need no migration). **1048 tests green** (1015 + 13 first-Admin bootstrap [env-unset baseline / match+no-admin → Admin+audit+outbox / active-Admin fail-closed / non-matching baseline / case+whitespace normalization / settings env read / route pass-through] + 8 bootstrap-status read endpoint: unit configured-flag + integration window open/closed vs a real DB + route reads the setting + 12 CP-Gen candidate generation: reproducibility / order-independence / output_contract+resolved_refs hash sensitivity / GENERATOR_VERSION namespace shift / fail-closed directional→ta.* + condition→cond.* + empty-resolved skip / output_type alias / DESCRIPTION uncertainty / test_plan dep listing).
  TIER 2 frontend — real-auth login/signup/logout (PR #65, MERGED): **FRONTEND-ONLY**
  (backend unchanged, no migration, backend test base stays 1015). Connects the `frontend/` shell
  (Vite 8 + React 18 + react-router 6 + @tanstack/react-query 5 + react-hook-form) to the landed
  local-auth backend (`/v1/auth/*`, opaque Bearer sessions) so humans get a real session instead of
  only the dev `X-Actor-Id` header. NEW `lib/session.ts` (external Bearer-token + user store,
  `useSyncExternalStore`-driven), `lib/auth.ts` (`useLogin`/`useSignup` auto-login/`useLogout`
  best-effort/`useSessionToken`), `pages/Login.tsx` (standalone `/login`, react-hook-form,
  login/signup toggle, canonical `ApiError` shown verbatim); `apiClient.ts` attaches
  `Authorization: Bearer` alongside `X-Actor-Id` (server honours only the header its `AUTH_MODE`
  trusts — no cross-mode spoofing); `Layout.tsx` `AuthControl` (Log in link / user + Log out;
  `DevActorControl` hidden while a session is active); `App.tsx` `/login` route; `types.ts`
  `AuthUser`/`LoginResponse`/`SignUpResponse`; `global.css` `.btn*`/`.auth-*`. Frontend 9/9 vitest
  (3 baseline + 6 new), typecheck + lint clean, build green. Honest boundary: no anonymous→`/login`
  route guard (dev mode allows anonymous browsing); first-Admin provisioning still absent upstream
  (signup → baseline role).
  TIER 2 frontend — SSE live-invalidation (PR #67, awaiting user merge): **FRONTEND-ONLY**
  (backend + its SSE taxonomy `apps/api/sse.py` consumed unchanged, no migration, backend test base
  stays 1015). Fills the `frontend/src/lib/sse.ts` stub (was heartbeat-only; `connectEvents`'
  `queryClient` param was an unused Stage-1 TODO) so each backend SSE frame invalidates react-query
  keys. NEW exports: `SseEventName` (taxonomy union), `EVENT_QUERY_KEYS` (`backtest.run.updated`→
  `[["backtests"]]`, `job.updated`→`[["jobs"]]`, `agent.task.updated`→`[["agent-tasks"]]`,
  `audit.event.created`→`[["audit"]]`, `resource.changed`→`[]` catch-all full refresh; react-query
  prefix-matches so `["backtests"]` covers `["backtests", runId, …]`), `SSE_EVENT_NAMES`; private
  `invalidateForEvent` (empty list→full refresh else per-prefix `invalidateQueries({queryKey})`).
  `connectEvents(queryClient, onStatus?)` signature + `SseStatus` UNCHANGED (`Layout.tsx` call-site
  untouched); handlers detached on dispose (symmetric add/remove) before `source.close()`; a
  reconnect (`hasOpened` flag: first `open` no-op, subsequent `open`→full `invalidateQueries()`)
  self-heals across a connection gap (INF-11). NEW `test/sse.test.ts` — 7 vitest via an in-memory
  `EventSource` double (`vi.stubGlobal`); **frontend 16/16** (9 prior + 7 new), typecheck + lint
  clean, build green. Honest boundary: no live page binds these keys yet (Stage 5/6 RUN / History /
  Metrics / Analysis Lab still placeholders) → visible payoff arrives with those pages;
  `EVENT_QUERY_KEYS` is their forward contract.
  TIER 2 frontend — /v1/metrics ops dashboard (PR #69, awaiting user merge): **FRONTEND-ONLY**
  (backend `apps/api/routes/metrics.py` Prometheus text exposition consumed unchanged, no migration,
  backend test base stays 1015). Surfaces the Stage 8b `GET /v1/metrics` `text/plain` exposition as a
  read-only ops dashboard. NEW `lib/metrics.ts` (dependency-free `parsePrometheus` — `# TYPE`/`# HELP`,
  labeled + scalar samples, histogram `_bucket`/`_sum`/`_count` grouped via `ownerFamily`, `+Inf`/`NaN`,
  label escapes, notes — + `summarizeMetrics`→`MetricsSummary`: four golden signals
  (`requestsTotal`/`serverErrors` 5xx/`clientErrors` 4xx/`inFlight`/`avgLatencyMs`=histogram sum÷count),
  sorted `jobsDepth`+total, `outboxLagSeconds`, `leaseAgeSeconds`, `degraded` DB-down detection,
  `familyCount`); NEW `apiClient.ts` `apiGetText`/`api.getText` (raw-text GET for the `text/plain`
  endpoint, mirrors `apiRequest` auth headers; existing `api.*` UNCHANGED); NEW `hooks.ts` `useMetrics`
  (react-query `["metrics"]`, `refetchInterval` 5s); NEW `pages/Metrics.tsx` (golden-signal tiles +
  status-class badges + operational gauges + jobs-depth table + degraded banner); `nav.ts`+`App.tsx`
  NEW adminOnly `System Metrics` item at `/panel/metrics` (`ALL_NAV_ITEMS` 22→23), real route replaces
  the placeholder; `global.css` `.metrics-table`. +13 vitest (10 parser/summary + 3 component via mocked
  fetch) → **frontend 29/29**, typecheck + lint clean, build green. Honest boundary: metrics has no SSE
  event → the dashboard POLLS every 5s (`["metrics"]` still swept by `resource.changed`); route reachable
  by URL (scrape endpoint unauthenticated by design), nav item admin-gated. Remaining TIER 2: live-data
  Stage 5/6 pages (bind SSE `EVENT_QUERY_KEYS`) + capability activations + first-Admin provisioning.
  TIER 2 frontend — live-data backtest pages (PR #72, MERGED): **FRONTEND-ONLY** (backend Stage 5a/5b
  backtest surface consumed unchanged, no migration, backend test base stays 1015). Binds the FIRST
  live pages to the SSE forward contract: `/backtest/run` + `/backtest/history` placeholders become
  real pages → SSE live-invalidation payoff now visible. NEW `lib/backtest.ts`: wire types mirroring
  backend projections verbatim (`DefaultMainboard`/`BacktestRunAdmission`/`BacktestRun`/
  `BacktestResultDetail`/`HistoryRow`/`HistoryPage`); `HISTORY_SORTS` (6 canonical `HistorySort` wire
  values + V18 labels), `KEY_METRIC_COLUMNS` (KEY_METRIC_KEYS order), `TERMINAL_RUN_STATES`;
  `formatMetricValue` (signed_percent/percent/decimal2/integer; null value renders its availability
  label, NEVER 0 — L4) + locale-free `formatUtc`; hooks `useDefaultMainboard` (`["mainboard","default"]`),
  `useBacktestRun` (`["backtests","run",id]`, poll fallback stops on terminal state — SSE primary,
  INF-11), `useBacktestResult` (immutable, staleTime 5m), `useResultsHistory`
  (`["backtests","history",sort,cursor]`, keyset cursor, placeholderData keeps prev page); 202
  mutations `useRequestBacktestRun`/`useRetryBacktestRun` (both invalidate `["backtests"]`); ALL path
  params `encodeURIComponent`'d (review fix — un-encoded `?result=` could URL-normalize onto another
  API GET endpoint). NEW `pages/BacktestRun.tsx` (two modes: `?result=` immutable deep-link doc 15
  §8.5 — History "View" lands here; workbench composition card from `GET /mainboards/default` → RUN
  admission → `?run=` durable tracking doc 15 §4; failure verbatim + Retry swaps onto the NEW run id;
  `warning_count` badge). NEW `pages/ResultsHistory.tsx` + `components/ResultDetail.tsx`
  (server-sorted keyset index — client never re-orders; digest cells; View → `?result=`; summary kv +
  metrics value/availability table + manifest excerpt + artifact counts). `App.tsx` `REAL_PATHS` set;
  `nav.ts` UNCHANGED (23 items). NEW shared `test/helpers/apiStub.ts` route-aware fetch double
  ("<METHOD> <fragment>" keyed); +7 vitest → **frontend 36/36**, typecheck + lint clean, build green.
  Review: 1 finding (path-param encoding) empirically CONFIRMED + fixed in-commit; 0 CRITICAL/HIGH.
  Honest boundary: Arrange Metrics (`/backtest/metrics`) + Analysis Lab (`/analysis-lab`) still
  placeholders (`["jobs"]`/`["agent-tasks"]`/`["audit"]` keys unbound); history compare/soft-delete
  affordances deferred with them.
  TIER 2 frontend — Arrange Metrics & Analysis Lab live pages (PR #74, MERGED): **FRONTEND-ONLY**
  (backend `routes/metric_profile.py` + `routes/agent_lab.py` consumed unchanged, no migration,
  backend test base stays 1015). The last two placeholders with a full backend surface become live
  pages; every Analysis Lab query key is prefixed `["agent-tasks"]` → the PR #67 `agent.task.updated`
  map (SECOND SSE forward-contract key) now sweeps live pages. NEW `lib/metricProfile.ts` (wire types
  `MetricDefinition`/`MetricRegistry`/`ResolvedMetricProfile` incl. `editable_profile_id` — 
  `"system_default"` until the first Apply forks a personal root — /`MetricProfileRevision` with
  server-derived `reason`; hooks `useMetricDefinitions` `["metric-definitions"]` 5m staleTime +
  `useResolvedMetricProfile` `["metric-profile","resolved"]`; `useApplyMetricProfile` — Apply /
  Apply & Lock / pure-Unlock are ALL the same append POST with `expected_profile_revision_id` OCC
  guard, 409 verbatim; presentation-only CR-07). NEW `pages/ArrangeMetrics.tsx` (registry table +
  resolved selection; future/experimental never checkable; locked profile → edits disabled, pure
  Unlock only; draft re-seeds on every server head move; empty selection blocks Apply). NEW
  `lib/agentLab.ts` (wire types `AgentRuntime`/`AgentTaskCard`/`AgentOverview`/`AgentTaskDetail`/
  `HypothesisCard` + `DirectiveAdmission`/`LabMessageResponse`/`RuntimeControlAccepted`; hooks
  `useAgentOverview` 15s poll fallback INF-11 / `useAgentTasks` keyset / `useAgentTask` /
  `useHypotheses` — ALL under `["agent-tasks"]`; 202 mutations `useQueueDirective`
  (`DIRECTIVE_PRIORITIES=normal|high`, `autonomous` never human-selectable), `useSendLabMessage`,
  `usePauseRuntime`/`useResumeRuntime`/`useStopRun` with runtime `row_version` as `If-Match` OCC
  token via `postWithIfMatch`). NEW `pages/AnalysisLab.tsx` (`RuntimeCard` pause/resume/stop — stop
  passes the active TASK id, run id ≡ task id: backend `stop_run` does `get_task(session, run_id)`;
  `QueueCard` + `TaskDetailCard` checkpoints/directives; `DirectiveCard` composers with
  `delivery_policy` echo; `HypothesesCard`; 403 envelope verbatim for non-Admin/Supervisor).
  `App.tsx` `REAL_PATHS` 4→6; `nav.ts` UNCHANGED (23 items). +9 vitest (4 arrangeMetrics + 5
  analysisLab, apiStub reuse) → **frontend 45/45**, typecheck + lint clean, build green. Honest
  boundary: no dedicated SSE event for metric-profile changes (only `resource.changed` full refresh;
  Apply invalidates `["metric-profile"]` same-tab); role-gated `GET /agent-events/stream` NOT wired
  as a second EventSource; task/hypothesis pagination past page 1 + status-filter UI deferred;
  `GET /backtest-results/{id}/metrics` (profile-hydrated Result view) NOT yet consumed — ResultDetail
  still renders raw persisted rows (natural follow-up); `["audit"]` still unbound (Panel/Logs) and
  `["jobs"]` has NO backend list surface at all; history compare/soft-delete still deferred.
  post-V1 TIER 2 — first-Admin bootstrap provisioning (PR #76, MERGED): **BACKEND-ONLY**
  (frontend unchanged, 45/45 stays; NO migration, alembic head stays 0021_local_auth). Closes the
  PR #38 honest boundary (signup always baseline; no path to a first Admin). NEW
  `config/settings.py` `bootstrap_admin_email` (env `ENTROPIA_BOOTSTRAP_ADMIN_EMAIL`, default `""`
  = disabled → zero behavior change unless the operator opts in); `application/commands/auth.py`
  `bootstrap_admin_matches` (case/whitespace-normalized email match) + `sign_up` bootstrap branch —
  a matching signup becomes Admin ONLY while no active Admin exists (fail-closed otherwise →
  baseline role), serialized by the same-tx advisory lock of the last-admin demote path
  (`identity_repo.lock_admin_count`) + `unique(human_users.email)`; emits `user.admin_bootstrapped`
  audit + `admin_bootstrapped` outbox in the SAME tx (`_audit_and_outbox`). `apps/api/routes/auth.py`
  passes the setting through server-side only — the route schema has NO role field, so client
  escalation is structurally impossible. NEW `tests/unit/test_auth_bootstrap_unit.py` +
  `tests/integration/test_auth_bootstrap_admin.py` (+13) → backend **1028**; ruff/format/mypy clean;
  review APPROVE 0 CRITICAL/HIGH. Honest boundary: backend MECHANISM only — no provisioning
  dashboard yet (later frontend slice); applies at signup time only (no retro-promotion of an
  existing account).
  TIER 2 frontend — live-data Panel / Management / Logs page (PR #78, MERGED): **FRONTEND-ONLY**
  (backend `routes/admin_panel.py` + `routes/audit.py` consumed unchanged, no migration, backend
  test base stays 1028). The `/panel` placeholder becomes the real page and the LAST bindable SSE
  key `["audit"]` gets its first bound page — `audit.event.created` (PR #67 map) now sweeps a live
  page. NEW `lib/adminPanel.ts`: Management reads under `["admin"]` (`useRegisteredUsers` keyset +
  `useSystemActors` + `useRoleMatrix` 5m staleTime); Logs/Audit reads under `["audit"]`
  (`useAdminLogs` filtered — family/severity/actor_type/q/correlation_id, an empty filter param is
  NEVER sent — + `useLogEvent` detail + `useAuditEvents` raw stream); `useAssignRole`
  `PATCH /admin/users/{id}/role` with OCC `expected_head_revision_id = user.version` (stale tab →
  409 verbatim), role options from the server role-matrix ASSIGNABLE rows (never hard-coded),
  invalidates `["admin"]`+`["audit"]`; `LOG_FAMILIES`/`LOG_SEVERITIES`/`LOG_ACTOR_TYPES` mirror the
  server taxonomy. NEW `pages/Panel.tsx` 5 cards (UsersCard inline role assignment /
  SystemActorsCard / RoleMatrixCard `policy_revision` / LogsCard detail + correlation chain /
  AuditStreamCard); forward-only cursor-stack pagination; non-Admin sees the 403 envelope verbatim.
  `App.tsx` `REAL_PATHS` 6→7 (`/panel`); `nav.ts` UNCHANGED (23 items). NEW `test/panel.test.tsx`
  (+6) → **frontend 51/51**, typecheck + lint clean, build green; review 0 CRITICAL/HIGH. Honest
  boundary: `["jobs"]` has NO backend list surface — PERMANENT (run projections + /v1/metrics
  jobs-depth only); users/system-actors have no dedicated SSE event (own mutations +
  `resource.changed` sweep); history compare/soft-delete + profile-hydrated
  `GET /backtest-results/{id}/metrics` binding (ResultDetail rebind) — landed next in PR #80.
  TIER 2 frontend — history compare/soft-delete + profile-hydrated Result metrics (PR #80, MERGED):
  **FRONTEND-ONLY** (backend `routes/results_history.py` compare/delete + `routes/metric_profile.py`
  result-metrics hydration consumed unchanged, no migration, backend test base stays 1028). The
  last two landed-but-unconsumed backtest surfaces bound (doc 16 §8.3/§7 + doc 17 §9.1).
  `lib/backtest.ts` NEW wire types `CompareEntry`/`CompareField`/`CompareResponse`
  (`context.fields{a,b,differs}` + `context_differs`) + `ResultMetricsProfile`/`ResultMetricsView`;
  hooks `useCompareResults(pair)` (READ over two immutable results — POST only the transport;
  `["backtests","compare",a,b]`, 5m staleTime, pick order preserved), `useResultMetrics(resultId)`
  (keyed `["metric-profile","result-metrics",id]` — deliberately NOT `["backtests"]` so an Arrange
  Metrics Apply sweeps the view; cross-tab rides `resource.changed`), `useSoftDeleteResult`
  (`POST /backtest-results/{id}/delete`, no OCC token — the history projection carries no
  row_version; command idempotent + owner/Admin-gated server-side; invalidates `["backtests"]`).
  `pages/ResultsHistory.tsx` compare selection capped at 2, checkbox gated by server
  `allowed_actions.compare`; `ComparePanel` renders the server context diff VERBATIM (differs
  badges, objects as JSON, "informational only; neither result is ranked" — RH-09); two-step
  confirm Delete gated by `allowed_actions.soft_delete` (deleting a compared row closes the panel).
  `components/ResultDetail.tsx` Metrics section rebound to the hydrated projection (profile caption
  personal/system default · locked · registry v1) with persisted-rows fallback while loading/on
  error (L4). NEW `test/historyActions.test.tsx` (+4) + `test/resultMetricsView.test.tsx` (+3);
  `backtestRun.test.tsx` deep-link test stubs the metrics route FIRST (apiStub ordered fragment
  match — detail fragment is a substring of the metrics URL) → **frontend 58/58**, typecheck +
  lint clean, build green; review 0 CRITICAL/HIGH. Honest boundary: compare is exactly two results
  (server min/max_length=2); soft-delete sends no OCC token; restore is the Admin Trash flow
  (frontend Trash page landed in PR #86).
  Follow-up (ii) — N-ary reference chain (PR #57): a nested condition's RHS extends from
  a single reference package (#53/#56) to an ORDERED chain of >2 separately-pinned indicator
  packages (`source [cmp] ref0 [cmp] ref1 ...` — the classic `fast > slow > slowest` MA fan;
  ascending mirror for downtrends). Single-reference path BYTE-IDENTICAL to #53/#56 (one-leg
  chain reduces exactly). `domain/strategy/config.py` `ReferenceLeg` model + `ConditionBlock`
  `+additional_reference_package_refs: list[ReferenceLeg]|None` (JSONB, no migration).
  `domain/backtest/indicators.py` `ReferenceSeriesSpec(key,length,resample_seconds)`;
  `ConditionSpec +extra_references`; `_ReferenceSeries` (per-leg coarser-TF resampling, no
  look-ahead — per-leg port of (i) `_advance_reference`); `_chain_ordered` (strict monotonic,
  `None` fails closed); `ConditionEvaluator` evaluates a chain over source + all RHS legs
  (`_ref_series`/`_prev_ref_values`/`_rhs_values` lists); warm-up on ANY leg fails whole chain
  closed. `indicator_plan.py` `_resolve_reference_package` → 5-tuple (+extras);
  `_resolve_additional_references` (per-leg key/timeframe/length); fail-closed
  `condition_additional_reference_without_primary`/`_unresolved:<i>`/`_no_series:<i>`; a leg on
  a `cond.between` RANGE rejected via `condition_reference_package_on_range`. `engine.py`
  +`nary_reference_conditions` diagnostic; `ENGINE_VERSION` → `backtest-engine-v2-nary-reference`
  (execution_key ns shift). Review APPROVE 0 CRITICAL/HIGH. +17 tests (unit +7 / integration +10).
  No migration. Honest boundary: (d) non-MA/RSI reference keys still deferred.
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
  
  **TIER 1 — Slice C backend follow-ups: ✅ EFFECTIVELY COMPLETE (all landed):**
  - ~~**(d) `ta.vwap` directional key**~~ ✅ **LANDED (PR #58)** — Slice C indicator-compute follow-ups effectively complete (`ta.atr` correctly stays non-directional by nature).
  - ~~**formula_based / Kelly sizing**~~ ✅ **LANDED (PR #60 + non-finite fail-closed fix PR #61)** — Kelly criterion honored; `custom_formula` + adaptive/rolling Kelly stay honest `unresolved` (no safe eval / path-dependent look-ahead).
  - ~~**`position_size_limits` (min/max cap) wiring**~~ ✅ **LANDED (PR #63)** — new `_clamp_to_limits` at the `_raw_position_size → _position_size` boundary clamps EVERY sizing method (base/risk_based/Kelly/notional); `ENGINE_VERSION=backtest-engine-v2-position-size-limits`; +15 tests → 1015; no migration. **TIER 1 backend is now DONE → next natural slice is TIER 2 (frontend/infra).**
  
  **TIER 2 — Frontend + infra (user-facing; login + SSE + /v1/metrics + backtest pages + Arrange Metrics/Analysis Lab + first-Admin bootstrap + Panel/Logs landed → PR #65, #67, #69, #72, #74, #76, #78):**
  - ✅ **Login / session integration (PR #65)** — real Bearer login/signup/logout wired into the shell (`lib/session.ts` + `lib/auth.ts` + `pages/Login.tsx` + `apiClient.ts` Bearer header + `Layout.tsx` AuthControl).
  - ✅ **SSE live-invalidation (PR #67)** — `frontend/src/lib/sse.ts` stub filled: `EVENT_QUERY_KEYS` maps each SSE taxonomy event → react-query key prefix (`backtest.run.updated`→`["backtests"]`, `job.updated`→`["jobs"]`, `agent.task.updated`→`["agent-tasks"]`, `audit.event.created`→`["audit"]`, `resource.changed`→full refresh) + reconnect self-heal; `connectEvents` signature unchanged; +7 vitest → 16/16. Honest boundary: no live page binds these keys yet (Stage 5/6 pages still placeholders) → payoff arrives with those pages.
  - ✅ **`/v1/metrics` dashboard (PR #69, MERGED)** — `lib/metrics.ts` Prometheus text-exposition parser + `apiGetText`/`useMetrics` (5s poll) + `pages/Metrics.tsx` (golden-signals/jobs-depth/outbox-lag/lease-age panels) + adminOnly `System Metrics` nav item at `/panel/metrics`; +13 vitest → 29/29; frontend-only, no migration.
  - ✅ **Live-data backtest pages (PR #72, MERGED)** — RUN & Backtest Results (`/backtest/run` — admission + `?run=` durable tracking + `?result=` immutable deep-link) + Results History (`/backtest/history` — server sorts + keyset cursor) bound to the SSE `["backtests"]` key via NEW `lib/backtest.ts` hooks; +7 vitest → 36/36; frontend-only, no migration.
  - ✅ **Arrange Metrics + Analysis Lab live pages (PR #74, MERGED)** — `/backtest/metrics` profile editor (OCC Apply/Lock/Unlock via `lib/metricProfile.ts`) + `/analysis-lab` agent workspace (`lib/agentLab.ts` — every key under `["agent-tasks"]` → second SSE key live; If-Match runtime controls); +9 vitest → 45/45; frontend-only, no migration.
  - ✅ **Panel / Management / Logs live page (PR #78, MERGED)** — `/panel` real page; the LAST bindable SSE key `["audit"]` bound via `lib/adminPanel.ts` (Management under `["admin"]`, Logs/Audit under `["audit"]`; `useAssignRole` OCC `expected_head_revision_id` with role options from the server role-matrix assignable rows; `pages/Panel.tsx` 5 cards) + `test/panel.test.tsx`; +6 vitest → 51/51; frontend-only, no migration. `["jobs"]` has NO backend list surface — permanent honest boundary.
  - ✅ **History compare/soft-delete + profile-hydrated Result metrics rebind (PR #80, MERGED)** — `useCompareResults`/`useResultMetrics`/`useSoftDeleteResult` (`lib/backtest.ts`) + `ComparePanel` verbatim context diff (RH-09, never ranked) + two-step confirm Delete gated by server `allowed_actions`; ResultDetail Metrics bound to the doc-17 §9.1 hydrated projection with persisted-rows fallback (L4); +7 vitest → 58/58; frontend-only, no migration.
  - ✅ **First-Admin bootstrap provisioning (PR #76, MERGED — backend)** — `ENTROPIA_BOOTSTRAP_ADMIN_EMAIL` opt-in: a matching signup is provisioned as Admin ONLY while no active Admin exists (fail-closed otherwise); advisory-lock (`identity_repo.lock_admin_count`) race-safe; `user.admin_bootstrapped` audit + outbox same tx; role decision server-side only (route schema has no role field); +13 tests → backend 1028; no migration.
  - ✅ **Future Dev capability registry page (PR #82, MERGED)** — `/future-dev` placeholder
    becomes the real page: the Stage 7b Capability Registry (`routes/capability.py`, doc 22)
    rendered as-is + Admin-only lifecycle transition. NEW `lib/capability.ts` (wire types
    verbatim; doc-22 §9.1/§9.2 taxonomy MIRROR `CAPABILITY_STATES`/`ALLOWED_TRANSITIONS`/
    `ACTIVATION_GATES` — select/checklist hydration only, server re-validates every dispatch;
    `gateComplete` mirrors server `_gate_complete`; `buildGatesSnapshot` note-preserving merge;
    hooks under `["capabilities"]` — no dedicated SSE event, swept by `resource.changed`;
    `useTransitionCapability` OCC `expected_registry_version` + REQUIRED fresh `Idempotency-Key`
    UUID, invalidates `["capabilities"]`+`["audit"]`) + `pages/FutureDev.tsx` (registry table,
    detail card with gate checklist + provenance, `TransitionComposer` — legal doc-22 targets
    only / reason required / untouched checklist OMITS `dependency_snapshot` / errors verbatim /
    mutation state owned by CARD so the accepted message survives the registry_version-bump
    remount; read-only Graphic View overview CR-09) + `App.tsx` `/future-dev` REAL_PATHS 7→8
    (`nav.ts` unchanged, 23 items). +9 vitest (7 component apiStub ORDERED — detail fragment
    precedes `/capabilities` list prefix — + 2 gate-merge unit) → **frontend 67/67**;
    review 0 CRITICAL/HIGH (3 MEDIUM/LOW self-review fixed in-commit); frontend-only, no
    migration, backend base stays 1028. Honest boundary: gated operational POSTs
    (`/view-datasets/query`, `/analysis-artifacts`) stay UNWIRED — no V1 UI workflow; server
    returns `CAPABILITY_NOT_ACTIVE` below Limited/Active (CR-09/FD-02); composer not role-gated
    (UI visibility is never authorization, doc 22 §3 — non-Admin sees 403 verbatim).
  - ✅ **First-Admin provisioning dashboard + bootstrap-status endpoint (PR #84, MERGED)** — closes
    the PR #76 boundary (backend mechanism landed, no UI). Backend (2 files + 2 tests):
    `application/commands/auth.py` pure `bootstrap_is_configured(bootstrap_email)` + read-only async
    `bootstrap_status(session, *, bootstrap_admin_email) -> {bootstrap_configured, active_admin_exists}`
    (booleans only, no PII; `active_admin_exists = count_active_admins(session) > 0`; a HINT — the
    `sign_up` provisioning branch stays advisory-lock guarded, this endpoint never provisions) +
    `apps/api/routes/auth.py` `GET /auth/bootstrap-status` → `BootstrapStatusResponse` (anonymous
    entry surface like sign-up/login; setting passed server-side only, no email field in the schema).
    Frontend (2 new + 3 edits + 1 test): NEW `lib/provisioning.ts` `BootstrapStatus` +
    `useBootstrapStatus` (`["auth"]` key, swept by `resource.changed`) + `pages/Provisioning.tsx`
    (`BootstrapWindow` `windowGuidance` open/closed×configured + `GET /me` identity via `useMe` +
    read-only `BootstrapExplainer`; Admin → Panel link, no duplicated role assignment) + `nav.ts` NEW
    non-`adminOnly` `Admin Provisioning` at `/panel/provisioning` (reachable pre-elevation;
    `ALL_NAV_ITEMS` 23→24) + `App.tsx` REAL_PATHS/route. +8 backend (unit + integration) → 1036, +6
    vitest (`provisioning.test.tsx` + `nav.test.tsx`) → 73; CI 3/3 green; no migration, alembic head
    stays 0021_local_auth, ENGINE_VERSION unchanged. Honest boundary (PERMANENT): provisioning stays
    server-side + signup-time only (no runtime provisioning API) — the page reads status and documents
    the flow, it never provisions; `active_admin_exists` anonymous-exposed by design (single boolean
    deployment fact, no PII, the first Admin is not yet authenticated); ongoing role management stays
    in the Panel.
  - ✅ **Frontend Admin Trash restore page (PR #86, MERGED)** — the `/trash` placeholder becomes the
    real page, binding the backend Stage 6c restore surface (`routes/trash.py`, doc 20 §7). **FRONTEND-ONLY**
    (backend unchanged, no migration, alembic head stays 0021_local_auth, ENGINE_VERSION unchanged, backend
    test base stays 1036). NEW `lib/trash.ts`: wire types mirroring `queries/trash.py` `_row`/detail +
    `commands/deletion.py` restore return (`TrashEntry`/`TrashEntriesPage`/`TrashEntryDetail`/`RestoreResult`);
    hooks under `["trash"]` (no dedicated SSE event — swept by `resource.changed`): `useTrashEntries`
    (q/object_type filter, keyset cursor, `placeholderData`) + `useTrashEntry` (enabled-gated); `useRestoreEntry`
    — OCC `expected_head_revision_id = entry.row_version` + a fresh `Idempotency-Key` per attempt, invalidates
    `["trash"]` + `["audit"]` (the `adminPanel.useAssignRole` pattern); `purgeStatusTone` badge helper. NEW
    `pages/Trash.tsx`: `TrashCard` (object_type select hydrated from server `meta.object_types` — no hard-coded
    list; q search; keyset pager; table) — Restore shown ONLY on server-truth `restore_eligible` rows, failures
    surface the `ApiError` verbatim; `TrashRow` + `TrashDetail` (deletion/dependency snapshot, purge/restore
    control state, tombstone; `snapshotStyle` inline pre wrap+scroll). `App.tsx` `/trash` joins REAL_PATHS + real
    Route; `nav.ts` UNCHANGED (the `/trash` adminOnly item already existed as a placeholder). NEW
    `test/trash.test.tsx` (+7: index+recoverable total / restore_eligible gating / OCC+Idempotency-Key restore /
    object_type query param / snapshot detail / `["trash"]` invalidation refetch / 403 verbatim) → **frontend
    73 → 80**; typecheck + lint clean, build green; review 0 CRITICAL/HIGH. Honest boundary (PERMANENT): Trash
    **purge** (destructive, needs `confirmation_phrase` / re-auth proof) is OUT OF SCOPE for this restore-focused
    slice — a separate re-auth slice; Trash is Admin-only server-side (a non-Admin sees the 403 envelope verbatim
    — UI visibility is never authorization).
  
  - ✅ **CP-Gen deterministic candidate generation (PR #89, MERGED — BACKEND)** — the
    `submit_candidate_generation` V1 stub *compute* becomes a deterministic candidate-manifest
    pipeline (doc 06 §5). NEW `domain/create_package/candidate.py` (pure, no I/O):
    `GENERATOR_VERSION="cp-candidate-gen-v1"` (ENGINE_VERSION analogue — bumping it shifts the
    `candidate_hash` namespace, INF-04/INF-05), frozen `CandidateManifest`, `build_candidate_manifest`
    + `candidate_hash = "sha256:" + content_hash(manifest.as_dict())` (order-independent via
    `_summarize_resolved` sorted by `canonical_key`), fail-closed `_output_kind` (`kind`/`output_type`
    alias) + `_validate_contract_against_deps` (`directional_signal`→needs `ta.*`, `boolean_condition`→
    needs `cond.*`, empty-resolved skip; layer-clean prefix check — NO indicator-taxonomy import).
    `commands/create_package.py::submit_candidate_generation` now computes the manifest (candidate_hash
    = real content hash; `candidate_output_contract = manifest.output_contract`) + NEW
    `_candidate_resolved_refs` (description→[], code→current PASSED `scan.resolved_refs`); return keys
    unchanged (`{request_id, state, candidate_hash, job_id}`). Pre-Check resolver / PC-13 gate / job
    durability / state machine / `_draft_dependency_snapshot` / engine all UNCHANGED. +12 unit tests →
    **1048**; NO migration, alembic head stays 0021_local_auth, `ENGINE_VERSION` unchanged, frontend
    unchanged (82); review 0 CRITICAL/HIGH. Honest boundary (PERMANENT): LLM generation is Future-Dev;
    the candidate artifact is NOT executed by the engine (native compute from `dependency_snapshot`
    pins — ESP `_MovingAverage`/`_Rsi`/`_Vwap`…); CP/Pre-Check FRONTEND pages remain placeholders
    (natural next slice); `["jobs"]` has NO backend list surface (permanent).
  - ✅ **Create Package request page (PR #91, MERGED — FRONTEND)** — the `/packages/create`
    placeholder becomes the real page, binding `routes/create_package.py` (doc 06 §4/§5/§9).
    **FRONTEND-ONLY** (backend unchanged, no migration, backend base stays 1048). Request
    **LIFECYCLE ENTRY** only: compose + own-requests keyset list + read-only detail projection.
    NEW `lib/createPackage.ts` (wire types mirror `queries/create_package.py` verbatim; enum
    mirrors of `domain/create_package/enums.py`; `OUTPUT_KINDS_BY_KIND` hydration-only mirror of
    `value_objects._OUTPUT_KINDS_BY_KIND`; `sourceKindForMode`; `requestStateTone`; hooks under
    `["package-requests"]` — no dedicated SSE event, swept by `resource.changed`:
    `usePackageRequests` keyset + `usePackageRequest` enabled-gated + `useRationaleFamilies`
    shared `["rationale-families"]`; `useCreatePackageRequest` fresh Idempotency-Key per submit,
    NO OCC token — a create has no head to race) + NEW `pages/CreatePackage.tsx` (`CreateForm`
    doc 06 §4: source_language only for code modes / `other`→label / output kind scoped to the
    package type + RESET on type switch / rationale family REQUIRED for Indicator+Condition,
    server-hydrated, N/A for ESP / declared keys one-per-line; `RequestsCard` keyset Pager;
    `RequestDetailCard` read-only projection + scan hints `current_scan`/`precheck_fresh`/
    `can_generate_candidate`; errors verbatim `ApiError`). `App.tsx` `/packages/create`
    REAL_PATHS; `nav.ts` UNCHANGED (24). `global.css` `.cp-*` grid. NEW
    `test/createPackage.test.tsx` (+7, apiStub ORDERED — `req_new`/`req_1` detail routes precede
    the list prefix; a create auto-opens its detail → the `req_new` detail stub is REQUIRED) →
    **frontend 82 → 89**; typecheck+lint clean, build green; CI 3/3. Honest boundary:
    `target_runtime` fixed `python` (`SUPPORTED_TARGET_RUNTIMES`); Pre-Check/generate-candidate/
    draft/approve ACTIONS + `compatible_rationale_family_ids`/`linked_indicator` deferred (next
    natural slice, OCC `X-Request-Version`); the Pre-Check PAGE (doc 07) is still a placeholder
    (→ both landed next in PR #93).
  - ✅ **CP request lifecycle actions + Pre-Check page (PR #93, MERGED — FRONTEND)** — closes the
    PR #91 boundary. **FRONTEND-ONLY** (2 new + 4 edits; backend 1048 stays, no migration).
    `lib/createPackage.ts` EXTENDED in place: action wire types mirror the command return dicts
    verbatim; `useRunPrecheck`/`useGenerateCandidate` — request `row_version` as the
    **`X-Request-Version` OCC header** + fresh `Idempotency-Key` per attempt
    (`postWithRequestVersion`, agentLab `postWithIfMatch` mirror); `useCreateDraft` —
    **`expected_candidate_hash` BODY token** from the accepted generate result;
    `useApproveRequest` — **`expected_head_revision_id` = draft head** + optional note,
    Admin-only SERVER-side (CR-02, 403 verbatim, UI never role-gates); all invalidate
    `["package-requests"]`+`["audit"]`; `useDependencyScan` immutable artifact (5m staleTime).
    `pages/CreatePackage.tsx` `RequestActions` bar (server-hint gating only:
    `can_generate_candidate`/`candidate_ready`/draft present). NEW `pages/PreCheck.tsx`
    (`/packages/pre-check`, doc 07): own-requests picker → run scan → §7.1 Resolved/Missing rows
    (literal text, values as text nodes) → §7.2 canonical status lines + stale warning →
    `GET /dependency-scans/{scan_id}` viewer. `App.tsx` REAL_PATHS 11→12; `nav.ts` UNCHANGED (24).
    +4 `createPackage.test.tsx` + NEW `test/preCheck.test.tsx` (+5) → **frontend 89 → 98**;
    CI 3/3. Honest boundary: `compatible_rationale_family_ids`/`linked_indicator` composer
    fields still deferred; the draft token lives only in the card that ran Generate (projection
    omits `candidate_hash`); no dedicated CP SSE event; the FULL `routes/create_package.py`
    surface is now frontend-bound — no CP endpoint remains unbound.
  - ✅ **Gated capability operational POSTs (PR #95, MERGED — FRONTEND)** — closes the PR #82
    boundary. **FRONTEND-ONLY** (4 edits, no new files; backend 1048 stays, no migration).
    `lib/capability.ts` EXTENDED in place: `ANALYSIS_ARTIFACT_CAPABILITY` hydration-only mirror
    of `commands/capability.py` (doc 22 §10.3–§10.6; server re-derives the gate from
    `artifact_type` on every dispatch) + `ANALYSIS_ARTIFACT_TYPES` (server's sorted `allowed`
    order); wire types `ViewDatasetResult`/`AnalysisArtifactResult` mirror the command returns;
    `useQueryViewDataset`/`useCreateAnalysisArtifact` — **fresh `Idempotency-Key` per attempt,
    NO OCC token** (a create has no head to race), blank optional fields OMITTED, success
    invalidates `["audit"]` ONLY (neither entity has a read surface — results live in the
    command return + audit trail). `pages/FutureDev.tsx`: `ViewDatasetComposer` in the Graphic
    View card + NEW `AnalysisArtifactsCard`; composers NEVER client-pre-gated (doc 22 §3) —
    `CAPABILITY_NOT_ACTIVE` renders verbatim (CR-09/FD-02). `App.tsx`/`nav.ts` UNCHANGED
    (REAL_PATHS stays 12). +5 `futureDev.test.tsx` + 2 `capabilityLib.test.ts` →
    **frontend 98 → 105**; CI 3/3. The FULL `routes/capability.py` surface is now frontend-bound.
    Honest boundary: `range_spec` has no composer input (wire type carries it); created view
    datasets/artifacts have NO list/read surface (permanent until a backend projection lands);
    no dedicated capability SSE event (`resource.changed` sweeps).
  - ✅ **Package Library catalog page (PR #97, MERGED — FRONTEND)** — the `/packages/library`
    placeholder becomes the real page, binding the FULL `routes/library.py` read surface
    (doc 08 §3/§4/§9.2; both GETs). **FRONTEND-ONLY** (backend 1048 stays, no migration).
    NEW `lib/library.ts` (wire types mirror `queries/library.py` verbatim — row/detail incl.
    live rationale-family resolution `{id, name, pinned_name, family_active}`, Stage-2e
    provenance + scan summary, revision history, ten-flag `PackagePermissions` +
    `PERMISSION_FLAGS`/`PERFORMANCE_FIELDS` order mirrors; facet taxonomy hydration mirrors +
    `UNASSIGNED_FAMILY` sentinel — server re-validates, 422 verbatim; hooks under `["library"]`
    — no dedicated SSE event, swept by `resource.changed`; the kind facet travels as the `type`
    route alias, empty facets never sent; READ-ONLY, no OCC token) + NEW `pages/Library.tsx`
    (facet bar + family select hydrated from the shared `useRationaleFamilies`; orthogonal
    state badges — doc 08 §13 facets never collapsed; cursor-stack pager; detail card with
    text-rendered permissions, L4 `not_applicable` performance labels verbatim — never
    fabricated zeros, contracts/snapshot JSON, provenance + scan summary, revision history;
    Guest → 401 verbatim). `App.tsx` REAL_PATHS 12→13; `nav.ts` UNCHANGED (24). +8 vitest
    (`test/library.test.tsx`, apiStub ORDERED — detail fragment precedes the `/library` list
    prefix) → **frontend 105 → 113**; CI 3/3. Honest boundary: read-only catalog — package
    ACTIONS (revise/validate/publish/deprecate/delete/export) are explained by the
    server-computed permission flags but NOT dispatched from this page (later slices; the
    detail ETag/`row_version` is ready as their OCC token); performance stays `not_applicable`
    until runs are linked. **Remaining TIER 2:** the 11 remaining placeholder pages, ALL with
    landed V1 backend surfaces (`esp.py` Embedded natural next — Library pattern continues /
    `rationale.py` / `market_data.py` / `research_data.py` / `strategy.py` /
    `trading_signal.py` / `trade_log.py` / `allocation.py` Portfolio / `readiness.py` Ready
    Check / `manual.py` User Manual).
  
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
  - (ii) N-ary reference chain **PR #57** — condition RHS as an ordered chain of >2 packages (`fast > slow > slowest` MA fan); `ConditionBlock.additional_reference_package_refs`
  - (d) VWAP directional key **PR #58** — `ta.vwap` → `DIRECTIONAL_KEYS` (rolling volume-weighted price line; price/VWAP cross native trigger + reference package + N-ary leg); `_Vwap` compute, volume threaded through engine→evaluators, `ENGINE_VERSION=backtest-engine-v2-vwap-directional`; `ta.atr` stays non-directional by nature
  - formula_based **Kelly criterion sizing PR #60** (+ non-finite fail-closed fix **PR #61**) — `formula_based_sizing`+`kelly_criterion` honored: `f*=kelly_fraction·(W−(1−W)/R)` (clamp 0), `size=usable_equity·f*/entry_price` (entry-price dependent); `_decimal_param`/`_kelly_capital_fraction`/`_position_size` Kelly branch/`_sizing_is_honored` in `engine.py`; `ENGINE_VERSION=backtest-engine-v2-kelly-sizing`; no migration; review fixed a non-finite `formula_params` crash + Inf-payoff silent-honor via `Decimal.is_finite()` guard; `custom_formula`/adaptive Kelly stay `unresolved`
  - **position_size_limits min/max cap wiring PR #63** — `PositionSizeLimits` (min/max caps) was silently ignored across ALL sizing methods in `engine._position_size` (latent bug). New `_clamp_to_limits(size, limits)` clamps at the single `_raw_position_size → _position_size` boundary so base/risk_based/Kelly/notional are all capped uniformly (fail-closed: `limits is None` or `size≤0` → no-op, `min>max` → 0, else max-down/min-up/floor-0; caps in size units, unquantized). Old `_position_size` body renamed `_raw_position_size`; `_position_size` now a thin wrapper. `TYPE_CHECKING` += `PositionSizeLimits`; `run_engine` diagnostics += `position_size_limits_active`; `ENGINE_VERSION=backtest-engine-v2-position-size-limits`; +15 tests → 1015; no migration; review APPROVE 0 CRITICAL/HIGH. **TIER 1 backend EFFECTIVELY COMPLETE.**
  
  Full roadmap: `docs/POST_V1_KICKOFF.md`.
