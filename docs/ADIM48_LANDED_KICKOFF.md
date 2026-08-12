<!-- doc-status: current -->
# ADIM 48 LANDED — #514 izleme ayrışması kapandı (A-08 blocker AÇIK) · sıradaki slice için kickoff
# ADIM 48 LANDED — kabul borcu sınıf B, parti 01 · sıradaki slice için kickoff

> **Bu belge ADIM 48 kapanışında yazıldı.** Sayısal otorite bu belge DEĞİL →
> `docs/generated/repository_facts.md` (üretilmiş, CI'da `--check` bloklayıcı).
> Tam kayıt: `docs/PROJECT_HISTORY.md` §ADIM 48.

## Nerede duruyoruz

**Base:** `origin/main` @ `7dd1dfe` (#682, ADIM 47). **Kod değişmedi** — ADIM 48 yalnız
belge uzlaştırmasıdır. Migration yok, `ENGINE_VERSION` değişmedi, alembic head
`0043_i08_registry_strategy_fks`.

**Verdict hâlâ `BLOCKED`. Blocker sayısı hâlâ 1 — yalnız A-08.**

| # | Blocker | Durum |
|---|---|---|
| 6.1 | A-08 insan ekran-okuyucu denetimi | 🔴 **AÇIK — TEK KALAN** |
| 6.2 | Uçtan uca kabul akışları | ✅ KAPANDI (ADIM 45, #680) |
| 6.3 | Alertmanager | ✅ KAPANDI (ADIM 31) |
| 6.4 | react-router `GHSA-qwww-vcr4-c8h2` | ✅ KAPANDI (ADIM 44, #678) |

## ADIM 48 ne yaptı

**#514 bir insan tarafından yeniden açıldı** (`2026-08-12T11:08:58Z`,
`state_reason=reopened`) ve repository bunu **hiçbir yerde kaydetmemişti**. RC raporu
kendi içinde çelişiyordu: banner'ı (`:31`) yeniden açılmayı yazarken §6.1, P12 ölçüm
tablosu ve `İzleme` bloğu hâlâ `CLOSED / COMPLETED` diyordu.

ADIM 29'un **kaydettiği** ayrışma (kapalı issue ↔ boş defter) böylece **kapandı**: insan
defterin harflemesiyle **(B)** yolunu seçti. 8 belge uzlaştırıldı; kanonik blok
`docs/audit/a11y_screen_reader_audit_results.md` §STATUS ▸ *Tracking-issue state*.

**Ayrışmanın kapanması denetimin yapılması DEĞİLDİR.** Defter boş, `0/4`, 0/46 rota,
0/20 akış, 0 `SR-BULGU`. **Yeniden açma bir sonuç değildir** — kapatmanın olmadığı gibi.

## Bu slice'ın bıraktığı reuse anchor'ları

- **Kanonik izleme bloğu** — `docs/audit/a11y_screen_reader_audit_results.md` §STATUS ▸
  *Tracking-issue state*. #514 hakkında bir şey yazacaksan **önce burayı oku, sonra buraya
  işaret et**; başka belgeye durum kopyalama (bu kusur tam olarak böyle doğdu).
- **HARF KARIŞIKLIĞI (yeni tuzak, pinlendi).** Defter ile RC raporu seçenekleri **ters**
  harfliyor:
  | | Defter (`a11y_..._results.md`) | RC §6.1 |
  |---|---|---|
  | **(A)** | imzalı kalıcı kabul | **denetimi koştur** |
  | **(B)** | hatalı kapatmanın geri alınması | imzalı sapma |
  Issue yorumundaki *"path (A)"* **RC anlamındadır**. İkisi de **yeniden
  numaralandırılMADI** — ikisi de başka yerlerden kimlikle anılıyor. Yeni bir belgede bu
  harfleri kullanacaksan **hangi belgenin harflemesi olduğunu yaz**.
- **Dated-update-block deseni** — `entropia_v18_remediation_status.md` ve
  `v18_final_acceptance.md` tarihli `GÜNCELLEME (…)` blokları **ekler**, geçmişi
  yeniden yazmaz. Yeni bir düzeltme yazarken bu deseni sürdür.

## Sıradaki iş — sırayla

| Kalem | Kim | Not |
|---|---|---|
| **A-08 denetimi** | **insan** | tek blocker; SR-2 (VoiceOver/Safari/macOS) **kullanıcının kendi makinesinde** koşulabilir |
| **P11-1** | **insan** | hazırlığı **PR #683** (taslak) yapıyor — ADIM 48 ona dokunmadı |
| K-2..K-7 | insan | beşi de ürün kararı; **K-5/K-6/K-7 A-08'den ÖNCE cevaplanamaz** |
| #558 / #559 | insan | kod açıkken COMPLETED kapalı; yeniden açmak insan işi |
| Kriter borç defteri (sınıf B) | agent | blocker değil; **sınıf D'ye test yazma — boşluğu gizler** |
| PR B2a → B2b | agent | post-V1; `SHARED_ALLOCATION_STATUS=future_dev` |
| RC yeniden doğrulama | agent | **denetim BİTTİKTEN sonra** |

## A-08 denetim oturumu — kâtiplik kuralları (değişmedi)

- Denetim oturumunda **agent KÂTİPTİR, denetçi değil**. DOM'dan / axe'tan / precheck'ten /
  Lighthouse'tan **hiçbir şey** defterin §1/§2/§3'üne yazılmaz. Koşulmayan hücre `—` KALIR.
- **İki kombinasyon zorunlu:** SR-1 (NVDA/Firefox/Windows) **ve** SR-2
  (VoiceOver/Safari/macOS). Tek kombinasyon A-08'i karşılamaz.
- Denetçinin sertifikalı olması **şart değil** — defterin §0 alanı `neither` yazmayı
  kaldırır ve sınırı dürüstçe kayda geçirir.
- **Beklenen gözlemler, yeni bulgu sayma:** K-2 (skip link yok, 23/23) · K-3 (contentinfo
  landmark yok, 23/23) · K-4 (`/user-manual`'da `<h1>` yok) · K-5 (h1→h3 atlaması, 21/23) ·
  K-7 (ilk DOM'da `aria-live` yok, 21/23) · D-10 (kontrast, **ayrı eksen**).
- **ORTAM TUZAĞI (ADIM 48'de ölçüldü):** uzak konteyner oturumları **Linux**'tadır;
  `a11y-audit-stack.sh` orada ayağa kalksa bile kullanıcının **macOS Safari**'sinden
  erişilemez. Kâtiplik oturumu, yığının **kullanıcının kendi makinesinde** kaldırılmasını
  gerektirir.
- **Precheck sayısını TEK KOŞUYLA tazeleme** — ilk koşu soğuktur ve eksik raporlar; en az
  iki kez koş.

## ASLA

- **#514'ü kapatma ya da açma** — `human-only`; agent ikisini de yapamaz.
- Hiçbir belgeye A-08 için `Complete` / `PASS` / `Done` yazma.
- **D-10'u** (WCAG 1.4.3, imzalı kalıcı sapma 2026-07-30) ekran-okuyucu ekseniyle
  karıştırma — ikisi AYRI, biri diğerini kapatmaz.
- Verdict'e `READY` yazma; A-08 kapanmadan **BLOCKED** kalır.

## Açık borç (ADIM 48'in kapatmadığı)

- **Memory checkpoint YAZILAMADI** — `ecc` ve `claude-mem` MCP sunucuları bu oturumda da
  bağlı değildi (ADIM 47'de de öyleydi). Kapanış ritüelinin 4. maddesi **iki slice'tır
  eksiktir**; bağlı bir oturumda ADIM 47 **ve** 48 için yazılmalı.
- **P1..P13 tanımı REPODA DEĞİL** (yalnız sohbet transkriptinde).
- `/library/{id}/validation-runs` **201'de kaldı** (ADIM 47) — ayrışma açık, PO kararı ister.

### YENİ BULGU (ADIM 48) — `A08_COMPLETE` kapısının kapsamı dar · ÖLÇÜLDÜ, DÜZELTİLMEDİ

`scripts/generate_repository_facts.py::INVARIANT_GLOBS` yalnız şunları tarıyor: `README.md`,
`CLAUDE.md`, `backend/`+`frontend/`+`docs/README.md`, `docs/CODEMAPS/*.md`,
`docs/STAGE2_HANDOFF.md`, `docs/STAGE_BUILD_PLAN.md`, `docs/ARCHITECTURE.md`,
`docs/DOMAIN_MODEL.md`, `docs/USAGE.md`.

**Taranmayanlar arasında A-08'in en kritik üç belgesi var:** kanonik defter
(`docs/audit/a11y_screen_reader_audit_results.md`), kanonik readiness raporu
(`docs/releases/…_RC_Readiness_….md`, üstelik `doc-status: current`) ve **canlı kickoff**
(`docs/ADIM<n>_LANDED_KICKOFF.md`). Yani *"A-08 Complete yazılmasını"* engellemek için var
olan kapı, bu ifadenin en çok önem taşıdığı belgeleri **okumuyor**.

**Negatif kanıt (ADIM 48'de ölçüldü):** canlı kickoff'a `A-08 denetimi tamamlandı ve PASS.`
satırı eklendi → kapı **exit 0** verdi (yakalamadı). Satır geri alındı.

**Neden tek satırlık bir düzeltme DEĞİL.** Glob'ları genişletmek bugün **7 sahte kırmızı**
üretir; yedisi de invariant'ı **doğru** ifade eden yasaklardır:

| Dosya | Satır | Metin |
|---|---|---|
| defter | 314 | *"no document may show A-08 as `Complete` or `PASS`"* |
| RC raporu | 668 | *"Hiçbir belge A-08'i Complete / PASS / Done **gösteremez**"* |
| RC raporu | 683 | *"**Nothing** above counts as a screen-reader PASS"* |
| RC raporu | 606 | *"WCAG 2.2 AA uyumlu" diye **tanımlayamaz**"* (WCAG kuralı) |
| checklist | 122 | *"hiçbir belge onu Complete **gösteremez**"* |
| runbook | 175 | *"no document may show A-08 as Complete, PASS…"* |
| kickoff | 88 | *"Hiçbir belgeye A-08 için `Complete` / `PASS` / `Done` **yazma**"* |

Kök neden: `NEGATION_RE` bu yasak biçimlerini tanımıyor — **`gösteremez`, `tanımlayamaz`,
`yazma`, `Nothing`, `no document`** listede yok. **Sıra ZORUNLU:** önce `NEGATION_RE`
genişletilir ve **her yeni terim için negatifi kanıtlanır** (bir terim gerçek bir ihlali
maskeliyorsa kapı sessizce işe yaramaz hâle gelir — bu kapının tek başarısızlık biçimi
budur), **sonra** `INVARIANT_GLOBS` genişletilir. Ters sırada yapılırsa 7 sahte kırmızı
gelir ve düzeltme "glob'u geri al" diye geri alınır.

**Ayrıca (küçük ama tuzak):** kural **satır tabanlıdır** ve `[^\n]{0,80}` newline geçmez —
`A-08` ile `Complete` farklı satırlara denk gelirse kural **hiç ateşlenmez**. ADIM 48'de
bir yeniden sarma tam da bunu tersine çevirdi (yakalanmayan satır yakalanır oldu). Bir
satırı yeniden sararken kapının davranışını değiştirdiğini bil.
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
ENTROPIA V18 — DEVİR: RC kapanışı, tek kalan blocker A-08
ENTROPIA V18 — ADIM 49: kabul kriteri borç defteri, sınıf B parti 02

[[ Kendi ROL / OTURUM BAŞLANGICI / CANONICAL KAYNAK / TAVİZ VERİLEMEZ /
   PR DİSİPLİNİ bloklarınızı buraya aynen yapıştırın ]]

════════════════ ÖNCE DOĞRULA (bu prompta da güvenme) ════════════════
  git fetch --all --prune && git log --oneline origin/main -6
  gh pr list --state open
  gh issue view 514 --json state,stateReason,updatedAt
  cd backend && uv run python ../scripts/generate_repository_facts.py --root .. --check

Bu repoda main iş sırasında İKİ KEZ altımdan değişti. Aşağıdaki her sayı
2026-08-12 ölçümüdür; yeniden türet.

BASE: origin/main @ <ADIM 48 merge sha>

════════════════ NEREDE DURUYORUZ ════════════════
Kanonik rapor: docs/releases/Entropia_V18_RC_Readiness_2026-08-07.md
Verdict: BLOCKED — dört blocker'dan ÜÇÜ kapandı, biri kaldı (A-08).

ADIM 48 (kod değişmedi) A-08'in İZLEME ayrışmasını kapattı: #514
2026-08-12T11:08:58Z'de bir İNSAN tarafından yeniden AÇILDI, 8 belge
uzlaştırıldı. AYRIŞMANIN KAPANMASI DENETİMİN YAPILMASI DEĞİLDİR —
defter hâlâ boş (0/4, 0/46 rota, 0/20 akış, 0 SR-BULGU).

════════════════ ÖNCELİK 1 — A-08 DENETİMİ ════════════════
Durum: #514 OPEN (reopened) · defter BOŞ · çıkış kriterleri 0/4 ·
A-08 için imzalı sapma YOK.

İKİ KOMBİNASYON ZORUNLU:
  SR-1  NVDA (son kararlı) / Firefox / Windows
  SR-2  VoiceOver / Safari / macOS   → kullanıcı macOS'ta

⚠ ORTAM: uzak oturumlar Linux konteynerindedir; yığın orada kalksa bile
  kullanıcının Safari'sinden ERİŞİLEMEZ. Kâtiplik oturumu yığının
  KULLANICININ KENDİ MAKİNESİNDE kaldırılmasını gerektirir:
      scripts/a11y-audit-stack.sh up
  Denetçi sertifikalı olmak ZORUNDA DEĞİL — defter §0 `neither` yazmayı
  kaldırır ve sınırı kayda geçirir.

DENETİM OTURUMUNDA SEN KÂTİPSİN, DENETÇİ DEĞİLSİN:
  · Kullanıcıyı rota rota yönlendirir, DUYDUĞUNU yazarsın.
  · DOM/axe/precheck/Lighthouse'tan HİÇBİR ŞEY §1/§2/§3'e YAZILMAZ.
  · Koşulmayan hücre `—` KALIR. Uydurulmuş dolu şablon boştan beterdir.
  · Emin değilsen SOR.
  Akış: docs/implementation/a11y_screen_reader_audit_runbook.md + defter §0–§5.

BEKLENEN GÖZLEMLER — yeni bulgu sayma:
  K-2 skip link yok (23/23) · K-3 contentinfo yok (23/23) ·
  K-4 /user-manual'da <h1> yok · K-5 h1→h3 atlaması (21/23) ·
  K-7 ilk DOM'da aria-live yok (21/23) · D-10 kontrast (AYRI EKSEN).
  ⇒ K-5/K-6/K-7'nin ASIL sorusu denetimde cevaplanır.

ASLA: #514'ü kapatma ya da açma (human-only) · hiçbir belgeye A-08 için
Complete/PASS/Done yazma · D-10'u ekran-okuyucu ekseniyle karıştırma.

════════════════ ÖNCELİK 2 — P11-1 BRANCH PROTECTION ════════════════
main'de branch protection ve ruleset YOK → on slice'ta kurulan kapıların
HİÇBİRİ kırmızıyken merge'i durduramıyor.
HAZIRLIĞI PR #683 (taslak) YAPIYOR — ÖNCE ONU OKU, ÇOĞALTMA.
Bu bir REPO AYARI: agent UYGULAMAZ, HAZIRLAR.
UYARI: var olmayan bir job adını required yapmak TÜM merge'leri kilitler.

════════════════ KALAN İŞ ════════════════
| Kalem | Kim |
|---|---|
| A-08 denetimi | insan — tek blocker |
| P11-1 (#683 taslak) | insan |
| K-2..K-7 | insan — K-5/K-6/K-7 A-08'den ÖNCE cevaplanamaz |
| #558 / #559 | insan |
| Kriter borç defteri | agent — YALNIZ sınıf B; sınıf D'ye test yazmak boşluğu GİZLER |
| PR B2a → B2b | agent — post-V1 |
| RC yeniden doğrulama | agent — denetim BİTTİKTEN sonra |

MEMORY BORCU: ecc + claude-mem checkpoint'i ADIM 47 VE 48 için YAZILMADI
(sunucular bağlı değildi). Bağlıysan ilk iş bu.

════════════════ BU REPONUN TUZAKLARI ════════════════
  · pytest'i `| tail`'e BORULAMA — exit code tail'in olur. Dosyaya yaz, $?'i AYRI oku.
  · Tam suite TEK pytest çağrısında, ORTADA ÖLDÜRME.
  · Alt küme koşarken `--no-cov` EKLE — yoksa %90 kapısı SAHTE KIRMIZI verir.
  · TEST_DATABASE_URL ile izole DB; sürücü postgresql+asyncpg://
  · vitest: --no-file-parallelism ZORUNLU; node_modules yoksa önce npm ci
  · Bir job'ın koştuğunu JOB LOG'undan doğrula; yeşil rozet YETERLİ DEĞİL.
  · Docs regresyonu ÜÇ KEZ oldu (#590, #604). Her docs PR'ından önce:
        git diff origin/main -- docs/ | grep '^-## '   → BOŞ OLMALI
  · Kod-review CRITICAL/HIGH bulgularını DÜZELTMEDEN ÖNCE empirik doğrula.
  · A-08 harflemesi: defterde (A)=imzalı kabul/(B)=geri alma; RC §6.1'de
    (A)=denetimi koştur/(B)=imzalı sapma. TERS. Hangisini kastettiğini YAZ.

════════════════ KAPANIŞ RİTÜELİ ════════════════
CLAUDE.md §Session CLOSING'in 6 maddesi +
  cd backend && uv run python ../scripts/generate_repository_facts.py --root .. --check
  git diff origin/main -- docs/ | grep '^-## '   → BOŞ olmalı
Verdict A-08 kapanmadan BLOCKED kalır. Hiçbir belgeye "READY" yazma.
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
