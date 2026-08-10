<!-- doc-status: current -->

# Alert notification path (ADIM 31)

**What this document covers:** how a fired alert gets from Prometheus to a human,
how to stop it temporarily, how to prove the path works, and — §5 — exactly what
it still does not cover.

Related: [METRIC_ALERT_MATRIX.md](METRIC_ALERT_MATRIX.md) (what is and is not
observable), and the per-alert runbooks each rule's `runbook` annotation points
at ([api](api.md) · [postgres](postgres.md) · [worker-down](worker-down.md) ·
[stale-jobs](stale-jobs.md) · [outbox-lag](outbox-lag.md)).

---

## 1. The path, and what each link is guarded by

```
metric      scrape        rule                                 notification     human
exposition  config        evaluation         firing            delivery
    │           │             │                 │                   │             │
    ▼           ▼             ▼                 ▼                   ▼             ▼
 7 families  entropia-api  11 rules        alertstate=       alertmanager     receiver
                          (7 page)          "firing"         routing tree     endpoint
```

| Link | Shipped as | Guarded by |
|---|---|---|
| Exposition | `infrastructure/observability/metrics.py`, `apps/api/routes/metrics.py` | `test_alert_rules_contract.py` derives the allowed metric set from the exposition code itself |
| Scrape | `ops/prometheus/prometheus.yml` | `promtool check config` (`scripts/alert-rules-gate.sh`) + `test_every_job_matcher_names_a_declared_scrape_job` |
| Rules | `ops/alerts/entropia.rules.yml` | `promtool check rules` + `promtool test rules` over `entropia.rules.test.yml` — every rule has an EVALUATED firing case |
| **Alerting block** | `ops/prometheus/prometheus.yml` → `alerting:` | `test_prometheus_sends_its_alerts_to_the_shipped_alertmanager` |
| **Routing** | `ops/alertmanager/alertmanager.yml` | `amtool check-config` + `amtool config routes test` (`scripts/alert-notification-gate.sh`) + `test_alert_notification_contract.py` |
| **Delivery** | `ALERTMANAGER_NOTIFY_URL` → your receiver | `scripts/alert-notification-proof.sh` (**not a CI gate** — see §3) |

**Everything in bold arrived in ADIM 31.** Before it, the first three links were
gated and the last three did not exist:
`docs/releases/Entropia_V18_RC_Readiness_2026-08-07.md` §6.3 recorded eleven
validated rules, seven of them paging, reaching nobody.

---

## 2. Running it

```bash
docker compose --profile observability up -d prometheus alertmanager
```

Both services sit behind the `observability` compose profile, so a plain
`docker compose up` — which every acceptance script runs — brings up exactly the
stack it brought up before, unchanged.

### Required configuration

| Variable | Required | What it is |
|---|---|---|
| `ALERTMANAGER_NOTIFY_URL` | **yes** | The endpoint that receives `severity: page`. Unset, empty, or not an `http(s)` URL → **Alertmanager exits 78 and does not start.** |
| `ALERTMANAGER_NOTIFY_URL_TICKET` | no | Where `severity: ticket` goes. Unset → the ticket lane is pointed at the page destination and the launcher says so on stdout. |
| `ENTROPIA_METRICS_TOKEN` | **yes** | The Bearer credential for `GET /metrics`. Unset → **Prometheus exits 78 and does not start** (an anonymous scrape is 403, which reads as `up == 0` and pages forever against a healthy product). |

**Why it fails closed rather than starting degraded.** An Alertmanager with no
reachable destination is strictly worse than none: the stack looks monitored,
`/-/ready` is green, alerts arrive and are grouped and "notified", and nobody is
told. That is the failure mode this whole path was built to remove, so it is not
one the path is allowed to reproduce.

### Routing

| Severity | Receiver | `group_wait` | `group_interval` | `repeat_interval` | Rules |
|---|---|---|---|---|---|
| `page` | `entropia-page` | 30s | 5m | 1h | 7 |
| `ticket` | `entropia-ticket` | 5m | 30m | 12h | 4 |
| *(no severity)* | `entropia-page` (root) | 30s | 5m | 1h | — |

The root receiver is a real one on purpose: an alert matching no branch **pages**
rather than vanishing. Alertmanager's usual `receiver: null` catch-all would
rebuild the exact blind spot this slice closed.

### Inhibitions (config-level noise suppression)

| Source (delivered) | Suppresses | Why |
|---|---|---|
| `EntropiaApiDown` | `EntropiaApiServerErrors`, `EntropiaApiRequestsExceedLargestBucket` | An API that answers no scrapes is describing one outage; its 5xx rate and latency histogram are the same event from the inside |
| `EntropiaWorkerHeartbeatNeverRecorded` | `EntropiaWorkerHeartbeatStale` | "never ran" strictly contains "has not run recently" |
| `EntropiaOutboxLagSevere` | `EntropiaOutboxLagGrowing` | The growing rule's own `escalation` annotation names the severe one as its escalation |

In all three the **source** alert is itself delivered, so the incident always
reaches someone. `test_no_ticket_severity_alert_can_suppress_a_page` enforces
that inhibition only ever runs downward.

---

## 3. Proving it works

```bash
scripts/alert-notification-proof.sh
```

Four phases, ~4 minutes, three containers, no synthetic fixture:

1. **Fail-closed** — Alertmanager is started with an empty destination and with a
   non-URL destination; both must exit non-zero.
2. **Up** — the shipped pair comes up on the shipped configs.
3. **Provenance** — the config in effect is hashed against
   `ops/prometheus/prometheus.yml` in the working tree, the process's own
   `--config.file` flag is read back, the parsed config is checked for this
   tree's distinguishing values, and the loaded rule set is diffed against the
   rules file.
4. **Delivery** — with no `api` service running, `up{job="entropia-api"} == 0` is
   simply true, `EntropiaApiDown` fires for real, and the proof asserts it
   arrives at a test receiver carrying `receiver: entropia-page` and
   `severity: page`.

**It is not a CI gate, and that is a deliberate, honest limit.** It costs minutes
of wall clock and a Docker network per run. Wiring it into every PR is a cost
decision for a human to make, not one this repository makes on anyone's behalf.
What runs on every PR is the *configuration* half:
`scripts/alert-notification-gate.sh` and
`backend/tests/contract/test_alert_notification_contract.py`.

> **Do not read a green `Alert rules and notification path` job as "alerting
> works".** It means the rules are correct and the routing config loads. It never
> asks who receives anything. The CI job was renamed in ADIM 31 precisely because
> its old name (`Alert rules — promtool`) was being read as the stronger claim.

### A note on `GET /api/v1/status/config`

The obvious provenance check — fetch the loaded config and diff it against the
file — **cannot pass**. Prometheus returns the config *marshalled*: defaults such
as `scrape_protocols` and `runtime.gogc` are injected and every comment is
stripped. Measured on v3.5.0 while building this path. Hence the hash + flag +
parsed-values chain in phase 3.

---

## 4. Silencing

Several rules' `false_positives` annotations explicitly ask for a silence — a
planned redeploy fires `EntropiaApiDown`; a deliberately stopped scheduler fires
`EntropiaOutboxLagSevere`. Silences are runtime state, not configuration, so they
live in Alertmanager rather than in this repository.

```bash
# Web UI (the port docker-compose.yml publishes)
open http://localhost:9093/#/silences

# Or from the CLI, inside the container
docker compose --profile observability exec alertmanager \
  amtool --alertmanager.url=http://localhost:9093 \
  silence add alertname=EntropiaApiDown --duration=30m \
  --comment="planned redeploy, <your name>"

docker compose --profile observability exec alertmanager \
  amtool --alertmanager.url=http://localhost:9093 silence query
```

**Always set a duration.** An open-ended silence is how a real outage gets
missed, and Alertmanager will not remind you it exists.

The silence store lives in the `alertmanagerdata` volume, so silences (and the
notification log that prevents a restart from re-paging everything) survive a
restart. `scripts/alert-notification-proof.sh` tears its volume down with `-v`
for exactly the mirror reason: a retained notification log would let a second
proof run pass on the first run's delivery.

---

## 5. What this path still does NOT cover — read before trusting it

**These are open residues, not solved problems.** Each is written here rather
than left implicit, because the failure this path exists to fix was a gap nobody
had written down as a gap.

| # | Not covered | Consequence | Closes when |
|---|---|---|---|
| **1** | **The rules have never been evaluated against real production series.** `promtool test rules` runs them over synthetic series; `scripts/alert-notification-proof.sh` fires one structural rule (`up == 0`). A threshold that is wrong for real traffic still looks correct. | A rule can be too sensitive (noise) or too slack (silence) and nothing here would say so. | Only as real traffic accumulates. Cannot be closed by any gate in this repository — this is the FIRST of the two unverified points §6.3 named, and ADIM 31 closed the second, not this one. |
| **2** | **Nothing monitors the monitor.** If Alertmanager is unreachable, Prometheus retries and increments `prometheus_notifications_errors_total` — on its *own* `/metrics`, which nothing here scrapes. | A notification path that has silently stopped delivering looks identical to a quiet system. | Scraping Prometheus's own exposition and alerting on it — which needs a second Prometheus to be non-circular. Not attempted. |
| **3** | **The delivery proof is not a CI gate.** | A regression in the notification path can land without any job objecting. The *config* half is gated; the *delivery* half is not. | A human accepting the wall-clock cost of running the proof in CI. |
| **4** | **No on-call rotation, escalation policy or acknowledgement.** Alertmanager has no acknowledgement concept; `repeat_interval` is the whole mechanism. Who is woken, and what happens if they do not answer, lives in whatever receives `ALERTMANAGER_NOTIFY_URL`. | An alert can be delivered to a destination nobody is watching at 3am. | An organisational decision, outside this repository. |
| **5** | **Per-queue worker liveness is still unobservable** (`METRIC_ALERT_MATRIX.md` §4). A dead `worker-backtest` leaves the heartbeat fresh. | The notification path faithfully delivers alerts that do not exist for this failure. | A new metric, not a new receiver. |

Residue **1** is the one to keep in mind when reading the release record: ADIM 31
closed §6.3's *delivery* blocker and its *provenance* point. It did not, and
could not, close the "never evaluated against production series" point.

---

## 6. Maintenance

| File | What it is |
|---|---|
| `ops/alertmanager/alertmanager.yml` | Routing tree, receivers, inhibitions |
| `ops/alertmanager/entrypoint.sh` | The fail-closed launcher — the refusal lives here, not in compose |
| `ops/prometheus/prometheus.yml` | Scrape config **and** the `alerting:` block |
| `ops/prometheus/entrypoint.sh` | Stages the config verbatim; requires the scrape credential |
| `ops/alertmanager/notification_catcher.py` | Test receiver — proof harness only, never deployed |
| `ops/alertmanager/docker-compose.proof.yml` | Proof overlay; adds the catcher and overrides nothing else |
| `scripts/alert-notification-gate.sh` | CI: `amtool check-config` + routing resolution |
| `scripts/alert-notification-proof.sh` | End-to-end proof (not CI) |
| `backend/tests/contract/test_alert_notification_contract.py` | CI: structure — no black-hole receiver, no inlined endpoint, no page/ticket collapse, no default destination |

**Adding a receiver:** it must carry at least one notifier config with a real
endpoint, and that endpoint must come from a `url_file` the launcher writes.
`amtool check-config` returns SUCCESS on a receiver with *no* notifier configs at
all — measured, not assumed — which is why the contract test exists.

**Bumping the images:** both are pinned BY DIGEST, in `docker-compose.yml` and in
the gate scripts. Bump the version constant and the digest together, deliberately.
