#!/usr/bin/env bash
# Validate ops/alerts + ops/prometheus with a real PromQL engine (ADIM 26).
#
# The alerting rules shipped in ADIM 25 with no PromQL validation whatsoever, and
# the cost was measured: two paging rules went out that could never fire. The
# Python contract test tokenizes expressions; it cannot tell a rule that MEANS
# something from one that merely parses. This script closes that gap in three
# passes:
#
#   check config  — the scrape config loads, and with it the rule file it names.
#                   This is what pins job="entropia-api" to a real scrape job.
#   check rules   — every expression is valid PromQL and every rule is well-formed.
#   test rules    — the rules are EVALUATED against synthetic series
#                   (ops/alerts/entropia.rules.test.yml). A dead rule fails here.
#
# SUPPLY CHAIN: promtool comes from the official Prometheus image pinned BY
# DIGEST, not by tag — same idiom as the gitleaks and trivy pins in
# .github/workflows/security.yml. A tag is mutable and this runs in a job that
# has already checked out the repository. The digest fixes the tool AND its own
# dependencies. Bump both constants together, deliberately.
#
# Usage: scripts/alert-rules-gate.sh      (needs docker; no other tooling)
set -euo pipefail

# Prometheus v3.5.0 — the current LTS line. An LTS pin keeps this gate from
# churning with every upstream minor.
PROMETHEUS_VERSION="v3.5.0"
PROMETHEUS_IMAGE="prom/prometheus@sha256:63805ebb8d2b3920190daf1cb14a60871b16fd38bed42b857a3182bc621f4996"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

workdir="$(mktemp -d)"
trap 'rm -rf "$workdir"' EXIT

cp -R "$REPO_ROOT/ops/." "$workdir/"

# `promtool check config` stats every credentials_file, so a config that
# authenticates cannot be validated without one on disk. The real token is a
# deployment secret (ENTROPIA_METRICS_TOKEN) and is gitignored; validating the
# config's SHAPE needs only a file to exist. This placeholder lives in a temp
# copy and never touches the working tree, so it cannot be committed by accident
# and cannot be mistaken for a credential in the repo.
printf 'placeholder-for-config-validation-only\n' > "$workdir/prometheus/metrics_token"

promtool() {
  docker run --rm --entrypoint promtool -v "$workdir:/ops:ro" "$PROMETHEUS_IMAGE" "$@"
}

echo "==> promtool ($PROMETHEUS_VERSION) check config"
promtool check config /ops/prometheus/prometheus.yml

echo "==> promtool check rules"
promtool check rules /ops/alerts/entropia.rules.yml

echo "==> promtool test rules"
promtool test rules /ops/alerts/entropia.rules.test.yml

echo "==> alert rules OK"
