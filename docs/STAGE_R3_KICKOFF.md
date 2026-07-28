# Stage R3 — 22-Jul Deep-Audit Remediation · Kickoff & Resume

> # ⛔ SUPERSEDED (2026-07-28) — R3 MÜHENDİSLİK BACKLOG'U KAPANDI
>
> **Bu dosyayı iş listesi olarak KULLANMA.** Aşağıdaki "Remaining R3 backlog" bölümü
> **2026-07-22** tarihli durumu anlatıyor; o günden beri listelenen kalemlerin **tamamı** merge
> oldu. Bu doküman authority order'da 1. sırada okunduğu için, tazelenmemiş hâli **bitmiş işi
> yeniden yaptırma riski** taşıyordu (DOC-01/02/03 + I-06 denetimi bulgusu).
>
> **Ampirik doğrulama (2026-07-28, `gh pr view <n> --json state`):**
>
> | Madde | PR | Durum |
> |---|---|---|
> | D-4 — Portfolio human labels | #375 | **MERGED** |
> | P-05 — Create Package persist (compatible family + indicator link) | #376 | **MERGED** |
> | P-06 — Package Library Market/Timeframe facets | #377 | **MERGED** |
> | P-14 — Panel Logs backtest-log primary view | #378 | **MERGED** |
> | P-09 — Market Data registry columns | #379 | **MERGED** |
> | F-07 — raw-id presentation sweep | #404 | **MERGED** — yalnız §4.4 backend-DTO kalıntısı açık |
>
> W1/W2 dalgasının tamamı da merged: #367 · #368 · #369 · #370 · **#371 · #372 · #373**
> — aşağıdaki tabloda son üçü hâlâ "open (green)" yazıyor, **bayat**.
>
> **Şu an geçerli durum ve sıradaki iş:** `CLAUDE.md` §Current position + §Next, ve
> `docs/STAGE2_HANDOFF.md` §Next. Bu dosya bundan sonra **tarihsel kayıt**.
>
> Aşağıdaki **"Working-loop method" bölümü hâlâ geçerlidir** (empirically-verify-first, verify
> komutları, GateGuard, never-touch listesi) — bayat olan yalnızca iş listesidir. Ayrıca
> §"Paste-ready resume prompt" içindeki `0035_portfolio_rules` /
> `backtest-engine-v18-capability-matrix` beklentileri de bayattır (bkz. o bölümdeki not).

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
| W2c | D-6 (compact TS/TL inline panel — registry → standalone) | #371 | ~~open (green)~~ → **merged** |
| W2d | P-10 (Research Data registry-first) + E2E fix | #372 | ~~open~~ → **merged** |
| W2e | D-5 (Results History collapsed metric digest) | #373 | ~~open (green)~~ → **merged** |

**All frontend D/P-items are done.** The PO signed D-1/D-9 (accept) and
D-2/D-3/D-4/D-5/D-6/D-8 (FIX) + D-7b (partial contrast). D-2/3/5/6/7b/8 are now
delivered; **D-4 is the last unfinished signed FIX** and needs a backend projection.

## ~~Remaining R3 backlog~~ — HEPSİ LANDED (tarihsel; 2026-07-28 doğrulaması)

> **Bu bölümdeki 1–5. maddeler ARTIK AÇIK İŞ DEĞİLDİR** (#375/#376/#377/#378/#379 merged).
> Metin, her maddenin kapsamının ne olduğunu göstermek için **olduğu gibi** bırakıldı — çünkü
> landed slice'ların reuse anchor'larını tarif ediyor. Yeni iş için buraya değil `CLAUDE.md`
> §Next'e bak.

1. **D-4** — ✅ **LANDED (PR #375).** Portfolio human labels. `Portfolio.tsx` renders `composition_item_id`
   / `workspace_id` (`mbi_…`) as primary labels. Extend the allocation projection
   with display labels + revision summaries; keep IDs as binding keys only
   (audit P-11 / F-07: never reconstruct names from IDs in the browser).
2. **P-05** — ✅ **LANDED (PR #376).** Create Package persist. "Compatible family" + "Explicit indicator
   link" are visible but "not yet sent to the backend (V1)" (`CreatePackage.tsx`).
   Extend the request schema + command path (or disable with a build-boundary label).
3. **P-06** — ✅ **LANDED (PR #377).** Package Library Market/Timeframe facets. `Library.tsx` says they are
   "absent by design". Add market/timeframe scope to the catalog DTO + indexed
   query filters; `System/Not applicable` for embedded_system.
4. **P-09** — ✅ **LANDED (PR #379).** Market Data registry columns. Add Source/Coverage/Resolution to the
   list projection; map `ohlcv` → `OHLCV`.
5. **P-14** — ✅ **LANDED (PR #378).** Panel Logs backtest-log primary view. Add a server-side admin
   backtest-log projection (User/Date/Backtest/Net/ROMAD/Trades) as the first
   view; keep the event/audit stream as a secondary technical tab.
6. **W3 backend truth:**
   - ~~**F-01** real worker lifecycle for `_enqueue_stub_job`~~ — **DONE** (F-01a/b/c,
     PR #380/#382/#383: Pre-Check · candidate+validation · baseline-parse all on durable
     workers; `_enqueue_stub_job`/`_enqueue_completed_job` deleted).
   - ~~**F-04** breakout-proxy cleanup~~ — **DONE** (PR #381: `run_engine` raises
     `UnresolvedStrategyError` unless a resolved plan exists; the labelled breakout is
     reachable only via the test-only `builtin_breakout_fixture=True`).
   - ~~**F-05 / M-05** machine-readable capability matrix~~ — **DONE** (this slice):
     `domain/backtest/capabilities.py` is the ONE canonical table, per option **VALUE**
     (`active_v1` | `future_dev` + dependency note), consumed by the engine (fail-closed at
     the `_open` choke point), Ready Check (`STRATEGY_CAPABILITY_NOT_IN_BUILD` = "Not
     available in this build") and the Strategy editor (generated TS mirror →
     disabled + dependency note). **Reuse anchors:** `capabilities_are_modelled(config)`,
     `future_dev_selections(config)`, `option_status(field_path, value)`,
     `CAPABILITY_MATRIX`, `FUTURE_DEV_OPTIONS`; exporter
     `backend/tools/export_capability_matrix.py` → `frontend/src/lib/engineCapabilityMatrix.generated.ts`
     (`capabilityOption()` / `isFutureDev()`); `SelectField capabilityField` prop.
     **Adding a new option value to `config.py` now FAILS CI** until it is classified —
     `test_matrix_enumerates_every_schema_literal` asserts matrix ↔ schema `Literal` set
     equality (register a brand-new FIELD in that test's `_SCHEMA_FIELDS` map).
   - ~~**F-07** raw-id presentation sweep residuals — **still open**~~ → **SUNUM KATMANI
     LANDED (PR #404).** 31 dosyada 161 `*_id` render'ı tarandı; P-11/P-12/P-16 gerçekten
     landed (traceability 10/13/16 gerekçeleri bayattı → düzeltildi), Portfolio'da 2 kalıntı
     presentation-only düzeltildi. **Kalan 4 yüzey açık ve presentation-only DEĞİL** — backend
     display-DTO gerektiriyor: `docs/implementation/v18_visual_traceability.md §4.4`.
     Yani **F-07 bütün olarak Complete DEĞİL**, ama "önce empirik doğrula" adımı yapıldı.
   - ~~**F-09** README / status honesty rewrite~~ — **DONE** (landed with PR #381).
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

## Paste-ready resume prompt — ⛔ BAYAT, YAPIŞTIRMA

> **Bu blok 2026-07-22'de yazıldı ve artık yanlış yönlendirir** (2026-07-28 doğrulaması):
> beklenen `alembic head` **`0035_portfolio_rules` DEĞİL** → gerçek **`0038_backtest_run_event`**
> (38 migration); beklenen `ENGINE_VERSION`
> **`backtest-engine-v18-capability-matrix` DEĞİL** → gerçek
> **`backtest-engine-v18-funding-step-order`** (`domain/backtest/manifest.py:83`).
> Ayrıca 3. maddedeki "kalan iş" (F-07 + PO imzası) **artık kalan iş değil**: F-07 sunum
> katmanı #404 ile landed, PO imzası **2026-07-22'de atıldı**
> (`docs/implementation/v18_final_acceptance.md:155-169`).
> **Güncel resume prompt için `CLAUDE.md` §Next'e bak.** Aşağısı tarihsel kayıttır.

```
Entropia V18 — R3 remediation dalgasına DEVAM. Frontend D/P-item'ları bitti
(PR #367-373). Şimdi backend-ağırlıklı kalanlar.

1) ÖNCE doğrula: git fetch; gh pr list --state all -L 8; F-05 capability-matrix
   PR'ı merged mi? origin/main HEAD + alembic head'i teyit et
   (beklenen: 0035_portfolio_rules, ENGINE_VERSION=backtest-engine-v18-capability-matrix).
2) OKU (authority order): docs/STAGE_R3_KICKOFF.md, sonra
   docs/implementation/v18_visual_traceability.md §2 (47-bulgu → disposition —
   "aynı konu" guard) + v18_final_acceptance.md §4.1 (PO imzaları:
   D-2/3/4/5/6/8 FIX, D-7b, D-1/D-9 kabul).
3) R3 mühendislik backlog'u KAPANDI: D/P item'ları + F-01a/b/c + F-04 + F-05/M-05 + F-09
   landed. Kalan: (a) F-07 raw-id sweep — traceability "overlaps P-11/12/16" diyor,
   P-11/12/16 landed, o yüzden ÖNCE gerçekten kalıntı var mı empirik doğrula;
   (b) R2 product-owner imzası (kod işi değil, docs/STAGE2_HANDOFF.md §Next).
   Capability matrisine dokunacaksan: tek kaynak domain/backtest/capabilities.py,
   değişince `cd backend && uv run python tools/export_capability_matrix.py` ile
   TS aynasını yenile (parity testi byte eşitliği ister).
4) Her slice: kendi branch'i (güncel main'den) + ayrı PR (base=main) +
   tam backend verify (ruff/mypy/pytest + FK insert-order proof + alembic
   up/down/up) + frontend verify. GateGuard: edit'te 4-fact, yeni dosya
   heredoc. Audit bulgusunu ÖNCE empirik doğrula (çoğu zaten çözülmüş).
5) Local Postgres :5432 hazır (entropia/entropia).
```
