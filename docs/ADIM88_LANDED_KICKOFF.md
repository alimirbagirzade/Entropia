<!-- doc-status: current -->
> **CANLI KICKOFF.** Bu belge en yeni slice'ın handoff'udur. Bir sonraki slice inince
> `historical`a demote edilir ve yerine yenisi geçer (`check_classification` CI'da doğrular:
> daha yüksek numaralı bir `docs/ADIM<n>…KICKOFF.md` varken canlı işaret eski belgede duramaz).

# ADIM 88 LANDED — kabul borcu batch 14 (doc 05 frontend): TL-18 sıfır testle kapandı · sıradaki slice için kickoff

> Tam kayıt: `docs/PROJECT_HISTORY.md` §ADIM 88. Bu belge **devam noktasıdır**, kayıt değil.

## Neredeyiz

- Kapanış yazılırken main **`cfce51e`** (dal `ccdd4fd`'de yazıldı; #795 ve #785 inince rebase edildi). **Ürün kodu ve test kodu değişmedi** — diff yalnız
  defter + üretilmiş artefakt. Migration yok, OpenAPI değişmedi, alembic head
  `0043_i08_registry_strategy_fks`, `SHARED_ALLOCATION_STATUS` = `future_dev`.
  **Blocker sayısı DEĞİŞMEDİ (1 — yalnız A-08), verdict BLOCKED.**
- **`uncovered` KRİTER tavanı ilk kez indi: 8 → 7.** Altı dalgadır (73/75/78/79/80/84) yalnız
  `partial`/`B` iniyordu. `debt_class.B` 52 → 51, açık borç **91 → 90**.
- **Doc 05'te bir test slice'ının kapatabileceği satır KALMADI.**

## Bu slice'ın bıraktığı yeniden kullanım çapaları

- `frontend/src/test/presentationState.test.tsx` — **üç kriteri birden** taşıyan düğüm çifti
  (`TS-16` / `TL-18` / `AOS-16`). Bir sayfa için *"bu etkileşim hiçbir şey yazmaz"* iddiasını
  kanıtlaman gerekirse **bunu kopyala**: `writeRequests(fetchMock)` yardımcısı non-GET
  çağrıları süzer, ve test ayrıca **kapsanmış** bir filtre (`/mainboard` + non-GET) ile
  "yanlış yüzeye yazmadı"yı ayrıca pinler.
- **Vacuity muhafızı deseni:** aynı testte, boş yazma listesinin *"hiç tetiklenmeyen bir
  etkileşim"*ten gelmediğini kanıtlamak için etkileşimin görünür sonucu ayrıca assert edilir
  (editor bölümünün açılması). Negatif iddia yazan her test bunu taşımalı.

## Pazarlıksız — bu slice'ın öğrendikleri

1. **PARTİ SEÇMEDEN ÖNCE KRİTER ID'SİNİ TEST AĞACINDA GREP'LE.** `TL-18` beş dalga boyunca
   *"Nothing in the suite asserts this"* notuyla borç göründü; oysa onu adlandıran bir describe
   bloğu ADIM 60'tan beri ağaçtaydı ve **kardeş iki kriter aynı düğümleri cite ediyordu**.
   `grep -rn "TL-18" frontend/src backend/tests` yazmaktan ucuzdur.
2. **YEŞİL BİR NEGATİF KONTROL ÇOĞU ZAMAN HİÇ UYGULANMAMIŞ BİR KONTROLDÜR.** Bu slice'ta ilk
   yama tek eşleşme varsaydı, handler dizesi **üçtü**, dosya değişmedi ve koşu yeşil kaldı.
   Yakalayan şey `assert count == 3`'tü. **Yamanın ürünü gerçekten değiştirdiğini ayrıca
   doğrula** (ADIM 71'in dersinin ikizi).
3. **"Yapı gereği doğru" her clause yanlışlanamaz DEĞİLDİR.** Ayırt edici ölçü **kırmak kaç
   noktalı bir değişiklik ister**: `TL-18` tek noktalı (bir `onClick`'e mutation) → kapatılır;
   `TL-02.c2` üç noktalı (session + repo write + snapshot wiring) → işaretlenir, kapatılmaz.
4. **Ratchet yalnız aşağı iner** ve tavan **aritmetikle türetilmez** — arada başka slice'lar
   inse bile `--report` kendi tabanında yeniden koşulur.
5. **NUMARA VE PARTİ ETİKETİ AYNI ANDA ÇALINIR, ve bu YAPISAL.** Bu slice `87 / batch 13`
   yazıldı, #785 ikisini birden aldı → `88 / batch 14`. ADIM 84'te #781 ile **birebir aynısı**
   olmuştu. Kabul borcu hattında paralel oturumlar aynı sırayı tüketiyor: kapanışta
   `grep '^## ADIM'` **yetmez**, `grep -o 'batch 1[0-9]'` de koş — ve ikisini de **commit'ten
   hemen önce** yeniden doğrula.

## Sıradaki tasarım işaretleri — ÖNCE ÖLÇ

- **Yoğunluk (bu freeze'den ölçüldü, ama sen yine ölç):** `AT` · `AL` · `RF` · `RD` · `AM`
  başlıkları en kalabalık sınıf-B kümeleri. Tek otorite
  `docs/audit/acceptance_coverage_baseline.json` + `acceptance_semantic_scan.py --report`.
- **Kabul borcu hattı, mühendislik hattından AYRI ilerliyor.** Mühendislik tarafında sıradaki
  kalem `C4` (`_EngineParticipant`'ın üretim çağıranı) — bkz. `docs/ADIM86_LANDED_KICKOFF.md`.
  İkisini aynı PR'da karıştırma.
- **Doc 05'e geri dönme.** Kalan beş satırın hiçbiri test kalemi değil: `TL-01.c4` yol sapması,
  `TL-02.c2` yanlışlanamaz, `TL-11.c3` sınıf C, `TL-14.c4`, `TL-16.c4` sınıf D (ADIM 84).

## Çalışma yöntemi (bu dalgada işe yarayan)

- Sıra: **kriter id'sini grep'le → map'i oku → ürünü oku → (gerekiyorsa) test yaz → negatif
  kontrol + yamanın uygulandığını doğrula → `--ratchet` → `--write-ledger` →
  `generate_repository_facts.py --root ..`**
- Frontend tek dosya koşusu: `npx vitest run src/test/<dosya> --no-file-parallelism`.
- **Ortam (bu makinede kurulu):** `dockerd` ayakta ve `/etc/docker/daemon.json`'da
  `registry-mirrors: ["https://mirror.gcr.io"]` → **Docker Hub 403 sınırı kalktı**. Ama
  `ghcr.io` blob host'u hâlâ gateway'de 403 (`Dockerfile` `ghcr.io/astral-sh/uv` çeker), o
  yüzden **yerel compose stack ve E2E/A11Y hâlâ koşturulamaz** — denemeye zaman harcama.
- **CI tuzağı:** `npx playwright install --with-deps chromium` beş E2E job'ında da
  cache'siz/timeout'suz/retry'siz koşuyor ve E2E real-browser'ın bütçesi 30 dk. Bu dalgada
  **üç job'ı** öldürdü (`cancelled`, `failure` DEĞİL — hiçbir test gövdesi koşmadı). Çare
  rerun; **test düzeltme, baseline indirme, workflow kurcalama YOK.** Kalıcı düzeltme
  (cache + adım-düzeyi timeout + retry) **ayrı bir PR'ın işi**, kabul borcu slice'ının değil.

## Paste-ready resume prompt

```
ENTROPIA V18 — kabul borcu batch 15

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
  d. Koşamadığın suite'e (E2E/A11Y — ghcr.io gateway'de 403) assertion YAZMA; sınırı yaz.
  e. Kriterin SON clause'u kapanıyorsa debt_class'ı KALDIR.

KAPATMAYA ÇALIŞMA (bulgular): TL-01.c4, TL-02.c2, TL-11.c3, TL-14.c4, TL-16.c4, RD-01.c4,
  RD-05.c5, RD-12.c4, RD-13.c4, PC-20.c3, PC-02.c2, TS-07.c2 + `unfalsifiable: true` clause'lar.
  Yeniden sınıflandırma tavan yükseltir = adjudication, test slice'ının kararı değil.

KAPANIŞ: CLAUDE.md §Session CLOSING'in 6 maddesi. ADIM numarasını VE parti etiketini
  commit'ten hemen önce yeniden doğrula (#781 bir kez ikisini birden aldı). Merge edilmiş ad
  kazanır. PR'ı main'e aç, DUR, MERGE ETME.
```
