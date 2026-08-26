<!-- doc-status: current -->

# ADIM 115 landed — paylaşımlı saatin ARBİTRAJI pinlendi; sıradaki hamle HÂLÂ bir imza, kod değil

## Neredeyiz

`main` tabanı `a57e552` (PR #835 merged). Alembic head `0043_i08_registry_strategy_fks`
(migration yok) · `ENGINE_VERSION` **değişmedi**
(`backtest-engine-v18-percent-sizing-per-fill-commission`) · OpenAPI **değişmedi** ·
`SHARED_ALLOCATION_STATUS` = **`future_dev`** · golden'lara dokunulmadı (ürün kodunda **sıfır
satır**). Blocker sayısı **1** (yalnız A-08), verdict **BLOCKED**. Kabul borcu tavanları
**54 partial / 6 uncovered · A1 B21 C6 D32** — bu slice onlara **dokunmadı** (bu bir kabul
borcu partisi değil).

**Sayısal otorite bu belge DEĞİL** → `docs/generated/repository_facts.md` (üretilmiş, CI'da
`--check` bloklayıcı; bu slice onu **3758 → 3765** collection'a tazeledi). Bu belge **ölçtüğü
anı dondurur**.

## Bu slice ne bıraktı

Görev *"worker → `run_portfolio` production wiring"* istedi. **Wiring İNMİŞTİ** (`C3` = #777,
`C4`/E5 = #799 + #805) ve tek satır ürün kodu yazılmadı. Kapatılan şey **arbitrajın
okunmamış olmasıydı**: `C4` dalın KOŞTUĞUNU pinlemişti, birleşik eksenin **var olma sebebini**
hiçbir şey okumuyordu.

**Yedi worker düzeyi integration case**, hepsi gerçek `run_backtest` üzerinden, hepsi
`tests/integration/test_shared_clock_worker_branch.py` §(3)/§(4) altında. Modül **7 → 14
passed**.

### Yeniden kullanım çapaları (birebir adlar)

| Ne | Nerede |
|---|---|
| Kimlik aracı (dört content checksum) | `test_shared_clock_worker_branch.py::_artifact_checksums` — `diagnostics` **bilerek dışarıda**, gerekçesi docstring'de ölçülü |
| İz okuyucu | `::_signal_events` (persist edilmiş `SignalEventRow`, `seq` sırasında) |
| Koşu sürücüsü | `::_admit_and_run` — `idempotency_key` **zorunlu** (aynı kompozisyonda iki koşu için) |
| Ayrık kadans üreteci | `::_stepped_bars(step, count, offset=...)` — `offset` **taşıyıcı** |
| Heterojen kompozisyon | `::_heterogeneous_composition` → `(composition_id, entity_id -> bars)` |
| Kadans tablosu | `::_HETEROGENEOUS_CADENCES` (`1D@06:00` ×22 · `12h@00:00` ×43 → birleşim 65) |
| Dünya değiştirici | `::_lifted(monkeypatch)` (değişmedi, `C4`'ten) |

### Pazarlıksız olarak öğrenilenler

* **`run_portfolio`'yu grep'lemek YANILTIR.** Worker `iter_portfolio` çağırır ve çağırmak
  **zorundadır**: `run_portfolio` generator'ı tüketir, worker'ın iptal kontrolü `async`'tir ve
  senkron bir döngüden koşamaz. Containment gate **ikisini birden** grepler
  (`_LOOP_ENTRY_POINTS`) ve `test_every_public_loop_driver_is_named_in_the_caller_scan`
  üçüncü bir giriş noktası eklenirse kırmızı verir.
* **`diagnostics` checksum'ı kimlik iddiasında KULLANILAMAZ** — projeksiyonu satırı taze
  basılan `diagnostic_id` ULID'i ile hash'ler, yani bayt bayt aynı iki koşuda bile ayrışır
  (ölçüldü). İçeriği **doğrudan** karşılaştır.
* **`_empty_composition` aktörün VARSAYILAN mainboard'unu döner.** Aynı aktör için iki kez
  `_composition(...)` çağırmak **ikinci bir kompozisyon yaratmaz**, birincisine ekler — bir
  probe bu yüzden tek-item sandığı koşuyu iki item'lı olarak ölçtü.
* **Ayrık kadans şart.** 1D@00:00 + 12h@00:00 hizalıdır ve birleşim **ince ekseni** verir (43);
  altı saatlik offset ile birleşim **65** olur ve *"birleşimi yürüyor"* iddiası ilk kez
  *"ilk stream'i yürüyor"*tan ayrışır.
* **`!= UNIFIED_KIND` yetmez.** Üç `engine_kind` var; tek item'ı **bileşik fold**'a yollayan
  bir kusur o assertion'ı geçerken Result'ı sessizce yeniden fiyatlar (negatif kontrolde
  ölçüldü). Yolu **adıyla** assert et.
* **Negatif kontrol yamasını `git checkout --` ile GERİ ALMA** — ağaç commit edilmemiş iş
  taşıyabilir. Bellekteki anlık görüntüden geri yaz, sonra `git status` oku (ADIM 111).

## Ölçülmüş, kapatılmayan sınır

A14'ün en güçlü okuması (*aynı kompozisyon iki dünyada aynı baytlar*) tek-item için **bu
ağaçtan kurulamaz**: paylaşımlı sermayeli kompozisyon sevk edilen dünyada **admission'da
reddedilir**, yani ikinci dünya yoktur. `C9`'un borçlu olduğu karşılaştırma birleşik eksenin
tek item'a indirgenmesidir ve `len(prepared_items) > 1` kapısının kaldırılmasını ister —
**kaynak düzeyi literal**, `C9` kararı.

## Sıradaki hamle — KOD DEĞİL, İMZA (değişmedi)

`G8` (#559) · `G14` (#544) hâlâ **KARARSIZ**; sonra `G11`+`G12` → `C6`, `G15` (leg 3), `G10`
**hiç talep edilmedi**, ön koşul 15–18 ve 22, **en son `C9`** (lift). Sıra ve gerekçe:
`docs/audit/final_closure_delta_audit_2026-08-25.md` §10. A-08 kendi hattında ve RC
verdict'ini bağımsız blokluyor.

---

## Paste-ready resume prompt

```
ENTROPIA — oturum devri (ADIM 115 sonrası)

ÖNCE DOĞRULA (handoff BAYAT VARSAYILIR):
  git fetch && git log --oneline origin/main -6 && gh pr list --state all
  grep -n '^## ADIM' docs/PROJECT_HISTORY.md | tail -3
  ls docs/ADIM*KICKOFF.md | sort -V | tail -3   # canlı olan EN YÜKSEK numaralı olmalı

OKUMA SIRASI: docs/ADIM115_LANDED_KICKOFF.md -> docs/STAGE2_HANDOFF.md (§landed + §Next)
  -> docs/STAGE_BUILD_PLAN.md -> docs/spec/NN_* -> agentmemory (boşsa:
  node scripts/memory_index.mjs --sync)

DURUM: paylaşımlı portföy CONTAINED. SHARED_ALLOCATION_STATUS = future_dev.
  Wiring İNMİŞ (C3 #777, C4/E5 #799+#805); worker iter_portfolio çağırır —
  run_portfolio'yu grep'lemek yanıltır. ADIM 115 birleşik eksenin ARBİTRAJINI
  worker düzeyinde pinledi (7 case, 7 negatif kontrol).
  Blocker 1 (yalnız A-08), BLOCKED.

SIRADAKİ HAMLE KOD DEĞİL, İMZA: G8 (#559) · G14 (#544) hâlâ kararsız.
  Sonra G11+G12 -> C6, G15 (leg 3), ön koşul 15-18 ve 22, EN SON C9 (lift).
  Gerekçe: docs/audit/final_closure_delta_audit_2026-08-25.md §10.

ORTAM: taze container'da .venv ve Postgres YOK.
  pg_ctlcluster 16 main start
  su postgres -c "psql -c \"CREATE ROLE entropia LOGIN PASSWORD 'entropia' SUPERUSER\""
  cd backend && uv sync --all-extras
  export TEST_DATABASE_URL=postgresql+asyncpg://entropia:entropia@localhost:5432/entropia_x
  uv run pytest tests/integration/test_shared_clock_worker_branch.py -q --no-cov

KURALLAR: alt küme koşarken --no-cov; exit code'u AYRI oku (pytest ... | tail KULLANMA);
  test ekleyen slice repository_facts'i TAZELEMELİ
  (cd backend && uv run python ../scripts/generate_repository_facts.py --root ..);
  docs PR'ında merge DEĞİL rebase; her CRITICAL/HIGH bulguyu ampirik doğrula.
```
