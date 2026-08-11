<!-- doc-status: historical -->
> **EVIDENCE SNAPSHOT — bu belge bir koşunun kaydıdır, güncel gerçek iddiası DEĞİLDİR.**
> Sayılar `98858da` sha'sı üzerine kurulan `test/rc-p11-gate-coverage-truth` dalında,
> **2026-08-11**'de yerel bir macOS makinesinde ölçüldü ve sonraki commit'lerle bayatlar.
> Otorite CI'dır (`gh run list --branch main --limit 1` → job log'u).

# RC §6.7 — P11-3 ve P11-6: kapının ölçtüğü ile iddia ettiği arasındaki fark

**Verdict DEĞİŞMEDİ.** §8 hâlâ **BLOCKED**, açık blocker sayısı hâlâ **üç** (1, 2, 4).
P11-3 ve P11-6 blocker değildi. **P11 KAPANMADI** — P11-1, P11-2 ve P11-8 açık kalıyor
ve bu dalgada **ele alınmadı**.

Bu iki kalem aynı kusur sınıfıdır: **kapı, ölçtüğünden fazlasını ölçüyormuş gibi duruyor.**

| Kalem | Önce | Sonra | Nasıl |
|---|---|---|---|
| **P11-3** | 8 `-chromium-darwin.png` commit'li, **hiçbir job assert etmiyor** | Sekizi de **SİLİNDİ**; geri dönüşü kapı kırıyor | ölçüm → (b) |
| **P11-6** | Tab sırası **3/23** rotada | **23/23**, 0 N/A, tek kaynak `TARGET_PAGES` | kapsam genişletme |

---

## 1) P11-3 — önce ölçüldü, körü körüne kabul edilmedi

Raporun iddiası **doğruydu**, ama "bayatlayabilir" ifadesi fazla nazikti: **zaten
bayatlamıştı**. Dört eksende ölçüldü.

### 1.1 Tüketici var mı?

| Soru | Ölçüm | Sonuç |
|---|---|---|
| Hangi job `-darwin` okuyor? | `.github/workflows/` içindeki **18 `runs-on:`'un 18'i** `ubuntu-latest`; `grep -i macos .github/workflows/` → **NONE** | **hiçbiri** |
| Playwright hangi seti seçer? | `playwright.config.ts`'te `snapshotPathTemplate` **yok** → varsayılan `<spec>-snapshots/<ad>-<proje>-<platform>.png`; karşılaştırma yalnız **koşan** platformun ekiyle yapılır | CI ⇒ `-linux` |
| İki set de sahipli mi? | `-linux` seti `27bf011` *"ci: enforce Linux visual regression gate"* (2026-07-30) ile geldi — sahibi CI. `-darwin` seti `e56575f` (2026-07-21) ile doğdu, **son dokunuş `7360f60` (2026-07-22)** | `-darwin` **sahipsiz** |
| Bir kez üretilip bırakıldı mı? | O tarihten bu yana `frontend/src`'e **67 commit** dokundu (linux baseline'ı eklendiğinden beri **12**) | **evet** |

Tek gerçek tüketici, macOS'ta `npm run visual` koşan bir geliştiricidir — bir **kapı**
değil, bir kişi.

### 1.2 O kişi bugün ne görüyor? (asıl kanıt)

Bu makinede (`darwin 25.5.0 arm64`) `docker compose` stack'i kaldırıldı ve **e2e.yml'in
kullandığı seed'in aynısıyla** (`SEED_E2E_GOLDEN=1 SEED_ESP_TA=1 SEED_RATIONALE=1`)
tohumlandı. `specs/11` **serial** olduğu için tek koşu ilk kırmızıda duruyor; sekiz sayfa
**tek tek** koşturuldu:

```
mainboard                      FAIL   Expected an image 1440px by 1439px, received 1440px by 900px.
strategy-standalone            FAIL   Expected an image 1440px by 1425px, received 1440px by 1135px.
trading-signal-standalone      FAIL   Expected an image 1440px by 2376px, received 1440px by 2438px.
trade-log-standalone           PASS
market-data                    FAIL   Expected an image 1440px by 1205px, received 1440px by 900px.
create-package                 FAIL   Expected an image 1440px by 1238px, received 1440px by 1396px.
ready-check                    FAIL   Expected an image 1440px by 944px, received 1440px by 900px.
run-result                     PASS
```

**8'in 6'sı düşüyor** (ham: `p11_3_visual_darwin_per_page.txt`). Bunlar alt-piksel farkı
değil: yükseklik sapmaları **44–539 px**, `maxDiffPixelRatio: 0.02` toleransının çok
dışında.

### 1.3 Bu bir platform farkı mı? — kontrol deneyi

`p11_3_baseline_dimensions.txt`: aynı sekiz sayfada `-darwin` ile `-linux` baseline'ları
**birbirinden 525 px'e kadar ayrışıyor**. Font rasterizasyonu birkaç px oynatır
(`ready-check` +3, `trading-signal` +62 bu sınıftır); 510/525 px **birkaç tablo satırıdır**
— farklı bir renderer değil, farklı bir sayfa durumu.

Kesin kontrol: **bu makinenin bugün ürettiği yükseklikler `-linux` baseline'larının
yanına düşüyor, `-darwin`'in yanına değil** (mainboard 900 vs linux 929 vs darwin 1439;
market-data 900/900/1205; trading-signal 2438/2438/2376). Yani `-darwin` seti bir
**platform** artefaktı değil, bir **bayatlık** artefaktıdır.

> **Dürüst sınır:** `strategy-standalone` bugün **1135** ölçtü — ne darwin (1425) ne linux
> (900). Bu sayfanın yüksekliği seed'e bağlı olan liste uzunluğuyla değişiyor. Ölçüldü,
> **açıklanmadı**; P11-3'ün sonucunu değiştirmiyor (baseline yine tutmuyor) ama
> `-linux` setinin kendi seed hassasiyeti hakkında **ayrı bir soru** bırakıyor.

### 1.4 Karar: **(b) SİL** — ve gerekçesi

(a) yolu bir **macOS runner** ister. Açıkça değerlendirildi ve **reddedildi**:
GitHub-hosted macOS dakikaları Linux'un **10 katı** faturalanır; üstelik ürün bir **Linux
konteyneri** olarak sevk ediliyor (`frontend/Dockerfile` runtime:
`nginxinc/nginx-unprivileged:1.31-alpine`). Ürünün sevk edilmediği bir platform için
Linux kapısını **ikinci kez** ödemek, bu kalemin çözmediği bir maliyeti getirirdi.

(b) seçildi. Assert edilmeyen bir baseline o sayfaları korumaz; **koruyormuş gibi durur** —
ve dahası, bugün onu koşan tek kişiye **var olmayan bir regresyon** raporlar. Bu, insanlara
kapıyı yok saymayı öğretir; kapısız olmaktan kötüdür.

### 1.5 Sevk edilen

- Sekiz `-chromium-darwin.png` **silindi** (`git rm`).
- **YENİ** `scripts/visual-baseline-platform-gate.sh` — `git ls-files` ile **commit'li**
  baseline'ları okur, assert edilen platform listesi (`ASSERTED_PLATFORMS="linux"`)
  dışındakinde **exit 1**. `ci.yml` → `frontend` job'ına bağlandı (statik kontrol; Docker,
  tarayıcı, DB istemez → stack kurmayan PR'ları da kapsar).
- `specs/11-visual-regression.spec.ts` ve `frontend/e2e/README.md`'deki *"Both
  authoring-platform and Ubuntu CI baselines are committed"* cümlesi **artık yanlıştı**;
  ikisi de düzeltildi ve macOS'ta beklenen davranış (**missing snapshot, regresyon değil**)
  yazıldı.

### 1.6 Kapının ısırdığının kanıtı — negatif önce

```
### NEGATIVE CONTROL — gate run BEFORE the darwin baselines are deleted
FAIL: baseline(s) committed for a platform no job asserts.
      asserted platform(s): linux
        …/create-package-chromium-darwin.png      (+7 more)
EXIT=1

### POSITIVE — gate run AFTER the darwin baselines are deleted
OK: 8 visual baseline(s) tracked, all for asserted platform(s): linux
EXIT=0
```

**Kapı ilk yazımında kendi kusurunu taşıyordu ve negatif kontrol onu yakaladı.**
`grep -Ev "$re" || true` iki hata yapıyordu: (1) `-` ile başlayan deseni grep **opsiyon**
sanıyordu, (2) `|| true` grep'in **hata** çıkışını (2) "ihlal yok"a çeviriyordu. Sonuç:
sekiz ihlalli bir ağaçta kapı **`OK … EXIT=0`** bastı. Düzeltildi (`-e` + exit kodunun üç
dallı okunması). Bu, bu slice'ın konusunun kapının kendisinde tekrarlanmasıdır ve
**negatif kontrolün neden zorunlu olduğunun** kaydıdır.

Ek doğrulama: silme, **başka bir kapı tarafından da** yakalandı —
`scripts/generate_repository_facts.py --check` `Playwright snapshot PNGs 16 → 8`
sapmasıyla kırmızıya döndü; artefakt yeniden üretildi, gate yeşil.

macOS davranışı da doğrulandı (README'deki iddia): silme sonrası `npm run visual`
`A snapshot doesn't exist at …-chromium-darwin.png, writing actual.` diyor —
**eksik baseline**, sahte regresyon değil. Ürettiği dosya commit edilmedi; edilseydi kapı
kırardı.

---

## 2) P11-6 — Tab sırası 3/23 → 23/23

### 2.1 Ölçüm

Doğrulanan üç rota `specs/20-a11y-prechecks.spec.ts`'in dördüncü testindeydi
(`TAB_ORDER_ROUTES = ["/", "/packages/library", "/trading-signal"]`). Daraltmanın yazılı
gerekçesi *"walking every tabbable element on all 23 routes would double this job's wall
clock"* idi. **Ölçüldü: doğru değil.** Sonda tek bir `page.evaluate`'tir ve aynı dosyadaki
yapı testi zaten 23 rotanın navigasyonunu ödüyor. 23 rotada test **13.2 s** sürdü, `@a11y`
job'ının tamamı **1.2 dk** (ADIM 29'un aynı job ölçümü: 1.0 dk).

### 2.2 Sevk edilen

`TAB_ORDER_ROUTES` artık elle yazılmıyor: `utils/screenshotMatrix.ts::TARGET_PAGES`'ten
türetiliyor — `backend/tests/contract/test_a11y_audit_prep_contract.py`'nin tekil kaynak
olarak pinlediği aynı liste. Yürütülemeyen bir rota **sessizce atlanmıyor**: `N/A`
gerekçesiyle `tab_order_routes_NOT_walked`'a yazılıyor ve yürüyüş devam ediyor.

### 2.3 Ölçülen sonuç

```
a11y prechecks: 23 route(s) inspected, 90 advisory observation(s).
Tab order walked on 23/23 route(s); NOT walked on 0.
6 passed (1.2m)
```

| Alan | Değer |
|---|---|
| `tab_order_routes_total` | **23** |
| walked | **23** (0 N/A — 23'ün hepsi `ensureAdmin` ile erişilebilir, Admin-only üçü dâhil) |
| `tab_order_routes_NOT_walked` | **[]** |
| tab-order advisory'si | **0** — hiçbir rotada pozitif `tabindex` kaynaklı sapma yok |
| `blocking_failures` | **[]** |
| advisory toplamı | **90** — ADIM 29 ölçümüyle **birebir aynı**; yeni bulgu yok, regresyon yok |

Ham: `p11_6_a11y_23routes.txt`, `p11_6_precheck_results.json`.

### 2.4 YENİ ÖLÇÜM — bu sonda Tab'a **basmıyor** (rapor bunu bildirmemişti)

Kapsam genişletilirken sondanın ne yaptığı da okundu ve iddiadan **zayıf** olduğu görüldü:

- **Tab tuşuna hiç basmıyor.** DOM sırasını, tarayıcının `tabindex`'ten türeteceği sırayla
  karşılaştırıyor. Görebildiği tek şey **pozitif `tabindex` yeniden sıralamasıdır**; odak
  tuzağı, klavyeyle erişilemeyen kontrol veya roving-tabindex widget'ı **görünmez**.
- **Hiçbir rota bu testi kıramaz.** Bulgular yalnız `advisories`'e yazılıyor; testin
  `expect`'i yok. Yapısal `blocking` kapısı **ilk** testtedir, bu testte değil.

Bu sınır **3 rotada da vardı** — bu slice onu getirmedi, **ölçtü**. Bilerek düzeltilmedi:
gerçek bir Tab yürüyüşü (radio grupları, `<select>`, roving tabindex) yeni bir modelleme
kararıdır ve bu slice kapsamı ölçer, deseni yeniden icat etmez. Bunun yerine sınır
**artefaktın kendisine** yazıldı — `precheck-results.json` artık `tab_order_probe`
alanını taşıyor ve konsola da basılıyor — ki 3→23 genişlemesi sonradan **daha güçlü bir
iddia** gibi okunamasın. Fiziksel Tab yürüyüşü `specs/14-keyboard-flow.spec.ts`'tedir ve
yalnız `/login` + `/`'yi kapsar. **Yeni kalem: P11-6b** (§4).

---

## 3) DOKUNULMAYANLAR — bu belge hiçbirini kapatmıyor

| Kalem | Durum |
|---|---|
| **A-08** | **İNSAN-BLOKLU.** Bu belgenin hiçbir çıktısı `docs/audit/a11y_screen_reader_audit_results.md` §1/§2'ye yazılamaz. Defter BOŞ, dört kriter de ☐, #514 kapalı-ama-iş-açık ayrışması **sürüyor**. Koşu `REMINDER: A-08 is HUMAN-BLOCKED. Nothing above counts as a screen-reader PASS.` satırını basmaya devam ediyor — o satır **kaldırılmadı**. |
| **P11-1** (branch protection) | **AÇIK.** Repo ayarı, insan kararı — agent kapatamaz. Yeni `visual-baseline-platform-gate` de diğerleri gibi **job kapısıdır, required status check DEĞİLDİR.** |
| **P11-2** (görsel kapsam 8→23) | **AÇIK, bilerek.** `CRITICAL_PAGES` sekiz sayfada bırakıldı; 15 sayfada piksel koruması yok. Ayrı PR. |
| **P11-8** (Lighthouse) | **AÇIK**, ele alınmadı. |
| **K-2..K-6** | **DOKUNULMADI** — beşi de ayrı ürün kararı, §6.5'te bilerek gate dışı. |
| Dört blocker | **DOKUNULMADI.** |

Tab sırası ölçümünde **düzeltilecek bir ürün bulgusu çıkmadı** (0 sapma), dolayısıyla
açılacak issue da olmadı. Çıksaydı issue açılacak, ürün **değiştirilmeyecekti**.

---

## 4) Bu koşuda doğan yeni kalemler

| # | Bulgu |
|---|---|
| **P11-6b** | Tab-sırası sondası **Tab'a basmıyor** ve **hiçbir rota onu kıramaz** (advisory-only). 23 rotayı kapsıyor ama ölçtüğü şey pozitif-`tabindex` yeniden sıralamasından ibaret. Sınır artefakta (`tab_order_probe`) ve spec'e yazıldı; **ölçüldü, düzeltilmedi.** Gerçek Tab yürüyüşü yalnız `specs/14`'te, 2 rotada. |
| **P11-3b** | `strategy-standalone` bugün **1135 px** ölçtü — `-darwin` (1425) ve `-linux` (900) baseline'larının **ikisiyle de** uyuşmuyor. Sayfa yüksekliği seed'e bağlı liste uzunluğuyla oynuyor. `-linux` setinin seed hassasiyeti hakkında açık soru; **ölçüldü, düzeltilmedi** (bu slice `-linux` setine dokunmadı). |

---

## 5) Değişiklik kaydı

Silinen: 8 `-chromium-darwin.png`. Yeni: `scripts/visual-baseline-platform-gate.sh` +
bu kanıt dizini. Değişen: `specs/20-a11y-prechecks.spec.ts` (kapsam + dürüstlük alanı),
`specs/11-visual-regression.spec.ts` (yalnız yorum), `frontend/e2e/README.md`,
`.github/workflows/ci.yml` (tek yeni step), `docs/generated/repository_facts.*`
(üretilmiş). **Ürün kodu (`frontend/src`, `backend/src`) DEĞİŞMEDİ** — route,
react-query key, OCC token, Idempotency-Key, hook, SSE taksonomisi, `lib/*.ts`
dokunulmadı.
