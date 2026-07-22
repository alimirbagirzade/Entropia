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
| `system_heartbeat` | `maintenance` | `:28` | (scheduler tick ping'i) |
| `run_market_data_analysis` | `data` | `:34` | `market_data.py` |
| `run_research_data_analysis` | `data` | `:61` | `research_data.py` |
| `run_trading_signal_import` | `data` | `:88` | `trading_signal.py` |
| `run_trade_log_import` | `data` | `:115` | `trade_log.py` |
| `run_backtest_engine` | `backtest` | `:142` | `backtest_engine.py` |
| `run_agent_tool` | `agent` | `:170` | `agent_tools.py` |
| `run_agent_tool_high` | `agent-high` | `:182` | `agent_tools.py` |
| `run_agent_executor` | `agent-executor` | `:205` | `agent_executor.py` |
| `run_trash_purge` | `maintenance` | `:234` | `purge.py` |
| `run_package_import` | `data` | `:261` | `package_import.py` |

Tüm aktörler `max_retries=3`.

## Kuyruklar

| Kuyruk | Aktör sayısı | Otomatik redelivery? |
|---|---|---|
| `data` | **5** (çok-aktörlü) | ❌ **Hayır** — kasıtlı olarak `ACTOR_BY_QUEUE` dışında |
| `backtest` | 1 | ✔ |
| `agent` | 1 | ✔ |
| `agent-high` | 1 | ✔ |
| `agent-executor` | 1 | ✔ |
| `maintenance` | 2 (`system_heartbeat`, `run_trash_purge`) | ✔ (`run_trash_purge`) |

### Neden `data` özel

`data` kuyruğu dört+bir durable aktör tipini multiplex eder. Scheduler, durable satırdan hangi
aktöre gideceğini **çıkaramaz** → otomatik sweep bu kuyruğu asla yönlendirmez
(`apps/scheduler/__main__.py:36` yorumu: *"Queues with exactly ONE durable-job actor are safe to auto-redeliver"*).

Bunun yerine **operator eylemi** vardır: `POST /admin/data-queue/redeliver`
(`routes/admin_panel.py:177` → `commands/data_queue.py::redeliver_data_queue_jobs`), payload'daki
`job_kind` ayırıcısını `DATA_ACTOR_BY_KIND` (`actors.py:294`) ile eşleyerek yönlendirir.

**`job_kind` taksonomisi** (`application/jobs/data_queue.py:31-37`):
`market_data_analysis` · `research_data_analysis` · `trading_signal_import` · `trade_log_import` · `package_import`

Discriminator taşımayan eski satırlar → `skipped_unknown_kind` (asla tahmin edilmez).

## Scheduler (`apps/scheduler/__main__.py`)

`TICK_SECONDS = 30`. Her tick'te (`_maintenance_pass:53`):

| Adım | Fonksiyon | Ne yapar |
|---|---|---|
| 1 | `relay_unpublished` (`outbox_relay.py`) | Yayınlanmamış outbox satırlarını işaretler (batch: `settings.outbox_relay_batch_size`) |
| 2 | `recover_stale_jobs` (`maintenance.py`) | Worker çökmesiyle RUNNING'de kalmış job'ları geri alır (INF-09), audit'lenir |
| 3 | `redeliverable_queued_jobs` (`maintenance.py`) | Grace süresini aşmış QUEUED job'ları listeler (INF-03) |
| 4 | `ACTOR_BY_QUEUE.get(queue)` (`:74`) | Tek-aktörlü kuyruklar için yeniden dağıtır; `data` atlanır |

`ACTOR_BY_QUEUE` (`:37-43`): `backtest`, `agent`, `agent-high`, `agent-executor`, `maintenance`.

---

## Outbox → SSE fan-out

```
domain mutasyonu ─┬─> audit_events   (aynı transaction)
                  └─> outbox_events  (aynı transaction)   ← _audit_and_outbox deseni
                            │
        ┌───────────────────┴────────────────────┐
        │                                        │
  relay_unpublished                       run_outbox_poller
  (scheduler, kalıcı işaretleme)          (apps/api/sse.py:77, in-process tail)
                                                 │
                                          SseHub.publish (:62)
                                                 │
                                     GET /events  (sse.py:162, EventSourceResponse)
                                                 │
                                     frontend lib/sse.ts → queryClient.invalidateQueries
```

> **AUTH-11 (#349):** `GET /events` artık **authenticated** — `_authenticated_subscriber`
> (`sse.py:163` → `require_authenticated`, `:157`) handshake'i doğrular; anonim SSE aboneliği
> kapalı, payload minimize edildi. Event taksonomisi / `EVENT_QUERY_KEYS` değişmedi.

İki tüketici **tasarım gereği bağımsızdır**: scheduler'ın `relay_unpublished`'ı kalıcı durumu
ilerletir; SSE poller (`fetch_events_after`, `latest_event_id`) yalnız YENİ olayları kuyruktan
tarar — geçmiş bir sorgu meselesidir, stream'in değil.

### Kayıp toleransı (INF-11)

- `SseHub` (`sse.py:47`) sabit boyutlu buffer (`_SUBSCRIBER_BUFFER = 256`) kullanır.
  **Yavaş bir abonenin dolu buffer'ı olay DÜŞÜRÜR** — stream best-effort'tur, kayıt defteri değildir.
- Heartbeat: `HEARTBEAT_SECONDS = 15` (`sse.py:27`); veri yoksa `event: heartbeat` çerçevesi (`:125`).
- Frontend her yeniden bağlanışta **tam refresh** yapar → boşlukta kaçan olaylar telafi edilir.

### SSE taksonomisi (`sse_event_name` `sse.py:33-44`)

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

---

## Idempotency ve durability

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
- `run_agent_tool` (`agent`) ile `run_agent_tool_high` (`agent-high`) arasındaki fark yalnız kuyruk
  önceliği mi, yoksa farklı gövde mi — her ikisi de `agent_tools.py`'a işaret ediyor, ayrım doğrulanmadı.
- `system_heartbeat` ve `run_trash_purge` aynı `maintenance` kuyruğunu paylaşıyor; `ACTOR_BY_QUEUE`
  bu kuyruk için **tek** aktör (`run_trash_purge`) tanımlıyor — `system_heartbeat` durable job satırı
  üretmediği için bunun güvenli olduğu varsayılıyor, ancak kanıtlanmadı.
