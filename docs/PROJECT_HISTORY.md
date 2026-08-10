<!-- doc-status: historical -->
> **HISTORICAL RECORD — bu belge GÜNCEL GERÇEK DEĞİLDİR.** Yazıldığı andaki durumu
> kaydeder; SHA'lar, sayılar, alembic head'i ve "next" maddeleri bayat olabilir.
> Güncel otorite: `CLAUDE.md` §Current position + `docs/generated/repository_facts.md`
> (üretilmiş, CI'da `--check` ile kapılı).

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

## I-07 · `human_users` OCC — şüphe bir adlandırma yanılgısıydı, migration YOK (PR #499)

**Branch:** `refactor/i07-human-users-row-version` · **migration YOK** (alembic head
`0041_filtered_event_artifact` değişmedi) · **backend kaynağı değişmedi.**

### Görev nasıl açıldı, ne çıktı

I-07 şu öncülle geldi: *"soft-delete taşıyıp `row_version` taşımayan TEK asimetrik kök tablo"* —
ve iki dallı bir karar istedi. Ampirik sonuç iki dalı da geçersiz kıldı:
`human_users` OCC'yi hem gerektiriyor hem **zaten taşıyor** — kolonun adı `row_version` değil,
`version`.

### Kanıt (sevk edilmiş hâl, dokunulmadı)

| Ne | Nerede |
|---|---|
| OCC kolonu | `models/identity.py:40` → `version: Mapped[int]` (`Integer NOT NULL default=1`) |
| Mutasyonda +1 | `commands/role_assignment.py:123` · `commands/roles.py:66` |
| 409 typed hata | `commands/role_assignment.py:94-95` → `USER_ROLE_VERSION_CONFLICT` |
| Dual-token (O-12) | `routes/admin_panel.py:97-100` → `reconcile_occ_tokens` |
| Row-lock | `session.refresh(user, with_for_update=True)` |
| No-op disiplini | aynı rol → `changed=false`, version bump ve audit yok |
| Idempotency | gövde `run_idempotent` içinde |

### Karar: `row_version` kolonu EKLENMEDİ

1. `version` zaten OCC token'ı; yanına `row_version` koymak aynı satırda iki bağımsız
   önkoşul yaratır ve O-12'yi ihlal ederdi.
2. Yeniden adlandırma kırıcıdır; `version` tel üstünde yayımlanıyor.
3. Farklı ad zaten repo konvansiyonudur; `registry_version` aynı davranışı başka
   tablolarda taşır.

### Asıl kusur: harita yanlış söylüyordu

`DATA_MODEL.md` içindeki `human_users` OCC hücresi `—` yerine `✔ version` olarak düzeltildi.
OCC'nin kolon adıyla değil davranışıyla tanınacağı kayda geçirildi.

### Dürüst sınır

`human_users` soft-delete kolonlarını taşısa da bunlara yazan bir komut ve K-06 trash katalog
kaydı yoktur. Kullanıcı silme özelliği eklenirse katalog, deletion command, purge job ve
trash query birlikte eklenmelidir.

### Doğrulama

- `test_panel_management_logs.py` 26 passed.
- Frontend tsc + eslint temiz.
- CI 6/6 yeşil.

---

## Current-main ground-truth reset (2026-08-03) — docs/audit-only

**Base:** `origin/main` @ `0dcce69` · **Branch:** `docs/current-main-ground-truth-reset` ·
**Production kodu değişmedi** (`backend/src`, `backend/alembic/versions`, `frontend/src`,
runtime config, Docker, test beklentileri, engine, API — hiçbirine dokunulmadı).

**Amaç:** stale status belgelerinin sonraki oturumları yanlış migration/test/PR/issue/acceptance
bilgisiyle çalıştırmasını durdurmak. Yeni özellik yok, davranış değişikliği yok.

### Yeniden ölçülen olgular

| Olgu | Değer | Komut / exit |
|---|---|---|
| Alembic head | `0043_i08_registry_strategy_fks`, 43 migration, **tek head** | `uv run alembic heads` · 0 |
| OpenAPI | 177 path / 196 operation / 119 schema, **drift yok** | `openapi_export --check` · 0 |
| Route | 195 decorator / 31 dosya | grep |
| Tablo / FK | 104 / 140 (30 model dosyası, 25 FK dosyası) | grep |
| Backend test | **2886 collected** / 271 dosya | `pytest --collect-only -q --no-cov` · 0 |
| Frontend test | **673 collected** / 66 dosya; typecheck temiz | `vitest list --no-file-parallelism` · 0 ; `npm run typecheck` · 0 |
| Capability matrix | 62 girdi — 40 `active_v1` / 22 `future_dev`; Python↔TS parity yeşil | `test_capability_matrix.py` · 0 |
| Frontend route / nav | 33 somut route (+catch-all) · `ALL_NAV_ITEMS` 25 · 31 sayfa · 40 `lib/*.ts` | grep |
| Acceptance ID | **174/215 (%80)**, untraced 41, 347 test dosyası | `acceptance_id_scan.py` · 0 |
| PR / issue | **0 açık PR, 0 açık issue** (denetim başında) | `gh pr list` / `gh issue list` · 0 |
| `ENGINE_VERSION` | `backtest-engine-v18-same-candle-entry-exit` | `manifest.py:118` |

### Doğrulanmış boşluklar (implementation)

1. **ESP resolver lifecycle-unsafe** — `queries/esp.py:214-268` yalnız `entry.trust_state`
   okuyor; Package Root `deletion_state`/`lifecycle_state` **hiç okunmuyor**, soft-delete
   `set_trust_state` çağırmıyor → soft-delete edilmiş root **yeni** resolution'da kullanılabiliyor.
   Fonksiyonun kendi docstring'i (`:228`) tersini iddia ediyor. **Hiçbir test kapsamıyor.**
2. **ESP export manifest eksik** — `commands/package_lifecycle.py:785-799` yalnız
   validation/approval state taşıyor; runtime adapter, warm-up, timing semantics, repaint
   policy, validation run id, validator version, vectors/checks, evidence **yok**; canonical
   key + signature yalnız teamülen `input_contract` içinde hayatta kalıyor.
3. **Tool Gateway** — `ToolName` 23 üye; 10 literal `strategy.*` / `trading_signal.*` aracının
   **hiçbiri yok** (repo genelinde 0 hit). Domain komutları tamdır — bu **ayrı eksendir**.
4. **Package Library Request Validation — frontend-only boşluk.** Backend tam
   (`routes/library.py:204` → aynı CP pipeline'ı, owner-or-Admin, bayrak 3 read path'te);
   frontend'de action/mutation hook/durum göstergesi **yok**, frontend testi sıfır.
5. **Shared Equity Allocation = sequential approximation.** Dış döngü item üzerindedir
   (`jobs/backtest_engine.py:298`), global valuation clock yok, ledger item başına.
   **Gizlenmiyor:** `portfolio_curve_sequential_not_unified_clock` L4 token'ı immutable
   Result'a yazılıyor — ama `lib/backtest.ts` bu koda insan-okur etiket vermiyor, UI'da ham
   token görünüyor.
6. **Panel ▸ Logs** hâlâ id'den türetilmiş `Backtest Result <id>` başlığı basıyor
   (`PanelLogs.tsx:134`) — Results History'de bilerek terk edilmiş olan aynı kusur.

### NOT-A-GAP düzeltmeleri (yanlış blocker üretilmedi)

- **Agent runtime provisioning.** `agent_alpha` = principal (yalnız `apps/seed.py:217-219`),
  `alpha-agent` = runtime (yalnız `0016_analysis_lab.py:251-261` `bulk_insert`). Fresh
  `alembic upgrade head` runtime satırını **oluşturur**. Ayrım şemada zorunlu (`0017:37-38`
  iki farklı FK hedefi). Yeni provisioning sistemi **önerilmedi**; tek kalan iş fresh-install
  acceptance testidir.
- **S5b/S5c/S5d.** Round-3 backlog'un "hepsi 0 hit" tablosu **stale token adlarıydı**:
  Stop Mode → `stop_trigger_requirement` (`any_active`/`all_active`), Multiple Stops →
  `stop_conflict_resolution`, Same Candle → `same_candle_entry_exit` (PR #513). S5c
  (`timeframe_mode`/`custom_sequence`) ve S5d (`logic_blocks`) de landed. **Üçü de kapalı.**
- **Historical pinned revision** okunabilirliği doğru davranıştır, kusur değildir.
- **Results History `display_title`** bilerek render edilmiyor (regresyon testi var).

### A-08 — insan kapısı

GitHub **#514** 2026-07-30T19:05:32Z'de **kanıt commit edilmeden kapatılmıştı**. Repository'de
NVDA/Firefox/Windows sonucu, VoiceOver/Safari/macOS sonucu, atanmış denetçi, sürüm bilgisi,
doldurulmuş 22-sayfa matrisi ve tek bir `SR-BULGU` kaydı **yok**
(`a11y_screen_reader_audit_checklist.md:28,38-39,89-98`). **#514 yeniden açıldı**; A-08
hiçbir belgede `Complete`/`PASS` yazılmadı. D-10 (2026-07-30, PO imzalı) 45 accent-mavi
düğümü kalıcı sapma yapar — bu **uyumluluk iddiası değildir**, WCAG 2.2 AA 1.4.3 karşılanmıyor.

### Onarılan stale belgeler

`README.md` (alembic head `0035`→`0043`, test sayıları) · `docs/CODEMAPS/README.md`
(head `0040`→`0043`, 102→104 tablo, 135→140 FK) ·
`entropia_v18_remediation_status.md` (olgu tablosu + A-08 issue durumu) ·
`v18_final_acceptance.md` (A-08 issue durumu) · `POST_V1_SPEC_GAP_BACKLOG_ROUND3.md`
(S5 b/c/d kapandı banner'ı) · `acceptance_id_map.md` §H (taze tarama) ·
`CLAUDE.md` §Current position. Tarihsel gövdeler **değiştirilmedi**, üstlerine tarihli
uyarı eklendi.

### Yeni belge

`docs/audit/current_main_ground_truth_2026-08-03.md` — 19 bölüm, her bulguda status /
canonical source / production path / test-evidence / risk / önerilen slice.

### Dürüst sınır

Tam backend ve frontend suite **koşulmadı** (docs-only slice) — yukarıdaki sayılar
`collected`'dir, `passed` değil; otorite CI'dır. Migration up/down/up ispatı yapılmadı;
fresh-install davranışı `0016`'nın kodundan okundu, canlı DB'den değil. E2E/visual/a11y
suite koşulmadı; kapıların varlığı workflow dosyalarından okundu. `main` bu worktree'de
checkout edilemedi (başka worktree tutuyor) — branch doğrudan `origin/main` SHA'sından
oluşturuldu, içerik özdeştir.

### Sıradaki tek slice

**ADIM 2 — `fix/esp-lifecycle-safe-resolution`** (yukarıdaki boşluk 1).

---

## ESP lifecycle-safe resolution — G-01/§E.2 kapatıldı (branch `fix/esp-lifecycle-resolution`)

**Base SHA:** `ef478477df532a57a4261f07e242dbfbfe0da233` (`ef47847`, #518 merge'ü) ·
**Tarih:** 2026-08-03 · **Migration YOK** (şema değişmedi; alembic head
`0043_i08_registry_strategy_fks`, tek head) · **OpenAPI drift YOK** ·
**`ENGINE_VERSION` DEĞİŞMEDİ.**

### Reproduction — önce kusur üretildi

Kod yazılmadan önce `origin/main` üzerinde ampirik probe:

```
resolve BEFORE soft delete  -> True  pkgrev_01KZ35DARPWXMHJYK998SCSACT
root.deletion_state         -> soft_deleted
registry.trust_state        -> trusted_active      (hiç demote edilmiyor)
resolve AFTER  soft delete  -> True  pkgrev_01KZ35DARPWXMHJYK998SCSACT
direct delete of trusted_active -> soft_deleted    (hiçbir blocker yok)
```

Yani soft-deleted bir ESP **yeni** Pre-Check'e pinlenebiliyordu ve trusted-active bir
resolver doğrudan silinebiliyordu. Fonksiyonun kendi docstring'i tersini iddia ediyordu.

### Ne değişti

1. **`domain/esp/resolver.py`** — `evaluate_resolution` artık `ResolverRootFacts`
   (deletion_state + lifecycle_state + package_kind) alıyor. Yeni reason'lar:
   `ROOT_MISSING` / `WRONG_PACKAGE_KIND` → `RESOLVER_NOT_RESOLVED` (404),
   `ROOT_NOT_ACTIVE` → `RESOLVER_NOT_ACTIVE` (409, doc 07 §12). Kontrol sırası:
   yapısal kimlik → contract (key/signature/adapter) → availability (root lifecycle →
   trust → validation → approval). Root, trust'tan ÖNCE bakılır: ikisi de bozuksa sebep
   köktür, pointer yalnızca bayat semptomdur.
2. **`queries/esp.py`** — `_root_facts` ile kökü ve package detail'i yükler; iki facet
   birden okunur (doc 09 §11.2 bunları ayrı tutar).
3. **`shared/errors.py`** — `DeletePolicyBlocked` / `DELETE_POLICY_BLOCKED` (409,
   `lifecycle`, `suggested_action=deprecate_resolver_first`) **geri geldi**; mesaj doc 09
   §7.1 katalog metninin birebir kendisi. O-03 bunu "hiç raise edilmiyor" diye silmişti;
   artık gerçek bir raise yolu var, bu yüzden `test_error_taxonomy_no_dead_definitions.py`
   ratchet'i gerekçesiyle güncellendi (`KNOWN_UNRAISED` hâlâ boş).
4. **`commands/deletion.py`** — deprecate-first blocker (doc 09 §9.5 adım 2) ve
   **`_soft_delete_preflight` artık `soft_delete_registry_root`'tan da çağrılıyor.**
   Bu, slice'ın en önemli bulgusuydu: paketlerin ÜRETİM silme yolu
   `pkg_cmd.soft_delete_package` → `soft_delete_registry_root`'tur ve preflight'ı
   **tamamen atlıyordu** — blocker'ı yalnız `soft_delete_entity`'ye koymak hiçbir şeyi
   korumazdı. Preflight `entity_type` ile dallandığı için market/research kökleri
   etkilenmez.
5. **`repositories/esp.py`** — `get_trusted_active_by_entity` (trust state SQL'de
   filtrelenir; kural çağırana kopyalanmaz).
6. **`jobs/create_package.py::registry_fingerprint`** — root lifecycle'ı da hash'ler.
   Önceden yalnız registry pointer'ı gözlemleniyordu, dolayısıyla bir resolver kökü
   silindiğinde fingerprint kıpırdamıyor ve PASSED bir tarama "taze" kalıyordu. Kararı
   sunucu türetir; browser bu kolonları hiç görmez (doc 07 §8.1).

### Historical integrity ve restore semantiği

- **Historical pin bozulmadı.** Kapı yalnız YENİ-iş yolunu daraltır. Pinlenmiş bir
  dependency snapshot zaten kesin `embedded_revision_id` taşır ve doğrudan
  `package_revision`'dan okunur — `resolve_embedded_dependency`'den hiç geçmez. Test:
  `test_historical_pin_stays_readable_after_the_resolver_is_closed` + PC-19 clause 1.
- **Restore trust'ı geri açmaz.** Restore kökü `active` yapar, registry'ye dokunmaz;
  trust `deprecated` kalır, pointer `None` kalır, resolver yeni iş için hâlâ kapalıdır.
  Yeniden seçilebilmesi için açık bir Admin activation gerekir (doc 09 §9.5 adım 4).
- **Soft-delete registry'yi `unavailable` yapMAZ — bilinçli karar.** `unavailable`
  `domain/esp/state_machine.py`'de terminaldir; delete'te oraya düşürmek tek yönlü kapı
  olurdu ve restore edilmiş bir kök bir daha asla aktive edilemezdi — doc 09 §9.5 adım 4'ün
  "policy re-evaluation" şartıyla çelişirdi. "Trash'teki resolver kökü asla `trusted_active`
  değildir" değişmezi bunun yerine deprecate-first blocker'ıyla garanti edilir; resolution
  ise pointer'ın demote edildiğine güvenmek yerine kök lifecycle'ını doğrudan okur.

### Testler

Yeni: `tests/integration/test_esp_lifecycle_resolution.py` (24 vaka) —
active-trusted success · soft-deleted/purge_pending/purged/lifecycle-deprecated/candidate/
deprecated failure · missing-detail + wrong-kind + signature/adapter · direct-delete
blocked (Trash entry ve audit YAZILMAZ) · non-resolver paket hâlâ silinebilir ·
deprecate→pointer temizlenir→delete başarılı · approval+audit+outbox · unauthorized
deprecate · stale `expected_registry_version` 409 · idempotent replay · restore trust'ı
açmaz · historical pin okunur · fingerprint hem registry hem lifecycle değişiminde kayar.
`unit/test_esp_resolver.py` root-gate vakalarıyla genişletildi.

Hizalanan mevcut testler: `test_acceptance_esp_package_gaps.py` PC-19 (artık deprecate-first
yolundan siliyor; "HOLE" paragrafı kapanış kaydıyla değiştirildi) ve
`tests/contract/test_esp_contract.py` (resolve double'ları kök/detail okumalarını da
karşılıyor).

---


## Shared portfolio containment — ADIM 3: shared capital fail-closed (PR #520)

**Base SHA:** `948b6fb` (#519 merge'ü) · **commit `088e3e9`** · **merge `6c46c03`** ·
**branch** `fix/portfolio-shared-mode-containment` · **Tarih:** 2026-08-03 ·
**Migration YOK** · **OpenAPI drift YOK** (196 operation sabit) ·
**`ENGINE_VERSION` BİLEREK bump EDİLMEDİ.**

### Reproduction — kusur kod yazılmadan ÖNCE ampirik olarak üretildi

Doc 13 §8.3/§8.4/§13 ve §14 kabul testi 11, **her timestamp'te TEK portfolio valuation
snapshot** şart koşuyor. Engine ise timestamp yerine **ITEM üzerinde** döngü kuruyordu: her
item kendi bar ekseninde, **tam havuz `P0` ile seed edilmiş kendi ledger'ında** replay
ediliyor, sonra `combine_item_runs` bitmiş koşuları **pin sırasında** birleştiriyordu.
Ölçülen üç sonuç:

* Kompozit "portfolio equity curve" **zaman-sıralı DEĞİL** — iç içe geçen işlemli iki item
  `01:00, 04:00, 02:00, 03:00` sırasıyla nokta üretiyor.
* Sıralı fold **`max_drawdown = 5000.00`**; aynı dört kapanış **tek saatte `3000.00`** →
  **%66 fazla**. `max_drawdown_pct` ve `romad` ondan türüyor.
* `resolve_allocation_execution` **HER item'a tam havuzu** veriyor, **hiç çapraz-item durumu
  yok** → sleeve kendi öz sermayesi üzerinden bileşikleniyor; havuz **yalnız isimde**
  paylaşımlı.

### Karar — bildirimi RETTE çevirmek

Gerçek unified clock **YOK**. Sapma zaten bildiriliyordu
(`portfolio_curve_sequential_not_unified_clock`) **ama sonuç yine de kanonik cevap olarak
sevk ediliyordu**. Bu PR bildirimi **RETTE** çevirdi — main'in önceki ürün pozisyonunun
**bilinçli tersine çevrilmesi**. **Authoring korundu, execution engellendi:** taslak HÂLÂ
KAYDEDİLİR.

Karar kaydı: **`docs/decisions/2026-08-03_shared_portfolio_containment.md`**
(§3 reproduction · §5 mekanizma · §6 kaldırma şartları · §7 tarihsel Result'lar ·
§8 bilinçli kapsam kaybı).

### Mekanizma — tek kanonik kaynak, dört yüzey okuyor, hiçbiri tekrarlamıyor

Yeni saf düzlem **`backend/src/entropia/domain/allocation/capability.py`** (DB yok, I/O yok):
`SHARED_ALLOCATION_STATUS = "future_dev"` (tek anahtar) ·
`SHARED_ALLOCATION_CAPABILITY_KEY = "portfolio.shared_capital_allocation"` ·
`SHARED_ALLOCATION_FIELD_PATH = "enabled"` · `SHARED_ALLOCATION_MESSAGE` ·
`SHARED_ALLOCATION_REMEDIATION` · `SHARED_ALLOCATION_DEPENDENCY` ·
`LEGACY_SEQUENTIAL_RESULT_NOTE` · `shared_allocation_is_executable()` ·
`shared_allocation_requested()` · `shared_allocation_capability_view()`.

1. **`domain/allocation/rules.py::validate_allocation`** →
   `AllocationIssueCode.SHARED_MODE_NOT_IN_BUILD` (`allocation/enums.py:105`), **BLOCKER**,
   `field="enabled"`, **ilk sırada = lead blocker** → Portfolio sayfası + revision freeze
   reddi. **Taslak HÂLÂ KAYDEDİLİR.**
2. **`domain/readiness/validators.py`** →
   `ReadinessIssueCode.ALLOCATION_SHARED_MODE_NOT_IN_BUILD` (`readiness/enums.py:176`),
   scope `portfolio_allocation`, `remediation` + `field_path` (doc 14 §9.1). Yeni tablo
   **`_ALLOC_REMEDIATION`** (`validators.py:136`, okunduğu yer `:1144`).
3. **`application/commands/backtest_run.py::_admit_run_body`** (`:488`, guard `:543`) —
   **Ready Check'ten BAĞIMSIZ** guard. `snapshot.capital_mode_snapshot`'ı **doğrudan** okur
   ve **`build_run_manifest`'ten ÖNCE** (`:574`) çalışır → **run / manifest / job hiç
   oluşmaz** (doc 15 §9.3). request + retry, human + Agent **hepsi** buradan geçer; dayanıklı
   `run_admission_rejected` audit'ini `_admit_run`'ın handler'ı diğer tipli retlerle aynı
   şekilde yazar.
4. **`application/queries/allocation_plan.py:59,76`** → `shared_mode_capability` yayınlar;
   **`frontend/src/pages/Portfolio.tsx:357`** **verbatim** basar. **Kontroller etkileşimli
   kalır** — disabled UI **sunumdur, authorization DEĞİLDİR**.

### Değişmeyen sınırlar

* **Independent capital dokunulmadı** (doc 13 §1.1 — eksik mod değil).
* **Kalıcı Result'lar immutable ve değiştirilmedi.** Pre-containment bir shared-pool Result
  `diagnostics.composition.capital_allocation = "shared_pool"` değerini ve
  `portfolio_curve_sequential_not_unified_clock` uyarısını **byte-for-byte** korur
  (`test_a_legacy_shared_pool_result_stays_readable_and_unmodified`). Yalnız **okuma-zamanı
  etiketi** eklendi: `frontend/src/lib/backtest.ts::diagnosticWarningLabel` (`:442`,
  `components/ResultDetail.tsx:668` kullanır) — audit **G-07**'nin ham-token sorununun cevabı.
* **Migration YOK:** `readiness_issue.code = String(64)`, CHECK yok, yeni değer 35 karakter;
  `portfolio_allocation` scope üyesi zaten vardı. **Alembic head `0043_i08_registry_strategy_fks`
  değişmedi (tek head).**
* **OpenAPI drift YOK** — yeniden üretilip diff'lendi, **196 operation**.
* **`ENGINE_VERSION` BİLEREK bump EDİLMEDİ:** çalışan davranış değişmedi, **çalışması
  engellendi**. (Kaldırma sırasında bump **zorunludur** — decision record §6 madde 6,
  INF-04/INF-05.)
* **Route path · react-query key · OCC token · `Idempotency-Key` · hook · SSE taksonomisi ·
  `lib/*.ts` veri mantığı değişmedi.**

### Yeni / değişen dosyalar (25 dosya, +1459 / −79)

**YENİ:** `domain/allocation/capability.py` (203) ·
`tests/unit/test_shared_allocation_containment.py` (312, **9 test**) ·
`tests/integration/test_shared_allocation_containment.py` (285, **7 test**) ·
`frontend/src/test/legacySequentialResultLabel.test.ts` (34, **3 test**) ·
`docs/decisions/2026-08-03_shared_portfolio_containment.md` (164).

**DEĞİŞEN (backend):** `commands/backtest_run.py` · `queries/allocation_plan.py` ·
`domain/allocation/enums.py` · `domain/allocation/rules.py` · `domain/readiness/enums.py` ·
`domain/readiness/validators.py`.
**DEĞİŞEN (frontend):** `lib/allocation.ts` (`SharedModeCapability`, `:115`) ·
`lib/backtest.ts` · `pages/Portfolio.tsx` · `test/portfolio.test.tsx`.
**Hizalanan mevcut testler:** `test_allocation_fx_dependency.py` ·
`test_allocation_persistence.py` · `test_backtest_manifest_warnings.py` ·
`test_backtest_persistence.py` · `test_e2e_pipeline.py` · `test_gateway_parity_s4.py` ·
`test_allocation_item_kind.py` · `test_allocation_rules.py`.
**CODEMAP (PR içinde güncellendi):** `docs/CODEMAPS/BACKEND_LAYERS.md` (allocation satırı →
`capability.py` + containment notu) · `docs/CODEMAPS/BACKEND_ROUTES.md`
(GET portfolio-allocation-draft altına `shared_mode_capability` notu).

### Testler / CI

Tam backend `uv run pytest -q`: **exit 0, 0 FAILED, coverage %92.43** (kapı %90) ·
`ruff check .` / `ruff format --check .` / `mypy src` **temiz** ·
frontend `vitest --no-file-parallelism`: **676 passed / 66 dosya, exit 0** ·
`tsc -b --noEmit` temiz. **CI PR #520: 6/6 pass** — Backend lint/type/test 37m26s ·
Frontend 1m58s · E2E real-browser F-23 7m02s · E2E dev-auth 2m04s ·
A11Y axe-core R2-14 2m39s · Docker 56s.

### Dürüst sınırlar

**1) Bilinçli kapsam kaybı (decision record §8).** Admitted shared run kalmadığı için **üç
davranış artık uçtan uca test edilemiyor:**

* worker'ın **pinned pool `P0`** ile kapitalizasyonu — **sizing aritmetiği**
  `tests/unit/test_backtest_engine_allocation.py`'de duruyor;
* portfolio kurallarının (`max_total_exposure_percent`, `conflict_policy`) **DONDURULMUŞ**
  revision'a taşınması — draft round-trip **ve** freeze reddi test ediliyor;
* **RC-03**'ün orijinal fixture'ı — artık strateji kapsamlı `EXECUTION_ASSUMPTIONS_DEFAULT`
  uyarısına taşındı; ulaşılamaz hale gelen yol
  `test_shared_allocation_warning_path_is_now_fail_closed`
  (`tests/integration/test_backtest_manifest_warnings.py:108`) ile kilitli.

**Containment kaldırılırken üçü de geri getirilmeli** — sessizce bırakılmamalı. Ayrıca
`test_composite_portfolio_curve_is_not_time_ordered` **pozitif muadiline yeniden yazılmalı,
SİLİNMEMELİ** (decision record §6 madde 5).

**2) "ADIM 20 unified oracle gate" BU REPODA TANIMLI DEĞİL.**
`docs/audit/current_main_ground_truth_2026-08-03.md` §18 yalnız **1–8** slice'ı listeliyor;
**ADIM 14–20 yok**. Unified-clock orada *"ürün kararı gerektirir, bu denetimin kapsamı
dışında"* diye kayıtlı. **Uydurulmadı** — kaldırma şartları bunun yerine decision record
**§6**'da **altı somut, denetlenebilir madde** olarak yazıldı. Gate repoda tanımlanınca
§6'yı **referans almalı, değiştirmemeli.**

**3) Ekran okuyucu denetimi (GitHub #514) hâlâ açık**; **D-10** imza-mavisi (45 düğüm) kalıcı
imzalı sapma sürüyor, **WCAG 2.2 AA 1.4.3 karşılanmıyor.**

### Kapanış kaydının zamanlaması (dürüst not)

Bu kayıt geç yazıldı: **#520 (`6c46c03`) merge olduktan sonra main #521 (`a570934`) ve onun
kapanış kaydı #522 (`b5d524d`) ile ilerlemişti.** Bu yüzden ADIM 3 kaydı, sonradan eklenen
**G-02 (#521) kaydının ÖNÜNE** yerleştirildi — dosyadaki sıra merge sırasıdır.

## ESP export contract v2 — G-02 / ESP-19 kapatıldı (PR #521)

**Base SHA:** `6c46c039ebf9f3eaa58c6f34bddb74d2ad86d073` (`6c46c03`, #520 merge'ü) ·
**Merge SHA:** `a570934` · **Tarih:** 2026-08-03 · **Migration YOK** (şema değişmedi; alembic
head `0043_i08_registry_strategy_fks`, tek head) · **`ENGINE_VERSION` DEĞİŞMEDİ** (motor ve
sayısal semantik hiç dokunulmadı) · **OpenAPI:** 1 yeni schema + 1 operation body `$ref`,
**operation sayısı değişmedi** (196).

### Reproduction — önce kusur üretildi

Kod yazılmadan önce `origin/main` @ `6c46c03` üzerinde geçici probe testi:

```
embedded_resolver_contract          -> VAR (contract_id, runtime_adapter=pine_v5, evidence)
embedded_resolver_validation_run    -> VAR (status=passed, vectors_run=1)
manifest omits ['export_schema_version', 'exporter_version',
                'resolver_contract_snapshot', 'validation_evidence_snapshot']
```

Yani olgular veritabanında **mevcuttu**; manifest yalnız `package_revision`'dan kuruluyordu.
Doc 09 §15 **ESP-19** ("root/revision identity, content hash, signature, adapter ref,
evidence and dependency manifest") ve doc 09 §14 ("adapter ref, test evidence manifest")
karşılanmıyordu — dışa aktarılmış bir ESP, hangi runtime/timing semantiğiyle doğrulandığını
söyleyemiyordu. Probe ağaçta bırakılmadı; kalıcı regresyon kapısı
`test_esp_export_contract_v2.py::test_esp_export_v2_carries_contract_adapter_and_validation_evidence`.

### Ne landed

**Yeni saf düzlem:** `backend/src/entropia/domain/package/export_contract.py` (I/O yok, session
yok) — `EXPORT_SCHEMA_VERSION = 2`, `EXPORTER_VERSION`, `SUPPORTED_IMPORT_SCHEMA_VERSIONS`,
`build_resolver_contract_snapshot` / `build_validation_evidence_snapshot` /
`build_registry_observation` / `resolve_import_schema_version` /
`describe_origin_resolver_contract`.

**Manifest v2 alanları** (`commands/package_lifecycle.py::export_package`):

| Alan | İçerik |
|---|---|
| `export_schema_version` | `2` — artifact'in ŞEKLİ |
| `exporter_version` | `"entropia-package-exporter-v2"` — ÜRETEN |
| `resolver_contract_snapshot` | `contract_id`, `canonical_key`, `signature`, `runtime_adapter`, `warm_up_period`, `timing_semantics`, `repaint`, `evidence`. **`created_at` bilerek YOK** — satır-doğum damgası, contract olgusu değil |
| `validation_evidence_snapshot` | `evidence_state`, `validation_run_id`, `validator_version`, `status`, `vectors_run`, `checks`, `completed_at` + revision'ın KENDİ `revision_validation_state`/`revision_approval_state`'i **ayrı alanlarda** |

**Kanıt yoksa `legacy_incomplete_evidence`, `status: null` — `passed` ASLA uydurulmaz.** En
tehlikeli vaka bilerek test edildi: revision `passed` okuyup hiç run satırı olmayabilir
(R8 öncesi legacy aktivasyon); artifact bunu doğrulayıcı-sertifikalı kanıt diye sunmaz,
revision'ın kendi durumunu kendi adıyla ayrı raporlar (doc 09 §7).

**Canlı registry immutable contract'tan AYRILDI.** ESP registry pointer'ı manifest'in İÇİNDE
değil, zarfın kardeşi `registry_observation` (`canonical_key`, `trust_state`,
`trusted_active_revision_id`, `registry_version`, `runtime_adapter`,
`is_trusted_active_revision`). İki sonucu var: (1) `ta.sma` deprecate edilince aynı
revision'ın yeniden export'u **birebir aynı `manifest_hash`**'i verir; (2) yabancı registry
state'i import'ta hiç seyahat etmez — importer kendi registry'sinde yeniden çözmek zorunda.

**Her iki snapshot da EXPORT EDİLEN revision'ın satırlarından okunur**, kökün head'inden asla.
Head ileri alındığında eski revision'ın export'u değişmez; contract taşımayan yeni head
`null` döner, selefinin contract'ını ödünç almaz.

**Import v1/v2** (`commands/package_import.py` + `jobs/package_import.py`): alan yok veya
`null` → v1 (bu artifact'lar alandan eski); `1`/`2` (int veya digit-string) → o versiyon;
başka her şey (`3`, `99`, `0`, `-1`, `"next"`, `"2.0"`, `""`, `true`, `[2]`, `{...}`) →
**iki katmanda fail-closed**: API sınırında 422 (durable job açılmadan, `_coerce_kind`'dan
ÖNCE) ve worker'da terminal `failed` (`unsupported_export_schema_version`, kuyruğa başka
yoldan ulaşmış payload için defence in depth). `true` bilerek listede — naif `raw in {1,2}`
Python'da `True == 1` olduğu için onu kabul ederdi.

**Hata kodu — kanonik boşlukta uydurma YOK.** Doc 08 §11 okunamayan şema versiyonu için kod
adlandırmıyor; yeni taksonomi girdisi icat edilmedi, sevk edilmiş
`PACKAGE_IMPORT_MANIFEST_INVALID` yeniden kullanıldı (sınıfın kendi tanımı zaten
"structurally unusable at the API boundary").

**Trust sınırı:** v2 manifestin `resolver_contract_snapshot`'ı import raporuna
`diagnostics.origin_resolver_contract` olarak **`trusted: false` +
`local_revalidation_required: true`** damgasıyla yankılanır. `embedded_resolver_contract`
satırı YAZILMAZ, `embedded_resolver_registry` pointer'ı YAZILMAZ (before/after satır
sayımıyla kanıtlı), paket DRAFT/PENDING kalır. Dosya import etmek trusted resolver basmanın
yolu değildir.

**`get_latest_validation_run` sıralaması TOTAL yapıldı** (`created_at DESC, run_id DESC`).
`created_at` = `server_default=func.now()` = PostgreSQL'de *transaction* timestamp; tek tx'te
insert edilen iki run tam eşitleniyordu ve çıplak `ORDER BY created_at DESC LIMIT 1` satırı
planlayıcının insafına bırakıyordu — content-addressed bir manifest'in içinde yazı-tura.
`run_id` (`new_id`: sabit genişlikli base32 zaman damgası + rastgele) benzersiz ve
leksikografik sıralanabilir.

**Route sözleşmesi yayımlandı:** `POST /library/{entity_id}/export` artık
`dict[str, Any]` değil **`PackageExportResponse`** döndürüyor. `dict` dönüşü gövdeyi
`docs/openapi.json`'dan gizlerken drift guard'ı yeşil tutuyordu — O-30'un purge 202 için
kapattığı tuzağın aynısı. `manifest` bilerek açık `dict` bırakıldı: versiyonlu,
content-addressed bir artifact'i kapalı modele dondurmak her şema bump'ını API kırığı yapardı.

**Pre-G-02 Idempotency-Key replay'i:** `_with_export_envelope_defaults` **kopya üzerinde**
`export_schema_version: 1` + `registry_observation: null` doldurur; saklı `response_ref`
JSONB'si mutate EDİLMEZ ve manifest **verbatim** döner — içine versiyon alanı geri-doldurmak
audit'in çoktan kaydettiği `manifest_hash`'i geçersiz kılardı (O-30 kalıbı).

### Adversarial review — iki fazla-iddia ampirik olarak çürütüldü

Read-only bir adversarial review, dokümantasyonumun determinizmi **fazla iddia ettiğini**
buldu. İki geçici probe testiyle doğruladım ve iddiayı **dört dosyada daralttım**:

| Bulgu | Probe sonucu | Aksiyon |
|---|---|---|
| `get_latest_validation_run` append-only kümeden seçiyor → yeniden validate hash'i değiştiriyor | `HASH_EQ=False`, iki farklı `run_id` | Sıralama total yapıldı; **"en yeni" semantiği KORUNDU** — `run_resolver_validation` en yeni run'ın status'unu `revision.validation_state`'e kopyalar, eski bir run'ı pinlemek sistemin `failed` saydığı revision'a `passed` reklamı yaptırırdı. Davranış artık test edilmiş kasıtlı sınır |
| `validation_state`/`approval_state` yerinde mutate ediliyor → hash'lenen alanlar "immutable" değil | `draft → approved`, `HASH_EQ=False` | Alanlar korundu (ESP-19 evidence gereği); dokümantasyon daraltıldı |

**Doğru cümle (dört dosyada):** artifact, bir revision'ın *export anındaki sertifikalı
durumunun* content-addressed anlık görüntüsüdür — export-zamanı saatinden ve canlı
registry'den bağımsız, ama revision'ın kendi lifecycle ilerleyişinden bağımsız **DEĞİL**.

Review ayrıca **test zayıflıkları** buldu ve hepsi düzeltildi: determinizm testi slice revert
edilse de geçerdi (artık v2 alanlarının hash preimage'ında olduğunu **önce** assert ediyor);
tamper testi SHA-256'nın özelliğini test ediyordu (artık hash **sınırını** test ediyor —
contract+evidence içeride, registry observation dışarıda); `PackageRoot` sayımı vakumdu
(`submit_package_import` hiçbir girdide root yaratmaz → `PackageImportJob`/`Job`); "only"
iddiası key-set assert etmiyordu (artık exact delta); legacy replay testi private fonksiyon
çağırıyordu (artık gerçek `idempotency_keys` satırı planlanıp gerçek yoldan replay ediliyor).

Review'un **doğruladığı ve dokunulmayan** iddialar: fail-closed import (bypass bulunamadı —
sınır `run_idempotent`'tan önce, worker `_manifest_defect`'in ilk kontrolü, tek dispatch
yüzeyi), trust minting yok, O-13 fingerprint kuralı iki tarafta da temiz, non-ESP
değişmezliği, `legacy_incomplete_evidence` (hiçbir yoldan `passed` sızmıyor).

### Dürüst sınırlar

1. **Digest revision ömrü boyunca DONMUŞ değildir.** Yeniden validate yeni bir run ekler
   (evidence snapshot en yeniyi izler) ve approve geçişi `approval_state`'i hareket ettirir.
   İkisi de test edilmiş kasıtlı davranış; `validation_run_id` hangi kanıtın digest'i
   desteklediğini adlandırır, artifact asla belirsiz değildir.
2. **v1 ve v2 hash'leri karşılaştırılmaz.** Aynı revision'ın iki şekli farklı hash üretir —
   versiyonlamanın sebebi budur. Kayıtlı v1 hash'leri kapsadıkları v1 artifact için geçerli
   kalır.
3. **Sistem GÖNDERİLEN bir `manifest_hash`'i asla doğrulamaz.** `submit_package_import` kendi
   digest'ini hesaplar ve hiçbir şeyle karşılaştırmaz — bilinçli: import gelen hash'e
   güvenmek yerine yerelde yeniden çözer. "Tamper detection" bir sistem davranışı değil,
   digest'in bağımsız kopyasını tutan dış okuyucuya açık bir özelliktir.
4. **Açık `null` versiyon v1 okunur.** JSON `null` değerin yokluğudur, bilinmeyen bir gelecek
   versiyon değil; alan-yok ile aynı davranır (test edildi).

### Testler

Yeni: `tests/integration/test_esp_export_contract_v2.py` (**13**) — ESP-19 tam alan
sadakati (DB satırlarına karşı) · audit metadata (`export_schema_version` + `exporter_version`)
· iki bağımsız export determinizmi · yeniden validate yeni artifact üretir ve run'ını adlandırır
· approve geçişi digest'i hareket ettirir · head move eski revision'ı yeniden yorumlamaz ·
registry deprecate hash'i bozmaz · hash preimage sınırı · `legacy_incomplete_evidence`
(passed-ama-run-yok vakası dahil) · pre-G-02 replay (gerçek `idempotency_keys` satırıyla) ·
non-ESP exact key-set delta.

Yeni: `tests/integration/test_package_import_schema_v2.py` (**18**) — v1 (versiyonsuz +
açık `1`) · açık `null` · v2 yerel resolver'a yeniden pinler (manifest `pine_v5`, yerel güven
`python`) · untrusted origin echo + satır sayımları · çözülemeyen adapter → BLOCKED · 10
reddedilen versiyon (`true == 1` tuzağı dahil) · worker defence in depth · **end-to-end
round trip** (gerçekten trusted bir ESP'nin gerçek artifact'i geri import edilir).

Hizalanan: `test_acceptance_esp_package_gaps.py::test_esp_revision_export_carries_identity_hash_and_dependency_manifest`
**PARTIAL → FULL** (ESP-19'un her cümlesi assert ediliyor).

**Ölçümler:** backend tam suite **exit 0 — 2974 passed**, 0 failed/skipped/error, coverage
**%92.47** (kapı ≥90) · frontend **680 passed** (67 dosya), `npm run coverage` exit 0 ·
`ruff` + `ruff format --check` + `mypy src` (380 dosya) temiz · OpenAPI drift guard temiz ·
**CI 6/6 pass** (Backend 32m39s, iki E2E dahil).

### Dokümantasyon

Yeni: **`docs/audit/esp_export_schema_v2.md`** — v1↔v2 uyumluluk matrisi (alan alan), versiyon
kabul kuralı tablosu, v2 şeması, determinizm bölümü (§4.1 garanti edilen / §4.2 edilmeyen /
§4.3 kanıtlayan testler), trust sınırı tablosu, değişen/değişmeyen yüzeyler.

Güncellendi: `docs/audit/current_main_ground_truth_2026-08-03.md` §G-02 **CLOSED** + §18 sıra 3
LANDED · `docs/audit/acceptance_id_map.md` ESP-19 satırı + §E.4 **CLOSED** ·
`docs/CODEMAPS/BACKEND_ROUTES.md` · `BACKEND_LAYERS.md` · `FRONTEND_MAP.md`.

### Frontend

`lib/library.ts`: `RegistryObservation` tipi + `ExportPackageResult`'a
`export_schema_version` + `registry_observation`. Route, `useExportPackage` hook'u,
`Idempotency-Key` üretimi, `["audit"]` invalidation'ı **değişmedi**. `manifest` bilerek açık
`Record<string, unknown>` kaldı. `pages/Library.tsx`: şema versiyonu satırı + **ayrı**
`registry_observation` bloğu (canlı state artifact bloğunun dışında, "not part of the
artifact" etiketiyle) + artifact `<pre>`'sine `aria-label="Export manifest artifact"`
(test kapsamlama için, CLAUDE.md'nin sanctioned mekanizması).

---

## ADIM 8 — Yüksek riskli API sözleşmelerini typed hale getirme (PR #529)

**Base `870cc1a` → commit `62705ec` → merge `8a87460`** · 2026-08-04 · **Migration YOK**
(alembic head `0043_i08_registry_strategy_fks` sabit, tek head) · **`ENGINE_VERSION`
DEĞİŞMEDİ** · **OpenAPI: 30 yeni schema, 0 kaldırılan, operation sayısı 196'da sabit.**

### Kusur, kod yazılmadan önce üretildi

ADIM 2–7 ile değişen 16 public 2xx gövdesi `dict[str, Any]` dönüyordu. Bu, gövdeyi
`docs/openapi.json`'dan **görünmez** tutarken drift guard'ı yeşil bırakıyor — O-30'un purge
202 için, G-02'nin package export için kapattığı **aynı tuzak**. Frontend'in bağlanacağı bir
sözleşme yoktu.

### Landed

Yeni `apps/api/schemas/` paketi (`common` · `esp` · `library` · `agent_tool_gateway`); 16 uç
`response_model` aldı. **Wire byte'ları değişmedi** — her model bir serializer'ı anahtar-anahtar
aynalıyor. Handler'lar `dict[str, Any]` dönmeye devam ediyor (sevk edilmiş kalıp:
`trash.py::PurgeAcceptedResponse`), böylece serileştirmeden ÖNCE çalışan route-içi subscript'ler
korunuyor: iki ETag için `int(detail["row_version"])` ve broker devri için
`dispatch_create_package_job(result["job_id"])`.

`PackageExportResponse` + `PackageValidationRunAcceptedResponse`, `routes/library.py`'den
`schemas/library.py`'ye **aynı sınıf adlarıyla** taşındı → yayımlanan component anahtarı kaymadı.
Modeller route modülünde değil ayrı pakette: o modüller kendini "thin handler" ilan ediyor ve
~40 model inline `routes/library.py`'yi 550+ satıra çıkarırdı. `routes/trash.py`'deki üçüncü
inline model kapsam dışı olduğu için yerinde bırakıldı.

### Üç bağlayıcı kural

**Her alan REQUIRED, nullability TİPTE** (`x: str | None`, default YOK) — `= None` default'u,
asla atlanmayan bir anahtarı "atlanabilir" diye reklam eder. 17 üst düzey + 14 iç component
için test edildi.

**Enum'lar `string` olarak yayımlanır, kapalı enum olarak DEĞİL.** Serializer'lar zaten
lowercase `StrEnum` değerini `str(x)` ile basıyor. Bir RESPONSE'ta kapalı enum, sunucunun
meşru ürettiği bir değeri istemci tarafı doğrulama hatasına — ve `response_model` çıkışta
doğruladığı için önce **500**'e — çevirir.

**Zaman damgaları `string`, `format: date-time` DEĞİL.** Serializer'lar `.isoformat()`
basıyor; `datetime` alanı değeri yeniden render ederdi.

Bu iki kural **hand-list ile değil**, 2xx gövdesinden geçişli olarak erişilebilen HER
component üzerinde **blanket walk** ile sınanıyor — el listesi tam da bir sonraki eklenen alanı
kapsamayı bırakan şeydir. Ayrı bir test walk'un boş dönmediğini kanıtlıyor.

**Aynı ad ≠ aynı model.** `checks` validate komutunda **liste**, detay okumasında saklı rapor
**dict**'i; `rationale_family` list satırında 2, detayda 4 anahtar. `ActivateResolverResponse`
ve `DeprecateResolverResponse` de ayrı kaldı (biri `revision_id`, diğeri
`replacement_revision_id` taşır). Birleştirmek her iki tarafı da optional yapardı.
`LibraryPackageDetailResponse` ile `LibraryPackageRow` ortak bir private taban paylaşıyor
(`_LibraryPackageFields`) — mypy strict, alt sınıfta alan tipi daraltmayı Liskov ihlali sayıyor.

### Bilerek AÇIK bırakılanlar

Export `manifest`'i (sürümlü artifact, `POST /package-imports`'a **aynen** geri gönderiliyor —
düşen alan import artifact'ini sessizce bozar), çağıran-yazımı JSONB sözleşmeler, ve gateway'in
`request`/`response_ref`'i. Sonuncusu `tool_name` ile 33 tool üzerinde ayrışıyor, arkasındaki
komutun dönüşünü aynen saklıyor (Strategy/Trading Signal parity sonuçları dahil) ve üç yönlü
birleşim: `succeeded`'da tool'un payload'ı (**`status` anahtarı YOK** — kardeş kolonu oku),
`rejected`'da `{status, reason_code, reason}`, `failed`'da
`{status, failure_code, failure_reason, details}`. Kapalı bir union her registry eklemesinde
yeniden kesilmeliydi. **Gateway ZARFI tam tipli; yalnız tool payload'ı açık.**
`permissions` ise tersine kapalı (11 adlı bool) — düşen bir bayrak UI eylemini **sessizce
gizler**; test `dataclasses.fields(PackagePermissions)`'a karşı sabitliyor.

**Enqueue'nun HTTP yüzeyi YOK.** `dispatch_tool_call`/`enqueue_tool_call` worker düzlemi;
`apps/api/routes/` altında `agent_tools`'u import eden modül yok. Gateway'in public sözleşmesi
iki history okumasıdır.

### Landing'i engelleyen ve düzeltilen kusur

`POST /package-imports`, çağıranın manifest'ini JSONB `rationale_family_snapshot`'a yalnız
kap-seviyesi `isinstance(dict)` kapısıyla yazıyor (`jobs/package_import.py:210`).
`_pinned_family`/`_live_family` ise id'yi **çıplak truthiness** ile eliyor, `display_name`'i ham
geçiriyordu. `{"rationale_family_id": 7, "display_name": 42}` içeren bir import eskiden çöp
render ediyordu; `PinnedRationaleFamilyRef` altında **tüm `GET /library` sayfası için 500**
olurdu — tek alan için değil. `_snapshot_family_id` artık boş-olmayan **string** id istiyor
(string olmayan bir id family referansı değildir), `_snapshot_display_name` string olmayan adı
düşürüyor (`42`'yi ad diye basmak sistemin hiç atamadığı bir etiket uydurmaktır). Kapı ayrıca
id `rationale_repo.get_family_root`'a **ulaşmadan** çalışıyor — oraya string olmayan bir arama
anahtarı gidiyordu. Modülün kendi emsali izlendi (`_package_name` isinstance eler,
`_output_kinds`/`derive_catalog_scope` `str()` ile zorlar). Geçerli veri birebir aynı. Yazma
yolu bilerek dokunulmadı: `POST /package-imports`'u keyfi manifest içeriğine karşı sertleştirmek
ayrı bir slice'tır, projeksiyon **zaten saklanana rağmen** güvenli olmalıdır.

### Frontend wire parity artık makine kontrollü

`tests/contract/test_wire_contract_parity.py` OpenAPI ↔ `frontend/src/lib/*.ts` karşılaştırmasını
alan alan + nullability ile yapıyor (27 çift), mevcut F-05 capability-matrix aynası
(`tests/unit/test_capability_matrix.py`) üslubunda. `main` üzerinde **dört sapma** buldu:

| Sapma | Yön | Düzeltme |
|---|---|---|
| `EspPackageDetail` `latest_validation_run`'ı hiç bildirmemiş | istemci **R8'den beri** gönderilen alana kör | alan + `EspValidationRunSummary` eklendi |
| `EspPackageDetail.lifecycle_state: string` | TS sunucudan **dar** (kolon nullable) — gizli runtime hatası | `string \| null` |
| `LibraryPackageRow.lifecycle_state: string` | aynı | `string \| null` |
| `ProvenanceScan.registry_fingerprint`/`context_hash` | TS **geniş** (kolonlar NOT NULL) — ölü dal | `string` |

İki genişletme üç render noktasını null-güvensiz yaptı; `lifecycleTone` artık `string | null`
alıyor ve etiketler `UNSTATED_LIFECYCLE_LABEL` (`"unstated"`) ile düşüyor — **asla uydurma
`"active"`**. Route path, react-query key, hook, OCC token, `Idempotency-Key`, SSE eşlemesi ve
`lib/*.ts` veri mantığı **dokunulmadı**.

### Testler

`test_typed_contract_no_field_drop.py` (17) — her model **kendisini besleyen gerçek
serializer**'a karşı sabitlendi (ORM stub'ları üzerinde saf fonksiyonlar, DB yok).
`test_typed_contract_openapi.py` (11) · `test_wire_contract_parity.py` (27 çift) ·
`test_typed_contract_replay_parity.py` (16).

**Kritik teknik:** integration modülü HTTP gövdesini **saklı idempotency zarfıyla**
karşılaştırıyor. `run_idempotent` komutun dönüşünü aynen saklıyor, yani saklı dict route'un
FastAPI'ye verdiği dict'tir — `body == stored` tek hamlede hem drop'u hem fazladan alanı
çürütüyor **ve** replay'in aynı DTO'dan geçtiğini yapısal olarak kanıtlıyor. Saklı zarfı
olmayan `validation-runs` için komut **spy**'lanıyor; onu el yazımı bir anahtar kümesine karşı
sabitlemek (mevcut route testinin yaptığı) modelle inşaen anlaşır ve komut dokuzuncu bir
anahtar kazansa yeşil kalırdı. `deprecate`'in replay'i HTTP'den **erişilemez** — lifecycle
guard'ı `run_idempotent`'ın dışında, ikinci çağrı idempotency'e bakılmadan 409.

**İki eski fixture yeniden hizalandı:** `tests/contract/test_library_contract.py` list ve
detail sorgularını `{"entity_id": "pkg_1"}` ile taklit ediyordu — projeksiyonun asla
üretmediği bir şekil. Tipli sözleşmede bu 500'dür ve doğru sonuç budur: sunucunun
üretemeyeceği bir gövdeyi assert eden contract testi hiçbir şey test etmiyordu. Stub'lar artık
`_package_row`'u anahtar-anahtar aynalıyor; testlerin gerçekte kontrol ettiği şey
(filtre alias'ları, ETag) değişmedi.

**Ölçüm:** backend **3143 passed / 0 failed / 0 skipped**, coverage **%92.81** (kapı ≥90),
exit 0 · frontend **696 passed**, `tsc -b --noEmit` temiz, eslint 0 error, `npm run coverage`
exit 0 · `ruff` + `ruff format --check` + `mypy src` (385 dosya) temiz · OpenAPI drift guard
temiz · **CI 6/6 pass** (Backend 44m18s).

### Uyumluluk

Breaking removal/rename/optional-yapma **yok** → alias veya deprecation penceresi gerekmedi.
`registry_observation` tiplendi (`PackageRegistryObservation`) ve `required` oldu — **response
tightening**, istemciye kesinlikle daha fazla garanti; anahtar zaten hep vardı çünkü
`_with_export_envelope_defaults` pre-G-02 replay'de backfill ediyor (testle sabitlendi).
`PackageValidationRunAcceptedResponse`'ta yalnız description değişti (model modül değiştirdi),
properties ve `required` birebir aynı. `ErrorBody`/`ErrorResponse`, 201/202 statüleri, OCC
token'ları ve `Idempotency-Key` dokunulmadı.

### Yöntem notu

Adversarial read-only review **iki gerçek kusur** buldu ve ikisi de düzeltildi: yukarıdaki
poisoned-snapshot 500'ü, ve `PackageValidationRunAcceptedResponse`'ın çalışma zamanı bağı
olmayan tek model olması. Review ayrıca sekiz zayıf/totolojik assertion işaretledi
(`set(x) == set(x)` biçimleri, fixture'ın kendisini okuyan `isinstance`, `list[X]` için de geçen
`is not list`) — hepsi gerçek kontrollerle değiştirildi. **Bir hata kendi ayağıma dolandı:**
`npx prettier --write` çalıştırdım; bu repoda prettier config'i, script'i ve bağımlılığı
**yok**, dolayısıyla beş frontend dosyası baştan aşağı yeniden biçimlendi (~700 satır ilgisiz
churn). Dosyalar commit'lenmiş içerikten yeniden kuruldu; nihai frontend diff'i **62 ekleme /
9 silme**.

### Dokümantasyon

Yeni: **`docs/audit/high_risk_api_contract_audit.md`** — 18 uçluk denetim tablosu
(method/path/request/gövde/replay/hata/frontend/OpenAPI), OpenAPI before/after, uyumluluk
matrisi, açık-bırakılan alanlar gerekçeleriyle, kalan risk. Güncellendi:
`docs/CODEMAPS/BACKEND_ROUTES.md` (satır numaraları + `response_model` sütunu + gateway'in
enqueue-route'u-yok notu) · `docs/CODEMAPS/FRONTEND_MAP.md`.

### Deferred (bilerek)

`GET /library-shared-with-me` (`routes/sharing.py`) birebir aynı `LibraryPage` zarfını
döndürüyor ve hâlâ tipsiz — kapsam dışı; `LibraryPageResponse` onun için olduğu gibi
kullanılabilir. API'nin geri kalanındaki ~161 `dict[str, Any]` route dönüşü **dokunulmadı**;
bu slice bilerek repo çapında bir DTO rewrite değildir.

---

## ADIM 9 / ADIM 10 — kayıt boşluğu (dürüst not)

Bu iki slice `main`'e indi ama **PROJECT_HISTORY'ye yazılmadı**. Ayrıntı için kaynaklarına
git, buradan tahmin etme:

* **ADIM 9 — PR #531** `test(acceptance): replace ID hits with semantic evidence mapping`
  (merged 2026-08-04T09:44Z, commit `e36f082`).
* **ADIM 10 — PR #537** `docs(audit): close the Strategy conflict matrix evidence chain`
  (merged 2026-08-04T11:28Z, commit `e4cbec0`). Tam kaydı kendi dokümanında:
  **`docs/audit/strategy_conflict_matrix_closure.md`**. Bulguları issue #532–#536 olarak
  açıldı; #535 (product decision) ve #536 hâlâ açık.

---

## ADIM 11 — Capability matrix canonical adjudication (PR #538)

**Base:** `origin/main` @ `53c28de` · **merged** 2026-08-04T12:35Z → `061d6d7` · CI **6/6 pass**
(Backend 47m22s) · **audit-only, tek dosya, +443 satır, kod/şema/migration/OpenAPI/codemap
değişikliği YOK.**

Yeni: **`docs/audit/capability_matrix_canonical_adjudication.md`**.

### Ne yapıldı

Engine capability matrisinin (**62 satır / 22 `future_dev` / 14 alan**) her `future_dev`
satırı V18 kanonuna karşı hükme bağlandı: gerçek data/model/determinism engeli olanlar ile
**kanonun hiç tanımlamadığı** ya da **ürün kararı bekleyen** olanlar ayrıştırıldı. Yöntem:
kanonik okuma → statik çağrı zinciri → **gerçek engine/Pydantic/form modülleri üzerinde
çalıştırılan probe** → test envanteri. Dört read-only subagent kanıt üretti; disposition
değiştiren her iddia ana oturumda yeniden ölçüldü ve **üç subagent sonucu geçersiz kılındı**.

### Disposition (22 satır)

`canonical_gap` **16** · `product_decision_required` **3** · `keep_future_dev` **2** ·
`eligible_for_implementation` **1** · `incorrect_current_status` **0**.

**Hiçbir capability aktif edilmedi.** `incorrect_current_status` en sert biçimde sekiz
tick-bağımlı `active_v1` satırına karşı test edildi ("gizli Future Dev mi?") ve **ölçümle
çürütüldü** — partial fill `size=20` vs `50`; intrabar touch print otoritesiyle bar
modelinin aldığı bir fill'i *kaldırıyor*; stop/limit priority bir bar gecikmesini kapatıyor.
Statü alanı her yerde dürüst; yanlış olan **kayıtlı gerekçeler** ve **kullanıcıya gösterilen
iddialar**.

### On kusur

| # | Kusur | Şiddet |
|---|---|---|
| D-1 | 22 `future_dev` satırının **11'i** formda sıradan, seçilebilir seçenek olarak render ediliyor — `StrategyGraphForm.tsx` generated matrix'i hiç import etmiyor (`capabilityField`: `StrategyConfigForm` 12, burada **0**) | **CRITICAL** |
| D-2 | Exhaustiveness guard matrisin **14 alanından 9'unu** kapsıyor; kapsanmayan 3 alanda zaten `future_dev` satırı var | **HIGH** |
| D-3 | 6 alan diagnostics provenance bloğunda yok (#534 ailesi) | MEDIUM |
| D-4 | Restriction **action** uzayı kanonik, doğru şekilde fail-closed, ama matriste **alanı yok** → run atıl iken `capability_not_in_build` boş | MEDIUM |
| D-5 | `strategyGraph.ts:93-95` var olmayan bir disable iddia ediyor | MEDIUM |
| D-6 | `MODELLED_FILTER_TYPES` parity testi olmayan elle bakımlı kopya | MEDIUM |
| D-7 | `increasing_by_layer`'ın kayıtlı gerekçesi **kanon tarafından yalanlanıyor**; scaling-timeframe'inki replay'in yapamadığını **abartıyor** | **HIGH** |
| D-8 | Kanonik `FORMULA_AST_INVALID` (doc 02 `:2394`) hiç emit edilmiyor | LOW |
| D-9 | `signal_strength_adjustment`'ın 4 literal'inden 3'ü — **sevk edilmiş `active_v1` olan `volatility_adjusted` dahil** — hiçbir kanonik belgede yok | **HIGH** |
| D-10 | `correlation_filter` şemada var kanonda yok; `regime_filter` kanonda var şemada yok | **HIGH** |

### Hareket eden tek satır

`scaling_logic.timeframe_mode = increasing_by_layer` → `eligible_for_implementation`.
Matris "doc 02 §5.7 rung boyunu söylemiyor" diyor; **§5.7 için doğru, doc 02 için yanlış** —
§6.1 ⓘ paneli (`02_..._v1_1.md:1998`) *"her yeni layer'da … bir üst timeframe'e geçer"*
diyor, `15m → 30m → 1h` örneğiyle, `CANONICAL_TIMEFRAMES` index+1 ile örtüşüyor. Mekanizma
S5c'den beri sevk edilmiş (`layer_timeframe`/`layer_bucket`). **Aktif edilmedi** — `1D` üstü
davranış açık ürün kararı.

### NET — matrisin dışında

`NET` capability matrisi satırı **değil**; `CrossItemConflictPolicy.NET`
(`domain/allocation/enums.py:35-52`) allocation yüzeyinde. Kanon hiçbir policy seti
saymıyor ve doc 13'ün kendi draft-write sözleşmesi (`:816`) `conflict_policy` alanını hiç
taşımıyor. Dahası **açıklaması karşı-olgusal**: ADIM 3 containment'ından sonra hiçbir shared
run kabul edilmiyor, ama uyarı ve tarayıcı etiketi hâlâ *"executed as Block opposite"*
reklamı yapıyor (ölçüldü: `BLOCKER SHARED_MODE_NOT_IN_BUILD` + `WARNING
CONFLICT_POLICY_NET_V1` aynı config'te birlikte).

### Doğrulama

Backend targeted **271 passed** + allocation **18 passed** + frontend **14 passed** — hepsi
exit 0. Generator temp path'e yeniden üretilip diff'lendi: **byte-identical** (sha256
eşleşti, tracked dosyaya yazılmadı). Doküman referansları 14/14 çözüldü. Tam suite
koşulmadı — PR hiç kod değiştirmiyor.

### Açılan issue'lar

| Issue | İçerik |
|---|---|
| #539 | **C-1 (CRITICAL)** — matrix'i `StrategyGraphForm`'a bağla, reachability'ye göre gate'le, `MODELLED_FILTER_TYPES`'ı sil |
| #540 | C-2 — exhaustiveness guard'ı 14/14'e çıkar |
| #541 | C-3 — iki yanlış gerekçe + bayat yorum (text-only) |
| #542 | **P-1 ürün kararı** — signal-strength taksonomisi (aktif satırı da etkiliyor) |
| #543 | **P-2 ürün kararı** — `correlation_filter` mi `regime_filter` mi |
| #544 | **P-6 ürün kararı** — NET'i tanımla ya da kaldır (+ text-only açıklama düzeltmesi bağımsız yapılabilir) |
| #545 | P-3+P-4 ürün kararı — ikinci dataset pin'i + stale-quote eşiği |
| #546 | P-5+P-8 ürün kararı — hangi volatility/volume koşulları ship edilir + action uzayı matrise girsin mi |
| #547 | C-5 — `increasing_by_layer` implementasyonu (P-7'ye bağlı, `ENGINE_VERSION` değerlendirmesi zorunlu) |
| #534 | C-4 — provenance eksikleri, **yeni issue açılmadı**, mevcut issue'ya 6 alan eklendi |

### Devam belgeleri

Bir sonraki oturumun seed'i: **`docs/ADIM11_LANDED_KICKOFF.md`** (reuse
anchor'ları + paste-ready resume prompt). Handoff girdisi: `docs/STAGE2_HANDOFF.md`
§"ADIM 11 … landed".

### Dürüst sınır

D-1'in etkisi form modülleri üzerinde ölçüldü, **tarayıcıda değil** — insan ya da ekran
okuyucu oturumu yapılmadı. Sunucu tarafı (bu 11 satırın Ready Check + engine tarafından hâlâ
reddedildiği) doğrudan ölçüldü ve tutuyor. `_ReferenceSeries` resampler'ı **okundu,
koşturulmadı** — "scaling override'a hizmet edebilir" iddiası bilerek bir disposition'ı
gerekçelendirmek için KULLANILMADI.

---

## ADIM 12 — Bağımsız finansal oracle baseline'ı (PR #553)

**Base `061d6d7` → commit `b5c7c44`** · 2026-08-04 · **Migration YOK** (alembic head
`0043_i08_registry_strategy_fks` sabit, tek head) · **OpenAPI DEĞİŞMEDİ** (196 operation /
151 schema) · **`ENGINE_VERSION` DEĞİŞMEDİ** · **production kod DEĞİŞMEDİ** — 9 yeni test
dosyası + 1 audit dokümanı, 2181 satır, tamamı additive.

### Neden — mevcut iki koruma katmanının cevaplamadığı soru

Engine suite'i bugün iki şekilde korunuyor ve **ikisi de kalıyor**:

* **golden digest'ler** (`test_backtest_engine_golden.py` + `engine_golden_digests.json`) —
  *değişimi* yakalar, ama digest'i de güncelleyen bir değişiklik yeşil geçer;
* **helper unit testleri** (`test_backtest_costs.py`, `test_backtest_fills.py`, …) —
  beklentilerini `_effective_fill` / `_position_size` / `due_funding_charges` çağırarak
  kuruyor, yani o helper'larla **yapı gereği** anlaşıyorlar.

Hiçbiri şunu sormuyor: *engine'in ürettiği sayı, aritmetiğin söylediği sayı mı?* ADIM 12'nin
tek işi bu ölçüyü kurmak — ve bunu unified-clock değişikliğinden **önce** yapmak, ki yeni saat
neyi koruduğunu/neyi bilerek değiştirdiğini gösterebilsin.

### Landed

`backend/tests/unit/oracles/` — **79 senaryo** (78 passing, 1 `xfail(strict)`).

| modül | senaryo | eksen |
|---|---|---|
| `harness.py` | — | fixture kurucu; **hiçbir beklenen değer üretmez** |
| `test_oracle_entry_exit_timing.py` | 10 | current/next candle open-close, market fill, short mirror, gap-open no-lookahead, end-of-data, same-candle entry+exit |
| `test_oracle_costs.py` | 14 | spread, slippage, kompozisyon sırası, commission, short aynalar, funding işareti, event_time↔available_time |
| `test_oracle_orders.py` | 10 | limit touch/no-touch/convert-to-market/±offset, stop trigger, stop gap, short mirror |
| `test_oracle_protection_stops.py` | 13 + 1 xfail | percentage/absolute/trailing seviyeleri, aktivasyon eşiği, any↔all, most-conservative↔priority order, stop+exit çakışması ×4 |
| `test_oracle_sizing.py` | 13 | base, risk-based, tam/kesirli Kelly, negatif edge, min/max, leverage modları, allocation sleeve |
| `test_oracle_position_lifecycle.py` | 8 | partial close ×3 aftermath, komisyon dağılımı, scaling ladder ×3 basis, cap reddi |
| `test_oracle_properties.py` | 10 | PnL korunumu, equity kimliği, batch invariance, deterministik replay, disabled-config etkisizliği, restrictions, no-lookahead, MTF closed-bar |

### Üç bağlayıcı kural (paketin `__init__.py` docstring'inde)

**Beklenen değerler engine'den ÜRETİLMEZ.** Pakette `_effective_fill`, `_position_size`,
`_resolve_stop`, `due_funding_charges` gibi hiçbir aritmetik helper import edilmiyor; tek
production import `run_engine` + tükettiği tipli girdiler. Bir helper çağırıp beklenti kurmak,
testi implementasyonun aynası yapardı.

**Fixture 5–20 bar.** Ledger'ın tamamı elle denetlenebilir kalmalı; hesap docstring'de yazılı.
Ortak geometri: **20 düz bar @100** (20-bar SMA tam 100'e oturur, 20 kopyanın ortalaması
tartışmalı değil) → **bar 21** kesişir. Sinyal `validity="current_candle_only"` ile **EDGE**:
sadece kesişim barında canlı, sonraki barlar sessizce yeni giriş ateşleyip elle hesaplanmış
ledger'ı bozamaz.

**Spec'in sessiz olduğu yerde "canon böyle diyor" DENMEZ.** V18 canon icra aritmetiğinin
çoğunu bilerek engine manifest'ine bırakıyor (Master Ref §10.13). Oracle'lar bu alanlarda
**sevk edilmiş konvansiyonu** pinliyor ve modül docstring'inde bunu açıkça söylüyor:

| alan | spec durumu | pinlenen konvansiyon |
|---|---|---|
| timing seçeneği başına fill fiyatı | sadece enum, **fiyat eşlemesi YOK** | close / next open / next close |
| spread+slippage işareti ve sırası | **adverse-side kuralı YOK** | iki tarafta da aleyhte; önce spread, sonra yüzde |
| commission taraf başına mı round-trip mi | **belirtilmemiş** | tam kapanışta `commission × 2` |
| funding işareti | doc 02 "düşülür veya … eklenir" | long öder, short alır |
| limit/stop seviyesinden gap | **spec sessiz** | dokunulan limit kendi seviyesinden; stop girişi `max(trigger, open)` |
| tetiklenen stop'un icra fiyatı | **spec sessiz** (sadece trigger seviyesini sabitler) | seviyeden — kanıtlanabilir şekilde ulaşılamaz olan tek vaka #549 |
| varsayılan stop önceliği | **kanonik sıra YOK**; `priority_order` kullanıcı listesi | percentage → trailing → absolute |
| `most_conservative` karşılaştırıcısı | sadece niteliksel | en dar aleyhte mesafe, kanonik rank tie-break |
| Kelly | **spec'te hiç geçmiyor** | `f* = kf × (W − (1−W)/R)`, 0'da kırpılır |
| min position size | **spec'te hiç geçmiyor** | engine-only alan |

### Dört uyuşmazlık — açıldı, düzeltilmedi

Slice yapı gereği test-only; her düzeltme engine semantiğini değiştirir → `ENGINE_VERSION`
kararı + golden digest tazelemesi gerekir.

**#549 (high) — gap'le atlanan koruma stop'u ulaşılamayan seviyeden kayıt açıyor.**
`_resolve_stop` icra fiyatı olarak stop **seviyesini** koşulsuz döndürüyor
(`execution/fills.py:610`, `price=triggered[winner]`); `bar.open` ile hiç karşılaştırmıyor.
102'den long, %1 stop → 100.98. Bar 22 `(open 90, high 92, low 88, close 91)` — **tüm aralık
88–92**, yani 100.98 o barın hiçbir yerinde yok. Engine −51.00 yazıyor; ilk ulaşılabilir fiyat
(open, 90) −600.00 demek. Tek barda 549.00, ve **her** gap'li stop-out'ta, hep run'ın lehine.
Bunun bir konvansiyon değil kusur olduğunun kanıtı engine'in kendisinde: stop **GİRİŞİ** gap'le
atlandığında `max(trigger, open)` ile doluyor (`engine.py:307`, `fills.py:205`) — aynı geometri,
ters işaret, kural yok. Ve bu bir *yol* varsayımı değil: `open` sınır gerçeğidir, bar içi sıra
bilgisi değil. Aritmetik repo'da `xfail(strict=True)` olarak duruyor → engine düzeltilince
pass'e döner ve düzeltmeyi bu dosyaya bağlar.

**#550 (high / ürün kararı) — `base_position_size` birim adedi olarak yürütülüyor.**
`_raw_position_size` alanı birebir birim sayısı olarak döndürüyor. Canon aynı alanı "resolved
capital'in yüzdesi" diye tanımlıyor (Master Ref §10.1; doc 02 ⓘ + çalışılmış örnek "Equity
10.000 USD ve Position Size %10 → 1.000 USD nominal"), ve V18 mockup input'u inline `%` ekiyle
render ediyor (`index_guncellenmis_duzeltilmis_v18.html:5696`). Şema alanı birimsiz. İki okuma
enstrüman fiyatıyla **sınırsız** ayrışıyor: 10.000 fiyatlı bir enstrümanda `base_position_size
= 10` canon'a göre 1.000 USD nominal, sevk edilene göre **100.000 USD** — 10.000'lik hesapta
10× kaldıraç. Karar isteniyor, sessiz değişiklik değil: birim okuması şema/engine/frontend/~3100
test boyunca tutarlı, çevirmek `ENGINE_VERSION` + saklı revision migration'ı demek.

**#551 (medium) — `min > max` penceresi 0-size hayalet trade açıyor.** `_clamp_to_limits`
tatmin edilemez pencereyi `0`'a indiriyor ve kendi docstring'i `0`'ı "açma" sentinel'i diye
adlandırıyor; bar loop bunu onurlandırmıyor, pozisyonu 0 size ile açıp trade satırı yazıyor.
`total_trades` risk taşımamış bir pozisyonu sayıyor ve `close_position`'ın
`if pnl > 0 … else gross_loss` sınıflandırması 0-PnL'i **zarar** tarafına koyuyor. Engine'in
diğer fail-closed yollarıyla (unmodelled sizing, unmodelled leverage, sıfır sleeve — hepsi
`entry_blocked`) tutarsız.

**#552 (medium) — kısmi kapatılan pozisyon 1.4 komisyon round-trip ödüyor.**
`close_position`: `commission * 2 if is_full else commission * 2 * fraction`, docstring
iddiası "N kısmi lot toplamda tam bir round-trip öder". Bu yalnız pozisyon **tamamen** kısmi
lotlarla kapanırsa doğru. Normal şekil — bir kısmi kapatma, sonra kalanın tam kapanışı — daha
fazla ödüyor: 50 birim @102, komisyon 7 (round-trip 14.00), `close_percentage=40`,
aftermath `move_stop_to_entry` → kısmi lot 14.00×0.4 = 5.60 (pnl −65.60), kalan tam kapanış
14.00 (pnl −14.00). Toplam **19.60**, oysa pozisyonun **üç** fill'i var (bir giriş, iki çıkış):
ne 3×7 = 21.00, ne belgelenen 14.00. Yön olarak muhafazakâr (fazla tahsil), bu yüzden fark
edilmemiş — ama maliyet modeli config'ten yeniden üretilemez hale geliyor.

### Doğrulama

Hedefli: `pytest tests/unit/oracles -q` → **78 passed, 1 xfailed**. Full backend suite
**exit 0**, 0 FAILED/ERROR, coverage **%92.84** (kapı ≥90). `ruff check` + `ruff format --check`
temiz; `mypy src` temiz — yeni paket ayrıca **mypy-strict temiz** (CI yalnız `src` denetliyor,
paket yine de o çıtaya çekildi).

**Ortam tuzağı (kaydedilmeli):** `TEST_DATABASE_URL` sürücüsü **`postgresql+asyncpg://`**
olmalı. `postgresql+psycopg://` ile integration conftest'i `create_async_engine`'de patlıyor ve
**2319 ERROR** üretiyor — testlerle ilgisi yok, tamamen sürücü uyuşmazlığı. Suite lokalde
~35 dakika; **tek pytest çağrısında** koş.

### Dürüst sınır

Oracle'lar yalnız **single-item** engine'i kapsıyor. Unified clock üzerinde çok-item
ko-simülasyon, cross-currency FX ve tick/print icra modları (`intrabar_touch`,
`limit_fill_simulation`, `stop_limit_priority_simulation`, `not_allowed` dışı partial-fill)
kapsam DIŞI: ilk ikisi implemente değil, üçüncüsü pinli tick revision gerektiren farklı bir
fixture şekli. Partial-fill karar tablosu mevcut helper testleriyle korunmaya devam ediyor.

### Kapanış kararı

`docs/audit/backtest_oracle_fixtures.md` bu slice'ın kalıcı çıktısı: her fixture'ın el hesabı,
spec-open konvansiyon tablosu ve dört bulgunun künyesi orada. Bir sonraki oturum engine
aritmetiğine dokunuyorsa **önce onu okumalı** — hangi sayının kanon, hangisinin sevk edilmiş
konvansiyon olduğunu ayıran tek belge o.

---

## ADIM 13 — Research Data point-in-time ve Agent/Run parity (PR #560)

**Base `c610600` → commit `4110138`** · 2026-08-04 · **Migration YOK** (alembic head
`0043_i08_registry_strategy_fks` sabit) · **OpenAPI değişmedi** · **capability matrix
dokunulmadı** · **frontend HİÇ dokunulmadı**. `ENGINE_VERSION`'ı ADIM 13 değiştirmedi
(aynı gün paralel landed olan PR #555 değiştirdi — aşağıda).

### Soru ve yöntem

Bir Research Data revizyonu, Agent research bundle'ına Backtest execution bundle'ına
taşıdığı **aynı canonical point-in-time doğruluğunu** taşıyor mu? Dört ayrı kod parçası bir
revizyonu pinleyebiliyor, dolayısıyla parity varsayılamazdı:

| | yüzey | giriş noktası | erişim |
|---|---|---|---|
| A1 | Agent tool gateway | `jobs/agent_tools.py::_handle_data_bundle_resolve` | `data_bundle.resolve` tool |
| A2 | Agent bundle derleyici | `jobs/research_data.py::compile_agent_data_bundle` | `POST /research-datasets/bundles/agent` |
| B1 | Evidence bundle derleyici | `jobs/research_data.py::compile_backtest_evidence_bundle` | `POST /research-datasets/bundles/backtest-evidence` |
| B2 | Run manifest | `commands/backtest_run_context.py::_research_entries` | her `request_backtest_run` |

**A1 ve A2 aynı kavramın iki bağımsız implementasyonu** ve farklı kural setleri uyguluyor.
Yöntem: her kusur, yazılmadan **önce** `c610600` üzerinde gerçek veritabanına karşı bir probe
ile yeniden üretildi; kod okumasından çıkarılan hiçbir iddia bulgu sayılmadı.

### Dar üretim düzeltmesi (tek kalem, ortak time-policy katmanı)

`set_time_policy` yalnız sahipliği (`ensure_can_edit_draft` → owner/Admin) kontrol ediyordu,
revizyonun **durumunu** değil. Sonuç: APPROVED bir revizyonun `available_time_policy`,
`available_delay_seconds` ve kaynak zaman dilimi **yerinde** yeniden yazılabiliyordu.
`content_hash` yalnız payload byte'larını kapsadığı ve `application/queries/funding.py` bu
alanları koşu anında **canlı** okuduğu için, aynı revizyon id'sini pinleyen iki koşu farklı
`available_at` çözüp farklı funding maliyeti kitaplayabiliyordu — manifest snapshot'ı
birebir aynı görünürken.

Ampirik probe (düzeltmeden önce):

```
state=approved   before=(None, None)   after=(fixed_delay, 7200)
content_hash=b704109aaf…  (DEĞİŞMEDİ)
```

Canon: doc 12 §11 *"available-time policy change → new Research Dataset Revision. In-place
overwrite forbidden."* · §14 *"Approved v1.0 mutate edilmez; existing run/result v1.0'a bağlı
kalır."*

**Düzeltmenin tamamı:** `domain/research_data/time_policy.py` içine
`TIME_POLICY_FROZEN_STATES` (`approved` / `approval_revoked` / `deprecated`),
`time_policy_is_frozen` ve `ensure_time_policy_mutable` eklendi → **409 `LIFECYCLE_BLOCKED`**,
`field_path=available_time_policy`, `suggested_action=create_new_revision`,
`retryable=false`; okunamayan durum fail-closed FROZEN sayılır. Tek çağrı yeri:
`set_time_policy`'nin `run_idempotent` gövdesinin **içinde** (2a dersi — tamamlanmış bir
key'in replay'i ilerlemiş durumu yeniden yargılamaz). `approval_revoked`/`deprecated` de
donmuş: onayı geri almak veya deprecate etmek **yeni** kullanımı durdurur, o revizyonu zaten
zikreden manifestleri unpinlemez. Kurtarma yolu zaten vardı ve değişmedi:
`create_research_dataset_revision` yeni bir DRAFT ekleyip head'i ilerletiyor.

### Yeni kapsam (öncesinde eşdeğeri yoktu)

* **mikrosaniye** as-of sınırı — önceki kapsam saniyede duruyordu;
* aynı `available_at`'li iki kayıt **ikisi de birer kez** ateşler (sessiz dedupe yok — ileride
  bir "dedupe" kitaplanan funding maliyetini yarıya indirirdi);
* **geç varış** replay'de de uygun değil, aynı barı tekrar oynatmak aynı boş cevabı verir;
* **non-UTC** beyan edilmiş kaynak zaman dilimi `build_funding_schedule` üzerinden — tüm
  önceki funding testleri `ZoneInfo("UTC")` geçiyordu, gerçek offset uygulayan dal test
  edilmemişti;
* **DST fold / DST gap** karakterize edildi (aşağıda);
* ingest normalizer (`resolve_timestamp`) ile funding reader (`parse_utc`) — iki ayrı
  implementasyon — her DST vakasında **aynı** cevabı veriyor;
* `feature_input_only` + **onaylı tanım** pozitif yolu (yalnız negatif hâli test edilmişti);
* **historical correction** pinli revizyonu *ve yeniden derlenen `bundle_hash`'i*
  byte-identical bırakıyor.

### DST: karakterize edildi, kural uydurulmadı

Beyan edilen zaman dilimi `America/New_York`, offset taşımayan kaynak hücresi:

| vaka | hücre | çözülen an | işaretleniyor mu |
|---|---|---|---|
| fold — 01:30 **iki kez** oluyor (EDT, sonra EST) | `2024-11-03T01:30:00` | `2024-11-03T05:30:00Z` (**ilk**, EDT oluşum) | hayır |
| gap — 02:30 **hiç olmadı** | `2024-03-10T02:30:00` | `2024-03-10T07:30:00Z` | hayır |

Mekanizma: her iki okuyucu da `datetime.replace(tzinfo=zone)` kullanıyor, `fold` varsayılan
`0`. Sonuç: **katlanan saatin ikinci oluşumu kaynak dosyadan adreslenemiyor** — offset
taşımayan bir string `fold=1`'i ifade edemez, yılda bir saatlik veri sessizce erken ana
çöküyor. Deterministik ve tekrar üretilebilir, ama **beyan edilmemiş**. Doc 12 §5.2 "conversion
failure blocks approval/run" diyor, fakat 1:1 olmayan iki yerel duvar saati için kural
tanımlamıyor → ADIM 13 karar **vermedi**, davranışı test ile pinledi ve #559'u açtı.

### Dört uyuşmazlık açıldı, hiçbiri düzeltilmedi

Hepsi ortak time-policy katmanının **dışında**; her biri `xfail(strict=True)` — düzeltildikleri
gün xfail'in kendisi kırılır ve marker kaldırılmak zorunda kalır, sessizce yeşile kayamaz.

| # | özet |
|---|---|
| #556 | `data_bundle.resolve` **hiç** lifecycle durumu okumuyor: soft-deleted root ve `deprecated`/`approval_revoked` revizyon başarıyla pinleniyor, ikizi `compile_agent_data_bundle` ikisini de `NotFoundError` ile blokluyor. İkincil kusur: market yarısı, docstring'i "approved Market" iddia etmesine rağmen yalnız varlık kontrolü yapıyor. |
| #557 | `data_bundle.resolve` (`agent_tools.py:396`) Feature-Input-Only kapısını **istek gövdesinden gelen** `has_approved_feature_definition` boolean'ından karara bağlıyor; ikizi (`research_data.py:488`) gerçek `SELECT` ile çözüyor. Engine bu pini çalıştırmadığı (Ready Check + worker kapısı her şeyi DB'den yeniden türetiyor) için CRITICAL değil — kaydedilen Agent provenance'ını bozuyor. |
| #558 | Hiçbir bundle üyesi doc 12 §9.1'in ("exact revision IDs, usage scope **and time policy**") ve §9.2'nin (`available_time_policies[]`) adını verdiği zaman politikasını pinlemiyor → `bundle_hash` politika değişimine karşı **değişmez**, bir bundle hangi kural altında derlendiğini kendi içeriğinden ispatlayamıyor. Run manifest hepsini pinliyor; iki execution-evidence yüzeyi çelişiyor. §9.2'nin diğer dört alanı (`feature_definition_revision_ids[]`, `instrument_mapping_revision_ids[]`, `alignment_policy_versions[]`, `missing_and_stale_policies[]`) da yok, aynı issue'ya katlandı. |
| #559 | DST fold/gap ürün kararı (yukarıda). |

### Dürüst sınırlar

* **V1 engine TEK research feed tüketiyor** — pinlenmiş funding-rate kaynağı. `grep -rn
  "research" domain/backtest/` tam olarak dört şeye çarpıyor: `funding.py`,
  `execution/costs.py:39`, `history.py` (manifest snapshot'ının geri okunması — canlı root
  ASLA) ve `result_visibility.py` (ilgisiz ACL). Hiçbir research değeri indikatöre, filtreye
  veya sinyale ulaşmıyor. Matrisi doldurmak için **sahte join yazılmadı**.
* Doc 12 §8.4 kural 3'ün *"t anından önce/eşit `available_at` taşıyan en son uygun record
  seçilir"* as-of join'inin **hiçbir implementasyonu yok** — o bir *değeri t anında okuma*
  kuralı; funding tüketicisi her *olayı* bir kez uyguluyor (`due_funding_charges` monoton
  imleç). İkisi de kendi semantiği için doğru, ama research **seviyesi** okuyan kimse olmadığı
  için kural 3 şu an işletilmiyor.
* `event_time_semantics` manifestte pinli ama **hiçbir yerde uygulanmıyor**; Ready Check de
  bakmıyor.
* **As-of tolerance / max staleness yok** — uygun bir kayıt asla eskimiyor. Canon da bir sınır
  tanımlamıyor, o yüzden uydurulmadı.
* `verified` durumu hâlâ retime edilebilir; doc 12 §5.2'nin ima ettiği "retime prior analysis'i
  geçersizler" reset'i implemente **değil** ve bu slice'ın kapsamı dışındaydı.
* **A2'nin zaman politikasını doğrulamaması kusur değil, bilinçli:** doc 12 §9.3 her scope'u
  Agent research'e kabul ediyor ve bir Agent bundle'ı as-of çözümlemesi yapmıyor; yalnız
  üyeleri karar zamanlarına karşı oynatılan B1 çözülebilir bir kural istiyor. Bu asimetri
  geçen bir testle **kasıtlı** olarak iddia edildi, kusur olarak dosyalanmadı.
* **A1'in `src` içinde çağıranı yok** — yalnız tool yüzeyi ve testler ulaşıyor;
  `agent_executor` `backtest.ready_check` (`:413`), `backtest.request` (`:470`),
  `result.query` (`:550`) ve `artifact.create` (`:584`) dışında bir şey dispatch etmiyor. Bu
  #556/#557'nin bugünkü etki alanını sınırlar, kapatmaz.
* **Frontend takip notu (issue açılmadı):** `ResearchLifecycle.tsx` onaylı bir revizyon için
  time-policy formunu hâlâ sunabiliyor ve artık 409 alacak; zarf `remediation` +
  `suggested_action` taşıdığı için kurtarma açıklanıyor, ama UI kontrolü ön-devre dışı
  bırakmıyor.

### Doğrulama

Hedefli **40 passed + 4 xfailed** · full backend suite **exit 0**, coverage **%92.89**
(kapı ≥90) · `ruff check` + `ruff format --check` + `mypy src` (385 dosya) temiz ·
**CI 6/6 pass** (Backend 46m01s, E2E-browser 8m53s, A11Y 2m41s, E2E dev-auth 1m59s,
Frontend 1m55s, Docker 43s).

**Doküman:** `docs/audit/research_point_in_time_matrix.md` — dört yüzeyin ne okuduğu tablosu,
zaman sözlüğünün ne olup **ne olmadığı** (per-record ingestion time yok, tolerance yok,
forward-fill hiç implemente edilmemiş → doc 12 §8.4 kural 5 boş yere sağlanıyor), T/S/L/P
kanıt matrisi ve dürüst sınırlar. Bir sonraki oturum Research Data zamanına dokunuyorsa
**önce onu okumalı**.

### Aynı gün paralel landed (ADIM 13'ün işi DEĞİL)

**PR #555** — `fix(engine): fill a gapped protection stop at the bar open, not at the level`
→ **issue #549 CLOSED** ve **`ENGINE_VERSION` artık
`backtest-engine-v18-gap-adjusted-stop-fill`** (önceki `backtest-engine-v18-same-candle-entry-exit`).
ADIM 12'nin tek oracle `xfail(strict)`'i bununla kalktı; suite'teki tek xfail dosyası artık
ADIM 13'ün parity testleri.

---

## ADIM 14 — Unified-clock multi-item portfolio ADR (PR #563)

**Base `f4e2fd3` → commit `992ac9d` → merge `fb57cc8`** · 2026-08-04T18:27:28Z ·
**docs-only**: `docs/adr/0002-unified-clock-portfolio-simulation.md` (761 satır) +
`docs/adr/README.md` indeks satırı. **Migration YOK** (alembic head
`0043_i08_registry_strategy_fks`, tek head) · **OpenAPI DEĞİŞMEDİ** (196 operation / 151 schema)
· **`ENGINE_VERSION` DEĞİŞMEDİ** · **production kod ve test DEĞİŞMEDİ.**

**Statü: `Proposed`.** PO / maintainer onayı bekliyor. ADR §16 bunu bir kapı olarak yazıyor:
onaya kadar implementasyon başlamaz, statü **`Accepted` değildir** ve belge tasarımın herhangi
bir parçasının **inşa edildiğinin kanıtı değildir**.

### Neden bir ADR, neden şimdi

Shared Equity Allocation bugün **contained**: `domain/allocation/capability.py` içindeki
`SHARED_ALLOCATION_STATUS` `future_dev` ve shared sermayeli run'lar fail-closed reddediliyor
(ADIM 3 / PR #520). Containment'ın gerekçesi kayıtlı ve altı maddelik bir **kaldırma koşulu**
listesi taşıyor. Kusur şuydu: item'lar **sırayla** simüle ediliyor, her biri kendi ledger'ıyla;
oysa kanon (doc 13 / Master Ref Modül 11) tek bir portföy sermayesi ister — tick başına **tek**
`E(t)`, ondan türeyen `Ci(t)` sleeve'leri ve item sırasından bağımsız bir sonuç.

Bu değişiklik engine'in **dış döngüsünün şeklini** değiştiriyor. ADIM 12 (oracle baseline) ve
PR #555 (#549 gap-adjusted stop) engine aritmetiğini önceden sabitledi; ADIM 14'ün işi
**tasarımı ADIM 15 tek satır kod yazmadan önce karara bağlamak** ve PR sınırlarını dondurmak.
Sebep operasyonel: saat değişimi ile fiyatlama değişimi **aynı digest tazelemesine** karışırsa
hangisinin neyi kaydırdığı bir daha kanıtlanamaz.

### Kararın çekirdeği

Dış döngü item listesi değil **birleştirilmiş zaman ekseni** (`t_ms` anahtarı, item bar
iterator'ları üzerinde streaming k-way merge, `(pin_ordinal, item_id)` tie-break) olur. Tek
`PortfolioLedger` `P0`/`R0`/`U0`'ı bir kez tutar; her tick'te zorunlu olaylar önce çözülür,
sonra **tam bir** `E(t)` yayımlanır, sonra her item `Ci(t)`'sini o tek değere karşı hesaplar.

**Blast radius'u sınırlayan invariant (§3.2):** tek-item yolu **bit-aynı** kalır. `run_engine`
imzasını *ve semantiğini* korur; birleştirilmiş eksen tek item'a indirgendiğinde bugünkü bar
dizisine eşittir. Bu yüzden 46 golden digest'in **37'si kımıldamaz** ve yalnız 9 `portfolio.*`
senaryosu hareket eder — her biri yazılı gerekçeyle tek tek incelenmek üzere.

### Üç dondurulmuş çıktı

**§12 — ADIM 15–20 sınırları.** Her adım tek branch, tek PR, bağımsız revert edilebilir;
**20 dışında hiçbiri containment'ı kaldırmaz**. 15 = saf clock primitive (engine kullanmaz,
rollback = modülü sil). 16 = `run_engine`'in bar döngüsünü resumable stepper'a çıkaran **saf
refactor**, tek kanıtı 46 digest'in değişmemesi. 17 = `PortfolioLedger` + `PortfolioSnapshot`.
18 = `ItemIntent` + tick faz döngüsü, **yeni** `run_portfolio(...)` girişinde. 19 = simetrik,
deterministik çatışma arbitrasyonu; solvency **reject** (asla kısmi, asla borç). 20 = manifest
alanları + `ENGINE_VERSION` bump + digest yenileme + **containment lift**.
ADIM 15–20'nin **parçası olmayan** önkoşullar ayrıca listelendi: #559 (DST), #544 (NET), R-1,
OD-1…OD-6.

**§13 — yedi açık karar (OD-1…OD-7).** Kanonun sessiz olduğu her yer bir OD olarak ayrıldı;
her biri soru + kanon durumu + seçenekler + **onay gerektiren** öneri taşıyor. Örnekler:
`record_time_basis` onurlandırılsın mı (OD-1); taze barı olmayan item'ın açık pozisyonu nasıl
mark edilir (OD-2); birlikte karşılanamayan intent'lerden hangisi reddedilir (OD-3 —
`(pin_ordinal, item_id)` sırası mı, tam simetrik "hepsini reddet" mi); `Ci(t)` sürekli mi yoksa
yalnız girişte mi sınırlar (OD-4); FX kapsamda mı (OD-5, hayır); icra edilmeyen item sleeve
tutabilir mi (OD-6); daha eksiksiz equity serisi `METRIC_SET_VERSION` bump'ı gerektirir mi
(OD-7, hayır). **Hiçbiri ADR tarafından kapatılmadı** — kapatma yetkisi üründe.

**§14 — A1–A22 kabul matrisi.** Containment lift'in kapısı; her satır kaynağı ve gerekli kanıtı
ile. Kritikler: **A4** item permütasyonu aynı digest'i verir; **A13** 37 portföy-dışı digest
değişmez; **A15** `ENGINE_VERSION` bump + `execution_key` namespace kayması; **A17** PR #560'ın
point-in-time testleri **zayıflatılmadan** yeşil; **A19** eski shared-pool Result byte-identical
okunur ve `LEGACY_SEQUENTIAL_RESULT_NOTE` ile etiketlenir; **A20** rollback kanıtlanır;
**A22** full backend suite `--cov-fail-under=90` kapısında yeşil.

### ADR'ın yazılırken bulduğu iki kalem — ikisi de bilerek düzeltilmedi

**R-1 (§10.2) — latent pinning drift.** `application/commands/readiness_check.py::_resolve_allocation`
(`:805-838`) kendini *"plan'ın mevcut revision config'ini pinler, yoksa canlı draft"* diye
belgeliyor; kod ise **koşulsuz** `config = _plan_to_config(plan, entries)` ile **canlı draft
satırlarından** kuruyor ve `plan_revision_id = plan.current_revision_id`'yi çıplak pointer olarak
yazıyor. Pinlenen config'in adı geçen `PortfolioAllocationPlanRevision.config` satırıyla
byte-eşleştiğini **hiçbir şey doğrulamıyor**. Snapshot bir kez alınıp bir daha join edilmediği
için bu **canlı-join kusuru değil** — ama "plan revision N" ile gerçekte simüle edilen ayrışabilir.
Doc 13 §8.5 composition snapshot'ının *tam* revision'ı sabitlemesini istiyor. **ADIM 20'den önce,
saat işinden bağımsız, ayrı ve dar bir PR.**

**§10.1 — manifest'te eksik üç kanonik alan.** Doc 13 §13 (`:1277`) ve Modül 11 §10
(`:8313-8333`) shared-mode manifest'inin **resolved sleeve amounts**, **currency/FX refs** ve
**`engine_allocation_policy_version`** taşımasını istiyor; sevk edilen `capital_execution`
snapshot'ı yalnız `{enabled, plan_id, plan_revision_id, config_hash, config}` taşıyor
(`readiness_check.py:829-835`) ve `grep -rn "allocation_policy" backend/ docs/openapi.json`
hiçbir şey döndürmüyor. Bugün zararsız çünkü shared mode contained; **ADIM 20'den önce kapanmalı.**

### Kapsam dışı bırakılanlar (kimse aksini çıkarmasın diye yazıldı)

Cross-margin ve portföy likidasyonu **sevk edilmiyor** (§9.5). NET netting semantiği burada
**tanımlanmıyor** (§9.4, #544). FX dönüşümü kapsam dışı (OD-5). Trading Signal / Trade Log
icrası kapsam dışı (OD-6). `record_time_basis` semantiği değişmiyor (A-1 / OD-1). Retention
auto-purge, LLM generation ve Graphic View renderer eskisi gibi kapsam dışı.

### Doğrulama — dürüst sınır

**Test suite KOŞULMADI.** Çalıştırılabilir hiçbir şey değişmedi (kod yok, test yok, migration
yok, OpenAPI yok); docs-only bir slice'a önceki bir koşunun sayısını etiketlemek yanıltıcı
olurdu. **Codemap tazelenmedi ve gerekmiyor:** yeni endpoint / tablo / sayfa / job yok, bu
yüzden `docs/CODEMAPS/` haritalarının hiçbirinin girdisi değişmedi. Sistemin doğrulanmış test
durumu için son **kod** slice'larının kayıtlarına bakılmalı (PR #555, #560).

### İki bayat kayıt — ADR tespit etti, iki kapanış birden düzeltti

ADR §10.3 yazılırken `CLAUDE.md` §Current position'da iki yanlış tespit edilip belgeye yazıldı:
`ENGINE_VERSION`'ın `backtest-engine-v18-same-candle-entry-exit` gösterilmesi (gerçek değer
`manifest.py:126`'da **`backtest-engine-v18-gap-adjusted-stop-fill`**, **PR #555** getirdi) ve
oracle paketi için "78 pass + 1 `xfail(strict)`" iddiası (`grep -rn xfail
backend/tests/unit/oracles/` **sıfır** dönüyor; #549 xfail'i PR #555 ile kalkıp düzenli teste
dönüştü, kalan 4 xfail `tests/integration/test_research_point_in_time_parity.py` içinde —
#556 / #557 / #558). **İkisi de ADIM 13'ün kapanışında (PR #562) düzeltildi**; bu kapanış
düzeltmeyi korur ve kaynağını kayda geçirir.

### Sıra ve numaralandırma çakışması — **çözüldü: ADIM 14 = ADR, frontend slice = F-26**

ADR (#563) `origin/main`'e **ADIM 13'ün kapanış kaydından (#562, merge `801791f`) ÖNCE** indi;
bu kayıt onun üzerine rebase edilerek yazıldı. Kronoloji tutarlıydı, **numaralandırma değildi**:
#562'nin "Next"i ADIM 14'ü *frontend capability disclosure (#539 + #533)* olarak tanımlıyordu,
merge edilmiş ADR ise kendini ADIM 14 sayıyor (§16: "Per the ADIM 14 brief") ve **ADIM 15–20'yi
unified-clock programına rezerve ediyor**.

**Karar (2026-08-04):** **ADIM 14 = ADR** (merge edilmiş gerçek; ADR immutable, metni
değiştirilmedi — statüsü hâlâ `Proposed`) ve **frontend slice'ının etiketi `F-26`**. Gerekçe iki
katlı: (1) slice saf frontend sunum işidir ve F-serisi tam olarak bunu adlandırır — `F-01…F-25`
doluydu, `F-26` ilk boş numara; (2) ADIM 15–20 unified-clock programına rezerve olduğu için ADIM
serisinden numara harcanmamalıydı. Etiket `docs/ADIM13_LANDED_KICKOFF.md`,
`docs/STAGE2_HANDOFF.md`, `docs/ADIM14_LANDED_KICKOFF.md` ve `CLAUDE.md` genelinde bu değere göre
düzeltildi; **tarihsel kayıtlar silinmedi, yalnız etiket düzeltildi.** Slice'ın kendisi
**PR #564 ile landed** — tam kaydı aşağıda **§F-26**.

### Kapanış kararı

`docs/adr/0002-unified-clock-portfolio-simulation.md` bu slice'ın kalıcı çıktısıdır ve
**onaylanana kadar bir öneridir**. Bir sonraki oturum unified clock'a dokunuyorsa önce onun
**statüsünü** okumalı: `Proposed` ise iş tasarım tartışmasıdır, implementasyon değil.
Reuse anchor'ları ve resume prompt: `docs/ADIM14_LANDED_KICKOFF.md`.

---

## F-26 — Strategy formu capability disclosure (PR #564)

**Commit `5887f3f`** → **merge `b8d62e2`** (2026-08-04T19:32:36Z) · branch
`fix/strategy-form-capability-disclosure` · **frontend-only, sunum işi** · **Migration YOK**
(alembic head `0043_i08_registry_strategy_fks`, tek head) · **OpenAPI DEĞİŞMEDİ** ·
**`ENGINE_VERSION` DEĞİŞMEDİ** · **backend byte-identical**.

**Etiket tarihçesi:** slice ADIM 13'ün kapanışında (#562) "ADIM 14" diye planlanmıştı. O numara
`origin/main`'e daha önce inen ADR 0002'ye (#563) aitti; çakışma 2026-08-04'te **F-26** lehine
karara bağlandı (yukarıdaki §"Sıra ve numaralandırma çakışması"). Planlama metinleri
`docs/ADIM13_LANDED_KICKOFF.md` ve `docs/STAGE2_HANDOFF.md` §"Eski Next"te — etiketleri
düzeltilmiş, içerikleri korunmuş halde — duruyor.

### Kapatılan iki kusur — aynı kök, zıt yönler

Üretilen capability aynası, kullanıcı bir `future_dev` opsiyonun **üzerine strateji kurmadan
önce** o opsiyonu reddetmek için var. İki kusur bu sözü zıt yönlerden bozuyordu ve **kökleri
aynıydı**: form kararını opsiyonun **DEĞERİNE** bakarak veriyordu, backend okuyucuları ise
motorun alanı **okuyup okumadığına** bakıyor.

**#539 — yanlış-NEGATİF (CRITICAL, ADIM 11'de açılmıştı).** `StrategyGraphForm` üretilen
aynayı **hiç** import etmiyordu (`grep -c capabilityField`: ConfigForm 12, GraphForm **0**) ve
kendi `SelectField`'ini taşıyordu. Matrisin 22 `future_dev` satırından **15'i** sıradan
seçilebilir opsiyon gibi render ediliyordu:

| alan | satır |
|---|---:|
| `scaling_logic.timeframe` | 10 |
| `scaling_logic.timeframe_mode = increasing_by_layer` | 1 |
| `restrictions_filters.filters.filter_type` | 4 |
| **toplam** | **15** |

> **Rakam notu:** issue #539'un başlığı "11" diyor, **kendi tablosuyla çelişiyor**; doğru sayı
> **15**'tir (bağlı 9 ConfigForm alanının `future_dev` toplamı 7 → 22 − 7 = 15). Aynı hatalı
> rakam ADIM 11'in tarihsel kaydında da duruyor ve **bilerek düzeltilmedi** (geçmiş yeniden
> yazılmaz); kabul ölçütü 15 üzerinden ölçüldü.

Kullanıcı gerçeği ancak stratejiyi kurduktan **sonra** Ready Check'te öğreniyordu
(`STRATEGY_SCALING_UNSUPPORTED`). **Yetki açığı değildi** — sunucu koşuyu reddediyor, motor
pozisyon açmıyor — ama bu bir **disclosure** kusuru ve hata yönü **güvensiz**.

**#533 — yanlış-POZİTİF.** Yepyeni bir stratejide, **sevk edilen varsayılanlarla**, form
`allow_hedge` için "Ready Check blocks it" basıyordu; Ready Check bloklamıyordu.
`exit_on_opposite_signal` AÇIKKEN pozisyon hedge dalına erişilmeden kapanır → değer **inert**tir
ve backend üçlü paritesi (`engine.py`, `capabilities.py::_read_opposite_hedge`, `validators.py`)
bunu zaten doğru işliyordu. Kusur yalnız frontend iddiasındaydı.

### Tek kural, tek modül

#539'u **değere** bakarak kapılamak tam olarak #533'ü çoğaltırdı — bu yüzden ikisi ayrı değil
**TEK slice**ta ve tek kuralla çözüldü; kural her forma kopyalanmak yerine **yeni tek modülde**
tutuldu:

* **`frontend/src/components/capabilityDisclosure.ts` (yeni)** — kuralın tek sahibi. Çağıran
  kart alanın **erişilebilirliğini** (`scaling.enabled`, `filter.enabled`) ya da bir **inert
  gerekçesini** (`exit_on_opposite_signal`) sağlar.
* **`frontend/src/components/CapabilityNote.tsx` (yeni)** — notun tek render yüzeyi.
* **Erişilemez alan** ne disable edilir ne de not alır — alanı atlayan backend okuyucusunu
  aynalar. **Inert alan** da hiçbir şeyi disable etmez, çünkü değeri seçmek bloklamazdı.
* **Zaten kaydedilmiş değer seçilebilir kalır** sözleşmesi **değişmedi**.

### Yan kazanç — D-6 (`MODELLED_FILTER_TYPES`)

`lib/strategyGraph.ts` içindeki `MODELLED_FILTER_TYPES`, motor allow-list'inin **elle bakımlı
3 elemanlı kopyasıydı ve parite testi yoktu**. Artık **matristen türetiliyor** ve bir testle
pinleniyor. Ayrıca uyarısı **disabled bir filtre satırında** da ateşleniyordu — kaydedilen
revizyondan zaten düşen bir satır için blocker iddia ediyordu; o da düzeldi.

### Regresyon kapısı

Yeni exhaustiveness guard **12 bağlı alan yolunu** kaydediyor ve kaydedilmemiş bir alanda
`future_dev` satırı belirirse **kırılıyor**. Bu, bugün **sıfır** `future_dev` taşıyan ama bağlı
olmayan `scaling_logic.method` ile `position_exit_logic.partial_aftermath`'i de kapsıyor —
yani matris yeniden üretilip biri `future_dev`'e dönerse **#539 sessizce geri gelemez**.

### Dosyalar (6 dosya, +412 / −49)

| dosya | durum |
|---|---|
| `frontend/src/components/capabilityDisclosure.ts` | **yeni** — kuralın tek sahibi |
| `frontend/src/components/CapabilityNote.tsx` | **yeni** — notun render yüzeyi |
| `frontend/src/components/StrategyConfigForm.tsx` | ortak kurala bağlandı |
| `frontend/src/components/StrategyGraphForm.tsx` | aynayı ilk kez import ediyor |
| `frontend/src/lib/strategyGraph.ts` | `MODELLED_FILTER_TYPES` matristen türetiliyor |
| `frontend/src/test/capabilityDisclosure.test.tsx` | **yeni** — kural + guard + parite testleri |

### Sınır (dürüst)

**Dokunulmayanlar:** route path · react-query key · OCC token · Idempotency-Key · hooks ·
SSE taksonomisi · API çağrıları · `lib/*.ts` veri mantığı — **hiçbiri değişmedi**.
`CAPABILITY_MATRIX` satırları, üretilmiş `engineCapabilityMatrix.generated.ts` (backend parity
testi byte byte pinliyor), readiness validator ve `opposite_direction_hedge`'in **sevk edilen
varsayılan değeri** (ayrı ürün kararı, F-4) **dokunulmadı**. Backend byte-identical.

**Doğrulama:** düzeltmeden **önce** üç kusuru da assert eden bir render probe'u yazıldı, düzeltme
**sonrası** aynı assertion'lar düştü. **CI PR #564'te 6/6 SUCCESS** — Backend (lint/type/test) ·
Frontend (lint/typecheck/build/test) · E2E gerçek tarayıcı (F-23) · E2E dev-auth acceptance ·
A11Y axe-core (R2-14) · Docker build. **Bu kapanış kaydı docs-only bir oturumda yazıldı ve
suite'i yeniden ÖLÇMEDİ**; tek doğrulama kanıtı #564'ün CI koşusudur.

**Açık kalan:** **#539 ve #533 issue'ları hâlâ AÇIK** — düzeltme merge edildi ama issue kapatma
yetkisi **insandadır**, agent kapatamaz. **#540** (exhaustiveness guard issue'su) bilerek kapsam
dışı bırakıldı: bu slice'ın guard'ı **12 bağlı alanı** kapsıyor, #540'ın istediği **14 alanlık**
tam kapsam değil.

---

## ADIM 15 — Merged-axis valuation clock primitive (PR #567)

**Merge `ef11dc9`** (2026-08-04T20:06:44Z) · branch `feat/portfolio-unified-clock-core` ·
**+864 / −1, 3 dosya** · **backend-only** · **Migration YOK** (alembic head
`0043_i08_registry_strategy_fks`) · **OpenAPI DEĞİŞMEDİ** · **`ENGINE_VERSION` DEĞİŞMEDİ**
(`backtest-engine-v18-gap-adjusted-stop-fill`) · **frontend dokunulmadı** · **CI 6/6 SUCCESS**.

ADR 0002 §12'nin ilk uygulama dilimi: **merged-axis clock primitive, ve başka hiçbir şey.**

### Neden — katlanan eğri bir zaman serisi değil

Kanon portföy motorunun **DIŞ döngüsünün** öğe listesi değil, tüm aktif öğeler üzerindeki
birleşik zaman damgası ekseni olmasını istiyor (doc 13 §8.3 · Modül 11 §5.2 · Modül 12 §9.2 —
`domain/allocation/capability.py`'de kaldırma şartı #1 olarak da yazılı). Sevk edilen worker
(`application/jobs/backtest_engine.py:298`) öğeler üzerinde dönüyor ve bitmiş run'ları pin
sırasında katlıyor. Sonuç yalnız yanlış değil, **tür olarak yanlış**: composite eğri bir zaman
serisi değil. Mevcut `test_composite_portfolio_curve_is_not_time_ordered` kusuru **bilerek**
pinliyor — aynı dört kapanışın unified-clock replay'i **3000.00** verirken sevk edilen kat
**5000.00** raporluyor.

### Sözleşmeler (tercih değil, kural)

| kural | ADR | ne demek |
|---|---|---|
| Tick anahtarı **`t_ms`** (UTC epoch ms) | §4.1 | String timestamp'ler karışık offset biçimleri girince yalnız **kazara** sıralıdır. `…T02:00:00+01:00` ile `…T01:00:00Z` **TEK** tick'e düşmeli — burada düşüyor, string sort'ta düşmezdi. Kod tabanı bu anahtarı zaten kullanıyor (`PriorItemInterval.start_ms/end_ms`) |
| Tick = **değerleme noktası**, asla (item, zaman) çifti değil | §4.1 | Öğeler tick'in **içinde** yaşıyor → "t anında her öğe aynı snapshot'ı görür" **yapısal** bir gerçek olur, sonradan doğrulanacak bir disiplin değil |
| Dedup **EKSENİN**, öğe verisinin **ASLA** değil | §4.2 | Bir öğenin pinli akışı aynı anda iki bar taşıyorsa **ikisi de** görünümde yüzeye çıkar (`bars` tuple), eksen **bir kez** ilerler. Katlamak kanonun vermediği bir merge kuralı ister; birini düşürmek pinli veriyi sessizce atar |
| Bar timestamp **==** karar zamanı | §4.3 / A-1 | Sevk edilen konvansiyon korundu; `record_time_basis` üzerinden **dallanma YOK** — o **OD-1**'dir ve aynı digest tazelemesine ikinci bir anlamsal değişiklik sokardı |
| **Fail closed, asla atlama** | §11 | Yerleştirilemeyen timestamp / geriye giden akış / mükerrer `item_id` → **raise**. Worker bunları başarısız run'a çevirir; sessizce bozuk bir eksen üzerinde devam etmez |
| **Streaming** k-way merge | §11 | Mevcut chunked bar iterator'ları üzerinde heap merge; öğe başına en fazla **bir bar** tutulur. Materialize-then-sort kabul edilemez — kaynak generator'lardan çekilen satırları **sayan** bir testle pinli |
| Tie-break **`(pin_ordinal, item_id)`** | §4.4 | `pin_ordinal` manifest'in deterministik pin sırasından (`manifest._pinned_items`, `(root_id, selected_revision_id)`). **Asla DOM sırası, asla varış sırası** |
| Duvar saati yok, rastgelelik yok | — | Eksen pinli girdilerinin **saf fonksiyonu** → replay yapıca yeniden üretilebilir |

### Public yüzey

`ItemBarStream(item_id, pin_ordinal, batches)` — worker'ın bugün zaten tuttuğu chunked
iterator doğrudan geçiyor; clock `run_engine`'in tükettiği **aynı** satırları tüketiyor ve
**aynı** coercion'ı (`_normalize`) uyguluyor, yani motorun düşürdüğü satır burada da düşüyor.
`ItemTickView` (`bars`, `last_closed`, `last_closed_t_ms`, `is_decision`, `staleness_ms`) ·
`ClockTick` (`t_ms`, `views`, `deciding`, `view_for`) · `iter_ticks()` · `tick_key()` ·
`timeline_identity()` (kendi sha256 namespace'i var, başka bir digest'le çakışamaz) ·
`CLOCK_POLICY_VERSION = "clock-policy-v1"`.
Hata sınıfları: `ClockAxisError(ValueError)` ← `UnplaceableBarTimestampError` ·
`NonMonotonicBarStreamError` · `DuplicateItemStreamError`.

> **`CLOCK_POLICY_VERSION` neden şimdi var ama manifest'te yok:** ADR §10.3 onu bir MANIFEST
> alanı sayıyor; **manifest'e yazmak ADIM 20'nindir.** Sabit, erken sevk edilsin diye değil,
> adlandırdığı politikanın **ilk satırından itibaren tek evi olsun** diye burada.

### İzolasyon — testle kilitli, sözle değil

**Hiçbir üretim modülü `clock.py`'yi import etmiyor** (`origin/main` üzerinde `git grep`,
`backend/src` altında sıfır eşleşme). `run_engine` **imzasını VE semantiğini** korudu (§3.2) →
hiçbir golden digest, `ENGINE_VERSION` veya `execution_key` oynamadı. ADIM 15'in rollback'i
gerçekten **"modülü sil"**. Bu iddia iki testle pinli:
`test_the_clock_is_not_wired_into_production_yet` ve
`test_no_clock_field_ships_in_the_manifest_yet_and_the_engine_version_stands`.

### 27 test neyi kapsıyor

Tek-öğe indirgemesi (§3.2) · sıralı birleşim · paylaşılan instant'ın tek tick'e çökmesi ·
offset biçimlerinin aynı instant'a düşmesi · **metin değil instant** sıralaması · tek taraflı
eksen · boş akış kümesi + barsız öğe · heterojen timeframe interleave (**bar ödünç almadan**) ·
öğe içi mükerrer instant'ın **yüzeye çıkması** (katlanmaması) · "hiçbir görünüm **gelecekten**
veri taşımaz" · seyrek öğenin son kapanışı + staleness **ÖLÇÜMÜ** · pin sırası tie-break ·
girdi sırasının ekseni değiştirememesi · rerun determinizmi · batch chunk bağımsızlığı ·
**materialize etmeme** · üç fail-closed dalı · motorun düşürdüğü satırın **aynı şekilde**
düşmesi · availability gate'in **öğenin kendi** karar zamanında değerlenmesi · üst timeframe
bucket'ının kardeş tick'lerden etkilenmemesi · `tick_key`'in sevk edilen epoch helper'larıyla
uyuşması · `CLOCK_POLICY_VERSION` pini · `timeline_identity` determinizm + ayırt edicilik ·
üretime bağlanmamışlık + manifest/ENGINE_VERSION sabitliği.

### Mutation testi — bir mutasyon ilk turda hayatta kaldı

Testler mutasyonla sınandı: **altı mutasyon, altısı da yakalanıyor** — cursor'ın mükerrer bardan
ilkini (sonuncusu yerine) izlemesi · barsız view'ların düşürülmesi · **merge'ün `t_ms` yerine ham
timestamp string'iyle anahtarlanması** · geriye-giden-akış guard'ının kaldırılması ·
`(pin_ordinal, item_id)` sıralamasının kaldırılması · mükerrer `item_id` guard'ının kaldırılması.

**String-key mutasyonu ilk turda HAYATTA KALDI.** Offset fixture'ı iki kaydı tesadüfen bitişik
bırakıyordu, bu yüzden `groupby` yanlış anahtarla bile doğru gruplamıştı — yani testlerin o anki
"geçmesi" eksen sözleşmesinin kanıtı **değildi**. Kapatan test sonradan yazıldı:
`test_a_mixed_offset_axis_orders_by_instant_and_not_by_text`, ve o mutasyon altında düşüyor.

**Bu, ADIM 16–19 için yöntemsel bir kayıttır:** geçen bir suite tek başına kanıt sayılmaz.
ADIM 16'nın tek kabul kanıtı 46 golden digest olduğu için orada mutasyon yerine digest sabitliği
kapıdır; ama ADIM 17–19'un yeni davranış getiren testleri aynı şekilde sınanmalı.

### Bilerek karar verilmeyenler

Shared ledger + snapshot (**ADIM 17**) · `ItemIntent` + faz döngüsü (**ADIM 18**) ·
conflict/sleeve arbitrasyonu (**ADIM 19**) · manifest alanları + `ENGINE_VERSION` bump +
containment lift (**ADIM 20**) · **taze barı olmayan bir pozisyonun tick'te nasıl mark
edileceği — OD-2, hâlâ AÇIK.** Clock bir mark politikasının ihtiyaç duyacağı olguları
**raporluyor** (`last_closed`, `last_closed_t_ms`, `staleness_ms`) ve **hiçbir eşik koymuyor**.

### Dürüst sınır — ADR kapısı kayıtsız geçildi

**ADR 0002'nin statüsü hâlâ `Proposed`** (satır 4: *"requires PO / maintainer approval before any
implementation slice starts"*). §16 onay gelmeden ADIM 15'in başlamamasını şart koşuyordu;
**PR #567 kayıtlı bir onay olmadan indi.** Zarar dar — modül saf, hiçbir yerden import edilmiyor,
rollback tek dosya silme — ama **kapı atlanmıştır ve bu kayda geçer.** §13'ün yedi açık kararı
(OD-1…OD-7) çözülmedi. ADIM 16'ya geçmeden önce onay durumu açıkça teyit edilmeli.

### İkinci dürüst sınır — naive timestamp ayrışması (K-01)

`tick_key` → `parse_utc(timestamp, source_zone=None)` **offset'siz** bir timestamp'ı çözümsüz
sayar, bu yüzden clock onu `UnplaceableBarTimestampError` ile **reddeder** (fail-closed, doğru
davranış). Ama `domain/backtest/indicators.py::_epoch_seconds` **aynı değeri sessizce UTC kabul
eder**. İki yardımcı gerçekten ayrışıyor.

Bugün tetiklenmesi beklenmiyor — üretim barları ingest'te UTC-normalize ediliyor — ve
`test_tick_key_agrees_with_the_shipped_epoch_helpers` clock'un iki *sevk edilmiş* epoch
wrapper'ıyla (`engine._epoch_ms_or_none`, `execution.rules.bar_epoch_ms`) uyuştuğunu kilitliyor;
`indicators._epoch_seconds` o üçlünün dışında. **ADIM 16/18 bununla karşılaşacak:** stepper ve
`run_portfolio` aynı bar akışını hem eksene hem indikatör hesabına verdiğinde iki yorum aynı
satırda buluşur. Kalem burada açık bırakılıyor — clock'un davranışı doğru olan, ayrışma
`indicators` tarafında ele alınmalı.

**Codemap:** `docs/CODEMAPS/BACKEND_LAYERS.md` PR #567 içinde tazelendi; başka harita
gerekmiyor (yeni endpoint / tablo / sayfa / job yok).

**Doğrulama:** bu kayıt **docs-only bir oturumda** yazıldı ve **suite'i yeniden ÖLÇMEDİ.**
İddia edilen tek doğrulama **PR #567'nin kendi CI'ıdır (6/6 SUCCESS)**; modül izolasyonu,
`ENGINE_VERSION` sabitliği ve ADR statüsü `origin/main` üzerinde `git grep` ile ayrıca teyit
edildi.

---

## ADIM 16 (sevk edilen) — Paylaşılan snapshot'a karşı item intent'leri (PR #571 + #572)

> **Geriye dönük kayıt.** ADIM 16'nın kapanış ritüeli yapılmamıştı; bu bölüm ADIM 17
> kapanışında telafi olarak yazıldı. Detay derinliği diğer slice'lardan daha az — kaynak
> commit `e2695e4` ve `docs/CODEMAPS/BACKEND_LAYERS.md`'nin `execution/intents.py` paragrafı.

**Commit `e2695e4` → merge `a572e07`** (2026-08-05T00:51:39+03:00) · branch
`feat/portfolio-item-intents` · +1943 / −3, 4 dosya · Migration YOK (alembic head
`0043_i08_registry_strategy_fks`) · OpenAPI DEĞİŞMEDİ · `ENGINE_VERSION` DEĞİŞMEDİ · CI yeşil.
Ardından **PR #572** (`3a2aea9`) ADIM 15'in mutasyon kaydını ve naive-timestamp sapmasını
docs'a taşıdı (PR #569 superseded olarak kapatılmıştı).

**Yeni:** `backend/src/entropia/domain/backtest/execution/intents.py` (846 satır) +
`backend/tests/unit/test_backtest_item_intents.py` (1087 satır, **45 vaka**).

**Ne getirdi.** Doc 13 §8.4 adım 4'ün tek cümlesi: *"Tum active Mainboard itemleri ayni data +
valuation snapshotiyla intent uretir."*

* **`PortfolioSnapshot`** — read-only VALUE (ledger değil). `A(t) = max(0, E(t) − R0)` ve `U(t)`
  `__post_init__`'te TÜRETİLİR, böylece üç figür tutarsız yayımlanamaz; `R0` sabit nominal ve
  asla yeniden türetilmez; haritalar `MappingProxyType` ile dondurulur; `identity` **kanonik**
  Decimal'ler üzerinden sha256 (`3600` ile `3600.00` aynı değerlemedir, farklı hash'lenemez) ve
  `__post_init__`'te **bir kez** hesaplanır (property olarak n öğelik tick'i n² yapıyordu).
* **`form_intent` = P4** (snapshot'a karşı), **`form_mandatory_intent` = P3** ve **snapshot
  argümanı ALMAZ** — stop/exit valuation noktasından önce çözülür (ADR §6 kural 4; M11 §5.2),
  yani kanonik sıra yorum değil **yapı** ile korunur. Her former diğerinin kind'larını reddeder.
* **Karar bir GİRDİDİR, burada yeniden hesaplanmaz.** Entry/exit/scale sonuçları barlar boyunca
  yol-bağımlıdır (`BlockEvaluator` warmup'ı, `prev_entry_signal`/`prev_scale_signal` edge'leri,
  funding sonrası okunan equity), tek tick'lik saf bir fonksiyon bunları yeniden türetemez;
  ~230 satırlık entry bloğunu yeniden yazmak **sürüklenmekte serbest ikinci bir motor**
  yaratırdı. Boyutlar yalnız sevk edilmiş zincirden gelir.
* **Sleeve cap UYGULANMAZ** — `desired_size` pre-cap'tir (P6b ayrı katman); sizing tabanı
  `sizing_base_source` olarak KAYDEDİLİR çünkü M11 §6.1 ile sevk edilmiş `planned_size` burada
  ayrışıyor (`SIZING_BASE_DIVERGENCE`, **adjudicate EDİLMEDİ**).
* **Hiçbir şey sessizce düşürülmez:** `no_op`/`blocked` birinci sınıf (`no_bar_at_tick`,
  `no_signal_at_tick`, `item_kind_does_not_execute` — sonuncusu **OD-6** açıkken iki okumanın da
  hemfikir olduğu tek davranış).

**⚠ PLAN SAPMASI (ADIM 17 kapanışında tespit edildi).** ADR 0002 §12 tablosunda **ADIM 16 =
`run_engine`'den resumable stepper** (saf refactor; kabul = 46 golden digest'in TAMAMI sabit),
**ADIM 18 = `ItemIntent` + faz döngüsü**. Sevk edilen ADIM 16 ise intent katmanıdır — ADR'nin
ADIM 18'inin bir yarısı. **Stepper hiç yazılmadı**, oysa §12 sınırları "dondurulmuş" ilan
edilmişti. Karara bağlanmalı: §12'yi amendment ile güncelle **ya da** stepper'ı geri planla.

---

## ADIM 17 — Shared capital ve exposure ledger (PR #573)

**Commit `3ad5bf3` → squash-merge `f8f96c5`** (2026-08-05T02:13:50+03:00) · branch
`feat/portfolio-shared-ledger` · **+2570 / −3, 5 dosya** · **Migration YOK** (alembic head
`0043_i08_registry_strategy_fks`) · **OpenAPI DEĞİŞMEDİ** · **`ENGINE_VERSION` DEĞİŞMEDİ**
(`backtest-engine-v18-gap-adjusted-stop-fill`) · **CI 6/6 SUCCESS** (Backend job 42m42s).

| dosya | |
|---|---|
| `backend/src/entropia/domain/backtest/execution/portfolio_ledger.py` | **yeni**, 971 satır |
| `backend/tests/unit/test_backtest_portfolio_ledger.py` | **yeni**, 1277 satır / **59 fonksiyon, 100 vaka** |
| `docs/audit/portfolio_ledger_accounting.md` | **yeni**, 311 satır |
| `backend/tests/unit/test_backtest_item_intents.py` | intents containment testi **bilerek** güncellendi |
| `docs/CODEMAPS/BACKEND_LAYERS.md` | `execution/portfolio_ledger.py` paragrafı |

### Neyin yerine geçiyor

Sevk edilen motor öğe **başına** bir `_Ledger` tutuyor ve her birini **tam havuz P0**'dan
tohumluyor (`engine.py:846`, `resolve_allocation_execution` her öğe için `initial_capital=p0`
döner). Sonuç: `COMPOUND_PORTFOLIO_EQUITY` altında bir öğenin sleeve'i **kendi** equity'si
üzerinden compound oluyor ve kardeşinin PnL/fee/funding'ini **asla** göremiyor — havuz yalnız
isimde paylaşılıyor. Bu slice o durumun yerine geçen **tek** hesap defterini getirir; onu
sürecek faz döngüsünü **değil**.

### Sözleşmeler (tercih değil, kural)

* **Sermaye yapısı bir kez çözülür.** `SleevePlan`: `P0 = quantize(initial_capital, 0.01)`,
  `R0 = P0 * max(r,0)/100`, `A0 = max(0, P0−R0)`, `Ci0 = A0*wi/100`, `U0 = A0 − ΣCi0`.
  `A0`/`Ci0`/`U0` `__post_init__`'te **türetilir** (tutarsız yayımlanamazlar). `R0` **nominal
  TUTAR** olarak tutulur — aşağı akışta hiçbir şey yüzdeyi sonraki equity'ye yeniden
  uygulayamaz (doc 13 §6.1: *"Reserve orani her barda current equitye yeniden uygulanmaz"*).
  `P0<=0`, negatif share ve toplam share>100 **reddedilir**; üçü de kanonik blocker.
* **`E(t) = P0 + realized − fees − funding − other`, YALNIZ REALIZED** (doc 13 §8.3).
  Unrealized hareket kanonda `E(t)`'nin dışındadır, dolayısıyla mark ona **asla** dokunmaz.
* **Muhasebe kimliği YAPIYLA kesin.** Her booking deltasını sevk edilmiş **artımlı** quantize
  ile uygular (`quantize(equity + delta, 0.01)` — `booking.py:96`, `engine.py:1953`) ve kovaya
  **gerçekten uygulanan** deltayı yazar. Bu yüzden `accounting_identity == equity` her noktada
  sent sente doğrudur ve `equity` sevk edilen öğe-başı defterle byte-özdeştir. Kovaları bağımsız
  toplayıp okurken çıkarmak **eşdeğer değildir**: yuvarlama, kuantumun tam katı boyunca yalnız
  half-even tie-break'i uyuştuğunda öteleme-değişmezdir. Somut karşı-örnek (testle pinli):
  equity `10000.01` iken `0.005`'lik fee toplamı `10000.005` yapar, tie **çift** olan
  `10000.00`'a düşer → **tam bir cent** uygulanır; aynı fee **kendi başına** yuvarlanınca
  `0.00`'dır (0 çifttir) → bağımsız toplanan `fees` ilk fill'den itibaren bir cent şaşardı.
* **Spread/slippage fill fiyatının İÇİNDEDİR** (`costs._effective_fill`) ve ikinci kez maliyet
  satırı olarak yazılmaz — her fill'i çift sayardı. Ayrı satırlar: commission (`fees`),
  funding, `other_realized_costs` — doc 13 §8.3'ün tam ayrımı.
* **`publish_snapshot` defteri DONDURUR** (`begin_apply`'a kadar `LedgerFrozenError`). ADR
  §8.1'in *"FROZEN: no writer may run until P7"*'si disiplin değil **yapı** oldu; "her öğe aynı
  `E(t)`'yi okudu" faz sırasını yanlış kuran bir çağıran tarafından ihlal edilemez. Başka bir
  tick'in snapshot'ıyla kapasite sorusu `MismatchedSnapshotError` verir (sleeve headroom'u
  snapshot'tan, solvency headroom'u defterden gelir — sorunun yarısını her birinden yanıtlamak
  reddedilir).
* **`resolve_capacity` = P6b.** `min(desired, remaining_sleeve, item_risk_limit,
  exposure_headroom)` **CLAMP** eder; `ledger_solvency` **yalnız REDDEDER** — M11 §5.3 kısmi
  fill ve sessiz borrow'u yasaklar, kırpılmış bir order zaten kısmi fill'dir. Bu yüzden solvency
  **en son**, cap'lerin ürettiği sonuca karşı değerlendirilir. `CapacityDecision` **her**
  katmanın headroom'unu yayımlar, yalnız bağlayanı değil — "bu neden 8 birim" sorusu iz'den
  yanıtlanabilsin diye. Reason token'ları sevk edilmiş sözlükten (`sleeve_zero_capacity`,
  `portfolio_max_total_exposure`) + kapalı `LEDGER_LAYER_REASONS` (4 token).
  `max_position_notional` yalnız **çağıran verirse** uygulanır; otoritesi Strategy Details'tir
  (M11 §6.1 katman 3), ledger uydurmaz.
* **`net_exposure` ÖLÇÜMDÜR.** Hiçbir cap, headroom, solvency veya margin gereksinimi ondan
  türetilmez. NET semantiği kanonda tanımsız (ADR §9.4, GH #544) ve net figürden kapasite
  hesaplamak NET'i **kazara sevk ederdi**. Hedge'li long/short çifti gross'u iki katına çıkarır,
  net'i sıfırlar ve **hiç** sermaye serbest bırakmaz.
* **Konuşlanmış sermaye = entry-basis notional** (`_Position.entry_notional`,
  `sizing._cap_to_sleeve`'in zaten cap'lediği figür) — sevk edilmiş konvansiyon, **yeni bir
  margin modeli DEĞİL**. Kanon maintenance-margin formülü tanımlamıyor; Master Ref §10.2
  `leverage_mode=cross`'u var olmayan bir portföy risk modeline devrediyor (ADR §9.5).
* **No-borrow guard ARTIŞI bağlar**, duran toplamı değil. Equity düştüğünde açık pozisyon
  sleeve'ini aşmış olabilir ve **öyle bırakılır** (doc 13 §8.3/§6.1 — OD-4(a) literal okuması).
  **Yerinde reversal reddedilir:** yönü çevirmek yeni notional'ı eskisiyle netler ve yalnız
  farkı kontrol ederdi; oysa reversal bir taahhüdü bırakıp başka birini alır (motor bunu
  close+open olarak modeller — `positions_replaced`).
* **`valuation()`** açık pozisyonları TEK noktada markler, sonucu `E(t)`'nin **yanında**
  raporlar. Marklanamayan pozisyon `unmarked_items`'a düşer ve `unrealized_pnl` ile her iki
  `marked_*` figürü `None` olur — **asla sıfır değerlenmez**. **OD-2 açık**: `MarkPrice`
  authority ve staleness'ı kaydeder, `stale_after` eşiği **seçmez**.
* **`PortfolioEquityPoint` YENİ bir tiptir.** ADR §7 `state.EquityPoint`'i yeniden kullanmayı
  taslaklamıştı; ama onun `exposure`'ı *kapanan lot'un* notional'ı / kapanış öncesi equity
  demek (`booking.py:100`) — portföy eğrisinin kaydettiği şey değil. Yeniden kullanmak alan
  adlarını koruyup iki alanın anlamını sessizce değiştirirdi. Adaptör (istenirse) ADIM 20'nin.
  Nokta kuralı: **`E(t)`'nin oynadığı her tick'te bir nokta** + run tohumu (ADR §7); kanon
  kardinalite sabitlemiyor (M12 §10) ve `E(t)` realized-only olduğu için her tick'te nokta
  yalnız düz tekrar eklerdi.
* **Rounding versiyonlu:** `LEDGER_POLICY_VERSION = "portfolio-ledger-v1"`, money `0.01`,
  quantity `1e-8`, rounding **`ROUND_HALF_EVEN` açıkça pinli** (ambient context'ten
  devralınmaz; varsayılan altında her golden digest'in üretildiği değerin aynısı). Sleeve
  aritmetiği **quantize edilmez**; yalnız yayımlanan para figürleri quantize olur.
  `allocation/rules.py:51`'in `ROUND_HALF_UP`'ı **display** yuvarlamasıdır, ikinci bir politika
  değil.

### Parity — iddia değil, kontrol

`docs/audit/portfolio_ledger_accounting.md` §4:

| iddia | neye karşı | sonuç |
|---|---|---|
| doc 13 §14 test 10'un `R0`/`A0`/`Ci0`/`U0`'ı | `validate_allocation` → `DerivedAmounts` (kullanıcıya gösterilen **preview**) | sent sente aynı — M11 §5.1 bunu şart koşuyor, bugüne dek hiçbir şey zorlamıyordu |
| `Ci(t)`, compound **ve** fixed | `sizing.sleeve_capital` | 24 vakada özdeş (2 mod × 3 share, `0` dahil × 4 equity, reserve altı biri dahil) |
| sleeve cap sonrası granted units | `sizing._cap_to_sleeve` | 9 vakada özdeş |
| tüm tek-item zinciri | sevk edilmiş sleeve oracle'ının **gerçek `run_engine` replay'i** | özdeş: `44.11764706` birim, `88.24` PnL, `100.088,24` final book |
| sub-cent deltalar altında equity | sevk edilmiş `quantize(equity + delta, 0.01)`'in elle yazılmış kopyası | adım adım özdeş |

**Karşılaştırılacak sevk edilmiş bir şey OLMAYAN yerler** raporda açıkça öyle yazıldı: çok-item
`E(t)` (motorda paylaşılan defter yok), `net_exposure`, marklanmış figürler ve portföy eğrisinin
nokta sayısı (per-trade-close vs per-tick — **tasarımca farklı seriler**).

### Mutasyon kaydı — biri ilk turda hayatta kaldı

12 mutasyon tek tek uygulandı. **M6** (no-borrow guard'ı artış yerine **duran toplamı** bağlar)
tüm suite'i geçti: hiçbir test, havuzun sıfırdan açmaya artık gücü yetmeyen bir pozisyonun
**yeniden boyutlandırılmasını** zorlamıyordu — tam da no-force-rebalance kuralının koruduğu
şekil. `test_only_the_increase_in_committed_capital_is_checked_against_the_pool` sonradan
yazıldı (headroom'u tam tüketen bir scale-in **ve** su altındayken bir küçültme). İkinci tur:
**12/12 yakalandı, 0 hayatta kalan.** Yerinde-reversal guard'ı ise testten değil **gözden
geçirmeden** çıktı; `M12` onunla birlikte eklendi.

### Ölçüm dürüstlüğü

Yerel tam suite koşuldu; coverage kapısı **%93.09** ile geçti (kapı ≥90, yeni modül **%98.8**),
log'da hiçbir failure satırı yok. **Ama koşu arka planda başlatıldığı için pytest'in özet satırı
ve exit code'u YAKALANMADI** — CLAUDE.md'nin *"çıktıyı dosyaya yaz, `$?`'i ayrı oku"* uyarısına
uyulmadı ve bekleme döngüsünün exit code'u pytest'inki sanıldı. **Otorite CI'dır:**
`Backend — lint, type, test` **pass**, 42m42s. Yerel kapılar ayrıca temiz: `ruff check .`,
`ruff format --check .`, `mypy src`, `openapi_export --check`.

### Kapsam dışı (bilerek)

Faz döngüsü (ADIM 18), cross-item arbitrasyon / NET / **OD-3** (ADIM 19), manifest alanları +
`ENGINE_VERSION` bump (ADIM 20), mark policy (**OD-2**), margin/cross (ADR §9.5). **ADR 0002
hâlâ `Proposed`** ve §16 onay şartı koşuyor; ADIM 15, 16 ve 17'nin üçü de kayıtlı onay olmadan
indi.

**Rollback:** `git revert`. Üretimde modülü import eden yok
(`test_nothing_in_production_imports_the_shared_ledger_yet` üç import yazımını da kapsar).

---

## ADIM 18 (sevk edilen sıra) — Cross-item intent arbitrasyonu (PR #575)

> **Geriye dönük kayıt.** Bu slice'ın kapanış ritüeli zamanında yapılmadı; bölüm PR #575'in
> **gerçek diff'i ve CI kaydı okunarak** sonradan yazıldı. Zamanında ölçülmemiş hiçbir sayı
> burada uydurulmadı — kayıt olmayan yerde açıkça öyle yazılıyor.

**Commit `df0082e` → squash-merge `9739466`** (2026-08-05T09:08:51+03:00) · base `1430b28` ·
branch `feat/portfolio-cross-item-arbitration` · **+2257 / −14, 6 dosya** · **Migration YOK**
(alembic head `0043_i08_registry_strategy_fks`) · **OpenAPI DEĞİŞMEDİ** · **`ENGINE_VERSION`
DEĞİŞMEDİ** (`backtest-engine-v18-gap-adjusted-stop-fill`; **46 golden digest sabit**) ·
**CI 6/6 SUCCESS** (Backend job 43m40s).

**⚠ Numaralandırma — bu başlıktaki "ADIM 18" ADR §12'nin ADIM 18'i DEĞİL.** PR #575 kendine
ADIM numarası vermedi (gövdesi yalnız *"ADR 0002 §9, phases P5/P6b… the fourth slice"* der).
ADIM 17 kapanışı arbitrasyonu **"ADIM 19"** diye rezerve etmişti; sonradan inen PR #581 ise
kendini **"ADIM 19"** ilan etti. Sevk edilen sıra bu yüzden 15=clock, 16=intents, 17=ledger,
**18=arbitration**, 19=provenance diye okunuyor — ama **ADR §12'nin ADIM 18'i `run_portfolio`
faz döngüsüdür ve hâlâ yazılmadı**. Başlıktaki numara sevk sırasıdır, ADR tablosuna uyum
iddiası değil; §12 sapması açık bir insan kapısı olarak duruyor.

| dosya | |
|---|---|
| `backend/src/entropia/domain/backtest/execution/arbitration.py` | **yeni**, 919 satır |
| `backend/tests/unit/test_backtest_cross_item_arbitration.py` | **yeni**, 1145 satır / **41 fonksiyon, 44 vaka** |
| `docs/audit/cross_item_conflict_policy.md` | **yeni**, 171 satır — politika tablosu + NET yetenek durumu |
| `backend/tests/unit/test_backtest_item_intents.py` | intents containment testi **bilerek** güncellendi (+13/−9) |
| `backend/tests/unit/test_backtest_portfolio_ledger.py` | ledger containment testi **bilerek** güncellendi (+12/−4) |
| `docs/CODEMAPS/BACKEND_LAYERS.md` | `execution/arbitration.py` satırı (+1/−1) |

### Ne getirdi

ADR 0002 §9'un **P5 (cross-item conflict)** ve **P6b (capacity)** fazları. Saf ve contained:
**hiçbir üretim modülü import etmiyor**
(`test_nothing_in_production_imports_the_arbitration_layer_yet`), `run_engine` imzası **ve**
semantiği aynı kaldı — hiçbir replay oynamıyor. Modülde `await` yok, session yok, query yok:
koşudan sonra düzenlenen bir plan, geçmiş bir raporun nasıl çözüldüğünü değiştiremez
(doc 13 §11.1).

### Sözleşmeler (tercih değil, kural)

* **Politika tablosu `CONFLICT_POLICY_TABLE`** (`ConflictPolicyRule`, kanonik wire token'ıyla
  anahtarlı): `KEEP_SEPARATE` karşıt yöne **izin verir**, `BLOCK_OPPOSITE` **bloklar**, `NET`
  **reddedilir**. **`shares_capital` her satırda `True`** ve varsayılmak yerine **yazılıyor**:
  `KEEP_SEPARATE` pozisyon **defterlerini** ayırır, havuzu değil. Sleeve cap, kompozisyon-geneli
  Max Total Exposure ve solvency limiti **her politika altında aynı** uygulanır (Modül 11 §6.1)
  — testle pinli.
* **`NET` düşürülmedi, REDDEDİLDİ.** Sevk edilen sıralı motor `NET`'i `BLOCK_OPPOSITE` olarak
  koşup bunu ifşa ediyor (`engine.py:862-871`, `CONFLICT_POLICY_NET_V1`); **bu düşürme ileri
  taşınmadı**. `resolve_policy("NET")` herhangi bir karar oluşmadan
  `UnsupportedConflictPolicyError` fırlatır; `NET_UNDEFINED_SEMANTICS` reddin gerekçesi olarak
  beş tanımsız semantiği adlandırır: netleme fiyatı · pozisyon custody'si · fee attribution ·
  realized-PnL attribution · margin/collateral (sonuncusu var olmayan cross-margin modeline
  bloke — Master Ref §10.2 / ADR §9.5). **Bilinmeyen token da reddedilir**: sevk edilen kapı
  onu blokla*maya* fail-closed eder, yani kimsenin adlandıramadığı bir politikayı koşar;
  reddetmek hiç Result üretmez. `NET_SUPPORT_STATUS = "undefined_in_canon"`. Sevk edilen yol
  dokunulmadı (`test_the_shipped_sequential_conflict_gate_is_untouched`).
* **Tutulan pozisyon, pin ordinali ne olursa olsun KAZANIR.** Sevk edilen kural ileri-yönlüydü
  (*"EARLIER-pinned holder blocks a LATER-pinned entry"*) — çünkü sıralı döngü daha sonraki bir
  öğenin pozisyonunu **fiziksel olarak göremez**. Birleşik eksen görebilir, dolayısıyla
  pin-sırası yarısı kural olmaktan çıkıp artefakta dönüşür; ADR §12 onu bu slice'ta emekliye
  ayırır. Kanonun söylediği, çatışma kurallarının iki öğenin **karşıt pozisyon AÇMASINI**
  sınırladığıdır (Modül 11 §6.3); doc 13 §8.3 açık bir pozisyonu zorla rebalance etmeyi
  yasaklar — kardeşin pozisyonunu kapatıp yer açmak kanonun sunduğu bir sonuç değildir.
* **Aynı tick'te iki intent → düşük `(pin_ordinal, item_id)` kabul edilir.** ADR §4.4'ün
  tie-break'i, **pinli manifest'ten** okunur; DOM, geliş veya DB sırası asla değil (doc 13 §13).
  Çağıranın girdi sırasının üç permütasyonu **özdeş karar demeti ve özdeş digest** üretir.
* **Bilinmeyen enstrüman kimliği fail-closed.** İki BİLİNEN farklı enstrüman çatışamaz; başka
  her şey çatışabilir. Sevk edilen L4 token'ı `portfolio_conflict_symbol_unknown_fail_closed`
  diagnostics'e yazılır — **ikinci bir reason olarak değil**; okuma
  `execution/rules.py::conflicts_with_prior`'dan birebir.
* **Zorunlu P3 intent'i asla arbitre edilmez** (`MandatoryIntentNotArbitrableError`). Test
  edilmiş sonuç: `t` anında ateşleyen bir stop pozisyonunu `PV`'den **önce** bırakır, bu yüzden
  karşıt öğenin aynı `t`'deki girişi kabul edilir — istisnayla değil, **çatışacak bir şey
  kalmadığı için**.
* **`arbitrate()` yazılabilir defter üzerinde koşmayı REDDEDER** (`LedgerNotFrozenError`).
  P5/P6b `PV` ile `P7` arasındadır (ADR §8.1); donmamış defterde bir kardeşin booking'i, hâlâ
  arbitre edilen öğelerin altından `E(t)`'yi kaydırabilirdi.
* **Tutulan pozisyon taraması karşı tarafın PİNLİ önceliğine göre sıralıdır**,
  `ledger.positions` insertion order'ına göre değil: atfedilen karşı taraf bir **sonuçtur** ve
  ADR §4.4 dict iterasyonunun bir sonucu belirlemesini yasaklar.

### Kapasite çekişmesi — ve OD-3'ün açık bıraktığı

Defter `PV`–`P7` arası donuk olduğu için `available_capital` **her öğe için aynı** figürü okur;
koşan bir sayaç olmasa iki öğeye de havuzun tamamı verilirdi. Arbitrasyon bu sayacı tutar ve hem
solvency headroom'undan hem exposure cap'inden düşer.

* Cap katmanları **CLAMP** eder — `capped` bir sonuç daha küçük **kabul edilmiş boyuttur**,
  kısmi fill değil (doc 13 §14 test 13).
* Solvency **bütün olarak REDDEDER** — Modül 11 §5.3: *"engine orderi reddeder, kismi fill veya
  sessiz borrow yapmaz"*. "1000 kaldı, 1000'i al" mevcut bir yanıt değildir.
* **Bloklanan öğenin kapasitesi kardeşine ASLA devredilmez.** Döngü yalnızca çıkarır; test bunu
  hayatta kalanın grant'ini bloklanan öğe **varken ve yokken** karşılaştırarak kanıtlar.

> **OD-3 AÇIK ve etiketlenmiş, sessizce benimsenmiş değil.** Kanon açığa verilecek **yanıtı**
> belirler (reddet; asla kısmi, asla borrow), **hangi** intent'in reddedileceğini değil. ADR'nin
> tavsiyesi `CONTENTION_SELECTION_POLICY = "pin_order_admission"` olarak sevk edildi ve
> `CONTENTION_SELECTION_STATUS = "recommended_pending_approval"` **her raporda ve çekişmeli her
> kararda taşınır** — böylece bu kural altında üretilmiş bir Result, farklı bir çözümle
> üretilmişten her zaman ayırt edilebilir. Bir gözden geçirenin tercih edebileceği alternatif
> (**tüm** rakip intent'leri reddet) `docs/audit/cross_item_conflict_policy.md` §3'te kayıtlı.

### Yeni sözcük dağarcığı YOK

Bu katmanın ürettiği her reason, sevk edilen motorun ya da paylaşılan defterin **zaten yazdığı**
bir token: `portfolio_conflict_blocked`, `sleeve_zero_capacity`, `portfolio_max_total_exposure`
ve `LEDGER_LAYER_REASONS`'ın dördü. `ARBITRATION_REASONS` tam olarak bu küme üzerinde kapalıdır
ve bir test bunu doğrular. **Yeni olan hangi öğenin reddedildiğidir, ne tür bir reddin var
olduğu değil** — yeni bir sözlük yalnızca tek bir bulguya iki ad verirdi.

### Ölçüm dürüstlüğü

**Otorite CI'dır:** `Backend — lint, type, test` **pass, 43m40s**; CI **6/6 SUCCESS**.
PR gövdesinde kayıtlı **yerel** ölçüm (izole worktree DB'si, tek pytest çağrısı, exit code
**ayrı** okunmuş — ADIM 17'nin hatası tekrarlanmamış): **exit 0**, **0 FAILED / 0 ERROR**,
coverage **%93.15** (kapı ≥90), `arbitration.py` **%99.1** (233 statement, 2 kapsanmayan);
`ruff check src/ tests/` temiz, `mypy src` 389 dosyada temiz.

**Bu slice'ta mutasyon turu kaydedilmedi.** ADIM 17'nin 12 mutasyonu ve ADIM 19'un 10 mutasyonu
gibi bir kayıt PR #575'te **yok**; sonradan da koşulmadı. Bu bir eksiklik olarak yazılıyor,
geriye dönük bir sayı uydurulmuyor.

### Kapsam dışı (bilerek, ki kimse aksini çıkarmasın)

Faz döngüsü / `run_portfolio` · **Result attribution ve diagnostics kalıcılığı** (reddedilen ve
kısmi kararlar `item_id`, reason, karşı taraf ve bağlayıcı katmanı taşıyan **typed değerler**
olarak üretilir — bir Result'ın kaydetmesine hazır, ama burada hiçbir şey yazmıyor) ·
**manifest alanları** (`arbitration_policy_version` `ENGINE_VERSION` bump'ıyla gelir, ADR §10.3;
bir test onun `manifest.py`'de **hâlâ yok** olduğunu doğrular) · **containment lift**
(`SHARED_ALLOCATION_STATUS = "future_dev"` kaldı) · cross-margin / netting (ADR §9.4, §9.5) ·
**OD-2** (taze barı olmayan pozisyonun markı) — arbitrasyon fiyatları intent'lerden okur ve mark
politikası **seçmez**.

**ADR 0002 hâlâ `Proposed`** ve §16 uygulamayı onaya bağlıyor; ADIM 15, 16, 17'nin ardından bu
slice de **kayıtlı onay olmadan** indi.

**Rollback:** `git revert` — "modülü sil" ile eşdeğer. Üretimde import eden yok; `ENGINE_VERSION`,
46 golden digest, alembic head, OpenAPI snapshot ve frontend dokunulmadı.

---

## T-02 — Ajan tooling: ponytail merdiveni + SAST skill alt kümesi (kod dışı slice)

**Bu bir stage slice'ı DEĞİL.** Migration yok, endpoint yok, tablo yok, `ENGINE_VERSION`
değişmedi, backend/frontend kaynak kodu hiç değişmedi. Yalnızca ajan operasyon katmanı.

**Değerlendirilen dört repo, verilen karar:**

| Repo | Karar | Gerekçe |
|---|---|---|
| `dietrichgebert/ponytail` (MIT, v4.8.4) | **Uyarlanarak alındı** | 7 basamaklı "tembel merdiven"in 2. basamağı (codebase'de zaten var mı) Entropia'nın REUSE-anchor disiplinine birebir oturuyor |
| `utkusen/sast-skills` (MIT, fork: alimirbagirzade) | **10/16 skill alındı** | Kaynak-kod odaklı; mevcut 754 cybersecurity skill'i daha çok pentest/ops tarafı |
| `rebelytics/one-skill-to-rule-them-all` (CC BY 4.0) | **Alındı (`task-observer`)** | claude-mem + `ecc:learn` ile örtüşüyor ama mekanizması farklı (oturum sürtünmesinden skill üretimi) |
| `Egonex-AI/Understand-Anything` (MIT) | **REDDEDİLDİ** | `codebase-memory-mcp` (~13k node/59k edge) + `docs/CODEMAPS/` aynı işi yapıyor; kurmak npm bağımlılığı + 35 MB + tazeliği korunacak ikinci bir graf demekti — merdivenin 5. basamağı |

**Ponytail'in Entropia ile üç gerçek çatışması** — bu yüzden upstream ruleset düz
alınmadı, `.claude/skills/ponytail-entropia/SKILL.md` içine **override tablosu** yazıldı:

1. Upstream "tek runnable check yeter, framework/fixture yok" der → burada
   `--cov-fail-under=90` **kapıdır**, her yeni `create_*` için L1 FK insert-order proof +
   alembic `<n>` up/down/up + migration↔model kolon paritesi zorunludur.
2. Upstream "en az dosya, istenmemiş soyutlama yok" der → burada
   `commands`/`queries`/`domain`/`routes` ayrımı, tek-tx no-commit, `run_idempotent`,
   `session.refresh(with_for_update=True)`, `_audit_and_outbox` **mecburi desendir**.
3. Upstream "en kısa diff kazanır" der → O-30'un `deletion_state` + `root_lifecycle_state`
   ikilisi, O-02'nin `suggested_action` + `remediation` ayrımı ve O-12'nin dual-token
   uzlaştırması **tekrar gibi görünen adjudicated kararlardır**; silinmeleri sözleşmeyi bozar.

Override tablosu ayrıca şunları pazarlık dışı sabitler: `reconcile_occ_tokens`,
`assert_supported_source_file` fail-closed kapısı, `TRASH_OBJECT_LOCATIONS` yazma zorunluluğu,
typed response modeli (bare `dict` sözleşmeyi şemadan gizler), v18 mockup otoritesi ve
kapanış ritüeli dokümanlarının "açıkça istenmiş çıktı" sayılması.

**Kurulan (global `~/.claude/skills/`, v4.8.4'e pinli, `PROVENANCE.txt` ile):**
`ponytail`, `ponytail-review`, `task-observer`, ve `sast-analysis`, `sast-report`,
`sast-idor`, `sast-missingauth`, `sast-businesslogic`, `sast-fileupload`,
`sast-pathtraversal`, `sast-sqli`, `sast-xss`, `sast-hardcodedsecrets`.

**Kurulmayan 6 SAST skill'i — yüzey ampirik olarak doğrulandı, karşılığı yok:**
`graphql` (grep: 0), `xxe` (XML parser yok), `ssti` (template render yok), `rce`
(`subprocess`/`os.system`/`eval` yok), `jwt` (auth session-tabanlı: `shared/passwords.py` +
revocable session), `ssrf` (giden HTTP çağrısı yok).

**Bilerek yapılmayanlar (dürüst sınır):**
- Upstream ponytail **plugin/hook'ları kurulmadı**. SessionStart/SubagentStart/
  UserPromptSubmit'te üçüncü-parti Node script'i koşuyor, `~/.claude`'a flag yazıyor ve
  ajana "kullanıcıya statusLine kurmayı proaktif öner" talimatı enjekte ediyor. Bu
  *her projede her zaman* açık olurdu; istenen "gerektiğinde"ydi. `~/.claude/settings.json`
  **hiç değiştirilmedi**.
- README'nin *%54 daha az satır / %22 daha az token* rakamları **reponun kendi benchmark'ı**
  ve greenfield FastAPI+React görevlerinden. Entropia spec'in şekli dikte ettiği bakım işi —
  bu kazanç burada beklenmemeli. Ölçülmedi.
- `sast-*` skill'leri 3'lük batch'lerde **paralel subagent** açıyor; CLAUDE.md'nin
  "no unnecessary parallel agents" kuralıyla gerilimde. Tek vuln tipiyle başla.
- `task-observer` gözlem log'u **stabil yola** yazmalı; `.claude/worktrees/` altındaki
  geçici checkout ile birlikte silinir.

**Otomatik tetikleme:** skill'ler `description` eşleşmesiyle devreye girer; ek olarak
`~/.claude/rules/skill-routing.md`'ye yönlendirme bloğu eklendi (kod yazmadan önce →
ponytail; auth/rol → sast-missingauth; upload → sast-fileupload; OCC/idempotency →
sast-businesslogic; çok adımlı oturum → task-observer).

**Yan bulgu:** PR #575 (`arbitration.py`) kod olarak indi ama `CLAUDE.md §Current position`
güncellenmedi — HEAD hâlâ `f8f96c5` yazıyordu. Bu slice'ta düzeltildi. **ADIM 18
(`run_portfolio` faz döngüsü) hâlâ açık**; #575 arbitration'dır, faz döngüsü değil.
ADR 0002'nin `Proposed` durumu ve §12 numaralandırma sapması da açık kalmaya devam ediyor.

**Rollback:** `git revert` + `rm -rf ~/.claude/skills/{ponytail,ponytail-review,task-observer,sast-*}`
ve `~/.claude/rules/skill-routing.md`'deki blok. Üretim kodu etkilenmediği için risk yok.

---

## ADIM 19 — Unified-clock result provenance + per-item attribution (PR #581)

> **Geriye dönük kayıt.** ADIM 18 gibi bu slice'ın da kapanış ritüeli zamanında yapılmadı;
> bölüm PR #581'in **gerçek diff'i ve CI kaydı okunarak** sonradan yazıldı. Zamanında
> ölçülmemiş sayılar uydurulmadı — **coverage yüzdesi ve suite toplamı bu PR'da hiç
> kaydedilmedi**, aşağıda §Ölçüm dürüstlüğü'nde öyle yazıyor.

**Commit `89cf0b6` (+ `7fcf3ea`, `61da506`) → squash-merge `b0bb4a0`**
(2026-08-05T12:37:21+03:00) · base `9739466` · branch `feat/portfolio-unified-result-artifacts` ·
**+3199 / −9, 23 dosya** · **Migration YOK** (alembic head `0043_i08_registry_strategy_fks`) ·
**OpenAPI snapshot BYTE-ÖZDEŞ** · **`ENGINE_VERSION` DEĞİŞMEDİ**
(`backtest-engine-v18-gap-adjusted-stop-fill`; **46 golden digest sabit, `contract.execution_key`
dahil**) · **CI 6/6 SUCCESS** (Backend job 45m45s). Tam kanıt:
`docs/audit/portfolio_result_provenance.md`.

**Bu, unified-clock programının ÜRETİME dokunan ilk slice'ıdır.** ADIM 15–18 tamamen contained'dı;
burada iki contained modülün yanında **gerçekten sevk edilen** bir okuma-zamanı etiketi indi
(`portfolio_mode.py` + iki query + repo + üç frontend dosyası). **Containment yine de
KALDIRILMADI:** `SHARED_ALLOCATION_STATUS = "future_dev"`, shared koşular admission'da hâlâ
reddediliyor.

| dosya | |
|---|---|
| `backend/src/entropia/domain/backtest/execution/provenance.py` | **yeni, contained**, 542 satır |
| `backend/src/entropia/domain/backtest/execution/attribution.py` | **yeni, contained**, 406 satır |
| `backend/src/entropia/domain/backtest/portfolio_mode.py` | **yeni, ÜRETİM**, 206 satır |
| `backend/src/entropia/infrastructure/postgres/repositories/backtest.py` | `get_run_diagnostics_markers` + `get_portfolio_mode_markers` (+88) |
| `backend/src/entropia/application/queries/backtest_run.py` | Result detail'e `portfolio_simulation` (+9) |
| `backend/src/entropia/application/queries/results_history.py` | history index'e batched mode (+25) |
| `backend/tests/unit/test_backtest_portfolio_provenance.py` | **yeni**, 508 satır / 23 fonksiyon, **26 vaka** |
| `backend/tests/unit/test_backtest_portfolio_attribution.py` | **yeni**, 327 satır / 21 fonksiyon, **25 vaka** |
| `backend/tests/unit/test_backtest_portfolio_mode.py` | **yeni**, 220 satır / 16 fonksiyon, **22 vaka** |
| `backend/tests/integration/test_portfolio_simulation_mode.py` | **yeni**, 198 satır / **7 vaka** |
| `frontend/src/test/portfolioSimulationMode.test.tsx` | **yeni**, 177 satır / **6 vaka** |
| `frontend/src/lib/backtest.ts` · `pages/ResultsHistory.tsx` · `components/ResultDetail.tsx` | tip + iki render noktası (+28 / +12 / +32) |
| `docs/audit/portfolio_result_provenance.md` | **yeni**, 372 satır |
| dört mevcut containment testi + iki frontend testi | **bilerek** güncellendi (aşağıda) |
| `docs/CODEMAPS/BACKEND_LAYERS.md` · `BACKEND_ROUTES.md` | (+1/−1) · (+2) |

### İki boşluk, kod yazılmadan ÖNCE reprodüksiyonla kanıtlandı

**Boşluk A — kanonun istediği allocation provenance'ının yaşayacağı yer yoktu.**
`validate_allocation` doc 13 §13 / Modül 11 §10'un istediği her figürü **zaten hesaplıyor** ve
`_resolve_allocation` (`readiness_check.py:846`) onu **atıyor**. doc 13 §14 test 10 fikstüründe
(10.000 USDT, reserve %10, 40/35/15) probe çıktısı: `reserved_cash 1000.00 ·
capital_available 9000.00 · sleeve 3600.00 / 3150.00 / 1350.00 · unallocated 900.00`, buna karşılık
`manifest['capital_execution']` anahtarları yalnız `[config, config_hash, enabled, plan_id,
plan_revision_id]` — `initial_sleeve_capital` ve `engine_allocation_policy_version` manifest
JSON'ının **hiçbir yerinde yok**.

**Boşluk B — per-item unrealized attribution hiç yoktu.** Defterin realized kimliği tutuyor
(`482.50 == 482.50`), ama `ItemAttribution`'da `unrealized` alanı, `PortfolioValuation`'da
per-item satır yok — yani per-item döküm **marklanmış** bir portföy toplamıyla mutabakat
edilemiyordu.

### Ne indi

**Contained (üretimde import eden yok; rollback = `git revert`):**

* **`execution/provenance.py`** — `build_portfolio_manifest` → `PortfolioManifest`. Her politika
  versiyonunu pinler (clock / intent / ledger / arbitration / allocation / attribution), öğe
  sırasını, allocation revision'ını, conflict policy'yi, zaman hizalamasını, per-item data
  revision'larını ve **tam item revision**'larını; artı değişmez bir ledger-artefakt referansı +
  checksum (`LedgerArtifactRef`, `ledger_artifact_ref`, `ledger_equity_rows`). Kanon alan adları
  Modül 11 §10'dan **birebir**; `test_the_allocation_block_uses_canon_field_names_verbatim` tam
  anahtar kümesini pinler. **Tutarlar KOPYALANIR, yeniden hesaplanmaz**: donmuş
  `PortfolioAllocationPlanRevision.derived_amounts` projeksiyonu
  (`allocation_provenance_from_derived`, `AllocationProvenance`, `SleeveProvenance`). Independent
  mod **açıkça** `enabled=false` yazar (`independent_allocation_provenance`) — eksik blok "off"
  değil "unknown" okunurdu. Pinli öğe listesi: `PinnedItem`, `pinned_items_from_identities`,
  `item_labels_from_identities`. Versiyon sabitleri: `PORTFOLIO_MANIFEST_VERSION =
  "portfolio-manifest-v1"`, `ENGINE_ALLOCATION_POLICY_VERSION = "portfolio-allocation-v1"`.
* **`execution/attribution.py`** — `attribute` → `PortfolioAttribution` / `ItemContribution`:
  per-item realized / unrealized / costs / contribution, portföy toplamıyla **tam mutabakat**
  (residual `0`; sıfırdan farklı bir realized residual **`AttributionResidualError` fırlatır**,
  tolerans değildir). `ATTRIBUTION_POLICY_VERSION = "portfolio-attribution-v1"`,
  `CONTRIBUTION_METHOD = "additive_pnl_decomposition"`; marklanamayan pozisyon
  `UNMARKED_POSITION` ile raporlanır. Katkı serisi ve korelasyon: `contribution_series`,
  `ContributionSeries`, `contribution_correlation`, `build_contribution_report`,
  `ContributionReport`, `pearson`.

**Üretim:**

* **`domain/backtest/portfolio_mode.py`** — kalıcı bir Result'ı **kendi pinli manifest'i + kendi
  pinli diagnostics'i** üzerinden `single_item` / `legacy_sequential` / `unified_clock` /
  `unknown` diye sınıflandırır (`resolve_portfolio_simulation_mode`, `resolve_mode_from_parts`,
  `portfolio_simulation_context`, `portfolio_simulation_context_from_parts`). **Canlı
  kompozisyondan ve canlı capability bayrağından ASLA okumaz** — bayrağı çevirmek yazılmış bir
  Result'ı yeniden etiketleyemez (ADR §10.4, doc 13 §14 test 19). Marker'lar
  `UNIFIED_MANIFEST_KEY = "portfolio_simulation"` + motorun kendi pinli `engine_kind`'ı
  (`SINGLE_ITEM_ENGINE_KIND = "v1_bar_replay"` → `execution/output.py:369`;
  `COMPOSITION_ENGINE_KIND = "v1_bar_replay_composition"` → `execution/portfolio.py:570`).
* **`GET /backtest-results/{id}` ve `GET /backtest-results`** ikisi de
  `portfolio_simulation = {mode, note, comparable_with_unified_clock}` döner; Result detail ve
  Results History bunu render eder (`PORTFOLIO_SIMULATION_LABELS`, `PortfolioSimulationContext`).
  Repo tarafı **N+1 değil**: `get_run_diagnostics_markers` tek satırda iki JSONB path extract'ı
  (tam `diagnostics` blob'u okumaz — çok-item Result'ta o blob her öğenin tüm equity eğrisini
  taşır), `get_portfolio_mode_markers` sayfa başına **iki batched read** (`_load_digests` /
  `_load_summaries` deseninin aynısı). Bir test index'in **tek** batched marker okuması
  yaptığını ve liste ile detail'in **özdeş** `portfolio_simulation` gövdesi döndürdüğünü
  doğrular.

### Üç karar (gözden geçirmeye değer)

1. **`ENGINE_VERSION` BUMP EDİLMEDİ.** Koşan davranış değişmedi; bump `execution_key` namespace'ini
   kaydırır ve **mevcut her Result'ı idempotent yeniden-RUN için yeniden kullanılamaz** hâle
   getirirdi — hiçbir sayıyı değiştirmeyen bir değişiklik için gerçek bir regresyon.
   `engine_golden_digests.json` dokunulmadı. Bump containment-lift slice'ının.
2. **Görünen etiketler hash'in DIŞINDA.** `identity` yalnız `execution_content()`'i hash'ler;
   öğe etiketleri `presentation`'da yolculuk eder — `manifest.pinned_item_labels`'ın zaten
   yaptığı ayrımın aynısı (`manifest.py:160-185`). Bir yeniden adlandırma bir koşunun
   tekrarlanabilirlik kimliğini **asla** çatallamamalı
   (`test_the_manifest_identity_ignores_display_labels`).
3. **Karşı-olgusal marjinal UYDURULMADI.** Paylaşılan saatte leave-one-out, portföyü o öğe
   olmadan **yeniden simüle etmeyi** gerektirirdi; kanon formül tanımlamıyor. Artefakt tam
   **toplamsal** ayrıştırmayı taşır ve eksikliği yüksek sesle kaydeder:
   `COUNTERFACTUAL_MARGINAL_STATUS = "not_derivable_without_re_simulation"`.

**Açık kararlar tahmin edilmedi, İFŞA EDİLDİ:** OD-2 `MARK_STALENESS_POLICY =
"undefined_pending_od2"` olarak pinlendi — ADIM 18'in OD-3 için kurduğu
`arbitration.CONTENTION_SELECTION_STATUS` emsalinin aynısı. `attribution.py` bu yüzden
**stale-ama-kullanılabilir** bir markı değerler ve bir staleness eşiği icat etmeyi reddeder.

### İki bulgu

1. **Preview ve execution aynı sleeve'i FARKLI yuvarlıyor.** `allocation.rules._money`
   `ROUND_HALF_UP`; `portfolio_ledger.MONEY_ROUNDING` `ROUND_HALF_EVEN`. `1000.10 @ %25`'te
   preview **`250.03`**, execution **`250.025`** der. doc 13 §13 tam olarak bu uyuşmazlığı
   yasaklıyor ve **hiçbir kanon kuralı bir tarafı kazandırmıyor** — bu yüzden manifest donmuş
   preview sayısını tutar ve `sleeve_amount_divergences()` (`SLEEVE_AMOUNT_DIVERGENCE =
   "sleeve_amount_preview_execution_divergence"`) anlaşmazlığı sessizce bir tarafı tercih etmek
   yerine **raporlar**. *Ürün kararı gerekiyor.*
2. **Tek-item Result, teşhissiz bir Result'tan ayırt EDİLEMİYORDU.** İnceleyerek değil, **düşen
   bir entegrasyon testiyle** bulundu: tek-item bypass'ı **hiç** `composition` bloğu yaymıyor,
   dolayısıyla tek başına `strategy_count` "bir öğe koştu" ile "diagnostics hiç saklanmadı"yı
   ayıramıyordu. Motorun kendi pinli `engine_kind` marker'ıyla çözüldü.

### Değişmeyen sınırlar (her biri testle pinli)

`ENGINE_VERSION` · `SHARED_ALLOCATION_STATUS = "future_dev"` · `engine_golden_digests.json`,
`manifest.py`, `capability.py`, `docs/openapi.json` — dokunulmadı · migration yok, alembic head
sabit · `run_engine`, fill modeli, sizing zinciri, `combine_item_runs` — dokunulmadı · export
sözleşmesi (`EXPORT_SCHEMA_VERSION`, `compute_export_checksum`) **bilerek** değişmedi, çünkü mode
bir **okuma-zamanı etiketidir, artefakt içeriği değil**. Dört mevcut containment testi
**bilerek** güncellendi (her biri yeni contained importer'ı açıkça adlandırır, assertion
gevşetilmez), iki yenisi eklendi
(`test_nothing_in_production_imports_the_provenance_layer_yet`,
`…_the_attribution_layer_yet`).

### Ölçüm dürüstlüğü

**Otorite CI'dır:** `Backend — lint, type, test` **pass, 45m45s**; CI **6/6 SUCCESS**
(A11Y, Docker, iki E2E ve Frontend jobları dahil).

**Mutasyon testi: 10 kasıtlı kusur tek tek enjekte edildi, 10'u da öldürüldü.** (M3 ilk turda
*pattern not found* raporladı — `ruff format` sonrası bayatlamış bir harness literali; gerçek
kaynağa yeniden uygulandı ve öldürüldü. **Bayat pattern tasarım gereği hayatta kalan sayılır,
asla "geçti" değil.**) Parity **yeniden ifade edilmedi, sevk edilen kod ÇAĞRILARAK kanıtlandı**:
sleeve tutarları `validate_allocation`'ı, korelasyon `portfolio._pearson`'ı, ledger checksum'ı
`artifacts.compute_artifact_checksum`'ı çağırır.

**KAYDEDİLMEYEN:** PR #581 gövdesi ne **coverage yüzdesi**, ne **suite toplam sayısı**, ne de
yerel `pytest` özet satırı bildiriyor — ADIM 18'in `%93.15`'i ve ADIM 20'nin `%93.24`'ü gibi bir
figür bu slice için **hiç ölçülmedi/yazılmadı**. Buraya geriye dönük bir sayı konmadı; coverage
kapısının bu commit'te geçtiğinin tek kanıtı **yeşil CI job'ıdır**. Yeni test vakaları sonradan
sayıldı: **80 yeni backend vakası** (26 provenance + 25 attribution + 22 mode + 7 entegrasyon) +
**6 yeni frontend vakası**.

### Dürüst sınırlar

1. **Unified faz döngüsü YOK.** ADR §12'nin ADIM 18'i (`run_portfolio`) hiç yazılmadı — PR #575
   yerine arbitrasyonu indirdi. Bugün hiçbir şey unified bir Result üretmiyor, dolayısıyla
   `unified_clock` **üretimde erişilemez** ve yalnız sentetik pinli manifest'li testlerle
   sınanıyor. Parser'ın şekli üreticiden **önce** kabul etmesi gerekiyordu — ama bu
   *"unified koşular çalışıyor"* diye okunmamalı.
2. **`portfolio_simulation` OpenAPI şemasında yayımlanmıyor.** İki route da bare
   `dict[str, Any]` döndürüyor, yani yalnız bu alan değil **tüm** Result-detail ve history
   gövdesi `docs/openapi.json`'da yok. Önceden var olan, **O-30 şeklinde** bir kusur; o
   endpoint'leri typed hâle getirmek ayrı bir slice. Gizlenmedi, kaydedildi.
3. **Yarım-sentlik sleeve sapması düzeltilmedi, ifşa edildi** — ürün kararı gerekiyor.
4. **ADR 0002 hâlâ `Proposed`.** §16 uygulamadan önce onay şart koşuyor; ADIM 15/16/17/18 ve
   şimdi 19 **hiçbiri kayıtlı onay olmadan** indi ve §12'nin numaralandırması sevk edilenle
   hâlâ uyuşmuyor. İki kapı da bakımcıda açık.

**Rollback:** `git revert`. Contained iki modülü import eden yok; üretim tarafı yalnız
**okuma-zamanı** bir etiket ekliyor (yeni tablo, yeni kolon, yeni yazma yolu yok) —
`ENGINE_VERSION`, 46 golden digest, alembic head ve OpenAPI snapshot dokunulmadı.

---

## ADIM 20 — Unified portfolio oracle suite; containment KALDIRILMADI (PR #583, BLOCKED)

**Base `b0bb4a0` → commit `fd0ead5` → PR #583 (DRAFT/BLOCKED, merge edilmedi)** · 2026-08-05 ·
**Migration YOK** (alembic head `0043_i08_registry_strategy_fks`, tek head) · **OpenAPI
DEĞİŞMEDİ** · **`ENGINE_VERSION` DEĞİŞMEDİ** · **üretim kodu HİÇ değişmedi** · blocking issue
**#582**.

**`SHARED_ALLOCATION_STATUS` `future_dev` kaldı.** Bu slice containment'ı kaldırmadı.

### Neden kaldırılmadı — kod yazmadan önce üretilen probe'lar

Görev "oracle'ları yaz, hepsi yeşilse containment'ı kaldır" idi. Durma koşulu tetiklendi, ama
**bir oracle kırmızı olduğu için değil: kabul edilecek sistem yok.**

| Probe | Sonuç |
|---|---|
| `grep -rn "def run_portfolio" backend/src` | **eşleşme yok** — ADR 0002 §12'nin **ADIM 18**'i hiç yazılmadı |
| altı `execution/` unified-clock modülünün `execution/` dışı import'u | **yok** |
| `application/jobs/backtest_engine.py:298` | hâlâ `for prepared in prepared_items:` — dış döngü hâlâ **item listesi** |
| `application/jobs/backtest_engine.py:363` | hâlâ `combine_item_runs(...)` — bitmiş koşular hâlâ pin sırasında katlanıyor |
| ADR §12 **ADIM 16** (resumable stepper, saf refactor) | **hiç yazılmadı** — atlandı ⟵ *sonradan kapandı: PR #602; aşağıda §"ADIM 16 — `run_engine` bar döngüsü → resumable stepper"* |
| `manifest.py` policy alanları (`clock_policy_version`, `arbitration_policy_version`, `engine_allocation_policy_version`, `mark_staleness_policy`) | yok |
| ADR 0002 statüsü | **`Proposed`** — §16 onayı her uygulama slice'ı için ön koşul |

ADIM 15–19'da inen altı modül **kopuk bir ada**: 216 testle kaplı, eksiksiz primitifler — ama
hiçbir üretim yolu onlara ulaşmıyor. `domain/allocation/capability.py` §REMOVAL'daki
kaldırma koşullarının **motorla ilgili olanları** (#1 dış döngü, #3 sizing'e ulaşan tek
`E(t)`, #5 sevk edilen yolda doc 13 §14 test 11, #6 `ENGINE_VERSION`) bu yüzden **inşa gereği**
karşılanamıyor — başarısız bir assertion yüzünden değil.

### Ne indi — 25 test, tek boşluğu dolduran

Mevcut 216 birim testi altı modülü kaplıyor ama **hepsi tek-tick veya tek-modül**. Hiçbiri
clock → intents → ledger → arbitration'ı bir portföyün ömrü boyunca **birlikte** koşmuyordu —
oysa contained kusur tam orada yaşıyor.

* `backend/tests/unit/oracles/portfolio_harness.py` — ADR §8.2 faz döngüsü
  (P1 → P3 → PV → P4 → P5/P6b → P7 → P9). Girdi ve sıralama; gerçekleşen PnL fikstür tarafından
  **beyan edilir**, burada yeniden türetilmez.
* `test_oracle_portfolio_clock.py` (**10**) — tick başına tek yayımlanan değerleme ve her
  item'ın onu okuması; mandatory olayların ondan **önce** çözülmesi; inşa gereği zaman sıralı
  eğri; gelecekten veri taşımayan view; heterojen timeframe'lerin tek havuz için çekişmesi;
  çağıran-sırası ve bar-batch değişmezliği; 12 item × 72 tick yük sağlaması.
* `test_oracle_portfolio_capital.py` (**11**) — doc 13 §14 test 10 bölüşümü (3600/3150/1350,
  U0 900); çok-tick drawdown boyunca sabit nominal `R0`; tek fikstürde compound vs fixed
  (**2500.00 vs 4500.00**); ortak insolvency'de **tam red** — kalan nakdin alacağı 5 unit'e
  kırpılmıyor; blocked item'ın share'i asla devredilmiyor; kompozisyon-geneli exposure cap;
  karşıt yön çatışması; NET fail-closed; her değerlemede muhasebe kimliği; sıfır-residual
  per-item mutabakat.
* `test_oracle_portfolio_containment_gate.py` (**4**) — aynı dört kapanış **sıralı fold'da
  5000.00**, **birleşik saatte 3000.00**; artı yukarıdaki dört kapı olgusu assertion olarak.
* `docs/audit/unified_portfolio_oracle_acceptance.md` — A1–A22 durum tablosu, decision-record
  §6 koşulları, desteklenmeyen politikalar, insan kapıları.

Tüm beklenen değerler doc 13 / Master Ref Modül 11 / ADR 0002'den **elle türetilmiş literal**;
hiçbir engine aritmetik helper'ı beklenti üretmiyor.

**Non-vacuity varsayılmadı, DOĞRULANDI:** dört taşıyıcı literal bozuldu (`3000.00`→`5000.00`,
sleeve `3500.00`→`4500.00`, compound `2500.00`→`4500.00`, red edilen `0`→`5` unit) →
**tam olarak o dört test kırıldı**, başkası değil.

> **Yöntem notu — tekrarlanmasın:** ilk mutasyon denemesi faz sırasını bozmaktı
> (`publish_snapshot`'ı P3'ün önüne almak). **Geçersizdi:** `arbitrate` donmuş ledger ister,
> döngü yapısal olarak çöktü ve **her** test kırıldı. Bu semantik tespit değil, crash'tir.
> Literal perturbasyonu doğru araçtı.

### Dürüst sınır (üç yerde yazılı, kaldırılmamalı)

Oracle'ların sürdüğü faz döngüsü **TEST-OWNED**, çünkü `run_portfolio` yok. Yeşil koşu
**primitifler** hakkında kanıttır, **sevk edilen engine hakkında DEĞİL** — engine onları hiç
çağırmıyor. ADIM 18 indiğinde `portfolio_harness.simulate` yerine `run_portfolio` konmalı ve
25 oracle **değişmeden** yeniden koşulmalı; ADR §14'ün gerçekten istediği kanıt **o ikamedir**.
Yazılı olduğu yerler: harness docstring'i §"HONEST BOUNDARY", iki test modülünün docstring'i,
raporun §2'si.

### Kaldırmayı bloklayanlar (ölçülmüş)

**Yapısal (üretim yolu yok):** A1, A3, A5, A15, A16, A21 (cancel checkpoint'i hâlâ **item
başına** — `jobs/backtest_engine.py` O-06 checkpoint #3). A4/A18 gerçek `EngineOutput`
**digest**'i istiyor. A13/A14 yalnız hiçbir şey bağlı olmadığı için trivially doğru.

**Test önkoşulu:** **A17** — `tests/integration/test_research_point_in_time_parity.py`'de
**4 `xfail(strict=True)`** (#556 ×2, #557, #558); "green, unweakened" değil.

**İnsan kapıları:** ADR `Proposed` (§16) · ADR §12 numaralandırması sevk edilenle uyuşmuyor
(ADIM 16 atlandı; "yeniden yapılandır" ile "yeniden fiyatla" ayrımı artık yok) ·
**OD-1…OD-7** açık (ADR R-5) · **#544 (NET)** · **#559 (DST)**.

> **Sonradan değişti (PR #602).** *"Ayrım artık yok"* cümlesi **geçerli değil** — stepper saf
> refactor olarak yazıldı ve indi, adaptör + call site bilerek ayrı PR'a bırakıldı, yani ayrım
> geri kazanıldı (ADR §12 amendment). Numaralandırma uyuşmazlığı **duruyor**: iki sevk edilmiş
> slice "ADIM 16" adını taşıyor (intent katmanı #571/#572 vs stepper #602), yeniden
> numaralandırılmadı — **insan kararı**. Diğer kapılar değişmedi.

**Kapalı, kayda geçsin:** **R-1** (revision pinning drift) →
`a33d3e4 fix(readiness): pin the allocation revision the snapshot names`.

### Testler / CI

Yerel tam suite **tek çağrıda**, worktree'ye özel izole `TEST_DATABASE_URL`, çıktı dosyaya,
`$?` ayrı okundu: **exit 0**, **0 FAILED / 0 ERROR**, **coverage %93.24** (kapı ≥90).
`ruff check .` / `ruff format --check .` (757 dosya) / `mypy src` (392 dosya) **temiz**.
Hedefli `tests/unit/oracles/`: **111 passed** (86 mevcut + 25 yeni).
Frontend/E2E: **hiç frontend dosyası değişmedi**; CI otoritedir.

### Yan bulgu — doküman-gerçeği boşluğu

`docs/STAGE2_HANDOFF.md` ve bu dosya **PR #575 (arbitration) ve #581 (provenance) için
`landed` kaydı taşımıyordu**; handoff'un son `## Next:` bloğu hâlâ ADIM 18'i sıradaki iş
gösteriyordu. Bu kapanış boşluğu **işaret ediyor ama başkasının slice kaydını uydurmuyor** —
#575/#581'in tam anlatısını yazacak olan o slice'ları indirendir.

### Rollback

`git revert fd0ead5` — yalnız test ve doküman siler; üretim davranışı zaten hiç değişmedi.

## INF-14 — Scheduler event-loop ömrü (PR #593)

**Kusur (pre-existing, #587 DEĞİL).** `apps/scheduler/__main__.py::run` her tick'te
`asyncio.run(_maintenance_pass())` çağırıyordu: tick başına bir event loop AÇILIP KAPANIYOR,
ama `infrastructure/postgres/engine.py::get_engine` `@lru_cache`'li. Havuzdaki asyncpg
bağlantısı kapanmış loop'a bağlı kalıyor, sonraki tick onu alıyor ve **tüm pass** düşüyordu:

```
RuntimeError: Event loop is closed
  asyncpg/connection.py:1682 in _cancel_current_command
  sqlalchemy/dialects/postgresql/asyncpg.py:912 in _terminate_graceful_close
```

Düşen pass bozuk bağlantıyı attığı için sonraki tick temiz bağlantı alıp başarılı oluyordu →
passes **tam %50** dönüşümlü. Değişiklikten ÖNCE canlı Postgres'te 6 tick koşularak üretildi:
**3 OK / 3 FAILED**, katı dönüşüm.

**Etki.** Outbox relay + stale-RUNNING recovery (INF-09) + lost-message redelivery (INF-03)
yarı hızda çalışıyordu. **Veri kaybı yok** — pass bütün olarak rollback ediyor, satırlar durable
QUEUED kalıyor — ama recovery gecikmesi iki katı ve log'da kalıcı warning akışı vardı.

**Çözüm.** `run()` = `configure_logging(); asyncio.run(_sweep_until_stopped())` — process ömrü
boyunca TEK loop, havuz asla loop'unu geçmiyor; tick başına bağlantı kurulum maliyeti de gitti.
Engine `finally` içinde, loop HÂLÂ AÇIKKEN dispose ediliyor (aksi halde aynı kusur çıkış
gürültüsü olarak dönüyor).

**Shutdown yolu yeniden kuruldu** (zorunluydu: bloklayan `time.sleep` restructure'ı geçemezdi).
`signal.signal` yerine `loop.add_signal_handler` → `asyncio.Event`; tick artık
`asyncio.wait_for(stop.wait(), timeout=tick_seconds())`. Bu **latent bir kusuru da kapatıyor**:
PEP 475 gereği `time.sleep` handler döndükten sonra yeniden kuruluyordu, yani SIGTERM eskiden
**tam bir tick'e (30s)** mal oluyordu. `Event` import'ta DEĞİL her run'da yaratılıyor — bir
`Event` kendisini ilk bekleyen loop'a bağlar ve sonra başkasını reddeder (loop'un tek ve uzun
ömürlü olması gerektiğinin bir sebebi daha). Yeni seam: `request_stop()`.

**Smoke düzeltmesi.** `scripts/worker-restart-smoke.sh` adım 5 çıplak `scheduler.maintenance`
substring'ini arıyordu — bu `scheduler.maintenance_failed`'i DE yakalıyor, yani her sweep'in
düştüğü bir stack'te "OK scheduler swept" yazıyordu. **Tam olarak bu bug'ı maskeleyecek bir
assertion'dı.** `grep -Eq 'scheduler\.maintenance([^_]|$)'` → hem json hem console renderer'da
doğru.

**Testler (ikisi de fix ÖNCESİ şekle karşı KIRMIZI doğrulandı).**
- `tests/integration/test_scheduler_maintenance_passes.py` — gerçek `run()`, gerçek Postgres,
  gerçek **cached + POOLED** engine (ikisi de taşıyıcı; suite'in NullPool engine'i her tick'e
  taze bağlantı verir ve bug hiç görünmez). Altı ardışık pass → **sıfır**
  `scheduler.maintenance_failed`. Pre-fix şekle karşı: *"3 of 6 passes aborted"*.
- `tests/unit/test_scheduler_loop_lifetime.py` — DB'siz yapısal değişmez: tüm pass'ler tek
  loop, hiçbir pass önceki tick'in kapanmış loop'uyla başlamıyor, havuz kendi loop'unda
  dispose ediliyor, düşen pass döngüyü bitirmiyor, SIGTERM stop event'ini kuruyor.

Integration testin durma koşulu **iki sonucu birden** sayar; yalnız `scheduler.maintenance`'e
bağlansaydı her pass'i düşen bir scheduler'da sonsuza dek dönerdi — yani test edilen durumda.

**Migration yok, model yok, OpenAPI yok, `ENGINE_VERSION` değişmedi.** `_maintenance_pass`'in
SQL'i ve tek-transaction commit/rollback sınırı, `_redeliver`, `ACTOR_BY_QUEUE`, `tick_seconds`,
tick heartbeat'i ve **her log event adı** bilerek aynı.

**CI 6/6 yeşil** — `Backend — lint, type, test` 46m26s (coverage kapısı dahil). Yerel tam suite
%78'e kadar sıfır hata ile ilerledikten sonra arka plan wrapper'ı öldürüldü (exit 144, `EXIT=$?`
dosyası hiç yazılmadı) — **kapıyı yerelde doğrulamadım, otorite CI koşusudur.**

**AÇIK DEVİR:** `apps/agent_coordinator/__main__.py` **aynı kusuru taşıyor** (aynı dört ön koşul;
`asyncio.run(_run_cycle())` `:64`, `time.sleep` `:74`, cached factory `:42/:44`) — farkı sadece
`agent_coordinator.cycle_failed` adıyla görünmesi, bu yüzden scheduler aramalarında çıkmadı.
**Issue #591**, ayrı PR. İkisi birleşiyordu: coordinator'ın kaçırdığı executor dispatch'ini
INF-03 sweep'i telafi ediyor, o sweep de %50 çalışıyordu. `apps/worker/actors.py`'deki 11
`asyncio.run` çağrısı **analiz EDİLMEDİ** — dramatiq thread yeniden kullanımına bağlı, ölçmeden
iddia yok.


---

## DOKÜMAN ONARIMI — üç silinen kaydın geri yüklenmesi (2026-08-06)

**Aynı kusur üç kez tekrarlandı: bayat base'den merge edilen bir docs PR'ı, başka bir docs PR'ının
bu dosyaya yazdığı kaydı sessizce geri alıyor.** Hiçbir CI job'ı `docs/` markdown'ını okumadığı
için üçü de yeşil merge oldu.

| silinen kayıt | yazan | silen | silme diff'i |
|---|---|---|---|
| `## ADIM 18 — run_portfolio faz döngüsü; ADR 0002 Accepted` | `cdb3ab1` (#586) | `c3f5673` (**#590**) | 211 silme / 0 ekleme |
| `## ADIM 22 — install/upgrade/restore acceptance` | `f2c963f` (#611) | `4df00f1` (**#604**) | ↓ |
| `` `## ADIM 16 — run_engine bar döngüsü → resumable stepper` `` | `5e457e8` (#603) | `4df00f1` (**#604**) | ikisi birlikte 194 silme |

```
git show c3f5673 --stat -- docs/PROJECT_HISTORY.md   #  211 ------------
git show 4df00f1 --stat -- docs/PROJECT_HISTORY.md   #  194 ------------
```

**#590** PR #584 ile aynı başlık ve gövdeyi taşıyan mükerrer bir PR'dı. **#604** ise #603 ve
#611'den önceki bir base'den kesilmişti; kendi ADIM 16 anlatısını `STAGE2_HANDOFF.md` ile yeni bir
`ADIM16_LANDED_KICKOFF.md`'ye yazdı ama **bu dosyaya yazmadı**, dolayısıyla sildiği iki kaydın
yerine hiçbir şey koymadı. Aynı commit `CLAUDE.md §Current position` bloğunu da **tamamen
boşalttı** (10 satır silindi, yerine hiçbir şey konmadı) — o da bu onarımda geri yüklendi.

Hiçbir silme, ilgili PR'ın gövdesinde veya commit mesajında bildirilmedi.

**Onarım.** Üç bölüm de kaybolmadan önceki commit'lerinden **birebir** geri yüklendi; tek kelimesi
değiştirilmedi. Tekrarlanabilir komutlar:

```
git show ba586c5:docs/PROJECT_HISTORY.md | awk '/^## ADIM 18 — `run_portfolio`/,0'
git show f2c963f:docs/PROJECT_HISTORY.md | awk '/^## ADIM 22 —/,/^## ADIM 16 — `run_engine`/'
git show f2c963f:docs/PROJECT_HISTORY.md | awk '/^## ADIM 16 — `run_engine`/,0'
```

**Bilerek düzeltilmedi:** §T-02 kaydındaki *"ADIM 18 faz döngüsü hâlâ açık"* cümlesi — tarihçe
kayıtları tarihli anlık görüntülerdir, geriye dönük yeniden yazılmaz. Ayrıca **iki rakip ADIM 16
kickoff dosyası** (`ADIM16_STEPPER_LANDED_KICKOFF.md` #603'ten, `ADIM16_LANDED_KICKOFF.md`
#604'ten) main'de yan yana duruyor; hangisinin otorite olduğu **insan kararıdır**, bu onarım
birini silmiyor.

**Süreç dersi — üç kez kanıtlandı:** bir docs PR'ı sessizce başka bir docs PR'ını geri alabilir ve
hiçbir otomatik kapı görmez. **Docs PR'ı merge etmeden önce kendi diff'inin silme satırlarına
bak:** `git show <sha> -- docs/ | grep '^-## '`.

## ADIM 18 — `run_portfolio` faz döngüsü; ADR 0002 `Accepted` (branch `feat/stage-18-run-portfolio`)

> **Ad çakışması var, bilerek korundu.** PR #575 de "ADIM 18" etiketiyle indi (cross-item
> arbitration). Bu slice ADR §12'nin **18. satırının faz-döngüsü yarısıdır**. Sevk edilen
> numaralandırma ile ADR'nin numaralandırması arasındaki tam eşleme tablosu artık ADR §12'nin
> düzeltme notunda; iki sözlük de dolaşımda olduğu için bir kez yazıldı, her seferinde
> çıkarsanmıyor.

**Base `d7fe432`** · 2026-08-05 · **migration YOK** (alembic head `0043_i08_registry_strategy_fks`,
tek head) · **OpenAPI değişmedi** · **`ENGINE_VERSION` değişmedi**
(`backtest-engine-v18-gap-adjusted-stop-fill`) · **frontend dokunulmadı** ·
**`SHARED_ALLOCATION_STATUS` = `future_dev`**.

### ADIM 0 — insan kapısı, atlanmadı

ADR 0002 §16 uygulamayı PO/maintainer onayına bağlıyordu ve statü hâlâ `Proposed`'du; ADIM
15–19 bu onay olmadan inmişti. Kod yazılmadan **soruldu** ve iki karar alındı:

1. **ADR onaylandı → statü `Accepted`.** §13'ün yedi açık kararı yeni **§13.1 amendment
   tablosuna** çözüm olarak yazıldı — **hepsi kendi tavsiyesine** (OD-1(a) … OD-7(a)); hiçbiri
   tavsiyesinin tersine karara bağlanmadı, bu yüzden §13'ün gerekçeleri yeniden yazılmadı,
   yalnız statüleri değişti.
2. **§12 sevk edilene göre düzeltildi** — ADR'nin **ADIM 16**'sı (resumable stepper) formally
   **SKIPPED**.

§16 "discharged" olarak yeniden yazıldı ve **onayın ADIM 15–19'dan SONRA geldiğini** kayda
geçiriyor: bu slice'ların hepsi contained olduğu için maliyet küçüktü, ama küçük olmasının
sebebi containment guard'larıydı, şans değil — ve kapı, sevk edilmiş bir sayıyı değiştirecek
ilk slice olan ADIM 20 için tutmalı.

**§13.1'in bilinçli boşluğu:** OD-2 ve OD-3 ADR'de çözüldü ama **kodda hâlâ `pending` yazıyor**
(`provenance.MARK_STALENESS_POLICY == "undefined_pending_od2"`,
`arbitration.CONTENTION_SELECTION_STATUS == "recommended_pending_approval"`). İkisi de yalnız
`build_portfolio_manifest` üzerinden yayımlanan **beyan string'i** ve o fonksiyonu hiçbir şey
çağırmıyor; ADR §10.3 manifest alanlarını ADIM 20'ye koyuyor. Taşıyacak manifest yokken bir
policy etiketini çevirmek, hiçbir artefaktın kaydetmediği bir kararı ilan etmek olurdu →
**iki flip de ADIM 20'nin**, R-5 ile birlikte.

### Neden ADIM 16 gerekmedi — ve neyin borcu olarak kaldı

Stepper'ın amacı bir per-item replay'i verilen `t`'ye ilerletebilmekti, ki faz döngüsü item'ları
araya sokabilsin. ADIM 18 aynı yere **öbür taraftan** varıyor: `run_portfolio` **ayrı bir giriş
noktası**, kendi tick döngüsü ve kendi katılımcı sözleşmesiyle — `run_engine`'in gövdesine hiç
girilmiyor, dolayısıyla **46 golden digest kımıldayamaz**, ki bu ADIM 16'nın bütün kanıt
yükümlülüğüydü.

Ama stepper **worker call site'ın** ön koşulu olarak duruyor: gerçek engine ile desteklenen bir
`ItemParticipant`, bir item'ı `t`'ye ilerletip ne karar verdiğini bildirmek zorunda ve
`engine.py`'de bunu yapabilecek hiçbir şey yok — bar döngüsü `engine.py:1782`, ~1100 satırlık
tek bir fonksiyonun içinde nested. **Empirik olarak doğrulandı:** `grep -n "def step\|yield "
engine.py` üretimde hiçbir stepper döndürmüyor.

### İnen kod — tek yeni üretim dosyası

`backend/src/entropia/domain/backtest/portfolio_engine.py` (549 satır).

`run_portfolio(participants, *, pool_initial, shares, reserve_percent, compound,
conflict_policy, max_position_notional, max_total_exposure_notional) -> PortfolioRun`
ADR §8.2 faz sırasını sahiplenir, tick başına bir kez:

```
P1 carry (funding/fee/other_cost)
P3 mandatory exits  — form_mandatory_intent, snapshot ARGÜMANI YOK
PV publish_snapshot(t)      [ledger DONAR — her yazıcı LedgerFrozenError atar]
P4 intents                  [hepsi O snapshot'a karşı]
P5/P6b arbitrate(...)       [donmuş ledger'a karşı; arbitrate donmamışı REDDEDER]
P7 begin_apply(t) + set_position
P9 commit_tick(t)           [E(t) kımıldadıysa TEK equity point]
```

**Kendi aritmetiği yok.** Katılımcının bildirdiğini booking eder, hiçbir şeyi cap'lemez, hiçbir
boyut hesaplamaz. Bir sayı kımıldarsa, kendi testleri olan bir primitifte kımıldamıştır.

**Yeni sözleşme — `ItemParticipant` (Protocol):** `identity`, `stream`, `instrument_id`,
`carry(view) -> CarryCharges | None` (P1), `mandatory_exit(view, *, held) -> MandatoryExit | None`
(P3), `entry(view, snapshot, *, held) -> ItemIntent | None` (P4). Kasten dar: döngü item'ın
ne **ücretlendirildiğini**, ne **kapatmak zorunda olduğunu** ve ne **istediğini** sorar; nasıl
hesaplandığını hiç sormaz ve item-local state'e (cursor, indicator warmup, stop ladder) hiç
uzanmaz (ADR §5). Havuzun aritmetiğiyle item'ın aritmetiğini birbirine büyümekten alıkoyan şey bu.

**Çıktı tipleri:** `PortfolioTick` (`t_ms, timestamp, views, snapshot, mandatory, intents,
report, equity_point`) ve `PortfolioRun` (`ledger, ticks` + `dated_points`, `instants`,
`max_drawdown`, `tick_at`). İkisi de test harness'ından **üretime taşındı**.

**Sabitler:** `PHASE_ORDER` (faz sırası bir DEĞER olarak — bir test kaynağı yeniden okumadan
sözleşmeyi iddia edebilsin), `PORTFOLIO_LOOP_VERSION = "portfolio-phase-loop-v1"`.

### Sözleşme kararı — P4 neden hazır `ItemIntent` alıyor

`execution.intents` kendi kuralını koyuyor: *karar bir GİRDİdir, burada yeniden hesaplanmaz* —
mutable `BlockEvaluator` state'ine ve bar-ötesi edge detector'lara bağlı. **Aynı argüman bir
entry'nin BOYUTU için bir adım daha ileri gidiyor:** `form_intent` bir entry'yi
`costs._effective_fill` + `sizing._position_size` üzerinden ölçer ve bunlar item'ın kendi
`StrategyConfig`/`FillCosts`'unu ister — bunlar item'da yaşar, havuzda değil.

Bu yüzden katılımcı kendi P4 intent'ini **sevk edilmiş former'larla** kurar, döngü onu
**doğrular**: doğru item, `phase == "P4"`, mandatory olmayan tür, `t_ms` tick ile aynı,
`snapshot_identity` bu tick'in snapshot'ıyla aynı. `form_intents`'in vereceği garantiler
**sınırda kontrol edilir**, çağrı sırasına güvenilmez.

**Açıkça saklanmayan sonuç:** `form_intents`'in aksine döngü sessiz bir item için izlenen bir
`no_op` **üretmez**; katılımcı `None` döner ve tick gerçekten oluşturulmuş intent'leri kaydeder.
Per-item sessizlik kaydı bir raporlama değişikliğidir, sermaye değişikliği değil, ve decision
trace'e aittir.

### Modellemeyenler (fail-closed, sessiz değil)

- **P0** clock cursor'ının kendisi; **P2 pending fills** ve **P8 same-direction scaling** item'ın
  kendi execution modeline ait. Admitted bir `scale_in` bu yüzden `UnsupportedIntentKindError`
  **atar** — `set_position` tutulan boyutu **değiştirir**, layer boyutunu yazsa pozisyonu sessizce
  küçültürdü.
- **Mark policy yok (OD-2).** `E(t)` ledger'ın tanımladığı gibi realized-only.
- Fail-closed reddedişler: `InvalidParticipantError` (kendiyle çelişen katılımcı: duplicate
  `item_id`, identity ile stream'in farklı item'ı, pin_ordinal uyuşmazlığı, share'i olmayan item),
  `MisformedIntentError`, `UnsupportedIntentKindError`, `UnpriceableAdmissionError`.

### Determinizm

`_ordered()` katılımcıları argüman sırasına güvenmeden `(pin_ordinal, item_id)`'ye **sıralar**
(ADR §4.4) — çağıranın sırası DOM/request sırasıdır ve doc 13 §13 onun sonucu etkilemesini
yasaklar. Clock da stream'lerini aynı şekilde sıralar. Tick'in `timestamp` etiketi **pinli
sıradaki ilk karar veren view'dan** okunur, yani eksenin bir özelliği; `ctx.prices` her P4'ten
önce **temizlenir** — eski bir tick'ten kalmış fiyat yalnız yanlışlıkla okunabilirdi ve okunsa
pozisyonu bayat bir barda açardı.

### Kabul — tek ölçüt karşılandı

`tests/unit/oracles/portfolio_harness.py` artık **test-owned faz döngüsü taşımıyor**:
`_run_tick`, `TickRecord` ve `PortfolioRun` silindi; `simulate` her `ScriptedItem`'ı bir
`_ScriptedParticipant`'a çevirip `run_portfolio`'ya veren **ince bir adaptör**.

**25 portföy oracle'ı gövde ve beklenen literal olarak BİREBİR aynı kaldı.** `git diff`
`test_oracle_portfolio_clock.py` ve `test_oracle_portfolio_capital.py` için **yalnız modül
docstring'i** gösteriyor (artık yanlış olan "faz döngüsü TEST-OWNED" cümlesi; yanlış bir dürüst-
sınır notu bırakmak, notu güncellemekten kötüdür). İkame ilk koşuşta **24/25 yeşil** geldi; tek
kırmızı, zaten yeniden yazılacak olan containment kapısıydı. `tests/unit/oracles/`: **111 passed**.

Bu, ADR §14'ün **A1 / A3 / A5**'ini PRIMITIVE'den **MET**'e taşıyan hamledir.

### Containment — 4 guard güncellendi, 2'sine dokunulmadı, kapı pozitife çevrildi

| guard | ne oldu |
|---|---|
| `test_the_clock_is_not_wired_into_production_yet` | → `test_the_clock_is_reachable_only_through_the_phase_loop` |
| `test_nothing_in_production_imports_the_intent_layer_yet` | → `test_the_intent_layer_is_reachable_only_through_the_phase_loop` |
| `test_nothing_in_production_imports_the_shared_ledger_yet` | → `test_the_shared_ledger_is_reachable_only_through_the_phase_loop` |
| `test_nothing_in_production_imports_the_arbitration_layer_yet` | → `test_the_arbitration_layer_is_reachable_only_through_the_phase_loop` |
| `test_nothing_in_production_imports_the_attribution_layer_yet` | **değişmedi** — faz döngüsü import etmiyor |
| `test_nothing_in_production_imports_the_provenance_layer_yet` | **değişmedi** — `build_portfolio_manifest` ADIM 20'nin |

Adlar yeniden yazıldı çünkü ad bir **iddiadır**: "nothing in production imports" artık
düpedüz yanlış olurdu. Assertion'lar **gevşetilmedi** — dördü de
`domain/backtest/portfolio_engine.py`'yi **adlandırılmış** importer olarak listeler, beşincisi
kazara beliremez. Arbitration guard'ı ayrıca `sorted()` aldı (rglob dosya sistemi sırası
macOS/Linux arasında değişiyor — clock guard'ı bu tespiti zaten kaydetmişti; tek importer'la
görünmezdi, ikiyle platform-bağımlı olurdu).

Oracle kapısı `test_no_unified_clock_driver_exists_in_production_on_this_commit` **silinmedi**,
pozitif muadiline yeniden yazıldı: **`test_the_phase_loop_exists_but_no_production_path_reaches_it`**
— (1) `def run_portfolio` var, (2) onu tanımlayan **tek** üretim modülü var (iki tanesi, faz
sırası sorusuna iki cevap demek olurdu), (3) altı unified-clock modülü `execution/` dışında
**yalnız** faz döngüsünden import ediliyor, (4) **`run_portfolio`'nun üretimde hiç çağıranı
yok**, (5) worker hâlâ `combine_item_runs` + `for prepared in prepared_items:`.

### Golden digest kapısı

`tests/unit/test_backtest_engine_golden.py` yeşil; `backend/tests/unit/engine_golden_digests.json`
**dokunulmadı** (`git status` temiz). `run_engine`'in imzası da gövdesi de hiç değişmedi (ADR §3.2).

### DÜRÜST SINIR — kapanmadı, ve kapanmadığı iddia ediliyor

`application/jobs/backtest_engine.py:298` **hâlâ item döngüsü**, `:363` hâlâ
`combine_item_runs`. `run_portfolio` **çağıransız** indi. Bu, ADIM 15–19'un "kopuk ada"
probleminin bir seviye yukarısıdır ve **kabul edilerek** yapıldı: alternatif, engine'i faz
döngüsünün içinde yeniden yazmak (bir ikinci engine — `intents.py` docstring'inin açıkça
yasakladığı şey) ya da 25 oracle'ın beklenen literallerini değiştirmek olurdu.

Sonuç: hiçbir request/retry/Agent çağrısı bir tick loop'una ulaşamaz, hiçbir sevk edilmiş
Result değişemez, `SHARED_ALLOCATION_STATUS` `future_dev` kalır. Bu **varsayılmıyor,
iddia ediliyor** — yukarıdaki (4) ve (5).

### Testler / CI

Yerel tam suite **tek çağrıda**, worktree'ye özel izole DB
(`TEST_DATABASE_URL=postgresql+asyncpg://…/entropia_wt_runportfolio`), çıktı dosyaya, `$?`
**ayrı** okundu. `ruff check .` / `ruff format --check .` (758 dosya) / `mypy src` (393 dosya)
**temiz**. `mypy tests/unit/oracles/portfolio_harness.py` de temiz — `_ScriptedParticipant`'ın
`ItemParticipant`'ı karşıladığı **statik olarak** doğrulandı (repo kapısı yalnız `src`'yi tarar).
Golden: 2 passed, digest dosyası değişmedi. Oracles: 111 passed. Containment guard suite'leri:
267 passed.

**Ortam notu:** `uv sync --all-extras --dev` `backend/uv.lock`'u değiştirdi (main'in lock'unda
`requires-dist` altında `boto3` / `boto3-stubs` satırlarının yerinde **boş bir satır** var).
Bu slice o farkı **geri aldı** (`git restore`) — alakasız bir değişiklik diff'i kirletmemeli;
`uv run` tek başına lock'u kirletmiyor. **Lock'taki o boşluk main'de duruyor ve ayrı bir
inceleme konusu.**

### Rollback

`portfolio_engine.py`'yi sil + dört guard'ı ve oracle kapısını geri al. Üretim davranışı zaten
hiç değişmedi — hiçbir şey döngüyü çağırmıyor.

### Sıradaki tek adım

**ADIM 20 DEĞİL.** Önce engine-destekli `ItemParticipant`: (a) `run_engine`'in bar döngüsünü
stepper'a çıkar — tek kanıt 46 digest kımıldamaz —, (b) **ayrı bir PR'da** adaptörü yaz ve
worker'ın item döngüsünü `run_portfolio` ile değiştir (yalnız >1 item). ADR §15 R-4'ün
"restructure ile re-price'ı ayır" kuralı bir kez kaybedildi; ikinci kez kaybedilmemeli.
## ADIM 22 — install/upgrade/restore acceptance (PR #594, #601)

**Boşluk.** Kurulum zincirinin harness'ları vardı ama **kapısı yoktu**.
`scripts/e2e-acceptance.sh`, `scripts/backup.sh`, `scripts/restore.sh`,
`scripts/backup-verify.sh` geliştirici komutlarıydı; **hiçbir workflow bunları koşmuyordu**.
Yani bozulmuş bir kurulum yolu, eski bir veritabanına uygulanamayan bir migration ve satırsız
bir şemayı geri yükleyen bir backup — üçü de **yeşil inebilirdi**. Denetim bunun backup yarısını
**H-07** diye kaydetmişti.

**PR #594** — squash-merge `3cc9588` (2026-08-05T17:49:33Z), base `c3f5673`, branch
`test/install-upgrade-restore-acceptance`, **+1728 / −38, 11 dosya**.
**PR #601** — squash-merge `e6cd2ee` (2026-08-05T19:24:09Z), branch
`fix/backup-object-storage-on-linux`, **+46 / −9, 4 dosya**.
**Migration YOK** (alembic head `0043_i08_registry_strategy_fks`) · **OpenAPI DEĞİŞMEDİ** ·
**`ENGINE_VERSION` DEĞİŞMEDİ**.

### Ne indi

| Yeni | Ne yapar |
|---|---|
| `scripts/migration-acceptance.sh` (`make migration-accept`) | Docker'sız, ~30 sn, **her PR**. Gerçek PostgreSQL + gerçek `alembic upgrade` yolu (asla `metadata.create_all`): tek head · empty→head · migration↔model **kolon** paritesi · migration'ın yazdığı satırlar · iki temsili legacy revizyon→head (değer parmak iziyle) · head down/up/up · provisioning tekrar **ve eşzamanlılık** idempotency'si |
| `scripts/dr-acceptance.sh` (`make dr-accept`) | `backup-verify.sh`'in "dump yükleniyor mu?" sığlığını kapatır: scratch DB + scratch bucket'a restore, sonra kaynak↔restore karşılaştırması — head, tablo kümesi, **her tablonun** satır sayısı, değişmez kanıt kolonları, append-only düzlemler, per-object md5 |
| `.github/workflows/install-acceptance.yml` | Dört job; maliyete göre bölünmüş: **her PR** → `migration-acceptance` + `fresh-install`; **nightly/manual** → `legacy-upgrade` + `disaster-recovery` |
| `docs/INSTALL_ACCEPTANCE.md` | Zincirin hangi halkasının nerede kanıtlandığı + dürüst sınırlar |
| `backend/tests/integration/test_provision_concurrency.py` | 6 test (aşağıya bak) |

`scripts/e2e-acceptance.sh::assert_planes_healthy` listesine **`worker-agent-executor`
eklendi** — o düzlem hiç yokken §9.4 akışı yeşil geçebiliyordu; Coordinator kimsenin
tüketmediği Agent task'ları kuyruğa alır, scheduler onları sonsuza dek yeniden gönderir ve
**her gönderim başarı raporlar**. Servisin kendi yorumunun tarif ettiği sessiz döngü, tam da
onu yakalaması gereken listede yoktu.

### Production değişikliği — provisioning eşzamanlı-güvenli DEĞİLDİ

`apps/seed.py`'deki her guard SELECT-then-INSERT ve seed sonda **tek kez** commit ediyor.
READ COMMITTED altında ikinci koşu birincinin commit edilmemiş satırlarını göremez: ikisi de
"zaten var mı?" kontrolünü geçer, kaybeden `principals_pkey` ile ölür ve **tüm transaction'ını**
geri alır. Taze, migrate edilmiş bir veritabanında üretildi: **3 paralel koşunun 2'si exit 1**.

Bu kozmetik değil. Compose'daki `provision` one-shot **her düzlem** için
`service_completed_successfully` kapısıdır (`docker-compose.yml` `x-needs-provision`), yani tek
bir yarışan exit-1 API'yi, tüm worker düzlemlerini, coordinator'ı ve scheduler'ı başlatmaz.

**Gürültülü çökme sadece görünen yarısı.** Arkasında unique constraint OLMAYAN guard'lar
başarısız olmak yerine **sessizce duplike commit eder**: `rationale_family_revision.normalized_name`
yalnızca `index=True`, yani iki koşu da "bu family var mı?" kontrolünü geçip ikisi de COMMIT eder.
**Varsayılmadı, ölçüldü:** kilit kaldırıldığında 3 eşzamanlı koşu **6 kanonik yerine 18**
rationale family üretiyor ve **hiçbir yerde hata raporlanmıyor**.
`test_concurrency_does_not_duplicate_an_unguarded_seed_block` o sayıyı pinliyor.

**Çözüm — yeni altyapı YOK.** `PROVISION_LOCK_KEY = 220_000` + `lock_provisioning()`:
transaction-scoped `pg_advisory_xact_lock`, repo'da zaten kullanılan deyim
(`repositories/identity.py::lock_admin_count`, `repositories/manual.py::lock_stream`). İlk guard
herhangi bir şey okumadan ÖNCE alınır; PostgreSQL onu commit **veya** rollback'te bırakır, yani
çöken bir koşu sonrakini bloke bırakamaz. `_seed()` ikiye ayrıldı: public
`provision(session, log)` + session sahibi `_seed()`.

Bekleme **sınırlı**: `PROVISION_LOCK_TIMEOUT_MS` (varsayılan 120000), `SET LOCAL lock_timeout`
ile — **lock_timeout'un `pg_advisory_xact_lock`'a uygulandığı PostgreSQL 16'da ampirik
doğrulandı**; aşılırsa `ProvisioningLockTimeout`. Sınırsız bekleme değiştirdiği hatadan **daha
kötü** olurdu: stale idle-in-transaction bir backend'in arkasında bloke kalan bir koşu tüm
stack'i **hatasız** asardı, ki bu bir exit code'dan daha zor teşhis edilir.

**Her iki yarı da mutation-verified** — kilit `pass` ile değiştirildiğinde testler kırmızıya
döndü (hem çökme yarısı hem sessiz-duplikasyon yarısı).

### PR #601 — object storage aslında yedeklenmiyordu

ADIM 22'nin DR kapısı **ilk gerçek CI koşusunda kırmızı** çıktı:
*"the backup captured no object storage (minio/ absent)"*. Sebep ortam değil: `minio/mc` imajı
`ENTRYPOINT ["mc"]` bildiriyor, yani `docker run minio/mc sh -c '...'` argümanları **mc
parametresi** olarak ayrıştırılıyor ve fallback hiç çalışmıyordu. `--entrypoint sh` eklendi —
`backup.sh`, `restore.sh` ve `dr-acceptance.sh`'in üçünde birden, çünkü üçü de aynı çağrıyı
taşıyordu. Host'unda `mc` olan bir geliştiricide kusur hiç görünmüyordu; **`mc`'si olmayan her
makinede object storage sessizce yedeklenmiyordu.**

### CI kanıtı

**Actions run 31038908690** — dört job da `success`:
`fresh-install` · `migration-acceptance` · `legacy-upgrade` · `disaster-recovery`.
Kanıt satırları: `PASS mirrored bucket 'entropia-artifacts' via dockerized mc` ·
`DR ACCEPTANCE OK` · `VERIFY OK — 20260805T192122Z restores into a coherent database
(head 0043_i08_registry_strategy_fks, 105 tables)`.

**Dürüst nüans:** bu koşu `main`'in merge commit'inde değil, **`fix/backup-object-storage-on-linux`
branch'inde `84d1a5e`'de** `workflow_dispatch` ile koştu — yani #601'in `e6cd2ee` olarak squash
edilen içeriğinde. `main` üzerinde heavy job'lar ilk kez nightly cron'da (03:17 UTC) koşacak.

### Dürüst sınırlar (yumuşatılmadı)

1. **Index ADLARI gate dışı.** `alembic check` migration'lar ile `Base.metadata` arasında fark
   bildiriyor — hepsi index-*adı* sapması (migration'ın adlandırdığı
   `ix_result_manifest_snapshot_hash` vs model'in autogenerate ettiği
   `ix_result_manifest_snapshot_manifest_hash`) artı bir server default. **Kolon paritesi**
   — `CONTRIBUTING.md`'nin gerçekten adlandırdığı eksen — temiz ve **gate'li**.
   `alembic check`'i kapıya çevirmek ayrı, daha büyük bir temizlik; sessizce yok sayılmıyor,
   bilerek kapsam dışı.
2. **Integration suite şemayı hâlâ `metadata.create_all` ile kuruyor**
   (`tests/integration/conftest.py`). Bu bir test-hızı kararı, kurulum yolu değil — ve
   **migration'ın yazdığı satırlar pytest'te YOK** (0016'nın `alpha-agent` `agent_runtime`
   singleton'ı, 0019/0020 fixture'ları). Bu yüzden `migration-acceptance.sh` [4] onları
   migrate edilmiş veritabanına karşı **ayrıca** doğruluyor.
3. **DR kanıtı sığdı.** Aynı run'ın transcript'i şunu bastı: `[7] all three append-only planes
   were EMPTY` ve `[8] 1 objects`. Sebep `apps/seed.py`'nin bir **fixture yazarı** olması —
   repository'ler üzerinden insert ettiği için `_audit_and_outbox`'a hiç ulaşmıyor (sıfır
   audit, sıfır outbox) ve `infrastructure/s3/datasets.py`'deki **dört** object writer'dan
   yalnız birini çağırıyor. **ADIM 23 / PR #610** bunu kapatıyor (yedeklemeden önce gerçek bir
   iş akışı + kapsama tabanları); bu kayıt yazıldığında PR **açık**, merge edilmedi.
4. **Docker job'ları yerelde koşturulamamıştı.** ADIM 22 yazılırken paralel bir worktree
   oturumu 5432/8000/8080/9000 portlarını tutuyordu; compose job'ları ilk gerçek yürütmelerini
   CI'da aldı. `docs/INSTALL_ACCEPTANCE.md`'deki **▶** işaretleri bunu kaydediyordu — run
   31038908690'dan sonra artık **✔**.
5. **PITR, off-site replikasyon ve zamanlanmış backup V1 kapsamı dışında**
   (`docs/BACKUP_DR.md` "Scope"). Bu slice V1'in gerçekten sevk ettiği operatör-tetiklemeli
   zinciri kanıtlıyor; ertelenmiş altyapı modülünü icat etmiyor.

### Kayıt doğrulaması (ADIM 23 oturumunda)

- **PR #575 / #581 kaydı EKSİK DEĞİL.** `docs/PROJECT_HISTORY.md` §"ADIM 18 (sevk edilen sıra)"
  ve §"ADIM 19" ile `docs/STAGE2_HANDOFF.md`'deki karşılıkları **PR #589 ile geriye dönük
  yazıldı**; `CLAUDE.md` artık o borcu taşımıyor. Bu oturuma gelen brief'te borç hâlâ açık
  sanılıyordu — doğrulandı, açık değil.
- **Coordinator event-loop kusuru KAPANDI.** ADIM 22 kapanışı sırasında hâlâ açıktı; **PR #600**
  (`735cc83`) scheduler'ın #593'teki düzeltmesinin aynısını uyguladı ve **issue #591'i
  `COMPLETED` olarak kapattı**. Bu oturuma gelen brief 17:55Z ve 19:09Z'deki iki koşuyu kanıt
  gösteriyordu; **ikisi de 19:19Z'deki merge'den ÖNCE**. Ayrı bir düzeltme gerekmedi.
- **`apps/worker/actors.py`'deki 11 `asyncio.run` da KAPANDI** — **PR #597** (`aa29509`),
  bu kayıt yazılırken merge edildi: aktör gövdeleri artık tek process-wide loop'ta. Aynı
  tarama `apps/seed.py:782`'yi de buluyor: tek seferlik CLI çağrısı, loop yeniden kullanımı
  yok, **bilerek dokunulmuyor**. Böylece per-tick/per-mesaj loop kusuru üç düzlemde de
  kapandı: **#593** (scheduler) · **#600** (coordinator) · **#597** (worker aktörleri).

## ADIM 16 — `run_engine` bar döngüsü → resumable stepper (PR #602)

**ADR §12 bu adımı SKIPPED işaretlemişti** — faz döngüsü aynı yere öbür taraftan ulaştığı için.
Ama aynı düzeltme notu şunu da yazıyordu: stepper hâlâ **worker call site'ının ön koşuludur**.
Gerçek engine ile desteklenen bir `ItemParticipant` bir öğeyi verilen `t`'ye ilerletebilmek
zorunda ve `engine.py` bunu yapamıyordu — bar döngüsü ~2400 satırlık bir fonksiyonun içinde
1355 satır derinlikte nested'dı. Bu slice o borcu ödedi; faz döngüsünün yerine geçmedi.

**Şekil.** `run_engine`'in gövdesinin bar döngüsüne kadarki kısmı `_build_stepper(...)` oldu ve
bir `_ItemStepper` döndürüyor: `step(bar)` · `finalize()` · `output()` · `open_position()` +
canlı `ledger` (`_Ledger`) ve `ctx` (`_RunConfig`). `run_engine` **imzasını, docstring'ini ve
semantiğini korudu** ve dokuz satırlık bir sürücüye indi. `_build_stepper` `run_engine`'in tüm
anahtar argümanlarını alır, **yalnız `bar_batches` hariç** — bar akışını artık çağıran sahiplenir;
fail-closed `UnresolvedStrategyError` fabrikada, ilk bardan önce atılır.

**State closure'da BIRAKILDI, bir `self`'e taşınmadı.** Replay durumu eskiden `run_engine`'in
frame'indeydi; sınıf alanlarına taşımak 1355 satırın her adını `self.` ile yeniden yazmak, yani
"saf refactor" iddiasını kaybetmek olurdu. `_ItemStepper` bu yüzden yalnız closure'lara işaret
eden ince bir dataclass.

**Arayüz ölçüldü, okunmadı.** AST ile: bar'lar arası taşınan **tam 10 ad** — `current_day`,
`exit_touch`, `funding_idx`, `pending`, `position`, `prev_entry_signal`, `prev_scale_signal`,
`scale_signal`, `working_limit`, `working_stop`. Gövdenin bağladığı diğer **83** ad bar-içi
geçicidir ve bunu **kesin-atama (definite-assignment) analizi** kapattı: her okumadan önce, her
yolda yazılıyorlar. (Analiz yanılsaydı hata modu sessiz bir sayı değil, gürültülü bir
`UnboundLocalError` olurdu — bu yüzden kabul edilebilir bir risk profiliydi.) `position_seq`
`_do_open`'ın `nonlocal`'ı olarak fabrikada kaldı; `_step` ona dokunmaz. Yerinde mutate edilenler
(`led.*`, `position.*`, `window`) rebind olmadığı için `nonlocal` istemez.

**Taşınan her satır birebir.** Düzenlemeden sonra taşınan aralıklar `HEAD`'e karşı satır satır
karşılaştırıldı: setup **955**, step gövdesi **1351**, gün-sonu **44**, output assembly **15** —
hepsi identical. Tek istisna, formatter'ın dedent sonrası tek satıra topladığı bir `max(...)`
çağrısı.

**Kabul = 46 golden digest, başka hiçbir şey** (ADR §15 R-4: *"46-digest invariance is the gate;
no other assertion is trusted"*). **46/46 kımıldamadı.** Tam backend suite tek çağrıda: **3699
passed, 4 xfailed (bilinen strict set #556 ×2 / #557 / #558), 0 failed**, coverage **%93.29**
(kapı ≥%90; `engine.py` %95.1). CI 8/8 (2 nightly job by-design skip). ruff + format + `mypy src`
temiz.

**Golden'ın göremediği yarı ayrıca test edildi** (`tests/unit/test_backtest_engine_stepper.py`).
`run_engine` stepper'ı **tek kesintisiz geçişte** besler, yani bar-içi yerele dönüşmüş bir
taşınan ad — her barda okunmadan önce yazıldığı sürece — yine de kayıtlı digest'i üretebilirdi.
Yeni testler aynı senaryoları **bar başına bir `step()` çağrısıyla, her bar arasında askıya
alarak** koşar ve digest eşitliğini iddia eder; taşınan her ad için bir vaka: resting limit
order, hiç touch etmeyen limit, tetiklenmeyen stop, merdiven kuran pozisyon, iki funding kaydı
ödeyen tutulan pozisyon, blackout gününü aşan tutulan sinyal. Ayrıca: batch boyutunun
gözlemlenemezliği, adım aralarında pozisyonun hayatta kalması, ve fail-closed kapının ilk bardan
önce çalışması.

**Bilerek KAPSAM DIŞI.** Worker'a dokunulmadı — `jobs/backtest_engine.py:298` hâlâ item döngüsü,
`:363` hâlâ `combine_item_runs`. `ENGINE_VERSION` değişmedi, containment guard kapalı
(`SHARED_ALLOCATION_STATUS = future_dev`), manifest policy alanı eklenmedi. Migration yok, model
yok, OpenAPI yok. `_ItemStepper` / `_build_stepper` modül-private ve `__all__`'da DEĞİL: **henüz
`engine.py` dışından çağıranı yok** — onlara tüketici kazandıran şey PR B'dir.

**Dürüst sınır.** PR B mekanik bir ikame değil: `ItemParticipant.entry` HAZIR bir `ItemIntent`
ister ama `form_intent` entry'yi item'ın kendi `StrategyConfig`/`FillCosts`'u olmadan ölçemez; ve
stepper bir barı **bütün olarak** ilerletirken faz döngüsü aynı barı **fazlara bölünmüş** ister.
O boşluğu kapatmak bir tasarım işidir. Devir belgesi: `docs/ADIM16_STEPPER_LANDED_KICKOFF.md`.

## ADIM 25 (observability) — alert kuralları + operatör runbook'ları (PR #622)

**Merged `780dc92`**, branch `ops/observability-alerts-runbooks`, base `e5c650a`.
**35 dosya, +2885 / −13.** Migration **YOK** — alembic head `0043_i08_registry_strategy_fks`
değişmedi. `ENGINE_VERSION` değişmedi. OpenAPI sözleşmesi değişmedi.

### Neden

Stage 8b'de sevk edilen `/metrics` expozisyonu **hiçbir şeye bağlı değildi**: repoda tek bir
alert kuralı yoktu, `docs/runbooks/` dizini **hiç yoktu** ve hangi metriğin hangi soruyu
yanıtladığını söyleyen bir belge de yoktu. Kimsenin alert yazmadığı metrik observability değil,
dashboard'dur.

### Ne indi

1. **`ops/alerts/entropia.rules.yml` — 11 alert / 5 grup.** Her alert `severity` (`page` |
   `ticket`), `component`, `for:` ve **dokuz zorunlu anotasyon** taşır: `summary`, `derivation`,
   `diagnosis`, `response`, `mitigation`, `recovery`, `escalation`, `false_positives`, `runbook`.
   Kurallar: `EntropiaApiDown` · `EntropiaApiServerErrors` ·
   `EntropiaApiRequestsExceedLargestBucket` · `EntropiaMetricsDatabaseProbeFailing` ·
   `EntropiaWorkerHeartbeatStale` · `EntropiaWorkerHeartbeatNeverRecorded` ·
   `EntropiaJobLeaseStuck` · `EntropiaQueueNeverDrains` · `EntropiaJobsFailingTerminally` ·
   `EntropiaOutboxLagGrowing` · `EntropiaOutboxLagSevere`.
2. **`docs/runbooks/` — 13 dosya:** `README.md` (index), `METRIC_ALERT_MATRIX.md` ve ateşleyen
   alert'ten erişilebilen 11 runbook (`api`, `postgres`, `redis`, `object-storage`,
   `worker-down`, `stale-jobs`, `outbox-lag`, `backtest`, `agent-coordinator`,
   `backup-restore`, `migration`).
3. **Yeni metrik ailesi — `entropia_worker_heartbeat_age_seconds`.**
   `apps/worker/actors.py::system_heartbeat` zaten scheduler→Redis→worker round-trip'ini
   kanıtlıyordu ama **hiçbir şey kaydetmiyordu**; boştaki bir sistemde ölen worker görünmez
   kalıyordu (queue depth ve lease age ancak bekleyen bir iş varken konuşur). Artık round-trip
   `application/jobs/heartbeat.py::record_worker_heartbeat` ile `app_metadata` tablosuna
   upsert ediliyor (`key="worker.maintenance.last_heartbeat_at"`). **Migration gerekmedi** —
   tablo zaten mapped'di ve yazarı yoktu. Okuma ucu:
   `application/queries/job_gauges.py::JobGauges.worker_heartbeat_age_seconds`.
4. **Frontend (brief'te anılmayan, ama sevk edilen dördüncü parça):** `lib/metrics.ts` +
   `pages/Metrics.tsx` heartbeat'i okur ve kayıt yokken **"never recorded"** basar — asla taze
   bir heartbeat gibi göstermez. Testler: `test/metrics.test.ts`, `test/metricsPage.test.tsx`
   (+128 satır, 4 dosya).

### Kritik semantik — None asla 0.0'a çökmez

`routes/metrics.py::_render_operational_gauges` heartbeat için `# TYPE` satırını basar ama
**kayıt yoksa ÖRNEK SATIRI BASMAZ**. Böylece seri gerçekten *absent* olur ve `absent()` tabanlı
alert ateşleyebilir. `entropia_outbox_lag_seconds`'ın meşru biçimde 0.0 basmasının sebebi
farklıdır ("yayınlanmamış bir şey yok" gerçekten sıfır lag demektir); heartbeat'te 0.0 basmak,
hiçbir şeyin koştuğunu kanıtlamadığı anda worker'ı "bir an önce canlıydı" diye **reklam etmek**
olurdu. Bu expozisyonun asla üretmemesi gereken sessiz fallback tam olarak budur.

### İki gerçek kusur bulundu ve düzeltildi (ikisi de mevcut kodda)

**(a) `method` metrik label'ı SINIRSIZDI.** `path` özenle çözümlenmiş route template'ine
sıkıştırılmışken `request.method` — hattan gelen keyfi bir token — verbatim geçiyordu. **Gerçek
app'e karşı kanıtlandı:** altı uydurma HTTP metodu altı ayrı seri üretti. Düzeltme:
`apps/api/hardening.py::_bounded_method` + `_KNOWN_METHODS` (7 metot + `"other"` = **8 tavan**).

**(b) `up{...} == 1 and absent(...)` HİÇ ATEŞLENEMEZDİ.** Eşitlik matcher'ı olmayan bir selector
üzerindeki `absent()` **etiketsiz** bir eleman döndürür ve `and` varsayılan olarak **tüm etiket
kümesini** eşleştirir → boş vektör. İki **paging** alert'i ölüydü. Düzeltme: `and on()`.
Regresyon kapısı: `test_absent_is_always_joined_with_on_to_match_label_sets`.

### Eşikler türetildi, seçilmedi (adjudicated — mutlak latency SLO'su YOK)

`docs/performance/README.md:144` interactive-read p95 satırını *"deliberately blank rather than
guessed"* diye bırakmıştır. Bu yüzden **hiçbir alert mutlak latency/throughput hedefi
uydurmaz.** Tek latency sınırı `le="5.0"` — histogram'ın **zaten sevk edilmiş** en büyük
bucket'ı. `entropia_http_requests_in_flight` için alert **YOK** (adjudicated bir concurrency
hedefi yok). Diğer tüm eşikler shipped config default'unun katıdır: **6x / 10x / 60x**
`SCHEDULER_TICK_SECONDS` (30), **2x** `JOB_STALE_AFTER_SECONDS` (600), **2x**
`JOB_REDELIVER_GRACE_SECONDS` (600). Hepsi `test_alert_rules_contract.py` içinde
`get_settings()` ve `_BUCKETS`'a karşı **makineyle pinli**; legal metrik-adı kümesi
expozisyon kodunun kendisinden türetilir, böylece yeniden adlandırılan bir metrik **aynı
commit'te** kırılır.

### Testler

**Yeni:** `tests/contract/test_alert_rules_contract.py`,
`tests/contract/test_metrics_label_cardinality.py`, `tests/unit/test_worker_heartbeat_gauge.py`,
`tests/integration/test_worker_heartbeat_persistence.py`.
**Güncellenen:** `tests/unit/test_metrics_gauge_rendering.py` (eski gövde artık **ÖNEK** olarak
pinli — altı mevcut aile adını, label'ını ve bayt sırasını korur),
`tests/unit/test_async_runtime.py` (`system_heartbeat` muafiyeti kaldırıldı — artık her actor
`run_sync` kullanıyor).

**Ölçümler:** backend tam suite **3912 passed / 1 xfailed / 0 failed**, exit 0, coverage
**%93.52** (kapı ≥90), 22dk38s. Frontend **721 passed / 70 dosya**, coverage **%84.92 line**
(baseline %84.67). `ruff` + `ruff format` + `mypy` (396 kaynak dosya) temiz.
`make openapi-check` temiz.

**Bağımlılık:** `pyyaml>=6.0,<7.0` dev extras'a eklendi — contract testinin kural dosyasını
ayrıştırması transitive bir bağımlılığa güvenmesin diye.

**Codemap'ler PR #622 içinde güncellendi** (bu kapanışta tekrar üretilmedi):
`BACKEND_ROUTES.md`, `BACKEND_LAYERS.md`, `DATA_MODEL.md`, `JOBS_AND_EVENTS.md`.

### Dürüst sınırlar (kayda aynen geçer)

- **PromQL anlamsal olarak DOĞRULANMIYOR.** `promtool` kurulu değil, CI'da yok, repoda
  `prometheus.yml` yok. Contract testi **elle yazılmış bir tokenizer** kullanıyor. Yukarıdaki
  (b) kusurunu bir kapı değil, **insan review'ı** yakaladı. Dört alert'in dayandığı
  `job="entropia-api"` scrape adını **hiçbir şey zorlamıyor** — `prometheus.yml`'de değiştirilirse
  `EntropiaApiDown` ve `EntropiaMetricsDatabaseProbeFailing` sessizce eşleşmeyi bırakır.
- **Heartbeat YALNIZ `maintenance` kuyruğunu (`worker-default`) kanıtlar.** Ölü bir
  `worker-backtest` onu tazecik bırakır. Bu sınır modül docstring'inde, codemap'te, matriste ve
  runbook'ta yazılıdır — üstü örtülmedi.
- **Metriği OLMAYAN alanlar** (alert yazılmadı; `METRIC_ALERT_MATRIX.md` §4'te **kör nokta
  haritası** olarak kayıtlı, backlog değil uyarı): **Backtest** (admission / readiness /
  duration / bars / artifact — `jobs/backtest_engine.py`'de **logger bile yok**), **Agent
  coordinator** (tick / state / task / checkpoint / ToolCall error), **SSE** (connection count /
  dropped events / replay lag), **object storage** (availability / read-write / checksum),
  **backup age & verify status**, **DB pool utilization** (`create_async_engine`
  `pool_size`/`max_overflow` **ayarlamıyor**).
- **`correlation_id` worker log'larına ULAŞMIYOR.** `Job.correlation_id` kolonu var ama hiçbir
  actor onu log context'ine bağlamıyor.
- **structlog REDACTION PROCESSOR'ü YOK** — kural elle, call-site bazında uygulanıyor.
- **`EntropiaQueueNeverDrains` "hiç boşalmadı" DEMEZ.** `entropia_jobs_depth` bir GROUP BY
  ürünü olduğu için boşalan kuyruk **seri üretmez** ve `min_over_time` boşlukları atlar.
  Anotasyon ve runbook bunu açıkça yazar.

### Numaralandırma — dürüst not (ADIM 23 ve ADIM 24 kayıtsız)

Bu kapanış yazılırken doğrulandı: **ADIM 23 = PR #610** (DR öncesi gerçek workload + coverage
kapısı, merged `2026-08-06`) ve **ADIM 24 = PR #619** (`docs/performance/README.md` +
`query_budgets.json`, load/query bütçeleri) **main'e indi ama `PROJECT_HISTORY.md`'de kayıtları
YOK**. Aynı dalgadaki #620/#621 (nightly failure notice) ve #614 (supply-chain gates) de
kayıtsız. Bu boşluk bu slice'ta **kapatılmadı** — kapsam ADIM 25'ti; `## ADIM 9 / ADIM 10 —
kayıt boşluğu (dürüst not)` ile aynı türden bir borç olarak burada bildiriliyor.

## ADIM 26 (observability) — alert kuralları gerçek bir PromQL kapısına bağlandı (PR #624)

> **Bu kayıt yazıldığında PR #624 AÇIKTI, merge EDİLMEMİŞTİ.** "landed" demiyorum
> çünkü inmedi. Okurken önce `gh pr view 624 --json state,mergedAt` ile doğrula.

**Branch** `ci/promtool-alert-rules-gate`, base `708ec07` · commit'ler `ed2d387` +
`68313ad` · **migration YOK**, alembic head `0043_i08_registry_strategy_fks` değişmedi ·
OpenAPI yüzeyi değişmedi · **frontend etkilenmedi** (hiçbir frontend dosyasına dokunulmadı).

### Kapatılan boşluk

ADIM 25, 11 alert kuralını **hiçbir PromQL doğrulaması olmadan** sevk etti: `promtool`
kurulu değildi, CI'da yoktu, repoda `prometheus.yml` yoktu. Bedeli hipotetik değil,
**ölçülmüştü** — iki paging kuralı `up{...} == 1 and absent(...)` biçiminde çıktı.
Bu ifade parse olur, yüklenir, kapsam gibi görünür ve **hiç ateşlenemez**: `absent()`
etiketsiz bir eleman döndürür, `and` ise varsayılan olarak tüm etiket kümesini
eşleştirir, dolayısıyla `job`/`instance` taşıyan `up` ile asla eşleşmez. Onu bir kapı
değil, insan review'ı yakaladı. Ayrıca dört kural `job="entropia-api"` adına bağlıydı
ve bu adı **yalnızca bir yorum satırı** iddia ediyordu.

### Ne sevk edildi

* **`scripts/alert-rules-gate.sh`** — `promtool check config` → `check rules` →
  `test rules`. Araç, resmi Prometheus imajından **digest ile pinlenmiş** gelir
  (`prom/prometheus@sha256:63805ebb8d2b3920190daf1cb14a60871b16fd38bed42b857a3182bc621f4996`,
  v3.5.0 LTS) — `security.yml`'deki gitleaks/trivy pin deseninin aynısı. Digest,
  sürüm+checksum'dan güçlüdür çünkü aracın **kendi bağımlılıklarını da** sabitler.
  Yeni marketplace action yok, indirilen binary yok, repo secret'ı yok.
* **CI job `Alert rules — promtool`** (`ci.yml`) — bloklayıcı, **paralel** koşar →
  eklenen wall-clock **0**. Ölçüm: **43 sn soğuk** (imaj çekimi baskın) / **3 sn sıcak**
  yerelde, **14 sn** CI'da. `Backend — lint, type, test` (~42 dk) dokunulmadı; ayrı
  job olmasının nedeni bu — kapı ne Postgres'e ne Python ortamına ihtiyaç duyar.
* **`ops/prometheus/prometheus.yml`** — `job_name: entropia-api`'yi kontrol edilebilir
  bir olguya çevirir. `rule_files` ve `credentials_file` **göreli**; Prometheus göreli
  yolları config dosyasının kendi dizinine göre çözer (`JoinDir`), böylece `ops/` tek
  parça mount edilip taşınabilir. `scrape_interval: 30s` = `SCHEDULER_TICK_SECONDS`.
* **`ops/alerts/entropia.rules.test.yml`** — 15 promtool unit-test case'i: bayat
  heartbeat, hiç kaydedilmemiş heartbeat, absent DB gauge'ları, sıkışmış lease, iki
  outbox lag katmanı, drenaj olmayan kuyruk (**ve drene OLAN kuyruk**), terminal
  başarısızlıklar, sürekli 5xx, en büyük bucket taşması, artı **"sağlıklı stack
  hiçbir şey ateşlemez"** case'i (tüm `ALERTS` kümesi üzerinde).

### Neden `alert_rule_test` DEĞİL de `ALERTS{...}` — kalıcı gerekçe

promtool'un `alert_rule_test`'i alert'in **anotasyonlarını tam olarak** karşılaştırır.
Ampirik olarak doğrulandı: `exp_annotations` verilmediğinde `Annotations:{}` beklenir
ve test kırmızı olur. Yani her beklenen alert dokuz operatör anotasyonunu **birebir
tekrar yazmak** zorunda kalırdı. Bu kopya kaçınılmaz olarak `entropia.rules.yml`'den
sapardı ve **sapma, geçen bir test gibi görünürdü** — tam olarak bu slice'ın karşı
çıktığı kusur. Sentetik `ALERTS{alertname=…, alertstate=…}` serisi üzerinde assert
etmek aynı semantiği verir (`for:` süresi, pending/firing geçişi, etiket yayılımı)
ve kural dosyasını tek doğruluk kaynağı olarak bırakır. Test dosyası hiçbir eşiği
veya ifadeyi tekrar yazmaz: **girdi** verir, **sonuç** üzerinde assert eder.

Yan bulgu, testlerde pinlendi: `and on()` boş etiket kümesinde eşleşir ama **sol
tarafın etiketlerini KORUR**, dolayısıyla iki absence alert'i `job`/`instance` taşır.
Bu, onları routable yapan şeydir — instance etiketi olmayan bir absence alert'i
*hangi* API'nin veritabanını kaybettiğini söyleyemezdi.

### Contract testleri (5 yeni, `test_alert_rules_contract.py`)

`test_every_job_matcher_names_a_declared_scrape_job` ·
`test_the_scrape_config_loads_the_shipped_rule_file` ·
`test_the_scrape_interval_is_no_slower_than_the_scheduler_tick` ·
`test_the_metrics_scrape_presents_a_credential` (dosya-tabanlı Bearer zorunlu,
literal `credentials` yasak) · `test_every_alert_has_an_evaluated_firing_case` —
sonuncusu, değerlendirilmiş firing case'i olmayan kuralı reddeder, yani ucuz metin
kapısı gerçek PromQL kapısını sessizce geçemez.

### Kapı kendi kendine test edildi (4 kanıt, hepsi geri alındı)

| # | Enjekte edilen kusur | Sonuç |
|---|---|---|
| A | `on()` silindi — **tam olarak ADIM 25 kusuru** | `check rules` **SUCCESS: 11 rules found**, `test rules` **FAILED — `got: nil`** |
| B | Geçersiz PromQL (`>> 1200(`) | `check rules` FAILED `213:15 … unexpected <op:>>` |
| C | Scrape job `entropia-backend` yapıldı | 2 contract testi kırmızı, 4 etkilenen kuralı adıyla söyler |
| D | Bir firing assertion'ı `pending`'e düşürüldü | `test_every_alert_has_an_evaluated_firing_case` kırmızı |

### Yerelde yeşil, CI'da kırmızı — TEKRARLAMA

İlk CI koşusunda kapı `promtool: error: stat /ops/prometheus/prometheus.yml:
permission denied` ile düştü. `mktemp -d` **0700** izinli, çağıran kullanıcıya ait bir
dizin üretir; resmi Prometheus imajı **`nobody` (uid 65534)** olarak koşar ve dizine
giremez. **macOS bunu tamamen gizler** — Docker Desktop sahipliği VM üzerinden eşler,
`chmod 700` + `--user 65534` ile bile hata yerelde **ÜRETİLEMEDİ**. Düzeltme
(`68313ad`): `chmod -R a+rX "$workdir"`, ve **placeholder token yazıldıktan SONRA**
(0600 bir credentials dosyası aynı hatayı bir adım sonra verir). Aracı root olarak
koşturmak yerine kopya genişletildi — içerik zaten takipli config + placeholder.

### Değişmeyen sınırlar

**11 alert'in ANLAMI değişmedi** — `entropia.rules.yml` diff'i **yalnızca yorum
satırları** (yorum-dışı değişiklikler filtrelenerek doğrulandı: boş). Hiçbir eşik
oynatılmadı, tüm derivation testleri korundu.
`test_no_rule_invents_an_absolute_latency_target` **aynen duruyor ve zayıflatılmadı**;
`docs/performance/README.md:144` p95 satırı bilerek boş kaldı. `/metrics`'in yaymadığı
hiçbir metrik adı eklenmedi.

### Ölçümler

Tam backend suite **tek pytest çağrısında**: **3917 passed / 1 xfailed / 0 failed**,
**exit code 0** (ayrı okundu, `| tail` kullanılmadı), coverage **%93.52** (kapı ≥90).
ADIM 25'teki 3912 + **tam olarak 5** yeni contract testi. `ruff check` ✅ ·
`ruff format --check` ✅ · `mypy src` ✅ 396 dosya. Hedefli koşu: 58 passed.
**Frontend koşulmadı — etkilenmedi.** Codemap etkisi **yok**: `docs/CODEMAPS/`
haritalarının hiçbiri `ops/` veya CI'ı kapsamıyor (grep ile doğrulandı).

### Dürüst sınırlar — KAPSAM DIŞI bırakıldı

* **Alertmanager / monitoring stack YOK.** `docker-compose.yml`'ye Prometheus servisi
  eklenmedi ve `prometheus.yml` bilerek `alerting:` bloğu taşımıyor: repo Alertmanager
  sevk etmiyor, var olmayan bir routing'i reklam etmek yalan olurdu.
  **`severity: page` hâlâ hiçbir alıcının okumadığı bir etikettir — kurallar doğru
  ateşliyor ama kimseye ulaşmıyor.** `METRIC_ALERT_MATRIX.md` §4'ün "The alert rules
  themselves" satırı bu yüzden silinmedi, **"Alert NOTIFICATION"** olarak yeniden
  yazıldı: değerlendirme kör noktası kapandı, **teslimat kör noktası kapanmadı**.
* Kurallar **gerçek üretim serilerine** karşı hiç değerlendirilmedi — var olan ama
  pratikte hiç doldurulmayan bir metrik burada sağlıklı görünür.
* **Sevk edilen Prometheus'un gerçekten bu dosyadan yapılandırıldığını hiçbir kapı
  kanıtlamıyor.**

---

## ADIM 27 — documentation-truth CI kapısı (PR #626)

**Branch `ci/documentation-truth-guard`** · base `7a9be2d` · merge commit **`0e67e9d`**
("ci(docs): prevent repository fact drift") · **86 dosya, +2665 / −29**.

**Ürün koduna dokunmadı:** migration **YOK** (alembic head `0043_i08_registry_strategy_fks`
sabit), yeni tablo YOK, yeni endpoint YOK, yeni sayfa YOK, yeni job YOK, OpenAPI değişmedi,
`ENGINE_VERSION` değişmedi, `SHARED_ALLOCATION_STATUS` = `future_dev` (containment KAPALI),
frontend etkilenmedi.

### Neden — üç ölçülmüş sapma, üçü de gerçek

Kapı hipotetik bir riske karşı yazılmadı. `ci.yml`'deki adım yorumunun kaydettiği üç olay:

1. **Bayat-base docs PR'ları `PROJECT_HISTORY.md`'den kayıt sildi — üç kez** (#590 ADIM 18,
   211 satır; #604 ADIM 22 + ADIM 16, 194 satır). Hiçbir CI kapısı `docs/` okumuyordu.
2. **`CLAUDE.md` haftalarca "4 deliberate xfail" reklamı yaptı**, gerçek sayı 1 olduktan
   sonra bile.
3. **Aynı tablo toplamı iki belgede farklı sevk edildi:** `DATA_MODEL.md` 102,
   `CODEMAPS/README.md` 104 — ikisi de elle sayılmıştı. **Gerçek 104.**

### Ne indi

**`scripts/generate_repository_facts.py`** — 873 satır, tek dosya, harici bağımlılık yok.
`collect_facts(root)` on olgu ailesini toplar; alt toplayıcılar: `collect_alembic` (head +
revision sayısı), `collect_database` (tablo/FK), `collect_http_api` (path/operation),
`collect_frontend_routes` (router path + nav item), `collect_engine_and_capabilities`
(`ENGINE_VERSION`, capability matrisi), `collect_tests` (statik **collection** sayıları,
`_count_python_tests` yardımcısıyla), `collect_acceptance` (kriter/clause),
`collect_visual_and_deviations` (PNG/baseline/prototype/a11y/sapma).

Üç artefakt tek kaynaktan üretilir: `render_markdown` → `docs/generated/repository_facts.md`,
`render_json` → `docs/generated/repository_facts.json`, `render_readme_block` + `splice_readme`
→ `README.md` içindeki `<!-- BEGIN GENERATED: repository-facts -->` /
`<!-- END GENERATED: repository-facts -->` bloğu.

**Kapı:** `.github/workflows/ci.yml` backend job'una bloklayıcı adım
**`Documentation truth gate (generated repository facts)`**, **OpenAPI drift guard'ından
SONRA** — sıra bilinçli: route olguları o adımın ürettiği şemadan okunur. Komut:
`uv run python ../scripts/generate_repository_facts.py --root .. --check`
(`working-directory: backend`).

`--check` üç bağımsız kontrolü birden reddeder:

* **`check_artifacts`** — `docs/generated/repository_facts.{json,md}` veya README bloğu bayat.
* **`check_classification`** — `CLASSIFIED_GLOBS` (`docs/*KICKOFF*.md`, `PROJECT_HISTORY.md`,
  `POST_V1_SPEC_GAP_BACKLOG_*.md`, `V18_R2_ROADMAP.md`, `docs/audit/*.md`,
  `docs/implementation/*.md`) içinden bir belge `doc-status` işareti taşımıyorsa, **birden
  fazla** belge `current` iddia ediyorsa, ya da `ALWAYS_HISTORICAL_GLOBS`'taki bir kayıt
  `current` işaretliyse. İşaret `STATUS_MARKER_RE` ile **ilk 3 satırda** aranır.
* **`check_assertions`** — `INVARIANT_GLOBS` (`README.md`, `CLAUDE.md`, `backend/README.md`,
  `frontend/README.md`, `docs/README.md`, `docs/CODEMAPS/*.md`, `STAGE2_HANDOFF.md`,
  `STAGE_BUILD_PLAN.md`, `ARCHITECTURE.md`, `DOMAIN_MODEL.md`, `USAGE.md`) içinde ağacın
  yalanladığı bir alembic head (`HEAD_ASSERTION_RE`), `ENGINE_VERSION` (`ENGINE_VERSION_RE`)
  veya `SHARED_ALLOCATION_STATUS` (`SHARED_ALLOCATION_RE`) — ya da `INVARIANT_RULES`'un
  **beş yasak eşitlemesinden** biri: `A08_COMPLETE` (A-08 ekran-okuyucu kabulü "Complete"),
  `WCAG_CONFORMANCE` ("WCAG 2.2 AA uyumlu"), `RUN_IS_RESULT` (Backtest Run = Backtest Result),
  `SIGNAL_IS_PACKAGE` (Trading Signal / Trade Log = Package), `FUTURE_DEV_ACTIVE`
  (Future Dev çalışıyor/üretiyor).

İki kaçış valfi bilerek var: **`NEGATION_RE`** iddiayı *reddeden* satırı muaf tutar (bir yalanı
doğru biçimde yasaklayan cümle zorunlu olarak yalanın kelimelerini içerir; Türkçe'nin `-ma-/-me-`
ekli olumsuzları da listede), **`HISTORICAL_HEDGE_RE`** kendini geçmiş olarak çerçeveleyen satırın
eski bir revision adı taşımasına izin verir — repo kendi sapmasını böyle denetlenebilir tutar.

**Banner sabitleri `HISTORICAL_BANNER` / `CURRENT_BANNER` üreticinin içinde yaşar** — yeni belge
yazan herkes metni oradan birebir kopyalar, elle yazmaz.

### Sınıflandırma dalgası

77 belge `doc-status` işareti aldı: **76 `historical` + 1 `current`**
(o an `docs/ADIM26_LANDED_KICKOFF.md`). Dokunuşların **tamamı saf eklemeydi** —
76 dosya ×(+6/−0), 1 dosya ×(+4/−0), **sıfır silme**. `docs/CODEMAPS/README.md` ve
`DATA_MODEL.md` elle sayılan olgu tablolarını bıraktı; `CLAUDE.md` §Current position
"**SAYISAL OTORİTE BU BLOK DEĞİL**" pointer'ı aldı ve içindeki HEAD sha'sının
**yapısal olarak bayat** olduğunu (kapanış commit'i onu değiştirir) açıkça söyledi.

### Testler

`backend/tests/contract/test_repository_facts_guard.py` — **28 case** (16 `def test_`,
kalanı parametrize genişlemesi). Bunlar kapının kendi davranışını kilitler: bayat artefakt,
işaretsiz belge, iki `current`, `PROJECT_HISTORY.md`'nin `current` işaretlenmesi, beş
invariant kuralının her biri, ve negasyon/hedge muafiyetleri.

### Ölçümler

Sayısal otorite **`docs/generated/repository_facts.md`** — bu bölüme rakam kopyalanmıyor,
çünkü kopyalanan rakam bayatlar (bu slice'ın var oluş sebebi tam olarak budur). Artefaktın
kapsadığı aileler: alembic head + revision, tablo, FK, HTTP path + operation, frontend
router path + nav item, `ENGINE_VERSION`, capability matrisi, backend/frontend/e2e test
**collection** sayıları, acceptance kriter + clause, görsel PNG/baseline/prototype/a11y,
sapma satırları.

Kapanış öncesi tam backend suite (tek pytest çağrısı, exit code ayrı okundu):
**3945 passed / 1 xfailed / 0 failed**, exit **0**, coverage **%93.52** (kapı ≥90).
`ruff check` ✅ · `ruff format --check` ✅ · `mypy src` ✅ 396 dosya · OpenAPI drift guard ✅ ·
acceptance semantic scan ✅ · doc-truth `--check` ✅ · 28/28 guard testi ✅.
**Frontend koşulmadı — etkilenmedi.**

### Dürüst sınırlar

* **Kapı `0e67e9d` için main'de HİÇ KOŞMADI.** 2026-08-06 16:00–17:00 arasında GitHub
  Actions servis arızası vardı: job'lar `Set up job` aşamasında
  `Failed to resolve action download info. Error: Service Unavailable` ile öldü — repo kodu
  hiç çalışmadı. `7a9be2d` (#625) main run'ı bu yüzden kırmızı (**altyapı, kusur değil** —
  log ile doğrulandı), `0e67e9d` için main'de hiç run oluşmadı. `ci.yml` yalnız
  `push:[main]` + `pull_request:[main]` taşır, **`workflow_dispatch` YOK** → main'de elle
  run tetiklemenin yolu yok. `gh run rerun` de işe yaramaz: mevcut run `7a9be2d`'ye aittir
  ve kapı o commit'te henüz mevcut değildir. Adımın **ilk gerçek koşusu ADIM 27 kapanış
  PR'ıdır**.
* **Kapsam dışı, bilerek:** commit sha, timestamp, GitHub API durumu (açık PR/issue,
  workflow run) — bunlar sunucunun özelliğidir, ağacın değil; gömülmeleri artefaktı yeniden
  üretilemez ve yeşil tutulamaz kılardı. **Test PASS sayısı da kapsam dışı:** artefaktın her
  test sayısı statik bir yürüyüşten gelen *collection* sayısıdır ve satır adı bunu söyler.
  Pass sayısını yalnız tam bir CI koşusu bildirir. Bu yüzden `CLAUDE.md`'nin "HEAD `708ec07`"
  ve "PR #624 AÇIK, merge EDİLMEDİ" yalanlarını kapı **yakalayamadı** — üçü de merge
  edilmişti; ADIM 27 kapanışında **elle** düzeltildi.
* **İki olgu hâlâ elle sayılı ve kapı onları KORUMUYOR:** audit `event_kind` 126 literal;
  frontend 31 sayfa / 40 `lib/*.ts`.
* **Üretici `entropia`'yı import eder** → yalnız backend venv'inde koşar. Salt-docs
  katkıcısı artefaktı yeniden üretemez; kapıyı kırdığında düzeltmesi için backend kurulumu
  gerekir.
* **`INVARIANT_RULES` regex tabanlıdır** — aynı yalanı farklı bir cümleyle yazan metni
  kaçırır. **Tripwire'dır, kanıt değil.**
* **Kapı silmeyi görmez.** `check_classification` sınıflandırmayı denetler; bir docs PR'ının
  `PROJECT_HISTORY.md`'den kayıt silmesini engelleyen otomatik hiçbir şey **hâlâ yok**.
  Merge öncesi elle kontrol zorunlu: `git show <sha> -- docs/ | grep '^-## '`.
* **Kapanış ritüelinin 4. maddesi (memory checkpoint) YAPILAMADI.** Ne ecc knowledge graph
  MCP'si (`create_entities` / `create_relations`) ne de `claude-mem` kapanış oturumunda
  bağlıydı; bağlı tek bellek sunucusu `codebase-memory-mcp`'ydi ve o bir slice checkpoint'i
  tutmaz. Bu slice bellekten aranamaz — kaynağı bu kayıt ve `docs/ADIM27_LANDED_KICKOFF.md`.
  Sunucular bağlandığında geriye dönük yazılabilir: entity
  `Entropia ADIM 27 — documentation-truth CI`, ilişki `unblocks` → PR B.
* Devralınan açık sınırlar: **Alertmanager YOK** (ADIM 25/26 kuralları ateşliyor ama kimseye
  ulaşmıyor); **ADIM 23 ve ADIM 24 bu dosyada hâlâ KAYITSIZ**; ekran okuyucu (NVDA/VoiceOver)
  denetimi **YAPILMADI** — GitHub **#514** açık, kapatma yetkisi insandadır; **D-10** imzalı
  kalıcı kontrast sapması → WCAG 2.2 AA 1.4.3 karşılanmıyor.

### Devir

Kickoff `docs/ADIM27_LANDED_KICKOFF.md` (`doc-status: current`);
`docs/ADIM26_LANDED_KICKOFF.md` aynı commit'te `historical`'a çevrildi — kapı **tek bir**
`current` belgeye izin verir. Sıradaki tek adım değişmedi: **PR B — `ItemParticipant`
adaptörü + `jobs/backtest_engine.py:298` call site**.

## ADIM 28 — A-08 insan denetimi hazırlığı (PR #628, unblocker PR #629)

**Branch `a11y/a08-human-audit-preparation`** · base `81336e1` · merge commit **`20e942b`**
("a11y(a08): prepare the human screen-reader acceptance run") · **9 dosya, +1762 / −8**.
Aynı dalganın unblocker'ı: **PR #629** (`security/js-yaml-advisory-freeze`, merge `81336e1`,
1 dosya, +6/−0) — ayrı bir ADIM değil, bu dalganın önündeki kırmızıyı kaldıran tek satırlık
gerekçe kaydı.

**Ürün koduna dokunmadı:** migration **YOK** (alembic head `0043_i08_registry_strategy_fks`
sabit), yeni tablo YOK, yeni endpoint YOK, yeni sayfa YOK, yeni job YOK, OpenAPI değişmedi,
`ENGINE_VERSION` değişmedi, `SHARED_ALLOCATION_STATUS` = `future_dev` (containment KAPALI),
codemap değişmedi, `.github/workflows/` **hiç dokunulmadı**.

### Neden — A-08 sekiz gündür yalnızca düzyazıyla bekliyordu

GitHub **#514** 2026-07-30'dan beri açıktı ve issue ile denetmen arasında duran tek şey bir
metindi: hangi rotalar, hangi akışlar, hangi ortam, bulgu nereye yazılır — hiçbiri
çalıştırılabilir değildi. Bu slice **iskeleyi** kurar. **Denetimi YAPMAZ** ve buradaki hiçbir
çıktı denetim olarak kaydedilemez.

### Ne indi

**`scripts/a11y-audit-stack.sh`** (390 satır) — `up | validate | status | down`. Compose
projesi **her zaman** `entropia-a11y-audit`; `down` başka bir projeyi **reddeder**. Ortam
hermetik ve git-ignored `.env.a11y-audit` (`ENTROPIA_ENV_FILE` üzerinden), portlar
çakışmayacak şekilde ayrı. Tek ayar düğmesi **`A11Y_HOST`** (varsayılan `127.0.0.1`);
`0.0.0.0` **hard error** verir çünkü o bir bind adresidir, tarayıcının açabileceği bir adres
değil — LAN'a açmak isteyen gerçek IP'yi yazar ve bunun için açık bir uyarı alır. Teardown
bir **EXIT trap DEĞİL, açık alt komuttur**: tüketici CI değil, oturumun ortasındaki bir
insandır; script'ten çıkmak onun stack'ini yıkmamalıdır.

`validate` beş adımda **9 kontrol** koşar ve hepsi geçer: (1) API `/health/ready` + web app
servis ediliyor, (2) `/meta.auth_mode=session` — denetmenin gerçekten login olacağı profil,
(3) Admin oturumu alınıyor ve `/me.is_admin=true` (Trash / Panel sayfaları Admin ister),
(4) üç seed fixture'ı **satır üretiyor** — `SEED_E2E_GOLDEN` (market dataset), `SEED_ESP_TA`
(Package Library), `SEED_RATIONALE` (rationale families), (5) **23 denetim rotasının hepsi**
200 dönüyor. Amaç dar ve bilinçli: kimse bir NVDA oturumunu, ürün sebebiyle değil **seeding
sebebiyle** boş olan sayfalarda harcamasın. §5'in kendi metni bunun sınırını da söylüyor —
SPA her yolu shell ile yanıtlar, yani bu adım origin ve rota tablosunu kanıtlar, sayfanın
kendi sorgusunun başarısını **değil** (onu `specs/17-page-coverage.spec.ts` iddia eder).

**`docs/audit/a11y_screen_reader_audit_results.md`** (306 satır) — çalışma defteri.
§0 iki zorunlu kombinasyon için oturum başlığı (SR-1 = NVDA/Firefox/Windows,
SR-2 = VoiceOver/Safari/macOS), §1 **23 rota × 2 kombinasyon**, §2 **10 akış × 2**,
§3 **16 kolonlu** bulgu defteri + her kolonun izinli değer sözleşmesi, §4 sekiz adımlı
retest listesi, §5 dört çıkış kriteri, §6 otomasyonun **ne ölçtüğü ve ne anlama gelmediği**
+ K-1..K-6. Rota satırları elle yazılmadı: `screenshotMatrix.ts::TARGET_PAGES`'ten, yani
axe taramasının yürüdüğü **aynı** matristen üretildi. Belge `doc-status: historical`
işaretli — ileriye dönük bir defter olmasına rağmen, çünkü `ALWAYS_HISTORICAL_GLOBS`
`docs/audit/*.md`'yi asla `current` olamaz kılıyor; belge bu gerilimi ilk paragrafında
**açıkça** söylüyor, sessizce kabul etmiyor.

**`.github/ISSUE_TEMPLATE/a11y_screen_reader_finding.yml`** (189 satır) — defterin her
kolonu için bir alan, artı **ZORUNLU "duydum" beyanı**: bir ekran-okuyucu bulgusunu bir DOM
çıkarımından ayıran tek şey budur. Retest checkbox'ları da şablonda. `accessibility` ve
`a11y-screen-reader` label'ları bu dalgada repoda **açıldı** (ikisi de mevcut).

**`frontend/e2e/specs/20-a11y-prechecks.spec.ts`** (426 satır) — `@a11y` etiketli, dolayısıyla
`npm run a11y` (= `playwright test --grep @a11y`) onu **otomatik alır**; workflow'a tek satır
eklenmedi. Dört `test()` bloğu iki sınıfa ayrılmış durumda. **BLOCKING** yapısal önkoşullar:
birden fazla `<h1>` yok, tek `main`, `banner` + adlandırılmış `navigation`, dialog erişilebilir
adı + Escape kapatıyor + odak tetikleyiciye geri dönüyor. **ADVISORY** gözlemler: skip link,
`contentinfo`, başlık atlaması, positive `tabindex`, `aria-live` envanteri, focus indicator,
tab order. Ayrım gerekçeli: bir advisory'nin düzeltmesi bir **ürün kararıdır** ve bu slice'ın
onu verme yetkisi yoktur — kırmızı bir kapı o kararı **ihmalle** vermiş olurdu. Her kayıt
`screen_reader_verified: false` damgası taşır. Rapor `a11y-report/precheck-results.json`
**`.gitignore`'dadır** (yerel koşu çıktısı, takipli axe kanıtının yanında kanıt gibi
görünmesin diye); CI onu build artifact olarak yükler.

**`backend/tests/contract/test_a11y_audit_prep_contract.py`** (429 satır) — **21 test**
(20 `def test_`, biri parametrize genişlemesi; `--collect-only` ile doğrulandı). Kontratı
şuraya çiviler: defterin rotaları `screenshotMatrix.ts::TARGET_PAGES` ile, akışları
checklist ile, script'in seed bayrakları + rota listesi **ikisiyle birden**, ve defterin
completion sayaçları **kendi hücreleriyle** aynı olmak zorunda. Testler üç mutasyonla
ısırdığı doğrulanarak yazıldı — yeşil kalan bir kontrat testi kontrat testi değildir.

**`frontend/e2e/.gitignore`** (+14) — `precheck-results.json` ve
`axe-baseline.measured/tightened.json` ignore edildi. Bu bir temizlik değil, **hazırlık
sırasında gözlemlenen** bir tehlikeye karşı: yerel `npm run a11y` bu üç dosyayı takipli
`a11y-report/axe-results.json`'ın yanına yazıyor ve yanlışlıkla commit edilmeleri kolay.
Baseline dosyaları yeniden-kalibrasyon **girdisidir**, kendi başına kayıt değil.

**PR #629 — js-yaml `!!omap` advisory'si (GHSA-5p4m-2wfm-xmqj / CVE-2026-59870).**
Yayımlanınca `npm audit` kapısı **her dalda**, hiçbir bağımlılığa dokunmayan PR'larda bile
kırmızıya döndü. Düzeltilmedi, **gerekçesiyle donduruldu** (`scripts/npm-audit-gate.mjs`,
+6 satır). Gerekçe bilerek dar: erişilebilirlik zinciri `eslint@9 → @eslint/eslintrc →
js-yaml@4.3.0`; eslint bir **devDependency**'dir, js-yaml sevk edilen bundle'a hiç girmez —
ne artefakt ne request yolu ona ulaşır. Açık kod eslintrc'nin YAML config yükleyicisidir ve
burada eline **hiçbir şey verilmez**: proje flat-config (`frontend/eslint.config.js`) ve
repoda **hiçbir türde `.eslintrc` dosyası yok**, yani ayrıştırılacak bir YAML belgesi —
saldırgan kontrollü ya da değil — mevcut değil. `npm audit fix` yalnız-lockfile bir çare
sunmuyor; yayımlanan düzeltme yolu eslint@10, yani build-zamanı bir CPU-DoS için orantısız
bir major upgrade. Kayda **iki bitiş koşulu** yazıldı: eslint 9.x yamalı js-yaml'a geçtiğinde
**veya** repo bir `.eslintrc.y(a)ml` kazandığında bu gerekçe biter.

### Ölçümler

Sayısal otorite **`docs/generated/repository_facts.md`** (üretilmiş, CI'da kapılı).
Bu dalganın artefakta yansıyan deltası: backend **collected** 3395 → **3415** (328 → **329**
dosya), E2E test **call site** 73 → **81** (20 → **21** spec). Bunlar *collection* sayılarıdır,
pass sayısı değildir — satır adı bunu söyler.

Kapanış öncesi koşular: backend tam suite **exit 0, 0 failed**, coverage **%93.52**
(kapı ≥90); frontend **721 passed / 70 dosya**, **%84.92 line**; `npm run a11y` (`CI=true`)
**exit 0**; CI'da **"A11Y — axe-core scan"** PASS.

### Dürüst sınırlar

* **A-08 denetimi YAPILMADI.** Çalışma defteri **BOŞ**: bulgu defterinde tek satır yok
  (`*(none recorded — audit not run)*`), §5'teki dört çıkış kriterinin **dördü de ☐**
  (`0 / 2` kombinasyon, `0 / 46` rota, `0 / 20` akış). **Boş bir şablon kanıt değildir.**
  Hiçbir belge A-08'i `Complete` veya `PASS` gösteremez — defterin kendisi de dahil.
* **K-2..K-6 ÖLÇÜLDÜ ama DÜZELTİLMEDİ**; her biri bir ürün kararıdır ve bu slice'ın onu
  verme yetkisi yok. Erişim sayıları hazırlığın kendi precheck koşusundan gelir
  (23 rota, **0 blocking failure, 85 advisory gözlem**): **K-2** skip link yok — **23/23
  rota**, her rota tüm menü çubuğunu tab'layarak başlıyor (WCAG 2.4.1); **K-3**
  `contentinfo` landmark yok — **23/23**, shell hiç `<footer>` basmıyor; **K-4**
  `/user-manual`'da `<h1>` yok, kendini `<h2 class="page-title">` ile adlandırıyor
  (`UserManual.tsx:181`) — sapma `frontend/e2e/utils/pageTruth.ts:15`'te **zaten kayıtlı**;
  **K-5** başlık taslağı `h1 → h3` atlıyor — **21/23 rota**, setteki en yüksek erişimli
  yapısal gözlem; **K-6** focus indicator computed-style'da görünmüyor
  (`outline: none; box-shadow: none`) — UA varsayılan halkası hâlâ boyanıyor olabilir,
  **bunu yalnızca insan gözü karara bağlayabilir**. K-1 = **D-10**, yeniden dosyalanmaz.
* **D-10 sürüyor:** 45 aksan-mavisi düğüm, 2026-07-30 imzalı kalıcı sapma.
  **WCAG 2.2 AA 1.4.3 KARŞILANMIYOR**; ürün bu ölçüt için uyumlu sayılamaz ve bu slice
  hiçbir AA iddiası getirmez.
* **ÖNCEDEN VAR OLAN iki kararsızlık — bu slice'tan gelmiyor, ama kayda giriyor:**
  `14-keyboard-flow` **4 koşudan 1'inde** bir autofocus yarışında düştü; `13-a11y-scan`
  ilk denemede **GERÇEK bir ratchet ihlali** verdi (`arrange-metrics` sayfasında
  `color-contrast` 4 düğüm, baseline 2), retry'da 2 ölçtü. Yani o sayfayı şu an yeşil tutan
  şey CI'ın `retries: 1` ayarıdır (`playwright.config.ts:22` — `process.env.CI ? 1 : 0`),
  ölçümün kararlılığı değil.
* **GitHub #514 sahibi tarafından 2026-08-07T03:52Z'de KAPATILDI** (`state_reason:
  completed`), **denetim kanıtı olmadan** — ve her iki dalga commit'inden de **önce**.
  Bu bir OLGUDUR ve A-08'i tamamlanmış göstermez: kapatılan issue ile boş çalışma defteri
  arasındaki ayrışma sürüyor. Belgelerin bu ayrışmayı nasıl anlatacağı **AYRI bir slice'ın**
  işidir; burada yalnızca not düşüldü, düzeltilmedi.
* **Kapanış ritüelinin 4. maddesi (memory checkpoint) yine YAPILAMADI** — ADIM 27'deki
  ile aynı sebep: ne ecc knowledge graph MCP'si (`create_entities` / `create_relations`)
  ne de `claude-mem` bu oturumda bağlıydı. Bu slice bellekten aranamaz; kaynağı bu kayıt ve
  `docs/ADIM28_LANDED_KICKOFF.md`'dir. Sunucular bağlandığında geriye dönük yazılabilir:
  entity `Entropia ADIM 28 — A-08 audit preparation`, ilişki `unblocks` → PR B.
* Devralınan açık sınırlar: **Alertmanager YOK** (ADIM 25/26 kuralları ateşliyor ama
  kimseye ulaşmıyor); **ADIM 23 ve ADIM 24 bu dosyada hâlâ KAYITSIZ**; documentation-truth
  kapısı **silmeyi görmez** → docs PR'ı merge etmeden önce hâlâ elle
  `git show <sha> -- docs/ | grep '^-## '`.

### Devir

Kickoff `docs/ADIM28_LANDED_KICKOFF.md` (`doc-status: current`);
`docs/ADIM27_LANDED_KICKOFF.md` aynı commit'te `historical`'a çevrildi — kapı **tek bir**
`current` belgeye izin verir. **İsim çakışması bilerek yaratılmadı:** #627 "ADIM 27" adını
documentation-truth CI slice'ı için aldı, bu yüzden A-08 hazırlığı **ADIM 28**'dir; repoda
zaten iki çift-kullanılmış slice adı var ve üçüncüsü yaratılmadı. Sıradaki tek adım
değişmedi: **PR B — `ItemParticipant` adaptörü + `jobs/backtest_engine.py:298` call site**.

---

## ADIM 29 — A-08 kaydı #514'ün kanıtsız kapatılmasıyla uzlaştırıldı (PR #631)

**Docs-only.** Ürün kodu, test ve CI **davranışı** değişmedi. Migration yok, alembic head
değişmedi, `ENGINE_VERSION` değişmedi.

### Tetikleyen olgu

GitHub **#514** ("A-08: Complete human NVDA/Firefox + VoiceOver/Safari acceptance audit",
label `human-only` — *"Sadece insan kapatabilir; kanitsiz kapatma yasak"*) repo sahibi
tarafından **`2026-08-07T03:52:03Z`**'de `state_reason: completed` ile **KAPATILDI**.
Doğrulama: `gh issue view 514 --json state,closedAt,stateReason,labels`.

**Denetim koşulmadı.** ADIM 28 (#628/#630) yalnız iskeleyi kurmuştu;
`docs/audit/a11y_screen_reader_audit_results.md` **boş defter** olarak inmişti — §5'teki
dört çıkış kriteri de ☐, §3 findings register'da tek kayıt yok, §1/§2'deki 46 rota ve 20
akış hücresinin tamamı `—`.

Bu, **aynı issue'nun ikinci kanıtsız kapatılmasıdır**. İlki `2026-07-30T19:05:32Z`'deydi ve
2026-08-03 ground-truth denetiminde geri alınmıştı. **İkincisi geri alınmadı.**

### Sorun: iki iddia da yazılamaz

Belgeler *"A-08 açık issue #514'te izleniyor"* diyordu — issue kapandığı için **BAYAT**.
Ama *"A-08 tamamlandı"* demek de **YANLIŞ** olurdu — denetim yapılmadı. Kapanışın hangi
niyetle yapıldığı (bilinçli kabul mü, sehven mi) **agent'ın veremeyeceği bir karardır**.

### Karar: ayrışma ÇÖZÜLMEDİ, KAYDEDİLDİ

Kullanıcı iki çerçeveyi de kullanmayı tercih etti. Uygulanan sentez: belgeler **niyeti
hükme bağlamaz**, yalnız **olguyu** kaydeder ve **iki insan çözüm yolunu da açık listeler**.
Gerekçe — her iki ihtimalde de doğru kalan tek çerçeve budur:

* **(A) bilinçli kabul** yazılamadı çünkü **imzalayanın adı ve tarihi verilmedi**; D-10
  biçiminde imza uydurmak reponun kendi kuralının ("kanıtsız kapatma yasak", "boş şablon
  kanıt değildir") ihlali olurdu.
* **(B) sehven kapandı** tek başına yazılamadı çünkü **#514'ü yeniden açma yetkisi
  insandadır**; agent issue durumunu değiştiremez.
* Her iki okuma da A-08'i tamamlanmış **yapmaz**: (A)'da kabul edilen şey denetimin
  **yokluğudur**, (B)'de iş zaten açıktır.

### Kanonik kayıt — tek yer

`docs/audit/a11y_screen_reader_audit_results.md` §STATUS ▸ **"Tracking-issue state —
closure/evidence divergence"**. Diğer bütün belgeler buraya **işaret eder**, olguyu
tekrarlamaz. Blok üç şeyi sabitler:

1. Beş olgu + `gh issue view` ile **yeniden türetme** yolu (issue durumu, label, denetim
   yapıldı mı, çıkış kriterleri `0/4`, kayıtlı bulgu yok).
2. Hüküm cümlesi: **"A closed issue is not evidence of a completed audit."**
3. (A)/(B) tablosu — her satırda **gerekli insan işi**, ve (A) için *"No signer has been
   supplied, so no such record exists."*

### Dokunulan yüzeyler

| Dosya | Değişiklik |
|---|---|
| `docs/audit/a11y_screen_reader_audit_results.md` | §STATUS'a kanonik ayrışma bloğu; §5'e *"Closing the tracking issue satisfies none of the four"* |
| `docs/implementation/a11y_screen_reader_audit_checklist.md` | banner'a kapatma olgusu; §Çıkış kriteri'ne "iki kez kapatıldı"; denetçi satırı → *"artık hiçbir açık kayıt bu atamayı izlemiyor"* |
| `docs/implementation/v18_final_acceptance.md` | §6'daki 2026-08-03 bloğu **korundu**, altına `GÜNCELLEME (2026-08-07)` |
| `docs/implementation/entropia_v18_remediation_status.md` | aynı desen + `## Change log` 2026-08-07 girdisi + *"hâlâ açıktır (GitHub #514)"* parantezi düzeltildi |
| `docs/implementation/v18_visual_traceability.md` | Bucket 2 A-08 satırı → **"iş AÇIK, izleme KAPALI"** |
| `docs/audit/current_main_ground_truth_2026-08-03.md` | §16, §17, §18 ve **E-01** satırına tarihli ekler |
| `CLAUDE.md` | §Current position "Son dalga" + §Açık iş (dürüst sınır) |
| `docs/ADIM29_LANDED_KICKOFF.md` | yeni, `doc-status: current` |
| `docs/ADIM28_LANDED_KICKOFF.md` | `current` → `historical` (tek-`current` kuralı) |
| `scripts/generate_repository_facts.py` | `A08_COMPLETE` kuralının **mesaj metni** — *"GH #514 tracks it"* artık yanlıştı |

**`generate_repository_facts.py` değişikliğinin sınırı:** yalnız insan-okur mesaj string'i.
Kural kimliği `A08_COMPLETE` ve regex'i **aynen duruyor**, dolayısıyla `check_invariants()`
davranışı birebir aynı. `test_repository_facts_guard.py:166` kural **id**'sini assert eder,
mesaj metnini değil — test değişmedi.

### Tavizsiz çizgiler (korundu)

* Hiçbir belge A-08'i `Complete` / `PASS` / `Done` göstermiyor.
* *"An empty template is not evidence"* worksheet'te **duruyor**.
* **D-10 sürüyor** — WCAG 2.2 AA **1.4.3 karşılanmıyor**; AA uyumluluk iddiası yok.
* Otomatik çıktı (axe-core / keyboard / prechecks) ekran-okuyucu kanıtı **sayılmıyor**.
* **Tarihsel kayıt silinmedi:** 2026-07-30 kanıtsız kapatma ve 2026-08-03 yeniden açma
  kayıtları **duruyor**; üzerlerine 2026-08-07 olayı eklendi. `git show <sha> -- docs/ |
  grep '^-## '` boş.
* **#514'ün durumu DEĞİŞTİRİLMEDİ.**

### Doğrulama

* `tests/contract/test_a11y_audit_prep_contract.py` + `test_repository_facts_guard.py`
  `--no-cov` ile koşuldu.
* `scripts/generate_repository_facts.py --root .. --check` — *documentation-truth gate OK*.
* Yeni prose, `A08_COMPLETE` ve `WCAG_CONFORMANCE` invariant regex'lerini tetiklemiyor
  (`NEGATION_RE` muafiyeti ile birlikte doğrulandı).

### Devralınan açık sınırlar

* **A-08 denetimi YAPILMADI** ve **izlemesi kapalı** — iş açık, izleme kapalı. Çözüm
  (A) imzalı kalıcı sapma **veya** (B) #514'ün insan eliyle yeniden açılması; **ikisi de
  insan işi**, bu slice hiçbirini yapmadı ve yapamazdı.
* **K-2..K-6** ölçüldü, düzeltilmedi — her biri ayrı ürün kararı.
* **Alertmanager YOK**; **ADIM 23 ve ADIM 24 bu dosyada hâlâ KAYITSIZ**.
* **Memory checkpoint (kapanış ritüeli md. 4) YİNE YAPILAMADI** — ADIM 27/28'deki ile aynı
  sebep: ne ecc knowledge graph MCP'si ne `claude-mem` bu oturumda bağlıydı. Sunucular
  bağlandığında geriye dönük yazılabilir: entity `Entropia ADIM 29 — A-08 record
  reconciliation`, ilişki `unblocks` → PR B.

### Devir

Kickoff `docs/ADIM29_LANDED_KICKOFF.md` (`doc-status: current`); `ADIM28` aynı commit'te
`historical`'a çevrildi. Sıradaki tek adım değişmedi: **PR B — `ItemParticipant` adaptörü +
`jobs/backtest_engine.py:298` call site**.

---

## ADIM 23 — DR yedeğinden önce gerçek iş yükü; kanıt tabanları kapıya bağlandı (PR #610)

**Kod değişmedi (`backend/` dokunulmadı).** Migration yok, alembic head değişmedi,
`ENGINE_VERSION` değişmedi, OpenAPI değişmedi. Merge: `2026-08-06T04:09:15Z`.

### Tetikleyen olgu — DR kanıtı boştu

Sevk edilmiş harness'ın kendi çıktısı (Actions run `31038908690`, job `disaster-recovery`):

```
[7] audit_events    — 0 rows, fingerprint EMPTY
[7] outbox_events   — 0 rows, fingerprint EMPTY
[7] agent_checkpoint— 0 rows, fingerprint EMPTY
WARN [7] all three append-only planes were EMPTY — this run proves nothing …
```

**Kök neden:** `apps/seed.py` bir *fixture writer*, kullanıcı değil. Repository'ler
üzerinden yazdığı için `_audit_and_outbox`'a **hiç uğramıyor**; `infrastructure/s3/datasets.py`
içindeki dört object writer'dan **yalnız birini** çağırıyor. `market/raw`, `signals/source`
ve `create-package/baseline` prefiksleri hiçbir seed yolunda değildi — yani tüm object
kanıtı hiçbir operatörün üretmediği bir key şekline dayanıyordu.

### Seçim: (b) gerçek iş yükü + (c) ratchet

Brief üç seçenek sunuyordu. **(a) fixture'ı büyütmek** reddedildi — sayıyı büyütmek için
eklenen object ürün kanıtı değildir ve seed yazımı komut yolundan geçmediği için
`audit_events` yine sıfır kalırdı. **(c) tek başına** döngüseldi: aynı reponun kontrol
ettiği bir fixture'a taban koymak bugünkü sayıyı pinlemekten başka bir şey yapmaz.

### Değişen

| Dosya | Değişiklik |
|---|---|
| `scripts/dr-workload.sh` (**yeni**) | Tek authenticated `POST /trade-logs/source-assets`. Kendi principal'ını bootstrap eder (`AUTH_MODE=session`'da credentialless Admin yok), CSV'yi her koşuda damgalar (TL-15 content-addressed dedup sessizce no-op yapmasın), ve yanıt `deduplicated:true` gelirse **BAŞARISIZ olur** — dedup ne object ne audit satırı yazar, aksi halde hiçbir şey kanıtlamadan yeşil geçerdi |
| `scripts/dr-acceptance.sh` | Üç opsiyonel taban: `DR_MIN_EVIDENCE_TABLES`, `DR_REQUIRE_APPEND_ONLY`, `DR_MIN_OBJECTS`. Adım [7] artık boş kalan düzlemleri **adlandırır**, adım [8] kapsadığı **key prefikslerini** basar |
| `.github/workflows/install-acceptance.yml` | seed ile backup arasına workload adımı; tabanlar fixture+workload'ın gerçekten ürettiğine ayarlandı |
| `docs/BACKUP_DR.md` · `docs/INSTALL_ACCEPTANCE.md` | iddia kanıta hizalandı |

**Tabanlar varsayılan olarak KAPALI.** Elle tek yedek doğrulayan geliştirici CI'ın fixture
kapsamını karşılamak zorunda değil; yalnız `install-acceptance.yml` açar.

### Doğrulama (canlı Compose, izole portlar)

| Kontrol | Sonuç |
|---|---|
| Baseline yeniden üretildi | `0/0/0` append-only satır, 1 object |
| Workload sonrası | **3 audit + 2 outbox satırı, 2 object, 2 key prefix** |
| Tam zincir, tabanlar açık | `8 passed, 0 failed, 0 warned` — kalıcı WARN kayboldu |
| **Mutation kontrolü** | üç düzlem boşaltılıp tabanlar gerçeğin üstüne çekildi → **üçü de ateşledi**, `8 passed, 3 failed`, exit 1 |
| Default-off kontrolü | tabansız → exit 0, WARN korunuyor; mevcut çağıranlar etkilenmedi |

### Dürüst sınır

**`agent_checkpoint` hâlâ kapsanmıyor** — bir Agent tool çağrısı gerektirir.
`DR_REQUIRE_APPEND_ONLY` bu yüzden üçünü değil **en az birini** boş olmamaya zorlar ve
adım [7] her koşuda `NOT covered by this run: agent_checkpoint` basar; boşluk transkriptte
kalır, gizlenmez.

---

## ADIM 24 — yük ve sorgu regresyon bütçeleri (PR #619)

**Üretim kodu dokunulmadı.** Migration yok, `ENGINE_VERSION` değişmedi, OpenAPI/route/OCC/
Idempotency/SSE/frontend değişmedi, yeni bağımlılık yok. Merge: `2026-08-06T08:55:14Z`.

### Tetikleyen olgu

Entropia'nın **hiçbir performans kapısı yoktu**. Mevcut üç `*_query_count` testinin her
biri **tek yüzeyde tek tabloyu** pinliyordu — artık bir N+1'in yeşil suite'ten sağ çıkmasının
tam olarak yolu budur.

### Bloklayıcı kapılar (deterministik — round trip, milisaniye değil)

| Kapı | Yer |
|---|---|
| 6 yüzey için DB round-trip bütçesi | `backend/tests/integration/test_query_budgets.py` (ci.yml'nin mevcut pytest adımı içinde) |
| Load-driver karar mantığı + scenario/OpenAPI tazeliği | `backend/tests/unit/test_loadgen.py` |
| Load smoke: her senaryo 2xx yanıtlıyor | `performance.yml` → `load-smoke` (PR + push) |

Her yüzey **tek oturumda n=1 ve n=11**'de ölçülür ve **iki** şeye birden bağlanır: toplam
ve **öğe başına eğim**. Satır başına okumaya başlayan düz bir yüzey, küçük-n toplamı
değişmese bile eğimden düşer — bu kusurlar gerçekte böyle sevk edilir.

Bütçeler `docs/performance/query_budgets.json` içinde **ratchet** olarak yaşar
(`frontend/e2e/a11y-baseline.json` ile aynı deyim).

| Yüzey | n=1 | n=11 | öğe başına |
|---|---|---|---|
| `library.list_packages` | 3 | 3 | 0 |
| `results_history.list_backtest_results` | 6 | 6 | 0 |
| `readiness_check.market_data_leg` | 2 | 12 | **1** |
| `dependency_pins.ensure_pinned_resolvers_active` | 2 | 22 | **2** |
| `agent_workspace.list_tasks` | 1 | 1 | 0 |
| `audit_log.list_audit_events` | 1 | 1 | 0 |

### Kapının bulduğu iki açık N+1 — kaydedildi, ONARILMADI

* **#617** — Ready Check'in market-data ayağı `get_dataset_root`'u öğe döngüsü **içinde**
  çağırıyor; kullanıcının beklediği bir sayfanın gecikmesini composition'ın Strategy sayısı
  belirliyor. `test_readiness_query_count` bunu **hiç görmedi** çünkü tek tabloya filtreliyor.
* **#618** — Approve-Package pinned-resolver yeniden doğrulaması pin başına 2 okuma.

**Bilerek düzeltilmedi:** ölçen slice aynı zamanda fail-closed bir admission yolunu
değiştirmemeli. Her issue kabul ölçütünü adlandırıyor (bütçe satırını `per_item: 0`'a çek),
böylece düzeltme ve kanıtı **birlikte** iner.

### Bilerek bağlanMAYAN kapı: latency oranı

`--compare` / `_ratio_gate` yazıldı ve unit-test edildi ama **CI'da değil**: bandı
ölçümden türetmek mümkün olmadı — değişmemiş bir stack'e karşı arka arkaya iki tam koşu
kontrolü **4.4x** oynattı, normalize sonrası bazı senaryolar 3–5x. Bu kanıt üzerine band
seçmek **sayı uydurmak** olurdu; slice'a tam olarak bu yasaklanmıştı. Aktivasyon prosedürü
`docs/performance/README.md` §6'da: ≥5 nightly artifact topla, gözlenen yayılımı hesapla,
bandı ondan koy.

### Dürüst sınır

**Kanonik SLO YOK** — `grep -rniE '\bSLO\b|p95|p99' docs/spec/` **hiçbir şey** döndürmüyor.
`docs/performance/` içindeki her hedef bu yüzden **operational target** etiketli, ve
interaktif-okuma p95 satırı nightly gerçek artifact üretene dek **bilerek boş** bırakıldı.

---

## ADIM 29 (RC verification) — V18 Release Candidate kanıt dalgası (PR #632–#636, #637)

> **Ad çakışması uyarısı — ÜÇÜNCÜ kez.** Bu kayıt, yukarıdaki
> *"ADIM 29 — A-08 kaydı #514'ün kanıtsız kapatılmasıyla uzlaştırıldı (PR #631)"* ile
> **AYNI numarayı** taşıyor ama **AYRI iştir**. Ayrım **başlık ekiyle** yapılır, kural budur:
> **`ADIM 29 (A-08 kaydı)`** = #631 · **`ADIM 29 (RC verification)`** = bu dalga.
> Eksiz "ADIM 29" tek anlamlı **değildir**. `ADIM 16` ve `ADIM 21` için konan kuralın aynısı.

**Dalganın tipi:** P1–P12 adımlarının **hiçbiri kod değiştirmez** — yalnız kanıt üretirler.
Tek istisna **P9-B1** (aşağıda), ki o bir P adımı değil, P9'un bulduğu blocker'ın düzeltmesidir.

### Landed kanıt

| Adım | Konu | PR | Karar |
|---|---|---|---|
| **P1** | repository truth + kanıt iskelesi | #632 | PASS |
| **P3** | frontend kapıları (lint/typecheck/test/build) | #633 | PASS |
| **P12** | A-08 insan kabul kapısı — adjudication | #634 | **BLOCKED** |
| **P4** | migration + şema kanıtı | #635 | bulgu: **alembic check RED** |
| **P9** | güvenlik kapıları | #636 | **BLOCKED** (B1 + B2) |

Kanıt dizini: `docs/releases/evidence/2026-08-07/`.

### P4'ün bulgusu — kaydedildi, onarılmadı

`alembic check` **RED**: 40 index-name divergence + 1 redundant index. **Hiçbir CI
workflow'u `alembic check` koşmuyor** — yani bu sapma kapıya bağlı değil.

### P9'un iki blocker'ı

* **B1** — `GHSA-5p4m-2wfm-xmqj` (js-yaml, HIGH) donduruldu ama **gerekçesi yanlıştı**.
* **B2** — iki dondurulmuş HIGH advisory'nin **hiçbirinde imza yok** (ne sorumlu, ne tarih,
  ne son kullanma).

### P9-B1 düzeltmesi (PR #637 — **AÇIK, merge BEKLİYOR**)

> Bu satır **merge edilmemiş** bir PR'ı tarif eder. Kapandığında bu bloğu güncelle.

js-yaml freeze'inin gerekçesi *"`npm audit fix` offers no lockfile-only remedy; the
published fix path is eslint@10, a major upgrade"* diyordu. Bu iddia **freeze merge
edildiğinde zaten yanlıştı**: js-yaml `4.3.1` **2026-07-31**'de yayımlandı ve advisory'yi
yerinde yamalıyor; #629 freeze'i **2026-08-07**'de, yani **yedi gün sonra** indi.

Uygulanan: `npm audit fix --package-lock-only` → js-yaml `4.3.0` → `4.3.1`, **3 satırlık**
lockfile diff, `package.json` **byte-identical**; ve `scripts/npm-audit-gate.mjs`'ten
js-yaml girdisi **düşürüldü**. 2026-08-03'te brace-expansion çiftine uygulanan desenin
aynısı — kapının kendi yorumu bunu emrediyor: *"A freeze whose reason has expired is worse
than no freeze."*

Doğrulama: kapı exit **0** (tek frozen kayıt react-router, "frozen but no longer reported"
notu **çıkmıyor**); `npm ci` exit 0 (js-yaml **4.3.1**); lint/typecheck/build exit 0;
vitest **721 passed / 70 dosya**. **Lint belirleyicidir** — js-yaml bu ağaca yalnız
`eslint@9 → @eslint/eslintrc` yolundan girer.

**B2 KAPANMADI.** react-router freeze'i **imzasız** kalmaya devam ediyor; yalnız iki bayat
olgusu düzeltildi: pin **7.18.2 → 7.18.2** (exact, `7.18.1` değil) ve yamalı hat **8.3.0+**
(`8.2.1+` değil; advisory `>=7.12.0 <8.3.0`). Freeze'in **özü ayakta** — tüm 7.x etkilenmiş,
lockfile-only çare yok (`--force` yalnız `7.11.0`'a **downgrade** öneriyor). Kaydı
`.github/security-allowlist.json` disiplinine taşımak **zorunlu `owner`** istiyor
(*"the human accountable for revisiting it, not a team alias"*); **imzalayan verilmediği
için hiçbir sapma kaydı YAZILMADI**.

### KOŞULMAMIŞ P adımları — dürüst sınır

**P2, P6, P7, P8, P10, P11, P13 için hiç kanıt YOK.** P5 **koşuldu ama commit EDİLMEDİ**:
`entropia-v18-docker-auth-validation-52e446` worktree'sinde **untracked** duruyor
(`P5_docker_auth.md` + `p5_logs/`), kararı **PARTIAL — 1/4 PASS, 3/4 BLOCKED** (imaj
build'leri geçti; stack ayağa kalkma, health endpoint'leri ve smoke script'leri **yerel
Docker daemon'ın kilitlenmesi** yüzünden bloklandı — ürün kusuru değil, host kaynak
tükenmesi). `git clean` bu kanıtı yok eder.

### Süreç kusuru — P adımlarının tanımı REPODA DEĞİL

P1..P13 ayrıştırması **hiçbir repo belgesinde tanımlı değil**; yalnız bir sohbet
transkriptinde yaşıyor. Repoda bulunan tek üst otorite
`docs/spec/Entropia_V18_Nihai_29_Adimli_Claude_Opus_5_Prompt_Paketi.md` §ADIM 29'un
**15 zorunlu iş kalemi**. Bu, dalganın devredilebilirliğini kırar: temiz bir oturum
"sıradaki P adımı ne?" sorusunu **repodan yanıtlayamaz**.

### CI kusuru — main'e giden iki commit'in CI'ı HİÇ KOŞMADI

`ci.yml`'nin concurrency bloğu `cancel-in-progress: ${{ github.ref != 'refs/heads/main' }}`
ve yorumu şunu iddia ediyor:

> "never on main: every push to main must run to completion so each merged commit lands
> with a full, green CI check instead of a cancelled (incomplete) one."

**Bu niyet gerçekleşmiyor.** GitHub bir concurrency grubunda **yalnız BİR** pending koşu
tutar; yeni bir koşu kuyruğa girdiğinde önceki pending koşuyu **iptal eder**. Ölçülen:

| Commit | PR | CI koşusu |
|---|---|---|
| `1f24391` | #632 | success |
| `e8d1d48` | #633 | **cancelled — 0 job, HİÇ KOŞMADI** |
| `bc59dae` | #634 | **cancelled — 0 job, HİÇ KOŞMADI** |
| `6cd6172` | #635 | success |
| `169cfaa` | #636 | success |

Yani **iki merge edilmiş commit** tam CI kanıtı olmadan main'e indi. Kusur
**kaydedildi, onarılmadı** — düzeltmesi bir CI politika kararıdır.

---

## ADIM 30 — RC Blocker 2: kabul akışı harness kapsamı (PR #647)

**Dalganın tipi:** harness/test. **Ürün kodu değişmedi** — `backend/src` ve `frontend/src`
bu dalgada hiç düzenlenmedi; migration yok, lockfile değişmedi, `ENGINE_VERSION` sabit.

### Ne kapatıldı

`docs/releases/Entropia_V18_RC_Readiness_2026-08-07.md` §6.2'nin **birinci ve asıl**
blocker'ı: harness kapsam boşluğu. `scripts/acceptance.sh` bir konteyner sağlık kapısıydı,
`scripts/e2e-acceptance.sh` bir auth/kimlik bootstrap harness'ıydı; beş kabul akışının
hiçbirini uygulamıyorlardı.

**Yeni harness İCAT EDİLMEDİ.** Mevcut script'e beşinci alt-komut (`flows`) eklendi, gövdesi
`scripts/lib/acceptance-flows.sh`'e kondu; izolasyon sözleşmesi, hermetik env dosyası,
`dc`/`req` helper'ları ve PASS/FAIL sayacı **aynen** yeniden kullanıldı. Proje
`entropia-e2e-flows`, port bloğu 18030/18110/15462/16409/19030/19031 (a11y yığınının
182xx bloğundan ayrı), tohum `SEED_E2E_GOLDEN` + `SEED_ESP_TA` + `SEED_RATIONALE`.

### İki katman — biri diğerinin yerine geçmez

* **Tarayıcı katmanı:** hâlihazırda var olan yolculuklar **yeniden yazılmadı, koşuldu** —
  `05` + `18` (akış a), `20-library` (akış b), `06` (akış e'nin delete→purge ayağı),
  `E2E_BASE_URL` + `E2E_API_BASE_URL` izole yığına yönlendirilerek.
* **Sunucu katmanı:** hiçbir katmanın kapsamadığı her şey — ESP yaşam döngüsü + paket export
  zarfı, Trading Signal / Agent tool yüzeyleri, akış e'nin **restore** ayağı (spec 06 onu
  atlıyor), ve bir tarayıcının kanıtlayamayacağı dört değişmez.

### Dört tavizsiz kural — varsayılmadı, iddia edildi

1. **TS/TL Package değildir** — Library kataloğunda yok; paket kökü `GET /trading-signals/<pkg>` → **404**.
2. **Run ≠ Result** — hazır olmayan kompozisyonda run **409**, Results düzlemi **0 → 0**.
3. **UI gizleme authorization değildir** — **on** Admin/owner yüzeyi plain USER token'ı ile
   yeniden saldırıya uğradı, hepsi **403** (koşu log'unda sayıldı, elle değil): run admission ·
   library approve · library delete · ESP activate · agent runtime pause · `GET /trash-entries` ·
   trash detay · restore-preflight · restore · purge.
4. **Uzun iş durable kuyrukta** — directive **202**, purge **202** + `purge_job_id`,
   `af_follow_run` gerçek worker'ı yokluyor, senkron kestirme yok.

### Ölçüm (2026-08-10, `origin/main` @ `aabb85d` + dal)

`./scripts/e2e-acceptance.sh flows` → **60 passed / 0 failed / 2 skipped**, **exit 0**;
tarayıcı katmanı **5 passed (23.8s)**. O-30 doğrulandı: purge 202 gövdesinde
`deletion_state` = `root_lifecycle_state` = `purge_pending`. O-12 doğrulandı: çelişkili dual
token → **409 `OCC_TOKEN_CONFLICT`**. K-07 doğrulandı: `.exe` **ve** boş filename → **422
`FILE_TYPE_NOT_ALLOWED`** (fail-closed).

**İki SKIP, PASS değildir:** (i) pozitif ESP activate→deprecate koşulmadı — probe resolver
`validation_state=failed / vectors_run=0` veriyor, harness test vektörü sentezlemiyor; onun
yerine *doğrulanmamış resolver trusted-active'e yükseltilemiyor* iddia edildi (pozitif yol
in-process: `backend/tests/integration/test_esp_persistence.py`). (ii) Tool Gateway çağrı
günlüğü egzersiz edilmedi — taze yığında agent task yok.

### Raporun iki iddiası yeniden ölçüldü ve kayıt düzeltildi

1. **"Docker/OrbStack takılı (`docker ps` sürekli 124)" — yeniden üretilemedi.** Aynı makinede
   `docker version`/`compose version`/`docker ps -q`/`docker images -q` dördü de **exit 0**,
   anında. Raporun *kaynak baskısı* teşhisi doğru (host 8 GB, VM **3.89 GiB**, 18–21 konteyner,
   load tepe **18.08**), ama **daemon takılı** sonucu geçerli değil.
2. **"Beş akışın hiçbiri hiçbir katmanda doğrulanmadı" — (a) ve (b) için yanlıştı.** Terim
   taraması yalnız iki shell dosyasını kapsıyordu; oradan "hiçbir katmanda" genellemesine
   geçmek **tarayıcı katmanını atlamaktı**. Aday SHA'da E2E run **31364211010** (success)
   spec 05 ✓, spec 20-library ✓, spec 06 ✓, spec 04 ✓, spec 18 ✓✓ koşmuştu — suite 39 passed.
   Gerçekten kapsanmayanlar: **(c)**, **(d)**, **(e)'nin restore ayağı** ve dört değişmez.

### Ölçüm bir kez daha kanıtladı: sayı kopyalanmaz, koşulur

İki harness kusuru **ilk koşuda** ortaya çıktı ve düzeltildi, ikisi de ölçümle:
`API_CORS_ORIGINS` (web origin API allowlist'inde olmadığından her tarayıcı yolculuğu
düşüyordu — `OPTIONS /meta` Origin `:18110` ile **400** — oysa curl, Origin göndermediği için
aynı API'yi sağlıklı raporluyordu; `a11y-audit-stack.sh` tam bu tuzağı belgeliyor) ve
spec 05'in sabit-kodlu `http://localhost:8000/api/v1` yedeği (`utils/api.ts::API_BASE` ile
değiştirildi; `E2E_API_BASE_URL` yokken **aynı literal** → CI davranışı birebir korunur).

### P5'in bloke kalemleri de koşuldu (Docker çalıştığı için)

| Kalem | Exit | Sonuç |
|---|---:|---|
| §9.4 session-clean | **0** | PASS — 27 passed / 0 failed |
| §9.5 legacy-upgrade | **0** | PASS — 15 passed / 0 failed |
| §9.6 dev-auth | **0** | PASS — 9 passed / 0 failed |
| servis bazında health (`acceptance.sh`) | **0** | PASS — 15 servis, hiçbiri exited/restarted/unhealthy |
| `smoke.sh` | **0** | PASS |
| `worker-restart-smoke.sh` | **0** | PASS — 7 düzlem SIGKILL+restart, `package_root` 15→15, `audit_events` 69→69, `outbox_events` 40→40 |

**P5 böylece "1 PASS / 3 BLOCKED" yerine 4/4 ölçülmüştür.**

### Dürüst sınır — blocker neden AÇIK kalıyor

**`flows` bir CI kapısı DEĞİLDİR.** Yerel bir komuttur; hiçbir workflow onu koşmaz, yani
sunucu katmanındaki bir regresyon sessizce geri gelebilir. (Tarayıcı yarıları
`.github/workflows/e2e.yml` ile kapılıdır; sunucu yarıları hiçbir yerde değil.) Kapıya
bağlamak CI'da ikinci bir 12 konteynerlik yığın + koşu süresi demektir ve **bu slice'ta
bilerek yapılmadı** — insan kararıdır. §6.2'deki iki SKIP de açık iştir. Bu yüzden kayıt
"kapandı" değil, **"kısmen kapandı"**dır ve RC verdict'i **BLOCKED** kalır.

### Değişen dosyalar

`scripts/lib/acceptance-flows.sh` (YENİ, 625 satır) · `scripts/e2e-acceptance.sh`
(`flows` alt-komutu, `API_CORS_ORIGINS`, SKIP sayacı) ·
`frontend/e2e/specs/05-mainboard-ready-check-run.spec.ts` (API tabanı parametreleştirildi) ·
`Makefile` (`e2e-flows`) · `README.md` · `docs/E2E_ACCEPTANCE.md` ·
`docs/releases/Entropia_V18_RC_Readiness_2026-08-07.md` (§3/P5, §3/P6, §6.2, §6.2.1, §8, §9, §10) ·
`docs/releases/evidence/2026-08-10/` (1 belge + 8 ham çıktı).

---

## ADIM 31 — RC Blocker 3: fail-closed bildirim yolu (PR #649)

**Dalganın tipi:** ops/CI. **Ürün kodu değişmedi** — `backend/src` ve `frontend/` bu dalgada
hiç düzenlenmedi; migration yok, lockfile değişmedi, `ENGINE_VERSION` sabit,
`SHARED_ALLOCATION_STATUS` = `future_dev` (containment KAPALI). Migration, imza, tag,
release, issue açma/kapama **yok**.

### Ne kapatıldı

`docs/releases/Entropia_V18_RC_Readiness_2026-08-07.md` §6.3: **ateşleyen 11 alarm kuralının
hiçbiri bir insana ulaşmıyordu.** ADIM 25 kuralları yazdı, ADIM 26 onların *doğru* olduğunu
kanıtladı (promtool `check config` / `check rules` / `test rules`, bloklayıcı CI job'ı).
İkisi de teslimata dokunmadı. `severity: page` ve `severity: ticket` **hiçbir şeyin okumadığı
etiketlerdi** — ve o etiketlerin yedisi "ürün kullanılamaz", "Postgres erişilemez", "async
düzlem hiç kurulmamış" diyor.

### Karar: (A) sevk — (B) imzalı sapma SEÇİLMEDİ

Eksik olan bir on-call *organizasyonu* değil, bildirim *yolunun kendisiydi*; o yol repo içi
yapılandırmadır. Ayrıca: imzalayan verilmediği için agent zaten imza üretemez (D-10 ve
`security-allowlist.json` disiplini imzayı **adı verilmiş bir insana** bağlar).

### ÖNCE DOĞRULAMA — raporun beş iddiası yeniden ölçüldü

`origin/main` (`20108af`) üzerinde: `alerting:` bloğu **yok** · compose'da Prometheus ve
Alertmanager **yok** · `ops/ scripts/ .github/ backend/src/` içinde receiver/routing/silence/
on-call **yok** (üç dosya eşleşiyor, **hepsi yokluğu anlatan yorum**) · **11 kural**,
`page` **7** / `ticket` **4** · promtool job'ı `alerts` / `Alert rules — promtool`, **exit 0**.
**Beşi de doğru.** Ham çıktı: `docs/releases/evidence/2026-08-10/p10b_preexisting_state.txt`.

### Sevk edilen

| Kalem | Dosya |
|---|---|
| Routing ağacı | `ops/alertmanager/alertmanager.yml` — `page` → `entropia-page` (group_wait 30s, repeat **1h**), `ticket` → `entropia-ticket` (group_wait 5m, repeat **12h**). **Kök receiver GERÇEK**: eşleşmeyen alarm düşürülmez, page eder. 3 inhibit, **hepsi aşağı yönlü** ve üçünde de kaynak alarm teslim edilir |
| Fail-closed başlatıcı | `ops/alertmanager/entrypoint.sh` — `ALERTMANAGER_NOTIFY_URL` unset/boş/http(s) değilse **exit 78**. `ALERTMANAGER_NOTIFY_URL_TICKET` opsiyonel; boşsa ticket hattı page hedefine yönlenir ve **stdout'ta söylenir** (teslimat kaybı yok, yalnız granularite) |
| Prometheus başlatıcı | `ops/prometheus/entrypoint.sh` — `ENTROPIA_METRICS_TOKEN` zorunlu (anonim scrape 403 → `up == 0` → sürekli sahte page); config'i **`cp -R` ile birebir** stage eder |
| `alerting:` bloğu | `ops/prometheus/prometheus.yml` → `alertmanager:9093` |
| Servisler | `docker-compose.yml` — `profiles: ["observability"]`, iki kalıcı volume (silence + notification log restart'ı atlatmalı) |
| CI kapıları | `scripts/alert-notification-gate.sh` (amtool) + `backend/tests/contract/test_alert_notification_contract.py` (**21 test**). CI job'ı `Alert rules — promtool` → **`Alert rules and notification path`** olarak yeniden adlandırıldı |
| Uçtan uca kanıt | `scripts/alert-notification-proof.sh` + `ops/alertmanager/notification_catcher.py` + `docker-compose.proof.yml` |
| Runbook | `docs/runbooks/alert-notification.md` (YENİ) + `METRIC_ALERT_MATRIX.md` §4/§5 |

### Ölçüm (2026-08-10)

promtool **exit 0** (11 kural) · amtool gate **exit 0** · contract **79 passed** (21 yeni + 58 mevcut,
regresyonsuz) · backend tam suite **3987 passed / 1 xfailed / 0 failed**, coverage **%93.53** ·
ruff / ruff format / mypy / repository-facts **hepsi exit 0** · proof **exit 0**:

* **Faz 1 (fail-closed):** boş hedef → **exit 78** + değişkeni adıyla anan mesaj; URL olmayan
  değer → **exit 78**.
* **Faz 3 (provenance):** çalışma ağacı / mount / staged sha256 **üçü de
  `f1c1949c6d3382fa5450138604759509ac57262f93fbb219c3356b34e5be0e19`** ·
  `--config.file=/tmp/ops/prometheus/prometheus.yml` · parse edilmiş config tracked dosyadan
  okunan beş değeri taşıyor · yüklenen kural seti **11 = 11, diff boş**.
* **Faz 4 (delivery):** `api` servisi hiç koşmadığı için `up{job="entropia-api"} == 0`
  **basitçe doğru** — sentetik seri yok. `EntropiaApiDown` ateşledi ve alıcıya
  **`"receiver": "entropia-page"`, `"alertname": "EntropiaApiDown"`, `"severity": "page"`**
  olarak ulaştı.

### ÜÇ ÖLÇÜLMÜŞ TUZAK — tekrarlanmasın

1. **`GET /api/v1/status/config` byte-diff'i ASLA geçmez.** Prometheus config'i *marshalled*
   döndürür: `scrape_protocols` ve `runtime.gogc` gibi varsayılanlar enjekte edilir, tüm
   yorumlar silinir. İlk yazılan provenance kapısı tam bu yüzden kırmızı verdi — kapının
   tasarım hatasıydı, ürünün değil. Yerine geçen zincir: **sha256 + `--config.file` flag +
   parse edilmiş değerler + kural seti diff'i**.
2. **`amtool check-config`, notifier config'i OLMAYAN bir receiver'a SUCCESS döner** (v0.28.1'de
   ölçüldü). "Geçici placeholder receiver" tam olarak bu şekildir: yönlendirilen her alarmı
   kabul eder, hiçbirini teslim etmez, ve kapı yeşil kalır. `test_no_receiver_is_a_silent_black_hole`
   bu yüzden var.
3. **`docker compose logs | grep -q`, `set -o pipefail` altında bir tuzaktır.** grep ilk
   eşleşmede çıkar, docker SIGPIPE alır, pipeline başarısız görünür. **Gerçekleşmiş bir
   teslimat "gelmedi" diye okundu** (proof exit 255, oysa bildirim çoktan alıcıdaydı).
   Log'u önce dosyaya yaz, sonra grep'le.

### Neden `${VAR:?...}` kullanılmadı

Compose'un zorunlu-değişken işareti **tüm dosyanın** interpolation'ını iptal eder, yani
`prometheus`/`alertmanager` profil kapalı olsa bile repo'daki **her** `docker compose up`
kırılırdı (`acceptance.sh`, `e2e-acceptance.sh`, `a11y-audit-stack.sh`). Ret bu yüzden
**konteynerin içinde** yaşıyor: compose değişkeni **boş fallback** ile geçirir
(`${ALERTMANAGER_NOTIFY_URL:-}`), entrypoint reddeder. `test_the_alertmanager_service_has_no_default_destination`
tam olarak bu yazımı pinler — herhangi bir varsayılan reddedilir.

### Kendi hatam, kayda geçirildi

Suite'in **ilk** koşusu **1 failed** verdi: `test_repository_facts_guard.py::test_the_repository_itself_passes_the_documentation_truth_gate`.
Slice bir test dosyası eklediği için `docs/generated/repository_facts.*` + README'nin üretilmiş
bloğu bayatladı ve ikinci bir kickoff `doc-status: current` iddia etti. **Kapı tam olarak bunun
için var.** Artefaktlar yeniden üretildi (delta **yalnız** collection sayısı: 3415→3432, 329→330
dosya — alembic head / `ENGINE_VERSION` / route / tablo **hareket etmedi**),
`docs/ADIM30_LANDED_KICKOFF.md` `historical`'a indirildi, suite yeniden koşuldu.

### Mevcut yığına etkisi — YOK (ölçüldü)

Düz `docker compose up` iki yeni servisi **başlatmaz** (profil). `test_worker_plane_deployment.py`
etkilenmez (yeni servislerde `--queues` yok, `image` farklı); `test_default_credential_gate.py`
etkilenmez (`.env.example`'a yalnız ekleme yapıldı).

### KAPANMAYAN ARTIK — dürüst sınır

§6.3'ün **iki** doğrulanmamış noktası vardı; **ikincisi (provenance) kapandı**, **birincisi
kapanmadı**: **kurallar gerçek production serilerine karşı hiç değerlendirilmedi** — yalnız
sentetik seri, artı tek bir yapısal `up == 0`. Gerçek trafiğe göre yanlış ayarlanmış bir eşik
hâlâ *doğru* görünür. Repo içindeki hiçbir kapı bunu kapatamaz; **kalıcı imzalı sapma
DEĞİLDİR** ve öyle kaydedilmemiştir.

Blocker olmayan üç kalem raporun §6.7'sine işlendi: **P10-B3** delivery proof'u bir CI kapısı
değil · **P10-B4** monitörü izleyen yok (`prometheus_notifications_errors_total` Prometheus'un
kendi `/metrics`'inde, onu kimse scrape etmiyor) · **P10-B5** on-call rotasyonu / escalation /
acknowledgement yok (Alertmanager'ın ack kavramı yoktur; `repeat_interval` mekanizmanın
tamamıdır). Beş maddelik tam liste: `docs/runbooks/alert-notification.md` §5.

### Verdict

**Blocker sayısı 4 → 3. RC verdict'i BLOCKED KALIR** — 1 (A-08), 2 (kabul akışları `flows`
CI kapısı değil) ve 4 (react-router imzasız freeze) açıktır. Numaralandırma **bilerek
korunmuştur**: kalanlar (1), (2), (4) olarak anılmaya devam eder — yeniden numaralandırmak
bu belgeye atıf yapan merge edilmiş PR gövdelerini geçmişten koparırdı (ADIM 16 / ADIM 21
çakışmasında verilen kararın aynısı). **"READY" yazılmadı.**

Kanıt: `docs/releases/evidence/2026-08-10/P10B_alert_notification_path.md` +
`p10b_preexisting_state.txt` · `p10b_promtool_gate.txt` · `p10b_amtool_gate.txt` ·
`p10b_notification_proof.txt` · `p10b_contract_tests.txt` · `p10b_backend_suite.txt`.

---

## ADIM 32 — RC §6.7 / P9-F2: SPA origin'inde Content-Security-Policy (PR pending)

**Dalganın tipi:** güvenlik / sunum-katmanı başlık işi. **Ürün kodu değişmedi** —
`backend/src` ve `frontend/src` bu dalgada hiç düzenlenmedi; route path, react-query key,
OCC token, Idempotency-Key, hook, SSE taksonomisi, `lib/*.ts` **hiç dokunulmadı**.
Migration yok, `ENGINE_VERSION` sabit, `SHARED_ALLOCATION_STATUS` = `future_dev`,
lockfile değişmedi. Issue açma/kapama, tag, release **yok**. Base `f3986fa` (#649).

### Neden — ve iddia yeniden ölçüldü

RC readiness raporu §6.7'nin **P9-F2** kalemi: *"SPA origin'inde CSP yok."* Körü körüne
kabul edilmedi. `origin/main` `f3986fa` üzerinde `grep -rn 'Content-Security-Policy'
frontend/` → **boş**. `frontend/nginx-security-headers.conf` dört header veriyordu
(`X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy`,
`Permissions-Policy`) ve **CSP vermiyordu**. Repodaki tek CSP API'ninkiydi
(`apps/api/hardening.py:39` → `default-src 'none'`), ve onu
`tests/contract/test_hardening_contract.py:29` **canlı bir yanıt üzerinde** pinliyordu.
İddia doğruydu — ve **yürütülebilir bundle'ı sunan origin korumasızdı**.

Aynı ölçüm ikinci bir boşluk gösterdi: SPA origin'inin **dört mevcut header'ı da** hiçbir
zaman telden geri okunmamıştı. Hepsi bir config dosyası + düzyazı olarak sevk edilmişti.

### Sevk edilen politika — genişliği ölçüldü, varsayılmadı

`frontend/nginx-security-headers.conf`:

```
default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self';
connect-src 'self' <API origin>; base-uri 'none'; form-action 'self';
frame-ancestors 'none'; object-src 'none'
```

**`unsafe-inline` ve `unsafe-eval` YOKTUR** — gerekmediği **ölçüldüğü** için. Sevk edilen
`dist/`'ten: tek harici module script + tek harici stylesheet; `dist/index.html`'de inline
`<script>` **0**, inline `<style>` **0**; bundle'da `eval(` / `new Function(` **0**; built
CSS'te `data:` URI / `url()` / `@import` / `@font-face` **0**; `src/`'de `new WebSocket` /
dynamic `import()` / harici http(s) literali / `<form action=…>` **0**.

Direktif gerekçeleri (dosyanın kendi yorumunda tam hâli): `base-uri 'none'` — uygulama
`<base>` kullanmıyor, enjekte edilen bir tanesi her göreli varlık URL'sini yeniden
hedefler. `form-action` **`'self'`, `'none'` değil** — her `<form>` `onSubmit` +
preventDefault ve hiçbirinde `action` yok, ama `'none'` bir handler hatasından sızan
native submit'i de bloklayıp **görünür bir bug'ı görünmez** hâle getirirdi; `'self'`
origin-dışı sızma yolunu yine kapatır. `object-src 'none'` — `default-src` fallback'i
tarayıcıların tarihsel olarak yanlış yaptığı yer olduğu için tekrar bildirildi.
`frame-ancestors 'none'` ile `X-Frame-Options` **birlikte** sevk edilir (farklı tarayıcılar
farklı olanı okur).

### `connect-src` origin'i — build zamanında türetilir, runtime'da DEĞİL

`apiClient.ts:9` → `import.meta.env.VITE_API_BASE_URL ?? "/api/v1"`; Vite bunu **build
zamanında** bundle'a gömer, compose varsayılanı `http://localhost:8000/api/v1` yani
**cross-origin**. Bu yüzden `connect-src`'nin API origin'ini taşıması **zorunlu**.

Yer tutucu `__API_ORIGIN__`, `frontend/Dockerfile`'ın **build stage**'inde aynı
`VITE_API_BASE_URL` arg'ından türetilip yerine konur ve **yer tutucu hayatta kalırsa build
DURUR** (`! grep -q '__API_ORIGIN__'`). Runtime lookup **bilerek** seçilmedi, iki sebeple:
(1) bundle zaten yalnız Vite'ın gömdüğü origin'e konuşabilir, dolayısıyla bir runtime
değeri onunla **ancak çelişebilirdi**; (2) web konteyneri `read_only: true` koşuyor, yani
nginx'in envsubst entrypoint'i üretilmiş bir config'i **yazamazdı** zaten. Runtime stage
artık kaynağı değil, **üretilmiş** dosyayı kopyalar.

### Kapı — canlı yanıtı assert eder, config dosyasını değil

`scripts/spa-security-headers-gate.sh` (yeni). API'nin CSP testinin **aynası**: config
okumaz, telden okur. **İki yüzeyi** sorgular — `/` (SPA shell) **ve** hash'li bundle
(`/assets/…`, index.html'den keşfedilir, sabit yazılmaz). İkincisi gereksiz değil:
`location /assets/` kendi `add_header`'ını bildirir ve include tekrarlanmazsa sunucu
düzeyi header'ların **hepsi iptal olur** — bu regresyon bir kez gerçekten sevk edildi
(bkz. conf dosyasının başındaki yorum). CSP dahil **beş header'ın da** değerini
**birebir** karşılaştırır.

CI: `.github/workflows/install-acceptance.yml` → **`fresh-install`** job'ı (her PR + `main`
push'u), `Wait for the API and the web app` adımından hemen sonra. Oraya konmasının sebebi:
kapı, **sevk edilen Dockerfile'dan kurulmuş çalışan bir stack** ister ve build-time
substitution başka hiçbir yerde gözlemlenemez; o job zaten bu stack'i ödüyor. Ayrıca
`fresh-install-evidence` artefaktına `spa-security-headers.txt` olarak düşer.

**Negatif adım da bağlandı** — repo'nun kendi disiplini (*"a gate that has never been
observed failing is not a gate"*): yanlış bir `connect-src` origin'i beklendiğinde kapı
**exit 1** vermeli **ve** kırmızısı `content-security-policy` satırında olmalı. Rebuild
istemez, ~1 saniye sürer, ve karşılaştırmanın gerçekten ısırdığını kanıtlar.

### Ölçülen kanıt (2026-08-10, `docs/releases/evidence/2026-08-10/`)

| Faz | Ne kanıtlandı | Sonuç |
|---|---|---|
| 1 | Politika **yanıtta** (config'de değil) | `curl -sI :8080/` **ve** hash'li bundle → CSP ikisinde de, `connect-src 'self' http://localhost:8000` olarak çözülmüş |
| 2 | Kapı geçiyor | **exit 0** — 2 yüzey × 5 header = **10 PASS** |
| 3 | Kapı **kırmızıya dönebiliyor** | Sahte origin ile **exit 1**, kırmızı `content-security-policy` satırında; beklenen/gerçek değerler yan yana basılıyor |
| 4 | Politika **UYGULANIYOR**, sadece mevcut değil | Canlı sayfada: enjekte inline `<script>` **çalışmadı** (XSS payload şekli), inline `<style>` **uygulanmadı**, `setAttribute('style',…)` **uygulanmadı**; **CSSOM ataması uygulandı** |
| 5 | **Uygulama BOZULMADI** | Playwright e2e (`npm test`, e2e.yml'in çağrısının aynısı) → **39 passed / 1 skipped / 0 failed** (3.3 dk) |
| 6 | Sessiz kırılma **yok** | Kimliği doğrulanmış **9 route**'ta **101** React inline-style'lı öğe render oldu, console + pageerror'da **0 CSP ihlali** |

Ham çıktı: `p9f2_spa_csp.txt` · `p9f2_spa_csp_app_not_broken.txt`.

**Faz 4 neden bu slice'ın en önemli ölçümü:** kodda **814** adet React `style={{…}}` prop'u
var ve `style-src 'self'` inline style'ları **polislemekle** ünlüdür. Ama React bunları
`style` ATTRIBUTE'u olarak değil, **CSSOM üzerinden** (`node.style.setProperty`) uygular —
ve CSP CSSOM atamasını denetlemez. Bu **varsayılmadı**: canlı sayfada, sevk edilen
politikanın altında, üç şekil ayrı ayrı denendi ve yalnız CSSOM olanı geçti. İlk yüklenen
sayfada (login shell) **hiç** inline style yoktu — yani o sayfaya bakıp "çalışıyor" demek
bu soruyu **hiç sormamak** olurdu; kimliği doğrulanmış sayfalara geçmenin sebebi budur.

### Dürüst sınırlar — bu slice'ta KAPANMAYAN

- **Kapı yalnız `install-acceptance.yml`'de koşar**, `e2e.yml`'de değil. Aynı header'ı iki
  job'da ölçmek maliyeti ikiye katlar, kanıtı katlamaz — ama şu demek: web origin'ini
  kuran ama `install-acceptance` koşmayan bir yol header'sız kalabilir.
- **P11-1 hâlâ açık.** `main` üzerinde branch protection / ruleset yok, dolayısıyla bu kapı
  da diğerleri gibi **job kapısıdır, required status check DEĞİLDİR**. Kırmızıyken merge'i
  mekanik engelleyen bir şey yok. **Repo ayarı, insan kararı** — agent kapatamaz.
- **CSP `report-uri` / `report-to` taşımıyor.** Production'da gerçek bir ihlal hiçbir yere
  raporlanmaz, yalnız kullanıcının konsolunda görünür. Toplayıcı bir uç **yok** ve bu
  slice bir tane **uydurmadı**.
- **Politika tek bir deployment topolojisine göre doğrulandı** (compose: web `:8080`, API
  `:8000`, cross-origin). Reverse-proxy arkasında same-origin sunulan bir kurulumda
  `connect-src` **kendiliğinden** doğru daralır (göreli base URL → yalnız `'self'`), ama
  **o topoloji ölçülmedi**.
- **P9-F1 (`npm install` → `npm ci`) ve P11-1 bilerek DIŞARIDA** — ayrı PR'lar.
  `frontend/` altında `.dockerignore` **hâlâ yok**; yerel `node_modules` build context'ine
  girer (CI'da temiz checkout olduğu için CI'yı etkilemez). Bu P9-F1 alanıdır, burada
  düzeltilmedi.
- Readiness raporu §7'nin *"`.github` ağacında `1f4b88b` sonrası sıfır değişiklik"*
  cümlesi **ADIM 31'den beri bayattır**; ADIM 32 `install-acceptance.yml`'i de değiştirir.
  §6.7.1'de **kaydedildi**, §7 elle düzeltilmedi (o blok ADIM 29'un ölçümüdür).
- **Backend/frontend birim suite'leri yeniden KOŞULMADI.** Bu dalga tek satır Python veya
  TypeScript kaynağı değiştirmiyor (`backend/src`, `frontend/src`, `backend/tests`,
  `frontend/src/test` **dokunulmadı**), dolayısıyla onları koşturmak yeni bir olgu
  üretmezdi. Değişikliği **gerçekten** sınayan suite — Playwright e2e — koşuldu ve yeşil.
  `generate_repository_facts.py --check` **exit 0**.

### Verdict

**RC verdict'i BLOCKED KALIR. Blocker sayısı DEĞİŞMEDİ (üç: 1, 2, 4)** — P9-F2 bir blocker
değildi, §6.7'nin blocker-olmayan kalemlerinden biriydi. **"READY" yazılmadı.**

---

## ADIM 33 — RC §6.7 / P9-F1: frontend build reproducibility (PR pending)

**Dalganın tipi:** build tesisatı. **Ürün kodu değişmedi** — `backend/src` ve `frontend/src`
bu dalgada hiç düzenlenmedi; route path, react-query key, OCC token, Idempotency-Key, hook,
SSE taksonomisi, `lib/*.ts` **hiç dokunulmadı**. Migration yok, `ENGINE_VERSION` sabit,
`SHARED_ALLOCATION_STATUS` = `future_dev`. **`package.json` ve `package-lock.json`
İÇERİĞİ bilerek değişmedi** — bağımlılık yükseltmek ayrı bir karardır. Issue açma/kapama,
tag, release **yok**. Base `979094e` (#655).

Kapsam **yalnız P9-F1**. Aynı §6.7 tablosundaki **P11-1 (branch protection) ELE ALINMADI** —
repo ayarı, insan kararı, agent işi değil.

### Neden — ve iddia yeniden ölçüldü

RC raporu §6.7'nin **P9-F1** kalemi: `frontend/Dockerfile` `npm install` kullanıyor ve
`COPY package-lock.json*` glob'u lockfile yokluğunu tolere ediyor. **İki parça da doğru
çıktı**, ama iddianın **bugünkü etkisi** ölçülmeden yazılmamalıydı — ölçüldü:

- `npm install` bu ağaçta lockfile'ı **bit-bit değiştirmiyor** (`a8979c98…` → `a8979c98…`),
- `npm install` ile `npm ci` **bit-bit aynı bundle'ı** üretiyor: `dist/`'in dört dosyasının
  dördü de aynı sha256, çözünen bağımlılık ağacı da aynı (`npm ls --all --json` → `ec299ea6…`).

**Dolayısıyla bu bir DAVRANIŞ DEĞİŞİKLİĞİ DEĞİLDİR.** Bugün ikisi aynı sonucu veriyor;
değişen şey **garantidir**. Bu, P9'un kendi kaydıyla (`evidence/2026-08-07/P9_security.md`
§F-1: *"bugün fiilî ayrışma yok; reproducibility riski, açık bir güvenlik açığı değil"*)
**tutarlıdır** — ölçüm onu çürütmedi, doğruladı.

### Ne landed

`frontend/Dockerfile` (üç satır) — `COPY package.json package-lock.json ./` (**glob'suz**,
lockfile yoksa COPY katmanında durur) + `RUN npm ci`. `frontend/.dockerignore` (**YENİ**) —
`node_modules`, `dist`, `coverage`, `e2e`, `.env*`, `public/mockup_v18.html` ve build girdisi
olmayanlar. Sonuncusu **kozmetik değil**: `COPY . .` install'dan **sonra** geldiği için
host'un `node_modules`'ü image'inkinin üstüne biner ve `npm ci`'yi süs hâline getirir; bu
ADIM 32'de yerel image build'inde bizzat yaşanmıştı. Dosya olmadan `npm ci` **uygulanabilir
değildir**.

### Isırdığının kanıtı — iki negatif, her biri kontrolüyle

Bir kapının yeşil olması onu kapı yapmaz; her negatif, **eski davranışın aynı girdi altında
ne yaptığını** gösteren bir kontrolle ölçüldü.

| Durum | Sevk edilen | Kontrol (eski hâl) |
|---|---|---|
| Lockfile YOK | `docker build` **exit 1** — `"/package-lock.json": not found` | glob **exit 0** — eşleşme yok, uyarı yok, build lockfile'sız devam etti |
| `package.json` lockfile'da olmayan dep bildiriyor (`left-pad@^1.3.0`) | `docker build` **exit 1** — `EUSAGE … Missing: left-pad@1.3.0 from lock file` | `npm install` **exit 0** — sessizce uzlaştırdı, lockfile'ı **yeniden yazdı** (`a8979c98…` → `3d8c1b66…`) |

`.dockerignore` de kontrollü ölçüldü: zehirli bir geliştirici ağacı (host `node_modules`,
`dist/STALE.txt`, `e2e/node_modules`, `evil.example` işaret eden `.env`,
`public/mockup_v18.html`) dosya varken **beşi de dışarıda**, dosya kaldırılınca **beşi de
içeride**.

**Ölçüm sırasında rapor satırında OLMAYAN bir kusur bulundu:** Vite `public/`'i olduğu gibi
`dist/`'e kopyaladığı için, CLAUDE.md'nin tarif ettiği dev-only mockup kopyasını yapmış bir
geliştirici **v18 spec mockup'ını production image'ına** sevk ediyor ve nginx onu
`/mockup_v18.html` adresinden sunuyordu. `.dockerignore` satırı bunu kapatır.

### Kırılmadığı doğrulananlar

`docker build --no-cache` **exit 0**, **84 MB** (2026-08-07 RC ölçümü de 84 MB) · sevk
edilen bundle host'ta `npm ci` ile üretilenle **bit-bit aynı** (js/css/favicon/index.html) ·
bu build'in context'inde zehir **duruyordu** ve image'a **girmedi** · **ADIM 32'nin CSP
kapısı** canlı konteynerde (`--read-only --tmpfs /tmp --cap-drop ALL`) `/` ve hash'li
bundle'da **10/10 PASS**, ve yanlış `connect-src` iddia edildiğinde hâlâ **exit 1** — kapı
hâlâ kapı.

### Honest boundary'ler

- **Frontend test suite KOŞULMADI.** `src/` altında tek dosya değişmedi; değişen yüzey build
  tesisatıdır ve o, image build'i + bundle hash karşılaştırmasıyla doğrulandı. Bu bir
  **gerekçedir, ölçüm değil** — bu kayıt suite'in yeşil olduğunu **iddia etmiyor**; otorite CI'dır.
- **Backend suite de koşulmadı** — bu dalga tek satır Python değiştirmiyor.
- **Tedarik-zinciri savunması değildir:** lockfile'a *sadakati* zorlar, lockfile'ın
  *içeriğini* denetlemez. `npm audit`'in 3 high-severity bulgusu **ele alınmadı**.
- **`npm ci` build'i hızlandırmaz** — RC 2026-08-07 ölçümünde image build'i 588,9 s'ti ve
  `npm ci` onun 579,1 s'iydi; bu dalga o profili değiştirmedi.
- **`e2e/` bütün olarak dışlandı**, istenen üç alt yol ayrı ayrı değil. Gerekçe: kendi
  `package.json`/lockfile'ı olan bağımsız bir Playwright paketidir ve `npm run build` onu hiç
  okumaz (`tsconfig.json` yalnız `"src"` içerir). İstenen üçü kapsamın içinde; ek olarak 142
  commit'li screenshot baseline'ı da context'ten çıkar. İstenen asgarinin **üstüne** çıkan
  bilinçli bir karar.
- **ADIM 32'nin bu dosyadaki başlığı hâlâ `(PR pending)` diyor**, oysa o dalga **#655 olarak
  merge edildi** (`979094e`). Başlık **bilerek düzeltilmedi**: `.claude/hooks/docs-history-guard.py`
  bir `## ` başlığının `origin/main`'de olup yeni içerikte olmamasını **kayıt silme** sayar ve
  commit'i reddeder — başlığı yeniden yazmak tam olarak o kapının önlemek için var olduğu şeye
  benzer. Ayrışma burada **kaydedildi**; düzeltmek insan kararıdır.

### Verdict

**RC verdict'i BLOCKED KALIR. Blocker sayısı DEĞİŞMEDİ (üç: 1, 2, 4)** — P9-F1 bir blocker
değildi, §6.7'nin blocker-olmayan kalemlerinden biriydi. **"READY" yazılmadı.**

---

## ADIM 35 — RC §6.7 / P6-ek + P6-6: harness fail-fast dayanıklılığı (PR pending)

**Dalganın tipi:** harness/script. **Ürün kodu değişmedi** — `backend/src` ve `frontend/src`
bu dalgada hiç düzenlenmedi; route path, react-query key, OCC token, Idempotency-Key, hook,
SSE taksonomisi, `lib/*.ts` **hiç dokunulmadı**. Migration yok, `ENGINE_VERSION` sabit,
`SHARED_ALLOCATION_STATUS` = `future_dev`. Issue açma/kapama, tag, release **yok**.
Base `970ec81` (#656).

Kapsam **yalnız §6.7'nin P6-ek ve P6-6 kalemleri**. Dört blocker ve §6.7'nin diğer kalemleri
(P9-F1 kapandı, P10-B2, P11-*, P10-7, P1-B1/B2, P8-B*, P1-Gate3) **girmedi**.
**P11-1 (branch protection) ELE ALINMADI** — repo ayarı, insan kararı, agent işi değil.

### Neden — iddialar yeniden üretildi, kabul edilmedi

Kusur sınıfı tek: **bir harici araca evet/hayır sorusu sınırsız soruluyordu.** İkisi de tam
olarak bu yüzden elle fark edilmedi — asılı kalma "biraz uzun sürüyor" gibi görünür.

- **P6-ek.** PATH'e cevap vermeyen bir `docker` konarak `e2e-acceptance.sh session`
  koşuldu: **25s sonra hâlâ koşuyordu**. `FATAL … exit 2` dalı probe'un **hemen altındadır**
  ama probe hiç dönmediği için asla alınamaz. Bir guard'ın kendisi asılı kalıyorsa guard
  değildir.
- **P6-6, iki ayrı biçimde.** (a) Takılmış `dropdb` → script süresiz asılı. (b) `dropdb`
  **başarısız** → `|| true` yuttu → artık scratch DB yüzünden `createdb` patladı →
  **`exit 1`**, yani dosyanın kendi başlığında "yedek geri yüklenmiyor" diye belgelenen kod.
  **Hiç okunmamış, sağlam bir yedek bozuk diye raporlandı.** Rapor bunu "raporlayabilir"
  diye yazmıştı; ölçüldü, **raporluyor**.

### Ne indi

| Dosya | Ne |
|---|---|
| `scripts/lib/bounded.sh` (**YENİ**) | `bounded_run SECONDS CMD…` → komutun kendi statüsü ya da **124**. Öldürdüğü bir komut için **asla 0** dönemez |
| `scripts/e2e-acceptance.sh` | preflight'ın iki probe'u sınırlı; `dc_probe` / `inspect_field` (kısa sorgular) sınırlı; `teardown` sınırlı. `dc up --build`/`exec`/`logs` **bilerek sınırsız** |
| `scripts/backup-verify.sh` | `dropdb`/`createdb`/`psql`/`pg_restore` sınırlı; **yeni `exit 3` = doğrulanamadı**; ön-koşu `dropdb` artık **katı** (eskiden `\|\| true` ile yutuluyordu) |
| `backend/tests/contract/test_harness_failfast_contract.py` (**YENİ**) | 12 test; PATH'e sahte binary koyup exit code + sınırlı dönüş süresi assert eder |

**Exit-code taksonomisi — üçü ayrı, bilerek.**
`e2e-acceptance.sh`: `0` her adım geçti · `1` bir adım düştü · `2` harness **hiç koşamadı**
(Compose yok · daemon erişilemez · daemon **HUNG**; üçü ayrı mesaj).
`backup-verify.sh`: `0` geri yükleniyor · `1` geri yüklenmiyor — **YEDEK hakkında** karar ·
`3` doğrulanamadı — **ORTAM hakkında** karar. `3` sıfır değildir: **belirsizlik BAŞARISIZ
sayılır**, yalnız artık neyin başarısız olduğu hakkında yalan söylemiyor.

**Ters yöne kayma yasak ve testli.** Bir yedek doğrulayıcısında asıl felaket, bozuk yedeği
sağlam raporlamaktır. İki kontrol testi bunu kilitler: tutarsız dump hâlâ **1**, sağlam
yedek hâlâ **0**.

**Eşikler gerekçeli — sihirli sayı yok.** Sağlıklı host ölçümleri: `docker version` 1.44s ·
`docker compose version` 0.16s · `dropdb` (mevcut DB) **4.83s** — raporun işaret ettiği
çağrı — `createdb` 0.92s · `psql` 0.13s. Varsayılanlar: docker probe **20s** (~14×), pg
kontrol düzlemi **60s** (~12×), `pg_restore` **1800s** (süresi dump'la ölçeklenir, ayrı
eksen). Hepsi env ile geçersiz kılınabilir; test 3s ile aynı kod yolunu koşar.

**`bounded_run`'ın iki inceliği ölçülerek bulundu.** (i) `kill -0` ile yoklama, kabuğun
çocuğu reap etmesiyle **yarışır** → sonuç gerçek bir `wait`'ten alınır, yoklamadan değil.
(ii) Yalnız doğrudan çocuğu öldürmek **yetmiyor**: `docker compose …`, compose eklentisini
`docker`'ın **çocuğu** olarak koşar; hayatta kalan torun `x="$(bounded_run …)"` borusunu
açık tutar ve 2s'lik sınıra karşı çağıran **60s** bloke ölçüldü. Bu yüzden **süreç grubu**
öldürülür (`set -m` + `kill -TERM -$pid`). GNU `timeout` **kullanılmadı** (macOS'ta yok);
`wait -n` yok, kesirli `sleep` yok → macOS'un **bash 3.2**'si ile CI'ın bash 5'i aynı yolu
koşar.

### Ölçüm

| Senaryo | rc | süre |
|---|---|---|
| docker CLI tamamen takılı | **2** | 3.0s |
| yalnız `docker version` takılı | **2** | 3.0s |
| daemon anında reddediyor (**kontrol**) | **2** | 0.0s — "not reachable", "HUNG" **değil** |
| `dropdb` takılı | **3** | 6.1s |
| artık scratch DB (**eski yanlış-negatif**) | **3** | 0.0s |
| `pg_restore` takılı | **3** | 3.1s |
| dump gerçekten tutarsız (**kontrol**) | **1** | 0.1s |
| **sağlam yedek** (**kontrol**) | **0** | 0.1s |

**Testlerin ısırdığı kanıtlandı.** `git stash` ile yalnız iki script düzeltmeden önceki
hâline döndürülüp aynı 12 test koşuldu: **5 failed / 7 passed** (369s) — dördü
`pytest.fail("… STILL RUNNING after 90s")`, biri `assert 1 == 3`, yani P6-6'nın
yanlış-negatifi. Düzeltmeyle **12 passed / 23.3s**. Geçen 7 kontrolün 3'ü `bounded_run`'ın
kendi semantiğidir ve o dosya bu slice'ta doğdu → bu üçü için "önce kırmızıydı"
**iddia edilmiyor**.

**Regresyon testi bir CI kapısıdır** (backend job'ında koşar) — `flows` harness'ının aksine.

**Üretilmiş belgeler tazelendi.** Yeni test dosyası collection sayısını değiştirdiği için
`documentation-truth` kapısı kırmızı verdi; `scripts/generate_repository_facts.py` yeniden
üretildi ve **tek satır** oynadı: *Backend tests collected* `3432 in 330 files` →
`3444 in 331 files` (alembic head, `ENGINE_VERSION`, tablo/FK, HTTP operation sayıları
**değişmedi**). Kapı ikinci bir düzyazı kusuru daha yakaladı: base `970ec81`'de
`docs/ADIM32_LANDED_KICKOFF.md` hâlâ `doc-status: current`'tı ve bu slice'ın kickoff'u ikinci
bir "canlı" belge yaratıyordu → `historical`'a **indirildi** (içeriği silinmedi). Sonradan
#657 aynı düzeltmeyi main'de yaptı; canlı kickoff artık yalnız `docs/ADIM35_LANDED_KICKOFF.md`.

**Numara çakışması ve bir belge onarımı (dürüst kayıt).** Bu slice önce **ADIM 34** olarak
yazıldı. Çalışırken **#657 kendini ADIM 34 ilan ederek merge oldu** (o da çift-numaradan
kaçınmak için ADIM 33 → ADIM 34'e taşınmıştı). Merge edilmiş bir başlık değiştirilmez, bu
yüzden **taşınan bu slice oldu: ADIM 35**; rapor alt bölümü de §6.7.3 → **§6.7.4**. İkinci
bir kusur daha vardı: dalın uzaktaki main-merge'ü (`d68fb45`)
`docs/ADIM34_LANDED_KICKOFF.md` çakışmasını **iki belgeyi iç içe geçirerek** çözmüştü —
#657'nin gövdesi bu slice'ın "Paste-ready resume prompt" başlığının altına yapışmış, bu
slice'ın kendi resume prompt bloğu ise **silinmişti**. İkisi de git'teki temiz
sürümlerinden **yeniden kuruldu**: `ADIM34_LANDED_KICKOFF.md` ← `origin/main` (#657, 133
satır, `historical`'a indirildi), `ADIM35_LANDED_KICKOFF.md` ← `672ebe1` (bu slice, 107
satır, `current`). Hiçbir kayıt kaybolmadı; ikisi de tekrar tek başlıklı ve tam.

**Yerel kapılar:** `ruff check .` temiz · `ruff format --check .` 788 dosya formatlı ·
`mypy src` 396 dosyada sorun yok · `pytest tests/contract/test_repository_facts_guard.py
tests/contract/test_harness_failfast_contract.py --no-cov` **40 passed** ·
`generate_repository_facts.py --check` **exit 0**. **Tam suite yerelde YENİDEN KOŞULMADI** —
dürüst gerekçe: paralel bir worktree oturumu aynı log dosyasını ezdi, dolayısıyla kendi
koşumun sonucunu iddia edemem. Ürün kodu değişmediği için otorite **CI'dır**.

### Verdict ve dürüst sınırlar

**RC verdict'i BLOCKED KALIR. Blocker sayısı DEĞİŞMEDİ (üç: 1, 2, 4).** P6-ek ve P6-6
blocker değildi, §6.7'nin blocker-olmayan kalemleriydi. **"READY" yazılmadı.**

- **"Docker düzeldi" DENMİYOR.** Daemon'a dokunulmadı; ölçüm günü zaten normal cevap
  veriyordu (`docker version` rc=0). Değişen tek şey: bir sonraki takılma **kendini
  bildirecek**, teşhis tahmine kalmayacak.
- **P5/P6 blocker'ı KAPANMADI.** §6.2'nin açık ekseni kapsam boşluğu ve `flows`'un CI
  kapısı olmaması — o ADIM 30'un eksenidir, bu slice ona dokunmaz.
- Aynı kusur sınıfı **yalnız bu iki script içinde** tarandı; başka script'lere süpürülmedi.
- `dc up --build` / `exec` / `logs` sınırsız bırakıldı: dürüst süreleri dakikalardır,
  sınırlamak **sahte başarısızlık** üretirdi — bu slice'ın tam tersi.

Ham kanıt: `docs/releases/evidence/2026-08-10/P6FF_harness_failfast.md` +
`p6ff_measurements.txt` · `p6ff_tests_before_fix.txt` · `p6ff_tests_after_fix.txt`.
Kanonik rapor kaydı: `Entropia_V18_RC_Readiness_2026-08-07.md` **§6.7.4** (+ §6.2 notu).
## ADIM 34 — RC §6.7 / P4-1 + P4-2: model↔migration şema paritesi (PR #657)

> **Numara notu:** bu slice önce `ADIM 33` olarak yazılmıştı; çalışma sürerken **#656
> (P9-F1) `ADIM 33` adıyla merge oldu**. PR'ı henüz merge edilmediği için bu slice temiz
> biçimde **ADIM 34'e taşındı** — `CLAUDE.md`'nin kaydettiği çift-numara sorunundan bir
> tane daha üretmemek için. Merge edilmiş bir başlık değiştirilmedi.

**Branch** `fix/rc-p4-schema-parity` · **base** `970ec81` (ADIM 33 / #656 merged) ·
**alembic head DEĞİŞMEDİ** (`0043_i08_registry_strategy_fks`; bu dalgada migration YOK) ·
`ENGINE_VERSION` değişmedi · `docs/openapi.json` değişmedi · **ürün davranışı değişmedi**.

Kapsam **yalnız** RC §6.7'nin P4-1 ve P4-2 kalemleri. Dört blocker ve §6.7'nin diğer
kalemleri girmedi.

### Raporun iddiaları yeniden ölçüldü — dördü doğru, biri YANLIŞ

İzole yerel Postgres, `LC_ALL=en_US.UTF-8`, boş şemadan `alembic upgrade head` (exit 0)
sonrası `alembic check`: **exit 255** DOĞRU · `removed index` **39** / `added index` **39** /
`changed index` **1** / `removed unique constraint` **1**, `added/removed column` **0**,
`added/removed table` **0** DOĞRU · **40 gerçek sapma** DOĞRU · `.github/workflows/*.yml`
içinde `alembic check` **yok**, sapma sahipsiz DOĞRU.

**YANLIŞ:** §6.7'nin *"Emitlediği farkların tamamı index/constraint eksenindedir"* /
*"tip/server-default değişimi = 0"* iddiası. Aynı koşu **60 `modify_default`** işlemi de
emitliyor (40 tabloda 60 kolon). Rapor yalnız `compare.constraints`'in
`Detected added/removed …` satırlarını saymış; `compare.server_defaults` farklı bir cümle
kurar (`Dialect impl … detected server default on column X`) ve o taramaya takılmamış.
Sapmalar `alembic check`'in **ERROR** satırındaki operasyon listesinde hep vardı.
Rapora **P4-3** olarak yazıldı.

### Fix tipi 1 — sevk edilmiş ad kazandı, DB'ye dokunulmadı

39 sapmanın tamamı **yalnız adlandırma**: sevk edilen kısa ad (`ix_backtest_run_snapshot`)
karşısında modelin `index=True`'dan türettiği SQLAlchemy varsayılanı
(`ix_backtest_run_composition_snapshot_id`). Kolon kümesi, uniqueness ve partial-predicate
**aynı**. Merdivenin ilk basamağı seçildi: **migration'lara ve DB'ye dokunulmadı**, model
sevk edilen ada hizalandı — `__table_args__` içinde `Index("<sevk edilen ad>", "<kolon>")`,
dosyaların **zaten kullandığı ev stili**. Sevk edilen adlar **DB'den `pg_index` ile okundu**,
isim benzerliğinden tahmin edilmedi. `alembic revision --autogenerate` **koşulmadı**;
üretilen diff index DROP/CREATE içerecekti.

Dokunulan 9 model dosyası / 26 tablo: `agent_lab.py` (10), `backtest.py` (11),
`metric_profile.py` (4), `research_data.py` (4), `agent_tool_gateway.py` (2), `export.py` (2),
`create_package.py` (1), `instrument.py` (1), `market_data.py` (1). `index=True` sayısı
**176 → 137** (tam 39). Hiçbir sütun adı, tipi, nullability'si, FK'si veya UNIQUE
constraint'i değişmedi.

### P4-2 — yapısal, ama yine model tarafında kapandı

Migration 0016 `sa.Column("seq", …, unique=True)` **ve ayrıca**
`op.create_index("ix_agent_event_seq", …)` yazıyor → DB'de `agent_event_seq_key` (UNIQUE)
**artı** `ix_agent_event_seq` (non-unique). Model ise `unique=True, index=True`'yu birlikte
bildiriyordu; SQLAlchemy bunu **tek bir unique index**'e çökertir. Model artık sevk edilen
şekli bildiriyor: `unique=True` **ayrı**, `Index("ix_agent_event_seq", "seq")` **ayrı**.

**Fonksiyonel etkisizlik deneysel kanıtlandı:** aynı `seq` ile iki satır eklendiğinde
**iki yol da** reddediyor — alembic yolunda `agent_event_seq_key`, create_all yolunda
`ix_agent_event_seq`. Ayrışan tek şey hata mesajındaki addır; `seq` zaten `Identity()` ile
DB'den geldiği için ORM yolundan duplicate erişilebilir değil. Fazladan non-unique index
**kaldırılmadı** — bir index'i düşürmek ya da uniqueness'ını çevirmek semantik bir
değişikliktir, ayrı karar ve ayrı PR.

### Kapanış ölçümü

| Ölçüm | Önce | Sonra |
|---|---|---|
| `alembic check` index-ekseni operasyonu | **40** | **0** |
| Kurulum yolu paritesi (alembic ↔ `create_all`) | DIVERGENT — 361 vs 360; 40/39/1 | **BIT-IDENTICAL** — 361 vs 361; 0/0/0 |
| `add/remove column` · `add/remove table` | 0 · 0 | **0 · 0** |
| `alembic check` exit | 255 | **255** (P4-3 yüzünden) |

Tam backend suite **3987 passed / 1 xfailed / 0 failed**, coverage **%93.52** (kapı ≥90).
Integration testleri şemayı `create_all` ile kurar — index adlarının değiştiği **tam o yol**
— dolayısıyla suite bu değişikliğin gerçek regresyon testidir. `ruff` · `mypy` temiz,
`generate_repository_facts.py --check` **exit 0**, tek head, `upgrade → downgrade -1 →
upgrade` **4/4 exit 0**.

### Kapı — ve neyi ölçmediği

`scripts/schema_parity_gate.py` (YENİ), `ci.yml` `backend` job'ında **`alembic upgrade head`'in
hemen ardından**. Assert ettikleri: (1) alembic yolu ile `create_all` yolunun index kümesi
**bit-özdeş**; (2) autogenerate **sıfır** index/constraint operasyonu; (3) server-default
sapma sayısı **60 tavanını** geçemez; (4) başka hiçbir şema drift'i yok. **Exit 0 doğrulandı.**

Kapı `alembic check`'ten **daha güçlüdür**: alembic, operatör sınıfı taşıyan dört
`audit_events` expression index'ini (`gin_trgm_ops`, `varchar_pattern_ops`) **atlayıp "eşit
varsayar"**; kapı onları gerçek `pg_get_indexdef` üzerinden görür.

**Negatifi kanıtlandı.** İki sapma tipi de geçici olarak geri konuldu; ikisinde de **exit 1**
(P4-1 tipinde `remove_index`+`add_index`, P4-2 tipinde MIGRATION-ONLY `agent_event_seq_key`
+ DIFFERS). Geri alındıktan sonra kapı yeniden **exit 0**.

CodeQL PR üzerinde iki bulgu verdi, **ikisi de bu betikte** ve ikisi de düzeltildi:
`py/uninitialized-local-variable` (f-string içindeki koşullu ifadeler `_verdict()`
yardımcısına çıkarıldı) ve `py/unused-import` (models paketi artık `MODEL_PACKAGE` adına
bağlı ve bir başlangıç guard'ı tarafından **okunuyor** — import'un yan etkisi
`Base.metadata`'yı doldurmaktır). Kapının assert ettikleri değişmedi.

`ci.yml`'ın **concurrency kusuru zaten onarılmıştı** (satır 9–14) — `CLAUDE.md` onu açık
listeliyordu, **bayattı**; bu dalgada düzeltildi.

### Honest boundaries — bu slice'ta KAPANMAYAN

- **`alembic check` hâlâ exit 255** ve ne kapı ne belge bunu sıfırmış gibi gösterir.
  Sebep **P4-3**: 60 `modify_default` sapması. **Ölçüldü, düzeltilmedi** — modele
  `server_default` eklemek `create_all`'ın kurduğu şemayı değiştirir (P4-2 ile aynı aileden
  gerçek bir ayrışma), ayrı karar ve ayrı PR. Kapı sayıyı **tavana** bağladı: büyüyemez.
- Kapı **`alembic check`'in exit code'unu assert etmez**; adı da bunu söyler (*index axis*).
- **P11-1 hâlâ açık:** `main`'de branch protection / ruleset YOK → bu kapı da diğerleri gibi
  **job kapısıdır, required status check DEĞİLDİR**. Repo ayarı, **insan kararı**.
- `docs/CODEMAPS/DATA_MODEL.md` **tazelenmedi ve tazelenmesi gerekmiyor**: o harita
  kolon-seviyesi index/constraint detayı taşımadığını satır 290'da açıkça yazar, alembic
  head de değişmedi.

### Verdict

**RC verdict'i BLOCKED KALIR. Blocker sayısı DEĞİŞMEDİ (üç).** P4-1/P4-2 blocker değildi.
**"READY" yazılmadı.**
