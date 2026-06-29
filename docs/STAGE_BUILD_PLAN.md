# Entropia V18 — Staged Build Plan (Stage 0..8)

> **Authority:** Stage map per `docs/spec/Coder_AI_Asamali_Kodlama_Prompt_Set_v1_0.docx` and Master Reference §17 build order; domain rules per M0–M19 + CR-01..CR-09. Each stage lists backend modules (under `backend/src/entropia/`), API endpoints (`/api/v1` base), DB tables, frontend routes, and acceptance criteria. A stage is "done" only when its acceptance criteria pass **and** the INF baseline (Stage 0) stays green.
>
> **Layer placement rule (every stage):** route in `apps/api/routes/`, write use-case in `application/commands/`, read use-case in `application/queries/`, durable job body in `application/jobs/` (invoked by `apps/worker/actors.py`), pure model/policy/lifecycle in `domain/`, persistence/adapters in `infrastructure/`.

---

## Stage 0 — Skeleton (DONE / baseline)

**Goal:** Bootable modular monolith with canonical conventions. Validated by the **INF acceptance suite (INF-01..INF-10)** in `ARCHITECTURE.md §12.4`.

| Aspect | Detail |
|--------|--------|
| **Backend modules** | `apps/api/{main,context,deps,errors,sse}`, `apps/api/routes/{health,meta}`, `apps/worker/{__main__,actors}`, `apps/{agent_coordinator,scheduler}` (placeholders), `infrastructure/{postgres,queues,redis,s3,observability}`, `config/settings`, `shared/{ids,errors,responses,pagination}` |
| **API endpoints** | `GET /api/v1/health/live`, `GET /api/v1/health/ready`, `GET /api/v1/meta`, `GET /api/v1/events` (SSE heartbeat) |
| **DB tables** | none yet (`Base` metadata only); Alembic wired via `sync_database_url` |
| **Queues** | `default, data, backtest, agent, agent-high, maintenance`; `system_heartbeat` actor |
| **Frontend routes** | app shell, `/health` diagnostic, SSE client + TanStack Query provider |
| **Acceptance** | INF-01..INF-10 pass: boot, health/ready degradation, request/correlation ids, error envelope, validation 422, queue round-trip, object-storage reachability, SSE heartbeat+disconnect, cursor clamp, env/secret hygiene |

---

## Stage 1 — Common System Foundation

**Goal:** Identity/policy/audit/revision/concurrency/soft-delete/worker/artifact substrate that every later page reuses. (Master §17 step 2; M1–M3.)

| Aspect | Detail |
|--------|--------|
| **Backend modules** | `domain/identity` (principals, roles, policy ops, last-admin rule), `domain/revision` (root/revision/head model, content_hash), `domain/lifecycle` (enum registry CR-04), `domain/deletion` (soft-delete/trash/purge state machine), `application/commands/{soft_delete,restore,request_purge}`, `application/queries/audit_log`, `infrastructure/postgres/repositories` (entity_registry, revision repo, audit, outbox, trash), `infrastructure/queues` outbox relay (scheduler), `infrastructure/redis` idempotency cache, `infrastructure/s3` artifact put/get; replace `deps.actor_context` stub with real identity/role resolution |
| **API endpoints** | session/identity bootstrap; `DELETE /v1/entities/{id}` (soft); `POST /v1/trash/{id}/restore`; `DELETE /v1/trash/{id}/purge`; `GET /v1/trash` (Admin); `GET /v1/audit-events` (Admin); generic command idempotency + `If-Match`/`ETag` middleware |
| **DB tables** | `principals`, `human_users`, `agents`, `entity_registry`, generic `*_revisions` base, `audit_events`, `outbox_events`, `trash_entries`, `tombstones`, `idempotency_keys`, durable `jobs` table |
| **Cross-cutting** | optimistic concurrency (`expected_head_revision_id`/`expected_row_version`), transactional outbox, audit-on-mutation, ULID ids, NUMERIC decimals, UTC time fields |
| **Frontend routes** | auth/login shell, role-aware nav gating (UX only), conflict (409) + stale reload UX |
| **Acceptance** | Save inserts revision N+1 + advances head + writes audit; duplicate idempotent command = no-op; concurrency mismatch → 409; soft delete writes trash+snapshot+audit+outbox in one tx; restore reuses entity_id+revision; purge Admin-only async with preflight; non-Admin Trash → 403; last-admin demotion → `LAST_ADMIN_PROTECTED`; agent non-assignable → 422; outbox consumer failure does not roll back root |

---

## Stage 2 — Data & Package Domain

**Goal:** Market Data, Research Data, Create Package, Pre-Check, Package Library, ESP, Rationale Families. (Master §17 step 3; M4–M8.)

| Page (doc) | Backend modules | Key endpoints | DB tables |
|------------|-----------------|---------------|-----------|
| **Market Data (11)** | `application/{commands,jobs}/market_data`, `domain/market_data`, parser/validator on `data` queue | `request_market_dataset_analysis`, `start/finalize_market_raw_upload`, `confirm_market_schema_mapping`, `create_market_dataset_revision`, `approve_market_dataset_revision` (Admin), `GET /v1/market-dataset-revisions`, `resolve_approved_market_data_bundle` | `market_dataset_root/revision`, `market_raw_asset`, `market_processed_asset`, `market_schema_mapping`, `market_validation_run/issue`, `market_approval_decision`, `dataset_coverage_slice` |
| **Research Data (12)** | `application/{commands,jobs}/research_data`, `domain/research_data` (event_time vs available_time, usage_scope) | `CreateUploadSession`, `RequestResearchDatasetAnalysis`, `CreateResearchDatasetRevision(FromBase)`, `ApproveResearchDatasetRevision` (Admin), `RevokeResearchDatasetApproval`, `GET /v1/research-dataset-revisions`, `compile_agent_data_bundle`, `compile_backtest_evidence_bundle` | `research_dataset_root/revision`, `research_raw/native_asset`, `research_field_definition`, `research_market_link`, `research_time_policy`, `research_validation_run`, `research_feature_definition` |
| **Create Package (06)** | `application/{commands,jobs}/package_create`, async candidate-gen on `default` | `GET /package-catalog`, `CreateDerivedStrategyDraftFromPackage`, `SubmitCreatePackageRequest`, `CreateDraftPackageFromCandidate`, `StartPackageValidationRun`, `ApproveAndPublishPackageRevision` (Admin), `CreatePackageRevisionAttempt` | `package_root/revision`, `package_request`, `package_candidate`, `package_dependency`, `validation_run`, `artifact` |
| **Pre-Check (07)** | `domain/precheck` (parser/AST, not regex), `application/jobs/dependency_scan` | `POST /v1/package-requests`, `POST /v1/package-requests/{id}/pre-check` (202), `GET /v1/embedded-system-resolvers?canonical_key=`, gate on `generate-candidate` (409 BLOCKED/STALE) | `dependency_scan`, `embedded_resolver_registry` |
| **Package Library (08)** | `application/queries/package_catalog` (role-aware), `application/commands/package_lifecycle` | `GET /v1/packages` (cursor, facets), `GET /v1/packages/{id}`, `.../revisions:draft`, `:derive`, `:deprecate`, `DELETE /v1/packages/{id}` (soft) | reuses package tables + `package_usage_reference`, `package_export`, `approval_decision` |
| **ESP (09)** | `domain/esp` (resolver contract/signature/runtime), `application/commands/esp_lifecycle` | `GET /v1/embedded-system-packages`, `/{root}/activate` (Admin), `/deprecate` (Admin), `resolve_embedded_dependency(parsed_call, target_runtime)` | `package_root(embedded_system)/revision`, `embedded_resolver_contract`, `resolver_registry_entry`, validation evidence; seed `ESP_TA_{SMA,EMA,RMA,ATR,RSI,WMA,VWAP}` |
| **Rationale Families (10)** | `domain/rationale` (shared-edit exception), `application/commands/rationale` | `GET /v1/rationale-families?state=active`, `POST /v1/rationale-families`, `.../{id}/revisions`, `DELETE /v1/rationale-families/{id}`, `GET /v1/package-rationale-assignments`, `POST .../package-rationale-assignments:batch` (atomic) | `rationale_family_root/revision`, `package_rationale_assignment` |

- **Frontend routes:** `/data/market`, `/data/research`, `/packages` (Library), `/packages/create`, `/packages/embedded-system`, `/edit/rationale-families`.
- **Acceptance:** approval Admin-only (non-Admin → 403); revisions immutable, new version never auto-repins; Pre-Check uses AST not regex (comment/string `ta.rsi` creates no dependency); resolver match requires key + exact signature + active+passed+approved+trusted; `PackageKind` rejects signal/trade_log (`CLIENT_LEGACY_TYPE_REJECTED`); Parquet processed assets in object storage, metadata in Postgres; available_time/event_time enforced; rationale batch atomic all-or-nothing; ESP perf metrics N/A (never fabricated 0); seed family `Embedded System / TA Resolver` ACTIVE.

---

## Stage 3 — Mainboard & External Work Objects

**Goal:** Mainboard, Strategy Details, Add Outsource Signal, Trading Signal, Trade Log. (M9–M10 + external-object subsystem; CR-01.)

| Page (doc) | Backend modules | Key endpoints | DB tables |
|------------|-----------------|---------------|-----------|
| **Mainboard (01)** | `domain/mainboard` (composition fingerprint, kind guard), `application/commands/mainboard` | `GET /mainboards/default`, `POST /mainboards/{id}/items`, `PATCH /mainboard-items/{id}` (pin/enable/reorder), `POST /strategy-drafts`, `POST /external-work-object-drafts/{kind}`, `DELETE /work-objects/{root_id}` | `mainboard_workspace`, `mainboard_working_item`, `work_object_root/revision`, `mainboard_composition_snapshot` |
| **Strategy Details (02)** | `domain/strategy` (typed StrategyConfig compiler, sizing exclusivity, trigger source), `application/commands/strategy_draft` | `POST /strategy-drafts`, `.patch/.set_reference/.add_node/.validate`, `POST /strategy-drafts/{id}/save` (201 → root/revision/config_hash, ready_state=STALE), `mainboard_item.pin_revision` | `strategy_root`, `strategy_editor_draft`, `strategy_revision`, `strategy_revision_references` |
| **Add Outsource Signal (03)** | `domain/outsource` (type chooser, transient draft), `application/commands/outsource_draft` | `start_transient_outsource_draft`, `create_trading_signal_revision`, `create_trade_log_revision`, `attach_mainboard_item`, `pin_mainboard_item_revision`, `discard_transient_outsource_draft` | (no persistence on transient draft) |
| **Trading Signal (04)** | `application/{commands,jobs}/trading_signal`, import on `data` queue | `CreateTradingSignalAndAttach`, `CreateTradingSignalRevision`, `RequestTradingSignalImport`, `UploadSourceAsset`, `PinTradingSignalRevisionToMainboard`, `GetImportReport`, `RequestTradingSignalExport`, `SoftDeleteTradingSignalRoot` | `trading_signal_root/revision`, `source_asset`, `import_job`, `normalized_signal_event_revision` |
| **Trade Log (05)** | `application/{commands,jobs}/trade_log`, 7-stage durable ingestion on `data` queue | `POST drafts`, `POST source-assets`, `POST imports`, `POST revisions`, `PATCH mainboard-items` (pin), `DELETE work-objects`, `get_import_report` | `trade_log_root/revision`, `source_asset`, `import_job/report`, `canonical_trade_record_batch` |

- **Frontend routes:** `/mainboard` (default), strategy editor panel, outsource type chooser submenu, trading-signal & trade-log detail panels (Mainboard row expansions, not routes).
- **Acceptance:** item_kind strictly `{strategy, trading_signal, trade_log}` (kind mismatch → 422); pin by `root_id + revision_id` only (no name/latest/DOM); composition_hash changes on add/del/enable/pin → prior Ready report STALE; expand/collapse + label-only do NOT change hash; `available_time` required + UTC + no lookahead; immutable revisions, no auto-repin (except first Save&Add); strategy save ≠ Ready PASS ≠ Run; signal/trade_log never in PackageKind; single-tx mutation+fingerprint+audit+outbox.

---

## Stage 4 — Portfolio Allocation & Backtest Ready Check

**Goal:** Portfolio/Equity Allocation + Backtest Ready Check (run-admission preflight). (M11–M12; CR-06.)

| Page (doc) | Backend modules | Key endpoints | DB tables |
|------------|-----------------|---------------|-----------|
| **Portfolio/Equity Allocation (13)** | `domain/allocation` (share/reserve/currency rules, NUMERIC), `application/commands/allocation_plan` | `PUT .../portfolio-allocation-draft` (If-Match, idempotency_key), `POST .../sync` (merge preview), `POST .../validate`, `POST .../revisions`, add/remove entry patch | `mainboard_composition_draft`, `portfolio_allocation_plan`, `portfolio_allocation_plan_revision`, `portfolio_allocation_entry` |
| **Backtest Ready Check (14)** | `domain/readiness` (snapshot from persisted draft, fingerprint compare), `application/commands/readiness_check` | `POST /compositions/{id}/readiness-checks` → {report_id, state, issues[], snapshot_id, fingerprint} | `composition_snapshot`, `ready_check_report`, `readiness_issue` |

- **Frontend routes:** `/mainboard/portfolio-allocation`, Ready Check panel within Mainboard.
- **Acceptance:** allocation entries bind by `composition_item_id` (never name/DOM/Type text); independent mode (`enabled=false`) valid; total active share ≤100 (>100 BLOCKER, <100 WARNING, no auto-borrow); money/percent NUMERIC strings (no float); manifest uses only `portfolio_allocation_plan_revision_id` (CR-06, no `allocation_profile*`); readiness snapshot built transactionally from persisted draft (not DOM/file presence); reports/issues immutable (rerun = new id); entry Condition Package required only when Trigger Source demands it; `expected_fingerprint` mismatch → 409; soft-delete never erases historical snapshot/manifest/report.

---

## Stage 5 — RUN, Backtest Results, History, Arrange Metrics

**Goal:** RUN/Backtest Results, Results History, Arrange Metrics — execution plane + result read models. (M13; CR-03/04/05/07.)

| Page (doc) | Backend modules | Key endpoints | DB tables |
|------------|-----------------|---------------|-----------|
| **RUN & Results (15)** | `application/commands/backtest_run` (1-tx snapshot+manifest+run+outbox), `application/jobs/backtest_engine` on `backtest` queue, result materializer | `POST /compositions/{id}/backtest-runs` (202 → run_id, QUEUED, manifest_ref, event_stream_ref), `GET /backtest-runs/{id}` (+SSE), `GET /backtest-results/{id}`, `QueryResultArtifact` (cursor), `RequestResultExport`, `RetryBacktestRun`, `SoftDeleteBacktestResult` | `backtest_run`, `backtest_run_manifest`, `backtest_result`, `result_summary`, `metric_value`, equity/drawdown/`trade_ledger_row`/`signal_event`/`diagnostic_artifact`/`export_artifact`, `result_manifest_snapshot` |
| **Results History (16)** | `application/queries/results_history` (server read model), sort on canonical numeric metrics | `GET /backtest-results?sort=<enum>&cursor&limit`, `GET /backtest-results/{id}`, `POST .../compare`, `POST .../{id}/delete` (If-Match+idempotency) | result history projection (read model) |
| **Arrange Metrics (17)** | `domain/metric_profile` (presentation-only), `application/commands/metric_profile` | `GET /metric-definitions?availability=`, `GET` resolved profile, `POST /metric-profiles/{id}/revisions` (Apply/Lock/Unlock), `GET /backtest-results/{id}/metrics` | `metric_definition` registry, `result_view_metric_profile_root/revision` |

- **Frontend routes:** RUN control + Result panel in Mainboard, `/results/history`, `/results/arrange-metrics`.
- **Acceptance:** RUN re-runs full server preflight (422 READINESS_BLOCKED); `expected_fingerprint` mismatch → 409 COMPOSITION_STALE; succeeded-only materializes Result (CR-03); failed/cancelled → diagnostics only, no history row; retry = new run_id + manifest_hash + retry_of link; worker reads only manifest (missing pinned asset → FAILED, no "latest" fallback); never recompute metrics/charts in frontend (hydrate from result_id); History sort on canonical numeric values, nulls last; Compare exactly 2 distinct visible results; metric profile presentation-only (never mutates MetricValue/manifest); Result artifacts immutable checksummed Parquet, DB holds URI+checksum+schema_version+row_count.

---

## Stage 6 — Analysis Lab, Panel/Management/Logs, Trash

**Goal:** Analysis Lab (Agent observation/control), Admin Panel/Logs, Trash recovery surface. (M14 + M19/M3; CR-09.)

| Page (doc) | Backend modules | Key endpoints | DB tables |
|------------|-----------------|---------------|-----------|
| **Analysis Lab (18)** | `apps/agent_coordinator` runtime loop, `application/commands/agent_control`, Tool Gateway in `application/jobs/agent_tools` on `agent`/`agent-high` | `GET /agent-workspace/overview`, `/agent-tasks[?status]`, `/agent-tasks/{id}`, `/hypotheses`, `/agent-events/stream` (SSE), `POST /lab/messages`, `/agent-directives` (202), `/agent-runtime/pause|resume` (202, Admin), `/agent-runs/{id}/stop` (202, Admin) | `agent_runtime`, `agent_task`, `task_directive`, `agent_checkpoint`, `lab_message`, `hypothesis_artifact`, `artifact_link`, `agent_event` |
| **Panel/Management/Logs (19)** | `application/commands/role_assignment`, `application/queries/log_projection` (Admin-only) | `PATCH /v1/admin/users/{id}/role`, `GET /v1/admin/users`, `GET /v1/admin/logs` (filters, opaque cursor), `GET /v1/admin/logs/{event_id}`, role-matrix, system-actors | `users` (role mutation), `log_projection` (read model over `audit_events`), `role_policy_matrix` |
| **Trash (20)** | `application/commands/{restore,request_purge}`, `application/jobs/purge` on `maintenance`, Admin-only | `GET /v1/trash-entries`, `GET /trash-entries/{id}` (snapshot), `POST .../restore`, `POST .../purge` (confirmation phrase + reauth → 202) | reuses `trash_entries`, `tombstones`, `purge_job` |

- **Frontend routes:** `/lab` (Analysis Lab), `/panel`, `/panel/logs`, `/panel/trash` (all Admin/role-gated, server-enforced).
- **Acceptance:** Agent runs continuously backend-side independent of UI (CR-09); pause/stop checkpoint-safe (never kills worker); High directive never preempts running task; directives consumed only at safe checkpoints; `autonomous` priority rejected for humans (422); Panel/Logs/Trash run `require_admin` at endpoint+service (menu hide insufficient); events append-only (no PATCH/DELETE, corrections via causation_event_id); last-admin protection; role change atomic with `expected_head_revision_id`+If-Match; restore reuses entity_id+revision; purge two-phase confirm + async preflight; SSE = refresh signal only.

---

## Stage 7 — User Manual & Future Dev

**Goal:** User Manual (all-role read/search + Admin write) and Future Dev (capability registry, activation-gated). (M17–M18; CR-08/CR-09.)

| Page (doc) | Backend modules | Key endpoints | DB tables |
|------------|-----------------|---------------|-----------|
| **User Manual (21)** | `domain/manual` (stream position, canonical blocks), `application/commands/manual`, search on Postgres FTS | `GET /v1/manual/stream`, `GET /v1/manual/search?q=&cursor=`, `POST /v1/admin/manual/documents` (Admin), `:upload`, `DELETE .../{id}` (Admin), `:restore`, `POST .../{id}/revisions`; Agent tools `documentation.search/get_section`, `artifact.attach_citation` | `manual_document`, `manual_document_revision`, `manual_stream_entry`, `manual_content_block`, `manual_search_chunk`, `manual_publication_event` |
| **Future Dev (22)** | `domain/capability` (7 activation gates, state graph), `application/commands/capability_transition` (Admin) | `GET /api/v1/capabilities`, `GET /capabilities/{key}`, `POST /capabilities/{key}/lifecycle-transitions` (Admin), `GET /future-dev/graphic_view/overview`, `POST /view-datasets/query` (Limited/Active only), `POST /analysis-artifacts` | `future_capability`, `capability_activation_event`, `analysis_artifact`, `view_dataset`, `experiment_proposal`, `execution_plan` |

- **Frontend routes:** `/help/user-manual`, `/future-dev` (capability overview shell).
- **Acceptance:** manual stream ordered by atomic unique `stream_position` (not created_at); baseline immutable via UI (`BASELINE_MANUAL_IMMUTABLE`); write Admin-only; canonical blocks only (no raw HTML/MD innerHTML); search eventually consistent but publication atomic; capability transition requires Admin + legal state edge + non-empty reason + `expected_registry_version` + idempotency_key + all 7 gates; inactive op → `CAPABILITY_NOT_ACTIVE` (no job/output); Agent gets tool contracts only for Active/Limited (CR-08); **no fake endpoints/jobs/progress/chart data** in placeholders (CR-09); Live Trade is a separate execution plane, never a Backtest-RUN variant.

---

## Stage 8 — End-to-End Integration & Hardening

**Goal:** Wire the full pipeline, cross-domain integration tests, observability/audit completeness, deployment hardening.

| Aspect | Detail |
|--------|--------|
| **Backend** | full outbox→SSE fan-out across all domains; agent Tool Gateway parity tests vs human commands; cross-stage manifest reproducibility; retention/purge scheduler; rate limiting; CORS/security headers; per-process metrics (golden signals + queue depth + outbox lag + lease age) |
| **Integration flows** | (a) ingest Market+Research → approve → Create Package (Pre-Check→candidate→validate→approve/publish) → Strategy revision → attach to Mainboard → Allocation → Ready Check → RUN → succeeded Result → History → Arrange Metrics → soft-delete → Trash → restore. (b) Agent loop: directive → bundle resolve → backtest request → result linked → hypothesis — independent of UI. |
| **Acceptance** | end-to-end run is fully reproducible from pinned manifest; identical re-run reuses idempotent results; failed/cancelled never yields Result/History (CR-03); every mutation audited + outboxed; no "latest" leak; soft-delete never breaks historical pinned manifests; Agent never escalates beyond own outputs; last-admin/role-context-stale enforced; all stage acceptance suites + INF-01..INF-10 green; secrets absent from logs/audit/frontend build; deployment topology (api + 4 worker planes + agent-coordinator + scheduler + postgres/redis/minio) boots and passes health/ready |

---

## Stage → Page Index

| Stage | Pages (doc #) |
|-------|---------------|
| 0 | platform skeleton (foundational plumbing referenced by Mainboard doc 01) |
| 1 | identity/policy/audit/revision/concurrency/soft-delete/worker/artifact (M1–M3) |
| 2 | Market Data (11), Research Data (12), Create Package (06), Pre-Check (07), Package Library (08), ESP (09), Rationale Families (10) |
| 3 | Mainboard (01), Strategy Details (02), Add Outsource Signal (03), Trading Signal (04), Trade Log (05) |
| 4 | Portfolio/Equity Allocation (13), Backtest Ready Check (14) |
| 5 | RUN & Backtest Results (15), Results History (16), Arrange Metrics (17) |
| 6 | Analysis Lab (18), Panel/Management/Logs (19), Trash (20) |
| 7 | User Manual (21), Future Dev (22) |
| 8 | end-to-end integration & hardening |

> **Note on doc-stated stages:** Individual page docs sometimes infer different per-page stage numbers (their authors lacked the canonical `Coder_AI` stage map). This plan follows the canonical staged grouping in the prompt set / Master §17: data+package domain precedes Mainboard composition, which precedes allocation/ready-check, which precedes RUN/results, which precedes agent/admin/trash, which precedes manual/future-dev, which precedes end-to-end integration.
