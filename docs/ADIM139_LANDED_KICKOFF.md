<!-- doc-status: historical -->

# ADIM 139 — GH #540: kapasite-matrisi muhafızı 9/14 → 14/14 + registry anti-drift ekseni (LANDED KICKOFF)

> Bu belge ADIM 139'un kapanış handoff'udur. En altta **paste-ready resume prompt** var.

## Neredeyiz

`backend/tests/unit/test_capability_matrix.py::_SCHEMA_FIELDS` artık matrisin **14
`field_path`'inin 14'ünü** kaydediyor (önce 9'du), ve **yeni bir ikinci eksen** registry'nin
matristen ayrışmasını CI'da kırıyor.

**ÜRÜN KODUNDA SIFIR SATIR.** Migration **YOK** · `ENGINE_VERSION` **değişmedi** · golden
**el değmedi** · OpenAPI **değişmedi** · `capabilities.py` **EL DEĞMEDİ** (sıfır yeni matris
satırı gerekti — ölçüldü) · `frontend/src` **sıfır satır** ·
**blocker DEĞİŞMEDİ (1 — yalnız A-08), BLOCKED.**

## Bu slice'ın bıraktığı çapalar (tam sembol adlarıyla)

* `tests/unit/test_capability_matrix.py::_SCHEMA_FIELDS` — beş yeni giriş:
  `data.order_config.limit.price_rule` ve `.partial_fill_policy` → `LimitOrderDetails` ·
  `position_sizing.formula_based.formula_type` → `FormulaBasedSizing` ·
  `scaling_logic.timeframe_mode` ve `scaling_logic.method` → `ScalingLogic`.
  **Model/alan çiftleri tahmin edilmedi**, dotted path `StrategyConfig`'ten
  `get_type_hints` ile çözülerek ölçüldü.
* `tests/unit/test_capability_matrix.py::test_the_registry_covers_every_matrix_field_path` —
  **eksen 2**. `set(_SCHEMA_FIELDS) == {o.field_path for o in CAPABILITY_MATRIX}`.
* `domain/backtest/capabilities.py::MATRIX_FIELD_PATHS` — **VAR ve kullanılmadı**, bilerek:
  eksen 2 sevk edilmiş **türeve** değil **kanona** karşı karşılaştırır.

## Pazarlıksız olanlar (bir sonraki oturum bunları BOZMASIN)

1. **Eksen 2'yi silme ya da `MATRIX_FIELD_PATHS`'e çevirme.** Eksen 1 registry üzerinde
   parametrize olduğu için registry drift'ine **yapısal olarak kördür** (NC-2'de ölçüldü: 13
   eksen-1 parametresi yeşil kalır). Türeve karşı karşılaştırmak, türev bozulduğunda testi
   sessizce peşinden sürükler.
2. **Yeni bir matris `field_path`'i eklersen `_SCHEMA_FIELDS`'e de ekle.** Eklemezsen eksen 2
   kırmızı verir — **bu doğru davranıştır**, testi gevşetme.
3. **Yeni bir literal kaydedilmemiş kalırsa `active_v1` ile toptan doldurma.** #540'ın kendi
   sınırı: çalışmadığı ölçülen bir literal bir **kapasite bulgusudur**, test düzeltmesi değil
   → DUR ve raporla.
4. **TS ayna testi kırmızıysa "aynayı yeniden üret" refleksine dikkat.** NC-4 tam olarak bunu
   ölçtü: düzeltme öncesi dünyada yeni bir alan **yalnız** aynayı kırıyordu ve aynayı
   yenilemek yeşili geri getirirken alanı kaydedilmemiş bırakıyordu. Beş alan böyle sızdı.

## Ölçülüp KAPATILMAYANLAR

* **#540 KAPATILMADI** — insan kararı.
* **#536'nın altı alanı** kapsam dışı: ayrı issue, ayrı kusur sınıfı (orada her literal çalışır).
* **Kabul defteri el değmedi**, hiçbir tavan oynamadı.
* `mypy tests/…` bu dosyada **önceden var olan** bir `attr-defined` hatası taşır (`:213` →
  `:227`); CI kapısı `mypy src` **temiz**.

## Paste-ready resume prompt

```
ENTROPIA — ADIM 139 (#540: kapasite muhafızı 9/14 -> 14/14 + anti-drift ekseni) İNDİ.

ÖNCE DOĞRULA (bu prompt BAYAT VARSAYILIR):
  git fetch && git log --oneline origin/main -4 && gh pr list --state open
  grep -n '^## ADIM' docs/PROJECT_HISTORY.md | tail -2
  gh issue list --state open --limit 60

İMZA KUTULARINI KUTU KUTU OKU — İKİ BELGE FARKLI İŞARET KULLANIR:
  grep -c '\[ \]' docs/decisions/closure_i534_same_candle_suppression_counter_2026-08-29.md   # 4 = hepsi boş
  grep -c '☐'     docs/decisions/closure_i854_external_import_pin_stability_2026-08-28.md     # 9 = hepsi boş
Tek bir grep ikisini birden ölçmez.

DURUM: ENGINE_VERSION = backtest-engine-v18-policy-provenance-completed (ADIM 139 DEĞİŞTİRMEDİ).
Blocker DEĞİŞMEDİ (1 — yalnız A-08), RC verdict BLOCKED.

SIRADAKİ KALEM — İMZASIZ KOD ADAYI KALMADI MI? ÖLÇ, VARSAYMA:

(1) #534 md. 3 — same-candle sayacı (İMZA). DÖRT kutu, ADIM 139'da yeniden ölçüldü: BOŞ.
    (c) = sıfır kod ve #534 kapanır; (a)/(b) = yeni sayaç + ENGINE_VERSION bump + golden.
(2) #854 — dış import pin'i TAŞINIYOR (İMZA). DOKUZ kutu, dokuzu da BOŞ. Şıkka göre DÖRT
    çağrı yeri birden değişir; test_external_import_pin_stability.py KASITLI kırmızı olur.
(3) instrument_mapping_ref (İMZA, sonra KOD) — #703'ün ikizi, ADIM 138'de ölçüldü: dört
    okuma, SIFIR yazıcı. Bir yazıcı eklemek "mapping ref nereden gelir" = ÜRÜN KARARI.
    Sınır test_research_native_asset_pointer.py içinde PİNLİ.
(4) #536 — kaydedilmemiş conflict option değerleri + inert overlapping_signal_policy. ADIM
    139'un KARDEŞİ ama AYRI kusur sınıfı: orada her literal çalışır, o yüzden kaydedilmemiş
    değer zararsız. İçinde ürün sorusu var mı ÖNCE ölç.
(5) #540 hâlâ AÇIK — kod indi, kapatmak insan kararı.
(6) A-08 (#514) — TEK BLOCKER, human-only, repo içinden KAPATILAMAZ.

DERS (ADIM 139): bir muhafızın kendi muhafızı olmayabilir. test_matrix_enumerates_every_
schema_literal MATRİS üzerinde değil REGISTRY üzerinde parametrizeydi -> kaydedilmemiş alan
hakkında hiç soru sorulmuyordu. Boşluğu İDDİA ETME, ÖLÇ: kusuru enjekte et ve suite'in YEŞİL
kaldığını gör (NC-0), sonra düzeltip aynı mutasyonun kırmızı verdiğini gör (NC-1).

DERS 2: SLICE'A BAŞLAMADAN ÖNCE AÇIK PR'LARI VE PARALEL OTURUMLARI TARA (#875/#876 emsali).

KURALLAR: her iddiayı ampirik doğrula; sayı taşıma, yeniden ölç; test EKLEYEN slice
docs/generated/repository_facts.* + README bloğunu TAZELEMELİ (ADIM 60); kapatmadığını
covered İŞARETLEME; kapanış ritüeli ZORUNLU.
```
