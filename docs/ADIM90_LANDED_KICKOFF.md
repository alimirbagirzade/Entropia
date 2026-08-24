<!-- doc-status: historical -->
> **HISTORICAL KICKOFF — canlı olan `docs/ADIM92_LANDED_KICKOFF.md`'dir.**
> **Bu belge CANLI OLARAK HİÇ DOĞMADI, bilerek.** ADIM 90 geriye dönük bir kayıttır (#779'un ritüeli);
> o dal sıra beklerken önce **#803 = ADIM 91** (`42c8185`), sonra **#799 = ADIM 92** (`3994725`)
> indi — yani ağaçtaki en yüksek numaralı kickoff **iki kez** başkasınınki oldu ve
> `check_classification` canlı işareti **orada** ister. ADIM 82 emsali: geriye dönük kaydın canlı
> seed'i en yüksek numaralı belgedir. Aşağısı yazıldığı andaki ölçümdür — bayat
> olabilir; sayısal otorite `CLAUDE.md` §Current position + `docs/generated/repository_facts.md`.

# ADIM 90 LANDED — kayıtsız inen #779'un ritüeli (G6/G7 kapı satırları) · sıradaki slice için kickoff

> Ölçüm anı: **2026-08-19**, taban main **`ee5ab38`** (#797 = ADIM 88 dahil; dal onun üstüne **rebase edildi**). Bu belgedeki her sayı o
> commit'e karşı ölçülmüştür ve **present-tense okunmamalıdır** — `git fetch` ile yeniden ölç.
> Sayısal otorite: `docs/generated/repository_facts.md` (üretilmiş) + `CLAUDE.md` §Current position.

## Neredeyiz

**ADIM 90 defterdir, ürün kodu değildir.** Kaydettiği slice (#779, `a5bc27f`) tek bir plan
belgesine dokundu (+37/−7) ve **hiçbir sayıyı oynatmadı**. alembic head
**`0043_i08_registry_strategy_fks`** · `ENGINE_VERSION` **değişmedi** · OpenAPI **değişmedi** ·
`SHARED_ALLOCATION_STATUS` = **`future_dev`** · blocker **1 (yalnız A-08)** · verdict
**BLOCKED** · **açık kapı 11**.

Kapatılan şey bir kusur değil, bir **çelişkiydi**: `final_closure_ordered_plan_2026-08-13.md`
§2'nin sayım tablosu `G6`/`G7`'yi çözülmüş sayarken satırların kendisi `UNSIGNED` diyordu.
Satırlar ölçülerek düzeltildi, eski metin `Was "…"` ile korundu.

## Bu slice'ın bıraktığı yeniden kullanım çapaları (tam adlarla)

| Çapa | Nerede | Ne işe yarar |
|---|---|---|
| `§2` kapı sicili (G1–G16) | `docs/implementation/final_closure_ordered_plan_2026-08-13.md` | tek kapı tablosu; **satır no değil bölüm adı** taşır artık |
| `§GÜNCELLEME 2026-08-19` notu | aynı dosya, tablonun hemen altı | üç issue kapanışının **neden** iki farklı sonuç verdiğini yazan tablo |
| `§Karar 2 ▸ İMZA SATIRI` | `docs/decisions/closure_product_decisions_2026-08-13.md` | G6+G7'nin imzası (A1+A2, 2026-08-14) |
| `§Karar 3 ▸ İMZA SATIRI` | aynı dosya | **G8** — tamamen boş, `#559` kapalı olmasına rağmen |
| `scripts/ci-install-playwright-chromium.sh` | #795 ile geldi | **her yeni E2E işi** buradan geçmeli, `npx playwright install` yazılmaz |

## Pazarlıksız — bu slice'ın öğrendikleri

1. **`issue CLOSED ≠ çözüldü` bir slogan değil, ÜÇ KEZ FARKLI SONUÇ VEREN bir testtir.**
   Aynı gün kapanmış üç issue'dan **biri** kapıyı çözdü (#558 — kapanış yorumu üç karar
   sorusunu yazılı cevaplıyor **ve** imza bağımsız olarak `§Karar 2`'de duruyor), **ikisi
   çözmedi** (#559, #544 — sıfır yorum, closing PR yok, imza bloğu boş). Kapanışı imza saymak
   **11 açık kapıyı 9'a** indirirdi. **İndirme.**
2. **Bir kapıyı düşürmeden önce üç şeyi birden ölç:** (a) issue durumu, (b) issue'da **yazılı
   karar** var mı, (c) `decisions` belgesindeki **imza kutusu**. Üçü ayrışabilir; ayrıştığında
   otorite **imza kutusudur**, issue durumu değil.
3. **`Was "…"` deseni zorunludur.** Düzeltilen kapı satırı eski metnini alıntılamalı, yoksa
   sicil bir düzeltmeyi sessizce yutar ve *"hep böyleydi"* diye okunur.
4. **`grep` sayısı tek başına kanıt değildir.** Bugün `grep -c 'decisions:[0-9]'` → **2** döner
   ve bu **eksik süpürme değildir**: iki eşleşme de `Was "…"` alıntısının içinde. Canlı
   işaretçi **0**. Alıntıyı temizlemek düzeltmenin kanıtını siler.
5. **`cancelled` ≠ `failure`, ama artık kökü de biliniyor.** GitHub **timeout'u `cancelled`
   diye raporlar**. #779'un dalında A11Y işi `Install Playwright browsers` içinde **38 dk 50 sn**
   asılıp iptal oldu (`Run the axe-core a11y scan` = **skipped**, hiçbir test gövdesi koşmadı);
   rerun **3 dk 08 sn**'de yeşil. Kök #795'te ölçüldü: `azure.archive.ubuntu.com` aynası düştü.
   **Ayırt edici:** aynı attempt'te üç kardeş işin aynı adımı yeşildi (1–3 dk) → **genel kesinti
   değil**. *"Install yavaş, tavanı büyüt"* **yanlış düzeltmedir**.
6. **Kırmızıyı görünce log'a bak, conclusion'a değil** — ve bir işi rerun etmeden önce
   `cancelled`'ın **timeout mu supersede mi** olduğunu adım sürelerinden oku.

## Ortam — devir promptunda BAYAT olan not

**`actions:write` VAR.** `actions_run_trigger` (`rerun_workflow_run` / `rerun_failed_jobs`) bu
oturumun GitHub yüzeyinde mevcut; *"403, rerun edilemez"* notu **bayattır**. Bu slice onu
**kullanmadı** (kırmızı yoktu) — yetenek kaydedildi, kullanım iddia edilmedi.

## Sıradaki iş — ÖNCE ÖLÇ, sonra seç

**Bu slice hiçbir mühendislik kalemini ilerletmedi ve ilerletmemeliydi.** Sıradaki iş
ölçülerek seçilmeli. Bu belge yazılırken **açık ve numara iddia eden** PR'lar:

| PR | iddia | durum | konu |
|---|---|---|---|
| **#797** | ADIM **88** | ✅ **İNDİ** (`ee5ab38`) | kabul borcu batch 14 (doc 05 frontend, `TL-18`) |
| **#799** | ADIM **89** | açık | `C4` / E5 — worker'ın paylaşımlı saat dalı |
| **#800** | — | açık | `C4` varyantı, importer guard bilerek genişletilmiş |
| **#801** | — | ✅ **İNDİ** (`d4efac3`) | `C4` worker importer-visibility kararının brifingi (yalnız karar belgesi, imza **boş**) |

**89 BOŞ AMA ALINAMAZ:** #799 açık ve `docs/ADIM89_LANDED_KICKOFF.md` ekliyor → o yolu almak
add/add çakışması üretirdi. Numara boşluğu kabul edilir; **numaralar yeniden atanmaz**.

**`C4` HATTI ÜÇ AÇIK PR TARAFINDAN SÜRÜLÜYOR (#799, #800, #801) → o hatta DOKUNMA**
(ADIM 87'nin ölçtüğü `HAT B` çakışmasının aynısı). Kabul borcu hattının **#797'si indi** (ADIM 88);
doc 05'te bir test slice'ının kapatabileceği satır **kalmadı**. Yeni parti seçmeden önce **açık PR'ların ekleyeceği dosya yollarını** listele.

## Çalışma yöntemi (bu dalgada işe yarayan)

* `git fetch` → `git log --oneline origin/main -8` → `grep -n '^## ADIM' docs/PROJECT_HISTORY.md | tail -5`.
* **Numarayı açık PR'ların DOSYA YOLLARINDAN doğrula**, başlıklarından değil: her aday dalın
  eklediği `docs/ADIM<n>_LANDED_KICKOFF.md` yolunu listele. `check_classification` bunu asla
  yakalayamaz — çakışan dalların hepsi kendi içinde tutarlıdır.
* Bir issue/PR gövdesini **otorite sayma**; GitHub API'sinden durumu, yorumları ve
  `closed_by_pull_requests`'i ayrı ayrı oku.
* Ürün kodu değişmediyse **suite koşma** ve **koşmadığını açıkça yaz**; doğrulama
  `generate_repository_facts.py --check` + `git diff --cached -- docs/ | grep '^-## '` (BOŞ olmalı).

## Paste-ready resume prompt

```
ENTROPIA V18 — SIRADAKİ SLICE

ÖNCE OKU: CLAUDE.md §Session START + §Session CLOSING · docs/ADIM90_LANDED_KICKOFF.md

ÖNCE ÖLÇ, DEVRALMA (bu blok BAYAT-VARSAYILANDIR):
  · git fetch && git log --oneline origin/main -8
  · grep -n '^## ADIM' docs/PROJECT_HISTORY.md | tail -5      → numaranı BURADAN al
  · git ls-tree --name-only origin/main docs/ | grep ADIM | sort -V | tail
  · list_pull_requests(state=open) → HER açık PR'ın EKLEYECEĞİ docs/ADIM<n>_LANDED_KICKOFF.md
    YOLUNU çıkar. Çakışma başlıkta değil DOSYA YOLUNDADIR ve hiçbir CI kapısı onu görmez.
  · Canlı kickoff'u adıyla arama: en yüksek numaralı ADIM<n>_LANDED_KICKOFF.md'dir.

DURUM (2026-08-19, main a5b46ab — YENİDEN ÖLÇ):
  alembic head 0043_i08_registry_strategy_fks · ENGINE_VERSION değişmedi ·
  SHARED_ALLOCATION_STATUS=future_dev · blocker 1 (yalnız A-08) · BLOCKED · açık kapı 11.

SIRADAKİ İŞ — ÖNCE ÇAKIŞMA TARA:
  · C4 hattı ÜÇ açık PR tarafından sürülüyordu (#799/#800/#801) → dokunmadan önce ölç.
  · Kabul borcu hattını #797 sürüyordu (doc 05 frontend, TL-18).
  · Kapı düşürmeyi düşünüyorsan: issue durumu + issue'da YAZILI karar + decisions imza
    kutusu — ÜÇÜNÜ birden ölç. Otorite imza kutusudur. #559/#544 kapalı ama G8/G14 AÇIK.

PAZARLIKSIZ:
  · Ürün kodu değişmediyse suite koşma, koşmadığını AÇIKÇA yaz.
  · Yeni E2E işinde `npx playwright install` YAZMA → scripts/ci-install-playwright-chromium.sh.
  · `cancelled` bir timeout olabilir — conclusion'a değil ADIM SÜRELERİNE bak.
  · Kapanışta: PROJECT_HISTORY kaydı + CLAUDE.md §Current position (5–6 satır) + yeni kickoff
    `current` / öncekini `historical` + node scripts/memory_index.mjs --sync --only <slug>.
  · DAL docs/adim-<n>-landed · Draft PR · MERGE ETME (self-merge bloklu).
```

## PAZARLIKSIZ

* **Hiçbir imza kutusunu doldurma, hiçbir issue durumunu değiştirme.** `#514` `human-only`.
* **Ratchet yalnız AŞAĞI iner.** Kabul borcu tavanlarını yükseltme.
* **Tavan/sayı iddiası yazacaksan üreteci koştur** — `generate_repository_facts.py --check`
  CI'da bloklayıcıdır ve bu bloğa aykırı bir head/ENGINE_VERSION iddiasını kırmızıya çevirir.
