# Post-V1 — Kickoff / Resume

> **Amaç:** V1 kapandı (Stage 0–8 COMPLETE). Bu doküman post-V1 durumunu, aday iş listesini
> ve temiz oturumda yapıştırılacak resume prompt'u içerir.

## Durum (2026-07-03, Backtest Engine `risk_based` sizing — Slice C follow-up (a) sonrası)

- **V1 ROADMAP COMPLETE + Auth/IdP + Parquet batch (Slice A) + Bar-replay engine (Slice B) +
  gerçek indikatör compute (Slice C) + `risk_based` sizing (Slice C follow-up a) landed.**
  Son iş `risk_based` sizing PR **#47** merged → `main` = **`4b4d1c6`** (feature kodu `43cee29`;
  Slice C kodu `671d227`; **git log ile doğrula** — özet stale-by-default). Alembic head =
  **`0021_local_auth`** (Slice C ve follow-up (a) migration'sız). Test tabanı: **864 yeşil**
  (859 + follow-up (a)'da 5). Backtest track artık **gerçek indikatör sinyalleriyle** giriş/çıkış
  üretiyor **ve** `risk_based_sizing`'i gerçekten modelliyor (önceki oturumda notional'a düşüp
  uyarıyordu). Manifest `ENGINE_VERSION = "backtest-engine-v2-risk-based-sizing"`.
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
- **Açık uçlar (Slice C follow-up'ları):** ~~`risk_based` sizing~~ ✅ **çözüldü (PR #47, aşağı bkz.)**;
  `formula_based` sizing hâlâ notional'a düşer + uyarır; `*_plus_condition` / condition block'ları
  `unresolved`; multi-timeframe (bar resampling) yok → timeframe override `unresolved`;
  `ta.atr`/`ta.vwap` directional değil.
- **NOT:** Slice C anchor'ındaki `ENGINE_VERSION = "backtest-engine-v2-indicator-compute"` follow-up
  (a)'da `"backtest-engine-v2-risk-based-sizing"`'e bump edildi (aşağı bkz.).

## `risk_based` sizing'in bıraktıkları (reuse anchor'ları — PR #47, Slice C follow-up a)

- **Engine sizing (güncellendi):** `domain/backtest/engine.py::_position_size` — YENİ `risk_based`
  bacağı: `size = max(equity, 0) * risk% / 100 / stop_loss_point` (**deterministik**, `entry_price`'tan
  **bağımsız**, non-negatif clamp — negatif size sonraki tüm trade'lerin PnL işaretini ters çevirirdi;
  önceki review CRITICAL, bust-safety testiyle sabit). YENİ helper `_sizing_is_honored(config)`:
  açık `base_position_size` **ve** sub-config'li `risk_based_sizing` = honored; `formula_based_sizing`
  **ve** sub-config'siz `risk_based` = notional fallback + L4 `position_sizing_method_unsupported:<method>`
  uyarısı. Diagnostics uyarısı artık `method != base_position_size` yerine `_sizing_is_honored(config)`'a bakıyor.
- **Manifest (güncellendi):** `domain/backtest/manifest.py` — `ENGINE_VERSION =
  "backtest-engine-v2-risk-based-sizing"` (`-indicator-compute`'tan bump). Gerekçe: `risk_based` çıktısı
  değişti → `execution_key` namespace'i kaymalı (INF-04 idempotent reuse / INF-05 reproducibility) —
  aynı kompozisyon için eski versiyon altında cache'lenmiş **stale notional-sized** sonucun yeniden
  kullanılmasını engeller.
- **Testler (+5):** `tests/unit/test_backtest_engine.py` — `_config` fixture'a `risk_pct`/`stop_point`;
  +5 test (risk formülü referans değeri, entry-price bağımsızlığı, bust clamp → 0, honored/unsupported
  uyarısı iki yön); 2 mevcut test `formula_based_sizing`'e repoint (hâlâ dürüst unsupported yolu).
  864 yeşil, ruff+mypy temiz, code-reviewer APPROVE (0 CRITICAL/0 HIGH). Migration YOK.
- **Açık uç:** `formula_based`/Kelly hâlâ `unresolved` (path-dependent istatistik; foundation'da
  belirsiz) → dürüst notional fallback + uyarı.

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
  testiyle sabitlendi). **GÜNCEL:** `risk_based_sizing` follow-up (a)'da (PR #47) **modellendi**
  (yukarı bkz.); `formula_based_sizing` hâlâ notional'a düşer + `position_sizing_method_unsupported:<method>`
  uyarısı (L4).
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
   engine (PR #43)~~ ✅ · ~~Slice C: gerçek indikatör compute (PR #45)~~ ✅ ·
   ~~Slice C follow-up (a): `risk_based` sizing (PR #47)~~ ✅ **LANDED**.
   **▶ SIRADAKİ (kullanıcıyla seçilecek): kalan Slice C follow-up'ları** — `indicators.py` /
   `indicator_plan.py` / `engine.py` üstüne biner:
   - ~~**(a)** `risk_based` sizing~~ ✅ **LANDED (PR #47)** — `_position_size` içinde izole çözüldü.
     **`formula_based`/Kelly hâlâ `unresolved`** (path-dependent istatistik; foundation'da belirsiz).
   - **(b)** condition block'ları + `*_plus_condition` trigger'ları — şu an `unresolved`;
     `SignalRule`/`BlockEvaluator`'ı condition bacağını değerlendirecek şekilde genişlet (orta boy,
     indikatör compute'a dokunur).
   - **(c)** multi-timeframe — bar resampling (timeframe override şu an `unresolved`; en invaziv,
     bar-replay determinizmini etkiler).
   - **(d)** daha çok directional canonical key — `ta.atr`/`ta.vwap` bugün directional değil
     (bant/kanal yorumu gerektirir).
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
  izole DB'de `uv run pytest --no-cov -q` (**864 yeşil kalmalı**); migration gerekirse
  `0022_*` (→0021) up/down/up + parity + L1 FK proof.
- code-reviewer subagent → CRITICAL/HIGH **AMPİRİK DOĞRULA** (8a: 0; 8b: 2/2 GERÇEK; auth: 0;
  parquet: 1/1 GERÇEK; engine Slice B: 1 CRITICAL/1 GERÇEK — oran değişken, HER ZAMAN doğrula) →
  commit (conventional, attribution YOK) → PR → `gh pr checks --watch` → merge için kullanıcıya
  sor. Türkçe, MALİYET BİLİNÇLİ.

---

## ⤵️ YENİ OTURUMDA YAPIŞTIR (resume prompt)

```
Entropia — post-V1: V1 tamam + Auth/IdP (PR #38) + Parquet Slice A (PR #41) + Bar-replay
engine Slice B (PR #43) + gerçek indikatör compute Slice C (PR #45) + risk_based sizing
Slice C follow-up (a) (PR #47 merged). ÖNCE DOĞRULA (stale-by-default): git fetch &&
git log --oneline origin/main -4. main=4b4d1c6 (feature kodu 43cee29; Slice C kodu 671d227);
alembic head 0021_local_auth (migration YOK). İzole DB:
TEST_DATABASE_URL=postgresql+asyncpg://entropia:entropia@localhost:5432/entropia_auth.
Test tabanı 864 (859 + 5); pytest --co ile teyit et (bu projede --co dosya-başına sayım
basar → ": N" değerlerini topla). ÖNCE docs/POST_V1_KICKOFF.md + docs/STAGE2_HANDOFF.md
("risk_based sizing landed (PR #47)" + "Next: remaining Slice C follow-ups") oku.

SIRADAKİ İŞ (kullanıcıyla seç): kalan Slice C follow-up'ları. (a) risk_based sizing ✅
LANDED (PR #47) — formula_based/Kelly hâlâ unresolved (path-dependent, foundation belirsiz).
Kalan: (b) condition blocks + *_plus_condition (SignalRule/BlockEvaluator genişlet, indikatör
compute'a dokunur), (c) multi-timeframe bar resampling (en invaziv, bar-replay determinizmi),
(d) daha çok directional key (ta.atr/vwap bant/kanal). Kapsamı kullanıcıyla netleştir, hangi
follow-up'tan başlanacağını sor.

REUSE ANCHOR'LARI (kodu incele, tek satır özet):
- domain/backtest/engine.py::_position_size — risk_based bacağı: size = max(equity,0)*risk%
  /100/stop_loss_point (deterministik, entry_price'tan bağımsız, non-negatif clamp). Helper
  _sizing_is_honored(config): base_position_size + sub-config'li risk_based_sizing = honored;
  formula_based VE sub-config'siz risk_based = notional fallback + L4 position_sizing_method_
  unsupported:<method>. ENGINE_VERSION=backtest-engine-v2-risk-based-sizing (manifest.py;
  execution_key namespace, INF-04/INF-05). Dual-mode run_engine(..., indicator_plan=None)
  (plan → gerçek sinyal, yoksa breakout PROXY); exit = protection stops + exit blocks +
  exit_on_opposite. jobs/backtest_engine.py plan'ı resolve+enjekte (sözleşmeler sabit).
- domain/backtest/indicators.py — pure/incremental Decimal TA (ta.sma/ema/rma/wma MA-cross
  + ta.rsi band cross; ta.atr/vwap non-directional/unresolved); IndicatorSpec/SignalRule/
  IndicatorPlan + BlockEvaluator; BUILTIN_ENTRY_MODEL=builtin_indicator_native_trigger_v1;
  params: parameter_overrides else defaults (RSI 14, MA 20, 30/70).
- application/queries/indicator_plan.py — resolve_indicator_plan(session, strategy_config)
  → IndicatorPlan; pinned PackageRevision.dependency_snapshot canonical_key → spec (gövde
  çalıştırılmaz; native-trigger-only → *_plus_condition/timeframe/non-directional = unresolved, L4).

YÖNTEM: Workflow KULLANMA; YENİ dosya heredoc, mevcut dosya Edit 4-fact; cd backend;
ruff+format+mypy+pytest (izole DB: ...entropia_auth; 864 yeşil kalmalı); migration gerekirse
0022_* (→0021) up/down/up + parity + L1 FK proof; code-reviewer → CRITICAL/HIGH AMPİRİK
DOĞRULA → commit (attribution YOK) → PR → checks watch → merge kullanıcıda. Türkçe, MALİYET
BİLİNÇLİ. Kapanışta: handoff + kickoff + CLAUDE.md + memory (ecc + claude-mem).
```
