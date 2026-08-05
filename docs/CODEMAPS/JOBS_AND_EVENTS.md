# JOBS_AND_EVENTS — async düzlem

İki bağımsız async yol:
1. **dramatiq aktörleri** — durable iş yürütme (`apps/worker/actors.py`).
2. **Transactional outbox → SSE** — değişiklik yayını (`application/jobs/outbox_relay.py` → `apps/api/sse.py`).

Ortak ilke: **`jobs` tablosu + domain satırı tek gerçek kaynağıdır**; broker mesajı yalnızca
transport'tur. Mesaj kaybolursa scheduler sweep'i (INF-03/INF-09) işi geri getirir.

---

## dramatiq aktörleri (`apps/worker/actors.py`)

| Aktör | Kuyruk | Satır | Gövde (`application/jobs/`) |
|---|---|---|---|
| `system_heartbeat` | `maintenance` | `:39` | (scheduler tick ping'i) |
| `run_market_data_analysis` | `data` | `:45` | `market_data.py` |
| `run_research_data_analysis` | `data` | `:72` | `research_data.py` |
| `run_trading_signal_import` | `data` | `:99` | `trading_signal.py` |
| `run_trade_log_import` | `data` | `:126` | `trade_log.py` |
| `run_backtest_engine` | `backtest` | `:153` | `backtest_engine.py` |
| `run_agent_tool` | `agent` | `:181` | `agent_tools.py` |
| `run_agent_tool_high` | `agent-high` | `:193` | `agent_tools.py` |
| `run_agent_executor` | `agent-executor` | `:216` | `agent_executor.py` |
| `run_create_package_job` | `default` | `:245` | `create_package.py` (kind-dispatch) |
| `run_trash_purge` | `maintenance` | `:274` | `purge.py` |
| `run_package_import` | `data` | `:301` | `package_import.py` |

Tüm aktörler `max_retries=3`.

### Yürütme modeli — sync gövde → async gövde (ZORUNLU: `run_sync`)

Her aktör gövdesi async gövdesine **`infrastructure/async_runtime.py::run_sync`** ile geçer;
**`asyncio.run` YASAK**. `asyncio.run` her mesajda loop'u kapatır, oysa
`postgres/engine.py::get_engine` `@lru_cache(maxsize=1)`'dir → asyncpg pool'u **process-wide**
ve her loop'tan uzun yaşar. dramatiq çok thread'li çalıştığı için bir thread'in loop'unda
doğan bağlantı başka thread'in loop'unda check-out edilir ve asyncpg
`got Future ... attached to a different loop` atar; mesaj `max_retries`'i tüketir ve broker onu
**düşürür**. `data` kuyruğunda bu **kurtarılamaz** (aşağıdaki tabloya göre otomatik redelivery
yok) — satır sonsuza dek `queued` + `attempts = 0` kalır. `run_sync` process başına **tek**
uzun ömürlü loop kullanır (ayrı daemon thread), böylece pool loop'undan asla uzun yaşamaz.
Regresyon: `tests/unit/test_async_runtime.py` (AST guard) +
`tests/integration/test_worker_actor_event_loop.py` (gerçek engine, eşzamanlı gövdeler).

## Kuyruklar

| Kuyruk | Aktör sayısı | Otomatik redelivery? | Compose tüketicisi |
|---|---|---|---|
| `data` | **5** (çok-aktörlü) | ❌ **Hayır** — kasıtlı olarak `ACTOR_BY_QUEUE` dışında | `worker-data` |
| `backtest` | 1 | ✔ | `worker-backtest` |
| `agent` | 1 | ✔ | `worker-agent` |
| `agent-high` | 1 | ✔ | `worker-agent` |
| `agent-executor` | 1 | ✔ | `worker-agent-executor` (**ADIM 21'de eklendi**) |
| `default` | 1 (`run_create_package_job`) | ✔ | `worker-default` |
| `maintenance` | 2 (`system_heartbeat`, `run_trash_purge`) | ✔ (`run_trash_purge`) | `worker-default` |

> **ADIM 21 bulgusu.** `agent-executor` kuyruğunun compose'da **hiç tüketicisi yoktu**:
> Coordinator ona iş gönderiyor, scheduler her grace penceresinde yeniden yolluyor, `send`
> her seferinde BAŞARILI dönüyor ve görev asla koşmuyordu — hiçbir katman hata bildirmiyor.
> `tests/unit/test_worker_plane_deployment.py` artık `docker-compose.yml`'i okuyup
> aktör-kuyruk kümesiyle karşılaştırıyor; tüketicisiz her durable kuyruk CI'da kırmızı.
> `system_heartbeat` durable job satırı üretmez (gövdesi `job_id` almaz), bu yüzden
> `maintenance` fiilen **tek** durable aktörlüdür — `ACTOR_BY_QUEUE` girdisi güvenlidir
> (`tests/unit/test_worker_queue_registry.py` bunu invariant olarak pinliyor).

### Neden `data` özel

`data` kuyruğu dört+bir durable aktör tipini multiplex eder. Scheduler, durable satırdan hangi
aktöre gideceğini **çıkaramaz** → otomatik sweep bu kuyruğu asla yönlendirmez
(`apps/scheduler/__main__.py:69` yorumu: *"Queues with exactly ONE durable-job actor are safe to auto-redeliver"*).

Bunun yerine **operator eylemi** vardır: `POST /admin/data-queue/redeliver`
(`routes/admin_panel.py:205` → `commands/data_queue.py::redeliver_data_queue_jobs`), payload'daki
`job_kind` ayırıcısını `DATA_ACTOR_BY_KIND` (`actors.py:334`) ile eşleyerek yönlendirir.

**Ama atlamak SESSİZ değildir.** Re-dispatch operator eylemi olarak kalır; yalnız her tick'te
`_redeliver` yönlendiremediği adayları **`scheduler.redeliver_unroutable`** uyarısıyla bildirir
(alanlar: `queue`, `count`, ilk `_UNROUTABLE_SAMPLE=20` `job_ids`). Adaylar zaten redeliver grace
penceresini aşmış satırlardır, yani sağlıklı bir in-flight iş bu dalı hiç görmez — uyarı ancak
gerçekten sıkışmış bir iş varsa çıkar. Bu, kaybolan bir `data` mesajının tek izinin "kimsenin
izlemediği bir `queued` satır" olması durumunu kapatır. Davranış değişmedi: hiçbir şey otomatik
redeliver edilmez.

**`job_kind` taksonomisi** (`application/jobs/data_queue.py:31-37`, `DATA_JOB_KINDS:37`):
`market_data_analysis` · `research_data_analysis` · `trading_signal_import` · `trade_log_import` · `package_import`

Discriminator taşımayan eski satırlar → `skipped_unknown_kind` (asla tahmin edilmez).

### `default` kuyruğu — Create-Package tek-aktör dispatch (F-01a + F-01b + F-01c)

`default` kuyruğunda **tek** durable aktör vardır (`run_create_package_job`), bu yüzden scheduler
sweep'i (stale-RUNNING kurtarma + kayıp mesaj redelivery, INF-03/INF-09) otomatik çalışır.
Aktör gövdesi `application/jobs/create_package.py::run_create_package_job`, durable
`jobs.payload["kind"]` ayırıcısını okuyup yönlendirir:

| `kind` | Worker gövdesi | Admission komutu | Terminal durumlar |
|---|---|---|---|
| `precheck` | `run_precheck_job` | `cp_cmd.run_precheck` | `precheck_passed/blocked/not_applicable` · hata → `precheck_failed` |
| `candidate_generation` | `run_candidate_generation_job` | `cp_cmd.submit_candidate_generation` | `candidate_ready` · hata → `candidate_failed` |
| `validation` | `run_validation_job` | `cp_cmd.start_package_validation_run` | `eligible_for_approval` / `revision_required` · hata → FAILED run + `revision_required` |
| `baseline_parse` | `run_baseline_parse_job` | `cp_cmd.start_baseline_parse` | `baseline_asset.parse_status` = `passed` · hata/parse-edilemez CSV → `failed` |

Dördü de aynı iskeleti paylaşır: terminal-job replay (at-least-once), request root kilidi,
superseded guard (admission'ın beklediği state'ten çıkmışsa hiçbir şey yazılmaz → `SUPERSEDED`),
`RUNNING` → compute → durable kanıt + state ilerlemesi + audit/outbox → `SUCCEEDED`.
Worker hatası **durable terminal** durumdur (sessiz başarı da sonsuz retry de değil).

**F-01c ile in-transaction compute kalmadı**: `baseline_parse` artık `_enqueue_create_package_job`
üzerinden admission alır (`parse_status` = `parsing`, `parse_job_id` pinlenir; payload'da
`baseline_asset_id` taşınır) ve CSV okuması worker'da yapılır. Superseded koşulu asset-scoped:
teslim anında asset artık request'in head'i değilse (yeni upload = yeni `attempt_no`) veya
`parse_status` `parsing` değilse hiçbir şey yazılmaz. `PARSE_FAILED` artık **kayıtlı failed
attempt**'tir (rapor + kod asset üzerinde) — fırlatılıp iz bırakmayan bir hata değil.
Silinen yardımcı: `_enqueue_completed_job` (eski "in-transaction stub" satırı).

### Backtest run stage stream (O-05)

`run_backtest` artık **tek** transaction değil. Her stage geçişinde
`backtest_run_event` satırı (+ audit + outbox) yazılır ve **commit edilir**:

| # | Stage | Olay (`event_type`) | Audit `event_kind` |
|---|---|---|---|
| 1 | `queued` → `provisioning` | `RUN_STARTED` | `backtest.run_started` |
| 2 | `provisioning` → `running` | `RUN_STAGE_CHANGED` | `backtest.run_stage_changed` |
| 3 | terminal | `RUN_SUCCEEDED` / `RUN_FAILED` / `RUN_CANCELLED` | `backtest.run_succeeded` / `backtest.run_failed` / `backtest.run_cancelled` |

- `sequence_no` run başına monoton, 1'den başlar; `UNIQUE(run_id, sequence_no)`
  de-dupe anahtarıdır (doc 15 §7). Replay: `GET /backtest-runs/{id}/events?last_sequence=`.
- **PROVISIONING = çözümleme** (pin re-resolve, asset/range/instrument/indicator/funding),
  **RUNNING = bar-replay**. Bu ayrım için `_prepare_and_run_strategy`,
  `_prepare_strategy` + `_replay_strategy` olarak bölündü; çözümleme hatası hâlâ
  RUNNING'e geçmeden FAILED verir.
- Outbox `resource_type = "backtest_run"` → SSE adı `backtest.run.updated` (aşağıdaki
  taksonomi tablosuna bak).
- **Controlled cancellation (O-06).** `cancel_backtest_run` worker'ı asla öldürmez;
  `backtest_run.cancel_requested_at` **niyetini** yazar. Worker bunu **dört güvenli
  kontrol noktasında** okur (`_cancellation_requested`): (1) PROVISIONING commit'inden
  hemen sonra, (2) her strateji hazırlığı arasında, (3) her bar-replay arasında,
  (4) **Result materialize edilmeden hemen önce**. 4. nokta doc 15 §16'yı fiilen
  garanti eder — ondan sonrası SUCCEEDED'dır ve geç kalan cancel dürüstçe
  uygulanmaz (komut zaten `cancellation_safe_boundary` sözü verir, `cancelled` demez).
  Terminal yazım `_cancel_run`: `cancelled` + `RUN_CANCELLED` + `backtest.run_cancelled`
  + `jobs.status = cancelled`, **BacktestResult YOK**. Kısmi teşhis olay `detail`'inde
  yaşar (`cancelled_at_stage`, `prepared/replayed_item_count`) — `diagnostic_artifact`
  satırı olarak DEĞİL, çünkü o tablo `backtest_result`'a FK ile bağlıdır (dürüst sınır).
  QUEUED/worker yarışı iki tarafın da aldığı **satır kilidi** ile kapatılır.
- **At-least-once guard değişmedi**: terminal run asla yeniden koşmaz. Terminal olmayan
  (worker öldürülmüş) bir run gerçekten yarımdır; redelivery onu yeniden dener ve aynı
  sequence'a yeni olaylar ekler.

### Manifest'in iki hash'i — `manifest_hash` vs `execution_key`

`domain/backtest/manifest.py::build_run_manifest` worker'a giden immutable manifest'i kurarken
**iki** sha256 üretir ve ikisini de saklar:

| Hash | Neyin üzerinden | Sonuç |
|---|---|---|
| `manifest_hash` | manifest'in **tamamı** (identity: `run_id`/`created_at`/`correlation_id` + `preflight` dahil) | her run ve her retry **benzersiz** — `backtest_run_manifest.manifest_hash` UNIQUE |
| `execution_key` | yalnız **reproducibility içeriği** (pinlenmiş item'lar, `capital_execution`, `engine_version`, `metric_set_version`/`output_artifact_profile`, `tick_data` + K-04 üç context) — run kimliği **DIŞLANIR** | aynı hesabı tarif eden iki run **aynı** değeri taşır — `execution_key` indeksli ama **unique DEĞİL** |

`manifest_hash` ile farkı tek cümle: biri "bu hangi run?", diğeri "bu hangi hesap?" sorusunu
yanıtlar. `preflight` bilerek `execution_key` dışındadır — bir readiness uyarısı manifest_hash'i
değiştirir, execution_key'i değiştirmez. `engine_version` ise **içindedir**: her `ENGINE_VERSION`
bump'ı tüm execution_key uzayını kaydırır, böylece eski motorun sonucu yeni motor altında yeniden
kullanılabilir sayılmaz.

**Bugün cross-run sonuç paylaşımı YOK (dürüst sınır).** `execution_key` üzerinde hiçbir sorgu
WHERE/JOIN yapmıyor; kolon yalnız yazılıyor + projeksiyonda okunuyor
(`queries/backtest_run.py:213`, `history.py`). İki run aynı anahtarı taşısa bile her biri kendi
`BacktestResult`'ını materialize eder; duplicate RUN'ı bugün engelleyen şey `Idempotency-Key`'dir.
Cross-run idempotent-reuse (INF-04/INF-05) **hazırlanmış ama bağlanmamış** — indeks var, lookup yok.
Fiilen uygulanan tek INF-04 reuse **run içidir**: `execution/portfolio.py::_fold_composite_metrics`
marginal katkı için kalan item'ları yeniden simüle etmez, mevcut çıktıları yeniden fold eder.
İkinci fiili kullanım K-09 byte-equality regresyon kapısıdır (`execution/__init__.py`).

Tam kayıt + alias tablosu ve `ExportFormat.PARQUET`: `docs/PROJECT_HISTORY.md` §"B-2".

## Scheduler (`apps/scheduler/__main__.py`)

**Süreç ömrü boyunca TEK event loop** (INF-14 / PR #593): `run():204` =
`asyncio.run(_sweep_until_stopped())`, tick içinde `await`. Tick başına `asyncio.run` havuzu
ölü loop'a bağlıyor ve passes %50 dönüşümlü düşüyordu — `get_engine` `@lru_cache`'li olduğu
için **yeni bir loop döngüye sokan her değişiklik bu kusuru geri getirir**. Engine `finally`
içinde, loop hâlâ açıkken dispose edilir (`:200`).

Durdurma: `request_stop():91` → run başına yaratılan `asyncio.Event`; SIGTERM/SIGINT
`_install_stop_handlers:147` ile `loop.add_signal_handler` üzerinden bağlanır (`signal.signal`
DEĞİL). Tick beklemesi `_wait_for_tick:166` = `asyncio.wait_for(stop.wait(), timeout=...)`, bu
yüzden SIGTERM tick'in kalanını beklemez. `Event` import'ta yaratılmaz: ilk bekleyen loop'a
bağlanır ve sonra başkasını reddeder.

Tick aralığı **yapılandırılabilir**: `DEFAULT_TICK_SECONDS = 30.0` (`:43`), `SCHEDULER_TICK_SECONDS`
env değişkeniyle ezilir (pozitif olmayan değer varsayılana düşer, `:59`). Her tick'te
(`_maintenance_pass:97`):

| Adım | Fonksiyon | Ne yapar |
|---|---|---|
| 1 | `relay_unpublished` (`outbox_relay.py`) | Yayınlanmamış outbox satırlarını işaretler (batch: `settings.outbox_relay_batch_size`) |
| 2 | `recover_stale_jobs` (`maintenance.py`) | Worker çökmesiyle RUNNING'de kalmış job'ları geri alır (INF-09), audit'lenir |
| 3 | `redeliverable_queued_jobs` (`maintenance.py`) | Grace süresini aşmış QUEUED job'ları listeler (INF-03) |
| 4 | `ACTOR_BY_QUEUE.get(queue)` (`:135`) | Tek-aktörlü kuyruklar için yeniden dağıtır; `data` atlanır |

`ACTOR_BY_QUEUE` (`:70`): `backtest`, `agent`, `agent-high`, `agent-executor`, `maintenance`.

---

## Outbox → SSE fan-out

```
domain mutasyonu ─┬─> audit_events   (aynı transaction)
                  └─> outbox_events  (aynı transaction)   ← _audit_and_outbox deseni
                            │
        ┌───────────────────┴────────────────────┐
        │                                        │
  relay_unpublished                       run_outbox_poller
  (scheduler, kalıcı işaretleme)          (apps/api/sse.py:140, in-process tail)
                                                 │
                                          SseHub.publish (:125)
                                                 │
                                     GET /events  (sse.py:293, EventSourceResponse)
                                                 │
                                     frontend lib/sse.ts → queryClient.invalidateQueries
```

> **AUTH-11 (#349):** `GET /events` artık **authenticated** — `_authenticated_subscriber`
> (`sse.py:270` → `require_authenticated`) handshake'i doğrular; anonim SSE aboneliği
> kapalı, payload minimize edildi. Anonim çözümleme hiç sorgu açmadığı için kimliksiz handshake
> **DB'ye hiç dokunmadan** reddedilir. Event taksonomisi / `EVENT_QUERY_KEYS` değişmedi.

İki tüketici **tasarım gereği bağımsızdır**: scheduler'ın `relay_unpublished`'ı kalıcı durumu
ilerletir; SSE poller (`fetch_events_after`, `latest_event_id`) yalnız YENİ olayları kuyruktan
tarar — geçmiş bir sorgu meselesidir, stream'in değil.

### Kayıp toleransı + resume (INF-11 + O-21)

Kayıp hâlâ **tolere edilir**, ama artık **sessiz değildir** ve boşluk **replay** edilir.

| Mekanizma | Nerede | Davranış |
|---|---|---|
| `id:` alanı | `_sse_frame:170` | Her veri çerçevesi **outbox satır id'sini** taşır (AUTH-11 zarfına bilerek eklenen tek alan; domain nesnesi adreslemez). Kontrol çerçeveleri (`heartbeat`, `stream.resync`) **id taşımaz** — cursor'ı ilerletmezler. |
| `Last-Event-ID` | `requested_cursor` → `replay_after` | Reconnect'te header okunur; `shared/ids.py::looks_like_id(prefix="obx")` ile **tam biçim** doğrulanır (yabancı/bozuk değer → cursor yok = eski davranış), sonra `fetch_events_after` ile kaçırılan olaylar **kısa bir session'da** DB'den replay edilir. |
| Yarış kapatma | `_event_source:231` | Generator replay'den **ÖNCE** hub'a abone olur; replay sorgusu sırasında yayılan olay kuyruğa düşer ve canlı akışta `event_id <= replayed_through` ile **tekilleştirilir** (aynı olay iki kez gitmez). |
| `stream.resync` | `_control_frame(RESYNC_EVENT)` | Üç durumda üretilir: (1) abone buffer'ı taştı (`Subscriber.mark_overflowed` → `take_overflow`), (2) boşluk `REPLAY_LIMIT = 500`'den büyük, (3) replay okuması hata verdi. Anlamı: *"veremediğim olaylar var — her şeyi refetch et"*. |
| Tam refresh | frontend `lib/sse.ts` | **Fallback olarak korunur**: ilk bağlantı, resync ve replay penceresinin yetmediği boşluk için. |

- `SseHub` sabit boyutlu buffer (`_SUBSCRIBER_BUFFER = 256`, `sse.py:49`) kullanır; dolu buffer olayı
  **düşürür** (poller asla back-pressure yemez) ama düşüş o abonenin **overflow bayrağına** yazılır
  → `stream.resync` (`RESYNC_EVENT`, `:56`).
- Heartbeat: `HEARTBEAT_SECONDS = 15` (`:48`); veri yoksa `event: heartbeat` çerçevesi.
- Replay penceresi: `REPLAY_LIMIT = 500` (`:61`).
- Frontend `EventSource` **kullanmaz** (AUTH-11 header'lı kimlik → `fetch` stream). Bu yüzden tarayıcının
  otomatik `Last-Event-ID` davranışı yoktur: `lib/sse.ts` son gördüğü `id:`'yi kendi tutar ve her
  yeniden açılışta `Last-Event-ID` header'ı olarak gönderir. Boş `id:` cursor'ı **silmez** (spec'in
  aksine, bilerek: silmek bir sonraki replay'i kaybettirirdi).

> **Taksonomi değişmedi.** `stream.resync` ve `heartbeat` domain taksonomisinin **dışındadır**
> (`EVENT_QUERY_KEYS`'te yer almazlar); resync frontend'de tam refresh'e bağlanır.

### SSE taksonomisi (`sse_event_name` `sse.py:71-82`)

| Koşul (öncelik sırasıyla) | Yayılan event adı |
|---|---|
| `resource_type` `backtest` ile başlıyor | `backtest.run.updated` |
| `resource_type == "job"` | `job.updated` |
| `resource_type` `agent` ile başlıyor **veya** `== "hypothesis_artifact"` | `agent.task.updated` |
| `event_type` `audit.` ile başlıyor | `audit.event.created` |
| aksi hâlde | `resource.changed` (catch-all) |

Frontend karşılığı: `FRONTEND_MAP.md` → "SSE → react-query invalidation".

### İkinci, ayrı stream

`GET /agent-events/stream` (`routes/agent_lab.py:237`) **yalnız heartbeat** üretir
(`_event_stream:227`, `_SSE_HEARTBEAT_SECONDS`) ve `require_role(_LAB_ROLES)` ile kapıdadır.
Ana `/events` stream'inden bağımsızdır ve frontend'de ikinci bir `EventSource` olarak bağlanmamıştır.

> **Dürüst sınır (O-21):** bu ikincil stream olay taşımadığı için `id:`/replay **eklenmedi** —
> abone başına `agent_event` yoklaması, tek-process poller mimarisinin kaçındığı bağlantı yükünü
> geri getirirdi. Agent olayları frontend'e ana `/events` üzerinden `agent.task.updated` olarak
> ulaşır ve replay'i oradan alır. `repositories/agent_lab.py::events_after` / `latest_event_seq`
> hâlâ **çağrısızdır** (agent_event'in kendi replay primitifleri, bir tüketici bekliyor).

---

## Audit `event_kind` kataloğu (2026-07-29, ampirik)

`audit_events.event_kind` **126 ayrı literal** taşır. Yeniden üretmek (yalnız düz literaller;
`backtest_engine.py::_STAGE_AUDIT_KIND` ve `purge.py::_audit(kind=...)` gibi **dolaylı** yerler
bu grep'e düşmez — aşağıda ayrıca listelendi):

```
grep -rhoE 'event_kind\s*=\s*"[a-z0-9_.]+"' backend/src/entropia/application/ | sort -u | wc -l
```

Bu haritanın ilgilendiği üç grup:

### 1. Create-Package admission + worker düzlemi

| Nerede yazılır | `event_kind` |
|---|---|
| **Admission** (`commands/create_package.py`) | `package_request_created` · `precheck_started` · `precheck_stale` · `candidate_generation_started` · `validation_run_started` · `package_draft_created` · `baseline_uploaded` · `revision_requested` · `revision_published` · `approval_granted` |
| **Worker** (`jobs/create_package.py`) | `package_precheck_completed` · `candidate_generation_completed` · `candidate_generation_failed` · `validation_run_completed` · `baseline_validated` · `dependency_resolved` · `dependency_missing` |

> **Tuzak — CP kind'ları noktasız yazılır ve çoğu `system_other`'a düşer.**
> `domain/admin_panel/log_taxonomy.py::event_family` bir kind'ı **substring** eşleşmesiyle
> sınıflar ve **ilk eşleşen aile kazanır** (`_FAMILY_PREFIXES` bildirim sırası). `package`
> ailesinin tek token'ı `"package"` olduğu için `package_precheck_completed` /
> `package_draft_created` / `package_request_created` **`package`** ailesine düşer; ama
> `precheck_started`, `candidate_generation_completed`, `validation_run_started`,
> `baseline_uploaded`, `approval_granted`, `revision_published`, `dependency_missing` hiçbir
> token'la eşleşmez → **`system_other`**. Admin Logs'ta CP akışını "package" filtresiyle
> ararken bu satırlar görünmez. Kayıtlı gözlem — kod ile spec arasında bir çelişki DEĞİL,
> taksonominin bilinmesi gereken davranışı.

### 2. Backtest run stage'leri (O-05/O-06) — dolaylı yazım

`event_kind` bir sözlükten okunur, bu yüzden yukarıdaki grep'e düşmez:
`jobs/backtest_engine.py:124-125` `_STAGE_AUDIT_KIND` → `RUN_STARTED: "backtest.run_started"`,
`RUN_STAGE_CHANGED: "backtest.run_stage_changed"` (yazım yeri `:853`). Terminal kind'lar düz
literaldir: `backtest.run_succeeded:1027` · `backtest.result_materialized:1038` ·
`backtest.run_failed:1065` · `backtest.run_cancelled:956`. Result soft-delete komut tarafındadır
(`commands/backtest_run.py` → `backtest.result_soft_deleted`).

### 3. Trash / purge — komut + worker ayrımı

| Aşama | `event_kind` | Nerede |
|---|---|---|
| soft delete | `entity.soft_deleted` | `commands/deletion.py` |
| restore | `trash.restored` | `commands/deletion.py` |
| purge **isteği** (202) | `trash.purge_requested` | `commands/deletion.py` |
| purge **sonucu** | `trash.purge_completed` / `trash.purge_failed` | `jobs/purge.py:271` / `:260` (dolaylı: `_audit(kind=...)` `:213`) |

**Manual purge'ün ikinci, ayrı kaydı var.** `jobs/purge.py::_finalize_manual_purge:88` bir
`manual_document_purged` **publication event**'i yazar (`manual_publication_events` tablosu,
`:126-128`) — audit akışından bağımsız, dokümanın kendi yayın zaman çizelgesini kapatan kayıt.
Aynı finalize adımı search chunk'larını siler, revizyonları `removed` işaretler ve stream
sürümünü ilerletir. Built-in baseline manual **purge edilemez** (`PurgeNotEligibleError`, `:55`).

---

## Idempotency ve durability

- **At-least-once delivery guard = `application/jobs/delivery.py::claim_job_for_delivery` (ADIM 21).**
  Durable job satırını `FOR UPDATE` ile okur; `job.status in JOB_TERMINAL_STATES` ise gövde
  hiçbir şey yazmadan `job.result_ref`'i **verbatim** replay eder. Kilit iki soruyu birden
  yanıtlar: *"bu iş bitti mi?"* (terminal replay) ve *"şu anda başka bir teslimat koşuyor mu?"*
  (ikinci teslimat birincinin commit'ini bekler, sonra replay eder). Beş `data` aktörü bunu
  kullanır. **Kendi domain-satır kilidi olan gövdeler bunu ÇAĞIRMAZ** ve değişmedi:
  `backtest_engine` (run satırı), `agent_executor` (runtime + task), `create_package`
  (request root + `job.status`). Ayrıntı + kanıt: `docs/audit/worker_delivery_recovery_matrix.md`.
- **`run_idempotent` ile karıştırma:** o, HTTP `Idempotency-Key`'i **admission** transaction'ında
  tekilleştirir ve worker koştuğunda anahtar çoktan `202 queued` zarfıyla tamamlanmıştır —
  replay'i kabul zarfını döndürürdü, worker'ın sonucunu değil. İkisi bileşiktir: anahtar ikinci
  bir job açılmasını, claim tek bir job'un iki kez koşmasını engeller.
- `idempotency_keys` tablosu (`models/jobs.py:48`) `Idempotency-Key` header'ını `actor_principal_id`
  ile birlikte tekilleştirir → aynı anahtar aynı sonucu döner, ikinci bir job açılmaz.
- 202 dönen her endpoint (import'lar, analiz, backtest RUN/retry, purge, direktif) **kabul** eder;
  gerçek işi worker yapar. İstemci ilerlemeyi ilgili projeksiyon üzerinden okur.
- `purge.py` özellikle uygunluğu **worker'da yeniden kontrol eder** — 202 çoktan dönmüştür,
  isteği kabul eden bağlam artık güvenilir değildir.

---

## Doğrulanmamış noktalar (`?`)

- Broker konfigürasyonu (Redis/RabbitMQ, prefetch, dead-letter) `infrastructure/queues/` içinde;
  bu haritada **incelenmedi**.
- `relay_unpublished` ile SSE poller arasındaki cursor semantiği (`latest_event_id` başlangıcı)
  yalnız docstring'den okundu; at-least-once vs at-most-once garantisi kod okunarak doğrulanmalı.
- ~~`run_agent_tool` / `run_agent_tool_high` farkı~~ → **ADIM 21'de çözüldü:** ikisi de aynı
  `_run_agent_tool` gövdesini çağırır (`actors.py:186`), fark **yalnız kuyruktur**
  (`agent` vs `agent-high`); ikisi de tek durable aktör olduğu için ikisi de `ACTOR_BY_QUEUE`'da.
- ~~`maintenance` iki aktör paylaşıyor, `ACTOR_BY_QUEUE` tekini tanımlıyor~~ → **ADIM 21'de
  kanıtlandı:** `system_heartbeat` gövdesi `job_id` almaz, yani durable job satırı üretmez ve
  hiçbir sweep'in hedefi olamaz; `maintenance` fiilen tek durable aktörlüdür.
  `tests/unit/test_worker_queue_registry.py` bunu invariant olarak pinliyor (tek-aktörlü her
  kuyruk `ACTOR_BY_QUEUE`'da olmalı, çok-aktörlü hiçbiri olmamalı).
- `dispatch_tool_call`'ın AL-14 guard'ı `if idempotency_key is not None` koşulludur.
  Ağaçta gözlenen her durable tool job bir anahtar taşıyor, ama `idempotency_key=None` ile
  enqueue eden bir çağıran **korumasız** bir tool call alırdı — ADIM 21'de sınanmadı, açık soru.
