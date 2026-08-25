<!-- doc-status: current -->
> **CANLI KICKOFF.** Bu belge en yeni slice'ın handoff'udur. Bir sonraki slice inince
> `historical`a demote edilir ve yerine yenisi geçer (`check_classification` CI'da doğrular:
> daha yüksek numaralı bir `docs/ADIM<n>…KICKOFF.md` varken canlı işaret eski belgede duramaz).

# ADIM 108 LANDED — kayıtsız inen #822'nin ritüeli: dört bayat precheck advisory `note`'u düzeltildi (§6.1b kapandı) · sıradaki slice için kickoff

> Tam kayıt: `docs/PROJECT_HISTORY.md` §ADIM 108. Bu belge **devam noktasıdır**, kayıt değil.

## Neredeyiz

- Taban main **`32d2c96`** (= kaydedilen slice PR #822'nin kendisi; onun tabanı `42c6377` = ADIM 107
  / #821). `git fetch` sonrası en yüksek kayıt **107**, canlı kickoff `ADIM107`, **açık PR listesi
  BOŞ** → bu slice **108**. Boş liste bir **anlık görüntüdür, garanti değil** (ADIM 100/103).
- **Bu bir DEFTER slice'ıdır.** Kaydettiği #822 kendi ritüelini yazmadan inmişti
  (`grep -c '#822' docs/PROJECT_HISTORY.md` → **0**, ölçüldü).
- **Ürün kodu değişti ama YALNIZ PROZA:** üç dosya, `20-a11y-prechecks.spec.ts`'te **dört satır,
  dördü de bir `note:` değeri**. Migration yok, OpenAPI değişmedi, alembic head
  `0043_i08_registry_strategy_fks`, `ENGINE_VERSION` değişmedi, `SHARED_ALLOCATION_STATUS` =
  `future_dev`. **Blocker sayısı DEĞİŞMEDİ (1 — yalnız A-08), verdict BLOCKED.**
- **Kabul borcu tavanları OYNAMADI:** `partial` **55** · `uncovered` **7** · A=1 · B=23 · C=6 · D=32
  (ADIM 107'den beri aynı; baseline dosyasına en son `42c6377` dokundu).
- **A-08 el değmedi:** **2/184** hücre · **0/10** akış · çıkış kriterleri **0/4** · **#514 AÇIK** ·
  §6 K-tablosu değişmedi. **Hiçbir belgeye `Complete`/`PASS`/`Done` yazma.**

## Bu slice'ın bıraktığı yeniden kullanım çapaları (tam sembol adlarıyla)

- **`frontend/e2e/specs/20-a11y-prechecks.spec.ts`** — dört advisory'nin `note:` metni artık güncel.
  Predicate / eşik / `observed` / per-route sayım / gating **el değmedi**. Yeni bir advisory eklerken
  metnini **kararın adıyla** (D-11, K-4, PR #685) ve **sembolle** (satır numarasıyla değil) yaz.
- **`frontend/e2e/utils/pageTruth.ts::PageContract.level`** — bir rotanın başlık seviyesinin
  **beyan edildiği** yer. `<h1>` sapması buraya yazılır, rotor'la keşfedilmez.
- **`frontend/src/app/Layout.tsx:397` / `:465`** — skip link (`a.skip-link` → `#main-content`) ve
  `<main id="main-content" tabIndex={-1}>`. K-2'nin sevk edilmiş hâli; testi
  `src/test/a11ySkipLink.test.tsx`.
- **`docs/audit/a11y_screen_reader_audit_results.md` §6.1b** — artık **kapalı**; dördün önceki metni
  `Note said` sütununda **korundu** (düzeltmenin neyi değiştirdiği okunabilsin diye).
- **`docs/implementation/a11y_screen_reader_audit_runbook.md` §0** — denetçinin bir sayfalık kartı;
  *"kaynakta düzeltildi, kanıtta donmuş duruyor"* ayrımını taşıyor.
- **`docs/audit/a11y_ci_ratchet_and_adjudication.md` §4b** — imzalı a11y kararlarının sicili
  (**D-10** kontrast · **D-11** landmark). **İmzalayan adı olmadan `D-xx` YAZILMAZ.**

## Pazarlıksız — bu slice'ın öğrendikleri

1. **BİR CHECKLIST'İ DÜZELTMEK, ONU ALINTILAYAN MAKİNE ÇIKTISINI DÜZELTMEZ.** ADIM 63 A-3'ü yeniden
   yazdı — **yalnız checklist'te**; precheck 22 advisory'nin yanına retired soruyu basmaya devam etti
   ve runbook §4 denetçiyi tam oraya yolluyordu. Bir soruyu/kuralı değiştirdiğinde **onu alıntılayan
   her yüzeyi** ara: test çıktısı, warning metni, runbook, seed, fixture.
2. **BAYAT BİR İŞARETÇİYİ DÜZELTMEK YENİSİNİ DOĞURUR.** Runbook §0'ın *"bu bayat note'u yoksay"*
   bloğu, note düzelince **kendisi bayatladı**. Aynı PR'da düzeltildi. Düzeltmenin **kendi
   gölgesini** ölç.
3. **BİR ADVISORY'Yİ BUGÜN GEÇİYOR DİYE SİLME.** K-2 ve K-4 dalları ulaşılamaz (ikisini de PR #685
   kapattı) → **REGRESYON TRIPWIRE'ı** olarak tutuldular ve notları bunu **yazıyor**. Silmek, geri
   gelişi fark edecek tek şeyi silerdi.
4. **DİSPOZİSYON ≠ ÖLÇÜM.** D-11 `contentinfo` yokluğunun **ne anlama geldiğini** sabitledi; advisory
   **susturulmadı**, hâlâ raporlanıp hâlâ sayılıyor. Bir kararı "advisory'yi kapat" diye okuma.
5. **`npm run typecheck` `frontend/e2e/`'yi KAPSAMAZ** (`frontend/tsconfig.json` `"include": ["src"]`,
   `typecheck` = `tsc -b --noEmit`, project reference yok). Gerçek kapı:
   **`npx tsc --noEmit -p e2e/tsconfig.json`**. `e2e/` düzenlediysen **o komutu koş**.
6. **DONMUŞ KANIT DÜZELTİLMEZ.** `docs/releases/evidence/` o tarihte ne basıldığının kaydıdır; eski
   prozayı taşımaya devam eder ve **bu doğrudur**. Arşiv bir raporu okuyan denetçiye bunu **söyle**.
7. **NEGATİF KONTROL BİR PROZA DEĞİŞİKLİĞİNDE DE KOŞULUR** — ama kapının **kendisine** karşı:
   metni kaçışsız biçime döndür, `TS1005`'i **düzenlenen bölge başına** oku (bu slice **iki kez**
   koştu: `:271` ve `:243`). Yeşil bir kapı, koştuğunu kanıtlamadıkça kanıt değildir.
8. **KOŞAMADIĞIN SUITE'E ASSERTION YAZMA, SINIRI YAZ.** Precheck spec'i seeded stack ister; yerelde
   koşulmadı, otorite CI (head `87f51ed`: **18 success / 4 skipped / 0 failure**).

## Sıradaki iş — ölçülmüş adaylar (yine de kendin ölç)

- **`C6` DEĞİL.** Ön koşulları `G11` (P2) + `G12` (P8) ve **ikisi de imzasız**. Brifingli ≠ imzalı.
  **İmzasız bir kapının arkasındaki slice'a başlama.**
- **Kabul borcu partisi (backend): YOK.** ADIM 107'nin ölçümü: *"backend'de testle kapanabilir
  sınıf-B satır KALMADI"*. **Frontend bitiricileri açık:** `UM-15.c3` · `RC-09.c3` · `CP-03.c4` ·
  `AT-07`. Parti seçmeden önce taze `--report` koş — sayıyı buradan **okuma**.
- **Kayıtsız inen slice ritüeli: #820 AÇIK.** §6.1b'yi ilk yazan slice; kendi `## ADIM` kaydı yok.
  ADIM 108 onu **uydurmadı** (ADIM 97 emsali). Kaydı sahibi yazmalı; başka bir oturum yazacaksa
  **önce ölçsün** (`grep -c '#820' docs/PROJECT_HISTORY.md`).
- **A-08 denetimi:** tek kalem **denetimin kendisi**. Bir agent bunu kapatamaz; runbook §0 kartı
  bir sonraki oturumun ne yapacağını yazıyor (SR-2, rota 1 `/`, A-3'ten sonra A-4..A-8).

## Paste-ready resume prompt (bir sonraki oturuma yapıştır)

```
Entropia — oturum başlıyor.

ÖNCE DOĞRULA (handoff STALE-BY-DEFAULT):
  git fetch && git log --oneline origin/main -3
  grep -o '^## ADIM [0-9]*' docs/PROJECT_HISTORY.md | grep -o '[0-9]*' | sort -n | tail -1
  açık PR listesi (list_pull_requests, state=open) — BOŞ liste bir ANLIK GÖRÜNTÜDÜR, garanti değil.
Ölçülen hâl (2026-08-25, bayat olabilir): main 32d2c96 · en yüksek ADIM 108 ·
  canlı kickoff docs/ADIM108_LANDED_KICKOFF.md · açık PR yok.

OKUMA SIRASI: bu belge → docs/STAGE2_HANDOFF.md (§Stage 108 + §Next) →
  docs/PROJECT_HISTORY.md §ADIM 108 (hedefli, baştan sona DEĞİL) → ilgili docs/spec/NN_*.
Hafıza: node scripts/memory_index.mjs --sync (~3 sn, taze container'da store BOŞ).

DURUM: blocker 1 (yalnız A-08), BLOCKED. alembic head 0043_i08_registry_strategy_fks.
  ENGINE_VERSION ve OpenAPI değişmedi. SHARED_ALLOCATION_STATUS=future_dev.
  Kabul borcu tavanları: partial 55 · uncovered 7 · A=1 B=23 C=6 D=32 (ADIM 107'den beri aynı).
  A-08: 2/184 hücre · 0/10 akış · 0/4 çıkış kriteri · #514 AÇIK.

İŞ SEÇİMİ — sırayla ölç:
  1. C-hattı: C6 ön koşulları G11 + G12 İMZASIZ → BAŞLAMA. Yeni bir C3/C4 dalı da AÇMA (indi).
  2. Kabul borcu: backend'de kapanabilir sınıf-B satır YOK (ADIM 107 ölçümü). Frontend
     bitiricileri: UM-15.c3 · RC-09.c3 · CP-03.c4 · AT-07. Taze --report'tan DOĞRULA.
  3. Kayıtsız inen slice ritüeli: #820 açık (grep -c '#820' docs/PROJECT_HISTORY.md ile ölç).
     Kaydı UYDURMA — ölçtüğünü yaz, ölçemediğini sınır olarak yaz (ADIM 97/108).

frontend/e2e/ DÜZENLİYORSAN — ADIM 108'in iki tuzağı:
  a. `npm run typecheck` bu ağacı KAPSAMAZ (frontend/tsconfig.json include=["src"]).
     Gerçek kapı: cd frontend && npx tsc --noEmit -p e2e/tsconfig.json. Onu KOŞ.
  b. 20-a11y-prechecks.spec.ts'te İKİ advisory dalı bugün ulaşılamaz (K-2 skip link,
     K-4 h1 — ikisini de PR #685 kapattı). REGRESYON TRIPWIRE'ları, SİLME.
  c. Bir advisory'nin `note` metnini değiştirmek predicate/observed/sayım/gating'i
     DEĞİŞTİRMEZ ve DEĞİŞTİRMEMELİDİR. Advisory SUSTURMA — dispozisyon ≠ ölçüm (D-11).
  d. docs/releases/evidence/ DÜZELTİLMEZ (donmuş kayıt). Eski prozayı taşır, doğrudur.

BİR KURAL/SORU/CHECKLIST DEĞİŞTİRİYORSAN (ADIM 108'in asıl dersi):
  onu ALINTILAYAN her yüzeyi ara — test çıktısı, ::warning:: metni, runbook, seed, fixture.
  Checklist'i düzeltmek makine çıktısını düzeltmez. Sonra kendi düzeltmenin GÖLGESİNİ ölç:
  "bu bayat şeyi yoksay" diyen her blok, o şey düzelince KENDİSİ bayatlar.

NEGATİF KONTROL — proza değişikliğinde bile:
  Kapının kendisine karşı koş (metni kaçışsız biçime döndür), DÜZENLENEN BÖLGE BAŞINA bir kez,
  ve KIRMIZININ HANGİ SATIRDA olduğunu OKU. Yeşil kontrol = yama uygulanmadı VEYA kapı vacuous.
  Koşamadığın suite'e (E2E/A11Y/seeded stack) assertion YAZMA — sınırı yaz, otorite CI.

KAPANIŞ: CLAUDE.md §Session CLOSING 6 madde (yeni endpoint/tablo/sayfa/job yoksa md. 5 atlanır).
  Kickoff ÇİFTİ birlikte: yeni `current` + öncekini `historical`. Numarayı commit'ten HEMEN ÖNCE
  yeniden doğrula (çakışma başlıkta değil DOSYA YOLUNDA ölçülür — ADIM 91).
  Rebase gerekiyorsa "Update branch" düğmesini KULLANMA; iki tarafı koruyarak çöz, üretilmişleri
  yeniden üret, tavanı taze --report'tan ÖLÇ (taşıma — ADIM 98/100).
  Push öncesi: grep -c '^## ADIM' docs/PROJECT_HISTORY.md (DÜŞMEMELİ).
  git guard: fetch/doğrulama ile push'u AYRI Bash çağrılarına böl.
  PR'ı main'e aç; self-merge bloklu → yeşil olunca kullanıcıdan merge iste.
```
