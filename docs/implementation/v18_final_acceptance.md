# Entropia V18 — Nihai Kabul Kaydı (R2-14)

> Kaynak gereksinim: `docs/spec/Entropia_V18_Guncel_Arayuz_Eksikleri_ve_Yanlis_Anlamalar.md`
> (**GAP belgesi**) **madde 20 "Nihai kabul tanımı"** + **madde 17** ("Complete yalnızca
> acceptance criteria gerçek browser ve gerçek backend ile geçtiğinde kullanılmalıdır").
>
> Bu belge R2-14 slice'ının çıktısıdır. **Hiçbir maddeyi kendi başına Complete yapmaz** —
> §4'teki product-owner onayı YAZILI olarak alınmadan
> `docs/implementation/entropia_v18_remediation_status.md` satırları güncellenmez.

**Doğrulama ortamı:** host-native local stack (Postgres :5432 + Redis + MinIO + API session-auth
modunda + dramatiq worker + Vite dev server @ `http://localhost:5173`), `SEED_E2E_GOLDEN=1`
`SEED_ESP_TA=1` `SEED_RATIONALE=1` tohumlu gerçek veri. Hiçbir fetch mock'lanmamıştır.
**Doğrulama tarihi:** 2026-07-21. **Dal:** `feat/v18-r2-14-final-acceptance`
(taban: `e56575f`, R2-13).

---

## 1. GAP madde 20 — nihai kabul listesi, madde madde

Statü sözlüğü: **PASS** = canlı stack'te doğrulandı · **PO-BEKLİYOR** = teknik iş bitti,
kabul kararı product-owner'ındır.

| # | GAP madde 20 koşulu | Statü | Kanıt |
|---|---|---|---|
| 20.1 | Mainboard'daki Strategy, Trading Signal ve Trade Log satırlarının üçü de gerçek editörünü **inline** açıyor | **PASS** | `frontend/e2e/specs/08-mainboard-inline-editors.spec.ts` — 3/3 canlı yeşil: "Trading Signal: create → upload → import → Save & Add → close, URL stays /" (53.4s), "Trade Log: …" (50.2s), "Strategy: Add Strategy opens the inline draft editor without navigation" (1.6s) |
| 20.2 | Kullanıcı bu nesneleri **route değiştirmeden** oluşturuyor, düzenliyor, validate ediyor, kaydediyor, kapatıyor | **PASS** | Aynı spec — her testin sonunda URL'in `/` kaldığı assert ediliyor (spec adlarındaki "URL stays /") |
| 20.3 | Add Package **gerçek seçim popover'ı** üzerinden çalışıyor | **PASS** | Canlı doğrulama (bu oturum): `+ Add → Add Package` → `role=dialog[name="Add Package"]` görünür, URL `http://localhost:5173/` **değişmedi**; ekran kanıtı `frontend/e2e/test-results/r2-14-add-package-popover.png`. Bileşen düzeyi: `frontend/src/test/mainboard.test.tsx` — "opens the Add Package popover from a package add-intent (R2-02 → R2-03)" + "lists eligible strategy package revisions and disables can_use=false rows (R2-03)" |
| 20.4 | Normal kullanıcı **raw JSON veya altyapı ID'si girmiyor** | **PASS** | Canlı DOM taraması (bu oturum): `/trading-signal` ve `/trade-log` üzerindeki tüm görünür `input`/`textarea` alanları tarandı — her sayfada ham-JSON textarea'sı **yalnızca bir tane** ve o da `details` disclosure'ı içinde **admin-gated**; kalan tüm alanlar typed (Base TF `1h`, Initial capital `10000`, kolon eşleme vb.). Sözleşme kaydı: status dosyası UI-06 satırı (R2-12) |
| 20.5 | Research dependency ve bütün workflow kilitleri **server-truth state'e** bağlı | **PASS** | `frontend/e2e/specs/03-research-data-upload.spec.ts` — "locks create behind a server-confirmed approved Market Data link" (2.5s, canlı yeşil): sunucu `DEPENDENCY_BLOCKED` döndürdüğünde kilit gerçekten kapalı kalıyor |
| 20.6 | Ready Check **gerçekten PASS** oluyor ve RUN açılıyor | **PASS** | `frontend/e2e/specs/05-mainboard-ready-check-run.spec.ts` (30.9s, canlı yeşil) — spec EXPLICIT **Ready** şartı koşuyor; blocked/NOT_READY başarısızlık sayılıyor (`frontend/e2e/README.md` §"Honest boundaries") |
| 20.7 | Gerçek RUN **başarılı** bitiyor ve Result **Mainboard altında** görüntüleniyor | **PASS** | Aynı spec — run terminal **succeeded** durumuna kadar poll ediliyor, ardından inline `ResultDetail` headline metrikleri + provenance ile assert ediliyor. Görsel kanıt: `frontend/e2e/test-results/r2-14-mainboard-375-fixed.png` (BACKTEST RESULTS kartı: Net Profit / Max Drawdown / ROMAD / Win Rate / Profit Factor) |
| 20.8 | Create Package süreci **request'ten publish'e** kadar browser üzerinden tamamlanıyor | **PASS** | `frontend/e2e/specs/04-create-package-lifecycle.spec.ts` (7.2s, canlı yeşil) — request → Pre-Check passed → C.D.P draft → baseline upload+parse passed → validation passed → Admin approve → **published** → Library `can_use: yes` |
| 20.9 | Backend/auth/permission/error/loading durumları kullanıcıya **doğru ve açıklayıcı** gösteriliyor | **PASS** | Durum matrisi: `frontend/e2e/screenshots/baseline/**/{loading,error,permission-denied}--1440.png` (14 loading · 14 error · 3 permission-denied PNG). Durumların gerçekliği R2-13'te doğrulandı: loading = gerçek spinner (API stall), error = "Backend unavailable" banner'ı, permission-denied = server-truth `TRASH_ACCESS_FORBIDDEN`. Auth hata zarfı: `specs/01-auth.spec.ts` — "rejects an unknown login with the server's canonical error envelope" |
| 20.10 | Mobil ve masaüstü genişliklerinde **yatay sayfa taşması yok** | **PASS** | `frontend/e2e/specs/09-responsive-overflow.spec.ts` — 375/768/1280/1440/1920 beşi de canlı yeşil + "mobile hamburger menu is usable at 375px" (6/6 passed, 24.6s). **Bu slice'ta kapatılan gerçek bulgu:** R2-13 sapma listesi 1.6/1.7. Kök neden: Mainboard bölüm grid'inin `auto` track'i 64 karakterlik composition hash'in min-content genişliğine büyüyordu (ölçüm: section `640px` @ 375px viewport). Düzeltme: `Mainboard.tsx` grid `minmax(0, 1fr)` + `.kv` değer kolonu `minmax(0,1fr)` + `overflow-wrap: anywhere`. Doğrulama: taşan öğe sayısı **110 → 0**, `scrollWidth` 375 |
| 20.11 | 22 sayfanın final screenshot seti V18 prototipiyle **karşılaştırılmış** ve **product owner tarafından onaylanmış** | **PO-BEKLİYOR** | Karşılaştırma tamam: 122 baseline PNG + 20 prototip referansı + madde madde sapma listesi `docs/implementation/v18_visual_deviations.md` (R2-13). **Onay kısmı §4'te bekliyor — bu belge imzalanana kadar 20.11 açıktır.** |

**Özet:** 11 koşulun **10'u PASS**; 20.11 yalnızca product-owner imzasına bağlıdır.

---

## 2. Responsive son geçiş (375 / 768 / 1280 / 1440 / 1920)

| Genişlik | Sonuç | Kanıt |
|---|---|---|
| 375 | Taşma yok (Mainboard + Market Data + Panel Management + TS inline editör) | `specs/09-responsive-overflow.spec.ts` "no horizontal overflow at 375px" |
| 768 | Taşma yok | aynı spec |
| 1280 / 1440 / 1920 | Taşma yok | aynı spec |

Her genişlik için ekran kanıtı `test-results/responsive/<screen>-<width>.png` altına üretilir.

**Kapatılan bulgu F-1** (R2-13 sapma listesi 1.6 + 1.7) — ayrıntı yukarıda 20.10'da.
1.7'deki "RUN kontrollerinin içerik üstüne binmesi" konusunda net karar: `.run-controls` sabit
dock'u v18 prototipinin bilinçli tasarımıdır; workspace'in `padding-bottom: 150px` değeri
içeriğin dock'un altından kaydırılabilmesini garanti eder. Taşma düzeltildikten sonra son
strateji satırı artık dock'un arkasında sıkışmıyor (`test-results/r2-14-mainboard-375-fixed.png`).

---

## 3. Accessibility son geçiş

### 3.1 Otomatik tarama (axe-core)

Yeni katman: `frontend/e2e/specs/13-a11y-scan.spec.ts` (`npm run a11y`), 22 sayfanın tamamı,
WCAG 2.0/2.1/2.2 A + AA etiketleriyle, canlı stack'te Admin oturumunda @1440.
Ham çıktı: `frontend/e2e/a11y-report/axe-results.json` + `axe-summary.txt`.

**Sonuç: critical = 0** (tüm sayfalar). Serious bulgular yalnızca iki kuralda toplanıyor:

| Kural | Sayfa | Düğüm | Değerlendirme |
|---|---|---|---|
| `color-contrast` | 23 | 228 | **Kayıtlı sapma — A11Y-01** (§3.3) |
| `link-in-text-block` | 2 | 2 | **Kayıtlı sapma — A11Y-02** (§3.3) |

Tarama gate'i, kayıtlı bu iki kural DIŞINDA yeni bir serious kuralı belirirse **kırmızıya döner**
(`ACCEPTED_SERIOUS_RULES`, spec içinde) — yani sapma kaydı bir muafiyet değil, dondurulmuş bir sınırdır.

### 3.2 Klavye-only temel akış

Yeni katman: `frontend/e2e/specs/14-keyboard-flow.spec.ts` — fare kullanmadan login →
Mainboard → Add menüsünü açma → menü öğelerine ulaşma → Escape ile kapatma. **Canlı yeşil.**

**Bu slice'ta KAPATILAN gerçek a11y bulgusu — A11Y-FIX-01:**
Add menüsü ve Add Package popover'ı **Escape ile kapanmıyordu** (empirik doğrulama: Escape
sonrası ikisi de `visible: true`). Bu, `~/.claude/rules/accessibility.md` "Support Escape to close
modals, dropdowns, and overlays" + "Restore focus to trigger element on close" kuralının ihlaliydi.
Düzeltme: yeni `frontend/src/components/useEscapeToClose.ts` hook'u her iki popover'a bağlandı
(sunum düzeyi; route/query-key/OCC/Idempotency davranışına dokunulmadı). Doğrulama sonrası:
her ikisi de `visible: false`, odak `+ Add` tetikleyicisine geri dönüyor.

Not: Login sayfasında Username alanı açılışta otomatik odaklanıyor — klavye kullanıcısı forma
tuşa basmadan giriyor. Bu **doğru davranış** olarak doğrulandı ve spec buna göre yazıldı.

### 3.3 Kayıtlı a11y sapmaları — PO kararı gerekir

#### A11Y-01 — v18 paletinin kontrast oranları (serious, 228 düğüm / 23 sayfa)

Bulguların tamamı **v18 temasının kendi renkleridir**, tekil bileşen hataları değil:

| Renk çifti | Ölçülen | WCAG AA eşiği | Nerede | Düğüm |
|---|---|---|---|---|
| `#00842f` üzerine `#e8e8e8` | 3.94:1 | 4.5:1 | `.topbar-badge.ok` (admin/local/api/open rozetleri) | 92 |
| `#ffffff` üzerine `#00a9e8` | 2.67:1 | 4.5:1 | `.menu-blue > .menu-trigger`, `.btn-primary` | 32 |
| `#888888` üzerine `#ffffff` | 3.54:1 | 4.5:1 | `.cp-note`, form yardım metinleri | 26 |
| `#888888` üzerine `#e8e8e8` | 2.89:1 | 4.5:1 | `.brand-title` | 23 |
| `#00a9e8` üzerine `#ffffff` | 2.67:1 | 4.5:1 | gövde içi bağlantılar | 14 |
| `#888888` üzerine `#fafafa` | 3.39:1 | 4.5:1 | panel alt başlıkları | 11 |
| `#c8a44d` üzerine `#fcfcfc` | 2.3:1 | 4.5:1 | `.rd-step-lock` (kilitli adım notu) | 2 |
| `#00a9e8` üzerine `#b9ecff` | 2.1:1 | 4.5:1 | açık sonuç satırındaki bağlantı | 1 |

**Çatışma:** `#00a9e8` (`--accent`) ve `#888888` (`--text-dim`), CLAUDE.md'de v18 temasının
**zorunlu görsel referansı** olarak pinlenmiş değerlerdir. Bunları düzeltmek WCAG AA'yı sağlar
ama v18'in imza mavisini görünür biçimde koyultur. Bu bir kod kusuru değil, **tema kararıdır** —
bu yüzden bu slice tek taraflı değiştirmedi.

**PO'ya sunulan üç seçenek:**

- **(a) Kabul et (kayıtlı sapma).** v18 sadakati korunur; WCAG 2.2 AA kontrast maddesi karşılanmaz.
  Tarama gate'i mevcut sınırı dondurur, yeni ihlalleri yakalar.
- **(b) Kısmi düzeltme (önerilen).** Marka mavisine dokunmadan yalnız gri/yeşil/amber tonları
  koyultulur: `--text-dim` `#888888 → #6e6e6e` (~4.6:1), rozet yeşili `#00842f → #006b26` (~4.8:1),
  kilit amberi koyultulur. **60+ düğüm kapanır**, görsel fark neredeyse ayırt edilemez.
  Kalan ihlal yalnız accent-mavi yüzeyler olur.
- **(c) Tam AA.** Ek olarak `--accent` `#00a9e8 → ~#0077a3`. Tüm ihlaller kapanır; v18'in imza
  rengi değişir — ayrı bir "tema revizyonu" slice'ı ve prototip mutabakatı gerektirir.

#### A11Y-02 — `link-in-text-block` (serious, 2 düğüm / 2 sayfa)

Panel Management ve Panel Logs sayfalarında paragraf içi bir bağlantı yalnız renkle ayrışıyor
(kontrast 2.78:1, altı çizili değil). **Düzeltmesi ucuz ve v18'i etkilemez** (`text-decoration:
underline`) — ancak GAP madde 20 kabul listesinin bir maddesi olmadığı için R2-14 kapsamında
kapatılmadı; PO onayıyla küçük bir takip slice'ına alınabilir.

---

## 4. Product-owner onayı — İMZA BEKLİYOR

> **Bu bölüm doldurulmadan `entropia_v18_remediation_status.md` içindeki hiçbir satır
> Complete'e çekilmez (GAP madde 17 zorunlu düzeltmesi).**

Onay için karar verilmesi gereken maddeler:

| Karar # | Konu | Kaynak | Seçenekler |
|---|---|---|---|
| D-1 | **Görsel sapma listesinin tamamı** — `v18_visual_deviations.md` içindeki PO-APPROVE işaretli maddelerin toptan kabulü | R2-13 | Kabul / madde madde revizyon |
| D-2 | **F-2** makine-değeri görünümleri (CP dropdown'ları, Market Data "ohlcv", Library rozetleri) | v18_visual_deviations F-2 | Display-label mini slice / kabul |
| D-3 | **F-3** CP Source code + Declared dependencies alan yerleşimi | F-3 | Mini slice / kabul |
| D-4 | **F-4** Portfolio "+ Add item" adaylarının ham `mbi_…` ULID göstermesi | F-4 | Frontend-only düzeltme / kabul |
| D-5 | **F-5** Results History kapalı satırında headline metrik yokluğu | F-5 | Satır özeti slice'ı / kabul |
| D-6 | **F-6** TS/TL formlarının dikey yoğunluğu (prototip kompakt grid) | F-6 | Grid sıkılaştırma slice'ı / kabul |
| D-7 | **A11Y-01** kontrast — §3.3'teki (a)/(b)/(c) seçenekleri | bu belge | (a) / **(b) önerilen** / (c) |
| D-8 | **A11Y-02** `link-in-text-block` | bu belge | Takip slice'ı / kabul |
| D-9 | **20.11** — 22 sayfalık final screenshot setinin kabulü | GAP 20 | Onay / revizyon |

**Onay kaydı** (product-owner tarafından dolduruldu):

```
Onaylayan       : alimirbagirzade (product owner)
Tarih           : 2026-07-22
Kapsam          : D-1 … D-9 kararları (22-Jul deep-audit / R3 kickoff)
Karar özeti     : D-1 KABUL · D-2 FIX(R3) · D-3 FIX(R3) · D-4 FIX(R3) ·
                  D-5 FIX(R3) · D-6 FIX(R3) · D-7 (b) kısmi kontrast · D-8 FIX ·
                  D-9 KABUL (20.11 PASS)
Not / istisna   : "FIX(R3)" maddeleri KABUL DEĞİLDİR — R3'te düzeltilecek onaylı
                  kapsamdır; ilgili status satırları düzeltme LANDED olana kadar
                  In Progress (R3) kalır. Yalnız D-1 ve D-9 imzayla kapanır.
                  A-06 (10 sayfa derin görsel kıyas) ve A-08 (NVDA/VoiceOver
                  manuel a11y) bu imzanın DIŞINDA açık iş olarak kalır.
```

### 4.1 Karar sonuçları — madde madde

| Karar # | Konu | PO kararı | Sonraki aksiyon |
|---|---|---|---|
| D-1 | Kalan görsel sapma listesi (`v18_visual_deviations.md`) | **KABUL (imzalı)** | R3'e alınmayan sapmalar signed-deviation; PO-APPROVE→signed |
| D-2 | Create Package makine-değeri görünümleri | **FIX (R3)** | P-03 display-label slice |
| D-3 | Create Package kaynak/bağımlılık yerleşimi | **FIX (R3)** | P-04 iki-kolon layout slice |
| D-4 | Portfolio ham `mbi_…` ULID | **FIX (R3)** | P-11 human-label projection slice |
| D-5 | Results History kapalı satır metrik digest | **FIX (R3)** | P-12 collapsed-digest slice |
| D-6 | TS/TL dikey yoğunluk | **FIX (R3)** | M-06/M-07 kompakt inline shell slice |
| D-7 | A11Y-01 kontrast | **(b) kısmi düzeltme** | `--text-dim`/rozet-yeşil/amber koyulaştır; accent-mavi dokunulmaz |
| D-8 | A11Y-02 `link-in-text-block` | **FIX** | paragraf-içi link `text-decoration: underline` |
| D-9 | 22-sayfa final screenshot seti (20.11) | **KABUL** | 20.11 → PASS; A-06 derin kıyas ayrı açık iş |

---

## 5. Bu slice'ta üretilen doğrulanabilir çıktılar

| Çıktı | Yol | Komut |
|---|---|---|
| axe-core tarama katmanı (22 sayfa) | `frontend/e2e/specs/13-a11y-scan.spec.ts` | `npm run a11y` |
| Klavye-only akış | `frontend/e2e/specs/14-keyboard-flow.spec.ts` | `npm run a11y` |
| Escape-ile-kapanma hook'u | `frontend/src/components/useEscapeToClose.ts` | `npx vitest run` |
| 375px taşma düzeltmesi | `frontend/src/pages/Mainboard.tsx`, `frontend/src/styles/global.css` | `npx playwright test specs/09-responsive-overflow.spec.ts` |
| a11y ham raporu | `frontend/e2e/a11y-report/{axe-results.json,axe-summary.txt}` | — |

**Test durumu (bu oturum, canlı stack):** e2e ana paket **20/20**, a11y paketi **2/2**,
responsive spec **6/6**, vitest **514/514**, tsc + eslint temiz.

---

## 6. Dürüst sınırlar

- **20.11 açıktır** — teknik karşılaştırma tamam, PO imzası yok. Bu belge onaysız hiçbir
  status satırını Complete yapmaz.
- **A11Y-01/A11Y-02 kapatılmadı**, kayıtlı sapmadır. WCAG 2.2 AA kontrast maddesi bugün
  karşılanmıyor; §3.3'teki seçenekler PO kararına sunulmuştur.
- **axe-core otomatik taraması, manuel a11y denetiminin yerine geçmez.** Ekran okuyucu
  (NVDA/VoiceOver) ile uçtan uca denetim yapılmamıştır — `~/.claude/rules/accessibility.md`
  bunu iki ekran okuyucuyla ister; R2 kapsamında yapılmamıştır ve açık iştir.
- **Klavye denetimi temel akışla sınırlıdır** (login → Mainboard → Add menü). Her sayfanın
  tam klavye gezinimi tek tek denenmemiştir.
- **Sapma listesinin derin kıyası kısmen R2-13'ten devralınmıştır:** `v18_visual_deviations.md`
  §"Kalan sayfalar" başlığındaki 10 sayfa (03, 07, 09, 10, 12, 17, 18, 19, 21, 22) için
  madde-madde derin karşılaştırma yapılmamış, yalnız ilk gözlem kaydedilmiştir. Bu sayfaların
  baseline + prototip görüntüleri mevcuttur; derin kıyas açık iştir.
- Doğrulamalar **host-native local stack**'te yapılmıştır; containerized CI yolu aynı
  spec'leri çalıştırır ancak bu oturumda CI'da koşmamıştır.
