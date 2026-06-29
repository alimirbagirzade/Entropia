# Entropia V18 — Canonical Domain Model

> **Authority:** `docs/spec/Entropia_V18_Master_Technical_Reference_v1_0.md` (M0–M19) + canonical decisions **CR-01..CR-09**. Overrides all page docs and the V18 prototype. Lifecycle state values are **lowercase snake_case** (CR-04) unless a state is an explicit UPPER_SNAKE deletion-overlay value.

---

## 1. Entity Spine: Root / Revision / Snapshot

Every durable business object follows the **Module-2 universal pattern**:

| Concept | Definition | Mutability |
|---------|-----------|-----------|
| **Root** | Stable identity (`entity_id`, ULID-like, never reused even post-purge). Holds name, owner, lifecycle pointer, `current_revision_id`, `row_version`. | Pointers mutate; identity never. |
| **Revision** | Immutable content snapshot. `revision_id`, `entity_id`, `revision_no`, `parent_revision_id`, `payload` (JSONB), `content_hash` (SHA-256 canonical), provenance, `validation_status`, `lifecycle_snapshot`. | **Never** `UPDATE`d. Each save `INSERT`s N+1 and advances head. |
| **Snapshot / Manifest** | Server-frozen, hash-pinned JSON artifact pinning exact revisions (composition snapshot, run/result manifest, context/data-bundle manifest). | Immutable after creation. |
| **Draft / Unsaved** | Client-side only OR a mutable editor draft row (`row_version`). Not a backend revision until saved. | Mutable. |
| **Artifact** | Result/memo/export/agent output. Carries provenance: source run/task/checkpoint + pinned input revisions. | Immutable. |

> **Pinning rule (P4):** all manifests/snapshots/bundles reference `root_id + revision_id + content_hash` — never "latest"/root-only. New revisions never auto-repin or mutate prior work.

---

## 2. Canonical Roots, Revisions & Snapshots (by domain)

### 2.1 Identity & access
| Entity | Kind | Key fields |
|--------|------|-----------|
| `principal` | base | principal_id, principal_type ∈ `anonymous\|human\|agent\|system` |
| `human_user` (Root, the only mutable user root) | root | user_id, username, current_role, `version`, role_changed_at/by |
| `agent` (system actor) | projection | actor_type=`system_agent`, actor_id — **not** in user registry, non-assignable |

### 2.2 Mainboard & composition
| Entity | Kind | Notes |
|--------|------|-------|
| `mainboard_workspace` | root | kinds: human_default / agent_research / system; one active default per human |
| `mainboard_working_item` | child | `item_kind ∈ {strategy, trading_signal, trade_log}` ONLY (CR-01). Links `work_object_root_id + pinned_revision_id`, `position_index`, `is_enabled`, `display_label_override`, `row_version` |
| `work_object_root` / `work_object_revision` | root/rev | head pointer + immutable content (`content_hash`, provenance) |
| `mainboard_composition_snapshot` | snapshot | `composition_hash`, item_manifest, capital_mode |
| `ready_check_report` / `readiness_issue` | snapshot/child | immutable; fingerprint-bound; issue severity `blocker\|warning` |

### 2.3 Strategy
| Entity | Kind | Notes |
|--------|------|-------|
| `strategy_root` | root | head pointer, lifecycle |
| `strategy_editor_draft` | draft | mutable, `row_version` |
| `strategy_revision` | rev | immutable `StrategyConfig` JSON, `config_hash`, `revision_number`, `strategy_revision_references[]`, ValidationSummary, `family_snapshot` (family_id+revision required for Backtest Ready) |

### 2.4 External work objects (Add Outsource Signal)
| Entity | Kind | Notes |
|--------|------|-------|
| `trading_signal_root` / `trading_signal_revision` | root/rev | `object_kind=trading_signal`; **NOT** a PackageRoot. Event set min: event_id, event_time, **available_time**, instrument_id, direction(long\|short), signal_type, source_record_id |
| `trade_log_root` / `trade_log_revision` | root/rev | `object_kind=trade_log`. Canonical columns: direction, entry_time, entry_price>0, exit_time≥entry_time, exit_price>0 (size/fees/pnl/symbol/OHLCV optional). V1 single-instrument |
| `source_asset` | immutable | raw TXT/CSV in object store, `raw_asset_hash` |
| `import_job` / `import_report` / `canonical_trade_record_batch` | job/report | durable async ingestion, mapping_hash, parsed/skipped counts |

### 2.5 Package system
| Entity | Kind | Notes |
|--------|------|-------|
| `package_root` | root | `package_kind ∈ {strategy, indicator, condition, embedded_system}` ONLY (CR-01). owner, visibility_scope, `current_revision_id`, `derived_from_revision_id` |
| `package_revision` | rev | immutable; input/output contract, dependency_snapshot, rationale_family_snapshot, validation_summary, `content_hash`, change_note, `supersedes_revision_id`. Independent facets: validation_state / approval_state / visibility_scope |
| `package_dependency` | edge | pins exact ESP/indicator `root_id + revision_id` |
| `package_request` / `dependency_scan` | work/evidence | Create Package + Pre-Check context; scan immutable (detected/resolved/missing/unsupported calls) |
| `embedded_resolver_registry` / `EmbeddedResolverContract` | registry | canonical_key → trusted active revision; signature/runtime/warm-up/timing/repaint |
| `artifact` / `async_job` / `validation_run` | support | object storage + jobs |

### 2.6 Data layer
| Entity | Kind | Notes |
|--------|------|-------|
| `market_dataset_root` / `market_dataset_revision` | root/rev | OHLCV/Tick/Spread. market_type, source_provider, timezone, record_time_basis, raw_asset_id, processed_asset_id, validation_report_id, content_manifest_hash, supersedes_revision_id |
| `market_raw_asset` / `market_processed_asset` | immutable | raw bytes + partitioned Parquet |
| `research_dataset_root` / `research_dataset_revision` | root/rev | native schema + `linked_market_dataset_revision_id`, `event_time_semantics`, `available_time_policy`, `usage_scope`, frequency_policy, source_timezone(IANA) |
| `research_field_definition` / `research_feature_definition` / `research_time_policy` | support | versioned; Feature-Input-Only needs feature_definition before strategy use |
| `MarketValidationRun` / `ValidationIssue` / `ApprovalDecision` / `dataset_coverage_slice` | support | severities PASS\|WARNING\|BLOCKING_FAIL |

### 2.7 Rationale classification (shared-edit exception)
| Entity | Kind | Notes |
|--------|------|-------|
| `rationale_family_root` | root | display_color (root-level presentation only), `row_version` |
| `rationale_family_revision` | rev | immutable: display_name, normalized_name, subfamilies_json, compatible_output_types_json, `content_hash` |
| `package_rationale_assignment` | edge | `target_kind = package_revision \| working_item_revision` (CR-01); carries `target_root_id + target_revision_id`. Trading Signal/Trade Log ARE assignable targets but NOT package types |
| `family_snapshot` | snapshot | historical pinned classification in package/strategy/backtest manifests; never recomputed |

### 2.8 Portfolio / Equity allocation
| Entity | Kind | Notes |
|--------|------|-------|
| `mainboard_composition_draft` | draft | mutable, `row_version` |
| `portfolio_allocation_plan` (Root) | root | controlled lifecycle |
| `portfolio_allocation_plan_revision` | rev | immutable: enabled, initial_capital, base_currency, compounding_mode, reserve_cash_percent, `config_hash` |
| `portfolio_allocation_entry` | child | `composition_item_id`, type(STRATEGY\|TRADING_SIGNAL\|TRADE_LOG), active, equity_share_percent, name snapshot |

### 2.9 Backtest run & result
| Entity | Kind | Notes |
|--------|------|-------|
| `backtest_run` (Root) | root | owns queue/execution/cancel/failure/retry/diagnostics lifecycle; `retry_of_run_id` |
| `backtest_run_manifest` | snapshot | immutable, `manifest_hash = SHA-256(canonical_json(...))`; carries CR-05/06/07 fields |
| `backtest_result` (Root) | root | **immutable, succeeded-run-only** (CR-03); `run_id` UNIQUE; identity = `result_id` |
| children | — | ResultSummary, MetricValue[], Equity/Drawdown points, TradeLedgerRow[], SignalEvent[], DiagnosticArtifact[], ExportArtifact[], ResultManifestSnapshot |
| `metric_definition` registry | registry | code, formula_version, unit, availability_status, null behavior — read-only to presentation |
| `result_view_metric_profile` (Root + Revision) | root/rev | presentation-only display subset (CR-07); never alters engine metrics |

### 2.10 Agent workspace
| Entity | Kind | Notes |
|--------|------|-------|
| `agent_runtime` | mutable pointers | agent_id, mode, status, active_task_id, last_checkpoint_id, policy_revision |
| `agent_task` | task | status, stage, progress, context_manifest_id, parent_task_id |
| `task_directive` | immutable | text immutable; status transitions append-only |
| `agent_checkpoint` | immutable | state_ref, manifest, directive_cursor, artifact_ids |
| `lab_message` | append | never hard-deleted |
| `hypothesis_artifact` | artifact | status, evidence_refs, source_task/checkpoint |
| `artifact_link` / `agent_event` | provenance/append | event log |

### 2.11 Admin, logs, manual, future-dev
| Entity | Kind | Notes |
|--------|------|-------|
| `audit_event` | append-only | immutable; corrections via `causation_event_id` |
| `log_projection` / `role_policy_matrix` | read model | cursor-ordered over events |
| `manual_document` / `manual_document_revision` | root/rev | publication_state Draft\|Published\|Superseded\|Removed; `is_baseline` immutable |
| `manual_stream_entry` / `manual_content_block` / `manual_search_chunk` | stream/blocks | unique `stream_position`; canonical block types |
| `future_capability` (registry root) | registry | capability_key (unique route map), lifecycle_state, dependency_snapshot |
| `capability_activation_event` | immutable | from_state/to_state, actor, reason, dependency hash |
| `analysis_artifact` / `view_dataset` / `experiment_proposal` / `execution_plan` | future-only | no instances while Placeholder |

### 2.12 Deletion / recovery
| Entity | Kind | Notes |
|--------|------|-------|
| `trash_entry` | record | immutable deletion + dependency snapshot |
| `tombstone` | record | post-purge marker; id never reused |
| `purge_job` | job | Admin async, retention/dependency preflight |

---

## 3. Central Lifecycle Enum Registry (CR-04, lowercase snake_case)

> Domain `lifecycle_state` is **separate** from `validation_status` and from `deletion_state`. The three never collapse into a single column.

### 3.1 Deletion overlay (orthogonal, all entities)
```
active → soft_deleted → purge_pending → purged
forbidden: active → purged ; purge_pending → restore ; purged → active
```

### 3.2 Per-entity lifecycle

| Entity group | lifecycle states (snake_case) |
|--------------|-------------------------------|
| **strategy** | draft → validated → active_candidate \| locked_for_test → deprecated → soft_deleted |
| **package (root)** | active ↔ deprecated ; → soft_deleted ; soft_deleted → active (Admin restore) |
| **package (revision)** | draft_revision → validating → published_current (immutable) \| rejected \| superseded |
| **package facets** | validation_state: pending\|passed\|warning\|failed\|stale · approval_state: draft\|approval_requested\|approved\|rejected (CR-02: also draft\|candidate) · visibility_scope: private\|explicitly_shared\|published\|system · visibility_state: private_draft\|shared_published\|deprecated |
| **create-package flow** | requested → precheck_{passed\|blocked\|not_applicable\|stale} → candidate_generating → candidate_ready\|failed → draft_created → validation_running → experimental\|eligible_for_approval\|revision_required → approved\|rejected\|superseded |
| **pre-check (dependency scan)** | not_checked → checking → passed\|blocked\|not_applicable\|failed ; passed → stale (on context/registry change) |
| **embedded resolver trust** | candidate → trusted_active → deprecated → unavailable |
| **market dataset revision** | draft → uploading → analyzing → needs_review\|verified\|rejected ; verified → approved ; approved → deprecated |
| **research dataset revision** | draft → analyzing → needs_review\|verified → approved → deprecated\|approval_revoked ; → soft_deleted |
| **rationale family** | active ↔ deleted (restore → active); born active, no draft/approval flow |
| **portfolio allocation plan** | draft → (validate) validation_report → (create_revision) immutable revision ; root active ↔ soft_deleted |
| **readiness report** | not_checked → checking → not_ready\|ready_with_warnings\|ready ; ready → stale ; → superseded ; access_denied |
| **backtest run** | requested → preflight_running → {rejected\|queued} → provisioning → running → [cancellation_requested] → finalizing → {succeeded\|failed\|cancelled} |
| **backtest result** | materializing → complete\|integrity_failed (no failed/cancelled) ; lifecycle active ↔ soft_deleted ; purge → tombstone |
| **export job** | queued\|running\|complete\|failed\|cancelled |
| **generic job** | queued\|claimed\|running\|cancellation_requested\|cancelled\|failed_retryable\|failed_final\|succeeded ; superseded |
| **agent task** | queued\|running\|waiting\|checkpointing\|paused\|succeeded\|failed\|cancelled |
| **task directive** | created → queued → consumed\|deferred\|completed\|cancelled |
| **hypothesis** | exploring\|testing\|candidate\|rejected\|archived |
| **manual revision** | draft\|published\|superseded\|removed |
| **future capability** | placeholder → designed → internal → shadow → limited → active → retired |
| **validation result** | pass\|warning\|blocking_fail |

> Transitions are typed commands (`approve`, `deprecate`, `soft_delete`, `restore`, …), never free `PATCH` of a state field. Each runs permission + domain validation and emits an audit event. Workers cannot freely update lifecycle state.

---

## 4. Role Model

| Role | View / Use | Edit / Delete | Special |
|------|-----------|---------------|---------|
| **Admin** | all | all (override; cannot skip lifecycle/dependency blockers) | sole Trash view/restore/permanent_delete; assign human roles; approve/publish (datasets, packages, ESP registry); capability transitions; system_config |
| **Supervisor** | all shared/published/system + own | own only; may **derive** others'; clone others | queue Agent directives (Normal\|High); Agent Workspace view; **no** Trash, role mgmt, approve, pause/resume/stop |
| **User** | own + explicitly_shared + published/system | own only | no Trash/Panel/Agent Workspace; create validation/approval **requests** only |
| **Agent** (non-login system actor) | system working content + shared/published/system | own outputs only | via Tool Gateway; capability parity; **never** approve/publish/dataset-approve/Trash/role/live-trade; non-assignable |
| **Guest / anonymous** | none (authenticated surfaces) | none | `UNAUTHENTICATED`/`ACCESS_DENIED`; leaks nothing |

- Title-based, fixed roles — **no per-action grants**. Client-supplied `role/owner/isAdmin` is never authoritative; menu hide/disable is UX only.
- **Last-admin protection:** cannot demote/deactivate the last active Admin → `LAST_ADMIN_PROTECTED`/`LAST_ADMIN_PROTECTION`. Role change re-evaluates active sessions; old-role requests → `ROLE_CONTEXT_STALE`.
- Agent role assignment attempt → `422 AGENT_ROLE_NOT_ASSIGNABLE`.

---

## 5. Ownership & Shared-Visibility Rules

- Separate fields, never conflated: `created_by_principal ≠ owner_principal ≠ updated_by_principal ≠ initiated_by ≠ approver ≠ publisher ≠ source`.
- Sharing / publish / admin-edit **never** change `owner`. Ownership transfer only via audited `transfer_ownership` (no general UI in V1).
- Visibility: `private`, `explicitly_shared`, `published`, `system`, `special_shared`.
- `use` grants reference rights only; new output's owner is the caller. Non-owners must **Derive** (new root, `derived_from_revision_id` provenance) — silent edit of another's payload is forbidden (`403 PACKAGE_EDIT_FORBIDDEN`).
- List endpoints exclude unauthorized rows server-side; detail re-runs `can_view`.

---

## 6. Global Shared-Editing Exception

**Rationale Families + Package Rationale Assignment** is a deliberate, resource-type-scoped exception:

- All four roles (Admin/Supervisor/User/Agent) may create/edit/rename/soft-delete any family and edit any assignment, regardless of `created_by` (provenance only). Policy via `can_manage_rationale_families(actor)` / `can_edit_rationale_assignments(actor)` — **not** generic owner policy.
- Classification is **semantic only**: never changes package type, entry/exit/risk/execution/backtest math, or the target object's kind.
- The exception does **not** widen edit rights elsewhere and does **not** extend to Trash restore/purge (still Admin-only).
- Assignment batch save is **atomic all-or-nothing** with `expected_table_version` + per-row `expected_head_revision_id`; one stale/deleted row rejects the whole batch (`PACKAGE_RATIONALE_ASSIGNMENT_CONFLICT`). Each changed assignment produces a new package revision; re-submitting identical = idempotent no-op.
- Color is root-level presentation only (not name-hash derived; no risk/perf/owner meaning).

---

## 7. Soft-Delete / Trash / Restore (Admin-only)

- **Normal delete = soft delete only.** One transaction atomically: set root `deletion_state=soft_deleted` (+ `deleted_at/by/reason`), create immutable `trash_entry` (deletion + dependency snapshot, redacted/size-bounded, no secrets/raw artifacts), write audit, enqueue outbox — all-or-rollback.
- Two separate fields: domain `lifecycle_state` (untouched by delete) vs `deletion_state`.
- **Restore** (Admin): same `entity_id` + same `current_revision_id`, **no new revision**, restores pre-delete owner, no history rewrite; fails atomically (stays soft_deleted) if dependency missing or asset retention purged.
- **Purge** (Admin, async job, irreversible): retention/dependency preflight (ALLOW / ALLOW_WITH_WARNING / REQUIRE_REASSIGNMENT / BLOCK / NO_OP). Historical pinned references do **not** block (history preserved); blockers = running/queued run or task, dangling active assignment. Leaves tombstone (id never reused) + audit. No automatic purge in V1.
- Blocks: deleting an object with a `queued/running` run → `OBJECT_IN_ACTIVE_RUN` / `DELETE_BLOCKED_BY_RUNNING_JOB`; Rationale Family with live assignments → `RATIONALE_FAMILY_IN_USE` (repair first).

---

## 8. Audit Event Model

- Append-only, never updated/deleted, **survives delete & purge**.
- Fields: `event_id, occurred_at(UTC), event_kind, severity, actor_principal_id, actor_kind(human|agent|system_service), target_entity_id/type/revision, previous_state/new_state, correlation_id, causation_event_id, reason, source_task/run_id, payload_hash_before/after`. Never stores secrets/PII/large payloads.
- Outbox is transactional: `entity.soft_deleted/restored`, domain events emitted in the same commit; consumer failure retries without rolling back the root.
- The Logs page is a cursor-paginated projection (`(occurred_at DESC, event_id DESC)`); corrections add new events, never edit.

---

## 9. Hard Canonical Invariants (CR-01..CR-09)

| ID | Invariant |
|----|-----------|
| **CR-01** | `PackageKind ∈ {strategy, indicator, condition, embedded_system}` only; `MainboardWorkingItem.item_kind ∈ {strategy, trading_signal, trade_log}` only. **Trading Signal & Trade Log are external MainboardWorkingItems, NOT Packages** — created under Add Outsource Signal; never in `GET /packages` or PackageKind. They ARE rationale-assignable (`target_kind=working_item_revision`) without becoming packages. |
| **CR-02** | Package shared/published transition is **Admin-only** via single-transaction `approve_and_publish`. Non-Admins create validation/approval requests only (`package_publish_admin_only`). Canonical ESP registry mutation is Admin-only. Agent `created_by` is provenance only. |
| **CR-03** | **Only a `succeeded` BacktestRun yields an immutable BacktestResult.** Failed/cancelled runs produce diagnostics/evidence only — no Result, no History row. `BacktestRun ≠ BacktestResult`; Result has no failed/cancelled state. |
| **CR-04** | Lifecycle enum registry is canonical and lowercase snake_case; API/SSE return domain values verbatim. Agent task / BacktestRun / GenericJob enums are distinct, never aliased. Workers cannot freely set state. |
| **CR-05** | Run manifest carries a versioned `engine_contract_version`; engine evaluation order is fixed by the Engine Contract. |
| **CR-06** | Manifest uses ONLY `portfolio_allocation_plan_revision_id` (null in independent mode, mode written explicitly); `allocation_profile*` fields are forbidden. |
| **CR-07** | Allocation Plan ≠ Metric Profile ≠ Output Artifact Profile. Manifest carries separate `run_profile_id`, `output_artifact_profile_id`, `metric_definition_set_version`, `result_view_metric_profile_id`. **Result View Metric Profile is presentation-only** — never reduces the engine metric set or mutates stored values. |
| **CR-08** | Future Dev capability state transitions are **Admin-only**; Agent receives tool contracts only for Active/Limited capabilities (else `capability_not_active`). |
| **CR-09** | **Agent runs continuously backend-side, independent of UI** (browser close/logout never stops it). **Future Dev is activation-gated and produces no production capability in V1** — no fake endpoints/jobs/state/progress; menu visibility ≠ active capability. Live Trade is a separate execution plane (execution_plan/session/broker adapter/order ledger/risk gate), never a Backtest-RUN variant. |

---

## 10. Cross-Cutting Invariants (supporting)

- **No "latest" resolution** in any manifest/bundle/run; exact revision IDs + content_hash pinned at submit time only.
- **No in-place revision mutation**; immutable revisions have no update endpoint (clone-to-draft only).
- **No last-write-wins**: optimistic concurrency (`expected_head_revision_id` / `expected_row_version` / `expected_fingerprint` / `expected_table_version`, mirrored by `If-Match`/`ETag`) on every mutation.
- **available_time ≠ event_time** (anti-lookahead): research/signal decisions gated on `available_at <= decision_time`; no forward-fill unless field policy allows.
- **Market Data is price/execution ground**; do not force funding/OI/research features into it. Research Data keeps native schema; missing time rules ⇒ cannot be Approved/used.
- **Disabled = semantic** (`enabled=false`): excluded from engine/manifest, never leaked.
- **No dependency cycles** (package self-dependency forbidden); detected server-side before use/publish.
- **No fabricated metrics**: Indicator/Condition/ESP perf metrics are `null`/NOT_APPLICABLE; missing result metrics render "Not available", never 0/∞.
