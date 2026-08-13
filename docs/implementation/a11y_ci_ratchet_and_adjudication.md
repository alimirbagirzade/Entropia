<!-- doc-status: historical -->
> **HISTORICAL RECORD — bu belge GÜNCEL GERÇEK DEĞİLDİR.** Yazıldığı andaki durumu
> kaydeder; SHA'lar, sayılar, alembic head'i ve "next" maddeleri bayat olabilir.
> Güncel otorite: `CLAUDE.md` §Current position + `docs/generated/repository_facts.md`
> (üretilmiş, CI'da `--check` ile kapılı).

# A11Y — CI ratchet + A11Y-01 yeniden adjudication

Kapsam: `chore/a11y-ci-baseline`. Bu belge **iki** işi yapar:

1. axe-core katmanının CI'daki geçme/kalma sınırını **kural muafiyetinden düğüm-sayısı
   tavanına** (ratchet) çevirir ve mevcut sapmaları dondurur.
2. **A11Y-01** (kontrast) sapmasını yeniden ölçülmüş rakamlarla **adjudicate eder**; D-10
   product-owner kararı 2026-07-30'da imzalanmıştır (§4).

Belge zamanla **imzalı a11y ürün kararlarının sicili** hâline geldi ve bugün **iki** karar
taşıyor: **D-10** (kontrast, 1.4.3 — §4) ve **D-11** (landmark kümesi / K-3 — §4b). Yeni bir
imzalı a11y kararı buraya, aynı `Karar # / Onaylayan / Tarih / Kayıt` biçiminde yazılır.

Kapatmadığı eksenleri Complete YAPMAZ — §6.

---

## 1. Önce düzeltilmesi gereken iki bayat önerme

Bu slice'a girilirken doğru sanılan iki şey **empirik olarak yanlış** çıktı. İkisi de
`CLAUDE.md` §"Açık iş" ve `v18_final_acceptance.md` §3.1'de yazılıydı.

### 1.1 "a11y/visual katmanları CI'da koşmadı" — a11y için YANLIŞ

axe-core taraması `d5f0322 ci(qa): coverage, dependency-audit and a11y gates in CI`
ile CI'a alınmış; `.github/workflows/e2e.yml` içinde kendi runner'ında **`A11Y` job'u**
olarak her PR'da koşuyor ve yeşil.

Kanıt (bu oturumda okundu):

```
gh run view 30439453123 --json jobs
A11Y — axe-core scan vs. the seeded stack (R2-14) :: success :: 09:23:51Z -> 09:26:57Z
```

Yani **kullanıcının (a) maddesinin "CI'a bağla" yarısı zaten yapılmıştı.** Gerçek boşluk
"koşmuyor" değil, **"koşuyor ama ölçmüyor"** idi (§2).

**2026-07-30 takip notu:** Bu slice yazıldığında visual/screenshot önermesi doğruydu.
Final acceptance slice'ı sekiz Ubuntu baseline'ını commit edip `@visual` katmanını gerçek-session
E2E job'ına bloklayıcı `npm run visual` adımıyla bağladı. `@screenshots` ve `@prototype`,
kanıt üreticisi oldukları için hâlâ opt-in'dir.

### 1.2 "228 serious node" — bugün YANLIŞ, gerçek sayı **70**

228 rakamı `frontend/e2e/a11y-report/axe-summary.txt` dosyasından geliyor; o dosya
`35cce7a` (R2-14 kabul geçişi, 2026-07-22) commit'inde donmuş ve **D-7(b) ile D-8
düzeltmeleri LANDED olmadan ÖNCE** ölçülmüş. Aynı dosya hâlâ `link-in-text-block × 2`
gösteriyor — o kural D-8 ile kapatıldı; dosyanın bayat olduğunun kendi kanıtı budur.

Bugünkü gerçek ölçüm, `origin/main` @ `9e86c99` üzerinde koşan **CI run 30436036299**
artifact'ından alındı:

| Ölçüm | Tarih | color-contrast düğüm | link-in-text-block |
|---|---|---|---|
| R2-14 kabul (repoda duran dosya) | 2026-07-22 | **228** / 23 sayfa | 2 |
| **Bugün (CI artifact, main @ 9e86c99)** | **2026-07-29** | **70** / 23 sayfa | **0** |

D-7(b) tahmini "60+ düğüm kapanır" diyordu; gerçekte **158 düğüm** kapandı.

> `frontend/e2e/a11y-report/*` **bilerek olduğu gibi bırakıldı** — o, R2-14 kabulünün
> tarihli kanıt artifact'ıdır, üstüne yazmak kabul kaydını siler. Güncel doğruluğun tek
> kaynağı artık `frontend/e2e/a11y-baseline.json` (provenance alanı hangi CI run'ından
> ölçüldüğünü taşır). `v18_final_acceptance.md` §3.1'e bu yönde bir "superseded" işareti
> düşüldü.

---

## 2. Gerçek boşluk: muafiyet ölçmeyi durdurmuştu

Eski sınır (`13-a11y-scan.spec.ts`):

```ts
const ACCEPTED_SERIOUS_RULES = ["color-contrast"];
```

Bu **kural kimliğini** muaf tutuyordu, bulunan düğümleri değil. Sonucu: `color-contrast`
altında **kaç düğüm çıkarsa çıksın** gate yeşil kalıyordu. Yeni bir bileşen yanlış bir gri
ile gelseydi — v18 paletiyle hiç ilgisi olmayan gerçek bir kod kusuru — CI bunu görmezdi.
"Kayıtlı sapma" pratikte "o kural kapalı"ya dönüşmüştü.

### Yeni sınır — ratchet

`frontend/e2e/a11y-baseline.json`:

```json
{ "pages": { "mainboard": { "color-contrast": 4 }, "future-dev": { "color-contrast": 8 } } }
```

| Durum | Davranış |
|---|---|
| `critical` (herhangi bir sayfada, herhangi bir kural) | **FAIL** — baseline'a alınamaz |
| serious, ölçülen **>** tavan | **FAIL** — sayfa + kural + delta ile |
| serious, sayfada tavanı olmayan kural | tavan 0 ⇒ **ilk düğümde FAIL** |
| serious, ölçülen **<** tavan | **PASS** + gürültülü uyarı + sıkılaştırılmış harita artifact'ı |
| `moderate` / `minor` | rapor edilir, gate değil (politika değişmedi) |
| baseline dosyası yok/okunamıyor | **FAIL** (fail-closed — sessizce "her şey serbest"e düşmez) |

**Asimetri bilinçli ve maliyeti kayıtlıdır.** İyileşmeyi FAIL yapmak klasik ratchet
davranışıdır ama burada, kontrastla alakasız bir PR bir düğümü tesadüfen düzelttiğinde
build'i kırardı. Bunun yerine run, sıkılaştırılmış haritayı `a11y-report/
axe-baseline.tightened.json` olarak yazar ve `::warning::` basar. **Dürüst maliyet:** biri
o dosyayı commit'leyene kadar tavan gerçeğin üstünde (gevşek) kalabilir; bu uyarıdan
başka onu iten bir mekanizma yok.

Tavanı **yükseltmek** PO kararıdır (§4) — CI'ı yeşile boyamak için değil.

---

## 3. A11Y-01 — bugünkü 70 düğümün gerçek dağılımı

Ölçüm: run 30436036299 `axe-results.json`, düğüm başına axe'ın raporladığı renk çifti.

> **Bu tablo 2026-07-29 sabahının (main @ `9e86c99`) fotoğrafıdır ve tarihsel kayıt olarak
> öyle bırakıldı.** Aynı günün öğleden sonrasında Sınıf B'nin 25 düğümü A11Y-03/04 ile
> kapatıldı; güncel sayı **45** ve tamamı Sınıf A'dır (§5 DURUM kutusu). Aşağıdaki iki
> Sınıf B satırı artık üründe **yok** — neyin neden kusurlu olduğunu anlatan teşhis
> olarak duruyorlar.

| Düğüm | Ön plan / arka plan | Oran | Nerede | Sınıf |
|---|---|---|---|---|
| 33 | `#ffffff` on `#00a9e8` | 2.67:1 | `.menu-trigger[aria-haspopup]`, `.btn-primary`, `.btn`, `.primary` | **A — accent** |
| 12 | `#00a9e8` on `#ffffff` | 2.67:1 | gövde içi bağlantılar, `strong`, `summary` | **A — accent** |
| 23 | `#888888` on `#e8e8e8` | 2.89:1 | `.brand-title` (üst marka şeridi) | **B — eksik kalan D-7(b) işi** |
| 2 | `#c8a44d` on `#fcfcfc` | 2.30:1 | `.rd-step-lock` (kilitli adım notu) | **B — eksik kalan D-7(b) işi** |
| **70** | | | | **45 A · 25 B** |

### Sınıf A (45 düğüm) — v18 imza mavisi, D-7(b)'nin bilerek dokunmadığı yüzey

PO 22-Tem kararı: *"(b) kısmi düzeltme — `--text-dim`/rozet-yeşil/amber koyulaştır;
**accent-mavi dokunulmaz**"*. Bu 45 düğüm tam olarak o karardır. Kod kusuru değil,
**imzalı tema kararı**. Ratchet bunları tavan olarak dondurur.

### Sınıf B (25 düğüm) — D-7(b)'nin KAPATMASI gereken ama kapatamadığı düğümler

Bu, bu slice'ın asıl bulgusu: **PO'nun onayladığı (b) düzeltmesi eksik uygulandı.**
İkisi de "gri/amber koyulaştır" kapsamındaydı, ikisi de düzeltmenin yolundan kaçtı —
ama farklı sebeplerden:

**B-1 — `.top-title` (23 düğüm).** D-7(b) `--text-faint` değişkenini `#888888 → #6e6e6e`
yaptı. Ama `frontend/src/styles/global.css:70` rengi **değişken üzerinden değil, sabit
kodlanmış** olarak taşıyor:

```css
.top-title { background: #e8e8e8; ... color: #888; }
.brand-title { letter-spacing: 0.5px; }   /* rengi .top-title'dan miras alır */
```

Değişkeni değiştirmek buraya ulaşmadı. Tek düzeltmeyle **70 düğümün 23'ü** (≈%33) kapanır.

> **ERRATA (A11Y-03 uygulanırken ölçüldü, 2026-07-29).** "`#888` yerine `var(--text-faint)`
> yaz" reçetesi **tek başına yetmiyordu.** D-7(b)'nin ürettiği `#6e6e6e` beyaz üstünde
> AA'yı geçiyor ama bu şeridin zemini beyaz değil, `#e8e8e8`: orada `#6e6e6e` yalnızca
> **4.16:1** — eşiğin altında. Token bu yüzden bir adım daha koyulaştırıldı
> (`#6e6e6e → #666666`, `#e8e8e8` üstünde **4.69:1**, beyaz üstünde 5.10 → 5.74:1), ve
> `.top-title` artık sabit renk yerine token'ı okuyor. Yani B-1'in kök nedeni "sabit
> kodlanmış renk"ti, ama düzeltmesi iki hamle: **token'ı doğru zemine göre kalibre et**
> + **sabit rengi token'a bağla**. Aynı şeritteki ikinci sabit gri
> (`.topbar-actor label { color: #666 }`) de token'a bağlandı — `#666` yeni token'la
> bayt-aynı olduğu için sıfır piksel değişimi, tek amacı aynı sapmanın tekrarlamaması.

**B-2 — `.rd-step-lock` (2 düğüm).** İhlal, ebeveynin opaklığından doğuyor:

```css
.rd-step-lock { color: var(--warn); }
.rd-step[data-locked="true"] { border-style: dashed; opacity: 0.7; }
```

`0.7` opaklık `#b07d00`'ı ekranda `#c8a44d`'ye kompozitliyor → 2.30:1. **Bu yüzden
D-7(b)'nin "kilit amberini koyulaştır" reçetesi tek başına çalışmazdı** — `--warn` ne
kadar koyulaşırsa koyulaşsın 0.7 opaklık onu geri açar. Düzeltmenin yarısı opaklığı
kilit göstergesinden ayırmaktır (dashed border + greyed adım numarası zaten sinyali
taşıyor).

> **ERRATA (A11Y-04 uygulanırken ölçüldü, 2026-07-29).** Bu paragraf ilk yazıldığında
> *"buradaki sorun rengin kendisi DEĞİL: `--warn: #b07d00` tek başına beyaz üstünde
> AA'yı geçer"* diyordu. **Bu yanlıştı.** `#b07d00` beyaz üstünde **3.63:1**, `.rd-step`
> zemininde (`--bg-elev-2` `#fafafa`) **3.48:1** ölçülür — ikisi de AA'nın 4.5:1 metin
> eşiğinin altında. `#b07d00` yalnızca kenarlık/nokta gibi **metin-olmayan** yüzeylerin
> 3:1 eşiğini geçiyordu, metnin eşiğini değil. Sonucu: **opaklığı kaldırmak tek başına
> bu 2 düğümü kapatmaz** — geriye 3.48:1 kalır, hâlâ serious ihlal. A11Y-04 bu yüzden
> iki parçalı uygulandı: opaklık kompoziti kaldırıldı **ve** token
> `--warn: #b07d00 → #8a6200` koyulaştırıldı (beyaz 5.49:1, `#fafafa` 5.26:1, kendi
> %12 wash'ı 4.65:1). Token darbesi D-7(b)'nin *"amber koyulaştır"* kapsamındadır;
> yeni PO kararı gerekmedi.

**Bu iki madde YENİ bir PO kararı gerektirmez** — D-7(b) zaten imzalı. Eksik olan
uygulamadır. Bu slice bunları **bilerek düzeltmedi**: CI sınırı değiştiren bir PR'a tema
CSS'i karıştırmak "tek mantıksal değişiklik" kuralını bozar ve v18 yüzeyine dokunan bir
değişiklik kendi görsel kanıtını hak eder. Takip slice'ı olarak açık bırakıldı (§5).

---

## 4. Product-owner kararı — D-10 ✅ İMZALI

D-7 (22-Tem) hâlâ geçerli; bu **onu değiştirme talebi değil**, (b) uygulandıktan sonra
geriye kalanın ne olacağı sorusudur.

**Karar konusu:** Sınıf B kapandıktan sonra geriye kalan **45 düğümlük accent-mavi seti**
kalıcı olarak ne sayılacak?

| Seçenek | Sonuç | Maliyet |
|---|---|---|
| **(i) İmzalı kalıcı sapma** (öneri) | 45 düğüm baseline'da donar; v18 imza mavisi korunur; WCAG 2.2 AA **1.4.3 karşılanmaz** ve bu yazılı kalır | Sıfır kod. Ürün "WCAG AA uyumlu" DİYEMEZ. |
| **(ii) Tam AA — eski (c) seçeneği** | `--accent` `#00a9e8 → ~#0077a3`; 45 düğüm kapanır, toplam **0** olur | Ayrı tema-revizyon slice'ı + v18 mockup mutabakatı + 23 sayfanın görsel yeniden kabulü |
| **(iii) Hedefli düzeltme** | Yalnız metin taşıyan accent yüzeyleri (buton dolgusu / gövde linki) koyulaştırılır, dekoratif accent aynı kalır | Orta; 45'in bir kısmını kapatır, "kısmen AA" durumu yaratır — en zor savunulan seçenek |

**Öneri: (i).** Gerekçe: (ii) 23 sayfanın görsel kabulünü yeniden açar ve v18 mockup'ı
CLAUDE.md'de **zorunlu görsel referans** olarak pinli; bu, bir a11y slice'ının tek taraflı
alabileceği bir karar değil. (iii) "kısmen uyumlu" gibi savunulması en zor sonucu üretir.

```
Karar #  : D-10
Konu     : A11Y-01 kalıntı accent-mavi seti (45 düğüm) — kalıcı statü
Seçenekler: (i) imzalı kalıcı sapma [öneri] / (ii) tam AA tema revizyonu / (iii) hedefli
Onaylayan: alimirbagirzade (product owner)
Tarih    : 2026-07-30
Karar    : (i) İmzalı kalıcı sapma
Kayıt    : 45 accent-mavi düğüm mevcut a11y baseline'ında dondurulur. V18 imza mavisi
           korunur. Bu karar WCAG 2.2 AA 1.4.3 uyumluluğu iddiası DEĞİLDİR; ürün bu
           ölçüt için uyumlu olarak pazarlanamaz. Yeni veya artan ihlaller CI ratchet'ini
           kırmaya devam eder.
```

---

## 4b. Product-owner kararı — D-11 ✅ İMZALI (K-3, landmark kümesi)

**Karar konusu:** Shell hiçbir `<footer>` render etmiyor, yani `contentinfo` landmark'ı
**23 / 23 route'ta yok** (K-3; precheck sınıfı beş koşuda da `23` — kararlı, oynamıyor).
Denetim checklist'inin **A-2** maddesi ise `banner`, `navigation`, `main`, `contentinfo`
olmak üzere **dört** landmark bekliyor. Soru: eksik olan **ürün mü, beklenti mi?**

| Seçenek | Sonuç | Maliyet |
|---|---|---|
| **(i) Checklist'i hizala + imzalı sapma** (öneri) | Entropia'nın landmark kümesi **üç**tür (`banner`/`navigation`/`main`); A-2 bunu bekler; K-3 `PO-APPROVE` olur | Sıfır kod. Ürün ileride footer isterse **yeni** bir karar gerekir. |
| **(ii) Görünür footer ekle** | Dördüncü landmark gerçekten var olur | v18 mockup'ta footer **YOK** (`grep` → 0 eşleşme) → **zorunlu görsel referansın ihlali**; 23 `-linux` baseline'ının 23'ü yeniden üretilir; Lighthouse CLS tabanı yeniden ölçülür; ayrıca **yeni bir v18 sapma kaydı** gerekir |
| **(iii) Boş / görsel olarak gizli `<footer>`** | Sayaç yeşile döner | **REDDEDİLDİ.** 0 baseline değişir ama landmark'ı **doldurmaz**: rotor'la `contentinfo`'ya atlayan kullanıcı hiçbir şey duymaz. Ölçüyü ürüne değil **ölçüme** uydurmak olurdu. |

**Karar (i)'in dayanağı — iki ölçüm, biri insan:**

1. **Hiçbir WCAG başarı ölçütü `contentinfo` landmark'ı zorunlu kılmaz.** 1.3.1 *var olan*
   yapının programatik olarak sunulmasını ister; var olmayan bir footer'ın sunulması
   gerekmez. A-2'nin "dört landmark" beklentisi **checklist'in kendi beklentisiydi**, dış
   bir ölçütün değil — RC §6.5'in K-3 satırındaki `1.3.1 / 2.4.1` etiketi bu yüzden kalemi
   olduğundan ağır göstermişti.
2. **A-08'in insan denetçisi bu soruyu zaten cevapladı.** SR-2 (VoiceOver / Safari /
   macOS, 2026-08-12) oturumunda route 1 (`/`) A-2 kontrolünde denetçi rotor'un Landmarks
   listesini gezdi, `banner` / `navigation` / `main` duydu, **`contentinfo` yoktu** ve
   yokluğu **kozmetik** buldu — landmark gezinmesini **engellemedi**. Kayıt:
   `docs/audit/a11y_screen_reader_audit_results.md` §1 ▸ route 1 dipnotu **ᴷ³**. Tek
   rotanın gözlemi karara tek başına yetmez, ama **kararın yönünü insan gözlemi
   doğruladı**: makine ölçümü (23/23 yok) ile insan yargısı (engellemiyor) aynı yöne bakıyor.

```
Karar #  : D-11
Konu     : K-3 — `contentinfo` landmark'ı yok (23/23 route); checklist A-2 dört bekliyor
Seçenekler: (i) checklist'i hizala + imzalı sapma [öneri] / (ii) görünür footer /
           (iii) boş-gizli footer [reddedildi]
Onaylayan: alimirbagirzade (product owner)
Tarih    : 2026-08-13
Karar    : (i) Checklist'i hizala + imzalı kalıcı sapma
Kayıt    : Entropia bir footer SEVK ETMEZ. Uygulamanın landmark kümesi ÜÇ'tür —
           `banner`, `navigation`, `main` — ve denetim checklist'inin A-2 maddesi bu
           ürün için üçü bekler. K-3 bu kararla `PO-APPROVE` olur; yeniden
           dosyalanmaz. Bu karar bir WCAG uyumluluk iddiası DEĞİLDİR, ama bir
           uyumluluk EKSİĞİ de değildir: hiçbir SC contentinfo'yu zorunlu kılmaz.
           İki sınır bilerek yazılıdır: (a) precheck'in K-3 advisory'si
           SUSTURULMAZ — advisory ölçümdür, karar yalnız dispozisyonunu belirler;
           (b) ürün ileride gerçek footer İÇERİĞİ isterse (sürüm / ortam / yasal
           metin) bu YENİ bir karardır ve bir v18 sapma kaydı gerektirir — D-11
           onu kapsamaz.
```

---

## 5. Bu slice'ın ürettiği doğrulanabilir çıktılar

| Çıktı | Yol | Durum |
|---|---|---|
| Dondurulmuş baseline (provenance'lı) | `frontend/e2e/a11y-baseline.json` | **Landed** |
| Ratchet gate | `frontend/e2e/specs/13-a11y-scan.spec.ts` | **Landed** — `npx tsc --noEmit` temiz |
| CI sınır tarifi | `.github/workflows/e2e.yml` (`a11y` job yorumu) | **Landed** |
| Ekran-okuyucu denetim checklist'i | `docs/implementation/a11y_screen_reader_audit_checklist.md` | **Landed (checklist); denetimin KENDİSİ yapılmadı** |

**Takip işleri (bu slice'ta AÇILMADI):**

| # | İş | Neden ayrı |
|---|---|---|
| A11Y-03 | `.top-title` sabit `#888` → `--text-faint` (23 düğüm) | D-7(b) uygulaması; tema CSS'i, kendi görsel kanıtını ister |
| A11Y-04 | `.rd-step[data-locked]` `opacity: 0.7` kompoziti (2 düğüm) | Aynı; düzeltme opaklığı kaldırmak, rengi koyulaştırmak değil |
| A11Y-05 | Baseline'ı A11Y-03/04 sonrası 70 → 45'e sıkılaştır | Yukarıdakiler landed olunca; CI zaten sıkılaştırılmış haritayı üretir |

> **DURUM (2026-07-29): üçü de KAPANDI.** A11Y-03/04 **PR #493** ile (`bfb5368`),
> A11Y-05 onu takip eden baseline PR'ı ile landed. §5 tablosunun tahminleri gerçek
> ölçümle şöyle karşılaştı:
>
> | # | Tahmin | Gerçekleşen |
> |---|---|---|
> | A11Y-03 | "`#888` → `--text-faint`" tek hamle | **İki hamle gerekti.** Token'ın kendisi de kalibre edilmeliydi: `#6e6e6e` beyazda AA'yı geçiyor ama bu şeridin zemini `#e8e8e8` ve orada yalnız 4.16:1. `--text-faint: #6e6e6e → #666666` + `.top-title` token'ı okuyor. 23 düğüm kapandı. |
> | A11Y-04 | "düzeltme opaklığı kaldırmak, **rengi koyulaştırmak değil**" | **Yanlıştı** — bkz. §3 B-2 ERRATA. Opaklık kalkınca geriye 3.48:1 kalıyordu, hâlâ serious. Hem opaklık kaldırıldı hem `--warn: #b07d00 → #8a6200`. 2 düğüm kapandı. |
> | A11Y-05 | 70 → 45 | **Birebir 45.** CI run `30448240930`, sayfa başına −1 (marka şeridi), research-data ek −2 (kilit notu). |
>
> Kalan 45 düğümün tamamı tek sınıf: `33 × #ffffff on #00a9e8` + `12 × #00a9e8 on #ffffff`,
> hepsi 2.67:1 — yani **Sınıf A, D-10'un konusu**. Sınıf B artık ölçümde yok.

---

## 6. Dürüst sınırlar — bu slice'ın KAPATMADIĞI eksenler

- **A11Y-01 ürün kararı ekseninde kapandı; teknik sapma sürüyor.** D-10, kalan **45
  düğümü** imzalı kalıcı tema sapması olarak kabul etti. Ratchet sınırı dondurur; WCAG 2.2
  AA 1.4.3 bugün hâlâ **karşılanmıyor** ve ürün bu ölçüt için uyumlu olarak tanımlanamaz.
- **Ekran okuyucu (NVDA/VoiceOver) denetimi YAPILMADI.** `~/.claude/rules/accessibility.md`
  en az iki ekran okuyucu ister. Bu slice yalnız **checklist** üretti; checklist denetim
  değildir ve otomatikleştirilemez — bkz. ayrı belge. A-08 AÇIK kalır.
- **A-06 ve visual-regression CI sonradan kapandı (2026-07-30).** 10-doc derin kıyas
  `v18_visual_deviations.md` §A-06'da tamamlandı; `@visual` gerçek-session E2E job'ında
  bloklayıcıdır. Exploratory `@screenshots` ve `@prototype` bilinçli olarak opt-in kalır.
- **Lighthouse bağlanmadı.** Kullanıcı isteği "axe-core / Lighthouse" diyordu; axe-core
  zaten mevcut katmandı ve ratchet ona uygulandı. Lighthouse ayrı bir araç (performans +
  a11y skoru) ve ayrı bir CI bütçesi ister; **eklenmedi**, açık iştir.
- **Ratchet yalnız `serious` üzerinde.** `moderate`/`minor` hâlâ rapor-only; bu bilinçli
  (mevcut politikanın korunması) ama bir boşluktur.
- **Tarama tek viewport (1440px) ve tek rol (Admin).** 375px ve Admin-olmayan roller
  taranmıyor — a11y kapsamı sayfa matrisiyle sınırlı, durum matrisiyle değil.
