<!-- doc-status: current -->

# ADIM 137 — GH #534: provenance bloğunun yayımlamadığı iki conflict kuralı

**Taban:** `de3d8816` (ADIM 136). **Migration YOK.** **`ENGINE_VERSION` DEĞİŞTİ** →
`backtest-engine-v18-conflict-provenance-completed`. **Golden yeniden üretildi (46/50).**
OpenAPI **değişmedi (ölçüldü: yeni anahtarlar 0 kez — kardeşi `stop_exit_conflict` de 0)**.
`frontend/src`'te sıfır satır. **Blocker DEĞİŞMEDİ (1 — yalnız A-08), BLOCKED.**

---

## Nerede duruyoruz

Oturum **iki imza kontrolüyle** açıldı ve ikisi de bloklu çıktı: #854'ün **dokuz kutusunun
dokuzu da BOŞ** (durduruldu — varsayılan seçilmedi, issue kapatılmadı), A-08 (#514)
`human-only`. Ürün sahibinin ölçülmüş kod adaylarından **#534** alındı; **md. 1/2/4 sevk
edildi, md. 3 adjudication olduğu için AÇILDI ama verilmedi.**

## Bu slice'ın bıraktığı çapalar (tam sembol adlarıyla)

- `execution/state.py::_RunConfig.same_candle_entry_exit` — §5.9 flat-position çakışma
  politikası, kardeşi `stop_exit_conflict`'in hemen yanında.
- `execution/state.py::_RunConfig.stop_priority_resolved` — **çözülmüş TOPLAM** stop
  öncelik sırası (`tuple[str, ...]`), ham nullable config girdisi DEĞİL.
- `engine.py` — sıra `_stop_priority_index`'ten **tek kez**, `logic_enabled`'ın kurulduğu
  yerde türetilir (`logic_enabled` koşu başına kurulur; `:969`–`:1206` arasında fonksiyon
  sınırı yok, ölçüldü).
- `execution/output.py` — `"same_candle_entry_exit"` ve `"stop_priority_resolved"`
  provenance bloğunda, gerekçeleri kaynak yorumunda.
- `tests/unit/test_backtest_conflict_provenance.py` — 6 case; yeni yüzey buraya yazılır.
- `tests/unit/test_backtest_engine.py::_config(stop_priority_order=...)` — **opsiyonel**
  parametre, varsayılan `None` → mevcut çağıranlar bayt bayt aynı.

## Pazarlıksız — bir sonraki okuyucu için

1. **Sırayı `output.py` tarafında YENİDEN YAZMA.** Tek kaynak `fills._stop_priority_index`;
   ikinci bir transkripsiyon motorun danıştığı sıradan ayrışır ve
   `test_the_published_order_is_the_one_the_resolver_would_build` bunu kırmızıya çevirir.
2. **Ham nullable girdiyi yayımlama.** `null` yaygın durumdur ve `None` basmak okuyucuya
   hiçbir şey söylemez; yayımlanan şey **çözülmüş** sıradır.
3. **`diagnostics`'e üye eklemek golden'ı OYNATIR.** Eksen *"diagnostics mi"* değil,
   **"artefaktın baytları oynuyor mu"** (ADIM 136'nın imzalı kuralı). Oynuyorsa **bump**,
   ve golden **aynı commit'te** yeniden üretilir.
4. **Golden'ı körlemesine yeniden üretme.** Önce payload'ları dondur, delta'nın **yalnız**
   eklenen üye olduğunu üye üye kanıtla — digest *"oynadı"* der, **ne** oynadığını demez.
5. **`suppressed_entries`'in anlamını değiştirme** — üç yol ona yazıyor ve semantiğini
   yeniden yazmak **adjudication**'dır (md. 3, imzasız).

## Açık kalanlar (bu slice kapatmadı, iddia da etmiyor)

- **#534 AÇIK** — md. 3 (`docs/decisions/closure_i534_same_candle_suppression_counter_2026-08-29.md`,
  **dört kutu, dördü BOŞ**).
- **#854 AÇIK** — dokuz kutu boş; düzeltme **dört** çağrı yerini birden değiştirir
  (`link_batch_to_revision` + `link_normalized_to_revision`, her biri create + revision) ve
  `test_external_import_pin_stability.py`'nin iki case'ini **kasıtlı** kırmızıya çevirir.
- **A-08 (#514) AÇIK** — tek blocker, `human-only`.
- **#703 AÇIK** — `native_asset_id` üretimde hiç yazılmıyor (ölçülmüş aday, alınmadı).
- `stop_priority_resolved` **koşu düzeyinde** tek sıradır; bar başına değişen bir tasarımda
  **yeniden ölçülmelidir**.
- Karar izinin **persist katmanındaki** olası limit **ölçülmedi**.
- **frontend kapıları KOŞULMADI.**

## Paste-ready resume prompt

```
ENTROPIA — ADIM 137 SONRASI. SIRADAKİ KALEM YİNE İMZA.

ÖNCE DOĞRULA (bu prompt BAYAT VARSAYILIR):
  git fetch && git log --oneline origin/main -4 && gh pr list --state open
  grep -n '^## ADIM' docs/PROJECT_HISTORY.md | tail -2
  grep -c '☑' docs/decisions/closure_i854_external_import_pin_stability_2026-08-28.md
  grep -c '☑' docs/decisions/closure_i534_same_candle_suppression_counter_2026-08-29.md

(1) #534 md. 3 — same-candle bastırmaları kendi sayacını hak ediyor mu? DÖRT kutu, ADIM
    137'de dördü de BOŞ. (b)/(c) seçilirse: state.py::_Ledger + output.py değişir, golden
    YENİDEN ÜRETİLİR, ENGINE_VERSION BUMP EDİLİR (bayt oynuyor). (c) ayrıca sevk edilmiş
    bir sayının anlamını değiştirir ve eski Result'ların okunabilirliğini AYRI bir kalem
    olarak açmayı gerektirir. Kutu boşsa DUR — varsayılan seçme, #534'ü kapatma.

(2) #854 — dış import pin'i taşınıyor. DOKUZ kutu, dokuzu da BOŞ. Şıkka göre DÖRT çağrı
    yerini birden değiştir; iki test kasıtlı kırmızı olur. Kutu boşsa DUR.

(3) A-08 (#514) — tek blocker. human-only; agent ne açar ne kapatır.

KOD KALEMİ İSTİYORSAN: #703 (native_asset_id üretimde hiç yazılmıyor — okuyucu var, yazıcı
yok; funding-enabled koşu app'te üretilmiş hiçbir research revision'ıyla çalışamaz).

KURALLAR: her iddiayı ampirik doğrula; sayı taşıma, yeniden ölç; diagnostics'e üye eklemek
golden'ı oynatır → önce payload'ları dondur, delta'yı üye üye kanıtla, sonra bump; kapatmadığını
covered İŞARETLEME; kapanış ritüeli ZORUNLU.
```
