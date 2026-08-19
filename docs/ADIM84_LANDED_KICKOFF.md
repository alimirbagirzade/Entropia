<!-- doc-status: current -->
> **CANLI KICKOFF.** Bu belge en yeni slice'ın handoff'udur. Bir sonraki slice inince
> `historical`a demote edilir ve yerine yenisi geçer (`check_classification` CI'da doğrular:
> daha yüksek numaralı bir `docs/ADIM<n>…KICKOFF.md` varken canlı işaret eski belgede duramaz).

# ADIM 84 LANDED — kabul borcu batch 12 (doc 05 backend): TL-13 + TL-22 kapandı · sıradaki slice için kickoff

> Tam kayıt: `docs/PROJECT_HISTORY.md` §ADIM 84. Bu belge **devam noktasıdır**, kayıt değil.

## Neredeyiz

- Kapanış yazılırken main **`7f331c7`** (dal `aecd72c`'de yazıldı, #781 inince rebase edildi). **Ürün kodu değişmedi**: migration yok, OpenAPI
  değişmedi, `ENGINE_VERSION` değişmedi, alembic head `0043_i08_registry_strategy_fks`,
  `SHARED_ALLOCATION_STATUS` = `future_dev`.
  **Blocker sayısı DEĞİŞMEDİ (1 — yalnız A-08), verdict BLOCKED.**
- Değişen kod **yalnız iki entegrasyon test dosyası**; `backend/src` altında sıfır satır.
- **Tavanlar İNDİ** — sayıların otoritesi `docs/audit/acceptance_coverage_baseline.json`;
  bu slice iki kriter (`TL-13`, `TL-22`) kapattı ve `partial` ile `debt_class.B`'yi **ikişer**
  indirdi. `total_criteria` **383** (TABAN) ve `uncovered` **kriter** **8** değişmedi.
  **Rakamlar rebase'den SONRA yeniden ölçüldü** — bkz. §Pazarlıksız md. 4.
- **Doc 05'te backend yüzeyinde testin kapatabileceği satır kalmadı** — kalan TL satırları ya
  bulgu (`TL-01.c4`, `TL-11.c3`, `TL-16.c4`), ya yanlışlanabilirliği şüpheli (`TL-02.c2`,
  `TL-14.c4`), ya da **frontend** (`TL-18`).

## Bu slice'ın bıraktığı yeniden kullanım çapaları (tam dosya/sembol adlarıyla)

- `backend/tests/integration/test_trade_log_persistence.py::test_explicit_pin_reports_the_prior_readiness_report_stale`
  — **var olan bir readiness raporunu bir composition mutasyonunun üzerinden taşıyan tek
  harness**. `rc_cmd.run_readiness_check(session, actor, composition_id=…)` → `report_id` →
  `rc_query.get_readiness_report(...)`. Yeni bir sayfa için aynı soruyu soracaksan **bunu
  kopyala**, üçüncü bir idiom icat etme. Okuma yüzeyinin taşıdığı alanlar:
  `state`, `stored_state`, `is_current`, `composition_fingerprint`, `current_fingerprint`.
- `backend/tests/integration/test_trade_log_persistence.py::test_two_writers_on_one_head_append_exactly_one_revision`
  — **aynı gerçek head'i okumuş iki yazar** deseni. `test_stale_expected_head_conflicts`'in
  uydurulmuş token'ından farklıdır ve son-yazan-kazanır'ı ondan ayırt eden **tek** testtir.
- `backend/tests/integration/test_gateway_parity_s4.py::test_successful_trade_log_tool_call_records_its_own_provenance`
  — **başarı yolunda** `AgentToolCall` satırını geri okuyan ilk test.
  `lab_repo.create_task(...)` ile gerçek bir `AgentTask` kurar (`task_id` FK'lidir,
  `checkpoint_id` düz string'tir). Başka bir Agent aracının provenance'ını pinlerken bunu çoğalt.
- `backend/tests/integration/test_gateway_parity_s4.py::test_agent_trade_log_work_leaves_the_human_mainboard_untouched`
  — `_composition_with_items(session, OWNER, count=2)` ile bir **insan** panosu kurup Agent'ın
  işinden sonra `item_id`'ler + `composition_hash` + `row_version`'ı karşılaştırır.
- `docs/audit/acceptance_coverage_baseline.json` §adjudication →
  **`TL_16_c4_409_carries_no_canonical_state`** ve **`TL_22_c4_is_defended_by_two_gates_not_one`**.
  İkincisi bir **ölçüm**dür, bir karar değil: o satırı yeniden ölçecek parti ilk negatif
  kontrolün kırmızısını kanıt sanmasın diye yazıldı.

## Pazarlıksız — bu slice'ın öğrendikleri

1. **Kırmızının HANGİ assertion'da olduğunu oku (ADIM 79'un dersi, ikinci kez).** `TL-22.c4`'ün
   ilk negatif kontrolü kırmızı verdi ama `status == succeeded` üzerinde — özellik **iki
   bağımsız kapıyla** korunuyordu, yani tek kapıyı kırmak mutasyon değil **REJECTED** üretti.
   O kırmızı ownership kapısını kanıtlar, test edilen assertion'ı değil.
2. **Clause ≠ kriter (ADIM 66 emsali, yine).** `TL-16.c3` kapandı ve **hiçbir tavan oynamadı**,
   çünkü `TL-16.c4` sevk edilmemiş. Bir partinin değerini clause sayısıyla değil **kapanan
   kriter** sayısıyla planla.
3. **"Yapı gereği doğru" bir clause'u kapatma iştahına dikkat.** `TL-02.c2` (revizyonsuz draft
   Ready Check'e girmez) **alınmadı**: draft hiçbir zaman Mainboard item'ı olmadığı için
   assertion bugün geçer ve tek bir gerçekçi değişiklikle kırmızıya dönmez — `TS-02.c2` /
   `AOS-04.c2` / `AOS-06.c2` ile aynı şekil. Yazmak **işaretleme** olurdu.
4. **Defter SERİ bir kaynaktır, ama önceki freeze'in `clause_totals`'ı ARİTMETİK TABANI
   DEĞİLDİR.** Batch 08+09 freeze'i `4ebd413`'e karşı 1016/9/111 yazmıştı; aynı belge bugünkü
   main'de **1022/9/105** ölçüyor. Tavanları **`--report` ile bu tabanda yeniden ölç**, iki
   freeze'in farkından türetme.
5. **Bulguyu YENİDEN SINIFLANDIRMA.** `TL-16.c4` sınıf D görünüyor; taşımak D tavanını
   **yükseltir** ve bu bir adjudication'dır. Defterde artık **on** böyle bulgu var.
6. **Numara DEĞİL, ETİKET de çakışır.** Bu slice `ADIM 83` + `batch 11` yazıldı; PR açıkken
   **#781** merge edilip **ikisini birden** aldı (doc 18 backend). **Merge edilmiş ad
   kazanır** → bu kayıt `ADIM 84` / `batch 12`. Kapanış yazarken yalnız `grep '^## ADIM'`
   yetmez: **parti etiketini de** `PROJECT_HISTORY.md`'de ara, yoksa iki slice aynı
   `batch <n>` adını taşır ve defter zincirinde hangi freeze'in hangisi olduğu okunamaz.

## Sıradaki tasarım işaretleri — ÖNCE ÖLÇ

- **Tümleyen parti: `TL-18` + `TL-02.c2` (doc 05, FRONTEND).** `TL-18` **tek clause'luk ve
  tamamen `uncovered`** — kapanırsa `uncovered` **kriter** tavanı 8 → 7 iner (bu dalgada hiç
  oynamadı). Şekli batch 07'nin `PC-17.c4`'ü ile aynı: *expand/collapse hiçbir non-GET istek
  atmaz ve hiçbir durum değişmez*. Mainboard jsdom testleri `expandRow()`'u bugün yalnız bir
  **navigasyon adımı** olarak kullanıyor; assertion yok. `TL-02.c2`'yi aynı partiye alma —
  yukarıdaki md. 3.
- **Yoğunluk sırası (bu freeze'den ölçüldü):** `AT` 5 · `AL` 5 · `RF` 4 · `RD` 4 · `AM` 4.
  Doc 03, 04, 07 **bitti**; doc 05'in backend yarısı **bu slice'ta bitti**.
- **`TL-16.c4`'ü ürün işi olarak açmak isteyen olursa:** düzeltme tek yerdedir —
  `WorkObjectRevisionConflictError`'a `details`/`scope_id` verecek üç raise yeri
  (`commands/trade_log.py`, `commands/trading_signal.py`, `commands/mainboard.py`). Ama bu
  **O-02 hata zarfını** genişletir → **ürün kararı**, test slice'ının işi değil.

## Çalışma yöntemi (bu dalgada işe yarayan)

- Ortamda Postgres **yoktu**; `/usr/lib/postgresql/16` kuruluydu → `initdb` + `pg_ctl` ile
  `entropia`/`entropia` @ **:5432** ayağa kaldırıldı, entegrasyon suite'i koştu. Konteynerde
  "no PostgreSQL" gördüğünde **önce bunu dene**, testleri skip'e bırakma.
- Sıra: **ölç (`--report`) → parti seç → test yaz → negatif kontrol → map → `--ratchet` →
  `--write-ledger` → `generate_repository_facts.py --root ..` → tam suite.**
  `repository_facts` **test collection sayısı** taşır; test ekleyen slice onu **tazelemek
  zorundadır** (ADIM 60 emsali).
- Alt küme koşarken **`--no-cov`**; tam suite'i **tek** `uv run pytest -q` çağrısında koş ve
  exit code'u **`| tail` olmadan** ayrı yakala.

## Paste-ready resume prompt

```
ENTROPIA V18 — kabul borcu batch 13

ROL: Entropia V18 Principal Engineer.
[ENTROPIA ORTAK SÖZLEŞME bloğunu uygula]

ÖNCE DURUM ÖLÇ — hiçbir SHA'yı ve hiçbir sayıyı bu prompttan alma, hepsini oku:
  git fetch && git log --oneline origin/main -6
  git show origin/main:docs/PROJECT_HISTORY.md | grep '^## ADIM' | tail -4
  mcp__github__list_pull_requests(state=open)   # aynı bölümü tazeleyen açık dal var mı

ZİNCİR UYARISI: kabul defteri SERİ bir kaynaktır. Aynı anda açık iki batch dalı
  aynı tavanı farklı tabanlarda dondurur; ikinci inen rebase edip YENİDEN
  DONDURMALI. Tavanı iki freeze'in FARKINDAN türetme — `--report` ile kendi
  tabanında yeniden ölç. Numara da aynı zincire tabidir: en yüksek '## ADIM' + 1,
  merge edilmiş ad kazanır.

GÖREV (önerilen): doc 05 FRONTEND yüzeyi — `TL-18` (tek clause, tamamen uncovered;
  kapanırsa `uncovered` KRİTER tavanı 8 → 7 iner) . Şekli batch 07'nin PC-17.c4'ü:
  expand/collapse hiçbir non-GET istek atmaz, hiçbir durum değişmez. Mainboard jsdom
  testleri expandRow()'u bugün yalnız navigasyon adımı olarak kullanıyor.
  Alternatif yoğunluk: AT 5 · AL 5 · RF 4 · RD 4 · AM 4.

  Parti seçmeden ÖNCE ölç:
    cd backend && uv run python ../docs/audit/acceptance_semantic_scan.py --root .. --report
  Kriterin adlandırdığı davranışın gerçekten sevk edildiğini backend/src ya da
  frontend/src'te DOĞRULA. Üç şekli ayır:
    unshipped (kurulabilir, kod yok -> D) · unconstructible (erişilebilir ekran yok -> C)
    · unfalsifiable (doğru ama regresyon geçirilecek dikiş yok -> işaretle, kapatma)

HER CLAUSE İÇİN ZORUNLU:
  1. Mevcut testler bu kusur altında yeşil mi kalıyor? Kalıyorsa yeni assertion
     BAŞKA bir eksene bakmalı — yoksa işaretleme yapıyorsun, kapsama değil.
  2. Negatif kontrol koş ve KİMİN, HANGİ ASSERTION'da kırmızıya döndüğünü oku.
     Yanlış sebeple kırmızı hiçbir şey kanıtlamaz (ADIM 84: bir özellik iki kapıyla
     korunuyordu, tek kapıyı kırınca test BAŞKA bir satırda düştü).
  3. Koşamadığın bir suite'e (e2e/@a11y — bu container Docker Hub'a 403 alır)
     assertion YAZMA; sınırı map notuna ve PROJECT_HISTORY'ye yaz.
  4. Kriterin SON clause'u kapanıyorsa debt_class'ı KALDIR.

KAPATMAYA ÇALIŞMA — on açık bulgu: TL-11.c3, TL-16.c4, TL-01.c4, RD-01.c4,
  RD-05.c5, RD-12.c4, RD-13.c4, PC-20.c3, PC-02.c2, TS-07.c2. Ayrıca dört
  `unfalsifiable: true` clause (TS-02.c2, AOS-04.c2, AOS-06.c2 + PC-02.c2 grubunun
  imzalı olanları) tavandan DÜŞMEZ; yeniden sınıflandırma bir adjudication'dır.

TAVANLAR: bu prompttan OKUMA — acceptance_coverage_baseline.json'dan oku.
  ADIM 84 sonrası (main 7f331c7 tabanlı) donan değerler o dosyadadır.
  total_criteria 383 bir TABANDIR. Ratchet YALNIZ AŞAĞI iner.

ORTAM: Postgres kurulu değilse /usr/lib/postgresql/16 ile initdb + pg_ctl ile
  entropia/entropia @ :5432 ayağa kaldır — entegrasyon suite'ini skip'e bırakma.
  Test ekliyorsan `scripts/generate_repository_facts.py --root ..` ile olguları
  TAZELE (collection sayısı taşır), sonra tam suite.

DUR koşulları: çözülmemiş canonical/PO kararı, kırmızı focused test, OpenAPI drift,
çoklu alembic head, historical Result davranışı değişimi. PR'ı aç, durumu dürüstçe
yaz, DUR. MERGE ETME.
```
