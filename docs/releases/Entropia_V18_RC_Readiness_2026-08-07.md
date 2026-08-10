<!-- doc-status: current -->
# Entropia V18 — Release Candidate Readiness Report

**Candidate SHA:** `1f4b88b7370dd73929d068175885c05f65fd3b9a` (`1f4b88b`)
**Candidate commit:** `docs(a08): reconcile the record with #514 being closed unaudited (#631)` · 2026-08-07 14:36:32 +0300
**Rapor tarihi:** 2026-08-07 · **Dalga:** ADIM 29 / P1–P13 (V18 RC verification)
**Kaynak:** `docs/releases/evidence/2026-08-07/` — 13 kanıt belgesi + 34 ham çıktı dosyası

> **FINAL VERDICT: BLOCKED** — dört bağımsız eksende kapatılmamış blocker var
> (A-08 insan kabul denetimi koşulmadı ve imzalı sapması yok · P5/P6'nın uçtan uca
> kabul akışları hiç koşmadı · Alertmanager yok, ateşleyen alarm kimseye ulaşmıyor ·
> react-router HIGH advisory'si imzasız dondurulmuş); imzalı sapma D-10 **yalnız**
> WCAG 1.4.3 eksenini kapsar ve bu blocker'ların hiçbirini kapatmaz. Gerekçe: §7.

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
**404**) · reddedilen run Results düzlemini **0 → 0** bıraktı · **dokuz** Admin/owner yüzeyi
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

### 6.3 Alertmanager YOK — **BLOCKER** (P10 §5.3)

```
metrik üretimi  →  scrape config  →  kural değerlendirme  →  ateşleme  →  BİLDİRİM  →  insan
   ✅ 7 aile        ✅ entropia-api    ✅ promtool PASS       ✅ 11/11      ❌ YOK      ❌ ulaşmıyor
```

**Olgu:** repo hiçbir Alertmanager sevk etmiyor — `ops/prometheus/prometheus.yml` içinde
`alerting:` bloğu **bilerek yok**, `docker-compose.yml`'de Prometheus servisi de yok,
repo genelinde receiver / routing ağacı / silence yapılandırması / on-call entegrasyonu
bulunmuyor. `severity: page` ve `severity: ticket` **hiçbir şeyin okumadığı etiketlerdir**.
**Yedi page-seviyeli alarm** — ürünün kullanılamaz olduğunu, Postgres'in erişilemez
olduğunu, async düzlemin hiç kurulmamış olduğunu söyleyen alarmlar — bu boşluğun arkasında.

**"`alerts` job'ı yeşil" bunu KAPATMAZ.** O job'ın kanıtladığı tek şey kuralların *doğru*
olduğudur (PromQL geçerli, metrik adları gerçek, eşikler gerekçeli, sentetik seride
ateşliyorlar). **Doğru bir kuralın kime gittiğini o job hiç sormaz.**

İki ek doğrulanmamış nokta: kurallar **gerçek production serilerine** karşı hiç
değerlendirilmedi, ve **sevk edilen Prometheus'un gerçekten bu dosyadan yapılandığını**
kanıtlayan bir kapı yok.

**Kapanış: (A)** Alertmanager'ı ayağa kaldır (receiver + routing + silence + on-call) +
Prometheus config provenance kapısı; **veya (B)** D-10 biçiminde **imzalı** kalıcı sapma
("V1 üretimi bildirimsiz alarm ile sevk edilir"). **İkisi de insan işi.**

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
| **P4-1** | `alembic check` **exit 255** (40 gerçek index-adı sapması) ve **hiçbir CI workflow'u onu koşmuyor** → sahipsiz, izlenmeyen | P4 |
| **P4-2** | `agent_event.seq`'te alembic yolunda fazladan non-unique index; `create_all` yolunda yok → iki kurulum yolu bu noktada bit-özdeş değil (fonksiyonel etki yok) | P4 |
| **P10-B2** | 9 uçta sayfalama sınırı **şemada yayımlanmıyor** → `limit=100000` reddedilmiyor, sessizce 100'e iniyor | P10 |
| **P9-F2** | **SPA origin'inde CSP yok** — `frontend/nginx-security-headers.conf` CSP vermiyor; yürütülebilir bundle'ı sunan origin budur. API'de CSP var ve testli; statik origin için **hiçbir test/kapı/belge yok** | P9 |
| **P9-F1** | `frontend/Dockerfile` **`npm install`** kullanıyor (`npm ci` değil) + `COPY package-lock.json*` glob'u lockfile yokluğunu tolere ediyor → reproducibility riski | P9 |
| **P11-1** | **`main` üzerinde branch protection YOK ve ruleset YOK** (`gh api …/protection` → 404, `…/rulesets` → `[]`) → visual/axe kapıları **job kapısıdır, required status check DEĞİLDİR**; kırmızı E2E ile merge'i mekanik engelleyen bir şey yok | P11 |
| **P11-2** | Visual gate 23 sayfanın **8'ini** kapsıyor; kalan 15'te piksel regresyonu koruması **yok** | P11 |
| **P11-3** | 8 `-chromium-darwin.png` baseline commit'li ama **hiçbir job onları assert etmiyor** → sessizce bayatlayabilir | P11 |
| **P11-6** | Tab sırası 23 route'un **yalnız 3'ünde** doğrulandı | P11 |
| **P11-8** | Lighthouse hâlâ bağlı değil | P11 |
| **P10-7** | Latency **ratio gate** bağlanmamış (`_ratio_gate` yazılı + unit-test'li, devrede değil; aktivasyon için 5 gecelik baseline gerekiyor) | P10 |
| **P1-B1/B2** | `BACKEND_LAYERS.md` başlık sayıları bayat (37→38, 14→16); `CLAUDE.md` dual-token sayısı (16) codemap'e (17) göre bayat | P1 |
| **P8-B1/B2/B3** | `pending_data_job_dispatch` docstring gerekçesi bayat · Create-Package durable admission uçları **200** dönüyor, diğer dokuzu **202** (adjudicate edilmedi) · `JOBS_AND_EVENTS.md` satır numaraları ~24 satır kaymış | P8 |
| **P6-6** | `dropdb` bu host'ta takılıyor → `backup-verify.sh` CI/cron'da sağlam bir yedeği **başarısız** raporlayabilir | P6 |
| **P6-ek** | `e2e-acceptance.sh` preflight koruması **takılmış** daemon'a karşı işlemiyor → net `exit 2` yerine sonsuz asılı kalma | P6 |
| **P1-Gate3** | **8 uncovered kriter** + **131 partial kriter** (kapı yeşil sayıyor, ama RC kabul kararında okunmalıdır) — aralarında `AT-04`, `AOS-17`/`TS-17` (spec adı `ACTIVE_RUN_DEPENDENCY` ↔ sevk edilen `OBJECT_IN_ACTIVE_RUN`, **hiçbiri pinli değil**), `TL-20`/`AOS-18` (K-06 tehlikesi) | P1 |

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
> V18 Release Candidate `1f4b88b` **sevk edilemez**: dört kapatılmamış blocker'ı vardır —
> **(1)** A-08 insan ekran okuyucu kabul denetimi hiç koşulmadı (0/4 çıkış kriteri, 0/46
> rota, 0/20 akış, 0 bulgu kaydı) ve yerine geçecek imzalı sapma **yok**, izleme issue'su
> #514 ise **kanıtsız kapatılmış**; **(2)** kabul akışları — **2026-08-10'da kısmen
> kapandı** (§6.2): harness kapsamı yazıldı, beş akış da koştu (**60 passed / 0 failed /
> 2 skipped**, tarayıcı katmanı **5 passed**), ama `flows` hâlâ **bir CI kapısı değildir**,
> yani regresyon sessizce geri gelebilir; **(3)** Alertmanager yok, yani doğrulanmış 11 alarm kuralının 7
> page-seviyelisi dahil hiçbiri bir insana ulaşmıyor; **(4)** sevk edilen bir HIGH advisory
> (`GHSA-qwww-vcr4-c8h2`) imzasız bir freeze ile geçiriliyor. Tek imzalı sapma **D-10**'dur
> ve kapsamı **yalnız WCAG 1.4.3**'tür — bu dördün hiçbirini kapsamaz, dolayısıyla
> "READY WITH SIGNED DEVIATIONS" **açık değildir**.

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
| 3 | Alertmanager | (A) receiver + routing + silence + on-call + Prometheus config provenance kapısı; **veya** (B) imzalı kalıcı sapma |
| 4 | react-router freeze | Kaydı `.github/security-allowlist.json` disiplinine taşı (**zorunlu `owner` + `expires`**) — **imzalayan verilmediği için agent yazamaz** |

Ayrıca **izleme hijyeni**: #558 / #559 / #617 / #618, kodun hâlâ açık olduğu ölçülmüşken
COMPLETED kapalıdır (§6.6). Yeniden açmak insan işidir.

---

## 9. Kanıt dizini

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
