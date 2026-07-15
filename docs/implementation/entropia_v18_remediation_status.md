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
| F-01 | Real Market Data file upload | P0 | Not Started | Upload still via pre-supplied object key (no native chooser / byte transfer). |
| F-02 | Real Research Data file upload | P0 | Not Started | Same object-key workflow as F-01. |
| F-03 | Replace simulated file inputs | P0 | Not Started | TXT/CSV textareas + manual filename entry still present. |
| F-04 | Execute full Mainboard composition | P0 | Not Started | Engine selects first enabled strategy path; multi-item execution unverified. |
| F-05 | Apply date range + instrument to engine | P0 | Not Started | `backtest_range`/instrument filtering to bar stream unverified. |
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
| F-22 | Production authentication profile | P0 | Not Started | CONFIRMED: `AUTH_MODE` defaults `dev` / trusts `X-Actor-Id` (settings.py:76). |
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

- 2026-07-14 — F-09 fail-closed sizing (engine + Ready Check blocker) + F-24 sizing-test rewrite.
  Branch `feat/v18-f09-sizing-fail-closed`. `ENGINE_VERSION → backtest-engine-v2-sizing-fail-closed`.
- 2026-07-15 — F-06 remove unresolved-indicator breakout fallback. Worker fails closed with
  `RUN_FAILED_UNRESOLVED_DEPENDENCY` (proxy unreachable in production); Ready Check adds the upfront
  `STRATEGY_INDICATOR_UNRESOLVED` blocker. No migration, no ENGINE_VERSION bump. Branch
  `feat/v18-f06-remove-breakout-proxy`.
