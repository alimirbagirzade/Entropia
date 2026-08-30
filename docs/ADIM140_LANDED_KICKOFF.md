<!-- doc-status: historical -->
# ADIM 140 landed — GH #703'ün İKİNCİ kapısı ölçüldü, karar açıldı (kod YOK)

## Nerede olduğumuz

`origin/main` @ `7f2d8317` (ADIM 138) üzerine inen slice. **`backend/src`'te sıfır satır**;
diff bir yeni integration test dosyası (3 case), bir yeni karar belgesi (11 boş kutu) ve
kapanış belgeleridir. Migration **yok** · `ENGINE_VERSION` **değişmedi** · golden **el
değmedi** · OpenAPI **değişmedi** · `frontend/src` **sıfır satır**.
**Blocker DEĞİŞMEDİ (1 — A-08), verdict BLOCKED.**

## Bu slice'ın bıraktığı çapalar (tam sembol adlarıyla)

| Çapa | Nerede | Ne için |
|---|---|---|
| `test_readiness_research_production_shape.py` | `backend/tests/integration/` | GH #703'ün ikinci kapısı, **Ready Check düzleminde**, üretim yolunda |
| `::test_an_application_created_research_revision_is_blocked_by_ready_check` | aynı dosya | gerçek pipeline → `not_ready` + `INSTRUMENT_MAPPING_INVALID` |
| `::test_the_blocked_revision_is_refused_admission_and_leaves_nothing_behind` | aynı dosya | admission refüzü; `Job` **delta** ile ölçülür (pipeline kendi analysis job'ını yazar) |
| `::test_the_hand_seeded_revision_shape_never_reaches_the_mapping_gate` | aynı dosya | **ayrışma ölçümü** — harness şekli kapıyı hiç görmez |
| `_production_funding_revision` | aynı dosya | `_analysed_funding_revision` + `_approve` üzerine kurulu; yeni kullanıcıya hazır |
| `_composition_pinning(...)` | aynı dosya | market pin'i research link'iyle **hizalar** → `DEPENDENCY_BLOCKED` karışmaz |
| `closure_i703_instrument_mapping_writer_2026-08-30.md` | `docs/decisions/` | **üç karar, on bir kutu, hepsi BOŞ** |

**Yeniden kullanım:** `_analysed_funding_revision` / `_approve`
(`test_research_native_asset_pointer.py`, ADIM 138) · `_empty_composition` /
`_strategy_payload` / `_seed_market_revision` / `_seed_principals`
(`test_readiness_persistence.py`) · `_seed_research_revision`
(`test_readiness_research_data.py`).

## Ölçülmüş ve KAPATILMAYAN

- **#703 açık, kusur düzeltilmedi.** Yazıcı bir ürün kararıdır; kutular boş.
- **`RD-09.c4`** `partial` kalır; kabul borcu defterine ve tavanlara **dokunulmadı**.
- **Harness değiştirilmedi** — NC-3 bedelini ölçtü (mevcut suite'in **iki** testi kırılır),
  imza `§Karar 2`'de bekliyor.
- **`quality_rules._check_instrument_mapping` (WARNING düzlemi)** ele alınmadı.
- **Frontend kapıları koşulmadı** (frontend'de sıfır satır).
- **Üretimde kaç revizyonun etkilendiği sayılmadı** ve **ikame edilmedi**.

## Çalışma yöntemi (bu slice'ta işe yarayanlar)

1. **İki karar belgesini kutu kutu oku.** `#534` `[ ]`, `#854` `☐` kullanır — tek bir grep
   ikisini birden ölçmez ve "imza yok" ile "işaret farklı"yı ayırt etmez.
2. **Bir predicate'in kaç düzlemde okunduğunu say.** Burada iki düzlem vardı ve bir öncekinin
   pinlediği düzlem, kullanıcının önce çarptığı düzlem **değildi**.
3. **Fixture'ın YAPMADIĞINI da oku.** Eksik bir atama bir iddiayı yanlışlanamaz kılmakla
   kalmaz, **tersine çevirebilir**.
4. **NC'yi bellekteki anlık görüntüden geri yaz** (`git checkout` değil, ADIM 111) ve her
   turdan sonra `git status`.
5. **Bir sayacın ayırt edici olduğunu varsayma.** `Job == 0` burada yanlıştı: üretim
   pipeline'ı kendi job'ını yazar → **delta** ölç.

## Paste-ready resume prompt

```
ENTROPIA — ÖNCE ADIM 140'IN PR'ININ İNİP İNMEDİĞİNİ ÖLÇ, SONRA SIRADAKİ KALEMİ SEÇ.

ÖNCE DOĞRULA (bu prompt BAYAT VARSAYILIR):
  git fetch && git log --oneline origin/main -4 && gh pr list --state open
  grep -n '^## ADIM' docs/PROJECT_HISTORY.md | tail -2
  grep -c '☐' docs/decisions/closure_i703_instrument_mapping_writer_2026-08-30.md
  grep -c '\[ \]' docs/decisions/closure_i534_same_candle_suppression_counter_2026-08-29.md
  grep -c '☐'    docs/decisions/closure_i854_external_import_pin_stability_2026-08-28.md
  gh issue view 703 --json state

NOT: karar belgeleri FARKLI kutu işareti kullanıyor (#534 -> "[ ]", #703/#854 -> "☐").
Tek bir grep hepsini ölçmez; her birini kutu kutu oku.

DURUM: ADIM 140 GH #703'ün İKİNCİ kapısını (instrument_mapping_ref) Ready Check düzleminde
ölçtü ve koşulur kıldı; DÜZELTMEDİ. backend/src'te sıfır satır. PR hâlâ AÇIKSA yeni slice
AÇMA. İNMİŞSE numara ADIM 141'dir; ölç, varsayma.

SIRADAKİ KALEM — DÖRDÜ İMZA, İKİSİ KOD, BİRİ BLOCKER:

(1) #703 — instrument_mapping_ref'i kim yazar? YENİ karar belgesi, ÜÇ karar / ON BİR kutu,
    hepsi BOŞ. Seçenekler ÖLÇÜLMÜŞ: (a) statüko · (b) link'ten türet — fail-open riski
    ölçüldü (MarketDatasetRevision.instrument_id de nullable ve yazıcısı koşullu) ·
    (c) Market Data desenini aynala — emsal AYNI REPODA sevk edilmiş (instrument_scope ->
    resolve_scope_id -> fail-closed 422) · (d) predicate'i gevşet — NC-1 bedelini ölçtü.
    §Karar 2 harness'ın kaderini sorar (NC-3: seeder'a link eklemek mevcut suite'in İKİ
    testini kırar). §Karar 3 RD-09.c4'ü bu karara bağlar. Kutu boşsa DUR, varsayılan seçme.

(2) #534 md. 3 — same-candle sayacı. DÖRT kutu, dördü BOŞ. Kutu boşsa DUR.

(3) #854 — dış import pin'i TAŞINIYOR. DOKUZ kutu, dokuzu BOŞ. Kutu boşsa DUR.

(4) Composite Result'ın provenance'ı (KOD, ama önce issue + imza) — ADIM 136/137'den devir.

(5) ADR-0002 §13.1'in OD-2 satırı + üç bayat docstring (İMZA/adjudication, ADIM 136'dan devir).

(6) RD-09.c4 (KOD) — (1) çözülmeden kapatmak mapping'i fixture'da elle set etmek olur =
    #703'ün kör noktasının tekrarı. Sınır test_readiness_research_production_shape.py ve
    test_research_native_asset_pointer.py içinde PİNLİ; kırmızıya dönerse testi düzeltip
    geçme, kaydı güncelle.

(7) A-08 (#514) — TEK BLOCKER, human-only, repo içinden KAPATILAMAZ.

KURALLAR: her iddiayı ampirik doğrula; sayı taşıma, yeniden ölç; kapatmadığını covered
İŞARETLEME; izole DB kullan (TEST_DATABASE_URL, asyncpg); kapanış ritüeli ZORUNLU.
```
