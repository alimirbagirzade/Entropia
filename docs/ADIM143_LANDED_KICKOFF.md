<!-- doc-status: current -->
# ADIM 143 landed — GH #536 md. 2 tamamlandı (`logic:<block_id>` motor düzleminde precedence yarışması + okunmayan sayaç)

## Nerede olduğumuz

Taban `origin/main` @ `6fec0e51` (ADIM 142). Bu slice **yalnız test** sevk etti:
`backend/src`'te **sıfır satır**, migration yok, `ENGINE_VERSION` değişmedi, golden el
değmedi, OpenAPI değişmedi, `frontend/src` sıfır satır. Toplanan test **3898 → 3901**
(statik, yalnız fonksiyon; modül düzeyinde 11 → 16 case).
**Blocker DEĞİŞMEDİ (1 — yalnız A-08) → RC verdict BLOCKED.**

ADIM 142 kendi docstring'ine bir HONEST BOUNDARY yazmıştı (*"motor düzleminde custom bir
priority order üzerinden `logic:<block_id>` sürmek burada kapsanmadı"*). Bu slice onu kapattı.

## Bu slice'ın bıraktığı çapalar (tam sembol adlarıyla)

Hepsi `backend/tests/unit/test_conflict_policy_coverage.py` içinde:

- `_logic_stop_plan()` — paylaşılan giriş planının **`replace`** türevi (F-24: her motor
  fixture'ı aynı `ta.sma` girişini sürer), tek farkı bir stop bloğu pinlemesi.
  **`length=3` geometriye karşı seçildi** ve gerekçesi docstring'de: 20 düz barda MA düz
  fiyatta durur ve kesişmez; breakout barı MA'nın **üstünde** kapanır (`long` — long
  pozisyona ters değil); düşüş barı 95 / MA 99 → **aşağı kesişir** = ters sinyal.
  (2, 3, 5 ölçüldü, üçü aynı.) **`_config`'i GENİŞLETME**, `_patched` idiomunu kullan.
- `_priority_config(order, *, requirement="any_active")` — **`priority_order`** çözünürlüğü
  set eder. Varsayılan `most_conservative` altında sıra yalnız **tie-break**'tir; onu
  bırakan bir test precedence'ı değil **mesafeyi** ölçerdi.
- `_PRIORITY_CONTESTS` — `null` / logic-önde / percentage-önde → (executed, exit).
  Ölçülmüş sayılar: **95.00** ya da **100.98**.
- `test_a_logic_block_takes_its_place_in_the_stop_priority_order_that_governed` (×3)
- `test_the_logic_stop_trigger_counter_counts_a_real_engine_firing`
- `test_the_stop_resolution_event_names_all_active_as_the_requirement_that_governed`

Sevk edilmiş taraf (**dokunulmadı**): `execution/fills.py::stop_priority_sequence` ·
`engine.py`'nin `logic_enabled` / `_emit_stop_resolution`'ı · `execution/output.py`'nin
`stop_priority_order{,_resolved}` ve `logic_stop_{blocks,triggers}` anahtarları.

## Ölçülmüş ve KAPATILMAYAN

- **#536 AÇIK.** md. 2 tamamlandı; **md. 4 (Gap C) kapsam dışı** (tasarım kararı).
- **Yarışma yalnız `priority_order` altında sürüldü.** Bir logic bloğunun
  **`most_conservative`** (sıra = tie-break) veya **`first_trigger_wins`** altında yarışması
  **KAPSANMADI** — sıradaki doğal KOD kalemi budur.
- **`record_all_execute_highest` hâlâ ikiz olarak PİNLİ, DÜZELTİLMEDİ** (ürün kararı).
- **Şema prozası düzeltilmedi** (adjudication).
- **`integration/test_logic_based_stop.py` ve `test_backtest_logic_stop.py` EL DEĞMEDİ.**
- **Frontend kapıları koşulmadı** (frontend'de sıfır satır).
- **A-08 (#514) AÇIK** — tek blocker, `human-only`.

## Çalışma yöntemi (bu slice'ta işe yarayanlar)

- **Devir notunun "yok" dediği şeyi ağaçta ara.** *"Motor düzleminde logic-stop fixture'ı
  YOK"* harfi harfine yanlıştı (integration'da bir tane **var**); taşıyıcı ayrım
  **ULAŞMAK ≠ ATEŞLEMEK** idi. Öncülü çürütmek, doğru testi yazmanın ön koşuluydu.
- **Yayımlanan ama okunmayan alanı `grep` ile ara.** `logic_stop_triggers`'ın üç yazma/
  yayımlama/toplama yeri vardı ve `backend/tests`'te **sıfır** okuyucusu.
- **Bir NC yalnız kırmızı verdiği için kabul edilmez — KAPSAMINI oku.** NC-1 kırmızıydı ama
  **iki mevcut testi de** düşürdü ⇒ boşluğu ölçmüyordu; **reddedildi** ve
  `logic:`-anahtarına özgü NC-1′ ile değiştirildi (**1 kırmızı, 72 yeşil**).
- **Gölgeyi kaydetmekle yetinme, KALDIRMAYI dene** (ADIM 101). NC-5 üyeliği koruyup sırayı
  ters çevirdi → `sorted()` geçti, hedef assertion **`:478`'de** düştü; **satır okundu**,
  çıkarımla yetinilmedi.
- **NC turundan sonra ağacı git ile geri al VE `__pycache__`'i temizle** (ADIM 141);
  her turda `git status --porcelain backend/src` boş doğrulandı.
- **Üretilmiş artefaktları tazeledikten sonra DELTA'yı oku** (ADIM 139): tek satır
  `3898 → 3901`, dosya sayısı sabit ⇒ main temizdi, yabancı drift absorbe edilmedi.

## Paste-ready resume prompt

```
ENTROPIA — ÖNCE ADIM 143'ÜN PR'ININ İNİP İNMEDİĞİNİ ÖLÇ, SONRA SIRADAKİ KALEMİ SEÇ.

ÖNCE DOĞRULA (bu prompt BAYAT VARSAYILIR):
  git fetch && git log --oneline origin/main -4 && gh pr list --state open
  grep -n '^## ADIM' docs/PROJECT_HISTORY.md | tail -2
  grep -c '☐' docs/decisions/closure_i703_instrument_mapping_writer_2026-08-30.md
  grep -c '\[ \]' docs/decisions/closure_i534_same_candle_suppression_counter_2026-08-29.md
  grep -c '☐'    docs/decisions/closure_i854_external_import_pin_stability_2026-08-28.md
  gh issue view 536 --json state && gh issue view 514 --json state

NOT: karar belgeleri FARKLI kutu işareti kullanır (#534 -> "[ ]", #703/#854 -> "☐").
Tek grep hepsini ölçmez; her birini kutu kutu oku. Kapalı issue != verilmiş karar (ADIM 90):
kapanış yorumu YOKSA ve imza kutusu BOŞSA kalem AÇIKTIR.

DURUM: ADIM 143 GH #536'nın md. 2'sini TAMAMLADI — motor düzleminde bir logic-stop fixture'ı
kurdu, logic:<block_id>'yi custom bir stop_priority_order yarışmasına soktu (exit 95.00 vs
100.98 = gerçek para), ve logic_stop_triggers'ı ilk kez okudu (yayımlanan + portföye toplanan
bir sayaçtı, SIFIR assertion'ı vardı). backend/src'te sıfır satır. #536 KAPATILMADI.
PR açıksa yeni slice AÇMA; inmişse ADIM 144.

SIRADAKİ KALEM — DÖRDÜ İMZA, İKİSİ KOD, BİRİ BLOCKER:

(1) #703 instrument_mapping_ref yazıcısı (İMZA) — üç karar / on bir kutu, hepsi BOŞ.
(2) #854 dış import pin'i (İMZA) — dokuz kutu, dokuzu BOŞ.
(3) #534 AYRIŞMA (İMZA) — issue CLOSED, kapanış yorumu YOK, dört kutu BOŞ -> md. 3 açık.
(4) #536'nın kalanı:
    - md. 4 (Gap C guard) = TASARIM kararı;
    - record_all_execute_highest'ın şema vaadi ayırt edici değil = ÜRÜN kararı;
    - KOD (imzasız yapılabilir): bir logic bloğunun `most_conservative` (sıra yalnız
      tie-break) ve `first_trigger_wins` altında yarışması. ADIM 143 yalnız
      `priority_order`'ı sürdü; fixture hazır (_logic_stop_plan / _priority_config).
(5) #677 Lighthouse dört donmuş eksik (KOD) — Compose + Lighthouse koşabilen ortam ister.
(6) A-08 (#514) — TEK BLOCKER, human-only. Çıkış kriterleri 0/4 -> KAPATILMAMALI.

KURALLAR: her iddiayı ampirik doğrula; devir notunun "yok" dediğini ağaçta ARA (ADIM 143'te
"fixture yok" yanlış çıktı — ULAŞMAK != ATEŞLEMEK); bir NC yalnız kırmızı verdiği için kabul
edilmez, KAPSAMINI oku; sayı taşıma, yeniden ölç; kapatmadığını covered İŞARETLEME; izole DB
(TEST_DATABASE_URL, asyncpg); NC sonrası bayat bytecode'u da temizle; üretilmiş artefaktları
tazele ve DELTA'yı oku; kapanış ritüeli ZORUNLU.
```
