<!-- doc-status: historical -->
> **HISTORICAL RECORD — bu belge GÜNCEL GERÇEK DEĞİLDİR.** Yazıldığı andaki durumu
> kaydeder; SHA'lar, sayılar, alembic head'i ve "next" maddeleri bayat olabilir.
> Güncel otorite: `CLAUDE.md` §Current position + `docs/generated/repository_facts.md`
> (üretilmiş, CI'da `--check` ile kapılı).

# ADIM 16 LANDED — `run_engine`'in bar döngüsü resumable stepper'a çıkarıldı (PR #602) · sıradaki slice kickoff'u

> Bu belge **ADIM 16'nın** (engine-destekli `ItemParticipant` çiftinin **PR A**'sı) kapanış
> handoff'udur. En altta **paste-ready resume prompt** var.
> Otorite sırası: bu belge → `docs/adr/0002-unified-clock-portfolio-simulation.md` §12/§15 R-4 →
> `docs/ADIM18_LANDED_KICKOFF.md` §6 → `docs/STAGE2_HANDOFF.md` §Next → `docs/spec/13_*`.

---

## 1. Nerede duruyoruz (empirik, 2026-08-05)

| Olgu | Değer |
|---|---|
| `origin/main` | `c5d4c5d` (PR #602) |
| PR / branch | **#602 merged** 20:00:24Z · `feat/adim-16-engine-stepper` |
| Değişen dosya | **iki**: `backend/src/entropia/domain/backtest/engine.py` + yeni `backend/tests/unit/test_backtest_engine_stepper.py` |
| Alembic head | `0043_i08_registry_strategy_fks` — **migration yok** |
| `ENGINE_VERSION` | `backtest-engine-v18-gap-adjusted-stop-fill` (`manifest.py:126`) — **bilerek bump EDİLMEDİ** |
| OpenAPI | **değişmedi** (route/şema dosyasına dokunulmadı) |
| `SHARED_ALLOCATION_STATUS` | **`future_dev`** — containment kaldırılmadı |
| 46 golden digest | **46/46 kımıldamadı** — ADR §15 R-4'ün tek kabul kriteri |
| CI (#602) | **8 job pass**, 2 heavy job skipped · `Backend — lint, type, test` 44m09s |
| PR'da bildirilen suite | 3699 passed · 4 xfailed · 0 failed · coverage **%93.29** (kapı ≥90; `engine.py` %95.1) |

---

## 2. ADIM 16 ne yaptı — tek cümlede

`run_engine`'in ~2400 satırlık gövdesinin içine gömülü **1355 satırlık bar döngüsünü** askıya
alınabilir bir stepper'a çıkardı; `run_engine` imzasını, docstring'ini ve semantiğini koruyarak
onun üzerinde **dokuz satırlık bir sürücü** oldu.

**Neden şimdi:** ADR §12 ADIM 16'yı resmen **SKIPPED** işaretlemişti (faz döngüsü aynı yere öbür
taraftan varmıştı), ama aynı §12 düzeltme notu stepper'ın **worker call site'ının ön koşulu**
olarak kaldığını söylüyor: gerçek engine ile desteklenen bir katılımcı **tek bir item'ı verilen
`t`'ye ilerletebilmek** zorunda ve döngü o dev fonksiyonun içindeyken `engine.py`'de bunu
yapabilecek hiçbir şey yoktu.

---

## 3. REUSE ANCHORS — birebir sembol adları (yeniden yazma, BUNLARI çağır)

| Sembol | Yer | Rolü |
|---|---|---|
| `_ItemStepper` | `engine.py:756` (frozen dataclass) | bir item'ın **bar'lar arasında askıya alınmış** replay'i |
| `_ItemStepper.step(bar)` | — | replay'i **BİR** normalize bar ilerletir (normalize eden ÇAĞIRANDIR: `_normalize`) |
| `_ItemStepper.finalize()` | — | end-of-data: duran emri iptal et, açık pozisyonu kapat. Son `step`'ten sonra **bir kez** |
| `_ItemStepper.output()` | — | `(ctx, led)` → `EngineOutput` projeksiyonu. **Hiçbir şey replay etmez** |
| `_ItemStepper.open_position()` | — | o an tutulan `_Position \| None` — katılımcının carry / mandatory exit kararı için replay içine uzanmadan okuyacağı tek şey |
| `_ItemStepper.ledger` / `.ctx` | — | canlı `_Ledger` ve `_RunConfig` |
| `_build_stepper(...)` | `engine.py:779` | `run_engine`'in bar döngüsüne kadarki gövdesi, **değişmeden**: aynı fail-closed `UnresolvedStrategyError`, aynı ledger seed, aynı `_RunConfig` snapshot'ı, aynı karar closure'ları |
| `run_engine(...)` sürücüsü | `engine.py:3245` | `_build_stepper` → `for batch: for raw: _normalize → step` → `finalize()` → `output()` |

**Replay state'i factory'nin closure'ında kaldı** — bar döngüsünün zaten tuttuğu yerde. Döngüyü
dışarı almak **hiçbir state'i scope'lar arasında taşımadı**, bu yüzden bir sayıyı kımıldatamazdı.

`_ItemStepper` / `_build_stepper` **module-private ve `__all__`'da DEĞİL**: `engine.py` dışından
onları çağıran henüz yok. Tüketiciyi veren şey **PR B**'dir.

---

## 4. Saf refactor iddiası neye dayanıyor (yeniden üretilebilir)

- **Taşınan her satır verbatim.** Edit sonrası taşınan aralıklar `HEAD` ile byte-byte
  karşılaştırıldı: setup **955**, step gövdesi **1351**, end-of-data settlement **44**, output
  assembly **15** — hepsi aynı. Formatter dedent sonrası tek satıra sığan **tam bir** `max(...)`
  çağrısını topladı, başka fark yok.
- **`nonlocal` bloğu ölçüldü, tahmin edilmedi.** Döngü gövdesi üzerinde bir AST geçişi bar'lar
  arasında taşınan **tam on** ad bildiriyor: `current_day` · `exit_touch` · `funding_idx` ·
  `pending` · `position` · `prev_entry_signal` · `prev_scale_signal` · `scale_signal` ·
  `working_limit` · `working_stop`. Gövdenin bağladığı **diğer 83** ad, definite-assignment
  analiziyle her yolda okunmadan önce yazıldığı kanıtlanarak step'e local bırakıldı — analiz
  yanlış olsaydı hata modu **gürültülü bir `UnboundLocalError`**'dur, sessizce farklı bir sayı
  değil.
- **Kabul kriteri 46 digest ve BAŞKA HİÇBİR ŞEY** (ADR §15 R-4). 46/46 kımıldamadı.

### 4.1 Digest'lerin göremediği yarı — yeni test

`tests/unit/test_backtest_engine_stepper.py` (**4 test**, 216 satır) tam olarak digest'lerin
kanıtlayamadığını kilitler: `run_engine` stepper'ı **tek bir generator'dan kesintisiz** besler,
yani sessizce per-bar local'a dönmüş bir taşıyıcı ad **yine de** kayıtlı digest'i üretebilirdi.
Test aynı senaryoları **çağrı başına bir bar**, her bar çiftinin arasında askıya alarak replay
eder ve digest özdeşliğini iddia eder:

| Test | Neyi kilitliyor |
|---|---|
| `test_stepping_one_bar_at_a_time_replays_identically_to_run_engine` | taşıyıcı ad başına bir vaka: duran limit emri, hiç dokunmayan limit, tetiklenmemiş stop, ladder'layan pozisyon, iki kayıt boyunca funding ödeyen tutulan pozisyon, blackout gününü aşan sinyal |
| `test_the_batching_of_the_bar_stream_is_not_observable` | batch sınırı bir karar değiştiremez |
| `test_the_stepper_holds_an_open_position_between_steps` | `open_position()` askı boyunca doğru |
| `test_the_stepper_refuses_an_unresolved_strategy_before_any_bar` | fail-closed `UnresolvedStrategyError` hâlâ **ilk bar'dan önce** |

---

## 5. DÜRÜST SINIR — bunu atlama

1. **Stepper'ın üretimde henüz İKİNCİ bir tüketicisi yok.** Bu PR'ın tek gözlemlenebilir etkisi
   `run_engine`'in döngü yerine sürücü olmasıdır. `jobs/backtest_engine.py:298` hâlâ item
   döngüsü, `:363` hâlâ `combine_item_runs`.
2. **Bu slice yerelde tam suite ile doğrulanmadı** — buradaki 3699/93.29 sayıları **#602'nin
   kendi PR gövdesinden** alınmıştır; bağımsız otorite **CI koşusudur** (8/8 pass).
3. **Kayıt borcu (bu slice'ın kapsamadığı):** `#594` (deploy acceptance), `#599`, `#600`, `#601`
   merged olduğu hâlde hiçbir dokümanda kaydı yok; `#597` (worker actor event loop) **açık ve
   CI yeşil, merge edilmemiş**. Bunlar başka slice'ların kaydıdır — **burada uydurulmadı**,
   yalnız adlandırıldı.

---

## 6. Sıradaki tek adım — **PR B: engine-destekli `ItemParticipant` + worker call site**

ADIM 20 DEĞİL. `docs/ADIM18_LANDED_KICKOFF.md` §6'nın (a)/(b) ayrımında **(a) bitti**, sırada (b):

1. **Adaptör.** `_ItemStepper`'ın üstüne `portfolio_engine.ItemParticipant`'ı uygula:
   `identity` · `stream` · `instrument_id` · `carry`→`CarryCharges` (P1) ·
   `mandatory_exit`→`MandatoryExit` (P3) · `entry`→`ItemIntent` (P4).
   **`entry` kendi `ItemIntent`'ini `form_intent` ile kurar** — boyut item'ın kendi
   `StrategyConfig`/`FillCosts`'unu ister (`costs._effective_fill` → `sizing._position_size`),
   faz döngüsü onu hesaplamaz, yalnız **doğrular** (`MisformedIntentError`).
2. **Call site.** `jobs/backtest_engine.py:298`'deki item döngüsünü `run_portfolio` ile değiştir —
   **YALNIZ >1 item çalışırken**; tek item `run_engine`'de kalır (ADR §3.2).
3. **Beklenen digest hareketi:** 9 `portfolio.*` digest'inin **kımıldaması BEKLENİR** ve her biri
   tek tek gerekçelendirilir; **37 non-portfolio digest KIMILDAMAMALI**.
4. Cancel/pause checkpoint'i (O-06) bugün **item başına**; tick tabanlısı bu PR'a bağlı (A21).

**Sonra ADIM 20** (manifest policy alanları, `ENGINE_VERSION` bump, digest yenileme, containment
lift, Result portfolio metadata + OpenAPI, codemaps). Hâlâ açık ön koşullar: **A17** (4
`xfail(strict)` — #556 ×2, #557, #558) · OD-1/OD-2/OD-6 kapıları **kod olarak yok** ·
`MARK_STALENESS_POLICY` + `CONTENTION_SELECTION_STATUS` flip'leri · **#544 (NET)** · **#559 (DST)**.

---

## 7. Çalışma döngüsü (bu slice'ta işleyen yöntem)

1. **Restructure'ı re-price'tan ayır.** ADR §15 R-4 bu ayrımı bir kez kaybetti (ADIM 16
   atlandığında). PR A hiçbir sayıyı kımıldatmaz, PR B kımıldatır — **tek PR'da birleştirme**,
   yoksa kımıldayan digest'i atfedecek hiçbir şey kalmaz.
2. **Taşıyıcı state'i ÖLÇ, tahmin etme.** On `nonlocal` adı bir AST geçişinden geldi; kalan 83
   ad definite-assignment ile elendi.
3. **Digest'in göremediğini teste yaz.** Kesintisiz bir sürücü, sessizce local'a dönmüş bir
   taşıyıcıyı gizler — bar-bar askıya alan replay onu gösterir.
4. **Lokal doğrulama:** `cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy src`
   + tam suite **tek çağrıda**, çıktı **dosyaya**, `$?` **AYRI** oku.
   `TEST_DATABASE_URL` ile worktree'ye özel izole DB (**`postgresql+asyncpg://`**).
   Alt küme koşarken `--no-cov` ekle; suite koşarken `uv sync`/`uv run` çalıştırma.
   `git status backend/uv.lock` — `uv sync` lock'u kirletebilir.
5. **GateGuard:** YENİ dosya → Bash heredoc (gate-free). Mevcut dosyaya EDIT/WRITE → 4 olgu sun.

---

## 8. Paste-ready resume prompt

```text
ENTROPIA — sıradaki slice: PR B — engine-destekli ItemParticipant + worker call site

ÖNCE DOĞRULA (handoff STALE-BY-DEFAULT — özete güvenme):
  git fetch --all --prune && git log --oneline origin/main -6 && gh pr list --state all --limit 8
  grep -rn "run_portfolio(" backend/src   # ÜRETİMDE ÇAĞIRAN VAR MI? yoksa aşağısı geçerli
  grep -n "_build_stepper\|_ItemStepper" backend/src/entropia/domain/backtest/engine.py

OKUMA SIRASI (otorite sırasıyla):
  1. docs/ADIM16_LANDED_KICKOFF.md                          ← bu belge (PR A: stepper)
  2. docs/ADIM18_LANDED_KICKOFF.md §6                       ← (a)/(b) ayrımı; (a) BİTTİ
  3. docs/adr/0002-unified-clock-portfolio-simulation.md    ← Accepted; §3.2, §12 notu, §15 R-4
  4. backend/src/entropia/domain/backtest/portfolio_engine.py  ← §"HONEST BOUNDARY" ÖNCE oku
  5. docs/STAGE2_HANDOFF.md — en alttaki "## Next:" bloğu

DURUM: run_portfolio VAR, stepper VAR, ama ikisi birbirine BAĞLI DEĞİL. jobs/backtest_engine.py:298
  hâlâ item döngüsü, :363 combine_item_runs. SHARED_ALLOCATION_STATUS = future_dev. ADR Accepted.
  25 portföy oracle'ı run_portfolio üzerinde değişmeden yeşil. 46/46 golden digest yerinde.

GÖREV — TEK PR (PR B):
  1. ADAPTÖR: _ItemStepper üstüne portfolio_engine.ItemParticipant'ı uygula
     (identity / stream / instrument_id / carry / mandatory_exit / entry).
     entry kendi ItemIntent'ini form_intent ile kurar — boyut item'ın StrategyConfig'ini ister.
     open_position() dışında replay içine UZANMA (ADR §5).
  2. CALL SITE: jobs/backtest_engine.py:298 item döngüsünü run_portfolio ile değiştir —
     YALNIZ >1 item çalışırken; tek item run_engine'de kalır (ADR §3.2).
  3. DIGEST: 9 portfolio.* digest'i KIMILDAR, her biri tek tek gerekçelendirilir.
     37 non-portfolio digest KIMILDAMAZ — bu PR'ın kabul kriteri odur.

YAPMA:
  - ENGINE_VERSION'a DOKUNMA (ADIM 20).  Containment'ı KALDIRMA (future_dev kalır).
  - Manifest policy alanı EKLEME (ADIM 20).  NET'i desteklenir yapma (#544).
  - Oracle'ların beklenen literallerini değiştirme; ikinci bir motor yazma.
  - run_engine'in imzasını/semantiğini değiştirme; tek-item yolu byte-identical kalır.

DOĞRULAMA:
  cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy src
  TEST_DATABASE_URL=postgresql+asyncpg://entropia:entropia@localhost:5432/<worktree_db> \
    uv run pytest -q > /tmp/full.log 2>&1; echo $?   # tek çağrı, exit code AYRI oku
  Alt küme koşarken --no-cov ekle. Suite koşarken uv sync/uv run çalıştırma.

KAPANIŞ: CLAUDE.md §"Session CLOSING ritual" — 6 madde, istisnasız.
```
