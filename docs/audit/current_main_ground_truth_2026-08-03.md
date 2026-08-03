# Current-main ground truth — 2026-08-03

## 1. Audit identity

| | |
|---|---|
| **Amaç** | `origin/main` üzerindeki gerçekleri yeniden ölçmek, stale status belgelerini düzeltmek, sonraki oturumların yanlış migration / test / PR / issue / acceptance bilgisiyle çalışmasını engellemek. |
| **Tip** | **docs/audit-only.** Production kodu, migration, test beklentisi, runtime config ve engine davranışı **değişmedi**. |
| **Branch** | `docs/current-main-ground-truth-reset` |
| **Ölçüm tarihi** | 2026-08-03 |
| **Otorite sırası** | (1) `docs/spec/Entropia_V18_Master_Technical_Reference_v1_0.md`, (2) ilgili `docs/spec/01–22`, (3) V18 Handoff standardı, (4) V18 HTML (yalnız görünür UI referansı), (5) current production code / migrations / testler. |
| **Kural** | Hiçbir sayı eski dokümandan kopyalanmadı. Her satır bu ağaçtan yeniden ölçüldü; ölçüm komutu ve exit code §3'te. |

> `git switch main` bu worktree'de **mümkün değil** — `main`,
> `/Users/mirbagirzade/Development/Entropia-s5b-codex` worktree'sinde checkout edilmiş
> durumda. Eşdeğer yol kullanıldı: çalışma branch'i doğrudan `origin/main`'den
> oluşturuldu, dolayısıyla ağaç içeriği `origin/main` ile birebir aynıdır
> (`git rev-parse HEAD` = `git rev-parse origin/main`).

---

## 2. Current main SHA

| Olgu | Değer |
|---|---|
| `git rev-parse origin/main` | **`0dcce690999f8c7029e5b3984b1b39aa7df28222`** |
| Kısa | `0dcce69` |
| Commit tarihi | `2026-07-30T22:48:38+03:00` |
| Son merge | `#517 refactor(i08): enforce registry and strategy cross-reference FKs` |
| Worktree durumu | `git status --short` boş (temiz) |

Son 8 commit:

```
0dcce69 Merge pull request #517 from alimirbagirzade/refactor/i08-cross-reference-fks-1
57f7320 test: seed strategy rationale family in parity acceptance
2596a24 Merge pull request #516 from alimirbagirzade/codex/v18-final-acceptance-closure
1432bff Merge remote-tracking branch 'origin/main' into codex/v18-final-acceptance-closure
694d9a1 Merge pull request #513 from alimirbagirzade/codex/s5b-conflict-matrix-residuals
8b2c24e docs: reconcile visual acceptance traceability
d0067bb Merge remote-tracking branch 'origin/main' into refactor/i08-cross-reference-fks-1
27bf011 ci: enforce Linux visual regression gate
```

---

## 3. Environment and commands

Bu oturumda **gerçekten koşulan** komutlar ve **gerçek** exit code'ları. Çıktılar dosyaya
yazıldı; exit code ayrı okundu (`pytest … | tail` **kullanılmadı** — pipe exit code'u
maskeler).

| # | Komut | Exit | Sonuç |
|---|---|---|---|
| 1 | `git fetch --all --prune` | 0 | remote taze |
| 2 | `git status --short` | 0 | çıktı boş → worktree temiz |
| 3 | `gh pr list --state open --limit 50` | 0 | **0 açık PR** |
| 4 | `gh issue list --state open --limit 50` | 0 | **0 açık issue** |
| 5 | `cd backend && uv sync --all-extras` | 0 | venv güncel |
| 6 | `uv run alembic heads` | 0 | `0043_i08_registry_strategy_fks (head)` — **tek head** |
| 7 | `uv run python -m entropia.apps.api.openapi_export --check` | 0 | `OpenAPI snapshot is up to date` |
| 8 | `uv run pytest --collect-only -q --no-cov > /tmp/entropia_backend_collect.txt` | 0 | **2886 test / 271 dosya** |
| 9 | `uv run pytest tests/unit/test_capability_matrix.py -q --no-cov` | 0 | 79 passed — Python↔TS capability parity **yeşil** |
| 10 | `cd frontend && npm ci` | 0 | lockfile'a uygun temiz install |
| 11 | `npm run typecheck` (`tsc -b --noEmit`) | 0 | tip hatası yok |
| 12 | `npx vitest list --no-file-parallelism` | 0 | **673 test / 66 dosya** |
| 13 | `python3 docs/audit/acceptance_id_scan.py` | 0 | 347 test dosyası tarandı; **GLOBAL 174/215 (%80)**, untraced 41 |

Ölçüm tuzakları (bu oturumda uyuldu): worktree'de `frontend/node_modules` **yoktu** →
`npm ci` önce koşuldu; vitest `--no-file-parallelism` ile listelendi; backend alt-küme
koşularına `--no-cov` eklendi (aksi halde `--cov-fail-under=90` sahte kırmızı verir).

**Koşulmayan (bilinçli):** tam backend pytest suite ve tam vitest run. Bu adım
docs-only; kapı olarak CI otoritedir (`gh run list --branch main --limit 1`).
Aşağıdaki test sayıları **collection** sayılarıdır, **pass** sayıları değildir — §19'a bak.

---

## 4. Schema and migration facts

| Olgu | Değer | Nasıl ölçüldü |
|---|---|---|
| Alembic head | **`0043_i08_registry_strategy_fks`** | `uv run alembic heads` (exit 0) |
| Head sayısı | **1 (tek head)** | `alembic heads` tek satır + down_revision graph taraması: `down_revision` olarak anılmayan tek revision |
| Migration dosyası | **43** | `ls backend/alembic/versions/*.py \| wc -l` |
| Postgres tablosu | **104** | `grep -rh __tablename__ …/postgres/models/ \| sort -u \| wc -l` |
| Model dosyası | **30** | `ls …/postgres/models/*.py \| wc -l` |
| `ForeignKey(...)` bildirimi | **140** (25 dosyada) | `grep -rh "ForeignKey(" …/postgres/models/ \| wc -l` |

Son 6 migration: `0038_backtest_run_event`, `0039_backtest_run_cancellation`,
`0040_export_type_agent_pine`, `0041_filtered_event_artifact`,
`0042_package_import_source_name`, `0043_i08_registry_strategy_fks`.

`0043` üç `op.create_foreign_key` çağrısı taşır (satır 59, 66, 73) — PR #517'nin
cross-reference FK'leri **main'dedir**.

---

## 5. Backend API facts

| Olgu | Değer | Nasıl ölçüldü |
|---|---|---|
| Route decorator | **195** | `grep -rEho '@router\.(get\|post\|put\|patch\|delete)\(' …/routes/ \| wc -l` |
| Route dosyası | **31** | `ls …/apps/api/routes/ \| wc -l` |
| OpenAPI path | **177** | `docs/openapi.json` |
| OpenAPI operation | **196** | `docs/openapi.json` |
| OpenAPI schema | **119** | `docs/openapi.json` |
| Drift guard | **temiz** | `openapi_export --check` exit 0 |

> Decorator (195) ile operation (196) arasındaki 1 fark route dizini dışında bildirilen
> bir operation'dan gelir (ör. app-level health). Drift guard yeşil olduğu için yayımlanan
> sözleşme ile kod **ayrışmıyor**.

### Sürüm sabitleri (kodda ölçüldü)

| Sabit | Değer | Yer |
|---|---|---|
| `ENGINE_VERSION` | **`backtest-engine-v18-same-candle-entry-exit`** | `domain/backtest/manifest.py:118` |
| `METRIC_SET_VERSION` | `metric-set-v1` | `domain/backtest/manifest.py:119` |
| `EXPORT_SCHEMA_VERSION` | `v1` | `domain/backtest/export.py:23` |
| `ARTIFACT_CHECKSUM_SCHEMA_VERSION` | `artifact-checksum-v1` | `domain/backtest/artifacts.py:69` |
| `VALIDATOR_VERSION` (ESP) | `esp-validation-v1` | `domain/esp/validation.py:54` |
| `VALIDATOR_VERSION` (CP) | `cp-validation-v3` | `domain/create_package/validation.py:35` |
| `GENERATOR_VERSION` | `cp-candidate-gen-v2` | `domain/create_package/generator.py:43`, `candidate.py:29` |

### Capability matrix

| Olgu | Değer |
|---|---|
| Matrix girdisi | **62** |
| `active_v1` | **40** |
| `future_dev` | **22** |
| Python↔TS mirror parity | **YEŞİL** — `tests/unit/test_capability_matrix.py` 79 passed (exit 0) |

Kaynak: `backend/src/entropia/domain/backtest/capabilities.py::CAPABILITY_MATRIX`
(tuple, 62 `CapabilityOption`). Mirror: `frontend/src/lib/engineCapabilityMatrix.generated.ts`.

> **Uyarı — token sayımı ölçüm değildir.** Dosyadaki `"active_v1"` / `"future_dev"`
> string'lerini grep'lemek yanlış sayı verir (docstring'ler ve tip union'ları da sayılır).
> Doğru ölçüm modülü import edip `CAPABILITY_MATRIX` üzerinde `status` saymaktır.

---

## 6. Frontend route / UI facts

| Olgu | Değer | Nasıl ölçüldü |
|---|---|---|
| `App.tsx` literal `path="…"` | **29** (28 somut + `path="*"` catch-all) | `grep -o 'path="[^"]*"' frontend/src/App.tsx` |
| Dinamik üretilen route | **5** (`FUTURE_DEV_SUBPAGES` − `graphic_view`) | `App.tsx:232-244` |
| **Toplam somut route** | **33** + 1 NotFound catch-all | yukarıdakilerin toplamı |
| `ALL_NAV_ITEMS` | **25** | `frontend/src/app/nav.ts:27-81` (NAV bölümlerindeki `path:` girdileri) |
| `FUTURE_DEV_SUBPAGES` | **6** | `nav.ts:134-164` |
| Sayfa dosyası | **31** | `ls frontend/src/pages/*.tsx \| wc -l` |
| `lib/*.ts` | **40** | `ls frontend/src/lib/*.ts \| wc -l` |
| Test dosyası (vitest) | **66** | `ls src/test/*.test.ts*` |

---

## 7. Test and CI facts

| Olgu | Değer | Kaynak |
|---|---|---|
| Backend **collection** | **2886 test / 271 dosya** | `pytest --collect-only -q --no-cov`, exit 0 |
| Frontend **collection** | **673 test / 66 dosya** | `npx vitest list --no-file-parallelism`, exit 0 |
| Frontend typecheck | **temiz** | `npm run typecheck`, exit 0 |
| Acceptance ID scan | **174/215 (%80)**, untraced 41, 347 test dosyası | `docs/audit/acceptance_id_scan.py`, exit 0 |

> Bu iki sayı **collected**'dir, **passed** değil. Tam suite bu oturumda koşulmadı
> (docs-only slice). "Passed" iddiası için otorite CI'dır.

### Workflow envanteri (2 dosya)

`.github/workflows/ci.yml` — job'lar: `backend`, `frontend`, `docker`
`.github/workflows/e2e.yml` — job'lar: `e2e`, `a11y`, `e2e-dev`

| Kapı | Durum | Kanıt |
|---|---|---|
| Linux visual-regression | **PRESENT · BLOKLAYICI** | `e2e.yml:17 runs-on: ubuntu-latest`, `:114 run: npm run visual`; 8 `*-chromium-linux.png` baseline commit'li; CI asla `--update-snapshots` koşmuyor |
| axe a11y ratchet | **PRESENT · BLOKLAYICI** | `e2e.yml:154 runs-on: ubuntu-latest`, `:230 run: npm run a11y`; ceiling mekanizması `frontend/e2e/a11y-baseline.json` (eksik baseline = hard failure) |
| `continue-on-error` | **hiçbir yerde yok** | `grep -rn "continue-on-error" .github/` → tek hit, o da bir **yorum satırı** (`ci.yml:114`) |
| Backend coverage | **≥ %90 kapı** | `backend/pyproject.toml` `addopts … --cov-fail-under=90` |
| Frontend coverage | lines 83 / statements 80 / functions 73 / branches 70 | `frontend/vite.config.ts:75-79` |
| Backend dependency audit | **PRESENT · BLOKLAYICI** | `ci.yml` `uv run --with pip-audit pip-audit` |
| Frontend dependency audit | **PRESENT · BLOKLAYICI** (3 dondurulmuş advisory) | `ci.yml` `node scripts/npm-audit-gate.mjs` |
| SAST / CodeQL / semgrep | **ABSENT** | `grep -rni "codeql\|semgrep\|trivy\|gitleaks" .github/` → 0 |
| Secret scanning | **ABSENT** | aynı grep |
| Container image scan | **ABSENT** | `docker` job yalnız build eder |
| Performance / Lighthouse / k6 | **ABSENT** | `grep -rni "lighthouse\|k6\|benchmark" .github/` → 0 |
| Observability job | **ABSENT** | iki workflow'da da yok |
| Klavye testi | **ÇOK İNCE** | E2E `14-keyboard-flow.spec.ts` → **1 test**; vitest → 4 focus/klavye testi. Sayfa başına klavye gezinimi **yok** |
| Backup / restore | **script + runbook PRESENT, CI kapısı YOK** | `scripts/backup.sh`, `scripts/backup-verify.sh`, `scripts/restore.sh`, `docs/BACKUP_DR.md`; hiçbir workflow bunları koşmuyor |

---

## 8. Recently landed work — tarihsel merge doğrulaması

Aşağıdakilerin hepsi **current main'de doğrulandı** (dokümandan değil, koddan).

### PR #513 — Same Candle Entry / Exit (S5b kalıntısı)

| Halka | Kanıt |
|---|---|
| Schema | `domain/strategy/config.py:1047` `same_candle_entry_exit: Literal[…5 değer…]` |
| Engine | `domain/backtest/engine.py:895`, `:1834` `admits_entry = same_candle_entry_exit == "exit_first"` |
| Diagnostics | `engine.py:1841` `"policy": same_candle_entry_exit` |
| UI | `frontend/src/lib/strategyForm.ts:348, 367, 491-492` |
| Test | `backend/tests/unit/test_strategy_config_validation.py`, `test_backtest_engine.py`, `frontend/src/test/strategyForm.test.tsx` |
| Sürüm | `ENGINE_VERSION = backtest-engine-v18-same-candle-entry-exit` |

**Verdict: LANDED, zincir tam (UI → schema → engine → diagnostics → test).**

### PR #516 — V18 görsel kabul kapanışı

- Linux visual-regression gate **main'de ve bloklayıcı** (§7).
- 8 Ubuntu + 8 darwin baseline commit'li; tolerans `maxDiffPixelRatio 0.02`.
- Görsel kabul belgeleri (`v18_visual_deviations.md`, `v18_visual_traceability.md`)
  A-06'yı kapalı, A-08'i **açık** gösteriyor — bu **doğru** ayrımdır (§17).

### PR #517 — cross-reference FK'ler

- `0043_i08_registry_strategy_fks` head; 3 `create_foreign_key`; **tek head**.

### F-07 raw-id sweep

| Alan | Durum | Kanıt |
|---|---|---|
| `display_label` | PRESENT | `queries/create_package.py:65,303` → `pages/PreCheck.tsx:142,218` |
| `source_package_name` | PRESENT | `queries/package_import.py:27` → `pages/Library.tsx:1271,1287` |
| `item_label` | PRESENT | `jobs/backtest_engine.py:327,673,851,881` (hash **dışında** pinlenir) → `components/ResultDetail.tsx:431,602` |
| `scope_label` | PRESENT | `queries/readiness_check.py:83,115` → `pages/ReadyCheck.tsx:295` |
| Ortak component | PRESENT | `frontend/src/components/LabelledId.tsx` — label yoksa **id'yi tek başına** gösterir, ASLA id'den isim türetmez |
| Embedded registry satırı (#515) | **FIXED** | `pages/Embedded.tsx:213-217` collapsed satır canonical key + insan-okur pin durumu; ham `pkgrev_…` yalnız expanded technical detail'da (`:303`) |

### Results History başlığı

- `queries/results_history.py:264` hâlâ `"display_title": f"Backtest Result {result_id}"` **üretiyor**,
  ama `pages/ResultsHistory.tsx` bunu **render etmiyor** (`:40-47` gerekçeli yorum) —
  satır ham `result_id`'yi tek bir `<code>` bağlama anahtarı olarak gösteriyor.
- Regresyon testi var: `frontend/src/test/resultsHistory.test.tsx:164-170`.
- **Aynı opaque id görünür metinde iki kez basılmıyor.** (Id ayrıca `aria-label` ve URL'de
  geçiyor — bu bir A-08 riski, §17.)
- **Kalıntı:** aynı sentetik başlık **Panel ▸ Logs**'ta hâlâ render ediliyor — §9/G-06.

### CORS

- `apps/api/main.py:130-137` `CORSMiddleware`; `allow_headers` **10 elemanlı kapalı liste**,
  `allow_methods` 7 elemanlı pin; `expose_headers` 3 eleman.
- Production profili **fail-closed**: `config/settings.py:146-169` —
  `ENTROPIA_ENV=production` iken boş origin listesi **ve** `"*"` başlatmada `ValueError`.
- Dev default: `http://localhost:5173,http://localhost:8080`.
- **LANDED.** Kalan incelik: §11/H-04.

---

## 9. Confirmed implementation gaps

### G-01 · ESP resolver, soft-delete edilmiş Package Root'u YENİ resolution'da kullanıyor

| | |
|---|---|
| **Status** | ~~CONFIRMED GAP~~ → **KAPANDI 2026-08-03**, `fix/esp-lifecycle-resolution` (ADIM 2). Aşağıdaki tespit kapanış-öncesi kayıt olarak **olduğu gibi** bırakıldı. |
| **Canonical source** | doc 07 §12, doc 09 §4.3, doc 09 §9.5 |
| **Production path** | `backend/src/entropia/application/queries/esp.py:214-268` |
| **Kanıt** | Fonksiyon yalnız `entry.trust_state` üzerinden karar veriyor (`:250`); `EntityRegistry`/`PackageRoot` **hiç yüklenmiyor**, `deletion_state` ve `lifecycle_state` **hiç okunmuyor**. `commands/deletion.py` soft-delete yolunda `esp_repo.set_trust_state` **çağırmıyor** (`set_trust_state` yalnız `commands/esp.py:281,431`'den çağrılır). Fonksiyonun kendi docstring'i (`:228`) tersini iddia ediyor: *"deprecated / soft-deleted registry entry -> RESOLVER_NOT_ACTIVE"*. |
| **Test/evidence** | Bu vakayı **hiçbir test kapsamıyor.** En yakın isimli test `tests/unit/test_esp_resolver.py:88` saf predicate'e `trust_state=UNAVAILABLE` geçiriyor — `deletion_state`'i test etmiyor, ve soft-delete `UNAVAILABLE` yazmıyor. Repo içi kayıt: `docs/audit/acceptance_id_map.md:241-262` (2026-07-29'da ampirik olarak üretilmiş). |
| **Risk** | Silinmiş bir paket yeni Pre-Check/paket üretiminde bağlanabilir; kod, yayımlanmış sözleşmesiyle çelişiyor. |
| **Next slice** | ~~**ADIM 2**~~ — **landed** olarak `fix/esp-lifecycle-resolution` |

> **Kusur DEĞİL:** historical pinned revision'ın okunabilir kalması. Bu doğru davranıştır ve
> `tests/integration/test_acceptance_esp_package_gaps.py` (PC-19 clause 1) ile sabitlenmiştir.
> ADIM 2 bunu bozmadı: kapı yalnız YENİ-iş yolunu (`resolve_embedded_dependency`) daraltır,
> pinlenmiş manifest ise `package_revision`'dan doğrudan okunur.

> **Kapanış özeti (2026-08-03).** Kusur önce `origin/main` @ `ef47847` üzerinde yeniden
> üretildi (activate `ta.sma` → root soft-delete → resolve → `resolved=True`, aynı revision).
> Üç eksende kapatıldı: (1) `domain/esp/resolver.py::evaluate_resolution` artık
> `ResolverRootFacts` alıyor — active root + `embedded_system` kind zorunlu; (2)
> `commands/deletion.py` deprecate-first `DELETE_POLICY_BLOCKED` blocker'ı (doc 09 §9.5 adım 2)
> ve bu preflight artık `soft_delete_registry_root`'tan da çağrılıyor — **`soft_delete_package`
> preflight'ı tamamen atlıyordu**, tek yerde blocker yetmezdi; (3)
> `registry_fingerprint` root lifecycle'ı da hash'liyor → registry/lifecycle değişimi eski
> Pre-Check taramasını sunucu tarafında `PRECHECK_STALE` yapıyor.
> **Sürüm notu:** `ENGINE_VERSION` DEĞİŞMEDİ — backtest motoru ve sayısal semantik bu slice'ta
> hiç dokunulmadı; değişen yüzey Pre-Check/paket üretimi ve silme lifecycle'ıdır.
> **Migration YOK** (şema değişmedi, alembic head `0043_i08_registry_strategy_fks`).

### G-02 · ESP export manifest'i resolver sözleşme olgularını taşımıyor

> **KAPANDI — 2026-08-03, `feat/esp-export-contract-v2`.** Kusur önce `origin/main` @ `6c46c03`
> üzerinde bir probe testiyle empirik yeniden üretildi: `embedded_resolver_contract` ve
> `embedded_resolver_validation_run` satırları veritabanında **MEVCUTKEN** manifest dört alanı
> birden atlıyordu. Export **schema v2**'ye taşındı (`domain/package/export_contract.py`):
> `export_schema_version` · `exporter_version` · `resolver_contract_snapshot` ·
> `validation_evidence_snapshot`. Alanlar **export edilen revision'ın kendi satırlarından**
> okunur (kökün head'inden asla), `created_at` hash'e girmez ve canlı registry pointer'ı
> manifest'in dışında `registry_observation` olarak taşınır → arada bir şey değişmediyse
> yeniden export **birebir** aynı `manifest_hash`'i verir. **Dürüst sınır (adversarial review
> sonrası daraltıldı, iki probe testiyle ölçüldü):** digest revision ömrü boyunca DONMUŞ
> değildir — revision'ın kendi `validation_state`/`approval_state`'i yerinde güncellenir ve
> yeniden validate yeni bir run satırı ekler; ikisi de kasıtlı, test edilmiş davranıştır.
> Kanıt yoksa `legacy_incomplete_evidence`; `passed` asla uydurulmaz.
> Import v1 (alansız) ve v2 okur, başka her versiyon iki katmanda fail-closed reddedilir;
> yabancı adapter yerel güven kazanmaz (sıfır yeni contract/registry satırı).
> **`ENGINE_VERSION` DEĞİŞMEDİ**, **migration YOK** (alembic head `0043_i08_registry_strategy_fks`).
> Tam sözleşme + v1/v2 uyumluluk matrisi + determinizm kanıtı: `docs/audit/esp_export_schema_v2.md`.

| | |
|---|---|
| **Status** | ~~CONFIRMED GAP~~ → **CLOSED (2026-08-03)** |
| **Canonical source** | doc 08 §export, doc 09 §4 |
| **Production path** | `backend/src/entropia/application/commands/package_lifecycle.py:743-827` (manifest dict `:785-799`) |
| **PRESENT** | `validation_state` (`:795`), `approval_state` (`:796`), root/revision kimliği, content hash, dependency snapshot, manifest hash |
| **ABSENT** | runtime adapter · warm-up · timing semantics · repaint policy · validation run id · validator version · vectors/checks · evidence |
| **Yalnız teamül** | canonical resolver key ve complete signature manifest'te **alan olarak yok**; sadece üretenin `input_contract`'a koyduğu kadarıyla hayatta kalıyor (`:791` passthrough) |
| **Test/evidence** | `tests/integration/test_acceptance_esp_package_gaps.py:271` bunu zaten böyle iddia ediyor |
| **Risk** | Dışa aktarılmış paket, hangi runtime/timing/repaint semantiğiyle doğrulandığını taşımıyor — export tek başına yeniden üretilebilir değil. |
| **Next slice** | `feat/esp-export-contract-evidence` (ADIM 2'den sonra) |

### G-03 · Tool Gateway'de `strategy.*` ve `trading_signal.*` araçları YOK

> **STRATEGY YARISI KAPANDI — 2026-08-03, `feat/agent-strategy-tool-gateway`.** Kusur önce
> `origin/main` @ `9944bfb` üzerinde yeniden üretildi: beş `strategy.*` literalinin beşi de
> `parse_tool_name` ile `ToolPolicyScopeError` veriyordu (`ToolName` 23 üye, capability'siz
> exposure 21 isim). Beş araç eklendi (`ToolName` → **28 üye**) ve **yeni iş mantığı
> yazılmadı**: her handler insanın kullandığı aynı `commands/strategy_draft.py` +
> `queries/strategy.py` hattına delege ediyor; ownership, `expected_draft_row_version` OCC,
> `Idempotency-Key` (`run_idempotent`), compiler verdict, audit + outbox ve Mainboard re-pin
> o komutların **içinde** kalıyor. Scope tablosu: get → `observation|research`;
> create/patch/validate → `research|proposal`; save → `proposal`; beşi de **asla
> `execution`** değil, dolayısıyla hepsi `agent` kuyruğunda (koşu ayrı araçtır, Save bir
> Ready PASS değildir). **Gateway sertleştirmesi (dar):** yalnız strategy ailesi için tipli
> governance-dışı hata artık **durable `FAILED` tool call** olarak yazılıyor (bayat OCC →
> `STRATEGY_DRAFT_CONFLICT`, bozuk istek → `AGENT_TOOL_REQUEST_INVALID`), çünkü önceden
> `dispatch_tool_call`'dan kaçıp worker rollback + 3× retry sonucu **hiç satır bırakmıyordu**;
> S4 aileleri (allocation/trade_log) landed *propagate* sözleşmesini koruyor — bilinen,
> tescilli asimetri. **`trading_signal.*` yarısı AÇIK** (TS-20 / AOS-20). 23 test:
> `backend/tests/integration/test_gateway_parity_strategy.py`. Tam sözleşme + scope tablosu +
> gerçek ToolCall zarfları: **`docs/audit/agent_strategy_tool_gateway.md`**.
> **`ENGINE_VERSION` DEĞİŞMEDİ**, **migration YOK** (alembic head `0043_i08_registry_strategy_fks`),
> **OpenAPI değişmedi** (yeni route yok), frontend değişmedi.

| | |
|---|---|
| **Status** | ~~CONFIRMED GAP~~ → **TAMAMEN CLOSED (2026-08-03)**: strategy yarısı `feat/agent-strategy-tool-gateway` (PR #526), `trading_signal.*` yarısı `feat/agent-trading-signal-tool-gateway` (post-V1 S6) |
| **Canonical source** | doc 02 AT-21, doc 04 TS-20 ("via Tool Gateway") |
| **Production path** | `backend/src/entropia/domain/agent_lab/tool_gateway.py` (`ToolName`, ölçüm anında **23 üye**; strategy sonrası **28**; signal sonrası **33** / 31 exposed) |
| **Kanıt** | Ölçüm anında 10/10 literal ABSENT: `strategy.get_draft`, `strategy.create_draft`, `strategy.patch_draft`, `strategy.validate_draft`, `strategy.save_revision`, `trading_signal.upload_source_asset`, `trading_signal.request_import`, `trading_signal.get_import_report`, `trading_signal.create`, `trading_signal.create_revision`. Repo genelinde bu literaller **0 hit**. → **Şimdi 10/10 literal VAR.** Signal yarısı kod yazılmadan ÖNCE yeniden üretildi: `d6bbe9b`'de beş literal de `ToolPolicyScopeError` verdi. |
| **Tuzak** | `trade_log.upload_source_asset` / `request_import` / `create` / `create_revision` **VAR** — farklı work-object ailesi, parity kanıtı değil. |
| **Domain-command parity (AYRI EKSEN)** | **TAM**: `commands/strategy_draft.py` (create/patch/validate/save_revision/derive/clear) + `queries/strategy.py`; `commands/trading_signal.py` (upload/request_import/create/create_revision/export) + `queries/trading_signal.py::get_import_report`. **Bunu Tool Gateway parity diye raporlama.** |
| **Test/evidence** | `test_gateway_parity_strategy.py` (AT-21, 23 test) + `test_gateway_parity_trading_signal.py` (TS-20/AOS-20, **33 test**). `test_acceptance_agent_parity_gaps.py` docstring'i iki kez güncellendi; artık her iki yarı da KAPALI olarak kayıtlı. Beş yeni koruma **negative control** ile ölçüldü (kapat → test kırmızı). |
| **Risk** | ~~Agent bu iki aileyi Gateway üzerinden hiç kullanamaz~~ → **kapandı.** Kalan dar artık: `trading_signal.attach` (bağımsız re-pin) ve `trading_signal.delete` hiçbir external work-object ailesinde tool DEĞİL (attach-at-save `create` ile kapsanıyor). Ayrıca **`trade_log.request_import` aynı eksik broker hand-off'u taşıyor** — doğrulandı, bu slice'ın kapsamı dışı bırakıldı, sıradaki tek adım. Tam kayıt: `docs/audit/agent_trading_signal_tool_gateway.md`. |

### G-04 · Package Library Request Validation — **frontend-only** boşluk

> **KAPANDI — 2026-08-03, `feat/library-request-validation-ui`.** Kusur önce `origin/main`
> @ `a570934` üzerinde empirik yeniden üretildi: `can_request_validation` `lib/library.ts:88`'de
> **tip olarak vardı** ama `Library.tsx`'te yalnız generic `PERMISSION_FLAGS` ızgarasında
> `yes`/`no` metni olarak basılıyordu — mutation hook yok, action yok, queued/running yüzeyi yok.
> Kapatma **yüzey** işidir: `useRequestPackageValidation` → mevcut `POST /library/{id}/validation-runs`,
> OCC body-form `expected_head_revision_id`, her submit'te taze `Idempotency-Key`. **İkinci
> certification yolu yazılmadı** — durable durum CreatePackage düzlemindeki
> `useValidationRun`'dan okunur (`live` seçeneği eklendi: terminal olana kadar 3 sn poll,
> SSE'nin kayıp-toleranslı yedeği). Route'un gövdesi `PackageValidationRunAcceptedResponse`
> ile **şemada yayımlandı** (O-30 tuzağı: `dict[str, Any]` drift guard'ı yeşil tutarken
> sözleşmeyi gizliyordu). **Dürüst sınır, ölçüldü:** koşu uçuştayken aynı `Idempotency-Key`
> ile tekrar gönderim **201 replay vermez** — wrapper'ın in-flight guard'ı `run_idempotent`'tan
> önce çalışır, 409 `VALIDATION_ALREADY_RUNNING` döner (guard hiçbir yazımdan önce patlar,
> ikinci kanıt satırı oluşmaz). UI bunu recovery yolu olarak render eder ve uçuştaki koşuyu
> takip eder. **PASS approval yapmaz**; Request Approval ayrı adım olarak kaldı.
> **`ENGINE_VERSION` DEĞİŞMEDİ**, **migration YOK** (alembic head `0043_i08_registry_strategy_fks`).

| | |
|---|---|
| **Status** | ~~CONFIRMED GAP (frontend) · backend COMPLETE~~ → **CLOSED (2026-08-03)** |
| **Canonical source** | doc 08 §validation |
| **Backend PRESENT** | Route `apps/api/routes/library.py:204` `POST /library/{entity_id}/validation-runs` (201) → `commands/package_lifecycle.py:547` → **aynı CP pipeline'ı**: `:619` `start_package_validation_run` (`commands/create_package.py:824`'ten import, `:64`). Rol kapısı: `package_lifecycle.py:585` `ensure_can_edit` (owner-or-Admin). Bayrak `can_request_validation` **list + shared + detail** DTO'da (`domain/package/permissions.py:37,98`; `queries/library.py:119/130, 173/184, 394/401`). |
| **Frontend ~~ABSENT~~ → LANDED** | ~~`pages/Library.tsx`'te action yok; bayrak yalnız salt-okunur "yes/no" hücresi. `lib/library.ts`'te mutation hook yok.~~ → `Library.tsx::PackageValidationActions` (idle/confirm/submit/queued/running/passed/failed/stale/already-running/unavailable/forbidden), `library.ts::useRequestPackageValidation`, durable durum `createPackage.ts::useValidationRun(id,{live})`'dan. `role="status"` + `aria-label="Validation run status"` canlı bölge, renk-dışı ilerleme (durum sözcüğü + cümle), submit sonrası kontrollü focus. |
| **Test** | Backend: `test_library_validation_run.py` (5 test, komut düzeyi) + `tests/unit/test_package_permissions.py` (2 test) + **YENİ** `test_library_validation_run_route.py` (**9 test, HTTP route düzeyi**: 201 zarf + şema yayını, OCC 409, already-running 409 + `details`, 422, 403, Idempotency-Key iki yarısı, worker → passed). Frontend: **YENİ** `libraryValidationRun.test.tsx` (**15 test**, tam state matrisi). E2E: **YENİ** `e2e/specs/20-library-request-validation.spec.ts` (Library → validation → worker → passed → approval available). |
| **Risk** | Backend'e ulaşılamayan bir yetenek: kullanıcı "yes" görüyor ama tetikleyemiyor. |

### G-05 · Shared Equity Allocation = sequential approximation (unified clock YOK)

| | |
|---|---|
| **Status** | CONFIRMED GAP — **ama gizlenmiyor, L4 ile bildiriliyor** |
| **Canonical source** | doc 13 §Shared Equity Allocation |
| **Production path** | `application/jobs/backtest_engine.py:298` dış döngü **item** üzerindedir, timestamp üzerinde değil; her item `_replay_strategy` (`:313`) ile kendi bar eksenini baştan sona koşar, sonra `combine_item_runs` (`:363`) katlar. |
| **Ölçüm** | global valuation clock **YOK** · her item kendi `_Ledger`'ı ile P0'dan başlar (`domain/backtest/engine.py:843`) · shared cash/reserve tek ledger **DEĞİL** (`engine.py:836-838` her item için yeniden hesaplanır) · dynamic sleeve capacity item'ın kendi equity'sinden (`engine.py:2808`) · cross-item exposure **önceki** item'ların kapanmış peak-notional pencerelerinden (`execution/state.py:315-323`) · conflict arbitration **ileri yönlü tek taraflı** (`state.py:346-352`), `NET` bilerek `BLOCK_OPPOSITE` olarak koşar (`engine.py:813-814`) · heterojen timeframe **uzlaştırılmıyor**, katlamada null'lanıyor (`execution/portfolio.py:530-531`) |
| **Diagnostic** | **VAR** — `execution/portfolio.py:67` `COMPOSITION_CURVE_WARNING = "portfolio_curve_sequential_not_unified_clock"`, `:550-551`'de 1'den fazla executing item varsa emit edilir ve immutable Result'ın `diagnostics["warnings"]`'ine yazılır. Kardeşi: `execution/output.py:88` `portfolio_rules_sequential_pin_order_precedence`. |
| **Test** | `tests/unit/test_backtest_portfolio_compose.py:240` token'ı stringi ile sabitler; `test_backtest_engine.py:829/858`, `:1159/1187`; `test_backtest_portfolio_rules.py:276-385`; `test_backtest_output.py:222` |
| **Risk** | Kullanıcı "shared equity allocation" beklerken ardışık yaklaşım alıyor. Sapma **bildirilmiş** olduğu için sessiz değil; yine de canonical sonuç gibi sunuluyor. |
| **Bu adımda** | Engine **değiştirilmedi**. |

### G-06 · Panel ▸ Logs hâlâ id'den türetilmiş sahte başlık gösteriyor

| | |
|---|---|
| **Status** | CONFIRMED GAP (I-16a kalıntısı) |
| **Production path** | `frontend/src/pages/PanelLogs.tsx:134` `<td>{row.backtest.display_title}</td>` ← `queries/panel_backtest_log.py:147` `f"Backtest Result {result.result_id}"` |
| **Kanıt** | Results History'de aynı alan **bilerek terk edildi** (`ResultsHistory.tsx:40-47` + regresyon testi), Panel Logs'ta terk edilmedi. `docs/implementation/v18_visual_traceability.md:199-200` revert notu **iki** query'yi birden anıyor, ama yalnız biri düzeltilmiş. |
| **Not** | Panel Logs'ta id görünür metinde **iki kez basılmıyor** (ayrı id kolonu yok) — kusur "id + yapıştırılmış isim", çift basım değil. |
| **Risk** | Düşük (kozmetik/bilgi kaybı), ama F-07 sweep'inin "BÜTÜN olarak COMPLETE" iddiasını yanlışlıyor. |

### G-07 · `portfolio_curve_sequential_not_unified_clock` UI'da ham token olarak görünüyor

| | |
|---|---|
| **Status** | CONFIRMED GAP (küçük) |
| **Production path** | `frontend/src/lib/backtest.ts:442-450` `diagnosticWarningLabel` — bu kod için **case yok**; `components/ResultDetail.tsx:643,661-669` uyarıyı `role="alert"` içinde **ham kod string'i** olarak basar. |
| **Risk** | En önemli honest-boundary uyarısı kullanıcıya makine token'ı olarak ulaşıyor. |

---

## 10. Confirmed evidence gaps

| # | Boşluk | Kanıt | Risk |
|---|---|---|---|
| **E-01** | **A-08 insan ekran-okuyucu denetimi YAPILMADI** ve GitHub #514 **yanlışlıkla KAPALI** | §17 | Release kabul kaydı gerçeğe aykırı |
| **E-02** | Fresh-install (`alembic upgrade head`, seed yok) agent runtime satırını kanıtlayan **pytest yok** | Integration conftest `create_all` kullanır (`tests/integration/conftest.py:46-47`), migration'ı koşmaz; her test satırı elle seed eder. Tek kanıt CI adımı `ci.yml` `alembic upgrade head` (satır düzeyi assert yok) | Migration seed'i sessizce kaybolursa test yakalamaz |
| **E-03** | Acceptance ID izlenebilirliği **174/215 (%80)**, 41 ID izlenemiyor | `acceptance_id_scan.py` çıktısı; en kötü sayfa **doc 16 Results History 2/16** | Kabul sözleşmesinin %20'si teste bağlanmamış |
| ~~**E-04**~~ → **KAPANDI (2026-08-03)** | ~~Library validation-run HTTP route düzeyinde test yok, frontend testi sıfır~~ → route düzeyi 9 test + frontend 15 test + 1 E2E journey | §G-04 | ~~Route sözleşmesi regresyona açık~~ |
| **E-05** | ESP soft-delete → yeni resolution vakası **hiçbir testte yok** | §G-01 | Kusur landed edilirken fark edilmedi |
| **E-06** | Klavye gezinimi sayfa başına denenmemiş (E2E'de **1** akış testi) | `e2e/specs/14-keyboard-flow.spec.ts` | WCAG 2.1.1 kapsamı dar |
| **E-07** | Strategy config alanları OpenAPI'de yayımlanmıyor (`same_candle_entry_exit`, `stop_trigger_requirement` → `docs/openapi.json`'da 0 hit; draft body'ler serbest biçimli) | `components.schemas` yalnız `Create/Patch/Save/ClearStrategyDraftBody` | Strateji sözleşmesi drift guard'ın koruması dışında |

---

## 11. Production hardening requirements

| # | Gereksinim | Current | Risk |
|---|---|---|---|
| **H-01** | SAST / CodeQL / semgrep | **YOK** | Kod düzeyi zafiyet CI'da yakalanmıyor |
| **H-02** | Secret scanning (gitleaks vb.) | **YOK** | Sızmış credential CI'da yakalanmıyor |
| **H-03** | Container image scan | **YOK** (`docker` job yalnız build) | Base image CVE'leri görünmez |
| **H-04** | CORS: `"*"` yasağı **yalnız** `ENTROPIA_ENV=production` dalında | `config/settings.py:146-169`. Karşılaştır: `_restrict_dev_auth_to_local` (`:131-144`) `!= "local"` kullanır — daha sıkı | `staging` profili `API_CORS_ORIGINS=*` + `allow_credentials=True` ile açılabilir |
| **H-05** | Performance / Lighthouse / yük kapısı | **YOK** (bilinçli ertelenmiş, `a11y_ci_ratchet_and_adjudication.md:265-267`) | Performans regresyonu ölçülmüyor |
| **H-06** | Observability (metrik/trace/log assertion) CI kapısı | **YOK** | Telemetri regresyonu görünmez |
| **H-07** | Backup/restore CI'da doğrulanmıyor | script + runbook var (`scripts/backup*.sh`, `restore.sh`, `docs/BACKUP_DR.md`), workflow yok | Restore yolu ancak elle denendiğinde bilinir |

---

## 12. Signed deviations

### D-10 — 45 accent-mavi düğüm (A11Y-01), **İMZALI KALICI SAPMA**

| | |
|---|---|
| Onaylayan | **alimirbagirzade (product owner)** |
| Tarih | **2026-07-30** |
| Kayıt | `docs/implementation/a11y_ci_ratchet_and_adjudication.md:208-219` |
| Kapsam | 45 düğüm — `33 × #ffffff on #00a9e8` + `12 × #00a9e8 on #ffffff`, hepsi **2.67:1** |
| Karar | Seçenek (i): kalıcı sapma. V18 imza mavisi korunur. |

**Bu bir uyumluluk iddiası DEĞİLDİR.** WCAG 2.2 AA **1.4.3 karşılanmıyor**; ürün bu ölçüt
için uyumlu olarak pazarlanamaz. Yeni veya artan ihlaller CI ratchet'ini kırmaya devam eder.

**Karıştırılmaması gereken dört ayrı eksen:**

1. **axe ratchet** — otomatik, CI'da bloklayıcı, **VAR**
2. **Screen-reader audit (A-08)** — insan, **YAPILMADI** (§17)
3. **Low-vision contrast uyumu** — **KARŞILANMIYOR** (D-10)
4. **PO signed deviation** — **VAR** (D-10)

(1) (3)'ü kapatmaz. (2) (3)'ü kapatmaz. (4) teknik PASS değildir.

**Tespit edilen drift:** `frontend/e2e/a11y-baseline.json` içindeki
`adjudication.color-contrast` metni hâlâ *"OPEN product-owner decision … until it is
signed"* diyor; `provenance.measured_at` = `2026-07-29T11:36:50Z`, yani imzadan **bir gün
önce**. Baseline JSON bir **production/CI artefaktıdır** — bu PR'da **değiştirilmedi**;
takip maddesi olarak §18'e yazıldı.

---

## 13. Deliberate Future Dev boundaries

Bunlar **implementation eksikliği değildir**; kapsam dışı verilmiş kararlardır.

| Sınır | Kayıt |
|---|---|
| Retention auto-purge | doc 20 §16 — "Production V1'de kapalı" |
| LLM generation | Future-Dev; V1 yalnız deterministik native-plan modülü üretir/çalıştırır |
| Graphic View renderer | doc 22 — V18 statik placeholder |
| Capability matrix `future_dev` (22 girdi) | Engine fail-closed; Ready Check `STRATEGY_CAPABILITY_NOT_IN_BUILD` blocker'ı verir; UI seçeneği görünür-disabled render eder |

---

## 14. Not-a-gap corrections

### N-01 · Agent runtime provisioning — **NOT A GAP**

İki kimlik **bilinçli olarak ayrıdır**:

| | `agent_alpha` | `alpha-agent` |
|---|---|---|
| Ne | Agent **principal** | Agent **runtime** |
| Depo | `principals.principal_id` (+ `agents` child) | `agent_runtime.agent_id` (singleton PK) |
| Tanım | `apps/seed.py:51` `DEFAULT_AGENT_ID` (env: `SEED_AGENT_ID`); ayna `jobs/agent_executor.py:76` | `domain/agent_lab/enums.py:112` `ALPHA_AGENT_ID` |
| Kim üretir | **yalnız** `python -m entropia.apps.seed` (`seed.py:217-219`) | **yalnız** `alembic/versions/0016_analysis_lab.py:251-261` `op.bulk_insert` |
| Rol | authz aktörü + audit atfı | operasyonel runtime satırı (mode/status/OCC) |

**Fresh `alembic upgrade head` runtime satırını OLUŞTURUR.** `0016` aynı `upgrade()` içinde
`agent_runtime` tablosunu yaratır ve singleton'ı koşulsuz `bulk_insert` eder; `0016` lineer
zincirdedir (`down_revision = 0015_arrange_metrics_export`, `0017` üzerine bağlanır); sonraki
hiçbir migration onu silmez.

Ayrım şema düzeyinde **zorunlu**: `0017:37-38` `agent_tool_call.agent_id → agent_runtime.agent_id`
ile `actor_principal_id → principals.principal_id` **iki ayrı FK hedefi**. Aynı ayrım
`task_directive`'te de var (`0016:99-101`). Kod bunu yorumla da bildiriyor
(`agent_executor.py:73-76`).

> **Yeni AgentRuntime provisioning sistemi ÖNERİLMEDİ ve production kodu değiştirilmedi.**
> Tek kalan iş **coverage**: fresh-install acceptance testi (§E-02).

### N-02 · S5b conflict-matrix "eksikleri" — **NOT A GAP** (stale token adları)

`docs/POST_V1_SPEC_GAP_BACKLOG_ROUND3.md:44` beş token'ı "hepsi 0 hit" diye açık gösteriyor.
2026-08-03 ölçümü (belgenin **kendi** komutu):

```
stop_mode                0
any_active_rule          0
all_active_rules         0
multiple_stops           0
same_candle_entry_exit   4
timeframe_mode          18
custom_sequence         21
```

**Sıfır hit'ler, davranışın yokluğu değil, ad değişikliğidir.** Sevk edilmiş adlar:

| Spec adı (doc 02) | Sevk edilmiş alan | Yer |
|---|---|---|
| Stop Mode / Stop Trigger Requirement (`stop.mode`) | `stop_trigger_requirement: Literal["any_active","all_active"]` | `domain/strategy/config.py:632` |
| "Any Active Stop Rule Triggers Stop" | değer `any_active` | `config.py:632`; engine `execution/fills.py:567` |
| "All Active Stop Rules Must Trigger Stop" | değer `all_active` | `fills.py:568` `if requirement == "all_active" and set(triggered) != enabled_keys` |
| Multiple Stops (`multipleStopsConflict`) | `stop_conflict_resolution` (`most_conservative`, `first_trigger_wins`, `priority_order`, `record_all`) | `config.py:641-658`; engine `fills.py:572,599,604` |
| Same Candle Entry / Exit | `same_candle_entry_exit` | `config.py:1047`; engine `engine.py:1834` |
| Stop + Exit | `stop_exit_conflict` | `config.py:1030` |

**S5c** (`timeframe_mode` 18 / `custom_sequence` 21) ve **S5d** (`logic_blocks`, 39 hit +
`tests/integration/test_logic_based_stop.py`, compiler `compiler.py:286-294`, readiness
`validators.py:677`, indicator plan `queries/indicator_plan.py:136`) da **landed**.

**Sonuç: S5 b/c/d'nin üçü de current main'de kapalıdır.** Round-3 backlog'un
"🔴 GERÇEKTEN AÇIK" bölümü tamamen stale'dir ve bu PR'da işaretlendi.

> Bu, promptun *"route/enum/DTO/test adı bulunması functional completion kanıtı sayılmaz"*
> kuralının **tersidir ve aynı derecede bağlayıcıdır**: token yokluğu da davranış yokluğu
> kanıtı değildir. Boşluk iddiası çağrı zincirinden doğrulanmalıdır.

### N-03 · Historical pinned revision okunabilirliği — **doğru davranış**

Soft-delete edilmiş bir ESP'nin **geçmişte pinlenmiş** revision'ının manifest üzerinden
okunabilir kalması kusur değildir; `test_acceptance_esp_package_gaps.py:250-257` ve
`test_esp_persistence.py:508-522` bunu sabitler. Kusur yalnız **YENİ** resolution'dır (§G-01).

### N-04 · Results History `display_title` — kusur DEĞİL (bilinçli terk)

Backend alanı hâlâ üretiyor ama sayfa render etmiyor; regresyon testi bunu kilitliyor.
Kalıntı **Panel Logs**'tadır (§G-06), Results History'de değil.

### N-05 · Domain-command parity ≠ Tool Gateway parity

Strategy ve Trading Signal domain komutlarının **tamamı** vardır. Bu, §G-03'ü **kapatmaz**
ve onun yerine raporlanamaz.

---

## 15. Stale documents repaired

| Dosya | Stale iddia | Current gerçek |
|---|---|---|
| `README.md:49` | Alembic head `0035_portfolio_rules`; ≈1841 backend / ≈577 frontend (2026-07-22) | head **`0043_i08_registry_strategy_fks`** (43 migration); **2886** backend / **673** frontend *collected* (2026-08-03) |
| `docs/CODEMAPS/README.md:12,14,15` | head `0040` (40 migration); 102 tablo; 135 FK | **`0043`** (43 migration); **104** tablo; **140** FK |
| `docs/implementation/entropia_v18_remediation_status.md:53-56` | head `0040`; ≈2538 backend passed; vitest 622/622 | head **`0043`**; **2886** collected; vitest **673** collected |
| `docs/POST_V1_SPEC_GAP_BACKLOG_ROUND3.md:40-56` | "🔴 GERÇEKTEN AÇIK: S5 b/c/d" | **üçü de landed** (§N-02) — 2026-08-03 tazeleme banner'ı eklendi |
| `docs/audit/acceptance_id_map.md §A` | 2026-07-28 sayıları | 2026-08-03 yeniden ölçüm bölümü eklendi (§H); §A–§G tarihsel kayıt olarak **değiştirilmedi** |
| `CLAUDE.md §Current position` | PR #513 açık iş gibi; #514 açık takip gibi; vitest 654; backend 2538/2712 | #513/#516/#517 **merged**; #514 **yanlışlıkla kapalı → yeniden açıldı**; sayılar tazelendi |
| `docs/implementation/v18_final_acceptance.md` | A-08 takibi "#514'te açık" | #514 kapatılmıştı; bu PR'da yeniden açıldı ve durum kaydedildi |

**Kural olarak yapılmayanlar:** tarihsel gövdeler değiştirilmedi (yalnız üstlerine tarihli
uyarı eklendi); kapanmış iş yeniden açılmadı; açık iş kapalı gösterilmedi; test sayısı
tahmin edilmedi; Future Dev implementation eksikliği sayılmadı; signed deviation teknik
PASS gibi gösterilmedi.

---

## 16. Open PR and issue truth

| Olgu | Değer (2026-08-03) |
|---|---|
| **Açık PR** | **0** |
| **Açık issue (denetim başında)** | **0** |
| Son merged PR | #517 (07-30), #516 (07-30), #513 (07-30), #511 (07-30), #509 (07-29), #508, #507, #505, #504, #503, #502, #501, #500, #499, #498 |
| Kapalı issue | #515 (07-30, F-7 Embedded raw pkgrev — **gerçekten fixed**, §8), **#514 (07-30 — kanıtsız kapatılmış)** |

**#514 bu PR'da YENİDEN AÇILDI.** Gerekçe §17.

---

## 17. Human-only gates

### A-08 — insan ekran-okuyucu kabulü: **AÇIK**

Issue #514 exit criteria'sı (kendi gövdesinden):

> *"All four exit criteria in the checklist are satisfied and evidence (auditor, versions,
> date, findings) is committed. An agent or automated scan must not close this issue on its own."*

Repository'de aranan kanıt (`grep -ril -E "NVDA|VoiceOver|JAWS|screen.reader" docs/`):

| Exit kriteri | Durum | Kanıt |
|---|---|---|
| NVDA + Firefox + Windows sonucu | **YOK** | `docs/implementation/a11y_screen_reader_audit_checklist.md:38` — `SR-1 … ☐ yapılmadı` |
| VoiceOver + Safari + macOS sonucu | **YOK** | `:39` — `SR-2 … ☐ yapılmadı` |
| Denetçi adı / rolü | **YOK — açıkça atanmamış** | `:28` — `**ATANMADI.** Atama ve kanıt takibi: GitHub #514.` |
| Sürüm bilgileri | **YOK** | tek sürüm string'i boş şablon içindeki `NVDA 2026.x` placeholder'ı (`:91`) |
| 22 sayfa matrisi | **BOŞ** | `:44` bölüm başlığı var, doldurulmuş sonuç tablosu yok |
| 10 kritik akış | **YAPILMADI** | `:64-73` yapılacaklar listesi; B-1 açıkça *"duyuru doğrulanmadı"* |
| Findings + retest | **YOK** | yalnız boş kayıt şablonu `:89-98`; `grep -rn "SR-BULGU" docs/` → **tek hit, o da `SR-BULGU-nn` şablon satırı** |

Belgenin kendi kapanış hükmü (`:100-109`):

> *"Bu dört madde sağlanana kadar A-08 **AÇIK**tır ve hiçbir belge onu Complete gösteremez."*

Belge otomasyonun neden yerine geçmediğini de yazıyor (`:7-22`): *"axe-core, Playwright ve
Lighthouse **DOM'u** denetler… Bu denetim bir **insana** düşer. Bir agent bunu yaptığını
iddia edemez."*

**Karar:** insan kanıtı yoktur → A-08 `Complete`/`PASS` **yazılmadı**; **issue #514 yeniden
açıldı** ve kısa, tarafsız bir yorum eklendi. Issue bu veya sonraki otomatik agent
oturumunda **kapatılmayacaktır**.

> #514 zaten bir kez bu sebeple yeniden açılmıştı — issue'daki mevcut yorum
> (*"Reopened after the acceptance PR merge: this issue is intentionally the remaining
> human-only release gate."*) buna tanıktır; buna rağmen 2026-07-30T19:05:32Z'de yeniden
> kapatılmış. Bu, tekrarlayan bir stale-truth kalıbıdır.

### Diğer insan kapıları

| Kapı | Durum |
|---|---|
| Low-vision contrast (WCAG 1.4.3) | **KARŞILANMIYOR** — D-10 imzalı sapma (§12). A-08 bunu **kapatmaz**, ayrı eksendir. |
| Sayfa başına klavye gezinimi | Denenmedi (§E-06) |
| Restore tatbikatı | Runbook var, CI kanıtı yok (§H-07) |

---

## 18. Ordered next slices

| Sıra | Slice | Kapsam | Neden bu sırada |
|---|---|---|---|
| **1** | **ADIM 2 — `fix/esp-lifecycle-safe-resolution`** | `queries/esp.py::resolve_embedded_dependency` root `deletion_state` + `lifecycle_state` okusun; yeni resolution'da soft-deleted/deprecated root `RESOLVER_NOT_ACTIVE` versin; historical pinned revision okunabilirliği **korunsun**; regresyon testi + PC-19 acceptance tag'i | Tek doğru davranış boşluğu ki **kod yayımlanmış docstring'iyle çelişiyor** (§G-01) |
| ~~2~~ | ~~`feat/library-request-validation-ui`~~ → **LANDED** | Library sayfasına gerçek action + mutation hook + queued/running/passed/failed durumu + route düzeyi backend testi (9) + frontend testi (15) + E2E journey; ayrıca 201 gövdesi `PackageValidationRunAcceptedResponse` ile şemada yayımlandı | Backend hazır; yalnız yüzey eksikti (§G-04) — **kapandı 2026-08-03** |
| ~~3~~ | ~~`feat/esp-export-contract-evidence`~~ → **LANDED as `feat/esp-export-contract-v2`** | Export manifest'ine adapter/warm-up/timing/repaint/validation-run/validator-version/vectors/evidence + canonical key & signature **alan olarak** eklendi; ayrıca `export_schema_version`/`exporter_version`, immutable contract'tan ayrılmış `registry_observation` ve v1/v2 import uyumluluğu (bilinmeyen versiyon fail-closed) | Export'un yeniden üretilebilirliği (§G-02) — **kapandı 2026-08-03**, bkz. `docs/audit/esp_export_schema_v2.md` |
| 4 | `fix/i16a-panel-logs-display-title` + `diagnosticWarningLabel` eşlemesi | Panel Logs sentetik başlığı kaldır; `portfolio_curve_sequential_not_unified_clock` için insan-okur etiket | İki küçük sunum kalıntısı (§G-06, §G-07) |
| 5 | `test/fresh-install-acceptance` | `alembic upgrade head` üzerinden `agent_runtime` singleton'ını **assert eden** test | Coverage boşluğu; production değişikliği YOK (§N-01, §E-02) |
| 6 | `feat/agent-tool-gateway-strategy-trading-signal` | 10 literal Tool Gateway aracı + scope/handler/test | Domain komutları hazır; Gateway yüzeyi eksik (§G-03) |
| 7 | `ci/security-hardening` | SAST + secret scan + image scan; CORS `"*"` yasağını non-local profillere genişlet | Production hardening (§H-01…H-04) |
| 8 | `docs/a11y-baseline-adjudication-refresh` | `a11y-baseline.json` `adjudication` metnini D-10 imzasıyla uyumla | CI artefaktı, ayrı PR (§12) |
| — | **A-08 (#514)** | **İNSAN** — agent kapatamaz | §17 |
| — | Unified-clock portfolio co-simulation (§G-05) | Ürün kararı gerektirir; V1'de L4 ile bildirilmiş sınırdır | Engine değişikliği; bu denetimin kapsamı dışında |

---

## 19. Evidence limitations

Bu belgenin **dürüst sınırları**:

1. **Test sayıları `collected`'dir, `passed` değildir.** Tam backend/frontend suite bu
   docs-only oturumda koşulmadı. "Yeşil" iddiası için otorite CI'dır:
   `gh run list --branch main --limit 1`.
2. **Migration up/down/up ispatı koşulmadı.** `alembic heads` script dizininden okunur;
   bu adımda DB'ye karşı upgrade/downgrade yapılmadı. Fresh-install davranışı `0016`'nın
   **kodundan** okunmuştur (§N-01), canlı bir DB'den değil.
3. **E2E / visual / a11y suite koşulmadı.** CI kapılarının varlığı ve bloklayıcı olduğu
   workflow dosyalarından okundu; koşu sonuçları CI'dadır.
4. `main` bu worktree'de checkout **edilemedi** (başka worktree tutuyor); ağaç `origin/main`
   SHA'sından oluşturulan branch üzerinden doğrulandı — içerik özdeştir.
5. Docs 06, 08, 09 acceptance tablolarında ID kolonu **yok**, bu yüzden acceptance
   scanner'a görünmezler (`acceptance_id_map.md §C`). %80 rakamı bu üç sayfayı kapsamaz.
6. Bu belgedeki her boşluk iddiası **çağrı zinciri** ile doğrulanmıştır; token grep'i tek
   başına kanıt sayılmamıştır (§N-02'nin doğrudan sebebi).
