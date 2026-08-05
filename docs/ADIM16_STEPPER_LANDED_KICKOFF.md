# ADIM 16 (ADR §12) landed — sıradaki: PR B, engine-destekli `ItemParticipant`

> **Durum:** `run_engine`'in bar döngüsü resumable bir stepper'a çıkarıldı (PR #602, merged,
> `c5d4c5d`). Saf refactor: imza, docstring ve semantik değişmedi, **46 golden digest
> kımıldamadı**, `engine_golden_digests.json` dosyasına dokunulmadı. Containment **kapalı**.

---

## Nerede duruyoruz

ADR 0002 §12'nin **ADIM 16**'sı (resumable stepper) atlanmıştı; ADIM 18 faz döngüsünü
(`run_portfolio`) öbür taraftan indirdi ama **üretimde çağıranı yoktu** ve olamazdı — bir
`ItemParticipant`'ın tek item'ı verilen bir `t`'ye ilerletmesi gerekiyordu, `engine.py`'de
bunu yapabilecek hiçbir şey yoktu. #602 o eksik parçayı koydu.

**Hâlâ doğru olan dürüst sınır:** `jobs/backtest_engine.py:298` hâlâ item döngüsü, `:363` hâlâ
`combine_item_runs`. `SHARED_ALLOCATION_STATUS = future_dev`. `run_portfolio`'nun üretimde
çağıranı **yok** ve bu varsayılmıyor, **iddia ediliyor**:
`tests/unit/oracles/test_oracle_portfolio_containment_gate.py::test_the_phase_loop_exists_but_no_production_path_reaches_it`.

---

## #602'nin bıraktığı reuse anchor'ları — tam sembol adlarıyla

| ne | nerede |
|---|---|
| askıya alınabilir replay kaydı | `domain/backtest/engine.py::_ItemStepper` (`:755`) |
| fabrika (kurulum + kapanışlar) | `engine.py::_build_stepper` (`:779`) |
| bar başına ilerletme | `_ItemStepper.step(bar)` — **çağıran normalize eder**: `engine.py::_normalize` |
| veri sonu uzlaştırma | `_ItemStepper.finalize()` — son `step`'ten sonra **bir kez** |
| çıktı projeksiyonu | `_ItemStepper.output()` → `EngineOutput`, hiçbir şeyi yeniden oynatmaz |
| tutulan pozisyon (P1 carry / P3 mandatory için) | `_ItemStepper.open_position()` → `_Position \| None` |
| canlı defter + pinli koşu ayarları | `_ItemStepper.ledger` (`_Ledger`), `_ItemStepper.ctx` (`_RunConfig`) |
| ince sürücü (referans kullanım) | `engine.py::run_engine` (`:3174`) — dokuz satır |
| bar sınırını aşan on ad | `engine.py:1761-1763` (`nonlocal` bloğu) |
| stepper sözleşmesinin testi | `tests/unit/test_backtest_engine_stepper.py` (10 test) |
| kabul kanıtı | `tests/unit/test_backtest_engine_golden.py` + `engine_golden_digests.json` (46 digest) |

**Faz döngüsü tarafındaki anchor'lar (ADIM 18'den, değişmedi):**
`portfolio_engine.py::run_portfolio` · `ItemParticipant` (Protocol) · `CarryCharges` ·
`MandatoryExit` · `PortfolioTick` / `PortfolioRun` · `PHASE_ORDER` / `PORTFOLIO_LOOP_VERSION` ·
referans katılımcı `tests/unit/oracles/portfolio_harness.py::_ScriptedParticipant`.

---

## Sıradaki iş — PR B (engine-destekli `ItemParticipant` + worker call site)

1. `_ItemStepper`'ı `ItemParticipant` protokolüne bağlayan bir adaptör yaz:
   `carry` → `CarryCharges` (P1), `mandatory_exit` → `MandatoryExit` (P3),
   `entry` → `ItemIntent` (P4). Pozisyonu `open_position()`'dan oku — replay'in içine uzanma.
2. `jobs/backtest_engine.py:298`'deki item döngüsünü `run_portfolio` ile değiştir
   **yalnız `>1` item çalışırken**; tek item `run_engine`'de kalır (ADR §3.2).
3. Containment guard'ı ancak o zaman ve **bilerek** güncellenir.

**Faz döngüsünün MODELLEMEDİĞİ (fail-closed, `portfolio_engine.py` docstring'inde yazılı):**
P0 (clock cursor'ı), **P2 pending fills**, **P8 same-direction scaling** — admitted bir
`scale_in` `UnsupportedIntentKindError` atar. Mark policy yok (**OD-2 açık**): `E(t)`
realized-only. Adaptör bunları **kapatmaz**; kapatmak ayrı slice'tır.

**Sonra ADIM 20** (manifest policy alanları, `ENGINE_VERSION` bump, digest yenileme,
containment lift). Ön koşulları değişmedi — `docs/STAGE2_HANDOFF.md` §Next ve
`docs/ADIM20_BLOCKED_KICKOFF.md`: A17'nin 4 `xfail(strict)`'i (#556 ×2, #557, #558),
OD-1/OD-2/OD-6 kapılarının kod olarak yokluğu, #544 (NET), #559 (DST).

---

## Yöntem — bu slice'ta işe yarayan

- **Tek kanıt digest'tir.** Geçen bir suite tek başına kanıt değil; refactor'ün kabulü
  `engine_golden_digests.json`'ın **hem yeşil hem değişmemiş** olmasıdır. Alt küme koşarken
  `--no-cov` ekle.
- **`nonlocal` listesini tahmin etme, ölç.** AST ile bar sınırını aşan adları çıkar, kalanları
  definite-assignment ile ele. Fazladan bir `nonlocal` sessizce bir kararı bara bağlar.
- **Taşınan aralıkları diff'le doğrula**, "aynı görünüyor" ile değil.
- **restructure ≠ re-price.** ADR §15 R-4. Adaptör ve call site aynı PR'a girmez.

---

## Paste-ready resume prompt

```
ENTROPIA — sıradaki slice: PR B (engine-destekli ItemParticipant + worker call site)

ÖNCE DOĞRULA (handoff STALE-BY-DEFAULT — özete güvenme):
  git fetch --all --prune && git log --oneline origin/main -6
  gh issue view 582        # ADIM 20 blocked — hâlâ açık olmalı
  grep -n "for prepared in prepared_items" backend/src/entropia/application/jobs/backtest_engine.py
  grep -n "combine_item_runs" backend/src/entropia/application/jobs/backtest_engine.py

OKUMA SIRASI:
  1. docs/ADIM16_STEPPER_LANDED_KICKOFF.md                ← bu slice'ın handoff'u
  2. docs/adr/0002-unified-clock-portfolio-simulation.md  ← §3.2, §5 (ItemParticipant), §8 (faz
     sırası), §12 (numaralandırma + ADIM 16 şerhi), §15 R-4
  3. backend/src/entropia/domain/backtest/engine.py:755   ← _ItemStepper + _build_stepper
  4. backend/src/entropia/domain/backtest/portfolio_engine.py ← ItemParticipant, run_portfolio
  5. docs/PROJECT_HISTORY.md §"ADIM 16 (ADR §12)" ve §"ADIM 18"

DURUM: stepper indi (#602, c5d4c5d). run_engine dokuz satırlık bir sürücü; _ItemStepper
  step/finalize/output/open_position + ledger + ctx veriyor. 46 golden digest kımıldamadı.
  DÜRÜST SINIR: run_portfolio'nun üretimde HÂLÂ çağıranı yok; containment kapalı.

GÖREV:
  (1) _ItemStepper üzerinde ItemParticipant adaptörü (carry/mandatory_exit/entry).
  (2) jobs/backtest_engine.py:298 item döngüsünü run_portfolio ile değiştir — YALNIZ >1 item;
      tek item run_engine'de kalır (ADR §3.2).
  (3) Containment guard'ı ancak burada, bilerek güncelle.

KANIT:
  - 46 golden digest KIMILDAMAMALI (tek-item yol byte-identical kalır) ve
    backend/tests/unit/engine_golden_digests.json DEĞİŞMEMELİ.
  - 25 portföy oracle'ı + stepper testi (10) yeşil.
  - >1 item için gerçek engine ile bir uçtan uca kanıt — scripted katılımcı yeterli değil.

YAPMA:
  - ENGINE_VERSION'a DOKUNMA (ADIM 20'nin işi). Manifest policy alanları da ADIM 20.
  - P2 pending fills / P8 same-direction scaling / OD-2 mark policy'yi bu PR'da AÇMA.

DOĞRULAMA:
  cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy src
  TEST_DATABASE_URL=postgresql+asyncpg://entropia:entropia@localhost:5432/entropia_wt_<slug> \
    uv run pytest -q > /tmp/full.log 2>&1; echo $?     # tek çağrı, exit code AYRI oku
  Alt küme koşarken --no-cov EKLE. Suite koşarken uv sync ÇALIŞTIRMA. `| tail` KULLANMA.

BRANCH: feat/adim-16b-item-participant   COMMIT: feat(engine): <subject>   (AI attribution YOK)
KAPANIŞ: CLAUDE.md §"Session CLOSING ritual" — 6 madde, istisnasız.
```
