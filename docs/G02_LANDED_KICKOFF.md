# Kickoff — G-02 landed (ESP export contract v2) → ADIM 5: Library Request-Validation UI (§G-04)

> Bu doküman **`origin/main` @ `a570934`** (PR #521 merge'ü) itibarıyla yazıldı, 2026-08-03.
> **Otorite sırası:** (1) bu doküman, (2) `docs/audit/current_main_ground_truth_2026-08-03.md`
> §18, (3) `docs/STAGE2_HANDOFF.md` son "landed" + "Next", (4) `docs/spec/08_*` §7/§9.1.
> **Uyarı:** aşağıdaki her olgu repodan ölçüldü ama **stale-by-default** kabul et — oturuma
> `git fetch` + `gh pr list --state all` ile başla.

---

## Neredeyiz

`main` @ `a570934`. Açık PR **yok**. Açık issue: **#514** (A-08 ekran okuyucu denetimi —
**insan işi**, agent kapatamaz). Alembic head **`0043_i08_registry_strategy_fks`** (tek head).
OpenAPI **196 operation** + `PackageExportResponse`. Backend **2974 passed / %92.47**,
frontend **680 passed**.

§18'de kapanan slice'lar: sıra 1 (ADIM 2, ESP lifecycle, #519), sıra 3 (ADIM 4, ESP export
contract v2, #521). **Sıradaki: sıra 2.**

---

## Son slice ne bıraktı (reuse anchor'ları — tam sembol adlarıyla)

ADIM 4 (#521) export/import sözleşmesine dokundu; ADIM 5 **başka bir yüzeydir** (validation-run
dispatch) ama şu kalıplar birebir yeniden kullanılır:

| Anchor | Yol | Neden işine yarar |
|---|---|---|
| `PackageExportResponse` | `backend/src/entropia/apps/api/routes/library.py:71` | **Yeni route gövdesi typed model olarak bildirilir.** `dict[str, Any]` dönüşü sözleşmeyi `docs/openapi.json`'dan gizlerken drift guard'ı yeşil tutar (O-30 tuzağı). `validation-runs` route'u hâlâ `dict` dönüyor — UI'ı bağlarken bunu da typed'a çevirmeyi değerlendir |
| `useExportPackage` | `frontend/src/lib/library.ts:530` civarı | **Mutation hook kalıbı:** `apiRequest<T>` + `crypto.randomUUID()` ile `Idempotency-Key` + `onSuccess` içinde dar `invalidateQueries`. Yeni `useRequestPackageValidation` bunu aynalar |
| `PackageExportBlock` | `frontend/src/pages/Library.tsx:797` civarı | **Sunucu-bayrağı kapılı blok kalıbı:** `if (!pkg.permissions.can_export) return null` — UI asla yetkilendirmez, sunucu yeniden doğrular. `can_request_validation` için birebir aynı |
| `aria-label="Export manifest artifact"` | `frontend/src/pages/Library.tsx` | Test kapsamlama mekanizması (CLAUDE.md'nin sanctioned yolu). `document.querySelector` yerine `screen.findByLabelText` |
| `routesFor()` stub'ı | `frontend/src/test/libraryActions.test.tsx:100` civarı | Library sayfası testlerinin API stub tablosu — yeni endpoint satırı buraya eklenir |
| `domain/package/export_contract.py` | backend | **Saf düzlem ayırma kalıbı:** I/O'suz kurucular ayrı modülde, komut yalnız satırları yükler. `package_lifecycle.py` 900+ satıra çıkmıştı |

---

## ADIM 5 — tasarım işaretleri

**Backend TAM, hiçbir şey yazılmayacak.** Ölçülmüş gerçek:

| Katman | Sembol | Not |
|---|---|---|
| Route | `POST /v1/library/{entity_id}/validation-runs` (201) — `apps/api/routes/library.py::request_package_validation` | Gövde `expected_head_revision_id` (OCC) + `Idempotency-Key` başlığı |
| Komut | `application/commands/package_lifecycle.py::request_package_validation` | `ensure_can_edit` (owner-or-Admin), sonra CP düzlemindeki `start_package_validation_run`'u **sarar** |
| Bayrak | `permissions.can_request_validation` | `domain/package/permissions.py`; list + shared + detail DTO'sunda (`queries/library.py`) |
| Frontend | `frontend/src/lib/library.ts` | Bayrağı **tipliyor**, çağıran hook **YOK** — boşluk tam olarak burada |

**Hata taksonomisi (dokunma, sadece render et):** bayat head → 409
`PACKAGE_REVISION_CONFLICT`; uçan koşu → 409 `VALIDATION_ALREADY_RUNNING`; doğrulanabilir
draft'ı olmayan paket → 422 `VALIDATION_PIPELINE_UNAVAILABLE`. Üçü de `ErrorState` ile
verbatim gösterilir; UI önden kapı koymaz.

**Durum yüzeyi:** komut `job_id` + `validation_run_id` + `status` + `state` döndürür. Job
ilerlemesi için mevcut SSE/`["jobs"]` invalidation kalıbına bak (`docs/CODEMAPS/JOBS_AND_EVENTS.md`);
**yeni bir polling mekanizması icat etme.**

**Yapılacak:** `useRequestPackageValidation` hook'u + detail panelinde sunucu-bayrağı kapılı
blok + queued/running/passed/failed durumu + route düzeyi backend testi + frontend testi.
**Yapılmayacak:** yeni endpoint, yeni komut, yeni tablo, OCC/Idempotency semantiğine dokunuş.

---

## REUSE listesi (önce bunları oku, sonra kod)

1. `docs/CODEMAPS/FRONTEND_MAP.md` — sayfa → `lib/*.ts` → react-query key → endpoint grubu
2. `docs/CODEMAPS/BACKEND_ROUTES.md` §library — `validation-runs` satırı OCC/Idempotency biçimini yazıyor
3. `frontend/src/pages/Library.tsx` — `PackageApprovalBlock` (iki-adım onay + OCC gövdesi olan en yakın komşu)
4. `frontend/src/test/libraryActions.test.tsx` — OCC/Idempotency assertion kalıbı
5. `docs/spec/08_*` §7 "Request validation" + §9.1

---

## Çalışma döngüsü (bu repoda kanıtlanmış)

1. `git fetch --all --prune` → `git status --short` → temiz değilse **DUR**; `origin/main`'e reset.
2. Önceki adım PR'ının merge edildiğini doğrula (`gh pr list --state all`).
3. `docs/CODEMAPS/` haritasını oku, sonra `codebase-memory-mcp` ile sembol bul. **Kör grep + tam dosya okuma yapma.**
4. **Kusuru önce üret** — UI boşluğu için: bayrağın `true` döndüğünü ama hiçbir hook'un çağırmadığını testle göster.
5. Branch `feat/library-request-validation-ui`; **direct-author, Workflow yok**.
6. Yeni dosyaları Bash heredoc ile yaz (gate-free); mevcut dosya EDIT'i fact-force tetikler → 4 olgu sun, retry.
7. Lokal doğrulama: `cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest -q`
   · frontend `npm run typecheck && npm run coverage -- --no-file-parallelism`.
8. **Read-only adversarial review subagent çalıştır** — ADIM 4'te bu, dokümantasyonda iki
   fazla-iddia ve beş test zayıflığı buldu. Her CRITICAL/HIGH'ı **probe ile ampirik doğrula**;
   düzeltmeden önce üret.
9. Commit `feat(library): <subject>` (**AI attribution YOK**) → PR → `gh pr checks <n> --watch`.
   **Self-merge kapalı — kullanıcıya merge ettir.**

### Ortam tuzakları (ADIM 4'te bizzat karşılaşıldı)

- Paralel worktree'ler aynı DB'yi paylaşır: **`TEST_DATABASE_URL` ile worktree'ye özel izole DB kullan**
  (ör. `postgresql+asyncpg://entropia:entropia@localhost:5432/entropia_<slug>_test`).
- Alt küme koşarken **`--no-cov` ekle** — tek dosyalık koşu paketin tamamını ~%4 ölçer, kapı sahte kırmızı verir.
- **`pytest … | tail` KULLANMA** — exit code `tail`'in olur. Çıktıyı dosyaya yaz, `$?`'i ayrı oku.
- Tam suite'i **tek çağrıda** koş, ortada öldürme; koşarken **`uv sync` çalıştırma**.
- vitest için **`--no-file-parallelism` ZORUNLU**; worktree'de `frontend/node_modules` yoksa önce `npm ci`.
- Taze worktree'de backend dev bağımlılıkları için bir kez `uv sync --all-extras` (suite koşarken DEĞİL).

---

## Paste-ready resume prompt

```
ENTROPIA V18 — ADIM 5: Library Request-Validation UI

ROL: Entropia V18 üzerinde kıdemli principal engineer ve release-closure sorumlusu.
Amaç yeni özellik icat etmek değil; canonical Production V1 sözleşmesini current
origin/main üzerinde kanıtlamak, yalnız doğrulanmış boşluğu dar bir PR ile kapatmak.

ZORUNLU BAŞLANGIÇ
1. git fetch --all --prune ; git status --short (temiz değilse DUR, stash/silme YOK)
2. origin/main SHA + açık PR/issue snapshot'ı al
3. Önceki adım PR'ı (#521, ESP export contract v2) main'e merge edilmiş mi doğrula; edilmediyse DUR
4. Oku: docs/STAGE_NEXT_KICKOFF.md → docs/audit/current_main_ground_truth_2026-08-03.md §18 + §G-04
   → docs/CODEMAPS/FRONTEND_MAP.md + BACKEND_ROUTES.md §library → docs/spec/08_* §7/§9.1
5. Eski README/CLAUDE.md/handoff iddiasını current truth sayma
6. Önce mevcut davranışı test/probe ile yeniden üret; kusur üretilemiyorsa kod yazma

BU ADIMIN AMACI
Package Library detay panelinde "Request Validation" aksiyonunu bağlamak. Backend TAM:
POST /v1/library/{entity_id}/validation-runs (201) → pkg_cmd.request_package_validation →
start_package_validation_run; rol kapısı ensure_can_edit; bayrak can_request_validation
list+shared+detail DTO'sunda. Eksik olan YALNIZ frontend yüzeyi: lib/library.ts bayrağı
tipliyor ama çağıran hook yok.

BRANCH: feat/library-request-validation-ui
COMMIT: feat(library): dispatch package validation runs from the catalog detail panel

KAPSAM
- frontend/src/lib/library.ts: useRequestPackageValidation hook (Idempotency-Key +
  expected_head_revision_id OCC gövdesi; mevcut useExportPackage kalıbını aynala)
- frontend/src/pages/Library.tsx: sunucu-bayrağı kapılı blok (can_request_validation),
  queued/running/passed/failed durumu, 409/422 zarfını verbatim render
- Route düzeyi backend testi + frontend testi
- V18 mockup (docs/spec/index_guncellenmis_duzeltilmis_v18.html) görsel referanstır

TAVİZ VERİLEMEZ
- UI hidden/disabled durumu authorization DEĞİLDİR; sunucu her istekte yeniden doğrular
- Route path, react-query key, OCC token (expected_head_revision_id), Idempotency-Key,
  SSE taksonomisi, app/nav.ts DEĞİŞMEZ
- Yeni endpoint/komut/tablo YOK; yeni polling mekanizması icat etme — mevcut jobs/SSE kalıbı
- Uzun işler durable queue/worker üzerinden yürür
- Hata taksonomisi: 409 PACKAGE_REVISION_CONFLICT · 409 VALIDATION_ALREADY_RUNNING ·
  422 VALIDATION_PIPELINE_UNAVAILABLE — üçü de verbatim gösterilir
- Kanonik boşlukta formül/öncelik/ürün kararı uydurulmaz
- Başarısız test varken "Complete"/"Done" YAZILMAZ

ARAÇ KULLANIMI
- Araştırma/mimari/test inceleme ve adversarial review için READ-ONLY subagent kullan
- Aynı dosyalara eşzamanlı birden fazla writer atama; production değişikliğini ana oturum yapsın
- Subagent bulgularını gerçek kod ve testlerle DOĞRULA (ADIM 4'te review dokümanda iki
  fazla-iddia ve beş test zayıflığı buldu — hepsi gerçekti, ama her biri probe ile ölçüldü)
- Tek branch, tek PR, tek sorumlu writer

DOĞRULAMA
- cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest -q
- cd frontend && npm run typecheck && npm run coverage -- --no-file-parallelism
- TEST_DATABASE_URL ile worktree'ye özel izole DB kullan; alt küme koşarken --no-cov;
  pytest çıktısını `| tail` ETME (exit code kaybolur)
- OpenAPI değişirse: make openapi ; codemap değişirse ilgili docs/CODEMAPS/ dosyasını tazele

PR DİSİPLİNİ
- Yalnız bu slice; ilgisiz refactor/dependency upgrade/görsel değişiklik YOK
- Claude merge etmez, tag/release oluşturmaz
- PR sonunda raporla: base SHA, branch, commit, PR, changed behavior, unchanged boundaries,
  targeted tests, full-suite exit code, migration/OpenAPI/codemap etkisi, kalan risk,
  sonraki tek adım

DURMA KOŞULU: Yalnız Library Request-Validation UI yüzeyini değiştir. PR aç ve dur.
```
