<!-- doc-status: historical -->
> **HISTORICAL KICKOFF — canlı olan `docs/ADIM77_LANDED_KICKOFF.md`'dir.**
> Bu belge yazıldığı andaki durumu kaydeder; SHA'lar, sayılar ve "next" maddeleri bayat
> olabilir. Sayısal gerçekler için otorite: `CLAUDE.md` §Current position +
> `docs/generated/repository_facts.md` (üretilmiş).

# ADIM 76 LANDED — kabul borcu batch 08 (doc 04, backend) · sıradaki slice için kickoff

> Tam kayıt: `docs/PROJECT_HISTORY.md` §ADIM 76. Bu belge **devam noktasıdır**, kayıt değil.

## Neredeyiz

Base **`d741ab4`** (ADIM 75'in tepesi — bu dal **merge edilmemiş** batch 07'nin üstünde yığılı;
ölçüm anında main `0f0651d`) · alembic head **`0043_i08_registry_strategy_fks`** ·
`ENGINE_VERSION` **değişmedi** · OpenAPI **değişmedi** · `SHARED_ALLOCATION_STATUS` =
**`future_dev`** · migration **YOK** · **ürün kodu değişmedi**. **Blocker sayısı DEĞİŞMEDİ
(1 — yalnız A-08), verdict BLOCKED.**

Tavanlar `partial` **97 → 93**, `debt_class.B` **66 → 62**. Açık kabul borcu:
**A=1 · B=62 · C=6 · D=32 → 101**. Clause `covered` **1015 → 1019**, `uncovered`
**112 → 108**; `total_criteria` **383** (taban).

> **SIRA UYARISI:** bu slice **merge edilmemiş** `test/closure-acceptance-batch-07` (PR #757,
> ADIM 74) üstünde duruyor. #757 inmeden batch 08 merge edilemez; #757 rebase edilirse bu dal
> da rebase ister. Sebep: kabul defteri **seri bir kaynaktır** — baseline'ın `supersedes`
> alanı bir zincirdir ve her batch bir öncekinin dondurduğu sayıları devralmalıdır.

## Bu slice'ın öğrettikleri

1. **"KAPATILAMAZ"ın ÜÇ FARKLI şekli var ve karıştırmak defteri bozar.**
   - **Sevk edilmemiş** — senaryo kurulabilir, kod yok (`PC-20.c3`, `TS-07.c2`). Sınıf D.
   - **Kurulamaz** — erişilebilir hiçbir ekran/durum yok (`PC-02.c2`). Sınıf C.
   - **Yanlışlanamaz** — kod var ve doğru, ama bozulabileceği bir **dikiş** yok
     (`TS-02.c2`). Test yazmak scanner'ı tatmin eder, hiçbir şey kanıtlamaz.
   Üçü de sınıf B değildir ve **hiçbiri bir test slice'ının yeniden sınıflandıracağı şey
   değildir**. Ölç, `notes`'a yaz, geç.
2. **Bir clause'un "son açık clause" olması onu KAPATILABİLİR yapmaz.** Doc 04'ün altı
   adayının **hepsi** son-clause'du; ikisi ölçümde sınıf B çıkmadı. Sıra: (a) son clause mu,
   (b) davranış sevk edilmiş mi, (c) bozulabileceği bir dikiş var mı.
3. **Bir yokluk iddiasını kapatmadan önce "hangi tek değişiklik bunu kırar?" diye sor.**
   Cevap "üç ayrı yerde değişiklik" ise clause yanlışlanamaz demektir (`TS-02.c2`).
4. **Rol tabanlı reddi rolün KENDİSİYLE sür.** `TS-15.c2` yıllarca "sahibi olmayan
   reddedilir" diye okunmuştu; Supervisor **User ile Admin arasında** durduğu için o kanıt
   satırı kapatmıyordu. Yükseltilmiş roller ayrı vaka ister.
5. **Rollback sonrası ORM nesnesine dokunma.** `blocked_rev.normalized_revision_id`'yi
   `session.rollback()`'ten sonra okumak `MissingGreenlet` verdi — id'yi **önce** düz bir
   `str`'e al.

## Bu slice'ın bıraktığı yeniden kullanım çapaları

| Düğüm / sembol | Nerede | Ne işe yarar |
|---|---|---|
| `SUPERVISOR` aktörü + `user_sup` principal | `test_trading_signal_persistence.py` | rol-spesifik yetki reddi sürmek |
| `test_soft_delete_writes_trash_entry_audit_and_outbox` | aynı dosya | silmenin **kurtarılabilir** yarısını (trash+audit+outbox) sayan kalıp |
| `test_enabling_allocation_preserves_the_stored_independent_capital` | aynı dosya | allocation'ı açıp `content_hash` ile koruma kanıtlayan **çift** assertion |
| `test_correcting_a_blocked_import_appends_and_keeps_the_old_report` | aynı dosya | "eski rapor tarih olarak sağ kalır" bayt-eşitlik kalıbı |
| `alloc_cmd.upsert_allocation_draft(..., enabled=True)` | `commands/allocation_plan.py` | herhangi bir kompozisyonda allocation'ı açmanın en kısa yolu |

## Açık bulgular — bunları kapatmaya çalışma (ON BİR)

`TL-11.c3`, `TL-16`, `TL-01.c4`, `RD-01.c4`, `RD-05.c5`, `RD-12.c4`, `RD-13.c4`,
`PC-20.c3`, `PC-02.c2`, **`TS-07.c2`**, **`TS-02.c2`**.

## Sıradaki tasarım işaretleri

- **Sınıf B'de 62 kriter kaldı.** Doc 07 ve doc 04 tükendi. Kalan yoğun belgeler: **doc 05**
  (TL, 8 — ama `TL-01`/`TL-11`/`TL-16` şüpheli, gerçekte **5**), **doc 02** (AT, 5),
  **doc 03** (AOS, 5), **doc 18** (AL, 5).
- **Doc 03 (AOS) doc 04'ün ikizidir** — bu slice'ın kapattığı satırların birçoğunun AOS
  karşılığı var (`AOS-04` = `TS-02`, `AOS-13` = `TS-15`, `AOS-18` = `TS-18`). Aynı harness
  ve aynı kanıt şekilleri **doğrudan** yeniden kullanılabilir; muhtemelen en ucuz sıradaki parti.
  **DİKKAT:** `AOS-04`, `TS-02` ile aynı transient-draft sorununu taşıyor olabilir — önce ölç.
- **A-08 tek blocker**; yalnız insan denetimi kapatır (#514).
- **G9 ve G13 İMZALI** (#753) — `C2` (`settle`/`finalize`/P10/`iter_portfolio`) artık imzasız
  kapıların arkasında **değil**. Paket-C'ye dönen slice `docs/adr/0002` §6/§8'i doğrulasın.

## Paste-ready resume prompt

```
ENTROPIA V18 — kabul borcu sınıf B, batch 09
TEK SLICE

ROL: Entropia V18 Principal Engineer. Yalnız bu slice.
[ENTROPIA ORTAK SÖZLEŞME bloğunu uygula]

TABAN — ÖNCE BUNA BAK
  ADIM 76 (batch 08) merge EDİLDİ Mİ? Batch 07 (#757) ve batch 08 zincirleme yığılıydı.
  - İkisi de indiyse: main'den dallan.
  - Biri hâlâ açıksa: EN ÜSTTEKİ açık dalın üstüne YIĞ (defter seri bir kaynak; baseline'ın
    `supersedes` zinciri bir öncekinin dondurduğu sayıları devralmalı).
  Numarayı `grep '^## ADIM' docs/PROJECT_HISTORY.md | tail -1` ile ÖĞREN, etikete güvenme.

ÖN KOŞUL — ÖLÇEREK SEÇ (bu slice'ın en önemli adımı)
  1. docs/ADIM76_ ve ADIM75_LANDED_KICKOFF.md'deki REUSE ANCHOR tablolarını oku.
  2. Her aday için SIRAYLA:
     (a) kriterin SON açık clause'u mu? değilse tavan İNMEZ;
     (b) davranış backend/src veya frontend/src'te SEVK EDİLMİŞ Mİ? grep ile doğrula;
     (c) durum KURULABİLİR mi? erişilebilir bir ekran/komut var mı?
     (d) HANGİ TEK DEĞİŞİKLİK bu testi kırar? cevap yoksa clause YANLIŞLANAMAZ —
         yeşil bir test yazmak kapsamak değil İŞARETLEMEK olur.
     (b)/(c)/(d)'den biri düşerse: bulguyu `notes`'a ÖLÇÜMÜYLE yaz, YENİDEN SINIFLANDIRMA,
     başka kriter seç.
  3. ON BİR açık şüpheli bulgu var (TL-11.c3, TL-16, TL-01.c4, RD-01.c4, RD-05.c5,
     RD-12.c4, RD-13.c4, PC-20.c3, PC-02.c2, TS-07.c2, TS-02.c2) — kapatmaya çalışma.

ÖNERİLEN PARTİ: doc 03 (AOS, 5) — doc 04'ün ikizi, harness ve kanıt şekilleri yeniden
  kullanılabilir. AOS-04'ü TS-02 ile aynı transient-draft tuzağı için ÖNCE ölç.
  Doc 07 ve doc 04 BİTTİ — oralarda sınıf B kalmadı.

YAPILACAK
  Her clause için davranışı adlandıran testi yaz ve NEGATİF KONTROLDEN geçir:
  davranışı ÜRÜNDEN kaldır -> test KIRMIZI olmalı VE kırmızının HANGİ ASSERTION'da
  olduğunu OKU (yanlış sebeple düşen kontrol hiçbir şey kanıtlamaz — ADIM 75 dersi).
  Frontend düğüm id'si `::` DEĞİL ` > ` ile yazılır (UNRESOLVED_NODE).
  Rollback'ten sonra ORM alanına dokunma — id'yi önce str'e al (ADIM 76 dersi).

RATCHET
  acceptance_semantic_map.yaml -> güncelle (clause evidence kriter düzeyindeki
  test_evidence'a DA eklenmeli; yeni bir evidence_type kullandıysan onu da EKLE).
  Son clause kapanıyorsa kriteri `covered` yap ve `debt_class`'i KALDIR.
  YAML notes'u DÜZ yazma — ':' içeren metin plain scalar'ı bozar, TIRNAKLA.
  python3 docs/audit/acceptance_semantic_scan.py --root . --ratchet docs/audit/acceptance_coverage_baseline.json
  Tavanları ÖLÇÜLEN değere İNDİR (partial 93 / B 62 taban). total_criteria = 383 TABAN.
  Clause toplamlarını TAHMİN ETME, --report'tan oku. Sonra --write-ledger + repository_facts.

DOKUNMA
  sizing.py / booking.py / engine.py / portfolio_engine.py / backtest_engine.py
  jobs/research_data.py::_pin_member / ::_seal_bundle

TEST
  repository_facts'i TAM SUITE KOŞMADAN ÖNCE tazele (ADIM 73 dersi: suite koşarken
  tazelemek tests/contract/test_repository_facts_guard.py'yi sahte kırmızı yapar).
  cd backend && uv run pytest -q      (tam suite = coverage kapısı)
  alt kümede --no-cov EKLE. `pytest | tail` KULLANMA.
  cd frontend && npx vitest run <dosya> --no-file-parallelism

COMMIT / PR
  DAL: test/closure-acceptance-batch-09
  commit: test(closure-acceptance): <kapatilan clause'lar>
  AI ATTRIBUTION YOK. Draft PR aç (yığılıysa base'i açık dala ver), MERGE ETME.
  Kapanış ritüeli 6 madde.

FINAL RESPONSE
  Kapanan clause'lar + inen tavanlar + KAYDEDİLEN BULGULAR + koşan kapıların GERÇEK
  sayıları + dürüst sınırlar. DUR.
```
