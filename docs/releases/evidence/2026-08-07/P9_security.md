<!-- doc-status: current -->
# P9 — Güvenlik kapıları (ADIM 29 / V18 RC verification)

**Tarih:** 2026-08-07 · **Base:** `6cd6172` (`origin/main` ile birebir, `0 / 0`)
**Kapsam:** `pip-audit` + `npm-audit-gate` + `security-allowlist-gate` + `.github/workflows/security.yml`
içindeki her adımın yerelde tekrarı; PR #629'un js-yaml "frozen" kaydının denetimi;
server-side policy / ownership / OCC / idempotency / audit / lifecycle korunumunun test ile kanıtı.
**Kod değişmedi.** Bu slice yalnızca kanıt üretir — hiçbir kaynak, test, lockfile, migration
veya CI dosyasına dokunulmadı. Bulunan düzeltmeler **uygulanmadı**, kaydedildi.

---

## 0. Karar: **BLOCKED**

P9 kuralı: *imzalı risk kabulü olmayan unresolved critical/high → BLOCKED.*

| # | Blocker | Dayanak |
|---|---|---|
| **B1** | `GHSA-5p4m-2wfm-xmqj` (js-yaml, **HIGH**) donduruldu ama **gerekçesi yanlış** — lockfile-only düzeltme **var** ve freeze yazılmadan **7 gün önce** yayımlanmıştı | §3 |
| **B2** | İki dondurulmuş HIGH advisory'nin **hiçbirinde imza yok** — ne adı verilmiş sorumlu, ne ISO tarih, ne son kullanma tarihi | §3.4, §4 |

Her iki blocker da **çözüm gerektirir, kayıt değil**: B1 için `npm audit fix
--package-lock-only` (3 satırlık lockfile diff'i), B2 için ya düzeltme ya da D-10 biçiminde
**imzalı** kalıcı sapma. **İmzalayan verilmediği için bu belge hiçbir sapma kaydı YAZMADI.**

Diğer tüm kapılar (**pip-audit, gitleaks, CodeQL, container scan + allowlist + SBOM,
non-root**) yeşil; server-side yetkilendirme kanıtı **geçti**. BLOCKED kararı **yalnızca**
bu iki frozen advisory'den geliyor.

---

## 1. Base snapshot

| Alan | Değer |
|---|---|
| HEAD | `6cd6172833aecf45186378de1e3aa3afa4e0b458` (`6cd6172`) |
| Başlık | `docs(adim-29): record the P4 migration and schema proof (#635)` |
| `origin/main` | aynı sha (`git rev-list --left-right --count HEAD...origin/main` → `0 0`) |
| Çalışma ağacı | temiz |
| CI **Security** workflow, **aynı sha** üzerinde | run `31190284830` → **success**, 4/4 job |

CI job sonuçları (`headSha = 6cd6172…`): `CodeQL — python` ✅ ·
`CodeQL — javascript-typescript` ✅ · `Secret scan (gitleaks)` ✅ ·
`Container scan + SBOM` ✅. Bu, kanıtlanan ağacın **birebir kendisidir** — başka bir
commit'ten devralınmış yeşil değil.

---

## 2. Kapılar

Her kapının çıktısı ayrı dosyaya yazıldı; exit code **ayrı** okundu (`| tail` kullanılmadı —
pipe exit code'u gizler).

| # | Kapı | Komut | Exit | Sonuç |
|---|---|---|---|---|
| G1 | Python bağımlılık denetimi (CI ile birebir) | `cd backend && uv run --with pip-audit pip-audit` | **0** | `No known vulnerabilities found` |
| G2 | Aynısı **dev extra dahil** (CI'ın ötesinde) | `uv run --extra dev --with pip-audit pip-audit` | **0** | `No known vulnerabilities found` (venv'de 79 dağıtım) |
| G3 | npm advisory kapısı | `node scripts/npm-audit-gate.mjs frontend frontend/e2e` | **0** | `OK — no unrecorded high/critical advisories` — **ama 2 HIGH "frozen" olarak geçiyor**, §3–§4 |
| G4 | Allowlist kapısı, argümansız | `node scripts/security-allowlist-gate.mjs` | 1 | `usage: …` — argüman zorunlu; **kapı hatası değil**, CI onu trivy raporlarıyla çağırır |
| G5 | Allowlist kapısı, trivy raporlarıyla | `… container:backend=… container:frontend=…` | **0** (CI) | `OK — 0 fixable CRITICAL/HIGH finding(s), all accounted for.` · allowlist `entries: []` |
| G6 | Secret scan (gitleaks, digest-pinned) | `docker run … gitleaks detect --no-git --config .gitleaks.toml --redact -v` | **0** | **`no leaks found`** — 19.45 MB / 2m22s |
| G7 | Runtime kullanıcı non-root | `docker run --rm --entrypoint id <image> -u` | **0** | backend **uid=10001**, web **uid=101** — CI ile birebir aynı |
| G8 | Trivy image scan (HIGH/CRITICAL, `--ignore-unfixed`) | `docker run … trivy image --input …` | **0** (CI) | fixable HIGH/CRITICAL **yok** (G5 bunu doğruluyor); yerel tekrar → §2.2 |
| G9 | SBOM (CycloneDX ×4) | `trivy image/fs --format cyclonedx` | **0** (CI) | 1202 / 81 / 71 / 13 bileşen; dördü de `bomFormat === "CycloneDX"` |
| G10 | CodeQL (python + javascript-typescript) | — | **0** (CI) | **yerelde koşulamaz** — CodeQL CLI + Action gerekir; aynı sha'da CI ✅ |

### 2.1 Kapılar iki workflow'a dağılmış (kayıt için)

Prompt bunları birlikte listeliyor ama `pip-audit` ve `npm-audit-gate` **`ci.yml`** içinde
(sırasıyla satır 119 ve 168), `security.yml` içinde **değil**. `security.yml` yalnız
CodeQL / gitleaks / container+SBOM+allowlist taşır. Kusur değil — "security.yml'in her adımını
tekrarla" talimatı G6–G10'u kapsar, G1/G3 ayrı workflow'dan gelir.

### 2.2 Dürüst sınır — G8/G9/G5'in **yerel tekrarı YAPILAMADI**

`security.yml`'in container job'ı yerelde **kısmen** tekrarlandı:

| Adım | Yerel | Not |
|---|---|---|
| `Build images` (backend + web) | ✅ | `entropia-backend:scan` 2.09 GB, `entropia-web:scan` 84 MB |
| `Export image filesystems` (`docker save`) | ✅ | iki tar üretildi |
| `Verify runtime users are non-root` | ✅ **exit 0** | backend **uid=10001**, web **uid=101** — CI ile birebir |
| `Trivy — backend/frontend image` | ❌ **tamamlanamadı** | aşağıya bak |
| `Vulnerability allowlist gate` (trivy raporlarıyla) | ❌ | girdi raporları üretilemedi |
| `Generate SBOMs` | ❌ | aynı sebep |

**Sebep — repo değil, bu makinedeki Docker.** Sırasıyla:

1. İlk tarama **FATAL** verdi:
   `failed to analyze file: …/pyarrow/libarrow_python.so: semaphore acquire: context deadline
   exceeded` (varsayılan 5 dk penceresi).
2. `--timeout 45m` ile yeniden denendi → **~40 dk boyunca tek bayt çıktı yok**, rapor dosyası
   0 bayt kaldı.
3. `trivy image --download-db-only` → **çıktı yok**.
4. Aynı imajdan düz bir ağ probu (`wget -T 20 https://ghcr.io/v2/`) → **2 dk+ askıda**.
5. Askıdaki konteynerleri toplamak için verilen `docker kill` **2 dk sonra timeout** oldu.

Yani trivy zafiyet veritabanını çekemiyor ve Docker daemon'ı yanıt vermiyor — bu bir **ortam
arızasıdır**, bir tarama bulgusu değil.

**Otorite CI'dır** ve CI **tam olarak bu sha'da** (`6cd6172`), aynı **digest-pinned** trivy
imajıyla (`aquasec/trivy@sha256:7cced7ca…`) her iki image'i taramış, allowlist kapısını
`OK — 0 fixable CRITICAL/HIGH finding(s), all accounted for.` ile geçmiş ve dört CycloneDX
SBOM'unu (1202 / 81 / 71 / 13 bileşen) üretmiştir. **Bu belge G5/G8/G9 için yerel yeşil iddia
ETMEZ** — CI sonucunu, üzerinde koştuğu sha adlandırılarak aktarır.

### 2.3 G1/G2 hakkında dürüst sınır

`pip-audit` **ortamı** denetler, projeyi değil: `entropia` paketinin kendisi
`Dependency not found on PyPI and could not be audited` ile **atlanır** (yerel paket, PyPI'da
yok — beklenen). G1 çalışma zamanı bağımlılıklarını (46 dağıtım), G2 dev extra dahil **79
dağıtımı** kapsar. "No known vulnerabilities" satırı bu kapsamla okunmalı — ürün kodunun
kendisi hakkında bir şey söylemez, onu CodeQL söyler.

---

## 3. B1 — js-yaml `!!omap` freeze'inin (PR #629) denetimi

**Soru (verbatim):** *"js-yaml omap advisory'sinin 'frozen' kaydını (PR #629) doğrula — hâlâ
geçerli mi, kapsamı ne, imzası var mı? İmzasız donduruluyorsa bu bir blocker'dır."*

Kayıt: `scripts/npm-audit-gate.mjs::FROZEN_ADVISORIES.frontend[1]`, PR **#629**
(`security(deps): record the js-yaml omap advisory as frozen`), merge commit `81336e1`,
**merged 2026-08-07T06:53:23Z**, 1 dosya +6/−0.

### 3.1 Kapsam iddiaları — **hepsi DOĞRU** (ampirik teyit)

| İddia | Doğrulama | Sonuç |
|---|---|---|
| Erişim zinciri `eslint@9 → @eslint/eslintrc → js-yaml@4.3.0` | lockfile: tek kurulum yeri `node_modules/js-yaml` **4.3.0**; tek bildiren `@eslint/eslintrc` (`js-yaml: ^4.3.0`) | ✅ |
| js-yaml bir **devDependency** | lockfile `dev=true`; `eslint` `frontend/package.json` **devDependencies** altında | ✅ |
| Sevk edilen bundle'a girmez | `frontend/src` içinde **hiçbir** `yaml` import'u yok; Vite yalnız import edileni bundle'lar | ✅ |
| Repoda **hiçbir türde `.eslintrc`** yok | `git ls-files \| grep eslintrc` → **boş** · `find . -name '.eslintrc*'` (node_modules hariç, **untracked dahil**) → **boş** · tek config `frontend/eslint.config.js` (flat) | ✅ |

**Risk argümanı sağlam:** açık kod eslintrc'nin YAML **config yükleyicisidir** ve bu repoda
ona verilecek bir YAML belgesi — saldırgan kontrollü ya da değil — yoktur.

### 3.2 Düzeltilebilirlik iddiası — **YANLIŞ**

Kaydın literali:

> "`npm audit fix` offers no lockfile-only remedy; the published fix path is eslint@10, a
> major upgrade…"

Ampirik (`npm audit --json`, `frontend/`):

```
--- js-yaml
  severity: high | range: 4.0.0 - 4.3.0 | fixAvailable: true
  advisory: GHSA-5p4m-2wfm-xmqj | vulnerable: >=4.0.0 <4.3.1
```

`fixAvailable: **true**` — düz boolean, yani **breaking olmayan** düzeltme (react-router'ın
aynı alandaki değeri `{"isSemVerMajor": true}` nesnesi; fark bilerek anlamlı).
`@eslint/eslintrc` js-yaml'ı **`^4.3.0`** olarak bildirir; **4.3.1 bu aralığı karşılar.**

**Kanıt** (scratch kopya, repo'ya dokunulmadı — [`p9_jsyaml_fix_proof.txt`](p9_jsyaml_fix_proof.txt)):

```
npm audit fix --package-lock-only        # /tmp/p9_lockfix_a = frontend/package*.json kopyası
→ js-yaml 4.3.0 → 4.3.1
→ lockfile diff: 3 satır (version / resolved / integrity)
→ package.json: BYTE-IDENTICAL  (diff -q → IDENTICAL)
→ kalan advisory: 3 high → 2 high  (yalnız react-router zinciri)
```

**Zamanlama — kayıt yazıldığı gün zaten yanlıştı:**

| Olay | Zaman (UTC) |
|---|---|
| js-yaml **4.3.1** (yamalı sürüm) npm'de yayımlandı | **2026-07-31T17:39:51Z** |
| PR #629 freeze'i merge edildi | **2026-08-07T06:53:23Z** |

Yamalı sürüm freeze'den **7 gün önce** yayındaydı. Kayıt "süresi dolmuş" değil — **doğduğunda
yanlıştı**. Olası mekanizma: `npm audit` özetinin altındaki *"To address all issues (including
breaking changes), run `npm audit fix --force`"* satırı **global**'dir ve react-router'dan
gelir; js-yaml satırına ait değildir. Advisory başına `fixAvailable` alanı ikisini ayırır.

### 3.3 Kaydın kendi doktrini bunu zaten yasaklıyor

`npm-audit-gate.mjs`'in kendi yorumu (satır 28–34), iki brace-expansion freeze'inin
**2026-08-03'te düşürülmesini** anlatırken aynı kusuru tarif ediyor:

> "A freeze whose reason has expired is worse than no freeze — it silently grants an exception
> nobody re-examined."

Bir önceki commit `e288d3a` (`chore(deps): clear six new frontend advisories and drop two
expired freezes`) bu emsalin ta kendisi. **js-yaml aynı sınıfa girer ve aynı işlem
uygulanmalıdır: dondurmak değil, düzeltmek.**

### 3.4 İmza — **YOK**

| Alan | `FROZEN_ADVISORIES` girdisi | `.github/security-allowlist.json` şartı |
|---|---|---|
| `id` | ✅ | zorunlu |
| paket | ✅ (`pkg`) | zorunlu (`package`) |
| gerekçe | ✅ (`reason`) | zorunlu (`justification`) |
| **adı verilmiş sorumlu (`owner`)** | ❌ **yok** | **zorunlu** — "the human accountable for revisiting it, **not a team alias**" |
| **son kullanma (`expires`)** | ❌ **yok** | **zorunlu**; `security-allowlist-gate.mjs` tarih geçince **build'i kırar** (`MAX_EXCEPTION_DAYS = 90`) |
| **ISO imza tarihi** | ❌ **yok** | — |

Bu asimetriyi repo **kendisi** yazmış (`security-allowlist-gate.mjs` başlığı):

> "This is the part the two older gates in this repo (`npm-audit-gate.mjs`'s
> `FROZEN_ADVISORIES`, the a11y scan's `ACCEPTED_SERIOUS_RULES`) do not have: their freezes
> expire only when a human happens to notice. Here the calendar notices."

PR #629 gövdesinde de imza yok: reachability / shipped / input / fixable tablosu ve iki
**niteliksel** RE-CHECK koşulu var, ama repo'nun kendi D-10 biçimindeki **adı verilmiş
imzalayan + ISO tarih + kapsam** üçlüsü (`docs/ADIM29_LANDED_KICKOFF.md:40`) yok.
Commit author'ı bir imza değildir.

**Sonuç:** freeze **imzasızdır** → prompt'un kuralı gereği **blocker**. B1 ayrıca gerekçesi
yanlış olduğu için **iki bağımsız gerekçeyle** blocker'dır.

---

## 4. B2 — react-router freeze'i (aynı listenin ilk girdisi)

`GHSA-qwww-vcr4-c8h2` — *React Router: RSC Mode CSRF Bypass Allows Action Execution Before
400 Response*, **HIGH**.

| Boyut | Bulgu |
|---|---|
| **Sevk ediliyor mu?** | **EVET** — lockfile `react-router` 7.18.2 **`dev=false`**. js-yaml'ın aksine bu paket bundle'a **girer**; freeze'in gerekçesi "erişilemez" değil, "**bu mod hiç açılmıyor**" |
| Risk argümanı | **geçerli** — uygulama `BrowserRouter` kullanıyor (`frontend/src/main.tsx:22`); `frontend/src` içinde **hiçbir** RSC API'si yok |
| npm'in sunduğu tek düzeltme | `react-router-dom@7.11.0`'a **downgrade**, `isSemVerMajor: true` — yani lockfile-only çare gerçekten **yok** |
| **Bayat olgu 1** | Kayıt "the only patched line is react-router@**8.2.1+**" diyor; advisory aralığı `>=7.12.0 **<8.3.0**` → yamalı hat **8.3.0+** |
| **Bayat olgu 2** | Kayıt "react-router-dom@**7.18.1** pins react-router@**7.18.1** exactly" diyor; gerçek **7.18.2 → 7.18.2**. Yapısal iddia (birebir pin) **doğru**, sürümler bayat |
| **İmza** | ❌ **yok** — `owner` yok, `expires` yok, ISO tarih yok |

B1'den farkı: gerekçesi **maddeten ayakta**, düzeltme gerçekten major. Ama **imzasız** olduğu
için P9 kuralının kapsamındadır; iki bayat sürüm olgusu da düzeltilmelidir.

> **Not — G3'teki sayı farkı gizlenmiş bulgu değil.** `npm-audit-gate.mjs` advisory **id**'sine
> göre tekilleştirir, npm `metadata` ise **paket** sayar. Bu yüzden `high=3` ama listelenen
> advisory **2**: `react-router` ve `react-router-dom` aynı GHSA'yı taşır. Kapı doğru
> davranıyor; fark raporlama biçimidir.

---

## 5. Server-side policy — "UI hidden/disabled authorization DEĞİLDİR" kanıtı

**İstenen:** *"UI hidden/disabled'ın authorization SAYILMADIĞINI en az bir uçta test ile
kanıtla."* Aşağıda **iki katman**, **iki test**, **altı uç**.

### 5.1 Önce: UI gerçekten gizliyor (yani iddia boş değil)

`frontend/src/pages/Trash.tsx:350` — `isAdmin` yanlışsa **Restore** ve **Permanent Delete**
düğmeleri **hiç render edilmez**; yerlerine `role="note"` taşıyan *"Admin approval required"*
metni gelir (`components/AdminGate.tsx::useIsAdmin` / `AdminApprovalNote`). Bu tam olarak
"düğme yok → güvenli sanılabilir" yüzeyidir.

### 5.2 Route katmanı — UI hiç devrede değilken **403**

`backend/src/entropia/apps/api/routes/trash.py` modül docstring'i kuralı **yazılı** taşıyor:

> "every Trash surface (list/detail/restore/purge) requires an authenticated human Admin at
> the ROUTE and again inside the service (`require_trash_admin` — **UI hide/disable is never
> authorization**, doc 20 §2)."

**Test:** `backend/tests/contract/test_identity_and_gating.py::test_admin_routes_reject_normal_user`
— `Role.USER` aktörü **ham ASGI isteği** gönderir: tarayıcı yok, React yok, düğme yok.

| Method | Path | Beklenen kod |
|---|---|---|
| GET | `/api/v1/trash-entries` | `TRASH_ACCESS_FORBIDDEN` |
| GET | `/api/v1/trash-entries/trash_x` | `TRASH_ACCESS_FORBIDDEN` |
| POST | `/api/v1/trash-entries/trash_x/restore` | `TRASH_ACCESS_FORBIDDEN` |
| POST | `/api/v1/trash-entries/trash_x/purge` | `TRASH_ACCESS_FORBIDDEN` |
| GET | `/api/v1/audit-events` | `ACCESS_DENIED` |
| POST | `/api/v1/users/user_2/role` | `ACCESS_DENIED` |

Altısı da **403**, hepsinde tipli hata kodu, ve `assert "data" not in resp.json()` — reddedilen
çağırana **hiçbir nesne adı / sayısı / snapshot'ı sızmaz** (doc 20 §15). Purge çağrısı
şema-geçerli gövdeyle yapılır ki 422 doğrulaması değil **403 muhafızı** koşsun.

**Koşu:** `uv run pytest tests/contract/test_identity_and_gating.py tests/contract/test_manual_contract.py -v --no-cov`
→ **28 passed**, exit **0** ([`p9_authz_contract.txt`](p9_authz_contract.txt)).

### 5.3 Servis katmanı — route bile atlansa **403**

`require_trash_admin` **iki kez** uygulanır: route'ta **5** çağrı yeri + application katmanında
**7** (`queries/trash.py` ×3, `commands/deletion.py` ×3, `commands/manual.py` ×1).

**Test:** `backend/tests/integration/test_trash_page.py::test_trash_surfaces_reject_non_admin[user|agent]`
— komut/sorgu fonksiyonlarını **doğrudan** çağırır (HTTP katmanı tamamen devre dışı), `USER`
**ve** `AGENT` aktörleriyle; dördü de `TrashAccessForbiddenError` fırlatır. Testin kendi notu
sırayı da pinliyor: `reauth_proof="irrelevant",  # role check runs before any proof lookup` —
yani rol kontrolü herhangi bir kanıt aramasından **önce** koşar.

**Koşu:** izole DB (`TEST_DATABASE_URL=postgresql+asyncpg://…/entropia_p9_authz`),
`uv run pytest tests/integration/test_trash_page.py -v --no-cov`
→ **19 passed**, exit **0**, 1089.02s ([`p9_authz_service.txt`](p9_authz_service.txt)).

### 5.4 UI-only gating var mı? — **hayır**

`frontend/src/app/nav.ts` içindeki **her** `adminOnly` hedefin sunucu tarafında muhafızı var:

| adminOnly rota | Backend route modülü | Route katmanı `require_*` |
|---|---|---|
| `/panel/management`, `/panel/logs` | `routes/admin_panel.py` | **9** |
| `/panel/metrics` | `routes/metrics.py` | **1** |
| `/trash` | `routes/trash.py` | **5** |

Route katmanında 0 `require_*` gösteren modüller **korumasız değil** — sahiplik application
katmanında uygulanır (`ensure_can_edit` **20**, `ensure_can_view` **31** çağrı yeri).
Örnek ampirik olarak doğrulandı: `commands/strategy_draft.py` içinde `require_authenticated`
(×3) + `ensure_can_edit` (×3) + `ensure_can_view` (×2).

**Toplam:** `require_*` → route katmanı **28** çağrı / **15** dosya; application katmanı
**251** çağrı / **54** dosya. Yetki kararı hiçbir yerde tek katmana bırakılmamış.

### 5.5 OCC / idempotency / audit / lifecycle / hardening

| Değişmez | Tek kural yeri | Çağrı yeri | Koşu |
|---|---|---|---|
| OCC dual-token | `shared/concurrency.py::reconcile_occ_tokens` | **12** (route katmanı) | `test_occ_dual_token_contract.py` ✅ |
| Idempotency-Key | `application/idempotency.py::run_idempotent` | **97** | — |
| Audit + outbox (tek tx) | `_audit_and_outbox` | **93** | — |
| HTTP hardening | `apps/api/hardening.py::SecurityHeadersMiddleware` | `nosniff` / `X-Frame-Options: DENY` / `Referrer-Policy` / `CSP: default-src 'none'` (+ prod'da HSTS) | `test_hardening_contract.py` ✅ |
| CORS | `apps/api/main.py:131` | `allow_origins=settings.cors_origin_list`, `allow_credentials=True` — wildcard **kapalı** | `test_cors_contract.py` ✅ |
| Lifecycle / deletion | `commands/deletion.py` + `jobs/purge.py` + `queries/trash.py` | §5.3 koşusu 19/19 | ✅ |

**Koşu:** `pytest tests/contract/{test_occ_dual_token_contract,test_hardening_contract,test_cors_contract,test_error_envelope_contract,test_sse_auth_contract,test_auth_mode_login_gate}.py -v --no-cov`
→ **76 passed, 1 failed**, exit 1.

> **Bu 1 failure bir ürün kusuru DEĞİL — benim dosya seçimimin ölçüm artefaktıdır.**
> `test_auth_mode_login_gate.py::test_session_mode_login_reaches_the_credential_check`
> `RuntimeError: … Future … attached to a different loop` ile düştü: paylaşılan async engine
> havuzu önceki testin (function-scope) event loop'una bağlı kalmıştı.
> **Aynı dosya tek başına koşuldu → 3 passed, exit 0**
> ([`p9_login_gate_isolated.txt`](p9_login_gate_isolated.txt)). CI'ın tam-suite sırasında
> yeşil. Kayda geçirildi çünkü ölçüm **kaydedilir, gizlenmez**.

---

## 6. Blocker olmayan bulgular (düzeltilmedi, kaydedildi)

| # | Bulgu | Neden blocker değil |
|---|---|---|
| **F-1** | `frontend/Dockerfile` **`RUN npm install`** kullanıyor, `npm ci` değil. Bugün lockfile'a uydu (image build'i de aynı `3 high severity vulnerabilities` özetini bastı → sapma yok), ama `npm install` package.json ↔ lockfile ayrışmasını **sessizce uzlaştırır**, kırmaz. Ayrıca `COPY package.json package-lock.json* ./` glob'u lockfile'ın **yokluğunu** tolere eder — o durumda çözünürlük tamamen serbest kalır. | Bugün fiilî ayrışma yok; reproducibility riski, açık bir güvenlik açığı değil |
| **F-2** | **SPA origin'inde CSP yok.** `frontend/nginx-security-headers.conf` `nosniff` / `X-Frame-Options: DENY` / `Referrer-Policy` / `Permissions-Policy` veriyor ama **`Content-Security-Policy` vermiyor** — ve yürütülebilir bundle'ı sunan origin **budur**. API'de CSP var (`default-src 'none'`) ve `test_hardening_contract.py:29` onu pinliyor; **statik origin için hiçbir test, hiçbir kapı, hiçbir belge yok** (`grep -r "Content-Security-Policy" docs/ frontend/` → boş). | Hiçbir kapı bunu iddia etmiyor, dolayısıyla bir kapı ihlali değil; ama **kayıtsız** bir boşluktu — artık kayıtlı |
| **F-3** | `pip-audit` yerel `entropia` paketini denetleyemez (PyPI'da yok) | Beklenen davranış; "no known vulnerabilities" satırının kapsamı §2.3'te yazıldı |

---

## 7. Üretilen dosyalar

| Dosya | İçerik |
|---|---|
| [`p9_pip_audit.txt`](p9_pip_audit.txt) | G1 ham çıktısı |
| [`p9_npm_audit_gate.txt`](p9_npm_audit_gate.txt) | G3 ham çıktısı |
| [`p9_gitleaks.txt`](p9_gitleaks.txt) | G6 ham çıktısı |
| [`p9_jsyaml_fix_proof.txt`](p9_jsyaml_fix_proof.txt) | **B1'in kanıtı** — `npm audit --json` düğümleri + `npm audit fix --package-lock-only` çıktısı + 3 satırlık lockfile diff'i + `package.json` birebirliği + 4.3.1 yayın tarihi |
| [`p9_authz_contract.txt`](p9_authz_contract.txt) | §5.2 HTTP-katmanı yetki testi (28 passed) |
| [`p9_authz_service.txt`](p9_authz_service.txt) | §5.3 servis-katmanı yetki testi (19 passed) |
| [`p9_login_gate_isolated.txt`](p9_login_gate_isolated.txt) | §5.5'teki tek failure'ın izole yeniden koşusu (3 passed) |
| [`p9_container_gates.txt`](p9_container_gates.txt) | G7 yerel çıktısı + G5/G8/G9'un yerelde neden tamamlanamadığının dört denemelik kaydı ve CI otoritesi |
| `P9_security.md` | bu dosya |

---

## 8. P9 sonucu

**On kapıdan dokuzu yeşil; onuncusu (G3) yeşil ama iki HIGH advisory'yi imzasız bir freeze ile
geçiriyor.** Server-side yetkilendirme kanıtı **geçti**: UI'ın gizlediği her Admin eylemi
sunucu tarafında **iki katmanda** reddediliyor; bu iki ayrı testle, **altı uçta**, hem HTTP
hem servis seviyesinde kanıtlandı (28 + 19 passed) ve `adminOnly` navigasyon hedeflerinin
hiçbirinde UI-only kapı bulunmadı.

**P9 BLOCKED** — sebep tek başına B1 + B2. Kapanması için gereken **insan kararı**:

* **(A) Düzelt — B1 için tek doğru yol.** `frontend/` içinde `npm audit fix
  --package-lock-only`, ardından js-yaml girdisini `FROZEN_ADVISORIES`'ten **düşür**.
  Değişiklik 3 satırlık lockfile diff'i; `package.json` değişmiyor; major upgrade yok.
  Bu, repo'nun 2026-08-03'te brace-expansion için yaptığının aynısıdır.
* **(B) İmzala — react-router için tek gerçekçi yol.** D-10 biçiminde: **adı verilmiş
  imzalayan + ISO tarih + kapsam**; tercihen kaydı `.github/security-allowlist.json`
  disiplinine taşı (`owner` + `expires`, takvimin hatırladığı yer). Bu arada iki bayat sürüm
  olgusu (8.2.1+ → **8.3.0+**, 7.18.1 → **7.18.2**) düzeltilmeli.
  **İmzalayan verilmediği için bu belge böyle bir kayıt YAZMADI.**

Hiçbirini agent yapamaz: (A) lockfile'ı değiştirir ve P-adımları kod/lockfile değiştirmez;
(B) imza gerektirir ve imza yetkisi insandadır. Bu belge **çözmedi — ölçtü ve kaydetti**.
