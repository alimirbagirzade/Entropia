# Stage R3 — 22-Jul Deep-Audit Remediation · Kickoff & Resume

> **Slice source:** `docs/spec/Entropia_V18_Current_UI_vs_Prototype_Deep_Audit_Claude_Code_Remediation.md`
> (47 findings). **PO sign-off:** `docs/implementation/v18_final_acceptance.md §4/§4.1`
> (D-1…D-9, recorded 2026-07-22). **Disposition map (the "same topic" guard):**
> `docs/implementation/v18_visual_traceability.md §2`.
>
> STALE-BY-DEFAULT — run the Session START verification before trusting anything here.

## Where we are (R3 W1 + W2 landed / in-flight)

| Slice | Findings | PR | State |
|---|---|---|---|
| Wave-1 | M-12 · A-01 · F-08 · A-04 traceability + PO D-1…D-9 sign-off | #367 | merged |
| W2a | D-7b (partial contrast) · D-8 (in-text link underline) | #368 | merged |
| W2b | D-2 (Create Package enum → human labels) | #369 | merged |
| D-3 | P-04 (Create Package dominant source compose area) | #370 | merged |
| W2c | D-6 (compact TS/TL inline panel — registry → standalone) | #371 | open (green) |
| W2d | P-10 (Research Data registry-first) + E2E fix | #372 | open (E2E green, backend pending) |
| W2e | D-5 (Results History collapsed metric digest) | #373 | open (green) |

**All frontend D/P-items are done.** The PO signed D-1/D-9 (accept) and
D-2/D-3/D-4/D-5/D-6/D-8 (FIX) + D-7b (partial contrast). D-2/3/5/6/7b/8 are now
delivered; **D-4 is the last unfinished signed FIX** and needs a backend projection.

## Remaining R3 backlog (backend-heavy — the next session's work)

1. **D-4** — Portfolio human labels. `Portfolio.tsx` renders `composition_item_id`
   / `workspace_id` (`mbi_…`) as primary labels. Extend the allocation projection
   with display labels + revision summaries; keep IDs as binding keys only
   (audit P-11 / F-07: never reconstruct names from IDs in the browser).
2. **P-05** — Create Package persist. "Compatible family" + "Explicit indicator
   link" are visible but "not yet sent to the backend (V1)" (`CreatePackage.tsx`).
   Extend the request schema + command path (or disable with a build-boundary label).
3. **P-06** — Package Library Market/Timeframe facets. `Library.tsx` says they are
   "absent by design". Add market/timeframe scope to the catalog DTO + indexed
   query filters; `System/Not applicable` for embedded_system.
4. **P-09** — Market Data registry columns. Add Source/Coverage/Resolution to the
   list projection; map `ohlcv` → `OHLCV`.
5. **P-14** — Panel Logs backtest-log primary view. Add a server-side admin
   backtest-log projection (User/Date/Backtest/Net/ROMAD/Trades) as the first
   view; keep the event/audit stream as a secondary technical tab.
6. **W3 backend truth:**
   - **F-01** real worker lifecycle for `_enqueue_stub_job` (`create_package.py` —
     currently completes in-transaction; route advertised-async work through real workers).
   - **F-04** breakout-proxy cleanup (`domain/backtest/engine.py` — remove/fence
     `deterministic_bar_breakout_proxy_v1` from production paths).
   - **F-05 / M-05** machine-readable capability matrix (UI ↔ Ready Check ↔ engine parity).
   - **F-07** raw-id presentation sweep residuals.
   - **F-09** README / status honesty rewrite.
7. **Kova 2 — recorded honest boundaries (NOT signed, stay open):** A-06 (10-page
   deep visual compare: 03/07/09/10/12/17/18/19/21/22) · A-08 (NVDA/VoiceOver
   manual a11y) · F-02 (NL generation Future-Dev) · F-03 (unified-clock portfolio)
   · P-13/F-06 (ResultDetail charts + AI Review).

## Working-loop method (mandatory)

- **Empirically verify every finding first** — the audit is often already
  addressed by earlier waves (M-01/M-10 hierarchy, P-04 layout, P-10 registry were
  ~mostly done; only a narrow residual remained). Do NOT re-do closed work.
- One slice → one branch off **current** main → one PR (`base=main`). The owner
  merges quickly, so branch fresh each time (no stacking needed).
- **Backend verify (every backend slice):**
  `cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest --no-cov -q`
  + an **L1 FK insert-order proof for every new `create_*`** + **alembic `<n>` up/down/up**
  (`LC_ALL=en_US.UTF-8`, `DROP SCHEMA public CASCADE; CREATE SCHEMA public;` first)
  + migration↔model column parity. Local Postgres on **:5432** (`entropia`/`entropia`).
- **Frontend verify:** `tsc --noEmit` · `eslint` · `vitest run` · `npm run build`.
  A broken test is realigned to the NEW markup (option values + OCC/Idempotency
  assertions unchanged; only visible labels / container scope).
- **GateGuard:** NEW files via Bash heredoc → gate-free; an EDIT to an existing
  file triggers the 4-fact preamble (importers / affected public API / data schema
  / user request verbatim) → retry.
- **Never touch** route paths, react-query keys, OCC tokens (If-Match /
  `expected_*_version` / `X-*-Version`), Idempotency-Key, SSE taxonomy, hooks, or
  `lib/*.ts` data logic when doing presentation work.

## Paste-ready resume prompt

```
Entropia V18 — R3 remediation dalgasına DEVAM. Frontend D/P-item'ları bitti
(PR #367-373). Şimdi backend-ağırlıklı kalanlar.

1) ÖNCE doğrula: git fetch; gh pr list --state all -L 8; #371/#372/#373
   merged mi? origin/main HEAD + alembic head'i teyit et.
2) OKU (authority order): docs/STAGE_R3_KICKOFF.md, sonra
   docs/implementation/v18_visual_traceability.md §2 (47-bulgu → disposition —
   "aynı konu" guard) + v18_final_acceptance.md §4.1 (PO imzaları:
   D-2/3/4/5/6/8 FIX, D-7b, D-1/D-9 kabul).
3) Sıradaki slice: D-4 (Portfolio mbi_ ULID → human label; allocation
   projection'a display label ekle). Sonra P-05, P-06, P-09, P-14, sonra
   W3 (F-01/F-04/F-05/F-07/F-09).
4) Her slice: kendi branch'i (güncel main'den) + ayrı PR (base=main) +
   tam backend verify (ruff/mypy/pytest + FK insert-order proof + alembic
   up/down/up) + frontend verify. GateGuard: edit'te 4-fact, yeni dosya
   heredoc. Audit bulgusunu ÖNCE empirik doğrula (çoğu zaten çözülmüş).
5) Local Postgres :5432 hazır (entropia/entropia).
```
