<!-- doc-status: historical -->
> **HISTORICAL RECORD — bu belge GÜNCEL GERÇEK DEĞİLDİR.** Yazıldığı andaki durumu
> kaydeder; SHA'lar, sayılar, alembic head'i ve "next" maddeleri bayat olabilir.
> Güncel otorite: `CLAUDE.md` §Current position + `docs/generated/repository_facts.md`
> (üretilmiş, CI'da `--check` ile kapılı).

# ADIM 33 LANDED — RC §6.7 / P9-F1: frontend build reproducibility

**Base:** `979094e` (ADIM 32 / PR #655) · **Branch:** `security/rc-p9f1-npm-ci` ·
**Migration yok**, `ENGINE_VERSION` sabit, alembic head `0043_i08_registry_strategy_fks`.

---

## Nerede duruyoruz

RC raporu §6.7'nin **P9-F1** kalemi kapandı. **P9-F2 (ADIM 32) ile birlikte §6.7'nin iki
"P9" kalemi de artık üstü çizili.** Blocker sayısı **DEĞİŞMEDİ (üç: 1, 2, 4)**; §8 verdict'i
**BLOCKED**. Bu slice bir blocker'a dokunmadı ve dokunduğunu iddia etmiyor.

**Aynı §6.7 tablosundaki P11-1 (branch protection) ELE ALINMADI** — `gh api …/protection`
→ 404 hâlâ geçerli. Repo ayarıdır, **insan kararıdır**, agent kapatamaz. P11-1 açık
durdukça bu slice'ın (ve ADIM 32'nin) kapıları **required status check değil, job
kapısıdır**.

---

## Bu slice ne bıraktı — reuse anchor'ları (tam adlarıyla)

| Anchor | Neden önemli |
|---|---|
| `frontend/.dockerignore` | **YENİ.** `COPY . .` her şeyi alır; yeni bir build girdisi eklerken **önce buraya bak**. Bu dosya olmadan `frontend/Dockerfile`'daki `npm ci` **uygulanabilir değildir** — host `node_modules`'ü image'inkini ezer. |
| `frontend/Dockerfile` → `COPY package.json package-lock.json ./` | **Glob EKLEME.** Fail-closed davranış (lockfile yoksa build durur) tam olarak glob'un yokluğundan geliyor. |
| `frontend/Dockerfile` → `RUN npm ci` | **`npm install`'a geri dönme.** Ayrışmayı kırar, sessizce uzlaştırmaz. |
| `frontend/Dockerfile` → `__API_ORIGIN__` sed bloğu | ADIM 32'den **değişmeden** duruyor; CSP `connect-src`'ini build zamanında türetir. |
| `scripts/spa-security-headers-gate.sh::EXPECTED_HEADERS` | ADIM 32'nin kapısı; bu dalgada **yeniden koşuldu ve geçti** (10/10). Yeni header eklerken yalnız bu listeye satır ekle. |

**Ölçüm deseni (bir sonraki "kapı" işinde tekrarla):** her negatif durumu **kontrolüyle
birlikte** koş. "Yeni hâl kırılıyor" tek başına zayıf bir iddiadır; yanına "eski hâl aynı
girdide sessizce geçiyordu" konduğunda düzeltmenin ısırdığı **kanıtlanmış** olur. Ham
kanıt: `docs/releases/evidence/2026-08-10/p9f1_negative_cases.txt`.

---

## Dürüst sınırlar (bir sonraki oturum bunları biliyor olmalı)

- **`npm audit` 3 high-severity bulgusu ELE ALINMADI.** Bu slice lockfile'a *sadakati*
  zorlar, lockfile'ın *içeriğini* denetlemez. Bağımlılık yükseltmek ayrı bir karardır.
- **Frontend/backend birim suite'leri koşulmadı** — `src/` altında tek satır değişmedi.
  Gerekçedir, ölçüm değil; **otorite CI'dır**.
- **ADIM 32'nin başlığı** `PROJECT_HISTORY.md` ve `STAGE2_HANDOFF.md`'de hâlâ
  `(PR pending)` diyor, oysa o dalga **#655** olarak indi. `.claude/hooks/docs-history-guard.py`
  bir `## ` başlığının yeniden yazılmasını **kayıt silme** sayıp commit'i reddedeceği için
  **bilerek düzeltilmedi**. Düzeltmek insan kararıdır.
- **Üç blocker açık** (A-08 · kabul akışları CI kapısı değil · react-router freeze imzasız).
  Bu slice hiçbirine dokunmadı.

---

## Paste-ready resume prompt

```
ENTROPIA V18 — ADIM 34

[[ Kendi ROL / OTURUM BAŞLANGICI / CANONICAL KAYNAK / TAVİZ VERİLEMEZ /
   PR DİSİPLİNİ bloklarınızı buraya aynen yapıştırın ]]

BASE: origin/main (DOĞRULA — ADIM 33 / P9-F1 merged olmalı; `git fetch` + `gh pr list`)

OTURUM BAŞLANGICI
  1. git fetch; git log --oneline origin/main -6; gh pr list --state all
     → ADIM 33 (npm ci + .dockerignore) gerçekten indi mi? Handoff BAYATTIR, doğrula.
  2. Oku: docs/ADIM33_LANDED_KICKOFF.md (bu belge) → docs/STAGE2_HANDOFF.md §Next
     → docs/releases/Entropia_V18_RC_Readiness_2026-08-07.md §6.7 + §8.
  3. Kod tarafına geçmeden ilgili docs/CODEMAPS/ haritasını oku, sonra
     codebase-memory-mcp ile sembolleri bul. Kör grep + tam dosya okuma YOK.

NEXT — DEĞİŞMEDİ: PR B — `ItemParticipant` adaptörü + `jobs/backtest_engine.py:298`
call site. Tasarım işaretleri: docs/ADIM16_STEPPER_LANDED_KICKOFF.md, docs/ADIM26_KICKOFF.md.
`SHARED_ALLOCATION_STATUS = future_dev` (containment KAPALI) — ADIM 20 matrisindeki
A1/A3/A5 dışında hiçbir satır bu boşluk kapanmadan kapanamaz.

TAVİZ VERİLEMEZ
  · Empirically verify her code-review CRITICAL/HIGH bulgusunu düzeltmeden ÖNCE.
  · Tembel merdiven (ponytail-entropia): gerekiyor mu → codebase'de var mı → stdlib →
    kurulu bağımlılık → tek satır. Override listesi pazarlıksız (coverage kapısı,
    katman deseni, adjudicated alanlar).
  · Backend local verify: cd backend && uv run ruff check . && uv run ruff format --check .
    && uv run mypy src && uv run pytest -q   (alt küme koşarken --no-cov; `| tail` YOK;
    TEST_DATABASE_URL ile worktree'ye özel izole DB, sürücü postgresql+asyncpg://)
  · Yeni create_* → L1 FK insert-order proof + alembic up/down/up + migration↔model parity.
  · Yeşile zorlama YOK. "READY" YAZMA — verdict BLOCKED, blocker sayısı üç.

KAPSAM DIŞI (dokunma)
  · Üç blocker (A-08 · kabul akışları CI kapısı · react-router freeze) — insan kararı.
  · P11-1 branch protection — repo ayarı, insan kararı.
  · npm audit 3 high-severity — ayrı bir bağımlılık kararı.

KAPANIŞ: CLAUDE.md §Session CLOSING ritüelinin 6 maddesi + docs regresyon kontrolü
  (git diff origin/main -- docs/ | grep '^-## ' → BOŞ) +
  cd backend && uv run python ../scripts/generate_repository_facts.py --root .. --check
```
