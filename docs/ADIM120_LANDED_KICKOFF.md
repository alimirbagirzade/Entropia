<!-- doc-status: current -->

# ADIM 120 landed — `G15` imzalandı (Seçenek B) ve aynı slice'ta uygulandı; leg 3 artık FLAT

> **Bu belge bir SONRAKİ oturumun tohumudur.** En altta yapıştır-hazır bir resume prompt var.

## Nerede duruyoruz

- **alembic head `0043_i08_registry_strategy_fks`** — bu dalgada **migration YOK**.
- `ENGINE_VERSION` **değişmedi** · OpenAPI **değişmedi** · `SHARED_ALLOCATION_STATUS` = `future_dev`.
- Blocker sayısı **DEĞİŞMEDİ (1 — yalnız A-08), BLOCKED**. Kabul borcu tavanları **OYNAMADI**.
- **`G15` KAPANDI.** `docs/decisions/closure_g15_external_row_winner_2026-08-17.md` §İMZA SATIRI
  → **Seçenek B**, kazanan **en yeni**, `created_at DESC, <pk> DESC`.

## Bu slice'ın BIRAKTIĞI çapalar (tam sembol adlarıyla)

| Sembol | Ne yapar |
|---|---|
| `infrastructure/postgres/repositories/readiness.py::resolve_trade_log_batch` | tek revision → **en yeni** batch (`LIMIT 1`, toplam sıra) |
| `…::resolve_trade_log_batches` | **çoğul**, `DISTINCT ON (work_object_revision_id)`, **aynı** sıra |
| `…::resolve_signal_revision` / `…::resolve_signal_revisions` | Trading Signal yarısı, birebir aynı sözleşme |
| `application/commands/readiness_check.py::_build_item_inputs` | döngüden **ÖNCE** iki batch okuma (`trade_log_pins` / `signal_pins`) |
| `application/commands/readiness_check.py::_resolve_external` | **`session` ALMAZ** — saf map lookup |
| `tests/integration/test_readiness_external_row_winner.py` | kazanan · toplam sıra · **iki formun anlaşması**, üçü AYRI pinli |

**Yeni bir external import yüzeyi eklersen:** okuyucusunu bu iki idiomdan birine bağla, üçüncü
bir idiom **icat etme**; ve `_resolve_external`'a **session geri koyma** — o parametrenin
yokluğu N+1'i yapısal olarak imkânsız kılan şeydir.

## Pazarlıksız kurallar (bu slice'ta ölçüldü)

1. **Kazananı kararsız olan bir bacağı batch'leyerek `per_item` DÜŞÜRME.** Bu bir onarım değil,
   sessiz bir ürün kararıdır. `query_budgets.json`'ın `note`'u bunu adıyla yazıyor.
2. **`work_object_revision_id` UNIQUE DEĞİLDİR.** B onu belirlenimli yaptı, **kaldırmadı**.
   Bunu bir kısıt sanıp üstüne kod yazma.
3. **`created_at` tek başına TOPLAM SIRA DEĞİLDİR.** `server_default=func.now()` **transaction**
   damgasıdır → tek transaction'da yazılan iki satır **birebir** eşitlenir. pk tie-break'i
   kaldırırsan eski belirlenimsizlik **geri gelir**.

## AÇIK kalanlar

- **`A` (UNIQUE kısıt + migration) AÇIK** — üretim duplikasyon sayısı hâlâ **alınamadı**
  (ön koşul kutusu `[x] sayılamadı`). Sayı alınırsa A ucuzdur: kısıt bugün de **yok** (ölçüldü).
  Betik belgenin §ÖLÇÜM 3'ünde, **doğrulanmış** hâlde duruyor.
- **#854** — §Ölçüm 4'ün pin-taşıma kusuru. G15'in **hiçbir** seçeneği çözmez.
- **`C6`'nın G11/G12 yarısı (admission blocker'ları) HÂLÂ İNMEDİ** — ADIM 119 yalnız OD-1/OD-6
  yarısını sevk etti (kendi başlığı bunu söylüyor). `ALLOCATION_SHARED_MODE_DEFERRED_FILL_UNSUPPORTED`
  `backend/src`'te **sıfır hit**.
- İmzasız kapılar: **`G14`** (#544 — #850 `C`'yi sevk etti, kapının kendisi ayrı ölçülmeli) ·
  **`G10`** (#852 imza yüzeyini açtı, **talep edilmedi**).

## Sıradaki kalem

**`C6`'nın kalan yarısı** (G11 + G12 admission blocker'ları — ikisi de #849'da İMZALI, yani
kapı açık). Sonra ön koşul 15–18 (`OD-1/2/3/6`'nın kalanı) → `G10` → **EN SON `C9`**.
Sıra ve gerekçe: `docs/audit/final_closure_delta_audit_2026-08-25.md` §10.

---

## Resume prompt (yapıştır-hazır)

```
ENTROPIA — C6'nın kalan yarısı (G11 + G12 admission blocker'ları)

ÖNCE DOĞRULA: git fetch && git log --oneline origin/main -6 && gh pr list --state all
  ADIM numarasını ve açık PR'ların docs/ADIM<n>_LANDED_KICKOFF.md yollarını ÖLÇ
  (son kayıt ADIM 120; boş görünen numara güvenli değildir — ADIM 100/120).

GÖREV: G11 ve G12 #849'da İMZALANDI ama kodları HÂLÂ İNMEDİ.
  Ölç: grep -rn 'ALLOCATION_SHARED_MODE_DEFERRED_FILL_UNSUPPORTED' backend/src
  (ADIM 120'de SIFIR hit idi). ADIM 119 C6'nın yalnız OD-1/OD-6 yarısını sevk etti.
  İmza metni: docs/decisions/ altındaki G11/G12 kapanış belgeleri —
  G11 = (a) tam admission blok, field_path İKİSİ DE (O-02); G12 = A + ret "ikisi de".
  KARARI YENİDEN AÇMA, imzalanmış olanı UYGULA.

KURALLAR: her CRITICAL/HIGH bulguyu ampirik doğrula; alt küme koşarken --no-cov;
  exit code'u AYRI oku (pytest ... | tail exit code'u YUTAR); GateGuard'da 4 olguyu sun;
  migration olursa alembic up/down/up + model<->migration kolon paritesi;
  main'i içeri alırken MERGE DEĞİL REBASE; kapanış ritüeli ZORUNLU.

BİLMEN GEREKEN (ADIM 120):
  - Ready Check leg 3 artık FLAT (per_item 0). Kazanan kuralı = G15/Seçenek B,
    en yeni (created_at DESC, <pk> DESC). work_object_revision_id UNIQUE DEĞİL.
  - _resolve_external session ALMAZ. Geri koyma.
  - docs-history-guard bayat tabanı YAKALAR; çare rebase, `ENTROPIA_DOCS_GUARD=off` DEĞİL.
  - git stash yığını worktree'ler arası PAYLAŞIMLI — patch dosyası kullan.
```
