# ADIM 20 BLOCKED — unified portfolio oracles landed, containment NOT lifted (PR #583) · sıradaki slice kickoff'u

> Bu belge **ADIM 20'nin** kapanış handoff'udur. En altta **paste-ready resume prompt** var.
> Otorite sırası: bu belge → `docs/audit/unified_portfolio_oracle_acceptance.md` →
> `docs/adr/0002-unified-clock-portfolio-simulation.md` §12/§13/§14/§16 →
> `docs/STAGE2_HANDOFF.md` → `docs/spec/13_*`.

---

## 1. Nerede duruyoruz (empirik, 2026-08-05)

| Olgu | Değer |
|---|---|
| `origin/main` | `b0bb4a0` (PR #581, ADIM 19 provenance) |
| ADIM 20 branch / commit | `test/portfolio-unified-oracles` / `fd0ead5` |
| ADIM 20 PR | **#583 — DRAFT / BLOCKED, merge edilmemeli** |
| Blocking issue | **#582** |
| Alembic head | `0043_i08_registry_strategy_fks` — tek head, **migration eklenmedi** |
| `ENGINE_VERSION` | `backtest-engine-v18-gap-adjusted-stop-fill` — **bilerek bump EDİLMEDİ** |
| OpenAPI | değişmedi · **üretim kodu hiç değişmedi** |
| `SHARED_ALLOCATION_STATUS` | **`future_dev`** — containment kaldırılmadı |

---

## 2. ADIM 20 ne yaptı — tek cümlede

Containment lift'in kanıt paketini yazdı ve **lift'i reddetti**: kaldırma koşullarının motorla
ilgili olanları karşılanamıyor, çünkü **kabul edilecek birleşik-saat yolu üretimde yok.**

## 3. Reddin gerekçesi — kod yazmadan önce üretilen probe'lar

| Probe | Sonuç |
|---|---|
| `grep -rn "def run_portfolio" backend/src` | **eşleşme yok** — ADR §12'nin **ADIM 18**'i hiç yazılmadı |
| altı `execution/` unified-clock modülünün `execution/` dışı import'u | **yok** |
| `application/jobs/backtest_engine.py:298` | hâlâ `for prepared in prepared_items:` |
| `application/jobs/backtest_engine.py:363` | hâlâ `combine_item_runs(...)` |
| ADR §12 **ADIM 16** (resumable stepper, saf refactor) | **hiç yazılmadı** — atlandı |
| `manifest.py` policy alanları | yok |
| ADR 0002 statüsü | **`Proposed`** (§16 onay kapısı) |

ADIM 15–19'da inen altı modül **kopuk bir ada**: 216 testle kaplı, eksiksiz primitifler — ama
hiçbir üretim yolu onlara ulaşmıyor.

---

## 4. REUSE ANCHORS — ADIM 20'nin bıraktığı tam sembol adları

### 4.1 Faz döngüsü harness'ı (ADIM 18'in yerine geçmesi gereken şey)

`backend/tests/unit/oracles/portfolio_harness.py` — **test-owned**, ADR §8.2 faz sırasını
(P1 → P3 → PV → P4 → P5/P6b → P7 → P9) sevk edilmiş primitifler üzerinde kurar.

| Sembol | Rolü |
|---|---|
| `ScriptedItem` | bir kompozisyon öğesi: pin kimliği, bar ekseni, senaryolu kararlar |
| `simulate(items, *, pool, reserve_percent, compound, policy, max_total_exposure_notional, max_position_notional, caller_order, batch)` | **ADIM 18 indiğinde `run_portfolio` ile DEĞİŞTİRİLECEK tek fonksiyon** |
| `_run_tick(...)` | tek tick'in tam ADR §8.1 çevrimi |
| `TickRecord` | `t_ms, timestamp, views, snapshot, mandatory, intents, report, equity_point` |
| `PortfolioRun` | `ledger, ticks` + `dated_points`, `instants`, `max_drawdown`, `tick_at(ts)` |
| `row(timestamp, close)` | `state._normalize`'ın kabul ettiği OHLCV satırı |

### 4.2 Oracle dosyaları (25 test)

| Dosya | Test | Neyi kanıtlıyor |
|---|---|---|
| `tests/unit/oracles/test_oracle_portfolio_clock.py` | 10 | tek `E(t)`, mandatory-before-PV, inşa gereği zaman sıralı eğri, no-lookahead, heterojen timeframe çekişmesi, çağıran-sırası + batch değişmezliği, 12×72 yük |
| `tests/unit/oracles/test_oracle_portfolio_capital.py` | 11 | doc 13 §14 test 10, sabit `R0`, compound vs fixed, ortak insolvency **tam red**, share transferi yok, exposure cap, karşıt yön, NET fail-closed, muhasebe kimliği, per-item mutabakat |
| `tests/unit/oracles/test_oracle_portfolio_containment_gate.py` | 4 | **5000.00 (sıralı) vs 3000.00 (birleşik)** aynı işlemlerde + dört kapı olgusu |

**Kritik testler (ADIM 18/20'de yeniden yazılmalı, SİLİNMEMELİ):**
`test_the_unified_clock_reports_the_drawdown_the_sequential_fold_overstated`,
`test_a_stop_that_fires_at_a_tick_shrinks_its_siblings_sleeve_at_that_same_tick`,
`test_the_same_trades_read_5000_sequentially_and_3000_on_one_clock`.

### 4.3 Kabul raporu

`docs/audit/unified_portfolio_oracle_acceptance.md` — A1–A22 durum tablosu, decision-record §6
koşulları, desteklenmeyen politikalar, insan kapıları.

---

## 5. DÜRÜST SINIR — bunu atlama

Oracle'ların sürdüğü faz döngüsü **TEST-OWNED**, çünkü `run_portfolio` yok. Yeşil koşu
**primitifler** hakkında kanıttır, **sevk edilen engine hakkında DEĞİL** — engine onları hiç
çağırmıyor. ADIM 18 indiğinde `portfolio_harness.simulate` yerine `run_portfolio` konmalı ve
oracle'lar **değişmeden** yeniden koşulmalı; ADR §14'ün istediği kanıt **o ikamedir**.

Bu sınır üç yerde yazılı: harness docstring'i §"HONEST BOUNDARY", iki test modülünün
docstring'i, ve raporun §2'si. **Kaldırma.**

---

## 6. Kaldırmayı bloklayanlar (ADIM 20'nin ölçtüğü)

**Yapısal (üretim yolu yok):** A1 (dış döngü), A3 (yayımlanan tek `E(t)` sizing'e ulaşmıyor),
A5 (sevk edilen yol hâlâ 5000 diyor), A15 (`ENGINE_VERSION` bump), A16 (manifest alanları),
A21 (cancel checkpoint'i hâlâ **item başına**, `jobs/backtest_engine.py` O-06 checkpoint #3).
A4/A18 gerçek `EngineOutput` **digest**'i istiyor.

**Test önkoşulu:** **A17** — `tests/integration/test_research_point_in_time_parity.py`'de
**4 `xfail(strict=True)`** (#556 ×2, #557, #558). "green, unweakened" değil.

**İnsan kapıları:** ADR `Proposed` (§16) · ADR §12 numaralandırması sevk edilenle uyuşmuyor
(ADIM 16 atlandı) · **OD-1…OD-7** açık (ADR R-5: OD-2/OD-3 kapanmadan lift, açıklanmamış bir
politika geri getirir) · **#544 (NET)** · **#559 (DST)**.

**Kapalı, kayda geçsin:** **R-1** → `a33d3e4 fix(readiness): pin the allocation revision the
snapshot names`.

---

## 7. Doküman-gerçeği boşluğu (ADIM 20'nin yan bulgusu)

`docs/STAGE2_HANDOFF.md` ve `docs/PROJECT_HISTORY.md` **PR #575 (arbitration) ve #581
(provenance) için `landed` kaydı taşımıyordu**; handoff'un son `## Next:` bloğu hâlâ ADIM 18'i
sıradaki iş gösteriyordu. Bu kapanış o boşluğu **işaret ediyor ama başkasının slice kaydını
uydurmuyor** — #575/#581'in tam anlatısı hâlâ eksik ve onu yazacak olan o slice'ları indirendir.

---

## 8. Sıradaki tek adım

**ADIM 20 DEĞİL.** Sırayla:

1. **ADR 0002'yi karara bağla** — onayla (statü `Accepted`, §13'ün yedi kararı bir amendment
   tablosuna yazılır) **veya** §12'yi sevk edilene göre düzelt (atlanan ADIM 16 dahil).
   İkisi de **insan** işi; agent yapamaz.
2. **ADIM 18 — `run_portfolio(...)`**: worker'ın birden fazla öğe çalıştığında çağırdığı yeni
   giriş noktası. `run_engine` imzasını **ve semantiğini** korur (ADR §3.2).
3. Harness'ı ona yönlendir: `portfolio_harness.simulate` → `run_portfolio`, 25 oracle
   **değişmeden** yeşil olmalı. Bu, A1/A3/A5'i PRIMITIVE'den MET'e taşıyan tek hamledir.

Bunlar kapanmadan containment-lift matrisinde başka hiçbir satır kapanamaz.

---

## 9. Çalışma döngüsü (bu slice'ta işleyen yöntem)

1. **Önce kusuru üret.** Bu slice'ın tüm meşruiyeti §3'teki yedi probe'dan geliyor — hiçbiri
   dokümana değil, koda soruldu.
2. **Oracle'ın ısırdığını kanıtla.** Dört taşıyıcı literali bozdum (`3000→5000`,
   sleeve `3500→4500`, compound `2500→4500`, red edilen `0→5` unit) → **tam olarak o dört
   test kırıldı**, başkası değil. Yeşil bir suite'e "ısırıyor" demeden önce bunu yap.
   (Faz sırasını bozarak yapılan ilk mutasyon **geçersizdi**: `arbitrate` donmuş ledger ister,
   döngü yapısal olarak çöktü ve HER test kırıldı — bu tespit değil, crash'tir.)
3. **Beklenen değerler literal.** Engine helper'ından beklenti üretme — test implementasyonun
   aynası olur.
4. **Read-only subagent** araştırma için; üretim değişikliğini yalnız ana oturum yapar.
5. **Lokal doğrulama:** `cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest -q`
   — tam suite'i **tek çağrıda**, çıktıyı **dosyaya**, `$?`'i **ayrı** oku.
   `TEST_DATABASE_URL` ile worktree'ye özel izole DB (**`postgresql+asyncpg://`**).
   Alt küme koşarken `--no-cov` ekle.
6. **GateGuard:** YENİ dosya → Bash heredoc (gate-free). Mevcut dosyaya EDIT/WRITE → 4 olgu sun,
   retry. `git checkout --` gibi destructive komutlar da kapıdan geçer.

---

## 10. Paste-ready resume prompt

```text
ENTROPIA — sıradaki slice: ADR 0002 karara bağlama → ADIM 18 (run_portfolio faz döngüsü)

ÖNCE DOĞRULA (handoff STALE-BY-DEFAULT — özete güvenme):
  git fetch --all --prune && git log --oneline origin/main -6 && gh pr list --state all --limit 8
  gh pr view 583   # ADIM 20 — DRAFT/BLOCKED, merge edilmiş OLMAMALI
  gh issue view 582

OKUMA SIRASI (otorite sırasıyla):
  1. docs/ADIM20_BLOCKED_KICKOFF.md                        ← bu belge
  2. docs/audit/unified_portfolio_oracle_acceptance.md     ← A1–A22 durum tablosu
  3. docs/adr/0002-unified-clock-portfolio-simulation.md   ← §12 sınırlar, §13 OD-1..7, §14 matris, §16 kapı
  4. docs/STAGE2_HANDOFF.md — en alttaki "## Next:" bloğu
  5. backend/tests/unit/oracles/portfolio_harness.py       ← §"HONEST BOUNDARY" ÖNCE oku

DURUM: ADIM 20 containment'ı KALDIRMADI. SHARED_ALLOCATION_STATUS = future_dev.
  Sebep bir kırmızı oracle değil: run_portfolio YOK, altı unified-clock modülü üretimden
  hiç import edilmiyor, worker hâlâ item döngüsü + combine_item_runs. ADR'nin ADIM 16'sı
  (resumable stepper) atlandı. ADR hâlâ Proposed.

GÖREV — SIRAYLA:
  1. İNSAN KAPISI: ADR 0002 onaylanacak (statü Accepted + §13'ün yedi kararı amendment
     tablosuna) VEYA §12 sevk edilene göre düzeltilecek. Agent bunu yapamaz — SOR.
  2. ADIM 18: yeni run_portfolio(...) giriş noktası, worker >1 öğe çalıştırınca çağırır.
     run_engine imzasını VE semantiğini korur (ADR §3.2) — 46 golden digest kımıldamamalı.
     Faz sırası: ADR §8.2, referans implementasyon portfolio_harness._run_tick.
  3. portfolio_harness.simulate -> run_portfolio ikamesi; 25 oracle DEĞİŞMEDEN yeşil olmalı.
     Bu, A1/A3/A5'i PRIMITIVE'den MET'e taşıyan tek hamledir.
  ADIM 20'yi (containment lift) TEKRAR DENEME — 2 ve 3 bitmeden matris kapanmaz.

KURALLAR (CLAUDE.md'den, ihlal etme):
  - Containment guard'ları (test_nothing_in_production_imports_*) ADIM 18'de BİLEREK güncellenir;
    kazara kırılmamalı.
  - ENGINE_VERSION'a ADIM 20'ye kadar DOKUNMA. Migration/OpenAPI yok.
  - Beklenen değerler literal; engine helper'ından beklenti üretme.
  - Direct-author, Workflow yok. YENİ dosyayı Bash heredoc ile yaz (GateGuard gate-free).
  - Kod arama: önce codebase-memory-mcp (search_graph / get_code_snippet), sonra dosya oku.

DOĞRULAMA:
  cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy src
  TEST_DATABASE_URL=postgresql+asyncpg://entropia:entropia@localhost:5432/<worktree_db> \
    uv run pytest -q > /tmp/full.log 2>&1; echo $?   # tek çağrı, exit code AYRI oku
  Alt küme koşarken --no-cov ekle. Suite koşarken uv sync/uv run çalıştırma.

KAPANIŞ: CLAUDE.md §"Session CLOSING ritual" — 6 madde, istisnasız.
```

---

*ADIM 20 kapanışı · 2026-08-05 · `origin/main` @ `b0bb4a0` · alembic head `0043_i08_registry_strategy_fks` · containment KALDIRILMADI*
