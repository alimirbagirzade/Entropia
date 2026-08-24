<!-- doc-status: historical -->
> **HISTORICAL KICKOFF — canlı olan `docs/ADIM95_LANDED_KICKOFF.md`'dir.**
> Bu belge yazıldığı andaki durumu kaydeder; SHA'lar, sayılar ve "next" maddeleri bayat
> olabilir. Sayısal gerçekler için otorite: `CLAUDE.md` §Current position +
> `docs/generated/repository_facts.md` (üretilmiş).

# ADIM 94 LANDED — kabul borcu batch 17 (doc 01 Mainboard, backend): iki kriter kapandı · sıradaki slice için kickoff

> Tam kayıt: `docs/PROJECT_HISTORY.md` §ADIM 94. Bu belge **devam noktasıdır**, kayıt değil.

## Neredeyiz

- Taban main **`d47c5ba`**. **Ürün kodu değişmedi** (`backend/src` altında sıfır satır);
  diff = iki yeni integration case + kabul defteri + üretilmiş artefakt. Migration yok,
  OpenAPI değişmedi, alembic head `0043_i08_registry_strategy_fks`,
  `SHARED_ALLOCATION_STATUS` = `future_dev`.
  **Blocker sayısı DEĞİŞMEDİ (1 — yalnız A-08), verdict BLOCKED.**
- **Kapananlar: `MB-01` (c4) · `MB-27` (c4)** — doc 01'in BACKEND yüzeyi.
- **Tavanlar İNDİ: `partial` 75 → 73, `debt_class.B` 43 → 41**; açık borç **82 → 80**
  (A=1 · B=41 · C=6 · D=32). Clause `covered` 1044 → 1046, `uncovered` 87 → 85.
- **`MB-22.c4` on birinci bulgu olarak kaydedildi** (aşağıda) — kapatılmadı, yeniden
  sınıflandırılmadı.

## Bu slice'ın bıraktığı yeniden kullanım çapaları

- `backend/tests/integration/test_readiness_persistence.py` — dosyanın sonundaki
  **"Acceptance batch 17"** bölümü. Üç desen taşır:
  - **Guest refüzü + yan etkinin yokluğu** (`test_guest_ready_check_is_refused_server_side_and_writes_no_report`)
    — bir refüzün *hiçbir şey yazmadığını* iddia edeceksen bunu kopyala. **Kritik ayrıntı:
    sayımdan önce `session.rollback()` ÇAĞIRMA** — komutun yazdığı satırı atar ve
    assertion'ı totolojiye çevirir (bu slice tam olarak o hatayı yaptı ve negatif kontrol
    yakaladı).
  - **Etkin/saklanan durum çifti** (`test_disabling_a_live_item_stales_the_report_and_leaves_the_ready_scope`)
    — `get_readiness_report` `state`'i (yeniden hesaplanmış) ve `stored_state`'i (satırın
    kendisi) **ayrı** döner. Bir projeksiyon iddiasını ölçerken **ikisini birden** assert et;
    yalnız `state` okumak yeniden hesaplanmış bir projeksiyonu yeniden yazılmış bir satırdan
    ayıramaz.
  - **Kapsam dışına çıkma, çıkarımla değil doğrudan** — "Ready Check kapsamından çıkar"
    yarısı, disable'dan sonra **yeniden koşulan** bir Ready Check'in `COMPOSITION_EMPTY`
    raporlamasıyla ölçülür.
- **Çok dosyalı negatif kontrol harness'i** (`finally` ile geri yazan) — bu slice'ta onarıldı;
  deseni `PROJECT_HISTORY.md` §ADIM 94'te yazılı. Çok dosyalı bir kontrol yazarken **geri
  yazmayı `finally`'ye koy**, yoksa ortada patlayan bir tekillik assertion'ı ürün ağacını
  kirli bırakır ve **bir sonraki kontrol onu sessizce ölçer**.
- **Yerel Postgres (bu container'da çalışıyor, ama yeniden başlatmalarda DÜŞER):**
  ```
  PGDATA=/var/lib/postgresql/entropia-data
  su postgres -c "/usr/lib/postgresql/16/bin/pg_ctl -D $PGDATA -l /tmp/pg.log -o '-p 5432' start"
  ```
  İlk kurulum (cluster yoksa) ve `alembic upgrade head` adımları için
  `docs/ADIM93_LANDED_KICKOFF.md` §çapalar.

## Pazarlıksız — bu slice'ın öğrendikleri

1. **BİR YAN ETKİNİN YOKLUĞUNU İDDİA EDEN ASSERTION'IN ÖNÜNDE ONU GERİ ALAN HİÇBİR ŞEY
   OLAMAZ.** `pytest.raises` bloğundan sonra konan `session.rollback()`, "hiç satır yazılmadı"
   assertion'ını **her koşulda** doğru yapıyordu. Kusur ancak **üçüncü** negatif kontrol
   (guard'ı insert'in altına taşımak) **YEŞİL geçtiğinde** görüldü.
2. **YEŞİL BİR NEGATİF KONTROL İKİ ŞEY DEMEK OLABİLİR:** yama hiç uygulanmadı (ADIM 88), ya da
   **assertion totolojik** (bu slice). İkisini ayırt etmek için yamanın uygulandığını **ayrıca**
   assert et — bu slice onu yaptığı için ikinci şıkka indirgeyebildi.
3. **İLK KIRMIZI SONRAKİ ASSERTION'I GÖLGELER** (ADIM 93'ün dersi burada da geçerli): iki
   guard-kaldırma kontrolü de `pytest.raises` satırında kırmızı verip rapor-sayısı satırına
   **hiç ulaşmıyordu**. Gölgelenen assertion'ı ölçmek için gölgeyi kaldıracak bir kontrol kur.
4. **BİR REFÜZ İKİ KAPIYLA KORUNUYOR OLABİLİR.** `require_authenticated`'ı silmek testi
   `AccessDeniedError` ile kırmızıya çevirir — refüz **hâlâ** vardır. O kırmızı, clause'un
   ("sunucu tarafında reddedilir") ihlalini değil **auth kapısını** kanıtlar; ADIM 84'ün
   `TL-22.c4` notu bunu zaten söylüyordu.
5. **SKIP'Lİ YEŞİL EXIT CODE KANIT DEĞİLDİR.** Container yeniden başlayınca Postgres düştü ve
   iki yeni case `ss` (iki SKIPPED) + **exit 0** verdi. Koşu çıktısının **gövdesine** bak.
6. **AÇIK PR'LARI SLICE'A BAŞLAMADAN TARA.** Bu slice ilk olarak doc 10'u seçmişti; **PR #806
   zaten açıktı ve tam o iki kriteri** (`RF-07` + `RF-12`) sürüyordu. Başlıklar bunu söyler —
   ama **numarayı** başlıktan değil, o PR'ların eklediği `docs/ADIM<n>_*.md` **dosya
   yollarından** ölç.

## Sıradaki tasarım işaretleri — ÖNCE ÖLÇ

- **Kalan sınıf-B yoğunluğu (bu freeze'den; sen yine ölç):** doc 14 (`RC`) · doc 21 (`UM`) ·
  doc 09 (`ESP`) · doc 06 (`CP`) · doc 01'in kalanı (`MB-22` **bulgu**, dokunma).
  **Doc 10 (`RF`) için #806'nın durumunu kontrol et.** Tek otorite
  `docs/audit/acceptance_coverage_baseline.json` + `acceptance_semantic_scan.py --report`.
- **`ESP-20` tek kriterde İKİ açık clause taşıyor** (`.c2` listeleme, `.c3` doğrudan id
  sorgusu) — ikisi de görünürlük/yetki ekseni, tek bir backend testi ikisini birden
  kapatabilir. Ama önce **sevk edildiğini** doğrula.
- **`UM-13.c3` eşzamanlılık ister** (iki paralel append'in stream lock'ta serileşmesi) —
  bu, tek session'lı bir integration testiyle **kurulamayabilir**; ikinci bir bağlantı gerekir
  (emsal: `test_readiness_persistence.py`'nin komşusu olan concurrent demotion race).
- **Kabul borcu hattı mühendislik hattından AYRI.** Mühendislik tarafında açık PR'lar
  #805 (`C4` containment gate onarımı) ve #802. Aynı PR'da karıştırma.

## Çalışma yöntemi (bu dalgada işe yarayan)

- Sıra: **açık PR'ları tara → kriter id'sini grep'le → map'i oku → ürünü oku → test yaz →
  negatif kontrol (yama uygulandı mı + hangi assertion kırmızı) → `--ratchet` →
  `--write-ledger` + `--write-report` → `generate_repository_facts.py --root ..`**
- **Kriter-düzeyi `status`/`debt_class`'ı da güncelle**, yalnız clause'u değil — bu slice
  `MB-01`'in kriter satırını atladı ve tavan bir kriter eksik düştü (`--ratchet` çıktısını
  okumak yakaladı).
- **YAML notu düz skalerse `: ` ekleyemezsin** — notu tek tırnağa al (bu slice bir
  `ScannerError` ile öğrendi; içeride apostrof varsa ikile).
- Backend alt küme: `.venv/bin/python -m pytest <dosya> -q --no-cov -k <ifade>`
  (**`--no-cov` şart**). Çıktıyı dosyaya yaz, exit code'u **ayrı** oku.
- **Koşulamayanlar:** frontend (`node_modules` yok) ve E2E/A11Y (`ghcr.io` gateway'de 403).
  Oralara assertion yazma, **sınırı yaz**.

## Paste-ready resume prompt

```
ENTROPIA V18 — kabul borcu batch 18

ROL: Entropia V18 Principal Engineer.
[ENTROPIA ORTAK SÖZLEŞME bloğunu uygula]

ÖNCE DURUM ÖLÇ — hiçbir SHA'yı ve hiçbir sayıyı bu prompttan alma:
  git fetch && git log --oneline origin/main -6
  git show origin/main:docs/PROJECT_HISTORY.md | grep '^## ADIM' | tail -4
  git show origin/main:docs/PROJECT_HISTORY.md | grep -o 'batch 1[0-9]' | sort -u
  mcp__github__list_pull_requests(state=open)
  # AÇIK PR'LARIN BAŞLIĞINI OKU: aynı belgeyi/yüzeyi süren bir dal varsa BAŞKA belge seç.
  # NUMARAYI başlıktan değil, o PR'ların eklediği docs/ADIM<n>_*.md YOLLARINDAN ölç.
  CANLI kickoff = en yüksek numaralı docs/ADIM<n>_LANDED_KICKOFF.md — onu oku, bunu değil.

TAVANLAR: bu prompttan OKUMA. Tek otorite acceptance_coverage_baseline.json `ceilings`.
  Ratchet YALNIZ AŞAĞI iner; total_criteria bir TABANDIR.

ORTAM: bu container'da Postgres 16 kurulu ama YENİDEN BAŞLATMALARDA DÜŞER. Koşudan önce
  ayakta olduğunu doğrula; `ss` (skipped) + exit 0 bir yeşil DEĞİLDİR.

GÖREV: sınıf-B kabul borcundan TEK belge + TEK yüzey seç ve kapat.
  1) cd backend && .venv/bin/python ../docs/audit/acceptance_semantic_scan.py --root .. --report
  2) ADAY SEÇTİKTEN SONRA, TEST YAZMADAN ÖNCE:
       grep -rn "<KRİTER-ID>" frontend/src backend/tests
     Kapsama zaten sevk edilmiş olabilir -> cite et, yazma (ADIM 88).
  3) Kriterin adlandırdığı davranışın gerçekten sevk edildiğini üründe DOĞRULA. Üç şekli ayır:
       unshipped (kurulabilir, kod yok -> D) · unconstructible (erişilebilir ekran yok -> C)
       · unfalsifiable (kırmak ÇOK NOKTALI bir değişiklik ister -> işaretle, kapatma)

HER CLAUSE İÇİN ZORUNLU:
  a. Mevcut testler bu kusur altında yeşil mi kalıyor? Kalıyorsa yeni assertion BAŞKA bir
     eksene bakmalı — yoksa işaretleme yapıyorsun, kapsama değil.
  b. Negatif kontrol koş VE YAMANIN UYGULANDIĞINI DOĞRULA (eşleşme sayısını assert et).
     Çok dosyalı kontrolde geri yazmayı `finally`'ye koy — yarıda patlarsa ağacı kirli bırakır
     ve BİR SONRAKİ kontrol onu sessizce ölçer (ADIM 94).
  c. Kırmızının HANGİ assertion'da olduğunu oku. İlk kırmızı sonrakini GÖLGELER: gölgelenen
     assertion'ı ölçmek için gölgeyi kaldıran ayrı bir kontrol kur.
  d. YEŞİL bir kontrol iki şey demek olabilir: yama uygulanmadı, ya da ASSERTION TOTOLOJİK
     (ADIM 94: `pytest.raises`'ten sonraki `session.rollback()` "satır yazılmadı" iddiasını
     her koşulda doğru yapıyordu). Bir yan etkinin yokluğunu iddia ediyorsan, önünde onu geri
     alan hiçbir şey olmadığını doğrula.
  e. Koşamadığın suite'e (E2E/A11Y) assertion YAZMA; sınırı yaz.
  f. Kriterin SON clause'u kapanıyorsa KRİTER-DÜZEYİ `status`'ü de covered yap ve
     `debt_class`'ı KALDIR (yalnız clause'u güncellemek tavanı eksik indirir).

KAPATMAYA ÇALIŞMA (bulgular): TL-01.c4, TL-02.c2, TL-11.c3, TL-14.c4, TL-16.c4, RD-01.c4,
  RD-05.c5, RD-12.c4, RD-13.c4, PC-20.c3, PC-02.c2, TS-07.c2, MB-22.c4
  + `unfalsifiable: true` clause'lar. Yeniden sınıflandırma tavan yükseltir = adjudication.

DOC 05, DOC 18, DOC 02-BACKEND, DOC 17-BACKEND ve DOC 01-BACKEND BİTTİ. Doc 10 backend'i
  #806 sürüyordu — durumunu kontrol et. Başka belge/yüzey seç.

KAPANIŞ: CLAUDE.md §Session CLOSING'in 6 maddesi. ADIM numarasını VE parti etiketini
  commit'ten hemen önce yeniden doğrula. Merge edilmiş ad kazanır.
  PR AÇIKKEN main ilerlerse: sunucu tarafı "Update branch" DÜĞMESİNE DAYANMA — serileştirilmiş
  defterleri (baseline JSON, ledger, traceability, facts) sessizce BİRLEŞTİRİR (ADIM 93'te
  ölçüldü). Dalı güncel main üzerine yeniden kur, yamaları yeniden uygula, artefaktları
  yeniden üret, --ratchet'i merged ağaçta yeniden koş.
  PR'ı main'e aç, DUR, MERGE ETME.
```
