<!-- doc-status: historical -->
# ADIM 142 landed — GH #536 md. 2 (politika echo'su iki düzlemde pinlendi + `record_all` ikiz tripwire'ı)

## Nerede olduğumuz

Taban `origin/main` @ `17bb495f` (ADIM 141). Bu slice **yalnız test** sevk etti:
`backend/src`'te **sıfır satır**, migration yok, `ENGINE_VERSION` değişmedi, golden el
değmedi, OpenAPI değişmedi, `frontend/src` sıfır satır. Toplanan test **3895 → 3898**
(statik, yalnız fonksiyon; modül düzeyinde 5 → 11 case).
**Blocker DEĞİŞMEDİ (1 — yalnız A-08) → RC verdict BLOCKED.**

ADIM 141'in kaydı #536 md. 2'yi açıkça borç bırakmıştı (*"yazılmadı — test işidir, imzasız
yapılabilir"*). Bu slice o borcun **ayakta kalan yarısını** kapattı; iki yarısı ölçümde
çürüdü (aşağıda).

## Bu slice'ın bıraktığı çapalar (tam sembol adlarıyla)

- `tests/unit/test_conflict_policy_coverage.py::_STOP_RESOLUTIONS` — literal → (executed
  rule, exit price, `first_trigger_approximated`). **Ölçülmüş sayılar**, tahmin değil.
- `…::_two_stop_config` — `_config()` + `_patched` ile ikinci (çakışan) absolute stop.
  **`_config`'i GENİŞLETME**: sekiz modülün paylaştığı fixture'dır; `_patched`
  (`tests/unit/test_backtest_policy_provenance.py`) bu iş için zaten var.
- `…::_stop_fingerprint` — echo'yu **İKİ düzlemden de** sıyırır. ADIM 141'in `_fingerprint`'i
  bu soruyu **cevaplayamaz** (gerekçe docstring'inde; aşağıda da).
- `…::test_the_stop_conflict_resolution_that_governed_is_published_per_literal` (×4)
- `…::test_the_four_stop_conflict_resolutions_are_covered_by_a_case_between_them`
- `…::test_record_all_execute_highest_is_a_deliberate_twin_of_priority_order`

Sevk edilmiş taraf (dokunulmadı): `execution/output.py`'nin
`"stop_conflict_resolution"` anahtarı · `engine.py`'nin `stop_resolution` event `detail`'i
(`resolution` / `requirement` / `executed` / `triggered`) · `execution/fills.py`'nin
paylaşılan `("priority_order", "record_all_execute_highest")` dalı.

## Ölçülmüş ve KAPATILMAYAN

- **#536 AÇIK.** Sevk edilen md. 2'nin echo yarısı. **Md. 4 (Gap C guard) kapsam dışı**
  (tasarım kararı, ADIM 141'in gerekçesi geçerli).
- **`logic:<block_id>`'nin MOTOR düzlemi kapsanmadı** — motor seviyesinde logic-stop
  fixture'ı **yok** (`test_backtest_logic_stop`'un motor case'leri `logic_stop_blocks == 0`).
  Kendi başına bir fixture slice'ı. Sınır modül docstring'inde yazılı.
- **`record_all_execute_highest` bulgusu: KAYDEDİLDİ + PİNLENDİ, DÜZELTİLMEDİ.** Literalin
  `backend/src`'teki tamamı **dört hit**; `priority_order` ile **bayt bayt aynı** koşu
  üretir. Şemanın *"records every co-triggered rule in the ledger"* vaadi dört literalin
  dördü tarafından karşılanır → hiçbirini ayırt etmez. Düzeltmek **ürün kararı** (gerçek bir
  etki ver, ya da literali kaldır = saklanan config'leri kırar). **Dördüncü bir imzasız
  karar belgesi AÇILMADI** (ADIM 141 emsali).
- **Şema prozası düzeltilmedi** — yeniden yazmak adjudication'dır (ADIM 42/128).
- **Frontend kapıları koşulmadı** (frontend'de sıfır satır).
- **A-08 (#514) AÇIK** — tek blocker, `human-only`.

## Çalışma yöntemi (bu slice'ta işe yarayanlar)

- **Öncülü issue'dan okuma, ağaçtan ölç.** Md. 2'nin üç yarısından **ikisi çürümüştü**
  (`most_conservative` zaten açıkça set ediliyordu; `logic:` ADIM 137'de kapanmıştı;
  `all_active` diagnostics'ten assert ediliyordu). Ayakta kalan tek şey **echo**'ydu.
- **Bir echo'nun KAÇ düzlemde yayımlandığını say.** Buradaki iki taneydi ve ADIM 141'in
  fingerprint yardımcısı yalnız birini sıyırıyordu → olduğu gibi kullanmak tripwire'ı
  **doğuştan tatmin edilemez** yapardı (ölçüldü: dört ayrı fingerprint).
- **"Mevcut test bunu göremez" iddiasını NC ile ÖLÇ.** NC-3'te literal dalından düşürüldü ve
  adı *"records every triggered rule"* olan mevcut test **yeşil kaldı**.
- **NC turundan sonra ağacı git ile geri al, `git status --porcelain src` boş mu bak ve
  bayat bytecode'u temizle** (ADIM 141'de sahte kırmızı üretmişti).
- **Karar kutularını BÖLÜM bazında say ve işaretin biçimini kontrol et** — #534 `[ ]`,
  #703/#854 `☐` kullanır; tek grep üçünü birden ölçmez.
- **Kapalı bir issue kapanmış karar demek değildir (ADIM 90).** #534 `CLOSED/COMPLETED` ama
  kapanış yorumu yok ve imza kutuları boş → otorite **imza kutusudur**.

## Paste-ready resume prompt

```
ENTROPIA — ÖNCE ADIM 142'NİN PR'ININ İNİP İNMEDİĞİNİ ÖLÇ, SONRA SIRADAKİ KALEMİ SEÇ.

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

DURUM: ADIM 142 GH #536'nın md. 2'sinin echo yarısını sevk etti (diagnostics + event
düzlemleri, per literal) ve record_all_execute_highest'ın priority_order ikizi olduğunu
ölçüp TRIPWIRE ile pinledi. backend/src'te sıfır satır. #536 KAPATILMADI.
PR açıksa yeni slice AÇMA; inmişse ADIM 143.

SIRADAKİ KALEM — DÖRDÜ İMZA, İKİSİ KOD, BİRİ BLOCKER:

(1) #703 instrument_mapping_ref yazıcısı (İMZA) — üç karar / on bir kutu, hepsi BOŞ.
(2) #854 dış import pin'i (İMZA) — dokuz kutu, dokuzu BOŞ.
(3) #534 AYRIŞMA (İMZA) — issue CLOSED, kapanış yorumu YOK, dört kutu BOŞ -> md. 3 açık.
(4) #536'nın kalanı (İMZA/TASARIM) — md. 4 (Gap C guard) bir tasarım kararı; ayrıca
    record_all'ın şema vaadi ("records every co-triggered rule in the ledger") ayırt edici
    DEĞİL: ya literale gerçek etki verilir ya kaldırılır (ikincisi saklanan config'leri
    kırar) = ÜRÜN KARARI. ADIM 142 bunu tripwire ile pinledi, DÜZELTMEDİ.
(5) #536 md. 2'nin kalan yarısı (KOD) — logic:<block_id> girdisini MOTOR düzleminde bir
    custom stop_priority_order ile sür. Motor seviyesinde logic-stop fixture'ı YOK; onu
    kurmak bu slice'ın işidir (test_backtest_logic_stop'un motor case'leri
    logic_stop_blocks == 0 ile koşar).
(6) #677 Lighthouse dört donmuş eksik (KOD) — Compose + Lighthouse koşabilen ortam ister.
(7) A-08 (#514) — TEK BLOCKER, human-only. Çıkış kriterleri 0/4 -> KAPATILMAMALI.

KURALLAR: her iddiayı ampirik doğrula; sayı taşıma, yeniden ölç; kapatmadığını covered
İŞARETLEME; izole DB (TEST_DATABASE_URL, asyncpg); NC sonrası bayat bytecode'u da temizle;
üretilmiş artefaktları tazele (scripts/generate_repository_facts.py --check CI'da bloklar);
kapanış ritüeli ZORUNLU.
```
