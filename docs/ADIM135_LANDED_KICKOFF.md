<!-- doc-status: current -->

# ADIM 135 — OD-2(a) MARK YOLU BAĞLANDI (`(b)` diagnostics): imza indi, kod indi

**Taban:** `origin/main` @ `a716f8ad` (ADIM 134 — GH #854 pin taşıma). Karar belgesi ADIM 133'te açılmıştı, kutular boştu.
**Bu slice ÜRÜN KODU DEĞİŞTİRDİ** ama **hiçbir finansal sayı oynamadı**: golden'ın 50
digest'i bayt bayt aynı, `ENGINE_VERSION` değişmedi, migration yok, OpenAPI değişmedi.

## Nerede duruyoruz

ADIM 132 (`C9`) OD-2(a) politikasını **sevk etti** ama ulaşılabilir bir yola **bağlamadı**.
ADIM 133 bunu ölçtü ve üç kutu açtı. **ADIM 135 kutuları imzalattı ve `(b)`'yi uyguladı.**

| Karar | Seçim | İmza |
|---|---|---|
| 1 — bağlansın mı / nereye | **`(b)` yalnız diagnostics** | `alimirbagirzade` · 2026-08-28 |
| 2 — `MARK_STALE_AFTER_MS` = 900 sn | **`A` — DOKUNMA** | `alimirbagirzade` · 2026-08-28 |
| 3 — diagnostics-only bump ister mi | **`A` — GEREKMEZ** | `alimirbagirzade` · 2026-08-28 |

## Bu slice'ın bıraktığı çapalar (tam sembol adlarıyla)

- `execution/intents.py::price_for` — **artık public** (eski `_price_for`). Yeni bir mark
  yüzeyi eklersen fiyat/authority çiftini **buradan al**, yeniden yazma.
- `portfolio_engine.py::_marks_at(views)` — `ItemTickView` → `MarkPrice` sözlüğü. Yeni
  finansal hesap yok; fiyatsız item **teklif edilmez** (unmarked olur, stale sayılmaz).
- `portfolio_engine.py::_run_tick` — bağlama noktası `publish_snapshot`'ın **hemen ardında**,
  donmuş pencerenin İÇİNDE. `valuation` **saf** olduğu için yasal.
- `portfolio_engine.py::PortfolioTick.valuation` — **zorunlu** alan (tek kurulum yeri
  `_run_tick`).
- `execution/portfolio_projection.py::_mark_staleness` → `diagnostics["mark_staleness"]`
  (dört anahtar). `ABSENT_BY_CONSTRUCTION` **el değmedi** — hiçbir disclosure iddiası
  karşı-olgusal olmadı.
- `tests/unit/test_oracle_od2_mark_binding.py` — 8 case, iki fixture:
  `_holder_and_ticker` (staleness ekseni) ve **`_marked_holder`** (E(t) ekseni, fiyatı
  oynayan). **İkincisini silme:** onsuz `E(t)` assertion'ı vacuous olur (NC-3 ölçtü).

## Pazarlıksız — bir sonraki okuyucu için

1. **`MARK_STALE_AFTER_MS`'i DEĞİŞTİRME.** Karar 2 = `A` imzalı. Değiştirmek yeni bir
   `carry_forward_bounded_v2` **ve** ikinci bir `ENGINE_VERSION` bump'ı gerektirir.
2. **Mark figürlerini `execution_content`'e KOYMA.** Bu `(c2)`'dir, **seçilmedi**, ve
   `execution_key`'i kendi çıktısına bağlar. Karar 3 = `A` bunun üzerine kuruludur.
3. **Terminal bir `valuation()`/`attribute()` çağrısı EKLEME.** P10 her pozisyonu kapatır →
   her zaman boş kitap görür (ADIM 133 Ölçüm 4, koşturularak).
4. **Worker'a (`application/jobs/backtest_engine.py`) mark kodu YAZMA** — imzalı importer
   allowlist'ini genişletir; `C4`'te birebir bu hamle reddedildi (GH #731).
5. **30m+ koşularda dolu `stale_refused_items` bir BUG DEĞİL** — imzalı fail-closed politika.

## Açık kalanlar (bu slice kapatmadı, iddia da etmiyor)

- ~~ADR-0002 §13.1'in OD-2 satırı~~ → **DÜZELTİLDİ** (ürün sahibi 2026-08-28'de adjudication'ı
  açıkça yetkilendirdi). Satır artık *"Built (ADIM 132), bound (ADIM 135)"* diyor; eski metin
  `Was: "…"` olarak **korundu**. `E(t)` realized-only iddiası **değişmedi, hâlâ doğru**.
- ~~ADIM 133 Ölçüm 1'in bayat docstring'leri~~ → **DÜZELTİLDİ** (dördü: `attribution.py`,
  `provenance.py`, `portfolio_projection.py`, `portfolio_engine.py`). Ampirik zincir ölçüldü:
  `jobs/backtest_engine.py:1273` → `project_portfolio_run` → `provenance:62` → `attribution`.
  **`attribute()`'un hâlâ SIFIR çağıranı var** ve bu docstring'de artık **gerekçesiyle** yazılı
  (taşıyıcı `valuation()`, çünkü `PortfolioAttribution` `stale_refused_items` taşımaz).
  `portfolio_projection.py`'nin **yol** biçimli yazımı korundu — noktalı yazım containment
  taramasını kendisi tetikler.
- **`(c1)` provenance** — seçilmedi; istenirse yeni bir imza ister.
- **A-08 (#514)** — AÇIK, ayrı hat, **RC verdict `BLOCKED`**.
- **Frontend kapıları koşulmadı**; **tam suite uçtan uca koşulmadı** → otorite **CI**.

## Paste-ready resume prompt

```
ENTROPIA — SONRAKİ SLICE

ÖNCE DOĞRULA (bu prompt BAYAT VARSAYILIR):
  git fetch && git log --oneline origin/main -4 && gh pr list --state open
  grep -n '^## ADIM' docs/PROJECT_HISTORY.md | tail -2

DURUM: ADIM 135 OD-2(a) mark yolunu `(b)` = yalnız diagnostics olarak üretime BAĞLADI.
`diagnostics["mark_staleness"]` artık her unified koşuda dört anahtar yayımlıyor.
ENGINE_VERSION DEĞİŞMEDİ, golden OYNAMADI, MARK_STALE_AFTER_MS = 900 sn (Karar 2 = A).

PAZARLIKSIZ: MARK_STALE_AFTER_MS'i değiştirme · mark figürlerini execution_content'e koyma
  ((c2), seçilmedi) · terminal valuation() ekleme (P10 boş kitap) · worker'a mark yazma
  (imzalı allowlist) · tests/unit/test_oracle_od2_mark_binding.py::_marked_holder'ı silme
  (onsuz E(t) testi vacuous olur — NC-3 ölçtü).

AÇIK KALEMLER (biri seçilir):
  (i)  ADR-0002 §13.1 OD-2 satırı + üç bayat docstring — karşı-olgusal, DÜZELTİLMEDİ.
       Bu bir adjudication'dır; ürün sahibi imzası ister.
  (ii) (c1) provenance'a yazma — YENİ İMZA ister.
  (iii) A-08 (#514) — tek blocker. RC verdict BLOCKED, kapatan tek şey budur.

KURALLAR: her iddiayı ampirik doğrula; sayı taşıma, yeniden ölç; kapatmadığını `covered`
  İŞARETLEME; negatif kontrolsüz test yazma; kapanış ritüeli ZORUNLU.
ORTAM: Postgres :5432 (entropia/entropia). backend/.venv yoksa `cd backend && uv sync --all-extras`.
```
