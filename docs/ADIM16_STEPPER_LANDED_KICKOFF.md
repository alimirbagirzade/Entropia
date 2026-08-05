# ADIM 16 (geç sevk) — stepper landed · sıradaki iş: adaptör + worker call site (PR B)

> Bu belge **PR #602'nin (stepper) kapanış handoff'udur** ve aynı zamanda bu oturumda yapılan
> **doküman onarımının** devir notudur. En altta **paste-ready resume prompt** var.

---

## 1. Neredeyiz — doğrulanmış (2026-08-06)

| ne | değer | nasıl doğrulandı |
|---|---|---|
| `origin/main` HEAD | `c5d4c5d` | `git log --oneline origin/main -1` |
| alembic head | `0043_i08_registry_strategy_fks` | bu dalgada migration yok |
| `ENGINE_VERSION` | `backtest-engine-v18-gap-adjusted-stop-fill` (**bump YOK**) | #602 gövdesi + kod |
| `SHARED_ALLOCATION_STATUS` | `future_dev` — **containment KAPALI** | #602 gövdesi |
| ADR 0002 | **`Accepted`** (2026-08-05, PO/maintainer) | `docs/adr/0002-*.md:4` |
| ADR §13'ün OD-1…OD-7'si | **çözüldü**, §13.1 amendment tablosu | ADR §13.1 |
| ADR §12 numaralandırma sapması | **düzeltildi** (ADIM 16 formally SKIPPED → sonra #602 ile yine de indi) | ADR §12 düzeltme notu |
| `run_portfolio` | **var** — `domain/backtest/portfolio_engine.py:479` | grep |
| `run_portfolio`'nun çağıranı | **YOK** — worker hâlâ item döngüsünde | `jobs/backtest_engine.py:298` |

**Devraldığın bir brief "PR #581 açık" veya "faz döngüsü yazılmadı" diyorsa STALE'dir.** PR #581
2026-08-05 09:37'de merge edildi (`b0bb4a0`); faz döngüsü #586 ile, stepper #602 ile indi.

---

## 2. Bu oturumda ne yapıldı — doküman onarımı (kod DEĞİŞMEDİ)

Sıfır üretim satırı değişti. Bulunan ve kapatılan gerçek boşluk:

1. **Silinmiş history kaydı geri yüklendi.** `cdb3ab1` (PR #586) `PROJECT_HISTORY.md`'ye ADIM 18
   faz-döngüsü kaydını (208 satır) yazmıştı; **`c3f5673` (PR #590) onu sildi** — o commit'in bu
   dosyadaki diff'i **211 silme / 0 ekleme**. PR #590, PR #584 ile aynı başlık ve gövdeyi taşıyan
   **mükerrer** bir docs PR'ıydı ve branch'i kayıttan önceki bir duruma dayanıyordu. Ne gövdesi
   ne commit mesajı bir silme bildiriyordu. Kayıt `ba586c5`'ten **birebir** geri yüklendi.
2. **Hiç yazılmamış kayıtlar eklendi:** ADIM 21 (worker delivery, #587/#592 — PR #595 başlığına
   rağmen history'ye tek satır bile yazmamıştı), INF-15 (#597, #600), INF-16 (#599, #601),
   ADIM 16 stepper (#602).
3. **Bayat iddialar kapatıldı:** handoff'un *"`actors.py` analiz EDİLMEDİ"* devri (#597 kapattı),
   `CLAUDE.md`'nin `20a32ab`/`3cc9588` HEAD'i ve iki *"AÇIK kusur"* satırı (#597/#599 kapattı).

**Ders, tekrarlanmasın diye:** hiçbir CI kapısı `docs/` markdown'ını okumaz. Bir docs PR'ı
**sessizce** başka bir docs PR'ını geri alabilir. **Docs PR'ı açarken kendi diff'inin silme
satırlarına bak** (`git show <sha> -- docs/ | grep '^-' | head`).

---

## 3. Sıradaki TEK adım — PR B: adaptör + worker call site

`run_portfolio` **var ama çağıranı yok**. ADIM 20'nin kabul matrisindeki A1/A3/A5 dışında hiçbir
satır bu boşluk kapanmadan kapanamaz. PR A (stepper) indi; **PR B tek başına sıradaki iştir.**

**Yapılacak:** `_ItemStepper`'ın üstüne `portfolio_engine.ItemParticipant` Protocol'ünü uygulayan
bir adaptör yaz, sonra `application/jobs/backtest_engine.py:298`'deki item döngüsünü
`run_portfolio` ile değiştir — **yalnız >1 item** çalışırken. Tek item `run_engine`'de kalır
(ADR §3.2), imzası ve semantiği değişmez.

**REUSE — tam sembol adlarıyla, yeniden YAZMA:**

| ne | nerede |
|---|---|
| stepper (PR A'nın bıraktığı yüzey) | `domain/backtest/engine.py::_build_stepper`, `::_ItemStepper` — `step(bar)` / `finalize()` / `output()` / `open_position()` / `ledger` / `ctx` |
| stepper resumability kanıtı | `tests/unit/test_backtest_engine_stepper.py` |
| faz döngüsü giriş noktası | `domain/backtest/portfolio_engine.py::run_portfolio` |
| katılımcı sözleşmesi | `portfolio_engine.py::ItemParticipant` — `identity`, `stream`, `instrument_id`, `carry`, `mandatory_exit`, `entry` |
| P1 / P3 girdi tipleri | `portfolio_engine.py::CarryCharges`, `MandatoryExit` |
| çıktı tipleri | `portfolio_engine.py::PortfolioTick`, `PortfolioRun` |
| faz sırası, değer olarak | `portfolio_engine.py::PHASE_ORDER`, `PORTFOLIO_LOOP_VERSION` |
| fail-closed reddedişler | `InvalidParticipantError`, `MisformedIntentError`, `UnsupportedIntentKindError`, `UnpriceableAdmissionError` |
| referans katılımcı uygulaması | `tests/unit/oracles/portfolio_harness.py::_ScriptedParticipant` |
| saat / intent / ledger / arbitrasyon | `execution/clock.py::iter_ticks`, `execution/intents.py::form_intents`, `execution/portfolio_ledger.py::PortfolioLedger`, `execution/arbitration.py::arbitrate` |
| containment'ın kalan kapısı | `tests/unit/oracles/test_oracle_portfolio_containment_gate.py::test_the_phase_loop_exists_but_no_production_path_reaches_it` |

**Faz döngüsünün MODELLEMEDİĞİ — adaptörün de sınırıdır** (`portfolio_engine.py` docstring'inde
yazılı): **P0** (clock cursor'ı), **P2 pending fills**, **P8 same-direction scaling**. Admitted
bir `scale_in` bilerek `UnsupportedIntentKindError` atar, çünkü `set_position` tutulan boyutu
**değiştirir** ve pozisyonu sessizce küçültürdü. Mark policy yok (**OD-2**): `E(t)` realized-only.

**KABUL:**
- doc 13 §14 test 11 — tüm item'lar tek `E(t)` görür; **`mainboard_items` permütasyonu aynı
  digest'i vermeli** (item sırası sonucu değiştiremez).
- composite eğri **yapıca** zaman-sıralı (`stamps == sorted(stamps)`).
- **cross-item batch invariance** — her öğenin barlarını farklı chunk'lamak aynı sonucu vermeli.
  **Bugün hiçbir test bunu kapsamıyor.**
- 46 golden digest'ten **yalnız `portfolio.*`** olanlar oynayabilir; diğerleri SABİT — digest
  diff'ini senaryo senaryo gerekçelendir.
- Yeni davranışı **mutasyonla** sına. Geçen bir suite tek başına kanıt DEĞİL (ADIM 17'de 12,
  ADIM 19'da 10 mutasyon; ADIM 18 ve #602 mutasyon turu kaydetmedi).

**YAPMA:** `ENGINE_VERSION` bump · containment lift · manifest policy alanlarını
`build_portfolio_manifest`'e bağlama (üçü de **ADIM 20**) · `MARK_STALENESS_POLICY` /
`CONTENTION_SELECTION_STATUS` etiketlerini çevirme (ADR §13.1 son paragraf: **ADIM 20'nin**) ·
margin/cross-margin (ADR §9.5) · NET semantiği (#544) · FX (OD-5).

**Containment testleri — iki tuzak, ikisi de daha önce canlı hata verdi:**
1. Testler dosya metninde **düz substring** araması yapıyor. Yeni bir ÜRETİM dosyası eklerken,
   o dosyanın **yorumlarında** bile `execution.<contained_modul>` noktalı yazımı geçerse test
   kırılır — yorumda **path formu** kullan (`execution/foo.py`). Yeni üretim dosyası her
   eklediğinde containment suite'ini **tamamen** yeniden koş; hedefli koşu yetmez.
2. `rglob` filesystem sırasında döner ve **macOS ile Linux runner farklı sıra veriyor.** İzinli
   importer listesi >1 elemanlıysa **`sorted()` ZORUNLU**. **Hâlâ açık kalıntı:**
   `test_nothing_in_production_imports_the_attribution_layer_yet`
   (`tests/unit/test_backtest_portfolio_attribution.py:322`) ve provenance ikizi
   (`tests/unit/test_backtest_portfolio_provenance.py:478`) şu an tek elemanlı/boş olduğu için
   sıra bağımsız — **ikinci importer eklendiği anda** aynı hataya düşerler. PR B ikisini de
   `sorted()` yapmalı.

---

## 4. Sonra: ADIM 20 — ön koşulları hâlâ açık

- **A17**: `tests/integration/test_research_point_in_time_parity.py`'de 4 `xfail(strict)`
  (#556 ×2, #557, #558). "green, unweakened" değil.
- **OD-1 / OD-2 / OD-6 kapıları KOD OLARAK YOK** — ADR §13.1 kararı kaydetti, blocker'ı yazmadı.
- **#544 (NET)** kanonda tanımsız · **#559 (DST)** karışık zaman dilimi öncesi.
- **A4 / A18** gerçek `EngineOutput` digest'i ister → PR B'ye bağlı.
- **A21** tick tabanlı cancel checkpoint → worker değişikliğine bağlı.

## 5. Açık insan/ürün kararı — tek kalan

**Yarım-cent yuvarlama.** `allocation/rules.py::_money` = `ROUND_HALF_UP`;
`execution/portfolio_ledger.py::MONEY_ROUNDING` = `ROUND_HALF_EVEN`. `1000.10 @ %25` →
preview `250.03`, execution `250.025`. **doc 13 §13 preview/manifest uyuşmazlığını YASAKLIYOR
ama kanon kazananı seçmiyor.** Şu an `provenance.sleeve_amount_divergences()` farkı
**raporluyor, çözmüyor** (`SLEEVE_AMOUNT_DIVERGENCE`). `initial_sleeve_capital` için hangi
quantization kanonik? — **karar verilmeden sizing/allocation aritmetiğine dokunma.**

## 6. Çalışma yöntemi (bu repoda pahalıya mal olmuş tuzaklar)

- `uv run` dev bağımlılıklarını siliyor → **her komutta `uv run --extra dev`**.
- `TEST_DATABASE_URL` ile **worktree'ye özel** DB kullan; sürücü `postgresql+asyncpg://` olmalı.
  **Paralel worktree oturumları CPU için gerçekten yarışıyor — ölçüldü (2026-08-06):** 8
  çekirdekli makinede iki tam pytest suite'i daha koşarken load average **32** idi ve bu
  worktree'nin koşusu **47 dakikada %7**'ye ulaştı (ekstrapolasyon ~11 saat). Tam suite'i
  başlatmadan önce `pgrep -fl pytest` + `uptime` ile bak; başka bir suite koşuyorsa **bekle**,
  yoksa ölçtüğün şey doğruluk değil çekişmedir.
- Tam suite'i **tek pytest çağrısında** koş, **ortada öldürme**; çıktıyı **dosyaya yaz** ve
  `$?`'i **ayrı** oku. **`| tail` KULLANMA** (exit code `tail`'in olur). Suite koşarken
  `uv sync`/`uv run` çalıştırma.
- Alt küme koşarken **`--no-cov` ekle** — tek dosyalık koşu paketin tamamını ~%4 ölçer ve
  `--cov-fail-under=90` kapısı sahte kırmızı verir.
- Frontend: `npx vitest run --no-file-parallelism` (**zorunlu**); `node_modules` yoksa önce
  `npm ci` — ilk koşudaki `ERR_MODULE_NOT_FOUND` test hatası değil.
- Kod aramaya **codemap + `codebase-memory-mcp`** ile başla, kör grep + tam dosya okuma ile değil.
- Code-review CRITICAL/HIGH bulgularını **düzeltmeden önce empirik doğrula** — sık yanlış çıkıyor.

---

## 7. Paste-ready resume prompt

```
ENTROPIA — sıradaki slice: PR B, engine-destekli ItemParticipant adaptörü + worker call site

BAŞLANGIÇ (zorunlu): git fetch --all --prune · git status --short (temiz değilse DUR) ·
git log --oneline origin/main -5 · gh pr list --state all --limit 10.
Devraldığın hiçbir özeti current truth sayma — koda ve teste bak.
Oku: docs/ADIM16_STEPPER_LANDED_KICKOFF.md (bu belge) → docs/STAGE2_HANDOFF.md §Next 1(b) →
docs/adr/0002-unified-clock-portfolio-simulation.md §3.2/§8.2/§13.1/§15 →
docs/CODEMAPS/BACKEND_LAYERS.md. Kod aramaya codebase-memory-mcp ile başla.

DOĞRULANMIŞ DURUM: origin/main c5d4c5d · alembic 0043_i08_registry_strategy_fks ·
ENGINE_VERSION bump YOK · SHARED_ALLOCATION_STATUS=future_dev (containment KAPALI) ·
ADR 0002 Accepted, OD-1…OD-7 §13.1'de çözüldü · run_portfolio VAR (portfolio_engine.py:479)
ama ÇAĞIRANI YOK · stepper VAR (engine.py::_build_stepper / _ItemStepper, PR #602).

GÖREV: _ItemStepper üstüne portfolio_engine.ItemParticipant Protocol'ünü uygulayan bir adaptör
yaz (identity, stream, instrument_id, carry, mandatory_exit, entry), sonra
application/jobs/backtest_engine.py:298'deki item döngüsünü run_portfolio ile değiştir —
YALNIZ >1 item çalışırken. Tek item run_engine'de kalır (ADR §3.2); run_engine'in imzası ve
semantiği DEĞİŞMEZ.

Branch: feat/portfolio-item-participant
Commit: feat(portfolio): drive multi-item runs through run_portfolio

REUSE (yeniden yazma): engine.py::_build_stepper/_ItemStepper · portfolio_engine.py::
run_portfolio/ItemParticipant/CarryCharges/MandatoryExit/PortfolioTick/PortfolioRun/PHASE_ORDER/
PORTFOLIO_LOOP_VERSION · execution/clock.py::iter_ticks · execution/intents.py::form_intents ·
execution/portfolio_ledger.py::PortfolioLedger · execution/arbitration.py::arbitrate ·
tests/unit/oracles/portfolio_harness.py::_ScriptedParticipant (referans uygulama).

KABUL: doc 13 §14 test 11 (tüm itemler tek E(t); mainboard_items PERMÜTASYONU aynı digest) ·
composite eğri yapıca zaman-sıralı · cross-item batch invariance (bugün HİÇBİR test kapsamıyor) ·
46 golden digest'ten yalnız portfolio.* oynayabilir, diğerleri SABİT ve diff senaryo senaryo
gerekçelendirilir · yeni davranış MUTASYONLA sınanır (geçen suite tek başına kanıt DEĞİL).

CONTAINMENT TUZAKLARI: (i) testler düz substring arıyor — yeni üretim dosyasının YORUMUNDA bile
"execution.<modul>" noktalı yazımı geçerse kırılır, yorumda path formu kullan, ve containment
suite'ini TAMAMEN yeniden koş. (ii) rglob filesystem sırasında döner, macOS ve Linux runner
FARKLI sıra veriyor → attribution (test_backtest_portfolio_attribution.py:322) ve provenance
(test_backtest_portfolio_provenance.py:478) importer listelerini sorted() yap.

YAPMA: ENGINE_VERSION bump · containment lift · manifest policy alanları · MARK_STALENESS_POLICY
ve CONTENTION_SELECTION_STATUS etiketlerini çevirme (üçü de ADIM 20) · margin (ADR §9.5) ·
NET (#544) · FX (OD-5) · yarım-cent yuvarlamayı KARAR GELMEDEN çözme.

YEREL DOĞRULAMA: cd backend && TEST_DATABASE_URL="postgresql+asyncpg://entropia:entropia@\
localhost:5432/<worktree-özel-db>" uv run --extra dev ruff check . && uv run --extra dev \
ruff format --check . && uv run --extra dev mypy src && uv run --extra dev pytest > /tmp/s.log \
2>&1; echo "EXIT=$?". Tek çağrı, ortada öldürme, "| tail" YOK, alt kümede --no-cov.

KAPANIŞ: CLAUDE.md §Session CLOSING ritüelinin altısı da — handoff landed girdisi + Next,
yeni KICKOFF (paste-ready resume prompt ile), PROJECT_HISTORY tam kayıt, CLAUDE.md §Current
position 5–6 satır, ecc + claude-mem checkpoint, codemap tazeleme. Docs PR'ı açarken KENDİ
diff'inin silme satırlarına bak: PR #590 böyle 208 satırlık bir kaydı sessizce silmişti.
```
