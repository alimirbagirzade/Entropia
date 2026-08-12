<!-- doc-status: current -->
# ADIM 48 LANDED — K-6b: odak halkasının kontrastı (WCAG 1.4.11) · sıradaki slice için kickoff
# ADIM 48 LANDED — kabul borcu sınıf B, parti 01 · sıradaki slice için kickoff

> **Bu belge ADIM 48 kapanışında yazıldı.** Sayısal otorite bu belge DEĞİL →
> `docs/generated/repository_facts.md` (üretilmiş, CI'da `--check` bloklayıcı).
> Tam kayıt: `docs/PROJECT_HISTORY.md` §ADIM 48.

## Neredeyiz

Base `7dd1dfe` (#682, ADIM 47). Migration yok, `ENGINE_VERSION` değişmedi, OpenAPI
değişmedi, `SHARED_ALLOCATION_STATUS` = `future_dev` (containment KAPALI).
**Blocker sayısı DEĞİŞMEDİ — 1 (yalnız A-08). RC verdict BLOCKED.**

Bu slice **presentation-only** idi ve **tek bir CSS deklarasyonu** sevk etti.

## Bu slice ne bıraktı (reuse anchor'ları, tam sembol adlarıyla)

- **`frontend/src/styles/global.css` `:focus-visible`** — uygulamadaki odak halkasının
  **TEK** tanımı. `outline: 2px solid var(--accent)` → **`var(--text)`**. Kuralın üstündeki
  yorum artık ölçülmüş oranları ve zemin kümesini taşıyor; sayı arıyorsan oradan oku.
  **Yeni bir odak stili yazma** — bileşene özel bir halka eklemek yerine bu kuraldan geçir,
  yoksa kontrast tekrar ölçülmemiş bir yere kaçar.
- **`docs/audit/a11y_screen_reader_audit_results.md` §6** — **K-6 İKİYE ayrıldı:**
  - **`K-6b` KAPANDI (2026-08-12)** — ölçülü. Satır, değişiklikten *sonraki* yedi zemin
    oranını taşır.
  - **`K-6a` AÇIK** — *"bir insan halkayı görebiliyor mu"*. **Yalnız A-08 kapatabilir.**
    Sayım tablosundaki satır da `K-6a` olarak yeniden adlandırıldı (ölçen prob odur).
  - *"K-2 … K-7 bilerek kapı değildir"* paragrafı **K-6b'yi tek istisna** olarak tarif eder
    ve istisnanın nerede olduğunu söyler. Yeni bir K-N kapatmadan önce o paragrafı oku.
- **Ölçüm yöntemi** — sRGB linearizasyonu + `(L1+0.05)/(L2+0.05)`. Kickoff'un verdiği
  sayılar kabul edilmedi, **sıfırdan yeniden hesaplandı** ve birebir tuttu. Bir sonraki
  kontrast kalemi için de aynısını yap: **verilen sayıyı doğrulamadan kod yazma.**

## Ölçülen oranlar (halka `#222222`, değişiklikten sonra)

| Zemin | Nerede | Oran |
|---|---|---:|
| `#ffffff` | gövde, kartlar | 15.91 : 1 |
| `#f5f5f5` | | 14.59 : 1 |
| `#e8e8e8` | başlık çubuğu | 12.98 : 1 |
| `#00a9e8` | `.dropdown-blue` paneli | 5.94 : 1 |
| `#8f8f8f` | `.dropdown` paneli | 4.92 : 1 |
| `#8b8b8b` | `.run-button:disabled` | 4.67 : 1 |
| `#0092c8` | `.menu-blue:hover` — **en kötü zemin** | 4.50 : 1 |

Öncesi (`#00a9e8`): beyazda **2.68:1**, `#f5f5f5`'te **2.46:1**, `.dropdown-blue`
üzerinde **1.00:1**. Uygulamadaki **15 zeminin hiçbirinde** 3:1 geçilmiyordu.

## Bir sonraki oturumun ilk işi (borç)

1. **Memory checkpoint borcu — İKİ slice birden.** `ecc` ve `claude-mem` MCP sunucuları
   ADIM 47'de de ADIM 48'de de **bağlı değildi** → kapanış ritüelinin 4. maddesi **üst üste
   iki oturumdur eksik**. Bağlı bir oturumda **ADIM 47 + ADIM 48** için birden yaz.
2. **CI'ın söylediğini oku.** `npm run visual` ve `npm run a11y` bu oturumda
   koşturulamadı (ortam ağ politikası Docker Hub blob CDN'ini **403** ile reddediyor).
   PR'ın `e2e.yml::e2e` ve `e2e.yml::a11y` job'ları **otoritedir** — job log'undan
   gerçekten koştuğunu doğrula. **Görsel diff çıkarsa tabanı GÜNCELLEME:** kural odak
   dışına sızmış demektir, selector'ı daralt.

## Kapatılmayan, kapatıldığı iddia EDİLMEYEN

- **K-6a** — insan gözü ister. Ölçülebilir kontrast ≠ görülebilirlik.
- **A-08** — defter **0/4**, dört çıkış kriteri de ☐, #514 kanıtsız kapalı. Hiçbir belge
  `Complete`/`PASS`/`Done` göstermez, *"açık issue #514'te izleniyor"* da yazılmaz.
- **D-10** — 45 accent-blue metin düğümü, **1.4.3** ekseni, imzalı kalıcı sapma. Bu slice
  o ekseni **değiştirmedi**; `--accent` token'ına dokunulmadı.
- **RC §6.7 kalanları** — P11-1 (branch protection, **insan kararı**), P11-6b, P11-3b,
  P8-B3b, P4-3, P10-B6, P1-Gate3, P10-B3/B4/B5.
- **`POST /library/{id}/validation-runs` 201'de** — ADIM 47'nin açık bıraktığı ayrışma.
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
ENTROPIA — sıradaki slice

CLAUDE.md §Session START protokolünü uygula: önce `git fetch` + `git log --oneline
origin/main -6` ile NEYİN GERÇEKTEN MERGE OLDUĞUNU doğrula (handoff STALE-BY-DEFAULT),
sonra docs/ADIM48_LANDED_KICKOFF.md → docs/STAGE2_HANDOFF.md → docs/STAGE_BUILD_PLAN.md
sırasıyla oku. Sayısal otorite docs/generated/repository_facts.md.

DURUM: ADIM 48 landed — K-6b (odak halkası kontrastı, WCAG 1.4.11) KAPANDI:
frontend/src/styles/global.css `:focus-visible` halkası var(--accent) → var(--text).
Ölçülen: beyazda 15.91:1, en kötü zemin (#0092c8, .menu-blue:hover) 4.50:1 — hepsi ≥3:1.
Öncesi 2.68:1 / 2.46:1 idi. Presentation-only; --accent token'ına, dolgu/kenarlık/link
paletine, route/react-query key/OCC/Idempotency/hook/SSE/lib'e DOKUNULMADI.
Blocker sayısı DEĞİŞMEDİ (1 — yalnız A-08), verdict BLOCKED.

İLK İŞ — İKİ BORÇ:
(1) MEMORY CHECKPOINT BORCU İKİ SLICE'TIR. ecc + claude-mem ADIM 47'de de 48'de de bağlı
    değildi. Bağlıysan ADIM 47 VE ADIM 48 için birden yaz; değilse bunu yine kaydet.
(2) ADIM 48'in PR'ında `e2e.yml::e2e` (görsel) ve `e2e.yml::a11y` (axe) job LOG'larını oku —
    bu iki kapı yerelde KOŞTURULAMADI (ortam Docker Hub blob CDN'ine 403 veriyor), otorite
    CI'dır. Görsel diff varsa TABANI GÜNCELLEME: kural odak dışına sızmıştır, selector'ı daralt.

KAPATILMADI, KAPATILDIĞI İDDİA EDİLMİYOR:
· K-6a (bir insan halkayı GÖREBİLİYOR mu) — AÇIK, yalnız A-08 kapatabilir.
· A-08 — defter 0/4, dört çıkış kriteri de ☐, #514 kanıtsız kapalı. Hiçbir belgeye
  Complete/PASS/Done yazma; "açık issue #514'te izleniyor" da yazma.
· D-10 — 45 accent-blue düğüm, 1.4.3 (METİN) ekseni. K-6b 1.4.11'di; AYRI ölçüt.
· RC §6.7: P11-1 (branch protection, İNSAN KARARI), P11-6b, P11-3b, P8-B3b, P4-3,
  P10-B6, P1-Gate3, P10-B3/B4/B5. · /library/{id}/validation-runs hâlâ 201.

Planlı ana eksen hâlâ: PR B — ItemParticipant adaptörü + jobs/backtest_engine.py:298
call site. ADIM 35 §4.1'in (c) engelini kapattı; (a) faz-bölünmüş bar ve (b) book-etmeyen
değerlendirme girişi run_engine'in gövdesine dokunur → ADR §16 İNSAN KAPISI + ADR
amendment'ı gerekir, o kapıdan geçmeden BAŞLAMA.

Kapanışta ritüelin altısı (CLAUDE.md §Session CLOSING). Verdiğin sayıları KABUL ETME,
yeniden ölç. Frontend doğrulama: cd frontend && npm run lint && npm run typecheck &&
npm test -- --no-file-parallelism (vitest'te --no-file-parallelism ZORUNLU).
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
