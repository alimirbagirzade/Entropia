<!-- doc-status: current -->

# ADIM 138 — GH #703'ün `native_asset_id` yarısı kapandı (LANDED KICKOFF)

> Bu belge ADIM 138'in kapanış handoff'udur. En altta **paste-ready resume prompt** var.

## Neredeyiz

`jobs/research_data.py::run_analysis` artık analiz ettiği revizyonu **yazdığı native
asset'e pinliyor** (`ResearchDatasetRevision.native_asset_id`). O alan sevk edilmiş bir
okuyucu tarafından dereference ediliyordu (`queries/funding.py:88` fail-closed guard, `:93`
deref) ama **hiçbir üretim satırı onu yazmıyordu** — `backend/src` ağacında bir bildirim +
iki okuma + **sıfır yazıcı**.

**Migration YOK** (kolon `0004_research_data.py:64`'te zaten vardı, nullable) ·
`ENGINE_VERSION` **değişmedi** · golden **el değmedi** · OpenAPI **değişmedi** ·
`queries/funding.py` **EL DEĞMEDİ** (okuma yolu değişmedi, artık yalnız beslenen bir alan
buluyor) · `frontend/src` **sıfır satır** · **blocker DEĞİŞMEDİ (1 — yalnız A-08), BLOCKED.**

## Bu slice'ın bıraktığı çapalar (tam sembol adlarıyla)

* `jobs/research_data.py::_WriteNative` — dönüş tipi artık `Awaitable[ResearchNativeAsset]`.
  **Bir digest DEĞİL, SATIR döndürür**; sebebi yorumda yazılı ve pazarlıksız (aşağıda).
* `jobs/research_data.py::_write_native` — `rd_repo.add_native_asset(...)`'ın dönüşünü
  **doğrudan** döndürür.
* `jobs/research_data.py::_advance_revision(revision, outcome, parsed, native_asset)` —
  pointer'ı **burada** yazar (`revision.native_asset_id = native_asset.asset_id`) ve digest'i
  satırdan okur (`native_asset.content_digest` — değer değişmedi, `manifest_hash` oynamadı).
* `tests/integration/test_research_native_asset_pointer.py` — üç case, hiçbiri pointer'a
  dokunmaz; `_analysed_funding_revision` gerçek komut zincirini sürer, `_approve` Admin-only
  komutundan geçer ve **PostgreSQL'den geri okur**.
* Dört mevcut fake (`test_research_validation_depth` · `test_research_revision_immutability` ·
  `test_worker_delivery_recovery` · `test_ingest_timezone_normalization`) artık
  `rd_repo.add_native_asset` çağırır — **yalnız S3 fake'lenir, DB fake'lenmez**.

## Pazarlıksız olanlar (bir sonraki oturum bunları BOZMASIN)

1. **Pointer'ı `_write_native`'e TAŞIMA.** O bir enjeksiyon seam'idir ve `write_native=` ile
   **her test onu değiştirir**; orada yazılan pointer'ı üretim değil **fake'ler** yazar, yani
   #703'ün görünmez kalma sebebi (*"fixture pointer'ı elle set ediyor"*) yeni bir kılıkta
   geri gelir. NC-1 bunu ölçer.
2. **Okuyucuyu `revision_id` ile aramaya ÇEVİRME.** `research_native_asset.revision_id`
   **UNIQUE DEĞİL** ve redelivery aynı revision için ikinci bir satır yazabilir
   (`run_analysis` docstring'i bunu kendisi söyler) → kazanan **tanımsız** olur. Bu `G15`'in
   birebir şeklidir = **ürün kararı**, temizlik değil.
3. **Fake'lerin `add_native_asset` çağrısını geri alma.** Seam'in sözleşmesi *"swap S3/Polars,
   keep the real DB"*; DB'yi de atlayan bir fake `get_native_asset`'i kör bırakır (NC-3).
4. **`test_research_native_asset_pointer.py`'de `native_asset_id` ATAMA.** Testin iddiası bir
   değer değil bir **provenance**'tır; elle atamak kanıtı yok eder.
5. Testlerde `session.expire_all()`'dan **önce** id'leri düz string olarak yakala — expire
   yüklü satırları detach eder ve sonrasında bir attribute okumak async testte senkron IO
   (`MissingGreenlet`) olur. `_approve` bunu yapıyor.

## Dürüst sınır

* **#703 KAPATILMADI.** Başlığındaki iddia (*"funding-enabled runs cannot use any Research
  revision created through the app"*) **hâlâ doğru**, çünkü ikinci bir kapı var:
  `instrument_mapping_ref` de üretimde **hiç yazılmıyor** (dört okuma, sıfır yazıcı), oysa
  `linked_market_dataset_revision_id` her app-created revizyonda yazılıyor
  (`create_research_dataset` `market_entity_id`'yi zorunlu kılar) →
  `instrument_mapping_is_valid`'in `has_link == has_ref`'i **False** →
  `build_funding_schedule` fail-closed. Bu **backlog R1**'dir, kapsam dışı bırakıldı,
  **testle pinlendi** (c2), **adjudicate edilmedi**.
* **Kabul defterine dokunulmadı.** `RD-09.c4` hâlâ `partial` — kriter funding-enabled bir
  **RUN** ister, bu slice bir **schedule**'a kadar gitti. Hiçbir tavan oynamadı.
* **Karar belgesi yazılmadı** (adjudication değil; seçenekler ölçüldü, reddedilen üçüncü yol
  `PROJECT_HISTORY.md` §ADIM 138'de kayıtlı).
* Frontend kapıları **koşulmadı**.

## Ölçüm yöntemi (tekrar keşfetme)

```bash
# yazıcı var mı — bu slice'ın öncülünü üreten tarama
grep -rn 'native_asset_id' backend/src            # 1 bildirim + 2 okuma + (artık) 1 yazıcı
grep -rn 'instrument_mapping_ref' backend/src     # HÂLÂ 4 okuma + 0 yazıcı (backlog R1)

# izole DB (paralel worktree oturumları aynı cluster'ı paylaşır)
export TEST_DATABASE_URL="postgresql+asyncpg://entropia:entropia@localhost:5432/entropia_a16_703"
cd backend && uv run pytest tests/integration/test_research_native_asset_pointer.py -q --no-cov
```

## Paste-ready resume prompt

```
ENTROPIA — ÖNCE ADIM 138'İN PR'ININ İNİP İNMEDİĞİNİ ÖLÇ, SONRA SIRADAKİ KALEMİ SEÇ.

ÖNCE DOĞRULA (bu prompt BAYAT VARSAYILIR):
  git fetch && git log --oneline origin/main -4 && gh pr list --state open
  grep -n '^## ADIM' docs/PROJECT_HISTORY.md | tail -2
  grep -c '\[ \]' docs/decisions/closure_i534_same_candle_suppression_counter_2026-08-29.md
  grep -c '☐'    docs/decisions/closure_i854_external_import_pin_stability_2026-08-28.md
  gh issue view 703 --json state

NOT: iki karar belgesi FARKLI kutu işareti kullanıyor (#534 -> "[ ]", #854 -> "☐").
Tek bir grep ikisini birden ölçmez; ikisini de kutu kutu oku.

DURUM: ADIM 138 GH #703'ün native_asset_id yarısını kapattı (jobs/research_data.py; migration
yok, ENGINE_VERSION değişmedi, golden el değmedi). #703 KAPATILMADI — başlığındaki iddia
ikinci bir kapı yüzünden ayakta. PR hâlâ AÇIKSA yeni slice AÇMA. İNMİŞSE numara ADIM 139'dur;
ölç, varsayma.

SIRADAKİ KALEM — İKİSİ İMZA, İKİSİ KOD, BİRİ BLOCKER:

(1) #534 md. 3 — same-candle bastırmaları kendi sayacını hak ediyor mu? DÖRT kutu, ADIM
    138'de ölçüldü: dördü de BOŞ. Kutu boşsa DUR, varsayılan seçme.

(2) #854 — dış import pin'i TAŞINIYOR. DOKUZ kutu, dokuzu da BOŞ. Kutu boşsa DUR.

(3) instrument_mapping_ref — #703'ün İKİZİ ve ADIM 138'de ÖLÇÜLDÜ: dört okuma, SIFIR yazıcı;
    linked_market_dataset_revision_id her app-created revizyonda yazıldığı için
    instrument_mapping_is_valid (has_link == has_ref) HER app-created revizyon için False ->
    build_funding_schedule fail-closed. Yani #703'ün başlığı hâlâ doğru. Bu backlog R1'dir ve
    bir yazıcı eklemek "mapping ref'i nereden gelir" sorusudur = ÜRÜN KARARI, imza ister.
    Sınır test_research_native_asset_pointer.py::test_the_native_asset_gate_is_passed_by_a_
    pipeline_built_revision içinde PİNLİ — o test kırmızıya dönerse boşluk kapanmış demektir,
    testi düzeltip geçme, kaydı güncelle.

(4) RD-09.c4 — funding-enabled bir RUN ister (bu slice schedule'a kadar gitti). Kapatılabilir
    hale gelmesi (3)'e bağlı: bugün kapatmak instrument_mapping_ref'i fixture'da elle set
    etmek demektir, ki bu #703'ün kör noktasının aynısıdır.

(5) A-08 (#514) — TEK BLOCKER, human-only, repo içinden KAPATILAMAZ.

KURALLAR: her iddiayı ampirik doğrula; sayı taşıma, yeniden ölç; kapatmadığını covered
İŞARETLEME; izole DB kullan (TEST_DATABASE_URL, asyncpg); kapanış ritüeli ZORUNLU.
```
