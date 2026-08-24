<!-- doc-status: historical -->
> **CANLI KICKOFF.** Bu belge en yeni slice'ın handoff'udur. Bir sonraki slice inince
> `historical`a demote edilir ve yerine yenisi geçer (`check_classification` CI'da doğrular:
> daha yüksek numaralı bir `docs/ADIM<n>…KICKOFF.md` varken canlı işaret eski belgede duramaz).

# ADIM 93 LANDED — kabul borcu batch 16 (doc 02 backend): dört kriter kapandı · sıradaki slice için kickoff

> Tam kayıt: `docs/PROJECT_HISTORY.md` §ADIM 93. Bu belge **devam noktasıdır**, kayıt değil.

## Neredeyiz

- Taban main **`3994725`**. **Ürün kodu değişmedi** (`backend/src` altında sıfır satır);
  diff = beş yeni integration case + kabul defteri + üretilmiş artefakt. Migration yok,
  OpenAPI değişmedi, alembic head `0043_i08_registry_strategy_fks`,
  `SHARED_ALLOCATION_STATUS` = `future_dev`.
  **Blocker sayısı DEĞİŞMEDİ (1 — yalnız A-08), verdict BLOCKED.**
- **Kapananlar: `AT-01` (c2) · `AT-11` (c2 + c3) · `AT-22` (c3) · `AT-23` (c3)** — hepsi
  doc 02'nin BACKEND yüzeyi. Doc 02 bugüne kadar **hiç parti görmemişti.**
- **Tavanlar İNDİ: `partial` 79 → 75, `debt_class.B` 47 → 43**; açık borç **86 → 82**
  (A=1 · B=43 · C=6 · D=32). Clause `covered` 1039 → 1044, `uncovered` 91 → 87.
- **Doc 02'nin backend borcu bitti.** Kalan tek test-kapatılabilir satır **`AT-07`** ve o
  **frontend**; diğer beşi sınıf D.

## Bu slice'ın bıraktığı yeniden kullanım çapaları

- `backend/tests/integration/test_strategy_integration.py` — dosyanın sonundaki
  **"Acceptance batch 16"** bölümü. Dört desen taşır:
  - **`_stop_logic_block(block_id, *, enabled, package_root_id)`** — F-08 Logic-Based Stop
    Block üretici. Bir bölümün "kapalı olan düşer" iddiasını kanıtlaman gerekirse **açık ve
    kapalı kardeşi AYNI Save'de** gönder; toptan düşürmeyle geçilemeyen tek şekil budur.
  - **`SUPERVISOR` / `ADMIN` aktörleri + `_seed_extra_principals`** — yetki grant'i
    kanıtlayacak her test için hazır (revizyon `created_by_principal` FK'si gerçek Principal
    satırı ister; seed etmezsen test yetki değil **FK** hatasıyla düşer).
  - **Sahte-id iki dalı** (`test_unsaved_draft_cannot_be_pinned_into_a_mainboard_composition`)
    — "bu nesne kompozisyona giremez" iddiasının kanonik ölçümü: yokluk assertion'ı +
    var-olmayan id + **başka kökten ödünç alınmış gerçek, aynı-kind** id + Save sonrası
    pozitif kontrol.
  - **Clear/immutability geri okuması** (`test_clear_leaves_a_prior_immutable_revision_untouched`)
    — bir komşu işlemin bir immutable satıra dokunmadığını kanıtlamanın şekli: satırı **geri
    oku** (payload + hash + revision_number), head pointer'ı çöz, ve yokluğu **doğrudan
    sorgula** (`trash_entries`), projeksiyon bayrağından çıkarma.
- **Yerel Postgres (bu container'da ÇALIŞIYOR — önceki dalgaların "yok" kaydı bayat):**
  ```
  PGDATA=/var/lib/postgresql/entropia-data
  mkdir -p $PGDATA && chown postgres:postgres $PGDATA && chmod 700 $PGDATA
  su postgres -c "/usr/lib/postgresql/16/bin/initdb -D $PGDATA -U postgres --auth=trust -E UTF8 --locale=C"
  su postgres -c "/usr/lib/postgresql/16/bin/pg_ctl -D $PGDATA -l /tmp/pg.log -o '-p 5432' start"
  su postgres -c "/usr/lib/postgresql/16/bin/psql -p 5432 -U postgres -c \"CREATE ROLE entropia LOGIN SUPERUSER PASSWORD 'entropia';\""
  su postgres -c "/usr/lib/postgresql/16/bin/createdb -p 5432 -U postgres -O entropia entropia"
  ```
  Bundan sonra `tests/integration` **skip etmez, gerçekten koşar** — backend kabul borcu
  partileri artık "otorite CI" diye kapanmak zorunda değil.

## Pazarlıksız — bu slice'ın öğrendikleri

1. **AYNI MEKANİZMADAN BESLENEN İKİ ASSERTION'IN İLKİ İKİNCİSİNİ GÖLGELER.** `AT-11.c2`'nin
   payload yarısı ve bağımlılık-kenarı yarısı tek bir filtreden gelir; kapalı Logic bloğunu
   koruyan negatif kontrol **payload satırında** kırmızı verip orada durdu — kenar assertion'ı
   hiç koşmadı, yani "o da ölçülüyor" bir **varsayım** olurdu. Kontrol yeniden koşuldu, bu kez
   ürün kırılmasının yanında **testin payload satırı da geçici olarak düşürülerek**; red
   kenara indi. **Bir testin ikinci yarısını ölçmek istiyorsan birinciyi sustur.**
2. **YETKİ TESTİNİN KIRMIZISI YANLIŞ SEBEPTEN GELEBİLİR.** Grant yarısını sürerken aktörün
   `Principal` satırı yoksa test **FK** hatasıyla düşer ve "Admin edemedi" gibi okunur. Seed
   et; ve redi **sınıfla değil** ölçtüğün şeyle pinle.
3. **BİR REDDİ EXCEPTION SINIFIYLA PİNLEME.** Ödünç-revizyon dalında `ValidationError`
   yetmez — AOS-12'nin kind kontrolü de aynı sınıfı fırlatır ve testi yeşil tutardı. Zarfın
   **ekolanan alanını** assert et (`details[*].actual == <gönderilen id>`).
4. **"Kabul edilmesi gereken" yarıyı da sür.** `AT-11.c3`'te ilk Save'in geçersiz değeri
   **kabul etmesi** clause'un yarısıdır: kabul etmeseydi "re-enable revalidate eder" cümlesi
   ölçülemezdi. Negatif kontrol (`gt 0` gevşetme) bu yüzden **yalnız ikinci** Save'i düşürür.
5. **BOŞ BİR NUMARA GÜVENLİ NUMARA DEĞİLDİR — bu slice bunu ödeyerek öğrendi.** `ADIM 89`
   yazıldı; o an 89 gerçekten **boştu**. Sonra **#803** 89'u *atlayıp* **91**'i aldı ve önce
   indi, ardından **#799** **92**'yi aldı → 89 kullanılamaz oldu, slice **93**'e taşındı.
   Kapı (`generate_repository_facts.py::_check_live_kickoff_is_newest`) canlı kickoff'un
   ağaçtaki **en yüksek numaralı `ADIM<n>` DOSYASI** olmasını ister ve **dosya varlığına**
   bakar, `doc-status` işaretine değil. Doğru soru *"numara boş mu"* değil,
   ***"inen her şeyin üstünde mi"***. Parti etiketi de aynı anda çalındı (#803 *"batch 15"*'i
   merge edilmiş adla aldı → bu slice *"batch 16"*).
6. **TAVANI DEVRALMA, YENİDEN ÖLÇ — hata SESSİZDİR.** Bu dal **79/47** dondurmuştu ve o rakam
   kendi tabanına karşı **doğruydu**; ama #803 indikten sonra main **zaten** 79/47'deydi.
   Rebase sonrası taze `--report` **75/43** verdi, çünkü iki slice'ın kriterleri **ayrıktı** ve
   ikisi birden düşürüyordu. Eski freeze'le inseydi `--ratchet` **yeşil kalırdı** — ölçülen <
   tavan **asla** kırmızı vermez — ama tavan dört fazla taşırdı ve baseline'ın kendi README'si
   bunu tarif ediyor: *"a ceiling set above the measured figure would silently license the
   next unproven criterion."* **Kapanışta `grep '^## ADIM'`, `grep -o 'batch 1[0-9]'` VE
   rebase sonrası `--ratchet`'i koş; üçünü de commit'ten hemen önce doğrula.**

## Sıradaki tasarım işaretleri — ÖNCE ÖLÇ

- **Yoğunluk (bu freeze'den ölçüldü, sen yine ölç):** doc 02 bitti; kalan en kalabalık sınıf-B
  kümeleri **`RF` (doc 10)** · **`RD` (doc 12)** · **`AM` (doc 17)** · **`UM` (doc 21)** ·
  **`MB` (doc 01)** · **`CP` (doc 06)** · **`ESP` (doc 09)** · **`RC` (doc 14)**.
  **`AM`'ye dokunmadan önce PR #803'ün durumunu kontrol et** — o dal doc 17 backend'i
  sürüyordu. Tek otorite `docs/audit/acceptance_coverage_baseline.json` +
  `acceptance_semantic_scan.py --report`.
- **Doc 02'ye geri dönüş yalnız FRONTEND partisi olarak anlamlı:** `AT-07` (entry bloğu
  silinince `display_order` yeniden numaralanır, `block_id` UUID'si sabit kalır) —
  `frontend/src/test/strategyGraph.test.tsx` bugün hiç blok silmiyor.
- **Kabul borcu hattı, mühendislik hattından AYRI ilerliyor.** Mühendislik tarafında sıradaki
  kalem `C4` (bkz. `docs/ADIM86_LANDED_KICKOFF.md` ve açık PR'lar #799/#800/#801).
  İkisini aynı PR'da karıştırma.

## Çalışma yöntemi (bu dalgada işe yarayan)

- Sıra: **kriter id'sini grep'le → map'i oku → ürünü oku → test yaz → negatif kontrol +
  yamanın uygulandığını doğrula → `--ratchet` → `--write-ledger` + `--write-report` →
  `generate_repository_facts.py --root ..`**
- **Üretilmiş artefaktı unutma:** test **eklemek** `repository_facts.md`'nin *collected*
  sayısını oynatır ve `--check` bloklayıcıdır. Ayrıca `--write-report`'u da koş:
  `acceptance_semantic_traceability.md` **kapı kapsamında değil** ve sessizce bayatlıyor
  (bu slice onu doc 05 için bayat buldu — ADIM 88'in kapanışından kalma).
- Backend alt küme koşusu: `.venv/bin/python -m pytest <dosya> -q --no-cov -k <ifade>`
  (**`--no-cov` şart**, yoksa kapı sahte kırmızı verir).
- **Koşulamayanlar:** frontend (`node_modules` yok — `npm ci` gerekir) ve E2E/A11Y
  (`ghcr.io` blob host'u gateway'de 403). Oralara assertion yazma, **sınırı yaz**.

## Paste-ready resume prompt

```
ENTROPIA V18 — kabul borcu batch 16

ROL: Entropia V18 Principal Engineer.
[ENTROPIA ORTAK SÖZLEŞME bloğunu uygula]

ÖNCE DURUM ÖLÇ — hiçbir SHA'yı ve hiçbir sayıyı bu prompttan alma:
  git fetch && git log --oneline origin/main -6
  git show origin/main:docs/PROJECT_HISTORY.md | grep '^## ADIM' | tail -4
  git show origin/main:docs/PROJECT_HISTORY.md | grep -o 'batch 1[0-9]' | sort -u
  mcp__github__list_pull_requests(state=open)   # aynı defteri tazeleyen açık dal var mı
  CANLI kickoff = en yüksek numaralı docs/ADIM<n>_LANDED_KICKOFF.md — onu oku, bunu değil.

TAVANLAR: bu prompttan OKUMA. Tek otorite acceptance_coverage_baseline.json `ceilings`.
  Ratchet YALNIZ AŞAĞI iner; total_criteria bir TABANDIR.

ORTAM: bu container'da Postgres 16 ikilileri KURULU. Integration suite'ini "koşamıyorum"
  diye atlama — cluster'ı kaldır (komutlar: docs/ADIM93_LANDED_KICKOFF.md §çapalar) ve KOŞ.

GÖREV: sınıf-B kabul borcundan TEK belge + TEK yüzey seç ve kapat.
  1) cd backend && .venv/bin/python ../docs/audit/acceptance_semantic_scan.py --root .. --report
  2) ADAY SEÇTİKTEN SONRA, TEST YAZMADAN ÖNCE:
       grep -rn "<KRİTER-ID>" frontend/src backend/tests
     ADIM 88'de bir kriter, kendi id'sini describe bloğunda taşıyan bir testle BEŞ DALGA
     boyunca "borç" göründü. Kapsama zaten sevk edilmiş olabilir -> cite et, yazma.
  3) Kriterin adlandırdığı davranışın gerçekten sevk edildiğini üründe DOĞRULA. Üç şekli ayır:
       unshipped (kurulabilir, kod yok -> D) · unconstructible (erişilebilir ekran yok -> C)
       · unfalsifiable (doğru ama kırmak ÇOK NOKTALI bir değişiklik ister -> işaretle, kapatma)
     Ayırt edici ölçü: kırmak KAÇ NOKTALI? Tek noktalıysa kapatılabilir.

HER CLAUSE İÇİN ZORUNLU:
  a. Mevcut testler bu kusur altında yeşil mi kalıyor? Kalıyorsa yeni assertion BAŞKA bir
     eksene bakmalı — yoksa işaretleme yapıyorsun, kapsama değil.
  b. Negatif kontrol koş VE YAMANIN GERÇEKTEN UYGULANDIĞINI DOĞRULA (eşleşme sayısını assert
     et). Yeşil bir kontrol çoğu zaman hiç uygulanmamış bir kontroldür.
  c. Kırmızının HANGİ assertion'da olduğunu oku. Yanlış sebeple kırmızı hiçbir şey kanıtlamaz.
     Aynı mekanizmadan beslenen iki assertion varsa BİRİNCİSİNİ SUSTURUP ikincisini ayrıca ölç.
  d. Koşamadığın suite'e (E2E/A11Y — ghcr.io gateway'de 403) assertion YAZMA; sınırı yaz.
  e. Kriterin SON clause'u kapanıyorsa debt_class'ı KALDIR.

KAPATMAYA ÇALIŞMA (bulgular): TL-01.c4, TL-02.c2, TL-11.c3, TL-14.c4, TL-16.c4, RD-01.c4,
  RD-05.c5, RD-12.c4, RD-13.c4, PC-20.c3, PC-02.c2, TS-07.c2 + `unfalsifiable: true` clause'lar.
  Yeniden sınıflandırma tavan yükseltir = adjudication, test slice'ının kararı değil.

DOC 05, DOC 18 ve DOC 02'nin BACKEND'i BİTTİ — oralarda bir test slice'ının kapatabileceği
  satır kalmadı (doc 02'de yalnız AT-07 kaldı ve o FRONTEND). Başka belge/yüzey seç.

KAPANIŞ: CLAUDE.md §Session CLOSING'in 6 maddesi. ADIM numarasını VE parti etiketini
  commit'ten hemen önce yeniden doğrula (bu hafta ÜÇ kez ikisi birden çalındı: #781, #785,
  ve #803 ile açık çakışma). Merge edilmiş ad kazanır. PR'ı main'e aç, DUR, MERGE ETME.
```
