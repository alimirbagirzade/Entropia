<!-- doc-status: historical -->
> **SUPERSEDED — ADIM 52 (2026-08-12).** Yerini `docs/ADIM52_LANDED_KICKOFF.md`
> (kabul borcu sınıf B, parti 02) aldı; **canlı kickoff** ise
> `docs/ADIM53_LANDED_KICKOFF.md`. Aşağısı ADIM 51 kapanışındaki durumu kaydeder.
> **Değişmeyen:** blocker sayısı 1 (yalnız A-08), verdict BLOCKED.
# ADIM 51 LANDED — #514 izleme ayrışması kapandı (A-08 blocker AÇIK) · sıradaki slice için kickoff

> **Bu belge ADIM 51 kapanışında yazıldı.** Sayısal otorite bu belge DEĞİL →
> `docs/generated/repository_facts.md` (üretilmiş, CI'da `--check` bloklayıcı).
> Tam kayıt: `docs/PROJECT_HISTORY.md` §ADIM 51.

> **NUMARA NOTU — bu slice İKİ KEZ taşındı: ADIM 48 → 49 → 50.** İş sürerken **main
> altımdan DÖRT KEZ değişti**: #683 (P11-1 hazırlığı), #686 (kabul borcu B/01), #688
> (K-6b odak halkası), #690 (memory checkpoint) ve #691 (P11-1 KAPANDI). **#686 ve #688'in
> İKİSİ DE "ADIM 48"** adını aldı (aynı kickoff yoluna yazdılar), **#691 ise "ADIM 49"u**
> aldı — ilk iki numaram da elimden gitti. CLAUDE.md'nin *"yeniden numaralandırma YASAK"*
> kuralı **merged** başlıklar içindir (değiştirilemezler); bu slice henüz merge
> edilmemişti, o yüzden her iki çakışma da **ucuzken** önlendi. **Ders:** kapanış belgelerini yazmadan hemen önce
> `git fetch && git log --oneline origin/main -3` **tekrar** koş — ADIM numarası main'de
> o sırada değişmiş olabilir.

## Nerede duruyoruz

**Base:** `origin/main` @ `ce823a8` (#685, ADIM 50 — K-2 + K-4). **Kod değişmedi** — ADIM 51 yalnız
belge uzlaştırmasıdır. Migration yok, `ENGINE_VERSION` değişmedi, alembic head
`0043_i08_registry_strategy_fks`.

**Verdict hâlâ `BLOCKED`. Blocker sayısı hâlâ 1 — yalnız A-08.**

| # | Blocker | Durum |
|---|---|---|
| 6.1 | A-08 insan ekran-okuyucu denetimi | 🔴 **AÇIK — TEK KALAN** |
| 6.2 | Uçtan uca kabul akışları | ✅ KAPANDI (ADIM 45, #680) |
| 6.3 | Alertmanager | ✅ KAPANDI (ADIM 31) |
| 6.4 | react-router `GHSA-qwww-vcr4-c8h2` | ✅ KAPANDI (ADIM 44, #678) |

## ADIM 51 ne yaptı

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
| ~~P11-1~~ | — | ✅ **KAPANDI (#691)** — ruleset `20765617` main'de **AKTİF**: 16 zorunlu check, `strict: true`, `bypass_actors: []`. **Çalışma şekli değişti:** main'e doğrudan push YOK; her PR 16 yeşil check + main ile güncellik ister. Yeni CI job'ı eklerken **SIRA:** önce merge → ad üretilsin → `required-checks-preflight.sh` → ruleset güncelle. **Ters sıra TÜM merge'leri kilitler.** |
| K-2..K-7 | insan | **K-2 + K-4 #685, K-6b #688 ile KAPANDI** (odak halkası `var(--text)`, ölçülen en kötü zemin 4.50:1 ≥ 3:1). Kalanlar ürün kararı; **K-3/K-5/K-6a/K-7 A-08'den ÖNCE cevaplanamaz** |
| #558 / #559 | insan | kod açıkken COMPLETED kapalı; yeniden açmak insan işi |
| Kriter borç defteri (sınıf B) | agent | **parti 01 #686 ile landed** (8 kriter, `partial` 126 → 118). Sıradaki parti: `TL-11.c3`+`TL-12.c3`+`TL-20.c3`. **Sınıf D'ye test yazma — boşluğu gizler** |
| PR B2a → B2b | agent | post-V1; `SHARED_ALLOCATION_STATUS=future_dev` |
| RC yeniden doğrulama | agent | **denetim BİTTİKTEN sonra** |

## A-08 denetim oturumu — kâtiplik kuralları (değişmedi)

- Denetim oturumunda **agent KÂTİPTİR, denetçi değil**. DOM'dan / axe'tan / precheck'ten /
  Lighthouse'tan **hiçbir şey** defterin §1/§2/§3'üne yazılmaz. Koşulmayan hücre `—` KALIR.
- **İki kombinasyon zorunlu:** SR-1 (NVDA/Firefox/Windows) **ve** SR-2
  (VoiceOver/Safari/macOS). Tek kombinasyon A-08'i karşılamaz.
- Denetçinin sertifikalı olması **şart değil** — defterin §0 alanı `neither` yazmayı
  kaldırır ve sınırı dürüstçe kayda geçirir.
- **Beklenen gözlemler, yeni bulgu sayma** — **liste KÜÇÜLDÜ, güncelini kullan:**
  **KAPANDI (yeniden kaydetme):** K-2 skip link (#685) · K-4 `/user-manual` `<h1>` (#685) ·
  K-6b odak halkası kontrastı (#688).
  **HÂLÂ AÇIK, beklenen:** K-3 (contentinfo landmark yok, 23/23) · K-5 (h1→h3 atlaması —
  **21 değil 22**, `/user-manual` K-4 kapanınca kümeye girdi) · K-7 (ilk DOM'da `aria-live`
  yok) · **K-6a** (odak GÖRÜLEBİLİR mi — yalnız A-08 kapatır) · D-10 (kontrast, **ayrı eksen**).
- **ORTAM TUZAĞI (ADIM 51'de ölçüldü):** uzak konteyner oturumları **Linux**'tadır;
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

## Açık borç (ADIM 51'in kapatmadığı)

- **Memory checkpoint YAZILAMADI — ve sebebi YAPISAL, #690'da ölçüldü.** Remote
  container'da `ecc`/`claude-mem` **kayıtlı değil** (`mcpServers` boş, `.mcp.json` yok),
  yani borç **bu ortamdan kapatılamaz**; yerel bir oturum ister. #690 içeriği hazır
  bıraktı → **`docs/memory/PENDING_CHECKPOINTS.md`** (ADIM 47 + ADIM 48, yapıştır-ve-sil).
  **ADIM 51 aynı ortamda koştu ve aynı sebeple kaçırdı** → o dosyaya **ADIM 51 girişi de
  gerekiyor**; borç artık dört slice. Sunucuları kaydetmek ya da remote oturumları
  ritüelin 4. maddesinden muaf tutmak **insan kararıdır**.
- **P1..P13 tanımı REPODA DEĞİL** (yalnız sohbet transkriptinde).
- `/library/{id}/validation-runs` **201'de kaldı** (ADIM 47) — ayrışma açık, PO kararı ister.

### AÇIK KUSUR — main'de İKİ slice "ADIM 48" adını taşıyor (DÜZELTİLMEDİ, bilerek)

`origin/main` @ `ce823a8` şu anda **çakışmalı**:
- `docs/PROJECT_HISTORY.md`'de **iki `## ADIM 48` bölümü** — `:7428` (#688, K-6b odak
  halkası) ve `:7547` (#686, kabul borcu B/01).
- `docs/ADIM48_LANDED_KICKOFF.md`'de **iki `# ADIM 48 LANDED` başlığı** ard arda.

**ADIM 51 bunu DÜZELTMEDİ ve düzeltmemelidir.** İki sebep:
1. **İkisi de merge edilmiş.** CLAUDE.md kuralı: merged başlıklar ve commit mesajları
   değiştirilemez → yeniden numaralandırma yasak. Belgelenmiş çare **başlık ekidir**
   (`ADIM 16 (sevk edilen)` / `ADIM 16 (ADR §12)` emsali).
2. **Başlığı yeniden yazmak docs-regresyon kapısını KIRAR.** Kapı `^-## ` arar; bir
   `## ADIM 48` başlığını değiştirmek onu *silinmiş* gösterir. Kapı burada **doğru**
   davranıyor: birleştirilmiş kayıtların tek taraflı yeniden yazılmasını engelliyor.

⇒ Çare **insan kararıdır**: ya başlık eki verilir (`ADIM 48 (K-6b)` / `ADIM 48 (borç B/01)`)
ve kapı bilerek bir kez aşılır, ya da çakışma emsallerdeki gibi **kayda geçip kalır**.
ADIM 51 yalnızca **kaydetti**. Ayrıca `docs/ADIM48_LANDED_KICKOFF.md`'nin banner'ı artık
iki başlığın neden ard arda durduğunu söylüyor (okuyan "bozuk" sanmasın).

### YENİ BULGU (ADIM 51) — docs-regresyon kapısının İKİ kör noktası · ÖLÇÜLDÜ

Bu oturumda main iki kez altımdan değişti ve **merge iki kez içerik SİLDİ**:

| Kayıp | Kapı yakaladı mı? | Neden |
|---|---|---|
| #688'in `## ADIM 48 — K-6b` **PROJECT_HISTORY bölümü** (119 satır) | ✅ **EVET** | `git diff origin/main -- docs/ \| grep '^-## '` ateşledi → geri yüklendi |
| #688'in **`CLAUDE.md` §Current position bloğu** (14 satır) | ❌ **HAYIR** | kapı yalnız `docs/` altına bakar; `CLAUDE.md` **kapsam dışı**. Elle fark edildi, geri yüklendi |

**İki kör nokta:** (a) kapı `CLAUDE.md`'yi hiç okumuyor, oysa §Current position tam olarak
slice özetlerinin biriktiği yer; (b) kapı yalnız `^-## ` başlıklarını görüyor — **başlıksız**
bir paragrafın silinmesi sessizce geçer (#688'in CLAUDE.md bloğu `>` blockquote'tur, `##`
değil). **Öneri (uygulanmadı):** guard'ı `git diff origin/main -- docs/ CLAUDE.md` yapmak
ucuz bir kazanç; başlıksız silmeleri yakalamak için satır-sayısı deltası eşiği gerekir ve
o bir ürün kararıdır. **Kural, bugünkü hâliyle:** bir merge sonrası **elle** doğrula —
`git log origin/main -1 --stat` ile dokunulan her dosyanın içeriğinin hâlâ orada olduğunu
gör. Yeşil kapı "hiçbir şey kaybolmadı" demek DEĞİLDİR.

### YENİ BULGU (ADIM 51) — `A08_COMPLETE` kapısının kapsamı dar · ÖLÇÜLDÜ, DÜZELTİLMEDİ

`scripts/generate_repository_facts.py::INVARIANT_GLOBS` yalnız şunları tarıyor: `README.md`,
`CLAUDE.md`, `backend/`+`frontend/`+`docs/README.md`, `docs/CODEMAPS/*.md`,
`docs/STAGE2_HANDOFF.md`, `docs/STAGE_BUILD_PLAN.md`, `docs/ARCHITECTURE.md`,
`docs/DOMAIN_MODEL.md`, `docs/USAGE.md`.

**Taranmayanlar arasında A-08'in en kritik üç belgesi var:** kanonik defter
(`docs/audit/a11y_screen_reader_audit_results.md`), kanonik readiness raporu
(`docs/releases/…_RC_Readiness_….md`, üstelik `doc-status: current`) ve **canlı kickoff**
(`docs/ADIM<n>_LANDED_KICKOFF.md`). Yani *"A-08 Complete yazılmasını"* engellemek için var
olan kapı, bu ifadenin en çok önem taşıdığı belgeleri **okumuyor**.

**Negatif kanıt (ADIM 51'de ölçüldü):** canlı kickoff'a `A-08 denetimi tamamlandı ve PASS.`
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
`A-08` ile `Complete` farklı satırlara denk gelirse kural **hiç ateşlenmez**. ADIM 51'de
bir yeniden sarma tam da bunu tersine çevirdi (yakalanmayan satır yakalanır oldu). Bir
satırı yeniden sararken kapının davranışını değiştirdiğini bil.

---

## Paste-ready resume prompt

```
ENTROPIA V18 — DEVİR: RC kapanışı, tek kalan blocker A-08

[[ Kendi ROL / OTURUM BAŞLANGICI / CANONICAL KAYNAK / TAVİZ VERİLEMEZ /
   PR DİSİPLİNİ bloklarınızı buraya aynen yapıştırın ]]

════════════════ ÖNCE DOĞRULA (bu prompta da güvenme) ════════════════
  git fetch --all --prune && git log --oneline origin/main -6
  gh pr list --state open
  gh issue view 514 --json state,stateReason,updatedAt
  cd backend && uv run python ../scripts/generate_repository_facts.py --root .. --check

Bu repoda main iş sırasında İKİ KEZ altımdan değişti. Aşağıdaki her sayı
2026-08-12 ölçümüdür; yeniden türet.

BASE: origin/main @ <ADIM 51 merge sha>

════════════════ NEREDE DURUYORUZ ════════════════
Kanonik rapor: docs/releases/Entropia_V18_RC_Readiness_2026-08-07.md
Verdict: BLOCKED — dört blocker'dan ÜÇÜ kapandı, biri kaldı (A-08).

ADIM 51 (kod değişmedi) A-08'in İZLEME ayrışmasını kapattı: #514
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
  K-2 skip link yok (23/23) · K-3 contentinfo yok (23/23) · K-6a odak GÖRÜNÜRLÜĞÜ ·
  K-4 /user-manual'da <h1> yok · K-5 h1→h3 atlaması (21/23) ·
  K-7 ilk DOM'da aria-live yok (21/23) · D-10 kontrast (AYRI EKSEN).
  ⇒ K-5/K-6a/K-7'nin ASIL sorusu denetimde cevaplanır. K-6b KAPANDI (#688), yeniden açma.

ASLA: #514'ü kapatma ya da açma (human-only) · hiçbir belgeye A-08 için
Complete/PASS/Done yazma · D-10'u ekran-okuyucu ekseniyle karıştırma.

════════════════ ÖNCELİK 2 — P11-1 BRANCH PROTECTION ════════════════
main'de branch protection ve ruleset YOK → on slice'ta kurulan kapıların
HİÇBİRİ kırmızıyken merge'i durduramıyor.
HAZIRLIĞI #683 İLE MERGE EDİLDİ (ruleset json + preflight + runbook).
Kalan iş AYARI UYGULAMAK — depo ayarı, agent yapamaz.
Bu bir REPO AYARI: agent UYGULAMAZ, HAZIRLAR.
UYARI: var olmayan bir job adını required yapmak TÜM merge'leri kilitler.

════════════════ KALAN İŞ ════════════════
| Kalem | Kim |
|---|---|
| A-08 denetimi | insan — tek blocker |
| ~~P11-1~~ KAPANDI (#691, ruleset 20765617) | — |
| K-2..K-7 | insan — K-6b #688'de KAPANDI; K-3/K-5/K-6a/K-7 A-08'den ÖNCE cevaplanamaz |
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
```
