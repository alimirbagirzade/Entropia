<!-- doc-status: historical -->
> **HISTORICAL RECORD — bu belge GÜNCEL GERÇEK DEĞİLDİR.** Yazıldığı andaki durumu
> kaydeder; SHA'lar, sayılar, alembic head'i ve "next" maddeleri bayat olabilir.
> Güncel otorite: `CLAUDE.md` §Current position + `docs/generated/repository_facts.md`
> (üretilmiş, CI'da `--check` ile kapılı).

# ADIM 15 landed — merged-axis valuation clock (PR #567) · ADIM 16 kickoff

> Bu belge **ADIM 15'in** kapanış handoff'udur. En altta **paste-ready resume prompt** var.

| ne | değer |
|---|---|
| ADIM 15 | merge **`ef11dc9`** (2026-08-04T20:06:44Z) · branch `feat/portfolio-unified-clock-core` · **+864 / −1, 3 dosya** · CI **6/6 SUCCESS** |
| `origin/main` HEAD | **`0f44c3a`** (PR #568, F-26 etiket düzeltmesi — ADIM 15'ten sonra indi) |
| Alembic head | `0043_i08_registry_strategy_fks` (tek head) — **migration YOK** |
| `ENGINE_VERSION` | `backtest-engine-v18-gap-adjusted-stop-fill` — **ADIM 15 değiştirmedi** |
| OpenAPI | **değişmedi** · frontend **dokunulmadı** |

Tam kayıt: `docs/PROJECT_HISTORY.md` §ADIM 15 · handoff: `docs/STAGE2_HANDOFF.md` ·
tasarım: `docs/adr/0002-unified-clock-portfolio-simulation.md`.

---

## ⚠ ÖNCE OKU — ADR kapısı kayıtsız geçildi

**ADR 0002'nin statüsü hâlâ `Proposed`** (satır 4: *"requires PO / maintainer approval before
any implementation slice starts"*) ve **§16 onay gelmeden ADIM 15'in başlamamasını şart
koşuyordu.** PR #567 kayıtlı bir onay olmadan indi.

Zarar dar: modül **saf**, hiçbir yerden import edilmiyor, rollback tek dosya silme. Ama kapı
atlanmıştır. **ADIM 16'ya başlamadan önce onay durumunu açıkça sor** — §13'ün yedi açık kararı
(OD-1…OD-7) hâlâ çözülmedi ve ADIM 16 saf refactor olsa bile aynı programın parçası.

---

## ADIM 15 ne bıraktı — reuse anchor'ları (kesin sembol adları)

Modül: **`backend/src/entropia/domain/backtest/execution/clock.py`** (300 satır).

| sembol | ne |
|---|---|
| `ItemBarStream(item_id, pin_ordinal, batches)` | bir öğenin pinli bar kaynağı; `batches` worker'ın **bugün zaten tuttuğu** chunked iterator (`stream_bars` / `iter_bar_batches`) doğrudan geçiyor |
| `ItemTickView` | `bars` (tuple) · `last_closed` · `last_closed_t_ms` · `is_decision` · `staleness_ms` |
| `ClockTick` | `t_ms` · `views` · `deciding` · `view_for(item_id)` |
| `iter_ticks(streams)` | **eksenin kendisi** — streaming k-way heap merge, öğe başına ≤1 bar tutar |
| `tick_key(timestamp) -> int \| None` | UTC epoch ms anahtarı; sevk edilen epoch helper'larıyla uyuştuğu testle pinli |
| `timeline_identity(t_ms_values, *, policy_version=...)` | eksen digest'i; kendi sha256 namespace'i var |
| `CLOCK_POLICY_VERSION = "clock-policy-v1"` | ADR §10.3 bunu MANIFEST alanı sayıyor — **manifest'e yazmak ADIM 20'nin** |
| `ClockAxisError(ValueError)` | ← `UnplaceableBarTimestampError` · `NonMonotonicBarStreamError` · `DuplicateItemStreamError` |

Bağımlılıkları: `execution.state._Bar` / `_normalize` ve `funding.parse_utc` — **yeni bağımlılık
eklemedi**, motorun kullandığı coercion'ın aynısını kullanıyor.

Testler: **`backend/tests/unit/test_backtest_unified_clock.py`** (563 satır / **27 test**).
İki tanesi **izolasyon bekçisidir** ve ADIM 16'da **kırılmamalı**:
`test_the_clock_is_not_wired_into_production_yet` ·
`test_no_clock_field_ships_in_the_manifest_yet_and_the_engine_version_stands`.
ADIM 16 clock'u engine'e **bağlamaz** — bu iki test yeşil kalmalı.

---

## ADIM 16 — resumable per-item stepper (SAF refactor)

ADR §12'nin ADIM 16 satırı:

> `run_engine`'in bar-döngü gövdesini, bir öğeyi verilen bir `t`'ye ilerletebilen bir
> **stepper**'a çıkar; `run_engine` **imzasını VE semantiğini** koruyup o stepper üzerinde ince
> bir sürücüye dönüşsün (§3.2). **Pure refactor.**

* **Dosyalar:** `domain/backtest/engine.py`, `execution/state.py`.
* **Kabul ölçütü:** **46 golden digest'in TAMAMI değişmemeli** — hepsi
  `run_engine` / `combine_item_runs`'ı **doğrudan** çağırıyor, worker'ı asla; bu yüzden digest'ler
  refactor'ün gerçekten saf olduğunun kanıtıdır. Ayrıca **tam engine suite yeşil**.
* **Rollback:** revert; hiçbir anlamsal yüzey değişmedi.

**ADIM 15'in bıraktığı bağlantı:** `iter_ticks` bir öğenin **hangi `t`'lerde** ilerletilmesi
gerektiğini zaten söylüyor; ADIM 16'nın işi o `t`'ye **ilerletebilen** bir motor gövdesi üretmek.
İkisi **ADIM 18'de** birleşir (`run_portfolio`) — **ADIM 16'da clock'u engine'e BAĞLAMA.**

**Sonraki sınırlar (ADR §12, dokunma):** ADIM 17 ledger + snapshot · ADIM 18 `ItemIntent` + faz
döngüsü · ADIM 19 conflict/sleeve arbitrasyonu · ADIM 20 manifest + `ENGINE_VERSION` bump +
**containment lift** (yalnız ADIM 20 containment'ı kaldırır).

---

## İki kalem — ADIM 16 bunları bilerek devralmalı

### 1. Mutation testi: bir mutasyon ilk turda hayatta kaldı

ADIM 15'in testleri mutasyonla sınandı — **altı mutasyon, altısı da yakalanıyor**: cursor'ın
mükerrer bardan ilkini (sonuncusu yerine) izlemesi · barsız view'ların düşürülmesi · **merge'ün
`t_ms` yerine ham timestamp string'iyle anahtarlanması** · geriye-giden-akış guard'ının
kaldırılması · `(pin_ordinal, item_id)` sıralamasının kaldırılması · mükerrer `item_id`
guard'ının kaldırılması.

**String-key mutasyonu ilk turda hayatta kaldı.** Offset fixture'ı iki kaydı tesadüfen bitişik
bırakıyordu, `groupby` yanlış anahtarla bile doğru gruplamıştı — testlerin o anki "geçmesi" eksen
sözleşmesinin kanıtı değildi. Kapatan test sonradan yazıldı:
`test_a_mixed_offset_axis_orders_by_instant_and_not_by_text`.

**Yöntemsel kayıt:** geçen bir suite tek başına kanıt değildir. ADIM 16'da kapı zaten 46 golden
digest'in sabitliği; ama **ADIM 17–19'un yeni davranış getiren testleri mutasyonla sınanmalı**,
yoksa aynı sessiz boşluk tekrarlanır.

### 2. Naive timestamp ayrışması (K-01) — ADIM 16/18 bununla karşılaşacak

`tick_key` → `parse_utc(timestamp, source_zone=None)` **offset'siz** bir timestamp'ı çözümsüz
sayar ve clock onu `UnplaceableBarTimestampError` ile **reddeder** (fail-closed, doğru davranış).
Ama `domain/backtest/indicators.py::_epoch_seconds` **aynı değeri sessizce UTC kabul eder.**

`test_tick_key_agrees_with_the_shipped_epoch_helpers` clock'un iki *sevk edilmiş* wrapper'la
(`engine._epoch_ms_or_none`, `execution.rules.bar_epoch_ms`) uyuştuğunu kilitliyor;
`indicators._epoch_seconds` o üçlünün **dışında**. Üretim barları ingest'te UTC-normalize edildiği
için bugün tetiklenmesi beklenmiyor, ama **stepper (ADIM 16) ve `run_portfolio` (ADIM 18) aynı bar
akışını hem eksene hem indikatör hesabına verdiğinde iki yorum aynı satırda buluşur.**
Clock'un davranışı doğru olan; ayrışma `indicators` tarafında ele alınmalı. Bu bir ADIM 15 kusuru
değil, **devredilen bir kalemdir.**

## Çalışma döngüsü (ADIM 15'te işe yarayan)

1. **Önce kusuru üret**, sonra düzelt/ekle — ADIM 15'te bu, katlanan eğrinin zaman serisi
   olmadığını gösteren mevcut pinli testti.
2. **İddiayı testle kilitle, sözle değil** — "hiçbir yerden import edilmiyor" bir yorum değil,
   `test_the_clock_is_not_wired_into_production_yet`.
3. **Fail closed** — bir girdi yerleştirilemiyorsa raise et; "atla" asla bir seçenek değil.
4. **Kanonun vermediği kuralı icat etme** — mükerrer instant katlanmadı çünkü merge kuralı yok;
   OD-2 seçilmedi çünkü ürün kararı.

---

## Paste-ready resume prompt

```
ENTROPIA — ADIM 16: resumable per-item stepper (ADR 0002 §12, SAF refactor)

Session START protokolü: git fetch --all --prune ; git status --short (kirliyse DUR) ;
git log --oneline origin/main -5 ile HEAD'i doğrula (ADIM 15 = merge ef11dc9).
Sonra docs/ADIM15_LANDED_KICKOFF.md + ADR §12 (ADIM 16 satırı) + §3.2'yi oku.

ÖNCE SOR — KOD YAZMADAN: ADR 0002'nin statüsü hâlâ `Proposed` mı? §16 onay olmadan
implementation slice başlatmıyor. ADIM 15 bu kapıdan KAYITSIZ geçti; ADIM 16'yı da
öyle geçirme. Onay durumu netleşmeden tek satır yazma.

Branch: feat/stage-16-resumable-stepper
Commit: feat(portfolio): extract a resumable per-item stepper from run_engine
(AI attribution YOK)

İŞ: run_engine'in bar-döngü gövdesini, bir öğeyi verilen bir t'ye ilerletebilen bir
stepper'a çıkar. run_engine İMZASINI VE SEMANTİĞİNİ korur, o stepper üzerinde ince
bir sürücü olur. SAF REFACTOR — davranış değişikliği YOK.
Dosyalar: domain/backtest/engine.py, execution/state.py.

KABUL: 46 golden digest'in TAMAMI değişmemeli (hepsi run_engine/combine_item_runs'ı
doğrudan çağırıyor) + tam engine suite yeşil. Digest oynadıysa refactor saf değildir —
digest'i YENİDEN KAYDETME, refactor'ü düzelt.

DOKUNMA: clock.py'yi engine'e BAĞLAMA (o ADIM 18). ENGINE_VERSION, manifest alanları,
containment (SHARED_ALLOCATION_STATUS), OpenAPI, frontend, migration — hiçbiri.
İzolasyon bekçileri yeşil kalmalı: test_the_clock_is_not_wired_into_production_yet ve
test_no_clock_field_ships_in_the_manifest_yet_and_the_engine_version_stands.

Doğrulama: cd backend && uv run ruff check . && uv run ruff format --check . &&
uv run mypy src && uv run pytest -q  (TEK çağrı, ortada öldürme, | tail KULLANMA;
TEST_DATABASE_URL ile worktree'ye özel izole DB, sürücü postgresql+asyncpg://).

PR aç ve DUR — merge etme, merge kullanıcıdan istenir.
```
