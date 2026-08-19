<!-- doc-status: historical -->
> **HISTORICAL KICKOFF — canlı olan `docs/ADIM86_LANDED_KICKOFF.md`'dir.**
> Bu belge yazıldığı andaki durumu kaydeder; SHA'lar, sayılar ve "next" maddeleri bayat
> olabilir. Sayısal gerçekler için otorite: `CLAUDE.md` §Current position +
> `docs/generated/repository_facts.md` (üretilmiş).

# ADIM 85 LANDED — C3 / E4c: `_EngineParticipant` · sıradaki slice için kickoff

## 0. Nerede duruyoruz

`SHARED_ALLOCATION_STATUS` = **`future_dev`** (DEĞİŞMEDİ) · `ENGINE_VERSION` **değişmedi** ·
alembic head `0043_i08_registry_strategy_fks` (bu dalgada migration yok) · OpenAPI
**değişmedi** · **50 golden digest bayt bayt aynı** · blocker **1** (yalnız A-08), verdict
**BLOCKED**.

`C1` (#735) describe/book bölmesini, `C2` (#759) `settle`/`finalize`/P10/`iter_portfolio`'yu
indirmişti. **`C3` bu ikisini birleştiren adaptörü indirdi.** Kritik yol artık bir imza değil
**wiring** bekliyor.

## 1. Bu slice ne bıraktı (REUSE anchor'ları — tam sembol adlarıyla)

| Sembol | Yer | Ne işe yarar |
|---|---|---|
| `_EngineParticipant` | `domain/backtest/participant.py` | `_ItemStepper` → `ItemParticipant`. `identity`, `stream`, `stepper`, `instrument_id` alır; **inşa edilmiş bir stepper** ister (worker `_replay_strategy`'de zaten çözüyor) |
| `_unsupported_shapes(ctx)` | aynı modül | **on bir maddelik** fail-closed reddi, `(violated, why)` tablosu olarak. **`C6`'nın admission blocker listesi bununla aynı olmalıdır** |
| `UnsupportedStrategyShapeError` / `ParticipantDivergenceError` | aynı modül | ikisi de `PortfolioEngineError` (yani `ValueError`) — worker onları başarısız run'a çevirir |
| `_protocol_check` | aynı modül | mypy'ın **yapısal** Protocol kanıtı. Negatif kontrolü koştu: `settle` adı bozulunca mypy *"missing following ItemParticipant protocol member: settle"* verir |
| `_apply_entry(..., size_override=None)` | `engine.py` | `_open`'ın cap kanalı artık P4 booking yarısından erişilebilir. Varsayılan `None` → `_step` ve `_phase_entry` bayt bayt aynı |
| `test_oracle_engine_participant.py` | `tests/unit/oracles/` | iki değişmez + üç tuzak + on bir reddin parametrize testi. `_participant(...)` yardımcısı **gerçek** `_build_stepper` + `AllocationExecution` kurar |
| `_AUTHORISED_PHASE_LOOP_IMPORTERS` + `_importers_outside_execution` | `test_oracle_portfolio_containment_gate.py` | allowlist artık **adlandırılmış veri** ve tarama fonksiyonu; negatif kontrol gerçek predicate'i sürer |

## 2. Pazarlıksız sınırlar (bunları gevşetme)

1. **`participant.py` `execution/` dışında KALIR.** İçeri taşımak containment gate'in importer
   taramasını yapısı gereği atlatır — kapı yeşil olur ama **hiçbir şey ölçmez**. Bu, imzalı
   kararın (2026-08-18) reddettiği **Seçenek B**'dir.
2. **Allowlist adlandırılmış listedir, sayı değildir.** Üçüncü bir importer kırmızı vermeli;
   `test_widening_the_importer_allowlist_did_not_disable_it` bunu iki eksende assert eder.
3. **Adaptör hiçbir tutarı yeniden türetmez.** Her `CarryCharges`/`MandatoryExit` alanı item
   ledger'ının **ölçülmüş** delta'sından gelir. Bir formül yazmak, motorun aritmetiğinin ikinci
   bir implementasyonudur.
4. **Sleeve parity üründe zorlanır**, yalnız testte değil. Guard'ı kaldırmak `C4`'ün `wi`'yi iki
   yere farklı geçirmesini sessizleştirir.
5. **`SHARED_ALLOCATION_STATUS` `future_dev` kalır.** `C3` de `C4` de containment'ı açmaz; lift
   `C9` + ADR §16 **Gate 2** (`G10`, **hiç talep edilmedi**).

## 3. Sıradaki slice: **`C4` (E5) — worker dalı**

Plan satırı: `docs/implementation/final_closure_ordered_plan_2026-08-13.md` §PACKAGE C, `C4`.
Tasarım: `closure_design_portfolio_performance_2026-08-13.md` §C.5, §C.6, §C.3.9.

- Üretim dosyası **tek**: `application/jobs/backtest_engine.py`.
  `_use_unified_clock(capital_execution)` **bir** yerde =
  `shared_allocation_is_executable() and shared_allocation_requested(capital_execution)`.
  **İki conjunct da taşıyıcıdır** — biri eksikse her bağımsız kompozit Result sessizce yeniden
  fiyatlanır.
- Paylaşımlı dal item döngüsünün **kardeşi**, üstünde. `iter_portfolio` generator'ı sürülür,
  tick'ler arasında `await _cancellation_requested(...)` (stride bir sabit, gerekçesi yazılı).
  **Checkpoint #4 yerinde kalır** (doc 15 §16: CANCELLED run Result üretmez).
- **Tripwire DARALTILIR, SİLİNMEZ.** `assert callers == []` → yetkili-çağıran allowlist'i.
  `combine_item_runs(` ve `for prepared in prepared_items:` assertion'ları **dokunulmaz ve
  yeşil kalmalıdır**.
- **DUR koşulu:** eğer PR kendini lift pinlerini (`SHARED_ALLOCATION_STATUS == "future_dev"`,
  `ENGINE_VERSION` literali, `5000.00`/`3000.00` fixture'ı) düzenlerken bulursa, sessizce
  ADIM 20 olmuştur ve önce **G10** gerekir → **DUR**.

**`C3`'ün `C4`'e devrettiği iki ölçülmüş kalem:**

1. **Giriş fill'i komisyonu havuza aynalanmıyor.** `_do_open` onu item equity'sine girişte
   yazar; loop'un o anda bir book kanalı yok. Sonraki tick'in `CarryCharges.fee`'sine kaydırmak
   toplamı düzeltir ama PD-2'nin **zamanlama** gerekçesini bozar. Pin:
   `test_the_entry_fills_commission_is_the_one_leg_the_loop_cannot_mirror`.
2. **`same_direction_stacking` varsayılanı `allow_stacking`** ve adaptör onu reddediyor —
   §C.3.7/§C.3.8 forkunun kayıtsız **üçüncü** kardeşi. `C6` bunu admission blocker'a çevirince
   mevcut stratejilerin çoğu paylaşımlı koşudan düşer → **ürün kararı**.

## 4. Çalışma yöntemi (bu slice'ta işe yarayan)

- **Kırmızı bir kapıyı gevşetmeden önce SAY.** İmzalı karar bir kapıyı ölçmüştü; ağaç **beş**
  dedi. Tahmin edilmedi, koşuldu.
- **Her assertion'ı negatif kontrolden geçir** ve **hangi** assertion'ın kırmızıya döndüğünü oku.
  Bu slice'ta on bir negatif kontrol koştu; biri (P3 aynası kaldırıldı) sleeve-parity testini de
  kırmızıya çevirdi — **doğru sebeple**: testin vacuity guard'ı (`E(t)` gerçekten oynamalı)
  ateşlendi.
- **Alt küme koşarken `--no-cov`.** Tam suite coverage kapısıdır.
- **Postgres yoksa** `/var/tmp`'de unprivileged bir PG16 cluster kur (`initdb` root koşmaz,
  scratchpad yolu `nobody` için traverse edilemez), `LC_ALL=C.UTF-8` (`en_US.UTF-8` bu
  container'da üretilmemiş).

---

## Paste-ready resume prompt

```
ENTROPIA V18 — C4 / E5: worker dalı, iptal kontrol noktası, daraltılmış tripwire
ROL: Entropia V18 Principal Engineer ve Release Closure Owner.
Konuşma dili TÜRKÇE; teknik tanımlayıcılar İngilizce.

SESSION START (atlamadan):
  git fetch --all --prune ; git status --short   -> kirliyse DUR
  git switch main ; git reset --hard origin/main ; git rev-parse HEAD
  Taban beklentin YOKTUR — ne bulursan RAPORLA ve her iddiayı AĞACA karşı yeniden ölç.

OKUMA SIRASI: (1) docs/implementation/final_closure_ordered_plan_2026-08-13.md §PACKAGE C, `C4`
  (2) docs/implementation/closure_design_portfolio_performance_2026-08-13.md §C.5, §C.6, §C.3.9
  (3) docs/adr/0002-unified-clock-portfolio-simulation.md §11, §14 A21, §16
  (4) docs/ADIM85_LANDED_KICKOFF.md (C3'ün bıraktıkları)
  (5) docs/generated/repository_facts.md = SAYISAL OTORİTE

ÖN KOŞUL: C3 merged — `backend/src/entropia/domain/backtest/participant.py` var ve
  `_EngineParticipant` `ItemParticipant`'ı yapısal olarak gerçekliyor. DOĞRULA, güvenme:
  `git ls-tree origin/main backend/src/entropia/domain/backtest/ | grep participant`

GÖREV: `application/jobs/backtest_engine.py` — TEK üretim dosyası.
  - `_use_unified_clock(capital_execution)` TEK yerde:
    `shared_allocation_is_executable() and shared_allocation_requested(capital_execution)`.
    İKİ CONJUNCT DA TAŞIYICIDIR — biri eksikse her BAĞIMSIZ kompozit Result sessizce
    yeniden fiyatlanır (bayraksız, bump'sız, kullanıcıya görünmeden).
  - Paylaşımlı dal item döngüsünün KARDEŞİ (üstünde), `iter_portfolio` generator'ı ile
    sürülür; tick'ler arasında `await _cancellation_requested(...)`, stride bir sabit ve
    gerekçesi yazılı. Checkpoint #4 YERİNDE KALIR.
  - Her item için `_EngineParticipant` kur: stepper'ı `_replay_strategy`'nin zaten çözdüğü
    pinlerden `_build_stepper` ile, `pin_ordinal` MANIFEST pin sırasından (liste konumundan
    DEĞİL), `shares` allocation planından.
  - Containment tripwire DARALTILIR, SİLİNMEZ: `assert callers == []` yerine yetkili-çağıran
    allowlist'i. `combine_item_runs(` ve `for prepared in prepared_items:` assertion'ları
    DOKUNULMAZ ve YEŞİL KALMALI.

DEĞİŞMEYECEK: migration YOK · OpenAPI YOK · ENGINE_VERSION YOK · manifest.py'ye DOKUNMA
  (o C7) · engine.py / portfolio_engine.py / capability.py NO-TOUCH ·
  engine_golden_digests.json BAYT BAYT AYNI · SHARED_ALLOCATION_STATUS "future_dev" KALIR.

İKİ DAVRANIŞSAL KANIT (plan `C4`):
  1. bağımsız çok-item'lı bir koşu unified loop'a ASLA ulaşmaz (bayrak sevk edildiği hâliyle;
     Result sıralı fold'un işaretini taşır)
  2. paylaşımlı bir koşu admission'da HÂLÂ reddedilir (test zaten var — GEVŞETMEDEN yeşil kalmalı)

C3'ÜN DEVRETTİĞİ İKİ KALEM (kapatmak zorunda değilsin, GÖRMEZDEN GELME):
  - giriş fill'i komisyonu havuza aynalanmıyor (loop'ta faz yok) —
    pin: test_the_entry_fills_commission_is_the_one_leg_the_loop_cannot_mirror
  - `_unsupported_shapes`'in on bir maddesi = C6'nın admission blocker listesi;
    `same_direction_stacking` ŞEMA VARSAYILANI `allow_stacking` → ürün kararı

KAPILAR (hepsi exit 0; `| tail` KULLANMA, $?'i AYRI oku; alt kümede --no-cov):
  cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy src
  uv run python -m entropia.apps.api.openapi_export --check ; uv run alembic heads (tek head)
  uv run pytest -q   (tam suite = coverage kapısı >=90)
  (backend'den) uv run python ../scripts/generate_repository_facts.py --root .. --check
  repo KÖKÜNDEN: node scripts/memory_index.mjs --check

YÖNTEM: Her assertion'ı NEGATİF KONTROLDEN geçir — davranışı üründen kaldır, testin KIRMIZIYA
  döndüğünü ve HANGİ assertion'da döndüğünü gör. and/or kapılarında bileşik sonucu değil
  TERİMLERİ ayrı pinle. Geçen bir negatif kontrol testin iyi olduğunu değil YOLUN HİÇ
  KOŞMADIĞINI söyler.

DURDURMA KOŞULLARI ("Complete" yazma): golden digest kıpırdadıysa · lift pinlerinden birini
  (`future_dev`, ENGINE_VERSION literali, 5000.00/3000.00 fixture'ı) düzenlemek gerekiyorsa
  (o zaman slice sessizce ADIM 20 olmuştur ve G10 gerekir) · tripwire'ın iki dokunulmaz
  assertion'ından biri kırmızıya dönüyorsa · açıklanamayan fark.

GIT/PR: dal `feat/closure-c4-worker-branch`. Commit `feat(closure-c4): <konu>`.
  AI attribution YOK. Yeniden tabanlamak gerekirse rebase et ve force-with-lease ile
  kendi feature dalına gönder (Update-branch düğmesi ve `-X theirs` YASAK).
  PR aç, MERGE ETME, auto-merge ARMA. Kapanış ritüeli 6 madde (CLAUDE.md §Session CLOSING);
  ADIM numarasını merge'den hemen önce `grep '^## ADIM' docs/PROJECT_HISTORY.md` ile doğrula.

SINIR: C4 containment'i AÇMAZ. Flag future_dev kalır; G10 (Gate 2) hâlâ TALEP EDİLMEDİ;
  G11/G12/G8/G14 ve A-08 açık; blocker 1, verdict BLOCKED. C6/C7'ye BAŞLAMA.
```
