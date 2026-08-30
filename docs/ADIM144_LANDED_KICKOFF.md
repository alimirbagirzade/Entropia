<!-- doc-status: current -->
# ADIM 144 landed — GH #536 md. 2'nin kalanı: `most_conservative` tie-break'i + `first_trigger_wins` yapısal dışlaması

## Nerede olduğumuz

Taban `origin/main` @ `c9676816` (ADIM 143). Bu slice **yalnız test** sevk etti:
`backend/src`'te **sıfır satır**, migration yok, `ENGINE_VERSION` değişmedi, golden el
değmedi, OpenAPI değişmedi, `frontend/src` sıfır satır. Üç yeni test fonksiyonu (yedi
parametrik case). **Blocker DEĞİŞMEDİ (1 — yalnız A-08) → RC verdict BLOCKED.**

ADIM 143 kendi docstring'ine bir HONEST BOUNDARY yazmıştı (*"a logic block competing under
`most_conservative` … or under `first_trigger_wins` is not covered"*). Bu slice onu kapattı.

## Bu slice'ın bıraktığı çapalar (tam sembol adlarıyla)

`backend/tests/unit/test_backtest_logic_stop.py`:

- `_TIE_PCT_LEVEL` = `99`, `_TIE_LOGIC_CLOSE` = `101` — beraberliği kuran **iki sabit**;
  ikisi de fixture'lar tarafından okunur, biri değişirse **tie guard ateşlenir** (NC-5).
- `_bar(low, close, high="100")` — `high` **opsiyonel eklendi**, varsayılan mevcut her
  çağıranı **bayt bayt aynı** bırakır.
- `_resolve(..., ticks=())` + `_ticks(*prices)` — tick yolu **opsiyonel** geçilir.
- `_CONSERVATIVE_TIES` (×3) · `test_most_conservative_breaks_a_distance_tie_with_the_stop_priority_order`
- `test_first_trigger_wins_cannot_elect_a_logic_block_from_a_tick_path` — **iki kollu**,
  ikinci kol testin **kendi negatif kontrolü**.

`backend/tests/unit/test_conflict_policy_coverage.py`:

- `_ORDER_UNDER_TEST` · `_RESOLUTION_CONTESTS` ·
  `test_the_stop_priority_order_governs_only_under_the_resolution_that_reads_it` (×3)
- Modül docstring'indeki **HONEST BOUNDARY yeniden yazıldı** (ADIM 143'ünki tahliye edildi).

Sevk edilmiş taraf (**el değmedi**): `execution/fills.py::_resolve_stop`'un
`most_conservative` demet karşılaştırıcısı ve `first_trigger_wins`'in `price_triggered`
filtresi · `stop_priority_sequence` · `_first_tick_touch`.

## Ölçülmüş ve KAPATILMAYAN

- **#536 AÇIK.** md. 2 tamam; **md. 4 (Gap C) kapsam dışı** (tasarım kararı).
- **`record_all_execute_highest` hâlâ ikiz olarak PİNLİ, DÜZELTİLMEDİ** (ürün kararı).
- Motor düzlemindeki contest'in **tick yolu yok** → `first_trigger_wins` orada yalnız
  OHLCV geri düşüşüyle sürülür; tick-çözümlü kolu **yalnız unit düzleminde** kapsanır.
- Şema prozası **düzeltilmedi** (adjudication).
- `integration/test_logic_based_stop.py` ve `oracles/test_oracle_protection_stops.py`
  **EL DEĞMEDİ**.
- **Frontend kapıları koşulmadı** (frontend'de sıfır satır).
- **A-08 (#514) AÇIK** — tek blocker, `human-only`, çıkış kriterleri 0/4.

## Çalışma yöntemi (bu slice'ta işe yarayanlar)

- **Devir notunun "kapsanmadı" dediğini ağaçta ARA.** *"`most_conservative` altında logic
  bloğu yarışmıyor"* **harfi harfine yanlıştı** (`test_logic_stop_can_be_more_conservative_than_a_touched_price_stop`
  zaten yarıştırıyor). Gerçek boşluk daha inceydi: **karşılaştırıcı bir DEMET** ve yalnız
  **birinci** terimi okunuyordu. ADIM 143'ün *"ULAŞMAK ≠ ATEŞLEMEK"*'inin kardeşi:
  **YARIŞMAK ≠ BERABERE KALMAK.**
- **Boşluğu yazmadan önce ÖLÇ.** İki bağımsız enjeksiyon (tie-break silindi · dışlama
  kaldırıldı) → **ikisinde de 2597 passed, exit 0**.
- **Bir NC yalnız kırmızı verdiği için kabul edilmez — KAPSAMINI oku.** NC-3 altı testi
  düşürdü, **dördü mevcut** ⇒ *"mesafe birincildir"* zaten korunuyordu → **REDDEDİLDİ**,
  yerine **yalnız açık sıra** varken vuran NC-3′ (tam 2 kırmızı, ikisi de yeni).
- **Kendi bayrağın kanıtı gizleyebilir:** `addopts` zaten `-q` taşırken komut satırına
  ikinci bir `-q` koymak pytest **özet satırını susturur** → elde yalnız exit code kalır.
- **Vacuity muhafızını da yanlışla** (NC-5): tie guard fixture kayınca gerçekten ateşleniyor.
- **NC turundan sonra ağacı geri al VE `__pycache__`'i temizle** (ADIM 141); her turda
  `git status --porcelain backend/src` boş doğrulandı.

## Paste-ready resume prompt

```
ENTROPIA — ÖNCE ADIM 144'ÜN PR'ININ İNİP İNMEDİĞİNİ ÖLÇ, SONRA SIRADAKİ KALEMİ SEÇ.

ÖNCE DOĞRULA (bu prompt BAYAT VARSAYILIR):
  git fetch && git log --oneline origin/main -4 && gh pr list --state open
  grep -n '^## ADIM' docs/PROJECT_HISTORY.md | tail -2
  grep -c '☐'     docs/decisions/closure_i703_instrument_mapping_writer_2026-08-30.md
  grep -c '\[ \]' docs/decisions/closure_i534_same_candle_suppression_counter_2026-08-29.md
  grep -c '☐'     docs/decisions/closure_i854_external_import_pin_stability_2026-08-28.md
  gh issue view 536 --json state && gh issue view 514 --json state

NOT: karar belgeleri FARKLI kutu işareti kullanır (#534 -> "[ ]", #703/#854 -> "☐").
Tek grep hepsini ölçmez. Kapalı issue != verilmiş karar (ADIM 90): kapanış yorumu YOKSA
ve imza kutusu BOŞSA kalem AÇIKTIR.

DURUM: ADIM 144 GH #536'nın md. 2'sini BİTİRDİ. İki yük taşıyan davranışın hiç muhafızı
olmadığı ÖLÇÜLDÜ (her iki enjeksiyonda da 2597 passed): most_conservative'in tie-break
terimi ve first_trigger_wins'in logic-stop dışlaması. backend/src'te sıfır satır.
#536 KAPATILMADI. PR açıksa yeni slice AÇMA; inmişse ADIM 145.

SIRADAKİ KALEM — ÜÇÜ İMZA, İKİSİ KOD, BİRİ BLOCKER:

(1) #703 instrument_mapping_ref yazıcısı (İMZA) — üç karar / on bir kutu, hepsi BOŞ.
(2) #854 dış import pin'i (İMZA) — dokuz kutu, dokuzu BOŞ.
(3) #534 AYRIŞMA (İMZA) — issue CLOSED, kapanış yorumu YOK, dört kutu BOŞ -> md. 3 açık.
(4) #536'nın kalanı — İKİSİ DE KARAR, imzasız yapılamaz:
    - md. 4 (Gap C guard) = TASARIM kararı (altı alanı _SCHEMA_FIELDS'e ekle ya da
      yeni-literal allowlist muhafızı yaz);
    - record_all_execute_highest'ın şema vaadi ayırt edici değil = ÜRÜN kararı.
    NOT: #536'nın imzasız KOD işi TÜKENDİ (md. 1/2/3 kapandı).
(5) #677 Lighthouse dört donmuş eksik (KOD) — Compose + Lighthouse koşabilen ortam ister.
(6) A-08 (#514) — TEK BLOCKER, human-only. Çıkış kriterleri 0/4 -> KAPATILMAMALI.

KURALLAR: her iddiayı ampirik doğrula; devir notunun "kapsanmadı" dediğini ağaçta ARA
(ADIM 144'te "logic bloğu yarışmıyor" yanlış çıktı — YARIŞMAK != BERABERE KALMAK); bir NC
yalnız kırmızı verdiği için kabul edilmez, KAPSAMINI oku; pytest'e ikinci bir -q verme
(özet susar); sayı taşıma, yeniden ölç; kapatmadığını covered İŞARETLEME; izole DB
(TEST_DATABASE_URL, asyncpg); NC sonrası bayat bytecode'u da temizle; üretilmiş
artefaktları tazele ve DELTA'yı oku; kapanış ritüeli ZORUNLU.
```
