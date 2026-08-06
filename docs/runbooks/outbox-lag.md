# Runbook — Outbox relay behind (SSE stale)

**Alerts:** `EntropiaOutboxLagGrowing` (ticket, >300s),
`EntropiaOutboxLagSevere` (page, >1800s).

Thresholds are 10 and 60 consecutive missed relay passes at the 30s default tick.

---

## What breaks for the user

The outbox relay publishes durable `resource.changed` events to SSE. When it
falls behind, **the product still works but the UI stops updating live** — a run
that finished minutes ago still shows as running until the user reloads. Nothing
is lost; it is late.

The relay runs inside the scheduler's maintenance pass, so this alert is very
often the same incident as [worker-down.md](worker-down.md).

---

## First 60 seconds

```bash
docker compose logs --tail=100 --no-color scheduler | grep maintenance
```

The `scheduler.maintenance` line carries `relayed` — the number of outbox rows
published in that pass.

| Observation | Meaning | Action |
|---|---|---|
| No `scheduler.maintenance` at all | Relay stopped | Restart `scheduler`; [worker-down.md](worker-down.md) |
| `scheduler.maintenance_failed` present | Relay failing; line carries `error` | Usually Postgres: [postgres.md](postgres.md) |
| `relayed` at ~200 every pass, lag high | **Saturated, not stopped** | See below |
| `relayed` small, lag high | Rows are not being picked up | Check the outbox table |

### Saturated vs stopped

`OUTBOX_RELAY_BATCH_SIZE` defaults to **200 rows per pass**. A `relayed` value
pinned at that ceiling while lag stays high means the producer is outrunning the
relay — a large import or a wide backtest can do this legitimately.

Confirm by trend, not by instantaneous value: **falling lag is draining, not
stuck.** Only act if it is flat or rising over several passes.

Remedies, in order of preference:
1. Wait — a burst drains on its own.
2. Raise `OUTBOX_RELAY_BATCH_SIZE`.
3. Shorten `SCHEDULER_TICK_SECONDS`. Note this also speeds the reclaim sweep, and
   `EntropiaWorkerHeartbeatStale` / the outbox thresholds are **multiples of this
   value** — `test_alert_rules_contract.py` will fail until the rules are
   revisited. That failure is the intended prompt, not an obstacle.

---

## Confirm the user-visible symptom

```bash
curl -N -H "Authorization: Bearer <token>" http://<host>:8000/api/v1/events
```

A `heartbeat` control frame every ~15s with no `resource.changed` while jobs are
completing confirms the relay, not the SSE transport, is at fault.

---

## Recovery

* `EntropiaOutboxLagGrowing`: lag back under 60s.
* `EntropiaOutboxLagSevere`: lag under 300s and the growing alert clears.

---

## Known false positives

* A large import or wide backtest produces a burst the relay drains over several
  passes.
* A stack deliberately left running with the scheduler stopped reproduces this
  exactly. Silence before doing that.

---

## What this cannot tell you

* **How many events were dropped to a slow SSE client.** Subscriber overflow is a
  **boolean flag**, not a count — each burst yields one `stream.resync` frame and
  the number of dropped events is never recorded.
* **How many SSE clients are connected.** `SseHub.subscriber_count` exists but is
  read only by tests; it is not exposed.
* **Replay lag per subscriber.** Not measured.
