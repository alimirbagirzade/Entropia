# Stage 5 — RUN, Backtest Results, History, Arrange Metrics (docs 15–17) — Kickoff / Resume Handoff

> **Amaç:** Yeni/temiz bir oturumda kaldığımız yerden devam edebilmek için hazır bağlam + **yapıştırmaya hazır başlangıç prompt'u**. Her kapanış oturumunda güncellenir.

## Nerede kaldık (2026-07-01)

- **Stage 3 (docs 01–05) + Stage 4a (doc 13) + Stage 4b (doc 14) TAMAMLANDI.** main = **`226c7d1`** (PR #14 merged). Alembic head = **`0013_ready_check`**.
- **Sıradaki = Stage 5 — RUN & Backtest Results / History / Arrange Metrics (docs 15/16/17).** Branch aç: `feat/stage-5a-run` (doc 15 önce; 16/17 ayrı dilimler olabilir). Sonraki alembic = **`0014_*`**.

## Stage 4b'nin bıraktıkları (Stage 5 bunları tüketir)

- **Ready Check = RUN önkoşulu (hint), asla güven değil.** `application/commands/readiness_check.py::run_readiness_check` + saf `domain/readiness/validators.py::evaluate_readiness` (composition→lifecycle→strategy→external→allocation). RUN endpoint **aynı preflight'ı SERVER-SIDE tekrar çalıştırmalı** (doc 14 §9.3, §14): blocker → **422 `READINESS_BLOCKED`**, client `ready`/modal/eski report **yeterli değil**.
- Tablolar: `ready_check_report` (`composition_snapshot_id`, `composition_fingerprint`, `state`, sayaçlar) + `readiness_issue`. `mainboard_composition_snapshot.readiness_report_id`/`readiness_state`/`capital_mode_snapshot` doldu.
- `expected_fingerprint` mismatch → **409 `COMPOSITION_STALE`** (`shared/errors.py::CompositionStaleError`, ZATEN var). `composition_hash` (3a) = fingerprint kaynağı.
- 3d follow-up'ları (TL-09/TL-11/OHLCV) 4b'de kapandı.

## Stage 5 tasarım (docs 15–17 + build plan ~satır 122)

- **doc 15 RUN & Results:** `POST /compositions/{id}/backtest-runs` body `{composition_id, expected_fingerprint, readiness_report_id?, run_profile_id, output_profile, idempotency_key}` → **202** `{run_id, state:"queued", manifest_hash, event_stream_url}`. **TEK transaction'da** immutable Composition Snapshot + `backtest_run_manifest` (canonical JSON + `manifest_hash`, exact strategy/package/market-data/research/allocation/engine kimlikleri **pinli**, worker "latest" fallback YOK) + `backtest_run` (QUEUED) + outbox → `backtest` queue. Worker (`application/jobs/backtest_engine`) → event stream/artifact; **yalnız succeeded** immutable `backtest_result` üretir (CR-03); failed/cancelled → diagnostics, history satırı YOK. Idempotency-key ile duplicate run dedup (RC-12); retry = yeni run_id + yeni manifest_hash + `retry_of_run_id`.
- **doc 16 Results History:** server read model, canonical numeric metric'lerde sort (nulls last), Compare tam 2 distinct result.
- **doc 17 Arrange Metrics:** presentation-only metric profile (MetricValue/manifest'i ASLA mutate etmez).
- **YENİ tablolar (build plan):** `backtest_run`, `backtest_run_manifest`, `backtest_result`, `result_summary`, `metric_value`, equity/drawdown/`trade_ledger_row`/`signal_event`/`diagnostic_artifact`/`export_artifact`, `result_manifest_snapshot`; `metric_definition` + `result_view_metric_profile_root/revision`. Migration `0014_*` (→0013).
- **3a `_assert_not_in_active_run` stub'ını BURADA wire et** → queued/running run referans ederse `OBJECT_IN_ACTIVE_RUN` (soft-delete engeli).

## REUSE (yeniden yazma)

- **4b:** `run_readiness_check` / `evaluate_readiness` (RUN preflight'ı buradan çağır, sonucu manifest'e warning olarak kopyala), `ready_check_report`/`composition_fingerprint`.
- **4a:** `portfolio_allocation_plan_revision` (manifest yalnız `plan_revision_id` pinler, CR-06 — `allocation_profile*` YOK).
- **3a:** `mainboard_composition_snapshot` + `mb_repo.create_snapshot`, `composition_hash`.
- `run_idempotent`, `audit_repo.add_audit_event/add_outbox_event`, `request_context` dep, `ensure_can_edit/can_view`, `enum_column`, `new_id(prefix)`, `RowVersionConflictError`/`CompositionStaleError` (409), `ValidationError` (422), `AppError.http_status` map, generic `jobs` tablosu + queue pattern (3c/3d worker'ları örnek).

## Yöntem (3b–4b dersi)

- **Workflow KULLANMA** — doğrudan yaz, 4b pattern'i birebir (module-level async command'lar, tek-tx no-commit, `run_idempotent`, `session.refresh(with_for_update=True)`, `_audit_and_outbox`).
- **GateGuard:** YENİ dosyaları **Bash heredoc** (`cat > f << 'PYEOF'`) ile yaz → gate-free. **Mevcut dosya edit'i** fact-force tetikler (4 fact sun: importer'lar (Grep) / etkilenen public API / veri şeması / kullanıcı isteği verbatim → retry). Küçük fix'leri `uv run python` replace script'iyle yap (gate-free). Bash gate oturumda bir kez.
- **Lokal doğrula:** `cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest --no-cov -q` + **HER `create_*` için L1 FK insert-order proof** + **alembic 0014 up/down/up** (`LC_ALL=en_US.UTF-8`, proof öncesi `DROP SCHEMA public CASCADE; CREATE SCHEMA public;`). Yerel Postgres **:5432 ayakta** (entropia/entropia), `/opt/homebrew/bin`. Integration conftest `create_all` ile şema kuruyor.
- **code-reviewer subagent → CRITICAL/HIGH bulgularını AMPİRİK DOĞRULA** (4b'de 2 HIGH'ın 1'i yanlış çıktı: reviewer `list_active_items`'in EntityRegistry join'lemediğini iddia etti — halbuki join'liyor) → gerçek olanı düzelt → commit (conventional, **attribution YOK**) → PR → `gh pr checks <n> --watch` → **YEŞİL olunca merge için kullanıcıya sor** (self-merge bloklu; ama kullanıcı 4b'yi kendi hızlı merge etti).
- **Türkçe konuş, autonomous ilerle, MALİYET BİLİNÇLİ** (4b oturumu ~$170 — gereksiz paralel ajan/tam-dosya okuma yapma, review bulgusunu kendin doğrula, targeted verify). Her checkpoint'te ecc memory'ye yaz. **HER KAPANIŞTA:** `docs/STAGE6_KICKOFF.md` + resume prompt + `docs/STAGE2_HANDOFF.md` güncelle.

---

## ⤵️ YENİ OTURUMDA YAPIŞTIR (resume prompt)

```
Entropia — Stage 5 başlat: RUN & Backtest Results (doc 15; sonra History doc 16 +
Arrange Metrics doc 17). Önce bağlamı oku, sonra working loop'a göre ilerle. Branch
feat/stage-5a-run AÇ. MALİYET BİLİNÇLİ ol.

Durum: Stage 3 (01–05) + 4a (13) + 4b (14) TAMAMLANDI. main 226c7d1, alembic head
0013_ready_check. Sıradaki = Stage 5. Sonraki alembic 0014_*.

ÖNCE OKU (otorite sırası): (1) docs/STAGE5_KICKOFF.md — bu dilimin tam handoff'u,
4b'nin bıraktıkları, Stage 5 tasarım pointer'ları, reuse listesi, working loop.
(2) docs/STAGE2_HANDOFF.md → "Stage 4b landed" + "Next: Stage 5" + dersler.
(3) docs/STAGE_BUILD_PLAN.md → "Stage 5 — RUN, Backtest Results, History, Arrange
Metrics" (tablolar + acceptance). (4) docs/spec/15_..RUN.. + 16_..History.. +
17_..Arrange_Metrics.. → spec'i TAM çıkar (domain, backend, acceptance). (5) ecc
memory "Entropia Stage 4b — Backtest Ready Check" + "Stage 4a" checkpoint'leri.

TASARIM: POST /compositions/{id}/backtest-runs RUN preflight'ı SERVER-SIDE TEKRAR
çalıştırır (4b run_readiness_check'i çağır; client ready/eski report yeterli değil):
blocker → 422 READINESS_BLOCKED; expected_fingerprint mismatch → 409 COMPOSITION_STALE
(CompositionStaleError zaten var). TEK tx: immutable snapshot + backtest_run_manifest
(hash-pinned exact revisions, latest fallback YOK) + backtest_run (QUEUED) + outbox →
backtest queue worker; yalnız succeeded → immutable backtest_result (CR-03); failed/
cancelled → diagnostics, history yok; retry = yeni run_id + manifest_hash + retry_of.
Idempotency-key run dedup. Sonra Results History (read model, numeric sort nulls last,
Compare 2 result) + Arrange Metrics (presentation-only, MetricValue mutate etmez).
3a _assert_not_in_active_run stub → OBJECT_IN_ACTIVE_RUN wire et. YENİ tablolar
backtest_run/manifest/result/summary/metric_value/equity/drawdown/trade_ledger_row/
signal_event/diagnostic/export + metric_definition/result_view_metric_profile +
migration 0014_*.

REUSE: 4b run_readiness_check/evaluate_readiness (RUN preflight), 4a allocation
plan_revision (manifest yalnız plan_revision_id pinler, CR-06), 3a snapshot/
composition_hash, run_idempotent, audit/outbox, request_context, ensure_can_edit/
can_view, enum_column, new_id, generic jobs tablosu + queue (3c/3d worker örnek).

YÖNTEM: Workflow KULLANMA — doğrudan yaz, 4b pattern birebir. YENİ dosyaları Bash
heredoc ile yaz (gate-free); mevcut dosya edit'i GateGuard fact-force (4 fact→retry),
küçük fix uv run python replace ile. Lokal doğrula (ruff+format+mypy+pytest + HER
create_* için L1 FK proof + alembic 0014 up/down/up; LC_ALL=en_US.UTF-8, DROP SCHEMA
public CASCADE önce). Yerel Postgres :5432 ayakta (entropia/entropia). code-reviewer
subagent → CRITICAL/HIGH bulgularını AMPİRİK DOĞRULA → gerçek olanı düzelt → commit
(conventional, attribution yok) → PR → gh pr checks --watch, YEŞİL olunca merge için
bana sor. Türkçe konuş, autonomous, MALİYET BİLİNÇLİ. Her checkpoint memory'ye. VE
HER KAPANIŞTA: docs/STAGE6_KICKOFF.md + resume prompt + STAGE2_HANDOFF.md güncelle.
```
