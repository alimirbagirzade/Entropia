# Entropia V18 — Remediation Traceability

Mandated by `docs/spec/Entropia_V18_Claude_Code_Implementation_Spec.md` §3.2. One row per
requirement (F-01..F-25, UI-01..UI-22). **Status** ∈ {Not Started, In Progress, Blocked, Complete}.
A requirement is **Complete** only with working end-to-end behavior + passing acceptance tests
(§3.3) — never because a component/route/field exists.

> Ground truth verified against `origin/main` @ `0daa454` (PR #208) on 2026-07-14, not the
> loaded session handoff (stale-by-default per CLAUDE.md).

## Spec document-level errors found (the "hataları")

These are errors **in the spec document itself**, surfaced during review:

1. **§2 references `.docx` sources that ship as `.md`** — `Entropia_V18_Master_Technical_Reference`
   exists at `docs/spec/Entropia_V18_Master_Technical_Reference_v1_0.md` (not `.docx`). The 22 page
   specs are `.md` (`01_..._v1_1.md` … `22_..._v1_1.md`), present and correct.
2. **§2 lists `2.3. POSITION ENTRY LOGIC.docx` — MISSING** from `docs/spec/`. No equivalent present.
3. **§2 lists `Entropia_V18_..._Handoff_ve_Calisma_Standardi_v1_1.docx` — MISSING**. The only
   `.docx` present is `Coder_AI_Asamali_Kodlama_Prompt_Set_v1_0.docx` (not the one §2 names).
4. **§2 "V18 prototype HTML"** = `docs/spec/index_guncellenmis_duzeltilmis_v18.html` (present; name
   differs from the generic reference).
5. The spec's own §3.2 traceability file (`docs/implementation/...`) **did not exist** until this
   file — created as the first Phase-0 deliverable.

Otherwise the spec's technical "broken" claims are **accurate, not errors** (verified below).

## Status table

| ID | Title | P | Status | Verified finding / evidence |
|----|-------|---|--------|------------------------------|
| **F-01** | **Real Market Data file upload** | **P0** | **Complete (this PR)** | Fixed: `start_market_raw_upload` (`application/commands/market_data.py`) now accepts real bytes via a multipart `POST /market-datasets/{entity_id}/raw-uploads` (`UploadFile`), never a pre-supplied `object_key`/`content_digest`/`size_bytes`; object key + SHA-256 digest + byte size + content type are all derived server-side, written via `datasets.put_raw_bytes`, and integrity-verified with a storage read-back before any evidence row is persisted (`MARKET_DATA_UPLOAD_INTEGRITY_FAILED` on mismatch). Content-addressed dedup (`find_raw_asset_by_hash`, scoped per dataset) makes a retry idempotent regardless of Idempotency-Key. Unsupported type/empty/oversized file -> `MARKET_DATA_FILE_TYPE_NOT_ALLOWED`/`VALIDATION_ERROR`/`MARKET_DATA_FILE_TOO_LARGE`; storage failure -> `MARKET_DATA_UPLOAD_STORAGE_FAILED`. Frontend: `frontend/src/lib/upload.ts` — new shared XHR-based multipart primitive (`uploadFile` + `useFileUpload` hook, real progress/cancel/retry) reused by `MarketData.tsx`'s `UploadComposer`, which replaces the manual object-key/digest/size-bytes form with a native file chooser; no storage metadata is ever requested from the user. No migration (`market_raw_asset.object_key`/`content_digest`/`size_bytes` columns already existed). Tests: +5 backend unit (validators), +7 backend integration (happy path, dedup, unsupported type, non-owner, storage failure, digest mismatch), +2 backend contract (pure-validation-before-DB), +3 frontend unit (`upload.test.ts` — progress/error/cancel), +2 frontend component (success+finalize, error+retry). A Playwright E2E extension of `frontend/e2e/specs/02-market-data-upload.spec.ts` is authored and held on a reference branch pending F-23's merge to `main` (that directory does not exist on `main` yet). |
| F-02 | Real Research Data file upload | P0 | Not Started | Same object-key workflow as F-01. |
| F-03 | Replace simulated file inputs | P0 | Not Started | TXT/CSV textareas + manual filename entry still present. |
| **F-04** | **Execute full Mainboard composition** | **P0** | **Complete (this PR)** | CONFIRMED gap: `jobs/backtest_engine.py::_resolve_primary_strategy` ran ONLY the first enabled Strategy — a two-strategy Mainboard silently dropped one. Fixed: `_resolve_enabled_strategies` resolves EVERY enabled Strategy in the immutable snapshot (manifest pin order — doc 01 §5.2 presentation `position` is explicitly NOT engine priority), `_prepare_and_run_strategy` runs each over its own pinned market revision / F-05 range+instrument filter / F-06 indicator plan / allocation sleeve, and a new pure `domain/backtest/engine.py::combine_item_runs` composes them into ONE portfolio result: net_profit additive, trades+decision events concatenated+re-sequenced+tagged with their originating `item_id`, portfolio equity curve built in deterministic pin order. Every participating revision stays pinned in the manifest; each object's contribution is traceable in `diagnostics.composition.items` (per-item net_profit / trade seq-range / executed flag) + the item-tagged decision trace. A selected Strategy that fails to resolve fails the WHOLE run (never silently dropped — F-04/F-06). Enabled Trading Signal / Trade Log items are pinned + recorded as participating-but-non-executing (their V1 execution effect is defined only as a Strategy data input — honest boundary, surfaced not faked). Disabled items excluded (doc 01 §5.2). A lone enabled Strategy stays byte-identical (worker skips the compose step). `ENGINE_VERSION → backtest-engine-v3-full-composition` (execution_key namespace shift, INF-04/05). No migration (per-item traceability rides `diagnostics` JSON). F-24: +2 integration (`test_backtest_persistence.py`: two-strategy runs both + composes one result with 20000 pooled independent capital; disabled-item exclusion collapses to a 10000 single-strategy result) + 3 unit (`test_backtest_engine.py`: sum/union + item-tagged trace, order-invariant net_profit, non-executing TS recorded without contribution). Honest boundary: the composite portfolio equity curve concatenates each strategy's realized-PnL progression in deterministic pin order — a genuine unified-clock multi-item co-simulation across heterogeneous bar sources stays deferred (surfaced as the L4 `portfolio_curve_sequential_not_unified_clock` diagnostic, never hidden). |
| **F-05** | **Apply date range + instrument to engine** | **P0** | **Complete (this PR)** | Fixed: worker (`jobs/backtest_engine.py`) parses+validates `backtest_range` (invalid/unparseable ISO → `RUN_FAILED_INVALID_BACKTEST_RANGE`), physically filters the bar stream via `application/queries/market_bars.py::filter_bars_by_range` (inclusive `[start,end]`, UTC-normalized, drops unparseable-timestamp rows, never yields empty batches) BEFORE the engine ever sees a bar, and cross-checks the pinned market revision's dataset-level `instrument_id` (GAP-16) against the strategy's selected instrument (a real mismatch → `RUN_FAILED_INSTRUMENT_MISMATCH`; an unset/legacy revision instrument_id is honestly passed through — no per-row instrument column exists in the current single-instrument-per-revision ingestion schema, confirmed empirically via `schema_mapping.py`/`_normalize`). A filtered stream with zero bars → explicit `RUN_FAILED_EMPTY_FILTERED_RANGE` (fail-closed, never a "succeeded" empty result). `domain/backtest/engine.py::run_engine` now surfaces the ACTUAL first/last processed bar timestamps as `summary["period_start"/"period_end"]`; `bt_repo.create_result` persists them (was hardcoded `None`) — manifest range now provably matches the data actually processed (spec acceptance). `ENGINE_VERSION → backtest-engine-v2-range-instrument-filter` (execution_key namespace shift, INF-04/05 — a stale unfiltered result is never reused). 3 new `RunFailureCode` members (additive). +8 unit (`test_market_bars_range_filter.py`, DB-free pure filter/parse coverage) + 7 integration (`test_backtest_persistence.py`: period_start/end match processed bars, narrower range processes fewer bars → 0 trades [proves the filter is physical, not cosmetic], empty-filtered-range reject, unparseable-range reject, instrument-mismatch reject, matching-instrument regression) + 1 literal-version fixup in `test_backtest_engine.py`. No migration (`backtest_range`/`instrument_id` already existed in config/schema). Honest boundary: row-level multi-instrument filtering is architecturally moot today — `MarketDatasetRevision.instrument_id` is a dataset-level field (GAP-16 resolves Instrument Scope once at dataset setup) and the canonical OHLCV Parquet schema carries no per-row instrument column (`schema_mapping.py::_ESSENTIAL_SYNONYMS` has none); true multi-instrument raw ingestion is F-01/F-02/F-03 territory (a different swimlane) and would need to land first for a per-row filter to have anything to filter. |
| **F-06** | **Remove unresolved-indicator breakout fallback** | **P0** | **Complete (this PR)** | Fixed: worker (`jobs/backtest_engine.py`) resolves the indicator plan while PROVISIONING and fails closed with `RUN_FAILED_UNRESOLVED_DEPENDENCY` when `not plan.has_entry or plan.unresolved` — the breakout proxy is now structurally unreachable on the production path. Upfront RUN gate: Ready Check emits `STRATEGY_INDICATOR_UNRESOLVED` blocker (`readiness_check._resolve_strategy_indicator_issues`), so admission (`request_backtest_run` → nested Ready Check) refuses to queue. `run_engine`'s proxy retained only as a domain unit-test primitive (24 fixtures intact). No migration, no ENGINE_VERSION bump (determinism unchanged; proxy just unreachable). Tests: +2 integration (admission-blocked + worker defence-in-depth) + 1 validator unit; proxy-reliant fixtures (`test_backtest_persistence`, `test_e2e_agent_loop`, `test_readiness_persistence`, `test_gateway_parity`) reseeded with a resolvable `ta.sma` package. |
| F-07 | Execute every saved Strategy setting | P0 | Not Started | Limit orders/partial fills/timing/scaling/etc. not engine-executed. |
| F-08 | Logic-Based Stop end to end | P0 | Not Started | `logic_blocks` / stop-combination schema absent. |
| **F-09** | **Fail closed for unsupported sizing** | **P0** | **In Progress (this PR)** | CONFIRMED gap: unsupported sizing fell back to all-in notional (engine.py). Fixed: engine `_open` fail-closed + Ready Check `STRATEGY_SIZING_UNSUPPORTED` blocker + tests rewritten (F-24 for sizing). |
| F-10 | Complete decision trace | P1 | Not Started | Trace limited to entry_signal + aggregated filtered_no_entry. |
| F-11 | Use Research Data + Funding in engine | P0 | Not Started | Stored as provenance only; available-time joins / funding cost unapplied. |
| F-12 | Create Package frontend lifecycle | P0 | Not Started | Not all backend transitions wired to UI. |
| F-13 | Execute every required package validation | P0 | Not Started | `not_executed` not treated as fail; real checks absent. |
| F-14 | Real candidate/package generation | P1 | Not Started | V1 stub emits manifest/hash only (no loadable implementation). |
| F-15 | Replace Mainboard JSON editor | P0 | Not Started | Generic add-work-object/raw-JSON still in normal flow. |
| F-16 | Bind RUN to real readiness | P0 | Not Started | RUN lock/authorization parity unverified. |
| F-17 | Headline metrics on Mainboard | P1 | Not Started | headline projection not consumed inline. |
| F-18 | Durable/discoverable Strategy drafts | P1 | Not Started | Depends on `?draft=` URL; no unattached-draft listing. |
| F-19 | Remove infra IDs/JSON from Strategy Details | P1 | Not Started | Root/revision/hash entry still user-facing. |
| F-20 | Real autonomous Alpha Agent executor | P1 | Not Started | No durable QUEUED-task executor loop. |
| F-21 | Real Trash re-authentication | P0 | Not Started | CONFIRMED: any non-empty string accepted (deletion.py:530). Needs real IdP verify (infra-gated). |
| **F-22** | **Production authentication profile** | **P0** | **In Progress (this PR) — blocked-needs-stack for full E2E** | CONFIRMED gap: `AUTH_MODE` defaulted `dev` with no guard against `ENTROPIA_ENV=staging\|production` also running `dev` (client-controlled `X-Actor-Id` trusted outright in that combination). Fixed at the config layer: `Settings._restrict_dev_auth_to_local` (pydantic `model_validator`, fail-closed) now REFUSES to construct — i.e. the app refuses to start — whenever `ENTROPIA_ENV != local` and `AUTH_MODE == dev`; `dev` is now structurally restricted to the named local profile. `AUTH_MODE=session` (real argon2id login + opaque Bearer session, fresh server-resolved role every request, bare `X-Actor-Id` ignored — PR #38 local auth, unchanged) remains the only auth mode staging/production can run. Proven empirically: 8 new unit tests (`tests/unit/test_settings.py`, all env×mode combinations) + a new production-*profile* integration test (`tests/integration/test_auth.py::test_production_profile_rejects_bare_actor_header_impersonation`, `ENTROPIA_ENV=production` + `AUTH_MODE=session`, not just the mode in isolation) proving a bare `X-Actor-Id` header resolves to an anonymous actor and a mismatched header on a valid Bearer session is ignored. **Honest boundary — NOT claimed Complete:** the full E2E acceptance (real login/logout/session-expiration/role-denial/audit against the running Docker stack + IdP) is `blocked-needs-stack` on this machine (no Docker available this session, per CLAUDE.md environment boundary) — deferred to F-23's Playwright-against-Docker suite. |
| F-23 | Real browser E2E suite | P0 | Not Started | No Playwright suite against the Docker stack. |
| F-24 | Replace tests approving incorrect behavior | P0 | In Progress | Sizing all-in tests rewritten to fail-closed with F-09 (#209). Breakout-fallback tests done with F-06: proxy-reliant fixtures reseeded with resolvable packages + fail-closed worker/admission tests added. Remaining incorrect-behavior tests tracked per future slice. |
| F-25 | Truthful README/status | P3 | Not Started | README claims "Production V1 complete"; contradicts this backlog. |
| UI-01..UI-22 | Page-by-page UI remediation | P0–P2 | Not Started | Inline Mainboard editor model, real uploads, prototype parity. Frontend track. |

## Environment boundaries (this headless session)

- Backend unit + DB-backed integration tests **run** here (Postgres :5432, isolated `TEST_DATABASE_URL`).
- **Cannot fully exercise:** F-22 production auth E2E, F-23 Playwright-against-Docker, F-21 real IdP
  re-auth — these need the running Docker stack / identity provider. They are marked Not Started and
  must not be claimed Complete from unit tests alone (§ "Prohibited completion claims").

## Change log

- 2026-07-15 — F-01 real Market Data raw-asset file upload. `POST /market-datasets/{id}/raw-uploads`
  now transfers real multipart bytes; object key/digest/size/content-type all server-derived +
  integrity-verified via a storage read-back before persisting; content-addressed dedup makes retry
  idempotent. New shared `frontend/src/lib/upload.ts` (XHR multipart + progress/cancel/retry) reused
  by `MarketData.tsx`'s native file-chooser UploadComposer. No migration. Branch
  `feat/v18-f01-market-data-upload`.
- 2026-07-14 — F-09 fail-closed sizing (engine + Ready Check blocker) + F-24 sizing-test rewrite.
  Branch `feat/v18-f09-sizing-fail-closed`. `ENGINE_VERSION → backtest-engine-v2-sizing-fail-closed`.
- 2026-07-15 — F-04 execute the complete Mainboard composition. Worker runs EVERY enabled Strategy (`_resolve_enabled_strategies` + `_prepare_and_run_strategy`) and composes them into one portfolio result via the pure `combine_item_runs`; per-item contribution traceable in `diagnostics.composition`; single-strategy path byte-identical. `ENGINE_VERSION → backtest-engine-v3-full-composition`. No migration. Branch `feat/v18-f04-full-composition`.
- 2026-07-15 — F-06 remove unresolved-indicator breakout fallback. Worker fails closed with
  `RUN_FAILED_UNRESOLVED_DEPENDENCY` (proxy unreachable in production); Ready Check adds the upfront
  `STRATEGY_INDICATOR_UNRESOLVED` blocker. No migration, no ENGINE_VERSION bump. Branch
  `feat/v18-f06-remove-breakout-proxy`.

