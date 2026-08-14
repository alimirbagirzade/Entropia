<!-- doc-status: historical -->
> **HISTORICAL RECORD — bu bir DENETİM KAYDIDIR, güncel handoff değildir.** 2026-08-13'te
> `e2fa521` üzerinde ölçülen durumu dondurur. SHA'lar, sayılar ve "next" maddeleri sonraki
> dalgalarda bayatlar. Güncel otorite: `CLAUDE.md` §Current position +
> `docs/generated/repository_facts.md`. Bulguların **kapanış durumu** için
> `docs/ADIM65_LANDED_KICKOFF.md`'ye bak — bu dosya hiçbir bulguyu "kapandı" diye
> güncellemez, ölçüldüğü anı korur.
>
> **BU BELGE ÜÇ KUSURU "HÂLÂ BOZUK" DİYE KAYDEDER VE O ÖLÇÜM ARTIK GEÇERSİZDİR.**
> §7 / §13'ün `#550` · `#551` · `#552` satırları `e2fa521` üzerinde doğruydu;
> **PR #720 üçünü de sevk etti** (`5e52465`, 2026-08-14, `ENGINE_VERSION` →
> `backtest-engine-v18-percent-sizing-per-fill-commission`). Kayıt **bilerek
> güncellenmedi** — bir denetim belgesi ölçtüğü anı dondurur; kapanış kaydı
> `PROJECT_HISTORY.md` §ADIM 61'dedir. Bu satırlardan **hiçbiri** bugünkü davranış
> hakkında okunmamalıdır.

# Entropia V18 — Final Closure Forensic Audit (AŞAMA A, read-only)

> **READ-ONLY GERÇEKLİK İNCELEMESİ.** Bu belge yalnız ölçer. Hiçbir production kodu,
> migration, test beklentisi, `ENGINE_VERSION`, capability flag, issue durumu veya PR
> bu oturumda değiştirilmedi. AŞAMA B (canonical + documentation reconciliation) burada
> BAŞLAMAZ.

---

## 1. Audit identity

| Alan | Değer |
|---|---|
| Audit türü | Forensic current-main implementation audit — AŞAMA A |
| Kapsam | Shared equity allocation · position sizing · zero-size trade · commission · research provenance · performance residuals · observability delivery · accessibility evidence · documentation drift · issue-state drift |
| Yöntem | CANONICAL → DOMAIN → APPLICATION → PRODUCTION CALLER → WORKER → PERSISTENCE → RESULT → TEST → DOCS → GITHUB, her eksende ayrı ayrı |
| Tarih | 2026-08-13 |
| Production kodu değişti mi | **HAYIR** |
| Commit / PR açıldı mı | **HAYIR** (görev talimatı §1: "Commit oluşturma. PR açma.") |
| Ölçüm dayanağı | Çalışan ağaç `origin/main`'e `--hard` reset edilmiş hâli; hiçbir test suite koşulmadı (aşağıdaki her test iddiası **statik** — kaynak okuması, koşu değil) |

**Bu auditin kendi dürüst sınırı.** Backend/frontend suite'leri bu oturumda **koşulmadı**.
Test sayıları `docs/generated/repository_facts.md`'nin *collected* (statik) rakamlarıdır,
pass sayısı değildir. Bir testin var olduğunu gördüm; **geçtiğini** görmedim. Aşağıda bir
davranışın "pinli" olduğunu söylediğim her yerde kastedilen, o assertion'ın kaynakta
bulunduğudur.

---

## 2. Current main SHA

```
HEAD            e2fa52173a302aa6e9e1b0a23ba6061e6ccd8b86
subject         test(acceptance): prove external-object run provenance survives
                revision and delete (#692)
committed       2026-08-13 11:48:49 +0300
alembic head    0043_i08_registry_strategy_fks   (43 revisions, single head)
ENGINE_VERSION  backtest-engine-v18-gap-adjusted-stop-fill
SHARED_ALLOCATION_STATUS  future_dev
```

### 2.1 Son 30 commit (main)

```
e2fa521 test(acceptance): prove external-object run provenance survives revision and delete (#692)
f09e5b9 test(a11y): add a tab-order axis to the skip-link gate and land the ADIM 48 evidence (#689)
8579897 docs(a08): record the SR-2 VoiceOver acceptance session (#684)
8fa0767 chore(mcp): register codebase-memory-mcp via a portable .mcp.json (#693)
108f16b docs(stage-rc): reconcile the A-08 record with #514 being re-opened (#687)
ce823a8 fix(a11y): ADIM 50 — RC §6.5'in K-2 ve K-4'ü kapandı (PO kararı) (#685)
2e75c51 docs(stage-rc): record ADIM 49 — P11-1 closed by ruleset 20765617 (#691)
bad8d52 docs(memory): stage the two unwritten checkpoints and record why they cannot be written here (#690)
04c6a9c fix(a11y): lift the focus ring to WCAG 1.4.11 contrast (K-6b) (#688)
d6fa02f test(acceptance): close the first batch of class-B coverage debt (#686)
74bbd70 ci(stage-rc): prepare the main required status checks for P11-1 (#683)
7dd1dfe fix(api): align the last two admission endpoints and pin the clamp policy (#682)
6da8a95 perf(query): collapse the readiness and dependency-pin N+1 loops (#617, #618) (#681)
c931063 ci(acceptance): gate the five acceptance flows in CI (#680)
6f8b652 docs(rc): correct the readiness banner to two blockers after ADIM 44 (#679)
853a358 security(deps): drop the react-router freeze, delete its unsigned home (#678)
e719af1 ci(perf): wire Lighthouse as a ratchet and arm the latency ratio gate (#676)
2a93b72 chore(deps): bump the backend-minor-patch group in /backend with 5 updates (#673)
e3965c0 chore(deps): bump the frontend-minor-patch group (#670)
99e2a46 chore(ci): bump github/codeql-action/analyze (#671)
3886a1f chore(ci): bump astral-sh/setup-uv from 7.6.0 to 9.0.0 (#672)
240fa1f chore(deps): update boto3-stubs[s3] requirement in /backend (#674)
ed28c77 chore(ci): bump github/codeql-action/init (#675)
c8bba97 test(acceptance): freeze the partial-criteria ceiling and pin the named few (#669)
c697fad fix(stage-41): adjudicate the durable admission status, canonical by canonical (#668)
0dc56f8 refactor: merge byte-identical helpers found by a duplication audit, plus the audit wrapper (#667)
0c3d0e6 docs: stop hand-writing counts that the generated facts already own (#666)
66bdeb4 test(e2e): extend visual regression coverage to every audited route (#665)
ed83688 test(e2e): make the visual and keyboard gates cover what they claim (#664)
98858da fix(api): publish the pagination limit that nine endpoints silently applied (#663)
```

**Son 15 commit'in şekli tek başına bir bulgudur.** `test(...)`, `docs(...)`, `ci(...)`,
`chore(deps)` ve iki `fix(a11y)` CSS/markup düzeltmesi. **Motor semantiğine dokunan tek
commit yok.** `ENGINE_VERSION` bu aralıkta hiç değişmedi ve `-S` taraması onun en son
`2cf7283` (ADIM 29 kayıt commit'i) civarında ele alındığını gösteriyor — yani sizing,
zero-size ve commission kararlarının hiçbiri sevk edilmedi.

### 2.2 Açık PR'lar

| # | Başlık | Base | Durum |
|---|---|---|---|
| **694** | `feat(adim-53): hafıza türetilir oldu (agentmemory) + iki sessiz ajan kapısı onarıldı` | `main` @ `e2fa521` | open, **draft değil** |

Başka açık PR yok. Bu auditin bulgularının hiçbiri #694'ün kapsamında değil.

### 2.3 Açık issue'lar (tamamı — 5 adet)

| # | Başlık | Etiket | Bu audit'teki sonucu |
|---|---|---|---|
| **514** | A-08: Complete human NVDA/Firefox + VoiceOver/Safari acceptance audit | `human-only` | **AÇIK ve doğru** — release blocker |
| **558** | neither research bundle pins the available-time policy | `product-decision` | **AÇIK ve doğru** — PRODUCT-DECISION-REQUIRED |
| **559** | DST fold/gap has no canonical rule | `product-decision`, `blocks-mixed-zone-axis` | **AÇIK ve doğru** — unified-clock ön koşulu |
| **617** | ready-check market-data leg reads one dataset root per item | — | **AÇIK ama KOD ONARILDI** → ISSUE-STATE-DRIFT (ters yön) |
| **618** | pinned ESP resolver re-validation costs 2 round trips per pin | — | **AÇIK ama KOD ONARILDI** → ISSUE-STATE-DRIFT (ters yön) |

### 2.4 Kritik kapalı issue'lar (bu audit tarafından yeniden ölçüldü)

| # | Başlık | Durum | Kapatan PR | Current main davranışı |
|---|---|---|---|---|
| **550** | base/min/max position size execute as unit counts while the UI labels them percent | `closed` (completed, 2026-08-07) | **YOK** (`closed_by_pull_requests: []`) | **HÂLÂ BOZUK** |
| **551** | three sizing paths open a phantom 0-size trade | `closed` (completed, 2026-08-07) | **YOK** | **HÂLÂ BOZUK** |
| **552** | partial-close pays 1.4 commission round trips | `closed` (completed, 2026-08-07) | **YOK** | **HÂLÂ BOZUK** |

`git log --grep="#55[012]"` main üzerinde **hiçbir commit döndürmüyor**. Tüm ağaçta tek
eşleşme `b5c7c44 test(backtest): add independent financial oracle fixtures` — yani
kusurları **PİNLEYEN** test slice'ı, onaran değil.

---

## 3. Canonical authorities (kullanılan otorite sırası)

1. `docs/spec/Entropia_V18_Master_Technical_Reference_v1_0.md`
2. Sayfa belgeleri: `docs/spec/02_…`, `12_…`, `13_…`, `14_…`, `15_…`, `18_…`
3. `docs/adr/0002-unified-clock-portfolio-simulation.md` (ADR — §12 delivery plan, §14
   acceptance matrix, §16 stopping condition)
4. `CLAUDE.md` §Current position · `docs/STAGE2_HANDOFF.md` · en güncel kickoff
   (`docs/ADIM52_LANDED_KICKOFF.md`)
5. `docs/spec/index_guncellenmis_duzeltilmis_v18.html` (yalnız görünür UI referansı)
6. Production code (`backend/src`, `frontend/src`)
7. Tests
8. `docs/generated/repository_facts.md` (üretilmiş, CI'da `--check` bloklayıcı)
9. GitHub issue / PR kayıtları — **kanıt değil, yalnız iddia**

---

## 4. Production execution map

### 4.1 CURRENT PRODUCTION FLOW (ölçüldü)

```
POST /compositions/{id}/backtest-runs
  → application/commands/backtest_run.py
      ├─ readiness re-evaluation
      ├─ backtest_run.py:542  shared_allocation_is_executable() == False
      │                       AND shared_allocation_requested(snapshot.capital_mode_snapshot)
      │                       → _readiness_blocked([ALLOCATION_SHARED_MODE_NOT_IN_BUILD])
      │                       ↑↑ SHARED MODE BURADA ÖLÜR — manifest, run, job hiç oluşmaz
      ├─ _resolve_tick_pins(...)
      ├─ build_run_manifest(...)        → ENGINE_VERSION = backtest-engine-v18-gap-adjusted-stop-fill
      └─ enqueue durable Job
  → apps/worker/actors.py  (dramatiq)
  → application/jobs/backtest_engine.py
      ├─ :299   for prepared in prepared_items:        ← OUTER LOOP = ITEM LİSTESİ
      │           ├─ _cancellation_requested(...)        (O-06 checkpoint #3, ITEM ARASINDA)
      │           ├─ item_rules = replace(base_rules, prior_intervals=tuple(prior_intervals))
      │           ├─ :323  _replay_strategy(prepared, ...)
      │           │           → domain/backtest/engine.py::run_engine
      │           │               → _build_stepper(...) → _ItemStepper
      │           │               → for bar in stream: stepper.step(bar)   ← ITEM'IN KENDİ BAR EKSENİ
      │           │               → stepper.finalize(); stepper.output() → EngineOutput
      │           │                 (her item KENDİ _Ledger'ı, TAM havuz P0 ile tohumlanmış)
      │           └─ prior_intervals.extend(build_prior_intervals(...))   ← forward-only precedence
      ├─ if len(item_runs) == 1 and not non_executing:
      │       output = item_runs[0].output              ← tek-item bypass, byte-identical
      │   else:
      │       :364  output = combine_item_runs([...], portfolio_initial=..., shared_pool=...)
      │             → execution/portfolio.py  — BİTMİŞ koşuları PIN SIRASINDA BİRLEŞTİRİR
      │               (realized-PnL progression'ları CONCATENATE eder; zaman ekseni YOK)
      ├─ _cancellation_requested(...)   (O-06 checkpoint #4 — son güvenli nokta)
      ├─ bt_repo.create_result(session, run, manifest, engine_output=output, ...)
      └─ Result IMMUTABLE
  → okuma:
      queries/backtest_run.py:167       portfolio_simulation_context(manifest, diagnostics)
      queries/results_history.py:267    portfolio_simulation_context_from_parts(...)
        → domain/backtest/portfolio_mode.py  → "legacy_sequential" | "single_item" | "unknown"
```

### 4.2 TARGET CANONICAL FLOW (doc 13 §8.3/§8.4/§13, ADR §8)

```
API → Run command → shared-mode admission (GEÇER) → durable Job → worker
  → participants:  her item için ItemParticipant (gerçek engine ile beslenmiş)
  → merged global clock:  execution/clock.py::iter_ticks  — OUTER LOOP = BİRLEŞTİRİLMİŞ t_ms EKSENİ
  → her tick'te:
        P1 funding/fee
        P3 mandatory exits            (snapshot'tan ÖNCE oluşur)
        PV publish ONE PortfolioSnapshot(t), ledger DONAR
        P4 discretionary intents      (hepsi AYNI E(t)'ye karşı)
        P5/P6b arbitrate              (donmuş deftere karşı, simetrik, id tie-break)
        P7 apply in (pin_ordinal, item_id)
        P9 commit ONE equity point
  → shared ledger:  execution/portfolio_ledger.py  — P0, R0 = P0·r, U0 TEK yerde
  → unified EngineOutput:  execution/portfolio_projection.py::project_portfolio_run
  → immutable Result + portfolio_simulation manifest section (execution/provenance.py::build_portfolio_manifest)
```

### 4.3 İLK DIVERGENCE NOKTASI

> **`backend/src/entropia/application/jobs/backtest_engine.py:299`**
> ```python
> for prepared in prepared_items:
> ```
> Dış döngü **item listesidir**, birleştirilmiş timestamp ekseni değil.

Bu tek satır tüm kanonik zinciri koparır: item outer-loop olduğu sürece tek bir `E(t)`
yayımlanamaz, paylaşılan defter olamaz, arbitration simultaneous intent göremez, ve
`:364`'teki `combine_item_runs` fold'u zaman-sıralı olmayan bir eğri üretmek zorunda kalır.
Sonraki her divergence (`_replay_strategy`'nin item-local `_Ledger`'ı, `prior_intervals`'ın
forward-only precedence'ı, `combine_item_runs`'ın pin-sırası concatenation'ı) bunun
**türevidir**, bağımsız bir kusur değil.

**Ölçülmüş yan kanıt:** kanonik yolun her parçası — clock, intents, ledger, arbitration,
phase loop, projection, provenance — **repo'da mevcut ve production `src/` altında**, ama
`application/` katmanından tek bir import bile almıyor (§5.2). Eksik olan bir modül değil,
**bir adaptör ve bir çağrı yeri**.

---

## 5. Shared Portfolio forensic result

### 5.1 Prompt'un 21 sorusuna tek tek yanıt (ölçülmüş)

| # | Soru | Yanıt | Kanıt |
|---|---|---|---|
| 1 | Gerçek unified/global valuation clock var mı? | **KOD OLARAK VAR, PRODUCTION'DA HAYIR** | `execution/clock.py::iter_ticks`; production importer'ı yalnız `portfolio_engine.py` |
| 2 | Production worker timestamp outer-loop mu kullanıyor? | **HAYIR** | `jobs/backtest_engine.py:299` |
| 3 | Yoksa hâlâ item outer-loop mu? | **EVET, item outer-loop** | aynı satır |
| 4 | `run_portfolio` veya eşdeğeri var mı? | **VAR** | `domain/backtest/portfolio_engine.py:518` |
| 5a | Kim import ediyor? | **`src/` içinde: yalnız `execution/portfolio_projection.py`** (tip için) | grep, §5.2 |
| 5b | Kim çağırıyor? | **`src/` içinde HİÇ KİMSE** | `run_portfolio(` çağrısı `src/` altında sıfır |
| 5c | Production caller var mı? | **YOK** | containment gate testi bunu assert ediyor: `test_the_phase_loop_exists_but_no_production_path_reaches_it` |
| 5d | Test caller var mı? | **VAR — tek** | `tests/unit/oracles/portfolio_harness.py:238` |
| 6 | `ItemParticipant` veya eşdeğeri adaptör var mı? | **PROTOCOL VAR, GERÇEK IMPLEMENTASYON YOK** | `portfolio_engine.py:238` Protocol; tek implementor `tests/…/portfolio_harness.py::_ScriptedParticipant` |
| 7 | `_ItemStepper` veya stateful engine adaptörü var mı? | **VAR ve PRODUCTION'DA KULLANILIYOR** — ama portfolio için değil | `engine.py:756` + `:3350` `run_engine` içinde |
| 8 | Her Strategy aynı valuation point'te aynı `E(t)` görüyor mu? | **HAYIR** | her item kendi `_Ledger`'ı, `resolve_allocation_execution` her item'a TAM P0 veriyor |
| 9 | Mandatory exits önce mi uygulanıyor? | **Portfolio ekseninde HAYIR** (item içinde faz sırası var) | `_run_tick` production'a bağlı değil |
| 10 | Entry/scale intentleri shared snapshot sonrası mı? | **HAYIR** | shared snapshot production'da hiç yayımlanmıyor |
| 11 | Shared cash/reserve tek ledger üzerinde mi? | **HAYIR** | `execution/portfolio_ledger.py` unwired |
| 12 | Cross-item exposure tek portfolio state üzerinden mi? | **HAYIR — forward-only approximation** | `execution/rules.py::prior_exposure_at` + `prior_intervals` |
| 13 | Conflict arbitration simultaneous intents üzerinde mi? | **HAYIR — forward-only, asimetrik** | `rules.py::conflicts_with_prior`; simetrik olan `execution/arbitration.py` unwired |
| 14 | Heterogeneous timeframe alignment production path'te mi? | **HAYIR** | merged axis production'da yok |
| 15 | Production cancellation merged timeline içinde çalışıyor mu? | **HAYIR — item sınırında** | O-06 checkpoint #3, `for prepared in prepared_items` döngüsünün başında |
| 16 | Output gerçek `EngineOutput`a dönüşüyor mu? | **PROJEKSİYON VAR, ÇAĞRILMIYOR** | `portfolio_projection.py:513::project_portfolio_run` → `EngineOutput`; `src/` importer'ı **sıfır** |
| 17 | Result persistence bu unified outputu kullanıyor mu? | **HAYIR** | `create_result(engine_output=output)` — `output` `combine_item_runs`'tan geliyor |
| 18 | Manifest unified policy/version/timeline identity pinliyor mu? | **HAYIR** | `execution/provenance.py::build_portfolio_manifest` — `src/` çağıranı yok; `portfolio_simulation` anahtarı hiç yazılmıyor |
| 19 | Historical sequential Results immutable/readable kalıyor mu? | **EVET — ve dürüstçe etiketleniyor** | `portfolio_mode.py`, canlı flag'i **hiç okumaz**, yalnız pinli manifest+diagnostics'ten türetir |
| 20 | `SHARED_ALLOCATION_STATUS` current değeri? | **`future_dev`** | `domain/allocation/capability.py:110` |
| 21 | Flag'i açma koşulları sağlanmış mı? | **6'da 1** | aşağıdaki tablo |

### 5.2 Kanonik modüller: mevcut ama production'dan izole

`capability.py`'nin kendi REMOVAL CONDITION listesi (1–6) current main'e karşı ölçüldü:

| # | Koşul (`capability.py` kendi yazdığı) | Durum | Kanıt |
|---|---|---|---|
| 1 | Engine'in dış döngüsü MERGED timestamp axis | ❌ | `jobs/backtest_engine.py:299` item listesi |
| 2 | TEK shared ledger: P0, `R0 = P0·r`, `U0` | ⚠️ **kod var, bağlı değil** | `execution/portfolio_ledger.py` — importer'ları yalnız `portfolio_engine.py`, `arbitration.py`, `attribution.py`, `provenance.py` (hepsi contained) |
| 3 | Her valuation point'te tek `E(t)`, `Ci(t) = max(0,E(t)−R0)·wi/100` | ⚠️ **kod var, bağlı değil** | `portfolio_engine.py::_run_tick` PV fazı |
| 4 | Simetrik arbitration, id tie-break, share transfer yok | ⚠️ **kod var, bağlı değil** | `execution/arbitration.py` |
| 5 | doc 13 §14 test 11 geçiyor + eğri zaman-sıralı | ⚠️ **oracle'da geçiyor, production'da anlamsız** | `tests/unit/oracles/*` `run_portfolio` üzerinde |
| 6 | `ENGINE_VERSION` bump | ❌ | `manifest.py:126` değişmedi |

**Yalnız 1 koşul (dürüst hiçbiri) tamamen sağlanmış değil; 4'ü "kod var ama unwired".**

**Contained modüllerin tam listesi ve production importer'ları** (`grep` ile ölçüldü):

| Modül | `src/` importer'ı | Sınıf |
|---|---|---|
| `domain/backtest/portfolio_engine.py` (`run_portfolio`, `ItemParticipant`) | **YOK** (yalnız `portfolio_projection` tip için import eder) | IMPLEMENTED-BUT-UNWIRED |
| `execution/clock.py` | yalnız `portfolio_engine.py` | IMPLEMENTED-BUT-UNWIRED |
| `execution/intents.py` | `portfolio_engine`, `arbitration`, `provenance`, `portfolio_ledger`, `portfolio_projection` | IMPLEMENTED-BUT-UNWIRED |
| `execution/portfolio_ledger.py` | `portfolio_engine`, `arbitration`, `attribution`, `provenance` | IMPLEMENTED-BUT-UNWIRED |
| `execution/arbitration.py` | `portfolio_engine`, `provenance` | IMPLEMENTED-BUT-UNWIRED |
| `execution/attribution.py` | contained küme içi | IMPLEMENTED-BUT-UNWIRED |
| `execution/provenance.py` (`build_portfolio_manifest`) | **YOK** | IMPLEMENTED-BUT-UNWIRED |
| `execution/portfolio_projection.py` (`project_portfolio_run`) | **YOK** | IMPLEMENTED-BUT-UNWIRED |
| `domain/backtest/portfolio_mode.py` | `queries/backtest_run.py`, `queries/results_history.py` | **IMPLEMENTED-ACTIVE** (okuma yolu) |

`portfolio_mode.py` bu kümenin **tek üretim-aktif** üyesidir ve bu bir tasarım kararıdır:
bir Result'ın hangi ko-simülasyondan geldiğini **kendi pinli manifest+diagnostics'inden**
söyler, canlı flag'ten değil. Bugün her zaman `legacy_sequential` / `single_item` /
`unknown` döner — çünkü `portfolio_simulation` manifest bölümünü yazan
`build_portfolio_manifest`'in production çağıranı yok. Yani okuma yüzeyi **doğru ama
dejenere**: `unified_clock` dalı ulaşılamaz.

### 5.3 Erişilebilirlik hattı — nerede kesiliyor

```
[HTTP admission]  commands/backtest_run.py:542   ─── shared mode ise 409 readiness blocker
                                                     (fail-closed, manifest'ten ÖNCE)
[Ready Check]     domain/allocation/rules.py:154  ─── validate_allocation containment blocker
[UI]              frontend/src/pages/Portfolio.tsx:357-409
                                                  ─── server capability view render ediliyor
                                                      (data-testid="alloc-containment-note")
```

Üç bağımsız katman aynı `shared_allocation_is_executable()` fonksiyonundan okuyor.
Containment **fail-closed ve gerçekten fail-closed** — bu bir DELIBERATE-FUTURE-DEV, gizli
bir kusur değil.

### 5.4 Test forensics — TEST-OWNED SIMULATION vs PRODUCTION-WORKER EXECUTION

Bu, portföy testlerinin **en yanıltıcı** noktası ve açıkça kaydedilmeli:

| Katman | ADIM 18 ÖNCESİ | ADIM 18 SONRASI (bugün) |
|---|---|---|
| Faz sırası (P1→P3→PV→P4→P5/P6b→P7→P9) | test-owned driver | **PRODUCTION** — `portfolio_engine.py::_run_tick` |
| Merged clock / dedup / tie-break | test-owned | **PRODUCTION** — `execution/clock.py` |
| Sleeve aritmetiği, `E(t)`, `R0`/`U0` | test-owned | **PRODUCTION** — `execution/portfolio_ledger.py` |
| **Item KARARLARI** (entries / exits / funding / fees) | test-owned | **HÂLÂ TEST-OWNED** — `ScriptedItem` fixture verisi |
| **Item'ı `t`'ye ilerletme** | yok | **HÂLÂ YOK** — gerçek engine ile beslenmiş participant yok |
| **Gerçek worker** | hayır | **HAYIR** |
| **Gerçek DB** | hayır | **HAYIR** — 25 portfolio oracle'ı saf unit |
| **Gerçek Result persistence** | hayır | **HAYIR** |
| **Gerçek feature flag** | n/a | **HAYIR** — flag `future_dev`, testler flag'i baypas etmiyor, ona **hiç uğramıyor** |

`tests/unit/oracles/portfolio_harness.py` bu ayrımı kendi başlığında dürüstçe ilan ediyor
("What is still test-owned, and must stay disclosed: the DECISIONS"). **Oracle'lar LOOP'u
ve PRIMITIVE'leri kanıtlar; hiçbir item'ın sinyal mantığını, hiçbir worker davranışını,
hiçbir persistence yolunu kanıtlamaz.**

`tests/unit/oracles/test_oracle_portfolio_containment_gate.py::test_the_phase_loop_exists_but_no_production_path_reaches_it`
containment'ı **yapısal olarak** doğruluyor: `run_portfolio(` ya da `import run_portfolio`
içeren `src/` dosyalarının listesinin **boş** olmasını assert ediyor. Yani "production
caller yok" iddiası bu repoda **testle kilitli**, benim grep'imle değil.

### 5.5 PR B'nin önündeki gerçek engeller (ADIM 16 kickoff §4.1, current main'e karşı doğrulandı)

| Engel | Durum bugün | Ölçüm |
|---|---|---|
| **(a)** Stepper barı ATOMİK ilerletir; faz döngüsü aynı barı P1/P3/PV/P4'e **bölünmüş** ister | **AÇIK** | `_ItemStepper` artık `admit`/`carry`/`open_fills`/`held`/`entry`/`tail` hook'larını **ayrı ayrı** açıyor (`engine.py:756-796`) — yani (a) ADIM 16 (ADR §12) ile **kısmen** kapandı; ama `step(bar)` hâlâ hepsini tek çağrıda yapıyor ve `run_engine` onu öyle sürüyor. Fazları portfolio sırasında **item-dışı bir sürücüden** çağırmanın hiçbir production örneği yok. |
| **(b)** `entry` book-etmeyen bir değerlendirme girişi ister | **AÇIK** | `entry: Callable[..., None]` bir `equity` parametresi kabul ediyor ("the SHARED `E(t)` for a portfolio participant") — **niyet kodda var**, ama book-etmeden değerlendiren bir giriş yok. |
| **(c)** `PortfolioRun → EngineOutput` projeksiyonu | **KAPANDI (ADIM 35)** | `portfolio_projection.py:513::project_portfolio_run` → `EngineOutput` |
| **Ek** P2 pending fills + P8 same-direction scaling faz döngüsünde modellenmemiş | **AÇIK** | `portfolio_engine.py` docstring §2 + `UnsupportedIntentKindError`; **scaling açık HERHANGİ bir stratejide anında raise eder** |

> **(a) hakkında bir düzeltme, kayda geçsin:** `portfolio_engine.py`'nin HONEST BOUNDARY
> bloğu (satır 44-49) hâlâ *"ADR §12's **ADIM 16** stepper, which was never written
> (`grep -n "def step" engine.py` returns nothing)"* diyor. **Bu ifade bugün YANLIŞ** —
> stepper PR #602 ile yazıldı ve `engine.py:756`/`:3350`'de sevk edildi. Aynı bayat iddia
> `tests/unit/oracles/portfolio_harness.py` başlığında ve containment gate testinin
> docstring'inde de tekrarlanıyor. Kod doğru, **üç yerdeki yorum bayat** →
> DOCUMENTATION-DRIFT (§13.4).

### 5.6 Git history forensics — shared allocation ekseni

Son 100 commit'te `domain/backtest/execution/` veya `portfolio_engine.py`'ye dokunan
**tek bir `feat`/`fix` yok**. En son ilgili slice'lar:

| Slice | PR | Ne getirdi | Yarım bırakıldı mı |
|---|---|---|---|
| ADIM 15 | #567 | merged-axis clock | hayır — bilinçli olarak "unused" |
| ADIM 16 (sevk edilen) | #571/#572 | intent katmanı | hayır |
| ADIM 17 | #573 | shared ledger | hayır |
| ADIM 18 | (phase loop) | `run_portfolio` | **EVET — worker call site'ı olmadan** (ADR §12 correction note'ta açıkça kaydedilmiş) |
| ADIM 18 | #575 | arbitration | hayır |
| ADIM 19 | #581 | result provenance | hayır |
| ADIM 20 | #583/#584 | manifest + containment lift | **BLOCKED (#582)** |
| ADIM 16 (ADR §12) | #602 | resumable stepper | hayır — 46 golden digest kımıldamadı |
| ADIM 35 | #659 | `project_portfolio_run` | **EVET — üretim yolu bilerek yazılmadı** |

**Follow-up planlanmış mı: EVET, adı "PR B"** ve `CLAUDE.md` §Next + `ADIM35_LANDED_KICKOFF.md`
onu **ADR §16 insan kapısının** arkasına koyuyor. Bu bir unutulmuş iş değil, **bilinçli
olarak bir insan kararının arkasında bekleyen** bir slice.

### 5.7 Sınıflandırma

**`IMPLEMENTED-BUT-UNWIRED`** (davranışın kendisi) + **`IMPLEMENTED-BUT-CONTAINED`**
(kullanıcıya dönük mod) + **`PRODUCT-DECISION-REQUIRED`** (PR B'nin başlaması için ADR §16
kapısı + ADR amendment'ı). **CONFIRMED-MISSING olan tek şey `ItemParticipant` adaptörü ve
`jobs/backtest_engine.py:299` çağrı yeridir.**

**Confidence: HIGH.** Her iddia hem grep hem de repo'nun kendi containment testiyle
çift-doğrulandı.

---

## 6. Position sizing forensic result

### 6.1 Ölçüm

| Katman | Dosya:satır | Ne diyor |
|---|---|---|
| **Master Ref §10.1** | `Entropia_V18_Master_Technical_Reference_v1_0.md:7552` | `Base Position Size ⓘ \| Position Size %. \| **Resolved capitalın yüzdesi.**` |
| **doc 02 ⓘ** | `02_…v1_1.md:1875` | *"Equity 10.000 USD ve Position Size %10 ise ilk pozisyon nominal olarak **1.000 USD** üzerinden oluşturulur"* |
| **V18 mockup** | `index_guncellenmis_duzeltilmis_v18.html:6225` | aynı örnek, aynı yüzde okuması |
| **doc 02 / Master Ref — Max Single Position** | `:1920` / `:6228` | *"Max Single Position %25 ise … tek pozisyon **equity'nin %25'inden** büyük açılamaz"* |
| **SHIPPED UI** | `frontend/src/components/StrategyConfigForm.tsx:590-686` | `unit="%"` — **üç alanda da** (`base_position_size`, `min_position_size`, `max_position_size`) |
| **ENGINE** | `backend/src/entropia/domain/backtest/execution/sizing.py:215-216` | `if sizing.method == "base_position_size" … return Decimal(sizing.base_position_size)` — **çarpan yok, bölen yok, equity okunmuyor** |
| **ENGINE (limits)** | `sizing.py:183-184` docstring | *"Caps are in the **same UNITS as the size (contracts/coins)**, applied verbatim (unquantized)"* |
| **SCHEMA** | `domain/strategy/config.py:711`, `:770-771` | `Decimal \| None`, **birim yok, `gt=0` yok, `le=100` yok** |

### 6.2 Karşı-kanıt kontrolü (negatif kontrol)

Aynı formdaki `risk_percentage_per_trade` **hem UI'da `unit="%"` hem motorda gerçek
yüzde**: `sizing.py:220` `risk_capital = usable_equity * risk.risk_percentage_per_trade / _HUNDRED`.
Yani "bu motor yüzdeyi bilmiyor" savunması geçersiz — **yüzde okuması bu modülde zaten
uygulanmış**; üç alan istisnadır.

### 6.3 GitHub durumu

#550 **CLOSED (completed)**, `closed_by_pull_requests: []`. Issue'nun tek yorumu
(2026-08-04, OWNER):

> **Decision: option A — adopt canon.** … A was chosen. The deciding argument is that the
> product currently **shows the user a `%` sign** and then does something else with the
> number.

Yani **ürün kararı VERİLDİ ve kanona uyma yönünde**; kararın gerektirdiği hiçbir şey
(percent aritmetiği, `ENGINE_VERSION` bump, golden-digest refresh, kayıtlı revizyonlar için
görünür transition gate) **sevk edilmedi**. `ENGINE_VERSION` hâlâ
`backtest-engine-v18-gap-adjusted-stop-fill`.

Kusuru pinleyen oracle'lar yerinde duruyor:
`tests/unit/oracles/test_oracle_sizing.py:48::test_base_position_size_is_taken_as_the_size`.

### 6.4 Finansal büyüklük

Issue'nun tablosu current koda karşı yeniden doğrulandı: `base_position_size = 10`,
equity 10 000, fiyat 10 000 → kanonik 1 000 USD nominal (0.1 unit), sevk edilen
**100 000 USD nominal (10 unit)** = hesabın **10 katı**. `max_position_size` kurtarmıyor —
o da aynı tartışmalı birimde.

### 6.5 Sınıflandırma

**`STILL-BROKEN`** + **`ISSUE-STATE-DRIFT`** (issue kapalı, kusur canlı) +
**`PRODUCT-DECISION-MADE-BUT-UNIMPLEMENTED`** (prompt taksonomisinde en yakın kutu
`PRODUCT-DECISION-REQUIRED` değil — karar verilmiş, uygulama borcu var).

**Confidence: HIGH.**

---

## 7. Zero-size trade forensic result

### 7.1 Ölçüm

`backend/src/entropia/domain/backtest/engine.py:1461-1463`:

```python
size = _planned_size(direction, fill_raw, strength)
if alloc_on and size <= _ZERO:
    return None
```

**`alloc_on and` hâlâ orada.** Guard yalnız allocation modunda. Independent mod (varsayılan)
0-size bir pozisyon açar, 0.00 PnL ile kapatır.

### 7.2 Ulaşılabilir yollar (current main)

| Yol | Ulaşılabilir mi | Neden |
|---|---|---|
| `min_position_size > max_position_size` | **EVET** | `sizing.py::_clamp_to_limits` bu pencerede `_ZERO` döner; şema `min ≤ max` doğrulaması taşımıyor |
| `base_position_size = "0"` | **EVET** | `config.py:711` `gt=0` **yok** — yalnız `method=base` iken *varlığı* zorunlu, pozitifliği değil |
| Kelly non-positive edge (`W=0.3, R=1`) | **EVET** | `_kelly_capital_fraction` `max(fraction*edge, _ZERO)` → 0; `_raw_position_size` 0 döner |
| `risk_based_sizing` (**bust equity**) | **EVET — ve tablonun en pahalı yolu** | **İKİ KEZ düzeltildi (PR #700 review).** Önce `HAYIR / şema gt=0`, sonra `HAYIR / iki bacak da korumalı` yazıyordu; **hüküm de yanlıştı.** Guard'lar (`stop_loss_point > 0` + `sizing.py:217` `usable_equity = max(equity, _ZERO)`) size'ın **negatif** olmasını engelliyor, **sıfır** olmasını değil — ve §7'nin sorduğu tam olarak sıfır. `equity <= 0` iken `risk_capital = 0` → size **0**; Kelly de aynı. Uçtan uca ölçüldü (`initial_capital=10.00`, `commission=7`, risk 2% / stop 4): bust hesapta `entry_fill size=0E-8` ve **tam bir komisyon round trip'i** — `pnl = -14.00`, `final_equity` `-4.15` → `-18.15`. Diğer üç yol yalnız metriği kirletiyor; **bu ayrıca para kaybettiriyor.** Yol spekülatif değil, `_open` docstring'i (`engine.py:1435-1436`) onu *"Independent mode books even a bust-equity 0-size fill (preserving the risk-based no-phantom-profit invariant)"* diye **bilinçli invariant** olarak adlandırıyor. |
| `max_position_size = 0` (tek başına, `min` olmadan) | **EVET** | `_clamp_to_limits` size'ı `maximum`'a indirir → `entry_fill size=0`, 1 trade. Tabloda **yoktu** (PR #700 review) |
| `base_position_size = "-5"` (**negatif**) | **EVET — sıfırdan ağır** | `_clamp_to_limits` non-positive girdide kısa devre yapar (`sizing.py:184`) ve `config.py:711` `gt=0` taşımaz → negatif size'lı pozisyon açılır ve **PnL işaretini tersine çevirir** (ölçüldü: lehte +2.00 hareket eden barda `pnl = -10.00`, `peak_notional = -510.00`). `_raw_position_size` docstring'i (`:209-212`) bu tehlikeyi adlandırıyor ama yalnız **equity** bacağına uyguluyor. Tabloda **yoktu** (PR #700 review) |
| allocation sleeve `wi = 0` | **HAYIR — doğru davranıyor** | `alloc_on` true, guard devrede, `sleeve_zero_capacity` reason'ı ile `entry_blocked` |

Yani **doğru davranış, doğru decision-trace event'i ve doğru reason ladder'ı zaten
uygulanmış** — sadece `alloc_on` olmadan ulaşılamaz. Bu, #551'in ana argümanıydı ve
current main'de aynen geçerli.

### 7.3 Cross-item sızıntı — **ÜRETİLEMEDİ (bu build'de filtreleniyor)**

> **DÜZELTME (PR #700 review, ölçüm: `docs/audit/closure_w0_financial_semantics_2026-08-13.md`
> §2.2, PR #708).** Bu bölüm önce *"doğrulandı"* diyordu. **Yanlıştı** ve yanlışlığın
> biçimi kaydedilmeye değer: okuma tek bir dosyada durdu, boru hattı izlenmedi.

Alıntılanan kod doğru — `execution/rules.py::conflicts_with_prior` gerçekten yalnız
`direction`'a bakar, `peak_notional`'ı hiç okumaz:

```python
for iv in rules.prior_intervals:
    if iv.direction == direction:
        continue
    ...
    return True
```

**Ama gate `led.position_intervals`'ı tüketmiyor — `rules.prior_intervals`'ı tüketiyor, ve
ikisinin arasında bir filtre var.** `PriorItemInterval` üretmenin `src/` içindeki tek yolu
`domain/backtest/engine.py::build_prior_intervals` (tek production çağıranı
`application/jobs/backtest_engine.py:333-334`; diğer tek `PortfolioRules(...)` kurulumu
`engine.py:688` ve orada `prior_intervals=()`), ve o da non-positive notional'ı **gate
görmeden önce** düşürür (`engine.py:721-723`):

```python
notional = _safe_decimal(iv.get("peak_notional"))
if notional is None or notional <= _ZERO:
    continue
```

Gerçek boru hattı üzerinden ölçüm, **pozitif kontrolle**:

| item | `EngineOutput.position_intervals` | `build_prior_intervals` sonrası | `conflicts_with_prior(dir="short")` |
|---|---|---|---|
| **hayalet** (`base_position_size = 0`) | `['0.00']` | **0 interval** | **`False`** — blok YOK |
| **gerçek** (`base_position_size = 50`) | `['5100.00']` | 1 interval | `True` — bloklar, tasarlandığı gibi |

Gerçek item'ın bloklaması probe'un duyarlı olduğunu kanıtlar (negatif kontrol). Davranış
ayrıca **zaten pinli**:
`tests/unit/test_backtest_portfolio_rules.py::test_build_prior_intervals_fails_closed_on_bad_bounds_and_drops_zero_notional`.

**Sonuç: hayalet pozisyon başka bir item'ın girişini engelleyemez; kusur kompozisyon
düzeyinde DEĞİLDİR.** §7.6'nın şiddet iddiası buna göre düzeltildi.

**Ders (bu denetimin kendi yöntem hatası):** bu, `#551`'in gövdesindeki **aynı** okuma
hatasının tekrarıdır — o da `rules.py`'ı tek başına okumuştu. İki belgenin uyuşması
bağımsız doğrulama değil, **tekrarlanmış tek bir okuma**. Bir tüketiciyi okumak yetmez;
üreticisini ve arasındaki her filtreyi izle.

### 7.4 Trade sayımı / win-rate paydası

`booking.py::close_position`: `if pnl > _ZERO: winners… else: led.gross_loss += -pnl`.
0.00 PnL'lik bir lot **kayıp tarafına** düşer → `total_trades`, `win_rate` paydası,
ortalama işlem ve expectancy hepsi seyrelir. Current kodda doğrulandı.

### 7.5 GitHub durumu

#551 **CLOSED (completed)**, `closed_by_pull_requests: []`, main'de kusuru onaran commit
yok. Kusuru **bilerek pinleyen** oracle yerinde:
`test_oracle_sizing.py:211::test_a_min_above_max_window_books_a_zero_size_trade`.

### 7.6 Sınıflandırma

**`STILL-BROKEN`** + **`ISSUE-STATE-DRIFT`** — **sınıflandırma DEĞİŞMEDİ, şiddet değişti.**

Kusur duruyor: hayalet pozisyon açılıyor, `total_trades` / `win_rate` paydası / ortalama
işlem / expectancy seyreliyor (§7.4 aynen geçerli), ve `commission > 0` iken hayalet
pozisyon **tam bir round trip ödüyor** (ölçüldü: `pnl = -14.00`, `final_equity = 9986.00`).
Ama §7.3'ün düzeltmesinden sonra kusur **metrik/artifact + maliyet düzeyindedir**,
kompozisyon düzeyinde değil.

**Confidence: MEDIUM** (§7.3 bir kez yanlış ölçüldüğü için bu kalem için indirildi;
§7.4 ve maliyet bacağı doğrudan ölçümle duruyor).

**Düzeltme iki kelimelik bir yama DEĞİL — bir ürün kararı.** #551'in önerdiği
`if size <= _ZERO: return None`, §7.2'nin bust-equity satırını da bastırır; o satır
`_open` docstring'inde (`engine.py:1435-1436`) **bilinçli bir invariant** olarak
adlandırılıyor (*risk-based no-phantom-profit*). Yani guard'ı genelleştirmek belgelenmiş
bir davranışı değiştirir ve PO'ya sorulmalıdır — #708'in denetiminde **PO-4** olarak
kayıtlı. `ENGINE_VERSION` bump'ı zaten gerekiyordu; bu karar onunla aynı slice'ta verilmeli.

---

## 8. Commission forensic result

### 8.1 Ölçüm

`backend/src/entropia/domain/backtest/execution/booking.py:93`:

```python
commission_lot = costs.commission * 2 if is_full else costs.commission * 2 * fraction
```

Docstring (`:82-84`), aynı fonksiyon:

> *"Commission is charged proportional to the fraction so N partial lots summing to the
> whole position pay exactly **one round-trip**."*

**Bu iddia yalnızca pozisyon TAMAMEN partial lot'larla kapandığında doğru.** Normal şekil —
bir partial close, sonra kalanın full close'u — daha fazla ödüyor, çünkü son kapanış
`is_full` olduğu için kalan boyut ne olursa olsun **tam bir round trip** alıyor.

### 8.2 Modeller ve hiçbirine uymayan sonuç

Issue'nun hesabı current koda karşı yeniden doğrulandı (long 50 @102, commission 7/fill,
`close_percentage=40`, kalan breakeven'de stop):

| Lot | boyut | gross | komisyon | pnl |
|---|---|---|---|---|
| partial | 20 | −60.00 | 14.00 × 0.4 = **5.60** | −65.60 |
| kalan (full) | 30 | 0.00 | **14.00** | −14.00 |

Toplam **19.60**. Üç fill için per-fill model **21.00** derdi; docstring'in tek round
trip'i **14.00** derdi. **Sevk edilen davranış ikisine de eşit değil.**

### 8.3 Kanonik / şema durumu

| Kaynak | Ne diyor |
|---|---|
| `costs.commission` şema açıklaması | *"Per-trade fee"* → **per-FILL** okuması |
| Master Ref §8 | *"komisyon dağılımı engine manifestinde açık olmalıdır"* → dağılımın **belirtilmiş** olması gerekiyor |
| `booking.py` docstring | tek round-trip |
| sevk edilen kod | `1 + Σ fraction` round trip |

**Kanon per-fill'e işaret ediyor, docstring tek round trip'e, kod ikisine de değil.**
Komisyon **fill sayısıyla değil, partial close sayısıyla** ölçekleniyor: üç adımda scale-out
yapan bir strateji **dört fill için 1.7 round trip** ödüyor.

Yön olarak **conservative (fazla ücretlendirme)** — bu yüzden fark edilmemiş — ama maliyet
modeli config'ten yeniden üretilemez hâle geliyor.

### 8.4 Oracle durumu

`tests/unit/oracles/test_oracle_position_lifecycle.py:140::test_a_partial_lot_pays_commission_in_proportion_but_the_final_close_pays_a_full_one`
— **kusuru adıyla pinliyor.** Yani suite yeşilken bile bu davranış "doğru" değil,
"donmuş".

### 8.5 GitHub durumu

#552 **CLOSED (completed)**, `closed_by_pull_requests: []`, onaran commit yok.

### 8.6 Sınıflandırma

**`STILL-BROKEN`** + **`ISSUE-STATE-DRIFT`** + **`DOCUMENTATION-DRIFT`** (docstring kodla
çelişiyor) + **`PRODUCT-DECISION-REQUIRED`** (per-fill mi, tek round-trip mi — issue bunu
"decide the model explicitly" diye bırakmış ve **karar hiç verilmemiş**, #550'nin aksine).

**Confidence: HIGH.**

---

## 9. Research provenance forensic result

### 9.1 Üç yüzeyin karşılaştırması (ölçüldü)

| Alan | Agent Data Bundle | Backtest Evidence Bundle | Run Context Manifest |
|---|---|---|---|
| `research_revision_id` | ✅ | ✅ | ✅ (`revision_id`) |
| `research_content_hash` | ✅ | ✅ | ✅ (`content_hash` + `pinned_content_hash`) |
| `usage_scope` | ✅ | ✅ | ✅ |
| `market_dataset_revision_id` | ✅ | ✅ | ✅ (`linked_market_dataset_revision_id`) |
| `market_content_hash` | ✅ | ✅ | — |
| **`available_time_policy`** | ❌ | ❌ | ✅ |
| **`available_delay_seconds`** | ❌ | ❌ | ✅ |
| **`event_time_semantics`** | ❌ | ❌ | ✅ |
| `frequency_policy` | ❌ | ❌ | ✅ |
| `source_timezone_mode` / `_iana` | ❌ | ❌ | ✅ |
| **`instrument_mapping_ref`** | ❌ | ❌ | ✅ |
| **`feature_definitions[]`** | ❌ | ❌ | ✅ |
| `field_definition_version` | ❌ | ❌ | ✅ |
| **`alignment_policy_versions[]`** | ❌ | ❌ | ❌ |
| **`missing_and_stale_policies[]`** | ❌ | ❌ | ❌ |
| `resolved_at` / `compiler_version` / `bundle_hash` | ✅ | ✅ | n/a |

Kaynak: `application/jobs/research_data.py` — `compile_agent_data_bundle` member şekli
(5 anahtar) ve `compile_backtest_evidence_bundle` member şekli (**aynı 5 anahtar**);
`application/commands/backtest_run_context.py:371-398`.

### 9.2 Bundle hash policy alanlarını kapsıyor mu — HAYIR

`research_data.py::_seal_bundle`:

```python
body = {"bundle_kind": …, "members": members,
        "compiler_version": _BUNDLE_COMPILER_VERSION, **extra}
bundle_hash = manifest_hash(body)
```

`members` zaman politikası taşımadığı için **`bundle_hash` bir time-policy değişikliği
altında değişmez**. Bir bundle, kendi içeriğinden hangi availability kuralı altında
derlendiğini **attest edemez**. `content_hash` bunu kapatmıyor: o payload byte'larını
kapsar, revizyonun timing metadata'sını değil.

**Doğrula-ama-kaydetme asimetrisi:** `admit_bundle_member(..., for_execution=True)` yolu
`_ensure_time_policy_valid(revision)` çağırıyor — yani politika **doğrulanıyor**, sonra
**atılıyor**.

### 9.3 Strict xfail — tam node ID

```
backend/tests/integration/test_research_point_in_time_parity.py:583
    ::test_both_bundles_pin_the_available_time_policy
    @pytest.mark.xfail(strict=True, reason="GH #558 — …")
```

`docs/generated/repository_facts.md`: **`Backend xfail markers | 1 (1 strict)`**. Yani bu
repodaki **tek** bilinçli strict xfail budur ve #558'e bağlıdır. ADIM 16 kickoff'unun
"A17 (4 strict xfail — #556 ×2, #557, #558)" satırı **bayat**: diğer üçü düzeltildi.

### 9.4 GitHub durumu — prompt'un varsayımı yanlış

Görev metni *"GitHub #558 CLOSED olsa bile"* diyor. **#558 KAPALI DEĞİL:**
`state: open`, `state_reason: reopened`, `labels: [product-decision]`, son güncelleme
2026-08-12. `CLAUDE.md` de onu doğru şekilde açık gösteriyor. Burada issue-state drift
**yok**; kayıt dürüst.

### 9.5 Ek gözlem — manifestin araştırma pini yalnız `funding` rolünde

`backtest_run_context.py:56` `_FUNDING_ROLE = "funding"`; zengin `revision` alt-sözlüğünü
üreten tek yol bu rol. Bir research revizyonunun **funding dışı** bir yoldan run'a girmesi
durumunda aynı zengin pin'in üretildiğine dair kanıt bulamadım. Bu, #558'in kapsamının bir
adım ötesi ve **bu auditte kanıtlanmadı** → aşağıda LOW confidence olarak listelendi.

### 9.6 Sınıflandırma

**`PARTIAL`** (üç yüzeyden biri tam, ikisi eksik) + **`PRODUCT-DECISION-REQUIRED`**
(§9.2 field'ları member'a mı, top-level array'e mi; `bundle_hash` şekil değişikliği; diğer
dört §9.2 alanı V1'de mi). **Confidence: HIGH** (§9.5 hariç — o LOW).

---

## 10. Performance residuals

### 10.1 #617 / #618 — kod ONARILDI, issue AÇIK

| Surface | Budget (`docs/performance/query_budgets.json`) | Production kodu | Sonuç |
|---|---|---|---|
| `readiness_check.market_data_leg` | `queries_small 2 / queries_large 2 / per_item 0` | `readiness_check.py:404` `market_repo.get_revisions(...)` **IN()**, `:411` `market_repo.get_dataset_roots(...)` **IN()**, ikisi de **döngü DIŞINDA** | **ONARILDI** |
| `dependency_pins.ensure_pinned_resolvers_active` | `2 / 2 / 0` | `queries/dependency_pins.py:125::_prefetch` — `get_registry_by_keys` IN() → `get_revisions` IN(); `_pin_defect` saf fonksiyon | **ONARILDI** |

`_prefetch`'in **batch SIRASI** kritik ve kodda doğru: `embedded_revision_id` vermeyen bir
ref, entry'nin `trusted_active_revision_id`'sine düşer → revizyon batch'i registry'den
**sonra** kurulmak zorunda.

Her ikisi de **PR #681 (`6da8a95`)** ile main'e indi. **Issue'lar #617 ve #618 hâlâ OPEN
(reopened).** → **ISSUE-STATE-DRIFT (ters yön: open issue, already fixed).**

### 10.2 YENİ BULGU — Ready Check'te iki adet ÖLÇÜLMEMİŞ N+1 kaldı

Budget yalnız **market-data leg**'i kapsıyor. Aynı sayfada, aynı kullanıcı beklerken,
**iki başka leg hâlâ döngü içinde tekil `get_dataset_root` çağırıyor:**

| Konum | Fonksiyon | Döngü ekseni | Kod |
|---|---|---|---|
| `application/commands/readiness_check.py:554` | `_resolve_signal_market_data_issues` | **Trading Signal item / OHLCV fallback pin** | `root = await market_repo.get_dataset_root(session, revision.entity_id) if revision is not None else None` — `for item, config, ref in signals:` **İÇİNDE** |
| `application/commands/readiness_check.py:749` | `_resolve_research_sources` | **funding'li Strategy item** | `root = await research_repo.get_dataset_root(session, revision.entity_id)` — `for item, config, revision_id in funded:` **İÇİNDE** |

İki fonksiyon da revizyonları O-24b tarzı bir `IN()` ile batch'liyor (`:549`, `:746`) — yani
**birinci leg batched, ikinci leg değil**, tam olarak #617'nin tarif ettiği şekil.

**Neden gate yakalamıyor:** `backend/tests/integration/test_query_budgets.py:304::test_ready_check_market_data_leg`
fixture'ı `_resolve_market_data_issues`'ı **doğrudan** çağırıyor —
`run_readiness_check`'in tamamını değil. Ne Trading Signal item'ı ne funding'li Strategy
item'ı üretiyor. Yani bu iki leg **hiç budget'lanmamış**; slope gate'i onlar için hiçbir şey
söylemiyor.

`readiness_check.py` içinde döngü-içi tekil `get_dataset_root` **kalmadı** iddiası
dolayısıyla **yanlıştır**; doğru iddia "market-data leg'inde kalmadı"dır.

**Sınıflandırma: `PARTIAL`** (N+1 onarımı üç leg'in birinde tamamlandı) — CONFIRMED, yeni,
hiçbir issue'da kayıtlı değil. **Confidence: HIGH** (kod okuması kesin; **ölçülmedi** —
statement sayısı koşulmadı, o yüzden "kaç round trip" değil "döngü içinde bir read var"
diye rapor ediliyor).

### 10.3 Ratchet mekanizması sağlıklı

`query_budgets.json` bir **ratchet**: altına inmek "tighten-me" satırı basar, üstüne çıkmak
build'i kırar. `per_item` slope'u N+1 dedektörüdür ve küçük-n toplamı değişmese bile
yakalar. Bu mekanizma doğru kurulmuş; sorun **kapsam**, mekanizma değil.

---

## 11. Observability delivery status

Prompt'un istediği dört katman **ayrı ayrı** ölçüldü:

| Katman | Durum | Kanıt | CI'da bloklayıcı mı |
|---|---|---|---|
| **DETECTION** | ✅ VAR | `ops/alerts/entropia.rules.yml` — 11 kural (7 `severity: page`, 4 `severity: ticket`) | — |
| **VALIDATION** | ✅ VAR | `scripts/alert-rules-gate.sh` → `promtool check config` + `check rules` + `test rules`, digest-pinned Prometheus image; `ops/alerts/entropia.rules.test.yml` | **EVET** (`ci.yml` job `alerts`) |
| **ROUTING** | ✅ VAR | `ops/alertmanager/alertmanager.yml` — page/ticket ayrımı receiver + timing ile; 3 inhibit rule; `scripts/alert-notification-gate.sh` → `amtool check-config` + `amtool config routes test`; ek olarak `backend/tests/contract/test_alert_notification_contract.py` **yapısal** kontrol (çünkü `amtool` sıfır notifier config'li bir receiver'a SUCCESS döndürüyor — ölçülmüş) | **EVET** (aynı job) |
| **DELIVERY** | ⚠️ **KANITLANABİLİR AMA KAPI DEĞİL** | `scripts/alert-notification-proof.sh` — 4 faz: fail-closed / up / provenance (config hash + `--config.file`) / gerçek `EntropiaApiDown` alert'inin loglayan bir receiver'a POST'lanması. **Sentetik fixture yok.** | **HAYIR — bilinçli** (script başlığı: *"IT IS NOT A CI GATE, deliberately and honestly"*) |

### 11.1 Fail-closed tasarımı — doğrulandı

`alertmanager.yml` hiçbir varsayılan URL, placeholder receiver, `receiver: null` veya
notifier'sız receiver taşımıyor. İki receiver da endpoint'i `url_file`'dan okuyor;
`ops/alertmanager/entrypoint.sh` `ALERTMANAGER_NOTIFY_URL` set değilse/boşsa/URL değilse
Alertmanager'ı **exec etmeyi reddediyor**. Kök route **gerçek bir receiver** (`entropia-page`)
— eşleşmeyen alert düşürülmüyor, sayfalanıyor.

### 11.2 Kapanmamış üç artık (CLAUDE.md'nin iddiası doğrulandı)

1. **Kurallar gerçek production serilerine karşı hiç değerlendirilmedi.** `entropia.rules.test.yml`
   promtool unit test'idir; repo içinde kapatılamaz.
2. **Delivery proof'u CI kapısı değil** — her PR'da koşmuyor, yalnız release evidence olarak
   elle koşuluyor (`docs/releases/evidence/2026-08-10/P10B_alert_notification_path.md`).
3. **Monitörü izleyen yok** — Alertmanager'ın kendi sağlığını izleyen bir katman repoda yok.

### 11.3 Sınıflandırma

DETECTION / VALIDATION / ROUTING → **`IMPLEMENTED-ACTIVE`**.
DELIVERY → **`PARTIAL`** (mekanizma tam, sürekli kanıt yok).
**Prometheus rule'un fire edebiliyor olması insan notification delivery DEĞİLDİR** ve bu
repo bunu kendi CI job adını değiştirerek (*"Alert rules and notification path"*) ve script
başlığında açıkça yazarak kabul ediyor. **Confidence: HIGH.**

---

## 12. Accessibility evidence status

Prompt'un istediği sekiz eksen ayrı ayrı:

| # | Eksen | Durum | Kanıt |
|---|---|---|---|
| 1 | **Automated axe** | ✅ CI'da **bloklayıcı** ratchet | `.github/workflows/e2e.yml` job `A11Y — axe-core scan vs. the seeded stack (R2-14)` → `npm run a11y`; taban `frontend/e2e/a11y-baseline.json` |
| 2 | **Keyboard / precheck** | ✅ VAR, bloklayıcı | aynı komut; ADIM 38/39/50 ile 23/23 rota + tab sırası |
| 3 | **Human audit preparation** | ✅ TAMAM | `scripts/a11y-audit-stack.sh` yığını 9/9, `docs/implementation/a11y_screen_reader_audit_checklist.md`, denetçi runbook'u |
| 4 | **Real NVDA (SR-1) results** | ❌ **HİÇ BAŞLAMADI** | `docs/audit/a11y_screen_reader_audit_results.md` §1: *"SR-1 Section A completion: 0 / 23 routes"*, §2: *"0 / 10 flows"* |
| 5 | **Real VoiceOver (SR-2) results** | ⚠️ **BAŞLADI, BİTMEDİ** | §Session log: 1 oturum, 2026-08-12, rota 1 `/` yalnız A-1 + A-2 → **2 / 184 Section A hücresi**, **0 / 10 flow** |
| 6 | **Findings** | ⭕ **BOŞ (vacuous)** | §3 Findings register — 0 kayıt. Belge bunu açıkça *"empty, not met"* diye nitelendiriyor |
| 7 | **Retests** | ⭕ 8 madde de ☐ | §4 |
| 8 | **Signed deviations** | ⚠️ **BİR TANE VAR ve ürünü uyumsuz kılıyor** | **D-10 (2026-07-30)** — 45 düğüm imza-mavisi, WCAG 2.2 AA **1.4.3 karşılanmıyor** (`repository_facts.md`: *"a11y frozen serious nodes … 45 across 23 pages"*) |

### 12.1 Çıkış kriterleri

`a11y_screen_reader_audit_results.md` §5 — **dördü de ☐**:

| # | Kriter | Durum |
|---|---|---|
| 1 | Hem SR-1 hem SR-2 koşuldu | ☐ (**0/2**) |
| 2 | Section A 23 rotada, Section B 10 akışta, iki kombinasyon için | ☐ (**0/46** rota, **0/20** akış) |
| 3 | Her bulgu `FIX` veya `PO-APPROVE` taşıyor | ☐ (**boş**, karşılanmış değil) |
| 4 | Her `FIX` landed ya da PO-imzalı sapma | ☐ (**boş**) |

Belge kendi kuralını yazıyor: *"Until all four are ☑, **no document may show A-08 as
`Complete` or `PASS`**"*.

### 12.2 Tracking issue

**#514 OPEN** (`state_reason: reopened`, 2026-08-12T11:08:58Z insan eliyle yeniden açıldı),
`human-only` etiketli. Prompt'un *"Issue #514 CLOSED olsa bile"* varsayımı **current main
için geçerli değil** — kayıt bugün dürüst. Ama uyarı yine de doğru: bu issue **iki kez
kanıtsız kapatılmıştı** (2026-07-30 ve 2026-08-07), ve kapı issue durumu değil §5 çıkış
kriterleridir.

### 12.3 Sınıflandırma

**`PARTIAL`** (otomasyon tam ve bloklayıcı; insan denetimi %1'in altında) —
**RELEASE BLOCKER.** Ayrıca **D-10 imzalı kalıcı sapması** nedeniyle ürün **WCAG 2.2 AA
1.4.3** için uyumlu sayılamaz; bu bir eksik iş değil, **imzalanmış bir sapma**.
**Confidence: HIGH.**

---

## 13. Documentation drift

### 13.1 `CLAUDE.md` — HEAD sha bayat (yapısal, beklenen)

| İddia | Gerçek |
|---|---|
| `HEAD 108f16b` | **`e2fa521`** — 4 commit ileride (`8fa0767`, `8579897`, `f09e5b9`, `e2fa521`) |

CLAUDE.md kendi başlığında bunu ilan ediyor (*"içindeki HEAD sha'sı yapısal olarak
bayattır"*), yani bu bir kusur değil, **bilinen bir sınır**. Alembic head, `ENGINE_VERSION`
ve `SHARED_ALLOCATION_STATUS` iddiaları `repository_facts.md` ile **birebir tutuyor**.

### 13.2 `CLAUDE.md` — İKİ FARKLI test/coverage sayısı, aynı dosyada

| Satır | İddia |
|---|---|
| `CLAUDE.md:75` (§Conventions ▸ Local verify) | *"ölçülen toplam **%92.06**, **2712 passed**; frontend **%84.67** line"* |
| `CLAUDE.md:465-467` (§Current position ▸ Testler) | *"Backend tam suite **3987 passed** / 1 xfailed / 0 failed, coverage **%93.53**; frontend **721 passed / 70 dosya**, **%84.92** line"* |
| `CLAUDE.md:241-242` (§Current position ▸ ADIM 50) | frontend **722 passed / 71 dosya**, **%84.90** |
| `README.md:730` | *"measured: **92.06%**"* |

**Üç farklı frontend sayısı ve iki farklı backend coverage sayısı aynı otorite belgesinde
yan yana duruyor.** `docs/generated/repository_facts.md` hiçbirini doğrulamıyor — o
bilinçli olarak *collected* sayar (**3538 in 337 files**) ve *"Only a full CI run reports
passes"* der. Bu **gerçek bir drift**, yapısal bir sınır değil: §75 bloğu bir önceki dalganın
ölçümüyle donmuş.

→ **`DOCUMENTATION-DRIFT`**, ama **düşük risk** (sayılar davranış değil, ve gerçek kapı CI).

### 13.3 `CLAUDE.md` §Next — hâlâ doğru

*"**Next:** PR B — `ItemParticipant` adaptörü + `jobs/backtest_engine.py:298` call site"*.
Satır numarası bugün **299** (bir commit kaydırmış), geri kalanı **tamamen doğru** ve
ADR §16 insan kapısı vurgusu yerinde. **Bu bir stale next-step DEĞİL.**

### 13.4 Production kaynağı içinde bayat yorum — üç yerde aynı yanlış

`domain/backtest/portfolio_engine.py:44-49` (HONEST BOUNDARY §1):

> *"Wiring it needs an `ItemParticipant` backed by the real engine … ADR §12's **ADIM 16**
> stepper, **which was never written** (`grep -n "def step" engine.py` returns nothing; the
> bar loop is nested at `engine.py:1782` inside a ~1100-line function)."*

**Bugün yanlış.** Stepper PR #602 ile yazıldı: `engine.py:756::_ItemStepper`,
`engine.py:805::_build_stepper`, `engine.py:3350` `run_engine` içinde kullanılıyor,
`step` alanı mevcut. `engine.py:1782` referansı da artık geçersiz.

Aynı bayat iddia iki yerde daha tekrarlanıyor:
* `backend/tests/unit/oracles/portfolio_harness.py:28-31`
* `backend/tests/unit/oracles/test_oracle_portfolio_containment_gate.py:144-146`

Bu üçünün **iddia ettiği containment doğru** (production caller yok) — **gerekçesi** bayat.
Bir sonraki ajan bunu okuyup "stepper yok, önce onu yaz" diye yanlış bir slice planlayabilir.

→ **`DOCUMENTATION-DRIFT` (production source içinde), ORTA risk.**

### 13.5 ADR 0002 §12 — kendi düzeltmesini taşıyor, ama iki vokabüler yan yana

ADR §12 delivery tablosu → correction note (2026-08-05) → amendment (PR #602). Amendment
"ADIM 16 is NO LONGER SKIPPED" diyor ve doğru. Ama:
* §12 satır 16 hâlâ ~~üstü çizili~~ "SKIPPED" olarak duruyor,
* iki ADIM numaralandırma vokabüleri (§12 satırları vs sevk edilen slice adları) **her ikisi
  de kullanımda**, ADR bunu bir eşleme tablosuyla çözüyor.

Bu **bilinçli** ve tablosu var → drift değil, kabul edilmiş karmaşıklık.

### 13.6 `docs/audit/current_main_ground_truth_2026-08-03.md`

`doc-status: historical`. CLAUDE.md zaten §18'in 2/3/4/6 kalemlerinin kapandığını ama
belgenin güncellenmediğini uyarıyor. **Doğru işaretlenmiş, drift değil.**

### 13.7 `acceptance_coverage_baseline.json` — provenance metni yanlış slice adı taşıyor

```json
"slice": "ADIM 49 — RC §6.7 P1-Gate3 follow-through (class-B debt, batch 02: …)"
"base_commit": "04c6a9c"
```

Ama tarif ettiği iş (`TL-12, TL-20, TS-11, TS-21, AOS-21`, partial 118→113, B 87→82)
`CLAUDE.md`'ye göre **ADIM 52**'nin işi ve PR **#692** (`e2fa521`) ile indi. Slice adı ve
base commit bayat. **Sayılar (`total_criteria 383`, `partial 113`, `B 82`) tutuyor** —
yalnız etiket yanlış. Bu, CLAUDE.md'nin de kaydettiği "bu slice DÖRT KEZ taşındı" numara
çakışmasının bir kalıntısı.

→ **`DOCUMENTATION-DRIFT`, düşük risk** (CI ratchet sayılara bakar, etikete değil).

### 13.8 Codemap kapsamı — portföy alt sistemi haritalarda YOK

`grep portfolio_engine|run_portfolio|portfolio_projection docs/CODEMAPS/` → **sıfır eşleşme.**

`scripts/generate_repository_facts.py::check_codemap_coverage` yalnız `application/*`
modüllerini ve dramatiq aktörlerini zorunlu tutuyor, `domain/*`'ı değil — yani **CI ihlali
yok**. Ama sonuç şu: repodaki **en büyük unwired alt sistem** (9 modül, ~2500 satır)
haritalarda görünmüyor, ve CLAUDE.md ajanlara *"Bir alana ilk kez dokunuyorsan ilgili
codemap'i oku"* diyor. PR B'ye başlayan bir oturum codemap'ten hiçbir şey öğrenemez.

→ **navigasyon boşluğu**, kapı ihlali değil.

---

## 14. GitHub issue-state drift

| # | Issue durumu | Current main davranışı | Drift yönü | Sınıf |
|---|---|---|---|---|
| **550** | CLOSED (completed), kapatan PR **yok** | sizing üç alanı hâlâ unit; UI hâlâ `%` | **kapalı ama kusur canlı** | `ISSUE-STATE-DRIFT` |
| **551** | CLOSED (completed), kapatan PR **yok** | `engine.py:1462` hâlâ `alloc_on and size <= _ZERO` | **kapalı ama kusur canlı** | `ISSUE-STATE-DRIFT` |
| **552** | CLOSED (completed), kapatan PR **yok** | `booking.py:93` hâlâ `1 + Σ fraction` round trip | **kapalı ama kusur canlı** | `ISSUE-STATE-DRIFT` |
| **617** | OPEN (reopened) | `readiness_check.py:404/411` **batched**, budget `per_item 0` | **açık ama onarılmış** | `ISSUE-STATE-DRIFT` (ters) |
| **618** | OPEN (reopened) | `dependency_pins.py::_prefetch` **batched**, budget `per_item 0` | **açık ama onarılmış** | `ISSUE-STATE-DRIFT` (ters) |
| **514** | OPEN (reopened) | A-08 gerçekten bitmemiş (0/4 çıkış kriteri) | **hizalı** | NOT-A-GAP |
| **558** | OPEN | bundle'lar gerçekten pinlemiyor, strict xfail canlı | **hizalı** | NOT-A-GAP |
| **559** | OPEN | DST kuralı yok; unified-clock ön koşulu | **hizalı** | NOT-A-GAP |

**Asimetri kayda değer:** üç finansal-semantik issue kanıtsız KAPATILDI; iki performans
issue'su onarıldıktan sonra AÇIK bırakıldı. İkisi de aynı kök nedeni gösteriyor — **issue
durumu bu repoda kanıt taşımıyor**, ve CLAUDE.md bunu #617/#618 için zaten "insan kararı"
diye kaydetmiş ama **#550/#551/#552 için hiçbir yerde kaydetmemiş.**

> **Bu oturumda hiçbir issue açılmadı, kapatılmadı, yeniden açılmadı veya yorumlanmadı**
> (görev §11). Yukarısı yalnız ölçümdür.

---

## 15. Hidden / differently named implementations found

Bu bölüm prompt'un "İSİM DEĞİL DAVRANIŞ İZLE" talimatının sonucudur. Aranan davranışlar,
sembol adına bakılmadan, `class`/`def` taraması + import grafiği ile arandı.

### 15.1 BULUNDU — beklenen addan farklı yerde yaşayan davranışlar

| Aranan davranış | Beklenen ad | **Gerçekte nerede** | Durum |
|---|---|---|---|
| Resumable per-item replay | `ADIM 16 stepper` (belgelerde "never written") | **`domain/backtest/engine.py:756::_ItemStepper`** + `:805::_build_stepper` — `run_engine` bunun üzerine kurulu 9 satırlık sürücü | **IMPLEMENTED-ACTIVE** — belgeler onu "yok" sanıyor |
| Faz-bölünmüş bar gövdesi | (adı yok) | `_ItemStepper` alanları: `admit` / `carry` / `open_fills` / `held` / `entry` / `tail` — **fazlar zaten ayrı callable** | **IMPLEMENTED-ACTIVE ama portfolio'dan kullanılmıyor** |
| Shared `E(t)` ile sizing | (adı yok) | `_ItemStepper.entry: Callable[..., None]` docstring: *"sized against `equity` when one is given — the **SHARED `E(t)`** for a portfolio participant"* | **kanca hazır, kullanılmıyor** |
| `PortfolioRun → EngineOutput` | (ADIM 16 kickoff'ta "kod olarak YOK") | **`execution/portfolio_projection.py:513::project_portfolio_run`** | **IMPLEMENTED-BUT-UNWIRED** — (c) engeli ADIM 35'te kapandı |
| Unified manifest identity | (adı yok) | `execution/provenance.py:473::build_portfolio_manifest` → `portfolio_simulation.policy_versions.portfolio_manifest_version` | **IMPLEMENTED-BUT-UNWIRED** |
| Result'ın hangi ko-simülasyondan geldiğini söyleme | (adı yok) | **`domain/backtest/portfolio_mode.py`** — ve **PRODUCTION'DA AKTİF** (`queries/backtest_run.py:167`, `queries/results_history.py:267`) | **IMPLEMENTED-ACTIVE (dejenere)** |
| Cross-item exposure/conflict — sevk edilen yaklaşım | `arbitration` | **`execution/rules.py::conflicts_with_prior` + `prior_exposure_at`** + `jobs/backtest_engine.py`'nin `prior_intervals` akümülatörü — forward-only, asimetrik | **IMPLEMENTED-ACTIVE** (kanonik olmayan yaklaşım) |
| Shared-mode reddi | `capability flag` | **üç bağımsız katman**: `commands/backtest_run.py:542` (admission), `domain/allocation/rules.py:154` (Ready Check), `frontend/pages/Portfolio.tsx:357` (UI) | **IMPLEMENTED-ACTIVE, fail-closed** |

### 15.2 ARANDI — BULUNAMADI (negatif sonuç, kayda değer)

`coordinator` / `executor` / `runner` / `facade` / `adapter` / `participant` / `orchestr*`
/ `scheduler` / `driver` / `simulat*` desenleri `backend/src` genelinde tarandı. Portföy
ko-simülasyonu için **alternatif bir orkestratör YOK**:

* `apps/agent_coordinator/` → Alpha Agent görev koordinatörü, portföyle **ilgisiz**
* `jobs/agent_executor.py` → Agent task executor, portföyle **ilgisiz**
* `apps/scheduler/` → outbox redelivery + heartbeat, portföyle **ilgisiz**
* `esp/resolver.py::_adapter_compatible` → ESP runtime adapter, portföyle **ilgisiz**

Ve containment gate testi bunu **assertion** hâline getiriyor:
`assert [p.name for p, text in sources.items() if "def run_portfolio" in text] == ["portfolio_engine.py"]`
— *"iki tane olması faz-sırası sorusuna iki cevap demektir"*.

**Sonuç: gizli bir ikinci portföy motoru yok. Eksik olan tek şey adaptör + çağrı yeri.**

---

## 16. Dead / test-only / unwired implementations

| Sembol | Dosya | Sınıf | Tek çağıranı |
|---|---|---|---|
| `run_portfolio` | `domain/backtest/portfolio_engine.py:518` | **IMPLEMENTED-BUT-UNWIRED** | `tests/unit/oracles/portfolio_harness.py:238` |
| `ItemParticipant` (Protocol) | `portfolio_engine.py:238` | **IMPLEMENTED-BUT-UNWIRED** | tek implementor `tests/…/portfolio_harness.py::_ScriptedParticipant` |
| `PortfolioTick` / `PortfolioRun` / `_run_tick` | `portfolio_engine.py` | **IMPLEMENTED-BUT-UNWIRED** | aynı |
| `project_portfolio_run` | `execution/portfolio_projection.py:513` | **IMPLEMENTED-BUT-UNWIRED** | `tests/unit/test_backtest_portfolio_projection.py` |
| `build_portfolio_manifest` | `execution/provenance.py:473` | **IMPLEMENTED-BUT-UNWIRED** | `tests/unit/test_backtest_portfolio_provenance.py` |
| `iter_ticks` / `ItemBarStream` | `execution/clock.py` | **IMPLEMENTED-BUT-UNWIRED** | yalnız `portfolio_engine.py` (o da unwired) |
| `ledger_for_items` / `PortfolioLedger` | `execution/portfolio_ledger.py` | **IMPLEMENTED-BUT-UNWIRED** | `portfolio_engine`, `arbitration`, `attribution`, `provenance` — hepsi contained |
| `arbitrate` (+ `arbitration.py` bütünü) | `execution/arbitration.py` | **IMPLEMENTED-BUT-UNWIRED** | aynı |
| `execution/attribution.py` | — | **IMPLEMENTED-BUT-UNWIRED** | aynı |
| `form_intents` / `ItemIntent` / `PortfolioSnapshot` | `execution/intents.py` | **IMPLEMENTED-BUT-UNWIRED** | aynı |
| `portfolio_mode::PORTFOLIO_MODE_UNIFIED_CLOCK` dalı | `portfolio_mode.py:129` | **DEAD-UNREACHABLE** (bugün) | okuma yolu aktif ama bu dal `build_portfolio_manifest` yazmadığı için ulaşılamaz |

**Hiçbiri DEAD-UNREACHABLE değil** (biri hariç): hepsi çağrılabilir, testleri var, `mypy`
ve `ruff` kapsamında, coverage kapısına dahil. **Kasıtlı, izole, testli bir ön-uygulama
katmanıdır** — çürük kod değil.

**TEST-ONLY sayılabilecek üretim kodu yok** — yani `src/` altında yalnız testlerin
çağırdığı ama bir gün production'a bağlanması *planlanmayan* bir şey bulunamadı. Yukarıdaki
her kalem ADR 0002 §12'de adlandırılmış bir teslimat planına ait.

---

## 17. Confirmed missing implementations

| # | Eksik | Kanonik kaynak | Neden CONFIRMED |
|---|---|---|---|
| **M-1** | **`ItemParticipant` adaptörü** — gerçek engine ile beslenmiş, bir item'ı verilen `t`'ye ilerletebilen | ADR §12 (PR B), doc 13 §8.3 | `src/` altında `ItemParticipant`'ı implement eden hiçbir şey yok; tek implementor test-owned `_ScriptedParticipant` |
| **M-2** | **Worker call site** — `jobs/backtest_engine.py:299` item döngüsünün `>1 item`'da `run_portfolio` + `project_portfolio_run`'a dallanması | ADR §12 satır 18/20 | `run_portfolio(` çağrısı `src/` altında sıfır, containment testiyle kilitli |
| **M-3** | **Book-etmeyen değerlendirme girişi** (stepper'da) — warmup evet, booking hayır | ADIM 16 kickoff §4.1 (b) | `_ItemStepper` hook'larının hiçbiri "değerlendir ama book etme" sunmuyor |
| **M-4** | **P2 pending fills + P8 same-direction scaling** faz döngüsünde | ADR §8 faz tablosu | `portfolio_engine.py` `UnsupportedIntentKindError` raise ediyor; **scaling açık her stratejide anında patlar** |
| **M-5** | **Sizing yüzde aritmetiği** — `notional = capital × pct/100`, `size = notional/entry_price`, leverage sonra | Master Ref §10.1, doc 02 ⓘ, #550 kararı (option A) | `sizing.py:216` ham değeri döndürüyor |
| **M-6** | **Kayıtlı revizyonlar için görünür transition gate** (#550 kararının 4. maddesi) | #550 comment | Ready Check'te böyle bir blocker yok; `ReadinessIssueCode` içinde karşılığı yok |
| **M-7** | **Genel zero-size guard** (`alloc_on` olmadan) + `size_resolved_to_zero` reason | #551, doc 13 §14 | `engine.py:1462` |
| **M-8** | **`base_position_size` şema pozitiflik kısıtı** (`gt=0`) | Master Ref §10.1 *"Pozitif olmalı"* | `config.py:711` yalnız `Decimal \| None` |
| **M-9** | **`min ≤ max` şema/Ready Check kısıtı** | #551 | yalnız motorda fail-closed 0 — "doğru ama geç" |
| **M-10** | ~~**`peak_notional`'ın conflict gate'te okunması**~~ — **GEREKMİYOR, ölçüldü** | #551 (b) | `rules.py:69` yalnız `direction` okuyor, **ama** `engine.py:721-723` non-positive notional'ı zaten gate'ten önce düşürüyor (§7.3). Bir savunma derinliği eklemek isteğe bağlıdır, eksik değildir |
| **M-11** | **Bundle'larda `available_time_policy` + 4 diğer §9.2 alanı** | doc 12 §9.1/§9.2 | `research_data.py` member şekli 5 anahtar; strict xfail kanıtı |
| **M-12** | **`alignment_policy_versions[]` + `missing_and_stale_policies[]`** — **üç yüzeyin hiçbirinde** | doc 12 §9.2 | Run manifest'te bile yok |
| **M-13** | **Ready Check signal + research leg'lerinin batch'lenmesi** | (issue yok — bu auditin yeni bulgusu) | `readiness_check.py:554`, `:749` |
| **M-14** | **`ENGINE_VERSION` bump** — M-5/M-7/commission kararının hepsi bunu gerektiriyor | #550, #551, #552, ADR §10.3 | `manifest.py:126` değişmemiş |
| **M-15** | **A-08 insan denetimi** — SR-1 tamamı, SR-2'nin %99'u | doc'lar + #514 | `a11y_screen_reader_audit_results.md` §5, 0/4 |

---

## 18. Product decisions required

| ID | Karar | Kim | Durum | Bu kararı bekleyen iş |
|---|---|---|---|---|
| **PD-1** | **PR B'nin ADR §16 insan kapısı** — `run_engine`'in bar gövdesini fazlara bölmek byte-identity sorusunu yeniden açar; **ADR amendment'ı gerekir** | Maintainer + PO | **AÇIK** | M-1, M-2, M-3, M-4 → tüm unified-clock hattı |
| **PD-2** | **Commission modeli**: per-FILL mi, tek round-trip mi? | PO | **AÇIK — hiç verilmemiş** (#550'nin aksine) | M-14 ile birlikte bir `ENGINE_VERSION` bump |
| **PD-3** | **#558**: §9.2 alanları member'a mı, top-level array'e mi? `bundle_hash` şekil değişikliği kabul mü? Diğer dört §9.2 alanı V1'de mi? | PO | **AÇIK** (`product-decision` etiketli) | M-11, M-12 |
| **PD-4** | **#559 DST fold/gap** — merged eksen karışık-zaman kaynaklarını kapsamadan önce | PO | **AÇIK** (`blocks-mixed-zone-axis`) | unified clock ön koşulu (ADR §12 "Prerequisites") |
| **PD-5** | **#550'nin kararı VERİLDİ (option A) ama uygulanmadı** — hâlâ geçerli mi, sequencing ne? | PO teyidi | karar var, **borç var** | M-5, M-6, M-14 |
| **PD-6** | **#550/#551/#552'nin kanıtsız kapatılması** — bunlar yeniden mi açılacak, yoksa yeni issue mu? | İnsan | **AÇIK** — agent kapatamaz/açamaz | issue hijyeni |
| **PD-7** | **#617/#618 onarıldı ama açık** — kapatılacak mı? | İnsan | **AÇIK** (CLAUDE.md "insan kararı" diyor) | issue hijyeni |
| **PD-8** | **A-08 denetçi rolü** — oturumu ürün sahibi kendisi koştu (`neither`); sertifikalı/ekran-okuyucu kullanan denetçi **hâlâ atanmadı** | İnsan | **AÇIK** | M-15 |
| **PD-9** | **D-10 imzalı sapması** — 45 düğüm, WCAG 1.4.3 karşılanmıyor. Sapma korunacak mı, kapatılacak mı? | PO | **imzalanmış**, gözden geçirilmemiş | uyumluluk beyanı |
| **PD-10** | **Alert delivery proof'unun CI kapısı olması** ve kuralların gerçek production serilerine karşı değerlendirilmesi — ikisi de repo içinde kapatılamaz | Maintainer | **AÇIK** | observability kapanışı |
| **PD-11** | **OD-1…OD-6** (ADR §13) + `MARK_STALENESS_POLICY` + `CONTENTION_SELECTION_STATUS` flip'i + **#544 (NET)** | PO | **AÇIK** | ADIM 20 (containment lift) |

---

## 19. Release blockers

RC readiness raporu (`docs/releases/Entropia_V18_RC_Readiness_2026-08-07.md`) bugün **TEK
blocker** sayıyor ve verdict **BLOCKED**. Bu audit o sayıyı **doğruluyor ama yetersiz
buluyor**: rapor kabul-akışı ve altyapı eksenlerini kapsıyor, **motor semantiği eksenini
kapsamıyor**.

### 19.1 RC raporunun saydığı blocker

| # | Blocker | Durum |
|---|---|---|
| **RC-1** | **A-08 insan kabul denetimi** | **AÇIK** — 0/4 çıkış kriteri, defter 2/184 hücre, SR-1 hiç başlamadı, #514 açık |

### 19.2 Bu auditin EKLEDİĞİ blocker'lar (RC raporunda blocker olarak sayılmıyor)

| # | Blocker | Neden release blocker | Kanıt |
|---|---|---|---|
| **FA-1** | **Sizing birim çelişkisi (#550)** — ürün kullanıcıya `%` gösterip birim sayısı çalıştırıyor | Fiyatla **sınırsız** ıraksayan finansal hata; 10 000 fiyatlı enstrümanda hesabın 10 katı nominal. Ürün kararı **verilmiş** (option A), uygulanmamış. | `sizing.py:216` vs `StrategyConfigForm.tsx:594` |
| **FA-2** | **Hayalet 0-size pozisyon (#551)** — ~~cross-item sızıntısı~~ **düzeltildi: sızıntı ÜRETİLEMİYOR** (§7.3) | Kusur duruyor ama **metrik/artifact + maliyet** düzeyinde: `total_trades`/`win_rate` paydası/expectancy seyreliyor ve `commission > 0` iken hayalet pozisyon **tam round trip** ödüyor (`pnl = -14.00`). Kompozisyon düzeyi **DEĞİL** — `engine.py:721-723` hayalet interval'i `conflicts_with_prior` görmeden düşürüyor. | `engine.py:1462` |
| **FA-3** | **Partial-close komisyonu (#552)** — üç modelden hiçbirine uymayan üçüncü bir model, docstring'i kendi koduyla çelişiyor | Maliyet modeli config'ten yeniden üretilemez; Master Ref §8 *"komisyon dağılımı engine manifestinde açık olmalıdır"* karşılanmıyor. | `booking.py:93` vs `:82` |
| **FA-4** | **Üç finansal issue kanıtsız KAPALI** | Release kaydı, canlı kusurları çözülmüş gösteriyor. Bir sonraki denetçi/PO **yanlış bir tabandan** karar verir. | `closed_by_pull_requests: []` ×3; main'de eşleşen commit yok |

### 19.3 Blocker OLMAYAN ama kapanışta beyan edilmesi gerekenler

| Kalem | Neden blocker değil |
|---|---|
| Shared allocation unified clock | **DELIBERATE-FUTURE-DEV**, üç katmanda fail-closed, kullanıcıya dürüst mesaj + remediation gösteriliyor, tarihsel Result'lar dürüstçe etiketleniyor. **Eksik özellik ≠ bozuk özellik.** |
| #617/#618 | kod onarıldı; yalnız issue hijyeni |
| #558 / #559 | açık, dürüst, `product-decision` etiketli, strict xfail ile kilitli |
| D-10 (WCAG 1.4.3) | **imzalı kalıcı sapma** — ama uyumluluk beyanında **açıkça** yer almalı: ürün 1.4.3 için AA uyumlu **değildir** |
| Ready Check'in iki batch'lenmemiş leg'i (M-13) | latency, doğruluk değil |

---

## 20. Recommended investigation next step

**AŞAMA B'ye geçmeden önce tek bir şey ölçülmeli, ve bu bir kod işi değil.**

### 20.1 Sıradaki adım (öneri)

> **PD-6'yı çöz: #550 / #551 / #552'nin gerçek durumu nedir?**

Bu audit üç canlı finansal kusuru ve onları "çözülmüş" gösteren üç kapalı issue'yu ölçtü.
Bir sonraki hiçbir teknik karar bu netleşmeden sağlıklı verilemez, çünkü:

* **#550'nin kararı (option A) hâlâ geçerliyse**, o karar **bir `ENGINE_VERSION` bump'ı, bir
  golden-digest refresh'i ve bir Ready Check transition gate'i** demektir — ve bu, PR B'nin
  46-digest byte-identity kapısıyla **aynı kaynağa dokunur**. İkisini yanlış sırada yapmak
  moved-digest'i **atfedilemez** kılar (ADR §15 R-4'ün tam olarak önlemeye çalıştığı şey).
* **#550/#551/#552 birlikte sevk edilmeli** (her iki issue de bunu yazıyor: aynı
  `_clamp_to_limits` yolu, aynı üç alan, tek digest refresh).
* Kapalı bırakılacaklarsa, bu bir **imzalı sapma** olmalı ve `CLAUDE.md`'ye O-02/O-12/O-30
  emsalindeki gibi bir adjudication olarak yazılmalı — sessiz kalmamalı.

### 20.2 Sıralama önerisi (karar verildikten sonra)

```
1.  PD-6  →  #550/#551/#552'nin durumu (insan)          ← BURADAN BAŞLA
2.  PD-2  →  commission modeli kararı (PO)
3.  FA-1 + FA-2 + FA-3 tek slice, tek ENGINE_VERSION bump, tek digest refresh
4.  M-13  →  Ready Check'in iki batch'lenmemiş leg'i (küçük, bağımsız, düşük risk)
5.  PD-1  →  ADR §16 insan kapısı + ADR amendment          ← PR B buradan sonra
6.  M-1 → M-2 → containment lift (ADIM 20)
7.  PD-3 / PD-4  →  #558 / #559 (unified clock'un ön koşulları)
8.  PD-8 → M-15  →  A-08 (paralel yürüyebilir, kimseyi bloklamaz)
```

**4. adım (M-13) hariç hiçbir kalem kod yazmakla başlamaz** — hepsi bir insan kararının
arkasında.

### 20.3 Bu auditin AŞAMA B'ye devrettiği açık sorular

1. `docs/audit/current_main_ground_truth_2026-08-03.md` §18'in kalan kalemleri (2/3/4/6
   dışındakiler) hâlâ geçerli mi? — bu audit onları ölçmedi.
2. §9.5: research revizyonlarının **funding dışı** bir yoldan run'a girmesi mümkün mü? Eğer
   mümkünse manifest pin'i orada da zengin mi? — **LOW confidence, ölçülmedi.**
3. `acceptance_coverage_debt_ledger.md`'nin 32 sınıf-D kriterinin kaçı yukarıdaki M-1…M-15
   ile örtüşüyor? — bu audit çapraz eşleme yapmadı.
4. Frontend'in sizing form'u #550 onarıldığında `%` etiketlerini koruyacak (kanon) — ama
   `min`/`max` için `le=100` gibi bir client-side kısıt gerekir mi? — ürün sorusu.

---

## 21. ZORUNLU MATRİS

| Requirement | Canonical Source | Production Symbol | Production Caller | Tests | Docs | GitHub | Classification | Confidence |
|---|---|---|---|---|---|---|---|---|
| Merged timestamp outer loop | doc 13 §8.3/§8.4/§13, ADR §4/§8 | `portfolio_engine.py:518::run_portfolio` | **YOK** | oracle-only (`portfolio_harness.py`) | ADR §12, `capability.py` — doğru | — | **IMPLEMENTED-BUT-UNWIRED** | HIGH |
| Item'ı `t`'ye ilerleten participant | ADR §6, §12 | **YOK** | — | test-owned `_ScriptedParticipant` | ADIM16 kickoff §4.1 (a)(b) | — | **CONFIRMED-MISSING** | HIGH |
| Tek `E(t)` valuation snapshot | doc 13 §8.3 | `portfolio_engine.py::_run_tick` (PV) | **YOK** | oracle | ADR §7 | — | **IMPLEMENTED-BUT-UNWIRED** | HIGH |
| Shared ledger P0/R0/U0 | doc 13 §8.3, ADR §7 | `execution/portfolio_ledger.py::ledger_for_items` | **YOK** | unit + oracle | ADR §7 | — | **IMPLEMENTED-BUT-UNWIRED** | HIGH |
| Simetrik arbitration, id tie-break | doc 13 §8.4.6/§13, ADR §9 | `execution/arbitration.py::arbitrate` | **YOK** | unit + oracle | ADR §9 | — | **IMPLEMENTED-BUT-UNWIRED** | HIGH |
| Cross-item conflict (sevk edilen) | doc 13 §8.4.6 | `execution/rules.py::conflicts_with_prior` | `jobs/backtest_engine.py:299-338` | unit | `cross_item_conflict_policy.md` | — | **PARTIAL** (forward-only, asimetrik) | HIGH |
| Unified `EngineOutput` projeksiyonu | ADR §14 A4/A18 | `portfolio_projection.py:513::project_portfolio_run` | **YOK** | unit | ADIM35 kickoff | — | **IMPLEMENTED-BUT-UNWIRED** | HIGH |
| Unified manifest identity | ADR §10.1 | `execution/provenance.py:473::build_portfolio_manifest` | **YOK** | unit | ADR §10 | — | **IMPLEMENTED-BUT-UNWIRED** | HIGH |
| Historical Result immutable + dürüst etiket | doc 15 §3.2, ADR §10.4 | `portfolio_mode.py::portfolio_simulation_context` | `queries/backtest_run.py:167`, `queries/results_history.py:267` | unit + integration | doğru | — | **IMPLEMENTED-ACTIVE** | HIGH |
| Shared-mode fail-closed reddi | doc 13 §1.1 + containment kararı | `allocation/capability.py`, `commands/backtest_run.py:542`, `allocation/rules.py:154` | 3 katman + UI | `test_shared_allocation_containment.py` | doğru | — | **IMPLEMENTED-BUT-CONTAINED** / **DELIBERATE-FUTURE-DEV** | HIGH |
| P2 pending fills / P8 scaling (faz döngüsünde) | ADR §8 | **YOK** (`UnsupportedIntentKindError`) | — | — | `portfolio_engine.py` docstring §2 — dürüst | — | **CONFIRMED-MISSING** | HIGH |
| `base_position_size` = resolved capital % | Master Ref §10.1:7552, doc 02 ⓘ:1875, mockup:6225, shipped UI | `sizing.py:216` — **ham birim** | `run_engine` → production | oracle **kusuru pinliyor** (`test_oracle_sizing.py:48`) | UI `%` diyor, motor unit | **#550 CLOSED, PR yok** | **STILL-BROKEN** + **ISSUE-STATE-DRIFT** | HIGH |
| `min`/`max_position_size` = % bounds | Master Ref §10.1, doc 02 ⓘ:1920 | `sizing.py:183-197::_clamp_to_limits` — **birim** | aynı | oracle pinliyor | docstring *"contracts/coins"* | #550 | **STILL-BROKEN** + **ISSUE-STATE-DRIFT** | HIGH |
| `base_position_size > 0` şema kısıtı | Master Ref §10.1 *"Pozitif olmalı"* | `config.py:711` — kısıt **yok** | — | — | — | #551 | **CONFIRMED-MISSING** | HIGH |
| Zero-size entry engellenir (tüm modlarda) | doc 13 §14, #551 | `engine.py:1462` `if alloc_on and size <= _ZERO` | `run_engine` | oracle `test_a_min_above_max_window_books_a_zero_size_trade` **kusuru pinliyor** | — | **#551 CLOSED, PR yok** | **STILL-BROKEN** + **ISSUE-STATE-DRIFT** | HIGH |
| Hayalet interval başka item'ı engellemez | doc 13 §8.4.6, #551(b) | `engine.py:721-723` non-positive notional'ı düşürür; `rules.py:69` onu hiç görmez | `jobs/backtest_engine.py:333` | `test_build_prior_intervals_fails_closed_on_bad_bounds_and_drops_zero_notional` **pinliyor** | — | #551 | **HOLDS** (önce yanlışlıkla STILL-BROKEN denmişti — §7.3) | HIGH |
| Komisyon modeli config'ten yeniden üretilebilir | Master Ref §8, `costs.commission` şeması *"Per-trade fee"* | `booking.py:93` — `1 + Σ fraction` | `run_engine` | oracle `…the_final_close_pays_a_full_one` **kusuru pinliyor** | docstring **koduyla çelişiyor** | **#552 CLOSED, PR yok** | **STILL-BROKEN** + **ISSUE-STATE-DRIFT** + **DOCUMENTATION-DRIFT** + **PRODUCT-DECISION-REQUIRED** | HIGH |
| Agent Data Bundle time policy pinler | doc 12 §9.1 | `jobs/research_data.py::compile_agent_data_bundle` — 5 anahtar | `jobs/agent_tools.py` | strict xfail `:583` | doğru | **#558 OPEN** | **PARTIAL** + **PRODUCT-DECISION-REQUIRED** | HIGH |
| Backtest Evidence Bundle `available_time_policies[]` | doc 12 §9.2 | `compile_backtest_evidence_bundle` — 5 anahtar | admission | strict xfail | doğru | #558 | **PARTIAL** + **PRODUCT-DECISION-REQUIRED** | HIGH |
| `bundle_hash` time policy'yi kapsar | doc 12 §9.2 | `_seal_bundle` — **kapsamıyor** | aynı | strict xfail | doğru | #558 | **CONFIRMED-MISSING** | HIGH |
| Run Context Manifest research pin'i | doc 12 §9.1/§9.2 | `backtest_run_context.py:371-398` | `commands/backtest_run.py` | integration | doğru | — | **IMPLEMENTED-ACTIVE** | HIGH |
| `alignment_policy_versions[]` / `missing_and_stale_policies[]` | doc 12 §9.2 | **hiçbir yüzeyde YOK** | — | — | #558 gövdesinde adlandırılmış | #558 | **CONFIRMED-MISSING** | HIGH |
| Research pin'i funding dışı yollarda da zengin mi | doc 12 §9.1 | `_FUNDING_ROLE` tek yol görünüyor | — | — | — | — | **belirsiz** | **LOW** — bu auditte ölçülmedi; run context'e research'ün başka bir rolle girip girmediği izlenmedi |
| Ready Check market-data leg flat | doc 14 §9.2/§11 | `readiness_check.py:404` + `:411` batched | `run_readiness_check` | `test_query_budgets.py:304` | budget doğru | **#617 OPEN** | **NOT-A-GAP** + **ISSUE-STATE-DRIFT** (ters) | HIGH |
| Pinned resolver re-validation flat | doc 06 §7 | `dependency_pins.py:125::_prefetch` batched | approve path | `test_query_budgets.py:340` | budget doğru | **#618 OPEN** | **NOT-A-GAP** + **ISSUE-STATE-DRIFT** (ters) | HIGH |
| Ready Check signal leg flat | doc 14 §11 | `readiness_check.py:554` — **döngü içinde `get_dataset_root`** | `run_readiness_check` | **budget YOK** | kayıt yok | **issue YOK** | **PARTIAL** | **HIGH** (kod) / statement sayısı **ölçülmedi** |
| Ready Check research leg flat | doc 14 §11 | `readiness_check.py:749` — **döngü içinde `get_dataset_root`** | `run_readiness_check` | **budget YOK** | kayıt yok | **issue YOK** | **PARTIAL** | **HIGH** (kod) / statement sayısı **ölçülmedi** |
| Alert DETECTION | M3 / RC §6.3 | `ops/alerts/entropia.rules.yml` (11 kural) | Prometheus | `test_alert_rules_contract.py` | doğru | — | **IMPLEMENTED-ACTIVE** | HIGH |
| Alert VALIDATION | RC §6.3 | `scripts/alert-rules-gate.sh` | `ci.yml` job `alerts` | promtool `test rules` | doğru | — | **IMPLEMENTED-ACTIVE** | HIGH |
| Alert ROUTING | RC §6.3 | `ops/alertmanager/alertmanager.yml` + `alert-notification-gate.sh` | `ci.yml` job `alerts` | `test_alert_notification_contract.py` | doğru | — | **IMPLEMENTED-ACTIVE** | HIGH |
| Alert DELIVERY (insan bildirimi) | RC §6.3 | `scripts/alert-notification-proof.sh` | **CI'da DEĞİL** | 4 fazlı proof, sentetik fixture yok | script başlığı dürüstçe ilan ediyor | — | **PARTIAL** | HIGH |
| Alert kuralları gerçek production serilerine karşı | RC §6.3 | — | — | — | CLAUDE.md dürüstçe kaydediyor | — | **CONFIRMED-MISSING** (repo içinde kapatılamaz) | HIGH |
| axe-core ratchet | R2-14 | `frontend/e2e/a11y-baseline.json` | `e2e.yml` job A11Y | bloklayıcı | doğru | — | **IMPLEMENTED-ACTIVE** | HIGH |
| Keyboard / precheck gate | R2-14 | `npm run a11y` prechecks | `e2e.yml` | bloklayıcı | doğru | — | **IMPLEMENTED-ACTIVE** | HIGH |
| Visual regression 23/23 rota | P11-2 | `screenshotMatrix.ts::TARGET_PAGES` | `e2e.yml` `npm run visual` | 23 snapshot PNG | doğru | — | **IMPLEMENTED-ACTIVE** | HIGH |
| İnsan SR denetimi (A-08) | doc'lar §5 | — | — | worksheet **2/184 hücre, 0/20 akış** | dürüst, `doc-status: historical` işaretli | **#514 OPEN** | **PARTIAL** — RELEASE BLOCKER | HIGH |
| WCAG 2.2 AA 1.4.3 (kontrast) | WCAG | 45 düğüm imza-mavisi | — | a11y-baseline dondurulmuş | D-10 imzalı sapma | — | **PRODUCT-DECISION-REQUIRED** (sapma imzalı) — ürün 1.4.3 için uyumlu **DEĞİL** | HIGH |
| `_ItemStepper` mevcut ve production'da | ADR §12 ADIM 16 amendment | `engine.py:756` + `:3350` | `run_engine` | `test_backtest_engine_stepper.py` (10 test) | **`portfolio_engine.py:44-49` "never written" diyor — BAYAT** | — | **IMPLEMENTED-ACTIVE** + **DOCUMENTATION-DRIFT** | HIGH |
| `CLAUDE.md` test/coverage sayıları tutarlı | — | — | — | — | **§75 ile §465 çelişiyor** (2712/%92.06 vs 3987/%93.53) | — | **DOCUMENTATION-DRIFT** | HIGH |
| `acceptance_coverage_baseline.json` provenance etiketi | — | — | — | sayılar doğru (383/113/B82) | **slice adı + base_commit bayat** ("ADIM 49" / `04c6a9c`; gerçekte ADIM 52 / `e2fa521`) | — | **DOCUMENTATION-DRIFT** | HIGH |
| Codemap portföy alt sistemini kapsıyor | CLAUDE.md §Kod arama | — | — | `check_codemap_coverage` `domain/`'ı kapsamıyor | **`docs/CODEMAPS/` içinde sıfır eşleşme** | — | **DOCUMENTATION-DRIFT** (kapı ihlali değil) | HIGH |

---

## 22. Kapanış özeti

```
Current main SHA:        e2fa52173a302aa6e9e1b0a23ba6061e6ccd8b86
Audit file:              docs/audit/final_closure_forensic_audit_2026-08-13.md
Production code changed: NO
```

| Kategori | Sayı | Kalemler |
|---|---|---|
| **Confirmed active implementations** | 12 | `_ItemStepper`+`run_engine` · `portfolio_mode` okuma yolu · 3 katmanlı shared-mode fail-closed reddi · forward-only cross-item rules · Run Context Manifest research pin'i · Ready Check market-data batch'i · dependency-pin batch'i · alert DETECTION/VALIDATION/ROUTING · axe ratchet · keyboard precheck · visual regression 23/23 |
| **Implemented but unwired** | 10 | `run_portfolio` · `ItemParticipant` · `execution/clock` · `execution/intents` · `execution/portfolio_ledger` · `execution/arbitration` · `execution/attribution` · `execution/provenance::build_portfolio_manifest` · `project_portfolio_run` · `PORTFOLIO_MODE_UNIFIED_CLOCK` dalı (unreachable) |
| **Implemented but contained** | 1 | Shared capital allocation (`SHARED_ALLOCATION_STATUS = future_dev`, üç katmanda fail-closed) |
| **Test-only implementations** | 1 | `_ScriptedParticipant` (`tests/unit/oracles/portfolio_harness.py`) — **`src/` altında test-only üretim kodu YOK** |
| **Confirmed missing** | 15 | M-1…M-15 (§17) |
| **Documentation drift** | 6 | `portfolio_engine.py` "stepper never written" (+2 test dosyası) · CLAUDE.md çelişen test sayıları · `acceptance_coverage_baseline.json` slice etiketi · codemap portföy boşluğu · `booking.py` commission docstring'i · CLAUDE.md HEAD sha (yapısal) |
| **Issue-state drift** | 5 | #550 / #551 / #552 (kapalı, kusur canlı) · #617 / #618 (açık, onarılmış) |
| **Product decisions required** | 11 | PD-1…PD-11 (§18) |
| **Release blockers** | 5 | **RC-1** A-08 · **FA-1** sizing birimi · **FA-2** hayalet 0-size (**cross-item sızıntı iddiası geri çekildi — §7.3**) · **FA-3** partial-close komisyonu · **FA-4** üç finansal issue kanıtsız kapalı |

### Most important first divergence in production execution

> **`backend/src/entropia/application/jobs/backtest_engine.py:299` — `for prepared in prepared_items:`**
>
> Dış döngü **item listesidir**, birleştirilmiş timestamp ekseni değil. Kanonik zincirin
> (tek `E(t)` → paylaşılan defter → simetrik arbitration → zaman-sıralı eğri) tamamı bu tek
> satırda kopar. Kanonik yolun **her modülü repoda mevcut ve testli**; eksik olan tek şey
> bir `ItemParticipant` adaptörü ve bu satırın `>1 item`'da `run_portfolio` +
> `project_portfolio_run`'a dallanmasıdır — ve o dallanma **ADR §16 insan kapısının**
> arkasındadır.

### Recommended next step

> **Kod yazma. PD-6'yı çöz: #550 / #551 / #552'nin gerçek durumunu bir insan karara bağlasın.**
>
> Üç canlı finansal kusur, kanıtsız kapatılmış üç issue tarafından "çözülmüş" gösteriliyor.
> #550'nin ürün kararı (option A — kanona uy) verilmiş ama uygulanmamış; #552'ninki hiç
> verilmemiş. Üçü de aynı `_clamp_to_limits` yoluna ve aynı `ENGINE_VERSION` bump'ına
> bağlı, ve o bump PR B'nin 46-digest byte-identity kapısıyla **aynı kaynağa dokunuyor** —
> yanlış sırada yapılırsa moved-digest atfedilemez hale gelir (ADR §15 R-4).
>
> Sıralama önerisi **§20.2**'de. AŞAMA B burada başlar.

---

*Bu belge bir ölçümdür, bir plan değil. Hiçbir satırı bir uygulama yetkisi vermez.*
