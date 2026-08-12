<!-- doc-status: current -->
# ADIM 49 LANDED — kabul borcu sınıf B, parti 02 · sıradaki slice için kickoff

> **Bu belge ADIM 49 kapanışında yazıldı.** Sayısal otorite bu belge DEĞİL →
> `docs/generated/repository_facts.md` (üretilmiş, CI'da `--check` bloklayıcı).
> Tam kayıt: `docs/PROJECT_HISTORY.md` §ADIM 49.

## Neredeyiz

**Blocker sayısı 1 (yalnız A-08), verdict BLOCKED.** ADIM 49 borç defterinin ikinci
partisiydi: dış work object'in **run provenance**'ı. **Beş kriter kapandı** →
**partial 118 → 113**, **sınıf B 87 → 82**. **Ürün kodu değişmedi** (tek satır bile).

Kapanan beş: `TL-12` (c2+c3) · `TL-20` (c3) · `TS-11` (c3) · `TS-21` (c1) · `AOS-21` (c1).

## Bu slice'ın bıraktıkları (reuse anchor'ları — tam sembol adlarıyla)

| Anchor | Ne için |
|---|---|
| `tests/integration/test_external_object_run_provenance.py::_attach_trade_log` | **Eksik olan parça.** Bir Trade Log'u run kompozisyonuna sokar; gerçek boru hattını koşturur (upload → import worker → Save & Add). Elle satır yazma, bunu çağır |
| `::_completed_run` | Admit + `run_backtest` → SUCCEEDED, tek çağrı. `run_id` + `result_id` + `manifest_hash` döner |
| `::_external_entry(manifest, item_kind)` | Manifest'ten dış nesne girdisini çeker |
| `test_backtest_manifest_pinning.py::_attach_trading_signal` | Signal karşılığı — **zaten vardı**, yeniden yazma |
| `test_backtest_persistence.py::_ready_composition` · `::_e2e_bars` · `::_count` | Strateji kompozisyonu + determinist barlar + satır sayacı |

## Tavizsiz kurallar (bu slice'ta kanıtlandı)

1. **Manifest girdisini BÜTÜN olarak karşılaştır**, yalnız id alanını değil — ve run'ın
   `manifest_hash`'ini yeniden doğrula. Tek alan assert etmek yeniden yazılmış bir
   manifest'i geçirir.
2. **"Değişmedi" iddiasından önce `session.expire_all()`.** Aksi halde soruyu
   veritabanı değil ORM identity map'i cevaplar ve test hiçbir şey kanıtlamaz.
3. **Sıfır-assertion kendi kendini korumalı.** `== 0` yazıyorsan, aynı sayacın aynı
   testte **1**'e ulaştığını da göster; yoksa bozuk bir sorgu ya da boş bir veritabanı
   testi yeşil tutar.
4. **RATCHET YALNIZ AŞAĞI İNER**; `total_criteria` bir **TABANDIR**.
5. **Sınıflar AYRI ratchet'lenir** → B'den C/D'ye taşımak o tavanı **YÜKSELTİR**,
   bu bir adjudication'dır.

## ÜÇ AÇIK BULGU (karar insan/PO'da — agent kapatamaz)

* **`TL-11.c3` KAPATILAMAZ; sınıfı B değil, C görünüyor.** Kriter *allocation-enabled*
  bir run istiyor; bu build'de shared allocation **admission'da fail-closed**
  (`SHARED_ALLOCATION_STATUS = "future_dev"` → `ALLOCATION_SHARED_MODE_NOT_IN_BUILD`,
  run/manifest/job yaratılmadan). **ADIM 48'in kickoff'u bunu kapatılabilir sandı —
  o öneri YANLIŞTI.** Yeniden sınıflandırılmadı: **C tavanını yükseltirdi.**
* **`TL-16` sınıfı ŞÜPHELİ (B yazıyor, D görünüyor).** `c4`'ün istediği "409 kanonik
  durum" alanı yok — `WorkObjectRevisionConflictError` `details` taşımıyor.
* **`TL-01.c4` yol sapması.** Kriter `GET /packages`, sevk edilen `GET /library`.

## Bir sonraki parti — öneri (ve bu kez ÖNCE ÖLÇ)

`TS-08.c3` *("düzeltilmiş mapping YENİ bir import revizyonu yaratır, eski rapor
tarihsel olarak okunabilir kalır")* — aynı doc 04 hattı, harness'ın yarısı hazır.
Yanına doc 05'ten `TL-02.c2` ve `TL-13.c3` bakılabilir.

**Ama önce ölç.** ADIM 48'in önerisi ölçülmediği için yanlıştı. Bir kriteri partiye
almadan önce **adlandırdığı davranışın gerçekten sevk edildiğini** `backend/src`'te
doğrula; sevk edilmemişse **sınıfı yanlıştır** ve test yazmak boşluğu gizler.

## Kalan borç (bu koşunun ölçümü)

| Sınıf | Kriter | Kim kapatır |
|---|---|---|
| A | 1 | adjudication + tek satır pin |
| B | **82** | test slice'ı (**tek sahibi bu**) |
| C | 6 | **kimse** — gerekçelenir, kapatılmaz |
| D | 32 | **ürün işi** |
| **açık toplam** | **121** | |

## Devralınan ritüel borcu

**Memory checkpoint ÜÇ slice'tır yazılamadı** (ADIM 47, ADIM 48 ×2, ADIM 49). Sebep
**ölçüldü ve yapısaldır** (#690): bu iş remote container'da yürüyor ve orada `ecc` /
`claude-mem` **kayıtlı değil** — yani borç **bu ortamdan kapatılamaz**, tekrar denemek
zaman kaybıdır.

İçerik hazır: **`docs/memory/PENDING_CHECKPOINTS.md`** (ADIM 47 + ADIM 48 metinleri
tam hâlde). **ADIM 49 girdisi oraya EKLENMELİDİR.** Bağlı bir ortamın ilk işi: üçünü
birden yaz, sonra o dosyayı **SİL** — kendini tüketen bir belgedir.

---

## Paste-ready resume prompt

```
ENTROPIA V18 — ADIM 50: kabul kriteri borç defteri, sınıf B parti 03

[[ Kendi ROL / OTURUM BAŞLANGICI / CANONICAL KAYNAK / TAVİZ VERİLEMEZ /
   PR DİSİPLİNİ bloklarınızı buraya aynen yapıştırın ]]

BASE: origin/main (DOĞRULA — `git fetch && git log --oneline origin/main -6`)
ADIM 49 landed: dış work object run provenance'ından 5 sınıf-B kriteri kapandı
(TL-12, TL-20, TS-11, TS-21, AOS-21). partial 118 → 113, sınıf B 87 → 82.

ÖNCE OKU (otorite sırası)
  1. docs/ADIM49_LANDED_KICKOFF.md (bu belge)
  2. docs/STAGE2_HANDOFF.md → "## Stage — ADIM 49" + "## Next"
  3. docs/PROJECT_HISTORY.md §ADIM 49
  4. docs/audit/acceptance_coverage_debt_ledger.md (ÜRETİLMİŞ defter)
  5. docs/generated/repository_facts.md (SAYISAL OTORİTE)

DURUM (doğrula, güvenme)
  · Blocker sayısı 1 (yalnız A-08), verdict BLOCKED. "READY" YAZMA.
  · Kalan borç: A=1 · B=82 · C=6 · D=32 (açık toplam 121).
  · P1-Gate3 KAPANMADI ve bu partiyle de kapanmayacak.

PARTİYİ SEÇMEDEN ÖNCE ÖLÇ — PAZARLIKSIZ
  ADIM 48'in kickoff'u TL-11.c3'ü "kapatılabilir" diye önerdi; YANLIŞTI (shared
  allocation admission'da fail-closed → o run kurulamaz). Bir kriteri partiye
  almadan önce adlandırdığı davranışın backend/src'te GERÇEKTEN sevk edildiğini
  doğrula. Sevk edilmemişse sınıfı yanlıştır; test yazmak boşluğu GİZLER.

ÖNERİLEN (yine de ölç): TS-08.c3 + TL-02.c2 + TL-13.c3

REUSE (yeniden yazma)
  · test_external_object_run_provenance.py::_attach_trade_log / ::_completed_run
  · test_backtest_manifest_pinning.py::_attach_trading_signal
  · test_backtest_persistence.py::_ready_composition / ::_e2e_bars / ::_count

SINIF DİSİPLİNİ
  · YALNIZ sınıf B. D'ye test YAZMA. C gerekçelidir.
  · B'den C/D'ye taşımak o TAVANI YÜKSELTİR → adjudication, PO işi.
  · RATCHET yalnız AŞAĞI iner. total_criteria bir TABANDIR — kriter SİLME.
  · Ürün kodu DEĞİŞMEZ.

DEVRALINAN ÜÇ AÇIK BULGU (kapatma, insan kararı)
  · TL-11.c3 kapatılamaz — sınıfı C görünüyor (allocation admission'da fail-closed).
  · TL-16 — c4'ün istediği 409 alanı yok → D görünüyor.
  · TL-01.c4 — yol sapması (GET /packages ↔ GET /library).

RİTÜEL BORCU — İLK İŞ
  Memory checkpoint ÜÇ slice'tır yazılamadı (ADIM 47, ADIM 48 ×2, ADIM 49).
  ecc + claude-mem BAĞLI MI diye ÖLÇ; bağlıysa önce o borcu kapat.

ÖLÇÜM TUZAKLARI (bu repoda gerçekten yaşandı)
  · pytest'i | tail'e BORULAMA — exit code tail'in olur.
  · Alt küme koşarken --no-cov EKLE; tam suite TEK çağrıda, ortada öldürme.
  · vitest: --no-file-parallelism ZORUNLU.
  · TEST_DATABASE_URL ile izole DB; sürücü postgresql+asyncpg://
  · Postgres yoksa DB testleri SESSİZCE SKIP olur. Remote container'da:
    `service postgresql start` + entropia rolü + `alembic upgrade head`
    (PYTHONIOENCODING=utf-8 LC_ALL=C.UTF-8, yoksa UnicodeDecodeError).
  · "Değişmedi" assert etmeden önce session.expire_all().
  · İKİ SLICE AYNI NUMARAYI ALABİLİR: kickoff dosyana yazmadan önce
    `grep -n '^# ADIM' docs/ADIM<n>_LANDED_KICKOFF.md` ile çakışma var mı bak.
    repository_facts --check bunu YAKALAMAZ (kuralı dosya başına bakar).

KAPANIŞ
  · Defteri (--write-ledger) ve baseline.json'u BU KOŞUNUN ölçümüyle tazele.
  · Kalan borcu SINIF BAZINDA raporla.
  · Blocker sayısı DEĞİŞMEZ (1: A-08). Verdict BLOCKED.
  · CLAUDE.md §Session CLOSING ritüelinin 6 maddesi +
    cd backend && uv run python ../scripts/generate_repository_facts.py --root .. --check
```
