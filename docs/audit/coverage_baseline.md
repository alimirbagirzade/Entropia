# Entropia — Test Coverage Baseline (ölçülmüş, tahmin değil)

Bu doküman **koşturulmuş bir ölçümün** kaydıdır. Öncesinde coverage rakamı projede
hiçbir yerde yazılı değildi: backend'in `addopts`'u coverage üretiyordu ama
CLAUDE.md'nin local-verify döngüsü `--no-cov` ile koşuyordu (kimse sayıyı görmüyordu),
frontend'de ise provider hiç kurulu değildi. P-32 iki gate'i de kurdu; bu doküman o
gate'lerin eşiklerini **gerçek sayıya** kalibre eder.

**Ölçüm tarihi:** 2026-07-29 · **Commit:** `479c5f8` (`origin/main`, P-32 landed)
**Makine:** macOS (darwin 25.5.0), lokal Postgres :5432, worktree'ye özel izole DB
(`entropia_covbase`, `TEST_DATABASE_URL` ile pinlendi)

> **Otorite uyarısı.** Aşağıdaki sayılar **lokal** bir koşudan gelir. Projenin otoritesi
> CI'dır (Linux). Platforma bağlı dallar iki ortam arasında birkaç onda puan
> oynayabilir — eşikler bu yüzden ölçülen değerin ~2 puan altına konmuştur (§4).

---

## 1. Koşulan komutlar

Backend (tek pytest çağrısı, ortada kesilmedi):

```bash
cd backend && TEST_DATABASE_URL=postgresql+asyncpg://entropia:entropia@localhost:5432/entropia_covbase \
  .venv/bin/pytest --cov-report=html --cov-report=json:<out>/backend_coverage.json
```

(`--cov=entropia --cov-report=term-missing --cov-fail-under` zaten
`backend/pyproject.toml` `addopts`'undan geliyor.)

Frontend:

```bash
cd frontend && npm run coverage -- --no-file-parallelism
```

---

## 2. Toplam sonuçlar

### Backend — `%92.06`

```
2712 passed, 8 warnings in 1770.85s (0:29:30)
TOTAL   24379 stmts   1936 missing   92.1%
Required test coverage of 80% reached. Total coverage: 92.06%
```

| | Değer |
|---|---|
| Toplam statement | 24 379 |
| Kapsanmayan | 1 936 |
| **Line coverage** | **92.06%** |
| Modül sayısı | 369 |
| %100 kapsanan modül | 194 (%52.6) |
| %80 altındaki modül | 23 (%6.2) |
| Test sonucu | **2712 passed / 0 failed** — tam yeşil |

### Frontend — `%84.67` line

```
Test Files  61 passed (61)
     Tests  641 passed (641)
Statements : 82.29% ( 5127/6230 )
Branches   : 71.96% ( 4630/6434 )
Functions  : 75.09% ( 1945/2590 )
Lines      : 84.67% ( 4806/5676 )
```

| Metrik | Ölçülen | Kapsanan / Toplam |
|---|---|---|
| **Lines** | **84.67%** | 4806 / 5676 |
| **Statements** | **82.29%** | 5127 / 6230 |
| **Functions** | **75.09%** | 1945 / 2590 |
| **Branches** | **71.96%** | 4630 / 6434 |

Dosya sayısı 103; 26'sı %100 line, 26'sı %80 altında.

**Eski tahminle kıyas:** oturum notlarındaki "backend %80-88, frontend %60-75" tahmini
**iki tarafta da düşüktü** — backend gerçekte 92, frontend 85 (line).

---

## 3. En düşük modüller

### 3.1 Backend — en düşük 15 (≥10 statement)

| # | Modül (`src/entropia/` altında) | % | stmts | missing |
|---|---|---|---|---|
| 1 | `apps/worker/actors.py` | 24.3 | 177 | 134 |
| 2 | `infrastructure/s3/datasets.py` | 32.8 | 61 | 41 |
| 3 | `application/queries/research_data.py` | 39.5 | 43 | 26 |
| 4 | `apps/seed.py` | 44.7 | 197 | 109 |
| 5 | `application/queries/strategy.py` | 47.4 | 57 | 30 |
| 6 | `apps/api/routes/admin_panel.py` | 60.6 | 99 | 39 |
| 7 | `application/queries/create_package.py` | 60.6 | 94 | 37 |
| 8 | `infrastructure/postgres/engine.py` | 61.9 | 21 | 8 |
| 9 | `domain/manual/stream.py` | 64.5 | 31 | 11 |
| 10 | `domain/manual/blocks.py` | 70.4 | 324 | 96 |
| 11 | `apps/api/routes/create_package.py` | 71.0 | 107 | 31 |
| 12 | `application/queries/esp.py` | 71.4 | 77 | 22 |
| 13 | `apps/api/routes/package_import.py` | 73.9 | 23 | 6 |
| 14 | `infrastructure/s3/parquet_stream.py` | 75.0 | 20 | 5 |
| 15 | `apps/api/routes/health.py` | 75.0 | 24 | 6 |

Sonraki beş (bağlam için): `apps/api/routes/instrument.py` 75.4 · `apps/api/routes/backtest.py`
75.7 · `infrastructure/redis/client.py` 77.8 · `apps/api/routes/sharing.py` 77.8 ·
`infrastructure/postgres/health.py` 78.6.

**Katman toplamları** (düşükten yükseğe, yalnız anlamlı olanlar):

| Katman | stmts | missing | % |
|---|---|---|---|
| `apps/worker` | 178 | 134 | 24.7 |
| `apps/seed.py` | 197 | 109 | 44.7 |
| `infrastructure/s3` | 101 | 48 | 52.5 |
| `domain/manual` | 416 | 107 | 74.3 |
| `infrastructure/redis` | 18 | 4 | 77.8 |
| `apps/api` | 2305 | 363 | 84.3 |
| `application/queries` | 2390 | 263 | 89.0 |
| `application/jobs` | 2025 | 195 | 90.4 |
| `application/commands` | 4493 | 406 | 91.0 |
| `domain/backtest` | 2912 | 86 | 97.0 |
| `infrastructure/postgres` | 3292 | 76 | 97.7 |

### 3.2 Frontend — en düşük 15 (≥20 satır)

| # | Dosya | line% | stmt% | fn% | br% | satır |
|---|---|---|---|---|---|---|
| 1 | `src/components/TradeLogConfigForm.tsx` | 33.3 | 34.6 | 25.0 | 50.0 | 24 |
| 2 | `src/components/TradingSignalConfigForm.tsx` | 34.8 | 36.0 | 26.3 | 50.0 | 23 |
| 3 | `src/components/StrategyGraphForm.tsx` | 40.2 | 38.3 | 23.2 | 55.1 | 189 |
| 4 | `src/components/StrategyConfigForm.tsx` | 45.5 | 46.7 | 33.3 | 78.6 | 88 |
| 5 | `src/lib/tradeLogForm.ts` | 64.8 | 64.5 | 66.7 | 60.4 | 108 |
| 6 | `src/components/PreCheckModal.tsx` | 65.4 | 64.3 | 33.3 | 35.3 | 26 |
| 7 | `src/lib/tradingSignalForm.ts` | 67.6 | 67.9 | 66.7 | 65.3 | 108 |
| 8 | `src/components/Modal.tsx` | 67.6 | 66.7 | 100.0 | 36.0 | 34 |
| 9 | `src/pages/Instruments.tsx` | 69.7 | 67.7 | 46.8 | 67.4 | 89 |
| 10 | `src/pages/Login.tsx` | 71.4 | 72.4 | 42.9 | 61.9 | 28 |
| 11 | `src/pages/FutureDev.tsx` | 75.3 | 71.4 | 68.5 | 62.3 | 97 |
| 12 | `src/lib/instrument.ts` | 78.4 | 75.6 | 78.3 | 58.3 | 37 |
| 13 | `src/components/InstrumentPicker.tsx` | 79.2 | 77.8 | 64.7 | 78.7 | 24 |
| 14 | `src/components/TradeLogEditor.tsx` | 79.4 | 76.8 | 75.0 | 64.0 | 97 |
| 15 | `src/pages/PreCheck.tsx` | 79.5 | 73.5 | 60.9 | 58.5 | 44 |

**Hiç kapsanmayan küçük dosyalar (%0):** `src/App.tsx` (6 satır),
`src/components/ErrorBoundary.tsx` (7), `src/lib/queryClient.ts` (3),
`src/pages/NotFound.tsx` (1), `src/pages/Placeholder.tsx` (1), `src/lib/types.ts` (0 —
salt tip, ölçülecek satırı yok). Toplam etkileri küçük ama `ErrorBoundary` **davranışı
olan** bir bileşen: hata yolu hiç test edilmiyor.

---

## 4. Eşik kalibrasyonu

Kural: eşik **ölçülen sayının hemen altına** konur — sıradan bir regresyon tetiklesin,
normal dalgalanma tetiklemesin. Yeşil bir koşuyu kırmamak için lokal (macOS) ile CI
(Linux) arasındaki olası platform farkına ~2 puan pay bırakıldı.

| Gate | Ölçülen | Eski eşik | **Yeni eşik** | Pay |
|---|---|---|---|---|
| backend `--cov-fail-under` | 92.06 | 80 | **90** | 2.06 |
| frontend `lines` | 84.67 | 80 | **83** | 1.67 |
| frontend `statements` | 82.29 | 78 | **80** | 2.29 |
| frontend `functions` | 75.09 | 70 | **73** | 2.09 |
| frontend `branches` | 71.96 | 68 | **70** | 1.96 |

Backend'de eski 80, gerçeğin **12 puan** altındaydı: `application/commands` katmanı
tümüyle test edilmeden silinse bile gate yeşil kalırdı. Frontend eşikleri P-32'de
"tam yeşil olmayan bir koşudan alt sınır" olarak konmuştu; bu ölçüm **641/641 yeşil**
olduğu için artık alt sınır değil, gerçek değer.

**Sonraki dalga:** CI bu eşiklerle bir kez yeşil koştuktan sonra CI'ın kendi rakamı
okunur ve pay ~1 puana indirilir (backend 91, frontend lines 84). Bir eşiği **kırmızı
koşuyu yeşile çevirmek için asla düşürme** — eksik testi yaz.

---

## 5. Kritik modüller — eşik altında olan var mı?

CLAUDE.md'de adjudicated invariant taşıyan modüller ayrıca kontrol edildi:

| Modül | % | Karar |
|---|---|---|
| `shared/errors.py` (O-02 hata zarfı) | **100.0** | temiz |
| `shared/responses.py` (O-02 `ErrorBody`) | **100.0** | temiz |
| `shared/concurrency.py` (O-12 OCC dual-token) | **100.0** | temiz |
| `domain/importing/source_file.py` (K-07 fail-closed upload) | **100.0** | temiz |
| `domain/trash/restore.py` (O-17 restore katalogu) | **100.0** | temiz |
| `domain/backtest/manifest.py` (ENGINE_VERSION) | **100.0** | temiz |
| `domain/trash/page.py` (K-06 tip katalogu) | 96.9 | temiz |
| `application/idempotency.py` (O-13 `run_idempotent`) | 95.7 | temiz |
| `domain/backtest/engine.py` | 94.8 | temiz |
| `application/commands/backtest_run.py` | 93.8 | temiz |
| `application/commands/deletion.py` (O-30 purge 202) | 86.8 | modül bazında yeni eşik altı |
| `application/jobs/purge.py` | 82.8 | modül bazında yeni eşik altı |

**Sonuç: adjudicated invariantların yaşadığı yüzeylerin hiçbiri düşük değil** — altısı
tam %100. Ancak **iki kritik modül yeni backend eşiğinin (90) altında:**
`commands/deletion.py` (86.8) ve `jobs/purge.py` (82.8). Gate **toplam** üzerinden
çalıştığı için bu CI kırmızısı değil, ama soft-delete / purge yolunun en az kapsanan
kritik yüzey olduğunu gösteriyor — O-30'un iki-ad-tek-değer 202 gövdesi ve
`PURGE_NOT_ELIGIBLE` preflight'ı burada yaşıyor. `jobs/purge.py`'de kapsanmayan satırlar
(`55, 61-64, 82, 110, 151, 159, 170, 183-189, 199-205, 240, 244`) ağırlıkla erken-çıkış
ve uygunsuzluk dalları.

---

## 6. Düşük kapsamın dürüst okuması

Listedeki her düşük modül "test edilmemiş davranış" demek değil:

- **`apps/worker/actors.py` (24.3)** — dramatiq actor gövdeleri
  (`asyncio.run(_run_x(job_id))`). Sardıkları komut fonksiyonları doğrudan test
  ediliyor; kapsanmayan satırlar broker'a bağlı actor kaydı. Gerçek boşluk değil,
  ölçüm artefaktı. (`__main__.py` zaten `[tool.coverage.run] omit`'te; `actors.py` değil.)
- **`apps/seed.py` (44.7)** — geliştirici seed script'i, ürün yolu değil.
- **`infrastructure/s3/datasets.py` (32.8)** — MinIO/S3 gerektiren yollar;
  `integration` marker'lı testler lokal stack olmadan koşmuyor.
- **`application/queries/*` (research_data 39.5, strategy 47.4, create_package 60.6)**
  — **gerçek boşluk.** Bunlar salt-okuma projeksiyonlar; kapsanmayan satırlar çoğunlukla
  filtre ve boş-sonuç dalları.
- **Frontend `*ConfigForm.tsx` (33-45)** — V18 form yüzeyleri; render testi var, alan
  doğrulama ve submit dalları yok. **Gerçek boşluk.**
- **`ErrorBoundary.tsx` (%0)** — hata yolu hiç test edilmiyor. **Gerçek boşluk.**

Kapsamı yükseltmek için ilk hedefler: `queries/research_data.py`, `queries/strategy.py`,
`queries/create_package.py`, `commands/deletion.py` + `jobs/purge.py` (kritik),
frontend `StrategyGraphForm.tsx` / `StrategyConfigForm.tsx`, `ErrorBoundary.tsx`.

---

## 7. Tekrarlanabilirlik notları

- Suite'i **tek pytest çağrısında** koş, ortada öldürme. Yarıda kesilmiş bir koşu
  artakalan DB bağlantıları bırakır ve sonraki koşuda sahte FAILED/ERROR üretir
  (bu ölçümde bir kez yaşandı; DB `DROP DATABASE` ile sıfırlanıp yeniden koşuldu).
- Paralel worktree oturumları aynı Postgres'i paylaşıyor — `TEST_DATABASE_URL` ile
  worktree'ye özel DB kullan.
- Koşu 10 dk'dan uzun (bu ölçümde 29:30, yüklü makinede daha uzun): oturum
  harness'ının arka plan zaman aşımına takılmaması için tam bağımsız process başlat.
- Frontend'de `--no-file-parallelism` lokal koşu için gerekli; coverage rakamını
  değiştirmez, yalnız yürütme modelini değiştirir.
- `pytest … | tail` **kullanma** — exit code `tail`'in olur, pytest'in değil.
