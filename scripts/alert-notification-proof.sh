#!/usr/bin/env bash
# Prove a fired alert reaches the END of the notification path (ADIM 31).
#
# WHY A SEPARATE SCRIPT FROM THE TWO GATES. `scripts/alert-rules-gate.sh` says
# the rules are correct. `scripts/alert-notification-gate.sh` says the routing
# config loads and resolves. NEITHER ASKS WHO RECEIVES ANYTHING, and reading a
# green `Alert rules — promtool` badge as "alerting works" is precisely the
# mistake docs/releases/Entropia_V18_RC_Readiness_2026-08-07.md §6.3 records:
# eleven validated rules, seven of them paging, reaching nobody. This script is
# the observation the badges cannot make.
#
# IT IS NOT A CI GATE, deliberately and honestly. It stands up three containers
# and waits out a rule's real `for: 2m`, so it costs minutes of wall clock and a
# Docker network. Wiring it into every PR would be a cost decision this slice
# does not make on anyone's behalf. Run it when the notification path changes,
# and record the output as release evidence.
#
# WHAT IT PROVES, in four phases:
#
#   1. FAIL-CLOSED   — Alertmanager REFUSES to start with no destination, and
#                      refuses again when the destination is not a URL.
#   2. UP            — the shipped pair comes up on the shipped configs.
#   3. PROVENANCE    — the config in effect IS ops/prometheus/prometheus.yml from
#                      this working tree, proven by hash and by the process's own
#                      --config.file flag. (§6.3's second unverified point: "no
#                      gate proves the deployed Prometheus is actually configured
#                      from this file".)
#   4. DELIVERY      — a REAL alert (EntropiaApiDown, from the SHIPPED rules file,
#                      evaluated against the SHIPPED scrape config) fires, is
#                      routed to `entropia-page`, and is POSTed to a receiver
#                      that logs it.
#
# NO SYNTHETIC FIXTURE ANYWHERE. The alert fires because the `api` service is not
# running, so `up{job="entropia-api"} == 0` is simply true. Nothing here injects
# a series, relaxes a threshold, or edits a shipped file.
#
# DEPENDENCIES: docker and a POSIX shell. Nothing else — no Python packages, no
# jq. An operator reproducing release evidence should not have to build an
# environment first, and the same constraint is why scripts/alert-rules-gate.sh
# is pure bash too.
#
# Usage: scripts/alert-notification-proof.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# Its own compose project so it cannot collide with, or tear down, the operator's
# running stack.
PROJECT="entropia-alert-proof"
COMPOSE_FILES=(-f docker-compose.yml -f ops/alertmanager/docker-compose.proof.yml)

# The catcher is reachable only inside the compose network; the proof reads its
# stdout via `docker compose logs`, never over the host.
CATCHER_URL="http://alert-catcher:9099/notify"

# EntropiaApiDown is `for: 2m`, the root route's group_wait is 30s, and the
# scrape interval is 30s. 8 minutes of headroom over a ~3 minute expectation:
# generous, because a flaky timeout here would read as "the path is broken".
DELIVERY_TIMEOUT_SECONDS=480

WORK="$(mktemp -d)"
dc() { docker compose -p "$PROJECT" "${COMPOSE_FILES[@]}" --profile observability "$@"; }

cleanup() {
  echo
  echo "==> tearing down $PROJECT"
  # -v: the alertmanager volume holds the notification log, and a retained one
  # would let a SECOND run pass on the FIRST run's delivery.
  dc down -v --remove-orphans >/dev/null 2>&1 || true
  rm -rf "$WORK"
}
trap cleanup EXIT

fail() { echo; echo "PROOF FAILED: $*" >&2; exit 1; }

# macOS ships `shasum`, Linux ships `sha256sum`. Pick whichever exists rather
# than assuming the host is the CI runner.
host_sha256() {
  if command -v sha256sum >/dev/null 2>&1; then sha256sum "$1" | awk '{print $1}'
  else shasum -a 256 "$1" | awk '{print $1}'; fi
}

# Ports are unset for this run: docker-compose.yml publishes prometheus and
# alertmanager on the host, and a proof that fights the operator's own stack for
# :9090 is a proof that cannot be run twice.
export PROMETHEUS_HOST_PORT="" ALERTMANAGER_HOST_PORT=""
# Any non-empty value satisfies the Prometheus entrypoint's fail-closed check.
# It is deliberately WRONG for the (absent) API: the proof wants `up == 0`.
export ENTROPIA_METRICS_TOKEN="alert-proof-throwaway-token"

echo "================================================================"
echo "PHASE 1 — FAIL-CLOSED: Alertmanager must refuse an empty destination"
echo "================================================================"
# `run --rm --no-deps` bypasses the restart policy, so the refusal is observed as
# an exit code rather than as a crash loop.
set +e
ALERTMANAGER_NOTIFY_URL="" dc run --rm --no-deps alertmanager > "$WORK/failclosed.txt" 2>&1
unset_exit=$?
set -e
cat "$WORK/failclosed.txt"
echo "    exit code with ALERTMANAGER_NOTIFY_URL unset: $unset_exit"
[ "$unset_exit" -ne 0 ] || fail "Alertmanager STARTED with no destination. The path is not fail-closed."
grep -q "ALERTMANAGER_NOTIFY_URL is unset or empty" "$WORK/failclosed.txt" \
  || fail "Alertmanager exited non-zero but did not name the missing variable."

set +e
ALERTMANAGER_NOTIFY_URL="not-a-url" dc run --rm --no-deps alertmanager > "$WORK/badurl.txt" 2>&1
badurl_exit=$?
set -e
echo "    exit code with a non-URL destination: $badurl_exit"
[ "$badurl_exit" -ne 0 ] || fail "Alertmanager STARTED with a non-URL destination."
grep -q "not an http:// or https:// URL" "$WORK/badurl.txt" \
  || fail "the non-URL refusal did not explain itself."
echo "PHASE 1 OK — no destination, no process."

echo
echo "================================================================"
echo "PHASE 2 — bring the path up with a real (test) destination"
echo "================================================================"
export ALERTMANAGER_NOTIFY_URL="$CATCHER_URL"
dc up -d prometheus alertmanager alert-catcher

wait_ready() {
  # $1 = service, $2 = readiness path
  local i
  for i in $(seq 1 60); do
    if dc exec -T "$1" wget -q -O - "http://localhost:$3$2" >/dev/null 2>&1; then return 0; fi
    sleep 2
  done
  return 1
}
wait_ready prometheus /-/ready 9090   || fail "Prometheus never became ready. $(dc logs --tail=40 prometheus)"
wait_ready alertmanager /-/ready 9093 || fail "Alertmanager never became ready. $(dc logs --tail=40 alertmanager)"
echo "PHASE 2 OK — both services up on the shipped configs."

echo
echo "================================================================"
echo "PHASE 3 — PROVENANCE: the config in effect IS this working tree's"
echo "================================================================"
# WHAT DOES NOT WORK, and why it is written down rather than quietly dropped.
# The obvious check — GET /api/v1/status/config, diff against the working-tree
# file — CANNOT pass: Prometheus returns the config MARSHALLED (defaults such as
# `scrape_protocols` and `runtime.gogc` injected, every comment stripped), not
# the bytes it read. Measured on v3.5.0 in this slice, not assumed. So provenance
# is a chain of three links instead, and each is checked:
#
#   (a) the file staged inside the container hashes identically to
#       ops/prometheus/prometheus.yml in this working tree;
#   (b) the process's own --config.file flag names exactly that staged file;
#   (c) the config Prometheus actually PARSED still carries this tree's
#       distinguishing values — the scrape job, the scrape target, the external
#       label, the rule file and the Alertmanager target. A config that hashed
#       right but was not in effect would fail here.

tracked_sha="$(host_sha256 ops/prometheus/prometheus.yml)"
mounted_sha="$(dc exec -T prometheus sha256sum /ops/prometheus/prometheus.yml | awk '{print $1}')"
staged_sha="$(dc exec -T prometheus sha256sum /tmp/ops/prometheus/prometheus.yml | awk '{print $1}')"
echo "    working tree          : $tracked_sha"
echo "    mounted in container  : $mounted_sha"
echo "    staged (config.file)  : $staged_sha"
[ "$mounted_sha" = "$tracked_sha" ] || fail "the mounted ops/ tree is not this working tree"
[ "$staged_sha" = "$tracked_sha" ] || fail "the staged config differs from the mounted one — the entrypoint is not copying verbatim"

dc exec -T prometheus wget -q -O - http://localhost:9090/api/v1/status/flags > "$WORK/flags.json" \
  || fail "could not read Prometheus's runtime flags"
config_flag="$(tr ',' '\n' < "$WORK/flags.json" | grep '"config.file"' | sed 's/.*"config.file":"\([^"]*\)".*/\1/')"
echo "    --config.file         : $config_flag"
[ "$config_flag" = "/tmp/ops/prometheus/prometheus.yml" ] \
  || fail "the process is running a config at '$config_flag', which is not the staged copy"

dc exec -T prometheus wget -q -O - http://localhost:9090/api/v1/status/config > "$WORK/config.json" \
  || fail "could not read Prometheus's loaded config"

# Each needle is read OUT OF the tracked file, so the assertion stays tied to the
# tree rather than to a literal copied into this script.
job_name="$(grep -o 'job_name: .*' ops/prometheus/prometheus.yml | head -1 | awk '{print $2}')"
scrape_target="$(grep -o 'targets: \["[^"]*"\]' ops/prometheus/prometheus.yml | head -1 | sed 's/.*"\(.*\)".*/\1/')"
am_target="$(grep -o 'targets: \["[^"]*"\]' ops/prometheus/prometheus.yml | tail -1 | sed 's/.*"\(.*\)".*/\1/')"
rules_basename="$(basename "$(grep -o '\.\./alerts/.*' ops/prometheus/prometheus.yml | head -1)")"
external_label="$(grep -A1 'external_labels:' ops/prometheus/prometheus.yml | tail -1 | sed 's/^ *//')"

for needle in "$job_name" "$scrape_target" "$am_target" "$rules_basename" "$external_label"; do
  [ -n "$needle" ] || fail "could not extract an expected value from ops/prometheus/prometheus.yml — the provenance check would be vacuous"
  if grep -q -- "$needle" "$WORK/config.json"; then
    echo "    parsed config carries  : $needle"
  else
    fail "the parsed config does NOT carry '$needle' declared by ops/prometheus/prometheus.yml"
  fi
done
[ "$scrape_target" != "$am_target" ] || fail "the scrape target and the Alertmanager target extracted identically — the check is not discriminating"

# Provenance of the RULES, one level down: a config can name a rule file that is
# not the one in this tree. Prometheus reports the rule groups it loaded.
dc exec -T prometheus wget -q -O - http://localhost:9090/api/v1/rules > "$WORK/rules.json" \
  || fail "could not read the loaded rules"
grep -o '"name":"Entropia[A-Za-z]*"' "$WORK/rules.json" | sed 's/.*:"\(.*\)"/\1/' | sort -u > "$WORK/loaded_rules.txt"
grep -o '^ *- alert: .*' ops/alerts/entropia.rules.yml | awk '{print $3}' | sort -u > "$WORK/tracked_rules.txt"
echo "    tracked alert rules   : $(wc -l < "$WORK/tracked_rules.txt" | tr -d ' ')"
echo "    loaded  alert rules   : $(wc -l < "$WORK/loaded_rules.txt" | tr -d ' ')"
diff "$WORK/tracked_rules.txt" "$WORK/loaded_rules.txt" \
  || fail "the running Prometheus did not load exactly the shipped rule set"
echo "PHASE 3 OK — provenance established for the scrape config, the alerting block and the rules."

echo
echo "================================================================"
echo "PHASE 4 — DELIVERY: a real alert must reach the receiver"
echo "================================================================"
echo "    no 'api' service is running, so up{job=\"entropia-api\"} == 0 is simply true."
echo "    EntropiaApiDown is for: 2m; root group_wait is 30s. Waiting up to ${DELIVERY_TIMEOUT_SECONDS}s."

# The catcher's log is CAPTURED TO A FILE and then grepped, never piped straight
# into grep. `docker compose logs | grep -q` looks obvious and is a trap under
# `set -o pipefail`: grep exits on its first match, docker takes SIGPIPE, the
# pipeline reports failure, and a delivery that DID happen reads as one that did
# not. Measured in this slice — the first version of this script exited 255 on a
# run whose notification had already arrived.
deadline=$(( SECONDS + DELIVERY_TIMEOUT_SECONDS ))
delivered=""
while [ "$SECONDS" -lt "$deadline" ]; do
  dc logs alert-catcher > "$WORK/catcher.log" 2>/dev/null || true
  if grep -q "NOTIFICATION_RECEIVED" "$WORK/catcher.log"; then
    delivered="yes"
    break
  fi
  sleep 5
done

echo
echo "---- alertmanager's own view of the alert ----"
dc exec -T alertmanager wget -q -O - http://localhost:9093/api/v2/alerts 2>/dev/null || true
echo
echo "---- what the receiver actually got ----"
grep "NOTIFICATION_RECEIVED" "$WORK/catcher.log" || true
echo

[ -n "$delivered" ] || fail "nothing arrived at the receiver within ${DELIVERY_TIMEOUT_SECONDS}s. Alertmanager log: $(dc logs --tail=40 alertmanager 2>&1)"

# The catcher emits `json.dumps(..., sort_keys=True)`, so these three literals
# appear verbatim or not at all. Asserting on all three separates "a
# notification arrived" from "THE notification arrived, at the right severity,
# through the right receiver" — the distinction this whole slice is about.
grep -m1 "NOTIFICATION_RECEIVED" "$WORK/catcher.log" > "$WORK/payload.txt"
for literal in '"receiver": "entropia-page"' '"alertname": "EntropiaApiDown"' '"severity": "page"'; do
  grep -qF -- "$literal" "$WORK/payload.txt" \
    || fail "the delivered payload does not contain $literal"
  echo "    payload carries: $literal"
done

echo
echo "================================================================"
echo "PROOF PASSED — a fired alert reached the end of the notification path."
echo "================================================================"
echo "Read this narrowly. It proves FAIL-CLOSED, PROVENANCE and DELIVERY for this"
echo "stack, on this run, against a test receiver. It does NOT prove that the"
echo "rules behave well against real PRODUCTION series — that residue stays open"
echo "and is recorded in docs/runbooks/alert-notification.md §5."
