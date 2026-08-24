<!-- doc-status: current -->
> **CANLI KICKOFF.** Bu belge en yeni slice'ın handoff'udur. Bir sonraki slice inince
> `historical`a demote edilir ve yerine yenisi geçer (`check_classification` CI'da doğrular:
> daha yüksek numaralı bir `docs/ADIM<n>…KICKOFF.md` varken canlı işaret eski belgede duramaz).

# ADIM 98 LANDED — kabul borcu batch 19 (doc 14 Backtest Ready Check, backend): iki kriter kapandı · sıradaki slice için kickoff

> Tam kayıt: `docs/PROJECT_HISTORY.md` §ADIM 98. Bu belge **devam noktasıdır**, kayıt değil.

## Neredeyiz

- Taban main **`b7e66ad`** (dal İKİ KEZ rebase edildi: `ca5e5dd` → `2a790ff` (#809 = ADIM 95) → `b7e66ad` (#806 = ADIM 97)). **Ürün kodu değişmedi** (`backend/src` altında sıfır satır);
  diff = üç yeni integration case + kabul defteri + üretilmiş artefakt. Migration yok,
  OpenAPI değişmedi, alembic head `0043_i08_registry_strategy_fks`,
  `SHARED_ALLOCATION_STATUS` = `future_dev`.
  **Blocker sayısı DEĞİŞMEDİ (1 — yalnız A-08), verdict BLOCKED.**
- **Kapananlar: `RC-10` (c2) · `RC-17` (c2)** — doc 14'ün BACKEND yüzeyi. İkisi de kendi
  kriterinin son açık clause'uydu → ikisinin de `debt_class`'ı **kaldırıldı**.
- **Tavanlar İNDİ: `partial` 71 → 69, `debt_class.B` 39 → 37**; açık borç **78 → 76**
  (A=1 · B=37 · C=6 · D=32). Clause `covered` 1048 → 1050, `uncovered` 83 → 82.
- **Doc 14 = 17 covered / 1 partial.** Kalan tek satır `RC-09.c3` ve o **frontend**
  (stale/`is_current=false` bir readiness projeksiyonu verilen sayfada RUN düğmesinin
  disabled olduğunu assert eden bir vitest case'i — ledger notu tam olarak bunu tarif eder).

## Bu slice'ın bıraktığı yeniden kullanım çapaları

- `backend/tests/integration/test_readiness_persistence.py` — dosyanın sonundaki
  **"Acceptance batch 19"** bölümü + yardımcı `_pinned_item(session, composition_id)`.
  İki desen taşır:
  - **Pin ≠ head** — bir "pinlenen şey oynamadı" iddiasını kanıtlamanın şekli: kök head'ini
    **oynat**, oynadığını assert et, pinin oynamadığını **ayrıca** assert et, sonra
    projeksiyonu geri oku. `create_work_object_revision`'ın **content-hash idempotency dalı**
    payload aynı kalırsa mevcut head'i döndürür ve **hiçbir şey yayımlanmaz** → payload'ı
    gerçekten değiştir, yoksa test totolojik olur.
  - **İkinci katalog ekseni** — market successor'ı: `md_rev_2` + `EntityRegistry.current_revision_id`
    kaydırması. Pini **fixture literalinden değil saklanan payload'dan** geri oku.
- `backend/tests/integration/test_readiness_denial_envelope.py` (**YENİ**) — bir reddin
  **gövdesi** hakkında iddia kurmanın şekli:
  - rotayı **ASGI app + gerçek session** ile sür (`_override` deseni,
    `test_library_validation_run_route.py`'den);
  - sızıntı iddiasını **serileştirilmiş metne karşı substring taramasıyla** kur, key
    lookup'la değil — `message` içindeki düz metne konan bir sızıntıyı hiçbir key lookup
    bulamaz (ölçüldü, NC-3c);
  - ve **pozitif kontrolü aynı rotadan al**: sahibi çağırdığında aynı kimliklerin gövdede
    **gerçekten** göründüğünü assert et, yoksa "yok" iddiası bu ucun hiç üretemeyeceği bir
    değer için de doğrudur.
- **Negatif kontrol harness'i** — `finally` ile geri yazan, yamanın uygulandığını (eşleşme
  sayısıyla) assert eden küçük bir `run(name, edits, pytest_args)` sarmalayıcısı. Bu slice
  onu scratchpad'de tuttu; deseni `PROJECT_HISTORY.md` §ADIM 94'te yazılı.
- **Yerel Postgres — bu container ÇIPLAK başladı** (`.venv` yok, cluster yok). Tam dizi:
  ```
  cd backend && uv sync --all-extras
  PGDATA=/var/lib/postgresql/entropia-data
  mkdir -p $PGDATA && chown postgres:postgres $PGDATA && chmod 700 $PGDATA
  su postgres -c "/usr/lib/postgresql/16/bin/initdb -D $PGDATA -U postgres --auth=trust -E UTF8 --locale=C"
  su postgres -c "/usr/lib/postgresql/16/bin/pg_ctl -D $PGDATA -l /tmp/pg.log -o '-p 5432' start"
  su postgres -c "/usr/lib/postgresql/16/bin/psql -p 5432 -U postgres -c \"CREATE ROLE entropia LOGIN SUPERUSER PASSWORD 'entropia';\""
  su postgres -c "/usr/lib/postgresql/16/bin/createdb -p 5432 -U postgres -O entropia entropia"
  cd backend && LC_ALL=C.UTF-8 LANG=C.UTF-8 PYTHONUTF8=1 uv run alembic upgrade head
  ```
  **`LC_ALL=en_US.UTF-8` bu imajda alembic'i `UnicodeDecodeError` ile patlatır** —
  CLAUDE.md §Local verify'ın çapası burada geçerli değil.

## Pazarlıksız — bu slice'ın öğrendikleri

1. **BİR NEGATİF KONTROL YANLIŞ YERDE KIRMIZI VEREBİLİR, VE O KIRMIZI HİÇBİR ŞEY KANITLAMAZ.**
   Market ekseninin ilk kontrolü (dataset head'ini fingerprint'in **kendisine** katmak) raporu
   **doğduğu anda** stale ediyordu: yeni case kendi **ön koşulunda** (`before["is_current"]`)
   kırmızı verdi ve yanında **ilgisiz, önceden var olan** bir testi de düşürdü. Kırmızı vardı,
   ama *"successor raporu stale ediyor mu"* sorusunu değil *"fingerprint hesabı bozuldu mu"*
   sorusunu ölçüyordu → **kontrol reddedildi**, yerine ön koşulu bozmayan biri kuruldu.
   **Kural: bir kontrol yalnız hedef testi ve yalnız hedef assertion'ı düşürmelidir.**
2. **AYNI CLAUSE'UN İKİ ASSERTION'I FARKLI KONTROLLERLE ÖLÇÜLÜR.** `fingerprint` ve
   `is_current` aynı fikirde görünür ama değildir: bir kusur fingerprint'i oynatmadan
   `is_current`'ı düşürebilir (NC-2b) ve tersi (NC-2c). İkisi de **taşıyıcıdır**; biri
   silinseydi bir kusur sınıfı görünmez olurdu.
3. **KEY LOOKUP BİR SIZINTI TESTİ DEĞİLDİR.** `details == []` ve `scope_id is None`
   assertion'ları gerçek ama **yetersiz**: sızıntıyı `message` içindeki serbest metne koyan
   kontrol ikisini de yeşil bırakır. Bir "gövde X'i taşımıyor" iddiası **serileştirilmiş
   metne** karşı kurulur.
4. **"MEVCUT SUITE BU KUSUR ALTINDA YEŞİL Mİ KALIYOR" SORUSUNU KONTROLÜN ÇIKTISINDAN OKU.**
   Bu partide yedi kontrolün hepsinde önceden var olan testler yeşil kaldı — RC-17'de sebebi
   ölçülmüş bir gerçek: **bir istisnanın TİPİNİ assert etmek zarfın ne taşıdığını göremez.**
5. **YAML NOTUNUN BİÇİMİNE YAZMADAN ÖNCE BAK.** RC-10'un `notes`'u düz skalerdi; eklenen
   metindeki tek bir `: ` (*"the other way: an APPROVED md_rev_2"*) `ScannerError` verdi. Not
   tek tırnaklı skalere çevrildi (apostroflar **ikilenerek**). RC-17'ninki zaten tek
   tırnaklıydı → aynı metin orada sorunsuz geçti.
6. **AÇIK PR'LARIN TALEP ETTİĞİ NUMARAYI DOSYA YOLUNDAN ÖLÇ.** Bu dalgada **#806 ve #809'un
   İKİSİ de** `docs/ADIM95_LANDED_KICKOFF.md` ekliyordu — yani 95 iki kez talep edilmişti ve
   ikisinden biri taşınmak zorundaydı. Başlıklar (`stage-95`) bunu söylüyordu, ama **kapının
   baktığı şey dosya yoludur**. Bu PR açıkken **#809 gerçekten ADIM 95 olarak indi** → 96
   seçimi doğrulandı. **Etiket tarafında da aynı kural:** `batch 18` #806'nın **açık** talebi
   olduğu için atlandı; inmezse kalıcı boşluk kalır (ADIM 89 emsali) — açık bir talebin
   üstüne yazmak sayıyı değil **atfı** kaybettirir.
7. **`mergeable_state: dirty` BİR İŞ EMRİDİR, BİR DURUM DEĞİL.** #809 inince bu PR yedi belge
   çakışmasıyla dirty oldu. Sunucu tarafı *"Update branch"* düğmesine **dayanılmadı** (ADIM 93
   baseline JSON'unu okunamaz hale getirdi, ADIM 94 bir `PROJECT_HISTORY` kaydını sessizce
   düşürdü); dal `origin/main` üzerine **rebase** edildi. **Çakışmanın doğru çözümü "benimkini
   al" DEĞİL:** `PROJECT_HISTORY` ve `STAGE2_HANDOFF`'ta **iki tarafın da bloğu korundu**
   (ADIM 95'inki + benimki), üretilmiş dosyalarda main alınıp **yeniden üretildi**, ve
   kickoff demote zinciri **bir kademe kaydırıldı** (94 zaten historical'dı, 95 demote edildi,
   96 current). Ölçüm: `grep -c '^## ADIM'` **89 → 90**, silinen kayıt yok.

## Sıradaki tasarım işaretleri — ÖNCE ÖLÇ

- **Kalan sınıf-B yoğunluğu (bu freeze'den; sen yine ölç):** doc 21 (`UM-08` `UM-13` `UM-15`) ·
  doc 09 (`ESP-03` `ESP-05` `ESP-20`) · doc 06 (`CP-03` `CP-09` `CP-13`) · doc 16
  (`RH-13` `RH-14`) · doc 20 (`TR-07` `TR-08`) · doc 19 (`FD-04` `FD-05`).
  Tek otorite `docs/audit/acceptance_coverage_baseline.json` + `acceptance_semantic_scan.py --report`.
- **`ESP-20` tek kriterde İKİ açık clause taşıyor** (görünürlük/yetki ekseni, tek backend testi
  ikisini birden kapatabilir) — ama önce **sevk edildiğini** doğrula.
- **`UM-13.c3` eşzamanlılık ister** ve tek session'lı bir integration testiyle
  **kurulamayabilir**; ikinci bir bağlantı gerekir.
- **`RC-09.c3` doc 14'ü bitirecek tek satır ve FRONTEND** — bu container'da `node_modules` yok,
  bir frontend partisi için önce `cd frontend && npm ci`.
- **Kabul borcu hattı mühendislik hattından AYRI.** Aynı PR'da karıştırma.

## Çalışma yöntemi (bu dalgada işe yarayan)

- Sıra: **açık PR'ları tara (başlık + eklenen `docs/ADIM<n>` yolu) → kriter id'sini
  `grep -rn` ile test ağacında ara → ledger notunu oku → ürünü PROBE ile ölç (geçici bir
  test dosyası + `assert False`, sonra sil) → test yaz → negatif kontrol → `--ratchet` →
  baseline'ı yeniden dondur → `--write-ledger` + `--write-report` →
  `generate_repository_facts.py --root ..` → **`--check-generated`** (ADIM 95'in yeni kapısı:
  iki üretilmiş artefakt map'ten yeniden türetilip bayt bayt karşılaştırılır; tazelemeyi
  unutursan CI kırmızı verir).**
- **`--write-ledger`/`--write-report` yolları REPO KÖKÜNE görelidir**, `backend/`'e değil
  (`../docs/...` verirsen `FileNotFoundError`).
- **Kriter-düzeyi `status`'ü ve `debt_class`'ı da güncelle**, yalnız clause'u değil.
- Backend alt küme: `LC_ALL=C.UTF-8 uv run python -m pytest <dosya> -q --no-cov`
  (**`--no-cov` şart**). Çıktıyı dosyaya yaz, exit code'u **ayrı** oku; `s` (skip) ara.
- **Koşulamayanlar:** frontend (`node_modules` yok) ve E2E/A11Y. Oralara assertion yazma,
  **sınırı yaz**.

## Paste-ready resume prompt

```
ENTROPIA V18 — kabul borcu (sıradaki parti)

ROL: Entropia V18 Principal Engineer.
[ENTROPIA ORTAK SÖZLEŞME bloğunu uygula]

ÖNCE DURUM ÖLÇ — hiçbir SHA'yı, numarayı ve hiçbir sayıyı bu prompttan alma:
  git fetch && git log --oneline origin/main -6
  git show origin/main:docs/PROJECT_HISTORY.md | grep '^## ADIM' | tail -4
  git show origin/main:docs/PROJECT_HISTORY.md | grep -o 'batch 1[0-9]' | sort -u
  mcp__github__list_pull_requests(state=open)
  # AÇIK PR'LARIN BAŞLIĞINI OKU: aynı belgeyi/yüzeyi süren dal varsa BAŞKA belge seç.
  # NUMARAYI başlıktan değil, o PR'ların EKLEDİĞİ docs/ADIM<n>_*.md YOLLARINDAN ölç —
  # bu dalgada İKİ ayrı PR aynı numarayı (ADIM 95) talep ediyordu.
  CANLI kickoff = en yüksek numaralı docs/ADIM<n>_LANDED_KICKOFF.md — onu oku, bunu değil.

TAVANLAR: bu prompttan OKUMA. Tek otorite acceptance_coverage_baseline.json `ceilings`.
  Ratchet YALNIZ AŞAĞI iner; total_criteria bir TABANDIR.

ORTAM: bu container ÇIPLAK başlayabilir — backend/.venv YOK ve Postgres cluster YOK.
  Kurulum dizisi: docs/ADIM98_LANDED_KICKOFF.md §çapalar. `alembic upgrade head` için
  LC_ALL=C.UTF-8 PYTHONUTF8=1 kullan (en_US.UTF-8 bu imajda UnicodeDecodeError verir).
  `ss` (skipped) + exit 0 bir yeşil DEĞİLDİR.

GÖREV: sınıf-B kabul borcundan TEK belge + TEK yüzey seç ve kapat.
  1) cd backend && python3 ../docs/audit/acceptance_semantic_scan.py --root .. --report
  2) ADAY SEÇTİKTEN SONRA, TEST YAZMADAN ÖNCE:
       grep -rn "<KRİTER-ID>" frontend/src backend/tests
     Kapsama zaten sevk edilmiş olabilir -> cite et, yazma (ADIM 88).
  3) Kriterin adlandırdığı davranışın gerçekten sevk edildiğini üründe DOĞRULA — geçici bir
     probe test dosyası + `assert False` en ucuz yol. Üç şekli ayır:
       unshipped (kurulabilir, kod yok -> D) · unconstructible (erişilebilir ekran yok -> C)
       · unfalsifiable (kırmak ÇOK NOKTALI bir değişiklik ister -> işaretle, kapatma)

HER CLAUSE İÇİN ZORUNLU:
  a. Mevcut testler bu kusur altında yeşil mi kalıyor? Kalıyorsa yeni assertion BAŞKA bir
     eksene bakmalı — yoksa işaretleme yapıyorsun, kapsama değil.
  b. Negatif kontrol koş VE YAMANIN UYGULANDIĞINI DOĞRULA (eşleşme sayısını assert et).
     Geri yazmayı `finally`'ye koy (ADIM 94).
  c. KIRMIZININ HANGİ ASSERTION'DA OLDUĞUNU OKU — ve o assertion HEDEF assertion mı?
     ADIM 98: bir kontrol testi kendi ÖN KOŞULUNDA düşürdü ve yanında ilgisiz bir testi de
     kırdı; kırmızı vardı ama clause'a atfedilemiyordu -> KONTROLÜ REDDET, yenisini kur.
     İlk kırmızı sonrakini GÖLGELER: gölgeyi kaldıran ayrı bir kontrol kur.
  d. YEŞİL bir kontrol iki şey demek olabilir: yama uygulanmadı, ya da ASSERTION TOTOLOJİK.
     Bir yan etkinin YOKLUĞUNU iddia ediyorsan, önünde onu geri alan hiçbir şey olmamalı.
  e. Bir GÖVDE iddiasını key lookup'la kurma — serileştirilmiş metne karşı substring tara
     (ADIM 98: sızıntı `message` içindeki düz metne konunca üç key assertion'ı da yeşil kaldı).
  f. Koşamadığın suite'e (E2E/A11Y/frontend) assertion YAZMA; sınırı yaz.
  g. Kriterin SON clause'u kapanıyorsa KRİTER-DÜZEYİ `status`'ü de covered yap ve `debt_class`'ı
     KALDIR (yalnız clause'u güncellemek tavanı eksik indirir).
  h. YAML notunun biçimine bak: düz skalere `: ` ekleyemezsin -> tek tırnağa al, apostrofları ikile.

KAPATMAYA ÇALIŞMA (bulgular): TL-01.c4, TL-02.c2, TL-11.c3, TL-14.c4, TL-16.c4, RD-01.c4,
  RD-05.c5, RD-12.c4, RD-13.c4, PC-20.c3, PC-02.c2, TS-07.c2, MB-22.c4
  + `unfalsifiable: true` clause'lar. Yeniden sınıflandırma tavan yükseltir = adjudication.

BİTMİŞ OLANLAR: doc 05, doc 18, doc 02-BACKEND, doc 17-BACKEND, doc 01-BACKEND, doc 14-BACKEND.
  Doc 10 backend #806'daydı — durumunu kontrol et. Kalan sınıf-B yoğunluğu (yine de ölç):
  doc 21 (UM) · doc 09 (ESP) · doc 06 (CP) · doc 16 (RH) · doc 20 (TR) · doc 19 (FD).

KAPANIŞ: CLAUDE.md §Session CLOSING'in 6 maddesi. ADIM numarasını VE parti etiketini
  commit'ten hemen önce yeniden doğrula. Merge edilmiş ad kazanır.
  PR AÇIKKEN main ilerlerse: sunucu tarafı "Update branch" DÜĞMESİNE DAYANMA. İki ölçülmüş zarar:
    (1) ADIM 93 — merge, baseline JSON'u okunamaz bir nesneye çevirdi;
    (2) ADIM 94 — merge, PROJECT_HISTORY'den `## ADIM 94` kaydını SESSİZCE DÜŞÜRDÜ.
  Dalı güncel main üzerine yeniden kur (rebase), yamaları yeniden uygula, artefaktları yeniden
  üret, --ratchet'i merged ağaçta yeniden koş. ADIM 98 bunu gerçekten yaşadı: çakışmanın doğru
  çözümü "benimkini al" DEĞİL — PROJECT_HISTORY ve STAGE2_HANDOFF'ta İKİ TARAFIN DA bloğu
  korunur, üretilmiş dosyalarda main alınıp yeniden üretilir, kickoff demote zinciri bir
  kademe kaydırılır. Ölçüm: `grep -c '^## ADIM'` düşmemeli.
  YENİ KAPI (ADIM 95): `--check-generated` iki üretilmiş kabul artefaktını map'ten yeniden
  türetip karşılaştırır — `--write-ledger`/`--write-report` koşmayı unutursan CI kırmızı.
  SUNUCU MERGE'ÜNDEN SONRA KAYDIN DURDUĞUNU ŞÖYLE ÖLÇ (ÜÇ NOKTALI DIFF KULLANMA):
    git show <merge-sha>:docs/PROJECT_HISTORY.md | grep -c '^## ADIM <n>'
    git show <parent-sha>:docs/PROJECT_HISTORY.md | grep -c '^## ADIM <n>'
  1 -> 0 düşmüşse kaydı geri koy. Merge'den SONRA da main'de aynı grep'i koş.

  PR'ı main'e aç, DUR, MERGE ETME.
```
