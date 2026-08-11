<!-- doc-status: historical -->
# ADIM 35 landed — `PortfolioRun` → composite `EngineOutput`; sıradaki iş hâlâ PR B

> Bu belge **projeksiyon slice'ının devri**dir. Otorite sırası: (1) bu belge, (2)
> `docs/adr/0002-unified-clock-portfolio-simulation.md` (§3.2, §7, §14 A4/A5/A18, §12 amendment),
> (3) `docs/ADIM16_STEPPER_LANDED_KICKOFF.md` §4.1 (üç engel — **ikisi hâlâ açık**), (4)
> `docs/STAGE2_HANDOFF.md` en alttaki `## Next:`. En altta **paste-ready resume prompt**.

---

## 1. Nerede duruyoruz

`ADIM16_STEPPER_LANDED_KICKOFF.md` §4.1 PR B'nin literal kapsamıyla **ulaşılabilir olmadığını**
ölçmüş ve üç seçenek bırakmıştı. **Seçenek 3 seçildi ve indi:** `PortfolioRun` artık tek bir
portföy-seviyesi `EngineOutput`'a projekte ediliyor.

Bu, ADR §14'ün **A4** ("item sırası sonucu değiştirmez — *identical `EngineOutput` digest*") ve
**A18** ("cross-item batch invariance — *identical digest*") kriterlerini **ilk kez
değerlendirilebilir** yaptı: o güne kadar bu yolda digest alınacak bir artefakt yoktu.

**Containment DEĞİŞMEDİ.** `run_portfolio` üretimde hâlâ çağrısız, projeksiyon da öyle;
`SHARED_ALLOCATION_STATUS = future_dev`, `ENGINE_VERSION` sabit, worker hâlâ item döngüsü +
`combine_item_runs`. §4.1'in (a) ve (b) engelleri **kapanmadı** — onlar hâlâ ADR §16 insan
kapısı + ADR amendment'ı gerektiriyor.

---

## 2. KARAR — tek portföy-seviyesi çıktı, N adet öğe-seviyesi DEĞİL

Bu bir tasarım tercihi değil, iki canon dayatması:

1. **Eğriyi ters çevirirdi.** `combine_item_runs` bileşik eğriyi her öğenin realized
   ilerleyişini pin sırasında **birleştirerek** kurar; kendi ifşası
   `portfolio_curve_sequential_not_unified_clock` ve ADR §14 **A5**'in ("*time-ordered by
   construction*") kaldırmak için var olduğu kusur tam olarak budur. Defterin eğrisi **zaten**
   zaman-sıralı; onu sıralı fold'dan geçirmek sıralı bir seriden sırasız bir seri türetmek olurdu.
2. **Bölünecek öğe-seviyesi equity YOK.** ADR §7: havuz paylaşımlıdır ve *"a sleeve is a cap, not
   a wallet"* — sermaye fiziksel olarak bölünmez. `E(t)`'yi N öğe eğrisine ayırmak canon'un
   tanımlamadığı bir **tahsis-atıf modeli** olurdu. Defterin öğe başına gerçekten kaydettiği şey
   `ItemAttribution`'dır (realized PnL, fees, funding, other costs) — bir **net katkı**, eğri değil,
   drawdown tabanı hiç değil.

**Sonuç:** projeksiyon paylaşımlı yolda `combine_item_runs`'ı **beslemez, YERİNE GEÇER**. İkisi
birbirini çağırmaz; sıralı fold ve onun dört `portfolio.combine*` golden digest'i **kımıldamadı**.

---

## 3. PR B'nin devralacağı reuse anchor'ları — tam sembol adlarıyla

| ne | nerede |
|---|---|
| projeksiyon girişi | `execution/portfolio_projection.py::project_portfolio_run` (`:511`) |
| pinlenmiş öğe metadata'sı (worker'ın vereceği) | `portfolio_projection.py::PinnedItem` (`:162`) |
| ifşa edilen sınırlar, tek liste | `portfolio_projection.py::ABSENT_BY_CONSTRUCTION` (`:117`) |
| fail-closed retler | `UnpinnedItemError` · `UnpairedCloseError` · `UnpricedIntentError` |
| bookkeeping kaydı (**YENİ**, faz döngüsünde) | `portfolio_engine.py::BookedClose` (`:165`) |
| tick üzerindeki yeri | `portfolio_engine.py::PortfolioTick.closes` (`:206`) |
| stepper fabrikası (ADIM 16'dan, değişmedi) | `domain/backtest/engine.py::_build_stepper` |
| stepper kaydı | `engine.py::_ItemStepper` (`step` / `finalize` / `output` / `open_position`) |
| sıralı fold (dokunulmadı) | `execution/portfolio.py::combine_item_runs` (`:312`) |
| worker call site | `application/jobs/backtest_engine.py:298` (item döngüsü) · `:363` (fold) |
| referans katılımcı | `tests/unit/oracles/portfolio_harness.py::_ScriptedParticipant` |

**Sözleşme:** `project_portfolio_run(run, *, items, execution_key, item_count) -> EngineOutput`.
`items` manifest'in pinlenmiş metadata'sıdır; **sırası okunmaz** — executing satırlar defterin pin
sırasını, non-executing satırlar `item_id` sırasını izler, bu yüzden A4 yapısaldır.

---

## 4. Bu slice'ta ölçülen, PR B'nin güvenebileceği gerçekler

- **`combine_item_runs`'ın yeri handoff'ta YANLIŞTI.** `jobs/backtest_engine.py:363` **call
  site**'tır; tanım `domain/backtest/execution/portfolio.py:312`. Doğrula, devralma.
- **`TradeRow.pnl` net'tir** (`booking.py::close_position`: `pnl = (gross - commission).quantize`).
  Faz döngüsünde bunun karşılığı `PortfolioLedger.book_trade`'in **dönüş değeridir** — `BookedClose.net_pnl`
  onu saklar. `gross - commission`'ı yeniden hesaplayan bir okuyucu, yuvarlamanın **ikinci bir
  uygulaması** olur ve defterden bir kuruş sapabilir.
- **`arbitrate` HER intent için bir karar üretir** — actionable olmayan bir `no_op` bile
  `outcome="not_actionable"` alır, düşürülmez. Bu yüzden P4 olayına arbitration eklemek dalsızdır.
- **`execution/*` modüllerinin her biri TAM importer listesiyle pinli** (`test_backtest_item_intents.py`,
  `test_backtest_unified_clock.py`, `test_backtest_portfolio_ledger.py`,
  `test_backtest_cross_item_arbitration.py`). Projeksiyon `execution.intents`'i import ediyor →
  o liste **bilerek** genişletildi. `clock` / `portfolio_ledger` / `arbitration` policy-version
  sabitleri **bilerek yayımlanmadı**: hiçbir tüketicinin okumadığı bir alan için üç containment
  listesi daha genişletmek pahalıydı.
- **`execution/` içindeki bir modül per-module importer kontrolünden MUAFTIR**
  (`path.parent.name != "execution"`). Bu yüzden projeksiyonun kendi containment iddiası
  `test_oracle_portfolio_containment_gate.py::test_the_result_projection_exists_but_no_production_path_reaches_it_either`
  olarak **ayrıca** yazıldı — aksi halde unified-clock yüzeyinin genişlemesi görünmezdi.

---

## 5. Fail-closed reddedilenler — sıfırla doldurulmadı, ADLANDIRILDI

`diagnostics["warnings"]` = `ABSENT_BY_CONSTRUCTION`, beş kalem:

| token | neden yok |
|---|---|
| `..._item_local_engine_counters_absent` | `_DIAG_SUM_KEYS` (bars_processed, indicator_blocks, …) öğe-yereldir; faz döngüsü bar gövdesi görmez. `0` yazmak "ölçüldü, sıfır" demek olurdu |
| `..._filter_veto_journal_is_item_local` | `FILTERED_EVENT_TYPES` katılımcı hook'una hiç ulaşmaz — boşluk "burada olmadı", "hiç olmadı" değil |
| `..._position_intervals_absent` | `peak_notional` tutulan pencere boyunca öğe motorunda izlenir; paylaşımlı defter yalnız giriş-bazlı notional tutar |
| `..._contribution_requires_resimulation` | `combine_item_runs`'ın leave-one-out'u *"each item's simulation is independent"* varsayımına dayanır — **paylaşımlı havuzda yanlış**: bir öğeyi çıkarmak her kardeşin `Ci(t)`'sini ve dolayısıyla fill'lerini değiştirir. Yeniden **simülasyon** ister |
| `..._equity_exposure_is_portfolio_gross_percent` | `EquityPoint.exposure` öğe eğrisinde *kapanan lot'un* notional'ı / kapanış öncesi equity'dir; burada **portföyün** gross exposure'ı / `E(t)`. Alan adı sevk edilmiş artefaktın adı, o yüzden taban değişikliği ilan edilir |

**PR B bunları "doldurmayı" iş edinmesin.** Her biri ya öğe motorundan gelmeli (adaptör
yazıldığında bazıları gelebilir) ya da hiç gelmemeli.

---

## 6. Bu slice'ta işleyen yöntem (PR B'de tekrarla)

1. **Handoff'a körlemesine güvenme.** Bu slice'ın ilk bulgusu `combine_item_runs`'ın yerinin
   yanlış yazılmış olmasıydı; ikincisi dört tam-liste containment guard'ının varlığıydı.
2. **Kararı canon'dan çıkar, koddan uydurma.** "Tek çıktı mı N çıktı mı" sorusunu A5 + §7 cevapladı;
   kod hiçbir yönde ipucu vermiyordu.
3. **Ponytail merdiveni gerçekten para kazandırdı.** Üç policy-version sabitini yayımlamak "bedava"
   görünüyordu; maliyeti **üç containment listesi genişletmekti**. Import silindi, guard'lardan
   yalnız biri (intents) genişledi.
4. **Hata yollarını gerçek bir koşuyu `dataclasses.replace` ile bozarak test et** — elle kurulmuş
   sentetik `PortfolioTick` yerine. Reddin gerçek bir bozulmadan geldiğini kanıtlar.
5. **Yerel doğrulama:** ruff + mypy, sonra tam suite **tek çağrıda**, çıktı **dosyaya**, `$?`
   **ayrı**. `TEST_DATABASE_URL` ile worktree'ye özel `postgresql+asyncpg://` DB.
   `scripts/generate_repository_facts.py` **kesinlikle** yeniden üretilmeli — test sayısı değişti,
   `test_repository_facts_guard` aksi halde kırmızı.

---

## 7. Paste-ready resume prompt

```text
ENTROPIA V18 — PR B: ItemParticipant adaptörü + run_portfolio call site

ÖNCE DOĞRULA (handoff STALE-BY-DEFAULT — özete güvenme):
  git fetch && git log --oneline origin/main -6 && gh pr list --state all
  grep -rn "project_portfolio_run(\|run_portfolio(" backend/src   # üretimde çağıran VAR MI? (olmamalı)
  grep -n "_build_stepper\|_ItemStepper" backend/src/entropia/domain/backtest/engine.py

OKUMA SIRASI:
  1. docs/ADIM35_LANDED_KICKOFF.md                          ← bu belge (projeksiyonun devri)
  2. docs/ADIM16_STEPPER_LANDED_KICKOFF.md §4.1             ← (a) ve (b) engelleri HÂLÂ AÇIK
  3. docs/adr/0002-unified-clock-portfolio-simulation.md    ← §3.2, §7, §12 amendment, §14, §16
  4. backend/src/entropia/domain/backtest/portfolio_engine.py      ← §"HONEST BOUNDARY" ÖNCE oku
  5. backend/src/entropia/domain/backtest/execution/portfolio_projection.py  ← §"deliberately ABSENT"
  6. backend/tests/unit/oracles/portfolio_harness.py::_ScriptedParticipant

DURUM: Projeksiyon indi (ADIM 35) — PortfolioRun -> tek portföy-seviyesi EngineOutput,
  A4/A18 artık digest üzerinden ölçülüyor. Containment DEĞİŞMEDİ: run_portfolio ve
  project_portfolio_run üretimde çağrısız, SHARED_ALLOCATION_STATUS=future_dev,
  ENGINE_VERSION sabit, worker hâlâ jobs/backtest_engine.py:298 item döngüsü + :363 fold.

KALAN ENGELLER (ADIM 35 bunları KAPATMADI):
  (a) Stepper bir barı BÜTÜN olarak ilerletir; faz döngüsü aynı barı P1/P3/PV/P4'e BÖLÜNMÜŞ ister.
  (b) `entry` book-etmeyen bir değerlendirme girişi ister (warmup evet, booking hayır).
  İkisi de run_engine'in bar gövdesine dokunur -> ADR §16 insan kapısı + ADR AMENDMENT'I gerektirir.
  Bu kapıdan geçmeden (a)/(b)'ye BAŞLAMA; geçtiysen amendment'ı ADR'ye YAZ.

GÖREV (kapı geçildiyse):
  (a) Stepper üstüne portfolio_engine.ItemParticipant adaptörü: carry / mandatory_exit / entry.
      Uyduramadığın fazı fail-closed reddet, sessizce modelleme.
  (b) jobs/backtest_engine.py:298 item döngüsünü >1 item'da run_portfolio + project_portfolio_run
      ile değiştir; tek item run_engine'de kalır (ADR §3.2).
  (c) İKİ containment testini de GEVŞETME, yeniden YAZ — importer'lar ADLANDIRILIR:
      test_oracle_portfolio_containment_gate.py::test_the_phase_loop_exists_but_no_production_path_reaches_it
      test_oracle_portfolio_containment_gate.py::test_the_result_projection_exists_but_no_production_path_reaches_it_either

KABUL:
  - 37 non-portfolio golden digest KIMILDAMAMALI.
  - portfolio.* digest'lerinin kımıldaması BEKLENİR — her biri tek tek gerekçelendirilir.
  - Tam backend suite yeşil + coverage kapısı (>=%90).

YAPMA:
  - ENGINE_VERSION'a dokunma. SHARED_ALLOCATION_STATUS'u KALDIRMA. İkisi ADIM 20.
  - run_engine'in imzasını/semantiğini değiştirme (amendment olmadan).
  - ABSENT_BY_CONSTRUCTION kalemlerini "doldurma" işine girme — her biri gerekçeli.
  - Manifest policy alanı ekleme (ADIM 20); NET'i desteklenir yapma (#544).

DOĞRULAMA:
  cd backend && uv run --extra dev ruff check . && uv run --extra dev ruff format --check . \
    && uv run --extra dev mypy src
  TEST_DATABASE_URL=postgresql+asyncpg://entropia:entropia@localhost:5432/<worktree_db> \
    uv run --extra dev pytest > /tmp/full.log 2>&1; echo $?   # tek çağrı, exit code AYRI
  cd backend && uv run python ../scripts/generate_repository_facts.py --root ..   # ZORUNLU
  Alt küme koşarken --no-cov. `git status backend/uv.lock` — uv run lock'u kirletir, stage etme.

KAPANIŞ: CLAUDE.md §"Session CLOSING ritual" — 6 madde, istisnasız + docs regresyon kontrolü.
```
