<!-- doc-status: historical -->
> **TARİHSEL KICKOFF — ARTIK CANLI DEĞİL** (ADIM 111 ile demote edildi). Yazıldığı anda bu belge en yeni slice'ın handoff'udur. Bir sonraki slice inince
> `historical`a demote edilir ve yerine yenisi geçer (`check_classification` CI'da doğrular:
> daha yüksek numaralı bir `docs/ADIM<n>…KICKOFF.md` varken canlı işaret eski belgede duramaz).

# ADIM 110 LANDED — kabul borcu batch 29 (doc 02 + doc 14, FRONTEND): `AT-07` + `RC-09` kapandı · sıradaki slice için kickoff

> Tam kayıt: `docs/PROJECT_HISTORY.md` §ADIM 110. Bu belge **devam noktasıdır**, kayıt değil.

## Neredeyiz

Taban `74db6ff` (ADIM 109 / #824). **ÜRÜN KODU DEĞİŞMEDİ** — `backend/src` ve `frontend/src`'in
test dışı hiçbir dosyasında tek satır yok; diff üç yeni vitest case'i + defter + üretilmiş
artefakt. Migration yok, alembic head `0043_i08_registry_strategy_fks`, `ENGINE_VERSION` ve
OpenAPI değişmedi, `SHARED_ALLOCATION_STATUS` = `future_dev`.
**Blocker sayısı DEĞİŞMEDİ (1 — yalnız A-08), BLOCKED.**

**İki kriter kapandı ve İKİ TAVAN birden indi:**

| | önce | sonra |
|---|---:|---:|
| `partial` kriter | 55 | **54** |
| `uncovered` kriter | 7 | **6** |
| `debt_class.B` | 23 | **21** |

`uncovered` **KRİTER** tavanı bu depoda ancak **ikinci kez** oynadı (ilki ADIM 88, 8 → 7) —
çünkü `AT-07` sınıf-B'nin **tek `uncovered` satırıydı**. Açık borç **60** (A=1 · B=21 · C=6 · D=32).

## Bu slice'ın bıraktığı yeniden kullanım çapaları (tam sembol adlarıyla)

- **`frontend/src/test/strategyGraph.test.tsx::twoEntryBlocksPayload`** — iki entry blokluk
  fixture; iki blok **okunan her eksende** ayrışır (`block_id`, `package_ref.package_root_id`,
  `timeframe`). Yeni bir blok-listesi davranışı sürecek her test bunu ödünç alabilir.
- **`renderComponent(PositionEntryCard, payload)`** (mevcut, değişmedi) → `onApply` mock'u döner;
  *"Apply Position Entry changes"* tıklandığında serileştirilmiş payload oradan okunur. Bu,
  `strategyGraph.ts::mergeBlock` / `mergeCondition` çıktısını sürmenin tek yoludur.
- **`frontend/src/test/backtestRun.test.tsx::MAINBOARD`** (mevcut) + `ready_summary.state`
  override deseni — `renderPage()` ile birlikte, RUN affordance'ının **herhangi bir** readiness
  durumundaki davranışını sürmenin hazır harness'ı.
- Ölçülmüş üretim çapaları: `frontend/src/lib/mainboard.ts::isReadyForRun` (RUN kapısının TEK
  predicate'i) · `::READY_STATUS_TEXT` (durum başına metin; `stale`'in kendi cümlesi var) ·
  `frontend/src/components/StrategyGraphForm.tsx::BlockList` (`remove`/`move`/`add`) ·
  `frontend/src/lib/strategyGraph.ts::mergeBlock` (`block_id` verbatim, `display_order` türetilmiş).

## Pazarlıksız — bu slice'ın öğrendikleri

1. **BİR KUSURUN ALTINDA MEVCUT SUITE'İN YEŞİL KALMASI, BOŞLUĞUN KANITIDIR.** `RC-09.c3`'ün tek
   içeriği *"NOT_READY'den AYRI"*dır. `isReadyForRun`'a `state === "stale"` eklendiğinde önceden
   var olan `not_ready` RUN-kilidi testi **YEŞİL kalıyor** ve yalnız yeni case kırmızıya dönüyor —
   yani bir `not_ready` case'i o clause'u **hiçbir zaman** kapatamazdı. Bu iddia edilmedi, NC-1'de
   **ölçüldü**.
2. **AYNI KRİTERİN İKİ CLAUSE'U İKİ AYRI KUSUR SINIFI OLABİLİR VE BİRBİRİNİ GÖRMEZ.** `AT-07.c1`
   bir **RENDER** özelliğidir (başlık + move/remove kontrollerinin erişilebilir adları),
   `AT-07.c2` bir **SERİLEŞTİRME** özelliğidir (Apply'ın geri gönderdiği). Doğru numaralayıp taze
   UUID basan bir bileşen c1'i geçer c2'yi düşürür; id'yi koruyup bayat numara gösteren bunun
   tersini yapar. **Tek case'e sıkıştırma.**
3. **GÖLGEYİ KAYDETMEKLE YETİNME, KALDIRMAYI DENE** (ADIM 101 kuralı, bu kez proaktif). c2'nin
   `package_root_id` assertion'ı `block_id` assertion'ının altında duruyor ve her *sıradan* kusurda
   onun gölgesinde kalıyordu. NC-4 bilerek **kimliği doğru bırakan** bir kusur kurar (silinen bloğun
   `package_ref`/`timeframe`'i survivor'a sızar) → kırmızı **yalnız paket ekseninde**. Gölge
   kaydedilmedi, **kaldırıldı**.
4. **`getByRole("heading")` bir `<strong>`'u BULMAZ.** `IndicatorBlockEditor`'ın blok başlığı
   `<strong>Indicator Block {index + 1}</strong>`'dir, heading değil. İlk yazımda test bu yüzden
   kırmızı verdi — **kaynak değil ölçüm aracı** düzeltildi (`getByText`).
5. **Sınıf-B sanılan bir satır sevk EDİLMEMİŞ olabilir — parti seçmeden ÖNCE ÖLÇ** (ADIM 54).
   Bu partide iki aday böyle elendi: `UM-15.c3` (bulgu, aşağıda) ve `CP-03.c4` (şüpheli, aşağıda).
6. **Üretilmiş olguları tazele** (ADIM 60): üç `it(...)` eklemek
   `docs/generated/repository_facts.{md,json}` + `README.md`'nin gömülü bloğunu bayatlatır
   (frontend call sites **726 → 729**). Üretici **`backend/.venv` ister** — çıplak container'da
   `ModuleNotFoundError: entropia` verir, önce `cd backend && uv sync --all-extras`.

## Bu partinin BULGUSU — kaydedildi, yeniden sınıflandırılMADI

**`UM-15.c3` SEVK EDİLMEMİŞ (sınıf D şekli).** Clause *"After a MANUAL_STREAM_CONFLICT the UI
rehydrates with the latest stream"* diyor. Ölçüldü: `frontend/src/pages/UserManual.tsx::requestDelete`
yalnız `onSuccess` taşır, `frontend/src/lib/manual.ts::useSoftDeleteManualDocument` da öyle —
**409 yolunda hiçbir invalidation yok**, `streamVersion` bayat `meta`'sında kalır ve hiçbir şey
yeniden okumaz. ADIM 87'nin `onSuccess`/`onSettled` şeklinin birebir ikizi. **Taşınmadı: B → D
D tavanını YÜKSELTİR, o bir adjudication'dır** — bir test slice'ının kararı değil.

**`CP-03.c4` ŞÜPHELİ, ölçüldü ama karara bağlanmadı.** *"After a use-denied refusal the UI clears
the stale selection state"*. `AddPackagePopover.tsx`'te seçim zaten **türetilmiş**
(`rows.find((r) => r.entity_id === selectedId)`), ama `deriveFrom` yalnız `onSuccess` taşır ve red
hâlinde `selectedId` **durur**. Clause'un *"clears"* fiili türetilmiş düşüşü mü yoksa açık bir
temizlemeyi mi kastettiği **belirsiz** — sınıfı değiştirmeden önce bu okunmalı.

## Sıradaki iş — ölçülmüş adaylar (yine de KENDİN ÖLÇ)

**Testle kapanabilir sınıf-B satır neredeyse tükendi.** Kalan 21 sınıf-B kriterin çoğu kayıtlı
**bulgu**dur (yanlışlanamaz ya da sevk edilmemiş): `MB-22` `AOS-04` `AOS-06` `TS-02` `TL-01`
`TL-02` `TL-11` `TL-16` `PC-02` `PC-20` `ESP-05` `RF-08` `RD-01` `RD-05` `RD-12` `RD-13` `UM-15`.
Bu partide **ölçülmemiş** kalan üç ad: **`TS-07`** · **`TL-14`** · **`TR-07`** — üçünü de
`acceptance_semantic_map.yaml`'daki `notes` alanından oku ve **ürün kodunda doğrula** (ADIM 54).

**Alternatif ve muhtemelen daha değerli hat:** defterdeki **on yedi bulgunun** artık bir
**adjudication kalemi** oluşturduğunu ADIM 79 yazmıştı; sayı o günden beri büyüdü. B→C/D taşıma
**tavan yükseltir**, yani bir insan kararıdır — ama *"bu satırların hangileri gerçekten sınıf B"*
sorusunu ölçüp imzaya sunan bir slice, her partide yeniden ölçülen aynı satırları kalıcı olarak
kapatırdı.

**Mühendislik hattı (kabul borcundan bağımsız):** `## Next:` kıpırdamadı — `C6` (G12 imzası),
`F2` (G4), `F3` (Karar 1 / #552), `C9` (Karar 3 / #559). **İmzasız bir kapının arkasındaki
slice'a BAŞLAMA.** A-08 hâlâ tek blocker ve yalnız bir insan denetçiyle ilerler; devam kartı
`docs/implementation/a11y_screen_reader_audit_runbook.md` **§0**'da hazır.

## Ortam çapaları (bu container'da ölçüldü)

```
cd frontend && npm ci                      # node_modules YOK gelir
npx vitest run --no-file-parallelism <dosya>   # alt küme; --no-file-parallelism ZORUNLU
npm run lint && npm run typecheck && npm run coverage   # tam kapı: 72 dosya / 739 passed
cd backend && uv sync --all-extras         # üretilmiş olguları tazelemek için ŞART
uv run python ../scripts/generate_repository_facts.py --root ..          # yaz
uv run python ../scripts/generate_repository_facts.py --root .. --check  # kapı
python3 docs/audit/acceptance_semantic_scan.py --root . \
    --write-report docs/audit/acceptance_semantic_traceability.md \
    --write-ledger docs/audit/acceptance_coverage_debt_ledger.md
python3 docs/audit/acceptance_semantic_scan.py --report --check-generated --ratchet
```

**Postgres KURULMADI ve gerekmedi** (backend'de sıfır satır) → backend suite'i **koşulmadı**,
geçen sayı ve coverage **CI'ın otoritesinde**.

## Paste-ready resume prompt (bir sonraki oturuma yapıştır)

```
Entropia — kabul borcu batch 30 (ADIM 111).

DOĞRULA ÖNCE (handoff STALE-BY-DEFAULT):
  git fetch && git log --oneline origin/main -3
  grep -o '^## ADIM [0-9]*' docs/PROJECT_HISTORY.md | grep -o '[0-9]*' | sort -n | tail -1
  açık PR listesi (state=open) — BOŞ liste bir ANLIK GÖRÜNTÜDÜR, garanti değil (ADIM 100/103).
  Çakışma başlıkta değil DOSYA YOLUNDA ölçülür (ADIM 91): açık PR'lar
  docs/ADIM<n>…KICKOFF.md ekliyor mu?
Ölçtüğüm hâl: main 74db6ff sonrası · en yüksek ADIM 110 · canlı kickoff
docs/ADIM110_LANDED_KICKOFF.md · tavanlar 54 partial / 6 uncovered · A1 B21 C6 D32.

PARTİ SEÇMEDEN ÖNCE ÖLÇ (ADIM 54 + ADIM 88):
  1) python3 docs/audit/acceptance_semantic_scan.py --report ile sınıf-B partial listesini çıkar.
  2) Aday kriterin ID'sini TEST AĞACINDA GREP'LE — kendi id'sini taşıyan bir test varsa clause
     bedavaya kapanabilir (ADIM 68/88).
  3) Kriterin adlandırdığı davranışın ÜRÜN KODUNDA SEVK EDİLDİĞİNİ doğrula. Sevk edilmemişse
     sınıfı yanlıştır → BULGU olarak kaydet, B→D TAŞIMA (tavan yükseltir = adjudication).
  ADIM 110'un ölçmediği üç ad: TS-07 · TL-14 · TR-07. Kalan sınıf-B'lerin çoğu kayıtlı bulgudur.

YÖNTEM (pazarlıksız):
  - Her clause için AYRI case yaz — iki clause iki ayrı kusur sınıfıysa biri diğerini GÖRMEZ.
  - Her assertion için NEGATİF KONTROL: tek noktalı bir kusur kur, yamanın UYGULANDIĞINI assert et
    (ADIM 88: yeşil kontrol çoğu zaman uygulanmamış kontroldür), koş, KIRMIZININ HANGİ
    ASSERTION'DA olduğunu OKU, sonra ağacı geri al ve `git status` ile doğrula (ADIM 100: `finally`
    SIGTERM'de koşmaz).
  - Bir kontrol yalnız HEDEF testi ve yalnız HEDEF assertion'ı düşürmelidir. Mevcut suite'in
    kusur altında YEŞİL kalması boşluğun ölçümüdür (ADIM 105: doğru sebep, yanlış kapsam = RED).
  - Gölge gördüysen KALDIRMAYI dene, kaydetmekle yetinme (ADIM 101).
  - Vacuity muhafızı koy: "hiçbir şey değişmedi" iddiası boş bir dünyada bedavadır (ADIM 100).

KAPANIŞ (CLAUDE.md §Session CLOSING, altı madde):
  - Tavanı MERGED ağaçta TAZE ölç, iki freeze'in farkından TÜRETME (ADIM 93/98/100).
  - Üretilmiş olguları tazele: test eklediysen repository_facts + README bayatlar (ADIM 60);
    üretici backend/.venv ister.
  - Kickoff: ADIM111 dosyasını YAZ ve ADIM110'u `historical` yap (ikisi birlikte).
  - Kapanış prozasında A08_COMPLETE mayınına dikkat:
    A-08[^\n]{0,80}?(Complete|COMPLETE|PASS|Done|tamamlan|kapandı) — TEK SATIRDA 80 karakter.
    Kapsam CLAUDE.md + docs/STAGE2_HANDOFF.md + README + docs/CODEMAPS/*.md.
    KURALI DÜZELTME, PROZAYI DÜZELT: satırı ayır, kelimeyi koru.
  - Dal docs/stage-111-landed → PR → yeşil bekle → merge'ü KULLANICIDAN İSTE (self-merge bloklu,
    auto-merge ARMA). main ilerlediyse REBASE et, "Update branch" düğmesini KULLANMA (ADIM 93/94).
```
