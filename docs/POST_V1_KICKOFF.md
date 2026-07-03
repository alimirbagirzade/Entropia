# Post-V1 — Kickoff / Resume

> **Amaç:** V1 kapandı (Stage 0–8 COMPLETE). Bu doküman post-V1 durumunu, aday iş listesini
> ve temiz oturumda yapıştırılacak resume prompt'u içerir.

## Durum (2026-07-03, Backtest Engine Slice B sonrası)

- **V1 ROADMAP COMPLETE + Auth/IdP + Parquet batch (Slice A) + Bar-replay engine (Slice B) landed.**
  Slice B PR **#43** merged → `main` = **`fc746f8`** (**git log ile doğrula** — özet stale-by-default).
  Alembic head = **`0021_local_auth`** (Slice B migration'sız). Test tabanı: **822 yeşil**
  (818 + Slice B'de 4). Backtest track artık gerçek: deterministik stub yerine pinlenmiş market
  revizyonunun OHLCV bar'ları üzerinde tek-geçiş **bar-replay** simülasyonu koşuyor.
- **Test-infra notu:** integration testleri her testte şemayı drop/create eder — aynı lokal
  Postgres'i paylaşan İKİ oturum birbirini bozar. İzole DB kullan:
  `TEST_DATABASE_URL=postgresql+asyncpg://entropia:entropia@localhost:5432/entropia_auth`.

## Backtest Engine Slice B'nin bıraktıkları (reuse anchor'ları — PR #43)

- **Engine (pure):** `domain/backtest/engine.py` — `run_engine(*, strategy_config, bar_batches,
  execution_key, item_count=1) → EngineOutput`. DB/clock/randomness yok; `bar_batches`'i BİR kez
  akıtır. Frozen çıktı satırları `TradeRow` / `EquityPoint` / `SignalEventRow` / `EngineOutput`.
  **Gerçek** protection stop'lar — `_initial_static_stop` (percentage/absolute'ün en sıkısı),
  `_trail_pct`+`_effective_stop` (trailing), **intrabar** değerlendirme (long: `bar.low ≤ stop`;
  short: `bar.high ≥ stop`) → `stop_loss`; ters-breakout `_exit_proxy` → `exit_signal`; veri
  sonu kapanışı → `end_of_data` (açık pozisyon asla sarkmaz). Maliyet — `_cost_params` /
  `_effective_fill` (yarım-spread + slippage oranı + fill başına komisyon ×2 gidiş-dönüş).
- **Entry PROXY (dürüst sınır):** giriş hâlâ **breakout proxy** (`_BREAKOUT_WINDOW = 20` look-back;
  yeni pencere yükseğinde long, düşüğünde short; aynı-bar beraberliğinde long kazanır). İndikatör
  katmanı stub — diagnostics'te `entry_model = deterministic_bar_breakout_proxy_v1` etiketli. Yön
  kısıtı → `suppressed_entries` → tek `filtered_no_entry` sinyal olayı.
- **Sizing:** `_position_size` — açık `base_position_size`, yoksa all-in **notional**, `max(equity, 0)`
  clamp'li (bust hesap → size 0, **asla negatif değil** — negatif size sonraki tüm trade'lerin PnL
  işaretini ters çevirirdi; review CRITICAL, deterministik bust-safety testiyle sabitlendi).
  `risk_based_sizing` / `formula_based_sizing` **modellenmedi** → notional'a düşer + diagnostics'te
  `position_sizing_method_unsupported:<method>` uyarısı (L4 — gizlenmez).
- **Job:** `application/jobs/backtest_engine.py` — `run_backtest(..., stream_bars=iter_bar_batches)`;
  bar'lar **enjekte edilebilir** (default gerçek S3-backed streamer) → integration testleri
  resolve → replay → persist'i uçtan uca sürer. Fail yolları: market revizyonu yok/çözülemez →
  `ASSET_UNAVAILABLE`; engine exception'ı → `ENGINE_ERROR` (ikisi de audit'lenir).
- **Manifest:** `domain/backtest/manifest.py` — `ENGINE_VERSION = "backtest-engine-v1-bar-replay"`
  (`execution_key` reprodüksiyon hash'ine katılır → aynı kompozisyon aynı sonucu üretir; INF-05).
- **Açık uçlar (dürüst, ertelendi):** `summary["timeframe"]` hâlâ `None` (DataContext'te base
  timeframe yok — istenirse market-revision metadata'sından çözülebilir); `risk_based`/`formula_based`
  sizing yok (uyarır); **entry/exit indikatör compute sıradaki doğal dilim** — YALNIZ `engine.py`'deki
  entry/exit değerlendirmesi değişir, run/manifest/result sözleşmeleri sabit kalır.

## Parquet Slice A'nın bıraktıkları (reuse anchor'ları — PR #41)

- **Streaming:** `infrastructure/s3/parquet_stream.py` — `stream_processed_batches(object_key)`
  (S3 `download_fileobj` → `SpooledTemporaryFile` 32MB spill-to-disk cap → pyarrow
  `ParquetFile.iter_batches`); `iter_parquet_batches(source)` saf lokal I/O (infra'sız
  unit-test edilebilir batching kontratı); `DEFAULT_BATCH_SIZE = 8_192`. YALNIZ worker
  plane — API process'inde asla çalışmaz.
- **Query:** `application/queries/market_bars.py` — `resolve_bar_source(session,
  market_revision_id=...)` → `BarSourceRef` (frozen dataclass: entity_id / revision_id /
  object_key / content_digest / size_bytes / row_count; işlenmemiş revizyonda
  `NotFoundError`) + `iter_bar_batches(source)` — **Slice B engine bunun üstüne kuruldu.**
  Read-only; 'latest'e asla dokunmaz (doc 15 no-latest-leak).
- **Repo:** `repositories/market_data.py::get_processed_asset_for_revision` — sıralama
  kontratı: re-processing ayrı tx'te koşar (farklı ULID timestamp); aynı-ms ULID tiebreak
  non-deterministik — belgelenmiş limit, deterministik testle sabitlendi.

## Auth/IdP'nin bıraktıkları (reuse anchor'ları — PR #38)

- **Transport:** `apps/api/deps.py` — `AUTH_MODE=dev|session` (`dev` default: `X-Actor-Id`
  hattı testler için aynen durur); `bearer_token(request)`; `_session_mode_actor` (Bearer →
  `auth_sessions` lookup → rol HER istekte registry'den taze, M1 §4.2); servis hattı
  `ENTROPIA_SERVICE_TOKEN` + non-human principal zorunlu (`SERVICE_LINE_FORBIDDEN`).
- **Komutlar:** `application/commands/auth.py` — `sign_up`/`login`/`logout` + `hash_token`;
  tek 401 `INVALID_CREDENTIALS` + `DUMMY_HASH` timing pad (`shared/passwords.py`, argon2id).
- **Tablolar:** `human_credentials`, `auth_sessions` (token yalnız SHA-256 digest;
  `models/auth.py`, `repositories/auth.py`, migration `0021_local_auth`).
- **L1 dersi:** principal→human_user→credential AYNI flush'ta FK ihlali veriyor — her FK
  adımında ayrı `flush()` (bkz. `sign_up`).

## Stage 8'in bıraktıkları (reuse anchor'ları)

- **e2e şablonlar:** `tests/integration/test_e2e_pipeline.py` (`_ready_pipeline` — gerçek
  ingest→publish→compose→allocate zinciri; INF-04/05 + CR-03 assert desenleri; Slice B bunu
  gerçek bar-replay ile sürer), `test_e2e_agent_loop.py` (UI'sız agent döngüsü),
  `test_gateway_parity.py` (insan-komutu ↔ agent-tool denklik deseni + capability walk).
- **Fan-out:** `application/jobs/outbox_relay.py` (`relay_unpublished` scheduler checkpoint,
  `fetch_events_after` SSE cursor feed, `outbox_lag_seconds`); `apps/api/sse.py`
  (`SseHub`, `run_outbox_poller`, `sse_event_name` taksonomisi). SSE kayıp-toleranslı (INF-11).
- **Scheduler:** `application/jobs/maintenance.py` (`recover_stale_jobs` INF-09,
  `redeliverable_queued_jobs` INF-03); `apps/scheduler/__main__.py` `ACTOR_BY_QUEUE`.
- **Hardening:** `apps/api/hardening.py` (SecurityHeaders / RateLimit opt-in `RATE_LIMIT_ENABLED`
  / Metrics middleware); `infrastructure/observability/metrics.py` + `GET /v1/metrics`.

## Post-V1 aday işler (öncelik sırası önerisi)

1. ~~**Auth/IdP**~~ ✅ **LANDED (PR #38)** — yerel auth (argon2id + opaque session + `AUTH_MODE`
   + servis hattı). Not: production'a geçişte `AUTH_MODE=session` + `ENTROPIA_SERVICE_TOKEN` set
   edilmeli; ilk Admin hesabı provisioning'i henüz yok (signup hep `user`).
2. **Gerçek backtest engine** — ~~Slice A: Parquet batch data-access (PR #41)~~ ✅ **LANDED**;
   ~~Slice B: bar-replay engine + rule set (PR #43)~~ ✅ **LANDED**. Sırada **Slice C: gerçek
   indikatör compute** — engine'in entry/exit PROXY'sini gerçek indikatör sinyalleriyle değiştirir
   (Create Package candidate generation / package compute ile bağlanır). YALNIZ `engine.py`'deki
   entry/exit değerlendirmesi değişir; run/manifest/result sözleşmeleri sabit kalır. Küçük
   follow-up: `risk_based`/`formula_based` sizing implementasyonu (şu an notional + uyarı).
3. **Frontend entegrasyonu** — SSE tüketimi (yeni taksonomi), `/v1/metrics` dashboard'ları,
   Trash/Panel/Manual/Future-Dev shell'leri; `/v1/auth/*` login akışı hazır.
4. **Create Package gerçek candidate generation** — stub generator → LLM/derleme hattı (2. madde
   ile örtüşür; indikatör compute'un kaynağı burası).
5. **Capability aktivasyonları** — Future Dev slotlarını Placeholder'dan çıkarma (graphic_view ilk
   aday; gate'ler + Admin transition hazır).
6. **Deferred takipleri** — `summary["timeframe"]` çözümü (market-revision metadata'sından);
   `dispatch_tool_call` status-key gölgelemesi (chip açıldı); retention-window auto-purge;
   data-queue auto-redelivery; SSE HTTP-streaming e2e; audit log-projection indexleri;
   ilk-Admin provisioning.

## Yöntem (değişmedi)

- Workflow KULLANMA — doğrudan yaz; YENİ dosya Bash heredoc, mevcut dosya Edit 4-fact.
- `cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy src` +
  izole DB'de `uv run pytest --no-cov -q` (**822 yeşil kalmalı**); migration gerekirse
  `0022_*` (→0021) up/down/up + parity + L1 FK proof.
- code-reviewer subagent → CRITICAL/HIGH **AMPİRİK DOĞRULA** (8a: 0; 8b: 2/2 GERÇEK;
  auth: 0; parquet: 1/1 GERÇEK; engine Slice B: 1 CRITICAL/1 GERÇEK — oran değişken, HER ZAMAN
  doğrula) → commit (conventional, attribution YOK) → PR → `gh pr checks --watch` → merge için
  kullanıcıya sor. Türkçe, MALİYET BİLİNÇLİ.

---

## ⤵️ YENİ OTURUMDA YAPIŞTIR (resume prompt)

```
Entropia — post-V1: V1 tamam + Auth/IdP (PR #38) + Parquet Slice A (PR #41) + Bar-replay
engine Slice B (PR #43 merged, main=fc746f8, git log ile DOĞRULA). 822 test yeşil; alembic
head 0021_local_auth (Slice B migration'sız). Önce docs/POST_V1_KICKOFF.md + docs/STAGE2_HANDOFF.md
("Post-V1 — Backtest Engine (INF-12, Slice B) landed" + "Next: post-V1 (continued)") oku.

Slice B reuse anchor'ları: domain/backtest/engine.py::run_engine — pure (strategy_config,
bar_batches, execution_key) bar-replay; breakout entry-PROXY (entry_model diagnostics'te etiketli)
+ GERÇEK protection stop'lar (percentage/trailing/absolute, intrabar) + costs + notional sizing
(max(equity,0) clamp'li). application/jobs/backtest_engine.py — stream_bars enjekte edilebilir
(default iter_bar_batches), ASSET_UNAVAILABLE/ENGINE_ERROR fail yolları.
manifest ENGINE_VERSION=backtest-engine-v1-bar-replay.

Kalan aday işler (öncelik): (2c) gerçek indikatör compute — engine'in entry/exit PROXY'sini gerçek
indikatör sinyalleriyle değiştir (Create Package candidate generation ile bağlanır; YALNIZ engine.py
entry/exit değişir, run/manifest/result sabit); küçük follow-up: risk_based/formula_based sizing.
(3) frontend SSE/metrics/login, (4) CP gerçek candidate generation, (5) capability aktivasyonları,
(6) deferred (+ summary["timeframe"] çözümü, ilk-Admin provisioning).
Hangisinden başlayacağımızı bana sor; kapsamı birlikte netleştirelim.

YÖNTEM: Workflow KULLANMA; YENİ dosya heredoc, mevcut dosya Edit 4-fact; cd backend;
ruff+format+mypy+pytest (izole DB: TEST_DATABASE_URL=...entropia_auth; 822 yeşil kalmalı);
migration 0022_* (→0021) up/down/up + parity + L1 FK proof; code-reviewer → CRITICAL/HIGH
AMPİRİK DOĞRULA → commit (attribution YOK) → PR → checks watch → merge kullanıcıda.
Türkçe, MALİYET BİLİNÇLİ. Kapanışta: handoff + kickoff + CLAUDE.md + memory (ecc + claude-mem).
```
