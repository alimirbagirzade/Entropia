#!/bin/sh
# Entropia — fail-closed Prometheus launcher (ADIM 31).
#
# TWO JOBS, both of which exist because the alternative fails silently.
#
# 1. THE SCRAPE CREDENTIAL IS REQUIRED. ops/prometheus/prometheus.yml scrapes
#    GET /metrics with a Bearer token read from `credentials_file`. That endpoint
#    is fail-closed in production (finding O-22): an anonymous scraper gets 403,
#    the target reads as `up == 0`, and EntropiaApiDown pages forever against a
#    perfectly healthy product. A Prometheus that starts without
#    ENTROPIA_METRICS_TOKEN is therefore not "degraded" — it is a permanent false
#    page generator. So it does not start.
#
# 2. THE CONFIG IS COPIED, NOT EDITED. `credentials_file` is RELATIVE, which is
#    what lets the whole ops/ tree relocate as one unit (and what
#    scripts/alert-rules-gate.sh relies on). Relative means the token file must
#    sit next to prometheus.yml — inside a tree that is mounted READ-ONLY, in an
#    image that runs as `nobody`. So the tree is copied verbatim to a writable
#    path and the token is written into the copy. `cp -R` and nothing else: the
#    copy is byte-identical to the mounted repo file, which is exactly what makes
#    the provenance check meaningful — scripts/alert-notification-proof.sh reads
#    the config Prometheus actually loaded back out of
#    GET /api/v1/status/config and diffs it against ops/prometheus/prometheus.yml
#    in the working tree. Any templating here would break that diff, and with it
#    the only evidence that the deployed Prometheus is configured from this repo.
#    docs/releases/Entropia_V18_RC_Readiness_2026-08-07.md §6.3 named the absence
#    of that evidence as one of its two unverified points.
set -eu

SOURCE_TREE=/ops
RUNTIME_TREE=/tmp/ops
CONFIG_FILE="$RUNTIME_TREE/prometheus/prometheus.yml"

fail() {
  echo "prometheus-entrypoint: FATAL: $1" >&2
  echo "prometheus-entrypoint: refusing to start. An unauthenticated scraper reads a" >&2
  echo "prometheus-entrypoint: healthy API as up == 0 and pages continuously." >&2
  exit 78  # EX_CONFIG
}

METRICS_TOKEN="${ENTROPIA_METRICS_TOKEN:-}"
[ -n "$METRICS_TOKEN" ] || fail "ENTROPIA_METRICS_TOKEN is unset or empty."
[ -f "$SOURCE_TREE/prometheus/prometheus.yml" ] || fail "$SOURCE_TREE/prometheus/prometheus.yml is not mounted."
[ -f "$SOURCE_TREE/alerts/entropia.rules.yml" ] || fail "$SOURCE_TREE/alerts/entropia.rules.yml is not mounted (rule_files would resolve to nothing)."

mkdir -p "$RUNTIME_TREE"
cp -R "$SOURCE_TREE/." "$RUNTIME_TREE/"

umask 077
printf '%s' "$METRICS_TOKEN" > "$RUNTIME_TREE/prometheus/metrics_token"

echo "prometheus-entrypoint: config staged from $SOURCE_TREE (verbatim copy); scrape credential written."

exec /bin/prometheus \
  --config.file="$CONFIG_FILE" \
  --storage.tsdb.path=/prometheus \
  --web.listen-address=:9090 \
  "$@"
