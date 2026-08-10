<!-- doc-status: historical -->
> **EVIDENCE SNAPSHOT — bu belge bir koşunun kaydıdır, güncel gerçek iddiası DEĞİLDİR.**
> Aşağıdaki sayılar `2cf7283` sha'sında koşan **tek** bir CI dalgasına aittir ve sonraki
> commit'lerle bayatlar. Otorite CI'dır (`gh run list --branch main --limit 1`).

# ADIM 29 / P11 — otomatik a11y ve görsel regresyon

**Sonuç: 3/3 YEŞİL — ama bu bir WCAG uyum beyanı DEĞİLDİR.** Üç otomatik katman da
Linux'ta (CI'ın kendi platformu) koştu ve geçti; hiçbir eşik gevşetilmedi, hiçbir test
atlanmadı/quarantine edilmedi. Kontrast ekseninde ürün **WCAG 2.2 AA 1.4.3'ü
KARŞILAMIYOR** — §4.

| # | Katman | Kapsam | Sonuç |
|---|---|---|---|
| 1 | Visual regression (`@visual`) | 8 kritik sayfa, 1440×900 fullPage | **8/8 passed** |
| 2 | axe-core ratchet (`@a11y`, bloklayıcı) | 23 route, wcag2a…wcag22aa | **45 serious düğüm / tavan 45** · **0 critical** · 0 moderate · 0 minor |
| 3 | Klavye-only gezinme (`@a11y`) | login → Mainboard → Add menü aç/kapa | **passed (860 ms)** |

---

## Koşum ortamı ve metodoloji

| Alan | Değer |
|---|---|
| Kanıt kaynağı | GitHub Actions — **E2E** workflow, run **`31212829328`** |
| Commit | **`2cf7283d768ad86aa7952f206b99f1a4f4801620`** (`2cf7283`, `main`) — bu oturumun HEAD'i ile **birebir aynı** |
| Tetikleyici | `push` → `main`, 2026-08-07T19:44:59Z; workflow sonucu **success** |
| Platform | `ubuntu-latest` (GitHub-hosted), Chromium (Playwright 1.55.1, `--with-deps`) |
| Hedef | Docker Compose stack (gerçek API + Postgres + Redis + MinIO + worker), `AUTH_MODE=session` |
| Fixture | `SEED_E2E_GOLDEN=1 SEED_ESP_TA=1 SEED_RATIONALE=1` (üç job da aynı seed) |
| Job'lar | `92980675739` (E2E/F-23) · `92980675586` (A11Y/R2-14) · `92980675661` (dev-auth) — **üçü de success** |

### Neden yerel bir koşu değil de CI koşusu?

Talep açıkça **"Linux visual regression suite (CI ile aynı platform)"** diyor.
`toHaveScreenshot` baseline'ları platform ekli (`…-chromium-linux.png` /
`…-chromium-darwin.png`), yani karşılaştırma yalnız **aynı render yığınında** anlamlıdır.
Bu makine `darwin/arm64`'tür; üstelik Docker daemon'ı bu oturumda **ayakta değildi**
(`unix:///Users/.../.orbstack/run/docker.sock` yok). İki seçenek vardı:

1. **Yerel Linux konteynerinde koşmak** — `mcr.microsoft.com/playwright` imajı
   ubuntu-latest runner'ının font/render yığını **değildir**. Oradan çıkacak bir kırmızı
   "regresyon" mu yoksa "farklı platform" mu olduğu ayırt edilemezdi; yorumlanamayan bir
   kanıt, kanıt değildir.
2. **CI'ın kendi Linux koşusunu kanıt almak** — HEAD sha'sında zaten koşmuş, yeşil,
   log'ları ve artefaktları indirilebilir durumda.

**(2) seçildi.** Bu bir kısayol değil, doğru referans düzlemi: CI, `--update-snapshots`
asla koşmaz; yalnız assert eder. Repoda **8 linux + 8 darwin** baseline commit'lidir;
`darwin` seti yalnız yazarın laptop'ı içindir ve **CI tarafından hiç doğrulanmaz** (§5).

Ham log'lar ve artefaktlar bu dizinde:
`p11_visual_gate.txt` · `p11_axe_ratchet.txt` · `p11_axe_summary.txt` ·
`p11_axe_baseline_measured.json`.

---

## 1) Visual regression — `npm run visual` (8/8)

`.github/workflows/e2e.yml` → job *E2E — real browser vs. Docker Compose stack (F-23)* →
adım **"Run the visual-regression gate"**, 19:54:17Z → 19:55:40Z, **success**.

```
> playwright test --grep @visual
Running 8 tests using 1 worker
  ✓  1 visual: mainboard (9.8s)
  ✓  2 visual: strategy-standalone (9.6s)
  ✓  3 visual: trading-signal-standalone (10.3s)
  ✓  4 visual: trade-log-standalone (10.9s)
  ✓  5 visual: market-data (9.6s)
  ✓  6 visual: create-package (9.6s)
  ✓  7 visual: ready-check (10.7s)
  ✓  8 visual: run-result (9.7s)
  8 passed (1.4m)
```

Karşılaştırma parametreleri (`specs/11-visual-regression.spec.ts`, bu koşuda
**değiştirilmedi**): `maxDiffPixelRatio 0.02`, `animations: "disabled"`, fullPage,
1440×900, volatile bölgeler (`time`, `[data-e2e-volatile]`) maskeli.

Aynı job'un ana E2E suite'i (`npm test`) de yeşil: **39 passed / 1 skipped** (atlanan,
session stack'te kendini bilerek skip eden dev-mode spec'i).

## 2) axe-core ratchet — `npm run a11y` (bloklayıcı)

Job *A11Y — axe-core scan vs. the seeded stack (R2-14)*, adım **"Run the axe-core a11y
scan"**, 19:52:15Z → 19:53:18Z, **success**. Toplam **6 test passed (1.0m)**.

```
a11y ratchet: 45 serious node(s) measured against a frozen ceiling of 45.
```

**Yeni ihlal YOK.** Kanıtın üç ayağı:

- **critical = 0**, 23 route'un hepsinde. Kritik hiçbir zaman baseline'lanamaz; tek düğüm
  koşuyu kırardı.
- **serious = 45**, dondurulmuş tavan **45** — sayfa/kural bazında da birebir eşit.
  Artefakt `axe-baseline.measured.json`, repodaki `frontend/e2e/a11y-baseline.json`
  `pages` bloğuyla **karakter karakter aynı** (bu oturumda programatik olarak
  karşılaştırıldı: `measured == baseline → True`, fark kümesi boş).
- **`axe-baseline.tightened.json` artefaktta YOK** → ölçüm hiçbir sayfa/kural çiftinde
  tavanın altına da düşmedi; yani tavan ne aşıldı ne de sessizce gevşek kaldı.
- **moderate = 0 ve minor = 0** — 23 sayfanın tamamında. (Bunlar rapor-only; yine de
  kayda geçiriliyor.)

Ölçülen 45 düğümün **tamamı tek kural**: `color-contrast`, **tamamı 2.67:1**, iki renk
çiftinden ibaret — **33 × `#ffffff` on `#00a9e8`** + **12 × `#00a9e8` on `#ffffff`**.
Bu dağılım, `a11y-baseline.json` §adjudication'ın iddia ettiği dağılımla birebir örtüşür.
En sık düşen seçiciler: `.menu-trigger[aria-haspopup="true"]` (23), `strong` (6),
`.btn-primary`/`.btn`/`.primary` (9), nav link'leri ve `summary`.

Sayfa bazında ölçülen/tavan: mainboard 3 · strategy-details 2 · outsource-signal 3 ·
trading-signal 2 · trade-log 2 · create-package 1 · pre-check 1 · package-library 1 ·
embedded-packages 1 · rationale-families 2 · market-data 2 · research-data 2 ·
portfolio 2 · ready-check 2 · run-results 2 · results-history 1 · arrange-metrics 2 ·
analysis-lab 1 · panel-management 2 · panel-logs 2 · trash 1 · user-manual 1 ·
future-dev 7 → **45**.

## 3) Klavye-only gezinme

```
✓ specs/14-keyboard-flow.spec.ts › @a11y keyboard-only basic flow
  › login → Mainboard → open + close Add menu with keyboard only (860ms)
```

Spec'in gerçekten assert ettiği (mouse tıklaması **yok**, her adım
`document.activeElement` üzerinden doğrulanıyor):

1. `/login` açılışında odak `name="username"` alanında (autofocus) — klavye kullanıcısı
   forma tuş basmadan iniyor.
2. Username → **tek Tab** → `name="password"`; araya odak tuzağı girmiyor.
3. `Enter` native form submit'i tetikliyor → Mainboard başlığı görünür oluyor.
4. `+ Add` butonu **Tab ile ulaşılabilir** (≤80 tab), `Enter` menüyü açıyor.
5. Menü girdileri de Tab ile ulaşılabilir (≤10 tab).
6. `Escape` menüyü mouse'suz kapatıyor.

Aynı koşuda `specs/20-a11y-prechecks.spec.ts`'in dört testi de geçti: yapı/landmark/
başlık envanteri (23 route), odak göstergesi, dialog sözleşmesi (erişilebilir ad +
Escape + odağın tetikleyiciye dönmesi) ve **temsilî route'larda DOM sırası = Tab sırası**.

---

## 4) D-10 disclosure — WCAG 2.2 AA 1.4.3 KARŞILANMIYOR

**Ürün, WCAG 2.2 AA 1.4.3 (Contrast — Minimum) ölçütü için UYUMLU DEĞİLDİR.**
Bu, koşuda ortaya çıkan bir sürpriz değil, **imzalanmış ve kayda geçmiş** bir üründür:

```
Karar #  : D-10
Konu     : A11Y-01 kalıntı accent-mavi seti (45 düğüm) — kalıcı statü
Onaylayan: alimirbagirzade (product owner)
Tarih    : 2026-07-30
Karar    : (i) İmzalı kalıcı sapma
Kayıt    : 45 accent-mavi düğüm mevcut a11y baseline'ında dondurulur. V18 imza mavisi
           korunur. Bu karar WCAG 2.2 AA 1.4.3 uyumluluğu iddiası DEĞİLDİR; ürün bu
           ölçüt için uyumlu olarak pazarlanamaz. Yeni veya artan ihlaller CI ratchet'ini
           kırmaya devam eder.
```
(kaynak: `docs/implementation/a11y_ci_ratchet_and_adjudication.md` §4)

Bu koşu D-10'un **iki yarısını da** doğruluyor:

- Sapma **gerçek ve ölçülü**: 45 düğüm, 2.67:1, gereken 4.5:1'in çok altında.
- Sapma **kapsanmış**: dondurulmuş tavan tutuyor, 46'ncı düğüm CI'ı kırar.

**Release dilinde ne demek:** D-10 **imzalıdır** (adı verilmiş onaylayan + ISO tarih +
kapsam + açık "uyumluluk iddiası değildir" cümlesi). Dolayısıyla bu eksende
**"READY WITH SIGNED DEVIATIONS" AÇIKTIR**. "READY"nin koşulsuz hâli bu eksende
kullanılamaz ve hiçbir belge/pazarlama metni ürünü "WCAG 2.2 AA uyumlu" diye
tanımlayamaz. Kapatmanın tek yolu D-10 seçenek (ii)'dir (`--accent` teması revizyonu +
23 sayfanın görsel yeniden kabulü) — bu slice'ın kapsamında değildir ve **yapılmadı**.

---

## 5) KRİTİK SINIR — bu adımın hiçbir çıktısı A-08 DEĞİLDİR

Yukarıdaki üç katmanın **hiçbiri** ekran-okuyucu kanıtı değildir ve hiçbiri
`docs/audit/a11y_screen_reader_audit_results.md` §1/§2'ye yazılamaz. Bu belge o dosyaya
**dokunmadı**; A-08 defteri BOŞ kalmaya devam ediyor, dört çıkış kriteri de ☐.

axe-core'un kendi koşusu bunu satır olarak da basıyor:

```
REMINDER: A-08 is HUMAN-BLOCKED. Nothing above counts as a screen-reader PASS.
```

Otomatik tarama, NVDA/VoiceOver ile bir insanın duyduğu şeyi ölçmez: duyuru sırası,
okunan ad, rol/durum telaffuzu, canlı bölge kesintisi. A-08 **insan-bloklu** kalır
(takip: GitHub #514; kapatma yetkisi insandadır).

## 6) Dürüst sınırlar ve bu koşuda çıkan açık kalemler

1. **CI kapıları workflow'u kırar, MERGE'İ kırmaz.** `main` üzerinde **branch protection
   YOK** ve **ruleset YOK** (`gh api .../branches/main/protection` → 404 "Branch not
   protected"; `.../rulesets` → `[]`). Yani `@visual` ve axe ratchet birer **job kapısıdır**
   — kırmızıya döner, log bırakır — ama hiçbiri **required status check** değildir; kırmızı
   bir E2E ile merge etmeyi mekanik olarak engelleyen bir şey yoktur. CLAUDE.md'nin
   "CI'da bloklayıcı" ifadesi bu ayrımla okunmalıdır.
2. **Visual gate 23 sayfanın 8'ini kapsıyor.** Kalan 15 sayfa için piksel regresyonu
   koruması **yoktur**; `@screenshots` ve `@prototype` süitleri bilerek opt-in ve CI'da
   koşmuyor.
3. **`darwin` baseline'ları CI'da hiç doğrulanmıyor.** Repoda 8 `-chromium-darwin.png`
   commit'li ama hiçbir job onları assert etmiyor → sessizce bayatlayabilirler.
4. **90 advisory gözlem** (bloklanmayan, prechecks katmanından) bu koşuda da duruyor.
   Dağılım (bu oturumda log'dan satır satır sayıldı, toplam 23+23+21+21+1+1 = **90**):
   23 route'un **tamamında** `contentinfo` landmark **yok** (1.3.1 / 2.4.1); 23 route'un
   **tamamında** ilk tabbable öğe "Log out" butonu — yani **skip link yok** (2.4.1);
   **21** route'ta başlangıç DOM'unda **hiç `aria-live` bölgesi yok** (4.1.3); **21**
   sayfada başlık hiyerarşisi atlıyor (h1 → h3/h4, 1.3.1); `/user-manual`'da **`<h1>`
   hiç yok** (1.3.1 / 2.4.6); +1 odak göstergesi gözlemi (madde 5).
5. **Odak göstergesi advisory'si:** `/` üzerinde bir buton için "computed style unchanged
   on focus: `outline:none`, `box-shadow:none`" gözlemi var (2.4.7 / 1.4.11). İlgili test
   *geçti* çünkü o test yalnız birincil chrome'u örnekliyor — bu gözlem **gated değildir**
   ve kapanmış sayılamaz.
6. **Tab sırası 23 route'un yalnız 3'ünde yürütüldü**; 20 route'ta (`/strategy`,
   `/trade-log`, `/market-data`, `/trash`, … ) DOM-sırası doğrulaması **yapılmadı**.
7. **Ratchet yalnız `serious` üzerinde.** `moderate`/`minor` rapor-only; bu koşuda ikisi de
   0 olduğu için pratikte fark yaratmadı, ama politika farkı duruyor.
8. **Lighthouse hâlâ bağlı değil** — açık iş.

## Değişiklik kaydı

Bu adım **hiçbir kaynak dosyayı, baseline'ı veya eşiği değiştirmedi**; hiçbir CI koşusu
yeniden tetiklenmedi. Üretilen tek kalıcı çıktı bu belge ve yanındaki dört ham kanıt
dosyasıdır.
