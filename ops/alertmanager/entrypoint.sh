#!/bin/sh
# Entropia — fail-closed Alertmanager launcher (ADIM 31).
#
# THE POINT OF THIS FILE IS TO REFUSE TO START. Everything else about a
# monitoring stack degrades gracefully; a notification path must not. An
# Alertmanager that comes up with no reachable destination is strictly WORSE than
# no Alertmanager at all: the stack looks monitored, `/api/v2/status` is green,
# alerts arrive, get grouped, get "notified" — and nobody is told. That is the
# shape docs/releases/Entropia_V18_RC_Readiness_2026-08-07.md §6.3 calls a
# blocker, and shipping a placeholder receiver would have reproduced it behind a
# green checkmark.
#
# So the destination is a REQUIRED environment variable with no default:
#
#   ALERTMANAGER_NOTIFY_URL         (required) — where `severity: page` goes.
#   ALERTMANAGER_NOTIFY_URL_TICKET  (optional) — where `severity: ticket` goes.
#                                   Unset, the ticket lane is pointed at the page
#                                   destination and this script SAYS SO. That is a
#                                   loss of routing granularity, announced; it is
#                                   not a dropped notification.
#
# Unset, empty, or not an http(s) URL -> this script exits non-zero and
# Alertmanager is never exec'd. The container fails, `docker compose up` reports
# it, and scripts/alert-notification-proof.sh asserts exactly that exit.
#
# WHY IT WRITES FILES. ops/alertmanager/alertmanager.yml reads both endpoints via
# `url_file`, the same idiom ops/prometheus/prometheus.yml uses for
# `credentials_file`: a webhook URL is routinely itself a credential (Slack,
# PagerDuty and Opsgenie ingest URLs embed a key), so it must never be inlined
# into a tracked config. The ops/ tree is mounted READ-ONLY and the image runs as
# `nobody`, hence /tmp.
set -eu

RUNTIME_DIR=/tmp/alertmanager
CONFIG_FILE=/ops/alertmanager/alertmanager.yml

fail() {
  # stderr, and with the variable named: a container that dies in a compose log
  # gets read by someone who does not have this file open.
  echo "alertmanager-entrypoint: FATAL: $1" >&2
  echo "alertmanager-entrypoint: refusing to start. An Alertmanager with no reachable" >&2
  echo "alertmanager-entrypoint: destination reports success while notifying nobody;" >&2
  echo "alertmanager-entrypoint: that failure mode is the reason this check exists." >&2
  exit 78  # EX_CONFIG
}

require_url() {
  # $1 = variable name (for the message), $2 = value
  case "$2" in
    "")
      fail "$1 is unset or empty. Set it to the endpoint that must receive Entropia alerts." ;;
    http://*|https://*)
      : ;;
    *)
      fail "$1 is set to a value that is not an http:// or https:// URL. A non-URL here would load, look configured, and never deliver." ;;
  esac
}

NOTIFY_URL="${ALERTMANAGER_NOTIFY_URL:-}"
require_url ALERTMANAGER_NOTIFY_URL "$NOTIFY_URL"

TICKET_URL="${ALERTMANAGER_NOTIFY_URL_TICKET:-}"
if [ -z "$TICKET_URL" ]; then
  TICKET_URL="$NOTIFY_URL"
  echo "alertmanager-entrypoint: ALERTMANAGER_NOTIFY_URL_TICKET is unset — routing" >&2
  echo "alertmanager-entrypoint: severity=ticket alerts to the page destination. Delivery" >&2
  echo "alertmanager-entrypoint: is unaffected; only the page/ticket destination split is." >&2
else
  require_url ALERTMANAGER_NOTIFY_URL_TICKET "$TICKET_URL"
fi

mkdir -p "$RUNTIME_DIR"
# 0600: the URL may embed a credential. The directory is a container-local tmpfs
# path, never a mount, so it cannot leak back into the working tree.
umask 077
printf '%s\n' "$NOTIFY_URL" > "$RUNTIME_DIR/notify_url"
printf '%s\n' "$TICKET_URL" > "$RUNTIME_DIR/notify_url_ticket"

# Deliberately NOT echoing the URLs: a compose log is not a secret store. The
# scheme + host shape is enough to tell "configured" from "misconfigured".
echo "alertmanager-entrypoint: notification path configured (page + ticket destinations written)."

exec /bin/alertmanager \
  --config.file="$CONFIG_FILE" \
  --storage.path=/alertmanager \
  --web.listen-address=:9093 \
  --cluster.listen-address= \
  "$@"
