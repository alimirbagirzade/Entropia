# Post-V1 — Kickoff / Resume

> **Amaç:** V1 kapandı (Stage 0–8 COMPLETE). Bu doküman post-V1 durumunu, aday iş listesini
> ve temiz oturumda yapıştırılacak resume prompt'u içerir.

## Durum (2026-07-02, Parquet Slice A sonrası)

- **V1 ROADMAP COMPLETE + Auth/IdP + Parquet batch (INF-12 Slice A) landed.** Parquet PR
  **#41** merged → `main` = **`3deee28`** (**git log ile doğrula** — özet stale-by-default).
  Alembic head = **`0021_local_auth`** (Slice A migration'sız). Test tabanı: **818 yeşil**
  (813 + Parquet'te 5). Tüm sayfa spec'leri (doc 01–22) + e2e integration flows + hardening +
  yerel auth + Parquet batch data-access landed.
- **Test-infra notu:** integration testleri her testte şemayı drop/create eder — aynı lokal
  Postgres'i paylaşan İKİ oturum birbirini bozar. İzole DB kullan:
  `TEST_DATABASE_URL=postgresql+asyncpg://entropia:entropia@localhost:5432/entropia_auth`.

## Parquet Slice A'nın bıraktıkları (reuse anchor'ları — PR #41)

- **Streaming:** `infrastructure/s3/parquet_stream.py` — `stream_processed_batches(object_key)`
  (S3 `download_fileobj` → `SpooledTemporaryFile` 32MB spill-to-disk cap → pyarrow
  `ParquetFile.iter_batches`); `iter_parquet_batches(source)` saf lokal I/O (infra'sız
  unit-test edilebilir batching kontratı); `DEFAULT_BATCH_SIZE = 8_192`. YALNIZ worker
  plane — API process'inde asla çalışmaz.
- **Query:** `application/queries/market_bars.py` — `resolve_bar_source(session,
  market_revision_id=...)` → `BarSourceRef` (frozen dataclass: entity_id / revision_id /
  object_key / content_digest / size_bytes / row_count; işlenmemiş revizyonda
  `NotFoundError`) + `iter_bar_batches(source)` — **Slice B engine bunun üstüne kurulacak.**
  Read-only; 'latest'e asla dokunmaz (doc 15 no-latest-leak).
- **Repo:** `repositories/market_data.py::get_processed_asset_for_revision` — sıralama
  kontratı: re-processing ayrı tx'te koşar (farklı ULID timestamp); aynı-ms ULID tiebreak
  non-deterministik — belgelenmiş limit, deterministik testle sabitlendi (review bulgusu
  ampirik DOĞRULANDI).
- **mypy:** `pyarrow.*` untyped override'lara eklendi (stub yayınlanmıyor).

## Auth/IdP'nin bıraktıkları (reuse anchor'ları — PR #38)

- **Transport:** `apps/api/deps.py` — `AUTH_MODE=dev|session` (`dev` default: `X-Actor-Id`
  hattı testler için aynen durur); `bearer_token(request)`; `_session_mode_actor` (Bearer →
  `auth_sessions` lookup → rol HER istekte registry'den taze, M1 §4.2); servis hattı
  `ENTROPIA_SERVICE_TOKEN` + non-human principal zorunlu (`SERVICE_LINE_FORBIDDEN`).
- **Komutlar:** `application/commands/auth.py` — `sign_up`/`login`/`logout` + `hash_token`;
  tek 401 `INVALID_CREDENTIALS` + `DUMMY_HASH` timing pad (`shared/passwords.py`, argon2id).
- **Tablolar:** `human_credentials`, `auth_sessions` (token yalnız SHA-256 digest;
  `models/auth.py`, `repositories/auth.py`, migration `0021_local_auth`).
- **L1 dersi (tekrar doğrulandı):** principal→human_user→credential AYNI flush'ta FK ihlali
  veriyor — her FK adımında ayrı `flush()` (bkz. `sign_up`).

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
  / Metrics middleware; bucket key artık Authorization digest tercih eder);
  `infrastructure/observability/metrics.py` + `GET /v1/metrics`.
- **8a fix:** `readiness_check._resolve_strategy_payload` — Strategy editör mirror'ı typed
  revision payload'a çözülür (editör yolu artık RUN'a ulaşır).
- **Coordinator plan adımı** artık CR-08 exposure tüketiyor (`run_coordinator_cycle` →
  `exposed_tools` summary + `agent_task_created` payload).

## Post-V1 aday işler (öncelik sırası önerisi)

1. ~~**Auth/IdP**~~ ✅ **LANDED (PR #38)** — yerel auth (argon2id + opaque session +
   `AUTH_MODE` + servis hattı). Not: production'a geçişte `AUTH_MODE=session` +
   `ENTROPIA_SERVICE_TOKEN` set edilmeli; ilk Admin hesabı provisioning'i henüz yok
   (signup hep `user` — Admin'e yükseltme için DB-seed veya gelecek dilim).
2. **Gerçek backtest engine** — ~~Slice A: Parquet batch data-access (INF-12)~~ ✅
   **LANDED (PR #41)**; sırada **Slice B: bar-replay engine + rule set** — deterministik
   stub (`domain/backtest/engine.py`) → `iter_bar_batches` üstünde gerçek market-data
   simülasyonu (anchor: `market_bars.py`).
3. **Frontend entegrasyonu** — SSE tüketimi (yeni taksonomi), `/metrics` dashboard'ları,
   Trash/Panel/Manual/Future-Dev shell'leri; artık `/v1/auth/*` login akışı da hazır.
4. **Create Package gerçek candidate generation** — stub generator → LLM/derleme hattı.
5. **Capability aktivasyonları** — Future Dev slotlarını Placeholder'dan çıkarma
   (graphic_view ilk aday; gate'ler + Admin transition zaten hazır).
6. **Deferred takipleri** — `dispatch_tool_call` status-key gölgelemesi (chip açıldı);
   retention-window auto-purge; data-queue auto-redelivery; SSE HTTP-streaming e2e;
   audit log-projection indexleri (6b'de KISS ertelenmişti); ilk-Admin provisioning.

## Yöntem (değişmedi)

- Workflow KULLANMA — doğrudan yaz; YENİ dosya Bash heredoc, mevcut dosya Edit 4-fact.
- `cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy src` +
  izole DB'de `uv run pytest --no-cov -q` (**818 yeşil kalmalı**); migration gerekirse
  `0022_*` (→0021) up/down/up + parity + L1 FK proof.
- code-reviewer subagent → CRITICAL/HIGH **AMPİRİK DOĞRULA** (8a: 0; 8b: 2/2 GERÇEK;
  auth: 0; parquet: 1/1 GERÇEK — oran değişken, HER ZAMAN doğrula) → commit (conventional,
  attribution YOK) →
  PR → `gh pr checks --watch` → merge için kullanıcıya sor. Türkçe, MALİYET BİLİNÇLİ.

---

## ⤵️ YENİ OTURUMDA YAPIŞTIR (resume prompt)

```
Entropia — post-V1: V1 tamam + Auth/IdP (PR #38) + Parquet batch Slice A (PR #41 merged,
main=3deee28, git log ile DOĞRULA). 818 test yeşil; alembic head 0021_local_auth (Slice A
migration'sız). Önce docs/POST_V1_KICKOFF.md + docs/STAGE2_HANDOFF.md ("Post-V1 — Parquet
batch data-access landed" + "Next: post-V1 (continued)") oku.

Kalan aday işler (öncelik): (2b) backtest engine Slice B — bar-replay engine + rule set
(domain/backtest/engine.py deterministik stub → iter_bar_batches üstünde gerçek simülasyon;
anchor: application/queries/market_bars.py — BarSourceRef / resolve_bar_source /
iter_bar_batches, infrastructure/s3/parquet_stream.py), (3) frontend SSE/metrics/login
entegrasyonu, (4) CP gerçek candidate generation, (5) capability aktivasyonları,
(6) deferred listesi (+ ilk-Admin provisioning).
Hangisinden başlayacağımızı bana sor; kapsamı birlikte netleştirelim.

YÖNTEM: Workflow KULLANMA; YENİ dosya heredoc, mevcut dosya Edit 4-fact; cd backend;
ruff+format+mypy+pytest (izole DB: TEST_DATABASE_URL=...entropia_auth; 818 yeşil kalmalı);
migration 0022_* (→0021) up/down/up + parity + L1 FK proof; code-reviewer → CRITICAL/HIGH
AMPİRİK DOĞRULA → commit (attribution YOK) → PR → checks watch → merge kullanıcıda.
Türkçe, MALİYET BİLİNÇLİ. Kapanışta: handoff + kickoff + CLAUDE.md + memory (ecc + claude-mem).
```
