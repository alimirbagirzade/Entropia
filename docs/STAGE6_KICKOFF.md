# Stage 6 — Analysis Lab (18) + Panel/Management/Logs (19) + Trash (20) — Kickoff / Resume Handoff

> **Amaç:** Yeni/temiz bir oturumda kaldığımız yerden devam. Yapıştırmaya hazır başlangıç prompt'u aşağıda. Her kapanışta güncellenir.

## Nerede kaldık (2026-07-01)

- **Stage 3 (01–05) + 4a (13) + 4b (14) + 5a (doc 15) + 5b-1 (Results History, doc 16) + 5c (Arrange Metrics doc 17 + doc-15 deferred export/artifact) TAMAMLANDI.** 5c PR **#20** MERGED → `main` = **`9e29c23`** (**git log ile doğrula** — bu özet stale-by-default). Alembic head = **`0015_arrange_metrics_export`**. İlk yeni migration = **`0016_*`** (→0015).
- **Sıradaki = Stage 6 — Analysis Lab (18) + Panel/Management/Logs (19) + Trash (20).** `STAGE_BUILD_PLAN.md` "Stage 6" tablosu otoritedir; alt-dilim sırası doc 18 → 19 → 20 (asla atlanmaz). Branch `feat/stage-6a-analysis-lab` (ilk dilim).

## Stage 5c'nin bıraktıkları (Stage 6 bunları tüketebilir — REUSE anchors, tam sembol adlarıyla)

- **Arrange Metrics presentation plane (salt-görünüm, mutasyon yok):**
  - `domain/metric_profile/{enums,registry,profile}.py`: `ProfileScope`/`MetricAvailabilityStatus`, `METRIC_REGISTRY` (9 selectable + 18 future) + `DEFAULT_SELECTED_METRIC_CODES` + `REGISTRY_VERSION`, `normalize_selection`/`compute_config_hash`/`transition_reason`/`RegistrySnapshot`.
  - `application/commands/metric_profile.create_metric_profile_revision` (Apply/Lock/Unlock tek komut, `SYSTEM_DEFAULT_PROFILE_ID` fork, `expected_profile_revision_id` OCC, lock precondition, IntegrityError→`MetricProfileStaleError`).
  - `application/queries/metric_profile.{list_metric_definitions,get_resolved_metric_profile,get_result_metrics}` (hydrate-by-profile, eksik=`not_computed` never-0, L4).
  - `infrastructure/postgres/{models,repositories}/metric_profile.py`: `MetricDefinition`, `ResultViewMetricProfileRoot/Revision`; `mp_repo.{list_definitions,load_registry_snapshot,get_personal_profile,create_profile_root,create_revision,max_revision_no}`.
  - `apps/api/routes/metric_profile.py` (4 endpoint).
- **doc-15 deferred export/artifact plane:**
  - `domain/backtest/{artifacts,export}.py`: `ArtifactType`+opaque keyset cursor (`encode/decode_artifact_cursor`, `normalize_artifact_type`, `SEQ_ORDERED_TYPES`), `ExportType`/`ExportFormat`+`build_object_key`/`compute_export_checksum`/`EXPORT_SCHEMA_VERSION`.
  - `application/commands/result_export.request_result_export` (synchronous V1, provenance=source `manifest_hash`, `run_idempotent`), `application/queries/result_artifacts.query_result_artifact` (cursor page).
  - `infrastructure/postgres/{models,repositories}/export.py` (`ExportArtifact`; `export_repo.{load_source_rows,create_export,get_export,list_exports}`) + `repositories/result_artifacts.py` (`page_artifacts`/`project_row`/`cursor_key_of`).
  - `apps/api/routes/result_export.py` (export POST + artifact drill-down GET).
- **Migration 0015** (→0014): `metric_definition` (seed 27), `result_view_metric_profile_root/revision`, `export_artifact`. enum_column (VARCHAR+CHECK, no CREATE TYPE).

## Stage 6 tasarım pointer'ları (build plan seviyesi — docs 18/19/20 spec'i TAM çıkar)

- **Analysis Lab (18):** `apps/agent_coordinator` runtime loop, `application/commands/agent_control`, Tool Gateway `application/jobs/agent_tools` (`agent`/`agent-high` queue). Endpoints: `GET /agent-workspace/overview`, `/agent-tasks[?status]`, `/agent-tasks/{id}`, `/hypotheses`, `/agent-events/stream` (SSE), `POST /lab/messages`, `/agent-directives` (202), `/agent-runtime/pause|resume` (202 Admin), `/agent-runs/{id}/stop` (202 Admin). Tablolar: `agent_runtime`, `agent_task`, `task_directive`, `agent_checkpoint`, `lab_message`, `hypothesis_artifact`, `artifact_link`, `agent_event`.
- **Panel/Management/Logs (19):** spec doc 19'u çıkar.
- **Trash (20):** result **restore/purge** (5a/5c'de deferred), profile-root soft-delete/restore (doc 17 §12 Admin-only). 5a `soft_delete_backtest_result` + `deletion` state machine + `TrashEntry`/`Tombstone` REUSE.

## REUSE (yeniden yazma yok)

- **Çekirdek:** `run_idempotent` (per-principal), `audit_repo.add_audit_event/add_outbox_event`, `request_context`/`RequestContext`, `require_authenticated`/`ensure_can_view`/`ensure_can_edit`/`require_admin`, `enum_column`, `new_id`, `TimestampMixin`, generic `jobs`+`enqueue_job`+queue, `RowVersionConflictError`(409)/`ValidationError`(422), `AppError.http_status`, entity_registry Root + immutable revision zinciri, opaque keyset cursor pattern (`domain/backtest/{history,artifacts}.py`).
- **Trash/deletion:** `domain/deletion/state_machine`, `models/deletion` (`TrashEntry`,`Tombstone`), `repositories/trash`, `application/commands/deletion` (`soft_delete`/`restore`/`request_purge`).

## Yöntem (3b–5c dersi — birebir uygula)

- **Workflow KULLANMA** — doğrudan yaz, 5a/5b/5c pattern'i birebir (module-level async command'lar, tek-tx no-commit, `run_idempotent`, `session.refresh(with_for_update=True)`, `_audit_and_outbox`).
- **GateGuard:** İlk Bash öncesi 2 fact; mevcut dosya Edit/Write → 4-fact (importers Grep / etkilenen public API / data schema / user request verbatim); YENİ dosyaları **Bash heredoc** (`cat > f << 'EOF'`) → gate-free. **`cd backend` teyit et** (branch/checkout cwd'yi repo root'a kaydırabilir).
- **zsh word-split:** ruff/mypy'ı tüm proje (`.`/`src`) üzerinde çalıştır.
- **Lokal doğrula:** `cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy src && DATABASE_URL=... uv run pytest --no-cov -q` + **HER yeni `create_*` için L1 FK insert-order proof** + **alembic 0016 up/down/up** (`LC_ALL=en_US.UTF-8`, proof öncesi `DROP SCHEMA public CASCADE; CREATE SCHEMA public;`) + **migration↔model kolon parity** (information_schema vs Base.metadata). Yerel Postgres **:5432** (entropia/entropia). Integration conftest `create_all` ile şema kurar; testte `DATABASE_URL` ver — **seed'li tablolar (ör. registry) testte manuel seed edilir**.
- **code-reviewer subagent → CRITICAL/HIGH'ı AMPİRİK DOĞRULA** (5a/5b/5c'de HIGH'ların çoğu yanlış/çürük çıktı). Gerçek olanı düzelt → commit (conventional, **attribution YOK**) → PR → `gh pr checks <n> --watch` → **YEŞİL olunca merge için kullanıcıya sor** (self-merge bloklu).
- **Türkçe konuş, autonomous ilerle, MALİYET BİLİNÇLİ.** Her checkpoint memory'ye (ecc + claude-mem). **HER KAPANIŞTA:** sıradaki kickoff + resume prompt + `docs/STAGE2_HANDOFF.md` + `CLAUDE.md` "Current position" güncelle.

---

## ⤵️ YENİ OTURUMDA YAPIŞTIR (resume prompt)

```
Entropia — Stage 6 başlat: Analysis Lab (doc 18) + Panel/Management/Logs (doc 19) +
Trash (doc 20). Önce bağlamı oku, working loop'a göre ilerle. İlk dilim = Analysis
Lab (doc 18); branch feat/stage-6a-analysis-lab AÇ. MALİYET BİLİNÇLİ ol.

Durum: Stage 3 (01–05) + 4a (13) + 4b (14) + 5a (doc 15) + 5b-1 (doc 16) + 5c
(Arrange Metrics doc 17 + doc-15 deferred export/artifact, PR #20) TAMAMLANDI. main =
9e29c23 (git log ile doğrula). Alembic head 0015. İlk yeni migration 0016_*.

ÖNCE OKU (otorite sırası): (1) docs/STAGE6_KICKOFF.md — bu dilimin tam handoff'u. (2)
docs/STAGE2_HANDOFF.md → "Stage 5c landed" + "Next: Stage 6" + dersler. (3)
docs/STAGE_BUILD_PLAN.md → "Stage 6" (18/19/20 tablolar + acceptance). (4) docs/spec/
18_..Analysis_Lab.. (+ 19, 20) → spec'i TAM çıkar. (5) 5a/5b/5c kodu: domain/backtest/
{metrics,history,artifacts,export}, domain/metric_profile/*, application/commands|
queries/{backtest_run,results_history,metric_profile,result_export,result_artifacts},
infrastructure/postgres/models|repositories/{backtest,metric_profile,export}, apps/api/
routes/{backtest,results_history,metric_profile,result_export}, domain/deletion +
repositories/trash + application/commands/deletion (Trash için).

TASARIM: doc18 Analysis Lab = agent runtime loop + agent_task/directive/checkpoint +
lab_message + hypothesis_artifact + agent_event (SSE); komutlar agent_control (+Admin
pause/resume/stop), Tool Gateway agent_tools job (agent/agent-high queue). doc20 Trash
= result restore/purge (5a/5c deferred) + profile-root soft-delete/restore (doc17 §12
Admin-only) — deletion state_machine + TrashEntry/Tombstone REUSE. YENİ tablolar spec'ten;
migration 0016_*.

REUSE: run_idempotent, audit/outbox, request_context, ensure_can_view/edit/require_admin,
enum_column, new_id, TimestampMixin, generic jobs+queue+enqueue_job, opaque keyset cursor
(domain/backtest/{history,artifacts}), entity_registry Root+immutable revision zinciri,
domain/deletion state_machine + models/deletion (TrashEntry,Tombstone) + repositories/trash
+ application/commands/deletion (soft_delete/restore/request_purge), 5a
soft_delete_backtest_result.

YÖNTEM: Workflow KULLANMA — doğrudan yaz, 5a/5b/5c pattern birebir. YENİ dosyaları Bash
heredoc (gate-free); mevcut dosya Edit/Write 4-fact fact-force. cd backend teyit et.
ruff/mypy tüm proje üzerinde. Lokal doğrula (ruff+format+mypy+pytest DATABASE_URL ile +
HER yeni create_* için L1 FK proof + alembic 0016 up/down/up LC_ALL=en_US.UTF-8 DROP SCHEMA
önce + migration↔model parity). Integration conftest create_all ile şema kurar (seed'li
tabloları testte manuel seed et). Yerel Postgres :5432. code-reviewer subagent →
CRITICAL/HIGH AMPİRİK DOĞRULA → gerçek olanı düzelt → commit (conventional, attribution yok)
→ PR → gh pr checks --watch, YEŞİL olunca merge için bana sor. Türkçe, autonomous, MALİYET
BİLİNÇLİ. Her checkpoint memory'ye (ecc + claude-mem). HER KAPANIŞTA: sıradaki kickoff +
resume prompt + STAGE2_HANDOFF.md + CLAUDE.md güncelle.
```
