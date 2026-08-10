#!/usr/bin/env bash
# Validate the notification path's CONFIGURATION with a real Alertmanager (ADIM 31).
#
# THE COMPANION GATE, AND ITS HONEST LIMIT. scripts/alert-rules-gate.sh proves
# the RULES are right. This proves the ROUTING loads. Neither proves anything
# reaches a human — that is scripts/alert-notification-proof.sh, which stands up
# the stack and fires a real alert into a real receiver, and which is not a CI
# gate because it costs minutes of wall clock and needs the Docker network.
# Keeping the three separate is deliberate: this slice exists because a green
# `Alert rules — promtool` badge was being read as "alerting works".
#
# WHAT amtool WILL NOT CATCH — measured, not assumed. `amtool check-config`
# returns SUCCESS on a receiver declared with NO notifier configs at all, i.e.
# the exact black-hole shape ops/alertmanager/alertmanager.yml bans in prose.
# It also cannot see that a `url_file` points at a file only the entrypoint
# creates. So the structural half lives in
# backend/tests/contract/test_alert_notification_contract.py and runs in the
# backend job; this script is the "does a real Alertmanager accept it" half.
#
# SUPPLY CHAIN: pinned BY DIGEST, matching the promtool pin in
# scripts/alert-rules-gate.sh and the gitleaks/trivy pins in
# .github/workflows/security.yml. Bump the version constant and the digest
# together, deliberately.
#
# Usage: scripts/alert-notification-gate.sh      (needs docker; no other tooling)
set -euo pipefail

ALERTMANAGER_VERSION="v0.28.1"
ALERTMANAGER_IMAGE="prom/alertmanager@sha256:27c475db5fb156cab31d5c18a4251ac7ed567746a2483ff264516437a39b15ba"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

workdir="$(mktemp -d)"
trap 'rm -rf "$workdir"' EXIT

cp -R "$REPO_ROOT/ops/." "$workdir/"

# `amtool check-config` stats every `url_file`, so a config whose destinations
# come from files cannot be validated without them on disk. In a real container
# ops/alertmanager/entrypoint.sh writes those two files from
# ALERTMANAGER_NOTIFY_URL; here they are throwaway placeholders in a temp copy,
# so validating the config's SHAPE needs no real destination and no real
# destination can be committed by accident. The URLs below are deliberately
# unreachable — nothing in this script sends anything.
mkdir -p "$workdir/alertmanager/runtime"
printf 'http://config-validation-only.invalid/page\n' > "$workdir/alertmanager/runtime/notify_url"
printf 'http://config-validation-only.invalid/ticket\n' > "$workdir/alertmanager/runtime/notify_url_ticket"

# The shipped config reads /tmp/alertmanager/*, which is where the entrypoint
# writes at runtime. amtool in this gate reads the same file NAMES from the temp
# copy, so the paths are rewritten for the validation run only — the tracked file
# is never edited. Kept as a sed over a copy rather than a second config file:
# two configs drift, and the one that drifts is always the one nobody runs.
sed 's#/tmp/alertmanager/#/ops/alertmanager/runtime/#g' \
  "$REPO_ROOT/ops/alertmanager/alertmanager.yml" > "$workdir/alertmanager/alertmanager.yml"

# Same ownership problem the promtool gate documents: the official image runs as
# `nobody` (uid 65534) and `mktemp -d` creates a 0700 directory, so the container
# cannot traverse into it. Do NOT delete this as redundant after testing on
# macOS — Docker Desktop maps ownership through its VM and hides the failure.
chmod -R a+rX "$workdir"

amtool() {
  docker run --rm --entrypoint amtool -v "$workdir:/ops:ro" "$ALERTMANAGER_IMAGE" "$@"
}

echo "==> amtool ($ALERTMANAGER_VERSION) check-config"
amtool check-config /ops/alertmanager/alertmanager.yml

# Routing is where a config is most often "valid and wrong": a matcher typo sends
# every page down the ticket branch and amtool has no opinion about it. Resolving
# concrete label sets through the tree turns the intent into an assertion.
echo "==> amtool config routes test — severity=page must reach entropia-page"
page_receiver="$(amtool config routes test \
  --config.file=/ops/alertmanager/alertmanager.yml \
  severity=page alertname=EntropiaApiDown component=api)"
echo "    -> $page_receiver"
[ "$page_receiver" = "entropia-page" ] || {
  echo "FAIL: severity=page routed to '$page_receiver', not entropia-page" >&2
  exit 1
}

echo "==> amtool config routes test — severity=ticket must reach entropia-ticket"
ticket_receiver="$(amtool config routes test \
  --config.file=/ops/alertmanager/alertmanager.yml \
  severity=ticket alertname=EntropiaQueueNeverDrains component=jobs)"
echo "    -> $ticket_receiver"
[ "$ticket_receiver" = "entropia-ticket" ] || {
  echo "FAIL: severity=ticket routed to '$ticket_receiver', not entropia-ticket" >&2
  exit 1
}

# The root receiver is a REAL one on purpose: an alert that matches no child
# route must page, not vanish. This pins that decision so a future edit cannot
# quietly turn the root into a drain.
echo "==> amtool config routes test — an unlabelled alert must still reach a receiver"
fallback_receiver="$(amtool config routes test \
  --config.file=/ops/alertmanager/alertmanager.yml \
  alertname=SomeRuleThatForgotItsSeverityLabel)"
echo "    -> $fallback_receiver"
[ -n "$fallback_receiver" ] || {
  echo "FAIL: an alert with no severity label routes to no receiver at all" >&2
  exit 1
}

echo "==> alert notification config OK"
