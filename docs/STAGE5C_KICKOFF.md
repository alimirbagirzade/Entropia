# Stage 5c — Arrange Metrics (doc 17) + doc-15 deferred (Export + artifact cursor-query) — Kickoff / Resume Handoff

> **Amaç:** Yeni/temiz bir oturumda kaldığımız yerden devam. Yapıştırmaya hazır başlangıç prompt'u aşağıda. Her kapanışta güncellenir.

## Nerede kaldık (2026-07-01)

- **Stage 3 (01–05) + 4a (13) + 4b (14) + 5a (RUN&Results core, doc 15) + 5b-1 (Results History, doc 16) TAMAMLANDI.** 5b-1 PR **#18** MERGED → `main` = **`bd4aff4`** (**git log ile doğrula** — bu özet stale-by-default). Alembic head = **`0014_backtest_run_result`** (5b-1 salt-okuma; migration YOK).
- **Sıradaki = Stage 5c — Arrange Metrics (doc 17) + doc-15 deferred'lar (Export + artifact cursor-query).** Branch: `feat/stage-5c-arrange-metrics`. İlk yeni migration = **`0015_*`** (→0014).

## Stage 5b-1'in bıraktıkları (Stage 5c bunları tüketir — REUSE anchors)

- **Results History read-model hazır (salt-okuma, mutasyon yok):**
  - `domain/backtest/history.py`: `SORT_REGISTRY` (6 canonical sort + V18 alias'ları), opak keyset cursor encode/decode (`{sort,value,result_id}`; tamper → `CURSOR_INVALID`), compare context extractor + diff (pin'lenmemiş alan ⇒ "Not available", L4 — asla fabricate etme).
  - `application/queries/results_history.py`: `list_backtest_results` (SQL visibility owner-or-Admin, canonical `metric_value.value` NULLS LAST + `result_id` tie-break, LEFT OUTER join → metric'siz sonuç null-tail'de kalır), `compare_backtest_results` (tam 2 distinct visible).
  - `apps/api/routes/results_history.py`: `GET /backtest-results`, `POST /backtest-results/compare`, `POST /backtest-results/{id}/delete` (5a `soft_delete_backtest_result` REUSE).
  - `shared/errors.py`: `INVALID_SORT_KEY`, `CURSOR_INVALID`, `COMPARE_REQUIRES_TWO_DISTINCT_RESULTS`.
- **5a tabanı (5c doğrudan tüketir):** `domain/backtest/metrics.DEFAULT_METRICS` (9 canonical metric registry — **Arrange Metrics `metric_definition` kaynağı**), `metric_value` (9 canonical, L4 never-0), `backtest_result` (immutable, `deletion_state`+`row_version`), `result_summary`, heavy-artifact tabloları (`result_equity_point`/`trade_ledger_row`/`signal_event`/`diagnostic_artifact` — **artifact cursor-query kaynağı**), `result_manifest_snapshot` (`manifest_hash` provenance — **export provenance kaynağı**), `bt_repo` read helper'ları.

## Stage 5c tasarım (doc 17 + doc-15 deferred)

- **doc 17 Arrange Metrics — PRESENTATION-ONLY (kritik):** `MetricValue`/manifest'i **ASLA mutate etmez**; yalnız görünüm profilini yönetir.
  - **`metric_definition` registry:** 5a `DEFAULT_METRICS`'ten beslenir (id, label, unit, availability, format). `GET /metric-definitions?availability=` (canonical liste + hangi metric hangi sonuç sınıfında N/A).
  - **`result_view_metric_profile_root/revision`:** entity_registry-anchored, **immutable revisions** (config JSONB = seçili+sıralı metric set + display opts, `config_hash`). Apply/Lock/Unlock akışı; head pointer + `row_version`. Komutlar: `create_metric_profile_revision` (immutable append), `apply/lock/unlock` (state advance → root `row_version` bump + FOR-UPDATE lock, L7).
  - **Resolved profile & result metrics:** resolved-profile `GET` (aktif profile → metric sırası/görünürlüğü), `GET /backtest-results/{id}/metrics` (result'ın `metric_value`'larını profile'a göre **sunar** — hesaplama YOK, 5a değerlerini hydrate eder; eksik = N/A never-0, L4).
- **doc-15 deferred:**
  - **Export:** `RequestResultExport` komutu + `export_artifact` tablosu (schema-versioned export bir result'tan; **provenance = source `manifest_hash`** — `result_manifest_snapshot`'tan pinlenir). Ağır iş → generic `jobs` + queue (`export_job` gerekirse, CR-09). Object-storage key + checksum + schema_version + row_count (DB yalnız metadata tutar; artifact immutable/checksummed).
  - **Artifact cursor-query:** `GET /backtest-results/{id}/artifacts/{type}` — ledger/equity/signal/diagnostic drill-down, **server-side ordering + opaque cursor** (5b-1 keyset pattern'i REUSE et), **root≠leg double-count YOK**. Salt-okuma.
- **YENİ tablolar:** `metric_definition`, `result_view_metric_profile_root/revision`, `export_artifact` (+ `export_job` gerekirse). Migration **`0015_*`** (→0014).
- **Trash (result restore/purge) Stage 6'ya (doc 20) ait — 5c DEĞİL.**

## REUSE (yeniden yazma yok)

- **5b-1:** `list_backtest_results` visibility+keyset shape (artifact cursor-query için pattern), `history.py` cursor encode/decode yardımcıları, `routes/results_history.py` (yeni okuma endpoint'leri buraya eklenebilir).
- **5a:** `DEFAULT_METRICS` (metric_definition seed), `metric_value`/`backtest_result`/`result_summary`/heavy-artifact tabloları, `result_manifest_snapshot` (export provenance), `bt_repo` read helper'ları.
- **Çekirdek:** `run_idempotent` (per-principal), `audit_repo.add_audit_event/add_outbox_event`, `request_context`, `ensure_can_edit/can_view`, `enum_column`, `new_id`, generic `jobs`+queue (export job), `RowVersionConflictError`(409)/`ValidationError`(422), `AppError.http_status`, entity_registry Root + immutable revision zinciri.

## Yöntem (3b–5b dersi — birebir uygula)

- **Workflow KULLANMA** — doğrudan yaz, 5a/5b pattern'i birebir (module-level async command'lar, tek-tx no-commit, `run_idempotent`, `session.refresh(with_for_update=True)`, `_audit_and_outbox`).
- **GateGuard:** İlk Bash öncesi 2 fact sun (oturumda bir kez). Mevcut dosya **Edit/Write** → 4-fact fact-force (importers / etkilenen public API / data schema / user request verbatim). YENİ dosyaları **Bash heredoc** (`cat > f << 'EOF'`) ile yaz → gate-free. **NOT:** branch komutundaki `cd` cwd'yi repo root'a kaydırabilir — backend dosyası yazmadan önce `cd backend` teyit et.
- **zsh word-split:** ruff/mypy'ı tüm proje (`.`/`src`) üzerinde çalıştır, dosya listesi değil.
- **Lokal doğrula:** `cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy src && DATABASE_URL=... uv run pytest --no-cov -q` + **HER yeni `create_*` için L1 FK insert-order proof** + **alembic 0015 up/down/up** (`LC_ALL=en_US.UTF-8`, proof öncesi `DROP SCHEMA public CASCADE; CREATE SCHEMA public;`) + **migration↔model kolon parity** (information_schema vs Base.metadata). Yerel Postgres **:5432** (entropia/entropia). Integration conftest `create_all` ile şema kurar; testte `DATABASE_URL` ver.
- **code-reviewer subagent → CRITICAL/HIGH'ı AMPİRİK DOĞRULA** (5a/5b'de HIGH'ların çoğu yanlış çıktı). Gerçek olanı düzelt → commit (conventional, **attribution YOK**) → PR → `gh pr checks <n> --watch` → **YEŞİL olunca merge için kullanıcıya sor** (self-merge bloklu).
- **Türkçe konuş, autonomous ilerle, MALİYET BİLİNÇLİ.** Her checkpoint memory'ye (ecc + claude-mem). **HER KAPANIŞTA:** sıradaki kickoff + resume prompt + `docs/STAGE2_HANDOFF.md` + `CLAUDE.md` "Current position" güncelle.

---

## ⤵️ YENİ OTURUMDA YAPIŞTIR (resume prompt)

```
Entropia — Stage 5c başlat: Arrange Metrics (doc 17, presentation-only) + doc-15
deferred (RequestResultExport + export_artifact + artifact cursor-query). Önce bağlamı
oku, working loop'a göre ilerle. Branch feat/stage-5c-arrange-metrics AÇ. MALİYET
BİLİNÇLİ ol.

Durum: Stage 3 (01–05) + 4a (13) + 4b (14) + 5a (doc 15, PR #16) + 5b-1 (Results
History, doc 16, PR #18) TAMAMLANDI. main = bd4aff4 (git log ile doğrula). Alembic
head 0014. İlk yeni migration 0015_*.

ÖNCE OKU (otorite sırası): (1) docs/STAGE5C_KICKOFF.md — bu dilimin tam handoff'u.
(2) docs/STAGE2_HANDOFF.md → "Stage 5b-1 landed" + "Next: Stage 5c" + dersler. (3)
docs/STAGE_BUILD_PLAN.md → "Stage 5" (17 tablolar + acceptance). (4) docs/spec/
17_..Arrange_Metrics.. + 15_..RUN_ve_Backtest_Results.. (Export + artifact-query
deferred kısımları) → spec'i TAM çıkar. (5) 5a/5b-1 kodu: domain/backtest/{metrics,
history}, application/queries/{backtest_run,results_history}, infrastructure/postgres/
models|repositories/backtest, apps/api/routes/results_history.

TASARIM: doc17 Arrange Metrics = PRESENTATION-ONLY (MetricValue/manifest ASLA mutate
ETMEZ): metric_definition (5a DEFAULT_METRICS'ten) + result_view_metric_profile_root/
revision (immutable, Apply/Lock/Unlock); GET /metric-definitions?availability=,
resolved profile GET, POST /metric-profiles/{id}/revisions, GET /backtest-results/
{id}/metrics (5a değerlerini hydrate — hesaplama yok, eksik=N/A never-0). doc15
deferred: RequestResultExport + export_artifact (provenance=source manifest_hash,
object-storage key+checksum+schema_version+row_count) + GET /backtest-results/{id}/
artifacts/{type} cursor-pagination (5b-1 keyset REUSE, root≠leg double-count yok).
YENİ tablolar metric_definition, result_view_metric_profile_root/revision,
export_artifact (+export_job gerekirse). Migration 0015_*.

REUSE: 5b-1 list_backtest_results visibility+keyset shape + cursor helpers +
results_history route; 5a DEFAULT_METRICS (metric_definition seed), metric_value/
backtest_result/result_summary/heavy-artifact tabloları, result_manifest_snapshot
(export provenance), bt_repo read helpers; run_idempotent, audit/outbox,
request_context, ensure_can_edit/can_view, enum_column, new_id, generic jobs+queue
(export).

YÖNTEM: Workflow KULLANMA — doğrudan yaz, 5a/5b pattern birebir. YENİ dosyaları Bash
heredoc (gate-free); mevcut dosya Edit/Write 4-fact fact-force. cd backend teyit et.
ruff/mypy tüm proje üzerinde (zsh word-split). Lokal doğrula (ruff+format+mypy+pytest
DATABASE_URL ile + HER yeni create_* için L1 FK proof + alembic 0015 up/down/up
LC_ALL=en_US.UTF-8 DROP SCHEMA önce + migration↔model parity). Yerel Postgres :5432.
code-reviewer subagent → CRITICAL/HIGH AMPİRİK DOĞRULA → gerçek olanı düzelt → commit
(conventional, attribution yok) → PR → gh pr checks --watch, YEŞİL olunca merge için
bana sor. Türkçe, autonomous, MALİYET BİLİNÇLİ. Her checkpoint memory'ye (ecc +
claude-mem). HER KAPANIŞTA: sıradaki kickoff + resume prompt + STAGE2_HANDOFF.md +
CLAUDE.md güncelle.
```
