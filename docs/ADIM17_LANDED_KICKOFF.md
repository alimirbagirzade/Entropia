<!-- doc-status: historical -->
> **HISTORICAL RECORD — bu belge GÜNCEL GERÇEK DEĞİLDİR.** Yazıldığı andaki durumu
> kaydeder; SHA'lar, sayılar, alembic head'i ve "next" maddeleri bayat olabilir.
> Güncel otorite: `CLAUDE.md` §Current position + `docs/generated/repository_facts.md`
> (üretilmiş, CI'da `--check` ile kapılı).

# ADIM 17 landed → ADIM 18 kickoff

**Bu belge bir sonraki oturumun başlangıç noktasıdır.** En altta **paste-ready resume prompt**
var; temiz bir oturuma onu yapıştır.

---

## 1. Neredeyiz — doğrulanmış gerçek

**`origin/main` = `f8f96c5`** (2026-08-05T02:13:50+03:00) ·
`feat(portfolio): add shared capital and exposure ledger (#573)`

| | |
|---|---|
| Alembic head | `0043_i08_registry_strategy_fks` (tek head) — **ADIM 15/16/17'de migration YOK** |
| `ENGINE_VERSION` | `backtest-engine-v18-gap-adjusted-stop-fill` — **değişmedi** |
| OpenAPI | değişmedi (196 operation / 151 schema) |
| CI (PR #573) | **6/6 SUCCESS**, Backend job 42m42s |
| Frontend | dokunulmadı |

**Unified-clock programının inen üç parçası, ve üçü de üretimden IMPORT EDİLMİYOR:**

| ADIM | modül | satır | test | PR |
|---|---|---|---|---|
| 15 | `domain/backtest/execution/clock.py` | 300 | 27 | #567 |
| 16 | `domain/backtest/execution/intents.py` | 846 | 45 | #571 (+#572 docs) |
| 17 | `domain/backtest/execution/portfolio_ledger.py` | 971 | 100 | #573 |

Containment testleri bunu kilitler ve **ADIM 18'de bilerek güncellenmeleri gerekir**:
`test_the_clock_is_not_wired_into_production_yet`,
`test_nothing_in_production_imports_the_intent_layer_yet`,
`test_nothing_in_production_imports_the_shared_ledger_yet`.
Rollback bugün hâlâ "modülleri sil / revert et".

---

## 2. ÖNCE İNSAN KARARI — iki kapı, ikisi de açık

### Kapı 1 — ADR 0002 onayı

Statü hâlâ **`Proposed`** ve §16 uygulamayı PO/maintainer onayına bağlıyor. **ADIM 15, 16 ve
17'nin üçü de kayıtlı onay olmadan indi.** Onay gelirse statü **Accepted** olur ve §13'ün yedi
açık kararı (OD-1…OD-7) bir amendment tablosuna **çözüm** olarak yazılmalı.

### Kapı 2 — ADR §12 numaralandırması sevk edilenle uyuşmuyor

| ADR §12 der ki | Gerçekte ne indi |
|---|---|
| **ADIM 16** = `run_engine`'den resumable stepper (saf refactor; kabul = **46 golden digest'in TAMAMI sabit**) | **hiç yazılmadı** |
| **ADIM 18** = `ItemIntent` + faz döngüsü | intent yarısı **ADIM 16 olarak** indi (PR #571) |

§12 sınırları "dondurulmuş" ilan edilmişti; sapma sessizce oldu. Karar gerekiyor:

* **(a)** §12'yi bir amendment ile sevk edilen sıraya güncelle (stepper'ı ayrı bir kalem yap), **ya da**
* **(b)** stepper'ı ADIM 18'in önüne geri planla.

**Sessizce devam etmek üçüncü bir seçenek değil** — kabul kriteri (46 digest sabitliği) bir
yerde durmalı.

---

## 3. ADIM 17 ne bıraktı — REUSE listesi (tam sembol adlarıyla)

Hepsi `backend/src/entropia/domain/backtest/execution/portfolio_ledger.py` içinde:

| sembol | ne yapar |
|---|---|
| `SleevePlan` | `P0`/`R0`/`A0`/`Ci0`/`U0`, bir kez. `allocatable(equity)`, `sleeve_capacity(equity)` (compound/fixed), `compounding_mode` |
| `build_sleeve_plan(...)` / `ledger_for_items(...)` | tek çağrılık kurucular; ikincisi faz döngüsünün kullanacağı |
| `PortfolioLedger` | tek hesap defteri. `equity`, `peak`, `realized_pnl`, `fees`, `funding`, `other_costs`, `attribution`, `positions`, `equity_points` |
| `.book_trade(item, gross_pnl=, commission=)` | **tek** equity yazımı, iki muhasebe satırı |
| `.book_fee` / `.book_funding` / `.book_other_cost` | tekil maliyet satırları (funding **işaretli**: + öder, − alır) |
| `.set_position` / `.close_position` | konuşlanmış sermaye; **artışı** bağlar, yerinde reversal reddeder |
| `.gross_exposure` / `.net_exposure` / `.available_capital` / `.deployed_notional()` | cap'lerin ve solvency'nin okuduğu figürler |
| `.publish_snapshot(t_ms)` → `PortfolioSnapshot` | **PV** — defteri dondurur |
| `.begin_apply(t_ms)` | **P7** — yalnız snapshot'ı yayımlayan tick açabilir |
| `.resolve_capacity(...)` → `CapacityDecision` | **P6b** — 3 clamp + yalnız-reddeden solvency; her katmanın headroom'u `limits`'te |
| `.commit_tick(t_ms)` → `PortfolioEquityPoint \| None` | **P9** — `E(t)` oynadıysa TEK nokta |
| `.valuation(t_ms, marks)` → `PortfolioValuation` | mark, `E(t)`'nin **yanında**; marklanamayan `unmarked_items`'a |
| `MarkPrice(price, authority, staleness_ms)` | OD-2 girdisi — **eşik yok** |
| `LEDGER_POLICY_VERSION`, `MONEY_QUANTUM`, `QTY_QUANTUM`, `MONEY_ROUNDING` | ADIM 20'de manifest'e yazılacak rounding sözleşmesi |
| hatalar | `LedgerError` ← `InvalidCapitalPlanError`, `UnknownLedgerItemError`, `LedgerFrozenError`, `MismatchedSnapshotError`, `LedgerSolvencyViolation`, `PositionStateError` |

ADIM 15/16'dan: `clock.iter_ticks` / `ClockTick` / `ItemTickView` / `timeline_identity`;
`intents.form_intent` (P4) / `form_mandatory_intent` (P3) / `form_intents` / `ItemIdentity` /
`ItemDecision` / `EntrySizing` / `ScaleSizing` / `ClosingSize` / `PortfolioSnapshot` /
`build_snapshot` / `snapshot_identities`.

---

## 4. ADIM 18 — sıradaki slice

**Deliverable (ADR §12, §8):** worker'ın **yalnız birden fazla öğe çalıştığında** çağırdığı
**yeni** bir `run_portfolio(...)` giriş noktasında per-tick faz döngüsünü kur.
`run_engine` bu yola **BAĞLANMAZ** — imzası **ve semantiği** aynı kalır (ADR §3.2).

Dosyalar: `application/jobs/backtest_engine.py`, yeni `domain/backtest/portfolio_engine.py`.

**Faz sırası (ADR §8.2), tick başına bir tur:**

```
CLOCK ADVANCE  (iter_ticks)
P0 admit data → P1 funding/fee → P2 pending fills → P3 stop/exit     [ledger yazar]
PV  publish_snapshot(t)        ← defter DONDU, tek E(t)
P4 form_intents (order-free)  → P5 conflict/exposure arbitrasyonu (ADIM 19)
P6a sizing + item risk        → P6b resolve_capacity
P7 begin_apply → schedule/execute → P8 scaling → P9 commit_tick      [ledger yazar]
```

**Kabul:**
* doc 13 §14 **test 11** — tüm itemler tek `E(t)` görür; **item sırası sonucu değiştirmez**
  (`mainboard_items` permütasyonu aynı digest'i vermeli);
* composite eğri **yapıca** zaman-sıralı;
* **cross-item batch invariance** — her öğenin barlarını farklı chunk'lamak aynı sonucu
  vermeli (**bugün hiçbir test kapsamıyor**);
* 46 golden digest'ten **yalnız** `portfolio.*` olanlar oynayabilir; diğerleri **sabit**.

**Rollback:** item döngüsüne dön; `combine_item_runs` yerinde duruyor.

**ADIM 18'de YAPMA:** conflict/NET arbitrasyonu (ADIM 19), manifest alanları veya
`ENGINE_VERSION` bump (ADIM 20), containment kaldırma (yalnız ADIM 20).

---

## 5. Çalışma yöntemi (ADIM 15–17'de işe yarayan)

1. **Direct-author, Workflow yok.** Önceki slice'ın desenini aynala.
2. **Yeni dosyaları Bash heredoc ile yaz** (GateGuard'sız); mevcut dosyaya EDIT fact-force
   tetikler — 4 gerçeği sun, tekrar dene.
3. **Kanon önce.** Formül, öncelik veya sıra kanonda yoksa **uydurma** — OD olarak kaydet.
4. **Parity'yi kontrol et, iddia etme.** Sevk edilmiş bir fonksiyon varsa testte onu **çağır**.
5. **Yeni davranışın testlerini mutasyonla sına.** ADIM 17'de 12 mutasyondan biri (M6) ilk
   turda hayatta kaldı; suite'in geçmesi tek başına kanıt değil.
6. **Ölçümü dürüst raporla.** Tam suite'i **tek** pytest çağrısında koş, **çıktıyı dosyaya
   yaz ve `$?`'i AYRI oku** — ADIM 17'de bu yapılmadı ve exit code yakalanmadı.
   `TEST_DATABASE_URL` ile worktree'ye özel DB kullan (`postgresql+asyncpg://`).
7. **Yerel kapılar:** `ruff check . && ruff format --check . && mypy src && pytest` +
   `python -m entropia.apps.api.openapi_export --check`.

---

## 6. Paralel açık kalemler (ADIM 18'i bloke etmez)

| # | ne | not |
|---|---|---|
| **#559** | DST fold/gap | merged eksen karışık zaman dilimli kaynakları kapsamadan **önce** kapanmalı |
| **#544** | NET semantiği | ADIM 19 ile ya da öncesinde; kanonda tanımsız |
| **#550/#551/#552** | ADIM 12'nin sizing/booking uyuşmazlıkları | **#550 karara bağlanmadan sizing'e dokunma** |
| **#556/#557/#558** | 4 bilinçli `xfail(strict)` | `test_research_point_in_time_parity.py` |
| **#539** | düzeltmesi indi (F-26/PR #564), issue **AÇIK** | kapatma yetkisi insanda |
| **#514** | ekran okuyucu denetimi | kanıtsız kapatılmamalı |
| R-1 | revision pinning | **LANDED** (PR #565) |

---

## 7. Paste-ready resume prompt

```
ENTROPIA V18 — ADIM 18: run_portfolio faz döngüsü (unified clock co-simulation)

ROL: Entropia V18 üzerinde kıdemli principal engineer. Yeni özellik icat etme; canonical
Production V1 sözleşmesini current origin/main üzerinde kanıtla, yalnız doğrulanmış boşluğu
dar bir PR ile kapat, sistemi geriletme.

OTURUM BAŞLANGICI (zorunlu):
1. git fetch --all --prune; git status --short (temiz değilse DUR, hiçbir şey silme/stash'leme)
2. git switch main; git reset --hard origin/main
3. origin/main SHA'sını, tarihi ve açık PR/issue snapshotını kaydet
4. Önceki adımın (ADIM 17 / PR #573) main'e merge edildiğini DOĞRULA — beklenen f8f96c5
5. Oku: docs/ADIM17_LANDED_KICKOFF.md → docs/STAGE2_HANDOFF.md (§ADIM 17 landed + §Next)
   → docs/adr/0002-unified-clock-portfolio-simulation.md §8, §12, §14
   → docs/audit/portfolio_ledger_accounting.md → docs/CODEMAPS/BACKEND_LAYERS.md
6. Eski README/CLAUDE.md/handoff iddiasını current truth sayma; kod ve testle doğrula.

ÖNCE İKİ İNSAN KAPISINI SOR, KOD YAZMADAN:
(1) ADR 0002 hâlâ `Proposed`; §16 PO onayı şart koşuyor ve ADIM 15/16/17 onaysız indi.
(2) ADR §12'nin ADIM 16'sı (run_engine'den resumable stepper, saf refactor, kabul = 46 golden
    digest sabit) HİÇ YAZILMADI; onun yerine ADR'nin ADIM 18'inin intent yarısı ADIM 16 olarak
    indi. Karar: §12'yi amendment ile güncelle mi, stepper'ı geri planla mı?
Yanıt gelmeden ADIM 18 kodu yazma.

BU ADIMIN AMACI: worker'ın yalnız >1 öğe çalıştığında çağırdığı YENİ bir run_portfolio(...)
giriş noktasında per-tick faz döngüsünü kurmak. run_engine BU YOLA BAĞLANMAZ — imzası ve
semantiği aynı kalır (ADR §3.2).

Branch: feat/portfolio-phase-loop
Commit: feat(portfolio): run the per-tick phase loop over the merged axis

KAPSAM:
- CLOCK ADVANCE (clock.iter_ticks) → P0..P3 mandatory (ledger yazar) → PV (publish_snapshot,
  defter donar) → P4 form_intents → P6a sizing → P6b resolve_capacity → P7 begin_apply +
  execute → P8 scaling → P9 commit_tick.
- REUSE ZORUNLU (yeniden yazma): execution/clock.py (iter_ticks, ClockTick, ItemTickView),
  execution/intents.py (form_intents, form_intent, form_mandatory_intent, PortfolioSnapshot),
  execution/portfolio_ledger.py (PortfolioLedger, ledger_for_items, publish_snapshot,
  begin_apply, resolve_capacity, commit_tick, valuation).
- Üç containment testini BİLEREK güncelle; kazara kırma.

ZORUNLU TEST:
- doc 13 §14 test 11: tüm itemler tek E(t) görür; mainboard_items permütasyonu aynı digest.
- composite eğri yapıca zaman-sıralı.
- cross-item batch invariance (bugün hiçbir test kapsamıyor).
- 46 golden digest'ten yalnız portfolio.* olanlar oynayabilir; diğerleri SABİT — digest
  diff'ini senaryo senaryo gerekçelendir.
- Yeni davranışın testlerini MUTASYONLA sına (ADIM 17'de 12 mutasyondan biri ilk turda
  hayatta kaldı; geçen suite tek başına kanıt değil).

YAPMA: conflict/NET arbitrasyonu (ADIM 19), manifest alanı veya ENGINE_VERSION bump (ADIM 20),
containment kaldırma (ADIM 20), margin modeli (ADR §9.5), mark policy seçimi (OD-2 açık),
jointly-insolvent seçim kuralı (OD-3 açık).

DOĞRULAMA: cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy src
&& uv run pytest  (TEST_DATABASE_URL ile worktree'ye özel postgresql+asyncpg:// DB; TEK çağrı,
çıktıyı dosyaya yaz ve $?'i AYRI oku — ADIM 17'de bu yapılmadı) +
uv run python -m entropia.apps.api.openapi_export --check

PR SONUNDA RAPORLA: base SHA, branch, commit, PR, changed behaviour, unchanged boundaries,
targeted tests, full-suite exit code, migration/OpenAPI/codemap etkisi, kalan risk, sonraki
tek adım. Claude merge etmez, tag/release oluşturmaz.

DURMA KOŞULU: Slice 3'ü aş(ma) — faz döngüsü inince PR aç ve dur.
```
