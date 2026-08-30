<!-- doc-status: historical -->
# ADIM 141 landed — GH #536 Gap A + Gap B (sevk edilen conflict literalleri ilk kez sürüldü)

## Nerede olduğumuz

`origin/main` @ `31593c79` (ADIM 140) üzerine inen slice. **`backend/src`'te sıfır satır**;
diff bir yeni unit test dosyası (5 case) + `test_backtest_engine.py::_config`'e opsiyonel bir
parametre + kapanış belgeleridir. Migration **yok** · `ENGINE_VERSION` **değişmedi** · golden
**el değmedi** · OpenAPI **değişmedi**. **Blocker DEĞİŞMEDİ (1 — A-08), verdict BLOCKED.**

## Bu slice'ın bıraktığı çapalar (tam sembol adlarıyla)

| Çapa | Nerede | Ne için |
|---|---|---|
| `test_conflict_policy_coverage.py` | `backend/tests/unit/` | GH #536 Gap A + Gap B |
| `::test_the_untested_same_candle_policies_suppress_the_entry_and_name_themselves` | aynı dosya | üç literal (parametrik): bastırır **ve** kendi `policy`'sini adlandırır |
| `::test_the_five_same_candle_literals_are_covered_by_a_case_between_them` | aynı dosya | anti-drift: yeni bir literal sıfır case'le gelemez |
| `::test_every_overlapping_signal_policy_produces_an_identical_run` | aynı dosya | Gap A tripwire'ı — vacuity **kasıtlı** ve pinli |
| `_fingerprint(out)` | aynı dosya | `diagnostics` **bilerek dışarıda** (alan orada echo'lanıyor → dahil etmek testi vacuous yapardı) |
| `_config(..., overlapping_signal_policy=None)` | `test_backtest_engine.py` | opsiyonel; varsayılan çağrılar bayt bayt aynı |

**Yeniden kullanım:** `_config` / `_run` / `_long_breakout_then_stop` /
`_same_candle_entry_exit_plan` (`test_backtest_engine.py`).

## Ölçülmüş ve KAPATILMAYAN

- **#536 açık.** Sevk edilen: issue md. 1 + md. 3. **Md. 2 yazılmadı**
  (`stop_conflict_resolution` explicit + `stop_priority_order` `logic:<block_id>` +
  `stop_resolution` event assertion'ları) — **test işidir, imzasız yapılabilir**.
- **Md. 4 (Gap C) kapsam dışı, gerekçesi ölçüldü:** `_SCHEMA_FIELDS` bugün **14 alan**
  (ADIM 139 9→14 yaptı), `ConflictPositionHandling`'in **beş** Literal alanından **biri
  guard'da, dördü dışarıda**. Kalanları eklemek her literal için matris satırı ister ve her
  satır bir **sınıflandırma kararıdır**.
- **Gap A'nın disclosure yarısı sevk edilmedi** — diagnostics ifadesini değiştirmek golden'ı
  oynatır + `ENGINE_VERSION` bump ister (ADIM 136'nın imzalı ekseni) → kapsam kararı.
- **#677 alınmadı** — kabul kriteri düzeltme + tavan sıkılaştırmasını **birlikte** ister,
  Lighthouse Compose stack'i bu ortamda koşulamıyor → kanıtsız kalırdı.

## Çalışma yöntemi (bu slice'ta işe yarayanlar)

1. **Issue'nun sayısını yeniden ölç.** *"Six fields"* bugün dört; aradaki farkı bir başka
   slice (ADIM 139) kapatmıştı.
2. **Bir "hiçbir şey yapmıyor" iddiasını pinlerken vacuity guard'ı koy** — dört boş koşu da
   özdeştir; `total_trades >= 1` olmadan test hiçbir şey ölçmez.
3. **Fingerprint'ten echo alanını çıkar.** Alan diagnostics'te echo'lanıyorsa onu hash'e
   katmak her değeri trivially farklı yapar.
4. **Bastırmayı assert etmek zayıf yarıdır** — literaller sessizce tek koda çökebilir; olayın
   `policy` alanını da pinle.
5. **NC sonrası `__pycache__`'i de geri al.** Ağaç temizken sahte kırmızı gördüysen bayat
   bytecode koşuyordur.

## Paste-ready resume prompt

```
ENTROPIA — ÖNCE ADIM 141'İN PR'ININ İNİP İNMEDİĞİNİ ÖLÇ, SONRA SIRADAKİ KALEMİ SEÇ.

ÖNCE DOĞRULA (bu prompt BAYAT VARSAYILIR):
  git fetch && git log --oneline origin/main -4 && gh pr list --state open
  grep -n '^## ADIM' docs/PROJECT_HISTORY.md | tail -2
  grep -c '☐' docs/decisions/closure_i703_instrument_mapping_writer_2026-08-30.md
  grep -c '\[ \]' docs/decisions/closure_i534_same_candle_suppression_counter_2026-08-29.md
  grep -c '☐'    docs/decisions/closure_i854_external_import_pin_stability_2026-08-28.md
  gh issue view 536 --json state && gh issue view 534 --json state

NOT: karar belgeleri FARKLI kutu işareti kullanıyor (#534 -> "[ ]", #703/#854 -> "☐").
Tek grep hepsini ölçmez; her birini kutu kutu oku.

DURUM: ADIM 141 GH #536'nın md. 1 + md. 3'ünü sevk etti (Gap B üç literal + Gap A tripwire).
backend/src'te sıfır satır. #536 KAPATILMADI. PR açıksa yeni slice AÇMA; inmişse ADIM 142.

SIRADAKİ KALEM — DÖRDÜ İMZA, ÜÇÜ KOD, BİRİ BLOCKER:

(1) #703 instrument_mapping_ref yazıcısı (İMZA) — üç karar / on bir kutu, hepsi BOŞ.
(2) #854 dış import pin'i (İMZA) — dokuz kutu, dokuzu BOŞ.
(3) #534 AYRIŞMA — issue CLOSED (kapanış yorumu YOK) ama karar belgesi current + dört kutu
    BOŞ. ADIM 90: otorite imza kutusudur -> md. 3 açık sayılır. Karar gerekiyor.
(4) #536'nın kalanı — md. 2 TEST İŞİDİR, İMZASIZ YAPILABİLİR (stop_conflict_resolution
    explicit + stop_priority_order logic:<block_id> + stop_resolution event). md. 4 (guard)
    bir tasarım kararı: ConflictPositionHandling'in dört alanı hâlâ _SCHEMA_FIELDS dışında.
(5) #677 Lighthouse dört donmuş eksik (KOD) — Compose + Lighthouse koşabilen ortam ister.
(6) Composite Result provenance (KOD, kapsamı karar) — combine_item_runs provenance almıyor.
(7) A-08 (#514) — TEK BLOCKER, human-only. Çıkış kriterleri 0/4, rota 0/46, akış 0/20,
    SR-1 hiç başlamadı -> KAPATILMAMALI.

KURALLAR: her iddiayı ampirik doğrula; sayı taşıma, yeniden ölç; kapatmadığını covered
İŞARETLEME; izole DB (TEST_DATABASE_URL, asyncpg); NC sonrası __pycache__'i de geri al;
kapanış ritüeli ZORUNLU.
```
