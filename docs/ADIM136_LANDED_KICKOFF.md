<!-- doc-status: historical -->

# ADIM 136 — GH #532: `entry_exit_collision` taksonomiye kaydedildi + eksik anti-drift muhafızı

**Taban:** `origin/main` @ `3d94c4c0`. **PR:** (bu slice). Migration **yok** ·
**`ENGINE_VERSION` DEĞİŞTİ** → `backtest-engine-v18-entry-exit-collision-registered` ·
golden **yeniden üretildi (46/50)** · OpenAPI **değişmedi** · `frontend/src` **sıfır satır** ·
blocker **DEĞİŞMEDİ (1 — A-08)**, verdict **BLOCKED**.

## Nerede duruyoruz

Oturum **#854** ile açıldı. İlk iş imzayı ölçmekti: karar belgesinde **dokuz kutu, dokuzu da
BOŞ**, dosya ADIM 134'ten beri el değmemiş → durdurma koşulu uygulandı, **kod yazılmadı**.
#854 **açık**, `G15`/Karar 4 **konusuz bırakılmadı**. Bunun yerine ölçülmüş adaylardan en dar
kapsamlısı (#532) alındı — #534 içinde bir *"açıkça karar ver"* maddesi (adjudication riski),
#703 daha büyük.

`entry_exit_collision` PR #513'ten beri yayılıyordu ve yayımlanan taksonomi onu **yalanlıyordu**.
Artık kayıtlı, ve bir daha aynı şeklin olmaması **iki eksenle** zorlanıyor.

## Bu slice'ın bıraktığı çapalar (tam sembol adlarıyla)

- `execution/output.py::DECISION_TRACE_EVENT_TYPES` — artık `entry_exit_collision` üyesi var
  (21 → 22 üye). Kardeş taksonomi `execution/state.py::FILTERED_EVENT_TYPES`; **hedef küme
  ikisinin birleşimidir**.
- `tests/unit/test_backtest_decision_trace.py::test_every_emitted_event_type_is_published_in_the_taxonomy`
  — eksen 1 (davranışsal). Kaynağı `_representative_outputs()`: golden matrisi **+** golden'ın
  hiç sürmediği çarpışma senaryosu.
- `…::test_every_event_type_literal_in_the_engine_source_is_published` — eksen 2
  (kaynak-düzeyi), tarayıcısı `_literal_event_types_in_source()`. **Fixture gerekmeden** drift
  yakalar.
- `domain/backtest/manifest.py::ENGINE_VERSION` — bump'ın **gerekçesi sabitin üstünde yazılı**
  (neden bir sayı oynamadığı hâlde gerekli olduğu dahil).

## Pazarlıksız — bir sonraki okuyucu için

1. **Yeni bir decision-trace olayı eklerken taksonomiye KAYDET.** Eksen 2 seni fixture olmadan
   yakalar; assertion'ı daraltma, üyeyi ekle.
2. **Taksonomiye üye eklemek 45 golden digest'i oynatır** (taksonomi 45 senaryonun
   payload'ında). Bu bir regresyon değil, yapının sonucudur — ama **golden'ı körlemesine
   yeniden üretme**: önce payload'ları dondur, deltanın *yalnız* eklenen üye olduğunu kanıtla.
   Bu slice'ın betikleri `/tmp` idi; şeklini kayıttan (`§ADIM 136`) oku.
3. **Bump'ın gerekçesi "bir sayı oynadı" DEĞİL.** `execution_key` artefaktın **baytlarını**
   anahtarlar. Diagnostics'i değiştiren bir sürüm bump'sız çıkarsa aynı anahtarlı iki koşu
   farklı bayt yayımlar.
4. **Eksen 2 değişken-değerli event type'ları GÖREMEZ** (üç site, üçü de ileri taşıyıcı —
   ölçüldü). Yeni bir emit yüzeyi literal olmayan bir tip üretirse muhafız sessiz kalır.

## Açık kalanlar (bu slice kapatmadı, iddia da etmiyor)

- **#532 kapatılmadı** — issue'nun 3 maddesi karşılandı ama kapatma **insan kararı**.
- **#534 el değmedi** (kardeş kusur: `same_candle_entry_exit` + `stop_priority_order`
  provenance bloğunda yok). Bu slice'ın taksonomi üyesi onu **çözmez**.
- **#854 el değmedi, imza bekliyor** (dokuz boş kutu). **#703 el değmedi.**
- **A-08 (#514) el değmedi** → tek blocker odur, RC verdict **BLOCKED**.
- **Eksen 1, yayımlanan 22 tipin 14'ünü sürüyor**; 8'i hiçbir temsili senaryoda koşmuyor
  (`exit_scheduled`, `filtered_no_entry`, `partial_fill`, `position_partial_close`,
  `scale_layer_added`, `scale_layer_rejected`, `stack_entry_added`, `stack_entry_rejected`).
- **YENİ KALEM (ölçüldü, kapatılmadı):** unified-clock **kompozit** Result'ı bir decision
  trace yayımlıyor ama sözcük dağarcığını hiç bildirmiyor — olayları `IntentKind`
  (`entry`/`scale_in`/`exit`/`partial_exit`/`no_op`/`blocked`, **altısının sıfırı**
  decision-trace taksonomisinde) ve `diagnostics`'inde `decision_trace_event_types` **yok**
  (yalnız `decision_trace_count`). #532'nin kusuru DEĞİL (orada yalan bir reklam vardı,
  burada reklam hiç yok) ama tek-item Result'ının sahip olduğu şey kompozitte eksik.
  Doldurmak bir **ürün kararıdır** — kompozit kendi listesini mi yayımlamalı, yoksa iki
  artefakt bilerek mi ayrı.
- **BULGU, düzeltilmedi:** `test_oracle_portfolio_containment_gate.py`'nin ikinci-bump
  muhafızındaki *"Today the flag is down"* yorumu C9'dan beri karşı-olgusal.
- **A13 partition testinin** *"bir bump yalnız `portfolio.*`'ı oynatabilir"* cümlesi **C9
  lift'i için** yazılmıştı; bu bump 41 non-portfolio digest'i de oynattı, test grup
  **boyutlarını** pinlediği için yeşil kaldı. Test **değiştirilmedi**.
- Frontend kapıları **koşulmadı** (sıfır satır); geçen sayı ve coverage **CI'ın otoritesinde**.

## Paste-ready resume prompt

```
ENTROPIA — SIRADAKİ KALEM KOD DEĞİL, İKİ İMZA HATTI.

ÖNCE DOĞRULA (bu prompt BAYAT VARSAYILIR):
  git fetch && git log --oneline origin/main -4 && gh pr list --state open
  grep -n '^## ADIM' docs/PROJECT_HISTORY.md | tail -2
  grep -c '☑' docs/decisions/closure_i854_external_import_pin_stability_2026-08-28.md

(1) #854 — dış import pin'i taşınıyor. Karar belgesinde DOKUZ kutu (Karar 1: (a)…(e) +
    "Başka"; Karar 2: A/B/C). ADIM 136'da ölçüldü: dokuzu da BOŞ. Kutu doluysa şıkka göre
    DÖRT çağrı yerini birden değiştir (link_batch_to_revision + link_normalized_to_revision,
    her biri create + revision); test_external_import_pin_stability.py'nin iki case'i
    KIRMIZI olur, kasıtlı güncelle. Kutu boşsa DUR — varsayılan seçme, #854'ü kapatma.

(2) A-08 (#514) — tek blocker. human-only; agent ne açar ne kapatır.

KOD KALEMİ İSTİYORSAN ölçülmüş adaylar: #534 (same_candle_entry_exit + stop_priority_order
provenance bloğunda yok — DİKKAT: 3. maddesi "açıkça karar ver" diyor, o bir adjudication)
· #703 (native_asset_id hiç yazılmıyor).

#534'e girersen ADIM 136'nın ölçümünü devral: diagnostics bloğuna alan eklemek 45 golden
digest'ini oynatır ve ürün sahibi bu sınıf için "bump et"i imzaladı (2026-08-29). Golden'ı
körlemesine yeniden üretme — önce payload'ları dondur, deltanın YALNIZ eklenen alan
olduğunu bayt düzeyinde kanıtla, sonra bump + regenerate.

KURALLAR: her iddiayı ampirik doğrula; sayı taşıma, yeniden ölç; kapatmadığını covered
İŞARETLEME; kapanış ritüeli ZORUNLU.
```
