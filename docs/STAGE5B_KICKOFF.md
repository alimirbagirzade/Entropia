# Stage 5b — Results History + Arrange Metrics (docs 16–17) + doc-15 deferred — Kickoff / Resume Handoff

> **Amaç:** Yeni/temiz bir oturumda kaldığımız yerden devam. Yapıştırmaya hazır başlangıç prompt'u aşağıda. Her kapanışta güncellenir.

## Nerede kaldık (2026-07-01)

- **Stage 3 (01–05) + 4a (13) + 4b (14) + 5a (RUN & Results core, doc 15) TAMAMLANDI.** Stage 5a PR **#16** (CI yeşil). Merge sonrası `main` = PR #16 merge commit'i (**git log ile doğrula** — bu özet stale-by-default). Alembic head = **`0014_backtest_run_result`**.
- **Sıradaki = Stage 5b — Results History (doc 16) + Arrange Metrics (doc 17) + doc-15 deferred'ları.** Branch: `feat/stage-5b-results-history` (doc 16 önce; 17 ayrı dilim olabilir). Sonraki alembic = **`0015_*`**.

## Stage 5a'nın bıraktıkları (Stage 5b bunları tüketir)

- **RUN→Result core hazır.** `application/commands/backtest_run.py` (request/retry/soft-delete), `application/jobs/backtest_engine.py` (worker: manifest-resolution check → latest fallback YOK → FAILED; succeeded → immutable result), `application/queries/backtest_run.py` (get_run/get_result), `apps/api/routes/backtest.py`.
- **Tablolar (migration 0014):** `backtest_run` (mutable lifecycle root), `backtest_run_manifest` (immutable hash-pinned; `execution_key` reproducible / `manifest_hash` run-unique), `backtest_result` (immutable, `deletion_state` flag + `row_version`), `result_summary`, `metric_value` (9 canonical, L4 never-0), `result_equity_point`, `trade_ledger_row`, `signal_event`, `diagnostic_artifact`, `result_manifest_snapshot`.
- **domain/backtest/**: `enums` (BacktestRunState, RunFailureCode, MetricAvailability, RUN_ACTIVE/TERMINAL/RETRYABLE), `manifest.build_run_manifest`, `engine.run_engine` (**V1 stub** — execution_key'den deterministik; gerçek engine gelince yalnız engine.py/metrics.py değişir), `metrics` (DEFAULT_METRICS 9'lu registry + `derive_metric_values`).
- **Engine V1 STUB:** gerçek market-data simülasyonu yok; deterministik placeholder üretir. Results History/Compare bu stub çıktısı üzerinde çalışır — gerçek sayı beklenmez, determinizm beklenir.
- 3a `_assert_not_in_active_run` → **`OBJECT_IN_ACTIVE_RUN`** wire edildi (queued/running run pinli root'un soft-delete'ini bloklar).

## Stage 5b tasarım (docs 16–17 + doc-15 deferred)

- **doc 16 Results History:** server read-model over `backtest_result` (yalnız `deletion_state='active'` + succeeded). `GET /backtest-results?sort=<enum>&cursor&limit` — **canonical numeric metric'lerde sort, nulls last** (metric_value.value join). `POST .../compare` — **tam 2 distinct visible result**. `POST .../{id}/delete` (If-Match + idempotency) — 5a `soft_delete_backtest_result`'ı REUSE et (yeni komut yazma). History satırı = succeeded only; failed/cancelled ASLA görünmez (CR-03).
- **doc 17 Arrange Metrics:** **presentation-only** metric profile — MetricValue/manifest'i ASLA mutate etmez. `metric_definition` registry (5a `domain/backtest/metrics.DEFAULT_METRICS`'ten besle) + `result_view_metric_profile_root/revision` (immutable revisions, Apply/Lock/Unlock). `GET /metric-definitions?availability=`, resolved profile GET, `POST /metric-profiles/{id}/revisions`, `GET /backtest-results/{id}/metrics`.
- **doc-15 deferred'lar:** `RequestResultExport` + `ExportArtifact`/`ExportJob` (result artifact'ten schema-versioned export, provenance = source manifest_hash); heavy artifact **cursor-pagination** query endpoint'leri (`GET /backtest-results/{id}/artifacts/{type}` — ledger/equity/signal drill-down, server-side ordering, root≠leg double-count yok). Result **Trash** restore/purge → Stage 6 (doc 20).
- **YENİ tablolar:** `metric_definition`, `result_view_metric_profile_root/revision`, `export_artifact` (+ `export_job` gerekirse). Migration `0015_*` (→0014).

## REUSE (yeniden yazma)

- **5a:** `soft_delete_backtest_result` (History delete = bu), `bt_repo.get_result/get_summary/list_metric_values/get_manifest_snapshot/count_artifacts`, `domain/backtest/metrics.DEFAULT_METRICS` (Arrange Metrics registry kaynağı), `backtest_result`/`metric_value` (History sort/filter kaynağı).
- `run_idempotent`, `audit_repo.add_audit_event/add_outbox_event`, `request_context`, `ensure_can_edit/can_view`, `enum_column`, `new_id`, `RowVersionConflictError`(409)/`ValidationError`(422), `AppError.http_status`, generic `jobs` + queue (export job için).

## Yöntem (3b–5a dersi)

- **Workflow KULLANMA** — doğrudan yaz, 5a pattern'i birebir (module-level async command'lar, tek-tx no-commit, `run_idempotent`, `session.refresh(with_for_update=True)`, `_audit_and_outbox`).
- **GateGuard:** YENİ dosyaları **Bash heredoc** (`cat > f << 'PYEOF'`) ile yaz → gate-free. **Mevcut dosya edit'leri** için `uv run python` replace script (gate-free). İlk Bash öncesi 2 fact sun. Bash gate oturumda bir kez. **NOT:** branch komutundaki `cd` cwd'yi repo root'a kaydırabilir — dosya yazmadan önce `cd backend` teyit et (5a'da bir kez repo-root `src/`'e yazıldı, taşındı).
- **zsh word-split:** `$VAR` unquoted split olmaz — ruff/mypy'ı tüm proje (`.`/`src`) üzerinde çalıştır, dosya listesi değil.
- **Lokal doğrula:** `cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy src && DATABASE_URL=... uv run pytest --no-cov -q` + **HER `create_*` için L1 FK insert-order proof** + **alembic 0015 up/down/up** (`LC_ALL=en_US.UTF-8`, proof öncesi `DROP SCHEMA public CASCADE; CREATE SCHEMA public;`) + **migration↔model kolon parity** (information_schema vs Base.metadata). Yerel Postgres **:5432** (entropia/entropia). Integration conftest `create_all` ile şema kurar; testte `DATABASE_URL` ver.
- **code-reviewer subagent → CRITICAL/HIGH'ı AMPİRİK DOĞRULA** (5a'da 2 HIGH'ın 2'si de yanlış çıktı: VARCHAR taşması yok/precedent var; "stuck in RUNNING" yanlış — rollback). Gerçek olanı düzelt (5a'da redelivery idempotency). commit (conventional, **attribution YOK**) → PR → `gh pr checks <n> --watch` → **YEŞİL olunca merge için kullanıcıya sor** (self-merge bloklu).
- **Türkçe konuş, autonomous ilerle, MALİYET BİLİNÇLİ** (5a oturumu ~$153). Her checkpoint memory'ye. **HER KAPANIŞTA:** sıradaki kickoff + resume prompt + `docs/STAGE2_HANDOFF.md` güncelle.

---

## ⤵️ YENİ OTURUMDA YAPIŞTIR (resume prompt)

```
Entropia — Stage 5b başlat: Results History (doc 16) + Arrange Metrics (doc 17) +
doc-15 deferred (Export + artifact cursor-query). Önce bağlamı oku, working loop'a
göre ilerle. Branch feat/stage-5b-results-history AÇ. MALİYET BİLİNÇLİ ol.

Durum: Stage 3 (01–05) + 4a (13) + 4b (14) + 5a (RUN&Results core, doc 15, PR #16)
TAMAMLANDI. main = PR #16 merge (git log ile doğrula). Alembic head 0014. Sonraki 0015_*.

ÖNCE OKU (otorite sırası): (1) docs/STAGE5B_KICKOFF.md — bu dilimin tam handoff'u.
(2) docs/STAGE2_HANDOFF.md → "Stage 5a landed" + "Next: Stage 5b" + dersler. (3)
docs/STAGE_BUILD_PLAN.md → "Stage 5" (16/17 tablolar + acceptance). (4) docs/spec/
16_..Results_History.. + 17_..Arrange_Metrics.. → spec'i TAM çıkar. (5) 5a kodu:
domain/backtest/*, application/{commands,jobs,queries}/backtest_run|engine,
infrastructure/postgres/models|repositories/backtest.

TASARIM: doc16 History = server read-model over backtest_result (active+succeeded),
canonical numeric metric sort nulls last, Compare tam 2 distinct; delete = 5a
soft_delete_backtest_result REUSE. doc17 Arrange Metrics = presentation-only
(MetricValue/manifest mutate ETMEZ): metric_definition (5a DEFAULT_METRICS'ten) +
result_view_metric_profile_root/revision (immutable, Apply/Lock/Unlock). doc15
deferred: RequestResultExport + export_artifact (provenance=source manifest_hash),
artifact cursor-pagination query. Migration 0015_*.

REUSE: 5a soft_delete_backtest_result, bt_repo read helpers, DEFAULT_METRICS,
backtest_result/metric_value; run_idempotent, audit/outbox, request_context,
ensure_can_edit/can_view, enum_column, new_id, generic jobs+queue (export).

YÖNTEM: Workflow KULLANMA — doğrudan yaz, 5a pattern birebir. YENİ dosyaları Bash
heredoc (gate-free); mevcut dosya edit'leri uv run python replace. cd backend teyit
et (branch cd'si cwd kaydırabilir). ruff/mypy tüm proje üzerinde (zsh word-split).
Lokal doğrula (ruff+format+mypy+pytest DATABASE_URL ile + HER create_* için L1 FK
proof + alembic 0015 up/down/up LC_ALL=en_US.UTF-8 DROP SCHEMA önce + migration↔
model parity). Yerel Postgres :5432. code-reviewer subagent → CRITICAL/HIGH AMPİRİK
DOĞRULA → gerçek olanı düzelt → commit (conventional, attribution yok) → PR → gh pr
checks --watch, YEŞİL olunca merge için bana sor. Türkçe, autonomous, MALİYET
BİLİNÇLİ. Her checkpoint memory'ye. HER KAPANIŞTA: STAGE6_KICKOFF.md + resume prompt
+ STAGE2_HANDOFF.md güncelle.
```
