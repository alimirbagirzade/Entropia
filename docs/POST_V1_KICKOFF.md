# Post-V1 — Kickoff / Resume

> **Amaç:** V1 kapandı (Stage 0–8 COMPLETE). Bu doküman post-V1 durumunu, aday iş listesini
> ve temiz oturumda yapıştırılacak resume prompt'u içerir.

## Durum (2026-07-02)

- **V1 ROADMAP COMPLETE.** Stage 8b (hardening) PR **#35** merged → `main` = **`bc38ca6`**
  (**git log ile doğrula** — özet stale-by-default). Alembic head = **`0020_future_dev`**
  (Stage 8 migration eklemedi). Test tabanı: **801 yeşil** (789 önceki + 8a'da 10 + 8b'de 10 — 8a
  öncesi 781). Tüm sayfa spec'leri (doc 01–22) + e2e integration flows + hardening landed.
- **Test-infra notu:** integration testleri her testte şemayı drop/create eder — aynı lokal
  Postgres'i paylaşan İKİ oturum birbirini bozar. İzole DB kullan:
  `TEST_DATABASE_URL=postgresql+asyncpg://entropia:entropia@localhost:5432/entropia_stage8`.

## Stage 8'in bıraktıkları (reuse anchor'ları)

- **e2e şablonlar:** `tests/integration/test_e2e_pipeline.py` (`_ready_pipeline` — gerçek
  ingest→publish→compose→allocate zinciri; INF-04/05 + CR-03 assert desenleri),
  `test_e2e_agent_loop.py` (UI'sız agent döngüsü), `test_gateway_parity.py`
  (insan-komutu ↔ agent-tool denklik deseni + capability walk).
- **Fan-out:** `application/jobs/outbox_relay.py` (`relay_unpublished` scheduler checkpoint,
  `fetch_events_after` SSE cursor feed, `outbox_lag_seconds`); `apps/api/sse.py`
  (`SseHub`, `run_outbox_poller`, `sse_event_name` taksonomisi). SSE kayıp-toleranslı (INF-11).
- **Scheduler:** `application/jobs/maintenance.py` (`recover_stale_jobs` INF-09,
  `redeliverable_queued_jobs` INF-03); `apps/scheduler/__main__.py` `ACTOR_BY_QUEUE`
  (data kuyruğu bilinçli hariç — multi-actor).
- **Hardening:** `apps/api/hardening.py` (SecurityHeaders / RateLimit opt-in `RATE_LIMIT_ENABLED`
  / Metrics middleware); `infrastructure/observability/metrics.py` + `GET /v1/metrics`
  (golden signals + `entropia_jobs_depth` + `entropia_outbox_lag_seconds` +
  `entropia_job_lease_age_seconds`).
- **8a fix:** `readiness_check._resolve_strategy_payload` — Strategy editör mirror'ı typed
  revision payload'a çözülür (editör yolu artık RUN'a ulaşır).
- **Coordinator plan adımı** artık CR-08 exposure tüketiyor (`run_coordinator_cycle` →
  `exposed_tools` summary + `agent_task_created` payload).

## Post-V1 aday işler (öncelik sırası önerisi)

1. **Auth/IdP** — `X-Actor-Id` dev-mode kimliği gerçek authentication ile değiştir
   (Master §20'de bilinçli ertelenen güvenlik kararı; rate limiter anahtarı da bundan beslenir).
2. **Gerçek backtest engine** — deterministik stub (`domain/backtest/engine.py`) →
   gerçek market-data simülasyonu; Parquet/batch data pipeline (INF-12).
3. **Frontend entegrasyonu** — SSE tüketimi (yeni taksonomi), `/metrics` dashboard'ları,
   Trash/Panel/Manual/Future-Dev shell'leri.
4. **Create Package gerçek candidate generation** — stub generator → LLM/derleme hattı.
5. **Capability aktivasyonları** — Future Dev slotlarını Placeholder'dan çıkarma
   (graphic_view ilk aday; gate'ler + Admin transition zaten hazır).
6. **Deferred takipleri** — `dispatch_tool_call` status-key gölgelemesi (chip açıldı);
   retention-window auto-purge; data-queue auto-redelivery; SSE HTTP-streaming e2e;
   audit log-projection indexleri (6b'de KISS ertelenmişti).

## Yöntem (değişmedi)

- Workflow KULLANMA — doğrudan yaz; YENİ dosya Bash heredoc, mevcut dosya Edit 4-fact.
- `cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy src` +
  izole DB'de `uv run pytest --no-cov -q` (**801 yeşil kalmalı**); migration gerekirse
  `0021_*` (→0020) up/down/up + parity + L1 FK proof.
- code-reviewer subagent → CRITICAL/HIGH **AMPİRİK DOĞRULA** (8a: 0 bulgu; 8b: 2/2 GERÇEK
  — oran değişken, HER ZAMAN doğrula) → commit (conventional, attribution YOK) → PR →
  `gh pr checks --watch` → merge için kullanıcıya sor. Türkçe, MALİYET BİLİNÇLİ.

---

## ⤵️ YENİ OTURUMDA YAPIŞTIR (resume prompt)

```
Entropia — post-V1: V1 tamam (Stage 0–8, PR #35 merged, main=bc38ca6, git log ile DOĞRULA).
801 test yeşil; alembic head 0020_future_dev. Önce docs/POST_V1_KICKOFF.md +
docs/STAGE2_HANDOFF.md ("Stage 8b landed" + "Next: post-V1") oku.

Aday işler (kickoff'taki öncelik sırası): (1) Auth/IdP (X-Actor-Id → gerçek auth, Master §20),
(2) gerçek backtest engine + Parquet pipeline (INF-12), (3) frontend SSE/metrics entegrasyonu,
(4) CP gerçek candidate generation, (5) capability aktivasyonları, (6) deferred listesi.
Hangisinden başlayacağımızı bana sor; kapsamı birlikte netleştirelim.

YÖNTEM: Workflow KULLANMA; YENİ dosya heredoc, mevcut dosya Edit 4-fact; cd backend;
ruff+format+mypy+pytest (izole DB: TEST_DATABASE_URL=...entropia_stage8; 801 yeşil kalmalı);
migration 0021_* (→0020) up/down/up + parity; code-reviewer → CRITICAL/HIGH AMPİRİK DOĞRULA →
commit (attribution YOK) → PR → checks watch → merge kullanıcıda. Türkçe, MALİYET BİLİNÇLİ.
Kapanışta: handoff + kickoff + CLAUDE.md + memory (ecc graph + claude-mem).
```
