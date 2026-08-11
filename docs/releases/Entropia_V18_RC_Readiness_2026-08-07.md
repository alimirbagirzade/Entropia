<!-- doc-status: current -->
# Entropia V18 — Release Candidate Readiness Report

**Candidate SHA:** `1f4b88b7370dd73929d068175885c05f65fd3b9a` (`1f4b88b`)
**Candidate commit:** `docs(a08): reconcile the record with #514 being closed unaudited (#631)` · 2026-08-07 14:36:32 +0300
**Rapor tarihi:** 2026-08-07 · **Dalga:** ADIM 29 / P1–P13 (V18 RC verification)
**Kaynak:** `docs/releases/evidence/2026-08-07/` — 13 kanıt belgesi + 34 ham çıktı dosyası

> **FINAL VERDICT: BLOCKED** — **ÜÇ** bağımsız eksende kapatılmamış blocker var
> (A-08 insan kabul denetimi koşulmadı ve imzalı sapması yok · P5/P6'nın kabul akışları
> koştu ama `flows` bir CI kapısı değil · react-router HIGH advisory'si imzasız
> dondurulmuş); imzalı sapma D-10 **yalnız** WCAG 1.4.3 eksenini kapsar ve bu
> blocker'ların hiçbirini kapatmaz. Gerekçe: §7.
>
> **2026-08-10 (ADIM 31) — blocker sayısı 4 → 3.** Eski blocker **(3) Alertmanager yok**
> **KAPANDI**: bildirim yolu sevk edildi, fail-closed, ve ateşleyen gerçek bir alarmın bir
> alıcıya ulaştığı uçtan uca ölçüldü (§6.3). Verdict **BLOCKED kalır** — 1, 2 ve 4 açıktır.

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
bulgu **P1-B2**. İkisi de **düzeltilmedi**.

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
| **`readiness_check.market_data_leg`** | 2 → **12** | **1** | **#617** | **CLOSED / COMPLETED** |
| **`dependency_pins.ensure_pinned_resolvers_active`** | 2 → **22** | **2** | **#618** | **CLOSED / COMPLETED** |

Ampirik doğrulama (çıkarım değil): `-s` koşusunda `came in under budget` satırı **0 kez**
geçti → ölçülen sayılar bütçeye **eşit**; ve kaynak hâlâ döngü içi await taşıyor
(`commands/readiness_check.py:401-406`, `queries/dependency_pins.py:114-115`).

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
| 45 düğümlük donmuş küme, iki renk çifti | K-2..K-6 (skip link, `contentinfo`, `<h1>`, başlık hiyerarşisi, odak göstergesi) |
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

### 6.2 Uçtan uca kabul akışları — **KISMEN KAPANDI**, blocker hâlâ **AÇIK** (P5 + P6)

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

> **Blocker neden hâlâ AÇIK.** Kapsam boşluğu kapandı ve beş akış koştu, ama **`flows` bir
> CI kapısı değildir** — yerel bir komuttur, hiçbir workflow onu koşmaz, dolayısıyla bir
> regresyon sessizce geri gelebilir. Kapıya bağlamak ayrı bir karardır (CI'da 12 konteynerlik
> ikinci bir yığın + koşu süresi) ve bu slice'ta **yapılmadı**. Yukarıdaki iki SKIP de açık
> iştir. Bu yüzden kayıt "kapandı" değil, **"kısmen kapandı"**dır.

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

### 6.4 react-router `GHSA-qwww-vcr4-c8h2` — imzasız freeze, **BLOCKER** (P9-B2)

| Boyut | Bulgu |
|---|---|
| Sevk ediliyor mu? | **EVET** — lockfile `react-router` 7.18.2 `dev=false`; paket bundle'a **girer** |
| Risk argümanı | **maddeten geçerli** — uygulama `BrowserRouter` kullanıyor (`main.tsx:22`); `frontend/src` içinde hiçbir RSC API'si yok |
| Lockfile-only çare | **YOK** — `npm audit fix --force` yalnızca `react-router-dom@7.11.0`'a **downgrade** öneriyor (`isSemVerMajor: true`) |
| **İmza** | ❌ **YOK** — `owner` yok, `expires` yok, ISO tarih yok |

Repo bu asimetriyi **kendi yazmış** (`security-allowlist-gate.mjs` başlığı): *"their freezes
expire only when a human happens to notice. Here the calendar notices."*
`.github/security-allowlist.json` **zorunlu `owner`** ("the human accountable for revisiting
it, **not a team alias**") ve `expires` istiyor (`MAX_EXCEPTION_DAYS = 90`);
`FROZEN_ADVISORIES` istemiyor. **Commit author'ı bir imza değildir.**

P9-B1 iki bayat olguyu düzeltti (yamalı hat `8.2.1+` → **`8.3.0+`**; pin `7.18.1` →
**`7.18.2`**) ama **freeze'i kapatmadı**. Kaydı allowlist disiplinine taşımak insan işidir —
uydurulmuş bir `owner` kaydın tüm amacını yok ederdi.

> **Karşıt kayıt, adalet için:** P9'un **B1** blocker'ı (js-yaml, gerekçesi doğduğunda
> yanlıştı — yamalı 4.3.1 freeze'den **7 gün önce** yayındaydı) **düzeltildi ve kapandı**
> (PR #637, merged `2026-08-07T17:56:59Z`). P9'un iki blocker'ından biri kapalıdır.

### 6.5 K-2..K-6 — ölçüldü, **düzeltilmedi**, bilerek gate DIŞI

`docs/audit/a11y_screen_reader_audit_results.md:330-334`. Beşi de **"Open — reported, not
gated"** statüsünde; hiçbiri CI'ı kırmaz, hiçbiri imzalı sapmaya bağlanmış değildir.

| # | Bulgu | Kapsam | WCAG | Statü |
|---|---|---|---|---|
| **K-2** | **Skip link yok** — her route'ta ilk tabbable öğe shell'in `Log out` butonu; her sayfa tüm menü çubuğunu tab'layarak başlıyor | **23 / 23 route** | 2.4.1 | Open — reported, not gated |
| **K-3** | **`contentinfo` landmark yok** — shell hiç `<footer>` render etmiyor; checklist A-2 dört landmark bekliyor, üç var | **23 / 23 route** | 1.3.1 / 2.4.1 | Open — reported, not gated |
| **K-4** | **`/user-manual`'da `<h1>` yok** — kendini `<h2 class="page-title">` ile adlandırıyor (`UserManual.tsx:181`); diğer her route `<h1>` kullanıyor | 1 route | 1.3.1 / 2.4.6 | Open — reported, not gated |
| **K-5** | **Başlık hiyerarşisi h2'yi atlıyor** — `h1 → h3` doğrudan (ör. `/backtest/run`: `h1 "RUN & Backtest Results" → h3 "Composition"`); setin **en yüksek erişimli** yapısal gözlemi | **21 / 23 route** | 1.3.1 (A-3) | Open — reported, not gated |
| **K-6** | **Odak göstergesi computed style ile saptanamıyor** — `outline: none; box-shadow: none`; UA varsayılan halkası hâlâ boyanıyor olabilir, computed-style probu onu göremez | probe: 1 element | 2.4.7 / 1.4.11 | Open — **insan gözü gerekiyor** |

**K-5 ve K-6 doğrudan A-08'e bağlıdır:** K-5'in cevabı (rotor başlık gezinmesi gerçekten
yanıltıyor mu) **21 sayfanın outline'ını yeniden kesmeyi önermeden ÖNCE** verilmelidir;
K-6 tam olarak otomasyonun karara bağlayamayacağı sınıftır. A-08 koşulmadığı için ikisi de
**cevapsızdır**.

### 6.6 İzleme kaydı ↔ kod ayrışması — tekrarlayan desen (P8 §4.3, P10 §3.3)

Aynı desen **beş issue'da** ölçüldü: iş açık, izleme COMPLETED kapalı, kayıtlı karar yok.

| # | Tür | closedAt | Ölçülen gerçek durum |
|---|---|---|---|
| **#514** | A-08 human audit | `2026-08-07T03:52:03Z` | defter BOŞ, 0/4 kriter (§6.1) |
| **#558** | product decision (bundle time-policy pin) | `2026-08-07T03:53:57Z` | **strict xfail bugün hâlâ düşüyor**; yorum sayısı 0, etiket hâlâ `product-decision` |
| **#559** | product decision (DST fold/gap) | `2026-08-07T03:53:36Z` | davranış karakterize, **canon hâlâ sessiz** |
| **#617** | N+1 `readiness_check.market_data_leg` | 2026-08-06 08:55 | `per_item=1` **hâlâ canlı**, kaynak döngü içi await taşıyor |
| **#618** | N+1 `dependency_pins` | `2026-08-07 03:53` | `per_item=2` **hâlâ canlı** |

Karşıt kayıt: **#557 meşrudur** — düzeltildi, marker kaldırıldı, test bugün PASS. **#556**
kod tarafı düzeltildi ama `unified_portfolio_oracle_acceptance.md` A17'ye göre **market
yarısı açık**.

**Sonuç:** A17 çıkış kriteri *"tests green **unweakened**"* strict xfail durdukça
**karşılanmamıştır**. Issue yeniden açmak **insan kararıdır**; bu dalgada hiçbir issue
açılmadı/kapatılmadı.

### 6.7 Blocker olmayan ama kapanmamış kalemler

| # | Bulgu | Kaynak |
|---|---|---|
| ~~**P4-1**~~ | ~~`alembic check` **exit 255** (40 gerçek index-adı sapması) ve **hiçbir CI workflow'u onu koşmuyor** → sahipsiz, izlenmeyen~~ → **2026-08-10 (ADIM 34) KAPANDI** — 40 sapmanın 40'ı kapatıldı (index ekseni ölçülen **0**), kapı CI'ya bağlandı ve negatifiyle kanıtlandı. **`alembic check` yine de exit 255**, ayrı bir sınıf yüzünden — ayrıntı ve ham kanıt: **§6.7.3** | P4 |
| ~~**P4-2**~~ | ~~`agent_event.seq`'te alembic yolunda fazladan non-unique index; `create_all` yolunda yok → iki kurulum yolu bu noktada bit-özdeş değil (fonksiyonel etki yok)~~ → **2026-08-10 (ADIM 34) KAPANDI** — iki kurulum yolu index ekseninde **bit-özdeş** (361/361, 0 sapma); fonksiyonel etkisizlik deneysel kanıtlandı. Ayrıntı: **§6.7.3** | P4 |
| **P4-3** | **YENİ (ADIM 34 ölçümü, rapor bunu bildirmemişti).** §6.7'nin *"tip/server-default değişimi = 0"* iddiası **yanlıştı**: aynı `alembic check` koşusu **60 `modify_default`** işlemi de emitliyor (40 tabloda 60 kolon; DB'de server default var, model onu yalnız Python tarafında bildiriyor). P4-2 ile aynı aileden gerçek bir model↔migration ayrışması; **ölçüldü, düzeltilmedi** (modele `server_default` eklemek `create_all` şemasını değiştirir → ayrı karar, ayrı PR). Sayı ADIM 34 kapısında **tavana** bağlandı: büyüyemez | P4 |
| **P10-B2** | ~~9 uçta sayfalama sınırı **şemada yayımlanmıyor**~~ → **2026-08-11 (ADIM 37): YAYIMLAMA KAPANDI, AŞIM DAVRANIŞI AÇIK.** Dokuz ucun dokuzu da artık default + tavan bildiriyor (`x-clamp-default` / `x-clamp-maximum`), kapı + negatif kanıt bağlı, `UNPUBLISHED = 0`. **Kalem KAPANMADI:** aşımın sessiz clamp mi 422 red mi olacağı bir **ürün kararıdır**, canonical **sessizdir** ve bu slice onu **VERMEDİ** → **PO kararı bekliyor**. Raporun *"sessizce 100'e iniyor"* ifadesi de düzeltildi: 5 uçta `meta.limit` etkin değeri **zaten yankılıyordu**, 1 uçta gerçekten sessiz. Ayrıntı, adjudication ve ham kanıt: **§6.7.5** | P10 |
| **P10-B6** | **YENİ (ADIM 37 ölçümü, rapor bunu bildirmemişti).** Dört uç uyguladığı **etkin** sayfa boyutunu yanıtta yankılamıyor: `/agent-tasks`, `/lab/messages`, `/hypotheses` (`next_cursor` var, `limit` yok) ve `/agent-tasks/{task_id}/tool-calls` (**hiçbir sayfalama metadata'sı yok** — ne cursor, ne has_more, ne limit). MTR §8'in `Response meta.pagination` sözleşmesiyle ayrışır; ama sevk edilen `meta: {cursor, has_more, limit}` şekli **zaten** MTR §8'in ad ekseninden ayrı → bu dört uçtan büyük, daha eski bir sapma. **Ölçüldü, düzeltilmedi** (yanıt gövdesi = wire contract; `lib/*.ts` + typed `AgentToolCallListResponse` okuyor → ayrı karar, ayrı PR) | ADIM 37 |
| ~~**P9-F2**~~ | ~~**SPA origin'inde CSP yok** — `frontend/nginx-security-headers.conf` CSP vermiyor; yürütülebilir bundle'ı sunan origin budur. API'de CSP var ve testli; statik origin için **hiçbir test/kapı/belge yok**~~ → **2026-08-10 (ADIM 32) KAPANDI** — politika sevk edildi, canlı yanıtta ölçüldü, CI kapısına bağlandı. Ayrıntı ve ham kanıt: **§6.7.1** | P9 |
| ~~**P9-F1**~~ | ~~`frontend/Dockerfile` **`npm install`** kullanıyor (`npm ci` değil) + `COPY package-lock.json*` glob'u lockfile yokluğunu tolere ediyor → reproducibility riski~~ → **2026-08-10 (ADIM 33) KAPANDI** — `npm ci` + glob'suz `COPY`; fail-closed olduğu **iki negatif durumda, her biri kontrolüyle** ölçüldü, ayrıca `frontend/.dockerignore` eklendi. Ayrıntı ve ham kanıt: **§6.7.2** | P9 |
| **P11-1** | **`main` üzerinde branch protection YOK ve ruleset YOK** (`gh api …/protection` → 404, `…/rulesets` → `[]`) → visual/axe kapıları **job kapısıdır, required status check DEĞİLDİR**; kırmızı E2E ile merge'i mekanik engelleyen bir şey yok | P11 |
| **P11-2** | Visual gate 23 sayfanın **8'ini** kapsıyor; kalan 15'te piksel regresyonu koruması **yok** | P11 |
| ~~**P11-3**~~ | ~~8 `-chromium-darwin.png` baseline commit'li ama **hiçbir job onları assert etmiyor** → sessizce bayatlayabilir~~ → **2026-08-11 KAPANDI.** İddia doğruydu ama *"bayatlayabilir"* fazla nazikti: **zaten bayatlamıştı** — macOS'ta, `e2e.yml`'in seed'inin aynısıyla koşulduğunda **8'in 6'sı düştü** (yükseklik sapmaları **44–539 px**, `maxDiffPixelRatio 0.02`'nin çok dışında). Tüketici ölçüldü: 18 `runs-on:`'un 18'i `ubuntu-latest`, macOS runner **YOK** → **(b) SİL** seçildi; (a)'nın maliyeti (macOS dakikası 10×, üstelik ürün bir Linux konteyneri olarak sevk ediliyor) açıkça değerlendirilip **reddedildi**. Sekizi silindi; geri dönüşü **YENİ** `scripts/visual-baseline-platform-gate.sh` (→ `ci.yml` `frontend` job'ı) kırıyor ve **negatifi kanıtlı**. Ayrıntı ve ham kanıt: **§6.7.6** | P11 |
| ~~**P11-6**~~ | ~~Tab sırası 23 route'un **yalnız 3'ünde** doğrulandı~~ → **2026-08-11 KAPANDI (kapsam ekseninde).** **23/23** yürütüldü, **0 N/A**; rota listesi artık elle yazılmıyor, `screenshotMatrix.ts::TARGET_PAGES`'ten türüyor. Daraltmanın yazılı gerekçesi (*"walking every tabbable element on all 23 routes would double this job's wall clock"*) **ölçülerek çürütüldü**: 23 rota **13.2 s**, `@a11y` job'ının tamamı **1.2 dk** (ADIM 29: 1.0 dk). 0 sapma, 0 blocking, advisory **90** — ADIM 29 ile birebir aynı. **YENİ KALEM → P11-6b:** aynı sonda **Tab'a hiç basmıyor** ve **hiçbir rota onu kıramaz**; ölçüldü, **düzeltilmedi**, sınır artefakta yazıldı. Ayrıntı: **§6.7.6** | P11 |
| **P11-6b** | **YENİ (2026-08-11 ölçümü, rapor bunu bildirmemişti).** `specs/20-a11y-prechecks.spec.ts`'in tab-sırası sondası adının vaat ettiğinden azını ölçüyor: **Tab tuşuna hiç basmıyor** (DOM sırasını `tabindex`'ten türetilen sırayla karşılaştırıyor) ve bulguları yalnız `advisories`'e yazdığı için **hiçbir rota onu kıramaz**. Görebildiği tek şey pozitif-`tabindex` yeniden sıralamasıdır; odak tuzağı / erişilemez kontrol / roving-tabindex **görünmez**. Sınır 3 rotada da vardı — bu dalga onu **getirmedi, ölçtü**; gerçek Tab yürüyüşü yeni bir modelleme kararıdır (radio grupları, `<select>`, roving tabindex) → **ayrı PR**. Şimdilik `precheck-results.json::tab_order_probe` + konsol satırı ile **beyan ediliyor**, ki 3→23 genişlemesi daha güçlü bir iddia gibi okunmasın. Fiziksel Tab yürüyüşü yalnız `specs/14-keyboard-flow.spec.ts`'te, **2 rotada** | P11 |
| **P11-3b** | **YENİ (2026-08-11 ölçümü).** `strategy-standalone` bugün **1135 px** ölçüldü — `-darwin` (1425) ve **`-linux` (900)** baseline'larının **ikisiyle de** uyuşmuyor; sayfa yüksekliği seed'e bağlı liste uzunluğuyla oynuyor. P11-3'ün sonucunu değiştirmez ama **hayatta kalan `-linux` setinin seed hassasiyeti** hakkında açık bir soru bırakır. **Ölçüldü, düzeltilmedi** — bu dalga `-linux` setine dokunmadı | P11 |
| **P11-8** | Lighthouse hâlâ bağlı değil | P11 |
| **P10-7** | Latency **ratio gate** bağlanmamış (`_ratio_gate` yazılı + unit-test'li, devrede değil; aktivasyon için 5 gecelik baseline gerekiyor) | P10 |
| **P1-B1/B2** | `BACKEND_LAYERS.md` başlık sayıları bayat (37→38, 14→16); `CLAUDE.md` dual-token sayısı (16) codemap'e (17) göre bayat | P1 |
| **P8-B1/B2/B3** | `pending_data_job_dispatch` docstring gerekçesi bayat · Create-Package durable admission uçları **200** dönüyor, diğer dokuzu **202** (adjudicate edilmedi) · `JOBS_AND_EVENTS.md` satır numaraları ~24 satır kaymış | P8 |
| ~~**P6-6**~~ | ~~`dropdb` bu host'ta takılıyor → `backup-verify.sh` CI/cron'da sağlam bir yedeği **başarısız** raporlayabilir~~ → **2026-08-10 (ADIM 36) KAPANDI** — yanlış-negatif **yeniden üretildi** (sağlam yedek, `exit 1`), harici çağrılar sınırlandı, **yeni `exit 3` = "doğrulanamadı"** eklendi; "yedek bozuk" (1) ile karışmıyor, "sağlam" (0) ile **asla**. Ayrıntı ve ham kanıt: **§6.7.4** | P6 |
| ~~**P6-ek**~~ | ~~`e2e-acceptance.sh` preflight koruması **takılmış** daemon'a karşı işlemiyor → net `exit 2` yerine sonsuz asılı kalma~~ → **2026-08-10 (ADIM 36) KAPANDI** — asılı kalma **yeniden üretildi** (25s'de hâlâ koşuyordu), preflight sınırlandı; takılı daemon'a karşı **sınırlı sürede `exit 2`** ölçüldü, "daemon yok" teşhisi ayrı mesajda korundu. Ayrıntı ve ham kanıt: **§6.7.4** | P6 |
| **P1-Gate3** | **8 uncovered kriter** + **131 partial kriter** (kapı yeşil sayıyor, ama RC kabul kararında okunmalıdır) — aralarında `AT-04`, `AOS-17`/`TS-17` (spec adı `ACTIVE_RUN_DEPENDENCY` ↔ sevk edilen `OBJECT_IN_ACTIVE_RUN`, **hiçbiri pinli değil**), `TL-20`/`AOS-18` (K-06 tehlikesi) | P1 |
| **P10-B3** | **Bildirim yolunun DELIVERY kanıtı bir CI kapısı DEĞİL** (ADIM 31). Config yarısı kapılı (`scripts/alert-notification-gate.sh` + 21 contract testi); teslimat yarısı yalnız `scripts/alert-notification-proof.sh` ile ölçülür ve o üç konteyner + dakikalarca wall-clock ister. Kapıya bağlamak **insan kararıdır** (maliyet). Regresyon sessizce dönebilir | ADIM 31 |
| **P10-B4** | **Monitörü izleyen yok.** Alertmanager erişilemezse Prometheus yeniden dener ve `prometheus_notifications_errors_total` sayacını artırır — **kendi** `/metrics`'inde, ki onu hiçbir şey scrape etmiyor. Sessizce teslim etmeyi bırakmış bir bildirim yolu, sessiz bir sistemden ayırt edilemez. Döngüsel olmayan bir çözüm ikinci bir Prometheus ister; denenmedi | ADIM 31 |
| **P10-B5** | **On-call rotasyonu / escalation policy / acknowledgement YOK.** Alertmanager'ın ack kavramı yoktur; `repeat_interval` mekanizmanın tamamıdır. Kimin uyandırılacağı `ALERTMANAGER_NOTIFY_URL`'in ucundaki sistemde yaşar — **repo dışı, organizasyonel karar** | ADIM 31 |

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

#### 6.7.5 P10-B2 — sayfalama sınırı YAYIMLANDI, aşım davranışı AÇIK (ADIM 37, 2026-08-11)

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

## 7. Unchanged boundaries

Bu dalga bir **doğrulama** dalgasıdır. Aşağıdaki üç sınır **ölçülerek** doğrulanmıştır:

| Sınır | Doğrulama | Sonuç |
|---|---|---|
| **Migration YOK** | `git diff 1f4b88b origin/main -- backend/alembic` → **boş**; P4: `git diff … \| grep '^\+.*def create_'` → **(none)**; `alembic/versions/*.py` = **43 dosya**, tek head `0043_i08_registry_strategy_fks` (canlı `alembic heads` ile birebir) | **DEĞİŞMEDİ** |
| **`ENGINE_VERSION` değişmedi** | Dört bağımsız yerde aynı: `domain/backtest/manifest.py:126` · `docs/generated/repository_facts.md:26` · `engine_golden_digests.json` `engine_version` · `test_oracle_portfolio_containment_gate.py:194` → hepsi `backtest-engine-v18-gap-adjusted-stop-fill`. Ayrıca golden aggregate digest baseline JSON ile **birebir** eşleşti | **DEĞİŞMEDİ** |
| **OpenAPI değişmedi** | P1 Gate 2: `openapi_export --check` → **exit 0**, `OpenAPI snapshot is up to date: docs/openapi.json`. Yayımlanmış sözleşme canlı FastAPI uygulamasıyla aynı; `ErrorResponse` zarfı ve `PurgeAcceptedResponse` şemada duruyor. **177 path / 196 operation** — P1 ayrıca `@router.<method>` sayımını ampirik **196** ölçtü | **DEĞİŞMEDİ** |

Ek olarak: `SHARED_ALLOCATION_STATUS` **`future_dev`** (containment KAPALI, §4) ve
`backend/src` / `frontend/src` / `backend/tests` / `frontend/e2e` / `.github` ağaçlarında
`1f4b88b` sonrası **sıfır değişiklik** (§1.1).

---

## 8. Final verdict

> ## **BLOCKED**
>
> V18 Release Candidate `1f4b88b` **sevk edilemez**: **üç** kapatılmamış blocker'ı vardır —
> **(1)** A-08 insan ekran okuyucu kabul denetimi hiç koşulmadı (0/4 çıkış kriteri, 0/46
> rota, 0/20 akış, 0 bulgu kaydı) ve yerine geçecek imzalı sapma **yok**, izleme issue'su
> #514 ise **kanıtsız kapatılmış**; **(2)** kabul akışları — **2026-08-10'da kısmen
> kapandı** (§6.2): harness kapsamı yazıldı, beş akış da koştu (**60 passed / 0 failed /
> 2 skipped**, tarayıcı katmanı **5 passed**), ama `flows` hâlâ **bir CI kapısı değildir**,
> yani regresyon sessizce geri gelebilir; **(4)** sevk edilen bir HIGH advisory
> (`GHSA-qwww-vcr4-c8h2`) imzasız bir freeze ile geçiriliyor. Tek imzalı sapma **D-10**'dur
> ve kapsamı **yalnız WCAG 1.4.3**'tür — bu üçün hiçbirini kapsamaz, dolayısıyla
> "READY WITH SIGNED DEVIATIONS" **açık değildir**.
>
> **Eski blocker (3) — Alertmanager — 2026-08-10'da (ADIM 31) KAPANDI** (§6.3): bildirim yolu
> sevk edildi ve **fail-closed**'dur (hedef yoksa Alertmanager **exit 78**, başlamaz),
> provenance kapısı eklendi (yürürlükteki config'in sha256'sı çalışma ağacınınkiyle özdeş),
> ve ateşleyen gerçek bir `EntropiaApiDown` **bir alıcıya `entropia-page` / `severity=page`
> olarak ulaştı** — sentetik seri kullanılmadan. Numaralandırma **bilerek korunmuştur**:
> kalanlar (1), (2), (4) olarak anılmaya devam eder, çünkü yeniden numaralandırmak bu
> belgeye atıf yapan kayıtları geçmişten koparırdı. **Kapanmayan artık:** kurallar gerçek
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
| 1 | `A-08-HUMAN-GATE-UNMET` | (A) denetimi koştur — **önce #514'ü yeniden aç** — iki SR kombinasyonu, 23 rota + 10 akış, dört kriter ☑; **veya** (B) D-10 biçiminde imzalı kalıcı sapma |
| 2 | Kabul akışları | ~~Harness'a (a)–(e) kapsamını **yaz** … üç auth modu + health + smoke + `worker-restart-smoke.sh` koştur~~ → **2026-08-10'da yapıldı** (§6.2 / §6.2.1). Kalan insan kararı: **`flows`'u bir CI kapısına bağla** (CI'da 12 konteynerlik ikinci yığın + süre maliyeti kabul edilecek mi?) ve §6.2'deki iki SKIP'i kapat |
| ~~3~~ | ~~Alertmanager~~ | ~~(A) receiver + routing + silence + on-call + Prometheus config provenance kapısı; **veya** (B) imzalı kalıcı sapma~~ → **2026-08-10'da (A) SEVK EDİLDİ, blocker KAPANDI** (§6.3). Kalan insan kararları blocker DEĞİL, §6.7'ye kaydedildi: **P10-B3** delivery proof'u bir CI kapısına bağlamak (maliyet kararı) · **P10-B5** on-call rotasyonu / escalation / ack (repo dışı) |
| 4 | react-router freeze | Kaydı `.github/security-allowlist.json` disiplinine taşı (**zorunlu `owner` + `expires`**) — **imzalayan verilmediği için agent yazamaz** |

Ayrıca **izleme hijyeni**: #558 / #559 / #617 / #618, kodun hâlâ açık olduğu ölçülmüşken
COMPLETED kapalıdır (§6.6). Yeniden açmak insan işidir.

---

## 9. Kanıt dizini

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
