<!-- doc-status: current -->
# Entropia V18 — Release Candidate Readiness Report

**Candidate SHA:** `1f4b88b7370dd73929d068175885c05f65fd3b9a` (`1f4b88b`)
**Candidate commit:** `docs(a08): reconcile the record with #514 being closed unaudited (#631)` · 2026-08-07 14:36:32 +0300
**Rapor tarihi:** 2026-08-07 · **Dalga:** ADIM 29 / P1–P13 (V18 RC verification)
**Kaynak:** `docs/releases/evidence/2026-08-07/` — 13 kanıt belgesi + 34 ham çıktı dosyası

> **FINAL VERDICT: BLOCKED** — **İKİ** bağımsız eksende kapatılmamış blocker var
> (A-08 insan kabul denetimi koşulmadı ve imzalı sapması yok · P5/P6'nın kabul akışları
> koştu ama `flows` bir CI kapısı değil); imzalı sapma D-10 **yalnız** WCAG 1.4.3
> eksenini kapsar ve bu blocker'ların hiçbirini kapatmaz. Gerekçe: §7.
>
> **2026-08-10 (ADIM 31) — blocker sayısı 4 → 3.** Eski blocker **(3) Alertmanager yok**
> **KAPANDI**: bildirim yolu sevk edildi, fail-closed, ve ateşleyen gerçek bir alarmın bir
> alıcıya ulaştığı uçtan uca ölçüldü (§6.3). Verdict **BLOCKED kalır** — 1, 2 ve 4 açıktır.
>
> **2026-08-12 (ADIM 44) — blocker sayısı 3 → 2.** Eski blocker **(4) react-router HIGH
> advisory'si imzasız dondurulmuş** **KAPANDI** — ve **imzayla değil, KALDIRMAYLA**:
> advisory upstream'de yeniden kapsamlandı (`first_patched` 7.x için **7.18.2**), kurulu
> ağaç **zaten 7.18.2**, `npm audit` **0 vulnerability**. Var olmayan bir açığa imza
> atılmaz; `FROZEN_ADVISORIES` silindi (§6.4). Verdict **BLOCKED kalır** — 1 ve 2 açıktır.
>
> **2026-08-12 (ADIM 45) — blocker sayısı 2 → 1.** Eski blocker **(2) kabul akışları /
> `flows` bir CI kapısı değil** **KAPANDI**: `e2e.yml::acceptance-flows` bağlandı ve
> **gerçekten koştu** (job **94097720164**, **67 passed / 0 failed / 1 skipped**,
> `duration_seconds=137`), maliyet ölçüldü, iki SKIP'ten biri kapandı ve diğeri yapısal
> gerekçeyle kayda geçti (§6.2). Verdict **BLOCKED kalır**.
>
> **Bugün açık olan TEK blocker: (1) A-08 insan kabul denetimi.** Defter hâlâ boştur ve
> imzalı sapması yoktur; takip issue'su **#514 2026-08-12'de bir insan tarafından yeniden
> AÇILDI** (`state=OPEN`, `stateReason=REOPENED`, etiket `human-only`) — kapatma yetkisi
> insandadır, agent kapatamaz. **Bu belge hiçbir yerde `READY` demez.** Blocker 2'nin
> kapanması **P11-1'i (branch protection) kapatmaz**: bir *required status check* kuralı
> olmadan kırmızı bir check merge'i fiilen durduramaz ve bu bir depo ayarı + insan
> kararıdır.
> **2026-08-12 (ADIM 44) — blocker sayısı 3 → 2.** Eski blocker **(4) react-router
> `GHSA-qwww-vcr4-c8h2` imzasız dondurulmuş** **KAPANDI**, ve **imzayla değil,
> kaldırmayla**: advisory upstream'de yeniden kapsamlandırıldı (`first_patched` 7.x hattı
> için **7.18.2**), kurulu ağaç zaten 7.18.2, `npm audit` **0 vulnerability** (§6.4).
> Verdict **BLOCKED kalır** — 1 ve 2 açıktır.

---

## 1. Kapsam ve okuma kuralı

Bu belgedeki **her sayı P1–P12 koşularının kendi çıktılarından** gelir. Hiçbir sayı önceki
PR gövdelerinden, `docs/STAGE2_HANDOFF.md`'den veya `CLAUDE.md` §Current position'dan
kopyalanmamıştır. Bir sayının yanında kaynağı (P adımı + ham dosya) yazılıdır; kaynağı
olmayan bir sayı bu belgede yoktur.

**Bu rapor bir kabul kararı değildir** — ölçülenin ne olduğunu, neyin ölçülmediğini ve
hangi kapıların kapalı olduğunu tek yerde toplar. Kabul/sevk kararı **insan işidir**.

### 1.1 Candidate SHA ile kanıt SHA'ları arasındaki ilişki (bu adımda ölçüldü)

P adımları tek bir ağaç üzerinde değil, `1f4b88b`'ten türeyen bir docs zinciri üzerinde
koştu. Bu ayrışmanın kanıtın geçerliliğini etkileyip etkilemediği ölçüldü:

```
git merge-base --is-ancestor 1f4b88b origin/main   → YES
git diff --stat 1f4b88b origin/main -- backend/src frontend/src backend/alembic \
                                        backend/tests frontend/e2e .github   → BOŞ
```

`1f4b88b` → `e35cf61` (origin/main) arasındaki **14 commit'in tamamı**; değişen dosyalar
yalnızca: `docs/`, `CLAUDE.md`, `frontend/package-lock.json` ve `scripts/npm-audit-gate.mjs`
(ikisi de PR #637, §5.4). **`backend/src`, `frontend/src`, `backend/alembic`,
`backend/tests`, `frontend/e2e` ve `.github` ağaçlarında sıfır değişiklik.**

Sonuç: `1f4b88b`'te ölçülen backend/frontend sayıları (P2, P3, P4) sonraki docs commit'leri
tarafından **geçersizleştirilmemiştir**. Tek istisna P3'ün npm audit gözlemidir (`3 high`);
o gözlem #637 ile **aşılmıştır** → bugün `high=2` (§5.4).

| P adımı | Koştuğu SHA | Candidate ile ilişki |
|---|---|---|
| P1, P2, P3, P4 | `1f4b88b` | **birebir candidate** |
| P12 | `1f24391` (#632) | candidate + docs |
| P5 | `bc59dae` (#634) | candidate + docs |
| P9 | `6cd6172` (#635) | candidate + docs |
| P9-B1 (düzeltme) | `169cfaa` (#636) | candidate + docs → **kod/lockfile değiştirdi** |
| P6, P7 | `6c239e4` (#638) | candidate + docs + #637 |
| P8, P11 | `2cf7283` (#640) | candidate + docs + #637 |
| P10 | `7926490` (#642) | candidate + docs + #637 |

---

## 2. Environment

### 2.1 Yerel doğrulama hostu (P1–P10'un çoğu)

| Alan | Değer | Kaynak |
|---|---|---|
| Platform | `darwin 25.5.0` (arm64) | P3 |
| Python | 3.12.13 (CPython) | P4, P7, P8, P10 |
| pytest | 9.1.1 · pytest-asyncio 1.4.0 (`Mode.AUTO`) | P8 |
| PostgreSQL | 16.14 (Homebrew), `localhost:5432` | P4, P6, P7, P8, P10 |
| alembic | 1.18.5 | P4 |
| Node / npm | v24.15.0 / 11.12.1 | P3 |
| TypeScript / ESLint / Vitest / Vite | 5.9.3 / 9.39.5 / 4.1.10 / 8.2.0 | P3 |
| `LC_ALL` | `en_US.UTF-8` | P4, P7 |
| Docker CLI | 29.4.0 (OrbStack) — daemon durumu adıma göre **değişken**, §6.2 | P5, P8, P10 |
| Load-smoke runner class | `local-darwin-arm64-dev-laptop` — CI baseline'ı ile **karşılaştırılamaz** | P10 |

**İzole test veritabanları** (paralel worktree oturumlarına karşı, hepsi
`postgresql+asyncpg://`): `entropia_v18rc_test` (P2) · `entropia_p4_proof` (P4) ·
`entropia_p6_restore_scratch` (P6) · `entropia_p7_oracle` (P7) · `entropia_p8_test` (P8) ·
`entropia_p9_authz` (P9) · `entropia_p10_test` + `entropia_p10_load` (P10).

### 2.2 CI hostu (P9, P10, P11'in otorite koşuları)

| Alan | Değer | Kaynak |
|---|---|---|
| Runner | `ubuntu-latest` (GitHub-hosted) | P11 |
| Tarayıcı | Chromium, Playwright 1.55.1 (`--with-deps`) | P11 |
| E2E hedefi | Docker Compose stack (API + Postgres + Redis + MinIO + worker), `AUTH_MODE=session` | P11 |
| E2E seed | `SEED_E2E_GOLDEN=1 SEED_ESP_TA=1 SEED_RATIONALE=1` | P11 |
| Alıntılanan CI koşuları | Security `31190284830` (`6cd6172`) · E2E `31212829328` (`2cf7283`) · Performance `31350909899` | P9, P11, P10 |

---

## 3. Kapı kapı kanıt tablosu

Aşağıdaki her satır bir **koşudur**: komut, ölçülen exit code, ve o koşunun ürettiği sayı.
Exit code'lar her adımda `| tail` kullanılmadan, ayrı `$?` okumasıyla alınmıştır.

### P1 — Repository truth (verdict: **PASS**)

| Kapı | Komut | Exit | Ölçülen |
|---|---|---:|---|
| Gate 1 — documentation-truth | `uv run python ../scripts/generate_repository_facts.py --root .. --check` | **0** | `documentation-truth gate OK — artefacts fresh, documents classified, no stale claims.` |
| Gate 2 — OpenAPI drift | `uv run python -m entropia.apps.api.openapi_export --check` | **0** | `OpenAPI snapshot is up to date: docs/openapi.json` |
| Gate 3 — acceptance semantic scan | `uv run python ../docs/audit/acceptance_semantic_scan.py --root .. --report` | **0** | `OK: 383 criteria / 1175 clauses validate against the live test tree` |

**Gate 1'in doğruladığı üretilmiş değerler:** alembic head `0043_i08_registry_strategy_fks`,
43 revision (tek head), 104 tablo, 140 FK, 177 path / 196 HTTP operation, 29 frontend router
path, `ENGINE_VERSION = backtest-engine-v18-gap-adjusted-stop-fill`,
`SHARED_ALLOCATION_STATUS = future_dev`.

**Gate 3 kriter dağılımı (383):** covered 229 · partial **131** · uncovered **8** ·
deliberate_future_dev 8 · not_applicable 7 · product_decision_required 0.
**Clause dağılımı (1175):** covered 971 · partial 10 · uncovered **155** ·
deliberate_future_dev 27 · not_applicable 12.
**Kanıt tipi başına kriter:** backend_integration 317 · backend_unit 131 ·
frontend_component 127 · backend_contract 70 · e2e 16.

**Codemap oku-doğrula:** 5 haritanın 4'ü tam tutarlı; `BACKEND_LAYERS.md` içerik olarak tam
ama iki başlık sayısı bayat (`queries` 37 yazıyor / gerçek **38**; `jobs` 14 yazıyor /
gerçek **16**) — bulgu **P1-B1**. Ayrıca dual-token op sayısında `CLAUDE.md` (**16**) ↔
codemap (**17**) ayrışması; ampirik `reconcile_occ_tokens` çağrı yeri **12** (10 dosya) —
bulgu **P1-B2**.

> **2026-08-11 (ADIM 40) düzeltmesi — ve bu koşunun bir DÜZELTMESİ.** İkisi de kapatıldı
> (§6.7.8). Bu paragrafın *"`BACKEND_LAYERS.md` **içerik olarak tam**"* ifadesi **yanlıştı**:
> `jobs` tablosu 16 modülün yalnız **14'ünü** adlandırıyordu — `delivery.py` ve `heartbeat.py`
> hiç satır almamıştı. Bayat olan yalnız başlık sayısı değil, içeriğin kendisiydi; sayı zaten
> bunu göremez, çünkü sayı yalnız birinin bir kez saydığını kaydeder.

### P2 — Backend lint / type / test / coverage (verdict: **PASS**, 4/4)

| Kapı | Komut | Exit | Ölçülen |
|---|---|---:|---|
| Lint | `uv run ruff check .` | **0** | `All checks passed!` |
| Format | `uv run ruff format --check .` | **0** | `786 files already formatted` |
| Type | `uv run mypy src` | **0** | `Success: no issues found in 396 source files` |
| Test + coverage | `uv run pytest` | **0** | **3966 passed / 0 failed / 0 error / 1 xfailed**, 11 warning, 21 dk 29 sn |

**Coverage: %93,52** (`TOTAL 27113 1756 93.5%`), kapı `--cov-fail-under=90` → **GEÇTİ**.
`failed`/`error` sıfırı ölçümdür: log'da `^FAILED`/`^ERROR` satır sayısı **0**, `= FAILURES =`
/ `= ERRORS =` bölümü yok.

**Bilinçli `xfail(strict)` sayısı = 1**, iki bağımsız yoldan doğrulandı (runtime özet satırı
`1 xfailed`; statik `grep -rn "pytest.mark.xfail" backend/tests/` → **tam 1 eşleşme**).
Tek xfail: `tests/integration/test_research_point_in_time_parity.py:583`
(`test_both_bundles_pin_the_available_time_policy`, GH **#558**). Dinamik xfail yok
(`pytest.xfail(` yok, `add_marker` yok, `xfail_strict` ayarı yok).

### P3 — Frontend lint / typecheck / test / build (verdict: **PASS**, 5/5)

| # | Komut | Exit | Süre / Ölçülen |
|---|---|---:|---|
| 1 | `npm ci` | **0** | ~13 s · `added 243 packages, and audited 244 packages` |
| 2 | `npm run lint` (`eslint .`) | **0** | çıktı boş — 0 error / 0 warning |
| 3 | `npm run typecheck` (`tsc -b --noEmit`) | **0** | çıktı boş — 0 tip hatası |
| 4 | `npm run coverage -- --no-file-parallelism` | **0** | **70 dosya / 721 test passed**, 0 failed / 0 skipped / 0 todo, 475.33 s |
| 5 | `npm run build` (`tsc -b && vite build`) | **0** | 176 modül, `✓ built in 1.52s` |

**Coverage — ölçülen vs. kapı** (`frontend/vite.config.ts`):

| Metrik | Ölçülen | Kapı | Pay |
|---|---|---|---|
| Lines | **84.92 %** (4914/5786) | 83 | +1.92 |
| Statements | 82.62 % (5247/6350) | 80 | +2.62 |
| Functions | 75.27 % (1976/2625) | 73 | +2.27 |
| Branches | 72.84 % (4810/6603) | 70 | +2.84 |

Dördü de kapının üstünde; **hiçbir eşik değiştirilmedi**. Build iki **uyarı** üretti (hata
değil): tek chunk `964.37 kB` (gzip 242.36 kB, Vite eşiği 500 kB) ve `vite.config.ts:18`
`__dirname` / `configLoader: 'native'` uyarısı.

### P4 — Migration ve şema (verdict: **PASS**)

| Adım | Komut | Exit | Ölçülen |
|---|---|---:|---|
| Head parity | `generate_repository_facts.py --check` | **0** | canlı `alembic heads` = `0043_i08_registry_strategy_fks` = generated head → **çelişki yok** |
| Boş DB'den kurulum | `DROP SCHEMA public CASCADE; CREATE SCHEMA public;` + `alembic upgrade head` | **0** / **0** | **43 migration** uygulandı (`0001`→`0043`); **104 tablo** (alembic_version hariç), **140 FK** — generated değerlerle **birebir** |
| Single head | `alembic heads` / `alembic current` | **0** / **0** | tek satır: `0043_i08_registry_strategy_fks (head)`; `versions/*.py` = 43 dosya |
| down/up × 2 | `alembic downgrade -1` + `upgrade head` (×2) | **0** ×4 | 4 fazın 4'ünde 5 tablonun fingerprint'i **IDENTICAL**; 0043'ün 3 FK'si 3/3 ↔ 0/3 tam döngü |
| Kolon parity | `information_schema.columns` ↔ `Base.metadata` | **0** | `tables compared: 104 · columns compared: 1157 · **problems: 0**` |

**Kritik dürüst sınır (P4'ün kendi bulgusu):** `alembic check` **exit 255** verir. Emitlediği
farkların tamamı index/constraint eksenindedir — `removed index` **39**, `added index` **39**,
`removed unique constraint` 1, `changed index` 1; **`added/removed column` = 0**,
**`added/removed table` = 0**, **tip/server-default değişimi = 0**. Şekil karşılaştırması:
DB'de 254 / modelde 253 şekil, **48 aynı-şekil-farklı-ad**, bunun **8'i sapma değil**
(isimsiz unique constraint) → **40 gerçek index-adı sapması**. Ve:
**`.github/workflows/*.yml` içinde `alembic check` YOK** (`alembic upgrade head` var:
`ci.yml:111`, `performance.yml:100`, `install-acceptance.yml`) → bu 40 sapma **sahipsiz ve
izlenmiyor**. Bu dalga onu getirmedi, düzeltmedi — **ölçtü**.

**L1 FK insert-order:** bu dalgada yeni `create_*` **YOK** (ölçüm: `git diff … | grep '^\+.*def create_'` → boş;
`git diff 20e942b^..HEAD -- backend/` boş). Mevcut `create_*` komutu sayısı **25**; hiçbiri
değişmedi, dolayısıyla yeni L1 kanıtı gerektiren yüzey yok. 0043'ün üç FK'si için tesadüfi
ama gerçek bir insert-order kanıtı §3'ün tohumlamasından çıkmıştır (**dar kapsam**).

### P5 — Docker stack + üç auth modu + servis sağlığı (verdict: **PARTIAL — 1 PASS / 3 BLOCKED**)

> **AŞILDI — 2026-08-10 (ADIM 30).** Aşağıdaki 2/3/4 satırları o günün kaydıdır ve
> **değiştirilmemiştir**. Üçü de 2026-08-10'da koşuldu ve geçti; güncel durum **§6.2 +
> §6.2.1**, ham kanıt `docs/releases/evidence/2026-08-10/`. Bu tabloyu tek başına okuma.

| # | Adım | Komut | Exit | Sonuç |
|---|---|---|---:|---|
| 1 | Backend image | `docker build -t entropia-backend:ci ./backend` | **0** | PASS — 203.4 s, **2.09 GB** |
| 1 | Frontend image | `docker build -t entropia-web:ci ./frontend` | **0** | PASS — 588.9 s, **84 MB** |
| 2 | Üç auth modu (session / legacy / dev-auth) | `scripts/e2e-acceptance.sh all` | — | **BLOCKED — hiç koşmadı** |
| 3 | Servis bazında health | — | — | **BLOCKED — hiç ölçülmedi** |
| 4 | `scripts/smoke.sh` + `scripts/worker-restart-smoke.sh` | — | — | **BLOCKED — hiç koşmadı** |

**Blokajın kanıtı (ürün kusuru değil, host kaynak tükenmesi):** Docker VM **3.89 GiB** / 8 CPU,
aynı daemon'da **22 container** (`entropia-a11y-audit` 15 + `entsec` 9+), host load average
tepe `14.98 / 23.95 / 27.22`, compose aynı 2.09 GB imajı **10 hedefe eşzamanlı** export etmeye
başladı ve buildkit **16+ dakika** hiçbir çıktı üretmedi. Daemon yüzeyi kısmen kilitlendi:
`docker version` **0**, `docker buildx ls` **0**, ama `docker ps -q` **124**, `docker images -q`
**124**, `docker tag` **124** (240 s timeout). Belge commit edilirken son ölçüm
`timeout 20 docker ps -q` → **124**.

> **Sahte yeşil YOK:** 2–4 için hiçbir servis "healthy" yazılmadı.

### P6 — Uçtan uca kabul akışları (verdict: **BLOCKED**)

> **AŞILDI — 2026-08-10 (ADIM 30).** (a)–(e) satırları o günün kaydıdır ve
> **değiştirilmemiştir**. Beşi de 2026-08-10'da koşuldu (**60 passed / 0 failed /
> 2 skipped**, tarayıcı katmanı **5 passed**) ve bu tablonun "kapsam boşluğu" gerekçesinin
> tarayıcı katmanını atladığı ölçülerek gösterildi. Güncel durum **§6.2**, ham kanıt
> `docs/releases/evidence/2026-08-10/P6B_acceptance_flows_harness.md`. Bu tabloyu tek
> başına okuma.

| # | Akış | Komut | Exit | Sonuç |
|---|---|---|---:|---|
| a | Strategy → Ready-check → Run → Result | — | — | **BLOCKED — harness kapsam boşluğu** |
| b | Library validation | — | — | **BLOCKED — harness kapsam boşluğu** |
| c | ESP lifecycle + export | — | — | **BLOCKED — harness kapsam boşluğu** |
| d | Agent Strategy / Trading Signal tools | — | — | **BLOCKED — harness kapsam boşluğu** |
| e | Trash: soft-delete → restore → purge | — | — | **BLOCKED — harness kapsam boşluğu** |
| — | harness denemesi | `timeout 90 ./scripts/acceptance.sh` | **124** | banner'dan sonra asılı kaldı |
| — | harness denemesi | `timeout 90 ./scripts/e2e-acceptance.sh all` | **124** | **tek satır çıktı bile yok** |
| f1 | Backup | `./scripts/backup.sh` | **0** | PASS — `postgres.dump` 394464 bayt, head `0039_backtest_run_cancellation`, **103** public tablo |
| f2 | Restore | `RESTORE_DB=… OBJECT_STORAGE_BUCKET=… ./scripts/restore.sh <dir> --yes` | **0** | PASS |
| f3 | Backup verify | `./scripts/backup-verify.sh <dir>` | **0** | PASS — 103 tablo restore edildi |
| f4 | DR acceptance (1. koşu) | `./scripts/dr-acceptance.sh` | **1** | FAIL — **6 passed / 2 failed / 1 warned** |
| f4b | DR acceptance (2. koşu) | `./scripts/dr-acceptance.sh` | **0** | PASS — **8 passed / 0 failed / 1 warned** |

**(a)–(e)'nin BLOCKED sebebi ortam değil, kapsam boşluğudur** — ve bu P6'nın en ağır
bulgusudur: görevin adlandırdığı iki script bu beş akışı **hiç uygulamıyor**. Terim taraması
(her iki script, case-insensitive): `ready-check`/`readiness` **0**, `backtest-run`/`/runs`
**0**, `backtest-result` **0**, `library` **0**, `trading-signal`/`agent-task` **0**,
`trash`/`purge` **0**, `Idempotency-Key`/`If-Match` **0**. Üç görünen isabetin üçü de yanlış
pozitif (`despite`, yorum satırı, shell `export`). **Docker ayağa kalksaydı da bu beş akış
koşmayacaktı.**

**f4'ün adjudication'ı (CLAUDE.md kuralı gereği ampirik):** sapma **monotonik büyüdü**
(`audit_events` 1030 → 1032 → 1036), sapan **tek tablo** `audit_events` iken diğer **102**
tablo + 10 immutable-evidence projeksiyonu + **56 nesnenin** path/size/md5'i birebir eşleşti,
fazla altı satır yedekten **sonra** yazılmıştı (18:19:22Z–18:23:00Z, hepsi
`backtest.run_admission_rejected`/`user_1`), ve yazıcı susunca ikinci tur 8/0 verdi →
**eşzamanlı-yazıcı artefaktı, DR kusuru değil**.

> **Kapsam uyarısı:** her iki koşuda da `WARN [6] only 1 evidence table(s) actually held rows`
> — 10 immutable projeksiyonun **9'u iki tarafta da boştu**. DR turu "hash korunur" iddiasını
> **taşımaz**. Ayrıca DR kanıtı canlı dev DB'nin `0039` başında alındı; repo başı `0043` →
> `0040`–`0043` şeması **round-trip edilmedi**.

**Ek bulgu (kaydedildi, düzeltilmedi):** `e2e-acceptance.sh`'in daemon preflight koruması
**takılmış** bir daemon'a karşı işlemiyor — koruma satırına hiç ulaşılmıyor, script net bir
`exit 2` yerine sonsuza kadar asılı kalıyor.

### P7 — Oracle determinizmi ve containment (verdict: **PASS**)

| Kapı | Komut | Exit | Ölçülen |
|---|---|---:|---|
| Oracle + golden, RUN 1 | `pytest tests/unit/oracles/ tests/unit/test_backtest_engine_golden.py --no-cov -q` | **0** | **113 passed / 0 failed / 0 xfail** |
| Oracle + golden, RUN 2 | aynı | **0** | **113 passed** — tekrarlanabilir |
| Determinizm probu | 4 süreç × `PYTHONHASHSEED ∈ {0, 1, 12345, random}` | — | 46 senaryonun **46/46** digest'i özdeş; `engine A == B` **True** (4/4 süreçte) |
| Containment (geniş) | `pytest test_shared_allocation_containment.py ×2 + test_repository_facts_guard.py --no-cov -q` | **0** | **44 passed** (9 unit + 7 integration + 28 contract) |
| F-07 pinli etiket (unit) | `pytest test_f07_manifest_item_labels.py test_backtest_portfolio_mode.py` | **0** | **28 passed** |
| F-07 pinli etiket (DB) | `pytest test_f07_display_labels.py test_backtest_manifest_pinning.py test_portfolio_simulation_mode.py` | **0** | **16 passed** |

**Digest'ler (bit-bit reproducibility kanıtı):**

| Ölçüm | Değer |
|---|---|
| `ENGINE_AGGREGATE_DIGEST` | `fa4a24e0b7c25bd86f0f65d2b77d5769ca00de6d216be1914abddd3dfb85ade2` |
| `BASELINE_AGGREGATE_DIGEST` (commit'li JSON) | `fa4a24e0b7c25bd86f0f65d2b77d5769ca00de6d216be1914abddd3dfb85ade2` |
| `PORTFOLIO_RUN_DIGEST` | `345b91a68399d5c8975141a1cac014ae1da84facaf4686388174094c409f3a79` |

Motor digest'i `engine_golden_digests.json` taban çizgisiyle **birebir**; `PYTHONHASHSEED=random`
altında da sabit → çıktı sözlük yineleme sırasına bağlı değil.
**Reconciliation toleransı = 0** — oracle paketinde `pytest.approx`, `math.isclose`, `rel=`,
`abs=` **yok**; 113 testin hepsi `Decimal` tam eşitlikle geçiyor.
**Oracle paketinde xfail/skip = 0** (grep boş + `-rxX` koşusu hiç XFAIL/XPASS basmadı,
**111 passed in 2.55s**, exit 0).

### P8 — Worker dayanıklılığı ve lookahead (verdict: **PARTIAL — 2 PASS / 1 BLOCKED**)

| # | Kapı | Komut | Exit | Ölçülen |
|---|---|---|---:|---|
| 1a | Süreç içi kaos (crash / eşzamanlı teslim / redelivery) | `pytest --no-cov -p no:randomly` × 8 dosya | **0** | **49 passed** in 262.53 s |
| 1b | Konteyner düzeyi kaos | `scripts/worker-restart-smoke.sh` | — | **BLOCKED** — `docker version` **124**, `docker info` **124** (`0 bytes / 0 cpu`), `docker ps -a` **124**, `docker compose ps` **124** |
| 1c | Uzun işler durable queue üzerinden mi | envanter + invariant testleri | **0** | 10 admission yüzeyi (`enqueue_job`) / 12 dispatch (`send_job`); 5 uzun-iş ailesinin **tamamı** durable |
| 2 | `event_time` vs `available_time`, no-lookahead | `pytest --no-cov -p no:randomly -rxXs` × 7 dosya | **0** | **75 passed + 1 xfailed** in 986.88 s |
| 3 | Oracle'da xfail sıfır | `pytest tests/unit/oracles/ -rxX` | **0** | **111 passed**, 0 xfail |

Point-in-time matrisi **T-1..T-11**'in 10'u PASS; **T-7 XFAIL (#558)** — `strict=True` olduğu
için XPASS bir başarısızlık olurdu, yani XFAIL raporlanması kusurun **hâlâ kodda** olduğunu
kanıtlar. Kusurun doğası: `compile_backtest_evidence_bundle` zaman politikasını **doğruluyor**
ama **kaydetmiyor** → `bundle_hash` politika değişimine karşı değişmiyor; Run manifest ise
dokuz alanı pinliyor → iki execution-evidence yüzeyi çelişiyor. **No-lookahead güvenliği
bundan etkilenmiyor** (T-6 yeşil: onaylı revizyon yerinde yeniden zamanlanamıyor).

**Dürüst formülasyon (P8 §4.2):** *bug değil, karşılanmamış bir canon şartı; remedy'nin
ŞEKLİ ürün kararına bağlı.*

### P9 — Güvenlik kapıları (verdict: **BLOCKED** — B1 sonradan düzeltildi, B2 açık)

| # | Kapı | Komut | Exit | Ölçülen |
|---|---|---|---:|---|
| G1 | Python bağımlılık denetimi | `cd backend && uv run --with pip-audit pip-audit` | **0** | `No known vulnerabilities found` (46 dağıtım) |
| G2 | Aynısı dev extra ile | `uv run --extra dev --with pip-audit pip-audit` | **0** | `No known vulnerabilities found` (79 dağıtım) |
| G3 | npm advisory kapısı | `node scripts/npm-audit-gate.mjs frontend frontend/e2e` | **0** | `frontend: high=3 critical=0` — **2 advisory frozen** · `frontend/e2e: high=0 critical=0` |
| G4 | Allowlist kapısı, argümansız | `node scripts/security-allowlist-gate.mjs` | 1 | `usage: …` — kapı hatası değil |
| G5 | Allowlist kapısı, trivy raporlarıyla | `… container:backend=… container:frontend=…` | **0** (CI) | `OK — 0 fixable CRITICAL/HIGH finding(s), all accounted for.` · allowlist `entries: []` |
| G6 | Secret scan (gitleaks, digest-pinned) | `docker run … gitleaks detect --no-git --config .gitleaks.toml --redact -v` | **0** | **`no leaks found`** — 19.45 MB / 2m22s |
| G7 | Runtime kullanıcı non-root | `docker run --rm --entrypoint id <image> -u` | **0** | backend **uid=10001** · web **uid=101** |
| G8 | Trivy image scan (HIGH/CRITICAL, `--ignore-unfixed`) | trivy | **0** (CI) | fixable HIGH/CRITICAL **yok** |
| G9 | SBOM (CycloneDX ×4) | trivy `--format cyclonedx` | **0** (CI) | **1202 / 81 / 71 / 13** bileşen |
| G10 | CodeQL (python + javascript-typescript) | — | **0** (CI) | yerelde koşulamaz; aynı sha'da CI ✅ |

**CI otoritesi:** Security workflow run `31190284830`, `headSha = 6cd6172` → **success, 4/4 job**
(`CodeQL — python`, `CodeQL — javascript-typescript`, `Secret scan (gitleaks)`,
`Container scan + SBOM`). Bu, kanıtlanan ağacın **birebir kendisidir**.

**Server-side authorization kanıtı — PASS.** "UI hidden/disabled authorization değildir"
iddiası **iki katmanda, altı uçta** kanıtlandı:

| Katman | Test | Komut | Exit | Ölçülen |
|---|---|---|---:|---|
| HTTP (route) | `test_identity_and_gating.py::test_admin_routes_reject_normal_user` | `pytest tests/contract/test_identity_and_gating.py test_manual_contract.py -v --no-cov` | **0** | **28 passed** — 6 ucun 6'sı **403**, tipli kod, `assert "data" not in resp.json()` |
| Servis (application) | `test_trash_page.py::test_trash_surfaces_reject_non_admin[user\|agent]` | `pytest tests/integration/test_trash_page.py -v --no-cov` | **0** | **19 passed**, 1089.02 s — HTTP tamamen devre dışı, yine 403 |

Sayım: `require_*` route katmanında **28** çağrı / **15** dosya, application katmanında
**251** çağrı / **54** dosya. `ensure_can_edit` **20**, `ensure_can_view` **31**.
OCC dual-token tek kural yeri `reconcile_occ_tokens` → **12** route çağrısı;
`run_idempotent` → **97** çağrı; `_audit_and_outbox` → **93** çağrı.
UI-only gating **yok**: `nav.ts`'teki her `adminOnly` hedefin sunucu muhafızı var.

> **Kaydedilen ölçüm artefaktı:** hardening/CORS/envelope/SSE/login-gate contract paketi
> birlikte koşulduğunda **76 passed / 1 failed** (exit 1) verdi; düşen test
> (`test_auth_mode_login_gate.py::test_session_mode_login_reaches_the_credential_check`,
> `Future … attached to a different loop`) **tek başına koşuldu → 3 passed, exit 0**.
> Ürün kusuru değil, dosya seçiminin event-loop artefaktı. Gizlenmedi, kaydedildi.

### P9-B1 — js-yaml düzeltmesi (PR #637, **MERGED**)

Bu bir P adımı değil, P9'un B1 blocker'ının **düzeltmesidir** — ve `1f4b88b` sonrası
**tek kod/lockfile değişikliğidir**.

| # | Kapı | Komut | Exit | Ölçülen |
|---|---|---|---:|---|
| V1 | npm advisory kapısı | `node scripts/npm-audit-gate.mjs frontend frontend/e2e` | **0** | `frontend: high=2 critical=0` — **tek** frozen kayıt: react-router |
| V2 | Temiz kurulum | `npm ci` | **0** | `node_modules/js-yaml` = **4.3.1** |
| V3 | Lint (js-yaml'ın tek tüketicisi) | `npm run lint` | **0** | eslint@9 flat-config sorunsuz |
| V4 | Typecheck | `npm run typecheck` | **0** | — |
| V5 | Build | `npm run build` | **0** | `✓ built in 1.38s` |
| V6 | Test | `npm test -- --no-file-parallelism` | **0** | **721 passed / 70 dosya** — baseline ile birebir |

**Bu adımda ölçüldü:** PR #637 `2026-08-07T17:56:59Z`'de merge edildi (merge commit
`8adb4d7`); `origin/main` lockfile'ında js-yaml **4.3.1**; `scripts/npm-audit-gate.mjs`
içinde kalan tek frozen id **`GHSA-qwww-vcr4-c8h2`**. Yani **B1 KAPANDI**, P9'un artık
kalan blocker'ı **yalnız B2**'dir (§6.4).

### P10 — Performans bütçeleri ve gözlemlenebilirlik (verdict: **PARTIAL**)

| # | Kapı | Komut | Exit | Ölçülen |
|---|---|---|---:|---|
| 1 | Load smoke (CI `load-smoke` aynası) | `loadgen.py --profile smoke --concurrency 4 --repeats 5 --sse-seconds 5` | **0** | **17/17 senaryo**, hepsinde `n=5 err=0`; SSE `connects=1, reconnects=0, transport_disconnects=0` |
| 1b | Load driver unit | `pytest tests/unit/test_loadgen.py` | **0** | **32 passed** in 0.13s |
| 2 | Query bütçeleri + alarm sözleşmesi | `pytest test_query_budgets.py test_alert_rules_contract.py --no-cov` | **0** | **66 passed** (8 bütçe + 58 alarm) — bütçe aşımı yok |
| 4 | Alarm kuralları (promtool, digest-pinned v3.5.0) | `scripts/alert-rules-gate.sh` | **0** | `check config` SUCCESS · `check rules` **11 rules** · `test rules` SUCCESS |
| 5 | Runbook kapsaması | 11 alarmın runbook taraması | — | **11/11** — dosya var **ve** alarmı adıyla anıyor (7 page + 4 ticket) |

Load smoke p50 aralığı 3.559 ms (`meta`) – 13.402 ms (`mainboard`); p95 aralığı 4.715 ms –
47.838 ms (`admin_logs`). **Bu milisaniyeler bir bütçe değildir** — runner class
`local-darwin-arm64-dev-laptop`, `docs/performance/README.md` §2 gereği CI baseline'ı ile
karşılaştırılamaz. Tek sert kapı **`err=0`**, ve karşılandı. Redis kasten ölü porta bağlandı
(`redis://127.0.0.1:59999/0`) ve 17 senaryonun tamamı yine cevap verdi → "hiçbir okuma
senaryosu iş kuyruğa atmıyor" iddiası doğrulandı.

**N+1 kapısı çalışıyor; iki N+1 hâlâ canlı — bulgu P10-B1:**

| Yüzey | n=1 → n=11 | `per_item` | Kayıtlı issue | Issue durumu |
|---|---|---|---|---|
| `library.list_packages` | 3 → 3 | 0 | — | — |
| `results_history.list_backtest_results` | 6 → 6 | 0 | — | — |
| `agent_workspace.list_tasks` | 1 → 1 | 0 | — | — |
| `audit_log.list_audit_events` | 1 → 1 | 0 | — | — |
| ~~**`readiness_check.market_data_leg`**~~ → **2 → 2** | ~~2 → **12**~~ | ~~**1**~~ → **0** | **#617** | **ADIM 46: KOD TARAFI KAPANDI** |
| ~~**`dependency_pins.ensure_pinned_resolvers_active`**~~ → **2 → 2** | ~~2 → **22**~~ | ~~**2**~~ → **0** | **#618** | **ADIM 46: KOD TARAFI KAPANDI** |

Ampirik doğrulama (çıkarım değil): `-s` koşusunda `came in under budget` satırı **0 kez**
geçti → ölçülen sayılar bütçeye **eşit**; ve kaynak hâlâ döngü içi await taşıyor
(`commands/readiness_check.py:401-406`, `queries/dependency_pins.py:114-115`).

> **2026-08-12 (ADIM 46) — iki N+1 de KAPANDI.** Üstü çizili sayılar **bayat değildi**:
> kod yazılmadan önce `c931063` üzerinde birebir yeniden üretildi (**12** @ n=11, slope
> **1.0**; **22** @ n=11, slope **2.0**) — yani ADIM 42–45 hiçbirini kapatmamıştı.
> Düzeltme sonrası **ikisi de n=1'de ve n=11'de 2 statement, slope 0**.
> `query_budgets.json` iki satırda da `queries_large: 2` / `per_item: 0`'a **sıkıldı** ve
> **kapının dişi kanıtlandı**: yalnız `src/` geri alınınca gate *"12 queries at n=11,
> budget 2"* ve *"22 queries at n=11, budget 2"* ile kırmızıya düşüyor.
> **Yukarıdaki satır numaraları artık geçersiz** — sembole bak, satıra değil:
> `commands/readiness_check.py::_resolve_market_data_issues` +
> `market_repo.get_dataset_roots`; `queries/dependency_pins.py::_prefetch` +
> `esp_repo.get_registry_by_keys`.
> Sorgu sayısı **davranışı kanıtlamaz**, o yüzden eşdeğerlik ayrı dosyada pinli
> (`tests/integration/test_batched_dereference_equivalence.py`, 13 test) ve **mutasyonla
> sınandı**: `entity_type` kapısını batch'ten düşürmek, ve revizyon batch'ini registry
> fallback'i olmadan kurmak, testleri kırmızıya çeviriyor. **Batch sırası taşıyıcıdır** —
> `embedded_revision_id` vermeyen bir ref entry'nin `trusted_active_revision_id`'sine
> düşer, yani revizyon batch'i ancak registry batch'inden SONRA kurulabilir.
> **#617/#618'in issue durumu bu slice'ın çıktısı değildir** — kodu kapatır, izleme
> kaydını insan kapatır. §6.6.

**Sayfalama — bulgu P10-B2:** runtime'da **istisnasız** kelepçeli, ama iki katmanda.
19 route parametresi `le=100` ilan ediyor (`shared/pagination.py`: `DEFAULT_LIMIT=20`,
`MAX_LIMIT=100`); **9 parametre** (`agent_lab` ×4, `admin_panel` ×3, `capability` ×2)
`le=` taşımıyor ve sorgu katmanında kelepçeleniyor (`clamp_limit` → 100, `_clamp_limit` →
`MAX_LOG_LIMIT=100` / `MAX_BACKTEST_LOG_LIMIT=100`). Sonuç: `limit=100000` gönderen istemci
**reddedilmiyor, sessizce 100'e indiriliyor** — 19 uç 422 verirken bu 9 uç 200 veriyor.
Kaynak tüketimi güvenli, **sözleşme yanıltıcı**. 24 uç keyset cursor kullanıyor.

### P11 — Görsel regresyon ve otomatik a11y (verdict: **PASS 3/3 — ama uyum beyanı DEĞİL**)

Kanıt kaynağı: GitHub Actions **E2E** run **`31212829328`**, commit **`2cf7283`**, sonuç
**success**; üç job da success (`92980675739` E2E/F-23 · `92980675586` A11Y/R2-14 ·
`92980675661` dev-auth).

| # | Katman | Komut | Sonuç | Ölçülen |
|---|---|---|---|---|
| 1 | Visual regression | `playwright test --grep @visual` | **success** | **8/8 passed** (1.4m), 1440×900 fullPage, `maxDiffPixelRatio 0.02` |
| 1b | Ana E2E suite | `npm test` | **success** | **39 passed / 1 skipped** |
| 2 | axe-core ratchet (bloklayıcı) | `npm run a11y` | **success** | **45 serious düğüm / tavan 45** · **critical 0** · moderate 0 · minor 0 · 23 route · 6 test passed (1.0m) |
| 3 | Klavye-only gezinme | `specs/14-keyboard-flow.spec.ts` | **passed** | 860 ms — login → Mainboard → Add menü aç/kapa, mouse yok |

45 düğümün **tamamı tek kural**: `color-contrast`, **tamamı 2.67:1**, iki renk çifti —
**33 × `#ffffff` on `#00a9e8`** + **12 × `#00a9e8` on `#ffffff`**. Ölçülen dağılım repodaki
`a11y-baseline.json` ile **karakter karakter aynı** (`measured == baseline → True`);
`axe-baseline.tightened.json` artefaktta **yok** → tavan ne aşıldı ne de sessizce gevşek kaldı.

**Bloklanmayan 90 advisory gözlem** (log'dan satır satır sayıldı, 23+23+21+21+1+1):
23/23 route'ta `contentinfo` landmark yok · 23/23 route'ta ilk tabbable öğe "Log out"
(**skip link yok**) · 21 route'ta başlangıç DOM'unda `aria-live` yok · 21 sayfada başlık
hiyerarşisi atlıyor · `/user-manual`'da `<h1>` yok · +1 odak göstergesi gözlemi.

### P12 — A-08 insan kabul kapısı (verdict: **BLOCKED**)

| Kapı | Gerekli | Ölçülen | Sonuç |
|---|---|---|---|
| Dört çıkış kriteri (defter §5) | 4/4 ☑ | **0/4** — dördü de ☐ | **DÜŞTÜ** |
| A-08 için imzalı kalıcı sapma | var **veya** yok+denetim yapılmış | **YOK** | **DÜŞTÜ** |

| Ölçüm | Komut | Sonuç |
|---|---|---|
| #514 durumu | `gh issue view 514 --json state,closedAt,stateReason,labels` | **CLOSED** · `closedAt 2026-08-07T03:52:03Z` · `stateReason COMPLETED` · label `human-only` |
| Denetim defteri §0 | okuma (346 satır) | denetçi `—`, tarih `—`, SR sürümü `—`, tarayıcı `—`, stack commit `—`, kayıt yolu `—` — **iki blokta da tek dolu alan yok** |
| Defter §1 (Section A) | okuma | **SR-1: 0/23 rota · SR-2: 0/23 rota** (46 koşunun 46'sı `—`) |
| Defter §2 (Section B) | okuma | **SR-1: 0/10 akış · SR-2: 0/10 akış** (20 koşunun 20'si `—`) |
| Defter §3 (findings) | okuma | tek satır, o da yer tutucu: `*(none recorded — audit not run)*` |
| `SR-BULGU` taraması | `grep -rn "SR-BULGU" docs/` | **8 hit / gerçek bulgu kaydı 0** (2 şablon + 6 yokluk beyanı) |
| A-08 için imzalı sapma | `grep -in 'a-08\|a08\|screen.reader\|NVDA\|VoiceOver' docs/implementation/v18_visual_deviations.md` | **0 hit**; dosyadaki tek sapma kimliği `D-1` |

**Blocker adı: `A-08-HUMAN-GATE-UNMET`.**

---

## 4. Future-Dev capability'leri — unified portfolio containment

`SHARED_ALLOCATION_STATUS = future_dev` (P1 Gate 1'in doğruladığı üretilmiş değer;
`docs/generated/repository_facts.md:27`, CI'da `--check` kapılı). Bu, **containment KAPALI**
demektir: mod ilan edilmiştir ama çalıştırılamaz. P7 üç bağımsız kanıtın üçünü de yeşil ölçtü.

### Kanıt A — bayrak

```
backend/src/entropia/domain/allocation/capability.py:105
SHARED_ALLOCATION_STATUS: SharedAllocationStatus = "future_dev"
```

`shared_allocation_is_executable()` → **`False`**. Bu tek cevap dört yüzeyi birden besliyor:
`domain/allocation/rules.py` (blocker) · `domain/readiness/validators.py`
(`ALLOCATION_SHARED_MODE_NOT_IN_BUILD`) · `application/commands/backtest_run.py`
(admission guard — **readiness bypass edilse bile tutar**) · Portfolio sayfasının
capability view'i.

### Kanıt B — `run_portfolio` üretimde çağrısız

`backend/src/` içindeki **tüm** geçişler: 1 tanım (`portfolio_engine.py:479`), 1 `__all__`
girdisi, 4 docstring metni. **Tek tanım, SIFIR çağrı.** `frontend/src` içinde referans yok.
Çağıranların tamamı test (8 dosya). Worker hâlâ eski yolu yürüyor ve PR B'nin hedefi olan
satırlar **dokunulmadan** duruyor:

```
application/jobs/backtest_engine.py:100   from ...execution.portfolio import combine_item_runs
application/jobs/backtest_engine.py:298   for prepared in prepared_items:
application/jobs/backtest_engine.py:363   output = combine_item_runs(
```

→ Hiçbir istek, retry veya job tick döngüsüne ulaşamaz → **sevk edilmiş hiçbir Result
değişemez**.

### Kanıt C — containment gate testi yeşil

```
tests/unit/oracles/test_oracle_portfolio_containment_gate.py
  ::test_the_phase_loop_exists_but_no_production_path_reaches_it   PASSED
```

Test iddiayı **statik olarak** da kanıtlıyor (`_SRC.rglob("*.py")` üzerinden): tek üretim
tanımı, altı unified-clock modülünün faz döngüsü dışında üretim importer'ı yok,
`callers == []`, ve worker'ın item döngüsü + `combine_item_runs` korunuyor. Paketin diğer
üç testi de yeşil; `test_the_containment_flag_and_engine_version_are_both_untouched` bayrak
+ versiyon çiftini **birlikte** kilitliyor.

**Contained defect'in büyüklüğü ölçüldü:** aynı trade seti üzerinde sıralı fold
`max_drawdown = 5000.00`, birleşik saat `3000.00` → **%66 abartı**
(`test_the_same_trades_read_5000_sequentially_and_3000_on_one_clock`). Bu tam olarak
containment'ın neyi tuttuğudur.

**Geniş containment yüzeyi:** `44 passed`, exit 0 (9 unit + 7 integration + 28 contract) —
aralarında `test_admission_guard_holds_when_ready_check_is_bypassed`,
`test_retry_of_a_shared_composition_is_refused`,
`test_run_admission_refuses_and_leaves_nothing_behind` (yarım kayıt bırakmıyor),
`test_independent_mode_still_runs_to_a_result` (independent mod bozulmadı),
`test_a_legacy_shared_pool_result_stays_readable_and_unmodified`.

**Açık boşluk (değişmedi):** worker'ı bağlamak gerçek motorla desteklenen bir
`ItemParticipant` gerektirir. **PR B post-V1'dir ve bu dalgada sokulmadı** — P7 salt-okuma
doğrulamadır.

**Diğer bilinçli Future-Dev / kapsam-dışı alanlar** (P1 Gate 3'ün ölçtüğü,
`deliberate_future_dev` sınıfı): **8 kriter / 27 clause**.

---

## 5. Signed deviations

### 5.1 D-10 — **İMZALI**, kapsamı 1.4.3 ile SINIRLI

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

**D-10 imzanın üç şartını da taşır:** adı verilmiş imzalayan + ISO tarih + açık kapsam.
P11 iki yarısını da doğruladı: sapma **gerçek ve ölçülü** (45 düğüm, 2.67:1, gereken
4.5:1'in çok altında) ve sapma **kapsanmış** (dondurulmuş tavan tutuyor, 46'ncı düğüm CI'ı
kırar).

**Kapsam sınırı — bu belgenin en sık yanlış okunan satırı olacaktır:**

| D-10 neyi kapsar | D-10 neyi KAPSAMAZ |
|---|---|
| WCAG 2.2 AA **1.4.3 (Contrast — Minimum)**, düşük-görüş ekseni | **A-08** (ekran okuyucu ekseni) — defter §329: *"It is a low-vision axis, not a screen-reader one."* |
| 45 düğümlük donmuş küme, iki renk çifti | K-2..K-6 (skip link, `contentinfo`, `<h1>`, başlık hiyerarşisi, odak göstergesi) — **özellikle K-6b**: odak halkasının kontrastı **1.4.11** ölçütüdür, D-10'un 1.4.3 imzası onu **kapsamaz** (ADIM 48'de ayrıca kapatıldı) |
| | Alertmanager boşluğu, P5/P6 kabul akışları, react-router advisory'si |

**Ürün WCAG 2.2 AA 1.4.3 için UYUMLU DEĞİLDİR** ve hiçbir belge/pazarlama metni ürünü
"WCAG 2.2 AA uyumlu" diye tanımlayamaz.

### 5.2 İmzalı sapma **olmayan** alanlar (kritik ayrım)

Aşağıdakilerin hiçbiri için D-10 biçiminde bir kayıt **yoktur** — "kapsam dışı" ile
"imzalı kalıcı sapma" aynı şey değildir:

| Alan | Durum |
|---|---|
| **A-08** insan ekran okuyucu denetimi | imzasız · denetim de yapılmadı (§6.1) |
| **Alertmanager** yokluğu | imzasız · repo kendi ilan ediyor ama imza yok (§6.3) |
| **react-router** `GHSA-qwww-vcr4-c8h2` freeze'i | imzasız — `owner` yok, `expires` yok, ISO tarih yok (§6.4) |
| **#558** bundle time-policy pin | imzasız · issue COMPLETED kapalı, strict xfail hâlâ düşüyor |
| **#559 / #617 / #618** | imzasız · üçü de COMPLETED kapalı, iş açık |

**Bu belge hiçbir sapma kaydı YAZMADI** — imzalayan verilmedi ve imza yetkisi agent'ta
değildir.

---

## 6. Blockers

### 6.1 `A-08-HUMAN-GATE-UNMET` — **BLOCKER** (P12)

> **2026-08-12 / ADIM 44 — denetim KOŞULABİLİR hâle geldi. Blocker KAPANMADI.**
> Aşağıdaki blok **olduğu gibi geçerlidir**: dört çıkış kriteri de ☐, defterin §1/§2/§3'ü
> boş, #514 hâlâ kanıtsız kapalı. Değişen tek şey, (A) yolunun önündeki **hazırlık**
> engellerinin kalkması:
>
> * **Yığın güncel main'de yeniden doğrulandı — `9 passed / 0 failed`.** Önceki doğrulama
>   `1f4b88b`'deydi; main o zamandan beri ADIM 30–43 ile dokuz slice ilerledi. Ölçüldü,
>   varsayılmadı; **hiçbir şeyin onarılması gerekmedi**.
> * **Precheck sayıları tazelendi — ve biri yerinde durmadı.** Beş ardışık koşu: K-2/K-3
>   `23/23`, K-4 `1`, K-6 `1` **kararlı**; K-5 ve yeni **K-7** `21/23`'e **yakınsıyor**,
>   toplam advisory `90`. **İlk koşu soğuktur ve EKSİK raporlar** (K-5'i `18` gösterdi) —
>   yani defterin kendi *"re-run it before the audit"* talimatı tek koşuyla uygulansaydı
>   `21/23`'ü `18/23` ile değiştirip tabloyu **daha yanlış** hâle getirirdi. Kalıcı bir
>   oynaklık üç adlandırılmış rotada sürüyor (`/analysis-lab`, `/backtest/history`,
>   `/backtest/metrics`). Sebep: prob *ilk* DOM'u okuyor ve sayfanın ilk veri render'ı ile
>   yarışıyor. **Kaydedildi, DÜZELTİLMEDİ** — probun ne zaman örnekleyeceğini değiştirmek
>   K-5 ve K-7'nin *anlamını* sessizce değiştirirdi ve ikisi de denetimin karara bağlaması
>   gereken gözlemlerdir.
> * **K-7 eklendi:** `aria-live` bölgesi ilk DOM'da yok — **21/23 rota**, WCAG 4.1.3 (AA).
>   ADIM 28'den beri `precheck-results.json` içinde **ölçülüyordu ama tabloda satırı yoktu**;
>   B-3 / B-4 / B-6 akışlarının tam olarak sorduğu şey.
> * **Denetçi runbook'u yazıldı:** `docs/implementation/a11y_screen_reader_audit_runbook.md`.
>
> Geriye kalan **randevu ve insan saatidir** — ikisi de repo dışıdır. Kanıt:
> `docs/releases/evidence/2026-08-12/A08_audit_readiness.md`. **Hazırlık denetim değildir;
> doğrulanmış bir ortam bir denetim değildir.**

```
Eksen   : Erişilebilirlik — insan ekran okuyucu kabul denetimi (A-08)
Durum   : BLOCKED
Ölçüm   : çıkış kriterleri 0 / 4 (defter §5) · 0 / 46 rota · 0 / 20 akış ·
          0 doldurulmuş SR-BULGU kaydı · A-08 için imzalı kalıcı sapma YOK
İzleme  : GitHub #514 — CLOSED 2026-08-07T03:52:03Z (COMPLETED), label human-only.
          İkinci kanıtsız kapatma; ilki 2026-07-30, 2026-08-03'te geri alınmıştı.
Etki    : Hiçbir belge A-08'i Complete / PASS / Done gösteremez (defter §5:293-294).
```

**#514 kanıtsız kapalıdır.** `stateReason: COMPLETED` bir **iddiadır, kanıt değildir**:
kapatma issue'nun durumunu değiştirdi, defterin içeriğini değil — ne denetçi adı, ne sürüm
dizesi, ne bulgu ekledi. Defterin kendi cümlesi: *"Closing the tracking issue satisfies
none of the four."*

**P11'in üç yeşil katmanının hiçbiri A-08 değildir.** axe koşusunun kendi çıktısı bunu
satır olarak basıyor:

```
REMINDER: A-08 is HUMAN-BLOCKED. Nothing above counts as a screen-reader PASS.
```

Otomatik tarama duyuru sırasını, okunan adı, rol/durum telaffuzunu, canlı bölge kesintisini
ölçmez. **İki çözüm yolu vardır, ikisi de insan işidir:** (A) denetimi koştur (iki
kombinasyon: NVDA/Firefox/Windows **ve** VoiceOver/Safari/macOS — tek kombinasyon A-08'i
karşılamaz) → dört kriter ☑ olunca insan #514'ü kapatır, ki (A) seçilirse #514'ün önce
**yeniden açılması** gerekir; (B) D-10 biçiminde imzalı kalıcı sapma. **Üçüncü yol yok** —
#514'ü kapalı bırakmak bir çözüm değildir, ayrışmayı yalnız görünmez kılar.

**Yan bulgu P12-B1 (düzeltilmedi):** defter iki yerde (`:50`, `:258-259`) imzalı sapmanın
`v18_visual_deviations.md`'de *"D-10 gibi"* kaydedildiğini söylüyor, ama **D-10 o dosyada
yok** (dosyadaki tek kimlik `D-1`); D-10 gerçekte
`docs/audit/current_main_ground_truth_2026-08-03.md:450` ve
`docs/implementation/a11y_ci_ratchet_and_adjudication.md:206-221`'de. İşaretçi yanlış olsa
da **kararı güçlendirir**: her iki yerde de A-08 için sapma yok.

### 6.2 Uçtan uca kabul akışları — **KAPANDI 2026-08-12 (ADIM 45)**, eski blocker 2 (P5 + P6)

> **2026-08-12 / ADIM 45 — BLOCKER 2 KAPANDI.** Bu bölümün açık kalan tek ekseni
> ("`flows` bir CI kapısı değildir") kapatıldı. Aşağıdaki her sayı **2026-08-12 CI
> koşusunundur**; ham kanıt `docs/releases/evidence/2026-08-12/` · özet
> `P6B2_flows_ci_gate.md`. Ölçüm: `origin/main` @ `853a358` + dal
> `ci/rc-blocker2-flows-gate` (PR #680). **Ürün kodu değişmedi** — yalnız harness,
> workflow ve belgeler.
>
> **1. Kapı bağlandı ve GERÇEKTEN KOŞTU.** `e2e.yml`'e yeni **`acceptance-flows`**
> job'ı: `scripts/e2e-acceptance.sh flows`. Yeni harness **icat edilmedi** — `flows`
> alt-komutu ve `scripts/lib/acceptance-flows.sh` ADIM 30'dan beri vardı.
> **Rozet kanıt değildir, job LOG'u kanıttır** (run
> [31591633498](https://github.com/alimirbagirzade/Entropia/actions/runs/31591633498),
> job **94097720164**, conclusion **success**):
>
> | Ölçüm | Değer |
> |---|---|
> | Verdict satırı | **`67 passed, 0 failed, 1 skipped`** → `E2E ACCEPTANCE OK` |
> | Harness süresi | **`duration_seconds=137`** |
> | Job wall-clock | `11:23:39Z → 11:26:35Z` = **2m56s** |
> | Yığın | 12 konteyner, **yedi düzlem** `broker-connected restarts=0` |
> | Tarayıcı katmanı | `npm ci ok` · `chromium available` · **dört yolculuk, 5 passed** |
>
> Hızlı yeşil bir koşunun geçmesi gereken kontrol **yığının gerçekten kalktığıdır**:
> `up --build` 11:23:5x, seed PASS 11:25:22, sonra yedi düzlem sağlıklı. Ham:
> `p6b2_acceptance_flows_ci_job.log` (639 satır).
>
> **Maliyet ölçüldü:** ikinci bir tam yığın (12 konteyner), ~3 dk runner. **Kardeş job**
> olduğu için `e2e`/`a11y`/`lighthouse`/`e2e-dev` ile **paralel** koşar → workflow
> wall-clock'una **~0** ekler (`lighthouse`'ın 75 dk bütçesi baskındır), yalnız dakika
> faturasına. §6.2 bu maliyeti "kabul edilemezse nightly'ye al ya da paralelleştir" diye
> öngörmüştü; **ikisi de gerekmedi. Kapsam KISILMADI, kapı advisory DEĞİL**
> (`continue-on-error` yok, `|| true` yok; `tee`'nin etrafındaki `set -o pipefail`
> taşıyıcıdır — onsuz adım tee'nin exit code'unu alır ve düşen bir koşu yeşil raporlar).
>
> **2. İki SKIP karara bağlandı — skip 2 → 1, pass 60 → 67.**
> **(ii) Tool Gateway çağrı günlüğü KAPANDI.** Seed'e task **eklenmedi** — tohumlanmış
> bir satır yalnız "uç bir fixture'ı projekte edebiliyor"u kanıtlardı. `[d5]` artık
> `[d4]`'ün directive'ini `agent-coordinator` düzlemi tükettiğinde
> `agent_loop.py::_spawn_followup_task`'ın ürettiği **GERÇEK** task'ı bekliyor
> (`source=directive` pinli, USER **403**). Aynı bekleyiş **4. tavizsiz kuralı**
> "admission KABUL EDİLDİ"den "**admission durable düzlem tarafından TÜKETİLDİ**"e
> yükseltir — kimsenin almadığı bir 202 tam da o kuralın yakalamak için var olduğu sessiz
> kusurdur ve bugüne dek buradaki hiçbir şey onu fark etmezdi. **Dürüst sınır:** günlük
> **sunuluyor** diye iddia edilir, **boş değil** diye değil (`0 call(s) logged`);
> executor'ın o an bir çağrı dağıtmış olması zamanlama olgusudur, sayı iddia etmek adımı
> güçlendirmez, **flaky** yapardı. Sayı basılır, sıfıra regresyon görünür.
> **(i) Pozitif ESP `activate`→`deprecate` SKIP KALIYOR — gerekçesi DÜZELTİLDİ.** Kayıtlı
> gerekçe "harness test vektörü sentezlemiyor"du; **yarısı doğruydu ve o yarı artık
> düzeltildi** — gerçek vektörler gönderiliyor, `vectors_run` **0 → 2**. Asıl gerekçe
> **yapısaldır**, sevk edilmiş üç değişmezin kilidi: (1) doğrulama yalnız
> `VALIDATABLE_RESOLVER_KEYS`'in **altı** kanonik anahtarı için PASS olabilir (doc 09 §7
> fail-closed); (2) `seed.py::_ESP_TA_RESOLVERS` `SEED_ESP_TA=1` altında **altısını da**
> `trusted_active` tohumlar (tarayıcı katmanının Pre-Check'i onları çözebilsin diye);
> (3) `esp/state_machine.py::_ALLOWED` aktivasyona **yalnız `candidate`'ten** izin verir,
> `deprecated` ise `unavailable` dışında terminaldir. **KESİŞİM BOŞ** — `SEED_ESP_TA`
> yığınında hem doğrulanabilir hem etkinleştirilebilir bir anahtar YOKTUR ve hiçbir çağrı
> sıralaması onu yaratmaz. Kapatmak ya `SEED_ESP_TA`'sız **ikinci** bir Compose yığını
> (tek bir iddia için yepyeni 12 konteynerlik job) ya da `seed.py` değişikliği (**ürün
> kodu**, bu slice'ın kapsamı dışı) ister. In-process kapsam duruyor:
> `backend/tests/integration/test_esp_persistence.py`. Sevk edilmiş doğrulayıcıya karşı
> **ölçüldü** (`p6b2_esp_vector_local_proof.txt`): probe anahtar → `failed / 2`, eski
> string → `failed / 0`, `ta.sma/ema/rma/wma` → **`passed / 2`** — yani vektörler her MA
> varyantı için **aritmetik olarak doğrudur**, red **anahtar** yüzündendir, düşsün diye
> ayarlanmış bir yük yüzünden değil. **İki yeni pin bu kararı çürümekten korur:** `[c2]`
> `validation_state=failed`'i pinler (rastgele bir anahtar sertifikalanabilir hale
> gelirse kapı **kırmızıya** döner ve bu karar yeniden açılmaya zorlanır), `[c5]` ise
> **`409 RESOLVER_VALIDATION_REQUIRED`**'ı pinler — `_ensure_validation_passed` önce
> `_ensure_activation_evidence`'ı çağırdığı için eski string yükte red iki kapıdan biri
> olabilirdi ve "200 değil" ikisini ayırt edemezdi.
>
> **3. Skip tavanı — kapıyı bağlamanın açtığı deliği kapatır.** SKIP koşuyu düşürmez;
> yerel komut için sorun değildi, **kapı** için şu demek: sessizce **koşmayı bırakan** bir
> adım (kaybolmuş tarayıcı zinciri, tohumlanmayan fixture, geçerken eklenmiş bir
> `af_skip`) kapıyı yeşil tutarken dünden **az** ölçer — kapının önlemek için bağlandığı
> "regresyon sessizce geri gelebilir" kusurunun bir kat yukarısı. `E2E_MAX_SKIPS`
> **karara bağlanmış** sayıyı pinler (CI: **1**); tanımsız = tavan yok, yani yerel koşu ve
> `install-acceptance.yml` (`legacy`, sıfır skip) **etkilenmez**. Skip'e izin belgesi
> **değildir** — yükseltmek bir §6.2 kararıdır ve hata mesajı bunu söyler.
>
> **4. Concurrency (brief'in 3. kalemi) — premisi BAYATTI.** Brief `ci.yml` kusurunu bu
> kapı için "ÖLÜMCÜL" saydı; kusur **ADIM 34'te onarılmıştı ve hâlâ onarılıdır**:
> `ci.yml:9-14` ve `e2e.yml:10-12`'nin ikisi de
> `cancel-in-progress: ${{ github.ref != 'refs/heads/main' }}` taşır → main'de **false**.
> Yeni job **e2e.yml'e** kondu ki **zaten doğru olan** bloğu miras alsın; ikinci bir blok
> yazmak kusurun geri dönmesi için ikinci bir şans olurdu. Tarihsel hasar API'den
> doğrulandı ve **tam olarak** kaydedilir: `e8d1d48` (#633) CI run `31189395028` ve
> `bc59dae` (#634) CI run `31189634665` — ikisi de `cancelled`, **`total_jobs=0`**.
> **Önemli incelik:** iptal edilen koşu her iki SHA'da da **`CI`**'dır;
> `E2E`/`Security`/`Performance`/`Install acceptance` o SHA'larda **başarılıdır** — yani
> **`e2e.yml` hiç kurban olmadı**. "CI'ları hiç koşmadı" ifadesi "hiçbir şey koşmadı" diye
> okunmasın diye böyle yazıldı. Ham: `p6b2_concurrency_verification.txt`.
>
> **KAPANMAYANLAR (bu bölüm onları kapatmaz):** **P11-1 branch protection** — bir
> **required status check** kuralı olmadan kırmızı bir check merge'i **fiilen
> durduramaz**; bu bir depo ayarı ve **insan kararıdır**. O ayar konana dek bu kapı dürüst
> rapor verir ama merge düğmesini tutmaz. **Blocker 1 (A-08)** dokunulmadı; **verdict
> A-08 açıkken hâlâ BLOCKED**, blocker sayısı **2 → 1**.

> **2026-08-10 / ADIM 30 güncellemesi.** Bu bölüm 2026-08-07'de yazıldı ve iki iddia
> taşıyordu. Her ikisi de **yeniden ölçüldü**; biri düzeltildi, biri kısmen kapandı.
> Aşağıdaki her sayı **2026-08-10 koşusunundur**, 08-07 kaydından kopyalanmamıştır.
> Ham kanıt: `docs/releases/evidence/2026-08-10/` · özet:
> `P6B_acceptance_flows_harness.md`. Ölçüm ağacı `origin/main` @ `aabb85d` + dal
> `fix/rc-blocker2-acceptance-harness`; `1f4b88b..aabb85d` arasında `backend/src`,
> `frontend/src` ve `frontend/e2e` **birebir aynıdır**, yani kanıt aday için geçerlidir.

**1. iddia — "Docker/OrbStack takılı (`docker ps` sürekli 124)": YENİDEN ÜRETİLEMEDİ.**
Aynı makinede `docker version` **0**, `docker compose version` **0** (29.4.0 / v5.1.2),
`timeout 20 docker ps -q` **0** ve `timeout 20 docker images -q` **0** — dördü de anında
döndü. Raporun *kaynak baskısı* teşhisi doğrudur (host 8 GB, VM **3.89 GiB**, ölçüm anında
18–21 konteyner koşuyor, load tepe **18.08**), ama ondan çıkarılan **daemon takılı** sonucu
bugün geçerli değildir: izole yığın bu baskının altında sorunsuz ayağa kalktı ve P5'in
2/3/4 kalemleri ile bu bölümün beş akışı **koşuldu**. Ham: `p6b_docker_remeasure.txt`.

> **NOT — 2026-08-10 / ADIM 36.** "Docker takılması" teşhisi bundan sonra **kendi kendini
> ayırt eder**: `e2e-acceptance.sh` preflight'ı artık sınırlıdır ve üç durumu üç ayrı
> mesajla verir — daemon **yok** (anında `exit 2`, "not reachable"), daemon **takılı**
> (sınırlı sürede `exit 2`, "HUNG, not absent"), harness koştu ama bir adım **düştü**
> (`exit 1`). Yani bir sonraki başarısız koşu, teşhisi doğru yere koyacak kanıtı kendisi
> üretir; bugün bir insanın "takıldı mı, yok mu?" diye tahmin etmesi gerekmiyor.
> **Bu, "Docker düzeldi" demek DEĞİLDİR** — ADIM 36 daemon'a hiç dokunmadı ve o gün daemon
> zaten normal cevap veriyordu. **P5/P6 blocker'ı da KAPANMADI:** bu bölümün açık kalan
> ekseni kapsam boşluğu ve `flows`'un CI kapısı olmaması (aşağıdaki "Blocker neden hâlâ
> AÇIK" bloğu), ADIM 36 ise yalnız §6.7'nin P6-ek/P6-6 kalemlerini kapatır (§6.7.4).

**2. iddia — "beş akışın hiçbiri hiçbir katmanda doğrulanmadı": (a) ve (b) için YANLIŞTI.**
Terim taraması **yalnız iki shell dosyasını** kapsıyordu ve o kapsamda doğrudur; hatalı olan
oradan "hiçbir katmanda" genellemesine geçmektir. **Tarayıcı katmanı atlanmıştır.** Aday
SHA'da GitHub Actions **E2E** run **31364211010** (branch `main`, head `aabb85d`,
conclusion **success**, 5m34s) şunları koşmuştur: `05-mainboard-ready-check-run.spec.ts`
**✓ 8.2s** = akış (a) · `20-library-request-validation.spec.ts` **✓ 7.2s** = akış (b) ·
`06-trash-reauth.spec.ts` **✓ 2.3s** = akış (e)'nin delete→purge ayağı ·
`04-create-package-lifecycle.spec.ts` **✓** · `18-result-artifacts-drilldown.spec.ts` **✓✓**
— suite **39 passed**. Ham: `p6b_ci_browser_layer.txt`.

**Gerçekten hiçbir katmanın kapsamadığı kalemler şunlardı:** **(c)** ESP lifecycle + export ·
**(d)** Agent / Trading Signal tool yüzeyleri · **(e)**'nin **restore** ayağı (spec 06 onu
atlıyor) · ve dört tavizsiz kuralın tamamı. Blocker'ın asıl içeriği buydu.

**Bu dalgada yazılan kapsam.** Yeni harness **icat edilmedi**: `scripts/e2e-acceptance.sh`'e
beşinci alt-komut (`flows`) eklendi, gövdesi `scripts/lib/acceptance-flows.sh`'e kondu;
izolasyon sözleşmesi, hermetik env, `dc`/`req` ve PASS/FAIL sayacı aynen yeniden kullanıldı.
Var olan yolculuklar **yeniden yazılmadı, koşuldu**; sunucu katmanı yalnız hiçbir katmanın
kapsamadığını ekler. Terim taraması aynı yöntemle: `ready-check|readiness` 0 → **17**,
`trash|purge` 0 → **43**, `restore` 0 → **19**, `library` 0 → **32**, `Idempotency-Key`
0 → **17**, `embedded-system-package` 0 → **9** (`p6b_term_scan.txt`).

**Koşu sonucu:** `./scripts/e2e-acceptance.sh flows` → **60 passed / 0 failed / 2 skipped**,
**exit 0**; tarayıcı katmanı **5 passed (23.8s)**. Beş akışın **beşi de PASS**. Dört tavizsiz
kural varsayılmadı, iddia edildi: TS/TL paket değil (katalogda yok, paket kökü TS yüzeyinde
**404**) · reddedilen run Results düzlemini **0 → 0** bıraktı · **on** Admin/owner yüzeyi
plain USER token'ı ile yeniden saldırıya uğradı ve hepsi **403** verdi · purge **202** +
`purge_job_id`, directive **202**, yedi düzlem broker-connected. O-30 doğrulandı:
`deletion_state` = `root_lifecycle_state` = `purge_pending`. Ham: `p6b_flows_run.txt`.

**İki SKIP, PASS değildir:** (i) pozitif ESP activate→deprecate koşulmadı — probe resolver
`validation_state=failed / vectors_run=0` veriyor ve harness test vektörü sentezlemiyor;
onun yerine **doğrulanmamış resolver trusted-active'e yükseltilemiyor** iddia edildi
(pozitif yol in-process: `backend/tests/integration/test_esp_persistence.py`). (ii) Tool
Gateway çağrı günlüğü egzersiz edilmedi — taze tohumlanmış yığında agent task yok.

**P5'in bloke kalemleri de koşuldu:** servis bazında health `acceptance.sh` **exit 0**
(15 servis, hiçbiri exited/restarted/unhealthy) · `smoke.sh` **exit 0** ·
`worker-restart-smoke.sh` **exit 0** — yedi düzlem SIGKILL + restart sonrası
`package_root` 15→15, `audit_events` 69→69, `outbox_events` 40→40, **mükerrer artefakt yok**.
Üç auth modunun sonucu §6.2.1'dedir.

> **~~Blocker neden hâlâ AÇIK.~~ — 2026-08-12 (ADIM 45) İTİBARIYLA GEÇERSİZ; kayıt için
> duruyor, silinmedi.** O tarihte yazılan gerekçe şuydu: *"Kapsam boşluğu kapandı ve beş
> akış koştu, ama **`flows` bir CI kapısı değildir** — yerel bir komuttur, hiçbir workflow
> onu koşmaz, dolayısıyla bir regresyon sessizce geri gelebilir. Kapıya bağlamak ayrı bir
> karardır (CI'da 12 konteynerlik ikinci bir yığın + koşu süresi) ve bu slice'ta
> **yapılmadı**. Yukarıdaki iki SKIP de açık iştir."*
>
> **Üçü de kapatıldı.** Kapı `e2e.yml::acceptance-flows` olarak bağlandı ve koştu
> (**67 passed / 0 failed / 1 skipped**, job **94097720164**); maliyet ölçüldü (~3 dk,
> paralel kardeş job → workflow wall-clock'una ~0); SKIP (ii) **kapandı**, SKIP (i)
> **yapısal** gerekçeyle kayda geçti. Ayrıntı bu bölümün başındaki **ADIM 45** bloğunda.
> Bu yüzden kayıt artık "kısmen kapandı" değil, **KAPANDI**'dır — ama §8'in verdict'i
> **BLOCKED** kalır, çünkü blocker 1 (A-08) açıktır.

#### 6.2.1 Üç auth modu (P5 kalem 2) — 2026-08-10 koşusu

2026-08-07'de üçü de **BLOCKED — hiç koşmadı** kaydedilmişti. Bugün, aynı makinede, her biri
kendi izole Compose projesinde ve kendi volume'larıyla koşuldu:

| Akış | Komut | Exit | Sonuç |
|---|---|---:|---|
| §9.4 session-clean | `./scripts/e2e-acceptance.sh session` | **0** | **PASS** — 27 passed / 0 failed / 0 skipped (14 adım + yedi düzlem + `acceptance.sh` kapısı) |
| §9.5 legacy-upgrade | `./scripts/e2e-acceptance.sh legacy` | **0** | **PASS** — 15 passed / 0 failed / 0 skipped (credentialless `user_admin` korunarak session'a yükseltme, satır birebir aynı) |
| §9.6 dev-auth | `./scripts/e2e-acceptance.sh dev-auth` | **0** | **PASS** — 9 passed / 0 failed / 0 skipped (`X-Actor-Id` impersonation, Bearer yok sayılıyor) |

Ham: `p5b_three_auth_modes.txt`. Bu üç akış **bu dalgada değişmedi** — 08-07'de de aynı
kodla oradaydılar; değişen tek şey, koşabilmiş olmalarıdır.

**Bu bölümün eski hâli, kayıt için.** 2026-08-07'de burada yazan gerekçe şuydu: harness
kapsam boşluğu (a)–(e)'yi hiç uygulamıyor **ve** uygulama düzlemi hiç ayağa kalkmadı
(API:8000 / web:5173 kapalı, `docker ps` **124**), P5'in 2/3/4 ve P8'in 1b kalemleri aynı
kök nedende. O gün hiçbir katmanda kanıtlanmadığı yazılan liste: beş akış · üç auth modu ·
servis bazında health · `smoke.sh` · `worker-restart-smoke.sh`. Yukarıdaki ölçümler bu
listenin tamamını yeniden ele almıştır; **silinmedi, yerine ölçüm konuldu.**

### 6.3 Alertmanager — **KAPANDI 2026-08-10 (ADIM 31)**, eski BLOCKER (P10 §5.3)

> **Bu bölümün eski hâli** "Alertmanager YOK — **BLOCKER**" idi. Aşağıda önce o
> tespitin **bu koşuda yeniden ölçülmüş** hâli, sonra kapanış kanıtı var. Rapordaki
> sayılar kopyalanmadı; `docs/releases/evidence/2026-08-10/p10b_preexisting_state.txt`
> onları `origin/main` üzerinde yeniden üretir.

#### 6.3.1 Eski durum — yeniden ölçüldü, doğrulandı

| Rapor iddiası | `origin/main` (`20108af`) üzerinde ölçülen | Doğru mu? |
|---|---|---|
| `prometheus.yml` içinde `alerting:` bloğu yok | `grep -n '^alerting:'` → **eşleşme yok** | ✅ |
| `docker-compose.yml`'de Prometheus servisi yok | `grep -nE '^  (prometheus\|alertmanager):'` → **ikisi de yok** | ✅ |
| Repo genelinde receiver / routing / silence / on-call yok | `ops/ scripts/ .github/ backend/src/` içinde 3 dosya eşleşiyor, **hepsi yokluğu anlatan YORUM** — tek satır yapılandırma yok | ✅ |
| 11 kural, 7'si page | `grep -c '^      - alert:'` → **11** · `severity: page` **7**, `severity: ticket` **4** | ✅ |
| promtool kapısı | CI job `alerts` / `Alert rules — promtool` → `scripts/alert-rules-gate.sh`, **exit 0** | ✅ |

Yani §6.3'ün tespiti maddeten doğruydu: doğrulanmış 11 kural, hiçbiri bir insana ulaşmıyordu.

#### 6.3.2 Karar ve kapanış

**(A) sevk edildi. (B) imzalı sapma SEÇİLMEDİ** — eksik olan bir on-call *organizasyonu*
değil, bildirim *yolunun kendisiydi*, ve o yol repo içi yapılandırmadır.

```
metrik üretimi  →  scrape config  →  kural değerlendirme  →  ateşleme  →  BİLDİRİM  →  insan
   ✅ 7 aile        ✅ entropia-api    ✅ promtool PASS       ✅ 11/11      ✅ VAR      ✅ ULAŞTI
```

**Sevk edilen:**

| Kalem | Dosya | Ne yapar |
|---|---|---|
| Routing ağacı | `ops/alertmanager/alertmanager.yml` | `severity: page` → `entropia-page` (repeat 1h), `severity: ticket` → `entropia-ticket` (repeat 12h) — **iki AYRI receiver, iki AYRI zamanlama**. Kök receiver **gerçek**: eşleşmeyen alarm düşürülmez, page eder. 3 inhibit kuralı (hepsi **aşağı** yönlü). |
| Fail-closed başlatıcı | `ops/alertmanager/entrypoint.sh` | `ALERTMANAGER_NOTIFY_URL` **unset / boş / http(s) değilse → exit 78, Alertmanager BAŞLAMAZ**. Placeholder receiver yok, `/dev/null` route yok, `receiver: null` yok. |
| `alerting:` bloğu | `ops/prometheus/prometheus.yml` | Ateşleyen alarmı değerlendiriciden çıkarıp Alertmanager'a verir. |
| Servisler | `docker-compose.yml` (profil `observability`) | Düz `docker compose up` **etkilenmez** — kabul script'lerinin getirdiği yığın birebir aynı kalır. |
| CI kapısı (config) | `scripts/alert-notification-gate.sh` + `backend/tests/contract/test_alert_notification_contract.py` | `amtool check-config` + `amtool config routes test` + **21 yapısal test**. |
| Uçtan uca kanıt | `scripts/alert-notification-proof.sh` | **CI kapısı DEĞİL** — dürüst sınır, §6.7'ye kaydedildi. |

**Ölçülen kanıt (2026-08-10, `docs/releases/evidence/2026-08-10/`):**

| Faz | Ne kanıtlandı | Sonuç |
|---|---|---|
| 1 | Boş hedefle Alertmanager **başlamaz** | **exit 78** + değişken adını söyleyen mesaj · URL olmayan değerle de **exit 78** |
| 2 | Sevk edilen çift, sevk edilen config'lerle ayağa kalkar | `prometheus` + `alertmanager` **ready** |
| 3 | **PROVENANCE** — yürürlükteki config bu ağacınki | çalışma ağacı / mount / staged sha256 **üçü de `f1c1949c…`** · `--config.file=/tmp/ops/prometheus/prometheus.yml` · parse edilmiş config `entropia-api`, `api:8000`, `alertmanager:9093`, `entropia.rules.yml`, `deployment: entropia` taşıyor · yüklenen kural seti **11 = 11, diff boş** |
| 4 | **DELIVERY** — gerçek bir alarm alıcıya ulaşır | `EntropiaApiDown` ateşledi (`up{job="entropia-api"} == 0` — **sentetik seri yok**, `api` servisi hiç koşmuyor) ve alıcıya **`"receiver": "entropia-page"`, `"alertname": "EntropiaApiDown"`, `"severity": "page"`** olarak ulaştı |

`scripts/alert-notification-proof.sh` **exit 0**. Ham çıktı: `p10b_notification_proof.txt`.

**"promtool PASS" bunu neden KANITLAMAZDI — ve hâlâ kanıtlamaz.** O job'ın söylediği tek
şey kuralların *doğru* olduğudur. **Doğru bir kuralın kime gittiğini o job hiç sormaz.**
CI job'ı bu yüzden `Alert rules — promtool` → **`Alert rules and notification path`**
olarak yeniden adlandırıldı: eski ad daha güçlü bir iddia olarak okunuyordu.

#### 6.3.3 KAPANMAYAN ARTIK — açıkça kayıtlı

§6.3'ün **iki** doğrulanmamış noktası vardı. **İkincisi kapandı** (provenance kapısı artık
var, faz 3). **BİRİNCİSİ KAPANMADI:**

> **Kurallar gerçek production serilerine karşı hiç değerlendirilmedi.** `promtool test
> rules` sentetik seri kullanır; ADIM 31'in uçtan uca kanıtı **tek bir yapısal kuralı**
> (`up == 0`) ateşler. Gerçek trafiğe göre yanlış ayarlanmış bir eşik hâlâ *doğru* görünür.

Bu **bu slice'ta kapanamaz** — yalnız gerçek trafik biriktikçe kapanır. Repo içindeki
hiçbir kapı onu kapatamaz. **Kalıcı imzalı sapma DEĞİLDİR** ve öyle kaydedilmemiştir;
süreli bir kayda dönüştürülmesi istenirse **imzayı agent atayamaz**. Tam liste:
`docs/runbooks/alert-notification.md` §5 (5 madde: production serisi · monitörü izleyen yok ·
delivery proof CI kapısı değil · on-call rotasyonu/ack yok · kuyruk bazında worker liveness yok).

### 6.4 react-router `GHSA-qwww-vcr4-c8h2` — freeze **DÜŞÜRÜLDÜ**, blocker **KAPANDI** (P9-B2)

> **KAPANIŞ BİÇİMİ İMZA DEĞİL, KALDIRMA.** PO kararı kaydın allowlist'e **taşınması**
> yönündeydi ve imza sahibi de verilmişti (owner `Ali Mirbagirzade`, expires
> `2026-11-10`). O kayıt **yazılmadı** — çünkü aynı talimatın *"Bunu YENİDEN DOĞRULA —
> bayatlamış olabilir"* maddesi uygulandığında öncülün kendisi çürüdü. **Bir imza,
> ortada olmayan bir açığa atılamaz.** Kabul edilen bir risk değil, **var olmayan** bir
> risk söz konusu; blocker kökünden kapandı.

**2026-08-12'de yeniden türetilen olgular** (ADIM 44, iki bağımsız kaynak):

| Boyut | 2026-08-07 kaydı | 2026-08-12 ölçümü |
|---|---|---|
| Advisory kapsamı | `>=7.12.0 <8.3.0` — "her 7.x etkilenir" | **RE-SCOPED**: `>=7.12.0 <7.18.2` (**first_patched 7.18.2**) **+** `>=8.0.0 <8.3.0` |
| Yamalı hat | yalnız `8.3.0+` (v8 migrasyonu) | **7.18.2 de yamalı** — 7.x hattına backport edildi |
| Kurulu ağaç | `react-router` 7.18.2, `dev=false` | **değişmedi** — 7.18.2, `react-router-dom@7.18.2` onu **birebir pinliyor** |
| `npm audit` (frontend) | high advisory raporlanıyor | **`found 0 vulnerabilities`**, high=0 critical=0 |
| Kapının kendi notu | — | *"GHSA-qwww-vcr4-c8h2 is frozen but no longer reported — drop it from the list."* |
| Risk argümanı | BrowserRouter, RSC yok | **hâlâ doğru** (`main.tsx:22`; `frontend/src`'de RSC API'si yok, tek router import specifier'ı `react-router-dom`) — ama artık **gereksiz**: savunulacak açık kalmadı |

Kaynaklar: `gh api /advisories/GHSA-qwww-vcr4-c8h2` (`updated_at 2026-08-07T18:16:54Z`,
`withdrawn_at: null`) **ve** `npm audit --json` — biri yanılsa öteki yakalardı.

**Zamanlama, kayıt için.** `react-router@8.3.0` 2026-07-22'de, advisory 2026-07-24'te,
**`react-router@7.18.2` 2026-07-28'de** yayınlandı. Yani repo, düzeltilmiş sürümün
üzerinde **on bir gündür oturuyordu**. Advisory metadata'sı 2026-08-07T18:16:54Z'de
yetişti — P9-B1'i (PR #637) merge eden commit'ten **yirmi dakika sonra**. Bu, aynı
desenin **üçüncü** tekrarı: brace-expansion çifti (2026-08-03) ve js-yaml (2026-08-07,
yaması freeze'den **yedi gün önce** yayındaydı). Gerekçesi çürümüş bir freeze, freeze
olmamasından **kötüdür** — kimsenin yeniden bakmadığı bir istisnayı sessizce verir.

**Asimetri de kapandı — silinerek.** Blocker'ın yapısal yarısı ("`FROZEN_ADVISORIES`
`owner`/`expires` istemiyor") bir belge notuyla değil, **ikinci evin kaldırılmasıyla**
çözüldü: `FROZEN_ADVISORIES` literal'i **yok**, `scripts/npm-audit-gate.mjs` artık
`.github/security-allowlist.json`'ı okuyor, iki kapı da ortak
`scripts/lib/security-allowlist.mjs`'ten geçiyor ve **ikisi de tüm listeyi expire
ediyor** (npm kapısı `ci.yml`'da her push/PR'da koşar, container kapısı
`security.yml`'da — her kapı yalnız kendi scope'unu expire etseydi bir istisnanın
takvimi *hangi workflow'un koştuğuna* bağlı olurdu). **İmzasız bir npm freeze
yazılabilecek yer kalmadı.** Negatif kanıt koşuldu: `owner`'sız kayıt → exit 1 · süresi
geçmiş kayıt → exit 1 (**npm kapısında**) · bildirilmemiş scope → exit 1 · kayıtsız
gerçek high advisory → exit 1 · doğru id + **yanlış paket** → exit 1. Pinleme:
`backend/tests/contract/test_security_freeze_discipline_contract.py` (7 test).

`entries` **boş** ve boş kalması hedeftir. Hiçbir bağımlılık sürümü değiştirilmedi;
downgrade yapılmadı.

> **Karşıt kayıt, adalet için:** P9'un **B1** blocker'ı (js-yaml) da aynı desenle
> kapanmıştı (PR #637, merged `2026-08-07T17:56:59Z`). **P9'un iki blocker'ı da artık
> kapalıdır** — ikisi de "gerekçe çürüdü" ile, hiçbiri imzayla değil. Bu tesadüf değil:
> bu repoda bir freeze'in en olası sonu, gerekçesinin bayatlamasıdır. `expires` alanı
> tam olarak bunun için var.

### 6.5 K-2..K-6 — ölçüldü, **K-6b hariç düzeltilmedi**, bilerek gate DIŞI

`docs/audit/a11y_screen_reader_audit_results.md` §6. Dördü **"Open — reported, not
gated"** statüsünde; hiçbiri CI'ı kırmaz, hiçbiri imzalı sapmaya bağlanmış değildir.
**ADIM 48'de K-6 İKİYE ayrıldı** (aşağıdaki tabloda `K-6a` / `K-6b`): ölçülebilir kontrast
yarısı **kapandı**, insan-gözü yarısı **açık kaldı**.

| # | Bulgu | Kapsam | WCAG | Statü |
|---|---|---|---|---|
| **K-2** | **Skip link yok** — her route'ta ilk tabbable öğe shell'in `Log out` butonu; her sayfa tüm menü çubuğunu tab'layarak başlıyor | **23 / 23 route** | 2.4.1 | Open — reported, not gated |
| **K-3** | **`contentinfo` landmark yok** — shell hiç `<footer>` render etmiyor; checklist A-2 dört landmark bekliyor, üç var | **23 / 23 route** | 1.3.1 / 2.4.1 | Open — reported, not gated |
| **K-4** | **`/user-manual`'da `<h1>` yok** — kendini `<h2 class="page-title">` ile adlandırıyor (`UserManual.tsx:181`); diğer her route `<h1>` kullanıyor | 1 route | 1.3.1 / 2.4.6 | Open — reported, not gated |
| **K-5** | **Başlık hiyerarşisi h2'yi atlıyor** — `h1 → h3` doğrudan (ör. `/backtest/run`: `h1 "RUN & Backtest Results" → h3 "Composition"`); setin **en yüksek erişimli** yapısal gözlemi | **21 / 23 route** | 1.3.1 (A-3) | Open — reported, not gated |
| **K-6a** | **Odak göstergesi computed style ile saptanamıyor** — `outline: none; box-shadow: none`; UA varsayılan halkası hâlâ boyanıyor olabilir, computed-style probu onu göremez | probe: 1 element | 2.4.7 | Open — **insan gözü gerekiyor** |
| **K-6b** | **Odak halkasının kontrastı 3:1'in altında** — `:focus-visible` halkası `var(--accent)` (`#00a9e8`) idi: beyazda **2.68:1**, `#f5f5f5`'te **2.46:1**, `.dropdown-blue` üzerinde **1.00:1**; uygulamadaki **15 zeminin hiçbirinde** eşiği geçmiyordu | her odaklanabilir düğüm, **23 / 23 route** | **1.4.11** | **KAPANDI (ADIM 48, 2026-08-12)** — halka `var(--text)`; beyaz **15.91:1**, en kötü zemin `#0092c8` **4.50:1** |

**K-5 ve K-6a doğrudan A-08'e bağlıdır:** K-5'in cevabı (rotor başlık gezinmesi gerçekten
yanıltıyor mu) **21 sayfanın outline'ını yeniden kesmeyi önermeden ÖNCE** verilmelidir;
K-6a tam olarak otomasyonun karara bağlayamayacağı sınıftır. A-08 koşulmadığı için ikisi de
**cevapsızdır**.

**K-6b neden kapatılabildi, diğerleri neden hayır.** 3:1 **sayısal bir AA eşiğidir**, halka
rengi v18 mockup'ında **hiç tarif edilmemiştir** (kanonda odak durumu yok → sapma değil), ve
düzeltme hiçbir yerleşimi değiştirmeyen **tek bir deklarasyondur**. Diğerlerinin çaresi
(footer eklemek, 21 sayfanın başlık ağacını yeniden kesmek) **ürün kararıdır**. **Bu kalem
D-10 DEĞİLDİR:** D-10 **1.4.3** (metin) ekseninde imzalı kalıcı sapmadır; K-6b **1.4.11**
(metin-dışı) ölçütüdür — ayrı ölçüt, ayrı eşik, ve `--accent` token'ına **dokunulmadı**.
**axe bu kuralı koşmuyordu** — a11y ratchet'inin yeşil olması bu soru için kanıt değildi.

### 6.6 İzleme kaydı ↔ kod ayrışması — tekrarlayan desen (P8 §4.3, P10 §3.3)

Aynı desen **beş issue'da** ölçüldü: iş açık, izleme COMPLETED kapalı, kayıtlı karar yok.

| # | Tür | closedAt | Ölçülen gerçek durum |
|---|---|---|---|
| **#514** | A-08 human audit | `2026-08-07T03:52:03Z` | defter BOŞ, 0/4 kriter (§6.1) |
| **#558** | product decision (bundle time-policy pin) | `2026-08-07T03:53:57Z` | **strict xfail bugün hâlâ düşüyor**; yorum sayısı 0, etiket hâlâ `product-decision` |
| **#559** | product decision (DST fold/gap) | `2026-08-07T03:53:36Z` | davranış karakterize, **canon hâlâ sessiz** |
| **#617** | N+1 `readiness_check.market_data_leg` | 2026-08-06 08:55 | ~~`per_item=1` **hâlâ canlı**, kaynak döngü içi await taşıyor~~ → **2026-08-12 (ADIM 46): AYRIŞMA KOD TARAFINDAN KAPANDI** — `per_item` ölçülen **0**, döngü içi await kalktı. İzleme kaydı **insan kararı** |
| **#618** | N+1 `dependency_pins` | `2026-08-07 03:53` | ~~`per_item=2` **hâlâ canlı**~~ → **2026-08-12 (ADIM 46): AYRIŞMA KOD TARAFINDAN KAPANDI** — `per_item` ölçülen **0**. İzleme kaydı **insan kararı** |

Karşıt kayıt: **#557 meşrudur** — düzeltildi, marker kaldırıldı, test bugün PASS. **#556**
kod tarafı düzeltildi ama `unified_portfolio_oracle_acceptance.md` A17'ye göre **market
yarısı açık**.

**Sonuç:** A17 çıkış kriteri *"tests green **unweakened**"* strict xfail durdukça
**karşılanmamıştır**. Issue yeniden açmak **insan kararıdır**; bu dalgada hiçbir issue
açılmadı/kapatılmadı.

> **2026-08-12 güncellemesi.** Beş satırın durumu artık tek tip DEĞİL, karışmasın:
> **#617 ve #618'in KODU kapandı** (ADIM 46 — `per_item` ikisinde de ölçülen **0**,
> ratchet sıkıldı, negatifi kanıtlandı); **#514 / #558 / #559'un kodu AÇIK KALDI** ve bu
> slice onlara **hiç dokunmadı** — A-08 defteri hâlâ **boş** (0/4), strict xfail hâlâ
> yerinde. Bu tablonun asıl bulgusu *"kod açıkken izleme kapalı"* ayrışmasıydı;
> **#617/#618'de ayrışmanın kod yarısı kapandı, izleme yarısı bir insan kararıdır** ve
> bir agent tarafından kapatılamaz. **Hiçbir issue'nun kapanışı bu slice'ın kanıtı
> sayılamaz** — kanıt ölçümdür, issue durumu değildir.

### 6.7 Blocker olmayan ama kapanmamış kalemler

| # | Bulgu | Kaynak |
|---|---|---|
| ~~**P4-1**~~ | ~~`alembic check` **exit 255** (40 gerçek index-adı sapması) ve **hiçbir CI workflow'u onu koşmuyor** → sahipsiz, izlenmeyen~~ → **2026-08-10 (ADIM 34) KAPANDI** — 40 sapmanın 40'ı kapatıldı (index ekseni ölçülen **0**), kapı CI'ya bağlandı ve negatifiyle kanıtlandı. **`alembic check` yine de exit 255**, ayrı bir sınıf yüzünden — ayrıntı ve ham kanıt: **§6.7.3** | P4 |
| ~~**P4-2**~~ | ~~`agent_event.seq`'te alembic yolunda fazladan non-unique index; `create_all` yolunda yok → iki kurulum yolu bu noktada bit-özdeş değil (fonksiyonel etki yok)~~ → **2026-08-10 (ADIM 34) KAPANDI** — iki kurulum yolu index ekseninde **bit-özdeş** (361/361, 0 sapma); fonksiyonel etkisizlik deneysel kanıtlandı. Ayrıntı: **§6.7.3** | P4 |
| **P4-3** | **YENİ (ADIM 34 ölçümü, rapor bunu bildirmemişti).** §6.7'nin *"tip/server-default değişimi = 0"* iddiası **yanlıştı**: aynı `alembic check` koşusu **60 `modify_default`** işlemi de emitliyor (40 tabloda 60 kolon; DB'de server default var, model onu yalnız Python tarafında bildiriyor). P4-2 ile aynı aileden gerçek bir model↔migration ayrışması; **ölçüldü, düzeltilmedi** (modele `server_default` eklemek `create_all` şemasını değiştirir → ayrı karar, ayrı PR). Sayı ADIM 34 kapısında **tavana** bağlandı: büyüyemez | P4 |
| **P10-B2** | ~~9 uçta sayfalama sınırı **şemada yayımlanmıyor**~~ → **2026-08-11 (ADIM 37): YAYIMLAMA KAPANDI, AŞIM DAVRANIŞI AÇIK.** Dokuz ucun dokuzu da artık default + tavan bildiriyor (`x-clamp-default` / `x-clamp-maximum`), kapı + negatif kanıt bağlı, `UNPUBLISHED = 0`. ~~**Kalem KAPANMADI:** aşımın sessiz clamp mi 422 red mi olacağı bir **ürün kararıdır**, canonical **sessizdir** ve bu slice onu **VERMEDİ** → **PO kararı bekliyor**.~~ → **2026-08-12 (ADIM 47): KALEM KAPANDI.** PO **kelepçenin kalmasına** karar verdi (422'ye çevrilmez); gerekçe kayda geçti — sınır artık yayımlandığı için davranış **sessiz değil**, ve 422 üretilmiş istemcileri kırardı. **19 ENFORCING / 9 CLAMPING ayrımı bilinçlidir.** Kod davranışı değişmedi; iki invariant (clamped → `x-clamp-maximum` VAR, `maximum` YOK) testte kilitli. **P10-B6 açık kalır.** Raporun *"sessizce 100'e iniyor"* ifadesi de düzeltildi: 5 uçta `meta.limit` etkin değeri **zaten yankılıyordu**, 1 uçta gerçekten sessiz. Ayrıntı, adjudication ve ham kanıt: **§6.7.5** | P10 |
| **P10-B6** | **YENİ (ADIM 37 ölçümü, rapor bunu bildirmemişti).** Dört uç uyguladığı **etkin** sayfa boyutunu yanıtta yankılamıyor: `/agent-tasks`, `/lab/messages`, `/hypotheses` (`next_cursor` var, `limit` yok) ve `/agent-tasks/{task_id}/tool-calls` (**hiçbir sayfalama metadata'sı yok** — ne cursor, ne has_more, ne limit). MTR §8'in `Response meta.pagination` sözleşmesiyle ayrışır; ama sevk edilen `meta: {cursor, has_more, limit}` şekli **zaten** MTR §8'in ad ekseninden ayrı → bu dört uçtan büyük, daha eski bir sapma. **Ölçüldü, düzeltilmedi** (yanıt gövdesi = wire contract; `lib/*.ts` + typed `AgentToolCallListResponse` okuyor → ayrı karar, ayrı PR) | ADIM 37 |
| ~~**P9-F2**~~ | ~~**SPA origin'inde CSP yok** — `frontend/nginx-security-headers.conf` CSP vermiyor; yürütülebilir bundle'ı sunan origin budur. API'de CSP var ve testli; statik origin için **hiçbir test/kapı/belge yok**~~ → **2026-08-10 (ADIM 32) KAPANDI** — politika sevk edildi, canlı yanıtta ölçüldü, CI kapısına bağlandı. Ayrıntı ve ham kanıt: **§6.7.1** | P9 |
| ~~**P9-F1**~~ | ~~`frontend/Dockerfile` **`npm install`** kullanıyor (`npm ci` değil) + `COPY package-lock.json*` glob'u lockfile yokluğunu tolere ediyor → reproducibility riski~~ → **2026-08-10 (ADIM 33) KAPANDI** — `npm ci` + glob'suz `COPY`; fail-closed olduğu **iki negatif durumda, her biri kontrolüyle** ölçüldü, ayrıca `frontend/.dockerignore` eklendi. Ayrıntı ve ham kanıt: **§6.7.2** | P9 |
| **P11-1** | **`main` üzerinde branch protection YOK ve ruleset YOK** (`gh api …/protection` → 404, `…/rulesets` → `[]`) → visual/axe kapıları **job kapısıdır, required status check DEĞİLDİR**; kırmızı E2E ile merge'i mekanik engelleyen bir şey yok | P11 |
| ~~**P11-2**~~ | ~~Visual gate 23 sayfanın **8'ini** kapsıyor; kalan 15'te piksel regresyonu koruması **yok**~~ → **2026-08-11 KAPANDI.** İddia doğruydu. Kapsam **8 → 23**; rota listesi artık elle yazılmıyor, `screenshotMatrix.ts::TARGET_PAGES`'ten türüyor (axe scan, keyboard sondaları ve insan incelemesiyle **aynı** tekil kaynak). Runner'da **23/23 passed**, **iki kez, aynı commit'te**. Onbeş yeni `-linux` baseline; sekiz mevcut baseline **yeniden üretilmedi**, yalnız slug'a göre **rename** edildi (byte-identical) → eski sekiz sözleşme aynen duruyor. Kapı **bloklayıcı** kaldı, tolerans **genişletilmedi**, hiçbir rota atlanmadı. Süre: `e2e` job'ında **1.4 dk → 4.0 dk (+2.6)**. İki YAN BULGU ölçüldü — (a) baseline'lar salt-seed stack'i değil **journey-suite sonrası** durumu tarif ediyor (yazılı değildi; **P11-3b'yi cevaplar**), (b) CI-dışı bir Linux imajı runner'ı 23'te 22 üretiyor, `analysis-lab` 6 px sapıyor → baseline'ı **CI artefaktından** alındı. Ayrıntı: **§6.7.7** | P11 |
| ~~**P11-3**~~ | ~~8 `-chromium-darwin.png` baseline commit'li ama **hiçbir job onları assert etmiyor** → sessizce bayatlayabilir~~ → **2026-08-11 KAPANDI.** İddia doğruydu ama *"bayatlayabilir"* fazla nazikti: **zaten bayatlamıştı** — macOS'ta, `e2e.yml`'in seed'inin aynısıyla koşulduğunda **8'in 6'sı düştü** (yükseklik sapmaları **44–539 px**, `maxDiffPixelRatio 0.02`'nin çok dışında). Tüketici ölçüldü: 18 `runs-on:`'un 18'i `ubuntu-latest`, macOS runner **YOK** → **(b) SİL** seçildi; (a)'nın maliyeti (macOS dakikası 10×, üstelik ürün bir Linux konteyneri olarak sevk ediliyor) açıkça değerlendirilip **reddedildi**. Sekizi silindi; geri dönüşü **YENİ** `scripts/visual-baseline-platform-gate.sh` (→ `ci.yml` `frontend` job'ı) kırıyor ve **negatifi kanıtlı**. Ayrıntı ve ham kanıt: **§6.7.6** | P11 |
| ~~**P11-6**~~ | ~~Tab sırası 23 route'un **yalnız 3'ünde** doğrulandı~~ → **2026-08-11 KAPANDI (kapsam ekseninde).** **23/23** yürütüldü, **0 N/A**; rota listesi artık elle yazılmıyor, `screenshotMatrix.ts::TARGET_PAGES`'ten türüyor. Daraltmanın yazılı gerekçesi (*"walking every tabbable element on all 23 routes would double this job's wall clock"*) **ölçülerek çürütüldü**: 23 rota **13.2 s**, `@a11y` job'ının tamamı **1.2 dk** (ADIM 29: 1.0 dk). 0 sapma, 0 blocking, advisory **90** — ADIM 29 ile birebir aynı. **YENİ KALEM → P11-6b:** aynı sonda **Tab'a hiç basmıyor** ve **hiçbir rota onu kıramaz**; ölçüldü, **düzeltilmedi**, sınır artefakta yazıldı. Ayrıntı: **§6.7.6** | P11 |
| **P11-6b** | **YENİ (2026-08-11 ölçümü, rapor bunu bildirmemişti).** `specs/20-a11y-prechecks.spec.ts`'in tab-sırası sondası adının vaat ettiğinden azını ölçüyor: **Tab tuşuna hiç basmıyor** (DOM sırasını `tabindex`'ten türetilen sırayla karşılaştırıyor) ve bulguları yalnız `advisories`'e yazdığı için **hiçbir rota onu kıramaz**. Görebildiği tek şey pozitif-`tabindex` yeniden sıralamasıdır; odak tuzağı / erişilemez kontrol / roving-tabindex **görünmez**. Sınır 3 rotada da vardı — bu dalga onu **getirmedi, ölçtü**; gerçek Tab yürüyüşü yeni bir modelleme kararıdır (radio grupları, `<select>`, roving tabindex) → **ayrı PR**. Şimdilik `precheck-results.json::tab_order_probe` + konsol satırı ile **beyan ediliyor**, ki 3→23 genişlemesi daha güçlü bir iddia gibi okunmasın. Fiziksel Tab yürüyüşü yalnız `specs/14-keyboard-flow.spec.ts`'te, **2 rotada** | P11 |
| **P11-3b** | **YENİ (2026-08-11 ölçümü).** `strategy-standalone` bugün **1135 px** ölçüldü — `-darwin` (1425) ve **`-linux` (900)** baseline'larının **ikisiyle de** uyuşmuyor; sayfa yüksekliği seed'e bağlı liste uzunluğuyla oynuyor. P11-3'ün sonucunu değiştirmez ama **hayatta kalan `-linux` setinin seed hassasiyeti** hakkında açık bir soru bırakır. **Ölçüldü, düzeltilmedi** — bu dalga `-linux` setine dokunmadı. → **2026-08-11 açık sorusu CEVAPLANDI (P11-2 ölçümü, §6.7.7):** yükseklik **seed'e** değil **journey-suite sonrası duruma** duyarlı; `e2e.yml` görsel kapıyı `npm test`'ten SONRA koşuyor, yani CI o durumu her koşuda üretiyor. Aynı 1135 px **Linux'ta da** ölçüldü → platform artefaktı **değil**. `-linux` seti runner'da iki kez 23/23 geçti | P11 |
| ~~**P11-8**~~ | ~~Lighthouse hâlâ bağlı değil~~ → **2026-08-12 (ADIM 43) KAPANDI.** İddia doğruydu. Lighthouse **ratchet olarak** bağlandı (`e2e.yml` → `lighthouse` job'ı + `specs/21-lighthouse.spec.ts` + `frontend/e2e/lighthouse-baseline.json`), mutlak eşik olarak **değil**: bugünkü ölçülen skor **taban**, yalnız yükselebilir, **pay çıkarılmadı** — a11y ve ADIM 42 kabul-kriteri ratchet'leriyle **aynı** desen, yeni desen icat edilmedi. **Kapsam: 23/23 rota, kapsanmayan 0.** Liste elle yazılmadı, `screenshotMatrix.ts::TARGET_PAGES`'ten türüyor; matriste olup tabanı olmayan rota **kırmızı** verir (boşluk, geçiş değil). **Gürültü tolerans genişleterek değil stabilize edilerek çözüldü:** atılan warm-up + rota başına 3 koşunun **medyanı** → ölçülen tekrar yayılımı **3 kategoride de 0 puan** (yani susturulacak gürültü yoktu; taban bu yüzden paysız). **İki otorite çakışması da önlendi:** (1) **a11y kategorisi hiç İSTENMİYOR** — axe sevk edilmiş otorite olarak kalıyor, rakip bir a11y sayısı **üretilmiyor**; **hiçbir Lighthouse çıktısı A-08 kanıtı değildir** ve defterin §1/§2'sine yazılamaz (A-08 hâlâ **yapılmadı**, defter hâlâ **boş**). (2) **Performans ayrımı iki belgeye de yazıldı** — `loadgen.py` **sunucuyu** ölçer (uç-nokta p95, kontrol-normalize, gecelik), Lighthouse **tarayıcıyı** (rota başına boyama/etkileşim skoru, PR'da); `performance/README.md` §8 zaten *frontend rendering*'i yük sürücüsünün kapsamı **dışında** ilan etmişti — bu kapı o **beyan edilmiş boşluğu** dolduruyor, ikinci bir görüş değil. **Ölçülen taban:** performance **100** (22 rota) / **98** (`panel-management`), best-practices **96** (23 rota), seo **82** (23 rota). **İki dürüst sınır tabanın kendi `provenance`'ına yazıldı:** performance localhost + desktop preset'te **doygun** (taban 100 = *"hiç kötüleşemez"*, mevcut en katı ratchet — ama gerçek bir kullanıcı makinesinde hızlı olduğunun kanıtı **değil**); best-practices 96 ve seo 82 **gerçek kusurlardır**, ölçülen değerinde donduruldu ve **AÇIK bırakıldı** — bir CI slice'ı ürün kodunu da değiştirmez. Ayrıntı ve ham kanıt: **§6.7.12** | P11 |
| ~~**P10-7**~~ | ~~Latency **ratio gate** bağlanmamış (`_ratio_gate` yazılı + unit-test'li, devrede değil; aktivasyon için 5 gecelik baseline gerekiyor)~~ → **2026-08-12 (ADIM 43) KAPANDI — planlanan ikinci PR'a GEREK KALMADI.** Bu satırın *"aktivasyon için 5 gecelik baseline gerekiyor"* kısmı **bayattı**: 2026-08-07'de yazıldı, bir daha okunmadı. Toplayıcı **zaten vardı** (`performance.yml` → `load-full`, cron `23 4 * * *`, ADIM 24'ten beri) ve **zaten koşuyordu**; beşinci gece **2026-08-11**'de doldu. Ölçüm: **altı** ardışık yeşil gece (08-07..08-12), altısı da `github-ubuntu-latest`, 16/40, **sıfır hata**, altısında da `loadgen-baseline` artefaktı mevcut ve süresi dolmamış. Bant **türetildi, seçilmedi**: ham kontrol kayması **1.71×** (normalizasyonun varlık nedeni), dondurulmuş baseline'a karşı herhangi bir gecenin ürettiği **en kötü** oran **1.62×** (`admin_logs`) → README §6 adım 3'ün *"gözlenen yayılımın ~1.5 katı"* = `1.5 × 1.62 = 2.43` → **`--max-ratio 2.5`**. Kanıt: altı gecenin altısı da **PASS** (1.54× pay); enjekte edilen **3.0× regresyon FAIL** — negatif, sentetik fixture'da değil **gerçek** baseline üzerinde; **2.4× regresyon geçer** ve bandın bu gerçek sınırı gizlenmeden yazıldı. §6 adım 5'in *"kullanılabilir bant yok, kapalı bırak"* çıkışı **mevcuttu ve alınmadı**. Baseline artık **takipli dosya** (`docs/performance/baseline_ci.json`) → kapı 30 günlük artefakt saklamasına **bağlı değil**. Gecelik koşunun iptal edilemeyeceği **log'dan** doğrulandı (`schedule` olayında `github.ref` = `refs/heads/main` → `cancel-in-progress` false; altı koşunun altısı da `success` + artefakt). **Kapının göremediği, açıkça yazıldı:** 2.5× altındaki hiçbir şey · PR'daki hiçbir şey (kapı **gecelik**) · başka hiçbir runner class · altı örnek bir kuyruğu sınırlayamaz. Ayrıntı ve ham kanıt: **§6.7.11** | P10 |
| ~~**P1-B1/B2**~~ | ~~`BACKEND_LAYERS.md` başlık sayıları bayat (37→38, 14→16); `CLAUDE.md` dual-token sayısı (16) codemap'e (17) göre bayat~~ → **2026-08-11 (ADIM 40) KAPANDI — sayı güncellenerek DEĞİL, sahipliği değiştirilerek.** İkisi de yeniden ölçüldü, ikisi de doğru çıktı. B1: üç sayı codemap'ten **silindi**, üretilmiş satıra taşındı (`repository_facts.md` §Summary ▸ *Application modules*); ölçüm ayrıca sayının **göremediği** kusuru buldu — `jobs` tablosunda `delivery.py` ve `heartbeat.py`'nin **hiç satırı yoktu** (14 satır / 16 modül), ikisi eklendi. B2: `CLAUDE.md`'den sayı **kaldırıldı**, otorite `BACKEND_ROUTES.md` §DUAL-TOKEN'ın tek tek sayan listesi (**17**). Tekrarı **yeni kapı** engelliyor: `check_codemap_coverage`, negatifi 5 testle kanıtlı. Ayrıntı: **§6.7.8** | P1 |
| ~~**P8-B1**~~ · ~~**P8-B3**~~ · **P8-B2 KARARA BAĞLANDI (kısmen — iki uç PO'da)** | ~~`pending_data_job_dispatch` docstring gerekçesi bayat~~ → **KAPANDI (ADIM 40):** gerekçe yeniden yazıldı — `None` **admission** yüzünden dönüyor (replay yeni iş admit etmedi, dispatch edilecek şey yok); *"gövdede terminal-state guard yok"* öncülü ADIM 21'de sona ermişti (`trade_log.py`/`trading_signal.py` gövdeleri `claim_job_for_delivery` çağırıyor — bu koşuda doğrulandı). **Davranış ve imza DEĞİŞMEDİ.** ~~`JOBS_AND_EVENTS.md` satır numaraları ~24 satır kaymış~~ → **KAPANDI (ADIM 40):** aktör tablosunun **"Satır" kolonu silindi** (aktör adı zaten sembolün kendisi; 12 değerin 11'i bayattı, yalnız `system_heartbeat :39` tutuyordu) ve tablonun tamlığı + kuyruk eşlemesi kapıya bağlandı. ~~**P8-B2** (Create-Package 200 ↔ diğer dokuz 202) BU SLICE'A GİRMEDİ ve AÇIK~~ → **2026-08-11 (ADIM 41) KARARA BAĞLANDI — kod ekseninde YARISI, ürün ekseninde AÇIK.** Ölçüm: **13** durable admission ucu (küme `enqueue_job` transitive closure'ından **türetildi**, elle sayılmadı), **hepsi** kuyruğa alıp iş bitmeden dönüyor → senkron uç **yok**. Raporun *"diğer dokuz 202"* ifadesi de **yanlıştı**: gerçek dağılım **4×200 + 1×201 + 8×202**. Kanonik uç uç soruldu: `pre-check` (doc 07 §10.3) ve `generate-candidate` (MTR §7.1 literal wire contract) **202 der** → ikisi **hizalandı** ve gövdeleri `dict[str, Any]`'den tiplenip şemada **yayımlandı**; `validate` ve `baseline-parse` için kanonik **status vermiyor** (baseline-parse için **ucu bile adlandırmıyor**) → ~~**kod DEĞİŞMEDİ, PO kararı bekliyor**~~ → **2026-08-12 (ADIM 47): PO KARARI GELDİ — ikisi de 200 → 202**, gövdeleri tiplendi (`ValidationRunAcceptedResponse` · `BaselineParseAcceptedResponse`) ve şemada yayımlandı. Otorite **karardır, sevk edilmiş desen değil** (kanonik hâlâ sessiz). **P8-B2 KAPANDI.** **Dürüst sınır:** PO `POST /library/{id}/validation-runs` (201) ucunu kapsam dışı bıraktı → aynı run'ı saran iki uç hâlâ farklı status döndürüyor, bu ayrışma **KAPANMADI**. Sevk edilmiş 202 deseni bir **olgu** olarak kaydedildi, kanonik boşlukta kural olarak kullanılmadı. Yeni kapı sınıflandırılmamış admission ucunu kırmızıya çevirir (negatifi kanıtlı). **P8 KAPANMADI** — **P8-B3b** açık (aşağıda). (P8-B2'nin kendisi ADIM 47'de kapandı.) Ayrıntı: **§6.7.8** + **§6.7.9** | P8 |
| **P8-B3b** | **YENİ (ADIM 40 ölçümü, rapor bunu bildirmemişti).** `JOBS_AND_EVENTS.md`'in **gövdesinde** ~30 adet `dosya.py:NN` / `:NN` referansı daha var (`sse.py:270`, `_wait_for_tick:166`, `actors.py:334`, …) — aktör tablosuyla **aynı** yapısal kusur: her düzenleme onları kaydırır. B3 ölçümü yalnız aktör tablosunu kapsıyordu, bu yüzden yalnız o kapatıldı; gerisini sembol adına çevirmek her referansın **tek tek doğrulanmasını** ister → **ayrı PR**. Sınır dosyanın kendisine yazıldı. **Ölçüldü, düzeltilmedi** | ADIM 40 |
| ~~**P6-6**~~ | ~~`dropdb` bu host'ta takılıyor → `backup-verify.sh` CI/cron'da sağlam bir yedeği **başarısız** raporlayabilir~~ → **2026-08-10 (ADIM 36) KAPANDI** — yanlış-negatif **yeniden üretildi** (sağlam yedek, `exit 1`), harici çağrılar sınırlandı, **yeni `exit 3` = "doğrulanamadı"** eklendi; "yedek bozuk" (1) ile karışmıyor, "sağlam" (0) ile **asla**. Ayrıntı ve ham kanıt: **§6.7.4** | P6 |
| ~~**P6-ek**~~ | ~~`e2e-acceptance.sh` preflight koruması **takılmış** daemon'a karşı işlemiyor → net `exit 2` yerine sonsuz asılı kalma~~ → **2026-08-10 (ADIM 36) KAPANDI** — asılı kalma **yeniden üretildi** (25s'de hâlâ koşuyordu), preflight sınırlandı; takılı daemon'a karşı **sınırlı sürede `exit 2`** ölçüldü, "daemon yok" teşhisi ayrı mesajda korundu. Ayrıntı ve ham kanıt: **§6.7.4** | P6 |
| **P1-Gate3 ELE ALINABİLİR HALE GELDİ — KAPANMADI** | ~~8 uncovered + 131 partial (kapı yeşil sayıyor)~~ → **2026-08-12 (ADIM 42) yeniden ölçüldü, sınıflandırıldı, ratchet'lendi, üç grup pinlendi.** Sayılar **bayat değildi** — koşu 229/131/8'i birebir yeniden üretti. Bu slice **8 clause / 5 kriter** kapattı (`AOS-17`, `TS-17`, `TR-06`, `TL-19`, `AOS-18`), yeni taban **234 covered / 126 partial / 8 uncovered**. Kalan **134 açık kriter** artık A/B/C/**D** sınıflı: **A=1** (ad sapması), **B=95** (gerçek test borcu), **C=6** (doğası gereği iddia edilemez), **D=32** (**uygulama boşluğu — hiçbir test kapatamaz**). Açık borcun **%24'ü test borcu değil, ürün işiydi**; üç sınıflı taksonomi veriye uymadı, dördüncü sınıf eklendi. Borç `acceptance_coverage_baseline.json` ile **tavan olarak donduruldu** (paysız), CI `--ratchet` ile bağlandı, negatifi CLI'da ve 6 unit testte kanıtlı; defter `acceptance_coverage_debt_ledger.md` (**üretilmiş**). `AT-04` ölçüldü → **sınıf D** (`MARKET_DATA_INSTRUMENT_MISMATCH` hiç yok; sevk edilen RUN-zamanlı `RUN_FAILED_INSTRUMENT_MISMATCH` **zaten pinli**). **Rapor bu satırda iki kez yanılmıştı** — ayrıntı §6.7.10. **P1-Gate3 KAPANMADI:** 134 kalem açık, 32'si ürün kararı/işi | P1 |
| **P10-B3** | **Bildirim yolunun DELIVERY kanıtı bir CI kapısı DEĞİL** (ADIM 31). Config yarısı kapılı (`scripts/alert-notification-gate.sh` + 21 contract testi); teslimat yarısı yalnız `scripts/alert-notification-proof.sh` ile ölçülür ve o üç konteyner + dakikalarca wall-clock ister. Kapıya bağlamak **insan kararıdır** (maliyet). Regresyon sessizce dönebilir | ADIM 31 |
| **P10-B4** | **Monitörü izleyen yok.** Alertmanager erişilemezse Prometheus yeniden dener ve `prometheus_notifications_errors_total` sayacını artırır — **kendi** `/metrics`'inde, ki onu hiçbir şey scrape etmiyor. Sessizce teslim etmeyi bırakmış bir bildirim yolu, sessiz bir sistemden ayırt edilemez. Döngüsel olmayan bir çözüm ikinci bir Prometheus ister; denenmedi | ADIM 31 |
| **P10-B5** | **On-call rotasyonu / escalation policy / acknowledgement YOK.** Alertmanager'ın ack kavramı yoktur; `repeat_interval` mekanizmanın tamamıdır. Kimin uyandırılacağı `ALERTMANAGER_NOTIFY_URL`'in ucundaki sistemde yaşar — **repo dışı, organizasyonel karar** | ADIM 31 |

> **§6.7'nin durumu — ADIM 47 sonrası, SAYILDI (2026-08-12).** ADIM 47'nin kickoff'u
> *"bununla §6.7'nin on iki kaleminin tamamı kapanır (P11-1 hariç)"* diyordu. **Bu iddia
> yanlıştır ve düzeltilmiştir** — ADIM 42'nin dersi burada tekrar geçerli: bayat değil,
> **anlamsız** bir sayıydı; iki farklı şeyi ("§6.7.N alt bölümleri" ile "§6.7 tablosu")
> tek sayıya katlıyordu.
>
> * **§6.7.N yazım alt bölümleri: 12 tane, 11'i KAPALI.** Kapanmayan **§6.7.10 /
>   P1-Gate3**'tür ve kendi başlığında zaten *"ELE ALINABİLİR HALE GELDİ — KAPANMADI"*
>   yazar. P11-1'in bir §6.7.N alt bölümü hiç olmadı, yani "P11-1 hariç" ifadesi bu
>   eksene uymuyordu.
> * **§6.7 tablosu: 24 satır, 14'ü KAPALI, 10'u AÇIK** → **P4-3** · **P10-B6** ·
>   **P11-1** · **P11-6b** · **P11-3b** · **P8-B3b** · **P1-Gate3** · **P10-B3** ·
>   **P10-B4** · **P10-B5**. Bunların yalnız biri (P11-1) repo ayarıdır; gerisi ölçülmüş
>   ve düzeltilmemiş teknik kalemlerdir.
>
> Yani ADIM 47 **iki** kalem kapattı (P10-B2 / §6.7.5 ve P8-B2 / §6.7.9), §6.7'yi
> **bitirmedi**. **Blocker sayısı DEĞİŞMEDİ: 1 (yalnız A-08); §8 BLOCKED.** Hiçbir kalem
> bu slice'ta READY'ye çevrilmedi.

#### 6.7.1 P9-F2 KAPANDI — SPA origin'inde CSP (ADIM 32, 2026-08-10)

**Verdict ve blocker sayısı DEĞİŞMEDİ.** P9-F2 bir blocker değildi; §8 hâlâ **BLOCKED**,
açık blocker sayısı hâlâ **üç** (1, 2, 4).

**Önce yeniden ölçüldü, körü körüne kabul edilmedi.** `origin/main` `f3986fa` üzerinde
`grep -rn 'Content-Security-Policy' frontend/` → **boş**; dört header (`nosniff`,
`X-Frame-Options: DENY`, `Referrer-Policy`, `Permissions-Policy`) vardı, **CSP yoktu**.
İddia doğruydu.

**Sevk edilen politika** (`frontend/nginx-security-headers.conf`), genişliği **sevk edilen
`dist/`'ten ölçülerek** belirlendi — varsayılmadı:

```
default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self';
connect-src 'self' <API origin>; base-uri 'none'; form-action 'self';
frame-ancestors 'none'; object-src 'none'
```

**`unsafe-inline` ve `unsafe-eval` YOK** — çünkü gerekmiyor: build tek harici module
script + tek harici stylesheet yayıyor, `dist/index.html`'de inline `<script>`/`<style>`
**0**, bundle'da `eval(`/`new Function(` **0**, CSS'te `data:`/`url()`/`@font-face` **0**,
`src/`'de WebSocket / dynamic `import()` / harici URL / `<form action=>` **0**.
`connect-src`'deki API origin'i **image build zamanında**, Vite'ın bundle'a gömdüğü aynı
`VITE_API_BASE_URL` arg'ından türetilir (yer tutucu hayatta kalırsa build **durur**);
runtime lookup değil, çünkü web konteyneri `read_only: true` ile koşuyor ve bundle zaten
yalnız Vite'ın gömdüğü origin'e konuşabilir.

**Kapı — canlı yanıtı assert eder, config dosyasını değil** (API'nin CSP testinin aynası):
`scripts/spa-security-headers-gate.sh`, **hem** `/` **hem de** hash'li bundle'ı
`/assets/`'ten sorgular — ikincisi gereksiz değil: `location /assets/` kendi
`add_header`'ını bildirir ve include tekrarlanmazsa sunucu düzeyi header'ların **hepsini
iptal eder** (bu regresyon bir kez sevk edildi). CI'a `install-acceptance.yml` →
**`fresh-install`** job'ında bağlandı (her PR + `main` push'u) — o job zaten sevk edilen
Dockerfile'dan kurulmuş çalışan bir stack ödüyor ve build-time substitution başka hiçbir
yerde gözlemlenemez.

**Ölçülen kanıt (2026-08-10, `docs/releases/evidence/2026-08-10/`):**

| Faz | Ne kanıtlandı | Sonuç |
|---|---|---|
| 1 | Politika canlı yanıtta | `curl -sI :8080/` **ve** hash'li bundle → CSP **ikisinde de** ayniyle var |
| 2 | Kapı geçiyor | `spa-security-headers-gate.sh` **exit 0** — 2 yüzey × 5 header = **10 PASS** |
| 3 | **Kapı kırmızıya DÖNEBİLİYOR** | Yanlış bir `connect-src` origin'i beklenince **exit 1**, ve `content-security-policy` satırında kırmızı (karşılaştırma gerçekten ısırıyor). CI'da **negatif adım** olarak bağlandı |
| 4 | **Politika UYGULANIYOR, sadece mevcut değil** | Canlı sayfada: enjekte inline `<script>` **çalışmadı**, inline `<style>` **uygulanmadı**, `setAttribute('style',…)` **uygulanmadı** |
| 5 | **Uygulama BOZULMADI** | Playwright e2e (`npm test`, e2e.yml'in koştuğu çağrının aynısı) → **39 passed / 1 skipped / 0 failed**; ayrıca kimliği doğrulanmış 9 route'ta **101** React inline-style'lı öğe render oldu ve **0 CSP ihlali** raporlandı |

Ham çıktı: `p9f2_spa_csp.txt` · `p9f2_spa_csp_app_not_broken.txt`.

**Dürüst sınırlar — bu slice'ta KAPANMAYAN:**

- **Kapı yalnız `fresh-install` job'ında koşar**, `e2e.yml`'de değil. Bu bilinçli (aynı
  header'ı iki job'da ölçmek maliyeti ikiye katlar, kanıtı katlamaz) ama şu demek: **web
  origin'ini kuran ama `install-acceptance` koşmayan bir yol** header'sız kalabilir.
- **P11-1 hâlâ açık:** `main` üzerinde branch protection / ruleset YOK, dolayısıyla bu kapı
  da diğerleri gibi **job kapısıdır, required status check DEĞİLDİR**. Kırmızıyken merge'i
  mekanik engelleyen bir şey yok. Bu bir **repo ayarıdır, insan kararıdır** — agent kapatamaz.
- **CSP `report-uri`/`report-to` taşımıyor.** Production'da gerçek bir ihlal olursa hiçbir
  yere raporlanmaz; yalnız kullanıcının konsolunda görünür. Rapor toplayıcı bir uç
  **yok** ve bu slice bir tane uydurmadı.
- §7'nin *"`.github` ağacında `1f4b88b` sonrası sıfır değişiklik"* cümlesi **ADIM 31'den
  beri bayattır** (o dalga `ci.yml`'i yeniden adlandırdı); ADIM 32 `install-acceptance.yml`'i
  de değiştirir. Cümle rapor tarihine (2026-08-07) göre doğruydu; **bugün için değildir**.
  Burada **kaydedildi**, §7 elle düzeltilmedi — o blok ADIM 29'un ölçümüdür.

#### 6.7.2 P9-F1 KAPANDI — frontend build reproducibility (ADIM 33, 2026-08-10)

**Verdict ve blocker sayısı DEĞİŞMEDİ.** P9-F1 bir blocker değildi; §8 hâlâ **BLOCKED**,
açık blocker sayısı hâlâ **üç** (1, 2, 4). Aynı satırdaki **P11-1 (branch protection) ELE
ALINMADI** — repo ayarı, insan kararı.

**Önce ölçüldü, körü körüne kabul edilmedi.** İddianın iki parçası da doğruydu, ama
**bugünkü etkisi** ölçülmeden yazılmamalıydı: `npm install` bu ağaçta lockfile'ı
**bit-bit değiştirmiyor** (`a8979c98…` → `a8979c98…`) ve `npm install` ile `npm ci`
**bit-bit aynı bundle'ı** üretiyor (dört `dist/` dosyasının dördü de aynı sha256; çözünen
ağaç da aynı). **Dolayısıyla bu bir davranış değişikliği DEĞİLDİR** — değişen şey
garantidir. Bu, P9'un kendi kaydıyla (`evidence/2026-08-07/P9_security.md` §F-1: "bugün
fiilî ayrışma yok") **tutarlıdır**.

**Sevk edilen:** `COPY package.json package-lock.json ./` (glob'suz) + `RUN npm ci`, ve
**yeni** `frontend/.dockerignore`. Sonuncusu kozmetik değil: `COPY . .` install'dan
**sonra** geldiği için host'un `node_modules`'ü image'inkinin üstüne biner ve `npm ci`'yi
süs hâline getirir (ADIM 32'de yerel build'de bizzat yaşandı).

**Isırdığının kanıtı — iki negatif, her biri kontrolüyle:**

| Durum | Sevk edilen | Kontrol (eski hâl) |
|---|---|---|
| Lockfile YOK | `docker build` **exit 1**, `"/package-lock.json": not found` | glob **exit 0** — eşleşme yok, uyarı yok, build lockfile'sız devam etti |
| `package.json` lockfile'da olmayan dep bildiriyor | `docker build` **exit 1**, `EUSAGE … Missing: left-pad@1.3.0 from lock file` | `npm install` **exit 0**, lockfile'ı **sessizce yeniden yazdı** (`a8979c98…` → `3d8c1b66…`) |

`.dockerignore` de kontrollü ölçüldü: zehirli bir geliştirici ağacı (host `node_modules`,
`dist/STALE.txt`, `e2e/node_modules`, `evil.example` işaret eden `.env`,
`public/mockup_v18.html`) dosya varken **beşi de dışarıda**, dosya kaldırılınca **beşi de
içeride**. Bu ölçüm sırasında **rapor satırında olmayan bir kusur bulundu**: Vite
`public/`'i `dist/`'e olduğu gibi kopyaladığı için dev-only v18 mockup kopyası
**production image'ına** sızıp nginx tarafından `/mockup_v18.html` adresinden sunulabiliyordu.

**Kırılmadığı doğrulananlar:** image **exit 0 / 84 MB** (2026-08-07 ölçümü de 84 MB) ·
sevk edilen bundle host'ta `npm ci` ile üretilenle **bit-bit aynı** · zehir image'a
**girmedi** · **ADIM 32'nin CSP kapısı** canlı konteynerde **10/10 PASS**, ve yanlış
`connect-src` iddia edildiğinde hâlâ **exit 1** (kapı hâlâ kapı).

**Dürüst sınır:** frontend test suite bu dalgada **koşulmadı** — `src/` altında tek dosya
değişmedi; bu bir gerekçedir, ölçüm değil, otorite CI'dır. Ayrıca bu değişiklik bir
**tedarik-zinciri savunması değildir**: lockfile'a sadakati zorlar, lockfile'ın içeriğini
denetlemez; `npm audit`'in 3 high-severity bulgusu **ele alınmadı**.

Ham kanıt: `docs/releases/evidence/2026-08-10/P9F1_frontend_build_reproducibility.md` +
`p9f1_install_vs_ci.txt` · `p9f1_npm_drift.txt` · `p9f1_negative_cases.txt` ·
`p9f1_dockerignore.txt` · `p9f1_image_and_csp.txt`.

#### 6.7.4 P6-ek ve P6-6 KAPANDI — harness fail-fast (ADIM 36, 2026-08-10)

> **Numara notu:** bu bölüm önce §6.7.3 yazılmıştı; #657 aynı numarayı alarak merge oldu
> (aşağıda, ADIM 34). Merge edilmiş bir numara değiştirilmez, bu yüzden **taşınan bu bölüm
> oldu**. Fiziksel sıra bu yüzden §6.7.4 → §6.7.3 şeklinde; numaralar otoritedir, sıra değil.

**Kusur sınıfı tek:** bir harici araca evet/hayır sorusu **sınırsız** soruluyordu. İki
kalem de bu yüzden elle fark edilmedi — asılı kalma "biraz uzun sürüyor" gibi görünür,
Ctrl-C basılır, geçilir. **İkisi de düzeltmeden ÖNCE yeniden üretildi.**

| Kalem | Düzeltmeden önce ÖLÇÜLEN | Sonra ÖLÇÜLEN |
|---|---|---|
| **P6-ek** | PATH'e cevap vermeyen bir `docker` konarak: script **25s sonra hâlâ koşuyordu**. `FATAL … exit 2` dalı probe'un **hemen altında** ama probe hiç dönmediği için asla alınamıyor | probe sınırı 3s → **`exit 2`, 3.0s** ("HUNG, not absent") |
| **P6-6 (a)** | Takılmış `dropdb` → script **süresiz** asılı | **`exit 3`, 6.1s** ("UNVERIFIED … says nothing about the backup") |
| **P6-6 (b)** | `dropdb` **başarısız** → `\|\| true` yuttu → artık DB yüzünden `createdb` patladı → **`exit 1`** = "yedek geri yüklenmiyor". **Sağlam bir yedek, bozuk diye raporlandı** | **`exit 3`, 0.0s** — yedek hakkında hiçbir iddia yok |

**Yeni exit-code taksonomisi (üçü ayrı, bilerek).**
`e2e-acceptance.sh`: `0` her adım geçti · `1` bir adım düştü · `2` harness **hiç koşamadı**
(Compose yok · daemon erişilemez · daemon **HUNG**).
`backup-verify.sh`: `0` geri yükleniyor · `1` geri yüklenmiyor — **YEDEK hakkında** karar ·
`3` **doğrulanamadı** — **ORTAM** hakkında karar. `3` sıfır değildir, yani CI/cron yine
kırmızı olur: **belirsizlik BAŞARISIZ sayılır**, yalnız neyin başarısız olduğu artık yalan
söylemiyor. Ters yöne kayma testle kilitlendi: bozuk dump hâlâ **1**, sağlam yedek hâlâ **0**.

**Eşikler gerekçeli, sihirli sayı yok** (hepsi bu host'ta ölçüldü):
`docker version` 1.44s · `docker compose version` 0.16s → **20s** (~14×) ·
`dropdb` (mevcut DB) **4.83s** — raporun işaret ettiği çağrı — `createdb` 0.92s,
`psql` 0.13s → **60s** (~12×) · `pg_restore` süresi dump'la ölçeklendiği için ayrı ve
gevşek bir sınır: **1800s**. Hepsi env ile geçersiz kılınabilir (test 3s ile koşar).
`dc up --build` / `exec` / `logs` **bilerek sınırsız** bırakıldı: dürüst süreleri dakikalar,
sınırlamak sahte başarısızlık üretirdi.

**Ortak yardımcı `scripts/lib/bounded.sh` (YENİ).** `bounded_run SECONDS CMD…` → komutun
kendi statüsü, ya da **124** (GNU `timeout` uzlaşımı). Öldürdüğü bir komut için **asla 0**
dönemez. GNU `timeout` yok (macOS'ta bulunmuyor), `wait -n` yok, kesirli `sleep` yok —
macOS'un **bash 3.2**'si ile CI'ın bash 5'i aynı yolu koşar. İki incelik ölçülerek bulundu:
(i) `kill -0` ile yoklama çocuğun reap edilmesiyle yarışıyor → sonuç gerçek bir `wait`'ten
alınır; (ii) yalnız doğrudan çocuğu öldürmek **yetmiyor** — `docker compose …`, compose
eklentisini `docker`'ın **çocuğu** olarak koşar ve hayatta kalan torun
`x="$(bounded_run …)"` borusunu açık tutar: 2s'lik sınıra karşı çağıran **60s** bloke
ölçüldü. Bu yüzden **süreç grubu** öldürülür.

**Regresyon testi bir CI kapısıdır** — `backend/tests/contract/test_harness_failfast_contract.py`
(12 test, backend job'ında koşar). PATH'e sahte binary koyar (takılan / patlayan / anında
cevaplayan) ve exit code + sınırlı dönüş süresi assert eder; asılı kalma `pytest.fail` olur,
**CI asılmaz**. **Testlerin ısırdığı kanıtlandı:** düzeltme geri alınıp koşulduğunda
**5 failed / 7 passed** (dördü 90s'de timeout, biri `assert 1 == 3` — yani P6-6'nın
yanlış-negatifi), düzeltmeyle **12 passed / 23.3s**.

**Bu slice'ın KAPATMADIĞI şeyler (dürüst sınır).** Blocker sayısı **değişmedi**; verdict
**BLOCKED** kalır. `flows` hâlâ bir CI kapısı **değildir** (§6.2 — ADIM 30'un ekseni, bu
slice ona dokunmaz). Ürün kodu değişmedi. Aynı kusur sınıfı **yalnız bu iki script içinde**
tarandı; diğer script'lere süpürme yapılmadı.

> **Sonradan not (2026-08-12 / ADIM 45).** Yukarıdaki *"`flows` hâlâ bir CI kapısı
> değildir"* cümlesi **ADIM 36'nın kendi sınırının kaydıdır ve o gün doğruydu**; bugün
> geçerli değildir — kapı ADIM 45'te bağlandı (§6.2). Cümle silinmedi: bir slice'ın ne
> yapmadığını söylediği yer, sonradan doğru çıktı diye yeniden yazılmaz.

Ham kanıt: `docs/releases/evidence/2026-08-10/P6FF_harness_failfast.md` +
`p6ff_measurements.txt` · `p6ff_tests_before_fix.txt` · `p6ff_tests_after_fix.txt`.
#### 6.7.3 P4-1 + P4-2 KAPANDI — model↔migration şema paritesi (ADIM 34, 2026-08-10)

Tam kayıt ve ham çıktılar: **`evidence/2026-08-10/P4_schema_parity.md`** +
`p4_alembic_check_before.txt` · `p4_alembic_check_after.txt` ·
`p4_install_path_parity_before.txt` · `p4_parity_gate_green.txt` ·
`p4_parity_gate_negative.txt`.

**Raporun P4-1/P4-2 iddiaları yeniden ölçüldü ve DOĞRULANDI** (exit 255; 39+39+1+1; 40 gerçek
sapma; hiçbir workflow koşmuyor; `agent_event.seq`'te fazladan non-unique index). 39 sapma
**yalnız adlandırmadır** — sevk edilen kısa ad ⇄ modelin `index=True`'dan türettiği SQLAlchemy
varsayılanı; kolon/uniqueness/predicate aynı. Bu yüzden **fix tipi 1** uygulandı: DB'ye ve
migration'lara **dokunulmadı**, model sevk edilen ada hizalandı. Sevk edilen adlar **DB'den
okundu**. 40'ıncı sapma (`agent_event.seq`) yapısaldır ama yine model tarafında kapandı: model
artık migration'ın sevk ettiği şekli bildiriyor (`unique=True` ⇒ `agent_event_seq_key` **ayrı**,
`Index("ix_agent_event_seq","seq")` **ayrı**).

| Ölçüm | Önce | Sonra |
|---|---|---|
| `alembic check` index-ekseni operasyonu | **40** | **0** |
| Kurulum yolu index paritesi (alembic ↔ `create_all`) | DIVERGENT (361 vs 360; 40/39/1) | **BIT-IDENTICAL** (361 vs 361; 0/0/0) |
| `add/remove column` · `add/remove table` | 0 · 0 | **0 · 0** |
| alembic head | `0043_i08_registry_strategy_fks` | **değişmedi** (bu dalgada migration YOK) |

**P4-2 fonksiyonel etkisizliği deneysel kanıtlandı:** aynı `seq` ile iki satır eklendiğinde
**iki yol da** reddediyor (alembic: `agent_event_seq_key`, create_all: `ix_agent_event_seq`) —
ayrışan tek şey hata mesajındaki addır. Fazladan index **kaldırılmadı**; bir index'i düşürmek
veya uniqueness'ını çevirmek ayrı bir karardır.

**Kapı:** `scripts/schema_parity_gate.py`, `ci.yml` `backend` job'ında `alembic upgrade head`'in
hemen ardından — **exit 0 doğrulandı**. Kapı `alembic check`'ten **daha güçlüdür**: alembic
operatör sınıfı taşıyan dört `audit_events` expression index'ini atlayıp "eşit varsayar", kapı
onları gerçek `pg_get_indexdef` üzerinden görür. **Negatifi kanıtlandı** — iki sapma tipi de
geri konuldu, ikisinde de **exit 1**; geri alınınca yeniden exit 0.

**Dürüst sınırlar — bu slice'ta KAPANMAYAN:**

- **`alembic check` hâlâ exit 255** ve kapı bunu sıfırmış gibi göstermez. Sebep P4-3'tür:
  **60 `modify_default`** sapması (40 tabloda 60 kolon). Rapor bunu *"tip/server-default
  değişimi = 0"* diye bildirmişti — **o iddia yanlıştı**; sapmalar `alembic check`'in ERROR
  satırında hep vardı, §6.7'nin taraması yalnız `Detected added/removed …` cümlelerini
  saydığı için görünmemişti. **Ölçüldü, düzeltilmedi.**
- Kapı **`alembic check`'in exit code'unu assert etmez** — index eksenini, kurulum-yolu
  ayniyetini, kolon/tablo drift'ini ve server-default sapma **tavanını** assert eder.
  Adı da bunu söyler (*index axis*). Kapının ölçmediği şeyi ölçtüğü sanılmasın.
- **P11-1 hâlâ açık:** `main` üzerinde branch protection / ruleset YOK → bu kapı da
  **job kapısıdır, required status check DEĞİLDİR**. Repo ayarı, **insan kararı**.

**Blocker sayısı DEĞİŞMEDİ (üç). §8 verdict BLOCKED kalır.** P4-1/P4-2 blocker değildi.

---

#### 6.7.5 P10-B2 **KAPANDI** — sınır yayımlandı (ADIM 37), kelepçe PO kararıyla korundu (ADIM 47)

> **KAPANIŞ — ADIM 47, 2026-08-12.** Aşağıdaki ADIM 37 kaydı **tarihsel olarak doğrudur ve
> değiştirilmemiştir**; açık bıraktığı tek soru — *aşım sessiz clamp mi, 422 red mi?* —
> 2026-08-12'de **PO tarafından cevaplandı: KELEPÇE KALIR.** Dokuz parametre 200 dönmeye
> devam eder, 422'ye çevrilmez.
>
> **Bu bir "yapılacak iş yok" kararı DEĞİLDİ.** Kapatılması gereken şey davranış değil,
> **farkın gerekçesinin yazılı olmamasıydı** — nitekim yazılmadığı için bu rapor onu bir
> "tutarsızlık" olarak yeniden raporladı. Gerekçe artık üç yerde birden yaşıyor
> (`apps/api/pagination.py` modül docstring'i · `docs/CODEMAPS/BACKEND_ROUTES.md`
> §SAYFALAMA SINIRI · burası):
> 1. **Davranış artık SESSİZ DEĞİL.** Gerçek kusur, istemcinin sınırı `docs/openapi.json`'dan
>    öğrenememesiydi; `x-clamp-default` / `x-clamp-maximum` onu kapattı. Kusur eksik
>    sözleşmeydi, kelepçenin kendisi değil.
> 2. **422'ye çevirmek ÜRETİLMİŞ İSTEMCİLERİ KIRARDI** — bugün 200 dönen bir istek
>    reddedilmeye başlardı. Sevk edilmiş bir wire contract yalnız simetri uğruna yeniden
>    kesilmez.
>
> Yani **19 ENFORCING / 9 CLAMPING ayrımı BİLİNÇLİDİR**, drift değil; üç farklı default
> (`clamp_limit` → 20 · `panel_backtest_log::_clamp_limit` → 25 ·
> `log_projection::_clamp_limit` → 50; tavan üçünde de 100) de bilinçlidir — her biri kendi
> sorgu katmanının **uyguladığı** sabittir. Tek ortak declarator
> `apps/api/pagination.py::clamped_limit_query`; yeni bir kelepçeli `limit` ondan geçmelidir.
>
> **Pin — iki invariant birlikte kilitli** (`tests/contract/test_pagination_limit_contract.py`):
> kelepçeli parametre `x-clamp-maximum` **YAYIMLAR** (`test_the_two_families_partition_every_limit_parameter`
> + `test_published_bounds_equal_the_enforced_bounds`) **ve** JSON Schema `maximum`
> **YAYIMLAMAZ** (`test_a_clamping_parameter_never_advertises_rejection`). İkincisi iki
> sınıfın birbirine karışmasını engeller: her iki anahtarı da emitleyen bir uç iki aileye
> birden girer ve karar şemadan **okunamaz** hâle gelir. **KOD DAVRANIŞI DEĞİŞMEDİ** — bu
> kalem yalnız belge + test ekseninde kapandı; `test_the_over_limit_behaviour_is_the_decided_clamp`
> kelepçeyi karar olarak pinler, bir simetri süpürgesi onu sessizce ters çeviremez.
>
> **Kapsam dışı kalan (KAPANMADI):** **P10-B6** — 4 uç etkin sayfa boyutunu yanıtta
> yankılamıyor. Ayrı bulgu, bu kararın konusu değil.
> **Verdict ve blocker sayısı DEĞİŞMEDİ: 1 (yalnız A-08), §8 BLOCKED.**

**(ADIM 37, 2026-08-11 kaydı — tarihsel, değiştirilmedi.)**

> **Numara notu:** bu slice'ın kickoff prompt'u kendisini "ADIM 36" diye adlandırıyordu.
> **ADIM 36 doludur** (P6-ek + P6-6 harness fail-fast, PR #658, §6.7.4). Merge edilmiş
> numarayı yeniden atamak yasak olduğu için bu slice **ADIM 37**'dir. Aynı sebeple yeni
> bulgu **P10-B6**'dır — `P10-B1`..`P10-B5` doludur.

**Ham kanıt:** `docs/releases/evidence/2026-08-11/p10b2_pagination_limit_contract.md`
(tam defter) + `p10b2_openapi_diff.txt` (şema diff'i).

**İki soru ayrı tutuldu.** (1) yayımlama = sevk edilen davranışın görünür kılınması,
bir karar değil → **yapıldı**. (2) aşım davranışı = ürün kararı → **verilmedi**.

##### Raporun iddiası: sayı doğru, niteleme yanlıştı

9 parametre — doğrulandı, adıyla listelendi (defter §1). Ama **"hepsi aynı deseni
kullanıyor" DEĞİL:** üç ayrı kelepçe fonksiyonu ve **üç ayrı default** var
(`clamp_limit` → 20 · `panel_backtest_log::_clamp_limit` → **25** ·
`log_projection::_clamp_limit` → **50**); tavan üçünde de 100. Yayımlama bu yüzden tek
sabit değil, **her ucun kendi ikilisini** taşır.

Raporun *"sessizce 100'e iniyor"* nitelemesi **9 uç için doğru değildi** — ölçüldü:

| Katman | Uç sayısı | Dönen metadata | Kesilme fark edilir mi |
|---|---|---|---|
| A | 5 | `meta: {cursor, has_more, limit}` — `limit` **etkin** değeri yankılar | **evet, doğrudan** |
| B | 3 | `{items, next_cursor}` — limit yankılanmıyor | kısmen (`next_cursor != null`) |
| C | **1** (`/agent-tasks/{task_id}/tool-calls`) | **hiçbiri** | **hayır — gerçekten sessiz** |

Asıl kusur "kesildiğini anlayamıyor" değil, **"sınırı önceden öğrenemiyor"** idi:
sözleşmeden istek kuran bir istemci 9 ucun hiçbirinde ne default'u ne tavanı bulabiliyordu.
Katman B/C'nin runtime yankı boşluğu ayrı bir kusurdur → **P10-B6**, ölçüldü, düzeltilmedi.

##### Ne sevk edildi

Tek ortak declarator: `backend/src/entropia/apps/api/pagination.py::clamped_limit_query`.
`description` (insan) + `x-clamp-default` / `x-clamp-maximum` (makine) yayımlar.
**JSON Schema `maximum` bilerek YAYIMLANMAZ:** o keyword "bundan büyükler geçersiz" der,
bu sunucu ise onları **kabul eder** — emitlemek eksik bir sözleşmeyi **yanlış** bir
sözleşmeyle değiştirir, üretilmiş istemci 200 dönen isteği reddederdi. *(Repodaki ilk
`x-` uzantısı; snapshot'ta önceden 0 tane vardı. Yeni kelepçeli uç eklerken sözleşmeyi
route'a KOPYALAMA, bu fonksiyondan geçir.)*

```
limit params total: 28
  ENFORCED  (JSON Schema maximum -> 422): 19
  CLAMPED   (x-clamp-maximum     -> 200):  9
  UNPUBLISHED:                             0
  clamped params ALSO emitting `maximum`:  0
```

**Davranış bit-özdeş:** `le=`/`ge=` eklenmedi, `default=None` korundu; route yolları,
OCC token'ları, `Idempotency-Key`, react-query key'leri, gövdeler ve `response_model`'lar
aynen kaldı. **Frontend etkisi ölçüldü = sıfır:** `lib/*.ts` bu 9 uca **hiç `limit`
göndermiyor** (yalnız `meta.limit` okuyor) → ileride (2) için red seçilse bile repo içi
hiçbir çağıran kırılmaz. Repo dışı çağıranlar bilinmiyor.

**Kapı:** `backend/tests/contract/test_pagination_limit_contract.py` (5 test) — sınırsız
yayımlanan `limit` yasak · iki aile kesişmez · kelepçeli parametre `maximum` reklamı
yapamaz · yayımlanan sayı uygulanana **eşit** · **aşım davranışı pin'i**
(`clamp_limit(100_000) == 100`), ki bu pin biri clamp'i red'e çevirirse kırılır ve ürün
kararının bir refactor yan etkisi olarak sessizce yutulmasını engeller.
**Negatif kanıtı:** tek uç geri alındı → `exit 1`, üç test kırmızı, uç adıyla raporlandı.

##### Adjudication (2) — AÇIK, PO kararı bekliyor

**Canonical SESSİZ.** MTR §2.1/§8 ve doc 19 cursor pagination'ı ve `meta.pagination`
alanlarını zorunlu kılar, doc 19 admin listelerinde `limit=50` **ister** — ama
**hiçbiri ne MAX_LIMIT değerini ne de aşım kuralını bildirir**. Doc 18 ve doc 22 sessiz.
Repo kuralı gereği ("canonical boşlukta ürün kararı UYDURULMAZ") karar verilmedi ve
sessiz clamp **sessizce onaylanmadı** — buraya kaydedildi.

* **(A) sessiz clamp (bugün sevk edilen):** affedici, kaynak fail-safe; ama aynı yüzeyde
  19 uç 422 verirken bu 9'u 200 veriyor.
* **(B) 422 red (19 ucun yaptığı):** tek tutarlı yüzey; davranış değişikliğidir, repo
  içi kırılan çağıran **ölçülen 0**.
* **Bağlayıcı OLMAYAN komşu sinyal:** MTR satır 7560/7605 **position sizing** alanında
  ürünün *"clamp değil blocker"* / *"kırpılıp açılmaz … reddedilir"* dediğini kaydederiz.
  **Sayfalama için canonical DEĞİLDİR** (farklı domain, farklı risk); ürünün eğilimini
  gösterir, kararın yerine geçmez — taşımak "uydurma"nın ta kendisi olurdu.
* **(B) seçilirse tuzak:** FastAPI'nin varsayılan `{"detail": [...]}` şekli adjudicated
  zarf DEĞİLDİR (O-02). `le=` taşıyan 19 uç zaten `apps/api/errors.py` handler'ından
  geçiyor, yani yeni 422'ler muhtemelen doğru zarfa düşer — **varsayma, ölç.**

**Blocker sayısı DEĞİŞMEDİ (üç). §8 verdict BLOCKED kalır.**

---

#### 6.7.6 P11-3 ve P11-6 KAPANDI — kapının ölçtüğü ile iddia ettiği (2026-08-11)

**Verdict ve blocker sayısı DEĞİŞMEDİ.** İkisi de blocker değildi; §8 hâlâ **BLOCKED**,
açık blocker sayısı hâlâ **üç** (1, 2, 4). **P11 KAPANMADI** — aynı satırdaki **P11-1**
(branch protection, repo ayarı → **insan kararı**), **P11-2** (görsel kapsam 8→23, ayrı PR)
ve **P11-8** (Lighthouse) **ele alınmadı**. Tam kayıt ve ham çıktılar:
`docs/releases/evidence/2026-08-11/P11_gate_coverage_truth.md` (+ `p11_3_gate.txt`,
`p11_3_visual_darwin_per_page.txt`, `p11_3_baseline_dimensions.txt`,
`p11_6_a11y_23routes.txt`, `p11_6_precheck_results.json`).

**P11-3 — ölçüm (a)'yı değil (b)'yi seçtirdi.** Playwright baseline'ları platform ekli ve
yalnız **koşan** platformun ekiyle karşılaştırılır; `.github/workflows`'daki **18
`runs-on:`'un 18'i** `ubuntu-latest` (macOS runner **yok**) → `-darwin` setinin kapısı
**yok**, tek gerçek tüketicisi macOS'ta `npm run visual` koşan bir kişi. O kişinin bugün ne
gördüğü ölçüldü: `e2e.yml`'in seed'inin aynısıyla kurulan stack'te, sekiz sayfa tek tek
koşturulunca **6 FAIL / 2 PASS**. Kontrol deneyi bunun bir platform farkı **olmadığını**
gösteriyor: `-darwin` ile `-linux` baseline'ları aynı sayfada **525 px'e kadar** ayrışıyor
ve bu makinenin bugün ürettiği yükseklikler **`-linux`'un yanına** düşüyor. `-darwin` bir
platform artefaktı değil, **bayat** bir artefakt. (a) için gereken macOS runner açıkça
değerlendirildi: dakikası **10×**, üstelik ürün `nginxinc/nginx-unprivileged` tabanlı bir
**Linux konteyneri** olarak sevk ediliyor → reddedildi.

**Sevk edilen:** 8 dosya `git rm`; **YENİ** `scripts/visual-baseline-platform-gate.sh`
(`git ls-files` ile **commit'li** baseline'ları okur, `ASSERTED_PLATFORMS="linux"` dışında
**exit 1**), `ci.yml` → `frontend` job'ına bağlı (statik kontrol: Docker/tarayıcı/DB
istemez, stack kurmayan PR'ları da kapsar). `specs/11` ve `frontend/e2e/README.md`'deki
*"Both authoring-platform and Ubuntu CI baselines are committed"* cümlesi artık yanlıştı →
düzeltildi; macOS'ta beklenen davranış (**missing snapshot, sahte regresyon DEĞİL**)
ölçülerek yazıldı.

> **Kapının kendisi ilk yazımında bu slice'ın konusunu tekrarladı ve negatif kontrol onu
> yakaladı.** `grep -Ev "$re" || true` iki hata yapıyordu: `-` ile başlayan deseni grep
> **opsiyon** sanıyor, `|| true` ise grep'in **hata** çıkışını (2) "ihlal yok"a çeviriyordu
> → sekiz ihlalli bir ağaçta kapı **`OK … EXIT=0`** bastı. Düzeltildi (`-e` + exit kodunun
> üç dallı okunması) ve negatif yeniden koşuldu: **exit 1, sekizini de adıyla listeliyor**.
> Silme ayrıca **ikinci bir kapı** tarafından da yakalandı — `generate_repository_facts.py
> --check` `Playwright snapshot PNGs 16 → 8` sapmasıyla kırmızıya döndü.

**P11-6 — 3/23 → 23/23.** Daraltmanın spec'e yazılı gerekçesi (*"would double this job's
wall clock"*) **ölçülerek çürütüldü**: sonda rota başına tek bir `page.evaluate`'tir, aynı
dosyadaki yapı testi zaten 23 rotanın navigasyonunu ödüyor → 23 rotada test **13.2 s**, job
toplamı **1.2 dk**. Rota listesi artık elle yazılmıyor;
`utils/screenshotMatrix.ts::TARGET_PAGES`'ten türüyor (contract testinin tekil kaynak
olarak pinlediği liste). Yürütülemeyen bir rota **sessizce atlanmıyor**: `N/A` gerekçesiyle
`tab_order_routes_NOT_walked`'a yazılır. Ölçülen: **23/23 walked, NOT_walked `[]`, 0
tab-order sapması, 0 blocking**, advisory **90** — ADIM 29'un sayısıyla **birebir aynı**
(yeni bulgu yok, regresyon yok). Düzeltilecek ürün bulgusu **çıkmadı**, dolayısıyla issue
da açılmadı.

**Bu koşuda doğan iki yeni kalem — §6.7 tablosuna eklendi: `P11-6b` ve `P11-3b`.**

**A-08 ile KARIŞTIRILAMAZ.** Bu bölümün hiçbir çıktısı ekran-okuyucu kanıtı değildir ve
`docs/audit/a11y_screen_reader_audit_results.md` §1/§2'ye yazılamaz; defter BOŞ, dört
kriter de ☐. Koşu `REMINDER: A-08 is HUMAN-BLOCKED. Nothing above counts as a
screen-reader PASS.` satırını basmaya devam ediyor — **kaldırılmadı**.

**Blocker sayısı DEĞİŞMEDİ (üç). §8 verdict BLOCKED kalır.**

---

#### 6.7.7 P11-2 KAPANDI — görsel kapı 8 → 23 (2026-08-11)

**Verdict ve blocker sayısı DEĞİŞMEDİ.** P11-2 blocker değildi; §8 hâlâ **BLOCKED**, açık
blocker sayısı hâlâ **üç** (1, 2, 4). **P11 KAPANMADI** — **P11-1** (branch protection,
repo ayarı → **insan kararı**), **P11-6b** ve **P11-8** (Lighthouse) **ele alınmadı**.
Tam kayıt ve ham çıktılar: `docs/releases/evidence/2026-08-11/P11_2_visual_coverage.md`
(+ `p11_2_ci_visual_run1.txt`, `p11_2_ci_visual_run2.txt`,
`p11_2_ci_visual_run3_same_commit.txt`, `p11_2_seed_only_calibration.txt`,
`p11_2_visual_cycle1.txt`, `p11_2_visual_cycle2.txt`, `p11_2_baseline_dimensions.txt`).
PR **#665**.

**Kapsam 8 → 23, ve liste artık YAZILMIYOR.** Kapı sekiz elle yazılmış sayfayı assert
ederken axe scan, keyboard sondaları ve insan sapma incelemesi yirmi üç rotayı geziyordu;
kalan onbeşte piksel koruması yoktu ve bunu **söyleyen bir satır da yoktu** — okuyucu yeşil
bir "visual gate" görüp ürünü kapsadığını sanıyordu. Liste artık
`utils/screenshotMatrix.ts::TARGET_PAGES`'ten türüyor (P11-6'nın keyboard sondası için
kullandığı **aynı** tekil kaynak), böylece oraya eklenen bir rota bir sonraki koşuda
sessizce kapsamsız kalmak yerine assert ediliyor.

**Sekiz mevcut baseline YENİDEN ÜRETİLMEDİ.** Snapshot adları slug'a çevrildi
(`strategy-standalone → strategy-details`, `trading-signal-standalone → trading-signal`,
`trade-log-standalone → trade-log`, `run-result → run-results`); git bunları **saf rename**
olarak kaydetti (`Bin`, byte farkı yok) → eski sekiz sözleşme **aynen** duruyor. A-01'in
dürüstlük notu korundu: bunlar hâlâ standalone rotalar, Mainboard inline editörü değil.

**Kararlılık iddia edilmedi, ÖLÇÜLDÜ — runner'da iki kez, AYNI commit'te.**

| Koşu | Nerede | Sonuç |
|---|---|---|
| `a75f5e7` | GitHub runner | 22 passed · **1 failed (`analysis-lab`)** · 4.2 dk |
| `fa0c6a2` | GitHub runner | **23 passed** · 4.0 dk |
| `fa0c6a2` (rerun, taze stack + taze seed) | GitHub runner | **23 passed** · 4.0 dk |

Öncesinde yerel Linux konteynerinde iki tam döngü (her biri `down -v` → rebuild → reseed →
`npm test` → `npm run visual`), yani ikinci döngü **taze ULID / timestamp / rastgele
kullanıcı adı** gördü.

**Süre etkisi ölçüldü: `e2e` job'ında 1.4 dk → 4.0 dk (+2.6).** Test başına 10.5 s → 10.4 s
— maliyet neredeyse tamamen rota **sayısından**, rota başına maliyetten değil. Kapsam
**kısılmadı**, paralelleştirme gerekmedi.

**YAN BULGU (a) — yazılı olmayan önkoşul; P11-3b'yi CEVAPLAR.** İlk kalibrasyon 4/8 düştü.
Sebep repoda hiçbir yerde yazmıyordu: **baseline'lar salt-seed stack'i değil, `npm test`
SONRASI durumu tarif ediyor** — `e2e.yml` ikisini aynı job'da sırayla koşuyor, yani kapının
fotoğrafladığı sayfalar journey suite'inin az önce yarattığı varlıkları içeriyor. Aynı
commit, aynı imaj, tek fark DB durumu: mainboard **929↔900**, ready-check **947↔900**,
create-package **1411↔1396**, strategy-details **900↔1135**. Bu, P11-3b'nin açık sorusunu
kapatır: yükseklik **seed'e** değil **journey sonrası duruma** duyarlı ve CI o durumu her
koşuda üretiyor; ayrıca aynı **1135 px Linux'ta da** ölçüldüğü için P11-3b'nin gözlemi bir
platform artefaktı **değil**. Yeniden üretim sırası artık `frontend/e2e/README.md`'de.

**YAN BULGU (b) — "Linux" ile "runner" aynı şey değil.** Baseline'lar
`mcr.microsoft.com/playwright:v1.55.1-noble` içinde üretildi ve bu imaj 23 sayfanın
**22'sini** runner ile birebir verdi; `analysis-lab` vermedi: konteynerde `1440x1496`,
`ubuntu-latest`'te `1440x1490`. **Jitter değil** — runner iki ardışık denemede
**byte-identical** çıktı üretti (`md5 12388809…`); kararlı ~6 px reflow, sebebi o sayfanın
boş-durum sembol glifleri (◇, ⧗) iki imajda farklı fontlara düşüyor. O baseline **CI
artefaktından** alındı; tolerans **genişletilmedi**, diğer 22 dosyaya dokunulmadı.

**Yerelde görülüp CI'da ÜRETİLEMEYEN bir gözlem — kalem AÇILMADI.** Bu makinede
`/backtest/ready-check` yüksekliği **946/947/950** arasında salınıyordu (tek testin kendi
retry'ları arasında bile) ve iki yerel döngüde de tekrarladı; **runner'da üç koşunun
üçünde de GEÇTİ**. Dolayısıyla CI'da bir flake **değildir** ve öyle raporlanmadı; §6.7'ye
kalem eklenmedi, yalnız kanıt belgesine yazıldı ki CI-dışı bir Linux host'unda yeniden
üretmeye çalışan bir sonraki kişi yanılmasın.

**v18 uyum incelemesi — 15 baseline, TEK TEK, toplu onay YOK.** Referans: kanonik v18
mockup + `frontend/e2e/screenshots/prototype/**` + adjudicated defter
`docs/implementation/v18_visual_deviations.md` (A-06 derin kıyas, D-1 imzalı). **Hiçbir
YENİ, imzasız sapma dondurulmadı.** Zaten adjudicated olup **artık kapı tarafından
dondurulan** açık kusurlar açıkça bildirildi: **F-2** (`package-library` makine-değeri
etiketleri), **F-4** (`portfolio` "+ Add item" ham `mbi_…`), ve **F-07 sınıfı** ham
`btres_…` kimlikleri (`panel-logs`, `results-history`). **F-7** `embedded-packages`'ta
**FIXED** doğrulandı (insan-okur "active revision pinned"). D-10 (45 accent-blue düğüm,
imzalı kalıcı sapma) baseline'larda **beklendiği gibi** görünür — yeniden dosyalanmadı.
Per-sayfa notlar kanıt belgesinin §7'sinde.

**A-08 ile KARIŞTIRILAMAZ.** Piksel karşılaştırması ekran-okuyucu kanıtı **değildir**; bu
bölümün hiçbir çıktısı `docs/audit/a11y_screen_reader_audit_results.md` §1/§2'ye
yazılamaz. Defter BOŞ, dört kriter de ☐, #514'ün durumu değişmedi.

**Blocker sayısı DEĞİŞMEDİ (üç). §8 verdict BLOCKED kalır.**

---

#### 6.7.8 P1-B1/B2 + P8-B1/B3 KAPANDI — sayının sahibi değişti (ADIM 40, 2026-08-11)

**Verdict ve blocker sayısı DEĞİŞMEDİ.** Dördü de blocker değildi; §8 hâlâ **BLOCKED**,
açık blocker sayısı hâlâ **üç** (1, 2, 4). **P8 KAPANMADI** — P8-B2 açık (aşağıda).

**Çekirdek karar: sayıyı güncellemek dördüncü tekrarı garanti ederdi.** Bu, elle yazılmış bir
sayının bayatladığı **üçüncü** kayıttı ve ADIM 27'nin doküman-gerçek kapısı hiçbirini
yakalamamıştı — çünkü o kapı **üretilmiş** olguları koruyor, bu sayılar ise elle yazılmış
düzyazıydı. Her kalemde "1 = üretilene işaret et / 2 = üretime ekle / 3 = bayatlamayacak
biçimde elle yaz" merdiveni sırayla soruldu ve **ilk uyan** seçildi:

| Kalem | Seçilen | Neden |
|---|---|---|
| **P1-B1** (`BACKEND_LAYERS.md` 37/38 · 14/16) | **2 → sonra 1** | Sayı ucuzca üretilebilir (dosya sistemi yürüyüşü), bu yüzden üreticiye eklendi; ardından codemap'ten **silinip** üretilmiş satıra işaret edildi. Yalnız 1'i seçmek olmazdı: üretilmiş bir dosyada olmayan sayıya işaret edilemez |
| **P1-B2** (`CLAUDE.md` dual-token 16 ↔ 17) | **1** | Op-seviyesinde **semantik** bir sayı; ucuz bir statik yürüyüşle türetilemez (ampirik `reconcile_occ_tokens` çağrı yeri **12**'dir, op sayısı **17** — yardımcı fonksiyonlar birden çok op'a hizmet ediyor). Kanonik, tek tek sayan liste zaten `BACKEND_ROUTES.md` §DUAL-TOKEN'da vardı → `CLAUDE.md`'deki kopya **kaldırıldı**, sayı ikinci kez yazılmıyor |
| **P8-B1** (docstring gerekçesi) | **3** | Bir gerekçe üretilemez. Yeni metin **mutlak sayı ve dosya:satır içermiyor**; guard'ın kapsamını tekrar etmek yerine `jobs/delivery.py` docstring'ini tek otorite olarak gösteriyor — yani aynı biçimde ikinci kez bayatlayamaz |
| **P8-B3** (aktör tablosu satır no) | **sembol adı** | Satır numarası yapısal olarak bayattır. Aktör adı **zaten** sembolün kendisidir (`apps/worker/actors.py::<aktör>`), yani kolon fazlalıktı → **kolon silindi**. Numarayı elle kaydırmak bir sonraki PR'da yine kayardı |

**Yeniden ölçüldü, rapordaki sayı kopyalanmadı.** `queries` **38** (rapor: 38 ✓), `jobs`
**16** (✓), `commands` **32**, `domain/` **26 paket**; dual-token codemap listesi tek tek
sayıldığında **17** (✓). Aktör tablosu: `@dramatiq.actor` tanımları **12**, tablodaki satır
numaralarının **11'i yanlış** (`run_market_data_analysis` `:45` yazıyor / gerçek `:70`), yalnız
`system_heartbeat :39` tutuyor — B3'ün "~24 satır kaymış" ifadesi doğrulandı.

**Ölçüm, raporun kendi ifadesini de çürüttü.** §6.7'nin *"`BACKEND_LAYERS.md` **içerik olarak
tam**"* cümlesi yanlıştı: `jobs` tablosu 16 modülün **14'ünü** adlandırıyordu — `delivery.py`
(ADIM 21 at-least-once teslim kapısı) ve `heartbeat.py` (ADIM 25 worker canlılığı) hiç satır
almamıştı. **Bu tam olarak bir sayının göremeyeceği kusurdur**, ve bayat sayının nedeniydi.
İki satır da eklendi.

**Tekrarı ne engelliyor (yeni kapı).** `scripts/generate_repository_facts.py::check_codemap_coverage`
— `--check` yolunda, `ci.yml`'a **zaten bağlı** olan aynı adımda koşar:

* her `application/{commands,queries,jobs}` modülünün BACKEND_LAYERS.md'de **satırı** var mı
  (katman bölümüne **kapsamlı** arama — `market_data.py` üç katmanda birden var, bütün-dosya
  eşleşmesi eksik satırı yanlışlıkla örterdi);
* her `@dramatiq.actor` JOBS_AND_EVENTS.md aktör tablosunda **var mı** ve **doğru kuyrukta mı**
  (kuyruk o satırın operasyonel yarısıdır: `data` scheduler sweep'inin **dışındadır**, yanlış
  kuyruk kayıp mesajın geri gelip gelmediğini yanlış anlatır).

Gerekçe: **sayı değil, üyelik kapıya bağlandı.** Bir sayı yalnız birinin bir kez saydığını
kaydeder; eksik satırı göremez.

**Negatifi kanıtlı** (`backend/tests/contract/test_repository_facts_guard.py`, 5 yeni test):
tam harita **sessiz** · eksik modül satırı → **1 bulgu** · başka katmandaki **aynı adlı** modül
eksik satırı **örtmüyor** · satırsız aktör → **1 bulgu** · yanlış kuyruk → **1 bulgu**. Artı
üretilmiş sayıların **transkripsiyon değil türetme** olduğunu pinleyen bir test.

**Ürün kodu değişmedi.** Tek dokunuş `pending_data_job_dispatch`'in **docstring**'i; imza,
gövde ve `__all__` aynı, fonksiyonun beş assert'i (`test_gateway_parity_s4.py`,
`test_gateway_parity_trading_signal.py`) değişmeden geçiyor.

**AÇIK KALAN — bu slice'ın kapatmadıkları (dürüst sınır):**

1. **P8-B2** — Create-Package durable admission uçları **200**, diğer dokuzu **202**. Bu bir
   belge sapması **değil**, çözülmemiş bir **API sözleşmesi** tutarsızlığıdır: wire contract'ı
   ve muhtemelen frontend'i etkiler, doc 06'nın kendi §-taksonomisi otoritedir ve **bu koşuda
   da okunmadı**. Ucuz belge PR'ına karıştırılmadı → **ayrı PR + ürün kararı**.
2. **P8-B3b (YENİ)** — `JOBS_AND_EVENTS.md` gövdesindeki ~30 `:NN` referansı. Aynı kusur,
   ölçüldü, **düzeltilmedi**; her biri ayrı doğrulama ister → ayrı PR. Sınır dosyanın kendisine
   yazıldı, böylece bir sonraki okuyucu onlara güvenmeden önce grep'liyor.
3. **Diğer codemap'lerdeki satır numaraları** (`BACKEND_LAYERS.md` `config.py:118-119` gibi)
   bu koşuda **ölçülmedi**. Yeni kapı **satır numarası doğrulamıyor**, yalnız üyelik ve kuyruk.

**Blocker sayısı DEĞİŞMEDİ (üç). §8 verdict BLOCKED kalır.**

---

#### 6.7.9 P8-B2 **KAPANDI** — iki uç hizalandı (ADIM 41), iki uç PO kararıyla çevrildi (ADIM 47)

> **KAPANIŞ — ADIM 47, 2026-08-12.** Aşağıdaki ADIM 41 kaydı **tarihsel olarak doğrudur ve
> değiştirilmemiştir**; PO'ya sorulan soru en altta duruyor. **Cevap 2026-08-12'de geldi:**
> `../validate` ve `../baseline-parse` **200 → 202**. Bu, aşağıda önerilen (1) seçeneği
> **değil**, onun Create-Package yarısıdır: PO `POST /library/{id}/validation-runs` (201)
> ucunu kapsam dışında bıraktı, o uç **201'de KALDI** → iki sarmalayıcı hâlâ aynı validation
> run'ı iki farklı status'le sarıyor. **Bu ayrışma KAPANMADI, kayda geçirildi**; kapatmak
> yeni bir PO kararı ister.
>
> **Karar bir ATIF DEĞİL.** Kanonik bu iki uç için hâlâ bir status **vermiyor** (baseline-parse
> için ucu bile adlandırmıyor). Otorite PO'nun kararıdır, "repo zaten 202 döndürüyor" gözlemi
> değil — ADIM 41'in reddettiği çıkarım hâlâ reddediliyor. İleride kanonik bir sayfa bu
> uçlar için bir kod adlandırırsa **kanonik kazanır ve karar yeniden açılır**.
> Gerekçe: 200, bu yanıtların taşımadığı **tamamlanmış bir sonucu** reklam ediyordu
> (`checks: []`, `parser_version: ""` — hepsi worker'ı bekleyen yer tutucular).
>
> **Yapılanlar (ADIM 47):** iki route `status_code=202` + **tipli** gövde
> (`ValidationRunAcceptedResponse` 8 alan · `BaselineParseAcceptedResponse` 8 alan) —
> bare `dict[str, Any]` sözleşmeyi şemadan gizlerdi (O-30 dersi, ADIM 41 ile aynı şablon,
> yeni desen icat edilmedi). `docs/openapi.json` tazelendi. **Semantik DEĞİŞMEDİ:** iki uç
> bu slice'tan önce de durable job kuyruğa alıyordu, sonra da alıyor — değişen yalnız sevk
> edilen semantiğin **doğru status ile adlandırılması**.
>
> **Üç bağımlılık YENİDEN ölçüldü (ADIM 41'in ölçümüne güvenilmedi):**
> * iki komut (`start_package_validation_run`, `start_baseline_parse`) gerçekten
>   `_enqueue_create_package_job` → `enqueue_job` çağırıp iş bitmeden dönüyor → 202 doğru;
>   senkron olsalardı bu slice DURUP raporlayacaktı.
> * **Frontend:** `lib/apiClient.ts` yalnız **204**'ü ayırır, gerisinde `response.ok`
>   kullanır → 200↔202 istemciye görünmez; `lib/createPackage.ts` hiçbir status'e assert
>   etmez. **Frontend kodu ve testleri DEĞİŞMEDİ** (değişmesi gerekmedi).
> * **Idempotency-Key:** `run_idempotent` yalnız **gövdeyi** saklar; status route
>   dekoratöründe yaşar ve gövde anahtarları **birebir aynı kaldı** → O-30'un "eski zarf
>   katı şema altında 500'e döner" tuzağı burada oluşamaz, **backfill gerekmedi**.
>
> **Pin:** `tests/contract/test_p8b2_admission_status.py` — `_EXPECTED` iki satırda 202'ye
> çevrildi (etiket `PO 2026-08-12 — canonical silent`, **ALIGNED etiketiyle birleştirilmedi**),
> `test_validate_and_baseline_parse_are_202_by_product_owner_decision` kararı adıyla pinler,
> `test_every_202_admission_body_is_published_in_the_schema` artık **dört** gövdeyi birden
> doğrular. Türetilmiş admission kümesi ve on üç ucun status pini **olduğu gibi duruyor**.
>
> **Verdict ve blocker sayısı DEĞİŞMEDİ: 1 (yalnız A-08), §8 BLOCKED.**

**(ADIM 41, 2026-08-11 kaydı — tarihsel, değiştirilmedi.)**

**Verdict ve blocker sayısı DEĞİŞMEDİ.** P8-B2 blocker değildi; §8 hâlâ **BLOCKED**, açık
blocker sayısı hâlâ **üç** (1, 2, 4). **Kalem KAPANMADI** — dördün ikisi PO'da.

**Önce ayırt edici ölçüm, sonra karar.** "Tutarsızlık gördüm, hizalayayım" refleksine
direnildi: her uç için tek soru soruldu — *iş isteğin İÇİNDE mi bitiyor, yoksa kuyruğa
alınıp bitmeden mi dönülüyor?* Küme elle sayılmadı; `application/` katmanında
`enqueue_job`'a **transitively** ulaşan fonksiyonlar çıkarıldı ve route tablosuna eşlendi:
**13 durable admission yüzeyi**, hepsi kuyruğa alıp dönüyor. **Senkron tamamlanan tek uç
yok** → sonuç (b) on üçünün hiçbirinde geçerli değil.

| Sınıf | Uç | Sevk edilen status |
|---|---|---|
| Create Package | `../pre-check` · `../generate-candidate` · `../validate` · `../baseline-parse` | **200** (dekoratörde status yok) + gövde `dict[str, Any]` |
| Library | `POST /library/{id}/validation-runs` | **201** (`PackageValidationRunAcceptedResponse`) |
| Diğer sekiz | backtest-runs · retries · market/research analysis · trade-log/trading-signal/package imports · purge | **202** |

**Raporun kendi sayısı yanlıştı.** §6.7 satırı *"diğer **dokuz** 202"* diyordu; ölçüm
**sekiz** 202 + **bir** 201 buldu. 201'i döndüren uç (`/library/{id}/validation-runs`)
`../validate` ile **aynı** validation run'ı sarar — yani sapma dört değil **beş** uçtaydı
ve raporun ifadesi bir yüzeyi görünmez kılıyordu.

**Kanonik'e soruldu — ve kanonik uç uç FARKLI konuşuyor.** Sayfa belgesi kendi ucunun
otoritesidir; bulunanlar:

| Uç | Kanonik ne diyor | Sonuç |
|---|---|---|
| `../pre-check` | **doc 07 §10.3** birebir: *"202 accepted or idempotent completed response: job/scan id, state precheck_pending/checking"* | **(a) HİZALA → 202** |
| `../generate-candidate` | **MTR §7.1** literal wire contract: `POST /package-requests/{id}/generate-candidate -> 202 Accepted { candidate_job_id, state:"CANDIDATE_GENERATING", … }`; **MTR §4.2**: *"Senkron LLM cevabı bekleme; 202 Accepted + job_id döndür"*; **doc 07 §10.3** tekrar eder | **(a) HİZALA → 202** |
| `../validate` | **Status YOK.** doc 06 §7 davranışı anlatır (*"Returns validation_run_id; rows show queued/running"*), doc 08 §7 ucu listeler (*"Job status via durable event/poll"*), **MTR §13** yalnız *"uzun analyze/parse/validate işlemleri HTTP request içinde tamamlanmaya çalışılmaz"* der — bu **davranış** kuralıdır, kod kuralı değil | **(c) UYDURMA → PO** |
| `../baseline-parse` | **Ucun kendisi bile yok.** doc 06 §7'de tek baseline yüzeyi vardır (*"asset upload and parse are async"*), MTR §10.2 yalnız `POST /package-revisions/{id}/baseline-assets` listeler. Upload(201)/parse ayrımı **sevk edilmiş bir ayrıştırmadır** → hizalanacak kanonik bir uç yok | **(c) UYDURMA → PO** |

**Sevk edilmiş desen bir OLGU olarak kaydedildi, kural olarak KULLANILMADI.** 202 bu
repoda "durable job" demek değil: `agent-directives`, `agent-runtime/pause` · `/resume`,
`agent-runs/{id}/stop` ve `backtest-runs/{id}/cancel` de 202 döner ama `enqueue_job`
çağırmaz. Yani gerçek desen *"etki yanıttan sonra iniyorsa 202"*tır — ve **kanonik boşlukta
bu desenden wire contract türetmek tam olarak reddedilen şeydir**. `../validate` ve
`../baseline-parse` bu yüzden **200 kaldı**; kod değişmedi.

**Wire contract değişikliği — üç bağımlılık ÖLÇÜLDÜ, tahmin edilmedi:**

* **Frontend:** `lib/apiClient.ts::executeRequest` yalnız **204**'ü ayırır, gerisinde
  `response.ok` kullanır → 200↔202 ayrımı istemciye **görünmez**. `lib/createPackage.ts`
  hiçbir status'e assert etmez. Frontend testleri `fetch`'i stub'lar (status'ü **testin
  kendisi** üretir), yani sunucu status'ünden **yapısal olarak** etkilenemezler.
* **Idempotency-Key:** `run_idempotent` yalnız **gövdeyi** saklar (`response_ref`); status
  route dekoratöründe yaşar. O-30'un "eski zarf katı şema altında 500'e döner" tuzağı
  burada **oluşamaz** — backfill gerekmedi, ve replay ADIM 41 testinde uçtan uca koştu.
* **Testler:** dört ucun hiçbirinde HTTP status assert'i yoktu (`test_create_package_contract.py`
  yalnız hata yollarını sürüyor) — yani sözleşme hem **yayımlanmamış** hem **testsizdi**.

**Gövde de yayımlandı (O-30 dersi).** İki hizalanan uç `dict[str, Any]` döndürüyordu →
drift guard yeşil kalırken sözleşme şemada **görünmüyordu**. Artık
`PrecheckAcceptedResponse` (11 alan) ve `CandidateAcceptedResponse` (5 alan)
`components.schemas` altında. Alan düşmediği **hand-written beklentiyle değil**, saklanan
idempotency zarfıyla karşılaştırılarak kanıtlandı (`test_typed_contract_replay_parity.py`,
2 yeni test): `resp.json() == IdempotencyKey.response_ref` **ve** replay aynı gövdeyi aynı
**202** ile döndürür.

**Tekrarı ne engelliyor (yeni kapı).** `backend/tests/contract/test_p8b2_admission_status.py`:
admission kümesini **türetir** (`enqueue_job` transitive closure) ve sınıflandırma tablosuyla
karşılaştırır. **Negatifi kanıtlı** — sınıflandırılmamış bir admission ucu eklendiğinde
*"new/unclassified: ['/package-imports']"* ile düşer; `status_code=202` geri alındığında
*"assert 200 == 202"* ile düşer (ikisi de bu koşuda çalıştırıldı). Ayrıca on üç ucun
**hepsinin** yayımlanmış status'ü pinlenir: bir "tutarlılık süpürgesi" sevk edilmiş bir
sözleşmeyi sessizce yeniden kesemez.

**PO'ya sorulan (kod DEĞİŞMEDİ, karar bekliyor):**

> Create-Package `../validate` ve `../baseline-parse` uçları — ve onlarla aynı run'ı saran
> `POST /library/{id}/validation-runs` (201) — durable admission oldukları hâlde kanonik
> bir status taşımıyor. **Üç okuma var:** (1) üçü de **202**'ye çekilir (sevk edilmiş
> desenle tam tutarlılık; üç yayımlanmış sözleşme değişir), (2) **olduğu gibi kalır**
> (hiçbir sözleşme kırılmaz; sayfa düzlemi 202/202/200/200 kalır), (3) yalnız
> `../validate` 202 olur ve `validation-runs` 201'de bırakılır (ikisi farklı kaynak
> yaratıyor gerekçesiyle). **Öneri: (1)** — üçü de admission ve 202 bu repoda tam olarak
> "etki yanıttan sonra iniyor" demek; maliyeti bir openapi snapshot + üç pin. Ama bu bir
> **ürün kararıdır** ve agent vermez.

**Bu dalganın DOKUNMADIKLARI (dürüst sınır):** P8-B3b (`JOBS_AND_EVENTS.md` gövdesindeki
~30 `:NN`) hâlâ açık · diğer status sınıflarının genel denetimi yapılmadı (bu slice yalnız
**durable admission** eksenidir; 200/201 ayrımı, 204'ler ve hata kodları kapsam dışı) ·
`BACKEND_ROUTES.md`'nin `create_package.py` tablosundaki `:NN` kolonu bu PR'ın kendi
kaydırmasını taşımamak için **silindi**, diğer tablolar ölçülmedi.

**P8 KAPANMADI.** **Blocker sayısı DEĞİŞMEDİ (üç). §8 verdict BLOCKED kalır.**

---

#### 6.7.10 P1-Gate3 ELE ALINABİLİR HALE GELDİ — ölç, sınıflandır, ratchet'le, pinle (ADIM 42, 2026-08-12)

**Kalemin iddiası:** *"8 uncovered kriter + 131 partial kriter (kapı yeşil sayıyor)"*.

**1) ÖLÇÜM — sayılar bayat değildi.** Kapı `docs/audit/acceptance_semantic_scan.py`;
`ci.yml`'daki adım `--report` ile koşuyor. 2026-08-12 koşusu **383 kriter / 1175 clause**
üzerinde 2026-08-07 dağılımını **birebir** yeniden üretti: covered 229 · partial 131 ·
uncovered 8 · deliberate_future_dev 8 · not_applicable 7. Yani rapor doğru sayıyordu.

**Kapı "partial"ı gerçekten geçer sayıyor mu?** Kaynağından doğrulandı: **evet, ve
kastederek.** `validate()` haritanın **kendisi hakkında yalan söylemediğini** kanıtlar
(çözülmeyen node, kanıtsız `covered`, jsdom'a dayanan sunucu ekseni…). Statü **dağılımına**
hiç bakmaz. Bu bir kusur değil, eksik bir yarıydı: kapı sözleşmenin ne kadarının
kanıtlandığını **hiç sınırlamıyordu**, o yüzden 139 açık kalem aylarca yeşil geçti.

**2) SINIFLANDIRMA — ve neden üç sınıf yetmedi.** 139 kalemin **tamamının** `notes`
gerekçesi okundu. Brief üç sınıf öngörüyordu (eşleme / gerçek kısmi / yapısal). **Veri
üçe uymadı.** Dördüncü bir durum baskındı: kriterin **adlandırdığı kod, alan, hata sınıfı
ya da Agent tool'u üretimde hiç yok**. Bunlar ne eşleme hatası (kapsanan bir test yok), ne
gerçek kısmi kapsam (uygulanmış bir davranış yok), ne de yapısal olarak kapatılamaz (pekâlâ
kapatılabilir — **kod yazarak**). Üçüne sıkıştırmak, ürün işini "test borcu" ya da
"gerekçelendirilecek" diye yanlış etiketlerdi — bu dalganın tam olarak kovaladığı hata.
Sonuç taksonomi:

| Sınıf | Ne demek | Kim kapatır | Sayı |
|---|---|---|---:|
| **A** | Davranış sevk edilmiş, **spec'in kullandığı addan farklı bir adla** | Adjudication + tek satır pin | **1** |
| **B** | Davranış uygulanmış, **iddia eksik** | Test slice'ı (tek sahibi budur) | **95** |
| **C** | Açık clause **doğası gereği iddia edilemez** — bir *belge* hakkında cümle, V1'de bilerek kapalı özellik, ya da Production'ın kuramayacağı senaryo | Kimse. Gerekçelendirilir, "kapatılmaz" | **6** |
| **D** | Kriterin **adlandırdığı şey üretimde yok** | Ürün işi; birkaçı önce **ürün kararı** ister | **32** |

**BULGU — "131 partial" kelimesi ürün işini gizliyordu.** Açık borcun **%24'ü (32/134)
sınıf D'dir ve hiçbir test onu kapatamaz.** `AT-06` (uyumluluk kuralı yok), `AT-13`
(ifade DSL'i / AST yok), `AT-17` (sunucu tarafı blackout doğrulayıcı yok), `CP-16` ·
`PC-15` · `PL-20` · `ESP-14` · `RF-13` (Tool Gateway'de ilgili tool **hiç yok**),
`AM-15` (`metric_profile` `TRASH_OBJECT_LOCATIONS`'ta değil), `FD-09` (split/seed kolonu
yok)… Aggregate'i test borcu diye okumak, bu 32 kalemi **yanlış slice'a bütçelemekti.**
Ayrıca **sınıf A yalnız 1** — "ucuz eşleme düzeltmesi" umudu neredeyse boş çıktı, çünkü
haritayı yazan kişi komşu testleri ödünç almayı zaten reddetmişti.

**3) RATCHET — mevcut desen, yeni desen değil.** Şablon `frontend/e2e/a11y-baseline.json`
+ `specs/13-a11y-scan.spec.ts`. Karşılığı `docs/audit/acceptance_coverage_baseline.json`:
`ceilings.status` ve `ceilings.debt_class` **tavan** (ölçülen > tavan → **kırmızı**),
`ceilings.total_criteria` ise **taban** — rahatsız edici bir `partial` kriteri **silmek
ilerleme sayılamaz**. Tavanın **altına** düşülürse kapı sıkılaştırılmış bloğu basar.
**Pay bırakılmadı** ve bu bir testle kilitli (`test_the_frozen_ceiling_leaves_no_headroom`):
ölçümün üstünde bir tavan, bir sonraki kanıtsız kriteri sessizce **lisanslar**.
Sınıflar **ayrı** ratchet'lenir — yoksa aynı PR'da sekiz B kapatıp sekiz D eklemek net
yeşil verirdi. Kapı `ci.yml`'a bağlandı (`--report --ratchet`) ve **negatifi kanıtlı**:
tavan bir düşürülünce CLI `exit 1` + `status.partial: 126 measured, ceiling 125 (+1)`
verdi; altı unit test dört kırmızı yolu da provoke ediyor.

**4) PİNLENEN ÜÇ GRUP — ve raporun bu satırdaki İKİ HATASI.**

* **`AOS-17` / `TS-17` — rapor HAKLIYDI, doğrulandı.** `ACTIVE_RUN_DEPENDENCY` `backend/src`
  ve `backend/tests` genelinde **sıfır** hit; `OBJECT_IN_ACTIVE_RUN` testlerde yalnız bir
  **docstring**'de geçiyordu. Test **exception tipini** assert ediyordu, wire kodunu asla →
  her iki yazım da serbestçe kayabilirdi. **Adjudication O-31** (O-02 emsali): üç belge tek
  bir reddi üç türlü adlandırıyor — `ACTIVE_RUN_DEPENDENCY` (doc 03 §14, doc 04 §15),
  `DELETE_BLOCKED_BY_RUNNING_JOB` (doc 20 §15), `OBJECT_IN_ACTIVE_RUN` (doc 01/15). **Sevk
  edilen ad kanoniktir, diğer ikisi tarihseldir.** Pin: `test_active_run_blocks_work_object_delete`
  artık `code == "OBJECT_IN_ACTIVE_RUN"` + `http_status == 409` + engellenen delete'ten sonra
  **sıfır** `TrashEntry` assert ediyor. Kapanan: `AOS-17`, `TS-17`, **`TR-06`** (aynı
  adjudication) ve **`TL-19`**.
* **`AT-04` — rapor bunu YANLIŞ gruplamıştı.** Pinlenecek bir şey yok: `MARKET_DATA_INSTRUMENT_MISMATCH`
  **hiç yok** ve Save-zamanlı çapraz kontrol **uygulanmamış** → **sınıf D**. Sevk edilen
  davranış RUN-zamanlıdır (`RunFailureCode.INSTRUMENT_MISMATCH` → `RUN_FAILED_INSTRUMENT_MISMATCH`)
  ve **zaten pinlidir** (`test_backtest_persistence.py:490`), haritada da `c1: covered`
  olarak duruyordu. Yani bu kalem "pinsiz" değil, **uygulanmamış**tı.
* **`TL-20` / `AOS-18` — brief K-06'yı YANLIŞ tarif etmişti.** Brief K-06'yı *upload
  dosya-tipi kapısı* diye tanımlıyor; `CLAUDE.md`'de o **K-07**'dir, **K-06** ise *Trash tip
  kataloğu*'dur — ve `TL-20`'nin kendi notu da K-06'yı trash-entry invariant'ı olarak
  anıyor. **İkisi de ele alındı.** (a) Gerçek tehlike: `mb_cmd.soft_delete_work_object`
  yolunda **hiçbir test** `TrashEntry`/`AuditEvent`/`OutboxEvent` sorgulamıyordu — artık
  sorguluyor (`entity_type == "work_object"`, birer `entity.soft_deleted` satırı).
  **İlk koşuda GEÇTİ**: invariant tutuyor, bu bir kusur keşfi değil, gerçek davranışın
  kilitlenmesidir. `AOS-18` kapandı, `TL-20` **`c3` yüzünden partial kaldı** (sınıf B).
  (b) Brief'in kastettiği K-07 fail-closed upload kapısı **ölçüldü: zaten pinli** — beş
  sayfa taksonomisinin beşi de assert ediliyor, `filename=None` fail-closed vakası dahil
  (`test_gateway_parity_trading_signal.py:425`). Yeni test gerekmedi.

**5) BACKLOG — bu PR'ın ana çıktısı.** `docs/audit/acceptance_coverage_debt_ledger.md`,
haritadan **üretilir** (elle sayı yazılmaz; bayatlığı `test_the_debt_ledger_is_not_stale`
kırmızıya çevirir). 134 kalem sınıf → belge → id sırasıyla, her birinin kendi gerekçesiyle
listeli. Planlama sırası: **A (1) → B (95) → D (32, ürün) ; C (6) hiç kapatılmaz.**

**Bu dalganın DOKUNMADIKLARI (dürüst sınır):** kalan **134 kalemin hiçbiri kapatılmadı**
(kapsam dışıydı) · sınıf D'nin **ürün kararı isteyen** alt kümesi (`RD-02`, `RD-03`,
`AM-11`, `AOS-02` — spec ile sevk edilen davranış **çelişiyor**) **PO'ya sorulmadı**, yalnız
deftere kaydedildi · sınıflandırma her kaydın **kendi `notes` gerekçesinden** okundu, 134
kaydın test gövdeleri **tek tek yeniden okunmadı** — bu, 139 kalemi kapatmak demek olurdu
ve slice'ın dışındaydı; bir yanlış sınıflandırma bu yüzden mümkündür ve `notes` otoritedir ·
`acceptance_id_scan.py` (zayıf kardeş tarayıcı) ve Master doc'un 21 modül-düzeyi kabul
tablosu hâlâ kapsam dışı.

**P1-Gate3 KAPANMADI** — ele alınabilir hale geldi. **Blocker sayısı DEĞİŞMEDİ (üç).
§8 verdict BLOCKED kalır.**

**GÜNCELLEME — ADIM 48 (2026-08-12): defter işlenmeye BAŞLANDI, kalem hâlâ AÇIK.**
Sınıf-B parti 01, doc 05 (Trade Log) **backend** yüzeyinden **sekiz** kriter kapattı:
`TL-03` `TL-06` `TL-07` `TL-08` `TL-15` `TL-17` `TL-21` `TL-23`. Yeni ölçüm →
**`partial` 126 → 118**, **`debt_class.B` 95 → 87**; `uncovered` (8), **A** (1),
**C** (6) ve **D** (32) tavanları **el değmeden** kaldı ve `total_criteria` **383'te
sabit** — bir sınıf-B slice'ı bunları hareket ettiremez. **Ürün kodu değişmedi.**
Parti **tek belge + tek yüzey** ile sınırlı tutuldu; gerekçe
`acceptance_coverage_baseline.json` §`adjudication.class_B_batches_are_deliberately_small`.
Vakumda geçebilecek assertion'lar **negatif kontrolden** geçirildi (`PROJECT_HISTORY.md`
§ADIM 48). **İki bulgu AÇIK bırakıldı, ikisi de insan/PO kararı:** (1) `TL-16`'nın sınıfı
**şüpheli** — `c4`'ün istediği *"409 zarfı sunucunun kanonik durumunu taşır"* alanı
üretimde **yok** (`WorkObjectRevisionConflictError` `details` taşımıyor, raise argümansız),
yani **B değil D** görünüyor; yeniden sınıflandırma **yapılmadı** çünkü **D tavanını
yükseltirdi** ve tavan yalnız aşağı iner. (2) `TL-01.c4` bir **yol sapması**: kriter
`GET /packages` diyor, sevk edilen katalog `GET /library`. **P1-Gate3 KAPANMADI** —
**126** kalem açık (A=1 · B=87 · C=6 · D=32), bu parti borcun **%6'sını** kapattı.
**Blocker sayısı DEĞİŞMEDİ (bir — yalnız A-08). §8 verdict BLOCKED kalır.**

**GÜNCELLEME 2 — ADIM 49 (2026-08-12): ikinci parti, ve bir ÖNERİ HATASININ düzeltilmesi.**
Sınıf-B parti 02 dış work object'in **run provenance**'ından **beş** kriter kapattı:
`TL-12` (c2+c3) · `TL-20` (c3) · `TS-11` (c3) · `TS-21` (c1) · `AOS-21` (c1). Beşi de tek
bir eksik makineye dayanıyordu — *dış work object içeren kompozisyon üzerinde TAMAMLANMIŞ
bir Backtest Run* — ve o makine kuruldu. Yeni ölçüm → **`partial` 118 → 113**,
**`debt_class.B` 87 → 82**; `uncovered` (8), **A** (1), **C** (6), **D** (32) tavanları ve
`total_criteria` (383) **el değmedi**. **Ürün kodu değişmedi.**

**Bu güncellemenin asıl içeriği bir düzeltmedir.** ADIM 48'in kickoff'u `TL-11.c3`'ü
"kapatılabilir" diye önermişti; **bu öneri YANLIŞTI ve ölçümle çürütüldü.** Kriter
*allocation-enabled* bir kompozisyon üzerinde aktif bir run istiyor, ama bu build'de
paylaşımlı sermaye **admission'da fail-closed**
(`domain/allocation/capability.py::SHARED_ALLOCATION_STATUS = "future_dev"` →
`commands/backtest_run.py` **run, manifest ya da job yaratılmadan**
`ALLOCATION_SHARED_MODE_NOT_IN_BUILD` fırlatır). O run **kurulamaz**, dolayısıyla
**hiçbir test** kriteri kapatamaz — bu sınıf **C** tanımıdır, B değil. **Yeniden
sınıflandırılmadı**, çünkü B→C **C tavanını yükseltirdi** ve tavan yalnız aşağı iner;
bulgu deftere ve `baseline.json` §`adjudication`'a yazıldı. Böylece **üç** açık
sınıflandırma bulgusu var: `TL-11.c3` (C görünüyor), `TL-16` (D görünüyor),
`TL-01.c4` (yol sapması) — **üçü de insan/PO kararı.**

Ders kayda geçirildi: **bir kriteri partiye almadan önce, adlandırdığı davranışın
`backend/src`'te gerçekten sevk edildiğini ÖLÇ.** ADIM 48'in önerisi ölçülmediği için
yanlıştı.

**P1-Gate3 KAPANMADI** — **121** kriter açık (A=1 · B=82 · C=6 · D=32); iki parti
toplamda borcun **~%10**'unu kapattı. **Blocker sayısı DEĞİŞMEDİ (bir — yalnız A-08).
§8 verdict BLOCKED kalır.**

---

#### 6.7.11 P10-7 KAPANDI — saat zaten dolmuştu (ADIM 43, 2026-08-12)

**Bu kalemin en pahalı kısmı kod değildi, okumaktı.** Satır *"aktivasyon için 5 gecelik
baseline gerekiyor"* diyordu; slice'ın brief'i de saati **başlatmayı** planlıyordu. İkisi
de yanlıştı. Önce ölçüldü:

| Soru | Cevap |
|---|---|
| Gece işi var mı? | **Var** — `performance.yml` → `load-full`, cron `23 4 * * *`, **ADIM 24'ten beri**. Yazılacak bir şey yoktu. |
| Kaç gece birikmiş? | **Altı** — 2026-08-07 … 08-12. Altısı da `success`, altısında da `loadgen-baseline` artefaktı, hepsi `github-ubuntu-latest`, 16/40, **sıfır hata**. §6 beş istiyor; beşinci **08-11**'de doldu. |
| Baseline nerede kalıcı? | Artefakt (30 gün) yalnız **girdi**. Kapının baseline'ı artık **takipli dosya** → saklama süresine bağlı değil. |

Yani bu PR bir saat başlatmadı; **saati okudu ve kapıyı açtı**. Planlanan ikinci PR'a
gerek kalmadı.

**Bant türetildi, seçilmedi.** Ham kontrol (`meta`: kimliksiz, DB okumasız) altı gecede
**1.71×** kaydı — normalizasyonun varlık nedeni tam olarak bu ve ham p95 kapısının neden
hiç seçenek olmadığının kanıtı. Kontrol-normalize edilmiş eksende:

* senaryo bazında en kötü **max/min** yayılım: **1.92×** (`hypotheses`);
* ama kapının gerçekte değerlendirdiği nicelik bu değil — her gece **dondurulmuş
  baseline'a** karşı ölçülür. O eksende herhangi bir gecenin ürettiği en kötü oran
  **1.62×** (`admin_logs`, 08-07 gecesi).

README §6 adım 3 *"gözlenen yayılımın kabaca 1.5 katı"* diyor. Kapının ölçtüğü niceliğe
uygulandığında: `1.5 × 1.62 = 2.43` → bir ondalığa **yukarı** yuvarlanarak
**`--max-ratio 2.5`**. Gevşek okuma (1.5 × 1.92 = 2.88) **reddedildi**: daha geniş bir
bant için daha zayıf bir kanıt olurdu.

**Baseline olarak hangi gece donduruldu ve neden.** §6 adım 3 *"medyan koşu"* diyor. Altı
gece, 16 karşılaştırılabilir senaryonun medyan kontrol-normalize p95'ine göre
sıralandığında ortada tek koşu yok (çift sayı) → **alt-orta** alındı: run `31461912952`,
2026-08-11, `4e9512d2`. En hızlı geceyi dondurmak her sıradan geceyi regresyon gibi
gösterirdi; en yavaşı dondurmak bir regresyonu gizlerdi.

**Negatif kanıtlandı, sentetik fixture'da değil gerçek baseline'da:**

```
altı gecenin altısı da            PASS   (en kötü 1.62x, banda 1.54x pay)
enjekte 3.0x regresyon            FAIL   ← negatif kontrol
enjekte 2.4x regresyon            geçer  ← bandın gerçek sınırı
```

**§6 adım 5 alınmadı, ve bu bir karardır.** Prosedür açıkça *"yayılım o kadar genişse ki
kullanılabilir bant yoktur — bunu yaz ve kapıyı kapalı bırak"* çıkışını sunuyor. Bant
gözlenen her geceyi 1.54× payla geçtiği ve hâlâ 3.0×'i yakaladığı için o çıkış
**kullanılmadı**; gerekçe README §6'ya yazıldı.

**Kapının GÖREMEDİĞİ (gizlenmedi, yazıldı):**

* **2.5× altındaki hiçbir şey.** Gözlenen 1.62× hava durumu ile 2.5× bandı arasındaki bir
  regresyon merge olur ve kalır. Bant geniş, çünkü **altı örnek bir kuyruğu sınırlayamaz**.
  Daraltmak, arkasında daha çok gece olan **sonraki** bir karardır — kırmızı bir geceyi
  susturmak için yapılan bir düzenleme **değil**.
* **PR'daki hiçbir şey.** Kapı **geceliktir**. Latency'yi 3× bozan bir PR yeşil merge olur
  ve ertesi sabah `load-full` + `nightly-failure-notice` ile yakalanır. Bu, §1'in bilerek
  yaptığı takas.
* **Başka hiçbir runner class.** §2 zaten karşılaştırmayı yasaklıyor.
* Altı gecenin üçü iki sha üzerinde (`2cf7283d` iki kez) → örneklem **beş** ayrı commit.

**Concurrency kusuru bu kapıyı vurmuyor — varsayılmadı, iki yoldan doğrulandı.** İfade
okundu: `cancel-in-progress: ${{ github.ref != 'refs/heads/main' }}`, ve bir `schedule`
olayında `github.ref` **zaten** `refs/heads/main` → false. Log okundu: altı ardışık
zamanlanmış koşunun altısı da `success` + gerçek artefakt, hiçbiri cancelled,
`nightly-failure-notice` hiç ateşlemedi. Yeşil rozet buna yetmezdi; her koşunun **job ve
artefakt listesi** tek tek çekildi.

**Bant tek yerde yaşamıyor, üç yerde ve birbirini tutmak zorunda:** workflow'un
`--max-ratio`'su, `test_loadgen.py`'deki `_BAND`/`_OBSERVED_WORST_RATIO`, ve README §6.
`test_the_nightly_actually_passes_the_band_this_file_pins` ayrışırlarsa kırmızıya
çeviriyor → bandı yalnız workflow'da genişletmek **mümkün değil**.

Ham kanıt: `docs/releases/evidence/2026-08-12/p10_7_nightly_baselines.md` ·
`p10_7_control_normalised_spread.txt` · `p10_7_ratio_gate_replay.txt`.

**Verdict ve blocker sayısı DEĞİŞMEDİ.** P10-7 blocker değildi; §8 hâlâ **BLOCKED**, açık
blocker sayısı hâlâ **üç** (1, 2, 4). **P10 KAPANMADI** — P10-B2'nin PO yarısı, P10-B3,
P10-B4, P10-B5 ve P10-B6 açık.

---

#### 6.7.12 P11-8 KAPANDI — Lighthouse ratchet olarak bağlandı (ADIM 43, 2026-08-12)

İddia doğruydu: bağlı değildi. Bağlandı — **eşik olarak değil, ratchet olarak**.

**Neden ratchet.** *"performance ≥ 90"* gibi bir eşik, kimsenin ölçmediği bir sayıdır: 2
vCPU'luk paylaşımlı bir runner'da ya hiç kırılmayacak kadar düşük olur ya da hava
durumundan kırılacak kadar yüksek. Repo bu muhakemeyi zaten yazmıştı
(`performance/README.md` §1) ve soruyu zaten **iki kez aynı** cevaplamıştı: axe
(`a11y-baseline.json`) ölçülen düğüm sayısını dondurur, ADIM 42 ölçülen kriter sayısını
dondurur. Üçüncüsü **yeni desen icat etmedi**, ikincisinin şeklini aldı. Tek eksen farkı:
axe kötü düğüm **tavanı**, bu iyi skor **tabanı** dondurur.

**Kapsam: 23/23, kapsanmayan 0.** Liste elle yazılmadı; `screenshotMatrix.ts::TARGET_PAGES`
— axe scan'in, klavye sondalarının ve (ADIM 39'dan beri) görsel kapının **aynı** tekil
kaynağı. Matriste olup tabanı olmayan rota **kırmızı** verir: tabansız rota bir **boşluktur**,
geçiş değil. Alt küme seçilmedi çünkü gerekmedi — job uçtan uca **9 dk 48 sn**, ratchet
adımı **7.6 dk** (23 × 3 + warm-up = 70 Lighthouse koşusu), 75 dk timeout'un çok içinde.

**Gürültü stabilize edildi, tolerans genişletilmedi.** Atılan warm-up (ilk koşu V8 ısınmasını
ve soğuk HTTP önbelleğini emer; matristeki ilk rotanın kalıcı olarak kötü görünmesini
engeller) + rota başına 3 koşunun **medyanı**. `cpuSlowdownMultiplier: 1` — Lighthouse'un
kendi desktop preset'i, elle gevşetilmiş bir ayar değil; runner zaten yavaş, üstüne 4×
mobil yavaşlatma koymak kimsede olmayan bir cihazı modellerdi.

**Ölçülen taban** (ölçüm koşusu `31571413853`): performance **100** (22 rota) / **98**
(`panel-management`) · best-practices **96** (23) · seo **82** (23).

**İki otorite çakışması da önlendi:**

1. **a11y kategorisi hiç İSTENMİYOR.** `CATEGORIES` = `performance, best-practices, seo`.
   axe sevk edilmiş otoritedir (kural-bazlı düğüm tavanları + yazılı adjudication + D-10);
   ikinci ve daha kaba bir a11y sayısı onunla **çelişebilirdi**, bu yüzden **üretilmiyor**.
   Ve mutlak kural: **hiçbir Lighthouse çıktısı A-08 kanıtı değildir** — defter bir insanın
   NVDA/VoiceOver ile **duyduğunu** kaydeder, hiçbir DOM tarayıcısı (axe dahil) oraya
   yazamaz. A-08 hâlâ **yapılmadı**, defter hâlâ **boş**, dört çıkış kriteri de ☐.
2. **Performans ayrımı iki belgeye de yazıldı.** `loadgen.py` **sunucuyu** ölçer (uç-nokta
   p95, kontrol-normalize, gecelik); Lighthouse **tarayıcıyı** (FCP/LCP/TBT/CLS/SI → rota
   başına kategori skoru, PR'da). `performance/README.md` §8 zaten *frontend rendering*'i
   yük sürücüsünün kapsamı **dışında** ilan etmişti; bu kapı o **beyan edilmiş boşluğu**
   dolduruyor — ikinci görüş değil, eksik yarı. Yeşil bir gece bundle regresyonu hakkında,
   yeşil bir Lighthouse skoru ikiye katlanmış bir sorgu hakkında **hiçbir şey söylemez**.

**Kapı UNARMED sevk edildi, sonra donduruldu.** İlk commit `armed: false` + boş `floors`:
hiç koşmamış bir işten eşik uydurmak, tam da yasaklanan uydurmaydı. İlk koşu **ölçtü** ve
`::warning::` ile kapının kapalı olduğunu bağırdı; ikinci commit dondurdu. Dosyanın
**yokluğu** hâlâ sert hatadır — silinmiş bir taban asla *"her skor serbest"*e dönüşmez.

**Armed koşu (`31572385301`) yeşil — ve bir iddiayı çürüttü.** 23 rotanın 22'si tabanı
birebir üretti. Yirmi üçüncüsü üretmedi ve bu slice'ın en öğretici ölçümü oldu:
`panel-management` performance **medyanı 98'de kaldı** ama aralığı `[98-98]` → `[98-100]`
**genişledi**. Yani ölçüm koşusunun *"yayılım 0 puan"*u **o koşunun özelliğiydi, kapının
değil** — ve rapor bunu düzeltilmiş halde taşıyor, güzel olanı değil. Üç sonuç:
**(a)** tabanı tutan şey gürültüsüzlük değil **medyandı** — kapı tek koşuyu dondursaydı
taban 100 olur ve armed koşu ilk denemede hava durumundan düşerdi; **(b)**
`panel-management`'ın tabanı **98'de kalmalı**, `provenance.do_not_tighten` bunu tam da
birinin yükseltmek üzere olduğu anda okunacak yere pinledi; **(c)**
`provenance.repeat_spread_points` artık **iki koşuyu birden** kaydediyor.

**Dondurulan kusurlar isimlendirildi ve AÇIK bırakıldı** — `errors-in-console` (**23/23**
rota), `meta-description` (**23/23**), `robots-txt` (**23/23**), `cumulative-layout-shift`
(1/23, `panel-management`, CLS 0.085). Üçü **uygulama geneli** kusurdur (shell veya origin
kaynaklı), sayfa başına değil. Donmuş bir kusur **görünmez** bir kusurdur; bu yüzden spec
`routes[].deductions`'ı kaydeder (yeşil koşu bile listeyi taşır) **ve** kalem
**[#677](https://github.com/alimirbagirzade/Entropia/issues/677)** olarak açıldı — kabul,
#617/#618 emsalindeki gibi: her düzeltme kendi tabanını sıkılaştırarak gelir.

**Dürüst sınırlar:** Lighthouse performance localhost + desktop preset'te **doygun** —
taban 100 mevcut **en katı** ratchet'tir (*"hiç kötüleşemez"*), ama **gerçek bir kullanıcı
makinesinde hızlı olduğunun kanıtı DEĞİLDİR** ve hiç kimse onu öyle alıntılayamaz; uyarı
tabanın kendi `provenance.sensitivity_boundary`'sine yazıldı ki sayıyla birlikte seyahat
etsin · SSE akışı yüzünden Lighthouse'un network-quiet koşulu hiç ateşlenemez, trace **20
sn**'de kesilir (FCP/LCP çok öncesinde düşer; sonrası ölçülmez) · ham metrikler
**raporlanır, kapılmaz** · **P11-1 açık olduğu için bu kapı da *required status check*
değil**, yalnız bir job — kırmızı bir Lighthouse koşusunun üstünden merge etmeyi bugün
mekanik olarak engelleyen bir şey yok.

Ham kanıt: `docs/releases/evidence/2026-08-12/p11_8_lighthouse_ratchet.md`.

**Verdict ve blocker sayısı DEĞİŞMEDİ.** P11-8 blocker değildi; §8 hâlâ **BLOCKED**, açık
blocker sayısı hâlâ **üç** (1, 2, 4). **P11 KAPANMADI** — **P11-1** (branch protection,
**insan kararı**) ve **P11-6b** açık.

---

## 7. Unchanged boundaries

Bu dalga bir **doğrulama** dalgasıdır. Aşağıdaki üç sınır **ölçülerek** doğrulanmıştır:

| Sınır | Doğrulama | Sonuç |
|---|---|---|
| **Migration YOK** | `git diff 1f4b88b origin/main -- backend/alembic` → **boş**; P4: `git diff … \| grep '^\+.*def create_'` → **(none)**; `alembic/versions/*.py` = **43 dosya**, tek head `0043_i08_registry_strategy_fks` (canlı `alembic heads` ile birebir) | **DEĞİŞMEDİ** |
| **`ENGINE_VERSION` değişmedi** | Dört bağımsız yerde aynı: `domain/backtest/manifest.py:126` · `docs/generated/repository_facts.md:26` · `engine_golden_digests.json` `engine_version` · `test_oracle_portfolio_containment_gate.py:194` → hepsi `backtest-engine-v18-gap-adjusted-stop-fill`. Ayrıca golden aggregate digest baseline JSON ile **birebir** eşleşti | **DEĞİŞMEDİ** |
| **OpenAPI değişmedi** (ADIM 29 dalgası; **ADIM 41 bunu bilerek DEĞİŞTİRDİ** — iki operation `200 → 202` oldu ve iki gövde şemaya girdi, path/operation **sayısı** aynı kaldı; §6.7.9) | P1 Gate 2: `openapi_export --check` → **exit 0**, `OpenAPI snapshot is up to date: docs/openapi.json`. Yayımlanmış sözleşme canlı FastAPI uygulamasıyla aynı; `ErrorResponse` zarfı ve `PurgeAcceptedResponse` şemada duruyor. **177 path / 196 operation** — P1 ayrıca `@router.<method>` sayımını ampirik **196** ölçtü | **DEĞİŞMEDİ** |

Ek olarak: `SHARED_ALLOCATION_STATUS` **`future_dev`** (containment KAPALI, §4) ve
`backend/src` / `frontend/src` / `backend/tests` / `frontend/e2e` / `.github` ağaçlarında
`1f4b88b` sonrası **sıfır değişiklik** (§1.1).

---

## 8. Final verdict

> ## **BLOCKED**
>
> V18 Release Candidate `1f4b88b` **sevk edilemez**: **2026-08-12 (ADIM 45) itibarıyla
> geriye TEK kapatılmamış blocker kalmıştır** —
> **(1)** A-08 insan ekran okuyucu kabul denetimi hiç koşulmadı (0/4 çıkış kriteri, 0/46
> rota, 0/20 akış, 0 bulgu kaydı) ve yerine geçecek imzalı sapma **yok**. İzleme issue'su
> #514 **2026-08-12'de bir insan tarafından yeniden AÇILDI** (`state=OPEN`,
> `stateReason=REOPENED`, etiket `human-only`) — bu, kapalı-issue ↔ boş-defter
> ayrışmasını **(B) yoluyla** çözer, ama **denetimi koşmaz**; iş hâlâ açıktır.
> **~~(2) kabul akışları~~ — 2026-08-12 / ADIM 45'te KAPANDI** (§6.2): `flows` artık
> `e2e.yml::acceptance-flows` olarak **bir CI kapısıdır** ve gerçekten koşmuştur
> (job **94097720164**, **67 passed / 0 failed / 1 skipped**, `duration_seconds=137`,
> tarayıcı katmanı **5 passed**). Tek imzalı sapma **D-10**'dur ve kapsamı **yalnız WCAG
> 1.4.3**'tür — kalan blocker'ı kapsamaz, dolayısıyla "READY WITH SIGNED DEVIATIONS"
> **açık değildir**.
>
> **Blocker 2'nin kapanması bir sevk kararı DEĞİLDİR** ve iki şeyi kapatmaz: **P11-1
> branch protection** (required status check olmadan kırmızı bir check merge'i fiilen
> durduramaz — depo ayarı + insan kararı) ve elbette **A-08**. Verdict **BLOCKED**.
>
> **(1) hakkında, ADIM 44'ün yaptığı ve YAPMADIĞI:** denetim **koşulabilir hâle geldi**
> (yığın güncel main'de yeniden doğrulandı, precheck sayıları tazelendi, denetçi
> runbook'u yazıldı). Bu blocker'ı **kapatmaz** — dört çıkış kriteri de hâlâ ☐, defterin
> §1/§2/§3'ü hâlâ boş, #514 hâlâ kanıtsız kapalı. Hazırlık denetim değildir.
>
> **Eski blocker (4) — react-router `GHSA-qwww-vcr4-c8h2` — 2026-08-12'de (ADIM 44)
> KAPANDI** (§6.4), ve **imzayla değil, kaldırmayla**: advisory 2026-08-07T18:16:54Z'de
> upstream'de yeniden kapsamlandırıldı (`first_patched` 7.x hattı için **7.18.2**),
> kurulu ağaç zaten 7.18.2 — `npm audit` artık **0 vulnerability** raporluyor. Sevk
> edilen imzasız bir istisna kalmadı; ayrıca `FROZEN_ADVISORIES` literal'i **silindi**,
> böylece imzasız bir npm freeze yazılabilecek ikinci bir ev de yok.
>
> **Eski blocker (3) — Alertmanager — 2026-08-10'da (ADIM 31) KAPANDI** (§6.3): bildirim yolu
> sevk edildi ve **fail-closed**'dur (hedef yoksa Alertmanager **exit 78**, başlamaz),
> provenance kapısı eklendi (yürürlükteki config'in sha256'sı çalışma ağacınınkiyle özdeş),
> ve ateşleyen gerçek bir `EntropiaApiDown` **bir alıcıya `entropia-page` / `severity=page`
> olarak ulaştı** — sentetik seri kullanılmadan. Numaralandırma **bilerek korunmuştur**:
> kapananlar (3) ve (4) olarak anılmaya devam eder, kalanlar (1) ve (2) olarak, çünkü
> yeniden numaralandırmak bu belgeye atıf yapan kayıtları geçmişten koparırdı — bir
> blocker'ın numarası kapandıktan sonra da kimliğidir. **Kapanmayan artık:** kurallar gerçek
> production serilerine karşı hâlâ değerlendirilmedi (§6.3.3) — bu bir blocker olarak
> sayılmıyor çünkü repo içinde kapatılabilir değil, ama **imzalı bir sapma da değildir**.

### Verdict'i **düşürmeyen** ölçümler (kayıt için)

Blocker'lar, koşan kapıların kalitesizliğinden gelmiyor. Koşabilen her kapı geçti:
backend **3966 passed / 0 failed**, coverage **%93,52** (kapı 90) · frontend **721 passed /
70 dosya**, lines **%84.92** (kapı 83) · üç repository-truth kapısı **exit 0** · migration
zinciri 43/43 + kolon parity `problems: 0` · determinizm **46/46 digest özdeş**, 4 süreç ×
3 hash-seed rejimi · containment **44 passed** + gate testi yeşil · worker delivery **49
passed** · no-lookahead **75 passed** · güvenlik kapılarının 10'undan 9'u yeşil, server-side
authz **28 + 19 passed** · load smoke **17/17, err=0** · promtool **11 kural, exit 0** ·
visual **8/8** · axe **45/45 tavan, critical 0**.

**Ayrım tam olarak şudur:** bu dalganın tekrar tekrar yakaladığı hata *kapının ölçtüğü şeyi,
ölçmediği şey sanmaktır*. Yeşil bir `Alert rules — promtool` rozeti alarm sisteminin
çalıştığını göstermez; yeşil bir axe ratchet'i ekran okuyucu kabulünü göstermez; yeşil bir
`acceptance.sh` kabul akışlarını göstermez. Verdict, **ölçülmeyenden** geliyor.

### BLOCKED'ı kaldırmak için gereken insan kararları

| # | Blocker | İnsan kararı |
|---|---|---|
| 1 | `A-08-HUMAN-GATE-UNMET` | (A) denetimi koştur — **önce #514'ü yeniden aç** — iki SR kombinasyonu, 23 rota + 10 akış, dört kriter ☑; **veya** (B) D-10 biçiminde imzalı kalıcı sapma. **ADIM 44 (A)'nın önündeki hazırlık engellerini kaldırdı** (yığın doğrulandı, precheck sayıları tazelendi, `docs/implementation/a11y_screen_reader_audit_runbook.md` yazıldı) — geriye kalan **randevu ve insan saati**, ki ikisi de repo dışıdır |
| 2 | Kabul akışları | ~~Harness'a (a)–(e) kapsamını **yaz** … üç auth modu + health + smoke + `worker-restart-smoke.sh` koştur~~ → **2026-08-10'da yapıldı** (§6.2 / §6.2.1). ~~Kalan insan kararı: **`flows`'u bir CI kapısına bağla** (CI'da 12 konteynerlik ikinci yığın + süre maliyeti kabul edilecek mi?) ve §6.2'deki iki SKIP'i kapat~~ → **2026-08-12 / ADIM 45'te KAPANDI**: kapı `e2e.yml::acceptance-flows` olarak bağlandı ve koştu (**67/0/1**, `duration_seconds=137`); maliyet ölçüldü ve **kabul edildi** (kardeş job → workflow wall-clock'una ~0); SKIP (ii) kapandı, SKIP (i) **yapısal** gerekçeyle kayda geçti. **BLOCKER 2 KAPANDI.** Kalan insan kararı **bu satırda değil, P11-1'de**: required status check olmadan bu kapı merge'i durduramaz |
| ~~3~~ | ~~Alertmanager~~ | ~~(A) receiver + routing + silence + on-call + Prometheus config provenance kapısı; **veya** (B) imzalı kalıcı sapma~~ → **2026-08-10'da (A) SEVK EDİLDİ, blocker KAPANDI** (§6.3). Kalan insan kararları blocker DEĞİL, §6.7'ye kaydedildi: **P10-B3** delivery proof'u bir CI kapısına bağlamak (maliyet kararı) · **P10-B5** on-call rotasyonu / escalation / ack (repo dışı) |
| ~~4~~ | ~~react-router freeze~~ | ~~Kaydı `.github/security-allowlist.json` disiplinine taşı (**zorunlu `owner` + `expires`**)~~ → **2026-08-12'de (ADIM 44) KAPANDI, ama taşınarak değil DÜŞÜRÜLEREK** (§6.4): imza sahibi verilmişti, kayıt yine de yazılmadı — advisory upstream'de yeniden kapsamlandırıldı ve kurulu ağaç zaten yamalıydı. **Kalan insan kararı YOK** |

Ayrıca **izleme hijyeni**: #558 / #559 / #617 / #618, kodun hâlâ açık olduğu ölçülmüşken
COMPLETED kapalıdır (§6.6). Yeniden açmak insan işidir.

---

## 9. Kanıt dizini

### 9.0-e 2026-08-12 (ADIM 44) — blocker 4 kapanışı + blocker 1 hazırlığı

Tüm ham çıktılar: **`docs/releases/evidence/2026-08-12/`**

| Adım | Belge / dosya | Verdict |
|---|---|---|
| P9-B2 | `P9B2_react_router_freeze_dropped.md` | **BLOCKER (4) KAPANDI** — imzayla değil, **kaldırmayla**; imza verilmişti, kayıt yazılmadı |
| — | `p9b2_advisory_ghsa_qwww_vcr4_c8h2.json` | ham advisory: `updated_at 2026-08-07T18:16:54Z`, `first_patched` 7.x hattı için **7.18.2** |
| — | `p9b2_gate_runs.txt` | iki kapı da **exit 0**; `npm audit` **`found 0 vulnerabilities`**; kurulu ağaç 7.18.2; `frontend/src`'de RSC API'si **yok** |
| — | `p9b2_gate_negative_proofs.txt` | **5 × exit 1** (owner yok · süresi geçmiş · bildirilmemiş scope · kayıtsız gerçek advisory · yanlış paket) + **1 × exit 0** (>90 gün = WARN, duvar değil) |
| A-08 | `A08_audit_readiness.md` | **BLOCKER (1) AÇIK KALIR** — denetim koşulabilir hâle geldi, koşulmadı; çıkış kriterleri **0/4** |
| — | `a08_audit_stack_validation.txt` | güncel main'de `scripts/a11y-audit-stack.sh up` → **9 passed / 0 failed**; onarım gerekmedi |
| — | `a08_precheck_results_run5.json` | yakınsamış koşu: 23 rota, **0 blocking**, **90 advisory**, `screen_reader_verified: false` |

### 9.0-c 2026-08-10 (ADIM 34) — §6.7 P4-1 + P4-2 dalgası

Tüm ham çıktılar: **`docs/releases/evidence/2026-08-10/`**

| Adım | Belge / dosya | Verdict |
|---|---|---|
| P4-1/P4-2 | `P4_schema_parity.md` | **İKİSİ DE KAPANDI** (index ekseni 40 → **0**; iki kurulum yolu **bit-özdeş**; kapı CI'ya bağlı) |
| — | `p4_alembic_check_before.txt` | `alembic check` **exit 255**, 39 removed / 39 added / 1 changed index + 1 removed unique constraint |
| — | `p4_install_path_parity_before.txt` | alembic ↔ `create_all`: **DIVERGENT**, 361 vs 360, 40 only-alembic / 39 only-create_all / 1 differing |
| — | `p4_alembic_check_after.txt` | index ekseni **0**; **exit hâlâ 255** — 60 `modify_default` (P4-3, kapsam dışı) |
| — | `p4_parity_gate_green.txt` | `scripts/schema_parity_gate.py` **exit 0** — parity 361/361, index ekseni 0, drift 0 |
| — | `p4_parity_gate_negative.txt` | **exit 1** — P4-2 sapması geri konulunca kapı gerçekten kırmızıya dönüyor |

### 9.0-b 2026-08-10 (ADIM 31) — blocker 3 dalgası

Tüm ham çıktılar: **`docs/releases/evidence/2026-08-10/`**

| Adım | Belge / dosya | Verdict |
|---|---|---|
| P10-B | `P10B_alert_notification_path.md` | **BLOCKER KAPANDI** (bildirim yolu sevk edildi, fail-closed, uçtan uca ölçüldü) |
| — | `p10b_preexisting_state.txt` | §6.3'ün beş iddiası `origin/main`'de **yeniden ölçüldü**, beşi de doğru |
| — | `p10b_promtool_gate.txt` | `scripts/alert-rules-gate.sh` yeni `alerting:` bloğuyla **exit 0**, 11 kural |
| — | `p10b_amtool_gate.txt` | `scripts/alert-notification-gate.sh` (YENİ) **exit 0** — `check-config` + üç `routes test` |
| — | `p10b_notification_proof.txt` | `scripts/alert-notification-proof.sh` (YENİ) **exit 0** — fail-closed exit 78 · sha256 provenance · gerçek `EntropiaApiDown` alıcıya ulaştı |
| — | `p10b_contract_tests.txt` | `test_alert_notification_contract.py` (YENİ) **21 passed** + `test_alert_rules_contract.py` regresyonsuz |
| — | `p10b_backend_suite.txt` | Tam backend suite — regresyon kontrolü |

### 9.0 2026-08-10 (ADIM 30) — blocker 2 dalgası

Tüm ham çıktılar: **`docs/releases/evidence/2026-08-10/`**

| Adım | Belge / dosya | Verdict |
|---|---|---|
| P6-B | `P6B_acceptance_flows_harness.md` | **KISMEN KAPANDI** (harness yazıldı, beş akış koştu; CI kapısı değil) |
| — | `p6b_flows_run.txt` | `flows` koşusu: 60 passed / 0 failed / 2 skipped + tarayıcı 5 passed |
| — | `p6b_docker_remeasure.txt` | "docker ps → 124" **yeniden üretilemedi** |
| — | `p6b_ci_browser_layer.txt` | aday SHA'da E2E run 31364211010 **success**, (a)/(b)/(e-kısmi) yeşil |
| — | `p6b_term_scan.txt` | terim taraması BEFORE 0 → AFTER 17/43/19/32/17/9 |
| P5-B | `p5b_three_auth_modes.txt` | üç auth modu **PASS** (27/0, 15/0, 9/0) |
| P5-B | `p5b_acceptance_gate.txt` · `p5b_smoke.txt` · `p5b_worker_restart.txt` | health / smoke / restart **exit 0** |

### 9.1 2026-08-07 (ADIM 29) — P1–P13 dalgası

Tüm ham çıktılar: **`docs/releases/evidence/2026-08-07/`**

| Adım | Belge | Verdict | Ham dosyalar |
|---|---|---|---|
| P1 | `P1_repository_truth.md` | PASS | `gate1_repository_facts.txt` · `gate2_openapi_export.txt` · `gate3_acceptance_semantic_scan.txt` |
| P2 | `P2_backend.md` | PASS | (log'lar oturum scratchpad'inde, kalıcı değil — belge sayıları taşır) |
| P3 | `P3_frontend.md` | PASS | — |
| P4 | `P4_migrations.md` | PASS | — |
| P5 | `P5_docker_auth.md` | PARTIAL (1/4) | `p5_logs/01_build_backend.txt` · `02_build_frontend.txt` · `03_compose_up_session.txt` |
| P6 | `P6_acceptance_flows.md` | **BLOCKED** | `p6_f1_backup.txt` · `p6_f2_restore.txt` · `p6_f3_backup_verify.txt` · `p6_f4_dr_acceptance.txt` · `p6_f4b_dr_acceptance_rerun.txt` · `p6_concurrency_adjudication.txt` · `p6_acceptance_sh_attempt.txt` · `p6_e2e_acceptance_sh_attempt.txt` |
| P7 | `P7_engine_oracles.md` | PASS | `p7_oracle_runs.txt` · `p7_determinism_probe.txt` · `p7_containment.txt` · `p7_pinned_labels.txt` |
| P8 | `P8_worker_research.md` | PARTIAL (2/3) | `p8_worker_delivery.txt` · `p8_research_lookahead.txt` · `p8_oracle_xfail.txt` · `p8_docker_probe.txt` |
| P9 | `P9_security.md` | **BLOCKED** | `p9_pip_audit.txt` · `p9_npm_audit_gate.txt` · `p9_gitleaks.txt` · `p9_jsyaml_fix_proof.txt` · `p9_authz_contract.txt` · `p9_authz_service.txt` · `p9_login_gate_isolated.txt` · `p9_container_gates.txt` |
| P9-B1 | `P9B1_jsyaml_remediation.md` | düzeltme (merged #637) | `p9b1_verification.txt` |
| P10 | `P10_perf_observability.md` | PARTIAL | `p10_query_budgets_and_alert_contract.txt` · `p10_loadgen_smoke.txt` · `p10_loadgen_smoke.json` · `p10_loadgen_unit.txt` · `p10_alert_rules_gate.txt` · `p10_n_plus_one_probe.txt` · `p10_pagination_bounds.txt` |
| P11 | `P11_visual_a11y.md` | PASS (uyum beyanı değil) | `p11_visual_gate.txt` · `p11_axe_ratchet.txt` · `p11_axe_summary.txt` · `p11_axe_baseline_measured.json` |
| P12 | `P12_a08_gate.md` | **BLOCKED** | — |
| P13 | **bu belge** | **BLOCKED** (toplam) | — |

---

## 10. Bu adımda (P13) değişen ve değişmeyenler

> **ADIM 31 eki (2026-08-10).** O dalgada bu belgenin **başlık verdict özeti**, **§6.3**
> (tamamen yeniden yazıldı), **§6.7** (üç yeni kalem: P10-B3/B4/B5), **§8** (verdict metni +
> insan-kararı tablosunun 3. satırı) ve **§9.0-b** güncellendi. **§6.1 / §6.2 / §6.4 / §6.5 /
> §6.6 ve P1–P13 tablolarının tamamı el değmeden bırakıldı** — blocker 1, 2 ve 4 o slice'ın
> kapsamı DIŞINDAYDI. Kod tarafında değişen: `ops/alertmanager/*` (YENİ),
> `ops/prometheus/entrypoint.sh` (YENİ), `ops/prometheus/prometheus.yml` (`alerting:` bloğu),
> `docker-compose.yml` (iki servis, `observability` profili — düz `docker compose up`
> **etkilenmez**), `.github/workflows/ci.yml` (`alerts` job'ına bir adım + yeniden adlandırma),
> `scripts/alert-notification-{gate,proof}.sh` (YENİ), `backend/tests/contract/test_alert_notification_contract.py`
> (YENİ), `.env.example`, `docs/runbooks/alert-notification.md` (YENİ) + `METRIC_ALERT_MATRIX.md`.
> **`backend/src` ve `frontend/` düzenlenmedi**; migration, lockfile, **imza**, tag, release,
> issue açma/kapama **yok**.

> **ADIM 30 eki (2026-08-10).** O dalgada bu belgenin §3/P5, §3/P6, §6.2, §8 ve §9
> bölümleri güncellendi ve `docs/releases/evidence/2026-08-10/` eklendi. Kod tarafında
> **yalnız harness** değişti: `scripts/lib/acceptance-flows.sh` (yeni),
> `scripts/e2e-acceptance.sh` (`flows` alt-komutu + `API_CORS_ORIGINS` + SKIP sayacı),
> `frontend/e2e/specs/05-mainboard-ready-check-run.spec.ts` (sabit-kodlu `:8000` yedeği
> parametreleştirildi; `E2E_API_BASE_URL` yokken **aynı literal** → CI davranışı birebir
> korunur). **`backend/src` ve `frontend/src` düzenlenmedi**; migration, lockfile, imza,
> tag, release, issue açma/kapama **yok**. Aşağısı P13 dalgasının kaydıdır.

**Değişen:** yalnız bu belge eklendi.

**Değişmeyen — bilerek:** hiçbir kaynak / test / migration / CI / lockfile dosyası ·
hiçbir GitHub issue açılmadı veya kapatılmadı · **hiçbir imza yazılmadı** (imzalayan
verilmedi; agent kendi inisiyatifiyle imza üretemez) · `docs/audit/a11y_screen_reader_audit_results.md`
düzenlenmedi · hiçbir tag atılmadı, hiçbir release oluşturulmadı, hiçbir PR merge edilmedi.

**PO onayı bekleniyor.**
