<!-- doc-status: current -->

# P9-F1 — Frontend build reproducibility (ADIM 33, 2026-08-10)

RC raporu `docs/releases/Entropia_V18_RC_Readiness_2026-08-07.md` §6.7'nin **P9-F1**
kalemi. **Blocker sayısı DEĞİŞMEDİ (üç); §8 verdict'i BLOCKED kalır.** P9-F1 bir blocker
değildi ve kapanması bir blocker'ı kapatmaz.

Kapsam **yalnız** P9-F1. Aynı satırdaki **P11-1 (branch protection) bu dalgada ELE
ALINMADI** — repo ayarı, insan kararı.

---

## 1. Önce ölçüldü — rapor körü körüne kabul edilmedi

Raporun iddiası iki parçalıydı: (a) `npm install` kullanılıyor, (b) `COPY package-lock.json*`
glob'u lockfile'ın yokluğunu tolere ediyor. **İkisi de doğru çıktı**, ama iddianın
**bugünkü etkisi ölçülmeden** yazılmamalıydı — ölçüldü:

| Ölçüm | Sonuç | Ham kanıt |
|---|---|---|
| `package.json` ↔ `package-lock.json` bugün ayrışmış mı? | **HAYIR.** `npm install` lockfile'ı **bit-bit değiştirmedi** (`a8979c98…` → `a8979c98…`) | `p9f1_install_vs_ci.txt` |
| `npm install` ile `npm ci` aynı bundle'ı mı üretiyor? | **EVET, bugün.** `dist/` dosyalarının dördü de aynı sha256; çözünen bağımlılık ağacı da aynı (`npm ls --all --json` → `ec299ea6…` her ikisinde) | `p9f1_install_vs_ci.txt` |

**Bu yüzden dürüst kayıt şudur: değişiklik bugün bir DAVRANIŞ DEĞİŞİKLİĞİ DEĞİLDİR.**
Bugün ikisi aynı sonucu veriyor. Değişen şey **garantidir**: `npm install`'ın bugün
lockfile'a uyması, yarın da uyacağının garantisi değildir. RC raporunun P9 bölümü de
(`evidence/2026-08-07/P9_security.md` §F-1) aynı şeyi söylüyordu — "bugün fiilî ayrışma
yok; reproducibility riski, açık bir güvenlik açığı değil". Bu ölçüm onu **doğruladı**.

---

## 2. Sevk edilen değişiklik

`frontend/Dockerfile` — üç satır:

```diff
-COPY package.json package-lock.json* ./
-RUN npm install
+COPY package.json package-lock.json ./
+RUN npm ci
 COPY . .
```

`frontend/.dockerignore` — **YENİ dosya**. Gerekçesi kozmetik değil: `COPY . .`
install'dan **SONRA** geliyor, yani host'un `node_modules`'ü image'inkinin **üstüne**
biner ve `npm ci`'yi süs hâline getirir. Bu ADIM 32'de yerel image build'inde bizzat
yaşandı. Dosya olmadan yukarıdaki `npm ci` **uygulanabilir değildir**.

**Ürün kodu değişmedi.** Route, react-query key, OCC token (`If-Match` / `expected_*`),
Idempotency-Key, hook, SSE taksonomisi, `lib/*.ts` — hiçbiri. Migration yok, alembic head
değişmedi, `ENGINE_VERSION` değişmedi.

---

## 3. Düzeltmenin gerçekten ısırdığının kanıtı — iki negatif, her biri kontrolüyle

Bir kapının yeşil olması onu kapı yapmaz. Her negatif durum, **eski davranışın aynı girdi
altında ne yaptığını gösteren bir kontrolle** birlikte ölçüldü (`p9f1_negative_cases.txt`):

| Durum | Sevk edilen | Kontrol (eski hâl) |
|---|---|---|
| **Lockfile YOK** | `docker build` **exit 1** — `"/package-lock.json": not found`, COPY katmanında durur | glob **exit 0** — hiçbir şey eşleşmedi, hiçbir şey söylenmedi, build lockfile'sız devam etti |
| **`package.json` lockfile'da olmayan bir bağımlılık bildiriyor** (`left-pad@^1.3.0`) | `docker build` **exit 1** — `npm error EUSAGE … Missing: left-pad@1.3.0 from lock file` | `npm install` **exit 0** — sessizce uzlaştırdı ve **lockfile'ı yeniden yazdı** (`a8979c98…` → `3d8c1b66…`) |

`.dockerignore` de aynı biçimde kontrollü ölçüldü (`p9f1_dockerignore.txt`): bir
geliştirici ağacı taklit edildi (`node_modules/POISONED`, `dist/STALE.txt`,
`e2e/node_modules`, `VITE_API_BASE_URL=http://evil.example/api` içeren `.env`,
`public/mockup_v18.html`). Dosya varken **beşi de dışarıda**; dosya kaldırıldığında
**beşi de içeri sızıyor**.

> `public/mockup_v18.html` satırı bu ölçüm sırasında **bulunan** bir kusuru kapatıyor:
> Vite `public/`'i olduğu gibi `dist/`'e kopyalar, dolayısıyla CLAUDE.md'nin tarif ettiği
> dev-only kopyayı yapmış bir geliştirici, v18 spec mockup'ını **production image'ına**
> sevk ediyor ve nginx onu `/mockup_v18.html` adresinden sunuyordu. Raporun P9-F1
> satırında bu yoktu.

---

## 4. Kırılmadığı doğrulanan şeyler

| Kontrol | Sonuç | Ham kanıt |
|---|---|---|
| Image gerçekten kuruluyor mu? | `docker build --no-cache` **exit 0**, **84 MB** (2026-08-07 RC ölçümü de 84 MB) | `p9f1_image_and_csp.txt` |
| Sevk edilen bundle referansla aynı mı? | `index-3Ltp7ple.js`, `index-XKVdEXBv.css`, `favicon.svg`, `index.html` — **dördü de** host'ta `npm ci` ile üretilenle bit-bit aynı | `p9f1_image_and_csp.txt` |
| Zehirli host ağacı image'a sızdı mı? | **Hayır** — bu build'in context'inde zehir **duruyordu**; `/usr/share/nginx/html` içinde ne `STALE.txt` ne `mockup_v18.html` var | `p9f1_image_and_csp.txt` |
| ADIM 32'nin CSP kapısı hâlâ geçiyor mu? | **Evet** — canlı konteynerde `/` ve hash'li bundle'da **10/10 PASS** (exit 0) | `p9f1_image_and_csp.txt` |
| O kapı hâlâ *kapı* mı? | **Evet** — yanlış `connect-src` origin'i iddia edildiğinde **exit 1**, ve CSP karşılaştırmasında kırmızı | `p9f1_image_and_csp.txt` |

---

## 5. Dürüst sınırlar

- **Frontend test suite bu dalgada KOŞULMADI.** `src/` altında tek dosya değişmedi;
  değişen yüzey build tesisatıdır ve o, yukarıdaki image build'i + bundle hash
  karşılaştırması ile doğrulandı. Bu bir gerekçedir, bir ölçüm değil — suite'in yeşil
  olduğunu bu belge **iddia etmiyor**; otorite CI'dır.
- **`npm ci` build süresini kısaltmaz.** RC 2026-08-07 ölçümünde image build'i 588,9 s
  sürüyordu ve `npm ci` onun 579,1 s'iydi; bu dalga o profili değiştirmedi.
- **Bu değişiklik bir tedarik-zinciri savunması değildir.** Lockfile'a *sadakati* zorlar;
  lockfile'ın kendi içeriğini denetlemez. `npm audit`'in bildirdiği 3 high-severity
  bulgusu bu dalgada **ele alınmadı** — bağımlılık yükseltmek ayrı bir karardır.
- **`e2e/` bütün olarak dışlandı**, istenen üç alt yolun (`e2e/node_modules`,
  `e2e/test-results`, `e2e/a11y-report`) her biri ayrı ayrı değil. Gerekçe: `e2e/` kendi
  `package.json`/lockfile'ı olan bağımsız bir Playwright paketidir ve `npm run build` onu
  hiç okumaz (`tsconfig.json` yalnız `"src"` içerir). İstenen üçü de bu kapsamın içinde
  kalır; ek olarak 142 commit'li screenshot baseline'ı da context'ten çıkar. Bu, istenen
  asgari listenin **üstüne** çıkan bilinçli bir karardır.
