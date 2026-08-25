# Entropia — Stage 2 Handoff

> Living handoff for the staged build. Update the **Status** + **Next** sections as sub-stages land.

## Status — Stage 2 COMPLETE (as of Stage 2f merge)

`main` contains: **Stage 0 + 1 + 2 (a–f)**, all merged via green CI (backend lint/type/**integration on real Postgres**/alembic, frontend, docker). **Stage 2 (Data & Package Domain) done; Stage 3 (Mainboard & External Work Objects, docs 01–05) done — 3a/3b/3c merged, 3d Trade Log PR #12 open (CI pending). Next is Stage 4 (Portfolio Allocation + Backtest Ready Check).**

| Sub-stage | Page(s) | State | PR |
|-----------|---------|-------|----|
| 2a | Market Data (11) | ✅ merged | #1 |
| 2b | Research Data (12) | ✅ merged | #2 → #1 → main |
| 2c | ESP / Embedded System Packages (09) | ✅ merged | #3 |
| 2d | Rationale Families (10) | ✅ merged | #4 |
| 2e | Create Package + Pre-Check (06, 07) | ✅ merged | #5 |
| 2f | Package Library (08) | ✅ merged | #6 |

Alembic head: `0007_create_package_precheck` (unchanged — 2f is read-only, no new migration). Chain: …→0005_esp_packages→0006_rationale_families→0007_create_package_precheck.

## How each sub-stage is built (the working loop)

1. Branch off `main`: `feat/stage-2<x>-<slug>`.
2. Run a **Workflow** (author core → author app+tests → review) with the binding decisions + lessons below baked into the prompt.
3. Verify locally: `cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest --no-cov` (unit+contract pass; integration auto-skips without local Postgres).
4. **FK insert-order proof** for any new `create_*` (async probe with `uv run --with aiosqlite python`, JSONB→TEXT `@compiles` shim) — confirm `entity_registry` inserts before child rows.
5. Apply review CRITICAL/HIGH/cheap-MEDIUM fixes; commit.
6. PR → `main`; watch CI (`gh run watch <id> --exit-status`); merge with `gh pr merge <n> --merge --delete-branch` when green.

## Binding architecture (authoritative: docs/ARCHITECTURE.md §131-133, DOMAIN_MODEL.md §1)

- `entity_registry` is the **universal Root** (one row per durable object, discriminated by `entity_type`). Per-domain **dedicated `*_revision` + detail/support tables** FK to `entity_registry.entity_id`. No EAV/generic-JSON for core domain; dependency/reference edges get normalized tables.
- Stage-1 soft-delete/restore/purge operate generically on `entity_registry` — keep them working.
- One generic `approval_decision` table (target_kind discriminator) for all approvals.
- Lifecycle/validation/approval/visibility are **separate facets** (CR-04), lowercase snake_case enums in `domain/<x>/enums.py` (+ shared in `domain/lifecycle/enums.py`).

## Hard-learned lessons (apply proactively — these caused real failures)

- **L1 FK insert order:** SQLAlchemy UOW does NOT order parent-before-child from a bare `ForeignKey` (no `relationship()` on `entity_registry`). Every `create_*` that makes a root + child in one flush must be **async**: add root → `await session.flush()` → add children. (Fixed in `create_market_dataset`, `create_research_dataset`, `create_package`.)
- **L2 Idempotency ordering:** put optimistic-concurrency (`check_row_version`/`check_head`) **and** state-machine legality checks **inside** the `run_idempotent` operation body — else a completed-key replay raises a spurious 409 instead of returning the cached result. Authorization + pure input validation stay outside.
- **L3 Role/page gating:** enforce server-side at route **and** service layer, per each page's doc. Read the doc's role matrix — e.g. Research Data page is Admin/Supervisor/Agent only (router gate); ESP list/detail are any-authenticated but activate/deprecate are Admin-only; the resolve endpoint requires `require_authenticated`. Contract tests must pick an actor that passes the page gate but fails the specific check, so the asserted error code is the intended one.
- **L4** No fabricated metrics (null/`not_applicable`, never 0). **L5** Pin exact `revision_id`+`content_hash` (never "latest"). **L6** Register every model in `models/__init__.py __all__`.
- **L7 Optimistic-token + check-before-mutate:** an `expected_*_version` token is **inert unless** every state-advancing op bumps the root `row_version` (and `SELECT … FOR UPDATE`-locks the root). Within the `run_idempotent` body, run legality/concurrency checks **before** any row mutation — 2e `approve_and_publish` first mutated then checked (and whitelisted states with no legal `→approved` edge); both fixed pre-merge.
- CI runs only on PRs whose **base is `main`** (push to non-main branches does not run CI). So land each stage via a PR → main.

## Reusable foundation (don't re-create)

`application/idempotency.py` (`run_idempotent` — now **per-principal scoped**: never replays another actor's cached result), `infrastructure/queues/enqueue.py` (`enqueue_job`/`send_job`, durable job row = source of truth, CR-09), `shared/manifest.py` (`manifest_hash`), `infrastructure/s3/datasets.py`, `repositories/approvals.py` (`add_approval_decision`), the shared **Package** model from 2c (`models/packages.py`, `repositories/packages.py` — `create_package` is async/FK-safe) which **2e reuses**, and the ESP resolver registry (`resolve_embedded_dependency`) which **2e Pre-Check consumes**.

## Known LOW follow-ups (tracked, not blocking)

- List endpoints (market/research/esp) compute `has_more`/cursor over the **post-visibility-filter** set → under-filled pages; push the visibility predicate into SQL.
- `queries/esp.py::_visibility_of` has an unused `root` param + misleading docstring.
- ESP soft-delete / `DELETE_POLICY_BLOCKED` deprecate-first guard deferred to a later stage.
- Research: derive-from-base market-link carry-forward; approve/revoke root `row_version` bump; idempotency keys on draft-edit endpoints.
- Consider aligning ESP audit `event_kind` to doc 09's `resolver.registry.activated`.
- Rationale family **name uniqueness is app-enforced only** (`find_active_or_reserved_by_name` + check inside `_op`); add a root-level denormalized active-name column + partial unique index for a DB-level backstop against concurrent same-name creation. Same gap as the no-cascade `package_rationale_assignment` table-version token (coarse; the per-row `expected_head_revision_id` is the real guard).
- 2e **candidate-generation compute + dependency-scan parsing are V1 stubs** (the durable rows, both state machines, resolver wiring, idempotency, concurrency, and audit/outbox are real); wire real generation + a real source-call scanner in a later stage. `dependency_scan` is already append-only with `attempt_no` to absorb re-scans.
- 2f **mutating catalog actions deferred** (read-only slice shipped): `Use in…`/`Create-Strategy-Draft` (needs Strategy drafts — Stage 3), `Derive`, `Export` (job/artifact pipeline), and `Deprecate`/`Approve & Publish` from the Library page — each its own future slice.
- 2f **`explicitly_shared` is readable by any authenticated actor** (mirrors `identity/policy.py::can_view`; no share-grant table yet). When a per-principal share list lands, tighten both `can_view` and `queries/library.py::_visibility_conditions` together.
- 2f deferred refinements: **market/timeframe-scope facets** (need a defined facet vocabulary + indexed columns) and **user-driven sort** (V1 is fixed newest-first by `entity_id`; performance sorts need linked runs from Stage 5); the catalog **list** row surfaces the *pinned* family name while **detail** resolves the live name (fold live name into list rows when an indexed family projection exists).

## Stage 2d — Rationale Families (doc 10) ✅ landed (#4)

Shared-edit exception (DOMAIN_MODEL §6): all four roles create/edit/rename/soft-delete any family + edit any assignment via `can_manage_rationale_families` / `can_edit_rationale_assignments` (NOT owner policy). `rationale_family_root` (detail + `display_color`) + immutable `rationale_family_revision` + `package_rationale_assignment` edge (`target_kind = package_revision | working_item_revision`), all entity_registry-anchored; `create_family` is async/FK-safe. Atomic all-or-nothing batch with `expected_table_version` + per-row `expected_head_revision_id` → `PACKAGE_RATIONALE_ASSIGNMENT_CONFLICT`; each changed assignment makes a new package revision (carrying contracts forward; package owner unchanged); identical resubmit = idempotent no-op; output mismatch = non-blocking `OUTPUT_TYPE_NOT_LISTED` warning. Assignment table renders the family's **current** name live (rename without re-pinning). 6 ACTIVE seed families behind `SEED_RATIONALE` (incl. `Embedded System / TA Resolver`). Migration `0006_rationale_families`. **Consumed by:** 2e Strategy required-family picker (ACTIVE roots only) + 2f Package Library family filter (`rationale_family_id` join).

## Stage 2e — Create Package + Pre-Check (docs 06, 07) ✅ landed (#5)

Reuses the shared **Package** model (2c `create_package`, async/FK-safe) + the ESP resolver registry (`resolve_embedded_dependency`). Two new entity_registry-anchored tables: `package_request` (mutable detail, optimistic `row_version`) + immutable append-only `dependency_scan` (`attempt_no`, `source_hash`/`context_hash` staleness anchors, JSONB detected/resolved/missing/unsupported calls). Command chain (all idempotent; concurrency + legality checks inside the body, **before** mutation — L2/L7): `create_package_request` → `run_precheck` (resolves each declared canonical TA call against the **live** 2c ESP registry, pins exact `revision_id`+`content_hash` — L5; blocked path on missing/untrusted) → `submit_candidate_generation` (Send gate re-checks precheck freshness + registry-race staleness) → `create_draft_from_candidate` (reuses 2c `create_package`) → `approve_and_publish` (**Admin-only**, CR-02, atomic head repoint). Non-Admins create requests only. Create-Package + Pre-Check state machines per DOMAIN_MODEL §3.2. Candidate-generation compute + scan parsing are honest **V1 stubs**; all durable rows, resolver wiring, per-principal idempotency, concurrency control, and audit/outbox are real. Migration `0007_create_package_precheck`. **Adversarial review fixed 3 issues pre-merge:** (1) `approve_and_publish` legality check hoisted before any mutation + approvable-state set reconciled to legal edges; (2) `package_request.row_version` now bumped on every state advance (+ root row lock) so `expected_request_version` is a live token; (3) per-principal idempotency isolation in shared `run_idempotent`. **Consumed by:** 2f Package Library (lists published packages; `dependency_scan` = "how this package was built" provenance).

## Stage 2f — Package Library (doc 08) ✅ landed (#6)

The catalog/discovery surface over the existing package schema — **read-only: no new migration, model, or command.** Reuses the shared **Package** model (2c), the 2d rationale snapshot, and 2e `package_request`/`dependency_scan` provenance. `domain/package/catalog.py` (filter parse/validate — CR-01 type guard, facet enums, lifecycle set, query cap) + `permissions.py` (the 10-flag projection, CR-02 Admin-only publish). `application/queries/library.py`: role-aware `list_packages` + `get_package_detail`; **visibility pushed into SQL** (ARCHITECTURE §9.5) — admin=all, else `published`/`system`/`explicitly_shared` OR owner — so `has_more`/cursor count the authorized set (fixed the market/research/esp under-fill pattern). Cursor newest-first by `entity_id`; facet filters (type/lifecycle/validation/approval/visibility/rationale-family+`unassigned`) + name ILIKE search. Detail = full contracts + dependency snapshot + **live** family name + 2e provenance + revision history; re-runs `can_view` (soft-deleted→404, foreign-private→403). Guests rejected (doc 08 §2); non-Strategy perf metrics N/A, never 0 (L4). `routes/library.py` thin GET handlers (list + detail+ETag), wired in `main.py`; `+CatalogFilterInvalid` (422). **Adversarial 4-dimension review: zero production defects;** the 5 confirmed MEDIUM test-coverage findings were fixed pre-merge, plus one production hardening (explicit `CATALOG_LIFECYCLE_STATES` in the list SQL).


## Next: Stage 3 — Mainboard & External Work Objects (docs 01–05)

Per `docs/STAGE_BUILD_PLAN.md` §"Stage 3" (M9–M10 + external-object subsystem, CR-01). Composition plane: **Mainboard (01)**, **Strategy Details (02)**, **Add Outsource Signal (03)**, **Trading Signal (04)**, **Trade Log (05)**. New entities: `mainboard_workspace`, `mainboard_working_item`, `work_object_root/revision`, `mainboard_composition_snapshot`, `strategy_root/editor_draft/revision/revision_references`, `trading_signal_root/revision`, `trade_log_root/revision`, `source_asset`, `import_job/report`, `normalized_signal_event_revision`, `canonical_trade_record_batch`.

**Binding rules to honor (Stage 3 acceptance):** `item_kind` strictly `{strategy, trading_signal, trade_log}` — kind mismatch → 422 (CR-01); Trading Signal / Trade Log are external `MainboardWorkingItem`s, **never** a `PackageKind` (the 2f catalog already excludes them). Pin by `root_id + revision_id` only (no name/latest/DOM). `composition_hash` changes on add/del/enable/pin → prior Ready report STALE; expand/collapse + label-only edits do **not** change the hash. `available_time` required, UTC, no lookahead. Immutable revisions, no auto-repin (except first Save&Add). Strategy save ≠ Ready PASS ≠ Run. Single-tx mutation+fingerprint+audit+outbox.

**Strong reuse from Stage 2:** the entity_registry Root + immutable revision chain, `run_idempotent` (per-principal), `enqueue_job`/durable jobs (CR-09 — Trading Signal/Trade Log import jobs on the `data` queue), `add_approval_decision`, audit/outbox, `shared/manifest.py`, and — crucially — **2f's `library_query` / catalog** (Strategy Details' "Use a Package" and "Create Strategy Draft from Package" consume the catalog read surface + pin exact package revisions). The 2f deferred `Use in…`/`Create-Strategy-Draft` actions become live once Strategy drafts exist here.

## Stage 3a — Mainboard (doc 01) ✅ in PR #7 (green CI, awaiting merge)

The composition plane only (Ready Check report = Stage 4, RUN/result = Stage 5, Strategy typed-config compiler = 3b, Signal/TradeLog import jobs = 3d/3e are OUT). Migration **`0008_mainboard_composition`** (chain →0007; new alembic head once merged). New tables: `mainboard_workspace` (entity_registry-anchored; kinds human_default/agent_research/system; `composition_hash`+`row_version`), `work_object_root`/`work_object_revision` (immutable, `content_hash`, `available_time`), `mainboard_working_item` (child: kind, pinned root+revision, position_index, is_enabled, display_label_override, row_version), `mainboard_composition_snapshot` (immutable; `readiness_report_id` null — Stage 4 fills). `MainboardItemKind` reused across 3 tables via `native_enum=False` (matches 0007). Endpoints (`/api/v1`): `GET /mainboards/default` (auto-create), `POST /strategy-drafts` + `/external-work-object-drafts/{kind}` (transient, no DB), `POST /work-objects` (+`/revisions`), `POST /mainboards/{id}/items`, `PATCH /mainboard-items/{id}`, `POST /mainboards/{id}/snapshots`, `DELETE /work-objects/{root_id}`.

**Decisions (binding):** `item_kind` server-derived from root `object_kind`, divergent client value → 422 (CR-01); pin exact `root_id`+`revision_id` (L5); no auto-repin on revision append (AT#5). `composition_hash` = `manifest_hash` over the sorted **ENABLED** `{kind,root,revision}` set → changes on add/del/enable/pin (prior report STALE), **unchanged** on reorder/label/expand-collapse (documented gap-resolution, doc 01 §5.2+§9.3). Single-tx mutation+fingerprint+audit+outbox; per-principal idempotency; FOR-UPDATE locks + `expected_row_version`/`expected_head_revision_id` inside the op (L2/L7); FK-safe async create (L1).

**Security design call (override of an auto-generated test + a reviewer's literal suggestion):** work objects have **no visibility/sharing facet and no publish path** in 3a (`create_work_object` always sets `lifecycle_state="active"`; that is a deletion/lifecycle facet, NOT publication — CR-04). So **all foreign work-object attach is denied** (owner/Admin only); deriving `published` from `lifecycle_state=="active"` (the market/research `_visibility_of` pattern) would make every work object foreign-attachable and re-open the CRITICAL leak. Cross-owner reuse is the **Package catalog** path (Add Package → derived Strategy Draft, 2f), not raw work-object attach.

**Adversarial 4-dim review → all fixed pre/at-merge:** CRITICAL foreign-private attach leak (hardcoded `explicitly_shared` → owner/Admin-only); HIGH soft-delete now idempotent no-op on already-deleted root, workspace `composition_hash` recompute now locks workspace + bumps `row_version` (live ETag, no lost update), pin_revision active-root check under the root lock (TOCTOU); MEDIUM idempotency fingerprints include `expected_head`/`source_provenance`. **CI Postgres caught one bug local SQLite masked:** 64-char `composition_hash` written into `audit_events.new_state` VARCHAR(48) → moved to JSONB metadata/outbox payload (`new_state=None`/`snapshot_id`). persistence/FK/migration dim: 0 findings.

**Tests:** 23 unit + 6 contract + 11 persistence + 6 authz integration; FK insert-order proof PASS; validated on local Postgres (17 mainboard integration green) + CI green.

**Known 3a follow-ups (tracked):** "one active default per human owner" app-enforced (no DB constraint — add denormalized owner col + partial unique idx later); `_assert_not_in_active_run` is a no-op stub (Stage 5 wires `OBJECT_IN_ACTIVE_RUN`); 3 LOW review notes (refresh-on-possibly-dirty, pre-lock item resolve, `or ""` owner fallback) deferred; work-object cross-owner sharing (visibility column + `_visibility_of`) deferred to whenever sharing lands; AT#9/11/12/14–18/20/22/24/25/28–30 depend on later stages.

## Stage 3b — Strategy Details (doc 02) ✅ landed (PR #9)

The Strategy typed-config plane. Migration **`0009_strategy_details`** (chain →0008; new alembic head). Four entity_registry-anchored tables: `strategy_root` (head pointer + lifecycle/display facets), immutable `strategy_revision` (typed StrategyConfig JSONB + `config_hash` + `(entity_id, revision_number)` unique), immutable `strategy_revision_references` (pinned dependency edges), mutable `strategy_editor_draft` (`row_version`). `domain/strategy/` = `enums.py` + `config.py` (Pydantic `StrategyConfig`, sections 1–9) + `compiler.py` (`validate_strategy_config` structural+semantic, `filter_disabled_sections`, `compute_config_hash`). Endpoints (`/api/v1`): `POST /strategy-drafts` (real persistence — supersedes 3a's transient opener), `PATCH /strategy-drafts/{id}`, `POST /strategy-drafts/{id}/validate|save|clear`, `GET /strategy-drafts/{id}`, `GET /strategies/{root}(+/revisions)`, `GET /strategy-revisions/{id}`.

**Binding integration decision (Strategy = work object):** a Strategy shares its registry Root with a work object (`entity_type='work_object'`, `work_object_root.object_kind='strategy'`) so 3a's `attach_mainboard_item` / `patch_mainboard_item.pin_revision` bind it **unchanged** (REUSE, no 3a edit). Save is ONE tx: validate (compiler) → append immutable `strategy_revision` (typed, `config_hash`) + pinned references (exact root+revision+content_hash, L5) → append a **mirror `work_object_revision`** (the "work-object-equivalent revision") → **auto-repin** every attached Mainboard item to it via 3a `pin_revision` (composition_hash changes → prior Ready report **STALE**, AT-20) → draft saved → audit `strategy.revision_created` + outbox. **Save ≠ Ready PASS ≠ Run.** Sizing exclusivity → `SIZING_METHOD_NOT_EXCLUSIVE` (AT-12); condition-bearing trigger source with no active Condition → `TRIGGER_SOURCE_CONDITION_REQUIRED` (AT-05); stale `expected_draft_row_version` → `STRATEGY_DRAFT_CONFLICT` (AT-19, no last-write-wins); per-principal `run_idempotent`; FOR-UPDATE lock + concurrency/legality checks INSIDE the op before mutation (L2/L7); FK-safe async create with a **second flush before the draft** (L1 — the FK proof caught a real draft→strategy_root ordering bug).

**Remediation of the workflow-authored draft (hardened before validation):** the first pass wrote glue against an imagined API with real defects, all fixed: (1) CRITICAL `referenced_revision_id` FK'd a **non-existent `revisions` table** → dropped (cross-domain polymorphic; pinned by content_hash, no FK); (2) CRITICAL `String(26)` IDs → `String(40)` (matches `entity_registry`/`principals`/every `*_revision`); (3) commands/queries/routes rewritten from class-handlers/placeholder-DI to module-level functions on the real `run_idempotent`/`audit_repo`/`request_context`/policy signatures; (4) **compiler↔config bug**: disabled `scaling_logic`/`protection_stop_logic` filtered to `None` but the fields were required → made Optional (any disabled-scaling Save would have 422'd); (5) missing migration 0009 authored; models registered in `models/__init__` (L6); router wired in `main.py`.

**Tests:** 53 unit (StrategyConfig validation) + 7 contract (guest 401 / blank-name 422 / compiler determinism + sizing + trigger + disabled-scaling) + 10 integration (create→save→revision+config_hash+refs+mirror+lifecycle; attach→save→composition_hash change=Ready STALE; sizing/trigger 422; concurrency conflict; foreign-owner 403; clear; audit+outbox; idempotent replay). **Validated on real Postgres** (full suite green, alembic 0009 up/down/up reversible) + ruff + mypy clean + L1 FK insert-order proof PASS.

**Known 3b follow-ups (tracked):** `_assert_references_active` is V1-lenient (unresolved reference roots allowed, pinned by content_hash; tighten when real package/dataset resolvers are wired at manifest time, Stage 5); no per-owner `display_name` uniqueness index yet (app-level only); `strategy_draft.set_reference`/`add_node` agent-tool granularity deferred (full-payload/patch covers the Save path); market/data instrument + coverage + condition-compatibility semantic checks (AT-04/06/09/10) are Stage-5-manifest-time concerns; 3a's now-unrouted `mb_cmd.start_strategy_draft` transient opener was **deleted in I-12** (superseded by the persisted 3b draft; it had no caller, no route and no test).

## Stage 3c — Trading Signal (doc 04) + Add Outsource Signal Trading-Signal path (doc 03) ✅ landed

**Trade Log (doc 05) is deferred to Stage 3d** (the Add Outsource Signal `trade_log` save path + `canonical_trade_record_batch` + the 7-stage ingestion are out of this slice; the 3a `start_external_work_object_draft(kind=trade_log)` opener already exists and is untouched).

Migration **`0010_trading_signal`** (chain →0009; new alembic head, up/down/up reversible). **Trading Signal = NATIVE work object** (`object_kind=trading_signal`): its root/revision REUSE 3a `work_object_root`/`work_object_revision` — **no separate `trading_signal_root/revision` tables and no mirror revision** (unlike 3b Strategy; doc 04 §9.1 maps the revision to `WorkObjectRevision`). Only **2 new standalone tables** (NOT entity_registry-anchored — they predate the root, created on the transient draft): `source_asset` (immutable raw TXT/CSV upload, object-storage key + `raw_asset_hash`) + `normalized_signal_event_revision` (durable import output: accepted time-safe events + skipped-row report + evidence + `content_hash`, pinned to the Trading Signal revision at Save via a plain `work_object_revision_id`). The durable **import job REUSES the generic `jobs` table** (`data` queue, CR-09, `enqueue_job`/`send_job`) — no new job/report table.

`domain/trading_signal/` = `enums.py` + `config.py` (typed §9.2 `TradingSignalConfig`) + `compiler.py` (structural + cross-field validation: event-model / OHLCV / price-source conflicts, `config_hash`) + `events.py` (**pure, infra-free** CSV/TXT parser + time-safe normalizer: canonical `event_id`, direction/signal-type alias maps, per-event `available_time` required + `>= event_time`, future-event + instrument-mismatch + duplicate skips, legacy entry/exit-ledger → whole-file blocker). Commands (`application/commands/trading_signal.py`, direct-authored — **no workflow**): `upload_source_asset` (content-addressed, dedup) → `request_trading_signal_import` (enqueue) → `create_trading_signal_and_attach` (validate + require succeeded/non-empty/time-safe import → `mb_repo.create_work_object` + link normalized → **Save & Add REUSES 3a `attach_mainboard_item` nested `key=None`**) → `create_trading_signal_revision` (append rev N+1, **NO auto-repin** — doc 04 rule 9). Import worker body `application/jobs/trading_signal.py::run_import` + actor `run_trading_signal_import`. **Pin (`Use This Revision`) + soft-delete REUSE 3a** `patch_mainboard_item(pin_revision)` / `soft_delete_work_object` directly (no new command). Endpoints (`/api/v1`): `POST /trading-signals/source-assets`, `POST /trading-signals/imports` (202), `GET /trading-signals/imports/{job_id}`, `POST /trading-signals` (Save & Add), `POST /trading-signals/{root}/revisions`, `GET /trading-signals/{root}`.

**Binding decisions honored:** Trading Signal never a `PackageKind` (CR-01; 2f catalog excludes it); pin by exact `root_id`+`revision_id` (L5); per-event `available_time` required + UTC + no-lookahead; immutable revisions, no auto-repin except first Save&Add; save ≠ Ready PASS ≠ Run (`ready_state="STALE"` on attach); single-tx mutation+audit+outbox; per-principal `run_idempotent` (nested `key=None` is a pass-through — safe); FOR-UPDATE lock + `expected_head_revision_id` INSIDE the op (L2/L7); FK-safe create with **`create_source_asset` flushing before returning (L1 — the FK proof caught the exact bare-ForeignKey ordering hazard, hardened)**.

**S3 decision:** source bytes go to object storage (`put_source_asset_bytes`/`get_raw_bytes`, prefix `signals/source`); the full upload→import→save pipeline is tested on Postgres alone by monkeypatching those two helpers to an in-memory dict (the pure parser is separately unit-tested).

**Tests (37 new):** 13 unit (parser/normalizer) + 8 unit (config/compiler) + 5 contract (guest 401 / provider 422 / event-model 422, DB-free) + 11 integration (full pipeline→work object+item+composition_hash+audit+outbox+normalized-pin; available-time & legacy-schema blockers; no auto-repin; explicit pin changes hash; stale-head conflict; idempotent replay; foreign-owner 403; soft-delete drops projection; content dedup). Validated on real Postgres (full suite **451 passed, 0 skipped**), alembic 0010 up/down/up reversible, ruff+format+mypy clean, **L1 FK insert-order proof PASS**.

**Known 3c follow-ups (tracked):** `upload_source_asset` content-dedup runs outside `run_idempotent` (a concurrent duplicate upload could create two content-addressed assets — harmless, same object key); V1 import is canonical-column identity mapping (no per-source column mapping profile / connector path yet — file-source only); Instrument Registry mapping is string-equality against the root scope (no real registry resolver — Stage 5 manifest-time); export (`RequestTradingSignalExport`) + Ready-Check/Run boundary are later stages; the future-`available_time` case is stored as-is (conservative, not lookahead), unlike 3a's object-level future check.

## Stage 3d — Trade Log (doc 05) + Add Outsource Signal Trade-Log path ✅ landed (PR #12, merged → main `7a3dab3`)

Completes **Stage 3 (docs 01–05)**. Migration **`0011_trade_log`** (chain →0010; up/down/up reversible). **Trade Log = NATIVE work object** (`object_kind=trade_log`, never a `PackageKind` — CR-01/TL-01): historical entry/exit LEDGER, **not** a live signal (contrast 3c's event/available-time model). Root/revision REUSE 3a `work_object_root`/`work_object_revision` (no mirror, like 3c). Only **1 new table** `canonical_trade_record_batch` (immutable parsed records + skipped-row report + evidence + `content_hash`, pinned to the Trade Log revision at Save via plain `work_object_revision_id`). The raw upload **REUSES the shared `source_asset` table** (0010) — its repo helpers moved to a neutral `repositories/source_asset.py` and are **re-exported from `trading_signal.py`** (DRY, zero 3c behavior change). Durable import REUSES the generic `jobs` table (`data` queue, CR-09).

`domain/trade_log/` = `enums.py` + `config.py` (typed §10.2 `TradeLogConfig`) + `compiler.py` (cross-field: `PRICE_CONTEXT_CONFLICT` TL-10, event-model) + `records.py` (**pure** ledger parser: required-column & timezone whole-file blockers TL-05/07, per-row skip evidence for exit<entry / non-positive price / out-of-scope symbol TL-07/08/09, **non-destructive pnl-mismatch warning** TL-08, deterministic record ids + content hash; **header keys lowercased** so capitalized broker/MT4/MT5 exports parse — code-review HIGH fix). Commands (`application/commands/trade_log.py`, direct-authored): `upload_source_asset` → `request_trade_log_import` → `create_trade_log_and_attach` (**REUSES 3a `attach_mainboard_item`**, `available_time=None` — historical §10.4) → `create_trade_log_revision` (rev N+1, **NO auto-repin**, Rule 10). Worker `jobs/trade_log.py::run_import` + actor `run_trade_log_import`. **Pin + soft-delete REUSE 3a** (no duplicate endpoints). Endpoints: `POST /trade-logs/source-assets`, `POST /trade-logs/imports` (202), `GET /trade-logs/imports/{job_id}`, `POST /trade-logs`, `POST /trade-logs/{root}/revisions`, `GET /trade-logs/{root}`.

**Tests (35 new):** unit (config/compiler + ledger parser incl. capitalized-header regression), contract (guest 401 / provider 422 / price-context 422, DB-free), integration (full upload→import→save→attach pipeline, required-column blocker, no-auto-repin, explicit-pin hash, stale-head 409, idempotent replay, foreign-owner 403, soft-delete, batch evidence). Full suite green; ruff+format+mypy clean; **L1 FK insert-order proof PASS**; alembic 0011 up/down/up reversible + idempotent on Postgres; CHECK-constraint parity with 3c.

**Known 3d follow-ups (tracked, mostly Stage 4 Ready-Check):** TL-09 (mixed-symbol Ready block), TL-11 (allocation-off capital>0), OHLCV-fallback → approved Market Data revision ref requirement are **Ready-Check concerns** (Save≠Ready) — the Trade Log revision already carries `price_policy.approved_market_data_revision_ref` (null) + `capital.independent_initial_capital` (nullable) so Stage 4 wires the blockers. **3c `events.py` still has the same case-sensitive header pattern** (lower exposure — hand-authored `source_record_id` headers); apply the same lowercase fix if broker-style signal files appear. Pure "Save Draft (no file)" path deferred (3c parity — both slices do Validate&Save + Save revision only).

## Stage 4a — Portfolio/Equity Allocation (doc 13) ✅ landed (PR #13)

Migration **`0012_portfolio_allocation`** (chain →0011; up/down/up reversible + idempotent). **No new draft table** — the existing `mainboard_workspace` IS the composition draft. 3 new tables: `portfolio_allocation_plan` (1:1 with a composition via UNIQUE workspace; mutable draft state + `row_version` + plain `current_revision_id`), `portfolio_allocation_entry` (bound by `composition_item_id` = `mainboard_working_item.item_id`, **NO FK** so it survives an item soft-delete and is flagged `ITEM_UNAVAILABLE` at validate; `item_type` server-derived), `portfolio_allocation_plan_revision` (immutable `config` JSONB + `config_hash` + `derived_amounts`). Money/percent are `Numeric` (float rejected at parse). `domain/allocation/` = `enums.py` (UPPERCASE currency/compounding wire tokens per §8.2) + `config.py` (`PortfolioAllocationConfigV1`, Decimal) + `rules.py` (`validate_allocation` → issues+`DerivedAmounts`, capital formulas R0/A0/sleeves/unallocated, `compute_config_hash`). Commands (`application/commands/allocation_plan.py`, direct-authored, one-tx + `run_idempotent`): `upsert_allocation_draft` (autosave PUT, `expected_row_version`→409, first PUT accepts None/0), `validate_allocation_draft` (immutable report, rerun=new id), `create_allocation_revision` (blocker-free ENABLED draft only). Queries: `get_allocation_draft` (+candidate picker), `sync_preview` (non-destructive). Endpoints (`/api/v1`): `GET/PUT /mainboard-compositions/{id}/portfolio-allocation-draft`, `POST .../portfolio-allocation/validate`, `POST .../portfolio-allocation/sync`, `POST .../portfolio-allocation/revisions`. Every mutation writes audit + outbox. **Tests (22 new):** 14 unit (rules/formulas incl. §14#10: 10k/10%/40-35-15 → R0=1000, A0=9000, sleeves 3600/3150/1350, unallocated 900) + 8 integration on Postgres (full flow, stale-token 409, unknown-item `DEPENDENCY_BLOCKED`, >100 blocks revision, soft-deleted item `ITEM_UNAVAILABLE`, independent-mode no-revision, foreign-owner 403, idempotent replay). ruff+format+mypy clean; **L1 FK proof PASS**; alembic 0012 up/down/up reversible on Postgres. Code review: 2 of 3 HIGH findings empirically refuted (Pydantic `model_dump(mode="json")` renders Decimal as str; strategy already includes `expected_*_row_version` in the idempotency payload), 1 fixed (`enabled_changed` now audit+outbox).

## Stage 4b — Backtest Ready Check (doc 14) ✅ landed (PR #14, merged → main `226c7d1`)

See **`docs/STAGE4_KICKOFF.md`** for the full handoff + paste-ready resume prompt. Ready Check fills the `readiness_report_id` slot 3a left null on the immutable `mainboard_composition_snapshot`, and pins the allocation via `capital_mode_snapshot` from the 4a `portfolio_allocation_plan_revision` (`mb_repo.create_snapshot(capital_mode_snapshot=)` already exists). `POST /compositions/{id}/readiness-checks` → `{report_id, state, issues[], snapshot_id, fingerprint}`; reports immutable (rerun = new id); snapshot built transactionally from a persisted draft; `expected_fingerprint` mismatch → 409. New tables `ready_check_report` + `readiness_issue`; new `domain/readiness/` + commands/queries/routes + migration `0013_*`. Wire the tracked 3d follow-ups here (TL-09 mixed-symbol block, TL-11 allocation-off capital>0, OHLCV-fallback → approved Market Data ref). REUSE 3a snapshot/work_object/item + 4a allocation plan_revision/`validate_allocation` + `run_idempotent`/audit/outbox/optimistic concurrency (`expected_fingerprint`→409). Follow the working loop; L1 FK proof for every new `create_*`; direct-author (no workflow); cost-conscious.

**Landed:** migration **`0013_ready_check`** (chain →0012; up/down/up reversible) — 2 new tables `ready_check_report` (immutable root: `composition_snapshot_id`, `composition_fingerprint` stale-key, `state`, blocker/warning/pass counts) + `readiness_issue` (immutable child CASCADE). The `mainboard_composition_snapshot` readiness columns already existed (0008) — **no ALTER**, filled at check time. `domain/readiness/` = `enums.py` + `issues.py` (value objects) + `validators.py` (pure `evaluate_readiness`: composition→lifecycle→strategy→external→allocation, state derivation, `is_stale`). Command `application/commands/readiness_check.py::run_readiness_check` (one-tx + `run_idempotent`): builds the transactional snapshot from the PERSISTED draft, resolves each pinned `work_object_revision.payload` via the native config models (`StrategyConfig`/`TradeLogConfig`/`TradingSignalConfig`), resolves external import evidence (`canonical_trade_record_batch`/`normalized_signal_event_revision` by `work_object_revision_id`), reuses 4a `validate_allocation` (mapped 1:1) + 3a `composition_hash`, persists the immutable report+issues, fills `snapshot.readiness_report_id`, audit+outbox. Query `queries/readiness_check.py` recomputes STALE/SUPERSEDED at read time (never stored). Endpoints (`/api/v1`): `POST /mainboard-compositions/{id}/readiness-checks` (rerun=new id), `GET /mainboard-compositions/{id}/readiness`, `GET /readiness-reports/{id}`. `expected_fingerprint` mismatch → **409 `COMPOSITION_STALE`**. **3d follow-ups WIRED:** TL-09 mixed-symbol block, TL-11 allocation-off independent capital, OHLCV-fallback → approved Market Data ref. **Tests (30 new):** 22 unit (RC-01/02/03/04/05/06/07/08/16 + TL-09/11 + OHLCV + allocation map + stale) + 8 integration on Postgres (RC-01/02/09/17/18 + STALE recompute + L1 FK proof). ruff+format+mypy clean; alembic 0013 up/down/up reversible. **Code review: 1 of 2 HIGH empirically refuted** (query/command fingerprint 'divergence' false — `list_active_items` already joins `EntityRegistry`), 1 fixed (exit-logic now requires ≥1 ENABLED exit indicator block, not `signal_block AND indicators`).

## Stage 5a — RUN + Backtest Results core (doc 15) ✅ landed (PR #16)

See **`docs/STAGE5B_KICKOFF.md`** for the next-slice handoff + paste-ready resume prompt. The execution plane: RUN admission (`POST /mainboard-compositions/{id}/backtest-runs`, 202) RE-RUNS the mandatory server preflight from the persisted composition (client `ready` never trusted — reuses 4b `run_readiness_check` nested); `expected_fingerprint` mismatch → **409 COMPOSITION_STALE**, any blocker → **422 READINESS_BLOCKED** (no run/manifest/job). One tx builds an immutable hash-pinned `backtest_run_manifest` (`execution_key` reproducible / `manifest_hash` run-unique, **no 'latest'**) + QUEUED `backtest_run` + durable `backtest` job (CR-09). Worker (`jobs/backtest_engine`) re-resolves every pinned revision (unresolved → **FAILED**, no fallback) then runs a **deterministic V1 engine stub**; **only** a succeeded run materializes an immutable Result + summary + 9 canonical metrics (never-0, L4) + equity/trade/signal/diagnostic artifacts + `result_manifest_snapshot` (CR-03). Failed/cancelled → diagnostics only, no Result/history. Retry = new run_id + manifest_hash + `retry_of_run_id`; result soft-delete under owner/Admin + `expected_row_version`. Wired 3a `_assert_not_in_active_run` → **OBJECT_IN_ACTIVE_RUN**.

Migration **`0014_backtest_run_result`** (chain →0013; up/down/up reversible; 10 tables: `backtest_run`/`backtest_run_manifest`/`backtest_result`/`result_summary`/`metric_value`/`result_equity_point`/`trade_ledger_row`/`signal_event`/`diagnostic_artifact`/`result_manifest_snapshot`). `domain/backtest/{enums,manifest,engine,metrics}` + `models/backtest` + `repositories/backtest` (L1 FK-safe `create_result`) + `commands/backtest_run` + `jobs/backtest_engine` + `queries/backtest_run` + `routes/backtest`. **Tests:** 8 unit (manifest/engine/metrics determinism, L4) + 10 integration on Postgres (admission→worker→result L1 FK proof; 409 stale; 422 blocked leaves nothing; idempotent dup; retry new run+link+hash; manifest-resolution FAILED→no result; soft-delete; foreign 403; guest 401; OBJECT_IN_ACTIVE_RUN; **worker redelivery idempotency**). ruff+format+mypy clean; migration↔model column parity verified. **Adversarial review: 0 CRITICAL; both HIGH empirically refuted** (result_id in `new_state` fits VARCHAR(48) + matches readiness `snapshot_created` precedent; "stuck in RUNNING" false — pin resolution runs while PROVISIONING + whole-tx rollback), 1 genuine fix (dramatiq at-least-once redelivery → duplicate result, terminal-state guard + regression test).

**Deferred to Stage 5b** (tracked): `RequestResultExport`/`ExportArtifact` + heavy artifact cursor-pagination query endpoints; Result Trash restore/purge (Stage 6, doc 20). Engine is an honest **V1 stub** (deterministic from `execution_key`; only `engine.py`/`metrics.py` change when the real engine lands).

## Stage 5b-1 — Results History (doc 16) ✅ landed (PR #18, merged → main `bd4aff4`)

See **`docs/STAGE5C_KICKOFF.md`** for the next-slice handoff + paste-ready resume prompt. The server-side history index over the immutable **succeeded** `backtest_result` rows — **pure read model: no migration (alembic head stays `0014`), no new `create_*` (delete REUSES 5a `soft_delete_backtest_result`), so no L1 FK / alembic proof needed.** `domain/backtest/history.py`: 6 canonical sorts (newest + highest total-return / net-profit / RoMaD / Sharpe, lowest max-drawdown) with V18 dropdown aliases, an **opaque keyset cursor pinned to the sort key** (encodes `{sort, value, result_id}`; tamper/mismatch → `CURSOR_INVALID`), and the compare context extractor/diff (a field the V1 manifest does not pin ⇒ **"Not available", never fabricated** — L4). `application/queries/results_history.py`: `list_backtest_results` — **SQL visibility** (owner OR Admin, pushed into the query), sort on the canonical numeric `metric_value.value` **NULLS LAST + `result_id` tie-break**, LEFT OUTER join so a **metric-less result stays in the null tail instead of vanishing**; `compare_backtest_results` — **exactly two distinct visible results**, read-only (no mutation). `apps/api/routes/results_history.py`: `GET /backtest-results` (sort+cursor+limit), `POST /backtest-results/compare`, `POST /backtest-results/{id}/delete` (**reuses the 5a soft-delete command** — If-Match + idempotency). `shared/errors.py`: `+INVALID_SORT_KEY`, `+CURSOR_INVALID`, `+COMPARE_REQUIRES_TWO_DISTINCT_RESULTS`. History rows are **succeeded-only**; failed/cancelled never appear (CR-03). **Tests (33 new):** 19 unit (sort normalization/alias, cursor round-trip + tamper-reject, compare context diff) + 14 integration on Postgres (newest / highest-return / lowest-drawdown / RoMaD-nulls-last sorts; cursor no-duplicate + null-tail continuation; equal-value tie-break stability; owner / Admin visibility; soft-deleted absent; compare context-diff + two-distinct guard; outer-join keeps a metric-less result indexed). ruff + ruff format + mypy src clean. **Adversarial review: 1 CRITICAL empirically not-triggerable but hardened** (INNER→LEFT-OUTER join so a result with no `metric_value` row can never drop out of the index), **2 HIGH empirically refuted** (ULID-like monotonic `result_id` ⇒ stable keyset pagination; an always-unavailable manifest field must not raise a permanent false compare warning) — each with a regression test.

**Deferred to Stage 5c** (tracked): **doc 17 Arrange Metrics** (presentation-only metric profile) and the **doc-15 deferred** items — `RequestResultExport`/`export_artifact` (provenance = source `manifest_hash`) + heavy artifact **cursor-pagination** query endpoints (ledger/equity/signal drill-down). Result **Trash** restore/purge → Stage 6 (doc 20).

## Stage 5c — Arrange Metrics (doc 17) + Result export/artifact plane (doc-15 deferred) ✅ landed (PR #20, merged → main `9e29c23`)

See **`docs/STAGE6_KICKOFF.md`** for the next-slice handoff + paste-ready resume prompt. **Arrange Metrics = PRESENTATION-ONLY (CR-07):** a Result View Metric Profile of immutable Apply/Lock/Unlock revisions that **never mutates** a Backtest Result / `metric_value` / manifest — it only reorders/filters which persisted metrics render. The **System Default** profile is resolved **in-memory** from the seeded `metric_definition` registry (9 selectable + 18 future, in display order); the **first Apply forks a personal profile** (`scope=user`, one per principal, `UNIQUE(scope, owner_principal_id)`). `domain/metric_profile/{enums,registry,profile}` (`normalize_selection` → empty/unknown/not-selectable guards + registry-order normalize; `compute_config_hash`; `transition_reason`). One command `create_metric_profile_revision` drives Apply/Lock/Unlock via `is_locked` + selection with `expected_profile_revision_id` OCC (409 `METRIC_PROFILE_STALE`), a lock precondition (a locked profile refuses everything but a **pure unlock**, 409 `METRIC_PROFILE_LOCKED`), and `run_idempotent`. Queries: `list_metric_definitions?availability=`, `get_resolved_metric_profile`, `get_result_metrics` (**hydrates** the immutable `metric_value` by the resolved profile; a missing metric is `not_computed`, **never 0** — L4). Routes: `GET /metric-definitions`, `GET /metric-profiles/resolved`, `POST /metric-profiles/{id}/revisions`, `GET /backtest-results/{id}/metrics`.

**doc-15 deferred:** `RequestResultExport` (**synchronous V1** — engine is a stub, artifacts small) materializes `export_artifact` metadata (`object_key` + content `checksum` + `schema_version` + `row_count`) with **provenance = source Result `manifest_hash`**; bytes are derived from the immutable source artifact (never rendered UI rows) so the checksum is reproducible. `QueryResultArtifact` (`GET /backtest-results/{id}/artifacts/{type}`) is cursor-paginated over equity/ledger/signal/diagnostics with an **opaque keyset cursor** (5b pattern reused; a Trade Ledger row is a trade **root** → no root/leg double count). `domain/backtest/{artifacts,export}`, `application/{commands/result_export,queries/result_artifacts}`, `infrastructure/postgres/{models,repositories}/export.py` + `repositories/result_artifacts.py`, `apps/api/routes/result_export.py`.

Migration **`0015_arrange_metrics_export`** (chain →0014; up/down/up reversible; 4 tables: `metric_definition` seeded 27 rows + `result_view_metric_profile_root`/`revision` + `export_artifact`). `enum_column` (VARCHAR+CHECK, no `CREATE TYPE`) throughout; migration↔model column parity verified. **Tests (33 new):** 16 unit (registry shape, selection validation/normalize, config-hash + lock transition, artifact cursor round-trip/tamper, export checksum provenance) + 17 integration on Postgres (System Default resolution; availability filter; first-Apply fork [L1 FK: root before revision]; minimum-one-selectable; future-metric block; lock → change-blocked → unlock; stale expected-revision; idempotent Apply; foreign-profile role guard; presentation-only null-never-0 + dropped-metric MetricValue survives; export provenance/idempotency/invalid-type; artifact cursor pagination no-duplicates; wrong-type cursor rejected; soft-deleted result hides artifacts; second-default-apply-when-personal-exists stale; existing-profile rejects None expected). ruff + ruff format + mypy src clean. **Adversarial review: 0 CRITICAL; 2 HIGH empirically triaged** — the first-Apply race is translated to a clean 409 (`UNIQUE(scope,owner)` already prevents duplication + regression test), the second HIGH refuted (a committed root always carries a head, so the OCC guard is not bypassable + regression test).

**Deferred to later (tracked):** Admin-writable **persisted** System/Workspace-Default profile (V1 default is read-only in-memory); **async ExportJob** for large exports (V1 is synchronous); real object-storage byte put/get (V1 stores only metadata + deterministic checksum); Result **Trash** restore/purge + profile-root soft-delete/restore → Stage 6 (doc 20).

## Stage 6a — Analysis Lab (doc 18) observation/control plane ✅ landed (PR #22, merged → main `c908cbc`)

Scope split (user-approved): **(A) observation + control surface + persistence** landed; **(B) continuous Coordinator runtime loop + Tool Gateway** → Stage 6a-2. Migration **`0016_analysis_lab`** (→0015; up/down/up reversible; **8 tables** — `agent_runtime`/`agent_task`/`task_directive`/`agent_checkpoint`/`lab_message`/`hypothesis_artifact`/`artifact_link`/`agent_event`; `enum_column` VARCHAR+CHECK; singleton `alpha-agent` runtime seeded; migration↔model column parity verified). `domain/agent_lab/{enums,state_machine,cursor}` — runtime/task/directive state machines; `parse_human_directive_priority` (422 on `autonomous`/unknown); opaque keyset cursor (5c pattern). Commands: **`agent_control`** (`create_directive` + Admin `pause_runtime`/`resume_runtime`/`stop_run`; `row_version` OCC → 409 `AGENT_RUNTIME_STATE_CONFLICT`; controls are safe-checkpoint *requests*, never a worker kill), **`lab_message`** (`record_discussion_message` + deterministic saved-context Lab Assistant response — never mutates the active task, CR-09 no fake progress), **`agent_coordinator`** (deterministic scaffold: `advance_to_safe_checkpoint` / `apply_pending_control` / `consume_next_directive`). Queries: **`agent_workspace`** (`get_overview`/`list_tasks`/`get_task`/`list_hypotheses`; keyset). Routes `apps/api/routes/agent_lab.py` — 10 endpoints incl `GET /agent-events/stream` (SSE, `require_role` **before** streaming). **Tests (18):** AL-02..AL-10, AL-17, AL-18, **L1 FK insert-order proof** (task→checkpoint→hypothesis→artifact_link), keyset pagination, soft-delete hiding, review regressions. ruff + ruff format + mypy src clean (251 files); alembic 0016 up/down/up + parity green; full suite green. **Adversarial review: 0 CRITICAL; 2 HIGH + 1 MEDIUM found and FIXED** — malformed `If-Match` → 422 (no silent OCC opt-out); a queued directive is **deferred, not burned**, while a pause/stop is pending (no `CONSUMED`-for-cancelled-task with no path back to `QUEUED`); `stop_run` locks the runtime **before** validating task state (TOCTOU narrowed).

**Deferred to Stage 6a-2 (tracked):** continuous `apps/agent_coordinator` runtime loop + **Tool Gateway** (`application/jobs/agent_tools` on `agent`/`agent-high` queue) + human↔agent tool parity (AL-01, AL-11..AL-16); the `stop_run` full task-row lock (once the loop runs concurrently). Also from 5c: Admin-writable **persisted** System/Workspace-Default profile; **async ExportJob** + real object storage. **Panel/Logs (19)** = Stage 6b; **Trash (20)** = Stage 6c (Result restore/purge + profile-root soft-delete/restore; reuse `domain/deletion` + `TrashEntry`/`Tombstone` + `repositories/trash` + `application/commands/deletion` + 5a `soft_delete_backtest_result`).

## Stage 6a-2 — Analysis Lab Coordinator runtime loop + Tool Gateway (doc 18 §9.2, §10) ✅ landed (PR #24, merged → main `23e13a5`)

Promoted the Stage-6a deterministic scaffold into the **real continuous Coordinator loop** and added the **UI-less agent Tool Gateway**. Migration **`0017_agent_tool_gateway`** (→0016; up/down/up reversible; **1 table** `agent_tool_call` — the durable tool-call envelope; `idempotency_key` UNIQUE `uq_agent_tool_call_idem`; `enum_column` VARCHAR+CHECK; migration↔model column parity verified).

- **Coordinator loop** — `application/commands/agent_loop.run_coordinator_cycle`: locks the runtime row for the cycle (`with_for_update`), applies pending pause/stop at a safe checkpoint, **skips consumption while PAUSED**, consumes the next directive at a safe checkpoint, and materializes **exactly one AUTONOMOUS follow-up task** per consumed directive (AL-01). `apps/agent_coordinator/__main__` promoted from the Stage-0 idle heartbeat to a real per-tick process (one tx/tick, own session, rollback+continue = crash recovery, AL-14).
- **Tool Gateway** — `application/jobs/agent_tools.dispatch_tool_call` records the mandated envelope (`actor_context`/`task_id`/`checkpoint_id`/`input_manifest_id`/`idempotency_key`/`policy_scope`/`artifact_output_ref`) + `tool_call_started`/`tool_call_succeeded`/`tool_call_failed` + tool-specific domain events. **At-least-once replay (AL-14):** `idempotency_key` UNIQUE; the tool-call row flushes BEFORE any handler side effect, so a losing concurrent tx blocks on the unique index and never runs its handler (same guarantee as `UNIQUE(backtest_result.run_id)`). Parity tools (`domain/agent_lab/tool_gateway.ToolName`): `agent.task.query`, `data_bundle.resolve`, `package.proposal.create` (candidate/draft only — `allow_status_override=False`, AL-12), `backtest.ready_check`+`backtest.request` (delegate to the same `readiness_check`/`backtest_run` commands a human uses; Ready Check never bypassed), `result.query`, `artifact.create`, `artifact.soft_delete` (own artifact only via `created_by_principal_id`, AL-16), `followup_task.enqueue` (AUTONOMOUS). **Governance:** `TOOL_ALLOWED_SCOPES`+`ensure_scope_allowed` (illegal scope → REJECTED); **AL-11 real** — `data_bundle.resolve` under EXECUTION reads each research revision's actual `usage_scope` from DB and calls `ensure_allows_evidence_bundle` → `agent_research_only` → recorded REJECTED + `research_input_blocked`, invalid bundle never pins a manifest. Denials are durable REJECTED outcomes, never a crash. New errors: `ToolPolicyScopeError`/`ResearchInputBlockedError`/`AgentToolCallForbiddenError`/`ArtifactOwnershipError` (403).
- **Durable job path** — `run_tool_job` + `enqueue_tool_call` routed by `queue_for_tool(tool, scope)` to the **`agent`/`agent-high`** queues (`run_agent_tool`/`run_agent_tool_high` worker actors).
- **Hardening** — `stop_run` now takes a full task-row lock (`session.refresh(task, with_for_update=True)`) now the loop is concurrent.
- **Tests (21):** AL-01 (loop + follow-up), AL-08 pause, AL-10 stop, AL-11 (research-only blocked from execution + allowed paths), AL-12, AL-14 (idempotent replay), AL-16 (own/foreign soft-delete), tool-call envelope, scope guard, durable job path + queue routing, **L1 FK insert-order proof** for `create_tool_call`. ruff + ruff format + mypy src clean; alembic 0017 up/down/up + parity green; full suite **658 passed**. **Adversarial review verdict was BLOCK (1 CRITICAL + 2 HIGH) — all three empirically FALSE POSITIVES** (UNIQUE constraint exists; `ToolPolicyScopeError` IS a `ForbiddenError`; `AppError` always sets `.message`); only cheap defensive/tidy fixes applied.

**Deferred to a later slice (tracked):** the agent "brain"/planner that decides *when* to call gateway tools (the gateway surface + queue routing are complete here); the heavy Create-Package proposal→approval pipeline wiring stays human/Admin-gated (Stage 8 e2e).

## Stage 6b — Panel / Management / Logs (doc 19) ✅ landed (PR #26, merged → main `77ea5b4`)

Admin-only management + operational-observation surface. **No migration / no new table** — Logs is an append-only read model over the existing immutable `audit_events` (alembic head stays **`0017`**).

- **Server-side policy (§2, §13)** — new `domain/identity/policy.require_admin_panel` → `AdminPanelAccessRequiredError` (403 `ADMIN_PANEL_ACCESS_REQUIRED`). **Every** endpoint AND its service re-check it (a hidden menu item is never authorization). Supervisor/User/Agent/anonymous all denied.
- **Role Assignment (§4.2, §9, §11)** — `application/commands/role_assignment.assign_user_role` (canonical Panel command, layered on the M1 policy helpers; the old M1 `roles.change_user_role`/`POST /users/{id}/role` stays for back-compat). `PATCH /v1/admin/users/{id}/role`: `require_admin_panel` → resolve human target (Agent id → `AgentRoleNotAssignableError` 422) → row-lock (`refresh(with_for_update=True)`) → **OCC** `expected_head_revision_id` (+ optional `If-Match` mirror, must agree) → mismatch = `UserRoleVersionConflictError` (409 `USER_ROLE_VERSION_CONFLICT`) → **no-op** (same role → `changed=false`, NO version bump, NO audit) → **last-admin protection** → mutate `role/version/role_changed_at/role_changed_by` → `user.role_assigned` audit + `role_assigned` outbox in ONE tx. Wrapped in `run_idempotent`. Owner/created_by/historical records untouched.
- **Last-admin TOCTOU fix (review finding)** — the count+check+demote critical section is serialized with a transaction-scoped advisory lock `identity_repo.lock_admin_count` (`pg_advisory_xact_lock`), gated on the demote-from-Admin path. Closes a concurrent-demotion race where two txs each locking a *different* Admin row could both read count=2 and reach **zero admins**.
- **Logs read model (§4.3, §5, §9.4)** — `application/queries/log_projection` (Admin-only, append-only). `GET /v1/admin/logs` — server-side filters (time range `from`/`to`, `family`, `severity`, `actor_type`/`actor_id`, `resource_type`, `correlation_id`, `q`), newest-first `(occurred_at desc, event_id desc)` with an **opaque composite keyset cursor** (`domain/admin_panel/log_taxonomy.encode/decode_log_cursor`, reuses `agent_lab/cursor`). `GET /v1/admin/logs/{event_id}` — read-only detail: correlation chain (same `correlation_id`, oldest-first, capped) + causation ref + deleted-subject status (best-effort via `EntityRegistry`) + safe technical identifiers only (no raw payload, no edit/delete/retry). Family filter **mirrors `event_family` exactly** (substring + first-match-wins) so filter agrees with each event's displayed family.
- **Management reads (§3.3, §4.1)** — `application/queries/user_registry`: `GET /v1/admin/users` (humans only, `deletion_state=active`, username-asc keyset via `agent_lab/cursor`), `/system-actors` (Agents, read-only, `assignable=false`), `/role-matrix` (canonical `domain/admin_panel/role_matrix.build_role_matrix`, read-only server truth, `policy_revision`).
- **New typed errors (`shared/errors`)** — `AdminPanelAccessRequiredError` (403), `UserRoleVersionConflictError` (409), `LogFilterInvalidError` (422).
- **Tests (43 new):** unit (taxonomy family classification, filter normalize, cursor roundtrip/foreign-ns/garbage, role matrix, `require_admin_panel`) + integration acceptance (§14): non-admin denial, role assign success (version++/role_changed_*/`role_assigned` audit+outbox), no-op, OCC conflict, last-admin protection **+ concurrent-demotion serialization** (2-session `asyncio.gather` → exactly one demote, never zero admins), agent-target rejection, identity fields preserved, idempotent replay, logs newest-first + cursor pagination + filters + empty + invalid cursor, log detail correlation/causation + deleted subject + unknown-event, user registry humans-only + keyset, system-actors, role-matrix admin-only, **family first-match-wins**. ruff + ruff format + mypy src clean; **full suite 701 passed**; no migration (parity N/A).
- **Adversarial review** — `ecc:code-reviewer`: 0 CRITICAL / 2 HIGH / 2 MEDIUM / 1 LOW. Empirically verified: **3 false positives** (event_id is ULID-sortable → keyset correct; `HumanUser.version` defaults to 1; `assert_role_assignable` dead-defensive since `Role` has no agent value). **2 real** fixed here (last-admin TOCTOU advisory lock; family-filter first-match consistency), each with a regression test.

**Deferred (tracked):** log-projection filter indexes on `audit_events` (correlation_id / actor / kind+severity) — deferred as premature optimization for V1 volumes (KISS/YAGNI); newest-first pagination already covered by `ix_audit_events_log_order`. The old M1 `change_user_role` retains the pre-6b (unlocked) last-admin count — Panel path is hardened; hardening M1 was left out of 6b scope.

## Stage 6c — Trash (doc 20) ✅ landed (PR #28, merged → main `b437254`) — Stage 6 COMPLETE

Admin-only Trash page contract built ON the Stage-1 deletion core. **Migration `0018_trash_page`** (→0017): no new table — `trash_entries` gains the page-contract columns (`display_name`, `original_location`, `deletion_snapshot` JSONB, `status` overlay enum soft_deleted/restored/purge_pending/purge_failed/purged, `row_version` OCC token, `purge_job_id`/`purge_error`/`purge_requested_by`, `correlation_id`, `restored_at/by`) + explicit **`(deleted_at DESC, id DESC)`** keyset index. Alembic head = **`0018_trash_page`**; up/down/up proven; model↔migration parity OK.

- **State machine (§9.2)** — added `PURGE_PENDING → SOFT_DELETED` (worker-failure return path) to `domain/deletion/state_machine`. Restore stays forbidden from purge_pending/purged.
- **`soft_delete_entity` rework (§9.3, §10, §14)** — row-lock (`refresh(with_for_update=True)`), **idempotent repeat** (already-soft-deleted → same entry, no duplicate entry/audit; purge_pending → 409 `PURGE_IN_PROGRESS`; purged → 409 `OBJECT_ALREADY_PURGED`), type-specific `_soft_delete_preflight` (work_object with active run → `OBJECT_IN_ACTIVE_RUN` [doc-20's `DELETE_BLOCKED_BY_RUNNING_JOB` mapped onto the landed doc-01/15 canonical code — one semantic, one code]; rationale_family with ASSIGNED rows → 409 `RATIONALE_FAMILY_IN_USE` via `rationale_repo.count_active_family_assignments`, **no Trash Entry for a blocked delete**), richer snapshot columns. Optional `display_name`/`original_location`/`deletion_snapshot` kwargs (backward-compatible).
- **Restore (§9.3)** — `restore_trash_entry(trash_entry_id, expected_head_revision_id, idempotency_key)`: `require_trash_admin` (service AND route) → entry row-lock → OCC vs `entry.row_version` (409 `STALE_REVISION`) → status gate → head-pointer integrity check (snapshot `current_revision_id` must equal root head, else 409 `RESTORE_CONFLICT`) → same entity_id/current_revision_id reactivation (no new revision) → entry `restored` + `trash.restored` audit + `entity.restored` outbox, one tx. `restore_entity(entity_id)` kept as Stage-1-compat wrapper.
- **Two-phase purge (§8.3, §9.3)** — `request_purge`: confirmation_phrase must equal display identity (422 `PURGE_CONFIRMATION_INVALID`), non-empty `reauth_proof` (401 `REAUTH_REQUIRED`; full MFA out of V1 scope), OCC + `run_idempotent` (same key → same job, no duplicate) → target `purge_pending` + durable `jobs` row on **`maintenance`** queue → 202 `{purge_job_id,...}`; duplicate without key → 409 `PURGE_IN_PROGRESS`. Worker `application/jobs/purge.run_purge` (+ `run_trash_purge` dramatiq actor): re-preflight at job start → success = root **PURGED (row retained as identity/audit evidence; revisions retained per V1 retention)** + `tombstones` row + entry `purged` + `trash.purge_completed`; not-eligible = root back to soft_deleted + entry `purge_failed` (+`purge_error`) + `trash.purge_failed`; redelivered terminal job = no-op.
- **List/detail projection (§4, §5, §13)** — `application/queries/trash`: `GET /v1/trash-entries` (Admin-only; `q` haystack + `object_type` filter pushed to SQL; unknown type → 422 `INVALID_TRASH_OBJECT_TYPE`; opaque composite keyset cursor `domain/trash/page.encode/decode_trash_cursor`; default statuses hide restored/purged; `restore_eligible` flag; `recoverable_total`), `GET /v1/trash-entries/{id}` (redacted snapshots + current target state + tombstone; no secrets/raw payloads). Routes: `POST /v1/trash-entries/{id}/restore`, `POST /v1/trash-entries/{id}/purge` (202 + dispatch), `DELETE /entities/{id}` unchanged. Old `GET /trash` + `/trash/{entity_id}/...` REPLACED (contract tests updated).
- **Policy (§2, §11)** — new `require_trash_admin` → 403 `TRASH_ACCESS_FORBIDDEN` (route AND service; User/Supervisor/Agent all denied, no data leak). Agent keeps ONLY own-artifact soft-delete (AL-16); no trash list/restore/purge tools.
- **Backtest Result integration (§3.3, §10)** — `soft_delete_backtest_result` now writes a Trash entry (`entity_type=backtest_result`); restore/purge type-dispatch mutates the Result row's LOCAL `deletion_state` (Result is not a registry root, CR-03); parent Run manifest untouched.
- **11 new typed errors** in `shared/errors` (TRASH_ACCESS_FORBIDDEN, TRASH_ENTRY_NOT_FOUND, ENTITY_NOT_SOFT_DELETED, PURGE_IN_PROGRESS, OBJECT_ALREADY_PURGED, RESTORE_CONFLICT, PURGE_NOT_ELIGIBLE, INVALID_TRASH_OBJECT_TYPE, PURGE_CONFIRMATION_INVALID, REAUTH_REQUIRED, RATIONALE_FAMILY_IN_USE).
- **Tests (+18 → 719 total, all green):** `tests/integration/test_trash_page.py` (17) — page-contract entry, idempotent repeat, non-admin/Agent denial, filters + search pushdown + invalid type, **keyset tie-break stability** (5 same-timestamp deletes, limit 2, no dup/gap), detail snapshot, restore identity/OCC/compat, purge validations, full two-phase purge incl. worker completion + tombstone + redelivery no-op, idempotency-key job replay, **worker-failure return path** (monkeypatched preflight), RATIONALE_FAMILY_IN_USE (both command paths, no entry written), Backtest Result roundtrip incl. purge. Contract test moved to `/trash-entries` + `TRASH_ACCESS_FORBIDDEN`.
- **Adversarial review** (`feature-dev:code-reviewer`): 2 HIGH, both verified REAL and fixed: (1) `soft_delete_family` missing row lock (TOCTOU duplicate-Trash-Entry window) → `refresh(with_for_update=True)`; (2) keyset index created ASC while spec/docstrings state DESC,DESC → explicit `sa.text("... DESC")` in model + 0018 (ASC was functionally masked by Postgres backward scan — aligned for spec fidelity). Everything else (purge dispatch ordering, idempotency fingerprints, OCC, state machine, authz, snapshot redaction) held.

**Deferred (tracked):** `soft_delete_family` idempotency_key (doc-10 route contract, row lock closes the race); retention-driven payload/object-storage cleanup in the purge worker (V1 retains root row + revisions as evidence; only projection exclusion + tombstone are live); Trash `resolution` conflict-choice enum (doc 20 §5 — no domain adapter returns alternatives yet, restore conflicts are terminal 409s in V1).

## Stage 7a — User Manual (doc 21) ✅ landed (PR #30, merged → main `be65d4e`)

The Help > User Manual backend: a server-authoritative **Continuous Manual Stream** replacing the V18 localStorage prototype. Migration **`0019_user_manual`** (→0018; up/down/up proven; migration↔model parity clean): **6 tables** — `manual_documents` (page-local root like `backtest_results`, NOT EntityRegistry; `is_baseline` + `deletion_state` overlay), `manual_document_revisions` (immutable; `publication_state` draft/published/superseded/removed; `content_checksum`; `UNIQUE(document_id, revision_no)`), `manual_stream_entries` (**unique never-reassigned `stream_position`**; `UNIQUE(document_id)`; state active/removed), `manual_content_blocks` (canonical safe-render blocks, `UNIQUE(revision_id, block_index)`), `manual_search_chunks` (FTS projection + **GIN `to_tsvector('simple', content_text)`**), `manual_publication_events` (append-only; **UNIQUE monotonic `resulting_stream_version`** doubles as the reader `stream_version` source). **Baseline guide seeded by the migration** from `domain/manual/baseline.build_baseline_seed()` (fixed ids `mdoc_baseline_entropia_guide`/`mrev_.._1`; canonical-corrected wording — Trading Signal/Trade Log are external Mainboard working items, never package types) — the SAME content source tests use.

- **domain/manual** — `enums` (`MANUAL_ENTITY_TYPE`, `ManualSourceType`, `PublicationState`, `StreamEntryState`, `BlockType`, `SOURCE_TYPE_BY_EXTENSION`, `source_label`), `blocks` (parsers: plain text / Markdown subset / **allowlisted HTML — any tag outside the allowlist raises `MANUAL_PARSE_FAILED` and rejects the WHOLE upload; raw markup never renders**; `normalized_checksum`; `build_search_chunks` title+heading+content chunker; stable heading anchors), `stream` (opaque stream/search cursors; search cursor carries an **exact-precision `(Decimal rank, chunk_id)`** keyset — rank rounded to `NUMERIC` scale in SQL so pagination never drifts), `baseline`.
- **Commands (`application/commands/manual`)** — `create_manual_document` / `upload_manual_document` (shared `_publish_new_document` pipeline: one atomic tx = root + Published revision + stream entry + search chunks + publication event + audit + outbox), `replace_manual_revision` (same `stream_position`, v1 → Superseded, OCC `expected_head_revision_id` → 409 `MANUAL_REVISION_CONFLICT`), `soft_delete_manual_document` (Trash entry `entity_type=manual_document`, entry keeps its position, idempotent repeat), `restore_manual_document` (thin wrapper → landed Trash core). Every stream mutation first takes the **advisory stream lock** (`manual_repo.lock_stream`, `pg_advisory_xact_lock(210_721)`) → concurrent Admin appends get deterministic unique positions (UM-13); `expected_stream_version` → 409 `MANUAL_STREAM_CONFLICT`; every mutation `run_idempotent`. Duplicate checksum in the active stream → 409 `MANUAL_DUPLICATE_CONTENT` unless explicit `allow_duplicate` override.
- **Queries (`application/queries/manual`)** — `get_manual_stream` (all-role incl. Agent principal; baseline first; keyset by position; single `stream_version` per page), `search_manual` (Published+active only via joins on `visible_revision_id` + document `deletion_state`; `ts_rank`/`ts_headline`; blank query searches nothing), `get_manual_section` (anchor slicing heading→next same-or-higher heading; stale anchor/revision → 404 `MANUAL_SECTION_NOT_FOUND`, UM-18).
- **Trash type dispatch** — `commands/deletion.py`: `MANUAL_ENTITY_TYPE` branches in `_restore_entry_core` (**`_restore_manual_target`**: same root/revision chain, stream entry back ACTIVE at its original position, head-pointer integrity vs snapshot, `manual_document_restored` event + version bump) and `_mark_target_purge_pending`; `jobs/purge.py`: preflight (**baseline never purge-eligible**), finalize (root PURGED row-retained + revisions/blocks retained for citations, **search chunks deleted** = projection redaction, tombstone), worker-failure return path. `domain/trash/page.TRASH_OBJECT_LOCATIONS += manual_document → "Help / User Manual"`.
- **Tool Gateway parity (doc 21 §12)** — `ToolName.DOCUMENTATION_SEARCH`/`DOCUMENTATION_GET_SECTION` (scopes observation+research; delegate to the SAME `queries/manual` read models a human uses) + `ARTIFACT_ATTACH_CITATION` (scopes research+proposal; own-artifact only per AL-16; cited revision must resolve; `artifact_link` `target_type=manual_citation`, `target_id="{doc}@{rev_no}"` — String(64), anchor rides in the citation payload; `citation_attached` event). **No Agent manual-mutation tool exists.**
- **Routes (`apps/api/routes/manual`)** — `GET /v1/manual/stream`, `GET /v1/manual/search`; Admin (route AND service `require_manual_admin` → 403 `ADMIN_MANUAL_WRITE_REQUIRED`): `POST /v1/admin/manual/documents`, `POST /v1/admin/manual/documents:upload` (JSON `source_filename`+`content`; TXT/MD/HTML only → 422 `MANUAL_FILE_TYPE_UNSUPPORTED`), `POST .../{id}/revisions` (If-Match mirror), `DELETE .../{id}`, `POST .../{id}:restore` (`require_trash_admin`).
- **12 new typed errors** in `shared/errors` (ADMIN_MANUAL_WRITE_REQUIRED, BASELINE_MANUAL_IMMUTABLE, MANUAL_TITLE_REQUIRED, MANUAL_CONTENT_REQUIRED, MANUAL_FILE_TYPE_UNSUPPORTED, MANUAL_SOURCE_ENCODING_INVALID, MANUAL_PARSE_FAILED, MANUAL_DUPLICATE_CONTENT, MANUAL_REVISION_CONFLICT, MANUAL_STREAM_CONFLICT, MANUAL_DOCUMENT_NOT_FOUND, MANUAL_SECTION_NOT_FOUND).
- **L1 lesson (important reuse knowledge):** SQLAlchemy does NOT order cross-table inserts by raw FK topology when no ORM `relationship()` exists — `manual_repo.create_document/create_revision/create_stream_entry` are async and **flush parent-before-child** (mirrors `agent_lab` repo). Empirically proven: without the flush, blocks hit the revisions FK.
- **Tests (+39 → 758 total, all green):** `tests/integration/test_user_manual.py` (17) — UM-01 baseline-first/positions, keyset stream pagination, atomic publish + audit, idempotent create replay, service-level non-admin denial (User/Supervisor/Agent), title/content validation, Markdown→canonical blocks, unsupported type + HTML `<script>` reject with **no phantom section**, duplicate block/override, FTS over title+heading+content (`ts_headline` excerpt) + soft-delete exclusion, Trash entry contract + idempotent repeat, baseline immutability, stale stream OCC, **deterministic restore** (same position 2 among later appends + same revision chain), revision replace (position kept, v1 superseded, search flips), **two-phase purge** (chunks redacted, revisions retained, tombstone), agent search/get_section, attach_citation ownership (own OK, foreign REJECTED `ARTIFACT_NOT_OWNED`), section anchor slicing + stale 404, L1 FK proof; `tests/contract/test_manual_contract.py` (22) — per-route × per-role 403 gating, restore trash-admin gating, anonymous 401, pre-DB upload-type/title validation.
- **Adversarial review** (`feature-dev:code-reviewer`): **0 CRITICAL / 0 HIGH** at confidence ≥80 (reviewer self-retracted its one HIGH candidate as spec-correct; verified lock ordering, OCC, allowlist, FTS keyset, parity). One dead-code nit (`_STRUCTURAL_TAGS`) empirically confirmed + removed.

**Deferred (tracked):** real multipart/object-storage upload path (V1 accepts JSON text content; raw-source object retention is policy-only), search-index outbox consumer (chunks are built in the publish tx — publication atomic, index effectively immediate; an async rebuild job can come later), superseded-revision chunk garbage collection (invisible to search via the `visible_revision_id` join; rows kept), citation resolution viewer for soft-deleted revisions (UM-12 retention read path — blocks/revisions are retained and resolvable, a dedicated artifact-viewer endpoint is Stage 8).

## Stage 7b — Future Dev (doc 22) ✅ landed (PR #32, merged → main `ef3e1c1`) — Stage 7 COMPLETE

The Future Dev **controlled activation boundary**: a server-side Capability Registry replacing the V18 static menu prototype — a capability below Limited/Active accepts NO command, starts NO job and produces NO output (CR-09). Migration **`0020_future_dev`** (→0019; up/down/up proven; new-table parity zero-diff): **6 tables** — `future_capability` (registry root; `capability_key` UNIQUE; per-row monotonic **`registry_version`** = the OCC token; `dependency_snapshot` JSONB `{"gates": {...}}`), `capability_activation_event` (immutable append-only; **UNIQUE `(capability_id, resulting_registry_version)`**; `snapshot_checksum` sha256), `analysis_artifact` + `view_dataset` (future OUTPUT roots with `deletion_state` overlay; only creatable while gating capability Limited/Active), `experiment_proposal` + `execution_plan` (**future-only contract tables — no V1 command writes them**; Live Trade = separate execution plane, FD-12). **Seven baseline V18 slots seeded by the migration** with deterministic ids (`fcap_<key>`, all Placeholder, `registry_version=1`) from `domain/capability/baseline.BASELINE_CAPABILITIES` — the SAME content source tests use: `live_trade`, `graphic_view`, `backtest_review`, `signal_intelligence`, `regime_research`, `hypothesis_lab`, `parameter_fields`.

- **domain/capability** — `enums` (`CapabilityState` 7 states, `ActivationGate` 7 gates, `OPERATIONAL_STATES = {limited, active}`, key constants, `CAPABILITY_ENTITY_TYPE`), `lifecycle` (**`ALLOWED_TRANSITIONS` legal-edge graph**: `placeholder→designed→internal→shadow→limited→active`; rollback `active→limited`, `limited→shadow`; `limited|active→retired`; **retired terminal**; `gate_issues`/`ensure_gates_pass` — Designed/Internal/Shadow require all 7 gate KEYS present, Limited requires 6 complete (all but `ui`), Active 7/7, failure → 422 `CAPABILITY_DEPENDENCY_MISSING` with per-gate issue list; `ensure_operational` → 403 `CAPABILITY_NOT_ACTIVE`; `snapshot_checksum`), `baseline` (7 seeds + doc-22 §4.1 Graphic View intro/6 cards + §7 per-state `STATE_MESSAGES`).
- **`transition_capability` (`application/commands/capability`)** — Admin at ROUTE and SERVICE (`require_capability_admin` → 403 `CAPABILITY_ACCESS_DENIED`), non-empty reason (else 422 `CAPABILITY_TRANSITION_REJECTED`), **REQUIRED idempotency key** (doc 22 §8) + **required `expected_registry_version`** OCC compared against the row after `session.refresh(with_for_update=True)` (stale → 409 `CAPABILITY_STATE_STALE`), legal-edge + gate checks, then registry mutation + activation event + audit + outbox in ONE tx via `run_idempotent`. `enabled_at` set on first Limited/Active; `retirement_at` on Retired.
- **Operational commands** — `query_view_dataset` (gates on `graphic_view`; pinned non-empty `source_manifest_refs` + `schema_version`; `view_dataset_prepared` outbox) and `create_analysis_artifact` (**`ANALYSIS_ARTIFACT_CAPABILITY`** type→capability map: `backtest_review|monte_carlo|walk_forward`→backtest_review, `signal_intelligence`, `regime_research`, `parameter_fields|sensitivity`→parameter_fields; `input_manifest_refs` + `method_version` mandatory; immutable row; `analysis_artifact_created` outbox). **State gate runs FIRST inside `_op`** — an inactive capability rejects before any validation/persistence, so FD-02 yields zero rows/jobs/events (HTTP path rolls back via `db_session`).
- **Queries + routes** — `list_capabilities`/`get_capability` (registry projections + `STATE_MESSAGES`), `get_graphic_view_overview` (static §4.1 intro + 6 cards + server state; no job/chart). Routes: `GET /v1/capabilities`, `GET /v1/capabilities/{key}`, `POST /v1/capabilities/{key}/lifecycle-transitions` (Admin), `GET /v1/future-dev/graphic_view/overview`, `POST /v1/view-datasets/query` (201), `POST /v1/analysis-artifacts` (201). **No live-trade/order/execution-plan route exists** (asserted by test).
- **CR-08 Tool Gateway gate** — `ToolName.VIEW_DATASET_QUERY` (`view_dataset.query`, scope research) + `ToolName.ANALYSIS_ARTIFACT_CREATE` (`analysis_artifact.create`, research+proposal); **`CAPABILITY_GATED_TOOLS`** maps tool → gating capability keys; **`exposed_tool_names(operational_keys)`** builds the Agent-visible registry (gated tools absent while nothing operational — FD-10); `capability_repo.operational_capability_keys(session)` supplies the input. A dispatched call while Placeholder → `CapabilityNotActiveError` (extends `ForbiddenError`) → recorded **REJECTED** tool call with reason_code `CAPABILITY_NOT_ACTIVE` via the existing `_record_rejection` path — never a job.
- **5 new typed errors** in `shared/errors` (CAPABILITY_NOT_FOUND 404, CAPABILITY_ACCESS_DENIED 403, CAPABILITY_TRANSITION_REJECTED 422, CAPABILITY_DEPENDENCY_MISSING 422 with per-gate `details`, CAPABILITY_STATE_STALE 409); pre-existing `CAPABILITY_NOT_ACTIVE` reused, NOT redefined.
- **L1 pattern honored:** `capability_repo.create_capability` flushes the registry row BEFORE `add_activation_event` references it; `create_view_dataset`/`create_analysis_artifact` flush; proven by the in-suite L1 FK insert-order test.
- **Tests (+23 → 781 total, all green):** `tests/integration/test_future_dev.py` — idempotent 7-slot seed, list/detail read models, static side-effect-free overview (FD-01/03), no live-trade route (FD-12), service-level non-admin denial (FD-13), empty-reason + missing-idempotency-key rejects, illegal edge + unknown state with `allowed_targets` details, stale OCC, missing-gate-keys per-gate issue list (FD-14), event/audit/outbox one-tx proof + version bump, idempotent transition replay (no double event), Limited-with-6-gates then Active-requires-`ui` then terminal Retired (FD-11), inactive view-dataset/analysis-artifact zero-side-effect rejects (FD-02), unknown artifact type, retired rejects ops with history preserved, Limited view-dataset pinning + validation (FD-04), Limited analysis artifact + MC→backtest_review gating (FD-05/09), CR-08 exposure matrix + `operational_capability_keys`, gateway REJECTED record while Placeholder + succeeded dispatch while Limited (FD-10), L1 FK proof, gate-key/seed-key consistency guard.
- **Adversarial review** (`feature-dev:code-reviewer`): **0 CRITICAL/HIGH/MEDIUM/LOW** at confidence ≥80 — verified CR-09 zero-side-effect ordering, CR-08 rejection path, OCC lock ordering, one-tx rule, migration parity, idempotency replay, FD-12.

**Deferred (tracked):** Coordinator does not yet CONSUME `exposed_tool_names` when planning (the CR-08 helper + repo input exist; wiring the planner's tool menu is Stage 8 gateway-parity work); no read endpoint lists `capability_activation_event` history (rows are queryable; an Admin history endpoint can ride a future Panel slice); `experiment_proposal`/`execution_plan` stay command-less by design until their capabilities leave Placeholder; frontend `/future-dev` shell is out of backend scope.

## Stage 8a — Integration Flows (Stage 8, part 1) ✅ landed (PR #34, merged → main `19c229c`)

The integration-flows half of Stage 8. **No migration** (alembic head stays `0020_future_dev`). Two production changes + three e2e/parity test suites (+10 → 791 tests):

- **Coordinator CR-08 wiring (deferred from 7b)** — `application/commands/agent_loop.run_coordinator_cycle` now resolves `capability_repo.operational_capability_keys(session)` + `tool_gateway.exposed_tool_names(...)` each cycle (after the pause gate — a paused runtime plans nothing, `exposed_tools: None`); the plan-time tool menu rides the cycle summary AND the `agent_task_created` event payload as plan provenance (FD-10: gated tools absent while nothing operational).
- **Cross-stage integration FIX found by flow (a)** — `application/commands/readiness_check._resolve_strategy_payload`: a strategy Mainboard item pinning the Strategy-editor MIRROR work-object revision (`{"strategy_revision_id", "config_hash", "display_name"}` — what `save_strategy_revision` appends) is dereferenced to the typed immutable `strategy_revision.payload` before config validation. Previously the editor path (draft → save → attach → Ready Check) yielded a false `STRATEGY_CONFIG_INVALID` blocker, so the doc-02→14→15 chain could never RUN. Disambiguation is structural: `StrategyConfig` is `extra="forbid"` with no `strategy_revision_id` field; an unresolvable mirror still fails validation visibly.
- **`tests/integration/test_e2e_pipeline.py` (flow a, 3 tests)** — full human pipeline over REAL ingested ids: Market+Research ingest→approve → Create Package (Pre-Check→candidate→draft→approve/publish) → Strategy revision pinning the real market+package refs → Mainboard attach (mirror revision) → Allocation (draft→validate→revision) → Ready Check → RUN → succeeded Result → Results History → Arrange Metrics (personal profile fork) → soft-delete → Trash entry → Admin `restore_trash_entry` → History returns. Asserts: exact-pin manifest (`root_id`→`selected_revision_id`), INF-04 idempotent re-run reuse, CR-03 (tampered manifest → failed run → zero Results, empty History), INF-05 no-'latest'-leak (approved market successor: old manifest untouched, new run shares the SAME `execution_key` + identical metric values = pinned-manifest reproducibility — `manifest_hash` includes run identity, `execution_key` is the content hash), monotonic audit+outbox growth per phase, Trash round-trip keeps the historical manifest byte-identical.
- **`tests/integration/test_e2e_agent_loop.py` (flow b, 2 tests)** — UI-independent Agent loop (INF-06): Admin directive → `run_coordinator_cycle` (consumed exactly once, AL-14; summary carries `exposed_tools`) → gateway `data_bundle.resolve` (EXECUTION evidence gate) → `backtest.request` on the Agent's OWN composition → engine worker → `result.query` → `artifact.create` hypothesis with `ArtifactLink` provenance to the result; every step a durable `AgentToolCall` row. Boundary: `backtest.request` on a HUMAN composition = recorded REJECTED, zero runs.
- **`tests/integration/test_gateway_parity.py` (5 tests)** — Agent tool line ≡ human command line: ready-check same report contract (same fingerprint/state), foreign-composition denial-code parity (raised `.code` == recorded `failure_code`), CR-08/CR-09 capability parity (Placeholder rejects BOTH lines `CAPABILITY_NOT_ACTIVE` with zero `ViewDataset`/`Job` rows; Limited allows both), Coordinator plan wiring proof over a live `graphic_view` walk to Limited (summary + event payload == `exposed_tool_names(operational_keys)` exactly).
- **Adversarial review:** 0 findings at confidence ≥80 (mirror disambiguation, paused path, lock scopes, no privilege widening all explicitly verified).
- **Test-infra lesson:** integration tests rebuild the schema per test — two sessions sharing one local Postgres destroy each other (a 47-failure wave was pure cross-session contention; suite is green on an isolated DB, e.g. `TEST_DATABASE_URL=...entropia_stage8`).

**Deferred (tracked):** `dispatch_tool_call` merged-response quirk — a handler payload's `status` key (e.g. hypothesis `exploring`) shadows the envelope's `succeeded`; the durable tool-call row is authoritative (spawned follow-up task chip).

## Stage 8b — Hardening (Stage 8, part 2) ✅ landed (PR #35, merged → main `bc38ca6`) — Stage 8 COMPLETE, **V1 ROADMAP COMPLETE**

The hardening half. **No migration.** +10 tests → **801 total**.

- **Outbox→SSE fan-out, all domains (Module 20 §10)** — `application/jobs/outbox_relay.py`: `relay_unpublished` (the scheduler's durable `published_at` checkpoint; id-ordered batches, `FOR UPDATE SKIP LOCKED`), `fetch_events_after` (read-only ULID-cursor feed, deliberately independent of the published checkpoint), `latest_event_id`, `outbox_lag_seconds`. `apps/api/sse.py` REWRITTEN: `SseHub` (in-process broadcast, drop-on-full per subscriber) + `run_outbox_poller` (per-process tail from the boot-time cursor; loss-tolerant by contract INF-11 — reconnect = query refetch; never crashes the API, lifespan-managed) + typed taxonomy `sse_event_name` (`backtest.run.updated` / `job.updated` / `agent.task.updated` / `resource.changed`) + heartbeat kept. **ID caveat:** `new_id` suffixes are random within one millisecond, so same-ms outbox ordering is approximate — fine for a loss-tolerant projection feed; tests pin explicit ids for determinism.
- **Real scheduler (Module 20 §6)** — `application/jobs/maintenance.py`: `recover_stale_jobs` (INF-09: committed RUNNING older than `JOB_STALE_AFTER_SECONDS` → attempts+1 → QUEUED redelivery or terminal `FAILED_FINAL` at max_attempts, each recovery audited `job.stale_recovered`; the one-tx worker pattern means a committed RUNNING row only exists after a true crash — verified no mid-flight commits in any worker) + `redeliverable_queued_jobs` (INF-03: durable QUEUED rows older than the grace window). `apps/scheduler/__main__.py` per tick: heartbeat + one-tx maintenance pass (relay + recovery + sweep) + re-dispatch via **`ACTOR_BY_QUEUE`** (`backtest`/`agent`/`agent-high`/`maintenance`; the multi-actor `data` queue is deliberately NOT auto-redelivered — recovery requeues the row, re-dispatch is an operator action); per-item send guard (a broker blip skips to next tick, rows stay durably QUEUED).
- **API hardening** — `apps/api/hardening.py`: `SecurityHeadersMiddleware` (nosniff, frame-deny, no-referrer, CSP `default-src 'none'`; HSTS production-only), opt-in `RateLimitMiddleware` (`RATE_LIMIT_ENABLED`, default OFF; fixed 60s window keyed by `X-Actor-Id` or client IP; separate write budget; `/health/*` + `/metrics` exempt; 429 = standard `ErrorResponse` envelope + `Retry-After` + `X-RateLimit-*`; **bounded memory**: prune + 10k hard cap under key churn), `MetricsMiddleware`. Stack order verified: a 429 still gets security headers + request ids and is counted.
- **Metrics (Module 20 §11)** — `infrastructure/observability/metrics.py` (dependency-free Prometheus text: request counters, latency histogram, in-flight gauge; **unmatched paths label as `unmatched`** — 404 scans cannot grow label cardinality) + `GET /v1/metrics` with scrape-time operational gauges (`entropia_jobs_depth{queue,status}`, `entropia_outbox_lag_seconds`, `entropia_job_lease_age_seconds`) that degrade gracefully when the DB is unreachable (scrape never 500s).
- **Settings** — `SSE_POLL_INTERVAL_SECONDS`, `OUTBOX_RELAY_BATCH_SIZE`, `JOB_STALE_AFTER_SECONDS`, `JOB_REDELIVER_GRACE_SECONDS`, `RATE_LIMIT_*` (all env-driven; rate limit is per-deployment opt-in).
- **Deployment** — topology already complete in `docker-compose.yml` (api + 4 worker planes + agent-coordinator + scheduler + postgres/redis/minio); `/health/live` + `/health/ready` unchanged and green.
- **Adversarial review:** 2 HIGH, **both verified real and fixed in-commit** (metrics label cardinality via raw 404 paths → `unmatched` sentinel + regression assert; rate limiter unbounded key growth under attacker-controlled `X-Actor-Id` → prune + hard cap). Stale-recovery false-positive race explicitly verified impossible (READ COMMITTED + one-tx workers); middleware ordering, poller shutdown, TimeoutError semantics (py3.12) verified clean.
- **Tests (+10):** relay checkpoint/batch/lag, cursor feed independence, hub broadcast + full taxonomy, INF-09 requeue→terminal with 3 audits, INF-03 sweep scoping + ACTOR_BY_QUEUE contract, security headers, metrics exposition + 404 sentinel, rate limit shed/exempt/opt-in (frozen clock — no window-boundary flake).

**Deferred (tracked):** retention-window AUTO-purge (V1 purge stays Admin-requested two-phase; scheduler only redelivers lost purge jobs); `data`-queue auto-redelivery (multi-actor queue → operator action); SSE HTTP-streaming e2e test (hub/poller/feed covered directly); frontend SSE consumption + `/metrics` dashboards.

## Post-V1 — Auth/IdP (Master §20 → local auth) ✅ landed (PR #38, merged → main `b9a9178`)

Migration **`0021_local_auth`** (→0020): `human_credentials` (argon2id hash, secret material apart from the user root) + `auth_sessions` (opaque Bearer; only the SHA-256 `token_hash` is stored; `expires_at`/`revoked_at`; `idx_auth_sessions_user_id`). New dep `argon2-cffi`. +12 tests → **813 total**.

- **Commands** — `application/commands/auth.py`: `sign_up` (role ALWAYS `user` — the route schema has no role field, escalation structurally impossible; **FK-ordered staged flushes** principal→human_user→credential — the L1 insert-order trap fired empirically in one flush and was fixed; unique race → 409 `USERNAME_TAKEN`), `login` (ONE 401 `INVALID_CREDENTIALS` for unknown user / wrong password / disabled account, argon2 `DUMMY_HASH` timing pad on both miss paths, rehash-on-verify, token = `secrets.token_urlsafe(32)` returned exactly once), `logout` (retry-safe no-op, no audit noise on re-revoke). One-tx no-commit, audit in the same tx; outbox only for the domain resource (`user_created`) — sessions are infra, no SSE noise.
- **Transport** — `apps/api/deps.py`: **`AUTH_MODE=dev|session`** (`dev` default → the `X-Actor-Id` line is byte-identical for tests/local). Session mode: bare `X-Actor-Id` is IGNORED; Bearer → `auth_sessions` lookup → role re-resolved from the registry on EVERY request (M1 §4.2: an Admin role change applies on the next request; a disabled/deleted user loses the live session) → invalid/expired/revoked = 401 `SESSION_INVALID`. **Service line**: `ENTROPIA_SERVICE_TOKEN` (`hmac.compare_digest`; empty disables) + `X-Actor-Id` must resolve to a NON-human principal, else 401 `SERVICE_LINE_FORBIDDEN` — agent/scheduler HTTP can never impersonate a human. New helper `bearer_token(request)`.
- **Routes** — `apps/api/routes/auth.py`: `POST /v1/auth/signup` (201) / `login` / `logout`.
- **Hardening** — rate-limit bucket key now prefers a sha256 digest of the `Authorization` header (raw token never sits in limiter memory); dev header + IP fallback unchanged.
- **Settings** — `AUTH_MODE`, `AUTH_SESSION_TTL_MINUTES` (default 720), `ENTROPIA_SERVICE_TOKEN`. **Errors** — `INVALID_CREDENTIALS`, `SESSION_INVALID`, `USERNAME_TAKEN`, `PASSWORD_POLICY`, `SERVICE_LINE_FORBIDDEN`.
- **Verify:** 813 green on an isolated DB; alembic 0021 up/down/up + column parity + L1 FK proof on real Postgres. **Review: 0 confirmed CRITICAL/HIGH** (timing pad, fixation absence, escalation closure, tx ordering explicitly verified).

## Post-V1 — Parquet batch data-access (INF-12, Slice A) ✅ landed (PR #41, merged → main `3deee28`)

No migration (alembic head stays `0021_local_auth`). +5 tests → **818 total**. Slice A of the real-backtest-engine track: the Data/Backtest worker can now stream a pinned market revision's processed Parquet asset in bounded batches instead of materializing the whole object in memory.

- **Streaming** — `infrastructure/s3/parquet_stream.py`: `stream_processed_batches(object_key)` (S3 `download_fileobj` → `SpooledTemporaryFile` with a 32MB spill-to-disk cap → `pyarrow.parquet.ParquetFile.iter_batches`); `iter_parquet_batches(source)` is pure local I/O so the batching contract is unit-testable without infra; `DEFAULT_BATCH_SIZE = 8_192`. Worker plane only — never runs in the API process.
- **Query layer** — `application/queries/market_bars.py`: `resolve_bar_source(session, market_revision_id=...)` (pinned revision → newest content-addressed processed asset → `BarSourceRef` frozen dataclass: entity_id/revision_id/object_key/content_digest/size_bytes/row_count; `NotFoundError` if the revision was never processed) + `iter_bar_batches(source)` (worker plane). Read-only — never touches 'latest' (doc 15 no-latest-leak contract).
- **Repository** — `repositories/market_data.py`: `get_processed_asset_for_revision(session, market_revision_id)` with an explicit ordering contract — re-processing jobs run in separate transactions (distinct ULID timestamps); the same-ms ULID tiebreak is non-deterministic and documented as a limit, pinned by a deterministic test.
- **mypy** — `pyarrow.*` added to the untyped overrides (no stubs published).
- **Verify:** 818 green on an isolated DB; ruff/format/mypy clean. **Review: 1 finding (ULID same-ms tiebreak) — empirically CONFIRMED**, addressed via the documented ordering contract + deterministic test.

## Post-V1 — Backtest Engine (INF-12, Slice B) ✅ landed (PR #43, merged → main `fc746f8`)

No migration (alembic head stays `0021_local_auth`). +4 tests → **822 total**. Slice B of the real-backtest-engine track: the deterministic stub is replaced by a real single-pass **bar-replay** simulation over the pinned market revision's OHLCV bars (built on Slice A's `iter_bar_batches`). Run / manifest / result contracts are UNCHANGED — only the engine's internal price evaluation is now real.

- **Engine** — `domain/backtest/engine.py`: `run_engine(*, strategy_config, bar_batches, execution_key, item_count=1) → EngineOutput` — pure (no DB / clock / randomness), streams `bar_batches` once. Frozen output rows `TradeRow` / `EquityPoint` / `SignalEventRow` / `EngineOutput`. **Real** protection stops — `_initial_static_stop` (tightest of percentage / absolute), `_trail_pct` + `_effective_stop` (trailing), evaluated **intrabar** (long: `bar.low ≤ stop`; short: `bar.high ≥ stop`) → `stop_loss`; opposite-breakout `_exit_proxy` → `exit_signal`; end-of-data close → `end_of_data` (open position never left dangling). Adverse-side costs — `_cost_params` / `_effective_fill` (half-spread + slippage fraction + per-fill commission ×2 round-trip).
- **Entry PROXY (honest boundary)** — entry is still a **breakout proxy** (`_BREAKOUT_WINDOW = 20` look-back; long on a new window high, short on a new low; long wins a same-bar tie). The indicator layer stays stubbed, labelled `entry_model = deterministic_bar_breakout_proxy_v1` in diagnostics. Direction restriction → `suppressed_entries` → one `filtered_no_entry` signal event.
- **Sizing** — `_position_size`: explicit `base_position_size`, else all-in **notional** clamped to `max(equity, 0)` (a bust account → size 0, **never negative** — a negative size would invert the PnL sign of every subsequent trade; review CRITICAL, pinned by a deterministic bust-safety test). `risk_based_sizing` / `formula_based_sizing` are NOT modelled → fall back to notional + a `position_sizing_method_unsupported:<method>` diagnostics warning (L4 — surfaced, never fabricated).
- **Job** — `application/jobs/backtest_engine.py`: `run_backtest(..., stream_bars=iter_bar_batches)` — bars are **injectable** (default the real S3-backed streamer) so integration tests drive resolve → replay → persist end-to-end. Fail paths: no / unresolvable market revision → `ASSET_UNAVAILABLE`; any engine exception → `ENGINE_ERROR` (both audited).
- **Manifest** — `domain/backtest/manifest.py`: `ENGINE_VERSION = "backtest-engine-v1-bar-replay"` (folded into the `execution_key` reproducibility hash → identical compositions reproduce identical results; INF-05).
- **Open ends (deferred, honest):** `summary["timeframe"]` is still `None` (DataContext carries no base timeframe — resolvable from market-revision metadata if wanted); `risk_based` / `formula_based` sizing unimplemented (warns); entry/exit **indicator compute is the natural next slice** — only `engine.py`'s entry/exit evaluation changes, run/manifest/result contracts stay fixed.
- **Verify:** 822 green on an isolated DB; ruff / format / mypy clean. **Review: 1 CRITICAL** (negative all-in size on a bust account inverts PnL signs) — **empirically CONFIRMED and fixed in-commit** via the `max(equity, 0)` clamp + a deterministic bust-safety test.

## Post-V1 — Backtest Engine (INF-12, Slice C) ✅ landed (PR #45, merged → main `a11640c`)

No migration (alembic head stays `0021_local_auth`). +37 tests → **859 total**. Slice C of the real-backtest-engine track: the engine's entry/exit breakout **PROXY** is replaced by real built-in indicator signals (native-trigger foundation). **Only** the engine's entry/exit evaluation changes — run / manifest / result contracts stay fixed.

- **Indicators (pure, new)** — `domain/backtest/indicators.py`: pure, incremental (bounded-memory) `Decimal` TA compute for the seeded canonical keys — `ta.sma` / `ema` / `rma` / `wma` (MA-cross native trigger) + `ta.rsi` (band cross); `ta.atr` / `ta.vwap` are RECOGNIZED but non-directional (unresolved). Types `IndicatorSpec` / `SignalRule` / `IndicatorPlan`; `BlockEvaluator` (validity window + per-block direction filter), `aggregate` / `build_evaluators`; `BUILTIN_ENTRY_MODEL = "builtin_indicator_native_trigger_v1"`. Params: `parameter_overrides` when present, else engine-version defaults (RSI 14, MA 20, bands 30/70 — reproducibility constants).
- **Plan resolution (new)** — `application/queries/indicator_plan.py`: `resolve_indicator_plan(session, strategy_config) → IndicatorPlan` dereferences each pinned `PackageRevision.dependency_snapshot["resolved"][i]["canonical_key"]` → built-in spec. **Package bodies are NOT executed.** NATIVE-TRIGGER-ONLY: `*_plus_condition` / timeframe override / non-directional key → `unresolved` diagnostics warning (never silently dropped — L4).
- **Engine dual-mode** — `domain/backtest/engine.py`: `run_engine(..., indicator_plan=None)`; a resolved entry block drives real signals, else it falls back to the labelled breakout PROXY (backward compatible — Slice B path intact). Exit = real protection stops (Slice B) + exit blocks + `exit_on_opposite`.
- **Job** — `application/jobs/backtest_engine.py`: resolves + injects the plan (run/manifest/result contracts unchanged). **Manifest** — `domain/backtest/manifest.py`: `ENGINE_VERSION = "backtest-engine-v2-indicator-compute"` (folds into the `execution_key` reproducibility hash — INF-05 preserved; same composition → same result).
- **Honest boundary (native-trigger-only; surfaced, never hidden — L4):** only `trigger_source == indicator_native_trigger` resolves to real signals; `*_plus_condition`, timeframe overrides, and non-directional keys (`ta.atr` / `ta.vwap`) become `unresolved` warnings; concrete params come from the un-parsed source body → engine-version defaults + `parameter_overrides`.
- **Tests (+37):** `tests/unit/test_backtest_indicators.py` (**+24** — MA/RSI reference values + invariants, native triggers, validity windows, aggregation), `tests/unit/test_backtest_engine_indicator_plan.py` (**+7** — real `entry_model`, determinism across batch sizes, exit-on-opposite, proxy fallback + unresolved warnings), `tests/integration/test_indicator_plan_resolution.py` (**+6** — real `package_revision` rows incl. every unresolved path), `test_e2e_pipeline.py` (published RSI package drives real compute `entry_model == BUILTIN_ENTRY_MODEL` end-to-end).
- **Verify:** 859 green on an isolated DB; ruff / format / mypy clean; **no migration** (head stays `0021_local_auth`). Merged via green CI (backend lint/type/integration on real Postgres + alembic). Contract-preserving compute change (run/manifest/result fixed) — no blocking review finding carried into this handoff.

## Post-V1 — Backtest Engine `risk_based` sizing (INF-12, Slice C follow-up a) ✅ landed (PR #47, merged → main `4b4d1c6`)

No migration (alembic head stays `0021_local_auth`). +5 tests → **864 total**. First of the Slice C follow-ups: `risk_based_sizing` is now really modelled inside `_position_size` (it previously fell back to notional + an `unsupported` warning). **Only** the engine's position-sizing branch changes — run / manifest / result contracts stay fixed; the manifest bumps `ENGINE_VERSION` because sized output changed.

- **Engine** — `domain/backtest/engine.py`: `_position_size` gains a `risk_based` branch — `size = max(equity, 0) * risk% / 100 / stop_loss_point` (deterministic, **independent of `entry_price`**, non-negative clamp — a negative size would invert the PnL sign of every subsequent trade, the earlier review CRITICAL). New helper `_sizing_is_honored(config)`: explicit `base_position_size` **and** `risk_based_sizing` **carrying a `risk_based` sub-config** are honored; `formula_based_sizing` **and** a `risk_based` request **without** its sub-config fall back to notional + the L4 `position_sizing_method_unsupported:<method>` warning. The diagnostics warning now keys off `_sizing_is_honored(config)` rather than `method != base_position_size`.
- **Manifest** — `domain/backtest/manifest.py`: `ENGINE_VERSION` bump `backtest-engine-v2-indicator-compute` → **`backtest-engine-v2-risk-based-sizing`**. Rationale: `risk_based` output now differs, so the version must shift the `execution_key` namespace (INF-04 idempotent reuse / INF-05 reproducibility) — this prevents reusing a stale notional-sized result cached under the old version for the same composition.
- **Tests (+5)** — `tests/unit/test_backtest_engine.py`: `_config` fixture extended with `risk_pct` / `stop_point`; +5 tests (risk-formula reference value, entry-price independence, bust clamp → 0, honored/unsupported warning in both directions); 2 pre-existing tests repointed to `formula_based_sizing` (still the honest unsupported path).
- **Verify:** 864 green on an isolated DB; ruff / format / mypy clean; **no migration** (head stays `0021_local_auth`). **Review: code-reviewer APPROVE — 0 CRITICAL / 0 HIGH** (contract-preserving sizing change; the negative-size hazard is covered by the `max(equity, 0)` clamp + bust test).

## Post-V1 — Backtest Engine condition blocks (INF-12, Slice C follow-up b) ✅ landed (PR #49, merged → main `6854e06`)

No migration (alembic head stays `0021_local_auth`). +28 tests → **892 total**. THRESHOLD-ONLY nested condition gating for the bar-replay engine: an indicator block with `trigger_source=indicator_native_trigger_plus_condition` now resolves and its native trigger fires only on a bar where the block's nested condition(s) hold (per `condition_block_rule`). Conditions are directionless gates. **Scope decision:** only the native-trigger gate is modelled; `indicator_output_plus_condition` stays an honest deferred `unresolved`. run / manifest / result contracts unchanged.

- **Compute** — `domain/backtest/indicators.py`: `ConditionSpec` + `ConditionEvaluator` (per-bar threshold check on a bar price field or the parent block's `indicator_output` value vs a strategy constant; validity window mirrors the trigger's `_VALIDITY_BARS`; strict `>`/`<`; `until_opposite_signal` clears on a false check; a `None` source during parent warm-up fails closed). `CONDITION_KEYS = {cond.above, cond.below}`; `_conditions_satisfied` aggregates required/supporting (no explicit required → all-must-hold, never a vacuous gate). `BlockEvaluator.current_signal` gates the trigger; `IndicatorSpec` gains `conditions` / `condition_rule` / `min_condition_support` (all defaulted → Slice C native path intact).
- **Resolution** — `application/queries/indicator_plan.py`: `_resolve_block` accepts `native_plus_condition` and dereferences each pinned condition package's `cond.*` dependency into a `ConditionSpec` (`_resolve_conditions` / `_resolve_condition` / `_primary_condition_key` / `_source_override`). **Fail-closed:** any unresolvable condition (missing package / no `cond.*` key / absent threshold) leaves the WHOLE block `unresolved` with a specific reason (L4). Threshold is REQUIRED from `parameter_overrides` (no universal default); source defaults to `close`.
- **Engine + manifest + seed** — `engine.py` feeds full OHLC to the evaluators (price-source conditions) + a `condition_blocks` diagnostics count; `manifest.py` `ENGINE_VERSION` → **`backtest-engine-v2-condition-blocks`** (shifts `execution_key` namespace, INF-04/INF-05). `apps/seed.py` seeds `cond.above` / `cond.below` as trusted-active ESP resolvers (boolean return) via an extracted `_seed_esp_resolver`.
- **Tests (+28)** — `tests/unit/test_backtest_conditions.py` (compute: raw checks, all sources, validity, block gating, aggregation), `test_backtest_engine_condition_gating.py` (engine allow/block, `indicator_output` source, batch-size determinism), `tests/integration/test_condition_plan_resolution.py` (every fail-closed path + an end-to-end published-condition-package gate). One pre-existing test repointed to `indicator_output_plus_condition` (still deferred).
- **Verify:** 892 green on an isolated DB; ruff / format / mypy clean; **no migration** (head stays `0021_local_auth`). **Review: code-reviewer APPROVE — 0 CRITICAL / 0 HIGH** (determinism-critical paths verified: OHLC plumbing, fail-closed resolution, validity-window arithmetic, `ENGINE_VERSION` shift, warm-up fail-close).

## Post-V1 — Backtest Engine condition extensions (INF-12, Slice C follow-up b2) ✅ landed (PR #51, merged → main `6913b0a`)

No migration (alembic head stays `0021_local_auth`). +24 tests → **916 total**. Extends the threshold-only gate from (b) with **crosses, ranges, series-vs-series RHS, and condition-only directional signals** — the honest boundary of single-package condition compute. `indicator_output_plus_condition` is now RESOLVED (was deferred in (b)). Back-compat: native triggers and native-gated `cond.above`/`cond.below` behave exactly as in (b)/(Slice C). run / manifest / result contracts unchanged.

- **Compute** — `domain/backtest/indicators.py`: `CONDITION_KEYS` grows to 5 — `cond.above`/`cond.below` (LEVEL), `cond.crosses_above`/`cond.crosses_below` (EDGE: prev on/under RHS → now strict over/under, via `_prev_source`/`_prev_rhs` tracking; warm-up `None` fails closed), `cond.between` (RANGE: strict `lower < source < upper`, non-directional). New `CROSS_CONDITION_KEYS` / `RANGE_CONDITION_KEYS`; `condition_direction()` (crosses_above→long, crosses_below→short, else None). `ConditionSpec` gains `lower`/`upper`/`reference` (threshold now Optional); `ConditionEvaluator._rhs_value` resolves a **reference series OR a constant threshold** → series-vs-series compare. `IndicatorSpec` gains `condition_only` (default False); in `condition_only` mode `BlockEvaluator` SKIPS the native `_detect`, fires on the **rising edge** of the `_conditions_satisfied` gate (`_prev_gate`), directs via `_condition_only_direction(spec)` (shared polarity of required crosses), holds for the block validity window, and filters by `block.direction`; `current_signal` returns `_active_dir` in condition_only (no re-gating), native mode byte-for-byte unchanged.
- **Resolution** — `application/queries/indicator_plan.py`: `_ACCEPTED_TRIGGERS` += `indicator_output_plus_condition`; `_resolve_condition` handles `between` (`lower`/`upper` REQUIRED + `lower < upper`, else `condition_bounds_missing`/`condition_bounds_invalid`) and `reference` (`_reference_override` → threshold OPTIONAL when a reference is set). `condition_only` validation: `_condition_only_direction_reason` → no single required-cross polarity ⇒ `condition_only_no_directional_edge`; conflicting crosses ⇒ `condition_only_conflicting_direction` (FAIL-CLOSED, whole block `unresolved`). **Honest boundary in the docstring:** comparing two SEPARATE packages needs a second `package_ref` (schema extension) — out of scope; today only single-package series-vs-series.
- **Engine + manifest + seed** — `manifest.py` `ENGINE_VERSION` → **`backtest-engine-v2-condition-extensions`** (shifts `execution_key` namespace so stale condition-blocks results are not reused, INF-04/INF-05). `apps/seed.py` `_ESP_COND_RESOLVERS` += `cond.crosses_above`/`below` (`["series","float"]`) + `cond.between` (`["series","float","float"]`).
- **Tests (+24)** — `tests/unit/test_backtest_condition_extensions.py` (crosses edge semantics, between range, series-vs-series, condition_only direction + edge-fire), plus condition-plan-resolution integration for every new fail-closed path; one pre-existing test repointed.
- **Verify:** 916 green on an isolated DB; ruff / format / mypy clean; **no migration** (new semantics ride in `parameter_overrides` JSONB; new `cond.*` keys are seed data). **Review: code-reviewer APPROVE — 0 CRITICAL / 0 HIGH.**

## Post-V1 — Backtest Engine two-package indicator-vs-indicator (INF-12, Slice C follow-up) ✅ landed (PR #53, merged → main `093df44`)

No migration (alembic head stays `0021_local_auth`). +12 tests → **928 total**. Opens the honest boundary left by (b2): a nested `ConditionBlock` can now pin a **SECOND indicator package** whose computed output series becomes the condition's RHS — the canonical **fast-MA vs slow-MA crossover**. Previously the RHS could only be a constant `threshold` or a bounded single-package `reference` series. Back-compat: all single-package forms behave byte-for-byte as in (b2); the **engine is unchanged** (the reference series is self-computed inside the evaluator). run / manifest / result contracts unchanged.

- **Schema (no migration)** — `domain/strategy/config.py`: `ConditionBlock` gains optional `reference_package_ref: PackageReference | None` (default `None`; Pydantic/JSONB, backward compatible). When set it takes **precedence** over a constant threshold / bounded reference series.
- **Compute** — `domain/backtest/indicators.py`: `ConditionSpec` gains `reference_key`/`reference_length`. New `_build_reference_indicator(key, length)` factory **reuses `_MovingAverage`/`_Rsi`** (Wilder RSI for `ta.rsi`, else a moving average — mirrors `BlockEvaluator`'s compute choice). `ConditionEvaluator` gains a `_ref_indicator` slot, **advances it inline from `close` each bar** (`.update(close)`), and `_rhs_value` resolves in precedence order: **reference indicator value > bounded `reference` series > constant `threshold`**. A warming-up reference indicator returns `None` → **fails the check closed** (LEVEL and CROSS alike), exactly like any missing series.
- **Resolution** — `application/queries/indicator_plan.py`: new `_resolve_reference_package(session, cond) → (key, length, reason)` dereferences the 2nd pinned package's revision to a `DIRECTIONAL_KEYS` canonical key via `_primary_directional_key(revision.dependency_snapshot)` + a look-back (`_int_override(_REFERENCE_LENGTH_KEYS)` — `reference_length`/`compare_length`/`reference_len` — else `default_length(key)`). The 2nd package's **body is never executed**. `_resolve_condition` precedence: reference package → bounded reference → threshold. **Fail-closed reasons:** `condition_reference_package_unresolved` (missing revision), `condition_reference_no_series` (key not a computable `DIRECTIONAL_KEYS` MA/RSI series), `condition_reference_package_on_range` (a reference package pinned on a `cond.between` RANGE condition is a misconfiguration, surfaced not silently ignored). Docstring honest-boundary updated.
- **Manifest** — `manifest.py` `ENGINE_VERSION` → **`backtest-engine-v2-indicator-vs-indicator`** (shifts the `execution_key` namespace so stale condition-extensions results are not reused — a new RHS source changes results; INF-04/INF-05). `apps/seed.py` unchanged (the new RHS rides on an existing pinned package; no new `cond.*` resolver key).
- **Tests (+12)** — `tests/unit/test_backtest_indicator_vs_indicator.py` (+6: reference-package LEVEL/EDGE compute, warm-up fail-closed, precedence-over-threshold, RSI reference key, and the **flagship condition-only fast(2)/slow(4) MA-cross → long entry**) + `tests/integration/test_condition_plan_resolution.py` (+6: `_cblock` gains `reference_package_rev`/`reference_length` params; resolve + all 3 fail-closed paths + a real published 2-package MA-cross e2e long entry).
- **Verify:** 928 green on an isolated DB; ruff / format / mypy clean; **no migration**. **Review: code-reviewer APPROVE — 0 CRITICAL / 0 HIGH.**

## Post-V1 — Backtest Engine higher-timeframe bar resampling (INF-12, Slice C follow-up c) ✅ landed (PR #55, merged → main `<merge>`)

An indicator block may now compute on a timeframe **coarser** than the base bars. Previously any explicit `timeframe` override was honest-unresolved (`timeframe_override_deferred`); it now **resamples**. No migration (alembic head stays `0021_local_auth`). +11 tests → **939 total**. The base-TF compute path is **byte-identical** to Slice C; run / manifest / result contracts unchanged.

- **Resampling (pure)** — `domain/backtest/indicators.py`: `timeframe_seconds()` maps the fixed override vocabulary (`1m`…`1D`) to a second span; `_epoch_seconds`/`_htf_bucket` parse an ISO/`Z`/epoch timestamp (clock-free) and floor it into a higher-TF bucket. `IndicatorSpec` gains `resample_seconds: int | None`. `BlockEvaluator.update` splits into a base/HTF **dispatcher** + `_advance` (the former per-bar body). In HTF mode it aggregates the base bars into the block's coarser candle (open=first, high=max, low=min, close=last) and calls `_advance` **only when the candle CLOSES** = the first base bar of the NEXT bucket → **no look-ahead / no repaint**; a trailing partial candle never finalizes; validity/conditions tick in higher-TF candles.
- **Resolution** — `application/queries/indicator_plan.py`: `_resolve_base_seconds` reads the pinned market revision's base timeframe (new read-only `market_data.get_base_timeframe_for_revision`, `ResolutionKind.BAR` `resolution_value`); `_resolve_timeframe` resolves an override — **coarser than base → `resample_seconds`**, **finer → `timeframe_finer_than_base`**, **equal → base compute**, **base unknown → still resamples** (degrades to the base bars, deterministic).
- **Engine / manifest** — `engine.py` passes `bar.timestamp` to the evaluators + a `multi_timeframe_blocks` diagnostic. `manifest.py` `ENGINE_VERSION` → **`backtest-engine-v2-multi-timeframe`** (shifts the `execution_key` namespace; INF-04/INF-05).
- **Honest boundary** — a **per-condition** multi-TF reference (item ii) is still deferred; conditions inherit the parent block's timeframe.
- **Tests (+11)** — `tests/unit/test_backtest_multi_timeframe.py` (+6: span map, epoch bucketing, no-look-ahead timing, trailing-partial, hand-aggregated equivalence, batch-invariant engine entry) + `tests/integration/test_multi_timeframe_plan_resolution.py` (+5: coarser/finer/equal/unknown-base branches + a real 2h MA-cross e2e long entry). `test_indicator_plan_resolution.py` override test repointed to the new resolve path.
- **Verify:** 939 green on an isolated DB; ruff / format / mypy clean; **no migration**. Self-reviewed (no separate code-reviewer agent — correctness pinned by the no-look-ahead / trailing-partial / equivalence / determinism / 4-branch-resolution / e2e tests).

## Post-V1 — Backtest Engine per-condition multi-timeframe reference (INF-12, Slice C follow-up i) ✅ landed (PR #56, merged → main `<merge>`)

A nested condition's **RHS reference indicator** (`reference_package_ref`, the two-package indicator-vs-indicator form from PR #53) may now compute on a timeframe **coarser** than its parent block. The fast `source` (parent TF) is compared against a slower reference series that only advances when a reference candle **CLOSES** — **no look-ahead / no repaint**, symmetric with (c). Unblocked by (c). No migration (alembic head stays `0021_local_auth`). +14 tests → **953 total**. The `reference_resample_seconds=None` path is **byte-identical** to the (#53) two-package form; run / manifest / result contracts unchanged.

- **Config** — `domain/strategy/config.py`: `ConditionBlock.reference_timeframe` (optional Literal, default `same_as_base_tf`; same vocabulary as `IndicatorBlock.timeframe`; JSONB, no migration). Only meaningful with a `reference_package_ref`.
- **Compute (pure)** — `domain/backtest/indicators.py`: `ConditionSpec` gains `reference_resample_seconds: int | None`. `ConditionEvaluator._advance_reference` aggregates the base bars' closes into the reference candle and advances the RHS **only on a completed candle** (first bar of the next bucket) — mirrors the block-level HTF dispatcher; `reference_resample_seconds is None` short-circuits to advance-every-bar (byte-identical). `ConditionEvaluator.update` gains a `timestamp` kwarg. `BlockEvaluator._advance` threads `timestamp` to the conditions and tracks `_form_ts` (the forming HTF candle's close time), so a nested reference buckets against the candle the parent trigger sees, not raw base bars.
- **Scope (honest dar boundary)** — only the `reference_package_ref` RHS is resampled; a bounded `reference` / constant `threshold` RHS stays on the block's timeframe.
- **Resolution** — `application/queries/indicator_plan.py`: `_resolve_reference_timeframe` resolves `ConditionBlock.reference_timeframe` against **`block_effective_seconds`** (the block's own resample span else the base bars) — **coarser → `reference_resample_seconds`**, **equal → block compute**, **finer → `condition_reference_timeframe_finer_than_block`**, **base/block unknown → still resamples**. `_resolve_reference_package` returns a 4-tuple `(key, length, resample, reason)`; a reference-TF override with **no reference package** → `condition_reference_timeframe_without_package`.
- **Engine / manifest** — `engine.py` adds a `per_condition_timeframe_conditions` diagnostic. `manifest.py` `ENGINE_VERSION` → **`backtest-engine-v2-per-condition-timeframe`** (shifts the `execution_key` namespace; INF-04/INF-05).
- **Honest boundary** — item (ii) **>2-package** comparison (N-ary reference) and item (d) **non-MA/RSI reference keys** are still deferred. Only the reference PACKAGE is resampled (not a bounded `reference` series).
- **Tests (+14)** — `tests/unit/test_backtest_per_condition_timeframe.py` (+6: RHS held within a forming reference candle, base-TF contrast, byte-identical when span `None`, fail-closed without timestamps, coarser-reference cross timing, full `BlockEvaluator`→`ConditionEvaluator` plumbing) + `tests/integration/test_per_condition_timeframe_resolution.py` (+8: coarser/equal/finer/no-package/unknown-base/coarser-than-HTF-block/finer-than-HTF-block resolution branches + an e2e 2h-reference cross driving a real long entry over 1h base bars).
- **Verify:** 953 green on an isolated DB; ruff / format / mypy clean; **no migration**. Reviewer agent (`ecc:code-reviewer`): **APPROVE, 0 CRITICAL/HIGH** (look-ahead/repaint, byte-identical-default, timestamp-plumbing, fail-closed paths all verified).

## Post-V1 — Backtest Engine N-ary reference chain (INF-12, Slice C follow-up ii) ✅ landed (PR #57)

A nested condition's **RHS reference** extends from a single package (the two-package #53/#56 form) to an **ordered chain of >2 separately-pinned indicator packages**: `source [cmp] ref0 [cmp] ref1 ...` — the classic **MA fan** (`fast > slow > slowest` = uptrend; ascending mirror for downtrends). The single-reference path is **byte-identical** to #53/#56 (a one-leg chain reduces to the old check exactly). No migration (alembic head stays `0021_local_auth`). +17 tests → **970 total**. Run / manifest / result contracts unchanged.

- **Config** — `domain/strategy/config.py`: new `ReferenceLeg` model (`package_ref` + `timeframe` + `parameter_overrides`); `ConditionBlock.additional_reference_package_refs: list[ReferenceLeg] | None` (optional, JSONB, no migration; only meaningful with a primary `reference_package_ref`).
- **Compute (pure)** — `domain/backtest/indicators.py`: `ReferenceSeriesSpec(key, length, resample_seconds)`; `ConditionSpec` gains `extra_references`; new `_ReferenceSeries` (one inline reference indicator + its own **per-leg** coarser-TF resampling, advancing only on a completed reference candle — **no look-ahead**, a per-leg port of the (i) `_advance_reference` logic); module-level `_chain_ordered` (strict monotonic, `None` fails closed); `ConditionEvaluator` evaluates a chain over `source` + all RHS legs (`_ref_series` list, `_prev_ref_values` list, `_rhs_values` list). Warm-up on **ANY** leg fails the whole chain closed (LEVEL and CROSS).
- **Semantics** — `cond.above`/`crosses_above`: `source > ref0 > ref1 > ...` (source largest, descending); `cond.below`/`crosses_below`: the ascending mirror; a cross fires when the fan aligns **THIS bar** (`chain_now AND NOT chain_prev`). `cond.between` (RANGE) still ignores the RHS chain.
- **Resolution** — `application/queries/indicator_plan.py`: `_resolve_reference_package` returns a **5-tuple** (adds `extras`); new async `_resolve_additional_references` (each leg → its own `DIRECTIONAL_KEYS` series, own timeframe resolved against the block, own look-back). Fail-closed reasons: `condition_additional_reference_without_primary`, `condition_additional_reference_unresolved:<i>`, `condition_additional_reference_no_series:<i>`; a leg on a `cond.between` RANGE is rejected via the pre-existing `condition_reference_package_on_range`.
- **Engine / manifest** — `engine.py` adds a `nary_reference_conditions` diagnostic. `manifest.py` `ENGINE_VERSION` → **`backtest-engine-v2-nary-reference`** (execution_key namespace shift; INF-04/INF-05).
- **Honest boundary** — item (d) **non-MA/RSI reference keys** (`ta.atr`/`ta.vwap`) still deferred; only `DIRECTIONAL_KEYS` (MA/RSI) packages are computable as chain legs. `formula_based`/Kelly still `unresolved`.
- **Tests (+17)** — `tests/unit/test_backtest_nary_reference.py` (+7: descending/ascending fan LEVEL, crosses_above/below EDGE alignment, N-ary strictly stronger than a single reference, warm-up fail-closed, condition-only three-MA fan long) + `tests/integration/test_nary_reference_resolution.py` (+10: chain resolves primary + 2 legs; fail-closed for additional-without-primary / missing revision / non-directional leg / finer-than-block leg / `additional` on a RANGE; coarser per-leg resample; per-leg length override; `use_package_default_tf` leg; e2e 3-MA fan cross → one long entry + `nary_reference_conditions` diagnostic).
- **Verify:** 970 green on an isolated DB; ruff / format / mypy clean; **no migration**. Reviewer agent (`code-reviewer`): **APPROVE, 0 CRITICAL/HIGH** (byte-identity exhaustively verified, warm-up fail-closed, no per-leg look-ahead, fail-closed resolution all confirmed).

## post-V1 — VWAP directional key (d) landed (PR #58, code `d27b2bb`)

**`ta.vwap` is now a `DIRECTIONAL_KEYS` member** (INF-12 Slice C follow-up (d)): a rolling,
volume-weighted price line whose **price/VWAP cross** is a native directional trigger (same
shape as an MA cross), usable as a **native trigger**, a **condition reference-package RHS**,
and an **N-ary reference chain leg**. `ta.atr` stays recognized-but-non-directional (a
volatility band width, no directional cross) — the honest boundary preserved. **No migration**
(`ta.vwap` already seeded; bars already carry the canonical `volume` column, dropped in the
engine's `_normalize` before this slice). **+17 tests → 987** (12 unit / 5 integration); review
outcome n/a (user opted to skip review after 987-green + ruff/format/mypy clean); no deferred
regressions. Reuse anchors:
- **`domain/backtest/indicators.py`** — `DIRECTIONAL_KEYS += {ta.vwap}`, `VOLUME_WEIGHTED_KEYS`,
  `NON_DIRECTIONAL_KEYS = {ta.atr}`. New `_Vwap` (bounded-memory rolling window over `length`
  candles; typical `(H+L+C)/3` weighted by volume; warm-up over `length`; **zero-volume window
  fails closed** — no divide-by-zero, no phantom crosses). `_feed_indicator` dispatch routes
  volume only to a `_Vwap` (MA/RSI **byte-identical**). Volume threaded through
  `BlockEvaluator._advance`, `ConditionEvaluator.update`, `_ReferenceSeries.advance` (reference-leg
  aggregation sums volume across a coarser candle for a resampled VWAP leg; inert for MA/RSI).
- **`domain/backtest/engine.py`** — `_Bar.volume` + `_volume()` (optional canonical OHLCV column →
  non-negative Decimal; absent/negative → 0, non-blocking); evaluators receive `volume`;
  `vwap_blocks` diagnostic.
- **`domain/backtest/manifest.py`** — `ENGINE_VERSION = "backtest-engine-v2-vwap-directional"`
  (execution_key ns shift; INF-04/INF-05).
- **`application/queries/indicator_plan.py`** — docstrings only; `ta.vwap` resolves directional via
  the existing `DIRECTIONAL_KEYS` checks (block + reference package + each N-ary leg). No logic change.
- **Tests (+17):** `tests/unit/test_backtest_vwap.py` (+12), `tests/integration/test_vwap_resolution.py` (+5).

## post-V1 — formula_based Kelly criterion sizing landed (PR #60) + non-finite fail-closed fix (PR #61, code `3a92e7d`)

**`formula_based` (Kelly criterion) position sizing is now HONORED** (INF-12 Slice C
follow-up; closes the last sizing gap left `unresolved` after (a) `risk_based`). A
`formula_based_sizing` request carrying a `kelly_criterion` formula config computes a
fractional-Kelly capital fraction and sizes the position from usable equity; **every other
`formula_based` shape** (notably `custom_formula`) still falls back to notional + a
non-blocking `position_sizing_method_unsupported` diagnostic. **No migration** (config-only;
the sizing sub-config already existed on `StrategyConfig`). **+12 tests → 999** (9 Kelly feat
`PR #60` / 3 non-finite fix `PR #61`). Reuse anchors:
- **`domain/backtest/engine.py`**
  - `_decimal_param(params, key)` — best-effort parse of a free-form `formula_params` value
    to `Decimal`; **absent / parse-failure / NON-FINITE (`NaN`/`±Inf`, guarded by
    `Decimal.is_finite()`) → `None`** (fail-closed).
  - `_kelly_capital_fraction(sizing)` — `f* = kelly_fraction · (W − (1 − W) / R)` with a lower
    clamp at `0`. An **absent** `kelly_fraction` defaults to **full Kelly (`1`)**; a
    **present-but-garbage / out-of-range** `kelly_fraction`, a non-`kelly_criterion` shape
    (`custom_formula`), or a missing / non-finite `W` (`win_probability`) / `R`
    (`payoff_ratio`) → `None` (unresolved → notional fallback).
  - `_position_size` Kelly branch — `size = usable_equity · f* / entry_price` (entry-price
    **dependent**, unlike `risk_based`'s stop-distance sizing), quantized to `_QTY`.
  - `_sizing_is_honored` returns `True` for a valid Kelly config (so
    `position_sizing_method_unsupported` fires only for the still-unsupported shapes).
- **`domain/backtest/manifest.py`** — `ENGINE_VERSION = "backtest-engine-v2-kelly-sizing"`
  (execution_key namespace shift; INF-04/INF-05 — a stale notional result is not reused).
- **Review (PR #60):** 1 CONFIRMED defect — non-finite `formula_params` (`NaN`/`Inf`) reached
  `Decimal` arithmetic → an `InvalidOperation` **crash**, and an `Inf` `payoff_ratio` made
  `(1 − W) / R → 0` so `f*` **silently honored** a bogus position. **Fixed in PR #61** by the
  `Decimal.is_finite()` guard in `_decimal_param` (non-finite → `None` → fail-closed); +3
  regression tests. (Note: #60 was self-merged before the fix commit landed on the branch, so
  the fix shipped as a separate PR #61 — both are on `main`.)
- **Honest boundary:** **adaptive / rolling Kelly** (estimating `W`/`R` from the backtest
  itself) is deferred — path-dependent and look-ahead-prone; **`custom_formula` is
  unsupported** (no safe expression eval). Both stay honest `unresolved` → notional fallback.

## post-V1 — position_size_limits (min/max cap) wiring landed (PR #63, code `5ef5525`, merge `97b10b8`)

**`position_size_limits` (min/max position caps) are now HONORED across EVERY sizing method**
(INF-12 Slice C follow-up; closes the last **TIER-1 backend** item). `PositionSizeLimits` was
defined on the sizing sub-config (`domain/strategy/config.py:599`) but **silently ignored** in
`engine._position_size` — a latent bug where a configured cap never constrained the computed
size on ANY path. The fix clamps the size at a single sizing boundary, so **base / risk_based /
Kelly / notional-fallback** are all capped uniformly. **No migration** (config-only, JSONB —
`PositionSizeLimits` unchanged). **+15 tests → 1015** (7 `_clamp_to_limits` unit / 6 per-method
`_position_size` / 1 e2e / 1 ENGINE_VERSION ns). Review APPROVE 0 CRITICAL/HIGH. Reuse anchors:
- **`domain/backtest/engine.py`**
  - **NEW `_clamp_to_limits(size, limits)`** — the clamp primitive. **Fail-closed edges:**
    `limits is None` OR `size <= _ZERO` → **no-op** (`0` is the "do not open" sentinel from
    `_raw_position_size` on bust equity / non-positive entry; a `min` cap must NOT resurrect it
    into a live position, nor lift a stray negative positive); a misconfigured `min > max`
    window → `_ZERO` (no size satisfies both — fail closed rather than honour one bound and
    violate the other); else pull the size **DOWN to `max`**, then **UP to `min`**, then
    `max(size, _ZERO)` (also neutralises a nonsensical negative cap). Caps are in the **same
    UNITS as the size** (contracts/coins), applied **unquantized** — symmetric with the
    `base_position_size` branch.
  - The old `_position_size` body was **renamed `_raw_position_size`** (logic unchanged: base /
    risk_based / Kelly / notional, each already clamped to non-negative equity).
  - **`_position_size` is now a thin wrapper** =
    `_clamp_to_limits(_raw_position_size(config, entry_price, equity), config.position_sizing.position_size_limits)`.
    A missing limits subtree → **byte-identical** to the pre-wiring engine. **Single call site**
    (`_open`, ~L475) → every sizing path is clamped automatically, no per-branch wiring.
  - `TYPE_CHECKING` import += `PositionSizeLimits`.
  - `run_engine` diagnostics += `"position_size_limits_active": config.position_sizing.position_size_limits is not None` (bool).
- **`domain/backtest/manifest.py`** — `ENGINE_VERSION = "backtest-engine-v2-position-size-limits"`
  (was `-kelly-sizing`; execution_key namespace shift — INF-04/INF-05, a stale **UNCLAMPED**
  result is never reused).
- **`domain/strategy/config.py:599`** — `PositionSizeLimits(min_position_size / max_position_size: Decimal | None)`
  — **UNCHANGED**, no migration (config-only, JSONB).
- **`tests/unit/test_backtest_engine.py`** — `_config` fixture gains `min_size` / `max_size`
  kwargs; `_clamp_to_limits` + `PositionSizeLimits` imported; +15 tests.
- **Honest boundary:** cap unit = the size unit (contracts/coins), unquantized (symmetric with
  the `base` branch). If `base_position_size` is given a NEGATIVE explicit size the clamp is
  exempt (the `size <= _ZERO` guard) — pre-existing behaviour, out of scope for this slice.

## Post-V1 — Frontend real-auth login/signup/logout (TIER 2, frontend slice 1) ✅ landed (PR #65, awaiting user merge)

**First TIER 2 (frontend) slice.** The backend already shipped real local auth
(`/v1/auth/signup|login|logout`, opaque Bearer sessions — Auth/IdP PR #38 + M1 §4), but the
web shell (`frontend/`, Vite 8 + React 18 + react-router 6 + @tanstack/react-query 5) only ever
sent the dev `X-Actor-Id` header. This slice connects the shell to that backend so humans get a
real Bearer session. **Frontend-only — NO backend change, NO migration; backend test base stays
1015.** CI: **Frontend + Docker checks green**; backend check re-runs unchanged (frontend-only
diff). Reuse anchors (exact symbols):
- **`frontend/src/lib/session.ts`** *(new)* — external session store: `getSessionToken()` (raw
  string fast-path read by the API client each request), `getStoredUser()`, `setSession({token,
  user, expiresAt})`, `clearSession()`, `subscribe(listener)`. Two `localStorage` keys
  (`entropia.sessionToken` + `entropia.session` JSON meta). Framework-agnostic (no React import)
  so it composes with `useSyncExternalStore`.
- **`frontend/src/lib/apiClient.ts`** — `apiRequest` now attaches `Authorization: Bearer <token>`
  when `getSessionToken()` is non-null, **in addition to** the existing `X-Actor-Id`. Both headers
  are sent safely: the server honours only the one its `AUTH_MODE` trusts (`session` → Bearer
  authoritative, bare `X-Actor-Id` ignored; `dev` → `X-Actor-Id`, Bearer ignored — per
  `backend .../apps/api/deps.py`), so neither header can spoof the other.
- **`frontend/src/lib/auth.ts`** *(new)* — react-query mutation hooks: `useLogin` (POST
  `/auth/login` → `setSession`), `useSignup` (POST `/auth/signup` then **auto-login**),
  `useLogout` (best-effort POST `/auth/logout`, **always** `clearSession()` — a failed/expired
  revoke never strands the UI), `useSessionToken()` (`useSyncExternalStore` over the store). Every
  success `queryClient.invalidateQueries()` so `/me` + role-gated nav refetch under the new principal.
- **`frontend/src/pages/Login.tsx`** *(new)* — standalone `/login` page (no app shell),
  `react-hook-form`, login/signup toggle (signup reveals optional display-name/email). Errors
  surface the backend canonical envelope verbatim (`ApiError` → `${code}: ${message}`); the client
  never invents auth messages. Required-field validation blocks submit client-side.
- **`frontend/src/app/Layout.tsx`** — new `AuthControl`: a **Log in** link when anonymous, the
  signed-in user + **Log out** button when a session token is present; `DevActorControl` is hidden
  while a real session is active (`token ? null : <DevActorControl/>`).
- **`frontend/src/App.tsx`** — standalone `/login` `<Route>` outside the `<Layout>` element route.
- **`frontend/src/lib/types.ts`** — `AuthUser` / `SignUpResponse` (= `AuthUser`) / `LoginResponse`
  ({token, session_id, expires_at, user}) envelopes mirroring `routes/auth.py`.
- **`frontend/src/styles/global.css`** — new `.btn` / `.btn-primary` / `.btn-ghost` + `.auth-*`
  classes (themed, dark/light).
- **`frontend/src/test/auth.test.tsx`** *(new)* — 6 vitest: session round-trip, subscribe fires on
  set/clear + unsubscribe, Bearer header present-when-token / absent-when-none, login stores the
  returned token + hits `/auth/login`, empty-field validation blocks the request. **Frontend total
  9/9** (3 baseline nav + 6 new); typecheck + lint clean; production build green.
- **Honest boundary:** no route guard forcing anonymous → `/login` (dev mode intentionally allows
  anonymous browsing; routes gate access server-side). First-Admin provisioning still absent
  upstream — signup always yields the baseline role. The other two TIER 2 candidates (SSE
  live-invalidation of the `sse.ts` stub; `/v1/metrics` Prometheus-text dashboard) are **not** in
  this slice.

## Post-V1 — Frontend SSE live-invalidation (TIER 2, frontend slice 2) ✅ landed (PR #67, awaiting user merge)

**Second TIER 2 (frontend) slice.** The backend already fans the transactional outbox out over
`GET /events` as typed SSE frames (Stage 8b, `apps/api/sse.py`); the web shell opened the
connection but only listened for `heartbeat` — `connectEvents`' `queryClient` param was an unused
Stage-1 TODO, so no domain event refreshed the cache. This slice fills the
`frontend/src/lib/sse.ts` stub so each taxonomy event invalidates the matching react-query keys.
**Frontend-only — NO backend change, NO migration; backend test base stays 1015.** CI: **Frontend
+ Docker checks green**; backend check re-runs unchanged (frontend-only diff). Reuse anchors
(exact symbols):
- **`frontend/src/lib/sse.ts`** — `connectEvents(queryClient, onStatus?)` signature and `SseStatus`
  UNCHANGED (the `Layout.tsx` call-site is untouched). New exports:
  - **`SseEventName`** — the backend taxonomy union (`backtest.run.updated` / `job.updated` /
    `agent.task.updated` / `audit.event.created` / `resource.changed`); must stay in lockstep with
    `apps/api/sse.py::sse_event_name`.
  - **`EVENT_QUERY_KEYS: Record<SseEventName, readonly QueryKey[]>`** — the event→key-prefix map:
    `backtest.run.updated → [["backtests"]]`, `job.updated → [["jobs"]]`,
    `agent.task.updated → [["agent-tasks"]]`, `audit.event.created → [["audit"]]`,
    `resource.changed → []` (empty list = catch-all → full `invalidateQueries()`). react-query
    matches by prefix, so `["backtests"]` also covers `["backtests", runId, …]`.
  - **`SSE_EVENT_NAMES`** — `Object.keys(EVENT_QUERY_KEYS)` for iteration/tests.
  - Private `invalidateForEvent(qc, name)` — empty list → full refresh, else per-prefix
    `invalidateQueries({queryKey})`. Handlers are added per event name and **detached on dispose**
    (symmetric add/remove) before `source.close()`.
  - **Reconnect self-heal (INF-11):** a `hasOpened` flag makes the FIRST `open` a no-op but a
    SUBSEQUENT `open` (reconnect after a drop) trigger a full `invalidateQueries()`, so no view is
    left stale across a connection gap.
- **`frontend/src/test/sse.test.ts`** *(new)* — 7 vitest backed by an in-memory `EventSource`
  double (`vi.stubGlobal`): subscribes to every taxonomy event + heartbeat; each specialized event
  → its `{queryKey}` prefix (exact call count); `resource.changed` → single full refresh (no key);
  heartbeat → no cache effect; first-open no-op + reconnect full-refresh; `connecting→open` status;
  dispose closes source + detaches all listeners. **Frontend total 16/16** (9 prior + 7 new);
  typecheck + lint clean; production build green.
- **Honest boundary:** no live page binds these keys YET — Stage 5/6 `RUN` / `Results History` /
  `Arrange Metrics` / `Analysis Lab` screens are still placeholders, so invalidation is a harmless
  no-op today; the **visible payoff arrives with those pages**, and `EVENT_QUERY_KEYS` is their
  forward contract. The remaining TIER 2 candidate (`/v1/metrics` Prometheus-text dashboard) is
  **not** in this slice.

## Post-V1 — Frontend /v1/metrics dashboard (TIER 2, frontend slice 3) ✅ landed (PR #69, merged → main `ee76b24`)

**Third TIER 2 (frontend) slice.** The backend already exposes `GET /v1/metrics` as a Prometheus text
exposition (Stage 8b, `apps/api/routes/metrics.py`, `PlainTextResponse`) — golden signals from the
in-process registry plus scrape-time operational gauges — but nothing consumed it. This slice adds a
read-only ops dashboard. **Frontend-only — NO backend change, NO migration; backend test base stays
1015.** CI: **Frontend + Docker checks green**; backend check re-runs unchanged (frontend-only diff).
Reuse anchors (exact symbols):
- **`frontend/src/lib/metrics.ts`** *(new)* — dependency-free Prometheus exposition parser
  `parsePrometheus(text) → ParsedMetrics` (handles `# TYPE`/`# HELP`, labeled + scalar samples,
  histogram `_bucket`/`_sum`/`_count` grouped to the base family via `ownerFamily`, `+Inf`/`-Inf`/`NaN`
  values, backslash/quote label escapes, freeform notes) + `summarizeMetrics(parsed) → MetricsSummary`:
  the four golden signals (`requestsTotal` traffic, `serverErrors` 5xx, `clientErrors` 4xx, `inFlight`
  saturation, `avgLatencyMs` = histogram `sum/count`), sorted `jobsDepth` rows + total,
  `outboxLagSeconds`, `leaseAgeSeconds`, `degraded` (detects the backend's "operational gauges
  unavailable" DB-down note), `familyCount`; `parseMetricsSummary(text)` convenience. Metric names
  consumed: `entropia_http_requests_total`, `entropia_http_request_duration_seconds_{bucket,sum,count}`,
  `entropia_http_requests_in_flight`, `entropia_jobs_depth{queue,status}`, `entropia_outbox_lag_seconds`,
  `entropia_job_lease_age_seconds`. (Backend emits `# TYPE` but not `# HELP`.)
- **`frontend/src/lib/apiClient.ts`** — new `apiGetText` / `api.getText`: a raw-text GET for non-JSON
  endpoints (metrics is `text/plain`, not the JSON envelope). Mirrors `apiRequest`'s auth headers
  (`Authorization: Bearer` + `X-Actor-Id`); `textError` falls back to the raw body when a non-envelope
  error is returned. Existing `apiRequest` / `api.{get,post,patch,del}` UNCHANGED.
- **`frontend/src/lib/hooks.ts`** — new `useMetrics()`: react-query `useQuery` on `["metrics"]`,
  `refetchInterval` 5s, `queryFn` = `parseMetricsSummary(await api.getText("/metrics"))`. The
  `["metrics"]` key is also swept by the SSE `resource.changed` catch-all.
- **`frontend/src/pages/Metrics.tsx`** *(new)* — the dashboard: golden-signal `Stat` tiles, status-class
  `StatusBadge`s, operational-gauges `kv` list, jobs-depth `.metrics-table`, a degraded banner, and a
  live/updating indicator. Reuses `Loading`/`ErrorState`/`StatusBadge` + `.card`/`.kv`/`.page-title`;
  `formatCount`/`formatMs`/`formatSeconds` render non-finite/absent values as an em-dash.
- **`frontend/src/app/nav.ts` + `App.tsx`** — new **adminOnly** nav item **System Metrics** at
  `/panel/metrics` (stage 8, under Agent & Admin); `ALL_NAV_ITEMS` 22 → 23 (`test/nav.test.tsx`
  updated). `App.tsx` adds an explicit `/panel/metrics` route (real `Metrics` page) and filters that
  path out of the `Placeholder` auto-map. `global.css`: `.metrics-table`.
- **`frontend/src/test/metrics.test.ts`** *(new, 10)* + **`test/metricsPage.test.tsx`** *(new, 3)* —
  parser/summary unit (healthy/degraded/empty scrapes, histogram avg 20ms, label escapes via
  `String.raw`, malformed-line tolerance) + component render via a `vi.stubGlobal("fetch")` double.
  **Frontend total 29/29** (16 prior + 13 new); typecheck + lint clean; production build green.
- **Honest boundary:** metrics has **no SSE event**, so the dashboard **polls every 5s** rather than
  SSE live-invalidating (`["metrics"]` still swept by `resource.changed`). The route is reachable by
  URL — the `/v1/metrics` scrape endpoint is unauthenticated by design — while the **nav item** is
  admin-gated (consistent with `/panel`, `/trash`). `# HELP` isn't shown (the backend omits it).

## Post-V1 — Frontend live-data backtest pages (TIER 2, frontend slice 4) ✅ landed (PR #72, merged → main `c322588`)

**Fourth TIER 2 (frontend) slice — the FIRST live pages on the SSE forward contract.** The Stage 5
backtest screens (`/backtest/run`, `/backtest/history`) were Stage-0 placeholders even though the
backend has served the full surface since Stage 5a/5b, and PR #67 already mapped
`backtest.run.updated → ["backtests"]` with no page bound to it. This slice binds RUN & Backtest
Results + Results History to real queries — the SSE live-invalidation payoff is now visible.
**Frontend-only — NO backend change, NO migration; backend test base stays 1015.** CI 3/3 green.
Reuse anchors (exact symbols):
- **`frontend/src/lib/backtest.ts`** *(new)* — wire types mirroring the backend projections verbatim
  (`DefaultMainboard`, `BacktestRunAdmission`, `BacktestRun`, `BacktestResultDetail`/`MetricValue`/
  `ManifestExcerpt`, `HistoryRow`/`HistoryPage`); `HISTORY_SORTS` (6 canonical `HistorySort` wire
  values + V18 labels), `KEY_METRIC_COLUMNS` (KEY_METRIC_KEYS order), `TERMINAL_RUN_STATES`;
  `formatMetricValue` (signed_percent/percent/decimal2/integer; a null value renders its availability
  label, NEVER 0 — L4) + locale-free `formatUtc`; hooks `useDefaultMainboard` (`["mainboard","default"]`),
  `useBacktestRun` (`["backtests","run",id]`, poll fallback stops on terminal state — SSE primary,
  INF-11), `useBacktestResult` (`["backtests","result",id]`, immutable), `useResultsHistory`
  (`["backtests","history",sort,cursor]`, keyset cursor, `placeholderData` keeps the previous page);
  202 mutations `useRequestBacktestRun` / `useRetryBacktestRun` (both invalidate `["backtests"]`).
  ALL path params `encodeURIComponent`'d (review fix — an un-encoded `?result=` could URL-normalize
  onto a different API GET endpoint).
- **`frontend/src/pages/BacktestRun.tsx`** *(new)* — two modes: `?result=<id>` immutable deep-link
  (hydrated ONLY from result_id, doc 15 §8.5 — where History "View" lands) and the workbench
  (composition card from `GET /mainboards/default` → Request Backtest Run 202 admission → run id in
  `?run=` so a refresh keeps tracking the durable row, doc 15 §4); failure_code/message verbatim +
  Retry swaps tracking onto the NEW run id; admission `warning_count` badge.
- **`frontend/src/pages/ResultsHistory.tsx` + `components/ResultDetail.tsx`** *(new)* — server-sorted
  keyset index (sort select resets the cursor stack; Prev/Next disabled while fetching), key-metric
  digest cells, View → `/backtest/run?result=<id>`; `ResultDetail` renders summary kv + metrics table
  (value + availability) + manifest excerpt + artifact counts. The client never re-orders rows.
- **`App.tsx`** — `REAL_PATHS` set (`/`, `/panel/metrics`, `/backtest/run`, `/backtest/history`)
  replaces the inline placeholder filter; two real routes. `nav.ts` UNCHANGED (23 items).
- **`test/backtestRun.test.tsx`** *(new, 3)* + **`test/resultsHistory.test.tsx`** *(new, 4)* + shared
  route-aware fetch double **`test/helpers/apiStub.ts`** ("<METHOD> <path fragment>" keyed) —
  **frontend 36/36** (29 prior + 7 new); typecheck + lint clean; build green.
- **Honest boundary:** Arrange Metrics (`/backtest/metrics`) + Analysis Lab (`/analysis-lab`) stay
  placeholders — `["jobs"]`/`["agent-tasks"]`/`["audit"]` keys still have no bound page; history
  compare + soft-delete affordances deferred with them.

## Post-V1 — Frontend live-data Arrange Metrics + Analysis Lab pages (TIER 2, frontend slice 5) ✅ landed (PR #74, merged → main `4969825`)

**Fifth TIER 2 (frontend) slice — the last two placeholders with a fully-landed backend surface become
live pages, and the SECOND SSE forward-contract key gets its first bound pages.** Arrange Metrics
(`/backtest/metrics`, Stage 5c, doc 17) and Analysis Lab (`/analysis-lab`, Stage 6a, doc 18) were
Stage-0 placeholders; every Analysis Lab query key is prefixed `["agent-tasks"]`, so the PR #67
`agent.task.updated` invalidation now sweeps live pages. **Frontend-only — NO backend change, NO
migration; backend test base stays 1015.** CI 3/3 green. Reuse anchors (exact symbols):
- **`frontend/src/lib/metricProfile.ts`** *(new)* — wire types mirroring
  `application/queries/metric_profile.py` verbatim (`MetricDefinition`/`MetricRegistry`,
  `ResolvedMetricProfile` incl. `editable_profile_id` — `"system_default"` until the first Apply
  forks a personal root, doc 17 §8.1 — `MetricProfileRevision` incl. the server-derived transition
  `reason`, `ApplyMetricProfileInput`); hooks `useMetricDefinitions` (`["metric-definitions"]`,
  5m staleTime — the registry is versioned server config) + `useResolvedMetricProfile`
  (`["metric-profile","resolved"]`); `useApplyMetricProfile` — Apply / Apply & Lock / pure-Unlock are
  ALL the same append `POST /metric-profiles/{id}/revisions` with the `expected_profile_revision_id`
  OCC guard (409 stale/locked surfaced verbatim); invalidates `["metric-profile"]`.
  PRESENTATION-ONLY (CR-07): never recomputes a metric, never touches a Result.
- **`frontend/src/pages/ArrangeMetrics.tsx`** *(new)* — registry table with the resolved selection
  layered on top: non-selectable (future/experimental) metrics rendered but never checkable; a locked
  profile disables edits and offers only the PURE Unlock (the server's own selection +
  `is_locked=false`, doc 17 §7); the draft re-seeds from the server head on every revision move;
  Apply disabled on an empty selection (server `min_length=1`); success echoes `revision_no` + `reason`.
- **`frontend/src/lib/agentLab.ts`** *(new)* — wire types mirroring
  `application/queries/agent_workspace.py` (`AgentRuntime`/`AgentTaskCard`/`AgentOverview`/
  `AgentTaskDetail` with checkpoints + related directives/`HypothesisCard` + pages) and the command
  admissions (`DirectiveAdmission`, `LabMessageResponse`, `RuntimeControlAccepted`); ALL query keys
  under the `["agent-tasks"]` SSE prefix: `useAgentOverview` (15s loss-tolerant poll fallback,
  INF-11 — SSE primary), `useAgentTasks` (keyset, `placeholderData`), `useAgentTask` detail,
  `useHypotheses`; 202 mutations `useQueueDirective` (`DIRECTIVE_PRIORITIES = normal|high` —
  `autonomous` is Coordinator-only, never human-selectable, doc 18 §9.1), `useSendLabMessage`, and
  `usePauseRuntime`/`useResumeRuntime`/`useStopRun` carrying the runtime `row_version` as an
  `If-Match` OCC token (`postWithIfMatch`); all invalidate `["agent-tasks"]`.
- **`frontend/src/pages/AnalysisLab.tsx`** *(new)* — `RuntimeCard` (status/mode/pending_control
  badges; Pause-at-next-safe-checkpoint / Resume / Stop-active-run — stop passes the active TASK id,
  which IS the run id in this domain: backend `stop_run` does `get_task(session, run_id)`),
  `QueueCard` (counts + overview cards + Detail drill-down), `TaskDetailCard` (checkpoints count,
  waiting/failure reasons, related directives), `DirectiveCard` (directive + discussion-message
  composers; `delivery_policy` echo; assistant response rendered), `HypothesesCard` (output board).
  Server policy is authority: a non-Admin/Supervisor sees the 403 envelope verbatim via `ErrorState`.
- **`App.tsx`** — `REAL_PATHS` 4 → 6 (`/backtest/metrics`, `/analysis-lab`); two real routes.
  `nav.ts` UNCHANGED (23 items).
- **`test/arrangeMetrics.test.tsx`** *(new, 4)* + **`test/analysisLab.test.tsx`** *(new, 5)* —
  `apiStub.ts` reuse; mutation payload + `If-Match` assertions, `["agent-tasks"]` invalidation
  refetch proof, error states — **frontend 45/45** (36 prior + 9 new); typecheck + lint clean;
  build green.
- **Honest boundaries:** no dedicated SSE event for metric-profile changes (those keys are swept only
  by the `resource.changed` full refresh; the Apply mutation invalidates `["metric-profile"]` for
  same-tab freshness) · the lab consumes the app-level `/events` stream — the role-gated
  `GET /agent-events/stream` (heartbeat/ready only today) is NOT wired as a second EventSource ·
  task/hypothesis keyset pagination beyond the first page + the `GET /agent-tasks?status&cursor`
  filter UI deferred · `GET /backtest-results/{result_id}/metrics` (profile-hydrated Result view) NOT
  consumed yet — `ResultDetail` still renders the raw persisted rows; binding it is the natural
  follow-up now the profile editor exists · `["audit"]` still has no bound page (Panel/Logs) and
  `["jobs"]` has NO backend list surface at all (job state is only visible through run projections +
  the /v1/metrics jobs-depth gauge) · history compare/soft-delete affordances still deferred.

## Post-V1 — first-Admin bootstrap provisioning (TIER 2, backend slice) ✅ landed (PR #76, merged → main `1771f14`)

**First TIER 2 backend slice — closes the PR #38 honest boundary ("signup always gets the baseline
User role; first-Admin provisioning absent upstream"): a fresh deployment now has an explicit,
operator-opt-in path to its first Admin.** BACKEND-ONLY — frontend unchanged (45/45 stays); NO
migration, NO new tables — alembic head stays `0021_local_auth`; `ENGINE_VERSION` stays
`backtest-engine-v2-position-size-limits`. CI green; review APPROVE 0 CRITICAL/HIGH. Backend tests
**1015 → 1028** (+13). Reuse anchors (exact symbols):
- **`config/settings.py`** — NEW `bootstrap_admin_email` field (env `ENTROPIA_BOOTSTRAP_ADMIN_EMAIL`,
  default `""` = disabled → ZERO behavior change unless the operator opts in).
- **`application/commands/auth.py`** — NEW `bootstrap_admin_matches` helper (case- and
  whitespace-normalized email match) + a bootstrap branch in `sign_up`: a matching signup is
  provisioned as **Admin ONLY while no active Admin exists** (fail-closed otherwise → baseline
  role). Race safety: the same-tx advisory lock already used by the last-admin demote path
  (`identity_repo.lock_admin_count`) serializes the count+decide section against concurrent
  demotions AND concurrent bootstraps; `unique(human_users.email)` additionally blocks a second
  qualifying signup. Provisioning emits a dedicated `user.admin_bootstrapped` audit event +
  `admin_bootstrapped` outbox event in the SAME transaction (house `_audit_and_outbox` pattern).
- **`apps/api/routes/auth.py`** — passes `settings.bootstrap_admin_email` through, server-side
  only. The route schema has NO role field → escalation via the client stays structurally
  impossible.
- **Tests** — NEW `tests/unit/test_auth_bootstrap_unit.py` +
  `tests/integration/test_auth_bootstrap_admin.py` (+13): env unset → baseline (no events); match +
  no admin → Admin + audit/outbox; active Admin exists → fail-closed baseline; non-matching/missing
  email → baseline; case/whitespace normalization; settings env read; route pass-through. **1028
  green** on an isolated DB; ruff + format + mypy (299 files) clean.
- **Honest boundaries:** backend MECHANISM only — no provisioning dashboard yet (a later frontend
  slice) · bootstrap applies at signup time only; it does NOT retro-promote an existing account
  (operator re-creates or uses a future admin tool).

## Post-V1 — Frontend live-data Panel / Management / Logs page (TIER 2, frontend slice 6) ✅ landed (PR #78, merged → main `2a8de9e`)

**Sixth TIER 2 (frontend) slice — the `/panel` placeholder becomes the real Panel / Management /
Logs page, and the LAST bindable SSE forward-contract key `["audit"]` gets its first bound page.**
Panel / Management / Logs (Stage 6b, doc 19) was a Stage-0 placeholder; its whole backend surface
(`routes/admin_panel.py` `/admin/users` + role PATCH + `/admin/system-actors` + `/admin/role-matrix`
+ `/admin/logs` and `routes/audit.py` `/audit-events`) had been landed since PR #26. With this
slice `audit.event.created` (PR #67 map) now sweeps a live page. **Frontend-only — NO backend
change, NO migration; backend test base stays 1028.** CI green; review 0 CRITICAL/HIGH. Reuse
anchors (exact symbols):
- **`frontend/src/lib/adminPanel.ts`** *(new)* — Management reads under the `["admin"]` prefix:
  `useRegisteredUsers` (keyset cursor, `placeholderData`), `useSystemActors`, `useRoleMatrix`
  (5m staleTime — versioned policy config). Logs/Audit reads under the `["audit"]` SSE prefix:
  `useAdminLogs` (filters `family`/`severity`/`actor_type`/`q`/`correlation_id` — an empty filter
  param is NEVER sent), `useLogEvent` detail, `useAuditEvents` raw stream. Mutation
  `useAssignRole` → `PATCH /admin/users/{id}/role` with the OCC guard
  `expected_head_revision_id = user.version` (a stale tab gets the 409 envelope verbatim); the
  offered role list comes from the server role-matrix ASSIGNABLE rows — never a hard-coded client
  list; invalidates `["admin"]` + `["audit"]` (the command emits an audit event).
  `LOG_FAMILIES`/`LOG_SEVERITIES`/`LOG_ACTOR_TYPES` mirror the server taxonomy verbatim.
- **`frontend/src/pages/Panel.tsx`** *(new)* — 5 cards: `UsersCard` (registry + inline role
  assignment), `SystemActorsCard`, `RoleMatrixCard` (grants grid + `policy_revision`), `LogsCard`
  (filtered list + detail drill-down + correlation-chain link), `AuditStreamCard` (raw append-only
  stream). Forward-only cursor-stack pagination throughout; a non-Admin sees the 403 envelope
  verbatim via `ErrorState`.
- **`App.tsx`** — `REAL_PATHS` 6 → 7 (`/panel`); `nav.ts` UNCHANGED (23 items).
- **`test/panel.test.tsx`** *(new, 6)* — `apiStub.ts` reuse; role-assignment OCC payload assertion,
  filter-param hygiene, 403 state — **frontend 51/51** (45 prior + 6 new); typecheck + lint clean;
  build green.
- **Honest boundaries:** `["jobs"]` has NO backend list surface — a PERMANENT honest boundary (job
  state is visible only through run projections + the /v1/metrics jobs-depth gauge) ·
  users/system-actors have no dedicated SSE event (their own mutations invalidate; the
  `resource.changed` full refresh sweeps the rest) · history compare/soft-delete + the
  profile-hydrated `GET /backtest-results/{id}/metrics` binding (ResultDetail rebind) still
  deferred — now the natural next follow-up.

## Post-V1 — Frontend history compare/soft-delete + profile-hydrated Result metrics (TIER 2, frontend slice 7) ✅ landed (PR #80, merged → main `8f57151`)

**Seventh TIER 2 (frontend) slice — the last two landed-but-unconsumed backtest surfaces get their
frontend binding: doc-16 §8.3 compare + §7 soft-delete on Results History, and the doc-17 §9.1
profile-hydrated `GET /backtest-results/{id}/metrics` projection replaces the raw persisted rows in
ResultDetail.** The backend surface (`routes/results_history.py` compare/delete +
`routes/metric_profile.py` result-metrics hydration) had been landed since Stage 5b/5c.
**Frontend-only — NO backend change, NO migration; backend test base stays 1028.** CI 3/3 green;
review 0 CRITICAL/HIGH. Reuse anchors (exact symbols):
- **`frontend/src/lib/backtest.ts`** — NEW wire types `CompareEntry`/`CompareField`/`CompareResponse`
  (`context.fields{a,b,differs}` + `context_differs`) and `ResultMetricsProfile`/`ResultMetricsView`;
  NEW hooks: `useCompareResults(pair)` — a READ over two immutable results, POST is only the
  transport for the id pair (`["backtests","compare",a,b]`, 5m staleTime, pick order preserved) —
  `useResultMetrics(resultId)` — keyed `["metric-profile","result-metrics",id]`, deliberately NOT
  `["backtests"]`: the Result rows are immutable and the caller's resolved profile is the only
  mutable input, so an Arrange Metrics Apply (which invalidates `["metric-profile"]`) sweeps this
  view; cross-tab profile changes ride the `resource.changed` full refresh — and
  `useSoftDeleteResult` (`POST /backtest-results/{id}/delete`; no OCC token — the history projection
  carries no row_version and the command is idempotent + owner/Admin-gated server-side; invalidates
  `["backtests"]` → the deletion-filtered index drops the row).
- **`frontend/src/pages/ResultsHistory.tsx`** — compare selection in pick order capped at two
  (checkbox gated by server `allowed_actions.compare`; columns A/B mirror pick order); `ComparePanel`
  renders the server context diff VERBATIM (per-field `differs` badge, object values as JSON, warn
  banner "informational only; neither result is ranked" — RH-09); two-step confirm Delete gated by
  `allowed_actions.soft_delete` (arm → confirm; deleting a compared row closes the panel); canonical
  error envelope verbatim.
- **`frontend/src/components/ResultDetail.tsx`** — the Metrics section now binds `useResultMetrics`:
  profile caption (personal/system default · locked · registry version); while the hydrated view
  loads — or if it fails — the raw persisted rows keep rendering with an honest note (L4 preserved:
  a missing metric is NEVER 0).
- **Tests** — NEW `test/historyActions.test.tsx` (4: wire body/pick order, selection cap,
  confirm-step delete + row disappearance, server-gated affordances) + `test/resultMetricsView.test.tsx`
  (3: rebind + L4 not_computed, system-default caption, persisted-rows fallback) → **frontend 58/58**
  (51 prior + 7 new); `backtestRun.test.tsx` deep-link test now stubs the metrics route FIRST
  (apiStub fragment matching is ordered — the detail fragment is a substring of the metrics URL) and
  asserts the hydrated caption; typecheck + lint clean; build green.
- **Honest boundaries:** compare is exactly two results (server `min/max_length=2` — no N-way UI) ·
  soft-delete sends no OCC token (no row_version in the history projection; server accepts optional) ·
  restore stays the Admin Trash flow (backend Stage 6c landed; the frontend Trash page is still a
  placeholder) · `["jobs"]` permanent boundary unchanged.

## Post-V1 — Frontend Future Dev capability registry page (TIER 2, frontend slice 8) ✅ landed (PR #82, merged → main `1411adc`)

**FRONTEND-ONLY** (backend `routes/capability.py` Stage 7b surface consumed unchanged; NO
migration, alembic head stays `0021_local_auth`; backend test base stays 1028). The
`/future-dev` placeholder becomes the real page: the server-side Capability Registry
(doc 22 — NEVER a frontend feature flag, §2/§15) rendered as-is, plus the Admin-only
lifecycle transition.

- **NEW `frontend/src/lib/capability.ts`** — wire types verbatim (`Capability` /
  `CapabilityDetail` incl. `dependency_snapshot` + provenance / `GraphicViewOverview` /
  `CapabilityTransitionResult`); doc-22 §9.1/§9.2 taxonomy MIRROR (`CAPABILITY_STATES`
  7 states, `ALLOWED_TRANSITIONS` legal edges, `ACTIVATION_GATES` 7 gates — select/checklist
  hydration only, the server re-validates every dispatch); `gateComplete` mirrors the server
  `_gate_complete` reading exactly; `buildGatesSnapshot` merges an Admin checklist WITHOUT
  clobbering server-side note objects or non-canonical keys; hooks under `["capabilities"]`
  (no dedicated SSE event — swept by `resource.changed`); `useTransitionCapability` — OCC
  `expected_registry_version` + REQUIRED fresh `Idempotency-Key` UUID per attempt,
  invalidates `["capabilities"]` + `["audit"]`.
- **NEW `frontend/src/pages/FutureDev.tsx`** — registry table (state badge / operational /
  registry v); detail card: gate checklist + last-transition provenance +
  `TransitionComposer` (targets = legal doc-22 edges only; reason REQUIRED; an untouched
  checklist OMITS `dependency_snapshot` so the server keeps its stored gate record; errors
  verbatim; mutation state owned by the CARD so the accepted message survives the
  registry_version-bump remount); read-only Graphic View overview (CR-09 — no fake
  operation/progress).
- **`App.tsx`** — `/future-dev` joins REAL_PATHS (7→8); `nav.ts` UNCHANGED (23 items).
- **Tests** — NEW `test/futureDev.test.tsx` (7; apiStub ORDERED routes — the detail fragment
  must precede the `/capabilities` list prefix it contains) + `test/capabilityLib.test.ts`
  (2 gate-merge unit) → **frontend 67/67**; typecheck + lint clean; build green.
- **Review:** 0 CRITICAL/HIGH; 3 MEDIUM/LOW self-review findings (success message lost on
  composer remount / non-canonical gate keys dropped by the merge / misleading terminal
  message for client-unknown states) — all fixed in-commit.
- **Honest boundary:** the gated operational POSTs (`/view-datasets/query`,
  `/analysis-artifacts`) stay UNWIRED — no V1 UI workflow exists for them; the server
  returns `CAPABILITY_NOT_ACTIVE` below Limited/Active regardless (CR-09/FD-02). Composer
  visibility is not role-gated (UI visibility is never authorization, doc 22 §3) — a
  non-Admin attempt renders the 403 envelope verbatim.

## Post-V1 — first-Admin provisioning dashboard + bootstrap-status endpoint (TIER 2, slice 9) ✅ landed (PR #84, merged → main `f7bf4a7`)

**BACKEND (2 files + 2 tests) + FRONTEND (2 new + 3 edits + 1 test)** — closes the PR #76 honest
boundary (backend bootstrap mechanism landed, no UI): the first-Admin flow was previously
observable only via the signup-response role; this adds the one missing read-only signal plus an
onboarding page. **NO migration; alembic head stays `0021_local_auth`; `ENGINE_VERSION` unchanged.**

- **Backend — `application/commands/auth.py`:** pure `bootstrap_is_configured(bootstrap_email)` +
  read-only async `bootstrap_status(session, *, bootstrap_admin_email) -> {bootstrap_configured,
  active_admin_exists}` (`active_admin_exists = await identity_repo.count_active_admins(session) > 0`).
  **Booleans only — no PII / no email echo**; a HINT, not a decision (the `sign_up` provisioning
  branch stays advisory-lock guarded — this endpoint never provisions). Both added to `__all__`.
- **Backend — `apps/api/routes/auth.py`:** `GET /auth/bootstrap-status` →
  `BootstrapStatusResponse(bootstrap_configured, active_admin_exists)`, an **anonymous entry
  surface** (like sign-up / login — the first Admin is not yet authenticated); passes
  `settings.bootstrap_admin_email` through server-side only (the response schema has no email field).
- **Backend tests** — `tests/unit/test_bootstrap_status_unit.py` (configured flag) +
  `tests/integration/test_bootstrap_status.py` (window open/closed against a real DB + route reads
  the setting): **+8 → backend 1028 → 1036**.
- **Frontend — NEW `lib/provisioning.ts`:** `BootstrapStatus` interface + `useBootstrapStatus()`
  (react-query `["auth"]` key, `api.get("/auth/bootstrap-status")`; no dedicated SSE event → swept
  by `resource.changed`).
- **Frontend — NEW `pages/Provisioning.tsx`:** `BootstrapWindow` card (`windowGuidance(status)` →
  open/closed × configured guidance), `GET /me` identity card (`useMe` from `lib/hooks`), read-only
  `BootstrapExplainer` mirroring the backend docstring; an Admin gets a Panel link instead of a
  duplicated role-assignment surface.
- **Frontend — `nav.ts`:** NEW `"Admin Provisioning"` item at `/panel/provisioning`, **NOT
  `adminOnly`** (reachable pre-elevation, before the first Admin exists) → `ALL_NAV_ITEMS` 23 → 24.
  **`App.tsx`:** `/panel/provisioning` joins REAL_PATHS + route.
- **Frontend tests** — `test/provisioning.test.tsx` (6; window states / identity + Panel link /
  error) + `nav.test.tsx` 23 → 24: **+6 → frontend 67 → 73**; typecheck + lint clean, build green.
- **CI:** 3/3 green (Backend lint/type/test 13m3s, Frontend 30s, Docker 34s); no blocking review finding.
- **Honest boundary (PERMANENT):** provisioning stays **server-side + signup-time only** (no runtime
  provisioning API) — this page **reads status and documents the flow, it never provisions**.
  `active_admin_exists` is deliberately anonymous-exposed (a single boolean deployment fact, no PII,
  the first Admin is not yet authenticated). Ongoing role management remains in the Panel.

## Post-V1 — Frontend Admin Trash restore page (TIER 2, frontend slice 10) ✅ landed (PR #86, merged → main `09f4130`)

**FRONTEND-ONLY (2 new + 2 edits + 1 test)** — the `/trash` placeholder becomes the real page, binding
the backend Stage 6c restore surface (`application/queries/trash.py` + `application/commands/deletion.py`
restore, exposed by `apps/api/routes/trash.py`, doc 20 §7). **NO backend change; NO migration; alembic
head stays `0021_local_auth`; `ENGINE_VERSION` unchanged; backend test base stays 1036.**

- **NEW `frontend/src/lib/trash.ts`:** wire types mirror the backend projections verbatim
  (`TrashEntry` / `TrashEntriesPage` — `meta.recoverable_total` + `meta.object_types` — /
  `TrashEntryDetail` — deletion + dependency snapshots, tombstone — / `RestoreResult`). Read hooks under
  the `["trash"]` prefix (**no dedicated SSE event** — a restore changes an entity lifecycle →
  `resource.changed` full refresh + emits `audit.event.created` → `["audit"]`): `useTrashEntries(filters,
  cursor)` (q / object_type filters, forward-only keyset cursor, `placeholderData` keeps the table mounted
  across a page flip) + `useTrashEntry(id)` (enabled-gated on a selected id). Restore mutation
  `useRestoreEntry` → `POST /trash-entries/{id}/restore` with **OCC `expected_head_revision_id =
  entry.row_version`** (a stale tab gets the 409 envelope verbatim) + a **fresh `Idempotency-Key` UUID per
  attempt** (a retry after a rejection is a new decision, not a replay — doc 20 §14; body token wins over
  If-Match), invalidates `["trash"]` + `["audit"]` on success — the exact `lib/adminPanel.ts` `useAssignRole`
  pattern. `purgeStatusTone` badge-tone helper (presentation only).
- **NEW `frontend/src/pages/Trash.tsx`:** `TrashCard` — the object_type filter select is hydrated from the
  server response (`entries.data.meta.object_types`), **never a hard-coded client list**; q search; keyset
  `Pager` (`useCursorStack`); recoverable-index table with the server `recoverable_total`. **Restore is
  offered ONLY on server-truth `restore_eligible` rows** (the purge-pending row shows "not restorable");
  a command failure surfaces the backend canonical `ApiError` **verbatim** (`mutationErrorText`, mirrors
  Panel / AnalysisLab). `TrashRow` + `TrashDetail` (immutable deletion + dependency snapshots, purge/restore
  control state, tombstone; `snapshotStyle` inline `pre` wrap + scroll so a wide JSON never widens the page).
- **`App.tsx`:** `/trash` joins REAL_PATHS + a real `Route`. **`nav.ts` UNCHANGED** — the `/trash` `adminOnly`
  item already existed as a placeholder; the page just went live behind it.
- **Frontend tests** — NEW `test/trash.test.tsx` (7; apiStub ORDERED — the restore + detail routes precede
  the `/trash-entries` list prefix): index + recoverable total / restore_eligible gating / OCC +
  Idempotency-Key restore / object_type query param / snapshot detail / `["trash"]` invalidation refetch /
  403 verbatim: **+7 → frontend 73 → 80**; typecheck + lint clean, build green.
- **CI:** all green on the merged branch; review 0 CRITICAL/HIGH.
- **Honest boundary (PERMANENT):** Trash **purge** (destructive — needs a `confirmation_phrase` / re-auth
  proof) is intentionally OUT OF SCOPE for this restore-focused slice — it requires a separate re-auth slice.
  Trash is **Admin-only server-side** (`require_trash_admin`) — a non-Admin sees the 403 envelope verbatim
  (a hidden nav item is never authorization, doc 20 §2). `["jobs"]` still has NO backend list surface.

## CP-Gen — deterministic candidate generation landed (PR #89, merged → main `ba533e5`, feat `5cc62cc`)

**BACKEND-ONLY (1 new + 1 edit + 1 test) — NO migration, alembic head stays `0021_local_auth`,
`ENGINE_VERSION` unchanged (`backtest-engine-v2-position-size-limits` — CP-Gen never touches the
engine).** Replaces the V1 stub *compute* in `submit_candidate_generation` with a deterministic,
reproducible candidate-manifest pipeline (doc 06 §5). **No LLM** — a real LLM/code generator stays
Future-Dev. Diff: `candidate.py` +149, `create_package.py` +41/−7, `test_candidate_generation.py`
+123 (3 files, +306/−7).

- **NEW `backend/src/entropia/domain/create_package/candidate.py` (pure, no I/O):**
  `GENERATOR_VERSION = "cp-candidate-gen-v1"` — the ENGINE_VERSION analogue; bumping it shifts the
  `candidate_hash` namespace so a candidate built by an older generator is never silently reused
  (INF-04/INF-05). Frozen `CandidateManifest` dataclass (`generator_version` / `package_kind` /
  `source_kind` / `signal_kind` / `output_contract` / `resolved_dependencies` / `test_plan` /
  `uncertainty`; `as_dict()` via `dataclasses.asdict`). `build_candidate_manifest(*, package_kind,
  source_kind, output_contract, resolved_refs)` → reproducible manifest; `candidate_hash(manifest)
  = "sha256:" + content_hash(manifest.as_dict())` (reuses `domain/revision/hashing.content_hash`).
  `_summarize_resolved` sorts resolved refs by `canonical_key` → **order-independent** hash.
  Fail-closed `_output_kind` (`kind` OR `output_type` alias missing → `OutputContractInvalid`) +
  `_validate_contract_against_deps` (`directional_signal` → needs ≥1 `ta.*` dep; `boolean_condition`
  → needs ≥1 `cond.*` dep; **empty resolved → skipped**: description / dep-less request,
  implementation deferred). **Layer-clean:** checks canonical-key **prefixes** (`ta.` / `cond.`) —
  does NOT import the backtest indicator taxonomy, keeping the CP domain independent.
  `_test_plan` / `_uncertainty` derive human-readable notes (DESCRIPTION source + empty-resolved
  uncertainty).
- **`application/commands/create_package.py::submit_candidate_generation`:** the 4-line stub compute
  (`sha256` of `{request_id, context_hash}` + an output-contract copy) → the manifest compute.
  `candidate_hash` is now the manifest's **real content hash**; `candidate_output_contract =
  manifest.output_contract`. NEW helper `_candidate_resolved_refs(session, detail)` — DESCRIPTION →
  `[]`, code → the **current PASSED scan's `resolved_refs`** (the PC-13 gate already ran in
  `_enforce_precheck_gate`, so the scan is fresh). Return keys UNCHANGED (`{request_id, state,
  candidate_hash, job_id}`); the audit/outbox `candidate_generation_started`/`_completed` pair,
  `run_idempotent`, `session.refresh(with_for_update=True)`, the state machine and the durable job
  row are all unchanged.
- **NEW `backend/tests/unit/test_candidate_generation.py` (+12):** reproducibility (same inputs →
  same hash), order-independence (`resolved_refs` shuffled → same hash), output_contract /
  resolved_refs hash sensitivity, `GENERATOR_VERSION` namespace shift, fail-closed validation
  (`directional_signal` → `ta.*` / `boolean_condition` → `cond.*` / empty-resolved skip),
  `output_type` alias, DESCRIPTION uncertainty note, test_plan dependency listing. **backend
  1036 → 1048; ruff/format/mypy clean; review 0 CRITICAL/HIGH.**
- **Unchanged (already real — DO NOT re-touch):** Pre-Check resolver (`_resolve_declared` → ESP
  registry pin), `DependencyScan` immutable evidence, PC-13 gate (`_enforce_precheck_gate`), job
  durability, the request state machine, `_draft_dependency_snapshot` (the `dependency_snapshot`
  comes from the Pre-Check scan — the Slice C SOURCE), the backtest engine + `resolve_indicator_plan`.
- **Honest boundary (PERMANENT):** LLM generation is Future-Dev (the spec itself defers it). The
  generated candidate artifact is **NOT executed** by the backtest engine — the engine natively
  computes from the `dependency_snapshot` pins (ESP `_MovingAverage`/`_Rsi`/`_Vwap`…); a real
  code-executor is a separate mega-slice. No async dramatiq move (deterministic in-tx compute
  suffices; the job row is still durable). CP / Pre-Check **frontend** pages remain placeholders (the
  natural next slice). `["jobs"]` has NO backend list surface (permanent).

## Post-V1 — Frontend Create Package request page (TIER 2, frontend slice 11) ✅ landed (PR #91, merged → main `bda3a7f`, feat `79fbd24`)

**FRONTEND-ONLY (3 new + 2 edits) — backend unchanged, NO migration, alembic head stays
`0021_local_auth`, `ENGINE_VERSION` unchanged, backend test base stays 1048.** Binds the
`/packages/create` placeholder to the real Create Package backend (`routes/create_package.py`;
doc 06 §4/§5/§9). This slice is the request **LIFECYCLE ENTRY** only — compose a request, list own
requests, open the read-only projection. Pre-Check run / generate-candidate / draft / approve
ACTIONS are the natural follow-up slice; the detail already surfaces their read-only hints
(`current_scan`, `precheck_fresh`, `can_generate_candidate`).

- **NEW `frontend/src/lib/createPackage.ts`** — wire types mirroring
  `application/queries/create_package.py` projections verbatim (`PackageRequestSummary` /
  `PackageRequestDetail` / `ScanSummary` / `CreateRequestResult`) + enums mirrored from
  `domain/create_package/enums.py` (`CreatePackageKind`/`CreationMode`/`SourceKind`/
  `SourceLanguage`) + `OUTPUT_KINDS_BY_KIND` (mirrors `value_objects._OUTPUT_KINDS_BY_KIND`;
  hydration only — the server re-validates every field) + `sourceKindForMode` (code vs description
  mirror of `_CODE_MODES`) + `requestStateTone` (presentation-only badge tone over the 17-state
  `CreatePackageState`). Hooks under **`["package-requests"]`** (no dedicated SSE event — swept by
  `resource.changed`): `usePackageRequests` (keyset cursor, `placeholderData`), `usePackageRequest`
  (enabled-gated detail), `useRationaleFamilies` (shared `["rationale-families"]` selector source,
  5m staleTime). `useCreatePackageRequest` — POST with a **fresh `Idempotency-Key` per submit**
  (no OCC token — a create has no head to race), invalidates `["package-requests"]`.
- **NEW `frontend/src/pages/CreatePackage.tsx`** — `CreateForm` (doc 06 §4 field contract:
  `source_language` only for code modes (`other` → label required); output-contract kind scoped to
  the package type and RESET on type switch; rationale family REQUIRED for Indicator/Condition,
  hydrated from `GET /rationale-families`, N/A for ESP (system classification); declared canonical
  keys one-per-line → `[{key}]`; `target_runtime` fixed `python`); `RequestsCard` (keyset `Pager`,
  flow-state badge); `RequestDetailCard` (read-only projection + current Pre-Check scan hints).
  Command failures render the canonical `ApiError` VERBATIM (`mutationErrorText` — Panel mirror).
- **`App.tsx`** — `/packages/create` joins `REAL_PATHS` + real `Route`; **`nav.ts` UNCHANGED**
  (24 items — the `/packages/create` item already existed as a placeholder). **`global.css`** —
  `.cp-*` compose-form grid (2-col, collapses at 720px).
- **NEW `test/createPackage.test.tsx` (+7):** list + flow-state badge / composed body + fresh
  Idempotency-Key / description mode sends `source_language: null` / output kinds scoped by type /
  detail projection + scan hints / `["package-requests"]` invalidation refetch / 403 verbatim.
  **Frontend 82 → 89**; typecheck + lint clean, build green; CI 3/3 green.
- **Honest boundary:** `target_runtime` fixed to `python` (`SUPPORTED_TARGET_RUNTIMES`; `pine_v5`
  rejected server-side with `RuntimeUnavailable`); Pre-Check / generate-candidate / draft / approve
  ACTIONS + `compatible_rationale_family_ids` / `linked_indicator` composer fields deferred to the
  follow-up slice; the Pre-Check PAGE (`/packages/pre-check`, doc 07) is still a placeholder; CP
  requests have no dedicated SSE event; `["jobs"]` has NO backend list surface (permanent).

## Post-V1 — CP request lifecycle actions + Pre-Check page (TIER 2, frontend slice 12) ✅ landed (PR #93, merged → main `5b59884`, feat `e8f8982`)

**FRONTEND-ONLY (2 new + 4 edits)** — backend unchanged (1048), no migration, alembic head
`0021_local_auth`, ENGINE_VERSION unchanged. Closes the PR #91 honest boundary: the request
detail gains the lifecycle ACTIONS (doc 06 §7, doc 07 §8) and `/packages/pre-check` becomes the
real page (doc 07). Frontend 89 → **98** (+9 vitest). CI 3/3 green; review self-review + local
loop (0 CRITICAL/HIGH).

- **`lib/createPackage.ts` EXTENDED in place (no new lib file):** action wire types mirror the
  command return dicts verbatim (`PrecheckActionResult`/`CandidateActionResult`/
  `DraftActionResult`/`ApproveActionResult`) + `DependencyScanDetail`
  (`queries::get_dependency_scan`) + `ResolvedRef`/`MissingCall` row shapes (`_resolve_declared`);
  `useRunPrecheck`/`useGenerateCandidate` — request `row_version` as the **`X-Request-Version`
  OCC header** + a **fresh `Idempotency-Key` per attempt** (private `postWithRequestVersion`,
  the agentLab `postWithIfMatch` mirror); `useCreateDraft` — **`expected_candidate_hash` BODY
  token** from the accepted generate result (races the CANDIDATE, not the request head; server
  idempotently replays an existing draft); `useApproveRequest` — **`expected_head_revision_id`
  = draft head** + optional note, **Admin-only SERVER-side (CR-02)** — the UI never role-gates,
  a non-Admin sees the 403 envelope verbatim. All actions invalidate `["package-requests"]` +
  `["audit"]`; `useDependencyScan` reads the immutable artifact (5m staleTime) under the
  `["package-requests"]` prefix; new `scanStatusTone` + `asRecordArray` helpers.
- **`pages/CreatePackage.tsx`:** `RequestActions` bar on the detail card — gating mirrors server
  hints ONLY (`can_generate_candidate`, `candidate_ready`, draft present); the accepted candidate
  hash lives in card state as the draft token; per-action results/denials rendered verbatim.
- **NEW `pages/PreCheck.tsx`** (`/packages/pre-check`, doc 07): own-requests picker (keyset
  `Pager`) → run scan (`Checking dependencies…` pending label) → §7.1 dependency result rows
  (literal **Resolved / Missing** text — never color alone; every value a text node, untrusted
  source can never inject markup) → §7.2 canonical status lines + the stale warning (passed scan
  with a moved context) → immutable scan artifact viewer (`GET /dependency-scans/{scan_id}`:
  source_hash / language / unsupported / job / completed_at).
- **`App.tsx`:** `/packages/pre-check` joins REAL_PATHS (11→12) + real Route; **`nav.ts`
  UNCHANGED** (24 items — the Pre-Check item existed as a placeholder).
- **Tests:** +4 `createPackage.test.tsx` (pre-check OCC header + fresh Idempotency-Key /
  generate gated on the server hint / draft carries the accepted candidate hash / approve sends
  the draft head token + Admin denial verbatim) + NEW `test/preCheck.test.tsx` (+5: §7.1 rows /
  OCC run + canonical passed line / scan artifact viewer / stale warning / 403 verbatim) —
  apiStub routes ORDERED (action POST + detail GET fragments precede the
  `/create-package/requests` list prefix they contain).

**Honest boundary:** `compatible_rationale_family_ids`/`linked_indicator` composer fields still
deferred; the draft staleness token exists only in the card that ran Generate (the projection
intentionally omits `candidate_hash` — after a reload the server-side state check alone gates);
approve targets `draft_created`/`eligible_for_approval` edges server-side (other states surface
the typed rejection verbatim); no dedicated CP SSE event (`resource.changed` sweeps); `["jobs"]`
has NO backend list surface (permanent).

## Post-V1 — gated capability operational POSTs into Future Dev (TIER 2, frontend slice 13) ✅ landed (PR #95, merged → main `5225629`, feat `652dfde`)

**FRONTEND-ONLY (4 edits, no new files)** — backend unchanged (1048), no migration, alembic head
`0021_local_auth`, ENGINE_VERSION unchanged. Closes the PR #82 honest boundary: the two gated
operational POSTs (`POST /view-datasets/query`, `POST /analysis-artifacts`) are now
frontend-bound — the FULL `routes/capability.py` surface is consumed; NO capability endpoint
remains unbound. Frontend 98 → **105** (+7 vitest). CI 3/3 green; self-review + local loop
(0 CRITICAL/HIGH).

- **`lib/capability.ts` EXTENDED in place (no new lib file):** `ANALYSIS_ARTIFACT_CAPABILITY` —
  hydration-only mirror of `commands/capability.py` (doc 22 §10.3–§10.6: review/MC/WFA →
  `backtest_review`, sensitivity → `parameter_fields`, label/regime → their research
  capabilities); the server re-derives the gate from `artifact_type` on every dispatch.
  `ANALYSIS_ARTIFACT_TYPES` in the server's sorted `allowed` order. Wire types
  `ViewDatasetResult`/`AnalysisArtifactResult` mirror the command return dicts verbatim.
  `useQueryViewDataset`/`useCreateAnalysisArtifact` — **fresh `Idempotency-Key` per attempt,
  NO OCC token** (a create has no head to race); blank optional fields are OMITTED, never sent
  empty; success invalidates `["audit"]` ONLY — neither entity has a read surface (results live
  in the command return + the audit trail).
- **`pages/FutureDev.tsx`:** `ViewDatasetComposer` inside the Graphic View card (source manifest
  refs one-per-line + schema version + optional series/marker refs; `parseRefLines` mirrors the
  CreatePackage declared-keys composer) + NEW `AnalysisArtifactsCard` (type select with the
  display-only gating-capability mirror + input refs + method version + optional output ref).
  Composers are NEVER client-pre-gated (UI visibility is never authorization, doc 22 §3): the
  server re-checks Limited/Active on every dispatch and `CAPABILITY_NOT_ACTIVE` renders verbatim
  (CR-09/FD-02) — no fake job, no fake progress.
- **Tests:** +5 `futureDev.test.tsx` (view-dataset body + Idempotency-Key + blank-optional
  omission / submit gating / CAPABILITY_NOT_ACTIVE verbatim + a DIFFERENT fresh key on retry /
  gating display scoping / artifact POST + created id) + 2 `capabilityLib.test.ts` mirror units.
  **`App.tsx`/`nav.ts` UNCHANGED** (REAL_PATHS stays 12 — `/future-dev` was already real).

**Honest boundary:** `range_spec` has no composer input (no V1 renderer consumes it — the wire
type carries it); created view datasets / analysis artifacts have NO list/read surface
(permanent until a backend projection lands — audit rows appear in Panel → Logs); no dedicated
capability SSE event (`resource.changed` sweeps).

## Post-V1 — live-data Package Library catalog page (TIER 2, frontend slice 14) ✅ landed (PR #97, merged → main `af7c66b`, feat `53394fe`)

**FRONTEND-ONLY (3 new files + 1 edit)** — backend unchanged (1048), no migration, alembic head
`0021_local_auth`, ENGINE_VERSION unchanged. The `/packages/library` placeholder becomes the real
page: the V1 Package Library read surface (`routes/library.py`, doc 08 §3/§4/§9.2) is fully
frontend-bound (both GETs). First of the 12 remaining placeholder pages — 11 remain. Frontend
105 → **113** (+8 vitest). CI 3/3 green; self-review + local loop (0 CRITICAL/HIGH).

- **NEW `lib/library.ts`:** wire types mirror `application/queries/library.py` verbatim —
  `LibraryPackageRow`/`LibraryPage`/`LibraryPackageDetail` (live rationale-family resolution
  `{id, name, pinned_name, family_active}`, Stage-2e `provenance` + immutable scan summary,
  `revisions` history, ten-flag `PackagePermissions` in backend dataclass order +
  `PERMISSION_FLAGS`/`PERFORMANCE_FIELDS` render-order mirrors). Hydration-only facet taxonomy
  mirrors (`CATALOG_PACKAGE_KINDS`/`CATALOG_LIFECYCLE_STATES`/`PACKAGE_VALIDATION_STATES`/
  `APPROVAL_STATES`/`VISIBILITY_SCOPES` + the `UNASSIGNED_FAMILY` sentinel) — selects hydrate
  from these; the server re-validates every filter (`CatalogFilterInvalid` 422 verbatim). Hooks
  under `["library"]` (no dedicated SSE event — `resource.changed` sweeps): `useLibraryPackages`
  (the kind facet travels as the `type` route alias; empty facets NEVER sent; keyset cursor;
  placeholderData) + `useLibraryPackage` (enabled-gated, `encodeURIComponent`). Read-only — no
  mutation, no OCC token. `validationTone`/`approvalTone`/`lifecycleTone` presentation helpers.
- **NEW `pages/Library.tsx`:** facet filter bar (5 taxonomy selects + a rationale-family select
  hydrated from the shared `useRationaleFamilies` list incl. the `unassigned` sentinel +
  free-text `q`), catalog table with orthogonal lifecycle/validation/approval badges (doc 08
  §13 — the V18 Status dropdown stays split into its facets), cursor-stack `Pager`, detail
  card: ten permission flags rendered as text (never colour-only), **L4 performance
  availability labels verbatim (never fabricated zeros)**, contracts/dependency-snapshot/
  validation-summary JSON, provenance + dependency-scan summary, revision history. A Guest sees
  the 401 envelope verbatim (doc 08 §2 — UI visibility is never authorization).
- **`App.tsx`:** `/packages/library` joins REAL_PATHS (12 → 13) + real Route; **`nav.ts`
  UNCHANGED** (24 items — the nav item already existed as a placeholder).
- **Tests:** NEW `test/library.test.tsx` (+8: index render with orthogonal facets scoped to the
  table / facet query param + empty-facet omission / unassigned sentinel / q search / detail
  permissions + N/A performance + provenance + history / keyset pager / `["library"]`
  invalidation refetch / 401 verbatim; apiStub ORDERED — the detail fragment precedes the
  `/library` list prefix).

**Honest boundary:** read-only catalog slice — package ACTIONS (revise / request-validation /
approve-publish / deprecate / soft-delete / export) are explained by the server-computed
permission flags but NOT dispatched from this page (later slices; the detail ETag/`row_version`
is already surfaced for their OCC tokens); catalog performance metrics are all `not_applicable`
by server contract until runs are linked (doc 08 §3.2, L4).

## Post-V1 — live-data Embedded System Packages page (TIER 2, frontend slice 15) ✅ landed (PR #99, merged → main `fa2003f`, feat `5bf633a`)

**FRONTEND-ONLY (3 new files + 1 edit)** — backend unchanged (1048), no migration, alembic head
`0021_local_auth`, ENGINE_VERSION unchanged. The `/packages/embedded` placeholder becomes the
real page: the doc 09 READ surface of `routes/esp.py` is frontend-bound — the role-aware
resolver-registry catalog (GET list, `trust_state` facet, keyset cursor by canonical_key), the
resolver detail projection, and the Pre-Check-parity resolve probe (`POST /resolve` as pure
transport). Second of the remaining placeholder pages — 10 remain. Frontend 113 → **121**
(+8 vitest). CI 3/3 green; self-review + local loop (0 CRITICAL/HIGH).

- **NEW `lib/esp.ts`:** wire types mirror `application/queries/esp.py` verbatim —
  `EspRegistryRow` (`_registry_dict`) / `EspPackageDetail` (`get_esp_detail`) / `EspContract`
  (`_contract_dict`) / `ResolveResult` (`resolve_embedded_dependency`). Hydration-only taxonomy
  mirrors of `domain/esp/enums.py` (`RESOLVER_TRUST_STATES`, `RUNTIME_ADAPTERS`) + the L4
  `ESP_PERFORMANCE_FIELDS` order (`net_profit`/`backtest_ready`/`oos_passed` — N/A by nature,
  doc 09 §14, never fabricated). Hooks under `["esp"]` (no dedicated SSE event —
  `resource.changed` sweeps): `useEspRegistry` (empty facet NEVER sent; keyset cursor;
  placeholderData) + `useEspPackage` (enabled-gated, `encodeURIComponent`) + `useResolveProbe`
  — the doc 09 §4.3 probe is a PURE READ over the live registry (creates nothing, writes no
  audit row) so the POST carries **no Idempotency-Key and invalidates no key**.
  `parseSignatureParams` ("name:type"-per-line → ordered `{name?, type}` list) + `trustTone`.
- **NEW `pages/Embedded.tsx`:** registry table (canonical_key / trust badge / adapter /
  registry_version / trusted revision) + trust facet + cursor-stack `Pager`; detail card
  (contract signature + warm-up/timing/repaint semantics verbatim, registry snapshot with the
  OCC-ready `registry_version`, lifecycle/validation/approval badges, **L4 N/A performance
  labels verbatim**); Resolve Probe card — ordered param TYPES are identity (names
  display-only); success renders the EXACT pinned revision (P4/L5 — never latest); typed
  failures (`RESOLVER_NOT_RESOLVED` 404 / `RESOLVER_SIGNATURE_MISMATCH` 422 /
  `RESOLVER_ADAPTER_INCOMPATIBLE` 409) render verbatim (doc 09 §9.1–§9.3).
- **`App.tsx`:** `/packages/embedded` joins REAL_PATHS (13 → 14) + real Route; **`nav.ts`
  UNCHANGED** (24 items).
- **Tests:** NEW `test/embedded.test.tsx` (+8: 1 `parseSignatureParams` unit + 7 component —
  index with trust badges scoped to the table / trust facet param + empty-facet omission /
  keyset pager / detail contract + L4 N/A ×3 + registry snapshot / probe body + pinned revision
  + no-Idempotency-Key / typed failure verbatim / `["esp"]` invalidation refetch; apiStub
  ORDERED — the resolve POST + detail GET fragments precede the `/embedded-system-packages`
  list prefix).

**Honest boundary:** read slice — registry MUTATIONS (`POST /embedded-system-packages` create +
`/activate` + `/deprecate`, Admin-only server-side, `X-Registry-Version` OCC header +
Idempotency-Key) are NOT dispatched from this page (later slices; the detail `row_version` /
`registry_version` tokens are already surfaced as their OCC tokens); ESP performance stays
`not_applicable` by nature (doc 09 §14, L4 — resolvers never carry trading metrics).

## Post-V1 — live-data Rationale Families page (TIER 2, frontend slice 16) ✅ landed (PR #101, merged → main `7372478`, feat `20ccacc`)

**FRONTEND-ONLY (3 new files + 1 edit)** — backend unchanged (1048), no migration, alembic head
`0021_local_auth`, ENGINE_VERSION unchanged. The `/rationale-families` placeholder becomes the
real page, binding the **FULL** `routes/rationale.py` surface (doc 10 §7, §8) — the shared taxonomy
plane, both tables. **Unlike the prior read-only slices this is a full CRUD + editor slice**, because
the backend is **shared-editing** (any authenticated actor may edit both; `ensure_can_manage_families`
/ `ensure_can_edit_assignments` — Admin-only is NOT used) and the read-only `useRationaleFamilies`
selector already existed (so a read-only re-do was low value). Third of the remaining placeholder
pages — 9 remain. Frontend 121 → **128** (+7 vitest). CI 3/3 green; self-review + local loop
(0 CRITICAL/HIGH).

- **NEW `lib/rationale.ts`:** wire types mirror `application/queries/rationale.py` `_family_dict` /
  `_assignment_row` + `application/commands/rationale.py` return dicts verbatim
  (`RationaleFamilyCard` / `RationaleAssignmentRow` + `CreateFamilyResult` / `ReviseFamilyResult` /
  `SoftDeleteFamilyResult` / `BatchAssignResult`). Hooks under prefixes swept by `resource.changed`
  (no dedicated rationale SSE event): `useFamilies` (active registry projection, keyset cursor,
  placeholderData) + `useAssignments` (`meta.table_version` = the batch OCC token). Four mutations
  mirror `lib/trash.ts` / `lib/adminPanel.ts`: `useCreateFamily` (fresh `Idempotency-Key`, **no OCC
  token** — a create has no head to race), `useReviseFamily` (OCC `expected_head_revision_id` = the
  family's current head, the command's token per doc 10 §5 Save + `Idempotency-Key`),
  `useSoftDeleteFamily` (OCC `row_version` as the **`"rv-N"` If-Match ETag**,
  `shared/concurrency.py row_version_from_if_match`), `useBatchAssign` (echoes
  `expected_table_version`; all-or-nothing server-side + `Idempotency-Key`). Family mutations
  invalidate `["rationale-families"]` + `["rationale-assignments"]` + `["audit"]`; the batch
  invalidates the same set. `assignmentStateTone` maps the doc 10 §9.2 projection
  (assigned→ok / unassigned→neutral / assigned_to_deleted_family→down).
- **NEW `pages/RationaleFamilies.tsx`:** `FamilyRegistryCard` — one editor that creates, or revises
  when a row's Edit seeds it (remounts by `key` so a mode switch reseeds; subfamilies /
  compatible-outputs are one-per-line textareas → trimmed list); two-step confirm Delete; the server
  envelope renders verbatim on every failure (`RATIONALE_FAMILY_CONFLICT` / `RATIONALE_FAMILY_IN_USE`
  / `NAME_CONFLICT` / `NAME_RESERVED`). `AssignmentTableCard` — per-row family `select` hydrated from
  the first active-families page; staged reassignments diffed against server truth (only changed rows
  enter the batch); Save builds one `AssignmentChange` per changed row pinning
  `current_package_revision_id` (head OCC) + the selected family's `current_revision_id`; non-blocking
  `OUTPUT_TYPE_NOT_LISTED` warnings render verbatim; a soft-deleted pinned family surfaces as a
  synthetic `select` option so the value never falls outside its options.
- **`App.tsx`:** `/rationale-families` joins REAL_PATHS (14 → 15) + real Route; **`nav.ts`
  UNCHANGED** (24 items — the item already existed as a placeholder).
- **Tests:** NEW `test/rationaleFamilies.test.tsx` (+7: two-projection render / create
  `Idempotency-Key` + no OCC + exact body / revise head-revision OCC token / two-step delete
  `"rv-1"` If-Match / staged batch `expected_table_version` + `changes` + verbatim warning /
  `["rationale-families"]` invalidation refetch / server denial verbatim; apiStub ORDERED — the
  revise/delete/batch action fragments precede the list prefixes; **"Momentum" is NOT a ready-check**
  since it appears in the registry row, the assignment cell AND every select option — "trend"
  (fam_1's unique subfamily) is used instead, family-name asserts scoped to the registry table via
  `within`).

**Honest boundary:** the assignment `select` reads only the FIRST active-families page (doc 10 §7 UI
scope — >20 families would truncate the option set); soft-deleted families live in the Admin-only
Trash surface (restore/purge are NOT dispatched here); no dedicated rationale SSE event
(`resource.changed` sweeps `["rationale-families"]` / `["rationale-assignments"]`).

## Post-V1 — live-data Market Data page (TIER 2, frontend slice 17) ✅ landed (PR #103, merged → main `c09051a`, feat `0ca0468`)

**FRONTEND-ONLY (3 new files + 1 edit)** — backend unchanged (1048), no migration, alembic head
`0021_local_auth`, ENGINE_VERSION unchanged. The `/market-data` placeholder becomes the real page,
binding the doc 11 READ surface of `routes/market_data.py` (registry list + head detail +
approved-bundle resolve) **plus the owner INGEST chain** (create dataset / raw-upload
start+finalize / durable 202 analysis job / schema mapping) — 8 of the 10 endpoints. Fourth of the
remaining placeholder pages — **8 remain**. Frontend 128 → **140** (+12 vitest). CI green;
self-review + local loop (0 CRITICAL/HIGH; 1 MEDIUM — bundle-probe re-click retry — fixed
pre-commit).

- **NEW `lib/marketData.ts`:** wire types mirror `application/queries/market_data.py`
  `_revision_dict` / `get_market_dataset_detail` / `resolve_approved_market_data_bundle` +
  `application/commands/market_data.py` return dicts verbatim (`MarketDatasetRow` /
  `MarketDatasetDetail` / `ApprovedBundle` + `CreateDatasetResult` / `StartUploadResult` /
  `FinalizeUploadResult` / `AnalysisAccepted` / `SchemaMappingResult`). Taxonomy hydration mirrors
  `MARKET_DATA_TYPES` (ohlcv/tick_trades/spread_execution) + `MARKET_REVISION_STATES` (8 states;
  `verified` ≠ `approved`) — the server re-validates (CR-04). Hooks under `["market-data"]` (no
  dedicated SSE event — `resource.changed` sweeps): `useMarketDatasets` (keyset registry,
  placeholderData) + `useMarketDataset` (enabled-gated detail; the response `row_version` is the
  deferred lifecycle actions' OCC token) + `useApprovedBundle` (ON-DEMAND read probe —
  enabled-gated GET, retry:false; 404 verbatim so consumers never bind "latest"; a re-click
  refetches). Mutations invalidate `["market-data"]` + `["audit"]`: `useCreateDataset` (**NO
  Idempotency-Key — the create route reads none, mirrored verbatim**), `useStartUpload` (immutable
  evidence row: object_key + digest + size metadata ONLY), `useFinalizeUpload` /
  `useRequestAnalysis` (fresh `Idempotency-Key` per attempt; analysis renders the 202 admission
  `{job_id, queue, status}` verbatim), `useConfirmMapping` (a blank confirmed mapping is OMITTED →
  server auto-confirm; `MAPPING_REVIEW_REQUIRED` 422 verbatim, D7). `parseMappingLines`
  ("canonical: source" per line; empty source → null) + `linesToList` + `revisionStateTone`.
- **NEW `pages/MarketData.tsx`:** `CreateDatasetCard` (type select from the canonical three;
  optional payload JSON **object** — parse failures blocked locally as transport shaping, domain
  validation stays server-side; a create auto-opens its detail), `RegistryCard` (revision-state
  badges + validation verbatim; cursor-stack Pager), `DetailCard` (identity/hashes/revision
  history + the Step 1/2 ingest workflow `UploadComposer` → `AnalysisAction` → `MappingComposer` +
  `BundleProbe`). Buttons are never role-pre-gated — the server owner/Admin draft gate
  (`ensure_can_edit_draft`) answers with the canonical envelope verbatim.
- **`App.tsx`:** `/market-data` joins REAL_PATHS (15 → 16) + real Route; **`nav.ts` UNCHANGED** (24).
- **Tests:** NEW `test/marketData.test.tsx` (+12: 1 `parseMappingLines` unit + 11 component;
  apiStub ORDERED — finalize precedes `/raw-uploads`, action/detail/bundle fragments precede the
  `/market-datasets` list prefix; "Binance 15m OHLCV" ready-check, badge asserts `within`-scoped
  to the registry table).

**Honest boundary:** revision lifecycle actions (create revision / successor, Admin approve /
deprecate — If-Match `"rv-N"` OCC + `Idempotency-Key`) are the NATURAL FOLLOW-UP slice (the CP
#91→#93 pattern; the detail `row_version` token is ready); raw BYTES never travel through this
page (no byte-upload endpoint on this surface — the D5/D6 evidence row pins object key + digest);
the analysis job id is informational (`["jobs"]` has no list surface — permanent), progress lands
on the revision state.

## Stage post-V1 TIER 2 — Market Data lifecycle actions landed (PR #105)

**FRONTEND-ONLY** (3 edits; backend unchanged, 1048 stays, no migration, alembic head
`0021_local_auth`, `ENGINE_VERSION` unchanged). Binds the four unbound `routes/market_data.py`
lifecycle endpoints, closing the Market Data page (PR #103) honest boundary — **10/10 endpoints now
frontend-bound**. **Empirical finding (route read — the handoff/kickoff summary was WRONG):**
`successor` + `deprecate` read NO `If-Match`/`Idempotency-Key` header (their route signatures carry
none); only `revisions` + `approve` carry both; `approve` + `deprecate` are Admin-only
(`ensure_can_approve`). `lib/marketData.ts`: `useCreateRevision`/`useCreateSuccessor`/
`useApproveRevision`/`useDeprecateRevision` under `["market-data"]` (each invalidates
`["market-data"]`+`["audit"]`); `postWithOcc` helper (`If-Match "rv-N"` + fresh `Idempotency-Key`)
mirrors `lib/rationale.ts::useSoftDeleteFamily`; `TIMEZONE_MODES` mirror + wire types
(`CreateRevisionResult`/`SuccessorResult`/`ApprovalResult`/`RevisionBody`). `pages/MarketData.tsx`:
`DetailCard` `LifecycleSection` = `RevisionComposer` (append revision OCC / create successor no-OCC;
custom-mode IANA input; local JSON payload parse-block) + `ApprovalComposer` (Admin
approve/deprecate; revision picker defaulting to the current head). Buttons never role-pre-gated —
403 (non-Admin) / 409 (stale token / illegal transition) renders the canonical envelope verbatim.
+6 vitest (`test/marketData.test.tsx`) → **frontend 140 → 146**; typecheck + lint clean, build
green; CI 3/3. main = `db7b585` (Merge #105), feat `d2a9ada`. Honest boundary: ESP/Library registry
MUTATION slices are a separate slice (Admin-only, `X-Registry-Version` OCC); `["jobs"]` list surface
permanently absent; raw bytes still never travel through the page.

## Stage post-V1 TIER 2 — Research Data page landed (PR #107)

**FRONTEND-ONLY (2 new + 1 edit + 1 test)** — backend UNCHANGED (**1048** stays), no migration,
alembic head `0021_local_auth`, `ENGINE_VERSION` unchanged. The `/research-data` placeholder becomes
the real page, binding `routes/research_data.py` (doc 12) READ surface + owner INGEST chain — the
LAST real page in the **Packages & Data** nav group. Mirrors the Market Data page (#103) pattern:
read + ingest first, revision lifecycle deferred. main = `38988a2` (Merge #107), feat `5049f4e`.

**Endpoints bound: 6 of 14** — `GET /research-datasets` (role-aware keyset registry), `GET
/research-datasets/{id}` (head detail + revision history, ETag `rv-N`), `POST /research-datasets`
(create Root+DRAFT — DR3 market link required), `POST /research-datasets/{id}/upload-session` (raw
evidence row), `.../upload-session/finalize`, `.../analysis` (202 durable job → ANALYZING).

**AMPİRİK bulgu (route/command okundu — özet değil):** `create_dataset` + `create_upload_session`
`Idempotency-Key` OKUMUYOR → key gönderilmedi; `finalize_upload` + `request_research_dataset_analysis`
İKİSİ de okuyor → deneme başına taze `Idempotency-Key`. Her endpoint Admin/Supervisor/Agent gate'li
(`ensure_can_access_page` — User/Guest 403 verbatim); create ayrıca DR3 (ACTIVE+APPROVED linked
market revision yoksa 409 `DEPENDENCY_BLOCKED`). `research_data.router` `market_data.router` ile aynı
`prefix=base` → path'ler `/api/v1/research-datasets`.

**Reuse anchor'ları (kesin semboller):**
- **`lib/researchData.ts` (yeni):** wire tipleri `queries/research_data.py` `_revision_dict`/
  `get_research_dataset_detail` + command return dict'leri birebir aynası; `RESEARCH_CATEGORIES` (8;
  `other_custom` extensible — `custom_category` ZORUNLU, diğerleri null) + `USAGE_SCOPES` (3) +
  `RESEARCH_REVISION_STATES` (7; `verified` ≠ `approved`, `approval_revoked`) taksonomi aynaları +
  `researchStateTone`/`OTHER_CUSTOM_CATEGORY`. Hook'lar `["research-data"]` altında (özel SSE YOK →
  `resource.changed`): `useResearchDatasets` keyset + `useResearchDataset` enabled-gated (dönen
  `row_version` = ertelenen lifecycle OCC token'ı). Ingest mutasyonları `["research-data"]`+`["audit"]`
  invalidate: `useCreateDataset` (**Idempotency-Key YOK**), `useStartUpload` (immutable evidence,
  no idem), `useFinalizeUpload`/`useRequestAnalysis` (taze `Idempotency-Key`).
- **`pages/ResearchData.tsx` (yeni):** `CreateDatasetCard` (market_entity_id REQUIRED [DR3] +
  category/usage_scope select + `other_custom`→custom_category input [built-in→null] + display/
  provider/payload; lokal JSON payload parse-block) + `RegistryCard` (keyset Pager) + `DetailCard`
  (`IdentitySection` meaning/timing/usage metadata tablosu + revision history + `IngestSection`
  Step 1 upload/finalize + Step 2 analyze). Butonlar asla role-ön-gate'li değil — 403/409 kanonik
  zarf verbatim.
- **`App.tsx`:** `/research-data` → `REAL_PATHS` + gerçek `<Route>`; `nav.ts` UNCHANGED (24).
- **Testler:** `test/researchData.test.tsx` +11 (1 `researchStateTone` unit + 10 component: registry
  verbatim / create no-idem+auto-open+body / `other_custom` custom_category / lokal payload block /
  detail meaning+timing+history / upload no-idem→finalize taze-idem / analysis taze-idem 202 / DR3
  `DEPENDENCY_BLOCKED` verbatim / role-aware read denial verbatim / `["research-data"]` SSE sweep).
  apiStub SIRALI — aksiyon/detay fragment'leri liste prefix'inden ÖNCE. **frontend 146 → 157**;
  typecheck+lint temiz, build green; review 0 CRITICAL/HIGH.

**Dürüst sınır:** revision lifecycle aksiyonları — append DRAFT/successor revision, `set_time_policy`,
`define_field`/`define_feature`, Admin `approve`/`revoke`, agent/backtest evidence **bundles** (8
endpoint) — doğal follow-up'a ertelendi (detay `row_version` If-Match OCC token'ı hazır); ham baytlar
sayfadan geçmez; `["jobs"]` liste yüzeyi kalıcı yok.

## Stage post-V1 TIER 2 — Research Data lifecycle actions landed (PR #109)

**FRONTEND-ONLY (2 new + 3 edits)** — backend UNCHANGED (**1048** stays), no migration, alembic head
`0021_local_auth`, `ENGINE_VERSION` unchanged. Closes the PR #107 read+ingest boundary: the 8 unbound
`routes/research_data.py` lifecycle endpoints are wired → the Research Data page is now **14/14
endpoints** (the **Packages & Data** nav group is fully bound). main = `32d07e4` (Merge #109), feat
`2e488dc`. CI 3/3 green; self-review 0 CRITICAL/HIGH. **frontend 157 → 168** (+11 vitest).

**AMPİRİK route/command haritası (imzalar OKUNDU — özet değil, PR #105 dersi):**

| Endpoint | If-Match `"rv-N"` | Idem-Key | Admin | Not |
|---|---|---|---|---|
| `POST /{id}/revisions` | ✓ | ✓ | — | append DRAFT (category+usage_scope+timezone_mode REQUIRED) |
| `POST /{id}/time-policy` | — | — | — | `fixed_delay`→delay REQUIRED; diğerleri `delay=null` |
| `POST /{id}/field-definitions` | — | — | — | 7 required + `unit_or_scale` optional |
| `POST /{id}/feature-definitions` | — | — | — | `definition` JSON object |
| `POST /{id}/approve` | ✓ | ✓ | ✓ | VERIFIED→APPROVED; DR3/DR4 yeniden kontrol |
| `POST /{id}/revoke` | ✓ | ✓ | ✓ | APPROVED→APPROVAL_REVOKED |
| `POST /bundles/agent` | — | — | — | **PURE READ** compile probe |
| `POST /bundles/backtest-evidence` | — | — | — | **PURE READ** compile probe |

`revise`/`approve`/`revoke` OCC (`etag_for_row_version` `"rv-N"` + taze `Idempotency-Key`);
`time-policy`/`field`/`feature` header YOK; bundle compiler'lar PURE READ (durable row/audit YOK,
content-addressed `bundle_hash` — ESP resolve-probe / Market Data approved-bundle deseni → Idem YOK,
invalidation YOK). approve/revoke Admin-only SERVER-side (`ensure_can_approve`/`ensure_can_revoke` →
`APPROVAL_REQUIRES_ADMIN` 403 verbatim); UI asla role-ön-gate'li değil.

**Reuse anchor'ları (kesin semboller):**
- **`lib/researchData.ts` (genişletildi):** 8 hook + wire tipleri + taksonomi aynaları
  (`EVENT_TIME_SEMANTICS`(4) / `AVAILABLE_TIME_POLICIES`(4; `FIXED_DELAY_POLICY`) /
  `RESEARCH_TIMEZONE_MODES`(3; `CUSTOM_TIMEZONE_MODE`)) + `postWithOcc` helper (`lib/marketData.ts`
  birebir kopyası). `useCreateRevision` (OCC; body `entity_id`/`row_version` İÇERMEZ) /
  `useSetTimePolicy` / `useDefineField` / `useDefineFeature` / `useApproveRevision` /
  `useRevokeApproval` (hepsi `["research-data"]`+`["audit"]` invalidate) / `useCompileAgentBundle` /
  `useCompileEvidenceBundle` (invalidation YOK). Tipler: `RevisionBody`/`CreateRevisionInput`/
  `TimePolicyInput`/`FieldDefinitionInput`/`FeatureDefinitionInput`/`ApprovalInput`/`AgentBundleInput`/
  `EvidenceBundleInput`/`BundleResult`/`BundleMember`/`CreateRevisionResult`/`TimePolicyResult`/
  `FieldDefinitionResult`/`FeatureDefinitionResult`/`ApprovalResult`.
- **`components/ResearchLifecycle.tsx` (yeni, 713 satır):** DetailCard içinde render edilen 6 composer
  — `ReviseComposer` (OCC; `other_custom`→custom_category, `custom` timezone→IANA) /
  `TimePolicyComposer` (`fixed_delay`→pozitif delay, diğerleri delay=null; `custom`→IANA input) /
  `FieldDefinitionComposer` (7 required + unit_or_scale; `FIELD_INPUTS` map) /
  `FeatureDefinitionComposer` (definition JSON object) / `ApprovalComposer` (revision picker +
  approve/revoke; `detail.revisions` fallback) / `BundleComposer` (revision-ids textarea +
  `BundleResultView` hash+members). Yerel `mutationErrorText`/`parseJsonObject`/`linesToList`.
- **`pages/ResearchData.tsx` (edit):** `ResearchLifecycle` import + DetailCard'da
  `key={detail.data.entity_id}` ile render + iki stale "deferred follow-up" yorumu tazelendi.
- **Testler:** NEW `test/researchDataLifecycle.test.tsx` +11 (revise OCC If-Match `"rv-4"`+Idem /
  custom_category+IANA yalnız other_custom+custom / fixed_delay delay+no-header / non-fixed delay=null /
  field 7-required no-header / feature JSON definition / approve OCC Admin / revoke selected revision /
  Admin denial `APPROVAL_REQUIRES_ADMIN` verbatim / agent bundle no-idem+hash+members / evidence
  bundle). apiStub SIRALI — 8 aksiyon route'u liste prefix'inden ÖNCE. `test/researchData.test.tsx`:
  2 detay assertion `within(identityTable)` ile scope'landı (lifecycle `<option>`'ları aynı metni
  paylaşıyor — event-time semantics + "rv 4"). `App.tsx`/`nav.ts` UNCHANGED (REAL_PATHS 17, nav 24).

**Dürüst sınır:** ham baytlar sayfadan geçmez; `["jobs"]` liste yüzeyi kalıcı yok; bundle compiler'lar
pure read (oluşan bundle'ın kalıcı read yüzeyi yok — command return + `bundle_hash`); özel research-data
SSE event'i yok (`resource.changed` süpürür). **`routes/research_data.py` yüzeyi artık TAM bağlı
(14/14) — Packages & Data grubu tamamen kapandı.**

## Stage post-V1 TIER 2 — Backtest Ready Check page landed (PR #111)

**FRONTEND-ONLY (4 files, +748 lines)** — backend UNCHANGED (**1048** stays), no migration, alembic
head `0021_local_auth`, `ENGINE_VERSION` unchanged. The `/backtest/ready-check` placeholder becomes
the real page binding `routes/readiness.py` (doc 14 §4/§7/§9) — the strategy→RUN gate of the
Backtest group (RUN/History already bound since PR #72). main = `946b6cf` (Merge #111), feat
`6232486`. CI 3/3 green; self-review found + fixed 1 bug (stale flag, below). **frontend 168 → 174**
(+6 vitest).

**AMPİRİK route bulgusu (imza OKUNDU):** OCC token `"rv-N"` DEĞİL — composition **FINGERPRINT**.
`POST /mainboard-compositions/{id}/readiness-checks` `expected_fingerprint`'i **BODY-form** taşır
(If-Match değil; route `_resolve_expected` body'yi öncelikler) + deneme başına taze
`Idempotency-Key`; 409 `CompositionStale` = RC-09 verbatim. Success `["readiness"]` + `["mainboard"]`
İKİSİNİ de invalidate eder (default-Mainboard `ready_summary` hareket eder).

**Reuse anchor'ları (kesin semboller):**
- **`lib/readiness.ts` (yeni):** wire tipleri `ReadinessIssue`/`ReadinessSummary`/`ReadinessReport`/
  `CurrentReadiness`/`RunCheckResult`; `enums.py` aynaları `READINESS_STATE_LABELS`/
  `READINESS_STATE_TONES` + `NOT_CHECKED_STATE` + `readinessStateLabel`/`readinessStateTone`/
  `severityTone`; `["readiness"]` hook'ları (özel SSE YOK — `resource.changed` süpürür):
  `useCurrentReadiness(compositionId)` / `useReadinessReport(reportId)` / `useRunReadinessCheck`
  (`expected_fingerprint` body + taze `Idempotency-Key`; success `["readiness"]`+`["mainboard"]`
  invalidate).
- **`pages/ReadyCheck.tsx` (yeni):** iki mod — `?report=<id>` immutable deep-link + default
  workbench (`useDefaultMainboard` composition → current readiness → guard toggle'lı run). Report
  kartı state badge + summary counts + issues tablosu verbatim; non-current raporda stale
  ("re-run") vs superseded ("a newer report exists") ayrımı SERVER `state`'inden
  (`state === "stale"`), asla client'ta yeniden türetilmez.
- **SELF-REVIEW BUG (bulundu + düzeltildi):** stale bayrağı `stored_state !== state` ile
  hesaplanıyordu → superseded raporda da true olur, yanlış "re-run" gösterirdi → `state === "stale"`
  karşılaştırmasına düzeltildi + regression testi.
- **`App.tsx`:** `/backtest/ready-check` REAL_PATHS 17→18 + gerçek Route (`nav.ts` UNCHANGED — 24;
  item zaten placeholder'dı). **Testler:** NEW `test/readyCheck.test.tsx` +6 (apiStub SIRALI;
  zincirleme yükleme için `findBy*` — composition→readiness ikinci dalga, senkron `getBy*` erken
  çalışıyordu).

**Dürüst sınır:** RUN admission (`POST /backtest-runs`) RUN sayfasında kalır (doc 14 §9.3 scope);
readiness'in özel SSE event'i yok (`resource.changed` süpürür); sayfa yalnız default Mainboard
composition'ını okur (RUN sayfası deseni; Stage 3 gerçek Mainboard sayfası app-level'a taşıyabilir).
**Backtest grubunda kalan tek placeholder: `/portfolio` (allocation.py) — Ready Check'in okuduğu
allocation draft'ının editörü, doğal sıradaki slice (kullanıcı 2026-07-10 teyit etti).**

## Stage post-V1 TIER 2 — Portfolio / Equity Allocation page landed (PR #113)

**FRONTEND-ONLY (4 dosya, +1477 satır)** — backend UNCHANGED (**1048** sabit), migration YOK, alembic
head `0021_local_auth`, `ENGINE_VERSION` sabit. `/portfolio` placeholder'ı gerçek sayfa oldu —
`routes/allocation.py`'nin TAM yüzeyi (5/5 endpoint, doc 13 Stage 4a) bağlandı: Ready Check'in
okuduğu allocation draft'ının editörü. **Backtest nav grubu KAPANDI** (RUN/History #72 + Arrange
Metrics #74 + Ready Check #111 + Portfolio #113). main = `3210ede` (Merge #113), feat `f3e9550`.
CI yeşil; self-review 0 CRITICAL/HIGH (2 test-assertion düzeltmesi in-commit). **frontend 174 → 181**
(+7 vitest).

**AMPİRİK route haritası (imzalar OKUNDU — PR #105/#111 dersi):**

| Endpoint | OCC | Idempotency-Key |
|---|---|---|
| `GET .../portfolio-allocation-draft` | body `row_version` = canlı token (0 = plan yok = geçerli creation token) | — |
| `PUT .../portfolio-allocation-draft` | **BODY-form `expected_row_version`** (route body'yi If-Match'e tercih eder) | taze key/deneme |
| `POST .../portfolio-allocation/validate` | YOK (body/header okumaz) | YOK |
| `POST .../portfolio-allocation/sync` | YOK — **PURE READ** merge preview (query katmanı) | YOK |
| `POST .../portfolio-allocation/revisions` | body `expected_row_version` | taze key/deneme |

`item_type` PUT'ta HİÇ gönderilmez (server composition item'dan türetir, doc 13 §8.2); stale token →
409 `ALLOCATION_DRAFT_CONFLICT` verbatim (asla last-write-wins, §10.1); sync non-destructive (§10.2
Flow D — removal yalnız açık Save PUT ile uygulanır, §14#9); revision yalnız blocker-free ENABLED
draft'tan (§8.5 — `ALLOCATION_HAS_BLOCKERS` verbatim). Draft PUT dönüşü `readiness_invalidated: true`
→ `["allocation"]+["readiness"]+["mainboard"]+["audit"]` invalidate (Ready Check bu draft'ı okuyor);
revision dönüşünde bu bayrak YOK → `["allocation"]+["audit"]`; validate yalnız `["audit"]` (draft'ı
oynatmaz); sync hiçbir şey invalidate etmez.

**Reuse anchor'ları (kesin semboller):**
- **`lib/allocation.ts` (yeni):** wire tipleri `AllocationDraftResponse`/`AllocationDraft`/
  `AllocationEntry`/`AllocationCandidate`/`AllocationIssue`/`DerivedAmounts`/`SleeveAmount`/
  `SaveDraftResult`/`AllocationValidationReport`/`SyncPreview`/`RevisionResult` +
  `AllocationDraftInput`/`AllocationEntryInput`; taksonomi aynaları `ALLOCATION_CURRENCIES`(4)/
  `COMPOUNDING_MODES`(2)+`COMPOUNDING_MODE_LABELS`/`ALLOCATION_STATE_LABELS`+`_TONES` (UPPERCASE
  `NOT_SELECTED|NOT_READY|READY_WITH_WARNINGS|READY` — doc-14 lowercase readiness'ten AYRI) +
  `allocationStateLabel`/`allocationStateTone`; `["allocation"]` hook'ları (özel SSE YOK →
  `resource.changed` süpürür): `useAllocationDraft(compositionId)` / `useSaveAllocationDraft` /
  `useValidateAllocation` / `useSyncPreview` / `useCreateAllocationRevision`.
- **`pages/Portfolio.tsx` (yeni):** default-Mainboard composition bağlamı (RUN/Ready Check deseni);
  `DraftEditor` `key={row_version}` ile her server head hareketinde REMOUNT → yerel state server
  draft'ından yeniden tohumlanır (asla merge edilmez); mutation state PARENT'ta (FutureDev
  registry_version-bump remount dersi — save/validate/sync/revision sonuçları remount'u atlatır);
  `EntriesTable` (active checkbox + share input + Remove) / `CandidatePicker` / `SaveResultCard`
  (inline_issues + "re-run Ready Check" uyarısı) / `ValidateCard` / `SyncCard`
  (retained/missing/new_candidates + destructive-removal hint) / `RevisionCard`; issues + derived
  amounts VERBATIM render (istemci asla kapital matematiği hesaplamaz); `severityTone`
  `lib/readiness`'ten reuse.
- **`App.tsx`:** `/portfolio` REAL_PATHS 18→19 + gerçek Route (`nav.ts` UNCHANGED — 24; item zaten
  placeholder'dı). **Testler:** NEW `test/portfolio.test.tsx` +7 (empty draft + candidate picker /
  save body+headers+reseed [OCC 0-token, `item_type` gönderilmiyor asserti] / 409
  `ALLOCATION_DRAFT_CONFLICT` verbatim / validate raporu + header'sız body'siz POST / sync pure-read
  + destructive hint / revision OCC+Idem / `ALLOCATION_HAS_BLOCKERS` denial verbatim).

**Dürüst sınır:** sayfa yalnız default Mainboard composition'ını okur (RUN/Ready Check deseni;
Stage-3 gerçek Mainboard sayfası composition seçimini app-level'a taşıyabilir); Validate SAVED
draft'ı doğrular (yerel edit'leri değil — UI'da açıkça yazılı); sync preview'ın "Apply" düğmesi yok —
birleştirme editörde yapılıp Save ile uygulanır (doc 13 §14#9 açık-destructive-PUT sözleşmesi);
allocation'ın özel SSE event'i yok. **Backtest grubu TAM — kalan placeholder'lar: Workspace (4) +
Docs User Manual (1).**

## Stage post-V1 TIER 2 — User Manual page landed (PR #115)

**FRONTEND-ONLY (3 yeni + 2 edit, +1295 satır)** — backend UNCHANGED (**1048** sabit), migration YOK,
alembic head `0021_local_auth`, `ENGINE_VERSION` sabit. `/user-manual` placeholder'ı gerçek sayfa
oldu — `routes/manual.py`'nin TAM yüzeyi (7/7 endpoint, Stage 7a doc 21) bağlandı: all-role Published
reader stream + server-side search + Admin publish/upload/replace/soft-delete/restore zinciri.
**Docs nav grubu KAPANDI** (Future Dev #82 + User Manual #115). main = `6a4ba3b` (Merge #115), feat
`54fd4db`. CI yeşil; self-review 0 CRITICAL/HIGH. **frontend 181 → 189** (+8 vitest).

**AMPİRİK route haritası (imzalar OKUNDU — PR #105/#111/#113 dersi):**

| Endpoint | OCC | Idempotency-Key |
|---|---|---|
| `GET /manual/stream` + `GET /manual/search` | — (meta `stream_version` snapshot taşır) | — |
| `POST /admin/manual/documents` (create) | **BODY-form `expected_stream_version` INT** (server'da optional; client HER ZAMAN render edilen snapshot ile korur — UM-13/UM-15) | taze key/deneme |
| `POST /admin/manual/documents:upload` | body `expected_stream_version` | taze key/deneme |
| `POST .../{id}/revisions` | **BODY-form `expected_head_revision_id` STR** (route body'yi If-Match'e tercih eder) | taze key/deneme |
| `DELETE .../{id}` | body `expected_stream_version` — **DELETE opsiyonel BODY taşır** (`api.del` body/header almaz → `apiRequest` doğrudan) | taze key/deneme |
| `POST .../{id}:restore` | YOK (body yok) — **`require_trash_admin`** (manual admin DEĞİL) | taze key/deneme |

Stale stream token → 409 `MANUAL_STREAM_CONFLICT`; hareket etmiş head → 409 `MANUAL_REVISION_CONFLICT`
(ikisi de verbatim); duplicate içerik → `MANUAL_DUPLICATE_CONTENT` (`allow_duplicate` audited
override); baseline → `BASELINE_MANUAL_IMMUTABLE` (UM-10). `:restore` dönüşü Trash-core
`RestoreResult` — tip `lib/trash.ts`'ten REUSE. `get_manual_section` query'si ROUTE EDİLMEMİŞ
(doc 21 §12 — Agent Tool Gateway'e ait, HTTP yüzeyi değil).

**Reuse anchor'ları (kesin semboller):**
- **`lib/manual.ts` (yeni):** wire tipleri `ManualBlock`/`ManualSection`/`ManualStreamPage`/
  `ManualSearchResult` (`heading_path` STRING, liste değil!)/`ManualSearchPage`/`PublishResult`/
  `ReviseResult`/`DeleteResult`; `ACCEPTED_UPLOAD_EXTENSIONS` hydration aynası (.txt/.md/.markdown/
  .html/.htm — server `MANUAL_FILE_TYPE_UNSUPPORTED` ile yeniden doğrular); `["manual"]` hook'ları
  (özel SSE YOK → `resource.changed` süpürür): `useManualStream(cursor)` / `useManualSearch(q,cursor)`
  (boş sorgu FETCH ETMEZ — doc 21 §14) / `useCreateManualDocument` / `useUploadManualDocument`
  (boş title OMIT — filename stem'den türer) / `useReplaceManualRevision` /
  `useSoftDeleteManualDocument` (delete/restore `["trash"]`'i de invalidate eder — aynı tx'te Trash
  entry yazılıyor) / `useRestoreManualDocument`.
- **`pages/UserManual.tsx` (yeni):** kanonik blok renderer `BlockView` (heading{level,text}/
  paragraph{text}/bullet+ordered_list{items}/code{code_text,language}/callout{tone,title,text}/
  divider — yalnız TEXT node, bilinmeyen tip fail-closed null); baseline aksiyonları server-truth
  `is_baseline` bayrağından gizli (Trash `restore_eligible` deseni); iki adımlı delete onayı +
  delete sonucu PARENT'ta (`lastDelete` — section refetch'te kaybolmaz, Portfolio dersi); composers
  role ile client-gate edilmez (doc 21 §2 — non-Admin 403 verbatim görür); `SearchCard` yalnız
  submit'te arar + reader/search `stream_version` uyuşmazlığında "index may lag" notu.
- **`App.tsx`:** `/user-manual` REAL_PATHS 19→20 + gerçek Route (`nav.ts` UNCHANGED — 24).
  **Testler:** NEW `test/userManual.test.tsx` +8 (apiStub SIRALI — `:upload`/`:restore`/`/revisions`
  fragmanları create prefix'inden ÖNCE: create path'i hepsinin substring'i).

**Dürüst sınır:** revision replacement doc 21 §7'de "V18 UI not exposed" — 7/7 bağlamak için açık
Admin bakım affordance'ı olarak sunuldu (PR #95 gated-POST emsali; server uçtan uca gate'ler);
upload UTF-8 METİN taşır (route sözleşmesi `content: str` — ham bayt sayfadan geçmez; PDF/DOCX V1
değil); manual'ın özel SSE event'i yok; Trash purge ayrı re-auth slice'ı. **Docs grubu TAM — kalan
placeholder'lar: Workspace (4: strategy / outsource-signal / trading-signal / trade-log).**

## Stage post-V1 TIER 2 — Strategy Details page landed (PR #117)

**FRONTEND-ONLY (3 yeni + 1 edit, +1501 satır)** — backend UNCHANGED (**1048** sabit), migration YOK,
alembic head `0021_local_auth`, `ENGINE_VERSION` sabit. `/strategy` placeholder'ı gerçek sayfa oldu —
`routes/strategy.py`'nin TAM yüzeyi (9/9 endpoint, Stage 3b doc 02 §7–§9) bağlandı: editor draft
workflow (create root+draft / full-payload PATCH / pure validate / save immutable revision / clear)
+ root header + revision history + immutable revision deep-link. main = `fcbbfb6` (Merge #117), feat
`8e5e068`. CI yeşil; self-review 0 CRITICAL/HIGH. **frontend 189 → 197** (+8 vitest).

**AMPİRİK route haritası (imzalar OKUNDU — PR #105/#111/#113/#115 dersi):**

| Endpoint | OCC | Idempotency-Key |
|---|---|---|
| `POST /strategy-drafts` (201) | YOK (create'in head'i yok) — `display_name` command-REQUIRED (route'ta optional) | taze key/deneme |
| `PATCH /strategy-drafts/{id}` | **BODY-form `expected_draft_row_version` INT** (body If-Match'e galip; ZORUNLU — yoksa 422; draft row_version **0'dan** başlar, 0 geçerli token) | taze key/deneme |
| `POST .../{id}/validate` | — (body/header OKUMAZ; saf compiler pass, audit satırı YOK → invalidation YOK) | YOK |
| `POST .../{id}/save` (201) | body `expected_draft_row_version` | taze key/deneme |
| `POST .../{id}/clear` | body `expected_draft_row_version` | taze key/deneme |
| `GET /strategy-drafts/{id}` · `/strategies/{root}` · `/strategies/{root}/revisions?limit=` (**BARE LIST**, envelope yok) · `/strategy-revisions/{id}` | — | — |

Stale token → 409 `STRATEGY_DRAFT_CONFLICT` verbatim (AT-19, asla last-write-wins). Bloklu save →
422 (`STRATEGY_VALIDATION_FAILED`/`SIZING_METHOD_NOT_EXCLUSIVE`/`TRIGGER_SOURCE_CONDITION_REQUIRED`)
+ compiler issue listesi `error.details`'te (verbatim render). save aynı tx'te bağlı Mainboard
item'larını yeni mirror revision'a re-pin eder (composition_hash oynar → önceki Ready raporu STALE)
→ `["strategy"]+["mainboard"]+["readiness"]+["audit"]` invalidate. `draft_id` bağımsız `stratdraft`
ULID — **root→draft lookup endpoint'i YOK** → sayfa draft handle'ını URL'de taşır (`?draft=`).

**Reuse anchor'ları (kesin semboller):**
- **`lib/strategy.ts` (yeni):** wire tipleri `StrategyDraft`/`StrategyDetail`/`StrategyRevisionRow`/
  `StrategyReference`/`StrategyRevisionDetail`/`CreateDraftResult`/`PatchDraftResult`/`StrategyIssue`
  (`{field,code,message}`)/`ValidateDraftResult`/`PinnedMainboardItem`/`SaveRevisionResult`
  (`ready_state="STALE"` sabiti — save asla Ready PASS değil)/`ClearDraftResult`; taxonomy aynaları
  `STRATEGY_LIFECYCLE_LABELS/_TONES` + `VALIDATION_STATUS_TONES` (+ `lifecycleLabel`/`lifecycleTone`/
  `validationStatusTone`); `["strategy"]` hook'ları (özel SSE YOK → `resource.changed` süpürür):
  `useStrategyDraft`/`useStrategy`/`useStrategyRevisions` (bare list)/`useStrategyRevision`
  (immutable, 5m staleTime) + `useCreateStrategyDraft`/`usePatchStrategyDraft` (full-payload
  replacement — shallow `patch` server'da var, UI kullanmıyor)/`useValidateStrategyDraft`
  (invalidation YOK)/`useSaveStrategyRevision`/`useClearStrategyDraft`.
- **`pages/StrategyDetails.tsx` (yeni):** URL modları `?draft=`/`?strategy=`/`?revision=`;
  `PayloadEditor` `key={row_version}` remount-reseed (asla merge); mutation state PARENT
  `DraftWorkbench`'te (Portfolio dersi); bozuk JSON client'ta kalır ("Not sent — invalid JSON");
  Clear iki adımlı onay; `AttachedStrategiesCard` default Mainboard'ın `item_kind==="strategy"`
  item'larından keşif; `MutationErrorCard` 422 `details`'i verbatim listeler.
- **`App.tsx`:** `/strategy` REAL_PATHS 20→21 + gerçek Route (`nav.ts` UNCHANGED — 24).
  **Testler:** NEW `test/strategy.test.tsx` +8 (apiStub SIRALI — draft-aksiyon fragmanları
  `POST /strategy-drafts` create prefix'inden ÖNCE; `/strategies/{root}/revisions` root GET'ten ÖNCE).

**Dürüst sınır:** strateji LIST endpoint'i YOK — keşif default Mainboard'a bağlı item'lardan; hiç
attach edilmemiş bir strateji yalnız create anındaki `?draft=` URL'i ile erişilir; Mainboard ATTACH
bu yüzeyin dışında (Stage 3a mainboard operasyonu); payload editörü ham JSON (semantik otorite
yalnız server compiler'ı — issue'lar verbatim). **Workspace kalan: trading_signal / trade_log /
outsource-signal (3 placeholder).**

## Stage post-V1 TIER 2 — Trading Signal & Trade Log pages landed (PR #119)

**FRONTEND-ONLY (6 yeni + 1 edit, +2690 satır)** — backend UNCHANGED (**1048** sabit), migration YOK,
alembic head `0021_local_auth`, `ENGINE_VERSION` sabit. `/trading-signal` + `/trade-log`
placeholder'ları TEK slice'ta gerçek sayfa oldu — `routes/trading_signal.py` + `routes/trade_log.py`
İKİZ yüzeylerinin TAMAMI (6+6 endpoint, Stage 3c/3d doc 04/05) bağlandı: immutable TXT/CSV source
asset upload (content-addressed dedup) → durable 202 import job → import report → Save & Add native
work object → OCC-guarded revision append. main = `7fd70dd` (Merge #119), feat `038187f`. CI yeşil;
self-review 0 CRITICAL/HIGH. **frontend 197 → 208** (+11 vitest: 6 TS + 5 TL).

**AMPİRİK route haritası (imzalar OKUNDU — iki router bire bir simetrik):**

| Endpoint (her iki prefix) | OCC | Idempotency-Key |
|---|---|---|
| `POST .../source-assets` (201) | YOK — content-addressed: aynı içerik `deduplicated:true` ile önceki asset'i döner | taze key/deneme (route okuyor) |
| `POST .../imports` (202) | YOK — durable jobs satırı (data queue, CR-09; browser kapansa da yaşar) | taze key/deneme |
| `GET .../imports/{job_id}` | — | — |
| `POST /trading-signals` · `/trade-logs` (201, create & attach) | YOK (create'in head'i yok); `workspace_id` HİÇ gönderilmez — server default Mainboard'ı çözer | taze key/deneme |
| `POST .../{root_id}/revisions` (201) | **BODY-form `expected_head_revision_id` STR** (server'da optional — client HER ZAMAN rendered head'i gönderir; stale → 409, asla last-write-wins) | taze key/deneme |
| `GET .../{root_id}` | — | — |

**İKİZ FARKLAR (verbatim aynalandı):** (1) report kanıt anahtarı — TS `normalized_event_revision_id`
vs TL `record_batch_revision_id` (import_binding'de de aynı fark); (2) TL revizyonları HER ZAMAN
`available_time=null` (historical ledger, doc 05 §10.4 — anti-lookahead availability sözleşmesi yok),
TS earliest-accepted-event taşır; (3) config şekli — TS `time_policy`+`event_model` vs TL `time_model`;
(4) hata taksonomileri ayrı. Pin ("Use This Revision") + delete bu router'larda YOK — Mainboard
router'ı REUSE edilir (CR-01/TL-01: work object, package değil).

**SSE kazanımı:** import report `["jobs", "<kind>-import", jobId]` anahtarıyla bağlandı — **`job.updated`
SSE anahtarının İLK sayfa bağlaması** (PR #67 forward-contract'ının son açık anahtarı). Poll fallback
`TERMINAL_IMPORT_STATUSES` (succeeded/failed/cancelled/failed_final/superseded) üzerinde durur
(INF-11). "`["jobs"]` bağlanamaz" sınırı LİSTE yüzeyi için geçerliydi (o hâlâ yok — kalıcı);
job-scoped report READ'i anahtarı canlandırdı. Work-object anahtarları `["trading-signals"]` /
`["trade-logs"]` özel SSE event'siz → `resource.changed` süpürür.

**Invalidation:** create-with-attach → kendi anahtarı + `["audit"]` + (result.attached ise)
`["mainboard"]`+`["readiness"]` (composition_hash oynar → önceki Ready raporu STALE); revisions
ASLA auto-repin yapmaz (doc 04 rule 9 / doc 05 Rule 10) → yalnız kendi anahtarı + `["audit"]`;
upload → `["audit"]`; import request → `["jobs"]`+`["audit"]`.

**Reuse anchor'ları (kesin semboller):**
- **`lib/tradingSignal.ts` (yeni):** `UploadSourceAssetResult`/`RequestImportResult`/
  `SignalImportReport`/`WorkObjectRevisionView`/`TradingSignalDetail`/`CreateTradingSignalResult`/
  `CreateSignalRevisionResult`; `SIGNAL_SOURCE_EXTENSIONS` (.txt/.csv) + `TERMINAL_IMPORT_STATUSES`
  + `buildSignalPayloadTemplate` (§9.2 iskeleti, import binding enjekte — hydration-only, otorite
  server compiler); hook'lar `useTradingSignal`/`useSignalImportReport` (["jobs"] altında, terminal-stop
  poll)/`useUploadSignalSource`/`useRequestSignalImport`/`useCreateTradingSignal`/`useCreateSignalRevision`.
- **`lib/tradeLog.ts` (yeni):** ikiz tipler `TradeLogImportReport`/`TradeLogDetail`/`CreateTradeLogResult`/
  `CreateTradeLogRevisionResult` + `buildTradeLogPayloadTemplate` (§10.2 — `time_model`,
  `content_profile`, `trade_log_entry_exit_price`, record-batch binding); paylaşılan
  `UploadSourceAssetResult`/`RequestImportResult`/`WorkObjectRevisionView`/`TERMINAL_IMPORT_STATUSES`
  tradingSignal'den import; hook'lar `useTradeLog`/`useTradeLogImportReport`/`useUploadTradeLogSource`/
  `useRequestTradeLogImport`/`useCreateTradeLog`/`useCreateTradeLogRevision`.
- **`pages/TradingSignal.tsx` + `pages/TradeLog.tsx` (yeni, simetrik):** URL modları `?job=` (durable
  import handle) / `?root=` (detail + revision composer); `Workbench` upload→import→report→create
  zinciri — mutation state + instrument/tz state PARENT'ta; `CreateCard` `key={<report revision id> ??
  "blank"}` remount-reseed; `RevisionComposer` `key={current_revision_id}`; bozuk JSON client'ta kalır;
  keşif `AttachedSignalsCard`/`AttachedTradeLogsCard` (default Mainboard `item_kind` filtresi).
- **`App.tsx`:** REAL_PATHS 21→23 + iki gerçek Route (`nav.ts` UNCHANGED — 24).
  **Testler:** NEW `test/tradingSignal.test.tsx` +6 / `test/tradeLog.test.tsx` +5 (apiStub SIRALI —
  `source-assets`/`imports`/`{root}/revisions` POST fragmanları çıplak create prefix'inden ÖNCE).

**Dürüst sınır:** work-object LIST endpoint'i YOK — keşif default Mainboard item'larından; hiç attach
edilmemiş nesne yalnız create-result `?root=` linkiyle erişilir; upload UTF-8 TEXT taşır (route
sözleşmesi `content: str` — ham bayt sayfadan geçmez); Pin/delete Mainboard operasyonu (bu sayfalarda
değil); deep-link `?job=` senaryosunda template timezone'u "UTC" default'una düşer (report tz taşımaz).
**Workspace kalan: outsource-signal (SON placeholder).**

## Stage post-V1 TIER 2 — ESP registry mutation actions landed (PR #121)

**FRONTEND-ONLY (3 edit, +720/−15 satır)** — backend UNCHANGED (**1048** sabit), migration YOK,
alembic head `0021_local_auth`, `ENGINE_VERSION` sabit. `routes/esp.py`'nin 3 MUTASYON endpoint'i
mevcut Embedded System Packages sayfasına (`/packages/embedded`, doc 09 §5/§8/§10) bağlandı —
okuma yüzeyi PR #99'daydı → **`esp.py` yüzeyi TAM** (`library.py` zaten 2/2 → Packages & Data
grubunda bağlanmamış endpoint KALMADI). Propose (create) CANDIDATE + Admin-only activate
(candidate → trusted_active) + deprecate (trusted_active → deprecated).
main = `45e615b` (Merge #121), feat `b692aaa`. CI 3/3 yeşil; self-review 0 CRITICAL/HIGH.
**frontend 208 → 213** (+5 vitest).

**AMPİRİK route haritası (imzalar OKUNDU):**

| Endpoint | X-Registry-Version (OCC) | Idempotency-Key | Admin-only |
|---|---|---|---|
| `POST /embedded-system-packages` (create, 201) | YOK | YOK | YOK — herhangi authenticated actor CANDIDATE önerir (doc 09 §5) |
| `POST /{id}/activate` | VAR (header) | VAR | VAR (`ensure_can_activate`) |
| `POST /{id}/deprecate` | VAR (header) | VAR | VAR (`ensure_can_deprecate`) |

OCC token = **`X-Registry-Version` HEADER-form DÜZ INT** (`int(strip('"'))` — If-Match `"rv-N"`
ETag DEĞİL; kaynak `detail.registry.registry_version`); stale → 409 `RESOLVER_REGISTRY_CONFLICT`.
Create'in head'i yok → OCC + Idem YOK. Admin gate command katmanında (`actor.is_admin`) — UI asla
pre-gate etmez; non-Admin → 403 `APPROVAL_REQUIRES_ADMIN` verbatim. `canActivate` (yalnız
`candidate`'ten) / `canDeprecate` (yalnız `trusted_active`'ten) UI-hint state-machine aynası
(`domain/esp/state_machine.py`) — server geçişi VE Admin gate'i yeniden doğrular.

**Invalidation:** her üç mutasyon → `["esp"]` + `["audit"]` (her command audit yazar); ESP'nin
özel SSE event'i yok (kalıcı) → `resource.changed` `["esp"]`'i süpürür.

**Reuse anchor'ları (kesin semboller):**
- **`lib/esp.ts` (genişletildi):** `CreateEspResult`/`ActivateResolverResult`/
  `DeprecateResolverResult` (command dönüş dict'lerinin verbatim aynası) + `CreateEspInput`/
  `ActivateResolverInput`/`DeprecateResolverInput`; `VISIBILITY_SCOPES` mirror
  (private/explicitly_shared/published/system); `postWithRegistryVersion` helper
  (X-Registry-Version + taze Idempotency-Key/deneme); `useCreateEsp` (`api.post`, OCC/Idem'siz) +
  `useActivateResolver`/`useDeprecateResolver`; `canActivate`/`canDeprecate`.
- **`pages/Embedded.tsx`:** `ProposeResolverCard` (herhangi authenticated; signature params
  `parseSignatureParams` REUSE; key + [params VEYA return] yoksa disabled — server
  `RESOLVER_CONTRACT_INVALID` guard'ının aynası) + detail'de `LifecycleActions` →
  `ActivateComposer` (head revision default, düzenlenebilir) / `DeprecateComposer` (reason
  ZORUNLU, opsiyonel replacement); 409/403 verbatim. `App.tsx`/`nav.ts` UNCHANGED (Embedded
  zaten route'luydu — REAL_PATHS 23, nav 24 sabit).
- **`test/embedded.test.tsx` +5:** activate OCC header ("2") + body `{revision_id, canonical_key}`
  + state gating (candidate'te Deprecate YOK); deprecate reason-gated + OCC ("4") + body; propose
  OCC/Idem'siz + signature verbatim + visibility default `private`; propose disabled-until-valid;
  403 `APPROVAL_REQUIRES_ADMIN` verbatim. Mevcut 2 resolve-probe testi `within(region)` ile
  scope'landı (Propose formu aynı label'ları kullanıyor).

**Dürüst sınır:** gelişmiş kontrat alanları (`input_contract`/`output_contract`/
`dependency_snapshot`/`evidence`) propose formunda YOK — server default (`{}`/null); signature
(params+return) kimlik girdisi. Activation default head revision'ı trust eder (düzenlenebilir);
server ownership + head'liği yeniden doğrular. **Workspace kalan: outsource-signal (SON
placeholder — backend'de ayrı router YOK, doc 03 keşfi ŞART).**

## Stage post-V1 TIER 2 — Add Outsource Signal chooser page landed (PR #123)

**FRONTEND-ONLY (2 yeni + 1 edit, +238 satır)** — backend UNCHANGED (**1048** sabit), migration
YOK, alembic head `0021_local_auth`, `ENGINE_VERSION` sabit. `/outsource-signal` placeholder'ı
gerçek sayfa oldu — doc 03 external-work TİP SEÇİCİsi; Workspace'in (ve TÜM TIER 2 sayfa
haritasının) SON placeholder'ıydı → **REAL_PATHS 23 → 24, placeholder KALMADI — TIER 2 SAYFA
HARİTASI TAMAM**. main = `2f8d28f` (Merge #123), feat `be2aa8a`. CI yeşil.
**frontend 213 → 219** (+6 vitest).

**AMPİRİK scope bulgusu (doc 03 TAM okundu; kapsam kullanıcıyla teyitleşildi):** seçici yüzey
HİÇBİR backend mutasyonu yapmaz — §7.1 `start_transient_outsource_draft` = "transient UI
acknowledgement only or local state creation" (root/revision/audit YOK); tüm alan sözleşmeleri +
save/import akışları doc 04/05'in malı ("burada tekrar edilmeleri kapsam ihlalidir", §5) ve
PR #119'da TAM bağlı. Backend'de "outsource" yalnız `shared/errors.py:624` YORUM başlığında —
router YOK ve spec gereği GEREKMİYOR → slice frontend-only, YENİ endpoint binding'i YOK (kickoff
uyarısındaki "yeni backend slice'ı gerekebilir" sorusunun ampirik cevabı: HAYIR).

**Reuse anchor'ları (kesin semboller):**
- **`pages/OutsourceSignal.tsx` (YENİ):** tam iki kanonik seçim (`trading_signal` | `trade_log`,
  CR-01 — PackageKind genişlemez) workbench'lere react-router `Link` (`TypeChoice`); doc 03 §6.2
  chooser + seçim-başı helper'lar ve §6.1 ⓘ kataloğu (3 panel: `outsourceSignalInfo` /
  `outsourceTypeInfo` / `unsavedExternalDraftInfo`) VERBATIM nihai metin (`InfoPanel`, native
  `<details>/<summary>` — ARIA'sız klavye erişimi); sınır kartı (seçici ne YAPMAZ: mutasyon yok;
  attach/pin/delete Mainboard operasyonu). Hook/query key/fetch YOK. Doğrudan seçim linkleri
  "seçimsiz devam" state'ini KURULAMAZ kılar → AOS-02 yapısal sağlanır (ID-03-01/ID-03-04: V18
  hover submenu → SPA'da adanmış seçici sayfası; transient draft = child workbench compose
  editörü).
- **`App.tsx`:** `/outsource-signal` REAL_PATHS (23→24) + `ErrorBoundary`'li route; `nav.ts`
  UNCHANGED (24 item — nav girdisi zaten vardı).
- **`test/outsourceSignal.test.tsx` (+6):** tam-iki-seçenek + href'ler (AOS-01); §6.2/§6.1
  verbatim metin; iki workbench'e tıkla-git (MemoryRouter route probe); stubbed-fetch sıfır-trafik
  guard'ı (§7.1 aynası). QueryClientProvider GEREKMEZ (sayfa hook bağlamaz).

**Dürüst sınır:** seçici rolü pre-gate etmez (doc 03 §2 — UI görünürlüğü yetki değildir);
"Unsaved draft" BADGE'i child workbench editörlerinin doc 04/05 yüzey detayı — bu slice TS/TL
sayfalarına DOKUNMADI (buradaki §6.1 paneli semantiği belgeliyor); attach/pin/delete Stage-3a
Mainboard operasyonları olarak KALIYOR (`routes/mainboard.py` 8 endpoint'ten yalnız
`GET /mainboards/default` bağlı; `pages/Mainboard.tsx` 55 satır, veri bağlamıyor → sıradaki
doğal büyük aday).

## Stage post-V1 TIER 2 — Mainboard composition page landed (PR #125)

**FRONTEND-ONLY** (1 yeni `lib/mainboard.ts` + 1 yeni `test/mainboard.test.tsx` + `pages/Mainboard.tsx`
yeniden yazımı; backend DEĞİŞMEDİ, migration YOK, alembic head `0021_local_auth` sabit,
`ENGINE_VERSION` sabit, backend test tabanı 1048 sabit). Index `/` Mainboard, Stage-0 meta/health
shell'inden gerçek **kompozisyon düzlemine** dönüştü (doc 01). `routes/mainboard.py`'nin **bağsız 7
endpoint'i** bağlandı (GET default zaten `lib/backtest.ts` `useDefaultMainboard` ile bağlıydı) →
**`mainboard.py` yüzeyi TAM**. **KALICI dürüst sınır kapandı:** attach + Pin ("Use This Revision") +
work-object soft-delete artık gerçek landed bir sayfada. main = `8fce88a` (Merge #125), feat `43b9063`.

**Ampirik OCC/Idem (route imzaları OKUNDU):** `POST /external-work-object-drafts/{kind}` Idem/OCC
YOK (transient, `async` değil → TS/TL workbench deep-link) · create/attach/snapshot/delete Idem-var,
OCC-yok · `POST /work-objects/{root}/revisions` BODY `expected_head_revision_id` STR (opsiyonel) ·
`PATCH /mainboard-items/{item}` BODY `expected_row_version` INT REQUIRED (body If-Match'ten öncelikli;
tek intent/çağrı: pin_revision|set_enabled|reorder|set_label) · `DELETE /work-objects/{root}` gövdesiz.

**Reuse anchor'ları:** `lib/mainboard.ts` (wire tipleri command dönüşünden VERBATIM + `useDefaultMainboard`
re-export + §6.2 ready-status text/tone kataloğu + `itemKindLabel`/`EXTERNAL_DRAFT_KINDS` + 7 hook
`["mainboard"]` altında — özel SSE event yok, `resource.changed` süpürür; kompozisyon mutasyonları
`["mainboard"]+["readiness"]+["audit"]`, delete +`["trash"]`, snapshot yalnız `["audit"]`) ·
`pages/Mainboard.tsx` (kompozisyon özeti + item-başına genişleyen operasyon paneli [row_version OCC'li
Pin/Enable-Disable/Move/Label + iki-adımlı soft-delete §6.2 metni VERBATIM] + Add Outsource Signal
opener + Advanced generic work object; row expand/collapse SUNUM-ONLY AT#7; empty-state VERBATIM) ·
`test/mainboard.test.tsx` +9 (apiStub SIRALI — `{root}/revisions` çıplak create prefix'inden ÖNCE) →
**frontend 219 → 228**; typecheck + lint temiz, build yeşil.

**Dürüst sınır:** Add Strategy draft + Add Package derive (`POST /strategy-drafts`) Strategy Details
router'ında (doc 02, `/strategy`), `mainboard.py`'de değil; Ready Check + RUN landed `/backtest/*`
sayfaları (doc 14 §9.3); Mainboard'a özel SSE event yok; `ready_summary` hâlâ backend `not_ready`
placeholder'ı, `latest_result_summary` runs bağlanana kadar null.

## Stage post-V1 TIER 2 — Trash Permanent Delete (purge) actions landed (PR #127)

**FRONTEND-ONLY** (`lib/trash.ts` + `pages/Trash.tsx` + `styles/global.css` + `test/trash.test.tsx`;
backend DEĞİŞMEDİ, migration YOK, alembic head `0021_local_auth` sabit, `ENGINE_VERSION` sabit,
backend test tabanı 1048 sabit). PR #86'nın restore-only sınırı kapandı: son bağsız
`routes/trash.py` endpoint'i (`POST /trash-entries/{id}/purge`, doc 20 §8.3) bağlandı →
**`trash.py` yüzeyi TAM**. main = `77b6b61` (Merge #127), feat `7ae3428`.

**Ampirik OCC/Idem (route + command imzaları OKUNDU):** İki-aşamalı **202** — request yalnızca hedefi
`purge_pending`'e taşır + durable maintenance job enqueue eder; asıl purge'ü **worker** yürütür (worker
eligibility'yi yeniden doğrular). Gövde **REQUIRED** `confirmation_phrase` + `reauth_proof`:
`confirmation_phrase` objenin **display kimliğine** (`display_name || entity_id`) EŞİT olmalı yoksa
server `PURGE_CONFIRMATION_INVALID` ile reddeder (hiç başlamaz); `reauth_proof` boş olamaz (V1
**varlık-kontrollü** kontrat, tam MFA kapsam dışı doc 20 §0) yoksa `REAUTH_REQUIRED`. OCC =
**BODY-form `expected_row_version` INT** (body If-Match'ten öncelikli, doc 20 §14) = entry `row_version`;
stale → `STALE_REVISION`. Her denemede taze `Idempotency-Key` (aynı key ile tekrar submit aynı job'ı
döner). Purge, Restore ile **AYNI recoverable statülerde** uygun (command `_assert_entry_recoverable`'ı
paylaşır) → sayfa aksiyonu server-truth `restore_eligible` flag'ı üzerinden gate eder (backend
değişikliği gerekmez).

**Reuse anchor'ları:** `lib/trash.ts` (`PurgeResult` wire tipi — `request_purge` dict'inden VERBATIM,
NB `display_name` İÇERMEZ + `useRequestPurge` — Idempotency-Key header + body-OCC token, invalidate
`["trash"]+["audit"]`) · `pages/Trash.tsx` (Permanent Delete → açık **iki-adımlı `PurgeComposer`**;
doc 20 §9 onay metni VERBATIM; Confirm server ön-koşullarını aynalar — tam isim + boş-olmayan proof,
server yeniden doğrular; §9 kabul toast'ı için display name'i **kabul anında yakalar** çünkü 202 dönüşü
`display_name` içermez) · `.btn-danger` style. `test/trash.test.tsx` +4 → **frontend 228 → 232**;
typecheck + lint temiz, build yeşil. Review 0 CRITICAL/HIGH.

**Dürüst sınır:** purge yalnızca bir **request** — asıl purge'ü worker yürütür (durum `["trash"]`
projeksiyonundan okunur, özel SSE event yok, `resource.changed` süpürür); re-auth proof V1'de yalnız
varlık-kontrollü (gerçek MFA challenge yok).

## Stage post-V1 TIER 3 — Data-queue operator redelivery landed (PR #129)

**BACKEND-ONLY** (`application/jobs/data_queue.py` + `application/commands/data_queue.py` NEW; 4 data
command payload'ı + `apps/worker/actors.py` + `routes/admin_panel.py` EDIT; migration YOK, alembic head
`0021_local_auth` SABİT, `ENGINE_VERSION` SABİT, frontend DEĞİŞMEDİ 232). main = `2829514` (Merge #129),
feat `986ede7`. CI yeşil. Backend **1048 → 1054** (+3 unit / +3 integration).

**Sorun (INF-03, doc 20 §6):** çok-actor'lı `data` queue (market/research analysis + TS/TL import)
scheduler auto-redelivery'sinden (`ACTOR_BY_QUEUE`) KASTEN dışlanmış — kayıp broker mesajı durable
`jobs` satırını sonsuza dek QUEUED bırakır, ama satırdan hangi actor olduğu ayırt edilemez (market vs
research aynı `{entity_id,revision_id}` payload; TS vs TL aynı `{source_asset_id,...}` payload — hiç
discriminator yoktu). Scheduler yorumu "re-dispatch is an operator action" diyordu ama böyle bir
operator aracı YOKTU → takılı data job sonsuza dek QUEUED kalıyordu.

**ÖNEMLİ karar — retention auto-purge YAPILMADI:** kardeş TIER 3 adayı doc 20 §16'da açıkça
*"Automatic purge remains disabled in Production V1"* → Future-Dev sınırı, uygulanabilir slice DEĞİL
(purge her zaman explicit Admin confirm+re-auth). Onun yerine spec-uyumlu data-queue redelivery
inşa edildi (kullanıcı ile teyitli seçim).

**Reuse anchor'ları:** `application/jobs/data_queue.py` — `DATA_QUEUE`, 4 `job_kind` sabiti
(`MARKET_DATA_ANALYSIS`/`RESEARCH_DATA_ANALYSIS`/`TRADING_SIGNAL_IMPORT`/`TRADE_LOG_IMPORT`),
`DATA_JOB_KINDS`, `data_job_kind(payload)` (legacy/bilinmeyen/yanlış-tip → `None`, ASLA tahmin),
`list_redeliverable_data_jobs(session, *, grace_seconds, now=None)` (QUEUED `data` satırları grace
sonrası, oldest-first, kind resolved) · 4 data enqueue payload'ı artık `"job_kind"` taşır (JSONB
additive, sabit import edilir — yanlış-literal riski yok) · `apps/worker/actors.py::DATA_ACTOR_BY_KIND`
(kind→actor; scheduler DOKUNULMADI — `data` operator-only kalır) ·
`commands/data_queue.py::redeliver_data_queue_jobs(session, actor, *, grace_seconds)`
(`require_admin_panel`; `data_queue.redelivery_requested` audit+outbox bir kez; dönüş
`{scanned, redeliverable:[{job_kind,job_id}], skipped_unknown_kind}`; dispatch route'ta, trash `_dispatch`
deseni) · `POST /admin/data-queue/redeliver` (Admin, opsiyonel `grace_seconds` query; `0` her QUEUED
data job'ı süpürür; `DATA_ACTOR_BY_KIND` ile send_job).

**Dürüst sınır (KALICI):** re-dispatch OPERATOR aksiyonu kalır (scheduler ASLA `data`'yı auto-route
etmez, doc 20 §6); discriminator ÖNCESİ enqueue edilmiş legacy satırlar `job_kind` taşımaz →
`skipped_unknown_kind` sayılır (geçici/nadir, asla tahmin edilmez); redelivery idempotent (durable satır
dokunulmaz, QUEUED kalır; data-plane worker'lar güvenle replay); `["jobs"]` HTTP LİSTE yüzeyi hâlâ
YOK — bu bir POST recovery aksiyonu, browser DEĞİL; operator ayrı rol değil = Admin (`require_admin_panel`).

## Stage post-V1 TIER 2 — Data-queue redelivery operator recovery card landed (PR #131)

**FRONTEND-ONLY** (backend değişmedi, migration yok, alembic head `0021_local_auth` SABİT,
`ENGINE_VERSION` SABİT, backend test base **1054** sabit; frontend **232 → 235**). Landed backend
operator-recovery endpoint'ini (PR #129, INF-03, doc 20 §6) `/panel` sayfasına bağlar — `data`-queue
redelivery için opsiyonel Admin UI paneli TIER 3 adayı KAPANDI (kullanıcıyla teyitli seçim).

**Ne yapıldı:** `POST /admin/data-queue/redeliver`'i Panel'e bir `OperatorRecoveryCard` olarak bağlar.
3 dosya, +264 satır, salt-ekleme; `App.tsx`/`nav.ts` DEĞİŞMEDİ (`/panel` zaten real).
- `lib/adminPanel.ts` (salt ekleme): `DataQueueRedeliverResult`/`DataQueueRedeliverable` wire tipleri
  (`commands/data_queue.py::redeliver_data_queue_jobs` dönüş dict'i VERBATIM →
  `{scanned, redeliverable:[{job_kind,job_id}], skipped_unknown_kind}`) + `DATA_JOB_KIND_LABELS`/
  `dataJobKindLabel` (`application/jobs/data_queue.py` `DATA_JOB_KINDS` okunabilir etiket aynası —
  yalnız hydration, server tek otorite) + `useRedeliverDataQueue` (route yalnız opsiyonel
  `grace_seconds` query okur, `ge=0`, `0`=hepsi → **OCC token / Idempotency-Key YOK**; başarıda
  `["audit"]` invalidate — command bir `data_queue.redelivery_requested` audit+outbox yayar, süpürülecek
  data-queue read yüzeyi yok).
- `pages/Panel.tsx` (salt ekleme): `OperatorRecoveryCard` — grace-seconds ipucu input'u (boş=server
  penceresi, `0`=hepsi), routable sonuç tablosu (server job_kind etiketleri + job id), scanned/
  re-dispatched/skipped sayaçları, un-routable legacy-satır notu (sayılır, ASLA tahmin edilmez); Admin-only
  server-side (non-Admin 403 zarfı VERBATIM); client negatif/ondalık grace'i dispatch öncesi engeller
  (server yine `ge=0` doğrular).
- `test/panel.test.tsx` +3 → **235**: routable render + query'siz default POST · `grace_seconds=0`
  süpürme + empty-state · geçersiz-grace client bloklama.

typecheck+lint temiz, build green, 235/235. Review 0 CRITICAL/HIGH (route imzası ampirik okundu →
VERBATIM aynalandı). **Dürüst sınır (KALICI):** re-dispatch OPERATOR aksiyonu kalır (scheduler `data`'yı
ASLA auto-route etmez, doc 20 §6); legacy satırlar `skipped_unknown_kind`; `["jobs"]` HTTP LİSTE yüzeyi
YOK (bu bir POST recovery aksiyonu); operator = Admin (`require_admin_panel`).

## Stage post-V1 TIER 3 — SSE reconnect backoff resilience landed (PR #133)

**FRONTEND-ONLY** (2 dosya; backend değişmedi, migration YOK, alembic head `0021_local_auth` SABİT,
`ENGINE_VERSION` SABİT, backend test base **1054** sabit; frontend **235 → 238**). main = `ff92310`
(Merge #133), feat `a100930`. `lib/sse.ts::connectEvents` non-retryable stream close'u atlatır →
**SSE streaming e2e dayanıklılık TIER 3 adayı KAPANDI.**

**Sorun:** önceki hâlde `onerror` her hatayı `"closed"` sayıyordu ve **manuel reconnect YOKTU**. Tarayıcının
`EventSource`'u yalnız `readyState===CONNECTING` iken auto-retry yapar; sunucu akışı non-retryable
kapattığında / initial handshake fail'de `readyState=CLOSED` olur ve native retry **DURUR** → dashboard
kalıcı SSE-kör kalır, tam reload'a kadar hiç canlı invalidation almaz.

**Ne yapıldı:**
- `lib/sse.ts` (Edit): **readyState-aware `onerror`** — `CONNECTING` (native retry sürüyor) → status
  `"connecting"` (yanlış `"closed"` değil); `CLOSED` (native vazgeçti) → kendi **exponential backoff**
  reconnect'i (`RECONNECT_BASE_MS=1000` → `RECONNECT_MAX_MS=30000` cap). Reopen (native VEYA backoff) aynı
  gap full-refresh'i tetikler (INF-11); backoff ramp `open`'da sıfırlanır. `dispose` bekleyen reconnect
  timer'ı iptal eder + mevcut source'un listener'larını söker; her (re)open önceki `teardownSource`'u
  değiştirir → handler sızıntısı YOK. Kapalı closure yapısı: `openSource`/`scheduleReconnect`/
  `teardownSource`. **`connectEvents(queryClient, onStatus?)` imzası + SSE taxonomy / `EVENT_QUERY_KEYS`
  yüzeyi DEĞİŞMEDİ** — `app/Layout.tsx:94` call-site dokunulmadı.
- `test/sse.test.ts` (Write): `FakeEventSource` double'ı `readyState` + statik `CONNECTING/OPEN/CLOSED`
  sabitleri + `error(readyState)` helper + `constructed` sayacı ile genişletildi; **+3 vitest** (`vi.useFakeTimers`):
  transient hata `connecting` kalır + self-reconnect etmez · fatal hata backoff ile reconnect + reopen'da
  self-heal (gap full-refresh) · dispose bekleyen backoff'u iptal eder.

typecheck+lint temiz, build green, **238/238**. Review 0 CRITICAL/HIGH (kendi ampirik doğrulaması: 238 test
+ build). **Dürüst sınır (KALICI):** reconnect sonsuza dek dener (delay cap 30s — canlı dashboard için doğru,
"denemeye devam"); yalnız CLIENT dayanıklılık değişikliği — backend SSE stream (`apps/api/sse.py`) tüketilen
hâliyle DEĞİŞMEDİ.

## Stage tool-call envelope status shadowing — landed (PR #135)

**BACKEND-ONLY** (no migration, alembic head `0021_local_auth` SABİT, `ENGINE_VERSION` SABİT; backend **1054 → 1057**). main after PR #135 = `18b29f9`, feat `4e8ce12`. Closes the tracked TIER 3 deferred defect (this handoff §263): `application/jobs/agent_tools.py::dispatch_tool_call` spread the handler payload **AFTER** the envelope keys, so a handler's own `status` shadowed the call's terminal `succeeded` in the RETURNED dict (the durable `agent_tool_call` row was always authoritative → low-severity response-envelope inconsistency, not persistence). Confirmed shadowers: `artifact.create` (`status: "exploring"`), `agent.task.query` (queried task status), and the idempotent-**replay** path (`_replayed` — stored payload shadowed `str(prior.status)`). NOT CR-08 (capability gating is fully wired/tested — the kickoff mislabeled it). **Fix (Option A, no info loss):** envelope `status`/`tool_call_id` now WIN on both success + replay paths (payload spread FIRST); the two colliding keys namespaced — `artifact.create` `status`→`artifact_status`, `agent.task.query` `status`→`task_status` (their `response_ref` key shape changes accordingly; `state`-keyed readiness/backtest + the rejection path never collided). Corrected the e2e assertion that had encoded the shadow (`test_e2e_agent_loop.py`: `hypothesis["status"]=="exploring"` → `"succeeded"` + `artifact_status`). +3 gateway regression tests (artifact.create / task.query / replay). Frontend UNCHANGED (does not consume the sync response — grep empty). Review: own empirical verify (full suite green + ruff/format/mypy clean), 0 CRITICAL/HIGH.

**Reuse anchor'ları:** `agent_tools.py::dispatch_tool_call` return (envelope-wins merge order — the pattern for any future handler) + `_replayed` (same rule on replay) + `test_agent_tool_gateway.py::test_envelope_status_not_shadowed_by_artifact_status` / `test_task_query_status_is_namespaced` / `test_replay_status_not_shadowed`.

## Stage summary["timeframe"] resolution — landed (PR #137)

**BACKEND-ONLY** (no migration, alembic head `0021_local_auth` SABİT; **`ENGINE_VERSION` BUMP:
`backtest-engine-v2-position-size-limits` → `backtest-engine-v2-summary-timeframe`**; backend
**1057 → 1061**). main after PR #137 = `22c099e`, feat `e1a2f88`. Closes the kickoff deferred item
"`summary[\"timeframe\"]` çözümü (market-revision metadata'sından)": `summary["timeframe"]` was a
hard-coded `None` since Slice B (`engine.py:657`). Now `domain/backtest/engine.py::run_engine` gains
an optional caller-resolved keyword `timeframe: str | None = None` (engine stays PURE — no I/O; all
callers pass keyword args → default keeps them byte-identical) and surfaces it verbatim in the
summary; `application/jobs/backtest_engine.py::run_backtest` resolves it from the PINNED strategy's
market revision via the read-only `md_repo.get_base_timeframe_for_revision` (PR #55 helper;
`resolution_kind == BAR` → `resolution_value` e.g. `"1m"`; immutable revision → reproducibility-safe)
and threads it into `run_engine`. Non-bar (event-based / unknown) revisions surface an honest `None`,
never guessed (L4). The resolve happens OUTSIDE the engine `try:` — an unexpected DB error stays a
retryable job exception, not a FAILED run (file contract preserved). ENGINE_VERSION bump shifts the
`execution_key` namespace so a stale timeframe-less result is not reused next to fresh ones carrying
the real value (INF-04/INF-05; PR #47/#63 precedent). Read models untouched (`ResultSummary.timeframe`
column existed since Stage 5a; queries/projections already carried the field); frontend UNCHANGED
(`lib/backtest.ts` already types `timeframe: string | null`). +4 tests (2 unit: engine passthrough
`"1m"` / default `None`; 2 integration: full admission→worker chain persists `"1m"` into the summary
row + headline JSONB + result read model / un-timeframed revision persists `None`); the ENGINE_VERSION
literal assert updated. Review: APPROVE 0 CRITICAL/HIGH (1 LOW accepted: the duplicate base-TF read in
`_resolve_base_seconds` returns SECONDS for plan validation while the job needs the verbatim STRING —
kept separate deliberately).

**Reuse anchor'ları:** `run_engine(..., timeframe=...)` (caller-resolved summary metadata pattern —
any future summary field resolved from pinned metadata follows this shape) +
`md_repo.get_base_timeframe_for_revision` + `test_backtest_persistence.py::_ready_composition(base_tf=...)`
(bar-timeframed market revision seed helper) +
`test_result_summary_carries_pinned_market_timeframe` / `test_result_summary_timeframe_none_when_revision_not_bar_timeframed`.

## Stage audit log-projection indexes — landed (PR #139)

**BACKEND-ONLY, MIGRATION slice** (alembic head **`0021_local_auth` → `0022_audit_log_indexes`**;
`ENGINE_VERSION` UNCHANGED — engine untouched; backend **1061 → 1065**; frontend unchanged 238).
main after PR #139 = `73ae1bd`, feat `72c95ec`. Closes the deferred performance candidate
"audit log-projection indexleri": the Admin Logs read model (`queries/log_projection.py`,
doc 19 §5/§6.2) ran every filtered page and every correlation chain as an unindexed scan over the
append-only, insert-hot `audit_events` table. Design derived from the EMPIRICAL read of ALL THREE
consumers (`list_log_events`, `get_log_event`, `audit_repo.query_audit_events` — no other consumer
exists). 5 indexes on `AuditEvent.__table_args__` + byte-identical mirror migration `0022`:

- `(severity | actor_principal_id | target_entity_type, occurred_at, event_id)` partial
  composites — filter equality + the newest-first keyset BEHIND it, so a filtered page is ONE
  ordered index scan; partial `WHERE` mirrors the filter semantics (NULL never matches);
  `severity` indexes only non-info rows (the warning/error triage case — `severity = 'info'`
  matches the table bulk and deliberately stays on `ix_audit_events_log_order`).
- `(correlation_id, occurred_at, event_id)` partial — the §5 detail correlation chain
  (equality + ASC composite order; DESC keyset via backward scan).
- `lower(correlation_id) varchar_pattern_ops` partial **EXPRESSION** index — the §6.2
  exact-or-prefix filter lowercases while ids store UPPERCASE Crockford base32 (`shared/ids.py`),
  so only this expression index can serve the LIKE prefix.

Proofs: migration↔model `pg_indexes.indexdef` diff **IDENTICAL** (migration-built vs
`Base.metadata.create_all` schema); alembic 0022 up/down/up green (8→3→8 indexes on
`audit_events`); 3× EXPLAIN — `severity='error'` → **Index Only Scan Backward** on the partial
index (the planner PROVES the `!= 'info'` implication; sort-free newest-first), prefix LIKE →
pattern-ops range cond on the expression index, chain → Index Only Scan without sort.
+4 integration tests (`tests/integration/test_audit_log_indexes.py` — asserts against
`pg_indexes.indexdef` server-truth DDL: names, column ORDER as contract, partial predicates,
expression + ops). Review: APPROVE 0 CRITICAL/HIGH (2 LOW accepted: non-CONCURRENT index
creation = the house pattern of all 21 prior migrations, dev-stage deployment; pre-existing
`startswith` `_`-wildcard nuance in `log_projection.py:102` — the planner extracts the fixed
prefix `corr` and filters, result correct).

**Honest boundary:** `actor_kind` (3-value enum) deliberately unindexed — poor selectivity;
family/query-text substring (`contains`) filters would need **pg_trgm** (an extension decision,
out of scope) — both keep riding the log-order index.

**Reuse anchor'ları:** `test_audit_log_indexes.py::_indexdefs` (pg_indexes `indexdef`
server-truth assert pattern for any future index slice) + the parity proof (indexdef dict diff
between the migration-built DB and an ORM-`create_all` schema) + the EXPLAIN
`SET enable_seqscan = off` viability ritual on the empty migration DB.

## Stage audit log substring (pg_trgm) indexes — landed (PR #141)

**BACKEND-ONLY, MIGRATION slice** (alembic head **`0022_audit_log_indexes` → `0023_audit_log_trgm_indexes`**;
`ENGINE_VERSION` UNCHANGED; backend **1065 → 1069**; frontend unchanged 238). main after PR #141 =
`9b5568d`, feat `36069cb`. Closes the **exact honest boundary #139 (PR #139) left open**: the Admin
Logs **substring** filters (`queries/log_projection.py::_apply_filters`, doc 19 §6.2) were sequential
scans. A leading-wildcard `lower(col) LIKE '%needle%'` (from `func.lower(col).contains(needle)`) can
be served by NO B-tree — not even `varchar_pattern_ops` (that only serves ANCHORED prefixes, which is
why #139's `correlation_prefix` index worked for the correlation filter but nothing else). Only a
`gin_trgm_ops` trigram index does. 3 GIN trigram EXPRESSION indexes over `lower(col)` (empirically
matching the two `contains` filters):

- `ix_audit_events_event_kind_trgm` = `lower(event_kind)` **no partial predicate** (event_kind is
  NOT NULL) → serves BOTH the `family` token filter (`_family_predicate` positive `own` tokens) AND
  the `q` search (first OR leg).
- `ix_audit_events_target_id_trgm` = `lower(target_entity_id)` partial `IS NOT NULL` → the `q` search
  (2nd OR leg).
- `ix_audit_events_reason_trgm` = `lower(reason)` partial `IS NOT NULL` → the `q` search (3rd OR leg).

The `pg_trgm` extension is provisioned two ways: migration `0023` runs `CREATE EXTENSION IF NOT
EXISTS pg_trgm` before the indexes; `models/audit.py` adds a `Base.metadata` `before_create` DDL
listener (`execute_if(dialect="postgresql")`) so any `create_all` path (the integration test schema
builds this way, NOT via alembic) provisions the extension before `CREATE INDEX`. Downgrade drops the
3 indexes but **RETAINS** the extension (a `DROP EXTENSION` in a routine down-migration is destructive
and could break unrelated objects). Proofs: migration↔model `indexdef` parity **IDENTICAL**; alembic
up/down/up → head `0023` (down drops trgm indexes, extension retained); **EXPLAIN** — the 3-column `q`
search plans a `BitmapOr` over all three trgm indexes, the `family`/`q` event_kind filter plans a
`Bitmap Index Scan on ix_audit_events_event_kind_trgm`. +4 integration shape tests
(`test_audit_log_trgm_indexes.py`, `pg_indexes.indexdef` server-truth: gin + gin_trgm_ops + lower(...)
expression + partial predicates on the nullable columns only). Review APPROVE 0 CRITICAL/HIGH.

**Honest boundary:** the `system_other` family and earlier-family exclusions are purely NEGATIVE
(`NOT lower(event_kind) LIKE '%token%'`) — no trigram index serves a negated substring; those ride a
scan filter behind the positive predicate. `actor_kind` (3-value enum) stays unindexed by design.
`pg_trgm` requires `CREATE EXTENSION` privilege at deploy — a trusted extension on PG13+, installable
by the database owner (deployment note, not a code gap).

**Reuse anchor'ları:** the `before_create` `execute_if(dialect="postgresql")` metadata listener
(pattern for provisioning any Postgres extension a `create_all` schema needs — mirror it whenever a
future index/type depends on an extension) + `test_audit_log_trgm_indexes.py` (GIN/trgm/expression
indexdef assert pattern) + the migration↔`create_all` parity + EXPLAIN-BitmapOr viability ritual.

## Post-V1 — capability operational output history read surface (TIER 2 slice) ✅ landed (PR #143, merged → main `30eabd5`, feat `44e4b1e`)

**BACKEND + FRONTEND** (no migration — `view_dataset` / `analysis_artifact` tables exist since
`0020_future_dev`; `ENGINE_VERSION` unchanged; backend **1069 → 1077**; frontend **238 → 242**). The two
Future Dev operational POSTs (`view_dataset.query`, `analysis_artifact.create`, landed PR #95) wrote rows
that NO endpoint could read back — the outputs lived only in the command return + audit trail; doc 22 §7
`futureDevNoHistory.empty` was defined but **unreachable**. Adds the owner-scoped, ACTIVE-only,
newest-first keyset read surface (doc 22 §7, §13):

- `repositories/postgres/repositories/capability.py`: list/get `view_datasets` + `analysis_artifacts`
  (owner + `deletion_state=active` filter, ULID id-DESC keyset `id < last_key`).
- `queries/capability.py`: list/detail projections over the agent-lab keyset cursor; detail reports a
  cross-owner / soft-deleted / missing id as **not-found** so existence never leaks.
- `routes/capability.py`: `GET /view-datasets[/{id}]` + `GET /analysis-artifacts[/{id}]`.
- `shared/errors.py`: `ViewDatasetNotFoundError`, `AnalysisArtifactNotFoundError`.
- Frontend `lib/capability.ts`: history + detail hooks + wire types mirroring the row/detail projections;
  the operational POSTs now invalidate their history key (`["view-datasets"]` / `["analysis-artifacts"]`)
  alongside `["audit"]`. `pages/FutureDev.tsx`: View Dataset + Analysis Artifact history cards (keyset
  cursor-stack pager, owner-scoped row detail, `futureDevNoHistory.empty` copy rendered verbatim).
- +8 backend integration tests (`test_capability_output_history.py`) + 4 vitest.

**Reuse anchor'ları:** the agent-lab ULID id-DESC keyset cursor + owner+`active` repo filter (mirror for
any future owner-scoped operational read surface) + the not-found-on-cross-owner projection
(existence-non-leak pattern) + the operational-POST-invalidates-its-own-history-key wiring.

## Post-V1 — capability lifecycle-transition history read surface (TIER 2 slice) ✅ landed (PR #144, merged → main `c5d97b6`, feat `d77d612`)

**BACKEND + FRONTEND** (no migration — `capability_activation_event` exists since `0020_future_dev`;
`ENGINE_VERSION` unchanged; backend **1077 → 1081**; frontend **242 → 244**). Binds the **orphan**
`capability_repo.list_activation_events` to a read surface (doc 22 §9, §13): the immutable, append-only
lifecycle-transition timeline for one capability, oldest-first by resulting registry version. Before this
the capability detail exposed only the LAST transition; every prior activation event was written but had
no read path.

- `queries/capability.py`: `get_capability_transitions` — projection over `list_activation_events`
  (oldest-first by resulting registry version).
- `routes/capability.py`: `GET /capabilities/{key}/lifecycle-transitions` — the POST on the same path
  already **appends**; the read is **any-authenticated** (mirrors the capability detail's last-transition
  provenance fields; the write / transition path stays **Admin-only**).
- Frontend `lib/capability.ts`: `useCapabilityTransitions`; `pages/FutureDev.tsx`: an immutable
  "Transition history" table in the capability detail card, keyed under `["capabilities"]` so an Admin
  transition (which invalidates `["capabilities"]`) refreshes it in the same tab.
- +4 backend integration tests (`test_capability_transition_history.py`) + 2 vitest.

**Reuse anchor'ları:** the **orphan-repo → read-surface binding ritual** (a written-but-unreadable append
log gets an oldest-first projection + an any-authenticated GET while the write path stays gated) — the
exact template for finding + closing the NEXT orphan. **With #143 + #144 the doc-22 Future Dev capability
system is END-TO-END COMPLETE:** registry list/detail + Admin transition (OCC + 7 gates + audit/outbox +
activation event) + 2 operational POSTs (view-dataset / analysis-artifact, ACTIVE-only) + owner-scoped
output history (#143) + transition history (#144). The Graphic View RENDERER stays OUT OF doc-22 scope
("V18 static placeholder retained").

## Post-V1 — agent tool-call gateway call-history read surface ✅ landed (PR #146, merged → main `4d5c5d4`, feat `b8f1664`)

**BACKEND+FRONTEND, migration YOK.** Orphan-scan bulgusu (#144 deseni: yazılı-ama-bağlanmamış durable
append log → projection + gated GET): `agent_tool_gateway` repo'sunun `list_tool_calls`/`get_tool_call`
metodları yazılı+test edilmişti ama query/route/frontend yoktu. YENİ `queries/agent_tool_gateway.py`
(`require_role` ADMIN/SUPERVISOR; task-scoped bounded newest-first list — summary satırları
request/response_ref gövdelerini omit eder — + full-record detail; missing task/id → not-found, sessiz
boş sayfa değil). `routes/agent_lab.py`'ye `GET /agent-tasks/{task_id}/tool-calls` +
`GET /agent-tool-calls/{tool_call_id}`. `errors.py`'ye `AgentToolCallNotFoundError` (additive).
Frontend: `lib/agentLab.ts` `AgentToolCall{Card,Detail,List}` + `TOOL_CALL_STATUS_TONES` +
`useTaskToolCalls`/`useToolCall` (`["agent-tasks"]` SSE-swept, on-demand detail); `AnalysisLab.tsx`
task-detail "Tool calls" bölümü (badge+tool_name+failure; satır açılınca request/response). +7 backend
integration + 2 vitest. alembic head / ENGINE_VERSION değişmedi. Honest boundary: detail read
rol-gate'li (Analysis Lab paylaşımlı-gözlem modeli, owner-scoped değil); list bounded newest-first
(keyset yok) — checkpoints/directives gibi.

## Post-V1 FINALIZATION — seed FK fix + smoke + README/USAGE/ARCHITECTURE ✅ landed (PRs #147 `f597883` + #148 `748b31e` + #149 `2d57f95` MERGED; #150 açık/merge bekliyor)

Developer/operator-experience kapanış seansı — yeni ürün özelliği YOK. Hepsi EMPİRİK kanıtla:

- **#147 `fix(post-v1)` seed identity FK flush order** — `python -m entropia.apps.seed` BOŞ veritabanında
  `ForeignKeyViolationError` ile patlıyordu (README yerel kurulum Adım 7 KIRIKTI): `Principal` ↔
  `HumanUser`/`Agent` arasında mapped `relationship()` olmadığından unit-of-work flush sırasını tablo-FK'sından
  TÜRETMİYOR — batched flush `agents` INSERT'ini `principals`'tan önce basabiliyor (minimal repro + SQL echo
  ile kanıtlandı; SQLAlchemy 2.0.51). Fix: her FK-bağımlı child'dan önce Principal flush'ı; kimlik bloğu
  `seed_identities(session)` olarak test edilebilir çıkarıldı. +2 integration (taze-şema FK sırası +
  idempotency) → **backend 1089 (CI server-truth; NOT: önceki zincirin "1088" sayımı off-by-one idi — #147
  öncesi CI 1087)**. Canlı kanıt: boş DB → seed → `/me` user_admin=admin; ikinci koşu idempotent.
- **#148 `chore(post-v1)` scripts/smoke.sh + `make smoke`** — çalışan stack'in dışarıdan doğrulaması:
  `/health/live` + `/meta` + `/openapi.json` + bağımlılık-bazlı `/health/ready` (postgres=hard FAIL,
  redis/minio=WARN — Docker'sız minimal kurulum meşru) + `/metrics` Prometheus + `X-Actor-Id` `/me` +
  frontend :5173/:8080. `--seed` opsiyonel. Bulgu: ready DOWN bağımlılıklarda kendi connect-timeout'larını
  beklediği için >5s sürer → ready çağrısına uzun curl timeout. Tam e2e yol header'da işaret edilen
  `tests/integration/test_e2e_pipeline.py` (bu seans canlı: **3 passed in 7.89s**, `entropia_smoke` DB).
- **#149 `docs(post-v1)` kök README yenileme** — "Stage 0/1 complete" → gerçek durum (V1 %100 + post-V1
  dalgası; CI-truth 1089/246; alembic 0023); YENİ "What's inside — the 24-screen map" tablosu; YENİ
  "Verifying changes" bölümü (CI'ın koştuğu kapılar + izole `TEST_DATABASE_URL` uyarısı + up/down/up +
  smoke + e2e); auth bölümü landed `AUTH_MODE=dev|session` modeline yeniden yazıldı (argon2id + Bearer,
  `/login`, `ENTROPIA_BOOTSTRAP_ADMIN_EMAIL`, `ENTROPIA_SERVICE_TOKEN`); Türkçe rehberin "login sonraya
  bırakıldı" notu güncellendi; `.env.example`'a Authentication + Rate-limiting blokları (settings.py
  default'ları verbatim — "every variable and its default" iddiası yeniden doğru).
- **#150 `docs(post-v1)` USAGE + ARCHITECTURE hizalama** — YENİ `docs/USAGE.md` (login & roller
  User/Supervisor/Admin/Agent, golden path ingest→package→strategy→mainboard→ready→RUN→result→
  history/compare→trash, Analysis Lab, güvenlik rayları; çalıştırılabilir kanıt = e2e testi);
  `docs/ARCHITECTURE.md` bayat pasajlar gerçekle hizalandı (ActorContext AUTH_MODE gerçeği; SSE fan-out
  CANLI; `/metrics` implemented; §12.2 config listesine AUTH_*/RATE_LIMIT_*); `docs/README.md` USAGE satırı.

**Canlı çalıştırılabilirlik kanıtı (Docker'sız yol):** lokal Postgres :5432 → alembic head `0023` →
uvicorn → live ok / ready degraded(pg ok) / metrics exposition → seed → `/me` admin → Vite
`<title>Entropia V18</title>` → `make smoke` SMOKE OK. **Dürüst sınır:** `docker compose up` bu seansta
KANITLANAMADI — Docker Desktop bu makinede self-update GUI onayı bekliyordu (daemon hiç ayağa kalkmadı);
`docker compose config --quiet` geçerli + CI'ın "Docker — build images" job'ı yeşil. Bir sonraki fırsatta:
Docker Desktop'ı GUI'den güncelle/başlat → `docker compose up -d --build` → `make smoke`.

## Video-alignment wave landed (#313–#318 MERGED) ✅ — the walkthrough (`docs/spec/video-anlatimi/entropia_transkript.md`) driven live end-to-end

**MOSTLY FRONTEND + narrow backend; migration YOK** (alembic head `0023_audit_log_trgm_indexes` SABİT;
`ENGINE_VERSION` SABİT). Kaynak: kullanıcının prototip anlatım videosu — kodlanan yapıyı prototiple satır
satır karşılaştıran transkript. Bu dalga videoda "çekirdek" (Entropia Core) ilan edilen **Add Strategy →
yatay açılır kutu → çok-stratejili evren** akışını CANLI çalışır hale getirdi ve yolda çıkan çökme/kullanılamazlık
defektlerini kapattı. Altı PR:

- **#313 `fix(api)` — commit-before-response** (`fix/api-commit-before-response`): Mainboard **Add Strategy**
  canlıda `WORK_OBJECT_NOT_FOUND` veriyordu — `POST /work-objects` 201 dönüyor ama tarayıcının hemen ardındaki
  `POST /mainboards/{id}/items` yeni satırı GÖREMİYORDU. Kök neden: FastAPI yield-dependency teardown'ı
  (`db_session` commit'inin yeri) yanıt gövdesi istemciye doğru YOLA ÇIKTIKTAN sonra koşuyor → aynı-makine istemci
  bu ~1ms yarışı kazanıyor (curl'de insan-ölçekli boşlukla hep başarılı). Fix: **`TransactionBoundaryMiddleware`**
  (en iç katman) request-scoped session'ı yanıt upstream'e iletilmeden ÖNCE commit eder; `>=400` → rollback (eski
  raise→rollback semantiği korunur); yakalanmamış exception → rollback+propagate. `db_session` session'ı
  `request.state`'e koyar + middleware'siz çıplak test app'leri için commit fallback tutar. 25 contract/integration
  test izole `TEST_DATABASE_URL`'de yeşil; canlı tarayıcı kanıtı.
- **#314 `fix(mainboard)` — Add Strategy'yi strateji-editör ailesine bağla** (`fix/mainboard-add-strategy-editor-family`):
  video 0:55–2:52'nin çekirdeği. #313'ten sonra kutu çıkıyordu ama inline editör hep `STRATEGY_REVISION_NOT_FOUND`
  veriyordu (add çıplak generic work object yaratıyordu, editör strateji ailesini okur). Fix: Add Strategy artık bir
  editör **draft**'ı yaratır (`POST /strategy-drafts`, auto-ad `STRATEGY <n>`) — "Unsaved draft" rozetli yatay kutu
  hemen render olur, `GET /strategy-drafts`'tan listelenir (reload'a dayanır); **ilk Save → attach** (`StrategyDetailsPanel`
  `onSaved` callback'i §7.1 `mirror_revision_id`'yi gerçek item olarak pinler; Save öncesi hiçbir şey attach olmaz —
  doc 02 §7). Backend deref: `GET /strategy-revisions/{id}` §7.1 mirror `worev_` id'yi de kabul eder (payload
  `strategy_revision_id` deref). 438 vitest; canlı: STRATEGY 1/STRATEGY 2 bağımsız editörlerle üst üste yığılır.
- **#315 `docs` — Docker-free local stack** (`docs/local-stack-no-docker`): YENİ `docs/LOCAL_STACK.md` (redis brew
  services, MinIO custom LaunchAgent + `entropia-artifacts` bucket, per-session dramatiq worker); Docker Desktop bu
  makinede self-update GUI onayında takıldığı için YOL B (Homebrew) native kurulum belgelendi. **Kod değişikliği YOK**;
  `/health/ready` `{postgres,redis,object_storage:ok}` + `make smoke` SMOKE OK + queue↔worker round-trip kanıtı.
- **#316 `fix(create-package)` — onaylı indicator uçtan uca kullanılabilir + pinlenebilir** (`fix/create-package-published-indicator-usable`):
  iki defekt. (1) `apps/seed.py` canonical `ta.*`/`cond.*` resolver'ları `pine_v5` adapter'la seed'liydi ama V1 Create
  Package her zaman `python` adapter'a sabit (`SUPPORTED_TARGET_RUNTIMES=={PYTHON}`); Pre-Check EXACT signature+adapter
  eşleşmesi yaptığından her declared `ta.sma` `RESOLVER_ADAPTER_INCOMPATIBLE` düşüyordu → `python`'a düzeltildi. (2)
  `start_package_validation_run` PASSED validation kaydediyor ama sertifikalı draft revision'ın `validation_state`'ini
  set etmiyordu (PENDING kalıyordu) → `can_use` PASSED istediğinden onaylı+publish indicator `can_use=false` idi ve
  **Choose indicator** picker'da pinlenemiyordu; revision artık verdict'le (`PASSED`/`FAILED`) sertifikalanır. +regresyon
  `test_validation_evidence.py`; canlı: Translate PineScript `ta.sma` → Pre-Check→candidate→draft→validate→approve/publish
  → Library `can_use: yes` → editörde pinlenir.
- **#317 `fix(frontend)` — Result headline objesini render et (crash yerine)** (`fix/result-detail-headline-object-render`):
  bar-replay engine `summary.headline`'ı yapısal metrik OBJESİ olarak yayıyor (`LatestResultSummary.headline`'da zaten
  `Record<string, unknown>`) ama `ResultSummary.headline` yanlışlıkla `string | null` tipliydi → `ResultDetail` objeyi
  doğrudan React child olarak render edip **her başarılı RUN'da beyaz ekran** ("Objects are not valid as a React child").
  Fix: `lib/backtest.ts` tipi `Record<string, unknown> | null`'a düzeltildi + `ResultDetail.tsx` headline'ı null-safe
  key/value listesi olarak render eder. **Presentation-only** (tek `lib` düzenlemesi backend şekline uyan tip anotasyonu).
  Canlı: tek-strateji (1728 trade) + iki-strateji kompozisyon (3456 trade) RUN'ları Result özetini çökmeden gösterir.
- **#318 `fix(mainboard)` — #314'ün dürüst sınırlarını kapat** (`fix/mainboard-legacy-strategy-cleanup`): (1) ESKİ akışın
  bıraktığı legacy orphan temizliği — `strategy_root`/`strategy_revision` detay'ı OLMAYAN `wo_` root'lar (yerel DB'de 3
  adet, hepsi active + hiçbirine attach değil) idempotent, kendi kendini seçen script
  `scripts/maintenance/cleanup_legacy_strategy_work_objects.sql` ile soft-delete (attach'lı orphan'ları Mainboard `×`
  yoluna bırakır). (2) `StrategyDetailsPanel` artık SADECE `STRATEGY_NOT_FOUND`/`STRATEGY_REVISION_NOT_FOUND` için sakin
  "This item is not an editor-managed strategy" notu gösterir (diğer her hata retryable `ErrorState` kalır). (3) Drafts
  hijyeni: `GET /strategy-drafts` zaten `deletion_state=ACTIVE` filtreler — "saved+attached sonra trashed draft listeden
  düşer" regresyonu eklendi. 440 vitest (+2), 17 strategy integration (+1); `apiErrorRoute()` additive test infra.

**Reuse anchor'ları:** `TransactionBoundaryMiddleware` (commit-before-response — aynı-makine yield-teardown yarışının
kalıcı çözümü; her yeni-satır-yaratıp-hemen-referanslayan akışın temeli); **Add-Strategy draft akışı** (`strat_` root
= attach edilebilir work object; **ilk Save'e kadar revision YOK**, doc 02 §7; `mirror_revision_id` attach + `worev_`
deref); legacy orphan **cleanup script deseni** (`scripts/maintenance/*.sql` — idempotent, kendi kendini seçen, soft-delete,
attach'lıyı UI `×` yoluna bırakır); `ResultSummary.headline` = backend `Record<string,unknown>` (obje-render tuzağı).
**Bu dalga tamamen video-alignment** — yeni backend domain YOK, migration YOK; kalan video boşlukları aşağıda (KALAN-A/B).

## V18-R2 · R2-07 — Golden-path E2E: Ready PASS → RUN SUCCEEDED → inline Result ✅ (GAP madde 12)

**Ne landed (test+seed slice — uygulama davranışı DEĞİŞMEDİ):**
- **Seed:** `backend/src/entropia/apps/seed.py`'ye idempotent `SEED_E2E_GOLDEN=1` modu —
  yol kararı: API zinciri yerine **seed genişletmesi** (API yolu admin oturumu + iki async
  worker pipeline'ına bağımlı; seed senkron/deterministik). İçerik: non-Admin fixture owner
  `user_e2e_fixture` (mod, `seed_identities`'i BİLEREK atlar → bootstrap-Admin bozulmaz),
  ACTIVE+APPROVED market dataset `E2E Golden BTCUSDT 1h` (resolution `1h` + **MinIO'da
  processed Parquet asset** — 1500 deterministik saatlik bar; asset olmadan her RUN
  `ASSET_UNAVAILABLE`), PUBLISHED+PASSED+APPROVED indicator package `E2E Golden SMA`
  (dependency_snapshot → `ta.sma`), canonical 6 rationale family (`_seed_rationale_families`
  owner-parametreli oldu).
- **Spec:** `05-mainboard-ready-check-run.spec.ts` TAMAMEN yeniden — "structured outcome
  yeterli" yaklaşımı kalktı; blocked/NOT_READY/error = FAIL. Akış ("/"dan hiç ayrılmadan):
  `+ Add → Add Strategy` inline typed editör → kart kart Apply (her Apply gerçek PATCH
  yanıtı beklenir — "Payload applied" notu bir önceki karttan görünür kalabildiği için
  YARIŞ kaynağıydı; tam-payload replace bayat draft'ı diriltip alanları siliyordu) →
  dataset+indicator PICKER'la pinlenir → Validate temiz → Save+auto-attach → RUN
  disabled (stale) assert → Ready Check modal AÇIK "Ready" → RUN enabled → inline run
  **succeeded** → inline `ResultDetail` Headline + Manifest hash/Execution key. Yeni
  `pages/InlineStrategyEditor.ts`; `MainboardPage`'e additive ready/run/result helper'ları.
- **CI:** `e2e.yml`'e stack-ready sonrası `docker compose exec -T -e SEED_E2E_GOLDEN=1 api
  python -m entropia.apps.seed` adımı. `e2e/README.md` yeni gerçeğe göre yazıldı.
- **Kanıt (gerçek koşu):** host-native tam stack (docs/LOCAL_STACK.md; Postgres+Redis+MinIO+
  session-auth API+dramatiq worker+Vite): temiz DB **passed 10.0s**, kirli stack rerun
  **passed 32.1s**. Full suite 13/14 (08 Trade Log importu yalnız suite sırasında, worker
  host-native `asyncio.run`/paylaşılan async engine "attached to a different loop" flake'i —
  izole koşuda geçiyor, R2-07'den bağımsız altyapı notu).

**Bulgular (ayrı iş):** (1) **Rationale family Mainboard-inline akışta set edilemiyor** —
`StrategyConfig.rationale_family_id` ZORUNLU ama Mainboard `addStrategy` null yollar,
Context kartı read-only, Advanced editör admin-only, derive yolu da family geçirmez →
normal kullanıcı inline strategy'yi asla Validate'ten geçiremez (spawn-task chip açıldı;
spec bu yüzden bootstrap Admin + Advanced editörle family set eder — boşluk kapanınca
plain user'a dönülmeli). (2) **Validate ↔ Ready Check parity açığı**: draft Validate,
`slippage_value`/`base_position_size`/`rationale_family_id` eksiklerini yakalamayabiliyorken
readiness `STRATEGY_CONFIG_INVALID` üretiyor. (3) Soft-delete edilen work object'in
`mainboard_working_item` satırı enabled kalıp Ready Check'i süresiz `ITEM_UNAVAILABLE`
bloklar (UI satırı gizler, readiness görür).

## V18-R2 · R2-03 — Add Package popover + Add Strategy From Package ✅

**Ne landed (GAP madde 4 — Add Package ≠ Create Package):** YENİ
`components/AddPackagePopover.tsx` — Mainboard "+ Add" menüsündeki "Add Package" artık
`/packages/create` linki değil, bağlama bağlı seçim popover'ı (mockup `.package-picker-popover`
sınıfları REUSE). İçerik: `useLibraryPackages({type:"strategy", lifecycle_state:"active", q})`
(TS/TL package türleri hiç listelenmez) + arama; satır seçilebilirliği SERVER-truth
`permissions.can_use` (false → `disabled` + neden title; client eligibility türetmez). Seçimde
kısa compatibility özeti: exact revision (rev no + id) + market/timeframe library detail
`input_contract`'ından (alan yoksa "not provided"). Primary **"Add Strategy From Package"** →
MEVCUT GAP-03 `useDeriveStrategyDraftFromPackage` (`POST /strategy-drafts` +
`source_package_root_id/source_package_revision_id`, taze Idempotency-Key, OCC yok) →
`onDerived(draftId)` → Mainboard `setJustAddedDraftId` → draft, yatay Strategy draft satırı
olarak inline Strategy Details editörüyle AÇIK gelir (PR #314 akışının parametrize hali; yeni
endpoint GEREKMEDİ). İkincil ghost eylem "Create new package →" `/packages/create`. R2-02
"package" add-intent'i artık popover'ı açar (`packagePopoverOpen` state; `/packages/create`
fallback kalktı, `useNavigate` importu düştü).

**Canlı stack kanıtı:** seed edilen iki strategy package'la (PASSED/APPROVED + PENDING) popover
yalnız usable olanı seçilebilir gösterdi; derive sonrası draft `source_provenance` exact
revision + content hash pinli, source package `current_revision_id`/`row_version` DEĞİŞMEDİ;
/research-data'dayken üst menü Add Package → "/" + popover açık; Create new package →
`/packages/create`.

**Testler:** `mainboard.test.tsx` +4 yeni (eligible-filtre & disabled-neden · derive akışı +
kaynak-mutasyonsuzluk + inline draft satırı · package-intent → popover · create-new ikincil yol)
+2 hizalama (Add Package link→button) → 30/30; toplam 51 dosya · 452 test, tsc/eslint/build
yeşil.

## V18-R2 · R2-02 — Üst menü Add eylemleri → Mainboard add-intent dispatcher ✅

**Ne landed (GAP madde 6 — tek Add modeli):** `app/nav.ts`'e `MainboardAddIntent`
(`"strategy" | "trading_signal" | "trade_log" | "package"`) + `MenuLink.addIntent` eklendi;
MENU_BAR Mainboard grubundaki dört Add eylemi route-link olmaktan çıktı. `app/Layout.tsx`
addIntent taşıyan öğeyi `navigate("/", { state: { add: intent } })` yapan buton olarak render
eder. `pages/Mainboard.tsx` intent'i mount'ta okur, kendi "+ Add" handler'larını çağırır
(`addStrategy` STRATEGY-n numaralandırması için board+drafts projection'larını bekler; TS/TL
anında `OutsourceDraftRow` ekler), sonra `history.replaceState` ile temizler (reload/back
tekrar tetiklemez). `"package"` intent'i R2-03 popover'ı gelene kadar `/packages/create`'e
yönlenir. `/strategy`, `/trading-signal`, `/trade-log`, `/packages/create` route'ları
deep-link olarak YAŞIYOR (App.tsx dokunulmadı); Portfolio ve diğer nav öğeleri normal link.

**Reuse anchor'ları:** `MainboardAddIntent` tipi + Mainboard'daki `pendingAdd` effect çifti —
R2-03 "package" intent'ini popover açacak şekilde bu noktadan devralır.

**Testler:** `nav.test.tsx` (addIntent-not-path pin), `menu.test.tsx` (dispatcher navigasyonu),
`mainboard.test.tsx` (router-state intent → TS satırı, tek transient-opener POST; package
fallback). vitest 51 dosya · 449 test, tsc/eslint/build yeşil; kabul canlı tarayıcıda kanıtlandı.

## V18-R2 · R2-01b — TS/TL editörleri Mainboard satırlarına INLINE mount edildi ✅

**Ne landed:** Route-launcher davranışı bitti (GAP madde 1-2). `pages/Mainboard.tsx`:
- **Persisted TS/TL `ItemRow`:** "Edit in {label} →" primary linki KALKTI; yerine
  `<TradingSignalEditor|TradeLogEditor mode="inline" initialRoot={item.work_object_root_id}
  onClose={collapse}>` mount (detail view + revizyon composer satır İÇİNDE). "Open full page ↗"
  ghost deep-link kaldı (back-compat).
- **`OutsourceDraftRow`:** "Continue in the {label} workbench →" KALKTI; satır açılır açılmaz
  editör yeni-kayıt modunda inline. Save & Add başarısında `onSaved(rootId)` →
  `outsourceDraftSaved`: transient satır listeden düşer + yeni persisted satır expanded açılır
  (`justAddedRootId` ↔ `work_object_root_id` eşleşmesi). `["mainboard"]`+`["readiness"]`
  invalidation'ları DEĞİŞMEYEN `useCreateTradingSignal`/`useCreateTradeLog` hook'larından gelir.
- **Üç ayrı etiketli eylem (GAP madde 2):** "Remove draft" (transient ×, Trash yok) / persisted
  satırda mevcut two-step soft-delete / "Close panel" (`onClose` → collapse).
- **Toolbar (GAP madde 3 min.):** iki editörün `CreatePanel` + `RevisionEditor`'ına **Validate**
  (client-side JSON structural check — asla Ready PASS değil) + **Cancel** (seed template'e reset)
  eklendi; inline modda "Close panel". Typed form içeriği R2-04'te.

**DEĞİŞMEYEN:** `lib/*.ts` veri sözleşmeleri, hook'lar, OCC/Idempotency, TS/TL route'ları,
`app/nav.ts` (Add menü + üst menü R2-02).

**Doğrulama:** YENİ `frontend/e2e/specs/08-mainboard-inline-editors.spec.ts` — canlı Docker'sız
stack'te (uvicorn :8000 + dramatiq worker + Postgres + Redis + MinIO, `E2E_BASE_URL=:5173`)
**3/3 yeşil**: TS ve TL için create → CSV upload → import report `succeeded` → payload doldur →
Save & Add → persisted satır expanded → Close panel → reload persist; her adımda
`expect(page).toHaveURL(/\/$/)`. Spec auth-mode-aware: session modunda gerçek signup formu,
dev modunda API signup + `#dev-actor` act-as (X-Actor-Id). Not: seeded template'te
`identity.display_name`/`source.provider_name` boş → server 422 `*_VALIDATION_FAILED`; test
kullanıcı gibi JSON'u doldurur (typed form R2-04 bunu çözer). vitest `mainboard.test.tsx` UI-03
satırları inline markup'a hizalandı (OCC/Idempotency/invalidation assert'leri korunarak) →
**445/445**; tsc + eslint + vite build temiz.

Branch `feat/v18-r2-01b-inline-editors`. **Sonraki: R2-02** (üst menü Add eylemleri → Mainboard
action dispatcher) — `docs/V18_R2_ROADMAP.md` §4 R2-02 paste-ready prompt'u.

---

## V18-R2 · R2-10 — App shell backend/auth/hata durumları ✅ (GAP madde 14)

Sonsuz "Loading…" bitti — backend kapalıyken hiçbir primary sayfa spinner'da takılmaz:

- **`lib/apiClient.ts`** — `fetchWithTimeout`: her istek AbortController deadline'ı taşır
  (`REQUEST_TIMEOUT_MS = 15_000`, named export). Timeout + socket-level TypeError →
  `ApiError(status: 0, code: NETWORK_UNAVAILABLE)` (envelope'a ADDITIVE); diğer tüm throw'lar
  DOKUNULMADAN geçer (test double'ların verbatim mesajları korunur — ilk sürümde 26 test bunu
  yakaladı, düzeltildi). Caller-supplied signal iptali NETWORK_UNAVAILABLE'a SAYILMAZ. status 0
  queryClient "no retry < 500" kuralına takılır → otomatik retry fırtınası yok.
- **`lib/hooks.ts` → `useApiHealth`** — `GET /health/live` (empirik en ucuz: dependency-check'siz,
  auth-exempt — `hardening.py` exempt listesinde), 30s interval, `retry: false`.
- **`app/Layout.tsx`** — health error → `.backend-banner` (role=alert): **Backend unavailable +
  `API: <BASE_URL>` + Retry** (Retry = kullanıcı eylemi: health refetch, başarıda
  `invalidateQueries()` ile takılan sayfalar toparlar). Topbar'da ÜÇ AYRI gösterge: auth rozeti
  (mevcut) · `● api` (yeni, health tone'u) · `● sse` (SseStatus REUSE).
- **`components/ErrorState.tsx`** — `ApiError.status === 401` → gerçek **UNAUTHENTICATED** durumu +
  `/login` Login linki (34 sayfa/bileşen kullanıcısına otomatik yayılır); 401-dışı render verbatim.

Evidence: vitest 490/490 (apiClient: fake-timer timeout → NETWORK_UNAVAILABLE, TypeError → ağ
hatası, dış signal iptali hariç; appShellHealth: banner + adres + Retry, Retry recovery, üç ayrı
gösterge, 401 → UNAUTHENTICATED + Login, 409 verbatim korunur); tsc/eslint/build temiz. Canlı
tarayıcı: `frontend-alt` (:5175 → ölü :8001) Mainboard banner + `NETWORK_UNAVAILABLE` ErrorState +
Retry gösterdi (screenshot), `frontend` (:5173 → canlı :8000) banner'sız, `● api` ok. Honest
boundary: canlı 401 kanıtı AUTH_MODE=session backend gerektirir (lokal dev mode'da /me anonim 200
döner) — 401 yolu vitest'te kanıtlandı. SSE taksonomisi / query key'ler / OCC / Idempotency
byte-identical. Branch `feat/v18-r2-10-app-shell-health`.

---

## V18-R2 · R2-01a — TS/TL editörleri reusable bileşenlere ayrıldı ✅ (saf refactor)

**Ne landed:** `pages/TradingSignal.tsx` içindeki iki kolonlu editör gövdesi **VERBATIM** olarak
YENİ `components/TradingSignalEditor.tsx`'e; `pages/TradeLog.tsx` gövdesi YENİ
`components/TradeLogEditor.tsx`'e taşındı. İki sayfa artık **ince wrapper** (~950 satır → 21
satır): sadece v18 sayfa kabuğu (`.page-title` + `.page-sub`) + `<XEditor mode="page" />`.

**Bileşen sözleşmesi (iki ikizde simetrik — R2-01b için forward-contract):**
```ts
{ mode: "page" | "inline"; initialRoot?: string;
  onSaved?: (rootId: string) => void; onClose?: () => void }
```
- `mode="page"` → URL tek doğruluk kaynağı: `?job=` (dayanıklı import handle, CR-09) ve `?root=`
  (work-object detay + revizyon composer) aynen çalışır; bileşen `useSearchParams`'ı kendisi çağırır.
- `mode="inline"` → sayfa kabuğu render EDİLMEZ; job handle bileşen state'inde (`inlineJobId`),
  root `initialRoot`'tan gelir; `onClose` verildiyse tek bir "Close" düğmesi çizilir (page modunda
  ASLA çizilmez → mevcut markup byte-identical).
- `onSaved` mevcut create mutation'ının `onSuccess`'inden yeni `root_id` ile tetiklenir; prop yoksa
  no-op.

**DEĞİŞMEYEN (kanıtlı):** `lib/tradingSignal.ts`, `lib/tradeLog.ts`, tüm hook'lar, react-query
key'leri, OCC token (`expected_head_revision_id`, **BODY-form STR**), `Idempotency-Key`, route
path'leri, `app/nav.ts`. Hiçbir form alanı değişmedi (typed formlar R2-04'ün işi).
`Mainboard.tsx`'e **DOKUNULMADI** (R2-01b).

**Doğrulama:** `tradingSignal.test.tsx` + `tradeLog.test.tsx` **hiç düzenlenmeden** geçti (testler
`@/pages/*`'i import ediyor, aynı bileşen adı hâlâ export ediliyor — import path güncellemesi bile
gerekmedi) → **445/445 frontend vitest yeşil**; `tsc --noEmit`, `eslint .`, `vite build` temiz.
Tarayıcı (dev :5174 + local API :8000): `/trading-signal` ve `/trade-log` aynı v18 iki kolonlu
paneli çiziyor; `?job=job_demo_1` hâlâ Import report kartını mount ediyor; `?root=…` hâlâ
workbench yerine detail view'a geçiyor.

**Reuse anchor'ları (R2-01b bunları mount edecek):**
`components/TradingSignalEditor.tsx` → `TradingSignalEditor`, `TradingSignalEditorProps`;
`components/TradeLogEditor.tsx` → `TradeLogEditor`, `TradeLogEditorProps`.

Branch `feat/v18-r2-01a-editor-extraction`. **Sonraki: R2-01b** (editörleri Mainboard satırlarına
inline mount et) — `docs/V18_R2_ROADMAP.md` §4 R2-01b paste-ready prompt'u.

---

## V18-R2 · R2-04 — TS/TL typed config formları ✅ (PR #TBD)

**Ne landed (GAP madde 3, 7-kısmi, 9-kısmi):** Trading Signal + Trade Log create/revision
akışlarındaki rows={16}/rows={14} ham JSON textarea'ları KALDIRILDI; payload artık typed formdan
ÜRETİLİYOR. YENİ saf modüller `lib/tradingSignalForm.ts` + `lib/tradeLogForm.ts`
(`*FormFromPayload` / `*FormToPayload` / `validate*Form` + `use*ConfigEditorState` hook'u) backend
otoritesini empirik aynalar: `domain/{trading_signal,trade_log}/config.py` alan/uzunluk kuralları +
`compiler.py` cross-field kuralları (event-based ⇄ base_timeframe, intrabar/ignore OHLCV,
signal_events_only / entry_exit_records_only ⇄ use_for_price_context) alan yanında hata olarak.
YENİ `components/{TradingSignalConfigForm,TradeLogConfigForm}.tsx` + paylaşılan
`components/ConfigFormControls.tsx` (enum select'leri canonical token value'larıyla). İkiz farkları
verbatim: TL tek `time_model` grubu, `content_profile`, ledger price source +
`approved_market_data_revision_ref`, currency'li capital, record-batch binding; TL revision
`available_time` null kalır (doc 05 §10.4) — form alanı DEĞİL. **Source asset id normal formdan
kalktı** (GAP madde 3 düzeltme #3): upload sonucundan sistemce taşınır, identity kartında ve
"Source binding (system-carried)" bölümünde read-only provenance; Request import upload'suz
disabled. **Advanced (raw payload)**: kapalı disclosure, `/me` `is_admin` server-truth'una
fail-closed gate'li; senkron kuralı — raw override KAPALIYKEN disclosure typed formdan üretilen
JSON'u read-only gösterir; override AÇIKKEN textarea gönderilecek payload'dır, typed alanlar
disabled, "Back to typed form" raw'ı parse edip formu yeniden tohumlar (parse hatası raw modda
tutar). Toolbar: Validate / Save / Cancel / **Close panel** (Close panel üst köşeden sticky
toolbar'a taşındı — GAP madde 3 düzeltme #4). **OCC (`expected_head_revision_id` BODY-form STR) +
Idempotency-Key + query key'ler + route'lar BYTE-IDENTICAL**; `lib/tradingSignal.ts`/`tradeLog.ts`
wire tipleri dokunulmadı, endpoint değişikliği YOK. Testler: yeni `configForms.test.ts` (round-trip
byte-parity + kural aynaları, 9 test), `tradingSignal.test.tsx` 8/8 + `tradeLog.test.tsx` 9/9 yeni
markup'a hizalandı (OCC/Idempotency assert'leri korunarak) → **464 vitest yeşil**, tsc/eslint/build
temiz. E2E `08-mainboard-inline-editors.spec.ts` typed forma hizalandı ve canlı local stack'e karşı
**3/3 geçti** (kullanıcı hiçbir JSON / root id / revision id / source asset id girmeden TS+TL
oluşturdu; URL `/` kaldı); tarayıcı screenshot kanıtı alındı. Remediation status UI-04/05
satırlarına R2-04 evidence eklendi.

**Reuse anchor'ları (R2-05a/05b için):** `use*ConfigEditorState` hook deseni (typed-form + admin
raw override senkron kuralı) Strategy Advanced JSON role-gate'inin (R2-05b) hazır şablonudur;
`ConfigFormControls.tsx` `SelectField/TextField/ProvenanceRow` her typed-form slice'ında REUSE.

---

## V18-R2 · R2-06 — Research Data server-truth dependency picker ✅ (GAP madde 8)

Sahte kilit (`dependencyReady = marketEntityId.trim().length > 0` — herhangi bir metin workflow'u
açıyordu) kaldırıldı. Serbest metin "Linked Market Data entity id" alanı SİLİNDİ; yerine:

- **`components/MarketLinkPicker.tsx` (YENİ)** — role-aware `/market-datasets` registry'sinden
  isimle seçim (isim + tür + durum rozeti + rev); yalnız `revision_state === "approved"` satırlar
  seçilebilir, deprecated/rejected "not eligible — {state}" ile disabled görünür. Immutable root
  id'yi sistem taşır.
- **`lib/marketDependency.ts` (YENİ)** — `useMarketDependency`: mevcut read-only
  **approved-bundle resolve probe** (`useApprovedBundle`, yeni endpoint YOK — empirik yeterli)
  üzerinden `none / checking / ready / blocked / denied` projection'ı. WorkflowStrip, dependency
  alert ve Create butonu bu TEK projection'dan türer; yalnız server-onaylı `ready` kilidi açar.
  Loading + stale refetch fail-closed kilitli; 404 (approved revision yok) ve 403 (erişim yok)
  zarfları ayrı alert varyantlarında VERBATIM render edilir.
- Create öncesi fail-closed guard + sunucu DR3 kapısı aynen: `DEPENDENCY_BLOCKED` verbatim
  (client kilidi sunucu doğrulamasının önüne geçer, yerine geçmez). OCC/Idempotency/route/
  query-key yüzeyleri byte-identical.

Evidence: vitest 482/482 (researchData.test.tsx picker markup'ına hizalandı — DR3 verbatim +
no-Idempotency-Key create assert'leri korundu; 4 YENİ test: default kilit + free-text input yok,
non-approved satır disabled, probe 404 kilit + verbatim zarf, probe 403 denial); tsc/eslint/build
temiz; canlı tarayıcı (:5173, act-as user_admin) — seçim GERÇEK `GET /market-datasets/…/
approved-bundle → 200` tetikledi, "Approved for use — revision mrev_…" + Create enabled + 2 kilit
temizlendi; Clear ile tam relock. Remediation status UI-12 satırına R2-06 evidence eklendi.

**Reuse anchor'ları (R2-08 için):** `MarketLinkPicker` + `useMarketDependency` deseni teknik-ID
sweep'inin (ResearchLifecycle, MarketData revision, evidence formları) hazır şablonudur.

---

## V18-R2 · R2-08 — Teknik-ID sweep → picker / read-only provenance ✅ (GAP madde 7 + 9 kalanı)

Normal kullanıcıdan altyapı kimliği isteyen TÜM kalan alanlar picker / read-only provenance
modeline çevrildi (envanter PR açıklamasında; wire alan adları VERBATIM — yalnız seçimin kaynağı
değişti):

- **`components/InstrumentPicker.tsx` (YENİ)** — canonical Instrument Registry'den (GAP-16,
  `useInstruments`) isim/venue/symbol ile seçim; yalnız `active` seçilebilir, `deprecated`
  disabled; immutable `instrument_id` sistem taşır ve yalnız "Instrument id (system-carried)"
  read-only provenance satırında görünür. Kullanım: MarketData RevisionComposer + TS/TL typed
  config formları + TS/TL editör identity kartları (5 yüzey).
- **`components/RationaleFamilyPicker.tsx` (YENİ)** — aktif Rationale Family registry'sinden
  (`useFamilies`) isimle seçim; entity_id provenance satırında. TS/TL config formlarındaki
  "Rationale family id" serbest metinlerinin yerine.
- **ResearchLifecycle**: "Re-link market entity id (md_…)" → `MarketLinkPicker` REUSE (optional
  varyant + `useMarketDependency` canlı verdict); "Base revision id (rrev_…)" → dataset'in kendi
  revision listesinden select; bundle "Research revision ids" textarea → checkbox grubu;
  "Agent task id" → `useAgentTasks` select. Run-request id + cross-dataset revision id'ler
  açıkça adlandırılmış "Advanced — manual ids" disclosure'ında (pick yüzeyi yok — gerekçeli).
- **Raw JSON payload'lar** (GAP madde 9): MarketData revision payload + Research revision payload →
  admin-gated "Advanced (raw revision payload)" (R2-05b `useMe` fail-closed deseni); feature
  definition JSON → açık "Advanced" disclosure (şema bilinçli serbest, doc 12 §9.3); CreatePackage
  baseline metadata → 4 typed alan (provider/symbol/timeframe/range) + admin-gated extra-JSON;
  Library manifest import → "Advanced — import from manifest JSON" disclosure (makine-üretimi
  export artifact'ı).

Evidence: vitest 492/492 (6 test yeni markup'a hizalandı — OCC/Idempotency + wire-body assert'leri
DEĞİŞMEDİ; + elle-id-yok negatif assert'leri); tsc/eslint/build temiz; canlı tarayıcı (:5173,
session-auth signup): TS identity picker'ı registry satırını listeledi → seçim "BTCUSDT Perpetual"
+ `instr_…` provenance; MarketData New revision'da serbest instrument/payload alanı YOK (DOM
kanıtı), admin oturumda Advanced payload disclosure göründü; Library import textarea'sı default
kapalı Advanced'te. Remediation status UI-12 satırı + yeni sweep bullet'ı güncellendi.

**Dürüst sınır:** ResearchLifecycle picker'larının tarayıcı kanıtı vitest + kod düzeyinde
(local stack'te approved market dataset olmadığından research dataset açılamadı); `Layout`
dev-actor "act as" alanı bilinçli KAPSAM DIŞI (yalnız dev-mode, açıkça "Dev-mode" etiketli araç).

**Reuse anchor'ları (R2-09 için):** `useMe` fail-closed admin-gate deseni artık 4 yüzeyde
(TS/TL raw override + MarketData/Research revision payload + CP baseline extra-JSON) — R2-09
role-aware presentation envanterinin hazır şablonu.

---

## V18-R2 · KALAN-B — Portfolio "Use Allocation Backtest" + Mainboard per-item pay görünürlüğü ✅ (video 7:16–9:24)

Videodaki Portfolio deneyimi kapandı: **toggle backend'de birebir vardı** — `AllocationDraft.enabled`
(routes/allocation.py PutDraftBody `enabled: bool = False`; OCC `expected_row_version` PUT'u) ve
Portfolio sayfası onu zaten "USE EQUITY ALLOCATION FOR THIS BACKTEST" checkbox'ı olarak
bağlıyordu (PR #113). Eksik olan Mainboard görünürlüğüydü; bu slice onu SERVER-TRUTH okumayla ekledi:

- **Mainboard "Use Allocation Backtest" şeridi (Mainboard.tsx):** STRATEGIES başlığı altında
  `useAllocationDraft(workspace_id)` pure-read projeksiyonundan `draft.enabled` rozeti
  (ON ok-tone / OFF neutral) + açıklama + `/portfolio` deep-link. Toggle'ın YAZMA yolu
  Portfolio'da kalır (OCC PUT orada) — şerit ikinci bir write-path değil; draft yüklenmeden
  hiçbir allocation durumu render edilmez (sahte state yok).
- **Per-item pay rozetleri:** allocation ON iken her satır başlığında
  `Share {equity_share_percent}%` (VERBATIM, client capital math yok — PR #113 kuralı) /
  `Share not set` / `Excluded from allocation` / `No allocation share`; expanded satırda
  "Edit share in Portfolio / Equity Allocation →" deep-link. Eşleşme
  `composition_item_id = mainboard_working_item.item_id` (models/allocation.py) üzerinden.
- **Invalidation zinciri değişmedi ve canlı kanıtlandı:** Portfolio Save draft →
  `["allocation"]+["readiness"]+["mainboard"]+["audit"]` (verbatim) → Mainboard şeridi
  ON↔OFF iki yönde tarayıcıda yansıdı (canlı stack, console temiz).
- **Dürüst sınırlar:** (1) sleeve TUTARLARI yalnız server'ın derived preview'ında
  (PUT/validate dönüşleri) var — Mainboard yüzde payı gösterir, tutarlar Portfolio'da;
  (2) canlı dev DB'de attached item olmadığından per-item rozet tarayıcıda boş kompozisyonla
  değil vitest'te kanıtlandı (Share 40% / No allocation share / deep-link, 3 yeni test);
  (3) pay atama/düzenleme Portfolio editöründe kalır (deep-link modeli, prompt'taki seçenek A).
- Backend DEĞİŞMEDİ; migration yok. vitest 514/514 (+3); tsc/eslint/build temiz.

---

## V18-R2 · KALAN-A — Market Data ham kaynak dosya UPLOAD UI ✅ (video 9:24–12:37, GAP 18)

Videodaki EN GÜÇLÜ şikâyet kapandı: kullanıcı artık Market Data kurulum kartında GERÇEK dosyayı
**Browse File** ile seçerek süreci BAŞLATIYOR — tek submit create → upload → finalize → analysis
zincirini koşuyor; analysis job'ı gerçek bytes'ı parse edip revizyonu `verified`'a taşıyor ve
detail polling ile sonuç kendiliğinden görünüyor; Admin approve + approved-bundle resolve UI'dan.

- **Empirik kopukluk tespiti (canlı stack):** backend zinciri (PR #103/#105) API'den uçtan uca
  sağlamdı (`draft→uploading→analyzing→verified`, validation `pass`); UI'da (1) kurulum kartında
  dosya seçici hiç yoktu ("önce create et, aşağıda Step 1'i bul" notu), (2) Upload/Finalize/
  Request analysis 3 ayrı manuel buton, (3) analysis sürerken sayfa kendini yenilemiyordu.
- **CreateDatasetCard (MarketData.tsx):** birincil `Raw source file *` Browse File girişi;
  "Create dataset & upload" TEK submit → `create → upload (progress + Cancel) → finalize →
  analysis` aşama listesi (`IngestStageList`, aria-live, Done/Running/Failed/Pending textual).
  Hata → "Retry from failed step" KALINAN aşamadan devam eder (dataset yeniden yaratılmaz,
  kabul edilmiş bytes yeniden gönderilmez). Sözleşmeler verbatim: create Idempotency-Key'siz;
  upload/finalize/analysis her denemede TAZE key; ham bytes sayfadan geçmez — evidence satırı
  server-türevi asset id + digest pinler.
- **Detail polling (lib/marketData.ts, additive):** `ingestRefetchInterval` pure helper —
  yalnız `uploading`/`analyzing` 2s poll, diğer her state durur; `useMarketDataset`
  `refetchInterval` ile `verified`/`needs_review` sonucu manuel refresh'siz düşer.
- **e2e 02 tam yolculuğa genişledi (26s yeşil, canlı stack):** Browse File → chained ingest →
  `Analysis requested` (202) → detail poll ile `verified` → AYRI admin context approve →
  owner'da `approved` + "Resolve approved bundle" → `Pinned — revision`. Her state TEK TEK
  assert. POM `MarketDataPage` genişletildi (spec 03 aynı POM ile yeşil).
- routes/market_data.py DEĞİŞMEDİ; migration yok. vitest 511/511 (marketData 29);
  tsc/eslint/build temiz.

---

## V18-R2 · R2-12 — CP typed baseline metadata + request→published tam lifecycle E2E ✅ (GAP madde 11)

Create Package baseline metadata artık uçtan uca typed alanlar; e2e 04 Pre-Check'te durmuyor —
request → published → Library `can_use=yes` TEK gerçek Playwright yolculuğunda kanıtlı.

- **Typed baseline metadata (lib/createPackage.ts + CreatePackage.tsx):** backend'in parse
  gate'inin GERÇEKTEN istediği 7 anahtar (`domain/create_package/baseline.py
  REQUIRED_BASELINE_METADATA_FIELDS`: provider/symbol/timeframe/range/timezone/settings/
  source_revision_context) typed product alanı — range iki input (`start`/`end` → `{start,end}`
  objesi). `buildBaselineMetadata` pure composer (typed alan Advanced extras'ı gölgeler; boşlar
  omit). Advanced JSON disclosure `useIsAdmin` (AdminGate) arkasında kaldı — normal kullanıcı
  JSON yazmaz.
- **Aşama gating nedenleri:** `packageActionAvailability` +`reasons` (precheck/generateDraft/
  runValidation/approve/parseBaseline; null=açık) — hepsi server projeksiyonundan (state/
  can_generate_candidate/scan.status/precheck_fresh/draft_revision_id/approvalBlockReason).
  `LockReason` notu doğrudan kilitli kontrolün yanında ("Pre-Check has not PASSED (blocked).",
  "No draft package yet — create one first (C.D.P).", …). **Approve AdminGate'li** (R2-09
  deseni): non-Admin buton yerine "Admin approval required — … awaiting an Admin approval
  decision" notunu görür; yetki her zaman server'da (CR-02, 403 verbatim).
- **EMPİRİK KÖK NEDEN — declared dependency signature:** ESP resolver EXACT sıralı param tipi +
  return eşleşmesi yapar (`domain/esp/resolver.py::signature_matches`, doc 09 §4.2); UI declared
  dep'i yalnız `{key}` gönderiyordu → boş signature ↔ 2-param `ta.sma` kontratı =
  `RESOLVER_SIGNATURE_MISMATCH` → UI'dan Pre-Check PASSED YAPISAL olarak imkânsızdı. Fix:
  declared-dependencies satırı opsiyonel `key(type,…)->return` sözdizimi
  (`parseDeclaredDependencies`; çıplak `key` hâlâ `{key, signature:{}}`) — CP command sözleşmesi
  DEĞİŞMEDİ (`clean_declared_dependencies` ikisini de zaten kabul eder).
- **e2e 04 tam yolculuk (6.1s yeşil):** normal kullanıcı compose (typed alanlar, family select,
  `ta.sma(series,int)->series`) → Pre-Check **passed** (exact status line) → C.D.P draft →
  typed baseline + CSV upload → parse **passed** → validation **passed** → owner'da AdminGate
  notu assert → AYRI admin context (`ensureAdmin`) request'i seçip Approve → "Approved &
  published" → owner Library'de kendi `pkg_` root detayında `can_use: yes` hücresi. Her state
  TEK TEK assert; "blocked/error da kabul" YOK. POM `CreatePackagePage` tam lifecycle'a
  genişletildi.
- **Stack ön koşulu (e2e/README):** canlı DB'ye `SEED_ESP_TA=1 SEED_RATIONALE=1` plain seed
  gerekli (SEED_E2E_GOLDEN canlı ESP registry'sini SEED ETMEZ — golden paket frozen snapshot
  taşır); bu oturumda `entropia_e2e07` DB'sine seed edildi. X-Request-Version OCC +
  Idempotency-Key davranışları verbatim korunmuş (vitest assert'leri değişmedi).

Evidence: e2e 04 yeşil + tüm e2e suite **20/20** (dev server :5173 + gerçek API :8000);
vitest **508/508** (createPackage 23); tsc/eslint/build temiz. GENERATOR_VERSION/ENGINE_VERSION
sabit; backend DEĞİŞMEDİ.

---

## V18-R2 · R2-11 — Mobil app-shell overflow sıfır ✅ (GAP madde 15, PR #339)

375px'te ortak shell'in dayattığı ~513px minimum genişlik kapandı. Suçlu empirik tespit:
`.menu-bar` min-content 513px (viewport 375 iken layout 512'ye genişliyordu; başka eleman
taşmıyordu).

- **Layout.tsx**: `mobileNavOpen` state + `.menu-hamburger` (`aria-expanded`/`aria-controls`) +
  `.menu-bar-menus` sarmalayıcı (masaüstünde saydam flex passthrough — DOM'daki tek değişiklik).
  Drawer içinde herhangi bir navigasyon/aksiyon delegated click ile drawer'ı kapatır.
- **global.css**: `@media (max-width: 760px)` bloğu — menü bar hamburger disclosure; dropdown +
  submenu'ler position:static, HER ZAMAN AÇIK in-flow ağaç (touch'ta hover bağımlılığı yok);
  workspace padding 16/12 + alt 150px; `.run-controls` 10px köşe (viewport'u örtmez);
  `.cp-form` tek kolon. Masaüstü (>760px) kuralları DEĞİŞMEDİ (1280'de tarayıcıda doğrulandı:
  hamburger display:none, yatay 34px bar). Inline Strategy/TS/TL panelleri zaten ≤980
  `.details-grid` tek kolon.
- **e2e/specs/09-responsive-overflow.spec.ts (YENİ)**: 5 genişlik (375/768/1280/1440/1920) ×
  4 ekran (Mainboard, TS inline draft, Market Data, Panel/Management)
  `document.scrollWidth <= viewport` + `test-results/responsive/*.png` evidence seti + 375px
  hamburger yolculuğu (aç → link görünür → Market Data'ya git → drawer kapanır). NOT: shell'in
  kalıcı SSE stream'i yüzünden `networkidle` OTURMAZ — spec `main` mount + kısa settle bekler.

Evidence: e2e 09 → 6/6 yeşil (dev server :5173 + gerçek API :8000); vitest 492/492;
tsc/eslint/build temiz. Remediation status "Ortak shell — mobil overflow" bullet'ı eklendi.
**Dürüst sınır:** screenshot seti 4 çekirdek ekran; 22 sayfa tam görsel kabul → R2-13.

---

## V18-R2 · R2-09 — Role-aware presentation: Admin-only eylemler `/me` ile fail-closed gizli ✅ (GAP madde 10)

Admin-only eylemler yetkisiz kullanıcıya primary kontrol olarak GÖRÜNMEZ; yerine read-only durum +
"Admin approval required" açıklaması. Presentation-only — HİÇBİR command/route çağrısı değişmedi:

- **`components/AdminGate.tsx` (YENİ, ortak)** — `useIsAdmin()` (`useMe` REUSE;
  `me.data?.is_admin === true`; loading/error/non-admin hepsi fail-closed "not admin") +
  `AdminApprovalNote` (`role="note"`, "Admin approval required — …" + yüzeye özgü read-only
  detay) + `AdminGate` wrapper. UI-22/R2-05b'deki dağınık `useMe` gate'lerinin ortak modülü.
- **Envanter (6 yüzey gate'lendi):** MarketData `ApprovalComposer` (Approve/Deprecate) ·
  ResearchLifecycle `ApprovalComposer` (Approve/Revoke) · Embedded ESP `LifecycleActions`
  (Activate/Deprecate — trust_state read-only notta) · Trash satır eylemleri (Restore/Permanent
  Delete gizli; Open Snapshot okuma yüzeyi kalır) · Panel/Management `UserRow` Assign hücresi +
  `OperatorRecoveryCard` disclosure'ı · User Manual bakımı (sidebar Add/Upload/Restore +
  section Replace/Delete; okuyucu + arama herkese açık).
- **Zaten-doğru referanslar (değişmedi):** Library per-entity SERVER `permissions.*` projection
  (can_approve_publish/can_deprecate/…) · FutureDev capability transition (UI-22 gate'i).
- **Yetki modeli:** client görünürlüğü authorization DEĞİL — server her dispatch'te
  `ensure_can_approve` / `esp_policy.ensure_can_activate` / `require_trash_admin` /
  `require_admin_panel` / `require_manual_admin` yeniden doğrular; mevcut 403-verbatim testleri
  ADMIN `/me` + server-denial (stale-cache) senaryosu olarak AYNEN yeşil.

Evidence: vitest **504/504** (12 YENİ görünürlük testi: 6 yüzeyde non-admin gizli+not +
fail-closed `/me` unavailable; OCC/Idempotency/403 assert gövdeleri byte-korundu — yalnız `/me`
stub'ı eklendi ve async `findByRole` hizalaması yapıldı); tsc/eslint/build temiz. Canlı tarayıcı:
dev server `:5179` (`.env.r209`, gitignored) → sentetik fixture stub API `:8009` (`/__role` ile
admin flip) — non-admin taramada 6 yüzeyin hiçbirinde Admin primary butonu yok, her yüzeyde not;
admin flip sonrası hepsi görünür/çalışır durumda (Embedded trusted_active doğru olarak yalnız
Deprecate sundu).

**Dürüst sınır:** tarayıcı kanıtı sentetik stub API üzerinde (403 verbatim davranışı zaten
vitest'te; canlı backend E2E'leri admin aktörle koşar — gate onları etkilemez). Non-admin gerçek
backend taraması R2-13 görsel kabul zincirinde tekrarlanacak.

---

## V18-R2 · R2-13 — 22 sayfa screenshot matrisi + V18 side-by-side + screenshot regression ✅

- **Baseline matris (canlı seeded stack, host-native):** `frontend/e2e/screenshots/baseline/`
  — 122 PNG: `normal` 77 (22 sayfa+panel-logs × 1280/1440/1920, +375/768 Mainboard ve üç
  inline-editör satırı), `empty` 14, `loading` 14 (API stall ile deterministik), `error` 14
  (zorlanmış 500 zarfı), `permission-denied` 3 (adminOnly sayfalar, plain user). Adlandırma
  `<sayfa>/<durum>--<genişlik>.png`.
- **V18 prototip referansları:** `frontend/e2e/screenshots/prototype/` — 20 ekran @1440,
  mockup'ın kendi `show*` fonksiyonları çağrılarak (specs/09). Mockup dev kopyası
  `frontend/public/mockup_v18.html` (gitignored) — üretimden önce `cp docs/spec/...v18.html`.
- **Sapma listesi:** `docs/implementation/v18_visual_deviations.md` — madde madde; 6 FIX adayı
  (F-1 mobil taşma/katman, F-2 display-label haritası, F-3 CP form yerleşimi, F-4 allocation
  ULID adayları, F-5 history headline metrikleri, F-6 TS/TL form yoğunluğu) + PO-APPROVE
  kümesi. Hiçbir madde Complete İLAN EDİLMEDİ — yazılı PO onayı R2-14.
- **Screenshot regression:** `specs/11-visual-regression.spec.ts` — 8 kritik sayfa
  (Mainboard, Strategy/TS/TL, Market Data, Create Package, Ready Check, RUN) `toHaveScreenshot`
  (maxDiffPixelRatio 0.02, animasyon kapalı, `time`/`[data-e2e-volatile]` maskesi, 1440×900).
  Baseline'lar commit'li (`-darwin` platform eki); komutlar: `npm run visual` /
  `npm run screenshots:update`. Varsayılan `npm test` bu üç katmanı grep-invert ile dışlar.
- **Sınır:** uygulama koduna dokunulmadı (test-id dahi gerekmedi); yalnız e2e suite + docs.
  Loading/empty dürüst sınırları README §R2-13'te.

## V18-R2 · R2-14 — Nihai kabul geçişi ✅ (GAP madde 17 + 20) — **R2 DALGASININ SON SLICE'I**

Çıktı: **`docs/implementation/v18_final_acceptance.md`** — GAP madde 20'nin 11 kabul koşulu canlı
seed'li stack'te tek tek doğrulandı, her koşula kanıt referansı yazıldı. **10/11 PASS**; 20.11
(22 sayfa screenshot setinin kabulü) **PO imzasına** bağlı olduğu için AÇIK.

- **Kapatılan bulgular:** 375px yatay taşma — Mainboard section grid'inin auto track'i 64
  karakterlik composition hash'inin min-content genişliğine büyüyordu (375px'te 640px section);
  `minmax(0,1fr)` + `overflow-wrap` ile taşan eleman **110 → 0**. Escape ile kapanma — YENİ
  `frontend/src/components/useEscapeToClose.ts` Add menüsü + Add Package popover'ına bağlandı,
  focus tetikleyiciye döner.
- **Kayıtlı a11y sapmaları (PO kararı):** A11Y-01 — 228 serious contrast node'unun tamamı
  canonical v18 paletinden (`--accent #00a9e8`, `--text-dim #888888`) → **tema kararı, kod
  düzeltmesi değil**; A11Y-02 `link-in-text-block`. 22 sayfada **critical = 0**. Tarama gate'i
  sınırı dondurur: kayıtlı iki kural dışında serious ihlal koşuyu düşürür.
- **Yeni opt-in katman:** `e2e/specs/13-a11y-scan.spec.ts` + `14-keyboard-flow.spec.ts`,
  `npm run a11y` arkasında (düz `npm test`'ten hariç).
- **Test:** e2e 20/20 · a11y 2/2 · responsive 6/6 · vitest **514/514** · tsc + eslint temiz.
- **Sınır:** hiçbir remediation-status satırı Complete'e ÇEKİLMEDİ (GAP madde 17 — PO imzası
  şart); ekran okuyucu denetimi YAPILMADI; klavye denetimi temel akışla sınırlı; 10 sayfanın
  derin görsel kıyası açık; doğrulamalar host-native local stack'te (bu oturumda CI'da koşmadı).
- **PO karar tablosu:** D-1…D-9 → `v18_final_acceptance.md` §4.

## Auth remediation wave — landed (PR #346–#364, merged → main `6e3fab9`)

İki güvenlik denetimi (`docs/spec/Entropia_Authentication_Remediation_Claude_Code_Deep_Audit.md`
AUTH/PROV/DEP/TEST + `Entropia_Auth_Mode_Login_Fix_Claude_Code_Prompt.md`) W2–W8 dalgaları halinde
kapatıldı. **Migration YOK — alembic head `0035_portfolio_rules` SABİT, `ENGINE_VERSION` SABİT.** OCC
token biçimleri / Idempotency-Key / react-query key'leri / SSE taksonomisi verbatim; sadece SSE
handshake auth + payload sıkılaştırıldı (AUTH-11).

- **#346** login-fix — frontend sunucunun runtime AUTH_MODE'unu izliyor; dev-mode insan login sunucu-reddi.
- **#347/#348 (W2, AUTH-01..07)** — dev-mode human-login reject + **fail-closed runtime-auth boot gate** + transport başına tek credential.
- **#349 (W3, AUTH-11)** — SSE handshake authenticate + payload minimize (anonim abonelik kapandı).
- **#357 (W4, PROV-02..05)** — credential-aware operational Admin count (`identity.count_login_capable_admins` / `count_operational_admins(auth_mode)`); bootstrap-status `login_capable_admin_exists` (+openapi, `Provisioning.tsx`); `roles.py` advisory lock; seed `_ensure_principal` fail-closed.
- **#358 (W5, DEP-04/05, TEST-11)** — explicit session/dev-auth Compose profilleri + worker healthcheck + fail-fast test.
- **#359 (W6, TEST-06..10)** — integration DB izolasyonu + auth test matrisi; revoked `/me` → 401 `SESSION_INVALID`.
- **#360 (W7, §9.4/9.5/9.6)** — 3 auth kabul akışı için gerçek izole Docker E2E.
- **#361 (W8-frontend, AUTH-08/09/10)** — cross-tab session-sync + canonical error kodları + güvenli stale-session redirect.
- **#362 (DEP-03/06)** — non-destructive .env config audit scripti + auth-mode-aware smoke.
- **#363 (W8, PROV-06)** — mode-safe Compose baseline provisioning + legacy `retire_dev_admin` scripti kaldırıldı.
- **#364 (AUTH-10 residual)** — cross-tab session-sync (storage relay) kapsama testi (son merge).

Aynı gün dependabot: #350/#351/#352 (CI actions@7), #354/#355 minor-patch grupları, #356 boto3-stubs.
**Test (CI server-truth `6e3fab9`):** backend **1841 passed** · frontend vitest **577/58 dosya** · E2E green.
**DEFERRED (dürüst sınır):** dependabot #353 (python 3.13→3.14-slim) **KAPATILDI** — `requires-python <3.14`
(ruff py312, mypy 3.12); `.github/dependabot.yml` Docker `/backend` ekosistemine **python-major ignore
guard'ı EKLENMEDİ** (yoksa haftaya yeniden açılır); tam 3.14 migration ayrı manuel bir dal. Tam kayıt +
madde-madde durum: `docs/PROJECT_HISTORY.md` §"Auth remediation dalgası".

## V18-R3 · F-05 / M-05 — makine-okur capability matrix landed (PR TBD)

**Migration YOK** (alembic head `0035_portfolio_rules` sabit) · **`ENGINE_VERSION` →
`backtest-engine-v18-capability-matrix`** (davranış değişti → execution_key namespace kaymalı).

- **Tek kanonik veri:** `backend/src/entropia/domain/backtest/capabilities.py` — her opsiyon
  **DEĞERİ** için `active_v1` | `future_dev` + `dependency` (bağımlılık / eksik veri serisi) +
  `blocker_code`. **59 satır, 22 future_dev.** Public: `capabilities_are_modelled()`,
  `future_dev_selections()`, `option_status()`.
- **Üç tüketici, tek kaynak:** engine (fail-closed gate `_open()` choke-point'inde + L4
  `capability_not_in_build:*` warning'leri + `capabilities_modelled` diagnostics) · Ready Check
  (`STRATEGY_CAPABILITY_NOT_IN_BUILD` = **"Not available in this build"**, remediation = matrisin
  `dependency`'si) · UI (üretilen `frontend/src/lib/engineCapabilityMatrix.generated.ts` aynası;
  `SelectField capabilityField` → 9 select'te disabled + açıklama).
- **Gerçek bulgu (silent, "fail eden" değil):** `slippage_mode='historical_slippage_if_available'`
  dokuz per-domain predikatın HEPSİNİ geçiyordu; `_cost_params` MODE'a bakmıyor ve schema o modda
  `slippage_value`'yu optional yapıyor → **sessizce SIFIR slippage** ile iyimser backtest. Artık
  fail-closed + Ready Check blocker.
- **Dokuz per-domain predikat korundu** — matrisin ifade edemediği misconfiguration'ları (eksik
  `trigger_offset`, pozitif olmayan cap, parse edilemeyen filter config) onlar yakalıyor.
- **Anti-drift:** `tools/export_capability_matrix.py` TS aynasını render eder;
  `test_capability_matrix.py` byte eşitliği + **schema `Literal` ↔ matris tam küme eşitliği** iddia
  eder → `config.py`'ye sınıflandırılmamış yeni opsiyon eklenirse CI patlar.
- **Kayıtlı `future_dev` değer seçilebilir kalır** (aksi hâlde mevcut strateji düzenlenemez olur ve
  form kayıtlı config'i sessizce yeniden yazar); çalıştırmayı Ready Check engeller.
- **Testler:** backend `tests/unit/test_capability_matrix.py` (exhaustiveness · 22 future_dev için
  blocker+inert-engine parity · active_v1 baseline gerçekten trade açar) · frontend
  `src/test/engineCapabilityMatrix.test.tsx` (10 test). Tam kayıt: `docs/PROJECT_HISTORY.md`
  §"V18-R3 · F-05 / M-05".
- **Gözlemlenebilirlik notu:** `capability_ok` flat-entry gate'ine **eklenmedi** — eklenince F-10
  `entry_blocked` decision-trace event'i hiç üretilmiyordu. Gate `_open()`'da (her entry yolu oradan
  geçer), `_blocked_reason()`'da ise **en sonda** (per-domain sebep daha spesifik ve sözleşmeli).



## Next: **PO imzası + R2 kapanışı** (R3 mühendislik backlog'u F-05 ile kapandı).
R3 W3 dalgası: F-01a/b/c (durable worker'lar) · F-04+F-09 (PR #381) · **F-05/M-05 (bu slice)**
landed. Kalan tek büyük açık iş hâlâ **R2'nin product-owner imzası**. Sırada:
> 0. **F-07 (raw-id presentation sweep residuals)** — kickoff'ta W3 kalemi; traceability tablosunda
>    "overlaps P-11/12/16" notuyla `Not started`. P-11/12/16 landed olduğu için gerçekten artık
>    kalıntı olup olmadığı **empirik doğrulanmalı** (bu slice onu kapsamadı).

Auth remediation (#346–#364) merge oldu; kalan tek açık iş **R2'nin product-owner imzası** + iki
opsiyonel deferred. Sırada:
> 1. **Product-owner imzası** — `docs/implementation/v18_final_acceptance.md` §4'teki D-1…D-9
>    kararları (görsel sapmaların toptan kabulü, F-2…F-6 mini slice'ları, A11Y-01 için (a)/(b)/(c),
>    20.11 onayı). **İmza olmadan `entropia_v18_remediation_status.md`'deki R2 RE-OPENING banner'ı
>    kalkmaz ve hiçbir satır Complete olmaz.**
> 2. **İmza sonrası:** banner kaldırılır, UI-01/02/03/04/05/06/12/14/15 satırları gerçek evidence
>    referanslarıyla (spec adı + screenshot yolu + PR) Complete'e çekilir.
> 3. **PO'nun mini slice istediği maddeler** (F-2 display label'ları, F-3 CP alan yerleşimi,
>    F-4 Portfolio ham ULID, F-5 Results History satır özeti, F-6 TS/TL grid sıkılaştırma,
>    A11Y-01 palet kararı) ayrı slice'lara açılır.
> 4. **Kapsam dışı kalan açık işler:** ekran okuyucu (NVDA/VoiceOver) denetimi, 10 sayfanın derin
>    görsel kıyası, CI'da a11y/visual katmanlarının koşturulması.
> 5. **Auth deferred (opsiyonel, kod-değişikliği yok):** (a) `.github/dependabot.yml` Docker `/backend`
>    ekosistemine `python` için `ignore: version-update:semver-major` guard'ı — yoksa dependabot #353
>    (3.14-slim) haftaya yeniden açılır; (b) tam Python 3.14 migration (requires-python + ruff/mypy
>    target + Dockerfile) ayrı manuel test edilen dal.

## Eski Next (R2 dalgası başlarken): **`docs/V18_R2_ROADMAP.md` otoritedir.** Yeni GAP belgesi
(`docs/spec/Entropia_V18_Guncel_Arayuz_Eksikleri_ve_Yanlis_Anlamalar.md`) kodda empirik
CONFIRMED 13 eksik kümesi tespit etti (Mainboard TS/TL inline editör yok, Add Package popover yok,
üst menü Mainboard'ı bypass ediyor, TS/TL + Strategy + CP ham JSON formları, Research sahte
dependency kilidi, golden-path E2E blocked'ı kabul ediyor, API timeout yok, 513px mobil overflow,
screenshot seti yok). Yol haritası 16 slice + 2 kapanış aşaması halinde, HER SLICE İÇİN paste-ready
prompt ile `docs/V18_R2_ROADMAP.md`'de: P0 = R2-01a/01b/02/03/04/05a/05b/06/07 (Mainboard merkezli
tek çalışma alanı + typed formlar + server-truth kilitler + gerçek golden-path E2E), P1 =
R2-08/09/10/11/12 + KALAN-A/KALAN-B (aşağıda, yol haritasına katlandı), P2 = R2-13/14 (screenshot
matrisi + PO onayı). `entropia_v18_remediation_status.md`'ye R2 RE-OPENING banner'ı eklendi
(UI-01/02/03/04/05/06/12/14/15 fiilen In Progress). Video-alignment kalan işleri (KALAN-A/B) yol
haritasında kendi prompt'larıyla korunuyor:
> - **KALAN-A — Market Data ham kaynak dosya UPLOAD UI (video 9:24–12:37) ✅ TAMAM (yukarıdaki KALAN-A landed girdisi):** videonun EN GÜÇLÜ şikâyeti — "süreci başlatacak ham kaynak dosya yükleme seçeneği maalesef yok" (11:00, 12:37). Backend ingest zinciri (`routes/market_data.py` create/upload-start/finalize/analysis) PR #103'te bağlıydı ama **Raw Source File / Browse File** akışı (ham dosyayı seçip standart Entropia yapısına dönüştürme, sonra Create Dataset / Approve for Use) UI'da eksik/çalıştırılamaz. Frontend slice — backend yüzeyi hazır.
> - **KALAN-B — Portfolio Equity Allocation "Use Allocation Backtest" + per-item pay UI (video 7:16–9:24) ✅ TAMAM (yukarıdaki KALAN-B landed girdisi):** strateji evreni kuruluyorsa toplam portföyün üst seviye paylaşımı gerekir (Strategy 1 / Strategy 2 / Trade 1 / Trade Log 1 payları). Portfolio sayfası PR #113'te + portfolio-level kurallar PR #320'de (Max Total Exposure + cross-item conflict) landed; ancak videodaki **"Use Allocation Backtest" toggle + Mainboard'daki her öğeye pay atama** deneyimi tam değil. Portfolio + Mainboard hizası — backend allocation yüzeyi hazır.
> - **KALAN-C — öğe evrene katkısı / "entropiyi nasıl değiştirdiği" (video 3:35) ✅ TAMAM:** Trade Log / bir öğenin toplam strateji evrenine katkısı **PR #319 (per-item contribution breakdown — correlation, diversification, marginal deltas) + PR #320 (portfolio-level rules)** ile karşılandı. `#321` (allocation portfolio-rule alanları için openapi snapshot rejenerasyonu) AÇIK — merge bekliyor.
>
> **KAPSAM DIŞI (değişmedi):** retention auto-purge (doc 20 §16), LLM generation (Future-Dev), Graphic View renderer (doc 22). alembic head `0023_audit_log_trgm_indexes` SABİT, `ENGINE_VERSION` SABİT. Başlamadan ilgili doc + route/command imzaları + queries/commands dönüş dict'lerini oku → wire tipleri VERBATIM ayna.

**V1 COMPLETE (Stages 0–8, docs 01–22) + Auth/IdP + Parquet Slice A + Backtest Engine Slice B + real indicator compute Slice C + `risk_based` sizing (a) + condition blocks (b) + condition extensions (b2) + two-package indicator-vs-indicator + higher-timeframe resampling (c) + per-condition multi-TF reference (i) + N-ary reference chain (ii) + VWAP directional key (d) + `formula_based` Kelly sizing + `position_size_limits` min/max cap (PR #63) landed (1015 tests).** The **Slice C indicator-compute + position-sizing follow-ups are now EFFECTIVELY COMPLETE — TIER 1 backend is DONE**:

- ~~`risk_based` sizing (a)~~ ✅ **PR #47** · ~~`formula_based` / Kelly sizing~~ ✅ **PR #60 + non-finite fail-closed fix PR #61** — Kelly is now honored; **`custom_formula` + adaptive/rolling Kelly stay honest `unresolved`** (no safe eval / path-dependent look-ahead) → notional fallback + `position_sizing_method_unsupported`.
- ~~Condition blocks (b)~~ ✅ **PR #49** · ~~extensions (b2)~~ ✅ **PR #51** · ~~two-package indicator-vs-indicator~~ ✅ **PR #53** · ~~(i) per-condition multi-TF reference~~ ✅ **PR #56** · ~~(ii) N-ary reference chain~~ ✅ **PR #57** · ~~(d) VWAP directional key~~ ✅ **PR #58** — `ta.vwap` is a directional key (native trigger + reference package + N-ary leg). **Remaining:** only `ta.atr` stays non-directional **by nature** (a volatility band, no cross) → the honest terminal boundary; any FUTURE canonical key with a directional interpretation would extend `DIRECTIONAL_KEYS` the same way VWAP did.
- ~~**(c)** Multi-timeframe bar resampling~~ ✅ **PR #55**.

**Next candidates** (priority per `docs/POST_V1_KICKOFF.md`):
- ~~**TIER 1 — `position_size_limits` (min/max cap) wiring**~~ ✅ **PR #63** — `PositionSizeLimits` (min/max caps) now clamps EVERY sizing method via `_clamp_to_limits` at the `_raw_position_size → _position_size` boundary; `ENGINE_VERSION → backtest-engine-v2-position-size-limits`; +15 tests → 1015; no migration. **TIER 1 backend is now EFFECTIVELY COMPLETE** (Kelly + risk_based + condition blocks + multi-TF + N-ary + VWAP + position_size_limits all landed).
- **TIER 2 — frontend / user-facing (login + SSE landed):** ~~login / session integration~~ ✅ **PR #65** (Bearer session store + standalone `/login` page + signup/logout + role-aware header; `frontend/src/lib/{session,auth}.ts`, `pages/Login.tsx`, `apiClient.ts` Bearer header) · ~~SSE live-invalidation~~ ✅ **PR #67** (`frontend/src/lib/sse.ts` stub filled: `EVENT_QUERY_KEYS` maps `backtest.run.updated`/`job.updated`/`agent.task.updated`/`audit.event.created` → `["backtests"]`/`["jobs"]`/`["agent-tasks"]`/`["audit"]`, `resource.changed` → full refresh, reconnect self-heal; +7 vitest → 16/16) · ~~**`/v1/metrics` dashboard**~~ ✅ **PR #69** (`lib/metrics.ts` Prometheus text-exposition parser + `apiGetText`/`useMetrics` 5s poll + `pages/Metrics.tsx` golden-signals / jobs-depth / outbox-lag / lease-age panels + adminOnly `System Metrics` nav item at `/panel/metrics`; +13 vitest → 29/29) · ~~**live-data backtest RUN + Results History**~~ ✅ **PR #72** (`lib/backtest.ts` `["backtests"]` hooks + `pages/BacktestRun.tsx` `?run=`/`?result=` modes + `pages/ResultsHistory.tsx` + `ResultDetail.tsx`; first pages bound to the SSE forward contract; +7 vitest → 36/36) · ~~**Arrange Metrics + Analysis Lab live pages**~~ ✅ **PR #74** (`lib/metricProfile.ts` + `pages/ArrangeMetrics.tsx` profile editor with OCC Apply/Lock/Unlock; `lib/agentLab.ts` + `pages/AnalysisLab.tsx` — every key under the `["agent-tasks"]` prefix, second SSE key live; If-Match runtime controls; +9 vitest → 45/45) · ~~**Panel / Management / Logs live page**~~ ✅ **PR #78** (`lib/adminPanel.ts` — Management under `["admin"]`, Logs/Audit under the LAST bindable SSE key `["audit"]`; `useAssignRole` OCC `expected_head_revision_id` with role options from the server role-matrix assignable rows; `pages/Panel.tsx` 5 cards; +6 vitest → 51/51) · ~~**history compare/soft-delete + profile-hydrated result metrics**~~ ✅ **PR #80** (`lib/backtest.ts` `useCompareResults`/`useResultMetrics`/`useSoftDeleteResult`; `ComparePanel` verbatim context diff — RH-09; ResultDetail rebound to the doc-17 §9.1 hydrated projection with persisted-rows fallback; +7 vitest → 58/58). · ~~**capability activations / Future Dev registry page**~~ ✅ **PR #82** (`lib/capability.ts` doc-22 taxonomy mirror + OCC/Idempotency-Key transition hook; `pages/FutureDev.tsx` registry/detail/transition composer + Graphic View overview; +9 vitest → 67/67). · ~~**first-Admin provisioning dashboard**~~ ✅ **PR #84** (`GET /auth/bootstrap-status` + `lib/provisioning.ts` `useBootstrapStatus` `["auth"]` + `pages/Provisioning.tsx` window/identity/explainer; nav 23→24; +8 backend → 1036 / +6 vitest → 73; read-only — provisioning stays server-side + signup-time). · ~~**Admin Trash restore page**~~ ✅ **PR #86** (`lib/trash.ts` `["trash"]` hooks + `useRestoreEntry` OCC `expected_head_revision_id` + fresh Idempotency-Key; `pages/Trash.tsx` server-truth `restore_eligible` gating + server-hydrated object_type filter + immutable snapshot detail; `App.tsx` `/trash` REAL_PATHS, `nav.ts` unchanged; +7 vitest → 80; frontend-only). · ~~**Create Package request page**~~ ✅ **PR #91** (`lib/createPackage.ts` `["package-requests"]` hooks + fresh-Idempotency-Key create + `pages/CreatePackage.tsx` compose/list/detail; +7 vitest → 89; frontend-only). · ~~**CP request actions + Pre-Check page**~~ ✅ **PR #93** (`lib/createPackage.ts` extended: `useRunPrecheck`/`useGenerateCandidate` OCC `X-Request-Version` + fresh Idempotency-Key, `useCreateDraft` `expected_candidate_hash` body token, `useApproveRequest` draft-head token Admin-only CR-02, `useDependencyScan`; `RequestActions` bar + NEW `pages/PreCheck.tsx` §7.1 rows + scan artifact viewer; +9 vitest → 98; frontend-only). · ~~**capability operational POSTs**~~ ✅ **PR #95** (`lib/capability.ts` extended: `ANALYSIS_ARTIFACT_CAPABILITY` mirror + `useQueryViewDataset`/`useCreateAnalysisArtifact` fresh-Idempotency-Key creates invalidating `["audit"]` only; `ViewDatasetComposer` + `AnalysisArtifactsCard` in `pages/FutureDev.tsx`, never client-pre-gated — `CAPABILITY_NOT_ACTIVE` verbatim; +7 vitest → 105; the FULL `routes/capability.py` surface is now bound). · ~~**Package Library catalog page**~~ ✅ **PR #97** (`lib/library.ts` `["library"]` hooks + facet taxonomy mirrors + `pages/Library.tsx`; +8 vitest → 113). · ~~**Embedded System Packages page**~~ ✅ **PR #99** (`lib/esp.ts` `["esp"]` hooks + resolve probe + `pages/Embedded.tsx`; +8 vitest → 121). · ~~**Rationale Families page**~~ ✅ **PR #101** (`lib/rationale.ts` full CRUD + `useBatchAssign` `expected_table_version`; `pages/RationaleFamilies.tsx`; +7 vitest → 128). · ~~**Market Data page**~~ ✅ **PR #103** (`lib/marketData.ts` `["market-data"]` reads + ingest chain; `pages/MarketData.tsx`; +12 vitest → 140). **Remaining candidates:** Market Data lifecycle ACTIONS follow-up (revise/successor + Admin approve/deprecate — If-Match `"rv-N"` OCC + Idempotency-Key; closes the PR #103 boundary — natural next) and the 8 remaining placeholder pages, ALL with landed V1 backend surfaces — Packages & Data (`research_data.py` Research Data — closes the group), Workspace (`strategy.py` Strategy Details / `trading_signal.py` / `trade_log.py` / outsource-signal), Backtest (`allocation.py` Portfolio / `readiness.py` Ready Check), Docs (`manual.py` User Manual); ~~ESP registry MUTATION slice~~ ✅ **PR #121** (`lib/esp.ts` extended: `postWithRegistryVersion` X-Registry-Version HEADER-form plain-int OCC + fresh Idempotency-Key; propose/activate/deprecate composers in `pages/Embedded.tsx`; +5 vitest → 213 — the FULL `routes/esp.py` surface is now bound; `library.py` was already 2/2, no Library mutation slice exists); ~~outsource-signal chooser page~~ ✅ **PR #123** (`pages/OutsourceSignal.tsx` — doc 03 type chooser, PURE presentation, no backend surface at all; REAL_PATHS 23→24 → **TIER 2 page map COMPLETE, no placeholder remains**; +6 vitest → 219). **Natural next:** Mainboard live page + composition operations (doc 01 — `routes/mainboard.py` 7/8 endpoints unbound: external-work draft, generic work-object create/revisions, attach item, PATCH item pin/enable/reorder, snapshot, work-object soft-delete; `pages/Mainboard.tsx` is a 55-line static shell binding nothing — closing this would retire the PERMANENT "attach+pin+delete on no landed page" boundary); Trash purge re-auth slice; TIER 3 deferred items. `["jobs"]` has NO backend list surface — permanent honest boundary; Trash **purge** (destructive, needs re-auth) is a separate future slice.
- **TIER 3 — data/ops (deferred):** retention auto-purge, data-queue redelivery, SSE streaming e2e (connection drops), tool-call status shadowing (CR-08 follow-up), `summary["timeframe"]` resolution from market-revision metadata.

See **`docs/POST_V1_KICKOFF.md`** for reuse anchors and the paste-ready resume prompt.

## K-07 devamı — Market/Research fail-closed upload kapısı landed (PR #388)

K-07'nin ortak kapısı (`domain/importing/source_file.assert_supported_source_file`) artık **dört**
komut yüzeyinin hepsinde: trade_log, trading_signal, **market_data, research_data**. Son ikisinde
`original_filename` yok/boşsa tip kontrolü tamamen atlanıyordu; hata kodları surface bazında ayrı
kaldı (`MARKET_DATA_FILE_TYPE_NOT_ALLOWED` / `RESEARCH_DATA_FILE_TYPE_NOT_ALLOWED`). Migration yok;
şema/route/OCC/Idempotency değişmedi. Her yüzey için unit + integration testi eklendi.
Tam kayıt: `docs/PROJECT_HISTORY.md` §"K-07 devamı".

**Next değişmedi** (yukarıdaki §Next geçerli).

## K-03 — Engine funding sırası spec adım 2'ye taşındı landed (PR #398)

**Migration YOK** (alembic head `0035_portfolio_rules` sabit) · **`ENGINE_VERSION` →
`backtest-engine-v18-funding-step-order`** (K-04'ün `-full-pinning` bump'ının üstüne; davranış
değişti → execution_key namespace kaymalı).

- **Bulgu:** doc 15 §9.3 funding/fee/carry'yi **adım 2**'ye pinliyor; motor onu bar döngüsünün
  **sonunda** — entry ve scaling'den SONRA — uyguluyordu ve docstring'i 8 adım yerine funding
  içermeyen 3 adım ilan ediyordu. `equity` hem `_position_size` hem `_sleeve_capital` girdisi
  olduğu için her giriş/scale katmanı carry'si ödenmemiş equity ile boyutlanıyordu → perp funding'de
  **tek yönlü kümülatif** sapma + bir bar geç bağlanan `max_total_exposure`. Exit barında available
  olan charge ise tamamen **düşüyordu** (blok flat defter görüyordu).
- **Fix:** funding bar'ın başına (adım 2) taşındı; docstring kanonik 8 adıma güncellendi; döngü içi
  `# (n)` işaretleri kanonik numaralara hizalandı; **adım 1 K-02'nin `is_eligible_for_decision`
  kapısına açıkça bağlandı** (PR #393). Kod≠spec sırası olan iki yer (5/6 iç içe — cap'ler boyutun
  hesaplandığı yerde bağlanır; 3d bar close'unda çözülür) örtülmedi, belgelendi.
- **İki yönlü sonuç:** barın BAŞINDA açık pozisyon o barın kaydını öder (bar onu kapatsa bile);
  o barda AÇILAN pozisyon ödemez. Bir charge ile ilk giriş **asla aynı bara düşemez** (charge tutulan
  pozisyon, giriş flat defter ister) — testlerde yazılı sınır.
- **Ölçülen sapma:** fixture'da `funding_paid` 0.00 → 20.40, ikinci giriş 195.92000000 →
  195.51200000, `final_equity` 9796.00 → 9775.60. Aynı-bar scaling: funding off `scale_layer_added`
  (75.0) → funding on `scale_layer_rejected` (`sleeve_capacity`, cap 2482.19).
- **Testler:** 6 unit (**5'i düzeltme öncesi motorda kırılıyor** — `engine.py` stash'lenip ampirik
  doğrulandı) + 3 integration (DB revision → `resolve_funding_schedule` → `run_engine` + execution_key
  namespace kayması). ruff/format/mypy temiz; tam backend suite **exit 0**.
- **Uygulanamayan proof'lar (dürüst sınır):** migration ve yeni `create_*` yok → alembic up/down/up
  ve L1 FK insert-order proof'ları bu slice'a uygulanmaz.
- **Sürüm uyumu:** eski Result'lar kendi pinli `engine_version`'ları altında geçerli kalır fakat yeni
  sonuçlarla **karşılaştırılamaz**; karşılaştırmak için yeniden RUN gerekir.

Tam kayıt: `docs/PROJECT_HISTORY.md` §"K-03 · Engine funding sırası".

## Next: **PO imzası + R2 kapanışı** (değişmedi) · I-17 izlenebilirlik slice'ı landed (#416)

K-serisi durumu: K-01 (#386) · K-02 (#393) · K-04 (#397) · K-05 (#387) · K-06 (#395) · K-07 (#388)
landed; **K-03 bu slice ile landed (#398)**. Kalan tek büyük açık iş hâlâ **R2'nin product-owner
imzası** (`docs/implementation/v18_final_acceptance.md` §4, D-1…D-9) — imza olmadan
`entropia_v18_remediation_status.md`'deki R2 RE-OPENING banner'ı kalkmaz.

Ayrıca hâlâ açık: **F-07 raw-id presentation sweep kalıntısı** (empirik doğrulanmalı) ve
**ortam tuzağı**: paralel worktree oturumları paylaşılan `entropia_test` DB'sini ezer —
`TEST_DATABASE_URL` ile worktree'ye özel izole DB kullan.


## O-03 — Hata kodu taksonomisi: 18 kod adjudicated, 2 ölü sınıf silindi (PR #407)

**Ne landed.** Denetimin "25+ spec-kanonik hata kodu yok veya farklı isimde" bulgusu tek tek
ampirik sınandı. **19/19 kod gerçekten 0 hit** — ama davranışları zaten fail-closed uygulanmış,
yalnız farklı adla. **Hiçbir kod adı değiştirilmedi**; sapmalar `docs/PROJECT_HISTORY.md` §O-03'te
tam tablo halinde adjudicate edildi (K-07 içtihadı). PR #407 iki ölü sınıfı sildi
(`PrecheckAlreadyRunning`, `DeletePolicyBlocked`) ve bir ratchet testi ekledi. **Migration YOK.**

**Denetimin üç yanlışı.** `TICK_DATA_UNAVAILABLE` ölü değil (2 emit + 5 assertion);
`MetricAvailability.NOT_COMPUTED` emit ediliyor; TIMEZONE üçlüsünü "tek ada indirmek" reddedildi —
`TIMEZONE_REQUIRED` (timezone **yok**, HTTP envelope) ile `TIMEZONE_INVALID` (timezone **var ama
geçersiz**, TL-07 whole-file blocker) aynı kusur değil.

**Review sırasında zemin kaydı — dikkat.** Üç bulgu, doğrulandıktan sonra paralel slice'lar main'e
indiği için geçersizleşti: `PACKAGE_DEPENDENCY_CYCLE`'ı O-10 (#402) canonical adıyla ekledi;
`PublicationState.REMOVED`'ı O-15 (#409) canlandırdı (silinmedi, geri kondu); O-02 (#400)
`DeletePolicyBlocked`'a alan ekledi. Ayrıca **PR #408 boş merge oldu** — `aa75fca` çakışma çözümü
144 satırın tamamını düşürdü, merge commit'i var içeriği yoktu; bu PR kaydı yeniden yazıyor.
Ders: bu hızda bir main'de tek seferlik tarama yetmiyor — ratchet testi ölü kümeyi her koşuda
ağaçtan yeniden hesaplıyor.

**Açık iş.** (1) Kalan 5 ölü error sınıfı (`KNOWN_UNRAISED`) ayrı bir slice bekliyor.
(2) `docs/audit/audit_report.md` repoda yok — doğrulama açıkça sayılan 19 kodla sınırlı, "25+"
iddiasının kalanı hakkında bu kayıt hiçbir şey söylemiyor. (3) Lokal tam suite tek koşuda
tamamlanamadı (ortam kaynaklı); integration'ın otoritesi #407 CI'ıdır (6/6 yeşil).


## O-14 — Results History: explicitly shared görünürlük + Supervisor ayrımı landed (PR #417)

**Kusur (ampirik).** `backtest_result` satırının kendi visibility kolonu **yok**; doc 16 §1'e göre
Result bir composition'ın değişmez kanıt artifact'ı, dolayısıyla yetkinin kökü composition'ın
(`mainboard_workspace`) registry root'u. History indeksi bu kökü yalnız `owner OR Admin` çözüyordu
(`queries/results_history.py:106-118`); `resource_share` tablosu (Package paylaşımı için GAP-17'den
beri **mevcut**) sorguya hiç bağlanmamıştı. Sonuç: doc 16 §2'nin User satırı ("Kendi + explicitly
shared + published") sadece "kendi"ye çöküyordu ve **Supervisor sorgu düzeyinde User'dan
ayrışmıyordu**. Aynı daralma dört dosyada birebir kopyalanmış
`_ensure_can_view_workspace(..., visibility="private")` yardımcısında tekrarlanıyordu — detail,
compare, metrics ve artifacts hep birlikte kayıyordu.

**Ne landed.** Yetki artık TEK yerde: `domain/backtest/result_visibility.py` (saf yüklem —
paylaşılan identity `can_view`'ini **`EXPLICITLY_SHARED`** görünürlükle çağırır; grant'leri saydıran
şey budur, `shared_principal_ids=None` fail-closed kalır) + `application/queries/result_access.py`
(DB tarafı: `share_repo.shared_resource_ids`/`active_grantee_ids` — Package paylaşımının **aynı**
repo'su; `visible_composition_stmt` = list SQL yüklemi, `ensure_can_view_composition` = satır-bazlı
yeniden kontrol, owner/Admin için hızlı yol ile eski sorgu sayısı korunur). Dört kopya yardımcı
silindi; `results_history`, `backtest_run`, `metric_profile`, `result_artifacts` tek kurala bağlandı.
`ShareResourceType.COMPOSITION = "mainboard_workspace"` (generic tablonun kendi docstring'inde tarif
ettiği uzantı noktası). **Migration YOK · ENGINE_VERSION değişmedi · route/şema değişmedi
(OpenAPI drift yok) · frontend'e dokunulmadı.**

**Supervisor ayrımı — neye dayandırıldı.** Sistemde takım/proje kapsamı diye bir şey yok; uydurmak
yerine **gerçekten modellenen tek "erişilebilir çalışma kapsamı"** kullanıldı: Analysis Lab'in
sahiplikten bağımsız olarak tam `(Admin, Supervisor)`'a açtığı **Agent research** kapsamı
(`queries/agent_workspace.py::_LAB_ROLES`, doc 18 §2). `LAB_SCOPE_ROLES` bilerek o demetin ikizi.
"Başkasının sonucu salt-okunur" ikinci kural gerektirmedi — `can_edit` her non-owner yazmayı zaten
reddediyor → `allowed_actions.soft_delete=false`.

**Dürüst sınırlar (hepsi bilinçli, PR gövdesinde de yazılı).**
1. **"Published result" V1'de YOK** — `mainboard_workspace`'te `visibility_scope` kolonu yok, hiçbir
   composition published/system olamaz; doc 16 §2'nin bu dalı **uydurulmadı**, erişilemez bırakıldı.
2. **Composition grant'ini YAZAN komut yüzeyi eklenmedi** — "yeni paylaşım mekanizması icat etme"
   kısıtı gereği yalnız OKUMA yolu bağlandı. Bugün grant ancak repo katmanından yazılabilir; bir
   composition-share komut/route slice'ı açık iş olarak duruyor.
3. **RUN kabul yüzeyi genişletilmedi** — `commands/backtest_run.py::_require_viewable_composition`
   kendi `visibility="private"` kapısını koruyor: grantee paylaşılan composition'ın sonuçlarını
   okur, orada run **başlatamaz**.
4. Yazma yolu (`soft_delete_backtest_result` → `ensure_can_edit`) dokunulmadı.

**Testler.** Yeni `tests/integration/test_results_history_visibility.py` — **12 case**: owner ·
grantee (list + detail + compare) · revoke edilen grant indeksten düşürür ·
`resource_type='package'` grant'i aynı id ile bile composition'ı **açmaz** (iki kolonlu fail-closed
kanıtı) · yabancı hiçbir şey görmez (detail/compare 403) · Admin hepsini görür · Supervisor lab
kapsamını salt-okunur görür ama başka bir insanın private sonucunu görmez · düz User lab sonuçlarını
asla görmez · Supervisor'da kapsam additive · karışık own/shared/lab kümesinde cursor yürüyüşü her
satırı tam bir kez döndürür (`has_more` yetkili kümeyi sayar). Lokal: 12/12 · ruff+format+mypy
(358 dosya) temiz · tam suite exit 0 (0 F/E, ~2242 test) · **CI 6/6 yeşil** (Backend job 30m5s).

**Takip dalgası — export kapısı (aynı finding).** İlk dalga dört okuma yüzeyini birleştirdi ama
**beşincisini atladı**: `commands/result_export.py` kendi `visibility="private"` kopyasını koruyordu.
Bu, O-14'ün kendi ürettiği bir tutarsızlıktı — grantee/Supervisor artık `allowed_actions.export=true`
diyen kartı görüyor, export komutu ise 403 veriyordu. Doc 15 §2 "Result view / export"u **tek satırda**
derecelendirdiği (Supervisor: "Erişilebilir resultları okuyabilir ve policy uygunsa export alabilir"),
doc 16 §2 ise export'u kendi tablosunda derecelendirmeyip Sayfa 15'e devrettiği için kapı
`result_access.ensure_can_view_composition`'a bağlandı, yerel yardımcı silindi. RUN kabulü
genişletilmedi. **+3 case → 15/15**; komşu suite'ler regresyonsuz (81/81); migration/route/şema yok.

**Ortam notu (tekrar teyit).** Tam suite'in İLK koşusu düzinelerce `ERROR` verdi; aynı dosyalar izole
koşuda geçti (`test_bootstrap_status.py` 4/4). CLAUDE.md'deki lock-wait tuzağı gerçek — çıktıyı
`tail -N` ile kırpma (özet satırı kaybolur), tamamını dosyaya yaz ve otoriteyi CI'a bırak.

## Next: **PO imzası + R2 kapanışı** (değişmedi) · O-14 landed (#417)

Kalan tek büyük açık iş hâlâ **R2'nin product-owner imzası**
(`docs/implementation/v18_final_acceptance.md` §4, D-1…D-9) — imza olmadan
`entropia_v18_remediation_status.md`'deki R2 RE-OPENING banner'ı kalkmaz.


---

## I-17-COV — kalan kabul-ID kapsam boşlukları gerçek testlerle kapandı (PR TBD)

**Branch:** `test/i17cov-acceptance-id-gaps` · **test-only: `src/` değişmedi, migration yok,
alembic head `0039_backtest_run_cancellation`, `ENGINE_VERSION` bump yok.**

**Ölçüm (`python3 docs/audit/acceptance_id_scan.py`):** **163/215 (%75) → 173/215 (%80)**;
kapsam içi (doc 02/03/04/05/07/10) **108/130 → 118/130**; doc 05 Trade Log **COMPLETE**.

I-17'nin `acceptance_id_map.md` §E'de bıraktığı "gerçek boşluk" listesi (etiketsiz değil, **testsiz**)
ID ID yeniden doğrulandı ve **20 yeni test / 6 yeni dosya** ile kapatıldı: PC-14, PC-19 (1. cümle),
ESP-19 (kısmi), RF-15/ESP-05, PL-06, AT-21, AT-24, TS-20/AOS-20 (domain-command yarısı), CP-05,
TS-16/TL-18/AOS-16, PC-22, CP-14. Tam tablo + kanıt: `docs/PROJECT_HISTORY.md` §I-17-COV ve
`docs/audit/acceptance_id_map.md` §H.

**Üç kusur bulundu, yamanmadı, belgelendi** (I-17'nin RF-12 deseni):
1. **PC-19 2. cümle tutmuyor** — soft-delete edilmiş ESP yeni Pre-Check'te hâlâ çözülüyor
   (`resolve_embedded_dependency` kökün `deletion_state`'ine bakmıyor; fonksiyonun kendi
   docstring'i tersini vaat ediyor) → `fix/pc19-soft-deleted-esp-must-not-resolve`.
2. **AT-21/TS-20'nin "Tool Gateway" cümlesi karşılıksız** — `ToolName`'de `strategy.*` /
   `trading_signal.*` üyesi yok → `feat/gateway-strategy-and-signal-tools`.
3. **ESP-19 export'u adapter ref + evidence taşımıyor** (manifest yalnız paket revision'ından
   kuruluyor) → `feat/esp19-export-carries-contract-facts`.

**Kalan (bu slice'ın kapsamı dışı, dürüst sınır):** `AOS-12` (kendi branch'i); kapsam içi 12 etiketsiz
ID (`AT-04/06/07`, `TS-10`, `PC-01/02/15/16/18`, `RF-13/18`) — hiçbiri §E'nin gerçek-boşluk
listesinde değildi, çoğu izlenebilirlik borcu; `RC`/`RH`/`AL`/`UM`/`FD` sayfaları (42 ID) baştan
kapsam dışı; doc 06/08/09 hâlâ ID sütunsuz.

## Next: **PO imzası + R2 kapanışı** (değişmedi) · I-17-COV landed

Kalan tek büyük açık iş hâlâ **R2'nin product-owner imzası**
(`docs/implementation/v18_final_acceptance.md` §4, D-1…D-9). Kabul-ID izlenebilirliği tarafında
sıradaki en yüksek değerli iş, yukarıdaki üç fix/feat slice'ı ve kalan 12 in-scope etiketi.

## I-07 — `human_users` OCC: şüphe adlandırma yanılgısı çıktı, migration yok (PR #499)

**Durum: PR #499 AÇIK — CI 6/6 yeşil, merge bekliyor** (self-merge kapalı). Merge edildiğinde bu
başlık "landed (PR #499)" olarak sabitlenmeli.

I-07 "soft-delete taşıyıp `row_version` taşımayan TEK asimetrik kök tablo" öncülüyle açıldı ve
migration'lı/notlu iki dallı karar istedi. **Ampirik sonuç iki dalı da geçersiz kıldı:**
`human_users` OCC'yi hem gerektiriyor hem zaten taşıyor — kolon adı `version`
(`models/identity.py:40`), `row_version` değil. Mutasyonda +1, uyuşmazlıkta 409
`USER_ROLE_VERSION_CONFLICT` (`role_assignment.py:94`), dual-token `reconcile_occ_tokens`'tan
geçiyor (`admin_panel.py:97`), row-lock + no-op + `run_idempotent` yerinde.

**`row_version` EKLENMEDİ:** (1) `version` zaten token — ikincisi aynı satırda iki bağımsız önkoşul
yaratır, O-12'nin yasağı; (2) yeniden adlandırma kırıcı — `version` tel üstünde, `adminPanel.ts:27,72`
tüketiyor; (3) farklı ad zaten konvansiyon — `registry_version` üç tabloda aynı işi yapıyor.

**Asıl kusur haritadaydı:** `DATA_MODEL.md`'nin `human_users` OCC hücresi `—` diyordu — eksik not
değil, **yanlış olgu**. `✔ version` olarak düzeltildi; OCC konvansiyonu bölümüne "token adı
`row_version` olmak zorunda değil, üç ad ailesi var, kolon adına bakıp OCC yok çıkarımı yapma"
kuralı ve **§I-07 karar kaydı** eklendi. `adminPanel.ts:362` yorumu token'ı yanlışlıkla registry
satırına atfediyordu — düzeltildi (yorum-only).

**Dürüst sınır (ayrı konu, kapsam dışı):** `human_users` soft-delete kolonları beyan edilmiş ama
**hiç yazılmıyor** — yazan komut yok, yalnız okuma kapısı (`identity.py:30`, `auth.py:364,509`).
`human_user` K-06 `TRASH_OBJECT_LOCATIONS` kataloğunda yok → kullanıcı silme özelliği yok. Katalogda
olmayan tip için trash-entry yükümlülüğü de yok, dolayısıyla tutarlı. Eklenirse dört yer birden.

**Testler:** `test_panel_management_logs.py` 26 passed · frontend tsc + eslint temiz · **CI 6/6**
(Backend 36m45s). **Backend kaynağı değişmedi → migration yok, alembic head `0041` sabit.**

**Görev metninde iki hata:** önerilen `-k "user_role_occ"` seçicisi hiçbir teste uymuyor (gerçeği
`-k "assign_role"`); ve "row_version yok → OCC yok" çıkarımı yanlış — kolon adı OCC'nin varlığına
kanıt değil.

## Next: **PO imzası + R2 kapanışı** (değişmedi) · I-07 PR #499 merge bekliyor

Kalan tek büyük açık iş hâlâ **R2'nin product-owner imzası**
(`docs/implementation/v18_final_acceptance.md` §4, D-1…D-9) — imza olmadan
`entropia_v18_remediation_status.md`'deki R2 RE-OPENING banner'ı kalkmaz.

Bu oturumda main ayrıca ilerledi: **#494 (I-03 allocation item kind allowlist)**,
**#495 (I-12 sekiz callerless sembol silindi)** — ikisi de I-07'den bağımsız, `origin/main`@`2cea1a6`.

---


---

## Shared portfolio containment — ADIM 3 landed (PR #520)

**Base `948b6fb` → commit `088e3e9` → merge `6c46c03`** · branch
`fix/portfolio-shared-mode-containment` · 2026-08-03 · **Migration YOK** (alembic head
`0043_i08_registry_strategy_fks` sabit, tek head) · **OpenAPI drift YOK** (196 operation) ·
**`ENGINE_VERSION` BİLEREK bump EDİLMEDİ** — çalışan davranış değişmedi, **çalışması
engellendi**.

Doc 13 §8.3/§8.4/§13 + §14 kabul testi 11 her timestamp'te **TEK** portfolio valuation
snapshot şart koşuyor; engine ise timestamp yerine **ITEM** üzerinde döngü kuruyordu.
**Kusur kod yazılmadan önce ampirik olarak üretildi:** kompozit eğri zaman-sıralı değil
(`01:00, 04:00, 02:00, 03:00`); sıralı fold `max_drawdown = 5000.00`, aynı dört kapanış tek
saatte `3000.00` → **%66 fazla**; `resolve_allocation_execution` **her** item'a tam havuzu
veriyor, çapraz-item durumu **yok** → havuz yalnız isimde paylaşımlı.

Gerçek unified clock **yok** → **containment**. Sapma zaten bildiriliyordu
(`portfolio_curve_sequential_not_unified_clock`) ama yine de **kanonik cevap olarak sevk
ediliyordu**; bu PR bildirimi **RETTE** çevirdi — main'in önceki ürün pozisyonunun bilinçli
tersine çevrilmesi. **Taslak HÂLÂ KAYDEDİLİR** (authoring korundu, execution engellendi).

**Mekanizma — tek kanonik kaynak, dört yüzey okuyor, hiçbiri tekrarlamıyor:**
`domain/allocation/capability.py` (`SHARED_ALLOCATION_STATUS = "future_dev"`) →
(1) `domain/allocation/rules.py::validate_allocation` → `SHARED_MODE_NOT_IN_BUILD` BLOCKER,
`field="enabled"`, lead blocker;
(2) `domain/readiness/validators.py` → `ALLOCATION_SHARED_MODE_NOT_IN_BUILD`, scope
`portfolio_allocation`, yeni `_ALLOC_REMEDIATION` tablosu (doc 14 §9.1);
(3) `commands/backtest_run.py::_admit_run_body` — **Ready Check'ten BAĞIMSIZ**, snapshot'ı
doğrudan okur, **`build_run_manifest`'ten ÖNCE** → run/manifest/job **oluşmaz** (doc 15 §9.3);
(4) `queries/allocation_plan.py` → `shared_mode_capability`, `pages/Portfolio.tsx:357`
verbatim basar (kontroller etkileşimli kalır — disabled UI sunumdur, authorization değil).

**Yeni:** `domain/allocation/capability.py` · `tests/unit/test_shared_allocation_containment.py`
(9) · `tests/integration/test_shared_allocation_containment.py` (7) ·
`frontend/src/test/legacySequentialResultLabel.test.ts` (3) ·
`docs/decisions/2026-08-03_shared_portfolio_containment.md`. **Codemap** PR içinde güncellendi
(`BACKEND_LAYERS.md`, `BACKEND_ROUTES.md`).

**Testler:** backend tam suite **exit 0 / 0 FAILED / coverage %92.43** (kapı %90) · ruff +
mypy temiz · frontend **676 passed / 66 dosya** · `tsc -b --noEmit` temiz · **CI 6/6 pass**
(Backend 37m26s · Frontend 1m58s · E2E F-23 7m02s · E2E dev-auth 2m04s · A11Y R2-14 2m39s ·
Docker 56s).

**Dürüst sınır — bilinçli kapsam kaybı (decision record §8):** admitted shared run kalmadığı
için üç davranış artık uçtan uca test edilemiyor — worker'ın pinned pool `P0` ile
kapitalizasyonu (sizing aritmetiği `test_backtest_engine_allocation.py`'de duruyor);
portfolio kurallarının DONDURULMUŞ revision'a taşınması (draft round-trip + freeze reddi test
ediliyor); RC-03'ün orijinal fixture'ı (artık `EXECUTION_ASSUMPTIONS_DEFAULT` uyarısına
taşındı, ulaşılamaz yol `test_shared_allocation_warning_path_is_now_fail_closed` ile kilitli).
**Containment kaldırılırken üçü de geri getirilmeli.** Kaldırma şartları: decision record
**§6** — altı somut madde. **"ADIM 20 unified oracle gate" bu repoda TANIMLI DEĞİL**
(`current_main_ground_truth_2026-08-03.md` §18 yalnız 1–8'i listeliyor); uydurulmadı, şartlar
bu yüzden §6'da somut yazıldı.

**Deferred:** yok — kapsam dışı kalanlar zaten ayrı kalemler (§G-03 Tool Gateway,
§G-04 Library Request-Validation UI).

## Stage post-V1 G-02 — ESP export contract v2 landed (PR #521)

**Base `6c46c03` → merge `a570934`** · 2026-08-03 · **Migration YOK** (alembic head
`0043_i08_registry_strategy_fks` sabit, tek head) · **`ENGINE_VERSION` DEĞİŞMEDİ** ·
**OpenAPI:** 1 yeni schema (`PackageExportResponse`) + 1 operation body `$ref`, **operation
sayısı 196'da sabit**.

Doc 09 §15 **ESP-19** ve doc 09 §14, export artifact'inin adapter ref + test evidence
taşımasını istiyor. Schema v1 yalnız identity/hash/dependency yarısını taşıyordu — adapter,
warm-up, timing, repaint ve evidence `embedded_resolver_contract`'ta, sertifikalayan run
`embedded_resolver_validation_run`'da yaşıyordu, manifest ise yalnız `package_revision`'dan
kuruluyordu. **Kusur kod yazılmadan önce `6c46c03` üzerinde probe ile üretildi:** satırlar
veritabanında mevcutken manifest dört alanı birden atlıyordu.

**Landed:** yeni saf düzlem `domain/package/export_contract.py`; manifest'e
`export_schema_version` · `exporter_version` · `resolver_contract_snapshot` ·
`validation_evidence_snapshot`; kanıt yoksa `legacy_incomplete_evidence` (**`passed` asla
uydurulmaz** — revision `passed` okusa bile); canlı registry manifest'in DIŞINDA, zarfın
kardeşi `registry_observation`; her iki snapshot da **export edilen revision'ın** satırlarından
(kökün head'inden asla); import v1(+açık `null`)/v2 okur, başka versiyon **iki katmanda**
fail-closed (sınırda 422, worker'da terminal `failed`); yabancı contract iddiası
`diagnostics.origin_resolver_contract` olarak `trusted: false` yankılanır ve **sıfır** yeni
contract/registry satırı yaratır; `get_latest_validation_run` sıralaması **total** yapıldı
(`created_at` = tx timestamp olduğu için aynı tx'teki iki run eşitleniyordu).

**Yeni taksonomi kodu icat EDİLMEDİ** — doc 08 okunamayan şema versiyonu için kod
adlandırmıyor, sevk edilmiş `PACKAGE_IMPORT_MANIFEST_INVALID` yeniden kullanıldı.

**Adversarial review iki fazla-iddiayı çürüttü** (ikisi de probe ile ölçüldü): yeniden
validate ve approve geçişi hash'i hareket ettiriyor. Alanlar korundu (ESP-19 gereği),
**dokümantasyon dört dosyada daraltıldı**. Doğru cümle: digest arada bir şey değişmediyse
birebir yeniden üretilir, ama revision ömrü boyunca **donmuş değildir**. Review ayrıca beş
test zayıflığı buldu (revert'te hayatta kalan determinizm testi, SHA-256'yı test eden tamper
testi, vakum `PackageRoot` sayımı, key-set assert etmeyen "only" iddiası, private fonksiyon
çağıran replay testi) — hepsi düzeltildi.

**Testler:** yeni `test_esp_export_contract_v2.py` (13) + `test_package_import_schema_v2.py`
(18, end-to-end round trip dahil); ESP-19 acceptance testi **PARTIAL → FULL**. Backend tam
suite **exit 0 / 2974 passed / coverage %92.47**; frontend **680 passed**; ruff + mypy +
OpenAPI drift temiz; **CI 6/6 pass**.

**Kapanan kayıtlar:** `docs/audit/current_main_ground_truth_2026-08-03.md` §G-02 CLOSED +
§18 sıra 3 LANDED; `docs/audit/acceptance_id_map.md` ESP-19 + §E.4 CLOSED. Yeni sözleşme
dokümanı: **`docs/audit/esp_export_schema_v2.md`** (v1/v2 matrisi + şema + determinizm kanıtı).

**Deferred (bilerek):** hiçbir şey bu slice'tan ertelenmedi. Kapsam dışı kalanlar zaten
ayrı kalemler: §G-03 Tool Gateway `strategy.*`/`trading_signal.*`, §G-04 Library
Request-Validation UI.

## ADIM 8 — Yüksek riskli API sözleşmeleri typed (PR #529)

**Base `870cc1a` → commit `62705ec` → merge `8a87460`** · 2026-08-04 · **Migration YOK**
(alembic head `0043_i08_registry_strategy_fks` sabit, tek head) · **`ENGINE_VERSION`
DEĞİŞMEDİ** · **OpenAPI: 30 yeni schema, 0 kaldırılan, operation sayısı 196'da sabit.**

> **Handoff boşluğu (dürüst kayıt):** ADIM 5 (#525), ADIM 6 (#526) ve ADIM 7 (#527) bu
> belgeye girdi yazılmadan merge edildi. Bu girdi yalnız ADIM 8'i kapsar — o üç slice'ın
> ayrıntısını geriye dönük uydurmuyorum; kayıtları PR'larında. Ayrıca **PR #528**
> (`fix/agent-tools-trade-log-handoff`, `30ff98f`) ADIM 8'in base'i ile merge'i arasına
> girdi — bir sonraki slice base olarak `8a87460` almalı, `870cc1a` değil.

ADIM 2–7 ile değişen 16 public 2xx gövdesi `dict[str, Any]` dönüyordu: gövde
`docs/openapi.json`'dan **görünmez** kalırken drift guard yeşildi — O-30'un purge 202,
G-02'nin package export için kapattığı **aynı tuzak**.

**Landed:** yeni `apps/api/schemas/` paketi (`common`/`esp`/`library`/`agent_tool_gateway`),
16 uçta `response_model`. **Wire byte'ları değişmedi.** Handler'lar `dict[str, Any]` dönmeye
devam ediyor (sevk edilmiş kalıp), böylece serileştirmeden ÖNCE çalışan route-içi
subscript'ler korunuyor (iki ETag + broker devri). `PackageExportResponse` ve
`PackageValidationRunAcceptedResponse` **aynı sınıf adlarıyla** taşındı → component anahtarı
kaymadı.

**Üç kural:** her alan REQUIRED, nullability TİPTE (`= None` default'u asla atlanmayan bir
anahtarı atlanabilir gösterir); enum'lar `string` (RESPONSE'ta kapalı enum, sunucunun meşru
ürettiği değeri `response_model` çıkış doğrulamasında **500**'e çevirir); zaman damgaları
`string` (serializer zaten `.isoformat()` basıyor). Son ikisi el listesiyle değil, 2xx
gövdesinden erişilebilen HER component üzerinde **blanket walk** ile sınanıyor.

**Bilerek açık:** export `manifest` (sürümlü artifact, `POST /package-imports`'a aynen geri
gider), JSONB sözleşmeler, gateway `request`/`response_ref` (33 tool üzerinde `tool_name` ile
ayrışır, Strategy/Trading Signal parity sonuçlarını aynen taşır). **Gateway ZARFI tam tipli.**
**Enqueue'nun HTTP yüzeyi yok** — worker düzlemi.

**Landing'i engelleyen kusur düzeltildi:** `POST /package-imports` çağıranın manifest'ini
JSONB `rationale_family_snapshot`'a yalnız kap-seviyesi kapıyla yazıyor;
`_pinned_family`/`_live_family` id'yi çıplak truthiness ile eliyordu →
`{"rationale_family_id": 7}` tipli sözleşmede **tüm `GET /library` sayfasını 500** yapardı.
İkisi de artık serializer'da eleniyor (`_package_name` emsali). Geçerli veri birebir aynı.

**Frontend parity makine kontrollü** (`test_wire_contract_parity.py`, 27 çift) ve **dört
sapma** buldu: `EspPackageDetail` `latest_validation_run`'ı hiç bildirmemiş (R8'den beri
gönderiliyor); iki `lifecycle_state` TS'te nullable kolondan dar; `ProvenanceScan`'in iki
alanı NOT NULL kolondan geniş. `lifecycleTone` artık `string | null` alıyor,
`UNSTATED_LIFECYCLE_LABEL` ile düşüyor — asla uydurma `"active"`.

**Testler:** 4 yeni modül (17 + 11 + 27 çift + 16). Integration modülü HTTP gövdesini **saklı
idempotency zarfıyla** karşılaştırıyor — `run_idempotent` komutun dönüşünü aynen sakladığı
için bu, `response_model` **öncesi** dict ile sonrası demektir; tek karşılaştırma hem drop'u
hem replay-parity'yi kanıtlar. İki eski contract stub'ı (`test_library_contract.py`) gerçek
projeksiyona hizalandı. Backend **3143 passed / coverage %92.81 / exit 0**; frontend **696
passed**; ruff + mypy + OpenAPI drift temiz; **CI 6/6 pass** (Backend 44m18s).

**Yeni doküman:** `docs/audit/high_risk_api_contract_audit.md` (18 uçluk denetim tablosu,
OpenAPI before/after, uyumluluk matrisi, kalan risk). Güncellendi: `BACKEND_ROUTES.md`,
`FRONTEND_MAP.md`.

**Deferred (bilerek):** `GET /library-shared-with-me` birebir aynı `LibraryPage` zarfını
döndürüyor, hâlâ tipsiz — `LibraryPageResponse` onun için aynen kullanılabilir. API'nin
geri kalanındaki ~161 `dict[str, Any]` route dönüşü dokunulmadı.

## ADIM 11 — Capability matrix canonical adjudication landed (PR #538)

**Merged** 2026-08-04T12:35Z, base `53c28de` → `main` `061d6d7`, **CI 6/6 pass**.
**Audit-only:** tek yeni dosya `docs/audit/capability_matrix_canonical_adjudication.md`
(+443). Migration YOK · OpenAPI YOK · codemap YOK · `ENGINE_VERSION` değişmedi
(`backtest-engine-v18-same-candle-entry-exit`) · alembic head `0043_i08_registry_strategy_fks`
(tek head) · `CAPABILITY_MATRIX` ve her status literal'i dokunulmadı.

Matrisin 22 `future_dev` satırı hükme bağlandı: `canonical_gap` 16 ·
`product_decision_required` 3 · `keep_future_dev` 2 · `eligible_for_implementation` 1 ·
`incorrect_current_status` **0**. **Hiçbir capability aktif edilmedi.**

Testler: backend targeted **271 passed** + allocation **18 passed** + frontend **14 passed**,
hepsi exit 0; capability generator temp path'e yeniden üretilip diff'lendi → **byte-identical**.
Tam suite koşulmadı (PR hiç kod değiştirmiyor).

En ağır bulgu **D-1 (CRITICAL)**: 22 `future_dev` satırının **11'i** Strategy formunda hiç
devre dışı bırakılmıyor — `StrategyGraphForm.tsx` generated matrix'i hiç import etmiyor.
Sunucu run'ı yine reddediyor (yetkilendirme açığı değil, **açıklama açığı**), ama bu #533'ün
tam tersi yönü ve 5 kat fazla satır. Ayrıca **D-9**: `signal_strength_adjustment`'ın dört
literal'inden üçü — sevk edilmiş **aktif** `volatility_adjusted` dahil — hiçbir kanonik
belgede yok. **D-10**: `correlation_filter` şemada var kanonda yok, `regime_filter` tersi.

Açılan issue'lar: **#539** (C-1 CRITICAL) · #540 · #541 · **#542/#543/#544/#545/#546**
(ürün kararları) · #547 (C-5) · #534'e 6 alanlık provenance yorumu eklendi.

Ayrıntı: `docs/PROJECT_HISTORY.md` §ADIM 11 · `docs/ADIM11_LANDED_KICKOFF.md`.

**Kayıt boşluğu (dürüst not):** ADIM 9 (PR #531) ve ADIM 10 (PR #537) `main`'e indi ama
PROJECT_HISTORY'ye yazılmamıştı; ADIM 11 kapanışında yalnız **işaretçi** eklendi, geriye
dönük anlatı üretilmedi. ADIM 10'un tam kaydı kendi dokümanında:
`docs/audit/strategy_conflict_matrix_closure.md`.

---

## ADIM 12 — Bağımsız finansal oracle baseline'ı (PR #553)

**Base `061d6d7` → commit `b5c7c44`** · 2026-08-04 · **Migration YOK** (alembic head
`0043_i08_registry_strategy_fks` sabit) · **OpenAPI değişmedi** (196 operation / 151 schema) ·
**`ENGINE_VERSION` DEĞİŞMEDİ** · **production kod DEĞİŞMEDİ** — slice tamamen additive.

`backend/tests/unit/oracles/` — **79 senaryo** (78 passing, 1 `xfail(strict)`). Her beklenen
değer kanonik kuraldan **elle** hesaplanıp literal yazıldı; pakette hiçbir engine aritmetik
helper'ı (`_effective_fill`, `_position_size`, `_resolve_stop`, `due_funding_charges`) import
EDİLMİYOR — tek production import `run_engine` ve tükettiği tipli girdiler. Fixture'lar 5–20
bar, yani ledger'ın tamamı elle denetlenebilir. Golden digest'ler yerinde ve yeşil; oracle'lar
onların yerine GEÇMEZ.

**Amaç:** unified-clock değişikliğinden önce mevcut single-item engine davranışını, engine'in
kendi helper'larından bağımsız bir ölçüyle sabitlemek.

**Dört uyuşmazlık bulundu, hiçbiri düzeltilmedi** (her biri engine semantiğini değiştirir →
`ENGINE_VERSION` kararı + golden digest tazelemesi gerekir):

| # | ağırlık | özet |
|---|---|---|
| #549 | high | gap'le atlanan koruma stop'u hâlâ ulaşılamayan seviyeden kayıt açıyor (bar 88–92, stop 100.98 → −51.00 yerine −600.00); engine stop **girişinde** `max(trigger, open)` uyguluyor, koruyucu çıkışta uygulamıyor. `xfail(strict)` olarak repo'da. |
| #550 | high / ürün | `base_position_size` birim adedi olarak yürütülüyor; canon + V18 formunun `%` eki "resolved capital yüzdesi" diyor |
| #551 | medium | `min > max` size penceresi 0-size hayalet trade açıyor |
| #552 | medium | kısmi kapatılan pozisyon 1.4 komisyon round-trip ödüyor |

**Doğrulama:** hedefli 78 passed + 1 xfailed · full backend suite **exit 0**, 0 FAILED/ERROR,
coverage **%92.84** · `ruff` + `ruff format` + `mypy src` temiz (yeni paket mypy-strict temiz).

**Doküman:** `docs/audit/backtest_oracle_fixtures.md` — tüm el hesapları + spec'in
**sessiz/açık** bıraktığı ve oracle'ların "sevk edilmiş konvansiyon" diye pinlediği alanların
listesi (fill fiyatı, maliyet işareti/sırası, gap, tetiklenen stop'un icra fiyatı, varsayılan
stop önceliği, Kelly, min position size — hiçbiri master reference'ta sabitlenmemiş).

---

## ADIM 13 — Research Data point-in-time ve Agent/Run parity (PR #560)

**Base `c610600` → commit `4110138`** · 2026-08-04 · **Migration YOK** (alembic head
`0043_i08_registry_strategy_fks` sabit) · **OpenAPI değişmedi** · **`ENGINE_VERSION`
ADIM 13 tarafından değiştirilmedi** · **capability matrix dokunulmadı** · **frontend HİÇ
dokunulmadı** (DTO / route / react-query key / OCC token / Idempotency-Key).

**Soru:** bir Research Data revizyonu Agent research bundle'ına, Backtest execution
bundle'ına taşıdığı **aynı canonical point-in-time doğruluğunu** taşıyor mu? Dört ayrı kod
parçası bir revizyonu pinleyebiliyor, o yüzden parity **varsayılmadı, kanıtlandı**:

| | yüzey | giriş noktası |
|---|---|---|
| A1 | Agent tool gateway | `jobs/agent_tools.py::_handle_data_bundle_resolve` |
| A2 | Agent bundle derleyici | `jobs/research_data.py::compile_agent_data_bundle` |
| B1 | Evidence bundle derleyici | `jobs/research_data.py::compile_backtest_evidence_bundle` |
| B2 | Run manifest | `commands/backtest_run_context.py::_research_entries` |

**40 yeni senaryo** (27 saf + 13 DB-destekli) anlaşmaları kilitliyor; **4 `xfail(strict)`**
kodun canon'la çeliştiği yeri canon'un ifadesiyle yazıyor. Her kusur, yazılmadan ÖNCE
`c610600` üzerinde gerçek veritabanına karşı **yeniden üretildi**.

**Dar üretim düzeltmesi (tek kalem, ortak time-policy katmanı).** `set_time_policy` yalnız
sahipliği (`ensure_can_edit_draft`) kontrol ediyordu, revizyon **durumunu** değil. APPROVED
bir revizyonun available-time kuralı yerinde yeniden yazılabiliyordu; `content_hash` yalnız
payload byte'larını kapsıyor ve `queries/funding.py` bu alanları **canlı** okuyor → aynı
revizyonu pinleyen iki koşu farklı `available_at` çözüp farklı funding maliyeti
kitaplayabiliyordu, manifest snapshot'ı aynı görünürken. Ampirik probe (düzeltme öncesi):
`state=approved · before=(None,None) · after=(fixed_delay,7200) · content_hash DEĞİŞMEDİ`.
Doc 12 §11/§14 bunu yasaklıyor. Artık `domain/research_data/time_policy.py` içinde
`TIME_POLICY_FROZEN_STATES` + `time_policy_is_frozen` + `ensure_time_policy_mutable` →
**409 `LIFECYCLE_BLOCKED`** (`field_path=available_time_policy`,
`suggested_action=create_new_revision`, `retryable=false`; okunamayan durum fail-closed
FROZEN). Tek çağrı, `run_idempotent` gövdesinin **içinde** (2a dersi). Kurtarma yolu zaten
vardı ve değişmedi: `create_research_dataset_revision` yeni DRAFT açıp head'i ilerletiyor.

**Yeni kapsam (öncesinde eşdeğeri yoktu):** mikrosaniye as-of sınırı (önceki kapsam saniyede
duruyordu) · aynı `available_at`'li iki kayıt ikisi de birer kez ateşler (sessiz dedupe yok)
· geç varış replay'de de uygun değil · non-UTC kaynak zaman dilimi `build_funding_schedule`
üzerinden (tüm önceki funding testleri `ZoneInfo("UTC")` geçiyordu) · DST fold/gap
**karakterize** edildi · ingest normalizer ile funding reader her DST vakasında aynı cevabı
veriyor · `feature_input_only` + onaylı tanım **pozitif** yolu · historical correction pinli
revizyonu ve yeniden derlenen `bundle_hash`'i byte-identical bırakıyor.

**Dört uyuşmazlık açıldı, hiçbiri düzeltilmedi** (hepsi ortak time-policy katmanının dışında;
her biri `xfail(strict)` — düzeltildikleri gün test kırmızıya döner, sessizce yeşile kaymaz):

| # | özet |
|---|---|
| #556 | `data_bundle.resolve` **hiç** lifecycle durumu okumuyor — soft-deleted root ve deprecated/revoked revizyon pinleniyor; ikizi ikisini de blokluyor. Aynı handler'da market yarısı "approved" iddia eden docstring'ine rağmen yalnız varlık kontrolü yapıyor. |
| #557 | `data_bundle.resolve` Feature-Input-Only kapısını **çağıranın gönderdiği** boolean'dan karara bağlıyor; ikizi gerçek `SELECT` ile çözüyor. Engine bu pini çalıştırmadığı için CRITICAL değil. |
| #558 | Hiçbir bundle üyesi doc 12 §9.1/§9.2'nin adını verdiği available-time policy'yi pinlemiyor → `bundle_hash` politika değişimine karşı **değişmez**. Run manifest pinliyor; iki execution-evidence yüzeyi çelişiyor. |
| #559 | DST fold/gap için canon kural **yok**; ikisi de sessizce çözülüyor ve katlanan saatin **ikinci oluşumu kaynak dosyadan adreslenemiyor** (`fold=0`). |

**Doğrulama:** hedefli 40 passed + 4 xfailed · full backend suite **exit 0**, coverage
**%92.89** (kapı ≥90) · `ruff` + `ruff format` + `mypy src` (385 dosya) temiz · **CI 6/6 pass**
(Backend job 46m01s).

**Doküman:** `docs/audit/research_point_in_time_matrix.md` — tüketim yolu haritası, zaman
sözlüğünün ne olup ne olmadığı, T/S/L/P kanıt matrisi ve dürüst sınırlar.

**Paralel landed (ADIM 13'ün işi DEĞİL):** PR #555 `fix(engine): fill a gapped protection
stop at the bar open, not at the level` → **#549 CLOSED** ve **`ENGINE_VERSION` artık
`backtest-engine-v18-gap-adjusted-stop-fill`** (önceki `…-same-candle-entry-exit`). ADIM
12'nin oracle `xfail`'i kalktı; suite'teki tek xfail dosyası artık ADIM 13'ünki.

**Frontend takip notu (issue açılmadı):** `ResearchLifecycle.tsx` onaylı bir revizyon için
time-policy formunu hâlâ sunabiliyor ve artık 409 alacak; zarf `remediation` +
`suggested_action` taşıdığı için kurtarma açıklanıyor, ama UI kontrolü ön-devre dışı
bırakmıyor.

---

## Eski Next (ADIM 13 kapanışında yazıldı — **etiketi F-26 oldu, slice LANDED**)

> Bu blok slice'ı yazıldığı gün **"ADIM 14"** diye etiketliyordu; ama `origin/main`'e daha
> önce inen **PR #563** (ADR 0002) kendini ADIM 14 sayıyor ve **ADIM 15–20**'yi unified-clock
> programına rezerve ediyor. **Çakışma karara bağlandı: frontend slice'ının etiketi `F-26`.**
> Gerekçe: iş saf frontend sunum işi (F-serisi tam olarak bu; F-01…F-25 dolu) ve ADIM 15–20
> rezerve olduğu için ADIM serisinden numara harcanmamalı. Slice bu etiketle **PR #564'te
> landed** — aşağıdaki analiz artık **kapanmış işin ön-tanısıdır**, sıradaki iş değil; sonucu
> için `## F-26 — Strategy formu capability disclosure landed (PR #564)` kaydına bak.

### F-26 (yazıldığındaki etiket: ~~ADIM 14~~) — Strategy formu capability disclosure (#539 + #533 TEK slice)

İki issue **aynı mekanizmanın iki zıt yönde kusuru**; ayrı düzeltmek diğerini üretir.
Backend tarafı **doğru ve testli** — kusur yalnız UI iddiasında. İkisi de güncel `main`
(`f4e2fd3`) üzerinde yeniden doğrulandı.

* **#539 — yanlış-NEGATİF.** `StrategyGraphForm` üretilen capability aynasını **hiç** import
  etmiyor (`grep -c capabilityField`: ConfigForm 12, GraphForm **0**), kendi `SelectField`'ini
  taşıyor. 22 `future_dev` satırından **15'i** sıradan seçilebilir opsiyon gibi görünüyor
  (`scaling_logic.timeframe` 10 · `timeframe_mode=increasing_by_layer` 1 ·
  `restrictions_filters.filters.filter_type` 4 → **10+1+4 = 15**; bağlı 9 ConfigForm alanının
  `future_dev` toplamı 7, 22−7 = 15). **Issue #539'un başlığındaki "11" yanlış** — kendi
  tablosuyla çelişiyor; aynı hatalı rakam yukarıdaki **ADIM 11 tarihsel kaydında** da duruyor
  ve bilerek düzeltilmedi. Kabul ölçütünü **15** üzerinden ölç. Kullanıcı gerçeği ancak stratejiyi
  kurduktan **sonra** Ready Check'te öğreniyor. Yetki açığı değil — sunucu koşuyu
  reddediyor; **disclosure** kusuru, hata yönü güvensiz.
* **#533 — yanlış-POZİTİF.** Sevk edilen varsayılanlarla form "Ready Check blocks it" diyor;
  Ready Check bloklamıyor. `exit_on_opposite_signal` AÇIKKEN kaydedilmiş `allow_hedge`
  **inert**tir ve backend üçlü paritesi (`engine.py:573-576`, `capabilities.py:638-645`,
  `validators.py:644-655`) bunu doğru işliyor. Frontend notu yalnız **değere** bakıyor.

**Tuzak:** #539'un naif düzeltmesi (değere bakıp kapıla) tam olarak #533'ü çoğaltır. Backend
okuyucular değere değil **erişilebilirliğe** bakıyor (`scaling.enabled`, `filter.enabled`,
`exit_on_opposite_signal`). Ortak çözüm: `SelectField`'e "bu `future_dev` değer şu an inert,
çünkü …" predicate'ini **çağıran kart** sağlar.

**Test boşluğu (doğrulandı):** `engineCapabilityMatrix.test.tsx` yalnız `DataExecutionCard`
ve `PositionSizingCard` render ediyor — `ConflictCard` ve `StrategyGraphForm` hiçbir
capability testinde yok.

**Sınır:** yalnız sunum. `capabilities.py`, `_read_opposite_hedge`, `CAPABILITY_MATRIX`
satırları, `engineCapabilityMatrix.generated.ts` (üretilmiş — backend parity testi byte byte
pinliyor), readiness validator ve `opposite_direction_hedge`'in sevk edilen varsayılan değeri
(ayrı ürün kararı, F-4) **dokunulmaz**.

Tam reçete, kabul ölçütleri ve önce-üret adımları: `docs/ADIM13_LANDED_KICKOFF.md`.

**Sıraya girmeyen açık kalemler:** #550/#551/#552 (ADIM 12 engine uyuşmazlıkları) ·
#556/#557 (agent gateway parity — doğal çözüm iki yüzeyi TEK resolver'a bağlamak) ·
#558/#559 (ürün kararı bekliyor) · #514 (ekran okuyucu denetimi; kapatma yetkisi insanda).

---

## ADIM 14 — Unified-clock portfolio ADR landed (PR #563)

**Base `f4e2fd3` → commit `992ac9d` → merge `fb57cc8`** (2026-08-04T18:27:28Z) · **docs-only**
· **Migration YOK** (alembic head `0043_i08_registry_strategy_fks`, tek head) · **OpenAPI
DEĞİŞMEDİ** (196 operation / 151 schema) · **`ENGINE_VERSION` DEĞİŞMEDİ** · **production kod
DEĞİŞMEDİ** — iki dosya: `docs/adr/0002-unified-clock-portfolio-simulation.md` (**761 satır**)
ve `docs/adr/README.md` indeks satırı.

**ADR statüsü: `Proposed`.** PO / maintainer onayı bekliyor — **`Accepted` DEĞİL.** §16 açık:
onay gelmeden ADIM 15 başlamaz. Bu belge tasarımın **inşa edildiğinin** kanıtı değildir.

**Ne kararlaştırdı:** Shared Equity Allocation (doc 13 / Modül 11) için icra modeli — dış
döngü item listesi değil **birleştirilmiş zaman ekseni** olur; tek `PortfolioLedger` `P0`/`R0`/`U0`
tutar; tick başına **tek** `E(t)` yayımlanır ve her item `Ci(t)`'yi ona karşı hesaplar. Blast
radius'u sınırlayan invariant: **tek-item yolu bit-aynı kalır** — `run_engine` imzasını *ve
semantiğini* korur, 46 golden digest'in 37'si kımıldamaz, yalnız 9 `portfolio.*` senaryosu hareket eder.

**Üç dondurulmuş çıktı** (bir sonraki oturumun sözleşmesi):

| Bölüm | İçerik |
|---|---|
| **§12** | **ADIM 15–20 sınırları** — her adım tek branch/tek PR/bağımsız revert; 20 dışında hiçbiri containment'ı kaldırmaz. Ayrıca ADIM 15–20'ye **dahil olmayan** önkoşullar: #559, #544, R-1, OD-1…OD-6. |
| **§13** | **Yedi açık karar OD-1…OD-7** — kanonun sessiz olduğu yerler; her biri seçenek + öneri taşıyor, **kararı insan verir**. |
| **§14** | **A1–A22 kabul matrisi** — containment lift'in kapısı; her satır kaynak + gerekli kanıt ile. |

**ADR'ın kendi bulduğu iki kalem (ikisi de düzeltilmedi, bilerek):**

* **R-1 (§10.2)** — `readiness_check.py::_resolve_allocation` (`:805-838`) kendini "revision
  config'ini pinler" diye belgeliyor ama **koşulsuz canlı draft satırlarından** kuruyor ve
  `plan_revision_id`'yi çıplak pointer olarak yazıyor; pinlenen config'in o revision satırıyla
  eşleştiğini hiçbir şey doğrulamıyor. **ADIM 20'den önce, ayrı dar PR.**
* **§10.1** — shared-mode manifest'inde kanonun istediği **resolved sleeve amounts**, **FX refs**
  ve **`engine_allocation_policy_version`** yok. Bugün zararsız (shared mode contained), ADIM
  20'den önce kapanmalı.

**Doğrulama — dürüst sınır:** **test suite KOŞULMADI.** Çalıştırılabilir hiçbir şey değişmedi;
docs-only bir slice'a eski bir koşunun sayısını etiketlemek yanıltıcı olurdu. **Codemap
tazelenmedi — gerekmiyor:** yeni endpoint / tablo / sayfa / job yok.

**Sıra notu (dürüst kayıt):** ADR (#563) `origin/main`'e **ADIM 13'ün kapanış kaydından
(#562, merge `801791f`) ÖNCE** indi; bu kapanış onun üzerine rebase edildi. Bu yüzden belgede
sıra kronolojiktir ama bir süre **numaralandırma çakıştı**: #562'nin "Next"i ADIM 14'ü
*frontend capability disclosure (#539 + #533)* sanıyordu, merge edilmiş ADR ise kendini ADIM 14
sayıp **ADIM 15–20'yi unified-clock'a rezerve ediyordu**. **Karara bağlandı (2026-08-04):
ADIM 14 = ADR; frontend slice'ının etiketi `F-26`.** ADR immutable olduğu ve F-serisi tam
olarak saf frontend sunum işini adlandırdığı için taşınan taraf slice oldu; ADIM 15–20 rezerve
kaldığından ADIM serisinden numara harcanmadı. Yukarıdaki "Eski Next" bloğu bu yüzden artık
F-26 başlığını taşıyor — iş geçerliydi, yalnız etiketi geçersizdi ve o slice **PR #564 ile
landed**.

**Doküman:** `docs/adr/0002-unified-clock-portfolio-simulation.md` (tam tasarım) ·
`docs/ADIM14_LANDED_KICKOFF.md` (reuse anchor'ları + resume prompt) ·
`docs/PROJECT_HISTORY.md` §ADIM 14.

---

## F-26 — Strategy formu capability disclosure landed (PR #564)

**Base `b8d62e2`'nin ebeveyni → commit `5887f3f` → merge `b8d62e2`** (2026-08-04T19:32:36Z) ·
branch `fix/strategy-form-capability-disclosure` · **frontend-only** · **Migration YOK**
(alembic head `0043_i08_registry_strategy_fks`) · **OpenAPI DEĞİŞMEDİ** · **`ENGINE_VERSION`
DEĞİŞMEDİ** · **backend byte-identical**.

> **Etiket:** bu slice ADIM 13 kapanışında "ADIM 14" diye planlanmıştı; o numara merge edilmiş
> ADR 0002'ye ait olduğu için **F-26** olarak yeniden etiketlendi (yukarıdaki "Eski Next"
> bloğu ve `docs/ADIM13_LANDED_KICKOFF.md` aynı etiketi taşır).

**Ne düzeltti — iki zıt kusur, TEK kural.** Her ikisinin de kökü aynıydı: form kararını
opsiyonun **DEĞERİNE** bakarak veriyordu, backend okuyucuları ise motorun alanı **okuyup
okumadığına** bakıyor.

* **#539 (yanlış-NEGATİF)** — `StrategyGraphForm` üretilen capability aynasını hiç import
  etmiyordu ve kendi `SelectField`'ini taşıyordu; matrisin 22 `future_dev` satırından **15'i**
  sıradan seçilebilir opsiyon gibi render ediliyordu (`scaling_logic.timeframe` 10 ·
  `timeframe_mode` 1 · `filters.filter_type` 4). Kullanıcı gerçeği ancak stratejiyi kurduktan
  sonra Ready Check'te öğreniyordu. **Yetki açığı değil** (sunucu koşuyu reddediyor, motor
  pozisyon açmıyor) ama hata yönü güvensiz.
* **#533 (yanlış-POZİTİF)** — not, her yeni stratejinin **sevk edilen varsayılanında**
  `allow_hedge` için "Ready Check blocks it" diyordu. `exit_on_opposite_signal` AÇIKKEN pozisyon
  hedge dalına erişilmeden kapanır; değer **inert**tir ve `_read_opposite_hedge` doğru şekilde
  "seçim yok" raporlar.

**Çözüm biçimi:** #539'u değere bakarak kapılamak tam olarak #533'ü çoğaltırdı, bu yüzden ikisi
tek kuralla ve **her forma kopyalanmak yerine tek yeni modülde** çözüldü — yeni
`frontend/src/components/capabilityDisclosure.ts` + `CapabilityNote.tsx`. Çağıran kart alanın
**erişilebilirliğini** (`scaling.enabled`, `filter.enabled`) ya da bir **inert gerekçesini**
(`exit_on_opposite_signal`) sağlar; erişilemez alan ne disable edilir ne de not alır (backend'in
alanı atlayan okuyucusunu aynalar), inert alan da hiçbir şeyi disable etmez. **Zaten kaydedilmiş
değer seçilebilir kalır** sözleşmesi değişmedi.

**Yan kazanç (D-6):** `MODELLED_FILTER_TYPES` elle bakımlı 3 elemanlı bir motor allow-list
kopyasıydı ve parite testi yoktu; artık **matristen türetiliyor** ve bir testle pinleniyor.
Uyarısı ayrıca **disabled bir filtre satırında** da ateşleniyordu — kaydedilen revizyondan
düşen bir satır için blocker iddia ediyordu; o da düzeldi.

**Regresyon kapısı:** yeni exhaustiveness guard **12 bağlı alan yolunu** kaydediyor ve
kaydedilmemiş bir alanda `future_dev` satırı belirirse **kırılıyor**. Bu, bugün sıfır
`future_dev` taşıyan ama bağlı olmayan `scaling_logic.method` ile
`position_exit_logic.partial_aftermath`'i de kapsıyor — matris yeniden üretilirse #539
sessizce geri gelemez.

**Dosyalar (6 dosya, +412/−49):** `components/capabilityDisclosure.ts` (**yeni**) ·
`components/CapabilityNote.tsx` (**yeni**) · `components/StrategyConfigForm.tsx` ·
`components/StrategyGraphForm.tsx` · `lib/strategyGraph.ts` ·
`test/capabilityDisclosure.test.tsx` (**yeni**).

**Sınır — dokunulmayanlar:** route path / react-query key / OCC token / Idempotency-Key /
hooks / SSE taksonomisi / API çağrısı / `lib/*.ts` veri mantığı **yok**; `CAPABILITY_MATRIX`,
üretilmiş `engineCapabilityMatrix.generated.ts`, readiness validator ve
`opposite_direction_hedge`'in **sevk edilen varsayılan değeri** (ayrı ürün kararı, F-4)
**dokunulmadı**. Sunum işi.

**Doğrulama:** düzeltmeden **önce** üç kusuru da assert eden bir render probe'u yazıldı,
**sonra** aynı assertion'lar düştü. **CI PR #564'te 6/6 SUCCESS** (Backend lint/type/test ·
Frontend lint/typecheck/build/test · E2E ×2 · A11Y axe-core · Docker build).
**Dürüst sınır:** bu kapanış belgesi docs-only bir slice'tır ve **suite'i yeniden ölçmedi** —
yukarıdaki tek doğrulama kanıtı #564'ün CI koşusudur; CLAUDE.md'deki test sayıları hâlâ ADIM
13'ün ölçümüdür.

**Açık kalan:** **#539 ve #533 issue'ları hâlâ AÇIK** — düzeltme merge edildi, ama issue kapatma
yetkisi insandadır (agent kapatmaz). **#540** (exhaustiveness guard'ın kendi issue'su) bilerek
kapsam dışında bırakıldı; bu slice'ın guard'ı 12 bağlı alanı kapsıyor, #540'ın istediği tam
14 alanlık kapsam değil.

---

## ADIM 15 — Merged-axis valuation clock landed (PR #567)

**Commit `4b06f0c`-serisi → merge `ef11dc9`** (2026-08-04T20:06:44Z) · branch
`feat/portfolio-unified-clock-core` · **+864 / −1, 3 dosya** · **Migration YOK** (alembic head
`0043_i08_registry_strategy_fks`) · **OpenAPI DEĞİŞMEDİ** · **`ENGINE_VERSION` DEĞİŞMEDİ**
(`backtest-engine-v18-gap-adjusted-stop-fill`) · **CI 6/6 SUCCESS**.

| dosya | |
|---|---|
| `backend/src/entropia/domain/backtest/execution/clock.py` | **yeni**, 300 satır |
| `backend/tests/unit/test_backtest_unified_clock.py` | **yeni**, 563 satır / **27 test** |
| `docs/CODEMAPS/BACKEND_LAYERS.md` | `backtest` satırına `execution/clock.py` paragrafı |

**Ne getirdi — ADR 0002 §12'nin ADIM 15'i, fazlası değil.** Kanon portföy motorunun **DIŞ
döngüsünün** öğe listesi değil, tüm aktif öğeler üzerindeki birleşik zaman damgası ekseni
olmasını istiyor (doc 13 §8.3 · Modül 11 §5.2 · Modül 12 §9.2). Sevk edilen worker
(`application/jobs/backtest_engine.py:298`) öğeler üzerinde dönüp bitmiş run'ları pin sırasında
katlıyor — composite eğrinin **zaman serisi bile olmamasının** sebebi bu; mevcut
`test_composite_portfolio_curve_is_not_time_ordered` kusuru bilerek pinliyor (aynı dört
kapanışın unified-clock replay'i 3000.00 verirken 5000.00 raporlanıyor).

**Modülün sözleşmeleri (tercih değil, kural):**

* **Tick anahtarı `t_ms`** — UTC epoch ms (ADR §4.1), kod tabanının öğeler arasında zaten
  kullandığı anahtar. String timestamp'ler karışık offset biçimleri girince yalnız **kazara**
  sıralıdır; `…T02:00:00+01:00` ile `…T01:00:00Z` **tek tick**'e düşmeli — burada düşüyor,
  string sort'ta düşmezdi.
* **Tick bir değerleme noktasıdır, asla bir (item, zaman) çifti değil** (§4.1). Öğeler tick'in
  **içinde** yaşıyor; böylece "t anında her öğe aynı snapshot'ı görür" yapısal bir gerçek olur,
  sonraki bir gözden geçirenin yeniden doğrulaması gereken bir disiplin değil.
* **Dedup EKSENİN'dir, öğe verisinin ASLA değil.** Bir öğenin pinli akışı aynı anda iki bar
  taşıyorsa **ikisi de** o öğenin görünümünde yüzeye çıkar (`bars` bir tuple) ve eksen bir kez
  ilerler. Katlamak kanonun vermediği bir merge kuralı gerektirirdi; birini düşürmek pinli
  veriyi sessizce atardı.
* **Bar timestamp == karar zamanı** (§4.3, adjudication A-1) — sevk edilen konvansiyon korundu,
  `record_time_basis` üzerinden dallanma **YOK**; o **OD-1**'dir ve aynı digest tazelemesine
  ikinci bir anlamsal değişiklik sokardı.
* **Fail closed, asla atlama.** Yerleştirilemeyen timestamp → `UnplaceableBarTimestampError`,
  geriye giden akış → `NonMonotonicBarStreamError`, mükerrer `item_id` →
  `DuplicateItemStreamError`. Üçü de `ClockAxisError(ValueError)` altında; worker bunları
  `engine.UnresolvedStrategyError` gibi başarısız run'a çevirir (§11 / Modül 12 §9).
* **Streaming.** Mevcut chunked bar iterator'ları üzerinde k-way heap merge; öğe başına en fazla
  **bir bar** tutuluyor. Materialize-then-sort kabul edilemez (§11) ve kaynak generator'lardan
  çekilen satırları **sayan** bir testle pinlenmiş.
* **Duvar saati yok, rastgelelik yok** — eksen pinli girdilerinin saf fonksiyonu.

**Public yüzey:** `ItemBarStream(item_id, pin_ordinal, batches)` · `ItemTickView` (`bars`,
`last_closed`, `last_closed_t_ms`, `is_decision`, `staleness_ms`) · `ClockTick` (`t_ms`,
`views`, `deciding`, `view_for`) · `iter_ticks()` · `tick_key()` · `timeline_identity()` ·
`CLOCK_POLICY_VERSION = "clock-policy-v1"` (ADR §10.3 bunu MANIFEST alanı sayıyor; **manifest'e
yazmak ADIM 20'nindir** ve bilerek yapılmadı — sabit erken sevk edilsin diye değil, adlandırdığı
politikanın ilk satırından itibaren tek evi olsun diye var).

**Sıralama determinizmi:** görünümler `(pin_ordinal, item_id)` ile sıralanıyor — `pin_ordinal`
manifest'in deterministik pin sırasından (`manifest._pinned_items`, `(root_id,
selected_revision_id)`'ye göre sıralı). **Asla DOM sırası, asla istek varış sırası** (§4.4).

**İzolasyon — doğrulandı, iddia değil.** `origin/main` üzerinde `git grep` ile:
**hiçbir üretim modülü `clock.py`'yi import etmiyor** (`backend/src` altında sıfır eşleşme);
`run_engine` imzası **ve semantiği** korundu (§3.2), hiçbir golden digest / `ENGINE_VERSION` /
`execution_key` oynamadı. ADIM 15'in rollback'i gerçekten **"modülü sil"** — ve bu iddia
`test_the_clock_is_not_wired_into_production_yet` +
`test_no_clock_field_ships_in_the_manifest_yet_and_the_engine_version_stands` ile **testle
kilitli**, sözle değil.

**27 testin kapsadığı eksenler:** tek-öğe indirgemesi (§3.2) · sıralı birleşim · paylaşılan
instant'ın tek tick'e çökmesi · offset biçimlerinin aynı instant'a düşmesi · metin değil instant
sıralaması · tek taraflı eksen · boş/barsız öğe · heterojen timeframe interleave (**bar ödünç
almadan**) · öğe içi mükerrer instant'ın **yüzeye çıkması** · "hiçbir görünüm gelecekten veri
taşımaz" · seyrek öğenin staleness **ölçümü** · pin sırası tie-break · girdi sırası bağımsızlığı ·
rerun determinizmi · batch chunk bağımsızlığı · **materialize etmeme** · üç fail-closed dalı ·
motorun düşürdüğü satırı **aynı şekilde** düşürme · availability gate'in öğenin kendi karar
zamanında değerlenmesi · üst timeframe bucket'ının kardeş tick'lerden etkilenmemesi ·
`tick_key`'in sevk edilen epoch helper'larıyla uyuşması · `CLOCK_POLICY_VERSION` pini ·
`timeline_identity` determinizm + ayırt edicilik.

**Bilerek KARAR VERİLMEYENLER:** shared ledger + snapshot (ADIM 17) · `ItemIntent` + faz döngüsü
(ADIM 18) · conflict/sleeve arbitrasyonu (ADIM 19) · manifest alanları + `ENGINE_VERSION` bump +
containment lift (ADIM 20) · **taze barı olmayan bir pozisyonun tick'te nasıl mark edileceği —
OD-2, hâlâ AÇIK**; clock bir mark politikasının ihtiyaç duyacağı olguları **raporluyor**, seçim
yapmıyor.

**Mutation testi — kayda değer:** altı mutasyon uygulandı, altısı da yakalanıyor; ama **biri ilk
turda hayatta kaldı** — merge'ü `t_ms` yerine ham timestamp string'iyle anahtarlamak. Offset
fixture'ı iki kaydı tesadüfen bitişik bırakıyordu, `groupby` yanlış anahtarla bile doğru
gruplamıştı. Kapatan test sonradan yazıldı: `test_a_mixed_offset_axis_orders_by_instant_and_not_by_text`.
**ADIM 16–19 için yöntemsel kayıt: geçen bir suite tek başına kanıt değildir.**

**İkinci dürüst sınır — naive timestamp ayrışması (K-01):** `tick_key` →
`parse_utc(source_zone=None)` offset'siz timestamp'ı reddeder (fail-closed, doğru), ama
`indicators._epoch_seconds` **aynı değeri UTC varsayar**. Üretim barları ingest'te
UTC-normalize olduğu için bugün tetiklenmesi beklenmiyor, fakat **ADIM 16/18 bununla
karşılaşacak** — stepper ve `run_portfolio` aynı akışı hem eksene hem indikatöre verdiğinde iki
yorum aynı satırda buluşur. Ayrışma `indicators` tarafında ele alınmalı.

> ### ⚠ Dürüst sınır — ADR kapısı atlandı
>
> **ADR 0002'nin statüsü hâlâ `Proposed`** (satır 4: *"requires PO / maintainer approval before
> any implementation slice starts"*) ve §16 onay gelmeden ADIM 15'in başlamamasını şart
> koşuyordu. PR #567 bu kapıdan geçtiğine dair **kayıtlı bir onay olmadan** indi. Zarar dar —
> modül saf, hiçbir yerden import edilmiyor, rollback tek dosya silme — ama **kapı atlanmıştır**
> ve bu kayda geçer. ADIM 16'ya geçmeden önce onay durumu **açıkça** teyit edilmeli; §13'ün yedi
> açık kararı (OD-1…OD-7) hâlâ çözülmedi.

**Codemap:** `docs/CODEMAPS/BACKEND_LAYERS.md` **PR #567 içinde tazelendi** — ayrıca gerekmiyor.
Yeni endpoint / tablo / sayfa / job yok, diğer haritalar değişmedi.

**Doğrulama — dürüst sınır:** bu kapanış kaydı **docs-only bir oturumda** yazıldı ve **suite'i
yeniden ÖLÇMEDİ.** İddia edilen tek doğrulama **PR #567'nin kendi CI'ıdır (6/6 SUCCESS)**;
modül izolasyonu, `ENGINE_VERSION` sabitliği ve ADR statüsü `origin/main` üzerinde `git grep` ile
ayrıca teyit edildi.

**Doküman:** `docs/ADIM15_LANDED_KICKOFF.md` (reuse anchor'ları + ADIM 16 resume prompt) ·
`docs/PROJECT_HISTORY.md` §ADIM 15 · ADR §12 (sınırlar) / §13 (açık kararlar) / §14 (kabul
matrisi).

---

## ADIM 16 (sevk edilen) — Paylaşılan snapshot'a karşı item intent'leri landed (PR #571 + #572)

> **Bu kayıt geriye dönük yazıldı.** ADIM 16 kapanış ritüeli **yapılmamıştı**: PR #571 merge
> edildi ama ne bu dosyaya ne `PROJECT_HISTORY.md`'ye bir giriş düştü, ve aşağıdaki eski
> "Next" bloğu ADIM 16'yı hâlâ *yapılacak* iş olarak tarif ediyordu. ADIM 17 kapanışında
> tespit edildi ve burada telafi ediliyor.

**Commit `e2695e4` → merge `a572e07`** (2026-08-05T00:51:39+03:00) · branch
`feat/portfolio-item-intents` · **+1943 / −3, 4 dosya** · **Migration YOK** (alembic head
`0043_i08_registry_strategy_fks`) · **OpenAPI DEĞİŞMEDİ** · **`ENGINE_VERSION` DEĞİŞMEDİ** ·
CI yeşil. Ardından **PR #572** (`3a2aea9`) ADIM 15'in mutasyon kaydını ve naive-timestamp
sapmasını docs'a taşıdı.

| dosya | |
|---|---|
| `backend/src/entropia/domain/backtest/execution/intents.py` | **yeni**, 846 satır |
| `backend/tests/unit/test_backtest_item_intents.py` | **yeni**, 1087 satır / **45 vaka** |
| `backend/tests/unit/test_backtest_unified_clock.py` | clock containment testi bilerek güncellendi |

**⚠ PLAN SAPMASI — kayda geçirilmesi gereken:** ADR 0002 §12'nin tablosunda **ADIM 16 =
`run_engine`'den resumable stepper (saf refactor, kabul = 46 golden digest sabit)**, **ADIM 18 =
`ItemIntent` + faz döngüsü**. Sevk edilen ADIM 16 ise `ItemIntent` + `PortfolioSnapshot`
katmanıdır — yani **ADR'nin ADIM 18'inin bir yarısı**, stepper'ın yerine. **Stepper hâlâ
yazılmadı** ve ADR §12 sınırları "dondurulmuş" diye ilan edilmişti. Bir sonraki oturum ya
ADR §12'yi bir amendment ile bu sıraya göre güncellemeli ya da stepper'ı geri planlamalı;
**sessizce kabullenilmemeli.**

**Ne getirdi:** doc 13 §8.4 adım 4'ün tek cümlesi — her aktif item aynı valuation snapshot'ıyla
intent üretir. `PortfolioSnapshot` (read-only VALUE; `A(t)`/`U(t)` `__post_init__`'te TÜRETİLİR,
`R0` sabit nominal, sha256 `identity`), `form_intent` (**P4**, snapshot'a karşı),
`form_mandatory_intent` (**P3**, snapshot argümanı **ALMAZ** — stop/exit valuation'dan önce
çözülür, kanonik sıra yapıyla korunur). Karar **girdidir**, burada yeniden hesaplanmaz; boyutlar
sevk edilmiş zincirden gelir. Sleeve cap UYGULANMAZ (P6b). `no_op`/`blocked` birinci sınıf.
**Hiçbir üretim modülü import etmiyor**; `clock`'un tek izinli importer'ı budur.

---

## ADIM 17 — Shared capital ve exposure ledger landed (PR #573)

**Commit `3ad5bf3` → squash-merge `f8f96c5`** (2026-08-05T02:13:50+03:00) · branch
`feat/portfolio-shared-ledger` · **+2570 / −3, 5 dosya** · **Migration YOK** (alembic head
`0043_i08_registry_strategy_fks`) · **OpenAPI DEĞİŞMEDİ** · **`ENGINE_VERSION` DEĞİŞMEDİ**
(`backtest-engine-v18-gap-adjusted-stop-fill`) · **CI 6/6 SUCCESS** (Backend job 42m42s).

| dosya | |
|---|---|
| `backend/src/entropia/domain/backtest/execution/portfolio_ledger.py` | **yeni**, 971 satır |
| `backend/tests/unit/test_backtest_portfolio_ledger.py` | **yeni**, 1277 satır / **59 fonksiyon, 100 vaka** |
| `docs/audit/portfolio_ledger_accounting.md` | **yeni**, 311 satır — muhasebe spec + fixture'lar + reconciliation |
| `backend/tests/unit/test_backtest_item_intents.py` | intents containment testi **bilerek** güncellendi |
| `docs/CODEMAPS/BACKEND_LAYERS.md` | `backtest` satırına `execution/portfolio_ledger.py` paragrafı |

**Ne getirdi — ADR 0002 §12'nin ADIM 17'si.** Sevk edilen motor öğe **başına** bir `_Ledger`
tutuyor ve her birini **tam havuzdan** tohumluyor (`engine.py:846`), bu yüzden bir öğenin
sleeve'i kendi equity'si üzerinden compound oluyor ve kardeşinin PnL/fee/funding'ini asla
göremiyor. Bu slice o durumun yerine geçen **tek** hesap defterini getirir — onu sürecek
döngüyü değil.

* **`SleevePlan`** `P0`/`R0`/`A0`/`Ci0`/`U0`'ı **bir kez** çözer; `A0`/`Ci0`/`U0`
  `__post_init__`'te türetilir (tutarsız yayımlanamazlar), `R0` **nominal TUTAR** olarak
  tutulur — böylece aşağı akışta hiçbir şey yüzdeyi sonraki bir equity'ye yeniden uygulayamaz.
  `P0<=0`, negatif share, toplam share>100 **reddedilir** (üçü de kanonik Ready-Check blocker'ı).
* **`E(t) = P0 + realized − fees − funding − other`, kanon gereği YALNIZ REALIZED.** Her booking
  deltasını sevk edilmiş **artımlı** quantize ile uygular (`quantize(equity + delta, 0.01)`,
  `booking.py:96`) ve kovaya **gerçekten uygulanan** deltayı yazar → `accounting_identity ==
  equity` **yapıyla** sent sente doğru. Kovaları bağımsız toplamak eşdeğer DEĞİL: yuvarlama,
  kuantumun tam katı boyunca yalnız half-even tie-break'i uyuştuğunda öteleme-değişmezdir.
* **Spread/slippage fill fiyatının İÇİNDE** (`costs._effective_fill`), ikinci kez maliyet satırı
  olarak yazılmaz — her fill'i çift sayardı. Ayrı satırlar: commission, funding, `other_costs`.
* **`publish_snapshot` defteri DONDURUR** (`begin_apply`'a kadar): ADR §8.1'in "PV ile P7 arası
  hiçbir yazar koşamaz" kuralı disiplin değil **yapı** oldu.
* **`resolve_capacity` = P6b:** sleeve / item risk limit / exposure cap **CLAMP**, ledger
  solvency **yalnız REDDEDER** — M11 §5.3 kısmi fill ve sessiz borrow'u yasaklıyor, kırpılmış
  bir order zaten kısmi fill'dir. Her katmanın headroom'u yayımlanır, yalnız bağlayan değil.
* **`net_exposure` ÖLÇÜMDÜR.** Hiçbir cap/headroom/solvency ondan türetilmez: NET semantiği
  kanonda tanımsız (ADR §9.4, #544) ve net figürden kapasite hesaplamak NET'i kazara sevk
  ederdi. Hedge'li long/short çifti **hiç** sermaye serbest bırakmaz.
* **No-borrow guard ARTIŞI bağlar**, duran toplamı değil — equity düştüğünde "açık pozisyonlar
  zorla rebalance edilmez" (doc 13 §8.3) kuralının tüm içeriği budur. **Yerinde reversal
  reddedilir:** yeni notional'ı eskisiyle netlemek yalnız farkı kontrol ederdi, oysa reversal
  bir taahhüdü bırakıp başka birini alır.
* **`valuation()`** açık pozisyonları TEK noktada markler ve sonucu `E(t)`'nin **yanında**
  raporlar, içine katlamaz. Marklanamayan pozisyon **raporlanır**, asla sıfır değerlenmez —
  **OD-2 açık**; ledger authority ve staleness'ı kaydeder, eşik seçmez.
* **`PortfolioEquityPoint` yeni bir tiptir**, `state.EquityPoint` değil. ADR §7 sevk edileni
  yeniden kullanmayı taslaklamıştı; ama onun `exposure`'ı *kapanan lot'un* notional'ı /
  kapanış öncesi equity demek — yeniden kullanmak alan adlarını koruyup ikisinin anlamını
  sessizce değiştirirdi.

**Parity iddia edilmedi, KONTROL EDİLDİ** (`docs/audit/portfolio_ledger_accounting.md` §4):
başlangıç bölüşümü kullanıcıya gösterilen **allocation preview**'ıyla (M11 §5.1 bunu şart
koşuyor ve bugüne dek hiçbir şey zorlamıyordu), `Ci(t)` `sizing.sleeve_capital` ile (24 vaka),
granted units `sizing._cap_to_sleeve` ile (9 vaka), ve tüm tek-item zinciri sevk edilmiş sleeve
oracle'ının **gerçek `run_engine` replay'i** ile (44.11764706 birim, 88.24 PnL, 100.088,24
final book). Karşılaştırılacak sevk edilmiş bir şey **olmayan** yerler (çok-item `E(t)`,
`net_exposure`, marklanmış figürler, portföy eğrisinin nokta sayısı) raporda **açıkça öyle
yazıldı**.

**Mutasyon kaydı — biri ilk turda HAYATTA KALDI.** 12 mutasyon tek tek uygulandı. **M6** —
no-borrow guard'ının artış yerine **duran toplamı** bağlaması — tüm suite'i geçti, çünkü hiçbir
test havuzun sıfırdan açmaya artık gücü yetmeyen bir pozisyonun **yeniden boyutlandırılmasını**
zorlamıyordu; bu tam da no-force-rebalance kuralının koruduğu şekil.
`test_only_the_increase_in_committed_capital_is_checked_against_the_pool` sonradan yazıldı
(headroom'u tam tüketen bir scale-in + su altındayken bir **küçültme**), ikinci tur **12/12
yakalandı, 0 hayatta kalan**. Yerinde-reversal guard'ı ise **testten değil gözden geçirmeden**
çıktı; `M12` onunla birlikte eklendi.

**Ölçüm dürüstlüğü.** Yerel tam suite koşuldu ve coverage kapısı **%93.09** ile geçti
(kapı ≥90; yeni modül **%98.8**), ama koşu arka planda başlatıldığı için **pytest'in özet
satırı ve exit code'u yakalanmadı** — CLAUDE.md'nin "çıktıyı dosyaya yaz, `$?`'i ayrı oku"
uyarısına uyulmadı. **Otorite CI'dır:** `Backend — lint, type, test` **pass**, 42m42s. Bir
sonraki slice bu hatayı tekrarlamamalı.

**Kapsam dışı (bilerek):** faz döngüsü (ADIM 18), cross-item arbitrasyon / NET / **OD-3**
(ADIM 19), manifest alanları + `ENGINE_VERSION` bump (ADIM 20), mark policy (**OD-2**),
herhangi bir margin modeli (ADR §9.5 — `leverage_mode=cross` `canonical_gap` kalır).

**Rollback:** `git revert`. Üretimde modülü import eden yok; `ENGINE_VERSION`, 46 golden digest,
alembic head, OpenAPI snapshot ve frontend dokunulmadı.

---

## ADIM 18 (sevk edilen sıra) — Cross-item intent arbitrasyonu landed (PR #575)

> **Geriye dönük kayıt.** Bu slice'ın kapanışı zamanında yapılmadı; bölüm PR #575'in gerçek
> diff'i ve CI kaydı okunarak sonradan yazıldı. Tam anlatı:
> `docs/PROJECT_HISTORY.md` §"ADIM 18 (sevk edilen sıra)".

**Commit `df0082e` → squash-merge `9739466`** (2026-08-05T09:08:51+03:00) · base `1430b28` ·
branch `feat/portfolio-cross-item-arbitration` · **+2257 / −14, 6 dosya** · **Migration YOK**
(alembic head `0043_i08_registry_strategy_fks`) · **OpenAPI DEĞİŞMEDİ** · **`ENGINE_VERSION`
DEĞİŞMEDİ** (46 golden digest sabit) · **CI 6/6 SUCCESS** (Backend job 43m40s).

**⚠ Başlıktaki "ADIM 18" ADR §12'nin ADIM 18'i DEĞİL.** PR kendine numara vermedi; ADIM 17
kapanışı arbitrasyonu "ADIM 19" diye rezerve etmişti, sonra PR #581 kendini "ADIM 19" ilan etti.
Buradaki numara **sevk sırasıdır** (15 clock · 16 intents · 17 ledger · **18 arbitration** ·
19 provenance). **ADR §12'nin ADIM 18'i `run_portfolio` faz döngüsüdür ve hâlâ yazılmadı** —
aşağıdaki `## Next:` bloğu geçerliliğini koruyor.

| dosya | |
|---|---|
| `backend/src/entropia/domain/backtest/execution/arbitration.py` | **yeni**, 919 satır |
| `backend/tests/unit/test_backtest_cross_item_arbitration.py` | **yeni**, 1145 satır / **41 fonksiyon, 44 vaka** |
| `docs/audit/cross_item_conflict_policy.md` | **yeni**, 171 satır — politika tablosu + NET durumu |
| `test_backtest_item_intents.py` · `test_backtest_portfolio_ledger.py` | containment testleri **bilerek** güncellendi |
| `docs/CODEMAPS/BACKEND_LAYERS.md` | `execution/arbitration.py` satırı |

**Ne getirdi — ADR §9'un P5 (cross-item conflict) + P6b (capacity) fazları.** Saf ve contained;
`run_engine` imzası **ve** semantiği aynı, replay oynamıyor. `CONFLICT_POLICY_TABLE`:
`KEEP_SEPARATE` karşıta izin verir, `BLOCK_OPPOSITE` bloklar, **`NET` reddedilir** — sevk edilen
motorun `NET → BLOCK_OPPOSITE` düşürmesi **ileri taşınmadı**, `resolve_policy("NET")` karar
oluşmadan fırlatır ve `NET_UNDEFINED_SEMANTICS` beş tanımsız semantiği adlandırır. Bilinmeyen
token da reddedilir. `shares_capital` her satırda `True` ve **yazılı**: politika pozisyon
defterini ayırır, havuzu değil. Tutulan pozisyon **pin ordinalinden bağımsız kazanır**
(ileri-yönlü sevk kuralı sıralı döngünün artefaktıydı); aynı tick'te düşük
`(pin_ordinal, item_id)` kabul edilir; bilinmeyen enstrüman kimliği fail-closed; **zorunlu P3
intent'i asla arbitre edilmez**; `arbitrate()` **donmamış** defterde koşmayı reddeder. Kapasite
çekişmesinde cap'ler **clamp**, solvency **bütün olarak reddeder**, **bloklanan öğenin kapasitesi
kardeşe devredilmez**. **OD-3 AÇIK ve etiketli:** `CONTENTION_SELECTION_POLICY =
"pin_order_admission"` + `CONTENTION_SELECTION_STATUS = "recommended_pending_approval"` her
raporda ve çekişmeli her kararda taşınır. **Yeni reason sözcüğü YOK** — `ARBITRATION_REASONS`
sevk edilmiş token kümesi üzerinde kapalı.

**Ölçüm:** otorite CI (Backend pass 43m40s). PR gövdesinde kayıtlı yerel ölçüm: exit 0,
0 FAILED/0 ERROR, coverage **%93.15** (kapı ≥90), `arbitration.py` **%99.1**, ruff/mypy temiz.
**Mutasyon turu bu slice'ta kaydedilmedi** (ADIM 17'de 12, ADIM 19'da 10 vardı) — eksiklik
olarak yazılıyor, geriye dönük sayı uydurulmuyor.

**Kapsam dışı (bilerek):** faz döngüsü · Result attribution / diagnostics kalıcılığı (kararlar
typed değer olarak üretilir, hiçbir şey yazmaz) · manifest alanları
(`arbitration_policy_version` `ENGINE_VERSION` bump'ıyla) · containment lift · cross-margin /
netting · **OD-2**. **ADR 0002 hâlâ `Proposed`**, bu slice da kayıtlı onay olmadan indi.

**Rollback:** `git revert` (= "modülü sil").

---

## ADIM 19 — Unified-clock result provenance + per-item attribution landed (PR #581)

> **Geriye dönük kayıt.** Kapanışı zamanında yapılmadı; PR #581'in gerçek diff'i ve CI kaydı
> okunarak sonradan yazıldı. Tam anlatı: `docs/PROJECT_HISTORY.md` §ADIM 19 + kanıt raporu
> `docs/audit/portfolio_result_provenance.md`.

**Commit `89cf0b6` (+ `7fcf3ea`, `61da506`) → squash-merge `b0bb4a0`**
(2026-08-05T12:37:21+03:00) · base `9739466` · branch `feat/portfolio-unified-result-artifacts` ·
**+3199 / −9, 23 dosya** · **Migration YOK** (alembic head `0043_i08_registry_strategy_fks`) ·
**OpenAPI snapshot BYTE-ÖZDEŞ** · **`ENGINE_VERSION` DEĞİŞMEDİ** (46 golden digest sabit,
`contract.execution_key` dahil) · **CI 6/6 SUCCESS** (Backend job 45m45s).

**Programın ÜRETİME dokunan ilk slice'ı.** ADIM 15–18 tamamen contained'dı; burada iki contained
modülün yanında sevk edilen bir **okuma-zamanı etiketi** indi. **Containment yine de
KALDIRILMADI:** `SHARED_ALLOCATION_STATUS = "future_dev"`.

| dosya | |
|---|---|
| `execution/provenance.py` · `execution/attribution.py` | **yeni, contained**, 542 + 406 satır |
| `domain/backtest/portfolio_mode.py` | **yeni, ÜRETİM**, 206 satır |
| `repositories/backtest.py` | `get_run_diagnostics_markers` + `get_portfolio_mode_markers` (+88) |
| `queries/backtest_run.py` · `queries/results_history.py` | `portfolio_simulation` (+9 / +25) |
| `lib/backtest.ts` · `pages/ResultsHistory.tsx` · `components/ResultDetail.tsx` | tip + iki render (+28 / +12 / +32) |
| 3 yeni unit + 1 entegrasyon + 1 frontend test dosyası | **80 yeni backend vakası + 6 frontend vakası** |
| `docs/audit/portfolio_result_provenance.md` | **yeni**, 372 satır |
| dört mevcut containment testi | **bilerek** güncellendi; iki yenisi eklendi |

**Kapattığı iki boşluk, kod yazılmadan önce reprodüksiyonla kanıtlandı.** (A) `validate_allocation`
kanonun istediği her figürü hesaplayıp `_resolve_allocation` onu **atıyordu**;
`initial_sleeve_capital` ve `engine_allocation_policy_version` manifest JSON'ının hiçbir yerinde
yoktu. (B) per-item **unrealized** attribution hiç yoktu.

**Üç karar:** (1) **`ENGINE_VERSION` bump EDİLMEDİ** — bump `execution_key` namespace'ini kaydırıp
mevcut her Result'ı idempotent re-RUN için kullanılamaz yapardı; (2) **görünen etiketler hash'in
dışında** (`identity` yalnız `execution_content()`'i hash'ler); (3) **karşı-olgusal marjinal
uydurulmadı** (`COUNTERFACTUAL_MARGINAL_STATUS = "not_derivable_without_re_simulation"`).
**OD-2 ifşa edildi:** `MARK_STALENESS_POLICY = "undefined_pending_od2"` — ADIM 18'in OD-3
emsalinin aynısı.

**İki bulgu:** preview ve execution aynı sleeve'i farklı yuvarlıyor (`ROUND_HALF_UP` vs
`ROUND_HALF_EVEN`; `1000.10 @ %25` → **250.03 vs 250.025**) → manifest donmuş preview'ı tutar,
`sleeve_amount_divergences()` anlaşmazlığı **raporlar**, *ürün kararı gerekiyor*; ve tek-item
Result teşhissiz Result'tan **ayırt edilemiyordu** → motorun kendi pinli `engine_kind`'ıyla
çözüldü.

**Ölçüm:** otorite CI (Backend pass 45m45s, 6/6). **Mutasyon: 10 enjekte, 10'u öldürüldü**
(M3'ün *pattern not found*'u bayat harness literaliydi; gerçek kaynağa yeniden uygulanıp
öldürüldü — bayat pattern tasarım gereği **hayatta kalan** sayılır). **KAYDEDİLMEYEN:** bu PR
gövdesi **coverage yüzdesi ve suite toplamı bildirmiyor**; o figürler bu slice için hiç
ölçülmedi/yazılmadı ve buraya geriye dönük konmadı — coverage kapısının geçtiğinin tek kanıtı
yeşil CI job'ıdır.

**Dürüst sınırlar:** (1) unified faz döngüsü YOK, `unified_clock` **üretimde erişilemez**, yalnız
sentetik pinli manifest'li testlerle sınanıyor — "unified koşular çalışıyor" diye okunmamalı;
(2) `portfolio_simulation` **OpenAPI'de yayımlanmıyor** — iki route da bare `dict[str, Any]`
döndürüyor, yani tüm Result-detail/history gövdesi şemada yok (önceden var olan, **O-30 şeklinde**
kusur; typed hâle getirmek ayrı slice); (3) yarım-sentlik sleeve sapması **düzeltilmedi, ifşa
edildi**; (4) **ADR 0002 hâlâ `Proposed`** ve §12 numaralandırması sevk edilenle uyuşmuyor.

**ADIM 18/19'un `run_portfolio`'ya bıraktığı — tam sembol adlarıyla** (aşağıdaki `## Next:`
bloğundaki ADIM 15/16/17 tablosunun devamı):

| ne | nerede |
|---|---|
| P5 çatışma + P6b kapasite kararı, tick başına | `execution/arbitration.py::arbitrate` → `ArbitrationReport` / `ArbitrationDecision` |
| politika tablosu + NET reddi | `arbitration.py::CONFLICT_POLICY_TABLE`, `ConflictPolicyRule`, `resolve_policy`, `NET_UNDEFINED_SEMANTICS` |
| manifest pin'lerinden profil kurma | `arbitration.py::profiles_from_pins` → `ItemArbitrationProfile` |
| OD-3 etiketi (rapora ve karara gömülü) | `arbitration.py::CONTENTION_SELECTION_POLICY` / `CONTENTION_SELECTION_STATUS` |
| unified manifest bölümü + kimlik | `execution/provenance.py::build_portfolio_manifest` → `PortfolioManifest` |
| donmuş allocation tutarlarının kopyası | `provenance.py::allocation_provenance_from_derived`, `independent_allocation_provenance`, `AllocationProvenance` |
| preview↔execution sapma raporu | `provenance.py::sleeve_amount_divergences` |
| ledger artefakt referansı + checksum | `provenance.py::ledger_artifact_ref` → `LedgerArtifactRef`, `ledger_equity_rows` |
| pinli öğe listesi / etiketler | `provenance.py::pinned_items_from_identities`, `item_labels_from_identities`, `PinnedItem` |
| per-item mutabakatlı attribution | `execution/attribution.py::attribute` → `PortfolioAttribution` / `ItemContribution` (residual≠0 → `AttributionResidualError`) |
| katkı serisi + korelasyon raporu | `attribution.py::contribution_series`, `contribution_correlation`, `build_contribution_report` |
| Result'ın hangi co-simulation'dan geldiği | `domain/backtest/portfolio_mode.py::resolve_portfolio_simulation_mode`, `portfolio_simulation_context`, `…_from_parts` |
| batched marker okuma (N+1 yok) | `repositories/backtest.py::get_run_diagnostics_markers`, `get_portfolio_mode_markers` |

**DİKKAT:** `arbitration.py`, `provenance.py` ve `attribution.py` bugün **üretimden import
edilmiyor** ve containment testleri bunu kilitliyor
(`test_nothing_in_production_imports_the_arbitration_layer_yet`,
`…_the_provenance_layer_yet`, `…_the_attribution_layer_yet`). `portfolio_mode.py`
**istisnadır** — o sevk edildi. Containment testlerini **bilerek** güncelle; kazara
kırılmamalılar.

**Rollback:** `git revert`. Contained iki modülü import eden yok; üretim tarafı yalnız
okuma-zamanı bir etiket ekliyor (yeni tablo/kolon/yazma yolu yok).

---

## ADIM 20 — Unified portfolio oracle suite; containment KALDIRILMADI (PR #583, BLOCKED)
<<

**Base `b0bb4a0` → commit `fd0ead5` → PR #583 DRAFT/BLOCKED** · issue **#582** · 2026-08-05 ·
**migration YOK** (alembic head `0043_i08_registry_strategy_fks`) · **OpenAPI değişmedi** ·
**`ENGINE_VERSION` değişmedi** · **üretim kodu HİÇ değişmedi**.

**`SHARED_ALLOCATION_STATUS` = `future_dev` kaldı.** Durma koşulu tetiklendi — bir oracle
kırmızı olduğu için değil, **kabul edilecek sistem olmadığı için**: `run_portfolio` yok,
altı unified-clock modülü üretimden hiç import edilmiyor, `jobs/backtest_engine.py` hâlâ
item döngüsü (`:298`) + `combine_item_runs` (`:363`), ADR'nin **ADIM 16**'sı (resumable
stepper) atlandı, ADR hâlâ `Proposed`.

**İndi:** 25 test — mevcut 216 birim testinin bıraktığı tek boşluk, yani **çok-tick /
çok-item birleşik simülasyon** (clock → intents → ledger → arbitration birlikte).
`tests/unit/oracles/portfolio_harness.py` (ADR §8.2 faz döngüsü, **TEST-OWNED**) +
`test_oracle_portfolio_clock.py` (10) + `test_oracle_portfolio_capital.py` (11) +
`test_oracle_portfolio_containment_gate.py` (4) + `docs/audit/unified_portfolio_oracle_acceptance.md`
(A1–A22 durum tablosu). Aynı dört kapanış **sıralı fold'da 5000.00**, **birleşik saatte
3000.00**. Beklenen değerlerin tümü elle türetilmiş literal; **non-vacuity dört literal
bozularak doğrulandı** (tam olarak o dört test kırıldı).

**Testler:** yerel tam suite tek çağrıda **exit 0**, 0 FAILED, **coverage %93.24** (kapı ≥90);
`ruff`/`mypy` temiz; `tests/unit/oracles/` **111 passed**. Frontend dosyası değişmedi.

**Dürüst sınır:** faz döngüsü **test-owned**; yeşil koşu primitifler hakkında kanıttır, sevk
edilen engine hakkında değil. ADIM 18 indiğinde `portfolio_harness.simulate` →
`run_portfolio` ikame edilmeli ve 25 oracle **değişmeden** yeşil olmalı.

Tam kayıt: `docs/PROJECT_HISTORY.md` §ADIM 20 · handoff: `docs/ADIM20_BLOCKED_KICKOFF.md`.

**Yan bulgu:** bu dosya ve `PROJECT_HISTORY.md` **PR #575 (arbitration) ve #581 (provenance)
için `landed` kaydı taşımıyor**; aşağıdaki `## Next:` bloğu ADIM 20 öncesine aitti ve hâlâ
geçerlidir. Eksik kayıtları yazacak olan o slice'ları indirendir.

---

## ADIM 18 — `run_portfolio` faz döngüsü; ADR 0002 Accepted (PR #586)

> **Ad çakışması, bilerek:** PR #575 de "ADIM 18" etiketiyle indi (cross-item arbitration).
> Bu slice ADR §12'nin **18. satırının faz-döngüsü yarısıdır**. Sevk edilen numaralandırma ile
> ADR'nin numaralandırması arasındaki tam eşleme artık ADR §12'nin düzeltme notundadır.

**Base `d7fe432` → branch `feat/stage-18-run-portfolio`** · 2026-08-05 · **migration YOK**
(alembic head `0043_i08_registry_strategy_fks`) · **OpenAPI değişmedi** · **`ENGINE_VERSION`
değişmedi** · **frontend dokunulmadı** · **`SHARED_ALLOCATION_STATUS` = `future_dev` kaldı.**

**İnsan kapısı önce geçildi (ADIM 0).** ADR 0002 **`Accepted`** oldu; §13'ün yedi açık kararı
§13.1 amendment tablosuna **tavsiye edildikleri gibi** (OD-1(a) … OD-7(a)) çözüm olarak yazıldı.
§16, onayın **ADIM 15–19'dan SONRA** geldiğini tidy'lemeden kayda geçiriyor. §12 sevk edilene
göre düzeltildi: **ADR'nin ADIM 16'sı (resumable stepper) formally SKIPPED**.

**İndi — tek yeni üretim dosyası:** `backend/src/entropia/domain/backtest/portfolio_engine.py`
(549 satır). `run_portfolio(...)` ADR §8.2 faz sırasını sahiplenir:
`P1 carry → P3 mandatory (snapshot YOK) → PV publish_snapshot [ledger DONAR] → P4 intents →
P5/P6b arbitrate → P7 begin_apply + set_position → P9 commit_tick`.
Kendi aritmetiği **yok** — booking'i katılımcının bildirdiği rakamdan yapar, hiçbir şeyi cap'lemez,
hiçbir boyut hesaplamaz. Yeni sözleşme: **`ItemParticipant` Protocol** (`identity`, `stream`,
`instrument_id`, `carry` → `CarryCharges`, `mandatory_exit` → `MandatoryExit`, `entry` →
`ItemIntent`). Çıktı tipleri `PortfolioTick` / `PortfolioRun` de burada.

**Neden P4 hazır `ItemIntent` alıyor (sözleşme kararı):** `execution.intents` "karar bir
GİRDİdir" diyor; aynı argüman bir entry'nin **boyutu** için de geçerli — `form_intent` entry'yi
`costs._effective_fill` + `sizing._position_size` üzerinden ölçer ve bunlar item'ın kendi
`StrategyConfig`/`FillCosts`'unu ister. Döngü bu yüzden **oluşturmaz, doğrular**: doğru item,
doğru tick, doğru snapshot identity, doğru faz, mandatory olmayan tür. `form_intents`'in
vereceği garantiler **sınırda kontrol edilir**.

**Kabul — tek ölçüt karşılandı:** `portfolio_harness.simulate` artık `run_portfolio` üzerine
ince bir adaptör; **25 portföy oracle'ı gövde ve beklenen literal olarak BİREBİR aynı kaldı**
(yalnız iki docstring güncellendi — artık yanlış olan "TEST-OWNED" cümlesi). `tests/unit/oracles/`
**111 passed**. Bu, A1/A3/A5'i PRIMITIVE'den MET'e taşıyan hamledir.

**Bilerek güncellenen containment guard'ları (4/6 — diğer ikisine dokunulmadı):**
`test_the_clock_is_not_wired_into_production_yet` → `..._is_reachable_only_through_the_phase_loop`;
aynı yeniden adlandırma intent / shared-ledger / arbitration guard'larında. Dördü de artık
`domain/backtest/portfolio_engine.py`'yi **adlandırılmış** importer olarak listeler — assertion
gevşetilmedi. **`attribution` ve `provenance` guard'ları değişmedi**: faz döngüsü onları import
etmiyor, o iki katman hâlâ tam contained (`build_portfolio_manifest` ADIM 20'nin).
Oracle kapısı `test_no_unified_clock_driver_exists_in_production_on_this_commit` **silinmedi,
pozitif muadiline yeniden yazıldı**: `test_the_phase_loop_exists_but_no_production_path_reaches_it`
— döngünün var olduğunu, `def run_portfolio`'nun **tek** üretim modülünde olduğunu, altı modülün
**yalnız** faz döngüsünden erişilebildiğini ve **`run_portfolio`'nun üretimde HİÇ çağıranı
olmadığını** iddia eder.

**Golden digest kapısı:** `test_backtest_engine_golden.py` yeşil, `engine_golden_digests.json`
**dokunulmadı** — `run_engine`'in gövdesine hiç girilmedi (ADR §3.2).

**DÜRÜST SINIR — kapanmadı:** `application/jobs/backtest_engine.py:298` **hâlâ item döngüsü**,
`:363` hâlâ `combine_item_runs`. Worker'ı bağlamak, gerçek engine ile desteklenen bir
`ItemParticipant` ister: bir item'ı verilen `t`'ye ilerletebilen replay — yani **ADR'nin
atlanan ADIM 16 stepper'ı**. `engine.py`'de böyle bir şey yok (bar döngüsü `:1782`, ~1100
satırlık fonksiyonun içinde). Bu yüzden faz döngüsü **çağıransız** indi: hiçbir request/retry
bir tick loop'una ulaşamaz, hiçbir sevk edilmiş Result değişemez, containment kapalı kalır.

Tam kayıt: `docs/PROJECT_HISTORY.md` §ADIM 18 · handoff: `docs/ADIM18_LANDED_KICKOFF.md`.

**Devam eden yan bulgu:** bu dosya ve `PROJECT_HISTORY.md` hâlâ **PR #575 (arbitration) ve #581
(provenance) için `landed` kaydı taşımıyor**. Bu slice o kayıtları **uydurmadı**.

---

## ADIM 21 (worker delivery) — Crash/retry/redelivery güvenliği landed (PR #587) + canlı Docker doğrulaması (PR #592)

> **Ad çakışması, bilerek korundu — ADIM 18 kaydındaki desenin aynısı.** Aşağıdaki `## Next`
> bloğu "yeni ADIM 21"i **engine-destekli `ItemParticipant`** (worker call site) olarak
> planlamıştı; PR #587 ise kendini "ADIM 21 — worker delivery & recovery" diye adlandırarak
> indi. **İki AYRI slice, tek numara.** `Next`'teki `ItemParticipant` işi **değişmedi ve hâlâ
> sıradaki iştir**.
>
> **KARAR (2026-08-05, insan): numaralar OLDUĞU GİBİ kalıyor, ayrım adla yapılır.** Yeniden
> atama yok. Sevk edilmiş slice her yerde **"ADIM 21 (worker delivery)"**, planlanan slice
> **"ADIM 21 (ItemParticipant)"** diye anılır — çıplak "ADIM 21" tek başına belirsizdir, öyle
> yazma. Gerekçe: #587/#592/#593/#595'in PR başlıkları, commit mesajları ve
> `docs/audit/worker_delivery_recovery_matrix.md` §7.1 hepsi "ADIM 21" diyor ve geriye dönük
> düzeltilemez; numarayı taşımak yazılı kaydı sessizce yanlışlardı.

At-least-once transport altında crash/retry/redelivery güvenliği: exactly-once transport değil,
**effectively-once domain effects**. İki kusur, ikisi de kod yazılmadan önce reprodüklendi.

- **Kusur 1 — `data` kuyruğunun guard'ı YOKTU.** Beş `data` gövdesini aynı `job_id` ile iki kez
  koşturmak ikinci immutable artefakt + audit + outbox yazıyordu (`revisions=2 audits=2
  outbox=2`); taze id'ler yüzünden hiçbir unique constraint tetiklenmiyor. Yeni paylaşılan
  **`application/jobs/delivery.py::claim_job_for_delivery`** — `jobs` satırının
  `SELECT … FOR UPDATE` ile okunması + terminal replay. Kendi domain-satır kilidi olan
  gövdeler (`backtest_engine`, `agent_executor`, `create_package`) bunu **çağırmaz**.
- **Kusur 2 — `agent-executor` kuyruğunun TÜKETİCİSİ YOKTU.** Coordinator gönderiyor, scheduler
  sonsuza dek yeniden yolluyor, task hiç koşmuyor, `send` hep başarılı olduğu için hiçbir katman
  hata bildirmiyor. Yeni **`worker-agent-executor`** compose servisi (worker-agent'a eklenen bir
  kuyruk değil — executor tam backtest engine'i koşuyor).

**Migration YOK** · **OpenAPI drift YOK** · frontend dokunulmadı · `ENGINE_VERSION` değişmedi.
Suite **3669 passed / 4 xfailed**, coverage **%93.26**, CI 6/6 yeşil.

**Canlı doğrulama (merge sonrası).** PR #587 iki kapıyı dürüstçe **"koşulmadı"** diye
işaretleyerek indi — o ortamda Docker yoktu, smoke yalnız `bash -n` görmüştü,
`worker-agent-executor` hiç boot edilmemişti. Kapatıldı: `make accept` **exit 0** (15/15,
`RestartCount=0`), `worker-agent-executor` tüketimi **broker'da** doğrulandı, boş-stack smoke
exit 0 **ama boş bir doğru** (tüm sayaçlar 0, guard hiç girilmedi), ve **mid-flight kill**
gerçek kanıtı verdi: 8 eşzamanlı job, parse sırasında SIGKILL, **11 delivery**, job başına
**tam 1** `market_validation_run`, `audit=outbox=44`, duplicate **0**.
Tam kayıt: **`docs/audit/worker_delivery_recovery_matrix.md` §7.1**.

**Doğrulamada çıkan iki pre-existing kusur (bu slice'ın regresyonu DEĞİL, düzeltilmedi):**

1. **`apps/worker/actors.py` durable job MAHSUR bırakıyor.** Mesaj başına `asyncio.run` +
   `@lru_cache`'li engine → `attached to a different loop`; 11 delivery'de 4 çökme, bir mesaj
   `max_retries=3`'ü tüketip düştü, `job_01KZ9717XQ5V0PKJ1PGKMB7P7B` kalıcı `queued`/`attempts=0`
   ve **hiçbir şey kurtarmıyor**. Duplikasyonun ayna kusuru: etkinin hiç oluşmaması. Crash
   gerekmiyor, paralel iki `data` job'ı yeter. Aynı desen `apps/scheduler/__main__.py`'de **her
   ikinci** maintenance pass'ini iptal ettiriyor (12 tick'te 6 OK / 6 failed, kusursuz alternasyon)
   → **scheduler yarısı PR #593 (`20a32ab`) ile DÜZELTİLDİ** (process ömrü boyunca tek event
   loop). **`actors.py` yarısı ölçüldüğü gibi AÇIK** — #593 yalnız scheduler ikizine dokundu.
2. **`worker-agent-executor` dev-auth override'ında yok** → `AUTH_MODE=session` koşuyor;
   `test_worker_plane_deployment.py` yalnız `docker-compose.yml`'i pinlediği için görmüyor.
   Kusur 2'nin tıpatıp aynı şekli. → **DÜZELTİLDİ:** servis override'a eklendi, test artık
   **iki compose dosyasını da** okuyor (`docs/audit/worker_delivery_recovery_matrix.md` §7.2).

Ayrıca `worker-restart-smoke.sh` adım 5'in grep'i `scheduler.maintenance_failed`'i de yakalıyor
→ **PR #593 ile DÜZELTİLDİ** (`scheduler\.maintenance([^_]|$)`).

**Dürüst sınır:** mid-flight kanıtı yalnız `data`/market-data actor'ünü kapsıyor; diğer dört
gövde canlı crash-test edilmedi. Seam 5 (eşzamanlı iki delivery) hiçbir plane için canlı
doğrulanmadı. `agent`/`agent-high` guard'ı `idempotency_key is not None` biçiminde — `None` ile
enqueue eden çağıran guard'sız kalır (açık soru).

---

## INF-14 — Scheduler event-loop ömrü landed (PR #593)

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

## ADIM 16 (ADR §12) — `run_engine`'in bar döngüsü resumable stepper'a çıkarıldı ✅ landed (PR #602)

Engine-destekli `ItemParticipant` çiftinin **PR A**'sı. `run_engine`'in ~2400 satırlık gövdesine
gömülü **1355 satırlık bar döngüsü** askıya alınabilir bir stepper'a çıkarıldı: setup yarısı
`_build_stepper(...)` (`engine.py:779`) oldu ve bir `_ItemStepper` (`engine.py:756`) döndürüyor —
`step(bar)` / `finalize()` / `output()` / `open_position()` + canlı `ledger` ve `ctx`.
`run_engine` **imzasını, docstring'ini ve semantiğini koruyup** onun üzerinde dokuz satırlık bir
sürücü oldu (`engine.py:3245`). ADR §12 ADIM 16'yı SKIPPED işaretlemişti ama aynı §12 düzeltme
notu stepper'ın **worker call site'ının ön koşulu** olduğunu söylüyor: bir item'ı verilen `t`'ye
ilerletebilen replay olmadan gerçek engine ile desteklenen bir katılımcı yazılamaz.

**Kabul kriteri 46 golden digest ve başka hiçbir şey** (ADR §15 R-4) — **46/46 kımıldamadı.**
Saf refactor iddiası iki ölçüme dayanıyor: taşınan aralıklar `HEAD` ile byte-byte karşılaştırıldı
(setup 955 · step gövdesi 1351 · settlement 44 · output 15, hepsi verbatim; formatter yalnız bir
`max(...)` çağrısını topladı) ve `nonlocal` bloğu bir AST geçişiyle **ölçüldü** — bar'lar arasında
taşınan tam **on** ad (`current_day`, `exit_touch`, `funding_idx`, `pending`, `position`,
`prev_entry_signal`, `prev_scale_signal`, `scale_signal`, `working_limit`, `working_stop`); diğer
**83** ad definite-assignment ile elendi (yanlış olsaydı hata modu gürültülü `UnboundLocalError`).

**Yeni test digest'lerin göremediği yarıyı kilitliyor.** `run_engine` stepper'ı tek generator'dan
kesintisiz besliyor, yani sessizce per-bar local'a dönmüş bir taşıyıcı ad yine de kayıtlı digest'i
üretebilirdi. `tests/unit/test_backtest_engine_stepper.py` (**4 test**) aynı senaryoları **çağrı
başına bir bar**, her bar çiftinin arasında askıya alarak replay ediyor — taşıyıcı ad başına bir
vaka (duran limit, hiç dokunmayan limit, tetiklenmemiş stop, ladder'layan pozisyon, funding ödeyen
tutulan pozisyon, blackout'u aşan sinyal) + batch sınırının gözlemlenemezliği + askı boyunca
`open_position()` + ilk bar'dan önceki fail-closed `UnresolvedStrategyError`.

**Migration yok, model yok, OpenAPI yok**; `ENGINE_VERSION` bump EDİLMEDİ, containment kapalı
(`SHARED_ALLOCATION_STATUS = future_dev`), manifest policy alanı yok — üçü de ADIM 20.
**CI 8 job pass** (`Backend — lint, type, test` 44m09s); PR gövdesinde bildirilen suite 3699
passed / 4 xfailed / coverage %93.29 — **yerelde bağımsız doğrulanmadı, otorite CI'dır.**
**Dürüst sınır:** `_ItemStepper`/`_build_stepper` module-private ve `__all__`'da değil; üretimde
ikinci tüketicisi yok. Tam kayıt: `docs/PROJECT_HISTORY.md` §"ADIM 16", kickoff:
`docs/ADIM16_LANDED_KICKOFF.md`.

## Yarım-cent yuvarlama — KARARA BAĞLANDI (2026-08-06, ürün kararı), UYGULANMADI

`allocation/rules.py::_money` = `ROUND_HALF_UP`; `execution/portfolio_ledger.py::MONEY_ROUNDING`
= `ROUND_HALF_EVEN`. `1000.10 @ %25` → preview `250.03`, execution `250.025`. doc 13 §13
preview/manifest uyuşmazlığını **yasaklıyor** ama kanon kazananı seçmiyordu;
`provenance.sleeve_amount_divergences()` (`SLEEVE_AMOUNT_DIVERGENCE`) farkı yalnızca raporluyordu.

**KARAR: `initial_sleeve_capital` yeniden quantize EDİLMEZ — dondurulmuş preview'dan KOPYALANIR.**
Kaynak `PortfolioAllocationPlanRevision.derived_amounts`'ın dondurulmuş değeridir. **Hiçbir
yuvarlama sabiti değişmez:** `MONEY_ROUNDING` `ROUND_HALF_EVEN` kalır (equity/pnl digest'leri
güvende), `_money` `ROUND_HALF_UP` kalır (kullanıcının onayladığı preview kaymaz).

**Gerekçe.** Repo'nun yazılı doktrini zaten bu: tutarlar dondurulmuş revizyondan **kopyalanır,
yeniden hesaplanmaz** (`provenance.allocation_provenance_from_derived` tam olarak böyle yapar).
İki yolun ayrı hesaplayıp aynı modda anlaşması kırılgandır ve yeniden ayrışabilir; kopyalama
ayrışmayı **yapısal olarak imkânsız** kılar.

**Uygulama sınırı — kararı hayata geçiren slice'a not.**
- Dokunulacak yer `portfolio_ledger.build_sleeve_plan`'ın sleeve'i **türettiği** nokta: türetme
  yerine dondurulmuş tutarı **girdi olarak al**.
- Sonrasında `sleeve_amount_divergences()`'in anlamı değişir: divergence artık "iki yol farklı
  yuvarladı" değil **"kopyalama yolu atlandı"** demektir → rapor olmaktan çıkıp **fail-closed**
  bir değişmeze dönmesi gerekir. Bu **ayrı bir karar noktasıdır**, otomatik sonuç sayma.
- Kalan artık `U0` (`A0 - Σ Ci0`) üzerinde toplanır; kopyalanan tutarların toplamı `A0`'ı aşamaz
  — testle pinle.
- Karara bağlanmamış sizing/booking kalemlerine (#550/#551/#552) **hâlâ dokunma**; bu karar
  yalnız `initial_sleeve_capital`'ı kapsar.

---

## Next: **worker call site — `ItemParticipant` (gerçek engine) → sonra ADIM 20**
## ADIM 22 — install/upgrade/restore acceptance landed (PR #594, #601)

**Boşluk.** Kurulum zincirinin harness'ları vardı ama **kapısı yoktu**. `e2e-acceptance.sh`,
`backup.sh`, `restore.sh`, `backup-verify.sh` geliştirici komutlarıydı; **hiçbir workflow
bunları koşmuyordu** — yani bozuk bir kurulum yolu, eski bir DB'ye uygulanamayan bir migration
ve satırsız bir şemayı geri yükleyen bir backup, üçü de yeşil inebilirdi (denetim: **H-07**).

**PR #594** squash-merge `3cc9588` (+1728 / −38, 11 dosya) · **PR #601** squash-merge `e6cd2ee`
(+46 / −9, 4 dosya). **Migration YOK** (head `0043_i08_registry_strategy_fks`) · **OpenAPI
DEĞİŞMEDİ** · **`ENGINE_VERSION` DEĞİŞMEDİ**.

**Yeni:** `scripts/migration-acceptance.sh` (`make migration-accept`, Docker'sız ~30 sn, her PR)
· `scripts/dr-acceptance.sh` (`make dr-accept`) · `.github/workflows/install-acceptance.yml`
(4 job, maliyete göre bölünmüş) · `docs/INSTALL_ACCEPTANCE.md` ·
`backend/tests/integration/test_provision_concurrency.py` (6 test).
`e2e-acceptance.sh::assert_planes_healthy` listesine **`worker-agent-executor` eklendi** — o
düzlem hiç yokken §9.4 yeşil geçebiliyordu.

**Production değişikliği — provisioning eşzamanlı-güvenli DEĞİLDİ.** `apps/seed.py`'nin her
guard'ı SELECT-then-INSERT ve seed sonda tek kez commit ediyor; READ COMMITTED altında ikinci
koşu birincinin commit edilmemiş satırlarını göremiyor. **Ölçüldü:** 3 paralel koşunun **2'si**
`principals_pkey` ile exit 1 — ve `provision` one-shot her düzlemin
`service_completed_successfully` kapısı olduğu için tek bir yarışan exit-1 tüm stack'i
başlatmıyor. **Sessiz yarısı daha kötü:** unique constraint'i olmayan guard'lar (ör.
`rationale_family_revision.normalized_name`, yalnız `index=True`) hata vermeden duplike commit
ediyor — 3 eşzamanlı koşu **6 kanonik yerine 18** rationale family üretiyor, hiçbir yerde hata
yok. Çözüm yeni altyapı değil: `PROVISION_LOCK_KEY = 220_000` + `lock_provisioning()`
(transaction-scoped `pg_advisory_xact_lock`, repo'nun mevcut deyimi), sınırlı bekleme
`PROVISION_LOCK_TIMEOUT_MS` (120000, `SET LOCAL lock_timeout`; PG16'da
`pg_advisory_xact_lock`'a uygulandığı ampirik doğrulandı) → `ProvisioningLockTimeout`.
`_seed()` ikiye ayrıldı: public `provision(session, log)` + session sahibi `_seed()`.
**Her iki yarı da mutation-verified** (kilit `pass` yapılınca testler kırmızı).

**PR #601 — object storage aslında yedeklenmiyordu.** `minio/mc` imajı `ENTRYPOINT ["mc"]`
bildiriyor, yani `docker run minio/mc sh -c '...'` argümanları mc parametresi olarak
ayrıştırılıyordu ve dockerized fallback hiç çalışmıyordu. `--entrypoint sh` → `backup.sh`,
`restore.sh`, `dr-acceptance.sh`. Host'unda `mc` olan geliştiricide görünmüyordu; **`mc`'si
olmayan her makinede object storage sessizce yedeklenmiyordu.**

**CI kanıtı — Actions run 31038908690**, dört job da `success`: `fresh-install` ·
`migration-acceptance` · `legacy-upgrade` · `disaster-recovery`.
`PASS mirrored bucket 'entropia-artifacts' via dockerized mc` · `DR ACCEPTANCE OK` ·
`VERIFY OK — … (head 0043_i08_registry_strategy_fks, 105 tables)`.
**Nüans:** bu koşu `main`'de değil, `fix/backup-object-storage-on-linux`@`84d1a5e`'de
`workflow_dispatch` ile koştu (yani #601'in squash edilen içeriği). `main` üzerinde heavy
job'lar ilk kez nightly cron'da (03:17 UTC) koşacak.

**Dürüst sınırlar:** (1) **index ADLARI gate dışı** — `alembic check` yalnız index-adı sapması
+ bir server default bildiriyor; **kolon paritesi** temiz ve gate'li, `alembic check`'i kapıya
çevirmek ayrı bir temizlik. (2) Integration suite şemayı hâlâ `metadata.create_all` ile kuruyor,
yani **migration'ın yazdığı satırlar pytest'te YOK** (`alpha-agent` `agent_runtime` singleton'ı);
`migration-acceptance.sh` [4] onları migrate edilmiş DB'ye karşı ayrıca doğruluyor. (3) **DR
kanıtı sığdı** — aynı transcript `[7] all three append-only planes were EMPTY` ve `[8] 1 objects`
bastı; sebebi `apps/seed.py`'nin repository'ler üzerinden yazması (→ `_audit_and_outbox`'a hiç
ulaşmıyor) ve dört object writer'dan yalnız birini çağırması. **ADIM 23 / PR #610** bunu
kapatıyor; bu kayıt yazıldığında PR **açık**. (4) Compose job'ları ADIM 22 sırasında yerelde
koşturulamamıştı (paralel worktree portları tutuyordu) — `INSTALL_ACCEPTANCE.md`'deki **▶**
işaretleri artık **✔**. (5) PITR / off-site replikasyon / zamanlanmış backup **V1 dışı**.

## ADIM 16 (ADR §12) — `run_engine` bar döngüsü resumable stepper'a çıktı landed (PR #602)

ADR §12'nin **SKIPPED** işaretlediği ADIM 16, faz döngüsünün yerine değil **worker call
site'ının ön koşulu** olarak yazıldı (§12 düzeltme notunun birebir dediği şey). `run_engine`'in
kurulum yarısı `_build_stepper(...)` oldu → `_ItemStepper{step(bar), finalize(), output(),
open_position(), ledger, ctx}`; `run_engine` **imzasını/docstring'ini/semantiğini korudu** ve
dokuz satırlık sürücüye indi. `bar_batches` fabrikaya GEÇMEZ — bar akışını çağıran sahiplenir;
`UnresolvedStrategyError` fabrikada, ilk bardan önce atılır.

**Kabul = 46 golden digest, başka hiçbir şey** (ADR §15 R-4). **46/46 sabit.** Tam suite tek
çağrıda **3699 passed / 4 bilinen xfail / 0 failed**, coverage **%93.29** (kapı ≥%90,
`engine.py` %95.1), CI 8/8. Taşınan 2365 satırın birebirliği `HEAD`'e karşı satır satır
doğrulandı; `nonlocal` kümesi AST ile **ölçüldü** (bar'lar arası taşınan tam 10 ad), kalan 83
geçici için kesin-atama analizi yapıldı. Yeni `tests/unit/test_backtest_engine_stepper.py`
golden'ın göremediği yarıyı kilitler: aynı senaryolar **bar başına bir çağrıyla, her bar arasında
askıya alınarak** koşulduğunda digest değişmiyor.

**Kapsam dışı (bilerek):** worker'a dokunulmadı (`jobs/backtest_engine.py:298` hâlâ item
döngüsü), `ENGINE_VERSION` değişmedi, containment kapalı kaldı, migration/OpenAPI yok.
`_ItemStepper` / `_build_stepper` modül-private, `__all__`'da değil — **üretimde çağıranı yok.**
Devir: `docs/ADIM16_STEPPER_LANDED_KICKOFF.md`.

## Next: **PR B — `ItemParticipant` adaptörü + `run_portfolio` call site → sonra ADIM 20**

**Stepper indi (PR #602); kalan borç adaptör + call site.** `run_portfolio` hâlâ üretimde
**çağrısız**: `jobs/backtest_engine.py:298` item döngüsü, `:363` `combine_item_runs`,
`SHARED_ALLOCATION_STATUS = future_dev`. ADIM 20'nin matrisindeki A1/A3/A5 dışında hiçbir satır
bu boşluk kapanmadan kapanamaz.

**1. PR B — adaptör + worker call site.** Stepper üstüne `portfolio_engine.ItemParticipant`'ı
uygula (`carry` / `mandatory_exit` / `entry`) ve `jobs/backtest_engine.py:298`'deki item
döngüsünü `run_portfolio` ile değiştir — **yalnız >1 item** çalışırken; tek item `run_engine`'de
kalır (ADR §3.2). Containment guard'ını **gevşetme, yeniden yaz** (artık üretim yolu var:
assertion'lar korunur, adlar düzeltilir, importer'lar adlandırılır).

> **Bu mekanik bir ikame DEĞİL.** `ItemParticipant.entry` hazır bir `ItemIntent` ister ama
> `intents.form_intent` entry'yi item'ın kendi `StrategyConfig`/`FillCosts`'u olmadan ölçemez; ve
> stepper bir barı **bütün olarak** ilerletirken faz döngüsü aynı barı **fazlara bölünmüş**
> ister. O boşluğu kapatmak PR B'nin asıl tasarım işidir. Uydurulamayan fazı fail-closed reddet.

**Kabul:** 37 non-portfolio digest **KIMILDAMAMALI**; `portfolio.*` digest'lerinin kımıldaması
**beklenir** ve her biri tek tek gerekçelendirilir. `ENGINE_VERSION`'a dokunma, containment'ı
kaldırma (ikisi de ADIM 20).

**PR A'nın bıraktığı reuse anchor'ları — tam sembol adlarıyla:**

| ne | nerede |
|---|---|
| stepper fabrikası | `domain/backtest/engine.py::_build_stepper` |
| stepper kaydı | `engine.py::_ItemStepper` |
| bir barı ilerlet | `_ItemStepper.step(bar: _Bar) -> None` |
| gün sonu settlement | `_ItemStepper.finalize() -> None` |
| sonucu projekte et | `_ItemStepper.output() -> EngineOutput` |
| tutulan pozisyonu oku | `_ItemStepper.open_position() -> _Position \| None` |
| canlı defter / run ayarları | `_ItemStepper.ledger`, `_ItemStepper.ctx` |
| ham dict → `_Bar` | `execution/state.py::_normalize` |
| eşdeğerlik kanıtı şablonu | `tests/unit/test_backtest_engine_stepper.py` |

**ADIM 18'in bıraktığı anchor'lar (değişmedi):** `portfolio_engine.py::run_portfolio` ·
`::ItemParticipant` (Protocol) · `CarryCharges` / `MandatoryExit` · `PortfolioTick` /
`PortfolioRun` · `PHASE_ORDER` / `PORTFOLIO_LOOP_VERSION` · fail-closed reddedişler
(`InvalidParticipantError`, `MisformedIntentError`, `UnsupportedIntentKindError`,
`UnpriceableAdmissionError`) · referans katılımcı
`tests/unit/oracles/portfolio_harness.py::_ScriptedParticipant` · containment'ın kalan tek kapısı
`tests/unit/oracles/test_oracle_portfolio_containment_gate.py::test_the_phase_loop_exists_but_no_production_path_reaches_it`.

**1. Engine-destekli `ItemParticipant` — (a) BİTTİ, sırada (b).**

- **(a) Stepper ✅ landed (PR #602).** `run_engine`'in bar döngüsü `_build_stepper` /
  `_ItemStepper`'a çıktı; `run_engine` ince sürücü, imza ve semantik aynı, **46/46 digest
  kımıldamadı**. Yukarıdaki "ADIM 16 ✅ landed" bölümü.
- **(b) Adaptör + worker — AÇIK.** `_ItemStepper` üstüne `portfolio_engine.ItemParticipant`'ı
  uygulayan bir adaptör yaz (`identity` / `stream` / `instrument_id` / `carry` / `mandatory_exit` /
  `entry`; `entry` kendi `ItemIntent`'ini **`form_intent` ile kurar** — boyut item'ın kendi
  `StrategyConfig`/`FillCosts`'unu ister, faz döngüsü yalnız doğrular). Sonra
  `jobs/backtest_engine.py:298`'deki item döngüsünü `run_portfolio` ile değiştir — **yalnız >1
  item** çalışırken; tek item `run_engine`'de kalır (ADR §3.2). `open_position()` dışında replay
  içine uzanma (ADR §5). **Bu PR'da 9 `portfolio.*` digest'inin kımıldaması BEKLENİR** ve her biri
  tek tek gerekçelendirilir; **37 non-portfolio digest kımıldamamalıdır** — kabul kriteri odur.

**(a) ile (b) tek PR'da BİRLEŞTİRİLMEDİ ve birleştirilmemeli** — ADR §15 R-4'ün "restructure ile
re-price'ı ayır" kuralı ADIM 16 atlandığında bir kez kaybedildi; ikinci kez kaybedilirse
kımıldayan bir digest'i atfedecek hiçbir şey kalmaz.
**Faz döngüsünün MODELLEMEDİĞİ (dürüst sınır, `portfolio_engine.py` docstring'inde de yazılı):**
P0 (clock cursor'ı), **P2 pending fills**, **P8 same-direction scaling** — admitted bir
`scale_in` bilerek `UnsupportedIntentKindError` atar. Mark policy yok (**OD-2**): `E(t)`
realized-only.

**2. Sonra ADIM 20** (manifest policy alanları, `ENGINE_VERSION` bump, digest yenileme,
containment lift). Ön koşulları — hâlâ açık:
- **A17**: `tests/integration/test_research_point_in_time_parity.py`'de 4 `xfail(strict)`
  (#556 ×2, #557, #558). "green, unweakened" değil.
- **OD-1 / OD-2 / OD-6 kapıları KOD OLARAK YOK.** `provenance.MARK_STALENESS_POLICY` hâlâ
  `"undefined_pending_od2"`, `arbitration.CONTENTION_SELECTION_STATUS` hâlâ
  `"recommended_pending_approval"` — **ikisini de ADIM 20 çevirir** (ADR §13.1 son paragraf, R-5).
- **#544 (NET)** kanonda tanımsız · **#559 (DST)** karışık zaman dilimi öncesi.
- **A4 / A18** gerçek `EngineOutput` digest'i ister → PR B'ye bağlı. **A21** tick tabanlı cancel
  checkpoint → PR B'ye bağlı.

**Paralel yürüyebilecek, bloke etmeyen kalemler:** #550/#551/#552 (sizing/booking — **#550 karara
bağlanmadan sizing'e dokunma**), #539 (düzeltme indi, issue açık), #514 (ekran okuyucu, kanıtsız
kapatma yok), #591 (`agent_coordinator` event-loop — PR #600 ile kapandıysa doğrula).

`docs/audit/current_main_ground_truth_2026-08-03.md` §18'in 2/3/4/6 kalemleri kapandığı hâlde
belge güncellenmedi — **kullanmadan önce doğrula.**

## ADIM 25 (observability) — alerts + runbooks landed (PR #622)

**Merged `780dc92`** (branch `ops/observability-alerts-runbooks`, base `e5c650a`) · 35 dosya,
**+2885 / −13** · **migration YOK**, alembic head `0043_i08_registry_strategy_fks` değişmedi ·
`ENGINE_VERSION` değişmedi · OpenAPI değişmedi.

Stage 8b'nin `/metrics` expozisyonu hiçbir şeye bağlı değildi: repoda alert kuralı yoktu,
`docs/runbooks/` yoktu, hangi metriğin hangi soruyu yanıtladığı yazılı değildi.

**İndi:** `ops/alerts/entropia.rules.yml` (**11 alert / 5 grup**, her biri severity +
component + `for:` + **9 zorunlu anotasyon**) · `docs/runbooks/` (**13 dosya**: README,
`METRIC_ALERT_MATRIX.md`, 11 runbook) · **yeni metrik ailesi**
`entropia_worker_heartbeat_age_seconds` (`system_heartbeat` artık round-trip'i
`application/jobs/heartbeat.py::record_worker_heartbeat` ile `app_metadata`'ya upsert ediyor,
`key="worker.maintenance.last_heartbeat_at"`; **tablo zaten mapped'di → migration gerekmedi**) ·
frontend System Metrics sayfası heartbeat yokken **"never recorded"** basıyor.

**Kritik semantik:** kayıt yoksa route `# TYPE` satırını basar ama **örnek satırı basmaz**
(0.0'a çökmez) → seri gerçekten absent olur ve `absent()` alert'i çalışır.

**İki gerçek kusur bulundu ve düzeltildi:** (a) `method` label'ı **sınırsızdı** (`path` route
template'e sıkıştırılmışken `request.method` verbatim geçiyordu; gerçek app'e karşı 6 uydurma
metot → 6 seri) → `hardening.py::_bounded_method` + `_KNOWN_METHODS`, tavan **8**. (b)
`up{...} == 1 and absent(...)` **hiç ateşlenemezdi** (`absent()` etiketsiz eleman döndürür, `and`
tüm etiket kümesini eşleştirir → boş vektör); **iki paging alert'i ölüydü** → `and on()` +
regresyon testi.

**Adjudicated:** `docs/performance/README.md:144` p95 satırını *"deliberately blank rather than
guessed"* bıraktığı için **hiçbir alert mutlak latency/throughput hedefi uydurmaz**. Tek latency
sınırı `le="5.0"` (histogram'ın zaten sevk edilmiş en büyük bucket'ı); `in_flight` için alert
yok. Diğer eşikler shipped default'ların katı (6x/10x/60x `SCHEDULER_TICK_SECONDS`, 2x
`JOB_STALE_AFTER_SECONDS`, 2x `JOB_REDELIVER_GRACE_SECONDS`), `test_alert_rules_contract.py`
içinde `get_settings()`'e karşı makineyle pinli.

**Ölçümler:** backend **3912 passed / 1 xfailed / 0 failed**, exit 0, coverage **%93.52**,
22dk38s · frontend **721 passed / 70 dosya**, **%84.92 line** · ruff + format + mypy (396 dosya)
temiz · `make openapi-check` temiz. `pyyaml>=6.0,<7.0` dev extras'a eklendi.
Codemap'ler **PR #622 içinde** güncellendi (ROUTES / LAYERS / DATA_MODEL / JOBS_AND_EVENTS).

**Dürüst sınırlar:** PromQL **anlamsal olarak doğrulanmıyor** (`promtool` yok, CI'da yok,
`prometheus.yml` yok; contract testi elle yazılmış tokenizer — (b) kusurunu **insan review'ı**
yakaladı, kapı değil) · `job="entropia-api"` scrape adını **hiçbir şey zorlamıyor** · heartbeat
**yalnız `maintenance` kuyruğunu** kanıtlar (ölü `worker-backtest` onu taze bırakır) ·
**metriği olmayan alanlar** (matris §4 kör nokta haritası): backtest içi, agent coordinator, SSE,
object storage, backup age, DB pool utilization · `correlation_id` **worker log'larına
ulaşmıyor** · structlog **redaction processor'ü yok** · `EntropiaQueueNeverDrains` "hiç
boşalmadı" **demez** (boşalan kuyruk seri üretmez, `min_over_time` boşlukları atlar).

**Numaralandırma borcu (dürüst not):** **ADIM 23 = #610** ve **ADIM 24 = #619** main'e indi ama
`PROJECT_HISTORY.md`'de **kayıtları yok** (#620/#621/#614 de kayıtsız). Bu slice'ta kapatılmadı.

**Tam kayıt:** `docs/PROJECT_HISTORY.md` § *ADIM 25 (observability)*.
**Devir:** `docs/ADIM26_KICKOFF.md`.

## ADIM 26 (observability) — alert kuralları promtool kapısına bağlandı (PR #624, **AÇIK**)

> **Merge EDİLMEDİ.** Bu satır yazıldığında #624 açıktı; "landed" demiyorum.
> Yeni oturumda **önce** `gh pr view 624 --json state,mergedAt`.

**Branch `ci/promtool-alert-rules-gate`**, base `708ec07`, commit'ler `ed2d387` + `68313ad`
· 8 dosya, **+618 / −10** (+ permission fix) · **migration YOK**, alembic head
`0043_i08_registry_strategy_fks` değişmedi · OpenAPI değişmedi · **frontend etkilenmedi**.

ADIM 25'in bilerek açık bıraktığı TEK boşluk kapandı: 11 alert kuralı artık **gerçek bir
PromQL motoruyla değerlendiriliyor**, sadece tokenize edilmiyor. Yeni bloklayıcı CI job
`Alert rules — promtool` (`scripts/alert-rules-gate.sh`) — `check config` → `check rules`
→ `test rules`, digest-pinned `prom/prometheus@sha256:63805ebb…` (v3.5.0 LTS). Paralel
koşar, eklenen wall-clock **0** (CI'da 14 sn). Yeni `ops/prometheus/prometheus.yml`
`job="entropia-api"`'yi kontrol edilebilir olguya çevirir; `ops/alerts/entropia.rules.test.yml`
15 unit-test case'i taşır; `test_alert_rules_contract.py`'ye 5 yeni test.

**11 alert'in ANLAMI değişmedi** — kural dosyası diff'i yalnızca yorum satırları.
Latency SLO uydurulmadı. Tam suite **3917 passed / 1 xfailed / 0 failed**, exit **0**,
coverage **%93.52**.

**İki ders, tekrarlanmasın:** (1) `alert_rule_test` anotasyonları TAM karşılaştırır →
assertion'lar sentetik `ALERTS{...}` serisi üzerinde yazıldı, aksi halde 9 anotasyon
her alert için kopyalanır ve sapma "geçen test" gibi görünürdü. (2) Kapı **yerelde
yeşil, CI'da kırmızıydı**: `mktemp -d` 0700 üretir, Prometheus imajı `nobody` (uid
65534) koşar → `permission denied`; **macOS bunu tamamen gizler**, hata yerelde
üretilemedi. Fix: `chmod -R a+rX "$workdir"`, placeholder token'dan SONRA.

**Açık kalan (bilerek):** Alertmanager YOK → kurallar doğru ateşliyor ama **kimseye
ulaşmıyor**; `severity: page` hiçbir alıcının okumadığı bir etiket.
**Devir:** `docs/ADIM26_LANDED_KICKOFF.md` (artık `historical`; güncel devir
`docs/ADIM27_LANDED_KICKOFF.md`). Tam kayıt: `PROJECT_HISTORY.md`.
**Sonradan doğrulandı:** #624 ve #625 merge edildi (`c859f1c`, `7a9be2d`).

## ADIM 27 — documentation-truth CI landed (PR #626)

**Branch `ci/documentation-truth-guard`**, base `7a9be2d`, merge `0e67e9d`
· 86 dosya, **+2665 / −29** · **migration YOK**, alembic head
`0043_i08_registry_strategy_fks` değişmedi · **yeni tablo YOK** · OpenAPI değişmedi ·
`ENGINE_VERSION` değişmedi · `SHARED_ALLOCATION_STATUS` = `future_dev` (containment KAPALI)
· yeni endpoint / sayfa / job **YOK** · **frontend etkilenmedi**.

Belgelerin ileri sürdüğü olgular artık **çalışma ağacından üretiliyor** ve CI'da
karşılaştırılıyor. `scripts/generate_repository_facts.py` (873 satır, bağımlılıksız)
on olgu ailesini toplar → `docs/generated/repository_facts.{json,md}` + `README.md`
içindeki `<!-- BEGIN/END GENERATED: repository-facts -->` bloğu. Backend job'una yeni
bloklayıcı adım **`Documentation truth gate (generated repository facts)`** eklendi,
OpenAPI drift guard'ından **SONRA** (route olguları o adımın şemasından okunur).

`--check` üç şeyi birden reddeder: (1) üç artefakttan biri bayatsa
(`check_artifacts`), (2) kickoff/audit/history belgesi `doc-status` işareti taşımıyorsa
**veya** birden fazla belge `current` iddia ediyorsa **veya** bir history/audit kaydı
`current` işaretliyse (`check_classification`), (3) güncel bir belge ağacın yalanladığı
alembic head / `ENGINE_VERSION` / `SHARED_ALLOCATION_STATUS` söylüyorsa ya da
`INVARIANT_RULES`'un beş yasak eşitlemesinden birini kuruyorsa (`check_assertions`).

77 belge `doc-status` işareti aldı — 76 `historical` + 1 `current`; #626'daki dokunuşların
**tamamı saf eklemeydi** (76×+6/−0, 1×+4/−0, **sıfır silme**). `docs/CODEMAPS/README.md`
ve `DATA_MODEL.md` elle sayılan olgu tablolarını bıraktı: aynı tablo toplamı birinde 102,
diğerinde 104 yazıyordu — **gerçek 104**. `CLAUDE.md` §Current position "sayısal otorite bu
blok değil" pointer'ı aldı.

**Testler:** `backend/tests/contract/test_repository_facts_guard.py` — **28 case**
(16 `def test_`, kalanı parametrize genişlemesi). Ölçülmüş sayılar için elle rakam
yazılmıyor: otorite **`docs/generated/repository_facts.md`** (tablo/FK/HTTP/route/nav/
capability/test **collection**/acceptance/görsel/sapma). Kapanış öncesi ölçüm: tam backend
suite **3945 passed / 1 xfailed / 0 failed**, exit **0**, coverage **%93.52** (kapı ≥90).

**Açık sınırlar (yumuşatılmadı):**
* **Kapı `0e67e9d` için main'de HİÇ KOŞMADI.** 2026-08-06 16:00–17:00 arasında GitHub
  Actions arızası vardı (`Set up job` → `Failed to resolve action download info. Error:
  Service Unavailable`); `7a9be2d` main run'ı bu yüzden kırmızı ve `0e67e9d` için main'de
  run oluşmadı. `ci.yml` `workflow_dispatch` **taşımıyor** → main'de elle tetiklenemez.
  Adımın ilk gerçek koşusu bu kapanış PR'ıdır.
* **Kapsam dışı (bilerek):** commit sha, timestamp, GitHub durumu (açık PR/issue),
  test **PASS** sayısı. Her test sayısı bir *collection* sayısıdır ve adı bunu söyler.
* **İki olgu hâlâ elle sayılı ve kapı onları KORUMUYOR:** audit `event_kind` 126 literal,
  frontend 31 sayfa / 40 `lib/*.ts`.
* Üretici `entropia`'yı import eder → yalnız backend venv'inde koşar; salt-docs katkıcısı
  artefaktı yeniden üretemez.
* `INVARIANT_RULES` **regex tabanlıdır** — aynı yalanı farklı cümleyle yazan metni kaçırır.
  **Tripwire, kanıt değil.**
* Docs regresyonu bu repoda **üç kez** oldu (#590, #604). Kapı sınıflandırmayı görür,
  **silmeyi görmez** — merge öncesi hâlâ elle: `git show <sha> -- docs/ | grep '^-## '`.
* **Alertmanager YOK** (ADIM 25/26'dan devralınan sınır) → kurallar ateşliyor ama kimseye
  ulaşmıyor. **`PROJECT_HISTORY.md`'de ADIM 23 ve ADIM 24 hâlâ KAYITSIZ.**
* Ekran okuyucu (NVDA/VoiceOver) denetimi **YAPILMADI** — GitHub #514 açık.
  **D-10** imzalı kalıcı kontrast sapması: WCAG 2.2 AA 1.4.3 karşılanmıyor.

**Devir:** `docs/ADIM27_LANDED_KICKOFF.md`. Tam kayıt: `PROJECT_HISTORY.md`.

## ADIM 28 — A-08 audit preparation landed (PR #628)

**Branch `a11y/a08-human-audit-preparation`**, base `81336e1`, merge `20e942b`
· 9 dosya, **+1762 / −8** · **migration YOK**, alembic head
`0043_i08_registry_strategy_fks` değişmedi · **yeni tablo YOK** · OpenAPI değişmedi ·
`ENGINE_VERSION` değişmedi · `SHARED_ALLOCATION_STATUS` = `future_dev` (containment KAPALI)
· yeni endpoint / sayfa / job **YOK** · codemap değişmedi · `.github/workflows/` **hiç
dokunulmadı**. Aynı dalganın unblocker'ı **PR #629** (merge `81336e1`, 1 dosya +6/−0).

GitHub **#514** 2026-07-30'dan beri açıktı ve issue ile denetmen arasında duran tek şey
düzyazıydı. Bu slice **iskeleyi** kurar; **denetimi YAPMAZ**.

**`scripts/a11y-audit-stack.sh`** — `up | validate | status | down`. Compose projesi her
zaman `entropia-a11y-audit` (`down` başkasını reddeder), hermetik git-ignored
`.env.a11y-audit`, tek düğme **`A11Y_HOST`** (`0.0.0.0` → hard error: o bir bind adresidir,
tarayıcının açacağı adres değil). Teardown **EXIT trap DEĞİL**, açık alt komut — tüketici
oturumun ortasındaki bir insan. `validate` beş adımda **9/9** geçiyor: session profili
(`/meta.auth_mode=session`), Admin oturumu (`/me.is_admin=true`), `SEED_E2E_GOLDEN` +
`SEED_ESP_TA` + `SEED_RATIONALE` gerçekten satır üretiyor, 23 rotanın hepsi servis ediliyor.
Amaç: kimse bir NVDA oturumunu ürün sebebiyle değil **seeding sebebiyle** boş sayfalarda
harcamasın.

**`docs/audit/a11y_screen_reader_audit_results.md`** — 23 rota × 2 kombinasyon + 10 akış × 2,
**16 kolonlu** bulgu defteri + kolon sözleşmesi, §4 retest listesi, §5 çıkış kriterleri,
§6 otomasyonun ne ölçtüğü + **K-1..K-6**. Rota satırları `screenshotMatrix.ts::TARGET_PAGES`'ten
üretildi (axe taramasının yürüdüğü aynı matris). `doc-status: historical` — kapı
`docs/audit/*.md` için bunu zorunlu kılıyor; belge bu gerilimi ilk paragrafında açıkça söylüyor.

**`.github/ISSUE_TEMPLATE/a11y_screen_reader_finding.yml`** — her kolon için bir alan +
**ZORUNLU "duydum" beyanı** (ekran-okuyucu bulgusunu DOM çıkarımından ayıran tek şey) +
retest checkbox'ları. `accessibility` ve `a11y-screen-reader` label'ları bu dalgada AÇILDI.

**`frontend/e2e/specs/20-a11y-prechecks.spec.ts`** — `@a11y` etiketli, `npm run a11y`
(= `playwright test --grep @a11y`) onu **otomatik alır**; workflow'a tek satır eklenmedi.
**BLOCKING:** tek `<h1>`den fazlası yok, tek `main`, `banner` + adlandırılmış `navigation`,
dialog adı + Escape + odak geri dönüşü. **ADVISORY:** skip link, `contentinfo`, başlık
atlaması, positive `tabindex`, `aria-live` envanteri, focus indicator, tab order. Ayrım
gerekçeli — bir advisory'nin düzeltmesi bir **ürün kararıdır**, kırmızı kapı o kararı
ihmalle vermiş olurdu. Her kayıt `screen_reader_verified: false`. Rapor
`a11y-report/precheck-results.json` `.gitignore`'da (yerel çıktı kanıt gibi görünmesin),
CI artifact olarak yükleniyor.

**Testler:** `backend/tests/contract/test_a11y_audit_prep_contract.py` — **21 test**
(20 `def test_` + parametrize genişlemesi). Rotaları `TARGET_PAGES`'e, akışları checklist'e,
script'in seed bayrakları + rota listesini **ikisine birden**, defterin completion
sayaçlarını **kendi hücrelerine** pinler; üç mutasyon testiyle ısırdığı doğrulandı.

**PR #629 — js-yaml `!!omap` (GHSA-5p4m-2wfm-xmqj / CVE-2026-59870) gerekçeyle donduruldu.**
`npm audit` kapısı hiçbir bağımlılığa dokunmayan PR'larda bile kırmızıydı. Zincir
`eslint@9 → @eslint/eslintrc → js-yaml@4.3.0`: devDependency, bundle'a girmiyor; açık kod
eslintrc'nin YAML config yükleyicisi ve eline hiçbir şey verilmiyor (proje flat-config,
repoda **hiçbir türde `.eslintrc` yok**). Kayda iki bitiş koşulu yazıldı: eslint 9.x yamalı
js-yaml'a geçtiğinde **veya** repo bir `.eslintrc.y(a)ml` kazandığında.

**Ölçümler:** sayısal otorite `docs/generated/repository_facts.md`. Bu dalganın deltası:
backend **collected** 3395 → **3415** (328 → 329 dosya), E2E **call site** 73 → **81**
(20 → 21 spec) — *collection* sayılarıdır, pass değil. Koşular: backend tam suite exit **0**,
**0 failed**, coverage **%93.52** (kapı ≥90); frontend **721 passed / 70 dosya**, **%84.92**
line; `npm run a11y` (`CI=true`) exit **0**; CI'da **"A11Y — axe-core scan"** PASS.

**Açık sınırlar (yumuşatılmadı):**
* **A-08 denetimi YAPILMADI.** Defter **BOŞ** (`*(none recorded — audit not run)*`), §5'in
  dört çıkış kriteri de **☐** (`0 / 2` kombinasyon, `0 / 46` rota, `0 / 20` akış).
  **Boş şablon kanıt değildir** — hiçbir belge A-08'i `Complete`/`PASS` gösteremez.
* **K-2..K-6 ÖLÇÜLDÜ, DÜZELTİLMEDİ** (her biri bir ürün kararı; precheck koşusu: 23 rota,
  **0 blocking failure, 85 advisory**): skip link yok **23/23** · `contentinfo` yok **23/23**
  · `h1 → h3` atlaması **21/23** · `/user-manual`'da `<h1>` yok (`UserManual.tsx:181`; sapma
  `frontend/e2e/utils/pageTruth.ts:15`'te zaten kayıtlı) · focus indicator computed-style'da
  görünmüyor — **yalnız insan gözü karar verebilir**.
* **D-10 sürüyor:** 45 aksan-mavisi düğüm, WCAG 2.2 AA **1.4.3 KARŞILANMIYOR**; bu slice
  hiçbir AA iddiası getirmiyor.
* **ÖNCEDEN VAR OLAN iki kararsızlık** (bu slice'tan değil): `14-keyboard-flow` 4 koşudan
  1'inde autofocus yarışında düştü; `13-a11y-scan` ilk denemede **gerçek** bir ratchet
  ihlali verdi (`arrange-metrics`: `color-contrast` 4 düğüm, baseline 2), retry'da 2 ölçtü —
  o sayfayı yeşil tutan şu an `playwright.config.ts:22`'deki `retries: CI ? 1 : 0`.
* **GitHub #514 sahibi tarafından 2026-08-07T03:52Z'de KAPATILDI** (`completed`), denetim
  kanıtı olmadan ve her iki dalga commit'inden de **önce**. Olgu olarak kaydedildi;
  A-08 bununla tamamlanmış **değildir**. Ayrışmanın düzeltilmesi **ayrı bir slice**.
* Kapanış ritüelinin **4. maddesi (memory checkpoint) yine YAPILAMADI** — ecc knowledge graph
  ve `claude-mem` bu oturumda bağlı değildi (ADIM 27 ile aynı sebep).
* Devralınan: **Alertmanager YOK** · **ADIM 23 / ADIM 24 `PROJECT_HISTORY.md`'de KAYITSIZ** ·
  documentation-truth kapısı **silmeyi görmez** → merge öncesi elle
  `git show <sha> -- docs/ | grep '^-## '`.

**Devir:** `docs/ADIM28_LANDED_KICKOFF.md`. Tam kayıt: `PROJECT_HISTORY.md` §ADIM 28.

## ADIM 29 — A-08 kayıt uzlaştırması landed (PR #631)

**Docs-only.** Migration yok, alembic head değişmedi, `ENGINE_VERSION` değişmedi, ürün kodu
ve test **davranışı** değişmedi.

**Tetikleyen olgu.** GitHub **#514** (`human-only`) `2026-08-07T03:52:03Z`'de
`state_reason: completed` ile **kanıtsız kapatıldı** — **ikinci kez** (ilki
`2026-07-30T19:05:32Z`, 2026-08-03'te geri alınmıştı; **bu geri alınmadı**). Denetim yine
koşulmadı: defter boş, dört çıkış kriteri de ☐, findings register'da tek kayıt yok.

> **ADIM 48 düzeltmesi (2026-08-12).** Bu paragrafın *"bu geri alınmadı"* parantezi artık
> **bayattır**: ikinci kapatma da `2026-08-12T11:08:58Z`'de geri alındı. Aşağıdaki ADIM 29
> kaydı olduğu gibi durur — yazıldığı gün doğruydu; ayrışmanın kapanışı ADIM 48'dedir.

**Sorun.** *"A-08 açık issue #514'te izleniyor"* iddiası **BAYAT** (issue kapalı);
*"A-08 tamamlandı"* iddiası ise **yanlış** — denetim yapılmadı. İkisi de yazılamazdı.

**Karar — ayrışma ÇÖZÜLMEDİ, KAYDEDİLDİ.** Belgeler niyeti hükme bağlamaz, olguyu kaydeder
ve **iki insan çözüm yolunu da açık listeler**: **(A)** D-10 biçiminde imzalı kalıcı sapma
— *imzalayan verilmediği için YAZILMADI*; **(B)** #514'ün **insan eliyle** yeniden açılması
— *agent issue durumunu değiştiremez*. Hiçbir okuma altında A-08 tamamlanmış **değildir**.

**Kanonik kayıt tek yerde:** `docs/audit/a11y_screen_reader_audit_results.md` §STATUS ▸
*Tracking-issue state — closure/evidence divergence*. Yedi belge + bir script mesajı oraya
**işaret eder**, olguyu tekrarlamaz.

**Doğrulama:** `test_a11y_audit_prep_contract.py` + `test_repository_facts_guard.py`
(`--no-cov`) yeşil; `generate_repository_facts.py --root .. --check` → *documentation-truth
gate OK*; `git show <sha> -- docs/ | grep '^-## '` **boş** (kayıt silme yok).

**Sınırlar (dürüst):** A-08 **YAPILMADI** ve **izlemesi kapalı** — iş açık, izleme kapalı;
çözüm insana düşer · D-10 sürüyor, **WCAG 2.2 AA 1.4.3 karşılanmıyor** · K-2..K-6 ölçüldü,
düzeltilmedi · **Alertmanager YOK** · **ADIM 23 / ADIM 24 `PROJECT_HISTORY.md`'de hâlâ
KAYITSIZ** · **memory checkpoint yine YAPILAMADI** (ecc graph ve `claude-mem` bağlı değildi).

**Devir:** `docs/ADIM29_LANDED_KICKOFF.md` (`current`; ADIM 28 `historical`'a çevrildi).
Tam kayıt: `PROJECT_HISTORY.md` §ADIM 29.

## ADIM 29 (RC verification) — V18 RC kanıt dalgası landed (PR #632–#636; #637 AÇIK)

> **Ad çakışması:** bu, yukarıdaki *"ADIM 29 — A-08 kayıt uzlaştırması landed (PR #631)"*
> ile **aynı numarayı** taşır ama **ayrı iştir**. Ayrım başlık ekiyle:
> **`ADIM 29 (A-08 kaydı)`** = #631 · **`ADIM 29 (RC verification)`** = bu dalga.

**Migration yok**, alembic head `0043_i08_registry_strategy_fks` değişmedi,
`ENGINE_VERSION` değişmedi, `SHARED_ALLOCATION_STATUS` = `future_dev`.

| Adım | Konu | PR | Karar |
|---|---|---|---|
| P1 | repository truth + kanıt iskelesi | #632 | PASS |
| P3 | frontend kapıları | #633 | PASS |
| P12 | A-08 insan kabul kapısı | #634 | **BLOCKED** |
| P4 | migration + şema kanıtı | #635 | bulgu: `alembic check` **RED** |
| P9 | güvenlik kapıları | #636 | **BLOCKED** (B1 + B2) |
| **P9-B1** | js-yaml freeze düzeltmesi | **#637** | **AÇIK — merge bekliyor** |

Kanıt dizini: `docs/releases/evidence/2026-08-07/`.

### P9-B1 (PR #637) — bu dalganın TEK kod değişikliği

js-yaml freeze'inin gerekçesi *"no lockfile-only remedy … the published fix path is
eslint@10"* diyordu; **doğduğunda yanlıştı** — js-yaml `4.3.1` **2026-07-31**'de yayımlandı,
freeze **2026-08-07**'de indi. `npm audit fix --package-lock-only` → `4.3.0`→`4.3.1`,
3 satırlık lockfile diff, `package.json` byte-identical; gate girdisi **düşürüldü**.
Doğrulama: gate exit 0, `npm ci` exit 0, lint/typecheck/build exit 0, vitest **721/70**.

**B2 KAPANMADI** — react-router freeze'i **imzasız**. Yalnız iki bayat olgu düzeltildi
(pin **7.18.2** exact, yamalı hat **8.3.0+**). `.github/security-allowlist.json`'a taşımak
**adı verilmiş `owner`** ister; **imzalayan verilmediği için sapma kaydı YAZILMADI**.

### Devam eden oturumun ilk işi — sırayla

1. **PR #637'yi merge et** (self-merge kapalı; `gh pr checks 637` yeşilse insan merge eder).
2. **P5 kanıtını KURTAR.** `entropia-v18-docker-auth-validation-52e446` worktree'sinde
   `docs/releases/evidence/2026-08-07/P5_docker_auth.md` + `p5_logs/` **untracked** duruyor;
   karar **PARTIAL — 1/4 PASS, 3/4 BLOCKED** (yerel Docker daemon kilitlendi; ürün kusuru
   değil). **`git clean` bu kanıtı yok eder.**
3. **P1..P13 tanımını repoya yaz.** Ayrıştırma **hiçbir repo belgesinde yok**, yalnız sohbet
   transkriptinde. Repodaki tek üst otorite
   `docs/spec/Entropia_V18_Nihai_29_Adimli_Claude_Opus_5_Prompt_Paketi.md` §ADIM 29'un
   15 zorunlu kalemi. Bu boşluk dalganın devredilebilirliğini kırıyor.
4. Kalan adımlar: **P2, P6, P7, P8, P10, P11** → sonra **P13** (RC readiness raporu + PR).

### Kaydedilen, onarılmayan iki kusur

* **`alembic check` RED** (P4) — 40 index-name divergence + 1 redundant index; **hiçbir CI
  workflow'u `alembic check` koşmuyor**, yani sapma kapıya bağlı değil.
* **`ci.yml` concurrency** — yorumu *"never on main: every push to main must run to
  completion"* diyor ama GitHub bir grupta **tek** pending koşu tutar; yeni koşu öncekini
  **iptal eder**. Sonuç: `e8d1d48` (#633) ve `bc59dae` (#634) **0 job ile cancelled** —
  iki merge edilmiş commit'in CI'ı **hiç koşmadı**. Düzeltmesi bir CI politika kararıdır.

---

## ADIM 30 — RC Blocker 2 kabul akışı harness kapsamı landed (PR #647)

**Tip:** harness/test. **Ürün kodu değişmedi**, migration yok, lockfile değişmedi,
`ENGINE_VERSION` sabit, `SHARED_ALLOCATION_STATUS` = `future_dev` (containment KAPALI).

**Ne indi.** `scripts/e2e-acceptance.sh`'e beşinci alt-komut **`flows`** eklendi; gövdesi
**`scripts/lib/acceptance-flows.sh`** (YENİ, 625 satır). Yeni harness icat edilmedi —
izolasyon sözleşmesi, hermetik env, `dc`/`req` ve PASS/FAIL sayacı aynen yeniden kullanıldı.
Proje `entropia-e2e-flows`, port bloğu 18030/18110/15462/16409/19030/19031.

**Reuse anchor'ları (tam sembol adlarıyla) — bir sonraki slice buradan devam eder:**

| Sembol / dosya | Ne yapar |
|---|---|
| `scripts/lib/acceptance-flows.sh::af_run_all_flows` | beş akışın sürücüsü |
| `..::af_bootstrap_actors` | Admin + **plain USER** token'ı (tavizsiz kural 3'ün dayanağı) |
| `..::af_flow_a_strategy_run` · `af_follow_run` | readiness OCC, Run≠Result, durable run takibi |
| `..::af_flow_b_library_validation` | katalog, head-match, USER 403 |
| `..::af_flow_c_esp_lifecycle_export` | ESP create/validate/registry OCC/trust gate + export zarfı |
| `..::af_flow_d_agent_signal_tools` | TS≠Package, K-07 fail-closed, agent yüzeyleri |
| `..::af_flow_e_trash_lifecycle` | O-12 dual-token 409, **restore** ayağı, O-30 purge gövdesi |
| `..::af_browser_layer` | var olan spec 05/18/20-library/06'yı **koşar** (yeniden yazmaz) |
| `..::af_skip` | SKIP kendi sayacında — PASS'e asla katılmaz |
| `scripts/e2e-acceptance.sh::flow_acceptance` | yığını kaldırır, tohumlar, `E2E_KEEP_UP=1` destekler |

**Ölçüm (2026-08-10):** `flows` → **60 passed / 0 failed / 2 skipped**, exit 0; tarayıcı
katmanı **5 passed**. P5'in bloke kalemleri de koşuldu: session **27/0**, legacy **15/0**,
dev-auth **9/0**, `acceptance.sh` **exit 0** (15 servis), `smoke.sh` **exit 0**,
`worker-restart-smoke.sh` **exit 0** (mükerrer artefakt yok). Kanıt:
`docs/releases/evidence/2026-08-10/`.

**İki ölçülmüş harness tuzağı (tekrarlama):** (1) izole yığında **`API_CORS_ORIGINS` şart** —
web origin allowlist'te değilse her tarayıcı yolculuğu düşer, ama curl (Origin göndermez)
aynı API'yi sağlıklı raporlar. (2) `E2E_API_BASE_URL` **`E2E_BASE_URL` kadar yük taşır** —
sunucu gerçeğini assert eden spec'ler API'ye doğrudan gider ve `:8000`'e düşer.

**Deferred / dürüst sınır:** **`flows` bir CI kapısı değildir** — hiçbir workflow onu koşmaz,
sunucu katmanındaki regresyon sessizce geri gelebilir. Bunu kapıya bağlamak (CI'da ikinci bir
12 konteynerlik yığın + süre) **insan kararıdır**, bu slice'ta bilerek yapılmadı. Ayrıca iki
SKIP açık iştir: pozitif ESP activate→deprecate (test vektörü gerekiyor) ve Tool Gateway
çağrı günlüğü (taze yığında agent task yok). **RC verdict'i BLOCKED kalır; §6.2 "kısmen
kapandı" der.** Tam kayıt: `docs/PROJECT_HISTORY.md` §ADIM 30.

---

## ADIM 31 — RC Blocker 3: fail-closed bildirim yolu landed (PR #649)

**Tip:** ops/CI. **`backend/src` ve `frontend/` DEĞİŞMEDİ**, migration yok, lockfile
değişmedi, `ENGINE_VERSION` sabit, `SHARED_ALLOCATION_STATUS` = `future_dev`.

**Ne indi.** ADIM 25/26 alarm kuralları **doğru**ydu ama **kimseye ulaşmıyordu** — 11 kural,
7'si `severity: page`, sıfır receiver. RC raporu §6.3 bunu blocker sayıyordu. Kapanış **(A)**
seçildi (sevk), **(B) imzalı sapma değil**: eksik olan bir on-call *organizasyonu* değil,
bildirim *yolunun kendisiydi*.

**Reuse anchor'ları (tam sembol/dosya adlarıyla):**

| Sembol / dosya | Ne yapar |
|---|---|
| `ops/alertmanager/alertmanager.yml` | routing ağacı — `page` → `entropia-page` (repeat 1h), `ticket` → `entropia-ticket` (repeat 12h), **kök receiver GERÇEK** (eşleşmeyen alarm page eder), 3 aşağı-yönlü inhibit |
| `ops/alertmanager/entrypoint.sh::require_url` | **FAIL-CLOSED seam.** `ALERTMANAGER_NOTIFY_URL` unset/boş/http(s) değilse **exit 78**, Alertmanager başlamaz |
| `ops/prometheus/entrypoint.sh` | `ENTROPIA_METRICS_TOKEN` zorunlu + config'i **`cp -R` ile birebir** stage eder (şablonlama provenance hash'ini kırardı) |
| `ops/prometheus/prometheus.yml` → `alerting:` | ateşleyen alarmı Alertmanager'a verir |
| `docker-compose.yml` `prometheus` / `alertmanager` | **`profiles: ["observability"]`** — düz `docker compose up` etkilenmez |
| `scripts/alert-notification-gate.sh` | CI: `amtool check-config` + **`amtool config routes test`** (page/ticket/etiketsiz üç çözümleme) |
| `scripts/alert-notification-proof.sh` | 4 faz uçtan uca; **CI kapısı DEĞİL** |
| `backend/tests/contract/test_alert_notification_contract.py` | 21 yapısal test |
| `ops/alertmanager/notification_catcher.py` + `docker-compose.proof.yml` | test receiver, yalnız proof overlay'inde |
| `docs/runbooks/alert-notification.md` | yol + silence + **§5 beş açık artık** |

**Ölçüm (2026-08-10):** promtool **exit 0** (11 kural) · amtool gate **exit 0** · contract
**79 passed** (21 yeni + 58 mevcut) · backend tam suite **3987 passed / 1 xfailed / 0 failed**,
coverage **%93.53** · ruff/format/mypy/repository-facts **exit 0** · proof **exit 0** — faz 1 boş hedefte **exit 78**, faz 3 sha256 üçlü eşleşme
(`f1c1949c…`) + `--config.file` + 11=11 kural, faz 4 gerçek `EntropiaApiDown` alıcıya
**`entropia-page` / `severity=page`** olarak ulaştı. Kanıt:
`docs/releases/evidence/2026-08-10/P10B_alert_notification_path.md`.

**Üç ölçülmüş tuzak (tekrarlama):**
1. **`GET /api/v1/status/config` byte-diff'i ASLA geçmez** — Prometheus config'i
   *marshalled* döndürür (`scrape_protocols`, `runtime.gogc` enjekte, yorumlar silinir).
   İlk provenance kapısı bu yüzden kırmızı verdi. Zincir: sha256 + `--config.file` + parse.
2. **`amtool check-config`, notifier config'i OLMAYAN bir receiver'a SUCCESS döner** (v0.28.1'de
   ölçüldü). "Placeholder receiver" tam olarak bu şekildir — contract testi onu reddeder.
3. **`docker compose logs | grep -q` `pipefail` altında tuzaktır** — grep ilk eşleşmede çıkar,
   docker SIGPIPE alır, pipeline başarısız görünür. Gerçekleşmiş bir teslimat "gelmedi" diye
   okundu (exit 255). Log'u **önce dosyaya yaz**, sonra grep'le.

**Neden `${VAR:?...}` kullanılmadı:** compose'un zorunlu-değişken işareti **tüm dosyanın**
interpolation'ını iptal eder → profil kapalı olsa bile repo'daki her `docker compose up`
kırılırdı. Ret konteynerin **içinde** yaşıyor.

**Deferred / dürüst sınır:** §6.3'ün **BİRİNCİ** doğrulanmamış noktası **KAPANMADI** —
kurallar gerçek production serilerine karşı hiç değerlendirilmedi (yalnız sentetik seri +
tek yapısal `up == 0`). Bu repo içinde kapatılamaz; **imzalı sapma DEĞİLDİR**. Ayrıca
**delivery proof'u bir CI kapısı değil** (P10-B3), **monitörü izleyen yok** (P10-B4),
**on-call rotasyonu/ack yok** (P10-B5). **RC verdict'i BLOCKED kalır**; blocker sayısı
**4 → 3** (1, 2, 4 açık). Tam kayıt: `docs/PROJECT_HISTORY.md` §ADIM 31.

---

## ADIM 32 — RC §6.7 / P9-F2: SPA origin'inde CSP landed (PR #655)

**Tip:** güvenlik / sunum-katmanı başlık işi. **`backend/src` ve `frontend/src`
DEĞİŞMEDİ**, migration yok, lockfile değişmedi, `ENGINE_VERSION` sabit,
`SHARED_ALLOCATION_STATUS` = `future_dev`. Route path, react-query key, OCC token,
Idempotency-Key, hook, SSE taksonomisi, `lib/*.ts` **hiç dokunulmadı**.

**Ne indi.** Yürütülebilir bundle'ı sunan origin'in **CSP'si yoktu** — API'ninki vardı ve
canlı yanıt üzerinde testliydi, statik origin'inki yoktu. İddia `f3986fa` üzerinde yeniden
ölçülüp doğrulandı (`grep -rn 'Content-Security-Policy' frontend/` → boş). Üç parça indi:

1. **Politika** — `frontend/nginx-security-headers.conf`: `default-src 'none'` tabanlı,
   `script-src` / `style-src` / `img-src 'self'`, `connect-src 'self' <API origin>`,
   `base-uri 'none'`, `form-action 'self'`, `frame-ancestors 'none'`, `object-src 'none'`.
   **`unsafe-inline` / `unsafe-eval` YOK** — sevk edilen `dist/`'ten ölçüldü, gerekmiyor.
2. **Build-time `connect-src`** — `frontend/Dockerfile`'da `__API_ORIGIN__`, Vite'ın
   bundle'a gömdüğü **aynı** `VITE_API_BASE_URL` arg'ından türetilir; yer tutucu hayatta
   kalırsa **build durur**. Runtime envsubst mümkün değil (`read_only: true`) ve zaten
   yanlış olurdu (bundle yalnız gömülü origin'e konuşabilir).
3. **Kapı** — `scripts/spa-security-headers-gate.sh`: **canlı yanıtı** assert eder, config
   dosyasını değil (API'nin CSP testinin aynası). Hem `/` hem hash'li bundle'ı sorgular —
   `location /assets/` kendi `add_header`'ını bildirdiği için ikincisi **gereklidir**.
   `install-acceptance.yml` → `fresh-install` job'ına bağlandı (her PR + `main` push'u),
   **negatif adımıyla birlikte** (yanlış origin beklenince kapı kırmızıya dönmeli).

**Reuse anchor'ları (tam sembol adlarıyla):** `scripts/spa-security-headers-gate.sh` içinde
`EXPECTED_HEADERS` (name|exact-value listesi), `header_of()` (bash 3.2 uyumlu — assoc-array
kullanmaz), `assert_surface()`. Yeni bir header eklerken **yalnız** `EXPECTED_HEADERS`'a
satır ekle; iki yüzey de otomatik kapsanır.

**Ölçüldü.** Kapı **exit 0** (2 yüzey × 5 header = 10 PASS); sahte origin ile **exit 1**,
kırmızı `content-security-policy` satırında. Politika **uygulanıyor**: canlı sayfada
enjekte inline `<script>` çalışmadı, inline `<style>` ve `setAttribute('style',…)`
uygulanmadı, **CSSOM ataması uygulandı** (React'in `style={{}}` mekanizması — 814 prop
hayatta). Uygulama **bozulmadı**: Playwright e2e **39 passed / 1 skipped / 0 failed**, ve
kimliği doğrulanmış 9 route'ta **101** inline-style'lı öğe render oldu, **0 CSP ihlali**.

**Dürüst sınır.** Kapı yalnız `install-acceptance.yml`'de koşar (e2e.yml'de değil) ·
**P11-1 açık** olduğu için bu da required status check DEĞİL, job kapısı · CSP
`report-uri`/`report-to` **taşımıyor**, production'da bir ihlal hiçbir yere raporlanmaz ·
yalnız cross-origin compose topolojisi ölçüldü · **P9-F1 ve P11-1 bilerek dışarıda** ·
backend/frontend birim suite'leri **koşulmadı** (tek satır Python/TS kaynağı değişmedi;
`generate_repository_facts.py --check` exit 0). **RC verdict'i BLOCKED kalır, blocker
sayısı DEĞİŞMEDİ (üç).** Tam kayıt: `docs/PROJECT_HISTORY.md` §ADIM 32.

## Stage — ADIM 34: RC §6.7 / P4-1 + P4-2, model↔migration şema paritesi (PR #657)

**Base** `970ec81` (ADIM 33 / #656 merged). **alembic head DEĞİŞMEDİ**
(`0043_i08_registry_strategy_fks`) — bu dalgada **migration YOK**. `ENGINE_VERSION` sabit,
`docs/openapi.json` değişmedi, ürün davranışı değişmedi. Route path, react-query key, OCC
token, Idempotency-Key, SSE taksonomisi, `lib/*.ts` **hiç dokunulmadı**.

**Ne indi.** `alembic check` proje ömrü boyunca **exit 255** veriyordu (40 index-adı sapması)
ve **hiçbir workflow onu koşmuyordu** — sapma sahipsizdi. 39'u **yalnız adlandırmaydı** (sevk
edilen kısa ad ⇄ modelin `index=True`'dan türettiği SQLAlchemy varsayılanı; kolon/uniqueness
aynı), 40'ıncısı (`agent_event.seq`) yapısaldı. **Fix tipi 1** seçildi: **DB'ye ve
migration'lara dokunulmadı**, model sevk edilen ada hizalandı. Sevk edilen adlar
`pg_index`'ten **okundu**, tahmin edilmedi; `alembic revision --autogenerate` **koşulmadı**.

**Reuse anchor'ları (tam sembol adlarıyla):** `scripts/schema_parity_gate.py` içinde
`INDEX_AXIS_OPS` (kapının sahiplendiği operasyon kümesi), `EXPECTED_SERVER_DEFAULT_DEVIATIONS`
(**60** — P4-3 tavanı), `INDEX_SHAPE_SQL` (`pg_index` üzerinden ad+kolon+uniqueness),
`_index_shape()`, `_build_create_all()`, `_model_vs_migration_ops()`. Model tarafında ev stili
**`__table_args__` içinde `Index("<sevk edilen ad>", "<kolon>")`** — yeni bir index eklerken
`index=True` **kullanma**, adı açıkça yaz, yoksa kapı kırmızıya döner.

**Ölçüldü.** index ekseni **40 → 0**; kurulum yolu paritesi **DIVERGENT (361 vs 360) →
BIT-IDENTICAL (361 vs 361, 0/0/0)**; `add/remove column` ve `add/remove table` **0**; tek head,
`upgrade → downgrade -1 → upgrade` **4/4 exit 0**, head `0043` sabit. Kapı **exit 0**, ve
**negatifi kanıtlandı** — iki sapma tipi de geri konuldu, ikisinde de **exit 1**.

**Dürüst sınır.** **`alembic check` HÂLÂ exit 255** ve ne kapı ne belge bunu sıfırmış gibi
gösterir. Sebep **P4-3 (YENİ bulgu)**: raporun *"tip/server-default değişimi = 0"* iddiası
**yanlıştı** — aynı koşu **60 `modify_default`** işlemi de emitliyor (40 tabloda 60 kolon;
DB'de server default var, model onu yalnız Python tarafında bildiriyor). P4-2 ile aynı
aileden gerçek bir ayrışma; **ölçüldü, düzeltilmedi** (ayrı karar, ayrı PR) ve sayı kapıda
**tavana** bağlandı. Kapı **`alembic check`'in exit code'unu assert etmez**; adı da bunu
söyler (*index axis*). **P11-1 açık** olduğu için bu da required status check DEĞİL, job
kapısı. `DATA_MODEL.md` tazelenmedi — kolon-seviyesi index detayı taşımadığını satır 290'da
kendisi yazar ve head değişmedi. **RC verdict'i BLOCKED kalır, blocker sayısı DEĞİŞMEDİ
(üç).** Tam kayıt: `docs/PROJECT_HISTORY.md` §ADIM 34.

---

## ADIM 33 — RC §6.7 / P9-F1: frontend build reproducibility landed (PR #656)

**Tip:** build tesisatı. **`backend/src` ve `frontend/src` DEĞİŞMEDİ**, migration yok,
`ENGINE_VERSION` sabit, `SHARED_ALLOCATION_STATUS` = `future_dev`. Route path, react-query
key, OCC token, Idempotency-Key, hook, SSE taksonomisi, `lib/*.ts` **hiç dokunulmadı**.
**`package.json` / `package-lock.json` İÇERİĞİ bilerek değişmedi.** ADIM 32'nin "P9-F1 ve
P11-1 bilerek dışarıda" notundaki **ilk yarısı** bu dalgada kapandı; **P11-1 hâlâ açık ve
ELE ALINMADI** (repo ayarı, insan kararı).

**Ne indi.** `frontend/Dockerfile`: `COPY package.json package-lock.json ./` (**glob'suz**)
+ `RUN npm ci`. `frontend/.dockerignore` (**YENİ**): `node_modules`, `dist`, `coverage`,
`e2e`, `.env*`, `public/mockup_v18.html`. Üçüncüsü kozmetik değil — `COPY . .` install'dan
**sonra** geldiği için host `node_modules`'ü image'inkinin üstüne biner ve `npm ci`'yi süs
hâline getirir (ADIM 32'de yerel build'de yaşandı); dosya olmadan `npm ci` **uygulanabilir
değildir**.

**Önce ölçüldü.** İddia doğruydu ama **bugün etkisi yok**: `npm install` lockfile'ı bit-bit
değiştirmiyor ve `npm ci` ile **bit-bit aynı bundle'ı** üretiyor (dört `dist/` dosyası da
aynı sha256). **Bu bir davranış değişikliği DEĞİL, bir garanti değişikliğidir** — ve P9'un
kendi kaydıyla (`P9_security.md` §F-1) tutarlıdır.

**Isırdığının kanıtı (her negatif, kontrolüyle).** Lockfile yokken sevk edilen **exit 1**
(`"/package-lock.json": not found`), eski glob **exit 0** (sessizce lockfile'sız devam) ·
lockfile'da olmayan dep bildirildiğinde `npm ci` **exit 1** (`Missing: left-pad@1.3.0 from
lock file`), `npm install` **exit 0** ve lockfile'ı **yeniden yazdı**. `.dockerignore` ile
zehirli host ağacının beş parçası da dışarıda, dosyasız beşi de içeride.

**Reuse anchor'ları (tam adlarıyla):** `frontend/.dockerignore` — yeni bir build girdisi
eklerken **buraya bak**, çünkü `COPY . .` her şeyi alır; `frontend/Dockerfile` içinde
`COPY package.json package-lock.json ./` (glob **ekleme** — fail-closed olması bunun
sayesinde) ve `RUN npm ci` (`npm install`'a **geri dönme**). CSP tarafındaki
`__API_ORIGIN__` sed bloğu ve `scripts/spa-security-headers-gate.sh::EXPECTED_HEADERS`
ADIM 32'den **değişmeden** duruyor.

**Ölçüldü.** `docker build --no-cache` **exit 0 / 84 MB** (2026-08-07 ölçümü de 84 MB) ·
sevk edilen bundle host `npm ci` referansıyla **bit-bit aynı** · zehir image'a **girmedi** ·
**ADIM 32'nin CSP kapısı** canlı konteynerde **10/10 PASS** ve yanlış origin'de **exit 1**.
Ölçüm sırasında **rapor satırında olmayan** bir kusur bulundu: dev-only v18 mockup kopyası
`public/` → `dist/` yoluyla **production image'ına** sızıp `/mockup_v18.html` adresinden
sunulabiliyordu; `.dockerignore` bunu kapatır.

**Dürüst sınır.** Frontend **ve** backend birim suite'leri **koşulmadı** (tek satır
Python/TS kaynağı değişmedi; gerekçedir, ölçüm değil — otorite CI'dır) · bu bir
**tedarik-zinciri savunması değildir** (lockfile'a sadakati zorlar, içeriğini denetlemez;
`npm audit`'in 3 high-severity bulgusu **ele alınmadı**) · `npm ci` build'i **hızlandırmaz**
(588,9 s'lik build'in 579,1 s'i) · `e2e/` istenen üç alt yol yerine **bütün olarak**
dışlandı (bilinçli, gerekçesi PROJECT_HISTORY §ADIM 33'te) · ADIM 32'nin başlığı bu iki
belgede hâlâ `(PR pending)` diyor ama o dalga **#655** olarak indi — `docs-history-guard.py`
başlık yeniden yazmayı kayıt silme sayacağı için **bilerek düzeltilmedi**.
**RC verdict'i BLOCKED kalır, blocker sayısı DEĞİŞMEDİ (üç).** Tam kayıt:
`docs/PROJECT_HISTORY.md` §ADIM 34.

> **Sonradan düzeltildi (PR #702, 2026-08-13).** Yukarıdaki *"başlık bu iki belgede hâlâ
> `(PR pending)` diyor"* tespiti **artık geçerli değildir**: 22 başlık son eki gerçek PR
> numarasını taşıyor (ADIM 32 → **#655**) ve repoda `(PR pending)` biçiminde **hiçbir `## `
> başlığı kalmadı**. Guard'ın rename'i delete'ten ayıramadığı tespiti **hâlâ doğrudur** —
> kapı `ENTROPIA_DOCS_GUARD=off` ile bilinçli aşıldı, aşmadan önce `## ` sayılarının
> `origin/main` ile birebir aynı kaldığı kanıtlandı. Tam kayıt: `PROJECT_HISTORY.md` §ADIM 33.

---

## ADIM 35 — `PortfolioRun` → composite `EngineOutput` projeksiyonu landed (PR #659)

**Tip:** motor yolu, **containment'ın dışında**. Migration **yok** (alembic head
`0043_i08_registry_strategy_fks` sabit), `ENGINE_VERSION` **sabit**,
`SHARED_ALLOCATION_STATUS` = `future_dev`, frontend / route / OCC / Idempotency / SSE
yüzeylerine **hiç dokunulmadı**.

**Neden bu slice.** `docs/ADIM16_STEPPER_LANDED_KICKOFF.md` §4.1 PR B'nin literal kapsamıyla
ulaşılabilir olmadığını ölçmüş, üç engel bırakmıştı; **(a)** ve **(b)** `run_engine`'in bar
gövdesini fazlara bölmeyi, yani ADR §16 insan kapısını + bir ADR amendment'ını gerektiriyor.
**(c)** — projeksiyonun kod olarak olmaması — gerektirmiyor, hangi yol seçilirse seçilsin
gerekiyor ve tek başına test edilebilir. Kickoff'un **seçenek 3**'ü seçildi.
**(a) ve (b) KAPANMADI.**

**KARAR (canon'dan, koddan değil): tek portföy-seviyesi çıktı, N adet öğe-seviyesi DEĞİL.**
(1) N öğe çıktısını `combine_item_runs`'a beslemek bileşik eğriyi **sıralı birleştirmeyle**
yeniden kurardı — ADR §14 **A5**'in ("*time-ordered by construction*") kaldırmak için var olduğu
kusur, ki fold onu `portfolio_curve_sequential_not_unified_clock` diye zaten ifşa ediyor.
(2) ADR §7: *"a sleeve is a cap, not a wallet"* — sermaye bölünmez, yani bölünecek **öğe-seviyesi
equity yoktur**; `E(t)`'yi N eğriye ayırmak canon'un tanımlamadığı bir tahsis-atıf modeli olurdu.
Defterin öğe başına tuttuğu şey `ItemAttribution`'dır (net katkı; eğri değil, drawdown tabanı
değil). Projeksiyon bu yüzden `combine_item_runs`'ı **beslemez, yerine geçer** — ve sıralı fold'a
tek satır dokunulmadı.

**Ne indi.** **YENİ** `domain/backtest/execution/portfolio_projection.py`:
`project_portfolio_run(run, *, items, execution_key, item_count) -> EngineOutput` (`:511`),
`PinnedItem` (`:162`), `ABSENT_BY_CONSTRUCTION` (`:117`), üç fail-closed hata,
`ENGINE_KIND = "v1_unified_clock_portfolio"`. `portfolio_engine.py`'ye **additive, reporting-only**
iki ekleme: `BookedClose` (`:165`) ve `PortfolioTick.closes` (`:206`, varsayılan `()`) — döngü P3'te
`MandatoryExit`'i tüketip unutuyordu ve realize edilen para yalnız `E(t)`'ye düşüyordu, orada
işlem-başı rakam geri alınamaz. `net_pnl` = `book_trade`'in **dönüş değeri**, çünkü
`gross - commission`'ı yeniden hesaplamak yuvarlamanın ikinci uygulaması olurdu.

**Bu ne açtı.** ADR §14'ün **A4** ("item sırası sonucu değiştirmez — *identical `EngineOutput`
digest*") ve **A18** (cross-item batch invariance, aynı ifade) kriterleri **ilk kez
değerlendirilebilir**: o yolda digest alınacak bir artefakt yoktu. İkisi de tam çıktı digest'i
üzerinden test edildi. Amiral gemisi test containment fixture'ının **kendi** trade set'idir:
sıralı fold'un `5000.00` dediği dört kapanış, projeksiyonda `summary["max_drawdown"] == 3000.00`.

**Reuse anchor'ları (tam adlarıyla):** yeni bir alan eklerken önce `portfolio_projection.py`
§"deliberately ABSENT" bölümünü oku — beş kalem gerekçeli olarak **yok** ve
`ABSENT_BY_CONSTRUCTION` ile ilan ediliyor · pinlenmiş metadata için `PinnedItem` (worker
`ItemRun`'ın taşıdığı alanların aynısını verir) · faz döngüsünde bir kapanışın parasını okumak için
`PortfolioTick.closes` / `BookedClose.net_pnl` · `combine_item_runs`
(`execution/portfolio.py:312`) **dokunulmadı**, worker call site `jobs/backtest_engine.py:363`.

**Containment ölçüldü, gevşetilmedi.** `execution/*` modüllerinin her biri tam importer listesiyle
pinli. Projeksiyon yalnız `execution.intents`'i (tip için) import ediyor →
`test_backtest_item_intents.py` listesi **bilerek** genişletildi. `clock`/`portfolio_ledger`/
`arbitration` policy-version sabitleri **bilerek yayımlanmadı** (hiçbir tüketicinin okumadığı bir
alan için üç liste daha genişletmek pahalıydı). `execution/` içindeki modüller per-module importer
kontrolünden muaf olduğu için projeksiyonun kendi containment iddiası ayrıca yazıldı:
`test_oracle_portfolio_containment_gate.py::test_the_result_projection_exists_but_no_production_path_reaches_it_either`.

**Dürüst sınır.** **Üretim yolu YOK ve bilerek yazılmadı** — worker hâlâ item döngüsü +
`combine_item_runs`, `run_portfolio` ve `project_portfolio_run` ikisi de çağrısız; bu slice
**hiçbir sevk edilmiş Result'ı değiştirmez** ve A4/A18'i tek başına "geçirmez", yalnız
*ölçülebilir* kılar · §4.1'in (a)/(b) engelleri **kapanmadı** · `domain/backtest/` paketi
`docs/CODEMAPS/BACKEND_LAYERS.md`'de **hiç haritalı değil** (bu slice öncesinde de öyleydi; bu
dalga endpoint/tablo/sayfa/job eklemediği için tazeleme tetiklenmedi — eksik kaydedildi,
kapatılmadı) · frontend suite koşulmadı (tek satır TS değişmedi; gerekçedir, ölçüm değil).
Tam kayıt: `docs/PROJECT_HISTORY.md` §ADIM 35. Devir: `docs/ADIM35_LANDED_KICKOFF.md`.

---

## ADIM 37 — RC §6.7 / P10-B2: sayfalama sınırı YAYIMLANDI, aşım davranışı AÇIK (PR #663)

**Numara düzeltmesi:** kickoff prompt'u bu slice'a "ADIM 36" diyordu; **ADIM 36 doludur**
(P6-ek + P6-6, PR #658, `881d273`). Merge edilmiş numara yeniden atanmaz → **ADIM 37**.
Yeni bulgu **P10-B6** (B1..B5 dolu). *Gözlem, düzeltilmedi: ADIM 36'nın bu belgede bir
`landed` girdisi **yok** — PROJECT_HISTORY §ADIM 36 var, handoff'ta yok. Başka bir slice'ın
kaydına dokunmadım, eksiği burada kaydediyorum.*

**Migration yok · `ENGINE_VERSION` sabit · `SHARED_ALLOCATION_STATUS` = `future_dev` ·
`frontend/src` hiç dokunulmadı.** Base `881d273` (#658).

**Ne kapandı:** 9 kelepçeli `limit` parametresinin **hiçbiri** sınırını yayımlamıyordu;
artık dokuzu da default + tavan bildiriyor. YENİ ortak declarator
`apps/api/pagination.py::clamped_limit_query` → `description` + `x-clamp-default` /
`x-clamp-maximum`. Ölçülen: **28 parametre = 19 ENFORCING (`maximum` → 422) + 9 CLAMPING
(`x-clamp-maximum` → 200), UNPUBLISHED 0**, ve kelepçeli hiçbir parametre `maximum` emitlemiyor.
`docs/openapi.json` yeniden üretildi (45+/9−). Kapı:
`tests/contract/test_pagination_limit_contract.py` (5 test), **negatifi kanıtlı**
(tek uç geri alındı → `exit 1`, uç adıyla raporlandı).

**Ne KAPANMADI (ve kapandı diye yazılmayacak):** aşımın **sessiz clamp mi 422 red mi**
olacağı bir **ürün kararıdır**; canonical (MTR §2.1/§8, doc 19, doc 18, doc 22) **sessizdir**
→ karar **VERİLMEDİ**, adjudication olarak kaydedildi (rapor §6.7.5, defter
`docs/releases/evidence/2026-08-11/`). **PO kararı bekliyor.** Sessiz clamp *"böyle kalsın"*
diye onaylanmadı da.

**Raporun bir ifadesi düzeltildi:** *"9 uçta sessizce 100'e iniyor"* — ölçüldü, **5 uçta
`meta.limit` etkin değeri zaten yankılıyordu**, 3 uçta yalnız `next_cursor` var, **1 uçta**
(`/agent-tasks/{task_id}/tool-calls`) gerçekten hiçbir sinyal yok. Asıl kusur "kesilmeyi fark
edememe" değil, **"sınırı önceden öğrenememe"** idi.

**Yeni ölçüm, düzeltilmedi → P10-B6:** 4 uç ETKİN sayfa boyutunu yanıtta yankılamıyor.
Yanıt gövdesi = wire contract (`lib/*.ts` + typed `AgentToolCallListResponse`) → ayrı karar,
ayrı PR.

**Bu eksende sırada:** §6.7'nin kalan kalemleri — P11-2/3/6/8 · P10-7 · P1-B1/B2 ·
P8-B1/B2/B3 · P1-Gate3 · yeni P10-B6. **P11-1 agent işi DEĞİL** (branch protection = repo
ayarı, insan kararı). **Blocker sayısı DEĞİŞMEDİ, verdict BLOCKED KALIR.**

---

## ADIM 38 — RC §6.7 / P11-3 + P11-6: kapının ölçtüğü ile iddia ettiği landed (PR #664)

> Görev metni "ADIM 37" diyordu; o ad merge edilmiş **#663**'e bağlı ve değiştirilemez →
> çift-ad hatasını tekrarlamamak için **ADIM 38**.

**Ürün kodu DEĞİŞMEDİ**, migration yok, `ENGINE_VERSION` sabit. Verdict **BLOCKED**,
blocker sayısı **üç**. **P11 KAPANMADI.**

- **P11-3 KAPANDI.** 8 `-chromium-darwin.png` baseline'ını **hiçbir job assert etmiyordu**
  (18 `runs-on:`'un 18'i `ubuntu-latest`, macOS runner yok) ve macOS'ta `e2e.yml`'in
  seed'iyle koşulunca **8'in 6'sı düştü** (44–539 px). Kontrol deneyi bunun bir platform
  farkı **olmadığını** gösterdi. → **silindi**; **YENİ**
  `scripts/visual-baseline-platform-gate.sh` (`ci.yml` → `frontend`) geri dönüşü kırıyor,
  **negatifi kanıtlı**. (a)'nın maliyeti (macOS 10×, ürün Linux konteyneri) reddedildi.
- **P11-6 KAPANDI (kapsam ekseninde).** Tab sırası **3/23 → 23/23**, 0 N/A; liste artık
  `screenshotMatrix.ts::TARGET_PAGES`'ten türüyor. Daraltmanın gerekçesi ölçülerek
  çürütüldü (**13.2 s**, job 1.2 dk). 0 sapma, 0 blocking, advisory **90** = ADIM 29.
- **YENİ AÇIK KALEMLER:** **P11-6b** (sonda **Tab'a basmıyor** ve **hiçbir rota onu
  kıramaz** — ölçüldü, düzeltilmedi; sınır `precheck-results.json::tab_order_probe`'a
  yazıldı) · **P11-3b** (`strategy-standalone` bugün 1135 px, `-linux` baseline'ı 900 →
  hayatta kalan setin **seed hassasiyeti** açık).
- **DOKUNULMADI:** P11-1 (repo ayarı, **insan kararı**), P11-2 (ayrı PR), P11-8, K-2..K-6,
  dört blocker. **A-08 ile karıştırılamaz** — defter BOŞ, `REMINDER: A-08 is
  HUMAN-BLOCKED` satırı yerinde.

Doğrulama: e2e tsc temiz · frontend eslint temiz · `ci.yml` ve precheck spec'i okuyan 94
backend testi **passed** · `generate_repository_facts.py --check` **OK** · docs regresyonu
**yok**. Ham kanıt: `docs/releases/evidence/2026-08-11/`. Tam kayıt:
`PROJECT_HISTORY.md` §ADIM 38; devir: `docs/ADIM38_LANDED_KICKOFF.md`.
**Linux `@visual` kapısının hâlâ yeşil olduğunu CI job LOG'undan doğrula** — bu makinede
(darwin) koşulamadı.

---

## ADIM 39 — RC §6.7 / P11-2: görsel regresyon kapsamı 8 → 23 landed (PR #665)

**Kapsam 8 → 23.** `specs/11-visual-regression.spec.ts` elle yazılmış sayfa dizisini
kaybetti; liste `utils/screenshotMatrix.ts::TARGET_PAGES`'ten türüyor — axe scan, keyboard
sondaları ve screenshot matrisinin okuduğu **aynı** tekil kaynak. **15 yeni `-linux`
baseline**; sekiz mevcut baseline **yeniden üretilmedi**, yalnız slug'a göre rename edildi
(git `Bin` = byte-identical), yani eski sekiz sözleşme aynen duruyor.
`mode: "serial"` kaldırıldı — bir hata artık grubun kalanını *skip* etmiyor (faydası aynı
gün görüldü: `analysis-lab` düşerken diğer 22 rota yine ölçüldü).

**Runner'da 23/23, İKİ KEZ, aynı commit'te** (`fa0c6a2` + rerun, taze stack + taze seed).
Süre `e2e` job'ında **1.4 dk → 4.0 dk (+2.6)**. Tolerans (`maxDiffPixelRatio 0.02`)
**değişmedi**, kapı **bloklayıcı** kaldı, hiçbir rota atlanmadı, **ürün kodu değişmedi**.

**İki yazılı olmayan önkoşul bulundu ve README'ye yazıldı — yeni baseline üretecek
herkesi ilgilendirir:**
1. **Baseline'lar salt-seed stack'i tarif ETMİYOR.** `e2e.yml` görsel kapıyı `npm test`'ten
   SONRA koşuyor; salt-seed bir stack'te mevcut sekiz baseline'ın **dördü** yalnız yükseklik
   yüzünden düşüyor (929↔900, 947↔900, 1411↔1396, 900↔1135). **Bu P11-3b'yi cevaplar:**
   hassasiyet seed'e değil **journey sonrası duruma**; aynı 1135 px Linux'ta da ölçüldü →
   platform artefaktı değil.
2. **"Linux" ile "runner" aynı şey değil.** `playwright:v1.55.1-noble` 23 sayfanın 22'sini
   runner ile birebir verdi; `analysis-lab` 6 px saptı (konteyner 1496 / runner 1490,
   runner iki denemede byte-identical → jitter değil, sembol glifi font farkı). O
   baseline **CI artefaktından** alındı.

**Yeni baseline eklerken:** listeyi elle yazma (TARGET_PAGES türetir), maske icat etme,
toleransı büyütme; CI-dışı bir Linux'ta üretiyorsan bir-iki sayfanın reddedilmesini bekle ve
runner'ın kendi `test-results/**/<slug>-actual.png` dosyasını baseline'ın üstüne kopyala.

**Dondurulan bilinen kusurlar açıkça bildirildi** (F-2 `package-library` makine etiketleri,
F-4 `portfolio` ham `mbi_…`, F-07 sınıfı ham `btres_…` `panel-logs`/`results-history`);
F-7 `embedded-packages`'ta FIXED doğrulandı; **F-5 görünüşe göre kapanmış** (history satırı
artık headline metrik gösteriyor) → defter hâlâ açık listeliyor, **PO kararı**.

**Yerelde görülüp CI'da üretilemeyen bir gözlem:** bu makinede `/backtest/ready-check`
yüksekliği 946/947/950 salınıyordu; **runner'da üç koşunun üçünde de geçti** → CI flake'i
DEĞİL, §6.7'ye kalem açılmadı, yalnız kanıta yazıldı.

Doğrulama: e2e tsc temiz · `visual-baseline-platform-gate.sh` → **23 baseline, hepsi
`linux`** · `generate_repository_facts.py --check` **OK** (`Playwright snapshot PNGs 8 → 23`)
· E2E + A11Y + frontend + backend CI **passed**. Ham kanıt:
`docs/releases/evidence/2026-08-11/P11_2_visual_coverage.md`. Tam kayıt:
`PROJECT_HISTORY.md` §ADIM 39; devir: `docs/ADIM39_LANDED_KICKOFF.md`.
**A-08 DEĞİL** — piksel karşılaştırması ekran-okuyucu kanıtı değildir.

---

## ADIM 40 — RC §6.7 / P1-B1+B2 + P8-B1+B3: sayının sahibi değişti landed (PR #666)

**Numaralandırma:** istem "ADIM 38" diyordu ve base olarak ADIM 37b'yi varsayıyordu; doğrulama
`origin/main`'de **ADIM 38 (#664) + ADIM 39 (#665) zaten merge** gösterdi → numara yeniden
kullanılmadı, bu **ADIM 40**. Base `66bdeb4`.

**Dört belge kalemi kapandı — sayı güncellenerek DEĞİL, sahipliği değiştirilerek.** Bu, elle
yazılmış bir sayının bayatladığı **üçüncü** kayıttı; sayıyı elle tazelemek dördüncüyü garanti
ederdi. Her kalemde merdiven (1 = üretilene işaret et · 2 = üretime ekle · 3 = bayatlamayacak
biçimde yaz) sırayla soruldu ve ilk uyan seçildi:

- **P1-B1** (`queries` 37/38, `jobs` 14/16) → **2 sonra 1**: sayılar artık
  `collect_backend_layers` ile üretiliyor (`repository_facts.md` §Summary ▸ *Application
  modules*), codemap'ten **silindi**. Ölçüm sayının **göremediği** kusuru buldu: `jobs` tablosu
  16 modülün 14'ünü adlandırıyordu — `delivery.py` ve `heartbeat.py` **hiç satır almamıştı**,
  ikisi de eklendi. Raporun *"içerik olarak tam"* ifadesi bu yüzden **yanlıştı**.
- **P1-B2** (`CLAUDE.md` 16 ↔ codemap 17) → **1**: op-seviyesinde semantik sayı, ucuzca
  türetilemez (`reconcile_occ_tokens` çağrı yeri 12, op 17). Kanonik liste zaten
  `BACKEND_ROUTES.md` §DUAL-TOKEN'daydı → `CLAUDE.md`'deki kopya **kaldırıldı**.
- **P8-B1** (docstring gerekçesi) → **3**: `pending_data_job_dispatch`'in replay'de `None`
  dönüşü artık **admission** ile gerekçeleniyor; *"gövdede terminal-state guard yok"* öncülü
  ADIM 21'de sona ermişti (`trade_log.py`/`trading_signal.py` → `claim_job_for_delivery`).
  **Davranış, imza, `__all__` değişmedi.**
- **P8-B3** (aktör tablosu ~24 satır kaymış) → **sembol adı**: aktör adı zaten sembol
  (`apps/worker/actors.py::<aktör>`) → **"Satır" kolonu silindi**. 12 değerin 11'i bayattı.

**Tekrarı yeni kapı engelliyor:** `generate_repository_facts.py::check_codemap_coverage` —
her application modülünün codemap satırı (**katman bölümüne kapsamlı** arama; `market_data.py`
üç katmanda birden var) + her `@dramatiq.actor`'ın satırı **ve kuyruğu**. **Negatifi 5 testle
kanıtlı** (+1 türetme testi). Kapı **sayı değil üyelik** doğrular; bir sayı yalnız birinin bir
kez saydığını kaydeder.

**AÇIK — bilerek girmedi:** **P8-B2** (Create-Package **200** ↔ diğer dokuz **202**) bir belge
sapması değil, çözülmemiş **API sözleşmesi** → ayrı PR + ürün kararı; **P8 KAPANMADI**.
**YENİ P8-B3b:** `JOBS_AND_EVENTS.md` gövdesinde ~30 `:NN` referansı daha — ölçüldü,
düzeltilmedi, sınır dosyanın kendisine yazıldı.

**Doğrulama:** ruff check + format temiz · mypy `398 source files` temiz · `generate_repository_facts.py --check` **OK** (negatifi hem sentetik hem **gerçek ağaçta** kanıtlandı) · tam suite **4034 passed / 1 xfailed / 0 failed**, coverage **%93.58** (kapı ≥90), exit **0** · `git diff origin/main -- docs/ | grep '^-## '` **boş**.

Migration YOK · alembic head, `ENGINE_VERSION`, `SHARED_ALLOCATION_STATUS` değişmedi ·
blocker sayısı **üç**, §8 verdict **BLOCKED**. Tam kayıt: `PROJECT_HISTORY.md` §ADIM 40;
rapor **§6.7.8**; devir: `docs/ADIM40_LANDED_KICKOFF.md`.

---

## ADIM 41 — RC §6.7 / P8-B2: durable admission status'ü karara bağlandı (PR #668)

**Karar slice'ı, bug fix değil.** "Tutarsızlık gördüm, hizalayayım" refleksine direnildi.

**Ölçüm önce (küme türetildi, elle sayılmadı).** `application/` katmanında `enqueue_job`'a
**transitively** ulaşan fonksiyonlar AST ile çıkarıldı → **13 durable admission ucu**;
on üçünün **tamamı** kuyruğa alıp iş bitmeden dönüyor → **senkron uç YOK**. Sevk edilen
dağılım **4×200 + 1×201 + 8×202** — yani raporun *"diğer dokuz 202"* ifadesi **yanlıştı**
(201'i döndüren `/library/{id}/validation-runs`, `../validate` ile **aynı** run'ı sarar).

**Kanonik uç uç konuşuyor.** `pre-check` (doc 07 §10.3 birebir *"202 accepted"*) ve
`generate-candidate` (MTR §7.1 literal `-> 202 Accepted`, §4.2, doc 07 §10.3) → **202'ye
hizalandı** ve gövdeleri `dict[str, Any]`'den tiplenip şemada **yayımlandı**
(`PrecheckAcceptedResponse` 11 alan, `CandidateAcceptedResponse` 5 alan).
`../validate` ve `../baseline-parse` için kanonik **status vermiyor** (baseline-parse için
**ucu bile adlandırmıyor**) → **kod DEĞİŞMEDİ, PO kararı bekliyor**; docstring'lere *neden
200 kaldığı* yazıldı. Sevk edilmiş 202 deseni **olgu** olarak kaydedildi, kanonik boşlukta
kural olarak kullanılmadı (202 dönen beş uç `enqueue_job` bile çağırmıyor).

**Bağımlılıklar ölçüldü, tahmin edilmedi:** frontend `apiClient` yalnız 204'ü ayırır
(2xx ayrımı istemciye görünmez, frontend'e tek satır dokunulmadı) · `run_idempotent` yalnız
**gövdeyi** saklar, status route dekoratöründe → O-30'un backfill tuzağı **oluşamaz** ·
dört ucun hiçbirinde HTTP status assert'i yoktu.

**Yeni kapı:** `tests/contract/test_p8b2_admission_status.py` (5 test) admission kümesini
**türetip** sınıflandırma tablosuyla karşılaştırır → **sınıflandırılmamış yeni admission ucu
CI'da kırmızı**; on üç ucun yayımlanmış status'ü pinli. **Negatifi iki yönden kanıtlandı.**
Alan düşmediği saklanan idempotency zarfıyla kanıtlandı (`test_typed_contract_replay_parity.py`
+2 test: `resp.json() == IdempotencyKey.response_ref`, replay aynı gövde + aynı **202**).

**AÇIK — bilerek girmedi:** `../validate` + `../baseline-parse` (+ `validation-runs` 201)
**PO kararı bekliyor** (öneri §6.7.9'da: üçünü de 202'ye çekmek) · **P8-B3b** · genel status
denetimi bu slice'ın kapsamı DEĞİL. **P8 KAPANMADI.**

Migration YOK · alembic head, `ENGINE_VERSION`, `SHARED_ALLOCATION_STATUS` değişmedi ·
**OpenAPI snapshot bilerek değişti** (iki operation `200 → 202`, path/operation sayısı aynı) ·
blocker sayısı **üç**, §8 verdict **BLOCKED**. Tam kayıt: `PROJECT_HISTORY.md` §ADIM 41;
rapor **§6.7.9**; devir: `docs/ADIM41_LANDED_KICKOFF.md`.

---

## ADIM 42 — RC §6.7 / P1-Gate3: kabul kriteri kapsamı ölçüldü, sınıflandırıldı, ratchet'lendi (PR #669)

**Migration:** yok · **Yeni tablo:** yok · **Ürün kodu:** DEĞİŞMEDİ (`ENGINE_VERSION`,
OpenAPI, alembic head sabit). Bu bir **test/kapı** slice'ıdır.

**Ne landed:**

* **Ölçüm.** `acceptance_semantic_scan.py --report` 2026-08-07'nin dağılımını **birebir**
  yeniden üretti (383 kriter / 1175 clause; 229 / 131 / 8) — sayılar **bayat değildi**.
  Kapının `partial`'ı geçer sayması **kasıtlı**: `validate()` haritanın kendisi hakkında
  yalan söylemediğini kanıtlar, statü **dağılımına** bakmaz. Eksik olan yarı buydu.
* **Sınıflandırma.** 139 kaydın tamamının gerekçesi okundu; **üç sınıf veriye uymadı**,
  dördüncü eklendi. Her açık kayıt `debt_class: A|B|C|D` taşıyor, kapı sınıfsızı
  **kırmızıya çevirir** (`DEBT_CLASS_REQUIRED` / `DEBT_CLASS_NOT_ALLOWED`).
  **A=1 · B=95 · C=6 · D=32.** Açık borcun **%24'ü sınıf D** — *hiçbir test kapatamaz*,
  ürün işidir.
* **Ratchet.** `docs/audit/acceptance_coverage_baseline.json` (a11y ratchet'i şablon aldı):
  statü ve sınıf sayıları **tavan**, `total_criteria` **taban** (kriter silmek ilerleme
  sayılamaz), **pay yok** (testle kilitli). `ci.yml` → `--report --ratchet`.
  **Negatifi kanıtlı:** CLI `exit 1` + 6 unit test.
* **Pinler (8 clause / 5 kriter).** **O-31 adjudication:** üç belge tek reddi üç türlü
  adlandırıyor (`ACTIVE_RUN_DEPENDENCY` / `DELETE_BLOCKED_BY_RUNNING_JOB` /
  `OBJECT_IN_ACTIVE_RUN`) → **sevk edilen ad kanonik**. `AOS-17`, `TS-17`, `TR-06`,
  `TL-19`, `AOS-18` **covered** oldu. Yeni taban **234 / 126 / 8**.
* **Defter.** `docs/audit/acceptance_coverage_debt_ledger.md` — **üretilmiş**, 134 kalem,
  bayatlığı testle kapılı.

**Test sayıları:** kapı unit paketi **61 passed** (13'ü yeni) · iki pin testi **2 passed**
(izole DB `entropia_p1gate3`). Kanıt: `docs/releases/evidence/2026-08-12/`.

**Review outcome:** ürün kodu değişmediği için ürün-review'ı yok; kapı değişikliklerinin
negatifi ampirik kanıtlandı.

**Ertelenen / dürüst sınır:**

* **134 açık kriterin hiçbiri kapatılmadı** (kapsam dışıydı) — sıralı defter yazıldı.
* Sınıf D'nin **ürün kararı isteyen** alt kümesi (`RD-02`, `RD-03`, `AM-11`, `AOS-02`:
  spec ↔ sevk edilen davranış **çelişiyor**) **PO'ya sorulmadı**, deftere kaydedildi.
* Sınıflandırma kayıtların **kendi `notes` gerekçesinden** okundu; 134 test gövdesi tek tek
  yeniden okunmadı → bir yanlış sınıflandırma mümkündür, `notes` otoritedir.
* `AT-04` **sınıf D** çıktı: pinlenecek bir şey yoktu, sevk edilen RUN-zamanlı kod zaten
  pinliydi. Brief'in `K-06 = upload kapısı` tanımı **yanlıştı** (o **K-07**); K-07 ölçüldü
  ve **zaten pinli** bulundu.

**P1-Gate3 KAPANMADI.** Blocker sayısı **üç**, verdict **BLOCKED**.

---

## ADIM 43 — RC §6.7 / P11-8 + P10-7: Lighthouse ratchet'i + latency ratio kapısı landed (PR #676)

**Migration:** yok · **Yeni tablo:** yok · **Ürün kodu:** DEĞİŞMEDİ (`ENGINE_VERSION`,
OpenAPI, alembic head sabit). **CI/kapı** slice'ı.

**Ne landed:**

* **P10-7 KAPANDI — ve saat zaten dolmuştu.** Brief bu kalemi *"kapanmaz, yalnız saati
  başlatır"* diye planlıyordu. Ölçüm bunu çürüttü: toplayıcı **ADIM 24'ten beri** vardı
  (`performance.yml` → `load-full`, cron `23 4 * * *`) ve **altı** yeşil gece birikmişti
  (08-07…08-12; hepsi `github-ubuntu-latest`, 16/40, sıfır hata, artefaktları duruyor).
  Beşinci gece **08-11**'de dolmuştu → planlanan ikinci PR **gereksiz**.
* **Bant türetildi.** Ham kontrol kayması **1.71×**; dondurulmuş baseline'a karşı en kötü
  gece **1.62×** → README §6 adım 3 (`~1.5×`) → **`--max-ratio 2.5`**. Baseline = altı
  gecenin medyanı (`31461912952`, 08-11, `4e9512d2`), artık **takipli dosya**
  (`docs/performance/baseline_ci.json`) → artefakt saklamasına bağlı değil.
* **Negatif kanıtlı, gerçek baseline üzerinde:** altı gece PASS (1.54× pay) · 3.0× FAIL ·
  2.4× geçer (sınır gizlenmedi). §6 adım 5'in *"bant yok, kapalı bırak"* çıkışı **alınmadı**.
* **P11-8 KAPANDI.** Lighthouse **ratchet** olarak bağlandı (`e2e.yml` → `lighthouse`,
  `specs/21-lighthouse.spec.ts`, `lighthouse-baseline.json`) — axe deseninin aynısı, yeni
  desen icat edilmedi. **23/23 rota, kapsanmayan 0**, liste `TARGET_PAGES`'ten türüyor.
  Gürültü **stabilize** edildi (warm-up + 3 koşunun medyanı) → tekrar yayılımı **0 puan**.
  Kapı **UNARMED** sevk edildi, ilk CI koşusu ölçtü, ikinci commit dondurdu.
* **Ölçülen taban:** performance **100** (22 rota) / **98** (`panel-management`) ·
  best-practices **96** · seo **82**.
* **İki otorite çakışması önlendi:** Lighthouse **a11y kategorisi hiç istenmiyor** (axe
  otorite; **hiçbir çıktısı A-08 kanıtı değil**) · performans ayrımı iki belgeye yazıldı
  (`loadgen` = sunucu, Lighthouse = tarayıcı; `performance/README.md` §8'in beyan ettiği
  boşluk).

**Dürüst sınırlar:** Lighthouse performance localhost'ta **doygun** (taban 100 = *"hiç
kötüleşemez"*, gerçek cihaz kanıtı **değil**) · BP 96 / SEO 82 **gerçek kusur**, donduruldu
**düzeltilmedi** (ayrı PR; `routes[].deductions` onları isimlendirmeye devam eder) · ratio
kapısı **2.5× altını görmez** ve **PR'da koşmaz** · bant **altı** geceye / **tek** runner
class'a dayanıyor · **P11 ve P10 KAPANMADI** (P11-1 = insan kararı, P11-6b, P10-B2'nin PO
yarısı, B3–B6) · Lighthouse kapısı P11-1 açık olduğu için *required status check* değil.

**Test sayıları:** `test_loadgen.py` **32 → 38 passed**. Üretilmiş: backend collected
**3497 → 3503**, e2e call sites **80 → 84 / 22 spec**. Kanıt:
`docs/releases/evidence/2026-08-12/`. Rapor: **§6.7.11** + **§6.7.12**.

---

## ADIM 44 — RC blocker 4 KAPANDI, blocker 1 koşulabilir hâle geldi (PR #678)

**Migration YOK** · `ENGINE_VERSION` değişmedi · **bağımlılık sürümü değişmedi.**
Base `e719af1`. (Seed prompt kendini "ADIM 41" sanıyordu; o numara **#668'de** kullanıldı
— kayıt **ADIM 44**.)

* **Blocker 4 (P9-B2) KAPANDI — imzayla değil, KALDIRMAYLA.** İmza verilmişti (owner
  `Ali Mirbagirzade`, expires `2026-11-10`) ama kayıt **yazılmadı**: advisory
  **2026-08-07T18:16:54Z**'de yeniden kapsamlandı (`first_patched` 7.x için **7.18.2**),
  kurulu ağaç **zaten 7.18.2** → `npm audit` **0 vulnerability**. **Bir imza, ortada
  olmayan bir açığa atılamaz.** Repo düzeltilmiş sürümün üzerinde on bir gündür
  oturuyordu; advisory metadata'sı #637'yi merge eden commit'ten **yirmi dakika sonra**
  yetişti. **Üçüncü tekrar** (brace-expansion, js-yaml, şimdi bu).
* **`FROZEN_ADVISORIES` SİLİNDİ.** Yeni bir npm advisory'yi dondurman gerekirse öyle bir
  liste **yok**: kayıt `.github/security-allowlist.json`'a `scope: npm:<dir>` + **`owner`**
  + **`expires`** ile girer. İki kapı da ortak `scripts/lib/security-allowlist.mjs`'ten
  geçer ve **ikisi de TÜM listeyi expire eder** — aksi hâlde bir istisnanın takvimi hangi
  workflow'un koştuğuna bağlı olurdu. **Yeni bir paket dizini gate'lerken scope'u
  BİLDİR:** bildirilmemiş scope `exit 1` verir. Pin:
  `backend/tests/contract/test_security_freeze_discipline_contract.py` (7 test).
  Negatif kanıt: 5 × exit 1 + 1 × WARN-exit-0.
* **Blocker 1 (A-08) KAPANMADI.** Çıkış kriterleri **0/4**, defterin §1/§2/§3'ü **boş**,
  **#514'e dokunulmadı**. Değişen: yığın güncel main'de **9 passed / 0 failed** (dokuz
  slice sonra, onarım gerekmedi) · precheck sayıları tazelendi · denetçi runbook'u yazıldı
  (`docs/implementation/a11y_screen_reader_audit_runbook.md`).
* **PRECHECK TUZAĞI — bunu bilmeden sayıyı tazeleme.** Beş ardışık koşu (aynı commit /
  yığın / seed): K-2 `23`, K-3 `23`, K-4 `1`, K-6 `1` **kararlı**; K-5 `18→21→20→21→21`,
  yeni K-7 `10→20→20→21→21`, toplam `76→89→88→90→90`. **`up`'tan sonraki İLK KOŞU
  SOĞUKTUR VE EKSİK RAPORLAR** — tek koşuyla "tazeleme" K-5'i `21/23`'ten `18/23`'e
  çekip tabloyu **daha yanlış** yapardı. **En az iki kez koş, sonrakini al.** Kalıcı
  oynaklık: `/analysis-lab`, `/backtest/history`, `/backtest/metrics`. Sebep: prob *ilk*
  DOM'u okuyup sayfanın ilk veri render'ıyla yarışıyor. **Kaydedildi, DÜZELTİLMEDİ** —
  örnekleme zamanını değiştirmek K-5/K-7'nin *anlamını* değiştirirdi.
* **K-7 eklendi:** ilk DOM'da `aria-live` yok, **21/23**, WCAG 4.1.3 (AA). ADIM 28'den beri
  ölçülüyordu ama defterde satırı yoktu; B-3 / B-4 / B-6'nın tam sorusu.

**Dürüst sınırlar:** hazırlık denetim değildir · blocker sayısı **4 → 2**, **verdict
BLOCKED kalır** · `npm audit` yalnız iki workspace'i, Trivy yalnız iki imajı görür ·
container kapısı hâlâ sadece `security.yml` tetikleyicilerinde koşar. Kanıt:
`docs/releases/evidence/2026-08-12/P9B2_react_router_freeze_dropped.md` +
`A08_audit_readiness.md`. Rapor: **§6.1** (açık, güncellendi) + **§6.4** (KAPANDI) + §8 + §9.0-e.

---

## ADIM 45 — RC blocker 2 KAPANDI: `flows` bir CI kapısı oldu (PR #680)

**Migration YOK** · `ENGINE_VERSION` değişmedi · **ürün kodu değişmedi** (harness +
workflow + belgeler). Base `853a358`.

* **Blocker 2 KAPANDI. Blocker sayısı 2 → 1 — geriye YALNIZ A-08 kaldı; verdict `BLOCKED`.**
  RC §6.2'nin açık kalan tek ekseni belgenin kendi cümlesiydi: *"`flows` bir CI KAPISI
  DEĞİLDİR."* Kapsam ADIM 30'da yazılmıştı; **eksik olan kapıydı.**
* **Yeni harness icat EDİLMEDİ** — `e2e.yml`'e tek job: **`acceptance-flows`**, var olan
  `scripts/e2e-acceptance.sh flows` alt-komutunu koşar.
* **Rozet değil, job LOG'u** (job **94097720164**, success): **`67 passed / 0 failed /
  1 skipped`**, `duration_seconds=137`, job **2m56s**, 12 konteyner + yedi düzlem
  `restarts=0`, tarayıcı katmanı **5 passed**. Ham:
  `docs/releases/evidence/2026-08-12/P6B2_flows_ci_gate.md` (+ 3 ham dosya).
* **Maliyet ölçüldü ve kabul edildi.** §6.2 "kabul edilemezse nightly'ye al ya da
  paralelleştir" demişti; **ikisi de gerekmedi** — kardeş job olduğu için workflow
  wall-clock'una **~0** ekler. **Kapsam KISILMADI, kapı advisory DEĞİL.**
* **Üç tuzak kapatıldı:** (1) `tee`'nin exit code'u — `set -o pipefail` olmasa düşen bir
  kabul koşusu **yeşil** raporlardı; (2) sessiz SKIP kayması — **`E2E_MAX_SKIPS`** (CI: 1)
  karara bağlanmış sayıyı pinler, tanımsız = tavan yok; (3) chromium sistem bağımlılıkları
  — job onu **önceden** `--with-deps` ile kurar, yoksa tarayıcı katmanı sessizce SKIP'e düşer.
* **SKIP (ii) Tool Gateway günlüğü KAPANDI** — seed'e task eklenmedi; `[d5]` artık
  Coordinator'ın directive'den ürettiği **gerçek** task'ı bekliyor (`source=directive`,
  USER 403). Aynı bekleyiş **4. tavizsiz kuralı** "KABUL EDİLDİ"den "**TÜKETİLDİ**"e
  yükseltir. Günlük **sunuluyor** diye iddia edilir, **boş değil** diye değil.
* **SKIP (i) pozitif ESP `activate`→`deprecate` KALIYOR — gerekçesi düzeltildi.** Vektörler
  artık gerçek (`vectors_run` **0 → 2**); asıl engel **yapısal**: doğrulanabilir altı
  kanonik anahtarın **hepsi** `SEED_ESP_TA` ile `trusted_active` tohumlanır ve aktivasyon
  **yalnız `candidate`'ten** yasaldır → **kesişim boş**. `[c2]` `validation_state=failed`'i,
  `[c5]` `409 RESOLVER_VALIDATION_REQUIRED`'ı **pinler**.
* **Concurrency premisi bayattı** — `ci.yml` de `e2e.yml` de ADIM 34'ten beri onarılı; job
  `e2e.yml`'e kondu ki **zaten doğru** bloğu miras alsın (yeni workflow = kusurun geri
  gelmesi için ikinci şans). `e8d1d48`/`bc59dae`: `cancelled`, **`total_jobs=0`** — ama
  iptal edilen **`CI`**'dır, `e2e.yml` hiç kurban olmadı.
* **KAPATMADIĞI:** **P11-1 branch protection** (required status check olmadan bu kapı
  merge'i **durduramaz** — depo ayarı + insan kararı) · **A-08** dokunulmadı (#514
  2026-08-12'de bir **insan** tarafından yeniden **AÇILDI**; defter hâlâ boş).

Paste-ready resume prompt: `docs/ADIM45_LANDED_KICKOFF.md` en altta.

---

## Stage — ADIM 46: RC §6.6, iki canlı N+1 kapandı (PR #681)

**Migration:** yok. **Yeni tablo:** yok. **`ENGINE_VERSION`:** değişmedi. **OpenAPI:** değişmedi.

RC §6.6'nın iki **kod** kalemi kapandı: **#617** (`readiness_check.market_data_leg`,
`per_item` **1 → 0**) ve **#618** (`dependency_pins.ensure_pinned_resolvers_active`,
`per_item` **2 → 0**). İkisi de **kod yazılmadan önce** `c931063` üzerinde yeniden ölçüldü
(12 @ n=11 ve 22 @ n=11) — rapor bayat değildi, ADIM 42–45 hiçbirini kapatmamıştı.

**Reuse anchor'ları (tam sembol adlarıyla):**

- `infrastructure/postgres/repositories/market_data.py::get_dataset_roots` — YENİ batch
  okuyucu; `entity_type` kapısı **SQL'de**. Yeni bir per-item Root okuması yazacaksan bunu
  kullan, `get_dataset_root`'u döngüye sokma.
- `infrastructure/postgres/repositories/esp.py::get_registry_by_keys` — YENİ batch okuyucu;
  `canonical_key` UNIQUE olduğu için dict keying güvenli.
- `application/queries/dependency_pins.py::_prefetch` — iki batch'i **sırayla** kuran tek
  yer. **Sırayı bozma:** `embedded_revision_id` vermeyen ref entry'nin
  `trusted_active_revision_id`'sine düşer, revizyon id'leri registry'den SONRA bilinir.
- `application/queries/dependency_pins.py::_pin_defect` — artık **saf**; session almaz.
- `tests/integration/test_batched_dereference_equivalence.py` — 13 test, davranış
  eşdeğerliği. Yeni bir batch dereference eklersen buraya yaz.

**Kapı:** `docs/performance/query_budgets.json` iki satırda da `per_item: 0`. Bu bir
**ratchet**; N+1 geri gelirse slope assertion'ı kırmızıya döner. Dişi kanıtlandı.

**Test sayıları:** tam suite **3523 collected / 0 failed**, coverage **%93.66**.

**Dürüst sınır:** **blocker sayısı değişmedi (1)**, verdict **BLOCKED**. A-08 / #514
defteri hâlâ **boş** (0/4); #558 / #559 açık. **#617/#618'in issue durumu bir insan
kararıdır** — bu slice yalnız kodu kapattı.

Paste-ready resume prompt: `docs/ADIM46_LANDED_KICKOFF.md` en altta.

---

## Stage — ADIM 47: RC §6.7'nin iki PO kararı uygulandı (PR #682)

**Migration:** yok. **Yeni tablo:** yok. **`ENGINE_VERSION`:** değişmedi.
**OpenAPI: DEĞİŞTİ** (bilerek) — iki operation `200 → 202`, iki component eklendi;
path/operation **sayısı** aynı.

**(A) §6.7.9 / P8-B2 KAPANDI.** `POST /create-package/requests/{id}/validate` ve
`../baseline-parse` **200 → 202** (PO kararı **2026-08-12**). **Otorite karardır, kanonik
DEĞİL** — kanonik bu iki uç için hâlâ status vermiyor (`baseline-parse` için ucu bile
adlandırmıyor). Sevk edilmiş 202 deseni bir **olgu**dur, gerekçe değil; ADIM 41'in bu
çıkarımı reddi **hâlâ geçerli**. İki komut kod yazılmadan önce **yeniden ölçüldü**: ikisi de
`enqueue_job`'a ulaşıp iş bitmeden dönüyor → 202 doğru (senkron olsalardı slice DURACAKTI).

**(B) §6.7.5 / P10-B2 KAPANDI.** 9 kelepçeli `limit` **200 KALIR** (PO kararı 2026-08-12).
**Kod davranışı değişmedi**; kapanan şey gerekçenin yazılı olmamasıydı.

**Reuse anchor'ları (tam sembol adlarıyla):**

- `apps/api/routes/create_package.py::ValidationRunAcceptedResponse` (8 alan) ve
  `::BaselineParseAcceptedResponse` (8 alan) — YENİ tipli admission gövdeleri. Yeni bir
  admission ucu eklerken **bu şablonu** kullan; `dict[str, Any]` dönüşü sözleşmeyi şemadan
  gizler (O-30). Alanlar komutun döndürdüğü yer tutucuları **aynen** yansıtır — `checks: []`,
  `parser_version: ""`, `parse_report: {}`; sentezlenmiş bir verdict ASLA yazma.
- `tests/contract/test_p8b2_admission_status.py::_EXPECTED` — 13 admission ucunun kanonik
  status tablosu. Etiketler **ayrıdır**: `ALIGNED` (kanonik kodu adlandırdı) ≠ `PO <tarih>`
  (kanonik sessiz, insan seçti). **Birleştirme** — birleştiren okuyucu kararı atıf sanar.
  Yeni admission ucu **sınıflandırılmazsa** kapı kırmızıya döner (küme türetilir).
- `apps/api/pagination.py::clamped_limit_query` — kelepçeli `limit`'in TEK declarator'ı;
  modül docstring'i artık PO kararının gerekçesini taşır.
- `tests/contract/test_pagination_limit_contract.py` — iki invariant **birlikte** kilitli:
  kelepçeli parametre `x-clamp-maximum` **yayımlar** ve `maximum` **yayımlamaz**. İkisi
  birden emitleyen uç iki aileye birden girer ve karar şemadan okunamaz hâle gelir.

**Test sayıları:** hedef paketler geçti (`test_p8b2_admission_status` ·
`test_pagination_limit_contract` · `test_openapi_contract` · `test_typed_contract_openapi` ·
`test_create_package_contract`). `ruff`/`mypy` temiz, `generate_repository_facts --check` OK.

**Dürüst sınırlar:** **blocker sayısı DEĞİŞMEDİ (1 — A-08)**, verdict **BLOCKED**.
· **Tam suite YERELDE KOŞMADI** — bu container'da Postgres yok (docker daemon kapalı);
DB'ye bağlı testlerin **otoritesi CI'dır**. Tek yerel hata temiz ağaçta da üretildi (ortamsal).
· **Memory checkpoint YAZILAMADI** — `ecc`/`claude-mem` bu oturumda bağlı değil (ritüel md. 4 **eksik**).
· **`POST /library/{id}/validation-runs` 201'de KALDI** — PO kararı onu kapsamadı; iki
sarmalayıcı hâlâ farklı status döndürüyor, ayrışma **açık**.
· **§6.7 BİTMEDİ:** alt bölümlerde 12'de 11 kapalı (§6.7.10/P1-Gate3 açık), tabloda
**24 satırda 10 AÇIK** (P4-3 · P10-B6 · P11-1 · P11-6b · P11-3b · P8-B3b · P1-Gate3 ·
P10-B3/B4/B5). Kickoff'un *"on iki kalemin tamamı kapanır"* iddiası **yanlıştı, sayıldı.**

Paste-ready resume prompt: `docs/ADIM47_LANDED_KICKOFF.md` en altta.

---

## Stage — ADIM 48: K-6b, odak halkasının kontrastı (WCAG 1.4.11) (PR #688)

**Migration:** yok. **Yeni tablo:** yok. **`ENGINE_VERSION`:** değişmedi. **OpenAPI:**
değişmedi. **Ürün kodu değişikliği TEK deklarasyondur:**
`frontend/src/styles/global.css` `:focus-visible` → `outline: 2px solid var(--text)`
(eski: `var(--accent)`).

**Neden.** `--accent` (`#00a9e8`) odak halkası olarak **hiçbir** uygulama zemininde WCAG
**1.4.11 Non-text Contrast (AA)**'nın istediği **3:1**'i geçmiyordu: beyazda **2.68:1**,
`#f5f5f5`'te **2.46:1**, `.dropdown-blue` üzerinde **1.00:1** (görünmez). Sayılar kabul
edilmedi, sRGB relatif luminans formülüyle **sıfırdan yeniden hesaplandı** ve doğrulandı.
`var(--text)` (`#222222`) ile ölçülen: beyaz **15.91:1**, `#f5f5f5` **14.59:1**, `#e8e8e8`
başlık çubuğu **12.98:1**, `#00a9e8` panel **5.94:1**, `#8f8f8f` panel **4.92:1**, ve
**uygulamadaki en kötü zemin** `#0092c8` (`.menu-blue:hover`) **4.50:1** — hepsi ≥ 3:1.

**Bunu repoda hiçbir şey ölçmüyordu:** axe odak halkası için kontrast kuralı **koşmaz**;
a11y/Lighthouse/görsel kapıların yeşil olması bu soru için **kanıt değildi**.

**Reuse anchor'ları (tam sembol adlarıyla):**

- `frontend/src/styles/global.css` `:focus-visible` — halkanın **TEK** tanımı. Yorumu artık
  ölçülmüş oranları ve zemin kümesini taşıyor. Yeni bir odak stili yazma, buradan geçir.
- `docs/audit/a11y_screen_reader_audit_results.md` §6 — **K-6 İKİYE ayrıldı**: `K-6b`
  **KAPANDI** (ölçülü), `K-6a` (*"insan görebiliyor mu"*) **AÇIK** ve **yalnız A-08**
  kapatabilir. Sayım tablosundaki satır da `K-6a` oldu.
- `pages/RationaleFamilies.tsx:368` — inline `outline: 2px solid var(--accent)` **bilerek
  bırakıldı**: o bir **seçim** göstergesi, odak halkası değil; ayrı ölçüt, ayrı karar.

**Neden bu bir v18 sapması DEĞİL:** v18 mockup'ı **hiçbir odak durumu tarif etmiyor**
(`:focus` / `:focus-visible` / halka görseli yok) — tarif edilmeyen bir şeyden sapılamaz.
`--accent` token'ı, dolgu, kenarlık ve link paleti **hiç dokunulmadı**; onları değiştirmek
sapma **olurdu**. **Bu D-10 de DEĞİL:** D-10 **1.4.3** (metin) eksenidir, bu **1.4.11**
(metin-dışı) — ayrı ölçüt, ayrı eşik; metin sapmasına verilmiş imza buraya genişletilemez.

**Test sayıları:** `npm run lint` exit 0 · `npm run typecheck` exit 0 ·
`npm test -- --no-file-parallelism` → **721 passed / 70 dosya** (ADIM 25 tabanıyla
**birebir aynı**; hiçbir test yeniden hizalanmadı).

**Dürüst sınırlar:** **blocker sayısı DEĞİŞMEDİ (1 — A-08)**, verdict **BLOCKED**.
· **K-6a AÇIK** — bu slice onu kapatmadı, kapattığını da iddia etmiyor.
· **`npm run visual` ve `npm run a11y` YERELDE KOŞMADI** — docker daemon başlatıldı ama
ortamın ağ politikası `production.cloudfront.docker.com`'a CONNECT'i **403** reddediyor,
`registry-1.docker.io` **429** veriyor; imaj çekilemedi (üç deneme). **Otorite CI'dır**
(`e2e.yml::e2e` görsel kapı + `e2e.yml::a11y` axe ratchet, ikisi de bloklayıcı). Yerelde
**statik** olarak kanıtlandı ki taban ekran görüntüleri odaklanmış öğe **yokken** alınır
(`specs/11-visual-regression.spec.ts` içinde `focus`/`blur`/`activeElement` **geçmiyor**;
tek `autoFocus` `Login.tsx:157` ve o **23 rotanın hiçbirinde değil**) → beklenen **0 diff**.
**Diff çıkarsa tabanı GÜNCELLEME** — kural odak dışına sızmış demektir, selector'ı daralt.
· **Memory checkpoint YAZILAMADI** — `ecc`/`claude-mem` bu oturumda da bağlı değil
(ritüel md. 4 **eksik**); **ADIM 47 ile üst üste ikinci oturum**, borç birikti.

Paste-ready resume prompt: `docs/ADIM48_LANDED_KICKOFF.md` en altta.

---
## Stage — ADIM 48: kabul borcu sınıf B, parti 01 (doc 05 Trade Log backend yüzeyi)

**Blocker sayısı DEĞİŞMEDİ (1 — yalnız A-08), verdict BLOCKED.** Bir blocker kalemi
değil: ADIM 42'nin ürettiği borç defterini **işlemeye başlayan** ilk parti. **Ürün kodu
DEĞİŞMEDİ** (tek satır bile) · migration yok · `ENGINE_VERSION` sabit · OpenAPI sabit ·
OCC / Idempotency / route yolları / react-query key'leri sabit.

**Kapanan sekiz sınıf-B kriteri** (hepsi doc 05 §16, hepsi backend server-truth):
`TL-03` (boş `display_name` → 422 **ve** hiçbir revision/pin yazılmaz) · `TL-06`
(tırnaklı alan içindeki ayraç) · `TL-07` (rapor **satır numarasını** adlandırır) ·
`TL-08` (non-finite fiyat) · `TL-15` (Pin replay'i çift satır yazmaz) · `TL-17`
(**Admin yabancı Trade Log'u değiştirebilir**; Supervisor **edemez**) · `TL-21`
(Supervisor Trash yüzeylerinde reddedilir) · `TL-23` (Trade Log save/import/export
hiçbir Result üretmez).

**Ratchet — yalnız AŞAĞI:** `partial` **126 → 118**, `debt_class.B` **95 → 87**.
`uncovered` (8) · A (1) · C (6) · **D (32)** tavanları **el değmeden** kaldı;
`total_criteria` **383'te sabit** (taban). Defter `--write-ledger` ile yeniden üretildi.

**"İşaretlemek ≠ kapsamak":** vakumda geçebilecek her assertion **negatif kontrolden**
geçirildi — `TL-15`'te `Idempotency-Key` çıkarılınca çağrı `ROW_VERSION_CONFLICT` veriyor,
`TL-17`'de `ADMIN` yerine akran `USER2` konulunca test `AccessDenied` ile düşüyor.
Kanıt: `PROJECT_HISTORY.md` §ADIM 48.

**İki BULGU açık bırakıldı (insan/PO kararı, agent kapatamaz):** `TL-16`'nın sınıfı
**şüpheli** — `c4`'ün istediği "409 kanonik durum" alanı **yok**
(`WorkObjectRevisionConflictError` `details` taşımıyor), yani B değil **D** görünüyor;
yeniden sınıflandırılmadı çünkü **D tavanını yükseltirdi**. `TL-01.c4` bir **yol
sapması**: kriter `GET /packages` diyor, sevk edilen katalog `GET /library`.

**Sıradaki parti (gerekçesi kickoff'ta):** `TL-11.c3` + `TL-12.c3` + `TL-20.c3` —
üçü de *Trade Log içeren kompozisyon üzerinde tamamlanmış Backtest Run* harness'ını
ister; harness bir kez kurulunca üçü birden kapanır ve doc 04'ün `TS-11`/`TS-21`
ikizlerini de açar.

**P1-Gate3 KAPANMADI** — kalan borç A=1 · B=87 · C=6 · D=32 (açık toplam **126**).
Tam kayıt: `PROJECT_HISTORY.md` §ADIM 48 · kickoff: `docs/ADIM48_LANDED_KICKOFF.md`.

## Stage — ADIM 49: P11-1 KAPANDI, main'de required status check ruleset'i (PR #683)

**Landed:** PR #683 (`74bbd70`) + **repo ayarı** ruleset `20765617` (insan uyguladı,
2026-08-12T23:14:40+03:00). **Migration yok · `ENGINE_VERSION` değişmedi · ürün
ağaçlarına (`backend/src`, `alembic`, `frontend/src`) HİÇ dokunulmadı.**

RC §6.7'nin **repo dışı** tek kalemi kapandı. Öncesi ölçüldü: `GET /rulesets` → `[]`,
`GET /rules/branches/main` → `[]`, `branches/main` → `enforcement_level: "off"`.
Yani ADIM 45'in `flows` kapısı dâhil **on altı kapı** merge'i durdurmuyordu.

**Yeni dosyalar (reuse anchor'ları):**
- `.github/rulesets/main-required-status-checks.json` — 16 context, hepsi
  `integration_id: 15368`; `deletion` · `non_fast_forward` · `pull_request`
  (`required_approving_review_count: 0`) · `required_status_checks`
  (`strict_required_status_checks_policy: true`). **GitHub bu yolu otomatik OKUMAZ.**
- `scripts/required-checks-preflight.sh` — POST öncesi **zorunlu** salt-okuma kapısı;
  payload'ı üretilen check adlarıyla diff'ler, göremediğini `FATAL` + `exit 1` yapar.
- `docs/implementation/required_status_checks_setup.md` — runbook (§2.1 Lighthouse kararı,
  §3 komut, §5 uyarılar, §6 geri alma, §7 bakım sırası).

**Sınıflandırma:** 16 zorunlu · 1 ayrıldı (çıplak `CodeQL` — farklı app `57789`,
PR-only, alert triage) · 5 gürültü (nightly/manual; `Nightly failure notice` **iki
workflow'dan aynı adla** gelir, tek-anlamlı required yapılamaz).

**Lighthouse insan kararıyla ZORUNLU** (ilk taslak varyans gerekçesiyle ayırmıştı).
Çırpınırsa **taban indirilmez**: skor `LH_REPEATS` medyanıdır → tekrar sayısını artır.
**`armed: false` + boş `floors` spec'i GEÇİRİR** → required olduktan sonra bu bayrak
kapının **sessiz kapatma düğmesidir**.

**Doğrulandı (canlı ↔ main'deki payload, programatik):** 16 ad + `integration_id`
sıra dâhil birebir · `/rules/branches/main` = 4 kural · `strict: true` ·
`current_user_can_bypass: "never"` · **kilitlenme kontrolü: üretilmemiş ad YOK**.

**Dürüst sınırlar:** `bypass_actors` salt-okuma token'ına görünmüyor (kanıt POST
yanıtı) · **ruleset repoda değil** — silinirse hiçbir CI kapısı fark etmez, drift
kapısı **yazılmadı (açık iş)** · **A-08 DEĞİŞMEDİ** (blocker 1, verdict BLOCKED) ·
**memory checkpoint yine yazılamadı** → borç **ADIM 47 + 48 + 49**, üç oturum;
sahnelenmiş içerik `docs/memory/PENDING_CHECKPOINTS.md` (bu slice Entity C'yi ekledi).

**Artık geçerli:** main'e doğrudan push kapalı; her PR 16 yeşil check + main ile
güncellik ister (`Backend` ~48 dk — bilinçli bedel, runbook §3'te tek alanı çeviren
komut var); muafiyet yok, sahibi dâhil. Kurtarma: ruleset `20765617` → `Disabled`/sil.

Tam kayıt: `PROJECT_HISTORY.md` §ADIM 49 · kickoff: `docs/ADIM49_LANDED_KICKOFF.md`.

## Stage — ADIM 50: RC §6.5'in K-2 ve K-4'ü KAPANDI (PO kararı, PR #685)

> **NUMARA NOTU:** bu slice ADIM 48 olarak başladı; `#686` main'e ADIM 48 adıyla merge
> edilince **merge edilmiş ad kazandı** ve bu slice ADIM 49'a taşındı. Branch'in commit
> mesajları `adim-48` yazmaya devam eder — yazılmış commit mesajı değiştirilmez.

**Migration:** yok. **Yeni tablo:** yok. **`ENGINE_VERSION`:** değişmedi.
**OpenAPI:** değişmedi. **OCC / Idempotency / route yolları / react-query key'leri /
`app/nav.ts`:** değişmedi. Presentation-only frontend + belge kaydı.

**Nasıl başladı:** kod değil, **karar brifingi**. Beş gözlemin (K-2..K-6) her biri için
ne / kaç rotada / hangi ölçüt · **ölçülen** düzeltme maliyeti · düzeltmemenin bedeli ·
öneri → `docs/ADIM50_KICKOFF.md` (dört paste-ready prompt: P-1..P-4). PO **P-1**'i seçti.

**(A) K-2 KAPANDI.** `app/Layout.tsx` shell'in ilk çocuğu olarak clip'lenmiş
`Skip to main content` linki; `<main>` `id="main-content"` + `tabIndex={-1}`.
**Kayda geçen düzeltme:** WCAG 2.4.1 landmark'larla (ARIA11) **zaten karşılanıyordu**
(axe `bypass` hep yeşildi) → bu bir **ergonomi** düzeltmesiydi, uygunluk düzeltmesi değil.

**(B) K-4 KAPANDI.** `/user-manual` artık `<h1 class="page-title">`. `.page-title` sınıf
tabanlı → **0 görsel diff** — ÖLÇÜLDÜ: `@visual` job `94223919309` **23/23 passed**,
hiçbir baseline yeniden üretilmedi. **Yan etki:** sayfa `h2 → h3` iken atlama taşımıyordu,
`h1 → h3` olunca taşıyor → **K-5'in kümesine girdi**: CI job `94221023796`
**K-5 21 / 23 → 22 / 23**, toplam advisory **90 → 67**. Tek ve **soğuk** koşu →
22 bir **taban**. Döküm: `docs/audit/a11y_screen_reader_audit_results.md` §6.

**(C) K-6 İKİYE AYRILDI.** **K-6a** (halka görünüyor mu, 2.4.7) A-08 bekliyor **ve mevcut
sondanın çıktısı ona kanıt DEĞİL** (programatik `el.focus()` `:focus-visible`'ı
eşleştirmez; halka `global.css`'te yazılı). **K-6b** (kontrast, 1.4.11) **ölçüldü ve
düşüyor**: `#00a9e8` ↔ beyaz **2.68 : 1** < 3 : 1; axe bu kuralı koşmuyor, D-10 (1.4.3)
kapsamıyor → **PO kararı bekliyor**.

**Reuse anchor'ları (tam sembol adlarıyla):**

- `frontend/src/app/Layout.tsx` → `.skip-link` + `<main id="main-content" tabIndex={-1}>`
  — **yeni bir shell landmark'ı eklerken** bu üçlüyü birlikte düşün: link / hedef id /
  odaklanabilirlik. Biri eksikse link sessizce hiçbir şey yapmaz.
- `frontend/src/styles/global.css` → `.skip-link` / `.skip-link:focus` — clip deseni
  (**negatif offset DEĞİL**; odaklanan ekran-dışı öğe sayfayı yana kaydırır) ve tetikleyici
  **`:focus`**, `:focus-visible` değil (K-6a hâlâ açık).
- `frontend/src/test/skipLink.test.tsx` — K-2'nin **üç parçalı** sözleşmesi; negatifi
  kanıtlı (kırık `href` → exit 1, `tabIndex` yok → exit 1). **Yalnız "link var" assert
  eden bir test yazma** — hedef adı değişince yeşil kalır.
- `frontend/e2e/specs/17-page-coverage.spec.ts` → `/user-manual` `level: 1` — K-4'ün
  regresyon pini **burada**, precheck'te değil: **eksik `<h1>`'i BLOCKING yapmak
  değerlendirildi ve bilerek yapılmadı** (sonda ilk DOM'u okur, veri render'ıyla yarışır →
  çırpınan kapı). Gerekçe `specs/20-a11y-prechecks.spec.ts` içinde yazılı.

**Testler:** frontend **722 passed / 71 dosya** (ölçüldü, `--no-file-parallelism`);
coverage kapısı geçti (**line %84.90**). Backend'e dokunulmadı.

**Açık kalan (bu slice kapsamadı):** **K-3** (footer/checklist kararı) ve **K-6b**
(halka rengi) → ikisi de **A-08'e bağımlı DEĞİL**, ikisi de **PO kararı** bekliyor;
prompt `docs/ADIM50_KICKOFF.md` §P-2 (K-3). **K-6b `#688`'de KAPANDI.** **K-5 + K-6a** → **A-08 bekliyor**.
**A-08'e dokunulmadı:** defter boş (0/4), `#514` kapalı, **blocker sayısı 1**, verdict
**BLOCKED**.

## Stage — ADIM 52: kabul borcu sınıf B, parti 02 (dış work object run provenance'ı)

**Blocker sayısı DEĞİŞMEDİ (1 — yalnız A-08), verdict BLOCKED.** **Ürün kodu
DEĞİŞMEDİ** (tek satır bile) · migration yok · `ENGINE_VERSION` sabit · OpenAPI sabit.

**Kapanan beş kriter:** `TL-12` (c2+c3) · `TL-20` (c3) · `TS-11` (c3) · `TS-21` (c1) ·
`AOS-21` (c1) — hepsi tek yeni modülde
(`tests/integration/test_external_object_run_provenance.py`).

**Eksik olan tek şey bir harness'tı:** *dış work object içeren kompozisyon üzerinde
TAMAMLANMIŞ bir Backtest Run*. Repoda yoktu. Sıfırdan yazılmadı — `_ready_composition`,
`_e2e_bars` ve `_attach_trading_signal` aynen kullanıldı; yalnız `_attach_trade_log`
eklendi (gerçek boru hattı: upload → import worker → Save & Add).

**Ratchet — yalnız AŞAĞI:** `partial` **118 → 113**, `debt_class.B` **87 → 82**.
`uncovered`/A/C/**D** tavanları el değmedi, `total_criteria` **383 sabit**. Yapısal
diff: 6 kayıt değişti, hiçbiri silinmedi, clause **1175 → 1175**.

**BULGU — `TL-11.c3` KAPATILAMAZ ve ADIM 48'in önerisi YANLIŞTI.** Kriter
*allocation-enabled* bir run istiyor; shared allocation bu build'de **admission'da
fail-closed** (`SHARED_ALLOCATION_STATUS = "future_dev"` →
`ALLOCATION_SHARED_MODE_NOT_IN_BUILD`, run/manifest/job yaratılmadan). Sınıfı **C**
görünüyor; **yeniden sınıflandırılmadı** çünkü **C tavanını yükseltirdi**. Artık ÜÇ
açık bulgu var: `TL-11.c3`, `TL-16`, `TL-01.c4` — üçü de insan/PO kararı.

**Ad çakışması onarıldı:** iki bağımsız slice kendini "ADIM 48" olarak adlandırıp aynı
kickoff dosyasına yazmıştı. Numaralar **yeniden atanmadı**, ayrım **başlık ekiyle**
yapıldı: `ADIM 48 (K-6b)` (#688) · `ADIM 48 (kabul borcu B-01)` (#686). İçerik
silinmedi. `repository_facts --check` bunu yakalamıyor (kuralı dosya başına bakar).

**P1-Gate3 KAPANMADI** — kalan borç A=1 · B=82 · C=6 · D=32 (açık toplam **121**).
Tam kayıt: `PROJECT_HISTORY.md` §ADIM 52 · kickoff: `docs/ADIM52_LANDED_KICKOFF.md`.

## Stage — ADIM 53: hafıza türetilir oldu (agentmemory) + iki sessiz ajan kapısı (PR #694)

**Ürün kodu değişmedi** — `backend/src`, `alembic`, `frontend/src` el değmedi; migration yok,
`ENGINE_VERSION` ve OpenAPI değişmedi. **A-08 blocker AÇIK, verdict BLOCKED** (bu slice ölçmedi).

* **Kapanış ritüeli md. 4 yeniden yazıldı (insan kararı, 2026-08-13).** Memory checkpoint artık
  **elle yazılmıyor, türetiliyor**: `node scripts/memory_index.mjs --write --only <slug>`.
  Tek doğruluk kaynağı `docs/PROJECT_HISTORY.md`; `agentmemory` onun **aranabilir indeksi**.
  Efemer container artık borç doğurmuyor — `--write` altı saniyede hepsini yeniden üretir.
  `docs/memory/PENDING_CHECKPOINTS.md` **silindi**; ADIM 47/48/49 borcu **kapandı**.
* **Yeni dosyalar:** `scripts/memory_index.mjs` (`--emit` / `--check` / `--write` / `--only`),
  `scripts/agent-config-gate.mjs` (4 kontrol, **dördünün de negatifi kanıtlı**).
  `.mcp.json`'a **pinli** `@agentmemory/mcp@0.9.28` eklendi; otomatik yakalama **KAPALI**.
* **YENİ BULGU — `.claude/settings.json` #651'den beri GEÇERSİZ JSON'du.** `docs-history-guard`
  (#590/#604 docs regresyonuna karşı yazılan kapı) ve `ultrareview-advisor` aradaki **her
  oturumda ölüydü**. Onarıldı; kapının çalıştığı iki yönlü kanıtlandı (silinen başlıkta exit 2).
* **`plugins/entropia-maintenance` hiçbir yerde etkin değildi** → `settings.json`
  `extraKnownMarketplaces` + `enabledPlugins`. Plugin `0.3.0` → `0.4.0`.
  **Etkisi bu oturumda doğrulanamadı** (plugin'ler oturum başında yüklenir) — bir sonraki
  oturumda görülecek.
* **CI:** iki yeni **adım** (`Frontend` job'ının içinde, **yeni job DEĞİL** — ruleset `20765617`
  adları başlıkla tanır, üretilmeyen ad tüm merge'leri kilitler): `agent-config-gate.mjs` ve
  `memory_index.mjs --check`. Job adı değişmedi, ruleset'e dokunulmadı.
* **Hiçbir skill/ajan silinmedi** — bayat çıkmadı; kusur *hiç yüklenmiyor olmalarıydı*.
* **Dürüst sınır:** semantik geri çağırma **yok** (sunucusuz kip harf eşleşmesi; kalıcı sunucu
  barındırmak insan kararı) · backend/frontend suite'leri bu oturumda **koşmadı** (Postgres ve
  `node_modules` yok) → **otorite CI** · `--write` toplayıcıdır, upsert yok.

Ayrıntı: `docs/PROJECT_HISTORY.md` §ADIM 53 · `docs/ADIM53_LANDED_KICKOFF.md` · `CLAUDE.md` §Hafıza.

## Stage — ADIM 54: kabul borcu sınıf B, parti 03 (Research Data revizyon değişmezliği)

**Blocker sayısı DEĞİŞMEDİ (1 — yalnız A-08), verdict BLOCKED.** Ürün kodu **DEĞİŞMEDİ**;
migration yok, `ENGINE_VERSION`/OpenAPI sabit. **`partial` 113 → 111, `debt_class.B` 82 → 80.**

**Kapananlar:** `RD-04` (c3) · `RD-06` (c2). Ayrıca `RD-09.c3` clause'u kapandı ama
**`RD-09` partial KALDI** (c4 açık) — yarım kanıtla işaretlenmedi, tavanı hareket ettirmedi.

**RD-04'ün dersi:** kriterin sözü (*"stale işaretlenir"*) ile sevk edilen davranış aynı
şey değildi; sevk edilen daha güçlü ve yapısal (onaylı revizyon yeniden zamanlanamaz,
replacement DRAFT doğar, `DRAFT → APPROVED` yasal değil). Test bayrak **icat etmedi**.
İki tuzak testin içine yazıldı: politika önce kurulmazsa **yanlış refüz** kanıtlanıyor,
onay **Admin-only**.

**RD-09.c4 neden açık:** manifest research revizyonunu **yalnız funding kaynağı**
üzerinden pinliyor; readiness funding revizyonunun stratejinin **kendi** market
revizyonuna bağlı olmasını istiyor, worker da native asset satırları çözülmezse
`RUN_FAILED_FUNDING_SOURCE_INVALID` veriyor. Uçtan uca bağlamak partiyi aştı.
`_ready_composition`'a denenen parametreler **geri alındı**.

**ÜÇ yeni bulgu (insan/PO):** `RD-01.c4` · `RD-05.c5` · `RD-11.c2` — üçü de sevk
edilmemiş alan/araç adlandırıyor, hiçbiri yeniden sınıflandırılmadı (tavan yükseltirdi).
Defterde artık **beş** açık bulgu var; **parti seçmeden ÖNCE ÖLÇ**.

**P1-Gate3 KAPANMADI** — kalan borç A=1 · B=80 · C=6 · D=32 (açık toplam **119**).
Tam kayıt: `PROJECT_HISTORY.md` §ADIM 54 · kickoff: `docs/ADIM54_LANDED_KICKOFF.md`.

## Stage — ADIM 55: agentmemory sunucusu yerele alındı, semantik geri çağırma (PR #699, `c4cd932`)

**Ürün kodu değişmedi.** Migration yok, `ENGINE_VERSION`/OpenAPI aynı. **A-08 blocker AÇIK,
verdict BLOCKED** (bu slice ölçmedi).

* **Barındırma GEREKMEDİ.** Sunucunun kazandırdığı şey kalıcılık değil **geri çağırma
  kalitesi**; kalıcılık ADIM 53'te indeks türetilerek çözülmüştü. `.mcp.json` artık
  `scripts/memory_mcp.sh`'ı çağırıyor: **önce sunucuyu yerelde kaldır, sonra shim'e dön**.
* **Ölçülen:** araç 7 → **53** · soğuk kalkış **33 sn** (npx cache sıcakken 4 sn) ·
  **LLM anahtarı gerekmiyor** (`zero-LLM: BM25 + on-device embeddings`) · İngilizce
  `focus ring contrast accessibility` sorgusu sunucusuz **boş**, sunucuyla Türkçe
  **§ADIM 48** kaydını buluyor (çapraz-dilli).
* **`memory_index.mjs --sync`** — ADIM 53'ün *"`--write` toplayıcıdır"* tuzağını kapatır:
  REST export'tan mevcut `§başlık` işaretlerini okuyup yalnız eksikleri yazar. Sunucu
  yoksa çoğaltmak yerine exit 1 verir.
* **İki kusuru kendi negatif kontrolüm yakaladı:** (a) sunucu `III_REST_PORT`'a bağlanır,
  URL'deki porta değil → port türetiliyor; **tek makinede tek örnek** koşabilir (iii
  engine portu sabit). (b) `agent-config-gate.mjs` MCP komutu `npx` değilse pin
  kontrolünü **atlıyordu** ve zincir takibi `"$ROOT/..."` yüzünden hiç çalışmıyordu →
  **gate kendi negatifini geçmişti**, düzeltildi.
* **Dürüst sınır:** soğuk container'da ilk MCP bağlantısı ~33 sn gecikir (oturumu
  bloklamaz) · suite'ler koşmadı → **otorite CI** · otomatik yakalama hâlâ KAPALI.

Ayrıntı: `docs/PROJECT_HISTORY.md` §ADIM 55 · `docs/ADIM55_LANDED_KICKOFF.md` · `CLAUDE.md` §Hafıza.

## Stage — ADIM 56: A-08 denetimi BAŞLADI, SR-2 oturum 1 kaydı (PR #684)

**Ürün kodu DEĞİŞMEDİ** (docs-only). Migration yok, `ENGINE_VERSION` değişmedi.
**Blocker sayısı DEĞİŞMEDİ (1 — yalnız A-08), verdict BLOCKED.**

**Defter boş olmaktan çıktı**, ama sayılar bunu bir sonuç sanmaya izin vermiyor: bir insanın
duyduğu **2 hücre** (rota 1 `/`, `A-1 PASS` + `A-2 PASS ᴷ³`) = **184'ün 2'si**, **0/10 akış**,
**0 bulgu**, **0/23 rota TAM**. **SR-1 hiç başlamadı** → çıkış kriterleri **0/4** ve kriter
1/2 bir SR-2 koşusuyla **kapatılamaz** (ikisi de iki kombinasyon ister). Denetçi
**`neither`** (ürün sahibi kendi koştu) — rol **hâlâ atanmadı**.

Yumuşatılmayan üç kayıt: `A-2 PASS` **üç** landmark demek (`contentinfo` yok, K-3) ·
**`A-3` bilerek `—`** çünkü *"atlamayı fark etmedim"* cevabı "yanılmadım" ile "bakmadım"ı
ayırmıyor → **K-5 AÇIK** · 2/184'ten sonra **0 bulgu temiz rapor değil**, örneklem çok küçük.

İkinci yarı: **`CLAUDE.md`'nin bayat A-08 bloğu** düzeltildi — #514 `2026-08-12T11:08:58Z`'de
yeniden açılmıştı, **#687 defterleri uzlaştırdı ama rehbere dokunmadı**. Ayrışma **(B) yolu
ile çözüldü**; (A) imzalı sapma **hiç yazılmadı ve yazılmamalıdır**. **Kullanıcı issue'nun
açık kalmasına karar verdi**; agent onu ne kapatabilir ne açabilir.

**Süreç bedeli (tekrarlanmasın):** P11-1 ruleset'i ilk kez kapı oldu — **22/22 yeşilken merge
reddedildi** (`405`, dal main'in gerisindeydi, `strict` politika); çözüm **main'i içeri almak**,
bypass değil · **#687 aynı işi yaptı**, çakışan hunk'larda main kazandırıldı · **`-X theirs`
sözleşme testinin pinlediği bir cümleyi sessizce düşürdü** → her strateji-çözümünden sonra
sözleşme testini koştur · `Backend` job'ı **85 dk**'ya kadar çıktı ve **koşarken log'u 404**.

**NUMARA: bu slice AYNI GÜN İKİ KEZ taşındı** — önce ADIM 54 yazıldı, #701 o adı merge
edilmiş olarak aldı → 55; sonra #699 55'i aldı → **56**. Kural: numaralar yeniden atanmaz,
**merge edilmiş ad kazanır**. Dal commit mesajları `adim-54`/`adim-55` yazar. **Ders:
kapanış belgelerini yazmadan önce `git fetch && grep '^## ADIM' docs/PROJECT_HISTORY.md`
ile numarayı doğrula — paralel oturumlar birbirini görmüyor.**

Ayrıntı: `docs/PROJECT_HISTORY.md` §ADIM 56 · `docs/ADIM56_LANDED_KICKOFF.md`
(paste-ready resume prompt en altta).

## Stage — ADIM 57: K-3 ADJUDICATED — imzalı karar D-11, KOD YOK

> **NUMARA NOTU:** ADIM 54 yazıldı, 55 ve 56 denendi, **ADIM 57** oldu — merge beklerken
> `#701` 54'ü, `#699` 55'i, `#697` 56'yı merge edilmiş adla aldı (DÖRT taşıma). Numaralar
> yeniden atanmaz; taşınan taraf merge edilmemiş olandır. Branch commit mesajları
> `adim-54` yazar. Üçünün de kaydına dokunulmadı — yalnız `doc-status` düşürüldü.
> **Sebep yapısal:** `Backend` ~50 dk + ruleset `strict: true` → yoğun günde koşu bandı
> (bu slice **beş tur** döndü). **Çare bu turda uygulandı: auto-merge.**

**Migration:** yok. **Kod:** **tek satır bile değişmedi** — `backend/src`, `frontend/src`,
`alembic` ağaçlarına dokunulmadı. **OpenAPI / OCC / Idempotency / route / query-key /
`ENGINE_VERSION`:** değişmedi. Bu bir **karar kaydı** slice'ıdır.

**Ne kapandı.** RC §6.5'in **K-3**'ü (`contentinfo` landmark yok, 23/23 route). PO
`docs/ADIM50_KICKOFF.md` §P-2'yi **Varyant A** ile uyguladı: footer eklenmedi, **beklenti**
hizalandı.

**Reuse anchor'ları (tam adlarıyla):**

- `docs/implementation/a11y_ci_ratchet_and_adjudication.md` **§4b → `Karar # : D-11`** —
  imzalı a11y kararlarının **sicili** artık bu belge (D-10 kontrast + D-11 landmark).
  Yeni imzalı a11y kararı buraya, **aynı** `Karar # / Onaylayan / Tarih / Kayıt` bloğuyla
  yazılır. **İmzalayan adı olmadan blok YAZILMAZ.**
- `docs/implementation/a11y_screen_reader_audit_checklist.md` **A-2 satırı** — beklenti
  artık **ÜÇ** landmark (`banner`/`navigation`/`main`); `contentinfo` **beklenmez**.
  A-08 denetçisi bu satırı okur; dört landmark arayan bir denetçi yanlış `FAIL` yazardı.
- `docs/audit/a11y_screen_reader_audit_results.md` §1 A-2 madde metni + route 1 dipnotu
  **ᴷ³** + §6 K-3 satırı — üçü **aynı** gerçeği söyler; biri değişirse üçü değişir.

**Kararın dayanağı — biri insan, biri makine.** (1) Hiçbir WCAG SC'si `contentinfo`
zorunlu kılmaz; 1.3.1 *var olan* yapıyı ister. Eski `1.3.1 / 2.4.1` etiketi kalemi
olduğundan ağır gösteriyordu, düzeltildi. (2) **A-08'in SR-2 oturumu bu soruyu zaten
cevaplamıştı:** route 1'de denetçi üç landmark duydu, yokluğu **kozmetik** buldu. Tek
rota karar vermeye yetmez, ama makine sayısıyla (23/23 yok) **aynı yöne** bakıyor.

**Reddedilen iki seçenek, gerekçeleriyle kayıtta:** görünür footer (v18'de footer YOK →
zorunlu görsel referans ihlali + 23 baseline + Lighthouse yeniden tabanlama + yeni v18
sapma kaydı) ve **boş/gizli footer** (sayacı yeşile çevirir, rotor kullanıcısına hiçbir
şey vermez — *ölçüyü ürüne değil ölçüme uydurmak*).

**Yan iş — main'de duran bir hasar onarıldı.** §6'nın K-tablosunda **K-4, K-5 ve K-6
satırları İKİ KEZ** vardı: ikinci küme bayattı (K-4 `Open`, K-5 `21/23`) ve ADIM 50 ile
#688'in aynı tabloyu düzenlemesinden kalan bir **merge artefaktıydı**. Üç fazla satır
silindi; tablo artık her kalem için **tek** satır taşıyor (K-1, K-2, K-3, K-4, K-5, K-6a,
K-6b, K-7). Bu bir yargı düzeltmesi değil, **çift kaydın** temizliğidir.

**Tavizsiz sınırlar (bu slice'ta pinlendi):**

1. **Advisory SUSTURULMADI.** K-3'ün `::warning::` satırı 23 rotada çıkmaya devam eder.
   Karar **dispozisyonu** belirler, ölçümü değil. Sonda çıktısını kırpan bir "temizlik"
   bu kararı yanlış okumuş olur.
2. **D-11 gelecekteki footer'ı KAPSAMAZ.** Ürün gerçek footer içeriği (sürüm / ortam /
   yasal metin) isterse bu **yeni** bir karardır ve bir v18 sapma kaydı gerektirir.
3. **Bu bir WCAG uyumluluk iddiası DEĞİL** — ama bir uyumluluk **eksiği** de değil.
   D-10 ile karıştırma: D-10 gerçek bir ihlali (1.4.3) imzalar, D-11 **olmayan bir
   yükümlülüğü** kaydeder.

**A-08 DEĞİŞMEDİ:** defter **2 / 184** hücre (yalnız SR-2), SR-1 hiç başlamadı, çıkış
kriterleri **0 / 4**, `#514` **açık**. **Blocker sayısı 1 (yalnız A-08), verdict BLOCKED.**
K-3'ün kapanması A-08'i **ilerletmez**; bu kalem hiç blocker değildi.

**Açık kalan:** **K-5** (22/23, maliyet ölçülü: 204 başlık / ~40 dosya / 5 tag-scoped CSS
kuralı) ve **K-6a** — ikisi de **yalnız A-08** ile kapanır. **K-7** ölçüldü, düzeltilmedi.

## Stage — ADIM 58: plugin hook'ları kurulumdan bağımsız oldu (iki bloklayıcı guard)

**Ürün kodu DEĞİŞMEDİ** (`backend/src`, `alembic`, `frontend/src` el değmedi). Migration
yok, `ENGINE_VERSION` değişmedi. **Blocker sayısı DEĞİŞMEDİ (1 — yalnız A-08), verdict
BLOCKED.**

**Ölçüm önce, karar sonra: `enabledPlugins` KURULUM DEĞİLDİR.**
`/root/.claude/plugins/installed_plugins.json` bu container'da `{"version":2,"plugins":{}}`
— **boş**. Yani ADIM 53'ün *"depoya güvenen her oturumda önerilir/etkinleşir"* cümlesi
remote'ta **yanlıştı** ve `guard-git.sh`'in docs-regresyon kapısı — #590/#604'ten sonra tam
onları durdurmak için yazılmıştı — **hiç koşmamıştı**. Sebep yapılandırma hatası **değil**
(`agent-config-gate.mjs` adı çözüyor, yeşil): kurulum bir **onay istemi** ister, remote
container etkileşimsizdir.

**Ne landed:** `.claude/settings.json` artık `guard-git.sh` (Bash) ve `guard-generated.sh`
(Edit/Write/MultiEdit/NotebookEdit) betiklerini `${CLAUDE_PROJECT_DIR}` üzerinden
**doğrudan** kaydediyor. **Dosya kopyalanmadı** — tek kaynak plugin'in içinde, ikilenen
yalnız **kayıt**. `${CLAUDE_PLUGIN_ROOT}` kullanılamazdı: onu plugin çalıştırıcısı kurar.

**Çift koşma bilinçli bir tavizdir ve `plugins/entropia-maintenance/README.md` §Çift koşma'da
gerekçesiyle yazılıdır** — *"kopya bırakılmadı"* kararı sessizce çiğnenmedi, açıkça gözden
geçirildi ve kapsamı **dosya**yla sınırlandı. Bedel ölçüldü: **≈25 ms/çağrı** (20 koşu:
24 / 27 ms), yan etki yok, iki guard da salt-okur + idempotent. Alternatifi
(*"kuruluysa atla"*) **fail-open**'dır; çift koşma fail-closed. **Yalnız BLOKLAYAN ikisi**
ikilendi — `post-edit-lint` / `session-brief` / `vendor-react-rules` hatırlatmadır.

**YENİ KAPI — `scripts/hook-guard-proof.sh`, `Frontend` job'ına ADIM olarak** (yeni job
DEĞİL; ruleset `20765617`, check adı job adıdır ve değişmedi). `agent-config-gate.mjs`
**kabloyu** kanıtlar, davranışı kanıtlayamaz: bir `case` kolunu düzenlemek her yolu geçerli
bırakırken guard'ı sessizce etkisizleştirir. Yeni kapı **19 beklenti** koşar — **6
engelleme + 13 geçiş**, çünkü her şeyi engelleyen bir guard pozitif-yalnız testi geçerken
işe yaramaz olur. Kaydın kendisi de assert edilir: `settings.json` betiklerden birini
adlandırmayı bırakırsa kırmızı.

**Üç negatif kontrol ailesi koşuldu ve üçü de kırmızı verdi:** guard davranışı (kapıyı
etkisizleştir / her şeyi engelle) · `agent-config-gate` yeni yolları (yeniden adlandır /
`chmod -x` — ikinci durumda **her iki yapılandırmayı da** adlandırdı) · kaydın silinmesi.
**Canlı kanıt:** kapı bu oturumun kendi Bash çağrılarını **üç kez** bloklladı.

**Ölçülmüş sınır (düzeltilmedi, fail-closed):** `guard-git.sh` **komut dizesinin tamamında**
desen arar → `feat/main-menu` de engellenir, bu desenleri *içeren* bir heredoc/döngü de.
Kaçınma yolu: metni Write ile bir **dosyaya** yaz, dosyayı koştur. Ayrıca
`docs-history-guard.py` (origin/main'e karşı, 2 dosya) ile `guard-git.sh`'in docs kapısı
(staged diff, tüm `docs/`) **farklı eksenlerdir**; tekilleştirmek birini kaybettirir.

Ayrıntı: `docs/PROJECT_HISTORY.md` §ADIM 58 · `docs/ADIM58_LANDED_KICKOFF.md`
(paste-ready resume prompt en altta).

## Stage — ADIM 59: P-A1 shared portfolio erişilebilirlik denetimi (PR #707)

**Migration:** yok. **Kod:** `backend/src`, `frontend/src`, `backend/alembic`,
`backend/tests` → `git diff --stat` **0 satır**. **OpenAPI / OCC / Idempotency / route /
query-key / `ENGINE_VERSION` / feature flag / issue state:** değişmedi. **Blocker sayısı
DEĞİŞMEDİ: 1 (yalnız A-08), verdict BLOCKED.** Sevk edilen tek şey
`docs/audit/closure_w0_shared_portfolio_2026-08-13.md` (579 satır, `historical`).

**Ne kanıtlandı.** `run_portfolio` (`portfolio_engine.py:531`), `project_portfolio_run`
(`execution/portfolio_projection.py:513`) ve `build_portfolio_manifest`
(`execution/provenance.py:473`) üretimde **çağrısız**; son ikisinin `backend/src`'te
**sıfır importer'ı** var. `ItemParticipant`'ın üretim implementasyonu **yok** — depodaki
tek örnek test sahipli `_ScriptedParticipant` (`tests/unit/oracles/portfolio_harness.py:156`).
Başka isim altında gizli adapter **yok**.

**İlk üretim sapması — tek satır:** `application/jobs/backtest_engine.py:299`
(`for prepared in prepared_items:`). Aşağı akıştaki her şey bundan türer.
**Not: bu satır eskiden bu belgede `:298` yazıyordu; ölçülen değer `:299`, fold ise `:364`.**

**YENİ BULGU — §Next'in (a) engeli ZATEN KAPALI.** `_ItemStepper` (`engine.py:756`) barı
ayrı ayrı çağrılabilir fazlar olarak sevk eder (`admit`/`carry`/`open_fills`/`held`/
`entry`/`tail`/`open_position`) ve **`E(t)` enjeksiyon noktası da sevk edilmiştir**:
`_phase_entry(bar, *, equity)` (`engine.py:2448`), `engine.py:786` bunu birebir *"the
SHARED `E(t)` for a portfolio participant"* diye belgeler. PR #602'den beri böyle.
**Kalan boşluk tam olarak (b)'dir:** üç faz **book eder**, `ItemParticipant` ise
arbitrasyon öncesi **tarif** ister (`CarryCharges` / `MandatoryExit` / `ItemIntent`).
Kapsam daraldı, **kapı açılmadı** — describe/book ayrımı `run_engine`'in bar gövdesine
dokunur, 46 golden digest ADR §15 R-4'ün riskidir, ADR §16 insan kapısı yerinde durur.

**Reuse anchor'ları (tam adlarıyla):**

- `docs/audit/closure_w0_shared_portfolio_2026-08-13.md` — §0 doğrulama tablosu, iki
  mermaid akış, importer haritası, tripwire assert-assert analizi, A1–A22
  KARŞILANAN/KARŞILANMAYAN dökümü, **en riskli beş seam**.
- `domain/backtest/engine.py::_ItemStepper` (`:756`) + `::_build_stepper` (`:793`) —
  adapter'ın oturacağı substrat. Faz callable'ları: `_phase_carry` `:1913`,
  `_phase_held` `:2264`, `_phase_entry` `:2448`.
- `domain/backtest/portfolio_engine.py::ItemParticipant` (`:238`) — adapter'ın
  karşılaması gereken üç hook.
- `tests/unit/oracles/portfolio_harness.py::_ScriptedParticipant` (`:156`) +
  `::simulate` (`:210`) — adapter'ın **şekil** referansı (davranış referansı DEĞİL).
- `application/commands/backtest_run.py:542` + `domain/allocation/rules.py:154` —
  iki fail-closed kapısı; tek doğruluk kaynağı `domain/allocation/capability.py:105`.

**Tavizsiz sınırlar (bu slice'ta pinlendi):**

1. **Containment-gate'in YEŞİLİ, shared engine'in aktif olduğunu DEĞİL, üretimin
   `run_portfolio`'ya ULAŞMADIĞINI kanıtlar.** İki merkezi assert **negatiftir**
   (`assert callers == []`). `5000.00` fixture'ı da sevk edilen fold **hâlâ yanlış**
   olduğu için geçer.
2. **E5 tripwire'ı SİLMEZ, DARALTIR** — boş beklenti yerine pinli çağıran allowlist'i +
   bayrak-erişilebilirliği assert'i. **`:225-233` ve `:103` E5'te DEĞİŞMEZ**; onlar
   *lift* kapısıdır. Bir E5 kendini `:230`/`:125`'i düzenlerken bulursa sessizce
   **ADIM 20 olmuştur** → önce ADR §16.
3. **`combine_item_runs` BAĞIMSIZ modun da yoludur.** Tüm çok-item koşularını faz
   döngüsüne yönlendiren bir wiring, bayraksız ve `ENGINE_VERSION` bump'sız her
   bağımsız-mod Result'ını yeniden fiyatlar.
4. **Alt küme koşarken `uv sync --all-extras` ÖNCE.** Soğuk venv'de prompt'un komutu
   **exit 4** verir (`unrecognized arguments: --cov=entropia … --no-cov`) — test hatası
   değil, ortam hatası.

**Kaydedildi, DÜZELTİLMEDİ (kapsam dışı):** containment-gate docstring `:146` hâlâ
stepper için *"was never written"* diyor (ADR §12 AMENDMENT / #602 bunu geçersiz kılar);
GH **#582**'nin gövdesi üç iddiada bayat (durumu **OPEN** ve doğru).

**NUMARA NOTU — bu slice 58 → 59 taşındı.** Denetim PR'ı `#707` ADIM 58 adıyla merge
edilmişti; kapanış PR'ı `#718` sıra beklerken main **`#715`**'i aldı ve o PR
**`feat(adim-58)`** adıyla indi. **Merge edilmiş ad kazanır**, taşınan taraf merge
edilmemiş olandır. Dal ve commit mesajları `stage-58` yazar; slice'ın adı **ADIM 59**.
`#715`'in kayıtlarına dokunulmadı, yalnız kickoff'unun `doc-status`'ü düşürüldü.
**Ders (auto-merge'ün kapatamadığı pencere):** auto-merge denetim PR'ında **çalıştı**
(#707 üç main ilerlemesine rağmen taşınmadı), ama **kapanış** PR'ı `Backend`'in ~50
dk'sı boyunca açık kalmak zorunda ve paralel bir oturum o pencerede aynı numarayı
alabiliyor. **Numarayı kapanış commit'ini YAZARKEN doğrula, ve merge'den hemen önce
`grep '^## ADIM' docs/PROJECT_HISTORY.md` ile BİR KEZ DAHA.**

**Süreç:** ADIM 57'nin çaresi **ölçüldü** — auto-merge açıkken main #707 altında üç kez
ilerledi, yeşilin ardından merge oldu, **numara taşınmadı**.

## Stage — ADIM 60: doküman kapısı artık HANGİ kickoff'un canlı olduğunu doğruluyor (PR #716, `f54bbc7`)

**Ürün kodu DEĞİŞMEDİ** (`backend/src`, `alembic`, `frontend/src` el değmedi). Migration yok,
`ENGINE_VERSION`/OpenAPI aynı. **Blocker sayısı DEĞİŞMEDİ (1 — yalnız A-08), verdict BLOCKED.**

**Kapı sayıyı koruyordu, doğruluğu değil.** `check_classification` **tam bir tane**
`doc-status: current` istiyordu; **hangisi** olduğunu sormuyordu. Depo bunu iki kez sevk etti ve
ikisi de yeşil geçti: **#697** kendi ADIM 56 kickoff'unu `historical` işaretleyip **ADIM 55'i
canlı bıraktı**; **#714** ADIM 56'yı promote etti ama arada **ADIM 57 inmişti**. İkisinde de
`current` sayısı **1**'di — yanlış olanı. Sonuç: §Session START md. 2'yi izleyen taze bir oturum
**bir slice bayat** resume seed'ine düşüyordu.

**Yeni kural:** `docs/ADIM<n>…KICKOFF.md` içindeki `<n>` slice sırasıdır; **daha yüksek numaralı
bir kickoff varken canlı işaret o belgede duramaz.** Semboller:
`generate_repository_facts.py::ADIM_KICKOFF_RE` · `::_adim_kickoff_number` ·
`::_check_live_kickoff_is_newest` · `::KICKOFF_GLOBS`. Kontrol **sayı kuralı yerleştikten sonra**
koşar; iki `current` varken susar (orada "hangisi"nin cevabı yok).

**Bilerek dar:** canlı belge slice-numaralı değilse (`STAGE*`, `O02`, `K05` … — 76 kickoff'un
**31'i**) kural **susar**. `strict: true` altında yanlış bir kırmızı **tüm merge'leri kilitler**;
sırasız bir adlandırmayı uydurma sırayla kırmızıya çevirmek daha büyük risktir.

**Negatifi kanıtlı — sekiz kurgu, dördü kırmızı dördü sessiz**, dördü test olarak indi
(`test_repository_facts_guard.py::test_a_superseded_kickoff_cannot_stay_live` ve üç kardeşi).
Gerçek ağaçta `check_classification(.)` → `[]` (45 slice-numaralı kickoff, maksimum 58).

**KAPI BU PR'I BİR KEZ KIRMIZIYA ÇEVİRDİ — ve haklıydı.** Üretilmiş olgular **backend test
collection** sayısını taşıyor; dört yeni test onu **3541 → 3545** yaptı ve üç artefakt bayatladı.
**Kalıcı kural: test ekleyen her slice
`cd backend && uv run python ../scripts/generate_repository_facts.py --root ..` koşmalıdır.**

**`strict: true` bandı ölçüldü.** `ea3db15` **22/22 yeşil** oldu ama merge olmadı — dal main'in
gerisine düşmüştü; auto-merge bir kez kendi güncelledi, main iki kez daha ilerledi.
**Koşan bir `Backend` varken dalı GÜNCELLEME** (85 dk sıfırlanır); koşu bitince güncelle.
Bu slice **üç** `Backend` turu harcadı — biri gerçek kusur, ikisi bant.

**Yan kalemler:** **#705** (`e0c25e6`) ADIM 55'i indiren PR'ı adlandırdı; içindeki `CLAUDE.md`
HEAD bump'ı bilerek **düşürüldü** (o blok artık ADIM 56'nındı). **#714 kapatıldı (obsolete)** —
teşhis doğruydu ama `#698` aynı onarımı daha doğru yapmıştı.

**Dürüst sınır:** `mypy` ve canlı-ağaç gate testi bu container'da **koşulamadı** (eklenti /
venv); testin assert ettiği çağrının aynısı (`--check`) ayrıca koşuldu → **exit 0**. Otorite CI.

Ayrıntı: `docs/PROJECT_HISTORY.md` §ADIM 60 · `docs/ADIM60_LANDED_KICKOFF.md`
(paste-ready resume prompt en altta).

## Stage 61 — üç canlı finansal kusur kapandı: yüzde sizing, per-fill komisyon, sıfır-boyut reddi (PR #720) landed

**ÜRÜN KODU DEĞİŞTİ ve FİNANSAL SONUÇLAR OYNADI** — önceki on bir slice'ın aksine bu bir
denetim değil. Kapanan: **#550** (`base_position_size` + min/max sınırları artık **resolved
capital'ın YÜZDESİ**), **#551** (pozitif olmayan boyut — negatif dahil — hiçbir modda pozisyon
açmaz), **#552** (komisyon **fill başına**, PD-2). `ENGINE_VERSION` →
**`backtest-engine-v18-percent-sizing-per-fill-commission`**. **Migration yok**
(head `0043_i08_registry_strategy_fks`), `SHARED_ALLOCATION_STATUS` `future_dev`,
**blocker sayısı DEĞİŞMEDİ (1 — yalnız A-08), BLOCKED**. Merge sha `5e52465`, 52 dosya,
+1090/−226.

**Reuse anchor'ları (tam sembol adlarıyla):**
`execution/sizing.py::_percent_of_capital` (tek dönüşüm, `_QTY` adımında kuantize) ·
`execution/sizing.py::max_position_size_cap` (**YENİ public** — cap'i okuyan her yer bundan
geçer: scaling merdiveni + stacking tranche; allocation açıkken sermaye argümanı **sleeve**) ·
`domain/strategy/config.py::PositionSizing.size_semantics` ·
`ReadinessIssueCode.STRATEGY_SIZING_SEMANTICS_UNCONFIRMED` (kapı **ALAN** tabanlıdır, metot
değil) · `frontend/src/lib/strategyForm.ts` (kaydetmek bayrağı basar = temizleme yolu).

**Pazarlıksız notlar:**
* **Kayıtlı revizyon TAŞINAMAZ** — 50, 102'de %51, 10 000'de %5000; hiçbir otomatik dönüşüm
  doğru olamaz. Bu yüzden bildirilir, uygulanmaz.
* **Golden 46 → 50.** #552 46'nın **0'ını** oynatmıştı: matris hiçbir yerde komisyon
  yapılandırmıyordu. Dört yeni senaryonun **negatif kontrolü kanıtlı**. Yeni senaryo eklerken
  negatif kontrolünü de üret.
* **Oracle fixture'ları risk-based ifade edildi** (`1% × 10 000 / 2.00 = 50 birim`) — yüzde
  **efektif** fill fiyatına böldüğü için maliyet oracle'ının boyutu maliyetle birlikte oynardı
  ve tek-knob-tek-delta özelliği ölürdü. `stop_loss_point` yalnız sizing'i besler, stop kurmaz.
* **#551'in "load-bearing" cross-item iddiası ÇÜRÜTÜLDÜ** — `build_prior_intervals` pozitif
  olmayan notional'ı kapıdan önce düşürür. Bu dal bir ara iddiayı tekrarladı ve `989c747` ile
  düzeltti. **İki okumanın anlaşması bağımsız doğrulama değildir.**
* **PO-4 (bust-equity 0-size fill invariant'ı) bilerek tersine çevrildi** — ürün sahibi kararı;
  gerekçe `_open` docstring'inde kalıcı.
* **AÇIK: komisyon TABANI** (kanon bps-on-notional, sevk edilen düz tutar). #709'un brief'i
  Karar 1 / Seçenek C. PD-2 **bölüşümü** kapattı, tabanı değil.

**Süreç dersi (YENİ):** main'i içeri alırken **merge DEĞİL rebase** — main bir `## ` başlığı
yeniden adlandırdığında merge onu staged diff'te `-## ` silme olarak sahneler ve
`docs-history-guard` haklı olarak bloklar. Kapıyı kapatma; rebase et (kapının kendi önerisi).
**`update_pull_request_branch`'i KAPANIŞ PR'ında KULLANMA.** Bu slice onu denedi ve
sunucu tarafı merge (`be4a082`) bu slice'ın ADIM kaydının **tamamını sessizce düşürdü**
(`grep -c percent-sizing-per-fill-commission` → **0**), üstelik **her kapıdan geçerek** —
hiçbir CI kapısı `docs/` altında kayıt silinmesini okumaz ve `docs-history-guard` yerel
commit olmadığı için hiç koşmaz. Kod PR'ında güvenli (main o dosyalara dokunmuyordu),
belge PR'ında **değil**. Kapanış PR'ında `behind` düşersen yerelde rebase et, kaydı
`grep` ile gözle doğrula, `--force-with-lease` ile it.
**Auto-merge numara taşımasını bu turda ÖNLEMEDİ:** kapanış
PR'ı `#723` açıkken `#721` merge oldu ve `## ADIM 60` ile
`docs/ADIM60_LANDED_KICKOFF.md`'in ikisini birden aldı → kayıt **61**'e taşındı.
Çakışma iki eksenliydi (başlık + dosya adı), o yüzden add/add çakışması ve
`check_classification` sessiz bir yanlış merge'i imkânsız kıldı.

`PROJECT_HISTORY.md` §ADIM 61 · `docs/ADIM61_LANDED_KICKOFF.md`.

## Stage 62 — Ready Check'in son iki artık N+1'i batch'lendi (P-E2, PR #712) landed

**Ne indi.** ADIM 46 (#617) market-data bacağındaki döngü-içi `get_dataset_root`'u
kapatmıştı; **aynı şekil iki bacakta daha yaşıyordu** ve hiçbir izleme kaydı yoktu
(#700'ün adli denetimi bunu **M-13** olarak kaydetmişti). İkisi de artık batch okur.

**Davranış değişikliği YOK** — aynı issue kodları, severity, sıralama, `field_path`,
`scope_id`, `root_active`. Migration yok, `ENGINE_VERSION` değişmedi, OpenAPI değişmedi,
alembic tek head `0043_i08_registry_strategy_fks`.

### Reuse anchor'ları (tam sembol adlarıyla)

| Anchor | Ne için |
|---|---|
| `infrastructure/postgres/repositories/research_data.py::get_dataset_roots` | **YENİ.** Research Root'ları için çoğul okuyucu; `market_data.py::get_dataset_roots`'un alan-alan aynası. Boş girdi round-trip'siz kısa devre, `dict.fromkeys` ile tekilleştirme, `entity_type` yükümü **SQL'de** |
| `infrastructure/postgres/repositories/market_data.py::get_dataset_roots` | **Yeniden kullanıldı, değiştirilmedi** — signal bacağı bunu çağırır |
| `commands/readiness_check.py::_resolve_signal_market_data_issues` | Batch'lenmiş signal bacağı; Root map'i revision map'inden **sonra** kurulur |
| `commands/readiness_check.py::_resolve_research_sources` | Batch'lenmiş research bacağı; yalnız RESOLVE OLAN revision'lar dereference edilir |
| `docs/performance/query_budgets.json` → `readiness_check.signal_market_data_leg` / `.research_funding_leg` | İki yeni bütçe yüzeyi, ikisi de `per_item: 0`. **Tavanı yükseltme** — N+1 geri gelirse slope assertion'ı kırar |
| `tests/integration/test_batched_dereference_equivalence.py` | 11 yeni eşdeğerlik testi (yabancı `entity_type`, soft-deleted Root, çözülemeyen pin, item sırası, paylaşılan pin) |

### Yeni bir okuma yüzeyi eklerken

Döngü içine `session.get` / `get_dataset_root` **koyma**; çoğul karşılığını yaz ve
`query_budgets.json`'a bir yüzey ekle. **Bütçe sayacının ölçülmüş kör noktası var:**
aynı session'da batch'in yüklediği bir PK için yeniden konan `session.get` **hiç SQL
üretmez** ve sayaç bunu görmez (gerekçesi `_comment`'te, beş ölçülmüş şekliyle) — kokuyu
kapıya bağlamak **sayaçla değil kaynak-düzeyi assertion'la** olur.

## Stage 63 — K-5'in sorusu düzeltildi (checklist A-3) + iki maliyet ölçümü (PR #719) landed

**Ne indi.** Bir **bulgu** değil, bulguyu kapatacak **araç** düzeltildi. Checklist **A-3**
*"`h1→h2→h3` sırası atlamasız"* diye soruyordu; bunu `specs/20-a11y-prechecks.spec.ts`
zaten her rotada sayıyor (**22 / 23**, K-5) → insandan makine çıktısını tekrarlaması
isteniyordu, yani **denetim K-5'i kaç rota gezerse gezsin kapatamazdı**. Yeni soru
atlamanın **yanıltıp yanıltmadığını** istiyor.

**Ürün kodu DEĞİŞMEDİ** — `backend/src`, `frontend/src`, `alembic` ağaçlarında tek satır yok.
**Blocker sayısı DEĞİŞMEDİ (1 — yalnız A-08), verdict BLOCKED. K-5 KAPANMADI** (yalnızca
*kapatılabilir* oldu).

### Reuse anchor'ları (tam adlarıyla)

| Anchor | Ne için |
|---|---|
| `a11y_screen_reader_audit_checklist.md` **A-3** satırı | Yeni beklenti. **Sayı sorma** — sonda sayıyor; **yanılma** sor |
| `a11y_screen_reader_audit_checklist.md` **§A-3 notu** | Sorunun neden değiştiği, neden `D-xx` olmadığı, `—` hücresinin neden kaldığı |
| `a11y_screen_reader_audit_results.md` §6 **K-5** satırı | Altı CSS kuralı + v18 ölçümü + `/market-data` düzeltmesi |
| `a11y_ci_ratchet_and_adjudication.md` §4 | Sicil **iki kararda kaldı** (D-10 + D-11) — buraya üçüncü satır **yazılmadı** |

### Bir sonraki denetçi/oturum için pazarlıksız

1. **Bu bir gevşetme değil.** Precheck 22 / 23 saymaya devam eder, K-5 audit §6'da ve
   RC §6.5'te **Open**. Advisory **susturulmadı**.
2. **`D-xx` yazılmadı ve yazılmamalı.** D-10/D-11 bir **gözlemin** dispozisyonunu imzalar;
   bu **aracı** düzeltir. Sicile bir satır eklemek *"K-5 adjudicated"* diye okunurdu.
3. **Rota 1'in `—` hücresi `—` kalır.** Eski cevap yeni soruya da cevap değil.
4. **K-5 düzeltilecekse sıra bellidir:** önce **altı** tag-scoped CSS kuralını sınıf-tabanlı
   yap, sonra tag'i oynat. `.data-guide-card h4` (`global.css:2261`) her önceki listede
   **eksikti** — unutulursa başlık UA varsayılanına düşer ve 23 görsel baseline kırılır.
   **v18 itirazı burada geçerli değildir** (mockup `h1:0 h2:1 h3:0 h4:14 h5:0`; seviyeler
   oradan kopyalanmadı).
5. **`/market-data` ayrı bir kusurdur** — sayı boşluğu değil **yanlış yuvalama**
   (`h1 → h4×4 → h3×3`). Ayrı kalem yapılmadı, açık bırakıldı.

## Stage 64 — kabul borcu sınıf B, parti 04: Backtest Result satır değişmezliği (doc 16, PR #704) landed

**Ne indi.** Doc 16 (Results History) kabul borcundan **beş kriter**: `RH-05` · `RH-10` ·
`RH-11` · `RH-12` · `RH-16`. **`partial` 111 → 106**, **`debt_class.B` 80 → 75**.
**Ürün kodu DEĞİŞMEDİ** — tek yeni dosya `backend/tests/integration/test_result_row_immutability.py`.
Blocker sayısı **değişmedi** (1 — yalnız A-08), verdict **BLOCKED**.

**Tema:** bir Result satırı tarihsel kayıttır — okumak, karşılaştırmak, üzerine inşa etmek
ona dokunamaz; dokunan iki işlem (soft delete, restore) denetlenir ve içerik hash'lerini korur.
Suite bunu **projeksiyon** üzerinden kanıtlamıştı; satırı komşu işlemden sonra **geri okumayı**
hiç yapmamıştı.

### Reuse anchor'ları (tam adlarıyla)

| Anchor | Ne için |
|---|---|
| `tests/integration/test_result_row_immutability.py::_snapshot` | Kolonları anlık görüntüler; "hiçbir şey değişmedi" iddiasının taşıyıcısı |
| `…::_reread` | Komşu işlemden **sonra** satırı geri okur — bu modülün tüm değeri burada |
| `…::_checksums` / `::_manifest_snapshot` | Artifact hash'lerinin round-trip boyunca bit-bit korunduğunu pinler |
| `…::_count_result_audits` | Audit satırını `target_entity_id` ile pinler |

### Pazarlıksız — bir sonraki parti bunları bilmeden dokunmasın

1. **İki olay adı sevk edilmemiş.** Doc 16 `RESULT_SOFT_DELETED` / `RESULT_RESTORED` der;
   sevk edilenler **`backtest.result_soft_deleted`** ve **`trash.restored`**. O-02/O-31
   emsali: **sevk edilen ad kanoniktir**. Restore testi `target_entity_id`'yi pinler —
   yoksa **herhangi bir** trash etkinliğiyle geçerdi.
2. **`moved == {...}` kümesi tam olmalı.** `RH-11` satırın *tam olarak*
   `{deletion_state, row_version}` kümesinde hareket ettiğini assert eder; gevşetmek testi
   bir "delete smoke test"ine indirir.
3. **Refüz testleri refüzden SONRA satırı geri okur.** Refüz iddianın yarısı; diğer yarısı
   hiçbir şeyin değişmemesi.
4. **`pytest.raises(Exception)` yazma** — `ruff` B017 yakalar ve kör exception zaten zayıf
   bir assertion'dır. Compare refüzü tipli: `CompareRequiresTwoDistinctResultsError`.

### Ölçülüp ERTELENENLER — sonraki partinin ilk iki kalemi

- **`RH-13.c2`** — `_digest_from_rows` **sabit** `KEY_METRIC_KEYS` üzerinden filtreler
  (profil revizyonu digest'e ulaşamaz); kanıt metrik **registry**'sinin seed'lenmesini ister,
  yoksa `MetricCodeUnknownError`.
- **`RH-14.c3`** — `create_analysis_artifact` capability-gated; kanıt registry'nin Limited'a
  yürütülmesini ister (`_walk_to_limited`), o helper bu modülün principal'larıyla çakışır.

**Yarım kanıtla işaretleme** — ADIM 54'ün `RD-09.c4` kararının aynısı.

### Devreden

**#703 açık:** `revision.native_asset_id` üretimde **hiç yazılmıyor**, yalnız
`queries/funding.py`'de okunuyor → funding-enabled backtest, uygulama içinde üretilmiş
hiçbir research dataset ile çalışamaz. `RD-09.c4` buna bağlı. **P1-Gate3 KAPANMADI**
(A=1 · B=75 · C=6 · D=32, açık **114**).

## Stage 65 — adli denetim kaydı + #541'in iki blocker gerekçesi (PR #700, DARALTILDI) landed

**Ne indi.** İki `historical` adli denetim belgesi, `#541`'in iki yanlış blocker gerekçesinin
düzeltilmesi (**Closes #541**), ve `portfolio_engine.py` HONEST BOUNDARY §1'in (a)/(b)/(c)
ayrımı. **Finansal mantık okundu, dokunulmadı.** Migration yok, `ENGINE_VERSION` değişmedi.
Blocker sayısı **değişmedi** (1 — yalnız A-08), verdict **BLOCKED**.

**Kapsam bilerek daraltıldı** — PR 30 commit / 2256 satır taşıyordu; güncel main'e karşı
yeniden ölçüldüğünde büyük kısmı **#722/#720 ile zaten inmişti** ve bir parçası **regresif**
hâle gelmişti (aşağıda).

### Reuse anchor'ları (tam adlarıyla)

| Anchor | Ne için |
|---|---|
| `domain/backtest/capabilities.py` §scaling-timeframe yorumu | Neden iki gerekçe yanlıştı, ve **gerekçe neden `dependency` içinde DEĞİL** |
| `domain/strategy/config.py::CANONICAL_TIMEFRAMES` | `1m…1D` — merdivenin **tepesi** `1D`, canon sonrasını söylemiyor |
| `domain/backtest/indicators.py:544::_ReferenceSeries` | Resampled seri **var**; eksik olan onu merdivenin fiyat karşılaştırmasına bağlamak |
| `docs/audit/final_closure_forensic_audit_2026-08-13.md` | 20 bölümlük adli ölçüm (`historical`, dondurulmuş) |
| `docs/audit/reopened_issue_reconciliation_2026-08-13.md` | 21 toplu-reopen issue'nun koda karşı ölçümü |

### Pazarlıksız

1. **`dependency` metnini uzatma.** `CapabilityNote.tsx:24` her `future_dev` seçeneğin
   `dependency`'sini tek paragrafta birleştirir; bu grupta **on tane** var → uzun bir metin
   kullanıcıya **on kez tekrar** olarak sevk edilir. Gerekçe **kaynak yorumuna** yazılır.
2. **`capabilities.py`'ye dokunduysan TS aynasını yeniden üret**
   (`uv run python tools/export_capability_matrix.py`); `test_capability_matrix.py` byte
   parity'yi pinler.
3. **Denetim belgeleri ölçtükleri anı dondurur.** §7/§13'ün `#550`/`#551`/`#552` satırları
   *"HÂLÂ BOZUK"* der ve `e2fa521`'de **doğruydu** — **#720 üçünü de sevk etti**. Banner
   bunu açıkça söyler; satırlar **bilerek güncellenmedi**. Bugünkü davranış için
   `PROJECT_HISTORY.md` §ADIM 61'e bak.
4. **`git diff origin/main <dal>` bir kapsam kararı için KANIT DEĞİLDİR** — dalın gerisinde
   kaldığı her şeyi "silinmiş" gösterir. `merge-base`'e göre **iki tarafın da** ne
   değiştirdiğini ayrı say.

### ALINMAYANLAR (gerekçeli, sessiz atlama değil)

| Parça | Neden |
|---|---|
| `booking.py` docstring'i | **REGRESİF** — main'in #720 sonrası *"COMMISSION IS PER-FILL"* metnini silip *"PD-2 uygulanmadı"* yazardı; #720 onu **uyguladı** |
| `test_oracle_portfolio_containment_gate.py` · `portfolio_harness.py` | main'in **#722** sürümü daha yeni, aynı düzeltmeyi taşıyor |
| `docs/CODEMAPS/BACKEND_LAYERS.md` (+2) | main'de #722 ile **75 satırlık tam bölüm** var |

### Açık bırakılanlar (insan kararı)

- **RC readiness raporunun blocker sayısı yükseltilmedi** — verdict'i değiştirir.
- Denetimin ölçtüğü **13 açık issue**'nun durumu değiştirilmedi.
- Merdivenin tepesi (`1D` sonrası) hâlâ **canonical bir boşluk**: clamp / durdur / reddet
  üç farklı üründür.

## Stage 66 — research timing provenance bundle KİMLİĞİNE pinlendi (P-E3, GH #558) landed

**Ne indi.** Doc 12 §9.1/§9.2'nin istediği available-time provenance'ı artık **her iki bundle
üyesi** taşıyor ve **hash'e giriyor** → `bundle_hash` bir time-policy değişimi altında artık
**değişmez değil**. `compiler_version` `research-bundle-v1` → **`research-bundle-v2`**.
Migration **yok** (kolon yok), dual-read **yok** (kalıcı tüketici yok — yeniden ölçüldü),
`ENGINE_VERSION` **değişmedi**. **OpenAPI DEĞİŞTİ.** Blocker sayısı **değişmedi** (1 — yalnız
A-08), verdict **BLOCKED**.

**Deponun tek `xfail(strict)`'i KALDIRILDI** (gevşetilmedi — ürün değişti). Doğrulama elle
değil **üretilmiş artefaktla**: `repository_facts.md` → `Backend xfail markers: 1 (1 strict)`
→ **`0 (0 strict)`**.

**Ön koşul imzasızdı ve slice DURDU.** `closure_product_decisions_2026-08-13.md` §Karar 2'nin
beş kutusu da boştu, GH #558 açık ve **yorumsuzdu**. Karar oturum içinde ürün sahibine
soruldu ve **imzalandı** (A1+A2, 2026-08-14). #720'nin Karar 1 imzasızken sevk etme emsali
**tekrarlanmadı**.

### Reuse anchor'ları (tam adlarıyla)

| Anchor | Ne için |
|---|---|
| `jobs/research_data.py::_pin_member` | **Her** bundle üyesi buradan geçer — yeni bir bundle yüzeyinde üyeyi elle kurma |
| `jobs/research_data.py::_derived` | Üye anahtarından **sıralı** + tekil + null'suz üst düzey dizi |
| `routes/research_data.py::SealedBundleResponse` | Yayımlanan gövde şeması — **`response_model` olarak bağlanmaz** (§Pazarlıksız 1) |
| `test_research_point_in_time_parity.py::TIMING_KEYS` | Parity **sözleşmesinin kendisi**; manifest'e yedinci alan eklersen buraya da ekle |
| `test_research_point_in_time_parity.py::_three_artifacts` | Üç artefaktı tek çağrıda kurar |

### Pazarlıksız

1. **Tipli gövdeyi `response_model` ile bağlama** — `response_model=None` +
   `responses={200: {"model": ...}}`. Ölçüldü: `response_model` gövdeyi yeniden serileştirir
   ve `task_id`/`run_request_id`'yi `null` olarak **geri ekler**; `_seal_bundle` onları
   **düşürür** ve düşürülmüş gövde **hash'lenen gövdedir**.
2. **`_derived`'ın `sorted()`'ı taşıyıcıdır** — `canonical_json` dizi elemanlarını
   **sıralamaz**, yani sıralamayı kaldırmak hash'i çağıranın argüman sırasına bağlar.
3. **Aynı token'lı iki üye sıralamayı SINAMAZ**; farklı policy taşıyan bir üçüncü üye gerekir.
4. **Harness zone alanlarını kurmaz** — kurmazsan üç artefakt `None` üzerinde anlaşır ve
   hiçbiri alanı taşımasa da test geçer.
5. **Arkasında alan olmayan bir §9.2 adını `[]` olarak yayımlama** — boş dizi *"böyle bir şey
   yok"* diye **beyan eder** (provenance yalanı); yokluk **boşluktur** ve assert edilir.

### Açık bırakılanlar (dürüst sınır)

- **`RD-11.c3` AÇIK** (sınıf B) — hiçbir test successor onayına karşı run manifest'ini geri
  okumuyor. Sıradaki slice bu; harness'ın yarısı hazır.
- **§9.2'nin iki adı sınıf D** (`alignment_policy_versions[]`, `missing_and_stale_policies[]`)
  — **ürün boşluğu**, test borcu değil. İmzalı sapma olarak kayıtlı.
- **Karar 1 (#552) ve Karar 3 (#559) HÂLÂ İMZASIZ.**
- **GH #558'e dokunulmadı** — kapatmak insan kararıdır.

## Stage 67 — RD-11.c3: successor onayı run manifest'ini yeniden yazmaz (doc 12 §14) landed

**Ne indi.** `RD-11.c3` `uncovered` → `covered`; kriterin **son açık clause'u** olduğu için
`RD-11` da `partial` → **`covered`** oldu ve `debt_class`'ını kaybetti. Tavanlar:
`partial` **106 → 105**, `debt_class.B` **75 → 74** (ratchet **aşağı**). **Ürün kodu
DEĞİŞMEDİ**, migration yok, OpenAPI değişmedi. Blocker sayısı **değişmedi** (1 — yalnız
A-08), verdict **BLOCKED**.

**Clause dört partidir açıktı çünkü harness yoktu** — *enabled funding policy üzerinden
research revision pinleyen TAMAMLANMIŞ bir run*. Ölçüldü: `FundingPolicy` kullanan dört
test dosyasının hiçbiri `run_backtest` çağırmıyordu.

### Reuse anchor'ları

| Anchor | Ne için |
|---|---|
| `_ready_composition(..., funding_for=...)` | Funding AÇIK ready composition; callback `(market_entity_id, market_revision_id)` alır |
| `_approved_funding_revision` | Readiness'in **ve** worker'ın kabul ettiği funding revision (beş kapı) |
| `_completed_funded_run` | `_completed_run`'ın funding'li ikizi, `load_funding_rows` enjekte eder |
| `_approve_successor` | Aynı root altında ikinci revizyon + onay, sevk edilmiş komutlarla |

### Pazarlıksız

1. **"Saklanan satır değişmedi" tek başına totolojidir** — manifest admission'da yazılır ve
   hiçbir şey yeniden yazmaz. Kanıt **okuma yolundadır**
   (`manifest_excerpt.research_data_revision_refs`, doc 16 §8.2).
2. **Negatif kontrol İKİ eksende**: saklanan JSON'u tahrif → saklanan assertion'lar kırmızı;
   `_research_revision_refs`'i boz → **yalnız** okuma-yolu assertion'ı kırmızı.
3. **Successor'ın gerçekten indiğini assert et**, yoksa test vacuous geçer.
4. **Market linkini elle yazma** (DR3 komutu pinler) ve **successor'a `market_entity_id` geçir**
   (onay `_ensure_market_link_active`'ten geçiyor).
5. **Kriterin son clause'u kapanınca `debt_class` KALDIRILIR** ve iki tavan birden iner.

### Açık bırakılanlar

- Sınıf D kalemleri (`alignment_policy_versions[]`, `missing_and_stale_policies[]`, `TL-16`,
  `AT-04`, `AT-17`, `CP-16`, `PC-15`, `AM-13`, `AM-15`) — **ürün boşluğu**, test kapatamaz.
- **Karar 1 (#552) / Karar 3 (#559) imzasız.** **A-08 tek blocker.**

## Stage 68 — kabul borcu batch 05 (doc 12): iki kriter kapandı, iki sınıf-D bulgusu landed

**Ne indi.** `RD-09` ve `RD-15` `partial` → `covered`; tavanlar `partial` **105 → 103**,
`debt_class.B` **74 → 72** (ratchet **aşağı**). **Ürün kodu DEĞİŞMEDİ.** Blocker sayısı
**değişmedi** (1 — yalnız A-08), verdict **BLOCKED**.

**`RD-09.c4` YENİ TEST YAZILMADAN kapandı.** ADIM 54 onu *"yalnız funding-enabled bir run
ile kapanır"* diye bırakmıştı; o harness **ADIM 67'de indi** ve oradaki `RD-11.c3` testi bu
clause'u birebir assert ediyor (v1.1 onaylandıktan sonra manifest + **Result snapshot** +
okuma yüzeyi hâlâ v1.0). Mevcut düğüm **cite edildi**.

**`RD-15.c4`** yeni bir frontend testiyle kapandı: `display_name: null` olan satır registry'de
hâlâ `entity_id` ile tanınıyor. Negatif kontrol: `display_name ?? entity_id` fallback'i
kaldırılınca test kırmızı.

### İki bulgu — ölçüldü, kaydedildi, üzerine gidilmedi

| Clause | Ölçüm |
|---|---|
| `RD-13.c4` | *reload/compare/new-revision* kurtarma yolu research frontend'inde **YOK** (verbatim `STALE_REVISION` yolu Trash/Market Data/Library/Mainboard'da var) → **sınıf D görünüyor** |
| `RD-12.c4` | Sayfa job durumunu/kalite raporunu **hiç yeniden okumuyor** (`useQueryClient` var, job-status sorgusu yok) → **sınıf D görünüyor** |

**İkisi de yeniden sınıflandırılMADI** — B → D **D tavanını yükseltir**, bu bir
adjudication'dır. Defterde artık **yedi** böyle açık bulgu var.

### Pazarlıksız

1. **Yeni partiye başlamadan önce son iki slice'ın REUSE anchor'larını oku** — bir clause
   bedavaya kapanabilir.
2. **Defterin sınıfı bir iddiadır**; davranışın sevk edildiğini `src` içinde doğrula.
3. **Stub şeklini varsayma** (`{data, meta}`, `{items, next_cursor}` değil).
4. **Frontend düğüm id'si `::` değil ` > `**; clause toplamlarını `--report`'tan oku.

## Stage 69 — kalan V18 closure işi bağımlılık sırasına konuldu (P-D, PR #728) landed

**Base `c49f5e7`** · migration **YOK** · `ENGINE_VERSION` **değişmedi** · alembic head
`0043_i08_registry_strategy_fks` · OpenAPI **değişmedi** · **ÜRÜN KODU DEĞİŞMEDİ**.
Blocker sayısı **DEĞİŞMEDİ (1 — yalnız A-08)**, verdict **BLOCKED**.
Tek çıktı: `docs/implementation/final_closure_ordered_plan_2026-08-13.md` (944 satır).

**NUMARA: bu kayıt merge sırasını TERS ÇEVİRİR.** #728 (`2a314ae`) main'e #729/#730'dan
**önce** indi ama kaydı yazılmadı; #730 aradan geçip **ADIM 66**'yı merge edilmiş adla aldı.
Kapanış PR'ı (#732) sıra beklerken **#733 ADIM 67**'yi, **#736 ADIM 68**'i aldı.
Numaralar yeniden atanmaz → bu **ADIM 69**'dur. Dal adındaki `stage-67` yazıldığı andaki
tahmindir, kaydın numarası değil.

**Ne indi:** AŞAMA C'nin iki tasarımı (#724, #725) **19 tek-sorumluluklu slice'a** bölündü —
`F1–F3` financial · `R1–R4` research · `P1–P3` performance · `C1–C9` shared portfolio. Her
slice on dokuz zorunlu alanı taşıyor; ayrıca mermaid bağımlılık grafiği, paralellik şeritleri,
**16 maddelik insan-kapısı sicili** ve P11-1 merge ekonomisi.

**Grafik körü körüne kabul EDİLMEDİ — üç düğüm değişti:**
- **E2 landed DEĞİL, 2/5** — üç per-item okuma canlı (`readiness_check.py` `:472`, `:371`,
  `:788`) ve **hiçbiri ölçülmüyor**; tamamlanmışlık kapısı elle yazılmış bir küme.
- **E1, E4'ün önünde olmak ZORUNDA DEĞİL.** `_build_stepper` **tek ~2541 satırlık fonksiyon**,
  o yüzden *"ikisi de engine.py'ye dokunuyor"* hiçbir şey kanıtlamaz. İç fonksiyon sahipleri
  çözüldü: **A-2 `_open()`'da, E4a `_phase_carry/_held/_entry`'de → AYRIK**; **A-3 ile E4a
  `_phase_tail()`'de ÇAKIŞIR**. Asıl kısıt **paylaşılan kabul artefaktı**:
  `engine_golden_digests.json` E4a'nın tüm kapısı (*byte değişmedi*) ve A-3'ün zorunlu çıktısı
  (*yeniden üret*) → **karşılıklı dışlama**, öncelik değil.
- **E3 ve E6 çoklu slice** (imzanın gerektiği yerden bölündü; E6 = C5–C9).

**Dört bayat sayı düzeltildi, biri kabul kapısıydı:** golden **46 → 50** (41 non-portfolio +
9 `portfolio.*`) · A13 **37 → 41** · E4b'nin *"25 oracle"*ı **hiçbir okumada üretilmiyor**
(11+10, ayrıca 5 containment) → kapı **sayıyla değil dosya adıyla** yazıldı.

**İnsan kapıları: prompt 6 diyordu, ölçüm 16 buldu** — 15 açık, 14 fiilen bloklayan.
**#550 (G5) TAHLİYE EDİLDİ** (kanonik seçenek issue gövdesinde kayıtlı, #720 sevk etti);
yerine **G4** çıktı: cap taşması dispozisyonu **briflenmemiş, sahibi yok**. **İki kapının
imzalanacak bloğu YOK: G4 ve G15** (leg 3'te hangi satır kazanır).

**Merge ekonomisi:** tavan **3 açık PR** (≤2'si `backend/src`, `engine.py`/üretilmiş artefakta
dokunan **TAM 1**; C4/C8/C9 sırasında **1**). Sıra: **en çok çakışan ÖNCE** — `strict` altında
her arkadaki PR main'i zaten yutar, ağırı sona bırakmak ona her küçük merge'de 48–85 dk'lık
`Backend` koşusunu **ve kendi kabulünü** yeniden ödetir.

### Açık bırakılanlar (dürüst sınır)

- **Hiçbir şey koşulmadı** — belgede tek bir test/coverage sayısı iddia edilmiyor; otorite CI.
- **Hiçbir ürün sorusu karara bağlanmadı**, hiçbir issue durumu değiştirilmedi.
- **`_phase_tail` ayrılabilirliği HÂLÂ ölçülmedi** — `C1`'in yazılı stop condition'ı yapıldı.
- **Ready Check leg 3 bilerek programlanmadı** — `work_object_revision_id` UNIQUE değil → G15.
- **PR #729 (F1) main'de ama HİÇBİR ADIM kaydı YOK** — ölçüldü ve §ADIM 69 md. 6'da kaydedildi;
  kaydı **sahibinin** yazması gerekir, bu slice başkasının anlatısını uydurmadı.

## Stage 70 — F1: sıfır-boyut reddinin gerekçesi adlandırılmış sabit oldu (PR #729) landed

> **GERİYE DÖNÜK KAYIT, BAŞKA BİR OTURUMUN SLICE'I.** Kaynak: PR #729 gövdesi (birinci el) +
> `600be00` diff'i + bağımsız yeniden ölçüm. Hangi iddianın yeniden ölçüldüğü
> `PROJECT_HISTORY.md` §ADIM 70 md. 5'te ayrı ayrı işaretli. **Kendi kickoff'u YOK, bilerek** —
> canlı devam noktası `docs/ADIM69_LANDED_KICKOFF.md` ve #729 onu değiştirmiyor.

**Base `2a314ae`** · migration **YOK** · `ENGINE_VERSION` **DEĞİŞMEDİ** · alembic head
`0043_i08_registry_strategy_fks` · OpenAPI **değişmedi** · **ÜRÜN KODU DEĞİŞTİ, DAVRANIŞ
DEĞİŞMEDİ** (yayılan string byte-identical, yalnız tanım yeri taşındı).
Blocker sayısı **DEĞİŞMEDİ (1 — yalnız A-08)**, verdict **BLOCKED**.

**Ne indi:** ordered plan'ın **`F1`** slice'ı (tasarımda **A-2**) — `"size_resolved_to_zero"`
çıplak literal'i **`execution/sizing.py:414` `SIZE_RESOLVED_TO_ZERO`** sabitine yükseltildi,
değeri testle pinlendi, allocation yolunun hâlâ daha spesifik `sleeve_zero_capacity`
raporladığı negatif kontrolle kanıtlandı.

**Planın talimatına UYULMADI ve sapma DOĞRUYDU.** Tasarım da benim planım da sabiti
`portfolio_ledger.py`'ye, `SLEEVE_ZERO_CAPACITY`'nin yanına koymayı söylüyordu; uygulayan
oturum önce onu yaptı ve **iki containment kapısı kırıldı**
(`test_the_shared_ledger_is_reachable_only_through_the_phase_loop` +
`test_the_phase_loop_exists_but_no_production_path_reaches_it`). Sevk edilmiş `engine.py`'ın
**bir string'e ulaşmak için** contained bir modülü import etmesi, canlı bir tripwire'ı
stilistik komşuluğa takas ederdi. `sizing.py` yerleşimi **net yeni modül kenarı: sıfır**.
`portfolio_ledger.py` `origin/main` ile **byte-identical** (bağımsız doğrulandı).
**Ders: bir tasarımın *"şu dosyaya koy"* talimatı ölçülmüş bir kısıt DEĞİLDİR — kapı
kırmızıysa kapıyı değil planı düzelt.**

**Adversarial review'ın bulduğu gerçek boşluk:** çağrı yeri literal'e geri dönerse
**davranışsal testlerin hepsi yeşil kalır** (yayılan string aynı) → teslimat bir convention'dı
ve DoD'si elle bir `grep`'ti (**benim planımın DoD'si de oydu**). Kaynak düzeyi ratchet
`test_oracle_sizing.py:394` bunu kapatıyor; **sembolle** eşleşiyor, satır numarasıyla değil;
mutasyonla kanıtlı.

**O-02 sınırı:** bu bir **F-10 restriction-trace** token'ı, HTTP hatası **değil** — hiç
`ErrorBody` yayılmıyor, o yüzden `ErrorCategory` **bilerek uygulanmaz**; kategori bildirmek
hiçbir yanıta ulaşmayan bir şey için `retryable` reklamı olurdu.

### Açık bırakılanlar (dürüst sınır)

- **Trace sözlüğü hâlâ sözleşme değil** — sekiz token daha literal, hiçbiri OpenAPI'de yok.
  Takipte ölçülmüş kısıt: `test_backtest_item_intents.py` `blocked_reason`'ın kaynağını
  regex'le tarayıp minimum sayı assert ediyor → yerinde sabite çevirmek **o testi kırar**.
- **İki sabit ayrı modüllerde** — containment sınırının sonucu; birleştirmek ledger sabitini
  dışarı taşımak demek, dört contained modüle dokunur, kendi slice'ını hak eder.
- **Containment kapıları METİN eşleştirici** — dinamik/re-export import'u kaçırırlar (önceden var).
- **F2 + F3 bloklu, P-E1 TAMAMLANMADI.** **A-08 DEĞİŞMEDİ** (0/4, #514 açık).
- **Tam suite bu oturumda koşulmadı** — CI iddiaları PR #729'un koşusundan taşındı
  (run `31841208114`: 4130 passed / 1 xfailed, coverage %93.72). **Otorite o koşudur.**


## Stage 71 — describe/book split: P1, P3 ve P4 ikiye ayrıldı (C1 / E4a, PR #735) landed

**Ne indi.** Üç karar fazı birer **çifte** ayrıldı: `_phase_carry` → `_compute_carry` +
`_book_carry`, `_phase_held` → `_evaluate_held` + `_apply_held`, `_phase_entry` →
`_evaluate_entry` + `_apply_entry`. `_ItemStepper` **altı alan kazandı, üçünü korudu**;
`_step` **karakter karakter aynı**, dolayısıyla `run_engine` yapı gereği el değmemiş.
**Ürün davranışı DEĞİŞMEDİ**, migration yok, OpenAPI değişmedi, `ENGINE_VERSION`
değişmedi, containment `future_dev`. Blocker sayısı **değişmedi** (1 — yalnız A-08),
verdict **BLOCKED**.

**Kabul (ADR-0002 §15 R-4): 50 golden digest OYNAMADI**, `engine_golden_digests.json`
**bayt bayt aynı** — ölçüm M-1 (41 non-portfolio + 9 `portfolio.*`) birebir yeniden
üretildi.

**Asıl kazanım:** değerlendirme artık **gerçekten salt-okur**. Split öncesi kod karar
verirken `suppressed_entries` / `entries_blocked_by_restriction` / `strength_adjustments`
sayaçlarını artırıp `filtered_no_entry` yayımlıyordu; bunlar artık karar nesnesinde
`_LedgerEffect` olarak taşınır ve yalnız `_book_effects` uygular. Mekanik kontrol:
`_evaluate_held` **0** etki + `_apply_held` 22 (aynı sırada); `_evaluate_entry` **0** etki
+ `_apply_entry` 13 + ertelenen 6.

**TEK bilinçli istisna:** `_evaluate_held` trail anchor'ı ilerletir — bu booking değil
**piyasanın** yüksek-su işaretidir (idempotent; `_resolve_stop` trailing seviyeyi ondan
türetir).

**C1'in ikinci teslimatı — `_phase_tail` scaling ayrılabilirliği ÖLÇÜLDÜ ve sonuç
OLUMSUZ.** Scale ladder kendi başına temiz bir describe/book şekli, ama guard'ı
`position` ve `len(led.trades) == trades_before_bar` okur; stacking bölümü **ikisini de**
yazar (`:3091`, `:3098`, `:3220`, `:3221`), tek bar-başı bütçe altında. Yani scaling
stacking book edilmeden tarif **edilemez** → paylaşımlı koşuda bar başına **ikinci bir
arbitraj turu** gerekir, **ADR §8'de bir tane var**. P-C2 §C.3.8 (a) artık **zorunlu**;
**G12** bir tercih değil **sözleşme sorusu**. `_phase_tail` **değiştirilmedi** (F3 talep
ediyor). → `docs/audit/closure_c1_phase_tail_scaling_separability_2026-08-17.md`

**Ders (kaydedildi):** ilk iki negatif kontrol **geçti**, çünkü ilk senaryo kümesi hiçbir
bastırma yoluna ulaşmıyordu — salt-okur testi üç sayacın **ikisini hiç gözlemlemiyordu**.
`date_blackout` / `volatility_strength` / `direction_veto` vakaları **negatif kontrol
geçtiği için** eklendi. **Geçen bir negatif kontrol, testin iyi olduğunu değil yolun hiç
koşulmadığını söyler.**

**Süreç:** `docs-history-guard` merge'i blokladı (#733'ün `Class B (75)` → `(74)` başlık
değişimi kayıt silme gibi göründü) → §ADIM 61'in kaydettiği çare **rebase** uygulandı,
guard'a dokunulmadı. E2E görsel kırmızısı **bu slice'ın değildi** (flake retry'si paylaşılan
compose stack'ini kirletti; `/mainboard` bir satır uzadı) → **taban güncellenMEDİ**, rebase
sonrası F-23 yeşil. Üretilmiş dosya çakışmaları elle birleştirilmedi, **yeniden üretildi**
(**3585 collected / 341 dosya**).

**Açık kaldı:** `C2` (`settle`/`finalize`/P10/`iter_portfolio`) **G9** ve **G13** imzasız
insan kapılarının arkasında; `C3` (adapter) hâlâ erişilemez. `PROJECT_HISTORY.md` §ADIM 71 ·
`docs/ADIM71_LANDED_KICKOFF.md`.


## Stage 72 — kayıtsız inen İKİ slice'ın ritüeli: C5 (PR #740) ve E5 (PR #738) landed

**Squash:** C5 `df7df92`, E5 `6ca478c` · base `6ba82a8` · migration **YOK** ·
`ENGINE_VERSION` **değişmedi** · alembic head `0043_i08_registry_strategy_fks` · OpenAPI
**değişmedi** · `SHARED_ALLOCATION_STATUS` **`future_dev`** (dokunulmadı).

**İKİSİ DE SIFIR ÜRÜN SATIRI SEVK ETTİ** (`git diff -- backend/` boş). **Blocker sayısı
DEĞİŞMEDİ (1 — yalnız A-08), verdict BLOCKED.**

- **C5 — R-1 allocation pinning: yapılacak iş yoktu.** Plan `C5`'i koşulabilir diye
  listeliyordu; ADR §10.2'nin üç yargısının üçü de yanlış çıktı.
  `readiness_check.py::_resolve_allocation` config'i **dondurulmuş revizyondan** kurar; draft
  yalnız `_pinned_revision(...) is None` dalında pinlenir ve orada `plan_revision_id` de
  null'dur. **Negatif kontrol karar verdi:** kusur geri konunca
  `test_allocation_revision_pin.py` **bayt-eşleşme satırında** kırmızı verdi (`5.000000` ↔
  `35.000000`), geri alınınca 3 passed → testi yeşil tutan **ürün kodu**. **E6 ön koşulu #19
  karşılanıyor.** Sevk edilen: ölçüm belgesi + plan satırı düzeltmesi. **Yeni test yazılmadı**
  (mevcut assertion taşıyıcı, ikincisi ratchet yüzeyini boşuna yükseltirdi).
  **ADR kaydı İMZASIZ kaldı — bilinçli:** imza verildi, uygulandı, sonra ürün sahibi commit'i
  dalı yeniden yazarken **düşürdü**; main'in §15 `R-1` satırı **değişmedi**. Geri
  uygulanmadı ve **uygulanmamalıdır**.
- **E5 — C4 worker shared-path: kurulamaz, DURDURULDU.** `C4`'ün ön koşulu `C3`; `C3` yok
  (`participant.py` yok, `backend/src`'te **sıfır** `ItemParticipant` impl'i — ikisi de test
  sahipli), `C2` de yok (`settle`/`finalize`/`iter_portfolio` **0 hit**, `PHASE_ORDER` 8 faz).
  Tasarımın E5 dalı üç çağrı; **ikisi mevcut değil**. **Containment gate değiştirilmedi** ve
  negatif kontrol koşulmadı — değişiklik yok; tarif ettiği yol yokken gate'i yeniden yazmak
  onu **kör eder**. E4'ün Blocker D'si (importer allowlist) **hâlâ canlı, insan incelemesi**.
- **KAYDIN ASIL GÜNCELLEMESİ:** **`C1` (#735), P-E4 kaydının Blocker 1'ini KAPATTI.**
  describe/book ayrımı `_ItemStepper`'ın **public** yüzeyinde. Yani **kritik yol artık kodla
  değil bir İMZAYLA başlıyor** — ajanın kapatabileceği son mühendislik ön koşulu `C1`'di.
  `closure_e4_adapter_precondition_measurement_2026-08-17.md` §2 **artık cite edilmemelidir**.
- **Dersler:** parti seçmeden **önce ölç** (plan bayattı, kod değil) · merge sonrası
  **yeniden ölç** (`#734` `readiness_check.py`'ye dokundu, satır numaraları **+3** kaydı →
  ADR satırı sembol adlarına geçirildi) · bir kayıt kaybolmuş görünüyorsa **önce delile bak**
  (geri alım tam ve tutarlıydı → kaza değil **karar**).
- Kabul borcu tavanları **oynamadı**; codemap **tazelenmedi ve gerekmedi** (yeni endpoint /
  tablo / sayfa / job yok).

`PROJECT_HISTORY.md` §ADIM 72 · `docs/ADIM72_KICKOFF.md`.

## Stage 73 — kabul borcu batch 06 (doc 07 backend): üç kriter kapandı, bir sınıf-D bulgusu landed

**Ne indi.** Yalnız **test + defter**. Ürün kodu **değişmedi**, migration **yok**, OpenAPI
**değişmedi**, `ENGINE_VERSION` **değişmedi**, containment `future_dev`. Blocker sayısı
**değişmedi** (1 — yalnız A-08), verdict **BLOCKED**.

Parti **tek sayfa belgesi (doc 07, Pre-Check) + tek yüzey (backend)** ile sınırlandı. Üç
kriter seçildi çünkü **son açık clause'ları backend'di**, yani tek clause kapatmak satırın
tamamını kapatıyor:

| Kriter | Kapanan clause | Neden açıktı |
|---|---|---|
| `PC-07` | `.c3` | `RESOLVER_SIGNATURE_MISMATCH` yalnız `/resolve` ucunda gözlenmişti, **scan'de hiç** |
| `PC-09` | `.c2` | `_enforce_precheck_gate`'in **registry kolu** test edilmemiş daldı (tek test `context_hash`'i oynatıyordu) |
| `PC-11` | `.c3` | `run_precheck` `idempotency_key` **kabul ediyordu ama hiçbir test göndermiyordu** |

**Tavanlar İNDİ:** `partial` **103 → 100**, `debt_class.B` **72 → 69**. Açık kabul borcu
**111 → 108** (A=1 · B=69 · C=6 · D=32). Clause düzeyinde `covered` **1007 → 1010**,
`uncovered` **120 → 117**. `total_criteria` **383** (taban, değişmedi).

**Üçü de NEGATİF KONTROLDEN geçti** — davranış üründen kaldırıldı, test kırmızıya döndü:
`signature_matches` → `return True` verince `assert 'passed' == 'blocked'`; registry dalı →
`if False` verince `DID NOT RAISE PrecheckStale`; `run_precheck` içinde `key=None` verince
`job_id` ve `request_version` ayrışıyor.

**BULGU — `PC-20.c3` sınıf D, kapatılmadı.** "Restore edilen bir package REQUEST bayat
döner" **sevk edilmemiş**: restore generic `_restore_registry_target`'tan geçer, yalnız
`deletion_state`'i ACTIVE'e çevirir; `context_hash`'e de `current_scan_id`'ye de dokunmaz,
`get_current_scan` ise deletion filtresi olmadan okur → restore edilen istek Send kapısını
**geçer**. Doc 07 §5 bunu talep ediyor, yani ürün boşluğu. **YENİDEN SINIFLANDIRILMADI**
(B → D **D tavanını yükseltir**, bu bir adjudication'dır). Defterde artık **SEKİZ** böyle
açık bulgu var.

**Açık kaldı:** `PC-01` backend-only bir partiyle kapanamaz — `.c3` backend ama `.c2`
(`Not Checked` pill) frontend, ikisi birden gerekiyor. `PROJECT_HISTORY.md` §ADIM 73 ·
`docs/ADIM72_LANDED_KICKOFF.md`.


## Stage 74 — R2 + R3: bundle yüzeyi tek okumaya bağlandı, sealed şekil sürüme kilitlendi (PR #742 + #745) landed

**Ürün davranışı DEĞİŞMEDİ.** `bundle_hash` kıpırdamadı · `_BUNDLE_COMPILER_VERSION`
`research-bundle-v2`'de kaldı · `ENGINE_VERSION` / `execution_key` / golden digest'ler
ellenmedi · migration yok · OpenAPI değişmedi. **Blocker sayısı DEĞİŞMEDİ (1 — yalnız
A-08), verdict BLOCKED.**

- **R2 (#742)** — `TimingProvenance.as_bundle_member()` + `BUNDLE_MEMBER_KEYS`;
  `jobs/research_data.py::_pin_member` tek projeksiyon çağrısına indi; `_enum` **silindi**
  (aynı iki satırlık coercion'ın **üçüncü** kopyası — `run_context._enum` ve R1'de kaldırılan
  `readiness_check._enum_value`'dan sonra). Üyenin 13 anahtarından 11'i value object'ten;
  ikisi (`market_content_hash`, `feature_definition_ids`) session gerektirdiği için parametre.
  İki projeksiyon **kasıtlı olarak farklı ad** kullanır (bundle `research_revision_id`,
  manifest `revision_id`) — birini diğerine uydurmak temizlik değil **wire değişikliğidir**;
  sabit kalması gereken **değerdir**.
- **R3 (#745)** — sealed body'nin şekli `compiler_version`'a **golden digest** ile kilitlendi
  (iki compiler ayrı pinli; opsiyonel `task_id`/`run_request_id` iki yönde de kapsandı).
  `resolved_at` yarısı **zaten #730'da inmişti**; planın durdurma koşulu kontrol edildi ve
  **tetiklenmedi**. **Golden'lar R2'nin altından geçti:** R2 inmeden önce pinlenmişlerdi,
  R2'li tabana rebase sonrası **değişmeden tuttular** (41 unit + 39 entegrasyon) — aynı sealed
  şeklin iki bağımsız türetimi birbirini doğruladı.
- **CodeQL alert 256 haklı çıktı:** `_SEALED_BODY_KEYS` ölü üretim koduydu (`backend/src`'te
  tek geçiş = kendi tanımı) ve savunma gerekçesi yanlıştı (`MANIFEST_REVISION_KEYS` public +
  `__all__`, bu private). **Kaldırıldı** — kapı zaten golden'a dayanıyordu, iki mutation proof
  kaldırma sonrası da kırmızı verdi.
- **R4 için iş YOKTU** — iki teslimatı da #730'da inmişti (strict xfail **0**,
  `test_all_three_artifacts_carry_the_same_timing_dict` mevcut ve **güçlü**: üç artefaktın tüm
  timing sözlüğünü karşılaştırıyor, non-default zone/delay ile değerleri de pinliyor). Ölçüldü,
  uydurulmadı. **PACKAGE R BİTTİ.**
- Test sayıları/coverage: **otorite CI**. Kabul borcu tavanları **bu iki slice yüzünden
  oynamadı** (kriter kapatılmadı); dalgadaki `105/B74 → 103/B72 → 100/B69` inişleri **#733 ve
  #749'a** aittir. Codemap: `BACKEND_LAYERS.md` `research_data` satırı genişletildi.
- **Süreç bedelleri (ÖLÇÜLDÜ):** R3'ün dalında **ONBİR CI koşusu** yapıldı (6 yeşil, 5
  supersede edilip iptal), head **on kez** oynadı, taban altı kez; PR 14:57Z→04:59Z, **~14
  saat**, ürün kodu hiç değişmeden. Tam suite üç kez yeşil indi, ilk ikisi **gene de merge
  edilemedi**, çünkü `strict: true` altında kapı green değil **güncelliktir** ·
  paylaşılan dal head'i defalarca altımdan değişti (push öncesi
  `git ls-remote --heads origin <dal>`, force-push daima `--force-with-lease` ile eski SHA'ya
  pinli) · `guard-git.sh` ledger ratchet düşüşünde **yanlış pozitif** verdi (birleşmiş dosya
  main'inkiyle byte-aynıydı; çare **merge değil rebase**) · **base'i `main` olmayan PR CI
  KOŞMAZ** (#743 `total_count: 0` ile bloklu kaldı, kapatıldı; R3 main'e rebase edilip **#745**
  olarak yeniden açıldı) · **CodeQL iki kez altyapıdan çöktü** (init'te "No server is currently
  available"; analiz hiç koşmadı, çare rerun — alert 256'nın **gerçek** bulgusuyla karıştırma,
  farkı log söyler) · aynı DB'ye paralel koşan iki pytest **iki sahte kırmızı** üretti, ve
  Postgres düşükken entegrasyon suite'i **sahte bir YEŞİL** verdi (`exit 0` ama 39 **skipped**).
- **Plan §5.2 tavanı aşıldı** — bir noktada altı PR açıktı (#742 #745 #746 #747 #748 #749),
  tavan üç. Kayda geçirildi; yeni kod slice'ı açılmadı.
- Tam kayıt: `docs/PROJECT_HISTORY.md` §ADIM 74 · kalkış: `docs/ADIM74_LANDED_KICKOFF.md`.

## Stage 75 — kabul borcu batch 07 (doc 07 frontend): doc 07 bitti, dokuzuncu bulgu landed

**Ne indi.** Yalnız **test + defter**. Ürün kodu **değişmedi**, migration **yok**, OpenAPI
**değişmedi**, `ENGINE_VERSION` **değişmedi**, containment `future_dev`. Blocker sayısı
**değişmedi** (1 — yalnız A-08), verdict **BLOCKED**.

Batch 06'nın **tümleyeni**: aynı sayfa belgesi (doc 07), bu kez **frontend** yüzeyi. Üç
kriter daha kapandı ve **doc 07'nin sınıf-B işi bitti**.

| Kriter | Kapanan clause | Neden açıktı |
|---|---|---|
| `PC-01` | `.c2` **+** `.c3` | `Not Checked` ağaçta **tam bir kez** var, hiçbir test assert etmiyordu; `.c3`'ün "doğru görünen" testi isteği önce **DRAFT**'a sürüyordu |
| `PC-17` | `.c4` | dayanıklılık yarısı güçlüydü, **UI yarısı** hiç assert edilmemişti |
| `PC-21` | `.c2` **+** `.c3` | kanonik PASSED metni assert edilmiyordu; `.c3` bir **negatif kapsam** iddiası ve yokluğu **varsayılmıştı** |

**Tavanlar İNDİ:** `partial` **100 → 97**, `debt_class.B` **69 → 66**. Açık kabul borcu
**108 → 105** (A=1 · B=66 · C=6 · D=32). Clause düzeyinde `covered` **1010 → 1015**,
`uncovered` **117 → 112**.

**ALTI negatif kontrol, altısı da kırmızı** — her biri davranışı **üründen** kaldırarak:
`Not Checked` → em dash · `get_package_request` paket yaratınca `assert 2 == 0` ·
`onClose` POST atınca `expected 1 to be +0` · modal'ın `detail`'i donunca `blocked`
bulunamıyor · PASSED satırı kırpılınca tam cümle eşleşmiyor · PASSED satırı fazla iddia
edince `not to match /repaint/i`.

**`PC-21.c3` bir totoloji değil.** Negatif kapsam iddiası (yüzey repaint / lookahead /
validation / approval hakkında hiçbir şey **iddia etmemeli**) yedi kalıba karşı **tüm
render edilmiş yüzeyi** pinliyor ve fazla-iddia eklendiğinde **kırmızıya dönüyor**.

**BULGU — `PC-02.c2` KURULAMAZ (sınıf C şeklinde), kapatılmadı.** "Boş kaynak için nihai
boş-girdi metni" **yok**: `EMPTY_SOURCE` `frontend/src`'te **hiç geçmiyor** ve daha
belirleyicisi, durum **erişilemez** — overlay yalnız `detail !== null` iken render ediliyor
(`CreatePackage.tsx:765`), yani kalıcı bir istek olmadan Pre-Check açılamıyor; boş kaynaklı
istek ise route'ta DB'den önce reddediliyor. **Yeniden sınıflandırılmadı** (C tavanını
yükseltir). Defterde artık **DOKUZ** böyle bulgu var.

**Doc 07'de sınıf B kalmadı.** Kalan açık satırlar yalnız bulgular (`PC-02.c2`, `PC-20.c3`)
ve iki sınıf-D Agent satırı (`PC-15`, `PC-16`). `PROJECT_HISTORY.md` §ADIM 75 ·
`docs/ADIM75_LANDED_KICKOFF.md`.

## Stage 76 — P-E6/C8: containment kapısının İKİNCİ DÜNYASI; flag DEĞİŞMEDİ landed

Base `0f0651d` · migration **YOK** · alembic head `0043_i08_registry_strategy_fks` ·
`ENGINE_VERSION` **değişmedi** · OpenAPI **değişmedi** ·
**`SHARED_ALLOCATION_STATUS` = `future_dev` (DEĞİŞMEDİ)** · **ürün kodu DEĞİŞMEDİ**
(`backend/src` + `frontend/src/lib` + `frontend/src/pages`'te sıfır satır) ·
**blocker sayısı DEĞİŞMEDİ (1 — yalnız A-08), verdict BLOCKED.**

**Prompt'un sert ön koşulu DÜŞTÜ ve slice bilerek daraltıldı.** P-E6'nın 1–3. maddeleri
(gerçek worker oracle'ları, historical compat, manifest namespace) üretimde bir shared kod
yolu varsayıyor; **yok**. Ölçüldü: `_EngineParticipant` yok · `_use_unified_clock` yok ·
`ItemParticipant.settle`/`.finalize` yok · `iter_portfolio` yok · `PHASE_ORDER` P10 taşımıyor.
`C2` imzaya bloklu: **`G9` + `G13` imza blokları #750 ile YARATILDI ama imzalanmadı**
(kutular `[ ]`, `karar veren:` boş). **22 containment ön koşulunun 2'si yeşil** (#1 = ADIM 71
describe/book split; #19 = ADIM 72 R-1 pini); `G8`/`G14` (#559/#544) **açık**, `G10` (ADR §16
Gate 2) **talep edilmedi**. Satır satır kanıt:
`docs/audit/closure_w0_containment_lift_preconditions_2026-08-17.md` §2.

**Sevk edilen iş = P-E6'nın 5. maddesi, ve ölçüm onu en değerli parça yaptı.**
**BULGU 1: containment kapısı TEK DÜNYALIYDI.** `active_v1`'i kuran tek test
(`test_backtest_portfolio_mode.py:160`) resolver'ın flag'i **görmezden geldiğini** kanıtlamak
için var; yani flag'i okuyan üç üretim yüzeyi (`rules.py:154`, `backtest_run.py:542`,
`allocation_plan.py:59`) lifted dünyada **hiç koşulmamıştı**, ve frontend fixture'ı
(`portfolio.test.tsx:43`) `available: false` **sabitti**. YENİ
`backend/tests/unit/test_shared_allocation_two_world_gate.py` (**10 test**) + bir lifted-dünya
frontend render testi. **Hiçbir `future_dev` pini gevşetilmedi.**

**BULGU 2 (asıl sonuç): flag bir REDDETMEDİR, bir MOTOR değildir.** `jobs/backtest_engine.py:299`
her item'ı bağımsız replay edip `:364` `combine_item_runs` ile katlar ve
`shared_allocation_is_executable`'ı **hiç çağırmaz** (kaynak düzeyinde assert edildi). Bugün
flag çevrilse Ready Check blocker'ı düşer, admission guard reddetmeyi bırakır ve worker
shared-capital Result'ı **sıralı yaklaşımla** üretir: **drawdown 5000, gerçeği 3000.**
Okuru koruyan tek şey `portfolio_mode.py`'nin flag-bağımsızlığı (A19, iki dünyada da
`legacy_sequential`) — **sayı yine yanlış, yalnız dürüstçe etiketli.** `C9`'un neden SON
slice olduğunun ölçülmüş gerekçesi.

**BULGU 3 (`C9` devraldı):** `shared_allocation_capability_view()` lifted dünyada
`available: true` ile *"not available in this build"* mesajını **birlikte** yayımlar.
Bugünün sayfası korunuyor (`Portfolio.tsx:358` `!available` arkasında, yeni test bunu pinler)
ama blok yayımlanan **sözleşmedir**. #559 emsaliyle **characterization** pinlendi —
`C9` metinleri flag-aware yapınca o test **kırmızıya döner, kasıtlı**.

**DERS: `and`/`or` kapısını BİLEŞİK sonucuyla test etmek kısa devrenin arkasını ölçmez.**
Sekiz negatif kontrol ailesinden **biri yeşil kaldı** — `shared_allocation_requested`'ı
flag-aware yapan perturbasyon truth-table testimi hiç kırmadı, çünkü guard lifted dünyada
ilk terimde kısa devre yapıyor. Test **hücre başına iki conjunct'ı ayrı** assert edecek
şekilde yeniden yazıldı; perturbasyon **iki yönde de** kırmızı verdi.

**Kabul borcu ratchet'ine DOKUNULMADI** (yeni testler kriter kapatmıyor; bu slice hiçbir
tavana el sürmedi). **Sayı yazmıyoruz: bu slice'ın TABANINDA tavanlar A=1 · B=69 · C=6 ·
D=32 → açık 108 idi, ama ARADA #757 (ADIM 75) indi ve B'yi 66'ya, açık borcu 105'e çekti** —
canlı değer `docs/audit/acceptance_coverage_baseline.json`. Üretilmiş olgular tazelendi:
backend collected **3625 → 3635** (+10 test, +1 dosya), frontend call site **722 → 723** (+1);
taban ölçümü 3610 → 3620 / 718 → 719 idi, arada #751/#755/#757 indi ve **delta aynı kaldı**. **A4 NOT EVALUABLE kalır ve `covered`
işaretlenMEDİ.** Hiçbir issue kapatılmadı; `G9`/`G13`/`G10` **imzasız bırakıldı** (ADR §16).
`PROJECT_HISTORY.md` §ADIM 76 · `docs/ADIM74_LANDED_KICKOFF.md`.



> **ADIM 74 GÜNCELLEMESİ (2026-08-17).** Yukarıdaki *"sıradaki hamle bir İMZADIR"*
> tespiti **yeniden ölçüldü ve DOĞRULANDI** — ve bir adım netleşti: `G9` ve `G13`'ün imza
> **blokları artık VAR** (#750, `decisions:834` ve `:911`), ama **hiçbiri imzalanmadı**
> (kutular `[]`, `karar veren:` boş). Yani engel *"imzalanacak yer yok"* değil, **imzanın
> kendisi**. `C9`'un ek kapıları da ölçüldü: **`G8` (#559) ve `G14` (#544) İKİSİ DE AÇIK**
> (`reopened`), **`G10` (ADR §16 Gate 2) hâlâ talep edilmedi**, `G16` (A-08) açık.
> **22 containment ön koşulunun 2'si yeşil.** ADIM 74 bu yüzden `C2`'ye başlamadı;
> ajanın imzasız kapatabileceği işten **kapının ikinci dünyasını** seçti (yukarı).
> **Flag'e dokunulmadı.** Ön koşul tablosu:
> `docs/audit/closure_w0_containment_lift_preconditions_2026-08-17.md` §2.

> **ADIM 74 KAPANIRKEN DEĞİŞTİ — `G9` + `G13` İMZALANDI (#753, `9fc5580`, 21:54Z).**
> Ürün sahibi ADR §16 **Gate 1**'i oturum içinde imzaladı: **`G9` APPROVED as stated**,
> **`G13` = FOLD**. Kayıt **ADR-0002 §13.2** (+ §6 madde 6–7, §8.2 P10).
> **Ön koşul sayısı DEĞİŞMEDİ (2/22)** — madde #5 bileşiktir, P10 **sevk edilmedi**
> (*"No product code ships with this amendment"*), `PHASE_ORDER` hâlâ sekiz faz.
> **AMA yukarıdaki "sıradaki hamle bir İMZADIR" satırı ARTIK GEÇERSİZ — sıradaki hamle
> KODDUR: `C2` / E4b.** `settle`/`finalize` **zorunlu** Protocol üyesi (`hasattr` probe'u
> **yasak**, fail-open), P10 döngüden sonra **bir kez**, sonra **FOLD**.
> **`G10` (Gate 2 / lift) hâlâ TALEP EDİLMEDİ**; `G11`/`G12`/`G8`/`G14` ve
> `participant.py` importer-allowlist incelemesi açık → **flag'e dokunmak hâlâ yasak.**



## Stage 77 — P1 + P4: Ready Check'in tick-data bacağı ve RUN admission'ın tick pinleri batch'lendi (PR #751 + #754) landed

**Ne indi.** #617'nin şeklinin **dördüncü ve beşinci** örneği — ikisi de bir döngünün içinde
duran per-item okuma. Ölçülen değerler, tahmin değil:

| Bacak | PR | Onarım öncesi | Sonra |
|---|---|---|---|
| Ready Check tick-data uygunluğu (`_resolve_tick_data_issues`) | #751 | 1 → 11 statement, slope 1 | tek `IN()`, `per_item: 0` |
| RUN admission tick pinleri (`_resolve_tick_pins`) | #754 | 3 → 23 statement, slope 2 | üç batch'li okuma, `per_item: 0` |

**Ürün kodu değişti, gözlenebilir davranış değişmedi.** Migration yok · `ENGINE_VERSION`
değişmedi · OpenAPI değişmedi · golden digest'ler ellenmedi · alembic head
`0043_i08_registry_strategy_fks` · `SHARED_ALLOCATION_STATUS` = `future_dev`. **Blocker sayısı
değişmedi (1 — yalnız A-08), verdict BLOCKED.** Kabul borcu tavanları oynamadı.

**P4 admission yolundaki İLK bütçe satırı.** `docs/performance/README.md` §8 run admission'ı
deterministik kapılanan yüzey diye adlandırıyordu ama onu ölçen satır yoktu.

**Yeni semboller — ikisi de mevcut bir okuyucunun aynası, üçüncü idiom yok:**
`market_data.py::find_approved_tick_revisions_for_instruments` (← `get_dataset_roots`) ve
`strategy.py::get_strategy_revisions` (← `mainboard.get_work_object_revisions`). Ayrıca
`readiness_check.py::_mirror_ref`, `::_tick_data_demands` ve `backtest_run.py::_pinned_mirror_refs`.
`_resolve_strategy_payload` **opsiyonel** bir prefetch haritası alır (`mirrors=None`), böylece
"mirror NEDİR" sorusunun tek tanımı korunur ve eski çağıranlar statement statement değişmez.

**Asıl nokta bir sözleşme, bir hız detayı değil.** Pinlenen revizyon id'si değişmez manifest'e
girer (doc 15 §15, INF-04/INF-05), yani aynı `execution_key`'i paylaşan iki koşu farklı tick
yolu replay edemez. `DISTINCT ON` yalnız tekil okuyucunun sırası **TOTAL** olduğu için güvenli
(`created_at DESC, revision_id DESC`), ve test bunu **eşit `created_at`'li** bir fixture ile
sürüyor — ayrı zaman damgalarıyla tie-break hiç koşmaz ve her implementasyon geçer.

**Leg 3 (`_resolve_external`) bilerek onarılmadı**, satırı `per_item: 1`'de bırakıldı: orada
per-item kazanan tanımsız (`work_object_revision_id` UNIQUE değil), yani hangi satırın kazandığı
bir **ürün kararıdır (G15)**.

**Kural metni daraltıldı, gevşetilmedi.** `docs/performance/README.md` §7'nin *"ölçen slice
admission'a dokunmamalı"* cümlesi, tek başına okununca P4'ü yasaklıyordu. Öznesi her zaman
**sayacı sevk eden** slice'tı; sonraki tek-yüzeyli slice'ın bunun yerine borçlu olduğu dört şey
yazıldı.

**Dürüst sınır.** İki PR da **kapanış ritüeli olmadan** açıldı ve **ayrı ayrı** merge edildi;
bu kaydı dalgayı merge eden oturum ürün sahibinin talimatıyla yazdı. Kayıtta **ölçülen** ile
**dalların iddia ettiği** ayrı işaretli — negatif kontroller bu kapanışta yeniden koşulmadı.
**#617 / #618 issue durumlarına dokunulmadı.** `PROJECT_HISTORY.md` §ADIM 77 ·
`docs/ADIM77_LANDED_KICKOFF.md`.

## Stage 78 — kabul borcu batch 08 (doc 04 backend): dört kriter kapandı, iki bulgu landed

**Ne indi.** Yalnız **test + defter**. Ürün kodu **değişmedi**, migration **yok**, OpenAPI
**değişmedi**, `ENGINE_VERSION` **değişmedi**, containment `future_dev`. Blocker sayısı
**değişmedi** (1 — yalnız A-08), verdict **BLOCKED**.

Doc 04 (Trading Signal), **backend** yüzeyi. Altı sınıf-B adayının **her birinin tek açık
clause'u** vardı, yani kapatmak satırın tamamını kapatıyordu — ama ikisi ölçümde sınıf B
çıkmadı.

| Kriter | Kapanan clause | Neden açıktı |
|---|---|---|
| `TS-15` | `.c2` | sayfadaki her sahiplik testi ikinci bir **düz USER** seçiyordu; **SUPERVISOR** hiç denenmemişti |
| `TS-18` | `.c2` | yalnız projeksiyon düşüşü assert ediliyordu; **trash + audit + outbox** hiç sorgulanmamıştı |
| `TS-10` | `.c3` | allocation açılınca bağımsız sermayenin **korunduğu** okunup doğrulanmamıştı |
| `TS-08` | `.c3` | düzeltilen import'un **ilk raporu** bozmadığı assert edilmemişti |

**Tavanlar İNDİ:** `partial` **97 → 93**, `debt_class.B` **66 → 62**. Açık kabul borcu
**105 → 101** (A=1 · B=62 · C=6 · D=32). Clause düzeyinde `covered` **1015 → 1019**,
`uncovered` **112 → 108**.

**DÖRT negatif kontrol, dördü de kırmızı** — her biri davranışı **üründen** kaldırarak:
`can_edit`'e `Role.SUPERVISOR` kısayolu → `DID NOT RAISE AccessDeniedError` ·
`add_trash_entry` silinince → `NoResultFound` · allocation açılışında sermaye null'lanınca →
`assert None == '10000'` · `run_import` eski özetleri yeniden yazınca → rapor bayt-eşitliği
kırılıyor.

**İKİ BULGU, ikisi de farklı şekilde:**
- **`TS-07.c2` sınıf D** — motorun **hiç sinyal-olayı girdisi yok**. `run_engine`'in
  parametreleri arasında yok, `jobs/backtest_engine.py` `trading_signal`'dan hiç söz etmiyor,
  `domain/backtest/` altında `trading_signal.events` import edilmiyor ve engine'in kendi
  `SignalEventRow`'u bir **çıktı** günlüğü. Motordaki tek `available_at` kapısı funding/research
  ekseni — bu satırın ödünç almaması söylenen kardeş.
- **`TS-02.c2` YANLIŞLANAMAZ** — transient draft açıcı (`start_external_work_object_draft`)
  **session'sız saf bir fonksiyon**; tek çağıranı yalnız `actor` ve `kind` geçiyor. Draft'ın
  snapshot'ta görünebileceği hiçbir yol yok, yani yeşil bir assertion **kapsamak değil
  işaretlemek** olurdu. **Bilerek açık bırakıldı.**

Doc 04'te sınıf B kalmadı; kalan satırlar iki bulgu ve önceden sınıf-D olan `TS-03`.
`PROJECT_HISTORY.md` §ADIM 76 · `docs/ADIM76_LANDED_KICKOFF.md`.


## Stage 79 — kabul borcu batch 09 (doc 03 backend): iki kriter kapandı, iki bulgu landed

**Ne indi.** Yalnız **test + defter**. Ürün kodu **değişmedi**, migration **yok**, OpenAPI
**değişmedi**, `ENGINE_VERSION` **değişmedi**, containment `future_dev`. Blocker sayısı
**değişmedi** (1 — yalnız A-08), verdict **BLOCKED**.

Doc 03 (Add Outsource Signal), **backend** yüzeyi. Beş sınıf-B adayının her birinin tek açık
clause'u vardı; **ikisi kapandı, ikisi bulgu çıktı, biri frontend olduğu için ertelendi**.

| Kriter | Kapanan clause | Neden açıktı |
|---|---|---|
| `AOS-13` | `.c3` | doc 03 §13'ün adlandırdığı **SUPERVISOR** rolü hiç sürülmemişti (testler ikinci bir düz USER ya da Agent seçiyordu) |
| `AOS-05` | `.c1` | transient-draft sözleşmesi yalnız **trading_signal** dalında kanıtlıydı; `trade_log` ödünç alınmamıştı |

**Tavanlar İNDİ:** `partial` **93 → 91**, `debt_class.B` **62 → 60**. Açık kabul borcu
**101 → 99** (A=1 · B=60 · C=6 · D=32). Clause düzeyinde `covered` **1019 → 1021**,
`uncovered` **108 → 106**.

**`AOS-13.c3` iki fiili de sürer** (`create_work_object_revision` **ve**
`soft_delete_work_object`), **iki external kind** üzerinde, ve reddin **kalıcı** olduğunu
doğrular. Edit çağrısı geçerli bir `available_time` taşır — yoksa çağrı izinli bir aktör için
bile anti-lookahead doğrulamasına takılırdı ve **red yetkilendirmeye atfedilemezdi**.

**İKİ negatif kontrol, ikisi de kırmızı:** `can_edit`'e `Role.SUPERVISOR` kısayolu → iki
parametrizasyonda da `DID NOT RAISE AccessDeniedError`; opener yalnız `TRADE_LOG` dalında
`root_id` döndürünce → yeni test kırmızı, **kardeşi yeşil kalıyor** (per-kind pinlemenin
varlık sebebi tam olarak bu).

**İKİ BULGU — ikisi de YANLIŞLANAMAZ:**
- **`AOS-04.c2`** `TS-02.c2`'nin **birebir ikizi**; satırın kendi notu zaten kabul ediyordu
  (*"bu bir argüman, assertion değil"*).
- **`AOS-06.c2` daha da net:** `discard` `commands/mainboard.py` ve `routes/mainboard.py`
  içinde **hiç geçmiyor** — discard komutu, ucu, handler'ı **yok**. Tek anma
  `OutsourceSignal.tsx:97`'deki *"leaving this page discards nothing durable"* yorumu, yani
  yokluğun **tarifi**. Clause bir **eylemsizliğin** etkisizliğini iddia ediyor.

**`AOS-01.c2` ertelendi, kapatılamaz olduğu için değil FRONTEND olduğu için** — chooser
seçimleri link olarak render ediliyor, yani klavye pariteliği native; assertion yazılabilir ve
negatif kontrolü gerçek (link'i `div onClick` yapmak). Doc 07'nin batch 06/07 bölünmesinin
aynısı. `PROJECT_HISTORY.md` §ADIM 78 · `docs/ADIM78_LANDED_KICKOFF.md`.


## Stage 80 — kabul borcu batch 10 (doc 03 frontend): AOS-01 kapandı, doc 03'ün test borcu bitti landed

**Ne indi.** Yalnız **test + defter**. Ürün kodu **değişmedi**, migration **yok**, OpenAPI
**değişmedi**, `ENGINE_VERSION` **değişmedi**. Tek clause'luk parti: `AOS-01.c2` (chooser klavye
paritesi, doc 03 §14) — batch 09'da **yüzey** gerekçesiyle ertelenmişti.

**Parite native:** `pages/OutsourceSignal.tsx` her seçimi `<Link>` (`<a href>`) olarak render
ediyor. Eksik olan davranış değil assertion'dı. Yeni test **"seçimler link"i tekrarlamıyor** —
o zaten `AOS-01.c1`'de asserted ve `tabIndex={-1}` altında **yeşil kalır**. Assertion **sıra**
hakkında: chooser bölgesinde klavyeye pointer'ın stop'larının **tam aynısı, aynı sırayla**
sunulur.

**İki negatif kontrol, ikisi de yeni testi izole etti** (diğer altısı yeşil): `tabIndex={-1}` →
`expected [] to deeply equal [<a>, <a>]`; chooser içine `tabIndex={0}` div → üç elemanlı dizi.

**Dürüst sınır:** jsdom'da native anchor activation yok → `Enter` **basılamaz** ve test bastığını
iddia etmiyor. Gerçek tarayıcı kanıtı `e2e/specs/14-keyboard-flow.spec.ts` (`@a11y`) içine
yazılırdı; bu container o suite'i koşamadığı için (Docker Hub **403**) **yazılmadı**.

**Tavanlar:** `partial` **97 → 96**, `debt_class.B` **66 → 65**, açık borç **105 → 104**
(A=1 · B=65 · C=6 · D=32). `total_criteria` **383** ve `uncovered` **8** değişmedi.

**Zincir notu:** freeze **main `347fe19`**'a karşı ölçüldü; batch 08/09 hâlâ **PR #768**'de
(91 / B 60). İkinci inen taraf rebase edip **yeniden dondurmalı**.

**Blocker sayısı DEĞİŞMEDİ (1 — yalnız A-08), BLOCKED.** `PROJECT_HISTORY.md` §ADIM 80 ·
`docs/ADIM80_LANDED_KICKOFF.md`.


## Stage 82 — kayıtsız inen `C2`'nin ritüeli (PR #759): ürün kodu sevk edildi, kaydı yoktu landed

**Ne indi.** Yalnız **defter** — `backend/src` altında bu slice'ta **sıfır** satır. Kaydettiği
slice ise ürün kodu değiştirdi: **PR #759** (`c78b15b`, 2026-08-18T13:42Z) `settle` + `finalize`
**zorunlu** Protocol üyelerini, `PHASE_ORDER`'a **P10**'u (8 → 9 faz), `PortfolioLedger.fold_tick`
ve `iter_portfolio`'yu sevk etti. `ENGINE_VERSION` **değişmedi**, migration **yok**, OpenAPI
**değişmedi**, `engine_golden_digests.json` **dokunulmadı**.

**Neden bir ritüel PR'ı.** #759 main'e indi ama `PROJECT_HISTORY.md`'de **hiç anılmıyordu**
(`grep -c '#759'` → **0**); handoff satırı ve kickoff'u yoktu, yani kapanış ritüelinin 1–6.
maddeleri o slice için **hiç koşmadı**. Aynı desen **#728/#729 = ADIM 69/70**'te de yaşandı ve
sonradan bir ritüel PR'ı ile kapatılmıştı — bu onun tekrarı.

**Anlatı uydurulmadı.** Her iddia ağaca karşı yeniden ölçüldü, PR gövdesinden kopyalanmadı — ve
gövde **bir noktada yanlış çıktı**: *"containment gate el değmedi"* diyor, oysa gate **güçlendi**
(`_LOOP_ENTRY_POINTS` artık `iter_portfolio`'yu da arıyor + yeni bir meta-test `participants`
alan her public callable'ın tuple'da adlandırılmasını zorunlu kılıyor). O ekleme olmadan bir
üretim modülü P10 dahil tüm fazları `iter_portfolio` üzerinden sürerken containment assertion'ı
**yeşil kalabilirdi**.

**Blocker sayısı DEĞİŞMEDİ (1 — yalnız A-08), BLOCKED.** `SHARED_ALLOCATION_STATUS` =
`future_dev`. `PROJECT_HISTORY.md` §ADIM 82. **Kickoff'u YOK, bilerek** — geriye dönük kayıt
(ADIM 70 emsali); canlı seed en yüksek numaralı kickoff belgesidir.
## Stage 81 — §2 kapı tablosu tazelendi: G4/G12/G15 brifingli, sayım 11'e düzeltildi (PR #769) landed

**Ne indi.** Yalnız **defter**. Ürün kodu **değişmedi**, migration **yok**, OpenAPI
**değişmedi**, `ENGINE_VERSION` **değişmedi**. Tek dosya, **+93/−30**:
`docs/implementation/final_closure_ordered_plan_2026-08-13.md` §2 (+ `F2` bloğu, mermaid kapı
düğümleri, §6 envanteri, §7 md. 2). Squash merge **2026-08-18T17:11:11Z**.

**Kapı durumları yeniden ölçüldü.** `G4` (#755), `G15` (#747) ve `G12` (#752) artık
**BRIEFED ama İMZASIZ** — üçünün de satırı *"unbriefed" / "no owner"* diyordu. **Brifingli
kapı ≠ imzalı kapı ve sayımı değiştirmez.** `G11` imzalanacak yeri olmayan **tek** kapı kaldı
(PR **#771** açık, onu brifliyor).

**Sayım düzeltildi: 16 kayıtlı · 11 açık · 11 bloklayan.** Çözülmüş beş: `G5` · `G6` + `G7`
(Karar 2, imzalı 2026-08-14) · `G9` + `G13` (ADR `0002` §13.2, imzalı 2026-08-17). Eski
*"14 bloklayan"* = *"15 açık eksi G7"*'ydi; G7 çözülünce dışlanan kalmadı.

**İki hata kaydedildi (bu slice'ın asıl dersi).** (a) İlk sürüm *"13 açık"* dedi çünkü G6/G7
bayat tablodan **ölçülmeden** taşındı — STALE-BY-DEFAULT ihlali, ve **bir kapı değil bir
insan** yakaladı. (b) **Çift iş:** #772 aynı bölümü bağımsız tazeledi (~60 satır çakışma);
**ölçümü daha doğru olduğu için taban #772 oldu**, bu dalın iki eklemesi üzerine taşındı, #772
merge edilmeden kapatıldı. **Tazelemeye başlamadan önce açık PR'lara bak.**

**Bayatlama canlı gözlendi:** dalın *"Karar 4/5 kutuları hâlâ boş"* cümlesi **#774** inince
yanlış oldu ve merge'den önce düzeltildi. Kural genelleştirildi: **boş kutu kapının imzasız
olduğunu göstermez** (imza başka belgede olabilir); işaretin kendisi de otorite değildir.

**`F2` dürüst sınırı:** disposition hücreleri brifin **öncesinden** kalmadır ve yeniden
türetilmedi. Brif **dört** disposition taşır; **(D) gözlemlenebilir clamp** hücre almadı çünkü
brif kendi Result-artefakt şeklini *ölçülmedi* diye kaydediyor. `execution_key` **yalnız
B-ii'de** kayar. `ENGINE_VERSION` ve `migration` beş şeklin hepsinde **yok**.

**Süreç:** `cancelled ≠ failure` (bir E2E job'ı `playwright install` içinde ~30 dk asıldı,
hiçbir test gövdesi koşmadan) · **auto-merge dalı kendi güncellemez** (`behind` durumunda
bekler) · main bu PR açıkken **altı kez** ilerledi, dal **dört kez** güncellendi ·
`update_pull_request_branch` bu kez kayıp yapmadı ama **kural değişmedi** (ADIM 61 emsali).

**Hiçbir kapı imzalanmadı, hiçbir seçenek seçilmedi, hiçbir issue durumu değişmedi.**
**Blocker sayısı DEĞİŞMEDİ (1 — yalnız A-08), BLOCKED.** Suite **koşmadı** (ürün kodu yok);
codemap güncellemesi **gerekmedi**. `PROJECT_HISTORY.md` §ADIM 81 ·
`docs/ADIM81_LANDED_KICKOFF.md`.

## Stage 84 — kabul borcu batch 12 (doc 05 Trade Log, backend): TL-13 + TL-22 kapandı, onuncu bulgu landed

**Ne indi.** Yalnız **test + defter**. Ürün kodu **değişmedi** (`backend/src` altında sıfır
dosya), migration **yok**, OpenAPI **değişmedi**, `ENGINE_VERSION` **değişmedi**. Parti = bir
sayfa belgesi (**doc 05**) + bir yüzey (**backend**).

**Kapandı — `TL-13.c3`:** iki yarısı da kanıtlıydı ama **dikişi hiç geçilmemişti**. Yeni test
var olan bir readiness raporunu bir Trade Log pin'inin **üzerinden taşır**: pin'den önce
`is_current is True`, sonra `state == ReadinessState.STALE` + `is_current False` +
`composition_fingerprint != current_fingerprint`, **ve** `stored_state` ile pinlenen fingerprint
değişmemiştir (rapora **yazılmış** bir bayrak ilk üçünü karşılar, doc 14 §12.2'yi çiğnerdi).

**Kapandı — `TL-22.c3` + `.c4`:** dayanıklı `AgentToolCall` satırı yalnız RED yolunda
okunuyordu; başarı yolu dispatcher'ın **bellekte** kurduğu sözlüğü assert ediyordu. Yeni test
gerçek `task_id` + `checkpoint_id` geçirip satırı geri okur (SUCCEEDED, `failure_code` None,
owner/scope/correlation, `response_ref`/`artifact_output_ref`). `.c4`: **`auto_repinned is False`
BAŞKA bir garantidir** — yeni test bir insan panosu kurar ve Agent'ın `attach=True` işinden sonra
o panonun item id'leri / `composition_hash` / `row_version`'ının kıpırdamadığını kanıtlar.

**Clause kapandı, tavan oynamadı — `TL-16.c3`:** iki yazar **aynı** gözlenen head'den sürülür,
kök `revision_no == [1, 2]` tutar ve kaybedenin adı hiçbir payload'da yoktur.

**BULGU (onuncu) — `TL-16.c4` SEVK EDİLMEMİŞ.** `WorkObjectRevisionConflictError`'un üç raise
yeri de **çıplak**; `AppError.__init__` `details = []` yazar ve `scope_id`/`field_path`'i None
bırakır → 409 zarfı kökün güncel head'i hakkında **hiçbir şey** taşımaz. Sınıf D şekli,
**taşınmadı** (B → D tavan yükseltir). Bu yüzden `TL-16` **partial/B kalır** — clause ≠ kriter.

**DERS — kırmızının HANGİ assertion'da olduğunu oku.** `TL-22.c4`'ün ilk negatif kontrolü
kırmızı verdi ama `status == succeeded` üzerinde: özellik **iki bağımsız kapıyla** korunuyor
(aktör kapsamlı çözüm **ve** `_require_owned_workspace`), yani tek kapıyı kırmak mutasyon değil
**REJECTED** üretir. Sayılan kontroller: ikisi birden kapalı (workspace-kimliği kırmızı) +
yabancı panoya `row_version` sızıntısı (pano-durumu kırmızı). Defterde
`TL_22_c4_is_defended_by_two_gates_not_one` olarak kayıtlı.

**Altı negatif kontrol koştu, altısı da hedef assertion'ı izole etti** (`stale=False`,
`stale=True`, OCC guard silme, `task_id/checkpoint_id=None`, terminal olmayan status, yabancı
pano bump'ı).

**Tavanlar:** `partial` **86 → 84**, `debt_class.B` **55 → 53**, açık borç **94 → 92**
(A=1 · B=53 · C=6 · D=32). Clause: `covered` 1028 → **1032**, `uncovered` 101 → **97**.
`total_criteria` **383** ve `uncovered` **kriter** **8** değişmedi.

**Zincir notu:** dal `aecd72c`'de 88/57 dondurdu; PR açıkken **#781** aynı tabandan
**86/55** dondurup indi. Kriter kümeleri **AYRIK** olduğu için fark alınabilirdi — alınmadı:
rebase edilip `--report` **merged ağaçta** yeniden koşuldu → **84/53**.

**Açık kalan doc 05 satırları:** `TL-01.c4` · `TL-02.c2` · `TL-11.c3` (sınıf C bulgusu) ·
`TL-14.c4` · `TL-16.c4` (bu slice'ın bulgusu) · `TL-18` (**frontend** — tümleyen parti).

**NUMARA:** bu slice **83** yazıldı; PR açıkken **#781** merge edilip hem ADIM 83'ü hem
`batch 11` etiketini aldı (doc 18 backend) → **merge edilmiş ad kazanır**, bu kayıt **84 /
batch 12**. Dal ve commit `adim-83` yazar.

**Blocker sayısı DEĞİŞMEDİ (1 — yalnız A-08), BLOCKED.** Codemap güncellemesi **gerekmedi**
(yeni endpoint / tablo / sayfa / job yok). `PROJECT_HISTORY.md` §ADIM 84 ·
`docs/ADIM84_LANDED_KICKOFF.md`.


## Stage 83 — kabul borcu batch 11 (doc 18 backend): dört kriter kapandı, doc 18'in backend borcu bitti landed

**Ne indi.** Yalnız **test + defter**. Ürün kodu **değişmedi** (`backend/src` ve `frontend/src`
altında sıfır dosya), migration **yok**, OpenAPI **değişmedi**, `ENGINE_VERSION` **değişmedi**.
Belge + yüzey: **doc 18 (Analysis Lab), backend**.

**Kapananlar.** `AL-05` (queued directive'in audit + outbox satırı, directive id'sine kapsanmış,
sevk edilen `agent.directive.queued` adına pinli) · `AL-09` (Supervisor reddinden sonra runtime
satırı **geri okunuyor**: pending control yok, `row_version` kıpırdamamış) · `AL-10` (Stop
admission'dan **sonra**, `run_backtest`'ten **bir sınır önce**: `BacktestRun` var, `BacktestResult`
yok; stop öncesi checkpoint'ler + controlled cancellation'ın kendi `safe_checkpoint`'i hayatta) ·
`AL-18` (aynı kökte yeni revizyon indikten sonra pinlenmiş context manifest kaymıyor; üç bağımsız
okuyucu + "yeni revizyon → yeni manifest → yeni task" yarısı). Ayrıca `AL-06.c2` (reddedilen boş
directive hiçbir satır bırakmıyor).

**`AL-10` vacuous olabilirdi.** Hiç backtest admit etmeden "Result yok" demek totolojidir. Test bu
yüzden durable executor'ı (`jobs/agent_executor.py`) sürüyor ve Admin Stop'unu **`backtest_requested`
checkpoint'inde** bastırıyor — `BacktestRun` satırı ve engine job'ı **vardır**, `run_backtest`
**bir sonraki satırdadır**. Basış executor'ın kendi `_checkpoint` yardımcısı sarılarak enjekte
edilir; koşan komut üretimdeki `stop_run`'dır.

**Altı negatif kontrol, altısı da yalnız yeni testi düşürdü** — her birinde aynı kriterin **mevcut**
testleri yeşil kaldı. En öğreticisi: `data_bundle.resolve` taze manifest'i çağıran task'a
damgalayınca (kriterin yasakladığı naif implementasyon) **tüm** gateway + executor + e2e agent
suite'i yeşil kalıyor, yalnız yeni test kırmızı.

**Tavanlar:** `partial` **90 → 86**, `debt_class.B` **59 → 55**, açık borç **98 → 94**
(A=1 · B=55 · C=6 · D=32). Clause `covered` 1022 → **1028**, `uncovered` 105 → **99**.
`total_criteria` **383** ve `uncovered` **kriter** sayısı **8** değişmedi. Doc 18: **13 covered /
5 partial → 17 covered / 1 partial**.

**Açık kalan tek satır yüzey yüzünden açık:** `AL-06.c3` frontend'dir (`analysisLab.test.tsx`'te
directive doğrulama testi yok) → sıradan sınıf-B borcu, **bulgu değil**; bir doc 18 **frontend**
partisi bekler. **Bu partide yeni bulgu YOK** — seçilen beş clause'un adlandırdığı davranışın hepsi
sevk edilmişti ve parti seçilmeden önce okunarak doğrulandı.

**Dürüst sınır:** frontend kapıları bu container'da koşulmadı (`node_modules` yok, slice frontend'de
tek satır değiştirmedi) → otorite CI. `@a11y`/e2e'ye assertion yazılmadı (Docker Hub **403**).

**Zincir notu:** freeze **main `aecd72c`**'ye karşı ölçüldü — batch 08/09/10 zaten içinde, bir
önceki freeze zincir borcunu kapattı. Paralel bir batch önce inerse bu dal rebase edilip **yeniden
dondurulmalı**.

**Blocker sayısı DEĞİŞMEDİ (1 — yalnız A-08), BLOCKED.** `PROJECT_HISTORY.md` §ADIM 83 ·
`docs/ADIM83_LANDED_KICKOFF.md`.

## ADIM 85 — C3 / E4c: `_EngineParticipant` adaptörü landed (PR #777)

**Ürün kodu değişti, gözlenebilir davranış değişmedi — adaptörün `backend/src` içinde ÇAĞIRANI
YOK.** `ENGINE_VERSION` değişmedi · migration yok · OpenAPI değişmedi ·
`SHARED_ALLOCATION_STATUS` = `future_dev` · **50 golden digest bayt bayt aynı**.
**Blocker sayısı DEĞİŞMEDİ (1 — yalnız A-08), BLOCKED.**

Yeni modül `domain/backtest/participant.py` (`execution/` DIŞINDA, bilerek: içeride
containment gate'in importer taraması **kör** olurdu). **Beş importer allowlist'i** tek
adlandırılmış modülle genişledi (imzalı karar 2026-08-18, Seçenek A) — containment gate + dört
kardeş guard (clock / portfolio_ledger / intents / arbitration). **Karar yalnız containment
gate'i ölçmüştü; dördü insan incelemesine açıkça bırakıldı.** Negatif kontrol koştu (gerçek bir
üçüncü importer → kırmızı) ve kalıcı bir teste dönüştü.

İki değişmez pinlendi: **reconciliation** (havuz attribution'ı == item ledger realize delta'sı,
iki item'lık gerçek engine fixture'ı) ve **sleeve parity** (`Ci(t)`'nin iki türetimi, her tick
her item, üç sermaye modelinde). İkincisi **üründe de** zorlanır (`ParticipantDivergenceError`),
yalnız testte değil.

**Ölçülmüş, kapatılmayan gap:** giriş fill'inin komisyonu — loop'ta o kanal yok (`settle`
`None` döner), sonraki tick'e kaydırmak PD-2'nin zamanlama gerekçesini bozardı. Ölçüldü,
pinlendi, `portfolio_engine.py`'ye (yani `C4`/`C6`'ya) bırakıldı.
**Yeni bulgu:** `same_direction_stacking` şema **varsayılanı** `allow_stacking` ve adaptör onu
reddediyor → §C.3.7/§C.3.8 forkunun kayıtsız **üçüncü** kardeşi, `C6` için bir **ürün kararı**.

`PROJECT_HISTORY.md` §ADIM 85 · `docs/ADIM85_LANDED_KICKOFF.md`.


## Stage 86 — kayıtsız inen iki slice'ın ritüeli (P1-proof #765 + P2 #766): D.1'in leg 2'si kapandı landed

**Geriye dönük kayıt.** İki PR de main'e indi, ikisinin de `PROJECT_HISTORY` kaydı / handoff
satırı / kickoff'u **yoktu** (ölçüm anında main `aecd72c`: `grep -c '#765'` → 0,
`grep -c '#766'` → 0). #728/#729 = ADIM 69/70 ve #759 = ADIM 82 emsali.

- **#765** (`650a66a`, test-only) — `tests/integration/test_tick_revision_batch_parity.py`
  (+118): P1'in batch tick okuyucusunun sevk edilmiş per-item probe ile **aynı satırları**
  döndürdüğünün vaka vaka kanıtı. Aynı dalın P1'i **yeniden uygulayan** yarısı düşürüldü
  (`PR #764` kapatıldı, unmerged) — o hâliyle merge etmek sevk edilmiş bir fonksiyonu
  davranışça özdeş bir kopyayla değiştirir **ve** inmiş 250 satır testi silerdi.
- **#766** (`c2c966e`, 19 satır ürün kodu) — `_build_item_inputs` artık mirror pinlerini
  `_mirror_ref` ile toplayıp **döngüden ÖNCE** tek `get_strategy_revisions` batch'iyle deref
  ediyor. **#754 (P4) dikişi atmıştı ama bağlamamıştı**: `mirrors` parametresi vardı, çağıran
  onu geçmiyordu. Yeni bütçe satırı `readiness_check.strategy_mirror_leg` → `per_item: 0` (2/2).

**Migration yok · OpenAPI değişmedi · `ENGINE_VERSION` değişmedi · alembic head
`0043_i08_registry_strategy_fks` · `SHARED_ALLOCATION_STATUS` = `future_dev`.
Blocker sayısı DEĞİŞMEDİ (1 — yalnız A-08), verdict BLOCKED.**

**P-C2 §D.1 tablosu artık 3'te 2:** leg 1 flat (`tick_data_leg` 1/1, P1 = #751), leg 2 flat
(`strategy_mirror_leg` 2/2, bu slice), **leg 3 açık ve bilerek** — `run_readiness_check`
`per_item: 1` (8 → 18), anahtarı UNIQUE değil → batch'lemek **hangi satırın kazandığı**
sorusudur = **G15 ürün kararı**, imzasız.

**Bu oturumda fiilen ölçülenler** (Postgres 16 kaldırıldı, `18 passed` / **sıfır skip**):
güçlü negatif kontrol (batch kaldır + per-item geri koy) → `assert 12 <= 2` **kırmızı** ·
zayıf negatif kontrol (batch yerinde, yalnız `mirrors` düşür) → **yeşil kalır**, ki bu satırın
**kayıtlı sınırıdır** (ısınmış identity map yüzünden `session.get` hiç SQL üretmez) ·
parity mutasyonu (kazanan sıralaması ters) → **tam olarak bir** test kırmızı.
**Satır KALDIRILMIŞ batch'i yakalar, gereksiz okumayı değil.**

**Ders:** slice'a başlamadan önce **açık PR'ları tara**, sadece ağacı değil — bu dalgada iki
slice de paralel yazıldı ve iş çöpe gitti (#764 kapatıldı, P2'nin rakip mekanizması düşürüldü).

`PROJECT_HISTORY.md` §ADIM 86 · `docs/ADIM86_LANDED_KICKOFF.md`.


## Stage 87 — kabul borcu batch 13 (doc 18 frontend): `AL-06` kapandı, doc 18 tamamen kapandı landed

**Ne indi.** Yalnız **test + defter**. Ürün kodu **değişmedi** (`backend/src` ve
`frontend/src/pages` altında sıfır satır), migration **yok**, OpenAPI **değişmedi**,
`ENGINE_VERSION` **değişmedi**. Belge + yüzey: **doc 18 (Analysis Lab), frontend** — ADIM 83'ün
(batch 11) tümleyeni.

**Kapanan.** `AL-06.c3` — reddedilen directive submit'inden sonra compose kutusu boşalmıyor.
`AL-06` **covered** oldu ve **`debt_class` KALDIRILDI** (kriterin son açık clause'uydu).

**ASIL NOKTA — 422 önce ÖLÇÜLDÜ.** Doc 18 §15 `AL-06` satırı bir **422**'yi adlandırıyor, ama
sevk edilen istemcide whitespace-only bir directive sunucuya **hiç ulaşmaz** (düğme `disabled`,
`sendDirective` erken döner). Boş metin + stub'lanmış 422 biçimindeki bir test **üretimin
üretemeyeceği bir dünyayı** ölçerdi. Ölçülen çıkış yolu: iki boş-metin kapısı aynı fikirde
değil — compose kapısı JS `String.trim()` (**`U+001C`–`U+001F`'i KORUR**), komut kapısı Python
`str.strip()` (**siler** → `MESSAGE_TEXT_REQUIRED`, 422). Test bu yüzden **`U+001C`** gönderir.
Bu ayrım **kusur değildir** (fail-closed) ve bulgu olarak kaydedilmedi; §15 satırının sevk
edilen yüzeyde gözlenebilir olmasının **tek sebebidir**.

**İki negatif kontrol, iki AYRI eksen.** (1) compose temizliğini `onSuccess` → `onSettled`
yapmak **yalnız** yeni testi ve **yalnız** textarea-değer assertion'ını düşürür; dosyadaki diğer
on dört test yeşil kalır — clause'un neden açık olduğunun kanıtı. (2) `sendDirective`'i hiç
dispatch etmez yapmak yeni testi **`role="alert"` assertion'ında** düşürür → red **gözleniyor**,
varsayılmıyor; o kusur altında "metin hâlâ orada" **tek başına vacuous geçerdi**. (2) mevcut
directive-queue testini de düşürür, **beklenendir**: o kontrol clause'u değil tüm submit yolunu
kırar, o yüzden bir *vacuity* kontrolüdür, "yalnız yeni test" kontrolü değil.

**Sayılar.** Tavanlar İNDİ: `partial` **86 → 85**, `debt_class.B` **55 → 54**; açık borç
**94 → 93** (A=1 · B=54 · C=6 · D=32). Clause: `covered` **1028 → 1029**, `uncovered`
**99 → 98**. `total_criteria` **383** (TABAN) ve `uncovered` kriter sayısı **8** değişmedi.
**DOC 18 ARTIK TAMAMEN KAPALI (18 covered / 0 partial / 0 uncovered)** — doc 03 ve doc 07'ye
katıldı. **Yeni bulgu YOK**, hiçbir kriter yeniden sınıflandırılmadı.

**Yan iş.** `docs/audit/acceptance_semantic_traceability.md` ADIM 42 dönemi sayılarını taşıyordu
(`234/126`) → yeniden üretildi (`275/85`). O dosya `--check` kapısının **kapsamında değil**, o
yüzden sessizce bayatlamıştı; aynı işi **PR #783** de yapıyor → hangisi önce inerse diğeri
rebase edip yeniden üretmeli. `repository_facts.*` + `README.md` bloğu da tazelendi (frontend
unit test call site **724 → 725**).

**Dürüst sınır.** Backend kapıları **koşulmadı** (bu slice backend'de tek satır değiştirmedi,
Postgres bu container'da ayakta değil) → otorite CI. e2e / `@a11y` suite'lerine **hiçbir
assertion yazılmadı** (Docker Hub 403). Koşulanlar: `npm run lint` 0 · `npm run typecheck` 0 ·
`npm run coverage` 0 (**72 dosya / 735 test passed**) · acceptance `--ratchet` 0 ·
`generate_repository_facts.py --check` 0.

**Zincir notu.** Freeze **main `7f331c7`**'ye karşı ölçüldü — batch 08/09/10/11 zaten içinde.
Paralel bir batch önce inerse bu dal rebase edilip **yeniden dondurulmalı**.

**Çakışma ölçümü.** `C3` (`execution/participant.py` adaptörü) **İKİ açık PR** tarafından zaten
sürülüyor (**#777**, **#782**) → bu oturum ona **hiç dokunmadı**.

**Blocker sayısı DEĞİŞMEDİ (1 — yalnız A-08), BLOCKED.** `PROJECT_HISTORY.md` §ADIM 87 ·
`docs/ADIM87_LANDED_KICKOFF.md`.
## Stage 88 — kabul borcu batch 14 (doc 05 frontend): TL-18 yeni test yazılmadan kapandı landed

**Ne indi.** Yalnız **defter + üretilmiş artefakt**. Ürün kodu **ve test kodu** değişmedi
(`backend/` ve `frontend/` altında sıfır satır), migration yok, OpenAPI değişmedi.

**`TL-18` SIFIR TESTLE kapandı — kapsama zaten sevk edilmişti.**
`frontend/src/test/presentationState.test.tsx` **ADIM 60'ta (`d012a63`, PR #719)** inmiş ve
describe adı birebir *"Mainboard row presentation state (TS-16 / TL-18 / AOS-16)"*. Kardeş
`TS-16` ve `AOS-16` o iki düğümü o günden beri cite ediyordu; `TL-18` `uncovered` kalmış ve
notunda *"Nothing in the suite asserts this"* yazıyordu. **Defterde gözden kaçma, eksik kapsama
değil** — ADIM 68'in `RD-09.c4`'ü ile aynı şekil.

**Clause'un dört yarısı da o düğümlerde:** yazma isteği yok (`writeRequests` `[]`, üç satır
tipinin expand+collapse'ı boyunca, artı `/mainboard` kapsamlı non-GET filtresi) · `hash_abc`
değişmemiş · `Backtest Ready: Ready` değişmemiş. Birinci test **vacuity muhafızı** taşıyor
(editor bölümü gerçekten açılıyor), yani boş liste "hiç açılmayan toggle"dan gelemez.

**Negatif kontrol koşuldu ve doğru sebeple kırmızı:** üç `onClick` handler'ına `PATCH` eklemek
her iki düğümü de düşürdü. **`TL-02.c2`'nin yanlışlanamaz şekli DEĞİL** — orası üç noktalı,
burası tek noktalı.

**DERS:** ilk negatif kontrol denemesi dosyayı **hiç değiştirmedi** (handler dizesi üç yerde
geçiyor, yama tek eşleşme varsaydı) ve koşu **yeşil** kaldı — sahte bir "kontrol geçti" olarak
kaydedilebilirdi. Yakalayan şey yamaya konmuş `assert count == 3`'tü. **Negatif kontrolün ürünü
gerçekten değiştirdiğini ayrıca doğrula.**

**Tavanlar:** `uncovered` **kriter** **8 → 7** — bu sayaç **altı dalgadır** ilk kez oynuyor
(73/75/78/79/80/84 hep `partial`/`B` indirmişti). `debt_class.B` **52 → 51**, açık borç
**91 → 90** (A=1 · B=51 · C=6 · D=32). Clause: `covered` 1033 → **1034**, `uncovered` 96 → **95**.
`total_criteria` **383** ve `partial` **83** değişmedi.

**Zincir notu:** taban `cfce51e`. Dal `ccdd4fd`'de dondurmuştu; PR açıkken **#785** (batch 13,
doc 18 frontend) indi ve kabul borcuna DOKUNDU → dalın freeze'i geçersizdi. Kriterler AYRIK
olduğu için fark alınabilirdi, alınmadı: rebase edilip `--report` **merged ağaçta** koşuldu.

**Doc 05 bitti** (test slice'ının kapatabileceği anlamda). Kalanlar bulgu ya da sınıf C/D:
`TL-01.c4` · `TL-02.c2` · `TL-11.c3` · `TL-14.c4` · `TL-16.c4`.

**NUMARA:** bu slice **87 / batch 13** yazıldı; PR açıkken **#785** merge edilip **ikisini
birden** aldı (doc 18 frontend) → merge edilmiş ad kazanır, bu kayıt **88 / batch 14**. ADIM
84'te #781 ile aynısı olmuştu; çakışma yapısal, bu yüzden devir promptu numarayı **ve** parti
etiketini commit'ten hemen önce yeniden doğrulatır.

**Blocker sayısı DEĞİŞMEDİ (1 — yalnız A-08), BLOCKED.** Codemap güncellemesi **gerekmedi**.
`PROJECT_HISTORY.md` §ADIM 88 · `docs/ADIM88_LANDED_KICKOFF.md`.


## Stage 91 — kabul borcu batch 15 (doc 17 backend): dört kriter kapandı landed

**Ne indi.** Yalnız **test + defter**. Ürün kodu **değişmedi** (`backend/src` ve `frontend/src`
altında sıfır satır), migration **yok**, OpenAPI **değişmedi**, `ENGINE_VERSION` **değişmedi**.
Belge + yüzey: **doc 17 (Arrange Metrics), backend**.

**Kapananlar.** `AM-03` (`.c2` + `.c3`) · `AM-05` (`.c2`) · `AM-06` (`.c3`) · `AM-07` (`.c2`).
Dördünde de bu **son** açık clause'du → dördü **covered**, dördünün **`debt_class` KALDIRILDI**.

**Parti ölçümle seçildi.** Doc 03 / 07 / 18 kapalı; doc 05 açık bir PR tarafından sürülüyordu
(**#797**, `TL-18`, frontend — bu dal açıkken **indi**); `HAT B` (`C4`) **üç** açık PR taşıyordu
(**#799** · **#800** · **#801**) → bu oturum ikisine de **hiç dokunmadı**. Doc 17'nin dört
sınıf-B satırı tek bir komuta (`commands/metric_profile.py::create_metric_profile_revision`)
bakıyordu.

**Dördü de "yanlış dünyada ölçülmüş" şekline sahipti.** `AM-05.c2`: mevcut test boş seçimi
**hiç revizyonu olmayan** SYSTEM DEFAULT sentinel'ine gönderiyor, korunacak revizyon yok.
`AM-07.c2`: sürülen tek sahiplik kapısı **kilitsiz** profil + **değişmiş** seçim (o `AM-14`'ün
senaryosu). `AM-06.c3`: lock/unlock testi bir `BacktestResult` satırına hiç dokunmuyor.
`AM-03.c2`: e2e'nin manifest assertion'ının arasından bir Trash delete+restore geçiyor →
iddia Apply'a **kapsanmış değil**; `.c3` için hiçbir yerde run/job satırı sayılmıyordu.

**Ölçüm kararları.** Boş tabloda "run oluşmuyor" zayıftır → önce **SUCCEEDED bir `BacktestRun`
+ `Job`** seed edilir ve sayı değil **kimlik listesi** karşılaştırılır · Apply'ın **gerçekten
indiği** ayrıca assert edilir (yoksa "hiçbir şey kıpırdamadı" hiçbir şey yapmayan bir çağrı için
de geçer) · satırlar `flush()` + `expire_all()` sonrası **veritabanından** okunur · `AM-06`
**dokuz kodun tamamını** uygular (projeksiyon daralamaz) ve **NULL metrik karşılaştırılan
kümenin içindedir** · `AM-07`'de aynı çağrı **sahibi** tarafından da yapılır ve **başarılı
olur** → red kimin çağırdığına atfedilebilir.

**BEŞ negatif kontrol, hepsi elle koştu, her birinde HANGİ assertion'ın kırmızı olduğu okundu.**
(1) Boş-seçim `raise`'ini `normalize_selection`'dan alıp `_op` içinde **append'in ALTINA**
taşımak → **yalnız** yeni `AM-05` testi, **tam olarak head assertion'ında**;
`test_min_selection_blocked` **yeşil kalır** — bu yüzden `pytest.raises` tek başına o clause'u
asla kapatamazdı. (2) Head kilitliyken `ensure_can_edit`'i atlamak → **yalnız** yeni `AM-07`
testi; `test_foreign_profile_role_guard` **yeşil kalır**, çünkü kilitsiz profil sürer — **eski
testin yeşil kalması kusur değil KANITTIR**. (3) Lock'un `metric_value` satırlarını sıfırlaması
→ **yalnız** yeni `AM-06` testi, çevrim ortasındaki kart karşılaştırmasında. (4) Apply'ın `Job`
eklemesi → job-listesi assertion'ı. (5) Apply'ın `BacktestRun.manifest_hash`'i yeniden yazması
→ manifest tuple'ı. Her kontrolden sonra ürün kodu bayt bayt geri yüklendi.

**Sayılar (ölçüldü, aritmetik YAPILMADI).** Tavanlar İNDİ: `partial` **83 → 79**,
`debt_class.B` **51 → 47**; açık borç **90 → 86** (A=1 · B=47 · C=6 · D=32). Clause:
`covered` **1034 → 1039**, `partial` **7 → 6**, `uncovered` **95 → 91**. `total_criteria`
**383** (TABAN) ve `uncovered` kriter sayısı **7** değişmedi. Doc 17: covered **7 → 11**.
**Yeni bulgu YOK**, hiçbir kriter yeniden sınıflandırılmadı.

**Dürüst sınır.** Bu container'a **PostgreSQL 16 KURULDU** (+ `alembic upgrade head`), o yüzden
dört case ve beş negatif kontrolün hepsi **gerçekten koştu** (`test_arrange_metrics.py`
**17 → 21 passed**). Frontend'e sıfır satır dokunuldu → frontend kapıları koşulmadı, otorite CI.
e2e / `@a11y` suite'lerine **hiçbir assertion yazılmadı**. Koşulanlar: `ruff check` 0 ·
`ruff format --check` 0 · `mypy src` 0 · acceptance `--ratchet` 0 ·
`generate_repository_facts.py --check` 0.
**İki tuzak kaydedildi:** `pytest … | tail` **`tail`'in** exit code'unu verir (200 collection
error `exit 0` göründü) · yerelde **`alembic upgrade head` koşulmadan** tam suite ~40 sahte hata
verir (contract testleri migrate edilmiş `DATABASE_URL` DB'sini kullanır).

**Zincir notu — UYARI ATEŞLENDİ.** Dal önce `a5b46ab`'ye karşı donduruldu (79/8, B 48); PR
açıkken **#797 (ADIM 88 / batch 14)** indi ve **aynı serial dosyalara** dokundu → dal
`ee5ab38`'e taşındı, yama orada **yeniden uygulandı**, `--ratchet` **yeniden koşuldu** (79/7,
B 47). **`partial` tesadüfen aynı, `B` ve `uncovered` DEĞİL** — iki freeze'i elle çıkarmak
yanlış tavan üretirdi.

**NUMARA.** Bu kayıt `ADIM 89` yazıldı, **`ADIM 91`**'e taşındı: **#799**
`docs/ADIM89_LANDED_KICKOFF.md`, **#802** `docs/ADIM90_LANDED_KICKOFF.md` **ekliyor**, ikisi de
açık. **Çakışma başlıkta değil DOSYA YOLUNDADIR.** Parti numarası taşınmadı (batch 14 = #797).

**Blocker sayısı DEĞİŞMEDİ (1 — yalnız A-08), BLOCKED.** `PROJECT_HISTORY.md` §ADIM 91 ·
`docs/ADIM91_LANDED_KICKOFF.md`.

## Stage 92 — C4 / E5: worker'ın paylaşımlı saat dalı + iptal kontrol noktası + daraltılmış tripwire landed

**Ürün kodu değişti (TEK dosya), gözlenebilir ÜRETİM davranışı değişmedi.** `ENGINE_VERSION`
değişmedi · migration yok · OpenAPI değişmedi · alembic head `0043_i08_registry_strategy_fks`
(tek head) · `SHARED_ALLOCATION_STATUS` = `future_dev` (**DEĞİŞMEDİ**) · **50 golden digest bayt
bayt aynı**. Planın no-touch listesi ölçüldü ve tutuldu: `manifest.py`, `engine.py`,
`portfolio_engine.py`, `capability.py` **el değmedi**.
**Blocker sayısı DEĞİŞMEDİ (1 — yalnız A-08), BLOCKED.**

`C1`/`C2`/`C3`'ün kurduğu zincirin **üretim çağıranı** yazıldı — ve **kimsenin giremeyeceği**
bir dal olarak: `_use_unified_clock(capital_execution)` **tek** yerde
(`shared_allocation_is_executable() and shared_allocation_requested(...)`), dal item döngüsünün
**kardeşi**, artı ADR §3.2'nin `len(prepared_items) > 1` koşulu (tek yürüyen item'da A14
`run_engine`'i şart koşar). Yol: `_shared_clock_inputs` (saf) → `_replay_shared_clock`
(`iter_portfolio` generator'ını elle sürer, tick-strided iptal kontrolü = **checkpoint #3b**,
ADR §14 **A21**) → `project_portfolio_run`. Refüzler terminal `RUN_FAILED_ENGINE_ERROR` olur.

**Tripwire DARALTILDI, silinmedi** — `assert callers == []` → yetkili-çağıran allowlist'i, artı
`assert "shared_allocation_is_executable" in worker`. **Dokunulmaz iki assertion yeşil kaldı.**
**İmporter allowlist'i DEĞİŞMEDİ.** Worker'da `ItemIdentity`/`ItemBarStream` kurmak sayıldı ve
**üç dosyada beş assertion** kırmızıya çeviriyordu; o genişletme imzalı bir listeyi **ikinci,
imzasız** bir modülle büyütürdü (GH #731'in borcu) → genişletmek yerine **tasarım değişti**:
`participant.py::build_engine_participant` (`C4`'ün no-touch listesinde **değil**). Kaçınma
vacuous değil — import'lar geri konunca üç guard kırmızı verir, ve kalıcı bir assertion arka
kapıyı kapatır.

**NEGATİF KONTROLÜN BULDUĞU GERÇEK KUSUR:** checkpoint #4'ün ilerleme sözlüğü `item_runs`
okuyordu (yalnız bağımsız kol bağlar) → paylaşımlı bir run'da #4'te gözlenen iptal
`UnboundLocalError` fırlatıyordu. **Yedi test de yeşildi**, çünkü hepsi daha erken #3b'de iptal
oluyordu. Onarıldı (`replay_progress` dal öncesinde bağlanır) ve kalıcı bir testle pinlendi.
**On üç negatif kontrol koştu, on üçü de doğru assertion'da kırmızı.**

**İki-dünya kapısı güncellendi (ADIM 76'nın kendi ısmarladığı güncelleme).**
`test_the_worker_fold_never_consults_the_capability_flag` worker'da bayrağın **bulunmamasını**
şart koşuyordu; C4 onu sevk ediyor. Blanket liste geri konmadı — savunulan özellik daha güçlü
biçimde, bir **ayrıklık** olarak yazıldı (`ast`: bayrak TEK fonksiyondan çağrılır, fold eden
fonksiyon onu çağırmaz). **Bunu alt küme koşuları değil TAM SUITE yakaladı** — ders bu.

**Ölçülüp kapatılmayan:** `same_direction_stacking` şema varsayılanı (`allow_stacking`) adaptör
tarafından reddediliyor — standart fixture **üç** maddeden düşüyor, yani bugünkü varsayılanla
kayıtlı stratejilerin çoğu paylaşımlı saatte koşamaz. Bunu admission blocker'a çevirmek `C6`'dır
ve bir **ürün kararıdır** (`G11`/`G12`, imzasız). Giriş fill'i komisyonu hâlâ havuza
aynalanmıyor.

`PROJECT_HISTORY.md` §ADIM 92 · `docs/ADIM92_LANDED_KICKOFF.md`.
## Stage 93 — kabul borcu batch 16 (doc 02 Add Strategy, backend): dört kriter kapandı landed

**Ne indi.** Beş yeni integration case (`backend/tests/integration/test_strategy_integration.py`)
+ kabul defteri + üretilmiş artefakt. **`backend/src` altında sıfır satır**, migration yok,
OpenAPI değişmedi, `ENGINE_VERSION` değişmedi.

**Kapananlar: `AT-01` (c2) · `AT-11` (c2 + c3) · `AT-22` (c3) · `AT-23` (c3).** Doc 02 bugüne
kadar **hiç parti görmemişti** ve en büyük dokunulmamış sınıf-B havuzuydu. Dördünde de eksik
olan **mekanizma değil DİKİŞTİ**:

- **`AT-01.c2`** artık projeksiyon bayrağından değil, kompozisyona giren **tek kapıdan**
  ölçülüyor: kaydedilmemiş draft'ın kökünde **hiç `work_object_revision` yok**, `attach_mainboard_item`
  tam `(root_id, revision_id)` çifti ister (L5) → iki sahte-id dalı da reddedilir; Save + kendi
  mirror revizyonu **pozitif kontroldür**. Ödünç-revizyon dalı **sınıfla değil ekolanan alanla**
  pinlenir (aksi halde AOS-12 kind kontrolü testi yeşil tutardı).
- **`AT-11.c2`** saklanan `strategy_revision.payload` **ve** pinlenmiş
  `protection_stop_indicator` bağımlılık kenarını geri okur; kapalı ve açık kardeşler **aynı
  Save'de** gider, yani bölümü toptan düşürerek geçilemez. **`AT-11.c3`** kapalı stopu
  `gt 0`'ı ihlal eden bir değerle kaydeder (Save kabul eder), sonra draft'ın **kendi saklanmış**
  bölümünü yalnız `enabled` çevrilmiş hâlde geri gönderir → 422 yalnız saklanan değerden gelebilir.
- **`AT-22.c3`** Supervisor ve Admin'i **aynı yabancı draft** üzerinde sürer; Admin gerçek bir
  revizyon yazar ve kökün sahibi **değişmez** (grant = düzenleme, devralma değil).
- **`AT-23.c3`** **zaten revizyonu olan** bir kökü Clear'lar; revizyon, kenarları ve head
  pointer sağ kalır, `trash_entries` doğrudan sorgulanır (c2'nin dolaylı yarısı artık doğrudan).

**Yedi negatif kontrol, hepsi kırmızı ve hepsi doğru assertion'da**; her biri koşmadan önce
**yamasının uygulandığını** (tek eşleşme sayısı) assert etti. Biri özellikle öğretici:
aynı ürün kırılması hem payload hem bağımlılık-kenarı assertion'ını düşürdüğü için **ilk
kırmızı ikincisini gölgeliyordu** → kontrol, testin payload satırını da geçici olarak düşürüp
redin **kenar** assertion'ına inmesini ölçtü.

**Tavanlar İNDİ: `partial` 79 → 75, `debt_class.B` 47 → 43**; açık borç **86 → 82**
(A=1 · B=43 · C=6 · D=32). Clause `covered` 1039 → 1044, `uncovered` 91 → 87. Taban `3994725`,
freeze **taze bir `--report` koşusundan** (fark alınmadı).

**Doc 02'nin backend borcu bitti.** Kalan tek test-kapatılabilir satır **`AT-07`** ve o
**frontend** (bulgu değil). Diğer beşi sınıf D. **Bu partide yeni bulgu yok.**

**Yan iş:** `acceptance_semantic_traceability.md`'nin **doc 05 satırı bayattı** (ADIM 88'in
`TL-18` kapanışı bu üretilmiş belgeye yansımamıştı; dosya `--check` kapsamında değil) →
yeniden üretildi.

**Ortam:** bu container'da **Postgres 16 ikilileri kurulu**; yerel bir cluster kaldırılıp
integration suite'i **gerçekten koşuldu**. Son beş dalganın *"Postgres yok → otorite CI"*
sınırı artık zorunlu değil. **Dürüst sınır:** frontend kapıları koşulmadı (`node_modules` yok,
frontend'de sıfır satır); tam suite'in **geçen** sayısı ve coverage yüzdesi CI'ın otoritesinde.

**NUMARA + TAVAN — ikisi de indiği anda yeniden ölçüldü.** Bu kayıt `ADIM 89` / *"batch 15"*
yazıldı; **#803** `91` + *"batch 15"*'i, **#799** `92`'yi merge edilmiş adla aldı → **ADIM 93**
/ *"batch 16"*. **89'un boş olması onu güvenli yapmadı:** kapı canlı kickoff'un ağaçtaki en
yüksek numaralı `ADIM<n>` **dosyası** olmasını ister. Tavan da taşındı — dal **79/47**
dondurmuştu ve #803 indikten sonra main **zaten** oradaydı; birleşik ağaçta taze `--report`
**75/43** verdi. Eski freeze `--ratchet`'i **yeşil** bırakırdı (ölçülen < tavan kırmızı
vermez) ama tavanı **dört fazla** yapardı → sessiz gevşeme. **Rakamlar farktan türetilmedi,
yeniden ölçüldü.**

**Blocker sayısı DEĞİŞMEDİ (1 — yalnız A-08), BLOCKED.** Codemap güncellemesi gerekmedi.
`PROJECT_HISTORY.md` §ADIM 93 · `docs/ADIM93_LANDED_KICKOFF.md`.


## Stage 90 — kayıtsız inen #779'un ritüeli: G6/G7 kapı satırları tazelendi landed

**Ne indi.** Yalnız **defter**. Ürün kodu, migration, test ağacı, OpenAPI, imza kutusu ve issue
durumu: **sıfır değişiklik**. alembic head `0043_i08_registry_strategy_fks` · `ENGINE_VERSION`
değişmedi · `SHARED_ALLOCATION_STATUS` = `future_dev`.

**Bu bir GERİYE DÖNÜK kayıttır.** PR **#779** (`a5bc27f`) 2026-08-19'da main'e indi ve
`PROJECT_HISTORY.md`'de yalnız ADIM 87'nin zincir notunda anıldı (`grep '#779'` → 1 satır, o da
yalnız *"kesildiği yer"* olarak). Kendi kaydı, handoff satırı ve kickoff'u **yoktu** → kapanış
ritüelinin 1–5. maddeleri o slice için **hiç koşmadı**. Desen tanınmıştır: #728/#729 = ADIM
69/70, #759 = ADIM 82, #765/#766 = ADIM 86.

**Kaydedilen slice ne yaptı.** Tek plan belgesi, **+37 / −7**. `final_closure_ordered_plan`
§2'nin kapı sicili **kendi içinde çelişiyordu**: sayım tablosu `G6`/`G7`'yi *"resolved (Karar 2,
signed 2026-08-14)"* sayarken yirmi satır yukarıdaki `G6` satırı hâlâ *"UNSIGNED, all boxes
`[ ]`, GH #558 OPEN"* diyordu. **Çelişen taraf sicilin kendisiydi — yani o belgenin tek
işlevi.** Satırlar `§Karar 2 ▸ İMZA SATIRI` ölçülerek düzeltildi (`[x] A1+A2`, `[x] evet`,
`[x] yalnız türetilebilir ikisi`, alimirbagirzade / 2026-08-14); eski metin `Was "…"` deseniyle
**yerinde korundu** (G4/G12/G15 satırlarının zaten kullandığı biçim).

**ASIL DEĞER YAN ÖLÇÜMLERDE — ikisi de kaydın kendisinden daha çok iş gördü.**

**(a) Altı `decisions:NNN` referansının altısı da bayattı** — hiçbiri iddia ettiği yeri
göstermiyordu (ör. `decisions:467-477` artık öneri paragrafının ortası, imza bloğu değil). Hepsi
**bölüm adına** çevrildi (`CLAUDE.md` §Conventions: *satır no değil sembol yaz*).
**Tuzak, ileride grep'leyecek olan için:** bugün `grep -c 'decisions:[0-9]'` → **2** döner ve bu
**eksik süpürme DEĞİLDİR** — iki eşleşme de `Was "…"` **alıntısının içinde**, canlı işaretçi
**0**. Alıntıyı "artık" sanıp temizlemek düzeltmenin kanıtını siler.

**(b) Üç issue durumu bayattı, ama İKİSİ KAPIYI AÇMAZ.** Tablo #558/#559/#544'ü `OPEN`
yazıyordu; **üçü de kapalı**. Ama kapanış tek başına hiçbir şey kanıtlamaz — tablonun **kendi
G1 kuralı** *issue CLOSED ≠ çözüldü* der ve burada **üç kez farklı** sonuç verdi:

| issue | kapanış | kayıtlı karar | kapı |
|---|---|---|---|
| **#558** (G6/G7) | 2026-08-17 `completed` | **EVET** — kapanış yorumu üç karar sorusunu da yazılı cevaplıyor, imza ayrıca `§Karar 2`'de **bağımsız** duruyor | **çözüldü** |
| **#559** (G8) | 2026-08-18 `completed` | **HAYIR** — sıfır yorum, `closed_by_pull_requests` boş, `§Karar 3` imza bloğu **tamamen boş** | **AÇIK kalır** |
| **#544** (G14) | 2026-08-18 `completed` | **HAYIR** — sıfır yorum, closing PR yok, karar bölümü cevapsız | **AÇIK kalır** |

`G14` bu ayrımın en kolay yanlış okunacağı yeridir, çünkü *"Evidence written where"* sütunu
**issue'nun kendisini** gösterir: **G5** gerçekten gövdesinde karara bağlanmıştı, **G14** ise
kapatıldı ve **boş bırakıldı**. Kapalı bir issue'yu imza saymak **on bir açık kapıyı dokuza**
indirirdi; **indirilmedi.**

**DERS: bir kapıyı düşürmeden önce ÜÇÜNÜ birden ölç** — issue durumu, issue'da **yazılı** karar,
`decisions` **imza kutusu**. Ayrıştıklarında otorite **imza kutusudur**.

**DERS 2 — `cancelled` ≠ `failure`, ve kökü artık biliniyor.** #779'un dalında A11Y işi
`Install Playwright browsers` içinde **38 dk 50 sn** asılıp `cancelled` oldu (axe adımı
**skipped** → hiçbir test gövdesi koşmadı); rerun **3 dk 08 sn**'de yeşil. Kök **#795**'te
ölçüldü: `azure.archive.ubuntu.com` aynası düştü ve **GitHub bir timeout'u `cancelled`
raporlar**. **Ayırt edici:** aynı attempt'te **üç kardeş işin** aynı adımı **yeşildi** (1–3 dk)
→ genel kesinti **değil**, yani *"install yavaş, tavanı büyüt"* yanlış düzeltmeydi. Sınıf artık
`scripts/ci-install-playwright-chromium.sh` ile korunuyor → **yeni E2E işinde
`npx playwright install` YAZMA.**

**PR gövdesi bir noktada düzeltildi.** #779'un gövdesi #544 için *"the body still ends on 'What
must be decided'"* diyor; gövde o bölümü **içerir** ama onunla **bitmez**. Sonuç değişmez (iki
karar sorusu cevapsız, kapı açık), iddia *"karar bölümü cevapsız"* biçiminde tutuldu.

**NUMARA — ve kuralın İKİ YARISI.** Kayıt `90`'da kaldı: #797 → 88, #803 → **91**, #799 → **92**
(kendisi de 89'dan taşındı) indi ve **hiçbiri `ADIM90` dosya yolunu eklemedi** → çakışma yok,
**yeniden atanmadı**. Kayıt sırası **87 → 88 → 91 → 92 → 90**; ADIM 69/70 *"numaralar merge
sırasının tersi"* emsalini zaten kaydetmişti. **`89` kalıcı bir BOŞLUKTUR.** Bedeli kickoff'ta:
`_check_live_kickoff_is_newest` canlı işareti **ağaçtaki en yüksek numaralı** `ADIM<n>`
**dosyasında** ister → bu slice'ın kickoff'u **`historical` DOĞDU** (ADIM 82 emsali).
***"Numaralar yeniden atanmaz"* KAYDIN numarasını korur; kickoff'un canlılığı AYRI bir sorudur.**

**Blocker sayısı DEĞİŞMEDİ (1 — yalnız A-08), BLOCKED, açık kapı 11.** Codemap güncellemesi
gerekmedi. Ürün kodunda sıfır satır olduğu için **suite koşulmadı**; doğrulama
`generate_repository_facts.py --check`. `PROJECT_HISTORY.md` §ADIM 90 ·
`docs/ADIM90_LANDED_KICKOFF.md`.

## Stage 94 — kabul borcu batch 17 (doc 01 Mainboard, backend): MB-01 + MB-27 kapandı landed

**Ne indi.** İki yeni integration case (`backend/tests/integration/test_readiness_persistence.py`)
+ kabul defteri + üretilmiş artefakt. **`backend/src` altında sıfır satır**, migration yok,
OpenAPI değişmedi.

**Kapananlar: `MB-01` (c4) · `MB-27` (c4)** — ikisi de doc 01'in son açık backend clause'uydu.

- **`MB-01.c4`**: kriterin adlandırdığı dört yüzeyden yalnız Ready Check hiç anonim aktörle
  sürülmemişti (satırın kendi notu *"muhtemelen reddederdi"* diyordu). Artık sürülüyor:
  `UnauthenticatedError` + **hiç rapor satırı yok** + authenticated çağrı pozitif kontrol.
- **`MB-27.c4`**: iki adımlı çıkarım yerine iki bağımsız gözlem — **etkin** durum `stale`'e
  düşer, **saklanan** durum kıpırdamaz; ve yeniden koşu **`COMPOSITION_EMPTY`** raporlar.

**Beş negatif kontrol; üçüncüsü bu partinin dersi.** İlk ikisi `pytest.raises` satırında
kırmızı verip rapor-sayısı assertion'ını **gölgeliyordu**; üçüncü kontrol auth kapısını
insert'in altına taşıdı ve **yeşil geçti** → assertion'ın **totolojik** olduğu ortaya çıktı
(test saymadan önce `session.rollback()` yapıyordu). Rollback silindi, kontrol yeniden koştu:
`assert 1 == 0`. **Bir yan etkinin yokluğunu iddia eden assertion'ın önünde onu geri alan
hiçbir şey olamaz.** Ayrıca **kontrol harness'inin kendisi** onarıldı: çok dosyalı bir
kontrolde sonraki bir tekillik hatası öncekini geri almadan aborte ediyor ve ağacı kirli
bırakıyordu → geri yazma artık `finally`'de.

**ON BİRİNCİ BULGU — `MB-22.c4` (kapatılmadı, ölçüldü).** *"Restore'dan sonra rapor
kullanılamaz"* iddiasının **tersi** sevk edilmiş: restore aynı `(root, revision)` çiftini geri
koyar, fingerprint **orijinaline birebir döner** (`02edaff5…` → `9e72b8a1…` → `02edaff5…`) ve
silme öncesi rapor yeniden `ready`/`current` okunur. Sınıf D şekli; **yeniden
sınıflandırılmadı** (D tavanını yükseltirdi).

**Tavanlar İNDİ: `partial` 75 → 73, `debt_class.B` 43 → 41**; açık borç **82 → 80**
(A=1 · B=41 · C=6 · D=32). Clause `covered` 1044 → 1046, `uncovered` 87 → 85. Taban `d47c5ba`.

**Ortam tuzağı (birinci elden):** container slice ortasında yeniden başladı, Postgres düştü ve
ilk koşu **`ss` = iki SKIPPED** ile **exit 0** verdi. Skip'li yeşil exit code kanıt değildir.

**NUMARA/ETİKET:** main'in son kaydı ADIM 93 / batch 16; **#806 açık ve *"batch 17"* diyor**
(doc 10 backend) → bu slice bilerek **başka belge** seçti, ama #806 önce inerse bu kayıt
**batch 18** olur. Numara açık PR'ların eklediği dosya yollarından ölçüldü → 94 boştu.

**Blocker sayısı DEĞİŞMEDİ (1 — yalnız A-08), BLOCKED.** Codemap güncellemesi gerekmedi.
`PROJECT_HISTORY.md` §ADIM 94 · `docs/ADIM94_LANDED_KICKOFF.md`.


## Stage 95 — üretilmiş kabul artefaktlarının drift kapısı (`--check-generated`) landed

**ÜRÜN KODU DEĞİŞMEDİ** (`backend/src`'te sıfır satır) · migration yok · OpenAPI değişmedi ·
`ENGINE_VERSION` değişmedi · **tavanlar OYNAMADI** (73 partial / 7 uncovered · A1 B41 C6 D32).
**Blocker sayısı DEĞİŞMEDİ (1 — yalnız A-08), BLOCKED.**

`acceptance_semantic_scan.py` iki checked-in artefakt üretiyor. **İddia daraltıldı:** defter
**zaten** kapılıydı (`test_the_debt_ledger_is_not_stale`); kapısız olan **rapordu** — ve
sürüklenen de tam olarak o oldu: **ADIM 60'tan beri YEDİ parti** (`234/126` yazarken ölçülen
`276/84`), CI hep yeşil.
Yeni `--check-generated` bunu bloklayıcı yapar; `ci.yml:93` artık
`--report --check-generated --ratchet` koşar (**yeni job değil, mevcut adıma bayrak**).

Kapı **eksik dosyayı taze saymaz** (`MISSING`), suçlamayı **dosya başına** ayrıştırır ve hata
mesajında **yeniden üretme komutunu** verir. Yazıcı ile kapı **tek renderer'ı paylaşır** —
ayrışsalardı kapı tatmin edilemez olurdu (kaynak düzeyi testle pinli).

**Dört negatif kontrol + testin kendisinin üç negatif kontrolü, yedisi de kırmızı.** En
öğreticisi: rapor `d012a63`'teki ADIM 60 sürümüne geri konduğunda kapı kırmızı verdi — yani o
yedi partilik sürüklenmeyi **gerçekten yakalardı**.

**Ders:** bir kapı ölçtüğü şeyin tamamını ölçtüğünü iddia etmez. `--ratchet` **borcun
tavanını** korur, üretilmiş belgenin doğruluğunu değil; ayrı sorular, ayrı kapılar.

**Asıl ders (tam suite kazandırdı):** odaklı testler yeşilken tam suite
`test_the_ratchet_is_wired_into_ci`'yi kırdı — CI satırının **birebir literalini** pinliyordu.
Test kendi konusuna göre yeniden yazıldı (literal değil **bayrak** assert'i), ve o dosyayı
okumak defterin **zaten kapılı** olduğunu ortaya çıkarıp bu kaydın ilk yanlış iddiasını
düzeltti. **Odaklı koşu yalnız senin bildiğin kapıları koşar.**

**NUMARA:** `ADIM 92` yazıldı, kapanış sırasında 92 **ve** 93 main'e indi → **94**; rebase
sekiz belge çakışması verdiği için dal main'e sıfırlanıp yalnız dört kod dosyası yeniden
uygulandı, defter belgeleri yeni tabana karşı yeniden yazıldı.

`PROJECT_HISTORY.md` §ADIM 94 · `docs/ADIM95_LANDED_KICKOFF.md`.
## Stage 97 — kabul borcu batch 18 (doc 10 backend): `RF-07` + `RF-12` kapandı landed

**Ne indi.** Yalnız **test + defter**. Ürün kodu **değişmedi** (`backend/src` ve `frontend/src`
altında sıfır satır), migration **yok**, OpenAPI **değişmedi**, `ENGINE_VERSION` **değişmedi**.
Belge + yüzey: **doc 10 (Rationale Families), backend**.

**Kapananlar.** `RF-07` (`.c2` — reddedilen create hiçbir kök/revizyon bırakmıyor) ·
`RF-12` (`.c3` — family'siz kompozisyon `request_backtest_run`'da reddediliyor ve
run/manifest/job/result yazılmıyor). İkisinde de son açık clause'du → ikisi **covered**,
ikisinin **`debt_class` KALDIRILDI**.

**`RF-07.c2` — "raise ediyor" ≠ "YAZMADAN raise ediyor".** Mevcut test istisnayı assert edip
duruyor; guard'ın insert'in üstünde mi altında mı olduğunu ayırt edemiyor. **Refüzden sonra
`rollback` YAPILMIYOR** — bu depoda ilk kez yazılan kural: rollback post-insert bir guard'ın
yazdığını **da** atar ve test vacuous geçer; `flush()` + `expire_all()` ile veritabanından okunur.

**`RF-12.c3`.** Harness `_strategy_payload(rationale_family_id: str | None = "rf_1")` aldı;
**`None` anahtarı tamamen ATAR**, `null` yazmaz. Varsayılan mevcut ~30 çağıranı bayt bayt aynı
bırakır ve bu **ölçüldü**.

**ÜÇ negatif kontrol**, her birinde hangi assertion'ın kırmızı olduğu okundu. **NK-2 harness
değişikliği yüzünden ZORUNLU** — yeni kural: *paylaşılan bir harness'a parametre eklediysen,
red'in senin değişikliğine atfedilemeyeceğini ayrı bir kontrolle göster.*

**YENİ BULGU (on birinci) — `RF-08.c2`.** 409 hiçbir `remediation` taşımıyor; `TL-16.c4`'ten
farkı, o zarfı genişletmeyi ister, bu **hiçbir yeni şey istemez** (aynı dosyada yirmi sınıf
`remediation` bildiriyor) → **tek satırlık** düzeltme. Sevk **edilmedi**, **yeniden
sınıflandırılmadı**.

**İKİNCİ BULGU — #808 KAYITSIZ İNDİ.** `ADIM 94` (batch 17, doc 01 Mainboard) main'e indi ama
**`docs/PROJECT_HISTORY.md`'ye hiç dokunmadı** (`grep -c 'MB-01'` → 0) → ritüelin 3. maddesi
koşmadı. Bu slice o kaydı **uydurmadı**; sahibinin yazması gerekir. Hiçbir kapı yakalamıyor —
`check_classification` kickoff dosyasına bakar, kaydın varlığına değil.

**Sayılar (ölçüldü, ÜÇ farklı tabanda).** Tavanlar İNDİ: `partial` **73 → 71**, `debt_class.B`
**41 → 39**; açık borç **80 → 78** (A=1 · B=39 · C=6 · D=32). Clause `covered` **1046 → 1048**.
**Doc 10'un BACKEND borcu bitti**; kalan `RF-18` **frontend**.

**Dürüst sınır.** Postgres ayakta + migrate + **izole DB** → iki case ve üç negatif kontrol
gerçekten koştu (#804'ün ve #805'in dosyaları da yanında yeşil). **Tam suite ve coverage CI'a
bırakıldı** — üç yerel deneme ortam yüzünden geçersizdi; bir önceki head'de CI `Backend`
yeşildi, bu dal için yerel sayı **iddia edilmiyor**. Frontend'e sıfır satır.

**NUMARA — üç kez taşındı.** `ADIM 93` → `94` → **`95`**. #804 `ADIM 93`'ü, **#808 HEM `ADIM 94`
HEM `batch 17`**'yi aldı. **DERS: iki numara bağımsız taşınABİLİR demek bağımsız taşınIR demek
değildir** — ayrı ayrı ölç. Bu kayıt **batch 18**.

**Blocker sayısı DEĞİŞMEDİ (1 — yalnız A-08), BLOCKED.** `PROJECT_HISTORY.md` §ADIM 97 ·
`docs/ADIM97_LANDED_KICKOFF.md`.

## Stage 98 — kabul borcu batch 19 (doc 14 Backtest Ready Check, backend): RC-10 + RC-17 kapandı landed

**Ne indi.** İki yeni integration case (`backend/tests/integration/test_readiness_persistence.py`)
+ bir yeni dosya (`backend/tests/integration/test_readiness_denial_envelope.py`) + kabul defteri
+ üretilmiş artefakt. **`backend/src` altında sıfır satır**, migration yok, OpenAPI değişmedi.

**Kapananlar: `RC-10` (c2) · `RC-17` (c2)** — ikisi de kendi kriterinin **son açık clause'uydu**,
ikisinin de `debt_class`'ı KALDIRILDI. **Doc 14'ün backend borcu bitti**; kalan tek satır
`RC-09.c3` ve o **frontend**.

- **`RC-10.c2`** (*yeni bir katalog revizyonu tek başına raporu stale etmez*): suite'te bunun
  karşılığı yalnız `is_stale(a, a) is False` unit gerçeğiydi — o gerçek, current fingerprint'in
  **hangi revizyon id'sinden** kurulduğu hakkında hiçbir şey söylemez. Clause tek davranışı **iki
  katalog** üzerinde adlandırıyor, iki kez sürüldü: (1) iş nesnesi kataloğu — revizyon append kök
  head'ini ilerletir, item pinini korur (AT#5); (2) market-data kataloğu — `md_rev_2` APPROVED
  head olur, payload hâlâ `md_rev_1`'i adlandırır (pin **saklanan payload'dan** geri okunur).
  Her iki case de ön koşullarını **assert eder** (successor indi mi, head oynadı mı, pin oynamadı
  mı) — content-hash idempotency dalı sessizce no-op yaparsa test totolojik olurdu.
- **`RC-17.c2`** (*reddin gövdesi kompozisyon ayrıntısı taşımaz*): üç mevcut RC-17 testi de
  **komut sınırında** durur, orada gövde henüz yoktur. Yeni case rotayı ASGI app üzerinden gerçek
  session'la sürer ve **serileştirilmiş zarfı** tarar. Vacuity iki uçtan kapatıldı: kompozisyonun
  sızdıracak ayrıntısı gerçekten var (pinli revizyon, onaylı paket, dataset, **bilerek eklenmiş
  duplicate item** → item-scoped blocker), ve **aynı rota sahibine çağrıldığında o kimliklerin
  üçünü birebir yayımlar** (pozitif kontrol).

**Yedi negatif kontrol — ve bu partinin dersi: BİR KONTROL YANLIŞ YERDE KIRMIZI VEREBİLİR.**
İlk market-axis kontrolü (market head'ini fingerprint'in **kendisine** katmak) raporu
**doğduğu anda** stale ediyordu → yeni case **`before` ÖN KOŞULUNDA** kırmızı verdi ve yanında
**ilgisiz, önceden var olan bir testi** de düşürdü; kırmızı **clause'a atfedilemezdi** →
kontrol **reddedildi**. Yerine okuma modelini *"katalog successor'ı var = stale"* yapan kontrol
kuruldu: yalnız market case'i, **hedef assertion'ında** kırmızı, fingerprint el değmemiş — bu
yüzden **iki assertion da taşıyıcı**. İki kontrol de yalnız **gölge kaldırmak** için var
(fingerprint satırları önce kırmızı verip `is_current`'ı gölgeliyor). RC-17 tarafında üç sızıntı
vektörünün üçü de **ayrı** bir assertion'ı düşürür; `message` içindeki düz metne konan sızıntıyı
**hiçbir key lookup bulamaz** → kontrol bir **substring taraması** olmak zorunda.
**Yedi kontrolün hepsinde önceden var olan suite YEŞİL kaldı** — ikisinin de gerçek boşluk
olduğunun kanıtı.

**Tavanlar İNDİ: `partial` 71 → 69, `debt_class.B` 39 → 37**; açık borç **78 → 76**
(A=1 · B=37 · C=6 · D=32). Clause `covered` 1048 → 1050, `uncovered` 83 → 82. Doc 14
**17 covered / 1 partial**. Taban `b7e66ad`.

**Ortam (birinci elden):** container **çıplak** başladı — `backend/.venv` yok, Postgres cluster
yok. İkisi de bu slice içinde kuruldu; üç yeni case ve yedi kontrol **gerçekten koştu**
(dört dosya, **77 nokta / exit 0**, skip yok). **`alembic upgrade head` `LC_ALL=en_US.UTF-8` ile
`UnicodeDecodeError` verdi** bu imajda — `LC_ALL=C.UTF-8 PYTHONUTF8=1` ile geçti.
**YAML tuzağı:** RC-10'un notu **düz skalerdi** ve eklenen metindeki bir `: ` `ScannerError`
verdi → not tek tırnaklı skalere çevrildi.

**Dürüst sınır:** frontend kapıları koşulmadı (frontend'de sıfır satır, `node_modules` yok),
E2E/A11Y koşulamadı → oralara assertion **yazılmadı**; tam backend suite sonuna kadar koşmadı
(yalnız `--collect-only`, 353 dosya / exit 0) → **geçen sayı ve coverage CI'ın otoritesinde**.

**NUMARA/ETİKET:** main'in son kaydı ADIM 94 / batch 18 metni main'de zaten var; **açık iki
PR'ın (#806, #809) İKİSİ de `docs/ADIM95_LANDED_KICKOFF.md` ekliyor** → 95 iki kez talep
edilmiş, bu kayıt **ADIM 98 / batch 19**. Numara başlıktan değil **dosya yolundan** ölçüldü.

**Blocker sayısı DEĞİŞMEDİ (1 — yalnız A-08), BLOCKED.** Codemap güncellemesi gerekmedi
(yeni endpoint / tablo / sayfa / job yok).
`PROJECT_HISTORY.md` §ADIM 98 · `docs/ADIM98_LANDED_KICKOFF.md`.


## Stage 99 — kabul borcu batch 20 (doc 10 FRONTEND): `RF-18` kapandı landed

**Ne indi.** Yalnız **test + defter**. Ürün kodu **değişmedi**, migration **yok**, OpenAPI
**değişmedi**, `ENGINE_VERSION` **değişmedi**. Belge + yüzey: **doc 10 (Rationale Families),
frontend** — batch 18'in (doc 10 backend) tümleyeni.

**Kapanan.** `RF-18` (`.c1` — sahnelenmiş yeniden atamalar yalnız istemci durumunda yaşar,
remount'ta düşer). Son açık clause'du → **covered**, **`debt_class` KALDIRILDI**.

**Neden açıktı.** Mevcut staging testi *stage → SAVE* yönünü sürüyor ve staging kalıcı olsa da
**yeşil kalır**. Yeni case sahne kurar, **hiçbir yazma gitmediğini** (non-GET istek kümesi boş)
assert eder, sonra **unmount + remount** edip düşüşü üç yüzeyde birden okur.

**Paylaşımlı `QueryClient` TAŞIYICIDIR ve bu ÖLÇÜLDÜ.** Staging query cache'e park edilmiş bir
dünyada **taze istemcili** sürüm 9/9 geçiyor, paylaşımlı sürüm kırmızı → taze istemci bir
**yanlış-negatif harness** olurdu.

**ÜÇ negatif kontrol.** (1) modül düzeyi store → yalnız yeni test kırmızı, **sekiz mevcut case
YEŞİL** (clause'un açık olduğunun kanıtı) · (2) query cache → aynı assertion kırmızı ·
(3) **atıf kontrolü** (ADIM 97 kuralı): `renderPage` opsiyonel `client` parametresi aldı, bu yüzden
(1) yeni case harness'ı **tamamen atlayarak** yeniden koşuldu → yine kırmızı.

**Sayılar — TAVAN İKİ KEZ ÖLÇÜLDÜ.** Dal önce `b7e66ad`'e karşı **71 → 70 / 39 → 38** ölçtü;
**#811 (ADIM 98) aynı baseline'a iki kriter daha yazarak indi** → rebase + `--ratchet` **yeniden**:
`partial` **69 → 68**, `debt_class.B` **37 → 36**; açık borç **75** (A=1 · B=36 · C=6 · D=32).
İki freeze **çıkarılmadı**. **Doc 10'da testin kapatabileceği satır KALMADI** (kalan: `RF-08`
kayıtlı bulgu + `RF-04`/`RF-13` sınıf D).

**Dürüst sınır.** Tam frontend suite yerelde koştu (**72 dosya / 736 passed**, coverage yeşil,
lint + typecheck temiz). **Backend'e sıfır satır → backend kapıları koşulmadı**, otorite CI.

**NUMARA.** #811 **ADIM 98 / batch 19** olarak indi (doc 14, `RC-10` + `RC-17`) → bu kayıt
**99 / batch 20**; `96` boşluk değil, #811'in taşıdığı numaradır. İkinci inen taraf bu daldı, o
yüzden **rebase edip tavanı yeniden ölçen** de bu dal oldu.

**Blocker sayısı DEĞİŞMEDİ (1 — yalnız A-08), BLOCKED.** `PROJECT_HISTORY.md` §ADIM 99 ·
`docs/ADIM99_LANDED_KICKOFF.md`.
## Stage 100 — kabul borcu batch 21 (doc 22 Future Dev, backend): FD-04 + FD-05 kapandı landed

**Ne indi.** İki yeni integration case (`backend/tests/integration/test_future_dev.py`) + kabul
defteri + üretilmiş artefaktlar. **`backend/src` altında sıfır satır**, migration yok, OpenAPI
değişmedi.

**Kapananlar: `FD-04` (c4) · `FD-05` (c4)** — ikisi de kendi kriterinin **son açık clause'uydu**,
ikisinin de `debt_class`'ı KALDIRILDI. Doc 22 artık **6 covered / 3 partial / 6
deliberate_future_dev** (4 → 6 covered, 5 → 3 partial).

- **Ortak şekil:** iki clause da *"referans edilen Backtest Result'a dokunulmadı"* der ve
  **davranış zaten sevk edilmiş** (`query_view_dataset` ile `create_analysis_artifact`'in
  gövdelerinde herhangi bir result tablosuna **tek bir yazma yok**). Boşluk şuydu: doc 22'nin
  FD-04/FD-05 testlerinin **hepsi** komuta **literal** bir ref veriyordu — `"result_abc123"` —
  ve o dize **hiçbir satırı adlandırmıyor**, yani iddia doğruydu çünkü **dokunulacak bir şey
  yoktu** (ADIM 91'in "iddia yanlış dünyada ölçülmüştü" şekli). Yeni case'ler **yoğun** bir
  result tohumlar (3 kanonik metrik — biri bilerek `value=None`/`no_drawdown` —, 2 trade-ledger
  satırı, pinlenmiş `result_manifest_snapshot`), **o result'ın kendi id'sini** ref olarak geçirir
  ve her şeyi **Postgres'ten** geri okur.
- **Üç taşıyıcı, üçü de ölçüldü:** yoğunluk muhafızı (boş result'ta "değişmedi" **bedavadır**) ·
  geri okumadan önce **`session.expire_all()`** — fixture `expire_on_commit=False` kurar, yoksa
  karşılaştırma veritabanına değil **identity map'e** karşı yapılır (ADIM 94 kuralının okuma
  yoluna uygulanmış hâli) · işlemin **gerçekten indiği** (`ViewDataset`/`AnalysisArtifact`
  satırı var **ve** gerçek result id'sini taşıyor), yoksa "hiçbir şey kıpırdamadı" hiçbir şey
  yapmamış bir çağrı için de doğrudur.

**Beş negatif kontrol, beşi de hedef assertion'ında kırmızı:** NC-1 `row_version` geri-yazması →
`result_row` · NC-2 pinlenmiş manifest yeniden yazımı → `manifest_snapshot` · NC-3 metrik ezme →
`metrics` · NC-4 ledger satırı **EKLEME** → `ledger` · NC-5 manifest yeniden yazımı (artifact
yolundan) → `manifest_snapshot`. **Beşinde de tam olarak bir test düştü (24 yeşil + 1 kırmızı) ve
önceden var olan 23 test YEŞİL kaldı** — bu, boşluğun iddiası değil **ölçümü**. **NC-3/NC-4 çifti
dersin kendisi:** satır **demetlerini** karşılaştırmak bir **ezmeyi**, tam sıralı **listeleri**
karşılaştırmak bir **eklemeyi** yakalar; hiçbiri diğerinin kusurunu göremez. `FD-05` case'inin
son `result_row` assertion'ı üç assertion tarafından **gölgelenir** → **kendi ekseni sayılmadı**,
o iddia `FD-04`'ün NC-1'i ile bağımsız ölçülüyor; defter notu bunu açıkça yazar.

**Tavanlar İNDİ: `partial` 68 → 66, `debt_class.B` 36 → 34**; açık borç **75 → 73**
(A=1 · B=34 · C=6 · D=32). Taban `bc25d22`. **Tavan TAŞINMADI** — dalın rebase öncesi freeze'i
67/35 taşıyordu ve arada inen #812 başka bir kriteri (`RF-18`) kapatmıştı; merged ağaçta taze
`--report` ile **yeniden ölçüldü**.

**Ortam (birinci elden):** container **çıplak** başladı — `backend/.venv` yok, Postgres cluster
yok; ikisi de bu slice içinde kuruldu ve iki case ile beş kontrol **gerçekten koştu**
(`test_future_dev.py` **23 → 25 passed**, skip yok). `alembic upgrade head`
**`LC_ALL=C.UTF-8 PYTHONUTF8=1`** ile koşuldu (`en_US.UTF-8` bu imajda `UnicodeDecodeError`).
**Yeni tuzak:** bir kontrol koşusu Bash aracının zaman aşımıyla **SIGTERM** aldı, `finally`
**koşmadı** ve ağaç yamalı kaldı → **her kontrol turundan sonra `git status`'e bak**.

**Dürüst sınır:** frontend kapıları koşulmadı (frontend'de sıfır satır, `node_modules` yok) →
otorite CI; geçen sayı ve coverage yüzdesi yine **CI'ın otoritesinde**.

**NUMARA/ETİKET:** dal `2b41cf8`'den kesildi ve o an açık PR listesi **boştu** → `ADIM 99` /
`batch 20` yazıldı. Bu PR açıkken **#812 indi ve İKİSİNİ de aldı** → bu kayıt **ADIM 100 /
batch 21**, kickoff dosyası dahil yeniden adlandırıldı. **Boş bir açık-PR listesi bir garanti
değil, bir anlık görüntüdür** — dal PR'ını açtıktan sonra da main ilerler. Dal `origin/main`
üzerine **rebase** edildi (*"Update branch"* düğmesi kullanılmadı); on çakışmanın hepsi **iki
tarafı da koruyarak** çözüldü, `## ADIM` sayısı 92 → **93**.

**Blocker sayısı DEĞİŞMEDİ (1 — yalnız A-08), BLOCKED.** Codemap güncellemesi gerekmedi
(yeni endpoint / tablo / sayfa / job yok).
`PROJECT_HISTORY.md` §ADIM 100 · `docs/ADIM100_LANDED_KICKOFF.md`.



## Stage 101 — kabul borcu batch 22 (doc 21 User Manual, backend): UM-08 + UM-13 kapandı landed

**Ne indi.** İki yeni integration case (`backend/tests/integration/test_user_manual.py`) + kabul
defteri + üretilmiş artefaktlar. **`backend/src` altında sıfır satır**, migration yok, OpenAPI
değişmedi.

**Kapananlar: `UM-08` (c5) · `UM-13` (c3)** — ikisi de kendi kriterinin **son açık clause'uydu**,
ikisinin de `debt_class`'ı KALDIRILDI. Doc 21 artık **15 covered / 3 partial** (13 → 15, 5 → 3).

- **`UM-08.c5` — olay ZATEN yazılıyordu, hiç kimse OKUMUYORDU.** `commands/manual.py:625-646`
  soft delete'te üç düzlemi birden yazar: `ManualPublicationEvent`
  (`event_type="manual_document_soft_deleted"`), `AuditEvent` + `OutboxEvent`
  (`event_kind="manual.document_soft_deleted"`). Suite bu şekli **yalnız purge için** pinlemişti
  (`test_manual_purge_writes_event_and_removes_every_revision`) → **tüm iz komuttan silinebilir ve
  27 mevcut testin 27'si de yeşil kalırdı** (ölçüldü: NC-1). Yeni case üç düzlemi de assert eder
  **artı üçünün göremediği dördüncü bir eksen**: iz **EKLENİYOR**, yeniden yazılmıyor.
  Belge silinmeden önce **revize edilir**, yoksa `revision_id` *"delete anındaki head"* ile
  *"ilk revizyon"*u ayırt edemez.
- **`UM-13.c3` — mekanizma vardı, ÇEKİŞME ALTINDA hiç sürülmemişti.**
  `repositories/manual.py::lock_stream` (`pg_advisory_xact_lock`, `MANUAL_STREAM_LOCK_KEY`) +
  `uq_manual_stream_position` + `uq_manual_event_stream_version`; ama dosyadaki her test **tek
  session'ı sırayla** sürüyor, yani ne kilit ne de unique kısıt bir yarışa hiç hakemlik etmemişti.
  Yeni case **iki bağımsız engine ve bağlantı** üzerinde iki `create_manual_document` koşar,
  ikisini bir **`asyncio.Barrier`** ile birlikte salar. **Bariyer komuttan ÖNCE salınır** —
  komutun İÇİNDE salmak **kilitlenir**, çünkü birinci görev diğerinin beklediği advisory kilidi
  tutuyor olur.

**Beş negatif kontrol, beşi de hedef assertion'ında kırmızı** (her biri yamanın uygulandığını
eşleşme sayısıyla assert etti, ağacı `finally`'de geri yazdı, ve her turdan sonra `git status`
okundu): NC-1 delete hiç publication event yazmaz → **assertion 1** · NC-2 audit satırı **publish
kind'ıyla** yazılır → **assertion 2** · NC-3 outbox payload'ı `trash_entry_id`'yi düşürür →
**assertion 3** · NC-4 delete, kendi olayını eklemeden önce o belgenin **önceki olaylarını siler**
→ **YALNIZ assertion 4** · NC-5 `_publish_new_document`'tan `lock_stream` kaldırılır → eşzamanlılık
case'i, kaybedende `uq_manual_stream_position` ihlaliyle. **Beşinde de tam olarak bir test düştü ve
önceden var olan 27 case YEŞİL kaldı.**

- **NC-4 bu partinin asıl dersi: GÖLGE KALDIRILDI, kaydedilmedi.** İlk üç assertion dördüncüyü
  gölgeliyordu (çoğu kusur zaten (1)'de kırmızı verir). NC-4 altında **ilk üçü geçer** ve yalnız
  sıralı iz karşılaştırması düşer → dördüncü eksen **kendi başına ölçüldü**.
- **NC-5 aynı zamanda UM-13'ün VACUITY KANITIDIR:** iki **sıralı** append kilit kaldırılınca
  çakışmazdı; çakışmanın kendisi iki çağıranın **gerçekten örtüştüğünün** delilidir. Determinizm
  **iki yönde de** ölçüldü — kilitle **8/8 yeşil**, kilitsiz **5/5 kırmızı**.

**Tavanlar İNDİ: `partial` 66 → 64, `debt_class.B` 34 → 32**; açık borç **73 → 71**
(A=1 · B=32 · C=6 · D=32); clause `covered` 1053 → 1055. Taban `7f4d927`.

**Doc 21'de kalan üç `partial` satırın hiçbiri backend test borcu değil:** `UM-04` (c4, sınıf D —
publish sonrası reader'ın yeni anchor'a kaydırması) · `UM-12` (c3, sınıf D) · **`UM-15` (c3,
sınıf B ama FRONTEND** — 409 `MANUAL_STREAM_CONFLICT` sonrası istemcinin stream'i yeniden
hidratlaması; `cd frontend && npm ci` gerektirir). **Doc 21'in BACKEND borcu bitti.**

**Ortam (birinci elden):** container **çıplak** başladı — `backend/.venv` yok, Postgres cluster
yok; ikisi de bu slice içinde kuruldu ve iki case ile beş kontrol **gerçekten koştu**
(`test_user_manual.py` **27 → 29 passed**, skip yok). `alembic upgrade head`
**`LC_ALL=C.UTF-8 PYTHONUTF8=1`** ile koşuldu (`en_US.UTF-8` bu imajda `UnicodeDecodeError`).
`ruff check` · `ruff format --check` · `mypy src` (400 dosya) **temiz**.

**Dürüst sınır:** frontend'de sıfır satır → **hiçbir frontend kapısı koşulmadı**; tam backend
suite'i **uçtan uca koşulmadı** → geçen sayı ve coverage yüzdesi **CI'ın otoritesinde**.

**NUMARA/ETİKET:** dal `7f4d927`'den kesildi ve o an `list_pull_requests(state=open)` **boş**
döndü — son üç partinin de kaydettiği gibi bu bir **garanti değil, anlık görüntüdür**. PR açıkken
main ilerlerse dal **rebase** edilir (*"Update branch"* düğmesi DEĞİL) ve tavan **merged ağaçta
taze bir `--report` ile YENİDEN ÖLÇÜLÜR**; taşınan bayat bir freeze `--ratchet`'i sonsuza dek
yeşil bırakır (ölçülen < tavan asla kırmızı vermez).

**Blocker sayısı DEĞİŞMEDİ (1 — yalnız A-08), BLOCKED.** Codemap güncellemesi gerekmedi
(yeni endpoint / tablo / sayfa / job yok).
`PROJECT_HISTORY.md` §ADIM 101 · `docs/ADIM101_LANDED_KICKOFF.md`.


## Stage 102 — kabul borcu batch 23 (doc 16 Results History, backend): RH-13 + RH-14 kapandı, DOC 16 BİTTİ landed

**Ne indi.** İki yeni integration case (`backend/tests/integration/test_result_row_immutability.py`)
+ kabul defteri + üretilmiş artefaktlar. **`backend/src` altında sıfır satır**, migration yok,
OpenAPI değişmedi.

**Kapananlar: `RH-13` (c2) · `RH-14` (c3)** — ikisi de kendi kriterinin **son açık clause'uydu**,
ikisinin de `debt_class`'ı KALDIRILDI. **Doc 16 artık 16 covered / 0 partial — HER SINIFTAN sıfır
açık borç.** İkisini de **ADIM 55 ölçmüş ve *plumbing* diyerek ertelemişti**; bu parti o plumbing'i
sağladı, ve ertelemenin iki gerekçesinden **biri yanlış çıktı** (aşağıda).

- **`RH-13.c2` — doc 17 ile doc 16 arasındaki sınır hiç iddia edilmemişti.** Hiçbir test Results
  History'yi daraltılmış bir profil ÖNCESİ ve SONRASI listelemiyordu. Yeni case `_seed_registry`
  ile metrik REGISTRY'sini kurar (ADIM 55'in ertelediği plumbing), sonra **yalnız `profit_factor`
  + `total_stops`** seçen kişisel bir profil revizyonu uygular — yani **BEŞ anahtar metriğin
  HEPSİNİ** düşürür, clause'un en güçlü biçimi. Karşılaştırma **tam sözlük eşitliğidir**: düşen
  bir anahtar da, eklenen bir anahtar da, değişen bir hücre de kırmızı verir (ADIM 98/101).
  **Vacuity iki yönde kapatıldı:** digest'in gerçekten DOLU olduğu (beş `None` kendine eşit olurdu)
  VE persist edilen seçimin anahtar metrikleri gerçekten DIŞLADIĞI, eşitlik iddia edilmeden önce
  assert edilir.
- **`RH-14.c3` — mevcut kanıt yalnız İLERİ okuyordu.** Agent-loop e2e testi artifact'ı,
  `source_task_id`'sini ve `ArtifactLink` satırlarını assert eder ama `BacktestResult`'ı sonradan
  **hiç geri okumaz**; mutasyonun yokluğu bir **inşa argümanıydı, bir assertion değil**. Yeni case
  **sevk edilmiş gateway yolunu** (`artifact.create`, `research` policy scope) GERÇEK bir persist
  edilmiş result'a karşı sürer — id hem `evidence_refs`'te hem bir provenance link'inde taşınır —
  sonra her dayanıklı sütunu artı manifest snapshot'ını geri okur.
  **ÖLÇÜM DÜZELTMESİ:** ADIM 55 bu clause'u *"capability registry'yi Limited'a yürütmek gerekir"*
  diye kaydetmişti, çünkü onu `commands/capability.create_analysis_artifact`'a karşı okumuştu.
  `RH-14`'ün adlandırdığı yol **agent tool gateway `artifact.create`**'tir ve o **capability-gated
  DEĞİLDİR** — ne yürüyüş gerekti ne de principal çakışması doğdu.

**İki negatif kontrol, ikisi de HEDEF assertion'ında kırmızı** (her biri yamanın uygulandığını
eşleşme sayısıyla assert etti, ağacı `finally`'de geri yazdı, ve her turdan sonra `git status`
okundu):

- **NC-1** — `list_backtest_results` digest'i çağıranın kişisel profil seçiminden geçirir
  (clause'un yasakladığı sızıntının ta kendisi) → hedef **eşitlik** assertion'ında kırmızı, beş
  hücre de `None`. **Aynı kusur altında `test_results_history` + `test_arrange_metrics` 39/39
  YEŞİL kaldı.**
- **NC-2** — `artifact.create` provenance link'i üzerinden yazar (`row_version += 1`) → hedef
  **snapshot** assertion'ında kırmızı, diff tam olarak `row_version 2 != 1`. **Aynı kusur altında
  agent-loop + trash-artifact + tool-gateway suite'leri 24/24 YEŞİL kaldı — `RH-14`'ün KENDİ kanıt
  testi dahil.**

**GÖLGE YOK, ölçüldü:** her iki kontrolde de hedeften ÖNCEKİ non-vacuity assertion'ları GEÇTİ
(NC-2'de "çağrı başarılı" + "link bu result'ı gösteriyor"), yani kırmızı gölgelenmedi. Her iki
kusurun mevcut suite'leri yeşil bırakması, yeni assertion'ların **başka bir eksene** baktığının
kanıtıdır — işaretleme değil, kapsama.

**Bu partinin öğrendiği (ADIM 100'ün identity-map tehlikesi, TERS YÖNDEN):** `_reread`
`session.expire_all()` çağırır ve bu **eldeki DİĞER nesneleri de** expire eder. `task.task_id`
snapshot'tan SONRA okununca sync bağlamda lazy-load olur → `MissingGreenlet`. id **expire_all'dan
ÖNCE** yakalanır. Negatif kontrol harness'inin doğrulayıcısı da aynı turda düzeltildi: `new`,
`old`'u İÇEREBİLİR (değiştirme değil **ekleme** yaması), o yüzden kontrol *"`old` kayboldu mu"*
değil *"tam metin tam olarak bir kez var mı"* olmalıdır — ilk hali sahte bir başarısızlık üretti
ve yamayı reddetti.

**Tavanlar İNDİ: `partial` 64 → 62, `debt_class.B` 32 → 30**; açık borç **71 → 69**
(A=1 · B=30 · C=6 · D=32); kriter `covered` 297 → 299, clause `uncovered` 77 → 75. Taban `43dc70d`.

**Ortam (birinci elden):** container **çıplak** başladı — `backend/.venv` yok, Postgres cluster
yok, **ve repo bile klonlanmamıştı**; üçü de bu slice içinde kuruldu ve iki case ile iki kontrol
**gerçekten koştu** (`test_result_row_immutability.py` **5 → 7 passed**, skip yok; ilgili altı
suite birlikte **71 passed**). `alembic upgrade head` **`LC_ALL=C.UTF-8 PYTHONUTF8=1`** ile
koşuldu (`en_US.UTF-8` bu imajda `UnicodeDecodeError`). `ruff check` · `ruff format --check` ·
`mypy src` (400 dosya) **temiz**.

**Dürüst sınır:** frontend'de sıfır satır → **hiçbir frontend kapısı koşulmadı**; tam backend
suite'i **uçtan uca koşulmadı** → geçen sayı ve coverage yüzdesi **CI'ın otoritesinde**. `mypy`
CI'da yalnız `src` üzerinde koşar; test dosyası bu modülün mevcut yardımcıları gibi annotate
edilmemiştir ve bu kasıtlıdır.

**NUMARA/ETİKET:** dal `43dc70d`'den kesildi ve o an açık PR listesi **boş** döndü — önceki dört
partinin kaydettiği gibi bu bir **garanti değil, anlık görüntüdür**. PR açıkken main ilerlerse dal
**rebase** edilir (*"Update branch"* düğmesi DEĞİL) ve tavan **merged ağaçta taze bir `--report`
ile YENİDEN ÖLÇÜLÜR**; taşınan bayat bir freeze `--ratchet`'i sonsuza dek yeşil bırakır
(ölçülen < tavan asla kırmızı vermez).

**Blocker sayısı DEĞİŞMEDİ (1 — yalnız A-08), BLOCKED.** Codemap güncellemesi gerekmedi
(yeni endpoint / tablo / sayfa / job yok).
`PROJECT_HISTORY.md` §ADIM 102 · `docs/ADIM102_LANDED_KICKOFF.md`.

## Stage 103 — kabul borcu batch 24 (doc 20 Trash, backend): TR-08 kapandı landed

**ÜRÜN KODU DEĞİŞMEDİ** — tek yeni integration case
(`test_trash_page.py::test_restore_emits_its_trash_outbox_event`) + defter + üretilmiş
artefaktlar. `TR-08.c4` (restore'un outbox olayı — UM-08.c5'in birebir ikizi: `entity.restored`
satırı hep yazılıyordu, hiçbir test okumuyordu; e2e pipeline'ın trail sayacı kendi restore'undan
ÖNCE duruyor) son açık clause'du → `TR-08` **covered**, `debt_class` **KALDIRILDI**. İki negatif
kontrol: emisyon kaldırılınca 30 testte yalnız yeni test kırmızı (`scalar_one`); payload
boşaltılınca varlık okuması geçip kırmızı tam-sözlük eşitliğine taşındı (gölge yok).
**Tavanlar merged ağaçta TAZE ölçüldü: `partial` 62 → 61, `debt_class.B` 30 → 29** (dalın
#815'siz freeze'i 63/31'di, TAŞINMADI). **Doc 20'nin kapatılabilir backend borcu bitti**
(kalan: `TR-07` bulgu · `TR-12` sınıf C).
**SÜREÇ KAYDI:** bu oturum önce batch 23'ü (doc 16, RH-13.c2 + RH-14.c3) sonuna kadar yazdı;
kapanışta açık **#815**'in aynı iki kriteri `ADIM 102 / batch 23` olarak kapattığı görüldü →
çift iş **bütünüyle geri alındı** (ADIM 86 emsali), numara **103 / batch 24** alındı (yol
ölçümü: #815 `docs/ADIM102_LANDED_KICKOFF.md` ekliyor). #815 bu PR açıkken **ADIM 102 olarak İNDİ** (`4dab3de`) →
dal rebase edildi, `ADIM102` kickoff'u `historical`a demote edildi, canlı işaret `ADIM103`'te. **Blocker sayısı DEĞİŞMEDİ (1 — yalnız A-08), BLOCKED.** Codemap
güncellemesi gerekmedi. `PROJECT_HISTORY.md` §ADIM 103 · `docs/ADIM103_LANDED_KICKOFF.md`.



## Stage 104 — kabul borcu batch 25 (doc 09 Embedded System Packages, backend): ESP-20 + ESP-03 kapandı landed

**ÜRÜN KODU DEĞİŞMEDİ** — iki yeni integration case (`test_esp_persistence.py`) + defter +
üretilmiş artefaktlar. **`ESP-20` (c2+c3):** rol farkındalıklı filtre üretimde iki okuma yolunda da
bağlıydı ama **hiç yabancı aktörle sürülmemişti** — tek listing testi iki kaydı da AYNI sahiple
yaratıyor, yani post-filter satırı silinse yeşil kalırdı (NC-1'de ölçüldü). **`ESP-03.c4`:** yedi
kanonik TA fixture'ı `SEED_ESP_TA=1` arkasındaki seeder'da vardı, **hiçbir test onu çağırmıyordu**;
yeni case gerçek seeder'ı koşar, yedi `(ad, anahtar)` çifti **literal** yazılır, ad `change_note`
üzerinden bağlanır. **BEŞ negatif kontrol, beşinde de 24 testten yalnız yeni case kırmızı**; NC-4
(ad değişti, anahtar korundu) gölgeyi kaldırdı, **NC-5 REDDEDİLDİ** (unique kısıt assertion'ın
yerine geçti) ve yeniden kuruldu. **ON İKİNCİ BULGU — `ESP-05.c3` KURULAMAZ:** ESP kökü
rationale-assignable değil (`RATIONALE_ASSIGNABLE_PACKAGE_KINDS = {INDICATOR, CONDITION}`,
`_apply_assignment_change` → `LifecycleBlocked`; probe ile ölçüldü) → sınıf C şekli, **taşınmadı**.
**Tavanlar İNDİ: `partial` 61 → 59, `debt_class.B` 29 → 27** (açık borç 66). Doc 09 = 17/3.
**Blocker sayısı DEĞİŞMEDİ (1 — yalnız A-08), BLOCKED.** Codemap güncellemesi gerekmedi.
`PROJECT_HISTORY.md` §ADIM 104 · `docs/ADIM104_LANDED_KICKOFF.md`.


## Stage 105 — kabul borcu batch 26 (doc 06 Create Package, backend): CP-09 + CP-13 kapandı landed

**ÜRÜN KODU DEĞİŞMEDİ** — iki yeni integration case + defter + üretilmiş artefaktlar.
**`CP-09.c2`:** `submit_candidate_generation` hep `run_idempotent` ile sarılıydı ama hiçbir test
ona iki kez anahtar geçirmemişti; yeni case iki ekseni sürer (yanıtın TAM sözlük eşitliği + tek
durable `Job`) ve ilk çağrının gerçekten admit ettiğini ayrıca pinler. **`CP-13.c4`:** onay
sınırının izin yarısı hiç sürülmemişti (her request-approval testi düz USER olan `OWNER`'ı
kullanıyor); yeni parametrik case `request_package_approval`'ı Supervisor ve Agent için **kendi
paketleri** üzerinde koşar, geçişi satırdan geri okur, audit'i aktöre atfeder ve **aynı kök
üzerinde** publish'in `ApprovalRequiresAdmin` verdiğini pinler. **ASIL DERS: bir negatif kontrol
KIRMIZI VERDİĞİ HÂLDE reddedilebilir** — ilk NC 10 testi birden (mevcutlar dahil) kırmızı yaptı,
yani ayırt edici değildi; yeniden kurulan sürüm USER+Admin'i geçirip yalnız Supervisor/Agent'ı
reddediyor → **30 testte yalnız iki yeni case kırmızı, 28 mevcut test yeşil**. **İki ölçülmüş
sınır deftere yazıldı** (CP-09.c2'nin iki ekseni tek satırlık kusurla ayrışmıyor;
`request_package_approval` Owner-or-Admin olduğu için c4 aktörün KENDİ adayı için geçerlidir).
**Tavanlar İNDİ: `partial` 59 → 57, `debt_class.B` 27 → 25** (açık borç 64). Doc 06 = 12/3/1.
**SÜREÇ:** parti #817 CI'dayken yazıldı ama o dala İTİLMEDİ (karışma + CI restart + facts kapısı
kırmızısı); patch olarak taşınıp merged ağaçta yeniden koşuldu. **Blocker sayısı DEĞİŞMEDİ
(1 — yalnız A-08), BLOCKED.** Codemap güncellemesi gerekmedi.
`PROJECT_HISTORY.md` §ADIM 105 · `docs/ADIM105_LANDED_KICKOFF.md`.

## Stage 106 — kabul borcu batch 27 (doc 08 Package Library, backend): PL-07 kapandı landed

**ÜRÜN KODU DEĞİŞMEDİ** — tek yeni integration case + defter + üretilmiş artefaktlar.
**`PL-07.c2`:** no-auto-repin garantisi yalnız Trading Signal düzleminde assert edilmişti;
paket→strateji düzleminde literal dizi (pinle → head'i ilerlet → geri oku) hiç koşulmamıştı.
**ASIL DERS: vacuity tuzağı YAZMADAN ÖNCE ölçüldü** — mevcut strateji fixture'ları placeholder
id pinler (`pkg_int`/`pkgrev_int`) ve `_assert_references_active` V1-lenient'tir, yani o pinlerin
üstüne kurulan "hâlâ N" iddiası vacuous olurdu (ADIM 100'ün dersi proaktif uygulandı); yeni case
GERÇEK bir ACTIVE INDICATOR paketi tohumlar, gerçek head N'i pinler, head'i N+1'e ilerletir
(atıf muhafızı `!= N`), N'in adreslenebilir kaldığını, kenarın/saklanan config'in N'de durduğunu
ve İKİNCİ Save'in — çıkarım N+1 dünyasında koşarken — yine N'i pinlediğini ayrı eksenler olarak
sürer. **İKİ negatif kontrol, ikisi de ayırt edici:** NC-1 (kenar yazımı head'i çözer) 24 testte
yalnız yeni case'i ikinci-Save kenar assertion'ında kırmızı yaptı — 23 mevcut test yeşil kaldı
çünkü placeholder kökler hiç çözülmüyor (yeşil kalma, clause'un açıklığının ölçümüdür); NC-2
(Save config'i head'e yeniden yazar) yalnız son saklanan-config assertion'ını düşürdü.
**Tavanlar İNDİ: `partial` 57 → 56, `debt_class.B` 25 → 24** (açık borç 63). **Doc 08 = 19/2/0 —
testle kapanabilir sınıf-B satır KALMADI** (kalan `PL-08` + `PL-20`, ikisi de sınıf D).
**Blocker sayısı DEĞİŞMEDİ (1 — yalnız A-08), BLOCKED.** Codemap güncellemesi gerekmedi.
`PROJECT_HISTORY.md` §ADIM 106 · `docs/ADIM106_LANDED_KICKOFF.md`.

## Stage 107 — kabul borcu batch 28 (doc 11 Market Data, backend): MKD-02 kapandı landed

**ÜRÜN KODU DEĞİŞMEDİ** — bir yeni test dosyası (iki integration case) + defter + üretilmiş
artefaktlar. **`MKD-02.c1`:** doc 11 §13'ün kanonik-şema sınırı ("yalnız ohlcv / tick_trades /
spread_execution; funding/OI/liquidation/order-book Research düzleminde kalır") kaynakta
gerçekti ve Research yarısı kanıtlıydı (c2), ama Market yarısını hiçbir şey assert etmiyordu —
ne enum üyeliği ne de funding-tipli bir market revizyonunun wire reddi. **İKİ BİLEREK AYRI
EKSEN:** (1) üyelik LİTERAL pinlendi (doc 11'in üç adı elle, set EŞİTLİĞİ — eklenen üye de
kırmızı) + dört dışlanan ad `ResearchCategory` üyesi olarak pinlendi; (2) gerçek ASGI
route'larında İKİ tipli mutating yüzey (create + append) `funding_rate` ile sürüldü — kanonik
422 `VALIDATION_ERROR` + `field_path body.market_data_type`, sıfır satır (`expire_all()`
sonrası sayım), head/row_version kıpırdamadı, yüzey başına pozitif kontrol. **ÜÇ negatif
kontrol, üçü de ayırt edici, üçünde 19 mevcut test YEŞİL:** NC-1 (enum'a üye ekle) iki ekseni
de düşürdü (üyelik eşitliği + 422→201); NC-2/NC-3 (route modeli `str`'a gevşet, yüzey başına)
üyelik eksenine GÖRÜNMEZ ve yalnız kendi yüzeyinin wire assertion'ını düşürdü. **Ölçülmüş
ikinci savunma hattı:** gevşek route'ta DB enum kolonu flush'ta yine reddediyor (satır inmez
ama red 500 olur) → testin pinlediği şey 422 SÖZLEŞMESİ, salt kalıcılık-yokluğu değil.
**Tavanlar İNDİ: `partial` 56 → 55, `debt_class.B` 24 → 23** (açık borç 62). **Doc 11 = 8/1/0 —
testle kapanabilir sınıf-B satır KALMADI** (kalan `MKD-04` sınıf D). **Blocker sayısı
DEĞİŞMEDİ (1 — yalnız A-08), BLOCKED.** Codemap güncellemesi gerekmedi.
`PROJECT_HISTORY.md` §ADIM 107 · `docs/ADIM107_LANDED_KICKOFF.md`.

## Stage 108 — kayıtsız inen #822'nin ritüeli: dört bayat precheck advisory `note`'u düzeltildi (§6.1b kapandı) landed

**Bu kayıt bir DEFTER; kaydettiği slice (#822, main'e `32d2c96`) kendi ritüelini yazmadan inmişti**
(`grep -c '#822'` → 0, ölçüldü). **ÜRÜN KODU DEĞİŞTİ ama YALNIZ PROZA:** üç dosya,
`frontend/e2e/specs/20-a11y-prechecks.spec.ts`'te **dört satır ve dördü de bir `note:` değeri**
(`:243` K-4 · `:252` K-3 · `:262` K-2 · `:271` K-5), artı `a11y_screen_reader_audit_results.md`
§6.1b ("kapandı" olarak yeniden yazıldı) ve runbook §0. **Predicate, eşik, `observed`, per-route
sayım, K-tablosu reach'i ve gating el DEĞMEDİ; hiçbir advisory SUSTURULMADI** — özellikle K-3
`contentinfo`: D-11 o gözlemin *dispozisyonunu* sabitledi, **ölçümünü değil**. Migration yok,
alembic head `0043_i08_registry_strategy_fks`, `ENGINE_VERSION` ve OpenAPI değişmedi, kabul borcu
tavanları **OYNAMADI** (`partial` 55 · A=1 B=23 C=6 D=32), donmuş kanıt (`docs/releases/evidence/`)
**DOKUNULMADI** (kayıttır, düzeltilmez), A-08 sayaçları (2/184, 0/4) · #514 · K-tablosu el değmedi.
**Blocker sayısı DEĞİŞMEDİ (1 — yalnız A-08), BLOCKED.**

**ÜÇ BULGU.** (1) §6.1b **üç** bayat note listeliyordu; düzeltirken **DÖRDÜNCÜSÜ** bulundu (`:243`,
`<h1>`-yok / K-4) ve o **iki bayatlık birden** taşıyordu: aynı retired A-3 ifadesi **VE** tek
yayıcısının kapanmış olması (`/user-manual`; K-4 / PR #685 `<h1>`'ini verdi — §6'nın K-tablosu
sayının **1 → 0** olduğunu zaten kaydediyor, `pageTruth.ts` yorumu da doğruluyor). (2) **Dördün
İKİSİ bugün ULAŞILAMAZ** (K-2 skip link, K-4 `<h1>` — ikisini de **aynı PR**, #685, kapattı):
**silinmediler, REGRESYON TRIPWIRE'ı olarak tutuldular** ve notları bunu yazıyor — bugün geçtiği
için bir dalı silmek geri gelişini fark edecek tek şeyi silerdi. (3) **`npm run typecheck`
`frontend/e2e/`'yi KAPSAMAZ** (`frontend/tsconfig.json` `"include": ["src"]`); o dosyanın gerçek
kapısı **`npx tsc --noEmit -p e2e/tsconfig.json`**.

**ASIL DERS: BİR CHECKLIST'İ DÜZELTMEK, ONU ALINTILAYAN MAKİNE ÇIKTISINI DÜZELTMEZ.** ADIM 63 A-3'ü
*"insandan bir makine ölçümünü tekrarlamasını istiyor"* diye yeniden yazdı — ama **yalnız
checklist'te**; precheck 22 heading-outline advisory'sinin yanına retired soruyu basmaya devam etti
ve runbook §4 denetçiyi *"önce buraya bak"* diye tam oraya yolluyordu. **İKİNCİ DERS: bayat bir
işaretçiyi düzeltmek yenisini doğurur** — runbook §0'ın *"bu bayat note'u yoksay"* bloğu, note
düzelince kendisi bayatladı; aynı PR'da düzeltildi.

**Doğrulama + dürüst sınır:** yerelde `npm run lint` + eslint(dosya) + `npx tsc --noEmit -p
e2e/tsconfig.json` yeşil; **typecheck negatif kontrolden İKİ KEZ geçti, düzenlenen bölge başına bir
kez** (`TS1005` `:271` ve `:243`, commit edilmiş numaralandırmaya karşı) → kapı vacuous değil.
**Precheck spec'i yerelde KOŞULMADI** (seeded stack) — o yarının otoritesi CI: head `87f51ed`,
**22 check → 18 success, 4 skipped (nightly), 0 failure**, `A11Y — axe-core scan` **success**.
**#820 da kayıtsız indi** (§6.1b'yi ilk yazan slice) ve bu kapanış onun kaydını **UYDURMADI** —
sahibi yazmalı (ADIM 97 emsali). Codemap gerekmedi (yeni endpoint/tablo/sayfa/job yok).
`PROJECT_HISTORY.md` §ADIM 108 · `docs/ADIM108_LANDED_KICKOFF.md`.

## Stage 109 — kayıtsız inen #820'nin ritüeli: A-08 devam kartı + ölçülemeyen bir tazelemenin kaydı landed

**Bu kayıt bir DEFTER; kaydettiği slice (#820, main'e `99a7f30`, 2026-08-25) kendi ritüelini
yazmadan inmişti** (`grep -c "^## ADIM.*#820"` → **0**, ölçüldü). **DOCS-ONLY: iki dosya, +222/−14**
(`git show --numstat`: runbook +116/−9 · worksheet +106/−5) — **ürün kodunda, testte, migration'da
SIFIR satır** (`git show --name-only` iki `docs/` yolu döndürür, başka hiçbir şey). Migration yok,
alembic head `0043_i08_registry_strategy_fks`, `ENGINE_VERSION` ve OpenAPI değişmedi, kabul borcu
tavanları **OYNAMADI** (bu ağaçta taze ölçüldü: `partial` 55 / `uncovered` 7 · A=1 B=23 C=6 D=32),
donmuş kanıt (`docs/releases/evidence/`) **DOKUNULMADI**. **A-08 İLERLEMEDİ — hiçbir hücre dolmadı:**
Section A **2/184** · Section B **0/10** · çıkış kriterleri **0/4** · hiçbir çıkış kriteri
işaretlenmedi · **#514 EL DEĞMEDİ** (`updated_at` hâlâ `2026-08-12T11:08:58Z`, `state: open`,
`state_reason: reopened` — API'den ölçüldü). **Blocker sayısı DEĞİŞMEDİ (1 — yalnız A-08), BLOCKED.**

**NE YAPTI.** Runbook'a **YENİ §0** — bir sayfalık *next-session card*: SR-2 devam eder (SR-1'in
hâlâ ne makinesi ne denetçisi var), rota 1 `/`, hücre sırası **A-3 → A-4..A-8**, sonra rota 2–23,
sonra §2'nin on akışı; kart, *tek bir kombinasyonun ilerlemesinin* çıkış kriteri 1'i **1/2**'de ve
kriter 2'yi **23/46** rotada bıraktığını denetçinin okuduğu yerde tekrarlar. Runbook §4/§6.4'te üç
bayat ifade düzeltildi (K-2/K-3/K-4/K-6b çözülmüş · *"21 pages"* → **22** · K-6 → **K-6a**).
Worksheet'e üç yeni bölüm: **§6.1a** (tazeleme denemesi **BAŞARISIZ**, aşağıda) · **§6.1b**
(precheck'teki üç bayat advisory `note`'u **kaydedildi**, düzeltilmedi — kaynak değişikliği,
frontend kapıları o container'da koşmuyordu, dispozisyon insanın) · **§6.1c** (rota listesi
`screenshotMatrix.ts::TARGET_PAGES`'ten **yeniden türetildi**: 23 girdi, §1 ile satır satır uyuşuyor,
**bayat DEĞİL**).

**ÖLÇÜLMÜŞ YÖNLENDİRME — ve bu, bir sonraki oturumun ilk saatini değiştirir.** Donmuş 2026-08-12
beş-koşu kanıtında (`a08_precheck_results_run5.json`) **`/`, heading-outline advisory'si yayMAYAN
TEK rotadır**; diğer 22'sinin hepsi yayar. İki sonucu var: **rota 1 K-5'i KAPATAMAZ** (K-5 ancak
kendi kümesindeki bir rotada kıpırdar, worksheet'in işlenmiş örneği `/backtest/run`), ve **bir
önceki oturumun A-3 sorusu orada VAR OLMAYAN bir atlamayı adlandırıyordu** — yani o hücredeki `—`
iki kere haklıydı. Ayrıca **K-6a yalnız `/` üzerinde problanır** (ilk dakikada cevaplanır,
human-only) ve **K-7 bir Section B sorusudur** (B-3/B-4/B-6), Section A onu çözmez.

**ASIL DEĞER: #820 BİR ÖLÇÜM YAPAMADIĞINI KAYDETTİ VE YERİNE UYDURMADI.** §6.1a'nın ürünü bir sayı
değil, bir **REDDİR**. Container'da `docker` ikilisi var ama **daemon yok**
(`dial unix /var/run/docker.sock: no such file`) ve **`minio` yok**; `a11y-audit-stack.sh`
compose tabanlı → stack kalkmıyor → `specs/20-a11y-prechecks.spec.ts`'in yürüyeceği seeded Admin
oturumu yok. **İkame bir stack UYDURULMADI:** farklı provision edilmiş bir stack sayfaların ilk data
render'ıyla farklı yarışır, ve bu **K-5 ile K-7'nin koşudan koşuya oynamasının BELGELENMİŞ TEK
sebebidir** — oradan gelen bir sayı yukarıdaki tablolardakilere **birebir benzer** ama başka bir şey
anlatır, yani insan denetiminin hakemlik etmek için var olduğu iki gözlemi **sessizce yeniden
tanımlardı**. Sayılar bu yüzden **2026-08-12 provenance'ında bırakıldı**, stale-by-default. Bu,
deponun *"yeşil exit code kanıt değildir"* / *"skip'li yeşil kanıt değildir"* dersinin **ölçüm
tarafındaki ikizidir**: yapılamayan bir ölçümün doğru çıktısı, yapılmış gibi görünen bir sayı değil,
yapılamadığının kaydıdır.

**İKİNCİ DEĞER — ve bu ARTIK KANITLI: #820 kusuru kendisi kapatmadı, KAPATILABİLİR HÂLE GETİRDİ.**
§6.1b'de kaydettiği üç bayat note, dört ay sonra değil **AYNI GÜN** düzeltildi — ve düzeltilirken
**DÖRDÜNCÜSÜ** bulundu (`:243`, `<h1>`-yok / K-4). Zincir tam olarak şudur: **#820 açtı →
#822 (`32d2c96`) düzeltti → ADIM 108 (#823) defterledi → bu kayıt #820'yi defterliyor.** ADIM 108
kaydının §*"DÜRÜST SINIR — #820 DA KAYITSIZ İNDİ"* paragrafı bu zincirin öteki ucudur ve
*"kaydını sahibi yazmalıdır"* diyordu — bu kayıt odur; ADIM 108'in ölçtüklerini **tekrarlamaz,
atıf yapar**.

**KICKOFF YOK, BİLEREK — ve bu bir atlama değil, ÖLÇÜLMÜŞ bir karar.** `check_classification` →
`_check_live_kickoff_is_newest` numarayı **DOSYA ADINDAN** okur (`ADIM_KICKOFF_RE`, glob
`docs/*KICKOFF*.md`), `doc-status` işaretinden değil. `docs/ADIM109_LANDED_KICKOFF.md` yaratılsaydı
kapı onu `current` olmaya **zorlar** ve `docs/ADIM108_LANDED_KICKOFF.md`'yi demote ettirirdi — oysa
ADIM 109, ADIM 108'den **ÖNCE** inmiş bir slice'ı kaydediyor; onun kickoff'unu canlı devam tohumu
yapmak yanlış olurdu, çünkü devam tohumu **en yeni** durumu anlatmalıdır. ADIM 82 emsali uygulandı:
geriye dönük kayıt için kickoff **hiç yazılmadı**, ADIM 108'inki canlı kaldı, kapı yeşil kaldı.
(ADIM 86/90 kickoff **yazdı** ama `historical` doğdu — onlar canlıdan **düşük** numaralıydı; bu
değil, bu **yüksek** numaralı, o yüzden dosya yaratmak kapıyı zorlardı.) Ritüelin **md. 5 de
atlandı, bilerek**: yeni endpoint / tablo / sayfa / job yok, tazelenecek codemap yok.

**DÜRÜST SINIR.** Bu kayıt #820'nin anlatısını **UYDURMADI** — commit gövdesine körü körüne
güvenilmedi, diff (`git show 99a7f30`), eklenen bölümler ve *"değişmedi"* iddialarının hepsi bu
ağaçta **yeniden ölçüldü**; ölçülemeyen hiçbir şey iddia edilmedi. **Ürün ve test kodunda sıfır
satır → backend ve frontend suite'leri KOŞULMADI ve hiçbir geçen/coverage sayısı iddia edilmiyor;
otorite CI.** #820 A-08'i **ilerletmedi**: değişen tek şey **devam edilebilirliktir**. Hiçbir belge
bu denetimi
**tamamlanmış** gösteremez ve hiçbir çıkış kriteri işaretlenmedi. Yerelde koşan üç kapı:
invariant taraması (boş) · `check_classification` (NONE) · `acceptance_semantic_scan.py --report
--check-generated --ratchet` (exit 0, tavan 55/7 sabit).
`PROJECT_HISTORY.md` §ADIM 109 · kickoff **YOK** (yukarıdaki gerekçe).

## Next: **PR B — `ItemParticipant` adaptörü + `jobs/backtest_engine.py:299` call site**

> **ADIM 109 GÜNCELLEMESİ (2026-08-25) — BAŞLIK VE GÖVDE DEĞİŞMEDİ, ÇÜNKÜ DEĞİŞECEK BİR ŞEY YOK.**
> ADIM 109 **geriye dönük bir defterdir**: kaydettiği slice (#820, `99a7f30`) ADIM 108'in kaydettiği
> #822'den **ÖNCE** inmişti ve DOCS-ONLY'dir — mühendislik hattına (`C6`, `F2`, `F3`, `C9` ve imzasız
> kapılar) **tek satır dokunmaz**. Bu blok yalnız "Next kıpırdamadı"yı yazılı hâle getirmek için var;
> aşağıdaki güncellemeler ve slice girdileri **bilerek el değmemiştir**.

> **ADIM 92 GÜNCELLEMESİ (2026-08-19) — BAŞLIK YİNE DEĞİŞTİRİLMEDİ, GÖVDE GÜNCELLENDİ.**
> (Gerekçe ADIM 81/85/86 güncellemelerinde: `docs-history-guard` `^-## ` desenine bakar, bir
> `## ` başlığını yeniden yazmak ona **kayıt silme** gibi görünür — ADIM 61 emsali, ADIM 85'te
> kapı **fiilen** kırmızı verdi.)
>
> **BU BAŞLIĞIN İKİ İŞİ DE ARTIK İNDİ.** Adaptör yarısı = `C3` = **#777** = §ADIM 85. **Call
> site yarısı = `C4` = BU SLICE = §ADIM 92**: `_use_unified_clock` tek yerde, paylaşımlı dal
> item döngüsünün kardeşi, `iter_portfolio` üzerinden **checkpoint #3b**, ve containment
> tripwire'ı **yetkili-çağıran allowlist'ine DARALTILDI** (silinmedi, gevşetilmedi; iki
> dokunulmaz assertion yeşil). Bu başlık altında **yeni bir dal AÇILMAMALIDIR.**
>
> **Containment AÇILMADI ve bu slice onu açmaya YAKLAŞMADI:** `SHARED_ALLOCATION_STATUS`
> `future_dev`, `ENGINE_VERSION` sabit, 50 golden digest bayt bayt aynı, `5000.00`/`3000.00`
> fixture'ı el değmemiş. Dal **çalışıyor** — test-sahipli bir lift fixture'ıyla iki-Strategy'li
> paylaşımlı bir run gerçekten `project_portfolio_run` Result'ı üretiyor — ama üretimde
> admission her paylaşımlı run'ı reddediyor.
>
> **SIRADAKİ KALEM `C6` DEĞİL, ÖNCE İKİ İMZA.** `C6`'nın ön koşulları `G11` (P2) ve `G12` (P8)
> ve **ikisi de imzasız** (brifingli ≠ imzalı). `C5` **zaten sevk edilmiş** (ADIM 72'de
> ölçüldü). `C7` `C4` + `C5` ister ve `manifest.py`'ye dokunur — `execution_key` namespace'ini
> kaydırır, yani **A15**'tir. **İmzasız bir kapının arkasındaki slice'a BAŞLAMA.**
>
> **`C4`'ün ölçtüğü ve `C6`'ya devrettiği:** adaptörün on bir reddi ile `C6`'nın admission
> blocker listesi **aynı** olmalıdır, ve standart strateji fixture'ı o listeden **üç** maddeden
> düşüyor (`entry_timing`, `exit_timing`, `same_direction_stacking`). Şema varsayılanı
> `allow_stacking` olduğu için bu **kayıtlı stratejilerin çoğunu** ilgilendirir → ürün kararı.

> **ADIM 85 GÜNCELLEMESİ (2026-08-19) — BAŞLIK BİLEREK DEĞİŞTİRİLMEDİ, GÖVDE GÜNCELLENDİ.**
> Bu slice'ın bir yazımı başlığı *"`C4` (E5) …"* olarak yeniden adlandırmıştı; geri alındı,
> çünkü `docs-history-guard` `^-## ` desenine bakar ve bir `## ` başlığını yeniden yazmak ona
> **kayıt silme** gibi görünür (ADIM 61 emsali; ADIM 81 ve ADIM 84 aynı kararı aynı gerekçeyle
> vermişti). **Kapı fiilen kırmızı verdi ve `ENTROPIA_HOOKS=off` ile atlanmadı** — düzeltilen
> kapı değil, başlıktı. Kural: *başlığa dokunma, düzeltmeyi gövdeye yaz.*
>
> **Başlık iki iş adlandırıyor ve ADAPTÖR yarısı İNDİ** (`C3`,
> `participant.py::_EngineParticipant` — üretimde çağıranı **YOK**, 50 golden digest bayt bayt
> aynı, `assert callers == []` el değmedi). Kalan yarı call site'tır ve o **`C4`**'tür:
> `_use_unified_clock(capital_execution)` **tek** yerde, paylaşımlı dal item döngüsünün
> **kardeşi** olarak, `iter_portfolio` üzerinden tick-adımlı iptal kontrolü, ve containment
> tripwire'ının *"hiçbir şey çağırmıyor"* assertion'ının **yetkili-çağıran allowlist'ine
> DARALTILMASI** (silinmesi ya da gevşetilmesi değil). `C4` de containment'ı **AÇMAZ**.
>
> **`C4`'ün iki conjunct'ı da taşıyıcıdır** (`shared_allocation_is_executable()` **ve**
> `shared_allocation_requested(...)`): biri eksik kalırsa her bağımsız kompozit Result
> **sessizce yeniden fiyatlanır** — bayraksız, bump'sız, kullanıcıya görünmeden.
>
> **`C3`'ün `C4`'e devrettiği iki ölçülmüş kalem:** (1) giriş fill'i komisyonunun havuza
> aynalanacak bir fazı yok; (2) adaptörün on bir maddelik reddi `C6`'nın admission blocker
> listesiyle **aynı** olmalıdır ve `allow_stacking` şema varsayılanı olduğu için bu bir **ürün
> kararı** doğurur.


> **ADIM 86 GÜNCELLEMESİ (2026-08-19) — BAŞLIK YİNE DEĞİŞTİRİLMEDİ.**
> (Gerekçe yukarıdaki ADIM 81 güncellemesinde: `docs-history-guard` `^-## ` desenine bakar,
> bir `## ` başlığını yeniden yazmak ona kayıt silme gibi görünür — ADIM 61 emsali. **ADIM 85
> bunu bir kez denedi, kapı FİİLEN kırmızı verdi ve başlık geri kondu**; kural artık ölçülmüş.)
> Başlık **iki iş** adlandırıyor ve **ADAPTÖR yarısı İNDİ** — `C3` = **#777** = **§ADIM 85**
> (`2cda24f`; `participant.py::_EngineParticipant`, üretimde çağıranı **YOK**, 50 golden digest
> bayt bayt aynı). Bu paragrafın ilk yazımındaki *"`C3` hâlâ sıradaki mühendislik kalemi"*
> iddiası **artık geçersizdir**: sıradaki kalem başlığın **call site** yarısı, yani **`C4`**'tür
> ve **yeni bir `C3` dalı AÇILMAMALIDIR**. Ayrıntı ADIM 85'in aynı başlık altındaki bloğunda.
>
> **Bu kapanışın kaydettikleri #765 + #766'dır** (P1'in parity kanıtı + P2'nin wiring'i) —
> ikisi de kayıtsız inmişti, kaydı `PROJECT_HISTORY.md` **§ADIM 86**. Bunlar `C`-hattını
> ilerletmez; **performans (`P`) hattıdır** ve o hat bu slice ile P-C2 §D.1'in
> **üç bacağından ikisini** kapatmış olur. **Kalan leg 3 bir performans işi DEĞİL, bir ürün
> kararıdır (`G15`, imzasız)** — `run_readiness_check` satırının `per_item: 1`'i o yüzden
> durur ve **indirilmemelidir**.
>
> **Yukarıdaki ADIM 81 güncellemesinin *"kayıt görünmeyen PR'lar"* satırı bir kez daha
> çürüdü ve yine doğru yönde:** orada **#765** *"kayıtsız"* diye listelenmişti; bu kapanış
> onu (ve o liste yazıldıktan sonra inen **#766**'yı) yazdı. **Kalan satırları present-tense
> okuma — ölç:** #752 · #755 · #747 · #761 · #770 · #774 · #773 · #762 hâlâ kayıtsız görünüyor,
> hepsi karar/brif belgesi. **Kaydı sahibinin yazması gerekir.**
>
> **G9/G13 hakkında:** ikisi de **İMZALI** (ADR-0002 §13.2, `9fc5580`, PR #753, 2026-08-17 —
> G9 `APPROVED as stated`, G13 `FOLD`). Bu kapanışın devir promptu bunları *"imzasız"*
> sanıyordu; **belgeler zaten doğruydu**, bayat olan bağlamdı. **Hâlâ imzasız:** Karar 1
> (#552), Karar 3 (#559), `G12`, `G15`; `G10` **hiç talep edilmedi**.

> **ADIM 85 GÜNCELLEMESİ (2026-08-19, main `7f331c7`) — `C3` ARTIK BEKLEMİYOR, İKİ DALDA
> BİRDEN SÜRÜLÜYOR.** Başlık yine **bilerek değiştirilmedi** (ADIM 81/61 emsali: bir `## `
> başlığını yeniden yazmak docs kayıt-silme kapısına kayıt silme gibi görünür) — düzeltme
> gövdeye yazılır. Ölçüldü (`list_pull_requests(state=open)`, 2026-08-19T06:0xZ): **PR #777**
> (*the engine-backed ItemParticipant adapter (E4c) + its two invariants*) ve **PR #782**
> (*ship the _EngineParticipant adapter (E4c)*) **ikisi de** `domain/backtest/participant.py`
> + `domain/backtest/engine.py` + containment gate testine dokunuyor. Yani bu satır bir
> **sıradaki iş** değil, **açık bir çakışma**dır: yeni bir oturum `C3`'e başlamadan ÖNCE bu
> iki PR'ın hangisinin kazandığına bakmalı. ADIM 85 bu yüzden `HAT B`'ye hiç dokunmadı ve
> `HAT A`'yı (kabul borcu batch 12) sürdü.

> **ADIM 81 GÜNCELLEMESİ (2026-08-18, main `1741b03`) — BU BAŞLIK ARTIK `C3`'Ü ADLANDIRIYOR,
> ve gövdesinin `C2` yarısı BAYATTIR.** Başlık **bilerek değiştirilmedi** (docs kayıt-silme
> kapısı `^-## ` desenine bakar ve bir `## ` başlığını yeniden yazmak ona kayıt silme gibi
> görünür — ADIM 61 emsali); düzeltme **gövdeye** yazılır. Aşağıdaki blok `C2`'yi **gelecek
> zamanda** (*"PR #759 onu sevk ediyor"*) anlatıyordu. **`C2` İNDİ** — `c78b15b`, **PR #759**,
> 2026-08-18T13:42Z. Ağaca karşı ölçüldü:
> `portfolio_engine.py::ItemParticipant.settle` ve `::finalize` **zorunlu** Protocol üyesi
> (`hasattr` probe'u **yok**), `PHASE_ORDER` **dokuz faz** — `P10` dahil —,
> `iter_portfolio` ve `PORTFOLIO_LOOP_VERSION` yayımlı.
> **#759'un kaydı bu kapanış yazılırken YOKTU; bu blok tazelenirken VARDI** — `PROJECT_HISTORY.md`
> §**ADIM 82** (PR **#778**, bu PR CI'da beklerken indi). Bu kapanış onun anlatısını **yazmadı**
> (ADIM 69/70 dersi: kaydı sahibi yazar) ve doğru olan buydu — satır sahibine gitti. Hâlâ
> kayıtsız görünenler: #752 #755 #747 #761 #770 #774 #773, artı bu PR açıkken inen #762 #765 —
> tablo `docs/ADIM81_LANDED_KICKOFF.md` §*Bugün main'e inen … kayıt görünmeyen PR'lar*
> (**o tablo da present-tense okunmaz, ölçülür**).
>
> **Sıradaki mühendislik kalemi `C3`.** Ölçüldü:
> `backend/src/entropia/domain/backtest/execution/` altında **`participant.py` YOK**.
> Önündeki kapı bir **imza değil, bir İNSAN İNCELEMESİDİR**: `portfolio_engine.__all__`
> Protocol'ün tiplendiği altı tipin hiçbirini yeniden yayımlamıyor, o yüzden `execution/`
> dışındaki her implementasyon containment gate'in importer kontrolünü **zorunlu olarak**
> kırmızıya çevirir → **bilinçli ve gözden geçirilmiş** bir allowlist genişletmesi gerekir,
> sessiz bir gevşetme değil. Brif **PR #761**'de indi
> (`docs/decisions/closure_participant_importer_allowlist_2026-08-18.md`) ve **İMZASIZDIR**.
>
> **İmzasız kapılar (ADIM 81 ölçümü — 11 açık):** `G1`/`G2`/`G3` (#552 → `F3`) · `G4` (`F2`,
> brifingli #755) · `G8` (#559 → `C9`) · `G10` (Gate 2 / containment lift — **hiç talep
> edilmedi**) · `G11` (`C6`; brif **PR #771**'de AÇIK olabilir — önce ölç) · `G12` (Karar 6,
> brifingli #752 → `C6`) · `G14` (#544 → `C9`) · `G15` (brifingli #747; ön koşulu **bir SAYI**
> ve alınmadı) · `G16` (A-08 — **ajan kapatamaz**).
> **BRİFİNGLİ ≠ İMZALI.** İmzasız bir kapının arkasındaki slice'a **BAŞLAMA**.
>
> **Paralel hat — kabul borcu: #768 İNDİ** (batch 08 + 09 = ADIM 78 + 79, bu PR CI'da
> beklerken) ve zinciri doğru çözdü — ADIM 80'in **96 / B 65** tabanının üstüne rebase edip
> yeniden dondurdu, main'de ölçülen taban artık **90 partial / B 59**. Defter **seri bir
> kaynaktır** ve bu onun kanıtıdır. **Sayıyı buradan alma** — otorite
> `docs/audit/acceptance_coverage_baseline.json` `ceilings`; **ratchet yalnız aşağı iner**.

> **AŞAĞIDAKİ SLICE GİRDİLERİ BİLEREK DEĞİŞTİRİLMEDİ** — ölçtükleri anı donduran kayıtlardır
> (ADIM 65 emsali). `G9`/`G13` hakkındaki cümleleri **present tense okuma**; ikisi de
> 2026-08-17'de imzalandı (ADR `0002` §13.2).

> **ÖNCE BUNU OKU — bu bloğun ALTINDAKİ iki güncelleme `G9`/`G13` için BAYATTIR (2026-08-18'de
> ölçüldü).** ADIM 72 ve ADIM 74 güncellemeleri *"sıradaki hamle bir İMZADIR"* ve
> *"`C2`/`C3`/`C4` → G9 + G13 imzasız"* der. **İkisi de artık yanlıştır:** ürün sahibi
> **2026-08-17**'de ADR §16 **Gate 1**'i imzaladı — **`G9` APPROVED as stated**, **`G13` =
> FOLD** — kayıt **ADR-0002 §13.2** (`9fc5580`, PR #753, main'de). Düzeltme **yukarıdaki
> ADIM 76 girdisinde** zaten yazılıydı; bayat cümleler başlığın **ALTINDA**
> kaldığı için `## Next:`'i giriş noktası olarak okuyan **yanlış** sonuca varıyordu (bu
> oturumun devir promptu tam olarak buna düştü). Alttaki iki paragraf **bilerek
> değiştirilmedi** — ölçtükleri anı donduran slice girdileridir (ADIM 65 emsali).
>
> **Ölçülmüş sonuç:** `C2` (E4b) bir imza beklemiyor, **kod bekliyor** — ve `PR #759`
> **onu sevk ETTİ ve MERGE EDİLDİ** (`c78b15b`, 2026-08-18T13:42Z; kaydı **ADIM 82**, geriye
> dönük yazıldı). Sıradaki mühendislik kalemi artık `C2` değil **`C3`**. Sevk edilenler: (`settle` + `finalize` **zorunlu** Protocol üyesi, `hasattr` probe'u yok,
> `PHASE_ORDER` **dokuz faz** → P10, `iter_portfolio`). **Hâlâ imzasız olan kapılar
> başkadır:** `G12` (Karar 6 — `C6`), Karar 1 (#552 — `F3`), Karar 3 (#559 — `C9`),
> `G4` (`F2`), ve `G10` (Gate 2 / containment lift) **hiç talep edilmedi**.
> **Bir kapının imzasını `docs/decisions/closure_product_decisions_2026-08-13.md`'nin
> kutusundan okuma** — G9/G13'ün imzası orada DEĞİL, **ADR-0002 §13.2**'dedir. O belgenin
> banner'ı altı kararın tamamı için imzanın **yerini** tablo hâlinde söyler; Karar 4/5'in
> kutuları 2026-08-18'de **geriye dönük** dolduruldu (ürün sahibi teyidi), yani artık boş
> değil — ama **işaretin kendisi otorite değildir**, §13.2'dir.

> **ADIM 71 (C1) SONRASI — sıradaki adım `C2` / E4b:
> `ItemParticipant.settle` + `.finalize`, P10, `iter_portfolio`.**

> **ADIM 72 GÜNCELLEMESİ (2026-08-17).** `C5` **indi** (#740) — planın *"ikinci şerit
> doldurucusu"* önerisi artık **tükendi**; ölçüm, R-1'in zaten sevk edilmiş olduğunu ve
> yapılacak iş kalmadığını gösterdi. `E5` (#738) aynı gün **bağımsız olarak** aşağıdaki
> engelleri yeniden ölçtü ve **doğruladı**: `C2` yok (`settle`/`finalize`/`iter_portfolio`
> **0 hit**, `PHASE_ORDER` 8 faz), `C3` yok (`participant.py` yok, `backend/src`'te **sıfır**
> `ItemParticipant` impl'i), `G9` **NOT REQUESTED**, `G13` **UNDECIDED**.
> **Ajanın kapatabileceği mühendislik ön koşulu KALMADI — sıradaki hamle bir İMZADIR.**
> Planın kalan koşulabilir kalemleri artık `C5` dışındakiler: bkz. §6 tablosu
> (`R2`/`R3`/`P1`/`P2` hatları ve açık PR'lar #741 #742 #743).

> **ADIM 74 GÜNCELLEMESİ (2026-08-17).** `R2` (#742) ve `R3` (#745) **indi**; `R4` ölçüldü ve
> **zaten #730'da inmişti** → **PACKAGE R BİTTİ**, bu satırın işaret ettiği açık PR listesi
> (#741 #742 #743) tükendi: #741 ve #742 merge edildi, #743 kapatıldı (yerine #745).
> **Sıradaki hamle hâlâ bir İMZADIR** — `F2` → G4 imzasız · `F3` → G1+G2+G3 imzasız ·
> `C2`/`C3`/`C4` → G9 + G13 imzasız, ardından importer-allowlist **insan incelemesi** ·
> `A-08` → ajan kapatamaz. İmzasız bir kapının arkasındaki slice'a **BAŞLAMA**, ürün kararı
> **UYDURMA**. Ve bir slice'a girmeden ÖNCE ağaca karşı **ölç**: bu dalgada planın *"açık"*
> dediği iki kalem (R3'ün yarısı, R4'ün tamamı) ağaçta **KAPALI** çıktı.

> **ADIM 71 (C1) §4.1'in (b) engelini DARALTTI ama KAPATMADI.** *"Üç faz book eder,
> `ItemParticipant` tarif ister"* artık **yanlış**: describe yarıları
> (`_compute_carry` / `_evaluate_held` / `_evaluate_entry`) sevk edildi ve `_evaluate_entry`
> ölçülmüş biçimde **sıfır** etki yazıyor. **Kalan engel Protocol'ün kendisi:** bugün
> **write-only** — loop bir kaleme ne YAPTIĞINI söyleyemez, çünkü `settle` yok.
>
> **BUNDAN ÖNCE İKİ İMZA GEREKİR ve ikisi de agent tarafından kapatılamaz:**
> **G9** = ADR-0002 §6/§8 amendment'ı (`settle`, `finalize`, P10, `iter_portfolio`) —
> **`Accepted`** bir ADR'yi değiştirmek onu kabul eden imzayı ister; **G13** = P10
> end-of-data equity noktası (son `t_ms`'e **ekle** mi, içine **katla** mı — eklemek aynı
> ana iki nokta koyar ve **A5**'in by-construction sıralılık iddiasını kırar).
>
> **`settle`/`finalize` ZORUNLU Protocol üyesi olmalı, `hasattr` ile YOKLANMAMALI:**
> yoklama fail-open'dır ve `settle`'ı unutan bir participant sessizce düz koşar. mypy bunu
> yapısal olarak zorlayamıyorsa **dur ve seam'i yeniden düşün** (plan `C2` stop condition).
>
> **`C3` (adapter) `C2`'ye bağlı** ve ayrıca **importer-allowlist kararı** ister:
> `portfolio_engine.__all__` Protocol'ün tiplendiği altı tipin **hiçbirini** yeniden
> yayımlamıyor, o yüzden `execution/` dışındaki her implementasyon containment gate'in
> importer kontrolünü **zorunlu olarak** kırmızıya çevirir — bu **bilinçli** ve
> **gözden geçirilmiş bir genişletme** ister, sessiz bir gevşetme değil.
> Ölçüm: `docs/audit/closure_e4_adapter_precondition_measurement_2026-08-17.md` (PR #731).
>
> **`C5` (allocation plan revision pin) — HEDEFİ ZATEN SEVK EDİLMİŞ, kod slice'ı DEĞİL.**
> Bu kayıt yazıldığında `C5` planın *"ikinci şerit dolgusu"* sayılıyordu; ölçüm bunu
> çürüttü: `readiness_check.py::_resolve_allocation` config'i **koşullu** kurar —
> `_pinned_revision` bir revizyon döndürürse **dondurulmuş satırdan**, yalnız `None`
> döndürürse draft'tan, ve o durumda `plan_revision_id` de `None` olduğu için ikisi
> **hiçbir yönde ayrışamaz**. Bayat olan kod değil **ADR 0002 §10.2**'nin present-tense
> cümlesi. Ölçüm ve dispozisyon: **PR #740**. `C5`'i kod yazmak için AÇMA.

### Bu hedefin ADIM 71 öncesi gerekçesi (korundu)



> **ADIM 69 sıralamayı belgeledi. BAŞLIK DEĞİŞMEDİ — PR B hâlâ kilometre taşıdır**; plan
> onun ÖNÜNDEKİ işi sıraya koyar, onu değiştirmez.
>
> **W4-a/W4-b'nin durumu, bu kapanışta YENİDEN ÖLÇÜLDÜ** (kayıt yazıldığında iddia edilen
> *"`R1`/`R2` #730 ile indi"* **YANLIŞTI** ve düzeltildi): planın `R1`'i
> (`final_closure_ordered_plan_2026-08-13.md:331`) **`TimingProvenance` value object +
> byte-identity proof**'tur, yani **#734**'tür — #730 ise `P-E3`/bundle kimliği idi, ayrı bir
> slice. Merge edilmiş durum:
>
> | Slice | Durum |
> |---|---|
> | **`F1`** | landed — **#729** (bu kapanışta ADIM 70 olarak kaydedildi) |
> | **`R1`** | landed — **#734** |
> | **`C1`** | landed — **#735** (E4a describe/book split; 50 golden digest kıpırdamadı) |
> | **`P3`** | **açılabilir** — whole-operation query budget backstop, kapısı olmayan tek Ready Check ölçümü |
> | **`C5`** | **açılabilir** — R-1 allocation pinning; `C1`–`C4`'e bağlı DEĞİL, ayrık dosya kümesi |
> | `R2` / `R4` | **G6 imzasını** bekler |
>
> **Tavan 3 eşzamanlı PR, `engine.py`/golden dosyaya dokunan TAM 1.** `C1` indiği için
> `F3` artık o kısıt açısından serbesttir — ama `_phase_tail()` hâlâ paylaşılan yüzeydir
> (`C1` ona **karakter karakter dokunmadı**, tam da `F3` talep ettiği için), `F3` ile `A-3`
> aynı anda açılmaz.
>
> **`C1`'in stop condition'ı ateşlendi ve bir kapıyı ZORUNLU yaptı:** `_phase_tail`'in scaling
> bölümü describe/book çifti olarak ayrılabiliyor ama **stacking book etmeden önce
> sıralanamıyor** — paylaşımlı run için bu *"ayrılamaz"* ile aynı şey → **G12 (scaling
> admission blocker) artık öneri değil, ölçülmüş zorunluluk**
> (`docs/audit/closure_c1_phase_tail_scaling_separability_2026-08-17.md`). Planın `C6` satırı
> G11/G12'yi hâlâ nötr bir *"blokla ya da modelle"* seçimi gibi çerçeveler; **G12 için o
> çerçeve artık yanlıştır.**
>
> **`C3`'ün önünde planın bilmediği 17. bir kapı var (#731):** Protocol'ün ihtiyaç duyduğu
> **altı tipin altısı da** `_PHASE_LOOP_MODULES` içinde → adaptör nereye konursa konsun
> importer kapısı tepki verir ve **allowlist genişletmesi bir İNSAN incelemesidir**
> (`docs/audit/closure_e4_adapter_precondition_measurement_2026-08-17.md`).
> **`C2` de insan kapısında:** `G9` + `G13` imzasız.

> **PR B (= plandaki `C2`→`C4` zinciri) HÂLÂ ADR §16 KAPISININ ARKASINDA ve kapı artık İKİYE
> bölünmüş durumda:** **G9** `C2`'den önce (`settle`/`finalize`/P10/`iter_portfolio` ADR §6/§8'i
> değiştirir), **G10** `C9`'dan önce (bayrak + bump). **`C1` (E4a) hiçbir ADR kapısı istemedi** —
> saf refactor, sevk edilmiş hiçbir sayıyı değiştirmedi, kapısı yalnızca 50 digest'in
> kıpırdamamasıydı ve kıpırdamadı (#735).
> Aşağıdaki ADIM 59 ölçümü geçerliliğini korur: (a) engeli kapalı; **kalan tek engel (b)** üç
> fazın book etmesiydi — **`C1` onu tarif/book olarak ikiye ayırdı**, dolayısıyla (b) artık
> `ItemParticipant` adaptörünün yazılabilirliği sorusudur, ifade edilebilirliği değil.
> #731 bu ön koşulları ölçtü ve adaptörün **hâlâ** `C2` + G9/G13 + importer-allowlist kararına
> bağlı olduğunu kaydetti.

> **ADIM 59 bunu ölçtü ve KAPSAMINI DARALTTI, kapıyı açmadı:** §4.1'in **(a)** engeli
> (faz-bölünmüş bar) **KAPALI** — `_ItemStepper` `engine.py:756`, `E(t)` girişi
> `_phase_entry(bar, *, equity)` `engine.py:2448`. **Kalan tek engel (b):** üç faz book
> eder, `ItemParticipant` tarif ister. Bu `run_engine`'in bar gövdesine dokunur →
> **ADR §16 insan kapısı + ADR amendment'ı** gerekir. **Ondan önce başlanmaz.**
> Ayrıntı, seam sıralaması ve tripwire tasarımı:
> `docs/audit/closure_w0_shared_portfolio_2026-08-13.md`.

> **ADIM 83 (2026-08-19) bunu DEĞİŞTİRMEDİ** — kabul borcu partisi, motor eksenine dokunmadı.
> İki hattın **ölçülmüş** sıradaki adımı: mühendislik hattında **`C3`**
> (`execution/participant.py` adaptörü; importer-allowlist kararı #761'de **imzalandı**,
> Seçenek A, negatif kontrol zorunlu), kabul-borcu hattında bir **doc 18 FRONTEND** partisi
> (tek açık satır `AL-06.c3`). İkisi de **bağımsızdır** ve ikisi de PR B'yi açmaz.

> **ADIM 38, 39, 40, 41, 45, 46, 47 ve 48 bunu DEĞİŞTİRMEDİ** — hepsi test/kapı/belge
> ya da sunum slice'ıydı, motor eksenine dokunmadı. **P8-B2'nin PO yarısı ADIM 47'de KAPANDI**
> (`../validate` + `../baseline-parse` → 202); **`validation-runs` 201'de KALDI** ve o
> ayrışma **açık**. **P11-1 ADIM 49'da KAPANDI** — ruleset `20765617` aktif, 16 required
> check doğrulandı; artık RC §6.7 kalanları arasında **değil**. RC §6.7'de kalanlar:
> **P11-6b**, **P11-3b**, **P8-B3b**, **P4-3**, **P10-B6**, **P1-Gate3**, **P10-B3/B4/B5**.
> **P1-Gate3 ADIM 48'de İŞLENMEYE BAŞLANDI ama KAPANMADI** (8 kriter kapandı, 126 açık).
> Paste-ready resume prompt: `docs/ADIM48_LANDED_KICKOFF.md` en altta.

**Kapsam daraldı ama kapı açılmadı.** ADIM 35 §4.1'in **(c)** engelini kapattı: projeksiyon artık
var, `execution/portfolio_projection.py::project_portfolio_run`. **ADIM 58 (a)'yı ölçtü ve KAPALI
buldu** — `_ItemStepper` (`engine.py:756`) barı zaten fazlara bölünmüş sevk ediyor ve `E(t)` girişi
`_phase_entry(bar, *, equity)` (`engine.py:2448`) olarak mevcut (PR #602'den beri). **Kalan tek
engel (b):** `carry`/`held`/`entry` **book eder**, `ItemParticipant` ise arbitrasyon öncesi
**tarif** ister (`CarryCharges` / `MandatoryExit` / `ItemIntent`). Bu `run_engine`'in bar
gövdesine dokunur ve **ADR §16 insan kapısı + bir ADR amendment'ı** gerektirir. Bu kapıdan
geçmeden (b)'ye başlanmaz.

`run_portfolio` **ve** `project_portfolio_run` üretimde **çağrısız**:
`jobs/backtest_engine.py:299` item döngüsü, `:364` `combine_item_runs`,
`SHARED_ALLOCATION_STATUS = future_dev` (containment KAPALI). ADIM 20 matrisindeki satırların
kalanı bu boşluk kapanmadan kapanamaz; **A4 ve A18 artık ölçülebilir ama ADIM 20'yi tek başına
açmaz**. Ayrıntı ve tasarım işaretleri: `docs/ADIM35_LANDED_KICKOFF.md` (paste-ready resume prompt
en altta), `docs/ADIM16_STEPPER_LANDED_KICKOFF.md` §4.1 ve `docs/ADIM26_KICKOFF.md`.

**A-08 ayrı bir eksendedir ve PR B'yi bloklamaz.** İnsan denetimi **BAŞLADI ama BİTMEDİ**
(ADIM 56, SR-2 oturum 1): iskele hazır (`scripts/a11y-audit-stack.sh up && … validate`),
defter artık boş değil ama **2/184** hücre, **0/10** akış, **SR-1 hiç başlamadı**, çıkış
kriterleri **0/4**. **#514 bugün AÇIK** —
2026-08-12T11:08:58Z'de insan eliyle yeniden açıldı, yani yukarıdaki iki yoldan **(B)
gerçekleşti** ve ADIM 29'un kaydettiği ayrışma **ADIM 48'de kapandı**; kanonik blok
`docs/audit/a11y_screen_reader_audit_results.md` §STATUS ▸ *Tracking-issue state*. Kalan iş
**insana** düşer ve artık tek kalemdir: **denetimin kendisi** (imzalı kalıcı sapma yolu
seçilmedi). **A-08 için
hiçbir belgeye `Complete`/`PASS`/`Done` yazma** — ama artık "açık issue #514'te
izleniyor" **yazılabilir**, çünkü doğrudur.

> **ADIM 108 GÜNCELLEMESİ (2026-08-25) — BAŞLIK YİNE DEĞİŞTİRİLMEDİ, GÖVDE GÜNCELLENDİ.**
> (Gerekçe ADIM 81/85/86/92 güncellemelerinde: `docs-history-guard` `^-## ` desenine bakar, bir
> `## ` başlığını yeniden yazmak ona **kayıt silme** gibi görünür — ADIM 61 emsali, ADIM 85'te
> kapı **fiilen** kırmızı verdi. Kural artık ölçülmüş: *başlığa dokunma, düzeltmeyi gövdeye yaz.*)
>
> **BU BAŞLIĞIN İKİ İŞİ DE İNMİŞ DURUMDA VE ADIM 108 ONU İLERLETMEDİ** — bu slice bir **defterdir**
> (kayıtsız inen #822'nin ritüeli, a11y precheck advisory prozası). `C`-hattına, motora, containment'a
> **hiç dokunmadı**: `SHARED_ALLOCATION_STATUS` `future_dev`, `ENGINE_VERSION` sabit, `backend/src`'te
> sıfır satır. **Bu başlık altında yeni bir dal AÇILMAMALIDIR** (ADIM 92'nin kaydı geçerli).
>
> **`C6`'nın ön koşulları DEĞİŞMEDİ: `G11` (P2) ve `G12` (P8), ikisi de İMZASIZ.** Brifingli ≠ imzalı.
> **İmzasız bir kapının arkasındaki slice'a BAŞLAMA.**
>
> **ADIM 108'in devrettiği iki ölçülmüş kalem — ikisi de KOD DEĞİL, birer TUZAK:**
> (1) **`npm run typecheck` `frontend/e2e/`'yi kapsamaz** (`frontend/tsconfig.json` `"include": ["src"]`);
> o ağacın gerçek kapısı `npx tsc --noEmit -p e2e/tsconfig.json` — `e2e/` düzenleyen bir sonraki slice
> yeşil bir `typecheck` gördüğünde dosyasının kapsandığını **sanmasın**.
> (2) **`20-a11y-prechecks.spec.ts`'te İKİ advisory dalı bugün ULAŞILAMAZ** (skip link / K-2 ve
> `<h1>`-yok / K-4 — ikisini de PR #685 kapattı). **Bilerek tutuluyorlar, REGRESYON TRIPWIRE'ı olarak**;
> notları bunu yazıyor. Geçtikleri için silme — geri gelişlerini fark edecek tek şey onlar.
>
> **KAYITSIZ İNEN SLICE SAYIMI: #820 hâlâ kayıtsız.** ADIM 108 onun kaydını **uydurmadı** (ADIM 97
> emsali); §6.1b'yi ilk yazan — yani ADIM 108'in kapattığı bulguyu **açan** — odur ve kaydını
> **sahibi** yazmalıdır. Bu hattın diğer kayıtsız satırlarını **present-tense okuma, ÖLÇ.**
