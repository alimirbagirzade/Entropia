<!-- doc-status: historical -->
> **HISTORICAL KICKOFF — canlı olan `docs/ADIM69_LANDED_KICKOFF.md`'dir.**
> **CURRENT SLICE KICKOFF.** Sayısal gerçekler için otorite:
> `CLAUDE.md` §Current position + `docs/generated/repository_facts.md` (üretilmiş).

# ADIM 68 LANDED — kabul borcu batch 05 (doc 12) · sıradaki slice için kickoff

> Tam kayıt: `docs/PROJECT_HISTORY.md` §ADIM 68. Bu belge **devam noktasıdır**, kayıt değil.

## Neredeyiz

**Blocker sayısı DEĞİŞMEDİ (1 — yalnız A-08), verdict BLOCKED.** Ürün kodu değişmedi,
migration yok, OpenAPI değişmedi. Tavanlar `partial` **105 → 103**, `debt_class.B`
**74 → 72**. Açık kabul borcu: **A=1 · B=72 · C=6 · D=32 → 111**.

## Bu slice'ın öğrettikleri

1. **Bir önceki slice'ın harness'ı bir sonrakinin kriterini bedavaya kapatabilir.**
   `RD-09.c4` ADIM 54'te *"yalnız funding-enabled bir run ile kapanır"* diye bırakılmıştı;
   ADIM 67 o yolu kurdu, ve oradaki test bu clause'u birebir assert ediyordu. **Yeni test
   yazılmadı, mevcut düğüm cite edildi.** Yeni bir partiye başlarken **önce son iki slice'ın
   bıraktığı harness'ları oku** — kapanmayı bekleyen clause olabilir.
2. **Sınıf-B defteri bir iddia, ölçüm değil.** Doc 12'nin üç frontend clause'undan **ikisi**
   sevk edilmemiş davranış adlandırıyordu. Parti seçmeden önce `backend/src` / `frontend/src`
   içinde davranışın **var olduğunu** doğrula.
3. **Stub şeklini varsayma.** `{items, next_cursor}` yazdım, sevk edilen `{data, meta}`;
   sayfa hiç tablo render etmedi. Mevcut fixture'a (`DATASETS_PAGE`) bak.
4. **Frontend düğüm id'si `::` DEĞİL, ` > ` ile yazılır** — scanner `UNRESOLVED_NODE` verir.
5. **Clause toplamlarını tahmin etme**, `--report` çıktısından oku (1008 yazdım, 1007'ydi).

## Sıradaki tasarım işaretleri

- **Sınıf B'de 72 kriter, 19 belgeye dağılmış.** En yoğun: doc 05 (TL, 8 → `TL-01 TL-02
  TL-11 TL-13 TL-14 TL-16 TL-18 TL-22`), doc 07 (PC, 8), doc 04 (TS, 6), doc 02 (AT, 5),
  doc 03 (AOS, 5), doc 18 (AL, 5).
- **Defterde YEDİ açık "sınıfı şüpheli" bulgusu var** (`TL-11.c3`, `TL-16`, `TL-01.c4`,
  `RD-01.c4`, `RD-05.c5`, `RD-12.c4`, `RD-13.c4`). Bunları kapatmaya çalışma; sınıflarını
  düzeltmek bir **adjudication**'dır ve D tavanını yükseltir.
- **A-08 tek blocker**; yalnız insan denetimi kapatır (#514).

## Paste-ready resume prompt

```
ENTROPIA V18 — kabul borcu sınıf B, batch 06
TEK SLICE

ROL: Entropia V18 Principal Engineer. Yalnız bu slice.
[ORTAK SÖZLEŞME bloğunu buraya yapıştır]

TABAN: ADIM 68'in merge edildiği main. FARKLIYSA durma, farkı raporla, yeniden ölç.

ÖN KOŞUL — ÖLÇEREK SEÇ
  1. Son iki slice'ın kickoff'undaki REUSE ANCHOR listesini oku: yeni harness bir
     clause'u yeni kapatılabilir yapmış olabilir (ADIM 68'de RD-09.c4 böyle kapandı,
     sıfır yeni testle).
  2. docs/audit/acceptance_coverage_debt_ledger.md sınıf B satırlarını oku.
     Her aday için davranışın backend/src veya frontend/src'te SEVK EDİLDİĞİNİ doğrula.
     Edilmemişse sınıf D'dir: BULGUYU KAYDET, yeniden sınıflandırma (D tavanı yükselir).
  3. Partiyi TEK sayfa belgesi + TEK yüzey ile sınırla. Doc 05 (TL, 8 kriter) en yoğunu.

YAPILACAK
  Her clause için davranışı adlandıran testi yaz ve NEGATİF KONTROLDEN geçir
  (davranışı kaldır -> test kırmızı). Saklanan bir satırın değişmezliğini kanıtlıyorsan
  OKUMA YOLUNU da assert et (ADIM 67).

RATCHET
  acceptance_semantic_map.yaml -> scan --ratchet -> tavanları ÖLÇÜLEN değere İNDİR
  (asla yükseltme) -> --write-ledger -> repository_facts --check.
  Bir kriterin SON clause'u kapanıyorsa kriteri covered yap ve debt_class'ini KALDIR.
  Frontend düğüm id'si ' > ' ile yazılır. Clause toplamlarını --report'tan OKU.

DOKUNMA: sizing.py / booking.py / engine.py / portfolio_engine.py / backtest_engine.py
         jobs/research_data.py::_pin_member / ::_seal_bundle

TEST
  cd backend && uv run pytest -q --no-cov <hedef>   (ALT KÜMEDE --no-cov ZORUNLU)
  cd frontend && npx vitest run <dosya> --no-file-parallelism
  Sonra tam suite + ruff + mypy + openapi --check + repository_facts --check.
  `pytest | tail` KULLANMA (exit code tail'in olur).

COMMIT / PR
  DAL: test/closure-acceptance-batch-06
  commit: test(closure-acceptance): <kapatilan clause'lar>
  Draft PR aç. MERGE ETME (ayrı talimat gerekir). Kapanış ritüeli 6 madde.

FINAL RESPONSE — [ORTAK ŞABLON] + "kapanan clause'lar + inen tavanlar + kaydedilen bulgular"
DUR.
```
