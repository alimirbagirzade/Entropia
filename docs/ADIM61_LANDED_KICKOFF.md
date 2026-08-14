<!-- doc-status: historical -->
> **HISTORICAL KICKOFF — canlı olan `docs/ADIM62_LANDED_KICKOFF.md`'dir.**
> **CURRENT SLICE KICKOFF.** Sayısal gerçekler için otorite:
> `CLAUDE.md` §Current position + `docs/generated/repository_facts.md` (üretilmiş).

# ADIM 61 LANDED — üç canlı finansal kusur kapandı · sıradaki slice için kickoff

> **NUMARA NOTU — bu slice İKİ KEZ taşındı: 58 → 60 → 61.** Dal
> `feat/stage-58-sizing-commission-zero-size`, commit mesajları `stage-58` yazar —
> **değiştirilmedi**. Kod PR'ı `#720` açıldığında main'in son kaydı ADIM 58'di; kapanış
> yazılırken **ADIM 59** (`#718`) inmişti → kayıt 60 olarak yazıldı. Sonra kapanış PR'ı
> `#723` **açıkken** `#721` merge oldu ve `## ADIM 60` ile
> `docs/ADIM60_LANDED_KICKOFF.md`'in **ikisini birden** aldı → bu belge **ADIM 61**'dir.
> Kural: **numaralar yeniden atanmaz, merge edilmiş ad kazanır.**
>
> **Yeni ders:** çakışma bu turda **iki eksenliydi** — yalnız `## ` başlığı değil, **dosya
> adı** da. Bu iyi haber: ikinci PR add/add çakışmasına düşer ve `check_classification`
> iki `current` kickoff'u kırmızıya çevirir, yani **sessiz bir yanlış merge mümkün
> değildi**. `#700` de bir ara aynı numaraya oynuyordu (üç PR, tek numara).
> **Numarayı kapanış commit'ini YAZARKEN doğrulamak YETMEZ — merge'den hemen önce
> `origin/main`'i yeniden ölç.**

---

## Neredeyiz

**Blocker sayısı 1 (yalnız A-08), verdict BLOCKED — DEĞİŞMEDİ.** ADIM 61 A-08'e dokunmadı.

Ama önceki on bir slice'tan **farklı** bir şey oldu: bu bir denetim ya da belge slice'ı
değildi. **Ürün kodu değişti ve finansal sonuçlar oynadı.** ADIM 58 ve 59'un denetimleri üç
kusuru *canlı* ölçmüştü; ADIM 61 üçünü de kapattı.

| Issue | Neydi | Ne oldu |
|---|---|---|
| **#550** | `base_position_size` + min/max sınırları **birim sayısı** olarak koşuyordu; beş yüzey (form `%` etiketi, doc 02 örneği, Master Ref §10.1, V18 mockup, ⓘ paneli) yüzde diyordu | üçü de **resolved capital'ın yüzdesi**; sapma fiyatla sınırsız büyüyordu (10 000'lik enstrümanda 100 000 nominal) |
| **#551** | `if alloc_on and size <= _ZERO` → bağımsız kipte 0-boyutlu hayalet pozisyon; **negatif** boyut PnL işaretini ters çeviriyordu | `if size <= _ZERO`, her modda, negatif dahil |
| **#552** | komisyon **kapanış** sayısıyla ölçekleniyordu (`1 + Σ fraction`), ücret kapatılan miktarı değil `fraction` parametresini izliyordu | **fill başına** (PD-2) |

`ENGINE_VERSION` → **`backtest-engine-v18-percent-sizing-per-fill-commission`**.
Migration yok (head `0043_i08_registry_strategy_fks`), `SHARED_ALLOCATION_STATUS`
`future_dev`. Merge sha **`5e52465`** (PR #720), 52 dosya, +1090/−226.

---

## Bu slice'ın bıraktıkları (reuse anchor'ları — tam adlarıyla)

* **`domain/backtest/execution/sizing.py::_percent_of_capital`** — üç magnitude'un TEK
  dönüşümü, motorun `_QTY` adımında kuantize. Ayrışamamalarının sebebi budur.
* **`domain/backtest/execution/sizing.py::max_position_size_cap`** — **YENİ public sembol.**
  `max_position_size`'ı okuyan **her yer** buradan geçer: scaling merdiveni
  (`resolve_scale_rejection` yoluyla) ve aynı-yön stacking tranche'ı. Allocation açıkken
  sermaye argümanı **sleeve**'dir, `led.equity` değil.
* **`domain/strategy/config.py::PositionSizing.size_semantics`** —
  `Literal["percent_of_capital"] | None`.
* **`domain/readiness/enums.py::ReadinessIssueCode.STRATEGY_SIZING_SEMANTICS_UNCONFIRMED`**
  + `validators.py`'deki `carries_magnitude` bloğu.
* **`frontend/src/lib/strategyForm.ts`** — kaydetmek `size_semantics` basar; kapının
  **temizleme yolu** budur.
* **Golden matris** `tests/unit/test_backtest_engine_golden.py` → **50 senaryo**
  (`costs.commission_round_trip`, `costs.commission_scale_ladder`,
  `sizing.base_percent_of_capital`, `sizing.impossible_window_opens_nothing`).
* **`.gitleaks.toml`** — digest satırı ŞEKLİ için allowlist (noktalı anahtar + 64 hex).

---

## Tavizsiz kurallar (bu slice'ta kanıtlandı)

1. **Cap'i okuyan yeni bir yer eklersen `max_position_size_cap`'ten geçir.** Yüzdeyi bir
   miktarla karşılaştıran bir satır, giriş zincirinin bağladığı yerden **başka** bir yerde
   bağlar — bu tam olarak düzeltilen kusurdu, iki farklı yerde.
2. **Yeni bir sizing magnitude alanı eklersen readiness geçiş kapısını genişlet.** Kapı
   **ALAN** tabanlıdır, metot tabanlı değil: yalnız max cap taşıyan risk-based bir strateji
   de açıktır, hiç magnitude taşımayan **bloklanmaz** (negatif kontrolü
   `test_sizing_semantics_gate_is_silent_when_no_magnitude_changed_meaning`).
3. **Golden matrise senaryo eklerken NEGATİF KONTROLÜNÜ de üret.** Bu slice'ın #552'de
   yaşadığı şey: matris hiçbir yerde komisyon yapılandırmıyordu, o yüzden düzeltme
   **46'nın 0'ını** oynattı ve yeşil ratchet o eksen için **kanıt değildi**.
4. **Fixture'da sayıyı değil NİYETİ yeniden ifade et.** 124 kırmızı, oracle'ların 50 birimlik
   pozisyonu **risk-based** ifade edilerek (`1% × 10 000 / 2.00`) çözüldü — modellenen tek
   fiyat-BAĞIMSIZ yöntem. Yüzde **efektif** fill fiyatına böler, yani maliyet oracle'ının
   boyutu maliyetle birlikte oynar ve tek-knob-tek-delta ölür. `stop_loss_point` yalnız
   sizing'i besler, **stop kurmaz**.
5. **main'i içeri alırken MERGE DEĞİL REBASE.** main bir `## ` başlığı yeniden
   adlandırdığında merge onu staged diff'te `-## ` **silme** olarak sahneler ve
   `docs-history-guard` bloklar — haklı olarak, çünkü #590/#604'te 400+ satır böyle
   kaybolmuştu. **Kapıyı kapatma** (`ENTROPIA_HOOKS=off` komut içinde zaten çalışmaz: hook
   komuttan ÖNCE koşar). Rebase et; çakışanlar hemen her zaman üç **üretilmiş** dosyadır →
   `git checkout --theirs` + `generate_repository_facts.py`.
6. **`update_pull_request_branch`'i KAPANIŞ PR'ında KULLANMA.** Kod PR'ında güvenlidir
   (main o dosyalara dokunmaz). Belge PR'ında **değil**: bu slice'ta sunucu tarafı merge
   `be4a082` ADIM kaydının **tamamını sessizce düşürdü** ve **her kapıdan geçti** — hiçbir
   CI kapısı `docs/` altında kayıt silinmesini okumaz, `docs-history-guard` ise yerel
   commit olmadığı için hiç koşmaz. *"Hook koşmuyor, o yüzden ucuz"* gerekçesi tersine
   döner: koşmaması **deliğin kendisidir**. `behind` düşersen yerelde rebase et, kaydın
   durduğunu `grep` ile gözle doğrula, `--force-with-lease` ile it.

---

## Açık kalanlar (ADIM 61 bunları KAPATMADI)

* **Komisyon TABANI.** Kanon (Master Ref `:3110`) **notional üzerinden bps**; sevk edilen
  alan para birimsiz **düz tutar** ve manifest resolved default yayımlamıyor. PD-2
  **bölüşümü** kapattı, tabanı değil. main'deki `docs/decisions/closure_product_decisions_2026-08-13.md`
  Karar 1 / **Seçenek C** bu sorudur; belgenin Karar 1 bölümü artık **bayattır** (Seçenek A
  sevk edildi).
* **A-08 ekran okuyucu denetimi** — tek blocker, değişmedi.
* **PR B / `ItemParticipant`** — ADIM 59'un ölçtüğü tek engel (b) yerinde, ADR §16 insan
  kapısının arkasında.
* `#514` · `#544` · `#558` · `#559`.

---

## Sıradaki iş

`STAGE2_HANDOFF.md` §Next hâlâ **PR B**'yi gösteriyor ve o **ADR §16 insan kapısının**
arkasında. Kapı açılmadan başlanmaz.

Kapı beklerken alınabilecek, bu slice'ın açtığı iki iş:

1. **Komisyon tabanı kararı** (yukarıda) — bir **ürün kararı**, kod değil. Karar imzalanana
   kadar `booking.py`'nin düz-tutar okuması kanoniktir ve docstring'i öyle der.
2. **Kabul borcu sınıf B, sonraki parti** — ADIM 48/52/54'ün deseni. **Parti seçmeden ÖNCE
   ÖLÇ:** kriterin adlandırdığı davranış `backend/src`'te sevk edilmemişse sınıfı yanlıştır
   (ADIM 52'nin `TL-11.c3` dersi).

---

## Paste-ready resume prompt

```
Entropia'da yeni bir slice'a başlıyoruz. Session START protokolünü uygula.

Taban: origin/main. Son inen slice ADIM 61 — üç canlı finansal kusur kapandı
(#550 yüzde sizing, #551 sıfır/negatif boyut reddi, #552 fill başına komisyon),
PR #720, merge sha 5e52465. ENGINE_VERSION artık
backtest-engine-v18-percent-sizing-per-fill-commission. Migration yok.
Blocker sayısı 1 (yalnız A-08), verdict BLOCKED.

ÖNCE OKU (otorite sırası):
1. docs/ADIM61_LANDED_KICKOFF.md (bu belge — reuse anchor'ları ve tavizsiz kurallar)
2. docs/STAGE2_HANDOFF.md §Stage 60 landed + §Next
3. docs/PROJECT_HISTORY.md §ADIM 61 (tam kayıt)
4. docs/generated/repository_facts.md (ÜRETİLMİŞ — sayısal otorite)

BİLMEN GEREKENLER:
- max_position_size_cap YENİ bir public sözleşmedir; max_position_size'ı okuyan
  her yer ondan geçer. Yüzdeyi miktarla karşılaştıran bir satır yazma.
- Readiness geçiş kapısı (STRATEGY_SIZING_SEMANTICS_UNCONFIRMED) ALAN tabanlıdır.
  Yeni bir sizing magnitude alanı eklersen carries_magnitude'ı genişlet.
- Golden matris 50 senaryo. Senaryo eklersen negatif kontrolünü de üret.
- Oracle fixture'ları risk-based sizing ile 50 birimi pinliyor (1% x 10 000 / 2.00).
  Yüzde sizing efektif fill fiyatına böler; maliyet oracle'ını onunla boyutlandırma.
- main'i içeri alırken MERGE DEĞİL REBASE (docs-history-guard, main'in başlık
  yeniden adlandırmasını kayıt silme sanar). Belge PR'ında
  update_pull_request_branch KULLANMA — sunucu merge'i kaydı sessizce düşürür
  ve hiçbir kapı görmez.
- Numarayı kapanış commit'ini YAZARKEN ve merge'den hemen ÖNCE doğrula.

AÇIK: komisyon TABANI (bps mi düz tutar mı) — ürün kararı, #709'un brief'i
Karar 1 / Seçenek C. A-08 denetimi. PR B (ADR §16 insan kapısı).

Ne yapacağımızı sormadan önce yukarıdakileri oku, sonra bana neyi hedeflediğimizi
sor.
```
