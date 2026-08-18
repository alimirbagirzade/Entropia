<!-- doc-status: current -->
> **CANLI KICKOFF.** Bu belge en yeni slice'ın handoff'udur. Bir sonraki slice inince
> `historical`a demote edilir ve yerine yenisi geçer (`check_classification` CI'da doğrular).

# ADIM 80 LANDED — kabul borcu batch 10 (doc 03 frontend): AOS-01 kapandı · sıradaki slice için kickoff

> Tam kayıt: `docs/PROJECT_HISTORY.md` §ADIM 80. Bu belge **devam noktasıdır**, kayıt değil.

## Neredeyiz

- Taban **main `347fe19`**. **Ürün kodu değişmedi**: migration yok, OpenAPI değişmedi,
  `ENGINE_VERSION` değişmedi, `SHARED_ALLOCATION_STATUS` = `future_dev`.
  **Blocker sayısı DEĞİŞMEDİ (1 — yalnız A-08), verdict BLOCKED.**
- Tek clause kapandı: **`AOS-01.c2`** (chooser klavye paritesi). Tavanlar
  **`partial` 97 → 96**, **`debt_class.B` 66 → 65**; açık borç **104** (A=1 · B=65 · C=6 · D=32).
- **Doc 03'te testin kapatabileceği satır KALMADI.** Geriye `AOS-02`'nin iki clause'u,
  `AOS-04.c2` + `AOS-06.c2` (batch 09'un **(B) adjudication**'ıyla *unfalsifiable* işaretli) ve
  sınıf-D satırlar kaldı.

> **ZİNCİR UYARISI — bunu okumadan ratchet'e dokunma.** Bu freeze **main'e** karşı ölçüldü.
> **Batch 08 + 09 hâlâ PR #768'de açık** ve orada **91 partial / B 60** donuyor. Kabul defteri
> **seri bir kaynaktır**: ikinci inen taraf rebase edip **yeniden dondurmak zorundadır**.
> Ölçülenin üstünde kalan bir tavan sessizce geçmez —
> `test_the_frozen_ceiling_leaves_no_headroom` kırmızı verir. **Numara da aynı zincire tabi:**
> main'in son kaydı ADIM 77, 78/79 #768'in, bu yüzden burası **80**.

## Bu slice'ın bıraktığı yeniden kullanım çapaları (tam sembol adlarıyla)

- `frontend/src/test/outsourceSignal.test.tsx::TABBABLE_SELECTOR` ve `::tabStopsWithin(root)` —
  jsdom'da tab sırasını **DOM'dan türeten** iki satırlık yardımcı. jsdom sequential focus
  navigation uygulamaz; bu yüzden `a[href], button, input, select, textarea, summary, [tabindex]`
  seçilir ve `tabIndex >= 0` ile süzülür. **Başka bir sayfa için klavye sırası assert edecek
  slice bunu kopyalamasın, buradan alsın** (ya da paylaşılan bir test util'e taşısın — bu slice
  tek çağıranı olduğu için taşımadı).
- `frontend/src/test/outsourceSignal.test.tsx > Add Outsource Signal chooser > offers the keyboard
  exactly the pointer's two stops, in the same order (AOS-01)` — clause'un cite ettiği düğüm.
- `frontend/src/pages/OutsourceSignal.tsx::TypeChoice` — seçim satırını `<Link>` olarak render
  eden fonksiyon. **Dokunma:** bunu `div onClick`'e çevirmek AOS-01'in üç clause'unu birden
  kırar.

## Pazarlıksız — bu slice'ın öğrendikleri

1. **"İşaretlemek ≠ kapsamak" burada ÖLÇÜLDÜ.** `AOS-01.c1` zaten *"seçimler link, href'leri
   şu"* diyor. Yeni test bunu tekrarlasaydı hiçbir şey kanıtlamazdı: **`tabIndex={-1}` role'ü,
   adı ve href'i olduğu gibi bırakır** → membership testi yeşil kalır, chooser mouse-only olur.
   Bir clause'u kapatmadan önce sor: **mevcut testler bu kusur altında yeşil mi kalıyor?**
   Kalıyorsa yeni assertion **başka bir eksene** bakmalı — burada o eksen **sıra**ydı.
2. **Negatif kontrolün KİMİ kırmızıya çevirdiği, kırmızı olduğu kadar önemli.** İyi kontrol
   (`tabIndex={-1}`) **yalnız** yeni testi düşürdü, diğer altısı yeşil kaldı — yani pointer
   davranışı bozulmadan klavye paritesi kırıldı ve tespit **yeni teste atfedilebilir**. Ürünü
   linkten `div`'e çevirmek de kırmızı verirdi ama **üç testi birden** düşürürdü ve hiçbir şey
   ayırt etmezdi.
3. **Koşamadığın suite'e assertion YAZMA.** Gerçek tarayıcı kanıtı
   `e2e/specs/14-keyboard-flow.spec.ts` (`@a11y`) içine yazılabilirdi ve **daha güçlü** olurdu
   (gerçek Tab + gerçek Enter). Yazılmadı: bu container Docker Hub blob CDN'ine **403** alıyor,
   yani assertion yerelde **doğrulanamazdı**. Sınır `PROJECT_HISTORY.md` §ADIM 80'de ve
   `acceptance_semantic_map.yaml`'ın `AOS-01` notunda **yazılı** — üstü örtülmedi.
4. **`@testing-library/user-event` KURULU DEĞİL** (ölçüldü: `package.json`'da yok, `src/test`
   altında sıfır kullanım). Tek bir clause için bağımlılık ekleme; `fireEvent` + DOM ile
   yazılabilen bir assertion varsa onu yaz (tembel merdiven).
5. **Kriterin son clause'u kapanınca `debt_class` KALDIRILIR.** `covered` bir satır sınıf
   taşıyamaz — scanner `DEBT_CLASS_NOT_ALLOWED` verir.

## Sıradaki tasarım işaretleri

- **Doc 03 bitti**, doc 07 batch 06/07 ile bitmişti, doc 05/04/12/16 kısmen. Sıradaki sınıf-B
  partisi için **önce ölç**: `acceptance_semantic_scan.py --root .. --report` çıktısındaki
  sınıf-B tablosundan tek bir belge + tek bir yüzey seç.
- **Parti seçmeden önce son iki slice'ın REUSE çapalarını oku** — ADIM 68'de bir clause
  mevcut bir düğüm cite edilerek **bedavaya** kapanmıştı.
- **Kapatmaya çalışma — on üç açık bulgu** (`TL-11.c3`, `TL-16`, `TL-01.c4`, `RD-01.c4`,
  `RD-05.c5`, `RD-12.c4`, `RD-13.c4`, `PC-20.c3`, `PC-02.c2`, `TS-07.c2`, `TS-02.c2`,
  `AOS-04.c2`, `AOS-06.c2`). Son dördünün şekli **karara bağlandı** (#768, seçenek B):
  `unfalsifiable: true` işareti taşırlar, **tavandan düşmezler**, ve scanner artık işareti
  `uncovered` olmayan bir clause'da **reddeder**.

## Çalışma yöntemi (bu dalgada işe yarayan)

- Yerel kapılar, **exit code'lar ayrı okunarak** (`| tail` YOK):
  `cd frontend && npm run lint && npm run typecheck && npm run coverage` ·
  `cd backend && uv run python ../docs/audit/acceptance_semantic_scan.py --root .. --report --ratchet` ·
  `uv run python ../scripts/generate_repository_facts.py --root .. --check` ·
  `node scripts/memory_index.mjs --check` (**repo kökünden**, `backend/`'den değil).
- Tek dosyalık vitest koşusu: `npx vitest run <file> --no-file-parallelism`.
  `frontend/node_modules` yoksa önce `npm ci` — ilk koşudaki `ERR_MODULE_NOT_FOUND` test hatası
  **değil**.
- Ratchet düştüğünde scanner **yapıştırılacak bloğu kendisi basar**; sayıyı elle yazma.
- `repository_facts` + `README` **üretilmiştir**: çakışırsa elle birleştirme, `--root ..` ile
  **yeniden üret**.

## Paste-ready resume prompt

```
ENTROPIA V18 — kabul borcu batch 11

ROL: Entropia V18 Principal Engineer.
[ENTROPIA ORTAK SÖZLEŞME bloğunu uygula]

ÖNCE DURUM ÖLÇ — hiçbir SHA'yı bu prompttan alma, hepsini API'den oku.
  git fetch && git log --oneline origin/main -6
  git show origin/main:docs/PROJECT_HISTORY.md | grep '^## ADIM' | tail -4

ZİNCİR UYARISI: kabul defteri SERİ bir kaynaktır. ADIM 80 (batch 10) main'e karşı
  96 partial / B 65 dondurdu; PR #768 (batch 08+09) aynı anda 91 / B 60 donduruyor.
  Hangisi ikinci inerse rebase edip YENİDEN DONDURMALI — ölçülenin üstünde kalan
  tavan test_the_frozen_ceiling_leaves_no_headroom ile kırmızı verir. Numara da
  aynı zincire tabi: en yüksek '## ADIM' + 1, merge edilmiş ad kazanır.

GÖREV: sınıf-B kabul borcundan TEK belge + TEK yüzey seç ve kapat.
  Parti seçmeden ÖNCE ölç:
    cd backend && uv run python ../docs/audit/acceptance_semantic_scan.py --root .. --report
  Sınıf-B tablosundan aday çıkar; kriterin adlandırdığı davranışın gerçekten sevk
  edildiğini backend/src ya da frontend/src'te DOĞRULA (sevk edilmemişse sınıfı
  yanlıştır ve o bir bulgudur, parti değil).

HER CLAUSE İÇİN ZORUNLU:
  1. Mevcut testler bu kusur altında yeşil mi kalıyor? Kalıyorsa yeni assertion
     BAŞKA bir eksene bakmalı — yoksa işaretleme yapıyorsun, kapsama değil.
  2. Negatif kontrol koş ve KİMİN kırmızıya döndüğünü oku. İyi kontrol yalnız yeni
     testi düşürür; her şeyi düşüren kontrol hiçbir şey ayırt etmez.
  3. Koşamadığın bir suite'e (e2e/@a11y — bu container Docker Hub'a 403 alır)
     assertion YAZMA; sınırı map notuna ve PROJECT_HISTORY'ye yaz.
  4. Kriterin SON clause'u kapanıyorsa debt_class'ı KALDIR.

KAPATMAYA ÇALIŞMA — on üç açık bulgu: TL-11.c3, TL-16, TL-01.c4, RD-01.c4,
  RD-05.c5, RD-12.c4, RD-13.c4, PC-20.c3, PC-02.c2, TS-07.c2, TS-02.c2,
  AOS-04.c2, AOS-06.c2. Son dördü #768'de (B) ile karara bağlandı:
  `unfalsifiable: true` taşırlar, tavandan DÜŞMEZLER, yeniden sınıflandırma
  bir adjudication'dır — test slice'ının kararı değil.

TAVANLAR (ADIM 80 sonrası, main tabanlı): partial 96 / uncovered 8 /
  A1 B65 C6 D32, total_criteria 383 (TABAN). Ratchet YALNIZ AŞAĞI iner.

DUR koşulları: çözülmemiş canonical/PO kararı, kırmızı focused test, OpenAPI drift,
çoklu alembic head, historical Result davranışı değişimi. PR'ı aç, durumu dürüstçe
yaz, DUR. MERGE ETME.
```
