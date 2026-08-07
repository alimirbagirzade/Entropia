<!-- doc-status: current -->
# P9-B1 — js-yaml freeze'i düşürüldü, advisory lockfile ile kapatıldı

**Tarih:** 2026-08-07 · **Base:** `169cfaa` (`origin/main` HEAD)
**Tip:** Bu bir **P adımı değil** — P9'un B1 blocker'ının **düzeltmesi**. P1/P3/P4/P9
kanıt slice'larının aksine burada **kod ve lockfile DEĞİŞTİ**.

**Değişen iki dosya:**
- `frontend/package-lock.json` — js-yaml `4.3.0` → `4.3.1` (3 satır)
- `scripts/npm-audit-gate.mjs` — `FROZEN_ADVISORIES.frontend`'den js-yaml girdisi **düşürüldü**;
  react-router girdisinin **iki bayat olgusu düzeltildi**

---

## 1. Neden düşürüldü — freeze'in gerekçesi doğduğunda yanlıştı

PR #629'un yazdığı gerekçe şunu iddia ediyordu:

> "`npm audit fix` offers no lockfile-only remedy; the published fix path is eslint@10,
> a major upgrade"

Bu iddia **freeze merge edildiğinde zaten yanlıştı**:

| Olay | Tarih |
|---|---|
| js-yaml `4.3.0` yayımlandı | 2026-06-26 |
| **js-yaml `4.3.1` yayımlandı (advisory'yi yamalıyor)** | **2026-07-31** |
| #629 freeze'i merge edildi | 2026-08-07 |

Yani lockfile-only düzeltme, freeze yazılmadan **yedi gün önce** raftaydı.
Kanıt: `p9_jsyaml_fix_proof.txt` §5 (npm registry timestamps).

Bu, `npm-audit-gate.mjs`'in **kendi yorumunun** (satır 28–34) 2026-08-03'te
brace-expansion çifti için uyguladığı desenin aynısı:

> "A freeze whose reason has expired is worse than no freeze — it silently
> grants an exception nobody re-examined."

---

## 2. Uygulanan düzeltme

```
$ cd frontend && npm audit fix --package-lock-only
```

Lockfile diff — **tam olarak 3 satır**, `p9_jsyaml_fix_proof.txt` §3'ün öngördüğü ile birebir:

```diff
     "node_modules/js-yaml": {
-      "version": "4.3.0",
-      "resolved": "https://registry.npmjs.org/js-yaml/-/js-yaml-4.3.0.tgz",
-      "integrity": "sha512-1td788aAnnZ5qs7V2QIRl1owjtYpbKt749Y3xauqQgwIIGF/xXWz1wMTEBx5O3LK3lXLVuqXPdPxj2BoFHaW9Q==",
+      "version": "4.3.1",
+      "resolved": "https://registry.npmjs.org/js-yaml/-/js-yaml-4.3.1.tgz",
+      "integrity": "sha512-CY6crGq313MX8GkwvB7tzgp99vjQxY1++5y10/BKN/GUfHqWaOGQMNZkBvqSzsZKWk/ijwHlWzzkLulsGHhjWQ==",
       "dev": true,
```

`frontend/package.json` **byte-identical** — `git status` onu hiç kirletmedi.
(`package-lock.json` `.gitattributes`'ta `-diff` işaretli, bu yüzden git onu binary
gösterir; yukarıdaki diff `git diff --text` ile alındı.)

---

## 3. Doğrulama

| # | Kapı | Komut | Exit | Sonuç |
|---|---|---|---|---|
| V1 | npm advisory kapısı | `node scripts/npm-audit-gate.mjs frontend frontend/e2e` | **0** | `OK — no unrecorded high/critical advisories`; **tek** frozen kayıt kaldı: react-router |
| V2 | temiz kurulum | `npm ci` | **0** | `node_modules/js-yaml` = **4.3.1** |
| V3 | lint (js-yaml'ın gerçek tüketicisi) | `npm run lint` | **0** | eslint@9 flat-config sorunsuz koştu |
| V4 | typecheck | `npm run typecheck` | **0** | — |
| V5 | build | `npm run build` | **0** | `✓ built in 1.38s` |
| V6 | test | `npm test -- --no-file-parallelism` | **0** | **721 passed / 70 dosya** — kayıtlı baseline ile birebir |

V3 kritik: js-yaml bu ağaca **yalnızca** `eslint@9 → @eslint/eslintrc → js-yaml`
yolundan giriyor. eslint'in kendisi yeşil koştuğuna göre patch bump'ı kırmadı.

Kapının V1 çıktısı:

```
frontend: high=2 critical=0 (moderate=0 low=0)
  frozen   GHSA-qwww-vcr4-c8h2 high react-router — RSC Mode CSRF Bypass ...

frontend/e2e: high=0 critical=0 (moderate=0 low=0)

OK — no unrecorded high/critical advisories.
```

`high=2`, `high=1` değil: advisory **id** tektir ama `react-router` ve
`react-router-dom` **iki ayrı paket düğümü** olarak sayılır. Düzeltme öncesi bu sayı
**3**'tü (js-yaml + ikili). "frozen but no longer reported" notu **çıkmıyor** —
yani liste artık dürüst.

---

## 4. B2 — **DÜZELTİLMEDİ, insan işi olarak duruyor**

`GHSA-qwww-vcr4-c8h2` (react-router) freeze'i **imzasız** kalmaya devam ediyor.
Bu slice onu **kapatmadı**; yalnızca **iki bayat olgusunu** düzeltti:

| İddia | Kayıtlı (yanlış) | Doğrulanan |
|---|---|---|
| react-router-dom pin | `7.18.1` → `react-router@7.18.1` | **`7.18.2` → `react-router@7.18.2`** (exact pin) |
| yamalı hat | `8.2.1+` | **`8.3.0+`** (advisory aralığı `>=7.12.0 <8.3.0`) |

Doğrulama: kurulu ağaç (`node_modules/*/package.json`) + canlı `npm audit --json`.

Freeze'in **özü ayakta**: 7.18.2 gerçekten 7.18.2'yi exact pinliyor ve tüm 7.x
etkilenmiş durumda, dolayısıyla lockfile-only düzeltme **yok** — `npm audit fix --force`
yalnızca `react-router-dom@7.11.0`'a **downgrade** öneriyor (breaking change).
Yanlış olan sadece sürüm numaralarıydı.

**Yapılmayan ve agent'ın yapamayacağı iş:** kaydı `.github/security-allowlist.json`
disiplinine taşımak. O dosya **zorunlu `owner`** istiyor —
*"the human accountable for revisiting it, not a team alias"* — ve `expires` tarihi
geçtiğinde build'i kırıyor. **İmzalayan verilmediği için hiçbir sapma kaydı YAZILMADI.**
Uydurulmuş bir `owner` kaydın tüm amacını yok ederdi. B2 **AÇIK**.

---

## 5. Dürüst sınır — bu slice neyi kanıtlamıyor

- **CI otoritedir, yerel değil.** Yukarıdaki altı kapı bu worktree'de koştu.
  Container/trivy kapıları **koşturulmadı** (P9'da yerel Docker daemon'ı yanıt
  vermeyi bırakmıştı) — onlar için CI'daki koşu otoritedir.
- Backend suite bu slice'ta **koşturulmadı**: değişen iki dosyanın ikisi de
  frontend/npm yüzeyinde, backend'e hiçbir import yolu yok
  (`scripts/npm-audit-gate.mjs`'i **hiçbir dosya import etmiyor**; tek çağıran
  `.github/workflows/ci.yml:168`, CLI olarak).
