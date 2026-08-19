<!-- doc-status: current -->
> **CANLI KICKOFF.** Bu belge en yeni slice'ın handoff'udur. Bir sonraki slice inince
> `historical`a demote edilir ve yerine yenisi geçer (`check_classification` CI'da doğrular:
> daha yüksek numaralı bir `docs/ADIM<n>…KICKOFF.md` varken canlı işaret eski belgede duramaz).

# ADIM 89 LANDED — `C4` / E5: worker'ın paylaşımlı saat dalı · sıradaki slice için kickoff

> Tam kayıt: `docs/PROJECT_HISTORY.md` §ADIM 89. Bu belge **devam noktasıdır**, kayıt değil.

## 0. Nerede duruyoruz

`SHARED_ALLOCATION_STATUS` = **`future_dev`** (DEĞİŞMEDİ) · `ENGINE_VERSION` **değişmedi** ·
alembic head `0043_i08_registry_strategy_fks` (migration yok) · OpenAPI **değişmedi** ·
**50 golden digest bayt bayt aynı** · blocker **1** (yalnız A-08), verdict **BLOCKED**.

`C1` (#735) → `C2` (#759) → `C3` (#777) → **`C4` (#800) wiring'i indirdi.** Paylaşımlı dal
artık **var ve girilemez**: `_use_unified_clock()`'un ilk conjunct'ı `future_dev` iken `False`,
ve admission zaten her paylaşımlı koşuyu worker'ı görmeden reddediyor.

## 1. Bu slice ne bıraktı (REUSE anchor'ları — tam sembol adlarıyla)

| Sembol | Yer | Ne işe yarar |
|---|---|---|
| `_use_unified_clock(capital_execution)` | `application/jobs/backtest_engine.py` | Paylaşımlı vs bağımsız kararının verildiği **tek** yer. Bayrak burada **okunur**, cache'lenmez. |
| `_replay_shared_clock(...)` | aynı dosya | `iter_portfolio`'yu **elle** boşaltır (`for` dönüş değerini atar), stride'da `_cancellation_requested` yoklar, `project_portfolio_run` ile projekte eder |
| `_TICK_CHECKPOINT_STRIDE = 500` | aynı dosya | ADR §14 **A21**. Gerekçesi sabitin yanında yazılı: gecikme/round-trip takası, **doğruluk düğmesi değil** |
| `_shared_participants(...)` | aynı dosya | `_EngineParticipant` kurucu. **`portfolio_rules=None`** (ADR §12 satır 19: arbitrasyon precedence'ı emekliye ayırır, yalnız paylaşımlı yolda) |
| `_manifest_pin_ordinals(...)` / `_pinned_records(...)` | aynı dosya | `pin_ordinal` manifest sırasından; projeksiyonun `PinnedItem`'ları (non-Strategy dahil) |
| `_AUTHORISED_LOOP_CALLERS` / `_AUTHORISED_PROJECTION_CALLERS` | `test_oracle_portfolio_containment_gate.py` | Daraltılmış tripwire — her biri **tek** modül |
| `test_backtest_worker_clock_selector.py` | `tests/unit/` | İki conjunct'ın **ayrı** pinleri + `pin_ordinal` numaralaması. **Substring assertion'ları bunun yerini TUTMAZ** |
| `test_backtest_worker_shared_clock_branch.py` | `tests/integration/` | Tuzaklı bağımsız koşu · çok-item'lı admission reddi · varsayılan şeklin fail-closed'ı · uçtan uca eş-simülasyon · A21 iptali |
| `_co_simulable_strategies(monkeypatch)` | aynı dosya | Adaptörün kabul ettiği **tek** şekli kuran fixture — eş-simüle eden her yeni test bunu yeniden kullanmalı |

## 2. Pazarlıksız sınırlar (bunları gevşetme)

1. **Tripwire'ın iki assertion'ı DOKUNULMAZ:** `combine_item_runs(` ve
   `for prepared in prepared_items:`. Birini silmek her bağımsız kompozit Result'ı sessizce
   yeniden fiyatlar.
2. **Lift pinleri `C9`'undur, `C4`'ün değil:** `SHARED_ALLOCATION_STATUS`, `ENGINE_VERSION`
   literali, `5000.00`/`3000.00` fixture'ı. Bunları düzenleyen bir PR sessizce ADIM 20 olmuştur
   ve önce **`G10` (ADR §16 Gate 2, HİÇ TALEP EDİLMEDİ)** gerekir.
3. **Bayrak worker'da tek fonksiyondan okunur.** `test_shared_allocation_two_world_gate.py`
   bunu **AST üzerinden** kanıtlar. İkinci bir okuyucu kırmızıdır.
4. **Worker'ın metnine containment sabitinin ADINI yazma** — aynı test bu dosyanın metnini
   tarar ve tarama çağrıyı docstring'den ayıramaz. Capability'yi adlandır, sabiti değil.
5. **Substring assertion'larına güvenme.** Ölçüldü: conjunct silinse bile yeşil kalırlar.
   Davranışsal pin `test_backtest_worker_clock_selector.py`'dedir.

## 3. Sıradaki slice: **`C6`** (admission blocker taksonomisi) ve **`C7`** (A16 manifest split)

Plan: `docs/implementation/final_closure_ordered_plan_2026-08-13.md` §PACKAGE C. İkisi de
`C4` merged ister, birbirlerine göre **ayrık** (admission taksonomisi vs manifest).

- **`C6` BLOKLU — `G11` + `G12` brifingli ama İMZASIZ.** Ve `C4` maliyeti **ölçtü**:
  `participant.py::_unsupported_shapes`'in on bir maddesi bugünkü şema **varsayılanlarıyla**
  çakışıyor. Zorla açılmış bayrakla koşulan standart fixture **üç** madde birden ihlal ediyor
  (`entry_timing`/`exit_timing` = `next_candle_open`, `same_direction_stacking` =
  `allow_stacking`). `C6` bunları admission blocker'a çevirdiğinde **mevcut stratejilerin çoğu
  paylaşımlı koşudan düşer** → bu bir **ürün kararıdır**, test slice'ının değil.
- **`C7`** ayrıca `C5` ister; `C5`'in hedefi **zaten sevk edilmiş** (ADIM 72'nin ölçümü), ama
  ADR kaydı **imzasız**. `manifest.py`'ye dokunan ilk slice `C7`'dir — `C4` ona **dokunmadı**.

## 4. Çalışma yöntemi (bu slice'ta işe yarayan)

- **SLICE'A BAŞLAMADAN ÖNCE AÇIK PR'LARI TARA.** ADIM 86 bunu ders olarak yazmıştı ve bu slice
  yine de düştü: ağaç ve `PROJECT_HISTORY` tarandı, `list_pull_requests(state=open)` **atlandı**
  → aynı `C4` üç kez paralel yazıldı. Prompt'un verdiği dal adı bile alınmıştı.
- **Kaynak METNİNİ okuyan testler üçüncü bir kümedir.** `execution.*` import edenleri ve
  fonksiyonu **çağıranları** taramak yetmez; `grep -rln '<dosya>.py' tests/` de koş. CI'ın
  yakaladığı tek kırmızı buydu.
- **Negatif kontrolü ürünü GERÇEKTEN değiştirerek koş** ve **hangi** assertion'ın kırmızıya
  döndüğünü oku. Bu slice'ta yedi kontrol koştu; ikisi gate'in substring'lerini kırmızıya
  **çevirmedi** ve bulgu tam olarak buydu.
- **Alt küme koşarken `--no-cov`.** Tam suite coverage kapısıdır ve ~53 dk sürer.
- **Postgres yoksa** `/var/tmp`'de unprivileged bir PG16 cluster kur (`initdb` root koşmaz),
  `LC_ALL=C.UTF-8`, `TEST_DATABASE_URL=postgresql+asyncpg://entropia@127.0.0.1:5432/entropia`.
- **Rebase'i zamanlayıcıyla yapma** (ADIM 74). Kapanış ritüeli + numara + rebase **tek pass**,
  merge'den hemen önce.

---

## Paste-ready resume prompt

```
ENTROPIA V18 — sıradaki closure slice'ı (`C6` ya da `C7`)
ROL: Entropia V18 Principal Engineer ve Release Closure Owner. Konuşma dili TÜRKÇE.

SESSION START (atlamadan):
  git fetch --all --prune ; git status --short   -> kirliyse DUR
  git switch main ; git reset --hard origin/main ; git rev-parse HEAD
  ***list_pull_requests(state=open) KOŞ*** — ADIM 89 bunu atladı ve aynı slice ÜÇ KEZ yazıldı.
  Taban beklentin YOKTUR — her iddiayı AĞACA karşı yeniden ölç.

OKUMA SIRASI: (1) docs/implementation/final_closure_ordered_plan_2026-08-13.md §PACKAGE C
  (2) docs/implementation/closure_design_portfolio_performance_2026-08-13.md
  (3) docs/adr/0002-unified-clock-portfolio-simulation.md
  (4) docs/ADIM89_LANDED_KICKOFF.md  ← C4'ün bıraktıkları ve pazarlıksız sınırlar
  (5) docs/generated/repository_facts.md = SAYISAL OTORİTE

ÖN KOŞUL — DOĞRULA, GÜVENME:
  `C6` için: G11 VE G12 İMZALI mı? (docs/decisions/ + ADR-0002 §13.2). İMZASIZSA BAŞLAMA —
    C4 ölçtü ki bu liste şema VARSAYILANLARIYLA çakışıyor (`same_direction_stacking =
    allow_stacking`), yani admission blocker'a çevirmek mevcut stratejilerin çoğunu düşürür.
    Bu bir ÜRÜN KARARIDIR; imzasızsa slice DURUR ve karar sorulur.
  `C7` için: `C5` ve `C4` merged mi? manifest.py'ye ilk dokunan slice budur.

DEĞİŞMEYECEK: `SHARED_ALLOCATION_STATUS` = `future_dev` · `ENGINE_VERSION` literali ·
  5000.00/3000.00 fixture'ı · tripwire'ın `combine_item_runs(` ve
  `for prepared in prepared_items:` assertion'ları · 50 golden digest.
  Bunlardan birini düzenlemek gerekiyorsa slice sessizce ADIM 20 olmuştur -> G10 gerekir -> DUR.

KAPILAR (hepsi exit 0; `| tail` KULLANMA, $?'i AYRI oku; alt kümede --no-cov):
  cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy src
  uv run python -m entropia.apps.api.openapi_export --check ; uv run alembic heads (tek head)
  uv run pytest -q   (tam suite = coverage kapısı >=90, ~53 dk)
  (backend'den) uv run python ../scripts/generate_repository_facts.py --root .. --check
  repo KÖKÜNDEN: node scripts/memory_index.mjs --check

YÖNTEM: Her assertion'ı NEGATİF KONTROLDEN geçir — davranışı üründen KALDIR, testin KIRMIZIYA
  döndüğünü VE HANGİ assertion'da döndüğünü gör. Yamanın gerçekten uygulandığını ayrıca
  doğrula. and/or kapılarında bileşik sonucu değil TERİMLERİ ayrı pinle. Kaynak METNİ okuyan
  testleri de tara (`grep -rln '<dosya>.py' tests/`) — sadece import/çağrı taraması yetmez.

KAPANIŞ: CLAUDE.md §Session CLOSING'in 6 maddesi. ADIM numarasını EN SONDA, merge'den hemen
  önce `grep '^## ADIM' docs/PROJECT_HISTORY.md` ile ata — bu haftada beş numara açık PR'ların
  altından çekildi. Rebase + numara + ritüel TEK PASS. PR aç, DUR, MERGE ETME.
```
