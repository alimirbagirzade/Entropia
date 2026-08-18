<!-- doc-status: current -->
> **CANLI KICKOFF.** Bu belge en yeni slice'ın handoff'udur. Bir sonraki slice inince
> `historical`a demote edilir ve yerine yenisi geçer (`check_classification` CI'da doğrular).

# ADIM 75 LANDED — kabul borcu batch 07 (doc 07, frontend) · sıradaki slice için kickoff

> Tam kayıt: `docs/PROJECT_HISTORY.md` §ADIM 75. Bu belge **devam noktasıdır**, kayıt değil.

## Neredeyiz

Base **`0f0651d`** · alembic head **`0043_i08_registry_strategy_fks`** · `ENGINE_VERSION`
**değişmedi** · OpenAPI **değişmedi** · `SHARED_ALLOCATION_STATUS` = **`future_dev`** ·
migration **YOK** · **ürün kodu değişmedi**. **Blocker sayısı DEĞİŞMEDİ (1 — yalnız A-08),
verdict BLOCKED.**

Tavanlar `partial` **100 → 97**, `debt_class.B` **69 → 66**. Açık kabul borcu:
**A=1 · B=66 · C=6 · D=32 → 105**. Clause düzeyinde `covered` **1010 → 1015**, `uncovered`
**117 → 112**; `total_criteria` **383** (taban).

**Doc 07'nin sınıf-B işi BİTTİ.** İki batch (06 backend + 07 frontend) altı kriter kapattı:
`PC-07`, `PC-09`, `PC-11`, `PC-01`, `PC-17`, `PC-21`. Doc 07'de kalan açık satırlar yalnız
**bulgular** (`PC-02.c2`, `PC-20.c3`) ve iki sınıf-D Agent satırı (`PC-15`, `PC-16`).

## Bu slice'ın öğrettikleri

1. **YANLIŞ SEBEPLE KIRMIZIYA DÖNEN NEGATİF KONTROL HİÇBİR ŞEY KANITLAMAZ.** `PC-01.c3`'ün
   kontrolü iki kez düştü çünkü yamada olmayan enum üyeleri yazmıştım
   (`PackageValidationState.NOT_RUN`, `ApprovalState.PENDING`). Kırmızı gördüm ama kanıt
   yoktu. **Kontrolün hangi satırda düştüğünü oku** — beklediğin assertion değilse kontrol
   koşmamıştır. (ADIM 71'in "geçen kontrol yolun koşulmadığını söyler" dersinin ikizi.)
2. **Frontend'de bir metni assert etmeden önce O EKRANIN RENDER OLDUĞUNU doğrula.** PASSED
   satırı yalnız bir koşum kabul edildikten **sonra** ve projeksiyon daha yüksek bir attempt
   taşıdığında çiziliyor. Statik fixture ile test sayfayı sonsuza dek "çalışıyor" satırında
   bırakır ve hiç render olmayan bir metni bekler. **Route handler'ı fonksiyon yap**
   (`stubApi` bunu destekler) ve geçişi gerçekten sür.
3. **Negatif kapsam iddiaları yazılabilir ve totoloji olmak zorunda değil.** `PC-21.c3`
   ("yüzey repaint/validation/approval hakkında hiçbir şey iddia etmemeli") tüm render
   edilmiş yüzeyi yedi kalıba karşı pinliyor; fazla-iddia eklenince kırmızıya dönüyor. Şart:
   kalıpları **adlandır** ve kontrolü **gerçekten koş**.
4. **"Yokluk" iddiası okuma yolundan sürülmeli.** `PC-01.c3` "render etmek revizyon
   yazmaz" diyor — test yüzeyin kullandığı okuma yolunu iki kez sürüp tabloları sayıyor.
   Adı doğru görünen mevcut test (`test_fresh_request_projects_an_empty_chain`) isteği önce
   DRAFT'a sürdüğü için **başka bir şeyi** kanıtlıyordu.
5. **Bir sayfa belgesini iki yüzeyde bitirmek işe yarıyor.** Batch 06 backend'i, batch 07
   frontend'i aldı; `PC-01` yalnız ikisi birlikte kapanabildi. Sonraki belgelerde de
   **"son açık clause hangi yüzeyde?"** sorusu parti sınırını çizmeli.

## Bu slice'ın bıraktığı yeniden kullanım çapaları

| Düğüm / sembol | Nerede | Ne işe yarar |
|---|---|---|
| `stubPassedRun()` | `frontend/src/test/preCheck.test.tsx` | admission → landed geçişini süren route-handler kalıbı (POST'tan önce/sonra farklı cevap) |
| `PASSED_SCAN` / `REQUEST_DETAIL_PASSED` / `REQUEST_DETAIL_NO_SCAN` | aynı dosya | PASSED ve scan'siz fixture'lar |
| `… > closing Pre-Check cancels nothing and reopening re-reads the server (PC-17.c4)` | `createPackage.test.tsx` | "kapanışta hiç istek gitmez" (non-GET sayımı) + "yeniden açılış sunucudan okur" |
| `test_reading_the_precheck_surface_persists_no_package_revision` | `test_create_package_persistence.py` | okuma yolunu sürüp tablo sayan "yokluk" kalıbı |
| `stubApi` fonksiyon handler'ı | `frontend/src/test/helpers/apiStub.ts` | durum değiştiren sunucu simülasyonu (zaten vardı, ilk kez böyle kullanıldı) |

## Açık bulgular — bunları kapatmaya çalışma (DOKUZ)

`TL-11.c3`, `TL-16`, `TL-01.c4`, `RD-01.c4`, `RD-05.c5`, `RD-12.c4`, `RD-13.c4`,
**`PC-20.c3`**, **`PC-02.c2`**.

Doc 07'nin ikisi farklı şekilde açık ve **fark önemli**:
- **`PC-20.c3` KURULABİLİR ama sevk edilmemiş** (sınıf D): restore generic
  `_restore_registry_target`'tan geçer, bayatlık işareti koymaz → restore edilen istek Send
  kapısını **geçer**. Ürün işi.
- **`PC-02.c2` HİÇ ERİŞİLEMEZ** (sınıf C şeklinde): overlay yalnız `detail !== null` iken
  render edilir, boş kaynaklı istek ise route'ta DB'den önce reddedilir → boş-girdi Pre-Check
  sonucunun çizilebileceği ekran **yok**.

## Sıradaki tasarım işaretleri

- **Sınıf B'de 66 kriter kaldı, doc 07 tükendi.** Sıradaki yoğun belgeler: **doc 05** (TL, 8 —
  ama `TL-01`/`TL-11`/`TL-16` şüpheli işaretli, yani gerçekte **5**), **doc 04** (TS, 6),
  **doc 02** (AT, 5), **doc 03** (AOS, 5), **doc 18** (AL, 5).
- **Doc 04 (TS, 6) muhtemelen en temiz sıradaki parti** — hiçbir satırı şüpheli işaretli değil.
  Doc 05'e girersen üç şüpheli satırı **saymadan** planla.
- **Parti sınırını "son açık clause hangi yüzeyde?" ile çiz**, belgeye göre değil. Bir kriterin
  son clause'unu kapatmayan clause'lar defteri iyileştirir ama **tavanı indirmez**.
- **A-08 tek blocker**; yalnız insan denetimi kapatır (#514).
- `C2` hâlâ **G9** (ADR-0002 §6/§8 amendment) ve **G13** (P10 equity noktası) imzasız insan
  kapılarının arkasında — `docs/ADIM71_LANDED_KICKOFF.md` §Sıradaki.

## Paste-ready resume prompt

```
ENTROPIA V18 — kabul borcu sınıf B, batch 08
TEK SLICE

ROL: Entropia V18 Principal Engineer. Yalnız bu slice.
[ENTROPIA ORTAK SÖZLEŞME bloğunu uygula]

TABAN: ADIM 75'ün merge edildiği main.
  SHA'yı doğrula AMA ETİKETE GÜVENME — numarayı
  `grep '^## ADIM' docs/PROJECT_HISTORY.md | tail -1` ile ÖĞREN (ADIM 72/73 dersi:
  merge edilmiş ad kazanır, sıra beklerken numaran taşınabilir).

ÖN KOŞUL — ÖLÇEREK SEÇ
  1. docs/ADIM75_ ve ADIM73_LANDED_KICKOFF.md'deki REUSE ANCHOR tablolarını oku
     (ADIM 74 = R2 + R3, ayrı bir eksen — kabul borcu partisi değil).
  2. Kriterin ADLANDIRDIĞI davranış backend/src veya frontend/src'te SEVK EDİLMİŞ Mİ?
     grep ile doğrula. Değilse — ya da durum HİÇ KURULAMIYORSA — sınıf B değildir:
     bulguyu `notes`'a ölçümüyle yaz, YENİDEN SINIFLANDIRMA, başka kriter seç.
  3. "Son açık clause'u benim yüzeyimde mi?" Değilse tavan İNMEZ.
  4. DOKUZ açık şüpheli bulgu var (TL-11.c3, TL-16, TL-01.c4, RD-01.c4, RD-05.c5,
     RD-12.c4, RD-13.c4, PC-20.c3, PC-02.c2) — bunları kapatmaya çalışma.

ÖNERİLEN PARTİ: doc 04 (TS, 6 kriter, hiçbiri şüpheli işaretli değil).
  Doc 07 BİTTİ — orada sınıf B kalmadı, tekrar bakma.

YAPILACAK
  Her clause için davranışı adlandıran testi yaz ve NEGATİF KONTROLDEN geçir:
  davranışı ÜRÜNDEN kaldır -> test KIRMIZI olmalı VE KIRMIZININ HANGİ ASSERTION'DA
  olduğunu OKU (yanlış sebeple düşen kontrol hiçbir şey kanıtlamaz — ADIM 75 dersi).
  Frontend metni assert etmeden önce o ekranın gerçekten render olduğunu doğrula.
  Frontend düğüm id'si `::` DEĞİL ` > ` ile yazılır (UNRESOLVED_NODE).

RATCHET
  acceptance_semantic_map.yaml -> güncelle (clause evidence kriter düzeyindeki
  test_evidence'a DA eklenmeli, AXIS_NOT_IN_EVIDENCE).
  Son clause kapanıyorsa kriteri `covered` yap ve `debt_class`'i KALDIR.
  python3 docs/audit/acceptance_semantic_scan.py --root . --ratchet docs/audit/acceptance_coverage_baseline.json
  Tavanları ÖLÇÜLEN değere İNDİR (partial 97 / B 66 taban). total_criteria = 383 TABAN.
  Clause toplamlarını TAHMİN ETME, --report'tan oku. Sonra --write-ledger + repository_facts.

DOKUNMA
  sizing.py / booking.py / engine.py / portfolio_engine.py / backtest_engine.py
  jobs/research_data.py::_pin_member / ::_seal_bundle

TEST
  cd backend && uv run pytest -q            (tam suite = coverage kapısı)
  alt kümede --no-cov EKLE. `pytest | tail` KULLANMA.
  cd frontend && npx vitest run <dosya> --no-file-parallelism   (alt küme)
  repository_facts'i TAM SUITE KOŞMADAN ÖNCE tazele — suite koşarken tazelemek
  tests/contract/test_repository_facts_guard.py'yi sahte kırmızı yapar (ADIM 73 dersi).

COMMIT / PR
  DAL: test/closure-acceptance-batch-08
  commit: test(closure-acceptance): <kapatilan clause'lar>
  AI ATTRIBUTION YOK. Draft PR aç, MERGE ETME. Kapanış ritüeli 6 madde.

FINAL RESPONSE
  Kapanan clause'lar + inen tavanlar + KAYDEDİLEN BULGULAR + koşan kapıların GERÇEK
  sayıları + dürüst sınırlar. DUR.
```
