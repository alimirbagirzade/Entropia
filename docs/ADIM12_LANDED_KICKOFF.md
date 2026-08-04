# ADIM 12 landed — Bağımsız finansal oracle baseline'ı (PR #553) · sıradaki slice kickoff'u

> Bu belge **ADIM 12'nin** kapanış handoff'udur. En altta **paste-ready resume prompt** var.

## Nerede duruyoruz

| | |
|---|---|
| ADIM 12 | commit `b5c7c44` · base `061d6d7` · **PR #553 merge bekliyor** |
| Alembic head | `0043_i08_registry_strategy_fks` — tek head, **migration EKLENMEDİ** |
| OpenAPI | **196 operation / 151 schema** — değişmedi |
| `ENGINE_VERSION` | `backtest-engine-v18-same-candle-entry-exit` — **değişmedi** |
| Production kod | **DEĞİŞMEDİ** — slice tamamen additive (9 test dosyası + 1 doküman) |
| Testler | backend full suite **exit 0**, coverage **%92.84**; oracle paketi 78 passed + 1 xfailed |
| Açılan issue'lar | **#549** (high) · **#550** (high/ürün) · **#551** (medium) · **#552** (medium) |

**Bir sonraki base:** PR #553 + #554 merge edildikten sonraki `origin/main`. ADIM 12
`061d6d7`'den dallandı; o sırada **ADIM 11 (PR #548) paralel merge oldu** ve `origin/main`
`83739ad`'e ilerledi, kapanış dokümanları ADIM 11'in üzerine yeniden kuruldu. Merge'i
doğrulamadan dallanma — `origin/main` bu seri boyunca oturum ortasında ilerliyor.

## ADIM 12 ne bıraktı — reuse anchor'ları (tam sembol adlarıyla)

**Yeni paket: `backend/tests/unit/oracles/`**

| Modül | İçerik / ne öğretir |
|---|---|
| `__init__.py` | Paketin sözleşmesi: beklenen değer engine helper'ından ÜRETİLMEZ |
| `harness.py` | `FLAT_BARS` · `FLAT_PRICE` · `SIGNAL_BAR_SEQ` · `INITIAL_CAPITAL` · `bar()` · `bar_time()` · `flat_run()` · `batched()` · `entry_plan()` · `entry_and_exit_plan()` · `oracle_config()` · `run_oracle()` — **sadece girdi kurar, hiçbir beklenti hesaplamaz** |
| `test_oracle_entry_exit_timing.py` | timing → fill fiyatı eşlemesi; gap-open no-lookahead kalıbı |
| `test_oracle_costs.py` | `_costs()` override kalıbı; `_schedule()` — `(event_day, available_day, rate)` üçlüsü, **iki zamanı AYRI tutar** |
| `test_oracle_orders.py` | `_limit()` / `_stop()` order-config kurucuları |
| `test_oracle_protection_stops.py` | `_collision()` — stop+exit çakışma politikası matrisi; `xfail(strict)` kalıbı (#549) |
| `test_oracle_sizing.py` | `_sized()` · `_entry_size(out)` — `entry_fill` event'inden size okuma |
| `test_oracle_position_lifecycle.py` | `_partial()` · `_scaled()` · `_LADDER` · `_HOLD_THROUGH_OPPOSITE` |
| `test_oracle_properties.py` | `_sma_plan()`; batch-invariance ve MTF closed-bar kalıpları |

**Yeni doküman:** `docs/audit/backtest_oracle_fixtures.md` — her fixture'ın el hesabı,
**spec-open konvansiyon tablosu** (§5) ve dört bulgunun künyesi (§6).

## Fixture geometrisini kuran üç bilgi (yeni senaryo yazarken gerekir)

1. **20 düz bar @100 → 20-bar SMA tam 100.** Bar 21 hangi yöne kapanırsa o yöne kesişir;
   sinyal barı `SIGNAL_BAR_SEQ == 21`, indikatör implementasyonunu okumadan bilinir.
2. **`validity="current_candle_only"` sinyali EDGE yapar** — sonraki barlar sessizce yeni
   giriş ateşleyemez. `until_opposite_signal` kullanırsan elle hesapladığın ledger bozulur.
3. **Bar 22'yi kurarken üç kural aynı anda çalışır** ve birbirini ezer:
   * SMA'nın altına kapanmak **ters yön sinyali** üretir → `exit_on_opposite_signal` (varsayılan
     `True`) long'u kapatır. Scaling/ladder testi istiyorsan
     `conflict={"exit_on_opposite_signal": False, "opposite_direction_hedge": "ignore"}`
     kullan — **sadece** `exit_on_opposite_signal: False` verirsen
     `conflict_handling_is_modelled` FALSE döner ve engine hiçbir şey açmaz (hedge fail-closed).
   * Exit kuralı giriş barında da ateşlerse `same_candle_entry_exit` çakışması olur;
     varsayılan `use_intrabar_data_if_available` **hiç giriş açmaz**. Partial-close testi için
     `conflict={"same_candle_entry_exit": "exit_first"}` gerekir.
   * Aktif bir koruma stop'u varsa `stop_has_priority` exit sinyalini ezer. Exit-sinyali
     davranışını izole etmek için `protection={}`.
4. **`price_scaling.retracement_distance` YÜZDEdir**, fiyat birimi değil
   (`scale_threshold_crossed`: `step = reference * distance_pct / 100`).

## Bir sonraki slice için tasarım işaretleri

**Sıradaki tek adım bir KARAR, kod değil: #549.** Gap-adjusted stop icrası
(`long: min(level, bar.open)`, short aynası) `ENGINE_VERSION` bump'ı gerektiriyor ve bu karar
**unified clock'tan ÖNCE** verilmeli. Sebep: iki semantik değişikliği tek golden-digest
tazelemesinde ayırt edemezsin — saat değişimiyle stop fiyatı değişimi aynı digest'te
karışırsa hangisinin neyi kaydırdığı kanıtlanamaz.

**#550 ayrı bir ürün kararı** (`base_position_size` birim mi yüzde mi). Unified clock'u
bloke etmez, ama karara bağlanmadan sizing üzerine yeni iş yapılmamalı — saved revision
migration'ı gerektiriyor.

**Oracle paketinin ikinci dalgası** (bu slice'ın bilerek ertelediği): tick/print icra modları
— `intrabar_touch`, `limit_fill_simulation`, `stop_limit_priority_simulation` ve `not_allowed`
dışı partial-fill politikaları. Bunlar `tick_data_required(config)` (yani
`intrabar_policy.tick_policy == "require"`) + `run_engine(tick_batches=…)` istiyor;
kalıp `tests/unit/test_backtest_tick_data.py` ve `test_backtest_intrabar_execution.py`'de.

**REUSE listesi:** `harness.oracle_config()` (her yeni senaryo), `_entry_size(out)` (size
okuması), `_schedule()` üçlüsü (available-time ayrımı gereken her research verisi),
`xfail(strict=True)` + issue numarası (bulunan her uyuşmazlık — testi engine'e uydurmak yerine).

## Çalışma döngüsü (ADIM 12'de işe yarayan)

1. `git fetch --all --prune` → **PR #553'ün merge edildiğini doğrula** → `git switch -c <branch> origin/main`.
2. Kanonik kuralı **spec'ten** çıkar (read-only subagent iyi çalıştı: Master Ref + ilgili sayfa
   dokümanı, "FORMULA FIXED / FORMULA OPEN" verdict'i isteyerek). **Spec'in çoğu icra
   aritmetiğini engine manifest'ine bıraktığını baştan kabul et** — bulduğun sessizliği
   "canon böyle diyor" diye raporlama.
3. Beklenen değeri **elle** hesapla, literal yaz. Sonra koş. Uyuşmazlıkta önce **kendi
   matematiğini** yeniden türet; engine haklıysa oracle'ı düzelt ve kuralı docstring'e yaz,
   engine hatalıysa `xfail(strict)` + issue.
4. Geometriyi probe ile doğrula (scratchpad script'i, `PYTHONPATH=. uv run --extra dev python`) —
   40 test yazıp hepsinin birden kırmızı gelmesini beklemekten çok daha ucuz.
5. Lokal kapı: `uv run ruff check . && uv run ruff format --check . && uv run mypy src` +
   **`TEST_DATABASE_URL=postgresql+asyncpg://…` ile** tek pytest çağrısı.

## Ortam tuzakları (kaydedilmeli)

* **`TEST_DATABASE_URL` sürücüsü `postgresql+asyncpg://` olmalı.** `postgresql+psycopg://`
  integration conftest'ini `create_async_engine`'de patlatıyor → **2319 ERROR**, testlerle
  ilgisi yok. Worktree'ye özel DB adı kullan (`…/entropia_oracle_wt`).
* Full suite lokalde **~35 dakika**; Bash tool timeout'u 10 dakikada tavanlı → `run_in_background`
  ile koş, çıktıyı dosyaya yaz, exit code'u **ayrı** oku (`| tail` KULLANMA — exit code `tail`'in olur).
* `uv run python` (dev extra'sız) venv'i dev bağımlılıkları olmadan kurar; sonra `pytest`
  bulunamaz. Probe script'lerinde de **`uv run --extra dev`** kullan.

---

## Paste-ready resume prompt

```
ENTROPIA V18 — ADIM 13: <BAŞLIK BURAYA>

ROL VE ÇALIŞMA BİÇİMİ

Sen Entropia V18 üzerinde çalışan kıdemli principal engineer ve release-closure
sorumlususun. Amaç yeni özellik icat etmek değil; canonical Production V1 sözleşmesini
current `origin/main` üzerinde kanıtlamak, yalnız doğrulanmış boşluğu dar bir PR ile
kapatmak ve sistemi geriletmemektir.

Read-only subagent'ları araştırma/inceleme için kullan; production değişikliklerini
yalnız ana oturum yapsın; tek branch, tek PR, tek sorumlu writer.

HER OTURUMUN ZORUNLU BAŞLANGICI

1. `git fetch --all --prune` · `git status --short` — temiz değilse DUR.
2. `git reset --hard origin/main`; current main SHA + açık PR/issue snapshot'ı al.
3. **PR #553 (ADIM 12 oracle baseline) ve #554 (kapanış dokümanları) merge edildi mi
   doğrula; edilmediyse DUR.**
4. `docs/ADIM12_LANDED_KICKOFF.md` (bu belge) + `docs/audit/backtest_oracle_fixtures.md`
   §5–§6'yı oku — hangi sayının kanon, hangisinin sevk edilmiş konvansiyon olduğunu
   ayıran tek belge o.
5. İlgili `docs/CODEMAPS/` haritasını ve gerçek çağrı zincirini oku.
6. Eski README/CLAUDE.md/handoff/backlog iddiasını current truth sayma.
7. Önce mevcut davranışı test/probe ile yeniden üret; kusur üretilemiyorsa kod yazma.

BU ADIMIN AMACI

<BRIEF BURAYA>

AÇIK KARARLAR (ADIM 12'nin bıraktığı — biri seçilmeden engine aritmetiğine dokunma)

- #549 (high): gap'le atlanan koruma stop'u ulaşılamayan seviyeden kayıt açıyor.
  Düzeltme `ENGINE_VERSION` bump'ı + golden digest tazelemesi ister ve **unified
  clock'tan ÖNCE** kararlaştırılmalı. Aritmetik repo'da `xfail(strict)` olarak duruyor:
  tests/unit/oracles/test_oracle_protection_stops.py
- #550 (high/ürün): `base_position_size` birim adedi mi, resolved capital yüzdesi mi.
  Saved revision migration'ı ister.
- #551 / #552 (medium): 0-size hayalet trade; kısmi kapanışta 1.4 komisyon round-trip.
- #539 (CRITICAL, ADIM 11'den): 22 `future_dev` satırının 11'i Strategy formunda devre dışı
  bırakılmıyor. #549'dan bağımsız, engine aritmetiğine dokunmuyor.

TAVİZ VERİLEMEZ KURALLAR

Trading Signal ve Trade Log Package değildir. Backtest Run ile Result aynı entity
değildir; yalnız SUCCEEDED Run immutable Result üretir. Agent human account değildir.
Uzun işler durable queue üzerinden yürür. UI hidden/disabled durumu authorization
değildir. Server-side policy, ownership, OCC, idempotency, audit ve lifecycle korunur.
Revision/snapshot/fingerprint/manifest/pinned revision geriye dönük bozulmaz. Research
Data için event_time ve available_time ayrımı korunur. Canonical boşlukta formül,
öncelik, time ordering veya ürün kararı UYDURULMAZ — boşluğu boşluk olarak raporla.
Historical Result canlı root/live registry join'iyle yeniden yorumlanmaz. Başarısız
test varken `Complete` yazılmaz.

ZORUNLU DOĞRULAMA

- `cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy src`
- `TEST_DATABASE_URL=postgresql+asyncpg://entropia:entropia@localhost:5432/<wt>_db`
  ile **tek** pytest çağrısı, arka planda, çıktı dosyaya, exit code ayrı okunur.
- Golden digest ve engine suite'leri korunur; oracle paketi onların yerine geçmez.

PR DİSİPLİNİ

Yalnız bu slice. İlgisiz refactor/dependency/görsel değişiklik yok. Migration varsa
single-head + up/down/up kanıtı. Engine semantiği değişiyorsa `ENGINE_VERSION` kararını
açıkça değerlendir. Public API değişiyorsa OpenAPI snapshot + frontend wire contract.
Claude merge etmez, tag/release oluşturmaz. PR sonunda base SHA, branch, commit, PR,
changed behavior, unchanged boundaries, targeted tests, full-suite exit code,
migration/OpenAPI/codemap etkisi, kalan risk ve sonraki tek adım raporlanır.
```
