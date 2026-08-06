<!-- doc-status: historical -->
> **HISTORICAL RECORD — bu belge GÜNCEL GERÇEK DEĞİLDİR.** Yazıldığı andaki durumu
> kaydeder; SHA'lar, sayılar, alembic head'i ve "next" maddeleri bayat olabilir.
> Güncel otorite: `CLAUDE.md` §Current position + `docs/generated/repository_facts.md`
> (üretilmiş, CI'da `--check` ile kapılı).

# ADIM 18 LANDED — `run_portfolio` faz döngüsü, çağıransız · sıradaki slice kickoff'u

> Bu belge **ADIM 18'in** kapanış handoff'udur. En altta **paste-ready resume prompt** var.
> Otorite sırası: bu belge → `docs/adr/0002-unified-clock-portfolio-simulation.md`
> (**artık `Accepted`**; §12 düzeltme notu, §13.1 amendment, §16 discharged) →
> `docs/audit/unified_portfolio_oracle_acceptance.md` (§0 ADDENDUM) →
> `docs/STAGE2_HANDOFF.md` → `docs/spec/13_*`.

> **Ad çakışması, bilerek korundu.** PR #575 de "ADIM 18" etiketiyle indi (cross-item
> arbitration). Bu slice ADR §12'nin **18. satırının faz-döngüsü yarısıdır**. Sevk edilen
> numaralandırma ile ADR'ninki arasındaki tam eşleme tablosu ADR §12'nin düzeltme notundadır.

---

## 1. Nerede duruyoruz (empirik, 2026-08-05)

| Olgu | Değer |
|---|---|
| Base | `origin/main` @ `d7fe432` (PR #584) |
| Branch | `feat/stage-18-run-portfolio` |
| Alembic head | `0043_i08_registry_strategy_fks` — tek head, **migration eklenmedi** |
| `ENGINE_VERSION` | `backtest-engine-v18-gap-adjusted-stop-fill` — **bump EDİLMEDİ** (ADIM 20'nin) |
| OpenAPI / frontend | değişmedi |
| `SHARED_ALLOCATION_STATUS` | **`future_dev`** — containment kaldırılmadı |
| ADR 0002 | **`Accepted`** (2026-08-05) |
| Blocking issue | **#582** hâlâ AÇIK |

**Düzeltme — önceki kickoff yanlıştı:** `docs/ADIM20_BLOCKED_KICKOFF.md` PR #583'ü
"DRAFT/BLOCKED, merge edilmemeli" diye kaydetmişti; **#583 ve #584 merge EDİLDİ**.

---

## 2. ADIM 18 ne yaptı — tek cümlede

ADR §8.2 faz döngüsünü üretime taşıdı (`run_portfolio`) ve 25 portföy oracle'ını test-owned
sürücüden ona **değişmeden** aktardı — **ama worker'ı bağlamadı**, çünkü bağlamak için gereken
şey (bir item'ı verilen `t`'ye ilerletebilen replay) hâlâ yok.

## 3. ADIM 0 — insan kapısı, atlanmadı

Kod yazılmadan soruldu ve iki karar alındı:

1. **ADR onaylandı** → statü `Accepted`, §13'ün yedi açık kararı **§13.1 amendment tablosuna**
   çözüm olarak yazıldı (**hepsi kendi tavsiyesine**: OD-1(a) … OD-7(a)).
2. **§12 sevk edilene göre düzeltildi** → ADR'nin **ADIM 16**'sı (resumable stepper) formally
   **SKIPPED**, sevk-edilen↔ADR numaralandırma haritası eklendi.

§16 "discharged" olarak yeniden yazıldı ve onayın **ADIM 15–19'dan SONRA** geldiğini kayda
geçiriyor. **§13.1'in bilinçli boşluğu:** OD-2/OD-3 kodda hâlâ `pending` etiketli
(`MARK_STALENESS_POLICY`, `CONTENTION_SELECTION_STATUS`) — ikisi de yalnız
`build_portfolio_manifest` üzerinden yayımlanır ve o fonksiyonu hiçbir şey çağırmaz; **iki flip
de ADIM 20'nin** (R-5 ile birlikte).

---

## 4. REUSE ANCHORS — tam sembol adlarıyla

### 4.1 Faz döngüsü — `backend/src/entropia/domain/backtest/portfolio_engine.py` (549 satır)

| Sembol | Rolü |
|---|---|
| `run_portfolio(participants, *, pool_initial, shares, reserve_percent, compound, conflict_policy, max_position_notional, max_total_exposure_notional)` | giriş noktası; dış döngü **merged eksen** (`iter_ticks`), item listesi DEĞİL |
| `ItemParticipant` (Protocol) | `identity`, `stream`, `instrument_id`, `carry`, `mandatory_exit`, `entry` |
| `CarryCharges(funding, fee, other_cost)` | P1 girdisi — **item bildirir**, döngü türetmez |
| `MandatoryExit(decision, sizing, gross_pnl, commission)` | P3 girdisi |
| `PortfolioTick` | `t_ms, timestamp, views, snapshot, mandatory, intents, report, equity_point` |
| `PortfolioRun` | `ledger, ticks` + `dated_points`, `instants`, `max_drawdown`, `tick_at(ts)` |
| `PHASE_ORDER`, `PORTFOLIO_LOOP_VERSION` | faz sözleşmesi **değer olarak** |
| `_phase_1_carry` / `_phase_3_mandatory` / `_phase_4_intents` / `_phase_7_apply` / `_run_tick` | fazlar, girdileri imzada görünür |
| `InvalidParticipantError` · `MisformedIntentError` · `UnsupportedIntentKindError` · `UnpriceableAdmissionError` | fail-closed reddedişler |

### 4.2 Referans katılımcı (scripted)

`backend/tests/unit/oracles/portfolio_harness.py::_ScriptedParticipant` — sözleşmenin çalışan
tek uygulaması. `simulate(...)` artık **ince bir adaptör**; `_run_tick`/`TickRecord`/`PortfolioRun`
oradan **silindi** (üretime taşındı).

### 4.3 Containment'ın kalan tek kapısı

`tests/unit/oracles/test_oracle_portfolio_containment_gate.py::test_the_phase_loop_exists_but_no_production_path_reaches_it`
— (1) `def run_portfolio` var, (2) onu tanımlayan **tek** üretim modülü var, (3) altı unified-clock
modülü `execution/` dışında **yalnız** faz döngüsünden import ediliyor, (4) **`run_portfolio`'nun
üretimde hiç çağıranı yok**, (5) worker hâlâ `combine_item_runs` + `for prepared in prepared_items:`.

---

## 5. DÜRÜST SINIR — bunu atlama

`run_portfolio`'nun **üretimde çağıranı yok.** Bu, ADIM 15–19'un "kopuk ada" probleminin bir
seviye yukarısıdır ve **kabul edilerek** yapıldı; alternatif ya engine'i faz döngüsünün içinde
yeniden yazmak (bir ikinci engine — `intents.py` docstring'inin açıkça yasakladığı şey) ya da
25 oracle'ın beklenen literallerini değiştirmek olurdu.

Ayrıca **modellenmeyenler** (`portfolio_engine.py` docstring'inde de yazılı): P0 (clock
cursor'ı), **P2 pending fills**, **P8 same-direction scaling** — admitted bir `scale_in` bilerek
`UnsupportedIntentKindError` atar. Mark policy yok (**OD-2**): `E(t)` realized-only.

Ve: **karar hâlâ fixture-owned.** `ScriptedItem` ne istediğini/kapattığını/ödediğini veri olarak
bildirir; gerçek item bunları kendi indicator evaluator'ından, stop resolver'ından ve pinlenmiş
funding takviminden türetir. Bu, katılımcı sözleşmesinin **tasarlandığı gibi** çalışmasıdır ama
oracle'lar **döngüyü ve primitifleri** kanıtlar, herhangi bir item'ın sinyal mantığını değil.

---

## 6. Sıradaki tek adım — ADIM 20 DEĞİL

**1. Engine-destekli `ItemParticipant` — İKİ AYRI PR:**

- **(a) Stepper.** `run_engine`'in bar döngüsünü (`engine.py:1782`, ~1100 satırlık fonksiyonun
  içinde nested) bir stepper'a çıkar; `run_engine` onun üzerinde ince bir sürücü olur ve
  **gözlemlenebilir biçimde değişmez**. **Tek kanıt: 46 golden digest kımıldamaz.**
- **(b) Adaptör + worker.** Stepper'ın üstüne `portfolio_engine.ItemParticipant`'ı uygulayan bir
  adaptör yaz; `jobs/backtest_engine.py:298`'deki item döngüsünü `run_portfolio` ile değiştir —
  **yalnız >1 item çalışırken**; tek item `run_engine`'de kalır (ADR §3.2).

**İkisini tek PR'da yapma.** ADR §15 R-4'ün "restructure ile re-price'ı ayır" kuralı zaten bir
kez kaybedildi (ADIM 16 atlandığında); ikinci kez kaybedilirse kımıldayan bir digest'i
atfedecek hiçbir şey kalmaz.

**2. Sonra ADIM 20** (manifest policy alanları, `ENGINE_VERSION` bump, digest yenileme,
containment lift, Result portfolio metadata + OpenAPI, codemaps). Hâlâ açık ön koşullar:

- **A17** — `tests/integration/test_research_point_in_time_parity.py`'de 4 `xfail(strict)`
  (#556 ×2, #557, #558). "green, unweakened" değil.
- **OD-1 / OD-2 / OD-6 blocker'ları KOD OLARAK YOK** (ADR §13.1 kararı kaydetti, kapıyı yazmadı).
- İki policy etiketi flip'i: `MARK_STALENESS_POLICY`, `CONTENTION_SELECTION_STATUS`.
- **#544 (NET)** · **#559 (DST)**.
- **A4 / A18** gerçek `EngineOutput` digest'i ister → 1(b)'ye bağlı. **A21** tick tabanlı cancel
  checkpoint → 1(b)'ye bağlı.

---

## 7. Çalışma döngüsü (bu slice'ta işleyen yöntem)

1. **İnsan kapısını gerçekten sor.** ADR onayı ve §12 düzeltmesi kod yazılmadan soruldu; iki
   cevap da tasarımı değiştirdi (ADIM 16'yı yazmak yerine SKIPPED işaretlemek).
2. **Sözleşmeyi primitiflerin kendi kurallarından türet.** P4'ün hazır `ItemIntent` alması bir
   kolaylık değil: `form_intent` entry'yi item'ın `StrategyConfig`'i olmadan ölçemez, ve
   oracle'ların literal unit sayılarını değiştirmek yasaktı. Kısıtlar tasarımı verdi.
3. **İkameyi erken koş.** `simulate` → `run_portfolio` ilk denemede **24/25** yeşil geldi; tek
   kırmızı zaten yeniden yazılacak kapıydı. Bu, tasarımın doğru olduğunun ilk sinyaliydi.
4. **Guard'ları yeniden ADLANDIR, gevşetme.** "nothing in production imports" artık yanlış
   olacaktı; assertion'lar korundu, adlar düzeltildi, importer'lar **adlandırıldı**.
5. **Lokal doğrulama:** `cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy src`
   + tam suite **tek çağrıda**, çıktı **dosyaya**, `$?` **ayrı**.
   `TEST_DATABASE_URL` ile worktree'ye özel izole DB (**`postgresql+asyncpg://`**).
   Alt küme koşarken `--no-cov` ekle. **`uv sync` lock'u kirletebilir** — `git status` ile bak.
6. **GateGuard:** YENİ dosya → Bash heredoc (gate-free). Mevcut dosyaya EDIT/WRITE → 4 olgu sun.
   Bu slice mevcut dosyaları `python3` in-place ile düzenledi (Bash, kapı geçildikten sonra serbest).

---

## 8. Paste-ready resume prompt

```text
ENTROPIA — sıradaki slice: engine-destekli ItemParticipant (a: stepper, b: worker)

ÖNCE DOĞRULA (handoff STALE-BY-DEFAULT — özete güvenme):
  git fetch --all --prune && git log --oneline origin/main -6 && gh pr list --state all --limit 8
  gh issue view 582
  grep -rn "run_portfolio(" backend/src   # ÇAĞIRAN VAR MI? yoksa aşağısı geçerli

OKUMA SIRASI (otorite sırasıyla):
  1. docs/ADIM18_LANDED_KICKOFF.md                         ← bu belge
  2. docs/adr/0002-unified-clock-portfolio-simulation.md   ← Accepted; §12 düzeltme notu, §13.1, §16
  3. docs/audit/unified_portfolio_oracle_acceptance.md     ← §0 ADDENDUM + A1–A22
  4. backend/src/entropia/domain/backtest/portfolio_engine.py  ← §"HONEST BOUNDARY" ÖNCE oku
  5. docs/STAGE2_HANDOFF.md — en alttaki "## Next:" bloğu

DURUM: run_portfolio VAR ama üretimde ÇAĞIRANI YOK. jobs/backtest_engine.py:298 hâlâ item
  döngüsü, :363 combine_item_runs. SHARED_ALLOCATION_STATUS = future_dev. ADR Accepted.
  25 portföy oracle'ı run_portfolio üzerinde değişmeden yeşil → A1/A3/A5 MET.

GÖREV — İKİ AYRI PR, SIRAYLA (tek PR'da BİRLEŞTİRME):
  (a) STEPPER: run_engine'in bar döngüsünü (engine.py:1782, ~1100 satırlık fonksiyonun içinde)
      bir stepper'a çıkar. run_engine onun üzerinde ince sürücü olur, imzası VE semantiği
      değişmez. TEK KANIT: 46 golden digest kımıldamaz (engine_golden_digests.json).
      Saf refactor — başka hiçbir assertion'a güvenme (ADR §15 R-4).
  (b) ADAPTÖR + WORKER: stepper üstüne portfolio_engine.ItemParticipant'ı uygula
      (carry / mandatory_exit / entry — entry kendi ItemIntent'ini form_intent ile kurar,
      çünkü boyut item'ın StrategyConfig'ini ister). jobs/backtest_engine.py:298 item
      döngüsünü run_portfolio ile değiştir — YALNIZ >1 item çalışırken; tek item run_engine'de
      kalır (ADR §3.2). Bu PR'da 9 portfolio.* digest'inin kımıldaması BEKLENİR; her biri
      tek tek gerekçelendirilir. 37 non-portfolio digest KIMILDAMAMALI.

YAPMA:
  - (a) ile (b)'yi tek PR'da birleştirme — restructure/re-price ayrımı bir kez kaybedildi.
  - ENGINE_VERSION'a DOKUNMA (ADIM 20).  Containment'ı KALDIRMA (future_dev kalır).
  - Oracle'ların beklenen literallerini değiştirme; harness'a ikinci bir motor yazma.
  - NET'i desteklenir yapma (#544).  Manifest policy alanı EKLEME (ADIM 20).

DOĞRULAMA:
  cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy src
  TEST_DATABASE_URL=postgresql+asyncpg://entropia:entropia@localhost:5432/<worktree_db> \
    uv run pytest -q > /tmp/full.log 2>&1; echo $?   # tek çağrı, exit code AYRI oku
  Alt küme koşarken --no-cov ekle. Suite koşarken uv sync/uv run çalıştırma.
  `git status backend/uv.lock` — uv sync lock'u kirletebilir, alakasız değişikliği geri al.

KAPANIŞ: CLAUDE.md §"Session CLOSING ritual" — 6 madde, istisnasız.
```

---

*ADIM 18 kapanışı · 2026-08-05 · base `d7fe432` · alembic head `0043_i08_registry_strategy_fks` ·
`ENGINE_VERSION` değişmedi · containment KALDIRILMADI*
