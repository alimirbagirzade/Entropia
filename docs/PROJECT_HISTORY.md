# Entropia — Proje Tarihçesi (tam kayıt)

> Bu dosya `CLAUDE.md`'nin eski "Current position" bölümünün **birebir** taşınmış
> halidir. Her oturumda otomatik yüklenmez — bir slice'ın ayrıntısına (hangi PR ne
> getirdi, ENGINE_VERSION geçmişi, OCC token biçimleri, honest boundary'ler)
> ihtiyaç duyduğunda BURADAN oku.
>
> Özet + güncel durum: `CLAUDE.md` §Current position.
> Yol haritası: `docs/POST_V1_KICKOFF.md` · Handoff: `docs/STAGE2_HANDOFF.md`

---

## Current position (keep in sync at each closing)

> **2026-07-22 güncelleme (auth remediation dalgası):** `main` HEAD → **`6e3fab9`** (PR #364).
> Auth güvenlik denetimi remediation'ı (#346–#364) COMPLETE — **migration YOK**, alembic head
> **`0035_portfolio_rules`** SABİT, `ENGINE_VERSION` SABİT. CI server-truth: backend **1841 passed**,
> frontend vitest **577/58 dosya**, E2E green. Tam kayıt: aşağıda "Auth remediation dalgası — tam kayıt".
> Aşağıdaki uzun "Landed" paragrafı V18-R2 öncesi durumun tarihsel aynasıdır — güncel özet: `CLAUDE.md` §Current position.

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
  Package Library catalog page (PR #97, MERGED) + TIER 2 frontend live-data Embedded System
  Packages page (PR #99, MERGED) + TIER 2 frontend live-data Rationale Families page — full
  CRUD + assignment batch editor (PR #101, MERGED) + TIER 2 frontend live-data Market Data page —
  read surface + owner ingest chain (PR #103, MERGED) + TIER 2 frontend Market Data revision
  lifecycle actions — revisions/successor/Admin approve+deprecate, 10/10 endpoints bound (PR #105, MERGED)
  + TIER 2 frontend live-data Research Data page — role-aware read surface + owner ingest chain
  (create[DR3 market-link]/upload/finalize/analysis), 6/14 endpoints bound (PR #107, MERGED)
  + TIER 2 frontend Research Data revision lifecycle actions — revise/time-policy/field+feature
  defs/Admin approve+revoke (OCC If-Match "rv-N")/agent+evidence bundles (pure read), 14/14 endpoints
  bound → Packages & Data group fully bound (PR #109, MERGED)
  + TIER 2 frontend Backtest Ready Check page — routes/readiness.py (doc 14 §4/§7/§9) bound to
  /backtest/ready-check; OCC token is the composition FINGERPRINT carried BODY-form as
  expected_fingerprint (NOT "rv-N"/If-Match) + fresh Idempotency-Key; success invalidates
  ["readiness"]+["mainboard"] (PR #111, MERGED)
  + TIER 2 frontend Portfolio / Equity Allocation page — routes/allocation.py 5/5 bound to
  /portfolio (Backtest nav group CLOSED); OCC is BODY-form expected_row_version (draft GET
  row_version = live token; 0 = no-plan creation token) + fresh Idempotency-Key on
  PUT/revisions; validate reads NO body/headers (new immutable report per run); sync POST is
  a PURE READ merge preview (no Idem, no invalidation); item_type never sent
  (server-derived §8.2); draft PUT readiness_invalidated:true → invalidates
  ["allocation"]+["readiness"]+["mainboard"]+["audit"] (PR #113, MERGED)
  + TIER 2 frontend User Manual page — routes/manual.py 7/7 bound to /user-manual (Docs nav
  group CLOSED: Future Dev #82 + User Manual #115); OCC is TWO different BODY-form tokens:
  expected_stream_version INT on create/upload/delete (optional server-side; client always
  guards with the rendered snapshot — stale → 409 MANUAL_STREAM_CONFLICT) and
  expected_head_revision_id STR on revisions (body wins over If-Match; 409
  MANUAL_REVISION_CONFLICT) + fresh Idempotency-Key per attempt; DELETE carries an OPTIONAL
  BODY (api.del takes neither → apiRequest direct); :restore is require_trash_admin (NOT
  manual admin), no body, returns the Trash-core RestoreResult (lib/trash.ts type REUSED);
  get_manual_section NOT routed (doc 21 §12 Agent Tool Gateway); mutations invalidate
  ["manual"]+["audit"] (+["trash"] on delete/restore) (PR #115, MERGED)
  + TIER 2 frontend live-data Strategy Details page — routes/strategy.py 9/9 bound to /strategy
  (biggest Workspace surface; editor draft workflow create/patch/validate/save/clear + root header
  + revision history + immutable ?revision= deep-link); OCC is BODY-form expected_draft_row_version
  INT on PATCH/save/clear (body wins over If-Match; REQUIRED; draft row_version starts at 0 — 0 is
  a valid token; stale → 409 STRATEGY_DRAFT_CONFLICT) + fresh Idempotency-Key; validate reads NO
  body/headers (pure compiler pass, no audit row → no Idem, no invalidation); save re-pins attached
  Mainboard items same-tx → invalidates ["strategy"]+["mainboard"]+["readiness"]+["audit"]; blocked
  save = 422 with compiler issues {field,code,message} in error.details (verbatim); draft_id is an
  independent stratdraft ULID — NO root→draft lookup endpoint → the page carries the draft handle
  in the URL (?draft=); /strategies/{root}/revisions is a BARE LIST (PR #117, MERGED)
  + TIER 2 frontend live-data Trading Signal & Trade Log twin pages — routes/trading_signal.py +
  trade_log.py FULL twin surfaces (6+6 endpoints, docs 04/05) bound to /trading-signal +
  /trade-log in ONE slice (upload content-addressed dedup → durable 202 import → report →
  Save & Add native work object → OCC revision append); all 4 POSTs/twin read fresh
  Idempotency-Key, ONLY OCC token = BODY-form expected_head_revision_id STR on /revisions
  (client always sends rendered head); TWIN DIFFS verbatim (normalized_event_revision_id vs
  record_batch_revision_id; TL available_time always null — historical doc 05 §10.4); import
  report keyed ["jobs","<kind>-import",jobId] — FIRST page binding of the job.updated SSE key
  (terminal-stop poll, INF-11); create-with-attach invalidates ["mainboard"]+["readiness"];
  revisions never auto-repin; Pin/delete stay Mainboard ops (CR-01/TL-01); App.tsx REAL_PATHS
  21→23; +11 vitest → 208 (PR #119, MERGED)
  + TIER 2 frontend ESP registry mutation actions — routes/esp.py create/activate/deprecate
  bound onto the existing /packages/embedded page (read surface was PR #99) → esp.py surface
  COMPLETE (library.py already 2/2 → NO unbound endpoint left in Packages & Data); create
  carries NO OCC/Idempotency-Key/Admin-gate (any authenticated actor proposes a CANDIDATE,
  doc 09 §5); activate + deprecate carry the X-Registry-Version HEADER-form PLAIN-INT OCC
  (NOT If-Match "rv-N"; source detail.registry.registry_version) + fresh Idempotency-Key +
  Admin-only (command layer — UI never pre-gates; 409 RESOLVER_REGISTRY_CONFLICT / 403
  APPROVAL_REQUIRES_ADMIN verbatim); canActivate/canDeprecate state-machine UI hints;
  postWithRegistryVersion helper; invalidates ["esp"]+["audit"]; App.tsx/nav.ts UNCHANGED;
  +5 vitest → 213 (PR #121, MERGED)
  + TIER 2 frontend Add Outsource Signal chooser page — the /outsource-signal placeholder (the
  LAST Workspace + TIER 2 page-map placeholder) becomes the real doc 03 external-work TYPE
  CHOOSER → REAL_PATHS 23→24, NO placeholder remains — **TIER 2 PAGE MAP COMPLETE**. PURE
  presentation: exactly two canonical choice links (trading_signal | trade_log, CR-01) into the
  TS/TL workbenches (direct links make "continue without a choice" unconstructible — AOS-02 by
  construction); doc 03 §6.1 ⓘ panels + §6.2 helpers VERBATIM; NO hooks/query keys/fetch (doc 03
  §7.1 — the chooser performs no backend mutation; "outsource" exists in the backend only as the
  errors.py:624 comment — no router exists and none is needed, confirmed empirically); nav.ts
  UNCHANGED (24); +6 vitest → 219 (PR #123, MERGED)**
  + TIER 2 frontend Mainboard composition page — the index `/` Mainboard becomes the real doc 01
  composition plane (was a 55-line Stage-0 meta/health shell). Binds the 7 unbound
  routes/mainboard.py endpoints (GET default already bound via lib/backtest.ts useDefaultMainboard)
  → **mainboard.py surface COMPLETE**; closes the PERMANENT boundary where attach + Pin
  ("Use This Revision") + work-object soft-delete lived on no landed page. EMPIRICAL OCC/Idem
  (route signatures READ): POST /external-work-object-drafts/{kind} carries NO Idempotency-Key/OCC
  (transient opener, not even async → deep-links to /trading-signal|/trade-log workbench, CR-01);
  create/attach/snapshot/delete are Idempotency-Key WITH NO OCC; /work-objects/{root}/revisions
  carries BODY-form expected_head_revision_id STR (optional); PATCH /mainboard-items/{item} carries
  BODY-form expected_row_version INT (REQUIRED, body wins over If-Match; one intent per call
  pin_revision|set_enabled|reorder|set_label, only the needed field sent — pin/enable change the
  composition hash → Ready stale); DELETE /work-objects/{root} carries NO body. NEW lib/mainboard.ts
  (wire result types mirror the command return dicts verbatim; re-exports useDefaultMainboard +
  item/workspace types from lib/backtest.ts; §6.2 ready-status text/tone catalog; itemKindLabel +
  EXTERNAL_DRAFT_KINDS taxonomy; 7 hooks under ["mainboard"] — no dedicated SSE event,
  resource.changed sweeps; composition mutations invalidate ["mainboard"]+["readiness"]+["audit"],
  delete +["trash"], snapshot ["audit"] only) + pages/Mainboard.tsx rewritten (composition summary
  + Ready Check/RUN links to the landed /backtest/* pages + Freeze composition; per-item expandable
  ops panel — row_version-OCC Pin/Enable-Disable/Move/Label + two-step soft-delete with doc 01 §6.2
  text verbatim; Add Outsource Signal opener; Advanced generic work object create→revision→attach;
  row expand/collapse presentation-only AT#7; empty-state verbatim) + test/mainboard.test.tsx +9
  (apiStub ORDERED — {root}/revisions precedes the bare create prefix); App.tsx/nav.ts UNCHANGED
  (index `/` already REAL_PATHS); +9 vitest → 228 (PR #125, MERGED)**.
  + TIER 2 frontend Trash Permanent Delete (purge) actions — the `/trash` page (read + restore
  landed in PR #86) gains the destructive purge, binding the last unbound routes/trash.py endpoint
  (POST /trash-entries/{id}/purge, doc 20 §8.3) → **trash.py surface COMPLETE** (mainboard.py #125 +
  trash.py #127 → no unbound endpoint remains). EMPIRICAL (route + command signatures READ): two-phase
  202 — the request only moves the target to purge_pending + enqueues a durable maintenance job; the
  WORKER runs the actual purge (re-checks eligibility). Body REQUIRES confirmation_phrase (must equal
  the object's display identity display_name||entity_id, else PURGE_CONFIRMATION_INVALID, never started)
  + reauth_proof (non-empty; V1 presence-only, full MFA out of scope doc 20 §0, else REAUTH_REQUIRED);
  OCC = BODY-form expected_row_version INT (body wins over If-Match, doc 20 §14) = entry row_version,
  stale → STALE_REVISION; fresh Idempotency-Key per attempt (same key → same job). Purge is eligible on
  the SAME recoverable statuses as Restore (shares _assert_entry_recoverable) → the page gates the action
  on the server-truth restore_eligible flag (no backend change). lib/trash.ts (PurgeResult wire type —
  request_purge dict verbatim, NB omits display_name + useRequestPurge Idempotency-Key header + body-OCC
  token, invalidates ["trash"]+["audit"]; PR #86 useRestoreEntry pattern) + pages/Trash.tsx (Permanent
  Delete → explicit two-step PurgeComposer, doc 20 §9 confirmation copy verbatim; Confirm mirrors the
  server preconditions — exact name + non-empty proof, server re-validates; captures the display name at
  accept time for the §9 accepted toast since the 202 return has no display_name) + .btn-danger style +
  test/trash.test.tsx +4 (228 → 232); App.tsx/nav.ts UNCHANGED (/trash already REAL_PATHS); review 0
  CRITICAL/HIGH. Honest boundary: purge is a request only — the worker runs the actual purge (status
  via the ["trash"] projection, no dedicated SSE event); reauth_proof presence-checked only in V1;
  retention auto-purge stays a TIER 3 backend slice; +4 vitest → 232 (PR #127, MERGED)**.
  **Overall: ~99% complete** (V1=100%, frontend page map=100%; all route surfaces bound;
  doc-22 Future Dev capability system END-TO-END complete — registry + Admin transition + 2 operational POSTs
  + owner-scoped output history #143 + lifecycle-transition history #144; **post-V1 FINALIZATION landed** —
  #146 agent tool-call history + #147 seed FK fix + #148 smoke script + #149 README refresh + #150 USAGE/ARCHITECTURE).
  `main` after PR #149 (`2d57f95`; #150 açık/merge bekliyor olabilir — gh pr list ile doğrula.
  FINALIZATION wave: README refresh docs `b61692c` MERGED [root README build status → gerçek durum: V1 %100 + post-V1;
  CI-truth sayılar; NEW "What's inside — the 24-screen map" + NEW "Verifying changes" (CI kapıları + izole
  TEST_DATABASE_URL uyarısı + up/down/up + smoke + e2e); auth bölümü AUTH_MODE=dev|session gerçeğine yeniden yazıldı;
  .env.example += Authentication/Rate-limiting blokları (settings.py default'ları verbatim)]; smoke script chore
  `0b5c877` MERGED [scripts/smoke.sh + make smoke — çalışan stack'in dışarıdan read-only doğrulaması: live/meta/
  openapi + per-dependency ready (postgres hard-FAIL, redis/minio WARN) + Prometheus metrics + X-Actor-Id /me +
  frontend :5173/:8080; ready DOWN bağımlılıklarda >5s sürer → uzun curl timeout; tam e2e yol =
  tests/integration/test_e2e_pipeline.py (canlı 3 passed, entropia_smoke DB)]; seed identity FK fix `d901e14`
  MERGED [BOŞ veritabanında python -m entropia.apps.seed ForeignKeyViolationError ile patlıyordu —
  relationship()'siz Principal↔HumanUser/Agent modellerinde unit-of-work flush sırasını tablo-FK'sından
  TÜRETMİYOR (SQLAlchemy 2.0.51, minimal repro + SQL echo ile kanıtlı); fix: her FK-bağımlı child'dan önce
  Principal flush + kimlik bloğu seed_identities(session) olarak test edilebilir; +2 integration
  (test_seed_identities.py: taze-şema FK sırası / idempotency) → backend CI-truth 1089 — NOT: önceki zincirin
  "1088" sayımı off-by-one idi, #147 öncesi CI 1087]; agent tool-call gateway call-history read surface feat
  `b8f1664` MERGED [BACKEND+FRONTEND, no migration — orphan agent_tool_gateway repo list_tool_calls/get_tool_call
  → YENİ queries/agent_tool_gateway.py (require_role ADMIN/SUPERVISOR; task-scoped bounded newest-first summary
  list request/response_ref gövdelerini omit eder + full-record detail; missing → not-found) + routes/agent_lab.py
  GET /agent-tasks/{task_id}/tool-calls + GET /agent-tool-calls/{tool_call_id} + errors.py
  AgentToolCallNotFoundError (additive); frontend lib/agentLab.ts AgentToolCall{Card,Detail,List} +
  TOOL_CALL_STATUS_TONES + useTaskToolCalls/useToolCall (["agent-tasks"] SSE-swept) + AnalysisLab.tsx task-detail
  "Tool calls" bölümü; +7 backend integration + 2 vitest → frontend 246; honest boundary: detail read rol-gate'li
  (paylaşımlı-gözlem modeli), list bounded newest-first keyset'siz]; ÇALIŞTIRILABİLİRLİK KANITI: Docker'sız yol
  uçtan uca canlı (pg :5432 + alembic head 0023 + uvicorn + seed + /me admin + Vite + make smoke SMOKE OK);
  DÜRÜST SINIR: docker compose up bu makinede kanıtlanamadı — Docker Desktop self-update GUI onayı bekliyordu
  (compose config geçerli + CI "Docker — build images" yeşil). Önceki: `c5d97b6`; capability lifecycle-transition history read surface feat `d77d612` MERGED [BACKEND+FRONTEND, no migration — `capability_activation_event` exists since `0020_future_dev`; binds the orphan `capability_repo.list_activation_events` → `GET /capabilities/{key}/lifecycle-transitions`, oldest-first by resulting registry version, any-authenticated read / write+transition Admin-only; `queries/capability.py::get_capability_transitions` + frontend `useCapabilityTransitions` + immutable "Transition history" table keyed `["capabilities"]` (Admin transition refreshes it same-tab); +4 backend integration + 2 vitest; backend 1077→1081, frontend 242→244; → doc-22 Future Dev capability system END-TO-END COMPLETE]; capability operational output history read surface feat `44e4b1e` MERGED [BACKEND+FRONTEND, no migration — `view_dataset`/`analysis_artifact` exist since `0020_future_dev`; owner-scoped ACTIVE-only newest-first keyset `GET /view-datasets[/{id}]` + `/analysis-artifacts[/{id}]` makes the two operational POSTs' (view_dataset.query/analysis_artifact.create, #95) outputs readable — doc 22 §7 `futureDevNoHistory.empty` now reachable; cross-owner/soft-deleted/missing → not-found (no existence leak); ULID id-DESC keyset, owner+`active` repo filter; +8 backend integration + 4 vitest; backend 1069→1077, frontend 238→242]; audit log substring (pg_trgm) indexes feat `36069cb` MERGED [BACKEND-ONLY **MIGRATION** slice — **alembic head → `0023_audit_log_trgm_indexes`**: closes the #139 honest boundary (substring filters were seq scans) — 3 GIN **trigram** (`pg_trgm`) expression indexes on `audit_events` mirroring `log_projection.py` §6.2 `contains` filters (a leading-wildcard `LIKE '%needle%'` no B-tree/`varchar_pattern_ops` can serve — only `gin_trgm_ops`): `ix_audit_events_event_kind_trgm` = `lower(event_kind)` NOT-NULL no-predicate → serves BOTH the `family` token filter AND the `q` search; `ix_audit_events_target_id_trgm` = `lower(target_entity_id)` partial `IS NOT NULL` → `q`; `ix_audit_events_reason_trgm` = `lower(reason)` partial `IS NOT NULL` → `q`; migration `CREATE EXTENSION IF NOT EXISTS pg_trgm` + a `models/audit.py` `before_create` metadata listener provisions pg_trgm on any `create_all` (test) path (Postgres-only); downgrade drops the indexes but RETAINS the extension (DROP is destructive in a routine down); proofs: migration↔model `indexdef` parity IDENTICAL + alembic up/down/up → head `0023` + EXPLAIN (3-column `q` → BitmapOr over all three trgm indexes; `family`/`q` event_kind → Bitmap Index Scan on the event_kind trgm index); +4 integration shape tests (`test_audit_log_trgm_indexes.py`); backend 1065→1069; ENGINE_VERSION unchanged, frontend unchanged (238); honest boundary: `system_other`/earlier-family exclusions are purely NEGATIVE (`NOT LIKE '%token%'` — no trigram serves a negated substring, they ride a scan filter behind the positive predicate), `actor_kind` stays unindexed, pg_trgm needs `CREATE EXTENSION` privilege at deploy (trusted extension on PG13+, installable by the DB owner)]; audit log-projection indexes feat `72c95ec` MERGED [BACKEND-ONLY **MIGRATION** slice — **alembic head → `0022_audit_log_indexes`**: 5 indexes on `audit_events` mirroring the EMPIRICAL Admin Logs query patterns (`queries/log_projection.py`, doc 19 §5/§6.2) — 3 partial composites (`severity|actor_principal_id|target_entity_type` + trailing `(occurred_at, event_id)` keyset → a filtered page is ONE ordered index scan; severity indexes only non-info triage rows, `info` deliberately rides `ix_audit_events_log_order`) + correlation-chain composite (§5 equality + ASC order) + `lower(correlation_id) varchar_pattern_ops` partial EXPRESSION index (§6.2 prefix filter lowercases while ids store UPPERCASE Crockford base32); proofs: migration↔model `pg_indexes.indexdef` parity IDENTICAL + alembic up/down/up (8→3→8) + 3× EXPLAIN (planner PROVES the `severity != 'info'` partial implication → Index Only Scan Backward sort-free); +4 integration tests (`test_audit_log_indexes.py` pg_indexes server-truth DDL shape); backend 1061→1065; ENGINE_VERSION unchanged, frontend unchanged (238); honest boundary: `actor_kind` (3-value enum) unindexed by design, family/query-text `contains` filters need pg_trgm — extension decision, out of scope]; summary["timeframe"] resolution feat `e1a2f88` MERGED [BACKEND-ONLY: `run_engine` +optional caller-resolved `timeframe: str|None` param (engine PURE — worker `jobs/backtest_engine.py` resolves the PINNED market revision's `resolution_value` via read-only `get_base_timeframe_for_revision`, BAR-only else honest None L4; resolve OUTSIDE the engine try → DB error stays a retryable job exception); **ENGINE_VERSION → `backtest-engine-v2-summary-timeframe`** (execution_key ns shift — stale timeframe-less result not reused, INF-04/05, PR #47/#63 precedent); +4 tests (2 unit passthrough/default + 2 integration persisted "1m"/None via `_ready_composition(base_tf=...)`); backend 1057→1061; no migration (`ResultSummary.timeframe` column existed since 5a), frontend unchanged (`timeframe: string|null` already typed)]; tool-call envelope status shadowing feat `4e8ce12` MERGED [BACKEND-ONLY: `application/jobs/agent_tools.py::dispatch_tool_call` — envelope `status`/`tool_call_id` now WIN over any handler payload key on success + idempotent-replay paths (payload spread FIRST); the 2 colliding keys namespaced — `artifact.create` `status`→`artifact_status`, `agent.task.query` `status`→`task_status`; durable `agent_tool_call` row was always authoritative → low-severity response-envelope fix, not persistence; NOT CR-08 (capability gating fully wired); +3 gateway regression tests + corrected e2e shadow assertion; backend 1054→1057; no migration, ENGINE_VERSION unchanged, frontend unchanged]; frontend SSE reconnect backoff resilience feat `a100930` MERGED [FRONTEND-ONLY: `lib/sse.ts::connectEvents` readyState-aware `onerror` (CONNECTING→"connecting" native retry; CLOSED→own exponential backoff 1s→30s cap) + gap full-refresh on reopen (INF-11) + dispose cancels timer/detaches listeners; signature + `EVENT_QUERY_KEYS` unchanged (`Layout.tsx` call-site untouched); frontend 235→238; no migration]; frontend data-queue redelivery Admin UI feat `51d9e83` MERGED [FRONTEND-ONLY: Panel `OperatorRecoveryCard` binds `POST /admin/data-queue/redeliver` via `lib/adminPanel.ts::useRedeliverDataQueue` — query-only, no OCC/Idem; frontend 232→235; no migration]; data-queue operator redelivery feat `986ede7` MERGED [INF-03, doc 20 §6: `job_kind` discriminator + `DATA_ACTOR_BY_KIND` + Admin `POST /admin/data-queue/redeliver`; backend 1048→1054; no migration]; Trash purge feat `7ae3428` MERGED; Mainboard composition feat `43b9063` MERGED; Outsource chooser feat `be2aa8a` MERGED; ESP registry mutation feat `b692aaa` MERGED; Trading Signal & Trade Log twin feat `038187f` MERGED; Outsource chooser feat `be2aa8a` MERGED; ESP registry mutation feat `b692aaa` MERGED; Trading Signal & Trade Log twin feat `038187f` MERGED;
  Strategy Details feat `8e5e068` MERGED; User Manual feat `54fd4db` MERGED; Portfolio feat `f3e9550` MERGED; Ready Check feat `6232486` MERGED; Research Data lifecycle-actions feat `2e488dc` MERGED; Research Data page feat `5049f4e` MERGED; Market Data lifecycle-actions feat `d2a9ada` MERGED; Market Data lifecycle-actions feat `d2a9ada` MERGED; Market Data page feat `0ca0468` MERGED; Rationale Families feat `20ccacc` MERGED; Embedded feat `5bf633a` MERGED; Embedded feat `5bf633a` MERGED; Package Library feat `53394fe` MERGED; capability-POSTs feat `652dfde` MERGED; CP-actions/Pre-Check feat `e8f8982` MERGED; CP-create-page feat `79fbd24` MERGED; CP-Gen candidate-generation feat `5cc62cc` MERGED; auth-invalidation feat MERGED (PR #88); trash-page feat `3ccb50d` MERGED; provisioning-dashboard feat `b56f621` MERGED; capability-page feat `3d7977e` MERGED; history-compare feat `491ac03` MERGED; panel-page feat `726ffcc` MERGED; first-Admin bootstrap feat `a53cf34` MERGED; live-pages feat `499bd8b` MERGED; backtest-pages feat `10a0007` MERGED; metrics feat `d3039e7` MERGED; login feat `58781e4` MERGED; SSE feat `5ddb14f` MERGED; position_size_limits feat `5ef5525`; Kelly feat `3f254bc` / non-finite fail-closed fix `3a92e7d`; VWAP code `d27b2bb`; N-ary code `44099a7`; per-condition code `1c5cca0`; multi-timeframe code `def6c28`; indicator-vs-indicator code `9087c2b`; condition-extensions code `361df4c`; condition-blocks code `8766fae`; risk_based code `43cee29`; Slice C code `671d227`);
  alembic head = **`0023_audit_log_trgm_indexes`** (PR #141 — `pg_trgm` extension + 3 GIN trigram indexes over `0022_audit_log_indexes` = PR #139 index-only over `0021_local_auth` = `human_credentials` + `auth_sessions`;
  Slices A/B/C + follow-ups (a)/(b)/(b2)/(#53)/(c)/(i)/(ii)/(d) + Kelly sizing + position_size_limits + first-Admin bootstrap + bootstrap-status read endpoint + CP-Gen deterministic candidate generation need no migration; data-queue operator redelivery PR #129 needs no migration; tool-call envelope status shadowing PR #135 needs no migration; summary["timeframe"] resolution PR #137 needs no migration — but it BUMPS ENGINE_VERSION; audit log-projection indexes PR #139 IS the migration `0022` — index-only, no table/column change, ENGINE_VERSION untouched; audit log substring pg_trgm indexes PR #141 IS the migration `0023` — pg_trgm extension + 3 GIN trgm indexes, no table/column change, ENGINE_VERSION untouched; capability operational output history PR #143 + lifecycle-transition history PR #144 need no migration — `view_dataset`/`analysis_artifact`/`capability_activation_event` all exist since `0020_future_dev`, ENGINE_VERSION untouched; agent tool-call history PR #146 + seed FK fix PR #147 + smoke PR #148 + README PR #149 + USAGE/ARCHITECTURE PR #150 need no migration). **1089 tests green — CI server-truth on `main`@#147** (= 1087 CI @#146 + 2 seed-identity regression [`test_seed_identities.py`: taze-şema FK sırası / idempotency] — NOT: aşağıdaki tarihsel zincirin "1081 + 7 = 1088" aritmetiği off-by-one idi, CI gerçeği esas; tarihsel kayıt: 1081-iddia = 1077 + 4 transition-history [`test_capability_transition_history.py`: capability lifecycle-transition GET oldest-first by resulting registry version / any-authenticated read / write+transition Admin-only / detail-parity provenance] = PR #144; 1077 = 1069 + 8 output-history [`test_capability_output_history.py`: owner-scoped ACTIVE-only keyset view-dataset/analysis-artifact read / keyset paging / soft-delete exclusion / artifact-type filter / cross-owner not-found existence-non-leak / futureDevNoHistory.empty] = PR #143; 1069 = 1065 + 4 audit-trgm shape [pg_indexes `indexdef` server-truth: 3 GIN trgm index names / `gin`+`gin_trgm_ops`+`lower(...)` expression / partial `IS NOT NULL` on the nullable target_id+reason, none on NOT-NULL event_kind]; 1065 = 1061 + 4 audit-index shape [pg_indexes `indexdef` server-truth: names / composite column ORDER as contract / partial predicates / expression+ops]; 1061 = 1057 + 4 summary-timeframe [2 unit: engine passthrough "1m" / default None; 2 integration: admission→worker chain persists "1m" into summary row + headline + read model / un-timeframed revision persists None]; 1057 = 1054 + 3 tool-call envelope shadowing regression [artifact.create status not shadowed by artifact_status / task.query status namespaced as task_status / replay status not shadowed]; 1054 = 1048 + 6 data-queue redelivery [3 unit: `job_kind` discriminator resolution / missing+unknown → None / `DATA_ACTOR_BY_KIND` registry completeness; 3 integration: stale-QUEUED-only listing oldest-first + kind resolved / Admin routing + skip-legacy + audit / non-admin rejected before any audit]; baseline 1048 = 1015 + 13 first-Admin bootstrap [env-unset baseline / match+no-admin → Admin+audit+outbox / active-Admin fail-closed / non-matching baseline / case+whitespace normalization / settings env read / route pass-through] + 8 bootstrap-status read endpoint: unit configured-flag + integration window open/closed vs a real DB + route reads the setting + 12 CP-Gen candidate generation: reproducibility / order-independence / output_contract+resolved_refs hash sensitivity / GENERATOR_VERSION namespace shift / fail-closed directional→ta.* + condition→cond.* + empty-resolved skip / output_type alias / DESCRIPTION uncertainty / test_plan dep listing).
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
- **Next:** **post-V1 FINALIZATION sonrası — NO teed-up (confirmed) open work remains.** Latest: the
  FINALIZATION wave (#146 agent tool-call history + #147 seed FK fix + #148 smoke script + #149 README
  refresh + #150 USAGE/ARCHITECTURE) landed on top of the capability READ surfaces (#143/#144 → doc-22
  END-TO-END COMPLETE). All route surfaces bound; TIER 2 page map 24/24; TIER 3 candidates all closed
  (data-queue redelivery #129/#131, SSE reconnect #133, tool-call status shadowing #135, audit indexes
  #139/#141). Backend **1089** (CI server-truth), frontend **246**. **On session start: ASK the user for
  direction** — candidates (none confirmed): (a) Docker compose full-stack live proof (`docker compose up
  -d --build` + `make smoke` — the single honest boundary of the finalization session: Docker Desktop was
  stuck on a self-update GUI approval on this machine); (b) a new user-brought feature; (c) an
  orphan/dead-code scan (any other repo function/endpoint/query left unbound — #144 and #146 closed
  exactly such orphans; template: a written-but-unreadable append log → projection + gated GET, write
  path stays gated); (d) minor backend cleanup/consistency (no migration). OUT OF SCOPE: retention
  auto-purge (doc 20 §16), LLM generation (Future-Dev), Graphic View renderer (doc 22 §1/§16/§17 "V18
  static placeholder retained"). The **3 priority tiers** below are the historical record (all landed):
  
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
    until runs are linked.
  - ✅ **Embedded System Packages page (PR #99, MERGED — FRONTEND)** — the `/packages/embedded`
    placeholder becomes the real page, binding the doc 09 READ surface of `routes/esp.py`
    (role-aware resolver-registry list + detail + Pre-Check-parity resolve probe).
    **FRONTEND-ONLY** (backend 1048 stays, no migration). NEW `lib/esp.ts` (wire types mirror
    `queries/esp.py` verbatim — `EspRegistryRow`/`EspPackageDetail`/`EspContract`/
    `ResolveResult`; `RESOLVER_TRUST_STATES`/`RUNTIME_ADAPTERS` hydration mirrors + L4
    `ESP_PERFORMANCE_FIELDS` (N/A by nature, doc 09 §14); hooks under `["esp"]` — no dedicated
    SSE event, swept by `resource.changed`: `useEspRegistry` trust_state facet (empty facet
    never sent, canonical_key keyset) + `useEspPackage` + `useResolveProbe` — the §4.3 probe is
    a PURE READ (creates nothing, no audit row) so the POST carries NO Idempotency-Key and
    invalidates nothing; `parseSignatureParams`/`trustTone`) + NEW `pages/Embedded.tsx`
    (registry table + trust facet + detail card with contract/registry snapshot + OCC-ready
    `registry_version`; Resolve Probe — ordered param TYPES are identity, success renders the
    EXACT pinned revision P4/L5, typed failures RESOLVER_NOT_RESOLVED/SIGNATURE_MISMATCH/
    ADAPTER_INCOMPATIBLE verbatim doc 09 §9.1–9.3). `App.tsx` REAL_PATHS 13→14; `nav.ts`
    UNCHANGED (24). +8 vitest (`test/embedded.test.tsx`, apiStub ORDERED — resolve POST +
    detail GET precede the list prefix) → **frontend 113 → 121**; CI 3/3. Honest boundary:
    read slice — registry MUTATIONS (create/activate/deprecate, Admin-only, `X-Registry-Version`
    OCC + Idempotency-Key) NOT dispatched (later slices; `row_version`/`registry_version`
    tokens ready). **Rationale Families (`rationale.py`) landed full CRUD + assignment
    batch editor in PR #101 — the shared-editing mutation pattern (OCC + Idempotency-Key, no
    Admin gate) is a base for the ESP/Library registry mutation slices.**
  - ✅ **Market Data page (PR #103, MERGED)** — the `/market-data` placeholder becomes the real
    page: doc 11 READ surface (registry list + detail + approved-bundle resolve probe) + the owner
    INGEST chain (create dataset / raw-upload start+finalize / durable 202 analysis / schema
    mapping) — 8 of 10 `routes/market_data.py` endpoints. NEW `lib/marketData.ts` (`["market-data"]`
    hooks; `useCreateDataset` sends NO Idempotency-Key — the route reads none; finalize/analysis
    fresh key per attempt; `useConfirmMapping` omits a blank confirmed_mapping →
    `MAPPING_REVIEW_REQUIRED` verbatim; `MARKET_DATA_TYPES`/`MARKET_REVISION_STATES` mirrors +
    `parseMappingLines`) + NEW `pages/MarketData.tsx` (Create/Registry/Detail + Step 1/2 ingest +
    `BundleProbe` — 404 verbatim, never "latest"); `App.tsx` REAL_PATHS 15→16; `nav.ts` UNCHANGED
    (24). +12 vitest (`test/marketData.test.tsx`, apiStub ORDERED) → **frontend 128 → 140**;
    frontend-only, no migration, backend base stays 1048. Honest boundary: revision lifecycle
    actions (revise/successor + Admin approve/deprecate — If-Match `"rv-N"` OCC + Idempotency-Key)
    are the NATURAL FOLLOW-UP slice (detail `row_version` token ready); raw bytes never travel
    through the page (evidence row pins object key + digest); analysis job id informational
    (`["jobs"]` list surface permanently absent). Lifecycle ACTIONS landed next in PR #105.
  - ✅ **Market Data lifecycle actions (PR #105, MERGED)** — closes the PR #103 boundary: the 4
    unbound lifecycle endpoints wired → 10/10. EMPIRICAL (route signatures READ — the handoff
    summary was WRONG): successor + deprecate read NO If-Match/Idempotency-Key; only revisions +
    approve carry both; approve + deprecate Admin-only. NEW `postWithOcc(path, rowVersion, body)`
    helper (If-Match `"rv-N"` + fresh Idempotency-Key); `LifecycleSection` composers in
    `pages/MarketData.tsx`; +6 vitest → 146.
  - ✅ **Research Data page (PR #107, MERGED)** — `/research-data` real page: role-aware read
    surface + owner ingest chain (create[DR3 market-link]/upload start+finalize/durable 202
    analysis), 6/14 endpoints. EMPIRICAL: create + upload-start read NO Idempotency-Key;
    finalize/analysis fresh key per attempt. NEW `lib/researchData.ts` + `pages/ResearchData.tsx`;
    +11 vitest → 157.
  - ✅ **Research Data lifecycle actions (PR #109, MERGED)** — the remaining 8 endpoints wired →
    14/14, **Packages & Data group fully bound**. revise/approve/revoke via `postWithOcc`
    (If-Match `"rv-N"` + Idem); time-policy/field/feature defs NO headers; agent + evidence bundle
    compilers PURE READ (no Idem, no invalidation, content-addressed `bundle_hash`); approve/revoke
    Admin-only (`APPROVAL_REQUIRES_ADMIN` verbatim). NEW `components/ResearchLifecycle.tsx` 6
    composers; +11 vitest → 168.
  - ✅ **Backtest Ready Check page (PR #111, MERGED)** — `/backtest/ready-check` real page binding
    `routes/readiness.py` (doc 14 §4/§7/§9) — the strategy→RUN gate of the Backtest group
    (RUN/History bound since PR #72). NEW `lib/readiness.ts` (wire types `ReadinessIssue`/
    `ReadinessSummary`/`ReadinessReport`/`CurrentReadiness`/`RunCheckResult`; enums.py mirrors
    `READINESS_STATE_LABELS`/`READINESS_STATE_TONES` + `NOT_CHECKED_STATE` +
    `readinessStateLabel`/`readinessStateTone`/`severityTone`; `["readiness"]` hooks — no dedicated
    SSE event, swept by `resource.changed`: `useCurrentReadiness`/`useReadinessReport`/
    `useRunReadinessCheck`). EMPIRICAL route finding (signature READ): the OCC token is NOT
    `"rv-N"` — it is the composition FINGERPRINT, carried BODY-form as `expected_fingerprint`
    (not If-Match; the route's `_resolve_expected` prefers the body) + fresh Idempotency-Key per
    attempt; 409 `CompositionStale` = RC-09 verbatim; success invalidates `["readiness"]` +
    `["mainboard"]` (the default-Mainboard `ready_summary` moves). NEW `pages/ReadyCheck.tsx` —
    two modes: `?report=<id>` immutable deep-link + default workbench (`useDefaultMainboard`
    composition → current readiness → guard-toggled run); stale ("re-run") vs superseded ("a newer
    report exists") distinction from SERVER `state` (`state === "stale"`), never re-derived —
    self-review found + fixed the `stored_state !== state` bug (showed "stale" for superseded too)
    + regression test. `App.tsx` REAL_PATHS 17→18; `nav.ts` UNCHANGED (24). NEW
    `test/readyCheck.test.tsx` +6 (apiStub ORDERED; `findBy*` for chained loading —
    composition→readiness second wave) → **frontend 168 → 174**; frontend-only, no migration,
    backend stays 1048. Honest boundary: RUN admission (`POST /backtest-runs`) stays on the RUN
    page (doc 14 §9.3 scope); the page reads only the default Mainboard composition (RUN-page
    pattern; a real Stage-3 Mainboard page may lift it app-level).
  - ✅ **Portfolio / Equity Allocation page (PR #113, MERGED)** — `/portfolio` real page binding the
    FULL `routes/allocation.py` surface (5/5 endpoints, doc 13 Stage 4a) — the editor of the
    allocation draft Ready Check reads; **Backtest nav group CLOSED**. EMPIRICAL (signatures read):
    draft GET body `row_version` = live OCC token (0 = no plan yet = valid creation token);
    PUT/revisions carry OCC **BODY-form `expected_row_version`** (route prefers body over If-Match)
    + fresh Idempotency-Key per attempt; validate reads NO body/headers (new immutable
    `validation_report_id` + audit row per run); sync POST is a **PURE READ** merge preview (query
    layer — no Idem, no invalidation; removals apply only via an explicit Save PUT, §14#9);
    `item_type` never sent (server-derived, §8.2); stale → 409 `ALLOCATION_DRAFT_CONFLICT` verbatim.
    NEW `lib/allocation.ts` (wire types verbatim; `ALLOCATION_CURRENCIES`/`COMPOUNDING_MODES`/
    UPPERCASE `ALLOCATION_STATE_LABELS`+`_TONES` mirrors; `["allocation"]` hooks — no dedicated SSE
    event, swept by `resource.changed`; draft PUT returns readiness_invalidated:true → invalidates
    `["allocation"]`+`["readiness"]`+`["mainboard"]`+`["audit"]`, revision → `["allocation"]`+
    `["audit"]`, validate → `["audit"]` only) + NEW `pages/Portfolio.tsx` (`DraftEditor`
    `key={row_version}` remount-reseeds from the server head, never merges; mutation state lives in
    the PARENT so results survive the remount; issues + derived amounts rendered VERBATIM — the
    client never recomputes capital math; `severityTone` reused from `lib/readiness`). `App.tsx`
    REAL_PATHS 18→19; `nav.ts` UNCHANGED (24). NEW `test/portfolio.test.tsx` +7 (apiStub ORDERED;
    OCC 0-token + no-item_type body asserts; pure-read sync header assert) → **frontend 174 → 181**;
    frontend-only, no migration, backend stays 1048. Honest boundary: page reads only the default
    Mainboard composition (RUN/Ready-Check pattern); Validate checks the SAVED draft (not unsaved
    edits — stated in the UI); the sync preview has no "Apply" button (merge is done in the editor
    and applied by Save — the §14#9 explicit-destructive-PUT contract).
  - ✅ **User Manual page (PR #115, MERGED)** — `/user-manual` real page binding the FULL
    `routes/manual.py` surface (7/7 endpoints, Stage 7a doc 21) — **Docs nav group CLOSED**
    (Future Dev #82 + User Manual #115). EMPIRICAL (signatures read): OCC is TWO different
    BODY-form tokens — `expected_stream_version` INT on create/upload/delete (optional
    server-side; the client ALWAYS guards with the rendered snapshot, UM-13/UM-15; stale →
    409 `MANUAL_STREAM_CONFLICT` verbatim) and `expected_head_revision_id` STR on revisions
    (body wins over If-Match; 409 `MANUAL_REVISION_CONFLICT`) + fresh Idempotency-Key per
    attempt; DELETE carries an OPTIONAL BODY (reason + expected_stream_version — `api.del`
    takes neither → `apiRequest` direct); `:restore` is `require_trash_admin` (NOT manual
    admin), no body, returns the Trash-core `RestoreResult` (`lib/trash.ts` type REUSED);
    `get_manual_section` NOT routed (doc 21 §12 Agent Tool Gateway). NEW `lib/manual.ts`
    (`ManualBlock`/`ManualSection`/stream+search pages [`heading_path` STRING, not a list]/
    `PublishResult`/`ReviseResult`/`DeleteResult` + `ACCEPTED_UPLOAD_EXTENSIONS` mirror;
    `["manual"]` hooks — no dedicated SSE event, swept by `resource.changed`; blank search
    query never fetches, doc 21 §14; mutations invalidate `["manual"]`+`["audit"]`
    (+`["trash"]` on delete/restore)) + NEW `pages/UserManual.tsx` (`BlockView` canonical
    block renderer — TEXT nodes only, unknown type fail-closed; baseline actions hidden from
    server-truth `is_baseline` [UM-10]; two-step delete confirm with PARENT-held `lastDelete`
    result; composers never client-role-gated, doc 21 §2). `App.tsx` REAL_PATHS 19→20;
    `nav.ts` UNCHANGED (24). NEW `test/userManual.test.tsx` +8 (apiStub ORDERED —
    `:upload`/`:restore`/`/revisions` fragments precede the create prefix) → **frontend
    181 → 189**; frontend-only, no migration, backend stays 1048. Honest boundary: revision
    replacement is "V18 UI not exposed" in doc 21 §7 — bound as an explicit Admin maintenance
    affordance (PR #95 precedent; server gates end-to-end); upload carries UTF-8 TEXT only
    (route contract `content: str` — raw bytes never travel; PDF/DOCX not V1); Trash purge
    stays a separate re-auth slice.
  - ✅ **Strategy Details page (PR #117, MERGED)** — `/strategy` real page binding the FULL
    `routes/strategy.py` surface (9/9 endpoints, Stage 3b doc 02 §7–§9) — the biggest Workspace
    surface: editor draft workflow (create root+draft / full-payload PATCH / pure validate /
    save immutable revision / clear) + root header + revision history + immutable `?revision=`
    deep-link. EMPIRICAL: PATCH/save/clear OCC BODY-form `expected_draft_row_version` INT (body
    wins over If-Match; REQUIRED; draft row_version starts at 0) + fresh Idempotency-Key;
    validate reads NOTHING (no audit → no Idem, no invalidation); save re-pins attached
    Mainboard items → `["strategy"]+["mainboard"]+["readiness"]+["audit"]`; NO root→draft
    lookup (draft handle lives in the `?draft=` URL). NEW `lib/strategy.ts` + 
    `pages/StrategyDetails.tsx` (PayloadEditor `key={row_version}` remount-reseed; mutation
    state parent-held; two-step Clear); `App.tsx` REAL_PATHS 20→21; +8 vitest → **197**;
    frontend-only, no migration, backend stays 1048.
  - ✅ **Trading Signal & Trade Log twin pages (PR #119, MERGED)** — `/trading-signal` +
    `/trade-log` real pages in ONE slice binding the FULL `routes/trading_signal.py` +
    `routes/trade_log.py` twin surfaces (6+6 endpoints, Stage 3c/3d docs 04/05): upload
    immutable TXT/CSV source asset (content-addressed dedup) → durable 202 import job →
    import report → Save & Add native work object → OCC-guarded revision append. EMPIRICAL:
    all 4 POSTs per twin read a fresh Idempotency-Key; the ONLY OCC token is BODY-form
    `expected_head_revision_id` STR on `/revisions` (server-optional — client always sends
    the rendered head); `workspace_id` never sent (server resolves the default Mainboard).
    TWIN DIFFS mirrored verbatim: report evidence key `normalized_event_revision_id` (TS) vs
    `record_batch_revision_id` (TL); TL revisions always `available_time=null` (historical,
    doc 05 §10.4); config TS `time_policy`+`event_model` vs TL `time_model`. Import report
    keyed `["jobs","<kind>-import",jobId]` — the FIRST page binding of the `job.updated` SSE
    key (terminal-stop poll fallback `TERMINAL_IMPORT_STATUSES`, INF-11). Create-with-attach
    invalidates `["mainboard"]+["readiness"]` (composition hash moves → prior Ready report
    STALE); revisions NEVER auto-repin. Pin/delete stay Mainboard operations (CR-01/TL-01).
    NEW `lib/tradingSignal.ts` + `lib/tradeLog.ts` + `pages/TradingSignal.tsx` +
    `pages/TradeLog.tsx` (URL modes `?job=`/`?root=`; report-seeded JSON payload editor,
    `CreateCard` key remount-reseed); `App.tsx` REAL_PATHS 21→23; +11 vitest → **208**;
    frontend-only, no migration, backend stays 1048.
  - ✅ **ESP registry mutation actions (PR #121, MERGED)** — the 3 mutation endpoints of
    `routes/esp.py` bound onto the existing `/packages/embedded` page (read surface was
    PR #99) → **`esp.py` surface COMPLETE** (`library.py` already 2/2 → no unbound endpoint
    left in Packages & Data). EMPIRICAL (signatures read): create (201) carries NO
    OCC/Idempotency-Key/Admin-gate — any authenticated actor proposes a CANDIDATE (doc 09
    §5); activate + deprecate carry the **X-Registry-Version HEADER-form PLAIN-INT OCC**
    (NOT If-Match `"rv-N"`; source `detail.registry.registry_version`) + fresh
    Idempotency-Key per attempt + Admin-only at the command layer
    (`ensure_can_activate`/`_deprecate` — UI never pre-gates; stale → 409
    `RESOLVER_REGISTRY_CONFLICT`, non-Admin → 403 `APPROVAL_REQUIRES_ADMIN`, both verbatim).
    `lib/esp.ts` extended: Create/Activate/Deprecate result+input wire types (command return
    dicts verbatim), `VISIBILITY_SCOPES` mirror, `postWithRegistryVersion` helper,
    `useCreateEsp`/`useActivateResolver`/`useDeprecateResolver`, `canActivate`/`canDeprecate`
    state-machine UI hints (activate only from `candidate`, deprecate only from
    `trusted_active`; server re-validates transition AND gate); mutations invalidate
    `["esp"]`+`["audit"]`. `pages/Embedded.tsx`: `ProposeResolverCard` (`parseSignatureParams`
    REUSE; disabled until key + [params OR return]) + detail `LifecycleActions`
    (`ActivateComposer` head-default / `DeprecateComposer` reason REQUIRED). 2 existing probe
    tests scoped via `within(region)` (the Propose form reuses the same labels).
    `App.tsx`/`nav.ts` UNCHANGED; +5 vitest → **213**; frontend-only, no migration, backend
    stays 1048. Honest boundary: advanced contract fields (`input_contract`/`output_contract`/
    `dependency_snapshot`/`evidence`) not in the propose form — server defaults (`{}`/null).
    ~~outsource-signal~~ ✅ **LANDED (PR #123)** — doc 03 type chooser, pure presentation, no
    backend surface (empirical answer: NO new backend slice was needed) → **TIER 2 page map
    COMPLETE (24/24 real)**.
    ~~Mainboard live page + composition operations~~ ✅ **LANDED (PR #125)** — doc 01 composition
    plane; `routes/mainboard.py` 8/8 bound (`mainboard.py` surface COMPLETE); the PERMANENT
    "attach+Pin+delete on no landed page" boundary is RETIRED.
    ~~Trash purge re-auth slice~~ ✅ **LANDED (PR #127)** — the `/trash` page (restore landed #86)
    gains the destructive purge, binding the last unbound `routes/trash.py` endpoint (POST
    /trash-entries/{id}/purge, doc 20 §8.3) → **trash.py surface COMPLETE** (mainboard.py #125 +
    trash.py #127 → no unbound route endpoint remains). Two-phase 202 (request → purge_pending +
    durable maintenance job; worker runs the actual purge); body REQUIRES confirmation_phrase
    (=display_name||entity_id, else PURGE_CONFIRMATION_INVALID) + reauth_proof (non-empty, V1
    presence-only, else REAUTH_REQUIRED); OCC = BODY-form expected_row_version INT (body wins over
    If-Match) = entry row_version, stale → STALE_REVISION; fresh Idempotency-Key; purge eligible on
    the SAME recoverable statuses as Restore (shares _assert_entry_recoverable) → page gates on
    server-truth restore_eligible. `lib/trash.ts` PurgeResult wire type (omits display_name) +
    useRequestPurge (Idem header + body-OCC, invalidates ["trash"]+["audit"]) + `pages/Trash.tsx`
    two-step PurgeComposer (§9 copy verbatim, display name captured at accept time) + .btn-danger;
    +4 vitest → 232; frontend-only, no migration, backend stays 1048. **Remaining candidates:**
    TIER 3 deferred (retention auto-purge [doc 20; related to the purge worker] / data-queue
    redelivery / SSE streaming e2e / tool-call status shadowing) + minor backend follow-ups
    (LLM generation stays Future-Dev, out of scope).
  
  **TIER 3 — Data/ops:**
  - ✅ **Data-queue redelivery (operator recovery tool) — PR #129 (LANDED)** — `job_kind` discriminator on the 4 `data`-queue payloads + `application/jobs/data_queue.py` (`list_redeliverable_data_jobs`) + `apps/worker/actors.py::DATA_ACTOR_BY_KIND` + `commands/data_queue.py::redeliver_data_queue_jobs` + Admin `POST /admin/data-queue/redeliver` routes stuck (QUEUED-past-grace) `data` jobs back to their actor (INF-03, doc 20 §6); scheduler UNTOUCHED (`data` stays operator-only); legacy pre-discriminator rows → `skipped_unknown_kind` (never guessed); backend 1048→1054, no migration.
  - ✅ **Data-queue redelivery Admin UI — PR #131 (LANDED, FRONTEND-ONLY)** — the #129 backend endpoint bound onto the `/panel` page as an `OperatorRecoveryCard`. `lib/adminPanel.ts` (additive): `DataQueueRedeliverResult`/`DataQueueRedeliverable` wire types (mirror `commands/data_queue.py` return dict verbatim → `{scanned, redeliverable:[{job_kind,job_id}], skipped_unknown_kind}`) + `DATA_JOB_KIND_LABELS`/`dataJobKindLabel` (mirror `jobs/data_queue.py` `DATA_JOB_KINDS`, hydration-only) + `useRedeliverDataQueue` (route reads only the optional `grace_seconds` query, `ge=0`, `0`=sweep all → **no OCC token / Idempotency-Key**; success invalidates `["audit"]` — the command emits one `data_queue.redelivery_requested` audit+outbox, no data-queue read surface to sweep). `pages/Panel.tsx` `OperatorRecoveryCard`: grace-seconds hint input + routable result table (server job_kind labels + job id) + scanned/re-dispatched/skipped counts + un-routable legacy-row note (counted, never guessed); Admin-only server-side (non-Admin 403 verbatim); client blocks a negative/non-integer grace before dispatch. `test/panel.test.tsx` +3 → 235; `App.tsx`/`nav.ts` UNCHANGED (`/panel` already real); review 0 CRITICAL/HIGH. Honest boundary (PERMANENT): re-dispatch stays an OPERATOR action (scheduler never auto-routes `data`, doc 20 §6); `["jobs"]` has NO HTTP list surface (this is a POST recovery action); operator = Admin. **Data-queue redelivery fully closed (backend #129 + Admin UI #131).**
  - ❌ **Retention auto-purge — OUT OF SCOPE (NOT an implementable slice)** — doc 20 §16 explicitly: *"Automatic purge remains disabled in Production V1"* → a Future-Dev boundary; purge is ALWAYS explicit Admin confirm+re-auth. Do NOT build a scheduled auto-purge sweep for V1.
  - ✅ **SSE streaming e2e reconnect resilience — PR #133 (LANDED, FRONTEND-ONLY)** — `lib/sse.ts::connectEvents` now survives a non-retryable stream close. Native `EventSource` auto-retries only while `readyState===CONNECTING`; on `CLOSED` (server closes non-retryably / initial handshake fails) native retry STOPS and the dashboard would sit SSE-blind. Fix: readyState-aware `onerror` (`CONNECTING`→status `"connecting"` native retry; `CLOSED`→own exponential backoff `RECONNECT_BASE_MS=1000`→`RECONNECT_MAX_MS=30000` cap) + a successful reopen (native OR backoff) fires the same gap full-refresh as before (INF-11); backoff ramp resets on `open`; `dispose` cancels the pending timer + detaches the current source's listeners (every reopen replaces the prior `teardownSource` — no handler leak). `connectEvents(queryClient, onStatus?)` signature + SSE taxonomy / `EVENT_QUERY_KEYS` UNCHANGED (`Layout.tsx:94` call-site untouched). `test/sse.test.ts` `FakeEventSource` extended with `readyState`+statics+`error()`+`constructed`; +3 vitest (transient stays connecting / fatal reconnects+self-heals / dispose cancels backoff) → 238; no migration, backend 1054 unchanged.
  - Tool-call status shadowing (CR-08 follow-up) — deferred
  
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

## V18-R2 · R2-07 — Golden-path E2E: Ready PASS → RUN SUCCEEDED → inline Result (GAP madde 12)

- **Seed:** `SEED_E2E_GOLDEN=1` idempotent modu (`entropia/apps/seed.py`): non-Admin owner
  `user_e2e_fixture` (bootstrap-Admin korunur — mod `seed_identities`'i atlar), ACTIVE+APPROVED
  `E2E Golden BTCUSDT 1h` dataset (resolution 1h, instrument BTCUSDT) + MinIO'da processed
  Parquet asset (1500 deterministik saatlik bar, sine-wave), PUBLISHED+PASSED+APPROVED
  `E2E Golden SMA` indicator package (`dependency_snapshot.resolved[0].canonical_key=ta.sma`),
  canonical 6 rationale family. Yol kararı: seed > API zinciri (async worker'sız, deterministik).
- **Spec:** 05 spec strict golden path'e yeniden yazıldı; blocked/error=FAIL; URL "/" assert;
  RUN disabled→enabled geçişi; run terminal `succeeded`; inline Result Headline+Manifest
  hash+Execution key. Yeni `e2e/pages/InlineStrategyEditor.ts`. Kart Apply'ları PATCH
  yanıtı + draft refetch bekler (full-payload replace bayat-draft yarışı gerçek bug kaynağıydı).
- **CI:** `e2e.yml` seed adımı. Kanıt: host-native tam stack'te temiz 10.0s + kirli 32.1s YEŞİL.
- **Bulgular:** (1) rationale family inline set edilemiyor → spec admin+Advanced editör
  (ayrı iş chip'i); (2) Validate↔readiness parity açığı (slippage/base size/rationale);
  (3) soft-deleted work object'in mainboard item'ı readiness'te kalıcı ITEM_UNAVAILABLE.

## V18-R2 · KALAN-A — Market Data ham kaynak dosya UPLOAD UI (video 9:24–12:37, GAP 18)

- **Empirik tespit (canlı Docker'sız stack):** backend ingest zinciri (PR #103/#105) API'den
  sağlam (`draft→uploading→analyzing→verified`, validation `pass`, analysis job gerçek CSV
  parse); UI kopuktu: kurulum kartında dosya seçici yok, Upload/Finalize/Request analysis
  3 ayrı manuel buton, analysis sırasında polling yok.
- **MarketData.tsx `CreateDatasetCard`:** birincil `Raw source file *` Browse File girişi +
  "Create dataset & upload" tek submit → `create → upload (progress+Cancel) → finalize →
  analysis` zinciri; `IngestStageList` aria-live textual aşama listesi; "Retry from failed
  step" kalınan aşamadan devam (entity/asset ref'leri pinli — dataset yeniden yaratılmaz).
  Sözleşmeler verbatim: create Idempotency-Key'siz; upload/finalize/analysis taze key/deneme;
  ham bytes sayfadan geçmez (asset id + digest evidence).
- **lib/marketData.ts (additive):** `ingestRefetchInterval` pure helper (yalnız
  `uploading`/`analyzing` → 2000ms, aksi false) + `useMarketDataset.refetchInterval`.
- **e2e 02 tam yolculuk (26s, canlı stack):** Browse File → chained ingest → 202 →
  poll `verified` → ayrı admin context approve → owner `approved` → bundle `Pinned`.
  POM `MarketDataPage` genişledi (expectIngestStarted / waitForRevisionState /
  openFromRegistry / approveHeadRevision / resolveApprovedBundle); spec 03 aynı POM'la yeşil.
- **Sayılar:** vitest 511/511 (marketData 29, +3 yeni: zincir sırası+header kuralları,
  dosyasız submit bloğu, kalınan-aşamadan retry; `ingestRefetchInterval` unit); tsc/eslint/
  build temiz. routes/market_data.py DEĞİŞMEDİ; migration yok.
- **Honest boundary:** schema-mapping composer'ı `needs_review` durumu için manuel kaldı
  (temiz CSV auto-map ile verified'a gider); registry tablosu analysis bitişinde otomatik
  yenilenmez (yalnız detail poll'lar) — kullanıcı akışı detail üzerinden ilerler.

## V18-R2 · R2-13 — Screenshot matrisi + V18 side-by-side + screenshot regression

- **Ne landed:** (1) `frontend/e2e/specs/10-screenshot-matrix.spec.ts` — 22 sayfa (+panel-logs)
  × 5 durum × 1280/1440/1920 (+375/768 Mainboard & inline editörler) = 122 PNG baseline
  (`frontend/e2e/screenshots/baseline/<sayfa>/<durum>--<genişlik>.png`, ~20 MB, canlı
  host-native seeded stack `entropia_e2e07`); (2) `12-prototype-capture.spec.ts` — V18
  mockup'ın kendi `show*` fonksiyonlarıyla 20 referans ekran (`screenshots/prototype/`);
  (3) `11-visual-regression.spec.ts` — 8 kritik sayfa `toHaveScreenshot` regression
  (maxDiffPixelRatio 0.02, animasyon kapalı, `time`/`[data-e2e-volatile]` mask, baseline
  commit'li `-darwin`); (4) `docs/implementation/v18_visual_deviations.md` — madde madde
  sapma listesi: 6 FIX adayı (mobil taşma/katman F-1, display-label F-2, CP yerleşim F-3,
  allocation ULID F-4, history headline F-5, TS/TL yoğunluk F-6) + PO-APPROVE kümesi.
- **Durum üretimi dürüst:** loading = API stall (gerçek in-flight UI), error = zorlanmış 500
  zarfı ("Backend unavailable" banner), permission-denied = server-truth 403 render'ı; empty =
  taze kullanıcı (paylaşımlı DB sınırı README'de).
- **Test:** matris 5/5, regression üretim + tekrar koşum 8/8 (flake yok); varsayılan
  `npm test` yeni katmanları `--grep-invert "@screenshots|@visual|@prototype"` ile dışlar.
- **Honest boundary:** uygulama koduna sıfır dokunuş; regression baseline'ları yalnız aynı
  seed verisine karşı anlamlı; `-linux` baseline'ları CI'da ilk `screenshots:update` ile
  üretilecek; derin kıyası R2-14'e bırakılan sayfalar sapma dokümanında listeli. Slice
  hiçbir maddeyi "Complete" İLAN ETMEZ — PO onayı R2-14.

## V18-R2 · R2-14 — Nihai kabul geçişi: axe-core taraması, klavye akışı, 375px taşma (GAP madde 17 + 20)

R2 dalgasının **son slice'ı**. Çıktı: **`docs/implementation/v18_final_acceptance.md`** — GAP
madde 20'deki 11 nihai kabul koşulu canlı seed'li stack'te TEK TEK doğrulandı, her koşula kanıt
referansı (spec adı / screenshot yolu / PR) yazıldı. **10/11 PASS; 20.11 (22 sayfa screenshot
setinin kabulü) yalnız product-owner imzasına bağlı** → GAP madde 17 gereği bu slice de
`entropia_v18_remediation_status.md` içindeki HİÇBİR satırı Complete'e çekmedi.

- **Kapatılan iki bulgu:** (1) **375px yatay taşma** (sapma 1.6/1.7) — kök neden: Mainboard
  section grid'inin auto track'i 64 karakterlik composition hash'inin min-content genişliğine
  büyüyordu (375px viewport'ta ölçülen 640px section). Fix: section grid + `.kv` value kolonuna
  `minmax(0,1fr)` + `overflow-wrap`; taşan eleman **110 → 0**. (2) **Escape ile kapanma** — Add
  menüsü ve Add Package popover'ı Escape'e kapanmıyordu; YENİ `useEscapeToClose` hook'u ikisine
  de bağlandı, focus tetikleyiciye döner.
- **Kayda geçen a11y sapmaları (PO kararına):** `A11Y-01` — 228 serious contrast node'unun
  tamamı canonical v18 paletinden geliyor (`--accent #00a9e8`, `--text-dim #888888`), yani
  değişiklik kod düzeltmesi değil **tema kararıdır**; `A11Y-02` `link-in-text-block`.
  22 sayfanın hepsinde **critical = 0**. Tarama gate'i mevcut sınırı DONDURUR: kayıtlı iki kural
  dışında herhangi bir serious ihlal koşuyu düşürür.
- **Yeni opt-in katman:** `frontend/e2e/specs/13-a11y-scan.spec.ts` (22 sayfa axe-core) +
  `14-keyboard-flow.spec.ts`, `npm run a11y` arkasında — düz `npm test`'ten hariç.
- **Test (canlı stack):** e2e ana paket **20/20**, a11y **2/2**, responsive **6/6**, vitest
  **514/514**, tsc + eslint temiz.
- **Dürüst sınırlar:** 20.11 AÇIK (teknik kıyas tamam, imza yok); A11Y-01/02 kapatılmadı —
  WCAG 2.2 AA kontrast maddesi bugün karşılanmıyor; **ekran okuyucu (NVDA/VoiceOver) denetimi
  YAPILMADI** (`~/.claude/rules/accessibility.md` iki okuyucu ister) — açık iş; klavye denetimi
  temel akışla sınırlı (login → Mainboard → Add menü); sapma listesinin 10 sayfası (03, 07, 09,
  10, 12, 17, 18, 19, 21, 22) için derin madde-madde kıyas yapılmadı; doğrulamalar host-native
  local stack'te, bu oturumda CI'da koşmadı.
- **PO karar tablosu:** D-1…D-9 (`v18_final_acceptance.md` §4) — görsel sapmaların toptan kabulü,
  F-2…F-6 mini slice kararları, A11Y-01 için (a)/(b)/(c) seçenekleri, 20.11 onayı.

## V18-R2 dalgası — toplu kayıt (#325–#343 merged + R2-14)

GAP belgesi (`docs/spec/Entropia_V18_Guncel_Arayuz_Eksikleri_ve_Yanlis_Anlamalar.md`) → yol
haritası `docs/V18_R2_ROADMAP.md` (16 slice + 2 kapanış, her biri paste-ready prompt'lu) → ayrı
oturumlarda kodlandı. Yukarıda kendi tam kaydı olmayan slice'ların özeti (ayrıntı: her birinin
`docs/STAGE2_HANDOFF.md` landed girdisi):

| Slice | PR | Ne getirdi |
|---|---|---|
| R2-01a | #325 | TS/TL editörleri `components/{TradingSignal,TradeLog}Editor.tsx`'e çıkarıldı (saf refactor; `mode: page\|inline` forward-contract) |
| R2-01b | #326 | Editörler Mainboard satırlarına inline mount edildi — route launcher bitti; URL `/` kalır |
| R2-02 | #327 | Üst menü Add eylemleri Mainboard add-intent dispatcher'ına bağlandı (tek Add modeli) |
| R2-03 | #328 | Add Package seçim popover'ı + usable package revision'ından derived Strategy Draft |
| R2-04 | #329 | TS/TL typed config formları — ham JSON payload editörleri kalktı |
| R2-05a | #330 | Strategy typed formlar: override'lar, reference chain'ler, filtreler, Kelly sizing |
| R2-05b | #331 | Advanced raw payload admin-gate'li; Mainboard composition kontrolleri kapalı disclosure'a |
| R2-06 | #332 | Research Data server-truth Approved Market Data dependency picker (sahte kilit bitti) |
| R2-07 | #334, #335 | Katı golden-path E2E (Ready PASS → RUN SUCCEEDED → inline Result) + `SEED_E2E_GOLDEN` fixture + tek seferlik rationale-family set |
| R2-08 | #336, #338 | Teknik-ID sweep — picker + read-only provenance; TS/TL import instrument değeri sembol metni kalır |
| R2-09 | #337 | Admin-only eylemler `/me` projection'ı arkasında fail-closed |
| R2-10 | #333 | App-shell backend health + request timeout + gerçek UNAUTHENTICATED durumu |
| R2-11 | #339 | Mobil app shell — hamburger menü, body seviyesinde sıfır yatay taşma |
| R2-12 | #340 | CP typed baseline metadata + request→published tam lifecycle E2E |
| KALAN-A | #341 | Market Data Browse File tam ingest zincirini başlatır (video 9:24–12:37) |
| KALAN-B | #342 | Mainboard "Use Allocation Backtest" modu + per-item pay rozetleri (video 7:16–9:24) |
| R2-13 | #343 | 22 sayfa screenshot matrisi + V18 side-by-side sapma listesi + visual regression |
| R2-14 | (bu branch) | Nihai kabul geçişi — yukarıdaki tam kayıt |

**Dalga boyunca sabit kalanlar:** alembic head `0035_portfolio_rules` (migration YOK),
`ENGINE_VERSION` sabit, tüm OCC token biçimleri / Idempotency-Key davranışı / react-query key'leri
/ SSE taksonomisi verbatim. Değişen tek guardrail: `nav.ts` menü DAVRANIŞI (R2-02/R2-03, GAP
belgesiyle kullanıcı onaylı); route path'leri ve deep-link'ler yaşamaya devam ediyor.

## Auth remediation dalgası — tam kayıt (#346–#364 merged, main@`6e3fab9`)

Kaynak: iki güvenlik denetimi —
`docs/spec/Entropia_Authentication_Remediation_Claude_Code_Deep_Audit.md` (AUTH-01..11 /
PROV-01..06 / DEP-01..06 / TEST-01..12) + `docs/spec/Entropia_Auth_Mode_Login_Fix_Claude_Code_Prompt.md`
(login akışı runtime AUTH_MODE'a uymuyordu). Her madde ayrı bir W-dalgasında (W2–W8) branch'lenip
PR olarak main'e merge oldu; ayrı oturumlarda kodlandı. **Migration YOK — alembic head
`0035_portfolio_rules` SABİT, `ENGINE_VERSION` SABİT.** Tüm OCC token biçimleri / Idempotency-Key /
react-query key'leri / SSE event taksonomisi verbatim korundu; sadece SSE **handshake auth'u** ve
payload'ı sıkılaştırıldı (AUTH-11, taksonomi aynı).

| Dalga / PR | Madde | Ne getirdi |
|---|---|---|
| Login-fix · #346 | Auth Mode Login | Frontend artık sunucunun **runtime AUTH_MODE**'unu izliyor (`de9c890`); dev-mode'da insan login'i sunucu tarafından reddediliyor, UI mode'a göre login/signup yüzeyini değiştiriyor |
| W2 · #347, #348 | AUTH-01..07 | (a) `AUTH_MODE=dev` altında insan login **reject** (`77a4f8e`); (b) **fail-closed runtime-auth boot gate** — geçersiz/eksik auth konfigürasyonunda süreç açılmıyor + **transport başına tek credential** (`bea75ec`) |
| W3 · #349 | AUTH-11 | **SSE handshake authenticate** edildi + payload minimize (`f330418`) — anonim SSE aboneliği kapandı; event taksonomisi (`EVENT_QUERY_KEYS`) değişmedi |
| W4 · #357 | PROV-02..05 | **Credential-aware operational Admin count** (`1cf8a26`): `identity.count_login_capable_admins` + `count_operational_admins(auth_mode)`; sign_up / bootstrap_status / role_assignment / roles operational count kullanıyor; `roles.py`'ye eksik advisory lock; bootstrap-status'a `login_capable_admin_exists` (+openapi, `Provisioning.tsx`); seed `_ensure_principal` type-conflict fail-closed; last-Admin koruması artık login-yeteneğine göre |
| W5 · #358 | DEP-04/05, TEST-11 | Explicit **session / dev-auth Compose profilleri** + worker healthcheck'leri + fail-fast test (`30100cd`) |
| W6 · #359 | TEST-06..10 | **Integration DB izolasyonu** + auth test matrisi güçlendirildi (`eacd5aa`); revoked `/me` artık 401 `SESSION_INVALID` (anonim değil) assert'i (TEST-08 düzeltmesi `1e67ce4`) |
| W7 · #360 | §9.4/9.5/9.6 | 3 auth kabul akışı için **gerçek izole Docker E2E** (`26cea44`) |
| W8-frontend · #361 | AUTH-08/09/10 | Frontend auth residuals (`4c9ce34`): cross-tab session-sync, canonical error kodları, güvenli stale-session redirect |
| DEP-03/06 · #362 | DEP-03/06 | Non-destructive **.env config audit** scripti + auth-mode-aware smoke (`8448484`) |
| W8-PROV06 · #363 | PROV-06 | **Mode-safe Compose baseline provisioning** (`d9121bd`) + audit §12 legacy `retire_dev_admin` scripti kaldırıldı |
| AUTH-09/10 residuals · #364 | AUTH-10 | Cross-tab session-sync (storage relay) kapsama testi (`46fa1c9`) — dalganın son merge'ü |

Ayrıca aynı gün merge olan **dependabot** PR'ları: #350 `upload-artifact@7`, #351 `setup-node@7`,
#352 `checkout@7` (CI actions major), #354 frontend-minor-patch grup, #355 backend-minor-patch grup,
#356 `boto3-stubs[s3]`.

**Test (CI server-truth, `main`@`6e3fab9`):** backend **1841 passed** (real-Postgres integration,
CI job "Backend — lint, type, test") · frontend vitest **577 passed / 58 dosya** · E2E job green ·
CI + E2E ikisi de `6e3fab9`'da yeşil.

**Dürüst sınırlar / DEFERRED:**
- **Dependabot #353 (`python 3.13-slim → 3.14-slim`) KAPATILDI** — proje `requires-python` `<3.14`
  pinliyor (ruff target `py312`, mypy `3.12`); 3.14'e geçiş ayrı, manuel test edilen bir dal gerektirir.
  `.github/dependabot.yml`'deki Docker `/backend` ekosisteminde **python-major ignore guard'ı henüz
  EKLENMEDİ** → guard eklenmezse dependabot 3.14 PR'ını haftaya yeniden açar. (Frontend/CI/toolchain
  major'ları için `ignore: version-update:semver-major` zaten var; Docker python için yok.)
- **Tam Python 3.14 migration** (requires-python + ruff/mypy target bump + Dockerfile) ayrı bir slice.
- Denetimin kalan maddeleri (AUTH-01..07 detay eşleme, PROV-01, DEP-01/02, TEST-01..05/12) W2–W8
  dalgalarında ele alındı ya da önceki post-V1 auth slice'larında (PR #38/#76/#84) zaten karşılanmıştı;
  audit dosyasındaki tam madde-madde durum `docs/spec/Entropia_Authentication_Remediation_Claude_Code_Deep_Audit.md`'de.

---

## V18-R3 · F-05 / M-05 — makine-okur capability matrix (UI ↔ Ready Check ↔ engine parity)

**Branch/PR:** `feat/v18-r3-f05-capability-matrix` · base `main@658db36` (F-04 = PR #381 merged doğrulandı).
**Migration YOK** — alembic head `0035_portfolio_rules` değişmedi. `readiness_issue.code` kolonu
zaten `String(64)` (native enum/CHECK değil), yeni readiness kodu migration gerektirmiyor.

### Bulgu — neden bu slice gerçekten gerekliydi

Engine'de F-07/F-09 dalgalarından kalan **dokuz** `*_is_modelled` predикat'ı vardı (sizing, leverage,
signal-strength, execution-timing, order-execution, partial-close, scaling, restrictions,
conflict-handling) ve her biri Ready Check ile **tek kaynak** paylaşıyordu. Yani "UI ↔ Ready Check ↔
engine parity" kısmen zaten sağlamdı. Ama bu predikatların hepsi **config düzeyinde** bir soruya cevap
veriyor ("bu stratejinin sizing'i modellenmiş mi?") — **enumerable değil**. Hiçbir şey onlara
"`leverage_mode`'un HANGİ DEĞERLERİ çalışır?" diye soramaz; UI de, bir drift testi de tam olarak bunu
sormak zorunda.

Bu yapısal boşluğun somut sonucu empirik olarak bulundu:

```
slippage_mode = "historical_slippage_if_available"
  → dokuz predikatın HEPSİ True (Ready Check RUN'a izin veriyor)
  → _cost_params() MODE'a hiç bakmıyor, sadece slippage_value okuyor
  → schema bu modda slippage_value'yu OPTIONAL yapıyor (validator: required iff percentage)
  → sonuç: slippage = Decimal('0')  →  SESSİZCE SIFIR-SLIPPAGE backtest
```

Yani kullanıcı "gerçekçi tarihsel slippage" seçiyor ve **sessizce iyimser** bir fill modeli alıyordu.
"Sonradan fail eden" değil — **hiç fail etmeyen, yanlış cevap veren** bir opsiyon; F-05'in hedeflediği
sınıfın en kötü hâli.

### Ne landed

- **`backend/src/entropia/domain/backtest/capabilities.py`** (YENİ, kanonik veri) — her opsiyon
  **DEĞERİ** için satır: `field_path`, `value`, `status` (`active_v1` | `future_dev`), `label`,
  `dependency` (active_v1 için ek koşul; future_dev için eksik veri serisi/model = dürüst sınır),
  `blocker_code`. **59 satır, 22 `future_dev`.** Matris saf serileştirilebilir veri; config'i okuyan
  `_FIELD_READERS` ayrı tutuldu (TS aynasına birebir dökülebilsin diye).
  Public yüzey: `capabilities_are_modelled()`, `future_dev_selections()`, `option_status()`.
- **Engine fail-closed** — `capability_ok` **`_open()`** choke-point'inde (flat entry, conflict-driven
  stack/replace ve scaling ladder'ın hepsi oradan geçer → tek kontrol, kapıda kalan yol yok).
  Flat-entry gate'e **bilinçli olarak eklenmedi**: eklenince F-10 `entry_blocked` decision-trace event'i
  hiç üretilmiyordu (`test_backtest_signal_strength` / `test_backtest_decision_trace` bunu yakaladı) —
  gözlemlenebilirlik korundu. `_blocked_reason()` içinde `capability_not_in_build` **en sonda**:
  per-domain bir predikat zaten açıklıyorsa (cross leverage, trend-adjusted…) o daha spesifik ve
  sözleşmeli trace değeri korunur; bu dal yalnız hiçbir per-domain gate'in kapsamadığı durumları
  (slippage) raporlar.
- **Result diagnostics (L4)** — `capabilities_modelled: bool` + `capability_not_in_build: [...]` +
  her seçim için `capability_not_in_build:<field_path>=<value>` warning'i.
- **Ready Check** — yeni `STRATEGY_CAPABILITY_NOT_IN_BUILD` BLOCKER, mesaj **"Not available in this
  build: …"** + remediation olarak matristen gelen `dependency`. Her ihlal eden opsiyon için ayrı issue
  (kullanıcı hepsini tek seferde görür). Dokuz per-domain blocker **korundu** — onlar matrisin ifade
  edemediği misconfiguration'ları (eksik `trigger_offset`, pozitif olmayan cap, parse edilemeyen filter
  config) yakalamaya devam ediyor.
- **`ENGINE_VERSION` → `backtest-engine-v18-capability-matrix`** — davranış değişti (historical-slippage
  artık pozisyon açmıyor), execution_key namespace'i kaymalı ki iyimser fill modeliyle üretilmiş bir
  Result idempotent olarak yeniden kullanılmasın (INF-04/INF-05).
- **UI tek kaynak** — `tools/export_capability_matrix.py` matrisi
  `frontend/src/lib/engineCapabilityMatrix.generated.ts`'e render eder (commit'li artefakt);
  `test_capability_matrix.py` dosyayı yeniden render edip **byte eşitliği** iddia eder → drift CI'da
  patlar. `SelectField` yeni `capabilityField` prop'u ile 9 select'e bağlandı: `future_dev` opsiyonlar
  **disabled** + label'da "— not available in this build" + kontrolün altında `aria-describedby` ile
  bağlı **bağımlılık açıklaması**.
- **Kayıtlı saved-value istisnası** — hâlihazırda KAYITLI bir `future_dev` değer **seçilebilir kalır**
  (disable edilirse mevcut strateji düzenlenemez hâle gelir ve form kayıtlı config'i sessizce yeniden
  yazar); not "saved but will not run — Ready Check blocks it" der. Çalıştırmayı engelleyen Ready
  Check'tir, form değil.
- **`allow_hedge` nüansı** — `exit_on_opposite_signal` ON iken opposite sinyal pozisyonu hedge dalına
  varmadan kapatır, yani değer **inert**; reader bu durumda seçim saymaz (tam olarak
  `conflict_handling_is_modelled`'ın kuralı). OFF iken future_dev → bloklanır.

### Testler

- **`backend/tests/unit/test_capability_matrix.py`** (YENİ) — üç yönlü kanıt:
  1. **Exhaustiveness**: matrisin enumere ettiği her alan için satırlar, saved schema'nın `Literal`
     değerleriyle **tam küme eşitliği**. `config.py`'ye yeni bir opsiyon eklenirse sınıflandırılmadan
     UI'ya ulaşamaz — bu testin asıl anti-drift değeri burada.
  2. **Fail-closed parity**: 22 `future_dev` satırının **her biri** için gerçek config → Ready Check
     `STRATEGY_CAPABILITY_NOT_IN_BUILD` **ve** engine `trades == []` + doğru L4 warning. Proof-overlay
     eksikse `test_every_future_dev_option_has_a_proof_overlay` patlar (satır kaçamaz).
  3. **Executability**: all-`active_v1` baseline gerçekten **trade açar** (her şeyi bloklayan bir
     matrisin fail-closed testlerini geçip ürünü kullanılamaz yapması engellenir) + inert `allow_hedge`
     ve 100% close'un aftermath'i hâlâ çalışır.
  \+ historical-slippage için ayrı regression pin (dokuz predikatın onu kapsamadığını da iddia eder).
- **`frontend/src/test/engineCapabilityMatrix.test.tsx`** (YENİ, 10 test) — disabled + not metni +
  `aria-describedby` bağı, kayıtlı-değer istisnası, matris-dışı select'te not YOK.

### İkinci bir sessiz boşluk var mı? — tam Literal sweep

Slippage'ı bulduktan sonra `config.py`'deki **çok-değerli tüm `Literal` alanları** (39 adet)
enumere edilip her biri için "bunu ya matris ya bir per-domain predikat ya da engine'de açık bir
branch gerçekten karşılıyor mu?" sorusu tek tek yanıtlandı:

- **13 alan** matriste sınıflandırıldı.
- Kalanlar per-domain predikat / engine branch ile karşılanıyor: `position_sizing.method` +
  `order_config.type` + `StopOrderDetails.activation_rule` (`sizing_is_modelled` /
  `order_execution_is_modelled` / `_stop_trigger_is_modelled` — değer düzeyinde satır YANLIŞ olurdu,
  çünkü geçerlilik alt-config'e bağlı) · `LimitOrderDetails.unfilled_policy` (4/4 branch) ·
  `LimitOrderDetails.validity` (6/6 `_VALIDITY_BARS`) · `intrabar_policy.tick_policy`
  (`tick_data_required` + `TICK_DATA_UNAVAILABLE`) · `stop_exit_conflict` (4/4) ·
  `ScalingLogic.add_size` (3/3: `fixed_amount` / `percent_of_initial` / else `percent_of_current`) ·
  `stop_trigger_requirement` (2/2) · `RestrictionsFilters.rule` (any/all) ·
  `same_direction_stacking` (3 açık branch + `allow_stacking` = kasıtlı fall-through "fold-in add") ·
  Indicator/Condition block alanları (plan resolution + `STRATEGY_INDICATOR_UNRESOLVED` /
  `STRATEGY_LOGIC_STOP_UNRESOLVED`) · direction alanları (`_direction_flags`).
- **Tek istisna, kayıtlı dürüst sınır:** `overlapping_signal_policy` hiç branch edilmiyor (yalnız
  diagnostics'e yazılıyor). Engine'in kendi docstring'indeki gerekçe geçerli: V1'de değerlendirme
  penceresi başına EN FAZLA bir agregat sinyal üretiliyor (signal-block kuralı + deterministik
  long-wins tie-break aynı-pencere eşzamanlılığını policy devreye girmeden çözüyor), yani dört değer
  **inşaat gereği** aynı davranışı paylaşıyor. Slippage tipi sessiz yanlış-modelleme DEĞİL — kararı
  olmayan bir alan. Bu nedenle bilinçli olarak matrise alınmadı.

**Sonuç:** `slippage_mode` gerçekten tek gate'lenmemiş alandı; ikinci bir aynı sınıf boşluk bulunamadı.

### Dürüst sınırlar

- Matris yalnızca **executability'si farklılaşan** alanları enumere eder. Her değeri aynı şekilde
  çalışan alanlar (order validity pencereleri, unfilled policy'ler, slippage DEĞERİ, stop-exit collision
  çözümü, overlapping-signal ve same-direction-stacking policy'leri) bilinçli olarak dışarıda — hepsini
  listelemek drift yüzeyi ekler, UI veya Ready Check'in alacağı tek bir karar eklemez.
- `_SCHEMA_FIELDS` (exhaustiveness testinin alan→model kaydı) **elle** tutulur: matrise yeni bir
  *alan* eklenirse oraya da eklenmeli. Yeni bir *değer* otomatik yakalanır.
- Bu slice R3 mühendislik backlog'unu kapatır; **F-07 (raw-id sweep) ve F-09 (README honesty)** ayrı
  slice'lar olarak açık.



## K-07 devamı · Market/Research upload — fail-closed source-file type gate (PR #388)

**Sorun.** K-07'nin Trade Log / Trading Signal'da düzelttiği fail-open dosya-tipi kapısı iki yerde daha
duruyordu (2026-07-27'de ampirik doğrulandı):

- `application/commands/market_data.py::_validate_upload_file_type`
- `application/commands/research_data.py::_validate_upload_file_type`

İkisi de `if name and not name.endswith(_ALLOWED_UPLOAD_EXTENSIONS):` deseniydi. `original_filename`
`None`/boş olduğunda koşul kısa devre yapıyor, sunucu tarafı tip kontrolü **tamamen atlanıyor** ve
binary dahil her payload kabul ediliyordu. Doğrudan komut çağıranlar (agent yüzeyi) route seviyesindeki
dosya adı kontrolünden geçmediği için başka hiçbir katman yakalamıyordu.
`domain/create_package/baseline.py::is_allowed_baseline_file` zaten fail-closed — dokunulmadı.

**Çözüm.** Her iki komut da ortak K-07 kapısına devredildi:
`domain/importing/source_file.py::assert_supported_source_file(original_filename, content, *, error=..., allowed_extensions=...)`.
Kapı eksik/boş filename'i doğrudan reddeder ve uzantı iddiasını içerik sniff'i (binary imza / NUL byte /
UTF-8 decode) ile destekler. Merge sonrası `main`'de **dört** komut yüzeyi de tek kapıyı çağırıyor:
`trade_log.py` · `trading_signal.py` · `market_data.py` · `research_data.py`.

**Hata kodları surface bazında korundu** — her sayfanın taksonomisi kendi yüzeyi için otoriter:

| Yüzey | Hata sınıfı | Kod | Doc |
|---|---|---|---|
| Trade Log | `UnsupportedSourceFileTypeError` | `UNSUPPORTED_SOURCE_FILE_TYPE` | 05 §12.1 |
| Trading Signal | `FileTypeNotAllowedError` | `FILE_TYPE_NOT_ALLOWED` | 04 §11 |
| Market Data | `MarketDataFileTypeNotAllowedError` | `MARKET_DATA_FILE_TYPE_NOT_ALLOWED` | 11 |
| Research Data | `ResearchDataFileTypeNotAllowedError` | `RESEARCH_DATA_FILE_TYPE_NOT_ALLOWED` | 12 |

`_ALLOWED_UPLOAD_EXTENSIONS` sırası `(".csv", ".txt")` bırakıldı ki red mesajı "CSV/TXT" kalsın
(Trade Log / Signal tarafında "TXT/CSV").

**Testler.** Her yüzey için unit (yeni `(filename, content)` imzası + `test_missing_filename_fails_closed`
parametrize `None`/`""`/`"   "` + `.csv` adlı zip blob) ve integration
(`test_upload_file_type_gate_is_fail_closed` — 5 red vakası, kod + `details[0]["field"]` assert'i,
"hiçbiri object storage'a veya raw-asset evidence tablosuna ulaşmadı", ardından gerçek `.csv`'nin hâlâ
yüklendiği). Migration YOK; şema, route, OCC ve Idempotency yüzeyi değişmedi.

### Dürüst sınırlar

- Kapı **komut seviyesinde**; route seviyesindeki F-03 multipart gate'i ayrı katman olarak duruyor.
- İçerik sniff'i heuristiktir — geçerli UTF-8 metin olan ama CSV olmayan bir payload bu kapıdan geçer;
  asıl parse doğrulaması aşağıdaki ingest/parse adımının işi.
- Codemap tazelenmedi: yeni endpoint / tablo / sayfa / job yok, yalnızca mevcut komutların iç
  doğrulaması değişti.
- **Ortam tuzağı (tekrar yaşamamak için):** yerel integration paketi paylaşılan `entropia_test` DB'sinde
  her test `drop_all`/`create_all` yapar; paralel worktree oturumları birbirini ezip dalgalı hatalar
  üretir — `TEST_DATABASE_URL` ile izole DB kullan. `uv run pytest` venv'i temel bağımlılıklara
  sıfırlayabiliyor (`uv sync --extra dev` gerekir). `tests/acceptance` ve `tests/deterministic` boş
  dizinler → pytest exit 5 normaldir.

---

## K-03 · Engine funding sırası — spec adım 2'ye taşındı (PR #398)

**Sorun (ampirik doğrulama ile).** `docs/spec/15_..._RUN_ve_Backtest_Results_..._v1_1.md` §9.3 sekiz
adımlık, sürümlenmiş ve deterministik bir bar sırası pinliyor ve **funding/fee/carry = ADIM 2**.
Motor ikisini de tutmuyordu:

- `domain/backtest/engine.py` docstring'i **3 adımlık** bir sıra ilan ediyordu (rolling look-back
  window → protection/stop/exit → entry) ve **funding bu üçünün hiçbirinde yoktu**;
- uygulama funding'i bar döngüsünün **SONUNDA** çalıştırıyordu — `entry_signal` değerlendirmesinden,
  pending/resting fill'lerden, restriction/scaling merdiveninden ve exposure reject yolundan sonra.

`equity` hem girişi boyutlandıran (`_position_size`) hem de allocation sleeve / exposure cap'lerini
sınırlayan (`_sleeve_capital`) girdidir. Carry'yi en sona bırakmak bu yüzden **her** girişi ve **her**
scale katmanını carry'si ödenmemiş equity ile boyutlandırıyordu — perp funding altında sistematik
olarak daha büyük pozisyona doğru **tek yönlü kümülatif** bir sapma ve bir bar geç bağlanan
`max_total_exposure`. Yerleşim ayrıca, kaydın available olduğu bar pozisyonu kapatıyorsa charge'ı
**sessizce düşürüyordu**: blok çalıştığında defter zaten flat'ti ve kayıt ücretlendirilmeden tüketiliyordu.

**Çözüm.** Funding kanonik **adım 2**'ye, bar'ın en başına taşındı — o bar'ın her fill'inden,
stop'undan, exposure kontrolünden, girişinden ve scale katmanından önce. Docstring tam 8 adımlık §9.3
sırasıyla değiştirildi; döngü içi `# (n)` işaretleri kanonik adım numaralarını taşıyacak şekilde
yeniden numaralandırıldı. **Adım 1 açıkça K-02'nin `is_eligible_for_decision` kapısına bağlandı**
(PR #393). Kod sırasının spec sırasına eşit olamadığı iki yer örtülmek yerine **belgelendi**:

- adım 5 ve 6 iç içe geçer, çünkü sleeve / `max_total_exposure` / size cap'leri tek bir bağımsız blok
  yerine bir boyutun hesaplandığı noktada bağlanır;
- adım 3d (bar'ın CLOSE'una ertelenmiş fill) yapısı gereği adım 4–6'dan sonra çözülür.

**Perp konvansiyonunun iki yönlü sonucu** ("funding yalnızca fiilen tutulan aralık için ödenir"):
bir bar'ın **BAŞINDA** açık olan pozisyon, bar daha sonra onu kapatsa bile o bar'da available olan
kaydı **öder** (eskiden düşüyordu); o bar'da **AÇILAN** pozisyon ise o bar'ın kaydını **ödemez**
(eskiden ödüyordu). Bir charge tutulan pozisyon, taze bir giriş ise flat defter gerektirdiğinden
**bir charge ile ilk giriş asla aynı bara düşemez** — testlerde açıkça yazılı bir sınır.

**ENGINE_VERSION** → `backtest-engine-v18-funding-step-order` (K-04'ün `-full-pinning` bump'ının
üstüne; her iki yorum bloğu da manifest.py'de kümülatif olarak durur). **Migration YOK.**

**Ölçülen sapma (integration fixture'ına yazıldı).**

```
bar 21  long @102, 200.00000000 birim (10000 * %2 risk / 1.0 stop point)   -- her iki sıra
bar 22  funding available (rate 0.001); %1 stop da bu barda tripliyor
          YENİ: önce charge -> 20400.00 * 0.001 = 20.40 işlenir, SONRA stop kapatır
          ESKİ: en son charge -> defter zaten flat, charge DÜŞTÜ
bar 29  ikinci long @120, bar 22'den kalan equity ile boyutlanır
          YENİ: (10000 - 204.00 - 20.40) * %2 = 195.51200000 birim
          ESKİ: (10000 - 204.00)         * %2 = 195.92000000 birim
final   YENİ final_equity 9775.60    ESKİ final_equity 9796.00
```

Aynı-bar exposure semptomu (scaling unit testi, %77 sleeve, rate 0.03): funding off →
`scale_layer_added` (`new_size 75.00000000`); funding on → `scale_layer_rejected`
(`reason sleeve_capacity`, `cap 2482.19`). Eski sırada charge merdivenden sonra düştüğü için katman
her hâlükârda kabul ediliyordu — geç bağlanan `max_total_exposure`'ın tek satırlık kanıtı.

**Testler.** `tests/unit/test_backtest_funding_step_order.py` (6 test): düşen exit-bar charge'ı ·
`funding_charge`'ın kendi barındaki her olaydan önce gelmesi · `risk_based_sizing` altında
before/after giriş-boyutu sapması · aynı-bar funding → scaling sleeve-cap flip'i · o barda açılan
pozisyonun charge ödememesi · batch-size determinizmi. **6'nın 5'i düzeltme öncesi motorda kırılıyor**
— `engine.py` stash'lenip yeniden koşularak ampirik doğrulandı; altıncısı (batch determinizmi) tasarım
gereği sıradan bağımsız. `tests/integration/test_backtest_funding_step_order.py` (3 test): DB'de
seed'lenmiş Approved funding Research revision → `resolve_funding_schedule` → `run_engine` zinciri,
eski/yeni sayılar yan yana kayıtlı, artı `execution_key` / `manifest_hash` namespace kayması.

**Doğrulama.** ruff · `ruff format --check` (601 dosya) · `mypy src` (352 dosya) temiz; tam backend
suite **exit 0, hiç F/E yok**. **Migration ve yeni `create_*` komutu olmadığı için** alembic
up/down/up proof'u ve L1 FK insert-order proof'u bu slice'a uygulanmaz.

**Dürüst sınırlar.** Bir funding oranının nasıl **çözüldüğü** (provenance gate, available-time policy,
instrument mapping) değişmedi — o K-02/F-11 ve dokunulmadı. Perp funding dışındaki fee ve carry V1
motorunun kapsamı dışında kalmaya devam ediyor; adım 2 onların bağlanacağı yerdir.

**Sürüm uyumu (PR açıklamasına da yazıldı).** Mevcut Result'lar kendi pinli `engine_version`'ları
altında **geçerli kalır** — hiçbiri yeniden yazılmaz, silinmez veya yeniden etiketlenmez. Ancak eski
sıra altında üretilmiş funding'li bir Result, bu PR sonrası üretilenle **KARŞILAŞTIRILAMAZ**: sayılar
yapısal olarak farklıdır ve aradaki fark stratejinin değil motor sürümünün artefaktıdır.
Karşılaştırmak için eski kompozisyonu yeni motorda yeniden RUN et.

**Ortam tuzağı (K-07'nin notunu doğrular).** Bu slice'ta tam suite üç kez baştan koşuldu, çünkü
paralel bir worktree (`entropia-o02-error-envelope-*`) aynı paylaşılan `entropia_test` DB'sine karşı
kendi integration paketini koşuyordu; conftest her testte `drop_all`/`create_all` yaptığından iki koşu
birbirinin şemasını siliyor ve dalgalı, ilgisiz hatalar üretiyor. **`TEST_DATABASE_URL` ile worktree'ye
özel izole DB kullan** (`entropia_k03_test`) — sonrasında suite ilk denemede yeşil.


## O-03 · Hata kodu taksonomisi — 18 spec kodu adjudicated, 2 ölü sınıf silindi (PR #407)

**Denetim iddiası.** ÖRÜNTÜ-1: "25+ spec-kanonik hata kodu yok veya farklı isimde + 4 ölü tanım",
ayrıca bir TIMEZONE ad çakışması. Her madde **tek tek ampirik doğrulandı** — CLAUDE.md'nin
"code-review bulgularını düzeltmeden önce ampirik doğrula (çoğu yanlıştır)" kuralı bu slice'ta
üç kez işe yaradı.

> **Bu bölüm ikinci kez yazıldı.** İlk hali PR #408 ile merge edildi ama `aa75fca` çakışma
> çözümü 144 satırın tamamını düşürdü; merge commit'i (`e15377d`) var, içeriği yoktu. Aynı
> zamanda iki satırı da bayatlamıştı (aşağıda §"Review sırasında kayan zemin").

### Doğrulanan yarı: 19/19 kod gerçekten 0 hit

Listelenen 19 kodun hiçbiri tarama anında `backend/src` veya `backend/tests` içinde geçmiyordu
(her biri ayrı grep).

### Çürütülen yarı: davranışlar zaten uygulanmış — farklı adla

Kodların **yokluğu** doğru, ama **davranışın yokluğu** yanlış. Her biri için fail-closed bir yol
zaten mevcut; sapma yalnız adlandırmada. Bu yüzden **hiçbir kod adı değiştirilmedi** — sapma
burada adjudicate edildi (K-07 içtihadı: "Kodlar aynı kusuru anlatır; her sayfanın kendi
§-taksonomisi otoritedir"). Yeniden adlandırma ayrıca zararlı olurdu: bu kodların bir kısmı
kabul edilmiş import çıktısında ve tarihsel satırlarda saklı.

| Spec kodu | Doc § | Kodda yaşayan karşılık | Kanıt |
|---|---|---|---|
| `PACKAGE_TIMING_INCOMPATIBLE` | 08 §1543 | `TICK_DATA_UNAVAILABLE` | `commands/readiness_check.py:326` |
| `PACKAGE_TYPE_INVALID` | 08 §681/1258/1524 | `CLIENT_LEGACY_TYPE_REJECTED` + `CATALOG_FILTER_INVALID` | `commands/esp.py`, 3+3 raise |
| `PACKAGE_DEPENDENCY_UNRESOLVED` | 08 §1270 | `DEPENDENCY_UNRESOLVED` | yalnız `PACKAGE_` öneki farkı |
| `PACKAGE_EDIT_FORBIDDEN` | 08 §1282 | `ACCESS_DENIED` | `domain/identity/policy.py:140` |
| `OWNER_REQUIRED` | 01/03/04/06/08/13 | `ACCESS_DENIED` | `ensure_can_edit` — "You can only edit resources you own." |
| `TRASH_ADMIN_ONLY` | 08 §1282 | `TRASH_ACCESS_FORBIDDEN` | `domain/identity/policy.py:51` |
| `INVALID_FILTER_VALUE` | 09 §794 | `CATALOG_FILTER_INVALID` / `LOG_FILTER_INVALID` | 3+3 raise |
| `POLICY_DENIED` | 10 §884 | `ACCESS_DENIED` | rol kapısı sorgu yüzeyinde |
| `RESOLVER_TEST_VECTOR_FAILED` | 09 §1008 | check adı `test_vectors` → `RESOLVER_VALIDATION_REQUIRED` | `domain/esp/validation.py:185` |
| `RESOLVER_TIMING_RISK_BLOCKED` | 09 §1013 | check adı `timing_integrity` → aynı | `domain/esp/validation.py:214` |
| `UNSAVED_MAINBOARD_DRAFT` | 01 §1119/1238 | revision'sız draft Ready Check/RUN'a giremez (AT-01) | `commands/strategy_draft.py:110` |
| `OBJECT_EDIT_FORBIDDEN` | 01 §1620 | `ACCESS_DENIED` | **spec "ACCESS_DENIED / OBJECT_EDIT_FORBIDDEN" yazıyor** |
| ~~`INTRABAR_DATA_UNAVAILABLE`~~ | 04 §604 | `TICK_DATA_UNAVAILABLE` | **SUPERSEDED → §"Sonradan canonical olan dört satır"** |
| ~~`OHLCV_CONTEXT_REQUIRED`~~ | 04 §599 | `OHLCV_POLICY_CONFLICT` | **SUPERSEDED → §"Sonradan canonical olan dört satır"** |
| `MARKET_DATA_INSTRUMENT_MISMATCH` | 02 §2380/2861 | `RunFailureCode.INSTRUMENT_MISMATCH` | `jobs/backtest_engine.py:503`, fail-closed (F-05) |
| `MISSING_EMBEDDED_DEPENDENCY` | 07 §1129/1422 | `PRECHECK_BLOCKED` | **spec §1422 alternatifi yazıyor** |
| ~~`INVALID_ITEM_KIND`~~ | 03 §838/922 | `MAINBOARD_ITEM_KIND_MISMATCH` | **SUPERSEDED → §"Sonradan canonical olan dört satır"** |
| ~~`UPLOAD_JOB_FAILED`~~ | 21 §942 | `MANUAL_PARSE_FAILED` | **SUPERSEDED → §"Sonradan canonical olan dört satır"** |

İki satırda spec **kendi alternatifini zaten yazıyor** (01 §1620, 07 §1422) — oralarda sapma bile
yok; denetim spec'in ilk seçeneğini tek geçerli ad sanmış.

### 19. kod: `PACKAGE_DEPENDENCY_CYCLE` — adjudicate DEĞİL, gerçekten eklendi

Tarama sırasında bu da "`DEPENDENCY_UNRESOLVED` kapsıyor, doc 09 §1018 alternatifi yazıyor"
diye adjudicate edilmişti. **O-10 (PR #402) bu slice review'dayken canonical sınıfı ekledi**
(`shared/errors.py:576`, `PackageDependencyCycle`, kod `PACKAGE_DEPENDENCY_CYCLE`, doc 08 §10/§14).
Artık spec adıyla mevcut; adjudication satırı geçersizdir ve bu kayıt onun yerini alır.

### Sonradan canonical olan dört satır (2026-07-29 tazelemesi)

`PACKAGE_DEPENDENCY_CYCLE` tek istisna değildi. **Yukarıdaki tablo yazıldığı anda doğruydu**;
o günden bu yana dört slice daha, adjudicate edilmiş dört kodu **spec adıyla** implement etti.
Dördü de O-03'ün İKİ PR'ından (kod #407 · doc #413, ikisi de 2026-07-28 sabahı) **sonra** indi —
yani tablo bayatladı, yanlış yazılmadı. Bu satırlar artık geçersizdir; adjudication DEĞİL,
**canonical implementasyon** geçerlidir:

| Spec kodu | Eski adjudication | Şimdi canonical | İndiren |
|---|---|---|---|
| `INTRABAR_DATA_UNAVAILABLE` | `TICK_DATA_UNAVAILABLE` | `ReadinessIssueCode.INTRABAR_DATA_UNAVAILABLE` (`domain/readiness/enums.py:151`), emit `commands/readiness_check.py:510` | `8a7a707` K-08 (2026-07-28 19:25) |
| `OHLCV_CONTEXT_REQUIRED` | `OHLCV_POLICY_CONFLICT` | `ReadinessIssueCode.OHLCV_CONTEXT_REQUIRED` (`domain/readiness/enums.py:157`), emit `domain/readiness/validators.py:1071` | `8a7a707` K-08 (aynı commit) |
| `INVALID_ITEM_KIND` | `MAINBOARD_ITEM_KIND_MISMATCH` | `InvalidItemKindError` / `INVALID_ITEM_KIND` (`shared/errors.py:967-972`), `domain/mainboard/item_kind.py:43` | `0b73b06` O-27 (PR #450) |
| `UPLOAD_JOB_FAILED` | `MANUAL_PARSE_FAILED` | `ManualUploadJobFailedError` / `UPLOAD_JOB_FAILED` (`shared/errors.py:2029-2045`), raise `commands/manual.py:126`, `:141` | `c8288b3` I15B-SL6 (PR #455) |

Eski karşılıklar **silinmedi** — `TICK_DATA_UNAVAILABLE`, `OHLCV_POLICY_CONFLICT`,
`MAINBOARD_ITEM_KIND_MISMATCH`, `MANUAL_PARSE_FAILED` hepsi hâlâ kendi ayrı kusurlarını
anlatıyor. Değişen tek şey: spec kodu artık **kendi adıyla da** mevcut, dolayısıyla
"bu kod yok, şu kod kapsıyor" cümlesi doğru değil.

> **Bu bölümün kalıcı dersi budur.** O-03 bir kez bayatladı (#408 boş merge), sonra
> review sırasında üç kez kaydı, şimdi dördüncü kez tazelendi. Bir adjudication tablosu
> **tarihsel bir kayıttır, canlı bir sözleşme değil** — ağaca sorulmadan alıntılanamaz.
> Ölü-sınıf tarafında bunu `tests/unit/test_error_taxonomy_no_dead_definitions.py`
> otomatikleştiriyor (küme her koşuda ağaçtan yeniden hesaplanıyor); **adjudication
> satırlarının böyle bir bekçisi yok** ve bu bilinçli bir açık: "spec kodu sonradan
> canonical oldu mu" sorusu ancak spec §-numarasıyla eşleşen bir kaynak listesi
> tutularak makineleştirilebilir, o liste de bugün yok.

Tablodaki satır numaraları (`errors.py:576`, `policy.py:140`, …) **tarama anına aittir**
ve rutin olarak kayar; bir satırı doğrularken numaraya değil, sembol adına grep at.

### TIMEZONE — "tek ada indir" reddedildi

- `TIMEZONE_REQUIRED` (`shared/errors.py:156`) — Market Data yüklemesinde timezone **yok**;
  HTTP error envelope kodu.
- `TIMEZONE_INVALID` (`domain/trade_log/records.py:50`) — Trade Log **whole-file blocker** kodu
  (TL-07); timezone **var ama geçersiz**; envelope değil, blocker taksonomisi.

Birleştirmek iki ayrı kusuru ("yok" vs "geçersiz") ve iki ayrı yüzeyi çökertirdi. **Gerçek sapma
tek karakterlik ve tek yerde:** TL blocker'ı `TIMEZONE_INVALID`, doc 05 §1179 ise
`TIME_ZONE_INVALID` diyor. Yeniden adlandırılmadı — TL blocker kodları kalıcı `trade_log_records`
satırlarında saklı; ad değişikliği geçmiş kayıtları okunamaz kılardı.

### Çürütülen iki "ölü tanım" iddiası

- **`TICK_DATA_UNAVAILABLE` ölü DEĞİL** — iki emit yeri (`readiness_check.py:326`,
  `backtest_run.py:409`), `test_readiness_tick_data.py`'de beş assertion.
- **`MetricAvailability.NOT_COMPUTED` emit EDİLİYOR** — `_metric_card_not_computed`,
  `queries/metric_profile.py:111`'den çağrılıyor.

### Silinen iki ölü sınıf (PR #407)

| Silinen | Neden ölü | Spec durumu |
|---|---|---|
| `PrecheckAlreadyRunning` / `PRECHECK_ALREADY_RUNNING` | 0 raise | doc 07 §897 "idempotent reuse **veya** bu kod" diyor; kod idempotent dalı seçmiş |
| `DeletePolicyBlocked` / `DELETE_POLICY_BLOCKED` | 0 raise | doc 09 §836/§896 gerektiriyor, ama `commands/deletion.py`'de package entity dalı yok — koruduğu özellik hiç yazılmamış |

Denetim `PrecheckAlreadyRunning`'i `errors.py:517-521` göstermişti; gerçek konum `:590` idi.

### Review sırasında kayan zemin — bu slice'ın asıl dersi

Bu sweep'te **üç bulgu, ben doğrulayıp raporladıktan sonra paralel slice'lar main'e indiği için
geçersizleşti**:

| Bulgu | Ne oldu | Sonuç |
|---|---|---|
| `PACKAGE_DEPENDENCY_CYCLE` "adjudicated" | O-10 (#402) canonical sınıfı ekledi | satır geçersiz, yukarıda düzeltildi |
| `DeletePolicyBlocked` silinecek | O-02 (#400) sınıfa `category` alanı ekledi | rebase çakışması; silme yine doğruydu |
| `PublicationState.REMOVED` silinecek | **O-15 (#409) purge-time redaction'ı implement etti** | silme YANLIŞ hale geldi; üye geri kondu |

`PublicationState.REMOVED` tarama anında gerçekten ölüydü ve docstring'inin vaat ettiği redaction
doc 21'de tanımlı değildi. #409 tam o redaction'ı ekledi (`repositories/manual.py:274,276`), yani
vaat gerçek oldu ve silme mypy'ı kırdı — CI yakaladı. **Üye korunuyor; `enums.py` main ile
byte-identical, veri modeline dokunulmadı, migration yok.**

Kalıcı önlem: `tests/unit/test_error_taxonomy_no_dead_definitions.py` ölü kümeyi **her koşuda
ağaçtan yeniden hesaplıyor**, "en son bakıldığında yazılmış" bir listeye güvenmiyor.

### Denetimin kaçırdığı: 5 ölü sınıf daha

219 sınıf tarandığında **7'si** `src/` içinde hiç referans edilmiyordu; denetim 1'ini bulmuştu.
2'si silindi, kalan **5'i kayıtlı borç** olarak `KNOWN_UNRAISED`'te pinlendi: `RoleContextStaleError`,
`ValidationAlreadyRunning`, `ServiceUnavailableError`, `ArtifactNotAvailableError`,
`HypothesisArtifactNotFoundError`. **Yetkilendirilmiş kapsam dışıydı**, bilerek dokunulmadı.
Test bir ratchet'tir: altıncı ölü sınıf eklenirse kırılır, listedekilerden biri fırlatılmaya
başlarsa da kırılır. Sayı yalnız aşağı iner.

> **SÜPERSEDE — bu paragraf tarihsel kayıttır, canlı borç listesi DEĞİL.** Beşi de listeden
> düştü: `ValidationAlreadyRunning` S-L3'te gerçek bir raise yolu kazandı, kalan dördü
> **O-03R**'de adjudicate edilip silindi. `KNOWN_UNRAISED` bugün **boş**. Kararların spec
> §referansları ve reddedilen (A) alternatifleri: §"O-03R · Kalan 4 ölü error sınıfı kapatıldı".

### Doğrulama

`ruff check` · `ruff format --check` (619 dosya) · `mypy src` (356 dosya) temiz; `tests/unit`
(ratchet dahil) + `acceptance` + `contract` + `deterministic` exit 0. Ölü küme her rebase'den
sonra yeniden hesaplandı. PR #407 CI'ı **6/6 yeşil** (backend, frontend, iki E2E, A11Y, Docker).
**Migration YOK**, alembic head değişmedi.

### Dürüst sınırlar

- **`docs/audit/audit_report.md` repoda yok** ve git geçmişine hiç eklenmemiş; O-numaralı bulgular
  checked-in olmayan harici bir belgeden geliyor. Doğrulama, açıkça sayılan **19** kodla sınırlıdır
  — "25+" iddiasının kalanı görülmedi ve bu kayıt onlar hakkında hiçbir şey söylemez.
- Tarama `backend/src` + `backend/tests` kapsamındadır; frontend yalnız silinen tanımlar için
  kontrol edildi (sıfır referans).
- **Lokal tam suite tek koşuda tamamlanamadı.** Paket paket yeşil; `tests/integration` 55 test
  temiz geçtikten sonra kesildi. Üç tam-suite denemesi de **test hatasıyla değil, lokal ortam
  tarafından** öldürüldü (arka plan süreçleri bu makinede Bash çağrısını aşamıyor). CLAUDE.md
  lokal-verify kuralından bilinçli ve açıklanmış sapmadır; integration'ın otoritesi #407 CI'ıdır.
- Adjudicate edilen kodlar için **yeni integration testi yazılmadı** — yeni kod eklenmediği için
  bağlanacak yeni davranış yok; her satırın karşılığı kendi mevcut testine sahip.


---

## O-17 · Restore conflict resolution — typed seçenek kümesi + ayrı preflight okuma yolu (branch `feat/o17-restore-conflict-resolution`)

### Kusur (ampirik doğrulandı, sabit değil)

`routes/trash.py::RestoreRequest` **yalnız** `expected_head_revision_id` taşıyordu; doc 20 §5'in
`resolution` alanı ve preflight'ın döndürmesi gereken typed seçenek kümesi **hiç yoktu**.
`commands/deletion.py` içinde `RestoreConflictError()` **altı ayrı yerde alternatifsiz** atılıyordu.
Sonuç: Admin 409 alıyor, doc 20 §8.2'nin "Admin yalnız domain adapter'ın sunduğu typed resolution'ı
seçebilir" kuralının seçecek hiçbir şeyi olmuyor, doc 20 §6 "Restore needs attention" paneli de
interpolate edecek `{conflict_summary}` bulamıyordu.

### Ne landed

**Tek katalog — `domain/trash/restore.py` (YENİ).** Conflict taksonomisi + typed resolution kataloğu
tek yerde: `RestoreConflictKind` (`head_pointer_moved`, `target_missing`), `RestoreResolution`
(`restore_at_current_head`), `_RESOLUTIONS` tablosu, `conflict_summary()`, `resolution_options()`,
`supports_resolution()`, `parse_resolution()`, `restore_conflict()`. **Hem** komut raise site'ları
**hem** okuma yolu bu tek tablodan cevap veriyor — iki yerde ayrışamaz.

**409 artık alternatiflerini taşıyor.** `restore_conflict()` fabrikası: `message` = doc 20 §6'nın
`{conflict_summary}`'si (iki head'i de adlandırır), `details` = resolution başına bir satır
(`conflict_kind`/`resolution`/`label`/`description`), `remediation` = insan adımı, `scope_type`/
`scope_id` pinlenir. Altı bare `RestoreConflictError()` bu fabrikaya bağlandı.
**Boş `details` bir eksiklik değil, gerçek cevap:** `target_missing` için dürüst bir onarım yok →
komut başlatılamaz, kök `soft_deleted` kalır (doc 20 §8.2).

**Ayrı okuma yolu.** `GET /trash-entries/{id}/restore-preflight` →
`queries/trash.py::get_restore_preflight`. Salt-okuma: kilit yok, mutation yok, OCC token yok,
Idempotency-Key yok. `outcome` ∈ `allow` | `conflict` | `blocked`; `blocked_reason` komutun
atacağı hata kodunu taşır; `expected_head_revision_id` echo edilir ki retry **aynı** sürümle
gitsin. Preflight **advisory**, asla yetkilendirme değil — komut her kontrolü kendi tx'inde
yeniden koşar.

**422, sessiz onarım değil.** `UnsupportedRestoreResolutionError`
(`UNSUPPORTED_RESTORE_RESOLUTION`, `field_path="resolution"`). `parse_resolution()` komutun
**en başında**, herhangi bir DB işinden önce koşar; bilinmeyen token → 422, `details` desteklenen
kümeyi adlandırır. Boş string de reddedilir (fail-closed). Pydantic enum'u **bilerek**
kullanılmadı: coercion hatası framework'ün jenerik gövdesini üretir, canonical zarfı değil.

**Resolution master key değil.** `supports_resolution()` yalnız kendi conflict kind'ını açar —
`restore_at_current_head` gönderip `target_missing`'i geçmek mümkün değil. Uygulanan resolution
audit metadata'sına yazılır (`{"restore_resolution": "restore_at_current_head"}`) ve dönüş
projeksiyonunda `applied_resolution` olarak görünür; temiz restore'da `null` kalır — handler'ın
sessizce onarmadığının kaydı.

**O-13 uyumu:** `resolution` idempotency fingerprint'ine **girdi olarak** eklendi (komutun kendi
değiştirdiği durum değil) — aynı key + farklı resolution farklı bir karardır, replay etmez.

**Frontend.** `lib/trash.ts`: `RestoreResolutionOption`/`RestorePreflight` tipleri,
`useRestorePreflight` (key `["trash","restore-preflight",id]`, staleTime/gcTime 0),
`restoreConflictOptions()` (409 zarfını savunmacı parse), restore mutation'ı opsiyonel
`resolution` alır — **yalnız seçildiğinde** gönderilir, ilk denemede alan hiç yok.
`pages/Trash.tsx`: `RestoreConflictPanel` doc 20 §6 metnini **VERBATIM** render eder
("Restore needs attention" + "This object cannot be restored automatically because:
{conflict_summary}. Review the available domain-specific resolution options. No change has been
applied; the object remains in Trash."). Seçenekler radio grubu; **resolution seçilmeden Retry
disabled** (doc 20 §8.2 "command başlatılamaz"); seçenek yoksa Retry düğmesi hiç render edilmez;
"Re-check" canonical preflight'ı yeniden okur (doc 20 §8.2 "Admin canonical detaili yeniler");
conflict temizlendiyse panel bunu söyler ve düz retry'a izin verir. Yalnız RESTORE_CONFLICT paneli
açar — diğer her hata eskisi gibi canonical zarfı verbatim gösterir.

### Testler

`tests/integration/test_trash_restore_conflict.py` (YENİ, 10 test): conflict typed seçeneklerini
taşır + kök `soft_deleted` kalır · preflight mutate etmeden aynı seçenekleri raporlar · temiz
entry'de `allow` · preflight Admin-only · desteklenen resolution açar ve audit'e yazar · temiz
restore `applied_resolution=None` bırakır · bilinmeyen resolution 422 · boş string 422 ·
`target_missing` sıfır seçenek sunar · başka conflict'in resolution'ı açmaz.
`src/test/trash.test.tsx` (+6): §6 metni verbatim · resolution seçilmeden komut başlatılamaz ·
retry aynı `expected_head_revision_id` + seçilen resolution ile gider · ilk denemede `resolution`
alanı hiç gönderilmez · seçenek yoksa retry yok · preflight `allow` dönerse panel temizlenir.

`apiStub.ts::apiErrorRoute` dördüncü opsiyonel `details` parametresi aldı (26 mevcut çağrı yeri
etkilenmedi) — zarfın yapısal payload'ı olmadan RESTORE_CONFLICT test edilemezdi.

### Doğrulama

Lokal: `ruff check` · `ruff format --check` · `mypy src` (369 dosya) temiz · yeni integration
dosyası 10/10 · `-k "restore_conflict"` 10/10 · regresyon (trash_page + trash_agent_artifact +
user_manual + error-taxonomy ratchet) 49/49 · `tests/contract` (openapi drift guard dahil) yeşil ·
frontend `typecheck` + `lint` temiz, `trash.test.tsx` 20/20, `-t "Restore needs attention"` 6/6.

**Lokal tam backend suite tek koşuda tamamlanamadı** (%19'da bilinçli olarak durduruldu —
CLAUDE.md'de kayıtlı ortam tuzağı, paralel worktree oturumları CPU paylaşıyor). **Otorite CI:**
PR #446 **6/6 yeşil** — backend **2532 passed** (32m25s), frontend **625 passed** (60 dosya),
Docker, iki E2E (dev-auth + gerçek tarayıcı/Compose) ve A11Y axe-core taraması dahil.

### Dürüst sınırlar

- **Migration YOK**, alembic head değişmedi (`0039_backtest_run_cancellation`). `ENGINE_VERSION`
  bump edilmedi — motor yolu dokunulmadı.
- Conflict taksonomisi kodun **gerçekten ürettiği** iki kusuru kapsar (`head_pointer_moved`,
  `target_missing`). Doc 20 §5'in örnek olarak andığı "manual sequence insertion policy" ve
  "name/location conflict" için **kod bugün böyle bir conflict üretmiyor** — uydurma bir kind
  eklemek boş bir panel üretirdi. Yeni bir conflict doğduğunda `_CONFLICT_SUMMARY` + `_RESOLUTIONS`
  satırları birlikte eklenir (modül docstring'i bunu yazıyor).
- `RestoreConflictError.category` **değiştirilmedi** (`CONFLICT` olarak kaldı). Doc 20 §8.2 buna
  "preflight conflict" diyor ve `CONCURRENCY_OR_PREFLIGHT` daha isabetli olurdu, ama yayınlanmış
  bir kategoriyi değiştirmek istemci davranışını kırabilir — kapsam dışı bırakıldı, kayıtlı borç.
- `blocked` outcome'ı (purge_pending / purged / restored) preflight'ta raporlanır ama frontend
  paneli bunu ayrıca ele almaz: bu durumlarda satır zaten `restore_eligible=false` olduğu için
  Restore düğmesi hiç render edilmiyor.

---

## B-1 · doc 13 §8.2'nin kapsamadığı, kodda uygulanan portfolio-level cross-item kuralları

> **Bu bölüm neden var.** `docs/spec/` **kanonik kaynaktır ve DEĞİŞTİRİLMEZ**. Kod iki
> portfolio-level alanı (`max_total_exposure_percent`, `conflict_policy`) uyguluyor; doc 13
> **§8.2 canonical payload'ı bu iki alanı içermiyor**, §8.3 formülleri exposure cap tanımlamıyor
> ve kodun atıf yaptığı §8.4 gövdesinde ne "Max Total Exposure" ne de NET/BLOCK_OPPOSITE geçiyor.
> Yani **kod spec'ten ileri** — spec bir hata içermiyor, sadece kapsamıyor. Bu kayıt o boşluğun
> tek referansıdır: yeni bir geliştirici bu alanların nereden geldiğini spec'e bakmadan buradan
> bulabilmeli. Kod bu bölüme değil `doc 13 §8.4`'e atıf yapmaya devam eder (aşağıda neden meşru
> olduğu yazıyor); atıfları **buraya çevirme**.

### Spec boşluğunun tam sınırı (ampirik, 2026-07-29)

| Spec yeri | Ne diyor | Kodda karşılığı |
|---|---|---|
| `docs/spec/13_..._v1_1.md` §8.2 (satır 875-884) | `PortfolioAllocationConfigV1 { enabled, initial_capital, compounding_mode, reserve_cash_percent, entries[] }` | Kodda **+2 alan** var: `max_total_exposure_percent`, `conflict_policy` |
| §8.3 (satır 885-893) | `P0 / r / R0 / A0 / Ci0 / U0` + `allowed_size = min(desired, remaining_sleeve_capacity, item_risk_limits, ledger_solvency_limit)` | `min(...)` listesinde **portfolio exposure cap terimi yok**; motor onu ayrıca bağlar |
| §8.4 adım 6 (satır 907) | "Conflict Rules item intentini engellerse o itemin share'ı diğer item'lere run içinde otomatik devredilmez" | **Invariant meşru** — kod bunu uygular. Ama §8.4 gövdesi ne "Max Total Exposure" adını ne de `NET`/`BLOCK_OPPOSITE`/`KEEP_SEPARATE` token'larını içerir |

**Sonuç:** kodun `doc 13 §8.4` atfı **yalnız "engellenen item'in share'ı devredilmez"
invariant'ı için** doğrudur. **Alan kümesi ve token sözlüğü spec'te YOK — kod-yereldir.**

### İSİM ÇAKIŞMASI — iki ayrı düzlem, aynı alan adı (en sık karışan nokta)

`max_total_exposure_percent` **iki yerde** geçer ve **aynı şey değildir**:

| Düzlem | Nerede | Kaynak | Anlamı |
|---|---|---|---|
| **Per-strategy** | `limits.max_total_exposure_percent` (Strategy Details) | **Spec'te VAR** — doc 02 satır 1039 (`>0`, `>= max single`, "total main + layers cannot exceed. Allocation is external cap, not bypass") | TEK bir stratejinin ana pozisyon + layer'larının toplam exposure tavanı |
| **Portfolio-level** | `PortfolioAllocationConfigV1.max_total_exposure_percent` | **Spec'te YOK — bu kaydın konusu** | TÜM composition item'larının eşzamanlı toplam notional'ının, paylaşılan havuz `P0`'a oran tavanı |

İkisi de motorda bağlar (`engine.py:2837` yorumu bunu açıkça yazar). Doc 02'nin "Allocation is
external cap, not bypass" cümlesi tam olarak bu ilişkiyi anlatır: portfolio cap per-strategy
cap'i gevşetmez, üstüne biner.

### Nereden geldi

- **PR [#320](https://github.com/alimirbagirzade/Entropia/pull/320)** — commit `c747b7e`,
  branch `feat/portfolio-level-rules`, merge **2026-07-19**, başlık
  *"feat(allocation,engine): portfolio-level rules — Max Total Exposure + cross-item conflict policy"*.
  20 dosya, +1454/−10.
- Takip: **PR #321** (`fix/openapi-snapshot-portfolio-rules`) — `docs/openapi.json` snapshot'ını
  tazeledi (drift guard).
- **Migration `0035_portfolio_rules`** (revises `0034_package_implementation`). O tarihte alembic
  head'i buydu; **bugünkü head `0039_backtest_run_cancellation`**.
- **`ENGINE_VERSION` → `backtest-engine-v18-portfolio-rules`** (execution_key namespace kayması,
  INF-04/INF-05). **Bugünkü değer `backtest-engine-v18-funding-step-order`** — sonraki slice'lar
  (K-02/K-04/K-03) bump etti.

### Alanlar — kanonik tanım

`domain/allocation/config.py:118-119` (`PortfolioAllocationConfigV1`):

| Alan | Python tipi | DB kolonu (`portfolio_allocation_plan`) | NULL anlamı |
|---|---|---|---|
| `max_total_exposure_percent` | `Decimal \| None` | `NUMERIC(9,6)` nullable | **cap yok** |
| `conflict_policy` | `CrossItemConflictPolicy \| None` | `enum_column(..., "allocation_conflict_policy")` = `VARCHAR(14)` + CHECK, nullable | **`KEEP_SEPARATE`** (rules öncesi davranış) |

- **`max_total_exposure_percent`** = composition-wide tavan, **paylaşılan havuz `P0`'ın yüzdesi**.
  **100'ü aşabilir** (kaldıraçlı exposure); tip sınırı `999.999999`. Üst sınır validasyonu
  **bilerek yok** — kaldıraç meşru bir konfigürasyon.
- **`conflict_policy`** = **item'lar ARASI** aynı-enstrüman ters yön politikası
  (doc 02'nin strateji-içi Conflict Handling'inin cross-item karşılığı).
  Enum: `domain/allocation/enums.py:37-53` →

  | Token | Anlamı | Motorda ne olur |
  |---|---|---|
  | `KEEP_SEPARATE` | Her item bağımsız replay (rules öncesi davranış) | Gate kapalı |
  | `BLOCK_OPPOSITE` | Erken-pinlenmiş item aynı enstrümanda ters yönü tutarken geç-pinlenmiş item'in girişi bloklanır | Gate açık, doğrudan uygulanır |
  | `NET` | Toplam pozisyonun netlenmesi | **V1'de netlenmez** — muhafazakâr biçimde `BLOCK_OPPOSITE` olarak koşar, ifşa edilir (aşağı bak) |

- Her iki alan da **additive nullable, backfill yok** → mevcut planlar davranışını birebir korur.
- Parser'lar: boş string → `None` (`_parse_reserve` validator `reserve_cash_percent` ile paylaşılır);
  `conflict_policy` wire token'ına **normalize edilir** (`"block_opposite"` → `BLOCK_OPPOSITE`).

### Validasyon — `domain/allocation/rules.py:164-186`

| Kod | Şiddet | Koşul | `field` |
|---|---|---|---|
| `MAX_TOTAL_EXPOSURE_INVALID` | **BLOCKER** | alan **set edilmiş VE `<= 0`** | `max_total_exposure_percent` |
| `CONFLICT_POLICY_NET_V1` | **WARNING** | `conflict_policy == NET` | `conflict_policy` |

- **Set edilmemiş = geçerli** (cap yok). Blocker yalnız "kullanıcı bir cap yazdı ama anlamsız"
  durumunda çıkar. **Üst sınır kontrolü yok** (kaldıraç meşru).
- `CONFLICT_POLICY_NET_V1` **asla bloklamaz** — motorun `BLOCK_OPPOSITE`'a düşüşünü
  **çalıştırmadan önce** ön-ifşa eder. Kullanıcı NET seçip kaydedebilir; sürpriz yaşamaz.

### Kalıcılık

- **Plan kökü:** iki kolon da `portfolio_allocation_plan` üzerinde (0035). Draft upsert
  `commands/allocation_plan.py:139-140` (create) / `162-163` (update, OCC `row_version` altında).
- **Revision:** `portfolio_allocation_plan_revision` **kolon ALMADI** — değerler değişmez
  `revision.config` JSON snapshot'ında taşınır
  (`test_allocation_persistence.py`: `stored.config["max_total_exposure_percent"] == "150.000000"`).
  Yeni bir portfolio-level kural eklerken **kolon eklemeye gerek yok**, config snapshot'ı yeter.

### Motor davranışı — fail-closed + L4, hiçbir sınır sessiz değil

`resolve_portfolio_rules` (`domain/backtest/engine.py:664-702` — **public, alt çizgisiz**; alt
çizgili adla grep'lersen sıfır hit alırsın. Çağıran: `application/jobs/backtest_engine.py:290`) → `PortfolioRules`
(`domain/backtest/execution/state.py:272-278`).

| Durum | Motor ne yapar | L4 warning |
|---|---|---|
| Kural yok / `KEEP_SEPARATE` + cap yok | `None` döner → **rules öncesi motorla byte-identical** | — |
| Kural aktif (her zaman) | Sıralı pin-order uygulanır | `portfolio_rules_sequential_pin_order_precedence` (`engine.py:3368`) |
| Cap **set ama okunamaz / `<= 0`** | **SIFIR cap** (hiçbir giriş kabul edilmez) — "cap yok"a **düşmez** | `portfolio_max_exposure_unparseable_zero_cap` |
| `conflict_policy == NET` | `BLOCK_OPPOSITE` olarak koşar | `conflict_policy_net_executed_as_block_opposite` |
| **Bilinmeyen** policy token'ı (kurcalanmış/yabancı snapshot) | Fail-closed → bloklar | `portfolio_conflict_policy_unknown_fail_closed` |
| Enstrüman sembolü çözülemedi | Fail-closed → bloklar | `portfolio_conflict_symbol_unknown_fail_closed` |
| Zaman damgası parse edilemedi | Fail-closed → bloklar | `portfolio_rules_time_unparseable_fail_closed` |

- **Cap tabanı** = run'ın replay ettiği pinlenmiş sermaye: allocation altında paylaşılan havuz
  `P0` (normal yol), yoksa stratejinin kendi initial capital'ı (savunmacı, gerçek manifest
  akışında ulaşılmaz).
- **Blok gerekçeleri:** `portfolio_conflict_blocked` (`engine.py:1371`),
  `portfolio_max_total_exposure` (giriş: `1399`; stack/scale reddi: `2714`).
- **Diagnostics anahtarları** (`engine.py:3306-3320`): `portfolio_rules_active`,
  `portfolio_conflict_policy` (**KAYDEDİLEN** token), `portfolio_conflict_policy_executed`
  (**KOŞAN** token — NET'in düşüşü görünür kalır), `portfolio_max_total_exposure_cap`
  (çözülmüş para tutarı), `portfolio_prior_intervals`, `portfolio_conflict_blocked_entries`.
  **Kaydedilen ile koşan token'ın ayrı raporlanması bilinçlidir** — biri diğerinin yerine geçmez.

### Dokunulan yüzeyler (tam liste)

| Katman | Dosya:satır |
|---|---|
| Domain config | `domain/allocation/config.py:118-119, 129, 134` |
| Domain enum | `domain/allocation/enums.py:37-53` |
| Domain kurallar | `domain/allocation/rules.py:164-186` |
| Motor | `domain/backtest/engine.py:664-702, 866-892, 1366-1371, 1399, 2714, 3020-3033, 3306-3320` · `execution/state.py:272-278` · worker girişi `application/jobs/backtest_engine.py:88, 290` |
| Komut | `application/commands/allocation_plan.py:84-85, 99-100, 139-140, 162-163, 218-219, 546-552, 588-594` · **409 `changed_paths` alan listesi `673-674`** (O-serisi #457 sonrası — iki alan da diff'lenir) |
| Ready Check | `application/commands/readiness_check.py:770-777` (snapshot'a taşınır) |
| Query | `application/queries/allocation_plan.py` (draft projeksiyonu) |
| Repo | `infrastructure/postgres/repositories/allocation.py:54-55, 66-67` |
| ORM | `infrastructure/postgres/models/allocation.py:91-93` |
| Route | `apps/api/routes/allocation.py:56-57, 104-105` (draft PUT gövdesi) |
| OpenAPI | `docs/openapi.json` → `conflict_policy` (2228), `max_total_exposure_percent` (2272) |
| Frontend | `lib/allocation.ts:73-74, 194-195` · `pages/Portfolio.tsx:308-309, 332-333, 455-482` — "Portfolio rules" alan grubu: *Max total exposure %* (placeholder `e.g. 150 (blank = no cap)`) + *Conflicting signals (same instrument)* select (varsayılan `— (keep separate)`) |

### Test kapsamı

- `backend/tests/unit/test_backtest_portfolio_rules.py` — **15 test**, motor kapılarının tamamı.
- `backend/tests/unit/test_allocation_rules.py:178-205` — pozitif cap + `BLOCK_OPPOSITE`
  normalizasyonu, çoklu geçersiz değer için blocker, NET warning'i.
- `backend/tests/integration/test_allocation_persistence.py:337-380` — draft round-trip
  (`"150.000000"`), revision config snapshot'ı, `0` cap'in **revision'ı bloklaması**.
- `backend/tests/unit/test_backtest_engine_golden.py` — golden/execution_key regresyonu.

### Dürüst sınırlar

- **Sıralı (pin-order) uygulama, unified-clock co-simulation DEĞİL.** Erken bir item, geç bir
  item yüzünden **asla yeniden simüle edilmez**. Bu V1 sınırıdır ve her rules-aktif run'da
  `portfolio_rules_sequential_pin_order_precedence` warning'i ile ifşa edilir.
- **`NET` V1'de gerçekten netlemez.** Netleme, V1 motorunun koşmadığı unified-clock çok-item
  co-simülasyonunu gerektirir; düşüş hem validation warning'i (`CONFLICT_POLICY_NET_V1`,
  kaydetme anında) hem L4 engine warning'i (çalıştırma anında) ile **iki kez** ifşa edilir.
- **Bu bölüm doc 13'ü değiştirmez.** `docs/spec/` kanonik ve dokunulmazdır; buradaki kayıt
  yalnızca kodun spec'i **aştığı** yeri belgeler. Doc 13 bir gün bu alanları kapsayacak biçimde
  yeniden yayımlanırsa, otorite spec'e döner ve bu bölüm tarihsel not haline gelir.
## B-2 · Backtest — kodda var, doc 15'te açıklanmayan üç kavram (docs-only)

Kod değişikliği YOK; bu bölüm HEAD `dd07d48` üzerinde **ampirik olarak** doğrulanmış üç
davranışın kaydıdır. Üçü de doc 15'te tanımsız; ikisi zararsız genişletme, biri sonuçların
"aynı mı farklı mı" sorusunu doğrudan etkilediği için burada uzun uzun yazılıyor.

### 1. `execution_key` — manifest'in İKİNCİ hash'i

`domain/backtest/manifest.py::build_run_manifest` her run için **iki** sha256 üretir
(`shared/manifest.py::manifest_hash`, kanonik JSON). `ManifestBuildResult` ikisini birden taşır.

**`manifest_hash` ile farkı** tek cümlede: `manifest_hash` manifest'in **tamamı** üzerinden
hesaplanır (identity bloğu — `run_id`, `created_at`, `correlation_id`,
`requested_by_principal_id`, `composition_id`/`composition_snapshot_id` — ve `preflight` dahil),
bu yüzden **her run ve her retry benzersiz** bir değer alır; `execution_key` ise SADECE
**reproducibility içeriği** üzerinden hesaplanır ve **run kimliğini DIŞLAR**, bu yüzden aynı
girdiyi tarif eden iki farklı run **aynı** `execution_key`'i taşır. Yani: manifest_hash "bu
hangi run?" sorusunu, execution_key "bu hangi hesap?" sorusunu yanıtlar.

`execution_content` tam olarak şu dokuz alandır (`manifest.py:166-176`):
`composition_fingerprint` · `mainboard_items` (pinlenmiş `(root_id, selected_revision_id)`,
sıralı) · `capital_execution` · `result_artifact_context` (`metric_set_version` +
`output_artifact_profile`) · `engine_version` · `tick_data` (F-07i B) ·
`strategy_package_context` · `external_object_context` · `data_time_context` (üçü K-04).

**Dışarıda bırakılan ve NEDEN:** `preflight` bilerek yok. Warning taşıyan bir run'ın manifest
byte'ları — dolayısıyla `manifest_hash`'i — değişir ama `execution_key`'i **değişmez**; readiness
uyarısı bir hesap girdisi değildir, o yüzden bir uyarı satırı yüzünden motor sürümü uzayı kaymaz
(`commands/backtest_run.py:875-883` bunu açıkça yazıyor).

**`engine_version` execution_content'in İÇİNDE** — bu tasarımın çekirdeği. Her `ENGINE_VERSION`
bump'ı bütün `execution_key` uzayını kaydırır, böylece eski motorun ürettiği bir sonuç yeni motor
altında **asla** yeniden kullanılabilir sayılmaz. `manifest.py`'nin baştaki ~90 satırlık yorum
bloğu her bump'ın gerekçesini tek tek tutar (F-07i C · v17 per-item breakdown · v18 BLOCK_OPPOSITE
· fill modeli · available-time gate · full-pinning · funding-step-order · restriction-min-n).
HEAD'de `ENGINE_VERSION = "backtest-engine-v18-restriction-min-n"`.

**Nerede saklanıyor:**

| Tablo | Kolon | Kısıt |
|---|---|---|
| `backtest_run_manifest` | `manifest_hash` | `String(64)` NOT NULL **UNIQUE** |
| `backtest_run_manifest` | `execution_key` | `String(64)` NOT NULL **index=True, unique DEĞİL** |
| `result_manifest_snapshot` | `execution_key` | `String(64)` NOT NULL, indeks yok |

Duplicate `execution_key`'e izin verilmesi kaza değil — tanımı gereği tekrarlanabilir bir değer.
Dışarı da veriliyor: `queries/backtest_run.py:213` ve `domain/backtest/history.py` whitelist'i
(`history.py:279,327,346`).

**Sonuç paylaşımı — dürüst cevap.** HEAD `dd07d48`'de `execution_key` üzerinde **hiçbir sorgu
WHERE/JOIN yapmıyor** (`grep -rn "execution_key ==" src/` → 0 hit; kolon yalnız yazılıyor ve
projeksiyonda okunuyor). Yani **iki run aynı `execution_key`'i taşısa bile bugün birbirinin
sonucunu paylaşmaz** — her başarılı run kendi `BacktestResult`'ını materialize eder. Cross-run
idempotent-reuse **hazırlanmış ama bağlanmamış** durumdadır: indeks var, lookup yok. Bir RUN
isteğinin tekrarını bugün engelleyen şey `Idempotency-Key`/`run_idempotent`'tır, `execution_key`
değil (doc 15 §942 de duplicate RUN'ı idempotency key'e bağlıyor).

Gerçekten uygulanmış tek INF-04 reuse **run İÇİdir**: `domain/backtest/execution/portfolio.py`
(`_fold_composite_metrics:90-99`, `:239`) — marginal katkı için "item'sız kompozisyon" yeniden
**simüle edilmez**, kalan item'ların hâlihazırda hesaplanmış per-item çıktıları in-memory yeniden
fold edilir. Her item'ın bar-replay'i diğerlerinden bağımsız olduğu için bu, gerçek bir re-RUN'ın
raporlayacağının aynısını verir; `combine_item_runs` ile drift'e karşı birim testiyle pinlenmiştir.

İkinci fiili kullanım bir **regresyon kapısı**: K-09 motor ayrıştırmasında her dilim, aynı fixture
matrisi üzerinde **özdeş `execution_key` + özdeş `EngineOutput` digest**'i ile byte-equality
kanıtına bağlandı (`domain/backtest/execution/__init__.py:8`).

**Spec durumu:** doc 15'te `execution_key` **0 hit**; spec yalnız "manifest hash"ten söz eder
(§7/§8.4 — satır 523, 545, 639, 942). İki-hash ayrımı tamamen kod tarafı bir icat.

### 2. `ARTIFACT_TYPE_ALIASES` — V18 etiketleri → canonical tip

`domain/backtest/artifacts.py:33-40`, altı giriş dört canonical tipe (many-to-one) eşlenir:
`equity → EQUITY_CURVE` · `ledger → TRADE_LEDGER` · `trades → TRADE_LEDGER` ·
`signals → SIGNAL_EVENTS` · `events → SIGNAL_EVENTS` · `diagnostics → DIAGNOSTICS`.

Tek çağıran `normalize_artifact_type` (`artifacts.py:47`), tek çağrı yeri
`queries/result_artifacts.py:43`. **Fail-closed:** alias tablosunda ve `ArtifactType` enum'unda
olmayan bir değer sert `ARTIFACT_TYPE_INVALID` verir (`ArtifactTypeInvalidError`) — sessiz fallback
yok, docstring bunu açıkça söylüyor.

Spec'te tanımlı değil (doc 15'te ne alias tablosu ne `artifact_type` sözcüğü geçiyor). **Zararsız:**
canonical enum yolunu daraltmıyor, yalnızca V18 UI'ın kısa sözcüklerini path değeri olarak kabul
ediyor; canonical adlar (`equity_curve` vb.) aynen çalışmaya devam ediyor.

### 3. `ExportFormat.PARQUET` — spec'te olmayan üçüncü format

`domain/backtest/export.py:47-52`: `ExportFormat` = `CSV` · `JSON` · **`PARQUET`**. Doc 15 §3.2
(satır 217) "Trade Log CSV, Signal Events CSV, Equity Curve CSV, PineScript Signal Marker, Result
JSON" der; **"parquet" spec'te 0 hit**. Üstelik sızıntı sunum katmanına kadar gelmiş:
`frontend/src/lib/backtest.ts:461` → `EXPORT_FORMATS = ["csv", "json", "parquet"]`, yani kullanıcı
export formu açılır listesinde parquet'i **görüyor** ve seçebiliyor.

**Dürüst sınır — bugün hiçbir formatta byte üretilmiyor.** `commands/result_export.py::_op` yalnız
bir metadata satırı yazar (object key + checksum + `schema_version` + `row_count` + provenance =
kaynak Result'ın `manifest_hash`'i). `compute_export_checksum` satırları **format ne olursa olsun
her zaman JSON olarak** serialize eder; `fmt` sadece (a) checksum payload'ının bir bileşeni ve
(b) `build_object_key`'in dosya uzantısıdır. Parquet encoder **yok** — ama csv/json encoder'ı da
yok; V1'de object-storage put/get adapter'ı async ExportJob ile gelecek (modül docstring'i bunu
kayıt altına alıyor). Yani parquet bugün bir *etiket*; csv/json'dan tek farkı spec'in o iki adı
anmış, bunu anmamış olması. Format değeri checksum'a girdiği için aynı Result + aynı tip farklı
formatta **farklı** checksum üretir — yani etiket sessiz değil, provenance'a bağlı.

### Doğrulama

Salt-okuma denetim; kod/test/migration değişmedi. Yukarıdaki her iddia `HEAD dd07d48` üzerinde
`grep`/`sed` ile dosyadan okundu: `manifest.py:96-104,140-205` · `artifacts.py:23-58` ·
`export.py:26-101` · `models/backtest.py:156-172,310-325` · `repositories/backtest.py:107-133,356-364` ·
`commands/result_export.py:62-120` · `commands/backtest_run.py:515-525,875-890` ·
`execution/portfolio.py:90-99,232-241` · `lib/backtest.ts:461` · `docs/spec/15_*.md`.

---

## B-2 / B-3 · Market Data cross-row `rule_code` kataloğu + monotonluk sıkılaştırması (adjudicated)

**Denetim iddiası.** B-2: "kod spec'ten daha spesifik, doküman güncellenmemiş" — cross-row
validation altı `rule_code` üretiyor ama doc 11 bunların hiçbirini yazmıyor. B-3:
`TIMESTAMP_NON_MONOTONIC` **tüm** veri tipleri için BLOCKING_FAIL, oysa doc 11 §7.4 ordering
kontrolünü yalnız Tick/Trades satırında ve "Trade ID/sequence available ise" koşuluyla istiyor.
**İkisi de doğrulandı.** Karar: **kod olduğu gibi kalıyor, sıkılaştırma bilinçli olarak
adjudicate edildi**; eksik olan katalog burada yazılıyor. Spec dosyasına dokunulmadı.

> Denetimin verdiği satır numaraları (251/262/274/290/302) bayattı; gerçek satırlar aşağıdaki
> tabloda. Bulguların kendisi geçerli.

### B-2 — kanıt: kodlar spec'te gerçekten yok

`docs/spec/11_Entropia_V18_Market_Data_Page_Documentation_v1_1.md` içinde altı kodun tamamı için
**0 hit** (tek grep, birleşik desen). §7.4 kuralları **nesir** olarak tarif ediyor ("Duplicate
instrument+timestamp+resolution reported", "Declared cadence gaps recorded", "spread unit
absolute/bps/% must be declared"); §10.2 ise **audit event** listesi — rule_code taksonomisi
değil, dolayısıyla orada olmaması kusur değil. Doc 11'de rule_code kataloğu için ayrılmış bir §
**yok**; K-07 içtihadı burada da geçerli (her sayfanın kendi §-taksonomisi otoritedir, kodlar
aynı kusuru anlatır). Katalog bu yüzden spec'e değil **buraya** yazılıyor.

### Katalog — `domain/market_data/validation_rules.py::evaluate_cross_row`

| `rule_code` | Satır | Severity | Kapsam | Doc 11 nesir karşılığı |
|---|---|---|---|---|
| `MARKET_DATA_TIMEZONE_UNRESOLVED` | `:26` (sabit), `:316` | BLOCKING_FAIL | tüm tipler | §9.1 "Timezone/time basis" + "no silent UTC fallback" |
| `TIMESTAMP_UNRESOLVABLE` | `:327` | BLOCKING_FAIL | tüm tipler | §7.4 OHLCV "Timestamp non-null and timezone-resolvable" |
| `TIMESTAMP_NON_MONOTONIC` | `:338` | BLOCKING_FAIL | **tüm tipler (spec'ten SIKI — aşağıda B-3)** | §7.4 Tick "ordering kontrolü"; §4.4 (`:632`), §9.1 (`:1133`) "tick ordering" |
| `DUPLICATE_TIMESTAMP` | `:350` | BLOCKING_FAIL | **tüm tipler (spec'ten SIKI)** | §7.4 OHLCV "Duplicate instrument+timestamp+resolution reported" |
| `CADENCE_GAP` | `:369` | WARNING | yalnız OHLCV + `ResolutionKind.BAR` + okunabilir cadence | §7.4 OHLCV "Declared cadence gaps recorded" |
| `SPREAD_UNIT_UNDECLARED` | `:384` | WARNING | yalnız `SPREAD_EXECUTION` | §7.4 Spread "unit absolute/bps/% must be declared" |

`MARKET_DATA_TIMEZONE_UNRESOLVED`, K-01'de modül sabiti olarak pinlendi ve
`shared/errors.py::MarketDataTimezoneUnresolved.code` ile **birebir aynı**; validation-issue satırı
ile API hata yüzeyi aynı kusuru aynı adla söyler. Diğer beşi bugün yalnız issue satırında yaşar —
karşılık gelen bir `shared/errors.py` sınıfı yok, çünkü bunlar bir isteği reddetmez, revizyonu
NEEDS_REVIEW'a sürükler.

**Severity → lifecycle (önemli, çünkü tabloyu yanlış okutuyor):** `jobs/market_data.py::decide_outcome`
(`:127-136`) **PASS dışındaki her şeyi** NEEDS_REVIEW yapar — WARNING de auto-verify'ı bloklar.
Yani WARNING/BLOCKING_FAIL ayrımı Market Data'da **raporlama** ayrımıdır, lifecycle ayrımı değil.
Bu, doc 11 AT #9'u ("spread unit belirsizse VERIFIED state'e geçemez") `SPREAD_UNIT_UNDECLARED`
WARNING iken bile sağlar. (Research Data bilerek farklıdır — orada WARNING verify'ı geçirir;
gerekçe `domain/research_data/quality_rules.py` docstring §"Severity contract".)

`evaluate_cross_row`'un tek çağıranı `application/jobs/market_data.py:259`. Research Data bu
fonksiyonu **kullanmaz**, yalnız `resolve_timestamp`'ı ödünç alır (`quality_rules.py:42`) — bu
kataloğun blast radius'u Market Data ile sınırlı.

### B-3 — sıkılaştırma DOĞRU, ve **bilinçli sıkı** olarak adjudicate edildi

Doc 11 ordering'i üç ayrı yerde Tick'e bağlıyor: §7.4 Tick hücresi (`:1006`), §4.4 field contract
(`:632` "Tick ordering/side unknown"), §9.1 quality satırı (`:1133` "tick ordering/side"). OHLCV
hücresi ordering'den **hiç söz etmiyor**. Kod ise `evaluate_cross_row`'da tip dallanması olmadan
`pairwise(resolved)` üzerinden herkese uyguluyor. Sapma gerçek.

Sıkılaştırma **kasıtlı değildi** — `48be1a9 feat(r3): cross-row market-data validation (doc 11 §7.4)`
kuralı tek seferde tip-agnostik yazdı; K-01 ve O-29'un aynı dosyadaki adjudication yorumlarının
aksine burada gerekçe yorumu yok. Ama **gevşetilmedi**, çünkü:

1. **Teslim sırası = replay sırası, zincirde hiçbir yerde sort yok.** `_to_parquet_bytes`
   (`jobs/market_data.py:214-221`) satırları `parsed.rows` sırasıyla yazar → `stream_processed_batches`
   (`infrastructure/s3/parquet_stream.py:43-51`) dosya sırasıyla okur → `domain/backtest/engine.py::run_engine`
   bar döngüsü aldığı sırayla replay eder. Sıra dışı bir OHLCV barı **motorda birebir lookahead'dir**:
   ileri tarihli bir barın close'u, geçmiş bar işlenmeden tüketilir. Doc 11 §7.5'in known-time /
   anti-lookahead kuralı bunu OHLCV için de kusur yapar; §7.4'ün OHLCV hücresi ordering'i **yasaklamıyor**,
   sadece susuyor.
2. **Spec'in tick koşulu bu kod tabanında hiç sağlanamaz.** Canonical tick satırı
   (`validation_rules.py::TickRow`) `price` + `side` taşır; `trade_id`/`sequence` alanı **yok**.
   "Trade ID/sequence available ise" koşuluna harfiyen uyulsaydı ordering kontrolü **hiçbir zaman**
   çalışmazdı — ve sıra riski en yüksek tip (olay tabanlı tick) kontrolsüz kalırken, yapısı gereği
   daha güvenli olan OHLCV kontrol edilirdi. Koşulu uygulamak sonucu tersine çevirirdi.
3. **Yanlış pozitifin bedeli sınırlı ve fail-safe.** BLOCKING_FAIL revizyonu NEEDS_REVIEW'a alır;
   veri silinmez, ham asset asla değiştirilmez (§9.1 recovery: "Fix source/mapping/metadata; create
   successor revision. Never alter raw asset."), Admin inceleyip ilerletebilir. Ters yön —
   gevşetip sıra dışı seriyi auto-verify etmek — sessizce para-boyutlandıran motora girer.

**Aynı eksende ikinci sıkılaştırma:** `DUPLICATE_TIMESTAMP` de tip-agnostiktir; doc 11 duplicate'i
OHLCV hücresinde koşulsuz, Tick hücresinde Trade ID koşuluyla anıyor. Gerekçe aynı invaryant:
yinelenen bir bar iki kez replay edilir → çift sayım. Bu ikisi birlikte adjudicate edilmiştir.
`CADENCE_GAP` **gevşetilmedi/sıkılaştırılmadı** — spec'e uygun biçimde yalnız OHLCV + bar cadence
yolunda üretilir (`:363-372`); cadence'siz tipler O-29 gereği yalnız günlük coverage segmenti yazar,
gap **yargılanmaz** (`_build_daily_coverage` docstring).

### Kural (yeni cross-row kuralı eklerken)

Yeni bir `rule_code`'u **bu tabloya ekle** ve tip kapsamını açıkça yaz. Tip-agnostik uygulamak
istiyorsan gerekçeyi "teslim sırası = replay sırası" invaryantına bağla; bağlayamıyorsan kuralı
`market_data_type` dallanmasıyla kapsa. Kodun spec nesrinden sıkı olması **kendi başına kusur
değildir** — kaydedilmemiş olması kusurdur.

### Dürüst sınırlar

- **Kod değişmedi.** Bu slice yalnız `docs/PROJECT_HISTORY.md`'ye yazar; migration yok, alembic head
  `0039_backtest_run_cancellation`, `ENGINE_VERSION` bump edilmedi, test sayısı değişmedi.
- **Spec dosyası kasten değiştirilmedi** (görev kısıtı). Doc 11 §7.4 hâlâ ordering'i Tick'e bağlı
  anlatıyor; kod ile spec arasındaki fark artık *kayıtlı sapma*, *bilinmeyen sapma* değil.
- `TIMESTAMP_NON_MONOTONIC` ölçümü **teslim sırası** üzerinedir (`pairwise` ham sırada), oysa
  `DUPLICATE_TIMESTAMP` ve coverage `Counter`/`sorted` üzerinden çalışır. Bu bilinçlidir ama
  yan etkisi şu: sıra dışı bir seri hem NON_MONOTONIC hem (varsa) coverage segmenti üretir —
  coverage sıralanmış veriden hesaplandığı için sıra hatasını yansıtmaz.
- Bu kodların hiçbiri `docs/openapi.json`'da yayımlanmıyor (issue satırı gövdesi, hata zarfı değil);
  drift guard onları korumaz.
- Mevcut regresyon kanıtı sınırlı: monotonluk için iki test var (`tests/unit/test_market_cross_row_validation.py:56`,
  `tests/integration/test_market_crossrow_validation.py:160`) ve **ikisi de OHLCV** kullanıyor —
  tick/spread için tip-agnostik davranışı kilitleyen bir test **yok**. Yeni test eklenmedi (bu slice
  docs-only); borç olarak kayıtlı.

---

## F-07 §4.4 · Backend display DTOs — dört yüzeyin ham `*_id`'si kapandı, F-07 BÜTÜN olarak Complete (branch `feat/f07-display-dto-residuals`)

**Ne getirdi.** F-07'nin sunum yarısı PR #404'te kapanmıştı; geriye "DTO'sunda insan
okunur ad OLMAYAN" dört yüzey kalmıştı. Bu slice F-07'nin kendi reçetesini uyguladı —
*add display DTOs at query boundaries* — ve F-07'yi bütün olarak kapattı.

**Doküman kayması (2026-07-29 ampirik).** §4.4 tablosu `ResultDetail.tsx`'i yol vermeden
listeliyordu; dosya `pages/` altında **değil**, `frontend/src/components/ResultDetail.tsx`
(`PerItemCard` :416, `MarginalCard` :585). Dört yüzeyin file:line'ı yeniden ölçülüp §4.4'e
yazıldı.

| # | Yüzey | Alan | Nerede doldurulur |
|---|---|---|---|
| 1 | `pages/PreCheck.tsx:129` | `display_label` + `created_at` | `queries/create_package.py::_request_display_labels` — sayfa başına **iki batched lookup**: üretilen paketin `input_contract.name`'i, yoksa pinlenen Rationale Family'nin `display_name`'i |
| 2 | `pages/Library.tsx:1263`, `1279` | `source_package_name` | `commands/package_import.py::submit_package_import` — **submit anında** `manifest["name"]` (migration `0042`) |
| 3 | `components/ResultDetail.tsx:424`, `:595` | `item_label` | snapshot `item_manifest.items[].label` → run manifest `mainboard_item_labels` → `ItemRun.item_label` → result diagnostics |
| 4 | `pages/ReadyCheck.tsx:295` | `scope_label` | `queries/readiness_check.py::_scope_labels` — raporun **pinlediği** snapshot'tan |

**Tek upstream, iki tüketici.** 3 ve 4'ün kaynağı aynı: `MainboardWorkingItem.display_label_override`
→ composition snapshot `item_manifest.items[].label`. İki snapshot yazıcısı da yazar
(`commands/mainboard.py::_snapshot_manifest` ve `commands/readiness_check.py::_manifest` — ikizler,
biri değişirse diğeri de değişmeli). Snapshot JSONB olduğu için 3 ve 4 **migration istemedi**.

**İki invariant (ikisi de RED kanıtlandı).**

1. **Display label reproducibility'yi çatallayamaz.** `mainboard_items` `execution_key`'e
   hash'lenir (`manifest.py::build_run_manifest` → `execution_content`). Label'ı oraya koymak,
   bir item'ı yeniden adlandırınca **aynı kompozisyonun aynı replay'inin farklı execution_key
   üretmesi** demekti (INF-04/INF-05 ihlali). Bu yüzden label'lar ayrı, hash'e girmeyen
   `mainboard_item_labels` anahtarında taşınır → `execution_key` bit-aynı.
   `_pinned_items`'a `label` eklenince
   `test_labels_do_not_change_the_execution_key` + `test_labels_are_absent_from_the_hashed_pin_set`
   düşüyor, başka hiçbir test düşmüyor.
2. **Pinli artefakt canlı veriden etiketlenemez.** `_scope_labels` canlı composition'a join
   edecek şekilde değiştirilince `test_renaming_the_item_does_not_relabel_an_existing_report`
   düşüyor, başka hiçbir test düşmüyor. Yani rapor yazıldıktan SONRA item yeniden adlandırılırsa
   rapor eski adı korur — `is_current` izlenen, immutable bir raporu bugünün adıyla etiketlemek
   aktif olarak yanlış olurdu.

**ENGINE_VERSION bump — golden guard yakaladı.** İlk tam suite koşusunda tek bir test düştü:
`test_backtest_engine_golden.py::test_engine_output_matches_the_recorded_golden_digests`, ve tam
olarak beklenen 4 senaryoda: `portfolio.combine`, `combine_reversed`, `combine_shared_pool`,
`combine_non_executing_only`. **Strategy-replay senaryolarının hepsi bit-aynı kaldı** → engine
DAVRANIŞI değişmedi; değişen composite **artefaktın şekli** (per-item + marginal satırlarına
`item_label` eklendi). Bu, v17'nin per-item breakdown'ı eklerken kaydettiği durumun aynısı, o
yüzden aynı muamele: `ENGINE_VERSION` → **`backtest-engine-v18-min-n-filtered-events-per-item-labels`** + golden
baseline aynı commit'te yeniden üretildi. Gerekçe: bump olmadan etiketsiz eski bir result aynı
kompozisyonun re-RUN'ında **idempotent olarak yeniden kullanılır** (INF-04/INF-05) ve satırlar
sonsuza dek id-only kalırdı — düzeltme mevcut bir kompozisyona hiç ulaşmazdı. Bu **tek seferlik
namespace kayması**; `test_labels_do_not_change_the_execution_key` ile çelişmez (o test versiyonu
sabit tutup label DEĞERİNİ değiştirir). `test_strategy_config_min_true_count.py`'deki literal
tripwire yeni sürüme güncellendi ve yeni
`test_the_artifact_change_shifted_the_execution_key_namespace` eklendi.

**İlk plan yanlıştı, kapı düzeltti.** Slice "bump YOK" varsayımıyla yürütüldü: `execution_key`'in
GİRDİLERİ doğru analiz edilmişti ama **kalıcı artefaktın şekli** hesaba katılmamıştı. Golden guard
tam da bunun için var.

**Geriye uyum backfill ile DEĞİL, omission ile.** Slice öncesi snapshot / manifest /
`package_import_job` satırları label taşımaz; her okuyucu boş map veya `null` üretir, UI ham
id'ye düşer. Backfill, o artefaktların hiç görmediği adları uydurmak olurdu.

**Yan bulgu — doc 06 §510-512 uygulanmamıştı.** "V18 has no editable field; name is generated
after C.D.P as *New [Type] Package*" kuralı kodda yoktu: request-doğumlu her paket adsız
okunuyordu (`queries/library._package_name` → None), Pre-Check picker'ının elinde bu yüzden
id'den başka şey yoktu. `commands/create_package.py::_generated_package_name` artık C.D.P'de
yazıyor. **Yeni bir kullanıcı input'u eklenmedi** — doc 06 request aşamasında editable ad
alanı olmadığını açıkça söylüyor.

**Sunum sözleşmesi.** Yeni `frontend/src/components/LabelledId.tsx`: label varsa PRIMARY metin
+ altında/yanında muted `<code>` id; label yoksa **yalnız id** (uydurma ad YOK). Portfolio'nun
`ItemLabel`'ının nullable-server-label'a genellenmiş hâli.

**Migration `0042_package_import_source_name`** — `package_import_job.source_package_name`
VARCHAR(255) NULL. up/down/up ✓ (`LC_ALL=en_US.UTF-8`, temiz şema), `\d package_import_job` ile
model↔migration kolon paritesi doğrulandı. Neden submit anında yakalanıyor: `blocked`/`failed`
biten bir import hiç paket üretmez (join edecek kök yok) ve import edilen kopyanın sonradan
yeniden adlandırılması "ne import edildi" tarihini yeniden yazmamalı.

**Testler.** Yeni `tests/unit/test_f07_manifest_item_labels.py` (5) +
`tests/integration/test_f07_display_labels.py` (6, `test_readiness_persistence`'ın seed
helper'larını yeniden kullanır — duplicate item ekleyerek deterministik `DUPLICATE_ENABLED_ITEM`
scope'u üretir). Frontend'de dört yüzeyin her biri için **label render** + **label'sız satır
id'ye düşer** çifti. Ölçülen: frontend **654/654** (62 dosya, `--no-file-parallelism`),
`ruff`/`ruff format`/`mypy src` (372 dosya) ✓. Backend tam suite lokal: ilk koşu **1 failed /
2732 passed** (yukarıdaki golden guard), bump + regenerate sonrası etkilenen modüller geçiyor.
**Otorite CI.**

**Dürüst sınır.** Dört route da gövdesini `dict[str, Any]` olarak bildiriyor, bu yüzden yeni
alanlar **`docs/openapi.json`'a yayımlanmıyor** ve drift guard onları göremiyor — O-30'un
kaydettiği aynı kör nokta. Dört legacy route'a typed response model vermek, kendi
idempotent-replay uyumluluk analizini gerektiren AYRI bir iş; burada yapılmadı.

**Yol boyunca düzeltilen iki bayat CLAUDE.md satırı:** alembic head `0039` değil **`0040`**'tı
(bu slice `0041` yaptı); `ENGINE_VERSION` `-funding-step-order` değil
**`backtest-engine-v18-restriction-min-n`** (I-15a).
