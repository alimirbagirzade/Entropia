# Post-V1 — Kickoff / Resume

> **Amaç:** V1 kapandı (Stage 0–8 COMPLETE). Bu doküman post-V1 durumunu, aday iş listesini
> ve temiz oturumda yapıştırılacak resume prompt'u içerir.

## Durum (2026-07-03, Backtest Engine Slice C sonrası)

- **V1 ROADMAP COMPLETE + Auth/IdP + Parquet batch (Slice A) + Bar-replay engine (Slice B) +
  gerçek indikatör compute (Slice C) landed.**
  Slice C PR **#45** merged → `main` = **`a11640c`** (Slice C kodu `671d227`; **git log ile
  doğrula** — özet stale-by-default). Alembic head = **`0021_local_auth`** (Slice C migration'sız).
  Test tabanı: **859 yeşil** (822 + Slice C'de 37). Backtest track artık **gerçek indikatör
  sinyalleriyle** giriş/çıkış üretiyor: engine'in entry/exit breakout PROXY'si, pinlenmiş
  indikatör paketlerinden çözülen native-trigger sinyallerle değiştirildi (plan yoksa PROXY'ye
  geriye-uyumlu düşer).
- **Test-infra notu:** integration testleri her testte şemayı drop/create eder — aynı lokal
  Postgres'i paylaşan İKİ oturum birbirini bozar. İzole DB kullan:
  `TEST_DATABASE_URL=postgresql+asyncpg://entropia:entropia@localhost:5432/entropia_auth`.

## Backtest Engine Slice C'nin bıraktıkları (reuse anchor'ları — PR #45)

- **Indicators (pure, YENİ):** `domain/backtest/indicators.py` — saf, **incremental
  (bounded-memory)** `Decimal` TA compute. Seed'li canonical key'ler: `ta.sma`/`ema`/`rma`/`wma`
  (MA-cross native trigger) + `ta.rsi` (band cross); `ta.atr`/`ta.vwap` **RECOGNIZED ama
  non-directional** (unresolved). Tipler: `IndicatorSpec` / `SignalRule` / `IndicatorPlan`;
  `BlockEvaluator` (validity penceresi + per-block direction filter), `aggregate` /
  `build_evaluators`; `BUILTIN_ENTRY_MODEL = "builtin_indicator_native_trigger_v1"`. Parametreler:
  `parameter_overrides` varsa o, yoksa **engine-version default** (RSI 14, MA 20, bantlar 30/70 —
  reproducibility sabitleri).
- **Plan resolution (YENİ):** `application/queries/indicator_plan.py` —
  `resolve_indicator_plan(session, strategy_config) → IndicatorPlan`. Pinlenmiş her
  `PackageRevision.dependency_snapshot["resolved"][i]["canonical_key"]`'i built-in spec'e çözer.
  **Paket gövdeleri ÇALIŞTIRILMAZ.** NATIVE-TRIGGER-ONLY: `*_plus_condition` / timeframe override /
  non-directional key → `unresolved` diagnostics warning (asla sessizce düşmez — L4).
- **Engine dual-mode:** `domain/backtest/engine.py` — `run_engine(..., indicator_plan=None)`.
  Çözülen bir entry block varsa **gerçek sinyaller** sürer; yoksa etiketli breakout PROXY'ye
  düşer (geriye uyumlu — Slice B yolu bozulmadan durur). Exit = gerçek protection stop'lar
  (Slice B) + exit block'lar + `exit_on_opposite`.
- **Job:** `application/jobs/backtest_engine.py` — plan'ı resolve edip **enjekte eder**
  (run/manifest/result sözleşmeleri sabit). **Manifest:** `domain/backtest/manifest.py` —
  `ENGINE_VERSION = "backtest-engine-v2-indicator-compute"` (`execution_key` reprodüksiyon
  hash'ine katılır — INF-05 korunur; aynı kompozisyon aynı sonucu üretir).
- **Dürüst sınır (native-trigger-only; yüzeye çıkar, gizlenmez — L4):** yalnız
  `trigger_source == indicator_native_trigger` gerçek sinyale çözülür; `*_plus_condition`,
  timeframe override ve non-directional key'ler (`ta.atr`/`ta.vwap`) `unresolved` uyarısı olur;
  somut parametreler parse-edilmemiş kaynak gövdeden gelir → engine-version default +
  `parameter_overrides`.
- **Testler (+37):** `tests/unit/test_backtest_indicators.py` (**+24** — MA/RSI referans değerleri
  + invariant'lar, native trigger'lar, validity, aggregation), `test_backtest_engine_indicator_plan.py`
  (**+7** — gerçek `entry_model`, batch-size'lar arası determinizm, exit-on-opposite, proxy
  fallback + unresolved uyarıları), `tests/integration/test_indicator_plan_resolution.py`
  (**+6** — gerçek `package_revision` satırları, her unresolved yol dahil), `test_e2e_pipeline.py`
  (yayınlanmış RSI paketi uçtan uca gerçek compute'u sürer: `entry_model == BUILTIN_ENTRY_MODEL`).
- **Açık uçlar (Slice C follow-up'ları → sıradaki dilim):** `risk_based`/`formula_based` sizing
  hâlâ notional'a düşer + uyarır; `*_plus_condition` / condition block'ları `unresolved`;
  multi-timeframe (bar resampling) yok → timeframe override `unresolved`; `ta.atr`/`ta.vwap`
  directional değil.

## Backtest Engine Slice B'nin bıraktıkları (reuse anchor'ları — PR #43)

- **Engine (pure):** `domain/backtest/engine.py` — `run_engine(*, strategy_config, bar_batches,
  execution_key, item_count=1, indicator_plan=None) → EngineOutput`. DB/clock/randomness yok;
  `bar_batches`'i BİR kez akıtır. Frozen çıktı satırları `TradeRow` / `EquityPoint` /
  `SignalEventRow` / `EngineOutput`. **Gerçek** protection stop'lar — `_initial_static_stop`
  (percentage/absolute'ün en sıkısı), `_trail_pct`+`_effective_stop` (trailing), **intrabar**
  değerlendirme (long: `bar.low ≤ stop`; short: `bar.high ≥ stop`) → `stop_loss`; veri sonu
  kapanışı → `end_of_data` (açık pozisyon asla sarkmaz). Maliyet — `_cost_params` /
  `_effective_fill` (yarım-spread + slippage oranı + fill başına komisyon ×2 gidiş-dönüş).
  **NOT:** Slice C sonrası entry/exit dual-mode — plan yoksa aşağıdaki breakout PROXY sürer.
- **Entry PROXY (fallback):** plan yoksa giriş **breakout proxy** (`_BREAKOUT_WINDOW = 20`
  look-back; yeni pencere yükseğinde long, düşüğünde short; aynı-bar beraberliğinde long kazanır),
  diagnostics'te `entry_model = deterministic_bar_breakout_proxy_v1` etiketli. Yön kısıtı →
  `suppressed_entries` → tek `filtered_no_entry` sinyal olayı.
- **Sizing:** `_position_size` — açık `base_position_size`, yoksa all-in **notional**,
  `max(equity, 0)` clamp'li (bust hesap → size 0, **asla negatif değil**; negatif size sonraki
  tüm trade'lerin PnL işaretini ters çevirirdi — review CRITICAL, deterministik bust-safety
  testiyle sabitlendi). `risk_based_sizing` / `formula_based_sizing` **modellenmedi** →
  notional'a düşer + `position_sizing_method_unsupported:<method>` uyarısı (L4). **Slice C
  follow-up'ının ilk maddesi burası.**
- **Job:** `application/jobs/backtest_engine.py` — `run_backtest(..., stream_bars=iter_bar_batches)`;
  bar'lar **enjekte edilebilir** (default gerçek S3-backed streamer). Fail yolları: market
  revizyonu yok/çözülemez → `ASSET_UNAVAILABLE`; engine exception'ı → `ENGINE_ERROR` (ikisi de
  audit'lenir). Slice C bu job'a plan resolution'ı da ekledi.

## Parquet Slice A'nın bıraktıkları (reuse anchor'ları — PR #41)

- **Streaming:** `infrastructure/s3/parquet_stream.py` — `stream_processed_batches(object_key)`
  (S3 `download_fileobj` → `SpooledTemporaryFile` 32MB spill-to-disk cap → pyarrow
  `ParquetFile.iter_batches`); `iter_parquet_batches(source)` saf lokal I/O (infra'sız
  unit-test edilebilir batching kontratı); `DEFAULT_BATCH_SIZE = 8_192`. YALNIZ worker plane.
- **Query:** `application/queries/market_bars.py` — `resolve_bar_source(session,
  market_revision_id=...)` → `BarSourceRef` (frozen: entity_id / revision_id / object_key /
  content_digest / size_bytes / row_count; işlenmemiş revizyonda `NotFoundError`) +
  `iter_bar_batches(source)`. Read-only; 'latest'e asla dokunmaz (doc 15 no-latest-leak).
- **Repo:** `repositories/market_data.py::get_processed_asset_for_revision` — sıralama kontratı:
  re-processing ayrı tx'te koşar (farklı ULID timestamp); aynı-ms ULID tiebreak non-deterministik
  — belgelenmiş limit, deterministik testle sabitlendi.

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
  ingest→publish→compose→allocate zinciri; Slice B gerçek bar-replay ile, Slice C gerçek
  indikatör compute ile sürer), `test_e2e_agent_loop.py` (UI'sız agent döngüsü),
  `test_gateway_parity.py` (insan-komutu ↔ agent-tool denklik deseni + capability walk).
- **Fan-out:** `application/jobs/outbox_relay.py` (`relay_unpublished`, `fetch_events_after`,
  `outbox_lag_seconds`); `apps/api/sse.py` (`SseHub`, `run_outbox_poller`, `sse_event_name`).
  SSE kayıp-toleranslı (INF-11).
- **Scheduler:** `application/jobs/maintenance.py` (`recover_stale_jobs` INF-09,
  `redeliverable_queued_jobs` INF-03); `apps/scheduler/__main__.py` `ACTOR_BY_QUEUE`.
- **Hardening:** `apps/api/hardening.py` (SecurityHeaders / RateLimit opt-in `RATE_LIMIT_ENABLED`
  / Metrics middleware); `infrastructure/observability/metrics.py` + `GET /v1/metrics`.

## Post-V1 aday işler (öncelik sırası önerisi)

1. ~~**Auth/IdP**~~ ✅ **LANDED (PR #38)** — yerel auth (argon2id + opaque session + `AUTH_MODE`
   + servis hattı). Not: production'a geçişte `AUTH_MODE=session` + `ENTROPIA_SERVICE_TOKEN` set
   edilmeli; ilk Admin hesabı provisioning'i henüz yok (signup hep `user`).
2. **Gerçek backtest engine** — ~~Slice A: Parquet batch (PR #41)~~ ✅ · ~~Slice B: bar-replay
   engine (PR #43)~~ ✅ · ~~Slice C: gerçek indikatör compute (PR #45)~~ ✅ **LANDED**.
   **▶ SIRADAKİ (kullanıcı seçti): Slice C follow-up'ları** — `indicators.py` /
   `indicator_plan.py` / `engine.py` üstüne biner:
   - **(a)** `risk_based`/`formula_based` sizing — `_position_size` içinde izole (şu an notional +
     `position_sizing_method_unsupported` uyarısı). **En küçük/en izole; doğal ilk adım.**
   - **(b)** condition block'ları + `*_plus_condition` trigger'ları — şu an `unresolved`;
     `SignalRule`/`BlockEvaluator`'ı condition bacağını değerlendirecek şekilde genişlet.
   - **(c)** multi-timeframe — bar resampling (timeframe override şu an `unresolved`).
   - **(d)** daha çok directional canonical key — `ta.atr`/`ta.vwap` bugün directional değil.
3. **Frontend entegrasyonu** — SSE tüketimi (yeni taksonomi), `/v1/metrics` dashboard'ları,
   Trash/Panel/Manual/Future-Dev shell'leri; `/v1/auth/*` login akışı hazır.
4. **Create Package gerçek candidate generation** — stub generator → LLM/derleme hattı; indikatör
   compute'un kaynağı burası (Slice C plan resolution pinned snapshot'tan okur).
5. **Capability aktivasyonları** — Future Dev slotlarını Placeholder'dan çıkarma (graphic_view ilk
   aday; gate'ler + Admin transition hazır).
6. **Deferred takipleri** — `summary["timeframe"]` çözümü (market-revision metadata'sından);
   `dispatch_tool_call` status-key gölgelemesi (chip açıldı); retention-window auto-purge;
   data-queue auto-redelivery; SSE HTTP-streaming e2e; audit log-projection indexleri;
   ilk-Admin provisioning.

## Yöntem (değişmedi)

- Workflow KULLANMA — doğrudan yaz; YENİ dosya Bash heredoc (gate-free), mevcut dosya Edit 4-fact.
- `cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy src` +
  izole DB'de `uv run pytest --no-cov -q` (**859 yeşil kalmalı**); migration gerekirse
  `0022_*` (→0021) up/down/up + parity + L1 FK proof.
- code-reviewer subagent → CRITICAL/HIGH **AMPİRİK DOĞRULA** (8a: 0; 8b: 2/2 GERÇEK; auth: 0;
  parquet: 1/1 GERÇEK; engine Slice B: 1 CRITICAL/1 GERÇEK — oran değişken, HER ZAMAN doğrula) →
  commit (conventional, attribution YOK) → PR → `gh pr checks --watch` → merge için kullanıcıya
  sor. Türkçe, MALİYET BİLİNÇLİ.

---

## ⤵️ YENİ OTURUMDA YAPIŞTIR (resume prompt)

```
Entropia — post-V1: V1 tamam + Auth/IdP (PR #38) + Parquet Slice A (PR #41) + Bar-replay
engine Slice B (PR #43) + gerçek indikatör compute Slice C (PR #45 merged). ÖNCE DOĞRULA
(stale-by-default): git fetch && git log --oneline origin/main -4. main=a11640c (Slice C
kodu 671d227); alembic head 0021_local_auth (migration YOK). İzole DB:
TEST_DATABASE_URL=postgresql+asyncpg://entropia:entropia@localhost:5432/entropia_auth.
Test tabanı 859 (822 + 37); pytest --co ile teyit et (bu projede --co dosya-başına sayım
basar → ": N" değerlerini topla). ÖNCE docs/POST_V1_KICKOFF.md + docs/STAGE2_HANDOFF.md
("Slice C landed (PR #45)" + "Next: Slice C follow-ups") oku.

SIRADAKİ İŞ (kullanıcı seçti): Slice C follow-up'ları. Doğal ilk adım (a): risk_based/
formula_based sizing — engine.py::_position_size içinde izole (şu an notional +
position_sizing_method_unsupported uyarısı). Sonra (b) condition blocks + *_plus_condition
(SignalRule/BlockEvaluator genişlet), (c) multi-timeframe bar resampling, (d) daha çok
directional key (ta.atr/vwap). Kapsamı kullanıcıyla netleştir, hangi follow-up'tan
başlanacağını sor.

SLICE C REUSE ANCHOR'LARI (kodu incele, tek satır özet):
- domain/backtest/indicators.py — pure/incremental Decimal TA (ta.sma/ema/rma/wma MA-cross
  + ta.rsi band cross; ta.atr/vwap non-directional/unresolved); IndicatorSpec/SignalRule/
  IndicatorPlan + BlockEvaluator; BUILTIN_ENTRY_MODEL=builtin_indicator_native_trigger_v1;
  params: parameter_overrides else defaults (RSI 14, MA 20, 30/70).
- application/queries/indicator_plan.py — resolve_indicator_plan(session, strategy_config)
  → IndicatorPlan; pinned PackageRevision.dependency_snapshot canonical_key → spec (gövde
  çalıştırılmaz; native-trigger-only → *_plus_condition/timeframe/non-directional = unresolved, L4).
- engine.py — run_engine(..., indicator_plan=None) dual-mode (plan → gerçek sinyal, yoksa
  breakout PROXY fallback); exit = protection stops + exit blocks + exit_on_opposite.
  ENGINE_VERSION=backtest-engine-v2-indicator-compute (execution_key, INF-05).
  jobs/backtest_engine.py plan'ı resolve+enjekte eder (sözleşmeler sabit).

YÖNTEM: Workflow KULLANMA; YENİ dosya heredoc, mevcut dosya Edit 4-fact; cd backend;
ruff+format+mypy+pytest (izole DB: ...entropia_auth; 859 yeşil kalmalı); migration gerekirse
0022_* (→0021) up/down/up + parity + L1 FK proof; code-reviewer → CRITICAL/HIGH AMPİRİK
DOĞRULA → commit (attribution YOK) → PR → checks watch → merge kullanıcıda. Türkçe, MALİYET
BİLİNÇLİ. Kapanışta: handoff + kickoff + CLAUDE.md + memory (ecc + claude-mem).
```
