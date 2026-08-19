<!-- doc-status: current -->
> **CURRENT SLICE KICKOFF.** Sayısal gerçekler için otorite:
> `CLAUDE.md` §Current position + `docs/generated/repository_facts.md` (üretilmiş).

# ADIM 89 LANDED — `C4` / E5: worker'ın paylaşımlı saat dalı · sıradaki slice için kickoff

> Ölçüm anı: **2026-08-19**, taban main **`ccdd4fd`** (ADIM 86 dahil). Bu belgedeki her sayı o
> commit'e karşı ölçülmüştür ve **present-tense okunmamalıdır** — `git fetch` ile yeniden ölç.

> **NUMARA: 87 ve 88 atlandı.** Bu slice ADIM 87 yazıldı; o numarayı **ve
> `docs/ADIM87_LANDED_KICKOFF.md` dosya yolunu** **PR #785** (doc 18 frontend, `cfce51e`) aldı.
> Ardından **#797 kendini 88'e taşıdı** ve aynı dosya yolunu orada talep etti (non-draft) → bu
> dal **89**'a taşındı — ve **#797 gerçekten 88'i aldı** (`ee5ab38`), yani boşluk kapandı ve
> zincir 86·87·88·89 kesintisiz. Ders: numara çakışması bu depoda **tekrar eden yapısal bir
> yarıştır** (bir günde ÜÇ kez); kapanış PR'ını açmadan ÖNCE ve merge'den HEMEN ÖNCE açık
> dalların **ekleyeceği DOSYA YOLLARINI** listele — başlığı değil. Taşınmanın bedeli birkaç
> dakikalık mekanik düzenlemedir; taşınmamanın bedeli add/add çakışması + çift başlıktır.
> (Kayıt önce #797'yi tahmin ediyordu — **ikisi de** aynı yolu ekliyordu; tahmin gereksizdi.)
> Çakışan şey başlık değil **dosya yoludur**. Bu dal rebase'te ADIM87 kickoff'unu
> **`historical`a demote etti** (numarayla aynı commit'te), yoksa iki `current` kalırdı.

## 0. Nerede duruyoruz

`SHARED_ALLOCATION_STATUS` = **`future_dev`** (DEĞİŞMEDİ) · `ENGINE_VERSION` **değişmedi** ·
alembic head `0043_i08_registry_strategy_fks` (bu dalgada migration yok) · OpenAPI **değişmedi**
· **50 golden digest bayt bayt aynı** · blocker **1** (yalnız A-08), verdict **BLOCKED**.

**PACKAGE C'nin serisel zinciri BİTTİ.** `C1` (#735) describe/book bölmesi, `C2` (#759)
`settle`/`finalize`/P10/`iter_portfolio`, `C3` (#777) `_EngineParticipant`, **`C4` (bu slice)
worker call site'ı**. Kritik yol artık **kodla değil iki İMZAYLA** devam ediyor.

## 1. Bu slice ne bıraktı (REUSE anchor'ları — tam sembol adlarıyla)

| Sembol | Yer | Ne işe yarar |
|---|---|---|
| `_use_unified_clock(capital_execution)` | `application/jobs/backtest_engine.py` | dalı seçen **TEK** yer. Yeni bir çağıran ekleme — bu fonksiyondan geçir |
| `_TICK_CHECKPOINT_STRIDE` | aynı modül | checkpoint #3b'nin K'sı; gerekçesi sabitin yanında. **Korrektlik düğmesi değil**, en kötü bedeli gecikme |
| `_SharedClockInputs` + `_shared_clock_inputs(...)` | aynı modül | **saf**; item başına `_build_stepper` + `_EngineParticipant`, `pin_ordinal` **manifest**'ten, `shares` plandan, `max_total_exposure_notional` motor prologunun dönüşümüyle |
| `_replay_shared_clock(...)` | aynı modül | `iter_portfolio`'yu **elle** tüketir (düz `for` dönüş değerini atar), #3b'yi koyar, `project_portfolio_run`'a bağlar; her refüzü `RUN_FAILED_ENGINE_ERROR`'a çevirir |
| `replay_progress` | `run_backtest` | checkpoint #4'ün ilerleme sözlüğü, **dal öncesinde** bağlanır. Paylaşımlı kolda `unified_clock: true`, #3b'de ayrıca `replayed_tick_count` |
| `build_engine_participant(...)` | `domain/backtest/participant.py` | worker'ın phase loop'un **sözlüğünü import etmeden** katılımcı kurmasını sağlar. **İmzalı importer allowlist'i bu yüzden değişmedi** |
| `_functions_calling(source, callee)` | `tests/unit/test_shared_allocation_two_world_gate.py` | `ast` tabanlı çağrı taraması. Bir dizenin **düzyazıda mı çağrıda mı** geçtiğini ayırman gerektiğinde bunu kopyala |
| `_AUTHORISED_LOOP_CALLERS` / `_AUTHORISED_PROJECTION_CALLERS` | `test_oracle_portfolio_containment_gate.py` | daraltılmış tripwire. Yeni bir çağıran **kırmızıdır** ve öyle kalmalı |
| `_lifted(monkeypatch)` | `tests/integration/test_shared_clock_worker_branch.py` **ve** `tests/unit/test_shared_clock_branch_predicate.py` | test-sahipli lift fixture'ı; `capability.SHARED_ALLOCATION_STATUS` modül global'ini yamar |
| `_shared_safe_payload` / `_composition` / `_enable_shared_pool` | `tests/integration/test_shared_clock_worker_branch.py` | adaptörün reddetmediği bir strateji + N-item'lı paylaşımlı plan kuran harness |

## 2. Pazarlıksız sınırlar (bunları gevşetme)

1. **`_use_unified_clock`'un iki conjunct'ı da taşıyıcıdır.** Simetrik değiller ve `A and B`
   kısa devre yapar — **bileşik cevabı değil TERİMLERİ ayrı pinle**
   (`test_shared_clock_branch_predicate.py` 2×2'si).
2. **Tripwire'ın iki dokunulmaz assertion'ı** (`combine_item_runs(`,
   `for prepared in prepared_items:`) her zaman yeşil kalır. Birini silmek her **bağımsız**
   kompozit Result'ı sessizce yeniden fiyatlamaktır.
3. **`portfolio_rules` paylaşımlı yolda `None`.** Çapraz-item önceliği ADR §12 satır 19 ile
   emekliye ayrıldı; item'a bir de sıralı kural vermek aynı soruya iki cevaptır (adaptör bunu
   zaten reddediyor).
4. **`max_position_notional` çıkarsanmaz.** §6 cap'i yüzdedir, sizing zinciri onu zaten
   `desired_size` içinde bağlar; `arbitrate`'in parametresi *"never inferred"* der.
5. **Worker phase loop'un sözlüğünü IMPORT ETMEZ.** Yeni bir alan gerekirse
   `participant.build_engine_participant`'ın imzasını genişlet — `ItemIdentity`/`ItemBarStream`'i
   `application/` içine taşımak imzalı allowlist'i **ikinci, imzasız** bir modülle büyütür
   (ölçüldü: üç dosyada beş assertion kırmızı). Kalıcı assertion:
   `assert "application/jobs/backtest_engine.py" not in live`.
6. **`SHARED_ALLOCATION_STATUS` `future_dev` kalır.** Lift = `C9` + ADR §16 **Gate 2**
   (`G10`, **hiç talep edilmedi**). Bir PR kendini `future_dev` / `ENGINE_VERSION` literali /
   `5000.00`-`3000.00` fixture'ını düzenlerken bulursa **sessizce ADIM 20 olmuştur → DUR**.

## 3. Sıradaki slice: **kod DEĞİL, iki İMZA** — sonra `C6`

Plan satırı: `docs/implementation/final_closure_ordered_plan_2026-08-13.md` §PACKAGE C, `C6`.

- **`C6`'nın ön koşulları:** `C4` merged ✅ + **`G11` (P2)** ve **`G12` (P8)** karara bağlanmış.
  **İkisi de İMZASIZ** (`G11` brifi #771, `G12` brifi #752). **Brifingli ≠ imzalı.**
  Planın kendi durdurma koşulu: *"If G11/G12 are unsigned, do not pick a default."*
- **`C5` ZATEN SEVK EDİLMİŞ** (ADIM 72'de ölçüldü, plan satırı düzeltildi) — iş **yoktur**.
- **`C7`** `C4` + `C5` ister ama `manifest.py`'ye dokunur ve **`execution_key` namespace'ini
  kaydırır** = **A15**. Yani `C7` bir "wiring" slice'ı değildir; ADIM 20 sınırındadır.
- **`C4`'ün `C6`'ya devrettiği ÖLÇÜM:** `participant._unsupported_shapes`'in on bir maddesi
  `C6`'nın admission blocker listesiyle **aynı** olmalıdır. Standart strateji fixture'ı o
  listeden **üç** maddeden düşüyor (`entry_timing`, `exit_timing`, `same_direction_stacking`) ve
  **üçüncüsü şema VARSAYILANIDIR** (`allow_stacking`) → bugünkü varsayılanla **kayıtlı
  stratejilerin çoğu** paylaşımlı saatte koşamaz. Bu bir ürün kararıdır, bir bug değil.

**Paralel hat (ön koşulsuz, `C`'den bağımsız):** kabul borcu partileri (`docs/audit/
acceptance_coverage_debt_ledger.md`) ve performans hattının **leg 3**'ü — ama leg 3 de
`G15` ürün kararıdır ve `per_item: 1` satırı **indirilmemelidir**.

## 4. Çalışma yöntemi (bu slice'ta işe yarayan)

- **ALT KÜME YEŞİLİ TAM SUITE YEŞİLİ DEĞİLDİR.** Bu slice on negatif kontrolden geçti ve
  dokunduğu her modülü koşturdu; yine de `test_shared_allocation_two_world_gate.py`'ı kırık
  bıraktı, çünkü o dosya dokunulan modüllerin listesinde değildi. **Ürün davranışını değiştiren
  bir slice'ta tam suiteyi koştur** — ve `PYTEST_EXIT`'i **ayrı** oku: arka plan görevinin
  bildirdiği çıkış kodu shell'inkidir, pytest'inki değil.
- **Negatif kontrol bir review'ın bulamayacağını buldu.** Yedi yeşil test bir kolun İKİNCİ
  çıkışını hiç ölçmemişti; `#4` paylaşımlı yolda `UnboundLocalError` fırlatıyordu ve bu ancak
  in-loop checkpoint kaldırılınca göründü. **Bir kolu kapattığında, o kolun HER çıkışını ölç.**
- **Kırmızı bir kapıyı gevşetmeden önce SAY** (ADIM 85'in dersi, yine işe yaradı): ağaç **üç
  dosyada beş assertion** dedi, dört guard **yeşil kaldı**. Tahmin edilmedi, koşuldu — **ve
  sayıdan sonraki doğru hamle genişletmek değil, TASARIMI DEĞİŞTİRMEKTİ.**
- **Negatif kontrolün temizliğini `git checkout <dosya>` ile yapma.** Index'ten geri yükler ve
  commit edilmemiş çalışma ağacını **siler** — bu slice'ta bir kez sildi. `cp` yedeği kullan.
- **Slice'a başlamadan ve KAPANIŞ PR'ını açmadan önce açık PR'ları tara.** Bu slice paralel bir
  oturumda da yazıldı (**#798**); onun ölçtüğü importer yaklaşımı bu dala **benimsendi**.
- **İki varsayım ölçümle çürüdü:** `COMPOSITION_CURVE_WARNING` paylaşımlı havuza özgü değil
  (bağımsız fold da yayımlıyor) · aynı session'da bir iptal `flush` olmadan görünmez
  (`refresh` flush edilmemiş alanı **düşürür**).
- **Alt küme koşarken `--no-cov`.** Tam suite coverage kapısıdır.
- **Postgres yoksa** `/var/tmp`'de unprivileged bir PG16 cluster kur (`initdb` root koşmaz →
  `postgres` kullanıcısı; `LC_ALL=C.UTF-8`, `en_US.UTF-8` bu container'da üretilmemiş).

---

## Paste-ready resume prompt

```
ENTROPIA V18 — sıradaki slice: PACKAGE C'nin serisel zinciri BİTTİ, önünde İKİ İMZA var
ROL: Entropia V18 Principal Engineer ve Release Closure Owner.
Konuşma dili TÜRKÇE; teknik tanımlayıcılar İngilizce.

SESSION START (atlamadan):
  git fetch --all --prune ; git status --short   -> kirliyse DUR
  git switch main ; git reset --hard origin/main ; git rev-parse HEAD
  git show origin/main:docs/PROJECT_HISTORY.md | grep -o '^## ADIM [0-9]*' | tail -4
  mcp__github__list_pull_requests (state=open)  -> açık PR'ların EKLEYECEĞİ kickoff
  dosya yollarını listele (add/add conflict bu haftanın en pahalı hatasıydı)
  Taban beklentin YOKTUR — ne bulursan RAPORLA ve her iddiayı AĞACA karşı yeniden ölç.

DURUM (2026-08-19 ölçüldü — DOĞRULA, GÜVENME):
  ADIM zinciri … 84·85·86·87 · canlı kickoff = docs/ADIM89_LANDED_KICKOFF.md
  alembic head 0043_i08_registry_strategy_fks · SHARED_ALLOCATION_STATUS = future_dev
  C1 #735 · C2 #759 · C3 #777 · C4 (ADIM 89) HEPSİ MERGED.

ÖNCE ÖLÇ, SONRA SEÇ:
  `C6` ön koşulu = G11 (P2) + G12 (P8) İMZALI. Bugün ikisi de İMZASIZ (brif #771 / #752).
  BRİFİNGLİ ≠ İMZALI. Planın kendi sözü: "If G11/G12 are unsigned, do not pick a default."
  `C5` ZATEN SEVK EDİLMİŞ (ADIM 72). `C7` manifest.py'ye dokunur ve execution_key
  namespace'ini kaydırır = A15, yani ADIM 20 sınırıdır — G10 hiç talep edilmedi.
  => İmzasız bir kapının arkasındaki slice'a BAŞLAMA. İmza yoksa PARALEL HATTA geç:
     kabul borcu partisi (docs/audit/acceptance_coverage_debt_ledger.md) — ratchet YALNIZ
     aşağı iner, tavan yükseltmek yasaktır.

OKUMA SIRASI: (1) docs/ADIM89_LANDED_KICKOFF.md (bu belge)
  (2) docs/implementation/final_closure_ordered_plan_2026-08-13.md §PACKAGE C
  (3) docs/adr/0002-unified-clock-portfolio-simulation.md §13.2, §14, §16
  (4) docs/generated/repository_facts.md = SAYISAL OTORİTE

C4'ÜN DEVRETTİĞİ ÖLÇÜLMÜŞ KALEMLER (görmezden gelme):
  - participant._unsupported_shapes'in 11 maddesi == C6'nın admission blocker listesi olmalı.
    Standart fixture ÜÇ maddeden düşüyor; üçüncüsü ŞEMA VARSAYILANI (allow_stacking)
    => kayıtlı stratejilerin çoğu paylaşımlı saatte koşamaz. ÜRÜN KARARI.
  - giriş fill'i komisyonu havuza aynalanmıyor (loop'ta o fazda book kanalı yok).
  - AÇIK İNSAN İNCELEMESİ (#731): C3 beş, C4 iki daha importer allowlist'i genişletti;
    imzalı karar YALNIZ containment gate'ini ölçmüştü. Bu bir ölçümdür, imza değil.

KAPILAR (hepsi exit 0; `| tail` KULLANMA, $?'i AYRI oku; alt kümede --no-cov):
  cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy src
  uv run python -m entropia.apps.api.openapi_export --check ; uv run alembic heads (tek head)
  uv run pytest -q   (tam suite = coverage kapısı >=90)
  (backend'den) uv run python ../scripts/generate_repository_facts.py --root .. --check
  repo KÖKÜNDEN: node scripts/memory_index.mjs --check

YÖNTEM: Her assertion'ı NEGATİF KONTROLDEN geçir — davranışı üründen kaldır, testin
  KIRMIZIYA döndüğünü ve HANGİ assertion'da döndüğünü gör. and/or kapılarında bileşik
  sonucu değil TERİMLERİ ayrı pinle. Bir kolu kapattığında o kolun HER çıkışını ölç
  (C4'te yedi yeşil test checkpoint #4'ün paylaşımlı çıkışını hiç ölçmemişti).

DURDURMA KOŞULLARI ("Complete" yazma): golden digest kıpırdadıysa · lift pinlerinden birini
  (future_dev, ENGINE_VERSION literali, 5000.00/3000.00 fixture'ı) düzenlemek gerekiyorsa
  (o zaman slice sessizce ADIM 20 olmuştur ve G10 gerekir) · imzasız bir kapının arkasına
  geçmen gerekiyorsa · açıklanamayan fark.

GIT/PR: yeni bir dal; commit `<type>(<slug>): <konu>`. AI attribution YOK. PR aç, MERGE ETME.
KAPANIŞ: 6 maddelik ritüel (CLAUDE.md §Session CLOSING). Boş ADIM numarasını merge'den HEMEN
  ÖNCE `grep '^## ADIM' docs/PROJECT_HISTORY.md` ile doğrula; demote hedefini (o an `current`
  olan kickoff) numarayla AYNI commit'te taşı; `## Next:` BAŞLIĞINI YENİDEN ADLANDIRMA.
```
