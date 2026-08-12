<!-- doc-status: historical -->
> **SUPERSEDED — sonrasında ADIM 49 ve ADIM 50 (2026-08-12).** Bu belgeden sonra iki
> slice landed: **ADIM 49** (`docs/ADIM49_KICKOFF.md`, RC §6.5 / K-2 + K-4, PR #685) ve
> **ADIM 50** (`docs/ADIM50_LANDED_KICKOFF.md`, K-6b odak halkası kontrastı, #688).
> **Canlı kickoff ADIM 50'dir.** Aşağısı ADIM 48 kapanışındaki durumu kaydeder; sayıları
> ve "sıradaki iş" maddeleri bayat olabilir. **Değişmeyen:** blocker sayısı 1 (yalnız
> A-08), verdict BLOCKED.

# ADIM 48 LANDED — kabul borcu sınıf B, parti 01 · sıradaki slice için kickoff

> **Bu belge ADIM 48 kapanışında yazıldı.** Sayısal otorite bu belge DEĞİL →
> `docs/generated/repository_facts.md` (üretilmiş, CI'da `--check` bloklayıcı).
> Tam kayıt: `docs/PROJECT_HISTORY.md` §ADIM 48.

## Neredeyiz

**Blocker sayısı 1 (yalnız A-08), verdict BLOCKED.** ADIM 48 bir blocker kalemi
değildi: ADIM 42'nin ürettiği borç defterini **işlemeye başladı**. Doc 05 (Trade Log)
backend yüzeyinden **sekiz sınıf-B kriteri** kapandı → **partial 126 → 118**,
**sınıf B 95 → 87**. **Ürün kodu değişmedi** (tek satır bile), migration yok,
`ENGINE_VERSION` sabit, OpenAPI değişmedi.

Kapanan sekiz: `TL-03` · `TL-06` · `TL-07` · `TL-08` · `TL-15` · `TL-17` · `TL-21` ·
`TL-23`.

## Bu slice'ın bıraktıkları (reuse anchor'ları — tam sembol adlarıyla)

| Anchor | Ne için |
|---|---|
| `tests/integration/test_trade_log_persistence.py::_count_rows` · `::_count_audits` | Satır/audit sayacı. **"Hiçbir şey yazılmadı" iddiası ancak sayaçla kanıtlanır** — exception tipini assert etmek yetmez |
| `tests/integration/test_trade_log_persistence.py::ADMIN` · `::SUPERVISOR` | Doc 05 hattında rol aktörleri; `_seed_principals` artık dördünü de seed eder |
| `tests/integration/test_trade_log_persistence.py::test_replayed_pin_creates_no_duplicate_item_or_pin_event` | Idempotency replay deseni: **tüketilmiş `expected_row_version` bilerek yeniden gönderilir** — zarf olmadan bu çağrı 409'dur |
| `docs/audit/acceptance_coverage_baseline.json` §`adjudication.class_B_batches_are_deliberately_small` | Parti disiplininin yazılı gerekçesi |

## Tavizsiz kurallar (bu slice'ta kanıtlandı)

1. **İşaretlemek ≠ kapsamak.** Vakumda geçebilecek her assertion **negatif kontrolden**
   geçirildi (kanıtı `PROJECT_HISTORY.md` §ADIM 48). Bir kriteri `covered` yapmadan önce
   *"bu assertion, davranış kaldırılınca düşer mi?"* sorusunu **koş**, tahmin etme.
2. **RATCHET YALNIZ AŞAĞI İNER.** `ceilings.total_criteria` bir **TABANDIR** — rahatsız
   edici bir `partial` kriteri silerek tavan düşürmek yasaktır, kapı yakalar.
3. **Sınıflar AYRI ratchet'lenir.** Sekiz B kapatıp sekiz D eklemek net yeşil vermez.
   Bir kriteri B'den D'ye taşımak **D tavanını yükseltir** → bu bir adjudication'dır,
   bir test slice'ının kararı değil.
4. **Sınıf D'ye test yazma.** Kriterin adlandırdığı kod/alan/hata sınıfı yoksa test
   yazmak boşluğu **gizler**. Issue aç, raporda AÇIK bırak.
5. **Yeni `partial`/`uncovered` kriter eklersen `debt_class` ZORUNLU** — kapı
   sınıfsızı kırmızıya çevirir.

## Bir sonraki parti — en yüksek değerli üçlü

**`TL-11.c3` + `TL-12.c3` + `TL-20.c3` birlikte alınmalı.** Üçü de aynı eksik
makineyi ister: **Trade Log içeren bir kompozisyon üzerinde tamamlanmış bir Backtest
Run**. Repoda hiçbir test bir `trade_log`'u run kompozisyonuna sokmuyor; harness bir
kez kurulunca üç clause birden kapanır (ve doc 04'ün `TS-11`/`TS-21` ikizleri de aynı
deseni paylaşır).

Ölçülmüş dayanaklar (bunlar **var**, sınıf B doğru):
* `application/commands/backtest_run_context.py::_external_entry` — `MainboardItemKind.TRADE_LOG`
  dalı manifest'e `work_object_revision_id` + `canonical_record_batch` pinliyor.
* `tests/integration/test_backtest_persistence.py::_ready_composition` — strateji
  kompozisyonu kurucusu; **yeniden yazma, genişlet.**
* `tests/integration/test_backtest_persistence.py::_e2e_bars` — determinist bar akışı.

## Açık bırakılan iki BULGU (karar insan/PO'da — agent kapatamaz)

* **`TL-16` sınıfı ŞÜPHELİ (B yazıyor, D görünüyor).** `c4` *"409 zarfı sunucunun
  kanonik güncel durumunu taşır"* diyor; `shared/errors.py::WorkObjectRevisionConflictError`
  **`details` taşımıyor** ve `commands/trade_log.py` onu **argümansız** raise ediyor.
  Hiçbir test kapatamaz. Yeniden sınıflandırılmadı çünkü **D tavanını yükseltirdi.**
* **`TL-01.c4` bir yol sapması.** Kriter `GET /packages` diyor; sevk edilen katalog
  `GET /library` (`library_query.list_packages`). Sınıf A ekseni; adjudication ister.

## Kalan borç (bu koşunun ölçümü)

| Sınıf | Kriter | Kim kapatır |
|---|---|---|
| A | 1 | adjudication + tek satır pin |
| B | **87** | test slice'ı (**tek sahibi bu**) |
| C | 6 | **kimse** — gerekçelenir, kapatılmaz |
| D | 32 | **ürün işi**; birkaçı önce PO kararı ister |
| **açık toplam** | **126** | |

Doc 05'in sınıf-B kalıntısı **9 kriter** (`TL-01 · TL-02 · TL-11 · TL-12 · TL-13 ·
TL-14 · TL-16 · TL-20 · TL-22`) + `TL-18` (uncovered).

---

## Paste-ready resume prompt

```
ENTROPIA V18 — ADIM 49: kabul kriteri borç defteri, sınıf B parti 02

[[ Kendi ROL / OTURUM BAŞLANGICI / CANONICAL KAYNAK / TAVİZ VERİLEMEZ /
   PR DİSİPLİNİ bloklarınızı buraya aynen yapıştırın ]]

BASE: origin/main (DOĞRULA — `git fetch && git log --oneline origin/main -6`)
ADIM 48 landed: doc 05 backend yüzeyinden 8 sınıf-B kriteri kapandı
(TL-03/06/07/08/15/17/21/23). partial 126 → 118, sınıf B 95 → 87.

ÖNCE OKU (otorite sırası)
  1. docs/ADIM48_LANDED_KICKOFF.md (bu belge)
  2. docs/STAGE2_HANDOFF.md → "## Stage — ADIM 48" + "## Next"
  3. docs/PROJECT_HISTORY.md §ADIM 48
  4. docs/audit/acceptance_coverage_debt_ledger.md (ÜRETİLMİŞ defter)
  5. docs/generated/repository_facts.md (SAYISAL OTORİTE)

DURUM (doğrula, güvenme)
  · Blocker sayısı 1 (yalnız A-08), verdict BLOCKED. "READY" YAZMA.
  · Kalan borç: A=1 · B=87 · C=6 · D=32 (açık toplam 126).
  · P1-Gate3 KAPANMADI ve bu partiyle de kapanmayacak.

ÖNERİLEN PARTİ (gerekçesi ADIM 48 kickoff'unda)
  TL-11.c3 + TL-12.c3 + TL-20.c3 — üçü de "Trade Log içeren kompozisyon üzerinde
  TAMAMLANMIŞ Backtest Run" harness'ını ister; harness bir kez kurulunca üçü
  birden kapanır. Reuse: backtest_run_context.py::_external_entry (TRADE_LOG dalı
  manifest'i GERÇEKTEN pinliyor) · test_backtest_persistence.py::_ready_composition
  (GENİŞLET, yeniden yazma) · ::_e2e_bars.
  Aynı harness doc 04'ün TS-11 / TS-21 ikizlerini de açar.

SINIF DİSİPLİNİ — PAZARLIKSIZ
  · YALNIZ sınıf B. Sınıf D'ye test YAZMA (boşluğu gizler). C gerekçelidir.
  · Bir kriteri B'den D'ye taşımak D TAVANINI YÜKSELTİR → adjudication, PO işi.
  · RATCHET yalnız AŞAĞI iner. total_criteria bir TABANDIR — kriter SİLME.
  · Ürün kodu DEĞİŞMEZ. Kusur bulursan issue aç, AÇIK bırak, sınıfını D yaz.

DEVRALINAN İKİ AÇIK BULGU (kapatma, insan kararı)
  · TL-16 sınıfı şüpheli: c4'ün istediği "409 kanonik durum" alanı YOK
    (WorkObjectRevisionConflictError details taşımıyor) → B değil D görünüyor.
  · TL-01.c4 yol sapması: kriter GET /packages diyor, sevk edilen GET /library.

TAVİZ VERİLEMEZ
  · "Kapsandı" işaretlemek kapsamak DEĞİLDİR — her kalem için kapsayan testin
    o kriteri GERÇEKTEN kanıtladığını NEGATİF KONTROLLE göster.
  · OCC (If-Match / expected_*_version / X-*-Version), Idempotency-Key, route
    YOLLARI, react-query key'leri, ENGINE_VERSION DEĞİŞMEZ.
  · A-08 / #514'ün durumunu DEĞİŞTİRME — insan kapısı.
  · Yeşile zorlama YOK.

KAPSAM DIŞI
  · A-08 / #514 · P11-1 (branch protection) · §6.5 K-2..K-6 · §6.6 #558/#559
  · post-V1 PR B2a/B2b (ADR §16 insan kapısı)

ÖLÇÜM TUZAKLARI (bu repoda gerçekten yaşandı)
  · pytest'i | tail'e BORULAMA — exit code tail'in olur; çıktıyı dosyaya yaz, $?'i AYRI oku.
  · Alt küme koşarken --no-cov EKLE; tam suite TEK çağrıda, ortada öldürme.
  · vitest: --no-file-parallelism ZORUNLU.
  · TEST_DATABASE_URL ile izole DB; sürücü postgresql+asyncpg://
  · Postgres yoksa DB testleri SESSİZCE SKIP olur — "geçti" sanma. Remote
    container'da `service postgresql start` + entropia rolü ile ayağa kalkar.
  · docs PR'ı öncesi: git diff origin/main -- docs/ | grep '^-## ' → BOŞ olmalı.

KAPANIŞ
  · Defteri (--write-ledger) ve baseline.json'u BU KOŞUNUN ölçümüyle tazele.
  · Kalan borcu SINIF BAZINDA raporla — bir sonraki parti planlanabilsin.
  · Blocker sayısı DEĞİŞMEZ (1: A-08). Verdict BLOCKED.
  · CLAUDE.md §Session CLOSING ritüelinin 6 maddesi +
    cd backend && uv run python ../scripts/generate_repository_facts.py --root .. --check
```
