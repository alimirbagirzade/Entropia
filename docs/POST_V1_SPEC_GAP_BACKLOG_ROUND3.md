# Entropia — Post-V1 Spec-Gap Backlog, ROUND 3

> **Kaynak:** 2026-07-14, R1–R9 (PR #179–196) merge edildikten SONRA yapılan üçüncü
> kapsamlı spec-vs-implementation denetimi (7 paralel read-only ajan + inline ampirik
> grep doğrulama; her bulgu `file:line` kanıtlı). Kod tabanı = `main` @ `226ca92`,
> alembic head `0029_esp_validation_run` (lineer, tek head).
>
> **Sonuç:** Kalite kapılarının tamamı yeşil (backend ruff+format+mypy+pytest, frontend
> typecheck+lint+331 vitest). 22 spec dokümanının normatif gereksinimlerinin ezici
> çoğunluğu birebir uygulanmış ve iki önceki tur (GAP-01..23 + R1–R9) kapatılmış.
> Aşağıdaki 9 madde (S1–S9) + LOW listesi, kalan **cila katmanı** farklardır —
> hiçbiri çekirdek davranış sözleşmesini (OCC/Idempotency/audit/state machine) bozmaz.
>
> **Amaç:** Her bölüm ayrı bir sohbete **paste-ready** çalışma birimidir; ayrı `feat/…`
> branch + ayrı PR. Bu dosya fix DEĞİL, backlog'tur.

## Çalışma kuralları (ortak)
- Direct-author (Workflow yok), önceki slice desenini aynala (one-tx no-commit, `run_idempotent`,
  `session.refresh(with_for_update=True)`, `_audit_and_outbox`).
- Her CRITICAL/HIGH bulgusunu fix'ten önce ampirik doğrula.
- Backend verify: `cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest --no-cov -q`
  \+ migration varsa alembic up/down/up (`LC_ALL=en_US.UTF-8`, `DROP SCHEMA public CASCADE; CREATE SCHEMA public;`)
  \+ migration↔model parite. İzole DB: `TEST_DATABASE_URL=...entropia_<slug>`.
- Frontend verify: `cd frontend && npm run lint && npm run typecheck && npm run test && npm run build`.
- Git: `feat/<slug>`; commit `<type>(<slug>): <subject>`; **NO AI attribution**; PR aç → checks → self-merge yok, kullanıcıdan merge iste.

## Önerilen sıra (değer/maliyet)
S9 (ucuz, hazır fix taslağı) → S1 (correctness, para motoruna değiyor) → S8 (backend hazır, UI bağla) →
S4 (gateway parity) → S6 (TS/TL export) → S7 (history excerpt) → S2 (Pre-Check lexer) →
S3 (package import, epic) → S5 (strategy config derinliği, en büyük).

---

## S9 — Analysis Lab Pause/Stop onay modalı (doc 18 §6.1) 🟢
**Boyut:** Küçük (frontend-only, 1 dosya + test). **Öncelik:** İlk (ucuz, fix taslağı hazır).

**Doğrulanan durum:** `frontend/src/pages/AnalysisLab.tsx:175-204` Pause/Stop butonları
`pause.mutate(...)` / `stopRun.mutate(...)`'i doğrudan onClick'te çağırıyor; §6.1'in onay
metinleri hiç render edilmiyor. Doc 18 §13 açık: "V18'de confirm modalı yoktur…
Production'da explicit confirmation modalı zorunludur." OCC (If-Match row_version) ve
Admin server-side gate zaten uygulanmış — yalnız UI onay adımı eksik.

**Kapsam:** RuntimeCard'a `pendingConfirm: "pause"|"stop"|null` state'i; Pause/Stop
butonları önce onay bloğunu açar (repo deseni: Trash.tsx PurgeComposer / ResultsHistory
delete confirm — `window.confirm` DEĞİL). §6.1 metinleri VERBATIM. Confirm mevcut
mutation'ları değiştirmeden dispatch eder; Resume onaysız kalır. `runtime.row_version`
değişince pendingConfirm sıfırlanır (stale-409 yolu yeniden onay ister, §11).

**Verify:** vitest — Pause tıkla → onay metni görünür, POST atılmaz; Confirm → POST;
Cancel → hiçbir şey. Mevcut direct-POST assert'leri onay adımından geçirilir.

**Paste-ready prompt:**
```
Entropia — S9: Analysis Lab Pause/Stop onay modalı. Session START + git doğrulama. Oku:
docs/POST_V1_SPEC_GAP_BACKLOG_ROUND3.md S9, doc 18 §6.1/§8.4/§13, mevcut
pages/AnalysisLab.tsx:175-204 + test/analysisLab.test.tsx. Fix: pendingConfirm state +
inline iki-adım onay (Trash PurgeComposer deseni), §6.1 metinleri verbatim, mutation'lar
değişmez, row_version değişince onay sıfırlanır. +vitest (3 senaryo). Frontend verify.
feat/s9-lab-pause-stop-confirm, ayrı PR, NO AI attribution.
```

---

## S1 — Portfolio FX settlement-currency blocker (doc 13 §5.1) 🔴
**Boyut:** Orta (backend). **Öncelik:** Yüksek (correctness — para-boyutlandıran motora değiyor).

**Doğrulanan durum:** `domain/allocation/rules.py` yalnız `initial_capital.currency`
varlığını doğruluyor (~:130). Item settlement currency'si Base Currency'den farklı olduğunda
approved+pinned FX conversion dataset kontrolü YOK — `grep settlement|fx_ domain/allocation/`
= 0. Doc 13 §5.1 + §6.2 "Error - FX dependency" + §10.1 Dependency satırı: farklı para
biriminde FX dataset yoksa validation/Ready Check BLOCKER üretmeli.

**Kapsam:** Allocation validate + readiness path'ine settlement-currency cross-check:
item'ların (pinned market revision'dan türeyen) settlement currency'si base'den farklıysa
approved FX dataset çözümlemesi ara; yoksa BLOCKER issue (doc 13 §6.2 metni). Fail-closed.

**Verify:** integration — farklı-currency item + FX dataset yok → BLOCKER, validate PASSED
olamaz; FX dataset approved+pinned → geçer; aynı currency → check atlanır.

**Paste-ready prompt:**
```
Entropia — S1: Portfolio FX settlement-currency blocker. Session START + git doğrulama. Oku:
docs/POST_V1_SPEC_GAP_BACKLOG_ROUND3.md S1, doc 13 §5.1/§6.2/§10.1, mevcut
domain/allocation/rules.py (yalnız initial_capital.currency) + queries/readiness_check.py +
market data revision şeması (settlement currency kaynağı). Ampirik doğrula: settlement/FX
check yok. Fix: validate + readiness'e cross-currency FX-dataset blocker (fail-closed).
+integration (3 senaryo). Backend verify. feat/s1-allocation-fx-blocker, ayrı PR, NO AI attribution.
```

---

## S8 — Create Package sayfası: validation-run + baseline UI bağlama (doc 06 §3.2/§5/§7) 🟠
**Boyut:** Orta (frontend-only). **Öncelik:** Yüksek-orta (backend zincirleri HAZIR, yalnız UI yok).

**Doğrulanan durum:** GAP-07 (#169) validation-evidence plane'i, GAP-07b (#171) baseline CSV
upload/parse zincirini backend'e getirdi. AMA `frontend/src/lib/createPackage.ts` +
`pages/CreatePackage.tsx`'te `validation-runs|baseline` grep = 0 — "Run Validation Tests",
"Request Revision", baseline CSV upload/parse aksiyonları CP sayfasından dispatch edilemiyor.
Approve, PASSED validation run'a server-side gate'li; UI bu yolu göstermiyor.

**Kapsam:** routes/create_package.py'daki mevcut validation-run + baseline endpoint'lerini
(imzaları AMPİRİK oku — OCC/Idem header'ları signature'dan çıkar) lib/createPackage.ts
hook'larına + RequestActions bar'ına bağla. UI pre-gate etmez; hatalar verbatim.

**Verify:** vitest — run-validation dispatch + header assert; baseline upload→parse zinciri;
PASSED sonrası approve akışı.

**Paste-ready prompt:**
```
Entropia — S8: CP sayfası validation-run + baseline UI. Session START + git doğrulama. Oku:
docs/POST_V1_SPEC_GAP_BACKLOG_ROUND3.md S8, doc 06 §3.2/§5/§7, mevcut routes/create_package.py
(validation-run + baseline endpoint imzalarını AMPİRİK oku) + lib/createPackage.ts +
pages/CreatePackage.tsx RequestActions. Fix (frontend-only): hook'lar + aksiyon butonları,
UI pre-gate yok, hatalar verbatim. +vitest. Frontend verify.
feat/s8-cp-validation-baseline-ui, ayrı PR, NO AI attribution.
```

---

## S4 — Agent Tool Gateway parity: allocation + trade_log (doc 13 §9, doc 05 §11) 🟠
**Boyut:** Orta (backend-only). **Öncelik:** Orta-yüksek.

**Doğrulanan durum:** `application/jobs/agent_tools.py` `_HANDLERS` + `domain/agent_lab/tool_gateway.py`
ToolName enum'unda `allocation|trade_log` grep = 0. Doc 13 §9 portfolio_allocation.get_draft/
upsert_draft/sync_preview/validate/create_revision; doc 05 §11 + TL-22 trade_log.* tool'ları
gateway'de yok. UI-yolu komutları mevcut — yalnız gateway exposure eksik (CR-08 deseni:
aynı command/service, gateway üzerinden).

**Kapsam:** Mevcut command/query fonksiyonlarını gateway handler'larına sar (yeni iş mantığı
YAZMA); capability/ownership gate'leri gateway'in mevcut deseniyle; audit tool_call kaydı zaten
dispatch_tool_call'da. Parity suite'e (Stage 8a deseni) yeni tool'ları ekle.

**Verify:** integration — gateway üzerinden allocation draft upsert→validate ve TL create→
revision zinciri UI-yolu ile AYNI sonucu/denial kodunu verir (parity), ownership ihlali REJECTED.

**Paste-ready prompt:**
```
Entropia — S4: Agent gateway allocation + trade_log parity. Session START + git doğrulama. Oku:
docs/POST_V1_SPEC_GAP_BACKLOG_ROUND3.md S4, doc 13 §9, doc 05 §11 (TL-22), mevcut
application/jobs/agent_tools.py (_HANDLERS) + domain/agent_lab/tool_gateway.py (ToolName) +
commands/allocation_plan.py + commands/trade_log.py. Fix: mevcut komutları gateway handler'ı
olarak expose et (yeni mantık yok), parity testleri (Stage 8a deseni). Backend verify.
feat/s4-gateway-allocation-tradelog, ayrı PR, NO AI attribution.
```

---

## S6 — TS/TL export komutu (doc 04 §7/Rule 17, doc 05 §8/§11/§13.2) 🟠
**Boyut:** Orta (backend + küçük UI). **Öncelik:** Orta.

**Doğrulanan durum:** `routes/trading_signal.py` + `routes/trade_log.py`'de `export` grep = 0.
V18 "Export As Package" butonunun production karşılığı (async export job → immutable
source-mapping/provenance artifact + TRADING_SIGNAL/TRADE_LOG_EXPORT_REQUESTED/COMPLETED
audit) iki twin'de de yok. Result export (#GAP) ve Library export (R2c) desenleri mevcut —
aynı desen TS/TL'ye uygulanır.

**Kapsam:** R2c `export_package` / result_export desenini aynala: POST /trading-signals/{root}/export
+ /trade-logs/{root}/export (fresh Idem, owner/Admin), artifact üret, audit+outbox; UI'da
workbench'e Export aksiyonu. Twin diff'leri koru.

**Verify:** integration (yetkili→artifact+audit / yetkisiz→403 / idempotent replay) + vitest.

**Paste-ready prompt:**
```
Entropia — S6: TS/TL export komutu. Session START + git doğrulama. Oku:
docs/POST_V1_SPEC_GAP_BACKLOG_ROUND3.md S6, doc 04 §7/§13 Rule 17, doc 05 §8/§11/§13.2,
mevcut R2c export deseni (commands/package_lifecycle.py export_package + routes/library.py:238)
+ routes/trading_signal.py + trade_log.py. Fix: twin export komut+route+UI (R2c deseni).
+integration+vitest. Backend+frontend verify. feat/s6-tstl-export, ayrı PR, NO AI attribution.
```

---

## S7 — History detail manifest excerpt zenginleştirme (doc 16 §8.2/§9.4, RH-09) 🟠
**Boyut:** Orta (backend + küçük UI). **Öncelik:** Orta.

**Doğrulanan durum:** `application/queries/results_history.py:273` her satırda
`"market_data_revision_summary": None` hardcode; `domain/backtest/history.py:170`
`extract_manifest_context` "market_data_revision": None (yorum: 'pinned inside strategy').
Doc 16 §9.4 ResultManifestExcerptDTO'nun strategy_revision_refs[]/package_revision_refs[]/
market-data context/allocation context/artifact_availability alanları detail projection'da yok;
compare context Market Data revision farkını flag'leyemiyor (RH-09).

**Kapsam:** Manifest JSON zaten immutable ve zengin — projection'ı manifest'ten OKUYARAK
doldur (yeni yazım yok): excerpt DTO alanları + history row market_data_revision_summary +
compare context'e market-data satırı. Frontend ResultDetail excerpt bölümünü genişlet.

**Verify:** integration — koşulmuş run'ın detail'i gerçek ref'leri döner; compare farklı
market revision'da differs flag'ler. Vitest excerpt render.

**Paste-ready prompt:**
```
Entropia — S7: History manifest excerpt zenginleştirme. Session START + git doğrulama. Oku:
docs/POST_V1_SPEC_GAP_BACKLOG_ROUND3.md S7, doc 16 §8.2/§9.4/RH-09, mevcut
queries/results_history.py:273 (None hardcode) + domain/backtest/history.py:170 +
manifest üretimi (commands/backtest_run.py build_run_manifest — kaynak gerçeği). Fix:
projection'ı manifest'ten doldur (read-only), compare'e market-data context. +integration+vitest.
Backend+frontend verify. feat/s7-history-manifest-excerpt, ayrı PR, NO AI attribution.
```

---

## S2 — Pre-Check kaynak-kod lexer'ı (doc 07 §6.2, PC-05/PC-06) 🟠
**Boyut:** Orta-büyük (backend, saf domain). **Öncelik:** Orta.

**Doğrulanan durum:** `commands/create_package.py::run_precheck` (~L350-417) detected listesini
caller-supplied declared deps'ten türetiyor; `lexer|tokenize|parse_source` grep = 0. Doc 07 §6.2:
TA bağımlılıkları KAYNAK KODDAN semantic call node'larla çıkarılmalı — yorum/string içindeki
`ta.*` sayılmamalı (PC-05), source'ta olup declare edilmemiş `ta.*` bloklamalı (PC-06).

**Kapsam:** Saf `domain/create_package/source_scan.py` — PineScript-benzeri tokenizer
(yorum/string state machine + `ta.<ident>(` / `cond.<ident>(` call tespiti). run_precheck:
declared ∪ detected reconcile — undeclared-in-source → BLOCKER, declared-not-in-source →
WARNING. Kod modu dışında (description) mevcut davranış korunur.

**Verify:** unit — yorum/string içi ta.* sayılmaz; gerçek call sayılır; undeclared → BLOCKER.
Integration: PC-05/PC-06 senaryoları.

**Paste-ready prompt:**
```
Entropia — S2: Pre-Check kaynak lexer'ı. Session START + git doğrulama. Oku:
docs/POST_V1_SPEC_GAP_BACKLOG_ROUND3.md S2, doc 07 §6.2/PC-05/PC-06, mevcut
commands/create_package.py run_precheck (~L350-417, declared-list bazlı). Fix: saf
domain/create_package/source_scan.py tokenizer (yorum/string-aware ta.*/cond.* call tespiti) +
run_precheck reconcile (undeclared→BLOCKER, unused→WARNING). +unit+integration.
Backend verify. feat/s2-precheck-source-lexer, ayrı PR, NO AI attribution.
```

---

## S3 — Package import (doc 08 §9.1/§10/§14, master ref Modül 7 §12) 🔴
**Boyut:** BÜYÜK (epic — R2c export'un tersi; job + tablo gerekebilir). **Öncelik:** Orta (export tek yönlü kaldıkça değeri sınırlı).

**Doğrulanan durum:** Export R2c'de landed (`routes/library.py:238` POST /library/{id}/export →
immutable manifest artifact). İmport yönü YOK: `package_import|import_job` grep backend'de 0.
Master ref Modül 7 §12: POST /v1/package-imports — async parser/validator job, yeni local root
`origin_package_id` provenance'ıyla; unresolved dependency → DRAFT/BLOCKED (asla sessizce
executable değil); `package_import_job` kaydı + import error/recovery contract (doc 08 §10).

**Kapsam (alt-slice önerisi):** (a) migration: package_import_job tablosu; (b) POST
/package-imports (fresh Idem, durable 202 job — INF-03 data queue deseni); (c) worker: manifest
parse + dependency resolve (Pre-Check resolver REUSE) → yeni DRAFT root + provenance; unresolved
→ BLOCKED + diagnostics; (d) UI: Library'ye Import aksiyonu + job report görünümü (TS/TL import
report deseni, ["jobs","package-import",jobId]).

**Verify:** integration — temiz manifest → DRAFT root + provenance; unresolved dep → BLOCKED +
diagnostics, asla executable; idempotent replay aynı job. Alembic up/down/up.

**Paste-ready prompt:**
```
Entropia — S3: Package import job. Session START + git doğrulama. Oku:
docs/POST_V1_SPEC_GAP_BACKLOG_ROUND3.md S3, doc 08 §9.1/§10/§14, master ref Modül 7 §12,
mevcut R2c export (commands/package_lifecycle.py + routes/library.py:238) + TS/TL import job
deseni (durable 202 + report) + Pre-Check resolver. Fix (alt-slice'lara böl): migration
package_import_job → POST /package-imports (202) → worker parse/resolve (unresolved→BLOCKED)
→ Library UI Import + report. +integration+vitest+alembic up/down/up. Backend+frontend verify.
feat/s3-package-import-*, ayrı PR'lar, NO AI attribution.
```

---

## S5 — Strategy config katalog derinliği (doc 02 §5.5/§5.7/§5.8/§5.9) 🟡
**Boyut:** EN BÜYÜK (backend şema + engine + frontend form; ENGINE_VERSION bump). **Öncelik:** Düşük-orta (mevcut davranış fail-closed L4 — sessiz yanlışlık yok).

**Doğrulanan durum:** `domain/strategy/config.py`'de yok (grep=0): §5.5 logic-based stop block +
stop mode enum (any_active_rule|all_active_rules); §5.9 conflict matrix'in bazı typed alanları
(stop_exit önceliği, multiple_stops, same_candle_entry_exit vb.); §5.8 Minimum-N-of-M restriction
rule (yalnız Literal['any','all'], :692-712); §5.7 scaling timeframe_mode|custom_sequence.
Engine desteklemediği yapılandırmayı `unresolved`/L4 ile işaretliyor — mevcut desen dürüst.

**Kapsam (alt-slice'lara böl, her biri ENGINE_VERSION bump):** (a) restriction Minimum-N
(+min_true_count alanı + engine gate); (b) conflict matrix eksik alanları (şema + engine öncelik
kuralları); (c) scaling timeframe_mode; (d) logic-based stop blocks (indicator ref + condition
list — condition-block altyapısı REUSE, PR #49/#51 deseni). Her adım: JSONB şema (migration yok),
compiler validation, engine davranışı, structured form UI (R6 package-picker REUSE), ⓘ paneller.

**Verify:** her alt-slice unit+integration (config→engine davranış kanıtı) + execution_key ns
shift testi + vitest form.

**Paste-ready prompt:**
```
Entropia — S5: Strategy config katalog derinliği. Session START + git doğrulama. Oku:
docs/POST_V1_SPEC_GAP_BACKLOG_ROUND3.md S5, doc 02 §5.5/§5.7/§5.8/§5.9 + §9.2, mevcut
domain/strategy/config.py (ProtectionStop :521, RestrictionsFilters :692) + domain/backtest/
engine.py + indicators.py condition-block altyapısı (PR #49/#51) + R6 form (#191/#192).
Alt-slice seç (a Minimum-N / b conflict / c scaling TF / d logic-based stop), ampirik doğrula,
uygula: şema+compiler+engine+form+ⓘ, ENGINE_VERSION bump. +testler. Backend+frontend verify.
feat/s5<x>-strategy-<slug>, ayrı PR'lar, NO AI attribution.
```

---

## LOW (opsiyonel, tek-oturumluk küçükler)
- **S-L1 — Allocation 409 gövdesi** (doc 13 §7.2/§10.2 Flow E): `AllocationDraftConflictError`
  (shared/errors.py:964) statik; `current_draft` + `changed_paths[]` eklenebilir (route zaten
  draft'ı okuyabiliyor). Frontend conflict UX'i buna göre zenginleşir.
- **S-L2 — Export tipleri** (doc 15 §3.2): ExportType'a `pinescript_signal_marker` +
  `agent_dataset` ekle (domain/backtest/export.py — mevcut 5 tip deseni).
- **S-L3 — Library request-validation** (doc 08 §7): POST /library/{id}/validation-runs —
  CP-plane validation-run komutunu (gap-07) Library-plane'e sar; `can_request_validation`
  orphan flag'i tüketilir.
- **S-L4 — Manifest warning satırları** (doc 14 RC-03): build_run_manifest preflight'a
  warning issue row'larını (code/scope/path/message) da koy (şimdi yalnız count + report ref —
  transitif erişilebilir, düşük değer).
- **S-L5 — `GET /rationale-families:suggest`** (master ref Modül 6 §11): read-only öneri
  endpoint'i (q= substring, mutation yok) + Create Package composer'da öneri chip'leri.
- **S-L6 — `UPLOAD_JOB_FAILED`** (doc 21 §10): manual upload pipeline teknik hatası için ayrı
  kanonik kod (şimdi generic); errors.py + jobs/manual upload fail path + test.
- **S-L7 — Nav legacy etiketleri** (doc 01 §6.3 vs v18-verbatim kuralı): "Trading Signal
  Packages"/"Trade Log Packages" (nav.ts:130-131) bilinçli v18-verbatim çelişkisi — KARAR
  maddesi: ya doc-01 migration notunu uygula ya CLAUDE.md'ye adjudication notu düş.
