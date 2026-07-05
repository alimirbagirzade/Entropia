# Post-V1 — Kickoff / Resume

> **Amaç:** V1 kapandı (Stage 0–8 COMPLETE). Bu doküman post-V1 durumunu, aday iş listesini
> ve temiz oturumda yapıştırılacak resume prompt'u içerir.

## Durum (2026-07-05, TIER 2 frontend — real-auth login/signup/logout; PR #65)

> **İlk TIER 2 (frontend) slice — gerçek auth login/signup/logout landed (PR #65, açık, CI
> yeşil, kullanıcı merge'i bekliyor).** Backend zaten gerçek local auth sunuyordu
> (`/v1/auth/signup|login|logout`, opaque Bearer session — Auth/IdP PR #38 + M1 §4) ama web
> shell (`frontend/`, **Vite 8 + React 18 + react-router 6 + @tanstack/react-query 5 + react-hook-form**)
> yalnızca dev `X-Actor-Id` header'ı gönderiyordu. Bu slice shell'i backend'e bağlar → insanlar
> gerçek Bearer session alır. **FRONTEND-ONLY — backend değişmedi, migration YOK, backend test
> tabanı 1015 sabit.** CI: **Frontend + Docker check yeşil**; backend check frontend-only diff
> için değişmeden yeniden koşar. alembic head hâlâ `0021_local_auth`.
> **Reuse anchor'ları (kesin semboller):**
> - **`frontend/src/lib/session.ts`** *(YENİ)* — external store: `getSessionToken()` (API client'ın
>   her istekte okuduğu ham-string fast-path), `getStoredUser()`, `setSession({token,user,expiresAt})`,
>   `clearSession()`, `subscribe(listener)`. İki `localStorage` anahtarı (`entropia.sessionToken`
>   + `entropia.session` JSON meta). React-bağımsız → `useSyncExternalStore` ile birleşir.
> - **`frontend/src/lib/apiClient.ts`** — `apiRequest` artık `getSessionToken()` non-null iken
>   mevcut `X-Actor-Id`'ye **EK OLARAK** `Authorization: Bearer <token>` ekler. İki header güvenle
>   birlikte gider: server yalnızca `AUTH_MODE`'un güvendiğini onurlandırır (`session` → Bearer
>   asıl, bare `X-Actor-Id` yok sayılır; `dev` → `X-Actor-Id`, Bearer yok sayılır — `backend
>   .../apps/api/deps.py`), ikisi de diğerini spoof edemez.
> - **`frontend/src/lib/auth.ts`** *(YENİ)* — react-query mutation'ları: `useLogin` (POST
>   `/auth/login` → `setSession`), `useSignup` (POST `/auth/signup` sonra **auto-login**),
>   `useLogout` (best-effort POST `/auth/logout`, **her durumda** `clearSession()` — başarısız/expired
>   revoke UI'ı yarı-login bırakmaz), `useSessionToken()`. Her success `queryClient.invalidateQueries()`
>   → `/me` + rol-gated nav yeni principal altında refetch.
> - **`frontend/src/pages/Login.tsx`** *(YENİ)* — standalone `/login` (app shell yok),
>   `react-hook-form`, login/signup toggle; hata backend canonical envelope'ını **verbatim** gösterir
>   (`ApiError` → `${code}: ${message}`); client asla auth mesajı uydurmaz. Zorunlu-alan validation
>   client-side submit'i bloklar.
> - **`frontend/src/app/Layout.tsx`** — yeni `AuthControl`: anonimken **Log in** link, token varken
>   kullanıcı + **Log out**; gerçek session aktifken `DevActorControl` gizli (`token ? null : <DevActorControl/>`).
> - **`frontend/src/App.tsx`** — `<Layout>` route'u DIŞINDA standalone `/login` `<Route>`.
> - **`frontend/src/lib/types.ts`** — `AuthUser` / `SignUpResponse` (= `AuthUser`) / `LoginResponse`
>   envelope'ları (`routes/auth.py` yansıması).
> - **`frontend/src/styles/global.css`** — yeni `.btn*` + `.auth-*` sınıfları (temalı, dark/light).
> - **`frontend/src/test/auth.test.tsx`** *(YENİ)* — 6 vitest → **frontend toplam 9/9**; typecheck +
>   lint temiz; production build yeşil.
> **Dürüst sınır:** anonim → `/login` zorlayan route guard YOK (dev mode anonim gezmeye izin verir;
> erişim server-side gate'lenir). First-Admin provisioning hâlâ upstream'de yok (signup hep baseline
> rol). Diğer iki TIER 2 adayı — **SSE live-invalidation** (`sse.ts` stub'ını doldur) ve
> **`/v1/metrics` dashboard** (Prometheus-text parser) — bu slice'ta DEĞİL, sıradaki doğal işler.
> **Sıradaki doğal slice: TIER 2 SSE live-invalidation** (küçük, saf infra) VEYA `/v1/metrics`
> dashboard — kullanıcı seçsin. Aşağıdaki position_size_limits (PR #63) bloğu ve öncesi tarihsel.

## Durum (2026-07-05, position_size_limits min/max cap wiring — Slice C follow-up sonrası; PR #63)

> **`position_size_limits` (min/max pozisyon cap) wiring landed (PR #63, kod `5ef5525`,
> merge `97b10b8`); MERGED → main `97b10b8`.** `PositionSizeLimits` sizing sub-config'de
> (`domain/strategy/config.py:599`) tanımlıydı ama `engine._position_size`'da **TÜM sizing
> metodlarında sessizce ignore ediliyordu** (latent bug — configure edilen cap hiçbir yolda
> hesaplanan size'ı kısıtlamıyordu). Fix, size'ı **tek bir sizing sınırında** clamp'ler →
> **base / risk_based / Kelly / notional-fallback** hepsi uniform cap'lenir. **Migration YOK**
> (config-only, JSONB — `PositionSizeLimits` değişmedi). **1015 test** (999 + 15: 7
> `_clamp_to_limits` unit / 6 per-method `_position_size` / 1 e2e / 1 ENGINE_VERSION ns).
> Review APPROVE 0 CRITICAL/HIGH. `ENGINE_VERSION=backtest-engine-v2-position-size-limits`.
> **Reuse anchor'ları:**
> - `domain/backtest/engine.py` — **YENİ `_clamp_to_limits(size, limits)`**: `limits is None`
>   VEYA `size <= _ZERO` → **no-op** (`0` = "açma" sentinel'i; bir `min` cap onu canlı pozisyona
>   diriltmez, ne de bir negatifi pozitife çeker); `min > max` yanlış-yapılandırma → `_ZERO`
>   (hiçbir size ikisini de sağlamaz → fail-closed); yoksa size'ı **DOWN-to-`max`**, sonra
>   **UP-to-`min`**, sonra `max(size, _ZERO)` (negatif cap'i de nötrler). Cap birimi = size birimi
>   (adet/coin), **unquantized** (base dalı ile simetrik). Eski `_position_size` gövdesi
>   **`_raw_position_size` olarak yeniden adlandırıldı** (mantık aynı); `_position_size` artık ince
>   wrapper = `_clamp_to_limits(_raw_position_size(config, entry_price, equity), config.position_sizing.position_size_limits)`.
>   Eksik limits alt-ağacı → pre-wiring engine ile **byte-identical**. **Tek çağrı noktası**
>   (`_open`, ~L475) → tüm sizing yolları otomatik clamp'lenir. `TYPE_CHECKING` import'una
>   `PositionSizeLimits` eklendi; `run_engine` diagnostics'e `"position_size_limits_active": bool`.
> - `domain/backtest/manifest.py` — `ENGINE_VERSION` `-kelly-sizing` → `-position-size-limits`
>   (execution_key ns shift; INF-04/INF-05 — stale UNCLAMPED sonuç reuse edilmez).
> - `domain/strategy/config.py:599` — `PositionSizeLimits(min_position_size/max_position_size: Decimal|None)`
>   **DEĞİŞMEDİ**, migration YOK.
> - `tests/unit/test_backtest_engine.py` — `_config`'e `min_size`/`max_size` kwargs; `_clamp_to_limits`
>   + `PositionSizeLimits` import; +15 test.
> **Dürüst sınır:** cap birimi = size birimi (adet), unquantized (base branch ile simetrik);
> `base_position_size` NEGATİF verilirse clamp muaf (`size <= _ZERO` guard) — pre-existing, scope
> dışı. **Slice C indikatör-compute + sizing + TIER 1 backend follow-up'ları böylece EFEKTİF TAMAM**
> (Kelly + risk_based + condition blocks + multi-TF + N-ary + VWAP + position_size_limits hepsi
> landed). **Sıradaki doğal slice: TIER 2 frontend/infra** (SSE/metrics/login, capability
> aktivasyonları, admin provisioning) — kullanıcı seçsin. Aşağıdaki Kelly (PR #60/#61) bloğu ve
> öncesi tarihsel.

## Durum (2026-07-04, formula_based Kelly sizing — Slice C follow-up sonrası; PR #60 + #61)

> **`formula_based` (Kelly criterion) sizing landed (PR #60, kod `3f254bc`) + non-finite
> fail-closed fix (PR #61, kod `3a92e7d`); ikisi de MERGED → main `54e71d2`.**
> `formula_based_sizing` + `kelly_criterion` config artık **HONORED**: fractional-Kelly capital
> fraction `f* = kelly_fraction·(W − (1−W)/R)` (alt-clamp 0), pozisyon usable equity'den boyutlanır
> (entry-price **BAĞIMLI**, `risk_based`'in stop-mesafesi boyutlamasının aksine). Diğer TÜM
> `formula_based` şekilleri (özellikle `custom_formula`) hâlâ notional fallback +
> `position_sizing_method_unsupported`. `ENGINE_VERSION=backtest-engine-v2-kelly-sizing`.
> **Migration YOK** (config-only). **999 test** (987 + 12: 9 Kelly feat / 3 non-finite fix).
> **Review (PR #60):** 1 CONFIRMED defect — non-finite `formula_params` (NaN/Inf) → Decimal
> aritmetiği `InvalidOperation` **CRASH** + Inf payoff → `(1−W)/R=0` → `f*` **SESSİZ honor**;
> **PR #61** `Decimal.is_finite()` guard'ı ile kapatıldı (non-finite → None → fail-closed) + 3
> regresyon testi. (#60 fix commit branch'e gelmeden self-merge edildi → fix ayrı PR #61 ile
> landed; ikisi de main'de.) **Reuse anchor'ları:** STAGE2_HANDOFF.md «formula_based Kelly …
> landed» + `domain/backtest/engine.py` (`_decimal_param` / `_kelly_capital_fraction` /
> `_position_size` Kelly dalı / `_sizing_is_honored`) + `manifest.py` `ENGINE_VERSION`.
> **Dürüst sınır:** adaptif/rolling Kelly (W/R backtest'ten tahmin) deferred (path-dependent +
> look-ahead); `custom_formula` unsupported (güvenli eval yok). Slice C indikatör-compute +
> sizing follow-up'ları böylece **EFEKTİF TAMAM**; sıradaki **TIER 1 kalıntısı**
> `position_size_limits` (min/max cap) wiring — `PositionSizeLimits` config'de tanımlı ama TÜM
> sizing metodlarında `engine._position_size`'da **sessizce ignore ediliyor** (latent bug;
> ENGINE_VERSION bump gerektirir). Aşağıdaki VWAP (d) bloğu ve öncesi tarihsel.

## Durum (2026-07-04, VWAP directional key — Slice C follow-up (d) sonrası; PR #58)

> **(d) VWAP directional key landed (PR #58, kod `d27b2bb`; merge KULLANICIDA, CI yeşil).**
> `ta.vwap` artık `DIRECTIONAL_KEYS` üyesi: rolling volume-ağırlıklı fiyat çizgisi, fiyat/VWAP
> cross'u native yönlü trigger (MA-cross ile aynı şekil); native trigger + reference paketi +
> N-ary chain leg olarak kullanılabilir. `ta.atr` doğası gereği non-directional kaldı (dürüst
> terminal sınır). Yeni `_Vwap` compute (bounded-memory, typical (H+L+C)/3 × volume, zero-volume
> fail-closed); volume engine `_Bar`→evaluator'lar boyunca threadlendi; `vwap_blocks` diagnostic;
> `ENGINE_VERSION=backtest-engine-v2-vwap-directional`. **Migration YOK.** **987 test** (970+17).
> Slice C indikatör-compute follow-up'ları böylece **etkin biçimde tamamlandı**; kalan TIER 1
> işi **formula_based/Kelly sizing** (hâlâ notional fallback). Aşağıdaki (ii) bölümü tarihsel.

## Durum (2026-07-04, N-ary reference chain — Slice C follow-up (ii) sonrası)

- **V1 ROADMAP COMPLETE + Auth/IdP + Parquet batch (Slice A) + Bar-replay engine (Slice B) +
  gerçek indikatör compute (Slice C) + `risk_based` sizing (a) + condition blocks (b) +
  condition extensions (b2) + two-package indicator-vs-indicator (#53) + higher-timeframe bar
  resampling (c) (#55) + per-condition multi-timeframe reference (i) + N-ary reference chain (ii) landed.** Son iş
  N-ary reference chain PR **#57** → `main` (feature kodu
  `44099a7`; #56 per-condition `1c5cca0`; #55 multi-tf kodu `def6c28`; #53 `9087c2b`; (b2) `361df4c`; condition-blocks (b)
  `8766fae`; risk_based (a) `43cee29`; Slice C `671d227`; **git log ile doğrula** — özet
  stale-by-default). Alembic head = **`0021_local_auth`** (Slice C + (a)/(b)/(b2)/(#53)/(c)/(i)/(ii)
  migration'sız). Test tabanı: **970 yeşil** (953 + #57'de 17). Backtest track artık **gerçek
  indikatör sinyalleriyle** giriş/çıkış üretiyor, `risk_based_sizing`'i modelliyor, condition
  gate'leri **crosses/between/series-vs-series** + **condition-only yön sinyali** ile
  değerlendiriyor, indikatör blok **daha kaba bir TF'de** compute edebiliyor (c), ve bir
  condition'ın **RHS reference paketi** parent bloktan **daha kaba bir TF'de** hesaplanabiliyor
  (i — `ConditionBlock.reference_timeframe`; hızlı source vs yavaş referans, look-ahead yok),
  ve bir condition'ın RHS'i **>2 paketlik sıralı bir zincir** olabiliyor (ii —
  `ConditionBlock.additional_reference_package_refs`; `fast > slow > slowest` MA fan; tek-paket
  yolu #53/#56 ile byte-identical).
  Manifest `ENGINE_VERSION = "backtest-engine-v2-nary-reference"`.
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
   **▶ Slice C follow-up'ları ARTIK EFEKTİF TAMAM** (aşağıdakilerin hepsi landed; TIER 1 backend
   DONE) — `indicators.py` / `indicator_plan.py` / `engine.py` üstüne biniyordu:
   - ~~**(a)** `risk_based` sizing~~ ✅ **LANDED (PR #47)** — `_position_size` içinde izole çözüldü.
     ~~**`formula_based`/Kelly**~~ ✅ **LANDED (PR #60 + #61)** — Kelly honored; `custom_formula` +
     adaptif/rolling Kelly dürüst `unresolved`. ~~**`position_size_limits` min/max cap**~~ ✅
     **LANDED (PR #63)** — `_clamp_to_limits` TÜM sizing metodlarını (base/risk_based/Kelly/notional) cap'ler.
   - ~~**(b)** condition block'ları (threshold gate)~~ ✅ **LANDED (PR #49)** ·
     ~~**(b2)** condition genişletmeleri (crosses/between/series-vs-series + condition-only yön)~~
     ✅ **LANDED (PR #51)** · ~~**indicator-vs-indicator — İKİ AYRI paket** (fast-MA vs slow-MA,
     `reference_package_ref`)~~ ✅ **LANDED (PR #53)**. **Kalan condition işi ARTIK LANDED:**
     ~~(i) **>2 paket** karşılaştırması (N-ary reference)~~ ✅ **PR #57** · ~~(ii) **per-condition
     multi-timeframe reference** (2. paket farklı-TF RHS)~~ ✅ **PR #56** · ~~(iii) `ta.vwap`
     directional reference key~~ ✅ **PR #58** — yalnız `ta.atr` doğası gereği yönsüz kalır (terminal sınır).
   - ~~**(c)** multi-timeframe — bar resampling~~ ✅ **LANDED (PR #55)** — indikatör blok base
     bar'lardan daha kaba bir TF'de compute eder (look-ahead yok). **(ii) multi-TF reference'ı unblock etti.**
   - ~~**(d)** daha çok directional canonical key — `ta.vwap`~~ ✅ **LANDED (PR #58)**; `ta.atr`
     doğası gereği yönsüz (volatilite bandı, cross yok) → terminal sınır.
   - ~~**`position_size_limits` (min/max cap) wiring**~~ ✅ **LANDED (PR #63)** — `_clamp_to_limits`
     `_raw_position_size → _position_size` sınırında; `ENGINE_VERSION=backtest-engine-v2-position-size-limits`;
     +15 test → 1015; migration yok. **TIER 1 backend böylece EFEKTİF TAMAM → sıradaki: TIER 2 frontend/infra.**
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

## two-package indicator-vs-indicator — ✅ LANDED (PR #53, merged → main `093df44`)

**İki AYRI pinlenmiş indikatör paketinin karşılaştırılması landed** (INF-12 Slice C follow-up).
(b2)'nin dürüst sınırını açar: bir nested `ConditionBlock` artık **2. bir indikatör paketi**
pinleyebilir; onun hesaplanan çıktı serisi condition'ın RHS'i olur — kanonik **fast-MA vs
slow-MA crossover**. Önceden RHS yalnız sabit `threshold` veya tek-paket bounded `reference`
serisi olabiliyordu. Geriye uyumlu: tüm tek-paket formlar (b2) ile birebir aynı; **engine
DEĞİŞMEDİ** (reference serisi evaluator içinde kendi hesaplanır). run / manifest / result
sözleşmeleri sabit. +12 test → **928**, review APPROVE 0/0, **migration YOK**.

Reuse anchor'ları:
- **`domain/strategy/config.py`** — `ConditionBlock` +`reference_package_ref: PackageReference | None`
  (default `None`; Pydantic/JSONB, geriye uyumlu, **migration YOK**). Set ise sabit threshold /
  bounded reference serisinden **önceliklidir**.
- **`domain/backtest/indicators.py`** — `ConditionSpec` +`reference_key`/`reference_length`. YENİ
  `_build_reference_indicator(key, length)` factory **`_MovingAverage`/`_Rsi`'yi reuse eder**
  (`ta.rsi` → Wilder RSI, aksi MA — `BlockEvaluator`'ın compute seçimini yansıtır).
  `ConditionEvaluator` +`_ref_indicator` slot, her bar **`close`'dan inline ilerletir**
  (`.update(close)`); `_rhs_value` precedence: **reference indikatör değeri > bounded `reference`
  serisi > sabit `threshold`**. Isınan reference indikatör `None` döner → **fail-closed** (LEVEL ve
  CROSS), tıpkı eksik seri gibi.
- **`application/queries/indicator_plan.py`** — YENİ `_resolve_reference_package(session, cond) →
  (key, length, reason)`: 2. paketin revision'ını `_primary_directional_key(revision.dependency_snapshot)`
  ile `DIRECTIONAL_KEYS` kanonik key'e + look-back'e (`_int_override(_REFERENCE_LENGTH_KEYS)` —
  `reference_length`/`compare_length`/`reference_len` — yoksa `default_length(key)`) çözer. 2. paketin
  **gövdesi ÇALIŞTIRILMAZ.** `_resolve_condition` precedence: reference paketi → bounded reference →
  threshold. **Fail-closed reason'lar:** `condition_reference_package_unresolved` (revision yok),
  `condition_reference_no_series` (key computable `DIRECTIONAL_KEYS` MA/RSI serisi değil),
  `condition_reference_package_on_range` (`cond.between` RANGE condition üstünde reference paketi =
  misconfig; sessizce yutulmaz, yüzeye çıkar). Docstring dürüst-sınır güncellendi.
- **`domain/backtest/manifest.py`** — `ENGINE_VERSION = "backtest-engine-v2-indicator-vs-indicator"`
  (`execution_key` namespace shift — yeni RHS kaynağı sonucu değiştirir, stale condition-extensions
  sonucu yeniden kullanılmaz; INF-04/INF-05). `apps/seed.py` DEĞİŞMEDİ (yeni RHS mevcut pinlenmiş
  pakete biner; yeni `cond.*` resolver key yok).
- **Testler (+12):** `tests/unit/test_backtest_indicator_vs_indicator.py` (+6: reference-pkg LEVEL/EDGE
  compute, warm-up fail-closed, threshold'a precedence, RSI reference key, **flagship condition-only
  fast(2)/slow(4) MA-cross → long entry**) + `tests/integration/test_condition_plan_resolution.py`
  (+6: `_cblock`'a `reference_package_rev`/`reference_length` parametreleri; resolve + 3 fail-closed
  yol + gerçek yayınlanmış 2-paket MA-cross e2e long entry).

**Kalan condition işi (yeni dürüst sınır):** (i) **>2 paket** karşılaştırması (N-ary reference
şeması ister, tek `reference_package_ref` yetmez); (ii) **multi-timeframe reference** (2. paket
trigger TF'inde `close`'dan hesaplanıyor — farklı-TF RHS (c) multi-TF resampling'e bağlı);
(iii) **non-MA/RSI reference key** (reference paketi `DIRECTIONAL_KEYS` MA/RSI serisine çözülmeli;
`ta.atr`/`ta.vwap` RHS (d)'ye bağlı).

## (b2) condition extensions — ✅ LANDED (PR #51, merged → main `6913b0a`)

**Crosses + between + series-vs-series + condition-only directional signals landed** (INF-12
Slice C follow-up b2). (b)'nin threshold-only gate'ini genişletir; **tek-paket** condition
compute'un dürüst sınırıdır. `indicator_output_plus_condition` artık **RESOLVED** ((b)'de
deferred'di). Geriye uyumlu: native trigger'lar ve native-gated `cond.above`/`cond.below`
(b)/(Slice C) ile birebir aynı. run / manifest / result sözleşmeleri sabit. +24 test → **916**,
review APPROVE 0/0, migration YOK.

Reuse anchor'ları:
- **`domain/backtest/indicators.py`** — `CONDITION_KEYS` artık 5: `cond.above`/`below` (LEVEL),
  `cond.crosses_above`/`crosses_below` (EDGE: prev on/under RHS → now strict over/under;
  `_prev_source`/`_prev_rhs` takibi; warm-up `None` fail-closed), `cond.between` (RANGE: strict
  `lower < source < upper`, non-directional). `CROSS_CONDITION_KEYS`/`RANGE_CONDITION_KEYS`;
  `condition_direction()` (crosses_above→long, crosses_below→short, else None). `ConditionSpec`
  +`lower`/`upper`/`reference` (threshold artık Optional); `ConditionEvaluator._rhs_value`
  (reference serisi VEYA sabit threshold) → series-vs-series. `IndicatorSpec` +`condition_only`
  (default False); `BlockEvaluator` condition_only modu: native `_detect` ATLANIR, sinyal
  `_conditions_satisfied` gate'inin **YÜKSELEN EDGE**'inde (`_prev_gate`) ateşler, yön
  `_condition_only_direction(spec)` (required cross'ların ortak polaritesi), block validity
  kadar tutulur, `block.direction` ile filtrelenir; `current_signal` condition_only'de
  `_active_dir` döner (yeniden gate yok), native mod bire bir eski.
- **`application/queries/indicator_plan.py`** — `_ACCEPTED_TRIGGERS` += `indicator_output_plus_condition`;
  `_resolve_condition`: `between` (`lower`/`upper` ZORUNLU + `lower < upper`, yoksa
  `condition_bounds_missing`/`condition_bounds_invalid`), `reference` (`_reference_override` →
  reference varsa threshold OPSİYONEL). `condition_only` validasyonu:
  `_condition_only_direction_reason` → required'da tek cross polaritesi yoksa
  `condition_only_no_directional_edge`, çelişkili crosses ise `condition_only_conflicting_direction`
  (FAIL-CLOSED, tüm blok unresolved). **DÜRÜST SINIR (docstring'de):** iki AYRI paket
  karşılaştırması 2. `package_ref` (şema genişletmesi) ister, kapsam dışı.
- **`domain/backtest/manifest.py`** — `ENGINE_VERSION = "backtest-engine-v2-condition-extensions"`
  (`execution_key` namespace shift — stale condition-blocks sonucu yeniden kullanılmaz, INF-04/INF-05).
- **`apps/seed.py`** — `_ESP_COND_RESOLVERS` += `cond.crosses_above`/`below` (`["series","float"]`)
  + `cond.between` (`["series","float","float"]`).
- **Testler (+24):** `tests/unit/test_backtest_condition_extensions.py` (crosses edge semantiği,
  between range, series-vs-series, condition_only yön + edge-fire) + `test_condition_plan_resolution.py`
  yeni fail-closed yollar; bir mevcut test repoint.

**Kalan condition işi (dürüst sınır):** ~~indicator-vs-indicator — İKİ AYRI paket karşılaştırması
(fast-MA vs slow-MA)~~ ✅ **LANDED (PR #53, yukarı bkz.)** — `reference_package_ref`. Şimdi kalan:
>2 paket / multi-timeframe reference / non-MA-RSI reference key (yukarıdaki #53 bölümüne bkz.).

## (b) condition blocks — ✅ LANDED (PR #49, merged → main `6854e06`)

**Threshold-only nested condition GATE landed** (INF-12 Slice C follow-up b). Kapsam
kararı: yalnız **`indicator_native_trigger_plus_condition`** (native trigger + threshold
gate) modellendi; **`indicator_output_plus_condition` bilinçli olarak `unresolved`
bırakıldı** (condition-only yön sinyali edge/direction mapping ister — ayrı dilim).
Reuse anchor'ları: `domain/backtest/indicators.py::ConditionSpec/ConditionEvaluator/
_conditions_satisfied` + `BlockEvaluator.current_signal` gate; `indicator_plan.py::
_resolve_conditions/_resolve_condition/_primary_condition_key/_source_override` (fail-closed);
`engine.py` full-OHLC besleme + `condition_blocks` diagnostics; `manifest.py` ENGINE_VERSION
`backtest-engine-v2-condition-blocks`; `apps/seed.py::_seed_esp_resolver` + `_ESP_COND_RESOLVERS`
(`cond.above`/`cond.below`). Threshold zorunlu (override), source default `close`. +28 test,
review APPROVE 0/0, migration yok. Kalan condition işi: `indicator_output_plus_condition`,
zengin primitive'ler (crosses, indicator-vs-indicator, ranges). Aşağıdaki **keşif bölümü
tarihsel referans** olarak duruyor.

### Keşif (tarihsel — (b) için, artık LANDED)

**KEŞİF (bu oturumda çıkarıldı — taze oturum tekrar keşfetmesin):**

- **Şema hazır (dokunma):** `domain/strategy/config.py` — `IndicatorBlock.trigger_source ∈
  {indicator_native_trigger, indicator_native_trigger_plus_condition,
  indicator_output_plus_condition}` (son ikisi bugün unresolved). `IndicatorBlock` içinde iç içe
  `condition_blocks: list[ConditionBlock] | None` + `condition_block_rule`
  (`required_condition_blocks_only` / `required_plus_any_supporting` /
  `required_plus_min_supporting` / `required_plus_all_supporting`) + `min_supporting_condition_count`.
  `ConditionBlock` = pinned **condition** `package_ref` (ayrı `condition` paket tipi,
  `domain/package/kind.py`) + `requirement` (required/supporting) + `validity` penceresi +
  `parameter_overrides`.
- **Bugünkü davranış:** `application/queries/indicator_plan.py::_resolve_block` (satır ~106)
  `trigger_source != "indicator_native_trigger"` → `trigger_source_deferred:<source>` unresolved;
  `condition_blocks` hiç okunmuyor.
- **KRİTİK — condition primitive katmanı SIFIRDAN gerekli:** bugün seed'li **hiç `cond.*`
  canonical key yok** — `indicators.py`/ESP registry yalnız `ta.*` seed'i içeriyor
  (`apps/seed.py::_ESP_TA_RESOLVERS`). Bu yüzden (b) = (1) yeni `cond.*` key ailesi + compute
  (threshold-only) + ESP seed (`apps/seed.py`), (2) plan resolution — `..._plus_condition`
  trigger'ları için `condition_blocks`'u dereference edip condition spec'lere çöz
  (`indicator_plan.py`), (3) engine gating — `BlockEvaluator`/`aggregate`'i "native trigger
  AND condition(lar) doğru" + `condition_block_rule` aggregation uygulayacak şekilde genişlet
  (`indicators.py` + `engine.py`), (4) testler (unit compute + plan resolution integration +
  engine gating + e2e yayınlanmış condition paketi).
- **Karar (taze oturumda):** `indicator_output_plus_condition` (native trigger yok, sadece
  condition sinyali) de mi kapsanacak, yoksa ilk sürüm `indicator_native_trigger_plus_condition`
  (native trigger + condition gate) ile mi sınırlı? Threshold semantiği reproducibility sabiti
  olmalı (parametre override yoksa engine-version default), ENGINE_VERSION bump gerekir.

## Yöntem (değişmedi)

- Workflow KULLANMA — doğrudan yaz; YENİ dosya Bash heredoc (gate-free), mevcut dosya Edit 4-fact.
- `cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy src` +
  izole DB'de `uv run pytest --no-cov -q` (**928 yeşil kalmalı**); migration gerekirse
  `0022_*` (→0021) up/down/up + parity + L1 FK proof.
- code-reviewer subagent → CRITICAL/HIGH **AMPİRİK DOĞRULA** (8a: 0; 8b: 2/2 GERÇEK; auth: 0;
  parquet: 1/1 GERÇEK; engine Slice B: 1 CRITICAL/1 GERÇEK — oran değişken, HER ZAMAN doğrula) →
  commit (conventional, attribution YOK) → PR → `gh pr checks --watch` → merge için kullanıcıya
  sor. Türkçe, MALİYET BİLİNÇLİ.

---

## ⤵️ YENİ OTURUMDA YAPIŞTIR (resume prompt)

```
Entropia — post-V1 TIER 2 (FRONTEND). Backend TIER 1 EFEKTİF TAMAM (V1 + Auth/IdP #38 + Parquet
A #41 + bar-replay B #43 + indikatör compute C #45 + risk_based #47 + condition blocks #49 +
extensions #51 + indicator-vs-indicator #53 + multi-TF #55 + per-condition-TF #56 + N-ary #57 +
VWAP #58 + Kelly #60/#61 + position_size_limits #63 — HEPSİ MERGED). FRONTEND: gerçek auth
login/signup/logout landed (PR #65 — merge KULLANICIDA; frontend-only, backend değişmedi, backend
test tabanı 1015 SABİT).

ÖNCE DOĞRULA (stale-by-default): git fetch && git log --oneline origin/main -6 && gh pr list
--state all -L 8. PR #65 (feat/post-v1-frontend-login) + docs PR'ı MERGE OLDU MU teyit et. Backend
main = 97b10b8 (Merge #63) → docs #64 = 3594a58; alembic head 0021_local_auth;
ENGINE_VERSION = backtest-engine-v2-position-size-limits. FRONTEND doğrula:
cd frontend && npm run typecheck && npm run lint && npm test && npm run build (login sonrası 9/9).

ÖNCE OKU: docs/POST_V1_KICKOFF.md (en üst Durum bloğu — TIER 2 frontend login PR #65) +
docs/STAGE2_HANDOFF.md ("Frontend real-auth login/signup/logout ... landed (PR #65)" + "Next: TIER 2
frontend — SSE live-invalidation + metrics dashboard remain").

FRONTEND STACK: Vite 8 + React 18 + react-router 6 + @tanstack/react-query 5 + react-hook-form +
vitest/jsdom + @testing-library. Alias @ = src; kök frontend/src/. Auth ZATEN bağlı (lib/session.ts
store + lib/auth.ts hooks + apiClient Bearer header + pages/Login.tsx + /login route + Layout
AuthControl). Node >=20.19.

SIRADAKİ İŞ (kullanıcıyla SEÇ) — kalan TIER 2 frontend adayları:
- (a) SSE LIVE-INVALIDATION (ÖNERİLEN, küçük/saf infra): frontend/src/lib/sse.ts stub'ı ŞU AN yalnızca
  heartbeat dinliyor + queryClient KULLANILMIYOR (Stage 1+ TODO). Backend /events taksonomisi
  (backend .../apps/api/sse.py::sse_event_name): backtest.run.updated / job.updated / agent.task.updated /
  audit.event.created / resource.changed (+heartbeat; data = tam outbox JSON). Bunları addEventListener
  ile ilgili query key'lere queryClient.invalidateQueries([...]) map et → canlı backtest/job/agent
  progress. İzole vitest ile test (EventSource mock).
- (b) /v1/metrics DASHBOARD: GET /v1/metrics PROMETHEUS-TEXT döner (PlainTextResponse, JSON DEĞİL —
  backend .../apps/api/routes/metrics.py:53). Exposition parser + golden-signals / jobs-depth /
  outbox-lag / lease-age panelleri. En zahmetli (metin parse), en az temiz kontrat.
- (c) capability aktivasyonları (role-gated), (d) first-Admin provisioning dashboard.
TIER 3 (deferred): retention auto-purge, data-queue redelivery, SSE streaming e2e (connection drops),
tool-call status shadowing (CR-08 follow-up).

BACKEND REUSE ANCHOR'LARI (frontend'in bağlanacağı HAZIR kontratlar — DEĞİŞTİRME, TÜKET):
- SSE: backend .../apps/api/sse.py (SseHub / run_outbox_poller / sse_event_name); GET /events
  (EventSourceResponse); .../application/jobs/outbox_relay.py (fetch_events_after / latest_event_id).
- Metrics: GET /v1/metrics (Prometheus text; golden signals + jobs depth + outbox lag + lease age).
- Auth: /v1/auth/* + /me (frontend'de zaten bağlı).

YÖNTEM: Workflow KULLANMA; direct-author. Bu slice FRONTEND — backend working-loop (izole DB / L1 FK /
alembic) UYGULANMAZ. Frontend loop: cd frontend (cwd resetlenebilir → absolute path); npm run typecheck
&& npm run lint && npm test && npm run build + yeni component/unit test. YENİ dosya heredoc (gate-free),
mevcut dosya Edit 4-fact (GateGuard: ilk Bash + dosya-başına-ilk-edit + docs da gate'lenir).
CRITICAL/HIGH AMPİRİK DOĞRULA → commit (conventional feat(post-v1)/branch feat/post-v1-frontend-<slug>,
attribution YOK) → PR → gh pr checks --watch (frontend+docker check; backend değişmediği için yeşil) →
merge KULLANICIDA. Türkçe, MALİYET BİLİNÇLİ. Kapanışta: handoff + kickoff + CLAUDE.md + memory
(ecc knowledge graph; claude-mem token stale/worker-modda atlanabilir).
```
