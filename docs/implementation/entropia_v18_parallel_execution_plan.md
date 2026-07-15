# Entropia V18 Remediation — Parallel Execution Plan & Paste-Ready Prompts

> Amaç: kalan V18 remediation maddelerini (F-01..F-25 + UI-01..UI-22) **yapıyı bozmadan**
> paralel yürütmek. Bu doküman iki şey verir: (1) hangi işlerin aynı anda ayrı
> chat/branch'lerde güvenle koşabileceğini gösteren **çakışma matrisi**, (2) her iş için
> **paste-ready kapsamlı prompt**.
>
> Landed: **F-06** (PR #210), **F-09** (PR #209). Kaynak otorite: `docs/spec/Entropia_V18_Claude_Code_Implementation_Spec.md`
> + `docs/implementation/entropia_v18_remediation_status.md`.

---

## 0. ALTIN KURALLAR (yapıyı bozmamak için)

1. **Bir çekirdek dosyaya aynı anda iki branch dokunmasın.** Aşağıdaki "sıcak dosyalar"
   tek seferde tek branch'e ait olmalı:
   - `backend/src/entropia/domain/backtest/engine.py` + `application/jobs/backtest_engine.py` (ENGINE)
   - `backend/src/entropia/domain/strategy/config.py` (STRATEGY SCHEMA)
   - `backend/src/entropia/domain/readiness/validators.py` + `application/commands/readiness_check.py` (READINESS)
   - `frontend/src/pages/Mainboard.tsx` + `frontend/src/lib/mainboard.ts` (MAINBOARD SHELL)
   - `frontend/src/pages/CreatePackage.tsx` + `frontend/src/lib/createPackage.ts` (CREATE PACKAGE)
   - `backend/src/entropia/config/settings.py` + auth middleware (AUTH)
2. **Her paralel iş kendi branch'inde.** `feat/v18-f0X-...`. Bitince PR → merge → sonraki.
3. **Migration'lı işleri paralel MERGE etme.** Aynı anda iki migration → `alembic head` dallanır.
   Migration olası: F-08 (`logic_blocks`), F-01/F-02 (upload evidence), F-21 (reauth token). Seri merge.
4. **Her session kendi izole DB'sini kullanır:** `TEST_DATABASE_URL=...entropia_<slug>` (:5432).
   İki session aynı DB adına paralel test koşarsa şema rebuild'i çakışır.
5. **Frontend UI maddeleri birbiriyle çakışır** (aynı Mainboard shell + inline editor). UI-01..05
   + F-15..19 tek şerit, **seri**.
6. Her PR: `ruff + ruff format --check + mypy src + pytest` (backend), `vitest + tsc + build`
   (frontend). **No AI attribution** (globally disabled). Empirik doğrula, review CRITICAL/HIGH'ı
   kanıtlamadan düzeltme.

---

## 1. PARALEL ŞERİT MATRİSİ

Farklı şeritler **aynı anda** ayrı chat'lerde koşabilir (ayrık dosya kümeleri). Bir şerit **içindeki**
maddeler **seri** (aynı sıcak dosyayı paylaşır).

| Şerit | Maddeler (şerit-içi sıra) | Sıcak dosyalar | Diğer şeritlerle paralel? |
|-------|---------------------------|----------------|----------------------------|
| **A — ENGINE** (kritik yol) | F-05 → F-04 → F-07 → F-08 → F-10 → F-11 | engine.py, jobs/backtest_engine.py, (F-08: config.py+validators) | ✅ B,C,D,E. ❌ F (F-08 config.py) |
| **B — AUTH/SECURITY** | F-22 → F-21 | settings.py, auth middleware, deletion.py, commands/auth.py | ✅ A,C,D,E,F |
| **C — AGENT EXECUTOR** | F-20 | worker/actors, agent_loop, agent_lab | ✅ A,B,D,E,F (engine'i çağırır, içine dokunmaz) |
| **D — E2E + TEST INFRA** | F-23 → F-24(sürekli) | `frontend/e2e/` (yeni dizin), CI yaml | ✅ herkes (sadece yeni dosya) |
| **E — UPLOAD/INGEST** | F-01 → (F-02 ∥ F-03) + UI-11 + UI-12 | upload service, MarketData/ResearchData/… pages, market_data.py, research_data.py | ✅ A,B,C,D. ❌ F (TS/TL) |
| **F — FRONTEND MAINBOARD** | UI-01→02→03→04→05→F-15→16→17→18→19→UI-14→15→16 | Mainboard.tsx, lib/mainboard.ts, StrategyDetails, TradingSignal, TradeLog | ❌ E (TS/TL,upload). ✅ A/B/C/D |
| **G — CREATE PACKAGE** | UI-06 → UI-07 → F-12 → F-13 → F-14 | CreatePackage.tsx, lib/createPackage.ts, package validation workers | ✅ A,B,C,D. ⚠️ F (nav) |
| **H — İZOLE UI** | UI-08,09,10,13,17,19,20(F-21 sonrası),22,18(F-20 sonrası),21 | her biri kendi page dosyası | ✅ birbirleriyle bile |
| **Z — DOCS** | F-25 | README, status doc | ✅ ama **EN SON** |

### Aynı anda güvenli örnek (4 paralel chat):
- Chat 1: A — F-05 · Chat 2: B — F-22 · Chat 3: C — F-20 · Chat 4: D — F-23
- Tamamen ayrık → merge conflict yok. 5. chat: E — F-01. Frontend (F) ayrı chat, E ile aynı anda DEĞİL.

### ❌ ASLA aynı anda koşma:
- A(F-08) + F(F-19): ikisi de `strategy/config.py`/readiness.
- E(F-03) + F(UI-04/05): ikisi de TradingSignal/TradeLog page.
- E(F-03) + G(UI-06/F-12): ikisi de CreatePackage.tsx.
- İki migration'lı iş (F-08+F-01+F-21) aynı anda **merge** → alembic head dallanır.
- Herhangi iki iş + aynı `TEST_DATABASE_URL` adı.

---

## 2. PASTE-READY PROMPTLAR

### Ortak iskelet (aşağıdakiler bunu somutlaştırır)
```
Entropia V18 remediation — <MADDE-ID> dilimi.
Session START: git fetch + git log --oneline origin/main -6 + gh pr list --state all ile
GERÇEKTE merged olanı doğrula (handoff STALE-BY-DEFAULT). Sonra oku:
  - docs/spec/Entropia_V18_Claude_Code_Implementation_Spec.md → <MADDE-ID> (tam)
  - docs/implementation/entropia_v18_remediation_status.md → durum + evidence
  - docs/implementation/entropia_v18_parallel_execution_plan.md → bu maddenin şeridi + çakışma kuralı
Kapsam: <spec Required implementation>. Acceptance: <spec Acceptance — HEPSİNE test>.
Sıcak dosyalar (SADECE bunlar, şerit sınırını aşma): <dosyalar>.
Kurallar: fail-closed (unsupported → blocker, silent substitution YOK); saved+financial her ayar
  engine'de çalışır + decision trace'te görünür; normal kullanıcıdan infra ID/JSON isteme.
Yerel: cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy src &&
  TEST_DATABASE_URL=postgresql+asyncpg://entropia:entropia@localhost:5432/entropia_<slug> uv run pytest --no-cov -q
  (+ migration varsa alembic up/down/up + model↔migration parity). Frontend: npm run test && npx tsc --noEmit && npm run build.
Branch feat/v18-<madde>-<slug> (main'den). Bitince: status doc güncelle → commit (No AI attribution)
  → PR → gh pr checks --watch → yeşilse merge iste.
F-24: fix'ten ÖNCE fail eden, SONRA geçen regression testi.
```

---

## ŞERİT A — ENGINE (kritik yol, tek chat, seri: F-05→F-04→F-07→F-08→F-10→F-11)

### F-05 — Date range + instrument → engine input (SIRADAKİ)
```
Entropia V18 remediation — F-05: seçili tarih aralığı + instrument'ı engine input'una uygula.
Session START (git verify + spec F-05 + status + plan şerit A).
Kapsam (spec §F-05): backtest_range'i worker+engine'e geçir; bar akışını start/end + instrument_id'ye
  göre FİZİKSEL filtrele; çoklu-instrument datasette SADECE seçili instrument; dökümante timezone +
  boundary-bar semantiği (Master Technical Reference); boş/geçersiz aralık → EXPLICIT reject (RUN_FAILED_*).
Acceptance: farklı aralıklar sadece kendi bar'larını işler; seçilmeyen instrument bar'ları asla
  decision/position/metric/artifact'a girmez; manifest range/instrument = işlenen data ile birebir.
Sıcak dosyalar: application/jobs/backtest_engine.py, domain/backtest/engine.py,
  application/queries/market_bars.py, (gerekirse) manifest.
Empirik: iter_bar_batches/resolve_bar_source imzasını OKU; filtreyi worker sınırında uygula, engine
  saf kalsın; bar timestamp format'ını doğrula. Karar: ENGINE_VERSION bump GEREKİR; migration yok.
F-24: aralık-dışı bar sızıntısını fix'ten önce yakalayan integration testi.
Branch feat/v18-f05-range-instrument-filter.
```

### F-04 — Execute complete Mainboard composition
```
Entropia V18 remediation — F-04: tüm Mainboard kompozisyonunu backtest'te çalıştır.
Session START + spec F-04 + status + plan A.
Kapsam (spec §F-04): sadece ilk enabled Strategy'yi seçmeyi BIRAK (_resolve_primary_strategy tek alıyor);
  immutable snapshot'taki HER enabled Strategy/TS/TL'yi dökümante sıralama + conflict kurallarına göre
  çalıştır; her katılan revision'ı manifest'te pinle; her objenin katkısı decision+result'ta izlenebilir.
Acceptance: çok-strateji Mainboard hepsini simülasyona+sonuca dahil eder; enabled TS/TL tanımlı yerde
  execution'ı etkiler, disabled etkilemez; sıralama+conflict deterministik, integration test'le kapalı.
Sıcak dosyalar: application/jobs/backtest_engine.py (_resolve_primary_strategy → çoklu),
  domain/backtest/engine.py (çoklu-item loop + conflict), manifest/result contract.
Empirik: doc 01 sıralama + doc 02 §5.9 conflict + doc 15 result şeması OKU; tek-strateji yolu
  byte-identical kalmalı. Karar: ENGINE_VERSION bump; result summary çoklu-item taşımıyorsa additive migration.
F-24: iki-strateji Mainboard'ın ikisini de çalıştırdığını kanıtlayan test.
Branch feat/v18-f04-full-composition.
```

### F-07 — Execute every saved Strategy setting (BÜYÜK — alt-dilimlere böl)
```
Entropia V18 remediation — F-07: kaydedilmiş her Strategy Details ayarını engine'de çalıştır.
Session START + spec F-07 + Master Technical Reference "2.3 POSITION ENTRY LOGIC" + status + plan A.
Kapsam (spec §F-07): limit orders + order validity + unfilled policy; partial fills; entry/exit timing;
  funding + Research available-time; Scaling; Restrictions & Filters; overlap/stacking/hedge;
  close_percentage + partial-close; signal-strength; leverage mode; trailing lock_in_percentage.
  "Entry hep candle close, exit hep full close" VARSAYIMINI KALDIR.
Acceptance: her ayar 1 pozitif + 1 negatif engine testi; saved revision↔manifest↔engine↔result↔trace
  UYUŞUR; unsupported = BLOCKER (ignored değil).
Sıcak dosyalar: domain/backtest/engine.py, config.py (ayar varlığı), readiness (unsupported → blocker).
⚠️ BÜYÜK → alt-dilim (ayrı PR, seri): (a) execution timing; (b) limit orders+validity+unfilled;
  (c) partial fills + close_percentage; (d) scaling; (e) restrictions/filters; (f) leverage+trailing;
  (g) signal-strength. Her biri fail-closed. Karar: her alt-dilim ENGINE_VERSION bump; migration muhtemelen yok.
Branch feat/v18-f07<x>-<slug>.
```

### F-08 — Logic-Based Stop end to end (MIGRATION var — F ile paralel koşma)
```
Entropia V18 remediation — F-08: Logic-Based Stop uçtan uca.
Session START + spec F-08 + Master Technical Reference (stop-combination canonical order) + status + plan A.
Kapsam (spec §F-08): backend strategy schema'ya logic_blocks + stop-combination mode alanları EKLE;
  aynı modeli frontend form+validation+revision serialization+readiness+engine'de kullan; AND/OR +
  priority + interaction'ı canonical sırada uygula.
Acceptance: kullanıcı Logic-Based Stop create/save/reopen/edit/execute; çoklu stop tipleri dökümante
  birleşir; "backend does not implement this" placeholder KALMAZ.
Sıcak dosyalar: domain/strategy/config.py (JSONB, migration olası), domain/backtest/engine.py (stop
  combination), readiness/validators.py, frontend StrategyDetails + lib/strategy.ts.
⚠️ MIGRATION olası → F-01/F-21 ile AYNI ANDA MERGE ETME; F şeridiyle (config.py) çakışır → aynı anda koşma.
Karar: ENGINE_VERSION bump; migration varsa alembic up/down/up + parity. F-24: her stop kombinasyonu +/- test.
Branch feat/v18-f08-logic-based-stop.
```

### F-10 — Complete decision trace
```
Entropia V18 remediation — F-10: eksiksiz decision trace.
Session START + spec F-10 + doc 15 (trace) + status + plan A.
Kapsam: trace'i entry_signal + aggregated filtered_no_entry ötesine genişlet — entry/exit/stop/scaling/
  evaluated rule ID/her condition sonucu/restriction/conflict kararı/fill/partial fill/partial-close;
  trace'i object revision + bar/event time + position + order + manifest'e bağla.
Acceptance: reviewer her pozisyonun neden açıldı/açılmadı/değişti/kapandı'yı yeniden kurar; aynı manifest
  deterministik trace; export + UI diagnostics aynı bilgi. Sıcak dosyalar: engine.py (trace emit),
  result/artifact contract, trace query. Karar: artifact additive; determinizm değişirse ENGINE_VERSION bump.
Branch feat/v18-f10-decision-trace.
```

### F-11 — Research Data + Funding engine'de
```
Entropia V18 remediation — F-11: Research Data + Funding'i backtest engine'de kullan.
Session START + spec F-11 + doc 10/12 + status + plan A.
Kapsam: Research revision'larını backtest sırasında OKU+KULLAN (sadece provenance değil); available-time
  join + future-leak önle; Funding'i pozisyon cost'una + bağımlı her kurala uygula.
Acceptance: research-bağımlı koşullar available-time öncesi bilgiyi kullanamaz; funding-on vs off farklı
  doğrulanabilir sonuç; kullanılan her revision manifest'te pinli. Sıcak dosyalar: engine.py,
  jobs/backtest_engine.py, application/queries (research/funding source), manifest.
Karar: ENGINE_VERSION bump; revision'lar manifest'e ekleniyorsa contract. F-24: future-leak testi.
Branch feat/v18-f11-research-funding-engine.
```

---

## ŞERİT B — AUTH / SECURITY (seri; A/C/D/F ile paralel)

### F-22 — Production authentication profile
```
Entropia V18 remediation — F-22: production authentication profilini tamamla.
Session START + spec F-22 + status + plan B. (Docker/IdP E2E bu makinede KANITLANAMAZ → unit/integration
  + config seviyesi; Docker kısmını "blocked-needs-stack" işaretle, "Complete" DEME.)
Kapsam (spec §F-22): AUTH_MODE=dev'i açıkça isimlendirilmiş dev profiline KISITLA; production +
  production-like test profilleri gerçek login + session/token validation + role + policy zorlasın;
  production'da kullanıcı-kontrollü X-Actor-Id spoofing'i REDDET.
Acceptance: production config dev header ile actor impersonate EDEMEZ; login/logout/expiration/role
  denial/audit E2E (F-23'e bağlı). Sıcak dosyalar: config/settings.py, auth middleware (X-Actor-Id trust),
  commands/auth.py, session validation. Empirik: PR #38 AUTH_MODE=dev|session akışı OKU; production'da
  X-Actor-Id reddini integration testle kanıtla.
Branch feat/v18-f22-prod-auth-profile.
```

### F-21 — Real Trash re-authentication (F-22 sonrası; MIGRATION olası)
```
Entropia V18 remediation — F-21: gerçek Trash re-authentication.
Session START + spec F-21 + doc 20 §0/§8.3 (purge) + status + plan B.
Kapsam (spec §F-21): non-empty string'i reauth proof olarak KABUL ETME (deletion.py ~530); aktif
  kullanıcıyı configured IdP/auth backend üzerinden yeniden doğrula; proof'u user+action+kısa expiration'a
  bağla, replay önle.
Acceptance: yanlış şifre/rastgele metin kalıcı silmeyi yetkilendiremez; başarılı/failure/expiration/
  lockout/replay/audit test edilir. Sıcak dosyalar: application/commands/deletion.py, auth verify path,
  (olası) reauth token/nonce tablosu → migration.
⚠️ MIGRATION olası → F-08/F-01 ile aynı anda merge etme. Gerçek-IdP verify kanıtlanamazsa dürüstçe işaretle.
F-24: rastgele-string proof reddini kanıtlayan test. Branch feat/v18-f21-trash-reauth.
```

---

## ŞERİT C — AGENT EXECUTOR (tek madde; A/B/D/F ile paralel)

### F-20 — Real autonomous Alpha Agent executor
```
Entropia V18 remediation — F-20: gerçek autonomous Alpha Agent executor.
Session START + spec F-20 + doc 18 (Agent/Coordinator) + doc 22 (capability) + status + plan C.
Kapsam (spec §F-20): coordinator'ın QUEUED task'larını claim eden DURABLE executor; planning + safe tool
  selection + tool execution + backtest execution + result evaluation + hypothesis/output creation +
  lifecycle transitions; retry + idempotency + timeout + cancellation + audit + permission boundaries.
Acceptance: bir directive, test kodu her adım için elle dispatch_tool_call çağırmadan uçtan uca tamamlanır;
  her adım/tool call/result/failure/transition Analysis Lab + audit'te görünür.
Sıcak dosyalar: apps/worker/actors.py (yeni executor actor), commands/agent_loop.py, jobs/agent_tools.py
  (gateway'i reuse, imzayı bozma), agent_lab repo/queries. Backtest engine'e DOKUNMA (run_backtest'i çağır).
Empirik: run_coordinator_cycle + dispatch_tool_call + AgentToolCall/AgentTask şeması OKU; gateway parity
  (test_gateway_parity) BOZMA. UI-18 (Analysis Lab bağlama) ayrı frontend dilimi, bundan sonra.
Branch feat/v18-f20-agent-executor.
```

---

## ŞERİT D — E2E + TEST INFRA (herkesle paralel; sadece yeni dosya)

### F-23 — Real browser E2E suite
```
Entropia V18 remediation — F-23: gerçek browser E2E suite.
Session START + spec F-23 + PART IV test stratejisi + status + plan D.
Kapsam (spec §F-23): Playwright (veya eşdeğer); Docker stack'e (gerçek API+DB+worker+test object storage)
  karşı koş; min kapsam: auth, Market Data upload, Research Data upload, Strategy creation, Mainboard attach,
  Ready Check, RUN, inline result, Create Package lifecycle, Trash reauth; mocked fetch'e BAĞIMLI OLMASIN;
  CI tekrarlanabilir + failure'da screenshot/video/trace publish.
Acceptance: suite yalnız mocked fetch'e dayanmaz; CI artifact üretir.
Sıcak dosyalar: SADECE YENİ — frontend/e2e/ (yeni dizin), playwright.config, CI workflow yaml (yeni job).
  Mevcut kaynağa DOKUNMA → sıfır çakışma. ⚠️ Docker bu makinede kanıtlanamayabilir → suite YAZ + CI job ekle;
  yerel Docker run kanıtlanamazsa "authored, needs stack for green" işaretle. Journey'ler ilgili UI dilimi
  landing'de yeşile döner; başta iskelet + auth journey.
Branch feat/v18-f23-e2e-suite.
```

---

## ŞERİT E — UPLOAD / INGEST (F-01 önce; sonra F-02∥F-03; F ile paralel koşma)

### F-01 — Real Market Data file upload (paylaşımlı uploader temeli; MIGRATION olası)
```
Entropia V18 remediation — F-01: gerçek Market Data file upload.
Session START + spec F-01 + Market Data page spec + status + plan E.
Kapsam (spec §F-01): MarketData.tsx'e native file chooser + dökümante upload workflow; gerçek dosya
  byte'larını API/upload service üzerinden object storage'a aktar; object key + SHA-256 digest + byte size
  + content type'ı OTOMATİK üret (kullanıcıdan İSTEME); progress/cancel/retry/failure/success; metadata'yı
  SADECE storage write + integrity verify sonrası persist et; upload idempotent + retry-safe.
Acceptance: kullanıcı storage metadata girmeden yerel dosya yükler; byte'lar storage'da, digest verify,
  revision doğru object'e işaret eder; unsupported type/size/interrupted/storage failure/digest mismatch →
  net hata; unit+API+storage+E2E test.
Sıcak dosyalar: frontend MarketData.tsx + (yeni) paylaşımlı file-upload component/hook,
  application/commands/market_data.py, infrastructure/s3, (olası) evidence alanları → migration.
⚠️ PAYLAŞIMLI UPLOADER'ı kurar → F-02/F-03 reuse eder; temiz+reusable yap. MIGRATION olası → F-08/F-21
  ile aynı anda merge etme. UI-11 bu dilimle birleştirilebilir. Branch feat/v18-f01-market-data-upload.
```

### F-02 — Real Research Data file upload (F-01 sonrası; F-03 ile paralel)
```
Entropia V18 remediation — F-02: gerçek Research Data file upload.
Session START + spec F-02 + Research Data page spec + status + plan E (F-01 uploader'ını REUSE).
Kapsam: ResearchData.tsx pre-uploaded-object-key workflow'u native seçim + gerçek upload ile DEĞİŞTİR
  (F-01 uploader); Approved Market Data dependency seçimi + time-alignment + provenance + available-time +
  validation entegre; tüm storage metadata içeride üret.
Acceptance: normal kullanıcı MinIO key/hash bilmeden yerel dosyadan Research Data; byte + provenance +
  available-time + linked Market Data revision doğru; invalid dependency/schema/alignment/upload net bloklar.
Sıcak dosyalar: frontend ResearchData.tsx, commands/research_data.py, (F-01 uploader reuse — dokunma).
F-03 ile PARALEL güvenli (farklı sayfa) — F-01 merge SONRASI başlat. Branch feat/v18-f02-research-data-upload.
```

### F-03 — Real file choosers (TS/TL/Manual/CreatePackage) (F-01 sonrası; F-02 ile paralel)
```
Entropia V18 remediation — F-03: tüm simüle dosya girişlerini gerçek file chooser'la değiştir.
Session START + spec F-03 + status + plan E (F-01 uploader REUSE).
Kapsam: TS + TL TXT/CSV textarea'larını gerçek dosya seçimiyle değiştir; User Manual elle filename/content
  → gerçek doküman seçimi; Create Package'a gerçek TradingView baseline CSV; extension+MIME+encoding+size+
  schema backend'de DE doğrula.
Acceptance: TS/TL/User Manual/Create Package native seçim; seçim/upload/parse/validate/error/persist E2E;
  textarea'ya yapıştırma zorunlu DEĞİL. Sıcak dosyalar: frontend TradingSignal.tsx, TradeLog.tsx,
  UserManual.tsx, CreatePackage.tsx (baseline), backend validation.
⚠️ TS/TL sayfaları UI-04/05 (F) ile, CreatePackage.tsx UI-06/F-12 (G) ile ÇAKIŞIR → aynı anda koşma.
Branch feat/v18-f03-real-file-choosers.
```

---

## ŞERİT F — FRONTEND MAINBOARD (seri; backend A/B/C/D ile paralel, E/G ile dikkat)

> Prototip görsel referansı ZORUNLU: `docs/spec/index_guncellenmis_duzeltilmis_v18.html`.
> CLAUDE.md UI kuralı: sunum-only, route/query-key/OCC/Idempotency/hook/SSE/API DEĞİŞMEZ.
> Sıra: UI-01→02→03→04→05→F-15→16→17→18→19→UI-14→15→16.

### Şerit F ortak prompt (her UI/F maddesi için doldur)
```
Entropia V18 remediation — <UI-0X | F-1X>: <başlık>.
Session START + spec <madde> + docs/spec/index_guncellenmis_duzeltilmis_v18.html (görsel kaynak, ZORUNLU)
  + ilgili page spec + status + plan F.
Kapsam: <spec Required implementation>. Acceptance: <spec Acceptance — vitest + a11y>.
CLAUDE.md UI kuralı (ZORUNLU): SADECE sunum — route path / react-query key / OCC token (If-Match/
  expected_*_version/X-*-Version) / Idempotency-Key / hook / SSE taxonomy / API call / lib/*.ts data logic
  DEĞİŞMEZ; app/nav.ts NAV verbatim. Kırık test YENİ markup'a hizalanır (option value + OCC/Idempotency
  assertion aynı; sadece görünür label / aria-label / role).
Preview: cp docs/spec/index_guncellenmis_duzeltilmis_v18.html frontend/public/mockup_v18.html (dev-only).
Sıcak dosyalar (F sınırı): <ilgili page + Mainboard.tsx/lib/mainboard.ts>. E/G aynı sayfaya dokunuyorsa aynı anda koşma.
Yerel: cd frontend && npm run test && npx tsc --noEmit && npm run build. Preview'da layout+a11y+responsive
  (1280/1440/1920) doğrula, screenshot al. Branch feat/v18-<madde>-<slug>.
```

Şerit F madde özetleri:
- **UI-01 Mainboard:** her obje uzun yatay row + sağda expand ok; expand → gerçek type-specific editor
  (teknik panel DEĞİL); prototip Add menüsü (Strategy/Package/nested Add Outsource Signal); edit/Ready Check/
  RUN/Result Mainboard bağlamında.
- **UI-02 Strategy Details:** Strategy row İÇİNDE aç (ayrı /strategy primary DEĞİL); 3-kolon SETUP & DATA /
  DECISION LOGIC / RISK MANAGEMENT; 10 alt-bölüm; alt toolbar Save/Cancel/validate/revision; raw JSON DEĞİL.
- **UI-03 Add Outsource Signal:** standalone /outsource-signal primary'den KALDIR; Add/hover menüsünde
  2-seçenekli nested submenu; seçim yeni TS/TL row açar inline.
- **UI-04 Trading Signal:** 2-kolon inline panel; identity/source/bulk import grupla; sticky bottom toolbar +
  gerçek TXT/CSV (F-03 koordine).
- **UI-05 Trade Log:** yatay row + expandable 2-kolon inline; gerçek file chooser + monospaced format guide +
  bottom toolbar; standalone card stack + textarea KALDIR.
- **F-15 Mainboard JSON editor kaldır:** generic "Add work object"/object kind/raw JSON'u normal akıştan çıkar;
  ayrı Add Strategy/Package/Outsource Signal; user-facing revision selector, elle wor_... yok.
- **F-16 RUN readiness binding:** RUN gerçekten disabled/locked (Ready Check geçene dek); aynı readiness
  projection görsel+keyboard+backend authz'de; unavailable iken RUN route'a gitme.
- **F-17 Headline metrics on Mainboard:** headline projection'ı tüket; Net Profit/Max Drawdown/Win Rate/
  Profit Factor/ROMAD inline; eksik değer explicit N/A. (Nispeten izole.)
- **F-18 Durable Strategy drafts:** ?draft= URL bağımlılığını kaldır; unattached draft list/open/attach/delete
  query + UI; ownership/permission/history/audit korunur. (Backend draft-list endpoint gerekebilir — ufak eki.)
- **F-19 Strategy Details infra ID/JSON kaldır:** Market/Research/Funding root/revision/hash → user-facing
  picker; parameter overrides/reference chains/restrictions için form; raw JSON sadece advanced view.
  ⚠️ config.py'ye dokunabilir → F-08 ile aynı anda koşma.
- **UI-14 Ready Check:** sabit sağ-alt Ready Check/RUN shell; modal (ayrı route DEĞİL); 3-kolon
  Passed/Failed/Warnings; strip gerçek readiness'a bağlı.
- **UI-15 RUN & Results:** RUN lock/unlock gerçek readiness'tan; progress+result Mainboard ALTINDA inline;
  Metrics/chart/Trade List/Diagnostics/Export korunur.
- **UI-16 Results History:** mavi yatay card + expansion + sort + pagination + compare korunur; inline panel'e
  Strategies/Parameters/Data/date/immutable manifest özeti.

---

## ŞERİT G — CREATE PACKAGE (seri; backend A/B/C/D ile paralel)

Sıra: UI-06 → UI-07 → F-12 → F-13 → F-14. Sıcak: CreatePackage.tsx, lib/createPackage.ts, validation workers.
F-03'ün CreatePackage baseline dokunuşuyla aynı anda koşma. F ortak iskeletini (UI) + Ortak iskeleti (backend) kullan.
- **UI-06 Add Package & Create Package:** Mainboard'da küçük Add Package popover; 2-kolon CP Agent workspace
  (sol: request/chat + draft-file list; sağ: Package Status/Baseline/Resolver/Validation Tests/Library Target);
  generic "New request/My requests/detail" DEĞİL; gerçek TradingView baseline CSV.
- **UI-07 Pre-Check:** Create Package İÇİNDE button + status pill + accessible overlay modal (ayrı route DEĞİL);
  passed/blocked/failed/warning Package Status ile bağlı.
- **F-12 Create Package frontend lifecycle:** tüm backend transition'ları bağla (Run Validation/Upload baseline/
  Parse/View report/Request Revision/Confirm eligibility/Approve+publish); UI sadece izinli action; draft
  doğrudan approval çağıramaz.
- **F-13 Every required package validation:** durable worker'larda gerçek syntax/runtime/Market Data/
  repaint-future-leak/baseline comparison; not_executed ≠ passed; eligible_for_approval yalnız tüm check bitince.
- **F-14 Real candidate/package generation:** manifest/hash-only V1 stub'ı değiştir; approved request'ten
  loadable implementation + contract + dependency + test draft + validation input üret; immutable revision +
  validation'a gönder; codegen/execution sandbox.

---

## ŞERİT H — İZOLE UI (birbirleriyle bile paralel — ayrı page dosyaları; F iskeletini kullan)

- **UI-08 Package Library:** yatay row + inline expand; 6-alan filter bar (Market/Timeframe/Sort); type section; compact detail.
- **UI-09 Embedded System Packages:** heading + System-scope facet + expandable resolver row; Propose Resolver/
  Resolve Probe modal/drawer'a; catalog önce.
- **UI-10 Rationale Families:** 2-kolon Family List / Package Assignment; pastel card primary; sürekli açık form →
  compact Add row → inline editor.
- **UI-13 Portfolio/Equity Allocation:** toggle off → opacity/grayscale/pointer-events/keyboard disable; 4-card
  (Calculation Preview + Allocation Check); Add Item picker + Sync confirm; explicit empty/error.
- **UI-17 Arrange Metrics:** her zaman görünür 18-item Future Version Metrics panel; available vs future ayrım;
  checklist/lock/profile korunur.
- **UI-19 Panel/Management/Logs:** Logs + Management ayrı work context; Registered Users/System Actors/Role Matrix →
  Management; Logs/Raw Audit/filter → Logs; Operator Recovery permission + controlled secondary flow.
- **UI-20 Trash (F-21 sonrası):** PANEL/TRASH başlık; search/type filter/table/restore/permanent-delete; snapshot
  content üst JSON panel; gerçek reauth (F-21).
- **UI-22 Future Dev:** Graphic View/Backtest Review/Signal Intelligence/Research target'ları geçerli route'a;
  Graphic View = intro + 6 static placeholder card; placeholder'da input/table/lifecycle/form YOK; Capability
  Registry/Prepare View Dataset/Analysis Artifact placeholder'dan çıkar (yalnız capability active + izinli).
- **UI-18 Analysis Lab (F-20 sonrası):** status bar + Lab Context/Conversation/Work Queue/Hypothesis 3-column;
  başlık AGENT WORKSPACE / ANALYSIS LAB; F-20 executor state'lerini Work Queue'ya bağla.
- **UI-21 User Manual:** sticky sol MANUAL DOCUMENTS sidebar + sağ continuous reader; search+section nav primary;
  Publish/Add Text/Upload/Restore modal/drawer; gerçek doküman chooser (F-03).

---

## ŞERİT Z — DOCS (EN SON)

- **F-25 Truthful README/status:** "Production V1 complete" iddiasını kaldır; test count/migration level/
  supported workflow/known limitation'ı verifiable kaynaktan güncelle; README ↔ CI ↔ migration dizini çelişkisiz.
  Her şey bittikten SONRA.

---

## 3. ÖNERİLEN BAŞLANGIÇ (bugün 4 paralel chat)

| Chat | Şerit | İlk madde | Neden güvenli |
|------|-------|-----------|----------------|
| 1 | A ENGINE | **F-05** | engine plane tek sahip |
| 2 | B AUTH | **F-22** | config/auth ayrık |
| 3 | C AGENT | **F-20** | worker/agent ayrık |
| 4 | D E2E | **F-23** | sadece yeni dosya |

5. chat: E — **F-01** (upload temeli; merge olunca F-02∥F-03 açılır). Frontend (F) ayrı chat, E ile aynı anda DEĞİL.
Her madde bitince: status doc güncelle → PR → merge → şerit-içi sonraki. Migration'lı işleri (F-08/F-01/F-21)
asla aynı anda **merge** etme.
