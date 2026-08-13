<!-- doc-status: historical -->
> **HISTORICAL RECORD — bu belge GÜNCEL GERÇEK DEĞİLDİR.** Yazıldığı andaki durumu
> kaydeder; SHA'lar, sayılar ve "next" maddeleri bayat olabilir.
> **SUPERSEDED — canlı kickoff artık `docs/ADIM57_LANDED_KICKOFF.md`** (K-3
> adjudicated, imzalı karar D-11 — kod yok). Aradaki iki slice: **ADIM 55**
> (agentmemory sunucusu yerele alındı) ve **ADIM 56** (A-08 / SR-2 oturum 1 kaydı).
> **Değişmeyen:** blocker sayısı 1
> (yalnız A-08), verdict BLOCKED. Sayısal otorite bu belge DEĞİL →
> `CLAUDE.md` §Current position + `docs/generated/repository_facts.md` (üretilmiş).

# ADIM 54 LANDED — kabul borcu sınıf B, parti 03 (Research Data revizyon değişmezliği)

Tam kayıt: `docs/PROJECT_HISTORY.md` §ADIM 54.

## Neredeyiz

Base `2a90fe3` (#694). **Ürün kodu DEĞİŞMEDİ**, migration yok, `ENGINE_VERSION`/OpenAPI
sabit. **`partial` 113 → 111, `debt_class.B` 82 → 80.** Kapananlar: `RD-04`, `RD-06`.
**Blocker 1 (yalnız A-08), verdict BLOCKED.**

## Reuse anchor'ları (birebir semboller)

| Anchor | Ne için |
|---|---|
| `tests/integration/test_research_revision_immutability.py::_drive_to_approved` | DRAFT→ANALYZING→VERIFIED→APPROVED yürüyüşü; **zaman politikasını komutla kurar** (kolon set etmek yetmez) ve onayı **ADMIN** ile yapar |
| `::_dataset` | `(root, market_entity_id)` döndürür — market id **her sonraki revizyonda tekrar gerekir**, onay bağı fail-closed yeniden çözer |
| `::_head` | head revizyonu tazeden okur |
| `rd_jobs.run_analysis(load_and_parse=…, write_native=…)` | ikisi de **async**; `write_native` **str digest** döndürür |

## DOKUNMA / DİKKAT (bu slice'ta ölçüldü)

1. **Kriterin sözü ≠ sevk edilen davranış.** `RD-04` *"stale işaretlenir"* diyor; sevk
   edilen daha güçlü ve yapısal. **Bayrak icat etme**, sevk edileni assert et.
2. **Yanlış refüzü kanıtlama.** Yeni revizyonun zaman politikası kurulmadan onay
   denenirse *eksik-politika* kapısı düşer, durum makinesi değil. Onay **Admin-only** —
   `OWNER` ile rol kapısına takılırsın.
3. **ORM nesnesine `rollback` sonrası dokunma** — expire olur, lazy IO `MissingGreenlet`
   verir. `entity_id`/`revision_id`'yi **erkenden `str()`** al.
4. **PARTİ SEÇMEDEN ÖNCE ÖLÇ.** Defterde **beş** açık bulgu var; her partide en az bir
   yanlış sınıflandırma çıktı. Kriterin adlandırdığı alan `backend/src`'te yoksa sınıfı
   yanlıştır — **yeniden sınıflandırma, tavan yükseltir**; bulgu olarak yaz.

## Sıradaki partinin doğal ilk kalemi — `RD-09.c4`

Kapatılabilir, bu partide **bilerek** açık bırakıldı. Gerekenler ölçüldü:
* manifest research revizyonunu **yalnız funding kaynağı** üzerinden pinler
  (`backtest_run_context::_research_entries`);
* readiness, funding revizyonunun **stratejinin KENDİ market revizyonuna** bağlı olmasını
  ve `instrument_mapping_ref` taşımasını ister (ikisi de blocker verdi);
* worker native asset satırları çözülmezse `RUN_FAILED_FUNDING_SOURCE_INVALID` verir —
  `run_backtest(load_funding_rows=…)` enjeksiyonu **vardır**.

`_ready_composition` kendi market'ini içeride yaratır; research dataset'i o market'e
bağlamak için helper'a bir kanca gerekir. Bu slice denedi ve **geri aldı** — bir sonraki
parti kancayı kalıcı olarak eklemeli.

## Kalan borç

| Sınıf | Kriter | Kim kapatır |
|---|---|---|
| A | 1 | adjudication |
| B | **80** | test slice'ı |
| C | 6 | **kimse** |
| D | 32 | ürün işi |
| **açık** | **119** | |

---

## Paste-ready resume prompt

```
Entropia'da yeni bir oturum. Önce CLAUDE.md §Session START protokolünü uygula:
1. git fetch && git log --oneline origin/main -6 — ADIM 54 merge edildi mi, ADIM
   numaram alınmış mı? DOĞRULA (bu depoda numara çakışması DEFALARCA yaşandı).
2. Otorite: docs/ADIM54_LANDED_KICKOFF.md → docs/STAGE2_HANDOFF.md → PROJECT_HISTORY §ADIM 54.
3. Hafıza: node scripts/memory_index.mjs --write (taze container'da store BOŞ).

PARTİ: kabul borcu sınıf B, parti 04. İlk kalem RD-09.c4 (gerekçe ve anchor'lar
ADIM 54 kickoff'unda). Sonra doc 07 (PC-*, 8 kriter) ya da doc 16 (RH-*, 7 kriter).

PAZARLIKSIZ
· PARTİ SEÇMEDEN ÖNCE ÖLÇ — kriterin adlandırdığı alan/kod/araç backend/src'te
  sevk edilmemişse sınıfı YANLIŞTIR. Defterde beş açık bulgu var; her partide
  en az bir tane daha çıktı.
· Yeniden SINIFLANDIRMA (B→C/D) TAVAN YÜKSELTİR → adjudication, PO işi. Bulgu yaz.
· Sınıf D'ye test yazma (boşluğu gizler). RATCHET yalnız AŞAĞI iner.
· "Kapsandı" işaretlemek kapsamak DEĞİLDİR — her assertion'ı NEGATİF KONTROLDEN geçir.
· Ürün kodu DEĞİŞMEZ. Yarım kanıtla kriter kapatma — partial bırak, gerekçesini yaz.
· A-08 blocker AÇIK, verdict BLOCKED. Hiçbir belgeye Complete/PASS/Done yazma.

ÖLÇÜM TUZAKLARI
· pytest'i | tail'e BORULAMA. Alt kümede --no-cov. TEST_DATABASE_URL izole DB.
· Postgres yoksa: service postgresql start (remote container'da her açılışta gerekir).
· ORM nesnesine rollback sonrası dokunma → MissingGreenlet; id'leri erken str() al.
· docs PR'ı öncesi: git diff origin/main -- docs/ | grep '^-## ' → BOŞ olmalı.

KAPANIŞ: CLAUDE.md ritüelinin 6 maddesi + node scripts/memory_index.mjs --write --only <slug>
+ cd backend && uv run python ../scripts/generate_repository_facts.py --root .. --check
```
